import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';
import { LoginComponent } from './login/login.component';
import { DashboardComponent } from './dashboard/dashboard.component';
import { AssessmentsComponent } from './assessments/assessments.component';
import { RecordsComponent } from './records/records.component';

export const routes: Routes = [
  { path: '', component: LoginComponent },
  { path: 'login', component: LoginComponent },
  { path: 'dashboard', canActivate: [authGuard], component: DashboardComponent },
  { path: 'assessments', canActivate: [authGuard], component: AssessmentsComponent },
  { path: 'lenders', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'lenders' } },
  { path: 'borrowers', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'borrowers' } },
  { path: 'consents', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'consents' } },
  { path: 'integrations', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'integrations' } },
  { path: 'credit-profiles', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'credit-profiles' } },
  { path: 'features', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'features' } },
  { path: 'ai-reputation', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'ai-reputation' } },
  { path: 'smart-contract', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'smart-contract' } },
  { path: 'blockchain', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'blockchain' } },
  { path: 'audit-logs', canActivate: [authGuard], component: RecordsComponent, data: { kind: 'audit-logs' } },
  { path: '**', redirectTo: '' },
];
