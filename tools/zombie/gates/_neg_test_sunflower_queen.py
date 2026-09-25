# -*- coding: utf-8 -*-
"""负向测试：逐条篡改生成器常量 / 插件源码，确认 self_check() 真的会报警。

铁律 20：
  · 断言必须与实现**不同源** ⇒ 篡改常量后必须打红；
  · 每条用例都断言「**被测的那一条**」出现在 FAIL 列表里（防被别的断言掩盖）；
  · 负向一律**全量替换**（`str.replace(old, new)`，不加 count）；
  · 有些目标行在当前口径下根本不生成 ⇒ 用**打桩注入**（直接改模板字面量）。

用法：python .cache/_neg_test_sunflower_queen.py
"""
from __future__ import annotations

import importlib.util
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
SRC = os.path.join(WS, "build_zombie_sunflower_queen.py")
ENTRY = os.path.join(WS, "runtime_src_zombie_sunflower_queen", "SunFlowerQueenRuntimeEntry.cs")

TMPDIR = WS          # ⚠️ 必须与生成器**同级**：生成器里 WS = dirname(__file__)，
                     #    临时文件放到 .cache/ 会让 WS 错位 ⇒ RUNTIME_SRC_DIR 找不到。
TMP_PREFIX = "_neg_tmp_"


def _out(s):
    sys.stdout.write(s + "\n")


