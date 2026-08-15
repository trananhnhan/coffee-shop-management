from django.contrib import admin
from .models import Category, Dish, Ingredient, RecipeItem

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name',)

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'is_active')
    list_filter = ('is_active', 'unit')
    search_fields = ('name',)

# Thiết lập Inline để hiển thị RecipeItem bên trong Dish
class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 1 # Hiển thị sẵn 1 dòng trống để điền
    fields = ('ingredient', 'quantity', 'is_active')

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'size_type', 'price', 'is_available', 'is_active')
    list_filter = ('category', 'size_type', 'is_available', 'is_active')
    search_fields = ('name',)
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [RecipeItemInline]