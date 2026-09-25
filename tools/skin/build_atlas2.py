# -*- coding: utf-8 -*-
"""shelf 装箱 + 交付图集：把 head/body 块拼进一张图。

约束（来自 AdobeAnimateData.cs:1639-1644）：
  像素区长度必须恰好 == W*H*4 ⇒ 图集必须是密实的 W×H RGBA8。
约束（来自 AdobeAnimateGlobalAtlasCache.cs:3211）：
  一个 .dat 只有一张图 ⇒ head/body 必须同图。

策略：按高度分层的 shelf（行）装箱，块按高度降序放置，最小化面积。

★★ 两种素材输入（`SOURCE_MODE`）：
  · 'deliver'（旧）：`deliver/PeaShooterVeteran_{idle,shoot}_00..24.png`，各 25 帧 176x192 透明底
    ⇒ 50 帧动画（BodyIdle/HeadIdle/HeadFire）。
  · 'single'（新）：`source/SuperGatlingPea_single.png`，**单帧 352x384**（= 176x192 的 2 倍）
    ⇒ 只出 1 帧（N_FRAMES=1）。352x384 恰好 2 倍 ⇒ `DISPLAY_SCALE=0.5` 不用改，
      渲染尺寸自动与原 176x192 素材一致。
"""
import json
import os

import pnglib

OUTDIR = os.path.dirname(os.path.abspath(__file__))
DELIVER = r'D:\AIAgent\WorkBuddyStorage\2026-09-18-18-25-09\pvz_char\deliver'
SINGLE_PNG = os.path.join(OUTDIR, 'source', 'SuperGatlingPea_single.png')

# ★ 切换素材来源：'single' = 用户新给的单帧贴图；'deliver' = 旧的 25+25 帧
SOURCE_MODE = 'single'

SPLIT_Y = 128        # 仅在 SOURCE_MODE == 'deliver' 时使用（按 176x192 画布）
ALPHA_THRESH = 8
PAD = 1              # 块间留 1px，避免采样时相邻渗色
MAXW = 2048          # 目标不超 2048（与 MaxAtlasPageSize 对齐，且 GPU 友好）


def load_frames(prefix):
    out = []
    for i in range(N):
        p = os.path.join(DELIVER, 'PeaShooterVeteran_%s_%02d.png' % (prefix, i))
        w, h, px = pnglib.read_png(p)
        assert (w, h) == (CW, CH)
        out.append(px)
    return out


def bbox(px, y0, y1, thresh=ALPHA_THRESH):
    minx, miny, maxx, maxy = CW, y1, -1, -1
    for y in range(y0, y1):
        row = y * CW * 4
        for x in range(CW):
            if px[row + x * 4 + 3] > thresh:
                if x < minx:
                    minx = x
                if x > maxx:
                    maxx = x
                if y < miny:
                    miny = y
                if y > maxy:
                    maxy = y
    if maxx < 0:
        return None
    return minx, miny, maxx, maxy


def crop(px, box):
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    buf = pnglib.new_rgba(bw, bh)
    for y in range(bh):
        srow = ((y0 + y) * CW + x0) * 4
        drow = y * bw * 4
        buf[drow:drow + bw * 4] = px[srow:srow + bw * 4]
    return buf, bw, bh


def crop_generic(px, w, box):
    """按任意源宽 w 裁剪（single 模式用）。"""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    buf = pnglib.new_rgba(bw, bh)
    for y in range(bh):
        srow = ((y0 + y) * w + x0) * 4
        drow = y * bw * 4
        buf[drow:drow + bw * 4] = px[srow:srow + bw * 4]
    return buf, bw, bh


def shelf_pack(items, maxw):
    """items = [(key, w, h)]；返回 {(key):(x,y)} 与 (W,H)。

    按高度降序，逐行摆放；行高 = 该行最高块。"""
    order = sorted(items, key=lambda t: (-t[2], -t[1]))
    placed = {}
    x = y = 0
    row_h = 0
    total_w = 0
    for key, w, h in order:
        if x + w > maxw and x > 0:
            y += row_h + PAD
            x = 0
            row_h = 0
        placed[key] = (x, y)
        x += w + PAD
        total_w = max(total_w, x - PAD)
        row_h = max(row_h, h)
    return placed, (total_w, y + row_h)


