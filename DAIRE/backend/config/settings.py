from pathlib import Path

import environ


# ============================================================
# BASE CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False)
)

environ.Env.read_env(BASE_DIR / ".env")


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = env(
    "SECRET_KEY",
    default="django-insecure-change-me"
)

DEBUG = env("DEBUG")


# ============================================================
# ALLOWED HOSTS
# ============================================================

ALLOWED_HOSTS = env.list(
    "ALLOWED_HOSTS",
    default=[
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "172.17.16.76",
        "172.17.16.47",
        "172.17.16.70",
    ],
)


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "corsheaders",
    "rest_framework",
    "drf_spectacular",

    # Local
    "core",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",
]


# ============================================================
# URL CONFIGURATION
# ============================================================

ROOT_URLCONF = "config.urls"


# ============================================================
# TEMPLATES
# ============================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ============================================================
# WSGI
# ============================================================

WSGI_APPLICATION = "config.wsgi.application"


# ============================================================
# DATABASE
# ============================================================
# PostgreSQL connection is provided through DATABASE_URL
# in the .env file.

DATABASES = {
    "default": env.db("DATABASE_URL")
}


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = []


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "static/"


# ============================================================
# DEFAULT PRIMARY KEY
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ============================================================
# CORS CONFIGURATION
# ============================================================
# This allows the Angular frontend and other trusted clients
# to communicate with the Django API.

CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_CREDENTIALS = True


# ============================================================
# CSRF TRUSTED ORIGINS
# ============================================================

CSRF_TRUSTED_ORIGINS = env.list(
    "CSRF_TRUSTED_ORIGINS",
    default=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://172.17.16.76:4200",
        "http://172.17.16.68:4200",
        "http://daire.co.tz",
        "https://daire.co.tz",
    ],
)


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
    ),

    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.AllowAny",
    ),

    "DEFAULT_SCHEMA_CLASS": (
        "drf_spectacular.openapi.AutoSchema"
    ),

    # Pagination
    "DEFAULT_PAGINATION_CLASS": (
        "rest_framework.pagination.PageNumberPagination"
    ),

    "PAGE_SIZE": 10,
}


# ============================================================
# DRF SPECTACULAR / API DOCUMENTATION
# ============================================================

SPECTACULAR_SETTINGS = {
    "TITLE": "DAIRE Central System API",

    "DESCRIPTION": (
        "Consent-aware lender integration and assessment orchestration API.\n\n"
        "The lender network is **NMB (LDR-NMB-02) and CRDB (LDR-CRDB-01) only** — "
        "pushes from any other lender_id are rejected. Lenders merge on "
        "`nida_number`: the same person at both banks becomes ONE central borrower "
        "and a single assessment scores the merged profile.\n\n"
        "Machine-checkable schema of record: `docs/openapi-schema.yml` "
        "(regenerate with `./export_openapi.sh`). Human-readable contracts: "
        "`docs/API_ENDPOINTS.md` and `DAIRE/LENDER_SUBSYSTEM_README.md`."
    ),

    "VERSION": "1.1.0",

    # Deterministic exports: sort everything, pin the server, keep the file
    # stable across runs so diffs only show real API changes.
    "SORT_OPERATION_PARAMETERS": True,
    "SORT_SCHEMAS": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "SERVERS": [{"url": "http://127.0.0.1:8000", "description": "DAIRE Central System (local)"}],

    # Serialize DecimalFields as strings (Django default) and mark them clearly.
    "ENUM_ADD_EXPLICIT_BLANK_NULL_CHOICE": False,
}


# ============================================================
# OTHER BACKEND CONFIGURATION
# ============================================================
# The other backend is running on 172.17.16.68.

OTHER_BACKEND_URL = env(
    "OTHER_BACKEND_URL",
    default="http://172.17.16.68:8000",
)