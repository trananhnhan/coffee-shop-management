import asyncio
from django.test import TransactionTestCase
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async
from rest_framework_simplejwt.tokens import RefreshToken

from core.asgi import application
from accounts.models import User, Branch, Role
from notifications.utils import broadcast_ws_event


class ComprehensiveWebSocketTests(TransactionTestCase):

    def setUp(self):
        # 1. TẠO 2 CHI NHÁNH KHÁC NHAU
        self.branch_1 = Branch.objects.create(
            name="Chi nhánh Quận 1",
            address="123 Lê Lợi",
            table_capacity=20  # <--- THÊM DÒNG NÀY
        )
        self.branch_2 = Branch.objects.create(
            name="Chi nhánh Quận 2",
            address="456 Thảo Điền",
            table_capacity=30  # <--- VÀ DÒNG NÀY NỮA
        )
        # 2. TẠO NHÂN VIÊN CHO TỪNG CHI NHÁNH
        self.cashier_b1 = User.objects.create_user(
            username="cashier_b1", password="password", role=Role.CASHIER, branch=self.branch_1
        )
        self.kitchen_b2 = User.objects.create_user(
            username="kitchen_b2", password="password", role=Role.KITCHEN, branch=self.branch_2
        )

        # 3. TẠO OWNER (Không thuộc chi nhánh cụ thể nào)
        self.owner = User.objects.create_user(
            username="owner_boss", password="password", role=Role.OWNER
        )

        # 4. TẠO TOKEN CHO TỪNG NGƯỜI
        self.token_b1 = str(RefreshToken.for_user(self.cashier_b1).access_token)
        self.token_b2 = str(RefreshToken.for_user(self.kitchen_b2).access_token)
        self.token_owner = str(RefreshToken.for_user(self.owner).access_token)

    async def test_1_reject_anonymous_connection(self):
        """Kịch bản 1: Không có JWT Token -> Từ chối kết nối"""
        communicator = WebsocketCommunicator(application, "/ws/notifications/")
        connected, _ = await communicator.connect()

        self.assertFalse(connected)
        await communicator.disconnect()

    async def test_2_cashier_receives_own_branch_event(self):
        """Kịch bản 2: Thu ngân nhận được thông báo tạo đơn từ chi nhánh CỦA MÌNH"""
        communicator = WebsocketCommunicator(application, f"/ws/notifications/?token={self.token_b1}")
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Bắn tin nhắn vào Chi nhánh 1
        await database_sync_to_async(broadcast_ws_event)(
            branch_id=self.branch_1.id,
            event_type="order.created",
            data={"id": "ORDER_001", "status": "PENDING"}
        )

        # Chờ nhận tin nhắn
        response = await communicator.receive_json_from(timeout=2)

        self.assertEqual(response["type"], "order.created")
        self.assertEqual(response["branch_id"], str(self.branch_1.id))
        self.assertEqual(response["data"]["id"], "ORDER_001")

        await communicator.disconnect()

    async def test_3_strict_branch_isolation(self):
        """
        Kịch bản 3 (Quan trọng): CÁCH LY CHI NHÁNH
        Tin nhắn của Chi nhánh 1 bắn ra, nhân viên Chi nhánh 2 tuyệt đối không được nghe thấy.
        """
        comm_b2 = WebsocketCommunicator(application, f"/ws/notifications/?token={self.token_b2}")
        connected, _ = await comm_b2.connect()
        self.assertTrue(connected)  # Đảm bảo đã connect thành công

        # Giả lập: Bếp Chi nhánh 1 nấu xong đồ ăn, bắn tin nhắn cho Chi nhánh 1
        await database_sync_to_async(broadcast_ws_event)(
            branch_id=self.branch_1.id,
            event_type="order.updated",
            data={"id": "ORDER_002", "status": "READY"}
        )

        # KHẲNG ĐỊNH: Nhân viên Chi nhánh 2 chờ mòn mỏi cũng không nhận được gì
        # Dùng receive_nothing() sẽ an toàn và chuẩn xác hơn ép lỗi Timeout
        is_empty = await comm_b2.receive_nothing(timeout=2)
        self.assertTrue(is_empty)  # Pass nếu thực sự ống bơ rỗng

        await comm_b2.disconnect()

    async def test_4_owner_receives_everything_globally(self):
        """
        Kịch bản 4: QUYỀN CHÚA TỂ CỦA OWNER
        Owner phải nhận được tin nhắn bất kể nó xuất phát từ Chi nhánh 1 hay 2.
        """
        # Owner kết nối
        comm_owner = WebsocketCommunicator(application, f"/ws/notifications/?token={self.token_owner}")
        await comm_owner.connect()

        # Sự kiện 1: Chi nhánh 1 báo hết cafe
        await database_sync_to_async(broadcast_ws_event)(
            branch_id=self.branch_1.id,
            event_type="inventory.low_stock",
            data={"item_name": "Cà phê hạt"}
        )

        response_1 = await comm_owner.receive_json_from(timeout=2)
        self.assertEqual(response_1["branch_id"], str(self.branch_1.id))
        self.assertEqual(response_1["type"], "inventory.low_stock")

        # Sự kiện 2: Chi nhánh 2 duyệt phiếu xin Sữa
        await database_sync_to_async(broadcast_ws_event)(
            branch_id=self.branch_2.id,
            event_type="inventory.request_approved",
            data={"item_name": "Sữa tươi"}
        )

        response_2 = await comm_owner.receive_json_from(timeout=2)
        self.assertEqual(response_2["branch_id"], str(self.branch_2.id))
        self.assertEqual(response_2["type"], "inventory.request_approved")

        await comm_owner.disconnect()