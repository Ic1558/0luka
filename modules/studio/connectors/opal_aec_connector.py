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
        """แปลง Perfect Prompt ให้เป็นค่าทางเทคนิคที่ AI ห้ามบิดพริ้ว (Upgraded for 3-Storey)"""
        mode = self.data.get("mode", "drawing")
        levels = self.data.get("levels", 1)
        
        # ตารางค่าคงที่สำหรับ 'กรงขังพิกเซล' (Structural Guardrails)
        locks = {
            "sketch": {
                "controlnet_model": "scribble_hed_aec",
                "control_weight": 1.5 if levels < 3 else 1.8, # เพิ่มแรงกดสำหรับ 3 ชั้น
                "denoising_strength": 0.45 if levels < 3 else 0.35, # ลดการมโนลง
                "guidance_scale": 7.5
            },
            "drawing": {
                "controlnet_model": "canny_mlsd_aec",
                "control_weight": 1.2 if levels < 3 else 1.4,
                "denoising_strength": 0.35,
                "guidance_scale": 9.0
            },
            "retouch": {
                "controlnet_model": "inpainting_global",
                "control_weight": 1.0,
                "denoising_strength": 0.60,
                "guidance_scale": 7.0
            }
        }
        
        lock_params = locks.get(mode, locks["drawing"])
        
        # 3-Storey Addendum: Dual-Level Lock Logic
        if levels >= 3:
            lock_params["dual_lock_protocol"] = {
                "level_a_strict": ["stairs", "shafts", "core_walls"],
                "level_b_guided": ["furniture", "materials", "lighting"],
                "vertical_anchor_weight": 2.0 # ตัวคูณสำหรับแกนดิ่ง
            }
            
        return lock_params

    def generate_opal_job(self):
        """สร้างไฟล์ Job สำหรับส่งเข้าเครื่อง Google Opal (v1.1 with stacking audit)"""
        lock_params = self.apply_structural_lock()
        levels = self.data.get("levels", 1)
        
        opal_job = {
            "job_id": f"OPAL-{datetime.now().strftime('%y%m%d-%H%M%S')}",
            "template_id": f"0luka-aec-{self.data['mode']}-v1-1-multi",
            "parameters": {
                "prompt": self.data.get("perfect_prompt", ""),
                "negative_prompt": "hallucination, distorted walls, extra windows, blurry textures, altered perspective, floor collapse, missing levels",
                **lock_params
            },
            "system_audit": {
                "source_payload": str(self.payload_path),
                "levels": levels,
                "fidelity_target": "95%+" if levels >= 3 else "85%+",
                "zero_waste_verdict": "ENFORCED",
                "vera_lite_plus": {
                    "page_coverage_check": "REQUIRED" if levels >= 3 else "OPTIONAL",
                    "vertical_core_consistency": "STRICT" if levels >= 3 else "N/A",
                    "stacking_report": "PENDING_EXECUTION"
                }
            }
        }

        # Export เป็น JSON สำหรับ Opal API
        output_dir = ROOT / "modules" / "studio" / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"opal_job_{opal_job['job_id']}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(opal_job, f, indent=2, ensure_ascii=False)
            
        print(f"🔒 [3-STOREY STRUCTURAL LOCK] Opal Job Created: {output_path.name}")
        return output_path

@app.command()
def deploy(payload: str):
    connector = OpalAECConnector(payload)
    connector.generate_opal_job()

if __name__ == "__main__":
    app()
