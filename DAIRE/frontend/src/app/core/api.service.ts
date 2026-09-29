import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { map, Observable } from 'rxjs';

export interface Lender {
  id?: number;
  lender_id: string;
  institution_name: string;
  institution_type: string;
  api_status: string;
  api_base_url?: string;
  authentication_method?: string;
  api_key_prefix?: string;
  /** Present ONLY in the create/regenerate response — store immediately. */
  api_key?: string;
  api_key_notice?: string;
  created_at?: string;
  updated_at?: string;
}

export interface Borrower {
  borrower_reference: string;
  name?: string;
  id?: number;
  is_active?: boolean;
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
  borrower_name?: string;
  reputation: string;
  reputation_score: number | null;
  risk_level: string;
  credit_score: number | null;
  verification_status: string;
  blockchain_transaction_hash?: string;
  blockchain_block_number?: number | null;
  risk_band?: string;
  score_inputs?: Record<string, unknown>;
  score_explanation?: ScoreExplanation[];
  [key: string]: unknown;
}

export interface ScoreExplanation {
  dimension: string;
  name: string;
  value: string | number;
  reason: string;
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
  assessment_reference?: string;
  borrower_name?: string;
  borrower_reference?: string;
  reputation: string;
  score: string | number;
  risk_level: string;
  behavior_summary: string;
  model_version: string;
  created_at: string;
  // Pre-flattened scoring fields (returned directly by serializer)
  decision?: string;
  credit_grade?: string;
  credit_tier?: string;
  nmb_credit_score?: number;
  concordance?: string;
  ensemble_pd?: number;
  ml_pd?: number;
  nmb_pd?: number;
  recommended_credit_limit?: number;
  recommended_apr?: number;
  expected_loss?: number;
  actionable_guidance?: string[];
  strengths?: string[];
  risk_factors?: string[];
  ml_weight?: number;
  nmb_weight?: number;
  history_band?: string;
  score_explanation?: Array<{dimension: string; name: string; value: string; reason: string}>;
  /** Full ensemble result payload — still available for deep access */
  raw_result?: {
    decision?: string;
    credit_grade?: string;
    credit_tier?: string;
    default_probability?: number;
    sklearn_metrics?: { default_probability?: number; survival_probability?: number; risk_band?: string; [key: string]: unknown };
    nmb_metrics?: { credit_score?: number; default_probability?: number; risk_band?: string; top_strengths?: unknown[]; top_risk_factors?: unknown[]; [key: string]: unknown };
    consensus_metrics?: { concordance?: string; ensemble_pd?: number; ml_weight?: number; nmb_weight?: number; history_band?: string; model_spread?: number; agreement_pct?: number; [key: string]: unknown };
    basel_metrics?: { expected_loss?: number; lgd?: number; ead?: number; pd?: number; loss_given_default?: number; exposure_at_default?: number; [key: string]: unknown };
    pricing_capacity?: { recommended_credit_limit?: number; recommended_apr?: number; collateral_policy?: string; max_monthly_debt_service?: number; [key: string]: unknown };
    actionable_guidance?: string[];
    strengths?: string[];
    risk_factors?: string[];
    underwriting_summary?: string;
    decision_label?: string;
    [key: string]: unknown;
  };
}

export interface SmartContractResult {
  id: number;
  assessment: number;
  assessment_reference?: string;
  credit_score: number;
  ruleset_version: string;
  contract_address: string;
  transaction_hash?: string;
  block_number?: number | null;
  risk_band?: string;
  raw_result?: Record<string, unknown>;
  created_at: string;
}

/** One recorded data exchange — the audit trail of a pipeline stage. */
export interface DataExchangeRecord {
  id: number;
  system: 'LENDER' | 'AI' | 'BLOCKCHAIN' | string;
  direction: 'PUSH' | 'PULL' | string;
  operation: string;
  batch_reference?: string | null;
  borrower?: number | null;
  borrower_reference?: string | null;
  lender?: number | null;
  lender_id?: string | null;
  lender_name?: string | null;
  assessment?: number | null;
  assessment_reference?: string | null;
  status: 'STARTED' | 'COMPLETED' | 'FAILED' | string;
  fields_sent?: string[];
  payload?: Record<string, unknown>;
  response?: Record<string, unknown>;
  error_message?: string;
  created_at: string;
  updated_at?: string;
}

export interface BlockchainTransaction {
  id: number;
  assessment: number;
  assessment_reference?: string;
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
  lender_fields: string[];
  ai_fields: string[];
  blockchain_fields: string[];
  active: boolean;
  version: string;
}

type CollectionResponse<T> = T[] | { results: T[] } | Record<string, T[]>;

/** Must match PAGE_SIZE in backend/config/settings.py. */
export const PAGE_SIZE = 10;

export interface Paged<T> {
  items: T[];
  count: number;
}

function collection<T>(response: CollectionResponse<T>, key?: string): T[] {
  if (Array.isArray(response)) return response;
  if (response && Array.isArray(response.results)) return response.results;
  const keyedResponse = response as Record<string, unknown>;
  if (key && Array.isArray(keyedResponse[key])) return keyedResponse[key] as T[];
  return [];
}

