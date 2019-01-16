from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    # url(r'employee/check_version$', views.checkVersion, name = 'checkVersion'),
    # url(r'employee/passer_reg$', views.passer_reg, name = 'passer_reg'),
    #
    # url(r'employee/pass_reg$', views.pass_reg, name='pass_reg'),
    # url(r'employee/pass_verify$', views.pass_verify, name='pass_verify'),
    # url(r'employee/reg_employee$', views.reg_employee, name='reg_employee'),
    # url(r'employee/verify_employee$', views.verify_employee, name='verify_employee'),
    # url(r'employee/work_list$', views.work_list, name='work_list'),
    # url(r'employee/exchange_info$', views.exchange_info, name='exchange_info'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
