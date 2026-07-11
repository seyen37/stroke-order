"""Phase 5ca — doodle_engine.js × Python parity 驗證（Python 側）。

用法：
    node scripts/verify_doodle_parity.cjs     # 先產 /tmp/parity_js.json
    python scripts/verify_doodle_parity.py    # 比對

比對三件事：
1. 裁切框（auto_crop）尺寸與角點值完全相等
2. SVG 線段/圓點數量完全相等、viewBox/實體 mm 完全相等
3. 全部幾何座標差 <= 0.011 mm（toFixed 與 %.2f 的半值進位差）
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from stroke_order.exporters.doodle import (  # noqa: E402
    auto_crop_image, render_doodle_svg,
)

# ---- Image A（與 cjs 相同的程序合成） ----
W, H = 160, 120
a = np.full((H, W, 3), 255, dtype=np.uint8)
for y in range(H):
    for x in range(W):
        v = None
        if 30 <= x < 60 and 20 <= y < 50:
            v = 0
        elif (x - 110) ** 2 + (y - 60) ** 2 <= 625:
            v = 128
        elif x - y == 10 and 10 <= x < 80:
            v = 0
        elif 90 <= y < 110:
            v = (x * 255) // 159
        if v is not None:
            a[y, x] = v
svg_py = render_doodle_svg(Image.fromarray(a, "RGB"), canvas_width_mm=150,
                           threshold=50, line_color="#222", line_width=0.4)

# ---- Image B（裁切框） ----
W2, H2 = 200, 150
b = np.full((H2, W2), 255, dtype=np.uint8)
for y in range(H2):
    for x in range(W2):
        frame = ((y in (30, 31, 118, 119) and 40 <= x < 160) or
                 (x in (40, 41, 158, 159) and 30 <= y < 120))
        if frame:
            b[y, x] = 0
        elif 80 <= x < 120 and 60 <= y < 90:
            b[y, x] = 50
cropped = auto_crop_image(Image.fromarray(b, "L"),
                          trim_whitespace=True, remove_border=True)

js = json.load(open("/tmp/parity_js.json"))
jsbox = js["box"]
js_size = (jsbox[2] - jsbox[0], jsbox[3] - jsbox[1])
ok_box = (js_size == cropped.size and
          cropped.getpixel((0, 0)) == int(b[jsbox[1], jsbox[0]]))


def parse(svg: str):
    lines = re.findall(
        r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)"/>',
        svg)
    circs = re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"',
                       svg)
    hdr = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', svg).groups()
    return ([tuple(map(float, t)) for t in lines],
            [tuple(map(float, t)) for t in circs],
            tuple(map(float, hdr)))


L1, C1, H1 = parse(svg_py)
L2, C2, H2_ = parse(js["svg"])
ok_hdr = all(abs(x - y) < 1e-9 for x, y in zip(H1, H2_))
ok_cnt = (len(L1) == len(L2) and len(C1) == len(C2))
ok_geo = ok_cnt and all(
    abs(u - v) <= 0.011
    for p, q in zip(L1 + C1, L2 + C2) for u, v in zip(p, q))

print("box    parity:", "PASS" if ok_box else f"FAIL {js_size} vs {cropped.size}")
print(f"counts        : py lines={len(L1)} circles={len(C1)} / "
      f"js lines={len(L2)} circles={len(C2)}")
print("header parity:", "PASS" if ok_hdr else f"FAIL {H1} vs {H2_}")
print("geom   parity:", "PASS" if ok_geo else "FAIL")
sys.exit(0 if (ok_box and ok_hdr and ok_geo) else 1)
