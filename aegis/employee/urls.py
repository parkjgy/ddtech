from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

urlpatterns = [
    # url(r'^api', include(router.urls)),
    # url(r'^swagger', schema_view),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # url(r'^api-auth', include('router.urls')),
    # url(r'^beacon_test_d3$', views.beaconTestD3, name = 'beaconTestD3'),
    url(r'employee/table_reset_and_clear_for_operation$', views.table_reset_and_clear_for_operation, name='table_reset_and_clear_for_operation'),
    url(r'employee/check_version$', views.check_version, name='check_version'),
    url(r'employee/reg_employee_for_customer$', views.reg_employee_for_customer, name='reg_employee_for_customer'),
    url(r'employee/update_work_for_customer$', views.update_work_for_customer, name='update_work_for_customer'),
    url(r'employee/notification_list$', views.notification_list, name='notification_list'),
    url(r'employee/notification_accept$', views.notification_accept, name='notification_accept'),

    url(r'employee/passer_list$', views.passer_list, name='passer_list'),

    url(r'employee/passer_reg$', views.passer_reg, name='passer_reg'),

    url(r'employee/pass_reg$', views.pass_reg, name='pass_reg'),
    url(r'employee/pass_verify$', views.pass_verify, name='pass_verify'),
    url(r'employee/pass_sms$', views.pass_sms, name='pass_sms'),

    # 비콘 상테 전송 API 이름 변경
    # url(r'employee/beacon_verify$', views.beacons_is, name='beacons_is'),
    url(r'employee/beacons_is$', views.beacons_is, name='beacons_is'),

    # old 등록 api
    # url(r'employee/reg_employee$', views.certification_no_to_sms, name='certification_no_to_sms'),
    # url(r'employee/verify_employee$', views.reg_from_certification_no, name='reg_from_certification_no'),
    # url(r'employee/exchange_info$', views.update_my_info, name='update_my_info'),
    # url(r'employee/work_list$', views.my_work_histories, name='my_work_histories'),
    # new 등록 api
    url(r'employee/certification_no_to_sms$', views.certification_no_to_sms, name='certification_no_to_sms'),
    url(r'employee/reg_from_certification_no$', views.reg_from_certification_no, name='reg_from_certification_no'),
    url(r'employee/update_my_info$', views.update_my_info, name='update_my_info'),
    url(r'employee/pass_record_of_employees_in_day_for_customer$', views.pass_record_of_employees_in_day_for_customer, name='pass_record_of_employees_in_day_for_customer'),
    url(r'employee/change_work_period_for_customer$', views.change_work_period_for_customer, name='change_work_period_for_customer'),
    url(r'employee/employee_day_working_from_customer$', views.employee_day_working_from_customer, name='employee_day_working_from_customer'),
    url(r'employee/my_work_histories$', views.my_work_histories, name='my_work_histories'),
    url(r'employee/my_work_histories_for_customer$', views.my_work_histories_for_customer,
        name='my_work_histories_for_customer'),

    url(r'employee/analysys$', views.analysys, name='analysys'),
    url(r'employee/rebuild_pass_history$', views.rebuild_pass_history, name='rebuild_pass_history'),
    url(r'employee/beacon_status$', views.beacon_status, name='beacon_status'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
