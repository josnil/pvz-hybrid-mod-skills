# -*- coding: utf-8 -*-
"""check_head_fit.py —— 换头对位的「数据侧反解 + 生成器常量核对」（回归门）

为什么要有它：
  `build_zombie_super_gatling_paper.py` 里的 `HEAD_OFFSET` 是**算出来的**，
  不是抄来的。手抄一个数字进生成器 = 下次换头/换身体必然漂。本脚本把推导过程固化：
  离线读两份 `.tres`，按引擎的真实变换公式反解，再和生成器里的常量对账。

数学**只在** `.cache/head_place.py` 里写一份（单一直源），本脚本只负责「对账 + 判定」。

引擎的真实变换（`AdobeAnimateSprite.UpdateChild()`，`AdobeAnimateSprite.cs:5259-5281`）：
    子精灵每帧被覆盖：Position = <被跟随图层 L 的 pose>.Origin + <父精灵的 offset>
                      Rotation = <被跟随图层 L 的 pose>.Rotation + child.offsetRotate
  绘制自己美术时 `transform = transform.Translated(child.offset)`（`:7044 / :7071 / :7362`）
  ⇒ `child.offset` 在**子精灵自己的美术坐标系**里，且会被节点 `scale = (-1,1)` 一起翻。

★★ 版本沿革（每一轮的口径都不同，**别拿旧结论套新版本**）：

  第二轮（2026-09-23）「摆正、不再歪斜」：
    `Rotation` 的覆写有开关 `useRotate`（`AdobeAnimateSprite.cs:275-282` / `:5259-5276`）
    ⇒ 场景写 `useRotate = false` + 常量 `rotation` ⇒ net 旋转从「每帧摆动」变成「场景常量」。
    本轮判据：`HEAD_OFFSET == solve(node_rot=HEAD_FIXED_ROT_DEG)`。
    ⚠️ 单位坑：`offsetRotate` / `rotation` 都是**弧度**。官方样本
       `ZombieNormalGatlingPea.tscn` 的 `offsetRotate = -0.25` 是 −0.25 rad = −14.324°；
       按「度」读会把交叉校验残差算成 3.96px（真值 4.61px）—— 错得不明显，所以一直没红。

  第三轮（2026-09-23）「回退头部动画 + 头部初始位置向右上微移」：
    ① 回退 ⇒ `HEAD_FIX_HEAD_ROTATE = False` ⇒ 引擎恢复每帧覆写 `Rotation`
       ⇒ 判据回到 `HEAD_OFFSET == solve(跟随层, body_frame=0)`（**不是** node_rot）。
    ② 微移 ⇒ 新增 `HEAD_PLACE_SHIFT`（**屏幕空间** dx,dy，y 向下；右上 = +x,−y）。
       ⇒ 判据从「落点中心必须压在原头中心（≤2px）」改成
          「**屏幕位移必须逐字等于 HEAD_PLACE_SHIFT**」+「头块与原头仍有实质重叠」。
       ⚠️ 旧判据（中心距 ≤2px）在本轮**必然假红** —— 那正是"有意偏移"的定义。
       ⚠️ 旧判据的第二半（"四边超出 ≤10px"）同样不能再当门槛：偏移是有意的，
          它只会随 shift 单调变差；真正要防的是"悬空/飞出去"，用**重叠比例**表达更准。

  第四轮（2026-09-24）「让子弹生成位置靠左一点，对齐子弹发射口」：
    子弹生成点 = `FireComponentDefinition.firePosMarkerPaths` 指向的 Marker2D 的世界位置
    （`FireComponent.cs:2708-2714`）。本轮把它从 HeadSlot 原点挪到炮口上。
    ⇒ 新增判据 ④，且**两个来源互相独立**（防「拿生成器常量比生成器常量」）：
      · 炮口点 ← 从 barrel 轨美术反推（`_muzzle_probe.derive_muzzle_pose`）；
      · 生成点 ← 从**生成的场景 .tscn** 现场反读（HeadSlot 的 rot/scale **会**作用在
        FireMarker 的局部坐标上 —— `space = slot.pos + M(θ,s)·marker + BODY_OFFSET`，
        旧版把这一步漏了，只在 marker == (0,0) 时才等价）。
    ⚠️ 静态 `FireMarker.position` **只能对上参考帧 bf=0**（与 `HEAD_OFFSET` 同口径）：
      头是跟 `anim_head1` 逐帧摆的 ⇒ 炮口每帧都在动（Idle 段最大离线 10.86px，
      Walk/Eat 更大）。「每帧都对齐」由插件 `SyncHeadPairs()` 每帧覆写 marker 完成，
      **不在本页判定**（本页只判静态兜底值 + 记录天花板）。
"""
from __future__ import annotations

