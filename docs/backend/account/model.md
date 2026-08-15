---
domain: account
file_type: model
depends_on:
  - shared/conventions.md
related_but_optional: []
last_verified: 2026-07-18
---

# Account — Model

## Scope
This file defines: `Branch`, `User`.
Base fields (`id`, `created_at`, `updated_at`) inherited from `BaseModel` — see `shared/conventions.md`, not repeated below.
Does NOT include: business logic, validation (see `logic.md`), rules/enums/invariants (see `constraints.md`), API contract (see `api.md`).

## Models

### Branch

| Field | Type | Required | Note |
|-------|------|----------|------|
| name | char | yes | |
| address | char | yes | |
| phone | char | no | |
| table_capacity | int | yes | total number of tables in this branch; used to validate `Order.table_number` |
| is_active | boolean | yes | default true; see `../constraints.md` → Branch status |

### User

| Field | Type | Required | Note |
|-------|------|----------|------|
| username | char | yes | unique |
| password | char | yes | hashed, handled by Django auth |
| role | enum | yes | see `../constraints.md` → Role |
| branch | FK → Branch | no | null when `role = owner`; required for all other roles |
| is_active | boolean | yes | default true |

## Relationships
- `Branch 1—N User`
- `User` is referenced by other domains: `Order.cashier`, `StockRequest.requested_by`, `StockRequest.approved_by`

## Related files
- [Account API](./api.md)
- [Account Logic](./logic.md)
- [Account Constraints](./constraints.md)