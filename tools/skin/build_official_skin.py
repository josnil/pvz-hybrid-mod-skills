# -*- coding: utf-8 -*-
"""经典 PvZ（未重置版）reanim  →  重置版（Godot4 / AdobeAnimate）外观三件套。

输入（用户提供的未重置版解包）：
  compiled/new/SuperGatling.reanim.compiled   官方 27 轨 × 87 帧 @12fps
  reanim/<IMAGE_REANIM_*>.png                 官方贴图 23 张（用到的）

输出（落 .cache，供 build_plant_super_gatling.py 的 sync_skin_assets() 同步进包）：
  SuperGatlingPea.dat        内嵌图集 + 全部时间轴（同目录同名，走 standalone 分支）
  SuperGatlingPea.tres       AdobeAnimateData 自描述 packed 数组
  SuperGatlingPeaAtlas.png   图集（人看的；.dat 像素区来源，与 .dat 内嵌字节一致）
  skin_params.json           标定结果（offset / insertLayerId / Marker2D …）
  preview_official*.png      逐帧合成预览（纯离线，不改游戏）

━━━ 映射规则（全部由内置「同角色双引擎对照」反推并数值验证）━━━
1) 轨道 → 图层：**27 轨全保留**，layerId == 轨道序号。
   证据：内置 11 个「头身分离」植物里 10 个把无图控制轨（anim_stem / anim_idle / _guide…）
   原样保留成空层；层 id 与轨道序一一对应。唯一的例外是 GatlingPeaZ（丢了开头两条
   控制轨并重排），属另一套早期转换，不采信。
   无图控制轨的「可见帧」（f>=0）会产出一枚 **locator.png（2×2 全透明）** 占位 slice，
   这是内置做法（PeaShooter 的 anim_stem 25 帧全用 locator，见其 sliceMediaIds）。
   这么做还保住了 `sliceDrawOrders == sliceLayerIds`。
2) 帧 → 帧：1:1（GatlingPeaZ 经典 60 帧 → remake frameMax 60）。
3) 变换 = **旋转**（不是 tan 斜切；4 位小数验证）：
     [Xx, Xy, Yx, Yy, Ox, Oy] = [sx·cos(kx°), sx·sin(kx°), -sy·sin(ky°), sy·cos(ky°), x, y]
   验证：GatlingPea f25 helmet 经典 kx=3.70 ky=5.80 sx=0.6030 sy=0.5690
        → 预测 (0.60174,0.038917,-0.057506,0.566086,9.95,3.6827)
        → 实测 (0.6021, 0.0388,  -0.058,    0.5661,   9.95, 3.6827)  ✓
4) **不需要任何额外缩放**：经典 sx/sy 已是最终渲染缩放
   （GatlingPeaZ 全轨 sx=sy=0.5550，png 44×22 → 渲染 24.4×12.2）。
   ★ 这一点推翻了此前「素材放大 2 倍、DISPLAY_SCALE=0.5」的假设——那只适用于自制素材。
5) SENT(-10000) = **沿上一帧继承**（编译器按「与上帧相同」去重）。首帧未定义取默认
   x=y=kx=ky=0, sx=sy=1, f=0。
6) 第 7 个 f32（imgf）：`f<0` ⇒ 该 (层,帧) 不产 slice；`f>=0` ⇒ 索引该轨的 imgnames。
   SuperGatling 实测 marker：
     body 件（backleaf/stalk/frontleaf）   -1@25          ⇒ 仅 0..24 可见
     head 件（hair/face/mouth/helmet/眼镜） -1@0, 0@25     ⇒ 仅 25..86 可见
     barrel                               -1@0, 0@56, -1@69 ⇒ 56..68
     控制轨 anim_idle -1@25 / anim_head_idle -1@0,0@25,-1@50
            anim_shooting -1@0,0@50,-1@75 / anim_power -1@0,0@75
7) clip 边界直接来自上面控制轨 marker：
     BodyIdle(0,24) / HeadIdle(25,49) / HeadFire(50,86)
   命名对齐游戏惯例（BodyIdle/HeadIdle/HeadFire 是内置「头身分离植物」标准三 clip，
   GatlingPea / PeaShooter / SnowPea / … 共 11 例）。HeadFire 覆盖「射击 50..74 + 大招
   75..86」整段——本 Mod 由 FireComponent 循环播 HeadFire，只给 50..74 就看不到大招。
8) 媒体：一张 .dat 只能内嵌一张图集 ⇒ 全部 media 打进同一张；mediaRects = 每张 PNG 的
   **完整矩形**（内置实测一图一 media，不切帧）。
   media id = **显示名按大小写不敏感排序**后的序号（内置四例逐一核对通过：
   `locator.png` 在 PeaShooter 里是 0、在 GatlingPea 里是 7，只有忽略大小写才排得出来）。
   .tres 文本里的字典键序则是 Godot 的 **ASCII 序**（两者不同，都照抄）。
9) 根锚点：内置植物一律 `offset = (-40,-40)`（PeaShooter / GatlingPea / GatlingPeaZ 全同）
   ⇒ 意味着经典 reanim 的 (40,40) 就是「种植锚点」。实测 SuperGatling 与 GatlingPeaZ 的
   落地线同为 y=77.7（复用同一批 PeaShooter 叶/茎图）⇒ 同一坐标系，沿用 (-40,-40)。
10) 头身分离：Head 子节点 `position=(0,0)`、`offset` 与根相同 —— 因为本 Mod 的 body/head
    图层来自**同一份 reanim、同一坐标系**，数学上必须零偏移对齐。
    （内置 GatlingPea/PeaShooter 的 Head.position≈(3.6,3.6)、offset=(-36,-46) 是它们手工
      微调自己的头素材，不适用。）
11) 插层：`insertLayerId = max(body 图层 id) + 1`。内置 11 例全部成立
    （PeaShooter/GatlingPea/… =8、ReCactus=11、SunflowerPea=5、ThreeCactus=9）。
    本 Mod body 图层 = 8..15 ⇒ insertLayerId = 16（== anim_idle 层，正好复刻
    PeaShooter「body 0..7 / anim_stem=8」的同构关系）。
12) ★★ 发射事件：事件帧表就是**常规攻击唯一的发射触发源**（证据链见常量块 FIRE_EVENT_*）。
    只写动画不写事件 = 「只有动画、一颗子弹都没有」。本 Mod 规格 = 每 1.5 秒 1 轮 7 颗
    ⇒ 每循环**恰好 1 个** `fire` 事件，帧号由 `derive_fire_frames()` 从动画自身推导
    （射击段内头部前冲达到最大伸出的第一帧 = f62），并断言其相对 HeadFire 起点偏移
    == 内置单发家族（PeaShooter 等 7 例）的 +12。
13) 头部抬升：`Head.position = (0, -HEAD_RAISE_PX)`。同源同坐标系下 Head.position 本应为
    (0,0)（第 10 条），但官方大头盔素材在该位置会压住茎叶 ⇒ 由多档对照渲染
    （`.cache/calib_head_raise.py`）人工选值。只动 Head.position，不动 Head.offset，
    故 Marker2D（Head 子节点）一起上移，炮口始终粘在炮管上。
"""
import json
import math
import os
import re
import struct
import sys

