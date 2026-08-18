from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from core.pagination import BasicPaginator
from accounts.models import Role
from accounts import permissions as acc_permissions
from notifications.utils import broadcast_ws_event

from .models import Order, OrderItem, OrderStatus, PaymentStatus, KitchenStatus
from . import serializers


class OrderViewSet(viewsets.ModelViewSet):
    pagination_class = BasicPaginator
    http_method_names = ['get', 'post', 'patch']  # Cấm DELETE cứng

    def get_permissions(self):
        if self.action == 'create': return [acc_permissions.IsCashier()]
        if self.action == 'mark_paid': return [acc_permissions.IsCashier()]
        if self.action == 'cancel': return [acc_permissions.IsStoreManagerOrCashier()]
        if self.action == 'update_kitchen_status': return [acc_permissions.IsKitchen()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.role == Role.OWNER:
            return Order.objects.all().order_by('-created_at')
        return Order.objects.filter(branch=user.branch).order_by('-created_at')

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListOrderSerializer
        if self.action == 'retrieve': return serializers.RetrieveOrderSerializer
        if self.action == 'create': return serializers.CreateOrderSerializer
        return serializers.RetrieveOrderSerializer

    @action(detail=True, methods=['patch'], url_path='mark-paid')
    def mark_paid(self, request, pk=None):
        order = self.get_object()
        try:
            order.mark_paid()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.RetrieveOrderSerializer(order).data)

    @action(detail=True, methods=['patch'], url_path='cancel')
    def cancel(self, request, pk=None):
        order = self.get_object()
        try:
            order.cancel()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.RetrieveOrderSerializer(order).data)

    # Khéo léo dùng regex để bắt param item_id trên URL lồng nhau
    @action(detail=True, methods=['patch'], url_path=r'items/(?P<item_id>[^/.]+)/kitchen-status')
    def update_kitchen_status(self, request, pk=None, item_id=None):
        order = self.get_object()

        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Item not found in this order."}, status=status.HTTP_404_NOT_FOUND)

        serializer = serializers.UpdateKitchenStatusSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['kitchen_status']

        try:
            # Giao phó toàn bộ logic nặng nhọc cho Model xử lý
            item.update_kitchen_status(new_status)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Lấy lại order từ DB để có trạng thái mới nhất sau khi Model xử lý
        order.refresh_from_db()
        serializer = serializers.RetrieveOrderSerializer(order)

        # GẮN TRIGGER WEBSOCKET
        transaction.on_commit(lambda: broadcast_ws_event(
            branch_id=order.branch.id,
            event_type="order.updated",
            data=serializer.data
        ))
        return Response(serializers.RetrieveOrderSerializer(order).data)