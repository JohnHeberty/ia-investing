from __future__ import annotations

import math as _math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

_TICKERS = [
    "PETR4",
    "VALE3",
    "ITUB4",
    "BBDC4",
    "ABEV3",
    "WEGE3",
    "BBAS3",
    "BOVA11",
    "USDBRL",
    "SMAL11",
]

_DAILY_SELIC_RATES: dict[str, Decimal] = {
    "2025-07-22": Decimal("0.000387"),
    "2025-07-23": Decimal("0.000387"),
    "2025-07-24": Decimal("0.000387"),
    "2025-07-25": Decimal("0.000387"),
    "2025-07-28": Decimal("0.000387"),
    "2025-07-29": Decimal("0.000387"),
    "2025-07-30": Decimal("0.000387"),
    "2025-07-31": Decimal("0.000385"),
    "2025-08-01": Decimal("0.000385"),
    "2025-08-04": Decimal("0.000385"),
    "2025-08-05": Decimal("0.000385"),
    "2025-08-06": Decimal("0.000383"),
    "2025-08-07": Decimal("0.000383"),
    "2025-08-08": Decimal("0.000383"),
    "2025-08-11": Decimal("0.000383"),
    "2025-08-12": Decimal("0.000383"),
    "2025-08-13": Decimal("0.000382"),
    "2025-08-14": Decimal("0.000382"),
    "2025-08-15": Decimal("0.000382"),
    "2025-08-18": Decimal("0.000382"),
    "2025-08-19": Decimal("0.000382"),
    "2025-08-20": Decimal("0.000380"),
    "2025-08-21": Decimal("0.000380"),
    "2025-08-22": Decimal("0.000380"),
    "2025-08-25": Decimal("0.000380"),
    "2025-08-26": Decimal("0.000378"),
    "2025-08-27": Decimal("0.000378"),
    "2025-08-28": Decimal("0.000378"),
    "2025-08-29": Decimal("0.000378"),
    "2025-09-01": Decimal("0.000376"),
    "2025-09-02": Decimal("0.000376"),
    "2025-09-03": Decimal("0.000376"),
    "2025-09-04": Decimal("0.000376"),
    "2025-09-05": Decimal("0.000376"),
    "2025-09-08": Decimal("0.000375"),
    "2025-09-09": Decimal("0.000375"),
    "2025-09-10": Decimal("0.000375"),
    "2025-09-11": Decimal("0.000375"),
    "2025-09-12": Decimal("0.000374"),
    "2025-09-15": Decimal("0.000374"),
    "2025-09-16": Decimal("0.000374"),
    "2025-09-17": Decimal("0.000374"),
    "2025-09-18": Decimal("0.000374"),
    "2025-09-19": Decimal("0.000373"),
    "2025-09-22": Decimal("0.000373"),
    "2025-09-23": Decimal("0.000373"),
    "2025-09-24": Decimal("0.000373"),
    "2025-09-25": Decimal("0.000373"),
    "2025-09-26": Decimal("0.000372"),
    "2025-09-29": Decimal("0.000372"),
    "2025-09-30": Decimal("0.000372"),
    "2025-10-01": Decimal("0.000370"),
    "2025-10-02": Decimal("0.000370"),
    "2025-10-03": Decimal("0.000370"),
    "2025-10-06": Decimal("0.000370"),
    "2025-10-07": Decimal("0.000370"),
    "2025-10-08": Decimal("0.000368"),
    "2025-10-09": Decimal("0.000368"),
    "2025-10-10": Decimal("0.000368"),
    "2025-10-13": Decimal("0.000368"),
    "2025-10-14": Decimal("0.000368"),
    "2025-10-15": Decimal("0.000366"),
    "2025-10-16": Decimal("0.000366"),
    "2025-10-17": Decimal("0.000366"),
    "2025-10-20": Decimal("0.000366"),
    "2025-10-21": Decimal("0.000366"),
    "2025-10-22": Decimal("0.000364"),
    "2025-10-23": Decimal("0.000364"),
    "2025-10-24": Decimal("0.000364"),
    "2025-10-27": Decimal("0.000364"),
    "2025-10-28": Decimal("0.000364"),
    "2025-10-29": Decimal("0.000364"),
    "2025-10-30": Decimal("0.000364"),
    "2025-10-31": Decimal("0.000364"),
    "2025-11-03": Decimal("0.000362"),
    "2025-11-04": Decimal("0.000362"),
    "2025-11-05": Decimal("0.000362"),
    "2025-11-06": Decimal("0.000362"),
    "2025-11-07": Decimal("0.000362"),
    "2025-11-10": Decimal("0.000361"),
    "2025-11-11": Decimal("0.000361"),
    "2025-11-12": Decimal("0.000361"),
    "2025-11-13": Decimal("0.000361"),
    "2025-11-14": Decimal("0.000361"),
    "2025-11-17": Decimal("0.000360"),
    "2025-11-18": Decimal("0.000360"),
    "2025-11-19": Decimal("0.000360"),
    "2025-11-21": Decimal("0.000360"),
    "2025-11-24": Decimal("0.000360"),
    "2025-11-25": Decimal("0.000359"),
    "2025-11-26": Decimal("0.000359"),
    "2025-11-27": Decimal("0.000359"),
    "2025-11-28": Decimal("0.000359"),
    "2025-12-01": Decimal("0.000358"),
    "2025-12-02": Decimal("0.000358"),
    "2025-12-03": Decimal("0.000358"),
    "2025-12-04": Decimal("0.000358"),
    "2025-12-05": Decimal("0.000358"),
    "2025-12-08": Decimal("0.000357"),
    "2025-12-09": Decimal("0.000357"),
    "2025-12-10": Decimal("0.000357"),
    "2025-12-11": Decimal("0.000357"),
    "2025-12-12": Decimal("0.000357"),
    "2025-12-15": Decimal("0.000356"),
    "2025-12-16": Decimal("0.000356"),
    "2025-12-17": Decimal("0.000355"),
    "2025-12-18": Decimal("0.000355"),
    "2025-12-19": Decimal("0.000355"),
    "2025-12-22": Decimal("0.000355"),
    "2025-12-23": Decimal("0.000355"),
    "2025-12-26": Decimal("0.000354"),
    "2025-12-29": Decimal("0.000354"),
    "2025-12-30": Decimal("0.000354"),
    "2026-01-02": Decimal("0.000354"),
    "2026-01-05": Decimal("0.000353"),
    "2026-01-06": Decimal("0.000353"),
    "2026-01-07": Decimal("0.000353"),
    "2026-01-08": Decimal("0.000353"),
    "2026-01-09": Decimal("0.000353"),
    "2026-01-12": Decimal("0.000352"),
    "2026-01-13": Decimal("0.000352"),
    "2026-01-14": Decimal("0.000352"),
    "2026-01-15": Decimal("0.000352"),
    "2026-01-16": Decimal("0.000352"),
    "2026-01-19": Decimal("0.000351"),
    "2026-01-20": Decimal("0.000351"),
    "2026-01-21": Decimal("0.000351"),
    "2026-01-22": Decimal("0.000350"),
    "2026-01-23": Decimal("0.000350"),
    "2026-01-26": Decimal("0.000350"),
    "2026-01-27": Decimal("0.000350"),
    "2026-01-28": Decimal("0.000350"),
    "2026-01-29": Decimal("0.000349"),
    "2026-01-30": Decimal("0.000349"),
    "2026-02-02": Decimal("0.000349"),
    "2026-02-03": Decimal("0.000349"),
    "2026-02-04": Decimal("0.000348"),
    "2026-02-05": Decimal("0.000348"),
    "2026-02-06": Decimal("0.000348"),
    "2026-02-09": Decimal("0.000348"),
    "2026-02-10": Decimal("0.000348"),
    "2026-02-11": Decimal("0.000347"),
    "2026-02-12": Decimal("0.000347"),
    "2026-02-13": Decimal("0.000346"),
    "2026-02-17": Decimal("0.000346"),
    "2026-02-18": Decimal("0.000346"),
    "2026-02-19": Decimal("0.000346"),
    "2026-02-20": Decimal("0.000346"),
    "2026-02-23": Decimal("0.000345"),
    "2026-02-24": Decimal("0.000345"),
    "2026-02-25": Decimal("0.000345"),
    "2026-02-26": Decimal("0.000345"),
    "2026-02-27": Decimal("0.000344"),
    "2026-03-02": Decimal("0.000344"),
    "2026-03-03": Decimal("0.000344"),
    "2026-03-04": Decimal("0.000344"),
    "2026-03-05": Decimal("0.000343"),
    "2026-03-06": Decimal("0.000343"),
    "2026-03-09": Decimal("0.000343"),
    "2026-03-10": Decimal("0.000343"),
    "2026-03-11": Decimal("0.000343"),
    "2026-03-12": Decimal("0.000342"),
    "2026-03-13": Decimal("0.000342"),
    "2026-03-16": Decimal("0.000342"),
    "2026-03-17": Decimal("0.000342"),
    "2026-03-18": Decimal("0.000341"),
    "2026-03-19": Decimal("0.000341"),
    "2026-03-20": Decimal("0.000341"),
    "2026-03-23": Decimal("0.000341"),
    "2026-03-24": Decimal("0.000341"),
    "2026-03-25": Decimal("0.000340"),
    "2026-03-26": Decimal("0.000340"),
    "2026-03-27": Decimal("0.000340"),
    "2026-03-30": Decimal("0.000340"),
    "2026-03-31": Decimal("0.000340"),
    "2026-04-01": Decimal("0.000339"),
    "2026-04-02": Decimal("0.000339"),
    "2026-04-03": Decimal("0.000339"),
    "2026-04-06": Decimal("0.000339"),
    "2026-04-07": Decimal("0.000339"),
    "2026-04-08": Decimal("0.000338"),
    "2026-04-09": Decimal("0.000338"),
    "2026-04-10": Decimal("0.000338"),
    "2026-04-13": Decimal("0.000338"),
    "2026-04-14": Decimal("0.000337"),
    "2026-04-15": Decimal("0.000337"),
    "2026-04-16": Decimal("0.000337"),
    "2026-04-17": Decimal("0.000337"),
    "2026-04-20": Decimal("0.000337"),
    "2026-04-22": Decimal("0.000336"),
    "2026-04-23": Decimal("0.000336"),
    "2026-04-24": Decimal("0.000336"),
    "2026-04-27": Decimal("0.000336"),
    "2026-04-28": Decimal("0.000336"),
    "2026-04-29": Decimal("0.000335"),
    "2026-04-30": Decimal("0.000335"),
    "2026-05-04": Decimal("0.000335"),
    "2026-05-05": Decimal("0.000335"),
    "2026-05-06": Decimal("0.000334"),
    "2026-05-07": Decimal("0.000334"),
    "2026-05-08": Decimal("0.000334"),
    "2026-05-11": Decimal("0.000334"),
    "2026-05-12": Decimal("0.000334"),
    "2026-05-13": Decimal("0.000333"),
    "2026-05-14": Decimal("0.000333"),
    "2026-05-15": Decimal("0.000333"),
    "2026-05-18": Decimal("0.000333"),
    "2026-05-19": Decimal("0.000333"),
    "2026-05-20": Decimal("0.000332"),
    "2026-05-21": Decimal("0.000332"),
    "2026-05-22": Decimal("0.000332"),
    "2026-05-25": Decimal("0.000332"),
    "2026-05-26": Decimal("0.000331"),
    "2026-05-27": Decimal("0.000331"),
    "2026-05-28": Decimal("0.000331"),
    "2026-05-29": Decimal("0.000331"),
    "2026-06-01": Decimal("0.000330"),
    "2026-06-02": Decimal("0.000330"),
    "2026-06-03": Decimal("0.000330"),
    "2026-06-04": Decimal("0.000330"),
    "2026-06-05": Decimal("0.000330"),
    "2026-06-08": Decimal("0.000329"),
    "2026-06-09": Decimal("0.000329"),
    "2026-06-10": Decimal("0.000329"),
    "2026-06-11": Decimal("0.000329"),
    "2026-06-12": Decimal("0.000328"),
    "2026-06-15": Decimal("0.000328"),
    "2026-06-16": Decimal("0.000328"),
    "2026-06-17": Decimal("0.000328"),
    "2026-06-18": Decimal("0.000328"),
    "2026-06-19": Decimal("0.000327"),
    "2026-06-22": Decimal("0.000327"),
    "2026-06-23": Decimal("0.000327"),
    "2026-06-24": Decimal("0.000327"),
    "2026-06-25": Decimal("0.000326"),
    "2026-06-26": Decimal("0.000326"),
    "2026-06-29": Decimal("0.000326"),
    "2026-06-30": Decimal("0.000326"),
    "2026-07-01": Decimal("0.000325"),
    "2026-07-02": Decimal("0.000325"),
    "2026-07-03": Decimal("0.000325"),
    "2026-07-06": Decimal("0.000325"),
    "2026-07-07": Decimal("0.000325"),
    "2026-07-08": Decimal("0.000324"),
    "2026-07-09": Decimal("0.000324"),
    "2026-07-10": Decimal("0.000324"),
    "2026-07-13": Decimal("0.000324"),
    "2026-07-14": Decimal("0.000324"),
    "2026-07-15": Decimal("0.000323"),
    "2026-07-16": Decimal("0.000323"),
    "2026-07-17": Decimal("0.000323"),
    "2026-07-20": Decimal("0.000323"),
    "2026-07-21": Decimal("0.000323"),
}


