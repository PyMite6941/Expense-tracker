import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Callable, Optional


def forecast_spending(expenses: list, base_currency: str = 'USD') -> dict:
    """Linear-trend forecast of monthly spend per category."""
    monthly: dict = defaultdict(lambda: defaultdict(float))
    for e in expenses:
        if e.get('currency', '').upper() != base_currency.upper():
            continue
        try:
            month = e['date'][:7]
            monthly[month][e.get('tags', 'Other')] += e['price']
        except (KeyError, TypeError):
            continue

    if not monthly:
        return {'success': False, 'message': 'Not enough data to forecast'}

    months_sorted = sorted(monthly.keys())
    categories: set = set()
    for m in monthly.values():
        categories.update(m.keys())

    forecasts = {}
    for cat in categories:
        values = [monthly[m].get(cat, 0.0) for m in months_sorted]
        n = len(values)
        if n < 2:
            forecasts[cat] = {
                'current_avg': round(values[-1] if values else 0.0, 2),
                'next_month_forecast': round(values[-1] if values else 0.0, 2),
                'trend': 'stable',
            }
            continue
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        num = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        den = sum((i - x_mean) ** 2 for i in range(n))
        slope = num / den if den else 0.0
        intercept = y_mean - slope * x_mean
        next_val = max(0.0, intercept + slope * n)
        trend = 'increasing' if slope > 0.5 else 'decreasing' if slope < -0.5 else 'stable'
        forecasts[cat] = {
            'current_avg': round(y_mean, 2),
            'next_month_forecast': round(next_val, 2),
            'trend': trend,
        }

    return {
        'success': True,
        'forecasts': forecasts,
        'based_on_months': len(months_sorted),
        'base_currency': base_currency,
    }


def detect_anomalies(expenses: list, z_threshold: float = 2.5) -> dict:
    """Flag expenses whose price deviates more than z_threshold std-devs from their category mean."""
    by_category: dict = defaultdict(list)
    for e in expenses:
        by_category[e.get('tags', 'Other')].append(e)

    anomalies = []
    for cat, items in by_category.items():
        if len(items) < 3:
            continue
        prices = [i['price'] for i in items]
        mean = sum(prices) / len(prices)
        try:
            std = statistics.stdev(prices)
        except statistics.StatisticsError:
            continue
        if std == 0:
            continue
        for item in items:
            z = abs(item['price'] - mean) / std
            if z >= z_threshold:
                anomalies.append({
                    **item,
                    'z_score': round(z, 2),
                    'category_mean': round(mean, 2),
                    'deviation': round(item['price'] - mean, 2),
                })

    anomalies.sort(key=lambda x: x['z_score'], reverse=True)
    return {'success': True, 'anomalies': anomalies, 'count': len(anomalies)}


def tax_summary(
    expenses: list,
    income: list,
    year: int,
    deductible_categories: Optional[list] = None,
) -> dict:
    """Year-level summary grouping deductible expense categories."""
    if deductible_categories is None:
        deductible_categories = ['Bills', 'Utilities', 'Other']

    year_str = str(year)
    year_expenses = [e for e in expenses if e.get('date', '').startswith(year_str)]
    year_income = [i for i in income if i.get('date', '').startswith(year_str)]

    total_income = sum(i['amount'] for i in year_income)
    total_expenses = sum(e['price'] for e in year_expenses)

    by_category: dict = defaultdict(float)
    for e in year_expenses:
        by_category[e.get('tags', 'Other')] += e['price']

    deductible_total = sum(by_category[c] for c in deductible_categories if c in by_category)

    return {
        'success': True,
        'year': year,
        'total_income': round(total_income, 2),
        'total_expenses': round(total_expenses, 2),
        'net': round(total_income - total_expenses, 2),
        'by_category': {k: round(v, 2) for k, v in sorted(by_category.items())},
        'deductible_categories': deductible_categories,
        'estimated_deductible_total': round(deductible_total, 2),
    }


