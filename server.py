"""
European Indices Screener — Backend
=====================================
API: Twelve Data (https://twelvedata.com)
Free plan: 800 calls/day
"""

from flask import Flask, jsonify
from flask_cors import CORS
import requests
from datetime import datetime

app = Flask(__name__)
CORS(app)

API_KEY = "119a73bda0984bd8b9225a864d30cce4"
BASE    = "https://api.twelvedata.com/time_series"

# ─── INDEX DEFINITIONS ────────────────────────────────────────────────────────
INDICES = [
    {"name": "EURO STOXX 50", "ticker": "SX5E",    "country": "Europe",       "benchmark": True},
    {"name": "DAX",           "ticker": "DAX",     "country": "Germany"},
    {"name": "CAC 40",        "ticker": "CAC40",   "country": "France"},
    {"name": "FTSE 100",      "ticker": "FTSE100", "country": "UK"},
    {"name": "IBEX 35",       "ticker": "IBEX35",  "country": "Spain"},
    {"name": "FTSE MIB",      "ticker": "FTSEMIB", "country": "Italy"},
    {"name": "AEX",           "ticker": "AEX",     "country": "Netherlands"},
    {"name": "SMI",           "ticker": "SMI",     "country": "Switzerland"},
    {"name": "OMX S30",       "ticker": "OMXS30",  "country": "Sweden"},
    {"name": "ATX",           "ticker": "ATX",     "country": "Austria"},
    {"name": "BEL 20",        "ticker": "BEL20",   "country": "Belgium"},
    {"name": "WIG 20",        "ticker": "WIG20",   "country": "Poland"},
    {"name": "OBX",           "ticker": "OBX",     "country": "Norway"},
    {"name": "PSI 20",        "ticker": "PSI20",   "country": "Portugal"},
    {"name": "BUX",           "ticker": "BUX",     "country": "Hungary"},
]

COLORS = [
    "#00d4ff","#ffd166","#ff6b35","#c8f56a","#ff4fd8",
    "#ff9f43","#a29bfe","#74b9ff","#55efc4","#fd79a8",
    "#e17055","#81ecec","#b2bec3","#dfe6e9","#fdcb6e",
]


def fetch_weekly(ticker: str, outputsize: int = 52):
    """Fetch weekly closing prices from Twelve Data, rebased to 100."""
    try:
        r = requests.get(BASE, params={
            "symbol":     ticker,
            "interval":   "1week",
            "outputsize": outputsize,
            "apikey":     API_KEY,
        }, timeout=15)
        r.raise_for_status()
        data = r.json()

        if "values" not in data:
            msg = data.get("message", data.get("code", "no values"))
            print(f"  ⚠ {ticker}: {msg}")
            return None, None

        # Twelve Data returns newest first — reverse to get chronological order
        values = list(reversed(data["values"]))
        closes = [float(v["close"]) for v in values]
        labels = [v["datetime"] for v in values]

        if len(closes) < 2:
            return None, None

        # Rebase to 100
        base    = closes[0]
        rebased = [round(v / base * 100, 2) for v in closes]
        return rebased, labels

    except Exception as e:
        print(f"  ⚠ Exception for {ticker}: {e}")
        return None, None


def mansfield_rs(idx_data, bmk_data):
    """
    Mansfield RS:
        RSM_t = (idx_t / idx_0) / (bmk_t / bmk_0) - 1  (expressed in %)
    """
    n = min(len(idx_data), len(bmk_data))
    return [
        round((idx_data[i] / idx_data[0]) / (bmk_data[i] / bmk_data[0]) * 100 - 100, 4)
        for i in range(n)
    ]


def perf(data, start, end):
    if start < 0 or end >= len(data):
        return None
    return round((data[end] - data[start]) / data[start] * 100, 2)


def signal(rsm):
    if rsm >= 8:     return "STRONG"
    elif rsm >= 1:   return "ABOVE"
    elif rsm >= -2:  return "INLINE"
    else:            return "WEAK"


# ─── ROUTES ───────────────────────────────────────────────────────────────────
@app.route("/api/screener")
def screener():
    # 1. Fetch benchmark first
    bmk      = next(i for i in INDICES if i.get("benchmark"))
    bmk_data, bmk_labels = fetch_weekly(bmk["ticker"])

    if bmk_data is None:
        return jsonify({"error": f"Could not fetch benchmark {bmk['ticker']}"}), 500

    results = []
    for i, idx in enumerate(INDICES):
        color  = COLORS[i % len(COLORS)]
        is_bmk = idx.get("benchmark", False)

        if is_bmk:
            data, labels   = bmk_data, bmk_labels
            rs_series      = [0.0] * len(bmk_data)
            rsm_final, sig = 0.0, "BENCHMARK"
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
            "ytd":       perf(data, 0, n - 1),
            "m1":        perf(data, max(0, n - 5),  n - 1),
            "m3":        perf(data, max(0, n - 13), n - 1),
            "m6":        perf(data, max(0, n - 26), n - 1),
        })

    return jsonify({"indices": results, "updated": datetime.now().isoformat()})


@app.route("/api/health")
def health():
    return jsonify({"status": "ok", "time": datetime.now().isoformat()})


if __name__ == "__main__":
    print("=" * 50)
    print("  EU Screener — Twelve Data API")
    print("  http://localhost:5000/api/screener")
    print("=" * 50)
    app.run(port=5000, debug=True)
