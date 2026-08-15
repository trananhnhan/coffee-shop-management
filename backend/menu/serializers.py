from rest_framework import serializers
from django.db import transaction
from core.shared import CloudinaryImageMixin  # Nhớ import mixin của bạn
from .models import Category, Dish, Ingredient, RecipeItem, SizeType



# -------CATEGORY---------


class ListCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'is_active']


class RetrieveCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'is_active', 'created_at', 'updated_at']


class CreateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name']


class PartialUpdateCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['name']



# ----------INGREDIENT-------------


class ListIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'unit', 'is_active']


class RetrieveIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'unit', 'is_active', 'created_at', 'updated_at']


class CreateIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'unit']


class PartialUpdateIngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['name', 'unit']



# ---------------DISH-----------

class DishSizeInputSerializer(serializers.Serializer):
    size_type = serializers.ChoiceField(choices=SizeType.choices)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class ListDishSerializer(CloudinaryImageMixin, serializers.ModelSerializer):
    cloudinary_fields = ['image']

    class Meta:
        model = Dish
        fields = ['id', 'category', 'name', 'size_type', 'price', 'image', 'is_available', 'is_active']


class RetrieveDishSerializer(CloudinaryImageMixin, serializers.ModelSerializer):
    cloudinary_fields = ['image']

    class Meta:
        model = Dish
        fields = ['id', 'category', 'name', 'size_type', 'price', 'description', 'image', 'is_available', 'is_active',
                  'created_at', 'updated_at']


class CreateDishSerializer(serializers.ModelSerializer):
    sizes = DishSizeInputSerializer(many=True, write_only=True)

    class Meta:
        model = Dish
        fields = ['id', 'category', 'name', 'description', 'image', 'sizes']

    def validate(self, data):
        name = data.get('name', '').lower()
        sizes = data.get('sizes', [])

        if not sizes:
            raise serializers.ValidationError({"detail": "At least one size must be provided."})

        size_types = [s['size_type'] for s in sizes]
        if len(size_types) != len(set(size_types)):
            raise serializers.ValidationError({"detail": "Duplicate size types in request."})

        # Enforce DB constraint ở tầng API để báo lỗi đẹp cho Client
        for size in sizes:
            if Dish.objects.filter(name=name, size_type=size['size_type']).exists():
                raise serializers.ValidationError(
                    {"detail": f"Dish with name '{name}' and size '{size['size_type']}' already exists."})

        return data

    def create(self, validated_data):
        sizes = validated_data.pop('sizes')
        name = validated_data.get('name').lower()
        validated_data['name'] = name

        # Lấy ảnh ra nếu có truyền lên
        image = validated_data.pop('image', None)

        dishes = []
        with transaction.atomic():
            for size in sizes:
                dish = Dish(
                    **validated_data,
                    size_type=size['size_type'],
                    price=size['price']
                )
                if image:
                    dish.image = image
                dish.save()  # Dùng .save() thay vì bulk_create để CloudinaryField tự động upload ảnh
                dishes.append(dish)

        # Trả về instance đầu tiên làm đại diện cho response
        return dishes[0]


class PartialUpdateDishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = ['category', 'name', 'description', 'image', 'price']

    def validate(self, data):
        if 'name' in data:
            new_name = data['name'].lower()
            if new_name != self.instance.name:
                # Đảm bảo tên mới không bị đụng hàng với size đã có
                current_sizes = Dish.objects.filter(name=self.instance.name).values_list('size_type', flat=True)
                for size in current_sizes:
                    if Dish.objects.filter(name=new_name, size_type=size).exclude(name=self.instance.name).exists():
                        raise serializers.ValidationError(
                            {"detail": f"Cannot rename. Name '{new_name}' with size '{size}' already exists."})
        return data

    def update(self, instance, validated_data):
        shared_fields = ['category', 'name', 'description', 'image']
        update_shared = {k: v for k, v in validated_data.items() if k in shared_fields}
        price = validated_data.get('price')

        with transaction.atomic():
            # Đồng bộ các field chung cho TẤT CẢ các size của món này
            if update_shared:
                siblings = Dish.objects.filter(name=instance.name)
                for sibling in siblings:
                    for attr, value in update_shared.items():
                        setattr(sibling, attr, value)
                    sibling.save()  # Lưu từng object để trigger Cloudinary upload nếu có ảnh mới

            # Cập nhật giá (price) CHỈ cho size hiện tại
            if price is not None:
                instance.price = price
                instance.save(update_fields=['price', 'updated_at'])

        instance.refresh_from_db()
        return instance


class ToggleAvailabilityDishSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dish
        fields = ['id', 'is_available']
        read_only_fields = fields



# --------RECIPE ITEM---------

class ListRecipeItemSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit = serializers.CharField(source='ingredient.unit', read_only=True)

    class Meta:
        model = RecipeItem
        fields = ['id', 'ingredient', 'ingredient_name', 'unit', 'quantity', 'is_active']


class CreateRecipeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeItem
        fields = ['ingredient', 'quantity']

    def create(self, validated_data):
        dish = self.context['dish']
        ingredient = validated_data['ingredient']
        quantity = validated_data['quantity']

        # Logic: Có rồi thì update, chưa có thì tạo mới
        item, created = RecipeItem.objects.update_or_create(
            dish=dish,
            ingredient=ingredient,
            defaults={'quantity': quantity}
        )
        return item


class PartialUpdateRecipeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecipeItem
        fields = ['quantity']