# -*- coding: utf-8 -*-
"""奶龙僵尸皮肤构建器：cut_body/cut_laugh → NaiLong.dat + NaiLong.tres + NaiLongAtlas.png

几何权威（见 anime_io.py 头部 + probe_slice_semantics.py 反证）：
    元素(f) = mediaId, xx, xy, yx, yy, ox, oy, alpha
    node_local(p) = (ox,oy) + M·(p)      M·v = (xx*vx + yx*vy,  xy*vx + yy*vy)
    p = 图集内「本 media rect 的局部坐标」，原点 = rect 左上角（mode A，已由
        ZombieNormalRasterComposite 的 tile 实测 + build_official_skin.py 预览渲染双证）

动画模型（每帧一个仿射 A = Lin·x + t，绕 pivot=(0,FEET_Y) 做缩放/旋转）：
    中性摆放（Lin=I,t=0）时 media 的左上角落在 node-local 的 (lx0, ly0)
    ⇒  元素 = ( s·Lin00, s·Lin10, s·Lin01, s·Lin11,
                Lin00·lx0 + Lin01·ly0 + tx,
                Lin10·lx0 + Lin11·ly0 + ty )
    其中 s = 每个图集像素对应的 node 单位（= PACK·BASE_SCALE）。

对齐基准：内置 ZombieNormal 在 SpriteGroup 空间里脚底 y≈+45（tile 实测），
    x 轴以躯干中轴为 0 ⇒ FEET_Y = 45.0，横向轴心 = 0。
"""
import json
import math
import os
import struct

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, '.cache_nailong')

# ------------------------------------------------------------------ 几何常量
FEET_Y = 45.0          # node-local 接地线。
                       # 实测内置普通僵尸（ZombieNormalRasterComposite）最深的脚底像素
                       # 在 tile 行 131 ⇒ node-local y = 131-86 = 45（origin y = -86）；
                       # Walk1/Walk2/Eat 的脚底恒在 42..45，从不低于 45。
BODY_DISPLAY_H = 124.0  # 内置普通僵尸（无护具）可见高 ≈120（tile 实测 y∈[-74,46]）
PACK = 2                # 图集以「显示尺寸 ×2」烘焙，兼顾清晰度与体积
FRAME_RATE = 12.0

MEDIA_BODY = 0
MEDIA_LAUGH = 1
LAYERS = ['body', 'laugh']

# ---------------------------------------------------------------- 根运动（前进）
#
# ★★ 僵尸「向前走」的唯一机制（源码实证）：
#    `GroundMoveComponent` 是**唯一**会平移角色的组件
#    （全仓只有它调用 `TowerDefenseCharacter.TranslateForPhysicsFrame`）。
#    它按名解析动画里的 `_ground` 层（`groundLayerName = &"_ground"`，
#    来自内置 `GroundMoveComponentDefinition`），然后：
#        vector2 = 上一帧该层的位姿 - 这一帧的位姿
#        TranslateParent(vector2 * _moveScale)
#    ⇒ **角色前进距离 = `_ground` 层的逐帧位移**。
#    没有 `_ground` 层 ⇒ `_usingGroundLayerSource = false`
#    ⇒ 回退到 `GroundSlot`（必须是 `AdobeAnimateSlot` 才有效）⇒ 位置恒定
#    ⇒ `_moveDelta == 0` ⇒ **角色永远原地不动**。
#    （本包初版就踩了这个坑：皮肤里只有 body/laugh 两层，所以奶龙僵尸一步都没走过。）
#
#    内置普通僵尸的实测标定（Asset/.../Normal/ZombieNormal.tres）：
#        `_ground` 在 Walk1(44..90) 上从 -10 线性走到 +40 ⇒ **+50 px / 47 帧**
#        （12 fps ⇒ 12.77 px/s ≈ 一格草坪 6.3s），回跳 -50 恰好落在
#        Walk1→Walk2 的**剪辑边界**上 —— 边界会置 `sprite.blend`，
#        `BatchUpdateValidated` 里 `if (sprite.pause || sprite.blend) { ResetGroundTracking(); return; }`
#        把这次回跳吃掉，所以看不到任何倒跳。
#    ⇒ **铁律：一个剪辑 = 一条完整锯齿，回跳必须落在剪辑边界上。**
#       （所以下面每个剪辑都是「从 0 递增到整条位移」，绝不在一帧内回跳两次。）
#
#    ⚠️ 顺带纠正上一轮的一个错误结论：`walkSpeedScale` **不影响移速**。
#       基类 `TowerDefenseZombie` 从不读它（只在派生类里被乘到 `sprite.timeScale`），
#       而 `_moveScale` 里也没有它。移速只由本层的位移速率决定。
NORMAL_GROUND_PX_PER_FRAME = 50.0 / 47.0   # 内置普通僵尸实测速率
SPEED_TIER = 2.0                           # 「快」= 普通僵尸的 2 倍
GROUND_PX_PER_FRAME = NORMAL_GROUND_PX_PER_FRAME * SPEED_TIER
GROUND_LAYER = '_ground'
GROUND_OY = 40.0            # 与内置同值；只要保证 transform != Identity 即可
LAYERS_ALL = LAYERS + [GROUND_LAYER]       # id: body=0, laugh=1, _ground=2
# 带根运动的剪辑（一个剪辑 = 一条完整锯齿）。
# 不含 Idle（站着不动）、Eat（停下啃）、Death*/Waterdeath（倒下不该滑走）。
GROUND_CLIPS = ('Walk1', 'Walk2', 'Swim', 'LaughWalk')