def load_module(src_text, tag):
    """把（可能被篡改的）源码写到临时文件并加载，返回模块对象。"""
    path = os.path.join(TMPDIR, "%s%s.py" % (TMP_PREFIX, tag))
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(src_text)
    spec = importlib.util.spec_from_file_location("negmod_" + tag, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_src(src_text, tag):
    """加载后跑 self_check，返回 FAIL 列表（stdout 静音）。"""
    saved = sys.stdout
    sys.stdout = io.StringIO()
    try:
        mod = load_module(src_text, tag)
        return list(mod.self_check())
    finally:
        sys.stdout = saved


# (tag, old, new, [必须出现在某条 FAIL 里的子串...], 备注)
#
# ⚠️ 铁律 20 ⑤「同名值稀释」：生成器里金标写作 `GOLD_UNUSE_BUFF_FLAGS = 19`，
#    它**文本上包含**实现常量 `UNUSE_BUFF_FLAGS = 19` ⇒ 直接全量替换会把**金标一起改掉**
#    ⇒ 断言两边同时变 = 恒真 = 假绿。修法：篡改锚点加**行首 `\n`**（金标那行前缀是
#    `\nGOLD_`，不会被命中），`new` 同样带 `\n` 以免吞掉换行。
CASES = [
    ("N01_q_hp", "hp_total=3500.0", "hp_total=3000.0",
     ["[数值] ZombieSunFlowerQueen 总血应为 3500"], ""),
    ("N02_d_hp", "hp_total=800.0", "hp_total=500.0",
     ["[数值] ZombieFireSunFlowerBackup 总血应为 800"], ""),
    ("N03_attack", "attack=300.0", "attack=100.0",
     ["[数值] ZombieSunFlowerQueen 啃食伤害应为 300",
      "[数值] ZombieFireSunFlowerBackup 啃食伤害应为 300"], "两处同源 ⇒ 2 条"),
    ("N04_unuse", "\nUNUSE_BUFF_FLAGS = 19", "\nUNUSE_BUFF_FLAGS = 0",
     ["[数值] ZombieSunFlowerQueen unUseBuffFlags 应为 19"], "行首锚点"),
    ("N05_dir", "\nFIRE_DIR_SPREAD = (-22.0, -13.0, -4.5, 4.5, 13.0, 22.0)",
     "\nFIRE_DIR_SPREAD = (-20.0, -13.0, -4.5, 4.5, 13.0, 22.0)",
     ["[齐射] ZombieSunFlowerQueen dir 扇形不符口径"], "行首锚点"),
    ("N06_head_off", "head_offset=(-83.7633, 27.496)", "head_offset=(-57.0, -28.0)",
     ["[文档] docstring 里没有 HEAD_OFFSET = (-57.0, -28.0)"], ""),
    # ⚠️ new 取 `1` 是**故意的**：文档里**舞者**那行是 `HEAD_EXTRA_SCALE = 1.0（…`，
    #    `HEAD_EXTRA_SCALE = 1` 恰好是它的**前缀** ⇒ 不带右边界 `(?![\d.])` 这条断理会
    #    **假绿**（铁律 20 ③）。改 scale 时别忘了把这里的 `new` 也换成一个**前缀**值。
    #    （⚠️ 别用 `1.0` 当 new：那样文档断言会**命中舞者的 1.0** ⇒ 恒绿 ⇒ 负向假失败。）
    #    （第十六轮女王 scale 1.08 → 0.9 后，`1` 的前缀关系改由**舞者那行**提供，语义不变。）
    ("N07_head_scale", "head_scale=0.9", "head_scale=1",
     ["[文档] docstring 里没有 HEAD_EXTRA_SCALE = 1"],
     "兼测右边界 `(?![\\d.])`（`1` 是文档里舞者 `1.0` 的前缀）"),
    ("N08_hide", '"anim_head1", "anim_head2"]', '"anim_head1", "anim_head2x"]',
     ["[换头] ZombieSunFlowerQueen 身体场景的原头层 'anim_head2' 未关掉",
      "[换头] ZombieFireSunFlowerBackup 身体场景的原头层 'anim_head2' 未关掉"],
     "两处同源 ⇒ 各角色 2 条"),
    ("N09_head_on",
     'QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]',
     'QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "图层_1", "图层_67 复制", "图层_69"]',
     ["[换头] ZombieSunFlowerQueen 可见头层 'blink' 应为 true"], "删掉 blink"),
    ("N10_pkt_type", "\nPACKET_TYPE = 6", "\nPACKET_TYPE = 7",
     ["[卡片] ZombieSunFlowerQueen/card type 必须 6"], "行首锚点"),
    ("N11_api_ver", "RUNTIME_API_VERSION = 1", "RUNTIME_API_VERSION = 2",
     ["[manifest] runtimeApiVersion 必须恰好 1"], ""),
    ("N12_zindex",
     'z_index = 1\nscale = Vector2({-sc:g}, {sc:g})\nscript = ExtResource("headscript")\n'
     'flashAnimeData = ExtResource("headdata")\n{mm}offset = Vector2({off[0]}, {off[1]})\n'
     'offsetRotate = 0.0\n{fr}{ts}useTween = false\nskipLastFrame = false\nAnimation/Clip = "{HEAD_CLIP}"',
     'scale = Vector2({-sc:g}, {sc:g})\nscript = ExtResource("headscript")\n'
     'flashAnimeData = ExtResource("headdata")\n{mm}offset = Vector2({off[0]}, {off[1]})\n'
     'offsetRotate = 0.0\n{fr}{ts}useTween = false\nskipLastFrame = false\nAnimation/Clip = "{HEAD_CLIP}"',
     ["[换头] ZombieSunFlowerQueen 可见头必须写 z_index = 1"], "删掉 z_index"),
    ("N13_userotate", 'skipLastFrame = false\nAnimation/Clip = "{HEAD_CLIP}"\n{vis_on}',
     'skipLastFrame = false\nuseRotate = false\nAnimation/Clip = "{HEAD_CLIP}"\n{vis_on}',
     ["[换头] ZombieSunFlowerQueen 的头不得写 useRotate"], "注入姿态开关"),
    ("N14_speed", "speed = {fmt_f(FIRE_SPEED)}", "speed = 600.0",
     ["[组件] ZombieSunFlowerQueen 火球 speed 应为 -600"], ""),
    ("N15_sunmax", "sunOnceMax = {ch['produce_num']}", "sunOnceMax = 50",
     ["[组件] ZombieSunFlowerQueen sunOnceMax 必须 >= num"], "打桩注入"),
    ("N16_track", "\nFIRE_METHOD_FLAGS = 32", "\nFIRE_METHOD_FLAGS = 0",
     ["[组件] ZombieSunFlowerQueen fireMethodFlags 应为 32（TRACK 追踪）"], "行首锚点"),
    ("N17_savekey", 'saveKey = "{ch[\'key\']}"', 'saveKey = "X{ch[\'key\']}"',
     ["[卡片] ZombieSunFlowerQueen/card saveKey 必须 == 注册键"], ""),
    ("N18_dirs", '    "Assets/Fonts", "Localization",\n',
     '    "Assets/Fonts", "Localization", "Scenes",\n',
     ["[目录] STANDARD_DIRS 应为 72 项，实为 73",
      "[目录] STANDARD_DIRS 有重复项：['Scenes']"], ""),
    # ================= 2026-09-25 追加：换头新口径 + 「3×3 光环」 =================
    # ⚠️ 光环类常量都以**行首 `\n`** 作锚点：金标写作 `GOLD_AURA_SCALE = 1.6`，
    #    文本上**包含** `AURA_SCALE = 1.6` ⇒ 不加 `\n` 会连金标一起替换 = 恒真（铁律 20 ⑤）。
    ("N20_aura_node", '\nAURA_NODE_NAME = "Aura"', '\nAURA_NODE_NAME = "AuraX"',
     ["[光环] ZombieSunFlowerQueen Sprite 缺 Aura 节点"], "行首锚点；缺节点只报 1 条"),
    ("N21_aura_holder", '\nAURA_HOLDER_NAME = "AuraHolder"', '\nAURA_HOLDER_NAME = "AuraHolderX"',
     ["[光环] ZombieSunFlowerQueen Sprite 缺 AuraHolder 容器"], "行首锚点"),
    ("N22_aura_scale", "\nAURA_SCALE = 1.6", "\nAURA_SCALE = 1.0",
     ["[光环] ZombieSunFlowerQueen Aura.scale 应为 Vector2(1.6, 1.6)"], "行首锚点"),
    ("N23_aura_offset", "\nAURA_OFFSET = (-39.5, -71.5)", "\nAURA_OFFSET = (-39.5, -70.0)",
     ["[光环] ZombieSunFlowerQueen Aura.offset 应为 Vector2(-39.5, -71.5)"], "行首锚点"),
    ("N24_aura_z", "\nAURA_Z_INDEX = -1", "\nAURA_Z_INDEX = 0",
     ["[光环] ZombieSunFlowerQueen Aura.z_index 应为 -1"], "行首锚点"),
    ("N25_aura_pos", '\nAURA_HOLDER_POS = "Vector2(1.4, 54.6)"',
     '\nAURA_HOLDER_POS = "Vector2(0, 80)"',
     ["[光环] ZombieSunFlowerQueen AuraHolder.position 应为 Vector2(1.4, 54.6)"],
     "行首锚点：退回被 `_ground` 污染掉的旧值"),
    ("N26_aura_on", '\nAURA_ON = ["AnimeClips", AURA_LAYER]',
     '\nAURA_ON = ["AnimeClips", AURA_LAYER, "图层_69"]',
     ["[光环] ZombieSunFlowerQueen 光环层 '图层_69' 应为 false"], "行首锚点：多开一层"),
    ("N27_cloak_back",
     'QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]',
     'QUEEN_HEAD_ON = ["AnimeClips", "1", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]',
     ["[换头] ZombieSunFlowerQueen head_on 不得含 '1'"], "把披风层加回来"),
    ("N28_aura_layer_back",
     'QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]',
     'QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "blink", "图层_1", "图层_3", "图层_67 复制", "图层_69"]',
     ["[换头] ZombieSunFlowerQueen head_on 不得含 '图层_3'"], "把光环层加回头上"),
    ("N29_head_scale", "head_scale=0.9", "head_scale=1.0",
     ["[换头] ZombieSunFlowerQueen 可见头 scale 应为 Vector2(-0.9, 0.9)"],
     "顺带实证「同名值稀释」：文档里 `HEAD_EXTRA_SCALE = 1.0` 是舞者的 ⇒ 文档断言**照样绿**"),
    ("N30_head_off_q", "head_offset=(-83.7633, 27.496)", "head_offset=(-50.0, -20.0)",
     ["[换头] ZombieSunFlowerQueen 可见头 offset 应为 Vector2(-83.7633, 27.496)"], ""),
    ("N31_head_off_d", "head_offset=(-48.6837, -37.1999)", "head_offset=(-56.6583, -23.3158)",
     ["[换头] ZombieFireSunFlowerBackup 可见头 offset 应为 Vector2(-48.6837, -37.1999)"],
     "舞者退回旧值（右上偏移被撤销）"),
    # ============ 2026-09-25 追加：「属性名引号只包末段」⇒ 静默失效（多出一个头） ============
    # ⚠️ 下面两条断言里的 **`sprite:<行号>` 是硬编码的**（钉住「报的就是这一行」）。它就是
    #    `HeadShadow` 的 `vis_off` 那一串 `= false` 的**首行**在产物文件里的行号 ⇒
    #    **任何在它之前新增/删除行数的改动都会把它顶掉**（第十四轮加 `timeScale = 0.0`
    #    顶掉了 HeadShadow 里那 +1 行：35 → 36）。改产物行数后跑一遍负向测试，
    #    若报 `N32/N33 未命中` 就按实际行号同步这两个数字。
    # 复刻历史 bug：`_prop` 退化成「只给最后一段加引号」
    ("N32_quote_tail",
     '    return f\'"{key}"\' if (" " in key or not key.isascii()) else key',
     '    _h, _t = key.rsplit("/", 1)\n'
     '    return _h + "/" + (f\'"{_t}"\' if (" " in _t or not _t.isascii()) else _t)',
     ["[引号] ZombieSunFlowerQueen/sprite:36 A 只给末段加引号"],
     "复刻真凶：`Animation/LayerVisible/\"图层_1\"` ⇒ 解析后名字带引号 ⇒ 该层恒 true"),
    # 复刻「该加引号却裸写」：`_prop` 退化成恒等
    ("N33_quote_none",
     '    return f\'"{key}"\' if (" " in key or not key.isascii()) else key',
     "    return key",
     ["[引号] ZombieSunFlowerQueen/sprite:36 B 含空格/非 ASCII 却裸写"],
     "整条裸写 ⇒ 名字被拆碎 ⇒ 同样静默失效"),
    # ============ 2026-09-25 追加：「光环画在身体后面」只能靠 `insertLayerId` ============
    # 复刻真凶：`insertLayerId = -1`（= 默认值）⇒ 回落**顶层** ⇒ 光环又跑到身体前面。
    ("N34_aura_inslayer_impl",
     "insertLayerId = {AURA_INSERT_LAYER}", "insertLayerId = -1",
     ["[光环] ZombieSunFlowerQueen Aura.insertLayerId 应为 0"],
     "复刻「默认 −1 ⇒ 回落顶层 ⇒ 画在最前」这个真凶"),
    # 同源金标：`GOLD_AURA_INSERT_LAYER = 0` 本身被改成 −1
    # ⚠️ 锚点带 `GOLD_` 前缀即天然互斥（实现那行是 `\nAURA_INSERT_LAYER = 0`），**无需**再加行首 `\n`
    #    —— 但为稳妥仍按铁律 20 ⑤ 显式区分，见 N35 的断言消息仍必须照抄实现模板。
    ("N35_aura_inslayer_gold",
     "GOLD_AURA_INSERT_LAYER = 0", "GOLD_AURA_INSERT_LAYER = -1",
     ["[光环] ZombieSunFlowerQueen Aura.insertLayerId 应为 -1"],
     "金标侧篡改 ⇒ 产物 0 ≠ 金标 −1"),
    # ============ 2026-09-25 第十五轮：「冻结头自播 Idle」被**取消** ⇒ 断言方向翻转 ============
    # 第十四轮曾写 `timeScale = 0.0` 冻结头自身的 `Idle`（修「抬头段衔接」）；
    # 第十五轮用户要求**取消**（头该有自己的眨眼 / 花瓣动作）⇒ 现在是「**不得写** `timeScale`」。
    # 复刻真凶 A：有人把冻结加回**可见头**（打桩注入：正常口径两个头都不渲染该行）。
    # ⚠️ 锚点 `z_index = 1\nscale = …` 只在**可见头**块里出现（影子块前面是 `visible = false`）
    #    ⇒ 唯一命中，不误伤影子。（与 N41 同锚点，但 new 不同、各自独立替换，互不干扰。）
    ("N36_head_ts_visible",
     'z_index = 1\nscale = Vector2({-sc:g}, {sc:g})\n',
     'z_index = 1\ntimeScale = 0.0\nscale = Vector2({-sc:g}, {sc:g})\n',
     ["[换头] ZombieSunFlowerQueen 可见头 Head 不得写 timeScale"],
     "复刻真凶 A：把「冻结头自播 Idle」加回可见头（第十五轮已取消）"),
    # 复刻真凶 B：冻结加回**影子**（影子虽 `visible = false`，但它的 `Idle` 会白跑，
    #   且两边口径应一致）⇒ 断言对**两个节点**都要生效。
    ("N37_head_ts_shadow",
     'visible = false\nscale = Vector2({-sc:g}, {sc:g})\n',
     'visible = false\ntimeScale = 0.0\nscale = Vector2({-sc:g}, {sc:g})\n',
     ["[换头] ZombieSunFlowerQueen 影子 HeadShadow 不得写 timeScale"],
     "复刻真凶 B：冻结加回影子（证明断言覆盖两个节点）"),
    # 复刻真凶 C：改走 `pause` 冻结 —— `ApplyRuntimeParentState`（`:5475-5478`）会把
    #   `pause = parent._pause` **覆写掉** ⇒ 影子（父=身体精灵）与可见头（父=普通 Node2D）
    #   行为不一致 ⇒ 必须报。⚠️ 锚点 `…\n{vis_on}` 只存在于可见头块。
    ("N38_head_pause",
     'skipLastFrame = false\nAnimation/Clip = "{HEAD_CLIP}"\n{vis_on}',
     'skipLastFrame = false\npause = true\nAnimation/Clip = "{HEAD_CLIP}"\n{vis_on}',
     ["[换头] ZombieSunFlowerQueen 可见头 Head 不得写 pause"],
     "复刻真凶 C：用会被父状态覆写的 `pause` 冻结（本轮口径是任何冻结旋钮都不写）"),
    # ============ 2026-09-25 第十四轮：**换「跟随层」**（修「抬头段头/身衔接不自然」） ============
    # 复刻真凶：把影子三属性从金标换走 ⇒ 头又被「随身体仰头转的那一层」带着甩
    #   （女王 L19 转 20.33°、舞者 L15 转 5.04° 的那一帧）。
    # ⚠️ 锚点 `head_follow_layer=28`（**小写、等号无空格**）与金标那行
    #    `GOLD_QUEEN_HEAD_FOLLOW_LAYER = 28`（**大写、等号带空格**）天然互斥（铁律 20 ⑤）
    #    ⇒ 全量替换**不会**连金标一起改掉。产物变 19 ≠ 金标 28 ⇒ 必须打红。
    ("N39_head_follow_q", "head_follow_layer=28", "head_follow_layer=19",
     ["[换头] ZombieSunFlowerQueen 影子 HeadShadow 的 Layer 必须 = 28",
      "[换头] ZombieSunFlowerQueen 影子 HeadShadow 的 followParentSpriteLayerId 必须 = 28"],
     "女王跟随层退回 L19（anim_head2，随仰头旋转的那层）"),
    ("N40_head_follow_d", "head_follow_layer=22", "head_follow_layer=15",
     ["[换头] ZombieFireSunFlowerBackup 影子 HeadShadow 的 Layer 必须 = 22",
      "[换头] ZombieFireSunFlowerBackup 影子 HeadShadow 的 followParentSpriteLayerId 必须 = 22"],
     "舞者跟随层退回 L15"),
    # 复刻真凶：**可见头**自己也写一份 `Layer` ⇒ 与插件每帧从影子抄来的位姿**双来源**
    #    （两套定位叠加 = 头会飘到身外）。正常口径下可见头**不渲染**这三行 ⇒ 用**打桩注入**。
    # ⚠️ 锚点 `z_index = 1\nscale = …` 只在**可见头**块里出现（影子块前面是 `visible = false`）
    #    ⇒ 唯一命中，不会误伤影子。
    ("N41_head_vis_layer",
     'z_index = 1\nscale = Vector2({-sc:g}, {sc:g})\n',
     'z_index = 1\nLayer = {ch[\'head_follow_layer\']}\nscale = Vector2({-sc:g}, {sc:g})\n',
     ["[换头] ZombieSunFlowerQueen 可见头 Head 不得写 Layer"],
     "可见头多写 Layer（打桩注入：正常口径不渲染该行）"),
]


def main():
    base = io.open(SRC, "r", encoding="utf-8").read()
    entry = io.open(ENTRY, "r", encoding="utf-8").read()

    _out("=" * 72)
    _out("负向测试：_neg_test_sunflower_queen.py（%d 条常驻用例 + 1 条真改 .cs）" % len(CASES))
    _out("=" * 72)

    # 基线：未篡改必须 0 条
    fails0 = check_src(base, "base")
    if fails0:
        _out("!! 基线不是 0 条失败（负向测试无意义）：")
        for f in fails0:
            _out("   - " + f)
        return 1
    _out("基线 0 条失败 OK")

    bad = 0
    for tag, old, new, expects, note in CASES:
        if old not in base:
            _out("!! %-14s 用例失效：源码里找不到 old 串（%s）" % (tag, note))
            bad += 1
            continue
        mutated = base.replace(old, new)
        if mutated == base:
            _out("!! %-14s 用例失效：替换后无变化" % tag)
            bad += 1
            continue
        fails = check_src(mutated, tag)
        hit = [e for e in expects if any(e in f for f in fails)]
        missing = [e for e in expects if e not in hit]
        if not fails:
            _out("!! %-14s 假绿：篡改后 0 条失败（期望命中 %d 条）" % (tag, len(expects)))
            bad += 1
        elif missing:
            _out("!! %-14s 未命中：期望 %r 不在 FAIL 列表里；实际 %d 条：" % (tag, missing, len(fails)))
            for f in fails[:6]:
                _out("      - " + f)
            bad += 1
        else:
            _out("OK %-14s ⇒ %d 条 FAIL（命中 %d/%d）%s"
                 % (tag, len(fails), len(hit), len(expects), ("  " + note) if note else ""))

    # ---- N19：真改插件 .cs（跨语言断言必须真的在读文件），写完立刻恢复
    tag = "N19_cs_burndmg"
    old_cs, new_cs = "BurnDamage = 25.0f", "BurnDamage = 30.0f"
    if old_cs not in entry:
        _out("!! %-14s 用例失效：.cs 里找不到 %r" % (tag, old_cs))
        bad += 1
    else:
        try:
            with io.open(ENTRY, "w", encoding="utf-8", newline="") as f:
                f.write(entry.replace(old_cs, new_cs))
            fails = check_src(base, tag)
            want = "[插件] 源码里找不到 `BurnDamage = 25.0f`"
            if any(want in f for f in fails):
                _out("OK %-14s ⇒ %d 条 FAIL（命中：%s）" % (tag, len(fails), want))
            else:
                _out("!! %-14s 假绿：改了 .cs 却没报「跨语言不符」；实际 %d 条："
                     % (tag, len(fails)))
                for f in fails[:6]:
                    _out("      - " + f)
                bad += 1
        finally:
            with io.open(ENTRY, "w", encoding="utf-8", newline="") as f:
                f.write(entry)   # 恢复原文件
            back = io.open(ENTRY, "r", encoding="utf-8").read()
            if back != entry:
                _out("!! .cs 未恢复原样！")
                bad += 1
            else:
                _out("   （.cs 已恢复原样）")

    # ---- 清理临时文件
    try:
        n = 0
        for f in sorted(os.listdir(TMPDIR)):
            if f.startswith(TMP_PREFIX) and f.endswith(".py"):
                os.remove(os.path.join(TMPDIR, f))
                n += 1
        _out("   （临时文件已清理 %d 个）" % n)
    except Exception as e:
        _out("   （临时文件清理失败：%s）" % e)

    _out("=" * 72)
    total = len(CASES) + 1
    if bad:
        _out("负向测试 FAIL：%d / %d 条用例不达标" % (bad, total))
        return 1
    _out("负向测试全部通过：%d / %d 条用例都能打红，且命中「被测的那一条」" % (total, total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
