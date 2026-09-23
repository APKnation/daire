import { DatePipe } from '@angular/common';
import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import {
  ApiService, ApiRecord, Assessment, BlockchainTransaction, DashboardData, DashboardTotals, DataExchangeRecord,
  Lender, PAGE_SIZE, SmartContractResult,
} from '../core/api.service';
import { PagerComponent } from '../core/pager.component';

interface RecentAssessment {
  reference: string;
  borrower: string;
  score: number | null;
  reputation: string;
  risk: string;
  verified: boolean;
  when: string;
}

/** Tabs of the inner navbar inside the Overview page. */
type OverviewStage =
  | 'snapshot'
  | 'lender-data'
  | 'assessed'
  | 'to-ai'
  | 'ai-results'
  | 'to-blockchain'
  | 'blockchain-results';

interface StageTab {
  key: OverviewStage;
  label: string;
}

/** Stage 1 — one row per data exchange received from a lender. */
interface LenderExchangeRow {
  record: DataExchangeRecord;
  when: string;
  direction: string;
  operation: string;
  lender: string;
  borrower: string;
  status: string;
  statusClass: string;
  fields: string;
  detail: string;
}

/** Stage 2 — assessment snapshot taken before the engines run. */
interface AssessedRow {
  record: Assessment;
  when: string;
  reference: string;
  borrower: string;
  reputation: string;
  risk: string;
  inputs: string;
}

/** Stage 3/5 — one row per payload pushed to the AI or blockchain engine. */
interface EngineSentRow {
  record: DataExchangeRecord;
  when: string;
  reference: string;
  borrower: string;
  operation: string;
  direction: string;
  status: string;
  statusClass: string;
  payload: string;
  error: string;
}

/** Stage 4 — one row per result returned by the AI engine. */
interface AiResultRow {
  record: ApiRecord;
  when: string;
  reference: string;
  reputation: string;
  reputationClass: string;
  score: string;
  risk: string;
  model: string;
  summary: string;
}

/** Stage 6 — one row per score sealed by the smart contract. */
interface BlockchainResultRow {
  record: SmartContractResult;
  when: string;
  reference: string;
  score: number | null;
  band: string;
  ruleset: string;
  contract: string;
  txHash: string;
  block: number | null;
}

/** Stage 6 — one row per blockchain transaction record. */
interface BlockchainTxRow {
  record: BlockchainTransaction;
  when: string;
  reference: string;
  txHash: string;
  network: string;
  block: number | null;
  status: string;
  statusClass: string;
}

/** Assessment with an optional created_at (present on API payloads, absent in the index-signature type). */
type AssessmentWithTimestamp = Assessment & { created_at?: string };

interface SparkDot {
  x: number;
  y: number;
}

interface SparkBar {
  x: number;
  y: number;
  w: number;
  h: number;
}

interface KpiCard {
  label: string;
  value: string;
  trend: string;
  trendUp: boolean;
  /** Flat fill sampled from the reference design (dashboard.jpeg). */
  bg: string;
  chip: string;
  /** Sparkline style, matching the reference: dotted line, smooth wave, or bars. */
  sparkType: 'dots' | 'wave' | 'bars';
  sparkPoints: string;
  sparkDots: SparkDot[];
  sparkWave: string;
  sparkBars: SparkBar[];
}

interface ScoreBand {
  label: string;
  min: number;
  max: number;
  color: string;
}

/** Slice of the pipeline-stage donut chart. */
interface DonutSegment {
  label: string;
  count: number;
  color: string;
  /** 0–1 share of the whole circle. */
  pct: number;
  /** Pre-computed SVG arc path in a 100×100 viewBox. */
  arc: string;
}

/** One per-lender bar: how much data each institution has contributed. */
interface LenderBar {
  label: string;
  full: string;
  count: number;
  /** 0–1 width relative to the busiest lender. */
  width: number;
}

