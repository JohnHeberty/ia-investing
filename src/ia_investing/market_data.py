"""Market data service — fetches real-time and historical prices via yfinance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

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
    """Fetch historical price data for a ticker.

    Args:
        ticker: Stock ticker symbol
        period: yfinance period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
        interval: yfinance interval (1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo)
    """
    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period=period, interval=interval)
        if hist.empty:
            return []

        return [
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
    except Exception as exc:
        logger.warning("Failed to fetch history for %s: %s", ticker, exc)
        return []


def get_fundamentals(ticker: str) -> dict[str, Any] | None:
    """Fetch fundamental data for a ticker."""
    yf_ticker = _to_yf_ticker(ticker)
    try:
        t = yf.Ticker(yf_ticker)
        info = t.info
        if not info:
            return None

        return {
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
            "revenue": info.get("totalRevenue"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "dividend_yield": info.get("dividendYield"),
            "beta": info.get("beta"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "avg_volume": info.get("averageVolume"),
            "currency": info.get("currency", "BRL"),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
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
