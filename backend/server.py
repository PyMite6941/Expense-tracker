from fastapi import FastAPI, HTTPException, UploadFile
from ocr import parse_receipt

app = FastAPI()

MAX_BYTES = 10 * 1024 * 1024  # 10 MB

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse-receipt")
async def parse(file: UploadFile):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (jpg, png, etc.)")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Max 10MB.")
    try:
        return parse_receipt(data)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Receipt parsing failed. Try again.")