# ------------------------------------------------------------------ 工具
def _load_params():
    return json.load(open(os.path.join(CACHE, 'art_params.json'), encoding='utf8'))


def _affine(sy, sx, rot_deg, dx, dy, pivot):
    """绕 pivot 的 缩放→旋转→平移，返回 (Lin(2x2 tuple-of-rows), t(2))。"""
    th = math.radians(rot_deg)
    c, s_ = math.cos(th), math.sin(th)
    # R·S
    a = c * sx
    b = -s_ * sy
    cc = s_ * sx
    d = c * sy
    px, py = pivot
    # t = P - RS·P + (dx,dy)
    tx = px - (a * px + b * py) + dx
    ty = py - (cc * px + d * py) + dy
    return (a, b, cc, d), (tx, ty)


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def _ease_out(t):
    return 1.0 - (1.0 - t) ** 2


# ------------------------------------------------------------------ 剪辑设计
def _idle1(n=10, amp=1.0):
    out = []
    for f in range(n):
        p = 2 * math.pi * f / n
        br = 0.5 - 0.5 * math.cos(p)          # 0→1→0
        out.append(dict(sy=1.0 - 0.030 * br * amp,
                        sx=1.0 + 0.026 * br * amp,
                        rot=0.9 * math.sin(p) * amp,
                        dx=0.6 * math.sin(p) * amp, dy=0.0))
    return out


def _idle2(n=10):
    """抬脚踮一下的变体（& 随机选，给待机加点随机性）。"""
    out = []
    for f in range(n):
        p = 2 * math.pi * f / n
        hop = 0.5 - 0.5 * math.cos(2 * p)
        out.append(dict(sy=1.0 + 0.045 * math.sin(p),
                        sx=1.0 - 0.028 * math.sin(p),
                        rot=2.2 * math.sin(p),
                        dx=0.8 * math.sin(p),
                        dy=-1.8 * hop))
    return out


def _walk1(n=12):
    """摇摆走路：一个周期两步 ⇒ 左右晃 1 次、上下颠 2 次。"""
    out = []
    for f in range(n):
        p = 2 * math.pi * f / n
        bob = 0.5 - 0.5 * math.cos(2 * p)
        out.append(dict(sy=1.0 - 0.032 * bob, sx=1.0 + 0.026 * bob,
                        rot=4.6 * math.sin(p),
                        dx=1.3 * math.sin(p + math.pi / 2),
                        dy=-2.3 * bob))
    return out


def _walk2(n=12):
    """夸张版摇摆（幅度更大、更晃）。"""
    out = []
    for f in range(n):
        p = 2 * math.pi * f / n
        bob = 0.5 - 0.5 * math.cos(2 * p)
        out.append(dict(sy=1.0 - 0.046 * bob, sx=1.0 + 0.038 * bob,
                        rot=6.2 * math.sin(p),
                        dx=2.1 * math.sin(p + math.pi / 2),
                        dy=-3.1 * bob))
    return out