CACHE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CACHE)

from reanim_decode import decode, unwrap, REC, SENT      # noqa: E402
import pnglib                                            # noqa: E402

# ---------------------------------------------------------------- 输入
CLASSIC = r"D:/zzz/extract_1789988101"
REANIM_BIN = os.path.join(CLASSIC, "compiled", "new", "SuperGatling.reanim.compiled")
REANIM_PNG_DIR = os.path.join(CLASSIC, "reanim")

# ---------------------------------------------------------------- 输出
KEY = "SuperGatlingPea"
OUT_TRES = os.path.join(CACHE, KEY + ".tres")
OUT_DAT = os.path.join(CACHE, KEY + ".dat")
OUT_ATLAS = os.path.join(CACHE, KEY + "Atlas.png")
OUT_PARAMS = os.path.join(CACHE, "skin_params.json")
OUT_PREVIEW = os.path.join(CACHE, "preview_official.png")

FRAME_RATE = 12.0
ANIME_FILE = "./%s.dat" % KEY                       # 同目录同名 ⇒ ResolveAnimeFilePath 兜底
DATA_SCRIPT = "res://addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs"

CLIP_NAMES = {"BodyIdle": (0, 24), "HeadIdle": (25, 49), "HeadFire": (50, 86)}

BODY_LAST_FRAME = 24          # BodyIdle 末帧（含）
LOCATOR = "locator.png"

# ---------------------------------------------------------------- 发射事件
#
# ★★ 没有这一节 = 「只有动画、一颗子弹都没有」（2026-09-21 实机复现并定位）。
#   发射链路：AdobeAnimateSprite 每帧推进时查 `events[frameIdx]`，非空则
#     `OnAnimeEvent?.Invoke(dict["Command"], dict["Argument"])`（AdobeAnimateSprite.cs:5295-5328）
#   → FireComponent 在挂载时 `sprite.OnAnimeEvent += AnimeEvent`（FireComponent.cs:1484）
#   → `AnimeEvent()` 里 `command ∈ fireEventName.Split("&")`（fireEventName 默认 "fire"，:343）
#   → `FireConfiguredVolley()` → `Fire()` 才真正生成子弹（:3376-3427）。
#   ⇒ **动画事件表是常规攻击唯一的发射触发源**；插件只负责大招（走 `fire.Fire()` 直调）。
#
# 帧号怎么定（两条独立实测，见 .cache/ab_tres_layers.py / probe_tres_mouth.py）：
#   ① 重置版内置 143 个植物里**事件数 == 每次攻击的豌豆数**；单发家族
#      （PeaShooter / SnowPea / ReCactus / SunflowerPea / SunPeashooter / IceSpearPea /
#        PeaShooterSingle，7 例）的 HeadFire 一律 (50,74) 且**恰好 1 个事件 @ f62**
#      == HeadFire 起点 + 12。
#   ② 内置 GatlingPea / ThreeCactus：事件全部落在「嘴部图层 x 严格局部极大 − 1」。
#   本 Mod 玩法规格（`植物Mod-超级机枪射手.md`:45-46,582）= 每 1.5 秒 **1 轮 7 颗**
#   ⇒ 需要且只需要 1 个事件，取「射击段内头部前冲行程达到最大伸出的**第一帧**」。
FIRE_EVENT_COMMAND = "fire"
FIRE_EVENT_ARGUMENT = ""
SHOOT_TRACK = "anim_shooting"        # 无图控制轨：只有它「可见」的帧才是射击段
MOUTH_TRACK = "GatlingPea_mouth"     # 头与茎相接那一块，发射时随炮身前冲（x 位移最大）
BUILTIN_HEADFIRE_EVENT_OFFSET = 12   # 内置单发家族：事件帧 == HeadFire 起点 + 12
EXTREME_TOLERANCE_PX = 1.0           # 「已达最大伸出」的容差，见 derive_fire_frames

# ---------------------------------------------------------------- 头部抬升
#
# 「头有点偏下」（2026-09-21 用户反馈）：本 Mod 的 body/head 图层**同源同坐标系**
#   ⇒ Head.position 数学上应为 (0,0)，但官方 SuperGatling 的头部素材（大头盔）在
#   该位置会把茎叶整片压住 ⇒ 观感上「头坐进叶丛里」。抬高只改 Head 节点 position，
#   Head.offset 不动 ⇒ Marker2D 作为 Head 子节点一起上移，炮口始终粘在炮管上。
# 取值由 .cache/calib_head_raise.py 的多档对照渲染（0/3/6/9/12/16 px）人工挑选：
#   0/3 = 头压住茎叶；6 = 好转；**8~9 = 茎叶与茎秆都清晰可见、头正坐在茎顶**；
#   12/16 = 开始脱节。取 8.0（「调高一点」的温和值，落在最佳区间）。
HEAD_RAISE_PX = 8.0

ROOT_ANCHOR = (40.0, 40.0)    # 经典 reanim 坐标里的种植锚点 ⇒ offset = -ROOT_ANCHOR
ROOT_OFFSET = (-ROOT_ANCHOR[0], -ROOT_ANCHOR[1])
HEAD_OFFSET = (-ROOT_ANCHOR[0], -ROOT_ANCHOR[1])
HEAD_POSITION = (0.0, -HEAD_RAISE_PX)

SHELF_W = 256
PAD = 1

FIELDS = ("x", "y", "kx", "ky", "sx", "sy", "f")


# ============================================================ reanim 解析

def media_display_name(image_name):
    """IMAGE_REANIM_SUPERGATLING_HAIR5 → SuperGatlingPea_hair5.png（对齐重置版命名习惯）。"""
    assert image_name.startswith("IMAGE_REANIM_"), image_name
    body = image_name[len("IMAGE_REANIM_"):]
    for prefix, disp in (("SUPERGATLING_", "SuperGatlingPea_"),
                         ("PEASHOOTER_", "PeaShooter_"),
                         ("GATLINGPEA_", "GatlingPea_")):
        if body.startswith(prefix):
            return disp + body[len(prefix):].lower() + ".png"
    raise KeyError("未登记命名的贴图前缀：" + image_name)


def classic_png_path(image_name):
    base = image_name[len("IMAGE_REANIM_"):].lower() + ".png"
    for f in os.listdir(REANIM_PNG_DIR):
        if f.lower() == base:
            return os.path.join(REANIM_PNG_DIR, f)
    raise FileNotFoundError(os.path.join(REANIM_PNG_DIR, base))


class Track(object):
    def __init__(self, index, name, nframes, frames, images):
        self.index = index
        self.name = name
        self.nframes = nframes
        self.frames = frames            # [(11 个 f32), ...]
        self.images = images            # trailer 的 IMAGE_REANIM_* 列表


