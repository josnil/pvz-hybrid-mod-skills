# -*- coding: utf-8 -*-
"""官方素材外观验证器（独立实现，**不复用 build_official_skin.py 的任何代码**）。

用途
----
「超级机枪射手」已把外观从「自制单帧素材」换成「未重置版官方素材直转」
（经典 PvZ `SuperGatling.reanim.compiled` 27 轨 × 87 帧 → 重置版 `.dat`/`.tres`/图集）。
本脚本从**磁盘上的成品**出发，用四套互相独立的解析器交叉核对，防止「自检只比内存文本」的假绿。

四层验证
--------
① 源 ↔ `.dat`：独立再解码经典 reanim（含末轨 trailer 补扫），对**全部 27×87 = 2349 个
   (层,帧)** 独立重算「carry-forward + f 选图 + 旋转矩阵」，与 `.dat` 里的 mediaId / 6 个 f32
   **逐位**比对；媒体名集合与 id 序（大小写不敏感）也从 `.dat` 反推核对；mediaRect 尺寸
   与源 PNG 真尺寸比对。
② `.dat` 二进制：自写解析器按引擎 `AdobeAnimateData` 规格走完全文，
   硬判据 = 「解析终点 == 文件长」+「像素区逐字节 == 图集 PNG 真解码像素（自写 zlib+unfilter）」。
③ `.tres` 文本：抽取 Packed*Array 与 `.dat` 互证；`sliceTransforms` 与 `.dat` 的 f32 位级一致。
④ 场景 `.tscn`：`Sprite/SuperGatlingPea.tscn` + `Scene/SuperGatlingPea.tscn` 的
   offset / insertLayerId / clip / Marker2D / 图层媒体名单 / 相对路径断言，并含**旧自制值反例**。

另含结构性不变量：任何图层不得跨 body(0..24)/head(25..86) 边界；
`insertLayerId == max(body 真实贴图图层)+1`。

用法
----
    python .cache/verify_official_skin.py              # 正常验证
    python .cache/verify_official_skin.py --negative    # 负向测试：故意写坏副本，断言必须报错
退出码：0 = 全绿；1 = 有 FAIL；2 = 缺文件/环境问题
"""
import json
import math
import os
import re
import struct
import sys
import zlib

CACHE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.join(os.path.dirname(CACHE), "ModWorkspace")      # ModWorkspace
PROJ = os.path.join(WS, "SuperGatlingPea")
CHAR = os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea")

DAT = os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPea.dat")
TRES = os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPea.tres")
ATLAS = os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPeaAtlas.png")
SPRITE = os.path.join(CHAR, "Sprite", "SuperGatlingPea.tscn")
SCENE = os.path.join(CHAR, "Scene", "SuperGatlingPea.tscn")
PARAMS = os.path.join(CACHE, "skin_params.json")

CLASSIC = r"D:/zzz/extract_1789988101"
REANIM = os.path.join(CLASSIC, "compiled", "new", "SuperGatling.reanim.compiled")
REANIM_PNG_DIR = os.path.join(CLASSIC, "reanim")

SENT = -10000.0
REC = 44
TABLE0 = 0x1C
FIELDS = ("x", "y", "kx", "ky", "sx", "sy", "f")

BODY_LAST = 24                       # BodyIdle 末帧（含）
EXPECT_CLIPS = {"BodyIdle": [0, 24], "HeadIdle": [25, 49], "HeadFire": [50, 86]}
EXPECT_FRAME_MAX = 87
EXPECT_LAYERS = 27
ROOT_ANCHOR = (40.0, 40.0)

# ★★ 发射事件：动画事件表是常规攻击**唯一**的发射触发源（见 .cache/build_official_skin.py
#    常量块 FIRE_EVENT_* 的引擎源码证据链）。本 Mod 规格 = 每 1.5 秒 1 轮 7 颗 ⇒ 每循环 1 个。
EXPECT_FIRE_FRAMES = [62]            # = 射击段(50..74)内头部前冲达最大伸出的首帧；内置单发家族 = HeadFire 起点 +12
EXPECT_FIRE_EVENT = ("fire", "")     # (Command, Argument)，顺序即 .dat 里的写入顺序
EXPECT_HEAD_RAISE_PX = 8.0           # 官方大头盔素材需整体抬高，见 .cache/calib_head_raise.py
EXPECT_HEAD_POSITION = [0.0, -EXPECT_HEAD_RAISE_PX]

# 旧值反例（必须不出现）
BAD_OFFSETS = ("(-69.25, -174.0)", "(23.75, -22.5)", "(18.5, -105.25)")
BAD_MARKERS = ("(87.75, -111.25)", "(31.740002, -17.82)", "(31.74, -17.82)")

_nok = _nfail = 0


def ok(cond, msg, got=None):
    global _nok, _nfail
    if cond:
        _nok += 1
        print("  [OK]   %s" % msg)
    else:
        _nfail += 1
        print("  [FAIL] %s%s" % (msg, "" if got is None else "   实测=%r" % (got,)))
    return bool(cond)


def chk(cond, msg, got=None):
    """与 ok 相同但静默成功（用于成百上千条批量断言，只报 FAIL）。"""
    global _nok, _nfail
    if cond:
        _nok += 1
    else:
        _nfail += 1
        print("  [FAIL] %s%s" % (msg, "" if got is None else "   实测=%r" % (got,)))
    return bool(cond)


# ============================================================ 自写 PNG 解码（zlib + unfilter）

