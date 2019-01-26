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
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
