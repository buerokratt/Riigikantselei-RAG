"""
Django settings for api project.

Generated by 'django-admin startproject' using Django 5.0.6.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.0/ref/settings/
"""
import logging
import os
from gettext import gettext
from pathlib import Path

import environ

from api.utilities.vectorizer import download_vectorization_resources

# pylint: disable=bad-builtin

env_file_path = os.getenv('RK_ENV_FILE', None)
if env_file_path:
    print(
        f"Loading environment variables from {env_file_path} as env variable 'RK_ENV_FILE' is set!"
    )
    environ.Env.read_env(env_file=env_file_path)

env = environ.Env()

GPT_SYSTEM_PROMPT_DEFAULT = """Kontekst: {}

Palun vasta järgnevale küsimusele sellega samas keeles.
Kasuta küsimusele vastamiseks AINULT ülaltoodud konteksti.
Kui kontekstis pole vastamiseks piisavalt ja/või sobivat infot, vasta: "{}".

Küsimus: {}
"""

# TODO: why are some parameters in core settings and some not?
#  Does anything other than default usage limit or cost need to be here?
PROTECTED_CORE_KEYS = ('SECRET', 'KEY', 'PASSWORD')
CORE_SETTINGS = {
    #
    # Elasticearch general
    'ELASTICSEARCH_URL': env('RK_ELASTICSEARCH_URL', default='http://localhost:9200'),
    'ELASTICSEARCH_TIMEOUT': env('RK_ELASTICSEARCH_TIMEOUT', default=10),
    # Elastic fields
    'ELASTICSEARCH_VECTOR_FIELD': env('RK_ELASTICSEARCH_VECTOR_FIELD', default='vector'),
    'ELASTICSEARCH_TEXT_CONTENT_FIELD': env('RK_ELASTICSEARCH_TEXT_CONTENT_FIELD', default='text'),
    'ELASTICSEARCH_YEAR_FIELD': env('RK_ELASTICSEARCH_YEAR_FIELD', default='year'),
    'ELASTICSEARCH_URL_FIELD': env('RK_ELASTICSEARCH_URL_FIELD', default='url'),
    'ELASTICSEARCH_TITLE_FIELD': env('RK_ELASTICSEARCH_TITLE_FIELD', default='reference'),
    # For the field which references the parent document (actual paper document)
    # the segment belongs to.
    'ELASTICSEARCH_PARENT_FIELD': env('RK_ELASTICSEARCH_PARENT_FIELD', default='doc_id'),
    # OpenAI integration
    # TODO: obtain key
    'OPENAI_API_KEY': env('RK_OPENAI_API_KEY', default=None),
    'OPENAI_SYSTEM_MESSAGE': env.str(
        'RK_OPENAI_SYSTEM_MESSAGE', default='You are a helpful assistant.'
    ),
    'OPENAI_MISSING_CONTEXT_MESSAGE': env.str(
        'RK_OPENAI_MISSING_CONTEXT_MESSAGE', default='Teadmusbaasis info puudub!'
    ),
    'OPENAI_OPENING_QUESTION': env.str(
        'RK_OPENAI_OPENING_QUESTION', default=GPT_SYSTEM_PROMPT_DEFAULT
    ),
    'OPENAI_API_TIMEOUT': env.int('RK_OPENAI_API_TIMEOUT', default=10),
    'OPENAI_API_MAX_RETRIES': env.int('RK_OPENAI_API_MAX_RETRIES', default=5),
    'OPENAI_API_CHAT_MODEL': env.int('RK_OPENAI_API_CHAT_MODEL', default='gpt-4o'),
    'OPENAI_CONTEXT_MAX_TOKEN_LIMIT': env.int('RK_OPENAI_CONTEXT_MAX_TOKEN_LIMIT', default=8000),
    #
    # Other
    'DEFAULT_USAGE_LIMIT_EUROS': env.float('RK_DEFAULT_USAGE_LIMIT_EUROS', default=10.0),
    # defaults from https://openai.com/api/pricing/ GPT-4o
    'EURO_COST_PER_INPUT_TOKEN': env.float('RK_EURO_COST_PER_INPUT_TOKEN', default=5 / 1_000_000),
    'EURO_COST_PER_OUTPUT_TOKEN': env.float(
        'RK_EURO_COST_PER_OUTPUT_TOKEN', default=15 / 1_000_000
    ),
}

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# DATA DIRECTORY
DATA_DIR = Path(env.str('RK_DATA_DIR', default=Path(BASE_DIR).parent / 'data'))
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env.str(
    'RK_SECRET_KEY', default='django-insecure-ofn2$!9q0$50i_=&i%^)9j8e9u)8#cbl=4ig8e-&@%m5z*(ien'
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env.bool('RK_DEBUG', default=True)

ALLOWED_HOSTS = env.list('RK_ALLOWED_HOSTS', default=['*'])

CORS_ALLOWED_ORIGINS = env.list('RK_CORS_ALLOWED_ORIGINS', default=['http://localhost:4200'])

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'core',
    'health',
    'text_search',
    'document_search',
    'user_profile.apps.UserProfileConfig',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'api.wsgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases


DATABASES = {
    'default': {
        'ENGINE': env('RK_DATABASE_ENGINE', default='django.db.backends.sqlite3'),
        # Becomes the file location for sqlite3 when nothing else is set,
        # currently saves into the project root directory.
        'NAME': env('RK_DATABASE_NAME', default=str(Path(BASE_DIR) / 'db.sqlite3')),
        'USER': env('RK_DATABASE_USER', default=''),  # Not used with sqlite3.
        'PASSWORD': env('RK_DATABASE_PASSWORD', default=''),  # Not used with sqlite3.
        'HOST': env('RK_DATABASE_HOST', default=''),
        # Set to empty string for localhost. Not used with sqlite3.
        'PORT': env('RK_DATABASE_PORT', default=''),
        'CONN_MAX_AGE': env.int('RK_DATABASE_CONN_MAX_AGE', default=30),
    }
}

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': ('rest_framework.renderers.JSONRenderer',),
    # Permissions vary a lot and therefore should always be specified.
    # In case a permission is accidentally missing we set the harshest default
    'DEFAULT_PERMISSION_CLASSES': ('rest_framework.permissions.IsAdminUser',),
    # Almost every endpoint uses TokenAuthentication
    'DEFAULT_AUTHENTICATION_CLASSES': ('rest_framework.authentication.TokenAuthentication',),
    'DEFAULT_THROTTLE_CLASSES': ('rest_framework.throttling.AnonRateThrottle',),
    'DEFAULT_THROTTLE_RATES': {'anon': '75/hour'},
}