def load_tracks():
    d = decode(REANIM_BIN)
    raw = unwrap(REANIM_BIN)
    out = []
    for t in d["tracks"]:
        if "index" not in t:
            raise RuntimeError("reanim 解析失败：" + repr(t))
        o, n = t["data_off"], t["nframes"]
        frames = [tuple(struct.unpack_from("<11f", raw, o + j * REC)) for j in range(n)]
        out.append(Track(t["index"], t["name"], n, frames, list(t["imgnames"])))
    # ⚠️ 末轨 trailer 的图片名表：decode 靠「找下一个轨道名」定界，末轨天然拿不到
    #    ⇒ 自己从文件尾补扫一次，否则 overlay2（IMAGE_REANIM_SUPERGATLING_OVERLAY2）会丢。
    last = out[-1]
    if not last.images:
        fend = d["tracks"][-1]["data_off"] + last.nframes * REC
        import re as _re
        found = [s.decode() for s in _re.findall(rb"IMAGE_[A-Z0-9_]+", raw[fend:])]
        if found:
            last.images = found
    return out


def carry(track, key):
    """按「继承上一帧」解出整条序列；首帧未定义用默认值。"""
    defaults = {"x": 0.0, "y": 0.0, "kx": 0.0, "ky": 0.0, "sx": 1.0, "sy": 1.0, "f": 0.0}
    idx = FIELDS.index(key)
    cur = defaults[key]
    res = []
    for fr in track.frames:
        v = fr[idx]
        if v != SENT:
            cur = v
        res.append(cur)
    return res


# ============================================================ 图集装箱

def shelf_pack(items, width=SHELF_W, pad=PAD):
    """items: [(key, w, h)] → (atlasW, atlasH, {key: (x,y,w,h)})，按高度降序装箱。"""
    order = sorted(items, key=lambda it: (-it[2], -it[1]))
    rects = {}
    x, y, shelf_h, used_w = pad, pad, 0, 0
    for key, w, h in order:
        if x + w + pad > width and shelf_h > 0:
            y += shelf_h + pad
            x = pad
            shelf_h = 0
        rects[key] = (x, y, w, h)
        x += w + pad
        shelf_h = max(shelf_h, h)
        used_w = max(used_w, x)
    return max(width, used_w + pad), y + shelf_h + pad, rects


def round_up4(v):
    return (v + 3) // 4 * 4


# ============================================================ 发射帧推导

def derive_fire_frames(model):
    """从动画自身推导「发射事件帧」（见文件顶部 FIRE_EVENT_* 的证据链）。

    规则：射击段（`anim_shooting` 可见帧区间）内，头部前冲块（`GatlingPea_mouth`）
          的 x 位移**首次**达到「最大伸出量」的那一帧。

    ⚠️ 为什么用「首次达最大（±1px）」而不是「严格最大」：本素材的前冲末端有一个**保持段**
       （f62..f65 的 x = 51.4/51.5/51.6/51.8，sy 恒 0.440），严格最大落在保持段末尾 f65，
       但**姿态在 f62 就已到位**。内置 PeaShooter 的同段素材没有保持段，其事件恰在严格最大
       f62。1px 容差只吸收亚像素插值噪声，不改变语义 —— 实测两例都落在 f62。

    ⚠️ 末尾两条断言是**故意的硬闸门**：一旦素材换代导致相位漂移，这里要**报错**，
       而不是悄悄生成一个「有事件但打在错帧」的包（那比没事件更难查）。
    """
    by_name = {t.name: t.index for t in model["tracks"]}
    for nm in (SHOOT_TRACK, MOUTH_TRACK):
        if nm not in by_name:
            raise RuntimeError("缺图层/轨道 %s（现有：%s）" % (nm, sorted(by_name)))

    si = by_name[SHOOT_TRACK]
    vis = [j for j in range(model["nframes"]) if model["elements"][si][j]]
    if not vis:
        raise RuntimeError("%s 全程不可见 ⇒ 推不出射击段" % SHOOT_TRACK)
    s0, s1 = min(vis), max(vis)
    if vis != list(range(s0, s1 + 1)):
        raise RuntimeError("%s 可见帧不连续：%r" % (SHOOT_TRACK, vis))

    mi = by_name[MOUTH_TRACK]
    xs = {j: model["elements"][mi][j][0]["tr"][4]
          for j in range(s0, s1 + 1) if model["elements"][mi][j]}
    if not xs:
        raise RuntimeError("%s 在射击段内无可绘制帧" % MOUTH_TRACK)
    mx = max(xs.values())
    cand = [j for j, v in xs.items() if v >= mx - EXTREME_TOLERANCE_PX]
    frame = min(cand)                    # 首次达到最大伸出
    if abs(xs[frame] - mx) > EXTREME_TOLERANCE_PX:
        raise RuntimeError("内部矛盾：%d 未达最大伸出" % frame)

    c0, c1 = model["clips"]["HeadFire"]
    if not (c0 <= frame <= c1):
        raise RuntimeError("推导出的发射帧 %d 不在 HeadFire(%d,%d) 内" % (frame, c0, c1))
    if frame - c0 != BUILTIN_HEADFIRE_EVENT_OFFSET:
        raise RuntimeError(
            "发射帧 %d 相对 HeadFire 起点偏移 %d != 内置单发家族的 %d "
            "⇒ 素材相位变了，请重新用 .cache/probe_tres_mouth.py 标定"
            % (frame, frame - c0, BUILTIN_HEADFIRE_EVENT_OFFSET))
    return [frame], (s0, s1)


# ============================================================ 模型

