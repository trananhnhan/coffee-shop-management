# Report — API

`ReportViewSet` is a **non-model ViewSet** (`viewsets.ViewSet`, not `ModelViewSet`) — it has no CRUD, no queryset property, no serializer. It exists purely as a read-only aggregation controller over `Order`/`OrderItem`. All four actions share the same base filtering logic (`get_queryset()`) and only differ in what aggregation they run on top of it.

---

## Shared filtering logic (`get_queryset`)

Every action below starts from the same base queryset before doing its own aggregation:

1. **Status filter**: `Order.objects.filter(status='COMPLETED')` — only completed orders are counted in any report.
2. **Branch isolation**:
   - Owner: sees all branches, or a single branch if `?branch_id=` is passed.
   - Everyone else: forced to `branch=user.branch`, regardless of any `branch_id` query param sent (the param is only read inside the `else` branch for non-owners, so a non-owner passing `?branch_id=` is silently ignored).
3. **Date range filter**: optional `?start_date=` / `?end_date=` (both inclusive, filtered on `created_at__date`).



---

## overview

**Method & Path**: `GET /reports/overview/`

**Permission**: any authenticated user (data scoped per branch — see above)

**Query params**: `start_date`, `end_date`, `branch_id` (owner only, optional)

**Success Response** — `200 OK`
```json
{
  "total_revenue": 4500000.00,
  "total_orders": 62,
  "average_order_value": 72580.65
}
```

**Behavior**
- `total_revenue` / `total_orders` via a single `aggregate(Sum, Count)` call.
- Both fall back to `0` when the queryset is empty (`stats['total_revenue'] or 0`) — avoids returning `null`.
- `average_order_value` computed in Python (`revenue / orders`), guarded against division by zero, rounded to 2 decimals.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 401 | not authenticated | `{ "detail": "Authentication credentials were not provided." }` |

---

## revenue_chart

**Method & Path**: `GET /reports/revenue-chart/`

**Permission**: any authenticated user

**Query params**: `start_date`, `end_date`, `branch_id` (owner only, optional)

**Success Response** — `200 OK`
```json
[
  { "date": "2026-08-10", "revenue": 1200000.00, "orders": 15 },
  { "date": "2026-08-11", "revenue": 980000.00, "orders": 11 }
]
```

**Behavior**
- Groups by calendar date (`TruncDate('created_at')`), ordered ascending — intended for a time-series line/bar chart on the frontend.
- Days with zero orders are **not** included as zero-filled entries — frontend needs to handle gaps in the date sequence itself if a continuous axis is required.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 401 | not authenticated | `{ "detail": "Authentication credentials were not provided." }` |

---

## peak_hours

**Method & Path**: `GET /reports/peak-hours/`

**Permission**: any authenticated user

**Query params**: `start_date`, `end_date`, `branch_id` (owner only, optional)

**Success Response** — `200 OK`
```json
[
  { "hour": "08:00", "orders": 15 },
  { "hour": "12:00", "orders": 42 }
]
```

**Behavior**
- Groups by hour (`TruncHour('created_at')`) across the **entire filtered date range**, not per-day — e.g. if `start_date`/`end_date` spans a week, all "08:00" buckets across all 7 days are summed into a single `08:00` entry. This is intended for a heatmap of typical busy hours, not a per-day hourly breakdown.
- `hour` is formatted server-side as `"HH:00"` (`strftime('%H:00')`) — minutes are always truncated to `:00` for display.
- Same gap behavior as `revenue_chart`: hours with zero orders are omitted, not zero-filled.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 401 | not authenticated | `{ "detail": "Authentication credentials were not provided." }` |

---

## top_items

**Method & Path**: `GET /reports/top-items/`

**Permission**: any authenticated user

**Query params**: `start_date`, `end_date`, `branch_id` (owner only, optional)

**Success Response** — `200 OK`
```json
[
  { "dish_name": "Ca phe sua", "total_sold": 340, "total_revenue": 10200000.00 },
  { "dish_name": "Tra dao", "total_sold": 289, "total_revenue": 8670000.00 }
]
```

**Behavior**
- Queries `OrderItem` filtered via `order__in=qs` — i.e. reuses the same branch/date/status-filtered order queryset from `get_queryset()`, then joins into items.
- `total_revenue` here is **recomputed from `OrderItem.unit_price_snapshot × quantity`**, not read from `Order.total_price_snapshot` — this is the correct approach since it reflects per-dish revenue (an order can contain multiple dishes), but worth noting as a different computation path than `overview`'s `total_revenue`.
- Hardcoded to top 10 (`[:10]`), not configurable via query param.
- Uses the *current* `dish__name` value at query time (via `F('dish__name')`), not a frozen snapshot — if a dish was renamed after being ordered, historical top-items will show the new name, not what the item was called at order time.

**Error Responses**
| Status | Condition | Body |
|--------|-----------|------|
| 401 | not authenticated | `{ "detail": "Authentication credentials were not provided." }` |

---

## Caching (applies to all four actions)

All four endpoints are wrapped with:
```python
@method_decorator(cache_page(60 * 15))
@method_decorator(vary_on_headers('Authorization'))
```

- Responses are cached for **15 minutes**.
- `vary_on_headers('Authorization')` means the cache key includes the `Authorization` header — so different users (different tokens) get separate cache entries, which is what makes branch-scoped data safe to cache (a store manager's cached response won't leak to another branch's staff).
- **Consequence to be aware of**: query params (`start_date`, `end_date`, `branch_id`) are **not** part of the explicit vary key. Django's `cache_page` does key on full request path + querystring by default, so different param combinations *should* produce different cache entries — but this depends on `cache_page` being given the full URL including querystring, which is the default behavior. Worth a quick manual check (hit the same endpoint with two different `start_date` values back-to-back) to confirm params aren't being collapsed into one cache entry.
- Owner switching `branch_id` on the same token reuses the same `Authorization` header — so as long as querystring *is* part of the cache key, this is fine; if it turns out not to be, an owner could get a stale cached response for the wrong branch. Flagging this as something to verify, not a confirmed bug.
- `vary_on_cookie` is imported but never used — dead import, harmless but worth cleaning up.

---

## Known permission summary (who can see what)

| Action | Owner | Store Manager | Cashier | Kitchen |
|---|---|---|---|---|
| overview | ✅ (all branches, or filtered via `branch_id`) | ✅ (own branch only) | ✅ (own branch only) | ✅ (own branch only) |
| revenue_chart | ✅ | ✅ | ✅ | ✅ |
| peak_hours | ✅ | ✅ | ✅ | ✅ |
| top_items | ✅ | ✅ | ✅ | ✅ |

Unlike the Order domain (where each action is locked to a specific role), **Report has no role-based action restriction** — `permission_classes = [IsAuthenticated]` is the only gate. Any authenticated staff member (including Kitchen) can pull revenue/order-count reports for their own branch. Worth confirming with product requirements whether Kitchen/Cashier should actually see revenue figures, or whether this should be tightened to Store Manager + Owner only.