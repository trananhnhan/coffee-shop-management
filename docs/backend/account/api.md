# Accounts — API

All primary keys are UUIDs (`TimeStampedModel.id = UUIDField(default=uuid.uuid4)`), not integers.

---

## list_branch

**Method & Path**: `GET /branches/`

**Permission**: owner only

**Query Params**
| Param | Values | Effect |
|---|---|---|
| `is_active` | `true` / `false` | filters by active state; any other value or omitted → no filter (all branches) |

**Success Response** — `200 OK`
```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
      "name": "district 1 branch",
      "address": "123 Nguyen Hue, D1",
      "phone": "0901234567",
      "table_capacity": 20,
      "is_active": true
    }
  ]
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

---

## retrieve_branch

**Method & Path**: `GET /branches/<uuid:id>/`

**Permission**: owner only

**Success Response** — `200 OK`
```json
{
  "id": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "name": "district 1 branch",
  "address": "123 Nguyen Hue, D1",
  "phone": "0901234567",
  "table_capacity": 20,
  "is_active": true,
  "created_at": "2026-08-01T09:00:00Z",
  "updated_at": "2026-08-01T09:00:00Z"
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | branch not found | `{ "detail": "Not found." }` |
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

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
  "id": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "name": "District 1 Branch",
  "address": "123 Nguyen Hue, D1",
  "phone": "0901234567",
  "table_capacity": 20
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing required field (name/address/table_capacity) | `{ "<field>": ["This field is required."] }` |
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**
- `table_capacity <= 0` is **not currently validated** — the model field is a plain `IntegerField` with no `MinValueValidator`. Currently accepts 0 or negative values.
- `phone` is optional (`null=True, blank=True`).
- `id` is server-generated (`uuid.uuid4`), any `id` in the payload is ignored.

---

## update_branch

**Method & Path**: `PATCH /branches/<uuid:id>/`

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
  "name": "District 1 Branch (renamed)",
  "address": "123 Nguyen Hue, D1",
  "phone": "0909999999",
  "table_capacity": 25
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | branch not found | `{ "detail": "Not found." }` |
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: same `table_capacity` validation gap as `create_branch`.

---

## activate_branch / deactivate_branch

**Method & Path**: `PATCH /branches/<uuid:id>/activate/` · `PATCH /branches/<uuid:id>/deactivate/`

**Permission**: owner only

**Payload**: `{}`

**Success Response** — `200 OK` — full `RetrieveBranchSerializer` output (not just `id`/`is_active`), since `BranchViewSet.get_serializer_class()` has no special case for `activate`/`deactivate` and falls through to the default:
```json
{
  "id": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "name": "district 1 branch",
  "address": "123 Nguyen Hue, D1",
  "phone": "0901234567",
  "table_capacity": 20,
  "is_active": false,
  "created_at": "2026-08-01T09:00:00Z",
  "updated_at": "2026-08-05T14:30:00Z"
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | branch not found | `{ "detail": "Not found." }` |
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |
| 400 | branch is already active/inactive | `{ "detail": "Branch is already active." }` or `{ "detail": "Branch is already inactive." }` |

**Side Effects**
- Soft action — sets `is_active` only via `BaseModel.activate()`/`deactivate()`, does **not** cascade to `User`/`Order`/`InventoryItem` records tied to this branch.
- Calling `activate` on an already-active branch (or `deactivate` on an already-inactive one) raises `ValueError` in the model, caught by the mixin and returned as `400`, not a silent no-op.

---

## list_user

**Method & Path**: `GET /users/`

**Permission**: owner or store_manager

**Success Response** — `200 OK`, paginated, each item:
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "is_active": true
}
```

**Visibility**
- Owner: sees all users, `?is_active=true/false` filter available.
- Store Manager: sees only users in their own branch, and only `is_active=true` (no filter override).

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 403 | caller role not owner/store_manager | `{ "detail": "You do not have permission to perform this action." }` |

---

## retrieve_user

**Method & Path**: `GET /users/<uuid:id>/`

**Permission**: owner or store_manager

Same visibility scoping as `list_user` — a store_manager requesting a user outside their branch (or an inactive one) gets `404`, not `403` (filtered out by `get_queryset()` before the object is even fetched).

**Success Response** — `200 OK`
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "is_active": true,
  "created_at": "2026-08-01T09:00:00Z",
  "updated_at": "2026-08-01T09:00:00Z"
}
```

---

## create_user

**Method & Path**: `POST /users/`

**Permission**: owner or store_manager

**Payload**
```json
{
  "username": "cashier01",
  "password": "********",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f"
}
```

**Success Response** — `201 Created`
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f"
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing username/password/role | `{ "<field>": ["This field is required."] }` |
| 400 | username already exists | `{ "username": ["A user with that username already exists."] }` |
| 400 | store_manager assigns role other than cashier/kitchen | `{ "detail": "Store manager can only assign cashier or kitchen roles." }` |
| 400 | owner creates staff (non-owner role) without branch | `{ "detail": "Branch is required for staff accounts." }` |
| 403 | caller role is not owner/store_manager | `{ "detail": "You do not have permission to perform this action." }` |

**Side Effects / behavior**
- If caller is `store_manager`: server **forces `branch` = caller's own branch**, silently overriding any `branch` sent in the payload (not an error — just ignored). Only `role = cashier` or `role = kitchen` accepted, anything else → 400.
- If caller is `owner`: **`role = owner` is allowed** through this endpoint, with no branch required for that case. Any other role still requires a branch.

---

## update_user

**Method & Path**: `PATCH /users/<uuid:id>/`

**Permission**: owner (any target) or store_manager (only cashier/kitchen within their own branch — object-level, via `CanManageTargetUser`)

**Payload**
```json
{
  "role": "kitchen",
  "password": "new-password"
}
```

**Success Response** — `200 OK`
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "kitchen",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f"
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | user not found, or store_manager targets a user outside their branch | `{ "detail": "Not found." }` |
| 403 | store_manager targets a store_manager/owner account | `{ "detail": "You do not have permission to perform this action." }` |
| 400 | store_manager tries to change target's branch | `{ "detail": "Cannot move user to another branch." }` |
| 400 | store_manager tries to promote target to store_manager | `{ "detail": "Cannot promote user to manager." }` |

**Behavior**
- `role` and `branch` are editable through this endpoint. `PartialUpdateUserSerializer` includes both fields.
- `username` is **not** in this serializer's fields — cannot be renamed through this endpoint.
- Owner has no restrictions here beyond the object existing — can change any user's role/branch/password freely, including promoting someone to store_manager or reassigning branch.
- **No self-service path**: a store_manager can't PATCH their own account through this endpoint either (object-permission check requires `obj.role` to be cashier/kitchen — a store_manager targeting themselves fails that check). See accounts.test.md Known Issues.

---

## activate_user / deactivate_user

**Method & Path**: `PATCH /users/<uuid:id>/activate/` · `PATCH /users/<uuid:id>/deactivate/`

**Permission**: same as `update_user` (owner any target; store_manager only cashier/kitchen in own branch)

**Payload**: `{}`

**Success Response** — `200 OK` — full `RetrieveUserSerializer` output, same reasoning as `activate_branch`/`deactivate_branch` (no special case in `get_serializer_class()`):
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "is_active": false,
  "created_at": "2026-08-01T09:00:00Z",
  "updated_at": "2026-08-05T14:30:00Z"
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | user not found / outside store_manager's branch | `{ "detail": "Not found." }` |
| 403 | store_manager targets store_manager/owner account | `{ "detail": "You do not have permission to perform this action." }` |
| 400 | user already active/inactive | `{ "detail": "User is already active." }` or `{ "detail": "User is already inactive." }` |

**Side Effects**
- Soft action — sets `is_active` only, does **not** cascade to `Order.cashier` / `StockRequest.requested_by` / `approved_by` (both are `PROTECT`, so those FKs stay intact regardless).

---

## me

**Method & Path**: `GET /users/me/`

**Permission**: any authenticated user

**Success Response** — `200 OK`
```json
{
  "id": "a1b2c3d4-e5f6-4789-a012-3456789abcde",
  "username": "cashier01",
  "role": "cashier",
  "branch": "e29b41d4-a716-4bb1-9f2e-8f3a1c2d4e5f",
  "is_active": true,
  "created_at": "2026-08-01T09:00:00Z",
  "updated_at": "2026-08-01T09:00:00Z"
}
```

**Note**: GET only — cannot be used to self-update anything, including password.