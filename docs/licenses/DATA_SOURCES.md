# Data permissions registry

SAMPLE is generated in memory and is not a market price. BTC-USD, ETH-USD, and SOL-USD tickers, daily candles, and a short 1-minute window are fetched from the Coinbase Exchange public API for personal display on this machine. Adding another source means reading that publisher’s current terms first. Do not scrape a site because it has a public page. US equity prices are not included: no licensed equity feed is configured.

| Source | Sprint 0 | Permission note | Confidence |
| --- | --- | --- | --- |
| Synthetic SAMPLE | Used | Invented by this repository. Source id `synthetic-sample`. | High |
| Coinbase Exchange public market data | Used for BTC-USD, ETH-USD, and SOL-USD tickers, daily bars, and 1-minute bars | Personal research display on this machine. Terms prohibit redistribution, an app for other end users, benchmark use, and AI training. No key. Not stored in git or Postgres. | Medium. The terms page was read on 7 November 2026; this is not a legal opinion |
| SEC EDGAR | Not used | Public filings. Automated access needs a declared user agent and is capped at 10 requests per second. No API key for the public JSON APIs. | High on the access rule, from the SEC page checked on 7 November 2026 |
| FRED | Not used | St. Louis Fed API. An API key and the FRED terms are required before any call. | Medium; terms were not re-read line by line this sprint |
| NOAA | Not used | Public weather and climate data, with agency disclaimers. Confirm the specific product’s terms before storing it. | Medium |
| Quiver | Not used | Commercial dataset. No key is stored. Terms were not reviewed. | Low |
| TradingView Lightweight Charts | Library only | Apache-2.0 code. It does not include a market-data feed. | High |
| TradingView Charting Library | Not used | Proprietary. Not installed. | High |
| God's Eye data | Not used | Not MIT. Upstream cites TeleGeography CC BY-NC-SA 3.0, some CC BY-NC material, ODbL, and provider terms. See the upstream data file. | High that the carve-out exists; the files were not re-downloaded this sprint |
| Liquid.trade | Not used | Unverified candidate only. No client, no account, and no credential. Do not integrate it from this note. | Low |

## SEC detail

The fair-access page asks automated clients to identify themselves and to stay at or below 10 requests per second. A later EDGAR adapter has to send a user agent that names the project and a contact address. It must not hide in a generic browser agent. This sprint sends nothing.

- https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data
- https://www.sec.gov/search-filings/edgar-application-programming-interfaces

## God's Eye data

Code and data are different grants. The MIT licence on the God's Eye repository does not let Veytrix redistribute TeleGeography or other third-party datasets. The fork, if it happens, starts by deleting or replacing anything the data file does not allow. Upstream data notes: https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md

## Liquid.trade

Recorded only so a later session does not treat the name as an approved integration. The legal entity, the data licence, and the trading permissions were not verified. No endpoint is configured.

## References

Coinbase. (n.d.). *Market data terms*. https://www.coinbase.com/legal/market_data

Sidhu, B. (n.d.). *DATA_SOURCES.md*. GitHub. https://github.com/bilawalsidhu/gods-eye-view/blob/main/DATA_SOURCES.md

U.S. Securities and Exchange Commission. (n.d.). *Accessing EDGAR data*. https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data

U.S. Securities and Exchange Commission. (n.d.). *EDGAR application programming interfaces*. https://www.sec.gov/search-filings/edgar-application-programming-interfaces

Federal Reserve Bank of St. Louis. (n.d.). *FRED API*. https://fred.stlouisfed.org/docs/api/fred/

National Oceanic and Atmospheric Administration. (n.d.). *Disclaimer*. https://www.noaa.gov/disclaimer