import io
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from head_fit import fmt_box  # noqa: E402
import head_place as HP  # noqa: E402

WS = os.path.dirname(HERE)
GAME = HP.GAME
AZ = HP.AZ
AP = HP.AP
GENERATOR = os.path.join(WS, 'build_zombie_super_gatling_paper.py')

TOL_PX = 6.0          # 官方样本「手调偏移」与「纯几何对齐」的差（实测 1.6 / 4.6）⇒ 上限 6px
TOL_OFFSET_PX = 1e-3  # 生成器 HEAD_OFFSET 与反解的差（常量写 4 位小数 ⇒ 理论 ≤ 7e-5）
TOL_SHIFT_PX = 1e-3   # 屏幕位移与 HEAD_PLACE_SHIFT 的差
MIN_COVER = 0.60      # 头块必须覆盖原头包围盒的面积比例（防「悬空/飞出去」）


def tres(*p):
    return os.path.join(GAME, *p)


def read_generator_constants():
    """从生成器读回 `HEAD_*` 常量（含本体开关、固定旋转、平移量、`z_index`）。"""
    s = io.open(GENERATOR, encoding='utf-8').read()

    def num(name, cast=float):
        m = re.search(r'^' + name + r'\s*=\s*(-?[\d.]+)', s, re.M)
        if not m:
            raise RuntimeError('生成器里找不到常量 %s' % name)
        return cast(m.group(1))

    def pair(name):
        m = re.search(r'^' + name + r'\s*=\s*\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)',
                      s, re.M)
        if not m:
            raise RuntimeError('生成器里找不到二元组常量 %s' % name)
        return (float(m.group(1)), float(m.group(2)))

    return {
        'offset': pair('HEAD_OFFSET'),
        'place_shift': pair('HEAD_PLACE_SHIFT'),
        'fixed_rot_deg': num('HEAD_FIXED_ROT_DEG'),
        # ⚠️ 用 `= False` 反向匹配：写成 `HEAD_FIX_HEAD_ROTATE = 0` 之类也要能被判成"关"，
        #    否则「开关被改坏」会静默走 True 分支（假绿）。
        'fix_rotate': bool(re.search(r'^HEAD_FIX_HEAD_ROTATE\s*=\s*True\s*$', s, re.M)),
        'node_z': num('HEAD_NODE_Z_INDEX', int),
        'offset_rotate': num('HEAD_OFFSET_ROTATE'),
        # 第四轮：炮口 / 子弹生成点
        'muzzle_pose': pair('MUZZLE_POSE'),
        'fire_marker': pair('FIRE_MARKER_POS'),
        'head_slot_pos': pair('HEAD_SLOT_POS'),
    }