/** Database-wide counts used by the Overview KPI cards (uncapped, full history). */
export interface DashboardTotals {
  lenders: number;
  connected_lenders: number;
  borrowers: number;
  active_borrowers: number;
  assessments: number;
  scored_assessments: number;
  verified_assessments: number;
  average_credit_score: number | null;
}

export interface DashboardData {
  /** True DB totals for the KPI cards — absent on older API payloads. */
  totals?: DashboardTotals;
  lenders: Lender[];
  borrowers: Borrower[];
  consents: Consent[];
  assessments: Assessment[];
  integrations: IntegrationRequest[];
  /** Per-stage pipeline records for the Overview inner tabs. */
  lender_exchanges?: DataExchangeRecord[];
  ai_exchanges?: DataExchangeRecord[];
  blockchain_exchanges?: DataExchangeRecord[];
  ai_results?: AIReputationResult[];
  smart_contract_results?: SmartContractResult[];
  blockchain_transactions?: BlockchainTransaction[];
}

export interface PullResult {
  borrower: Borrower;
  pulled_from: string[];
  failed: Array<{ lender: string; detail: string }>;
  pull_reference: string;
  status: 'COMPLETED' | 'PARTIAL_SUCCESS' | 'FAILED';
  total_lenders: number;
  successful_lenders: number;
  failed_lenders: number;
  results: Array<{ lender: string; status: string; exchange_id: number; detail?: string }>;
}

@Injectable({ providedIn: 'root' })
export class ApiService {
  private readonly http = inject(HttpClient);

  dashboard(): Observable<DashboardData> {
    return this.http.get<DashboardData>('/api/dashboard/');
  }

  lenders(): Observable<Lender[]> {
    return this.http.get<CollectionResponse<Lender>>('/api/lenders/').pipe(
      map((response) => collection(response, 'lenders')),
    );
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
  pullFromAllLenders(borrowerReference: string): Observable<PullResult> {
    return this.http.post<PullResult>(`/api/borrowers/pull-from-all-lenders/`, { borrower_reference: borrowerReference });
  }
  pushAi(reference: string): Observable<ApiRecord> {
    return this.http.post<ApiRecord>(`/api/assessments/${reference}/ai-reputation/`, {});
  }
  pushBlockchain(reference: string): Observable<ApiRecord> {
    return this.http.post<ApiRecord>(`/api/assessments/${reference}/blockchain-score/`, {});
  }
  broadcastResult(borrowerId: number, resultType: string, assessmentReference?: string, payload?: ApiRecord): Observable<ApiRecord> {
    // Without a payload the backend assembles the combined AI + blockchain results.
    return this.http.post<ApiRecord>(`/api/borrowers/${borrowerId}/broadcast-result/`,
      payload
        ? { result_type: resultType, assessment_reference: assessmentReference, payload }
        : { result_type: resultType, assessment_reference: assessmentReference });
  }
  borrowers(): Observable<Borrower[]> {
    return this.http.get<CollectionResponse<Borrower>>('/api/borrowers/').pipe(map((response) => collection(response, 'borrowers')));
  }
  createBorrower(data: Partial<Borrower>): Observable<Borrower> { return this.http.post<Borrower>('/api/borrowers/', data); }
  updateBorrower(id: number, data: Partial<Borrower>): Observable<Borrower> { return this.http.patch<Borrower>(`/api/borrowers/${id}/`, data); }
  deleteBorrower(id: number): Observable<void> { return this.http.delete<void>(`/api/borrowers/${id}/`); }
  createLender(data: Partial<Lender>): Observable<Lender> { return this.http.post<Lender>('/api/lenders/', data); }
  regenerateLenderKey(id: number): Observable<Lender> { return this.http.post<Lender>(`/api/lenders/${id}/regenerate-key/`, {}); }
  updateLender(id: number, data: Partial<Lender>): Observable<Lender> { return this.http.patch<Lender>(`/api/lenders/${id}/`, data); }
  deleteLender(id: number): Observable<void> { return this.http.delete<void>(`/api/lenders/${id}/`); }
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
  createAssessment(borrowerReference: string): Observable<Assessment> {
    return this.http.post<Assessment>('/api/assessments/', { borrower_reference: borrowerReference });
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
  blockchain(): Observable<BlockchainTransaction[]> { return this.collectionRecords<BlockchainTransaction>('/api/blockchain/', 'transactions'); }

  private collectionRecords<T>(url: string, key: string): Observable<T[]> {
    return this.http.get<CollectionResponse<T>>(url).pipe(
      map((response) => collection(response, key)),
    );
  }

  /** One page of a paginated ViewSet list (PAGE_SIZE rows). */
  paged<T>(url: string, page = 1): Observable<Paged<T>> {
    const sep = url.includes('?') ? '&' : '?';
    return this.http.get<T[] | { results?: T[]; count?: number }>(`${url}${sep}page=${page}`).pipe(
      map((response) => Array.isArray(response)
        ? { items: response, count: response.length }
        : { items: response.results ?? [], count: response.count ?? (response.results ?? []).length }),
    );
  }

  verifyAssessment(reference: string): Observable<VerificationResult> {
    return this.http.get<VerificationResult>(`/api/assessments/${reference}/verify/`);
  }

  predictCreditRisk(data: any): Observable<any> {
    return this.http.post<any>('/api/predict_credit_risk/', data);
  }
}