def png_decode(path):
    """独立实现（不依赖 pnglib）：返回 (w, h, rgba_bytes)。仅支持 8bit RGBA/RGB/灰度 无损。"""
    b = open(path, "rb").read()
    assert b[:8] == b"\x89PNG\r\n\x1a\n", "不是 PNG：" + path
    pos, idat, w, h, bitd, ct = 8, bytearray(), None, None, None, None
    plte, trns = None, None
    while pos < len(b):
        ln = struct.unpack_from(">I", b, pos)[0]
        typ = b[pos + 4:pos + 8]
        data = b[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b"IHDR":
            w, h, bitd, ct = struct.unpack_from(">IIBB", data, 0)
            assert bitd == 8, "仅支持 8bit（实测 %d）" % bitd
        elif typ == b"PLTE":
            plte = data
        elif typ == b"tRNS":
            trns = data
        elif typ == b"IDAT":
            idat += data
        elif typ == b"IEND":
            break
    assert ct in (0, 2, 3, 4, 6), "不支持的颜色类型 %r" % ct
    if ct == 3:
        assert plte, "调色板 PNG 缺 PLTE"
    nch = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(bytes(idat))
    stride = w * nch
    assert len(raw) == h * (stride + 1), (len(raw), h * (stride + 1))
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]
        p += 1
        line = bytearray(raw[p:p + stride])
        p += stride
        if ft == 1:
            for i in range(nch, stride):
                line[i] = (line[i] + line[i - nch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - nch] if i >= nch else 0
                bb = prev[i]
                c = prev[i - nch] if i >= nch else 0
                pp = a + bb - c
                pa, pb, pc = abs(pp - a), abs(pp - bb), abs(pp - c)
                pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    if nch != 4:
        rgba = bytearray(w * h * 4)
        for i in range(w * h):
            if ct == 3:
                idx = out[i]
                a = trns[idx] if (trns and idx < len(trns)) else 255
                rgba[4 * i:4 * i + 4] = bytes(plte[3 * idx:3 * idx + 3]) + bytes((a,))
            elif nch == 1:
                rgba[4 * i:4 * i + 4] = bytes((out[i], out[i], out[i], 255))
            elif nch == 2:
                g, a = out[2 * i], out[2 * i + 1]
                rgba[4 * i:4 * i + 4] = bytes((g, g, g, a))
            else:
                rgba[4 * i:4 * i + 4] = bytes(out[3 * i:3 * i + 3]) + b"\xff"
        return w, h, bytes(rgba)
    return w, h, bytes(out)


def _chunk(typ, data):
    return (struct.pack(">I", len(data)) + typ + data
            + struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF))


def write_png_rgba(path, w, h, rgba):
    """最小 RGBA PNG 写出（负向测试造坏副本用；过滤器恒 0）。"""
    rows = b"".join(b"\x00" + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))
    png = (b"\x89PNG\r\n\x1a\n"
           + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
           + _chunk(b"IDAT", zlib.compress(rows, 6))
           + _chunk(b"IEND", b""))
    open(path, "wb").write(png)
    return len(png)


# ============================================================ 自写经典 reanim 解码

def reanim_unwrap(path):
    b = open(path, "rb").read()
    if b[:4] == b"\xd4\xfe\xad\xde":
        n = struct.unpack_from("<I", b, 4)[0]
        raw = zlib.decompress(b[8:])
        assert len(raw) == n, (len(raw), n)
        return raw
    return b


def reanim_tracks(path):
    """返回 [ {name,nframes,frames,imgnames} ]。末轨 trailer 扫到文件尾（补扫 图片名表）。"""
    raw = reanim_unwrap(path)
    ntracks = struct.unpack_from("<I", raw, 8)[0]
    table = [struct.unpack_from("<3I", raw, TABLE0 + 12 * i) for i in range(ntracks)]
    base = TABLE0 + 12 * ntracks
    body = raw[base:]
    out = []
    pos = 0
    for ti in range(ntracks):
        m = re.match(rb"[ -~]+?,", body[pos:pos + 128])
        assert m, "轨道 %d 名解析失败 @%d" % (ti, pos)
        name = m.group()[:-1].decode()
        nframes = table[ti][1]
        fstart = pos + m.end() + 3
        fend = fstart + nframes * REC
        assert fend <= len(body), "轨道 %s 帧数据越界" % name
        frames = [struct.unpack_from("<11f", body, fstart + j * REC) for j in range(nframes)]
        nm = re.search(rb"[ -~]+?,", body[fend:fend + 4096])
        tend = fend + (nm.start() if nm else 0)
        seg = body[fend:tend] if nm else body[fend:]        # ★ 末轨扫到 EOF
        imgnames = [s.decode() for s in re.findall(rb"IMAGE_[A-Z0-9_]+", seg)]
        out.append({"index": ti, "name": name, "nframes": nframes,
                    "frames": frames, "imgnames": imgnames})
        pos = tend if nm else len(body)
        if not nm:
            break
    return out


def carry(track, key):
    """SENT = 继承上一帧；首帧未定义取默认。独立实现。"""
    dflt = {"x": 0.0, "y": 0.0, "kx": 0.0, "ky": 0.0, "sx": 1.0, "sy": 1.0, "f": 0.0}[key]
    idx = FIELDS.index(key)
    cur, res = dflt, []
    for fr in track["frames"]:
        v = fr[idx]
        if v != SENT:
            cur = v
        res.append(cur)
    return res


def display_name(image_name):
    """IMAGE_REANIM_<PREFIX>_<REST> → 重置版习惯命名（独立实现）。"""
    assert image_name.startswith("IMAGE_REANIM_"), image_name
    body = image_name[len("IMAGE_REANIM_"):]
    for pre, disp in (("SUPERGATLING_", "SuperGatlingPea_"),
                      ("PEASHOOTER_", "PeaShooter_"),
                      ("GATLINGPEA_", "GatlingPea_")):
        if body.startswith(pre):
            return disp + body[len(pre):].lower() + ".png"
    raise KeyError(image_name)


def src_png(image_name):
    base = image_name[len("IMAGE_REANIM_"):].lower() + ".png"
    for f in os.listdir(REANIM_PNG_DIR):
        if f.lower() == base:
            return os.path.join(REANIM_PNG_DIR, f)
    raise FileNotFoundError(base)