def collect_blocks_single():
    """单帧模式：读 source/SuperGatlingPea_single.png，按等分中线切 head/body。

    ⚠️ 352x384 是 176x192 的**精确 2 倍** ⇒ 分层线同样 ×2 = 256。
    """
    w, h, px = pnglib.read_png(SINGLE_PNG)
    assert (w, h) == (CW * 2, CH * 2), 'single 素材应为 %dx%d，实为 %dx%d' % (CW * 2, CH * 2, w, h)
    split = SPLIT_Y * 2

    def bb(y0, y1):
        minx, miny, maxx, maxy = w, y1, -1, -1
        for y in range(y0, y1):
            row = y * w * 4
            for x in range(w):
                if px[row + x * 4 + 3] > ALPHA_THRESH:
                    if x < minx:
                        minx = x
                    if x > maxx:
                        maxx = x
                    if y < miny:
                        miny = y
                    if y > maxy:
                        maxy = y
        return (minx, miny, maxx, maxy) if maxx >= 0 else None

    hb = bb(0, split)
    bb2 = bb(split, h)
    assert hb and bb2, '单帧上半/下半必须都有内容（检查分层线 y=%d）' % split
    hbuf, hw, hh = crop_generic(px, w, hb)
    bbuf, bw2, bh2 = crop_generic(px, w, bb2)
    hcx, hcy = (hb[0] + hb[2] + 1) / 2.0, (hb[1] + hb[3] + 1) / 2.0
    bcx, bcy = (bb2[0] + bb2[2] + 1) / 2.0, (bb2[1] + bb2[3] + 1) / 2.0
    print('single: head bbox=%s (%dx%d)  body bbox=%s (%dx%d)' % (hb, hw, hh, bb2, bw2, bh2))
    blocks = [('body', 0, bbuf, bw2, bh2, bcx, bcy),
              ('head', 0, hbuf, hw, hh, hcx, hcy)]
    return blocks, 1


def collect_blocks_deliver():
    """旧模式：25 帧 idle + 25 帧 shoot ⇒ 50 帧。"""
    idle = load_frames('idle')
    shoot = load_frames('shoot')
    frames = idle + shoot
    assert len(frames) == 50
    blocks = []
    for i, px in enumerate(frames):
        hb = bbox(px, 0, SPLIT_Y)
        bb = bbox(px, SPLIT_Y, CH)
        assert hb and bb
        hbuf, hw, hh = crop(px, hb)
        bbuf, bw, bh = crop(px, bb)
        hcx, hcy = (hb[0] + hb[2] + 1) / 2.0, (hb[1] + hb[3] + 1) / 2.0
        bcx, bcy = (bb[0] + bb[2] + 1) / 2.0, (bb[1] + bb[3] + 1) / 2.0
        blocks.append(('body', i, bbuf, bw, bh, bcx, bcy))
        blocks.append(('head', i, hbuf, hw, hh, hcx, hcy))
    return blocks, 50


