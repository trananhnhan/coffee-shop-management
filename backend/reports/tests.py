from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from decimal import Decimal
from django.utils import timezone
from datetime import timedelta
from rest_framework_simplejwt.tokens import RefreshToken
from django.core.cache import cache
from accounts.models import User, Branch, Role
from orders.models import Order, OrderItem, OrderStatus, OrderType, PaymentStatus
from menu.models import Dish, Category


class ReportViewSetTests(APITestCase):

    def setUp(self):
        cache.clear()
        # 1. Tạo 2 Chi nhánh
        self.branch_1 = Branch.objects.create(name="Chi nhánh Q1", address="123 Lê Lợi", table_capacity=20)
        self.branch_2 = Branch.objects.create(name="Chi nhánh Q2", address="456 Thảo Điền", table_capacity=20)

        # 2. Tạo Users (Owner, Quản lý Q1, Quản lý Q2)
        self.owner = User.objects.create_user(username="owner", password="password", role=Role.OWNER)
        self.manager_q1 = User.objects.create_user(username="mgr1", password="password", role=Role.STORE_MANAGER,
                                                   branch=self.branch_1)
        self.manager_q2 = User.objects.create_user(username="mgr2", password="password", role=Role.STORE_MANAGER,
                                                   branch=self.branch_2)

        # 3. Tạo Category và Dish mẫu
        category = Category.objects.create(name="Cà phê")
        self.dish_1 = Dish.objects.create(name="Cà phê sữa đá", price=Decimal('35000.00'), category=category)
        self.dish_2 = Dish.objects.create(name="Bạc xỉu", price=Decimal('40000.00'), category=category)

        # 4. Tạo Đơn hàng giả lập cho Chi nhánh 1 (Trạng thái COMPLETED)
        self.order_1 = Order.objects.create(
            branch=self.branch_1,
            cashier=self.manager_q1,
            order_type=OrderType.TAKEAWAY,
            status=OrderStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_price_snapshot=Decimal('70000.00'),  # 2 ly cà phê sữa
            queue_number=1
        )
        OrderItem.objects.create(
            order=self.order_1,
            dish=self.dish_1,
            quantity=2,
            unit_price_snapshot=Decimal('35000.00')
        )

        # 5. Tạo Đơn hàng giả lập cho Chi nhánh 2
        self.order_2 = Order.objects.create(
            branch=self.branch_2,
            cashier=self.manager_q2,
            order_type=OrderType.TAKEAWAY,
            status=OrderStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_price_snapshot=Decimal('40000.00'),  # 1 ly bạc xỉu
            queue_number=1
        )
        OrderItem.objects.create(
            order=self.order_2,
            dish=self.dish_2,
            quantity=1,
            unit_price_snapshot=Decimal('40000.00')
        )

    def test_manager_q1_can_only_see_their_branch_overview(self):
        """Kịch bản 1: Quản lý chi nhánh 1 gọi overview -> Chỉ thấy số liệu của chi nhánh 1 (70k, 1 đơn)"""
        self.client.force_authenticate(user=self.manager_q1)
        url = reverse('reports-overview')  # Tên route do DefaultRouter tự sinh

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_revenue']), 70000.0)
        self.assertEqual(response.data['total_orders'], 1)

    def test_owner_sees_global_overview_by_default(self):
        """Kịch bản 2: Owner gọi overview mà không lọc chi nhánh -> Thấy toàn chuỗi (110k, 2 đơn)"""
        self.client.force_authenticate(user=self.owner)
        url = reverse('reports-overview')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_revenue']), 110000.0)
        self.assertEqual(response.data['total_orders'], 2)

    def test_owner_can_filter_by_specific_branch(self):
        """Kịch bản 3: Owner chủ động lọc theo branch_id của chi nhánh 2"""
        self.client.force_authenticate(user=self.owner)
        url = reverse('reports-overview') + f'?branch_id={self.branch_2.id}'

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['total_revenue']), 40000.0)
        self.assertEqual(response.data['total_orders'], 1)

    def test_top_items_ranking(self):
        """Kịch bản 4: Kiểm tra bảng xếp hạng top món bán chạy"""
        self.client.force_authenticate(user=self.owner)
        url = reverse('reports-top-items')

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Cà phê sữa đá bán 2 ly (nhiều hơn), phải đứng đầu bảng
        top_item = response.data[0]
        self.assertEqual(top_item['dish_name'].lower(), "Cà phê sữa đá".lower())
        self.assertEqual(top_item['total_sold'], 2)

    def test_redis_cache_and_data_isolation(self):
        """
        Kịch bản 5: Chứng minh Cache hoạt động siêu tốc và Cách ly dữ liệu 100% bằng Header
        """
        # Xóa toàn bộ cache trước khi test để đảm bảo môi trường sạch
        cache.clear()

        # 1. Lấy JWT Token thật của 2 Quản lý
        token_q1 = str(RefreshToken.for_user(self.manager_q1).access_token)
        token_q2 = str(RefreshToken.for_user(self.manager_q2).access_token)

        # 2. Q1 GỌI API LẦN 1 (Sẽ tính DB và lưu Cache)
        # Bắt buộc phải gắn Header HTTP thật thì @vary_on_headers mới hoạt động
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token_q1)
        response_q1_first = self.client.get('/api/reports/overview/')
        self.assertEqual(float(response_q1_first.data['total_revenue']), 70000.0)

        # 3. LÉN LÚT CHUYỂN DATA: Tạo thêm 1 đơn 10k cho Q1 trực tiếp vào Database
        Order.objects.create(
            branch=self.branch_1,
            cashier=self.manager_q1,
            order_type=OrderType.TAKEAWAY,
            status=OrderStatus.COMPLETED,
            payment_status=PaymentStatus.PAID,
            total_price_snapshot=Decimal('10000.00'),
            queue_number=2
        )

        # 4. Q1 GỌI API LẦN 2
        # Khẳng định: Vẫn trả về 70k (Dù DB đã là 80k). Chứng tỏ Cache đang hoat động!
        response_q1_second = self.client.get('/api/reports/overview/')
        self.assertEqual(float(response_q1_second.data['total_revenue']), 70000.0)

        # 5. Q2 GỌI API LẦN ĐẦU TIÊN
        self.client.credentials(HTTP_AUTHORIZATION='Bearer ' + token_q2)
        response_q2 = self.client.get('/api/reports/overview/')

        # Khẳng định: Q2 trả về đúng 40k của mình.
        # Chứng tỏ Cache của Q1 không bị rò rỉ sang Q2 nhờ vary_on_headers.
        self.assertEqual(float(response_q2.data['total_revenue']), 40000.0)

        # (Dọn dẹp Header cho các test khác nếu cần)
        self.client.credentials()