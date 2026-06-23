import { HttpInterceptorFn } from '@angular/common/http';

const unsafeMethods = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

export const csrfInterceptor: HttpInterceptorFn = (request, next) => {
  if (!unsafeMethods.has(request.method)) {
    return next(request);
  }

  const csrfToken = getCookie('csrftoken');
  if (!csrfToken) {
    return next(request);
  }

  return next(
    request.clone({
      setHeaders: {
        'X-CSRFToken': csrfToken
      }
    })
  );
};

function getCookie(name: string): string | null {
  const cookies = document.cookie ? document.cookie.split('; ') : [];

  for (const cookie of cookies) {
    const [cookieName, ...valueParts] = cookie.split('=');

    if (cookieName === name) {
      return decodeURIComponent(valueParts.join('='));
    }
  }

  return null;
}
