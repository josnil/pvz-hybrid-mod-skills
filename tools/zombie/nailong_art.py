# -*- coding: utf-8 -*-
"""奶龙僵尸 —— 素材管线（抠图 / 量测 / 图集 / 离线预览）。

输入（用户提供的三件素材）：
    C:/Users/yanxulin002/Pictures/奶龙.avif     站立全身（1152x1795 有效）
    C:/Users/yanxulin002/Pictures/奶龙笑.avif   大笑半身（1192x1370 有效）
    D:/啊这/.../奶龙笑_爱给网_aigei_com.mp3      大笑音频

输出（落 CACHE，供 build_zombie_nailong.py 同步进包）：
    cut_body.png        站立全身（透明底色）
    cut_laugh.png       大笑半身（透明底色）
    cut_legs.png        站立全身的「腿」子图（大笑姿势需要接腿）
    atlas.png           图集（3 个 media 横排）
    art_params.json     量测结果（缩放 / 锚点 / 图集矩形）
    preview_*.png       逐帧合成预览（纯离线，不改游戏）

━━━ 抠图判据 ━━━
素材是「棚拍白底 + 底部渐灰阴影 + 底边 3px 深色压条」。
背景特征 = **去饱和**（max-min 小）且 **亮**（max 大）；角色是饱和黄 / 深棕爪 / 绿眼。
⇒ 从四边泛洪（不是全图阈值），保住嘴里的白牙、眼白这些**被包住的**亮块。
底边 3px 深色压条先裁掉。
"""
from __future__ import annotations

import json
import os
import sys
from collections import deque

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache_nailong")
os.makedirs(CACHE, exist_ok=True)

SRC_BODY = r"C:/Users/yanxulin002/Pictures/奶龙.avif"
SRC_LAUGH = r"C:/Users/yanxulin002/Pictures/奶龙笑.avif"
SRC_AUDIO = r"D:/啊这/2819680957/FileRecv/枪械图片/识别结果/奶龙笑_爱给网_aigei_com.mp3"

BOTTOM_TRIM = 3          # 素材底边的深色压条
BG_DIST = 30             # 与「本行背景参考色」的 RGB 欧氏距离阈值

# ---- 画布规格（对齐内置 Chapter1/Normal 僵尸，见 art_params.json 的 calib） ----
CANVAS_H = 140.0         # 角色渲染高度（= 内置普通僵尸 Idle1 可见高 140.3）
GROUND_Y = 0.0           # 画布原点 = 脚底接地线
LEG_SPLIT_MIN = 0.55     # 「腿」子图搜索起点（占站立图高度的比例）
LAUGH_ANCHOR = 0.46      # 大笑图的「肚子最宽行」在站立图里的对应位置（占站立图高度比例）


