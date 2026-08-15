from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from cloudinary.models import CloudinaryField

from core.shared import BaseModel


class SizeType(models.TextChoices):
    S = 's', 'S'
    M = 'm', 'M'
    L = 'l', 'L'
    XL = 'xl', 'XL'
    NOSIZE = 'nosize', 'No Size'


class Unit(models.TextChoices):
    G = 'g', 'g'
    KG = 'kg', 'kg'
    ML = 'ml', 'ml'
    L = 'l', 'l'
    PIECE = 'piece', 'piece'


class Category(BaseModel):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = 'Categories'  # Bắt buộc giữ để tránh lỗi "Categorys"


    def __str__(self):
        return self.name


class Dish(BaseModel):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='dishes')
    name = models.CharField(max_length=255)
    size_type = models.CharField(max_length=20, choices=SizeType.choices)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    description = models.TextField(null=True, blank=True)
    image = CloudinaryField('image', null=True, blank=True)
    is_available = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'Dishes'  # Bắt buộc giữ để tránh lỗi "Dishs"
        # BỔ SUNG TỪ FILE LOGIC: Chặn việc tạo trùng size của cùng 1 tên món ăn
        unique_together = ('name', 'size_type')

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.lower()
        if self.size_type:
            self.size_type = self.size_type.lower()
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.name} ({self.size_type})"


class Ingredient(BaseModel):
    name = models.CharField(max_length=255, unique=True)
    unit = models.CharField(max_length=20, choices=Unit.choices)

    # ĐÃ XÓA class Meta vì Django tự sinh ra "Ingredients" chuẩn ngữ pháp

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.lower()
        super().save(*args, **kwargs)


    def __str__(self):
        return self.name


class RecipeItem(BaseModel):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='recipe_items')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='recipe_items')
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )

    class Meta:
        # DB Enforce: 1 món ăn không được add cùng 1 nguyên liệu 2 lần
        unique_together = ('dish', 'ingredient')


    def __str__(self):
        return f"{self.dish.name} - {self.quantity} {self.ingredient.unit} {self.ingredient.name}"