def _eat(n=12):
    """啃食：前倾 + 每口一次下压。 3 口 / 周期。"""
    out = []
    for f in range(n):
        p = 2 * math.pi * 3 * f / n
        bite = 0.5 - 0.5 * math.cos(p)
        out.append(dict(sy=1.0 - 0.055 * bite, sx=1.0 + 0.040 * bite,
                        rot=-8.0 - 5.5 * bite,
                        dx=-1.0 * bite, dy=1.4 * bite))
    return out


def _laugh(n=16):
    """大笑：起手一个「弹一下」，然后 2 拍肚子抖。"""
    out = []
    for f in range(n):
        p = 2 * math.pi * 2 * f / n          # 2 拍 / 剪辑
        wob = math.sin(p)
        pop = math.exp(-f / 3.0)             # 起手弹性
        slow = math.sin(2 * math.pi * f / n)
        out.append(dict(sy=1.0 + 0.062 * wob - 0.055 * pop,
                        sx=1.0 - 0.052 * wob + 0.140 * pop,
                        rot=3.6 * slow + 6.0 * pop * math.sin(f * 1.9),
                        dx=1.7 * slow,
                        dy=-1.6 * (0.5 - 0.5 * math.cos(p))))
    return out


def _laugh_walk(n=36, cycles=3):
    """大笑 + 正常走路：3 秒（36 帧 @12fps）里走完 **3 个完整步态周期**。

    关键约束（三条都有闸门强制）：
      ① 步态分量与 `_walk1(n=12)` **逐帧同值** —— 因为 cycles/n = 3/36 = 1/12，
         `p = 2π·3·f/36 = 2π·f/12` 与 Walk1 完全同相 ⇒ 「就是正常走路」，
         不是另画一套脚步。
      ② 帧数 36 = 3 × 12，所以播放到任何一帧停下都落在完整周期上，
         在 3 秒窗口内必然整周期播完（「动作完整播放」）。
      ③ 笑意叠加用 **5 拍 / 剪辑**，刻意与步态（3 周期）不同频，
         避免两层同频叠出机械感；幅度很小，只做「笑着在走」的微表情，
         不抢走路的骨架。
    """
    out = []
    for f in range(n):
        p = 2 * math.pi * cycles * f / n          # 步态相位：与 _walk1 同值
        bob = 0.5 - 0.5 * math.cos(2 * p)
        lq = math.sin(2 * math.pi * 5 * f / n)    # 笑意相位（5 拍，与步态不同频）
        out.append(dict(
            sy=1.0 - 0.032 * bob + 0.014 * lq,
            sx=1.0 + 0.026 * bob - 0.011 * lq,
            rot=4.6 * math.sin(p) + 1.3 * lq,
            dx=1.3 * math.sin(p + math.pi / 2),
            dy=-2.3 * bob,
        ))
    return out


def _death1(n=18):
    """瘫成一坨：起手一鼓，然后横向摊开、纵向压扁（保底在接地线上）。"""
    out = []
    for f in range(n):
        t = f / (n - 1)
        e = _smooth(t)
        pop = math.exp(-f / 2.2)
        sy = 1.0 + 0.085 * pop - 0.52 * e
        sx = 1.0 - 0.05 * pop + 0.32 * e
        out.append(dict(sy=sy, sx=sx,
                        rot=7.5 * math.sin(t * 4 * math.pi) * (1 - e),
                        dx=0.0, dy=0.0))
    return out


def _death2(n=18):
    """向前扑倒：绕脚踝转到 −90° 就地躺平，再整体抬高使其贴地（否则会半埋）。

    plant=False：这一剪辑本来就该「离开站立那条脚线」，交给抬升量自己控制。
    """
    out = []
    for f in range(n):
        t = f / (n - 1)
        e = _smooth(t)
        out.append(dict(sy=1.0 - 0.10 * e, sx=1.0 + 0.05 * e,
                        rot=-90.0 * e,
                        dx=0.0, dy=-32.0 * e, plant=False))
    return out


