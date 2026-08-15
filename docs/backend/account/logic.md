---
domain: account
file_type: logic
depends_on:
  - account/model.md
  - account/constraints.md
last_verified: 2026-07-18
---

# Account — Logic

## Scope
This file defines: step-by-step business processes for `Branch`/`User` that don't fit as a static rule in `constraints.md`.
Does NOT include: field definitions (see `model.md`), enums/invariants (see `constraints.md`), endpoint shapes (see `api.md`).

## Process: Create a Branch

1. Only `owner` can create a new `Branch` (see `account/constraints.md`).
2. Required at creation: `name`, `address`, `table_capacity`. `phone` optional.
3. New branch starts with `is_active = true`.
4. Creating a branch does **not** automatically create a `store_manager` for it — that's a separate step (see next process).

## Process: Create a staff User (Cashier / Kitchen / Store Manager)

1. Only `owner` or `store_manager` can create staff accounts.
2. `owner` creating a user: must explicitly assign `branch` and `role`. Can assign any role including `store_manager`.
3. `store_manager` creating a user: `branch` is **forced to the manager's own branch** (not selectable by the manager — prevents cross-branch account creation); can only assign `role = cashier` or `role = kitchen`, never `store_manager` or `owner`.
4. `role = owner` accounts are not created through this flow — reserved for initial system setup (e.g. Django `createsuperuser` or a seed script), not exposed via a regular "create user" API.
5. Reject creation if `branch.is_active = false`.

## Process: Deactivate a User

1. `store_manager` can deactivate `cashier`/`kitchen` users within their own branch. `owner` can deactivate any user.
2. Sets `is_active = false` — soft action, not a hard delete (see `shared/conventions.md` soft-delete pattern).
3. A deactivated user must be rejected at authentication (cannot log in), but their historical references (`Order.cashier`, `StockRequest.requested_by`/`approved_by`) remain intact — never cascade-delete related records.

## Process: Enforce branch-scope on every request

1. This is the central cross-cutting rule referenced by every other domain's constraints (`order`, `inventory`).
2. On every authenticated request, resolve `current_user.branch`:
   - `owner` (branch = null): read access across all branches; write access only within a branch they are explicitly acting in the context of for that request (no implicit cross-branch write).
   - `store_manager` / `cashier` / `kitchen`: every query is filtered by `branch = current_user.branch`, both for reads and writes — enforced once centrally (e.g. a shared permission/query mixin in `shared/permissions.py`), not re-implemented per domain.
3. This process is the reason `Order.branch`, `InventoryItem.branch`, etc. must always match the acting user's branch — see the "Cross-domain Constraints" sections in `order/constraints.md` and `inventory/constraints.md`.

## Related files
- [Account Model](./model.md)
- [Account Constraints](./constraints.md)
- [Account API](./api.md)