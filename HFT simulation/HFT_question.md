#HFT Quote Lifecycle and Latency Simulation

**Summary:**
This question asks you to simulate a simple HFT market-making engine that sends/cancels quotes under exchange latency, tracks whether orders become live, estimates fills using queue position, and evaluates PnL and adverse selection.

**Focus:**
Order state machines, event-driven processing, latency, queue position, cancel/replace risk, stale quotes, maker fills, inventory limits, and HFT-style performance metrics.

**Difficulty:** Medium-hard
**Suggested time:** 60–75 minutes
**Language:** Python preferred. Pandas/Numpy may help, but the core logic should be solvable with built-in data structures.

---

# Problem Context

You are working on a crypto HFT market-making strategy for `BTC-USDT`.

Your strategy sends passive bid/ask quotes to the exchange. However, orders do not become active immediately because of exchange/network latency.

You are given:

1. `market_events.csv`: public market data events, including top-of-book quotes and trades.
2. `algo_actions.csv`: actions sent by your strategy, including new orders and cancel requests.

Your task is to simulate what actually happened to your orders, calculate fills and PnL, and evaluate whether the strategy suffered from stale quotes or adverse selection.

---

# Dataset 1: `market_events.csv`

Each row is either a top-of-book update or a public trade.

```csv
ts_ms,event_type,bid,ask,bid_size,ask_size,trade_price,trade_qty,aggressor_side
1000,QUOTE,100.00,100.04,3.0,2.5,,,
1010,TRADE,,,,,100.04,1.0,BUY
1030,TRADE,,,,,100.04,2.2,BUY
1050,QUOTE,100.01,100.05,2.8,2.0,,,
1080,TRADE,,,,,100.01,1.5,SELL
1100,QUOTE,100.02,100.06,2.0,2.4,,,
1130,TRADE,,,,,100.02,2.5,SELL
1180,QUOTE,99.98,100.02,4.0,1.0,,,
1200,TRADE,,,,,99.98,4.5,SELL
1250,QUOTE,99.96,100.00,3.5,2.8,,,
1300,TRADE,,,,,100.00,3.2,BUY
1360,QUOTE,100.03,100.07,1.8,1.5,,,
1400,TRADE,,,,,100.07,2.0,BUY
1450,QUOTE,100.05,100.09,2.2,2.0,,,
1500,TRADE,,,,,100.05,2.4,SELL
1600,QUOTE,100.08,100.12,2.0,2.5,,,
1700,TRADE,,,,,100.12,3.0,BUY
1800,QUOTE,100.06,100.10,3.0,2.0,,,
1900,TRADE,,,,,100.06,3.4,SELL
2000,QUOTE,100.02,100.06,2.5,2.5,,,
```

## Market Event Rules

* `event_type = QUOTE` means this row updates the current top-of-book.
* `event_type = TRADE` means a public trade happened.
* `aggressor_side = BUY` means a market buy order lifted the ask.
* `aggressor_side = SELL` means a market sell order hit the bid.
* For simplicity, assume all trades occur at the displayed `trade_price`.
* The latest valid quote before a trade gives the current bid, ask, bid size, ask size, and mid price.

The mid price is:

```python
mid = (bid + ask) / 2
```

---

# Dataset 2: `algo_actions.csv`

Each row is an action sent by your strategy.

```csv
send_ts_ms,action,order_id,side,price,qty
1005,NEW,B1,BUY,100.00,0.5
1005,NEW,S1,SELL,100.04,0.5
1070,CANCEL,B1,,,
1075,NEW,B2,BUY,100.01,0.6
1090,CANCEL,S1,,,
1110,NEW,S2,SELL,100.06,0.6
1160,CANCEL,B2,,,
1165,NEW,B3,BUY,100.02,0.7
1190,CANCEL,S2,,,
1195,NEW,S3,SELL,100.02,0.7
1240,CANCEL,B3,,,
1245,NEW,B4,BUY,99.96,0.8
1280,CANCEL,S3,,,
1285,NEW,S4,SELL,100.00,0.8
1370,CANCEL,B4,,,
1375,NEW,B5,BUY,100.03,0.6
1420,CANCEL,S4,,,
1425,NEW,S5,SELL,100.09,0.6
1510,CANCEL,B5,,,
1515,NEW,B6,BUY,100.08,0.6
1610,CANCEL,S5,,,
1615,NEW,S6,SELL,100.12,0.6
1810,CANCEL,B6,,,
1815,CANCEL,S6,,,
```

---

# Global Parameters

Use the following assumptions:

```python
exchange_latency_ms = 20
maker_fee_bps = -1
max_abs_position = 1.5
stale_threshold_bps = 3
post_fill_horizon_ms = 200
```

Interpretation:

* A `NEW` order sent at time `t` becomes live at `t + exchange_latency_ms`.
* A `CANCEL` request sent at time `t` becomes effective at `t + exchange_latency_ms`.
* An order can still be filled while its cancel request is pending.
* Maker fee is `-1 bps`, meaning you receive a rebate.
* Your absolute BTC position cannot exceed `1.5`.
* A fill is considered stale if the fill price is more than `3 bps` worse than the current mid.
* Post-fill adverse selection is measured using the first mid price at or after `fill_ts + 200ms`.

