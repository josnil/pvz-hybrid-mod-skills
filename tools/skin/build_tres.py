# -*- coding: utf-8 -*-
"""生成 SuperGatlingPea.tres（AdobeAnimateData，自描述 packed 数组）。

必须满足 HasPackedRuntimeData() 的**全部长度不变量**（AdobeAnimateData.cs:1139-1148）：
  frameOffsets.Length == frameMax
  frameCounts.Length  == frameMax
  sliceKeys/sliceMediaIds/sliceLayerIds/sliceDrawOrders/sliceFlags/sliceAlpha 长度相等 == N
  sliceTransforms.Length == N * 6
其中 N = sum(frameCounts)。

★ sliceKeys[i] = (layerId << 16) | slotIndex
  权威依据 = AdobeAnimateData.cs:1480 `list4.Add((k << 16) ^ (l & 0xFFFF));`
    k = layerId，l = 该元素在「本图层本帧」内的槽序号（从 0 起）。
  ★ 反证：内置 GatlingPea.tres 的 842 项里，`(layer<<16)|mediaId` 有 586 项不成立；
    实测其逐帧 sliceKeys = [0x0, 0x10000, ..., 0x90000]（低 16 位恒 0 = 槽序号），
    而 sliceMediaIds = [8, 9, 10, 15, 16, 12, ...] 各不相同。
  ⚠️ 之前误写为 `(layer<<16)|mediaId`，本 Mod 因「每层每帧恰好 1 个元素」⇒ 槽序号恒 0，
     故 sliceKeys 恒为 0 / 65536，与 mediaId 无关。

★ sliceDrawOrders[i] = 该元素在「本图层本帧」内的槽序号（per-layer-per-frame 重置）
  权威依据 = AdobeAnimateData.cs:1482 `list7.Add(num3);`，num3 在每层起始处归零、
    在遍历该层元素时自增（且对 MediaId==65535 的空槽也自增，见 :1476-1484）。
  内置实测：每帧 sliceDrawOrders = [0,1,2,...,9]（10 图层、每层每帧 1 切片）。
  ⚠️ 之前误写为全局递增 `i`（0..99），会让 ResolveLayerSortBand 的阶梯偏移量整体跑偏。
"""
import json
import os

OUTDIR = os.path.dirname(os.path.abspath(__file__))

# ★ animeFile 写「与 .tres 同目录的相对路径」，理由（ResolveAnimeFilePath，AdobeAnimateData.cs:1790-1822）：
#   1) FileExists(path)                       —— 相对路径在 cwd 下基本命中不了
#   2) ResourcePath.GetBaseDir().PathJoin(path)  —— ★ 命中：.tres 所在目录 + "./X.dat"
#   3) TryResolveOwnerBasenameCompanionDat    —— ★ 兜底命中：同目录同基名的 X.dat
#   所以「.tres 与 .dat 同目录同名」是双保险；写任一绝对 res:// 都会在 mod 包重定位后失效。
ANIME_BASENAME = 'SuperGatlingPea'

# 图层顺序：body=0, head=1（body 先画，head 后画压在上面）
LAYER_ORDER = ['body', 'head']

DEFAULT_LAYER_ORDER = LAYER_ORDER
BODY_LAYERS = ['body']
HEAD_LAYERS = ['head']


def fmt_int_array(vals):
    return 'PackedInt32Array(%s)' % ', '.join(str(int(v)) for v in vals)


def fmt_float_array(vals):
    out = []
    for v in vals:
        s = repr(float(v))
        out.append(s)
    return 'PackedFloat32Array(%s)' % ', '.join(out)