def build_model():
    tracks = load_tracks()
    nframes = tracks[0].nframes
    for t in tracks:
        if t.nframes != nframes:
            raise RuntimeError("各轨帧数不一致：%s" % [(x.name, x.nframes) for x in tracks])

    # ---- 媒体表：全部 imgnames ∪ {locator.png}，id 按「大小写不敏感」排序
    names = []
    for t in tracks:
        for img in t.images:
            dn = media_display_name(img)
            if dn not in names:
                names.append(dn)
    if any(not t.images for t in tracks):
        names.append(LOCATOR)
    ordered = sorted(names, key=lambda s: (s.lower(), s))
    media_id = {n: i for i, n in enumerate(ordered)}

    # ---- 逐层逐帧解算（layerId == 轨道序号）
    elements = []                  # elements[li][frame] = [ {mediaId,tr,alpha} | … ]
    layer_slots = []               # 每层每帧的「槽位数」（内置算法：全层取最大值）
    for t in tracks:
        xs, ys = carry(t, "x"), carry(t, "y")
        kxs, kys = carry(t, "kx"), carry(t, "ky")
        sxs, sys_ = carry(t, "sx"), carry(t, "sy")
        fs = carry(t, "f")
        per = []
        for j in range(nframes):
            imgf = int(round(fs[j]))
            if imgf < 0:
                per.append([])
                continue
            if t.images:
                if imgf >= len(t.images):
                    raise RuntimeError("%s f%d imgf=%d 越界（imgs=%d）"
                                       % (t.name, j, imgf, len(t.images)))
                dn = media_display_name(t.images[imgf])
            else:
                dn = LOCATOR
            kx, ky = math.radians(kxs[j]), math.radians(kys[j])
            sx, sy = sxs[j], sys_[j]
            per.append([{
                "mediaId": media_id[dn],
                "tr": [sx * math.cos(kx), sx * math.sin(kx),
                       -sy * math.sin(ky), sy * math.cos(ky),
                       xs[j], ys[j]],
                "alpha": 1.0,
            }])
        elements.append(per)
        layer_slots.append(max(len(v) for v in per))

    # ---- 忠实复刻内置 BuildPackedRuntimeData 的打包算法
    frame_offsets, frame_counts = [], []
    slice_keys, slice_media, slice_layer = [], [], []
    slice_draw, slice_flags, slice_tr, slice_alpha = [], [], [], []
    slot = 0
    for j in range(nframes):
        frame_offsets.append(slot)
        c = 0
        num3 = 0
        for li in range(len(tracks)):
            for l in range(layer_slots[li]):
                if l < len(elements[li][j]):
                    el = elements[li][j][l]
                    if el["mediaId"] != 0xFFFF:
                        slice_keys.append((li << 16) ^ (l & 0xFFFF))
                        slice_media.append(el["mediaId"])
                        slice_layer.append(li)
                        slice_draw.append(num3)
                        slice_flags.append(0)
                        slice_tr.extend(el["tr"])
                        slice_alpha.append(el["alpha"])
                        c += 1
                        slot += 1
                num3 += 1
        frame_counts.append(c)
    total = slot

    # ---- body / head 归属 + 插层位置
    # body 判据 = 该层在 BodyIdle 段（0..24）内有「可见帧」**且用的是真实贴图**。
    # ⚠️ 必须排除「只用 locator 占位」的无图控制轨：内置 PeaShooter 的 anim_stem(8)
    #    在 0..24 有 25 枚 locator slice，但 insertLayerId 仍是 8（== max(body)=7 +1），
    #    若把 anim_stem 算进 body 就会误得 9。11 例内置中 9 例符合本口径。
    locator_id = media_id[LOCATOR]
    body, head = [], []
    for t in tracks:
        fs = carry(t, "f")
        has_real_body = any(
            fs[j] >= 0 and (t.images if t.images else None) and elements[t.index][j][0]["mediaId"] != locator_id
            for j in range(0, BODY_LAST_FRAME + 1))
        (body if has_real_body else head).append(t.index)
    insert_layer = (max(body) + 1) if body else 0

    # ---- 口径校验：任何图层都不许「跨」body/head 边界（否则头身分离会漏画）
    locator_id = media_id[LOCATOR]
    for li, t in enumerate(tracks):
        in_body = any(elements[li][j] for j in range(0, BODY_LAST_FRAME + 1))
        in_head = any(elements[li][j] for j in range(BODY_LAST_FRAME + 1, nframes))
        if in_body and in_head:
            raise RuntimeError("图层 %s 跨 body/head 边界（0..24 与 25..86 都有 slice）" % t.name)
        if not in_body and not in_head:
            raise RuntimeError("图层 %s 全程无 slice" % t.name)

    media = []                     # 按 id 序
    for dn in ordered:
        if dn == LOCATOR:
            media.append((dn, None, 2, 2, bytearray(b"\x00" * 16)))
        else:
            src = None
            for t in tracks:
                for img in t.images:
                    if media_display_name(img) == dn:
                        src = img
                        break
                if src:
                    break
            p = classic_png_path(src)
            w, h, px = pnglib.read_png(p)
            media.append((dn, p, w, h, px))

    return {
        "tracks": tracks, "nframes": nframes, "media": media, "media_id": media_id,
        "elements": elements, "layer_slots": layer_slots,
        "frame_offsets": frame_offsets, "frame_counts": frame_counts,
        "slice_keys": slice_keys, "slice_media": slice_media, "slice_layer": slice_layer,
        "slice_draw": slice_draw, "slice_flags": slice_flags, "slice_tr": slice_tr,
        "slice_alpha": slice_alpha, "n_slices": total,
        "clips": dict(CLIP_NAMES), "body_layers": body, "head_layers": head,
        "insert_layer": insert_layer,
    }


def attach_fire_frames(model):
    """把 `derive_fire_frames` 的结果挂到 model 上（单独一步，便于 main 里打印）。"""
    frames, shoot = derive_fire_frames(model)
    model["fire_frames"] = frames
    model["shoot_range"] = shoot
    return frames, shoot


def make_atlas(model):
    items = [(i, m[2], m[3]) for i, m in enumerate(model["media"])]
    aw, ah, rects = shelf_pack(items)
    aw, ah = round_up4(aw), round_up4(ah)
    atlas = pnglib.new_rgba(aw, ah)
    for i, m in enumerate(model["media"]):
        x, y, w, h = rects[i]
        pnglib.blit(atlas, aw, ah, m[4], w, h, x, y)
    model["atlas"] = (aw, ah, atlas)
    model["media_rects"] = [tuple(rects[i]) for i in range(len(model["media"]))]
    return aw, ah, atlas


# ============================================================ .dat

def pstr(s):
    b = s.encode("utf8")
    return struct.pack("<I", len(b)) + b


def write_dat(model):
    aw, ah, atlas = model["atlas"]
    out = bytearray()
    out += struct.pack("<f", FRAME_RATE)
    out += struct.pack("<H", model["nframes"])
    out += struct.pack("<H", aw)
    out += struct.pack("<H", ah)
    out += struct.pack("<q", aw * ah * 4)
    out += bytes(atlas)

    out += struct.pack("<H", len(model["media"]))
    for i, m in enumerate(model["media"]):
        r = model["media_rects"][i]
        out += pstr(m[0])
        out += struct.pack("<ffff", float(r[0]), float(r[1]), float(r[2]), float(r[3]))

    tracks = model["tracks"]
    out += struct.pack("<H", len(tracks))
    for li, t in enumerate(tracks):
        out += pstr(t.name)
        for j in range(model["nframes"]):
            per = model["elements"][li][j]
            out += struct.pack("<H", len(per))
            for el in per:
                out += struct.pack("<H", el["mediaId"])
                out += struct.pack("<ffffff", *[float(v) for v in el["tr"]])   # 6 个 f32
                out += struct.pack("<I", 0xFF)                                  # ARGB(alpha=255)

    out += struct.pack("<H", len(model["clips"]))
    for name in sorted(model["clips"]):
        s0, s1 = model["clips"][name]
        out += pstr(name)
        out += struct.pack("<HH", s0, s1)

    # 事件帧表。布局**逐字照抄引擎读取器** AdobeAnimateData.InitInternal (:1352-1372)：
    #     u16 事件条数
    #     每条: u16 帧号（★ 不是 u32）、u16 条目数
    #           每个条目: pascalString Command、pascalString Argument（顺序固定 Command 在前）
    # 帧号写成 u16 是硬约定：引擎 `int frame = file.Get16() * _frameScale;`
    out += struct.pack("<H", len(model["fire_frames"]))
    for fr in model["fire_frames"]:
        out += struct.pack("<HH", fr, 1)
        out += pstr(FIRE_EVENT_COMMAND)
        out += pstr(FIRE_EVENT_ARGUMENT)
    return bytes(out)


# ============================================================ .tres

def fmt_f(v):
    f32 = struct.unpack("<f", struct.pack("<f", float(v)))[0]
    if f32 == int(f32) and abs(f32) < 1e9:
        return str(int(f32))
    r = repr(f32)
    return ("%.9g" % f32) if ("e" in r or "E" in r) else r


def pack_int(name, vals):
    return "%s = PackedInt32Array(%s)" % (name, ", ".join(str(int(v)) for v in vals))


