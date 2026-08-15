from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, DishViewSet, IngredientViewSet, RecipeItemViewSet

router = DefaultRouter()
router.register(r'categories', CategoryViewSet, basename='category')
router.register(r'dishes', DishViewSet, basename='dish')
router.register(r'ingredients', IngredientViewSet, basename='ingredient')
router.register(r'recipe-items', RecipeItemViewSet, basename='recipe-item')

urlpatterns = [
    path('', include(router.urls)),
]