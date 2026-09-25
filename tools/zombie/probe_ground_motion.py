# -*- coding: utf-8 -*-
"""量出各个内置僵尸 .tres 里 _ground 层的漂移：每周期总位移 / 周期帧数 ⇒ 真实移速。

用法: python probe_ground_motion.py <tres> [<tres> ...]
不带参数则跑内置样本集。
"""
import re
import sys

ROOT = r'D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28'

SAMPLES = [
    ('普通僵尸(慢)', r'Asset\Anime\Character\Zombie\Chapter1\Normal\ZombieNormal.tres'),
    ('橄榄球僵尸(快)', r'Asset\Anime\Character\Zombie\Chapter1\Football\ZombieFootball.tres'),
    ('摇旗僵尸(稍快)', r'Asset\Anime\Character\Zombie\Chapter1\Normal\ZombieFlag.tres'),
]


def arr(txt, name):
    m = re.search(r'^%s = Packed\w+Array\(([^)]*)\)' % name, txt, re.M)
    return [float(x) for x in m.group(1).split(',')] if m else None


def clocks(txt):
    m = re.search(r'^clips = \{(.*?)\n\}', txt, re.S)
    out = {}
    if m:
        for line in m.group(1).splitlines():
            mm = re.search(r'"([^"]+)"\s*:\s*Vector2i\((\d+),\s*(\d+)\)', line)
            if mm:
                out[mm.group(1)] = (int(mm.group(2)), int(mm.group(3)))
    return out


def report(label, path):
    try:
        txt = open(path, encoding='utf8').read()
    except OSError as e:
        print('%-16s 读取失败: %s' % (label, e))
        return
    fo, fc = arr(txt, 'frameOffsets'), arr(txt, 'frameCounts')
    sl, st = arr(txt, 'sliceLayerIds'), arr(txt, 'sliceTransforms')
    if fo is None or sl is None:
        print('%-16s 不是帧数组格式' % label)
        return
    ox = {}
    for f in range(len(fo)):
        s, n = int(fo[f]), int(fc[f])
        for k in range(n):
            i = s + k
            if int(sl[i]) == 0:
                ox[f] = st[i * 6 + 4]
    fr = re.search(r'^frameRate = ([\d.]+)', txt, re.M)
    fmax = re.search(r'^frameMax = (\d+)', txt, re.M)
    print('== %s ==' % label)
    print('   file      : %s' % path.replace(ROOT + '\\', ''))
    print('   frameRate : %s   frameMax: %s' % (fr.group(1) if fr else '?',
                                                fmax.group(1) if fmax else '?'))
    print('   clips     : %s' % clocks(txt))
    if not ox:
        print('   _ground   : **无切片** ⇒ 该角色不能自主前进')
        print()
        return
    fs = sorted(ox)
    print('   _ground   : 帧 %d..%d，共 %d 帧' % (fs[0], fs[-1], len(fs)))
    # 找锯齿回跳（Δx < -1 视为周期边界）。用排序后的相邻帧，避免帧号断档。
    cycles = []
    start = fs[0]
    prev_f = fs[0]
    for f in fs[1:]:
        if ox[f] - ox[prev_f] < -1:
            cycles.append((start, prev_f, ox[prev_f] - ox[start], prev_f - start + 1))
            start = f
        prev_f = f
    cycles.append((start, fs[-1], ox[fs[-1]] - ox[start], fs[-1] - start + 1))
    print('   周期      : %d 个' % len(cycles))
    for a, b, dx, n in cycles[:5]:
        px_per_s = dx / n * float(fr.group(1)) if fr else 0.0
        print('     帧 %3d..%-3d  位移 %+8.2f px / %3d 帧  ⇒ %6.2f px/s' % (a, b, dx, n, px_per_s))
    print()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            report(p, p)
    else:
        for label, rel in SAMPLES:
            report(label, ROOT + '\\' + rel)
