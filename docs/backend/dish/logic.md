---
domain: dish
file_type: logic
depends_on:
  - dish/model.md
  - dish/constraints.md
last_verified: 2026-07-18
---

# Dish — Logic

## Scope
This file defines: step-by-step business processes for `Category`/`Dish`/`Ingredient`/`RecipeItem` that don't fit as a static rule in `constraints.md`.
Does NOT include: field definitions (see `model.md`), enums/invariants (see `constraints.md`), endpoint shapes (see `api.md`).

## Process: Create a new Dish with sizes

1. Staff (store_manager or owner) submits a dish `name` plus one or more `(size_type, price)` pairs — e.g. `{s: 25000, m: 30000, l: 35000}`, or a single `nosize` entry for dishes without size variants.
2. For each `(size_type, price)` pair, create a separate `Dish` row sharing the same `name`, `category`, `description`, `image_url`.
3. Reject if `(name, size_type)` already exists (unique constraint, see `constraints.md`).
4. Each created `Dish` row starts with `is_available = true` by default and no `RecipeItem` rows — recipe is added separately (see next process).

## Process: Keep shared fields in sync across sibling size-rows

Known trade-off from `constraints.md`: `name`, `description`, `image_url`, `category` are duplicated per size-row, not normalized into a separate "dish group" table.

1. When staff edits `description`, `image_url`, or `category` on one size-row, the API layer must apply the same update to **all sibling rows** sharing the same `name` (before normalization) in the same request — not left for the client to call once per size.
2. `price` and `is_available` are **not** synced — each size-row's `price`/`is_available` is independent (e.g. size L can sell out while S is still available).
3. Renaming a dish (`name` change) must also apply to all sibling size-rows together, and must re-validate the `(name, size_type)` uniqueness for the new name across all sizes before committing.

## Process: Add/update a Dish's Recipe

1. Recipe is per size-row (`Dish`), not shared across sizes — since ingredient quantity legitimately differs by size (e.g. size L uses more milk than size S).
2. To add an ingredient to a dish's recipe: create a `RecipeItem(dish, ingredient, quantity)`.
3. If `(dish, ingredient)` already exists, update `quantity` on the existing row instead of inserting a duplicate (see `constraints.md` invariant).
4. Deleting a `RecipeItem` row removes that ingredient from the dish's recipe; it does not affect `InventoryItem` in any way (domains are decoupled, see `constraints.md`).

## Process: Toggle `is_available`

1. Independent per size-row — toggling `is_available = false` on `Dish (name=X, size_type=m)` does not affect `Dish (name=X, size_type=l)`.
2. When `is_available = false`, the dish must not be selectable when creating a new `OrderItem` (enforced cross-domain, see `order/constraints.md`).
3. No soft-delete distinction needed here — `is_available` already serves that purpose for dishes; a dish is never hard-deleted once it has been referenced by any `OrderItem` (history integrity).

## Related files
- [Dish Model](./model.md)
- [Dish Constraints](./constraints.md)
- [Dish API](./api.md)