from config.settings.base import *

# SECURITY WARNING: don't run with debug turned on in production!
# DEBUG = True
DEBUG = False

# Database
# https://docs.djangoproject.com/en/2.1/ref/settings/#databases

DATABASES = {
    'default': {
        #     'ENGINE': 'django.db.backends.sqlite3',
        #     'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        # }
        'ENGINE': 'django.db.backends.mysql',  # Add 'postgresql_psycopg2', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': 'aegis',  # Or path to database file if using sqlite3.
        # The following settings are not used with sqlite3:
        'USER': 'ddtech',
        'PASSWORD': 'ddTech!!82',
        'HOST': 'aegisdbinstance.cpa3beafxpw7.ap-northeast-2.rds.amazonaws.com',
        # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '3306',  # Set to empty string for default.
    }
}

CUSTOMER_URL = 'https://api.ezchek.co.kr/customer/'
OPERATION_URL = 'https://api.ezchek.co.kr/operation/'
EMPLOYEE_URL = 'https://api.ezchek.co.kr/employee/'

SMS_SENDER_PN = '1899-3832'

IS_TEST = False
IS_SERVICE = True

# APNs 인증서 경로
APNS_PEM_EMPLOYEE_FILE = os.path.join(STATIC_ROOT, 'employee_pro.pem')
APNS_PEM_MANAGER_FILE = os.path.join(STATIC_ROOT, 'mng_pro.pem')
