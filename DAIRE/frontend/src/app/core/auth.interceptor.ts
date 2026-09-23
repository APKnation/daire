import { HttpInterceptorFn } from '@angular/common/http';

function csrfToken(): string {
  const match = document.cookie.split('; ').find((item) => item.startsWith('csrftoken='));
  return match ? decodeURIComponent(match.split('=').slice(1).join('=')) : '';
}

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = csrfToken();
  const protectedMethod = !['GET', 'HEAD', 'OPTIONS'].includes(request.method.toUpperCase());
  return next(request.clone({
    withCredentials: true,
    setHeaders: protectedMethod && token ? { 'X-CSRFToken': token } : {},
  }));
};
