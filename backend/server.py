import os
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from analytics import detect_anomalies, forecast_spending, tax_summary
from ai import answer_query, is_configured as ai_configured
from bots import AdvancedCategorizationCrew
from ocr import parse_receipt

app = FastAPI()
security = HTTPBearer()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"


def require_pro(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        claims = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired license key")
    if "advanced_categorization" not in claims.get("features", []):
        raise HTTPException(status_code=403, detail="This feature requires a Pro license")
    return claims


# ── Request models ─────────────────────────────────────────────────────────────

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
