import os
import secrets
from pathlib import Path

from core.env import env_first, resolve_data_root, resolve_real_fixtures_dir

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_ROOT = resolve_data_root()
if DATA_ROOT == BASE_DIR or BASE_DIR in DATA_ROOT.parents:
    raise RuntimeError("DATA_ROOT must be outside the source repository.")

REAL_FIXTURES_DIR = resolve_real_fixtures_dir()


def _secret_key():
    env = env_first("SOCIALS_MANAGER_SECRET_KEY", "BAND_EVIDENCE_SECRET_KEY")
    if env:
        return env
    path = DATA_ROOT / "secret_key"
    if path.exists():
        return path.read_text().strip()
    if DATA_ROOT.exists():
        key = secrets.token_urlsafe(50)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as fh:
            fh.write(key)
        return key
    return "uninitialised-" + secrets.token_urlsafe(20)


SECRET_KEY = _secret_key()
DEBUG = env_first("SOCIALS_MANAGER_DEBUG", "BAND_EVIDENCE_DEBUG") == "1"
BIND_HOST = "127.0.0.1"
PORT = int(env_first("SOCIALS_MANAGER_PORT", "BAND_EVIDENCE_PORT", default="8765"))
ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
CSRF_TRUSTED_ORIGINS = [f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}"]

INSTALLED_APPS = [
    "django.contrib.staticfiles",
    "core",
    "catalogue",
    "sources",
    "campaigns",
    "evaluation",
    "findings",
    "context",
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.middleware.LoopbackOnlyMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.SecurityHeadersMiddleware",
]

ROOT_URLCONF = "socials_manager.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "web.context.app_context",
            ],
        },
    }
]
WSGI_APPLICATION = "socials_manager.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_ROOT / "app.sqlite3",
        "OPTIONS": {
            "timeout": 20,
            "transaction_mode": "IMMEDIATE",
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LANGUAGE_CODE = "en-au"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT_SOURCE = BASE_DIR / "web" / "static"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 64 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = MAX_UPLOAD_BYTES + 64 * 1024
DATA_UPLOAD_MAX_NUMBER_FIELDS = 2000

CSRF_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_HTTPONLY = False
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"

ALLOW_CLOCK_OVERRIDE = False
ALLOW_SYNTHETIC_SOURCES = False

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {"django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False}},
}
