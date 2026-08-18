---
domain: inventory
covers: [StockItem, InventoryItem, StockRequest]
status: draft
---

# Test Plan: Inventory Domain

## Part 1 — Unit-level tests (Model / Serializer / View, tested separately)

Test each layer in isolation — no real HTTP calls (except View, which can be tested directly via `get_permissions`/queryset or a minimal APIClient call, whichever style you prefer).

| Target | Model/File | Case | Input | Expected | Note |
|---|---|---|---|---|---|
| model | StockItem | unique name | create 2 records with same name | error (IntegrityError) | |
| model | StockItem | auto lowercase | name = "Cà Phê" | saved as "cà phê" | |
| model | StockItem | unit outside choices | unit = "invalid" | error on full_clean() | |
| model | StockItem | negative unit_price | unit_price = -1 | error (MinValueValidator) | |
| model | StockItem | null unit_price | unit_price not provided | OK, saved as null | |
| model | InventoryItem | unique_together | duplicate (branch, stock_item) | error | |
| model | InventoryItem | negative quantity | quantity = -1 | error | |
| model | InventoryItem | is_low_stock boundary | quantity == threshold | True | uses `<=`, not `<` |
| model | InventoryItem | is_low_stock | quantity > threshold | False | |
| model | InventoryItem | FK PROTECT | delete StockItem still referenced | raise ProtectedError | |
| model | StockRequest | quantity = 0 | quantity = 0 | error (Min 0.001) | |
| model | StockRequest | status default | create without status | status = PENDING | |
| model | StockRequest.approve() | PENDING → APPROVED | call approve() | status changes, approved_by/at set | |
| model | StockRequest.approve() | not PENDING | call approve() again | raise ValueError | |
| model | StockRequest.approve() | final_price differs from old price | pass new final_unit_price | StockItem.unit_price updated | |
| model | StockRequest.deliver() | APPROVED → DELIVERED | call deliver() | InventoryItem.quantity correctly incremented | |
| model | StockRequest.deliver() | called twice | deliver() x2 | 2nd call raises ValueError, quantity not double-counted | |
| model | StockRequest.reject() | PENDING → REJECTED | call reject() | status changes, quantity/price UNCHANGED | |
| serializer | CreateStockItemSerializer | missing unit | unit not provided | 400 | |
| serializer | ListInventoryItemSerializer | nested source | stock_item_name, unit | correctly pulled from related stock_item | |
| serializer | PartialUpdateInventoryItemSerializer | field outside quantity | payload includes threshold/branch | silently ignored, no error, no update | risky if the wrong serializer gets reused elsewhere |
| serializer | CreateStockRequestSerializer | happy path | inventory_item same branch as user | created successfully | |
| serializer | CreateStockRequestSerializer | cross-branch | inventory_item belongs to a different branch | ValidationError `{"detail":...}` | **security-critical** |
| serializer | CreateStockRequestSerializer | price snapshot | create request, then change base price | old snapshot stays unchanged | |
| serializer | ApproveStockRequestSerializer | passing unit_price_snapshot | value flows into approve(final_unit_price=) | verify it doesn't bypass the model method | |
| view | StockItemViewSet | create permission | role != owner | 403 | |
| view | StockItemViewSet | is_active filter | owner passes is_active=false | queryset filtered correctly | |
| view | InventoryItemViewSet | partial_update permission | role != StoreManager/Kitchen | 403 | |
| view | InventoryItemViewSet | branch isolation | non-owner list | only sees items from own branch | |
| view | StockRequestViewSet | create permission | role != BranchStaff | 403 | |
| view | StockRequestViewSet | approve/reject permission | role != StoreManager | 403 | |
| view | StockRequestViewSet | deliver permission | StoreManager calls deliver | 403 | deliver is for BranchStaff, not Manager |
| view | StockRequestViewSet | cross-branch object access | branch A retrieves an id from branch B | 404 (filtered out by queryset, not a 403) | |

---

## Part 2 — Integration / Flow tests

Goes through a real `APIClient` — request → response, across permission → serializer → view → model → DB.

| Flow | Steps | Expected | Role per step | Note |
|---|---|---|---|---|
| Full lifecycle happy path | 1. Create request<br>2. Approve<br>3. Deliver | Status changes correctly at each step; InventoryItem.quantity ends up incremented by the right amount | Cashier → Manager → BranchStaff | main happy path |
| Reject flow | 1. Create request<br>2. Reject | Status REJECTED; quantity/unit_price UNCHANGED | Cashier → Manager | |
| Cross-branch blocked end-to-end | User in branch A tries to approve a request from branch B | Blocked at the correct step (404 via queryset filtering) | Manager (branch A) | verify it's blocked at the right layer |
| Double approve via API | Approve the same request twice through the endpoint | 2nd call → 400 `{"detail": "..."}` | Manager | test via real APIClient, not by calling the model directly |
| Price changes between create and approve | 1. Create request (snapshot price A)<br>2. Change StockItem price<br>3. Approve with a different final_price | StockItem.unit_price updates per approve; the request's original snapshot stays at price A | Cashier → (price change) → Manager | verify snapshot isn't retroactively overwritten |

---

## Known issues / things to watch for
- `StockRequest.approved_by` is reused for both approve and reject — assert the right context, don't confuse "approver" with "rejector".
- The `approve` action reads `final_price` via `serializer.validated_data.get('unit_price_snapshot', None)` — confirmed it correctly flows through the model's `approve()` method and doesn't bypass the state check.