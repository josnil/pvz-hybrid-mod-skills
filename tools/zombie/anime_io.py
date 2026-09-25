# -*- coding: utf-8 -*-
"""AdobeAnimateData .tres / .dat 读写（Godot 4.7 / PvZ-HE）。

坐标约定（本模块唯一权威，已由 ZombieNormal 栅格合成图反证）：
    slice 元素字段 = mediaId, xx, xy, yx, yy, originX, originY, alpha
    矩阵列： X=(xx,xy)  Y=(yx,yy)
    M(v) = (xx*vx + yx*vy,  xy*vx + yy*vy)
    最终「节点局部坐标」= offset + M( atlasPoint - (originX, originY) )
其中 AtlasPoint 是该像素在 mediaRects 里的绝对图集坐标。
"""
import os
import re
import struct


# ---------------------------------------------------------------- .tres 解析

def _arr(text, key, typ='int'):
    m = re.search(re.escape(key) + r'\s*=\s*Packed(?:Int32|Float32|Vector4|Int64)Array\(([^)]*)\)', text)
    if not m:
        return []
    body = m.group(1).strip()
    if not body:
        return []
    vals = [v.strip() for v in body.split(',')]
    if typ == 'int':
        return [int(float(v)) for v in vals]
    return [float(v) for v in vals]


def _dict_of(text, key):
    m = re.search(re.escape(key) + r'\s*=\s*\{(.*?)\n\}', text, re.S)
    if not m:
        return {}
    out = {}
    for line in m.group(1).split('\n'):
        line = line.strip().rstrip(',')
        if not line:
            continue
        km = re.match(r'"([^"]*)"\s*:\s*(.+)$', line)
        if not km:
            continue
        k, v = km.group(1), km.group(2).strip()
        vm = re.match(r'Vector2i\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)', v)
        if vm:
            out[k] = (int(vm.group(1)), int(vm.group(2)))
        else:
            try:
                out[k] = int(v)
            except ValueError:
                out[k] = v
    return out


def parse_tres(path):
    text = open(path, encoding='utf8').read()
    d = {
        'path': path,
        'frameRate': float(re.search(r'frameRate\s*=\s*([\d.eE+-]+)', text).group(1)),
        'frameMax': int(re.search(r'frameMax\s*=\s*(\d+)', text).group(1)),
        'frameOffsets': _arr(text, 'frameOffsets', 'int'),
        'frameCounts': _arr(text, 'frameCounts', 'int'),
        'sliceKeys': _arr(text, 'sliceKeys', 'int'),
        'sliceMediaIds': _arr(text, 'sliceMediaIds', 'int'),
        'sliceLayerIds': _arr(text, 'sliceLayerIds', 'int'),
        'sliceDrawOrders': _arr(text, 'sliceDrawOrders', 'int'),
        'sliceFlags': _arr(text, 'sliceFlags', 'int'),
        'sliceTransforms': _arr(text, 'sliceTransforms', 'float'),
        'sliceAlpha': _arr(text, 'sliceAlpha', 'float'),
        'mediaRects': _arr(text, 'mediaRects', 'float'),
        'clips': _dict_of(text, 'clips'),
        'mediaDictionary': _dict_of(text, 'mediaDictionary'),
        'layerDictionary': _dict_of(text, 'layerDictionary'),
    }
    m = re.search(r'animeFile\s*=\s*"([^"]*)"', text)
    d['animeFile'] = m.group(1) if m else ''
    return d


def _pstr(buf, off):
    n = struct.unpack_from('<I', buf, off)[0]
    off += 4
    s = buf[off:off + n].decode('utf8', 'replace')
    return s, off + n


