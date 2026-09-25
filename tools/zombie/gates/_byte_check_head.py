# -*- coding: utf-8 -*-
"""对**落盘的**产物做字节级核对（不用 Read 预览 —— 它会把 3e 渲染成 5d）。

校验两处副本：构建工作区 + 已安装镜像（Mods/超级机枪读报僵尸/），
两处必须逐字节相同（否则「我看的是 A、游戏跑的是 B」）。
"""
import io
import os
import re
import sys

WS = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版\Asset\Anime\Character\Zombie\.workbuddy\ModWorkspace"
APP = os.path.join(os.environ["APPDATA"], "Godot", "app_userdata",
                   "植物大战僵尸杂交版", "Mods")
KEY = "ZombieSuperGatlingPaper"
REL = os.path.join("Resources", "Characters", "Zombies", KEY, "Sprite", KEY + ".tscn")

PAIRS = [
    ("工作区", os.path.join(WS, "SuperGatlingPaper", REL)),
    ("已安装镜像", os.path.join(APP, "超级机枪读报僵尸", REL)),
]

WANT = [
    ('[node name="Head" type="Node2D" parent="HeadHolder"]', "可见头挂在 HeadHolder 下"),
    ('\nz_index = 1', "可见头 z_index = 1（层级 = 用户第二轮需求，未回退）"),
    ('\noffset = Vector2(-59.9377, -10.0515)',
     "重解后的 offset（跟随摆动 + 右上微移 8,-4）"),
    ('\noffsetRotate = 0.0', "offsetRotate = 0"),
    ('Animation/Clip = "HeadIdle"', "官方键名 Animation/Clip"),
]
BAD = [
    ('\nposition = Vector2', "可见头不该写 position"),
    # 第三轮「回退头部动画」：这三行必须**一个都没有**
    ('useRotate', "回退后不该出现 useRotate"),
    ('usePos', "回退后不该出现 usePos"),
    ('\nrotation = ', "回退后不该出现 rotation（没有 useRotate=false 时它是死值）"),
]

# ---- 第四轮：Scene 场景里的**子弹生成点**（`FireMarker` = Marker2D）---------------
# 真源 = `FireComponent.cs:2698-2714` 的 `marker2D.GlobalPosition`。
# 静态值是**参考帧 bf=0** 的兜底（`.cache/_fire_marker_solve.py` 反解）；
# 「每帧都对上炮口」由插件 `SyncHeadPairs()` 覆写 `GlobalPosition` 完成。
REL_SCENE = os.path.join("Resources", "Characters", "Zombies", KEY, "Scene", KEY + ".tscn")
PAIRS_SCENE = [
    ("工作区", os.path.join(WS, "SuperGatlingPaper", REL_SCENE)),
    ("已安装镜像", os.path.join(APP, "超级机枪读报僵尸", REL_SCENE)),
]
_FM_HEAD = ('[node name="FireMarker" type="Marker2D" '
            'parent="SpriteGroup/TransformPoint/ZombiePaper/HeadSlot" index="0"]')
SCENE_WANT = [
    (_FM_HEAD, "FireMarker 是 HeadSlot 下的 Marker2D"),
    ('\nposition = Vector2(-35.697232, 94.988609)',
     "FireMarker 局部位置 = 反解值（回代离线 0.000004px）"),
    ('position = Vector2(-14.015516, -40.408867)', "HeadSlot 保持原版 position"),
    ('rotation = -0.27867758', "HeadSlot 保持原版 rotation"),
    ('scale = Vector2(0.79857695, 0.79857695)', "HeadSlot 保持原版 scale"),
]
# ⚠️ 这两条只在 **FireMarker 块内**判（场景别处出现 `Vector2(0, 0)` 是正常的）
SCENE_BAD = [
    ('position = Vector2(0, 0)', "FireMarker 退回 HeadSlot 原点 = 子弹从头顶上方出膛"),
    ('position = Vector2(0.0, 0.0)', "同上（另一种写法）"),
]

# 生成点路径在**另一个文件**里（FireComponentDefinition.tres）—— 别放错场景
REL_FIREDEF = os.path.join("Resources", "Characters", "Zombies", KEY, "Scene",
                           KEY + "FireComponentDefinition.tres")
PAIRS_FIREDEF = [
    ("工作区", os.path.join(WS, "SuperGatlingPaper", REL_FIREDEF)),
    ("已安装镜像", os.path.join(APP, "超级机枪读报僵尸", REL_FIREDEF)),
]
FIREDEF_WANT = [
    ('firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker")]',
     "生成点路径（与场景节点路径 / 插件里的 `HeadSlot/FireMarker` 同名）"),
    ('fireInterval = 1.5', "开火间隔 1.5s（未被误改）"),
    ('speed = -300.0', "豌豆速度 -300（负数 = 向前；误改会让子弹反向）"),
]


def check_simple(tag, path, title, want):
    """「文件存在 + 逐条包含」核对；返回 bytes（失败返回 None）。"""
    print()
    print("=" * 74)
    print(f"【{tag} · {title}】{path}")
    print("=" * 74)
    if not os.path.isfile(path):
        fails.append(f"{tag} 缺 {title}")
        print("  ★ 文件不存在")
        return None
    with open(path, "rb") as f:
        raw = f.read()
    print(f"  字节数 = {len(raw)}")
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        fails.append(f"{tag} {title} 不是合法 UTF-8: {e}")
        return None
    for pat, desc in want:
        hit = pat in txt
        print(f"  [{'OK ' if hit else '★ 缺'}] {desc}")
        if not hit:
            fails.append(f"{tag} {title} 缺 {desc}")
    return raw

