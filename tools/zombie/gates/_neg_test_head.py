# -*- coding: utf-8 -*-
"""_neg_test_head.py —— 负向测试 + 字节级核对（2026-09-23 第三轮更新）

为什么要有它：
  自检（`self_check()`）里的断言有两种失效方式：
    ① 恒真（拿常量比由同一常量渲染出的文本）—— 已经用「金标」修过一轮；
    ② **门控共用**（实现与断言包在同一个 if 开关里）—— 常量一改，两边一起跳过。
  唯一能证明断言"真的会响"的办法就是**逐条篡改常量**看它报不报。这就是本脚本。

本轮（第三轮）变更：
  · 口径从「冻结固定角」翻回「跟随 anim_head1 摆动」⇒ 用例 a 反向
    （现在要测的是「**打开**开关后场景出现三行且自检不误报」）。
  · 新增 `HEAD_PLACE_SHIFT`（屏幕空间右上微移）相关的用例 h/i/j。
  · 新增**注入式**用例 k/l：直接往渲染出来的场景文本里塞 `rotation = ` / `useRotate = false`，
    验证「开关为 False 时这三行不许出现」的断言不是摆设。
"""
import math
import os
import sys

WS = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, WS)
os.chdir(WS)

import build_zombie_super_gatling_paper as B  # noqa: E402

HEAD_OFFSET = B.HEAD_OFFSET
HEAD_PLACE_SHIFT = B.HEAD_PLACE_SHIFT

print("=" * 78)
print("【1】字节级核对 sprite_scene_tscn()")
print("=" * 78)
raw = B.sprite_scene_tscn()
data = raw.encode("utf-8")
lines = raw.split("\n")
for i, ln in enumerate(lines, 1):
    if ("Node2D" in ln) or ("useRotate" in ln) or ("usePos" in ln) \
            or ("rotation = " in ln) or ("z_index" in ln) or ("offset = " in ln) \
            or ("offsetRotate" in ln) or ("unique_name_in_owner" in ln) \
            or ("HeadHolder" in ln) or ("HeadShadow" in ln):
        print(f"{i:4d}| {ln}")
print()
print(f"raw 含 CR? {chr(13) in raw}  行数={len(lines)}  字节={len(data)}")

print()
print("=" * 78)
print("【2】节点头闭合括号扫描（字节级，不看 Read 预览）")
print("=" * 78)
bad = []
for i, ln in enumerate(lines, 1):
    s = ln.strip()
    if s.startswith("[node ") and not s.endswith("]"):
        bad.append((i, ln))
if bad:
    for i, ln in bad:
        print(f"  ★ 未以 ] 收尾  L{i}: {ln!r}")
else:
    print("  OK：所有 [node ...] 行都以 ] 收尾")

print()
print("=" * 78)
print("【3】当前产物的正向不变量（缺了就说明渲染模板坏了）")
print("=" * 78)
want_absent = ["useRotate", "usePos", "rotation = ", "position = Vector2"]
want_present = [f"offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})",
                "offsetRotate = 0.0", "z_index = 1"]
inv = True
for k in want_absent:
    ok = (k not in raw)
    inv &= ok
    print(f"  {'✔' if ok else '✘'} 不该出现 `{k}`")
for k in want_present:
    n = raw.count(k)
    ok = n >= 1
    inv &= ok
    print(f"  {'✔' if ok else '✘'} 应出现 `{k}`（{n} 次）")
print(f"  ⇒ {'OK' if inv else '★ 正向不变量不成立'}")
if len(want_present[0]) and raw.count(f"offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})") != 2:
    print("  ★ 两个头必须写同一个 offset（应为 2 次）")
    inv = False

print()
print("=" * 78)
print("【4】负向测试：逐项篡改，断言必须响")
print("=" * 78)

_SAVED_KEYS = ("HEAD_OFFSET", "HEAD_PLACE_SHIFT", "HEAD_FIX_HEAD_ROTATE",
               "HEAD_FIXED_ROT_RAD", "HEAD_FIXED_ROT_DEG", "HEAD_OFFSET_ROTATE",
               "HEAD_NODE_Z_INDEX", "sprite_scene_tscn",
               # 第四轮（炮口 / 生成点）
               "MUZZLE_POSE", "HEAD_MUZZLE_LOCAL", "FIRE_MARKER_POS", "HEAD_SLOT_POS",
               "zombie_scene_tscn")