def main():
    global CW, CH, N
    CW, CH = 176, 192
    N = 25

    if SOURCE_MODE == 'single':
        blocks, n_frames = collect_blocks_single()
    else:
        blocks, n_frames = collect_blocks_deliver()

    # 2) 装箱
    items = [(('%s#%d' % (k, i)), w, h) for (k, i, _b, w, h, _cx, _cy) in blocks]
    placed, (AW, AH) = shelf_pack(items, MAXW)
    print('atlas = %d x %d  (%.1f MPix)' % (AW, AH, AW * AH / 1e6))

    # 3) 合成
    atlas = pnglib.new_rgba(AW, AH)
    for (layer, i, buf, w, h, cx, cy) in blocks:
        x, y = placed['%s#%d' % (layer, i)]
        pnglib.blit(atlas, AW, AH, buf, w, h, x, y)

    pnglib.write_png(os.path.join(OUTDIR, 'SuperGatlingPeaAtlas.png'), AW, AH, atlas)

    # 4) 组装 author2.json
    #
    # ★★★ DISPLAY_SCALE：显示缩放（几乎被忽略过，导致角色大了 2 倍）
    #   'deliver' 模式：素材单帧 176x192，角色实际占 144x170；交付侧另有一张
    #     _source_cutout_1x.png = 72x85，恰好是 144x170 的 **1/2**
    #     （也等于 _frames.json 的 scaleFromSource=2 的倒数）。
    #   'single'  模式：素材单帧 352x384，恰好是 176x192 的 **2 倍**
    #     ⇒ 同样是「放大 2 倍画」，**0.5 继续适用，标定常量不需要改**。
    #   内置机枪射手同样走「大图 + scale 缩小」：其 .tres 的 sliceTransforms
    #     scale ≈ 0.41~1.0，渲染最大边长 ≈ 59 px。
    #   ⚠️ 写 scale=1.0 ⇒ 角色按满画布尺寸画 ⇒ 比内置大 2.5~3 倍。
    #
    # ★★ origin 必须跟着一起缩：origin 是「层内局部坐标」（未缩放画布空间），
    #    渲染时走 transform(含 origin) 再整体乘 scale ⇒ 只有 origin 也乘 0.5，
    #    角色中心才会画在同样的屏幕位置。
    #    （若只缩 scale 不缩 origin，中心点会偏离约 2 倍的距离。）
    DISPLAY_SCALE = 0.5

    slices = []
    frame_offsets = []
    frame_counts = []
    # 每帧：先 body 后 head（body 在底层）
    by_frame = {}
    for (layer, i, buf, w, h, cx, cy) in blocks:
        x, y = placed['%s#%d' % (layer, i)]
        by_frame.setdefault(i, []).append((layer, w, h, x, y, cx, cy))

    for i in range(n_frames):
        frame_offsets.append(len(slices))
        for (layer, w, h, x, y, cx, cy) in sorted(by_frame[i], key=lambda t: 0 if t[0] == 'body' else 1):
            slices.append({
                'layer': 0 if layer == 'body' else 1,
                'layerName': layer,
                'mediaId': 1 if layer == 'body' else 0,
                'scale': DISPLAY_SCALE,
                'ox': cx * DISPLAY_SCALE, 'oy': cy * DISPLAY_SCALE,
                'rect': [x, y, w, h],
            })
        frame_counts.append(len(by_frame[i]))

    # ★ clips 按模式给：
    #   'single'：只有 1 帧 ⇒ 三个 clip 全指向 (0,0)
    #     （BodyIdle/HeadIdle/HeadFire 必须都存在，否则 ComponentSet 引用的 clip 找不到）
    #     ⚠️ fireEvents 留空：单帧没有「开火第 11 帧」这回事；
    #        本 Mod 的发射靠托管插件直调 Fire()，不依赖动画事件。
    #   'deliver'：帧序 = idle(0..24) + shoot(25..49)
    if SOURCE_MODE == 'single':
        clips = {'BodyIdle': [0, 0], 'HeadIdle': [0, 0], 'HeadFire': [0, 0]}
        fire_events = []
    else:
        clips = {'BodyIdle': [0, 24], 'HeadIdle': [0, 24], 'HeadFire': [25, 49]}
        fire_events = [25 + 11]

    author = {
        'canvas': [CW, CH],
        'splitY': SPLIT_Y,
        'sourceMode': SOURCE_MODE,
        'frameRate': 12.0,
        'frameMax': n_frames,
        'atlas': {'w': AW, 'h': AH, 'bytes': AW * AH * 4},
        'media': [
            {'name': 'SuperGatlingPea_head.png', 'rect': None},
            {'name': 'SuperGatlingPea_body.png', 'rect': None},
        ],
        'layers': ['body', 'head'],
        # ★ clips：权威约束见 Scene/SuperGatlingPeaComponentSet.tres:
        #     fireAnimeClips="HeadFire" / spliceIdleAnimeClips="HeadIdle" / spliceIdleAnimeClips
        'clips': clips,
        'slices': slices,
        'frameOffsets': frame_offsets,
        'frameCounts': frame_counts,
        'fireEvents': fire_events,
    }
    with open(os.path.join(OUTDIR, 'author2.json'), 'w', encoding='utf8') as f:
        json.dump(author, f, ensure_ascii=False, indent=1)

    print('mode =', SOURCE_MODE, ' slices =', len(slices), ' frames =', len(frame_offsets))
    print('clips =', clips, ' fireEvents =', fire_events)
    print('frameCounts 分布 =', sorted(set(frame_counts)))
    print('atlas bytes =', AW * AH * 4, '(%.1f MB)' % (AW * AH * 4 / 1e6))
    print('png size =', os.path.getsize(os.path.join(OUTDIR, 'SuperGatlingPeaAtlas.png')))


if __name__ == '__main__':
    main()
