import os
import json
import requests

_PROVIDERS = {
    'groq': {
        'base_url': 'https://api.groq.com/openai/v1',
        'default_model': 'llama-3.1-8b-instant',
    },
    'openrouter': {
        'base_url': 'https://openrouter.ai/api/v1',
        'default_model': 'meta-llama/llama-3.1-8b-instruct:free',
    },
}

_CATEGORIES = ['Food', 'Transport', 'Entertainment', 'Utilities', 'Bills', 'Other']


def is_configured() -> bool:
    return bool(os.environ.get('AI_API_KEY', '').strip())


def _provider_config() -> tuple[str, str, str]:
    name = os.environ.get('AI_PROVIDER', 'groq').lower()
    cfg = _PROVIDERS.get(name, _PROVIDERS['groq'])
    key = os.environ.get('AI_API_KEY', '')
    model = os.environ.get('AI_MODEL', cfg['default_model'])
    return cfg['base_url'], key, model


def _chat(messages: list, max_tokens: int = 512, temperature: float = 0.3) -> str:
    base_url, api_key, model = _provider_config()
    resp = requests.post(
        f'{base_url}/chat/completions',
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        json={'model': model, 'messages': messages, 'max_tokens': max_tokens, 'temperature': temperature},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()['choices'][0]['message']['content'].strip()


def suggest_category(merchant: str, amount: float, categories: list = None) -> str:
    cats = categories or _CATEGORIES
    messages = [
        {
            'role': 'system',
            'content': (
                f'You are an expense categorizer. Given a merchant name and purchase amount, '
                f'respond with exactly one word from this list: {", ".join(cats)}. '
                'No punctuation, no explanation — just the single category name.'
            ),
        },
        {'role': 'user', 'content': f'Merchant: {merchant}\nAmount: {amount}'},
    ]
    raw = _chat(messages, max_tokens=10, temperature=0)
    for cat in cats:
        if cat.lower() in raw.lower():
            return cat
    return 'Other'


def recommend_budgets(expenses: list, income: list) -> dict:
    from datetime import date
    today = date.today()
    three_months_ago = f"{today.year}-{today.month - 3:02d}" if today.month > 3 else \
        f"{today.year - 1}-{today.month + 9:02d}"
    recent = [e for e in expenses if e.get('date', '') >= three_months_ago]

    from collections import defaultdict
    totals: dict = defaultdict(list)
    for e in recent:
        totals[e.get('tags', 'Other')].append(e.get('price', 0))
    avg_by_cat = {cat: sum(v) / max(1, len(v)) * len(set(e['date'][:7] for e in recent if e.get('tags') == cat))
                  for cat, v in totals.items()}

    monthly_income = sum(i.get('amount', 0) for i in income) / max(1, len(
        set(i['date'][:7] for i in income if i.get('date'))
    )) if income else 0

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a personal finance advisor. Given recent average monthly spending per category '
                'and the user\'s average monthly income, suggest realistic budget limits for each category. '
                'Respond with a JSON object: {"recommendations": [{"category": str, "suggested_limit": float, '
                '"reasoning": str}]}. Use numbers only, no markdown.'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Monthly income: {monthly_income:.2f}\n'
                f'Recent avg monthly spend by category:\n' +
                '\n'.join(f'  {cat}: {amt:.2f}' for cat, amt in sorted(avg_by_cat.items()))
            ),
        },
    ]
    raw = _chat(messages, max_tokens=400, temperature=0.2)
    try:
        import json as _json
        start = raw.find('{')
        end = raw.rfind('}') + 1
        return _json.loads(raw[start:end]) if start >= 0 else {'recommendations': []}
    except Exception:
        return {'recommendations': [], 'raw': raw}


