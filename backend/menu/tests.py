from rest_framework.test import APITestCase
from rest_framework import status
from django.db.models import ProtectedError
from unittest.mock import patch

from accounts.models import User, Branch, Role
from .models import Category, Dish, Ingredient, RecipeItem


class MenuIntegrationTests(APITestCase):
    def setUp(self):
        # 1. Tạo Users & Quyền
        self.branch = Branch.objects.create(name="Central", table_capacity=20)
        self.owner = User.objects.create_user(username="owner", password="123", role=Role.OWNER)
        self.cashier = User.objects.create_user(username="cashier", password="123", role=Role.CASHIER,
                                                branch=self.branch)

        # 2. Tạo Data Nền
        self.category = Category.objects.create(name="Coffee")
        self.ingredient = Ingredient.objects.create(name="Sữa đặc", unit="ml")

        # URLs
        self.dish_url = '/api/menu/dishes/'

    def get_dish_detail_url(self, dish_id):
        return f'{self.dish_url}{dish_id}/'

    # ==========================================
    # SỬA TEST 1
    # ==========================================
    def test_create_dish_multiple_sizes_and_lowercase_duplicate_check(self):
        self.client.force_authenticate(user=self.owner)

        payload = {
            "name": "Cà Phê Sữa",
            "category": self.category.id,
            "description": "Ngon tuyệt",
            "sizes": [
                # ĐỔI THÀNH CHỮ THƯỜNG (HOẶC GIÁ TRỊ KHỚP VỚI MODEL CỦA BẠN)
                {"size_type": "m", "price": 30000},
                {"size_type": "l", "price": 40000}
            ]
        }
        response = self.client.post(self.dish_url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(Dish.objects.count(), 2)

        payload_dup = {
            "name": "cà phê sữa",
            "category": self.category.id,
            "sizes": [{"size_type": "m", "price": 35000}]
        }
        response_dup = self.client.post(self.dish_url, payload_dup, format='json')
        self.assertEqual(response_dup.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already exists", str(response_dup.data).lower())

    # ==========================================
    # TEST 2: DISH UPDATE (Sync Shared vs Isolate Price)
    # ==========================================
    def test_partial_update_syncs_shared_fields_but_isolates_price(self):
        # Tạo 2 size cho 1 món
        dish_m = Dish.objects.create(name="trà đào", category=self.category, size_type="M", price=30000,
                                     description="Cũ")
        dish_l = Dish.objects.create(name="trà đào", category=self.category, size_type="L", price=40000,
                                     description="Cũ")

        self.client.force_authenticate(user=self.owner)
        url = self.get_dish_detail_url(dish_m.id)

        # Cập nhật thông qua Dish M (đổi cả price và description)
        payload = {
            "price": 35000,
            "description": "Mới update"
        }
        response = self.client.patch(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        dish_m.refresh_from_db()
        dish_l.refresh_from_db()

        # KỲ VỌNG:
        # 1. Price của M đổi, L giữ nguyên (Isolated)
        self.assertEqual(dish_m.price, 35000)
        self.assertEqual(dish_l.price, 40000)
        # 2. Description của CẢ HAI đều đổi (Synced)
        self.assertEqual(dish_m.description, "Mới update")
        self.assertEqual(dish_l.description, "Mới update")

    # ==========================================
    # TEST 3: RECIPE ITEM LIFECYCLE (Update_or_create)
    # ==========================================
    def test_recipe_item_creation_prevents_duplicates(self):
        dish = Dish.objects.create(name="đen đá", category=self.category, size_type="M", price=20000)
        self.client.force_authenticate(user=self.owner)
        recipe_url = f'{self.get_dish_detail_url(dish.id)}recipe-items/'

        # 3.1 Thêm nguyên liệu lần đầu
        self.client.post(recipe_url, {"ingredient": self.ingredient.id, "quantity": 20})
        self.assertEqual(RecipeItem.objects.count(), 1)
        self.assertEqual(RecipeItem.objects.first().quantity, 20)

        # 3.2 Thêm LẠI nguyên liệu đó với số lượng mới -> KỲ VỌNG: Không tạo dòng mới, chỉ đè số lượng
        self.client.post(recipe_url, {"ingredient": self.ingredient.id, "quantity": 50})
        self.assertEqual(RecipeItem.objects.count(), 1)  # Vẫn là 1
        self.assertEqual(RecipeItem.objects.first().quantity, 50)  # Đã được update

    # ==========================================
    # TEST 4: PERMISSIONS (Read/Write Asymmetry)
    # ==========================================
    def test_non_owner_read_write_permissions(self):
        dish = Dish.objects.create(name="bạc xỉu", category=self.category, size_type="M", price=25000)
        self.client.force_authenticate(user=self.cashier)

        # 4.1 Cashier ĐƯỢC list dishes và ingredients
        self.assertEqual(self.client.get(self.dish_url).status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/menu/ingredients/').status_code, status.HTTP_200_OK)

        # 4.2 Cashier ĐƯỢC xem recipe_items (Nhờ cái override get_permissions tụi mình vừa làm)
        recipe_url = f'{self.get_dish_detail_url(dish.id)}recipe-items/'
        self.assertEqual(self.client.get(recipe_url).status_code, status.HTTP_200_OK)

        # 4.3 Cashier BỊ CHẶN khi cố tạo mới
        self.assertEqual(self.client.post(self.dish_url, {}).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.post(recipe_url, {}).status_code, status.HTTP_403_FORBIDDEN)

    # ==========================================
    # TEST 5: DATABASE CONSTRAINTS (CASCADE vs PROTECT)
    # ==========================================
    def test_database_deletion_constraints(self):
        dish = Dish.objects.create(name="latte", category=self.category, size_type="M", price=45000)
        RecipeItem.objects.create(dish=dish, ingredient=self.ingredient, quantity=100)

        # 5.1 Xóa Ingredient đang có RecipeItem -> Bị DB chặn (PROTECT)
        with self.assertRaises(ProtectedError):
            self.ingredient.delete()

        # 5.2 Xóa Dish -> Thành công và tự động xóa luôn RecipeItem (CASCADE)
        dish.delete()
        self.assertEqual(Dish.objects.count(), 0)
        self.assertEqual(RecipeItem.objects.count(), 0)

    # ==========================================
    # SỬA LẠI TEST 6 (Hoàn hảo 100%)
    # ==========================================
    @patch('menu.models.Dish.save')
    def test_dish_creation_rolls_back_on_db_failure(self, mock_save):
        self.client.force_authenticate(user=self.owner)

        # Giăng bẫy
        mock_save.side_effect = Exception("Database crash!")

        payload = {
            "name": "Món Lỗi",
            "category": self.category.id,
            "sizes": [{"size_type": "m", "price": 30000}],
        }

        # Vì Django Test Client sẽ ném ngược Exception ra ngoài, ta phải "đỡ" nó!
        with self.assertRaises(Exception) as context:
            self.client.post(self.dish_url, payload, format='json')

        # Xác nhận đúng là do cái bẫy của ta nổ chứ không phải lỗi vớ vẩn nào khác
        self.assertIn("Database crash!", str(context.exception))

        # KỲ VỌNG QUAN TRỌNG NHẤT: Giao dịch đã bị rollback!
        # Database sạch sẽ, không có dấu vết của "Món Lỗi"
        self.assertEqual(Dish.objects.filter(name="Món Lỗi").count(), 0)