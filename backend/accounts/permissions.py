from rest_framework import permissions
from .models import Role


class IsOwner(permissions.BasePermission):
    """Chỉ Owner mới có quyền truy cập"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == Role.OWNER)


class IsOwnerOrStoreManager(permissions.BasePermission):
    """Owner hoặc Store Manager (Dùng cho quản lý User/Branch)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role in [Role.OWNER, Role.STORE_MANAGER]


class IsStoreManager(permissions.BasePermission):
    """Chỉ Store Manager (Dùng để duyệt đơn hàng)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role == Role.STORE_MANAGER


class IsStoreManagerOrKitchen(permissions.BasePermission):
    """Quyền dùng để kiểm kho (sửa số lượng thực tế)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role in [Role.STORE_MANAGER, Role.KITCHEN]


class IsBranchStaff(permissions.BasePermission):
    """Tất cả nhân viên của quán: Store Manager, Cashier, Kitchen (Không bao gồm Owner)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role in [Role.STORE_MANAGER, Role.CASHIER, Role.KITCHEN]

class IsCashier(permissions.BasePermission):
    """Chỉ Cashier (Dùng để tạo đơn, thanh toán)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role == Role.CASHIER

class IsKitchen(permissions.BasePermission):
    """Chỉ Kitchen (Dùng để cập nhật trạng thái món)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role == Role.KITCHEN

class IsStoreManagerOrCashier(permissions.BasePermission):
    """Store Manager hoặc Cashier (Dùng để hủy đơn)"""
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated: return False
        return request.user.role in [Role.STORE_MANAGER, Role.CASHIER]