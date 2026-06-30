import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AdminCallCenterLocation,
  AsteriskHealth,
  AsteriskImportPreview,
  AsteriskImportRequest,
  AsteriskImportResult,
  AsteriskImportSelectedRequest,
  AsteriskInventoryResult,
  AsteriskInspectResult,
  CallCenterLocation,
  CreateLocationPayload,
  CreateTenantPayload,
  ProcessSyncJobsPayload,
  ProcessSyncJobsResult,
  ScheduleChangeLog,
  ScheduleAsteriskComparison,
  SchedulePreview,
  SchedulePreviewPayload,
  ScheduleSnapshot,
  ScheduleSyncJob,
  ScheduleUpdatePayload,
  Tenant
} from './models';

@Injectable({ providedIn: 'root' })
export class ScheduleApiService {
  constructor(private readonly http: HttpClient) {}

  getLocations(): Observable<CallCenterLocation[]> {
    return this.http.get<CallCenterLocation[]>('/api/locations/', {
      withCredentials: true
    });
  }

  getSchedule(locationId: number): Observable<ScheduleSnapshot> {
    return this.http.get<ScheduleSnapshot>(`/api/locations/${locationId}/schedule/`, {
      withCredentials: true
    });
  }

  updateSchedule(locationId: number, payload: ScheduleUpdatePayload): Observable<ScheduleSnapshot> {
    return this.http.put<ScheduleSnapshot>(`/api/locations/${locationId}/schedule/`, payload, {
      withCredentials: true
    });
  }

  previewSchedule(locationId: number, payload: SchedulePreviewPayload): Observable<SchedulePreview> {
    return this.http.post<SchedulePreview>(`/api/locations/${locationId}/schedule/preview/`, payload, {
      withCredentials: true
    });
  }

  refreshScheduleFromAsterisk(locationId: number): Observable<ScheduleSnapshot> {
    return this.http.post<ScheduleSnapshot>(`/api/locations/${locationId}/schedule/refresh-from-asterisk/`, {}, {
      withCredentials: true
    });
  }

  compareScheduleWithAsterisk(locationId: number): Observable<ScheduleAsteriskComparison> {
    return this.http.get<ScheduleAsteriskComparison>(`/api/locations/${locationId}/schedule/compare-asterisk/`, {
      withCredentials: true
    });
  }

  getChangeLogs(locationId: number): Observable<ScheduleChangeLog[]> {
    return this.http.get<ScheduleChangeLog[]>(`/api/locations/${locationId}/schedule-changes/`, {
      withCredentials: true
    });
  }

  getAdminTenants(): Observable<Tenant[]> {
    return this.http.get<Tenant[]>('/api/admin/tenants/', {
      withCredentials: true
    });
  }

  createAdminTenant(payload: CreateTenantPayload): Observable<Tenant> {
    return this.http.post<Tenant>('/api/admin/tenants/', payload, {
      withCredentials: true
    });
  }

  getAdminLocations(): Observable<AdminCallCenterLocation[]> {
    return this.http.get<AdminCallCenterLocation[]>('/api/admin/locations/', {
      withCredentials: true
    });
  }

  createAdminLocation(payload: CreateLocationPayload): Observable<AdminCallCenterLocation> {
    return this.http.post<AdminCallCenterLocation>('/api/admin/locations/', payload, {
      withCredentials: true
    });
  }

  archiveAdminLocation(locationId: number): Observable<AdminCallCenterLocation> {
    return this.http.post<AdminCallCenterLocation>(`/api/admin/locations/${locationId}/archive/`, {}, {
      withCredentials: true
    });
  }

  restoreAdminLocation(locationId: number): Observable<AdminCallCenterLocation> {
    return this.http.post<AdminCallCenterLocation>(`/api/admin/locations/${locationId}/restore/`, {}, {
      withCredentials: true
    });
  }

  inspectAsterisk(): Observable<AsteriskInspectResult> {
    return this.http.get<AsteriskInspectResult>('/api/admin/asterisk/inspect/', {
      withCredentials: true
    });
  }

  getAsteriskInventory(): Observable<AsteriskInventoryResult> {
    return this.http.get<AsteriskInventoryResult>('/api/admin/asterisk/inventory/', {
      withCredentials: true
    });
  }

  getAsteriskHealth(): Observable<AsteriskHealth> {
    return this.http.get<AsteriskHealth>('/api/admin/asterisk/health/', {
      withCredentials: true
    });
  }

  previewAsteriskImport(payload: AsteriskImportRequest): Observable<AsteriskImportPreview> {
    return this.http.post<AsteriskImportPreview>('/api/admin/asterisk/import-preview/', payload, {
      withCredentials: true
    });
  }

  previewSelectedAsteriskImport(payload: AsteriskImportSelectedRequest): Observable<AsteriskImportPreview> {
    return this.http.post<AsteriskImportPreview>('/api/admin/asterisk/import-selected-preview/', payload, {
      withCredentials: true
    });
  }

  importAsteriskSchedules(payload: AsteriskImportRequest): Observable<AsteriskImportResult> {
    return this.http.post<AsteriskImportResult>('/api/admin/asterisk/import/', payload, {
      withCredentials: true
    });
  }

  importSelectedAsteriskSchedules(payload: AsteriskImportSelectedRequest): Observable<AsteriskImportResult> {
    return this.http.post<AsteriskImportResult>('/api/admin/asterisk/import-selected/', payload, {
      withCredentials: true
    });
  }

  getSyncJobs(): Observable<ScheduleSyncJob[]> {
    return this.http.get<ScheduleSyncJob[]>('/api/admin/sync-jobs/', {
      withCredentials: true
    });
  }

  processSyncJobs(payload: ProcessSyncJobsPayload): Observable<ProcessSyncJobsResult> {
    return this.http.post<ProcessSyncJobsResult>('/api/admin/sync-jobs/process/', payload, {
      withCredentials: true
    });
  }
}
