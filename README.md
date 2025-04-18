# 📊 IBKR Options Trading Bot

An automated **intraday options trading algorithm** built with [Interactive Brokers (IBKR)](https://www.interactivebrokers.com/) and the powerful `ib_insync` Python client. This bot is designed for dynamic execution of **calls and puts** based on price levels, with built-in risk controls and time-based exits.

> ⚠️ **Disclaimer:** This project is for educational and research purposes only. Use at your own risk.

---

## 🚀 Features

- ✅ Live trading via IBKR API (TWS or IB Gateway)
- 📈 Level-triggered entries for calls and puts
- 🔁 Automated OCO/OTO orders (target, stop-loss, timed exit)
- 📅 Time-based logic to avoid premarket/after-hours activity
- 🧾 Excel-driven input: supports multiple tickers and setups
- 🪵 Rich logging for trades, fills, and errors
- 🧠 Modular architecture for customization and extensions

---


---

## 📋 Excel Instructions Format

The bot reads trade setups from `instructions_file.xlsx`. Here's the expected format:

| symbol | trading | amount | call_entry | call_strike | call_exp   | put_entry | put_strike | put_exp   | stop | target | flat_delay |
|--------|---------|--------|------------|-------------|------------|-----------|------------|-----------|------|--------|------------|
| AAPL   | OPTIONS | 1000   | 170.5      | 172.5       | 2024-05-24 | 165.0     | 162.5      | 2024-05-24 | 20   | 40     | 15         |

- `amount` = capital per trade
- `stop` / `target` = % from entry price (e.g. 20%)
- `flat_delay` = minutes before close to exit all positions

---

## 🛠️ Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/OnelValery/Tradifact.git
cd Tradifact

**2. Required packages include:**

ib_insync

pandas

python-dateutil

openpyxl

3. Start IBKR TWS or IB Gateway
Ensure the API is enabled:

TWS: Edit > Global Configuration > API > Settings > Enable ActiveX and Socket Clients

Default port: 7497 (paper), 7496 (live)

Optional Flags

Flag	Description
--log_accounts	Logs available IB accounts & exits
--debug	Enables verbose debug logs
--instructions	Path to a custom Excel file
**🧩 Strategy Overview**
🕒 Starts during Regular Trading Hours (RTH)

📉 Monitors call/put trigger levels

🛒 Buys matching option contract (strike, expiry)

**🧯 Places 3 exit orders:**

Stop-loss

Profit target

Time-based exit

🔒 Uses OCA to enforce single-exit behavior

🧹 Exits open positions before market close

**🧰 Example Use Cases**
Live testing with small capital

Paper trading through IBKR

Adapting to other instruments (futures, stocks)



