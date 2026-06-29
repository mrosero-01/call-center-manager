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
  days: Partial<Record<Weekday, TimeRange[]>>;
}

export interface ScheduleUpdatePayload {
  timezone: string;
  reason: string;
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

export interface AsteriskFamilyPreview {
  astdb_family: string;
  days: ScheduleDayPayload[];
  exists?: boolean;
  current_tenant?: string;
  name?: string;
}

export interface AsteriskInspectResult {
  contexts: string[];
  families: AsteriskFamilyPreview[];
}

export interface AsteriskImportRequest {
  tenant_code: string;
  tenant_name?: string;
  family?: string;
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
