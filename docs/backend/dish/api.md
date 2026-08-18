# Menu — API

All primary keys are UUIDs. `Dish` uses a "one row per size" model — a single logical dish (e.g. "Cafe Sua") with 3 sizes is stored as **3 separate `Dish` rows** sharing the same `name`, linked only by that shared name, not by a parent/variant FK.

---

## list_category / retrieve_category

**Method & Path**: `GET /categories/` · `GET /categories/<uuid:id>/`

**Permission**: any authenticated user

**Success Response** — `200 OK` (list, paginated)
```json
{
  "id": "b3c1e2d4-1234-4a5b-8c9d-0e1f2a3b4c5d",
  "name": "coffee",
  "is_active": true
}
```
Retrieve adds `created_at`, `updated_at`.

**Note**: `get_queryset()` on `BaseMenuViewSet` filters non-owner callers to `is_active=True` only. Owner sees all + `?is_active=true/false` filter.

---

## create_category

**Method & Path**: `POST /categories/`

**Permission**: owner only

**Payload**
```json
{ "name": "Coffee" }
```

**Success Response** — `201 Created`
```json
{ "id": "b3c1e2d4-1234-4a5b-8c9d-0e1f2a3b4c5d", "name": "Coffee" }
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing name | `{ "name": ["This field is required."] }` |
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: unlike `Dish`/`Ingredient`, `Category.name` has **no `save()` lowercasing and no uniqueness constraint** — "Coffee" and "coffee" can both exist as separate rows.

---

## update_category

**Method & Path**: `PATCH /categories/<uuid:id>/`

**Permission**: owner only

**Payload**: `{ "name": "Coffee & Tea" }`

**Success Response** — `200 OK`: `{ "name": "Coffee & Tea" }`

**Error Responses**: same shape as `create_category`, plus `404` if not found.

---

## activate_category / deactivate_category

**Method & Path**: `PATCH /categories/<uuid:id>/activate/` · `.../deactivate/`

**Permission**: owner only

**Success Response** — `200 OK`, full `RetrieveCategorySerializer` output (no special-case in `get_serializer_class()` for these actions).

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | already active/inactive | `{ "detail": "Category is already active." }` / `"...already inactive."` |
| 404 | not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: `Category` has no hard-delete — `CategoryViewSet.http_method_names = ['get', 'post', 'patch']`, DELETE → `405`.

---

## list_ingredient / retrieve_ingredient

**Method & Path**: `GET /ingredients/` · `GET /ingredients/<uuid:id>/`

**Permission**: **owner only** — unlike Category/Dish, `IngredientViewSet.permission_classes = [IsOwner]` applies to every action, including reads.

**Success Response** — `200 OK`
```json
{ "id": "c4d2f3e5-...", "name": "milk", "unit": "ml", "is_active": true }
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 403 | caller is not owner | `{ "detail": "You do not have permission to perform this action." }` |

---

## create_ingredient

**Method & Path**: `POST /ingredients/`

**Permission**: owner only

**Payload**: `{ "name": "Milk", "unit": "ml" }`

