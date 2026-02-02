import sys, os
from PIL import Image, ImageOps, ImageDraw, ImageFont

def main():
    if len(sys.argv) < 4:
        print("usage: image_to_banner.py <input_image> <output_image> <title> [subtitle]")
        sys.exit(2)

    inp, outp, title = sys.argv[1], sys.argv[2], sys.argv[3]
    subtitle = sys.argv[4] if len(sys.argv) >= 5 else ""

    img = Image.open(inp).convert("RGB")
    w, h = img.size

    # 16:9 banner target
    tw = max(1600, w)
    th = int(tw * 9 / 16)

    # Fit source into banner with blurred background
    from PIL import ImageFilter
    bg = img.resize((tw, th))
    bg = bg.filter(ImageFilter.GaussianBlur(radius=18))

    fg = ImageOps.contain(img, (int(tw*0.86), int(th*0.86)))
    canvas = bg.copy()
    fx, fy = fg.size
    canvas.paste(fg, ((tw-fx)//2, (th-fy)//2))

    # Text overlay block
    draw = ImageDraw.Draw(canvas)
    pad = int(tw * 0.05)
    box_h = int(th * 0.22)
    y0 = th - box_h - pad

    overlay = Image.new("RGB", (tw - 2*pad, box_h), (0,0,0))
    overlay = ImageOps.colorize(ImageOps.grayscale(overlay), black=(0,0,0), white=(0,0,0))
    overlay = overlay.convert("RGBA")
    overlay.putalpha(140)
    canvas_rgba = canvas.convert("RGBA")
    canvas_rgba.alpha_composite(overlay, (pad, y0))

    draw = ImageDraw.Draw(canvas_rgba)

    # Attempt common fonts
    font_candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    title_fs = max(26, int(tw * 0.035))
    sub_fs   = max(18, int(tw * 0.02))
    
    title_font = ImageFont.load_default()
    sub_font = ImageFont.load_default()
    
    for f in font_candidates:
        if os.path.exists(f):
            try:
                title_font = ImageFont.truetype(f, size=title_fs)
                sub_font = ImageFont.truetype(f, size=sub_fs)
                break
            except: continue

    tx = pad + int(tw*0.03)
    ty = y0 + int(box_h*0.18)
    draw.text((tx, ty), title, font=title_font, fill=(255,255,255,255))

    if subtitle.strip():
        draw.text((tx, ty + int(box_h*0.45)), subtitle, font=sub_font, fill=(220,220,220,255))

    os.makedirs(os.path.dirname(outp) or ".", exist_ok=True)
    canvas_rgba.convert("RGB").save(outp, quality=92)
    print(outp)

if __name__ == "__main__":
    main()
