# -*- coding: utf-8 -*-
r"""_j15_shift.py —— 第十五轮 ①：女王头**整体向上移动 dy 显示px**，重解 `head_offset`。

口径（与第十一轮/第十二轮一致，复用 `_j14_final.solve_for`）：
    target = 当前头块中心 + (0, −dy)   ⇒ 解 offset 使**参考帧**头块中心落到 target。
    · 参考帧：女王 `MoonWalk f0`（θ=0）；舞者 `Walk f0`（θ=20.33°）。
    · 只因「同一参考帧上 θ/scale 不变」⇒ 上移 dy 后整头在该帧**刚性平移 dy**，形状逐像素不变。

⚠️ dy 无参考图 ⇒ **口径默认值**（用户第十一轮「往上一点」实测 20.16px 是**量出来的**；
   本轮「向上移动一点」取 **dy = 8px** 保守值，要改只换 `--dy`）。

用法：
    python .cache/_j15_shift.py                 # 女王 dy=8
    python .cache/_j15_shift.py --dy 12         # 换量级
    python .cache/_j15_shift.py --char dancer --dy 0   # 舞者不动（默认）
"""
from __future__ import annotations

import argparse
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from _j14_final import solve_for          # noqa: E402
from _j14_gap import BO, GAME             # noqa: E402
from _j14_follow import BODY_CLIP         # noqa: E402
from head_fit import Skin                 # noqa: E402
from head_place import Placement, center  # noqa: E402

g = lambda *p: os.path.join(GAME, *p)     # noqa: E731

# ★ 当前生成器口径（第十四轮换层后）
CUR = {
    'queen': dict(
        body=g('Asset', 'Anime', 'Character', 'Zombie', 'Challenge', 'DiscoFire',
               'ZombieDiscoFire.tres'),
        head=g('Asset', 'Anime', 'Character', 'Plant', 'Gold', 'QueenSunFlower',
               'QueenSunFlower.tres'),
        follow=28, scale=1.08, off=(-76.9485, 10.3213)),
    'dancer': dict(
        body=g('Asset', 'Anime', 'Character', 'Zombie', 'Challenge', 'DancerFire',
               'ZombieDancerFire.tres'),
        head=g('Asset', 'Anime', 'Character', 'Zombie', 'Chapter1', 'Normal', 'Sprite',
               'Sunflower', 'SunFlowerHead.tres'),
        follow=22, scale=1.0, off=(-48.6837, -37.1999)),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--char', default='queen', choices=sorted(CUR))
    ap.add_argument('--dy', type=float, default=8.0, help='向上移动的显示px（正数=上）')
    a = ap.parse_args()
    W = sys.stdout.write
    C = CUR[a.char]
    S = C['scale']
    B = Skin(C['body'])
    bc = BODY_CLIP[a.char]
    fref = B.clips[bc][0]
    PL = Placement(C['body'], BO, C['follow'], bc, C['head'], 'Idle', 'anim_idle',
                   scale=(-S, S))
    off0 = C['off']
    mass0 = center(PL.place_box(PL.mass_box, off0))
    box0 = PL.place_box(PL.all_box, off0)
    W("角色 %s  参考帧 %s f%d  θ(L%d)=%.4f°  S=%.3f  跟随层 L%d\n"
      % (a.char, bc, fref, C['follow'], PL.body_rot_deg(fref), S, C['follow']))
    W("  现状 OFF=(%.4f, %.4f)  头块中心=(%.4f, %.4f)\n"
      % (off0[0], off0[1], mass0[0], mass0[1]))
    W("  整头落点 (x %.2f..%.2f  y %.2f..%.2f)\n" % (box0[0], box0[2], box0[1], box0[3]))

    target = (mass0[0], mass0[1] - a.dy)
    off1 = solve_for(PL, target)
    mass1 = center(PL.place_box(PL.mass_box, off1))
    box1 = PL.place_box(PL.all_box, off1)
    W("  目标 dy=%.2f ⇒ 新 OFF=(%.4f, %.4f)\n" % (a.dy, off1[0], off1[1]))
    W("  新头块中心=(%.4f, %.4f)   实际位移=(%.6f, %.6f)（期望 (0, %.2f)）\n"
      % (mass1[0], mass1[1], mass1[0] - mass0[0], mass1[1] - mass0[1], -a.dy))
    W("  整头落点 (x %.2f..%.2f  y %.2f..%.2f)  ⇒ 形状差=max|Δ| %.2e / dy 精确性=%.2e\n"
      % (box1[0], box1[2], box1[1], box1[3],
         max(abs((box1[2] - box1[0]) - (box0[2] - box0[0])),
             abs((box1[3] - box1[1]) - (box0[3] - box0[1]))),
         abs((mass1[1] - mass0[1]) + a.dy)))
    W("\n  ⇒ 生成器常量： head_offset=(%.4f, %.4f)   （跟随层仍 %d）\n"
      % (off1[0], off1[1], C['follow']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
