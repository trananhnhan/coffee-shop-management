---
domain: account
file_type: constraints
depends_on:
last_verified: 2026-07-27
---

# Account — Constraints

## Enums

Branch status (active | inactive)
### User.role
Role (`owner | store_manager | cashier | kitchen`).
- Superuser/Admin (system troubleshooting: stuck orders, refund/void, stock correction, unlock account) is **not** part of this enum — handled via Django Admin `is_superuser`, outside business RBAC.

### Branch.is_active
Branch status (`active | inactive`).

## State Machine
_(not applicable — no status field with transitions on Branch/User beyond active/inactive toggle)_

## Field-level Constraints
- `User.branch` — must be null when `role = owner`; must NOT be null for `store_manager`, `cashier`, `kitchen`.
- `Branch.table_capacity` — must be > 0.
- `User.username` — must be unique.

## Invariants
_(conditions that must always hold true, regardless of entry point)_
- A `store_manager`, `cashier`, or `kitchen` user can only ever act within the scope of their assigned `branch` — enforced at query/permission level across all domains (see `shared/permissions.py`), not just at the model level here.
- `owner` role has read access across all branches, but must not write data belonging to a branch it wasn't explicitly acting on behalf of (no cross-branch writes).

## Cross-domain Constraints
_(rules that depend on another domain's state)_
- `Order.cashier`, `StockRequest.requested_by`, `StockRequest.approved_by` — all reference `User`; the referenced user's `branch` must match the `branch` of the `Order`/`StockRequest`/`InventoryItem` involved (branch-scope integrity). See `order/constraints.md` and `inventory/constraints.md`.

## Related files
- [Account Model](./model.md)
- [Account Logic](./logic.md)