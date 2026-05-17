// ── Auth ──────────────────────────────────────────────────────────────────────
export interface User {
  id: number
  username: string
  is_admin: boolean
  created_at: string
}

export interface LoginResponse {
  access_token: string
}

// ── Tenant ───────────────────────────────────────────────────────────────────
export interface Tenant {
  id: number
  name: string
  user_ocid: string
  fingerprint: string
  tenancy_ocid: string
  region: string[]
  is_active: boolean
  created_at: string
}

// ── Snipe Task ───────────────────────────────────────────────────────────────
export interface SnipeTask {
  id: number
  tenant_id: number
  region: string
  shape_name: string
  instance_ocpus: number
  instance_memory_in_gbs: number
  boot_volume_size_in_gbs: number
  frequency: number
  ssh_public_key: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'stopped'
  attempt_count: number
  result_ip: string | null
  log: string | null
  created_at: string
}

// ── Instance ─────────────────────────────────────────────────────────────────
export interface Instance {
  id: string
  display_name: string
  lifecycle_state: string
  shape: string
  ocpus: number | null
  memory_in_gbs: number | null
  boot_volume_size_gb: number | null
  availability_domain: string
  region: string
  public_ips: string[]
  private_ips: string[]
  time_created: string
  vnic_id: string | null
}

// ── Boot Volume ──────────────────────────────────────────────────────────────
export interface BootVolume {
  id: string
  display_name: string
  availability_domain: string
  size_in_gbs: number
  vpus_per_gb: number
  lifecycle_state: string
  region: string | null
  time_created: string | null
  instance_ocpus: number | null
  instance_memory_in_gbs: number | null
  instance_shape: string | null
}

// ── Cloudflare ───────────────────────────────────────────────────────────────
export interface CfConfig {
  id: number
  name: string
  zone_id: string
  domain: string | null
  created_at: string | null
}

export interface DnsRecord {
  id: string
  type: string
  name: string
  content: string
  ttl: number
  proxied: boolean
  created_on: string
}

// ── Notify ───────────────────────────────────────────────────────────────────
export interface NotifyConfig {
  id: number
  notify_type: 'email' | 'wecom'
  is_active: boolean
  smtp_server: string | null
  smtp_port: number | null
  sender_email: string | null
  sender_password: string | null
  receiver_email: string | null
  wecom_webhook: string | null
}

// ── Bills ────────────────────────────────────────────────────────────────────
export interface BillItem {
  start_time: string
  end_time: string
  currency: string
  amount_cny: number
}

export interface BillData {
  total_cny: number
  items: BillItem[]
}

// ── Security Rules ───────────────────────────────────────────────────────────
export interface SecurityRule {
  id: string
  direction: string
  protocol: string
  source: string
  destination: string
  source_port_range: string | null
  destination_port_range: string | null
  description: string | null
  is_stateless: boolean
}

// ── Traffic ──────────────────────────────────────────────────────────────────
export interface VnicInfo {
  vnic_id: string
  display_name: string
  instance_name: string
  public_ip: string | null
}

// ── IP Data ──────────────────────────────────────────────────────────────────
export interface IpDataItem {
  id: number
  ip: string
  region: string
  country: string
  city: string
  isp: string
  lat: number
  lon: number
  tenant_name: string
  created_at: string
}

// ── Region ───────────────────────────────────────────────────────────────────
export interface OciRegion {
  identifier: string
  name: string
}