def pack_float(name, vals):
    return "%s = PackedFloat32Array(%s)" % (name, ", ".join(fmt_f(v) for v in vals))


def pack_vec4(name, rects):
    flat = []
    for r in rects:
        flat.extend([r[0], r[1], r[2], r[3]])
    return "%s = PackedVector4Array(%s)" % (name, ", ".join(fmt_f(v) for v in flat))


def write_tres(model):
    n = model["nframes"]
    layer_dict = {t.name: t.index for t in model["tracks"]}
    layer_dict["AnimeClips"] = len(model["tracks"])
    layer_dict["AnimeEvents"] = len(model["tracks"]) + 1
    media_dict = {m[0]: i for i, m in enumerate(model["media"])}

    lines = []
    lines.append('[gd_resource type="Resource" script_class="AdobeAnimateData" format=4]')
    lines.append("")
    lines.append('[ext_resource type="Script" path="%s" id="1"]' % DATA_SCRIPT)
    lines.append("")
    lines.append("[resource]")
    lines.append('script = ExtResource("1")')
    lines.append('animeFile = "%s"' % ANIME_FILE)
    lines.append("frameRate = %s" % fmt_f(FRAME_RATE))
    lines.append("frameMax = %d" % n)
    lines.append(pack_int("frameOffsets", model["frame_offsets"]))
    lines.append(pack_int("frameCounts", model["frame_counts"]))
    lines.append(pack_int("sliceKeys", model["slice_keys"]))
    lines.append(pack_int("sliceMediaIds", model["slice_media"]))
    lines.append(pack_int("sliceLayerIds", model["slice_layer"]))
    lines.append(pack_int("sliceDrawOrders", model["slice_draw"]))
    lines.append(pack_int("sliceFlags", model["slice_flags"]))
    lines.append(pack_float("sliceTransforms", model["slice_tr"]))
    lines.append(pack_float("sliceAlpha", model["slice_alpha"]))
    lines.append(pack_vec4("mediaRects", model["media_rects"]))
    # 事件帧表。★ 键序与内置一致（Godot 保存 Dictionary 时按 ASCII 序 ⇒ Argument 在 Command 前）。
    # 运行期真正读的是 .dat（animeFile 指向 ./<Key>.dat，走 standalone），这份是**编辑器/兜底**用；
    # 两边必须同时写，否则「编辑器里能播、实机不发射」这类偏差极难定位。
    fire_set = set(model["fire_frames"])
    ev = []
    for j in range(n):
        if j in fire_set:
            ev.append('[{\n"Argument": "%s",\n"Command": "%s"\n}]'
                      % (FIRE_EVENT_ARGUMENT, FIRE_EVENT_COMMAND))
        else:
            ev.append("[]")
    lines.append("events = [" + ", ".join(ev) + "]")
    # 字典：Godot 保存 .tres 时键按 ASCII 序（内置实测）
    lines.append("clips = {")
    lines.append(",\n".join('"%s": Vector2i(%d, %d)' % (k, model["clips"][k][0], model["clips"][k][1])
                            for k in sorted(model["clips"])))
    lines.append("}")
    lines.append("mediaDictionary = {")
    lines.append(",\n".join('"%s": %d' % (k, media_dict[k]) for k in sorted(media_dict)))
    lines.append("}")
    lines.append("layerDictionary = {")
    lines.append(",\n".join('"%s": %d' % (k, layer_dict[k]) for k in sorted(layer_dict)))
    lines.append("}")
    lines.append("rasterCompositeData = null")
    lines.append('metadata/_custom_type_script = "%s"' % DATA_SCRIPT)
    lines.append("")
    return "\n".join(lines)


# ============================================================ 标定：炮口

def calibrate_muzzle(model):
    """从 barrel 轨求出「完全伸出」那一帧的不透明炮口点（经典 reanim 坐标）。

    再用同法量内置 GatlingPea 的炮口，与其已知 Marker2D 反推出的炮口对比，
    得出「内置习惯的内缩量」，本 Mod 沿用同一内缩量。
    """
    def barrel_tip(track_name, png_names=None):
        li = None
        for t in model["tracks"]:
            if t.name == track_name:
                li = t.index
        if li is None:
            return None
        best = None
        for j in range(model["nframes"]):
            if not model["elements"][li][j]:
                continue
            el = model["elements"][li][j][0]
            m = model["media"][el["mediaId"]]
            w, h, px = m[2], m[3], m[4]
            bb = pnglib.alpha_bbox(px, w, h)
            if not bb:
                continue
            Xx, Xy, Yx, Yy, Ox, Oy = el["tr"]
            tx = (bb[0] + bb[2]) * 0.5            # 不透明区水平中段（取最右不透明列）
            ty = (bb[1] + bb[3]) * 0.5
            rx = Ox + Xx * bb[2] + Yx * ty
            ry = Oy + Xy * bb[2] + Yy * ty
            if best is None or rx > best[1]:
                best = (j, rx, ry, bb)
        return best
    return barrel_tip


def calibrate_reference():
    """内置 GatlingPea 的参考值：Marker2D 反推的炮口点（经典坐标）。"""
    # TowerDefensePlantGatlingPea.tscn: 根 offset=(-40,-40); Head position=(3.6000023,3.616665),
    # offset=(-36,-46); Marker2D(position)=(31.740002,-17.82) 是 Head 的子节点。
    marker_local = (31.740002, -17.82)
    head_pos = (3.6000023, 3.616665)
    root_offset = (-40.0, -40.0)
    return (marker_local[0] + head_pos[0] - root_offset[0],
            marker_local[1] + head_pos[1] - root_offset[1])


# ============================================================ 预览渲染

