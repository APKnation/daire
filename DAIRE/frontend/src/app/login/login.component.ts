import { Component, inject } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../core/auth.service';

@Component({
  standalone: true,
  imports: [ReactiveFormsModule],
  templateUrl: './login.component.html',
  styles: [`
    /* Staggered entrance for the hero copy — each element delays via
       Tailwind's [animation-delay:…] arbitrary property. */
    @keyframes hero-fade-up {
      from { opacity: 0; transform: translateY(18px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    .hero-anim {
      opacity: 0;
      animation-name: hero-fade-up;
      animation-duration: 0.7s;
      animation-timing-function: cubic-bezier(0.22, 0.61, 0.36, 1);
      animation-fill-mode: forwards;
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
      .hero-anim { animation: none; opacity: 1; }
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
