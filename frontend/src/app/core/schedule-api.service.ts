import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  CallCenterLocation,
  ScheduleChangeLog,
  ScheduleSnapshot,
  ScheduleUpdatePayload
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

  getChangeLogs(locationId: number): Observable<ScheduleChangeLog[]> {
    return this.http.get<ScheduleChangeLog[]>(`/api/locations/${locationId}/schedule-changes/`, {
      withCredentials: true
    });
  }
}