@dataclass(frozen=True)
class PricePoint:
    date: date
    ticker: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True)
class CorporateEvent:
    date: date
    ticker: str
    event_type: str
    description: str
    ratio: Decimal | None = None


@dataclass(frozen=True)
class TechnicalIndicators:
    sma_20: Decimal | None = None
    sma_50: Decimal | None = None
    ema_12: Decimal | None = None
    rsi_14: Decimal | None = None
    macd: Decimal | None = None
    macd_signal: Decimal | None = None
    bollinger_upper: Decimal | None = None
    bollinger_middle: Decimal | None = None
    bollinger_lower: Decimal | None = None


def _make_seed(ticker: str) -> dict[str, float]:
    seeds = {
        "PETR4": {"start": 38.50, "trend": 0.0004, "vol": 0.018},
        "VALE3": {"start": 62.80, "trend": -0.0001, "vol": 0.015},
        "ITUB4": {"start": 34.20, "trend": 0.0003, "vol": 0.012},
        "BBDC4": {"start": 28.90, "trend": 0.0002, "vol": 0.014},
        "ABEV3": {"start": 14.75, "trend": -0.0002, "vol": 0.011},
        "WEGE3": {"start": 42.30, "trend": 0.0005, "vol": 0.016},
        "BBAS3": {"start": 52.10, "trend": 0.0003, "vol": 0.013},
        "BOVA11": {"start": 132.40, "trend": 0.0002, "vol": 0.014},
        "USDBRL": {"start": 5.65, "trend": -0.0001, "vol": 0.008},
        "SMAL11": {"start": 96.20, "trend": 0.0001, "vol": 0.017},
    }
    return seeds[ticker]


