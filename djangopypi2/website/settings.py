import os
import sys
import errno
from . import user_settings

def ensure_directory(path):
    try:
        os.makedirs(path)
    except OSError, os_error:
        if os_error.errno != errno.EEXIST:
            raise
    return path

def find_project_root():
    '''Finds the project root, where uploaded packages are kept and where the user
    can save the settings.json file.
    The default is ~/.djangopypi2, but it can be overridden with the DJANGOPYPI2_ROOT
    environment variable.
    '''
    project_root = os.environ.get('DJANGOPYPI2_ROOT', None)
    if project_root is None:
        user = os.environ.get('USER', '')
        project_root = os.path.expanduser('~{user}/.djangopypi2'.format(user=user))
    return ensure_directory(project_root)

PROJECT_ROOT = find_project_root()
USER_SETTINGS = user_settings.load(PROJECT_ROOT)

DEBUG = USER_SETTINGS['DEBUG']
TEMPLATE_DEBUG = DEBUG

ADMINS = USER_SETTINGS['ADMINS']
TIME_ZONE = USER_SETTINGS['TIME_ZONE']
LANGUAGE_CODE = USER_SETTINGS['LANGUAGE_CODE']
ALLOW_VERSION_OVERWRITE = USER_SETTINGS['ALLOW_VERSION_OVERWRITE']

MANAGERS = ADMINS

ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(PROJECT_ROOT, 'db.sqlite3'),
    }
}

SITE_ID = 1

USE_I18N = True
USE_L10N = True
USE_TZ = True

MEDIA_ROOT = ensure_directory(os.path.join(PROJECT_ROOT, 'media'))
MEDIA_URL = USER_SETTINGS['WEB_ROOT'].rstrip('/') + '/media/'

STATIC_ROOT = ensure_directory(os.path.join(PROJECT_ROOT, 'static'))
STATIC_URL = USER_SETTINGS['WEB_ROOT'].rstrip('/') + '/static/'

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
)

SECRET_KEY = 'qf!u&amp;+fb+m4g@z8=#^v4du0)&amp;51z0e@_j+5tyw)w9=f20a6wr*'

TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
#     'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'djangopypi2.website.urls'

WSGI_APPLICATION = 'djangopypi2.website.wsgi.application'

LOGIN_URL = '/accounts/login/'
LOGOUT_URL = '/accounts/logout/'
LOGIN_REDIRECT_URL = '/'

TEMPLATE_CONTEXT_PROCESSORS = [
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.request',
]

WEBSITE_ROOT = os.path.dirname(os.path.realpath(__file__))

TEMPLATE_DIRS = (
    os.path.join(WEBSITE_ROOT, 'templates'),
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'registration',
    'djangopypi2.apps.pypi_ui',
    'djangopypi2.apps.pypi_users',
    'djangopypi2.apps.pypi_manage',
    'djangopypi2.apps.pypi_metadata',
    'djangopypi2.apps.pypi_packages',
    'djangopypi2.apps.pypi_frontend',
)

ACCOUNT_ACTIVATION_DAYS = 7

# Run "python -m smtpd -n -c DebuggingServer localhost:1025" to see the email message
EMAIL_HOST = 'localhost'
EMAIL_PORT = 1025
EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
EMAIL_USE_TLS = False
DEFAULT_FROM_EMAIL = 'sender@example.com'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        }
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    }
}
