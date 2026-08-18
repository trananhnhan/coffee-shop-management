import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from notifications.routing import websocket_urlpatterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

# Khởi tạo HTTP router trước
django_asgi_app = get_asgi_application()

# Import Middleware vừa viết
from accounts.ws_middleware import JWTAuthMiddlewareStack
# (Lát nữa chúng ta sẽ tạo file routing.py sau, tạm thời để rỗng)
from django.urls import path

application = ProtocolTypeRouter({
    # 1. Xử lý các request HTTP bình thường (REST API)
    "http": django_asgi_app,
    
    # 2. Xử lý WebSocket
    "websocket": AllowedHostsOriginValidator(
        JWTAuthMiddlewareStack(
            URLRouter(
                websocket_urlpatterns
            )
        )
    ),
})