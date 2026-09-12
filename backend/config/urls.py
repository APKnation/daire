from django.contrib import admin
from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


@csrf_exempt
@ensure_csrf_cookie
def session_login(request):
    if request.method != "POST":
        return JsonResponse({"detail": "Only POST is allowed."}, status=405)
    import json
    credentials = json.loads(request.body)
    user = authenticate(
        request,
        username=credentials.get("username", ""),
        password=credentials.get("password", ""),
    )
    if user is None:
        return JsonResponse({"detail": "Invalid username or password."}, status=401)
    login(request, user)
    return JsonResponse({"username": user.get_username()})


@csrf_exempt
def session_logout(request):
    logout(request)
    return JsonResponse({"detail": "Logged out."})


def session_user(request):
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication credentials were not provided."}, status=401)
    return JsonResponse({"username": request.user.get_username()})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/login/", session_login, name="session_login"),
    path("api/auth/logout/", session_logout, name="session_logout"),
    path("api/auth/me/", session_user, name="session_user"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("core.urls")),
]
