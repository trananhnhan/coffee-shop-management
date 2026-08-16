from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.pagination import BasicPaginator
from core.shared import ActivatableViewSetMixin

from .models import Branch, User, Role
from .permissions import IsOwner, IsOwnerOrStoreManager, CanManageTargetUser
from . import serializers


class BranchViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    # View này chỉ có Owner truy cập, nên cho phép dùng param ?is_active=true/false
    queryset = Branch.objects.all()
    permission_classes = [IsOwner]
    http_method_names = ['get', 'post', 'patch']

    pagination_class = BasicPaginator

    def get_queryset(self):
        qs = super().get_queryset()
        is_active_param = self.request.query_params.get('is_active')

        # Chỉ chấp nhận chính xác chuỗi 'true' hoặc 'false'
        if is_active_param == 'true':
            qs = qs.filter(is_active=True)
        elif is_active_param == 'false':
            qs = qs.filter(is_active=False)

        return qs

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.ListBranchSerializer
        if self.action == 'retrieve':
            return serializers.RetrieveBranchSerializer
        if self.action == 'create':
            return serializers.CreateBranchSerializer
        if self.action == 'partial_update':
            return serializers.PartialUpdateBranchSerializer
        return serializers.RetrieveBranchSerializer


class UserViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    # View này có nhiều role, nên phải chia case ở get_queryset

    http_method_names = ['get', 'post', 'patch']

    pagination_class = BasicPaginator
    def get_permissions(self):
        # Nếu là các thao tác tác động trực tiếp lên 1 user cụ thể
        if self.action in ['partial_update', 'deactivate', 'activate']:
            return [IsOwnerOrStoreManager(), CanManageTargetUser()]

        # Các action còn lại (list, create, retrieve)
        return [IsOwnerOrStoreManager()]

    def get_queryset(self):
        user = self.request.user

        if user.role == Role.OWNER:
            # Owner thấy tất cả, được quyền lọc bằng param
            qs = User.objects.all()
            is_active_param = self.request.query_params.get('is_active')

            if is_active_param == 'true':
                qs = qs.filter(is_active=True)
            elif is_active_param == 'false':
                qs = qs.filter(is_active=False)
            return qs

        elif user.role == Role.STORE_MANAGER:
            # Store Manager CHỈ thấy user thuộc nhánh mình VÀ đang active
            return User.objects.filter(branch=user.branch, is_active=True)

        return User.objects.none()

    def get_serializer_class(self):
        if self.action == 'list':
            return serializers.ListUserSerializer
        if self.action == 'retrieve':
            return serializers.RetrieveUserSerializer
        if self.action == 'create':
            return serializers.CreateUserSerializer
        if self.action == 'partial_update':
            return serializers.PartialUpdateUserSerializer
        return serializers.RetrieveUserSerializer


    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = serializers.RetrieveUserSerializer(request.user)
        return Response(serializer.data)