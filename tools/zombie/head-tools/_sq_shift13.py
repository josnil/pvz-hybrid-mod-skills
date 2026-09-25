# -*- coding: utf-8 -*-
r"""_sq_shift13.py —— 第十三轮「两个头一起**往右上方移一点**（右上各 12px）」的前后对照图。

四格：女王·移前 / 女王·移后 / 舞者·移前 / 舞者·移后。
每一格都用**解析解出的锚点**（`target + shift` = 头块落点中心）画十字：
  · **亮色十字** = 本格自己的位置；**灰色虚线十字** = 对面那格的位置
  ⇒ 同一格里就能看出「动了 12px、方向右上」。

口径：
  · 渲染全部走 `.cache/_sq_preview.py`（`--char queen|dancer`，第十三轮新加的角色开关），
    **按绝对 `--head-scale`**（= 生成器 `head_scale`）指定尺寸 ——
    ⚠️ 别用 `--mult`：它是「相对基准 **0.45**」的倍率，而 0.45 是**女王包的历史口径**，
    舞者 `head_scale 1.0` 写成 `--mult 1.0` ⇒ `S = 0.45` ⇒ **头被渲小 2.2 倍**（本轮实测踩到）。
  · `shift` 语义 = 加在**锚点**上（与 `Placement.solve(shift=…)` 一致），与生成器常量同源；
  · 锚点由 `head_place.Placement` 现算，**不手抄**（防文档与产物口径漂移）。
  · 尺寸比 / 位移量一律报**解析值**（别用启发式取块量，火焰花瓣逐帧变会给出假比值）。

用法: python .cache/_sq_shift13.py <out.png>
（必须用带 PIL 的解释器：envs/default/Scripts/python.exe）
"""
from __future__ import annotations

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from PIL import Image, ImageDraw  # noqa: E402

from head_place import Placement  # noqa: E402

PREVIEW = os.path.join(HERE, '_sq_preview.py')
GAME = r'D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28'
BOX = '-110,-170,110,80'
K = 1.5
PAD = 18
HEADER = 34
BG = (238, 238, 243)
DELTA = 12.0                    # 本轮增量（右上各 12px）

ROLES = [
    dict(tag='QUEEN', char='queen', mult=2.4, scale=1.08,
         before=(0.0, -20.1565), after=(12.0, -32.1565),
         body=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Challenge',
                           'DiscoFire', 'ZombieDiscoFire.tres'),
         follow=19, clip='MoonWalk',
         head=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Plant', 'Gold',
                           'QueenSunFlower', 'QueenSunFlower.tres')),
    dict(tag='DANCER', char='dancer', mult=1.0, scale=1.0,
         before=(18.0, -18.0), after=(30.0, -30.0),
         body=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Challenge',
                           'DancerFire', 'ZombieDancerFire.tres'),
         follow=15, clip='Walk',
         head=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Chapter1',
                           'Normal', 'Sprite', 'Sunflower', 'SunFlowerHead.tres')),
]


def anchor_of(r, shift):
    """锚点 = 身体 follow 层并集 bbox 中心（target） + 有意位移 shift。"""
    P = Placement(r['body'], (-40.0, -80.0), r['follow'], r['clip'],
                  r['head'], 'Idle', 'anim_idle', scale=(-r['scale'], r['scale']))
    return (P.target[0] + shift[0], P.target[1] + shift[1])


def to_px(pt):
    x0, y0 = [float(v) for v in BOX.split(',')[:2]]
    return ((pt[0] - x0) * K, (pt[1] - y0) * K)


def render(r, shift, out):
    # ⚠️ 用 `--head-scale`（绝对 `S` = 生成器 `head_scale`），**不要**用 `--mult`：
    #    `--mult` 是「相对基准 0.45」的倍率，而 0.45 是**女王包的历史口径**
    #    ⇒ 舞者 `head_scale 1.0` 若写成 `--mult 1.0` 会得到 `S = 0.45`，**头被渲小 2.2 倍**。
    cmd = [sys.executable, PREVIEW, '--out', out, '--char', r['char'],
           '--head-scale', '%g' % r['scale'], '--no-aura',
           '--shift=%g,%g' % shift, '--box=' + BOX, '--k', '%g' % K]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL)
    return out


def main():
    out = sys.argv[1]
    panels = []
    for r in ROLES:
        a_b, a_a = anchor_of(r, r['before']), anchor_of(r, r['after'])
        d = (a_a[0] - a_b[0], a_a[1] - a_b[1])
        sys.stdout.write('%s  shift %s → %s   锚点 %s → %s   Δ=(%.2f, %.2f)\n'
                         % (r['tag'], r['before'], r['after'],
                            tuple(round(v, 4) for v in a_b), tuple(round(v, 4) for v in a_a),
                            d[0], d[1]))
        for tag, sh, anchor, other in (('BEFORE', r['before'], a_b, a_a),
                                       ('AFTER', r['after'], a_a, a_b)):
            p = render(r, sh, os.path.join(HERE, '_s13_%s_%s.png' % (r['char'], tag.lower())))
            im = Image.open(p).convert('RGBA')
            flat = Image.alpha_composite(Image.new('RGBA', im.size, BG + (255,)), im).convert('RGB')
            panels.append(dict(r=r, tag=tag, shift=sh, im=flat, anchor=anchor, other=other))

    w, h = panels[0]['im'].size
    W = w * len(panels) + PAD * (len(panels) + 1)
    H = h + HEADER + PAD + 24
    cv = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(cv)
    x = PAD
    for pn in panels:
        now = 'AFTER ' if pn['tag'] == 'AFTER' else 'BEFORE'
        cv.paste(pn['im'], (x, HEADER))
        d.text((x + 2, 5), '%s %s' % (pn['r']['tag'], now), fill=(20, 20, 20))
        d.text((x + 2, 18), 'shift=(%g, %g)  scale=%.2f' % (pn['shift'][0], pn['shift'][1],
                                                            pn['r']['scale']), fill=(95, 95, 95))
        # 灰色虚线十字 = 对面那格的位置
        ox, oy = to_px(pn['other'])
        ox, oy = int(round(x + ox)), int(round(HEADER + oy))
        for t in range(x, x + w, 8):
            d.line([(t, oy), (min(t + 4, x + w), oy)], fill=(150, 150, 158), width=1)
        for t in range(HEADER, HEADER + h, 8):
            d.line([(ox, t), (ox, min(t + 4, HEADER + h))], fill=(150, 150, 158), width=1)
        # 亮色十字 = 本格锚点
        ax, ay = to_px(pn['anchor'])
        ax, ay = int(round(x + ax)), int(round(HEADER + ay))
        d.line([(x, ay), (x + w, ay)], fill=(220, 30, 30), width=2)
        d.line([(ax, HEADER), (ax, HEADER + h)], fill=(0, 170, 220), width=2)
        x += w + PAD
    d.text((PAD, H - 18),
           'solid crosshair = this panel head-centre    dashed grey = the other panel '
           '(delta = up-right %.0fpx each)' % DELTA, fill=(60, 60, 60))
    cv.save(out)
    sys.stdout.write('-> %s  %s\n' % (out, cv.size))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
