"""安全列表管理 — 查看/添加/删除入站和出站安全规则 + 一键放行所有端口"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app import models
from app.auth import get_current_user
from app import oci_client
import oci

router = APIRouter(prefix="/api/security-rules", tags=["安全列表"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class VcnItem(BaseModel):
    vcn_id: str
    display_name: str
    cidr_block: Optional[str] = None
    ipv6_cidr_blocks: Optional[List[str]] = None


class SecurityRuleInfo(BaseModel):
    """安全规则展示项"""
    is_stateless: bool = False
    protocol: str
    source_or_destination: str
    source_port: Optional[str] = None
    destination_port: Optional[str] = None
    type_and_code: Optional[str] = None
    description: Optional[str] = None


class SecurityRuleListResponse(BaseModel):
    rules: List[SecurityRuleInfo]
    total: int


class AddIngressRuleRequest(BaseModel):
    region: str
    vcn_id: str
    is_stateless: bool = False
    source_type: str = "CIDR_BLOCK"  # CIDR_BLOCK / SERVICE_CIDR_BLOCK
    source: str = "0.0.0.0/0"
    protocol: str = "all"  # all / 6(TCP) / 17(UDP) / 1(ICMP)
    source_port: Optional[str] = None  # e.g. "80" or "1024-65535"
    destination_port: Optional[str] = None
    icmp_type: Optional[int] = None
    icmp_code: Optional[int] = None
    description: Optional[str] = None


class AddEgressRuleRequest(BaseModel):
    region: str
    vcn_id: str
    is_stateless: bool = False
    destination_type: str = "CIDR_BLOCK"
    destination: str = "0.0.0.0/0"
    protocol: str = "all"
    source_port: Optional[str] = None
    destination_port: Optional[str] = None
    icmp_type: Optional[int] = None
    icmp_code: Optional[int] = None
    description: Optional[str] = None


class RemoveRulesRequest(BaseModel):
    region: str
    vcn_id: str
    rule_type: int  # 0=ingress, 1=egress
    indices: List[int]  # 要删除的规则索引列表


class ReleaseAllPortsRequest(BaseModel):
    region: str


# ── Protocol mapping ──────────────────────────────────────────────────────────

PROTOCOL_MAP = {
    "all": "所有协议",
    "1": "ICMP",
    "6": "TCP",
    "17": "UDP",
    "47": "GRE",
    "50": "ESP",
    "51": "AH",
    "58": "IPv6-ICMP",
}


def _protocol_display(code: str) -> str:
    return PROTOCOL_MAP.get(code, f"协议({code})")


def _port_range_str(port_range) -> Optional[str]:
    if port_range is None:
        return None
    min_p = port_range.min
    max_p = port_range.max
    if min_p == max_p:
        return str(min_p)
    return f"{min_p}-{max_p}"


def _parse_port_range(port_str: Optional[str]):
    """Parse port string like '80' or '1024-65535' into (min, max) tuple"""
    if not port_str:
        return None, None
    parts = port_str.strip().split("-")
    if len(parts) == 1:
        p = int(parts[0])
        return p, p
    return int(parts[0]), int(parts[1])


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


def _get_network_client(tenant, region: str):
    config = oci_client.build_oci_config(tenant, region)
    return oci.core.VirtualNetworkClient(config), config


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{tenant_id}/vcns")
async def list_vcns(
    tenant_id: int,
    region: str = Query(..., description="区域标识"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出指定区域下的所有 VCN"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, region)
        vcns = network.list_vcns(compartment_id=tenant.tenancy_ocid).data
        result = []
        for v in vcns:
            if v.lifecycle_state == "TERMINATED":
                continue
            result.append(VcnItem(
                vcn_id=v.id,
                display_name=v.display_name,
                cidr_block=v.cidr_block,
                ipv6_cidr_blocks=v.ipv6_cidr_blocks,
            ))
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取 VCN 列表失败: {str(e)}")


@router.get("/{tenant_id}/rules")
async def list_security_rules(
    tenant_id: int,
    region: str = Query(...),
    vcn_id: str = Query(...),
    rule_type: int = Query(0, description="0=入站, 1=出站"),
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """列出 VCN 默认安全列表的入站/出站规则"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, region)
        # 获取 VCN 的默认安全列表
        vcn = network.get_vcn(vcn_id=vcn_id).data
        security_list = network.get_security_list(security_list_id=vcn.default_security_list_id).data

        rules = []
        if rule_type == 0:
            # 入站规则
            for r in (security_list.ingress_security_rules or []):
                src_port = None
                dst_port = None
                type_and_code = None

                if r.protocol == "6" and r.tcp_options:
                    src_port = _port_range_str(r.tcp_options.source_port_range) if r.tcp_options.source_port_range else "全部"
                    dst_port = _port_range_str(r.tcp_options.destination_port_range) if r.tcp_options.destination_port_range else "全部"
                elif r.protocol == "17" and r.udp_options:
                    src_port = _port_range_str(r.udp_options.source_port_range) if r.udp_options.source_port_range else "全部"
                    dst_port = _port_range_str(r.udp_options.destination_port_range) if r.udp_options.destination_port_range else "全部"
                elif r.protocol == "1" and r.icmp_options:
                    type_and_code = str(r.icmp_options.type)
                    if r.icmp_options.code is not None:
                        type_and_code += f", {r.icmp_options.code}"
                elif r.protocol in ("6", "17"):
                    src_port = "全部"
                    dst_port = "全部"

                rules.append(SecurityRuleInfo(
                    is_stateless=r.is_stateless or False,
                    protocol=_protocol_display(r.protocol),
                    source_or_destination=r.source,
                    source_port=src_port,
                    destination_port=dst_port,
                    type_and_code=type_and_code,
                    description=r.description,
                ))
        else:
            # 出站规则
            for r in (security_list.egress_security_rules or []):
                src_port = None
                dst_port = None
                type_and_code = None

                if r.protocol == "6" and r.tcp_options:
                    src_port = _port_range_str(r.tcp_options.source_port_range) if r.tcp_options.source_port_range else "全部"
                    dst_port = _port_range_str(r.tcp_options.destination_port_range) if r.tcp_options.destination_port_range else "全部"
                elif r.protocol == "17" and r.udp_options:
                    src_port = _port_range_str(r.udp_options.source_port_range) if r.udp_options.source_port_range else "全部"
                    dst_port = _port_range_str(r.udp_options.destination_port_range) if r.udp_options.destination_port_range else "全部"
                elif r.protocol == "1" and r.icmp_options:
                    type_and_code = str(r.icmp_options.type)
                    if r.icmp_options.code is not None:
                        type_and_code += f", {r.icmp_options.code}"
                elif r.protocol in ("6", "17"):
                    src_port = "全部"
                    dst_port = "全部"

                rules.append(SecurityRuleInfo(
                    is_stateless=r.is_stateless or False,
                    protocol=_protocol_display(r.protocol),
                    source_or_destination=r.destination,
                    source_port=src_port,
                    destination_port=dst_port,
                    type_and_code=type_and_code,
                    description=r.description,
                ))

        return SecurityRuleListResponse(rules=rules, total=len(rules))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取安全规则失败: {str(e)}")