@Component({
  standalone: true,
  imports: [DatePipe, RouterLink, FormsModule, PagerComponent],
  templateUrl: './dashboard.component.html',
})
export class DashboardComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  data: DashboardData | null = null;
  error = '';

  /** Active tab of the inner navbar inside the Overview page. */
  stage: OverviewStage = 'snapshot';
  readonly stageTabs: StageTab[] = [
    { key: 'snapshot', label: 'Snapshot' },
    { key: 'lender-data', label: 'Data received from lenders' },
    { key: 'assessed', label: 'Data assessed (pre-engine)' },
    { key: 'to-ai', label: 'Sent to AI' },
    { key: 'ai-results', label: 'Received from AI' },
    { key: 'to-blockchain', label: 'Sent to blockchain' },
    { key: 'blockchain-results', label: 'Received from blockchain' },
  ];

  // =======================================================================
  // Stage-table search + pagination state. One query/page pair per table,
  // so each tab keeps its own filter while the user hops between tabs.
  // =======================================================================

  /** Rows per page for every stage table (matches PAGE_SIZE used app-wide). */
  readonly stagePageSize = PAGE_SIZE;
  lenderQuery = '';
  assessedQuery = '';
  aiSentQuery = '';
  aiResultQuery = '';
  blockchainSentQuery = '';
  blockchainResultQuery = '';
  txQuery = '';
  lenderPage = 1;
  assessedPage = 1;
  aiSentPage = 1;
  aiResultPage = 1;
  blockchainSentPage = 1;
  blockchainResultPage = 1;
  txPage = 1;

  ngOnInit(): void {
    this.load();
  }

  /** Reload dashboard data — wired to the header refresh button. */
  load(): void {
    this.api.dashboard().subscribe({
      next: (data) => {
        this.data = data;
        // Fresh data can shrink a table below the current page — start over.
        this.resetStagePages();
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Dashboard error:', err);
        this.error = 'Dashboard data could not be loaded. Confirm the Django API is running.';
        this.cdr.markForCheck();
      },
    });
  }

  /** True database totals (full history) with a computed fallback for older payloads. */
  private get totals(): Partial<DashboardTotals> | undefined {
    return this.data?.totals;
  }

  /** Available lenders = the same set the pull pipeline targets (CONNECTED + DEGRADED). */
  get connectedLenders(): number {
    return this.totals?.connected_lenders
      ?? this.data?.lenders.filter((l) => l.api_status !== 'DISCONNECTED').length
      ?? 0;
  }

  get scoredAssessments(): number {
    return this.totals?.scored_assessments ?? this.data?.assessments.filter((a) => a.credit_score != null).length ?? 0;
  }

  get verifiedAssessments(): number {
    return this.totals?.verified_assessments ?? this.data?.assessments.filter((a) => a.verification_status === 'CONFIRMED').length ?? 0;
  }

  /** Share of assessments that reached scoring, for the chart footer. */
  get scoredPct(): number {
    const total = this.totals?.assessments ?? this.data?.assessments.length ?? 0;
    return total ? Math.round((this.scoredAssessments / total) * 100) : 0;
  }

  get activeBorrowers(): number {
    return this.totals?.active_borrowers ?? this.data?.borrowers.filter((b) => b.is_active !== false).length ?? 0;
  }

  /** The one number lenders care about: mean of every on-chain credit score. */
  get averageCreditScore(): number | null {
    if (this.totals?.average_credit_score != null) return this.totals.average_credit_score;
    const scores = this.scoredList();
    if (!scores.length) return null;
    return Math.round(scores.reduce((sum, s) => sum + s, 0) / scores.length);
  }

  private scoredList(): number[] {
    return (this.data?.assessments ?? [])
      .map((a) => a.credit_score)
      .filter((s): s is number => s != null);
  }

  /** Signed change of the average score: newest half vs oldest half of the history. */
  private scoreTrend(): { text: string; up: boolean } {
    const scores = (this.data?.assessments ?? [])
      .filter((a) => a.credit_score != null)
      .sort((x, y) => ((x as AssessmentWithTimestamp).created_at ?? '').localeCompare((y as AssessmentWithTimestamp).created_at ?? ''))
      .map((a) => a.credit_score as number);
    if (scores.length < 4) return { text: 'NEW', up: true };
    const half = Math.floor(scores.length / 2);
    const oldAvg = scores.slice(0, half).reduce((s, v) => s + v, 0) / half;
    const newAvg = scores.slice(half).reduce((s, v) => s + v, 0) / (scores.length - half);
    const delta = Math.round(newAvg - oldAvg);
    return { text: `${delta >= 0 ? '+' : ''}${delta} pts`, up: delta >= 0 };
  }

  /** Weekly per-lender pull counts, 0..1 normalized — feeds the KPI sparkline. */
  private lenderSpark(): number[] {
    const counts = this.data?.lenders.map((l) => (l.api_status === 'CONNECTED' ? 2 : 1)) ?? [];
    return counts.length ? counts.slice(0, 12) : [1, 1, 1];
  }

  private borrowersSpark(): number[] {
    const stamps = (this.data?.borrowers ?? [])
      .map((b) => b.created_at ?? '')
      .filter(Boolean)
      .sort();
    return this.buckets(stamps, 12);
  }

  private assessmentsSpark(): number[] {
    const stamps = (this.data?.assessments ?? [])
      .filter((a) => a.credit_score != null)
      .map((a) => (a as AssessmentWithTimestamp).created_at ?? '')
      .filter(Boolean)
      .sort();
    return this.buckets(stamps, 12);
  }

  private scoresSpark(): number[] {
    const scores = (this.data?.assessments ?? [])
      .filter((a) => a.credit_score != null)
      .sort((x, y) => ((x as AssessmentWithTimestamp).created_at ?? '').localeCompare((y as AssessmentWithTimestamp).created_at ?? ''))
      .map((a) => a.credit_score as number);
    if (!scores.length) return [1, 1, 1];
    return scores.slice(-12).map((s) => (s - 350) / 450);
  }

  /** Map 0..1 series to "x,y" pairs in a 100×24 viewBox for the sparkline polyline. */
  private toSparkPoints(series: number[]): string {
    const pts = this.sparkXY(series);
    return pts.map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
  }

  /** Series as dot coordinates — the dotted sparkline style from the reference. */
  private toSparkDots(series: number[]): SparkDot[] {
    return this.sparkXY(series);
  }

  /** Smooth cubic path through the series — the wave sparkline style. */
  private toSparkWave(series: number[]): string {
    const pts = this.sparkXY(series);
    if (pts.length < 2) return '';
    let d = `M${pts[0].x.toFixed(2)},${pts[0].y.toFixed(2)}`;
    for (let i = 1; i < pts.length; i++) {
      const x0 = pts[i - 1].x;
      const y0 = pts[i - 1].y;
      const x1 = pts[i].x;
      const y1 = pts[i].y;
      const mx = (x0 + x1) / 2;
      d += ` C${mx.toFixed(2)},${y0.toFixed(2)} ${mx.toFixed(2)},${y1.toFixed(2)} ${x1.toFixed(2)},${y1.toFixed(2)}`;
    }
    return d;
  }

  /** Series as rounded bars — the histogram sparkline style from the reference. */
  private toSparkBars(series: number[]): SparkBar[] {
    const n = Math.max(series.length, 1);
    const w = 100 / n;
    return series.map((v, i) => {
      const h = Math.max(2, Math.min(Math.max(v, 0), 1) * 20);
      return { x: i * w + w * 0.22, y: 22 - h, w: w * 0.56, h };
    });
  }

  /** Shared mapping: series values to points in the 100×24 sparkline viewBox. */
  private sparkXY(series: number[]): SparkDot[] {
    const n = series.length;
    if (n < 2) return [{ x: 0, y: 22 }, { x: 100, y: 22 }];
    return series.map((v, i) => ({
      x: (i * 100) / (n - 1),
      y: 22 - Math.min(Math.max(v, 0), 1) * 18,
    }));
  }

  /** Count timestamps into n equal time buckets, oldest → newest. */
  private buckets(stamps: string[], n: number): number[] {
    if (!stamps.length) return Array(n).fill(0.15);
    const times = stamps.map((s) => new Date(s).getTime()).filter((t) => !Number.isNaN(t));
    if (!times.length) return Array(n).fill(0.15);
    const min = Math.min(...times);
    const max = Math.max(...times);
    const span = Math.max(max - min, 1);
    const out = Array(n).fill(0);
    for (const t of times) {
      out[Math.min(n - 1, Math.floor(((t - min) / span) * n))]++;
    }
    const peak = Math.max(...out, 1);
    return out.map((v) => 0.15 + (v / peak) * 0.85);
  }

  /** The four hero KPI cards, styled after the colored reference design. */
  get kpiCards(): KpiCard[] {
    const trend = this.scoreTrend();
    const total = this.totals?.assessments ?? this.data?.assessments.length ?? 0;
    const card = (
      label: string,
      value: string,
      trend: string,
      trendUp: boolean,
      bg: string,
      chip: string,
      sparkType: KpiCard['sparkType'],
      series: number[],
    ): KpiCard => ({
      label,
      value,
      trend,
      trendUp,
      bg,
      chip,
      sparkType,
      sparkPoints: this.toSparkPoints(series),
      sparkDots: this.toSparkDots(series),
      sparkWave: this.toSparkWave(series),
      sparkBars: this.toSparkBars(series),
    });
    return [
      card('Lender network', `${this.connectedLenders}/${this.totals?.lenders ?? this.data?.lenders.length ?? 0}`, `${this.connectedLenders} available`,
        this.connectedLenders > 0, '#024ad8', 'bg-white/25', 'dots', this.lenderSpark()),
      card('Borrowers', String(this.activeBorrowers), 'unified across institutions', true,
        '#296ef9', 'bg-white/25', 'wave', this.borrowersSpark()),
      card('Avg credit score', this.averageCreditScore != null ? String(this.averageCreditScore) : '—', trend.text, trend.up,
        '#356373', 'bg-white/25', 'bars', this.scoresSpark()),
      card('Assessments', `${this.scoredAssessments}/${total}`, `${this.verifiedAssessments} on-chain`, this.verifiedAssessments > 0,
        '#024ad8', 'bg-white/25', 'bars', this.assessmentsSpark()),
    ];
  }

  // =======================================================================
  // Inner-navbar stage tables — one table per pipeline stage.
  // =======================================================================

  selectStage(stage: OverviewStage): void {
    this.stage = stage;
    this.cdr.markForCheck();
  }

  // =======================================================================
  // Search + pagination helpers shared by every stage table.
  // =======================================================================

  /** Case-insensitive needle match against every row value (and its JSON). */
  private matchesQuery(row: object, query: string): boolean {
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return Object.values(row).some((value) =>
      String(value ?? '').toLowerCase().includes(needle),
    );
  }

  /** Search + page a row list. Pages stay valid because every search and
   * every data reload resets all tables back to page 1 (see below). */
  stageView<T extends object>(rows: T[], query: string, page: number): T[] {
    const filtered = query.trim() ? rows.filter((row) => this.matchesQuery(row, query)) : rows;
    return filtered.slice((page - 1) * this.stagePageSize, page * this.stagePageSize);
  }

  /** Filtered row count for a stage table — the number the pager paginates. */
  stageCount<T extends object>(rows: T[], query: string): number {
    return query.trim() ? rows.filter((row) => this.matchesQuery(row, query)).length : rows.length;
  }

  /** True when a search is active but matches nothing — drives the empty state. */
  stageNoMatch<T extends object>(rows: T[], query: string): boolean {
    return Boolean(query.trim()) && this.stageCount(rows, query) === 0;
  }

  onStageSearch(): void {
    // Every keystroke starts all tables back at page 1; the pager buttons
    // keep navigation within range afterwards.
    this.resetStagePages();
    this.cdr.markForCheck();
  }

  private resetStagePages(): void {
    this.lenderPage = 1;
    this.assessedPage = 1;
    this.aiSentPage = 1;
    this.aiResultPage = 1;
    this.blockchainSentPage = 1;
    this.blockchainResultPage = 1;
    this.txPage = 1;
  }

  // =======================================================================
  // Record actions — view-only detail modal on every stage-table row.
  // Pipeline records are audit data: they are inspected, never edited or
  // deleted from the console.
  // =======================================================================

  /** The record currently shown in the read-only detail modal. */
  recordModal: {
    kind: OverviewStage;
    id: number;
    title: string;
    fields: Array<{ key: string; label: string; value: string; multiline: boolean }>;
  } | null = null;

  private static fieldLabel(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  }

  /** Open the read-only detail modal for a stage-table row. */
  viewRecord(kind: OverviewStage, title: string, record: object): void {
    const entries = Object.entries(record).filter(([key]) => !key.endsWith('_id') || key === 'id');
    this.recordModal = {
      kind,
      id: typeof (record as ApiRecord)['id'] === 'number' ? (record as ApiRecord)['id'] as number : 0,
      title,
      fields: entries.map(([key, value]) => ({
        key,
        label: DashboardComponent.fieldLabel(key),
        value: this.displayValue(value),
        multiline: typeof value === 'object' && value !== null,
      })),
    };
    this.cdr.markForCheck();
  }

  closeRecordModal(): void {
    this.recordModal = null;
    this.cdr.markForCheck();
  }

  /** Human-friendly rendering of any record value. */
  private displayValue(value: unknown): string {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'object') return JSON.stringify(value, null, 2);
    return String(value);
  }

  /** Newest-first rows for the "Data received from lenders" table. */
  get lenderExchangeRows(): LenderExchangeRow[] {
    return (this.data?.lender_exchanges ?? [])
      .map((exchange) => {
        const response = exchange.response ?? {};
        const loans = response['loans_received'];
        const txs = response['transaction_count'];
        const detailBits = [
          typeof loans === 'number' ? `${loans} loan(s)` : '',
          typeof txs === 'number' ? `${txs} transaction(s)` : '',
        ].filter(Boolean);
        return {
          record: exchange,
          when: exchange.created_at,
          direction: exchange.direction,
          operation: exchange.operation,
          lender: exchange.lender_name || exchange.lender_id || '—',
          borrower: exchange.borrower_reference || '—',
          status: exchange.status,
          statusClass: this.exchangeStatusClass(exchange.status),
          fields: (exchange.fields_sent ?? []).join(', ') || '—',
          detail: detailBits.join(' · ') || exchange.error_message || '—',
        };
      });
  }

  /** Stage 2 — assessment snapshots, newest first. */
  get assessedRowsNewestFirst(): AssessedRow[] {
    return (this.data?.assessments ?? [])
      .map((a) => ({
        record: a,
        when: (a as AssessmentWithTimestamp).created_at ?? '',
        reference: a.assessment_reference,
        borrower: a.borrower_name || a.borrower_reference,
        reputation: a.reputation || 'PENDING',
        risk: a.risk_level || '—',
        inputs: this.summarizePayload(a.score_inputs ?? {}),
      }))
      .sort((x, y) => y.when.localeCompare(x.when));
  }

  /** Stage 3 — payloads sent to the AI engine. */
  get aiSentRows(): EngineSentRow[] {
    return this.toEngineSentRows(this.data?.ai_exchanges ?? []);
  }

  /** Stage 5 — payloads sent to the blockchain engine. */
  get blockchainSentRows(): EngineSentRow[] {
    return this.toEngineSentRows(this.data?.blockchain_exchanges ?? []);
  }

  /** Shared mapper: engine exchanges (AI or blockchain) to sent-payload rows. */
  private toEngineSentRows(exchanges: DataExchangeRecord[]): EngineSentRow[] {
    return exchanges.map((exchange) => ({
      record: exchange,
      when: exchange.created_at,
      reference: exchange.assessment_reference || '—',
      borrower: exchange.borrower_reference || '—',
      operation: exchange.operation,
      direction: exchange.direction,
      status: exchange.status,
      statusClass: this.exchangeStatusClass(exchange.status),
      payload: this.summarizePayload(exchange.payload),
      error: exchange.error_message || '—',
    }));
  }

  /** Stage 4 — results returned by the AI engine. */
  get aiResultRows(): AiResultRow[] {
    return (this.data?.ai_results ?? [])
      .map((result) => ({
        record: result as unknown as ApiRecord,
        when: result.created_at,
        reference: result.assessment_reference || `#${result.assessment}`,
        reputation: result.reputation || '—',
        reputationClass: this.reputationClass(result.reputation || ''),
        score: result.score != null ? String(result.score) : '—',
        risk: result.risk_level || '—',
        model: result.model_version || '—',
        summary: result.behavior_summary || '—',
      }));
  }

  /** Stage 6 — scores sealed by the smart contract. */
  get blockchainResultRows(): BlockchainResultRow[] {
    return (this.data?.smart_contract_results ?? [])
      .map((result) => ({
        record: result,
        when: result.created_at,
        reference: result.assessment_reference || `#${result.assessment}`,
        score: result.credit_score,
        band: result.risk_band || '—',
        ruleset: result.ruleset_version ? `v${result.ruleset_version}` : '—',
        contract: result.contract_address || '—',
        txHash: result.transaction_hash || '—',
        block: result.block_number ?? null,
      }));
  }

  /** Stage 6 — blockchain transaction records. */
  get blockchainTxRows(): BlockchainTxRow[] {
    return (this.data?.blockchain_transactions ?? [])
      .map((tx) => ({
        record: tx,
        when: tx.created_at,
        reference: tx.assessment_reference || `#${tx.assessment}`,
        txHash: tx.transaction_hash || '—',
        network: tx.network || '—',
        block: tx.block_number,
        status: tx.status || '—',
        statusClass: tx.status === 'CONFIRMED' ? 'badge-green' : tx.status === 'FAILED' ? 'badge-red' : 'badge-slate',
      }));
  }

  /** Badge class for a DataExchange status. */
  exchangeStatusClass(status: string): string {
    if (status === 'COMPLETED') return 'badge-green';
    if (status === 'FAILED') return 'badge-red';
    return 'badge-slate'; // STARTED / pending
  }

  /** Compact one-line preview of a JSON payload for the sent-to-engine tables. */
  summarizePayload(payload: Record<string, unknown> | undefined): string {
    if (!payload || !Object.keys(payload).length) return '—';
    return Object.entries(payload)
      .map(([key, value]) => {
        if (value === null || value === undefined) return `${key}=—`;
        if (typeof value === 'object') return `${key}={…}`;
        return `${key}=${String(value)}`;
      })
      .join('  ');
  }

  /** Title-case an operation slug for readability. */
  prettyOperation(operation: string): string {
    if (!operation) return '—';
    return operation.replace(/_/g, ' ');
  }

  /** Live lenders first, then by name — keep the overview compact. */
  get sortedLenders(): Lender[] {
    return [...(this.data?.lenders ?? [])].sort((a, b) => {
      if ((a.api_status === 'CONNECTED') !== (b.api_status === 'CONNECTED')) {
        return a.api_status === 'CONNECTED' ? -1 : 1;
      }
      return a.institution_name.localeCompare(b.institution_name);
    }).slice(0, 3);
  }

  /** Stage 2 — assessment snapshot rows (newest first). */
  private toAssessedRow(a: Assessment): AssessedRow {
    const created = (a as AssessmentWithTimestamp).created_at ?? '';
    return {
      record: a,
      when: created,
      reference: a.assessment_reference,
      borrower: a.borrower_name || a.borrower_reference,
      reputation: a.reputation || 'PENDING',
      risk: a.risk_level || '—',
      inputs: this.summarizePayload(a.score_inputs ?? {}),
    };
  }

  /** Newest three scored assessments as a compact activity feed. */
  get recentAssessments(): RecentAssessment[] {
    const byNewest = (x: AssessmentWithTimestamp, y: AssessmentWithTimestamp) =>
      (y.created_at ?? '').localeCompare(x.created_at ?? '');
    return [...(this.data?.assessments ?? [])]
      .sort(byNewest)
      .slice(0, 3)
      .map((a) => this.toRecent(a));
  }

  private toRecent(a: Assessment): RecentAssessment {
    const created = (a as AssessmentWithTimestamp).created_at ?? '';
    return {
      reference: a.assessment_reference,
      borrower: a.borrower_name || a.borrower_reference,
      score: a.credit_score,
      reputation: a.reputation || 'PENDING',
      risk: a.risk_level || '—',
      verified: a.verification_status === 'CONFIRMED',
      when: created,
    };
  }

  reputationClass(reputation: string): string {
    switch (reputation) {
      case 'EXCELLENT':
      case 'GOOD':
        return 'badge-green';
      case 'MODERATE':
        return 'badge-yellow';
      case 'HIGH_RISK':
        return 'badge-red';
      default:
        return 'badge-slate';
    }
  }

  lenderStatusClass(lender: Lender): string {
    return lender.api_status === 'CONNECTED' ? 'badge-green' : lender.api_status === 'DEGRADED' ? 'badge-yellow' : 'badge-slate';
  }

  // =======================================================================
  // Charts dashboard — line, donut, histogram and bars above the inner
  // navbar. All series derive from the same dashboard payload, all rendering
  // is responsive SVG (viewBox + preserveAspectRatio).
  // =======================================================================

  private static readonly DONUT_COLORS = ['#024ad8', '#296ef9', '#356373', '#0e3191', '#c2c2c2'];

  /** Describe an SVG arc for the donut: one path per segment, 100×100 viewBox. */
  private static donutArc(startAngle: number, endAngle: number): string {
    const cx = 50;
    const cy = 50;
    const r = 38;
    const a0 = startAngle * 2 * Math.PI - Math.PI / 2;
    const a1 = endAngle * 2 * Math.PI - Math.PI / 2;
    const x0 = cx + r * Math.cos(a0);
    const y0 = cy + r * Math.sin(a0);
    const x1 = cx + r * Math.cos(a1);
    const y1 = cy + r * Math.sin(a1);
    const large = endAngle - startAngle > 0.5 ? 1 : 0;
    return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
  }

  /** Stage composition of every pipeline record as donut slices. */
  get stageDonut(): DonutSegment[] {
    const parts = [
      { label: 'Lender data', count: (this.data?.lender_exchanges ?? []).length },
      { label: 'Assessments', count: (this.data?.assessments ?? []).length },
      { label: 'Sent to AI', count: (this.data?.ai_exchanges ?? []).length },
      { label: 'AI results', count: (this.data?.ai_results ?? []).length },
      { label: 'On-chain', count: (this.data?.smart_contract_results ?? []).length },
    ];
    const total = parts.reduce((sum, p) => sum + p.count, 0);
    let acc = 0;
    return parts.map((part, i) => {
      const pct = total ? part.count / total : 0;
      const start = acc;
      acc += pct;
      return {
        label: part.label,
        count: part.count,
        color: DashboardComponent.DONUT_COLORS[i % DashboardComponent.DONUT_COLORS.length],
        pct,
        arc: pct > 0 ? DashboardComponent.donutArc(start, Math.max(acc, start + 0.0001)) : '',
      };
    }).filter((segment) => segment.count > 0);
  }

  get stageDonutTotal(): number {
    return this.stageDonut.reduce((sum, s) => sum + s.count, 0);
  }
  /** Per-lender data contribution (exchange counts), busiest first. */
  get lenderBars(): LenderBar[] {
    const counts = new Map<string, number>();
    for (const exchange of this.data?.lender_exchanges ?? []) {
      const key = exchange.lender_name || exchange.lender_id || 'Unknown';
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    const bars = [...counts.entries()]
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 6);
    const peak = Math.max(...bars.map((b) => b.count), 1);
    return bars.map((bar) => ({
      ...bar,
      full: bar.label,
      width: bar.count / peak,
    }));
  }

  private static readonly BANDS: ScoreBand[] = [
    { label: 'Poor', min: 350, max: 499, color: 'bg-[#024ad8]' },
    { label: 'Fair', min: 500, max: 579, color: 'bg-[#296ef9]' },
    { label: 'Good', min: 580, max: 669, color: 'bg-[#356373]' },
    { label: 'Excellent', min: 670, max: 800, color: 'bg-[#0e3191]' },
  ];

  /** Share of scored assessments per 350–800 band, for the mini distribution bar. */
  get scoreBands(): Array<ScoreBand & { count: number; pct: number }> {
    const scores = this.scoredList();
    return DashboardComponent.BANDS.map((band) => {
      const count = scores.filter((s) => s >= band.min && s <= band.max).length;
      const pct = scores.length ? Math.round((count / scores.length) * 100) : 0;
      return { ...band, count, pct };
    });
  }
}
