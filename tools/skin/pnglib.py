# -*- coding: utf-8 -*-
"""极简 PNG 读写库（无 PIL 依赖）。

只支持：8-bit / colorType 6(RGBA) 与 2(RGB)、非隔行。写出一律 RGBA8。
点阵表示为 (w, h, bytearray) 其中 bytearray 长度 = w*h*4。
"""
import struct
import zlib


def read_png(path):
    b = open(path, 'rb').read()
    assert b[:8] == b'\x89PNG\r\n\x1a\n', 'not png: ' + path
    w, h, bd, ct, comp, filt, inter = struct.unpack('>IIBBBBB', b[16:29])
    assert bd == 8, 'bit depth %d unsupported' % bd
    assert inter == 0, 'interlaced unsupported'
    pos = 8
    idat = bytearray()
    plte = None
    trns = None
    while pos < len(b):
        ln = struct.unpack('>I', b[pos:pos + 4])[0]
        typ = b[pos + 4:pos + 8]
        data = b[pos + 8:pos + 8 + ln]
        if typ == b'IDAT':
            idat += data
        elif typ == b'PLTE':
            plte = data
        elif typ == b'tRNS':
            trns = data
        pos += 12 + ln
    raw = zlib.decompress(bytes(idat))

    if ct == 6:
        nch = 4
    elif ct == 2:
        nch = 3
    elif ct == 0:
        nch = 1
    elif ct == 4:
        nch = 2
    elif ct == 3:
        nch = 1
    else:
        raise ValueError('colorType %d unsupported' % ct)

    stride = w * nch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    o = 0
    for y in range(h):
        ft = raw[o]
        o += 1
        line = bytearray(raw[o:o + stride])
        o += stride
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
                c = prev[i - nch] if i >= nch else 0
                bb = prev[i]
                pa = abs(bb - c)
                pb = abs(a - c)
                pc = abs(a + bb - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (bb if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line

    # 统一转 RGBA8
    rgba = bytearray(w * h * 4)
    if ct == 6:
        rgba = out
    elif ct == 2:
        for i in range(w * h):
            rgba[i * 4] = out[i * 3]
            rgba[i * 4 + 1] = out[i * 3 + 1]
            rgba[i * 4 + 2] = out[i * 3 + 2]
            rgba[i * 4 + 3] = 255
    elif ct == 0:
        for i in range(w * h):
            g = out[i]
            rgba[i * 4] = g
            rgba[i * 4 + 1] = g
            rgba[i * 4 + 2] = g
            rgba[i * 4 + 3] = 255
    elif ct == 4:
        for i in range(w * h):
            g = out[i * 2]
            rgba[i * 4] = g
            rgba[i * 4 + 1] = g
            rgba[i * 4 + 2] = g
            rgba[i * 4 + 3] = out[i * 2 + 1]
    elif ct == 3:
        for i in range(w * h):
            idx = out[i]
            rgba[i * 4] = plte[idx * 3]
            rgba[i * 4 + 1] = plte[idx * 3 + 1]
            rgba[i * 4 + 2] = plte[idx * 3 + 2]
            rgba[i * 4 + 3] = trns[idx] if (trns and idx < len(trns)) else 255
    return w, h, rgba


def write_png(path, w, h, rgba):
    """写出 RGBA8 非隔行 PNG。rgba 为 bytes/bytearray，长度 w*h*4。"""
    raw = bytearray()
    stride = w * 4
    for y in range(h):
        raw.append(0)  # filter type 0 (None)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        c = struct.pack('>I', len(data)) + typ + data
        c += struct.pack('>I', zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    out = bytearray(b'\x89PNG\r\n\x1a\n')
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(bytes(out))


def new_rgba(w, h, fill=(0, 0, 0, 0)):
    """新建点阵，fill 为 (r,g,b,a)。"""
    return bytearray(bytes(fill) * (w * h))


def get_px(px, w, x, y):
    i = (y * w + x) * 4
    return px[i], px[i + 1], px[i + 2], px[i + 3]


def set_px(px, w, x, y, rgba):
    i = (y * w + x) * 4
    px[i] = rgba[0]
    px[i + 1] = rgba[1]
    px[i + 2] = rgba[2]
    px[i + 3] = rgba[3]


def blit(dst, dw, dh, src, sw, sh, ox, oy, skip_alpha=False, alpha_thresh=0):
    """把 src 贴到 dst 的 (ox,oy)，越界自动裁剪。alpha_thresh>0 时忽略低于阈值的像素。"""
    x0 = max(0, -ox)
    y0 = max(0, -oy)
    x1 = min(sw, dw - ox)
    y1 = min(sh, dh - oy)
    for y in range(y0, y1):
        srow = (y * sw + x0) * 4
        drow = ((y + oy) * dw + (x0 + ox)) * 4
        n = (x1 - x0) * 4
        if not skip_alpha and alpha_thresh <= 0:
            dst[drow:drow + n] = src[srow:srow + n]
        else:
            for i in range(0, n, 4):
                a = src[srow + i + 3]
                if a > alpha_thresh:
                    dst[drow + i:drow + i + 4] = src[srow + i:srow + i + 4]


def alpha_bbox(px, w, h, thresh=8):
    """返回内容包围盒 (minx, miny, maxx, maxy) 含端点；空则 None。"""
    minx, miny, maxx, maxy = w, h, -1, -1
    for y in range(h):
        row = y * w * 4
        for x in range(w):
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
