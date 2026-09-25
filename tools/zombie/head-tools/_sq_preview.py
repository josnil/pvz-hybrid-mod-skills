# -*- coding: utf-8 -*-
"""_sq_preview.py —— 离线合成「火焰迪斯科僵尸身体 + 向日葵女王头(+光环)」PNG。

按引擎真实变换画（与 `.cache/render_head_preview.py` / `head_place.py` 同源）：
    · 身体切片 : space = pose_matrix·(u,v) + body_offset(-40,-80)
    · 头节点   : node  = <被跟随层 L19 的 pose>.Origin + body_offset
                 A     = rot_scale(θ_L, −S, +S)      （S = 0.45 × 倍数）
                 头切片: space = node + A·(pose + head.offset)
    · 光环     : space = AuraHolder.pos + rot_scale(0, 1.6, 1.6)·(pose + aura.offset)
                        + body_offset
图层显隐：身体可见层 = 1..15 + 17 + 21..26（根场景里关掉的头发/原头层除外）；
          头 = `QUEEN_HEAD_ON` 5 个美术层；光环只画 `图层_3`。

用法：
  python .cache/_sq_preview.py --out .cache/_pv_25.png --mult 2.5
  python .cache/_sq_preview.py --out .cache/_pv_20.png --mult 2.0 --no-aura
  python .cache/_sq_preview.py --out .cache/_pv_up8.png --mult 2.0 --no-aura \
         --shift=0,-8          # 头整体上移 8px（显示空间 y 向下为正）
"""
from __future__ import annotations

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image  # noqa: E402

from head_fit import Skin  # noqa: E402
from head_place import Placement  # noqa: E402
from atlas_manifest import Manifest  # noqa: E402

GAME = r'D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28'
GA = os.path.join(GAME, 'addons', 'AdobeAnimateEditor', 'GeneratedAtlas')
MANIFEST = os.path.join(GA, 'AdobeAnimateGlobalAtlasManifest.tres')
MANIFEST_PNG = os.path.join(GA, 'AdobeAnimateVisualTextureArray.png')

BODY_TRES = os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Challenge',
                         'DiscoFire', 'ZombieDiscoFire.tres')
BODY_DAT = 'ZombieDiscoFire.dat'
HEAD_TRES = os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Plant', 'Gold',
                         'QueenSunFlower', 'QueenSunFlower.tres')
HEAD_DAT = 'QueenSunFlower.dat'

BODY_OFF = (-40.0, -80.0)
FOLLOW = 19
BODY_VISIBLE = set(list(range(1, 16)) + [17] + list(range(21, 27)))
HEAD_ON = ["anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]
AURA_LAYER = "图层_3"
AURA_HOLDER_POS = (1.4, 54.6)
AURA_SCALE = 1.6
AURA_OFFSET = (-39.5, -71.5)
BASE = 0.45
BODY_CLIP = 'MoonWalk'

# ★ 2026-09-25 第十三轮新增：`--char` 让它也能渲**火焰向日葵舞者僵尸**（本文件原先是女王专用）。
#   默认 `queen` ⇒ **完全向后兼容**（所有既有脚本/图都不受影响）。
#   ⚠️ 换角色要同时换：身体/头的 `.tres` + 图集 **key**（= `.dat` 名，查 `Manifest.source_keys`）
#      + `follow` 图层 + body clip + 可见层集合 + 头的可见层清单（`AnimeClips` 不是视觉层，忽略无害）。
#      ⚠️ 身体可见层**必须剔掉 `_ground`（隐藏背景板）与被关掉的原头层**，否则会渲出「两个头」。
CHARS = {
    'queen': dict(
        body_tres=BODY_TRES, body_dat=BODY_DAT, follow=FOLLOW, clip='MoonWalk',
        body_visible=BODY_VISIBLE,
        head_tres=HEAD_TRES, head_dat=HEAD_DAT, head_on=list(HEAD_ON),
        aura=True,
    ),
    'dancer': dict(
        body_tres=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Challenge',
                               'DancerFire', 'ZombieDancerFire.tres'),
        body_dat='ZombieDancerFire.dat', follow=15, clip='Walk',
        # 25 层里剔掉 `_ground`(0) + `anim_hair/hair1/hair2/hair3`(23/22/16/13) +
        # `anim_head1/head2`(14/15) ⇒ 剩下 1..12 + 17..21（= 舞者身体本体 + 手臂 + 领子）
        body_visible=set(list(range(1, 13)) + list(range(17, 22))),
        head_tres=os.path.join(GAME, 'Asset', 'Anime', 'Character', 'Zombie', 'Chapter1',
                               'Normal', 'Sprite', 'Sunflower', 'SunFlowerHead.tres'),
        head_dat='SunFlowerHead.dat',
        head_on=["anim_idle", "SunFlower_bottompetals", "SunFlower_toppetals"]
                + ["SunFlower_leftpetal%d" % i for i in range(1, 9)]
                + ["SunFlower_rightpetal%d" % i for i in range(1, 10)],
        aura=False,          # 舞者没有「3×3 光环」
    ),
}


