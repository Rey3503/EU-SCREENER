"""
European Indices Screener — Backend
=====================================
API: Alpha Vantage
"""

from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

API_KEY = "ML6WPC02KC9L12TW"
AV_BASE = "https://www.alphavantage.co/query"

# ─── INDEX DEFINITIONS ────────────────────────────────────────────────────────
# Alpha Vantage tickers for European indices
INDICES = [
    {"name": "EURO STOXX 50", "ticker": "^STOXX50E", "country": "Europe",       "benchmark": True},
    {"name": "DAX",           "ticker": "^GDAXI",    "country": "Germany"},
    {"name": "CAC 40",        "ticker": "^FCHI",     "country": "France"},
    {"name": "FTSE 100",      "ticker": "^FTSE",     "country": "UK"},
    {"name": "IBEX 35",       "ticker": "^IBEX",     "country": "Spain"},
    {"name": "AEX",           "ticker": "^AEX",      "country": "Netherlands"},
    {"name": "SMI",           "ticker": "^SSMI",     "country": "Switzerland"},
    {"name": "ATX",           "ticker": "^ATX",      "country": "Austria"},
    {"name": "BEL 20",        "ticker": "^BFX",      "country": "Belgium"},
    {"name": "OMX Stockholm", "ticker": "^OMX",      "country": "Sweden"},
]

COLORS = [
    "#00d4ff","#ffd166","#ff6b35","#c8f56a","#ff4fd8",
    "#ff9f43","#a29bfe","#74b9ff","#55efc4","#fd79a8",
]


def fetch_weekly(ticker: str):
    """Fetch weekly adjusted closing prices from Alpha Vantage, rebased to 100."""
    try:
        params = {
            "function":   "TIME_SERIES_WEEKLY_ADJUSTED",
            "symbol":     ticker,
            "apikey":     API_KEY,
            "outputsize": "compact",  # last 100 weeks
        }
        r = requests.get(AV_BASE, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()

        # Check for API errors
        if "Error Message" in data:
            print(f"  ⚠ AV Error for {ticker}: {data['Error Message']}")
            return None, None
        if "Note" in data:
            print(f"  ⚠ AV Rate limit hit for {ticker}")
            return None, None
        if "Information" in data:
            print(f"  ⚠ AV Info for {ticker}: {data['Information']}")
            return None, None

        series = data.get("Weekly Adjusted Time Series", {})
        if not series:
            print(f"  ⚠ No data for {ticker}")
            return None, None

        # Sort by date ascending, take last 52 weeks
        sorted_dates = sorted(series.keys())[-52:]
        closes = [float(series[d]["5. adjusted close"]) for d in sorted_dates]
        labels = sorted_dates

        # Rebase to 100
        base = closes[0]
        rebased = [round(v / base * 100, 2) for v in closes]
        return rebased, labels

    except Exception as e:
        print(f"  ⚠ Exception for {ticker}: {e}")
        return None, None


def mansfield_rs(idx_data, bmk_data):
    """RSM_t = (idx_t / idx_0) / (bmk_t / bmk_0) - 1  (in %)"""
    n = min(len(idx_data), len(bmk_data))
    return [round((idx_data[i]/idx_data[0]) / (bmk_data[i]/bmk_data[0]) * 100 - 100, 4) for i in range(n)]


def perf(data, start, end):
    if start < 0 or end >= len(data):
        return None
    return round((data[end] - data[start]) / data[start] * 100, 2)


def signal(rsm):
    if rsm >= 8:    return "STRONG"
    elif rsm >= 1:  return "ABOVE"
    elif rsm >= -2: return "INLINE"
    else:           return "WEAK"


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/api/screener")
def screener():
    # Fetch benchmark first
    bmk = next(i for i in INDICES if i.get("benchmark"))
    bmk_data, bmk_labels = fetch_weekly(bmk["ticker"])

    if bmk_data is None:
        return jsonify({"error": f"Could not fetch benchmark {bmk['ticker']}"}), 500

    results = []
    for i, idx in enumerate(INDICES):
        color = COLORS[i % len(COLORS)]
        is_bmk = idx.get("benchmark", False)

        if is_bmk:
            data, labels = bmk_data, bmk_labels
            rs_series, rsm_final, sig = [0.0]*len(bmk_data), 0.0, "BENCHMARK"
        else:
            data, labels = fetch_weekly(idx["ticker"])
            if data is None:
                print(f"  ⚠ Skipping {idx['ticker']}")
                continue
            min_n     = min(len(data), len(bmk_data))
            data      = data[:min_n]
            rs_series = mansfield_rs(data, bmk_data[:min_n])
            rsm_final = rs_series[-1] if rs_series else 0.0
            sig       = signal(rsm_final)

        n = len(data)
        results.append({
            "name":      idx["name"],
            "ticker":    idx["ticker"],
            "country":   idx["country"],
            "color":     color,
            "benchmark": is_bmk,
            "data":      data,
            "labels":    labels or bmk_labels,
            "rs_series": rs_series,
            "rsm_final": round(rsm_final, 4),
            "signal":    sig,
            "ytd":       perf(data, 0, n-1),
            "m1":        perf(data, max(0, n-5),  n-1),
            "m3":        perf(data, max(0, n-13), n-1),
            "m6":        perf(data, max(0, n-26), n-1),
        })

    return jsonify({"indices": results, "updated": datetime.now().isoformat()})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    print("=" * 50)
    print("  European Indices Screener — Alpha Vantage")
    print("  http://localhost:5000/api/screener")
    print("=" * 50)
    app.run(port=5000, debug=True)
