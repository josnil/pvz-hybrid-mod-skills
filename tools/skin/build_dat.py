# -*- coding: utf-8 -*-
"""写《植物大战僵尸杂交版》AdobeAnimate .dat（Godot 4.7 / PvZ-HE）。

格式（逐字节，已由 AdobeAnimateData.cs 双路径交叉验证 + verify_dat_parse.py 实测）：

  float32 frameRate                 // :1696 / :1041      @off 0    (4 B)
  uint16  frameMax                  // :1697 / :1046      @off 4    (2 B)
  uint16  atlasW                    // :1698              @off 6    (2 B)
  uint16  atlasH                    // :1698              @off 8    (2 B)
  int64   pixelByteCount            // :1699              @off 10   (8 B)  ← ⚠️ 不是 off 8！
      必须 == atlasW*atlasH*4；无对齐填充，像素区紧随其后 @off 18
  bytes   pixelByteCount 字节 RGBA8  // :1700  (head/top-left 逐行)        @off 18
  uint16  mediaCount                // :1052
    × mediaCount:
        PascalString 名             // :1055
        float32 x4  Rect2(x,y,w,h)  // :1056
  uint16  layerCount                // :1060
    × layerCount:
        PascalString 图层名         // :1063
        × frameMax:
            uint16 元素数           // :1069
            × 元素数: 30 字节       // :1071  SkipBytes(num6*30)
                uint16 mediaId
                float32 xx, xy, yx, yy
                float32 originX, originY
                uint32  alpha (低 8 位 / 255)   // :850-858 解析端
  uint16  clipCount                 // :1075
    × clipCount:
        PascalString 名             // :1078
        uint16 start, uint16 end    // :1079
  uint16  eventFrameCount           // :1082
    × eventFrameCount:
        uint16 frame                // :1087
        uint16 事件数               // :1088
        × 事件数:
            PascalString Command    // :1093
            PascalString Argument   // :1094

PascalString（Godot FileAccess::get_pascal_string，4.7 源码）：
    uint32（小端）长度 n   +   n 字节 UTF-8（无终止符）

★ 元素 30 字节的逐字段假设（源自 :850-858 的读取序列）：
    mediaId u16(2) + 4×float(16) + 2×float(8) + u32(4) = 30 ✓
"""
import json
import os
import struct

OUTDIR = os.path.dirname(os.path.abspath(__file__))

ALPHA_SCALE = 255.0


def pstr(s):
    """Godot PascalString：uint32 LE 长度 + UTF-8。"""
    b = s.encode('utf8')
    return struct.pack('<I', len(b)) + b


def build(author, pixel_bytes):
    """author: author2.json 结构；pixel_bytes: 图集 RGBA8 原始字节。"""
    AW = author['atlas']['w']
    AH = author['atlas']['h']
    assert len(pixel_bytes) == AW * AH * 4, \
        'pixel bytes %d != %d*%d*4' % (len(pixel_bytes), AW, AH)

    out = bytearray()

    # ---- 头 ----
    out += struct.pack('<f', author['frameRate'])
    out += struct.pack('<H', author['frameMax'])
    out += struct.pack('<H', AW)
    out += struct.pack('<H', AH)
    out += struct.pack('<q', AW * AH * 4)
    out += pixel_bytes

    # ---- media 表 ----
    media = author['media']
    # rect 从 slices 里该 media 的并集包围盒推出（须与 .tres 的 mediaRects 一致）
    rects = {}
    for s in author['slices']:
        x, y, w, h = s['rect']
        mid = s['mediaId']
        if mid not in rects:
            rects[mid] = [x, y, x + w, y + h]
        else:
            r = rects[mid]
            r[0] = min(r[0], x)
            r[1] = min(r[1], y)
            r[2] = max(r[2], x + w)
            r[3] = max(r[3], y + h)
    out += struct.pack('<H', len(media))
    media_rect_list = []
    for i, m in enumerate(media):
        r = rects[i]
        rect = (r[0], r[1], r[2] - r[0], r[3] - r[1])
        media_rect_list.append(rect)
        out += pstr(m['name'])
        out += struct.pack('<ffff', *rect)

    # ---- layer 表 ----
    layers = author['layers']
    frame_max = author['frameMax']
    # 组织成 per-layer per-frame 元素表
    per = {}   # (layerIdx, frame) -> [slice,...]
    for s in author['slices']:
        per.setdefault((s['layer'], 0) + (0,), None)
    # 按 frameOffsets/frameCounts 重建每帧的 slice 归属
    frame_slices = []
    for f in range(frame_max):
        o = author['frameOffsets'][f]
        c = author['frameCounts'][f]
        frame_slices.append(author['slices'][o:o + c])

    out += struct.pack('<H', len(layers))
    for li, lname in enumerate(layers):
        out += pstr(lname)
        for f in range(frame_max):
            elems = [s for s in frame_slices[f] if s['layer'] == li]
            out += struct.pack('<H', len(elems))
            for s in elems:
                sc = s['scale']
                out += struct.pack('<H', s['mediaId'])
                # Transform2D 列：xx, xy, yx, yy （无旋转 ⇒ xy=yx=0）
                out += struct.pack('<ffff', sc, 0.0, 0.0, sc)
                out += struct.pack('<ff', s['ox'], s['oy'])
                out += struct.pack('<I', 255)

    # ---- clip 表 ----
    clips = author['clips']
    out += struct.pack('<H', len(clips))
    for name, (s0, s1) in clips.items():
        out += pstr(name)
        out += struct.pack('<HH', s0, s1)

    # ---- 事件帧表 ----
    ev = author['fireEvents']
    out += struct.pack('<H', len(ev))
    for fr in ev:
        out += struct.pack('<H', fr)
        out += struct.pack('<H', 1)
        out += pstr('fire')
        out += pstr('')

    return bytes(out), media_rect_list


def main():
    author = json.load(open(os.path.join(OUTDIR, 'author2.json'), encoding='utf8'))
    import pnglib
    w, h, px = pnglib.read_png(os.path.join(OUTDIR, 'SuperGatlingPeaAtlas.png'))
    assert (w, h) == (author['atlas']['w'], author['atlas']['h'])

    blob, media_rects = build(author, bytes(px))
    outp = os.path.join(OUTDIR, 'SuperGatlingPea.dat')
    open(outp, 'wb').write(blob)
    print('wrote %s  %d bytes' % (outp, len(blob)))
    print('mediaRects (%d):' % len(media_rects))
    for i, r in enumerate(media_rects):
        print('   %d %s  -> %s' % (i, author['media'][i]['name'], r))

    json.dump(media_rects, open(os.path.join(OUTDIR, 'media_rects.json'), 'w'), indent=1)


if __name__ == '__main__':
    main()
