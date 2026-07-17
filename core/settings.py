import os
from pathlib import Path
from datetime import timedelta
from core.unfold import UNFOLD

ENVIRONMENT = os.environ.get("DJANGO_ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT == "production"

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = "django-insecure-&%16q%ly$sa-&spy_5-l-6$b3!#h^tw!bu6%d&-e23emtc5b7d"

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

if IS_PRODUCTION:
    ALLOWED_HOSTS = ["*", "ledarsapi.raktch.com"]
    # SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # SESSION_COOKIE_SECURE = True
    # CSRF_COOKIE_SECURE = True
    # SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = None
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
else:
    ALLOWED_HOSTS = ["*", "192.168.0.101", "192.168.0.15:8000"]
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
SITE_ID = 1

LOCAL_FRONTEND_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3071",
    "http://127.0.0.1:3071",
    "http://localhost:3072",
    "http://127.0.0.1:3072",
]

CSRF_TRUSTED_ORIGINS = LOCAL_FRONTEND_ORIGINS + [
    "http://192.168.0.15:3000",  # For frontend running from another PC using your backend IP
]

CORS_ALLOWED_ORIGINS = LOCAL_FRONTEND_ORIGINS + [
    "http://192.168.0.15:3000",
]


# Application definition

INSTALLED_APPS = [
    "unfold",  # before django.contrib.admin
    "unfold.contrib.filters",  # optional, if special filters are needed
    "unfold.contrib.forms",  # optional, if special form elements are needed
    "unfold.contrib.inlines",  # optional, if special inlines are needed
    "unfold.contrib.import_export",  # optional, if django-import-export package is used
    "unfold.contrib.guardian",  # optional, if django-guardian package is used
    "unfold.contrib.simple_history",  # optional, if django-simple-history package is used
    "unfold.contrib.location_field",  # optional, if django-location-field package is used
    "unfold.contrib.constance",  # optional, if django-constance package is used
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_filters",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "djoser",
    "corsheaders",
    "import_export",
    # local apps
    "authentication",
    "employee",
    "attendance",
    "device_attendance",
    "beneficiary.apps.BeneficiaryConfig",
    "shift",
    "holiday",
    "leave",
    "notification",
    "payroll",
    "accounting.apps.AccountingConfig",
    "vendorportal.apps.VendorportalConfig",
    # 'inventory',
    "inventory.apps.InventoryConfig",
    "procurement",
    "donor",
    "projects",
    "project_managements.apps.ProjectManagementsConfig",
    "returns",
    "approval_workflow.apps.ApprovalWorkflowConfig",
    "todo",
    "crm",
    "meeting_management", "django_extensions",
    "final_settlement",
    "movement_management",
    "travel_expense",
    "provident_fund",
    "central_dashboard",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # 'rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly',
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
    ],
}

SIMPLE_JWT = {
    # 'AUTH_HEADER_TYPES': ('JWT',),
    "ACCESS_TOKEN_LIFETIME": timedelta(days=7),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=15),
    # 'AUTH_TOKEN_CLASSES': (
    #     'rest_framework_simplejwt.tokens.AccessToken',
    # )
}

DOMAIN = "Ledar'sapi.raktch.com"
SITE_NAME = "Ledar's"
FRONTEND_URL = "https://Ledar's.raktch.com"

DJOSER = {
    "DOMAIN": DOMAIN,
    "LOGIN_FIELD": "email",
    # "USER_ID_FIELD": "name",
    "USER_CREATE_PASSWORD_RETYPE": True,
    "USERNAME_CHANGED_EMAIL_CONFIRMATION": False,
    "PASSWORD_CHANGED_EMAIL_CONFIRMATION": False,
    "SET_USERNAME_RETYPE": True,
    "SET_PASSWORD_RETYPE": True,
    "PASSWORD_RESET_CONFIRM_URL": "/password/reset/confirm/{uid}/{token}",
    "USERNAME_RESET_CONFIRM_URL": "email/reset/confirm/{uid}/{token}",
    "ACTIVATION_URL": "api/activate/{uid}/{token}",
    "SEND_ACTIVATION_EMAIL": False,
    "SEND_CONFIRMATION_EMAIL": False,
    "SERIALIZERS": {
        "user_create": "authentication.serializers.CustomUserSerializer",
        "user": "authentication.serializers.CustomUserSerializer",
        "current_user": "authentication.serializers.CustomUserSerializer",
        # 'user_delete': 'djoser.serializers.UserDeleteSerializer',
    },
    "EMAIL": {
        "activation": "authentication.email.ActivationEmail",
        "confirmation": "authentication.email.ConfirmationEmail",
        "password_reset": "authentication.email.PasswordResetEmail",
        "password_changed_confirmation": "authentication.email.PasswordChangedConfirmationEmail",
    },
}

# # Email settings
# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
# EMAIL_HOST = "smtp.gmail.com"
# EMAIL_PORT = 587
# EMAIL_HOST_USER = "dsphr.soft@Ledar's.com.bd"
# EMAIL_HOST_PASSWORD = "tunt logd nevc srfa"
# EMAIL_USE_TLS = True

# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

# DATABASES = {
#     "default": {
#         "ENGINE": "django.db.backends.postgresql",
#         "NAME": "ledars_db",          # your PostgreSQL database name
#         "USER": "ledarsuser",        # your PostgreSQL user
#         "PASSWORD": "Raktch@1997#", # your PostgreSQL password
#         "HOST": "localhost",   # IP of your PostgreSQL server
#         "PORT": "5432",                  # default PostgreSQL port
#         "CONN_MAX_AGE": 30,              # seconds; Django keeps DB connection open
#         "OPTIONS": {
#             "connect_timeout": 10,       # seconds to wait for connection
#             # "sslmode": "require",      # optional if you use SSL
#         },
#     }
# }




DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}




##################
# AUTHENTICATION #
##################

AUTH_USER_MODEL = "authentication.User"

# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Dhaka"


USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
CRISPY_TEMPLATE_PACK = "bootstrap4"
# URL used to access the media
MEDIA_URL = "/media/"
# MEDIA_ROOT = BASE_DIR / 'media'

# STATICFILES_DIRS = [
#     os.path.join(BASE_DIR / 'static')
# ]
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

UNFOLD = UNFOLD

DATA_UPLOAD_MAX_NUMBER_FIELDS = 100000
