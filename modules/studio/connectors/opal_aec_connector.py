import typer
import yaml
import json
from pathlib import Path
from datetime import datetime

app = typer.Typer()
ROOT = Path("/Users/icmini/0luka")

class OpalAECConnector:
    def __init__(self, payload_path: str):
        self.payload_path = Path(payload_path)
        with open(self.payload_path, 'r', encoding='utf-8') as f:
            self.data = yaml.safe_load(f)
        
    def apply_structural_lock(self):
        """แปลง Perfect Prompt ให้เป็นค่าทางเทคนิคที่ AI ห้ามบิดพริ้ว"""
        mode = self.data.get("mode", "drawing")
        
        # ตารางค่าคงที่สำหรับ 'กรงขังพิกเซล' (Structural Guardrails)
        locks = {
            "sketch": {
                "controlnet_model": "scribble_hed_aec",
                "control_weight": 1.5,      # ล็อกเส้นร่างเข้มข้นสูงสุด
                "denoising_strength": 0.45,  # ห้าม AI มโนรูปทรงใหม่เกิน 45%
                "guidance_scale": 7.5
            },
            "drawing": {
                "controlnet_model": "canny_mlsd_aec",
                "control_weight": 1.2,      # ล็อกความเป๊ะของเส้นกิ่ง
                "denoising_strength": 0.35,  # เน้นความแม่นยำทางสถาปัตยกรรม
                "guidance_scale": 9.0
            },
            "retouch": {
                "controlnet_model": "inpainting_global",
                "control_weight": 1.0,
                "denoising_strength": 0.60,  # ยอมให้เปลี่ยนพื้นผิวแต่ห้ามเปลี่ยนทรง
                "guidance_scale": 7.0
            }
        }
        
        return locks.get(mode, locks["drawing"])

    def generate_opal_job(self):
        """สร้างไฟล์ Job สำหรับส่งเข้าเครื่อง Google Opal"""
        lock_params = self.apply_structural_lock()
        
        opal_job = {
            "job_id": f"OPAL-{datetime.now().strftime('%y%m%d-%H%M%S')}",
            "template_id": f"0luka-aec-{self.data['mode']}-v1",
            "parameters": {
                "prompt": self.data.get("perfect_prompt", ""),
                "negative_prompt": "hallucination, distorted walls, extra windows, blurry textures, altered perspective",
                **lock_params # ฉีดค่า Structural Lock เข้าไปใน Job ทันที
            },
            "system_audit": {
                "source_payload": str(self.payload_path),
                "fidelity_target": "85%+",
                "zero_waste_verdict": "ENFORCED"
            }
        }

        # Export เป็น JSON สำหรับ Opal API
        output_dir = ROOT / "modules" / "studio" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"opal_job_{opal_job['job_id']}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(opal_job, f, indent=2, ensure_ascii=False)
            
        print(f"🔒 [STRUCTURAL LOCK] Opal Job Created: {output_path.name}")
        return output_path

@app.command()
def deploy(payload: str):
    connector = OpalAECConnector(payload)
    connector.generate_opal_job()

if __name__ == "__main__":
    app()
