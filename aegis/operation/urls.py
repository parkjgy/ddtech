from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    url(r'operation/testEnv$', views.testEnv, name='testEnv'),
    url(r'operation/currentEnv$', views.currentEnv, name='currentEnv'),
    url(r'operation/updateEnv$', views.updateEnv, name='updateEnv'),

    url(r'operation/reg_staff$', views.reg_staff, name='reg_staff'),
    url(r'operation/login$', views.login, name='login'),
    url(r'operation/logout$', views.logout, name='logout'),
    url(r'operation/update_staff$', views.update_staff, name='update_staff'),
    url(r'operation/list_staff$', views.list_staff, name='list_staff'),
    url(r'operation/reg_customer', views.reg_customer, name='reg_customer'),
    url(r'operation/list_customer', views.list_customer, name='list_customer'),

    url(r'operation/update_work_place$', views.update_work_place, name='update_work_place'),
    url(r'operation/update_beacon$', views.update_beacon, name='update_beacon'),
    url(r'operation/list_work_place$', views.list_work_place, name='list_work_place'),
    url(r'operation/list_beacon$', views.list_beacon, name='list_beacon'),
    url(r'operation/detail_beacon$', views.detail_beacon, name='detail_beacon'),
    url(r'operation/dt_android_upgrade', views.dt_android_upgrade, name='dt_android_upgrade'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
