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
router = routers.DefaultRouter()
router.register(r'users', UserViewSet)

urlpatterns = [
    url(r'^api', include(router.urls)),
    url(r'^swagger', schema_view),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework')),

    # url(r'^api-auth', include('router.urls')),
    # url(r'^beacon_test_d3$', views.beaconTestD3, name = 'beaconTestD3'),
    url(r'test_RSA$', views.test_RSA,  name='test_RSA'),
    url(r'request_AES256$', views.request_AES256, name='request_AES256'),

    url(r'employee/check_version$', views.checkVersion, name = 'checkVersion'),
    url(r'employee/passer_reg$', views.passer_reg, name = 'passer_reg'),

    url(r'employee/pass_reg$', views.pass_reg, name='pass_reg'),
    url(r'employee/pass_verify$', views.pass_verify, name='pass_verify'),
    url(r'employee/reg_employee$', views.reg_employee, name='reg_employee'),
    url(r'employee/verify_employee$', views.verify_employee, name='verify_employee'),
    url(r'employee/work_list$', views.work_list, name='work_list'),
    url(r'employee/exchange_info$', views.exchange_info, name='exchange_info'),
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
