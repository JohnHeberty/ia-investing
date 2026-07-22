from ia_investing.platform.database import normalize_async_database_url


def test_normalizes_plain_postgres_url():
    assert normalize_async_database_url("postgresql://u:p@db/x") == "postgresql+psycopg://u:p@db/x"


def test_normalizes_legacy_asyncpg_url():
    assert normalize_async_database_url("postgresql+asyncpg://u:p@db/x") == "postgresql+psycopg://u:p@db/x"


def test_preserves_psycopg_url():
    assert normalize_async_database_url("postgresql+psycopg://u:p@db/x") == "postgresql+psycopg://u:p@db/x"
