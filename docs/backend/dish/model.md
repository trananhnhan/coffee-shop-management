---
domain: dish
file_type: model
depends_on:
  - shared/conventions.md
related_but_optional:
  - inventory/model.md
last_verified: 2026-07-18
---

# Dish — Model

## Scope
This file defines: `Category`, `Dish`, `Ingredient`, `RecipeItem`.
Base fields (`id`, `created_at`, `updated_at`) inherited from `BaseModel` — see `../constraints.md`, not repeated below.
Does NOT include: business logic, validation (see `logic.md`), rules/enums/invariants (see `constraints.md`), API contract (see `api.md`).

## Models

### Category

| Field | Type | Required | Note |
|-------|------|----------|------|
| name | char | yes | |

### Dish

| Field | Type | Required | Note |
|-------|------|----------|------|
| category | FK → Category | yes | |
| name | char | yes | normalized lowercase before save |
| size_type | enum | yes | see `constraints.md`; each size is a separate Dish row |
| price | decimal | yes | price is per size row, not per dish group |
| description | text | no | |
| image_url | char | no | Cloudinary URL |
| is_available | boolean | yes | default true |

### Ingredient

| Field | Type | Required | Note |
|-------|------|----------|------|
| name | char | yes | unique, normalized lowercase before save |
| unit | enum | yes | see `constraints.md` → Unit |

### RecipeItem

| Field | Type | Required | Note |
|-------|------|----------|------|
| dish | FK → Dish | yes | |
| ingredient | FK → Ingredient | yes | |
| quantity | decimal | yes | in `Ingredient.unit` |

## Relationships
- `Category 1—N Dish`
- `Dish 1—N RecipeItem`
- `RecipeItem N—1 Ingredient`
- Dish is **not** branch-scoped — shared menu across all branches.

## Related files
- [Dish API](./api.md)
- [Dish Logic](./logic.md)
- [Dish Constraints](./constraints.md)