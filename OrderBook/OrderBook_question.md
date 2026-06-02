#  Live Coding Question: Market-Making Data Analysis

**Difficulty:** Medium-hard
**Suggested time:** 60–75 minutes
**Language:** Python preferred, but the problem should be solvable with only built-in data structures. Pandas/Numpy may help but should not be strictly required.

You are given two datasets:

1. `book_updates.csv`: order book level updates from two crypto exchanges.
2. `trades.csv`: your own executed trades.

Your task is to reconstruct the order book, evaluate execution quality, calculate PnL, and analyze whether order book imbalance predicts short-term price movement.

---

## Dataset 1: `book_updates.csv`

Each row is an order book update.

```csv
ts_ms,venue,symbol,side,price,size
1000,BINANCE,BTC-USDT,BID,100.00,1.5
1000,BINANCE,BTC-USDT,ASK,100.10,1.2
1000,OKX,BTC-USDT,BID,99.95,2.0
1000,OKX,BTC-USDT,ASK,100.08,1.0
2000,BINANCE,BTC-USDT,BID,100.02,1.0
2000,BINANCE,BTC-USDT,ASK,100.12,0.8
3000,BINANCE,BTC-USDT,BID,99.98,2.0
3500,OKX,BTC-USDT,ASK,100.03,1.4
4000,OKX,BTC-USDT,BID,100.00,1.0
5000,BINANCE,BTC-USDT,ASK,100.10,0
6000,BINANCE,BTC-USDT,ASK,100.09,2.0
7000,OKX,BTC-USDT,BID,99.95,0
8000,BINANCE,BTC-USDT,BID,100.06,0.5
9000,OKX,BTC-USDT,ASK,100.15,0.6
10000,BINANCE,BTC-USDT,ASK,100.20,1.0
11000,OKX,BTC-USDT,BID,100.05,1.8
12000,BINANCE,BTC-USDT,BID,100.02,0
13000,BINANCE,BTC-USDT,ASK,100.09,0
14000,BINANCE,BTC-USDT,ASK,100.07,1.0
15000,OKX,BTC-USDT,ASK,100.03,0
16000,OKX,BTC-USDT,ASK,100.11,1.2
```

### Rules

* `side = BID` means this is a bid level update.
* `side = ASK` means this is an ask level update.
* `size = 0` means delete that price level.
* Otherwise, replace the size at that price level.
* Maintain one order book per `(venue, symbol)`.

---

## Dataset 2: `trades.csv`

Each row is one of your executed trades.

```csv
ts_ms,venue,symbol,side,price,qty,liquidity,fee_bps
2500,BINANCE,BTC-USDT,BUY,100.12,0.2,TAKER,5
4500,OKX,BTC-USDT,SELL,100.00,0.3,MAKER,-1
6500,BINANCE,BTC-USDT,SELL,100.09,0.4,MAKER,-1
8500,BINANCE,BTC-USDT,BUY,100.11,0.5,TAKER,5
11500,OKX,BTC-USDT,BUY,100.12,0.2,TAKER,5
14500,BINANCE,BTC-USDT,SELL,100.07,0.6,MAKER,-1
17000,OKX,BTC-USDT,SELL,100.05,0.2,TAKER,5
```

### Rules

* `BUY` means you buy BTC and pay USDT.
* `SELL` means you sell BTC and receive USDT.
* `fee_bps` is applied to notional.
* Positive `fee_bps` means you pay a fee.
* Negative `fee_bps` means you receive a rebate.

---

# Part A: Reconstruct Best Bid / Best Ask

Process `book_updates.csv` in timestamp order.

After each update, output the current:

```python
ts_ms
venue
symbol
best_bid
best_bid_size
best_ask
best_ask_size
mid_price
spread
imbalance
```

Where:

```python
mid_price = (best_bid + best_ask) / 2
spread = best_ask - best_bid
imbalance = (best_bid_size - best_ask_size) / (best_bid_size + best_ask_size)
```

