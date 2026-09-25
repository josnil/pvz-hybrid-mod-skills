# -*- coding: utf-8 -*-
# --- LEGACY GUARD (2026-09-21) ---
# 本验证器针对「自制单帧素材」旧管线（frameMax=1 / 每个 media 1 帧 / 176x192 画布）。
# 工程现已改用官方素材直转（经典 PvZ SuperGatling.reanim.compiled：frameMax=87 / 1168 slice），
# 旧期望值不再适用 => 检测到 .dat frameMax != 1 时直接跳过，避免误导性 FAIL。
# 官方素材请改用同目录 verify_official_skin.py。
import os as _lg_os
import struct as _lg_struct

_LG_DAT = _lg_os.path.join(_lg_os.path.dirname(_lg_os.path.abspath(__file__)), "..",
                           "ModWorkspace", "SuperGatlingPea", "Resources", "Animations",
                           "SuperGatlingPea.dat")
try:
    with open(_LG_DAT, "rb") as _lg_f:
        _lg_fm = _lg_struct.unpack_from("<H", _lg_f.read(6), 4)[0]
except Exception:
    _lg_fm = 1
if _lg_fm != 1:
    print("[SKIP] %s：当前 .dat frameMax=%d（官方素材多帧），本验证器仅适用于旧自制单帧管线。"
          % (_lg_os.path.basename(__file__), _lg_fm))
    print("       请改用 .cache/verify_official_skin.py")
    raise SystemExit(0)
# --- /LEGACY GUARD ---
"""按 AdobeAnimateData.cs 的**精确读取顺序**回读 .dat，验证自制文件自洽。

读取序列严格照抄：
  LoadDatMetadataForModPreview :1028-1100
  ParseEditorDatHydration      :809-993  （元素 30 字节）
"""
import os
import struct
import sys

OUTDIR = os.path.dirname(os.path.abspath(__file__))


class R:
    def __init__(self, b):
        self.b = b
        self.o = 0

    def f32(self):
        v = struct.unpack_from('<f', self.b, self.o)[0]
        self.o += 4
        return v

    def f64i(self):
        v = struct.unpack_from('<q', self.b, self.o)[0]
        self.o += 8
        return v

    def u16(self):
        v = struct.unpack_from('<H', self.b, self.o)[0]
        self.o += 2
        return v

    def u32(self):
        v = struct.unpack_from('<I', self.b, self.o)[0]
        self.o += 4
        return v

    def skip(self, n):
        self.o += n

    def pstr(self):
        n = self.u32()
        s = self.b[self.o:self.o + n].decode('utf8')
        self.o += n
        return s


def parse(path):
    b = open(path, 'rb').read()
    r = R(b)
    info = {}
    info['frameRate'] = r.f32()
    info['frameMax'] = r.u16()
    AW = r.u16()
    AH = r.u16()
    info['atlas'] = (AW, AH)
    nbytes = r.f64i()
    info['pixelBytes'] = nbytes
    assert nbytes == AW * AH * 4, 'pixelBytes %d != %d*%d*4' % (nbytes, AW, AH)
    info['pixelOffset'] = r.o
    r.skip(nbytes)
    info['pixelEnd'] = r.o

    mc = r.u16()
    info['mediaCount'] = mc
    info['media'] = []
    for _ in range(mc):
        name = r.pstr()
        rect = (r.f32(), r.f32(), r.f32(), r.f32())
        info['media'].append((name, rect))

    lc = r.u16()
    info['layerCount'] = lc
    info['layers'] = []
    for _ in range(lc):
        lname = r.pstr()
        per_frame = []
        for _f in range(info['frameMax']):
            n = r.u16()
            elems = []
            for _e in range(n):
                mid = r.u16()
                xx, xy, yx, yy = r.f32(), r.f32(), r.f32(), r.f32()
                ox, oy = r.f32(), r.f32()
                a32 = r.u32()
                elems.append((mid, xx, xy, yx, yy, ox, oy, a32))
            per_frame.append(elems)
        info['layers'].append((lname, per_frame))

    cc = r.u16()
    info['clipCount'] = cc
    info['clips'] = []
    for _ in range(cc):
        cn = r.pstr()
        s0, s1 = r.u16(), r.u16()
        info['clips'].append((cn, s0, s1))

    ec = r.u16()
    info['eventFrameCount'] = ec
    info['events'] = []
    for _ in range(ec):
        fr = r.u16()
        ne = r.u16()
        evs = []
        for _ in range(ne):
            cmd = r.pstr()
            arg = r.pstr()
            evs.append((cmd, arg))
        info['events'].append((fr, evs))

    info['consumed'] = r.o
    info['fileSize'] = len(b)
    return info


def main():
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(OUTDIR, 'SuperGatlingPea.dat')
    info = parse(p)
    print('file        %s' % p)
    print('size        %d' % info['fileSize'])
    print('consumed    %d' % info['consumed'])
    print('trailing    %d  bytes' % (info['fileSize'] - info['consumed']))
    print('frameRate   %g' % info['frameRate'])
    print('frameMax    %d' % info['frameMax'])
    print('atlas       %dx%d' % info['atlas'])
    print('pixelBytes  %d  (offset %d..%d)' % (info['pixelBytes'], info['pixelOffset'], info['pixelEnd']))
    print('mediaCount  %d' % info['mediaCount'])
    for i, (n, rc) in enumerate(info['media']):
        print('    %d %-32s rect=(%g,%g,%g,%g)' % (i, n, *rc))
    print('layerCount  %d' % info['layerCount'])
    for ln, pf in info['layers']:
        counts = sorted(set(len(e) for e in pf))
        print('    %-10s frames=%d elem/frame=%s' % (ln, len(pf), counts))
    print('clipCount   %d' % info['clipCount'])
    for cn, a, bb in info['clips']:
        print('    %-12s %d..%d' % (cn, a, bb))
    print('events      %d' % info['eventFrameCount'])
    for fr, evs in info['events']:
        print('    frame %d -> %s' % (fr, evs))

    # 断言
    ok = True
    if info['fileSize'] != info['consumed']:
        print('FAIL: trailing bytes'); ok = False
    for ln, pf in info['layers']:
        for f, e in enumerate(pf):
            if len(e) == 0 and ln == 'body':
                print('WARN: %s frame %d empty' % (ln, f))
    if info['frameRate'] != 12.0:
        print('FAIL frameRate'); ok = False
    print()
    print('RESULT:', 'OK' if ok else 'FAIL')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
