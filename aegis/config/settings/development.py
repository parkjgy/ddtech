from config.settings.base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True
# DEBUG = False

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
        'USER': 'root',
        'PASSWORD': 'ddTech!!82',
        'HOST': '127.0.0.1',  # Empty for localhost through domain sockets or '127.0.0.1' for localhost through TCP.
        'PORT': '3306',  # Set to empty string for default.
    }
}

CUSTOMER_URL = 'http://127.0.0.1:8000/customer/'
OPERATION_URL = 'http://127.0.0.1:8000/operation/'
EMPLOYEE_URL = 'http://127.0.0.1:8000/employee/'

SMS_SENDER_PN = '1899-3832'

# IS_TEST = True     # 인증번호: 201903 (sms 서버에 문자를 발송을 할 수 없을 때 사용한다.)
IS_TEST = False
IS_SERVICE = False

# APNs 인증서 경로
APNS_PEM_EMPLOYEE_FILE = os.path.join(STATIC_ROOT, 'employee_dev.pem')
APNS_PEM_MANAGER_FILE = os.path.join(STATIC_ROOT, 'mng_dev.pem')
