\set ON_ERROR_STOP on
BEGIN;

INSERT INTO sectors (id, name_pt) VALUES ('31000000-0000-0000-0000-000000000001', 'Fixture');
INSERT INTO industries (id, name_pt, sector_id)
VALUES ('31000000-0000-0000-0000-000000000002', 'Fixture', '31000000-0000-0000-0000-000000000001');
INSERT INTO issuers (id, name_pt, cnpj, industry_id)
VALUES (
  '31000000-0000-0000-0000-000000000003',
  'Emissor Fixture',
  '00000000000001',
  '31000000-0000-0000-0000-000000000002'
);
INSERT INTO instruments (id, issuer_id, instrument_type, currency_code, is_active, created_at)
VALUES (
  '31000000-0000-0000-0000-000000000004',
  '31000000-0000-0000-0000-000000000003',
  'common_share',
  'BRL',
  true,
  now()
);
INSERT INTO listings (id, instrument_id, exchange_code, ticker, valid_from, valid_to, created_at)
VALUES (
  '31000000-0000-0000-0000-000000000005',
  '31000000-0000-0000-0000-000000000004',
  'B3',
  'FIXT3',
  DATE '2020-01-01',
  DATE '2024-01-01',
  now()
);
INSERT INTO listings (id, instrument_id, exchange_code, ticker, valid_from, valid_to, created_at)
VALUES (
  '31000000-0000-0000-0000-000000000006',
  '31000000-0000-0000-0000-000000000004',
  'B3',
  'FIXT3',
  DATE '2024-01-01',
  NULL,
  now()
);

DO $verify$
BEGIN
  BEGIN
    INSERT INTO listings (id, instrument_id, exchange_code, ticker, valid_from, valid_to, created_at)
    VALUES (
      '31000000-0000-0000-0000-000000000007',
      '31000000-0000-0000-0000-000000000004',
      'B3',
      'FIXT3',
      DATE '2023-01-01',
      DATE '2025-01-01',
      now()
    );
    RAISE EXCEPTION 'overlapping ticker window was accepted';
  EXCEPTION WHEN exclusion_violation THEN
    RAISE NOTICE 'overlapping ticker window rejected as expected';
  END;
END
$verify$;

SELECT 'instrument-master-ok historical_windows=2 overlap_rejected=true' AS verification;
ROLLBACK;
