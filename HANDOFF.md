# HANDOFF

Owner: Claude Code
Last updated: 2026-11-22

## Position

Version 1 is built, pushed and live.

- Live site: https://nicejazaa7.github.io/global-fund-flow/
- Repo: https://github.com/nicejazaa7/global-fund-flow (public, branch `main`, GitHub Pages from `/`)
- Daily update: `.github/workflows/update-data.yml` runs `scripts/fetch_data.py` at 12:30 UTC, commits `data/live.json`, and that commit triggers a Pages rebuild by itself. Tested on GitHub on 2026-11-22: no source errors.

Page sections (`index.html`): where value sits, price effect versus real flow (SPY, SPEM, SPAB, GLD, IBIT), daily real flow (60 days), and M2 for the US, Eurozone, China and Japan.

## Decisions settled

- **No API keys.** All sources are free and keyless: CoinGecko, ECB, FRED CSV, State Street (SSGA) xlsx, and the iShares page.
- **Real flow formula.** Fund companies report shares outstanding one day late. So flow for day i = (shares on row i+1 − shares on row i) × NAV on day i, and price effect = shares × change in NAV. Checked against TD Securities: SPY outflow of $6.98B versus $7.0B published for the week ending 2026-11-06.
- **SPDR funds instead of iShares.** SSGA publishes a year of daily history for free, while iShares only shows the current day. IBIT history therefore grows one day per run.
- **Stocks come from Ocorian Global Asset Monitor** (full listed market value, one source and one date), not an FTSE free-float estimate. Ocorian splits North America from the rest of the world, not the US alone.
- **"Where value sits" rows overlap** and are never summed into one total.
- **M2 is shown per country.** No invented global M2.

## Hand-updated data

All in `data/slow.json`. Check schedule:

| When | Items |
|---|---|
| Every month, around the 25th | China M2 (PBOC), Japan M2 (Bank of Japan), and a health check: `data/live.json` should have `"errors": []` and the IBIT history should be growing |
| Mar, Jun, Sep, Dec (with the monthly check) | Debt (IIF Global Debt Monitor), gold tonnes (World Gold Council), stocks and private assets (Ocorian Global Asset Monitor) |
| October (with the monthly check) | Real estate (Savills) |

After changing `money_hand` (China or Japan), rerun `python scripts/fetch_data.py` or start the workflow, because the M2 bars read `live.json`. Changes to `stores` show straight away.

## Next action

Monthly data check around 2026-12-25: Japan M2 November (`ms2611.pdf`) and China M2 November (PBOC list page). That date also starts the quarterly checks. Look for an IIF Q3 2026 edition.

## Open questions

- A CoStar headline says global real estate is "$397.7 trillion", crediting Savills. CoStar blocks automated access, so the date is unconfirmed. Savills' own site still shows $393.3T (end 2024). Update the row if this turns out to be end-2025.
- The IBIT reading of the iShares page is the most likely part to break if iShares redesigns its site.
- If the repo gets no commits for 60 days, GitHub turns off the schedule. The daily data commits normally prevent this.
