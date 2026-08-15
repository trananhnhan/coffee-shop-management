from django.db import models
from django.contrib.auth.models import AbstractUser

# Giả định bạn có import BaseModel từ file shared
from core.shared import BaseModel


class Role(models.TextChoices):
    OWNER = 'owner', 'Owner'
    STORE_MANAGER = 'store_manager', 'Store Manager'
    CASHIER = 'cashier', 'Cashier'
    KITCHEN = 'kitchen', 'Kitchen'


class Branch(BaseModel):
    name = models.CharField(max_length=255)
    address = models.CharField(max_length=255)
    phone = models.CharField(max_length=20, null=True, blank=True)
    table_capacity = models.IntegerField()

    class Meta:
        verbose_name_plural = 'Branches'

    def __str__(self):
        return self.name


class User(AbstractUser, BaseModel):
    role = models.CharField(max_length=20, choices=Role.choices)

    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='users'
    )

    def __str__(self):
        return f"{self.username} ({self.role})"