**Success Response** — `201 Created`: `{ "id": "...", "name": "Milk", "unit": "ml" }`

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | missing name/unit | `{ "<field>": ["This field is required."] }` |
| 400 | unit not in choices (g/kg/ml/l/piece) | `{ "unit": ["\"x\" is not a valid choice."] }` |
| 400 | duplicate name | `{ "name": ["Ingredient with this name already exists."] }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: `name` is auto-lowercased on save (model-level), and unique — "Milk" and "milk" collide.

---

## update_ingredient

**Method & Path**: `PATCH /ingredients/<uuid:id>/`

**Permission**: owner only

**Payload**: `{ "name": "Whole Milk", "unit": "ml" }`

Same error shape as `create_ingredient`, plus `404`.

---

## activate_ingredient / deactivate_ingredient

**Method & Path**: `PATCH /ingredients/<uuid:id>/activate/` · `.../deactivate/`

**Permission**: owner only

Same behavior pattern as `activate_category` (full `RetrieveIngredientSerializer` output, 400 on already-active/inactive, 404/403 as usual).

**Note**: `Ingredient` deletion is never exposed via HTTP (`http_method_names = ['get', 'post', 'patch']`) — the model's `on_delete=PROTECT` on `RecipeItem.ingredient` only matters for admin/shell-level deletes, not the API.

---

## list_dish / retrieve_dish

**Method & Path**: `GET /dishes/` · `GET /dishes/<uuid:id>/`

**Permission**: any authenticated user

**Success Response** — `200 OK` (list)
```json
{
  "id": "d5e3a4f6-...",
  "category": "b3c1e2d4-...",
  "name": "cafe sua",
  "size_type": "m",
  "price": "35000.00",
  "image": "https://res.cloudinary.com/.../image.jpg",
  "is_available": true,
  "is_active": true
}
```
Retrieve adds `description`, `created_at`, `updated_at`.

**Note**
- `image` is rendered as a full Cloudinary URL string via `CloudinaryImageMixin.to_representation()`, not the raw field value — `null` if no image was set.
- Every size of the same logical dish appears as a **separate item** in the list (each with its own `id`, same `name`).
- Non-owner callers only see `is_active=True` dishes, regardless of `is_available` (a dish can be active but temporarily unavailable and will still show up in the list — just with `is_available: false`).

---

## create_dish

**Method & Path**: `POST /dishes/`

**Permission**: owner only

**Payload**
```json
{
  "category": "b3c1e2d4-...",
  "name": "Cafe Sua",
  "description": "Vietnamese milk coffee",
  "image": "<file>",
  "sizes": [
    { "size_type": "s", "price": 25000 },
    { "size_type": "m", "price": 30000 },
    { "size_type": "l", "price": 35000 }
  ]
}
```

**Success Response** — `201 Created` — returns **only the first created size** as the representative object (`dishes[0]` per `CreateDishSerializer.create()`), not all 3:
```json
{
  "id": "d5e3a4f6-...",
  "category": "b3c1e2d4-...",
  "name": "cafe sua",
  "description": "Vietnamese milk coffee",
  "image": "<file>",
  "sizes": [ ... ]
}
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | empty `sizes` array | `{ "detail": "At least one size must be provided." }` |
| 400 | duplicate `size_type` within the same request | `{ "detail": "Duplicate size types in request." }` |
| 400 | a (name, size_type) pair already exists in DB | `{ "detail": "Dish with name '<name>' and size '<size>' already exists." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**
- Name is lowercased before the duplicate check runs, so "Cafe Sua" collides with an existing "cafe sua" even with different casing.
- The whole request is rejected if **any** size in the payload collides — not a partial success.
- The response body doesn't reflect that 3 rows were created — client must call `list_dish?name=...` (no such filter currently exists) or `retrieve` each `id` separately to see all sizes. Worth flagging as a UX gap for the frontend team, not something to silently work around in tests.

---

## update_dish

**Method & Path**: `PATCH /dishes/<uuid:id>/`

**Permission**: owner only

**Payload**
```json
{ "price": 32000 }
```
or
```json
{ "category": "new-category-uuid", "description": "Updated description" }
```

**Success Response** — `200 OK`, the updated instance (after `refresh_from_db()`).

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | renaming collides with an existing dish+size | `{ "detail": "Cannot rename. Name '<name>' with size '<size>' already exists." }` |
| 404 | not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Critical behavior — field scope differs by field**
- `category`, `name`, `description`, `image` are **shared fields**: updating any of them on ONE size instance propagates to **every sibling row** with the same `name` (re-saved individually in a loop, which also re-triggers Cloudinary upload on `image` for every sibling).
- `price` is **NOT shared** — updating it only changes the single instance targeted by `<uuid:id>`. This is the only field where each size keeps its own value.
- Sending both in one request applies the shared fields to all siblings and the price to just the targeted one.

---

## activate_dish / deactivate_dish

**Method & Path**: `PATCH /dishes/<uuid:id>/activate/` · `.../deactivate/`

**Permission**: owner only

**Note**: this operates on a **single size row**, not the whole logical dish — deactivating the "M" size doesn't affect "S"/"L" siblings. To fully hide a dish from customers, every size must be deactivated individually. Same 400-on-already-active/inactive and full-serializer-response pattern as other `Activatable` resources.

---

## toggle_availability

**Method & Path**: `PATCH /dishes/<uuid:id>/toggle-availability/`

**Permission**: owner only

**Payload**: `{}`

**Success Response** — `200 OK`
```json
{ "id": "d5e3a4f6-...", "is_available": false }
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: no confirmation needed on the client side. Intentionally `IsOwner`-only, not opened to store_manager/kitchen — `Dish` has no `branch` FK, so availability is a chain-wide flag, not per-branch. If a branch-level role could toggle it, one branch running out of an ingredient would incorrectly hide the dish for every other branch too. Confirmed intentional.

