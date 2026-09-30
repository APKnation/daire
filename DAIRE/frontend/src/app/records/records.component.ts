import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectorRef, Component, Input, OnDestroy, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';
import {
  AIReputationResult, ApiService, BlockchainTransaction, Borrower,
  Consent, IntegrationRequest, Lender, LoanApplication, Paged, PAGE_SIZE, SmartContractResult
} from '../core/api.service';
import { PagerComponent } from '../core/pager.component';

type RecordKind = 'lenders' | 'borrowers' | 'consents' | 'integrations' | 'ai-reputation' | 'blockchain';

@Component({
  standalone: true,
  imports: [DatePipe, DecimalPipe, PagerComponent],
  templateUrl: './records.component.html',
})
export class RecordsComponent implements OnInit, OnDestroy {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly cdr = inject(ChangeDetectorRef);
  private sub?: Subscription;

  private _kind: RecordKind = 'lenders';

  @Input()
  set kind(val: RecordKind) {
    if (val && val !== this._kind) {
      this._kind = val;
      this.page = 1;
      this.loadRecords();
    }
  }
  get kind(): RecordKind {
    return this._kind;
  }

  lenders: Lender[] = [];
  borrowers: Borrower[] = [];
  selectedBorrower: Borrower | null = null;
  borrowerSearchError = '';
  consents: Consent[] = [];
  integrations: IntegrationRequest[] = [];
  aiResults: AIReputationResult[] = [];
  smartContracts: SmartContractResult[] = [];
  blockchainTransactions: BlockchainTransaction[] = [];
  error = '';
  loading = false;
  page = 1;
  totalCount = 0;

  formatDetails(details: unknown): string {
    if (!details || typeof details !== 'object') return String(details ?? '—');
    return Object.entries(details as Record<string, unknown>)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(' · ');
  }

  /** Template helper — Angular templates cannot access the global Number() constructor. */
  toNumber(value: unknown): number {
    return Number(value);
  }

  ngOnInit(): void {
    const routeKind = this.route.snapshot.data['kind'] as RecordKind | undefined;
    if (routeKind) {
      this._kind = routeKind;
    }
    this.page = 1;
    this.loadRecords();

    this.sub = this.route.data.subscribe((data) => {
      const newKind = data['kind'] as RecordKind | undefined;
      if (newKind && newKind !== this._kind) {
        this._kind = newKind;
        this.page = 1;
        this.loadRecords();
      }
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  loadRecords(): void {
    this.lenders = [];
    this.borrowers = [];
    this.consents = [];
    this.integrations = [];
    this.aiResults = [];
    this.smartContracts = [];
    this.blockchainTransactions = [];
    this.selectedBorrower = null;
    this.borrowerSearchError = '';
    this.error = '';
    this.totalCount = 0;
    this.loading = true;
    this.cdr.markForCheck();

    const handleData = <T>(assign: (data: T) => void) => ({
      next: (data: T) => {
        assign(data);
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: (error: { status?: number }) => {
        this.loading = false;
        this.error = error.status === 401 || error.status === 403
          ? 'Your session has expired. Sign in again using the same host as this page.'
          : `${this._kind} could not be loaded.`;
        this.cdr.markForCheck();
      }
    });

    const handlePaged = <T>(assign: (items: T[]) => void) => ({
      next: (paged: Paged<T>) => {
        assign(paged.items);
        this.totalCount = paged.count;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: (error: { status?: number }) => {
        this.loading = false;
        this.error = error.status === 401 || error.status === 403
          ? 'Your session has expired. Sign in again using the same host as this page.'
          : `${this._kind} could not be loaded.`;
        this.cdr.markForCheck();
      }
    });

    switch (this._kind) {
      case 'lenders':
        this.api.paged<Lender>('/api/lenders/', this.page).subscribe(handlePaged((data) => this.lenders = data));
        break;
      case 'borrowers':
        this.api.borrowerSearch().subscribe(handleData((data) => this.borrowers = data));
        break;
      case 'consents':
        this.api.paged<Consent>('/api/consents/', this.page).subscribe(handlePaged((data) => this.consents = data));
        break;
      case 'integrations':
        this.api.paged<IntegrationRequest>('/api/integrations/request-credit-data/', this.page).subscribe(handlePaged((data) => this.integrations = data));
        break;
      case 'ai-reputation':
        this.api.paged<AIReputationResult>('/api/ai-reputation/', this.page).subscribe(handlePaged((data) => this.aiResults = data));
        break;
      case 'blockchain':
        // One verification view: on-chain scores (smart contract results) plus
        // the raw blockchain transactions. The pager follows the scores; the
        // transaction list loads alongside without touching pagination.
        this.api.paged<SmartContractResult>('/api/smart-contract/', this.page)
          .subscribe(handlePaged((data) => this.smartContracts = data));
        this.api.paged<BlockchainTransaction>('/api/blockchain/', this.page).subscribe({
          next: (paged) => { this.blockchainTransactions = paged.items; this.cdr.markForCheck(); },
          error: () => this.cdr.markForCheck(),
        });
        break;
      default:
        this.loading = false;
        this.cdr.markForCheck();
        break;
    }
  }

  changePage(next: number): void {
    if (next < 1 || (this.totalCount > 0 && next > Math.ceil(this.totalCount / PAGE_SIZE))) return;
    this.page = next;
    this.loadRecords();
  }

  searchBorrowers(lenderName: string, accountReference: string, borrowerReference: string): void {
    this.borrowerSearchError = '';
    this.api.borrowerSearch(lenderName.trim(), accountReference.trim(), borrowerReference.trim()).subscribe({
      next: (data) => {
        this.borrowers = data;
        this.selectedBorrower = null;
        this.cdr.markForCheck();
      },
      error: () => {
        this.borrowerSearchError = 'Borrower search could not be completed.';
        this.cdr.markForCheck();
      },
    });
  }

  selectBorrower(borrower: Borrower): void {
    this.selectedBorrower = borrower;
  }

  totalOutstanding(borrower: Borrower): number {
    return Number(borrower.financial_profile?.total_outstanding_debt || 0);
  }

  /** Latest application per lender — what the borrower is currently asking for. */
  currentApplications(borrower: Borrower): LoanApplication[] {
    const apps = [...(borrower.loan_applications || [])];
    apps.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''));
    const seen = new Set<string>();
    return apps.filter((app) => {
      const key = app.lender_name || `#${app.lender ?? 'central'}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  appliedTotal(borrower: Borrower): number {
    return this.currentApplications(borrower)
      .reduce((sum, app) => sum + Number(app.applied_amount || 0), 0);
  }

  paymentTotal(borrower: Borrower): number {
    return (borrower.loans || []).reduce(
      (total, loan) => total + loan.repayments.reduce((sum, payment) => sum + Number(payment.repayment_amount || 0), 0),
      0,
    );
  }
}
