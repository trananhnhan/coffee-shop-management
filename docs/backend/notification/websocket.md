# Notification Domain — WebSocket Channel

Tài liệu mô tả kênh **WebSocket** trong domain `notification` — một trong các kênh phát thông báo của hệ thống (bên cạnh các kênh khác có thể bổ sung sau này, ví dụ email qua Gmail SMTP, xem `email.md`).

Dùng Django Channels + Redis channel layer. Kênh này bổ sung cho REST API, dùng để đẩy thông báo tức thời (đơn hàng mới, cập nhật trạng thái món, cảnh báo tồn kho, phiếu nhập kho...) tới các client đang kết nối, thay vì phải polling.

> **Vị trí trong domain:** `notification` không sở hữu business logic tạo ra event — các event được trigger từ domain khác (`order`, `inventory`). Domain `notification` chỉ đóng vai trò kênh phát (channel), tương tự vai trò của `email.md` sau này.

---

## 1. Connection

### Endpoint

```
ws://<domain>/ws/notifications/?token=<JWT_ACCESS_TOKEN>
```

- Giao thức: WebSocket (`ws://` hoặc `wss://` khi có TLS).
- Không có phân biệt endpoint theo branch hay theo resource — chỉ có **một** endpoint duy nhất cho toàn hệ thống. Việc phân luồng dữ liệu (branch nào nhận event nào) được xử lý ở tầng group, không phải ở tầng URL.

### Authentication

- JWT access token được truyền qua **query param** `token`, không phải qua header (do giới hạn của WebSocket handshake trên nhiều client, đặc biệt React Native).
- Xử lý bởi `JWTAuthMiddlewareStack` (custom middleware trong `accounts/ws_middleware.py`), gắn ở tầng ASGI trước khi vào `URLRouter`.
- Nếu token thiếu hoặc không hợp lệ → `self.scope['user']` là `AnonymousUser` → connection bị từ chối ngay trong `connect()` với close code `4001`.

```python
if self.user.is_anonymous:
    await self.close(code=4001)
    return
```

### Origin validation

- Toàn bộ WebSocket route được bọc trong `AllowedHostsOriginValidator`, chặn kết nối từ origin không nằm trong `ALLOWED_HOSTS`.

---

## 2. Groups (Room routing)

Sau khi connect thành công, client được tự động add vào một **group** dựa theo role và branch — client không tự chọn group, không có cơ chế subscribe/unsubscribe thủ công.

| Role | Group name | Ghi chú |
|---|---|---|
| `OWNER` | `admin_global` | Nhận **toàn bộ** event từ mọi chi nhánh |
| Các role khác (Cashier, Kitchen, Store Manager...) có `branch_id` | `branch_{branch_id}` | Chỉ nhận event của chi nhánh mình |
| User không có `branch_id` gán | `unassigned` | Trường hợp fallback, hiện chưa có event nào bắn vào group này |

**Cách ly chi nhánh (branch isolation)** là nguyên tắc cốt lõi: nhân viên chi nhánh A không bao giờ nhận được event của chi nhánh B, chỉ Owner mới nhìn thấy toàn cảnh. Đây là hành vi đã được cover bởi test suite (`test_3_strict_branch_isolation`, `test_4_owner_receives_everything_globally`).

### Lifecycle

- `connect()`: xác thực → xác định group → `group_add` → `accept()`.
- `disconnect()`: `group_discard` khỏi group đã join (dùng `hasattr` để tránh lỗi nếu chưa từng join được, ví dụ do bị reject sớm).
- Không có cơ chế reconnect/resume tự động ở tầng backend — client tự chịu trách nhiệm reconnect khi mất kết nối (nên implement ở phía React Native).

---

## 3. Message format

Mọi event gửi từ server xuống client đều theo cùng một envelope:

```json
{
  "type": "<event_type>",
  "branch_id": "<uuid | null>",
  "data": { ... }
}
```

- `type`: tên event nghiệp vụ (xem bảng catalog bên dưới). **Lưu ý:** đây không phải field `type` dùng nội bộ bởi Channels để định tuyến tới consumer handler (đó là `send_notification`, khớp tên hàm trong `NotificationConsumer`) — hai khái niệm "type" này khác nhau, dễ gây nhầm lẫn khi đọc code nên cần phân biệt rõ trong docs.
- `branch_id`: chi nhánh phát sinh sự kiện (dạng string UUID).
- `data`: payload chi tiết, cấu trúc khác nhau tùy event — xem bảng bên dưới.

Kênh giao tiếp là **one-way (server → client)**. Consumer hiện không xử lý message nào gửi từ client lên (`receive()` chưa được implement) — WebSocket chỉ dùng để nhận thông báo, mọi hành động (tạo đơn, duyệt phiếu...) vẫn đi qua REST API như bình thường.

---

## 4. Event catalog