If either side of the book is missing, output `None` for `mid_price`, `spread`, and `imbalance`.

### What this tests

* Dictionaries / maps
* Sorting
* Handling deletions
* Maintaining best bid and best ask
* Edge cases when one side of the book disappears

---

# Part B: Detect Bad Market Data

While reconstructing the book, flag any timestamp where:

```python
best_bid >= best_ask
```

This is called a **crossed book**.

Return:

```python
ts_ms
venue
symbol
best_bid
best_ask
```

### What this tests

* Market data sanity checks
* Understanding that bid should normally be below ask
* Edge-case handling

---

# Part C: Join Trades with Latest Book Snapshot

For each trade, find the latest book snapshot from the **same venue and symbol** where:

```python
snapshot_ts_ms < trade_ts_ms
```

Important: use strictly earlier book data. Do **not** use future data or same-timestamp updates.

For each trade, output:

```python
trade_ts_ms
venue
symbol
side
trade_price
qty
mid_before
spread_before
imbalance_before
slippage_bps
```

Define slippage as negative if execution is bad for you.

For a `BUY`:

```python
slippage_bps = (mid_before - trade_price) / mid_before * 10000
```

For a `SELL`:

```python
slippage_bps = (trade_price - mid_before) / mid_before * 10000
```

So:

* If you buy above mid, slippage is negative.
* If you sell below mid, slippage is negative.
* If you buy below mid or sell above mid, slippage is positive.

### What this tests

* Time-series joining
* Avoiding look-ahead bias
* Understanding execution quality
* `merge_asof` if pandas is allowed
* Binary search if pandas is not allowed

---

# Part D: Calculate Total PnL

Using the trade list, calculate:

```python
final_position
cash
total_fees
mark_to_market_value
total_pnl
```

Use the final available mid price across venues as the mark price.

For simplicity, use the average of the final valid mids from `BINANCE` and `OKX`.

Accounting rules:

For a `BUY`:

```python
position += qty
cash -= price * qty
```

For a `SELL`:

```python
position -= qty
cash += price * qty
```

Fee:

```python
fee = abs(price * qty) * fee_bps / 10000
cash -= fee
```

Notice that if `fee_bps` is negative, `cash -= fee` increases cash because it is a rebate.

Final PnL:

```python
total_pnl = cash + final_position * final_mark_price
```

### What this tests

* PnL accounting
* Inventory tracking
* Fee/rebate handling
* Crypto market-making intuition

---

# Part E: Post-Trade Adverse Selection

For each trade, find the first book snapshot from the same venue and symbol where:

```python
snapshot_ts_ms >= trade_ts_ms + 5000
```

This checks the mid price roughly **5 seconds after the trade**.

Calculate `post_trade_edge_bps`.

For a `BUY`:

```python
post_trade_edge_bps = (future_mid - trade_price) / trade_price * 10000
```

For a `SELL`:

```python
post_trade_edge_bps = (trade_price - future_mid) / trade_price * 10000
```

Positive value means the market moved in your favor after the trade.

Negative value means adverse selection.

Then report the average `post_trade_edge_bps` by:

```python
liquidity
```

So compare:

```python
MAKER average post-trade edge
TAKER average post-trade edge
```

### What this tests

* Short-horizon return calculation
* Adverse selection concept
* Groupby aggregation
* Interpretation of maker vs taker fills

---

# Part F: Does Imbalance Predict Short-Term Price Movement?

For every valid book snapshot, calculate the next 5-second mid-price return on the same venue:

```python
future_return_bps = (future_mid - current_mid) / current_mid * 10000
```

Where `future_mid` is the first mid at or after:

```python
current_ts_ms + 5000
```

Then calculate the Pearson correlation between:

```python
imbalance
```

and:

```python
future_return_bps
```

Return:

```python
correlation
mean_future_return_when_imbalance_positive
mean_future_return_when_imbalance_negative
```

