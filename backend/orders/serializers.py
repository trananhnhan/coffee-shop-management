from django.db.models import Max
from rest_framework import serializers
from django.db import transaction
from django.utils.timezone import now

from accounts.models import Branch
from notifications.utils import broadcast_ws_event
from .models import Order, OrderItem, OrderStatus, OrderType, PaymentStatus, KitchenStatus
from menu.models import Dish



# ----------ORDER ITEM--------

class OrderItemSerializer(serializers.ModelSerializer):
    dish_name = serializers.CharField(source='dish.name', read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'dish', 'dish_name', 'quantity', 'unit_price_snapshot', 'note', 'kitchen_status']
        read_only_fields = ['unit_price_snapshot', 'kitchen_status']


class OrderItemCreateInputSerializer(serializers.Serializer):
    """Dùng để hứng data mảng items truyền lên khi tạo Order"""
    dish = serializers.PrimaryKeyRelatedField(
        queryset=Dish.objects.filter(is_active=True, is_available=True),
        error_messages={'does_not_exist': 'Dish does not exist or is currently unavailable.'}
    )
    quantity = serializers.IntegerField(min_value=1)
    note = serializers.CharField(required=False, allow_blank=True, max_length=500)



# ---------ORDER---------


class ListOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['id', 'branch', 'cashier', 'status', 'order_type', 'table_number', 'queue_number', 'payment_status',
                  'total_price_snapshot', 'created_at']


class RetrieveOrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'branch', 'cashier', 'status', 'order_type', 'table_number', 'queue_number', 'payment_method',
                  'payment_status', 'total_price_snapshot', 'items', 'created_at', 'updated_at']


class CreateOrderSerializer(serializers.ModelSerializer):
    items = OrderItemCreateInputSerializer(many=True, write_only=True)

    class Meta:
        model = Order
        fields = ['id', 'order_type', 'table_number', 'payment_method', 'items']

    def validate(self, data):
        order_type = data.get('order_type')
        table_number = data.get('table_number')
        branch = self.context['request'].user.branch

        if order_type == OrderType.DINE_IN:
            if not table_number:
                raise serializers.ValidationError({"detail": "Table number is required for dine-in orders."})
            if table_number > branch.table_capacity:
                raise serializers.ValidationError(
                    {"detail": f"Table number exceeds branch capacity ({branch.table_capacity})."})

        elif order_type == OrderType.TAKEAWAY:
            if table_number is not None:
                raise serializers.ValidationError({"detail": "Table number must be null for takeaway orders."})

        if not data.get('items'):
            raise serializers.ValidationError({"detail": "Order must have at least one item."})

        return data

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context['request'].user
        branch = user.branch

        # Gán tự động các field cố định
        validated_data['branch'] = branch
        validated_data['cashier'] = user
        validated_data['status'] = OrderStatus.PENDING
        validated_data['payment_status'] = PaymentStatus.UNPAID

        # Đẩy TOÀN BỘ logic vào trong transaction
        with transaction.atomic():
            # 1. DB LOCK: Khóa record Branch này lại (Chống Race Condition)
            Branch.objects.select_for_update().get(id=branch.id)

            # 2. Sinh queue_number cho Takeaway SAU KHI ĐÃ LOCK
            if validated_data['order_type'] == OrderType.TAKEAWAY:
                today = now().date()
                max_queue = Order.objects.filter(
                    branch=branch,
                    order_type=OrderType.TAKEAWAY,
                    created_at__date=today
                ).aggregate(max_num=Max('queue_number'))['max_num']

                validated_data['queue_number'] = (max_queue or 0) + 1

            # 3. Tính tổng tiền từ snapshot của Dish
            total_price = sum((item['dish'].price * item['quantity']) for item in items_data)
            validated_data['total_price_snapshot'] = total_price

            # 4. TẠO ORDER (Làm thủ công hoàn toàn, KHÔNG dùng super().create nữa)
            order = Order.objects.create(**validated_data)

            # 5. Tạo OrderItems
            order_items = [
                OrderItem(
                    order=order,
                    dish=item['dish'],
                    quantity=item['quantity'],
                    unit_price_snapshot=item['dish'].price,
                    note=item.get('note', '')
                ) for item in items_data
            ]
            OrderItem.objects.bulk_create(order_items)
            # 6. TRIGGER WEBSOCKET
            # Bọc try-except để lỡ có lỗi lúc lấy data cũng không làm sập luồng tạo đơn
            try:
                full_order_data = self.to_representation(order)

                # Gắn cò súng: Chỉ kích hoạt GỬI TIN NHẮN khi DB đã commit thành công
                transaction.on_commit(lambda: broadcast_ws_event(
                    branch_id=order.branch.id,
                    event_type="order.created",
                    data=full_order_data
                ))
            except Exception as e:
                # Ghi log lỗi nếu cần, không ném lỗi ra ngoài làm sập quá trình tạo đơn
                print(f"WebSocket Trigger Error: {e}")

        # Trả về order nguyên vẹn (DRF sẽ tự gọi to_representation một lần nữa để trả về cho API)
        return order

    def to_representation(self, instance):
        """
        Ghi đè dữ liệu trả về: Sau khi tạo đơn thành công,
        dùng RetrieveOrderSerializer để trả về full tất cả thông tin
        (bao gồm cả queue_number, items, trạng thái, v.v...)
        """
        return RetrieveOrderSerializer(instance, context=self.context).data

class UpdateKitchenStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['kitchen_status']