| Event type | Trigger tại | branch_id nguồn | Payload | Khi nào bắn |
|---|---|---|---|---|
| `order.created` | `CreateOrderSerializer.create()` | `order.branch.id` | Full order object (qua `to_representation`) | Cashier tạo đơn hàng mới |
| `order.updated` | `OrderViewSet.update_kitchen_status()` | `order.branch.id` | Full order object (qua `RetrieveOrderSerializer`) | Kitchen cập nhật trạng thái món trong đơn |
| `inventory.stock_request` | `CreateStockRequestSerializer.create()` | `inventory_item.branch.id` | `request_id, item_name, quantity, requested_by, status` | Branch staff tạo phiếu xin nhập kho |
| `inventory.request_approved` | `StockRequestViewSet.approve()` | `req_obj.inventory_item.branch.id` | `request_id, item_name, status, approved_by` | Store Manager duyệt phiếu |
| `inventory.request_rejected` | `StockRequestViewSet.reject()` | `req_obj.inventory_item.branch.id` | `request_id, item_name, status, rejected_by` | Store Manager từ chối phiếu |
| `inventory.request_delivered` | `StockRequestViewSet.deliver()` | `req_obj.inventory_item.branch.id` | `request_id, item_name, status` | Branch staff xác nhận đã nhận hàng nhập kho |
| `inventory.low_stock` | `InventoryItem.save()` (model layer, không phải view) | `self.branch.id` | `item_id, item_name, current_quantity, threshold` | Tự động, khi tồn kho **chuyển trạng thái** từ an toàn sang dưới ngưỡng |

### Quy ước payload

- **Order events** (`order.created`, `order.updated`) luôn gửi **full snapshot** của order — client có thể dùng trực tiếp để render lại toàn bộ UI đơn hàng mà không cần gọi thêm REST API.
- **Inventory events** chỉ gửi các field tóm tắt cần thiết (delta-style) — client cần tự gọi REST API nếu cần chi tiết đầy đủ hơn.

### Chi tiết logic `inventory.low_stock`

Đây là event duy nhất không bắn từ view/serializer mà từ `save()` của model `InventoryItem`, dựa trên transition logic:

```python
was_safe = not old_instance.is_low_stock   # trạng thái TRƯỚC khi save
is_dangerous_now = self.is_low_stock        # trạng thái SAU khi save

if not is_new and was_safe and is_dangerous_now:
    # chỉ bắn khi vừa "rớt" xuống dưới threshold
```

Ví dụ minh họa (threshold = 5):

| Bước | quantity trước | quantity sau | Bắn event? |
|---|---|---|---|
| 1 | 10 | 8 | Không (vẫn an toàn) |
| 2 | 8 | 3 | **Có** (vừa rớt xuống dưới ngưỡng) |
| 3 | 3 | 1 | Không (đã "unsafe" từ bước 2, không bắn lặp lại) |
| 4 | 1 | 6 | Không (event low_stock không áp dụng cho chiều tăng) |

Thiết kế này tránh spam thông báo mỗi lần quantity thay đổi nhỏ khi đã ở trạng thái nguy hiểm.

---

## 5. Design decisions đáng lưu ý

1. **`transaction.on_commit()` bọc quanh mọi lệnh gọi `broadcast_ws_event`.** Đảm bảo event chỉ được gửi sau khi transaction DB commit thành công — tránh trường hợp client nhận thông báo về một record thực chất đã bị rollback.
2. **`order.created` có try-except riêng quanh phần trigger WebSocket:**
   ```python
   try:
       full_order_data = self.to_representation(order)
       transaction.on_commit(lambda: broadcast_ws_event(...))
   except Exception as e:
       print(f"WebSocket Trigger Error: {e}")
   ```
   Mục đích: nếu serialize lỗi, không được làm sập luồng tạo đơn (đơn vẫn phải được tạo thành công dù real-time notify thất bại). **Known limitation:** đang dùng `print()` thay vì `logging` — nên thay bằng logger chuẩn ở bản production tiếp theo.
3. **Channel layer backend:** Redis, thông qua `channels_redis`. Không xử lý trong tài liệu này (thuộc phần infra/deployment).

---

## 6. Error / edge cases

| Tình huống | Hành vi |
|---|---|
| Kết nối không kèm token, hoặc token invalid/hết hạn | Bị `close(code=4001)` ngay trong `connect()` |
| Origin không nằm trong `ALLOWED_HOSTS` | Bị chặn bởi `AllowedHostsOriginValidator` trước khi tới consumer |
| User có role khác `OWNER` nhưng không có `branch_id` | Vào group `unassigned`, hiện không nhận được event nào |
| Redis channel layer không khả dụng | `broadcast_ws_event` return sớm (`if not channel_layer: return`), không raise lỗi — tránh làm sập request HTTP đi kèm, nhưng đồng nghĩa **notification bị mất âm thầm**, không có retry/queue |

---

## 7. Test coverage

Được cover bởi `ComprehensiveWebSocketTests` (dùng `channels.testing.WebsocketCommunicator`):

- Từ chối kết nối anonymous (không token).
- Cashier nhận đúng event từ chi nhánh của mình.
- Cách ly chi nhánh nghiêm ngặt: chi nhánh B không nhận được event của chi nhánh A.
- Owner nhận được toàn bộ event bất kể nguồn từ chi nhánh nào.

Test hiện **chưa cover**: `order.updated`, `inventory.stock_request`, `inventory.request_rejected`, `inventory.request_delivered` ở tầng WebSocket integration test (mới chỉ cover qua unit test của view/serializer nếu có).