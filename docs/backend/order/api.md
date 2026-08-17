# Order — API

All primary keys are UUIDs. `Order` has no soft activate/deactivate (`TimeStampedModel`, not `BaseModel`) — no `is_active` field at all, and no hard delete either (`http_method_names = ['get', 'post', 'patch']`). Lifecycle is entirely driven by `status`/`payment_status` via the custom actions below.

---

## list_order / retrieve_order

**Method & Path**: `GET /orders/` · `GET /orders/<uuid:id>/`

**Permission**: any authenticated user

**Success Response** — `200 OK` (list item)
```json
{
  "id": "1a2b3c4d-...",
  "branch": "e29b41d4-...",
  "cashier": "a1b2c3d4-...",
  "status": "in_kitchen",
  "order_type": "dine_in",
  "table_number": 5,
  "queue_number": null,
  "payment_status": "unpaid",
  "total_price_snapshot": "65000.00",
  "created_at": "2026-08-16T10:00:00Z"
}
```

**Success Response** — retrieve adds `payment_method`, `updated_at`, and nested `items`:
```json
{
  "...": "same fields as list, plus:",
  "payment_method": "cash",
  "items": [
    {
      "id": "9f8e7d6c-...",
      "dish": "d5e3a4f6-...",
      "dish_name": "cafe sua",
      "quantity": 2,
      "unit_price_snapshot": "30000.00",
      "note": "",
      "kitchen_status": "cooking"
    }
  ],
  "updated_at": "2026-08-16T10:05:00Z"
}
```

**Visibility**
- Owner: sees orders across all branches.
- Everyone else: only orders in their own branch (`get_queryset()` filters by `branch=user.branch`).

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | order not found / belongs to a different branch than caller | `{ "detail": "Not found." }` |

---

## create_order

**Method & Path**: `POST /orders/`

**Permission**: cashier only — not owner, not store_manager, not kitchen.

**Payload — dine-in**
```json
{
  "order_type": "dine_in",
  "table_number": 5,
  "payment_method": "cash",
  "items": [
    { "dish": "d5e3a4f6-...", "quantity": 2, "note": "less sugar" },
    { "dish": "e6f4b5a7-...", "quantity": 1 }
  ]
}
```

**Payload — takeaway** (omit `table_number`; server assigns `queue_number`)
```json
{
  "order_type": "takeaway",
  "payment_method": "vietqr",
  "items": [ { "dish": "d5e3a4f6-...", "quantity": 1 } ]
}
```

**Success Response** — `201 Created` — returns the created `Order` id and the fields on `CreateOrderSerializer.Meta.fields` only (`id`, `order_type`, `table_number`, `payment_method`) — **does not include `items`, `total_price_snapshot`, `status`, `queue_number`, or `branch`/`cashier` in the response body**, even though all of those were computed and saved server-side. Client needs a follow-up `GET /orders/<id>/` to see the full picture.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | dine-in without `table_number` | `{ "detail": "Table number is required for dine-in orders." }` |
| 400 | dine-in `table_number` exceeds branch capacity | `{ "detail": "Table number exceeds branch capacity (<capacity>)." }` |
| 400 | takeaway with `table_number` provided | `{ "detail": "Table number must be null for takeaway orders." }` |
| 400 | empty `items` | `{ "detail": "Order must have at least one item." }` |
| 400 | a dish in `items` is inactive/unavailable/doesn't exist | `{ "dish": ["Dish does not exist or is currently unavailable."] }` (nested under the specific item index) |
| 400 | item `quantity` < 1 | `{ "quantity": ["Ensure this value is greater than or equal to 1."] }` |
| 403 | caller is not cashier | `{ "detail": "You do not have permission to perform this action." }` |

