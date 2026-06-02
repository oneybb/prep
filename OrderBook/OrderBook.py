import pandas as pd

class ExchangeSymbolOrderbook:
    def __init__(self,exchange:str,symbol:str):
        self.exchange = exchange
        self.symbol = symbol
        self.bids = {}
        self.asks = {}
        self.last_update_ts_ms = 0

    def update_symbol_orderbook(self, side, price,size, ts_ms):
        self.last_update_ts_ms = ts_ms
        if side == "bid":
            if price in self.bids:
                if size <=0 :
                    self.bids.pop(price)
                else:
                    self.bids[price] = {"size": size, "ts_ms": ts_ms}
        elif side == "ask":
            if price in self.asks:
                if size <=0 :
                    self.asks.pop(price)
                else:
                    self.asks[price] =  {"size": size, "ts_ms": ts_ms}
        else:
            raise ValueError(f"Invalid side: {side}")

    def get_bbo(self, side:str):
        if side == "bid":
            return max(self.bids.keys())
        elif side == "ask":
            return min(self.asks.keys())
        else:
            raise ValueError(f"Invalid side: {side}")

    def get_bbo_size(self, side:str):
        if side == "bid":
            return self.bids[max(self.bids.keys())]['size']
        elif side == "ask":
            return self.asks[min(self.asks.keys())]['size']
        else:
            raise ValueError(f"Invalid side: {side}")

    def get_bbo_ts(self, side:str):
        if side == "bid":
            return self.bids[max(self.bids.keys())]['ts_ms']
        elif side == "ask":
            return self.asks[min(self.asks.keys())]['ts_ms']
        else:
            raise ValueError(f"Invalid side: {side}")

    def get_effective_mid(self):
        bid = self.get_bbo("bid")
        ask = self.get_bbo("ask")
        return (bid + ask) / 2

    def get_spread(self):
        bid = self.get_bbo("bid")
        ask = self.get_bbo("ask")
        return ask - bid

    def get_imbalance(self):
        best_bid_size = self.get_bbo_size("bid")
        best_ask_size = self.get_bbo_size("ask")
        return (best_bid_size - best_ask_size) / (best_bid_size + best_ask_size)

    def get_snapshot(self):
        return{
            "best_bid": self.get_bbo("bid"),
            "best_ask": self.get_bbo("ask"),
            "best_bid_size": self.get_bbo_size("bid"),
            "best_ask_size": self.get_bbo_size("ask"),
            "mid_price": self.get_effective_mid(),
            "spread": self.get_spread(),
            "imbalance": self.get_imbalance(),
            "best_bid_ts": self.get_bbo_ts("bid"),
            "best_ask_ts": self.get_bbo_ts("ask")
        }


class OrderbookManager:
    def __init__(self):
        self.orderbooks = {}
    def update_orderbook(self, row):
        exchange = row['exchange']
        symbol = row['symbol']
        side = str(row['side']).lower()
        price = float(row['price'])
        size = float(row['size'])
        if exchange not in self.orderbooks:
            self.orderbooks[exchange] ={}
        if symbol not in self.orderbooks[exchange]:
            self.orderbooks[exchange][symbol] = ExchangeSymbolOrderbook(exchange, symbol)
        self.orderbooks[exchange][symbol].update_symbol_orderbook(side, price, size)

class Portfolio:
    def __init__(self, cash:float =0.0):
        self.cash = cash
        self.position = {} #key = symbol, value = qty
        self.total_fee = 0.0


    def update_portfolio(self, exchange:str, symbol:str, price:float, qty:float,fee_bps:float):
        if symbol not in self.position.keys():
            self.position[exchange,symbol]=0.0
        self.position[exchange,symbol] += qty 
        fee_notional = abs(price * qty) * fee_bps / 10000
        self.total_fee += fee_notional
        self.cash -= fee_notional + price * qty

    def get_portfolio_snapshot(self):
        return self.position
    
    def get_portfolio_cash(self):
        return self.cash

    def get_total_fee_(self):
        return self.total_fee





##################################answers
# Part A 
def get_snapshots(orderbook_manager: OrderbookManager):
    snapshots = pd.DataFrame()
    for exchange, symbol in orderbook_manager.orderbooks.items():
        symbol_snapshot = symbol.get_snapshot()
        symbol_snapshot['exchange'] = exchange
        symbol_snapshot['symbol'] = symbol
        snapshots = snapshots.append(symbol_snapshot)
    return snapshots

# Part B
def detect_cross_book(orderbook_manager: OrderbookManager):
    cross_book_events = pd.DataFrame()
    for [exchange, symbol] in orderbook_manager.orderbooks.keys():
        snapshot = orderbook_manager.orderbooks[exchange][symbol].get_snapshot()
        if snapshot['best_bid'] >= snapshot['best_ask']:
            cross_book_events = cross_book_events.append({
                'venue': exchange,
                'symbol': symbol,
                'cross_book_timing': max(snapshot['best_bid_ts'], snapshot['best_ask_ts']),
                'best_bid': snapshot['best_bid'],
                'best_ask': snapshot['best_ask'],
            })
    return cross_book_events

