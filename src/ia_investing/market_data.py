"""Market data service — fetches real-time and historical prices via yfinance.

Includes in-memory TTL cache to avoid excessive yfinance API calls:
- Fundamentals: 1 hour TTL (changes daily at most)
- Analyst data: 4 hours TTL (changes weekly)
- Historical prices: 15 minutes TTL (intraday changes)
- Current prices: no cache (always fresh)
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# In-memory TTL cache
# ---------------------------------------------------------------------------


class _TTLCache:
    """Simple thread-safe TTL cache with max size and LRU eviction."""

    def __init__(self, max_size: int = 512, default_ttl: float = 3600.0):
        self._store: dict[str, tuple[float, Any]] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str, ttl: float | None = None) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            self._misses += 1
            return None
        expires_at, value = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            self._misses += 1
            return None
        self._hits += 1
        return value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        if len(self._store) >= self._max_size:
            oldest_key = min(self._store, key=lambda k: self._store[k][0])
            del self._store[oldest_key]
        self._store[key] = (time.monotonic() + (ttl or self._default_ttl), value)

    def stats(self) -> dict[str, Any]:
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "N/A",
        }


# Separate caches per data type
_fundamentals_cache = _TTLCache(max_size=256, default_ttl=3600.0)  # 1 hour
_analyst_cache = _TTLCache(max_size=256, default_ttl=14400.0)  # 4 hours
_history_cache = _TTLCache(max_size=128, default_ttl=900.0)  # 15 minutes
_prices_cache = _TTLCache(max_size=128, default_ttl=60.0)  # 1 minute (batch only)


def get_cache_stats() -> dict[str, dict[str, Any]]:
    """Return cache statistics for monitoring."""
    return {
        "fundamentals": _fundamentals_cache.stats(),
        "analyst": _analyst_cache.stats(),
        "history": _history_cache.stats(),
        "prices": _prices_cache.stats(),
    }

# Brazilian tickers need .SA suffix for yfinance
_SA_SUFFIXES = (".SA", ".S", ".N")

# Map of common tickers that need .SA
_TICKER_MAP: dict[str, str] = {}


def _to_yf_ticker(ticker: str) -> str:
    """Convert a ticker to yfinance format (add .SA for Brazilian stocks)."""
    ticker = ticker.upper().strip()
    if ticker in _TICKER_MAP:
        return _TICKER_MAP[ticker]
    if ticker.endswith(_SA_SUFFIXES):
        return ticker
    # Known US tickers (5 chars max with dot already) — don't add .SA
    us_tickers = {"AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "TSLA", "META", "NVDA", "NFLX"}
    if ticker in us_tickers:
        return ticker
    # If it looks like a B3 ticker (3-5 chars, ends with digit 3/4/11), add .SA
    if 2 <= len(ticker) <= 5 and ticker[-1].isdigit():
        return f"{ticker}.SA"
    return ticker


def get_current_price(ticker: str) -> dict[str, Any] | None:
    """Fetch the current price for a single ticker."""
    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        info = t.fast_info
        price = getattr(info, "last_price", None)
        if price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
        if price is None:
            return None
        return {
            "ticker": ticker,
            "yf_ticker": yf_ticker,
            "price": float(price),
            "currency": getattr(info, "currency", "BRL"),
            "market_cap": float(getattr(info, "market_cap", 0) or 0),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning("Failed to fetch price for %s: %s", ticker, exc)
        return None


def get_current_prices(tickers: list[str]) -> dict[str, dict[str, Any]]:
    """Fetch current prices for multiple tickers efficiently."""
    results: dict[str, dict[str, Any]] = {}
    yf_tickers = [_to_yf_ticker(t) for t in tickers]
    yf_map = dict(zip(yf_tickers, tickers))

    try:
        data = yf.download(yf_tickers, period="1d", progress=False, threads=True)
        if data.empty:
            return results

        for yf_t, orig_t in yf_map.items():
            try:
                if len(yf_tickers) == 1:
                    close = float(data["Close"].iloc[-1])
                else:
                    close = float(data[("Close", yf_t)].iloc[-1])
                results[orig_t] = {
                    "ticker": orig_t,
                    "yf_ticker": yf_t,
                    "price": close,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            except (KeyError, IndexError):
                continue
    except Exception as exc:
        logger.warning("Batch price fetch failed: %s", exc)
        # Fallback: fetch individually
        for t in tickers:
            result = get_current_price(t)
            if result:
                results[t] = result

    return results


def get_historical_prices(
    ticker: str,
    period: str = "6mo",
    interval: str = "1d",
) -> list[dict[str, Any]]:
    """Fetch historical price data for a ticker (cached 15min).

    Args:
        ticker: Stock ticker symbol
        period: yfinance period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: yfinance interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    """
    cache_key = f"hist:{ticker}:{period}:{interval}"
    cached = _history_cache.get(cache_key)
    if cached is not None:
        return cached

    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period=period, interval=interval)
        if hist.empty:
            return []

        result = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
            }
            for idx, row in hist.iterrows()
        ]
        _history_cache.set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Failed to fetch history for %s: %s", ticker, exc)
        return []


def get_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch fundamental data for a ticker (cached 1h)."""
    cache_key = f"fund:{ticker}"
    cached = _fundamentals_cache.get(cache_key)
    if cached is not None:
        return cached

    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        info = t.info
        if not info:
            return None

        result = {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "debt_to_equity": info.get("debtToEquity"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "earnings_quarterly_growth": info.get("earningsQuarterlyGrowth"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "avg_volume": info.get("averageVolume"),
            "average_volume_10days": info.get("averageVolume10days"),
            "recommendation_mean": info.get("recommendationMean"),
            "number_of_analyst_opinions": info.get("numberOfAnalystOpinions"),
            "recommendation_key": info.get("recommendationKey"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "held_percent_insiders": info.get("heldPercentInsiders"),
            "held_percent_institutions": info.get("heldPercentInstitutions"),
            "short_ratio": info.get("shortRatio"),
            "short_percent_of_float": info.get("shortPercentOfFloat"),
            "free_cashflow": info.get("freeCashflow"),
            "operating_cashflow": info.get("operatingCashflow"),
            "payout_ratio": info.get("payoutRatio"),
            "currency": info.get("currency", "BRL"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        _fundamentals_cache.set(cache_key, result)
        return result
    except Exception as exc:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
        return None


def get_analyst_data(ticker: str) -> dict[str, Any] | None:
    """Fetch analyst consensus, upgrades/downgrades, and earnings estimates (cached 4h)."""
    cache_key = f"analyst:{ticker}"
    cached = _analyst_cache.get(cache_key)
    if cached is not None:
        return cached

    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        result: dict[str, Any] = {}

        info = t.info or {}
        result["recommendation_mean"] = info.get("recommendationMean")
        result["number_of_analysts"] = info.get("numberOfAnalystOpinions")
        result["recommendation_key"] = info.get("recommendationKey")
        result["target_mean_price"] = info.get("targetMeanPrice")
        result["target_high_price"] = info.get("targetHighPrice")
        result["target_low_price"] = info.get("targetLowPrice")
        result["current_price"] = info.get("currentPrice") or info.get("regularMarketPrice")

        try:
            ud = t.upgrades_downgrades
            if ud is not None and not ud.empty:
                recent = ud.head(10)
                result["recent_upgrades_downgrades"] = [
                    {"firm": str(row.get("Firm", "")), "action": str(row.get("Action", "")),
                     "from_grade": str(row.get("FromGrade", "")), "to_grade": str(row.get("ToGrade", ""))}
                    for _, row in recent.iterrows()
                ]
            else:
                result["recent_upgrades_downgrades"] = []
        except Exception:
            result["recent_upgrades_downgrades"] = []

        try:
            ed = t.earnings_estimate
            if ed is not None and not ed.empty:
                result["earnings_estimate"] = {
                    "next_quarter": {
                        "avg": float(ed.loc["0q", "avg"]) if "0q" in ed.index and "avg" in ed.columns else None,
                        "growth": float(ed.loc["0q", "growth"]) if "0q" in ed.index and "growth" in ed.columns else None,
                    }
                }
            else:
                result["earnings_estimate"] = None
        except Exception:
            result["earnings_estimate"] = None

        try:
            eh = t.earnings_history
            if eh is not None and not eh.empty:
                last = eh.iloc[-1]
                result["last_earnings_surprise"] = {
                    "eps_estimate": float(last.get("epsEstimate")) if last.get("epsEstimate") == last.get("epsEstimate") else None,
                    "eps_actual": float(last.get("epsActual")) if last.get("epsActual") == last.get("epsActual") else None,
                    "surprise_percent": float(last.get("surprisePercent")) if last.get("surprisePercent") == last.get("surprisePercent") else None,
                }
            else:
                result["last_earnings_surprise"] = None
        except Exception:
            result["last_earnings_surprise"] = None

        has_data = any(v is not None for v in result.values() if v != [] and v != {})
        if has_data:
            _analyst_cache.set(cache_key, result)
            return result
        return None
    except Exception as exc:
        logger.warning("Failed to fetch analyst data for %s: %s", ticker, exc)
        return None


def get_esg_data(ticker: str) -> dict[str, Any] | None:
    """Fetch ESG/sustainability data for a ticker."""
    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        sustain = t.sustainability
        if sustain is None or sustain.empty:
            return None

        result: dict[str, Any] = {}
        for key in ["ESG Score", "Environmental Score", "Social Score", "Governance Score", "Highest Controversy"]:
            val = sustain.loc[key].iloc[0] if key in sustain.index else None
            if val is not None and val == val:  # NaN check
                result[key.lower().replace(" ", "_")] = float(val)

        return result if result else None
    except Exception as exc:
        logger.warning("Failed to fetch ESG data for %s: %s", ticker, exc)
        return None


def get_financial_statements(ticker: str) -> dict[str, Any] | None:
    """Fetch financial statements (income statement, balance sheet, cash flow)."""
    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)

        income = t.income_stmt
        balance = t.balance_sheet
        cashflow = t.cashflow

        def _df_to_records(df):
            if df is None or df.empty:
                return []
            records = []
            for col in df.columns:
                record = {"period": col.strftime("%Y-%m-%d") if hasattr(col, "strftime") else str(col)}
                for idx in df.index:
                    val = df.loc[idx, col]
                    record[str(idx)] = float(val) if val == val else None  # NaN check
                records.append(record)
            return records

        return {
            "ticker": ticker,
            "income_statement": _df_to_records(income),
            "balance_sheet": _df_to_records(balance),
            "cash_flow": _df_to_records(cashflow),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning("Failed to fetch financials for %s: %s", ticker, exc)
        return None
