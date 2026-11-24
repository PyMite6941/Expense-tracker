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
from datetime import date, timedelta
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


def _as_date(v: Any) -> Optional[date]:
    try:
        return date.fromisoformat(str(v or "")[:10])
    except ValueError:
        return None


def _bucket_for(days: int) -> str:
    """Daily bars up to a month, weekly up to ~6 months, monthly beyond.
    Keeps the bar count readable (≤31 / ≤26 / one per month)."""
    if days <= 31:
        return "day"
    if days <= 182:
        return "week"
    return "month"


def cash_flow_window(expenses: List[Dict[str, Any]], income: List[Dict[str, Any]],
                     days: int, end: Optional[date] = None,
                     bucket: str = "auto") -> Dict[str, Any]:
    """Money in vs money out over the ``days`` days ending on ``end`` (inclusive).

    Every bucket in the window is returned, including empty ones, so a chart
    shows quiet days as gaps rather than silently skipping them. Weeks are
    7-day blocks counted from the window's first day (the last may be shorter);
    months are calendar months clipped to the window.
    """
    days = max(1, int(days))
    end = end or date.today()
    start = end - timedelta(days=days - 1)
    if bucket == "auto":
        bucket = _bucket_for(days)
    if bucket not in ("day", "week", "month"):
        raise ValueError("bucket must be 'auto', 'day', 'week' or 'month'")

    def key(d: date) -> str:
        if bucket == "day":
            return d.isoformat()
        if bucket == "week":
            return (start + timedelta(days=((d - start).days // 7) * 7)).isoformat()
        return d.strftime("%Y-%m")

    # Pre-seed every bucket in order.
    rows: Dict[str, Dict[str, Any]] = {}
    d = start
    while d <= end:
        k = key(d)
        if k not in rows:
            label = (d.strftime("%b %d") if bucket == "day"
                     else f"Wk of {d.strftime('%b %d')}" if bucket == "week"
                     else d.strftime("%b %Y"))
            rows[k] = {"period": k, "label": label, "money_in": 0.0, "money_out": 0.0}
        d += timedelta(days=1)

    for items, field, amount_key in ((income, "money_in", "amount"),
                                     (expenses, "money_out", "price")):
        for x in items or []:
            xd = _as_date(x.get("date"))
            if xd is not None and start <= xd <= end:
                rows[key(xd)][field] += _f(x.get(amount_key))

    out = []
    for r in rows.values():
        r["money_in"] = round(r["money_in"], 2)
        r["money_out"] = round(r["money_out"], 2)
        r["net"] = round(r["money_in"] - r["money_out"], 2)
        out.append(r)
    total_in = round(sum(r["money_in"] for r in out), 2)
    total_out = round(sum(r["money_out"] for r in out), 2)
    in_window = [x for x in list(expenses or []) + list(income or [])
                 if (xd := _as_date(x.get("date"))) is not None and start <= xd <= end]
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "bucket": bucket,
        "rows": out,
        "total_in": total_in,
        "total_out": total_out,
        "net": round(total_in - total_out, 2),
        "transactions": len(in_window),
        "currencies": sorted({(x.get("currency") or "").lower() for x in in_window} - {""}),
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
