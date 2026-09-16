import { DatePipe } from '@angular/common';
import { ChangeDetectorRef, Component, inject, OnInit } from '@angular/core';
import { AdminLogEntry, ApiService } from '../core/api.service';

@Component({
  standalone: true,
  imports: [DatePipe],
  templateUrl: './audit-logs.component.html',
})
export class AuditLogsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  logs: AdminLogEntry[] = [];
  loading = true;
  error = '';

  ngOnInit(): void {
    this.api.auditLogs().subscribe({
      next: (logs) => { this.logs = logs; this.loading = false; this.cdr.markForCheck(); },
      error: (error: { status?: number }) => {
        this.loading = false;
        this.error = error.status === 401 || error.status === 403
          ? 'You must be signed in to view audit logs.'
          : 'Audit logs could not be loaded.';
        this.cdr.markForCheck();
      },
    });
  }

  actionLabel(flag: number): string {
    return flag === 1 ? 'Added' : flag === 2 ? 'Changed' : flag === 3 ? 'Deleted' : 'Other';
  }

  actionClass(flag: number): string {
    return flag === 1 ? 'badge-green' : flag === 3 ? 'badge-red' : 'badge-slate';
  }
}
