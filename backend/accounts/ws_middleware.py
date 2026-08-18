from urllib.parse import parse_qs
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from accounts.models import User


@database_sync_to_async
def get_user_from_token(token_string):
    """
    Hàm này chạy bất đồng bộ (async). Nó giải mã JWT Token
    và truy vấn Database để lấy object User.
    """
    try:
        # Giải mã token giống hệt cách DRF SimpleJWT làm
        access_token = AccessToken(token_string)
        user_id = access_token['user_id']
        return User.objects.get(id=user_id)
    except (InvalidToken, TokenError, User.DoesNotExist):
        # Nếu token sai, hết hạn, hoặc user không tồn tại -> Trả về Khách vô danh
        return AnonymousUser()
    except Exception:
        return AnonymousUser()


class JWTAuthMiddleware:
    """
    Middleware bóc tách Token từ Query String (URL) của WebSocket
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # 1. Lấy chuỗi query string từ URL (VD: b'token=abc.xyz')
        query_string = scope.get('query_string', b'').decode('utf-8')

        # 2. Parse nó thành Dictionary
        query_params = parse_qs(query_string)

        # 3. Lấy giá trị của key 'token'
        token = query_params.get('token', [None])[0]

        # 4. Xác thực và gắn user vào scope
        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = AnonymousUser()

        # 5. Chuyển request đi tiếp tới các tầng bên trong (Consumers)
        return await self.app(scope, receive, send)


# Tạo một wrapper để dễ gọi trong asgi.py
def JWTAuthMiddlewareStack(inner):
    return JWTAuthMiddleware(inner)