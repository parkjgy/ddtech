from django.conf.urls import url, include
from . import views

from django.conf.urls.static import static
from django.conf import settings

# from .modules.mobile import urls as mobile_urls # 모바일용 화면 분기처리 ( mobile/urls.py, mobile/views.py )
# from .modules.api import urls as api_urls # 모바일용 화면 분기처리 ( mobile/urls.py, mobile/views.py )

urlpatterns = [
    # url(r'^beacon_test_d3$', views.beaconTestD3, name = 'beaconTestD3'),
    url(r'check_version$', views.checkVersion, name = 'checkVersion')
]
# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
# + static(settings.MEDIA_URL, document_root = settings.MEDIA_ROOT)
