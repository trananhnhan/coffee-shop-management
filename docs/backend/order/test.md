---
domain: order
covers: [Order, OrderItem]
status: draft
---

# Test Plan: Order Domain

## Part 1 — Unit-level tests (Model / Serializer / View, tested separately)

| Target | Model/File | Case | Input | Expected | Note |
|---|---|---|---|---|---|
| model | Order | CheckConstraint dine_in | order_type=DINE_IN, table_number=None | DB-level error (constraint) | |
| model | Order | CheckConstraint dine_in | order_type=DINE_IN, table_number set, queue_number also set | DB-level error | queue_number must be null for dine-in |
| model | Order | CheckConstraint takeaway | order_type=TAKEAWAY, queue_number=None | DB-level error | |
| model | Order | CheckConstraint takeaway | order_type=TAKEAWAY, table_number also set | DB-level error | |
| model | Order | negative total_price_snapshot | total_price_snapshot = -1 | error (MinValueValidator) | |
| model | Order | FK `branch`/`cashier` PROTECT | delete Branch/User still referenced | raise ProtectedError | |
| model | Order.mark_paid() | READY → PAID/COMPLETED | call mark_paid() from READY | payment_status=PAID, status=COMPLETED | |
| model | Order.mark_paid() | not READY | call from PENDING/IN_KITCHEN/CANCELLED/COMPLETED | raise ValueError | |
| model | Order.cancel() | any status except COMPLETED | call cancel() from PENDING/IN_KITCHEN/READY | status=CANCELLED | |
| model | Order.cancel() | already CANCELLED | call cancel() again | succeeds again, status stays CANCELLED | not blocked — only COMPLETED is blocked; confirm this is intentional (idempotent) not a gap |
| model | Order.cancel() | COMPLETED | call cancel() on a completed order | raise ValueError | |
| model | Order.recalculate_status() | all items PENDING | mixed order with all-PENDING items | status → PENDING | |
| model | Order.recalculate_status() | all items DONE | all-DONE items | status → READY | |
| model | Order.recalculate_status() | mixed statuses | some PENDING, some COOKING/DONE | status → IN_KITCHEN | |
| model | Order.recalculate_status() | zero items | order with no items | status → PENDING (vacuous `all()` on empty list) | edge case worth locking in explicitly |
| model | Order.recalculate_status() | no-op | new_status equals current status | no extra save (only saves `if self.status != new_status`) | verify with save call count/mock, not just end state |
| model | OrderItem | quantity < 1 | quantity = 0 | error (MinValueValidator 1) | |
| model | OrderItem | negative unit_price_snapshot | unit_price_snapshot = -1 | error | |
| model | OrderItem | FK `dish` PROTECT | delete Dish referenced by an OrderItem | raise ProtectedError | |
| model | OrderItem | FK `order` CASCADE | delete Order | its OrderItems deleted too | |
| model | OrderItem.update_kitchen_status() | order CANCELLED/COMPLETED | call on item whose order is CANCELLED or COMPLETED | raise ValueError | |
| model | OrderItem.update_kitchen_status() | revert from DONE | kitchen_status=DONE, new_status=COOKING | raise ValueError | |
| model | OrderItem.update_kitchen_status() | DONE → DONE | kitchen_status=DONE, new_status=DONE | allowed (not a "revert") | edge case in the revert-guard condition |
| model | OrderItem.update_kitchen_status() | valid transition | PENDING → COOKING → DONE | succeeds, triggers `order.recalculate_status()` each time | |
| serializer | OrderItemSerializer | read_only fields | attempt to write `unit_price_snapshot`/`kitchen_status` via this serializer | ignored | this serializer is only used nested inside RetrieveOrderSerializer (read path) |
| serializer | OrderItemCreateInputSerializer | dish inactive or unavailable | dish with is_active=False or is_available=False | error: "Dish does not exist or is currently unavailable." | |
| serializer | OrderItemCreateInputSerializer | quantity < 1 | quantity = 0 | 400 | |
| serializer | CreateOrderSerializer | dine-in missing table_number | order_type=DINE_IN, no table_number | ValidationError `{"detail":...}` | |
| serializer | CreateOrderSerializer | dine-in table exceeds capacity | table_number > branch.table_capacity | ValidationError `{"detail":...}` | |
| serializer | CreateOrderSerializer | takeaway with table_number provided | order_type=TAKEAWAY, table_number set | ValidationError `{"detail":...}` | |
| serializer | CreateOrderSerializer | empty items | items = [] | ValidationError `{"detail": "Order must have at least one item."}` | |
| serializer | CreateOrderSerializer | branch/cashier auto-assign | any valid payload | `branch`/`cashier` forced from request user, ignoring any client-provided value | client can't spoof branch/cashier — confirm fields aren't even writable via payload |
| serializer | CreateOrderSerializer | status/payment_status forced | any valid payload | status=PENDING, payment_status=UNPAID regardless of input | |
| serializer | CreateOrderSerializer | queue_number generation | 2nd takeaway order created same day, same branch | queue_number = previous max + 1 | uses `Max()` not `count()`, so it's resilient to gaps from deleted orders |
| serializer | CreateOrderSerializer | queue_number concurrency | 2 concurrent requests creating takeaway orders for the same branch | sequential, distinct queue_numbers — no collision | `select_for_update()` on Branch serializes creation per branch; test with threads/`transaction.atomic` + a blocking second call, or at minimum assert the lock query executes |
| serializer | CreateOrderSerializer | queue_number resets daily | takeaway order created "today" vs a stale one from a prior day | count only considers `created_at__date=today` | |
| serializer | CreateOrderSerializer | total_price_snapshot calculation | 2 items, different dish prices/quantities | total = sum(dish.price × quantity) for each item | |
| serializer | CreateOrderSerializer | unit_price_snapshot frozen at creation | dish.price changes right after order creation | OrderItem.unit_price_snapshot keeps the price at creation time, unaffected by later dish price changes | |
| serializer | CreateOrderSerializer | atomicity | force a failure mid-creation (e.g. invalid dish in 2nd item) | no Order or OrderItem rows left behind | |
| view | OrderViewSet | create permission | role != Cashier (including Owner) | 403 | Owner is an oversight/admin role, not an operational one — intentional |
| view | OrderViewSet | mark_paid permission | role != Cashier | 403 | |
| view | OrderViewSet | cancel permission | role not in [StoreManager, Cashier] | 403 | |
| view | OrderViewSet | update_kitchen_status permission | role != Kitchen | 403 | |
| view | OrderViewSet | list/retrieve permission | any authenticated role | 200 | |
| view | OrderViewSet | branch isolation | non-owner lists orders | only sees orders from own branch | |
| view | OrderViewSet | Owner queryset | Owner lists orders | sees all branches | |
| view | OrderViewSet.update_kitchen_status | item not in order | valid order id, item_id belongs to a different order | 404 `{"detail": "Item not found in this order."}` | |
| view | OrderViewSet.update_kitchen_status | cross-branch order access | Kitchen (branch A) targets an order id from branch B | 404 (queryset filters branch before get_object) | |
| view | OrderViewSet | http methods | DELETE request | 405 | |

