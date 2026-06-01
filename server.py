"""
European Indices Screener — Backend
====================================
Requirements:
    pip install flask flask-cors yfinance

Run:
    python server.py

Then open index.html in your browser.
"""

from flask import Flask, jsonify
from flask_cors import CORS
import yfinance as yf
from datetime import datetime, timedelta
import traceback

app = Flask(__name__)
CORS(app)  # Allow requests from the HTML file

# ─── INDEX DEFINITIONS ────────────────────────────────────────────────────────
INDICES = [
    {"name": "STOXX 600",     "ticker": "^STOXX",      "country": "Europe",       "benchmark": True},
    {"name": "DAX",           "ticker": "^GDAXI",      "country": "Germany"},
    {"name": "CAC 40",        "ticker": "^FCHI",       "country": "France"},
    {"name": "FTSE 100",      "ticker": "^FTSE",       "country": "UK"},
    {"name": "IBEX 35",       "ticker": "^IBEX",       "country": "Spain"},
    {"name": "FTSE MIB",      "ticker": "FTSEMIB.MI",  "country": "Italy"},
    {"name": "AEX",           "ticker": "^AEX",        "country": "Netherlands"},
    {"name": "SMI",           "ticker": "^SSMI",       "country": "Switzerland"},
    {"name": "OMX Stockholm", "ticker": "^OMX",        "country": "Sweden"},
    {"name": "PSI 20",        "ticker": "PSI20.LS",    "country": "Portugal"},
    {"name": "ATX",           "ticker": "^ATX",        "country": "Austria"},
    {"name": "BEL 20",        "ticker": "^BFX",        "country": "Belgium"},
    {"name": "WIG 20",        "ticker": "^WIG20",      "country": "Poland"},
    {"name": "OBX",           "ticker": "^OBX",        "country": "Norway"},
    {"name": "PX",            "ticker": "^PX",         "country": "Czech Rep."},
    {"name": "BUX",           "ticker": "^BUX",        "country": "Hungary"},
]

COLORS = [
    "#00d4ff","#ffd166","#ff6b35","#c8f56a","#ff4fd8",
    "#ff9f43","#a29bfe","#74b9ff","#55efc4","#fd79a8",
    "#e17055","#81ecec","#b2bec3","#dfe6e9","#fab1a0","#fdcb6e",
]


def fetch_weekly(ticker: str, period: str = "1y"):
    """Fetch weekly closing prices, rebased to 100."""
    t = yf.Ticker(ticker)
    hist = t.history(period=period, interval="1wk")
    if hist.empty:
        return None, None
    closes = hist["Close"].dropna()
    base = closes.iloc[0]
    rebased = (closes / base * 100).round(2).tolist()
    labels = [d.strftime("%Y-%m-%d") for d in closes.index]
    return rebased, labels


def mansfield_rs(idx_data, bmk_data):
    """
    Mansfield RS at each point:
        RSM_t = (idx_t / idx_0) / (bmk_t / bmk_0) - 1
    Returned as a list of floats (%).
    """
    n = min(len(idx_data), len(bmk_data))
    rs = []
    for i in range(n):
        idx_perf = idx_data[i] / idx_data[0]
        bmk_perf = bmk_data[i] / bmk_data[0]
        rs.append(round((idx_perf / bmk_perf - 1) * 100, 4))
    return rs


def perf(data, start, end):
    """Percentage performance between two indices of the data list."""
    if start < 0 or end >= len(data):
        return None
    return round((data[end] - data[start]) / data[start] * 100, 2)


def signal(rsm_final):
    """Map final Mansfield RS value to a signal string."""
    if rsm_final >= 8:
        return "STRONG"
    elif rsm_final >= 1:
        return "ABOVE"
    elif rsm_final >= -2:
        return "INLINE"
    else:
        return "WEAK"


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/api/screener")
def screener():
    """
    Returns all indices with:
    - Weekly rebased price series
    - Weekly Mansfield RS series vs STOXX 600
    - Performance metrics (YTD, 1M, 3M, 6M)
    - Signal
    """
    # 1. Fetch benchmark first
    bmk_ticker = next(i["ticker"] for i in INDICES if i.get("benchmark"))
    bmk_data, bmk_labels = fetch_weekly(bmk_ticker)

    if bmk_data is None:
        return jsonify({"error": f"Could not fetch benchmark {bmk_ticker}"}), 500

    results = []
    n = len(bmk_data)

    for i, idx in enumerate(INDICES):
        color = COLORS[i % len(COLORS)]
        is_benchmark = idx.get("benchmark", False)

        if is_benchmark:
            data = bmk_data
            labels = bmk_labels
            rs_series = [0.0] * n
            rsm_final = 0.0
            sig = "BENCHMARK"
        else:
            data, labels = fetch_weekly(idx["ticker"])
            if data is None:
                print(f"  ⚠ Could not fetch {idx['ticker']}, skipping.")
                continue
            # Align lengths
            min_n = min(len(data), len(bmk_data))
            data = data[:min_n]
            rs_series = mansfield_rs(data, bmk_data[:min_n])
            rsm_final = rs_series[-1] if rs_series else 0.0
            sig = signal(rsm_final)

        n_pts = len(data)
        results.append({
            "name":       idx["name"],
            "ticker":     idx["ticker"],
            "country":    idx["country"],
            "color":      color,
            "benchmark":  is_benchmark,
            "data":       data,
            "labels":     labels if labels else bmk_labels,
            "rs_series":  rs_series,
            "rsm_final":  round(rsm_final, 4),
            "signal":     sig,
            "ytd":        perf(data, 0, n_pts - 1),
            "m1":         perf(data, max(0, n_pts - 5),  n_pts - 1),
            "m3":         perf(data, max(0, n_pts - 13), n_pts - 1),
            "m6":         perf(data, max(0, n_pts - 26), n_pts - 1),
        })

    return jsonify({"indices": results, "updated": datetime.now().isoformat()})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


# ─── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  European Indices Screener — Backend")
    print("  http://localhost:5000/api/screener")
    print("=" * 50)
    app.run(port=5000, debug=True)
