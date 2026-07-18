from __future__ import annotations

from data_quality._accounting import (
    run_all_checks,
    validate_balance_sheet,
    validate_dre,
)


class TestBalanceSheetValidation:
    def test_balanced_sheet_passes(self):
        line_items = {
            "entity_id": "BS001",
            "total_assets": 1000,
            "total_liabilities": 400,
            "equity": 600,
            "current_assets": 300,
            "non_current_assets": 700,
            "cash": 100,
            "accounts_receivable": 50,
            "inventory": 150,
        }
        results = validate_balance_sheet(line_items)
        balance_check = next(r for r in results if r.check_name == "balance_sheet_balances")
        assert balance_check.passed

    def test_unbalanced_sheet_fails(self):
        line_items = {
            "entity_id": "BS002",
            "total_assets": 1000,
            "total_liabilities": 400,
            "equity": 300,
        }
        results = validate_balance_sheet(line_items)
        balance_check = next(r for r in results if r.check_name == "balance_sheet_balances")
        assert not balance_check.passed
        assert balance_check.severity == "error"

    def test_missing_required_accounts_still_validates(self):
        line_items = {"entity_id": "BS003"}
        results = validate_balance_sheet(line_items)
        assert len(results) > 0
        balance_check = next(r for r in results if r.check_name == "balance_sheet_balances")
        assert balance_check.passed

    def test_negative_current_assets_flagged(self):
        line_items = {
            "entity_id": "BS004",
            "total_assets": 100,
            "total_liabilities": 50,
            "equity": 50,
            "current_assets": -10,
        }
        results = validate_balance_sheet(line_items)
        check = next(r for r in results if r.check_name == "current_assets_non_negative")
        assert not check.passed
        assert check.severity == "error"


class TestDREValidation:
    def test_valid_dre_passes(self):
        line_items = {
            "entity_id": "DRE001",
            "receita_liquida": 1000,
            "custo_receita": 600,
            "despesas_operacionais": 200,
            "ebitda": 200,
            "ebit": 150,
            "despesas_financeiras": 30,
            "impostos": 40,
            "lucro_liquido": 80,
        }
        results = validate_dre(line_items)
        rev_check = next(r for r in results if r.check_name == "receita_liquida_non_negative")
        assert rev_check.passed

    def test_negative_revenue_triggers_error(self):
        line_items = {
            "entity_id": "DRE002",
            "receita_liquida": -100,
            "custo_receita": 0,
            "despesas_operacionais": 0,
            "ebitda": 0,
            "ebit": 0,
            "despesas_financeiras": 0,
            "impostos": 0,
            "lucro_liquido": 0,
        }
        results = validate_dre(line_items)
        check = next(r for r in results if r.check_name == "no_negative_revenue")
        assert not check.passed
        assert check.severity == "error"

    def test_negative_revenue_allowed_when_flagged(self):
        line_items = {
            "entity_id": "DRE003",
            "receita_liquida": -50,
            "custo_receita": 0,
            "despesas_operacionais": 0,
            "ebitda": 0,
            "ebit": 0,
            "despesas_financeiras": 0,
            "impostos": 0,
            "lucro_liquido": 0,
            "allow_negative_revenue": True,
        }
        results = validate_dre(line_items)
        check = next((r for r in results if r.check_name == "no_negative_revenue"), None)
        assert check is None


class TestRunAllChecks:
    def test_unknown_statement_type(self):
        results = run_all_checks("UNKNOWN", {"entity_id": "X"})
        assert len(results) == 1
        assert results[0].check_name == "unknown_statement_type"
        assert not results[0].passed

    def test_dispatches_balance_sheet(self):
        data = {"entity_id": "X", "total_assets": 100, "total_liabilities": 50, "equity": 50}
        results = run_all_checks("BALANCE_SHEET", data)
        assert any(r.entity_type == "balance_sheet" for r in results)

    def test_dispatches_dre(self):
        data = {
            "entity_id": "X", "receita_liquida": 100, "custo_receita": 50,
            "despesas_operacionais": 20, "ebitda": 30, "ebit": 25,
            "despesas_financeiras": 5, "impostos": 5, "lucro_liquido": 15,
        }
        results = run_all_checks("DRE", data)
        assert any(r.entity_type == "dre" for r in results)