# ============================================================ 自写 .dat 解析

def parse_dat(b):
    """按引擎规格完整解析；返回 dict + 终点。"""
    d = {}
    d["frame_rate"] = struct.unpack_from("<f", b, 0)[0]
    d["frame_max"], d["atlas_w"], d["atlas_h"] = struct.unpack_from("<HHH", b, 4)
    d["pixel_bytes"] = struct.unpack_from("<q", b, 10)[0]
    off = 18
    d["pixels"] = b[off:off + d["pixel_bytes"]]
    off += d["pixel_bytes"]

    def rpstr():
        nonlocal off
        ln = struct.unpack_from("<I", b, off)[0]
        s = b[off + 4:off + 4 + ln].decode("utf8")
        off += 4 + ln
        return s

    nmedia = struct.unpack_from("<H", b, off)[0]
    off += 2
    d["media"] = []
    for _ in range(nmedia):
        nm = rpstr()
        r = struct.unpack_from("<ffff", b, off)
        off += 16
        d["media"].append((nm, r))

    nlayer = struct.unpack_from("<H", b, off)[0]
    off += 2
    d["layers"] = []
    for _ in range(nlayer):
        nm = rpstr()
        per = []
        for _j in range(d["frame_max"]):
            cnt = struct.unpack_from("<H", b, off)[0]
            off += 2
            els = []
            for _k in range(cnt):
                mid = struct.unpack_from("<H", b, off)[0]
                tr = struct.unpack_from("<ffffff", b, off + 2)
                col = struct.unpack_from("<I", b, off + 26)[0]
                off += 30
                els.append((mid, tr, col))
            per.append(els)
        d["layers"].append((nm, per))

    nclip = struct.unpack_from("<H", b, off)[0]
    off += 2
    d["clips"] = {}
    for _ in range(nclip):
        nm = rpstr()
        c0, c1 = struct.unpack_from("<HH", b, off)
        off += 4
        d["clips"][nm] = [c0, c1]

    nevent = struct.unpack_from("<H", b, off)[0]
    off += 2
    # ★ 帧号是 u16（引擎 AdobeAnimateData.InitInternal 用 `Get16() * _frameScale`）；
    #   每个条目按字典序读两段 pascalString：先 Command 后 Argument。
    d["events"] = {}
    for _ in range(nevent):
        eframe = struct.unpack_from("<H", b, off)[0]
        off += 2
        cnt = struct.unpack_from("<H", b, off)[0]
        off += 2
        d["events"][eframe] = [(rpstr(), rpstr()) for _2 in range(cnt)]
    d["end"] = off
    return d


# ============================================================ 自写 .tres 解析

def tres_int_array(text, name):
    m = re.search(r"^%s = PackedInt32Array\((.*?)\)$" % re.escape(name), text, re.M)
    assert m, "缺 %s" % name
    s = m.group(1).strip()
    return [int(x) for x in s.split(",")] if s else []


def tres_float_array(text, name):
    m = re.search(r"^%s = PackedFloat32Array\((.*?)\)$" % re.escape(name), text, re.M)
    assert m, "缺 %s" % name
    s = m.group(1).strip()
    return [float(x) for x in s.split(",")] if s else []


def tres_vec4_array(text, name):
    m = re.search(r"^%s = PackedVector4Array\((.*?)\)$" % re.escape(name), text, re.M)
    assert m, "缺 %s" % name
    s = m.group(1).strip()
    v = [float(x) for x in s.split(",")] if s else []
    return [tuple(v[i:i + 4]) for i in range(0, len(v), 4)]


def tres_dict(text, name):
    m = re.search(r"^%s = \{(.*?)\}$" % re.escape(name), text, re.M | re.S)
    assert m, "缺 %s" % name
    out = {}
    for k, v in re.findall(r'"([^"]+)":\s*(?:Vector2i\()?\s*(-?\d+)\s*\)?', m.group(1)):
        out[k] = int(v)
    return out


def f32bits(v):
    return struct.unpack("<I", struct.pack("<f", v))[0]


# ============================================================ ① 源 ↔ .dat

