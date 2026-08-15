---
file_type: index
scope: global
last_verified: 2026-07-19
---

# Docs Index — Coffee Shop Capstone

## Project summary
A management system for a multi-branch coffee shop chain (drinks + light food).

**Core business flow:** Customer orders → Cashier creates order, sends to Kitchen → Kitchen processes, marks it done → status is pushed back to Cashier in real time → Cashier settles payment. Store Manager manages staff + inventory within their own branch. Owner/HQ views all branches, read-only.

**Tech stack:** Django REST Framework (API-first, JSON only) · React (Web only — no mobile in this project's core scope) · Django Channels/WebSocket (Cashier↔Kitchen sync; fallback to polling every 3-5s if not stable by week 4) · VietQR (payment) · Cloudinary (images)

**Explicit scope boundaries (do NOT build):** detailed supplier/purchase-order management, precise gram-level recipe costing, delivery integration, mobile app, shift scheduling/attendance/payroll, combo/bundle pricing.

**Roles:** `owner | store_manager | cashier | kitchen` (see `account/constraints.md`). Superuser/Admin is not part of business RBAC — handled via Django Admin for operational fixes.

## How to use this doc set
1. When asking a coding AI to build a feature in a given domain, feed exactly the files listed in that domain's `depends_on` header — not the whole folder.
2. Always feed `shared/conventions.md` for any backend task.
3. When a model/logic changes, update the corresponding doc immediately — don't let it drift. Use a **separate** Docs Maintainer session for this (see `backend/_maintainer_prompt.md`), not the same session that wrote the code.
4. Standard domain file set: `model.md`, `api.md`, `logic.md`, `constraints.md`.
5. If a rule isn't written down in the docs, treat it as **not yet decided** — the AI should ask, not guess.

## Domain map

- **backend/**
  - `_maintainer_prompt.md` — briefing for the dedicated Docs Maintainer AI session
  - **shared/** — `docs/backend/shared/` | applies project-wide
    - index.md
    - conventions.md
    - permissions.md
    - enums.md
    - glossary.md _(not yet written)_
  - **account/** — `backend/account/` ↔ `docs/backend/account/` | foundation layer — every other domain depends on it (`User`, `Branch`)
    - model.md
    - api.md _(not yet written)_
    - logic.md
    - constraints.md
  - **dish/** — `backend/dish/` ↔ `docs/backend/dish/`
    - model.md
    - api.md _(not yet written)_
    - logic.md
    - constraints.md
  - **order/** — `backend/order/` ↔ `docs/backend/order/` | depends on `account`, `dish`
    - model.md
    - api.md _(not yet written)_
    - logic.md
    - constraints.md
  - **inventory/** — `backend/inventory/` ↔ `docs/backend/inventory/` | depends on `account`
    - model.md
    - api.md _(not yet written)_
    - logic.md
    - constraints.md

- **frontend/** _(not started yet)_
  - **screens/** — `docs/frontend/screens/`
    - index.md
    - order-create.screen.md
    - order-list.screen.md
    - dish-menu.screen.md

## Code ↔ Docs map

| Domain | Code |
|--------|------|
| Account | `backend/account/` |
| Dish | `backend/dish/` |
| Order | `backend/order/` |
| Inventory | `backend/inventory/` |

## Related
- [Shared Index](./backend/shared/index.md)
- [Docs Maintainer Prompt](./backend/_maintainer_prompt.md)
- [Frontend Screen Index](./frontend/screens/index.md) _(not yet written)_