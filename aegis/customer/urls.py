from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    url(r'customer/table_reset_and_clear_for_operation$', views.table_reset_and_clear_for_operation,
        name='table_reset_and_clear_for_operation'),
    url(r'customer/reg_customer_for_operation$', views.reg_customer_for_operation, name='reg_customer_for_operation'),
    url(r'customer/list_customer_for_operation$', views.list_customer_for_operation, name='list_customer_for_operation'),
    url(r'customer/sms_customer_staff_for_operation', views.sms_customer_staff_for_operation, name='sms_customer_staff_for_operation'),

    url(r'customer/update_customer$', views.update_customer, name='update_customer'),

    url(r'customer/reg_relationship$', views.reg_relationship, name='reg_relationship'),
    url(r'customer/list_relationship$', views.list_relationship, name='list_relationship'),
    url(r'customer/detail_relationship$', views.detail_relationship, name='detail_relationship'),
    url(r'customer/update_relationship$', views.update_relationship, name='update_relationship'),

    url(r'customer/reg_staff$', views.reg_staff, name='reg_staff'),
    url(r'customer/login$', views.login, name='login'),
    url(r'customer/logout$', views.logout, name='logout'),
    url(r'customer/update_staff$', views.update_staff, name='update_staff'),
    url(r'customer/list_staff$', views.list_staff, name='list_staff'),

    url(r'customer/reg_work_place$', views.reg_work_place, name='reg_work_place'),
    url(r'customer/update_work_place$', views.update_work_place, name='update_work_place'),
    url(r'customer/list_work_place$', views.list_work_place, name='list_work_place'),

    url(r'customer/reg_work$', views.reg_work, name='reg_work'),
    url(r'customer/update_work$', views.update_work, name='update_work'),
    url(r'customer/list_work_from_work_place$', views.list_work_from_work_place, name='list_work_from_work_place'),
    url(r'customer/list_work$', views.list_work, name='list_work'),

    url(r'customer/reg_employee$', views.reg_employee, name='reg_employee'),
    url(r'customer/employee_work_accept_for_employee$', views.employee_work_accept_for_employee, name='employee_work_accept_for_employee'),
    url(r'customer/update_employee_for_employee$', views.update_employee_for_employee, name='update_employee_for_employee'),
    url(r'customer/update_employee$', views.update_employee, name='update_employee'),
    url(r'customer/list_employee$', views.list_employee, name='list_employee'),

    url(r'customer/report$', views.report, name='report'),
    url(r'customer/report_of_manager$', views.report_of_manager, name='report_of_manager'),
    url(r'customer/report_all$', views.report_all, name='report_all'),
    url(r'customer/report_of_staff$', views.report_of_staff, name='report_of_staff'),
    url(r'customer/report_of_employee$', views.report_of_employee, name='report_of_employee'),

    url(r'customer/staff_version$', views.staff_version, name='staff_version'),
    url(r'customer/staff_fg$', views.staff_fg, name='staff_fg'),

    url(r'customer/staff_employees_at_day$', views.staff_employees_at_day, name='staff_employees_at_day'),
    url(r'customer/staff_employees$', views.staff_employees, name='staff_employees'),

    # url(r'customer/staff_bg$', views.staff_bg, name='staff_bg'),
    url(r'customer/staff_background$', views.staff_background, name='staff_background'),

    url(r'customer/staff_change_time$', views.staff_change_time, name='staff_change_time'),
    url(r'customer/staff_employee_working$', views.staff_employee_working, name='staff_employee_working'),
    # url(r'customer/staff_employees_from_work$', views.staff_employees_from_work, name='staff_employees_from_work'),
    url(r'customer/staff_recognize_employee$', views.staff_recognize_employee, name='staff_recognize_employee'),
    url(r'customer/staff_update_employee$', views.staff_update_employee, name='staff_update_employee'),

    # 이하 사용 보류
    # url(r'customer/staff_update_me$', views.staff_update_me, name='staff_update_me'),
    # url(r'customer/staff_request_certification_no$', views.staff_request_certification_no,
    #     name='staff_request_certification_no'),
    # url(r'customer/staff_verify_certification_no$', views.staff_verify_certification_no,
    #     name='staff_verify_certification_no'),
    # url(r'customer/staff_reg_my_work$', views.staff_reg_my_work, name='staff_reg_my_work'),
    # url(r'customer/staff_update_my_work$', views.staff_update_my_work, name='staff_update_my_work'),
    # url(r'customer/staff_list_my_work$', views.staff_list_my_work, name='staff_list_my_work'),
    # url(r'customer/staff_work_list_employee$', views.staff_work_list_employee, name='staff_work_list_employee'),
    # url(r'customer/staff_work_update_employee$', views.staff_work_update_employee, name='staff_work_update_employee'),
    url(r'customer/ddtech_update_syatem$', views.ddtech_update_syatem, name='ddtech_update_syatem'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
