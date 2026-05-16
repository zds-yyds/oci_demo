"""OCI 客户端工厂 —— 根据租户配置动态构建 OCI config"""
import oci
from typing import Optional


def build_oci_config(tenant, region: str = None) -> dict:
    """从数据库 Tenant 对象构建 OCI SDK config dict，可指定 region 覆盖"""
    # 如果未指定 region，使用租户的第一个区域
    if not region:
        regions = tenant.region.split(",")
        region = regions[0].strip()

    config = {
        "user": tenant.user_ocid,
        "fingerprint": tenant.fingerprint,
        "tenancy": tenant.tenancy_ocid,
        "region": region,
        "key_content": tenant.private_key,
    }
    return config


def get_compute_client(tenant, region: str = None):
    config = build_oci_config(tenant, region)
    client = oci.core.ComputeClient(config)
    return client, config


def get_identity_client(tenant, region: str = None):
    config = build_oci_config(tenant, region)
    client = oci.identity.IdentityClient(config)
    return client, config


def get_usage_client(tenant, region: str = None):
    config = build_oci_config(tenant, region)
    client = oci.usage_api.UsageapiClient(config)
    return client, config


def get_network_client(tenant, region: str = None):
    config = build_oci_config(tenant, region)
    client = oci.core.VirtualNetworkClient(config)
    return client, config


def list_all_compartments(tenant, region: str = None) -> list:
    """递归列出租户下所有 compartment（包括根和子区间）"""
    compartment_ids = [tenant.tenancy_ocid]
    try:
        identity, _ = get_identity_client(tenant, region)
        resp = identity.list_compartments(
            compartment_id=tenant.tenancy_ocid,
            compartment_id_in_subtree=True,
            access_level="ACCESSIBLE",
            lifecycle_state="ACTIVE",
        )
        for c in resp.data:
            compartment_ids.append(c.id)
    except Exception:
        pass
    return compartment_ids


def list_instances(tenant) -> list:
    """列出租户下所有区域、所有区间的实例（并发加速）"""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 优先使用 region_list，如果为空则回退到 region 字符串解析
    regions = []
    if hasattr(tenant, 'region_list') and tenant.region_list:
        regions = tenant.region_list
    elif hasattr(tenant, 'region') and tenant.region:
        regions = [r.strip() for r in tenant.region.split(",") if r.strip()]

    def _fetch_instance_details(compute, network, block_storage, compartment_id, inst, region):
        """获取单个实例的公网 IP、IPv6 和引导卷大小"""
        public_ip = None
        ipv6_addresses = []
        try:
            vnics = compute.list_vnic_attachments(
                compartment_id=compartment_id, instance_id=inst.id
            ).data
            for vnic_att in vnics:
                if vnic_att.lifecycle_state == "ATTACHED":
                    vnic = network.get_vnic(vnic_id=vnic_att.vnic_id).data
                    if not public_ip:
                        public_ip = vnic.public_ip
                    # 获取 IPv6 地址
                    try:
                        ipv6_list = network.list_ipv6s(vnic_id=vnic_att.vnic_id).data
                        for ipv6 in ipv6_list:
                            if ipv6.ip_address:
                                ipv6_addresses.append(ipv6.ip_address)
                    except Exception:
                        pass
        except Exception:
            pass

        boot_volume_size_gb = None
        try:
            boot_vol_attachments = compute.list_boot_volume_attachments(
                availability_domain=inst.availability_domain,
                compartment_id=compartment_id,
                instance_id=inst.id,
            ).data
            if boot_vol_attachments:
                boot_vol = block_storage.get_boot_volume(
                    boot_volume_id=boot_vol_attachments[0].boot_volume_id
                ).data
                boot_volume_size_gb = boot_vol.size_in_gbs
        except Exception:
            pass

        ocpus = None
        memory_in_gbs = None
        if inst.shape_config:
            ocpus = inst.shape_config.ocpus
            memory_in_gbs = inst.shape_config.memory_in_gbs

        return {
            "id": inst.id,
            "display_name": inst.display_name,
            "lifecycle_state": inst.lifecycle_state,
            "shape": inst.shape,
            "ocpus": ocpus,
            "memory_in_gbs": memory_in_gbs,
            "boot_volume_size_gb": boot_volume_size_gb,
            "region": region,
            "availability_domain": inst.availability_domain,
            "public_ip": public_ip,
            "ipv6_addresses": ipv6_addresses,
            "time_created": inst.time_created.isoformat() if inst.time_created else None,
        }

    def _fetch_region(region):
        """获取单个区域的所有实例"""
        region_results = []
        try:
            compute, config = get_compute_client(tenant, region)
            network = oci.core.VirtualNetworkClient(config)
            block_storage = oci.core.BlockstorageClient(config)

            compartment_ids = list_all_compartments(tenant, region)

            # 先收集所有实例
            all_instances = []
            for compartment_id in compartment_ids:
                try:
                    instances_resp = compute.list_instances(compartment_id=compartment_id)
                    for inst in instances_resp.data:
                        if inst.lifecycle_state not in ("TERMINATED", "TERMINATING"):
                            all_instances.append((compartment_id, inst))
                except Exception:
                    continue

            # 并发获取每个实例的详情
            with ThreadPoolExecutor(max_workers=8) as detail_executor:
                futures = [
                    detail_executor.submit(
                        _fetch_instance_details,
                        compute, network, block_storage, cid, inst, region
                    )
                    for cid, inst in all_instances
                ]
                for future in as_completed(futures):
                    try:
                        region_results.append(future.result())
                    except Exception:
                        continue
        except Exception:
            pass
        return region_results

    # 并发查询所有区域
    result = []
    with ThreadPoolExecutor(max_workers=len(regions) or 1) as region_executor:
        futures = [region_executor.submit(_fetch_region, r) for r in regions]
        for future in as_completed(futures):
            try:
                result.extend(future.result())
            except Exception:
                continue

    return result