# ---------------------------------------------------------------- 2x3 仿射
def mul(M1, M2):
    a1, b1, c1, d1, x1, y1 = M1
    a2, b2, c2, d2, x2, y2 = M2
    return (a1 * a2 + c1 * b2, b1 * a2 + d1 * b2,
            a1 * c2 + c1 * d2, b1 * c2 + d1 * d2,
            a1 * x2 + c1 * y2 + x1, b1 * x2 + d1 * y2 + y1)


def inv(M):
    a, b, c, d, x, y = M
    det = a * d - b * c
    ia, ib, ic, id_ = d / det, -b / det, -c / det, a / det
    return (ia, ib, ic, id_, -(ia * x + ic * y), -(ib * x + id_ * y))


def trans(tx, ty):
    return (1.0, 0.0, 0.0, 1.0, float(tx), float(ty))


def rot_scale(deg, sx, sy):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (c * sx, s * sx, -s * sy, c * sy, 0.0, 0.0)


# ---------------------------------------------------------------- 图集
class Atlas(object):
    def __init__(self):
        self.m = Manifest(MANIFEST)
        Image.MAX_IMAGE_PIXELS = None
        self._img = None
        self.src = {}
        self._crops = {}

    def page(self, n):
        if self._img is None:
            self._img = Image.open(MANIFEST_PNG).convert('RGBA')
            sys.stdout.write("atlas loaded %s\n" % (self._img.size,))
        w = self.m.layer_w
        return self._img.crop((n * w, 0, (n + 1) * w, self.m.layer_h))

    def source_index(self, key):
        if key not in self.src:
            self.src[key] = self.m.source_index(key)
        return self.src[key]

    def crop(self, key, mid):
        ck = (key, mid)
        if ck in self._crops:
            return self._crops[ck]
        g = self.m.media(self.source_index(key), mid)
        if g is None:
            self._crops[ck] = None
            return None
        page, rect = g
        box = (int(round(rect[0])), int(round(rect[1])),
               int(round(rect[0] + rect[2])), int(round(rect[1] + rect[3])))
        if box[2] <= box[0] or box[3] <= box[1]:
            self._crops[ck] = None
            return None
        self._crops[ck] = self.page(page).crop(box)
        return self._crops[ck]


class Canvas(object):
    def __init__(self, box, k):
        self.x0, self.y0 = box[0], box[1]
        self.k = k
        self.W = int(round((box[2] - box[0]) * k))
        self.H = int(round((box[3] - box[1]) * k))
        self.im = Image.new('RGBA', (self.W, self.H), (0, 0, 0, 0))

    def draw_slice(self, crop, M):
        """M: media 局部像素 -> 显示空间。"""
        Mi = inv(M)
        k, x0, y0 = self.k, self.x0, self.y0
        params = (Mi[0] / k, Mi[2] / k, Mi[0] * x0 + Mi[2] * y0 + Mi[4],
                  Mi[1] / k, Mi[3] / k, Mi[1] * x0 + Mi[3] * y0 + Mi[5])
        piece = crop.transform((self.W, self.H), Image.AFFINE, params,
                               resample=Image.BILINEAR)
        self.im = Image.alpha_composite(self.im, piece)


def draw_skin(cv, at, key, skin, frame, layers, pre):
    n = 0
    for lid, mid, M, al in skin.frame_slices(frame):
        if layers is not None and lid not in layers:
            continue
        if al <= 0:
            continue
        crop = at.crop(key, mid)
        if crop is None:
            continue
        cv.draw_slice(crop, mul(pre, M))
        n += 1
    return n


REF_HEAD_FIG = 66.0 / 134.0     # 参考图：头(皇冠顶→花瓣下缘) 66 / 全身 134
REF_HEAD_BODY = 66.0 / 66.0      # 参考图：可见身体(花瓣下缘→脚) 66


