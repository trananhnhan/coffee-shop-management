---
domain: order
file_type: model
depends_on:
  - shared/conventions.md
  - account/model.md
  - dish/model.md
related_but_optional:
  - inventory/model.md
last_verified: 2026-07-18
---

# Order — Model

## Scope
This file defines: `Order`, `OrderItem`.
Base fields (`id`, `created_at`, `updated_at`) inherited from `BaseModel` — see `shared/conventions.md`, not repeated below.
Does NOT include: business logic, validation (see `logic.md`), rules/enums/invariants (see `constraints.md`), API contract (see `api.md`).

## Models

### Order

| Field | Type | Required | Note |
|-------|------|----------|------|
| branch | FK → Branch | yes | see `account/model.md`; enforces branch data isolation |
| cashier | FK → User | yes | see `account/model.md`; must belong to `branch` |
| status | enum | yes | see `constraints.md` |
| order_type | enum | yes | `dine_in \| takeaway`, see `constraints.md` |
| table_number | int | no | required when `order_type = dine_in`; validated against `Branch.table_capacity` |
| queue_number | int | no | required when `order_type = takeaway`; resets daily per branch |
| payment_method | enum | yes | `cash \| vietqr` |
| payment_status | enum | yes | `unpaid \| paid` |
| total_price_snapshot | decimal | yes | computed from `OrderItem` at creation/payment time, not recalculated live |

### OrderItem

| Field | Type | Required | Note |
|-------|------|----------|------|
| order | FK → Order | yes | |
| dish | FK → Dish | yes | see `dish/model.md`; size is already encoded in the referenced Dish row |
| quantity | int | yes | number of units of this exact dish+size |
| unit_price_snapshot | decimal | yes | copied from `Dish.price` at order time; not tied to later price changes |
| note | text | no | e.g. "less sugar, no ice" |
| kitchen_status | enum | yes | see `constraints.md`; no history log kept, current value only |

## Relationships
- `Branch 1—N Order` (see `account/model.md`)
- `User 1—N Order` (cashier)
- `Order 1—N OrderItem`
- `OrderItem N—1 Dish` (see `dish/model.md`)

## Related files
- [Order API](./api.md)
- [Order Logic](./logic.md)
- [Order Constraints](./constraints.md)