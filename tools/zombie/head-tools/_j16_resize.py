# -*- coding: utf-8 -*-
r"""_j16_resize.py —— 第十六轮：女王头**缩放改回 2.0 倍** + **位置回调到之前** ，一次解出 `head_offset`。

用户 2026-09-25 第十六轮原话：
    「将女王的头部位置**回调至之前的状态**，并将头部的缩放比例调整为**原有的 2.0 倍**，
      确保两项调整**同时生效且相互不冲突**。」

为什么这两项会「冲突」：
    `A = rot_scale(θ, −s, +s)` **含节点 scale**（见 `head_place.py` 头注 / 铁律 27）
    ⇒ **改 scale 必须重解 offset**，否则头横竖都跑偏（残差 ∝ Δs，实测 5~50px）。
    本脚本把两件事**一次解**：在**新 scale** 下让「头块中心」落到目标位置。

为什么「钉住头块中心」就等于「位置不变」（数学依据）：
    · 头是**刚体**、参考帧上「同旋转 + 同缩放 + 一点钉住 ⇒ 整头全等」
      ⇒ 把「头块（`anim_idle` 火焰脸）中心」钉到同一个显示坐标 ⇒ 整头在该帧**逐像素一致**；
    · `Placement.target` = 身体**跟随层**全帧并集 bbox 中心 —— 只取决于身体、**与 head scale 无关**，
      且在任何 scale 下 `solve_for(PL, target)` 都能把「头块中心」**精确钉到** `target`。
    ⇒ 「位置保持、只改尺寸」= **沿用同一个 target（= 上一版头块中心的绝对坐标）、换 scale 重解**
      ⇒ 两项天然不冲突（这正是用户要的「同时生效」）。

⚠️⚠️ **不能用 `Placement.solve(shift=…)` 复现历史位移**：那些 `shift`（如 `(0,-20.1565)`）是
    第十一轮在 **L19 口径**下定的（`_sq_head_place.py` 至今写死 `follow=19`，**已过期**）；
    第十四轮换成 **L28** 后是按「保头块中心」重解的 ⇒ `screen_delta` 相对**新**锚点已不是历史值
    （实测 `(-3.7002, 30.2434)` vs 期望 `(0,-20.1565)`）。
    ⇒ 本脚本一律用**头块中心的绝对坐标**做目标（= `_j14_final.solve_for` / `_j15_shift.py` 的口径）。

两种「之前的状态」（`--pos-src`）：
    prev = 第十四轮末（**只撤销第十五轮的 8px 上移**）
           ⇒ 目标 = 上一版头块中心 `(-10.2002, -55.2566)`
    zero = 更早的 **2.0 倍那一版**（**连第十一轮的 20.1565px 上移也撤销**）
           ⇒ 目标 = `(-10.2002, -55.2566 + 20.1565) = (-10.2002, -35.1001)`

用法：
    python .cache/_j16_resize.py                          # 默认 scale=0.9(2.0×) + prev
    python .cache/_j16_resize.py --pos-src zero            # 换成「2.0 倍时代」，一并撤销 20.16px
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from _j14_final import solve_for          # noqa: E402
from _j14_gap import BO, GAME             # noqa: E402
from _j14_follow import BODY_CLIP         # noqa: E402
from head_place import Placement, center  # noqa: E402

g = lambda *p: os.path.join(GAME, *p)     # noqa: E731

FOLLOW = 28                               # 第十四轮换到的 anim_hair1（女王）
BASE_SCALE = 0.45                         # 本包倍率基准（倍率 = S / 0.45）
UP11 = 20.1565                            # 第十一轮「往上一点」的上移量（显示 px）
# 历史口径（第十四轮末 / 第十五轮末）
PREV = dict(scale=1.08, off=(-76.9485, 17.7287))
CUR = dict(scale=1.08, off=(-76.9485, 10.3213))

BODY = g('Asset', 'Anime', 'Character', 'Zombie', 'Challenge', 'DiscoFire',
         'ZombieDiscoFire.tres')
HEAD = g('Asset', 'Anime', 'Character', 'Plant', 'Gold', 'QueenSunFlower',
         'QueenSunFlower.tres')


def build(scale):
    return Placement(BODY, BO, FOLLOW, BODY_CLIP['queen'], HEAD, 'Idle', 'anim_idle',
                     scale=(-scale, scale))


def _b(b):
    return "(x %.2f..%.2f y %.2f..%.2f  中心=(%.4f,%.4f)  宽高 %.2f x %.2f)" % (
        b[0], b[2], b[1], b[3], (b[0] + b[2]) / 2.0, (b[1] + b[3]) / 2.0,
        b[2] - b[0], b[3] - b[1])


def describe(tag, P, off, target, W):
    mass = center(P.place_box(P.mass_box, off))
    box = P.place_box(P.all_box, off)
    W("  %-6s S=%.3f(%.2f×)  OFF=(%.4f, %.4f)\n"
      % (tag, P.scale[1], P.scale[1] / BASE_SCALE, off[0], off[1]))
    W("         头块中心=(%.4f, %.4f)   整头=%s\n" % (mass[0], mass[1], _b(box)))
    if target is not None:
        W("         目标=(%.4f, %.4f)  偏差=(%.8f, %.8f)   ⇒ %s\n"
          % (target[0], target[1], mass[0] - target[0], mass[1] - target[1],
             "钉住 OK" if (abs(mass[0] - target[0]) < 1e-9
                           and abs(mass[1] - target[1]) < 1e-9) else "✗ 未钉住"))
    return mass, box


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--scale', type=float, default=round(BASE_SCALE * 2.0, 4),
                    help='女王头缩放绝对值（默认 0.45*2.0 = 0.9 ⇒ **2.0 倍**）')
    ap.add_argument('--pos-src', default='prev', choices=('prev', 'zero'),
                    help='「之前的状态」基准：prev=撤销第十五轮 8px / zero=回到 2.0 倍时代')
    a = ap.parse_args()
    W = sys.stdout.write
    S_new = abs(a.scale)
    W("女王 scale: %.3f → %.3f（倍率 %.2f× → **%.2f×**，基准 %.2f）\n"
      % (CUR['scale'], S_new, CUR['scale'] / BASE_SCALE, S_new / BASE_SCALE, BASE_SCALE))
    W("锚点（身体跟随层 L%d 全帧并集中心）= (%.4f, %.4f)"
      "  ⚠️ 仅供参照，本脚本用**头块中心绝对坐标**做目标\n\n"
      % (FOLLOW, build(S_new).target[0], build(S_new).target[1]))

    W("── 现状（第十五轮末）─────────────────────────────\n")
    m_cur, b_cur = describe('现状', build(CUR['scale']), CUR['off'], None, W)
    W("\n── 上一版（第十四轮末 = 撤销 8px）─────────────────\n")
    m_prev, b_prev = describe('上一版', build(PREV['scale']), PREV['off'], None, W)

    # ★ 本轮目标
    t_prev = m_prev
    t_zero = (m_prev[0], m_prev[1] + UP11)
    target = t_prev if a.pos_src == 'prev' else t_zero

    Pn = build(S_new)
    off_new = solve_for(Pn, target)
    W("\n── ★ 本轮解（scale=%.3f / --pos-src %s）─────────\n" % (S_new, a.pos_src))
    m_new, b_new = describe('新值', Pn, off_new, target, W)
    W("\n  ⇒ 生成器常量： head_scale=%s  head_offset=(%.4f, %.4f)\n"
      % (S_new, off_new[0], off_new[1]))

    # 另一档对照
    t_alt = t_zero if a.pos_src == 'prev' else t_prev
    off_alt = solve_for(Pn, t_alt)
    W("  （另一种「之前」--pos-src %s ⇒ head_offset=(%.4f, %.4f)，头块中心=(%.4f, %.4f)）\n"
      % ('zero' if a.pos_src == 'prev' else 'prev', off_alt[0], off_alt[1],
         t_alt[0], t_alt[1]))

    W("\n── 校验 ─────────────────────────────────────────\n")
    W("  新头块中心 − 上一版头块中心 = (%.8f, %.8f)   ⇒ %s\n"
      % (m_new[0] - m_prev[0], m_new[1] - m_prev[1],
         "位置逐字不变" if (abs(m_new[0] - m_prev[0]) < 1e-9
                            and abs(m_new[1] - m_prev[1]) < 1e-9) else "★ 有位移"))
    W("  新整头宽高 %.2f x %.2f   上一版 %.2f x %.2f   比值 %.4f / %.4f （期望 %.4f）\n"
      % (b_new[2] - b_new[0], b_new[3] - b_new[1],
         b_prev[2] - b_prev[0], b_prev[3] - b_prev[1],
         (b_new[2] - b_new[0]) / (b_prev[2] - b_prev[0]),
         (b_new[3] - b_new[1]) / (b_prev[3] - b_prev[1]),
         S_new / PREV['scale']))
    W("  ⚠️ 旧 offset 配新 scale(%.3f) 的偏差 = %.4f px（反向印证「改 scale 必须重解」）\n"
      % (S_new, Pn.residual(CUR['off'], shift=(target[0] - Pn.target[0],
                                               target[1] - Pn.target[1]))[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
