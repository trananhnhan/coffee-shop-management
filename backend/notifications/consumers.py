import json
from channels.generic.websocket import AsyncWebsocketConsumer
from accounts.models import Role


class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Thu thập thông tin user từ Middleware (Kẻ gác cổng)
        self.user = self.scope['user']

        # 1. TỪ CHỐI KẾT NỐI nếu là Khách vô danh (sai token/không có token)
        if self.user.is_anonymous:
            await self.close(code=4001)
            return

        # 2. PHÂN PHÒNG (Routing Group)
        if self.user.role == Role.OWNER:
            self.group_name = 'admin_global'
        else:
            # Nếu là nhân viên, đưa vào group của chi nhánh đó
            if self.user.branch_id:
                self.group_name = f'branch_{self.user.branch_id}'
            else:
                self.group_name = 'unassigned'

        # 3. JOIN PHÒNG
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        # 4. BẤM NÚT CHẤP NHẬN KẾT NỐI
        await self.accept()

    async def disconnect(self, close_code):
        # 5. RỜI PHÒNG khi user đóng tab trình duyệt
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    # 6. HÀM NHẬN TIN NHẮN TỪ REDIS VÀ GỬI CHO FRONTEND
    # Lưu ý: Tên hàm này (send_notification) phải khớp với field "type" lúc gửi từ Django
    async def send_notification(self, event):
        payload = {
            "type": event["event_type"],  # Ví dụ: 'order.created'
            "branch_id": event["branch_id"],
            "data": event["data"]  # Payload JSON của đơn hàng
        }

        # Đẩy dữ liệu qua đường ống WS xuống trình duyệt (dưới dạng chuỗi JSON)
        await self.send(text_data=json.dumps(payload))