def answer_query(question: str, financial_data: dict) -> str:
    summary = {
        'expenses': financial_data.get('expenses', [])[-100:],
        'income': financial_data.get('income', [])[-100:],
        'budget': financial_data.get('budget', []),
        'subscriptions': financial_data.get('subscriptions', []),
        'goals': financial_data.get('goals', []),
    }
    messages = [
        {
            'role': 'system',
            'content': (
                'You are a helpful financial assistant. Answer the user\'s question concisely '
                'using only the provided financial data. Format currency values to 2 decimal places. '
                'If data is insufficient to answer, say so clearly.'
            ),
        },
        {
            'role': 'user',
            'content': f'Financial data:\n{json.dumps(summary, indent=2)}\n\nQuestion: {question}',
        },
    ]
    return _chat(messages, max_tokens=600, temperature=0.3)


# ── Pro AI features (honour max_tokens; Pro callers pass 2000, Max pass 4096) ──

def smart_budget_advisor(
    expenses: list,
    income: list,
    current_budget: list = None,
    max_tokens: int = 2000,
) -> dict:
    """50/30/20 rule analysis with category-by-category AI budget recommendations."""
    from collections import defaultdict

    if current_budget is None:
        current_budget = []

    months_active = max(1, len({e.get('date', '')[:7] for e in expenses if e.get('date')}))
    income_months = max(1, len({i.get('date', '')[:7] for i in income if i.get('date')}))

    cat_totals: dict = defaultdict(float)
    for e in expenses:
        cat_totals[e.get('tags', 'Other')] += e.get('price', 0)
    cat_monthly = {c: round(v / months_active, 2) for c, v in cat_totals.items()}

    monthly_income = round(sum(i.get('amount', 0) for i in income) / income_months, 2) if income else 0
    total_monthly_spend = round(sum(cat_monthly.values()), 2)

    needs_cats = {'Food', 'Transport', 'Utilities', 'Bills', 'Health', 'Education'}
    wants_cats = {'Entertainment', 'Shopping', 'Subscriptions', 'Travel'}
    needs = sum(v for k, v in cat_monthly.items() if k in needs_cats)
    wants = sum(v for k, v in cat_monthly.items() if k in wants_cats)
    savings = max(0, monthly_income - total_monthly_spend)

    def _pct(x): return round(x / monthly_income * 100, 1) if monthly_income > 0 else 0

    budget_ctx = (
        '\nCurrent budget limits:\n' +
        '\n'.join(f'  {b["category"]}: ${float(b.get("amount", b.get("limit", 0))):.2f}'
                  for b in current_budget)
    ) if current_budget else ''

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a certified financial planner. Provide specific, actionable budget '
                'recommendations using the 50/30/20 rule as guidance. '
                'Respond ONLY with valid JSON:\n'
                '{"recommendations":[{"category":str,"current_avg":float,"suggested_limit":float,'
                '"change_pct":float,"reasoning":str,"action":str}],'
                '"summary":str,"savings_potential":float,'
                '"rule_analysis":{"needs_pct":float,"wants_pct":float,"savings_pct":float,'
                '"compliance":str}}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Monthly income: ${monthly_income:.2f}\n'
                f'Total monthly spending: ${total_monthly_spend:.2f} ({_pct(total_monthly_spend)}% of income)\n\n'
                f'50/30/20 snapshot:\n'
                f'  Needs: ${needs:.2f} ({_pct(needs)}% vs 50% target)\n'
                f'  Wants: ${wants:.2f} ({_pct(wants)}% vs 30% target)\n'
                f'  Current savings: ${savings:.2f} ({_pct(savings)}% vs 20% target)\n\n'
                f'Spending by category (monthly avg):\n' +
                '\n'.join(
                    f'  {c}: ${a:.2f} ({_pct(a)}% of income)'
                    for c, a in sorted(cat_monthly.items(), key=lambda x: -x[1])
                ) + budget_ctx
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.2)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        return {'success': True, **json.loads(raw[s:e2])} if s >= 0 else {'success': False, 'raw': raw}
    except Exception:
        return {'success': False, 'raw': raw, 'recommendations': []}


