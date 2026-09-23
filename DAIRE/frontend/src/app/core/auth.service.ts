import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { Router } from '@angular/router';

interface LoginResponse {
  username: string;
}

interface MeResponse {
  username: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly authenticated = signal(false);
  private readonly currentUsername = signal('');
  readonly isAuthenticated = (): boolean => this.authenticated();
  /** Signed-in operator name — drives the sidebar user card. */
  readonly username = (): string => this.currentUsername();

  verifySession(): Observable<boolean> {
    return this.http.get<MeResponse>('/api/auth/me/').pipe(
      tap((me) => {
        this.authenticated.set(true);
        this.currentUsername.set(me.username || '');
      }),
      map(() => true),
      catchError((error: { status?: number }) => {
        if (error.status === 401 || error.status === 403) {
          this.authenticated.set(false);
        }
        return of(false);
      }),
    );
  }

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http.post<LoginResponse>('/api/auth/login/', { username, password }).pipe(
      tap((response) => {
        this.authenticated.set(true);
        this.currentUsername.set(response.username || username);
      }),
    );
  }

  logout(): void {
    this.http.post('/api/auth/logout/', {}).subscribe({
      complete: () => this.finishLogout(),
      error: () => this.finishLogout(),
    });
  }

  private finishLogout(): void {
    this.authenticated.set(false);
    this.currentUsername.set('');
    void this.router.navigate(['/']);
  }
}
