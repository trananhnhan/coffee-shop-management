---
file_type: conventions
scope: global
last_verified: 2026-07-19
---

# Backend — Conventions

## Naming
- Field name: `snake_case` (standard Python/Django)
- API response key: `camelCase` (matches frontend JS — use `djangorestframework-camel-case` or serializer-level conversion)
- Model class: `PascalCase`, singular (e.g. `Order`, not `Orders`)
- FK field: named after the related model, no redundant suffix (e.g. `branch`, not `branch_id` — Django appends `_id` at the DB level automatically)
- Serializer class: `{Action}{Model}Serializer` — one serializer per action, not one shared serializer with conditional branches inside. Examples: `CreateOrderSerializer`, `UpdateDishSerializer`, `ListInventoryItemSerializer`, `ApproveStockRequestSerializer`.

## Serializer-first principle
- Business logic and validation live in the **serializer**, not the view.
- Views stay thin: parse request → call serializer → return response. No business rules, no manual validation, no direct queryset manipulation inside a view.
- Each action gets its own serializer (per the naming convention above) rather than reusing one serializer with `if self.context['action'] == ...` branching — keeps validation rules scoped and readable per operation.
- Cross-field validation (e.g. `Order.table_number` required only when `order_type = dine_in`) belongs in the serializer's `validate()` method, not in the view or the model's `save()`.
- Multi-step processes described in a domain's `logic.md` (e.g. approve `StockRequest` → increment `InventoryItem.quantity` in the same transaction) are implemented in the serializer's `create()`/`update()`, or delegated to a service function called from there — never inlined in the view.

## API Response Format

**Success:**
```json
{
  "success": true,
  "data": { ... },
  "message": null
}
```

**Error:**
```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "errors": { "field_name": ["error detail"] }
}
```

## HTTP Status Codes
| Code | Used when |
|------|-----------|
| 200 | GET/PUT/PATCH success |
| 201 | POST created successfully |
| 204 | DELETE success |
| 400 | Input validation error |
| 401 | Not authenticated |
| 403 | Not authorized |
| 404 | Resource not found |
| 409 | Conflict (e.g. unique constraint violation) |

## Base Classes & Mixins (core app)

### CloudinaryImageMixin
A utility mixin used in DRF Serializers to automatically extract the direct URL string from Cloudinary image fields (instead of returning the raw object).

**Usage:** 
Inherit this mixin **before** `ModelSerializer` and declare the `cloudinary_fields` list containing the names of the fields to be converted.

```python
class DishSerializer(CloudinaryImageMixin, serializers.ModelSerializer):
    cloudinary_fields = ['image', 'thumbnail'] # Specify image fields here

    class Meta:
        model = Dish
        fields = ['id', 'name', 'image', 'thumbnail']
```

Every model inherits these from `BaseModel` in `shared/models.py`:
```python
id = UUIDField(primary_key=True, default=uuid4)
created_at = DateTimeField(auto_now_add=True)
updated_at = DateTimeField(auto_now=True)
```
→ Do not redeclare these 3 fields in any domain's `model.md`.

## Soft Delete
- Any model requiring soft delete has an `is_active = BooleanField(default=True)` field.
- Never call `objects.delete()` directly on a soft-deletable model — use a custom `.deactivate()` method instead.

## Permission Pattern
- Every ViewSet uses `permission_classes` from `shared/permissions.py`. Don't write ad-hoc permission logic per app unless the domain has a genuinely specific rule not covered there.

## Pagination
- Use `PageNumberPagination`, default `page_size = 20`.
- Don't override unless a domain has a specific need — if so, state the reason explicitly in that domain's `api.md`.

## Error Handling
- Business logic errors → raise a custom exception from `shared/exceptions.py`, never a bare `Exception`.
- Validation happens in the serializer, not the view (see Serializer-first principle above).

## Related files
- [Shared Permissions](./permissions.md)
- [Shared Enums](./enums.md)
- [Account Constraints](../account/constraints.md)
- [Order Constraints](../order/constraints.md)
- [Dish Constraints](../dish/constraints.md)
- [Inventory Constraints](../inventory/constraints.md)