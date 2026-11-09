# Product requirements

Status on 8 November 2026: the "this sprint" list below is the original scope. The tree has since added a Coinbase display (BTC-USD, ETH-USD, SOL-USD), the MAC-01 CLI, and simulated testnet swaps. Authentication, a broker balance, and AWS are still absent. Current behaviour is `docs/architecture/current-state.md`.

Veytrix is a private research desk for one person. Tagline: Intelligence beyond the market. It is not a customer product. There is no onboarding, subscription, or tenant model.

## This sprint

- A local dashboard with an accessible shell, an overview of health and posture, one synthetic chart, and a paper sizing form.
- An API that reports liveness, readiness, and diagnostics without secrets.
- One synthetic instrument: SAMPLE, venue SIM, equity, USD, source `synthetic-sample`.
- One series: synthetic SAMPLE, venue SIM, source id `synthetic-sample`. No vendor prices.
- A long-only sizing calculator with decimal arithmetic and a hard risk-fraction ceiling of 0.02.
- A Postgres baseline and a repeatable local check.

## Always

- No investment advice and no claim that a method makes money.
- No real-money order is authorised. The MAC-01 live gate exists and is unused. Shorts, leverage, derivative execution, wallet signatures, and bank transfers stay out.
- Model output and web content do not execute trades.
- Agents do not receive production withdrawal permissions.
- Paper results say that stops can fail.

## Not in this sprint

Authentication, MFA, CSRF tokens, a distributed rate limit, enforcement of the daily or weekly stop, God's Eye source, and any order route on the API.

Later work that is already in the tree, and is outside this original list: Coinbase display data, the MAC-01 ledger (not an API order route), and simulated swap rows. Stops on the sizing policy are still not enforced.

## Acceptance for the sizing response

The response includes `execution_permitted: false` and `order_submitted: false`. The route does not insert an order. Unknown symbols are not given a price. If the market API fails, the UI shows an error.
