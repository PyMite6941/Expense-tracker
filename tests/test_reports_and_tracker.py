"""Monthly reports, plus the ExpenseTracker import round trip on a temp file."""
import csv
import io
import json
from datetime import date

import pytest

from CLI.core import reports
from CLI.core.core_stuff import ExpenseTracker

DATA = {
    "expenses": [
        {"id": 1, "price": 300, "purchased": "Whole Foods", "tags": "Groceries", "date": "2026-02-03", "currency": "usd"},
        {"id": 2, "price": 150, "purchased": "Trader Joe's", "tags": "groceries", "date": "2026-02-10", "currency": "usd"},
        {"id": 3, "price": 90, "purchased": "Chipotle", "tags": "Dining", "date": "2026-02-11", "currency": "usd"},
        {"id": 4, "price": 60, "purchased": "Mystery", "tags": "", "date": "2026-02-12", "currency": "usd"},
        {"id": 5, "price": 200, "purchased": "Whole Foods", "tags": "Groceries", "date": "2026-01-05", "currency": "usd"},
        {"id": 6, "price": "12.5", "purchased": "Bad type", "tags": "Dining", "date": "2026-02-20", "currency": "usd"},
    ],
    "income": [{"id": 1, "amount": 2000, "source": "Salary", "date": "2026-02-01", "currency": "usd"}],
    "budget": [
        {"id": 1, "category": "Groceries", "amount": 400, "currency": "usd"},
        {"id": 2, "category": "Dining", "amount": 120, "currency": "usd"},
        {"id": 3, "category": "Fun", "amount": 50, "currency": "usd"},
    ],
}


class TestReports:
    def setup_method(self):
        self.r = reports.monthly_report(DATA, "2026-02", today=date(2026, 3, 15))

    def test_totals(self):
        assert self.r["total_spent"] == 612.5
        assert self.r["total_income"] == 2000
        assert self.r["net"] == 1387.5
        assert self.r["savings_rate"] == 69.4
        assert self.r["avg_daily_spend"] == round(612.5 / 28, 2)

    def test_month_over_month(self):
        assert self.r["previous_month_spent"] == 200
        assert self.r["spend_change_pct"] == 206.2

    def test_budget_vs_actual_case_insensitive_and_sorted(self):
        rows = {b["category"]: b for b in self.r["budgets"]}
        assert rows["Groceries"]["spent"] == 450 and rows["Groceries"]["status"] == "over"
        assert rows["Dining"]["status"] == "warning"      # 102.5 / 120 = 85%
        assert rows["Fun"]["status"] == "ok" and rows["Fun"]["spent"] == 0
        assert self.r["budgets"][0]["category"] == "Groceries"
        assert self.r["over_budget"] == ["Groceries"]

    def test_uncategorized_and_unbudgeted(self):
        assert self.r["uncategorized_spent"] == 60
        assert self.r["unbudgeted_spent"] == 60

    def test_current_month_average_uses_elapsed_days(self):
        r = reports.monthly_report(DATA, "2026-02", today=date(2026, 2, 10))
        assert r["avg_daily_spend"] == round(612.5 / 10, 2)

    def test_empty_month(self):
        r = reports.monthly_report(DATA, "2025-06")
        assert r["total_spent"] == 0 and r["savings_rate"] is None and r["spend_change_pct"] is None

    def test_previous_month_wraps_year(self):
        assert reports.previous_month("2026-01") == "2025-12"

    def test_trend(self):
        assert [t["month"] for t in reports.trend(DATA)] == ["2026-01", "2026-02"]

    def test_export_csv_and_json(self):
        rows = list(csv.reader(io.StringIO(reports.export_report(self.r, "csv").decode("utf-8-sig"))))
        assert rows[0] == ["Summary", "2026-02"]
        assert ["Groceries", "400.00", "450.00", "-50.00", "112.5", "over"] in rows
        assert json.loads(reports.export_report(self.r, "json"))["net"] == 1387.5
        with pytest.raises(ValueError):
            reports.export_report(self.r, "xml")


STATEMENT = b"""Date,Description,Amount
2026-03-01,NETFLIX.COM,-15.49
2026-03-02,SQ *BLUE BOTTLE COFFEE #9,-6.00
2026-03-02,SQ *BLUE BOTTLE COFFEE #9,-6.00
2026-03-05,ACME PAYROLL,2500.00
2026-03-07,WEIRD MERCHANT 99,-20.00
"""


@pytest.fixture
def tracker(tmp_path):
    return ExpenseTracker(filename=str(tmp_path / "data.json"))


