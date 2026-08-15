---
domain: order
file_type: logic
depends_on:
  - order/model.md
  - order/constraints.md
  - account/model.md
last_verified: 2026-07-18
---

# Order — Logic

## Scope
This file defines: step-by-step business processes for `Order`/`OrderItem` that don't fit as a static rule in `constraints.md`.
Does NOT include: field definitions (see `model.md`), enums/invariants (see `constraints.md`), endpoint shapes (see `api.md`).

## Process: Derive `Order.status` from `OrderItem.kitchen_status`

Triggered whenever any `OrderItem.kitchen_status` changes (e.g. kitchen marks an item `done` via WebSocket).

1. Fetch all `OrderItem` rows for the parent `Order`.
2. Apply rules in this priority order:
   - If all items are `pending` → `Order.status = pending`
   - Else if at least one item is `cooking` OR a mix of `pending`/`done` (not all done) → `Order.status = in_kitchen`
   - Else if all items are `done` → `Order.status = ready`
3. `completed` is **never** set by this derivation — only by the manual "mark paid" action (see below).
4. `cancelled` is **never** set by this derivation — only by explicit cancel action (see below).
5. This derivation runs server-side after every `kitchen_status` update; push the resulting `Order.status` to the cashier view via WebSocket (same channel used for Cashier ↔ Kitchen sync).

## Process: Create Order (Cashier)

1. Cashier submits `order_type`, `table_number` or nothing (queue_number is system-generated, not submitted), and a list of `(dish, quantity, note)`.
2. Validate `cashier.branch` — reject if cashier has no branch or branch mismatch with request context.
3. If `order_type = dine_in`:
   - `table_number` required, must be `<= branch.table_capacity`.
   - `queue_number` left null.
4. If `order_type = takeaway`:
   - `table_number` left null.
   - Compute `queue_number` (see next process).
5. For each `(dish, quantity, note)`:
   - Look up `Dish`, reject if `is_available = false`.
   - Create `OrderItem` with `unit_price_snapshot = dish.price` (copied at this moment, not referenced live).
6. Compute `Order.total_price_snapshot = sum(unit_price_snapshot * quantity)` across created items.
7. Set `Order.status = pending`, `payment_status = unpaid`.
8. Push new order to Kitchen display via WebSocket.

## Process: Compute `queue_number`

1. Scope: per `branch`, per calendar day (resets daily, not a global running counter).
2. On order creation with `order_type = takeaway`:
   - `queue_number = count(Order where branch = X, order_type = takeaway, created_at date = today) + 1`
3. Reset happens implicitly — no cron job needed, since the count naturally restarts each day by filtering on `created_at` date.
4. Concurrency note: if two takeaway orders are created at the same instant, this count-based approach can race. For MVP scale (single branch counter, low concurrency), acceptable; flag as known limitation, not solved with a DB sequence/lock.

## Process: Mark Order as paid (Cashier)

1. Only allowed when `Order.status = ready` (all items done) — reject otherwise.
2. Set `payment_status = paid`, `Order.status = completed`.
3. `total_price_snapshot` is not recalculated — already fixed at creation time.
4. Once `completed`, no further status transitions allowed (see `constraints.md` state machine).

## Process: Cancel Order

1. Allowed from any `Order.status` before `completed` (see `constraints.md`).
2. Permission: only `cashier` or `store_manager` belonging to the **same branch** as the order. `owner` has read-only access (see `account/constraints.md`), so cannot cancel.
3. Set `Order.status = cancelled`.
4. No inventory/stock rollback — since `inventory` is decoupled from `order`, there's nothing to reverse there.

## Related files
- [Order Model](./model.md)
- [Order Constraints](./constraints.md)
- [Order API](./api.md)