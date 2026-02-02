import sys, os
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance

def main():
    if len(sys.argv) < 3:
        print("usage: pdf_to_images.py <input.pdf> <out_dir> [dpi=200] [goal=clean|line]") # Updated usage
        sys.exit(2)
    pdf_path = sys.argv[1]
    out_dir = sys.argv[2]
    dpi = int(sys.argv[3]) if len(sys.argv) >= 4 else 200
    goal = sys.argv[4] if len(sys.argv) >= 5 else "" # Added goal argument

    # Create artifact folder
    os.makedirs(out_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    # Render loop
    for i, page in enumerate(doc):
        # 2x scale for quality (approx 150-300 dpi depending on base)
        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
        
        # Convert to Pillow for processing
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        
        # S1: Clean Plan Logic
        if "clean" in goal.lower() or "line" in goal.lower():
            # Convert to grayscale
            img = img.convert("L")
            
            if "line" in goal.lower():
                # High contrast threshold for clean lines (Line Art)
                # Simple adaptive-like threshold
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(2.0)
                img = img.point(lambda x: 0 if x < 200 else 255, '1')
            else:
                # General cleanup (Auto-Enhance)
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.5)
        
        out_name = f"plan_clean_{i+1:03d}.png" if "clean" in goal else f"page_{i+1:03d}.png"
        img.save(os.path.join(out_dir, out_name))
        print(f"Rendered: {out_name}")

if __name__ == "__main__":
    main()