def expense_narrative(
    expenses: list,
    income: list,
    month: str,
    max_tokens: int = 2000,
) -> dict:
    """Write a personal monthly financial narrative — a letter from a trusted advisor."""
    from collections import defaultdict

    m_exp = [e for e in expenses if e.get('date', '').startswith(month)]
    m_inc = [i for i in income if i.get('date', '').startswith(month)]
    if not m_exp and not m_inc:
        return {'success': False, 'message': 'No data for this month'}

    total_exp = sum(e.get('price', 0) for e in m_exp)
    total_inc = sum(i.get('amount', 0) for i in m_inc)
    net = total_inc - total_exp
    savings_rate = round(net / total_inc * 100, 1) if total_inc > 0 else 0

    cat_totals: dict = defaultdict(float)
    for e in m_exp:
        cat_totals[e.get('tags', 'Other')] += e.get('price', 0)
    top_cat = max(cat_totals, key=lambda k: cat_totals[k]) if cat_totals else 'N/A'
    top_exp = max(m_exp, key=lambda e: e.get('price', 0), default={})
    top_src = max(m_inc, key=lambda i: i.get('amount', 0), default={})

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a warm, insightful financial coach. Write a personal 2-3 paragraph monthly '
                'financial summary — like a letter from a trusted advisor. Use specific numbers. '
                'Identify wins and one clear area to improve. End with a concrete tip for next month. '
                'Then respond with valid JSON:\n'
                '{"narrative":str,"highlights":[str],"concerns":[str],"tip":str,'
                '"sentiment":"positive"|"mixed"|"concerning","grade":str}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Month: {month}\n'
                f'Income: ${total_inc:.2f}   Expenses: ${total_exp:.2f}   Net: ${net:+.2f}\n'
                f'Savings rate: {savings_rate}%\n'
                f'Top category: {top_cat} (${cat_totals.get(top_cat, 0):.2f})\n'
                f'Largest purchase: {top_exp.get("purchased","N/A")} — ${top_exp.get("price",0):.2f}\n'
                f'Main income source: {top_src.get("source","N/A")}\n\n'
                f'Spending breakdown:\n' +
                '\n'.join(f'  {c}: ${a:.2f}' for c, a in sorted(cat_totals.items(), key=lambda x: -x[1]))
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.4)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        return {'success': True, **json.loads(raw[s:e2])} if s >= 0 else {'success': False, 'raw': raw}
    except Exception:
        return {'success': False, 'narrative': raw[:800]}


def cash_flow_forecast(
    expenses: list,
    income: list,
    recurring_expenses: list = None,
    recurring_income: list = None,
    months_ahead: int = 3,
    max_tokens: int = 2000,
) -> dict:
    """Combine historical averages + recurring commitments into a multi-month cash flow projection."""
    from collections import defaultdict
    from datetime import date

    if recurring_expenses is None:
        recurring_expenses = []
    if recurring_income is None:
        recurring_income = []

    months_ahead = max(1, min(months_ahead, 12))
    today = date.today()

    # Build last-3-month baseline
    recent: set = set()
    for delta in range(1, 4):
        y = today.year + (today.month - 1 - delta) // 12
        m = (today.month - 1 - delta) % 12 + 1
        recent.add(f'{y}-{m:02d}')

    exp_by_m: dict = defaultdict(float)
    inc_by_m: dict = defaultdict(float)
    for e in expenses:
        if e.get('date', '')[:7] in recent:
            exp_by_m[e['date'][:7]] += e.get('price', 0)
    for i in income:
        if i.get('date', '')[:7] in recent:
            inc_by_m[i['date'][:7]] += i.get('amount', 0)

    avg_exp = sum(exp_by_m.values()) / max(1, len(exp_by_m)) if exp_by_m else 0
    avg_inc = sum(inc_by_m.values()) / max(1, len(inc_by_m)) if inc_by_m else 0
    rec_exp = sum(float(r.get('amount', 0)) for r in recurring_expenses)
    rec_inc = sum(float(r.get('amount', 0)) for r in recurring_income)

    projections = []
    for i in range(1, months_ahead + 1):
        y = today.year + (today.month - 1 + i) // 12
        m = (today.month - 1 + i) % 12 + 1
        pi = round(avg_inc + rec_inc, 2)
        pe = round(avg_exp + rec_exp, 2)
        projections.append({'month': f'{y}-{m:02d}',
                            'predicted_income': pi,
                            'predicted_expenses': pe,
                            'net': round(pi - pe, 2)})

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a financial analyst. Interpret a cash flow projection and identify key risks '
                'and opportunities. Be specific and concise. '
                'Respond with valid JSON:\n'
                '{"narrative":str,"risks":[str],"opportunities":[str],'
                '"overall_trend":"improving"|"stable"|"deteriorating"}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'3-month baseline — avg monthly expenses: ${avg_exp:.2f}, avg income: ${avg_inc:.2f}\n'
                f'Fixed recurring expenses: ${rec_exp:.2f}/mo, recurring income: ${rec_inc:.2f}/mo\n\n'
                f'Projections:\n' +
                '\n'.join(f'  {p["month"]}: income ${p["predicted_income"]:.2f}, '
                          f'expenses ${p["predicted_expenses"]:.2f}, net ${p["net"]:+.2f}'
                          for p in projections)
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.3)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        ai = json.loads(raw[s:e2]) if s >= 0 else {}
    except Exception:
        ai = {'narrative': raw[:500]}

    return {'success': True, 'projections': projections, 'months_ahead': months_ahead, **ai}