def _trading_dates() -> list[date]:
    start = date(2025, 7, 22)
    end = date(2026, 7, 21)
    dates: list[date] = []
    d = start
    while d <= end:
        if d.weekday() < 5:
            dates.append(d)
        from datetime import timedelta

        d += timedelta(days=1)
    return dates


def _generate_prices() -> dict[str, list[PricePoint]]:
    dates = _trading_dates()
    result: dict[str, list[PricePoint]] = {}
    for ticker in _TICKERS:
        seed = _make_seed(ticker)
        price = seed["start"]
        candles: list[PricePoint] = []
        for dt in dates:
            change = seed["trend"] + seed["vol"] * _math.sin(dt.toordinal() * 0.3)
            price *= 1 + change + seed["vol"] * _math.sin(dt.toordinal() * 1.7) * 0.5
            open_px = round(price, 2)
            high_px = round(open_px * (1 + seed["vol"] * abs(_math.sin(dt.toordinal() * 2.1))), 2)
            low_px = round(open_px * (1 - seed["vol"] * abs(_math.sin(dt.toordinal() * 1.3))), 2)
            close_px = round(open_px * (1 + seed["vol"] * _math.sin(dt.toordinal() * 0.9) * 0.6), 2)
            vol = int(1_000_000 * (50 + 40 * abs(_math.sin(dt.toordinal() * 0.5))))
            candles.append(
                PricePoint(
                    date=dt,
                    ticker=ticker,
                    open=Decimal(str(open_px)),
                    high=Decimal(str(high_px)),
                    low=Decimal(str(low_px)),
                    close=Decimal(str(close_px)),
                    volume=vol,
                )
            )
            price = float(close_px)
        result[ticker] = candles
    return result