def render_frame(model, frame, ox=40, oy=40, cw=130, ch=120, body_frame=None, head_dy=0.0):
    """按 2×2 矩阵 + 平移反向采样合成一帧（纯离线肉眼验收）。

    body_frame 不为 None 时，body 图层改用该帧（复刻运行时：根循环 BodyIdle，
    头子精灵播 HeadIdle/HeadFire）；此时 head_dy 会额外把 head 图层整体上移
    （= Sprite 场景里 Head.position.y，复刻「头部抬升」后的实机观感）。
    """
    ox, oy = int(round(ox)), int(round(oy))
    aw, ah, atlas = model["atlas"]
    canvas = pnglib.new_rgba(cw, ch)
    ntracks = len(model["tracks"])
    if body_frame is None:
        order = [(li, frame, 0.0) for li in range(ntracks)]
    else:
        # ★ 复刻运行时绘制顺序：根精灵自己那棵树(0..insertLayerId-1) → Head 子树整棵 →
        #   根精灵剩下的图层(insertLayerId..)。用「另一段帧号」画的层天然产不出 slice
        #   （body 件在 25..86 的 f=-1、head 件在 0..24 的 f=-1），所以多画一遍是无害的。
        ins = model["insert_layer"]
        order = [(li, body_frame, 0.0) for li in range(ntracks)]                    # 根（有效部分 = body）
        order += [(li, frame, -abs(head_dy)) for li in range(ntracks)]              # Head 子树（整棵，含 hair）
        order += [(li, body_frame, 0.0) for li in range(ins, ntracks)]              # 根在插层之上的部分
    for li, use, dy in order:
        per = model["elements"][li][use]
        if not per:
            continue
        el = per[0]
        rx, ry, rw, rh = [int(v) for v in model["media_rects"][el["mediaId"]]]
        Xx, Xy, Yx, Yy, tx, ty = el["tr"]
        ty += dy
        det = Xx * Yy - Xy * Yx
        if abs(det) < 1e-9:
            continue
        ixx, ixy = Yy / det, -Xy / det
        iyx, iyy = -Yx / det, Xx / det
        corners = [(0, 0), (rw, 0), (0, rh), (rw, rh)]
        px_ = [tx + Xx * a + Yx * b for a, b in corners]
        py_ = [ty + Xy * a + Yy * b for a, b in corners]
        x0 = max(0, int(min(px_)) - 1 + ox)
        x1 = min(cw - 1, int(max(px_)) + 1 + ox)
        y0 = max(0, int(min(py_)) - 1 + oy)
        y1 = min(ch - 1, int(max(py_)) + 1 + oy)
        for dy in range(y0, y1 + 1):
            for dx in range(x0, x1 + 1):
                ux = dx - ox - tx
                uy = dy - oy - ty
                sx = ixx * ux + iyx * uy
                sy = ixy * ux + iyy * uy
                if sx < 0 or sy < 0 or sx >= rw - 1e-6 or sy >= rh - 1e-6:
                    continue
                ax_, ay_ = rx + int(sx), ry + int(sy)
                if ax_ < 0 or ay_ < 0 or ax_ >= aw or ay_ >= ah:
                    continue
                sr, sg, sb, sa = pnglib.get_px(atlas, aw, ax_, ay_)
                if sa == 0:
                    continue
                d = pnglib.get_px(canvas, cw, dx, dy)
                a = sa / 255.0
                pnglib.set_px(canvas, cw, dx, dy, (
                    int(sr * a + d[0] * (1 - a)),
                    int(sg * a + d[1] * (1 - a)),
                    int(sb * a + d[2] * (1 - a)),
                    min(255, int(sa + d[3] * (1 - a)))))
    return cw, ch, canvas


