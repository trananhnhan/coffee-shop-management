---
app: order
file_type: model
depends_on:
  - shared/conventions.md
  - dish/model.md
related_but_optional:
  - inventory/model.md
last_verified: 2026-07-16
---

# Order — Model

## Scope
File này định nghĩa: `Order`, `OrderItem`.
Không bao gồm: business logic tính giá, validate (xem `logic.md`), API contract (xem `api.md`).

## Models

### Order

| Field | Type | Required | Note |
|-------|------|----------|------|
| id | UUID | auto | primary key |
| branch | FK → Branch | yes | chi nhánh tạo order |
| table_number | int | no | null nếu là takeaway |
| status | choice | yes | xem Status enum bên dưới |
| payment_status | choice | yes | tách riêng khỏi order status |
| created_at | datetime | auto | |
| total_price | decimal | auto | snapshot, không tính live |

**Status enum:**
- `pending` → `confirmed` → `preparing` → `served` → `completed`
- `cancelled` (có thể nhảy từ bất kỳ trạng thái nào trước `served`)

### OrderItem

| Field | Type | Required | Note |
|-------|------|----------|------|
| id | UUID | auto | |
| order | FK → Order | yes | |
| dish | FK → Dish | yes | ref tới size variant cụ thể |
| quantity | int | yes | |
| unit_price | decimal | yes | **snapshot tại thời điểm order**, không lấy live từ Dish |

## Relationships
- `Order 1—N OrderItem`
- `OrderItem N—1 Dish` (xem `dish/model.md`)
- `Order N—1 Branch`

## Design decisions
> Giá lưu snapshot trong `OrderItem.unit_price`, không tính lại từ `Dish.price` — tránh sai lệch khi giá món thay đổi sau khi đơn đã tạo.

> `status` và `payment_status` tách 2 field riêng vì 1 đơn có thể `served` nhưng chưa `paid` — gộp chung sẽ tạo state không hợp lệ.

## Migration notes
_(optional — ghi lại nếu có migration đặc biệt, VD đổi kiểu field, data migration cần chạy tay)_

## Related files
- [Order API](./api.md)
- [Order Logic](./logic.md)
- [Dish Model](../dish/model.md)