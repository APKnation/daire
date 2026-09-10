import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (request, next) =>
  next(request.clone({ withCredentials: true }));
