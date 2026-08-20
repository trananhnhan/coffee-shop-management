---
domain: report
covers: [ReportViewSet]
status: draft
---

# Test Plan: Report Domain

`ReportViewSet` has no model/serializer of its own — it's a pure aggregation controller over `Order`/`OrderItem`. Because of that, "Part 1" here is lighter than a normal domain (no model constraints, no serializer validation) and leans mostly on **view-level filtering logic** (`get_queryset`) and **aggregation correctness**. Part 2 is where the real coverage lives, tested end-to-end via `APIClient`.

---

## Part 1 — Unit-level tests (View filtering / aggregation logic)

| Target | Case | Input | Expected | Note |
|---|---|---|---|---|
| view | `get_queryset` — status filter | mix of `COMPLETED` and non-`COMPLETED` orders | only `COMPLETED` orders counted in any report | confirm enum value matches `OrderStatus.COMPLETED`, not a raw string mismatch |
| view | `get_queryset` — non-owner branch isolation | store_manager/cashier/kitchen calls any report action | forced to own `branch`, ignoring any `branch_id` param sent | ✅ covered (`test_manager_q1_can_only_see_their_branch_overview`) |
| view | `get_queryset` — non-owner passing `branch_id` | non-owner sends `?branch_id=<other_branch>` | param silently ignored, still scoped to own branch | ⬜ not covered — worth asserting explicitly since it's a security-adjacent behavior |
| view | `get_queryset` — owner, no `branch_id` | owner calls with no filter | sees all branches combined | ✅ covered (`test_owner_sees_global_overview_by_default`) |
| view | `get_queryset` — owner with `branch_id` | owner filters to one branch | only that branch's orders counted | ✅ covered (`test_owner_can_filter_by_specific_branch`) |
| view | `get_queryset` — date range | `start_date`/`end_date` provided | orders outside range excluded (inclusive on both ends) | ⬜ not covered |
| view | `get_queryset` — malformed date param | `start_date=not-a-date` | current behavior unverified — could 500 instead of 400 | ⬜ not covered, worth checking since it's user-controlled input with no explicit validation |
| aggregation | `overview` — empty queryset | no completed orders in range/branch | `total_revenue: 0`, `total_orders: 0`, `average_order_value: 0` (no ZeroDivisionError) | ⬜ not covered |
| aggregation | `revenue_chart` — day grouping | orders across multiple days | one entry per day, correct `revenue`/`orders` sums, ascending order | ⬜ not covered |
| aggregation | `revenue_chart` — day with zero orders | gap day between two order days | gap day simply absent from response (not zero-filled) | ⬜ not covered, but matches documented behavior — worth a regression test so it doesn't silently change |
| aggregation | `peak_hours` — hour grouping across days | orders at 08:00 on two different days in range | summed into a single `"08:00"` entry, not split per day | ⬜ not covered — this is a non-obvious behavior, high value to lock in with a test |
| aggregation | `top_items` — ranking | dish A sold more than dish B | dish A appears first, `total_sold` correct | ✅ covered (`test_top_items_ranking`) |
| aggregation | `top_items` — revenue computed from OrderItem, not Order | dish price changed after order was placed | `total_revenue` uses `unit_price_snapshot` at order time, unaffected by later price change | ⬜ not covered |
| aggregation | `top_items` — cap at 10 | more than 10 distinct dishes sold | response has exactly 10 entries | ⬜ not covered |
| permission | any action | unauthenticated request | `401` | ⬜ not covered |
| permission | any action | authenticated as any role (owner/manager/cashier/kitchen) | `200`, no role-based `403` — confirm this is intentional | ⬜ not covered — see Known issues |

---

## Part 2 — Integration / Flow tests

Goes through a real `APIClient` — request → response, across permission → queryset filtering → aggregation → cache.

| Flow | Steps | Expected | Role per step | Status |
|---|---|---|---|---|
| Branch-scoped overview | Manager Q1 calls `overview` | Sees only branch 1's revenue/order count | Store Manager | ✅ `test_manager_q1_can_only_see_their_branch_overview` |
| Global overview (Owner) | Owner calls `overview` with no filter | Sees combined revenue/order count across all branches | Owner | ✅ `test_owner_sees_global_overview_by_default` |
| Filtered overview (Owner) | Owner calls `overview?branch_id=<branch_2>` | Sees only branch 2's numbers | Owner | ✅ `test_owner_can_filter_by_specific_branch` |
| Top items ranking | Owner calls `top-items` after orders across 2 dishes | Best-selling dish first, correct `total_sold` | Owner | ✅ `test_top_items_ranking` |
| Cache hit + cross-user isolation | 1. Q1 calls `overview` (cache miss, stores cache)<br>2. New order created directly in DB for branch 1<br>3. Q1 calls `overview` again<br>4. Q2 calls `overview` for the first time | Step 3 still returns the **stale cached** value (proves cache is active); step 4 returns Q2's own correct number (proves `vary_on_headers('Authorization')` isolates cache per user/token) | Store Manager (Q1), Store Manager (Q2) | ✅ `test_redis_cache_and_data_isolation` |
| `revenue_chart` end-to-end | Call with orders across multiple days | Correct day-by-day breakdown returned | any role | ⬜ not covered |
| `peak_hours` end-to-end | Call with orders across multiple hours/days | Correct hour-bucketed breakdown | any role | ⬜ not covered |
| Date-range filtered flow | Create orders inside and outside a date window, filter by `start_date`/`end_date` | Only in-range orders counted | any role | ⬜ not covered |
| Cache expiry | Wait/mock past the 15-minute `cache_page` window | Fresh DB query happens, updated numbers returned | any role | ⬜ not covered — likely needs cache backend mocking/time-freezing rather than a real 15-min wait |

---

## Known issues / things to watch for

- **No role-based restriction on report actions** — `permission_classes = [IsAuthenticated]` is the only gate, so Kitchen/Cashier can pull branch revenue figures, same as Store Manager/Owner. Confirmed as current behavior, not yet confirmed as *intended* behavior — flagged in the API docs too. If product decides to restrict this later, add a `403` test for the excluded roles at that point.
- **Cache correctness depends on querystring being part of the cache key** — `cache_page` does this by default, but there's no explicit test proving `start_date=A` and `start_date=B` on the same endpoint/user produce two different cache entries rather than one being served stale for the other. Worth adding once date-range tests exist, since it's the kind of bug that wouldn't show up in manual testing with a warm cache.
- **`status='COMPLETED'` filter** — confirmed correct against `OrderStatus.COMPLETED` per the latest test setup (`status=OrderStatus.COMPLETED`), so the earlier concern about a lowercase/uppercase mismatch is resolved. Leaving this note here so it doesn't get re-flagged as a bug later without context.
- Tests using `force_authenticate()` don't send a real `Authorization` header, so they don't exercise `vary_on_headers('Authorization')` the same way `test_redis_cache_and_data_isolation` does (which uses `self.client.credentials(HTTP_AUTHORIZATION=...)`). Not a bug — `cache.clear()` in `setUp()` keeps each test isolated regardless — but worth knowing why only one test needs the heavier real-header setup.