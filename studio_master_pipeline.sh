#!/bin/bash

# --- 0luka Master Pipeline: Structural Integrity Edition ---
# Workflow: NLP -> Universal Distiller -> Opal Connector -> Nano Banana

INPUT_FILE=$1
USER_NLP=$2
MODE=${3:-drawing} # Default เป็น drawing ถ้าไม่ได้ระบุ

echo "🚀 [0LUKA STUDIO] Initiating High-Fidelity Pipeline..."
echo "📍 Mode: $MODE | Input: $INPUT_FILE"
echo "----------------------------------------------------"

# STEP 1: Distillation (The Brain)
# กลั่นกรอง NLP + Visual ให้กลายเป็น Perfect Prompt
echo "🧠 [STEP 1/3] Distilling AEC Logic via Antigravity..."
python3 modules/studio/engines/universal_studio_distiller.py "$INPUT_FILE" "$USER_NLP" --mode "$MODE"

if [ $? -ne 0 ]; then echo "❌ Distillation Failed. Aborting to save tokens."; exit 1; fi

# ดึงไฟล์ล่าสุดที่ถูกสร้างขึ้นมา (ระบุโหมดเพื่อให้แม่นยำ)
LATEST_PAYLOAD=$(ls -t modules/studio/outputs/universal_payload_${MODE}_*.yaml | head -1)

# STEP 2: Structural Lock (The Connector)
# บีบพิกัดพิกเซลด้วยพารามิเตอร์ทางเทคนิค (Opal Job)
echo "🔒 [STEP 2/3] Enforcing Structural Lock & Generating Opal Job..."
python3 modules/studio/connectors/opal_aec_connector.py deploy "$LATEST_PAYLOAD"

if [ $? -ne 0 ]; then echo "❌ Structural Locking Failed."; exit 1; fi

LATEST_JOB=$(ls -t modules/studio/outputs/opal_job_*.json | head -1)

# STEP 3: Execution (Nano Banana)
# เสกภาพด้วยสกิล Nano Banana (Gemini Image Engine)
echo "🍌 [STEP 3/3] Activating Nano Banana Engine for Final Synthesis..."
python3 modules/studio/features/nano_banana_engine.py activate "$LATEST_JOB"

if [ $? -ne 0 ]; then echo "❌ Nano Banana Execution Failed."; exit 1; fi

echo "----------------------------------------------------"
echo "✅ [SUCCESS] Zero-Waste Pipeline Complete!"
echo "📂 Final Artifacts ready in modules/studio/outputs/"
