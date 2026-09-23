import Swal, { SweetAlertResult } from 'sweetalert2';

const THEME = {
  background: '#f7f7f7',
  customClass: { popup: 'rounded-2xl shadow-xl' },
};

/** Anchor an error popup right next to the button/element the user clicked. */
export function alertNear(
  el: HTMLElement | null,
  title: string,
  text: string,
  icon: 'error' | 'warning' | 'info' | 'success' = 'error',
): Promise<SweetAlertResult> {
  const target = el?.closest('button, label, .btn-anchor') as HTMLElement | null;
  return Swal.fire({
    target,
    title,
    text,
    icon,
    position: 'bottom',
    grow: 'row',
    backdrop: false,
    timer: 2200,
    timerProgressBar: true,
    showConfirmButton: false,
    ...THEME,
  });
}

/** Centered confirmable popup for blocking errors. */
export function alertCenter(title: string, text: string, icon: 'error' | 'warning' | 'info' | 'success' = 'error'): Promise<SweetAlertResult> {
  return Swal.fire({ title, text, icon, confirmButtonColor: '#024ad8', ...THEME });
}

/** Compact success/info toast in the top-right corner. */
export function toast(title: string, icon: 'success' | 'info' | 'warning' | 'error' = 'success'): Promise<SweetAlertResult> {
  return Swal.fire({
    toast: true,
    position: 'top-end',
    showConfirmButton: false,
    timer: 1800,
    timerProgressBar: true,
    icon,
    title,
    background: icon === 'success' ? 'rgb(145 234 247 / 0.25)' : undefined,
  });
}
