# Overview API

Path params dùng `<uuid>` (không phải id tự tăng).

## Account

| Method & Path | Permission |
|---|---|
| POST /branches/ | owner |
| GET /branches/ | owner |
| GET /branches/\<uuid\>/ | owner |
| PATCH /branches/\<uuid\>/ | owner |
| PATCH /branches/\<uuid\>/deactivate/ | owner |
| POST /users/ | owner, store_manager (branch/role bị force theo logic) |
| GET /users/ | owner (all), store_manager (own branch) |
| GET /users/\<uuid\>/ | owner, store_manager (own branch) |
| PATCH /users/\<uuid\>/ | owner, store_manager (own branch, chỉ cashier/kitchen) |
| PATCH /users/\<uuid\>/deactivate/ | owner, store_manager (own branch, chỉ cashier/kitchen) |
| GET /users/me/ | mọi role đã login |

## Dish (menu)

| Method & Path | Permission |
|---|---|
| POST /categories/ | owner |
| GET /categories/ | mọi role đã login |
| PATCH /categories/\<uuid\>/ | owner |
| POST /dishes/ | owner |
| GET /dishes/ | mọi role đã login |
| GET /dishes/\<uuid\>/ | mọi role đã login |
| PATCH /dishes/\<uuid\>/ | owner (sync sibling size-rows) |
| PATCH /dishes/\<uuid\>/toggle-availability/ | owner |
| POST /ingredients/ | owner |
| GET /ingredients/ | owner |
| PATCH /ingredients/\<uuid\>/ | owner |
| POST /dishes/\<uuid\>/recipe-items/ | owner |
| GET /dishes/\<uuid\>/recipe-items/ | owner |
| PATCH /recipe-items/\<uuid\>/ | owner |
| DELETE /recipe-items/\<uuid\>/ | owner |

## Inventory

| Method & Path | Permission |
|---|---|
| POST /stock-items/ | owner |
| GET /stock-items/ | owner, store_manager |
| GET /inventory-items/ | owner (all branch), store_manager/cashier/kitchen (own branch) |
| GET /inventory-items/\<uuid\>/ | owner, store_manager/cashier/kitchen (own branch) |
| PATCH /inventory-items/\<uuid\>/ | store_manager, kitchen (own branch — manual quantity correction) |
| POST /stock-requests/ | store_manager, cashier, kitchen (own branch) |
| GET /stock-requests/ | owner (all), store_manager/cashier/kitchen (own branch) |
| GET /stock-requests/\<uuid\>/ | owner, store_manager/cashier/kitchen (own branch) |
| PATCH /stock-requests/\<uuid\>/approve/ | store_manager (own branch) |
| PATCH /stock-requests/\<uuid\>/reject/ | store_manager (own branch) |
| PATCH /stock-requests/\<uuid\>/deliver/ | store_manager, cashier, kitchen (own branch) |

## Order

| Method & Path | Permission |
|---|---|
| POST /orders/ | cashier |
| GET /orders/ | owner (all), store_manager/cashier/kitchen (own branch) |
| GET /orders/\<uuid\>/ | owner, store_manager/cashier/kitchen (own branch) |
| PATCH /orders/\<uuid\>/items/\<uuid\>/kitchen-status/ | kitchen (own branch) |
| PATCH /orders/\<uuid\>/mark-paid/ | cashier (own branch) |
| PATCH /orders/\<uuid\>/cancel/ | cashier, store_manager (own branch) |