def _compute_sma(prices: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        s = sum(prices[i - period + 1 : i + 1], Decimal("0"))
        result[i] = (s / period).quantize(Decimal("0.01"))
    return result


def _compute_ema(prices: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(prices)
    k = Decimal(str(2 / (period + 1)))
    ema = prices[0]
    result[0] = ema.quantize(Decimal("0.01"))
    for i in range(1, len(prices)):
        ema = prices[i] * k + ema * (Decimal("1") - k)
        result[i] = ema.quantize(Decimal("0.01"))
    return result


def _compute_rsi(prices: list[Decimal], period: int) -> list[Decimal | None]:
    result: list[Decimal | None] = [None] * len(prices)
    if len(prices) < period + 1:
        return result
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for i in range(1, period + 1):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, Decimal("0")))
        losses.append(max(-diff, Decimal("0")))
    avg_gain = sum(gains, Decimal("0")) / period
    avg_loss = sum(losses, Decimal("0")) / period
    for i in range(period, len(prices)):
        if i > period:
            diff = prices[i] - prices[i - 1]
            current_gain = max(diff, Decimal("0"))
            current_loss = max(-diff, Decimal("0"))
            avg_gain = (avg_gain * (period - 1) + current_gain) / period
            avg_loss = (avg_loss * (period - 1) + current_loss) / period
        if avg_loss == Decimal("0"):
            result[i] = Decimal("100")
        else:
            rs = avg_gain / avg_loss
            result[i] = (Decimal("100") - Decimal("100") / (Decimal("1") + rs)).quantize(Decimal("0.1"))
    return result