def _swim(n=10):
    out = []
    for f in range(n):
        p = 2 * math.pi * f / n
        out.append(dict(sy=1.0 + 0.022 * math.sin(p),
                        sx=1.0 - 0.016 * math.sin(p),
                        rot=2.0 * math.sin(p),
                        dx=0.9 * math.sin(p),
                        dy=-2.6 * (0.5 - 0.5 * math.cos(p))))
    return out


def _waterdeath(n=14):
    """落水：加速下沉 + 摊扁。plant=False —— 下沉正是这一剪辑的意义。"""
    out = []
    for f in range(n):
        t = f / (n - 1)
        e = _ease_out(t)
        out.append(dict(sy=1.0 - 0.38 * e, sx=1.0 + 0.24 * e,
                        rot=5.0 * math.sin(t * 5 * math.pi) * (1 - e),
                        dx=1.0 * e, dy=58.0 * e, plant=False))
    return out


# 名字 → (生成器, 使用的 media)
CLIP_SPECS = [
    ('Idle1',      _idle1(),       MEDIA_BODY),
    ('Idle2',      _idle2(),       MEDIA_BODY),
    ('Walk1',      _walk1(),       MEDIA_BODY),
    ('Walk2',      _walk2(),       MEDIA_BODY),
    ('Eat',        _eat(),         MEDIA_BODY),
    ('Laugh',      _laugh(),       MEDIA_LAUGH),
    ('LaughWalk',  _laugh_walk(),  MEDIA_LAUGH),
    ('Death1',     _death1(),      MEDIA_BODY),
    ('Death2',     _death2(),      MEDIA_BODY),
    ('Swim',       _swim(),        MEDIA_BODY),
    ('Waterdeath', _waterdeath(),  MEDIA_BODY),
]
# 额外别名剪辑（不新增帧，只指到已有区间）：内置默认值是 "Idle"
CLIP_ALIASES = {'Idle': 'Idle1'}


