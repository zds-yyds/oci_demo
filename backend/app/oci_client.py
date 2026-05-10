"""OCI 客户端工厂 —— 根据租户配置动态构建 OCI config"""
import tempfile
import os
import oci
from typing import Optional


def build_oci_config(tenant, region: str = None) -> dict:
    """从数据库 Tenant 对象构建 OCI SDK config dict，可指定 region 覆盖"""
    # 将 PEM 私钥写入临时文件（OCI SDK 需要文件路径）
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
    tmp.write(tenant.private_key)
    tmp.close()

    # 如果未指定 region，使用租户的第一个区域
    if not region:
        regions = tenant.region.split(",")
        region = regions[0].strip()

    config = {
        "user": tenant.user_ocid,
        "fingerprint": tenant.fingerprint,
        "tenancy": tenant.tenancy_ocid,
        "region": region,
        "key_file": tmp.name,
    }
    return config, tmp.name


def cleanup_key_file(path: str):
    try:
        os.unlink(path)
    except Exception:
        pass


def get_compute_client(tenant, region: str = None):
    config, key_path = build_oci_config(tenant, region)
    client = oci.core.ComputeClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_identity_client(tenant, region: str = None):
    config, key_path = build_oci_config(tenant, region)
    client = oci.identity.IdentityClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_usage_client(tenant, region: str = None):
    config, key_path = build_oci_config(tenant, region)
    client = oci.usage_api.UsageapiClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_network_client(tenant, region: str = None):
    config, key_path = build_oci_config(tenant, region)
    client = oci.core.VirtualNetworkClient(config)
    cleanup_key_file(key_path)
    return client, config


def list_instances(tenant) -> list:
    """列出租户下所有区域的实例"""
    regions = tenant.region_list if hasattr(tenant, 'region_list') else [r.strip() for r in tenant.region.split(",") if r.strip()]
    result = []
    for region in regions:
        try:
            compute, config = get_compute_client(tenant, region)
            network, _ = get_network_client(tenant, region)

            compartment_id = tenant.tenancy_ocid
            instances_resp = compute.list_instances(compartment_id=compartment_id)
            for inst in instances_resp.data:
                if inst.lifecycle_state in ("TERMINATED", "TERMINATING"):
                    continue
                public_ip = None
                try:
                    vnics = compute.list_vnic_attachments(
                        compartment_id=compartment_id, instance_id=inst.id
                    ).data
                    for vnic_att in vnics:
                        if vnic_att.lifecycle_state == "ATTACHED":
                            vnic = network.get_vnic(vnic_id=vnic_att.vnic_id).data
                            public_ip = vnic.public_ip
                            break
                except Exception:
                    pass
                result.append({
                    "id": inst.id,
                    "display_name": inst.display_name,
                    "lifecycle_state": inst.lifecycle_state,
                    "shape": inst.shape,
                    "region": region,
                    "availability_domain": inst.availability_domain,
                    "public_ip": public_ip,
                    "time_created": inst.time_created.isoformat() if inst.time_created else None,
                })
        except Exception:
            # 某个区域查询失败不影响其他区域
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
    regions = tenant.region_list if hasattr(tenant, 'region_list') else [r.strip() for r in tenant.region.split(",") if r.strip()]
    results = {}
    for region in regions:
        try:
            identity, _ = get_identity_client(tenant, region)
            identity.get_tenancy(tenant.tenancy_ocid)
            results[region] = "ok"
        except Exception as e:
            results[region] = str(e)
    return results