if DEBUG is True:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = (
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    )

    # TODO: remove once browsable API is no longer needed
    REST_FRAMEWORK['DEFAULT_AUTHENTICATION_CLASSES'] = (
        # For authenticating requests with the Token
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        # For the Browsable API Renderer
        'rest_framework.authentication.SessionAuthentication',
    )

    REST_FRAMEWORK['DEFAULT_THROTTLE_CLASSES'] = []
    REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {}

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGES = (('et', gettext('Estonian')),)

LANGUAGE_CODE = 'et'
TIME_ZONE = env.str('RK_TIME_ZONE', default='Europe/Tallinn')
USE_I18N = True
USE_TZ = True

LOCALE_PATHS = (BASE_DIR / 'locale',)

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# TODO: Added initial configuration for logging, revisit it somewhere in the future.
INFO_LOGGER = 'info_logger'
ERROR_LOGGER = 'error_logger'
LOGGING_SEPARATOR = '-'

LOGS_DIR = env.str('RK_LOGS_DIR', default=DATA_DIR / 'logs')
Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '\n'
            + LOGGING_SEPARATOR.join(
                [
                    '%(levelname)s',
                    '%(module)s',
                    '%(name)s',
                    '%(funcName)s',
                    '%(message)s',
                    '%(asctime)-15s',
                ]
            )
        },
        'detailed': {
            'format': LOGGING_SEPARATOR.join(
                [
                    '%(levelname)s',
                    '%(module)s',
                    'function: %(funcName)s',
                    'line: %(lineno)s',
                    '%(name)s',
                    'PID: %(process)d',
                    'TID: %(thread)d',
                    '%(message)s',
                    '%(asctime)-15s',
                ]
            ),
        },
        'detailed_error': {
            'format': '\n'
            + LOGGING_SEPARATOR.join(
                [
                    '%(levelname)s',
                    '%(module)s',
                    '%(name)s',
                    'PID: %(process)d',
                    'TID: %(thread)d',
                    '%(funcName)s',
                    '%(message)s',
                    '%(asctime)-15s',
                ]
            )
        },
    },
    'handlers': {
        'info_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'detailed',
            'filename': Path(LOGS_DIR) / 'info.log',
            'encoding': 'utf8',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'formatter': 'detailed_error',
            'filename': Path(LOGS_DIR) / 'error.log',
            'encoding': 'utf8',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'loggers': {
        INFO_LOGGER: {
            'level': 'INFO',
            'handlers': ['info_file'],
            'propagate': True,
        },
        ERROR_LOGGER: {
            'level': 'ERROR',
            'handlers': ['console', 'error_file'],
        },
        'elasticsearch': {'level': logging.WARN, 'handles': ['console']},
        # Big parent of all the Django loggers, MOST (not all) of this will get overwritten.
        # https://docs.djangoproject.com/en/2.1/topics/logging/#topic-logging-parts-loggers
        'django': {'handlers': ['console', 'error_file'], 'level': 'ERROR'},
        # Log messages related to the handling of requests.
        # 5XX responses are raised as ERROR messages; 4XX responses are raised as WARNING messages
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
        # Log messages related to the handling of
        # requests received by the server invoked by the runserver command.
        # HTTP 5XX responses are logged as ERROR messages,
        # 4XX responses are logged as WARNING messages,
        # everything else is logged as INFO.
        'django.server': {
            'handlers': ['console', 'error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

#### CELERY CONFIGURATIONS ####

# Whether to run Celery tasks in workers or synchronously in the webserver.
CELERY_TASK_ALWAYS_EAGER = env.bool('RK_CELERY_TASK_ALWAYS_EAGER', default=False)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = env.str('RK_CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = env.str('RK_CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_TIMEZONE = env.str('RK_CELERY_TIMEZONE', default='Europe/Tallinn')
CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_WORKER_PREFETCH_MULTIPLIER = env.int('RK_CELERY_PREFETCH_MULTIPLIER', default=1)
CELERY_DEFAULT_QUEUE = env.str('RK_WORKER_QUEUE', default='celery')
CELERY_DEFAULT_EXCHANGE = CELERY_DEFAULT_QUEUE
CELERY_DEFAULT_ROUTING_KEY = CELERY_DEFAULT_QUEUE

#### VECTORIZATION CONFIGURATIONS ####
VECTORIZATION_MODEL_NAME = 'BAAI/bge-m3'
BGEM3_SYSTEM_CONFIGURATION = {'use_fp16': True, 'device': 'cpu', 'normalize_embeddings': True}
BGEM3_INFERENCE_CONFIGURATION = {'batch_size': 12, 'return_dense': True, 'max_length': 8192}

# DOWNLOAD MODEL DEPENDENCIES

DOWNLOAD_RESOURCES = env('RK_DOWNLOAD_DATA', default=True)

if DOWNLOAD_RESOURCES:
    download_vectorization_resources(VECTORIZATION_MODEL_NAME, DATA_DIR)

#### EMAIL CONFIGURATION ####

EMAIL_HOST = env('RK_EMAIL_HOST', default='localhost')
EMAIL_PORT = env.int('RK_EMAIL_PORT', default=25)
EMAIL_HOST_USER = env('RK_EMAIL_HOST_USER', default='')
EMAIL_DISPLAY_NAME = env.str('RK_DISPLAY_NAME', default='Riigikantselei semantiline otsing')
EMAIL_HOST_PASSWORD = env('RK_EMAIL_HOST_PASSWORD', default='')
EMAIL_TIMEOUT = env.int('RK_EMAIL_TIMEOUT_IN_SECONDS', default=5)  # in seconds.
EMAIL_USE_TLS = env.bool('RK_EMAIL_USE_TLS', default=False)
EMAIL_USE_SSL = env.bool('RK_EMAIL_USE_SSL', default=False)
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

#### OTHER ####

SERVICE_NAME = 'Riigikantselei semantiline tekstiotsing'
BASE_URL = env('RK_BASE_URL', default='http://localhost')