# part C
def calculate_slippage(trade_price, mid_price,side):
    diff = mid_price - trade_price if side == 'BUY' else trade_price - mid_price
    return diff / mid_price * 10000

def construct_orderbook_till_ts_ms(orderbook_manager:OrderbookManager,ts_ms,book_data:pd.DataFrame, exchange:str, symbol:str):
    if [exchange][symbol] not in orderbook_manager:
        orderbook_manager[exchange][symbol] = ExchangeSymbolOrderbook(exchange, symbol)
    if orderbook_manager[exchange][symbol].last_update_ts_ms < ts_ms: # need to update
        book_data_slice = book_data[(book_data['ts_ms'] <= ts_ms) & (book_data['ts_ms'] > orderbook_manager[exchange][symbol].last_update_ts_ms)]
        for row in book_data_slice.iterrows():
            orderbook_manager.update_orderbook(row)
    else: # no need to update
         return orderbook_manager
    return orderbook_manager

def join_trades_with_latest_snapshot():
    trades = pd.read_csv('trades.csv')
    trades = trades.sort_values(by='ts_ms')
    trades['prev_ts_ms'] = trades['ts_ms'].shift(1)
    book_data = pd.read_csv('book_data.csv')
    book_data = book_data.sort_values(by='ts_ms')

    # init orderbook manager
    orderbook_manager = OrderbookManager()
    output = pd.DataFrame()
    for trade in trades.iterrows():
        prev_ts_ms = trade['prev_ts_ms'] if trade['prev_ts_ms'] is not None else 0
        trade_ts_ms = trade['ts_ms']
        exchange = trade['venue']
        symbol = trade['symbol']
        side = trade['side']
        price = trade['price']

        #update orderbook till prev_ts_ms
        orderbook_manager = construct_orderbook_till_ts_ms(orderbook_manager, prev_ts_ms, book_data, exchange, symbol)
        # get snapshot at prev_ts_ms
        snapshot = orderbook_manager[exchange][symbol].get_snapshot()
        output = output.append({
            'trade_ts_ms': trade_ts_ms,
            'venue': exchange,
            'symbol': symbol,
            'side':side,
            'trade_price':price,
            'qty':snapshot['qty'],
            'mid_before':snapshot['mid_price'],
            'spread_before':snapshot['spread'],
            'imbalance_before':snapshot['imbalance'],
            'slippage_bps':calculate_slippage(price, snapshot['mid_price'], side)
        })
    return output

#part D
def calculate_final_pnl(orderbook_manager: OrderbookManager):
    trades_df = pd.read_csv('trades.csv')
    portfolio = Portfolio(cash = 0.0) #assume auto borrow
    for row in trades_df.iterrows():
        qty = row['qty'] if row['side'] == 'BUY' else -row['qty']
        portfolio.update_portfolio(row['exchange'], row['symbol'], row['price'], qty, row['fee_bps'])

    final_cash = portfolio.get_portfolio_cash()
    final_position = portfolio.get_portfolio_position()
    for [exchange,symbol] in final_position.keys():
        mid = []
        for exchange2,symbol2 in orderbook_manager.orderbooks.keys():
            if symbol2 == symbol:
                mid.append(orderbook_manager.orderbooks[exchange2][symbol2].get_effective_mid())
        final_mid = sum(mid) / len(mid)
        final_position[exchange,symbol] *= final_mid
    final_pnl = final_cash + final_position # assume no initial cash
    return final_pnl, final_cash, final_position, final_pnl

#part E
def post_trade_analysis(ts_ms_after:int = 5000):
    book_data = pd.read_csv('book_data.csv')
    trades_df = pd.read_csv('trades.csv')
    orderbook_manager = OrderbookManager()
    maker_edge_bps = []
    taker_edge_bps = []
    for row in trades_df.iterrows():
        next_ts_ms = row['ts_ms'] + ts_ms_after # 5 seconds after trade
        exchange = row['venue']
        symbol = row['symbol']

        # cosntruct orderbook snapshot at ts_ms + 5000
        orderbook_manager = construct_orderbook_till_ts_ms(orderbook_manager, next_ts_ms, book_data, exchange, symbol)
        mid_price = orderbook_manager[exchange][symbol].get_effective_mid()
        post_trade_edge_bps = calculate_slippage(row['price'], mid_price, row['side'])
        maker_edge_bps.append(post_trade_edge_bps) if row['liquidity'] == 'MAKER' else taker_edge_bps.append(post_trade_edge_bps)
    return sum(maker_edge_bps) / len(maker_edge_bps), sum(taker_edge_bps) / len(taker_edge_bps)


