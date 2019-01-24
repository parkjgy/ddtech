"""config URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.urls import include
from django.conf.urls import url
from django.conf.urls.static import static

from . import secret
from . import views as confViews

from django.conf import settings

urlpatterns = [
    path('apiView', confViews.api_view),
    path('apiView_beta', confViews.api_view_beta),
    path('admin/', admin.site.urls),
    path('api_apk_upload', confViews.api_apk_upload),  # 업로드 URL
    path('app', confViews.beta_employee_app_download),  # 근로자 앱 다운로드 ( 베타 링크, 의사 결정 필요 )
    path('android_upload', confViews.app_upload_view),  # 근로자 앱 업로드
    # path('employee/', include('employee.urls')),

    url(r'', include('employee.urls')),
    url(r'', include('operation.urls')),
    url(r'', include('customer.urls')),

    url(r'testEncryptionStr', secret.testEncryptionStr, name='testEncryptionStr'),
    url(r'testDecryptionStr', secret.testDecryptionStr, name='testDecryptionStr'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
