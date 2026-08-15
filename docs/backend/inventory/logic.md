---
domain: inventory
file_type: logic
depends_on:
  - inventory/model.md
  - inventory/constraints.md
  - account/model.md
last_verified: 2026-07-18
---

# Inventory — Logic

## Scope
This file defines: step-by-step business processes for `InventoryItem`/`StockRequest` that don't fit as a static rule in `constraints.md`.
Does NOT include: field definitions (see `model.md`), enums/invariants (see `constraints.md`), endpoint shapes (see `api.md`).

## Process: Compute `is_low_stock` (derived, not stored)

1. Not a DB field — computed on read.
2. Rule: `is_low_stock = InventoryItem.quantity <= InventoryItem.threshold`.
3. Recommended implementation: annotate in queryset (e.g. Django `annotate` with `Case/When`, or a `@property` on the model) rather than storing/syncing a boolean field — avoids staleness.
4. Exposed in list/detail API responses so frontend can show a warning badge without extra calls.

## Process: Manual stock update (staff correction)

1. Staff (store_manager or kitchen, same branch) directly edits `InventoryItem.quantity` after physically checking stock — no approval needed for this direct edit.
2. This is separate from `StockRequest` — `StockRequest` is for **requesting new stock to be purchased/brought in**, not for correcting a miscount.
3. This direct edit does **not** touch `InventoryItem.unit_price` — price is only updated via the `StockRequest` approval flow below.
4. No history/log kept of manual quantity edits (same MVP trade-off as `OrderItem.kitchen_status` — current value only).

## Process: Create `StockRequest`

1. Triggered by staff (any role, same branch as the `InventoryItem`) noticing `is_low_stock = true`, or proactively requesting more stock regardless of threshold.
2. Validate `requested_by.branch == inventory_item.branch` (see `constraints.md` cross-domain rule).
3. `unit_price_snapshot` is auto-copied from `StockItem.unit_price` at creation time — not staff-entered, not optional anymore.
4. Create `StockRequest` with `status = pending`, `approved_by = null`, `approved_at = null`.
5. No automatic notification/push required for MVP — store_manager checks pending requests manually via list view.

## Process: Approve / Deliver / Reject `StockRequest`

1. **Approve/Reject**: only `store_manager` of the same branch (owner is read-only, cashier/kitchen have no approval permission).
2. **Deliver**: any staff of the same branch — `store_manager`, `cashier`, or `kitchen` (owner excluded, read-only).

### On approve
- Allowed only when `status = pending`.
- Set `status = approved`, `approved_by = <current user>`, `approved_at = now()`.
- If `StockRequest.unit_price_snapshot` differs from `StockItem.unit_price`, update `StockItem.unit_price` to that value in the same operation (source catalog reflects the newly agreed price).
- **No change** to `InventoryItem.quantity` at this stage (goods haven't physically arrived).

### On deliver
- Allowed only when `status = approved`.
- Set `status = delivered`.
- In the same transaction:
  - Increment `InventoryItem.quantity` by `StockRequest.quantity`.
- All writes must succeed together — wrap in a DB transaction to avoid a request marked `delivered` without stock actually being updated.

### On reject
- Allowed from `pending` only.
- Set `status = rejected`, `approved_by = <current user>`, `approved_at = now()`.
- No change to `InventoryItem.quantity` or `StockItem.unit_price`.

5. Once `delivered` or `rejected`, the request is terminal — no further edits, including `unit_price_snapshot` (see `constraints.md` state machine).

## Related files
- [Inventory Model](./model.md)
- [Inventory Constraints](./constraints.md)
- [Inventory API](./api.md)