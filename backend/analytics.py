import statistics
from collections import defaultdict
from datetime import date, datetime
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
