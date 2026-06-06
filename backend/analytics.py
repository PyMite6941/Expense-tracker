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

    net_cash_flow = total_income - total_expenses

    return {
        'success': True,
        'base_currency': base_currency,
        'total_income': round(total_income, 2),
        'total_expenses': round(total_expenses, 2),
        'net_cash_flow': round(net_cash_flow, 2),
        'monthly_subscription_burden': round(monthly_sub_burden, 2),
        'goal_targets_total': round(goal_targets, 2),
        'goal_contributions_to_date': round(goal_saved, 2),
        'estimated_net_worth': round(net_cash_flow - monthly_sub_burden * 12, 2),
    }


def financial_health_score(data: dict, base_currency: str = 'USD') -> dict:
    """Composite 0-100 financial health score with per-pillar breakdown."""
    expenses = data.get('expenses', [])
    income = data.get('income', [])
    budget = data.get('budget', [])
    subscriptions = data.get('subscriptions', [])
    goals = data.get('goals', [])

    today = date.today()
    current_month = today.strftime('%Y-%m')

    month_income = sum(i['amount'] for i in income if i.get('date', '').startswith(current_month))
    month_expenses = sum(e['price'] for e in expenses if e.get('date', '').startswith(current_month))

    # Pillar 1: savings rate (target >= 20%)
    if month_income > 0:
        savings_rate = (month_income - month_expenses) / month_income
        savings_score = min(100, max(0, savings_rate / 0.20 * 100))
    else:
        savings_score = 0.0

    # Pillar 2: budget adherence (% of budgets not exceeded)
    if budget:
        budget_totals: dict = defaultdict(float)
        for e in expenses:
            if e.get('date', '').startswith(current_month):
                budget_totals[e.get('tags', '')] += e['price']
        within = sum(1 for b in budget if budget_totals.get(b['category'], 0) <= float(b['amount']))
        adherence_score = within / len(budget) * 100
    else:
        adherence_score = 100.0

    # Pillar 3: subscription burden (target < 10% of monthly income)
    monthly_subs = sum(float(s['price']) for s in subscriptions)
    if month_income > 0:
        sub_ratio = monthly_subs / month_income
        sub_score = min(100, max(0, (1 - sub_ratio / 0.10) * 100))
    else:
        sub_score = 100.0 if not subscriptions else 0.0

    # Pillar 4: goal consistency (all goals making contributions this month)
    if goals:
        on_track = 0
        for g in goals:
            try:
                start = datetime.strptime(g['startDate'], '%Y-%m-%d').date()
                if start <= today and g.get('monthContribution', 0) > 0:
                    on_track += 1
            except (ValueError, TypeError, KeyError):
                pass
        active_goals = [g for g in goals if g.get('monthContribution', 0) > 0]
        goal_score = (on_track / len(active_goals) * 100) if active_goals else 100.0
    else:
        goal_score = 100.0

    weights = {'savings': 0.35, 'budget': 0.30, 'subscriptions': 0.20, 'goals': 0.15}
    composite = (
        savings_score * weights['savings']
        + adherence_score * weights['budget']
        + sub_score * weights['subscriptions']
        + goal_score * weights['goals']
    )

    def grade(s: float) -> str:
        if s >= 85: return 'A'
        if s >= 70: return 'B'
        if s >= 55: return 'C'
        if s >= 40: return 'D'
        return 'F'

    return {
        'success': True,
        'score': round(composite, 1),
        'grade': grade(composite),
        'pillars': {
            'savings_rate': round(savings_score, 1),
            'budget_adherence': round(adherence_score, 1),
            'subscription_burden': round(sub_score, 1),
            'goal_consistency': round(goal_score, 1),
        },
        'details': {
            'monthly_income': round(month_income, 2),
            'monthly_expenses': round(month_expenses, 2),
            'monthly_subscriptions': round(monthly_subs, 2),
        },
    }


def upcoming_renewals(subscriptions: list, days_ahead: int = 30) -> dict:
    """Return subscriptions whose next monthly billing falls within days_ahead days."""
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)
    upcoming = []

    for s in subscriptions:
        try:
            start = datetime.strptime(s['startDate'], '%Y-%m-%d').date()
        except (ValueError, TypeError, KeyError):
            continue

        # Find the next billing date on or after today
        billing_day = start.day
        candidate = today.replace(day=1)
        # Walk month by month until we find next billing on or after today
        for _ in range(3):
            try:
                import calendar
                last_day = calendar.monthrange(candidate.year, candidate.month)[1]
                day = min(billing_day, last_day)
                billing = candidate.replace(day=day)
                if billing >= today:
                    break
                # Advance one month
                if candidate.month == 12:
                    candidate = candidate.replace(year=candidate.year + 1, month=1)
                else:
                    candidate = candidate.replace(month=candidate.month + 1)
            except ValueError:
                break

        if today <= billing <= cutoff:
            days_until = (billing - today).days
            upcoming.append({
                **s,
                'next_billing_date': billing.isoformat(),
                'days_until': days_until,
            })

    upcoming.sort(key=lambda x: x['days_until'])
    return {'success': True, 'upcoming': upcoming, 'count': len(upcoming)}


