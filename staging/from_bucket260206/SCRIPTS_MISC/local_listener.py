from fastapi import FastAPI, Request
import uvicorn
import subprocess

app = FastAPI()

@app.post("/trigger")
async def trigger(request: Request):
    data = await request.json()
    command = data.get("cmd")

    if command == "open_vscode":
        try:
            result = subprocess.run(
                ["osascript", "/Users/icmini/open_vscode.applescript"],
                capture_output=True,
                text=True,
                check=True
            )
            print("✅ AppleScript ran successfully")
            print("stdout:", result.stdout)
            print("stderr:", result.stderr)
            return {"status": "VSCode opened via .applescript"}
        except subprocess.CalledProcessError as e:
            print("❌ AppleScript failed")
            print("stdout:", e.stdout)
            print("stderr:", e.stderr)
            return {"status": "Error running AppleScript"}
    else:
        return {"status": f"⚠ Unknown command: {command}"}

