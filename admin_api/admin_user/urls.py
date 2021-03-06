from django.conf.urls import include, url
from rest_framework.routers import DefaultRouter
from rest_framework_jwt.views import ObtainJSONWebToken

from .views import AdminUserView, InstrumentViewSet, OrdersViewSet

router = DefaultRouter()
router.register(r'instruments', InstrumentViewSet)
router.register(r'orders', OrdersViewSet)

urlpatterns = [
    url('api-token-auth/', ObtainJSONWebToken.as_view(), name='login'),
    url(r'user-info/', AdminUserView.as_view()),
    url('^', include(router.urls))
]
