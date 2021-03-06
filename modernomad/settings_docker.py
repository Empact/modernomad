# A sensible set of defaults for a development environment, that can be
# overridden with environment variables

import environ
from django.core.exceptions import ImproperlyConfigured
from .settings import *

env = environ.Env()

# what mode are we running in? use this to trigger different settings.
DEVELOPMENT = 0
PRODUCTION = 1

# default mode is production. change to dev as appropriate.
env_mode = env('MODE', default='DEVELOPMENT')
if env_mode == 'DEVELOPMENT':
    MODE = DEVELOPMENT
    DEBUG = True
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
elif env_mode == 'PRODUCTION':
    MODE = PRODUCTION
else:
    raise ImproperlyConfigured('Unknown MODE setting')

TEMPLATE_DEBUG = DEBUG

SECRET_KEY = env('SECRET_KEY')
DATABASES = {
    'default': env.db(),
}

BROKER_URL = env('BROKER_URL', default='amqp://')
CELERY_RESULT_BACKEND = env('BROKER_URL', default='amqp://')

# this should be a TEST or PRODUCTION key depending on whether this is a local
# test/dev site or production!
STRIPE_SECRET_KEY = env('STRIPE_SECRET_KEY', default='')
STRIPE_PUBLISHABLE_KEY = env('STRIPE_PUBLISHABLE_KEY', default='')

# Discourse discussion group
DISCOURSE_BASE_URL = env('DISCOURSE_BASE_URL', default='')
DISCOURSE_SSO_SECRET = env('DISCOURSE_SSO_SECRET', default='')

MAILGUN_API_KEY = env('MAILGUN_API_KEY', default='')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': env('DJANGO_LOG_LEVEL', default='INFO'),
        },
    },
}