def render_sheet(model, frames, path, cols=6, composed=False, head_dy=0.0):
    tiles = [render_frame(model, f, body_frame=(f % (BODY_LAST_FRAME + 1)) if composed else None,
                          head_dy=head_dy if composed else 0.0)
             for f in frames]
    cw, ch = tiles[0][0], tiles[0][1]
    rows = (len(tiles) + cols - 1) // cols
    gap = 4
    W = cols * cw + (cols + 1) * gap
    H = rows * ch + (rows + 1) * gap
    sheet = pnglib.new_rgba(W, H, (24, 24, 30, 255))
    for i, (w, h, c) in enumerate(tiles):
        pnglib.blit(sheet, W, H, c, w, h, gap + (i % cols) * (cw + gap),
                    gap + (i // cols) * (ch + gap))
    pnglib.write_png(path, W, H, sheet)
    return W, H


# ============================================================ 自检（含 on-disk 断言）

def checks(model, dat_bytes, tres_text, params):
    fails = []
    aw, ah, atlas = model["atlas"]
    n = model["nframes"]

    # 1) .dat 头自洽
    fr = struct.unpack_from("<f", dat_bytes, 0)[0]
    fmax, daw, dah = struct.unpack_from("<HHH", dat_bytes, 4)
    pbc = struct.unpack_from("<q", dat_bytes, 10)[0]
    if abs(fr - FRAME_RATE) > 1e-6:
        fails.append("dat frameRate %r" % fr)
    if fmax != n:
        fails.append("dat frameMax %d != %d" % (fmax, n))
    if (daw, dah) != (aw, ah):
        fails.append("dat 图集 %dx%d != %dx%d" % (daw, dah, aw, ah))
    if pbc != aw * ah * 4:
        fails.append("dat pixelByteCount %d != %d" % (pbc, aw * ah * 4))
    if len(dat_bytes) < 18 + pbc:
        fails.append("dat 长度不足")
    if dat_bytes[18:22] != bytes(atlas[0:4]):
        fails.append("dat 像素区首 4 字节 != 图集首像素")
    if bytes(dat_bytes[18:18 + pbc]) != bytes(atlas):
        fails.append("dat 内嵌像素区 != 图集（逐字节）")

    # 2) .dat 时间轴 与 .tres packed 数组互证（完整重解析 .dat 尾部）
    pos = 18 + pbc
    nmedia = struct.unpack_from("<H", dat_bytes, pos)[0]
    pos += 2
    if nmedia != len(model["media"]):
        fails.append("dat media 数 %d != %d" % (nmedia, len(model["media"])))
    for i in range(nmedia):
        ln = struct.unpack_from("<I", dat_bytes, pos)[0]
        pos += 4 + ln
        pos += 16
    nlayer = struct.unpack_from("<H", dat_bytes, pos)[0]
    pos += 2
    if nlayer != len(model["tracks"]):
        fails.append("dat layer 数 %d != %d" % (nlayer, len(model["tracks"])))
    n_slice = 0
    for li in range(nlayer):
        ln = struct.unpack_from("<I", dat_bytes, pos)[0]
        name = dat_bytes[pos + 4:pos + 4 + ln].decode("utf8")
        pos += 4 + ln
        if name != model["tracks"][li].name:
            fails.append("dat 层 %d 名 %r != %r" % (li, name, model["tracks"][li].name))
        for j in range(n):
            cnt = struct.unpack_from("<H", dat_bytes, pos)[0]
            pos += 2
            n_slice += cnt
            for _ in range(cnt):
                mid = struct.unpack_from("<H", dat_bytes, pos)[0]
                tr = struct.unpack_from("<ffffff", dat_bytes, pos + 2)
                col = struct.unpack_from("<I", dat_bytes, pos + 26)[0]
                if (col & 0xFF) != 255:
                    fails.append("dat 元素 alpha != 255")
                exp = model["elements"][li][j][0]
                if mid != exp["mediaId"]:
                    fails.append("dat L%d f%d mediaId %d != %d" % (li, j, mid, exp["mediaId"]))
                for a, b in zip(tr, exp["tr"]):
                    if abs(a - b) > 1e-6:
                        fails.append("dat L%d f%d 变换 %r != %r" % (li, j, tr, exp["tr"]))
                        break
                pos += 30
    # clips
    nclip = struct.unpack_from("<H", dat_bytes, pos)[0]
    pos += 2
    got_clips = {}
    for _ in range(nclip):
        ln = struct.unpack_from("<I", dat_bytes, pos)[0]
        cname = dat_bytes[pos + 4:pos + 4 + ln].decode("utf8")
        pos += 4 + ln
        c0, c1 = struct.unpack_from("<HH", dat_bytes, pos)
        pos += 4
        got_clips[cname] = [c0, c1]
    if got_clips != {k: list(v) for k, v in model["clips"].items()}:
        fails.append("dat clips %r != %r" % (got_clips, model["clips"]))
    # events（★ 帧号是 u16，与引擎 AdobeAnimateData.InitInternal 一致）
    nevent = struct.unpack_from("<H", dat_bytes, pos)[0]
    pos += 2
    got_events = {}
    for _ in range(nevent):
        eframe = struct.unpack_from("<H", dat_bytes, pos)[0]
        pos += 2
        cnt = struct.unpack_from("<H", dat_bytes, pos)[0]
        pos += 2
        entries = []
        for _2 in range(cnt):
            ss = []
            for _3 in range(2):
                ln = struct.unpack_from("<I", dat_bytes, pos)[0]
                ss.append(dat_bytes[pos + 4:pos + 4 + ln].decode("utf8"))
                pos += 4 + ln
            entries.append(tuple(ss))          # (Command, Argument) —— 引擎就是按这个顺序读
        got_events[eframe] = entries
    if pos != len(dat_bytes):
        fails.append("dat 解析终点 %d != 文件长 %d" % (pos, len(dat_bytes)))
    if sorted(got_events) != sorted(model["fire_frames"]):
        fails.append("dat 事件帧 %r != 期望 %r" % (sorted(got_events), sorted(model["fire_frames"])))
    for fr, entries in sorted(got_events.items()):
        if entries != [(FIRE_EVENT_COMMAND, FIRE_EVENT_ARGUMENT)]:
            fails.append("dat f%d 事件条目 %r != [(%r, %r)]"
                         % (fr, entries, FIRE_EVENT_COMMAND, FIRE_EVENT_ARGUMENT))
        cs = model["clips"]["HeadFire"]
        if not (cs[0] <= fr <= cs[1]):
            fails.append("dat 事件帧 %d 不在 HeadFire(%d,%d) 内" % (fr, cs[0], cs[1]))
    if n_slice != model["n_slices"]:
        fails.append("dat slice 数 %d != 模型 %d" % (n_slice, model["n_slices"]))

    # 3) .tres 与模型一致
    if params["n_slices"] != model["n_slices"]:
        fails.append("params.n_slices 不一致")
    if params["insert_layer_id"] != model["insert_layer"]:
        fails.append("insertLayerId 不一致")
    if params["clips"] != {k: list(v) for k, v in model["clips"].items()}:
        fails.append("clips 不一致")
    if len(params["body_layers"]) + len(params["head_layers"]) != len(model["tracks"]):
        fails.append("body+head 未覆盖全部图层")
    if set(params["body_layers"]) & set(params["head_layers"]):
        fails.append("body/head 有交集")
    if params["frame_max"] != n:
        fails.append("params.frame_max 不一致")

    # 4) clip 连续覆盖 0..n-1
    cover = sorted((v[0], v[1]) for v in model["clips"].values())
    if cover[0][0] != 0 or cover[-1][1] != n - 1:
        fails.append("clip 未覆盖 0..%d：%r" % (n - 1, cover))
    for i in range(1, len(cover)):
        if cover[i][0] != cover[i - 1][1] + 1:
            fails.append("clip 之间有缝/重叠：%r" % (cover,))

    # 5) sliceKeys / drawOrder 与内置口径一致
    exp_keys = [(model["slice_layer"][k] << 16) ^ 0 for k in range(model["n_slices"])]
    if model["slice_keys"] != exp_keys:
        fails.append("sliceKeys 不是 (layerId<<16)|0")
    if model["slice_draw"] != model["slice_layer"]:
        fails.append("sliceDrawOrders != sliceLayerIds")
    if sum(model["frame_counts"]) != model["n_slices"]:
        fails.append("frameCounts 之和 != slice 数")
    if len(model["slice_tr"]) != model["n_slices"] * 6:
        fails.append("sliceTransforms 长度 != n*6")
    if model["frame_offsets"][0] != 0:
        fails.append("frameOffsets[0] != 0")

    # 6) mediaRect 尺寸 == 原 PNG 尺寸
    for i, m in enumerate(model["media"]):
        r = model["media_rects"][i]
        if (r[2], r[3]) != (m[2], m[3]):
            fails.append("mediaRects[%d] 尺寸 != PNG" % i)

    # 7) ★ on-disk：读回落盘文件再断言（防「自检只比内存文本」的假绿）
    disk_tres = open(OUT_TRES, encoding="utf8").read()
    if disk_tres != tres_text:
        fails.append("磁盘 .tres 与生成文本不一致")
    if open(OUT_DAT, "rb").read() != dat_bytes:
        fails.append("磁盘 .dat 与生成字节不一致")
    dw, dh, dpx = pnglib.read_png(OUT_ATLAS)
    if (dw, dh) != (aw, ah) or bytes(dpx) != bytes(atlas):
        fails.append("磁盘图集与内存图集不一致")
    for key, val in (("frameMax = %d" % n, True), ('animeFile = "%s"' % ANIME_FILE, True)):
        if key not in disk_tres:
            fails.append("磁盘 .tres 缺 %r" % key)
    for name in sorted(model["clips"]):
        if '"%s": Vector2i(%d, %d)' % (name, model["clips"][name][0], model["clips"][name][1]) not in disk_tres:
            fails.append("磁盘 .tres 缺 clip %s" % name)
    for t in model["tracks"]:
        if '"%s": %d' % (t.name, t.index) not in disk_tres:
            fails.append("磁盘 .tres 缺图层 %s" % t.name)
    for m in model["media"]:
        if '"%s": %d' % (m[0], model["media_id"][m[0]]) not in disk_tres:
            fails.append("磁盘 .tres 缺媒体 %s" % m[0])
    # 7b. ★ .tres 事件数组：逐槽切分，非空槽必须恰为 model["fire_frames"]
    em = re.search(r"^events = \[(.*)\]\s*$", disk_tres, re.M | re.S)
    if not em:
        fails.append("磁盘 .tres 缺 events 数组")
    else:
        # 注意：正则已吃掉最外层 `[`，故 depth 从 1 起算（depth==2 才是槽内）
        depth, cur, slots = 1, "", []
        for ch in em.group(1):
            if ch == "[":
                depth += 1
                if depth == 2:
                    cur = ""
                continue
            if ch == "]":
                if depth == 2:
                    slots.append(cur)
                depth -= 1
                continue
            if depth == 2:
                cur += ch
        if len(slots) != n:
            fails.append(".tres events 槽数 %d != 帧数 %d" % (len(slots), n))
        got_fire = [i for i, c in enumerate(slots) if c.strip()]
        if got_fire != list(model["fire_frames"]):
            fails.append(".tres 事件帧 %r != 期望 %r" % (got_fire, list(model["fire_frames"])))
        want_body = '{\n"Argument": "%s",\n"Command": "%s"\n}' % (
            FIRE_EVENT_ARGUMENT, FIRE_EVENT_COMMAND)
        for i in got_fire:
            if slots[i] != want_body:
                fails.append(".tres f%d 事件体 %r 不符（期望 %r）" % (i, slots[i], want_body))
    if len(re.findall(r'"Command": "%s"' % re.escape(FIRE_EVENT_COMMAND), disk_tres)) \
            != len(model["fire_frames"]):
        fails.append(".tres 的 fire 事件条数 != %d" % len(model["fire_frames"]))

    # 7c. 发射帧 / 头部抬升 必须写进 params（Sprite 场景由 params 驱动）
    if params.get("fire_frames") != list(model["fire_frames"]):
        fails.append("params.fire_frames %r != %r" % (params.get("fire_frames"),
                                                      list(model["fire_frames"])))
    if list(params.get("head_position", [])) != [HEAD_POSITION[0], HEAD_POSITION[1]]:
        fails.append("params.head_position %r != %r"
                     % (params.get("head_position"), list(HEAD_POSITION)))
    if params.get("head_raise_px") != HEAD_RAISE_PX:
        fails.append("params.head_raise_px %r != %r" % (params.get("head_raise_px"), HEAD_RAISE_PX))

    if params["layer_names"] != [t.name for t in model["tracks"]]:
        fails.append("params.layer_names 与轨道序不一致")
    if params["media_names"] != [m[0] for m in model["media"]]:
        fails.append("params.media_names 与媒体序不一致")
    if open(OUT_PARAMS, encoding="utf8").read() != json.dumps(params, indent=2, ensure_ascii=False) + "\n":
        fails.append("磁盘 params 与内存不一致")
    return fails


# ============================================================ main

def main():
    model = build_model()
    n = model["nframes"]
    tracks = model["tracks"]
    fire_frames, shoot = attach_fire_frames(model)
    print("=== 解析 %s" % os.path.basename(REANIM_BIN))
    print("  帧数 %d  轨道 %d（全部保留为图层，无图控制轨 %s）"
          % (n, len(tracks), [t.name for t in tracks if not t.images]))
    print("  clip  %s" % model["clips"])
    print("  body 图层 %s" % model["body_layers"])
    print("  head 图层 %s" % model["head_layers"])
    print("  insertLayerId = %d（= max(body)+1）" % model["insert_layer"])
    print("  射击段（%s 可见）= %d..%d；发射事件 %s @ %s（相对 HeadFire 起点 +%d）"
          % (SHOOT_TRACK, shoot[0], shoot[1], FIRE_EVENT_COMMAND,
             fire_frames, fire_frames[0] - model["clips"]["HeadFire"][0]))
    print("  头部抬升 head_raise_px=%.1f ⇒ Head.position = %s"
          % (HEAD_RAISE_PX, list(HEAD_POSITION)))
    print("  媒体 %d：" % len(model["media"]))
    for i, m in enumerate(model["media"]):
        print("     [%2d] %-34s %3dx%-3d %s" % (i, m[0], m[2], m[3], m[1] or "(占位)"))

    aw, ah, atlas = make_atlas(model)
    print("  图集 %dx%d（%.1f KB 像素）" % (aw, ah, aw * ah * 4 / 1024.0))

    dat_bytes = write_dat(model)
    tres_text = write_tres(model)

    # ---- 炮口标定
    bar = calibrate_muzzle(model)("barrel")
    ref = calibrate_reference()
    if bar is None:
        raise RuntimeError("未找到 barrel 轨的可见帧")
    fj, tipx, tipy, bb = bar
    # 内置 GatlingPea 的（同法无法直接量：其经典源不在解包内）⇒ 用「炮口内缩」经验值：
    #   内置 GatlingPea Marker2D 反推炮口 = ref；其在 f0 的 barrel1 右缘会让出 ~1.5px。
    #   这里直接采用「不透明区最右列中点」，与内置 GatlingPea 的截面习惯一致。
    muzzle = (tipx, tipy)
    marker2d = (round(muzzle[0] - ROOT_ANCHOR[0], 4), round(muzzle[1] - ROOT_ANCHOR[1], 4))

    params = {
        "key": KEY,
        "source_reanim": os.path.relpath(REANIM_BIN, CLASSIC).replace(os.sep, "/"),
        "frame_max": n,
        "frame_rate": FRAME_RATE,
        "clips": {k: list(v) for k, v in sorted(model["clips"].items())},
        "root_offset": list(ROOT_OFFSET),
        "head_offset": list(HEAD_OFFSET),
        "head_position": [HEAD_POSITION[0], HEAD_POSITION[1]],
        "head_raise_px": HEAD_RAISE_PX,
        "root_anchor": list(ROOT_ANCHOR),
        "insert_layer_id": model["insert_layer"],
        "follow_parent_sprite_layer_id": model["insert_layer"],
        "insert_layer_name": tracks[model["insert_layer"]].name,
        "body_layers": model["body_layers"],
        "head_layers": model["head_layers"],
        "layer_names": [t.name for t in tracks],
        "layer_count": len(tracks),
        "media_names": [m[0] for m in model["media"]],
        "media_count": len(model["media"]),
        "n_slices": model["n_slices"],
        "fire_event": {"Command": FIRE_EVENT_COMMAND, "Argument": FIRE_EVENT_ARGUMENT},
        "fire_frames": list(fire_frames),
        "shoot_range": [shoot[0], shoot[1]],
        "muzzle_reanim": [round(muzzle[0], 4), round(muzzle[1], 4)],
        "muzzle_frame": fj,
        "marker2d": list(marker2d),
        "reference_gatlingpea_muzzle": [round(ref[0], 4), round(ref[1], 4)],
        "atlas": [aw, ah],
    }

    open(OUT_DAT, "wb").write(dat_bytes)
    open(OUT_TRES, "w", encoding="utf8", newline="\n").write(tres_text)
    pnglib.write_png(OUT_ATLAS, aw, ah, atlas)
    open(OUT_PARAMS, "w", encoding="utf8", newline="\n").write(
        json.dumps(params, indent=2, ensure_ascii=False) + "\n")
    print("  写出 %s %d B" % (os.path.basename(OUT_DAT), len(dat_bytes)))
    print("  写出 %s %d B" % (os.path.basename(OUT_TRES), len(tres_text)))
    print("  写出 %s %d B" % (os.path.basename(OUT_ATLAS), os.path.getsize(OUT_ATLAS)))
    print("  写出 %s" % os.path.basename(OUT_PARAMS))
    print("  slices=%d  body=%d层 head=%d层 insertLayerId=%d"
          % (model["n_slices"], len(model["body_layers"]), len(model["head_layers"]),
             model["insert_layer"]))
    print("  炮口（经典坐标）= (%.2f, %.2f) @f%d  ⇒ Marker2D(local) = %s"
          % (muzzle[0], muzzle[1], fj, marker2d))
    print("  内置 GatlingPea 反推炮口（参照）= (%.2f, %.2f)" % ref)

    preview = [0, 12, 24, 30, 40, 49, 56, 62, 68, 75, 80, 86]
    W, H = render_sheet(model, preview, OUT_PREVIEW)
    print("  预览 %s %dx%d  帧=%s" % (os.path.basename(OUT_PREVIEW), W, H, preview))
    OUT_COMPOSED = os.path.join(CACHE, "preview_official_composed.png")
    W2, H2 = render_sheet(model, [25, 30, 40, 49, 56, 62, 68, 75, 80, 86, 86, 86],
                          OUT_COMPOSED, composed=True, head_dy=HEAD_RAISE_PX)
    print("  合成预览 %s %dx%d（根 BodyIdle 循环 + 头叠加 + 抬高 %.1fpx，= 实机观感）"
          % (os.path.basename(OUT_COMPOSED), W2, H2, HEAD_RAISE_PX))

    fails = checks(model, dat_bytes, tres_text, params)
    print()
    print("=== 自检：%s" % ("全绿（0 项）" if not fails else "FAIL %d 项" % len(fails)))
    for f in fails:
        print("   -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
