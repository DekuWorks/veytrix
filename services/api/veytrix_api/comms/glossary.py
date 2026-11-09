"""Investing terms at three levels. This is fixed educational text, so replies that use it
are labelled `scripted`. It is not advice and not tied to any live data."""

from __future__ import annotations

from dataclasses import dataclass

from veytrix_api.comms.envelope import Level


@dataclass(frozen=True)
class Term:
    key: str
    title: str
    aliases: tuple[str, ...]
    beginner: str
    intermediate: str
    advanced: str

    def at(self, level: Level) -> str:
        return {
            "beginner": self.beginner,
            "intermediate": self.intermediate,
            "advanced": self.advanced,
        }[level]


TERMS: tuple[Term, ...] = (
    Term(
        "sma",
        "Simple moving average (SMA)",
        ("sma", "simple moving average", "moving average"),
        "The average closing price over the last N days. A 20-day SMA smooths out daily noise.",
        "The arithmetic mean of the last N closes. Short windows react fast and lag less; long "
        "windows are smoother and lag more.",
        "An equal-weight FIR filter on price with lag of about (N-1)/2 bars. It is a trend filter, "
        "not a forecast, and it whipsaws in ranges.",
    ),
    Term(
        "crossover",
        "Moving-average crossover",
        ("crossover", "golden cross", "death cross", "sma 20/50", "20/50"),
        "A signal when a faster average moves above or below a slower one. It hints the recent "
        "trend changed.",
        "A buy signal when the fast SMA crosses above the slow SMA, a sell when it crosses below. "
        "MAC-01 uses 20 and 50 days on AAPL.",
        "A lagging momentum rule. Edge after costs is uncertain, results are regime dependent, "
        "and over-tuning the windows overfits history.",
    ),
    Term(
        "paper trading",
        "Paper trading",
        ("paper trading", "paper", "simulated trading"),
        "Practising with pretend money. Nothing real is bought or sold.",
        "Simulated orders against real or sample prices. Fills are optimistic: no real queue, "
        "slippage, or rejections unless modelled.",
        "A forward test without capital at risk. It validates plumbing and logic, not execution "
        "quality, so slippage and partial fills need explicit models.",
    ),
    Term(
        "position size",
        "Position size",
        ("position size", "position sizing", "sizing", "size"),
        "How many shares or units you hold in one idea. Smaller size means smaller loss if wrong.",
        "Shares = (equity x risk fraction) / (entry - stop), then capped by a maximum allocation.",
        "Fixed-fractional sizing makes loss per trade a constant fraction of equity. Kelly-style "
        "sizing needs a trustworthy edge estimate, which small samples cannot give.",
    ),
    Term(
        "notional",
        "Notional",
        ("notional", "notional value"),
        "The dollar value of a position, such as 1 share at $200 is $200 notional.",
        "Quantity x price (x contract multiplier for futures). Caps on notional bound exposure.",
        "Notional measures gross exposure, not risk. A hedged book can have large notional and "
        "small net risk.",
    ),
    Term(
        "drawdown",
        "Drawdown",
        ("drawdown", "max drawdown"),
        "How far your account fell from its highest point.",
        "(Peak equity - current equity) / peak equity. Max drawdown is the worst such fall in a "
        "period.",
        "Path dependent. A 50% drawdown needs a 100% gain to recover. Drawdown is sensitive to "
        "sample length.",
    ),
    Term(
        "stop loss",
        "Stop loss",
        ("stop loss", "stop-loss", "stop"),
        "A price at which you plan to exit to limit a loss.",
        "A stop caps planned risk per share. In fast markets the fill can be worse than the stop.",
        "Stops define risk in sizing but add gap and slippage risk. Stop placement from volatility "
        "(for example ATR) beats arbitrary percentages.",
    ),
    Term(
        "slippage",
        "Slippage",
        ("slippage",),
        "The gap between the price you expected and the price you got.",
        "Caused by spread, market impact, and delay. Larger for illiquid assets and big orders.",
        "Modelled as a function of spread, volatility, and participation rate. DEX swaps add price "
        "impact from pool depth.",
    ),
    Term(
        "liquidity",
        "Liquidity",
        ("liquidity", "liquid"),
        "How easily you can buy or sell without moving the price.",
        "Tight spreads and deep order books mean high liquidity.",
        "Liquidity is time-varying and vanishes under stress, which is when it matters most.",
    ),
    Term(
        "spread",
        "Bid-ask spread",
        ("spread", "bid ask", "bid-ask", "bid/ask"),
        "The gap between the best price to buy and the best price to sell.",
        "You cross the spread when you trade at market. It is a direct cost per round trip.",
        "Quoted and effective spread differ; effective spread captures price improvement "
        "and impact.",
    ),
    Term(
        "volatility",
        "Volatility",
        ("volatility", "vol"),
        "How much a price moves up and down.",
        "Usually the standard deviation of returns, annualised. Higher volatility means wider "
        "outcomes both ways.",
        "Clusters over time (GARCH-type behaviour). Realised and implied volatility differ.",
    ),
    Term(
        "etf",
        "Exchange-traded fund (ETF)",
        ("etf", "exchange traded fund", "exchange-traded fund"),
        "A basket of assets you can buy like one share.",
        "Tracks an index or theme. Watch the expense ratio, tracking difference, and liquidity.",
        "Creation and redemption by authorised participants keeps price near NAV. Tracking error "
        "comes from fees, sampling, and cash drag.",
    ),
    Term(
        "expense ratio",
        "Expense ratio",
        ("expense ratio",),
        "The yearly fee a fund charges, as a percent of what you hold.",
        "A 0.10% ratio costs $1 a year per $1,000. It compounds against you.",
        "Total cost also includes spread, tracking difference, and tax drag.",
    ),
    Term(
        "futures",
        "Futures contract",
        ("futures", "future contract", "mes", "mnq"),
        "An agreement to buy or sell something at a set price on a set date. MES and MNQ are small "
        "index futures.",
        "Margined, leveraged, and marked to market daily. Each contract has a multiplier.",
        "Basis, roll, and margin calls drive risk. Leverage amplifies drawdown. FUTURES-01 is "
        "disabled in this build.",
    ),
    Term(
        "margin",
        "Margin",
        ("margin", "leverage"),
        "Borrowed money or a deposit that lets you control more than you put in. It magnifies "
        "losses too.",
        "Initial and maintenance margin set how much you must hold. Falling below it triggers "
        "a margin call.",
        "Leverage turns a small adverse move into a large equity loss and forced liquidation.",
    ),
    Term(
        "defi",
        "DeFi",
        ("defi", "decentralised finance", "decentralized finance"),
        "Financial apps that run on blockchains instead of banks.",
        "Smart contracts run swaps and lending. Risks include contract bugs, price impact, and "
        "fees.",
        "Composability multiplies smart-contract risk. This build only simulates swaps on "
        "testnets.",
    ),
    Term(
        "amm",
        "Automated market maker (AMM)",
        ("amm", "automated market maker", "uniswap"),
        "A pool of two tokens that sets prices by a formula instead of an order book.",
        "Constant-product pools keep x*y=k. Larger trades move the price more.",
        "Liquidity providers face impermanent loss. Concentrated liquidity changes depth and fee "
        "capture.",
    ),
    Term(
        "testnet",
        "Testnet",
        ("testnet", "sepolia", "devnet"),
        "A practice blockchain where tokens have no value.",
        "Allowed here: Solana devnet, Ethereum Sepolia, and Base Sepolia.",
        "Testnet liquidity and prices do not reflect mainnet. Quotes are read-only data.",
    ),
    Term(
        "reconciliation",
        "Reconciliation",
        ("reconciliation", "reconcile"),
        "Checking that your records match the broker's records.",
        "Compare local ledger rows with broker orders and fills, and flag any difference.",
        "Handle delayed fills, partial fills, and ambiguous responses without guessing. A local "
        "row is not a fill until the broker says so.",
    ),
    Term(
        "treasury",
        "Treasury",
        ("treasury", "payout", "distribution"),
        "Where profits would be set aside. Here it is a local projection only.",
        "A month projection from paper fills. It cannot move money.",
        "Loss carryforward and fees change the projection. Any real payout would need separate "
        "authorisation.",
    ),
    Term(
        "sharpe",
        "Sharpe ratio",
        ("sharpe", "sharpe ratio"),
        "Return per unit of risk. Higher is better, all else equal.",
        "(Mean excess return) / (standard deviation of returns), usually annualised.",
        "Penalises upside volatility, assumes normal returns, and is inflated by smoothing and "
        "short samples.",
    ),
    Term(
        "kill switch",
        "Kill switch",
        ("kill switch",),
        "A stop button that blocks the bot from placing orders.",
        "MAC-01 checks the switch before submitting. Only you can change it.",
        "A control that must fail closed. Releasing it is a human decision.",
    ),
    Term(
        "dividend",
        "Dividend",
        ("dividend", "dividends"),
        "A share of company profit paid to shareholders.",
        "Paid per share on a schedule. The price usually drops by about the dividend on the "
        "ex-date.",
        "Total return includes reinvested dividends. Taxes depend on the holding period.",
    ),
)

_BY_KEY = {term.key: term for term in TERMS}


def find(text: str) -> Term | None:
    """Longest alias found in the text wins."""

    lowered = f" {text.lower()} "
    best: tuple[int, Term] | None = None
    for term in TERMS:
        for alias in term.aliases:
            padded = f" {alias} "
            probe = lowered.replace("?", " ").replace(",", " ").replace(".", " ")
            if padded in probe and (best is None or len(alias) > best[0]):
                best = (len(alias), term)
    return best[1] if best else None


def level_from(text: str, default: Level = "beginner") -> Level:
    lowered = text.lower()
    if "advanced" in lowered or "expert" in lowered:
        return "advanced"
    if "intermediate" in lowered:
        return "intermediate"
    if "beginner" in lowered or "eli5" in lowered or "simple" in lowered:
        return "beginner"
    return default
