---
domain: inventory
covers: [StockItem, InventoryItem, StockRequest]
depends_on: [accounts.models.Role, accounts.permissions]
status: draft
---

# Test Plan: Inventory Domain

## Scope
`StockItem`, `InventoryItem`, `StockRequest` — models, serializers, views (RBAC + actions).

---

## Tầng 1 — Model constraints

| Model | Field/Rule | Test case | Expected |
|---|---|---|---|
| StockItem | `name` | tạo 2 bản ghi trùng tên | lỗi (unique) |
| StockItem | `name` | tạo "Cà Phê" | lưu thành "cà phê" (auto lowercase) |
| StockItem | `unit` | giá trị ngoài `InventoryUnit.choices` | lỗi khi `full_clean()` |
| StockItem | `unit_price` | null/blank | tạo không truyền giá vẫn OK |
| StockItem | `unit_price` | giá trị âm | lỗi (MinValueValidator 0.00) |
| InventoryItem | `(branch, stock_item)` | tạo trùng cặp | lỗi (unique_together) |
| InventoryItem | `quantity` | âm | lỗi |
| InventoryItem | `threshold` | âm | lỗi |
| InventoryItem | `is_low_stock` | quantity == threshold | True |
| InventoryItem | `is_low_stock` | quantity > threshold | False |
| InventoryItem | `is_low_stock` | quantity < threshold | True |
| InventoryItem | FK `stock_item` (PROTECT) | xóa StockItem đang được reference | raise `ProtectedError` |
| StockRequest | `quantity` | = 0 | lỗi (MinValueValidator 0.001) |
| StockRequest | `unit_price_snapshot` | âm | lỗi |
| StockRequest | `status` | tạo mới không truyền | default = PENDING |
| StockRequest | FK `requested_by`/`approved_by` (PROTECT) | xóa User đang được reference | lỗi |
| StockRequest | `approved_by`/`approved_at` | tạo mới | mặc định None |

---

## Tầng 2 — Model business logic (state transitions)

### `StockRequest.approve()`
- [ ] PENDING → APPROVED: status đổi đúng, `approved_by`/`approved_at` được set
- [ ] Not PENDING (APPROVED/REJECTED/DELIVERED) → gọi lại → raise `ValueError`
- [ ] `final_unit_price` khác giá cũ → `StockItem.unit_price` được update
- [ ] `final_unit_price=None` hoặc bằng giá cũ → `StockItem.unit_price` giữ nguyên

### `StockRequest.deliver()`
- [ ] APPROVED → DELIVERED: `InventoryItem.quantity` cộng dồn đúng số lượng request
- [ ] Not APPROVED → raise `ValueError`
- [ ] Gọi deliver() 2 lần liên tiếp → lần 2 lỗi, quantity không bị cộng đúp

### `StockRequest.reject()`
- [ ] PENDING → REJECTED: `approved_by` được set, quantity/unit_price KHÔNG đổi
- [ ] Not PENDING → raise `ValueError`

---

## Tầng 3 — Serializer

### StockItem
- [ ] `ListStockItemSerializer`/`RetrieveStockItemSerializer`: toàn bộ field readonly
- [ ] `CreateStockItemSerializer`: thiếu `unit` → 400
- [ ] `CreateStockItemSerializer`: `unit` ngoài choices → 400
- [ ] `PartialUpdateStockItemSerializer`: update `name`/`unit`/`unit_price` thành công, trả đúng giá trị mới
- [ ] `PartialUpdateStockItemSerializer`: `unit` ngoài choices → 400
- [ ] `PartialUpdateStockItemSerializer`: `unit_price` âm → 400
- [ ] `PartialUpdateStockItemSerializer`: `id`/`created_at`/`updated_at` không nằm trong payload writable — gửi kèm cũng bị ignore

### InventoryItem
- [ ] `List`/`Retrieve`: `stock_item_name`, `unit` lấy đúng từ `stock_item` liên kết (nested source)
- [ ] `is_low_stock` trả đúng giá trị theo data thực tế
- [ ] `PartialUpdateInventoryItemSerializer`: chỉ `quantity` được update — gửi kèm `threshold`/`branch` trong payload phải bị ignore, không lỗi và không update

