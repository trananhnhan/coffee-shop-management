from django.contrib import admin
from .models import StockItem, InventoryItem, StockRequest

@admin.register(StockItem)
class StockItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'unit_price', 'is_active')
    list_filter = ('is_active', 'unit')
    search_fields = ('name',)

@admin.register(InventoryItem)
class InventoryItemAdmin(admin.ModelAdmin):
    list_display = ('stock_item', 'branch', 'quantity', 'threshold', 'is_low_stock_display', 'is_active')
    list_filter = ('branch', 'is_active')
    search_fields = ('stock_item__name',)
    readonly_fields = ('id', 'created_at', 'updated_at')

    # Hàm hiển thị icon đỏ cảnh báo nếu hàng tồn dưới ngưỡng
    @admin.display(boolean=True, description='Low Stock')
    def is_low_stock_display(self, obj):
        return obj.is_low_stock

@admin.register(StockRequest)
class StockRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_item_name', 'get_branch', 'requested_by', 'quantity', 'status', 'created_at')
    list_filter = ('status', 'inventory_item__branch', 'created_at')
    search_fields = ('inventory_item__stock_item__name',)
    readonly_fields = ('id', 'created_at', 'updated_at', 'approved_at')

    @admin.display(description='Item Name')
    def get_item_name(self, obj):
        return obj.inventory_item.stock_item.name

    @admin.display(description='Branch')
    def get_branch(self, obj):
        return obj.inventory_item.branch.name