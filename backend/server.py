import hmac
import ipaddress
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
from ai import (
    answer_query, is_configured as ai_configured, recommend_budgets,
    smart_budget_advisor, expense_narrative, cash_flow_forecast,
    debt_elimination_planner, investment_readiness_check,
    financial_goal_coach, spending_dna_analysis,
)
from ocr import parse_receipt
from ip_limits import check_and_register_ip, key_id_from_claims, reset_key

log = logging.getLogger(__name__)

# Cloud Run sits behind Google's front end; request.client.host is the peer,
# not the real caller, so X-Forwarded-For is what identifies a client.
#
# SECURITY: read XFF from the RIGHT, never the left. A client can send its own
# X-Forwarded-For and Google appends to it, so the leftmost entry is entirely
# attacker-controlled. Taking xff.split(",")[0] (as this used to) let anyone
# choose their own rate-limit bucket AND their own license-activation identity —
# so a shared key could report one constant fake IP from any number of machines
# and never exceed its device cap.
#
# The rightmost entry is the one the infrastructure appended and cannot be
# forged. TRUSTED_PROXY_HOPS counts any ADDITIONAL trusted proxies in front of
# Cloud Run (e.g. a custom external HTTPS LB, or Cloudflare); each one shifts
# the real client one position further left. Default 0 = Cloud Run's *.run.app
# URL hit directly, which is how these services are deployed today.
_TRUSTED_PROXY_HOPS = int(os.getenv("TRUSTED_PROXY_HOPS", "0"))


def _real_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        idx = len(parts) - 1 - _TRUSTED_PROXY_HOPS
        if 0 <= idx < len(parts):
            candidate = parts[idx]
            try:
                ipaddress.ip_address(candidate.rsplit(":", 1)[0]
                                     if candidate.count(":") == 1 else candidate)
                return candidate
            except ValueError:
                log.warning("Unparseable X-Forwarded-For entry; falling back to peer")
    return request.client.host if request.client else "unknown"

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
            # Content-Length is attacker-controlled; a non-numeric value used to
            # raise ValueError here and surface as a 500 before any handler ran.
            cl = request.headers.get("content-length")
            if cl:
                try:
                    too_big = int(cl) > _JSON_BODY_LIMIT
                except ValueError:
                    return JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)
                if too_big:
                    return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)

app.add_middleware(_BodySizeMiddleware)

security = HTTPBearer()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB for receipt images
ALGORITHM = "HS256"

# Must stay in lockstep with auth-service/jwt_utils.py — auth-service signs,
# this service verifies, and both read the same Secret Manager value.
_KNOWN_BAD_SECRETS = {
    "change-me-in-production",
    "replace-with-a-long-random-string",
    "secret",
    "changeme",
}
_MIN_SECRET_LEN = 32


def _load_verification_secret() -> str:
    """Return the HS256 verification secret, or refuse to start.

    Fails CLOSED. This used to default to "change-me-in-production" and only
    warn, which meant a missing Secret Manager binding left every paid endpoint
    open to anyone who forged a token with the placeholder published in this
    public repo. ALLOW_INSECURE_JWT_SECRET=1 bypasses this for local dev only.
    """
    secret = (os.getenv("JWT_SECRET") or "").strip()
    dev_ok = os.getenv("ALLOW_INSECURE_JWT_SECRET", "").lower() in ("1", "true", "yes")

    if not secret:
        problem = "JWT_SECRET is not set"
    elif secret.lower() in _KNOWN_BAD_SECRETS:
        problem = "JWT_SECRET is a well-known placeholder value"
    elif len(secret) < _MIN_SECRET_LEN:
        problem = f"JWT_SECRET is shorter than {_MIN_SECRET_LEN} characters"
    else:
        return secret

    if dev_ok:
        log.warning("%s — continuing anyway because ALLOW_INSECURE_JWT_SECRET is set. "
                    "NEVER set that flag on a deployed service.", problem)
        return secret or "insecure-development-secret"

    raise RuntimeError(
        f"{problem}. Every paid endpoint is gated on verifying license JWTs with "
        "it, so this service refuses to start without a real one. Set JWT_SECRET "
        "(32+ chars, identical to auth-service) or, for local development only, "
        "set ALLOW_INSECURE_JWT_SECRET=1."
    )


JWT_SECRET = _load_verification_secret()


def _decode(credentials: HTTPAuthorizationCredentials) -> dict:
    try:
        return jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")


def _client_ip(request: Request) -> str:
    # Single source of truth with the rate limiter — this used to be a second,
    # subtly different copy that read the spoofable leftmost XFF entry. The
    # license device-cap is enforced on this value, so it must not be forgeable.
    ip = _real_ip(request)
    return "" if ip == "unknown" else ip


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


