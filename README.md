# Global Fund Flow

A one-page web app that shows where the world's value sits, and how much of each move is real new money versus a change in price.

## How the data updates

| Data | How it updates |
|---|---|
| Crypto total, gold price | Your browser fetches them from CoinGecko every minute |
| Fund flows (SPY, SPEM, SPAB, GLD, IBIT), US and Eurozone M2, exchange rates | `scripts/fetch_data.py` runs every day on GitHub Actions and commits `data/live.json` |
| Real estate, debt, stock totals, China and Japan M2, gold tonnes | You edit `data/slow.json` by hand when a new report comes out |

No API keys are needed.

## Run it on your computer

```bash
pip install -r requirements.txt
```

```bash
python scripts/fetch_data.py
```

```bash
python -m http.server 8765
```

Then open http://localhost:8765. Opening `index.html` directly does not work, because browsers block loading the data files that way.

## Put it online with GitHub Pages

1. Create a **public** repository on GitHub and push this folder to it.
2. In the repository, open **Settings → Pages**. Under "Build and deployment", choose **Deploy from a branch**, branch `main`, folder `/ (root)`.
3. Open the **Actions** tab, choose **Update data**, and click **Run workflow** once to test it.

After that, the data refreshes every day by itself.

## Known limits

- IBIT's history starts on the first day the script runs, because iShares only shows the current day's figures. Its 20-day view fills in after about 20 trading days.
- Japan M2 in `data/slow.json` is from April 2026 and needs a manual update.
- ETFs are a small slice of each market, so their flows are a signal, not the whole picture.
