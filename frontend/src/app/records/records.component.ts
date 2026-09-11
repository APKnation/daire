import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, Input, OnInit, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { AIReputationResult, ApiService, AuditLog, BlockchainTransaction, Borrower, Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult } from '../core/api.service';

type RecordKind = 'lenders' | 'borrowers' | 'consents' | 'integrations' | 'credit-profiles' | 'features' | 'ai-reputation' | 'smart-contract' | 'blockchain' | 'audit-logs';

@Component({
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  templateUrl: './records.component.html',
})
export class RecordsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  @Input() kind: RecordKind = 'lenders';
  lenders: Lender[] = [];
  borrowers: Borrower[] = [];
  consents: Consent[] = [];
  integrations: IntegrationRequest[] = [];
  creditProfiles: CreditProfile[] = [];
  auditLogs: AuditLog[] = [];
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
      this.kind = routeKind;
    }
    this.loadRecords();

    this.route.data.subscribe((data) => {
      const newKind = (data['kind'] as RecordKind | undefined) ?? 'lenders';
      if (newKind !== this.kind) {
        this.kind = newKind;
        this.loadRecords();
      }
    });
  }

  private loadRecords(): void {
    this.lenders = [];
    this.borrowers = [];
    this.consents = [];
    this.integrations = [];
    this.creditProfiles = [];
    this.auditLogs = [];
    this.features = [];
    this.aiResults = [];
    this.smartContracts = [];
    this.blockchainTransactions = [];
    this.error = '';
    this.loading = true;
    const handleData = <T>(assign: (data: T) => void) => ({
      next: (data: T) => {
        assign(data);
        this.loading = false;
      },
      error: (error: { status?: number }) => {
        this.loading = false;
        this.error = error.status === 401 || error.status === 403
          ? 'Your session has expired. Sign in again using the same host as this page.'
          : `${this.kind} could not be loaded.`;
      }
    });

    if (this.kind === 'lenders') {
      this.api.lenders().subscribe(handleData((data) => this.lenders = data));
    } else if (this.kind === 'borrowers') {
      this.api.borrowers().subscribe(handleData((data) => this.borrowers = data));
    } else if (this.kind === 'consents') {
      this.api.consents().subscribe(handleData((data) => this.consents = data));
    } else if (this.kind === 'integrations') {
      this.api.integrations().subscribe(handleData((data) => this.integrations = data));
    } else if (this.kind === 'audit-logs') {
      this.api.auditLogs().subscribe(handleData((data) => this.auditLogs = data));
    } else if (this.kind === 'credit-profiles') {
      this.api.creditProfiles().subscribe(handleData((data) => this.creditProfiles = data));
    } else if (this.kind === 'features') {
      this.api.features().subscribe(handleData((data) => this.features = data));
    } else if (this.kind === 'ai-reputation') {
      this.api.aiReputation().subscribe(handleData((data) => this.aiResults = data));
    } else if (this.kind === 'smart-contract') {
      this.api.smartContracts().subscribe(handleData((data) => this.smartContracts = data));
    } else {
      this.api.blockchain().subscribe(handleData((data) => this.blockchainTransactions = data));
    }
  }
}
