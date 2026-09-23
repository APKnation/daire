import { Component, EventEmitter, Input, Output } from '@angular/core';
import { PAGE_SIZE } from '../core/api.service';

/** Shared pager controls for long tables. */
@Component({
  standalone: true,
  selector: 'app-pager',
  template: `
    @if (count > pageSize) {
      <div class="flex items-center justify-end border-t border-[#e8e8e8] bg-[#f7f7f7] px-6 py-3 text-sm">
        <span class="flex items-center gap-2">
          <button class="rounded-lg border border-[#e8e8e8] bg-white px-3 py-1.5 text-xs font-semibold text-[#3d3d3d] disabled:opacity-40"
            [disabled]="page <= 1" (click)="pageChange.emit(page - 1)">← Prev</button>
          <button class="rounded-lg border border-[#e8e8e8] bg-white px-3 py-1.5 text-xs font-semibold text-[#3d3d3d] disabled:opacity-40"
            [disabled]="page >= totalPages" (click)="pageChange.emit(page + 1)">Next →</button>
        </span>
      </div>
    }
  `,
})
export class PagerComponent {
  @Input() page = 1;
  @Input() count = 0;
  @Input() pageSize = PAGE_SIZE;
  @Output() pageChange = new EventEmitter<number>();

  get totalPages(): number {
    return Math.max(1, Math.ceil(this.count / this.pageSize));
  }
  get from(): number {
    return this.count === 0 ? 0 : (this.page - 1) * this.pageSize + 1;
  }
  get to(): number {
    return Math.min(this.count, this.page * this.pageSize);
  }
}
