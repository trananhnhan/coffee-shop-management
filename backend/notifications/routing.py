from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # Đường dẫn chuẩn cho Frontend kết nối: ws://domain/ws/notifications/?token=...
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]