# ------------------------------------------------------------------ 主构建
def build():
    p = _load_params()
    body_src = Image.open(os.path.join(CACHE, 'cut_body.png')).convert('RGBA')
    laugh_src = Image.open(os.path.join(CACHE, 'cut_laugh.png')).convert('RGBA')
    assert (body_src.width, body_src.height) == (p['body']['w'], p['body']['h'])
    assert (laugh_src.width, laugh_src.height) == (p['laugh']['w'], p['laugh']['h'])

    base_scale = BODY_DISPLAY_H / p['body']['h']          # 140/1745（显示尺寸 / 源像素）
    # 图集按「显示尺寸 ×PACK」烘焙 ⇒ 1 个图集像素 = 1/PACK 个 node 单位。
    # （注意不是 PACK*base_scale：那是「src 像素 → 图集像素」的比，方向相反）
    s_pix = 1.0 / PACK                                     # 每个图集像素的 node 单位
    # 大笑用与站立同尺（实测比 0.789 版更有「存在感」，见 _laugh_scale_pick.png）
    laugh_scale = base_scale

    # 中性摆放：media 左上角在 node-local 的落点
    BODY_LX0 = -p['body']['axis_x'] * base_scale
    BODY_LY0 = FEET_Y - p['body']['h'] * base_scale
    LAUGH_LX0 = -p['laugh']['axis_x'] * laugh_scale
    LAUGH_LY0 = FEET_Y - p['laugh']['h'] * laugh_scale

    # ---- 图集（纵向堆叠，宽度小更安全）------------------------------
    bake = PACK * base_scale                 # 源像素 → 图集像素
    bw = max(1, int(round(body_src.width * bake)))
    bh = max(1, int(round(body_src.height * bake)))
    lw = max(1, int(round(laugh_src.width * bake)))
    lh = max(1, int(round(laugh_src.height * bake)))
    GAP = 2
    AW = max(bw, lw)
    AH = bh + GAP + lh
    atlas = Image.new('RGBA', (AW, AH), (0, 0, 0, 0))
    atlas.paste(body_src.resize((bw, bh), Image.LANCZOS), (0, 0))
    atlas.paste(laugh_src.resize((lw, lh), Image.LANCZOS), (0, bh + GAP))

    media = [
        ('NaiLong_body.png', (0, 0, bw, bh)),
        ('NaiLong_laugh.png', (0, bh + GAP, lw, lh)),
    ]
    med_meta = [
        dict(lx0=BODY_LX0, ly0=BODY_LY0),
        dict(lx0=LAUGH_LX0, ly0=LAUGH_LY0),
    ]

    # ---- 逐帧元素 ---------------------------------------------------
    # 「脚不离地」自动修正：绕脚底 pivot 旋转/倾斜的姿态会把身体后下角压到地面以下
    # （实测 Eat 前倾会让最低像素沉到 ~51，而内置僵尸恒 ≤45）。
    # 这里对声明 plant=True 的帧做一次抬升，使该帧最低可见像素恰好落在 FEET_Y 上；
    # 死亡/溺亡剪辑显式 plant=False（下沉是设计预期）。
    # 每个 media 在**图集里**的可见像素 bbox（相对该 media rect 左上角）。
    # 用图集而非源图，保证与最终烘焙出的像素完全一致。
    vis_box = {}
    for midx, (_nm, rect) in enumerate(media):
        rx, ry, rw, rh = (int(round(v)) for v in rect)
        vis_box[midx] = atlas.crop((rx, ry, rx + rw, ry + rh)).getbbox()

    frames = []          # 每帧: [elem] （单元素，单层）
    clips = {}
    cursor = 0
    PIVOT = (0.0, FEET_Y)
    lifted = 0
    for name, anim, midx in CLIP_SPECS:
        start = cursor
        for a in anim:
            Lin, t = _affine(a['sy'], a['sx'], a['rot'], a['dx'], a['dy'], PIVOT)
            lx0 = med_meta[midx]['lx0']
            ly0 = med_meta[midx]['ly0']

            xx = s_pix * Lin[0]
            xy = s_pix * Lin[2]
            yx = s_pix * Lin[1]
            yy = s_pix * Lin[3]
            ox = Lin[0] * lx0 + Lin[1] * ly0 + t[0]
            oy = Lin[2] * lx0 + Lin[3] * ly0 + t[1]

            if a.get('plant', True):
                vb = vis_box.get(midx)
                if vb is not None:
                    # node = (ox,oy) + (xx,yx ; xy,yy) @ (vx,vy)
                    ys = []
                    for vx, vy in ((vb[0], vb[1]), (vb[2] - 1, vb[1]),
                                   (vb[0], vb[3] - 1), (vb[2] - 1, vb[3] - 1)):
                        ys.append(oy + xy * vx + yy * vy)
                    y_bottom = max(ys)
                    if y_bottom > FEET_Y:
                        oy += FEET_Y - y_bottom
                        lifted += 1

            frames.append(dict(mediaId=midx, xx=xx, xy=xy, yx=yx, yy=yy,
                               ox=ox, oy=oy, alpha=255))
            cursor += 1
        clips[name] = (start, cursor - 1)
    frame_max = cursor
    for alias, target in CLIP_ALIASES.items():
        clips[alias] = clips[target]

    # ---- 根运动：给每个 GROUND_CLIPS 生成「一条完整锯齿」----------------
    # 第 k 帧 = (k+1)·step（不是 k·step）：保证没有一帧的 origin 是 0，
    # 因为 TryGetManagedLayerPositionForRender 会把 Identity 变换判为无效。
    ground = {}
    for name in GROUND_CLIPS:
        s0, s1 = clips[name]
        for k in range(s1 - s0 + 1):
            ground[s0 + k] = (k + 1) * GROUND_PX_PER_FRAME

    return dict(atlas=atlas, media=media, frames=frames, clips=clips,
                frame_max=frame_max, scale=s_pix, base_scale=base_scale,
                lifted=lifted, ground=ground,
                params=p)


# ------------------------------------------------------------------ dat 写入
def _pstr(s):
    b = s.encode('utf8')
    return struct.pack('<I', len(b)) + b


