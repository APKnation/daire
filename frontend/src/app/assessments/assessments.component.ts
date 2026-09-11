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
    this.api.verifyAssessment(assessment.assessment_reference).subscribe({
      next: (result) => {
        this.verification = result;
        this.cdr.markForCheck();
      },
    });
  }
}