def check_source_vs_dat(d):
    print("\n--- ① 源 reanim ↔ .dat（全部 2349 个 (层,帧) 逐值反查）---")
    tracks = reanim_tracks(REANIM)
    chk(len(tracks) == EXPECT_LAYERS, "轨道数 %d == %d" % (len(tracks), EXPECT_LAYERS), len(tracks))
    chk([t["name"] for t in tracks] == [l[0] for l in d["layers"]],
        "轨道名序 == .dat 图层名序", [t["name"] for t in tracks][:3])
    n = d["frame_max"]

    # 媒体名集合 & id 序（大小写不敏感）
    names = []
    for t in tracks:
        for img in t["imgnames"]:
            dn = display_name(img)
            if dn not in names:
                names.append(dn)
    if any(not t["imgnames"] for t in tracks):
        names.append("locator.png")
    ordered = sorted(names, key=lambda s: (s.lower(), s))
    dat_names = [m[0] for m in d["media"]]
    chk(dat_names == ordered, "媒体表 ids 序 == 大小写不敏感排序", dat_names)
    chk("locator.png" in dat_names, ".dat 含 locator.png 占位媒体")
    chk("SuperGatlingPea_overlay2.png" in dat_names, "末轨 overlay2 图集名未丢（末轨 trailer 补扫）")
    mid = {nm: i for i, nm in enumerate(dat_names)}

    # mediaRect 尺寸 == 源 PNG 真尺寸
    dim_ok = dim_bad = 0
    for nm, r in d["media"]:
        if nm == "locator.png":
            chk((round(r[2]), round(r[3])) == (2, 2), "locator mediaRect = 2x2", r)
            continue
        src = None
        for t in tracks:
            for img in t["imgnames"]:
                if display_name(img) == nm:
                    src = img
                    break
            if src:
                break
        w, h, _ = png_decode(src_png(src))
        if (round(r[2]), round(r[3])) == (w, h):
            dim_ok += 1
        else:
            dim_bad += 1
            print("  [FAIL] mediaRect %s 尺寸 (%g,%g) != 源 PNG %dx%d" % (nm, r[2], r[3], w, h))
    chk(dim_bad == 0, "全部 mediaRect 尺寸 == 源 PNG 真尺寸（%d 张）" % dim_ok)

    # 全部 (层,帧) 独立重算
    nreal = nloc = nempty = 0
    bad = []
    for li, t in enumerate(tracks):
        xs, ys = carry(t, "x"), carry(t, "y")
        kxs, kys = carry(t, "kx"), carry(t, "ky")
        sxs, sys_ = carry(t, "sx"), carry(t, "sy")
        fs = carry(t, "f")
        for j in range(n):
            els = d["layers"][li][1][j]
            imgf = int(round(fs[j]))
            if imgf < 0:
                nempty += 1
                if els:
                    bad.append("L%d f%d 源不可见但 .dat 有 %d 个 slice" % (li, j, len(els)))
                continue
            want_nm = display_name(t["imgnames"][imgf]) if t["imgnames"] else "locator.png"
            if want_nm == "locator.png":
                nloc += 1
            else:
                nreal += 1
            if len(els) != 1:
                bad.append("L%d f%d slice 数 %d != 1" % (li, j, len(els)))
                continue
            mid_got, tr_got, col = els[0]
            if mid_got != mid[want_nm]:
                bad.append("L%d f%d mediaId %d(%s) != 期望 %d(%s)"
                           % (li, j, mid_got, dat_names[mid_got], mid[want_nm], want_nm))
            kx, ky = math.radians(kxs[j]), math.radians(kys[j])
            sx, sy = sxs[j], sys_[j]
            want_tr = (sx * math.cos(kx), sx * math.sin(kx),
                       -sy * math.sin(ky), sy * math.cos(ky), xs[j], ys[j])
            for a, b_ in zip(tr_got, want_tr):
                if f32bits(a) != f32bits(b_) or abs(a - b_) > 1e-6:
                    bad.append("L%d f%d 变换 %r != 期望 %r" % (li, j, tr_got, want_tr))
                    break
            if (col & 0xFF) != 255:
                bad.append("L%d f%d alpha != 255" % (li, j))
    print("  轨道 %d / 帧 %d / 媒体 %d（含 locator）" % (len(tracks), n, len(dat_names)))
    ok(not bad, "全部 %d 个 (层,帧) 的 mediaId + 旋转矩阵 逐位一致"
        "（真贴图 %d / 占位 %d / 不可见 %d）" % (len(tracks) * n, nreal, nloc, nempty), bad[:3])

    # ★★ 发射帧独立推导：射击段内「头部前冲块 x 首次达最大伸出(±1px)」那一帧。
    #    与 build_official_skin.derive_fire_frames 是**各自实现**的两份，互为交叉验证。
    name2i = {t["name"]: i for i, t in enumerate(tracks)}
    if "anim_shooting" in name2i and "GatlingPea_mouth" in name2i:
        si, mi = name2i["anim_shooting"], name2i["GatlingPea_mouth"]
        vis = [j for j in range(n) if d["layers"][si][1][j]]
        xs = {j: d["layers"][mi][1][j][0][1][4]
              for j in range(min(vis), max(vis) + 1) if d["layers"][mi][1][j]}
        mx = max(xs.values())
        fr = min(j for j, v in xs.items() if v >= mx - 1.0)
        chk(fr == EXPECT_FIRE_FRAMES[0],
            "独立推导发射帧 %d == %d" % (fr, EXPECT_FIRE_FRAMES[0]), fr)
        chk(fr - d["clips"]["HeadFire"][0] == 12,
            "发射帧相对 HeadFire 起点 +%d == +12（内置单发家族相位）"
            % (fr - d["clips"]["HeadFire"][0]), fr - d["clips"]["HeadFire"][0])
    else:
        ok(False, "缺 anim_shooting / GatlingPea_mouth ⇒ 无法独立推导发射帧")
    return tracks, dat_names


# ============================================================ ② .dat 二进制

def check_dat_binary(d, raw_bytes):
    print("\n--- ② .dat 二进制完整性 ---")
    ok(d["frame_rate"] == 12.0, ".dat frameRate == 12.0", d["frame_rate"])
    ok(d["frame_max"] == EXPECT_FRAME_MAX, ".dat frameMax == %d" % EXPECT_FRAME_MAX, d["frame_max"])
    ok(len(d["layers"]) == EXPECT_LAYERS, ".dat 图层数 == %d" % EXPECT_LAYERS, len(d["layers"]))
    ok(d["pixel_bytes"] == d["atlas_w"] * d["atlas_h"] * 4,
       "pixelByteCount == atlasW*atlasH*4", d["pixel_bytes"])
    ok(d["clips"] == EXPECT_CLIPS, ".dat clips == %r" % (EXPECT_CLIPS,), d["clips"])
    # ★★ 事件帧表：没有它，实机「只有动画、一颗子弹都没有」
    ok(d["events"] == {EXPECT_FIRE_FRAMES[0]: [EXPECT_FIRE_EVENT]},
       ".dat 事件帧表 == {%d: [%r]}（发射触发源）" % (EXPECT_FIRE_FRAMES[0], EXPECT_FIRE_EVENT),
       d["events"])
    for ef, ents in d["events"].items():
        chk(EXPECT_CLIPS["HeadFire"][0] <= ef <= EXPECT_CLIPS["HeadFire"][1],
            "事件帧 %d 落在 HeadFire(%d,%d) 内" % (ef, EXPECT_CLIPS["HeadFire"][0],
                                                   EXPECT_CLIPS["HeadFire"][1]))
        chk(all(e[0] == "fire" for e in ents), "事件条目 Command 全为 fire", ents)
    ok(d["end"] == len(raw_bytes), "★ 解析终点 == 文件长（%d）" % len(raw_bytes), d["end"])

    # ★ 像素区 == 图集 PNG 真解码像素（逐字节）
    w, h, px = png_decode(ATLAS)
    ok((w, h) == (d["atlas_w"], d["atlas_h"]), "图集 PNG 尺寸 == .dat 头声明", (w, h))
    ok(d["pixels"] == px, "★ .dat 像素区逐字节 == 图集 PNG 真解码像素", len(d["pixels"]))
    if px[:4] != d["pixels"][:4]:
        print("      首像素 RGBA dat=%r atlas=%r" % (d["pixels"][:4], px[:4]))

    nslice = sum(len(e) for _nm, per in d["layers"] for e in per)
    ok(nslice > 0, "slice 总数 = %d" % nslice, nslice)
    return nslice