### StockRequest — CreateStockRequestSerializer
- [ ] Case chính: `inventory_item` thuộc branch user → tạo thành công
- [ ] **[MUST-HAVE / bảo mật]** user branch A tạo request cho `inventory_item` thuộc branch B → `ValidationError` với `{"detail": "..."}`
- [ ] `unit_price_snapshot` sau create() khớp đúng `stock_item.unit_price` tại thời điểm tạo (test snapshot: đổi giá gốc sau đó, snapshot cũ giữ nguyên)
- [ ] `requested_by` tự động gán = user đang login, client truyền field khác trong payload bị ignore
- [ ] `inventory_item` id không tồn tại → 400 (DRF PK field validation)

### StockRequest — ApproveStockRequestSerializer
- [ ] Truyền `unit_price_snapshot` mới → action `approve` truyền đúng vào `approve(final_unit_price=...)` (verify không bypass model method)

---

## Tầng 4 — View / Permission (RBAC)

### StockItemViewSet
- [ ] `create`/`activate`/`deactivate`: chỉ `IsOwner` — role khác → 403
- [ ] `list`/`retrieve`/`partial_update`: `IsOwnerOrStoreManager` — role ngoài 2 role này → 403
- [ ] `partial_update` thành công cho cả Owner lẫn Store Manager (đã fix — trước đây bị no-op do thiếu serializer)
- [ ] Owner truyền `is_active=true/false` → filter đúng
- [ ] Non-owner (Store Manager) không thấy item `is_active=False` dù cố truyền query param
- [ ] `http_method_names` giới hạn ['get','post','patch'] — gọi DELETE → 405

### InventoryItemViewSet
- [ ] `list`/`retrieve`: mọi user đã login đều gọi được (IsAuthenticated), nhưng queryset tự lọc theo branch
- [ ] `partial_update`: chỉ `IsStoreManagerOrKitchen` — role khác → 403
- [ ] `activate`/`deactivate`: chỉ `IsOwner` → role khác 403
- [ ] Non-owner chỉ thấy `InventoryItem` của branch mình + `is_active=True`
- [ ] Owner thấy toàn bộ, filter `is_active` hoạt động đúng
- [ ] User branch A gọi `retrieve` id thuộc branch B → 404 (do queryset đã lọc branch, không phải 403)

### StockRequestViewSet
- [ ] `create`: chỉ `IsBranchStaff` — role khác → 403
- [ ] `approve`/`reject`: chỉ `IsStoreManager` — role khác (kể cả BranchStaff) → 403
- [ ] `deliver`: chỉ `IsBranchStaff` — Store Manager gọi → 403 (xác nhận đúng phân quyền nhận hàng vs duyệt đơn)
- [ ] Non-owner chỉ thấy StockRequest thuộc branch mình qua `list`
- [ ] User branch A gọi `approve`/`reject`/`deliver` trên request id thuộc branch B → 404 (do get_queryset lọc branch trước get_object)
- [ ] `approve` action: verify gọi đúng qua `req_obj.approve()`, không gán trực tiếp field → trạng thái PENDING mới approve được, state khác → 400 `{"detail": "..."}`
- [ ] `reject`/`deliver` action tương tự: trả đúng 400 `{"detail": "..."}` khi sai state

---

## Known issues / cần lưu ý khi test
- `StockRequest.approved_by` dùng chung cho cả action approve và reject (field naming dễ nhầm là "người duyệt" dù có thể là người từ chối) — không phải bug, nhưng test phải assert đúng ngữ cảnh, và cân nhắc note lại cho FE khi hiển thị.
- Action `approve` lấy `final_price` qua `serializer.validated_data.get('unit_price_snapshot', None)` — nếu client không gửi gì thì mặc định None, đúng behavior "giữ giá cũ" của model method. Đã verify không bypass, an toàn.