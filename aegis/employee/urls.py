from django.conf.urls import url, include
from django.contrib.auth.models import User
from . import views

from django.conf.urls.static import static
from django.conf import settings

# from .modules.mobile import urls as mobile_urls # 모바일용 화면 분기처리 ( mobile/urls.py, mobile/views.py )
# from .modules.api import urls as api_urls # 모바일용 화면 분기처리 ( mobile/urls.py, mobile/views.py )

##### set swagger

# from rest_framework import routers
from rest_framework import routers, serializers, viewsets
from rest_framework_swagger.views import get_swagger_view

router = routers.DefaultRouter()
# router.register(r'post', <PostViewSet)

schema_view = get_swagger_view(title='근로자 API')


# Serializers define the API representation.
class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ('url', 'username', 'email', 'is_staff')


# ViewSets define the view behavior.
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer


# Routers provide an easy way of automatically determining the URL conf.
# router = routers.DefaultRouter()
# router.register(r'users', UserViewSet)

urlpatterns = [
    # url(r'^api', include(router.urls)),
    # url(r'^swagger', schema_view),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # url(r'^api-auth', include('router.urls')),
    # url(r'^beacon_test_d3$', views.beaconTestD3, name = 'beaconTestD3'),
    url(r'employee/check_version$', views.check_version, name='check_version'),
    url(r'employee/reg_employee_for_customer$', views.reg_employee_for_customer, name='reg_employee_for_customer'),
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
    url(r'employee/my_work_histories$', views.my_work_histories, name='my_work_histories'),

    url(r'employee/analysys$', views.analysys, name='analysys'),
    url(r'employee/rebuild_pass_history$', views.rebuild_pass_history, name='rebuild_pass_history'),
    url(r'employee/beacon_status$', views.beacon_status, name='beacon_status'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
