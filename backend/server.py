import os
from fastapi import FastAPI, HTTPException, UploadFile
from ocr import parse_receipt

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/parse-receipt")
async def parse(file: UploadFile):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image (jpg, png, etc.)")
    data = await file.read()
    return parse_receipt(data)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