def sweep(a):
    """对一串放大倍数，用**真实渲染像素**量「头 / 全身」「头 / 可见身体」两个比值。"""
    at = Atlas()
    B = Skin(BODY_TRES)
    H = Skin(HEAD_TRES)
    x0, y0, x1, y1 = [float(v) for v in a.box.split(',')]
    sys.stdout.write("参考图：头/全身 = %.4f   头/可见身体 = %.4f\n\n"
                     % (REF_HEAD_FIG, REF_HEAD_BODY))
    sys.stdout.write("%6s %8s %8s %8s %8s %8s %8s %10s %10s\n"
                     % ("倍率", "S", "头高", "头宽", "身体rc", "全身rc", "可见身", "头/全身", "头/可见身"))
    for mult in [float(v) for v in a.sweep.split(',')]:
        S = round(BASE * mult, 6)
        P = Placement(BODY_TRES, BODY_OFF, FOLLOW, BODY_CLIP, HEAD_TRES, 'Idle',
                      'anim_idle', scale=(-S, S))
        off = P.solve()['offset']
        by_id = {P.H.layer_dict[n]: n for n in HEAD_ON if n in P.H.layer_dict}
        head_M = mul(trans(*P.node(a.bf)),
                     mul(rot_scale(P.body_rot_deg(a.bf), -S, S), trans(off[0], off[1])))
        boxes = {}
        for tag, key, skin, frame, layers, M in (
                ("body", BODY_DAT, B, a.bf, BODY_VISIBLE, trans(*BODY_OFF)),
                ("head", HEAD_DAT, H, a.hf, set(by_id), head_M),
                ("aura", HEAD_DAT, H, a.aura_hf, {H.layer_dict[AURA_LAYER]},
                 mul(trans(AURA_HOLDER_POS[0], AURA_HOLDER_POS[1]),
                     mul(rot_scale(0.0, AURA_SCALE, AURA_SCALE),
                         trans(AURA_OFFSET[0], AURA_OFFSET[1]))))):
            sub = Canvas((x0, y0, x1, y1), a.k)
            draw_skin(sub, at, key, skin, frame, layers, M)
            bb = sub.im.getbbox()
            boxes[tag] = None if bb is None else (
                x0 + bb[0] / a.k, y0 + bb[1] / a.k, x0 + bb[2] / a.k, y0 + bb[3] / a.k)
        hb, bb_ = boxes["head"], boxes["body"]
        head_h = hb[3] - hb[1]
        head_w = hb[2] - hb[0]
        body_h = bb_[3] - bb_[1]
        fig_h = max(hb[3], bb_[3]) - min(hb[1], bb_[1])
        vis_body = bb_[3] - hb[3]        # 花瓣下缘 → 脚底
        sys.stdout.write("%6.2f %8.4f %8.2f %8.2f %8.2f %8.2f %8.2f %10.4f %10.4f\n"
                         % (mult, S, head_h, head_w, body_h, fig_h, vis_body,
                            head_h / fig_h, head_h / vis_body))
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--mult', type=float, default=2.5)
    ap.add_argument('--head-scale', type=float, default=0.0,
                    help='★ **直接**给头的绝对缩放 `S`（= 生成器里的 `head_scale`），'
                         '优先于 `--mult`。⚠️ `--mult` 是「相对基准 0.45」的倍率'
                         '（`S = 0.45 × mult`），**基准 0.45 是女王包的历史口径** ⇒ '
                         '给别的角色渲图时极易搞错（实测把 `head_scale 1.0` 写成 `--mult 1.0` '
                         '⇒ `S = 0.45`，头被渲小 2.2 倍）。**一律优先用 `--head-scale`。**')
    ap.add_argument('--bf', type=int, default=0)
    ap.add_argument('--hf', type=int, default=0)
    ap.add_argument('--aura-hf', type=int, default=0)
    ap.add_argument('--no-aura', action='store_true')
    ap.add_argument('--no-head', action='store_true')
    ap.add_argument('--no-body', action='store_true')
    ap.add_argument('--box', default='-200,-300,200,150')
    ap.add_argument('--k', type=float, default=1.0)
    ap.add_argument('--shift', default='0,0',
                    help='★ 头部在**显示空间**的位移 dx,dy（px，y 向下；「往上一点」= dy 为负）。'
                         '语义与 `head_place.Placement.solve(shift=…)` **完全一致** —— '
                         '加在**锚点**(node)上而不是直接加在 offset 上。'
                         '⚠️ 显示空间位移 ≠ offset 增量：A 含 sx=−1 的横翻 + 交叉项，'
                         '直接改 offset 会横竖都变（详见 head_place.py 头注 ★★ 第三轮 ②）。')
    ap.add_argument('--off', default=None,
                    help='★★ 直接给 `head_offset` 的 x,y（**场景真值**，见生成器 `GOLD_*_HEAD_OFFSET`）。'
                         '给了它就**绕过** `Placement.solve()` 与 `--shift`（= 与实机逐字同源）。'
                         '核对法：女王 `--shift=0,-20.1565` 与 '
                         '`--off=-61.2078,-46.9935` 必须渲出同一张图。')
    ap.add_argument('--fit-height', type=int, default=0,
                    help='>0 时按非空 bbox 裁切并缩放到该像素高度')
    ap.add_argument('--char', default='queen', choices=sorted(CHARS),
                    help='★ 哪个角色（默认 queen，向后兼容）。dancer = 火焰向日葵舞者僵尸')
    ap.add_argument('--follow', type=int, default=0,
                    help='★★ 覆盖「跟随层」`followParentSpriteLayerId`（0 = 用角色默认）。'
                         '第十四轮：试 `--follow=28`（女王 anim_hair1）看抬头段接缝是否更连贯。'
                         '⚠️ 换 L 后 `head_offset` **必须重解**（`.cache/_j14_follow.py` 会给值），'
                         '并把该值用 `--off` 传进来。')
    ap.add_argument('--sweep', default=None,
                    help='只算指标不落盘：逗号分隔的放大倍数列表，如 2.5,2.25,2.0,1.75')
    a = ap.parse_args()

    # ★ 把所选角色的参数**写回模块全局** ⇒ 下面的闭包（show / box_of）与 sweep 不用改一行
    C = CHARS[a.char]
    globals().update(BODY_TRES=C['body_tres'], BODY_DAT=C['body_dat'],
                     FOLLOW=(a.follow or C['follow']), BODY_CLIP=C['clip'],
                     BODY_VISIBLE=C['body_visible'],
                     HEAD_TRES=C['head_tres'], HEAD_DAT=C['head_dat'],
                     HEAD_ON=list(C['head_on']))
    if not C['aura']:
        a.no_aura = True          # 舞者没有光环节点

    if a.sweep:
        return sweep(a)

    S = round(a.head_scale if a.head_scale else BASE * a.mult, 6)
    sh = tuple(float(v) for v in a.shift.split(','))
    P = Placement(BODY_TRES, BODY_OFF, FOLLOW, BODY_CLIP, HEAD_TRES, 'Idle',
                  'anim_idle', scale=(-S, S))
    off = P.solve()['offset']
    if a.off:                      # ★ 场景真值优先（与实机逐字同源，见 --off 的 help）
        off = tuple(float(v) for v in a.off.split(','))
    by_id = {P.H.layer_dict[n]: n for n in HEAD_ON if n in P.H.layer_dict}
    body_rot = P.body_rot_deg(a.bf)
    node = P.node(a.bf)
    head_A = rot_scale(body_rot, -S, S)
    # ★ shift 加在**锚点**上（与 Placement.solve(shift=…) 等价）：
    #   trans(node+sh)·A·trans(off)  ⇔  整头在显示空间平移 (sh[0], sh[1])
    node_s = (node[0] + sh[0], node[1] + sh[1])
    sys.stdout.write("mult=%.3f  S=%.4f  head_offset=(%.4f, %.4f)  body_rot=%.4f°  "
                     "node=(%.4f, %.4f)  shift=(%.2f, %.2f)\n"
                     % (S / BASE, S, off[0], off[1], body_rot, node[0], node[1], sh[0], sh[1]))

    at = Atlas()
    B = Skin(BODY_TRES)
    H = Skin(HEAD_TRES)
    x0, y0, x1, y1 = [float(v) for v in a.box.split(',')]
    cv = Canvas((x0, y0, x1, y1), a.k)

    # ---- 三个变换（各自独立，顺序 = 实际绘制顺序：光环 → 身体 → 头） ----
    aura_M = mul(trans(AURA_HOLDER_POS[0], AURA_HOLDER_POS[1]),
                 mul(rot_scale(0.0, AURA_SCALE, AURA_SCALE),
                     trans(AURA_OFFSET[0], AURA_OFFSET[1])))
    body_M = trans(*BODY_OFF)
    head_M = mul(trans(*node_s), mul(head_A, trans(off[0], off[1])))

    def show(tag, key, skin, frame, layers, M, want):
        sub = Canvas((x0, y0, x1, y1), a.k)
        n = draw_skin(sub, at, key, skin, frame, layers, M)
        bb = sub.im.getbbox()
        if bb is None:
            sys.stdout.write("  %-5s slices=%-3d  空\n" % (tag, n))
            return None
        spx = (x0 + bb[0] / a.k, y0 + bb[1] / a.k, x0 + bb[2] / a.k, y0 + bb[3] / a.k)
        sys.stdout.write("  %-5s slices=%-3d  bbox x %.2f..%.2f  y %.2f..%.2f  (w %.2f h %.2f)\n"
                         % (tag, n, spx[0], spx[2], spx[1], spx[3],
                            spx[2] - spx[0], spx[3] - spx[1]))
        return sub.im if want else None

    def box_of(tag, key, skin, frame, layers, M):
        """只算几何 bbox（不画），用于头部/光环的显示空间范围。"""
        pts = []
        for lid, mid, Mp, al in skin.frame_slices(frame):
            if layers is not None and lid not in layers:
                continue
            rw, rh = skin.media_size(mid)
            for u, v in ((0, 0), (rw, 0), (0, rh), (rw, rh)):
                px = Mp[0] * u + Mp[2] * v + Mp[4]
                py = Mp[1] * u + Mp[3] * v + Mp[5]
                pts.append((M[0] * px + M[2] * py + M[4], M[1] * px + M[3] * py + M[5]))
        if not pts:
            return None
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return (min(xs), min(ys), max(xs), max(ys))

    sys.stdout.write("各部位几何（显示空间）：\n")
    bb_body = box_of("body", BODY_DAT, B, a.bf, BODY_VISIBLE, body_M)
    sys.stdout.write("  身体几何 x %.2f..%.2f  y %.2f..%.2f  (高 %.2f)\n"
                     % (bb_body[0], bb_body[2], bb_body[1], bb_body[3], bb_body[3] - bb_body[1]))
    bb_head = box_of("head", HEAD_DAT, H, a.hf, set(by_id), head_M)
    sys.stdout.write("  头几何   x %.2f..%.2f  y %.2f..%.2f  (高 %.2f 宽 %.2f)\n"
                     % (bb_head[0], bb_head[2], bb_head[1], bb_head[3],
                        bb_head[3] - bb_head[1], bb_head[2] - bb_head[0]))
    # ★ 光环是**女王专属**：舞者没有 `图层_3` ⇒ 必须跳过（否则 KeyError），并让 fig 不受影响
    bb_aura = None
    if AURA_LAYER in H.layer_dict:
        bb_aura = box_of("aura", HEAD_DAT, H, a.aura_hf, {H.layer_dict[AURA_LAYER]}, aura_M)
    if bb_aura:
        sys.stdout.write("  光环几何 x %.2f..%.2f  y %.2f..%.2f  (w %.2f h %.2f), 中心 (%.2f, %.2f)\n"
                         % (bb_aura[0], bb_aura[2], bb_aura[1], bb_aura[3],
                            bb_aura[2] - bb_aura[0], bb_aura[3] - bb_aura[1],
                            (bb_aura[0] + bb_aura[2]) / 2, (bb_aura[1] + bb_aura[3]) / 2))
    fig = (min(bb_body[0], bb_head[0], bb_aura[0] if bb_aura else 1e9),
           min(bb_body[1], bb_head[1], bb_aura[1] if bb_aura else 1e9),
           max(bb_body[2], bb_head[2], bb_aura[2] if bb_aura else -1e9),
           max(bb_body[3], bb_head[3], bb_aura[3] if bb_aura else -1e9))
    sys.stdout.write("  全身几何 x %.2f..%.2f  y %.2f..%.2f  (高 %.2f)\n"
                     % (fig[0], fig[2], fig[1], fig[3], fig[3] - fig[1]))
    sys.stdout.write("  ★ 头高/全身高 = %.4f   头高/身体高 = %.4f\n"
                     % ((bb_head[3] - bb_head[1]) / (fig[3] - fig[1]),
                        (bb_head[3] - bb_head[1]) / (bb_body[3] - bb_body[1])))

    sys.stdout.write("绘制：\n")
    ims = []
    if not a.no_aura:
        ims.append(show("aura", HEAD_DAT, H, a.aura_hf, {H.layer_dict[AURA_LAYER]}, aura_M, True))
    if not a.no_body:
        ims.append(show("body", BODY_DAT, B, a.bf, BODY_VISIBLE, body_M, True))
    if not a.no_head:
        ims.append(show("head", HEAD_DAT, H, a.hf, set(by_id), head_M, True))
    for im in ims:
        if im is not None:
            cv.im = Image.alpha_composite(cv.im, im)

    out = cv.im
    if a.fit_height > 0:
        bbox = out.getbbox()
        if bbox:
            out = out.crop(bbox)
            h = a.fit_height
            w = int(round(out.size[0] * h / float(out.size[1])))
            out = out.resize((w, h), Image.LANCZOS)
    out.save(a.out)
    sys.stdout.write("-> %s  %s\n" % (a.out, out.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