def write_dat(path, atlas, media, frames, clips, frame_max, frame_rate=FRAME_RATE,
              ground=None):
    AW, AH = atlas.width, atlas.height
    px = atlas.tobytes()          # RGBA8, row-major top-left
    assert len(px) == AW * AH * 4
    out = bytearray()
    out += struct.pack('<f', frame_rate)
    out += struct.pack('<HHH', frame_max, AW, AH)
    out += struct.pack('<q', AW * AH * 4)
    out += px
    # media 表
    out += struct.pack('<H', len(media))
    for name, (x, y, w, h) in media:
        out += _pstr(name)
        out += struct.pack('<ffff', x, y, w, h)
    # layer 表：body(0) / laugh(1) / _ground(2)
    # `.dat` 的原生结构就是「每层 × 每帧 × 若干元素」，所以加一层不需要改格式。
    ground = ground or {}
    out += struct.pack('<H', len(LAYERS_ALL))
    for li, lname in enumerate(LAYERS_ALL):
        out += _pstr(lname)
        for f in range(frame_max):
            el = frames[f]
            if li == 2:
                # _ground：alpha=0（不可见），只提供逐帧位移给 GroundMoveComponent
                if f in ground:
                    out += struct.pack('<H', 1)
                    out += struct.pack('<H', el['mediaId'])
                    out += struct.pack('<ffff', 1.0, 0.0, 0.0, 1.0)
                    out += struct.pack('<ff', ground[f], GROUND_OY)
                    out += struct.pack('<I', 0)
                else:
                    out += struct.pack('<H', 0)
                continue
            mine = ((li == 0 and el['mediaId'] == MEDIA_BODY) or
                    (li == 1 and el['mediaId'] == MEDIA_LAUGH))
            out += struct.pack('<H', 1 if mine else 0)
            if mine:
                out += struct.pack('<H', el['mediaId'])
                out += struct.pack('<ffff', el['xx'], el['xy'], el['yx'], el['yy'])
                out += struct.pack('<ff', el['ox'], el['oy'])
                out += struct.pack('<I', el['alpha'])
    # clip 表
    out += struct.pack('<H', len(clips))
    for name, (s0, s1) in clips.items():
        out += _pstr(name)
        out += struct.pack('<HH', s0, s1)
    # 事件帧表（未使用）
    out += struct.pack('<H', 0)
    blob = bytes(out)
    open(path, 'wb').write(blob)
    return blob


# ------------------------------------------------------------------ tres 写入
def _fmt_i(v):
    return 'PackedInt32Array(%s)' % ', '.join(str(int(x)) for x in v)


def _fmt_f(v):
    return 'PackedFloat32Array(%s)' % ', '.join(repr(float(x)) for x in v)