def run_case(label, mutate, expect_kw):
    """mutate() 就地改模块常量 / 打桩；跑完还原。"""
    saved = {k: getattr(B, k) for k in _SAVED_KEYS}
    try:
        mutate()
        try:
            fails = B.self_check()
        except Exception as e:  # noqa: BLE001
            print(f"  [{label}] ✔ 抛异常（视为拦截成功）: {type(e).__name__}: {str(e)[:90]}")
            return True
    finally:
        for k, v in saved.items():
            setattr(B, k, v)
    hit = [f for f in fails if expect_kw in f]
    if hit:
        print(f"  [{label}] ✔ 断言响了 {len(hit)} 条，例：{hit[0][:110]}")
        return True
    print(f"  [{label}] ✘ 期望命中 {expect_kw!r}，但未命中；fails={fails}")
    return False


results = []

# a) **打开**冻结开关 ⇒ 场景出现三行，且自检不该误报
#    （这是合法开关，不是 bug ⇒ 判据是「一致」，不是「报错」）
#    ⚠️ 自检**不**校验「打开时 offset 是否对应冻结角」—— 那需要重解几何，
#       归 `.cache/check_head_fit.py`（它按开关切口径并重算）。
_saved_a = B.HEAD_FIX_HEAD_ROTATE
try:
    B.HEAD_FIX_HEAD_ROTATE = True
    _sp_on = B.sprite_scene_tscn()
    _f_on = B.self_check()
finally:
    B.HEAD_FIX_HEAD_ROTATE = _saved_a
_ok_a = (("useRotate = false" in _sp_on) and ("usePos = true" in _sp_on)
         and ("rotation = 0.0" in _sp_on)
         and not any(("useRotate" in f) or ("usePos" in f) or ("rotation" in f)
                     for f in _f_on))
print(f"  [打开 HEAD_FIX_HEAD_ROTATE] "
      f"{'✔ 一致（三行都写了，自检不误报）' if _ok_a else f'✘ 场景/自检不一致；fails={_f_on}'}")
results.append(_ok_a)

# b) 度数形式与弧度不一致 ⇒ 一致性断言（只在开关打开时判）
def m_b():
    B.HEAD_FIX_HEAD_ROTATE = True
    B.HEAD_FIXED_ROT_DEG = -30.0
results.append(run_case("DEG 与 RAD 不一致（开关打开）", m_b, "对不上"))

# c) z_index 归零 ⇒ 「常量必须是正整数」拦下（无门控）
def m_c():
    B.HEAD_NODE_Z_INDEX = 0
results.append(run_case("HEAD_NODE_Z_INDEX = 0", m_c, "必须是正整数"))

# c2) z_index 改成 5 ⇒ 与金标不符
def m_c2():
    B.HEAD_NODE_Z_INDEX = 5
results.append(run_case("HEAD_NODE_Z_INDEX = 5（与金标不符）", m_c2, "金标"))

# d) offsetRotate 写非零 ⇒ 本版（两种口径都）必须拦：
#    冻结时它是死值；跟随时它会改头基准倾角 ⇒ `HEAD_OFFSET` 立刻失效。
#    ⚠️ 关键词用 `HEAD_OFFSET_ROTATE`（两种口径的文案都含它）—— 别用 `offsetRotate`：
#       现网文案里那个词只出现在「引擎不读 offsetRotate」这句解释里，换个分支就命中不到
#       （第一次跑就是这么假红的）。
def m_d():
    B.HEAD_OFFSET_ROTATE = -0.25
results.append(run_case("HEAD_OFFSET_ROTATE 非零", m_d, "HEAD_OFFSET_ROTATE"))

# e) offset 换成旧错值 ⇒ 金标必须响
def m_e():
    B.HEAD_OFFSET = (-36.0, -46.0)
results.append(run_case("HEAD_OFFSET 改成旧值 (-36,-46)", m_e, "HEAD_OFFSET"))

# e2) offset 换成「纯几何对齐」值（= 没加右上微移）⇒ 金标必须响
def m_e2():
    B.HEAD_OFFSET = (-51.4558, -7.2129)
results.append(run_case("HEAD_OFFSET 换成本版纯几何值 (-51.4558,-7.2129)", m_e2, "HEAD_OFFSET"))

# f) 旋转角回退到上一版错值 −0.25 rad（锚错参照物）⇒ 金标必须响
def m_f():
    B.HEAD_FIXED_ROT_RAD = -0.25
    B.HEAD_FIXED_ROT_DEG = -14.32394487827058
results.append(run_case("旋转角回退到 −0.25 rad（锚错参照物）", m_f, "HEAD_FIXED_ROT_RAD"))

