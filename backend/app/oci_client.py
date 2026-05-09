"""OCI 客户端工厂 —— 根据租户配置动态构建 OCI config"""
import tempfile
import os
import oci
from typing import Optional


def build_oci_config(tenant) -> dict:
    """从数据库 Tenant 对象构建 OCI SDK config dict"""
    # 将 PEM 私钥写入临时文件（OCI SDK 需要文件路径）
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pem", mode="w")
    tmp.write(tenant.private_key)
    tmp.close()

    config = {
        "user": tenant.user_ocid,
        "fingerprint": tenant.fingerprint,
        "tenancy": tenant.tenancy_ocid,
        "region": tenant.region,
        "key_file": tmp.name,
    }
    return config, tmp.name


def cleanup_key_file(path: str):
    try:
        os.unlink(path)
    except Exception:
        pass


def get_compute_client(tenant):
    config, key_path = build_oci_config(tenant)
    client = oci.core.ComputeClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_identity_client(tenant):
    config, key_path = build_oci_config(tenant)
    client = oci.identity.IdentityClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_usage_client(tenant):
    config, key_path = build_oci_config(tenant)
    client = oci.usage_api.UsageapiClient(config)
    cleanup_key_file(key_path)
    return client, config


def get_network_client(tenant):
    config, key_path = build_oci_config(tenant)
    client = oci.core.VirtualNetworkClient(config)
    cleanup_key_file(key_path)
    return client, config


def list_instances(tenant) -> list:
    """列出租户下所有实例"""
    compute, config = get_compute_client(tenant)
    network, _ = get_network_client(tenant)
    identity, _ = get_identity_client(tenant)

    compartment_id = tenant.tenancy_ocid
    instances_resp = compute.list_instances(compartment_id=compartment_id)
    result = []
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
            "availability_domain": inst.availability_domain,
            "public_ip": public_ip,
            "time_created": inst.time_created.isoformat() if inst.time_created else None,
        })
    return result


def instance_action(tenant, instance_id: str, action: str) -> dict:
    """对实例执行操作: START / STOP / RESET / SOFTSTOP"""
    compute, config = get_compute_client(tenant)
    resp = compute.instance_action(instance_id=instance_id, action=action.upper())
    inst = resp.data
    return {
        "id": inst.id,
        "display_name": inst.display_name,
        "lifecycle_state": inst.lifecycle_state,
    }


def get_availability_domains(tenant) -> list:
    identity, config = get_identity_client(tenant)
    ads = identity.list_availability_domains(compartment_id=tenant.tenancy_ocid).data
    return [ad.name for ad in ads]


def get_subnet_id(tenant) -> Optional[str]:
    network, config = get_network_client(tenant)
    subnets = network.list_subnets(compartment_id=tenant.tenancy_ocid).data
    if subnets:
        return subnets[0].id
    return None


def get_image_id(tenant, shape_name: str) -> str:
    compute, config = get_compute_client(tenant)
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
    identity, config = get_identity_client(tenant)
    tenancy = identity.get_tenancy(tenant.tenancy_ocid).data
    return tenancy.description or tenant.name
