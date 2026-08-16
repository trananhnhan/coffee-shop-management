from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.db.models import Q, CheckConstraint
from decimal import Decimal

from core.shared import BaseModel, TimeStampedModel
from accounts.models import Branch, User
from menu.models import Dish


class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    IN_KITCHEN = 'in_kitchen', 'In Kitchen'
    READY = 'ready', 'Ready'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class OrderType(models.TextChoices):
    DINE_IN = 'dine_in', 'Dine In'
    TAKEAWAY = 'takeaway', 'Takeaway'


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    VIETQR = 'vietqr', 'VietQR'


class PaymentStatus(models.TextChoices):
    UNPAID = 'unpaid', 'Unpaid'
    PAID = 'paid', 'Paid'


class KitchenStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    COOKING = 'cooking', 'Cooking'
    DONE = 'done', 'Done'


class Order(TimeStampedModel):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='orders')
    cashier = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders_handled')

    status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)
    order_type = models.CharField(max_length=20, choices=OrderType.choices)

    table_number = models.PositiveIntegerField(null=True, blank=True)
    queue_number = models.PositiveIntegerField(null=True, blank=True)

    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.UNPAID)

    total_price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    class Meta:
        # DB Enforce: Ràng buộc logic null/not null cứng ở DB thay vì chỉ dựa vào API
        constraints = [
            CheckConstraint(
                condition=(
                        (Q(order_type=OrderType.DINE_IN) & Q(table_number__isnull=False) & Q(
                            queue_number__isnull=True)) |
                        (Q(order_type=OrderType.TAKEAWAY) & Q(table_number__isnull=True) & Q(
                            queue_number__isnull=False))
                ),
                name='strict_order_type_fields'
            )
        ]

    def mark_paid(self):
        if self.status != OrderStatus.READY:
            raise ValueError("Order must be READY to be marked as paid.")

        self.payment_status = PaymentStatus.PAID
        self.status = OrderStatus.COMPLETED
        self.save(update_fields=['payment_status', 'status', 'updated_at'])

    def cancel(self):
        if self.status == OrderStatus.COMPLETED:
            raise ValueError("Cannot cancel a completed order.")

        self.status = OrderStatus.CANCELLED
        self.save(update_fields=['status', 'updated_at'])

    def recalculate_status(self):
        """Tự động tính lại trạng thái đơn hàng dựa trên các món ăn"""
        items_statuses = self.items.values_list('kitchen_status', flat=True)

        if all(s == KitchenStatus.PENDING for s in items_statuses):
            new_status = OrderStatus.PENDING
        elif all(s == KitchenStatus.DONE for s in items_statuses):
            new_status = OrderStatus.READY
        else:
            new_status = OrderStatus.IN_KITCHEN

        if self.status != new_status:
            self.status = new_status
            self.save(update_fields=['status', 'updated_at'])
    def __str__(self):
        return f"Order {self.id} - {self.branch.name} ({self.status})"


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    dish = models.ForeignKey(Dish, on_delete=models.PROTECT, related_name='order_items')

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    note = models.TextField(null=True, blank=True)
    kitchen_status = models.CharField(max_length=20, choices=KitchenStatus.choices, default=KitchenStatus.PENDING)

    def update_kitchen_status(self, new_status):
        if self.order.status in [OrderStatus.CANCELLED, OrderStatus.COMPLETED]:
            raise ValueError(f"Cannot update items in a {self.order.status} order.")

        if self.kitchen_status == KitchenStatus.DONE and new_status != KitchenStatus.DONE:
            raise ValueError("Cannot revert status from DONE.")

        with transaction.atomic():
            self.kitchen_status = new_status
            self.save(update_fields=['kitchen_status', 'updated_at'])

            # Yêu cầu đơn hàng cha tự tính toán lại trạng thái của nó
            self.order.recalculate_status()

    def __str__(self):
        return f"{self.quantity}x {self.dish.name} - Order {self.order.id}"