def analyse(name, P, node_rot=None, offset_rot_deg=0.0, shift=None, declared=None):
    """打印一份对位分析；`declared` 给了就同时打印落点与「屏幕位移」。"""
    kw = {'node_rot': node_rot} if node_rot is not None else {'offset_rot_deg': offset_rot_deg}
    s = P.solve(shift=shift, **kw)
    print('== %s' % name)
    print('   身体 %s  clip=%s  跟随图层 L%d（rot=%+.2f°）'
          % (os.path.basename(P.body_tres), P.body_clip, P.follow, s['body_rot_deg']))
    print('   头   %s  clip=%s  头块=L%d'
          % (os.path.basename(P.head_tres), P.head_clip, P.mass_layer))
    print('   bodyOffset=%s  ⇒ 节点位置=(%.2f, %.2f)  net rot=%+.2f°  scale=%s'
          % (P.body_off, s['node'][0], s['node'][1], s['node_rot_deg'], P.scale))
    print('   原头包围盒(身体局部)   %s' % fmt_box(P.body_box))
    print('   头块包围盒(头自身局部) %s' % fmt_box(P.mass_box))
    print('   新头整体包围盒         %s' % fmt_box(P.all_box))
    print('   ★ 反解 offset = (%+.4f, %+.4f)  [把「头块中心」对到「原头中心 %s」]'
          % (s['offset'][0], s['offset'][1],
             ('+ shift(%+.2f,%+.2f)' % tuple(s['shift'])) if any(s['shift']) else ''))

    for tag, off in ([('反解值', s['offset'])]
                     + ([('生成器现值', declared)] if declared else [])):
        got = P.place_box(P.mass_box, off, **kw)
        allb = P.place_box(P.all_box, off, **kw)
        sd = P.screen_delta(off, **kw)
        print('   %-10s 头块落点 %s' % (tag, fmt_box(got)))
        print('   %-10s 屏幕位移 (%+.4f, %+.4f)  覆盖原头 %.3f  整体落点 %s'
              % ('', sd[0], sd[1], cover_ratio(got, P.body_box), fmt_box(allb)))
    print('   原头中心 = (%+.2f,%+.2f)' % s['target'])
    print()
    return s


def cover_ratio(got, ref):
    """`got` 覆盖 `ref` 的面积比例（0~1）。用来表达「头块还压在原头上」。"""
    ix = max(0.0, min(got[2], ref[2]) - max(got[0], ref[0]))
    iy = max(0.0, min(got[3], ref[3]) - max(got[1], ref[1]))
    a_ref = max(0.0, ref[2] - ref[0]) * max(0.0, ref[3] - ref[1])
    if a_ref <= 0:
        return 0.0
    return (ix * iy) / a_ref


def fit_ok(P, offset, node_rot=None, offset_rot_deg=0.0, shift=(0.0, 0.0),
           tol=TOL_SHIFT_PX):
    """本轮判据：**屏幕位移逐字等于 shift**（±tol）+ 头块仍覆盖原头 ≥ MIN_COVER。

    返回 (ok, 位移误差, 覆盖比例, 落点, 原头盒)。
    """
    kw = {'node_rot': node_rot} if node_rot is not None else {'offset_rot_deg': offset_rot_deg}
    got = P.place_box(P.mass_box, offset, **kw)
    sd = P.screen_delta(offset, **kw)
    err = math.hypot(sd[0] - shift[0], sd[1] - shift[1])
    return (err <= tol and cover_ratio(got, P.body_box) >= MIN_COVER,
            err, cover_ratio(got, P.body_box), got, P.body_box)


