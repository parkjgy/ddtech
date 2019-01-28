from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    url(r'customer/reg_customer$', views.reg_customer, name='reg_customer'),
    url(r'customer/update_customer$', views.update_customer, name='update_customer'),
    url(r'customer/list_customer$', views.list_customer, name='list_customer'),
    url(r'customer/reg_staff$', views.reg_staff, name='reg_staff'),
    url(r'customer/login$', views.login, name='login'),
    url(r'customer/update_staff$', views.update_staff, name='update_staff'),
    url(r'customer/list_staff$', views.list_staff, name='list_staff'),
    url(r'customer/reg_work_place$', views.reg_work_place, name='reg_work_place'),
    url(r'customer/update_work_place$', views.update_work_place, name='update_work_place'),
    url(r'customer/list_work_place$', views.list_work_place, name='list_work_place'),
    url(r'customer/reg_work$', views.reg_work, name='reg_work'),
    url(r'customer/update_work$', views.update_work, name='update_work'),
    url(r'customer/list_work$', views.list_work, name='list_work'),
    url(r'customer/reg_employee$', views.reg_employee, name='reg_employee'),
    url(r'customer/update_employee$', views.update_employee, name='update_employee'),
    url(r'customer/list_employee$', views.list_employee, name='list_employee'),
    url(r'customer/report$', views.report, name='report'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
