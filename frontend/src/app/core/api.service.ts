import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { catchError, map, Observable, of } from 'rxjs';

export interface Lender {
  id?: number;
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
  customer_id?: string;
  age?: number | null;
  gender?: string;
  employment_status?: string;
  income?: string | number | null;
  business_information?: Record<string, unknown>;
  account_information?: Record<string, unknown>;
  source_lenders?: string[];
  financial_profile?: FinancialProfile | null;
  accounts?: BorrowerAccount[];
  loans?: BorrowerLoan[];
  created_at?: string;
  updated_at?: string;
}

export interface FinancialProfile {
  active_loans: number;
  total_outstanding_debt: string | number;
  monthly_repayment: string | number;
  previous_loans: number;
  debt_to_income_ratio: string | number;
  transaction_frequency: number;
  income_frequency: number;
  savings: string | number;
  cash_flow_patterns: Record<string, unknown>;
  account_activity: Record<string, unknown>;
}

export interface BorrowerAccount {
  id: number;
  lender: number;
  lender_name: string;
  account_reference: string;
  account_name: string;
  customer_id: string;
  metadata: Record<string, unknown>;
}

export interface BorrowerLoan {
  id: number;
  loan_id: string;
  lender: number;
  lender_name: string;
  loan_amount: string | number;
  loan_date: string | null;
  loan_duration_months: number;
  interest_rate: string | number;
  outstanding_balance: string | number;
  status: string;
  repayments: Repayment[];
}

export interface Repayment {
  id: number;
  repayment_amount: string | number;
  repayment_date: string | null;
  due_date: string | null;
  days_overdue: number;
  missed_payments: number;
  late_payments: number;
  default_status: string;
}

export interface Consent {
  consent_id: string;
  status: string;
  expires_at: string;
  borrower_id?: number;
  lender_id?: number;
  borrower?: number;
  lender?: number;
  borrower_reference?: string;
  lender_name?: string;
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

export interface ApiRecord { [key: string]: unknown; }

export interface CreditProfile {
  id: number;
  borrower: number;
  borrower_reference?: string;
  integration_request: number | null;
  source_version: string;
  created_at: string;
  updated_at: string;
  profile_data?: {
    active_loan_count?: number;
    completed_loan_count?: number;
    defaulted_loan_count?: number;
    total_outstanding_debt?: number;
    on_time_payment_ratio?: number;
    missed_payment_count?: number;
    late_payment_count?: number;
    max_days_overdue?: number;
    transaction_frequency?: number;
    income_frequency?: number;
    balance_stability?: number;
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

export interface RoutingPolicy {
  id?: number;
  policy_id: string;
  name: string;
  ai_fields: string[];
  blockchain_fields: string[];
  active: boolean;
  version: string;
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
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  dashboard(): Observable<DashboardData> {
    const empty: DashboardData = { lenders: [], borrowers: [], consents: [], assessments: [], integrations: [] };
    return this.http.get<DashboardData>('/api/dashboard/').pipe(
      catchError((err) => { console.error('Dashboard API error', err); return of(empty); })
    );
  }

  lenders(): Observable<Lender[]> {
    return this.http.get<CollectionResponse<Lender>>('/api/lenders/').pipe(map((response) => collection(response, 'lenders')));
  }
  routingPolicies(): Observable<RoutingPolicy[]> {
    return this.http.get<CollectionResponse<RoutingPolicy>>('/api/routing-policies/').pipe(map((response) => collection(response, 'routing_policies')));
  }
  updateRoutingPolicy(policy: RoutingPolicy): Observable<RoutingPolicy> {
    return this.http.put<RoutingPolicy>(`/api/routing-policies/${policy.id}/`, policy);
  }
  pullLenderData(lenderId: number, borrowerReference: string): Observable<Borrower> {
    return this.http.post<Borrower>(`/api/lenders/${lenderId}/pull-borrower-data/`, { borrower_reference: borrowerReference });
  }
  pushAi(reference: string): Observable<ApiRecord> {
    return this.http.post<ApiRecord>(`/api/assessments/${reference}/ai-reputation/`, {});
  }
  pushBlockchain(reference: string): Observable<ApiRecord> {
    return this.http.post<ApiRecord>(`/api/assessments/${reference}/blockchain-score/`, {});
  }
  broadcastResult(borrowerId: number, resultType: string, payload: ApiRecord): Observable<ApiRecord> {
    return this.http.post<ApiRecord>(`/api/borrowers/${borrowerId}/broadcast-result/`, { result_type: resultType, payload });
  }
  borrowers(): Observable<Borrower[]> {
    return this.http.get<CollectionResponse<Borrower>>('/api/borrowers/').pipe(map((response) => collection(response, 'borrowers')));
  }
  borrowerSearch(lenderName = '', accountReference = '', borrowerReference = ''): Observable<Borrower[]> {
    const params = new URLSearchParams();
    if (lenderName) params.set('lender_name', lenderName);
    if (accountReference) params.set('account_reference', accountReference);
    if (borrowerReference) params.set('borrower_reference', borrowerReference);
    const query = params.toString();
    return this.http.get<CollectionResponse<Borrower>>(`/api/borrowers/search/${query ? `?${query}` : ''}`).pipe(
      map((response) => collection(response, 'borrowers')),
    );
  }
  ingestBorrower(data: { lender_id: string; borrower_reference: string; account_reference?: string; payload: Record<string, unknown> }): Observable<Borrower> {
    return this.http.post<Borrower>('/api/borrowers/ingest/', data);
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
      map((response) => collection(response, 'credit_profiles')),
    );
  }
  features(): Observable<CreditFeature[]> { return this.collectionRecords<CreditFeature>('/api/features/', 'features'); }
  aiReputation(): Observable<AIReputationResult[]> { return this.collectionRecords<AIReputationResult>('/api/ai-reputation/', 'results'); }
  smartContracts(): Observable<SmartContractResult[]> { return this.collectionRecords<SmartContractResult>('/api/smart-contract/', 'results'); }
  blockchain(): Observable<BlockchainTransaction[]> { return this.collectionRecords<BlockchainTransaction>('/api/blockchain/', 'transactions'); }

  private collectionRecords<T>(url: string, key: string): Observable<T[]> {
    return this.http.get<CollectionResponse<T>>(url).pipe(
      map((response) => collection(response, key)),
    );
  }

  verifyAssessment(reference: string): Observable<VerificationResult> {
    return this.http.get<VerificationResult>(`/api/assessments/${reference}/verify/`);
  }
}