class TestTrackerImport:
    def test_preview_then_commit(self, tracker):
        p = tracker.preview_bank_statement(STATEMENT)
        assert p["success"] and len(p["transactions"]) == 5
        assert p["meta"]["duplicates"] == 0 and p["meta"]["uncategorized"] >= 1
        r = tracker.commit_bank_import(p["transactions"], "usd", source_name="march.csv")
        assert (r["added_expenses"], r["added_income"]) == (4, 1)
        data = tracker.open_file()["data"]
        assert {e["purchased"] for e in data["expenses"]} >= {"Netflix.Com", "Blue Bottle Coffee"}
        assert data["income"][0]["source"] == "Acme Payroll"
        ids = [e["id"] for e in data["expenses"]]
        assert len(set(ids)) == len(ids)

    def test_reimport_is_fully_deduplicated(self, tracker):
        tracker.import_bank_statement(STATEMENT)
        again = tracker.import_bank_statement(STATEMENT)
        assert again["added_expenses"] == 0 and again["added_income"] == 0
        assert again["skipped"] == 5

    def test_dedupe_survives_user_renaming(self, tracker):
        tracker.import_bank_statement(STATEMENT)
        data = tracker.open_file()["data"]
        for e in data["expenses"]:
            e["purchased"] = "renamed by user"
        tracker.write_file(data)
        assert tracker.import_bank_statement(STATEMENT)["added_expenses"] == 0

    def test_learns_from_user_recategorization(self, tracker):
        tracker.import_bank_statement(STATEMENT)
        data = tracker.open_file()["data"]
        for e in data["expenses"]:
            if e["purchased"].startswith("Weird"):
                e["tags"] = "Hobbies"
        tracker.write_file(data)
        p = tracker.preview_bank_statement(b"Date,Description,Amount\n2026-04-07,WEIRD MERCHANT 12,-20\n")
        t = p["transactions"][0]
        assert (t["category"], t["category_source"]) == ("Hobbies", "history")

    def test_excluded_rows_are_skipped(self, tracker):
        p = tracker.preview_bank_statement(STATEMENT)
        for t in p["transactions"]:
            t["include"] = t["kind"] == "income"
        r = tracker.commit_bank_import(p["transactions"])
        assert (r["added_expenses"], r["added_income"]) == (0, 1)

    def test_bad_file_reports_error(self, tracker):
        r = tracker.preview_bank_statement(b"not,a,statement\n1,2,3\n")
        assert not r["success"] and "header" in r["message"]

    def test_monthly_report_export(self, tracker, tmp_path):
        tracker.import_bank_statement(STATEMENT)
        out = tmp_path / "r.csv"
        r = tracker.export_monthly_report("2026-03", "csv", str(out))
        assert r["success"] and out.exists()
        assert r["data"]["total_spent"] == 47.49 and r["data"]["total_income"] == 2500


class TestLegacyCsvImport:
    """import_from_csv used to store any CSV verbatim (bank columns, NaN)."""

    CHASE = (b"Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #\n"
             b"DEBIT,02/03/2026,STARBUCKS 123,-5.75,DEBIT_CARD,1994.25,,\n"
             b"CREDIT,02/05/2026,ACME PAYROLL,2500.00,ACH_CREDIT,4312.15,,\n")

    def test_bank_statement_is_routed_to_bank_import(self, tracker, tmp_path):
        p = tmp_path / "chase.csv"
        p.write_bytes(self.CHASE)
        r = tracker.import_from_csv("expenses", str(p))
        assert r["success"] and "bank statement" in r["message"]
        data = tracker.open_file()["data"]
        assert data["expenses"][0]["price"] == 5.75 and data["expenses"][0]["date"] == "2026-02-03"
        assert data["income"][0]["amount"] == 2500

    def test_own_export_round_trips(self, tracker, tmp_path):
        tracker.add_expenses(1234.5, "Laptop", "Tech", "gbp", "2026-02-01", "")
        out = tmp_path / "e.csv"
        tracker.export_to_csv("expenses", str(out))
        other = ExpenseTracker(filename=str(tmp_path / "other.json"))
        assert other.import_from_csv("expenses", str(out))["success"]
        e = other.open_file()["data"]["expenses"][0]
        assert (e["price"], e["purchased"], e["currency"], e["date"]) == (1234.5, "Laptop", "gbp", "2026-02-01")
        assert e["notes"] is None  # blank cell -> None, never NaN
        json.dumps(other.open_file()["data"], allow_nan=False)

    def test_unknown_csv_is_rejected_not_stored(self, tracker, tmp_path):
        p = tmp_path / "x.csv"
        p.write_bytes(b"foo,bar\n1,2\n")
        r = tracker.import_from_csv("expenses", str(p))
        assert not r["success"] and "missing column" in r["message"]
        assert tracker.open_file()["data"]["expenses"] == []
