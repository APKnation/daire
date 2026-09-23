import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ApiService, Assessment, PAGE_SIZE, VerificationResult } from '../core/api.service';
import { PagerComponent } from '../core/pager.component';

@Component({
  standalone: true,
  imports: [FormsModule, PagerComponent],
  templateUrl: './assessments.component.html',
})
export class AssessmentsComponent implements OnInit {
  private readonly api = inject(ApiService);
  private readonly cdr = inject(ChangeDetectorRef);
  assessments: Assessment[] = [];
  verification: VerificationResult | null = null;
  error = '';
  loading = true;
  verifyingReference = '';
  borrowerReference = '';
  creating = false;
  page = 1;
  totalCount = 0;

  ngOnInit(): void {
    this.loadPage(1);
  }
  loadPage(next: number): void {
    if (next < 1 || (this.totalCount > 0 && next > Math.ceil(this.totalCount / PAGE_SIZE))) return;
    this.page = next;
    this.loading = true;
    this.cdr.markForCheck();
    this.api.paged<Assessment>('/api/assessments/', this.page).subscribe({
      next: (paged) => {
        this.assessments = paged.items;
        this.totalCount = paged.count;
        this.loading = false;
        this.cdr.markForCheck();
      },
      error: () => {
        this.error = 'Assessments could not be loaded.';
        this.loading = false;
        this.cdr.markForCheck();
      },
    });
  }
  verify(assessment: Assessment): void {
    this.error = '';
    this.verifyingReference = assessment.assessment_reference;
    this.cdr.markForCheck();
    this.api.verifyAssessment(assessment.assessment_reference).subscribe({
      next: (result) => {
        this.verification = result;
        this.verifyingReference = '';
        assessment.verification_status = result.verified ? 'CONFIRMED' : 'UNCONFIRMED';
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.verifyingReference = '';
        this.error = err?.error?.detail || 'This assessment could not be verified. It may not have a blockchain transaction yet.';
        this.cdr.markForCheck();
      },
    });
  }
  create(): void {
    this.error = '';
    const ref = this.borrowerReference.trim();
    if (!ref) {
      this.error = 'Enter a borrower reference first — pull or receive lender data for it, then open the assessment.';
      return;
    }
    this.creating = true;
    this.cdr.markForCheck();
    this.api.createAssessment(ref).subscribe({
      next: (assessment) => {
        this.creating = false;
        this.borrowerReference = '';
        this.loadPage(1);
        this.cdr.markForCheck();
      },
      error: (err) => {
        this.creating = false;
        this.error = err?.error?.detail || 'Assessment could not be opened.';
        this.cdr.markForCheck();
      },
    });
  }
}