# g) 旋转角改成 +1° ⇒ 同样必须响
def m_g():
    B.HEAD_FIXED_ROT_RAD = math.radians(1.0)
    B.HEAD_FIXED_ROT_DEG = 1.0
results.append(run_case("旋转角改成 +1°", m_g, "HEAD_FIXED_ROT_RAD"))

# h) 平移量被偷偷改成 0（= 悄悄撤掉「右上微移」）⇒ 金标必须响
def m_h():
    B.HEAD_PLACE_SHIFT = (0.0, 0.0)
results.append(run_case("HEAD_PLACE_SHIFT 偷偷改成 (0,0)", m_h, "HEAD_PLACE_SHIFT"))

# i) 平移量方向写反（左下）⇒ 金标必须响
def m_i():
    B.HEAD_PLACE_SHIFT = (-8.0, 4.0)
results.append(run_case("HEAD_PLACE_SHIFT 方向反了 (-8,+4)", m_i, "HEAD_PLACE_SHIFT"))

# j) 平移量形状写坏 ⇒ 形状不变量必须响
def m_j():
    B.HEAD_PLACE_SHIFT = (8.0,)
results.append(run_case("HEAD_PLACE_SHIFT 只有一个分量", m_j, "HEAD_PLACE_SHIFT"))

# k) **注入**：开关为 False 时，场景里出现 `rotation = `（= 半回退的死值）⇒ 必须响
def m_k():
    real = B.sprite_scene_tscn()
    head_txt, sep, tail = real.rpartition("offsetRotate = 0.0")
    injected = head_txt + "offsetRotate = 0.0" + "\nrotation = 0.0" + tail
    B.sprite_scene_tscn = lambda: injected
results.append(run_case("注入：可见头偷偷写 rotation = 0.0", m_k, "rotation"))

# l) **注入**：影子块里偷偷写 `useRotate = false` ⇒ 必须响
def m_l():
    real = B.sprite_scene_tscn()
    sh, sep, rest = real.partition("offsetRotate = 0.0")
    injected = sh + "offsetRotate = 0.0" + "\nuseRotate = false" + rest
    B.sprite_scene_tscn = lambda: injected
results.append(run_case("注入：影子偷偷写 useRotate = false", m_l, "useRotate"))

# ── 第四轮：炮口 / 子弹生成点（用户「让子弹生成位置靠左一点，对齐子弹发射口」）──
# m) 生成点被退回 HeadSlot 原点 ⇒ 「不是 (0,0)」那条无开关不变量必须响
def m_m():
    B.FIRE_MARKER_POS = (0.0, 0.0)
results.append(run_case("FIRE_MARKER_POS 退回 (0,0)", m_m, "FireMarker"))

# n) 只改一个分量（典型「手抖只改了一半」）⇒ 金标必须响
def m_n():
    B.FIRE_MARKER_POS = (-35.697232, 0.0)
results.append(run_case("FIRE_MARKER_POS 只改 y", m_n, "FIRE_MARKER_POS"))

# o) 炮口点被挪走（炮口标定的独立二次确认值）⇒ 金标必须响
def m_o():
    B.MUZZLE_POSE = (88.552, 40.2)
results.append(run_case("MUZZLE_POSE 被挪走", m_o, "MUZZLE_POSE"))

# p) 插件用的 head-local 炮口点被悄悄改精度 / 改错符号 ⇒ 一致性断言必须响
#    （它是**独立派生**量：必须恒等于 MUZZLE_POSE + HEAD_OFFSET）
def m_p():
    B.HEAD_MUZZLE_LOCAL = (28.61, 20.15)
results.append(run_case("HEAD_MUZZLE_LOCAL 与派生式不符", m_p, "HEAD_MUZZLE_LOCAL"))

# q) **注入**：场景里 FireMarker 的 position 被写回 HeadSlot 原点
#    ⇒ 既命中「应为解出的值」，也命中「不许是 (0,0)」
def m_q():
    real = B.zombie_scene_tscn()
    i = real.find('[node name="FireMarker"')
    assert i >= 0, "场景里没有 FireMarker 节点，注入用例失效"
    j = real.find("position = Vector2", i)
    k = real.find("\n", j)
    injected = real[:j] + "position = Vector2(0, 0)" + real[k:]
    B.zombie_scene_tscn = lambda: injected
results.append(run_case("注入：场景 FireMarker 偷写回 (0, 0)", m_q, "FireMarker"))

print()
print("=" * 78)
print(f"负向测试 / 不变量：{sum(results)}/{len(results)} 条如期成立")
print("=" * 78)
sys.exit(0 if all(results) and inv else 1)
