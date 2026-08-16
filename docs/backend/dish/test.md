---
domain: menu
covers: [Category, Dish, Ingredient, RecipeItem]
status: draft
---

# Test Plan: Menu Domain

## Part 1 — Unit-level tests (Model / Serializer / View, tested separately)

| Target | Model/File | Case | Input | Expected | Note |
|---|---|---|---|---|---|
| model | Category | required field | missing `name` | error | |
| model | Dish | unique_together | duplicate (name, size_type) | error | |
| model | Dish | auto lowercase | name = "Cà Phê Sữa", size_type = "M" | saved as "cà phê sữa", "m" | |
| model | Dish | negative price | price = -1 | error (MinValueValidator) | |
| model | Dish | size_type outside choices | size_type = "invalid" | error on full_clean() | |
| model | Dish | FK `category` PROTECT | delete Category still referenced | raise ProtectedError | |
| model | Dish | `is_available` default | create without value | defaults True | |
| model | Ingredient | unique name | duplicate name | error | |
| model | Ingredient | auto lowercase | name = "Đường" | saved as "đường" | |
| model | RecipeItem | unique_together | duplicate (dish, ingredient) | error | |
| model | RecipeItem | quantity = 0 | quantity = 0 | error (Min 0.001) | |
| model | RecipeItem | FK `ingredient` PROTECT | delete Ingredient still referenced | raise ProtectedError | |
| model | RecipeItem | FK `dish` CASCADE | delete Dish | RecipeItem rows deleted too | different from ingredient's PROTECT — worth a dedicated test to lock in the asymmetry |
| serializer | CreateCategorySerializer | missing name | no `name` | 400 | |
| serializer | CreateIngredientSerializer | missing unit | no `unit` | 400 | |
| serializer | CreateDishSerializer | happy path, single size | 1 valid size in `sizes` | 1 Dish row created | |
| serializer | CreateDishSerializer | happy path, multiple sizes | 3 sizes (S/M/L) in one request | 3 Dish rows created, sharing category/name/description/image | |
| serializer | CreateDishSerializer | empty sizes | `sizes = []` | ValidationError `{"detail": "At least one size..."}` | |
| serializer | CreateDishSerializer | duplicate size types in payload | `sizes = [{S,...}, {S,...}]` | ValidationError `{"detail": "Duplicate size types..."}` | |
| serializer | CreateDishSerializer | name+size already exists in DB | name matches existing Dish, one size overlaps | ValidationError `{"detail": "...already exists"}` | pre-check before hitting the DB unique_together error |
| serializer | CreateDishSerializer | partial overlap | 2 new sizes + 1 that already exists for that name | whole request rejected (validate() checks all sizes before create) | verify it's all-or-nothing, not partial insert |
| serializer | CreateDishSerializer | name lowercased before duplicate check | name = "Trà Sữa" vs existing "trà sữa" | still caught as duplicate (case-insensitive match) | |
| serializer | CreateDishSerializer | atomicity on failure | force an error mid-loop (e.g. mock image upload failure on 2nd size) | no partial Dish rows left behind (transaction rolled back) | requires mocking Cloudinary — worth doing given `.save()` per row |
| serializer | PartialUpdateDishSerializer | rename without conflict | new name, no size collision with siblings | succeeds, name synced to all sibling sizes | |
| serializer | PartialUpdateDishSerializer | rename with conflict | new name collides with an existing dish that shares one of this dish's sizes | ValidationError `{"detail": "Cannot rename..."}` | |
| serializer | PartialUpdateDishSerializer | shared field sync | update `category`/`description`/`image` | all sibling Dish rows (same name) updated | |
| serializer | PartialUpdateDishSerializer | price isolation | update `price` only | only the current instance's price changes, siblings untouched | this is the one field that must NOT sync across siblings |
| serializer | PartialUpdateDishSerializer | update both price and shared field together | payload has `category` + `price` | siblings get new category; only current instance gets new price | |
| serializer | ToggleAvailabilityDishSerializer | read_only fields | attempt write via this serializer | no-op, used for output only | |
| serializer | CreateRecipeItemSerializer | new ingredient for dish | ingredient not yet linked to dish | RecipeItem created | |
| serializer | CreateRecipeItemSerializer | existing ingredient for dish | ingredient already linked, new quantity | existing RecipeItem's quantity updated (update_or_create), no duplicate row | |
| serializer | PartialUpdateRecipeItemSerializer | valid update | new quantity | quantity updated | |
| serializer | PartialUpdateRecipeItemSerializer | quantity = 0 | quantity = 0 | 400 (model validator) | |
| view | CategoryViewSet | read permission | any authenticated role (Cashier, Kitchen...) can list/retrieve | 200 | |
| view | CategoryViewSet | write permission | non-Owner attempts create/partial_update | 403 | |
| view | CategoryViewSet | http methods | DELETE request | 405 (not in http_method_names) | |
| view | DishViewSet | read permission | any authenticated role can list/retrieve | 200 | |
| view | DishViewSet | write permission | non-Owner attempts create/partial_update | 403 | |
| view | DishViewSet | is_active filter | Owner passes is_active=false | queryset filtered correctly | |
| view | DishViewSet | non-owner visibility | Cashier lists dishes | only sees `is_active=True` dishes, regardless of `is_available` | is_active vs is_available are separate concerns — confirm both are tested independently |
| view | IngredientViewSet | permission (all actions) | non-Owner attempts list/retrieve/create | 403 | unlike Category/Dish, Ingredient is Owner-only even for reads |
| view | RecipeItemViewSet | http methods | attempt list/retrieve/create directly on this viewset | 405/404 (only patch, delete allowed; create happens via Dish action) | |
| view | RecipeItemViewSet | permission | non-Owner attempts patch/delete | 403 | |
| view | DishViewSet.toggle_availability | permission | non-Owner attempts toggle | 403 | action isn't in ['list','retrieve'], so it falls under IsOwner despite being a simple flag flip |
| view | DishViewSet.toggle_availability | happy path | Owner toggles | `is_available` flips (True→False or reverse) | |
| view | DishViewSet.recipe_items (GET) | permission | non-Owner attempts to view a dish's recipe items | 403 | **surprising**: action name isn't in ['list','retrieve'], so even the read (GET) branch requires IsOwner — Cashier/Kitchen can't see recipe items at all |
| view | DishViewSet.recipe_items (GET) | filtering | dish has both active and inactive RecipeItems | only active ones returned | |
| view | DishViewSet.recipe_items (POST) | happy path | Owner adds ingredient to dish | RecipeItem created/updated, 201 | |

