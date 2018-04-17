"""
Django settings for bespin project.

Generated by 'django-admin startproject' using Django 1.10.1.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.10/ref/settings/
"""

import os
from bespin.settings_base import *

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('BESPIN_SECRET_KEY')

ALLOWED_HOSTS = [os.getenv('BESPIN_ALLOWED_HOST')]


# Database
# https://docs.djangoproject.com/en/1.10/ref/settings/#databases

DATABASES = {
    'default': {
       'ENGINE': 'django.db.backends.postgresql_psycopg2',
       'NAME': os.getenv('BESPIN_DB_NAME'),
       'USER': os.getenv('BESPIN_DB_USER'),
       'PASSWORD': os.getenv('BESPIN_DB_PASSWORD'),
       'HOST': os.getenv('BESPIN_DB_HOST'),
    }
}

STATIC_ROOT=os.getenv('BESPIN_STATIC_ROOT')

#SECURE_SSL_REDIRECT = True
#SESSION_COOKIE_SECURE = True
#CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
#CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = 'DENY'

DEFAULT_FROM_EMAIL = os.getenv('BESPIN_MAILER_EMAIL')
if os.getenv('BESPIN_MAILER_ADMIN_BCC') is not None:
   BESPIN_MAILER_ADMIN_BCC = os.getenv('BESPIN_MAILER_ADMIN_BCC').split()
else:
   BESPIN_MAILER_ADMIN_BCC = []

# To enable SMTP email, set BESPIN_SMTP_HOST
if os.getenv('BESPIN_SMTP_HOST') is not None:
  EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
  EMAIL_HOST = os.getenv('BESPIN_SMTP_HOST')

REQUIRED_GROUP_MANAGER_GROUP = os.getenv('BESPIN_REQUIRED_GROUPMANAGER_GROUP')
