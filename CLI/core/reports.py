"""Monthly budget-vs-actual and summary metrics.

Pure functions over the finance blob (no I/O), so the CLI, Streamlit UI and
tests share one implementation. ``ExpenseTracker.monthly_report`` is the thin
wrapper that loads the data.

Amounts are summed as stored. Mixed-currency data is reported in
``currencies`` rather than silently converted (conversion needs a network
call; callers that want one can run ``convert_prices_to_currency`` first).
"""
from __future__ import annotations

import csv
import io
import json
from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from .bank_import import clean_merchant, UNCATEGORIZED
except ImportError:  # flat import
    from bank_import import clean_merchant, UNCATEGORIZED

WARN_AT = 0.8   # budget is "warning" from 80% used


def _f(v: Any) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _month(d: Any) -> str:
    return str(d or "")[:7]


def previous_month(month: str) -> str:
    y, m = int(month[:4]), int(month[5:7])
    return f"{y - 1}-12" if m == 1 else f"{y}-{m - 1:02d}"


def _days_in(month: str) -> int:
    y, m = int(month[:4]), int(month[5:7])
    nxt = date(y + (m == 12), 1 if m == 12 else m + 1, 1)
    return (nxt - date(y, m, 1)).days


def _category(e: Dict[str, Any]) -> str:
    return (str(e.get("tags") or "").strip()) or UNCATEGORIZED


def spend_by_category(expenses: List[Dict[str, Any]], month: str) -> Dict[str, float]:
    """Totals per category. "groceries" and "Groceries" are one category,
    shown with whichever spelling appeared first."""
    totals: Dict[str, float] = defaultdict(float)
    label: Dict[str, str] = {}
    for e in expenses:
        if _month(e.get("date")) == month:
            cat = _category(e)
            label.setdefault(cat.lower(), cat)
            totals[cat.lower()] += _f(e.get("price"))
    return dict(sorted(((label[k], round(v, 2)) for k, v in totals.items()),
                       key=lambda kv: -kv[1]))


def budget_vs_actual(budgets: List[Dict[str, Any]], expenses: List[Dict[str, Any]],
                     month: str) -> List[Dict[str, Any]]:
    """One row per budget category. Matching is case-insensitive."""
    spent = {k.lower(): v for k, v in spend_by_category(expenses, month).items()}
    rows = []
    for b in budgets or []:
        limit = _f(b.get("amount"))
        used = round(spent.get(str(b.get("category", "")).lower(), 0.0), 2)
        pct = (used / limit) if limit > 0 else (1.0 if used else 0.0)
        status = "over" if used > limit else ("warning" if pct >= WARN_AT else "ok")
        rows.append({
            "category": b.get("category", ""),
            "limit": round(limit, 2),
            "spent": used,
            "remaining": round(limit - used, 2),
            "pct_used": round(pct * 100, 1),
            "status": status,
            "currency": (b.get("currency") or "").lower(),
        })
    order = {"over": 0, "warning": 1, "ok": 2}
    return sorted(rows, key=lambda r: (order[r["status"]], -r["pct_used"]))


