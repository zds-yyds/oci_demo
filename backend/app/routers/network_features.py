"""网络功能 — 一键附加 IPv6 / 一键开启下行 500Mbps"""
import time
import logging
import threading
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/network", tags=["网络功能"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class AttachIpv6Request(BaseModel):
    region: str
    instance_id: str


class Enable500MRequest(BaseModel):
    region: str
    instance_id: str
    ssh_port: int = 22


class Disable500MRequest(BaseModel):
    region: str
    instance_id: str
    retain_nlb: bool = False  # 是否保留网络负载平衡器
    retain_nat_gw: bool = False  # 是否保留 NAT 网关


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_tenant(tenant_id: int, db: AsyncSession, current_user: models.User) -> models.Tenant:
    stmt = select(models.Tenant).options(selectinload(models.Tenant.regions)).where(models.Tenant.id == tenant_id)
    result = await db.execute(stmt)
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="租户不存在")
    if not current_user.is_admin and tenant.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权访问")
    return tenant


def _get_vnic_by_instance(compute_client, network_client, compartment_id, instance_id):
    """获取实例的主 VNIC"""
    vnics = compute_client.list_vnic_attachments(
        compartment_id=compartment_id, instance_id=instance_id
    ).data
    for va in vnics:
        if va.lifecycle_state == "ATTACHED":
            vnic = network_client.get_vnic(vnic_id=va.vnic_id).data
            return vnic
    return None


def _get_vcn_by_instance(compute_client, network_client, compartment_id, instance_id):
    """通过实例获取其所在的 VCN"""
    vnic = _get_vnic_by_instance(compute_client, network_client, compartment_id, instance_id)
    if not vnic:
        return None, None
    subnet = network_client.get_subnet(subnet_id=vnic.subnet_id).data
    vcn = network_client.get_vcn(vcn_id=subnet.vcn_id).data
    return vcn, vnic


# ── IPv6 Endpoint ─────────────────────────────────────────────────────────────