---

## recipe_items (GET)

**Method & Path**: `GET /dishes/<uuid:dish_id>/recipe-items/`

**Permission**: owner only (see note)

**Success Response** — `200 OK`, array of active recipe items only:
```json
[
  {
    "id": "f6a7b8c9-...",
    "ingredient": "c4d2f3e5-...",
    "ingredient_name": "milk",
    "unit": "ml",
    "quantity": "50.000",
    "is_active": true
  }
]
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 404 | dish not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: fixed after review — this GET was previously (incorrectly) gated behind `IsOwner` alongside the POST branch, since `get_permissions()` only special-cased `['list', 'retrieve']` action names and `'recipe_items'` isn't one of them. Confirm current permission after the fix; docs here assume it now allows any authenticated role to read, matching the intent of letting kitchen staff see what goes into a dish.

---

## recipe_items (POST)

**Method & Path**: `POST /dishes/<uuid:dish_id>/recipe-items/`

**Permission**: owner only

**Payload**
```json
{ "ingredient": "c4d2f3e5-...", "quantity": 50 }
```

**Success Response** — `201 Created`
```json
{ "ingredient": "c4d2f3e5-...", "quantity": "50.000" }
```

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 400 | quantity <= 0 | `{ "quantity": ["Ensure this value is greater than or equal to 0.001."] }` |
| 404 | dish not found | `{ "detail": "Not found." }` |
| 403 | not owner | `{ "detail": "You do not have permission to perform this action." }` |

**Note**: uses `update_or_create` keyed on `(dish, ingredient)` — posting the same ingredient again with a new quantity **updates** the existing `RecipeItem` rather than erroring on the `unique_together` constraint or creating a duplicate.

---

## update_recipe_item

**Method & Path**: `PATCH /recipe-items/<uuid:id>/`

**Permission**: owner only

**Payload**: `{ "quantity": 60 }`

**Success Response** — `200 OK`: `{ "quantity": "60.000" }`

**Error Responses**: same as other quantity validations, plus `404`, `403`.

**Note**: `RecipeItemViewSet.http_method_names = ['patch', 'delete']` — no `list`/`retrieve`/`create` on this viewset directly; creation only happens through the nested `recipe_items` action on `DishViewSet`. A bare `GET /recipe-items/` or `GET /recipe-items/<id>/` → `405`.

---

## delete_recipe_item

**Method & Path**: `DELETE /recipe-items/<uuid:id>/`

**Permission**: owner only

**Success Response** — `204 No Content`

**Note**: this is a genuine hard delete, coexisting with soft `activate`/`deactivate` on the same resource — `RecipeItemViewSet` inherits `ActivatableViewSetMixin` (so `PATCH /recipe-items/<id>/activate/` and `.../deactivate/` work, since those are separate `@action` routes not restricted by `http_method_names`) while also allowing `DELETE` for a real removal. Worth confirming with the team which one the frontend is actually meant to use day-to-day — having both a soft and a hard delete path on the same resource is easy to use inconsistently.