def monthly_report(data: Dict[str, Any], month: str,
                   today: Optional[date] = None) -> Dict[str, Any]:
    """Everything a monthly summary needs, as plain JSON-able values."""
    expenses = data.get("expenses") or []
    income = data.get("income") or []
    budgets = data.get("budget") or []

    m_exp = [e for e in expenses if _month(e.get("date")) == month]
    m_inc = [i for i in income if _month(i.get("date")) == month]
    spent = round(sum(_f(e.get("price")) for e in m_exp), 2)
    earned = round(sum(_f(i.get("amount")) for i in m_inc), 2)
    net = round(earned - spent, 2)

    prev = previous_month(month)
    prev_spent = round(sum(_f(e.get("price")) for e in expenses
                           if _month(e.get("date")) == prev), 2)
    change = round((spent - prev_spent) / prev_spent * 100, 1) if prev_spent else None

    # Average per elapsed day: a half-finished month shouldn't look frugal.
    today = today or date.today()
    days = _days_in(month)
    if today.strftime("%Y-%m") == month:
        days = max(today.day, 1)

    merchants: Dict[str, float] = defaultdict(float)
    for e in m_exp:
        merchants[clean_merchant(e.get("purchased", "")) or "Unknown"] += _f(e.get("price"))
    top_merchants = [{"merchant": k, "spent": round(v, 2)}
                     for k, v in sorted(merchants.items(), key=lambda kv: -kv[1])[:5]]

    largest = max(m_exp, key=lambda e: _f(e.get("price")), default=None)
    budgets_rows = budget_vs_actual(budgets, expenses, month)
    budgeted = {r["category"].lower() for r in budgets_rows}
    by_cat = spend_by_category(expenses, month)

    return {
        "month": month,
        "total_income": earned,
        "total_spent": spent,
        "net": net,
        "savings_rate": round(net / earned * 100, 1) if earned > 0 else None,
        "transactions": len(m_exp) + len(m_inc),
        "avg_daily_spend": round(spent / days, 2),
        "previous_month_spent": prev_spent,
        "spend_change_pct": change,
        "by_category": by_cat,
        "uncategorized_spent": by_cat.get(UNCATEGORIZED, 0.0),
        "unbudgeted_spent": round(sum(v for k, v in by_cat.items()
                                      if k.lower() not in budgeted), 2),
        "budgets": budgets_rows,
        "over_budget": [r["category"] for r in budgets_rows if r["status"] == "over"],
        "top_merchants": top_merchants,
        "largest_expense": None if largest is None else {
            "item": largest.get("purchased", ""), "amount": _f(largest.get("price")),
            "date": largest.get("date", ""), "category": _category(largest)},
        "currencies": sorted({(x.get("currency") or "").lower()
                              for x in m_exp + m_inc} - {""}),
    }


def months_with_data(data: Dict[str, Any]) -> List[str]:
    ms = {_month(x.get("date")) for k in ("expenses", "income")
          for x in (data.get(k) or []) if x.get("date")}
    return sorted(m for m in ms if len(m) == 7)


def trend(data: Dict[str, Any], months: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """One flat row per month — the shape a spreadsheet or chart wants."""
    rows = []
    for m in months or months_with_data(data):
        r = monthly_report(data, m)
        rows.append({k: r[k] for k in ("month", "total_income", "total_spent", "net",
                                       "savings_rate", "transactions", "avg_daily_spend")})
    return rows


def export_report(report: Dict[str, Any], fmt: str = "csv") -> bytes:
    """Serialise a monthly report. CSV is sectioned so it opens cleanly in Excel."""
    if fmt == "json":
        return json.dumps(report, indent=2).encode("utf-8")
    if fmt != "csv":
        raise ValueError("fmt must be 'csv' or 'json'")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Summary", report["month"]])
    for key, label in (("total_income", "Income"), ("total_spent", "Spent"),
                       ("net", "Net"), ("savings_rate", "Savings rate %"),
                       ("avg_daily_spend", "Avg daily spend"),
                       ("spend_change_pct", "Spend vs last month %"),
                       ("transactions", "Transactions")):
        v = report.get(key)
        w.writerow([label, "" if v is None else v])
    w.writerow([])
    w.writerow(["Budget", "Limit", "Spent", "Remaining", "% used", "Status"])
    for b in report["budgets"]:
        w.writerow([b["category"], f'{b["limit"]:.2f}', f'{b["spent"]:.2f}',
                    f'{b["remaining"]:.2f}', b["pct_used"], b["status"]])
    w.writerow([])
    w.writerow(["Category", "Spent"])
    for cat, v in report["by_category"].items():
        w.writerow([cat, f"{v:.2f}"])
    w.writerow([])
    w.writerow(["Top merchant", "Spent"])
    for t in report["top_merchants"]:
        w.writerow([t["merchant"], f'{t["spent"]:.2f}'])
    return buf.getvalue().encode("utf-8-sig")