---

## Part 2 — Integration / Flow tests

| Flow | Steps | Expected | Role per step | Note |
|---|---|---|---|---|
| Full dish creation with multiple sizes | Owner creates a dish with S/M/L sizes in one request | 3 Dish rows created, all sharing name/category/description | Owner | |
| Rename propagates, price stays isolated | 1. Create dish with S/M sizes<br>2. Rename via S instance<br>3. Update price via M instance | Both siblings show new name; only M's price changed | Owner | covers the two conflicting update semantics in one flow |
| Recipe item lifecycle | 1. Owner creates dish<br>2. Owner adds ingredient via recipe-items POST<br>3. Owner re-adds same ingredient with new quantity<br>4. Owner deactivates ingredient (is_active=False)<br>5. GET recipe-items | Step 3 updates quantity (no duplicate row); after step 4, item disappears from the active-only GET in step 5 | Owner | |
| Duplicate dish rejected end-to-end | 1. Owner creates dish "Cafe Sua", size M<br>2. Owner tries creating "cafe sua" (different case) with size M again | 2nd request rejected with 400, no new row created | Owner | confirms lowercase normalization is applied before the duplicate check, not just at save() |
| Non-owner staff can browse but not edit menu | Cashier lists categories/dishes (200), attempts to create a category (403), attempts to view a dish's recipe items (403) | All three behave as expected in sequence | Cashier | ties together the read/write asymmetry and the recipe_items surprise case |
| Deleting an ingredient still in use | 1. Owner creates ingredient<br>2. Owner links it to a dish via recipe-items<br>3. Owner attempts to delete/deactivate the ingredient | Hard delete blocked (ProtectedError) if attempted; soft-deactivate (is_active=False) should succeed independently since PROTECT only applies to hard delete | Owner | clarify whether "delete" in this app means hard delete or `ActivatableViewSetMixin`'s deactivate — test both paths |

---

## Known issues / things to watch for
- `DishViewSet.recipe_items` GET branch requires `IsOwner`, same as the POST branch, because `get_permissions()` only special-cases `['list', 'retrieve']` and `'recipe_items'` isn't one of those action names. This means Cashier/Kitchen — who can otherwise browse the full dish list — cannot see what ingredients go into a dish. Worth confirming with product intent: if kitchen staff are expected to check recipe items, this is likely a bug, not a feature.
- `IngredientViewSet` is Owner-only for every action, including list/retrieve — unlike `Category`/`Dish` where reads are open to all authenticated roles. Confirm this asymmetry is intentional (e.g. ingredient cost data is sensitive) since it's easy to assume all "menu" resources follow the same read-open pattern.
- `PartialUpdateDishSerializer.update()` re-saves every sibling row individually inside the transaction to trigger Cloudinary re-upload on image change — if a dish has many sizes, an image update on one triggers a re-upload for all. Worth a test asserting the actual number of Cloudinary calls if that mixin allows mocking/counting, since this could be a hidden cost/performance issue.
- `RecipeItem.dish` uses CASCADE while `RecipeItem.ingredient` uses PROTECT — intentional asymmetry (deleting a dish should clean up its recipe, deleting an ingredient still in use shouldn't silently break existing dishes). Lock this in with an explicit test rather than leaving it implicit.