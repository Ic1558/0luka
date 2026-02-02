import sys, os, textwrap
import fitz
from datetime import datetime

HTML_TMPL = """<!doctype html>
<html>
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>{title}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial; margin: 24px; line-height: 1.45; }}
h1 {{ margin: 0 0 8px 0; }}
.meta {{ color: #666; margin-bottom: 18px; }}
.grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }}
.card {{ border: 1px solid #ddd; border-radius: 12px; padding: 14px; }}
pre {{ white-space: pre-wrap; word-break: break-word; font-size: 12px; background: #f7f7f7; padding: 12px; border-radius: 10px; }}
@media (max-width: 900px) {{ .grid {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="meta">Generated: {ts} • Source: {src}</div>
<div class="grid">
  <div class="card">
    <h3>Key Bullets (heuristic)</h3>
    <ul>
      {bullets}
    </ul>
  </div>
  <div class="card">
    <h3>Extracted Text (first {nchars} chars)</h3>
    <pre>{excerpt}</pre>
  </div>
</div>
</body>
</html>
"""

def main():
    if len(sys.argv) < 3:
        print("usage: pdf_to_visual_summary.py <input.pdf> <out_html>")
        sys.exit(2)

    pdf_path, out_html = sys.argv[1], sys.argv[2]
    doc = fitz.open(pdf_path)

    chunks = []
    for page in doc:
        t = page.get_text("text") or ""
        t = t.strip()
        if t: chunks.append(t)
    full = "\n\n".join(chunks)

    lines = [ln.strip() for ln in full.splitlines() if ln.strip()]
    candidates = []
    for ln in lines:
        if len(ln) <= 90 and (ln[:2].isdigit() or ln.startswith(("-", "•")) or ln.isupper()):
            candidates.append(ln.lstrip("-• ").strip())
        elif 12 <= len(ln) <= 70 and ln.endswith(":"):
            candidates.append(ln[:-1].strip())
            
    seen = set()
    bullets = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            bullets.append(c)
        if len(bullets) >= 10: break
    if not bullets:
        for ln in lines[:10]: bullets.append(ln[:90])

    bullets_html = "\n".join([f"<li>{b}</li>" for b in bullets])
    nchars = 2500
    excerpt = (full[:nchars] + ("…" if len(full) > nchars else ""))
    title = os.path.basename(pdf_path)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = HTML_TMPL.format(
        title=title, ts=ts, src=pdf_path, bullets=bullets_html, 
        excerpt=excerpt.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;"),
        nchars=nchars
    )

    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    print(out_html)

if __name__ == "__main__":
    main()
