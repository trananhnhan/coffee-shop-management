---
domain: order
file_type: constraints
depends_on:
  - account/model.md
last_verified: 2026-07-18
---

# Order — Constraints

## Enums

### Order.status
`pending | in_kitchen | ready | completed | cancelled`
- Derived from the aggregate of `OrderItem.kitchen_status`, except `completed` (manual, cashier action) and `cancelled` (manual, any role with permission).

### Order.order_type
`dine_in | takeaway`

### Order.payment_method
`cash | vietqr`

### Order.payment_status
`unpaid | paid`

### OrderItem.kitchen_status
`pending | cooking | done`
- No history/log of transitions kept — current value only (explicit MVP trade-off).

## State Machine

### Order.status
pending → in_kitchen → ready → completed
↘ cancelled (from any state before completed)
| From | To | Allowed |
|------|----|----|
| pending | in_kitchen | ✅ (derived: at least one OrderItem = cooking, OR a mix of pending/done not all done) |
| in_kitchen | ready | ✅ (derived: all OrderItem = done) |
| ready | completed | ✅ (manual, cashier marks paid) |
| any (before completed) | cancelled | ✅ |
| completed | any | ❌ |

### OrderItem.kitchen_status
pending → cooking → done
- No backward transitions.

## Field-level Constraints
- `Order.table_number` — required and must be `<= Branch.table_capacity` when `order_type = dine_in`; must be null when `order_type = takeaway`.
- `Order.queue_number` — required when `order_type = takeaway`; must be null when `order_type = dine_in`; auto-incremented per branch per day (resets at midnight, not a global counter).
- `Order.cashier.branch` — must equal `Order.branch` (cashier can't create orders for a branch they don't belong to).
- `OrderItem.quantity` — must be > 0.
- `OrderItem.unit_price_snapshot` — set once at creation, immutable afterward even if `Dish.price` changes later.

## Invariants
_(conditions that must always hold true, regardless of entry point)_
- Sum of `OrderItem.unit_price_snapshot * quantity` across all items of an order must equal `Order.total_price_snapshot`.
- `Order.total_price_snapshot` is fixed once set — not recalculated live from current `Dish.price`.
- Cannot delete an `Order`/`OrderItem` once `payment_status = paid` — cancel only, no hard delete.

## Cross-domain Constraints
_(rules that depend on another domain's state)_
- `Order.branch` must match `Order.cashier.branch` (see `account/constraints.md`).
- `OrderItem.dish` must reference a `Dish` with `is_available = true` **and** `is_active = true` at the time the order is created (see `dish/constraints.md`).
- No automatic interaction with `inventory` domain — creating an `Order`/`OrderItem` does **not** deduct `InventoryItem.quantity`. Inventory is tracked manually, independent of orders (see `inventory/constraints.md`).

## Related files
- [Order Model](./model.md)
- [Order Logic](./logic.md)