@router.post("/{tenant_id}/ingress")
async def add_ingress_rule(
    tenant_id: int,
    data: AddIngressRuleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """添加入站安全规则"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, data.region)
        vcn = network.get_vcn(vcn_id=data.vcn_id).data
        security_list = network.get_security_list(security_list_id=vcn.default_security_list_id).data

        # 构建新的入站规则
        builder_kwargs = {
            "is_stateless": data.is_stateless,
            "protocol": data.protocol,
            "source": data.source,
            "source_type": data.source_type,
            "description": data.description,
        }

        # TCP 端口
        if data.protocol == "6":
            tcp_opts_kwargs = {}
            src_min, src_max = _parse_port_range(data.source_port)
            dst_min, dst_max = _parse_port_range(data.destination_port)
            if src_min is not None:
                tcp_opts_kwargs["source_port_range"] = oci.core.models.PortRange(min=src_min, max=src_max)
            if dst_min is not None:
                tcp_opts_kwargs["destination_port_range"] = oci.core.models.PortRange(min=dst_min, max=dst_max)
            if tcp_opts_kwargs:
                builder_kwargs["tcp_options"] = oci.core.models.TcpOptions(**tcp_opts_kwargs)

        # UDP 端口
        if data.protocol == "17":
            udp_opts_kwargs = {}
            src_min, src_max = _parse_port_range(data.source_port)
            dst_min, dst_max = _parse_port_range(data.destination_port)
            if src_min is not None:
                udp_opts_kwargs["source_port_range"] = oci.core.models.PortRange(min=src_min, max=src_max)
            if dst_min is not None:
                udp_opts_kwargs["destination_port_range"] = oci.core.models.PortRange(min=dst_min, max=dst_max)
            if udp_opts_kwargs:
                builder_kwargs["udp_options"] = oci.core.models.UdpOptions(**udp_opts_kwargs)

        # ICMP
        if data.protocol == "1" and data.icmp_type is not None:
            icmp_kwargs = {"type": data.icmp_type}
            if data.icmp_code is not None:
                icmp_kwargs["code"] = data.icmp_code
            builder_kwargs["icmp_options"] = oci.core.models.IcmpOptions(**icmp_kwargs)

        new_rule = oci.core.models.IngressSecurityRule(**builder_kwargs)

        # 追加到现有规则
        ingress_rules = list(security_list.ingress_security_rules or [])
        ingress_rules.append(new_rule)

        network.update_security_list(
            security_list_id=vcn.default_security_list_id,
            update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                ingress_security_rules=ingress_rules,
                egress_security_rules=security_list.egress_security_rules,
            ),
        )
        return {"message": "入站规则添加成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加入站规则失败: {str(e)}")


@router.post("/{tenant_id}/egress")
async def add_egress_rule(
    tenant_id: int,
    data: AddEgressRuleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """添加出站安全规则"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, data.region)
        vcn = network.get_vcn(vcn_id=data.vcn_id).data
        security_list = network.get_security_list(security_list_id=vcn.default_security_list_id).data

        builder_kwargs = {
            "is_stateless": data.is_stateless,
            "protocol": data.protocol,
            "destination": data.destination,
            "destination_type": data.destination_type,
            "description": data.description,
        }

        if data.protocol == "6":
            tcp_opts_kwargs = {}
            src_min, src_max = _parse_port_range(data.source_port)
            dst_min, dst_max = _parse_port_range(data.destination_port)
            if src_min is not None:
                tcp_opts_kwargs["source_port_range"] = oci.core.models.PortRange(min=src_min, max=src_max)
            if dst_min is not None:
                tcp_opts_kwargs["destination_port_range"] = oci.core.models.PortRange(min=dst_min, max=dst_max)
            if tcp_opts_kwargs:
                builder_kwargs["tcp_options"] = oci.core.models.TcpOptions(**tcp_opts_kwargs)

        if data.protocol == "17":
            udp_opts_kwargs = {}
            src_min, src_max = _parse_port_range(data.source_port)
            dst_min, dst_max = _parse_port_range(data.destination_port)
            if src_min is not None:
                udp_opts_kwargs["source_port_range"] = oci.core.models.PortRange(min=src_min, max=src_max)
            if dst_min is not None:
                udp_opts_kwargs["destination_port_range"] = oci.core.models.PortRange(min=dst_min, max=dst_max)
            if udp_opts_kwargs:
                builder_kwargs["udp_options"] = oci.core.models.UdpOptions(**udp_opts_kwargs)

        if data.protocol == "1" and data.icmp_type is not None:
            icmp_kwargs = {"type": data.icmp_type}
            if data.icmp_code is not None:
                icmp_kwargs["code"] = data.icmp_code
            builder_kwargs["icmp_options"] = oci.core.models.IcmpOptions(**icmp_kwargs)

        new_rule = oci.core.models.EgressSecurityRule(**builder_kwargs)

        egress_rules = list(security_list.egress_security_rules or [])
        egress_rules.append(new_rule)

        network.update_security_list(
            security_list_id=vcn.default_security_list_id,
            update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                ingress_security_rules=security_list.ingress_security_rules,
                egress_security_rules=egress_rules,
            ),
        )
        return {"message": "出站规则添加成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加出站规则失败: {str(e)}")


