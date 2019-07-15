"""
Main urls

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
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
from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include
from django.urls import path
from rest_framework_swagger.views import get_swagger_view

from . import common
from . import views as confViews

urlpatterns = [
    url(r'^swagger-ui', get_swagger_view(title='Rest API Document')),
    path('rq/apiView', confViews.api_view),
    path('rq/admin/', admin.site.urls),
    path('rq/api_apk_upload', confViews.api_apk_upload),  # 업로드 URL
    path('rq/app', confViews.beta_employee_app_download),  # 근로자 앱 다운로드 ( 베타 링크, 의사 결정 필요 )
    path('rq/apm', confViews.beta_manager_app_download),  # 관리자 앱 다운로드 ( 베타 링크, 의사 결정 필요 )
    path('rq/tncp', confViews.tnc_privacy),  # 개인정보 보호 약관
    path('rq/privacy_policy', confViews.privacy_policy),  # 개인정보 처리방침
    path('rq/android_upload', confViews.app_upload_view),  # 근로자 앱 업로드
    # path('employee/', include('employee.urls')),

    url(r'', include('employee.urls')),

    url(r'', include('operation.urls')),
    url(r'', include('customer.urls')),

    url(r'rq/encrypt', common.encryption, name='encryption'),
    url(r'rq/decrypt', common.decryption, name='decryption'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