---

## Part 2 — Integration / Flow tests

| Flow | Steps | Expected | Role per step | Note |
|---|---|---|---|---|
| Dine-in full lifecycle | 1. Cashier creates dine-in order (2 items)<br>2. Kitchen updates each item PENDING→COOKING→DONE<br>3. Cashier marks paid | Order auto-transitions PENDING→IN_KITCHEN→READY as items complete; mark_paid succeeds only once all items DONE and order is READY | Cashier → Kitchen → Cashier | ties together recalculate_status with the real endpoint chain |
| Takeaway queue numbering | Create 3 takeaway orders same day/branch in sequence | queue_number increments 1, 2, 3 | Cashier | |
| Cancel mid-cooking | 1. Cashier creates order<br>2. Kitchen sets one item to COOKING<br>3. StoreManager cancels order<br>4. Kitchen attempts to update remaining item's kitchen_status | Cancel succeeds; step 4 blocked with 400 (order is CANCELLED) | Cashier → Kitchen → StoreManager → Kitchen | confirms cancel doesn't leave orphaned in-progress items |
| Mark paid before ready blocked | 1. Cashier creates order<br>2. Cashier immediately attempts mark-paid (items still PENDING) | 400, order stays PENDING/UNPAID | Cashier | |
| Cross-branch isolation end-to-end | Cashier in branch A creates an order; Cashier in branch B lists orders | Branch B cashier does not see branch A's order | Cashier (A), Cashier (B) | |
| Owner has no operational access to orders | Owner attempts create/mark-paid/cancel/update_kitchen_status on any order | All 403 — Owner can only list/retrieve | Owner | intentional: Owner oversees, doesn't operate the counter — if an owner needs to act as staff, they use a staff account for that |
| Dish becomes unavailable mid-service | 1. Dish is available, added to menu<br>2. Owner sets dish unavailable<br>3. Cashier attempts to create a new order with that dish | Order creation rejected via `OrderItemCreateInputSerializer`'s filtered queryset error message | Owner → Cashier | confirms the is_available filter is enforced at order-creation time, not just menu browsing |

---

## Known issues / things to watch for
- **Owner has read-only access to orders (list/retrieve), no operational actions.** `IsCashier`, `IsStoreManagerOrCashier`, and `IsKitchen` check for an exact role match and don't include `Role.OWNER`, unlike `CanManageTargetUser` in accounts which explicitly special-cases Owner. Confirmed intentional: Owner is an oversight/admin role, not an operational one — an owner who wants to work the counter uses a staff account for that, the same way a real person would. Test this as a locked-in requirement, not a gap.
- `Order.cancel()` allows canceling an already-CANCELLED order again (only blocks COMPLETED) — harmless no-op in practice since state stays CANCELLED, but worth an explicit test so it's a documented decision rather than an accidental gap.
- `recalculate_status()` on a zero-item order evaluates `all()` on an empty iterable as `True`, landing on PENDING — unlikely to occur in practice since `CreateOrderSerializer` requires at least one item, but if items are ever removed after creation (not currently exposed via any endpoint here) this path would matter.
- Takeaway `queue_number` generation now locks the `Branch` row via `select_for_update()` inside the same `transaction.atomic()` block before computing the next number, and uses `Max()` instead of `count()` to stay correct even if past orders are deleted. **Fixed** — the earlier race condition no longer applies; test should confirm concurrent requests serialize correctly (e.g. via threads or a blocking second transaction) rather than re-testing for the old bug.