import { Injectable, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, catchError, map, of, tap } from 'rxjs';
import { Router } from '@angular/router';

interface LoginResponse {
  username: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly authenticated = signal(false);
  readonly isAuthenticated = (): boolean => this.authenticated();

  verifySession(): Observable<boolean> {
    return this.http.get<LoginResponse>('/api/auth/me/').pipe(
      tap(() => {
        this.authenticated.set(true);
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
      tap(() => {
        this.authenticated.set(true);
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
    void this.router.navigate(['/']);
  }
}
