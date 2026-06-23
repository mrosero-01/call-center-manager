import { HttpClient } from '@angular/common/http';
import { Injectable, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { CurrentUser } from './models';

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly currentUser = signal<CurrentUser | null>(null);

  constructor(private readonly http: HttpClient) {}

  ensureCsrfCookie(): Observable<{ detail: string }> {
    return this.http.get<{ detail: string }>('/api/auth/csrf/', {
      withCredentials: true
    });
  }

  login(username: string, password: string): Observable<CurrentUser> {
    return this.http
      .post<CurrentUser>(
        '/api/auth/login/',
        { username, password },
        { withCredentials: true }
      )
      .pipe(tap((user) => this.currentUser.set(user)));
  }

  logout(): Observable<void> {
    this.clearSessionState();

    return this.http
      .post<void>('/api/auth/logout/', {}, { withCredentials: true })
      .pipe(tap(() => this.clearSessionState()));
  }

  me(): Observable<CurrentUser> {
    return this.http
      .get<CurrentUser>('/api/me/', { withCredentials: true })
      .pipe(tap((user) => this.currentUser.set(user)));
  }

  clearSessionState(): void {
    this.currentUser.set(null);
  }
}
