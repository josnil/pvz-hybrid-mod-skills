# -*- coding: utf-8 -*-
"""反证 slice 变换语义：把 .tres 算出的帧包围盒与栅格合成图 tile 实测包围盒对齐。"""
import sys
sys.path.insert(0, r'D:/zzz/pvzHE/pvz-hybrid-mod-skills/tools/zombie')
from anime_io import parse_tres
from PIL import Image

TRES = r'D:/zzz/pvzHE/解包/植物大战僵尸杂交版V0.28/Asset/Anime/Character/Zombie/Chapter1/Normal/ZombieNormal.tres'
COMP = r'D:/zzz/pvzHE/解包/植物大战僵尸杂交版V0.28/Asset/Anime/Character/Zombie/Chapter1/Normal/Generated/ZombieNormalRasterComposite.png'
TW, TH = 105, 134
COLS = 32
ANCHOR = (52.0, 86.0)   # = -origin


def frame_items(d, f):
    o, c = d['frameOffsets'][f], d['frameCounts'][f]
    return list(range(o, o + c))


def corners(x, y, w, h):
    return [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]


def bbox_for(d, f, mode):
    xs, ys = [], []
    for i in frame_items(d, f):
        mid = d['sliceMediaIds'][i]
        rx, ry, rw, rh = d['mediaRects'][mid * 4:mid * 4 + 4]
        xx, xy, yx, yy, ox, oy = d['sliceTransforms'][i * 6:i * 6 + 6]
        for (px, py) in corners(rx, ry, rw, rh):
            if mode == 'A':      # M(p - rect.topleft) + (ox,oy)
                vx, vy = px - rx, py - ry
            elif mode == 'C':    # M(p - rect.center) + (ox,oy)
                vx, vy = px - (rx + rw / 2), py - (ry + rh / 2)
            elif mode == 'D':    # M(p) - (ox,oy)
                vx, vy = px, py
            elif mode == 'E':    # M(p - (ox,oy)) + (ox,oy)
                vx, vy = px - ox, py - oy
            elif mode == 'F':    # M(p) + offset(no origin at all)
                vx, vy = px, py
            X = xx * vx + yx * vy
            Y = xy * vx + yy * vy
            if mode == 'D':
                X -= ox; Y -= oy
            else:
                X += ox; Y += oy
            xs.append(X); ys.append(Y)
    return (min(xs), min(ys), max(xs), max(ys))


def tile_bbox(im, ti):
    c, r = ti % COLS, ti // COLS
    t = im.crop((c * TW, r * TH, c * TW + TW, r * TH + TH))
    b = t.getbbox()
    return b


im = Image.open(COMP).convert('RGBA')
d = parse_tres(TRES)

for f in (44, 91, 138):
    b = tile_bbox(im, f)
    tgt = (b[0] - ANCHOR[0], b[1] - ANCHOR[1], b[2] - ANCHOR[0], b[3] - ANCHOR[1])
    print('frame %d  tile bbox %s  -> slice-space %s' % (f, b, tuple(round(v, 1) for v in tgt)))
    for mode in 'ACDE':
        r = bbox_for(d, f, mode)
        print('     mode %s -> %s' % (mode, tuple(round(v, 1) for v in r)))
