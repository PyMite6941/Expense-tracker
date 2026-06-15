import hmac
import logging
import os
from typing import Literal, Optional

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

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

# Cloud Run sits behind a Google load balancer; request.client.host is always
# the LB's internal IP, not the real caller. Use X-Forwarded-For instead so
# each real client gets its own rate-limit bucket.
def _real_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    return xff.split(",")[0].strip() if xff else (
        request.client.host if request.client else "unknown"
    )

limiter = Limiter(key_func=_real_ip)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Reject oversized JSON bodies before they reach any endpoint.
# (Receipt uploads are handled separately with a per-read MAX_BYTES guard.)
_JSON_BODY_LIMIT = 5 * 1024 * 1024  # 5 MB

class _BodySizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            cl = request.headers.get("content-length")
            if cl and int(cl) > _JSON_BODY_LIMIT:
                return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)

app.add_middleware(_BodySizeMiddleware)

security = HTTPBearer()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB for receipt images
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
    base_currency: str = Field(default='USD', min_length=3, max_length=3,
                               pattern=r'^[A-Za-z]{3}$')


class AnomalyRequest(BaseModel):
    expenses: list
    z_threshold: float = Field(default=2.5, ge=1.0, le=5.0)


class TaxSummaryRequest(BaseModel):
    expenses: list
    income: list
    year: int = Field(..., ge=2000, le=2100)
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
    days_ahead: int = Field(default=30, ge=1, le=365)


class GoalProgressRequest(BaseModel):
    goals: list


class SpendingByCategoryRequest(BaseModel):
    expenses: list
    month: Optional[str] = Field(default=None, pattern=r'^\d{4}-(?:0[1-9]|1[0-2])$')


class MonthlyTotalsRequest(BaseModel):
    entries: list
    amount_field: Literal['price', 'amount'] = 'price'


class SavingsRateRequest(BaseModel):
    expenses: list
    income: list


class BudgetUtilizationRequest(BaseModel):
    expenses: list
    budget: list
    month: Optional[str] = Field(default=None, pattern=r'^\d{4}-(?:0[1-9]|1[0-2])$')


class IncomeVsExpensesRequest(BaseModel):
    expenses: list
    income: list


class MonthlyComparisonRequest(BaseModel):
    expenses: list
    month_a: str = Field(..., pattern=r'^\d{4}-(?:0[1-9]|1[0-2])$')
    month_b: str = Field(..., pattern=r'^\d{4}-(?:0[1-9]|1[0-2])$')


class RecommendBudgetsRequest(BaseModel):
    expenses: list
    income: list


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get('/health')
@limiter.limit("120/minute")
def health(request: Request):
    return {'status': 'ok', 'ai_configured': ai_configured()}


# Vision API call — Pro required, tight rate limit to control cost
@app.post('/parse-receipt')
@limiter.limit("5/minute")
async def parse(request: Request, file: UploadFile,
                _claims: dict = Depends(require_pro)):
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
@limiter.limit("20/minute")
def net_worth(req: NetWorthRequest, request: Request,
              _claims: dict = Depends(require_max)):
    data = {'expenses': req.expenses, 'income': req.income,
            'subscriptions': req.subscriptions, 'goals': req.goals,
            'assets': req.assets, 'liabilities': req.liabilities}
    return net_worth_snapshot(data)


# Pro feature (budget_forecasting in JWT)
@app.post('/forecast')
@limiter.limit("20/minute")
def forecast(req: ForecastRequest, request: Request,
             _claims: dict = Depends(require_pro)):
    result = forecast_spending(_cap(req.expenses, 'expenses'), base_currency=req.base_currency)
    if not result['success']:
        raise HTTPException(status_code=422, detail=result.get('message', 'Forecast failed'))
    return result


# Pro feature (anomaly_detection in JWT)
@app.post('/detect-anomalies')
@limiter.limit("20/minute")
def anomalies(req: AnomalyRequest, request: Request,
              _claims: dict = Depends(require_pro)):
    return detect_anomalies(_cap(req.expenses, 'expenses'), z_threshold=req.z_threshold)


