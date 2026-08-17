from rest_framework.test import APITestCase
from rest_framework import status
from django.db.utils import IntegrityError
from django.db import transaction
from django.urls import reverse

from accounts.models import User, Branch, Role
from menu.models import Category, Dish
from .models import Order, OrderItem, OrderStatus, OrderType, PaymentStatus, KitchenStatus, PaymentMethod


class OrderIntegrationTests(APITestCase):
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
        self.kitchen_a = User.objects.create_user(username="kitchen_a", password="123", role=Role.KITCHEN,
                                                  branch=self.branch_a)

        # 2. Tạo Menu Data
        self.category = Category.objects.create(name="Coffee")
        self.dish_1 = Dish.objects.create(name="Cafe Sữa", category=self.category, size_type="M", price=30000,
                                          is_available=True)
        self.dish_2 = Dish.objects.create(name="Bạc Xỉu", category=self.category, size_type="L", price=40000,
                                          is_available=True)

        # URLs
        self.order_url = '/api/orders/orders/'

    # ==========================================
    # TEST 1: DB CONSTRAINTS (Dine-in vs Takeaway)
    # ==========================================
    def test_db_check_constraints_for_order_type(self):
        # 1.1 Dine-in BẮT BUỘC phải có table_number và KHÔNG có queue_number
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(branch=self.branch_a, cashier=self.cashier_a, order_type=OrderType.DINE_IN,
                                     table_number=None)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(branch=self.branch_a, cashier=self.cashier_a, order_type=OrderType.DINE_IN,
                                     table_number=5, queue_number=1)

        # 1.2 Takeaway BẮT BUỘC phải có queue_number và KHÔNG có table_number
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Order.objects.create(branch=self.branch_a, cashier=self.cashier_a, order_type=OrderType.TAKEAWAY,
                                     queue_number=None)

    # ==========================================
    # TEST 2: CREATE ORDER (Validation & Max Queue Logic)
    # ==========================================
    def test_create_takeaway_order_uses_max_queue_resilient_to_gaps(self):
        self.client.force_authenticate(user=self.cashier_a)

        payload = {
            "order_type": OrderType.TAKEAWAY,
            "payment_method": PaymentMethod.CASH,
            "items": [{"dish": self.dish_1.id, "quantity": 1}]
        }

        # Đơn 1
        res_1 = self.client.post(self.order_url, payload, format='json')
        # ---> THÊM DÒNG NÀY ĐỂ BẮT LỖI
        self.assertEqual(res_1.status_code, status.HTTP_201_CREATED, res_1.data)
        self.assertEqual(res_1.data['queue_number'], 1)

        # Đơn 2
        res_2 = self.client.post(self.order_url, payload, format='json')
        self.assertEqual(res_2.data['queue_number'], 2)

        # Xóa (hoặc Hủy) Đơn 2 để tạo khoảng trống (gap)
        Order.objects.get(id=res_1.data['id']).delete()

        # Đơn 3 -> KỲ VỌNG: Phải là 3 (Max + 1), không phải là 2 (count + 1)
        res_3 = self.client.post(self.order_url, payload, format='json')
        self.assertEqual(res_3.data['queue_number'], 3)

        # KIỂM TRA TỔNG TIỀN (Price Snapshot)
        self.assertEqual(res_3.data['total_price_snapshot'], '30000.00')

    # ==========================================
    # TEST 3: FULL STATE MACHINE (Create -> Kitchen -> Paid)
    # ==========================================
    def test_full_order_lifecycle_and_state_machine(self):
        # 1. Thu ngân tạo đơn Dine-in
        self.client.force_authenticate(user=self.cashier_a)
        payload = {
            "order_type": OrderType.DINE_IN,
            "payment_method": PaymentMethod.CASH,
            "table_number": 5,
            "items": [
                {"dish": self.dish_1.id, "quantity": 1},
                {"dish": self.dish_2.id, "quantity": 2}
            ]
        }
        res_create = self.client.post(self.order_url, payload, format='json')
        # ---> THÊM DÒNG NÀY
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED, res_create.data)
        order_id = res_create.data['id']
        items = res_create.data['items']
        item_1_id, item_2_id = items[0]['id'], items[1]['id']

        self.assertEqual(res_create.data['status'], OrderStatus.PENDING)

        # Cố tình Mark Paid khi hàng chưa ra -> KỲ VỌNG: 400
        res_fail_paid = self.client.patch(f"{self.order_url}{order_id}/mark-paid/")
        self.assertEqual(res_fail_paid.status_code, status.HTTP_400_BAD_REQUEST)

        # 2. Bếp vào cuộc (Kitchen updates status)
        self.client.force_authenticate(user=self.kitchen_a)

        # Nấu xong món 1
        self.client.patch(f"{self.order_url}{order_id}/items/{item_1_id}/kitchen-status/",
                          {"kitchen_status": KitchenStatus.DONE})

        # Order status lúc này phải là IN_KITCHEN (vì món 2 vẫn PENDING)
        res_check = self.client.get(f"{self.order_url}{order_id}/")
        self.assertEqual(res_check.data['status'], OrderStatus.IN_KITCHEN)

        # Nấu xong món 2
        self.client.patch(f"{self.order_url}{order_id}/items/{item_2_id}/kitchen-status/",
                          {"kitchen_status": KitchenStatus.DONE})

        # Order status tự nhảy lên READY
        res_check = self.client.get(f"{self.order_url}{order_id}/")
        self.assertEqual(res_check.data['status'], OrderStatus.READY)

        # 3. Thu ngân thanh toán
        self.client.force_authenticate(user=self.cashier_a)
        res_paid = self.client.patch(f"{self.order_url}{order_id}/mark-paid/")
        self.assertEqual(res_paid.status_code, status.HTTP_200_OK)
        self.assertEqual(res_paid.data['payment_status'], PaymentStatus.PAID)
        self.assertEqual(res_paid.data['status'], OrderStatus.COMPLETED)

    # ==========================================
    # TEST 4: CANCEL & GUARDRAILS
    # ==========================================
    def test_cancel_mid_cooking_and_idempotent_cancel(self):
        # Thu ngân tạo đơn
        self.client.force_authenticate(user=self.cashier_a)
        res = self.client.post(self.order_url, {
            "order_type": OrderType.TAKEAWAY,
            "payment_method": PaymentMethod.CASH,
            "items": [{"dish": self.dish_1.id, "quantity": 1}]
        }, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        order_id = res.data['id']
        item_id = res.data['items'][0]['id']

        # Thu ngân HỦY ĐƠN
        res_cancel = self.client.patch(f"{self.order_url}{order_id}/cancel/")
        self.assertEqual(res_cancel.status_code, status.HTTP_200_OK)
        self.assertEqual(res_cancel.data['status'], OrderStatus.CANCELLED)

        # TEST IDEMPOTENT: Hủy lại đơn đã hủy -> KỲ VỌNG: Pass (Không lỗi)
        res_cancel_again = self.client.patch(f"{self.order_url}{order_id}/cancel/")
        self.assertEqual(res_cancel_again.status_code, status.HTTP_200_OK)

        # Bếp cố tình update món của đơn đã hủy -> KỲ VỌNG: 400 Blocked
        self.client.force_authenticate(user=self.kitchen_a)
        res_kitchen_fail = self.client.patch(f"{self.order_url}{order_id}/items/{item_id}/kitchen-status/",
                                             {"kitchen_status": KitchenStatus.COOKING})
        self.assertEqual(res_kitchen_fail.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot update items in a cancelled order", str(res_kitchen_fail.data).lower())

    # ==========================================
    # TEST 5: UNAVAILABLE DISH GUARD
    # ==========================================
    def test_cannot_order_unavailable_dish(self):
        self.dish_1.is_available = False
        self.dish_1.save()

        self.client.force_authenticate(user=self.cashier_a)
        payload = {
            "order_type": OrderType.TAKEAWAY,
            "items": [{"dish": self.dish_1.id, "quantity": 1}]
        }
        res = self.client.post(self.order_url, payload, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("does not exist or is currently unavailable", str(res.data).lower())

    # ==========================================
    # TEST 6: PERMISSIONS & CROSS-BRANCH ISOLATION
    # ==========================================
    def test_owner_has_no_operational_access_and_cross_branch_is_isolated(self):
        # Cashier A tạo đơn hợp lệ
        self.client.force_authenticate(user=self.cashier_a)
        res_create = self.client.post(self.order_url, {
            "order_type": OrderType.TAKEAWAY,
            "payment_method": PaymentMethod.CASH,
            "items": [{"dish": self.dish_2.id, "quantity": 1}]
        }, format='json')
        self.assertEqual(res_create.status_code, status.HTTP_201_CREATED, res_create.data)
        order_id = res_create.data['id']

        # --- TEST CROSS-BRANCH 404 ---
        # Cashier B cố tình truy cập đơn của Branch A
        self.client.force_authenticate(user=self.cashier_b)
        res_cross = self.client.get(f"{self.order_url}{order_id}/")
        self.assertEqual(res_cross.status_code, status.HTTP_404_NOT_FOUND)  # Bị chặn từ queryset

        # --- TEST OWNER RESTRICTIONS ---
        self.client.force_authenticate(user=self.owner)

        # Owner ĐƯỢC PHÉP xem (READ)
        res_read = self.client.get(f"{self.order_url}{order_id}/")
        self.assertEqual(res_read.status_code, status.HTTP_200_OK)

        # Owner BỊ CẤM tạo đơn (POST)
        res_owner_post = self.client.post(self.order_url, {}, format='json')
        self.assertEqual(res_owner_post.status_code, status.HTTP_403_FORBIDDEN)

        # Owner BỊ CẤM hủy đơn (PATCH /cancel/)
        res_owner_cancel = self.client.patch(f"{self.order_url}{order_id}/cancel/")
        self.assertEqual(res_owner_cancel.status_code, status.HTTP_403_FORBIDDEN)