def net_worth_snapshot(
    data: dict,
    convert_fn: Optional[Callable] = None,
    base_currency: str = 'USD',
) -> dict:
    """Aggregate net-worth across all data sources, optionally converting currencies."""

    def to_base(amount: float, currency: str) -> float:
        if not currency or currency.upper() == base_currency.upper():
            return amount
        if convert_fn:
            result = convert_fn(amount, currency, base_currency)
            if result.get('success'):
                return result['rate']
        return amount

    expenses = data.get('expenses', [])
    income = data.get('income', [])
    subscriptions = data.get('subscriptions', [])
    goals = data.get('goals', [])
    assets = data.get('assets', [])
    liabilities = data.get('liabilities', [])

    total_income = sum(to_base(i['amount'], i.get('currency', base_currency)) for i in income)
    total_expenses = sum(to_base(e['price'], e.get('currency', base_currency)) for e in expenses)
    monthly_sub_burden = sum(
        to_base(float(s['price']), s.get('currency', base_currency)) for s in subscriptions
    )

    goal_targets = sum(to_base(g.get('amount', 0), g.get('currency', base_currency)) for g in goals)

    goal_saved = 0.0
    today = date.today()
    for g in goals:
        try:
            start = datetime.strptime(g['startDate'], '%Y-%m-%d').date()
            months = max(0, (today.year - start.year) * 12 + (today.month - start.month))
            goal_saved += to_base(g.get('monthContribution', 0) * months, g.get('currency', base_currency))
        except (ValueError, TypeError, KeyError):
            pass

    # Assets by type
    asset_by_type: dict = defaultdict(float)
    for a in assets:
        asset_by_type[a.get('type', 'other')] += to_base(float(a.get('value', 0)), a.get('currency', base_currency))
    total_assets = sum(asset_by_type.values())

    # Liabilities by type
    liability_by_type: dict = defaultdict(float)
    for l in liabilities:
        liability_by_type[l.get('type', 'other')] += to_base(float(l.get('balance', 0)), l.get('currency', base_currency))
    total_liabilities = sum(liability_by_type.values())

    net_cash_flow = total_income - total_expenses

    # True net worth = assets - liabilities; fall back to cash-flow estimate if neither is recorded
    if assets or liabilities:
        net_worth = total_assets - total_liabilities
    else:
        net_worth = net_cash_flow - monthly_sub_burden * 12

    return {
        'success': True,
        'base_currency': base_currency,
        'total_income': round(total_income, 2),
        'total_expenses': round(total_expenses, 2),
        'net_cash_flow': round(net_cash_flow, 2),
        'monthly_subscription_burden': round(monthly_sub_burden, 2),
        'goal_targets_total': round(goal_targets, 2),
        'goal_contributions_to_date': round(goal_saved, 2),
        'total_assets': round(total_assets, 2),
        'total_liabilities': round(total_liabilities, 2),
        'assets_by_type': {k: round(v, 2) for k, v in asset_by_type.items()},
        'liabilities_by_type': {k: round(v, 2) for k, v in liability_by_type.items()},
        'estimated_net_worth': round(net_worth, 2),
    }


def financial_health_score(data: dict) -> dict:
    """Composite 0-100 score across savings rate, budget adherence, subscription burden, goal consistency."""
    expenses = data.get('expenses', [])
    income = data.get('income', [])
    budget = data.get('budget', [])
    subscriptions = data.get('subscriptions', [])
    goals = data.get('goals', [])

    total_income = sum(i.get('amount', 0) for i in income)
    total_expenses = sum(e.get('price', 0) for e in expenses)
    monthly_sub = sum(float(s.get('price', 0)) for s in subscriptions)

    # Savings rate (35 pts)
    if total_income > 0:
        savings_rate = max(0.0, (total_income - total_expenses) / total_income)
        savings_score = min(35, savings_rate * 140)
    else:
        savings_score = 0.0

    # Budget adherence (30 pts)
    if budget:
        month = date.today().strftime('%Y-%m')
        month_expenses: dict = defaultdict(float)
        for e in expenses:
            if e.get('date', '')[:7] == month:
                month_expenses[e.get('tags', 'Other')] += e.get('price', 0)
        adherences = []
        for b in budget:
            limit = float(b.get('amount', 0))
            spent = month_expenses.get(b.get('category', ''), 0.0)
            if limit > 0:
                adherences.append(min(1.0, 1.0 - max(0.0, (spent - limit) / limit)))
        budget_score = (sum(adherences) / len(adherences)) * 30 if adherences else 15.0
    else:
        budget_score = 15.0

    # Subscription burden (20 pts) — penalise if monthly subs > 15% of income
    if total_income > 0:
        sub_ratio = monthly_sub / (total_income / 12) if total_income > 0 else 0
        sub_score = max(0.0, 20 - sub_ratio * 100)
    else:
        sub_score = 10.0

    # Goal consistency (15 pts)
    if goals:
        today = date.today()
        on_track = 0
        for g in goals:
            try:
                start = datetime.strptime(g['startDate'], '%Y-%m-%d').date()
                months = max(1, (today.year - start.year) * 12 + (today.month - start.month))
                expected = g.get('monthContribution', 0) * months
                target = g.get('amount', 0)
                if target > 0 and expected >= target * 0.9:
                    on_track += 1
                elif g.get('monthContribution', 0) > 0:
                    on_track += 0.5
            except (ValueError, TypeError, KeyError):
                pass
        goal_score = min(15, (on_track / len(goals)) * 15)
    else:
        goal_score = 7.5

    total = savings_score + budget_score + sub_score + goal_score
    grade = 'A' if total >= 85 else 'B' if total >= 70 else 'C' if total >= 55 else 'D' if total >= 40 else 'F'

    return {
        'success': True,
        'score': round(total, 1),
        'grade': grade,
        'breakdown': {
            'savings_rate': round(savings_score, 1),
            'budget_adherence': round(budget_score, 1),
            'subscription_burden': round(sub_score, 1),
            'goal_consistency': round(goal_score, 1),
        },
    }