---

# Part A: Normalize All Events into One Timeline

Combine `market_events.csv` and `algo_actions.csv` into a single event stream ordered by timestamp.

You need to process the following event types:

```python
QUOTE
TRADE
NEW_SEND
NEW_ACK
CANCEL_SEND
CANCEL_ACK
```

For each `NEW` order:

* Create a `NEW_SEND` event at `send_ts_ms`.
* Create a `NEW_ACK` event at `send_ts_ms + exchange_latency_ms`.

For each `CANCEL` action:

* Create a `CANCEL_SEND` event at `send_ts_ms`.
* Create a `CANCEL_ACK` event at `send_ts_ms + exchange_latency_ms`.

If multiple events have the same timestamp, process them in this order:

```python
QUOTE
NEW_ACK
CANCEL_ACK
TRADE
NEW_SEND
CANCEL_SEND
```

## What this tests

* Event-driven processing
* Sorting with custom priority
* Latency modeling
* Careful handling of same-timestamp events

---

# Part B: Maintain Order State

Each order can have the following states:

```python
PENDING_NEW
LIVE
PENDING_CANCEL
CANCELLED
PARTIALLY_FILLED
FILLED
REJECTED
```

Rules:

1. When a `NEW_SEND` event occurs, create the order in `PENDING_NEW`.
2. When `NEW_ACK` occurs, the order becomes `LIVE`, unless it violates risk limits.
3. When `CANCEL_SEND` occurs, if the order is `LIVE` or `PARTIALLY_FILLED`, mark it as `PENDING_CANCEL`.
4. When `CANCEL_ACK` occurs, if the order is not fully filled, mark it as `CANCELLED`.
5. If an order is completely filled, mark it as `FILLED`.
6. A `PENDING_CANCEL` order can still be filled before its `CANCEL_ACK`.

Return a table with:

```python
order_id
side
price
qty
filled_qty
remaining_qty
first_live_ts_ms
final_state
```

## What this tests

* State machine logic
* Edge cases
* Partial fills
* Cancel/replace behavior
* HFT order lifecycle understanding

---

# Part C: Risk Limit Check

Before accepting a `NEW_ACK`, check whether the order would violate the worst-case inventory limit.

Current position is your filled position.

Open risk should include live and pending-cancel orders.

For a new BUY order, reject it if:

```python
current_position + open_buy_qty + new_order_qty > max_abs_position
```

For a new SELL order, reject it if:

```python
current_position - open_sell_qty - new_order_qty < -max_abs_position
```

If rejected:

```python
final_state = REJECTED
```

The order should never become live.

Return all rejected orders.

## What this tests

* Inventory-aware quoting
* Risk controls
* Difference between current position and worst-case position
* Open order exposure

---

# Part D: Queue Position and Fill Simulation

When an order becomes live, estimate its initial queue position.

For a BUY order:

* If `order.price == current_bid`, then:

```python
queue_ahead_qty = current_bid_size
```

* If `order.price < current_bid`, assume it is behind the best bid and cannot fill in this simplified model.
* If `order.price >= current_ask`, reject it as an unsafe crossing quote.

For a SELL order:

* If `order.price == current_ask`, then:

```python
queue_ahead_qty = current_ask_size
```

* If `order.price > current_ask`, assume it is behind the best ask and cannot fill in this simplified model.
* If `order.price <= current_bid`, reject it as an unsafe crossing quote.

Public trade fill rules:

For a public trade with `aggressor_side = BUY`:

* It consumes ask-side liquidity.
* Your live SELL orders can be filled if:

```python
order.price <= trade_price
```

For a public trade with `aggressor_side = SELL`:

* It consumes bid-side liquidity.
* Your live BUY orders can be filled if:

```python
order.price >= trade_price
```

Queue logic:

```python
remaining_trade_qty = trade_qty

if queue_ahead_qty > 0:
    consumed_ahead = min(queue_ahead_qty, remaining_trade_qty)
    queue_ahead_qty -= consumed_ahead
    remaining_trade_qty -= consumed_ahead

if queue_ahead_qty == 0 and remaining_trade_qty > 0:
    fill_qty = min(order_remaining_qty, remaining_trade_qty)
```

For each fill, record:

```python
fill_ts_ms
order_id
side
price
fill_qty
position_after_fill
cash_after_fill
```

## What this tests

* Queue position simulation
* Maker fill logic
* Partial fills
* Understanding that being at the best price does not mean immediate fill
* Handling fills during pending cancel

---

# Part E: Cash, Inventory, Fees, and PnL

For each fill:

For a BUY fill:

```python
position += fill_qty
cash -= price * fill_qty
```

For a SELL fill:

```python
position -= fill_qty
cash += price * fill_qty
```

Maker fee/rebate:

```python
fee = abs(price * fill_qty) * maker_fee_bps / 10000
cash -= fee
```

Because `maker_fee_bps = -1`, the fee is negative, so this increases cash.

At the end of the simulation, mark your inventory using the final mid price.

Return:

