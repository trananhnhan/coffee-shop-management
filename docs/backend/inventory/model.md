---
domain: inventory
file_type: model
depends_on:
  - shared/conventions.md
  - account/model.md
related_but_optional:
  - dish/model.md
last_verified: 2026-07-18
---

# Inventory — Model

## Scope
This file defines: `InventoryItem`, `StockRequest`.
Base fields (`id`, `created_at`, `updated_at`) inherited from `BaseModel` — see `shared/conventions.md`, not repeated below.
Does NOT include: business logic, validation (see `logic.md`), rules/enums/invariants (see `constraints.md`), API contract (see `api.md`).

## Models

### StockItem

| Field | Type | Required | Note |
|-------|------|----------|------|
| name | char | yes | normalized lowercase before save; unique; not branch-scoped — shared catalog across all branches |
| unit | enum | yes | packaging unit, see `constraints.md` |
| unit_price | decimal | no | reference price, synced from the most recently *approved* `StockRequest.unit_price_snapshot` across any branch; display-only, not authoritative history |

### InventoryItem

| Field | Type | Required | Note |
|-------|------|----------|------|
| branch | FK → Branch | yes | see `account/model.md`; inventory is branch-scoped |
| stock_item | FK → StockItem | yes | 
| quantity | decimal | yes | current stock on hand |
| threshold | decimal | yes | low-stock warning level |

### StockRequest

| Field | Type | Required | Note |
|-------|------|----------|------|
| inventory_item | FK → InventoryItem | yes | |
| requested_by | FK → User | yes | see `account/model.md` |
| quantity | decimal | yes | amount requested |
| unit_price_snapshot | decimal | no | price at the time of this request; immutable once set; source of truth for purchase-cost history |
| status | enum | yes | see `constraints.md` |
| approved_by | FK → User | no | null until approved/rejected |
| approved_at | datetime | no | null until approved/rejected |

## Relationships
- `StockItem 1—N InventoryItem`
- `Branch 1—N InventoryItem`
- `InventoryItem 1—N StockRequest`
- `(StockItem.name)` unique catalog-wide; `(InventoryItem.branch, InventoryItem.stock_item)` unique together (moved from old `(branch, name)`)

## Related files
- [Inventory API](./api.md)
- [Inventory Logic](./logic.md)
- [Inventory Constraints](./constraints.md)