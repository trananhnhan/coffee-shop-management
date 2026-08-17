# Inventory — API

All primary keys are UUIDs. `StockItem`/`InventoryItem` extend `BaseModel` (soft activate/deactivate). `StockRequest` extends `TimeStampedModel` only — no `is_active`, no activate/deactivate.

---

## list_stock_item / retrieve_stock_item

**Method & Path**: `GET /stock-items/` · `GET /stock-items/<uuid:id>/`

**Permission**: owner or store_manager

**Success Response** — `200 OK`
```json
{ "id": "f1a2...", "name": "milk", "unit": "l", "unit_price": "25000.00", "is_active": true }
```

**Visibility**: owner sees all + `?is_active=true/false`; store_manager sees `is_active=True` only.

---

## create_stock_item

**Method & Path**: `POST /stock-items/`

**Permission**: owner only

**Payload**: `{ "name": "Milk", "unit": "l", "unit_price": 25000 }`

**Success Response** — `201 Created`: `{ "id": "...", "name": "Milk", "unit": "l", "unit_price": "25000.00" }`

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing `unit` | `{ "unit": ["This field is required."] }` |
| 400 | `unit` not in choices | `{ "unit": ["\"x\" is not a valid choice."] }` |
| 400 | `unit_price` negative | `{ "unit_price": ["Ensure this value is greater than or equal to 0.00."] }` |
| 400 | duplicate `name` | `{ "name": ["Stock item with this name already exists."] }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: `name` auto-lowercased on save. `unit_price` is optional (`null=True, blank=True`).

---

## update_stock_item

**Method & Path**: `PATCH /stock-items/<uuid:id>/`

**Permission**: owner or store_manager (per `get_permissions()` — `partial_update` isn't in the owner-only action list)

**Payload**: `{ "name": "Whole Milk", "unit": "l", "unit_price": 27000 }`

**Success Response** — `200 OK`: `{ "name": "Whole Milk", "unit": "l", "unit_price": "27000.00" }`

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | `unit` not in choices | `{ "unit": ["\"x\" is not a valid choice."] }` |
| 400 | `unit_price` negative | `{ "unit_price": ["Ensure this value is greater than or equal to 0.00."] }` |
| 404 | not found | `{ "detail": "Not found." }` |
| 403 | caller role not owner/store_manager | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: `id` and timestamps are excluded from writable fields (`PartialUpdateStockItemSerializer.Meta.fields = ['name', 'unit', 'unit_price']`). This endpoint lets a **store_manager** rename or reprice a stock item — worth double-checking that's intended, since pricing changes here don't go through the `approve()` guard rail that `StockRequest.approve()` uses (that one is store_manager-only too, but tied to a specific pending request rather than a free-form edit).

---

## activate_stock_item / deactivate_stock_item

**Method & Path**: `PATCH /stock-items/<uuid:id>/activate/` · `.../deactivate/`

**Permission**: owner only

**Success Response** — `200 OK`, full `RetrieveStockItemSerializer` output.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | already active/inactive | `{ "detail": "StockItem is already active." }` / `"...already inactive."` |
| 404 | not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

---

## list_inventory_item / retrieve_inventory_item

**Method & Path**: `GET /inventory-items/` · `GET /inventory-items/<uuid:id>/`

**Permission**: any authenticated user

**Success Response** — `200 OK`
```json
{
  "id": "a9b8...",
  "branch": "e29b41d4-...",
  "stock_item": "f1a2...",
  "stock_item_name": "milk",
  "unit": "l",
  "quantity": "12.500",
  "threshold": "5.000",
  "is_low_stock": false
}
```

**Visibility**: owner sees all + `?is_active=true/false`; everyone else sees only their own branch's `is_active=True` items.

---

## update_inventory_item

**Method & Path**: `PATCH /inventory-items/<uuid:id>/`

**Permission**: store_manager or kitchen (`IsStoreManagerOrKitchen`)

**Payload**: `{ "quantity": 15 }`

**Success Response** — `200 OK`: `{ "quantity": "15.000" }`

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | `quantity` negative | `{ "quantity": ["Ensure this value is greater than or equal to 0.000."] }` |
| 404 | not found / outside caller's branch (non-owner) | `{ "detail": "Not found." }` |
| 403 | caller role not store_manager/kitchen | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: only `quantity` is writable — `PartialUpdateInventoryItemSerializer.Meta.fields = ['quantity']`. Any other field in the payload (`threshold`, `branch`, `stock_item`) is silently ignored, not rejected. This is the "physical stock count" endpoint — used for manual inventory correction, not restocking (restocking flows through `StockRequest`).

---

## activate_inventory_item / deactivate_inventory_item

**Method & Path**: `PATCH /inventory-items/<uuid:id>/activate/` · `.../deactivate/`

**Permission**: owner only

Same pattern as `activate_stock_item` — full `RetrieveInventoryItemSerializer` output, 400 on already-active/inactive.

---

## list_stock_request / retrieve_stock_request

**Method & Path**: `GET /stock-requests/` · `GET /stock-requests/<uuid:id>/`

**Permission**: any authenticated user

**Success Response** — `200 OK` (list)
```json
{
  "id": "77c6...",
  "inventory_item": "a9b8...",
  "stock_item_name": "milk",
  "requested_by": "a1b2c3d4-...",
  "quantity": "10.000",
  "status": "pending"
}
```
Retrieve adds `unit_price_snapshot`, `approved_by`, `approved_at`, `created_at`.

**Visibility**: owner sees all branches; everyone else sees only their own branch's requests.

---

## create_stock_request

**Method & Path**: `POST /stock-requests/`

**Permission**: branch staff (store_manager, cashier, or kitchen — `IsBranchStaff`, excludes owner)

**Payload**: `{ "inventory_item": "a9b8...", "quantity": 20 }`

**Success Response** — `201 Created`: `{ "id": "...", "inventory_item": "a9b8...", "quantity": "20.000" }`

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | `quantity` <= 0 | `{ "quantity": ["Ensure this value is greater than or equal to 0.001."] }` |
| 400 | `inventory_item` belongs to a different branch than the caller | `{ "detail": "You can only request stock for your own branch." }` |
| 403 | caller is owner (not branch staff) | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: `requested_by` is always the authenticated user; `unit_price_snapshot` is auto-copied from `StockItem.unit_price` at creation time — neither is client-settable. `status` always starts `pending`.

---

## approve

**Method & Path**: `PATCH /stock-requests/<uuid:id>/approve/`

**Permission**: store_manager only

**Payload**: `{}` or `{ "unit_price_snapshot": 27000 }` (optional — if provided, becomes the new `StockItem.unit_price`)

**Success Response** — `200 OK`, full `RetrieveStockRequestSerializer`, `status: "approved"`.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | request status is not `pending` | `{ "detail": "Only pending requests can be approved." }` |
| 404 | not found / different branch | `{ "detail": "Not found." }` |
| 403 | caller is not store_manager | `{ "detail": "You do not have permission to perform this action." }` |

**Side effect**: if `unit_price_snapshot` in the payload differs from the current `StockItem.unit_price`, the `StockItem`'s base price is updated to match — this changes the price for **future** orders/requests, it does not retroactively change this request's own frozen snapshot from creation.

---

## reject

**Method & Path**: `PATCH /stock-requests/<uuid:id>/reject/`

**Permission**: store_manager only

**Payload**: `{}`

**Success Response** — `200 OK`, `status: "rejected"`.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | request status is not `pending` | `{ "detail": "Only pending requests can be rejected." }` |
| 404 | not found / different branch | `{ "detail": "Not found." }` |
| 403 | caller is not store_manager | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: does not touch `InventoryItem.quantity` or `StockItem.unit_price` — purely a status change. `approved_by`/`approved_at` on the model are still set (reused fields for whoever actioned the request, approve or reject).

---

## deliver

**Method & Path**: `PATCH /stock-requests/<uuid:id>/deliver/`

**Permission**: branch staff (store_manager, cashier, or kitchen)

**Payload**: `{}`

**Success Response** — `200 OK`, `status: "delivered"`.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | request status is not `approved` | `{ "detail": "Only approved requests can be delivered." }` |
| 404 | not found / different branch | `{ "detail": "Not found." }` |
| 403 | caller is not branch staff | `{ "detail": "You do not have permission to perform this action." }` |

**Side effect**: `InventoryItem.quantity` is incremented by the request's `quantity` — this is the only point where physical stock actually increases from a restock (as opposed to `update_inventory_item`, which is a manual correction).

---

## Known permission summary (who can do what)

| Action | Owner | Store Manager | Cashier | Kitchen |
|---|---|---|---|---|
| StockItem read | ✅ (all) | ✅ (active only) | ❌ | ❌ |
| StockItem create/update/activate | ✅ | update only | ❌ | ❌ |
| InventoryItem read | ✅ (all) | ✅ (own branch) | ✅ (own branch) | ✅ (own branch) |
| InventoryItem update (quantity) | ❌ | ✅ (own branch) | ❌ | ✅ (own branch) |
| InventoryItem activate/deactivate | ✅ | ❌ | ❌ | ❌ |
| StockRequest read | ✅ (all) | ✅ (own branch) | ✅ (own branch) | ✅ (own branch) |
| StockRequest create | ❌ | ✅ | ✅ | ✅ |
| StockRequest approve/reject | ❌ | ✅ | ❌ | ❌ |
| StockRequest deliver | ❌ | ✅ | ✅ | ✅ |

**Owner cannot create/approve/reject/deliver stock requests, and cannot touch InventoryItem quantity directly** — consistent with the same "Owner is oversight-only" pattern seen in the Order domain. Flagging for consistency, not as a bug, based on the earlier confirmation that Owner intentionally doesn't do frontline operational work.