# ============================================================ ③ .tres ↔ .dat

def check_tres_vs_dat(d, nslice):
    print("\n--- ③ .tres 文本 ↔ .dat ---")
    text = open(TRES, encoding="utf8").read()
    ok(re.search(r"^frameMax = %d$" % EXPECT_FRAME_MAX, text, re.M) is not None,
       ".tres frameMax == %d" % EXPECT_FRAME_MAX)
    ok('animeFile = "./SuperGatlingPea.dat"' in text, ".tres animeFile = ./SuperGatlingPea.dat")

    # clips / 字典
    clips = {}
    for m in re.finditer(r'"([^"]+)": Vector2i\((-?\d+), (-?\d+)\)', text):
        clips[m.group(1)] = [int(m.group(2)), int(m.group(3))]
    ok(clips == EXPECT_CLIPS, ".tres clips == %r" % (EXPECT_CLIPS,), clips)
    ok(tres_dict(text, "mediaDictionary") == {m[0]: i for i, m in enumerate(d["media"])},
       "mediaDictionary == .dat 媒体序")
    lay = tres_dict(text, "layerDictionary")
    exp_lay = {nm: i for i, (nm, _p) in enumerate(d["layers"])}
    ok({k: v for k, v in lay.items() if k in exp_lay} == exp_lay,
       "layerDictionary 的图层名→序 == .dat 图层序", len(lay))
    ok(lay.get("AnimeClips") == len(d["layers"]) and lay.get("AnimeEvents") == len(d["layers"]) + 1,
       "layerDictionary 另含 AnimeClips/AnimeEvents 两个内建表（= %d / %d）"
       % (len(d["layers"]), len(d["layers"]) + 1))

    # 数组长度
    fo = tres_int_array(text, "frameOffsets")
    fc = tres_int_array(text, "frameCounts")
    sk = tres_int_array(text, "sliceKeys")
    sm = tres_int_array(text, "sliceMediaIds")
    sl = tres_int_array(text, "sliceLayerIds")
    sd = tres_int_array(text, "sliceDrawOrders")
    sf = tres_int_array(text, "sliceFlags")
    st = tres_float_array(text, "sliceTransforms")
    sa = tres_float_array(text, "sliceAlpha")
    mr = tres_vec4_array(text, "mediaRects")

    ok(len(fo) == EXPECT_FRAME_MAX and len(fc) == EXPECT_FRAME_MAX,
       "frameOffsets/Counts 长度 == %d" % EXPECT_FRAME_MAX, (len(fo), len(fc)))
    ok(len(sk) == nslice, "sliceKeys 长度 == slice 总数", (len(sk), nslice))
    for nm, arr in (("sliceMediaIds", sm), ("sliceLayerIds", sl), ("sliceDrawOrders", sd),
                    ("sliceFlags", sf), ("sliceAlpha", sa)):
        chk(len(arr) == nslice, "%s 长度 == slice 总数" % nm, len(arr))
    ok(len(st) == nslice * 6, "sliceTransforms 长度 == slice 数 × 6", len(st))
    ok(len(mr) == len(d["media"]), "mediaRects 条数 == 媒体数", len(mr))

    # frameOffsets/Counts 由 .dat 独立推出
    exp_fo, exp_fc, exp_sk, exp_sm, exp_sl, exp_sd, exp_st = [], [], [], [], [], [], []
    slot = 0
    for j in range(d["frame_max"]):
        exp_fo.append(slot)
        c = 0
        num3 = 0
        for li, (nm, per) in enumerate(d["layers"]):
            for l in range(1):                     # layer_slots == 1（每层每帧至多 1 个元素）
                if l < len(per[j]):
                    els = per[j][l]
                    exp_sk.append((li << 16) ^ (l & 0xFFFF))
                    exp_sm.append(els[0])
                    exp_sl.append(li)
                    exp_sd.append(num3)
                    exp_st.extend(els[1])
                    c += 1
                    slot += 1
                num3 += 1
        exp_fc.append(c)
    ok(fo == exp_fo, "frameOffsets 由 .dat 独立推出后一致", fo[:5])
    ok(fc == exp_fc, "frameCounts 由 .dat 独立推出后一致", fc[:5])
    ok(sum(fc) == nslice, "Σ frameCounts == slice 总数", sum(fc))
    ok(sm == exp_sm, "sliceMediaIds 由 .dat 独立推出后一致", sm[:5])
    ok(sl == exp_sl, "sliceLayerIds 由 .dat 独立推出后一致", sl[:5])
    ok(sd == sl, "sliceDrawOrders == sliceLayerIds（内置口径）")
    ok(all(f == 0 for f in sf), "sliceFlags 恒 0")
    ok(sk == [(li << 16) ^ 0 for li in exp_sl], "sliceKeys == (layerId<<16)|槽序号")
    def _bits(v):
        return f32bits(0.0 if v == 0.0 else v)       # ±0.0 视为等值（-0.0 的翻译行为与 0.0 相同）
    mism = [(i, a, b_) for i, (a, b_) in enumerate(zip(st, exp_st)) if _bits(a) != _bits(b_)]
    ok(not mism, "★ sliceTransforms 与 .dat f32 位级一致（%d 项 ×6）" % nslice, mism[:3])
    ok(all(a == 1.0 for a in sa), "sliceAlpha 全 1.0")
    ok([tuple(round(v, 6) for v in r) for r in mr] ==
       [tuple(round(v, 6) for v in m[1]) for m in d["media"]], "mediaRects == .dat mediaRect")

    # ★★ events 数组 ↔ .dat 事件表（.dat 是实机真源，.tres 是编辑器/兜底 ⇒ 两边都要写且一致）
    em = re.search(r"^events = \[(.*)\]\s*$", text, re.M | re.S)
    ok(em is not None, ".tres 有 events 数组")
    if em:
        body = em.group(1)
        depth, cur, slots = 1, "", []          # 正则已吃掉最外层 `[` ⇒ 从 1 起算
        for ch in body:
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
        ok(len(slots) == EXPECT_FRAME_MAX, ".tres events 槽数 == %d" % EXPECT_FRAME_MAX, len(slots))
        ne = [i for i, c in enumerate(slots) if c.strip()]
        ok(ne == EXPECT_FIRE_FRAMES, ".tres 事件帧 %r == %r" % (ne, EXPECT_FIRE_FRAMES), ne)
        for i in ne:
            ok('"Command": "fire"' in slots[i] and '"Argument": ""' in slots[i],
               ".tres f%d 事件体含 Command=fire / Argument 为空" % i, slots[i])
        ok(ne == sorted(d["events"]), ".tres 事件帧 == .dat 事件帧", (ne, sorted(d["events"])))
    own = re.findall(r"events = \[(.*)\]\s*$", text, re.M | re.S)
    if len(own) > 1:
        ok(False, ".tres 出现多个 events 数组（应为 1 个）", len(own))
    return text


