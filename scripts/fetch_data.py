"""Fetch the fast-changing numbers and write data/live.json.

Run:  python scripts/fetch_data.py
Needs: openpyxl (pip install -r requirements.txt). No API keys.

If a source fails, the previous value from data/live.json is kept and the
failure is listed under "errors", so one broken source never blanks the page.
"""

import csv
import io
import json
import re
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent
SLOW = ROOT / "data" / "slow.json"
LIVE = ROOT / "data" / "live.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
TROY_OZ_PER_TONNE = 32150.7466
KEEP_DAYS = 260  # about one year of trading days

# Proxy ETFs: one per asset class. ETFs are only a slice of each market.
SSGA_ETFS = {
    "SPY": ("US stocks", "SPDR S&P 500 ETF"),
    "SPEM": ("Emerging market stocks", "SPDR Portfolio Emerging Markets ETF"),
    "SPAB": ("US bonds", "SPDR Portfolio Aggregate Bond ETF"),
    "GLD": ("Gold", "SPDR Gold Shares"),
}
IBIT_URL = "https://www.ishares.com/us/products/333011/ishares-bitcoin-trust-etf"


def get(url, ua=UA):
    req = urllib.request.Request(url, headers={"User-Agent": ua})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def get_json(url):
    return json.loads(get(url))


def ecb_last(series_key):
    """Return {series_key_row: (period, value)} from the ECB data API."""
    url = f"https://data-api.ecb.europa.eu/service/data/{series_key}?lastNObservations=1&format=csvdata"
    rows = csv.DictReader(io.StringIO(get(url).decode("utf-8")))
    return {r["KEY"]: (r["TIME_PERIOD"], float(r["OBS_VALUE"])) for r in rows}


def fetch_crypto():
    g = get_json("https://api.coingecko.com/api/v3/global")["data"]
    return {
        "total_mcap_usd": g["total_market_cap"]["usd"],
        "as_of": datetime.fromtimestamp(g["updated_at"], timezone.utc).isoformat(),
        "source": "CoinGecko",
    }


def fetch_gold(tonnes):
    p = get_json("https://api.coingecko.com/api/v3/simple/price?ids=pax-gold&vs_currencies=usd")
    price = p["pax-gold"]["usd"]
    return {
        "price_usd_oz": price,
        "value_usd": price * tonnes * TROY_OZ_PER_TONNE,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "source": "PAX Gold token price on CoinGecko (tracks 1 oz of gold)",
    }


def fetch_fx():
    rows = ecb_last("EXR/D.USD+CNY+JPY.EUR.SP00.A")
    usd = rows["EXR.D.USD.EUR.SP00.A"]
    cny = rows["EXR.D.CNY.EUR.SP00.A"]
    jpy = rows["EXR.D.JPY.EUR.SP00.A"]
    return {
        "EURUSD": usd[1],
        "USDCNY": cny[1] / usd[1],
        "USDJPY": jpy[1] / usd[1],
        "as_of": usd[0],
        "source": "ECB reference rates",
    }


def fetch_us_m2():
    start = (date.today() - timedelta(days=400)).isoformat()
    # A plain user agent: FRED times out on browser-like ones for this endpoint.
    text = get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id=M2SL&cosd={start}", ua="fund-flow-fetcher").decode()
    last = [r for r in csv.reader(io.StringIO(text))][-1]
    return {"id": "US", "label": "US M2", "usd_tn": float(last[1]) / 1000, "as_of": last[0],
            "source": "FRED (Federal Reserve), M2SL", "url": "https://fred.stlouisfed.org/series/M2SL"}


def fetch_ez_m2(eurusd):
    (period, val), = ecb_last("BSI/M.U2.Y.V.M20.X.1.U2.2300.Z01.E").values()
    return {"id": "EZ", "label": "Eurozone M2", "usd_tn": val / 1e6 * eurusd, "as_of": period,
            "source": "ECB data portal", "url": "https://data.ecb.europa.eu/"}


