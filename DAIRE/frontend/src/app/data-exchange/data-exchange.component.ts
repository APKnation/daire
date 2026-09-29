import { ChangeDetectorRef, Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { forkJoin, map, switchMap, tap } from 'rxjs';
import { ApiRecord, ApiService, Borrower, PAGE_SIZE, PullResult } from '../core/api.service';
import { alertNear, toast } from '../core/notify';

interface ResultRow {
  label: string;
  value: string;
  mono?: boolean;
  highlight?: boolean;
}

type StepState = 'pending' | 'active' | 'done' | 'failed';
type StepKey = 'pull' | 'assessment' | 'analysis';

interface ExchangeStep {
  key: StepKey;
  label: string;
  hint: string;
  state: StepState;
}

@Component({
  standalone: true,
  imports: [FormsModule],
  templateUrl: './data-exchange.component.html',
})
export class DataExchangeComponent {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  constructor() {
    // The received-borrowers dropdown is populated immediately so the user can
    // see (and select from) every borrower whose data already arrived.
    this.refreshReceivedBorrowers();
  }

  borrowerReference = '';
  assessmentReference = '';
  borrower: Borrower | null = null;

  /** Borrowers that already have data in Central (received via push or pull),
   * newest-received first — the dropdown the pull step selects from. */
  receivedBorrowers: Borrower[] = [];
  receivedPage = 1;
  receivedCount = 0;
  /** Raw count before the reference filter, so the header can say how many exist. */
  receivedTotalCount = 0;
  receivedQuery = '';
  readonly receivedPageSize = PAGE_SIZE;
  pullResult: PullResult | null = null;
  lastResult: ApiRecord | null = null;
  /** Flattened, relevant-only rows for the result table. */
  resultRows: ResultRow[] = [];
  aiRows: ResultRow[] = [];
  blockchainRows: ResultRow[] = [];
  aiResult: ApiRecord | null = null;
  blockchainResult: ApiRecord | null = null;
  /** Which engine produced `lastResult` — drives the panel heading. */
  resultKind = '';
  loading = false;
  message = '';
  error = '';
  pullError = '';

  /** Progress stepper: pulled → assessment → both scoring engines. */
  readonly steps: ExchangeStep[] = [
    { key: 'pull', label: 'Pull from lenders', hint: 'Merge data from every lender', state: 'pending' },
    { key: 'assessment', label: 'Assessment', hint: 'Opens automatically after the pull', state: 'pending' },
    { key: 'analysis', label: 'Analyse borrower', hint: 'AI reputation + blockchain score', state: 'pending' },
  ];

  /** One page of borrowers that already have received data, newest first.
   * Optional reference filter narrows the list while keeping the pager. */
  loadReceivedBorrowers(next: number): void {
    if (next < 1 || (this.receivedCount > 0 && next > Math.ceil(this.receivedCount / this.receivedPageSize))) return;
    this.receivedPage = next;
    const query = this.receivedQuery.trim();
    const url = query
      ? `/api/borrowers/search/?borrower_reference=${encodeURIComponent(query)}`
      : '/api/borrowers/';
    this.api.paged<Borrower>(url, this.receivedPage).subscribe({
      next: (paged) => {
        this.receivedBorrowers = paged.items;
        this.receivedCount = paged.count;
        this.receivedTotalCount = paged.count;
        this.cdr.markForCheck();
      },
      error: () => this.cdr.markForCheck(),
    });
  }

  /** Load the borrower picker with one request, including its total count. */
  refreshReceivedBorrowers(): void {
    this.loadReceivedBorrowers(1);
  }

  selectReceivedBorrower(reference: string): void {
    this.borrowerReference = reference;
    this.cdr.markForCheck();
  }

  /** Label for a received borrower: name or reference, plus its data sources. */
  receivedBorrowerLabel(b: Borrower): string {
    return b.name ? `${b.name} — ${b.borrower_reference}` : b.borrower_reference;
  }

  /** Has Central actually received data for this borrower (account-level proof)? */
  borrowerHasReceivedData(b: Borrower | null | undefined): boolean {
    if (!b) return false;
    return (b.accounts?.length ?? 0) > 0 || (b.loans?.length ?? 0) > 0
      || (b.source_lenders?.length ?? 0) > 0
      || (b.financial_profile !== null && b.financial_profile !== undefined);
  }

  private setStep(key: StepKey, state: StepState): void {
    const step = this.steps.find((s) => s.key === key);
    if (step) step.state = state;
  }

  /** A fresh pull starts a new run: everything resets except the active step. */
  private resetSteps(activeKey: StepKey): void {
    for (const step of this.steps) {
      step.state = step.key === activeKey ? 'active' : 'pending';
    }
  }

  stepDotClass(step: ExchangeStep): string {
    const base = 'flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-bold';
    switch (step.state) {
      case 'done': return `${base} bg-[rgb(201,224,252,0.65)] text-[#356373]`;
      case 'failed': return `${base} bg-[#f9d4d2] text-[#b3262b]`;
      case 'active': return `${base} bg-[#024ad8] text-white`;
      default: return `${base} bg-[#e8e8e8] text-[#9a9a9a]`;
    }
  }

  stepLabelClass(step: ExchangeStep): string {
    switch (step.state) {
      case 'done': return 'text-[#356373]';
      case 'failed': return 'text-[#b3262b]';
      case 'active': return 'text-[#1a1a1a]';
      default: return 'text-[#9a9a9a]';
    }
  }

  /** Project the raw scoring result onto a small, human-friendly table.
   * Handles both shapes: AI reputation ({reputation, score, risk_level,
   * behavior_summary, model_version}) and blockchain score ({credit_score,
   * transaction_hash, ...}). The old version only knew the blockchain shape,
   * so AI results rendered as a table of "—". */
  private buildResultRows(result: ApiRecord): ResultRow[] {
    const row = (label: string, value: unknown, mono = false, highlight = false): ResultRow =>
      ({ label, value: value === null || value === undefined || value === '' ? '—' : String(value), mono, highlight });

    const isAi = result['reputation'] !== undefined || result['behavior_summary'] !== undefined
      || (result['model_version'] !== undefined && result['credit_score'] === undefined);
    if (isAi) {
      this.resultKind = 'Latest AI dual-model result (Scikit-Learn + NMB Scorecard)';
      const raw = (result['raw_result'] as Record<string, unknown> | undefined) ?? {};
      const skl = (raw['sklearn_metrics'] as Record<string, unknown> | undefined) ?? {};
      const nmb = (raw['nmb_metrics'] as Record<string, unknown> | undefined) ?? {};
      const consensus = (raw['consensus_metrics'] as Record<string, unknown> | undefined) ?? {};
      const basel = (raw['basel_metrics'] as Record<string, unknown> | undefined) ?? {};
      const pricing = (raw['pricing_capacity'] as Record<string, unknown> | undefined) ?? {};
      const decision = raw['decision'] ?? result['reputation'];
      const grade = raw['credit_grade'] ? `Grade ${raw['credit_grade']} · ${raw['credit_tier'] ?? ''}` : (result['risk_level'] ?? raw['risk_level']);

      return [
        row('Underwriting decision', decision ? `${decision} (${raw['decision_label'] ?? ''})`.trim() : result['reputation'], false, true),
        row('Credit rating & tier', grade, false, true),
        row('Blended default probability', consensus['blended_default_probability'] != null ? `${(Number(consensus['blended_default_probability']) * 100).toFixed(1)}%` : result['score'], false, true),
        row('NMB bureau score (300–850)', nmb['credit_score'] != null ? `${nmb['credit_score']} / 850` : '—', false, true),
        row('Dual models used', Array.isArray(raw['models_used']) ? (raw['models_used'] as string[]).join(' + ') : 'Scikit-Learn ML + NMB Scorecard', true),
        row('Model breakdown', skl['default_probability'] != null && nmb['default_probability'] != null
          ? `ML: ${(Number(skl['default_probability']) * 100).toFixed(1)}% PD  |  NMB: ${(Number(nmb['default_probability']) * 100).toFixed(1)}% PD`
          : '—', true),
        row('Model agreement', consensus['model_agreement_pct'] != null ? `${consensus['model_agreement_pct']}% (${consensus['concordance'] ?? ''})` : '—'),
        row('Basel II Expected Loss', basel['expected_loss'] != null ? `$${Number(basel['expected_loss']).toLocaleString()} (LGD: ${(Number(basel['loss_given_default'] ?? 0.5) * 100).toFixed(0)}%, EAD: $${Number(basel['exposure_at_default'] ?? 0).toLocaleString()})` : '—', false, true),
        row('Recommended credit limit', pricing['recommended_credit_limit'] != null ? `$${Number(pricing['recommended_credit_limit']).toLocaleString()}` : '—', false, true),
        row('Risk-based APR', pricing['recommended_apr'] != null ? `${pricing['recommended_apr']}% APR` : '—', false, true),
        row('Max monthly debt capacity', pricing['max_monthly_debt_service'] != null ? `$${Number(pricing['max_monthly_debt_service']).toLocaleString()}/mo` : '—'),
        row('Collateral policy', pricing['collateral_policy'] ?? '—'),
        row('Assessment record', result['assessment'] ?? '—', true),
      ];
    }

    this.resultKind = 'Latest blockchain result';
    const raw = (result['raw_result'] as Record<string, unknown> | undefined) ?? {};
    const data = (raw['data'] as Record<string, unknown> | undefined) ?? {};
    const dims = (data['dimensionsProcessed'] as Record<string, unknown> | undefined)
      ?? (result['score_inputs'] as Record<string, unknown> | undefined) ?? {};

    const rows: ResultRow[] = [
      row('Credit score (350–800)', result['credit_score'], false, true),
      row('Risk band', data['riskBand'] ?? raw['risk_band'] ?? result['risk_band'], false, true),
      row('Transaction hash', data['transactionHash'] ?? raw['transactionHash'] ?? result['transaction_hash'], true),
      row('Block number', data['blockNumber'] ?? raw['blockNumber'] ?? result['block_number']),
      row('Ruleset version', `v${result['ruleset_version'] ?? data['version'] ?? '—'}`),
      row('Contract address', data['contractAddress'] ?? result['contract_address'], true),
      row('Calculation', raw['calculation']),
      row('Dimensions sent', Object.entries(dims).map(([k, v]) => `${k}=${v}`).join('  ') || '—', true),
      row('Scored at', data['assessedAt'] ? new Date(Number(data['assessedAt']) * 1000).toLocaleString() : '—'),
      row('Chain latency', data['latencyMs'] != null ? `${data['latencyMs']} ms` : '—'),
    ];
    return rows;
  }

  pull(event: Event): void {
    const btn = event.target as HTMLElement;
    this.error = '';
    this.pullError = '';
    if (!this.borrowerReference.trim()) {
      void alertNear(btn, 'Borrower reference required', 'Please enter the unique borrower reference (e.g. 1001) before pulling data.', 'warning');
      return;
    }
    this.loading = true; this.message = ''; this.error = '';
    this.resetSteps('pull');
    this.cdr.markForCheck();
    this.api.pullFromAllLenders(this.borrowerReference.trim()).subscribe({
      next: (result) => {
        this.pullResult = result;
        this.borrower = result.borrower;
        this.setStep('pull', 'done');
        this.setStep('assessment', 'active');
        void toast(`Data pulled from ${result.successful_lenders} lender(s)`);
        // The pull response already contains the borrower. Update the picker
        // locally instead of issuing another list request.
        this.receivedBorrowers = [
          this.borrower,
          ...this.receivedBorrowers.filter((item) => item.borrower_reference !== this.borrower?.borrower_reference),
        ];
        this.receivedCount = Math.max(this.receivedCount, this.receivedBorrowers.length);
        this.receivedTotalCount = Math.max(this.receivedTotalCount, this.receivedCount);
        // The assessment step is automatic: open it on the freshly pulled borrower.
        this.openAssessmentAutomatically(btn);
      },
      error: (err) => {
        this.loading = false;
        this.setStep('pull', 'failed');
        this.pullError = err?.error?.detail || 'Lender pull failed. Check the lender API connection.';
        void alertNear(btn, 'Pull failed', this.pullError, 'error');
        this.cdr.markForCheck();
      },
    });
  }

  performAssessment(event: Event): void {
    const btn = event.target as HTMLElement;
    const reference = this.borrowerReference.trim();
    this.error = '';
    this.pullError = '';
    this.clearResults();
    if (!reference) {
      void alertNear(btn, 'Borrower reference required', 'Select a borrower reference first.', 'warning');
      return;
    }

    this.loading = true;
    this.message = '';
    this.pullResult = null;
    this.borrower = null;
    this.assessmentReference = '';
    this.resetSteps('pull');
    this.cdr.markForCheck();

    this.api.pullFromAllLenders(reference).pipe(
      tap((result) => {
        this.pullResult = result;
        this.borrower = result.borrower;
        this.setStep('pull', 'done');
        this.setStep('assessment', 'active');
        this.receivedBorrowers = [
          result.borrower,
          ...this.receivedBorrowers.filter((item) => item.borrower_reference !== result.borrower.borrower_reference),
        ];
        this.receivedCount = Math.max(this.receivedCount, this.receivedBorrowers.length);
        this.receivedTotalCount = Math.max(this.receivedTotalCount, this.receivedCount);
      }),
      switchMap(() => this.api.createAssessment(reference)),
      tap((assessment) => {
        this.assessmentReference = assessment.assessment_reference;
        this.setStep('assessment', 'done');
        this.setStep('analysis', 'active');
      }),
      // Run the engines in sequence: both refresh the same backend credit
      // profile, so parallel requests can race on SQLite/development DBs.
      switchMap((assessment) => this.api.pushAi(assessment.assessment_reference).pipe(
        switchMap((ai) => this.api.pushBlockchain(assessment.assessment_reference).pipe(
          map((blockchain) => ({ ai, blockchain })),
        )),
      )),
    ).subscribe({
      next: ({ ai, blockchain }) => {
        this.aiResult = ai;
        this.blockchainResult = blockchain;
        this.lastResult = blockchain;
        this.aiRows = this.buildResultRows(ai);
        this.blockchainRows = this.buildResultRows(blockchain);
        this.resultRows = [...this.aiRows, ...this.blockchainRows];
        this.setStep('analysis', 'done');
        this.loading = false;
        this.message = 'Assessment completed. Review the AI and blockchain results, then broadcast them.';
        void toast('Assessment completed');
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loading = false;
        this.error = err?.error?.detail || 'The assessment could not be completed.';
        if (this.pullResult) this.setStep('analysis', 'failed');
        else this.setStep('pull', 'failed');
        void alertNear(btn, 'Assessment failed', this.error, 'error');
        this.cdr.markForCheck();
      },
    });
  }

  /** Step 2 needs no button: every successful pull opens and selects
   * the assessment for the pulled borrower automatically. */
  private openAssessmentAutomatically(btn: HTMLElement): void {
    const ref = this.borrower?.borrower_reference || this.borrowerReference.trim();
    if (!ref) {
      this.loading = false;
      this.setStep('assessment', 'failed');
      this.cdr.markForCheck();
      return;
    }
    this.api.createAssessment(ref).subscribe({
      next: (assessment) => {
        this.assessmentReference = assessment.assessment_reference;
        this.loading = false;
        this.setStep('assessment', 'done');
        this.message = `Assessment ${assessment.assessment_reference} opened automatically — analyse the borrower when ready.`;
        void toast(`Assessment ${assessment.assessment_reference} selected automatically`);
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loading = false;
        this.setStep('assessment', 'failed');
        this.error = err?.error?.detail || 'Assessment could not be opened automatically. Pull the data again to retry.';
        void alertNear(btn, 'Auto-assessment failed', this.error, 'warning');
        this.cdr.markForCheck();
      },
    });
  }

  analyse(event: Event): void {
    const btn = event.target as HTMLElement;
    if (!this.assessmentReference.trim()) {
      this.clearResults();
      void alertNear(btn, 'Assessment not selected yet', 'Pull the borrower data first — the assessment opens automatically after the pull.', 'warning');
      return;
    }
    this.loading = true; this.message = ''; this.error = '';
    this.setStep('analysis', 'active');
    this.cdr.markForCheck();
    forkJoin({
      ai: this.api.pushAi(this.assessmentReference.trim()),
      blockchain: this.api.pushBlockchain(this.assessmentReference.trim()),
    }).subscribe({
      next: ({ ai, blockchain }) => {
        this.aiResult = ai;
        this.blockchainResult = blockchain;
        this.lastResult = blockchain;
        this.aiRows = this.buildResultRows(ai);
        this.blockchainRows = this.buildResultRows(blockchain);
        this.resultRows = [...this.aiRows, ...this.blockchainRows];
        this.setStep('analysis', 'done');
        this.loading = false;
        this.message = 'AI and blockchain analysis completed. Review the results, then broadcast them.';
        void toast('Borrower analysis completed');
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loading = false;
        this.clearResults();
        this.setStep('analysis', 'failed');
        this.error = err?.error?.detail || 'AI or blockchain did not return a result.';
        void alertNear(btn, 'Analysis failed', this.error, 'error');
        this.cdr.markForCheck();
      },
    });
  }

  private clearResults(): void {
    this.lastResult = null;
    this.aiResult = null;
    this.blockchainResult = null;
    this.aiRows = [];
    this.blockchainRows = [];
    this.resultRows = [];
    this.resultKind = '';
  }

  broadcast(event: Event): void {
    const btn = event.target as HTMLElement;
    if (!this.borrower?.id) {
      void alertNear(btn, 'Nothing to broadcast', 'Pull borrower data and get a result first, then broadcast it.', 'warning');
      return;
    }
    this.loading = true; this.message = ''; this.error = '';
    this.api.broadcastResult(this.borrower.id, 'CREDIT_RESULT', this.assessmentReference.trim()).subscribe({
      next: (result) => {
        const orgs = (result['broadcasts'] as unknown[] || []).length;
        this.loading = false;
        void toast(`${orgs} lender(s) received the result.`);
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.loading = false;
        void alertNear(btn, 'Broadcast failed', err?.error?.detail || 'Broadcast failed.', 'error');
        this.cdr.markForCheck();
      },
    });
  }
}
