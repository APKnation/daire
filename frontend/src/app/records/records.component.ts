import { DatePipe, DecimalPipe } from '@angular/common';
import { ChangeDetectorRef, Component, Input, OnDestroy, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { Subscription } from 'rxjs';
import {
  AIReputationResult, ApiService, BlockchainTransaction, Borrower,
  Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult
} from '../core/api.service';

type RecordKind = 'lenders' | 'borrowers' | 'consents' | 'integrations' | 'credit-profiles' | 'features' | 'ai-reputation' | 'smart-contract' | 'blockchain';

@Component({
  standalone: true,
  imports: [DatePipe, DecimalPipe],
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
  creditProfiles: CreditProfile[] = [];
  features: CreditFeature[] = [];
  aiResults: AIReputationResult[] = [];
  smartContracts: SmartContractResult[] = [];
  blockchainTransactions: BlockchainTransaction[] = [];
  error = '';
  loading = false;

  formatDetails(details: unknown): string {
    if (!details || typeof details !== 'object') return String(details ?? '—');
    return Object.entries(details as Record<string, unknown>)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(' · ');
  }

  ngOnInit(): void {
    const routeKind = this.route.snapshot.data['kind'] as RecordKind | undefined;
    if (routeKind) {
      this._kind = routeKind;
    }
    this.loadRecords();

    this.sub = this.route.data.subscribe((data) => {
      const newKind = data['kind'] as RecordKind | undefined;
      if (newKind && newKind !== this._kind) {
        this._kind = newKind;
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
    this.creditProfiles = [];
    this.features = [];
    this.aiResults = [];
    this.smartContracts = [];
    this.blockchainTransactions = [];
    this.selectedBorrower = null;
    this.borrowerSearchError = '';
    this.error = '';
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

    switch (this._kind) {
      case 'lenders':
        this.api.lenders().subscribe(handleData((data) => this.lenders = data));
        break;
      case 'borrowers':
        this.api.borrowerSearch().subscribe(handleData((data) => this.borrowers = data));
        break;
      case 'consents':
        this.api.consents().subscribe(handleData((data) => this.consents = data));
        break;
      case 'integrations':
        this.api.integrations().subscribe(handleData((data) => this.integrations = data));
        break;
      case 'credit-profiles':
        this.api.creditProfiles().subscribe(handleData((data) => this.creditProfiles = data));
        break;
      case 'features':
        this.api.features().subscribe(handleData((data) => this.features = data));
        break;
      case 'ai-reputation':
        this.api.aiReputation().subscribe(handleData((data) => this.aiResults = data));
        break;
      case 'smart-contract':
        this.api.smartContracts().subscribe(handleData((data) => this.smartContracts = data));
        break;
      case 'blockchain':
        this.api.blockchain().subscribe(handleData((data) => this.blockchainTransactions = data));
        break;
      default:
        this.loading = false;
        this.cdr.markForCheck();
        break;
    }
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

  paymentTotal(borrower: Borrower): number {
    return (borrower.loans || []).reduce(
      (total, loan) => total + loan.repayments.reduce((sum, payment) => sum + Number(payment.repayment_amount || 0), 0),
      0,
    );
  }
}
