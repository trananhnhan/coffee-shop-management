# Account — API

---

## create_branch

**Method & Path**: `POST /branches/`

**Permission**: owner only

**Payload**
```json
{
  "name": "District 1 Branch",
  "address": "123 Nguyen Hue, D1",
  "phone": "0901234567",
  "table_capacity": 20
}
```

**Success Response** — `201 Created`
```json
{
  "id": 3,
  "name": "District 1 Branch",
  "address": "123 Nguyen Hue, D1",
  "phone": "0901234567",
  "table_capacity": 20,
  "is_active": true
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing required field (name/address/table_capacity) | `{ "error": "name is required" }` |
| 400 | table_capacity <= 0 | `{ "error": "table_capacity must be greater than 0" }` |
| 403 | caller is not owner | `{ "error": "permission denied" }` |

---

## update_branch

**Method & Path**: `PATCH /branches/<id>/`

**Permission**: owner only

**Payload**
```json
{
  "name": "District 1 Branch (renamed)",
  "phone": "0909999999",
  "table_capacity": 25
}
```

**Success Response** — `200 OK`
```json
{
  "id": 3,
  "name": "District 1 Branch (renamed)",
  "address": "123 Nguyen Hue, D1",
  "phone": "0909999999",
  "table_capacity": 25,
  "is_active": true
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | branch not found | `{ "error": "not found" }` |
| 400 | table_capacity <= 0 | `{ "error": "table_capacity must be greater than 0" }` |
| 403 | caller is not owner | `{ "error": "permission denied" }` |

---

## deactivate_branch

**Method & Path**: `PATCH /branches/<id>/deactivate/`

**Permission**: owner only

**Payload**
```json
{}
```

**Success Response** — `200 OK`
```json
{
  "id": 3,
  "is_active": false
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | branch not found | `{ "error": "not found" }` |
| 403 | caller is not owner | `{ "error": "permission denied" }` |

**Side Effects**
- Soft action — sets `is_active = false` only, does not cascade-deactivate `User`/`Order`/`InventoryItem` records tied to this branch.
- New staff creation and new orders for this branch should be rejected while inactive (see `create_user`, `order` domain).

---

## create_user

**Method & Path**: `POST /users/`

**Permission**: owner or store_manager (branched logic based on caller's role, see Side Effects)

**Payload**
```json
{
  "username": "cashier01",
  "password": "********",
  "role": "cashier",
  "branch": 3
}
```

**Success Response** — `201 Created`
```json
{
  "id": 15,
  "username": "cashier01",
  "role": "cashier",
  "branch": 3,
  "is_active": true
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing username/password/role | `{ "error": "role is required" }` |
| 400 | username already exists | `{ "error": "username already exists" }` |
| 400 | branch.is_active = false | `{ "error": "cannot create user for an inactive branch" }` |
| 403 | store_manager attempts to assign role=store_manager/owner | `{ "error": "store_manager can only create cashier or kitchen accounts" }` |
| 403 | caller role is not owner/store_manager | `{ "error": "permission denied" }` |
| 403 | role=owner requested through this endpoint | `{ "error": "owner accounts cannot be created through this endpoint" }` |

**Side Effects**
- If caller is `owner`: uses `branch`/`role` exactly as sent, any value allowed except `role = owner`.
- If caller is `store_manager`: server forces `branch` = caller's own branch (ignores any `branch` sent by client), only accepts `role = cashier` or `role = kitchen`.

---

## update_user

**Method & Path**: `PATCH /users/<id>/`

**Permission**: owner (any user) or store_manager (only cashier/kitchen within their own branch)

**Payload**
```json
{
  "username": "cashier01-renamed"
}
```

**Success Response** — `200 OK`
```json
{
  "id": 15,
  "username": "cashier01-renamed",
  "role": "cashier",
  "branch": 3,
  "is_active": true
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | user not found | `{ "error": "not found" }` |
| 400 | username already exists | `{ "error": "username already exists" }` |
| 403 | store_manager tries to update a user outside their branch | `{ "error": "permission denied" }` |
| 403 | store_manager tries to update a store_manager/owner account | `{ "error": "permission denied" }` |
| 403 | request includes `role` or `branch` change | `{ "error": "role and branch cannot be changed through this endpoint" }` |

**Side Effects**
- `role` and `branch` are not editable here — reassigning role/branch is out of scope for MVP (would need a separate dedicated flow if required later).

---

## deactivate_user

**Method & Path**: `PATCH /users/<id>/deactivate/`

**Permission**: owner (any user) or store_manager (only cashier/kitchen within their own branch)

**Payload**
```json
{}
```

**Success Response** — `200 OK`
```json
{
  "id": 15,
  "username": "cashier01",
  "is_active": false
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | user not found | `{ "error": "not found" }` |
| 403 | store_manager deactivates a user outside their branch | `{ "error": "permission denied" }` |
| 403 | store_manager deactivates a store_manager/owner account | `{ "error": "permission denied" }` |

**Side Effects**
- Soft action — sets `is_active = false` only, does not cascade-delete `Order.cashier`, `StockRequest.requested_by`/`approved_by`.
- Deactivated user is rejected at login going forward.