@router.post("/{tenant_id}/remove")
async def remove_rules(
    tenant_id: int,
    data: RemoveRulesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """删除安全规则（按索引）"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, data.region)
        vcn = network.get_vcn(vcn_id=data.vcn_id).data
        security_list = network.get_security_list(security_list_id=vcn.default_security_list_id).data

        ingress_rules = list(security_list.ingress_security_rules or [])
        egress_rules = list(security_list.egress_security_rules or [])

        # 按索引删除（从大到小排序避免索引偏移）
        indices_sorted = sorted(data.indices, reverse=True)
        if data.rule_type == 0:
            for idx in indices_sorted:
                if 0 <= idx < len(ingress_rules):
                    ingress_rules.pop(idx)
        else:
            for idx in indices_sorted:
                if 0 <= idx < len(egress_rules):
                    egress_rules.pop(idx)

        network.update_security_list(
            security_list_id=vcn.default_security_list_id,
            update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                ingress_security_rules=ingress_rules,
                egress_security_rules=egress_rules,
            ),
        )
        return {"message": "规则删除成功"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"删除规则失败: {str(e)}")


@router.post("/{tenant_id}/release-all")
async def release_all_ports(
    tenant_id: int,
    data: ReleaseAllPortsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """一键放行所有端口 — 为所有 VCN 添加 0.0.0.0/0 和 ::/0 的全协议入站+出站规则"""
    tenant = await _get_tenant(tenant_id, db, current_user)
    try:
        network, config = _get_network_client(tenant, data.region)
        vcns = network.list_vcns(compartment_id=tenant.tenancy_ocid).data
        vcns = [v for v in vcns if v.lifecycle_state != "TERMINATED"]

        if not vcns:
            raise HTTPException(status_code=400, detail="当前区域未创建 VCN，无法放行安全列表")

        released_count = 0
        for vcn in vcns:
            security_list = network.get_security_list(
                security_list_id=vcn.default_security_list_id
            ).data

            ingress_rules = list(security_list.ingress_security_rules or [])
            egress_rules = list(security_list.egress_security_rules or [])

            # IPv4 全放行
            ingress_rules.append(oci.core.models.IngressSecurityRule(
                source_type="CIDR_BLOCK",
                source="0.0.0.0/0",
                protocol="all",
                is_stateless=False,
            ))
            egress_rules.append(oci.core.models.EgressSecurityRule(
                destination_type="CIDR_BLOCK",
                destination="0.0.0.0/0",
                protocol="all",
                is_stateless=False,
            ))

            # 如果 VCN 有 IPv6，也放行
            if vcn.ipv6_cidr_blocks:
                ingress_rules.append(oci.core.models.IngressSecurityRule(
                    source_type="CIDR_BLOCK",
                    source="::/0",
                    protocol="all",
                    is_stateless=False,
                ))
                egress_rules.append(oci.core.models.EgressSecurityRule(
                    destination_type="CIDR_BLOCK",
                    destination="::/0",
                    protocol="all",
                    is_stateless=False,
                ))

            network.update_security_list(
                security_list_id=vcn.default_security_list_id,
                update_security_list_details=oci.core.models.UpdateSecurityListDetails(
                    ingress_security_rules=ingress_rules,
                    egress_security_rules=egress_rules,
                ),
            )
            released_count += 1

        return {"message": f"已放行 {released_count} 个 VCN 的所有端口及协议"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"放行安全列表失败: {str(e)}")