def write_tres(path, media, frames, clips, frame_max, anime_basename='NaiLong',
               atlas_name='NaiLongAtlas.png', frame_rate=FRAME_RATE, ground=None):
    ground = ground or {}
    fo, fc = [], []
    keys, mids, lids, orders, flags, trs, alphas = [], [], [], [], [], [], []
    for f in range(frame_max):
        fo.append(len(keys))
        cnt = 0
        el = frames[f]
        # 按 layer id 顺序铺，保证与 .dat 的层表顺序一致（省得两边语义漂移）
        for li in range(len(LAYERS_ALL)):
            if li == 2:
                if f not in ground:
                    continue
                # _ground：单位矩阵 + 逐帧位移，alpha=0 ⇒ 不可见，只喂 GroundMoveComponent
                keys.append((li << 16) | 0)
                mids.append(el['mediaId'])
                lids.append(li)
                orders.append(li)
                flags.append(0)
                trs += [1.0, 0.0, 0.0, 1.0, ground[f], GROUND_OY]
                alphas.append(0.0)
                cnt += 1
                continue
            if (li == 0 and el['mediaId'] == MEDIA_BODY) or \
               (li == 1 and el['mediaId'] == MEDIA_LAUGH):
                keys.append((li << 16) | 0)
                mids.append(el['mediaId'])
                lids.append(li)
                orders.append(li)
                flags.append(0)
                trs += [el['xx'], el['xy'], el['yx'], el['yy'], el['ox'], el['oy']]
                alphas.append(1.0)
                cnt += 1
        fc.append(cnt)
    N = len(keys)
    assert sum(fc) == N, (sum(fc), N)
    assert len(trs) == N * 6

    mr = []
    for (_n, (x, y, w, h)) in media:
        mr += [x, y, w, h]

    layer_dict = {LAYERS_ALL[i]: i for i in range(len(LAYERS_ALL))}
    for j, nm in enumerate(('AnimeClips', 'AnimeEvents')):
        layer_dict[nm] = len(LAYERS_ALL) + j

    L = []
    L.append('[gd_resource type="Resource" script_class="AdobeAnimateData" format=4]')
    L.append('')
    L.append('[ext_resource type="Script" path="res://addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs" id="1"]')
    L.append('')
    L.append('[resource]')
    L.append('script = ExtResource("1")')
    L.append('animeFile = "./%s.dat"' % anime_basename)
    L.append('frameRate = %s' % repr(float(frame_rate)))
    L.append('frameMax = %d' % frame_max)
    L.append('frameOffsets = %s' % _fmt_i(fo))
    L.append('frameCounts = %s' % _fmt_i(fc))
    L.append('sliceKeys = %s' % _fmt_i(keys))
    L.append('sliceMediaIds = %s' % _fmt_i(mids))
    L.append('sliceLayerIds = %s' % _fmt_i(lids))
    L.append('sliceDrawOrders = %s' % _fmt_i(orders))
    L.append('sliceFlags = %s' % _fmt_i(flags))
    L.append('sliceTransforms = %s' % _fmt_f(trs))
    L.append('sliceAlpha = %s' % _fmt_f(alphas))
    L.append('mediaRects = PackedVector4Array(%s)' %
             ', '.join(repr(float(v)) for v in mr))
    L.append('events = [%s]' % ', '.join('[]' for _ in range(frame_max)))
    cl = ['"%s": Vector2i(%d, %d)' % (n, s[0], s[1]) for n, s in clips.items()]
    L.append('clips = {')
    L.append(',\n'.join(cl))
    L.append('}')
    md = ['"%s": %d' % (n, i) for i, (n, _r) in enumerate(media)]
    L.append('mediaDictionary = {')
    L.append(',\n'.join(md))
    L.append('}')
    ld = ['"%s": %d' % (n, layer_dict[n]) for n in sorted(layer_dict, key=layer_dict.get)]
    L.append('layerDictionary = {')
    L.append(',\n'.join(ld))
    L.append('}')
    L.append('rasterCompositeData = null')
    L.append('metadata/_custom_type_script = "res://addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs"')
    L.append('')
    open(path, 'w', encoding='utf8', newline='\n').write('\n'.join(L))
    return N


# ------------------------------------------------------------------ 预览渲染
def _render_one(model, fi, zoom, box=None):
    """把一个帧渲染成贴片。box=(x0,x1,y0,y1) 节点局部视野，默认 (-100,100,-110,80)。"""
    if box is None:
        box = (-100.0, 100.0, -110.0, 80.0)
    bx0, bx1, by0, by1 = box
    atlas = model['atlas']
    media = model['media']
    el = model['frames'][fi]
    _nm, (rx, ry, rw, rh) = media[el['mediaId']]
    tile = atlas.crop((rx, ry, rx + rw, ry + rh))
    xx, xy, yx, yy = el['xx'], el['xy'], el['yx'], el['yy']
    ox, oy = el['ox'], el['oy']
    det = xx * yy - xy * yx
    TW, TH = int(round((bx1 - bx0) * zoom)), int(round((by1 - by0) * zoom))
    sheet = Image.new('RGBA', (TW, TH), (24, 24, 28, 255))

    def to_screen(nx, ny):
        return (nx - bx0) * zoom, (ny - by0) * zoom

    if abs(det) > 1e-12:
        ixx, ixy = yy / det, -xy / det
        iyx, iyy = -yx / det, xx / det
        cs = [(0, 0), (rw, 0), (0, rh), (rw, rh)]
        pts = [to_screen(ox + xx * a + yx * b, oy + xy * a + yy * b) for a, b in cs]
        x0 = max(0, int(min(p[0] for p in pts)) - 1)
        x1 = min(TW - 1, int(max(p[0] for p in pts)) + 1)
        y0 = max(0, int(min(p[1] for p in pts)) - 1)
        y1 = min(TH - 1, int(max(p[1] for p in pts)) + 1)
        tpx = tile.load()
        dst = sheet.load()
        for dy in range(y0, y1 + 1):
            for dx in range(x0, x1 + 1):
                ux = dx / zoom + bx0 - ox
                uy = dy / zoom + by0 - oy
                sx = ixx * ux + iyx * uy
                sy = ixy * ux + iyy * uy
                if sx < 0 or sy < 0 or sx >= rw - 1e-6 or sy >= rh - 1e-6:
                    continue
                r, g, b, a = tpx[int(sx), int(sy)]
                if a == 0:
                    continue
                dr, dg, db, da = dst[dx, dy]
                al = a / 255.0
                dst[dx, dy] = (int(r * al + dr * (1 - al)),
                               int(g * al + dg * (1 - al)),
                               int(b * al + db * (1 - al)),
                               min(255, int(a + da * (1 - al))))
    gy = int(round((FEET_Y - by0) * zoom))
    if 0 <= gy < TH:
        d = sheet.load()
        for x in range(TW):
            d[x, gy] = (78, 78, 86, 255)      # 接地线参考
    return sheet


