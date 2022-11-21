# PYTHON IB TWS API BASIC OPTIONS TRADING ALGORITHM

# The code is done using ib_insync with a standard trading loop
# High level description of the code operation
# - Read input file to identify stocks and associated levels and parameters
# - Generate buy orders for call/put options when input levels are crossed
# - Generate stop/target orders
# - Go flat sometime before market close

# The code uses these abbreviations:
# - RTH for Regular Trading Hours
# - ORTH for Outside Regular Trading Hours

# Change log
#   Version                    Comment
#  Tradifact_algo_00_00          Creation
#  Tradifact_algo_00_02          Added sleep for options market data
#  Tradifact_algo_00_03          Correction to round price from rules
#  Tradict_algo_00_04          Removed expiration date >= today assertion
#  Tradifact_algo_00_05          Corrected target calculation

# Import standard libraries
import datetime
import time
import dateutil.tz
import functools
import ib_insync as ibis
from pathlib import Path
import pandas as pd
import math
from sys import exit

# Use local framework files to have smaller and more manageable algo files but not libraries, so no namespace used
from trading_framework.account import *
from trading_framework.bars import *
from trading_framework.base_args import *
from trading_framework.cli import *
from trading_framework.context import *
from trading_framework.log import *
from trading_framework.market import *
from trading_framework.orders import *

# Arguments specific to this code
default_bar_size = 60 # seconds
routing = 'SMART'

parser = base_args(description="Day trading", default_client=154, default_input_file="instructions_file.xlsx")
parser.add_argument("-a", "--account", dest="account", default="0", type=str,
                    help="Account to use, 0 means use the first listed account, default: 0")
parser.add_argument("-b", "--bar_size", dest="bar_size", default=default_bar_size, type=int,
                    help="default bar size, in seconds, default: " + str(default_bar_size))
parser.add_argument("--log_accounts", dest="log_accounts", action="store_true", help="Capture accounts in log")
parser.add_argument("-v", "--verbose", dest="verbose", action="store_true", help="Be verbose")

# Prepare the context
c = Context()
c.args = parser.parse_args()

if c.args.verbose:
    c.args.log_console = "INFO"
if c.args.debug:
    c.args.log_trading = "DEBUG"

c.args.name = Path(__file__).name.replace(".py", "")
c.alive = True
c.local_tz = dateutil.tz.tzlocal()
c.market_tz = dateutil.tz.gettz(c.args.market_tz)
c.utc_tz = dateutil.tz.tzutc()
c.previous_mtime = datetime.datetime.now() + datetime.timedelta(days=365)  # Impossible mtime to trigger initial read
c.trading_states = {}
c.seen_fills = set()
c.seen_commissions = set()
c.daily_rth_bars = {}
c.trades_orth_bars = {}
c.first_bar_seen = set()
c.stop_trades = {}
c.sizes = {}
c.previous_last_prices = {}
c.current_last_prices = {}
c.commissions = []
c.new_bars = set()

# Start logging, we use a local handler to avoid colliding with ibapi and ib_insync messages
log_dir = Path("../logs")
log_dir.mkdir(parents=True, exist_ok=True)
start_log(c)
c.logging.info(f"{c.args}")
# Put ib as None, this will be detected inside the loop to start IB, similar as what an exception can trigger
ib = None
c.global_state = "INIT"

# FUNCTIONS
# Error handling
def ib_error(reqId, errorCode, errorString, contract, c):
    # We intercept the error codes, some will indicate permission errors: 354 for subscription
    msg = str(reqId) + " " + str(errorCode) + " " + errorString
    if contract:
        symbol = contract.localSymbol
        msg += " " + symbol
        c.ib_errors[symbol].add(errorCode)
    c.logging.info(msg)


# Trade execution
def ib_exec(trade, fill, c):
    c.logging.info("Fill, possibly duplicate")
    if fill.execution.execId in c.seen_fills:
        return
    c.seen_fills.add(fill.execution.execId)
    c.logging.info("New fill")
    c.logging.info(f"Trade: {trade}")
    c.logging.info(f"Fill: {fill}")


# Commissions reporting
def ib_commission(trade, fill, report, c):
    # We capture the commission reports, these contain the full information about an executed trade
    # We store them in full, to make postprocessing easier (if present).  Note that trade.order will also have the orderRef
    c.logging.info("Commission, possibly duplicate")
    if fill.execution.execId in c.seen_commissions:
        return
    c.seen_commissions.add(fill.execution.execId)
    c.logging.info("New commission")
    c.logging.info(f"Trade: {trade}")
    c.logging.info(f"Fill: {fill}")
    c.logging.info(f"Report: {report}")
    c.commissions.append((trade, fill, report))


