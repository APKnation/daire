import { Component, inject, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from './core/auth.service';

interface NavItem {
  label: string;
  link: string;
  /** SVG path data for the 24×24 stroke icon. */
  icon: string;
  exact?: boolean;
}

interface NavSection {
  label: string;
  items: NavItem[];
}

@Component({
  selector: 'daire-root',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.component.html',
})
export class AppComponent {
  readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** Mobile drawer visibility (< lg). */
  readonly sidebarOpen = signal(false);
  /** True below the lg breakpoint — drives drawer-only accessibility attrs. */
  readonly isMobile = signal(
    typeof matchMedia !== "undefined" && matchMedia("(max-width: 1023px)").matches,
  );
  /** Desktop icon-rail mode (≥ lg), persisted across sessions. */
  readonly collapsed = signal(
    typeof localStorage !== 'undefined' && localStorage.getItem('daire.sidebar.collapsed') === '1',
  );

  readonly sections: NavSection[] = [
    {
      label: '',
      items: [
        { label: 'Overview', link: '/dashboard', exact: true,
          icon: 'M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6' },
        { label: 'Assessments', link: '/assessments',
          icon: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z' },
        { label: 'Data exchange', link: '/data-exchange',
          icon: 'M8 7h8m-8 5h8m-8 5h5M5 4h14a1 1 0 011 1v14a1 1 0 01-1 1H5a1 1 0 01-1-1V5a1 1 0 011-1z' },
        { label: 'Data management', link: '/data-management',
          icon: 'M4 6h16M4 12h16M4 18h16' },
      ],
    },
    {
      label: 'Network',
      items: [
        { label: 'Lenders', link: '/lenders',
          icon: 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4' },
        { label: 'Consent management', link: '/consents',
          icon: 'M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z' },
        { label: 'Integrations', link: '/integrations',
          icon: 'M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z' },
      ],
    },
    {
      label: 'Verification',
      items: [
        { label: 'AI reputation', link: '/ai-reputation',
          icon: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z' },
        { label: 'Blockchain', link: '/blockchain',
          icon: 'M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1' },
      ],
    },
  ]
    .filter((section) => !['Network', 'Verification'].includes(section.label))
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => item.label !== 'Assessments'),
    }));

  constructor() {
    // Track the lg breakpoint so the drawer-only inert/aria-hidden state is
    // never applied on desktop (inert would kill clicks and hover there).
    if (typeof matchMedia !== "undefined") {
      const media = matchMedia("(max-width: 1023px)");
      media.addEventListener("change", (event) => this.isMobile.set(event.matches));
    }
    // Close the mobile drawer whenever a navigation lands.
    this.router.events
      .pipe(filter((event) => event instanceof NavigationEnd))
      .subscribe(() => this.sidebarOpen.set(false));
  }

  toggleSidebar(): void {
    this.sidebarOpen.update((open) => !open);
  }

  closeSidebar(): void {
    this.sidebarOpen.set(false);
  }

  toggleCollapse(): void {
    this.collapsed.update((value) => {
      localStorage.setItem('daire.sidebar.collapsed', value ? '0' : '1');
      return !value;
    });
  }

  showApplicationShell(): boolean {
    return !['/', '/login'].includes(this.router.url);
  }
}
