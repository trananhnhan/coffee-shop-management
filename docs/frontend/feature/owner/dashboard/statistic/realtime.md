- Real-time monitoring (WebSocket) — “what is happening”
  - This part requires live updates, sharing the same channel/group with the existing order flow:

  - Number of active orders (pending/preparing/ready) per branch

  - Today’s revenue (incremental with each order completed) — push increments via WS, no need to fetch the entire list again

  - Kitchen/counter status: whether orders are congested (queue unusually long)

  - Tables currently occupied (if dine-in is available)

  - Alerts like “Branch X has had no activity > 30 minutes” (POS machine may be frozen)

→ This should be event-driven, meaning the owner dashboard subscribes to the same WS group as cashier/kitchen (or a separate branch_stats group), receiving delta events (order_completed, order_created) and accumulating on the frontend, not receiving a full snapshot each time.