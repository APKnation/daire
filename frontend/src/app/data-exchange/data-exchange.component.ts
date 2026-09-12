import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ApiRecord, ApiService, Borrower, Lender, RoutingPolicy } from '../core/api.service';

@Component({
  standalone: true,
  imports: [FormsModule, JsonPipe],
  templateUrl: './data-exchange.component.html',
})
export class DataExchangeComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  lenders: Lender[] = [];
  policy: RoutingPolicy | null = null;
  selectedLenderId: number | null = null;
  borrowerReference = '';
  assessmentReference = '';
  borrower: Borrower | null = null;
  lastResult: ApiRecord | null = null;
  loading = false;
  message = '';
  error = '';
  readonly fields = [
    'active_loan_count', 'completed_loan_count', 'defaulted_loan_count',
    'total_outstanding_debt', 'on_time_payment_ratio', 'missed_payment_count',
    'late_payment_count', 'max_days_overdue', 'transaction_frequency',
    'income_frequency', 'balance_stability',
  ];
  readonly lenderFields = [
    'borrower_reference', 'customer_id', 'age', 'gender', 'employment_status', 'income',
    'business_information', 'account_information', 'account_reference', 'account_name',
    'transaction_frequency', 'income_frequency', 'savings', 'cash_flow_patterns',
    'account_activity', 'loans',
  ];

  ngOnInit(): void {
    this.api.lenders().subscribe((lenders) => { this.lenders = lenders; this.cdr.markForCheck(); });
    this.api.routingPolicies().subscribe((policies) => {
      this.policy = policies.find((item) => item.active) || policies[0] || null;
      this.cdr.markForCheck();
    });
  }

  toggle(field: string, target: 'lender_fields' | 'ai_fields' | 'blockchain_fields'): void {
    if (!this.policy) return;
    const fields = this.policy[target];
    this.policy[target] = fields.includes(field) ? fields.filter((item) => item !== field) : [...fields, field];
  }

  selected(target: 'lender_fields' | 'ai_fields' | 'blockchain_fields', field: string): boolean {
    return !!this.policy?.[target].includes(field);
  }

  savePolicy(): void {
    if (!this.policy?.id) return;
    this.api.updateRoutingPolicy(this.policy).subscribe({
      next: (policy) => { this.policy = policy; this.message = 'Routing policy saved.'; this.error = ''; this.cdr.markForCheck(); },
      error: () => { this.error = 'Routing policy could not be saved.'; this.cdr.markForCheck(); },
    });
  }

  pull(): void {
    const selected = this.lenders.find((lender) => lender.id === this.selectedLenderId);
    if (!selected || !this.borrowerReference.trim()) {
      this.error = 'Select a lender from the Lenders registry and enter a borrower reference.';
      return;
    }
    this.loading = true; this.message = ''; this.error = '';
    this.api.pullLenderData(selected.id!, this.borrowerReference.trim()).subscribe({
      next: (borrower) => { this.borrower = borrower; this.loading = false; this.message = 'Lender data pulled and merged into the borrower profile.'; this.cdr.markForCheck(); },
      error: (err) => { this.loading = false; this.error = err?.error?.detail || 'Lender pull failed. Check the lender API connection.'; this.cdr.markForCheck(); },
    });
  }

  pushAi(): void {
    if (!this.assessmentReference.trim()) return;
    this.runPush(this.api.pushAi(this.assessmentReference.trim()), 'AI result received.');
  }

  pushBlockchain(): void {
    if (!this.assessmentReference.trim()) return;
    this.runPush(this.api.pushBlockchain(this.assessmentReference.trim()), 'Blockchain result received.');
  }

  private runPush(request: ReturnType<ApiService['pushAi']>, success: string): void {
    this.loading = true; this.message = ''; this.error = '';
    request.subscribe({
      next: (result) => { this.lastResult = result; this.loading = false; this.message = success; this.cdr.markForCheck(); },
      error: (err) => { this.loading = false; this.error = err?.error?.detail || 'The destination system did not return a result.'; this.cdr.markForCheck(); },
    });
  }

  broadcast(): void {
    if (!this.borrower?.id || !this.lastResult) return;
    this.loading = true; this.message = ''; this.error = '';
    this.api.broadcastResult(this.borrower.id, 'CREDIT_RESULT', this.lastResult).subscribe({
      next: (result) => { this.loading = false; this.message = `${(result['broadcasts'] as unknown[] || []).length} lender(s) received the result.`; this.cdr.markForCheck(); },
      error: (err) => { this.loading = false; this.error = err?.error?.detail || 'Broadcast failed.'; this.cdr.markForCheck(); },
    });
  }
}