def _require_feature(feature: str, label: str):
    """Factory: returns a FastAPI dependency that checks for a specific license feature."""
    def _dep(request: Request,
             credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
        claims = _decode(credentials)
        if feature not in claims.get("features", []):
            raise HTTPException(status_code=403, detail=f"This feature requires a {label} license")
        _enforce_ip_limit(claims, request)
        return claims
    return _dep


def _token_limit(claims: dict) -> int:
    """Return max_tokens based on tier: Max gets 4096, Pro gets 2000."""
    return 4096 if claims.get("tier") == "max" else 2000


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


class SmartBudgetRequest(BaseModel):
    expenses: list
    income: list
    current_budget: list = []


class ExpenseNarrativeRequest(BaseModel):
    expenses: list
    income: list
    month: str


class CashFlowForecastRequest(BaseModel):
    expenses: list
    income: list
    recurring_expenses: list = []
    recurring_income: list = []
    months_ahead: int = Field(3, ge=1, le=12)


class DebtPlannerRequest(BaseModel):
    liabilities: list
    monthly_payment_budget: float = 0.0


class InvestmentReadinessRequest(BaseModel):
    expenses: list
    income: list
    assets: list = []
    goals: list = []


class FinancialCoachRequest(BaseModel):
    goals: list
    expenses: list
    income: list


class SpendingDNARequest(BaseModel):
    expenses: list


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

    try:
        from bots import AdvancedCategorizationCrew
    except ImportError as exc:
        raise HTTPException(status_code=503, detail=f'Advanced categorization unavailable: {exc}')

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


# ── Pro AI endpoints (token-limited by tier) ───────────────────────────────────

@app.post('/smart-budget-advisor')
@limiter.limit("10/minute")
def smart_budget(req: SmartBudgetRequest, request: Request,
                 claims: dict = Depends(_require_feature('smart_budget_advisor', 'Pro'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = smart_budget_advisor(
            _cap(req.expenses, 'expenses'),
            _cap(req.income, 'income'),
            req.current_budget,
            max_tokens=_token_limit(claims),
        )
        if not result.get('success'):
            raise HTTPException(status_code=422, detail=result.get('raw', 'Analysis failed'))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/expense-narrative')
@limiter.limit("10/minute")
def narrative(req: ExpenseNarrativeRequest, request: Request,
              claims: dict = Depends(_require_feature('expense_narrative', 'Pro'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = expense_narrative(
            _cap(req.expenses, 'expenses'),
            _cap(req.income, 'income'),
            req.month,
            max_tokens=_token_limit(claims),
        )
        if not result.get('success'):
            raise HTTPException(status_code=422, detail=result.get('message', 'Narrative failed'))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/cash-flow-forecast')
@limiter.limit("10/minute")
def cash_flow(req: CashFlowForecastRequest, request: Request,
              claims: dict = Depends(_require_feature('cash_flow_forecast', 'Pro'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    months = min(req.months_ahead, 3 if claims.get('tier') == 'pro' else 12)
    try:
        result = cash_flow_forecast(
            _cap(req.expenses, 'expenses'),
            _cap(req.income, 'income'),
            req.recurring_expenses,
            req.recurring_income,
            months_ahead=months,
            max_tokens=_token_limit(claims),
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# ── Max AI endpoints (no token cap) ───────────────────────────────────────────

@app.post('/debt-planner')
@limiter.limit("10/minute")
def debt_plan(req: DebtPlannerRequest, request: Request,
              claims: dict = Depends(_require_feature('debt_planner', 'Max'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = debt_elimination_planner(
            req.liabilities,
            req.monthly_payment_budget,
            max_tokens=_token_limit(claims),
        )
        if not result.get('success'):
            raise HTTPException(status_code=422, detail=result.get('message', 'Planner failed'))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/investment-readiness')
@limiter.limit("10/minute")
def investment(req: InvestmentReadinessRequest, request: Request,
               claims: dict = Depends(_require_feature('investment_readiness', 'Max'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = investment_readiness_check(
            _cap(req.expenses, 'expenses'),
            _cap(req.income, 'income'),
            req.assets,
            req.goals,
            max_tokens=_token_limit(claims),
        )
        return result
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/financial-coach')
@limiter.limit("10/minute")
def coach(req: FinancialCoachRequest, request: Request,
          claims: dict = Depends(_require_feature('financial_coach', 'Max'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = financial_goal_coach(
            req.goals,
            _cap(req.expenses, 'expenses'),
            _cap(req.income, 'income'),
            max_tokens=_token_limit(claims),
        )
        if not result.get('success'):
            raise HTTPException(status_code=422, detail=result.get('message', 'Coaching failed'))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


@app.post('/spending-dna')
@limiter.limit("10/minute")
def dna(req: SpendingDNARequest, request: Request,
        claims: dict = Depends(_require_feature('spending_dna', 'Max'))):
    if not ai_configured():
        raise HTTPException(status_code=503, detail='AI_API_KEY is not configured.')
    try:
        result = spending_dna_analysis(
            _cap(req.expenses, 'expenses'),
            max_tokens=_token_limit(claims),
        )
        if not result.get('success'):
            raise HTTPException(status_code=422, detail=result.get('message', 'Analysis failed'))
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
