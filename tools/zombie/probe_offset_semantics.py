# -*- coding: utf-8 -*-
"""判定 sprite.offset 与 .tres 元素 (ox,oy) 的叠加关系。

做法：取内置 ZombieNormal 的一个已知帧，分别用
   (a) node = (ox,oy) + M(p)                    （不加 offset）
   (b) node = offset + (ox,oy) + M(p)           （加 offset = (-40,-80)）
去算 bbox，与官方栅格合成图 ZombieNormalRasterCompositeData.tres 给出的
   node = tile_pixel - origin   (origin = (-52,-86), tile = 105x134)
做比对，唯一匹配者即真。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anime_io  # noqa: E402

GAME = r'D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版'
UNPACK = r'D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28'
NORMAL = os.path.join(UNPACK, 'Asset', 'Anime', 'Character', 'Zombie', 'Chapter1', 'Normal')

OFFSET = (-40.0, -80.0)          # 内置 ZombieNormal 精灵节点的 offset
ORIGIN = (-52.0, -86.0)          # 栅格合成图锚点
TILE = (105, 134)


def media_rect(mr, mid):
    x, y, w, h = mr[mid * 4:mid * 4 + 4]
    return x, y, w, h


_ATLAS = None


def _atlas():
    """返回 (PIL 图集, PIL 栅格合成图)。

    关键：mediaRects 的坐标是 **.dat 内嵌图集** 的坐标，
    而 tile 目标图是 Generated/ 下的栅格合成图 —— 两者是不同的图。
    """
    global _ATLAS
    if _ATLAS is not None:
        return _ATLAS
    from PIL import Image
    dd = anime_io.parse_dat(os.path.join(NORMAL, 'ZombieNormal.dat'))
    atlas = Image.frombytes('RGBA', (dd['atlasW'], dd['atlasH']), dd['pixels'])
    comp = None
    gen = os.path.join(NORMAL, 'Generated')
    for n in sorted(os.listdir(gen)):
        if n.endswith('.png') and 'Composite' in n and 'Data' not in n:
            comp = Image.open(os.path.join(gen, n)).convert('RGBA')
            break
    _ATLAS = (atlas, comp)
    return _ATLAS


def _visible_box(img, rect):
    x, y, w, h = (int(round(v)) for v in rect)
    sub = img.crop((x, y, x + w, y + h))
    bb = sub.getbbox()
    if bb is None:
        return None
    return bb  # 相对 rect 左上角


def bbox_of(d, frame, add_offset, img, cache):
    """该帧所有 slice 的 node-local bbox（用 media 的可见像素 bbox）。"""
    fo, N = d['frameOffsets'], len(d['sliceKeys'])
    a, b = fo[frame], (fo[frame + 1] if frame + 1 < len(fo) else N)
    xs, ys = [], []
    for i in range(a, b):
        mid = d['sliceMediaIds'][i]
        rect = media_rect(d['mediaRects'], mid)
        if rect not in cache:
            cache[rect] = _visible_box(img, rect)
        vb = cache[rect]
        if vb is None:
            continue
        vx0, vy0, vx1, vy1 = vb
        t = d['sliceTransforms'][i * 6:i * 6 + 6]
        xx, xy, yx, yy, ox, oy = t
        for vx, vy in ((vx0, vy0), (vx1, vy0), (vx0, vy1), (vx1, vy1)):
            nx = xx * vx + yx * vy + ox
            ny = xy * vx + yy * vy + oy
            if add_offset:
                nx += OFFSET[0]
                ny += OFFSET[1]
            xs.append(nx)
            ys.append(ny)
    if not xs:
        return None
    return (min(xs), min(ys), max(xs), max(ys))


def tile_bbox(frame, cols=32):
    """该帧在栅格合成图里对应 tile 的非透明像素 bbox → node-local。"""
    atlas, comp = _atlas()
    cx, cy = frame % cols, frame // cols
    tile = comp.crop((cx * TILE[0], cy * TILE[1], (cx + 1) * TILE[0], (cy + 1) * TILE[1]))
    bb = tile.getbbox()   # include alpha
    if bb is None:
        return None
    x0, y0, x1, y1 = bb
    return (x0 + ORIGIN[0], y0 + ORIGIN[1], (x1 - 1) + ORIGIN[0], (y1 - 1) + ORIGIN[1])


def main():
    d = anime_io.parse_tres(os.path.join(NORMAL, 'ZombieNormal.tres'))
    print('frameMax=%d  N=%d  mediaRects=%d  offset_test=%s'
          % (d['frameMax'], len(d['sliceKeys']), len(d['mediaRects']) // 4, OFFSET))
    print()
    hdr = '%-6s %-30s %-30s %-30s' % ('frame', 'A: (ox,oy)+M(p)', 'B: offset+(ox,oy)+M(p)', 'TARGET: tile-origin')
    print(hdr)
    print('-' * len(hdr))
    atlas, comp = _atlas()
    cache = {}
    ok_a = ok_b = 0
    tot = 0
    for f in (44, 45, 46, 47, 20, 21, 22, 90, 91, 60, 100, 150):
        if f >= d['frameMax']:
            continue
        a = bbox_of(d, f, False, atlas, cache)
        b = bbox_of(d, f, True, atlas, cache)
        t = tile_bbox(f)
        if not a or not t:
            continue
        tot += 1
        sa = '(%6.1f,%6.1f,%6.1f,%6.1f)' % a
        sb = '(%6.1f,%6.1f,%6.1f,%6.1f)' % b
        st = '(%6.1f,%6.1f,%6.1f,%6.1f)' % t
        ma = max(abs(a[i] - t[i]) for i in range(4)) <= 2.0
        mb = max(abs(b[i] - t[i]) for i in range(4)) <= 2.0
        ok_a += ma
        ok_b += mb
        print('%-6d %-30s %-30s %-30s  A=%s B=%s' % (f, sa, sb, st, 'Y' if ma else '.', 'Y' if mb else '.'))
    print()
    print('MATCH  A(no offset)=%d/%d   B(with offset)=%d/%d' % (ok_a, tot, ok_b, tot))
    print('=> sprite.offset 是否叠加到元素变换之上: %s'
          % ('YES (B)' if ok_b > ok_a else ('NO (A)' if ok_a > ok_b else 'AMBIGUOUS')))


if __name__ == '__main__':
    main()
