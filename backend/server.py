import logging
import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field

from analytics import (
    budget_utilization, detect_anomalies, financial_health_score, forecast_spending,
    goal_progress, income_vs_expenses, monthly_comparison, monthly_totals,
    net_worth_snapshot, savings_rate_history, spending_by_category, tax_summary,
    upcoming_renewals,
)
from ai import answer_query, is_configured as ai_configured, recommend_budgets
from bots import AdvancedCategorizationCrew
from ocr import parse_receipt
from ip_limits import check_and_register_ip, key_id_from_claims, reset_key

log = logging.getLogger(__name__)

app = FastAPI()
security = HTTPBearer()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"


@app.on_event("startup")
def _check_jwt_secret():
    if JWT_SECRET == "change-me-in-production":
        log.warning(
            "JWT_SECRET is using the insecure default value. "
            "Set the JWT_SECRET environment variable before deploying to production."
        )


def _decode(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")


def _client_ip(request: Request) -> str:
    # Behind Cloud Run the real client IP is the first entry of X-Forwarded-For.
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


def _enforce_ip_limit(claims: dict, request: Request) -> None:
    allowed, _count, limit = check_and_register_ip(claims, _client_ip(request))
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=(
                f"This license key is already active on its maximum of {limit} "
                f"devices/IPs. Email greshamd27@gmail.com to reset your activations."
            ),
        )


def require_pro(request: Request,
                credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    claims = _decode(credentials)
    if "advanced_categorization" not in claims.get("features", []):
        raise HTTPException(status_code=403, detail="This feature requires a Pro license")
    _enforce_ip_limit(claims, request)
    return claims


def require_max(request: Request,
                credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    claims = _decode(credentials)
    if "net_worth" not in claims.get("features", []):
        raise HTTPException(status_code=403, detail="This feature requires a Max license")
    _enforce_ip_limit(claims, request)
    return claims


# ── Request models ─────────────────────────────────────────────────────────────

MAX_LIST = 10_000


def _cap(lst: list, name: str = 'list') -> list:
    if len(lst) > MAX_LIST:
        raise HTTPException(status_code=400, detail=f'{name} exceeds {MAX_LIST} item limit')
    return lst


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


class NetWorthRequest(BaseModel):
    expenses: list
    income: list
    subscriptions: list = []
    goals: list = []
    assets: list = []
    liabilities: list = []


class QueryRequest(BaseModel):
    question: str = Field(..., max_length=1000)
    data: dict


class HealthScoreRequest(BaseModel):
    expenses: list
    income: list
    budget: list = []
    subscriptions: list = []
    goals: list = []


class UpcomingRenewalsRequest(BaseModel):
    subscriptions: list
    days_ahead: int = 30


class GoalProgressRequest(BaseModel):
    goals: list


class SpendingByCategoryRequest(BaseModel):
    expenses: list
    month: Optional[str] = None


class MonthlyTotalsRequest(BaseModel):
    entries: list
    amount_field: str = 'price'


class SavingsRateRequest(BaseModel):
    expenses: list
    income: list


class BudgetUtilizationRequest(BaseModel):
    expenses: list
    budget: list
    month: Optional[str] = None


class IncomeVsExpensesRequest(BaseModel):
    expenses: list
    income: list


class MonthlyComparisonRequest(BaseModel):
    expenses: list
    month_a: str
    month_b: str


class RecommendBudgetsRequest(BaseModel):
    expenses: list
    income: list


# ── Endpoints ──────────────────────────────────────────────────────────────────

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


@app.post('/net-worth')
def net_worth(req: NetWorthRequest, _claims: dict = Depends(require_max)):
    data = {'expenses': req.expenses, 'income': req.income,
            'subscriptions': req.subscriptions, 'goals': req.goals,
            'assets': req.assets, 'liabilities': req.liabilities}
    return net_worth_snapshot(data)


@app.post('/forecast')
def forecast(req: ForecastRequest):
    result = forecast_spending(_cap(req.expenses, 'expenses'), base_currency=req.base_currency)
    if not result['success']:
        raise HTTPException(status_code=422, detail=result.get('message', 'Forecast failed'))
    return result


@app.post('/detect-anomalies')
def anomalies(req: AnomalyRequest):
    return detect_anomalies(_cap(req.expenses, 'expenses'), z_threshold=req.z_threshold)


@app.post('/tax-summary')
def tax(req: TaxSummaryRequest):
    return tax_summary(
        _cap(req.expenses, 'expenses'),
        _cap(req.income, 'income'),
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
    data = {'expenses': req.expenses, 'income': req.income, 'budget': req.budget,
            'subscriptions': req.subscriptions, 'goals': req.goals}
    return financial_health_score(data)


@app.post('/upcoming-renewals')
def renewals(req: UpcomingRenewalsRequest):
    return upcoming_renewals(req.subscriptions, days_ahead=req.days_ahead)


@app.post('/goal-progress')
def goals(req: GoalProgressRequest):
    return goal_progress(req.goals)


@app.post('/spending-by-category')
def by_category(req: SpendingByCategoryRequest):
    return spending_by_category(req.expenses, month=req.month)


@app.post('/monthly-totals')
def totals(req: MonthlyTotalsRequest):
    return monthly_totals(req.entries, amount_field=req.amount_field)


@app.post('/savings-rate')
def savings(req: SavingsRateRequest):
    return savings_rate_history(req.expenses, req.income)


@app.post('/budget-utilization')
def utilization(req: BudgetUtilizationRequest):
    return budget_utilization(req.expenses, req.budget, month=req.month)


@app.post('/income-vs-expenses')
def inc_vs_exp(req: IncomeVsExpensesRequest):
    return income_vs_expenses(req.expenses, req.income)


@app.post('/monthly-comparison')
def comparison(req: MonthlyComparisonRequest):
    return monthly_comparison(req.expenses, req.month_a, req.month_b)


@app.post('/recommend-budgets')
def recommend(req: RecommendBudgetsRequest):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        return recommend_budgets(req.expenses, req.income)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/advanced-categorize')
async def advanced_categorize(request: Request, _claims: dict = Depends(require_pro)):
    body = await request.json()
    expenses = body.get('expenses', [])
    context = body.get('context', 'Categorize and analyze these expenses with advanced subcategories')

    if not expenses:
        raise HTTPException(status_code=400, detail='No expenses provided')

    crew = AdvancedCategorizationCrew(context=context)
    result = crew.run(expenses)
    return result


class ResetActivationsRequest(BaseModel):
    key_id: Optional[str] = None   # the JWT jti
    token: Optional[str] = None    # or the full license key, jti derived from it


@app.post('/admin/reset-activations')
def reset_activations(req: ResetActivationsRequest, request: Request):
    """Clear a license's registered IPs. Guarded by the ADMIN_RESET_SECRET env
    var, sent in the X-Admin-Secret header. Disabled (503) if the var is unset."""
    secret = os.getenv('ADMIN_RESET_SECRET')
    if not secret:
        raise HTTPException(status_code=503, detail='Activation reset is not configured.')
    if request.headers.get('x-admin-secret', '') != secret:
        raise HTTPException(status_code=401, detail='Unauthorized')

    key_id = req.key_id
    if not key_id and req.token:
        try:
            claims = jwt.decode(req.token, JWT_SECRET, algorithms=[ALGORITHM])
        except JWTError:
            raise HTTPException(status_code=400, detail='Invalid token')
        key_id = key_id_from_claims(claims)
    if not key_id:
        raise HTTPException(status_code=400, detail='Provide key_id or token')

    return {'success': reset_key(key_id), 'key_id': key_id}