Then answer in one or two sentences:

> Does positive book imbalance seem to predict upward price movement in this tiny sample?

### What this tests

* Basic statistics
* Correlation
* Signal evaluation
* Market intuition
* Being careful with tiny sample sizes

---

# Part G: Cross-Exchange Arbitrage Check

At every timestamp where both venues have valid best bid and ask, check whether there is an immediate arbitrage.

Assume taker fee is:

```python
BINANCE taker fee = 5 bps
OKX taker fee = 5 bps
```

You can:

* Buy from the cheaper ask venue.
* Sell to the higher bid venue.

Net edge:

```python
net_edge = sell_bid * (1 - sell_fee_bps / 10000) - buy_ask * (1 + buy_fee_bps / 10000)
```

Return all timestamps where:

```python
net_edge > 0
```

Output:

```python
ts_ms
buy_venue
sell_venue
buy_ask
sell_bid
net_edge
net_edge_bps
```

Where:

```python
net_edge_bps = net_edge / buy_ask * 10000
```

### What this tests

* Multi-venue logic
* Fees
* Arbitrage reasoning
* Best bid / ask comparison
* Trading realism

---

# Expected Solution Structure

A strong candidate would probably write an `OrderBook` class like this:

```python
class OrderBook:
    def __init__(self):
        self.bids = {}
        self.asks = {}

    def update(self, side, price, size):
        book = self.bids if side == "BID" else self.asks

        if size == 0:
            book.pop(price, None)
        else:
            book[price] = size

    def best_bid(self):
        if not self.bids:
            return None, None
        price = max(self.bids)
        return price, self.bids[price]

    def best_ask(self):
        if not self.asks:
            return None, None
        price = min(self.asks)
        return price, self.asks[price]

    def snapshot(self):
        bid, bid_size = self.best_bid()
        ask, ask_size = self.best_ask()

        if bid is None or ask is None:
            return {
                "best_bid": bid,
                "best_bid_size": bid_size,
                "best_ask": ask,
                "best_ask_size": ask_size,
                "mid": None,
                "spread": None,
                "imbalance": None,
            }

        mid = (bid + ask) / 2
        spread = ask - bid
        imbalance = (bid_size - ask_size) / (bid_size + ask_size)

        return {
            "best_bid": bid,
            "best_bid_size": bid_size,
            "best_ask": ask,
            "best_ask_size": ask_size,
            "mid": mid,
            "spread": spread,
            "imbalance": imbalance,
        }
```

However, using:

```python
max(self.bids)
min(self.asks)
```

every time is not optimal for very large books.

A more advanced implementation could use:

```python
heapq
bisect
SortedDict
```

or another sorted data structure to maintain best bid and best ask more efficiently.

---

# Final Interpretation Questions

After completing the coding parts, briefly answer:

1. Did the strategy make money after fees and rebates?
2. Was most of the PnL from spread capture or inventory mark-to-market?
3. Were maker trades better or worse than taker trades based on post-trade edge?
4. Did order book imbalance show any predictive power?
5. Were there any crossed books or suspicious market data?
6. Were there any cross-exchange arbitrage opportunities after fees?

---

# Why This Is a Good Market-Making Interview Question

This question tests multiple areas at once:

| Area                  | Tested By                                     |
| --------------------- | --------------------------------------------- |
| Algorithms            | Maintaining bid/ask books                     |
| Data cleaning         | Sorting, deleting levels, missing states      |
| Market microstructure | Spread, mid, imbalance, crossed book          |
| PnL                   | Cash, inventory, fees, rebates                |
| Time-series           | Latest snapshot before trade                  |
| Bias control          | Strictly using past book data                 |
| Statistics            | Correlation and conditional means             |
| Crypto realism        | Maker/taker fees and cross-exchange arbitrage |
| Interpretation        | Adverse selection and signal usefulness       |

 