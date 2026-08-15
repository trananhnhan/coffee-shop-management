from django.contrib import admin
from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    # Đơn hàng đã chốt thì không nên cho admin vô sửa bậy giá
    readonly_fields = ('unit_price_snapshot', 'kitchen_status')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'branch', 'order_type', 'status', 'payment_status', 'total_price_snapshot', 'created_at')
    list_filter = ('branch', 'status', 'payment_status', 'order_type', 'created_at')
    search_fields = ('id', 'branch__name', 'cashier__username')
    readonly_fields = ('id', 'total_price_snapshot', 'queue_number', 'created_at', 'updated_at')
    inlines = [OrderItemInline]

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'dish', 'quantity', 'kitchen_status')
    list_filter = ('kitchen_status',)
    search_fields = ('order__id', 'dish__name')