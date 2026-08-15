# list
- List branches, each branch card includes branch name + today's revenue (live)
- Filter by active, inactive, search by name.

# detail
1. Header — Static info (from model.md)

Branch name, address, phone, table_capacity
Active/Inactive status badge
Edit button (edit name/address/phone/table_capacity) + Change Status button (active ⇄ inactive)

2. Revenue — Live

Today's revenue (real-time, can use WebSocket similar to the cashier-kitchen flow you're currently implementing)
Can optionally add a quick comparison (today vs yesterday, or vs 7-day average) — depending on priority

3. Order — Live overview

Number of orders today, breakdown by status (pending/preparing/done/cancelled...)
Breakdown by order type (dine-in / takeaway / delivery — depending on how order types are defined in your system)
Recent orders list (5–10 rows) + "View all" button → /owner/orders?branch=id

4. Table — Live

Current occupancy / table_capacity
Can display a list/grid of tables that currently have active orders

5. Inventory — Overview

Top items running low / below the warning threshold
"View all inventory" button → /owner/inventory?branch=id (if this page remains separate)

6. Staff — merge into this page (instead of a separate route)

List staff belonging to the branch (cashier/kitchen/store_manager), with active/inactive status
Create new staff button (according to logic.md: when created by the owner, the branch is already fixed to the current branch; role can still be selected freely)
Deactivate button for each user