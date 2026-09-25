# -*- coding: utf-8 -*-
"""_sq_final_cmp.py —— 出「交付用」头身比对照图。

口径（为什么这么裁）：
  · 候选图用 `--no-aura --fit-height H`：**剔除光环**再按非空 bbox 归一 —— 光环在
    各倍率下**像素尺寸恒定**（200px），把它算进「全身高」会把倍率差异稀释掉
    （实测：含光环时 2.0 倍只有 0.3576，剔掉后 0.4793）。
  · 参考图按 `.cache/_sq_refmeasure.py` 泛洪分割出的**角色连通块**紧裁
    （默认 box `60,38,124,172`），再缩放到同一高度。
⇒ 两边都只剩「头 + 身体」，头身比可直接目视比较。

用法:
    python .cache/_sq_final_cmp.py <out.png> [H]
"""
from __future__ import annotations

import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, '_ref_QQ_1790301323306.png')
REF_BOX = (60, 38, 124, 172)      # 泛洪分割得到的角色连通块（x0,y0,x1,y1）
CANDS = [('2.25x', '_fit_nb_2.25.png'), ('2.10x', '_fit_nb_2.10.png'),
         ('2.00x', '_fit_nb_2.00.png'), ('1.80x', '_fit_nb_1.80.png')]
GAP = 18


def main():
    out = sys.argv[1]
    H = int(sys.argv[2]) if len(sys.argv) > 2 else 340

    tiles = []
    ref = Image.open(REF).convert('RGBA').crop(REF_BOX)
    w = max(1, int(round(ref.width * H / ref.height)))
    tiles.append(ref.resize((w, H), Image.NEAREST))
    for _tag, fn in CANDS:
        p = os.path.join(HERE, fn)
        if not os.path.isfile(p):
            sys.stderr.write('缺文件: %s\n' % p)
            return 2
        im = Image.open(p).convert('RGBA')
        w = max(1, int(round(im.width * H / im.height)))
        tiles.append(im.resize((w, H), Image.NEAREST))

    W = sum(t.width for t in tiles) + GAP * (len(tiles) - 1)
    cv = Image.new('RGBA', (W, H), (255, 255, 255, 255))
    x = 0
    for t in tiles:
        cv.paste(t, (x, 0), t)
        x += t.width + GAP
    cv.save(out)
    sys.stdout.write('REF %dx%d  +  %s\n-> %s (%d x %d)\n'
                     % (tiles[0].width, tiles[0].height,
                        ' '.join('%s=%dpx' % (t[0], w.width)
                                 for t, w in zip(CANDS, tiles[1:])),
                        out, W, H))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