# ── Max AI features (deep analysis, 4096 tokens) ───────────────────────────────

def debt_elimination_planner(
    liabilities: list,
    monthly_payment_budget: float = 0.0,
    max_tokens: int = 4096,
) -> dict:
    """Avalanche vs snowball comparison with math + AI recommendation."""
    debts = [
        {
            'name': l.get('name', 'Debt'),
            'balance': float(l.get('balance', 0)),
            'rate': float(l.get('interest_rate', l.get('rate', 0))),
            'type': l.get('type', 'other'),
            'currency': l.get('currency', 'USD'),
        }
        for l in liabilities
        if float(l.get('balance', 0)) > 0
    ]
    if not debts:
        return {'success': False, 'message': 'No liabilities with positive balances'}

    total_debt = sum(d['balance'] for d in debts)
    for d in debts:
        d['min_payment'] = max(25.0, d['balance'] * 0.02)
    total_minimums = sum(d['min_payment'] for d in debts)
    extra = max(0, monthly_payment_budget - total_minimums) if monthly_payment_budget > 0 else 0

    def _simulate(order: list) -> tuple[int, float]:
        bals = {d['name']: d['balance'] for d in order}
        rates = {d['name']: d['rate'] / 1200 for d in order}  # monthly rate
        mins = {d['name']: d['min_payment'] for d in order}
        months, total_interest, avail_extra = 0, 0.0, extra
        while any(b > 0 for b in bals.values()) and months < 600:
            months += 1
            pool = avail_extra
            for d in order:
                n = d['name']
                if bals[n] <= 0:
                    continue
                interest = bals[n] * rates[n]
                total_interest += interest
                bals[n] += interest
                pmt = min(mins[n] + pool, bals[n])
                pool = max(0, pool - max(0, pmt - mins[n]))
                bals[n] = max(0, bals[n] - pmt)
        return months, round(total_interest, 2)

    aval = sorted(debts, key=lambda d: -d['rate'])
    snow = sorted(debts, key=lambda d: d['balance'])
    aval_mo, aval_int = _simulate(aval)
    snow_mo, snow_int = _simulate(snow)

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a debt counselor. Recommend the best payoff strategy, considering both '
                'mathematical optimisation and psychological factors. '
                'Respond with valid JSON:\n'
                '{"recommendation":"avalanche"|"snowball"|"hybrid","reasoning":str,"ai_advice":str,'
                '"action_steps":[str],"interest_savings":float}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Total debt: ${total_debt:,.2f}  Budget: ${monthly_payment_budget:.2f}/mo  '
                f'Minimums: ${total_minimums:.2f}  Extra available: ${extra:.2f}\n\n'
                f'Debts:\n' +
                '\n'.join(f'  {d["name"]}: ${d["balance"]:,.2f} at {d["rate"]}% ({d["type"]})'
                          for d in debts) +
                f'\n\nAvalanche (highest rate first): order={[d["name"] for d in aval]}, '
                f'{aval_mo} months, ${aval_int:,.2f} interest\n'
                f'Snowball (smallest balance first): order={[d["name"] for d in snow]}, '
                f'{snow_mo} months, ${snow_int:,.2f} interest'
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.3)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        ai = json.loads(raw[s:e2]) if s >= 0 else {}
    except Exception:
        ai = {'ai_advice': raw[:800]}

    return {
        'success': True,
        'total_debt': round(total_debt, 2),
        'debts': debts,
        'avalanche': {'order': [d['name'] for d in aval], 'months_to_payoff': aval_mo, 'total_interest': aval_int},
        'snowball':  {'order': [d['name'] for d in snow], 'months_to_payoff': snow_mo, 'total_interest': snow_int},
        **ai,
    }


