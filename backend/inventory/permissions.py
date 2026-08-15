from rest_framework import permissions
from accounts.models import Role

class IsOwnerOrStoreManager(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        return request.user.role in [Role.OWNER, Role.STORE_MANAGER]

class IsBranchStaff(permissions.BasePermission):
    """Store Manager, Cashier, Kitchen (Không bao gồm Owner)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        return request.user.role in [Role.STORE_MANAGER, Role.CASHIER, Role.KITCHEN]

class IsStoreManagerOrKitchen(permissions.BasePermission):
    """Quyền dùng để kiểm kho (sửa số lượng)"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        return request.user.role in [Role.STORE_MANAGER, Role.KITCHEN]

class IsStoreManager(permissions.BasePermission):
    """Quyền duyệt đơn"""
    def has_permission(self, request, view):
        if not request.user.is_authenticated: return False
        return request.user.role == Role.STORE_MANAGER