from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from core.pagination import BasicPaginator
from accounts.models import Role
from accounts import permissions as acc_permissions

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

        if order.status != OrderStatus.READY:
            return Response({"detail": "Order must be READY to be marked as paid."}, status=status.HTTP_400_BAD_REQUEST)

        order.payment_status = PaymentStatus.PAID
        order.status = OrderStatus.COMPLETED
        order.save(update_fields=['payment_status', 'status', 'updated_at'])

        return Response(serializers.RetrieveOrderSerializer(order).data)

    @action(detail=True, methods=['patch'], url_path='cancel')
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.status == OrderStatus.COMPLETED:
            return Response({"detail": "Cannot cancel a completed order."}, status=status.HTTP_400_BAD_REQUEST)

        order.status = OrderStatus.CANCELLED
        order.save(update_fields=['status', 'updated_at'])

        return Response(serializers.RetrieveOrderSerializer(order).data)

    # Khéo léo dùng regex để bắt param item_id trên URL lồng nhau
    @action(detail=True, methods=['patch'], url_path=r'items/(?P<item_id>[^/.]+)/kitchen-status')
    def update_kitchen_status(self, request, pk=None, item_id=None):
        order = self.get_object()

        # Ngăn chặn bếp update khi đơn đã bị hủy hoặc hoàn thành
        if order.status in [OrderStatus.CANCELLED, OrderStatus.COMPLETED]:
            return Response({"detail": f"Cannot update items in a {order.status} order."},
                            status=status.HTTP_400_BAD_REQUEST)

        try:
            item = order.items.get(id=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Item not found in this order."}, status=status.HTTP_404_NOT_FOUND)

        serializer = serializers.UpdateKitchenStatusSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        new_status = serializer.validated_data['kitchen_status']

        # Chặn đi lùi trạng thái (ví dụ Done lùi về Cooking)
        if item.kitchen_status == KitchenStatus.DONE and new_status != KitchenStatus.DONE:
            return Response({"detail": "Cannot revert status from DONE."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Cập nhật status của Item
            item.kitchen_status = new_status
            item.save(update_fields=['kitchen_status', 'updated_at'])

            # Đọc lại toàn bộ Item để đánh giá Status của Order cha
            items_statuses = order.items.values_list('kitchen_status', flat=True)

            if all(s == KitchenStatus.PENDING for s in items_statuses):
                new_order_status = OrderStatus.PENDING
            elif all(s == KitchenStatus.DONE for s in items_statuses):
                new_order_status = OrderStatus.READY
            else:
                new_order_status = OrderStatus.IN_KITCHEN

            # Chỉ save Order nếu có sự thay đổi
            if order.status != new_order_status:
                order.status = new_order_status
                order.save(update_fields=['status', 'updated_at'])

        return Response(serializers.RetrieveOrderSerializer(order).data)