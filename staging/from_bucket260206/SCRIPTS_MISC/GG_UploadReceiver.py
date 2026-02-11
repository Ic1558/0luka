from fastapi import FastAPI, File, UploadFile
import shutil, os

app = FastAPI()
os.makedirs("gg_uploads", exist_ok=True)

@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    with open(f"gg_uploads/{file.filename}", "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"status": "✅ Success", "filename": file.filename}

