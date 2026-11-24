"""reports.cash_flow_window — money in vs out over the last N days."""
from datetime import date

import pytest

from CLI.core import reports

EXP = [
    {"price": 10, "date": "2026-02-10", "currency": "usd"},
    {"price": "5.5", "date": "2026-02-10", "currency": "usd"},
    {"price": 20, "date": "2026-02-14", "currency": "usd"},
    {"price": 99, "date": "2026-02-15", "currency": "usd"},   # after the window
    {"price": 99, "date": "2026-02-07", "currency": "usd"},   # before the window
    {"price": 99, "date": "not a date"},
    {"price": None, "date": "2026-02-12"},
]
INC = [
    {"amount": 100, "date": "2026-02-08", "currency": "eur"},
    {"amount": 50, "date": "2026-02-14T09:30:00"},            # datetime string
]
END = date(2026, 2, 14)


def test_daily_window_has_every_day_and_correct_totals():
    r = reports.cash_flow_window(EXP, INC, 7, end=END)
    assert r["bucket"] == "day"
    assert r["start"] == "2026-02-08" and r["end"] == "2026-02-14"
    assert [row["period"] for row in r["rows"]] == [
        f"2026-02-{d:02d}" for d in range(8, 15)]
    by = {row["period"]: row for row in r["rows"]}
    assert by["2026-02-08"]["money_in"] == 100
    assert by["2026-02-10"]["money_out"] == 15.5
    assert by["2026-02-14"] == {"period": "2026-02-14", "label": "Feb 14",
                                "money_in": 50, "money_out": 20, "net": 30}
    assert by["2026-02-09"]["money_in"] == by["2026-02-09"]["money_out"] == 0
    assert r["total_in"] == 150
    assert r["total_out"] == 35.5
    assert r["net"] == 114.5
    assert r["transactions"] == 6          # 4 expenses (incl. None price) + 2 income
    assert r["currencies"] == ["eur", "usd"]


def test_one_day_window():
    r = reports.cash_flow_window(EXP, INC, 1, end=END)
    assert len(r["rows"]) == 1 and r["total_out"] == 20 and r["total_in"] == 50


def test_zero_or_negative_days_clamped_to_one():
    assert reports.cash_flow_window([], [], 0, end=END)["days"] == 1


def test_weekly_buckets_cover_window_from_first_day():
    r = reports.cash_flow_window(EXP, INC, 60, end=END)
    assert r["bucket"] == "week"
    assert r["rows"][0]["period"] == r["start"]
    assert len(r["rows"]) == 9            # ceil(60 / 7)
    assert sum(row["money_out"] for row in r["rows"]) == r["total_out"] == 35.5 + 99   # Feb 7 in, Feb 15 still after `end`
    assert r["rows"][0]["label"].startswith("Wk of ")


def test_monthly_buckets_are_calendar_months():
    r = reports.cash_flow_window(EXP, INC, 365, end=END)
    assert r["bucket"] == "month"
    assert r["rows"][0]["period"] == "2025-02" and r["rows"][-1]["period"] == "2026-02"
    assert r["rows"][-1]["label"] == "Feb 2026"


def test_explicit_bucket_and_bad_bucket():
    assert reports.cash_flow_window(EXP, INC, 7, end=END, bucket="month")["rows"][0]["period"] == "2026-02"
    with pytest.raises(ValueError):
        reports.cash_flow_window(EXP, INC, 7, end=END, bucket="year")


def test_empty_data():
    r = reports.cash_flow_window(None, None, 30, end=END)
    assert r["total_in"] == r["total_out"] == r["net"] == 0
    assert len(r["rows"]) == 30