# ============================================================ ④ 场景 .tscn

def check_sprite_scene(d, dat_names, tmp_sprite=None):
    print("\n--- ④a Sprite 场景 ---")
    path = tmp_sprite or SPRITE
    s = open(path, encoding="utf8").read()
    ok(s.count("offset = Vector2(-40.0, -40.0)") == 2, "根 + Head 的 offset 都是 (-40,-40)（两份）",
       s.count("offset = Vector2(-40.0, -40.0)"))
    ok("position = Vector2(0.0, -8.0)" in s,
       "Head position == (0, -8.0)（整体抬高 8px；只许垂直，炮口随 Head 一起上移）")
    ok(re.search(r'^position = Vector2\(0(\.0)?, ', s, re.M) is not None,
       "Head position.x == 0（不做水平位移）")
    ok(re.search(r"^Layer = 16$", s, re.M) is not None, "Head Layer == 16")
    ok(re.search(r"^insertLayerId = 16$", s, re.M) is not None, "insertLayerId == 16")
    ok(re.search(r"^followParentSpriteLayerId = 16$", s, re.M) is not None,
       "followParentSpriteLayerId == 16")
    ok('parentSprite = NodePath("..")' in s, "parentSprite 指向父精灵")
    ok('Animation/Clip = "BodyIdle"' in s and 'Animation/Clip = "HeadIdle"' in s,
       "根 clip = BodyIdle / Head clip = HeadIdle")

    lv = sorted(set(re.findall(r"^Animation/LayerVisible/(\S+) = true$", s, re.M)))
    want_lv = [nm for nm, _p in d["layers"]] + ["AnimeClips", "AnimeEvents"]
    ok(lv == sorted(want_lv),
       "LayerVisible 覆盖全部 %d 个图层名 + 2 个内建表（根/Head 两块共 %d 行）"
       % (len(d["layers"]), len(lv) * 2), len(lv))
    mr = sorted(set(re.findall(r"^Animation/MediaReplace/(\S+) = null$", s, re.M)))
    ok(mr == sorted(dat_names),
       "MediaReplace 覆盖全部 %d 个媒体名（根/Head 两块）" % len(dat_names), len(mr))

    # 相对路径：不得出现本机绝对路径；包内引用必须 ./ 或 ../
    ok(not re.search(r'path="[A-Za-z]:', s), "无本机绝对路径引用")
    for p in re.findall(r"^\[ext_resource[^\]]*?path=\"([^\"]+)\"", s, re.M):
        chk(p.startswith("res://") or p.startswith("./") or p.startswith("../"),
            "ext_resource 引用为 res:// 或相对：%s" % p, p)
    ok("../../../../../Resources/Animations/SuperGatlingPea.tres" in s,
       "tres 引用是 5 级相对路径（Sprite 5 段目录）")

    for bad in BAD_OFFSETS:
        ok(bad not in s, "不含旧自制 offset 反例 %s" % bad)
    for bad in BAD_MARKERS:
        ok(bad not in s, "不含旧 Marker2D 反例 %s" % bad)
    return s