def _compute_macd(prices: list[Decimal]) -> tuple[list[Decimal | None], list[Decimal | None]]:
    ema_12 = _compute_ema(prices, 12)
    ema_26 = _compute_ema(prices, 26)
    macd: list[Decimal | None] = [None] * len(prices)
    for i in range(26, len(prices)):
        e12 = ema_12[i]
        e26 = ema_26[i]
        if e12 is not None and e26 is not None:
            macd[i] = (e12 - e26).quantize(Decimal("0.01"))
    signal: list[Decimal | None] = [None] * len(prices)
    macd_values: list[Decimal] = [v for v in macd if v is not None]
    if len(macd_values) >= 9:
        signal_vals = _compute_ema(macd_values, 9)
        j = 0
        for i in range(len(prices)):
            if macd[i] is not None and signal_vals[j] is not None:
                signal[i] = signal_vals[j]
                j += 1
    return macd, signal


def _compute_bollinger(
    prices: list[Decimal],
    period: int = 20,
    num_std: Decimal = Decimal("2"),
) -> tuple[list[Decimal | None], list[Decimal | None], list[Decimal | None]]:
    sma = _compute_sma(prices, period)
    upper: list[Decimal | None] = [None] * len(prices)
    lower: list[Decimal | None] = [None] * len(prices)
    for i in range(period - 1, len(prices)):
        chunk = prices[i - period + 1 : i + 1]
        mean = sum(chunk, Decimal("0")) / period
        variance = sum(((p - mean) ** 2 for p in chunk), Decimal("0")) / period
        std = Decimal(str(_math.sqrt(float(variance))))
        s = sma[i]
        if s is not None:
            upper[i] = (s + num_std * std).quantize(Decimal("0.01"))
            lower[i] = (s - num_std * std).quantize(Decimal("0.01"))
    return upper, sma, lower


