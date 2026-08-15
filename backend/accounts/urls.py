from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BranchViewSet, UserViewSet


router = DefaultRouter()
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'users', UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),
]