@router.post("/{tenant_id}/attach-ipv6")
async def attach_ipv6(
    tenant_id: int,
    data: AttachIpv6Request,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """一键为实例附加 IPv6 地址"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        config = oci_client.build_oci_config(tenant, data.region)
        compute = oci.core.ComputeClient(config)
        network = oci.core.VirtualNetworkClient(config)
        compartment_id = tenant.tenancy_ocid

        # 获取实例的 VCN 和 VNIC
        vcn, vnic = _get_vcn_by_instance(compute, network, compartment_id, data.instance_id)
        if not vcn or not vnic:
            raise HTTPException(status_code=400, detail="无法获取实例的 VCN/VNIC 信息")

        # 1. 为 VCN 添加 IPv6 CIDR（如果还没有）
        if not vcn.ipv6_cidr_blocks:
            try:
                network.add_ipv6_vcn_cidr(
                    vcn_id=vcn.id,
                    add_vcn_ipv6_cidr_details=oci.core.models.AddVcnIpv6CidrDetails(
                        is_oracle_gua_allocation_enabled=True,
                    ),
                )
                # 刷新 VCN 信息
                time.sleep(2)
                vcn = network.get_vcn(vcn_id=vcn.id).data
            except Exception as e:
                if "already has" not in str(e).lower():
                    raise

        # 2. 为子网添加 IPv6 CIDR
        subnet = network.get_subnet(subnet_id=vnic.subnet_id).data
        if vcn.ipv6_cidr_blocks and not subnet.ipv6_cidr_block:
            v6_cidr = vcn.ipv6_cidr_blocks[0]
            subnet_v6_cidr = v6_cidr.replace("/56", "/64")
            try:
                network.update_subnet(
                    subnet_id=subnet.id,
                    update_subnet_details=oci.core.models.UpdateSubnetDetails(
                        ipv6_cidr_block=subnet_v6_cidr,
                    ),
                )
            except Exception as e:
                if "already" not in str(e).lower() and "ULA CIDR" not in str(e):
                    raise

        # 3. 确保有 Internet 网关和路由规则
        gateways = network.list_internet_gateways(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        if not gateways:
            gw = network.create_internet_gateway(
                create_internet_gateway_details=oci.core.models.CreateInternetGatewayDetails(
                    compartment_id=compartment_id,
                    vcn_id=vcn.id,
                    display_name="ipv6-gateway",
                    is_enabled=True,
                ),
            ).data
        else:
            gw = gateways[0]

        # 4. 放行 IPv6 安全规则
        try:
            security_list = network.get_security_list(
                security_list_id=vcn.default_security_list_id
            ).data
            ingress_rules = list(security_list.ingress_security_rules or [])
            egress_rules = list(security_list.egress_security_rules or [])

            # 添加 ::/0 全协议规则
            has_ipv6_ingress = any(r.source == "::/0" and r.protocol == "all" for r in ingress_rules)
            if not has_ipv6_ingress:
                ingress_rules.append(oci.core.models.IngressSecurityRule(
                    source_type="CIDR_BLOCK", source="::/0", protocol="all", is_stateless=False,
                ))
            has_ipv6_egress = any(r.destination == "::/0" and r.protocol == "all" for r in egress_rules)
            if not has_ipv6_egress:
                egress_rules.append(oci.core.models.EgressSecurityRule(
                    destination_type="CIDR_BLOCK", destination="::/0", protocol="all", is_stateless=False,
                ))

            network.update_security_list(
                security_list_id=vcn.default_security_list_id,
                update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                    ingress_security_rules=ingress_rules,
                    egress_security_rules=egress_rules,
                ),
            )
        except Exception:
            pass

        # 5. 为 VNIC 创建 IPv6
        ipv6_resp = network.create_ipv6(
            create_ipv6_details=oci.core.models.CreateIpv6Details(
                vnic_id=vnic.id,
            ),
        )
        ipv6_address = ipv6_resp.data.ip_address

        return {"message": "IPv6 附加成功", "ipv6_address": ipv6_address}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"附加 IPv6 失败: {str(e)}")


# ── 500Mbps Endpoints ─────────────────────────────────────────────────────────

@router.post("/{tenant_id}/enable-500m")
async def enable_500m(
    tenant_id: int,
    data: Enable500MRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    一键开启下行 500Mbps（仅支持 AMD 免费实例）
    通过创建 Network Load Balancer + NAT 网关实现。
    此操作为异步执行，立即返回。
    """
    tenant = await _get_tenant(tenant_id, db, current_user)

    # 验证实例是否为 AMD
    config = oci_client.build_oci_config(tenant, data.region)
    compute = oci.core.ComputeClient(config)
    try:
        instance = compute.get_instance(instance_id=data.instance_id).data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取实例信息失败: {str(e)}")

    if "E2" not in instance.shape and "E4" not in instance.shape and "E5" not in instance.shape:
        raise HTTPException(status_code=400, detail=f"仅支持 AMD 实例（当前 Shape: {instance.shape}）")

    # 异步执行
    tenant_data = {
        "tenancy_ocid": tenant.tenancy_ocid,
        "user_ocid": tenant.user_ocid,
        "fingerprint": tenant.fingerprint,
        "private_key": tenant.private_key,
        "region": data.region,
    }
    t = threading.Thread(
        target=_run_enable_500m,
        args=(tenant_data, data.instance_id, data.ssh_port),
        daemon=True,
    )
    t.start()

    return {"message": "一键开启下行 500Mbps 任务已提交，请稍后查看实例状态"}


@router.post("/{tenant_id}/disable-500m")
async def disable_500m(
    tenant_id: int,
    data: Disable500MRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """关闭下行 500Mbps（清理 NLB + NAT 网关）"""
    tenant = await _get_tenant(tenant_id, db, current_user)

    tenant_data = {
        "tenancy_ocid": tenant.tenancy_ocid,
        "user_ocid": tenant.user_ocid,
        "fingerprint": tenant.fingerprint,
        "private_key": tenant.private_key,
        "region": data.region,
    }
    t = threading.Thread(
        target=_run_disable_500m,
        args=(tenant_data, data.instance_id, data.retain_nlb, data.retain_nat_gw),
        daemon=True,
    )
    t.start()

    return {"message": "关闭下行 500Mbps 任务已提交"}


# ── Background workers ────────────────────────────────────────────────────────

def _build_config(tenant_data: dict) -> dict:
    return {
        "user": tenant_data["user_ocid"],
        "fingerprint": tenant_data["fingerprint"],
        "tenancy": tenant_data["tenancy_ocid"],
        "region": tenant_data["region"],
        "key_content": tenant_data["private_key"],
    }


def _run_enable_500m(tenant_data: dict, instance_id: str, ssh_port: int):
    """后台线程：创建 NLB + NAT 网关实现 500Mbps"""
    try:
        config = _build_config(tenant_data)
        compartment_id = tenant_data["tenancy_ocid"]
        compute = oci.core.ComputeClient(config)
        network = oci.core.VirtualNetworkClient(config)
        nlb_client = oci.network_load_balancer.NetworkLoadBalancerClient(config)

        instance = compute.get_instance(instance_id=instance_id).data
        vcn, vnic = _get_vcn_by_instance(compute, network, compartment_id, instance_id)
        if not vcn or not vnic:
            logger.error(f"[500M] 无法获取实例 VCN/VNIC: {instance_id}")
            return

        # 获取实例私有 IP
        private_ips = network.list_private_ips(vnic_id=vnic.id).data
        instance_pri_ip = private_ips[0].ip_address if private_ips else None
        if not instance_pri_ip:
            logger.error(f"[500M] 无法获取实例私有 IP: {instance_id}")
            return

        # 1. 创建或获取 NAT 网关
        nat_gateways = network.list_nat_gateways(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        nat_gateways = [g for g in nat_gateways if g.lifecycle_state == "AVAILABLE"]

        if nat_gateways:
            nat_gw = nat_gateways[0]
            logger.info(f"[500M] 使用已有 NAT 网关: {nat_gw.display_name}")
        else:
            nat_gw = network.create_nat_gateway(
                create_nat_gateway_details=oci.core.models.CreateNatGatewayDetails(
                    vcn_id=vcn.id,
                    compartment_id=compartment_id,
                    display_name="nat-gateway-500m",
                ),
            ).data
            # 等待 NAT 网关就绪
            for _ in range(30):
                gw = network.get_nat_gateway(nat_gateway_id=nat_gw.id).data
                if gw.lifecycle_state == "AVAILABLE":
                    break
                time.sleep(2)
            logger.info(f"[500M] NAT 网关创建成功: {nat_gw.display_name}")

        # 2. 获取子网
        subnets = network.list_subnets(compartment_id=compartment_id, vcn_id=vcn.id).data
        if not subnets:
            logger.error(f"[500M] 无子网可用: {vcn.id}")
            return
        subnet = subnets[0]

        # 3. 删除已有 NLB 并重建
        existing_nlbs = nlb_client.list_network_load_balancers(
            compartment_id=compartment_id
        ).data.items
        for nlb in existing_nlbs:
            if nlb.lifecycle_state == "ACTIVE":
                try:
                    nlb_client.delete_network_load_balancer(network_load_balancer_id=nlb.id)
                    logger.info(f"[500M] 删除已有 NLB: {nlb.display_name}")
                except Exception:
                    pass

        # 4. 创建 NLB（带重试）
        nlb = None
        for attempt in range(5):
            try:
                import datetime
                nlb_name = f"nlb-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
                nlb = nlb_client.create_network_load_balancer(
                    create_network_load_balancer_details=oci.network_load_balancer.models.CreateNetworkLoadBalancerDetails(
                        display_name=nlb_name,
                        compartment_id=compartment_id,
                        is_private=False,
                        subnet_id=subnet.id,
                        listeners={
                            "listener1": oci.network_load_balancer.models.ListenerDetails(
                                name="listener1",
                                default_backend_set_name="backend1",
                                protocol="TCP_AND_UDP",
                                port=0,
                            ),
                        },
                        backend_sets={
                            "backend1": oci.network_load_balancer.models.BackendSetDetails(
                                is_preserve_source=True,
                                is_fail_open=True,
                                policy="TWO_TUPLE",
                                health_checker=oci.network_load_balancer.models.HealthChecker(
                                    protocol="TCP",
                                    port=ssh_port,
                                ),
                                backends=[
                                    oci.network_load_balancer.models.Backend(
                                        target_id=instance_id,
                                        ip_address=instance_pri_ip,
                                        port=0,
                                        weight=1,
                                    ),
                                ],
                            ),
                        },
                    ),
                ).data
                break
            except Exception as e:
                logger.warning(f"[500M] 创建 NLB 第 {attempt+1} 次失败: {e}")
                time.sleep(30)

        if not nlb:
            logger.error("[500M] 创建 NLB 失败，已达最大重试次数")
            return

        # 等待 NLB 就绪
        for _ in range(60):
            nlb_status = nlb_client.get_network_load_balancer(
                network_load_balancer_id=nlb.id
            ).data
            if nlb_status.lifecycle_state == "ACTIVE":
                break
            time.sleep(5)

        logger.info(f"[500M] NLB 创建成功: {nlb.display_name}")

        # 5. 创建 NAT 路由表
        route_tables = network.list_route_tables(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        nat_rt = None
        for rt in route_tables:
            if rt.lifecycle_state != "AVAILABLE":
                continue
            for rule in (rt.route_rules or []):
                if (rule.network_entity_id == nat_gw.id and
                    rule.destination == "0.0.0.0/0"):
                    nat_rt = rt
                    break
            if nat_rt:
                break

        if not nat_rt:
            nat_rt = network.create_route_table(
                create_route_table_details=oci.core.models.CreateRouteTableDetails(
                    compartment_id=compartment_id,
                    vcn_id=vcn.id,
                    display_name="nat-route-500m",
                    route_rules=[
                        oci.core.models.RouteRule(
                            destination="0.0.0.0/0",
                            destination_type="CIDR_BLOCK",
                            network_entity_id=nat_gw.id,
                        ),
                    ],
                ),
            ).data
            # 等待路由表就绪
            for _ in range(15):
                rt_status = network.get_route_table(rt_id=nat_rt.id).data
                if rt_status.lifecycle_state == "AVAILABLE":
                    break
                time.sleep(2)
            logger.info(f"[500M] NAT 路由表创建成功: {nat_rt.display_name}")

        # 6. 绑定 VNIC 到 NAT 路由表
        network.update_vnic(
            vnic_id=vnic.id,
            update_vnic_details=oci.core.models.UpdateVnicDetails(
                skip_source_dest_check=True,
                route_table_id=nat_rt.id,
            ),
        )

        # 7. 放行安全规则
        try:
            security_list = network.get_security_list(
                security_list_id=vcn.default_security_list_id
            ).data
            ingress_rules = list(security_list.ingress_security_rules or [])
            egress_rules = list(security_list.egress_security_rules or [])
            ingress_rules.append(oci.core.models.IngressSecurityRule(
                source_type="CIDR_BLOCK", source="10.0.0.0/16", protocol="all", is_stateless=False,
            ))
            egress_rules.append(oci.core.models.EgressSecurityRule(
                destination_type="CIDR_BLOCK", destination="10.0.0.0/16", protocol="all", is_stateless=False,
            ))
            network.update_security_list(
                security_list_id=vcn.default_security_list_id,
                update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                    ingress_security_rules=ingress_rules,
                    egress_security_rules=egress_rules,
                ),
            )
        except Exception:
            pass

        logger.info(f"[500M] 实例 {instance.display_name} 已成功开启下行 500Mbps")

    except Exception as e:
        logger.error(f"[500M] 开启 500Mbps 失败: {e}", exc_info=True)


def _run_disable_500m(tenant_data: dict, instance_id: str, retain_nlb: bool, retain_nat_gw: bool):
    """后台线程：关闭 500Mbps，清理 NLB + NAT"""
    try:
        config = _build_config(tenant_data)
        compartment_id = tenant_data["tenancy_ocid"]
        compute = oci.core.ComputeClient(config)
        network = oci.core.VirtualNetworkClient(config)
        nlb_client = oci.network_load_balancer.NetworkLoadBalancerClient(config)

        vcn, vnic = _get_vcn_by_instance(compute, network, compartment_id, instance_id)
        if not vcn or not vnic:
            logger.error(f"[500M关闭] 无法获取实例 VCN/VNIC: {instance_id}")
            return

        # 1. 获取默认路由表（非 NAT 路由表）
        route_tables = network.list_route_tables(
            compartment_id=compartment_id, vcn_id=vcn.id
        ).data
        default_rt = None
        nat_rts = []
        for rt in route_tables:
            if rt.lifecycle_state != "AVAILABLE":
                continue
            if rt.id == vcn.default_route_table_id:
                default_rt = rt
            else:
                nat_rts.append(rt)

        # 2. 将 VNIC 绑定回默认路由表
        if default_rt:
            network.update_vnic(
                vnic_id=vnic.id,
                update_vnic_details=oci.core.models.UpdateVnicDetails(
                    skip_source_dest_check=True,
                    route_table_id=default_rt.id,
                ),
            )

        # 3. 清理 NAT 网关和路由表
        if not retain_nat_gw:
            # 清空并删除 NAT 路由表
            for rt in nat_rts:
                try:
                    network.update_route_table(
                        rt_id=rt.id,
                        update_route_table_details=oci.core.models.UpdateRouteTableDetails(
                            route_rules=[],
                        ),
                    )
                    time.sleep(2)
                    network.delete_route_table(rt_id=rt.id)
                except Exception:
                    pass

            # 删除 NAT 网关
            nat_gateways = network.list_nat_gateways(
                compartment_id=compartment_id, vcn_id=vcn.id
            ).data
            for gw in nat_gateways:
                try:
                    network.delete_nat_gateway(nat_gateway_id=gw.id)
                except Exception:
                    pass

        # 4. 删除 NLB
        if not retain_nlb:
            nlbs = nlb_client.list_network_load_balancers(
                compartment_id=compartment_id
            ).data.items
            for nlb in nlbs:
                try:
                    nlb_client.delete_network_load_balancer(network_load_balancer_id=nlb.id)
                except Exception:
                    pass

        logger.info(f"[500M关闭] 实例 {instance_id} 已成功关闭下行 500Mbps")

    except Exception as e:
        logger.error(f"[500M关闭] 关闭 500Mbps 失败: {e}", exc_info=True)
