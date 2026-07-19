from database.models.instrument_master import InstrumentIdentifier, Listing
from ia_investing.application.instruments import normalize_alias


def test_alias_normalization_is_accent_and_whitespace_insensitive() -> None:
    assert normalize_alias("  Petróleo   Brasileiro S.A. ") == "petroleo brasileiro s.a."


def test_temporal_identity_constraints_are_registered() -> None:
    listing_constraints = {constraint.name for constraint in Listing.__table__.constraints}
    identifier_constraints = {constraint.name for constraint in InstrumentIdentifier.__table__.constraints}
    assert "ex_listings_ticker_window" in listing_constraints
    assert "ex_instrument_identifiers_value_window" in identifier_constraints