def goal_progress(goals: list) -> dict:
    """Return progress %, amount saved so far, and estimated completion date per goal."""
    today = date.today()
    results = []

    for g in goals:
        try:
            target = float(g.get('amount', 0))
            contribution = float(g.get('monthContribution', 0))
            start = datetime.strptime(g['startDate'], '%Y-%m-%d').date()
        except (ValueError, TypeError, KeyError):
            continue

        months_elapsed = max(0, (today.year - start.year) * 12 + (today.month - start.month))
        saved = contribution * months_elapsed
        pct = min(100.0, (saved / target * 100)) if target > 0 else 0.0

        if contribution > 0 and saved < target:
            months_remaining = (target - saved) / contribution
            import math
            months_remaining = math.ceil(months_remaining)
            completion = today
            for _ in range(months_remaining):
                if completion.month == 12:
                    completion = completion.replace(year=completion.year + 1, month=1)
                else:
                    completion = completion.replace(month=completion.month + 1)
            eta = completion.isoformat()
        elif saved >= target:
            eta = 'Completed'
        else:
            eta = 'No contribution set'

        results.append({
            'name': g.get('name', ''),
            'target': round(target, 2),
            'saved': round(saved, 2),
            'remaining': round(max(0.0, target - saved), 2),
            'percent': round(pct, 1),
            'eta': eta,
            'currency': g.get('currency', 'USD'),
        })

    return {'success': True, 'goals': results}


def spending_by_category(expenses: list, month: Optional[str] = None) -> dict:
    """Sum expenses by category, optionally filtered to a YYYY-MM month."""
    totals: dict = defaultdict(float)
    for e in expenses:
        if month and not e.get('date', '').startswith(month):
            continue
        totals[e.get('tags', 'Other')] += e.get('price', 0.0)
    return {
        'success': True,
        'by_category': {k: round(v, 2) for k, v in sorted(totals.items(), key=lambda x: -x[1])},
        'month': month,
    }


def monthly_totals(expenses: list) -> dict:
    """Sum all expenses per calendar month, sorted chronologically."""
    totals: dict = defaultdict(float)
    for e in expenses:
        m = e.get('date', '')[:7]
        if m:
            totals[m] += e.get('price', 0.0)
    return {
        'success': True,
        'monthly': {k: round(v, 2) for k, v in sorted(totals.items())},
    }


def savings_rate_history(income: list, expenses: list) -> dict:
    """Monthly savings rate (%) for every month that has income data."""
    monthly_inc: dict = defaultdict(float)
    monthly_exp: dict = defaultdict(float)
    for i in income:
        m = i.get('date', '')[:7]
        if m:
            monthly_inc[m] += i.get('amount', 0.0)
    for e in expenses:
        m = e.get('date', '')[:7]
        if m:
            monthly_exp[m] += e.get('price', 0.0)

    all_months = sorted(set(list(monthly_inc.keys()) + list(monthly_exp.keys())))
    history = {}
    for m in all_months:
        inc = monthly_inc.get(m, 0.0)
        exp = monthly_exp.get(m, 0.0)
        rate = round((inc - exp) / inc * 100, 1) if inc > 0 else None
        history[m] = {
            'income': round(inc, 2),
            'expenses': round(exp, 2),
            'savings': round(inc - exp, 2),
            'rate_pct': rate,
        }
    return {'success': True, 'history': history}


def budget_utilization(expenses: list, budget: list, month: str) -> list:
    """Per-budget-category spend vs limit for a given month."""
    totals: dict = defaultdict(float)
    for e in expenses:
        if e.get('date', '').startswith(month):
            totals[e.get('tags', 'Other')] += e.get('price', 0.0)

    result = []
    for b in budget:
        cat = b['category']
        limit = float(b.get('amount', 0))
        spent = totals.get(cat, 0.0)
        pct = round(spent / limit * 100, 1) if limit > 0 else 0.0
        result.append({
            'category': cat,
            'limit': round(limit, 2),
            'spent': round(spent, 2),
            'remaining': round(max(0.0, limit - spent), 2),
            'percent': pct,
            'currency': b.get('currency', 'USD'),
        })
    result.sort(key=lambda x: -x['percent'])
    return result


def income_vs_expenses(income: list, expenses: list) -> dict:
    """Monthly income and expense totals side-by-side, sorted chronologically."""
    monthly_inc: dict = defaultdict(float)
    monthly_exp: dict = defaultdict(float)
    for i in income:
        m = i.get('date', '')[:7]
        if m:
            monthly_inc[m] += i.get('amount', 0.0)
    for e in expenses:
        m = e.get('date', '')[:7]
        if m:
            monthly_exp[m] += e.get('price', 0.0)

    all_months = sorted(set(list(monthly_inc.keys()) + list(monthly_exp.keys())))
    return {
        'success': True,
        'months': all_months,
        'income': [round(monthly_inc.get(m, 0.0), 2) for m in all_months],
        'expenses': [round(monthly_exp.get(m, 0.0), 2) for m in all_months],
    }


def monthly_comparison(expenses: list, month_a: str, month_b: str) -> dict:
    """Compare category spending between two months."""
    cats_a: dict = defaultdict(float)
    cats_b: dict = defaultdict(float)
    for e in expenses:
        m = e.get('date', '')[:7]
        cat = e.get('tags', 'Other')
        if m == month_a:
            cats_a[cat] += e.get('price', 0.0)
        elif m == month_b:
            cats_b[cat] += e.get('price', 0.0)

    all_cats = sorted(set(list(cats_a.keys()) + list(cats_b.keys())))
    return {
        'success': True,
        'categories': all_cats,
        'month_a': month_a,
        'month_b': month_b,
        'values_a': [round(cats_a.get(c, 0.0), 2) for c in all_cats],
        'values_b': [round(cats_b.get(c, 0.0), 2) for c in all_cats],
    }