def parse_dat(path):
    buf = open(path, 'rb').read()
    off = 0
    frameRate = struct.unpack_from('<f', buf, off)[0]; off += 4
    frameMax = struct.unpack_from('<H', buf, off)[0]; off += 2
    atlasW = struct.unpack_from('<H', buf, off)[0]; off += 2
    atlasH = struct.unpack_from('<H', buf, off)[0]; off += 2
    nbytes = struct.unpack_from('<q', buf, off)[0]; off += 8
    pixels = buf[off:off + nbytes]; off += nbytes

    nmedia = struct.unpack_from('<H', buf, off)[0]; off += 2
    media = []
    for _ in range(nmedia):
        name, off = _pstr(buf, off)
        r = struct.unpack_from('<ffff', buf, off); off += 16
        media.append({'name': name, 'rect': list(r)})

    nlayer = struct.unpack_from('<H', buf, off)[0]; off += 2
    layers = []
    for _ in range(nlayer):
        name, off = _pstr(buf, off)
        frames = []
        for _f in range(frameMax):
            cnt = struct.unpack_from('<H', buf, off)[0]; off += 2
            elems = []
            for _e in range(cnt):
                mid = struct.unpack_from('<H', buf, off)[0]
                xx, xy, yx, yy = struct.unpack_from('<ffff', buf, off + 2)
                ox, oy = struct.unpack_from('<ff', buf, off + 18)
                alpha = struct.unpack_from('<I', buf, off + 26)[0]
                elems.append({'mediaId': mid, 'xx': xx, 'xy': xy, 'yx': yx, 'yy': yy,
                              'ox': ox, 'oy': oy, 'alpha': alpha})
                off += 30
            frames.append(elems)
        layers.append({'name': name, 'frames': frames})

    nclip = struct.unpack_from('<H', buf, off)[0]; off += 2
    clips = {}
    for _ in range(nclip):
        name, off = _pstr(buf, off)
        s, e = struct.unpack_from('<HH', buf, off); off += 4
        clips[name] = (s, e)

    nev = struct.unpack_from('<H', buf, off)[0]; off += 2
    events = {}
    for _ in range(nev):
        fr, cnt = struct.unpack_from('<HH', buf, off); off += 4
        evs = []
        for _e in range(cnt):
            cmd, off = _pstr(buf, off)
            arg, off = _pstr(buf, off)
            evs.append((cmd, arg))
        events[fr] = evs

    assert off == len(buf), 'trailing bytes: %d/%d' % (off, len(buf))
    return {'frameRate': frameRate, 'frameMax': frameMax, 'atlasW': atlasW, 'atlasH': atlasH,
            'pixels': pixels, 'media': media, 'layers': layers, 'clips': clips, 'events': events}


# ------------------------------------------------------- 排版 / 写入（自制皮肤）

def write_dat(path, *, frameRate, frameMax, atlasW, atlasH, pixels,
              media, clips, events=None):
    """media: [(name, (x,y,w,h))]；clips: {name:(s,e)}；events: {frame:[(cmd,arg)]}
    levels: layers = [(name, [ [elem,...]  × frameMax ])]
    elem = dict(mediaId,xx,xy,yx,yy,ox,oy,alpha)
    """
    assert len(pixels) == atlasW * atlasH * 4
    out = bytearray()
    out += struct.pack('<f', frameRate)
    out += struct.pack('<HHH', frameMax, atlasW, atlasH)
    out += struct.pack('<q', atlasW * atlasH * 4)
    out += pixels
    out += struct.pack('<H', len(media))
    for name, (x, y, w, h) in media:
        out += _pstr_w(name)
        out += struct.pack('<ffff', x, y, w, h)
    raise NotImplementedError


def _pstr_w(s):
    b = s.encode('utf8')
    return struct.pack('<I', len(b)) + b


if __name__ == '__main__':
    import sys
    p = sys.argv[1]
    d = parse_tres(p)
    print('frameMax', d['frameMax'], 'frameRate', d['frameRate'])
    print('N', len(d['sliceKeys']), 'sum(cnt)', sum(d['frameCounts']))
    print('clips', d['clips'])
    print('media', d['mediaDictionary'])
    print('layers', d['layerDictionary'])