```python
final_position
cash
total_fees_or_rebates
final_mid
mark_to_market_value
total_pnl
```

Where:

```python
total_pnl = cash + final_position * final_mid
```

## What this tests

* HFT PnL accounting
* Maker rebates
* Inventory mark-to-market
* Difference between cash PnL and total PnL

---

# Part F: Detect Stale Fills

For each fill, compare the fill price to the current mid price at the time of fill.

For a BUY fill, stale slippage is:

```python
stale_slippage_bps = (current_mid - fill_price) / current_mid * 10000
```

For a SELL fill:

```python
stale_slippage_bps = (fill_price - current_mid) / current_mid * 10000
```

A fill is stale if:

```python
stale_slippage_bps < -stale_threshold_bps
```

Return:

```python
fill_ts_ms
order_id
side
fill_price
current_mid
stale_slippage_bps
is_stale
```

## What this tests

* Stale quote detection
* Execution quality
* Market-making intuition
* Whether latency caused bad fills

---

# Part G: Post-Fill Adverse Selection

For each fill, find the first mid price at or after:

```python
fill_ts_ms + post_fill_horizon_ms
```

For a BUY fill:

```python
post_fill_edge_bps = (future_mid - fill_price) / fill_price * 10000
```

For a SELL fill:

```python
post_fill_edge_bps = (fill_price - future_mid) / fill_price * 10000
```

Positive means the market moved in your favor after the fill.

Negative means adverse selection.

Return:

```python
order_id
side
fill_ts_ms
fill_price
future_mid
post_fill_edge_bps
```

Then report:

```python
average_post_fill_edge_bps
average_post_fill_edge_bps_for_BUY
average_post_fill_edge_bps_for_SELL
```

## What this tests

* Adverse selection analysis
* Future return calculation
* Time-series lookup
* Interpreting whether fills are toxic

---

# Part H: Message Rate Limit

Assume the exchange allows at most:

```python
max_messages_per_100ms = 3
```

A `NEW_SEND` or `CANCEL_SEND` counts as one message.

Check whether the strategy violated the message rate limit in any rolling 100ms window.

Return:

```python
window_start_ts_ms
window_end_ts_ms
message_count
```

for every violation.

## What this tests

* Sliding window logic
* HFT exchange constraints
* Rate-limit risk
* Efficient event processing

---

# Part I: Quote Uptime

Calculate quote uptime over the full simulation period.

Define:

```python
simulation_start = first market event timestamp
simulation_end = last market event timestamp
```

You are considered to have a live two-sided quote if you have:

```python
at least one live BUY order
and
at least one live SELL order
```

Calculate:

```python
one_sided_uptime_ratio
two_sided_uptime_ratio
```

Where:

```python
one_sided_uptime_ratio = time_with_at_least_one_live_order / total_simulation_time
two_sided_uptime_ratio = time_with_live_buy_and_live_sell / total_simulation_time
```

## What this tests

* Time interval accounting
* Live order tracking
* Market-making coverage
* Understanding that market makers care about quote presence, not just PnL

---

# Final Interpretation Questions

After completing the coding parts, answer briefly:

1. Did the strategy make money after maker rebates?
2. Was the PnL mainly from spread capture or inventory mark-to-market?
3. Did any orders get filled while pending cancel?
4. Were any fills stale?
5. Did the strategy suffer from adverse selection after fills?
6. Did the strategy violate any message rate limits?
7. What would you change to improve this market-making strategy?

---

# Expected Solution Structure

A strong candidate might structure the solution using classes like:

```python
class Order:
    def __init__(self, order_id, side, price, qty):
        self.order_id = order_id
        self.side = side
        self.price = price
        self.qty = qty
        self.filled_qty = 0.0
        self.remaining_qty = qty
        self.state = "PENDING_NEW"
        self.first_live_ts_ms = None
        self.queue_ahead_qty = None
```

```python
class HFTEngine:
    def __init__(self):
        self.orders = {}
        self.position = 0.0
        self.cash = 0.0
        self.current_bid = None
        self.current_ask = None
        self.current_bid_size = None
        self.current_ask_size = None
        self.fills = []
```

Key helper functions:

```python
process_quote_event()
process_trade_event()
process_new_send()
process_new_ack()
process_cancel_send()
process_cancel_ack()
check_risk_limit()
simulate_fill()
calculate_pnl()
calculate_quote_uptime()
```

---


This question tests a different set of skills from a normal order book reconstruction problem.

| Area                      | Tested By                                             |
| ------------------------- | ----------------------------------------------------- |
| HFT systems               | Event ordering, latency, ACKs, pending cancel         |
| Order lifecycle           | State machine for new, live, cancelled, filled orders |
| Queue modeling            | Queue-ahead quantity and partial fills                |
| Risk controls             | Worst-case inventory from open orders                 |
| PnL                       | Cash, inventory, maker rebates, mark-to-market        |
| Execution quality         | Stale fills and adverse selection                     |
| Exchange constraints      | Message rate limits                                   |
| Market-making performance | One-sided and two-sided quote uptime                  |
| Data interpretation       | Explaining whether the strategy is healthy or toxic   |

 