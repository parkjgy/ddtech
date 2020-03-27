"""
Employee urls

Copyright 2019. DaeDuckTech Corp. All rights reserved.
"""
from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

urlpatterns = [
    # url(r'^api', include(router.urls)),
    # url(r'^swagger', schema_view),
    # url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # url(r'^api-auth', include('router.urls')),
    # url(r'^beacon_test_d3$', views.beaconTestD3, name = 'beaconTestD3'),
    url(r'employee/table_reset_and_clear_for_operation$', views.table_reset_and_clear_for_operation, name='table_reset_and_clear_for_operation'),
    url(r'employee/check_version$', views.check_version, name='check_version'),
    url(r'employee/list_my_work$', views.list_my_work, name='list_my_work'),
    url(r'employee/reg_employee_for_customer$', views.reg_employee_for_customer, name='reg_employee_for_customer'),
    url(r'employee/update_work_for_customer$', views.update_work_for_customer, name='update_work_for_customer'),

    url(r'employee/notification_list$', views.notification_list, name='notification_list'),
    url(r'employee/notification_accept$', views.notification_accept, name='notification_accept'),

    url(r'employee/notification_list_v2$', views.notification_list_v2, name='notification_list_v2'),
    url(r'employee/notification_accept_v2$', views.notification_accept_v2, name='notification_accept_v2'),

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
    url(r'employee/reg_from_certification_no_2', views.reg_from_certification_no_2, name='reg_from_certification_no_2'),
    url(r'employee/update_my_info_2', views.update_my_info_2, name='update_my_info_2'),

    url(r'employee/exchange_phone_no_to_sms$', views.exchange_phone_no_to_sms, name='exchange_phone_no_to_sms'),
    url(r'employee/exchange_phone_no_verify$', views.exchange_phone_no_verify, name='exchange_phone_no_verify'),

    url(r'employee/my_work_list$', views.my_work_list, name='my_work_list'),
    url(r'employee/pass_record_of_employees_in_day_for_customer$', views.pass_record_of_employees_in_day_for_customer, name='pass_record_of_employees_in_day_for_customer'),
    url(r'employee/work_record_in_day_for_customer$', views.work_record_in_day_for_customer, name='work_record_in_day_for_customer'),
    url(r'employee/pass_record_of_employees_in_day_for_customer_v2$', views.pass_record_of_employees_in_day_for_customer_v2, name='pass_record_of_employees_in_day_for_customer_v2'),    url(r'employee/change_work_period_for_customer$', views.change_work_period_for_customer, name='change_work_period_for_customer'),
    # url(r'employee/employee_day_working_from_customer$', views.employee_day_working_from_customer, name='employee_day_working_from_customer'),
    url(r'employee/my_work_histories$', views.my_work_histories, name='my_work_histories'),
    # url(r'employee/my_work_records$', views.my_work_records, name='my_work_records'),
    url(r'employee/my_work_records$', views.my_work_histories, name='my_work_histories'),  # 상용 서버에서 사용하기 때문에 임시 방편 2020/01/31 18:20
    url(r'employee/my_work_histories_for_customer$', views.my_work_histories_for_customer, name='my_work_histories_for_customer'),
    url(r'employee/work_report_for_customer$', views.work_report_for_customer, name='work_report_for_customer'),
    url(r'employee/alert_recruiting', views.alert_recruiting, name='alert_recruiting'),

    url(r'employee/my_work_records_v2$', views.my_work_records_v2, name='my_work_records_v2'),

    url(r'employee/analysys$', views.analysys, name='analysys'),
    url(r'employee/rebuild_pass_history$', views.rebuild_pass_history, name='rebuild_pass_history'),
    url(r'employee/beacon_status$', views.beacon_status, name='beacon_status'),
    url(r'employee/tk_employee$', views.tk_employee, name='tk_employee'),
    url(r'employee/tk_pass$', views.tk_pass, name='tk_pass'),
    url(r'employee/tk_passer_list', views.tk_passer_list, name='tk_passer_list'),
    url(r'employee/tk_list_reg_stop', views.tk_list_reg_stop, name='tk_list_reg_stop'),
    url(r'employee/tk_update_rest_time', views.tk_update_rest_time, name='tk_update_rest_time'),
    url(r'employee/tk_passer_work_backup', views.tk_passer_work_backup, name='tk_passer_work_backup'),
    url(r'employee/tk_match_test_for_customer', views.tk_match_test_for_customer, name='tk_match_test_for_customer'),
    url(r'employee/tk_in_out_null_list', views.tk_in_out_null_list, name='tk_in_out_null_list'),
    url(r'employee/tk_patch', views.tk_patch, name='tk_patch'),

    url(r'employee/apns_test', views.apns_test, name='apns_test'),
    url(r'employee/test_beacon_list', views.test_beacon_list, name='test_beacon_list'),
    url(r'employee/get_test_beacon_list', views.get_test_beacon_list, name='get_test_beacon_list'),
    url(r'employee/del_test_beacon_list', views.del_test_beacon_list, name='del_test_beacon_list'),

    url(r'employee/list_employee', views.list_employee, name='list_employee'),
    url(r'employee/update_camera', views.update_camera, name='update_camera'),

    url(r'employee/push_work', views.push_work, name='push_work'),

    # url(r'employee/get_works', views.get_works, name='get_works'),
    url(r'employee/reset_passer', views.reset_passer, name='reset_passer'),
    url(r'employee/temp_test_post', views.temp_test_post, name='temp_test_post'),
    url(r'employee/make_work_io', views.make_work_io, name='make_work_io'),
    url(r'employee/work_remover$', views.work_remover, name='work_remover'),

]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
