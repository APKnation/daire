import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { ApiService, Borrower, Lender } from '../core/api.service';

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
  borrowerForm: Partial<Borrower> = {};
  lenderForm: Partial<Lender> = {};
  editingBorrowerId: number | null = null;
  editingLenderId: number | null = null;
  error = '';
  message = '';

  ngOnInit(): void { this.reload(); }
  reload(): void {
    this.api.borrowers().subscribe((items) => { this.borrowers = items; this.cdr.markForCheck(); });
    this.api.lenders().subscribe((items) => { this.lenders = items; this.cdr.markForCheck(); });
  }
  newBorrower(): void { this.editingBorrowerId = null; this.borrowerForm = { borrower_reference: '' }; }
  editBorrower(item: Borrower): void { this.editingBorrowerId = item.id || null; this.borrowerForm = { ...item }; }
  saveBorrower(): void {
    const request = this.editingBorrowerId ? this.api.updateBorrower(this.editingBorrowerId, this.borrowerForm) : this.api.createBorrower(this.borrowerForm);
    request.subscribe({ next: () => { this.message = 'Borrower saved.'; this.error = ''; this.borrowerForm = {}; this.reload(); this.cdr.markForCheck(); }, error: (err) => this.showError(err) });
  }
  removeBorrower(item: Borrower): void {
    if (!item.id || !window.confirm(`Delete borrower ${item.borrower_reference}?`)) return;
    this.api.deleteBorrower(item.id).subscribe({ next: () => { this.message = 'Borrower deleted.'; this.reload(); this.cdr.markForCheck(); }, error: (err) => this.showError(err) });
  }
  newLender(): void { this.editingLenderId = null; this.lenderForm = { lender_id: '', institution_name: '', institution_type: 'BANK', api_base_url: '', api_status: 'DISCONNECTED', authentication_method: 'API_KEY' }; }
  editLender(item: Lender): void { this.editingLenderId = item.id || null; this.lenderForm = { ...item }; }
  saveLender(): void {
    const request = this.editingLenderId ? this.api.updateLender(this.editingLenderId, this.lenderForm) : this.api.createLender(this.lenderForm);
    request.subscribe({ next: () => { this.message = 'Lender saved.'; this.error = ''; this.lenderForm = {}; this.reload(); this.cdr.markForCheck(); }, error: (err) => this.showError(err) });
  }
  removeLender(item: Lender): void {
    if (!item.id || !window.confirm(`Delete lender ${item.institution_name}?`)) return;
    this.api.deleteLender(item.id).subscribe({ next: () => { this.message = 'Lender deleted.'; this.reload(); this.cdr.markForCheck(); }, error: (err) => this.showError(err) });
  }
  private showError(err: { error?: { detail?: string } }): void { this.error = err.error?.detail || 'Operation failed. Check required fields and linked records.'; this.cdr.markForCheck(); }
}