def investment_readiness_check(
    expenses: list,
    income: list,
    assets: list = None,
    goals: list = None,
    max_tokens: int = 4096,
) -> dict:
    """Assess investment readiness and generate personalised portfolio allocation advice."""
    import statistics as _stats
    from collections import defaultdict

    if assets is None:
        assets = []
    if goals is None:
        goals = []

    exp_months = max(1, len({e.get('date', '')[:7] for e in expenses if e.get('date')}))
    inc_months = max(1, len({i.get('date', '')[:7] for i in income if i.get('date')}))
    monthly_exp = sum(e.get('price', 0) for e in expenses) / exp_months
    monthly_inc = sum(i.get('amount', 0) for i in income) / inc_months
    disposable = monthly_inc - monthly_exp

    liquid = sum(float(a.get('value', 0)) for a in assets if a.get('type') == 'liquid')
    total_assets = sum(float(a.get('value', 0)) for a in assets)
    ef_months = round(liquid / monthly_exp, 1) if monthly_exp > 0 else 0

    by_month: dict = defaultdict(float)
    for e in expenses:
        if e.get('date'):
            by_month[e['date'][:7]] += e.get('price', 0)
    vals = list(by_month.values())
    volatility = round(_stats.stdev(vals) / (_stats.mean(vals) or 1), 2) if len(vals) >= 2 else 0.2

    ent_spend = sum(e.get('price', 0) for e in expenses if e.get('tags') in ('Entertainment', 'Travel', 'Shopping'))
    ent_ratio = round(ent_spend / max(1, sum(e.get('price', 0) for e in expenses)), 2)

    risk_score = round(
        min(1.0, ef_months / 6) * 30 +
        min(1.0, max(0, disposable) / max(1, monthly_inc)) * 40 +
        (1 - min(1.0, volatility)) * 20 +
        ent_ratio * 10,
        1,
    )
    risk_profile = 'aggressive' if risk_score >= 70 else 'moderate' if risk_score >= 40 else 'conservative'
    monthly_investable = round(max(0, disposable * 0.6), 2)

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a certified financial advisor. Provide personalised investment guidance. '
                'Be specific with percentages and concrete strategies. '
                'Respond with valid JSON:\n'
                '{"allocation":{"index_funds":float,"bonds":float,"real_estate":float,'
                '"emergency_cash":float,"other":float},'
                '"strategies":[str],"priorities":[str],"warnings":[str],'
                '"readiness_score":int,"readiness_summary":str}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Monthly income: ${monthly_inc:.2f}  Monthly expenses: ${monthly_exp:.2f}\n'
                f'Disposable: ${disposable:.2f}  Investable estimate: ${monthly_investable:.2f}/mo\n'
                f'Emergency fund: ${liquid:.2f} ({ef_months} months of expenses)\n'
                f'Total assets: ${total_assets:.2f}\n'
                f'Spending volatility: {volatility} (lower = more stable)\n'
                f'Risk profile (calculated): {risk_profile} (score {risk_score}/100)\n'
                f'Active goals: {len(goals)}\n'
                f'{"✅ Emergency fund adequate" if ef_months >= 3 else "⚠️ Emergency fund below 3 months"}'
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.3)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        ai = json.loads(raw[s:e2]) if s >= 0 else {}
    except Exception:
        ai = {'readiness_summary': raw[:800]}

    return {
        'success': True,
        'monthly_disposable': round(disposable, 2),
        'monthly_investable': monthly_investable,
        'emergency_fund_months': ef_months,
        'risk_profile': risk_profile,
        'risk_score': risk_score,
        **ai,
    }


