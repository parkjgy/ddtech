"""
Operation urls

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

# from operation import views
# from operation.views import OperationView

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    url(r'operation/logControl$', views.logControl, name='logControl'),

    url(r'operation/testEnv$', views.testEnv, name='testEnv'),
    url(r'operation/currentEnv$', views.currentEnv, name='currentEnv'),
    url(r'operation/updateEnv$', views.updateEnv, name='updateEnv'),

    # url(r'operation/reg_staff$', OperationView.reg_staff, name='reg_staff'),
    url(r'operation/reg_staff$', views.reg_staff, name='reg_staff'),
    url(r'operation/check_version', views.check_version, name='check_version'),
    url(r'operation/login$', views.login, name='login'),
    url(r'operation/logout$', views.logout, name='logout'),
    url(r'operation/update_staff$', views.update_staff, name='update_staff'),
    url(r'operation/list_staff$', views.list_staff, name='list_staff'),

    url(r'operation/reg_customer', views.reg_customer, name='reg_customer'),
    url(r'operation/list_customer', views.list_customer, name='list_customer'),
    url(r'operation/sms_customer_staff', views.sms_customer_staff, name='sms_customer_staff'),

    url(r'operation/update_work_place$', views.update_work_place, name='update_work_place'),
    url(r'operation/update_beacon$', views.update_beacon, name='update_beacon'),
    url(r'operation/list_work_place$', views.list_work_place, name='list_work_place'),
    url(r'operation/list_beacon$', views.list_beacon, name='list_beacon'),
    url(r'operation/detail_beacon$', views.detail_beacon, name='detail_beacon'),
    url(r'operation/dt_android_upgrade', views.dt_android_upgrade, name='dt_android_upgrade'),
    url(r'operation/dt_upgrade', views.dt_upgrade, name='dt_upgrade'),

    url(r'operation/customer_test_step_1', views.customer_test_step_1, name='customer_test_step_1'),
    url(r'operation/customer_test_step_2', views.customer_test_step_2, name='customer_test_step_2'),
    url(r'operation/customer_test_step_3', views.customer_test_step_3, name='customer_test_step_3'),
    url(r'operation/customer_test_step_4', views.customer_test_step_4, name='customer_test_step_4'),
    url(r'operation/customer_test_step_5', views.customer_test_step_5, name='customer_test_step_5'),
    url(r'operation/customer_test_step_6', views.customer_test_step_6, name='customer_test_step_6'),
    url(r'operation/customer_test_step_7', views.customer_test_step_7, name='customer_test_step_7'),
    url(r'operation/customer_test_step_8', views.customer_test_step_8, name='customer_test_step_8'),
    url(r'operation/customer_test_step_9', views.customer_test_step_9, name='customer_test_step_9'),
    url(r'operation/customer_test_step_A', views.customer_test_step_A, name='customer_test_step_A'),

    url(r'operation/employee_test_step_1', views.employee_test_step_1, name='employee_test_step_1'),
    url(r'operation/employee_test_step_2', views.employee_test_step_2, name='employee_test_step_2'),
    url(r'operation/employee_test_step_3', views.employee_test_step_3, name='employee_test_step_3'),
    url(r'operation/employee_test_step_4', views.employee_test_step_4, name='employee_test_step_4'),
    url(r'operation/employee_test_step_5', views.employee_test_step_5, name='employee_test_step_5'),

    url(r'operation/employee_test_step_A', views.employee_test_step_A, name='employee_test_step_A'),
    url(r'operation/employee_test_step_B', views.employee_test_step_B, name='employee_test_step_B'),

    url(r'operation/sms_install_mng', views.sms_install_mng, name='sms_install_mng'),

    url(r'operation/employee_beacon_step_1', views.employee_beacon_step_1, name='employee_beacon_step_1'),
    url(r'operation/test_go_go', views.test_go_go, name='test_go_go'),
    url(r'operation/fjfjieie', views.fjfjieie, name='fjfjieie'),

    url(r'operation/tk_employee', views.tk_employee, name='tk_employee'),
    url(r'operation/tk_in_out_null_list', views.tk_in_out_null_list, name='tk_in_out_null_list'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
