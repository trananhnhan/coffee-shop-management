from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate, TruncHour
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie, vary_on_headers
# Import Model từ app orders
from orders.models import Order, OrderItem, OrderStatus
from accounts.models import Role


class ReportViewSet(viewsets.ViewSet):
    """
    ViewSet này KHÔNG gắn với một Model cụ thể nào.
    Nó đóng vai trò như một Controller chuyên query và tính toán số liệu.
    """
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Hàm cốt lõi: Lọc ra các đơn hàng hợp lệ và CÁCH LY THEO QUYỀN.
        """
        # 1. Chỉ lấy những đơn hàng đã thanh toán hoặc hoàn thành (Tùy logic dự án của bạn)
        # Giả sử bạn có trạng thái 'COMPLETED'
        qs = Order.objects.filter(status=OrderStatus.COMPLETED)

        user = self.request.user

        # 2. Phân quyền dữ liệu (Data Isolation)
        if user.role != Role.OWNER:
            # Quản lý/Nhân viên chỉ được thống kê số liệu nhánh của mình
            qs = qs.filter(branch=user.branch)
        else:
            # Owner có thể xem tất cả, hoặc lọc theo 1 chi nhánh cụ thể
            branch_id = self.request.query_params.get('branch_id')
            if branch_id:
                qs = qs.filter(branch_id=branch_id)

        # 3. Lọc theo thời gian (Ngày bắt đầu -> Ngày kết thúc)
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')

        if start_date:
            qs = qs.filter(created_at__date__gte=start_date)
        if end_date:
            qs = qs.filter(created_at__date__lte=end_date)

        return qs

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """ Khối 1: Tổng quan (Doanh thu, Số đơn, Giá trị TB) """
        qs = self.get_queryset()

        # Câu lệnh này tương đương: SELECT SUM(total), COUNT(id) FROM orders
        stats = qs.aggregate(
            total_revenue=Sum('total_price_snapshot'),
            total_orders=Count('id')
        )

        revenue = stats['total_revenue'] or 0
        orders = stats['total_orders'] or 0
        aov = (revenue / orders) if orders > 0 else 0

        return Response({
            "total_revenue": revenue,
            "total_orders": orders,
            "average_order_value": round(aov, 2)
        })

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=False, methods=['get'], url_path='revenue-chart')
    def revenue_chart(self, request):
        """ Khối 2: Biểu đồ doanh thu theo ngày (Time-series) """
        qs = self.get_queryset()

        # Gom nhóm theo Ngày (TruncDate)
        data = qs.annotate(date=TruncDate('created_at')).values('date').annotate(
            revenue=Sum('total_price_snapshot'),
            orders=Count('id')
        ).order_by('date')

        return Response(data)

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=False, methods=['get'], url_path='peak-hours')
    def peak_hours(self, request):
        """ Khối 2: Biểu đồ Giờ cao điểm (Heatmap) """
        qs = self.get_queryset()

        # Gom nhóm theo Giờ (TruncHour)
        data = qs.annotate(hour=TruncHour('created_at')).values('hour').annotate(
            orders=Count('id')
        ).order_by('hour')

        # Chế biến lại data một chút cho Frontend dễ vẽ Bar Chart
        # Format trả về: [{"hour": "08:00", "orders": 15}, ...]
        formatted_data = [
            {
                "hour": item['hour'].strftime('%H:00'),
                "orders": item['orders']
            } for item in data
        ]

        return Response(formatted_data)

    @method_decorator(cache_page(60 * 15))
    @method_decorator(vary_on_headers('Authorization'))
    @action(detail=False, methods=['get'], url_path='top-items')
    def top_items(self, request):
        """ Khối 3: Top món bán chạy nhất """
        qs = self.get_queryset()

        # Query chéo sang bảng OrderItem, lọc theo các đơn hàng hợp lệ ở trên
        items = OrderItem.objects.filter(order__in=qs).values(
            dish_name=F('dish__name')  # Lấy tên món
        ).annotate(
            total_sold=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('unit_price_snapshot'))
        ).order_by('-total_sold')[:10]  # Chỉ lấy Top 10

        return Response(items)