def financial_goal_coach(
    goals: list,
    expenses: list,
    income: list,
    max_tokens: int = 4096,
) -> dict:
    """Per-goal AI coaching with progress assessment and concrete action steps."""
    from datetime import date

    if not goals:
        return {'success': False, 'message': 'No goals provided'}

    inc_months = max(1, len({i.get('date', '')[:7] for i in income if i.get('date')}))
    exp_months = max(1, len({e.get('date', '')[:7] for e in expenses if e.get('date')}))
    monthly_inc = sum(i.get('amount', 0) for i in income) / inc_months
    monthly_exp = sum(e.get('price', 0) for e in expenses) / exp_months
    free_cash = monthly_inc - monthly_exp

    today = date.today()
    statuses = []
    for g in goals:
        try:
            start = date.fromisoformat(g.get('startDate', str(today)))
            elapsed = max(0, (today.year - start.year) * 12 + (today.month - start.month))
            target = float(g.get('amount', 0))
            contrib = float(g.get('monthContribution', 0))
            saved = contrib * elapsed
            pct = round(min(100, saved / target * 100), 1) if target > 0 else 0
            needed = (target - saved) / max(1, 24) if saved < target else 0
            statuses.append({
                'name': g.get('name', 'Goal'),
                'target': target, 'saved': round(saved, 2), 'pct': pct,
                'monthly_contribution': contrib, 'required_monthly': round(needed, 2),
                'shortfall': round(max(0, needed - contrib), 2),
                'on_track': contrib >= needed or saved >= target,
                'currency': g.get('currency', 'USD'),
            })
        except Exception:
            continue

    if not statuses:
        return {'success': False, 'message': 'Could not process goals'}

    messages = [
        {
            'role': 'system',
            'content': (
                'You are an encouraging but realistic financial coach. Provide personalised coaching '
                'for each goal with concrete action steps. Use specific numbers. Be motivating. '
                'Respond with valid JSON:\n'
                '{"coaching":[{"goal":str,"status":"on_track"|"behind"|"completed",'
                '"advice":str,"action_steps":[str],"timeline_note":str,"motivation":str}],'
                '"overall_assessment":str,"top_priority":str}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Monthly income: ${monthly_inc:.2f}  Monthly expenses: ${monthly_exp:.2f}  '
                f'Free cash: ${free_cash:.2f}\n\nGoals:\n' +
                '\n'.join(
                    ('  ' + g['name'] + ': $' + f'{g["saved"]:.2f}' + ' / $' + f'{g["target"]:.2f}' +
                     ' (' + str(g['pct']) + '%)\n'
                     '    Paying: $' + f'{g["monthly_contribution"]:.2f}' + '/mo, '
                     'needs: $' + f'{g["required_monthly"]:.2f}' + '/mo — ' +
                     ('✅ on track' if g['on_track'] else '⚠️ short $' + f'{g["shortfall"]:.2f}' + '/mo'))
                    for g in statuses
                )
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.5)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        ai = json.loads(raw[s:e2]) if s >= 0 else {}
    except Exception:
        ai = {'overall_assessment': raw[:800], 'coaching': []}

    return {'success': True, 'goal_statuses': statuses, **ai}


def spending_dna_analysis(expenses: list, max_tokens: int = 4096) -> dict:
    """Identify spending personality type and deep behavioural patterns."""
    from collections import Counter, defaultdict
    from datetime import datetime

    if len(expenses) < 5:
        return {'success': False, 'message': 'Need at least 5 expenses for DNA analysis'}

    day_totals: dict = defaultdict(float)
    day_counts: dict = defaultdict(int)
    dom_totals: dict = defaultdict(float)
    for e in expenses:
        try:
            d = datetime.fromisoformat(e.get('date', ''))
            day = d.strftime('%A')
            day_totals[day] += e.get('price', 0)
            day_counts[day] += 1
            dom_totals[d.day] += e.get('price', 0)
        except Exception:
            continue

    peak_day = max(day_totals, key=lambda k: day_totals[k]) if day_totals else 'Unknown'

    first = sum(v for k, v in dom_totals.items() if k <= 10)
    mid   = sum(v for k, v in dom_totals.items() if 11 <= k <= 20)
    last  = sum(v for k, v in dom_totals.items() if k > 20)
    peak_period = 'beginning' if first >= max(mid, last) else 'end' if last >= max(first, mid) else 'middle'

    merchant_counts = Counter(e.get('purchased', '') for e in expenses)
    top_merchants = [
        {'name': m, 'count': c,
         'total': round(sum(e.get('price', 0) for e in expenses if e.get('purchased') == m), 2)}
        for m, c in merchant_counts.most_common(5) if m
    ]

    monthly_by_cat: dict = defaultdict(lambda: defaultdict(float))
    for e in expenses:
        d = e.get('date', '')[:7]
        if d:
            monthly_by_cat[d][e.get('tags', 'Other')] += e.get('price', 0)
    recent_months = sorted(monthly_by_cat.keys())[-3:]
    cat_trends: dict = {}
    for cat in {c for m in recent_months for c in monthly_by_cat[m]}:
        vals = [monthly_by_cat[m].get(cat, 0) for m in recent_months]
        cat_trends[cat] = 'increasing' if vals[-1] - vals[0] > 10 else 'decreasing' if vals[-1] - vals[0] < -10 else 'stable'

    cat_prices: dict = defaultdict(list)
    for e in expenses:
        cat_prices[e.get('tags', 'Other')].append(e.get('price', 0))
    avg_tx = {c: round(sum(ps) / len(ps), 2) for c, ps in cat_prices.items()}

    total = len(expenses)
    impulse_ratio = round(sum(1 for e in expenses if e.get('price', 0) < 20) / total, 2)

    messages = [
        {
            'role': 'system',
            'content': (
                'You are a behavioural finance psychologist. Identify the user\'s Spending DNA — '
                'their financial personality and key habits. Give a creative but relatable personality type name. '
                'Respond with valid JSON:\n'
                '{"personality_type":str,"personality_description":str,"traits":[str],'
                '"insights":[str],"recommendations":[str],"strengths":[str],"watch_out_for":[str]}'
            ),
        },
        {
            'role': 'user',
            'content': (
                f'Transactions analysed: {total}\n'
                f'Peak spending day: {peak_day}\n'
                f'Peak month period: {peak_period}\n'
                f'Impulse-buy ratio (< $20): {impulse_ratio:.0%}\n\n'
                f'Top merchants:\n' +
                '\n'.join(f'  {m["name"]}: {m["count"]}x (${m["total"]:.2f})' for m in top_merchants) +
                f'\n\nCategory trends (3-month):\n' +
                '\n'.join(f'  {c}: {t}' for c, t in cat_trends.items()) +
                f'\n\nAvg transaction by category:\n' +
                '\n'.join(f'  {c}: ${a:.2f}' for c, a in sorted(avg_tx.items(), key=lambda x: -x[1])[:8]) +
                f'\n\nDay-of-week totals:\n' +
                '\n'.join(f'  {d}: ${t:.2f}' for d, t in sorted(day_totals.items(), key=lambda x: -x[1]))
            ),
        },
    ]
    raw = _chat(messages, max_tokens=max_tokens, temperature=0.6)
    try:
        s, e2 = raw.find('{'), raw.rfind('}') + 1
        ai = json.loads(raw[s:e2]) if s >= 0 else {}
    except Exception:
        ai = {'personality_type': 'Unknown', 'insights': [raw[:400]]}

    return {
        'success': True,
        'stats': {
            'total_transactions': total,
            'peak_day': peak_day,
            'peak_period': peak_period,
            'impulse_ratio': impulse_ratio,
            'top_merchants': top_merchants,
            'category_trends': cat_trends,
            'avg_transaction_by_category': avg_tx,
        },
        **ai,
    }