# ------------------------------------------------------------------ 抠图
def cutout(im: Image.Image) -> Image.Image:
    """抠底。

    ★ 判据不能写「亮 + 去饱和」——素材底部是一层**渐变灰地面**（约 126,127,122），
      亮度低于任何合理阈值 ⇒ 会被当成前景，于是「底边整行不透明」。
    正解 = **逐行背景参考色**：白底棚拍图左右两侧永远是纯背景 ⇒
      取每行最左 6px / 最右 6px 的均值当该行背景色，按 RGB 欧氏距离判前景。
      这样「地面渐变」与「角色深棕爪子」自动分开（爪子饱和度差很大）。
    再叠加**从四边泛洪**（不是全图阈值）：保住嘴里的白牙 / 眼白这些被包住的亮块。
    """
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()

    # ---- 逐行背景参考色 ----
    row_bg = []
    for y in range(h):
        acc = [0, 0, 0]
        n = 0
        for x in list(range(0, 6)) + list(range(w - 6, w)):
            c = px[x, y]
            acc[0] += c[0]
            acc[1] += c[1]
            acc[2] += c[2]
            n += 1
        row_bg.append((acc[0] / n, acc[1] / n, acc[2] / n))

    def is_bg(x, y):
        c = px[x, y]
        b = row_bg[y]
        d = (c[0] - b[0]) ** 2 + (c[1] - b[1]) ** 2 + (c[2] - b[2]) ** 2
        if d <= BG_DIST * BG_DIST:
            return True
        # ★ 地面接触阴影是「去饱和灰 + 亮度略低于本行背景」的**径向渐变** ⇒
        #   单看「与本行参考色的距离」判不掉（渐变中心离边缘参考色很远）。
        #   加一条：**去饱和**且亮度接近本行背景 ⇒ 也算背景。
        #   角色最暗的爪子是 (145,84,31)（饱和度 0.79）⇒ 不会被误伤（实测口径）。
        mx, mn = max(c[0], c[1], c[2]), min(c[0], c[1], c[2])
        if mx > 0 and (mx - mn) <= 0.13 * mx:
            return abs(mx - max(b[0], b[1], b[2])) <= 55
        return False

    seen = bytearray(w * h)
    dq = deque()

    def push(x, y):
        if 0 <= x < w and 0 <= y < h and not seen[y * w + x] and is_bg(x, y):
            seen[y * w + x] = 1
            dq.append((x, y))

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)
    while dq:
        x, y = dq.popleft()
        push(x + 1, y)
        push(x - 1, y)
        push(x, y + 1)
        push(x, y - 1)

    out = im.copy()
    opx = out.load()
    for y in range(h):
        row = y * w
        for x in range(w):
            if seen[row + x]:
                r, g, b, _ = opx[x, y]
                opx[x, y] = (r, g, b, 0)

    # 去噪：清掉面积 < 40 的孤立不透明小块（压缩噪点 / 残留阴影碎片）
    comp = bytearray(w * h)
    for y0 in range(h):
        for x0 in range(w):
            if comp[y0 * w + x0] or opx[x0, y0][3] == 0:
                continue
            stack = [(x0, y0)]
            comp[y0 * w + x0] = 1
            blob = []
            while stack:
                x, y = stack.pop()
                blob.append((x, y))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and not comp[ny * w + nx] and opx[nx, ny][3] > 0:
                        comp[ny * w + nx] = 1
                        stack.append((nx, ny))
            if len(blob) < 40:
                for x, y in blob:
                    r, g, b, _ = opx[x, y]
                    opx[x, y] = (r, g, b, 0)

    # 边缘软化：邻接背景的不透明像素降 alpha，避免硬锯齿
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            if seen[y * w + x] or opx[x, y][3] == 0:
                continue
            nb = seen[(y - 1) * w + x] + seen[(y + 1) * w + x] + seen[y * w + x - 1] + seen[y * w + x + 1]
            if nb:
                r, g, b, a = opx[x, y]
                opx[x, y] = (r, g, b, max(110, a - 60 * nb // 4))
    return out


def load_cut(path: str) -> Image.Image:
    im = Image.open(path).convert("RGBA")
    if BOTTOM_TRIM:
        im = im.crop((0, 0, im.width, im.height - BOTTOM_TRIM))
    return cutout(im)


def trimmed(im: Image.Image):
    bb = im.getchannel("A").getbbox()
    assert bb, "抠图后没有不透明像素"
    return im.crop(bb), bb


def rowwise(im: Image.Image, y: int):
    """返回 (不透明像素数, xmin, xmax, 中心)；空行返回 (0, -1, -1, 0)。"""
    a = im.getchannel("A")
    xs = [x for x in range(im.width) if a.getpixel((x, y)) > 8]
    if not xs:
        return 0, -1, -1, 0.0
    return len(xs), min(xs), max(xs), (min(xs) + max(xs)) / 2.0


def row_runs(im: Image.Image, y: int):
    """该行的不透明「连续段」个数（用于找分腿行）。"""
    a = im.getchannel("A")
    runs = 0
    prev = False
    for x in range(im.width):
        cur = a.getpixel((x, y)) > 8
        if cur and not prev:
            runs += 1
        prev = cur
    return runs


def widest_row(im: Image.Image, y0: int, y1: int):
    best = (0, 0)
    for y in range(y0, y1):
        n, _, _, _ = rowwise(im, y)
        if n > best[0]:
            best = (n, y)
    return best[1], best[0]


def body_axis(im: Image.Image) -> float:
    """躯干中轴 x：取躯干段各行中心的**中位数**（对垂臂 / 伸脚不敏感）。"""
    h = im.height
    cs = []
    for y in range(int(h * 0.35), int(h * 0.85), 3):
        n, _, _, c = rowwise(im, y)
        if n > 0:
            cs.append(c)
    cs.sort()
    return cs[len(cs) // 2]


def crotch_row(im: Image.Image) -> int:
    """分腿行 = 从下往上，第一个「连续段数 >= 2」的行（脚底那一段）。"""
    h = im.height
    for y in range(int(h * 0.60), h - 1):
        if row_runs(im, y) >= 2:
            return y
    return int(h * 0.80)


def feather(img: Image.Image, top=0, bottom=0) -> Image.Image:
    """对上下边缘做线性 alpha 羽化，用来把「大笑半身」与「站立腿」的硬接缝化开。"""
    im = img.copy()
    a = im.getchannel("A")
    px = a.load()
    if top:
        for y in range(min(top, im.height)):
            k = y / float(top)
            for x in range(im.width):
                px[x, y] = int(px[x, y] * k)
    if bottom:
        for i in range(min(bottom, im.height)):
            y = im.height - 1 - i
            k = i / float(bottom)
            for x in range(im.width):
                px[x, y] = int(px[x, y] * k)
    im.putalpha(a)
    return im


def main():
    body, _ = trimmed(load_cut(SRC_BODY))
    laugh, _ = trimmed(load_cut(SRC_LAUGH))
    laugh = feather(laugh, bottom=30)
    body.save(os.path.join(CACHE, "cut_body.png"))
    laugh.save(os.path.join(CACHE, "cut_laugh.png"))

    bw, bh = body.size
    gw, gh = laugh.size

    # ---- 站立图量测 ----
    axis = body_axis(body)
    crotch = crotch_row(body)
    belly_y, belly_w = widest_row(body, int(bh * 0.15), int(bh * 0.62))
    head_y, head_w = widest_row(body, 0, int(bh * 0.18))
    print("站立 %dx%d  躯干轴 x=%.1f  分腿行 y=%d(%.1f%%)" % (bw, bh, axis, crotch, 100.0 * crotch / bh))
    print("     肚子最宽 %d @ y=%d(%.1f%%)  头最宽 %d @ y=%d" % (belly_w, belly_y, 100.0 * belly_y / bh, head_w, head_y))

    # ---- 腿子图（分腿行往上留 24px 重叠，横向覆盖双脚并集） ----
    top = max(0, crotch - 24)
    x0 = min(rowwise(body, y)[1] for y in range(top, bh) if rowwise(body, y)[0])
    x1 = max(rowwise(body, y)[2] for y in range(top, bh) if rowwise(body, y)[0])
    legs = body.crop((x0, top, x1 + 1, bh))
    legs = feather(legs, top=26)
    legs.save(os.path.join(CACHE, "cut_legs.png"))
    print("腿子图 %dx%d  从 (%d,%d) 切" % (legs.width, legs.height, x0, top))

    # ---- 大笑图量测 ----
    g_axis = body_axis(laugh)
    g_belly_y, g_belly_w = widest_row(laugh, int(gh * 0.20), int(gh * 0.85))
    g_head_y, g_head_w = widest_row(laugh, 0, int(gh * 0.30))
    print("大笑 %dx%d  躯干轴 x=%.1f  肚子最宽 %d @ y=%d(%.1f%%)  头最宽 %d @ y=%d"
          % (gw, gh, g_axis, g_belly_w, g_belly_y, 100.0 * g_belly_y / gh, g_head_w, g_head_y))

    # ---- 图集 ----
    hmax = max(bh, gh, legs.height)
    order = [("nailong_body.png", body), ("nailong_laugh.png", laugh), ("nailong_legs.png", legs)]
    rects, x = {}, 0
    for name, img in order:
        rects[name] = [x, 0, img.width, img.height]
        x += img.width + 2
    atlas = Image.new("RGBA", (x - 2, hmax), (0, 0, 0, 0))
    for name, img in order:
        atlas.paste(img, (rects[name][0], 0))
    atlas.save(os.path.join(CACHE, "atlas.png"))

    scale = CANVAS_H / bh
    params = {
        "atlas": {"w": atlas.width, "h": atlas.height},
        "media": [{"name": n, "rect": rects[n]} for n, _ in order],
        "canvas_h": CANVAS_H,
        "scale": scale,
        "body": {
            "w": bw, "h": bh, "axis_x": axis, "bottom_y": float(bh),
            "crotch_y": float(crotch), "belly_y": float(belly_y), "belly_w": belly_w,
            "head_w": head_w,
        },
        "legs": {"rect_x": float(x0), "rect_y": float(top), "w": legs.width, "h": legs.height},
        "laugh": {
            "w": gw, "h": gh, "axis_x": g_axis, "belly_y": float(g_belly_y),
            "belly_w": g_belly_w, "head_w": g_head_w,
            "scale_ratio": float(belly_w) / float(g_belly_w),
        },
        "calib": {
            "target_h_canvas": CANVAS_H,
            "ground_canvas_y": GROUND_Y,
            "offset": [0.0, 38.0],
            "note": "offset=(0,38) ⇒ 画布(0,0) 落在角色空间(0,38)；内置僵尸 offset=-80 时脚底画布 y=118 ⇒ 角色 y=38，ShadowSprite y=36",
        },
    }
    json.dump(params, open(os.path.join(CACHE, "art_params.json"), "w", encoding="utf8"), indent=1, ensure_ascii=False)
    print("\n图集 %dx%d  scale=%.6f" % (atlas.width, atlas.height, scale))
    print("落盘:", CACHE)


def render_pose(kind: str, scale: float, zoom: int = 4):
    """把「站立 / 大笑」两种姿势渲到同一画布坐标系（脚底 y=0，躯干轴 x=0）。"""
    body = Image.open(os.path.join(CACHE, "cut_body.png")).convert("RGBA")
    laugh = Image.open(os.path.join(CACHE, "cut_laugh.png")).convert("RGBA")
    legs = Image.open(os.path.join(CACHE, "cut_legs.png")).convert("RGBA")
    p = json.load(open(os.path.join(CACHE, "art_params.json"), encoding="utf8"))
    bh, bw = p["body"]["h"], p["body"]["w"]
    axis = p["body"]["axis_x"]
    bh_scale = p["scale"]
    belly_y = p["body"]["belly_y"]
    g_axis = p["laugh"]["axis_x"]
    g_belly_y = p["laugh"]["belly_y"]
    g_ratio = p["laugh"]["scale_ratio"]

    W, H = int(130 * zoom), int(185 * zoom)      # 画布像素（画布单位 × zoom）
    canvas = Image.new("RGBA", (W, H), (28, 30, 36, 255))

    def to_screen(cx, cy):
        return (W / 2 + cx * zoom, H - 30 * zoom + cy * zoom)

    def paste(img, s, ox, oy):
        w2, h2 = max(1, int(img.width * s * zoom)), max(1, int(img.height * s * zoom))
        im2 = img.resize((w2, h2), Image.LANCZOS)
        sx, sy = to_screen(ox, oy)
        canvas.alpha_composite(im2, (int(sx), int(sy)))

    # 站立：x = (px-axis)*bh_scale, y = (py-bh)*bh_scale
    if kind == "stand":
        paste(body, bh_scale, -axis * bh_scale, -bh * bh_scale)
    else:
        s2 = bh_scale * g_ratio
        top = -belly_y * bh_scale - (g_belly_y) * s2     # 让「肚子最宽行」对齐站立图的那一行
        # 腿：先画（在下层）
        lx = p["legs"]["rect_x"]
        paste(legs, bh_scale, -(axis - lx) * bh_scale, (p["legs"]["rect_y"] - bh) * bh_scale)
        # 大笑半身：后画（压在上面）
        paste(laugh, s2, -g_axis * s2, top)
    return canvas


def preview(scale: float):
    a = render_pose("stand", scale)
    b = render_pose("laugh", scale)
    sheet = Image.new("RGBA", (a.width + b.width + 8, max(a.height, b.height)), (12, 12, 14, 255))
    sheet.alpha_composite(a, (0, 0))
    sheet.alpha_composite(b, (a.width + 8, 0))
    # 叠加图：站立=红通道，大笑=青通道
    ov = Image.new("RGB", (a.width, a.height), (0, 0, 0))
    aa = a.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    ba = b.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    ov = Image.merge("RGB", (aa, ba, ba))
    sheet.alpha_composite(ov.convert("RGBA"), (0, 0)) if False else None
    out = os.path.join(CACHE, "preview_pose.png")
    sheet.convert("RGB").save(out)
    print("preview ->", out)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--preview":
        preview(float(sys.argv[2]) if len(sys.argv) > 2 else 4)
    else:
        main()