def main():
    a = json.load(open(os.path.join(OUTDIR, 'author2.json'), encoding='utf8'))
    media_rects = json.load(open(os.path.join(OUTDIR, 'media_rects.json')))

    frame_max = a['frameMax']
    slices = a['slices']

    frame_offsets = []
    frame_counts = []
    for f in range(frame_max):
        frame_offsets.append(a['frameOffsets'][f])
        frame_counts.append(a['frameCounts'][f])

    # ★ 遍历顺序必须与 BuildPackedRuntimeData 一致：外层帧 → 中层图层 → 内层槽序号
    #   （不是按 slices 原顺序）—— frameOffsets/frameCounts 已按「帧内先 body 后 head」排好，
    #   但为了 sliceDrawOrders 的 per-layer-per-frame 语义，这里显式按帧×图层重排。
    slice_keys = []
    slice_media_ids = []
    slice_layer_ids = []
    slice_draw_orders = []
    slice_flags = []
    slice_transforms = []
    slice_alpha = []

    for f in range(frame_max):
        off = frame_offsets[f]
        cnt = frame_counts[f]
        frame_items = slices[off:off + cnt]
        for lid in range(len(LAYER_ORDER)):
            slot = 0
            for s in frame_items:
                if s['layer'] != lid:
                    continue
                mid = s['mediaId']
                slice_keys.append((lid << 16) | (slot & 0xFFFF))
                slice_media_ids.append(mid)
                slice_layer_ids.append(lid)
                slice_draw_orders.append(slot)
                slice_flags.append(0)
                sc = s['scale']
                # Transform2D: xx, xy, yx, yy, ox, oy
                slice_transforms += [sc, 0.0, 0.0, sc, s['ox'], s['oy']]
                slice_alpha.append(1.0)
                slot += 1

    N = len(slice_keys)
    assert N == sum(frame_counts), '%d != %d' % (N, sum(frame_counts))
    assert len(slice_transforms) == N * 6

    # ---- clips ----
    # ★★ 从 author2.json 读，**不要在这里硬编码**：
    #   'deliver' 模式（25+25 帧）：BodyIdle=(0,24) / HeadIdle=(0,24) / HeadFire=(25,49)
    #     —— 用户素材帧序 idle(0..24) + shoot(25..49)，shoot 内 fireFrame=11 ⇒ 全局帧 36。
    #   'single'  模式（单帧）：三者全 = (0,0)
    #     —— 只有 1 帧；但三个 clip 名**必须都存在**，因为
    #        TowerDefensePlantGatlingPeaComponentSet.tres 引用了
    #        fireAnimeClips="HeadFire" / spliceIdleAnimeClips="HeadIdle" / isSpliceSprite=true，
    #        且角色场景 idleAnimeClip="BodyIdle" ⇒ 缺任何一个都会让 clip 解析失败。
    clips = {k: (int(v[0]), int(v[1])) for k, v in a['clips'].items()}
    # 防御：三个必需 clip 名必须在
    for _need in ('BodyIdle', 'HeadIdle', 'HeadFire'):
        assert _need in clips, 'author2.json 缺 clip: %s' % _need

    # ---- events ----
    # 事件帧位置：ParseEditorDatHydration 会按 frameScale 展开；
    # frameScale=1 时 events 数组长度 = frameMax。
    # 内置 GatlingPea：在 HeadFire 段内每 6 帧一个 fire。
    # 本素材：shoot 段的 fireFrame=11 ⇒ 全局帧 25+11 = 36。
    events_len = frame_max
    ev_lines = []
    fire_frames = set(a['fireEvents'])
    for f in range(events_len):
        if f in fire_frames:
            ev_lines.append('[{ "Argument": "", "Command": "fire" }]')
        else:
            ev_lines.append('[]')

    # ---- mediaDictionary / layerDictionary ----
    media_dict = {m['name']: i for i, m in enumerate(a['media'])}
    layer_dict = {n: i for i, n in enumerate(LAYER_ORDER)}

    # 额外图层名（内置约定，非必需但保持兼容）
    extra_layers = ['AnimeClips', 'AnimeEvents']
    for j, nm in enumerate(extra_layers):
        layer_dict[nm] = len(LAYER_ORDER) + j

    lines = []
    lines.append('[gd_resource type="Resource" script_class="AdobeAnimateData" format=4]')
    lines.append('')
    lines.append('[ext_resource type="Script" path="res://addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs" id="1"]')
    lines.append('')
    lines.append('[resource]')
    lines.append('script = ExtResource("1")')
    lines.append('animeFile = "./%s.dat"' % ANIME_BASENAME)
    lines.append('frameRate = %s' % repr(float(a['frameRate'])))
    lines.append('frameMax = %d' % frame_max)
    lines.append('frameOffsets = %s' % fmt_int_array(frame_offsets))
    lines.append('frameCounts = %s' % fmt_int_array(frame_counts))
    lines.append('sliceKeys = %s' % fmt_int_array(slice_keys))
    lines.append('sliceMediaIds = %s' % fmt_int_array(slice_media_ids))
    lines.append('sliceLayerIds = %s' % fmt_int_array(slice_layer_ids))
    lines.append('sliceDrawOrders = %s' % fmt_int_array(slice_draw_orders))
    lines.append('sliceFlags = %s' % fmt_int_array(slice_flags))
    lines.append('sliceTransforms = %s' % fmt_float_array(slice_transforms))
    lines.append('sliceAlpha = %s' % fmt_float_array(slice_alpha))
    # mediaRects: PackedVector4Array(x, y, w, h, ...)
    mr_flat = []
    for (x, y, w, h) in media_rects:
        mr_flat += [x, y, w, h]
    lines.append('mediaRects = PackedVector4Array(%s)' % ', '.join(repr(float(v)) for v in mr_flat))
    lines.append('events = [%s]' % ', '.join(ev_lines))
    # clips
    cl = []
    for name, (s0, s1) in clips.items():
        cl.append('"%s": Vector2i(%d, %d)' % (name, s0, s1))
    lines.append('clips = {')
    lines.append(',\n'.join(cl))
    lines.append('}')
    # mediaDictionary
    md = []
    for name, idx in sorted(media_dict.items(), key=lambda t: t[1]):
        md.append('"%s": %d' % (name, idx))
    lines.append('mediaDictionary = {')
    lines.append(',\n'.join(md))
    lines.append('}')
    # layerDictionary
    ld = []
    for name, idx in sorted(layer_dict.items(), key=lambda t: t[1]):
        ld.append('"%s": %d' % (name, idx))
    lines.append('layerDictionary = {')
    lines.append(',\n'.join(ld))
    lines.append('}')
    lines.append('rasterCompositeData = null')
    lines.append('metadata/_custom_type_script = "res://addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs"')
    lines.append('')

    outp = os.path.join(OUTDIR, 'SuperGatlingPea.tres')
    open(outp, 'w', encoding='utf8', newline='\n').write('\n'.join(lines))
    print('wrote', outp, os.path.getsize(outp), 'bytes')
    print('N slices =', N, ' frameMax =', frame_max)
    print('clips =', clips)
    print('fire frames =', sorted(fire_frames))
    print('layers =', layer_dict)


if __name__ == '__main__':
    main()
