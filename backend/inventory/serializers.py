from rest_framework import serializers
from accounts.models import Role
from .models import StockItem, InventoryItem, StockRequest, StockRequestStatus


# ==========================================
# STOCK ITEM
# ==========================================
class ListStockItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = ['id', 'name', 'unit', 'unit_price', 'is_active']
        read_only_fields = fields


class RetrieveStockItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = ['id', 'name', 'unit', 'unit_price', 'is_active', 'created_at', 'updated_at']
        read_only_fields = fields


class CreateStockItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockItem
        fields = ['id', 'name', 'unit', 'unit_price']


# ==========================================
# INVENTORY ITEM
# ==========================================
class ListInventoryItemSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source='stock_item.name', read_only=True)
    unit = serializers.CharField(source='stock_item.unit', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = ['id', 'branch', 'stock_item', 'stock_item_name', 'unit', 'quantity', 'threshold', 'is_low_stock']
        read_only_fields = fields


class RetrieveInventoryItemSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source='stock_item.name', read_only=True)
    unit = serializers.CharField(source='stock_item.unit', read_only=True)
    is_low_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = InventoryItem
        fields = ['id', 'branch', 'stock_item', 'stock_item_name', 'unit', 'quantity', 'threshold', 'is_low_stock',
                  'created_at', 'updated_at']
        read_only_fields = fields


class PartialUpdateInventoryItemSerializer(serializers.ModelSerializer):
    """Chỉ cho phép nhân viên sửa đúng trường quantity khi kiểm kho thực tế"""

    class Meta:
        model = InventoryItem
        fields = ['quantity']


# ==========================================
# STOCK REQUEST
# ==========================================
class ListStockRequestSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source='inventory_item.stock_item.name', read_only=True)

    class Meta:
        model = StockRequest
        fields = ['id', 'inventory_item', 'stock_item_name', 'requested_by', 'quantity', 'status']
        read_only_fields = fields


class RetrieveStockRequestSerializer(serializers.ModelSerializer):
    stock_item_name = serializers.CharField(source='inventory_item.stock_item.name', read_only=True)

    class Meta:
        model = StockRequest
        fields = ['id', 'inventory_item', 'stock_item_name', 'requested_by', 'quantity', 'unit_price_snapshot',
                  'status', 'approved_by', 'approved_at', 'created_at']
        read_only_fields = fields


class CreateStockRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockRequest
        fields = ['id', 'inventory_item', 'quantity']

    def validate(self, data):
        request_user = self.context['request'].user
        inventory_item = data.get('inventory_item')

        # Đảm bảo nhân viên chỉ được tạo yêu cầu cho kho của chi nhánh mình
        if inventory_item.branch != request_user.branch:
            raise serializers.ValidationError({"detail": "You can only request stock for your own branch."})
        return data

    def create(self, validated_data):
        inventory_item = validated_data['inventory_item']

        # Logic tự động: Copy giá hiện tại từ StockItem vào snapshot
        validated_data['unit_price_snapshot'] = inventory_item.stock_item.unit_price

        # Tự động gán người yêu cầu
        validated_data['requested_by'] = self.context['request'].user
        return super().create(validated_data)


class ApproveStockRequestSerializer(serializers.ModelSerializer):
    """Serializer dùng riêng cho API duyệt đơn, chỉ cho phép truyền unit_price_snapshot mới nếu cần chốt giá"""

    class Meta:
        model = StockRequest
        fields = ['unit_price_snapshot']