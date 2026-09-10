import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ApiService, DashboardData } from '../core/api.service';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true,
  imports: [DatePipe, RouterLink],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent {
  private readonly api = inject(ApiService);
  readonly auth = inject(AuthService);
  data: DashboardData | null = null;
  error = '';

  constructor() {
    this.api.dashboard().subscribe({ next: (data) => this.data = data, error: () => this.error = 'Dashboard data could not be loaded. Confirm the Django API is running.' });
  }
  connectedLenders(data: DashboardData): number { return data.lenders.filter((lender) => lender.api_status === 'CONNECTED').length; }
  confirmed(data: DashboardData): number { return data.assessments.filter((assessment) => assessment.verification_status === 'CONFIRMED').length; }
  activeConsents(data: DashboardData): number { return data.consents.filter((consent) => consent.status === 'ACTIVE').length; }
}
