---
domain: dish
file_type: constraints
depends_on:
last_verified: 2026-07-28
---

# Dish — Constraints

## Enums

### Dish.size_type
`s | m | l | xl | nosize`
- Stored lowercase; normalize on save.
- `nosize` used when the dish has no size variants (single fixed price).
- Design choice: size is modeled as **separate Dish rows** (same `name`, different `size_type`), not a child table — so recipe (via `RecipeItem`) can be 1-to-1 with `Dish` directly, since ingredient quantity legitimately differs per size.

### Ingredient.unit
`g | kg | ml | l | piece`
- Domain-specific to `dish` — measures recipe-level quantity. **Not** the same enum as `InventoryItem.unit` in `inventory/constraints.md`, which tracks packaging-level stock (`bao | chai | thung | kg | lit | goi`). Do not merge these two.

## State Machine
_(not applicable — `is_available` and `is_active` are independent booleans, no ordered transitions)_

## Field-level Constraints
- `Dish.name` — normalize to lowercase before save.
- `(Dish.name, Dish.size_type)` — must be unique together.
- `Dish.price` — must be >= 0.
- `Ingredient.name` — normalize to lowercase before save; must be unique.
- `RecipeItem.quantity` — must be > 0.
- `(RecipeItem.dish, RecipeItem.ingredient)` — must be unique together (one row per ingredient per dish; update quantity instead of duplicating).
- `Category`, `Dish`, `Ingredient`, `RecipeItem` — all inherit `is_active` (soft-delete) from `BaseModel`; `on_delete=PROTECT` on `Dish.category` and `RecipeItem.ingredient` prevents hard-deleting a `Category`/`Ingredient` still referenced elsewhere — deactivate instead.

## Invariants
_(conditions that must always hold true, regardless of entry point)_
- `is_available` (menu visibility, toggled often) and `is_active` (soft-delete, permanent) are independent — deactivating (`is_active = false`) a `Dish` should also be treated as unavailable in practice, but the reverse is not true: `is_available = false` does NOT imply `is_active = false`.
- A `Dish` is never hard-deleted once referenced by any `OrderItem` — deactivate (`is_active = false`) instead, history integrity preserved via `PROTECT`/soft-delete.
- Recipe (`RecipeItem`) is per size-row (`Dish`), not shared across sibling sizes — ingredient quantity legitimately differs by size.

## Cross-domain Constraints
_(rules that depend on another domain's state)_
- `OrderItem.dish` must reference a `Dish` with `is_available = true` **and** `is_active = true` at order creation time (see `order/constraints.md`).
- No relationship to `inventory` domain — `RecipeItem` is fully decoupled from `InventoryItem`; no automatic stock deduction (see `inventory/constraints.md`).

## Related files
- [Dish Model](./model.md)
- [Dish Logic](./logic.md)