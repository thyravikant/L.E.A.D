"""Generate a synthetic, degraded Jamabandi-style scan for the demo.

Run from the project root:  python samples/make_sample.py
Everything on the page is fictional demo data.
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent / "sample_jamabandi.png"
W, H = 1700, 1100

ROWS = [  # khewat, khasra, owner, area (K-M-S)
    ("118", "1234/2", "Harbans Singh", "8-4-0"),
    ("118", "1235", "Harbans Singh", "5-0-0"),
    ("121", "1240/1", "Gurmeet Kaur", "3-12-4"),
    ("121", "1241", "Balwinder Singh", "10-0-0"),
    ("125", "1250", "Sukhdev Singh", "2-6-0"),
    ("128", "1257/3", "Jaswant Kaur", "4-0-0"),
]


def font(size, bold=False):
    names = ["DejaVuSerif-Bold.ttf" if bold else "DejaVuSerif.ttf", "times.ttf", "Times New Roman.ttf",
             "LiberationSerif-Regular.ttf"]
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    img = Image.new("RGB", (W, H), (236, 224, 196))
    d = ImageDraw.Draw(img)
    ink = (52, 40, 30)
    d.text((W // 2, 70), "JAMABANDI  2019-20", font=font(44, True), fill=ink, anchor="mm")
    d.text((W // 2, 130), "Village: Sample Pur     Tehsil: Rupnagar     (demo data)", font=font(28), fill=ink, anchor="mm")

    x = [90, 330, 690, 1330, 1610]  # column rules
    top, row_h = 190, 100
    heads = ["Khewat", "Khasra", "Owner", "Area (K-M-S)"]
    for i, h in enumerate(heads):
        d.text(((x[i] + x[i + 1]) // 2, top + 40), h, font=font(30, True), fill=ink, anchor="mm")
    n = len(ROWS)
    for r in range(n + 2):
        y = top + r * row_h if r == 0 else top + 80 + (r - 1) * row_h
        d.line([(x[0], y), (x[-1], y)], fill=ink, width=3)
    d.line([(x[0], top + 80 + n * row_h)] * 2, fill=ink)
    y_end = top + 80 + n * row_h
    for xi in x:
        d.line([(xi, top), (xi, y_end)], fill=ink, width=3)
    for r, row in enumerate(ROWS):
        yc = top + 80 + r * row_h + row_h // 2
        for i, cell in enumerate(row):
            d.text((x[i] + 22, yc), cell, font=font(36), fill=ink, anchor="lm")
    d.text((90, y_end + 60), "Attested: Patwari Halqa 14", font=font(26), fill=ink, anchor="lm")

    arr = np.array(img).astype(np.float32)
    rng = np.random.default_rng(7)

    # uneven fading + vignette
    yy, xx = np.mgrid[0:H, 0:W]
    fade = 1.0 - 0.18 * (xx / W) - 0.10 * np.sin(yy / 180.0)
    arr = 236 - (236 - arr) * fade[..., None]
    # stains
    for _ in range(5):
        cx, cy, rad = rng.integers(0, W), rng.integers(0, H), rng.integers(80, 220)
        mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < rad ** 2
        arr[mask] *= 0.93
    # fold shadow
    arr[:, 840:850] *= 0.82
    # noise + blur
    arr += rng.normal(0, 7, arr.shape)
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    arr = cv2.GaussianBlur(arr, (3, 3), 0)

    # slight skew
    m = cv2.getRotationMatrix2D((W / 2, H / 2), 1.6, 1.0)
    arr = cv2.warpAffine(arr, m, (W, H), borderMode=cv2.BORDER_REPLICATE)
    cv2.imwrite(str(OUT), cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))
    print("wrote", OUT)


if __name__ == "__main__":
    sys.exit(main())
