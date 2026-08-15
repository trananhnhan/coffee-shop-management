from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Branch


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'table_capacity', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'address', 'phone')
    readonly_fields = ('id', 'created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'role', 'branch', 'is_active', 'is_staff')
    list_filter = ('role', 'is_active', 'branch', 'is_staff')
    search_fields = ('username',)
    readonly_fields = ('created_at', 'updated_at')

    # Gắn thêm role và branch vào màn hình chỉnh sửa chi tiết của Admin
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Coffee Shop Info', {'fields': ('role', 'branch')}),
    )
    # Gắn thêm role và branch vào màn hình tạo mới User
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Coffee Shop Info', {'fields': ('role', 'branch')}),
    )