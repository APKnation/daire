import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './login.component.html',
  styles: [`
    /* Hero copy: hidden at first, POPS up after 5s with a springy overshoot,
       then a separate inner layer bobs it up and down forever. */
    @keyframes hero-pop {
      0%   { opacity: 0; transform: scale(0.6) translateY(24px); }
      60%  { opacity: 1; transform: scale(1.05) translateY(0); }
      100% { opacity: 1; transform: scale(1) translateY(0); }
    }
    .hero-pop {
      opacity: 0;
      animation: hero-pop 0.8s cubic-bezier(0.34, 1.56, 0.64, 1) 5s forwards;
    }
    /* Small-amplitude vertical bob (±6px) — starts right after the pop
       settles so the two transforms never fight over the same property. */
    @keyframes hero-float {
      0%, 100% { transform: translateY(0); }
      25%      { transform: translateY(-6px); }
      75%      { transform: translateY(6px); }
    }
    .hero-float {
      animation: hero-float 3.5s ease-in-out 5.8s infinite;
    }
    /* Slow color drift across the gradient headline. */
    @keyframes hero-gradient-shift {
      0%, 100% { background-position: 0% 50%; }
      50%      { background-position: 100% 50%; }
    }
    .hero-gradient {
      background-size: 220% auto;
      animation: hero-gradient-shift 5s ease-in-out infinite;
    }
    /* Respect users who opt out of motion. */
    @media (prefers-reduced-motion: reduce) {
      .hero-pop { animation: none; opacity: 1; }
      .hero-float { animation: none; }
      .hero-gradient { animation: none; }
    }
  `],
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  readonly form = this.fb.nonNullable.group({ username: ['', Validators.required], password: ['', Validators.required] });
  loading = false;
  error = '';

  submit(): void {
    if (this.form.invalid) return;
    this.loading = true;
    this.error = '';
    const { username, password } = this.form.getRawValue();
    this.auth.login(username, password).subscribe({
      next: () => void this.router.navigate(['/dashboard']),
      error: () => { this.error = 'Unable to sign in. Check your credentials and try again.'; this.loading = false; },
    });
  }
}