# Global algorithm state
def switch_global_state(c, dest, now):
    msg = now.strftime("%Y%m%d %H:%M:%S") + " switching global state from " + c.global_state + " to " + dest
    c.logging.warning(msg)
    print(msg)
    c.global_state = dest


# Timeout management
def ib_timeout(idlePeriod, c):
    # We cannot do much, log an error message and also print on the console
    msg = "TIMEOUT!!!, IB connection probably lost"
    c.logging.error(msg)
    print(msg)


# Bar updating
def ib_bar_update(bars, hasNewBar, c):
    if not hasNewBar:
        return
    symbol = bars.contract.localSymbol
    c.new_bars.add(symbol)


# Instructions spreadsheet normalization
def normalize_spreadsheet(c, df, cols=None):
    # Sometimes strings can have extra spaces, these are not humanly visible but can get you into trouble
    # This is done for all columns with dtype object unless a list of cols is passed explicitly
    if cols is None:
        cols = [c for c in df.columns if df[c].dtype == 'object']
    for col in cols:
        if df[col].dtype != 'object':
            c.logging.warning(f"Could not normalize column {col} expected to be string, check contents")
        else:
            # Empty cells can become nan, we fill them with "" instead
            df[col] = df[col].fillna("")
            df[col] = df[col].str.strip()
    return df


# Instructions file validation
def valid_row(row):
    if row["trading"] not in ['STOCKS', 'OPTIONS']:
        c.logging.warning(f"trading needs to be on STOCKS or OPTIONS {row}")
        return False
    if row["amount"] < 1:
        c.logging.warning(f"amount needs to be at least 1 {row}")
        return False
    if row["stop"] <= 0:
        c.logging.warning(f"stop needs to be > 0 {row}")
        return False
    if row["target"] <= 0:
        c.logging.warning(f"target needs to be > 0 {row}")
        return False
    if row["call_entry"] <= 0:
        c.logging.warning(f"short_entry <= 0, not allowed {row}")
        return False
    if row["call_strike"] <= 0:
        c.logging.warning(f"call_strike <= 0, not allowed {row}")
        return False
    if row["put_entry"] <= 0:
        c.logging.warning(f"put_entry <= 0, not allowed {row}")
        return False
    if row["put_strike"] <= 0:
        c.logging.warning(f"put_strike <= 0, not allowed {row}")
        return False
    if not (0 <= row["flat_delay"] <= 6 * 60 + 30):
        c.logging.warning(f"flat_delay out of bounds, not allowed {row}")
        return False
    return True


# Trading state management
def switch_trading_state(c, symbol, dest, now):
    at = now.strftime("%Y%m%d %H:%M:%S")
    msg = at + " " + symbol + " switching state from " + c.trading_states[symbol] + " to " + dest
    c.logging.warning(msg)
    c.trading_states[symbol] = dest


# Level crossing
def cross(c, symbol, level):
    previous = c.previous_last_prices[symbol]
    current = c.current_last_prices[symbol]
    if previous <= level < current:
        return "RISING"
    if previous >= level > current:
        return "FALLING"
    return "NONE"


def round_price(price, min_tick, fmt="%.4f"):
    rounded = round(price/min_tick) * min_tick
    truncated = float(fmt % rounded)
    return truncated


# Build order reference string
def build_order_reference(c, prefix, symbol, now):
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    return f"{prefix}_{c.args.name}_{symbol}_{timestamp}"


