from __future__ import annotations

from datetime import date as DateType
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


class CVMCompanyProfile(BaseModel):
    cnpj: str
    legal_name: str
    cvm_code: str
    reference_date: str
    sector: str | None = None
    website: str | None = None
    issuer_status: str | None = None
    registration_status: str | None = None
    registration_category: str | None = None


class CVMSecurityProfile(BaseModel):
    cnpj: str
    trading_code: str | None = None
    market: str | None = None
    segment: str | None = None
    listing_start_date: str | None = None
    security_type: str = ""


class B3ListingProfile(BaseModel):
    ticker: str
    exchange: str = "BOVESPA"
    market_segment: str | None = None
    listing_status: Literal["active", "inactive", "suspended"] = "active"
    average_volume_30d: Decimal | None = None
    closing_price: Decimal | None = None
    last_trade_date: DateType | None = None