def _build_indicators(
    prices: dict[str, list[PricePoint]],
) -> dict[str, list[TechnicalIndicators]]:
    result: dict[str, list[TechnicalIndicators]] = {}
    for ticker, candles in prices.items():
        closes = [c.close for c in candles]
        sma_20 = _compute_sma(closes, 20)
        sma_50 = _compute_sma(closes, 50)
        ema_12 = _compute_ema(closes, 12)
        rsi = _compute_rsi(closes, 14)
        macd, signal = _compute_macd(closes)
        bb_upper, bb_mid, bb_lower = _compute_bollinger(closes)
        indicators: list[TechnicalIndicators] = []
        for i in range(len(closes)):
            indicators.append(
                TechnicalIndicators(
                    sma_20=sma_20[i],
                    sma_50=sma_50[i],
                    ema_12=ema_12[i],
                    rsi_14=rsi[i],
                    macd=macd[i],
                    macd_signal=signal[i],
                    bollinger_upper=bb_upper[i],
                    bollinger_middle=bb_mid[i],
                    bollinger_lower=bb_lower[i],
                )
            )
        result[ticker] = indicators
    return result


_PRICES = _generate_prices()
_INDICATORS = _build_indicators(_PRICES)
_TRADING_DATES = _trading_dates()

RISK_FREE_RATES: dict[date, Decimal] = {date.fromisoformat(k): v for k, v in _DAILY_SELIC_RATES.items()}

CORPORATE_EVENTS: list[CorporateEvent] = [
    CorporateEvent(
        date=date(2025, 9, 15),
        ticker="PETR4",
        event_type="dividend",
        description="Dividendo Juros sobre Capital Próprio R$ 0,87/ação",
        ratio=Decimal("0.0225"),
    ),
    CorporateEvent(
        date=date(2025, 12, 10),
        ticker="VALE3",
        event_type="dividend",
        description="Dividendo R$ 1,25/ação",
        ratio=Decimal("0.0198"),
    ),
    CorporateEvent(
        date=date(2026, 3, 1),
        ticker="ITUB4",
        event_type="split",
        description="Desdobramento 1:1 (split)",
        ratio=Decimal("2"),
    ),
    CorporateEvent(
        date=date(2026, 1, 20),
        ticker="BBDC4",
        event_type="dividend",
        description="Juros sobre Capital Próprio R$ 0,45/ação",
        ratio=Decimal("0.0156"),
    ),
    CorporateEvent(
        date=date(2026, 5, 5),
        ticker="ABEV3",
        event_type="dividend",
        description="Dividendo R$ 0,32/ação",
        ratio=Decimal("0.0217"),
    ),
    CorporateEvent(
        date=date(2026, 4, 15),
        ticker="WEGE3",
        event_type="dividend",
        description="Dividendo R$ 0,58/ação",
        ratio=Decimal("0.0137"),
    ),
    CorporateEvent(
        date=date(2026, 2, 10),
        ticker="BBAS3",
        event_type="dividend",
        description="Juros sobre Capital Próprio R$ 0,72/ação",
        ratio=Decimal("0.0138"),
    ),
]


@dataclass(frozen=True)
class GoldenMarketData:
    prices: dict[str, list[PricePoint]]
    indicators: dict[str, list[TechnicalIndicators]]
    risk_free_rates: dict[date, Decimal]
    corporate_events: list[CorporateEvent]
    trading_dates: list[date]


def load_golden_market(period_days: int = 252) -> GoldenMarketData:
    limit = len(_TRADING_DATES) if period_days >= len(_TRADING_DATES) else period_days
    dates_subset = _TRADING_DATES[-limit:]
    prices: dict[str, list[PricePoint]] = {}
    indicators: dict[str, list[TechnicalIndicators]] = {}
    for ticker in _TICKERS:
        full_prices = _PRICES[ticker]
        full_indicators = _INDICATORS[ticker]
        subset = [(p, i) for p, i in zip(full_prices, full_indicators, strict=False) if p.date in dates_subset]
        prices[ticker] = [sp for sp, _ in subset]
        indicators[ticker] = [si for _, si in subset]
    return GoldenMarketData(
        prices=prices,
        indicators=indicators,
        risk_free_rates=dict(RISK_FREE_RATES),
        corporate_events=list(CORPORATE_EVENTS),
        trading_dates=list(dates_subset),
    )
