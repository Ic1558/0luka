#!/usr/bin/env python3
import sys
import yaml
import json
import argparse
from pathlib import Path
from datetime import datetime, timezone

def now_utc():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def load_data(path_str):
    p = Path(path_str)
    if not p.exists():
        print(f"Error: File not found {p}")
        sys.exit(1)
    with open(p, 'r') as f:
        if p.suffix in ['.yaml', '.yml']:
            return yaml.safe_load(f)
        return json.load(f)

def check_structural(plan, render):
    issues = []
    score = 1.0
    
    # Check 1: Elements existence (Walls/Windows)
    # Plan mock expectation: {"elements": ["wall_north", "window_north", "door_east"]}
    plan_elements = set(plan.get("elements", []))
    render_elements = set(render.get("detected_elements", []))
    
    missing = plan_elements - render_elements
    extra = render_elements - plan_elements
    
    for m in missing:
        issues.append({
            "type": "structural",
            "severity": "high",
            "description": f"Missing required structural element: {m}",
            "zone": m.split("_")[-1].capitalize() if "_" in m else "General"
        })
        score -= 0.2
        
    for e in extra:
        # Extra elements are less severe (decoration?) but worth noting
        issues.append({
            "type": "structural",
            "severity": "low",
            "description": f"Detected un-planned element: {e}",
            "zone": e.split("_")[-1].capitalize() if "_" in e else "General"
        })
        score -= 0.05
        
    return max(0.0, score), issues

def check_semantic(brief, render):
    issues = []
    score = 1.0
    
    # Check 1: Materials
    required_materials = set(brief.get("materials", []))
    detected_materials = set(render.get("detected_materials", []))
    
    missing_mat = required_materials - detected_materials
    
    for m in missing_mat:
        issues.append({
            "type": "semantic",
            "severity": "medium",
            "description": f"Missing required material: {m}",
            "zone": "Material Palette"
        })
        score -= 0.15
        
    # Check 2: Mood
    req_mood = brief.get("mood", "").lower()
    det_mood = render.get("detected_mood", "").lower()
    
    if req_mood and det_mood and req_mood not in det_mood:
         issues.append({
            "type": "semantic",
            "severity": "medium",
            "description": f"Mood mismatch. Requested '{req_mood}', detected '{det_mood}'.",
            "zone": "Ambience"
        })
         score -= 0.2

    return max(0.0, score), issues

def generate_suggestions(issues):
    suggestions = []
    struct_issues = [i for i in issues if i['type'] == 'structural']
    sem_issues = [i for i in issues if i['type'] == 'semantic']
    
    if struct_issues:
        suggestions.append("Increase ControlNet 'LineArt' weight to enforce structural boundaries.")
        suggestions.append(f"Review map for missing elements: {', '.join([i['zone'] for i in struct_issues[:2]])}")
        
    if sem_issues:
        suggestions.append("Refine text prompt to emphasize missing materials.")
        
    if not suggestions and not issues:
        suggestions.append("No actionable drift detected. Proceed to High-Res Render.")
        
    return suggestions

def main():
    parser = argparse.ArgumentParser(description="S4 Feedback Loop Analyzer (PoC)")
    parser.add_argument("--plan", required=True, help="Path to Plan data (JSON/YAML)")
    parser.add_argument("--brief", required=True, help="Path to Brief data (JSON/YAML)")
    parser.add_argument("--render", required=True, help="Path to Render Manifest (JSON/YAML)")
    parser.add_argument("--out", required=True, help="Output path for Report (YAML)")
    
    args = parser.parse_args()
    
    plan_data = load_data(args.plan)
    brief_data = load_data(args.brief)
    render_data = load_data(args.render)
    
    # logic
    struct_score, struct_issues = check_structural(plan_data, render_data)
    sem_score, sem_issues = check_semantic(brief_data, render_data)
    
    all_issues = struct_issues + sem_issues
    suggestions = generate_suggestions(all_issues)
    
    report = {
        "schema": "feedback_report_v1",
        "target_artifact": render_data.get("artifact_id", "unknown"),
        "structural_score": round(struct_score, 2),
        "semantic_score": round(sem_score, 2),
        "issues": all_issues,
        "suggestions": suggestions,
        "created_at_utc": now_utc(),
        "model_version": "po_logic_v0.1"
    }
    
    # write
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w') as f:
        yaml.safe_dump(report, f, sort_keys=False)
        
    print(f"Report generated: {out_path}")

if __name__ == "__main__":
    main()