#part F
def check_imbalance_predicts_price_movement(ts_ms_after:int = 5000):
    book_data = pd.read_csv['book_data.csv']
    orderbook_manager = OrderbookManager()
    curr_ts_ms = 0 
    analysis_df = pd.DataFrame()
    while curr_ts_ms < max(book_data['ts_ms']):
        for exchange, symbol in book_data['exchange', 'symbol'].unique():
            #curr imbalance
            orderboook_manager = construct_orderbook_till_ts_ms(orderbook_manager, curr_ts_ms, book_data, exchange, symbol)
            imbalance = orderbook_manager[exchange][symbol].get_imbalance()
            curr_mid = orderbook_manager[exchange][symbol].get_effective_mid()
            # future mid
            curr_ts_ms += ts_ms_after
            orderboook_manager = construct_orderbook_till_ts_ms(orderbook_manager, curr_ts_ms, book_data, exchange, symbol)
            future_mid = orderbook_manager[exchange][symbol].get_effective_mid()
            future_return_bps = (future_mid- curr_mid).curr_mid * 10000


            analysis_df.append({'ts_ms': curr_ts_ms-ts_ms_after,'imbalance': imbalance, 'futre_return_bps': future_return_bps})
    analysis_df['sign_imbalance'] = analysis_df['imbalance'].apply(lambda x: 1 if x >0 else -1 if x<0 else 0)
    output = pd.DataFrame()
    #test stat significant
    # test two groups distribution 
    from scipy.stats import ttest_ind, pearsonr
    positive_imb = analysis_df[analysis_df['imbalance']>0]['future_return_bps']
    negative_imb = analysis_df[analysis_df['imbalance']<0 ]['future_return_bps']
    t_stat, p_value = ttest_ind( positive_imb, negative_imb)
    output['positive_imb_mean'] = positive_imb.mean()
    output['negative_imb_mean'] = negative_imb.mean()
    output['sign_imb_t_stat'] = t_stat
    output['sign_imb_p_value'] = p_value

    # test corr 
    corr, p_value = pearsonr(analysis_df['imablance'], analysis_df['future_return_bps'])
    output['corr'] = corr
    output['corr_p_value'] = p_value

    return output

#part G

def calcualte_net_edge (sell_bid, buy_ask, sell_fee_bps, buy_fee_bps):
    return sell_bid * (1-sell_fee_bps/1e4) - buy_ask * (1 +buy_fee_bps/1e4)
def check_cross_exchange_arbitarge(book_data:pd.DataFrame, taker_fee_bps:float = 5.0):
    orderbook_manager = OrderbookManager()
    opportunity_df = pd.DataFrame()
    for row in book_data.iterrows():
        ts_ms = row['ts_ms']
        orderbook_manager = construct_orderbook_till_ts_ms(orderbook_manager, ts_ms,book_data, row['exchange'], row['symbol'])
        curr_bbo_bid = orderbook_manager[row['exchange']][row['symbol']].get_bbo("bid")
        curr_bbo_ask = orderbook_manager[row['exchange']][row['symbol']].get_bbo("ask")
        
        for exchange,symbol in orderbook_manager.orderbooks.keys():
            if (symbol == row['symbol']) & (exchange != row['exchange']):
                exchange_last_bbo_bid = orderbook_manager[exchange][symbol].get_bbo("bid")
                exchange_last_bbo_ask = orderbook_manager[exchange][symbol].get_bbo("ask")
                if exchange_last_bbo_bid> curr_bbo_ask:
                    net_edge = calcualte_net_edge(exchange_last_bbo_bid, curr_bbo_ask, taker_fee_bps, taker_fee_bps)
                    if net_edge >0:
                        opportunity_df.append({'ts_ms':ts_ms,'sell_venue': row['exchange'], 'buy_venue': exchange , 'buy_ask':curr_bbo_ask,'sell_bid': exchange_last_bbo_bid,'net_edge':net_edge,'net_edge_bps':net_edge/curr_bbo_ask*1e4})
    return opprtunity_df




def main():
    df = pd.read_csv('book_data.csv')
    df = df.sort_values(by='ts_ms')
    orderbook_manager = OrderbookManager()
    for row in df.iterrows():
        orderbook_manager.update_orderbook(row)
    # add the differne parts of the question here
    snapshots = get_snapshots(orderbook_manager)
    cross_book_events = detect_cross_book(orderbook_manager)
    trades_with_latest_snapshot = join_trades_with_latest_snapshot() # initalize its own orderbook manager
    final_pnl, final_cash, final_position, final_pnl = calculate_final_pnl(orderbook_manager)



if __name__ == "__main__":
    main()