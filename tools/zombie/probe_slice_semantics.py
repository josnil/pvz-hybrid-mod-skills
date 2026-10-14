# -*- coding: utf-8 -*-
"""反证 slice 变换语义：把 .tres 算出的帧包围盒与栅格合成图 tile 实测包围盒对齐。"""
import sys
# sys.path 由适配块处理
from anime_io import parse_tres
from PIL import Image
# --- 本机路径适配（自动注入；换机器只改 tools/_env.py）---
import os as _os
import sys as _sys

_TOOLS = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isfile(_os.path.join(_TOOLS, "_env.py")):
    _parent = _os.path.dirname(_TOOLS)
    if _parent == _TOOLS:
        break
    _TOOLS = _parent
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
_PIPE = _os.path.join(_TOOLS, 'zombie')
if _os.path.isdir(_PIPE) and _PIPE not in _sys.path:
    _sys.path.insert(0, _PIPE)

from _env import (  # noqa: E402
    GAME, UNPACK, CLASSIC, MODS, USER_DATA_DIR, PY, WORKSPACE, REF_DIR,
    require_ref_dir, require_classic, ensure_mods, unpack_status, describe,
)
try:  # 从属脚本：向上找 _gen.py 定位本流水线的工作区
    from _gen import MOD_WORKSPACE  # noqa: F401,E402
except ImportError:
    MOD_WORKSPACE = None
# --- 适配块结束 ---

TRES = _os.path.join(UNPACK, "Asset/Anime/Character/Zombie/Chapter1/Normal/ZombieNormal.tres")
COMP = _os.path.join(UNPACK, "Asset/Anime/Character/Zombie/Chapter1/Normal/Generated/ZombieNormalRasterComposite.png")
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