def check_main_scene(params):
    print("\n--- ④b 主场景 + 标定 ---")
    s = open(SCENE, encoding="utf8").read()
    ok('ComponentSet = ExtResource("2")' in s, "★ 显式声明 ComponentSet（否则发射组件不创建）")
    idx_cs = s.index('ComponentSet = ExtResource("2")')
    idx_sc = s.index("script = ExtResource(\"3\")")
    ok(idx_cs < idx_sc, "ComponentSet 写在 script 之前")
    ok("Marker2D" in s, "含 Marker2D 节点")
    m = re.search(r'^\[node name="Marker2D".*?\nposition = Vector2\(([-\d.]+), ([-\d.]+)\)',
                  s, re.M | re.S)
    assert m, "未找到 Marker2D position"
    got = [float(m.group(1)), float(m.group(2))]
    ok(got == list(params["marker2d"]), "Marker2D == skin_params.marker2d %r" % (params["marker2d"],), got)
    # 反推：Marker2D + anchor == 炮口（经典坐标）
    back = [round(got[0] + ROOT_ANCHOR[0], 4), round(got[1] + ROOT_ANCHOR[1], 4)]
    ok(back == list(params["muzzle_reanim"]),
       "Marker2D + anchor 反推 == muzzle_reanim %r" % (params["muzzle_reanim"],), back)
    ok("idleAnimeClip = \"BodyIdle\"" in s, "idleAnimeClip = BodyIdle")
    for bad in BAD_MARKERS:
        ok(bad not in s, "不含旧 Marker2D 反例 %s" % bad)
    ok(not re.search(r'path="[A-Za-z]:', s), "无本机绝对路径引用")
    ext = re.findall(r"^\[ext_resource[^\]]*?path=\"([^\"]+)\"", s, re.M)
    ok(len(ext) >= 5, "ext_resource 引用数 = %d" % len(ext), len(ext))
    for p in ext:
        chk(p.startswith("res://") or p.startswith("./") or p.startswith("../"),
            "ext_resource 引用为 res:// 或相对：%s" % p, p)
    ok("res://Asset/Anime/Character/Plant/Cover/GatlingPea/Scene/TowerDefensePlantGatlingPea.cs" in ext,
       "复用内置 GatlingPea 场景脚本（白拿其行为）")


# ============================================================ 结构不变量 + 参数一致性

def check_invariants(d, params):
    print("\n--- ⑤ 结构不变量 + skin_params 一致性 ---")
    n = d["frame_max"]
    locator = [i for i, m in enumerate(d["media"]) if m[0] == "locator.png"]
    assert locator, "缺 locator.png"
    locid = locator[0]

    body, head, cross = [], [], []
    for li, (nm, per) in enumerate(d["layers"]):
        in_b = [j for j in range(0, BODY_LAST + 1) if per[j]]
        in_h = [j for j in range(BODY_LAST + 1, n) if per[j]]
        if in_b and in_h:
            cross.append(nm)
        if not in_b and not in_h:
            print("  [FAIL] 图层 %s 全程无 slice" % nm)
            globals()["_nfail"] += 1
        real_b = any(per[j] and per[j][0][0] != locid for j in in_b)
        (body if real_b else head).append(li)
    ok(not cross, "没有任何图层跨 body(0..24)/head(25..86) 边界", cross)
    ok(sorted(body + head) == list(range(len(d["layers"]))), "body+head 恰好覆盖全部图层")
    ok(not (set(body) & set(head)), "body/head 无交集")
    ok(params["body_layers"] == body, "skin_params.body_layers == 独立推出 %r" % (body,),
       params["body_layers"])
    ok(params["head_layers"] == head, "skin_params.head_layers == 独立推出")
    ins = max(body) + 1 if body else 0
    ok(params["insert_layer_id"] == ins, "insertLayerId == max(body)+1 == %d" % ins,
       params["insert_layer_id"])
    ok(params["follow_parent_sprite_layer_id"] == ins, "followParentSpriteLayerId == %d" % ins)
    ok(params["frame_max"] == n, "skin_params.frame_max == %d" % n)
    ok(params["layer_count"] == len(d["layers"]), "skin_params.layer_count == %d" % len(d["layers"]))
    ok(params["media_count"] == len(d["media"]), "skin_params.media_count == %d" % len(d["media"]))
    ok(params["layer_names"] == [nm for nm, _p in d["layers"]],
       "skin_params.layer_names == .dat 图层序")
    ok(params["media_names"] == [m[0] for m in d["media"]], "skin_params.media_names == .dat 媒体序")
    ok(params["clips"] == EXPECT_CLIPS, "skin_params.clips == 标准三 clip", params["clips"])
    ok(params["root_offset"] == [-40.0, -40.0] and params["head_offset"] == [-40.0, -40.0],
       "skin_params 两层 offset 都是 (-40,-40)")
    ok(params["head_position"] == EXPECT_HEAD_POSITION,
       "skin_params.head_position == %r（= 抬高 %.1f px）"
       % (EXPECT_HEAD_POSITION, EXPECT_HEAD_RAISE_PX), params["head_position"])
    ok(params.get("head_raise_px") == EXPECT_HEAD_RAISE_PX,
       "skin_params.head_raise_px == %.1f" % EXPECT_HEAD_RAISE_PX, params.get("head_raise_px"))
    ok(list(params.get("fire_frames") or []) == EXPECT_FIRE_FRAMES,
       "skin_params.fire_frames == %r" % (EXPECT_FIRE_FRAMES,), params.get("fire_frames"))
    ok(list(d["events"]) == EXPECT_FIRE_FRAMES, "skin_params.fire_frames == .dat 事件帧",
       params.get("fire_frames"))
    ok(params["atlas"] == [d["atlas_w"], d["atlas_h"]], "skin_params.atlas == .dat 头声明")
    ok(list(params["marker2d"]) == [round(params["muzzle_reanim"][0] - ROOT_ANCHOR[0], 4),
                                    round(params["muzzle_reanim"][1] - ROOT_ANCHOR[1], 4)],
       "marker2d == muzzle - anchor")
    # clip 连续覆盖 0..n-1
    cover = sorted((v[0], v[1]) for v in d["clips"].values())
    ok(cover[0][0] == 0 and cover[-1][1] == n - 1, "clip 恰好覆盖 0..%d" % (n - 1), cover)
    ok(all(cover[i][0] == cover[i - 1][1] + 1 for i in range(1, len(cover))),
       "clip 之间无缝隙/重叠", cover)


# ============================================================ main