def main():
    fails = []

    # ---- 交叉校验：官方样本 A（ZombieNormal + 植物 GatlingPea）----
    #  官方场景常量：offsetRotate = -0.25（★ 弧度 = -14.3239°），手调 headOffset = (-58,-5)
    #  ⚠️ 这一条**与本包口径无关**，它只验「变换模型 + 锚点选得对」⇒ 保留不改。
    OFFICIAL_OFFSET_ROT_RAD = -0.25
    P_off = HP.official_placement()
    s_off = analyse('交叉校验 · 官方样本 A（ZombieNormal + GatlingPea）', P_off,
                    offset_rot_deg=math.degrees(OFFICIAL_OFFSET_ROT_RAD),
                    declared=(-58.0, -5.0))
    d_a = math.hypot(s_off['offset'][0] - (-58.0), s_off['offset'][1] - (-5.0))
    print('   ⇒ 与官方手调值 (-58,-5) 相差 %.2f px（官方美术微调量级；阈值 %.1f）' % (d_a, TOL_PX))
    print('   （注意：`offsetRotate = -0.25` 是**弧度** ⇒ -14.324°；按「度」读会得到 3.96px 的假值）')
    if d_a > TOL_PX:
        fails.append('官方样本反解偏差 %.2fpx > %.1fpx —— 变换模型或锚点选错了' % (d_a, TOL_PX))
    # 负向：把「度/弧度」搞错（按 -0.25° 算）应当**明显偏离**官方手调值
    s_bad = P_off.solve(offset_rot_deg=-0.25)
    d_bad = math.hypot(s_bad['offset'][0] - (-58.0), s_bad['offset'][1] - (-5.0))
    print('   负向（单位写错：按 -0.25° 当度）⇒ 偏差 %.2f px，应 ≠ 正解的 %.2f px'
          % (d_bad, d_a))
    if abs(d_bad - d_a) < 0.2:
        fails.append('单位负向测试失去区分度（度/弧度算出来一样）')
    print()

    # ---- 我们的样本 ----
    g = read_generator_constants()
    P = HP.paper_placement()
    # 口径由开关决定：True = 冻结固定角；False = 跟随被跟随图层（本版）
    node_rot = g['fixed_rot_deg'] if g['fix_rotate'] else None
    kw = ({'node_rot': node_rot} if node_rot is not None else {'offset_rot_deg': 0.0})
    s = analyse('本包（ZombiePaper + SuperGatlingPea）', P,
                shift=g['place_shift'], declared=g['offset'], **kw)

    d = math.hypot(s['offset'][0] - g['offset'][0], s['offset'][1] - g['offset'][1])
    print('   口径                   = %s'
          % ('冻结 net %g°' % g['fixed_rot_deg'] if g['fix_rotate']
             else '跟随 anim_head1（net %+.2f° @ frame0）' % s['node_rot_deg']))
    print('   生成器 HEAD_PLACE_SHIFT = (%g, %g)  [屏幕空间 dx,dy；右上 = +x,−y]'
          % g['place_shift'])
    print('   生成器 HEAD_OFFSET      = (%g, %g)' % g['offset'])
    print('   数据反解                = (%.4f, %.4f)' % s['offset'])
    print('   差                      = %.6f px（阈值 %g）' % (d, TOL_OFFSET_PX))
    if d > TOL_OFFSET_PX:
        fails.append('生成器 HEAD_OFFSET 与数据反解相差 %.6fpx（应改为 (%.4f, %.4f)）'
                     % (d, s['offset'][0], s['offset'][1]))

    # 判据 ①（本轮核心）：屏幕位移必须逐字等于 HEAD_PLACE_SHIFT
    ok, err, cov, got, ref = fit_ok(P, g['offset'], shift=g['place_shift'], **kw)
    sd = P.screen_delta(g['offset'], **kw)
    print('   落点核对：头块 %s' % fmt_box(got))
    print('             原头 %s' % fmt_box(ref))
    print('             屏幕位移 (%+.4f, %+.4f)  与 HEAD_PLACE_SHIFT 差 %.6fpx（<=%g）'
          % (sd[0], sd[1], err, TOL_SHIFT_PX))
    print('             覆盖原头面积比例 %.3f（>=%.2f）' % (cov, MIN_COVER))
    if err > TOL_SHIFT_PX:
        fails.append('屏幕位移 %.4f,%.4f 与 HEAD_PLACE_SHIFT 差 %.6fpx —— '
                     '「有意偏移」没落到锚点上（最常见原因：把 shift 直接加到了 offset 上，'
                     '横向会反向）' % (sd[0], sd[1], err))
    if cov < MIN_COVER:
        fails.append('头块只覆盖原头 %.1f%%（<%.0f%%）—— 头可能悬空/飞出去了'
                     % (cov * 100, MIN_COVER * 100))

    # 判据 ②：本轮「回退」的口径 —— 开关必须关（否则引擎每帧覆写 Rotation 被跳过，
    #        头又会冻住，与用户「回退动画」的诉求相反）
    if g['fix_rotate']:
        fails.append('生成器 HEAD_FIX_HEAD_ROTATE 应为 False（用户要求**回退**头部动画）'
                     '—— 开着会把 Rotation 冻成常量，头不再跟 anim_head1 摆动')
    else:
        rng = [P.body_rot_deg(f) for f in P.bframes]
        print('   回退核对：HEAD_FIX_HEAD_ROTATE=False ⇒ 头跟 L%d 摆动，'
              'Idle 净旋转 %+.2f°..%+.2f°（%d 帧）'
              % (P.follow, min(rng), max(rng), len(rng)))
        if max(rng) - min(rng) < 1.0:
            fails.append('本版靠"跟随摆动"成立，但测得 Idle 净旋转只变化 %.2f°'
                         ' —— 可能跟错了图层（应跟 anim_head1 = L%d）'
                         % (max(rng) - min(rng), P.follow))

    # 判据 ③：层级仍是硬需求（用户未要求回退）
    if g['node_z'] <= 0:
        fails.append('生成器应给可见头写正数 HEAD_NODE_Z_INDEX —— 排序键第一位是 '
                     'EffectiveZIndex(= z_index 沿父链累加)，只有正数才保证压住身体')
    if g['fix_rotate'] and abs(g['offset_rotate']) > 1e-9:
        fails.append('useRotate=false 时引擎**不读** offsetRotate ⇒ 非零值是死配置，容易误读')
    if (not g['fix_rotate']) and abs(g['offset_rotate']) > 1e-9:
        # 跟随口径下 offsetRotate 是**生效的**（加在 net 旋转上）⇒ 但不能悄悄改：
        # 它是头的基准倾角，非零 ⇒ 上面按 offset_rot_deg=0 反解的 HEAD_OFFSET 立刻失效。
        # 本页用的正是 0 ⇒ 非零时本页的反解会与常量对不上（会先在这里红）。
        fails.append('跟随口径下 HEAD_OFFSET_ROTATE 应为 0（现为 %g）—— '
                     '它会让本页按 offset_rot_deg=0 反解的 HEAD_OFFSET 失效；'
                     '要改必须先重解 offset' % g['offset_rotate'])

    # ---- 判据 ④（第四轮）：子弹生成点必须落在炮口上 ----------------------------
    #   用户原话：「让子弹生成位置靠左一点，对齐子弹发射口」。
    #   ⚠️ 这一组必须**独立于生成器常量**，否则就是「拿生成器常量比生成器常量」（铁律 20①）：
    #      · 炮口点 ← 从 **barrel 轨美术** 反推（完全伸出帧的最右列中点，映射到 pose 空间）；
    #      · 生成点 ← 从 **生成的场景 .tscn** 现场反读（HeadSlot/FireMarker 四个数）。
    #   机制与三套坐标换算见生成器顶部「炮口 / 子弹生成点」长注释段。
    import _muzzle_probe as MP

    print('   炮口 pose 点（头 %s）：' % os.path.basename(MP.HEAD_TRES_SRC))
    _hk, _atlas = MP.load_head_and_atlas()
    got_muz = MP.derive_muzzle_pose(_hk, _atlas, 'barrel')
    if got_muz is None:
        fails.append('没能从 barrel 轨反推出炮口 —— 头的皮肤/图集不对？')
        MUZZLE_D = g['muzzle_pose']
    else:
        MUZZLE_D = got_muz[0]
        print('     美术反推（barrel 轨 hf=%d 最右列中点）= (%+.4f, %+.4f)'
              % (got_muz[1], MUZZLE_D[0], MUZZLE_D[1]))
        print('     生成器 MUZZLE_POSE                        = (%g, %g)'
              % (g['muzzle_pose'][0], g['muzzle_pose'][1]))
        _dm = math.hypot(MUZZLE_D[0] - g['muzzle_pose'][0], MUZZLE_D[1] - g['muzzle_pose'][1])
        print('     差 = %.6f px（<=%g）' % (_dm, TOL_OFFSET_PX))
        if _dm > TOL_OFFSET_PX:
            fails.append('生成器 MUZZLE_POSE (%g,%g) 与美术反推 (%.4f,%.4f) 差 %.6fpx'
                         % (g['muzzle_pose'][0], g['muzzle_pose'][1],
                            MUZZLE_D[0], MUZZLE_D[1], _dm))

    # 生成点：从**场景文件**读（HeadSlot 的 rot/scale 会作用在 FireMarker 的局部坐标上）
    sm = MP.read_scene_marker()
    fm_space = MP.marker_local_to_space(sm)
    _fv = HP.apply_affine(HP.node_matrix(math.degrees(sm['slot_rot_rad']),
                                         sm['slot_scale'], sm['slot_scale']), sm['marker'])
    print('   场景 FireMarker（%s）：' % os.path.basename(MP.SCENE_TSCN))
    print('     HeadSlot.position=(%.6f, %.6f)  rot=%.8f rad(%.4f°)  scale=%.8f'
          % (sm['slot_pos'][0], sm['slot_pos'][1], sm['slot_rot_rad'],
             math.degrees(sm['slot_rot_rad']), sm['slot_scale']))
    print('     FireMarker.position=(%.6f, %.6f) [HeadSlot 局部]  ⇒ M(θ,s)·marker=(%+.6f, %+.6f)'
          % (sm['marker'][0], sm['marker'][1], _fv[0], _fv[1]))
    print('     ⇒ 生成点 space = (%.4f, %.4f)' % fm_space)
    print('     生成器 FIRE_MARKER_POS = (%g, %g)'
          % (g['fire_marker'][0], g['fire_marker'][1]))
    _dfmr = math.hypot(sm['marker'][0] - g['fire_marker'][0],
                       sm['marker'][1] - g['fire_marker'][1])
    if _dfmr > TOL_OFFSET_PX:
        fails.append('场景 FireMarker.position 与生成器 FIRE_MARKER_POS 差 %.6fpx '
                     '—— 场景没重生成？（跑 build_zombie_super_gatling_paper.py 不带 --self-check）'
                     % _dfmr)

    # 参考帧：`FIRE_MARKER_POS` 是按 **bf=0** 反解的（与 HEAD_OFFSET 同口径）
    target = MP.muzzle_space(P, g['offset'], MUZZLE_D, body_frame=0)
    dfm = math.hypot(fm_space[0] - target[0], fm_space[1] - target[1])
    print('     参考帧 bf=0 真炮口 space = (%.4f, %.4f)  ⇒ 生成点离线 %.6f px（<=%g）'
          % (target[0], target[1], dfm, TOL_OFFSET_PX))
    if dfm > TOL_OFFSET_PX:
        fails.append('静态生成点离线炮口 %.6fpx（应 ≤%g）—— FIRE_MARKER_POS 需要重解：'
                     '`python .cache/_fire_marker_solve.py`（依赖 HEAD_OFFSET / 参考帧 bf=0）'
                     % (dfm, TOL_OFFSET_PX))

    # 炮口随动画跑：静态兜底只能对上参考帧 ⇒ 必须靠插件每帧覆写（这里只做**记录**，不判失败）
    _sw = [MP.muzzle_space(P, g['offset'], MUZZLE_D, body_frame=f) for f in (0, 6, 12, 18, 24)]
    _mx = max(math.hypot(w[0] - fm_space[0], w[1] - fm_space[1]) for w in _sw)
    print('     静态兜底的天花板：Idle 0..24 帧内最大离线 %.2f px'
          '（头跟 anim_head1 摆动 ⇒ 每帧真炮口都在动；'
          '「每帧都对齐」由插件 SyncHeadPairs() 覆写，不在本页判定）' % _mx)
    if _mx < 1.0:
        fails.append('Idle 段炮口几乎不动（%.3fpx）—— 反推或跟随层可能错了'
                     '（本版头是跟 anim_head1 逐帧摆的，炮口必然移动）' % _mx)

    # 负向：生成点写错必须被判定为「离线」，否则说明判据没有区分度
    print('   生成点负向（必须离线 >1px）：')
    for tag, bad in (
            ('退回 HeadSlot 原点 (0,0)', (0.0, 0.0)),
            ('只改 y、x 忘了改', (0.0, g['fire_marker'][1])),
            ('只改 x、y 忘了改', (g['fire_marker'][0], 0.0)),
            ('两个分量符号写反', (-g['fire_marker'][0], -g['fire_marker'][1])),
            ('整体再偏 10px', (g['fire_marker'][0] + 10.0, g['fire_marker'][1]))):
        sp_bad = MP.marker_local_to_space(dict(sm, marker=bad))
        dbad = math.hypot(sp_bad[0] - target[0], sp_bad[1] - target[1])
        print('     %-22s ⇒ 落点 (%+8.3f, %+8.3f)  离线 %8.3f px  %s'
              % (tag, sp_bad[0], sp_bad[1], dbad, '竟然在线 ✗' if dbad <= 1.0 else '判定离线 ✓'))
        if dbad <= 1.0:
            fails.append('负向测试失败：生成点 %s 竟然仍落在炮口上（离线 %.4fpx）' % (tag, dbad))

    # ---- 负向测试：历史值 / 方向坑必须被判不合格 ----
    #     每条都代表一次真实踩过的坑；留在库里当回归哨兵。
    #     ⚠️ 必须用**当前口径**（本版 = 跟随 + shift）去算 —— 否则测的是「另一口径下的对位」，
    #        区分度来自口径而不是 offset，会失去意义。
    base = s['offset']
    for tag, off in (
            ('旧 (-36,-46)（照抄植物 Head 的 offset ⇒ 悬空）', (-36.0, -46.0)),
            ('(-49.07,-5.24)（冻在 −14.32° 的解）', (-49.07, -5.24)),
            ('(-54.19,-10.11)（第二轮：冻在 0° 的解 = 上一版交付）', (-54.19, -10.11)),
            ('本版**纯几何对齐**、没加右上微移（= solve(shift=0,0)）', (-51.4558, -7.2129)),
            ('★ 方向坑：把 shift **直接加到 offset** 上（base + (8,−4)）⇒ 左右反向',
             (base[0] + 8.0, base[1] - 4.0))):
        ok_old, err_old, cov_old, got_old, _r = fit_ok(P, off, shift=g['place_shift'], **kw)
        print('   负向：%s\n          ⇒ 落点中心 (%+.2f,%+.2f)  位移误差 %.4fpx  覆盖 %.3f  %s'
              % (tag, (got_old[0] + got_old[2]) / 2.0, (got_old[1] + got_old[3]) / 2.0,
                 err_old, cov_old, '竟然通过 ✗' if ok_old else '判定失败 ✓'))
        if ok_old:
            fails.append('负向测试失败：%s 竟然也通过了 —— 检查没有区分度' % tag)

    print()
    if fails:
        print('FAIL %d' % len(fails))
        for f in fails:
            print('  ·', f)
        return 1
    print('PASS 换头对位反解与生成器常量一致'
          '（官方样本交叉校验 + 单位负向 + 屏幕位移逐字核对 + 覆盖率 + 5 条历史/方向负向'
          ' + 炮口反推/生成点落点 + 5 条生成点负向）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
