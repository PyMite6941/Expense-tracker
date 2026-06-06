from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel
from typing import Optional
from ocr import parse_receipt
from analytics import (
    forecast_spending, detect_anomalies, tax_summary,
    financial_health_score, upcoming_renewals, goal_progress,
    spending_by_category, monthly_totals,
    savings_rate_history, budget_utilization, income_vs_expenses, monthly_comparison,
)
from ai import answer_query, recommend_budgets, is_configured as ai_configured

app = FastAPI()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB


# ── Request models ────────────────────────────────────────────────────────────

class ForecastRequest(BaseModel):
    expenses: list
    base_currency: str = 'USD'


class AnomalyRequest(BaseModel):
    expenses: list
    z_threshold: float = 2.5


class TaxSummaryRequest(BaseModel):
    expenses: list
    income: list
    year: int
    deductible_categories: Optional[list] = None


class QueryRequest(BaseModel):
    question: str
    data: dict


class HealthScoreRequest(BaseModel):
    data: dict
    base_currency: str = 'USD'


class RenewalsRequest(BaseModel):
    subscriptions: list
    days_ahead: int = 30


class GoalProgressRequest(BaseModel):
    goals: list


class SpendingRequest(BaseModel):
    expenses: list
    month: Optional[str] = None


class BudgetRecommendRequest(BaseModel):
    expenses: list
    existing_budgets: list = []


class SavingsRateRequest(BaseModel):
    income: list
    expenses: list


class BudgetUtilizationRequest(BaseModel):
    expenses: list
    budget: list
    month: str


class IncomeVsExpensesRequest(BaseModel):
    income: list
    expenses: list


class MonthlyComparisonRequest(BaseModel):
    expenses: list
    month_a: str
    month_b: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get('/health')
def health():
    return {'status': 'ok', 'ai_configured': ai_configured()}


@app.post('/parse-receipt')
async def parse(file: UploadFile):
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail='File must be an image (jpg, png, etc.)')
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail='File too large. Max 10MB.')
    try:
        return parse_receipt(data)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail='Receipt parsing failed. Try again.')


@app.post('/forecast')
def forecast(req: ForecastRequest):
    result = forecast_spending(req.expenses, base_currency=req.base_currency)
    if not result['success']:
        raise HTTPException(status_code=422, detail=result.get('message', 'Forecast failed'))
    return result


@app.post('/detect-anomalies')
def anomalies(req: AnomalyRequest):
    return detect_anomalies(req.expenses, z_threshold=req.z_threshold)


@app.post('/tax-summary')
def tax(req: TaxSummaryRequest):
    return tax_summary(
        req.expenses,
        req.income,
        req.year,
        deductible_categories=req.deductible_categories,
    )


@app.post('/query')
def query(req: QueryRequest):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        answer = answer_query(req.question, req.data)
        return {'answer': answer}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/health-score')
def health_score(req: HealthScoreRequest):
    return financial_health_score(req.data, base_currency=req.base_currency)


@app.post('/upcoming-renewals')
def renewals(req: RenewalsRequest):
    return upcoming_renewals(req.subscriptions, days_ahead=req.days_ahead)


@app.post('/goal-progress')
def goals(req: GoalProgressRequest):
    return goal_progress(req.goals)


@app.post('/spending-by-category')
def spending(req: SpendingRequest):
    return spending_by_category(req.expenses, month=req.month)


@app.post('/monthly-totals')
def totals(req: SpendingRequest):
    return monthly_totals(req.expenses)


@app.post('/recommend-budgets')
def budget_recommendations(req: BudgetRecommendRequest):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        return recommend_budgets(req.expenses, req.existing_budgets)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/savings-rate')
def savings_rate(req: SavingsRateRequest):
    return savings_rate_history(req.income, req.expenses)


@app.post('/budget-utilization')
def bud_util(req: BudgetUtilizationRequest):
    return {'utilization': budget_utilization(req.expenses, req.budget, req.month)}


@app.post('/income-vs-expenses')
def inc_vs_exp(req: IncomeVsExpensesRequest):
    return income_vs_expenses(req.income, req.expenses)


@app.post('/monthly-comparison')
def month_compare(req: MonthlyComparisonRequest):
    return monthly_comparison(req.expenses, req.month_a, req.month_b)