def instance_action(tenant, instance_id: str, action: str, region: str = None) -> dict:
    """对实例执行操作: START / STOP / RESET / SOFTSTOP"""
    compute, config = get_compute_client(tenant, region)
    resp = compute.instance_action(instance_id=instance_id, action=action.upper())
    inst = resp.data
    return {
        "id": inst.id,
        "display_name": inst.display_name,
        "lifecycle_state": inst.lifecycle_state,
    }


def terminate_instance(tenant, instance_id: str, region: str = None, preserve_boot_volume: bool = False) -> dict:
    """终止（删除）实例"""
    compute, config = get_compute_client(tenant, region)
    compute.terminate_instance(
        instance_id=instance_id,
        preserve_boot_volume=preserve_boot_volume,
    )
    return {"message": "实例删除指令已发送", "instance_id": instance_id}


def update_instance_config(
    tenant,
    instance_id: str,
    region: str = None,
    display_name: str = None,
    shape: str = None,
    ocpus: float = None,
    memory_in_gbs: float = None,
) -> dict:
    """
    更改实例配置：名称、shape、OCPU、内存。
    对于 Flex 类型 shape（如 VM.Standard.A1.Flex / VM.Standard.E4.Flex），
    可以动态调整 OCPU 和内存大小。
    注意：更改 shape 需要实例处于 STOPPED 状态。
    """
    compute, config = get_compute_client(tenant, region)

    update_details_kwargs = {}

    if display_name:
        update_details_kwargs["display_name"] = display_name

    if shape:
        update_details_kwargs["shape"] = shape

    # 构建 shape_config（OCPU / 内存）
    if ocpus is not None or memory_in_gbs is not None:
        shape_config_kwargs = {}
        if ocpus is not None:
            shape_config_kwargs["ocpus"] = float(ocpus)
        if memory_in_gbs is not None:
            shape_config_kwargs["memory_in_gbs"] = float(memory_in_gbs)
        update_details_kwargs["shape_config"] = oci.core.models.UpdateInstanceShapeConfigDetails(
            **shape_config_kwargs
        )

    if not update_details_kwargs:
        return {"message": "未提供任何修改项", "instance_id": instance_id}

    update_details = oci.core.models.UpdateInstanceDetails(**update_details_kwargs)
    resp = compute.update_instance(instance_id=instance_id, update_instance_details=update_details)
    inst = resp.data

    return {
        "message": "实例配置更新成功",
        "instance_id": inst.id,
        "display_name": inst.display_name,
        "shape": inst.shape,
        "lifecycle_state": inst.lifecycle_state,
    }


def get_availability_domains(tenant, region: str = None) -> list:
    identity, config = get_identity_client(tenant, region)
    ads = identity.list_availability_domains(compartment_id=tenant.tenancy_ocid).data
    return [ad.name for ad in ads]


def get_subnet_id(tenant, region: str = None) -> Optional[str]:
    network, config = get_network_client(tenant, region)
    subnets = network.list_subnets(compartment_id=tenant.tenancy_ocid).data
    if subnets:
        return subnets[0].id
    return None


def get_image_id(tenant, shape_name: str, region: str = None) -> str:
    compute, config = get_compute_client(tenant, region)
    images = compute.list_images(
        compartment_id=tenant.tenancy_ocid, shape=shape_name
    ).data
    preferred = [
        "Canonical-Ubuntu-20.04-2024.08.26-0",
        "Canonical-Ubuntu-20.04-aarch64-2024.08.26-0",
    ]
    for img in images:
        if img.display_name in preferred:
            return img.id
    if images:
        return images[0].id
    raise ValueError(f"未找到适合 {shape_name} 的镜像")


def get_tenancy_name(tenant) -> str:
    """测试连接，使用第一个区域"""
    identity, config = get_identity_client(tenant)
    tenancy = identity.get_tenancy(tenant.tenancy_ocid).data
    return tenancy.description or tenant.name


def test_all_regions(tenant) -> dict:
    """测试所有区域的连接"""
    regions = []
    if hasattr(tenant, 'region_list') and tenant.region_list:
        regions = tenant.region_list
    elif hasattr(tenant, 'region') and tenant.region:
        regions = [r.strip() for r in tenant.region.split(",") if r.strip()]
    results = {}
    for region in regions:
        try:
            identity, _ = get_identity_client(tenant, region)
            identity.get_tenancy(tenant.tenancy_ocid)
            results[region] = "ok"
        except Exception as e:
            results[region] = str(e)
    return results
