import { DatePipe } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, DashboardData } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  readonly auth = inject(AuthService);
  data: DashboardData | null = null;
  error = '';

  ngOnInit(): void {
    this.api.dashboard().subscribe({
      next: (data) => {
        this.data = data;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Dashboard error:', err);
        this.error = 'Dashboard data could not be loaded. Confirm the Django API is running.';
        this.cdr.markForCheck();
      }
    });
  }

  connectedLenders(d: DashboardData): number {
    return d.lenders.filter((l) => l.api_status === 'CONNECTED').length;
  }
  confirmed(d: DashboardData): number {
    return d.assessments.filter((a) => a.verification_status === 'CONFIRMED').length;
  }
  activeConsents(d: DashboardData): number {
    return d.consents.filter((c) => c.status === 'ACTIVE').length;
  }
}
