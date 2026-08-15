import uuid
from django.db import models
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

class TimeStampedModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    # Đổi 'active' thành 'is_active' để chuẩn hóa toàn hệ thống
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

    def deactivate(self):
        if not self.is_active:
            raise ValueError(f"{self.__class__.__name__} is already inactive.")
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    def activate(self):
        if self.is_active:
            raise ValueError(f"{self.__class__.__name__} is already active.")
        self.is_active = True
        self.save(update_fields=['is_active', 'updated_at'])

class ActivatableViewSetMixin:
    """
    Mixin dùng cho các ViewSet cần 2 endpoint activate/deactivate.
    Chỉ áp dụng cho các Model kế thừa từ BaseModel.
    """
    @action(detail=True, methods=['patch'])
    def activate(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.activate()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=['patch'])
    def deactivate(self, request, pk=None):
        obj = self.get_object()
        try:
            obj.deactivate()
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(obj).data)

class CloudinaryImageMixin:
    cloudinary_fields = []

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for field_name in self.cloudinary_fields:
            if getattr(instance, field_name, None):
                data[field_name] = getattr(instance, field_name).url
        return data