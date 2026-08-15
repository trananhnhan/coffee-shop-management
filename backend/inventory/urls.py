from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StockItemViewSet, InventoryItemViewSet, StockRequestViewSet

router = DefaultRouter()
router.register(r'stock-items', StockItemViewSet, basename='stock-item')
router.register(r'inventory-items', InventoryItemViewSet, basename='inventory-item')
router.register(r'stock-requests', StockRequestViewSet, basename='stock-request')

urlpatterns = [
    path('', include(router.urls)),
]