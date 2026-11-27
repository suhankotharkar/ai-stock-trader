# AI Stock Trader India — Version 1 (Paper Trading Only)

A mobile-friendly educational Streamlit dashboard for Indian NSE equities.

## Included
- Daily end-of-day stock scan for a small fixed NSE watchlist.
- SMA20, SMA50 and RSI14 calculations.
- Rule-based simulated BUY / EXIT / HOLD signals.
- Virtual portfolio starting at ₹1,00,000.
- Simulated position sizing, 5% stop threshold and 10% target threshold.
- Downloadable CSV scan and trade history.

## Important limitations
- This is an educational prototype, not investment advice.
- It cannot connect to a broker and cannot place real orders.
- TejHQ's API provides end-of-day data, not live intraday quotes.
- The app auto-scans once per calendar day when its dashboard session is opened. It does NOT run a guaranteed background job while nobody is viewing it.
- Streamlit session state is temporary. If the hosted app restarts, the virtual portfolio can reset. Download CSVs to keep copies.
- The example watchlist and rules are for learning only; they are not validated as profitable.
- The illustrative 0.10% per-side cost is not an exact estimate of all Indian market charges.

## Run locally
1. Install Python 3.11 or newer.
2. Open a terminal in this folder.
3. Run:
   `pip install -r requirements.txt`
4. Run:
   `streamlit run app.py`

## Deploy for mobile access
1. Create a GitHub repository and upload `app.py` and `requirements.txt`.
2. Sign in to Streamlit Community Cloud.
3. Create an app, select your repository, and choose `app.py`.
4. Deploy. Open the generated `*.streamlit.app` address in your phone browser and use **Add to Home screen** if desired.

## Data
The app uses the documented public end-of-day OHLCV route:
`https://api.tejhq.dev/v1/ohlcv/nse/{SYMBOL}?from=YYYY-MM-DD&to=YYYY-MM-DD`

Provider documentation: https://tejhq.dev/docs
Data project notes: https://github.com/tejhq/tej-bazaar

Check the provider's current terms and availability before relying on it. If the API response schema changes, update `extract_rows()` / field normalization in `app.py`.
