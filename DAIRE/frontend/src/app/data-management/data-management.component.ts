import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, Borrower, Lender, PAGE_SIZE } from '../core/api.service';

@Component({
  standalone: true,
  imports: [FormsModule, RouterLink],
  templateUrl: './data-management.component.html',
})
export class DataManagementComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);

  borrowers: Borrower[] = [];
  lenders: Lender[] = [];
  borrowerQuery = '';
  lenderQuery = '';
  borrowerPage = 1;
  borrowerCount = 0;
  lenderPage = 1;
  lenderCount = 0;
  lenderForm: Partial<Lender> = {};
  editingLenderId: number | null = null;
  error = '';
  message = '';
  /** Plaintext key issued on register/regenerate — shown once, never re-fetchable. */
  newApiKey: { lender_id: string; api_key: string } | null = null;
  /** Central push URL handed to lender developers — derived from the live host
   * at runtime, never hardcoded, so it is correct wherever the console runs. */
  get centralPushUrl(): string {
    return `${window.location.protocol}//${window.location.host}/api/lender-data/receive/`;
  }

  ngOnInit(): void { this.reload(); }

  reload(): void {
    this.loadBorrowers(1);
    this.loadLenders(1);
  }

  loadBorrowers(next: number): void {
    if (next < 1 || (this.borrowerCount > 0 && next > Math.ceil(this.borrowerCount / PAGE_SIZE))) return;
    this.borrowerPage = next;
    const query = this.borrowerQuery.trim();
    const url = query ? `/api/borrowers/search/?borrower_reference=${encodeURIComponent(query)}` : '/api/borrowers/';
    this.api.paged<Borrower>(url, this.borrowerPage).subscribe((paged) => {
      this.borrowers = paged.items.slice(0, 3);
      this.borrowerCount = paged.count;
      this.cdr.markForCheck();
    });
  }

  loadLenders(next: number): void {
    if (next < 1 || (this.lenderCount > 0 && next > Math.ceil(this.lenderCount / PAGE_SIZE))) return;
    this.lenderPage = next;
    // Client-side filter (small registry) over the paged lender endpoint.
    this.api.paged<Lender>('/api/lenders/', this.lenderPage).subscribe((paged) => {
      this.lenders = this.filterLenders(paged.items).slice(0, 3);
      this.lenderCount = paged.count;
      this.cdr.markForCheck();
    });
  }

  private filterLenders(items: Lender[]): Lender[] {
    const q = this.lenderQuery.trim().toLowerCase();
    if (!q) return items;
    return items.filter((l) =>
      l.institution_name?.toLowerCase().includes(q)
      || l.lender_id?.toLowerCase().includes(q)
      || l.institution_type?.toLowerCase().includes(q)
      || l.api_base_url?.toLowerCase().includes(q));
  }

  get activeBorrowerCount(): number {
    return this.borrowers.filter((b) => b.is_active !== false).length;
  }

  get connectedLenderCount(): number {
    return this.lenders.filter((l) => l.api_status === 'CONNECTED').length;
  }

  /** Status chip color from the lender URL shape (mock vs real subsystem). */
  lenderKind(l: Lender): 'live' | 'mock' {
    return (l.api_base_url || '').includes('mock-lender') ? 'mock' : 'live';
  }

  toggleBorrower(item: Borrower): void {
    if (!item.id) return;
    const nextState = !(item.is_active ?? true);
    const action = nextState ? 'activate' : 'deactivate';
    if (!window.confirm(`${action[0].toUpperCase() + action.slice(1)} borrower ${item.borrower_reference}?`)) return;
    this.api.updateBorrower(item.id, { is_active: nextState }).subscribe({
      next: () => { this.message = `Borrower ${nextState ? 'activated' : 'deactivated'}.`; this.error = ''; this.reload(); this.cdr.markForCheck(); },
      error: (err) => this.showError(err),
    });
  }

  newLender(): void {
    this.editingLenderId = null;
    this.lenderForm = { lender_id: '', institution_name: '', institution_type: 'COMMERCIAL_BANK', api_base_url: '', api_status: 'CONNECTED', authentication_method: 'API_KEY' };
  }

  editLender(item: Lender): void { this.editingLenderId = item.id || null; this.lenderForm = { ...item }; }

  saveLender(): void {
    const request = this.editingLenderId ? this.api.updateLender(this.editingLenderId, this.lenderForm) : this.api.createLender(this.lenderForm);
    request.subscribe({
      next: (res) => {
        this.newApiKey = res.api_key ? { lender_id: res.lender_id, api_key: res.api_key } : null;
        this.message = res.api_key ? `Lender ${res.lender_id} registered — copy its API key now.` : 'Lender saved.';
        this.error = ''; this.lenderForm = {}; this.reload(); this.cdr.markForCheck();
      },
      error: (err) => this.showError(err),
    });
  }

  regenerateKey(item: Lender): void {
    if (!item.id || !window.confirm(`Revoke the current API key for ${item.institution_name} and issue a new one?`)) return;
    this.api.regenerateLenderKey(item.id).subscribe({
      next: (res) => {
        this.newApiKey = res.api_key ? { lender_id: res.lender_id, api_key: res.api_key } : null;
        this.message = `New API key issued for ${res.lender_id} — copy it now. The old key is revoked.`;
        this.error = ''; this.reload(); this.cdr.markForCheck();
      },
      error: (err) => this.showError(err),
    });
  }

  removeLender(item: Lender): void {
    if (!item.id || !window.confirm(`Delete lender ${item.institution_name}? Linked borrower accounts will block deletion.`)) return;
    this.api.deleteLender(item.id).subscribe({ next: () => { this.message = 'Lender deleted.'; this.reload(); this.cdr.markForCheck(); }, error: (err) => this.showError(err) });
  }

  private showError(err: { error?: { detail?: string } }): void {
    this.error = err.error?.detail || 'Operation failed. Check required fields and linked records.';
    this.cdr.markForCheck();
  }
}
