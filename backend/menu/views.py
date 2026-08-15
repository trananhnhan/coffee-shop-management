from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from core.pagination import BasicPaginator
from core.shared import ActivatableViewSetMixin
from accounts.permissions import IsOwner
from accounts.models import Role  # Cần import Role để check quyền

from .models import Category, Dish, Ingredient, RecipeItem
from . import serializers


class BaseMenuViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    """Lớp nền tự động chuyển đổi quyền: Đọc (mọi user), Ghi (chỉ Owner)"""
    pagination_class = BasicPaginator
    http_method_names = ['get', 'post', 'patch', 'delete']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [IsAuthenticated()]
        return [IsOwner()]

    def get_queryset(self):
        # Lấy queryset gốc từ class con (Category hoặc Dish)
        qs = super().get_queryset()
        user = self.request.user

        if user.role == Role.OWNER:
            # Owner được quyền xem tất cả và lọc bằng param ?is_active=true/false
            is_active_param = self.request.query_params.get('is_active')
            if is_active_param == 'true':
                qs = qs.filter(is_active=True)
            elif is_active_param == 'false':
                qs = qs.filter(is_active=False)
            return qs

        # Các Role khác (Manager, Cashier, Kitchen) CHỈ THẤY món đang hoạt động
        return qs.filter(is_active=True)


class CategoryViewSet(BaseMenuViewSet):
    queryset = Category.objects.all()
    http_method_names = ['get', 'post', 'patch']  # Không cho xóa cứng

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListCategorySerializer
        if self.action == 'retrieve': return serializers.RetrieveCategorySerializer
        if self.action == 'create': return serializers.CreateCategorySerializer
        if self.action == 'partial_update': return serializers.PartialUpdateCategorySerializer
        return serializers.RetrieveCategorySerializer


class IngredientViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    pagination_class = BasicPaginator
    permission_classes = [IsOwner]
    http_method_names = ['get', 'post', 'patch']

    def get_queryset(self):
        qs = super().get_queryset()
        # View này chỉ Owner vào được, nên chỉ cần check param
        is_active_param = self.request.query_params.get('is_active')
        if is_active_param == 'true':
            qs = qs.filter(is_active=True)
        elif is_active_param == 'false':
            qs = qs.filter(is_active=False)
        return qs

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListIngredientSerializer
        if self.action == 'retrieve': return serializers.RetrieveIngredientSerializer
        if self.action == 'create': return serializers.CreateIngredientSerializer
        if self.action == 'partial_update': return serializers.PartialUpdateIngredientSerializer
        return serializers.RetrieveIngredientSerializer


class DishViewSet(BaseMenuViewSet):
    queryset = Dish.objects.all()
    http_method_names = ['get', 'post', 'patch']

    def get_serializer_class(self):
        if self.action == 'list': return serializers.ListDishSerializer
        if self.action == 'retrieve': return serializers.RetrieveDishSerializer
        if self.action == 'create': return serializers.CreateDishSerializer
        if self.action == 'partial_update': return serializers.PartialUpdateDishSerializer
        if self.action == 'toggle_availability': return serializers.ToggleAvailabilityDishSerializer

        if self.action == 'recipe_items':
            if self.request.method == 'POST': return serializers.CreateRecipeItemSerializer
            return serializers.ListRecipeItemSerializer

        return serializers.RetrieveDishSerializer

    @action(detail=True, methods=['patch'], url_path='toggle-availability')
    def toggle_availability(self, request, pk=None):
        dish = self.get_object()
        dish.is_available = not dish.is_available
        dish.save(update_fields=['is_available', 'updated_at'])

        serializer = self.get_serializer(dish)
        return Response(serializer.data)

    @action(detail=True, methods=['get', 'post'], url_path='recipe-items')
    def recipe_items(self, request, pk=None):
        dish = self.get_object()

        if request.method == 'GET':
            # Chỉ lấy các công thức đang active
            items = dish.recipe_items.filter(is_active=True)
            serializer = self.get_serializer(items, many=True)
            return Response(serializer.data)

        if request.method == 'POST':
            serializer = self.get_serializer(data=request.data, context={'dish': dish})
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)


class RecipeItemViewSet(ActivatableViewSetMixin, viewsets.ModelViewSet):
    queryset = RecipeItem.objects.all()
    permission_classes = [IsOwner]
    http_method_names = ['patch', 'delete']

    def get_serializer_class(self):
        return serializers.PartialUpdateRecipeItemSerializer