import os
import django
import random
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction

# 1. KHỞI ĐỘNG MÔI TRƯỜNG DJANGO (BẮT BUỘC CHO FILE CHẠY NGOÀI)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

# 2. IMPORT CÁC MODEL TỪ APP
from accounts.models import User, Branch, Role
from menu.models import Category, Dish
from inventory.models import StockItem, InventoryItem
from orders.models import Order, OrderItem, OrderType, OrderStatus, PaymentStatus, PaymentMethod


def run_seeder():
    with transaction.atomic():
        print("--- BẮT ĐẦU KHỞI TẠO VŨ TRỤ COFFEE SHOP ---")

        # 1. CHI NHÁNH
        print("1. Đang xây dựng Chi nhánh...")
        b1, _ = Branch.objects.get_or_create(name="The Coffee - Quận 1",
                                             defaults={'address': '123 Lê Lợi', 'table_capacity': 30})
        b2, _ = Branch.objects.get_or_create(name="The Coffee - Quận 3",
                                             defaults={'address': '456 Võ Văn Tần', 'table_capacity': 25})

        # 2. TÀI KHOẢN (Mật khẩu chung: 123)
        print("2. Đang tuyển dụng Nhân viên...")
        users_data = [
            ("boss", Role.OWNER, None),
            ("manager_q1", Role.STORE_MANAGER, b1),
            ("cashier_q1", Role.CASHIER, b1),
            ("kitchen_q1", Role.KITCHEN, b1),
            ("manager_q3", Role.STORE_MANAGER, b2),
        ]
        for uname, role, branch in users_data:
            if not User.objects.filter(username=uname).exists():
                User.objects.create_user(username=uname, password="123", role=role, branch=branch)

        cashier_q1 = User.objects.get(username="cashier_q1")
        manager_q3 = User.objects.get(username="manager_q3")

        # 3. MENU: DANH MỤC & MÓN ĂN
        print("3. Đang thiết kế Menu đồ uống & bánh...")
        cat_coffee, _ = Category.objects.get_or_create(name="Cà Phê Truyền Thống")
        cat_tea, _ = Category.objects.get_or_create(name="Trà Trái Cây")
        cat_cake, _ = Category.objects.get_or_create(name="Bánh Ngọt")

        dishes_data = [
            ("Cà phê đen đá", 30000, cat_coffee),
            ("Cà phê sữa đá", 35000, cat_coffee),
            ("Bạc xỉu", 40000, cat_coffee),
            ("Trà đào cam sả", 45000, cat_tea),
            ("Trà ô long hạt sen", 50000, cat_tea),
            ("Tiramisu", 35000, cat_cake),
            ("Bánh sừng trâu", 30000, cat_cake),
        ]
        dishes = []
        for name, price, cat in dishes_data:
            d, _ = Dish.objects.get_or_create(name=name, defaults={'price': Decimal(price), 'category': cat})
            dishes.append(d)

        # 4. KHO & NGUYÊN LIỆU
        print("4. Đang nhập kho nguyên vật liệu...")
        stocks_data = [
            ("Cà phê hạt Robusta", "kg"),
            ("Sữa đặc Ngôi Sao", "lon"),
            ("Đường nước", "lít"),
            ("Ly nhựa size M", "cái"),
        ]
        for s_name, unit in stocks_data:
            si, _ = StockItem.objects.get_or_create(name=s_name, defaults={'unit': unit})
            InventoryItem.objects.get_or_create(branch=b1, stock_item=si,
                                                defaults={'quantity': random.randint(20, 100), 'threshold': 15})
            InventoryItem.objects.get_or_create(branch=b2, stock_item=si,
                                                defaults={'quantity': random.randint(10, 50), 'threshold': 15})

        # 5. ĐƠN HÀNG LỊCH SỬ (100 đơn)
        print("5. Đang đón khách (Tạo 100 đơn hàng lịch sử trong 14 ngày qua)...")
        now = timezone.now()

        for i in range(100):
            branch, cashier = (b1, cashier_q1) if random.random() < 0.7 else (b2, manager_q3)

            days_ago = random.randint(0, 14)
            hour = random.choice([7, 8, 8, 9, 12, 13, 19, 19, 20])
            minute = random.randint(0, 59)
            fake_date = now - timedelta(days=days_ago)
            fake_date = fake_date.replace(hour=hour, minute=minute)

            is_completed = random.random() < 0.9
            status = OrderStatus.COMPLETED if is_completed else OrderStatus.CANCELLED
            payment = PaymentStatus.PAID if is_completed else PaymentStatus.UNPAID
            pay_method = random.choice([PaymentMethod.CASH, PaymentMethod.VIETQR])

            order = Order.objects.create(
                branch=branch, cashier=cashier, order_type=OrderType.TAKEAWAY,
                status=status, payment_status=payment, payment_method=pay_method,
                total_price_snapshot=Decimal('0'), queue_number=i + 1
            )

            Order.objects.filter(id=order.id).update(created_at=fake_date)

            num_items = random.randint(1, 3)
            selected_dishes = random.choices(dishes, k=num_items)
            total = Decimal('0')

            for dish in selected_dishes:
                qty = random.randint(1, 2)
                total += dish.price * qty
                OrderItem.objects.create(
                    order=order, dish=dish, quantity=qty, unit_price_snapshot=dish.price
                )
            Order.objects.filter(id=order.id).update(total_price_snapshot=total)

        # 6. ĐƠN HÀNG REAL-TIME
        print("6. Bếp đang nấu: Tạo 3 đơn hàng PENDING / IN_KITCHEN...")
        for i in range(3):
            active_order = Order.objects.create(
                branch=b1, cashier=cashier_q1, order_type=OrderType.TAKEAWAY,
                status=random.choice([OrderStatus.PENDING, OrderStatus.IN_KITCHEN]),
                payment_status=PaymentStatus.PAID, payment_method=PaymentMethod.CASH,
                total_price_snapshot=dishes[0].price, queue_number=900 + i
            )
            OrderItem.objects.create(order=active_order, dish=dishes[0], quantity=1,
                                     unit_price_snapshot=dishes[0].price)

        print("--- CHÚC MỪNG! HỆ THỐNG ĐÃ FULL DATA ĐỂ BẠN THỬ NGHIỆM! ---")


# Gọi hàm chạy
if __name__ == '__main__':
    run_seeder()