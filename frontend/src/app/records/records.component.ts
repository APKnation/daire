import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { finalize } from 'rxjs';
import { AIReputationResult, ApiService, AuditLog, BlockchainTransaction, Borrower, Consent, CreditFeature, CreditProfile, IntegrationRequest, Lender, SmartContractResult } from '../core/api.service';

type RecordKind = 'lenders' | 'borrowers' | 'consents' | 'integrations' | 'credit-profiles' | 'features' | 'ai-reputation' | 'smart-contract' | 'blockchain' | 'audit-logs';

@Component({
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  templateUrl: './records.component.html',
})
export class RecordsComponent {
  private readonly api = inject(ApiService);
  kind: RecordKind = 'lenders';
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

  constructor() {
    const route = inject(ActivatedRoute);
    route.data.subscribe((data) => {
      this.kind = (data['kind'] as RecordKind | undefined) ?? 'lenders';
      this.loadRecords();
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
    const failed = (error: { status?: number }) => {
      this.loading = false;
      this.error = error.status === 401 || error.status === 403
        ? 'Your session has expired. Sign in again using the same host as this page.'
        : `${this.kind} could not be loaded.`;
    };
    const loaded = <T>(assign: (data: T) => void) => (data: T): void => {
      assign(data);
      this.loading = false;
    };
    const complete = () => { this.loading = false; };
    if (this.kind === 'lenders') {
      this.api.lenders().pipe(finalize(complete)).subscribe({ next: (data) => this.lenders = data, error: failed });
    } else if (this.kind === 'borrowers') {
      this.api.borrowers().pipe(finalize(complete)).subscribe({ next: (data) => this.borrowers = data, error: failed });
    } else if (this.kind === 'consents') {
      this.api.consents().pipe(finalize(complete)).subscribe({ next: (data) => this.consents = data, error: failed });
    } else if (this.kind === 'integrations') {
      this.api.integrations().pipe(finalize(complete)).subscribe({ next: (data) => this.integrations = data, error: failed });
    } else if (this.kind === 'audit-logs') {
      this.api.auditLogs().pipe(finalize(complete)).subscribe({ next: (data) => this.auditLogs = data, error: failed });
    } else if (this.kind === 'credit-profiles') {
      this.api.creditProfiles().pipe(finalize(complete)).subscribe({ next: loaded((data) => this.creditProfiles = data), error: failed });
    } else {
      if (this.kind === 'features') {
        this.api.features().pipe(finalize(complete)).subscribe({ next: (data) => this.features = data, error: failed });
      } else if (this.kind === 'ai-reputation') {
        this.api.aiReputation().pipe(finalize(complete)).subscribe({ next: (data) => this.aiResults = data, error: failed });
      } else if (this.kind === 'smart-contract') {
        this.api.smartContracts().pipe(finalize(complete)).subscribe({ next: (data) => this.smartContracts = data, error: failed });
      } else {
        this.api.blockchain().pipe(finalize(complete)).subscribe({ next: (data) => this.blockchainTransactions = data, error: failed });
      }
    }
  }
}
