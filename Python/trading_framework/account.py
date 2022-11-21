import math


def shares_owned(ib, symbol):
    api_positions = list(ib.positions())
    for position in api_positions:
        if position.contract.localSymbol == symbol:
            return position.position
    return 0


def pnl(ib, symbol):
    api_portfolio = list(ib.portfolio())
    for portfolio_item in api_portfolio:
        if portfolio_item.contract.localSymbol == symbol:
            return portfolio_item.unrealizedPNL
    return math.nan


def breakeven(ib, symbol):
    api_portfolio = list(ib.portfolio())
    for portfolio_item in api_portfolio:
        if portfolio_item.contract.localSymbol == symbol:
            mult = float(portfolio_item.contract.multiplier) if portfolio_item.contract.secType == "FUT" else 1.0
            return portfolio_item.averageCost / mult
    return math.nan


def market_value(ib, symbol):
    portfolio_positions = list(ib.portfolio())
    for position in portfolio_positions:
        if position.contract.localSymbol == symbol:
            return position.marketValue
    return 0


def get_account_attribute(ib, attribute):
    for value in ib.accountValues():
        if attribute == value.tag:
            return float(value.value)
    return math.nan


def account_liquidation(ib):
    for value in ib.accountValues():
        if value.tag == "NetLiquidation":
            return float(value.value)
    return math.nan


def excess_liquidity(ib):
    return get_account_attribute(ib, "ExcessLiquidity")