def fetch_ssga(ticker):
    url = f"https://www.ssga.com/us/en/intermediary/etfs/library-content/products/fund-data/etfs/us/navhist-us-en-{ticker.lower()}.xlsx"
    ws = openpyxl.load_workbook(io.BytesIO(get(url)), read_only=True).active
    hist = []
    for row in ws.iter_rows(values_only=True):
        try:
            d = datetime.strptime(str(row[0]).strip(), "%d-%b-%Y").date().isoformat()
            hist.append([d, float(row[1]), float(row[2]), float(row[3])])
        except (TypeError, ValueError, IndexError):
            continue  # header and footer rows
    if not hist:
        raise ValueError("no data rows found")
    hist.sort()
    return hist[-KEEP_DAYS:]


def fetch_ibit_snapshot():
    html = get(IBIT_URL).decode("utf-8", errors="ignore")
    text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))
    m = re.search(r"Shares Outstanding ([\d,]+) as of ([A-Z][a-z]{2} \d{1,2}, \d{4})", text)
    t = re.search(r'"Net Assets of Fund","value":"\$([\d,.]+)".{0,200}?"value":"([A-Z][a-z]{2} \d{1,2}, \d{4})"', html)
    if not (m and t):
        raise ValueError("iShares page layout changed")
    shares = float(m.group(1).replace(",", ""))
    tna = float(t.group(1).replace(",", ""))
    d = datetime.strptime(t.group(2), "%b %d, %Y").date().isoformat()
    return [d, tna / shares, shares, tna]


def main():
    slow = json.loads(SLOW.read_text(encoding="utf-8"))
    prev = json.loads(LIVE.read_text(encoding="utf-8")) if LIVE.exists() else {}
    out = {"generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "errors": []}

    def step(key, fn, *args):
        try:
            out[key] = fn(*args)
        except Exception as e:  # keep the last good value, record the failure
            out["errors"].append(f"{key}: {e}")
            if key in prev:
                out[key] = prev[key]

    step("crypto", fetch_crypto)
    step("gold", fetch_gold, slow["gold_above_ground_tonnes"]["value"])
    step("fx", fetch_fx)

    money = []
    prev_money = {m["id"]: m for m in prev.get("money", [])}
    for mid, fn, args in [("US", fetch_us_m2, ()), ("EZ", fetch_ez_m2, (out.get("fx", {}).get("EURUSD"),))]:
        try:
            money.append(fn(*args))
        except Exception as e:
            out["errors"].append(f"money {mid}: {e}")
            if mid in prev_money:
                money.append(prev_money[mid])
    fx = out.get("fx")
    for h in slow["money_hand"]:
        rate = fx and {"CNY": fx["USDCNY"], "JPY": fx["USDJPY"]}[h["currency"]]
        if rate:
            money.append({"id": h["id"], "label": h["label"], "usd_tn": h["value_local_tn"] / rate,
                          "as_of": h["as_of"], "source": h["source"] + ", entered by hand", "url": h["url"]})
    out["money"] = money

    etfs = {}
    prev_etfs = prev.get("etfs", {})
    for tk, (cls, name) in SSGA_ETFS.items():
        try:
            etfs[tk] = {"asset_class": cls, "name": name, "source": "State Street (SSGA) daily NAV history",
                        "history": fetch_ssga(tk)}
        except Exception as e:
            out["errors"].append(f"etf {tk}: {e}")
            if tk in prev_etfs:
                etfs[tk] = prev_etfs[tk]
    # iShares only shows today's figures, so IBIT history grows one day per run.
    ibit_hist = prev_etfs.get("IBIT", {}).get("history", [])
    try:
        snap = fetch_ibit_snapshot()
        ibit_hist = [r for r in ibit_hist if r[0] != snap[0]] + [snap]
        ibit_hist.sort()
    except Exception as e:
        out["errors"].append(f"etf IBIT: {e}")
    if ibit_hist:
        etfs["IBIT"] = {"asset_class": "Bitcoin", "name": "iShares Bitcoin Trust ETF",
                        "source": "iShares fund page (history builds up one day per run)",
                        "history": ibit_hist[-KEEP_DAYS:]}
    out["etfs"] = etfs

    LIVE.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"wrote {LIVE}  errors: {out['errors'] or 'none'}")


if __name__ == "__main__":
    main()