# TRADING LOOP
while c.alive:
    try:
        # (re)Start ib
        if ib is None:
            ib = ibis.IB()
            ib.errorEvent += functools.partial(ib_error, c=c)
            ib.execDetailsEvent += functools.partial(ib_exec, c=c)
            ib.commissionReportEvent += functools.partial(ib_commission, c=c)
            ib.timeoutEvent += functools.partial(ib_timeout, c=c)
            ib.barUpdateEvent += functools.partial(ib_bar_update, c=c)
            ib.setTimeout(300)
            ib.connect(host=c.args.ipaddr, port=c.args.port, clientId=c.args.client, timeout=2)
            accounts = list(ib.managedAccounts())
            if c.args.log_accounts:
                c.logging.info(f"Managed accounts {accounts}")
            if c.args.account == "0":
                c.args.account = accounts[0]
                if c.args.log_accounts:
                    c.logging.info(f"Selecting first of managed accounts as target for orders")
            else:
                if c.args.account not in accounts:
                    c.logging.info(f"Selected account {c.args.account} not in managed accounts, aborting")
                    c.logging.warning(f"Selected account {c.args.account} not in managed accounts, aborting")
                    c.alive = False
                    raise KeyError

        ib.waitOnUpdate(0.1)

        market_now = ib.reqCurrentTime().astimezone(c.market_tz)
        local_now = datetime.datetime.now(c.local_tz)
        utc_now = datetime.datetime.now(c.utc_tz)

        if c.global_state == "INIT":
            ib_time = ib.reqCurrentTime()
            c.logging.info(f"Now, market: {market_now}, local: {local_now}, UTC: {utc_now}, IB: {ib_time}")
            previous_market_now = market_now

            if c.args.test_right_now:
                ib.reqMarketDataType(4)  # Allow frozen data for testing

            # Use a well known stock to find market hours.
            # Note that the code only trades during RTH but uses premarket information to find some levels
            c.market_details = ib.reqContractDetails(ibis.Stock("AAPL", "SMART", "USD"))[0]
            market_open = market_open_at_date(market_now.date(), c.market_details) or c.args.test_right_now
            if not market_open:
                c.logging.info("Market closed today, nothing to do")
                c.alive = False
            c.market_open = market_open_time(datetime.date.today(), c.market_details)
            c.market_open = c.market_open.replace(tzinfo=c.local_tz)
            if c.market_open is None:
                c.market_open = market_now.replace(hour=9, minute=30, second=0, microsecond=0)
            c.market_close = market_close_time(datetime.date.today(), c.market_details)  # can be None
            if c.market_close is None:
                c.market_close = market_now.replace(hour=16, minute=0, second=0, microsecond=0)
            if c.args.test_right_now:
                c.market_open = market_now + datetime.timedelta(seconds=10)
                c.market_close = c.market_open + datetime.timedelta(seconds=600)
            c.logging.info(f"market start: {c.market_open}, close: {c.market_close}")

            # Make open and close times offset-aware
            c.market_open = c.market_open.replace(tzinfo=c.local_tz)
            c.market_close = c.market_close.replace(tzinfo=c.local_tz)

            switch_global_state(c, "WAIT_MARKET_OPEN", market_now)

        # Whenever the instruction file changes, read it, including the initial time (can be seen as a full change)
        p = Path(c.args.input_file)
        mtime = p.stat().st_mtime
        if c.previous_mtime != mtime:
            c.previous_mtime = mtime
            try:
                df = pd.read_excel(p, sheet_name="instructions")
                df = normalize_spreadsheet(c, df).set_index(["symbol"], drop=False)
                if not df.index.is_unique:
                    c.logging.warning(f"At least one repeated symbol in {p.name}, arbitrarily deleting duplicates")
                    df = df.drop_duplicates(["symbol"])
                c.instructions = df
                c.logging.warning(f"Read file {p}, {len(c.instructions.index)} underlying contracts found")
                for row in df.itertuples():
                    c.logging.info(f"{row}")
                print(c.instructions.to_string())
            except:
                c.logging.error(f"Reading file {p} did not succeed, not much will happen")
                raise

            # Qualify the symbols, and start bars and tickers, streaming is on the stock
            for symbol, row in df.iterrows():
                if symbol in c.contracts:
                    continue
                assert(valid_row(row))
                contract = ibis.Contract(symbol=symbol, currency=row["currency"], secType='STK', exchange=routing)
                details = ib.reqContractDetails(contract)
                if len(details) != 1:
                    c.logging.error(f"Unable to unambiguously qualify {symbol}")
                    continue
                contract = details[0].contract
                c.details[symbol] = details[0]
                rule_ids = [int(x) for x in details[0].marketRuleIds.split(",")]

                for rule_id in rule_ids:
                    if rule_id not in c.rules:
                        c.rules[rule_id] = ib.reqMarketRule(rule_id)
                try:
                    # We keep the daily bar updated
                    c.daily_rth_bars[symbol] = ib.reqHistoricalData(contract, "", "1 Y", "1 day", "TRADES",
                                                                    useRTH=True, formatDate=2, keepUpToDate=True)
                    c.logging.debug(f"{symbol} {len(c.daily_rth_bars[symbol])} daily RTH bars at start")
                    c.tickers[symbol] = ib.reqMktData(contract, "", False, False)
                    c.logging.debug(f"{symbol} ticker started")
                    bar_size_string = barsize2barsize_string(c.args.bar_size)
                    bar_duration = barSize2durationStr[bar_size_string]

                    c.trades_orth_bars[symbol] = ib.reqHistoricalData(contract, "", bar_duration, bar_size_string,
                                                                      "TRADES", useRTH=False, formatDate=2,
                                                                      keepUpToDate=True)
                    c.logging.debug(f"{symbol} {len(c.trades_orth_bars[symbol])} trades outside RTH bars at start")

                    c.trading_states[symbol] = "IDLE"
                    c.contracts[symbol] = contract
                    c.current_last_prices[symbol] = c.tickers[symbol].last

                except:
                    c.logging.warning("Caught unexpected exception in establishing data streams")
                    c.logging.exception("Exception trace:", exc_info=True, stack_info=True)
                    c.logging.warning(f"Unable to get all required information for {symbol}, check subscriptions")
                    c.n_exceptions += 1
                    if c.args.fail_fast or c.n_exceptions > 100 or not c.alive:
                        raise
                    if c.args.fail_fast:
                        raise

        for symbol, contract in c.contracts.items():
            if symbol not in c.tickers:
                c.tickers[symbol] = ib.reqMktData(contract, "", False, False)
                bar_size_string = barsize2barsize_string(c.args.bar_size)
                bar_duration = barSize2durationStr[bar_size_string]
                c.daily_rth_bars[symbol] = ib.reqHistoricalData(contract, "", "1 Y", "1 day", "TRADES",
                                                                useRTH=True, formatDate=2, keepUpToDate=True)
                c.trades_orth_bars[symbol] = ib.reqHistoricalData(contract, "", bar_duration, bar_size_string,
                                                                  "TRADES", useRTH=False, formatDate=2,
                                                                  keepUpToDate=True)


        # Fills information
        fills = list(ib.fills())
        for fill in fills:
            if fill.execution.execId in c.seen_commissions:
                continue
            c.seen_commissions.add(fill.execution.execId)
            c.logging.info("New fill")
            c.logging.info(f"Contract: {fill.contract}")
            c.logging.info(f"Execution: {fill.execution}")
            c.logging.info(f"Report: {fill.commissionReport}")
            c.commissions.append((fill.execution, fill.commissionReport))

        # Sample the last prices
        for symbol in c.contracts.keys():
            c.previous_last_prices[symbol] = c.current_last_prices[symbol]
            c.current_last_prices[symbol] = c.tickers[symbol].last

        # Whenever there is a new bar, we handle it.  Note that the last bar is the bar just starting, the
        # last full bar is bar[-2], except for the very first one.
        # We work on a copy, c.new_bars can be updated any time we pass control to the ib loop
        new_bars = c.new_bars.copy()
        c.new_bars = set()

        for symbol in new_bars:
            row = c.instructions.loc[symbol]
            contract = c.contracts[symbol]

            # Check the bar related conditions
            bars = c.trades_orth_bars[symbol][:-1]
            bars = [b for b in bars if b.date.date() == c.market_open.date()]
            if len(bars) < 1:
                continue
            bar = bars[-1]
            c.logging.info(f"New complete bar for {symbol} {bar}")

        ib.sleep(0)

        # Entry conditions
        if c.global_state == "ACTIVE":
            for symbol, contract in c.contracts.items():
                if c.trading_states[symbol] != "IDLE" or market_now >= c.market_close - datetime.timedelta(minutes=int(c.instructions["flat_delay"].loc[symbol])):
                    continue
                ref_price = c.current_last_prices[symbol]
                action = "NONE"

                # Entry parameters
                call_entry = c.instructions["call_entry"].loc[symbol]
                call_strike = c.instructions["call_strike"].loc[symbol]
                call_exp = c.instructions["call_exp"].loc[symbol]
                put_entry = c.instructions["put_entry"].loc[symbol]
                put_strike = c.instructions["put_strike"].loc[symbol]
                put_exp = c.instructions["put_exp"].loc[symbol]

                # Enter only if a call_entry level is specified in the instructions file
                if call_entry != "" and call_strike != "" and call_exp != "":
                    if cross(c, symbol, call_entry) == "RISING":
                        print("Call entry for", symbol, "crossed at", market_now)
                        action = "BUY"
                        level_type = "call_entry"

                # Enter only if a put_entry level is specified in the instructions file
                if put_entry != "" and put_strike != "" and put_exp != "":
                    if cross(c, symbol, put_entry) == "FALLING":
                        print("Put entry for", symbol, "crossed at", market_now)
                        action = "SELL"
                        level_type = "put_entry"

                if action == "NONE":
                    continue
                assert(action == "BUY" or action == "SELL")

                # If the trading is an option, we read the strike and expiration.
                # If this fails we mark the symbol as DONE
                if row["trading"] == "OPTIONS":
                    if action == 'BUY':
                        right = 'C'
                        expiration = c.instructions["call_exp"].loc[symbol].strftime('%Y%m%d')
                        strike = c.instructions["call_strike"].loc[symbol]
                        option_spec = ibis.Option(symbol, lastTradeDateOrContractMonth=expiration, strike=strike, right=right, exchange=routing)
                        details = ib.reqContractDetails(option_spec)
                        rules = details[0].marketRuleIds.split(",")
                        rule_dones = set()
                        for rule in rules:
                            if rule in rule_dones:
                                continue
                            rule_dones.add(rule)
                            market_rule = ib.reqMarketRule(int(rule))
                        option_contract = details[0].contract
                        if option_contract is None:
                            switch_trading_state(c, symbol, "DONE_NO_VALID_OPTION", market_now)
                            continue
                        option_ticker = ib.reqMktData(option_contract, "", False, False)
                        ib.sleep(0.5)
                    if action == 'SELL':
                        right = 'P'
                        expiration = c.instructions["put_exp"].loc[symbol].strftime('%Y%m%d')
                        strike = c.instructions["put_strike"].loc[symbol]
                        option_spec = ibis.Option(symbol, lastTradeDateOrContractMonth=expiration, strike=strike, right=right, exchange=routing)
                        details = ib.reqContractDetails(option_spec)
                        rules = details[0].marketRuleIds.split(",")
                        rule_dones = set()
                        for rule in rules:
                            if rule in rule_dones:
                                continue
                            rule_dones.add(rule)
                            market_rule = ib.reqMarketRule(int(rule))
                        option_contract = details[0].contract
                        if option_contract is None:
                            switch_trading_state(c, symbol, "DONE_NO_VALID_OPTION", market_now)
                            continue
                        option_ticker = ib.reqMktData(option_contract, "", False, False)
                        ib.sleep(0.5)

                    # Check for valid option price (when option data is not available queried prices can be negative)
                    if option_ticker.bid <= 0 or option_ticker.ask <= 0:
                        c.logging.warning(f"No entry because {option_contract.localSymbol}  price <= 0")
                        continue

                    # Check for spread
                    print('ask_price =', option_ticker.ask)
                    print('bid_price =', option_ticker.bid)
                    spread = abs(option_ticker.ask - option_ticker.bid)
                    print('spread =', round(spread, 2))
                    stop = c.instructions["stop"].loc[symbol] / 100
                    spread_last_ratio = spread / option_ticker.last
                    print('spread_last_ratio = ', round(spread_last_ratio * 100, 2), '%')
                    if spread_last_ratio > stop:
                        c.logging.warning(f"No entry because {option_contract.localSymbol} spread is too large")
                        continue

                    # Place the trade in the option market, entry is always BUY, up/dn reflected in C/P instead
                    multiplier = float(option_contract.multiplier)
                    amount = c.instructions["amount"].loc[symbol]
                    print('amount =', amount)
                    size = int(math.floor((amount / (option_ticker.ask * multiplier))))
                    if size <= 0:
                        c.logging.warning(f"Option price too expensive for amount of {amount}$")
                        continue
                    c.sizes[symbol] = size

                    raw_stop_price = option_ticker.ask * (1 - stop)
                    raw_target_price = option_ticker.ask * (1 + c.instructions["target"].loc[symbol] / 100)

                    # Price rounding from rules
                    min_tick = None
                    for low_edge, tick in market_rule:
                        if low_edge <= abs(raw_stop_price) and low_edge <= abs(raw_target_price):
                            min_tick = tick
                    stop_price = round_price(raw_stop_price, min_tick)
                    target_price = round_price(raw_target_price, min_tick)

                    print('stop_price =', stop_price)
                    print('target_price =', target_price)
                    exit_time = c.market_close - datetime.timedelta(minutes=int(c.instructions["flat_delay"].loc[symbol]))
                    print('exit_time =', exit_time)

                    if size >= 1:   # Minimum size for entry
                        option_symbol = option_contract.localSymbol
                        option_symbol_str = option_symbol.replace(" ", ".")
                        c.logging.warning(f"Entry trade: Buy {size} of {option_symbol} at {market_now}")

                        # Place entry trade
                        entry_order = ibis.MarketOrder('BUY', size)
                        entry_order.orderRef = build_order_reference(c, 'entry', symbol, market_now)
                        entry_order.account = c.args.account
                        entry_order.transmit = True
                        entry_trade = ib.placeOrder(option_contract, entry_order)

                        # Create stop order
                        stop_order = ibis.StopOrder('SELL', size, stop_price)
                        stop_order.orderRef = build_order_reference(c, "stop_exit", symbol, market_now)
                        stop_order.account = c.args.account

                        # Create target order
                        target_order = ibis.LimitOrder('SELL', size, target_price)
                        target_order.orderRef = build_order_reference(c, "target_exit", symbol, market_now)
                        target_order.account = c.args.account

                        # Create time exit order
                        time_order = ibis.MarketOrder('SELL', size)
                        time_order.goodAfterTime = exit_time.strftime('%Y%m%d %H:%M:%S')
                        time_order.orderRef = build_order_reference(c, "time_exit", symbol, market_now)
                        time_order.account = c.args.account

                        # Create OCA group
                        orders = [stop_order, target_order, time_order]
                        oca_group = build_order_reference(c, "oca", symbol, market_now)
                        ib.oneCancelsAll(orders=orders, ocaGroup=oca_group, ocaType=2)

                        while entry_trade.filled() != c.sizes[symbol]:
                            ib.sleep(0.001)

                        stop_trade = ib.placeOrder(option_contract, stop_order)
                        target_trade = ib.placeOrder(option_contract, target_order)
                        time_trade = ib.placeOrder(option_contract, time_order)

                        c.stop_trades[symbol] = stop_trade
                        switch_trading_state(c, symbol, "ACTIVE", market_now)
                        print('***********************************************************************************')
        ib.sleep(0)

        # Stop exit management
        for symbol, contract in c.contracts.items():
            # If the symbol is active, we check if the stop order started filling, if yes mark it inactive
            if c.trading_states[symbol] != "ACTIVE":
                continue
            if c.global_state != "ACTIVE":
                continue
            if symbol not in c.stop_trades:
                c.logging.error(f"{symbol} is marked ACTIVE but no stop trade found")
                continue
            stop_trade = c.stop_trades[symbol]
            if stop_trade.filled() == c.sizes[symbol]:
                print(symbol, "STOPPED")
                c.logging.warning(f"Stop hit for {symbol}")
                switch_trading_state(c, symbol, "IDLE", market_now)
                c.stop_trades[symbol] = []

        if c.global_state == "WAIT_MARKET_OPEN":
            if market_now >= c.market_open:
                switch_global_state(c, "ACTIVE", market_now)

        ib.sleep(0)

        if c.global_state == "ACTIVE":
            if market_now >= c.market_close:
                switch_global_state(c, "DONE", market_now)
                c.logging.warning("Closing program")
                exit(0)

        ib.sleep(0)

        # Heartbeat message
        if market_now.hour != previous_market_now.hour:
            c.logging.info("Hour boundary, heartbeat to show code is still alive")
        previous_market_now = market_now
        ib.sleep(0.1)

    except (KeyboardInterrupt, SystemExit):
        c.logging.warning("Caught expected exception or CTRL-C or system exit")
        raise
    except:  # In case of any error, try to recover
        c.logging.warning(
            "Caught unexpected exception, will attempt to restart connection unless this was a hard termination")
        c.logging.exception("Exception trace:", exc_info=True, stack_info=True)
        if c.args.fail_fast or c.n_exceptions > 100 or not c.alive:
            raise
        else:
            c.n_exceptions += 1
            if ib is not None:
                for symbol, contract in c.contracts.items():
                    try:
                        ib.cancelMktData(contract)
                    except:
                        c.logging.warning(f"{symbol} Error for cancellation during recovery")
                    try:
                        ib.cancelHistoricalData(c.daily_rth_bars[symbol])
                    except:
                        c.logging.warning(f"{symbol} Error for cancellation during recovery")
                    try:
                        ib.cancelHistoricalData(c.trades_orth_bars[symbol])
                    except:
                        c.logging.warning(f"{symbol} Error for cancellation during recovery")

                c.tickers = {}
                c.daily_rth_bars = {}
                c.trades_orth_bars = {}
                ib.disconnect()
                ib = None
                time.sleep(1)
            if c.args.debug:
                print("Exception in trading loop, will try to reconnect to IB")
            ib = None

if ib is not None:
    ib.disconnect()

# Final message
if c.args.debug:
    print("Done")