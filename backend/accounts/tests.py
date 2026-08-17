from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import User, Branch, Role


class AccountsIntegrationTests(APITestCase):
    def setUp(self):
        # 1. Tạo dữ liệu nền (Branches)
        self.branch_a = Branch.objects.create(name="Branch A", table_capacity=10)
        self.branch_b = Branch.objects.create(name="Branch B", table_capacity=15)

        # 2. Tạo Users đa dạng Role
        self.owner = User.objects.create_user(
            username="owner", password="123", role=Role.OWNER
        )
        self.manager_a = User.objects.create_user(
            username="manager_a", password="123", role=Role.STORE_MANAGER, branch=self.branch_a
        )
        self.cashier_a = User.objects.create_user(
            username="cashier_a", password="123", role=Role.CASHIER, branch=self.branch_a
        )
        self.cashier_b = User.objects.create_user(
            username="cashier_b", password="123", role=Role.CASHIER, branch=self.branch_b
        )

        # Set URLs (Giả định router của bạn đăng ký basename là 'user')
        self.user_list_url = '/api/accounts/users/'

    def get_user_detail_url(self, user_id):
        return f'{self.user_list_url}{user_id}/'


    # TEST 1: STORE MANAGER ONBOARDS STAFF (THÀNH CÔNG)
    def test_manager_can_create_cashier(self):
        self.client.force_authenticate(user=self.manager_a)
        payload = {
            "username": "new_cashier_a",
            "password": "strongpassword",
            "role": Role.CASHIER,
            # Cố tình không truyền branch để test server-side override
        }
        response = self.client.post(self.user_list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify: Mật khẩu đã được hash và branch bị ép về branch A
        new_user = User.objects.get(username="new_cashier_a")
        self.assertNotEqual(new_user.password, "strongpassword")
        self.assertTrue(new_user.check_password("strongpassword"))
        self.assertEqual(new_user.branch, self.branch_a)


    # TEST 2: PRIVILEGE ESCALATION (CHẶN NÂNG QUYỀN)
    def test_manager_cannot_create_another_manager(self):
        self.client.force_authenticate(user=self.manager_a)
        payload = {
            "username": "hacker_manager",
            "password": "123",
            "role": Role.STORE_MANAGER  # Vượt quyền
        }
        response = self.client.post(self.user_list_url, payload)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("assign cashier or kitchen", str(response.data).lower())


    # TEST 3: CROSS-BRANCH 404 (CÁCH LY DỮ LIỆU)
    def test_manager_cross_branch_access_returns_404(self):
        self.client.force_authenticate(user=self.manager_a)

        # Cố tình sửa Cashier của Branch B
        url = self.get_user_detail_url(self.cashier_b.id)
        response = self.client.patch(url, {"username": "hacked"})

        # Kỳ vọng 404 vì get_queryset đã lọc mất tiêu, không lọt được tới check 403
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


    # TEST 4: OBJECT-LEVEL PERMISSION (CAN_MANAGE_TARGET_USER)
    def test_manager_cannot_update_themselves(self):
        self.client.force_authenticate(user=self.manager_a)

        # Manager A tự đổi thông tin của chính mình qua endpoint CRUD
        url = self.get_user_detail_url(self.manager_a.id)
        response = self.client.patch(url, {"username": "new_manager_name"})

        # Kỳ vọng 403 vì obj.role == STORE_MANAGER không lọt vào list [CASHIER, KITCHEN]
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


    # TEST 5: OWNER BYPASS & IS_ACTIVE FILTER
    def test_owner_soft_delete_visibility(self):
        self.client.force_authenticate(user=self.owner)

        # Owner xóa mềm Cashier A
        url = self.get_user_detail_url(self.cashier_a.id) + 'deactivate/'
        self.client.patch(url)

        self.cashier_a.refresh_from_db()
        self.assertFalse(self.cashier_a.is_active)

        # Manager A GET list -> Không thấy Cashier A nữa
        self.client.force_authenticate(user=self.manager_a)
        response = self.client.get(self.user_list_url)
        usernames = [user['username'] for user in response.data['results']]
        self.assertNotIn('cashier_a', usernames)

        # Owner gọi list với param ?is_active=false -> Thấy Cashier A
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.user_list_url + '?is_active=false')
        usernames = [user['username'] for user in response.data['results']]
        self.assertIn('cashier_a', usernames)

    # TEST 6: GET /ME ENDPOINT

    def test_me_endpoint_returns_correct_user(self):
        self.client.force_authenticate(user=self.cashier_a)
        response = self.client.get(self.user_list_url + 'me/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'cashier_a')
        self.assertEqual(response.data['role'], Role.CASHIER)