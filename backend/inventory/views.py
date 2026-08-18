from django.db import transaction
from django.db.models import F
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.pagination import BasicPaginator
from core.shared import ActivatableViewSetMixin
from accounts.models import Role
from accounts import permissions as acc_permissions
from notifications.utils import broadcast_ws_event

from .models import StockItem, InventoryItem, StockRequest, StockRequestStatus
from . import serializers


class StockItemViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):

    pagination_class = BasicPaginator
    http_method_names = ['get', 'post', 'patch']

    def get_permissions(self):
        if self.action in ['create', 'activate', 'deactivate']:
            return [acc_permissions.IsOwner()]
        return [acc_permissions.IsOwnerOrStoreManager()]

    def get_queryset(self):
        user = self.request.user
        qs = StockItem.objects.all()

        if user.role == Role.OWNER:
            # Owner được phép lọc để xem danh mục đã bị vô hiệu hóa
            is_active_param = self.request.query_params.get('is_active')
            if is_active_param == 'true':
                qs = qs.filter(is_active=True)
            elif is_active_param == 'false':
                qs = qs.filter(is_active=False)
            return qs

        # Store Manager chỉ được phép thấy danh mục đang hoạt động
        return qs.filter(is_active=True)

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListStockItemSerializer
        if self.action == 'retrieve': return serializers.RetrieveStockItemSerializer
        if self.action == 'create': return serializers.CreateStockItemSerializer
        if self.action == 'partial_update': return serializers.PartialUpdateStockItemSerializer
        return serializers.RetrieveStockItemSerializer


class InventoryItemViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    pagination_class = BasicPaginator
    http_method_names = ['get', 'patch']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']: return [IsAuthenticated()]
        if self.action == 'partial_update': return [acc_permissions.IsStoreManagerOrKitchen()]
        if self.action in ['activate', 'deactivate']: return [
            acc_permissions.IsOwner()]  # Chỉ owner được quyền bật/tắt item trong kho
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if user.role == Role.OWNER:
            qs = InventoryItem.objects.all()
            is_active_param = self.request.query_params.get('is_active')

            if is_active_param == 'true':
                qs = qs.filter(is_active=True)
            elif is_active_param == 'false':
                qs = qs.filter(is_active=False)
            return qs

        return InventoryItem.objects.filter(branch=user.branch, is_active=True)

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListInventoryItemSerializer
        if self.action == 'retrieve': return serializers.RetrieveInventoryItemSerializer
        if self.action == 'partial_update': return serializers.PartialUpdateInventoryItemSerializer
        return serializers.RetrieveInventoryItemSerializer

    @action(detail=False, methods=['get'], url_path='low-stock')
    def low_stock(self, request):
        """
        API dành cho Frontend gọi 1 lần khi vừa mở app (F5).
        Trả về danh sách các nguyên liệu đang cạn kiệt của chi nhánh.
        """
        user = request.user

        # Chỉ lấy hàng của chi nhánh user đang làm việc (hoặc tất cả nếu là Owner)
        qs = self.get_queryset()

        # Dùng F object của Django để so sánh 2 cột trong cùng 1 dòng DB cực nhanh
        # Lọc ra những món có quantity <= threshold
        low_stock_items = qs.filter(quantity__lte=F('threshold'))

        # Phân trang hoặc Serialize trả về
        page = self.paginate_queryset(low_stock_items)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(low_stock_items, many=True)

        # Kèm thêm một cờ `has_low_stock` để FE dễ làm biểu tượng ❗️
        return Response({
            "has_low_stock": len(serializer.data) > 0,
            "items": serializer.data
        })

class StockRequestViewSet(viewsets.ModelViewSet):

    pagination_class = BasicPaginator
    http_method_names = ['get', 'post', 'patch']

    def get_permissions(self):
        if self.action == 'create': return [acc_permissions.IsBranchStaff()]
        if self.action in ['approve', 'reject']: return [acc_permissions.IsStoreManager()]
        if self.action == 'deliver': return [acc_permissions.IsBranchStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user

        if user.role == Role.OWNER:
            return StockRequest.objects.all()

        return StockRequest.objects.filter(inventory_item__branch=user.branch)

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListStockRequestSerializer
        if self.action == 'retrieve': return serializers.RetrieveStockRequestSerializer
        if self.action == 'create': return serializers.CreateStockRequestSerializer
        if self.action == 'approve': return serializers.ApproveStockRequestSerializer
        return serializers.RetrieveStockRequestSerializer

    @action(detail=True, methods=['patch'])
    def approve(self, request, pk=None):
        req_obj = self.get_object()

        # Lấy giá trị unit_price_snapshot từ serializer nếu có truyền lên
        serializer = self.get_serializer(req_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        final_price = serializer.validated_data.get('unit_price_snapshot', None)

        try:
            req_obj.approve(approver_user=request.user, final_unit_price=final_price)

            # Đã sửa stock_request thành req_obj
            transaction.on_commit(lambda: broadcast_ws_event(
                branch_id=req_obj.inventory_item.branch.id,
                event_type="inventory.request_approved",
                data={
                    "request_id": str(req_obj.id),
                    "item_name": req_obj.inventory_item.stock_item.name,
                    "status": req_obj.status,
                    "approved_by": request.user.username
                }
            ))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.RetrieveStockRequestSerializer(req_obj).data)

    @action(detail=True, methods=['patch'])
    def reject(self, request, pk=None):
        req_obj = self.get_object()

        try:
            req_obj.reject(rejector_user=request.user)

            # Đã sửa stock_request thành req_obj
            transaction.on_commit(lambda: broadcast_ws_event(
                branch_id=req_obj.inventory_item.branch.id,
                event_type="inventory.request_rejected",
                data={
                    "request_id": str(req_obj.id),
                    "item_name": req_obj.inventory_item.stock_item.name,
                    "status": req_obj.status,
                    "rejected_by": request.user.username
                }
            ))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.RetrieveStockRequestSerializer(req_obj).data)

    @action(detail=True, methods=['patch'])
    def deliver(self, request, pk=None):
        req_obj = self.get_object()

        try:
            req_obj.deliver()

            # Bổ sung thông báo Deliver để Bếp biết hàng đã về kho
            transaction.on_commit(lambda: broadcast_ws_event(
                branch_id=req_obj.inventory_item.branch.id,
                event_type="inventory.request_delivered",
                data={
                    "request_id": str(req_obj.id),
                    "item_name": req_obj.inventory_item.stock_item.name,
                    "status": req_obj.status
                }
            ))
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(serializers.RetrieveStockRequestSerializer(req_obj).data)