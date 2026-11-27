import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import date, timedelta, datetime
import json

st.set_page_config(page_title="AI Stock Trader India", page_icon="📊", layout="wide")

API_BASE = "https://api.tejhq.dev/v1/ohlcv/nse"
UNIVERSE = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "SBIN", "ITC", "LT", "BHARTIARTL", "HINDUNILVR"
]
STARTING_CASH = 100_000.0
MAX_POSITION_FRACTION = 0.10
STOP_LOSS_PCT = 0.05
TAKE_PROFIT_PCT = 0.10
SIMULATED_COST_RATE = 0.001  # illustrative 0.10% per side; not an exact fee schedule

st.title("📊 AI Stock Trader — India")
st.caption("Educational paper-trading prototype • NSE end-of-day data • No real orders")

st.warning(
    "SIMULATION ONLY. Signals are rule-based educational examples, not investment advice. "
    "Prices may be delayed or unavailable. No broker is connected and no real trades can occur."
)

def extract_rows(payload):
    """Accept common JSON response shapes and return a DataFrame."""
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        for key in ("data", "results", "rows", "candles", "ohlcv"):
            value = payload.get(key)
            if isinstance(value, list):
                return pd.DataFrame(value)
            if isinstance(value, dict):
                for nested in ("data", "rows", "results"):
                    if isinstance(value.get(nested), list):
                        return pd.DataFrame(value[nested])
        # Some APIs return column-oriented JSON.
        for key in ("items", "records"):
            if isinstance(payload.get(key), list):
                return pd.DataFrame(payload[key])
    return pd.DataFrame()

