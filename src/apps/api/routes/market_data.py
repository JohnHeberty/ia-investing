"""Market data API endpoint — real-time and historical prices."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, Query

from apps.api.security import AuthContext, get_auth_context
from ia_investing.market_data import (
    get_current_price,
    get_current_prices,
    get_financial_statements,
    get_fundamentals,
    get_historical_prices,
)

router = APIRouter(prefix="/api/v1/market-data", tags=["market-data"])


@router.get("/prices/{ticker}")
async def fetch_price(
    ticker: str,
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any] | None:
    """Fetch current price for a single ticker."""
    return await asyncio.to_thread(get_current_price, ticker)


@router.post("/prices")
async def fetch_prices(
    tickers: list[str],
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Fetch current prices for multiple tickers."""
    return await asyncio.to_thread(get_current_prices, tickers)


@router.get("/history/{ticker}")
async def fetch_history(
    ticker: str,
    period: str = Query("6mo", description="yfinance period"),
    interval: str = Query("1d", description="yfinance interval"),
    _auth: AuthContext = Depends(get_auth_context),
) -> list[dict[str, Any]]:
    """Fetch historical price data."""
    return await asyncio.to_thread(get_historical_prices, ticker, period=period, interval=interval)


@router.get("/fundamentals/{ticker}")
async def fetch_fundamentals(
    ticker: str,
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any] | None:
    """Fetch fundamental data for a ticker."""
    return await asyncio.to_thread(get_fundamentals, ticker)


@router.get("/financials/{ticker}")
async def fetch_financials(
    ticker: str,
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any] | None:
    """Fetch financial statements for a ticker."""
    return await asyncio.to_thread(get_financial_statements, ticker)
