---
domain: inventory
file_type: constraints
depends_on:

  - account/model.md
last_verified: 2026-07-18
---

# Inventory — Constraints

## Enums

### InventoryItem.unit
`bao | chai | thung | kg | lit | goi`
- Domain-specific, packaging-level unit — deliberately **separate** from `dish/constraints.md` → Unit (`g | kg | ml | l | piece`), which is used only by `dish.Ingredient` for recipe-level measurement. Do not merge these two enums; they serve different granularity (recipe precision vs. real-world stock counting).

### StockRequest.status
`pending | approved | rejected | delivered`

## State Machine

### StockRequest.status
| From | To | Allowed |
|------|----|----|
| pending | approved | ✅ |
| pending | rejected | ✅ |
| approved | delivered | ✅ |
| approved | any other | ❌ |
| rejected | any | ❌ |
| delivered | any | ❌ |

## Field-level Constraints
- `(InventoryItem.branch, InventoryItem.stock_item)` must be unique together.
- `StockItem.name` — normalize to lowercase before save; must be unique.
- `InventoryItem.quantity`, `threshold` — must be >= 0.
- `StockItem.current_price` — must be >= 0 when set.
- `StockRequest.quantity` — must be > 0.
- `StockRequest.unit_price_snapshot` — must be >= 0 when set; immutable once the request is created (not editable after submission, regardless of status).
- `StockRequest.approved_by` / `approved_at` — must both be null when `status = pending`; both must be set when `status = approved` or `rejected`.

## Invariants
_(conditions that must always hold true, regardless of entry point)_
- When `StockRequest.status` transitions to `delivered`, `InventoryItem.quantity` must be incremented by `StockRequest.quantity` as part of the same operation (moved from `approved` → `delivered`).
- When `StockRequest.status` transitions to `approved` and `unit_price_snapshot` differs from `StockItem.unit_price`, update `StockItem.unit_price` to that value in the same operation.
- `StockRequest.unit_price_snapshot` is copied from `StockItem.unit_price` at request creation time — immutable from creation, no longer fillable at approval time.
- `is_low_stock` (`InventoryItem.quantity <= InventoryItem.threshold`) is a computed/derived value, not a stored field — recalculated on read.
- Stock is updated manually by staff (observed/counted in person); there is no automatic deduction tied to any other domain event.

## Cross-domain Constraints
_(rules that depend on another domain's state)_
- `StockRequest.requested_by` and `approved_by` must belong to the same `branch` as `StockRequest.inventory_item.branch` (see `account/constraints.md`).
- **No link to `dish` domain.** `InventoryItem` is fully decoupled from `Ingredient`/`RecipeItem` — no automatic stock deduction when an `Order`/`OrderItem` is created. This is an intentional MVP trade-off: real-world coffee shop operations don't track precise per-gram/ml consumption; inventory is managed at the packaging level and updated manually by staff. See `dish/constraints.md` and `order/constraints.md` for the corresponding notes on the other side of this boundary.

## Related files
- [Inventory Model](./model.md)
- [Inventory Logic](./logic.md)