@st.cache_data(ttl=60*60*20, show_spinner=False)
def load_history(symbol):
    end = date.today()
    start = end - timedelta(days=180)
    url = f"{API_BASE}/{symbol}?from={start.isoformat()}&to={end.isoformat()}"
    response = requests.get(url, timeout=25, headers={"User-Agent": "EducationalPaperTradingDashboard/1.0"})
    response.raise_for_status()
    df = extract_rows(response.json())
    if df.empty:
        raise ValueError("The data provider returned no rows or an unknown response format.")

    # Normalize likely field names.
    rename = {}
    for col in df.columns:
        c = str(col).lower()
        if c in ("timestamp", "trading_date", "trade_date"): rename[col] = "date"
        elif c in ("o",): rename[col] = "open"
        elif c in ("h",): rename[col] = "high"
        elif c in ("l",): rename[col] = "low"
        elif c in ("c", "adj_close"): rename[col] = "close"
        elif c in ("v", "qty", "quantity"): rename[col] = "volume"
    df = df.rename(columns=rename)

    required = {"date", "close"}
    if not required.issubset(set(df.columns)):
        raise ValueError(f"Unexpected data columns: {', '.join(map(str, df.columns))}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates("date")
    if "volume" not in df.columns:
        df["volume"] = np.nan
    return df.reset_index(drop=True)

def add_indicators(df):
    x = df.copy()
    x["SMA20"] = x["close"].rolling(20).mean()
    x["SMA50"] = x["close"].rolling(50).mean()
    delta = x["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    x["RSI14"] = 100 - (100 / (1 + rs))
    x["VOL20"] = x["volume"].rolling(20).mean()
    return x

def classify(row):
    if pd.isna(row["SMA20"]) or pd.isna(row["SMA50"]) or pd.isna(row["RSI14"]):
        return "WAIT", "Not enough history for indicators"
    volume_ok = pd.isna(row["VOL20"]) or pd.isna(row["volume"]) or row["volume"] >= row["VOL20"]
    if row["close"] > row["SMA20"] > row["SMA50"] and 50 <= row["RSI14"] <= 70 and volume_ok:
        return "BUY (SIM)", "Uptrend + positive momentum"
    if row["close"] < row["SMA20"] or row["RSI14"] > 75:
        return "EXIT (SIM)", "Trend weakened or momentum overheated"
    return "HOLD / WAIT", "Conditions do not fully match"

def init_state():
    if "cash" not in st.session_state:
        st.session_state.cash = STARTING_CASH
        st.session_state.positions = {}
        st.session_state.trades = []
        st.session_state.last_scan = None
        st.session_state.scan_rows = []

def run_scan():
    init_state()
    rows = []
    for symbol in UNIVERSE:
        try:
            hist = add_indicators(load_history(symbol))
            if len(hist) < 55:
                rows.append({"Symbol": symbol, "Signal": "WAIT", "Reason": "Insufficient history", "Data": "Incomplete"})
                continue
            r = hist.iloc[-1]
            signal, reason = classify(r)
            price = float(r["close"])
            rows.append({
                "Symbol": symbol, "Date": r["date"].date().isoformat(),
                "Close (₹)": round(price, 2),
                "SMA20": round(float(r["SMA20"]), 2),
                "SMA50": round(float(r["SMA50"]), 2),
                "RSI14": round(float(r["RSI14"]), 1),
                "Signal": signal, "Reason": reason, "Data": "OK"
            })

            # Exit existing simulated position first.
            pos = st.session_state.positions.get(symbol)
            if pos:
                entry = pos["entry"]
                if price <= entry * (1 - STOP_LOSS_PCT):
                    exit_reason = "Simulated stop threshold"
                elif price >= entry * (1 + TAKE_PROFIT_PCT):
                    exit_reason = "Simulated target threshold"
                elif signal == "EXIT (SIM)":
                    exit_reason = reason
                else:
                    exit_reason = None
                if exit_reason:
                    gross = pos["qty"] * price
                    cost = gross * SIMULATED_COST_RATE
                    net = gross - cost
                    pnl = net - pos["cost_basis"]
                    st.session_state.cash += net
                    st.session_state.trades.append({
                        "Date": r["date"].date().isoformat(), "Symbol": symbol,
                        "Action": "SIMULATED SELL", "Qty": pos["qty"],
                        "Price": round(price, 2), "P/L (₹)": round(pnl, 2),
                        "Reason": exit_reason
                    })
                    del st.session_state.positions[symbol]

            # Open a small virtual position only if the rule matches.
            if signal == "BUY (SIM)" and symbol not in st.session_state.positions:
                portfolio_value = st.session_state.cash + sum(
                    p["qty"] * p["last_price"] for p in st.session_state.positions.values()
                )
                allocation = min(st.session_state.cash, portfolio_value * MAX_POSITION_FRACTION)
                qty = int(allocation / (price * (1 + SIMULATED_COST_RATE)))
                if qty > 0:
                    gross = qty * price
                    fee = gross * SIMULATED_COST_RATE
                    total = gross + fee
                    if total <= st.session_state.cash:
                        st.session_state.cash -= total
                        st.session_state.positions[symbol] = {
                            "qty": qty, "entry": price, "cost_basis": total,
                            "last_price": price, "entry_date": r["date"].date().isoformat()
                        }
                        st.session_state.trades.append({
                            "Date": r["date"].date().isoformat(), "Symbol": symbol,
                            "Action": "SIMULATED BUY", "Qty": qty,
                            "Price": round(price, 2), "P/L (₹)": 0.0,
                            "Reason": reason
                        })

            if symbol in st.session_state.positions:
                st.session_state.positions[symbol]["last_price"] = price

        except Exception as e:
            rows.append({"Symbol": symbol, "Signal": "DATA ERROR", "Reason": str(e)[:140], "Data": "Unavailable"})

    st.session_state.scan_rows = rows
    st.session_state.last_scan = datetime.now().strftime("%Y-%m-%d %H:%M IST")
    st.session_state.auto_scan_day = date.today().isoformat()

init_state()

top1, top2 = st.columns(2)
with top1:
    st.metric("Virtual starting balance", f"₹{STARTING_CASH:,.0f}")
with top2:
    st.metric("Last scan", st.session_state.last_scan or "Not scanned yet")

if st.button("Run today's paper scan", type="primary", use_container_width=True):
    with st.spinner("Fetching end-of-day data and applying the fixed rules..."):
        run_scan()

# Run automatically once per date while this app session is active.
today_key = date.today().isoformat()
if st.session_state.get("auto_scan_day") != today_key:
    with st.spinner("Running the daily educational scan..."):
        run_scan()
    st.session_state.auto_scan_day = today_key

st.subheader("Daily stock scanner")
if st.session_state.scan_rows:
    scan_df = pd.DataFrame(st.session_state.scan_rows)
    st.dataframe(scan_df, use_container_width=True, hide_index=True)
    csv = scan_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download scan CSV", csv, "daily_stock_scan.csv", "text/csv")
else:
    st.info("No scan results yet. Run the scan to fetch the latest available end-of-day data.")

st.subheader("Virtual portfolio")
positions = st.session_state.positions
market_value = sum(p["qty"] * p["last_price"] for p in positions.values())
invested_cost = sum(p["cost_basis"] for p in positions.values())
unrealized = market_value - invested_cost
equity = st.session_state.cash + market_value
m1, m2, m3 = st.columns(3)
m1.metric("Cash", f"₹{st.session_state.cash:,.2f}")
m2.metric("Open positions value", f"₹{market_value:,.2f}")
m3.metric("Estimated total value", f"₹{equity:,.2f}", f"{equity-STARTING_CASH:+,.2f}")
st.caption(f"Unrealised P/L before any future exit costs: ₹{unrealized:,.2f}")
if positions:
    p_rows = []
    for sym, p in positions.items():
        p_rows.append({
            "Symbol": sym, "Qty": p["qty"], "Entry date": p["entry_date"],
            "Entry ₹": round(p["entry"], 2), "Latest close ₹": round(p["last_price"], 2),
            "Unrealised P/L ₹": round(p["qty"] * p["last_price"] - p["cost_basis"], 2)
        })
    st.dataframe(pd.DataFrame(p_rows), use_container_width=True, hide_index=True)
else:
    st.info("No open virtual positions.")

st.subheader("Trade history")
if st.session_state.trades:
    trades_df = pd.DataFrame(st.session_state.trades)
    st.dataframe(trades_df, use_container_width=True, hide_index=True)
    st.download_button("Download trade history", trades_df.to_csv(index=False).encode("utf-8"),
                       "paper_trade_history.csv", "text/csv")
else:
    st.info("No simulated trades have been recorded.")

with st.expander("How the rules work"):
    st.markdown("""
    - **Simulated BUY:** closing price above SMA20, SMA20 above SMA50, RSI(14) between 50 and 70, and volume at/above its 20-day average when volume is available.
    - **Simulated EXIT:** closing price below SMA20, RSI above 75, or a simulated 5% stop / 10% target threshold.
    - **Position size:** at most 10% of estimated virtual portfolio value per stock.
    - **Friction assumption:** illustrative 0.10% per side. Actual taxes, fees, slippage and market impact differ.
    - Signals use end-of-day values, not intraday prices.
    """)

st.caption(
    "Data source: TejHQ end-of-day NSE OHLCV API. Data is historical/end-of-day, not a live feed. "
    "The app's once-per-day auto-scan runs when the dashboard session is opened; it is not a guaranteed "
    "background scheduler. Session data may reset if the hosted app restarts. Download CSVs to keep records."
)
