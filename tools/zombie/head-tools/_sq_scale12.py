# -*- coding: utf-8 -*-
r"""_sq_scale12.py —— 第十二轮「头的模型改为**现在的 1.2 倍**」的**尺寸前后对照图**。

口径（为什么这样能当证据）：
  · 三格全部来自同一个离线合成渲染器 `_sq_preview.py`，**同一 box / 同一 k / 同一 shift
    （0, -20.1565）**，只有 `--mult` 不同（2.0 vs 2.4）
    ⇒ 三格**像素坐标系完全一致**，可以直接叠同一套标注 / 直接叠轮廓。
  · 第 1、2 格：BEFORE(2.0×) / AFTER(2.4×)，画**解析解出的锚点十字**
        target (-10.2002, -35.1001) + shift (0, -20.1565)  ⇒  锚点 (-10.2002, -55.2566)
    十字在两格里都落在头块上、且第 2 格头明显更大 ⇒ 证明「**以该点为轴原地放大 1.2 倍**」。
  · 第 3 格：把 **BEFORE 的轮廓**叠到 AFTER 上。
    ⚠️ 关键便利：`_sq_preview.py` 落盘的是 **RGBA（透明底）** ⇒ 轮廓可以直接取 **alpha 通道**
    （`MinFilter(3)` 做腐蚀、相减得边界），**不需要任何启发式取块**。
    ⚠️ 不要用「最靠上的橙色大块」这类启发式量尺寸：头的火焰花瓣是**逐帧动画**，
    两倍率下会取到**不同的块**（实测给出 1.19 这种假比值）——见铁律 30。
  · 尺寸比用**解析值**报（`head_scale 0.9 → 1.08` ⇒ 1.2000）。

用法: python .cache/_sq_scale12.py <out.png>
（必须用带 PIL 的解释器：envs/default/Scripts/python.exe）
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageChops, ImageDraw, ImageFilter  # noqa: E402

PREVIEW = os.path.join(HERE, '_sq_preview.py')
BOX = '-90,-160,90,70'
K = 2.0
SHIFT = (0.0, -20.1565)
MULTS = (2.0, 2.4)
TARGET = (-10.2002, -35.1001)          # 身体 L19 并集 bbox 中心（= 原点锚）
ANCHOR = (TARGET[0] + SHIFT[0], TARGET[1] + SHIFT[1])
BG = (238, 238, 243)
OUTLINE_RGB = (225, 40, 140)
PAD = 22
HEADER = 36


def render(mult):
    out = os.path.join(HERE, '_sc12_m%s.png' % ('%g' % mult).replace('.', '_'))
    cmd = [sys.executable, PREVIEW, '--out', out, '--mult', '%g' % mult,
           '--no-aura', '--shift=%g,%g' % SHIFT, '--box=' + BOX, '--k', '%g' % K]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
    return out


def flatten(rgba):
    return Image.alpha_composite(Image.new('RGBA', rgba.size, BG + (255,)), rgba).convert('RGB')


def outline_of(rgba, thr=32):
    """轮廓 = alpha 掩码减腐蚀 3×3，再膨胀 3×3 提粗（纯几何，无启发式）。"""
    m = rgba.getchannel('A').point(lambda v: 255 if v > thr else 0, 'L')
    er = m.filter(ImageFilter.MinFilter(3))
    edge = ImageChops.subtract(m, er)
    return edge.filter(ImageFilter.MaxFilter(3))


def to_px(pt):
    x0, y0 = [float(v) for v in BOX.split(',')[:2]]
    return ((pt[0] - x0) * K, (pt[1] - y0) * K)


def main():
    out = sys.argv[1]
    raws = [Image.open(render(m)).convert('RGBA') for m in MULTS]
    scales = [round(0.45 * m, 4) for m in MULTS]
    for m, s, im in zip(MULTS, scales, raws):
        sys.stdout.write('mult=%.2f  head_scale=%.4f  %dx%d\n' % (m, s, im.size[0], im.size[1]))
    sys.stdout.write('尺寸比（解析）= %.4f / %.4f = %.4f\n'
                     % (scales[1], scales[0], scales[1] / scales[0]))

    # 第 3 格：BEFORE 轮廓 叠在 AFTER 上
    ov = flatten(raws[1]).copy()
    ov.paste(OUTLINE_RGB, (0, 0), outline_of(raws[0]))
    panels = [flatten(raws[0]), flatten(raws[1]), ov]
    labels = [('BEFORE   mult=%.1fx   head_scale=%.2f' % (MULTS[0], scales[0]),
               'anchored head centre = crosshair'),
              ('AFTER    mult=%.1fx   head_scale=%.2f' % (MULTS[1], scales[1]),
               'anchored head centre = crosshair'),
              ('OVERLAY  BEFORE-silhouette on AFTER',
               'magenta edge = the 2.0x head/body outline')]

    ax, ay = to_px(ANCHOR)
    sys.stdout.write('锚点 %s（显示）⇒ 图像 (%.1f, %.1f)\n' % (ANCHOR, ax, ay))

    w, h = panels[0].size
    W = w * len(panels) + PAD * (len(panels) + 1)
    H = h + HEADER + PAD + 22
    cv = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(cv)
    x = PAD
    for i, im in enumerate(panels):
        cv.paste(im, (x, HEADER))
        d.text((x + 2, 6), labels[i][0], fill=(20, 20, 20))
        d.text((x + 2, 20), labels[i][1], fill=(90, 90, 90))
        if i < 2:
            yl = int(round(HEADER + ay))
            xl = int(round(x + ax))
            d.line([(x, yl), (x + w, yl)], fill=(220, 30, 30), width=2)
            d.line([(xl, HEADER), (xl, HEADER + h)], fill=(0, 170, 220), width=2)
        x += w + PAD
    d.text((PAD, H - 17),
           'RED/CYAN crosshair = anchored head centre (-10.2002, -55.2566)    '
           'all panels share box/k/shift; only --mult differs',
           fill=(60, 60, 60))
    cv.save(out)
    sys.stdout.write('-> %s  %s\n' % (out, cv.size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
