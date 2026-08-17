from rest_framework.test import APITestCase
from rest_framework import status
from django.db.models import ProtectedError

from accounts.models import User, Branch, Role
from .models import StockItem, InventoryItem, StockRequest, StockRequestStatus


class InventoryIntegrationTests(APITestCase):
    def setUp(self):
        # 1. Tạo Branches & Users
        self.branch_a = Branch.objects.create(name="Branch A", table_capacity=10)
        self.branch_b = Branch.objects.create(name="Branch B", table_capacity=15)

        self.owner = User.objects.create_user(username="owner", password="123", role=Role.OWNER)
        self.manager_a = User.objects.create_user(username="manager_a", password="123", role=Role.STORE_MANAGER,
                                                  branch=self.branch_a)
        self.cashier_a = User.objects.create_user(username="cashier_a", password="123", role=Role.CASHIER,
                                                  branch=self.branch_a)
        self.cashier_b = User.objects.create_user(username="cashier_b", password="123", role=Role.CASHIER,
                                                  branch=self.branch_b)

        # 2. Tạo Data Nền (Danh mục kho & Tồn kho)
        self.stock_item = StockItem.objects.create(name="Cà phê hạt", unit="kg", unit_price=200000)

        # Branch A đang có 5kg, ngưỡng cảnh báo là 10kg
        self.inv_a = InventoryItem.objects.create(branch=self.branch_a, stock_item=self.stock_item, quantity=5,
                                                  threshold=10)
        # Branch B đang có 20kg, ngưỡng cảnh báo là 10kg
        self.inv_b = InventoryItem.objects.create(branch=self.branch_b, stock_item=self.stock_item, quantity=20,
                                                  threshold=10)

        # URLs
        self.request_url = '/api/inventory/stock-requests/'

    # ==========================================
    # TEST 1: MODEL BOUNDARY (is_low_stock)
    # ==========================================
    def test_inventory_item_is_low_stock_boundary(self):
        # Quantity (5) < Threshold (10) -> True
        self.assertTrue(self.inv_a.is_low_stock)

        # Quantity (20) > Threshold (10) -> False
        self.assertFalse(self.inv_b.is_low_stock)

        # Boundary: Quantity (10) == Threshold (10) -> KỲ VỌNG: True
        self.inv_b.quantity = 10
        self.inv_b.save()
        self.assertTrue(self.inv_b.is_low_stock)

    # ==========================================
    # TEST 2: CROSS-BRANCH BLOCKED END-TO-END
    # ==========================================
    def test_create_request_cross_branch_validation(self):
        self.client.force_authenticate(user=self.cashier_a)

        # Cashier A lén tạo đơn xin hàng cho kho của Branch B
        payload = {
            "inventory_item": self.inv_b.id,
            "quantity": 10
        }
        response = self.client.post(self.request_url, payload, format='json')

        # KỲ VỌNG: 400 Bad Request từ Serializer Validation
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("own branch", str(response.data).lower())

    def test_cross_branch_object_access_returns_404(self):
        # Tạo sẵn 1 đơn hợp lệ cho Branch B
        req_b = StockRequest.objects.create(
            inventory_item=self.inv_b, requested_by=self.cashier_b, quantity=10,
            unit_price_snapshot=200000, status=StockRequestStatus.PENDING
        )

        # Manager A cố tình truy cập vào đơn của Branch B để xem/duyệt
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.get(f"{self.request_url}{req_b.id}/")

        # KỲ VỌNG: Bị chặn ngay từ get_queryset, trả về 404 (Không phải 403)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ==========================================
    # TEST 3: FULL LIFECYCLE (Happy Path & Price Isolation)
    # ==========================================
    def test_stock_request_full_lifecycle_and_price_sync(self):
        # --- BƯỚC 1: CASHIER TẠO ĐƠN ---
        self.client.force_authenticate(user=self.cashier_a)
        payload = {"inventory_item": self.inv_a.id, "quantity": 15}
        res_create = self.client.post(self.request_url, payload, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED)
        req_id = res_create.data['id']

        # Kiểm tra snapshot giá phải được copy chuẩn
        req_obj = StockRequest.objects.get(id=req_id)
        self.assertEqual(req_obj.status, StockRequestStatus.PENDING)
        self.assertEqual(req_obj.unit_price_snapshot, 200000)

        # --- BƯỚC 1.5: GIÁ THỊ TRƯỜNG BIẾN ĐỘNG ---
        self.stock_item.unit_price = 220000
        self.stock_item.save()

        # --- BƯỚC 2: MANAGER DUYỆT ĐƠN (KÈM CHỐT GIÁ CUỐI) ---
        self.client.force_authenticate(user=self.manager_a)
        approve_url = f"{self.request_url}{req_id}/approve/"

        # Manager chốt giá cuối là 250000
        res_approve = self.client.patch(approve_url, {"unit_price_snapshot": 250000}, format='json')
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        req_obj.refresh_from_db()
        self.stock_item.refresh_from_db()

        self.assertEqual(req_obj.status, StockRequestStatus.APPROVED)
        self.assertEqual(req_obj.approved_by, self.manager_a)
        # BẢO MẬT: Snapshot gốc lúc Cashier tạo (200000) KHÔNG ĐƯỢC PHÉP ĐỔI
        self.assertEqual(req_obj.unit_price_snapshot, 200000)
        # ĐỒNG BỘ: Giá gốc trong danh mục (StockItem) ĐÃ ĐƯỢC ĐỔI thành 250000
        self.assertEqual(self.stock_item.unit_price, 250000)

        # Tồn kho lúc này vẫn phải là 5 (Hàng chưa về)
        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.quantity, 5)

        # --- BƯỚC 3: DELIVER (NHẬP KHO) ---
        self.client.force_authenticate(user=self.cashier_a)
        res_deliver = self.client.patch(f"{self.request_url}{req_id}/deliver/")
        self.assertEqual(res_deliver.status_code, status.HTTP_200_OK)

        # Tồn kho phải được cộng đúng: 5 + 15 = 20
        self.inv_a.refresh_from_db()
        self.assertEqual(self.inv_a.quantity, 20)

    # ==========================================
    # TEST 4: STATE MACHINE (Chống double-action)
    # ==========================================
    def test_double_approve_and_invalid_state_transitions_return_400(self):
        # Tạo sẵn 1 đơn ĐÃ DUYỆT (APPROVED)
        req = StockRequest.objects.create(
            inventory_item=self.inv_a, requested_by=self.cashier_a, quantity=10,
            status=StockRequestStatus.APPROVED, unit_price_snapshot=200000
        )

        self.client.force_authenticate(user=self.manager_a)

        # Cố tình duyệt thêm 1 lần nữa -> KỲ VỌNG: 400
        res_approve = self.client.patch(f"{self.request_url}{req.id}/approve/")
        self.assertEqual(res_approve.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only pending", str(res_approve.data).lower())

        # Cố tình Reject một đơn đã APPROVED -> KỲ VỌNG: 400
        res_reject = self.client.patch(f"{self.request_url}{req.id}/reject/")
        self.assertEqual(res_reject.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("only pending", str(res_reject.data).lower())

    # ==========================================
    # TEST 5: DATABASE CONSTRAINTS
    # ==========================================
    def test_stock_item_protect_constraint(self):
        # Xóa StockItem đang có InventoryItem liên kết -> Bị DB chặn (PROTECT)
        with self.assertRaises(ProtectedError):
            self.stock_item.delete()