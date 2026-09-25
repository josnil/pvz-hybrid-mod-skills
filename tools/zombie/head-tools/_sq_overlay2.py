# -*- coding: utf-8 -*-
r"""_sq_overlay2.py —— 把「用户示例图」与「游戏内截图」按**身体**对齐后叠加，
直接读出「头该往哪个方向、挪多少像素」。只读/可复跑。

对齐（只用**身体**像素，与头的大小/位置无关）：
  · 尺度 s = 头宽(实机) / 头宽(示例)。两图的头是**同一素材同一 2.0 倍** ⇒ 头宽就是
    共同比例尺（实测 64 vs 62，差 3.2%）。
    ⚠️ **不能用裤高**：实机截图的裤子被**脚底光环截断**（白块只到 y=123，真腿到 ~150）
    ⇒ 裤高跨图不可比（这正是前一版把 s 算成 1.06 的原因）。
  · 平移：把示例图（缩放后）的**裤腰**（白块最靠上那行的 y 与其 x 中心）对齐到实机截图的裤腰。
  · 两图都置灰后做「红/青」叠加：**只能红** = 示例图独有（**目标**）；
    只能青 = 实机截图独有（**现状**）。头部的红/青错位量 = **要移动的像素数**。

量化：头块（画面里**最靠上的橙色大块**，见 `pick_head` 的说明）中心在两图中的 y 差。

⚠️ 头块判据的一致性：实机截图里**向上火焰**更张扬、示例图里**向下花瓣**更多
   ⇒ 单看「头顶」或「头底」都会偏；**取 bbox 中心**对上下不对称最不敏感。

用法：
  python .cache/_sq_overlay2.py .cache/_ov2.png            # 出图 + 打印位移
  python .cache/_sq_overlay2.py .cache/_ov2.png --no-lines # 不画参考线
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw  # noqa: E402

GAME = os.path.join(HERE, '_ref2_QQ_1790302860709.png')   # 游戏内实机截图（现状）
REF = os.path.join(HERE, '_ref_QQ_1790301323306.png')     # 用户示例图（目标）

# 「显示空间」的头块宽度（px），由 `.cache/_sq_preview.py` 离线渲染量出：
#   mult=2.0 --no-aura --k 2 ⇒ 头块 bbox 宽 121 图px ⇒ 121/2 = 60.5 显示px
HEAD_W_DISP = 60.5
GUIDE_STEP = 10


# ------------------------------------------------------------------ 掩码
def near_white(p):
    return min(p) >= 165 and (max(p) - min(p)) <= 55


def mane(p):
    return p[0] >= 150 and (p[0] - p[1]) >= 70 and (p[0] - p[2]) >= 80


def yellow(p):
    """脸 / 王冠的黄色。⚠️ 黄上衣同色，但只在本函数**限定的头块 bbox 内**取块。"""
    return p[0] >= 190 and p[1] >= 140 and p[2] <= 150 and (p[0] - p[1]) >= 30


def blobs(im, pred, min_px=30, box=None):
    w, h = im.size
    px = im.load()
    seen = bytearray(w * h)
    x0, y0, x1, y1 = box if box else (0, 0, w, h)
    out = []
    for yy in range(y0, y1):
        for xx in range(x0, x1):
            i0 = yy * w + xx
            if seen[i0] or not pred(px[xx, yy]):
                continue
            stack = [(xx, yy)]
            seen[i0] = 1
            pts = []
            while stack:
                x, y = stack.pop()
                pts.append((x, y))
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        nx, ny = x + dx, y + dy
                        if x0 <= nx < x1 and y0 <= ny < y1:
                            j = ny * w + nx
                            if not seen[j] and pred(px[nx, ny]):
                                seen[j] = 1
                                stack.append((nx, ny))
            if len(pts) >= min_px:
                xs = [q[0] for q in pts]
                ys = [q[1] for q in pts]
                out.append((len(pts), (min(xs), min(ys), max(xs) + 1, max(ys) + 1)))
    out.sort(key=lambda t: t[0], reverse=True)
    return out


def face_crown(im, hbox, min_px=40, max_n=6):
    """头块 bbox 内的黄色块（= 脸 / 王冠）。

    ★ 这是**刚性**锚点：脸与王冠随整个头平移，**不随火焰帧变形** ⇒ 比「头块中心」
      （含火焰，受帧影响上下不对称）可靠得多。实测两图一致地给出：
        第 1 大块 = 脸（宽 > 高 约 2:1），第 2 大块 = 王冠金色环（~13x15）。
    """
    return blobs(im, yellow, min_px, box=hbox)[:max_n]


def pick_head(im, min_px=150):
    """头 = 掩码里**位置最靠上**的大块。

    ⚠️ 不能用「最大块」：实机截图里**脚底光环** n=6701 > 花瓣 n=1575。
    """
    bs = [b for b in blobs(im, mane, 30) if b[0] >= min_px]
    if not bs:
        return None
    bs.sort(key=lambda t: (t[1][1], -t[0]))
    return bs[0]


def pick_pants(im, min_px=300):
    """裤子 = 白块里**最靠下**的大块（用 y1 排序）。

    ⚠️ 不能用「最大块」：离线渲染图里**白手套与白裤连通成一块**，最大块的 y0 落在
    手套上而不是裤腰；实机截图里**白鞋**比裤子更靠下但很小（n=49）⇒ 用 min_px 滤掉。
    """
    bs = [b for b in blobs(im, near_white, 60) if b[0] >= min_px]
    if not bs:
        return None
    bs.sort(key=lambda t: -t[1][3])
    return bs[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('out')
    ap.add_argument('--no-lines', action='store_true')
    ap.add_argument('--head-w-disp', type=float, default=HEAD_W_DISP)
    a = ap.parse_args()

    g = Image.open(GAME).convert('RGB')
    r = Image.open(REF).convert('RGB')

    gh, rh = pick_head(g), pick_head(r)
    gp, rp = pick_pants(g), pick_pants(r)
    if not (gh and rh and gp and rp):
        sys.stderr.write('找不到头块或裤子块\n')
        return 1
    gw, rw = gh[1][2] - gh[1][0], rh[1][2] - rh[1][0]
    s = gw / float(rw)
    sys.stdout.write('头块  实机 %s 宽 %d   |   示例 %s 宽 %d\n' % (gh[1], gw, rh[1], rw))
    sys.stdout.write('裤子  实机 %s       |   示例 %s\n' % (gp[1], rp[1]))
    sys.stdout.write('★ 尺度 s = 头宽比 = %d/%d = %.4f  （头是同一素材 2.0 倍 ⇒ 头宽即比例尺）\n'
                     % (gw, rw, s))

    r2 = r.resize((max(1, int(round(r.width * s))), max(1, int(round(r.height * s)))),
                  Image.LANCZOS)
    # 把示例图的「裤腰」对齐到实机的「裤腰」（y 用白块顶，x 用白块中心）
    gpx = (gp[1][0] + gp[1][2]) / 2.0
    rpx = (rp[1][0] + rp[1][2]) / 2.0 * s
    dx = int(round(gpx - rpx))
    dy = int(round(gp[1][1] - rp[1][1] * s))
    sys.stdout.write('示例图缩放后 %s，平移 (%d, %d) 使裤腰重合（实机裤腰 y=%d）\n'
                     % (r2.size, dx, dy, gp[1][1]))

    W = max(g.width, r2.width + max(0, dx)) + 60
    H = max(g.height, r2.height + max(0, dy)) + 60
    cg = Image.new('RGB', (W, H), (0, 0, 0))
    cr = Image.new('RGB', (W, H), (0, 0, 0))
    cg.paste(g, (0, 0))
    cr.paste(r2, (dx, dy))

    # ---- 统一坐标系下的头部锚点 -------------------------------------
    scale_fb = gw / a.head_w_disp        # 截图px → 显示px

    def ref_to_game(cx, cy):
        """示例图坐标 → 实机截图坐标（缩放 s + 平移 dx,dy）。"""
        return (cx * s + dx, cy * s + dy)

    def cen(b):
        return ((b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0)

    gf, rf = face_crown(g, gh[1]), face_crown(r, rh[1])
    rows = [('头块中心(含火焰·仅参考)', rh[1], gh[1], False)]
    if gf and rf:
        rows.append(('脸中心(刚性★)', rf[0][1], gf[0][1], True))
    if len(gf) > 1 and len(rf) > 1:
        rows.append(('王冠中心(刚性★)', rf[1][1], gf[1][1], True))
    sys.stdout.write('\n★ 统一坐标系下的头部锚点（Δy > 0 ⇒ 实机头更低）：\n')
    sys.stdout.write('   %-24s %-16s %-16s %9s %10s\n'
                     % ('判据', '目标(示例)', '现状(实机)', 'Δy(截图)', 'Δy(显示)'))
    rigid = []
    for name, rb, gb_, is_rigid in rows:
        rcx, rcy = ref_to_game(*cen(rb))
        gcx, gcy = cen(gb_)
        sys.stdout.write('   %-24s (%6.1f,%6.1f) (%6.1f,%6.1f) %+9.2f %+10.2f\n'
                         % (name, rcx, rcy, gcx, gcy, gcy - rcy, (gcy - rcy) / scale_fb))
        if is_rigid:
            rigid.append(gcy - rcy)
    if not rigid:
        sys.stderr.write('没有刚性判据可用\n')
        return 1
    ddy = sum(rigid) / float(len(rigid))
    dy_disp = ddy / scale_fb
    sys.stdout.write('   头宽 %d 截图px / %.2f 显示px ⇒ 换算系数 %.4f\n'
                     % (gw, a.head_w_disp, scale_fb))
    sys.stdout.write('★ 采用值 = 刚性判据（脸/王冠）均值：Δy = %+.2f 截图px = %+.2f 显示px\n'
                     % (ddy, dy_disp))
    sys.stdout.write('   ⇒ 实机头比目标**低** %.2f 显示px，需**上移**\n' % dy_disp)
    sys.stdout.write('   ⇒ 反解新 head_offset：\n'
                     '        python .cache/_sq_head_place.py --queen-shift=0,%.4f\n' % (-dy_disp))

    # ---- 红/青叠加 ---------------------------------------------------
    lg = cg.convert('L')
    lr = cr.convert('L')
    ov = Image.merge('RGB', (lr, lg, lg))
    d = ImageDraw.Draw(ov)
    if not a.no_lines:
        for y in range(0, H, GUIDE_STEP):
            five = (y // GUIDE_STEP) % 5 == 0
            d.line([(0, y), (W, y)], fill=(255, 255, 0) if five else (70, 70, 0))
            if five:
                d.text((2, y + 1), '%d' % y, fill=(255, 255, 0))
    # 锚点水平线：示例（目标）= 红，实机（现状）= 绿；刚性判据用亮色
    for name, rb, gb_, is_rigid in rows:
        _rcx, rcy = ref_to_game(*cen(rb))
        _gcx, gcy = cen(gb_)
        d.line([(0, int(round(rcy))), (W, int(round(rcy)))],
               fill=(255, 40, 40) if is_rigid else (150, 40, 40))
        d.line([(0, int(round(gcy))), (W, int(round(gcy)))],
               fill=(40, 255, 40) if is_rigid else (40, 150, 40))
    d.text((2, 2), 'RED=ref(target)  GREEN=game(now)', fill=(255, 255, 255))
    ov.save(a.out)
    sys.stdout.write('-> %s  %s\n' % (a.out, ov.size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