def main():
    global _nok, _nfail
    for p in (DAT, TRES, ATLAS, SPRITE, SCENE, PARAMS, REANIM):
        if not os.path.exists(p):
            print("缺文件：" + p)
            return 2
    params = json.load(open(PARAMS, encoding="utf8"))
    raw = open(DAT, "rb").read()
    d = parse_dat(raw)
    print("=== verify_official_skin：超级机枪射手（官方素材直转）===")
    print(".dat %d B  图集 %dx%d  帧数 %d  图层 %d  媒体 %d"
          % (len(raw), d["atlas_w"], d["atlas_h"], d["frame_max"],
             len(d["layers"]), len(d["media"])))

    _tracks, dat_names = check_source_vs_dat(d)
    nslice = check_dat_binary(d, raw)
    check_tres_vs_dat(d, nslice)
    check_sprite_scene(d, dat_names)
    check_main_scene(params)
    check_invariants(d, params)

    print("\n" + "=" * 74)
    print("结果: OK=%d  FAIL=%d  ->  %s" % (_nok, _nfail, "全绿 ✔" if not _nfail else "不通过 ✗"))
    print("=" * 74)
    return 1 if _nfail else 0


def negative():
    """负向测试：证明断言真的读磁盘（写坏副本必须报错）。"""
    import tempfile
    print("=" * 74)
    print("负向测试：故意写坏副本，断言必须报错")
    print("=" * 74)
    cases = []

    tmpd = tempfile.mkdtemp(prefix="vsk_")
    # 1) 图集 PNG 改一个像素 → ② 必须报错
    w, h, px = png_decode(ATLAS)
    tampered = bytearray(px)
    tampered[0] ^= 0xFF
    t_atlas = os.path.join(tmpd, "bad_atlas.png")
    write_png_rgba(t_atlas, w, h, bytes(tampered))
    print("\n[case1] 图集首像素改 1 bit（%s）" % os.path.basename(t_atlas))
    global _nok, _nfail
    _nok = _nfail = 0
    w2, h2, px2 = png_decode(t_atlas)
    chk(px2 == parse_dat(open(DAT, "rb").read())["pixels"],
        "② 图集像素 == .dat 像素区（应 FAIL）")
    cases.append(("图集像素篡改", _nfail))

    # 2) Sprite 场景 offset 改成旧错值 → ④a 必须 FAIL
    tmp_sprite = os.path.join(tmpd, "bad_sprite.tscn")
    s = open(SPRITE, encoding="utf8").read().replace(
        "offset = Vector2(-40.0, -40.0)", "offset = Vector2(-69.25, -174.0)")
    open(tmp_sprite, "w", encoding="utf8", newline="\n").write(s)
    print("\n[case2] Sprite 场景 offset 改成旧错值 (-69.25,-174.0)")
    _nok = _nfail = 0
    d = parse_dat(open(DAT, "rb").read())
    check_sprite_scene(d, [m[0] for m in d["media"]], tmp_sprite=tmp_sprite)
    cases.append(("场景 offset 篡改", _nfail))

    # 3) .tres frameMax 改错 → ③ 必须 FAIL
    tmp_tres = os.path.join(tmpd, "bad.tres")
    open(tmp_tres, "w", encoding="utf8", newline="\n").write(
        open(TRES, encoding="utf8").read().replace("frameMax = 87", "frameMax = 1"))
    print("\n[case3] .tres frameMax 改成 1")
    _nok = _nfail = 0
    text = open(tmp_tres, encoding="utf8").read()
    chk(re.search(r"^frameMax = %d$" % EXPECT_FRAME_MAX, text, re.M) is not None,
        ".tres frameMax == %d（应 FAIL）" % EXPECT_FRAME_MAX)
    cases.append((".tres frameMax 篡改", _nfail))

    # 4) 事件 Command 改坏 → 事件断言必须 FAIL（这就是「只有动画没有子弹」那个真实故障）
    t4 = os.path.join(tmpd, "bad_events.tres")
    open(t4, "w", encoding="utf8", newline="\n").write(
        open(TRES, encoding="utf8").read().replace('"Command": "fire"', '"Command": "noop"'))
    print("\n[case4] .tres 事件 Command 改成 noop（模拟「只有动画、没有子弹」）")
    _nok = _nfail = 0
    bt = open(t4, encoding="utf8").read()
    chk(bt.count('"Command": "fire"') == len(EXPECT_FIRE_FRAMES),
        ".tres fire 事件条数 == %d（应 FAIL）" % len(EXPECT_FIRE_FRAMES))
    cases.append(("事件表被改坏", _nfail))

    # 5) .dat 尾部事件段被截断 → 「解析终点 == 文件长」必须 FAIL
    t5 = os.path.join(tmpd, "bad_trunc.dat")
    open(t5, "wb").write(open(DAT, "rb").read()[:-4])
    print("\n[case5] .dat 去掉尾部 4 字节（事件段 Argument 空串被截断）")
    _nok = _nfail = 0
    db = open(t5, "rb").read()
    try:
        d5 = parse_dat(db)
        chk(d5["end"] == len(db), "★ 解析终点 == 文件长（应 FAIL）", d5["end"])
    except Exception as e:
        _nfail += 1
        print("  [FAIL] 解析抛异常（也算抓到坏文件）：%s" % e)
    cases.append((".dat 事件段截断", _nfail))

    print("\n" + "=" * 74)
    allok = True
    for nm, f in cases:
        print("  %-16s 报错 %d 条  %s" % (nm, f, "✔ 断言有效" if f else "✘ 断言失效（假绿！）"))
        if not f:
            allok = False
    print("=" * 74)
    print("负向测试结果：%s" % ("%d/%d 全部报错 ✔" % (len(cases), len(cases)) if allok
                               else "有断言失效 ✘"))
    return 0 if allok else 1


if __name__ == "__main__":
    if "--negative" in sys.argv:
        sys.path.insert(0, CACHE)
        sys.exit(negative())
    sys.exit(main())
