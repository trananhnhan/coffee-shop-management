---
file_type: permissions
scope: shared
depends_on:
  - account/model.md
  - account/constraints.md
last_verified: 2026-07-18
---

# Shared — Permissions

## Standard roles
See `account/constraints.md` → Role for the canonical list: `owner | store_manager | cashier | kitchen`.

- `owner` — read access across all branches; write access only within the branch context of the current action, never cross-branch. Can create branches and assign `store_manager`.
- `store_manager` — full access within their own branch only (`user.branch`, fixed at account creation). Manages staff, inventory, approves stock requests.
- `cashier` — create/manage `Order`, handle payment, within their own branch.
- `kitchen` — update `OrderItem.kitchen_status`, within their own branch.
- Superuser/Admin — **not** part of this role set. Handled via Django Admin (`is_superuser`) for operational fixes (stuck orders, refunds, stock corrections). Not exposed through the app's business permission classes below.

## Base permission classes (reusable)
- `IsBranchMember` — checks the requesting user's `branch` matches the `branch` of the object/resource being acted on. Central enforcement of branch-scope isolation (see `account/logic.md` → "Enforce branch-scope on every request").
- `IsOwner` — read-only across branches; blocks write outside the acting branch context.
- `IsStoreManager` — full access, restricted to `request.user.branch`.
- `IsCashier`, `IsKitchen` — role-specific write access, restricted to `request.user.branch`.

## Usage
A domain that relies on these standard classes only needs to declare which classes apply per endpoint in its own `api.md` — do not re-implement branch-scope or role-check logic inside individual domain apps.

## Related files
- [Shared Enums](./enums.md)
- [Account Model](../account/model.md)
- [Account Logic](../account/logic.md)