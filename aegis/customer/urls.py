from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    url(r'customer/reg_customer$', views.reg_customer, name='reg_customer'),
    url(r'customer/reg_staff$', views.reg_staff, name='reg_staff'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
