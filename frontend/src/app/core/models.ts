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