@app.post('/tax-summary')
@limiter.limit("30/minute")
def tax(req: TaxSummaryRequest, request: Request):
    return tax_summary(
        _cap(req.expenses, 'expenses'),
        _cap(req.income, 'income'),
        req.year,
        deductible_categories=req.deductible_categories,
    )


# LLM call — Pro required, tight rate limit to control cost
@app.post('/query')
@limiter.limit("10/minute")
def query(req: QueryRequest, request: Request,
          _claims: dict = Depends(require_pro)):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        answer = answer_query(req.question, req.data)
        return {'answer': answer}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/health-score')
@limiter.limit("30/minute")
def health_score(req: HealthScoreRequest, request: Request):
    data = {'expenses': req.expenses, 'income': req.income, 'budget': req.budget,
            'subscriptions': req.subscriptions, 'goals': req.goals}
    return financial_health_score(data)


@app.post('/upcoming-renewals')
@limiter.limit("60/minute")
def renewals(req: UpcomingRenewalsRequest, request: Request):
    return upcoming_renewals(req.subscriptions, days_ahead=req.days_ahead)


@app.post('/goal-progress')
@limiter.limit("60/minute")
def goals(req: GoalProgressRequest, request: Request):
    return goal_progress(req.goals)


@app.post('/spending-by-category')
@limiter.limit("60/minute")
def by_category(req: SpendingByCategoryRequest, request: Request):
    return spending_by_category(req.expenses, month=req.month)


@app.post('/monthly-totals')
@limiter.limit("60/minute")
def totals(req: MonthlyTotalsRequest, request: Request):
    return monthly_totals(req.entries, amount_field=req.amount_field)


@app.post('/savings-rate')
@limiter.limit("60/minute")
def savings(req: SavingsRateRequest, request: Request):
    return savings_rate_history(req.expenses, req.income)


@app.post('/budget-utilization')
@limiter.limit("60/minute")
def utilization(req: BudgetUtilizationRequest, request: Request):
    return budget_utilization(req.expenses, req.budget, month=req.month)


@app.post('/income-vs-expenses')
@limiter.limit("60/minute")
def inc_vs_exp(req: IncomeVsExpensesRequest, request: Request):
    return income_vs_expenses(req.expenses, req.income)


@app.post('/monthly-comparison')
@limiter.limit("60/minute")
def comparison(req: MonthlyComparisonRequest, request: Request):
    return monthly_comparison(req.expenses, req.month_a, req.month_b)


# LLM call — Pro required, tight rate limit to control cost
@app.post('/recommend-budgets')
@limiter.limit("10/minute")
def recommend(req: RecommendBudgetsRequest, request: Request,
              _claims: dict = Depends(require_pro)):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        return recommend_budgets(req.expenses, req.income)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# CrewAI call — Pro required, very tight limit (slow + costly)
@app.post('/advanced-categorize')
@limiter.limit("5/minute")
async def advanced_categorize(request: Request, _claims: dict = Depends(require_pro)):
    body = await request.json()
    expenses = body.get('expenses', [])
    context = str(body.get('context',
                            'Categorize and analyze these expenses with advanced subcategories'))

    if not expenses:
        raise HTTPException(status_code=400, detail='No expenses provided')
    if len(context) > 500:
        raise HTTPException(status_code=400, detail='context exceeds 500 characters')

    crew = AdvancedCategorizationCrew(context=context)
    result = crew.run(expenses)
    return result


class ResetActivationsRequest(BaseModel):
    key_id: Optional[str] = None   # the JWT jti
    token: Optional[str] = None    # or the full license key, jti derived from it


@app.post('/admin/reset-activations')
@limiter.limit("5/minute")
def reset_activations(req: ResetActivationsRequest, request: Request):
    secret = os.getenv('ADMIN_RESET_SECRET')
    if not secret:
        raise HTTPException(status_code=503, detail='Activation reset is not configured.')
    incoming = request.headers.get('x-admin-secret', '')
    if not hmac.compare_digest(incoming.encode(), secret.encode()):
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
