from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReportViewSet

router = DefaultRouter()

# ĐỔI CHỮ 'reports' THÀNH CHUỖI RỖNG '' Ở ĐÂY
router.register(r'', ReportViewSet, basename='reports')

urlpatterns = [
    path('', include(router.urls)),
]