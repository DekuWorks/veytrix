# Third-party notices

Veytrix itself is proprietary. See the root `LICENSE`. The items below are other people's work. Versions move; the package locks are the inventory that CI installs.

## TradingView Lightweight Charts

The web app depends on `lightweight-charts` 5.2.1, the open-source charting library. On 7 November 2026, `npm view lightweight-charts license` reported `Apache-2.0` for version 5.2.1.

This is not the proprietary TradingView Charting Library (also called Advanced Charts). That library is not installed and its terms are not accepted by this repository.

The UI links to the Apache licence. The chart is used to draw the synthetic SAMPLE series only.

- Package: https://www.npmjs.com/package/lightweight-charts
- Licence: https://github.com/tradingview/lightweight-charts/blob/master/LICENSE
- Proprietary library, not used: https://www.tradingview.com/charting-library-docs/

## God's Eye

Not forked and not vendored. Pinned for a later audit only:

- Repository: https://github.com/bilawalsidhu/gods-eye-view
- Commit: `52187c91d188504188ea9e9ae33e5b6e24cab7f2` (2026-11-07)
- Code licence: https://github.com/bilawalsidhu/gods-eye-view/blob/main/LICENSE

The MIT grant covers upstream source code, not the third-party datasets described in the upstream `DATA_SOURCES.md`. Veytrix is not God's Eye and is not an official or endorsed version. Brand note: https://godseyeview.ai/brand/

## 21st.dev Dashboard Shell

Component id 43212, “Dashboard Shell”, by isaiahbjork on https://21st.dev, was inspected for this sprint. The retrieval included component source and a demo. It did not include a licence text, and it did not include the kit imported as `@/components/ui/app-dashboard-shell-utils/app-block-kit`. The demo is a commerce orders dashboard.

That source was not copied and is not installed. The Veytrix shell is an original layout that keeps a familiar interaction pattern: a collapsible sidebar, a drawer below about 768px, a skip link, a visible focus style, `aria-current`, summary cards, and Escape to close the drawer. Do not describe 21st.dev components as installed.

## Fonts

IBM Plex Sans and IBM Plex Mono are loaded from the `@fontsource` packages so the browser does not call Google Fonts at runtime. IBM Plex is published under the SIL Open Font License.

- https://github.com/ibm/plex

## Other runtime packages

These are used as libraries. Their own licences stay in the installed distributions. Confidence is high for the names below and medium for “no other copyleft surprise”, because that depends on the resolved tree:

| Package | Role | Licence, as commonly published |
| --- | --- | --- |
| FastAPI | API | MIT |
| Uvicorn | ASGI server | BSD |
| Pydantic | Models | MIT |
| SQLAlchemy | ORM | MIT |
| Alembic | Migrations | MIT |
| psycopg | Postgres driver | GNU LGPL 3.0 |
| React | UI | MIT |
| Vite | Bundler | MIT |
| Tailwind CSS | Styles | MIT |
| TypeScript | Types | Apache-2.0 |
| PostgreSQL 16 | Database image | PostgreSQL licence |

psycopg’s LGPL status matters if Veytrix is ever distributed as a binary. This sprint does not distribute a binary. Confirm the wheel licence again before any distribution.

## References

Fontsource. (n.d.). *IBM Plex Sans*. npm. https://www.npmjs.com/package/@fontsource/ibm-plex-sans

IBM. (n.d.). *IBM Plex*. https://github.com/ibm/plex

Sidhu, B. (n.d.). *God's Eye* [Source code]. https://github.com/bilawalsidhu/gods-eye-view

TradingView. (n.d.). *Lightweight Charts* [Source code]. https://github.com/tradingview/lightweight-charts

TradingView. (n.d.). *Advanced Charts documentation*. https://www.tradingview.com/charting-library-docs/
