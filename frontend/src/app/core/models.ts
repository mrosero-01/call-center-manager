export interface Tenant {
  id: number;
  name: string;
  code: string;
}

export interface Membership {
  tenant: Tenant;
  role: 'admin' | 'operator';
}

export interface CurrentUser {
  id: number;
  username: string;
  is_superuser: boolean;
  memberships: Membership[];
}

export interface CallCenterLocation {
  id: number;
  name: string;
  code: string;
  astdb_family: string;
  tenant: string;
  is_active: boolean;
}

export interface TimeRange {
  start: string;
  end: string;
}

export type Weekday = 'Mon' | 'Tue' | 'Wed' | 'Thu' | 'Fri' | 'Sat' | 'Sun';

export interface ScheduleDayPayload {
  day_of_week: Weekday;
  ranges: TimeRange[];
}

export interface ScheduleSnapshot {
  location?: CallCenterLocation;
  timezone: string | null;
  sync_status?: 'pending' | 'synced' | 'failed';
  last_sync_error?: string;
  last_synced_at?: string | null;
  updated_at?: string | null;
  days: Partial<Record<Weekday, TimeRange[]>>;
}

export interface ScheduleUpdatePayload {
  timezone: string;
  reason: string;
  expected_updated_at?: string | null;
  days: ScheduleDayPayload[];
}

export interface SchedulePreviewPayload {
  timezone: string;
  days: ScheduleDayPayload[];
}

export interface SchedulePreviewAction {
  action: 'DBPut' | 'DBDel';
  day_of_week: Weekday;
  family: string;
  key: string;
  path: string;
  value: string;
  ranges: TimeRange[];
}

export interface SchedulePreview {
  location: CallCenterLocation;
  astdb_family: string;
  actions: SchedulePreviewAction[];
}

export interface ScheduleChangeLog {
  id: number;
  changed_by: string | null;
  reason: string;
  before_value: unknown;
  after_value: unknown;
  created_at: string;
}

export interface AdminCallCenterLocation {
  id: number;
  name: string;
  code: string;
  astdb_family: string;
  tenant: Tenant;
  is_active: boolean;
}

export interface AdminTenantMembership {
  id: number;
  username: string;
  tenant: Tenant;
  role: 'admin' | 'operator';
  is_active: boolean;
  created_at: string;
}

export interface CreateTenantPayload {
  name: string;
  code: string;
}

export interface CreateLocationPayload {
  tenant_id: number;
  name: string;
  code: string;
  astdb_family: string;
}

export interface CreateTenantUserPayload {
  tenant_id: number;
  username: string;
  password: string;
  role: 'admin' | 'operator';
}

export interface AsteriskFamilyPreview {
  astdb_family: string;
  days: ScheduleDayPayload[];
  exists?: boolean;
  is_active?: boolean;
  current_tenant?: string;
  name?: string;
}

export interface AsteriskInspectResult {
  contexts: string[];
  families: AsteriskFamilyPreview[];
}

export interface AsteriskInventoryLocation {
  id: number;
  name: string;
  code: string;
  astdb_family: string;
  tenant: string;
  is_active: boolean;
}

export interface AsteriskInventoryItem {
  name: string;
  has_context: boolean;
  has_astdb_schedule: boolean;
  days: ScheduleDayPayload[];
  django_location: AsteriskInventoryLocation | null;
  suggested_action: 'import' | 'update' | 'restore' | 'created' | 'create';
}

export interface AsteriskInventoryResult {
  items: AsteriskInventoryItem[];
}

export interface AsteriskHealth {
  ok: boolean;
  host?: string;
  port?: number;
  latency_ms?: number;
  message?: string;
  detail?: string;
}

export interface ScheduleComparisonDifference {
  day_of_week: Weekday;
  django_ranges: TimeRange[];
  asterisk_ranges: TimeRange[];
}

export interface ScheduleAsteriskComparison {
  astdb_family: string;
  has_context: boolean;
  context_name: string;
  in_sync: boolean;
  django_days: Partial<Record<Weekday, TimeRange[]>>;
  asterisk_days: Partial<Record<Weekday, TimeRange[]>>;
  differences: ScheduleComparisonDifference[];
  checked_at: string;
}

export interface AsteriskImportRequest {
  tenant_code: string;
  tenant_name?: string;
  family?: string;
}

export interface AsteriskImportSelectedRequest {
  tenant_code: string;
  tenant_name?: string;
  families: string[];
}

export interface AsteriskImportPreview {
  tenant: {
    code: string;
    name: string;
  };
  locations: AsteriskFamilyPreview[];
}

export interface AsteriskImportResult {
  tenant: Tenant;
  locations: AdminCallCenterLocation[];
  imported_days: number;
  created_count: number;
  updated_count: number;
  restored_count: number;
}

export interface ScheduleSyncJob {
  id: number;
  tenant: string;
  location: string;
  astdb_family: string;
  requested_by: string | null;
  reason: string;
  status: 'pending' | 'synced' | 'failed';
  attempts: number;
  last_error: string;
  synced_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProcessSyncJobsPayload {
  limit: number;
  retry_failed: boolean;
  max_attempts: number;
}

export interface ProcessSyncJobsResult {
  processed: number;
  synced: number;
  failed: number;
  failed_jobs: Array<{
    id: number;
    error: string;
  }>;
}
