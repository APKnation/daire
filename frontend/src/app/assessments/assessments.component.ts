import { ChangeDetectorRef, Component, OnInit, inject } from '@angular/core';
import { ApiService, Assessment, VerificationResult } from '../core/api.service';

@Component({
  standalone: true,
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

  ngOnInit(): void {
    this.api.assessments().subscribe({
      next: (assessments) => {
        this.assessments = assessments;
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
}