**Server-controlled behavior**
- `branch`/`cashier` are always taken from the authenticated user — never from the payload (not even accepted as input fields).
- `status` is always forced to `pending`, `payment_status` to `unpaid`, regardless of anything sent.
- `queue_number` (takeaway only) is auto-assigned: locks the `Branch` row (`select_for_update()`), then `Max(queue_number)` for that branch/today + 1 — safe under concurrent requests.
- `total_price_snapshot` = sum of `dish.price × quantity` at the moment of creation, using the dish's **current** price.
- `unit_price_snapshot` on each `OrderItem` is frozen at creation time — later price changes on the `Dish` don't retroactively affect this order.
- Whole request is atomic — a failure on any item rolls back the entire order (no partial `Order` with some `OrderItem`s missing).

---

## mark_paid

**Method & Path**: `PATCH /orders/<uuid:id>/mark-paid/`

**Permission**: cashier only

**Payload**: `{}`

**Success Response** — `200 OK`, full `RetrieveOrderSerializer` output with `payment_status: "paid"`, `status: "completed"`.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | order status is not `ready` | `{ "detail": "Order must be READY to be marked as paid." }` |
| 404 | order not found / different branch | `{ "detail": "Not found." }` |
| 403 | caller is not cashier | `{ "detail": "You do not have permission to perform this action." }` |

---

## cancel

**Method & Path**: `PATCH /orders/<uuid:id>/cancel/`

**Permission**: store_manager or cashier

**Payload**: `{}`

**Success Response** — `200 OK`, full `RetrieveOrderSerializer` output with `status: "cancelled"`.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | order status is already `completed` | `{ "detail": "Cannot cancel a completed order." }` |
| 404 | order not found / different branch | `{ "detail": "Not found." }` |
| 403 | caller role not store_manager/cashier | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: cancelling an already-`cancelled` order **succeeds again** (no-op, stays `cancelled`) — only `completed` is blocked. This is intentional, not a bug — confirmed with the model logic (`Order.cancel()` only checks `== COMPLETED`).

---

## update_kitchen_status

**Method & Path**: `PATCH /orders/<uuid:order_id>/items/<uuid:item_id>/kitchen-status/`

**Permission**: kitchen only

**Payload**: `{ "kitchen_status": "cooking" }` (choices: `pending`, `cooking`, `done`)

**Success Response** — `200 OK`, full `RetrieveOrderSerializer` of the **parent order** (not just the item) — reflects the order's recalculated `status` after this item change.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | order not found / different branch | `{ "detail": "Not found." }` |
| 404 | `item_id` doesn't belong to this order | `{ "detail": "Item not found in this order." }` |
| 400 | order is already `cancelled` or `completed` | `{ "detail": "Cannot update items in a <status> order." }` |
| 400 | attempting to change status away from `done` | `{ "detail": "Cannot revert status from DONE." }` |
| 403 | caller is not kitchen | `{ "detail": "You do not have permission to perform this action." }` |

**Side effect**: successfully updating an item's `kitchen_status` triggers `Order.recalculate_status()`:
- all items `pending` → order `status = pending`
- all items `done` → order `status = ready`
- anything mixed → order `status = in_kitchen`

**Note**: setting `done` → `done` again is allowed (not treated as a "revert" since the guard only blocks moving *away from* done, and same-value isn't a change in direction).

---

## Known permission summary (who can do what)

| Action | Owner | Store Manager | Cashier | Kitchen |
|---|---|---|---|---|
| list / retrieve | ✅ (all branches) | ✅ (own branch) | ✅ (own branch) | ✅ (own branch) |
| create | ❌ | ❌ | ✅ | ❌ |
| mark_paid | ❌ | ❌ | ✅ | ❌ |
| cancel | ❌ | ✅ | ✅ | ❌ |
| update_kitchen_status | ❌ | ❌ | ❌ | ✅ |

**Owner has zero operational access to orders** — confirmed intentional per earlier discussion: Owner is an oversight role, and an owner working the counter is expected to log in as staff for that, not act through the Owner account.