def upcoming_renewals(subscriptions: list, days_ahead: int = 30) -> dict:
    """Return subscriptions renewing within the next N days (assumes monthly billing)."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    renewals = []
    for s in subscriptions:
        try:
            start = datetime.strptime(s['startDate'], '%Y-%m-%d').date()
            day_of_month = start.day
            # Next renewal = same day-of-month in current or next month
            for delta_months in (0, 1):
                year = today.year + (today.month - 1 + delta_months) // 12
                month = (today.month - 1 + delta_months) % 12 + 1
                try:
                    renewal = date(year, month, day_of_month)
                except ValueError:
                    import calendar
                    renewal = date(year, month, calendar.monthrange(year, month)[1])
                if today <= renewal <= cutoff:
                    renewals.append({**s, 'next_renewal': renewal.isoformat()})
                    break
        except (ValueError, TypeError, KeyError):
            continue
    renewals.sort(key=lambda x: x['next_renewal'])
    return {'success': True, 'renewals': renewals, 'count': len(renewals)}


def goal_progress(goals: list) -> dict:
    """Return goal ETA and progress percentage for each goal."""
    today = date.today()
    results = []
    for g in goals:
        try:
            start = datetime.strptime(g['startDate'], '%Y-%m-%d').date()
            months_elapsed = max(0, (today.year - start.year) * 12 + (today.month - start.month))
            contribution = float(g.get('monthContribution', 0))
            target = float(g.get('amount', 0))
            saved = contribution * months_elapsed
            pct = min(100.0, (saved / target * 100)) if target > 0 else 0.0
            if contribution > 0 and target > saved:
                months_left = (target - saved) / contribution
                eta = date(today.year + (today.month - 1 + int(months_left)) // 12,
                           (today.month - 1 + int(months_left)) % 12 + 1, 1).isoformat()
            elif saved >= target:
                eta = 'reached'
            else:
                eta = 'unknown'
            results.append({
                'name': g.get('name', ''),
                'target': round(target, 2),
                'saved_estimate': round(saved, 2),
                'progress_pct': round(pct, 1),
                'monthly_contribution': round(contribution, 2),
                'eta': eta,
                'currency': g.get('currency', 'USD'),
            })
        except (ValueError, TypeError, KeyError):
            continue
    return {'success': True, 'goals': results}


def spending_by_category(expenses: list, month: Optional[str] = None) -> dict:
    """Aggregate expenses by category, optionally filtered to a single month (YYYY-MM)."""
    totals: dict = defaultdict(float)
    counts: dict = defaultdict(int)
    for e in expenses:
        if month and not e.get('date', '').startswith(month):
            continue
        cat = e.get('tags', 'Other')
        totals[cat] += e.get('price', 0)
        counts[cat] += 1
    grand_total = sum(totals.values())
    result = []
    for cat in sorted(totals, key=lambda c: totals[c], reverse=True):
        result.append({
            'category': cat,
            'total': round(totals[cat], 2),
            'count': counts[cat],
            'pct': round(totals[cat] / grand_total * 100, 1) if grand_total else 0.0,
        })
    return {'success': True, 'by_category': result, 'grand_total': round(grand_total, 2), 'month': month}


def monthly_totals(entries: list, amount_field: str = 'price') -> dict:
    """Sum entries by month. Works for expenses (price) or income (amount)."""
    by_month: dict = defaultdict(float)
    for e in entries:
        try:
            month = e['date'][:7]
            by_month[month] += e.get(amount_field, 0)
        except (KeyError, TypeError):
            continue
    ordered = [{'month': m, 'total': round(v, 2)} for m, v in sorted(by_month.items())]
    return {'success': True, 'monthly': ordered}


def savings_rate_history(expenses: list, income: list) -> dict:
    """Monthly savings rate (%) over all recorded history."""
    exp_by_month: dict = defaultdict(float)
    inc_by_month: dict = defaultdict(float)
    for e in expenses:
        try:
            exp_by_month[e['date'][:7]] += e.get('price', 0)
        except (KeyError, TypeError):
            pass
    for i in income:
        try:
            inc_by_month[i['date'][:7]] += i.get('amount', 0)
        except (KeyError, TypeError):
            pass
    months = sorted(set(list(exp_by_month) + list(inc_by_month)))
    history = []
    for m in months:
        inc = inc_by_month.get(m, 0.0)
        exp = exp_by_month.get(m, 0.0)
        rate = round((inc - exp) / inc * 100, 1) if inc > 0 else 0.0
        history.append({'month': m, 'income': round(inc, 2), 'expenses': round(exp, 2), 'savings_rate_pct': rate})
    return {'success': True, 'history': history}


def budget_utilization(expenses: list, budget: list, month: Optional[str] = None) -> dict:
    """Return per-category budget utilization for a given month."""
    if month is None:
        month = date.today().strftime('%Y-%m')
    spent: dict = defaultdict(float)
    for e in expenses:
        if e.get('date', '')[:7] == month:
            spent[e.get('tags', 'Other')] += e.get('price', 0)
    result = []
    for b in budget:
        cat = b.get('category', '')
        limit = float(b.get('amount', 0))
        total_spent = spent.get(cat, 0.0)
        pct = round(total_spent / limit * 100, 1) if limit > 0 else 0.0
        result.append({
            'category': cat,
            'limit': round(limit, 2),
            'spent': round(total_spent, 2),
            'remaining': round(max(0.0, limit - total_spent), 2),
            'utilization_pct': pct,
            'over_budget': total_spent > limit,
            'currency': b.get('currency', 'USD'),
        })
    return {'success': True, 'month': month, 'utilization': result}


def income_vs_expenses(expenses: list, income: list) -> dict:
    """Monthly income vs expenses comparison."""
    exp_by_month: dict = defaultdict(float)
    inc_by_month: dict = defaultdict(float)
    for e in expenses:
        try:
            exp_by_month[e['date'][:7]] += e.get('price', 0)
        except (KeyError, TypeError):
            pass
    for i in income:
        try:
            inc_by_month[i['date'][:7]] += i.get('amount', 0)
        except (KeyError, TypeError):
            pass
    months = sorted(set(list(exp_by_month) + list(inc_by_month)))
    result = []
    for m in months:
        inc = inc_by_month.get(m, 0.0)
        exp = exp_by_month.get(m, 0.0)
        result.append({
            'month': m,
            'income': round(inc, 2),
            'expenses': round(exp, 2),
            'net': round(inc - exp, 2),
        })
    return {'success': True, 'monthly': result}


def monthly_comparison(expenses: list, month_a: str, month_b: str) -> dict:
    """Compare spending by category between two months (YYYY-MM)."""
    def _totals(month: str) -> dict:
        t: dict = defaultdict(float)
        for e in expenses:
            if e.get('date', '')[:7] == month:
                t[e.get('tags', 'Other')] += e.get('price', 0)
        return t

    a = _totals(month_a)
    b = _totals(month_b)
    cats = sorted(set(list(a) + list(b)))
    comparison = []
    for cat in cats:
        va, vb = a.get(cat, 0.0), b.get(cat, 0.0)
        comparison.append({
            'category': cat,
            month_a: round(va, 2),
            month_b: round(vb, 2),
            'change': round(vb - va, 2),
            'change_pct': round((vb - va) / va * 100, 1) if va > 0 else None,
        })
    return {'success': True, 'month_a': month_a, 'month_b': month_b, 'comparison': comparison}