texts = {}
fails = []
for tag, path in PAIRS:
    print("=" * 74)
    print(f"【{tag}】{path}")
    print("=" * 74)
    if not os.path.isfile(path):
        fails.append(f"{tag} 缺文件")
        print("  ★ 文件不存在")
        continue
    with open(path, "rb") as f:
        raw = f.read()
    texts[tag] = raw
    print(f"  字节数 = {len(raw)}")
    try:
        txt = raw.decode("utf-8")           # 允许 BOM 则单独处理
    except UnicodeDecodeError as e:
        fails.append(f"{tag} 不是合法 UTF-8: {e}")
        continue
    print(f"  含 BOM = {raw[:3] == b'\xef\xbb\xbf'}   行尾 = "
          f"{'CRLF' if b'\r\n' in raw else 'LF'}")
    # 节点头闭合括号（字节级）
    bad_head = [ln for ln in txt.split("\n")
                if ln.startswith("[node ") and not ln.rstrip("\r").endswith("]")]
    if bad_head:
        fails.append(f"{tag} 节点头未以 ] 收尾：{bad_head}")
    else:
        print("  节点头闭合括号：OK（全部以 ] 收尾）")
    # 头块提取
    m = txt.find('[node name="Head" ')
    blk = txt[m:].split("\n[", 1)[0] if m >= 0 else ""
    for pat, desc in WANT:
        hit = pat in txt
        in_head = pat in blk
        mark = "OK " if hit else "★ 缺"
        print(f"  [{mark}] {desc:<28} 全文={hit}  在头块内={in_head}")
        if not hit:
            fails.append(f"{tag} 缺 {desc}")
        if pat.startswith("\n") and not in_head and not pat.startswith("\noffsetRotate") \
                and not pat.startswith("\noffset ="):
            fails.append(f"{tag} 的 `{desc}` 不在可见头块内")
    for pat, desc in BAD:
        if pat in txt:
            fails.append(f"{tag} 不该有：{desc}")
    # 影子块：必须有 offset/offsetRotate，且**不许**有 usePos/useRotate/rotation/z_index
    ms = txt.find('[node name="HeadShadow" ')
    sblk = txt[ms:].split("\n[", 1)[0] if ms >= 0 else ""
    if not sblk:
        fails.append(f"{tag} 找不到影子块")
    for pat in ("\noffset = Vector2(-59.9377, -10.0515)", "\noffsetRotate = 0.0"):
        if pat not in sblk:
            fails.append(f"{tag} 影子块缺 {pat!r}")
    for pat in ("\nusePos", "\nuseRotate", "\nrotation = ", "\nz_index"):
        if pat in sblk:
            fails.append(f"{tag} 影子块不该有 {pat!r}")

# 两处副本必须逐字节相同
if len(texts) == 2:
    a, b = list(texts.values())
    same = a == b
    print()
    print(f"两处副本逐字节相同：{same}（{len(a)} vs {len(b)} 字节）")
    if not same:
        fails.append("工作区与已安装镜像的 Sprite .tscn 不一致")

# ---- Scene 场景：子弹生成点 ------------------------------------------------
scene_texts = {}
for tag, path in PAIRS_SCENE:
    print()
    print("=" * 74)
    print(f"【{tag} · Scene】{path}")
    print("=" * 74)
    if not os.path.isfile(path):
        fails.append(f"{tag} 缺 Scene 文件")
        print("  ★ 文件不存在")
        continue
    with open(path, "rb") as f:
        raw = f.read()
    scene_texts[tag] = raw
    print(f"  字节数 = {len(raw)}")
    try:
        txt = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        fails.append(f"{tag} Scene 不是合法 UTF-8: {e}")
        continue
    bad_head = [ln for ln in txt.split("\n")
                if ln.startswith("[node ") and not ln.rstrip("\r").endswith("]")]
    if bad_head:
        fails.append(f"{tag} Scene 节点头未以 ] 收尾：{bad_head}")
    else:
        print("  节点头闭合括号：OK（全部以 ] 收尾）")
    for pat, desc in SCENE_WANT:
        hit = pat in txt
        print(f"  [{'OK ' if hit else '★ 缺'}] {desc}")
        if not hit:
            fails.append(f"{tag} Scene 缺 {desc}")
    m = txt.find('[node name="FireMarker" ')
    blk = txt[m:].split("\n[", 1)[0] if m >= 0 else ""
    if not blk:
        fails.append(f"{tag} Scene 找不到 FireMarker 块")
    else:
        print(f"  FireMarker 块 ={blk}")
        for pat, desc in SCENE_BAD:
            if pat in blk:
                fails.append(f"{tag} Scene 的 {desc}")

if len(scene_texts) == 2:
    a, b = list(scene_texts.values())
    same = a == b
    print()
    print(f"两处副本（Scene）逐字节相同：{same}（{len(a)} vs {len(b)} 字节）")
    if not same:
        fails.append("工作区与已安装镜像的 Scene .tscn 不一致")

# ---- FireComponentDefinition.tres：生成点路径 ---------------------------------
fired_texts = {}
for tag, path in PAIRS_FIREDEF:
    raw = check_simple(tag, path, "FireComponentDefinition", FIREDEF_WANT)
    if raw is not None:
        fired_texts[tag] = raw

if len(fired_texts) == 2:
    a, b = list(fired_texts.values())
    same = a == b
    print()
    print(f"两处副本（FireDef）逐字节相同：{same}（{len(a)} vs {len(b)} 字节）")
    if not same:
        fails.append("工作区与已安装镜像的 FireComponentDefinition.tres 不一致")

print()
print("=" * 74)
if fails:
    print(f"BYTE_CHECK: FAIL（{len(fails)}）")
    for f in dict.fromkeys(fails):
        print("   -", f)
    sys.exit(1)
print("BYTE_CHECK: PASS")
