from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal

from core.shared import BaseModel, TimeStampedModel
from accounts.models import Branch, User


class InventoryUnit(models.TextChoices):
    BAO = 'bao', 'Bao'
    CHAI = 'chai', 'Chai'
    THUNG = 'thung', 'Thùng'
    KG = 'kg', 'Kg'
    LIT = 'lit', 'Lít'
    GOI = 'goi', 'Gói'


class StockRequestStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    DELIVERED = 'delivered', 'Delivered'


class StockItem(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    unit = models.CharField(max_length=20, choices=InventoryUnit.choices)
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"


class InventoryItem(BaseModel):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='inventory_items')
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name='inventory_items')

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    threshold = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.000'))]
    )

    class Meta:
        unique_together = ('branch', 'stock_item')

    @property
    def is_low_stock(self):
        return self.quantity <= self.threshold

    def __str__(self):
        return f"{self.stock_item.name} - {self.branch.name}"


class StockRequest(TimeStampedModel):
    inventory_item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='stock_requests')
    requested_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_requests_created')

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit_price_snapshot = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )

    status = models.CharField(
        max_length=20,
        choices=StockRequestStatus.choices,
        default=StockRequestStatus.PENDING
    )
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_requests_approved', null=True,
                                    blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    def approve(self, approver_user):
        """
        Quản lý duyệt đơn: Đổi trạng thái và đồng bộ giá mới nhất vào bảng StockItem (nếu có thay đổi)
        """
        with transaction.atomic():
            self.status = StockRequestStatus.APPROVED
            self.approved_by = approver_user
            self.approved_at = timezone.now()
            self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

            stock_item = self.inventory_item.stock_item
            if self.unit_price_snapshot is not None and stock_item.unit_price != self.unit_price_snapshot:
                stock_item.unit_price = self.unit_price_snapshot
                stock_item.save(update_fields=['unit_price', 'updated_at'])

    def deliver(self):
        """
        Hàng về tới quán: Chuyển trạng thái và cộng dồn số lượng kho thực tế
        """
        with transaction.atomic():
            self.status = StockRequestStatus.DELIVERED
            self.save(update_fields=['status', 'updated_at'])

            self.inventory_item.quantity += self.quantity
            self.inventory_item.save(update_fields=['quantity', 'updated_at'])

    def reject(self, rejector_user):
        """
        Từ chối đơn lúc Pending: Chỉ đổi trạng thái, không đụng tới kho hay giá
        """
        self.status = StockRequestStatus.REJECTED
        self.approved_by = rejector_user
        self.approved_at = timezone.now()
        self.save(update_fields=['status', 'approved_by', 'approved_at', 'updated_at'])

    def __str__(self):
        return f"Req {self.id} - {self.inventory_item.stock_item.name} ({self.status})"