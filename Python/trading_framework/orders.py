def round_price_from_rules(price, exchange, details, rules):
    # the exchange is the exchange selected for the order, normally SMART
    # details are the details for the instrument
    # rules is the dictionary of rules
    # First find the rule ID to use for the target exchange
    selected_id = None
    rule_ids = [int(x) for x in details.marketRuleIds.split(",")]
    exchanges = details.validExchanges.split(",")
    for rule_exchange, rule_id in zip(exchanges, rule_ids):
        if rule_exchange == exchange:
            selected_id = rule_id
    if selected_id not in rules:
        print("No valid rule found")
        raise AttributeError
    min_tick = None
    # note that we use the absolute value or price
    for low_edge, tick in rules[selected_id]:
        if low_edge <= abs(price):
            min_tick = tick
    return round_price(price, min_tick)


def round_price(price, min_tick, fmt="%.4f"):
    # this code needs to use string processing to avoid floating point issues
    # the initial code fails because e.g. 188 * 0.01 = 1.8800000000000001
    # deep down, the IB API python code uses simply str(val), no formatting
    # so we transform back and forth from string to float
    rounded = round(price/min_tick) * min_tick
    # ideally the size should depend on min_tick, but 4 should be enough for most instruments
    truncated = float(fmt % rounded)
    return truncated


def active_order(ib, symbol, directions):
    # confusingly, ib_insync calls trades what is generally called an order
    # note that this code will *not* work across session
    api_trades = list(ib.openTrades())
    for trade in api_trades:
        if trade.contract.localSymbol != symbol:
            continue
        if trade.order.action not in directions:
            continue
        return True
    return False


def matching_trades(trades, symbol="", ref_pattern="", action="", neg_pattern=""):
    matching = []
    for trade in trades:
        if symbol and trade.contract.localSymbol != symbol:
            continue
        if ref_pattern and ref_pattern not in trade.order.orderRef:
            continue
        if action and action != trade.order.action:
            continue
        if neg_pattern and neg_pattern in trade.order.orderRef:
            continue
        matching.append(trade)
    return matching


def matching_fills(fills, symbol="", ref_pattern="", action="", neg_pattern=""):
    matching = []
    for fill in fills:
        if symbol and symbol != fill.contract.localSymbol:
            continue
        # note that the orderRef is inside execution, there is no order inside a fill
        if ref_pattern and ref_pattern not in fill.execution.orderRef:
            continue
        # action is BOT or SOLD for an execution
        if action == "BUY":
            action = "BOT"
        if action == "SELL":
            action = "SOLD"
        if action and action != fill.execution.side:
            continue
        if neg_pattern and neg_pattern in fill.execution.orderRef:
            continue
        matching.append(fill)
    return matching
