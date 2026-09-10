import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable, timeout } from 'rxjs';

export interface Lender {
  lender_id: string;
  institution_name: string;
  institution_type: string;
  api_status: string;
  api_base_url?: string;
  authentication_method?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Borrower {
  borrower_reference: string;
  id?: number;
  created_at?: string;
  updated_at?: string;
}

export interface Consent {
  consent_id: string;
  status: string;
  expires_at: string;
  borrower_id?: number;
  lender_id?: number;
  purpose?: string;
  granted_at?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Assessment {
  assessment_reference: string;
  borrower_reference: string;
  reputation: string;
  reputation_score: number | null;
  risk_level: string;
  credit_score: number | null;
  verification_status: string;
  [key: string]: unknown;
}

export interface IntegrationRequest {
  request_reference: string;
  lender_id: string;
  borrower_reference: string;
  status: string;
  error_message: string;
  raw_payload: unknown;
  created_at: string;
}

export interface AuditLog {
  id: number;
  event_type: string;
  actor: number | null;
  request_reference: string | null;
  details: unknown;
  created_at: string;
  updated_at: string;
}

export interface ApiRecord { [key: string]: unknown; }

export interface CreditProfile {
  id: number;
  borrower: number;
  integration_request: number | null;
  source_version: string;
  created_at: string;
  updated_at: string;
  profile_data: {
    active_loan_count: number;
    completed_loan_count: number;
    defaulted_loan_count: number;
    total_outstanding_debt: number;
    on_time_payment_ratio: number;
    missed_payment_count: number;
    late_payment_count: number;
    max_days_overdue: number;
    transaction_frequency: number;
    income_frequency: number;
    balance_stability: number;
  };
}

export interface CreditFeature {
  id: number;
  name: string;
  value: string | number;
  feature_version: string;
  profile: number;
  created_at: string;
}

export interface AIReputationResult {
  id: number;
  assessment: number;
  reputation: string;
  score: string | number;
  risk_level: string;
  behavior_summary: string;
  model_version: string;
  created_at: string;
}

export interface SmartContractResult {
  id: number;
  assessment: number;
  credit_score: number;
  ruleset_version: string;
  contract_address: string;
  created_at: string;
}

export interface BlockchainTransaction {
  id: number;
  assessment: number;
  transaction_hash: string;
  network: string;
  block_number: number | null;
  status: string;
  created_at: string;
}

export interface VerificationResult {
  assessment_reference: string;
  credit_score: number | null;
  verified: boolean;
  transaction_hash: string;
  block_number: number | null;
  ruleset_version: string;
}

type CollectionResponse<T> = T[] | { results: T[] } | Record<string, T[]>;

function collection<T>(response: CollectionResponse<T>, key?: string): T[] {
  if (Array.isArray(response)) return response;
  if (response && Array.isArray(response.results)) return response.results;
  const keyedResponse = response as Record<string, unknown>;
  if (key && Array.isArray(keyedResponse[key])) return keyedResponse[key] as T[];
  return [];
}

export interface DashboardData {
  lenders: Lender[];
  borrowers: Borrower[];
  consents: Consent[];
  assessments: Assessment[];
  integrations: IntegrationRequest[];
  auditLogs: AuditLog[];
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  dashboard(): Observable<DashboardData> {
    return this.http.get<DashboardData>('/api/dashboard/');
  }

  lenders(): Observable<Lender[]> {
    return this.http.get<CollectionResponse<Lender>>('/api/lenders/').pipe(map((response) => collection(response, 'lenders')));
  }
  borrowers(): Observable<Borrower[]> {
    return this.http.get<CollectionResponse<Borrower>>('/api/borrowers/').pipe(map((response) => collection(response, 'borrowers')));
  }
  consents(): Observable<Consent[]> {
    return this.http.get<CollectionResponse<Consent>>('/api/consents/').pipe(map((response) => collection(response, 'consents')));
  }
  assessments(): Observable<Assessment[]> {
    return this.http.get<CollectionResponse<Assessment>>('/api/assessments/').pipe(map((response) => collection(response, 'assessments')));
  }
  integrations(): Observable<IntegrationRequest[]> {
    return this.http.get<CollectionResponse<IntegrationRequest>>('/api/integrations/request-credit-data/').pipe(map((response) => collection(response, 'integrations')));
  }
  creditProfiles(): Observable<CreditProfile[]> {
    return this.http.get<CollectionResponse<CreditProfile>>('/api/credit-profiles/').pipe(
      timeout(10000),
      map((response) => collection(response, 'credit_profiles')),
    );
  }
  features(): Observable<CreditFeature[]> { return this.collectionRecords<CreditFeature>('/api/features/', 'features'); }
  aiReputation(): Observable<AIReputationResult[]> { return this.collectionRecords<AIReputationResult>('/api/ai-reputation/', 'results'); }
  smartContracts(): Observable<SmartContractResult[]> { return this.collectionRecords<SmartContractResult>('/api/smart-contract/', 'results'); }
  blockchain(): Observable<BlockchainTransaction[]> { return this.collectionRecords<BlockchainTransaction>('/api/blockchain/', 'transactions'); }
  auditLogs(): Observable<AuditLog[]> {
    return this.http.get<CollectionResponse<AuditLog>>('/api/audit-logs/').pipe(map((response) => collection(response, 'auditLogs')));
  }

  private collectionRecords<T>(url: string, key: string): Observable<T[]> {
    return this.http.get<CollectionResponse<T>>(url).pipe(
      timeout(10000),
      map((response) => collection(response, key)),
    );
  }

  verifyAssessment(reference: string): Observable<VerificationResult> {
    return this.http.get<VerificationResult>(`/api/assessments/${reference}/verify/`);
  }
}