def render_sheet(model, clip, out_path, zoom=2.2, per_row=8, box=None):
    s0, s1 = model['clips'][clip]
    idxs = list(range(s0, s1 + 1))
    tiles = [_render_one(model, i, zoom, box) for i in idxs]
    tw, th = tiles[0].size
    rows = (len(tiles) + per_row - 1) // per_row
    out = Image.new('RGBA', (tw * min(per_row, len(tiles)) + 4, th * rows + 4),
                    (12, 12, 14, 255))
    for k, t in enumerate(tiles):
        out.alpha_composite(t, ((k % per_row) * tw, (k // per_row) * th))
    out.save(out_path)
    return out_path


def render_strip(model, clip, picks, out_path, zoom=1.9, box=None):
    s0, _ = model['clips'][clip]
    tiles = [_render_one(model, s0 + f, zoom, box) for f in picks]
    w, h = tiles[0].size
    o = Image.new('RGBA', (w * len(tiles) + 2 * (len(tiles) - 1), h), (10, 10, 12, 255))
    for i, t in enumerate(tiles):
        o.alpha_composite(t, (i * (w + 2), 0))
    o.save(out_path)
    return o.size


def main():
    import sys
    m = build()
    dat = os.path.join(CACHE, 'NaiLong.dat')
    tres = os.path.join(CACHE, 'NaiLong.tres')
    png = os.path.join(CACHE, 'NaiLongAtlas.png')
    m['atlas'].save(png)
    blob = write_dat(dat, m['atlas'], m['media'], m['frames'], m['clips'], m['frame_max'],
                     ground=m['ground'])
    N = write_tres(tres, m['media'], m['frames'], m['clips'], m['frame_max'],
                   ground=m['ground'])
    print('atlas %dx%d  media=%d  frames=%d  slices=%d'
          % (m['atlas'].width, m['atlas'].height, len(m['media']), m['frame_max'], N))
    print('  s_pix=%.6f base_scale=%.6f' % (m['scale'], m['base_scale']))
    print('  .dat %d bytes   .tres %d bytes' % (len(blob), os.path.getsize(tres)))
    print('  feet planted: %d/%d frames lifted to y=%.1f'
          % (m['lifted'], m['frame_max'], FEET_Y))
    print('  ground(根运动): %.4f px/帧 × %.1f 倍 = %.4f px/帧'
          % (NORMAL_GROUND_PX_PER_FRAME, SPEED_TIER, GROUND_PX_PER_FRAME))
    for nm in GROUND_CLIPS:
        s0, s1 = m['clips'][nm]
        px = m['ground'][s1] - m['ground'][s0] + GROUND_PX_PER_FRAME
        print('     %-12s 帧 %3d..%-3d (%2d 帧)  前进 %6.2f px  ⇒ %5.2f px/s'
              % (nm, s0, s1, s1 - s0 + 1, px, px / (s1 - s0 + 1) * FRAME_RATE))
    print('  clips:')
    for k, v in m['clips'].items():
        print('     %-12s %s' % (k, v))
    if '--sheet' in sys.argv:
        which = [a for a in sys.argv[1:] if not a.startswith('--')]
        for nm in (which or ['Idle1', 'Walk1', 'Laugh', 'Eat', 'Death1', 'Death2', 'Swim']):
            render_sheet(m, nm, os.path.join(CACHE, '_sheet_%s.png' % nm))
        print('sheets written')


if __name__ == '__main__':
    main()
