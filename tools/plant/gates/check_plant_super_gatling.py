"""校验《超级机枪射手》植物 Mod —— 按 ModLoader 的真实规则逐条核对（离线）。

核对项分五组：
  A. 角色包路径硬约束（TryInferCharacterScene / IsCharacterPackageDependency / PrepareSafeCharacterPackage）
  B. 资源类别与 manifest 声明一致性（InferRuntimeEntry + provides 键匹配）
  C. 玩法数值（2026-09-21 改版：1 条 dir=0 直线配置 / 1.5s 一轮 7 颗由插件逐发 /
     10% → 5s 300 颗 ±15°；开火动画仍由 fireAnimeClips 驱动）
     另含 C29x（2026-09-25）：图鉴文案必须**内联**在卡片里、且数值块逐字等于指定文本
     （「威力」= 20×7 /1.5秒）
  D. 产物形态（pmod 包结构、工程目录、enabled_mods）
  K. 插件源码证据链（含 K12+：OnFireReady 触发源、vanilla 发射链屏蔽、动画静止修复；
     K15+：射击判定与僵尸版共用 runtime_shared/GatlingVolleyCore.cs，两版数值不许漂移；
     K20+（2026-09-25）：图鉴去重 —— 摘掉 ModPlants 独立分类里的本卡，只留金卡分类那一张）

用法：python .cache/check_plant_super_gatling.py
"""

import hashlib
import io
import json
import os
import re
import sys
import zipfile

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(WS, "SuperGatlingPea")
DIST = os.path.join(WS, "dist")
MODS = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
BUILDER = os.path.join(WS, "build_plant_super_gatling.py")
MAP_BUILDER = os.path.join(WS, "build_map_vampire_pool.py")

MOD_NAME = "超级机枪射手"
MOD_ID = "supergatlingpea"
CHAR_KEY = "SuperGatlingPea"
# 自制外观三件套（自研 .dat 整帧单层 + 头独立分层）——只有走这条路的 Mod 才有
ANIM_DAT_REL = "Resources/Animations/SuperGatlingPea.dat"
ANIM_TRES_REL = "Resources/Animations/SuperGatlingPea.tres"
ANIM_PNG_REL = "Resources/Animations/SuperGatlingPeaAtlas.png"
PLANT_REL = f"Resources/Characters/Plants/{CHAR_KEY}"
SCENE_FILE = f"{CHAR_KEY}.tscn"
SPRITE_FILE = f"{CHAR_KEY}.tscn"
CARD_REL = f"Resources/Cards/{CHAR_KEY}.tres"

# ★ 2026-09-25 图鉴文案（**内联**，不走翻译键）—— 独立复述一遍期望值，当「第二双眼睛」：
#   Mod 的 Localization/translations.csv 在游戏运行时**不会被加载**
#   （ModLoader 无 TranslationServer.AddTranslation；project.godot 只挂内置 .translation），
#   所以字段里写 key，进游戏就原样显示 key。生成器改了文案而这里没同步 ⇒ 立刻红。
#   数值口径按用户 2026-09-25 指定：「威力」= 20×7 /1.5秒（截图上原为 20×7 /2s）。
PLANT_CN_NAME = "超级机枪射手"
PLANT_CN_DESC = "大哥登场！"
PLANT_CN_HANDBOOK_DESC = (
    "韧性：[color=cc241d]1000[/color]\n"
    "威力：[color=cc241d]20×7 /1.5秒[/color]\n"
    "范围：[color=cc241d]前方一行[/color]\n"
    "特点：[color=cc241d]每次攻击有10%概率释放大招[/color]\n"
    "大招：[color=cc241d]小范围散射约300枚子弹[/color]"
)
PLANT_CN_STORY = (
    "超级机枪射手完美诠释了“火力优势学说”，在那个属于他的时空，"
    "他的每次发怒都是无数僵尸的梦魇。然而，他也有属于自己脆弱的一面，"
    "比如他背地里其实很害怕史莱姆。"
)

# 托管运行时（2026-09-19 起本包带插件；四条硬约束见 build_plant_super_gatling.py docstring）
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"
RUNTIME_ENTRY_TYPE = "SuperGatlingPeaRuntimeEntry"
# ModLoader.IsExecutablePackageFile 认的扩展名（除声明的程序集外一个都不许出现在包里）
EXEC_EXTS = (".dll", ".exe", ".bat", ".cmd", ".ps1", ".cs", ".gd")

KNOWN_CHAR_CATEGORIES = {"Plants", "Zombies", "Props", "Vases", "Mowers", "Items", "Graves", "Craters"}
MANIFEST_KEYS = [
    "schemaVersion", "id", "name", "version", "author", "description",
    "dependencies", "conflicts", "provides", "overrides", "scripts",
    "runtimeAssembly", "runtimeEntryType", "runtimeApiVersion", "runtimeAssemblyPolicy",
    "blueprints", "translations", "resources",
]
EXPECTED_HAS_ZIP_ENTRY0 = "mod.json"

ok = warn = fail = 0
msgs = []


_CHK_LINES = []          # [(调用行号, 断言名)]，供文末按分节标记归组统计


def chk(cond, name, detail=""):
    global ok, fail
    _CHK_LINES.append((sys._getframe(1).f_lineno, name))
    if cond:
        ok += 1
    else:
        fail += 1
        msgs.append(f"FAIL  {name}  {detail}")


def note(name, detail=""):
    global warn
    warn += 1
    msgs.append(f"WARN  {name}  {detail}")


def R(rel):
    return os.path.join(BUILD, rel.replace("/", os.sep))


def read(rel, mode="r"):
    p = R(rel)
    if mode == "rb":
        with open(p, "rb") as f:
            return f.read()
    with io.open(p, "r", encoding="utf-8-sig") as f:
        return f.read()


def is_char_pkg_dep(rel):
    """ModLoader.IsCharacterPackageDependency 的 Python 复刻：
    路径落在 `Resources/Characters/<已知类别>/...`（>=5 段）即算角色包依赖。
    这类文件不参与 InferRuntimeEntry，天然不会触发 unsupported package file。
    """
    parts = rel.replace("\\", "/").strip("/").split("/")
    return (len(parts) >= 5 and parts[0] == "Resources" and parts[1] == "Characters"
            and parts[2] in KNOWN_CHAR_CATEGORIES)


def infer_runtime_entry(rel):
    """ModLoader.InferRuntimeEntry 的 Python 复刻（只覆盖本 Mod 用到的类别）。"""
    text = rel.replace("\\", "/").strip("/")
    ext = os.path.splitext(text)[1].lower()
    parts = text.split("/")
    # Character:       Resources/Characters/<Cat>/<Key>/Scene/<Key>.tscn  （恰好 6 段）
    # CharacterSprite: Resources/Characters/<Cat>/<Key>/Sprite/<Key>.tscn（恰好 6 段）
    if is_char_pkg_dep(text) and len(parts) == 6 and parts[4] in ("Scene", "Sprite") \
            and ext == ".tscn" and os.path.splitext(parts[5])[0] == parts[3]:
        return ("Character" if parts[4] == "Scene" else "CharacterSprite"), parts[3]
    if is_char_pkg_dep(text):
        return None, None  # 角色包依赖（不推导 key）
    if ext in (".tres", ".res"):
        table = [
            ("Battle/Features/", "Feature"), ("Battle/Processes/", "Process"),
            ("Resources/LevelCatalogs/", "Level"), ("Resources/Maps/", "Map"),
            ("Resources/Cards/", "Packet"), ("Resources/PacketBank/", "PacketBank"),
            ("Resources/Projectiles/", "Projectile"),
            ("Resources/ProjectileChanges/", "ProjectileChange"),
            ("Resources/Collectables/", "Collectable"), ("Resources/Mowers/", "Mower"),
            ("Resources/Shovels/", "Shovel"), ("Resources/Survivals/", "Survival"),
            ("Resources/Tutorials/", "Tutorial"), ("Resources/NpcTalks/", "NpcTalk"),
            ("Resources/Shops/", "Shop"),
            ("Resources/AnimationAtlasProfiles/", "AnimationAtlas"),
            ("Resources/BGMConfigs/", "BGM"),
        ]
        for pre, cat in table:
            if text.startswith(pre):
                return cat, os.path.splitext(os.path.basename(text))[0]
    return None, None


def ext_resources(body):
    """→ [(type, path), ...]"""
    out = []
    for m in re.finditer(r"\[ext_resource([^\]]*)\]", body):
        attrs = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        if "path" in attrs:
            out.append((attrs.get("type", ""), attrs["path"]))
    return out


def prop(body, key, default=None):
    m = re.search(r"^" + re.escape(key) + r"\s*=\s*(.*)$", body, re.M)
    return m.group(1).strip() if m else default


def prop_block(body, key, default=None):
    """取**可能跨行**的字符串属性（`.tres` 引号内允许真实换行）。

    与 `prop()` 的区别：`prop` 只吃到行尾，多行值只能拿到第一行；
    这里从 `key = "` 一路吃到「引号 + 行尾」为止（值里不含 `"`，非贪婪即可）。
    """
    m = re.search(r"^" + re.escape(key) + r' = "(.*?)"\n', body, re.M | re.S)
    return m.group(1) if m else default


# ============================================================ 前置
print("=" * 72)
print("《超级机枪射手》植物 Mod 校验")
print("=" * 72)

chk(os.path.isdir(BUILD), "工作区构建目录存在", BUILD)

mod_json = json.loads(read("mod.json"))

# ============================================================ A. 角色包路径
print("\n--- A. 角色包路径硬约束 ---")
scene_rel = f"{PLANT_REL}/Scene/{CHAR_KEY}.tscn"
parts = scene_rel.split("/")
chk(len(parts) == 6, "A1 场景路径恰好 6 段", f"实际 {len(parts)}: {scene_rel}")
chk(parts[0] == "Resources" and parts[1] == "Characters", "A2 前缀 Resources/Characters")
chk(parts[2] in KNOWN_CHAR_CATEGORIES, "A3 类别属于已知集合", parts[2])
chk(parts[3] == CHAR_KEY, "A4 目录名 == 角色 key", parts[3])
chk(parts[4] == "Scene", "A5 第 5 段为 Scene", parts[4])
chk(parts[5] == CHAR_KEY + ".tscn", "A6 文件名 == 角色 key + .tscn", parts[5])
chk(os.path.isfile(R(scene_rel)), "A7 场景文件存在")

cat, key = infer_runtime_entry(scene_rel)
chk(cat == "Character" and key == CHAR_KEY, "A8 可被推导为 Character/" + CHAR_KEY, f"{cat}/{key}")

# 包内所有文件都必须是「角色包依赖」或可推导
pkg_dir = R(PLANT_REL)
pkg_files = []
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        pkg_files.append(os.path.relpath(os.path.join(root, f), BUILD).replace("\\", "/"))
        pkg_files[-1] = pkg_files[-1]
for rel in pkg_files:
    if rel.endswith((".uid", ".import", ".cs")):
        continue
    c, k = infer_runtime_entry(rel)
    chk(c is not None or is_char_pkg_dep(rel), f"A9 包内文件可用: {rel}", f"cat={c} key={k}")

# 引用规则（ModLoader.SanitizeCharacterTextResource + TryGetGodotResourcePath）：
#   · 指向游戏自带资源（res://Prefab|Asset|Script|Resource|Registry|Extends）→ 必须 res://
#   · 指向包内自己的文件 → 必须**相对路径**，且在 ModsCache 树内解析得到
#   · 包内 .tres 的 Script 引用非 res:// → 整包被拒；.tscn 则会被剥离
#   · 绝不能出现 res://Resources/…（游戏 pck 根没有 Resources/ 目录）
print("\n--- A10 引用路径：脚本 res://、自引用相对 ---")
body_by_rel = {
    f"{PLANT_REL}/Scene/{SCENE_FILE}": read(f"{PLANT_REL}/Scene/{SCENE_FILE}"),
    f"{PLANT_REL}/Scene/{CHAR_KEY}ComponentSet.tres": read(f"{PLANT_REL}/Scene/{CHAR_KEY}ComponentSet.tres"),
    f"{PLANT_REL}/Config/TowerDefensePlant{CHAR_KEY}.tres": read(f"{PLANT_REL}/Config/TowerDefensePlant{CHAR_KEY}.tres"),
    f"{PLANT_REL}/Packet/{CHAR_KEY}.tres": read(f"{PLANT_REL}/Packet/{CHAR_KEY}.tres"),
    f"{PLANT_REL}/Sprite/{SPRITE_FILE}": read(f"{PLANT_REL}/Sprite/{SPRITE_FILE}"),
    CARD_REL: read(CARD_REL),
}
pkg_all = set()
for root, dirs, files in os.walk(BUILD):
    for f in files:
        pkg_all.add(os.path.relpath(os.path.join(root, f), BUILD).replace("\\", "/"))

bad_res_self, bad_script, bad_abs, unresolved = [], [], [], []
for rel, body in body_by_rel.items():
    chk('type="CSharpScript"' not in body and 'type="GDScript"' not in body,
        f"A10a 无内嵌脚本: {rel}")
    for t, p in ext_resources(body):
        if p.startswith("res://"):
            if p.startswith("res://Resources/"):
                bad_res_self.append((rel, p))
        elif p.startswith("user://") or p.startswith("/") or re.match(r"^[A-Za-z]:", p):
            bad_abs.append((rel, p))
        else:
            tgt = os.path.normpath(os.path.join(os.path.dirname(rel), p)).replace("\\", "/")
            if tgt not in pkg_all:
                unresolved.append((rel, p, tgt))
        if t == "Script" and not p.startswith("res://"):
            bad_script.append((rel, p))

chk(not bad_script, "A10b 所有 Script 引用均为 res://",
    "; ".join(f"{r}:{p}" for r, p in bad_script))
chk(not bad_res_self, "A10c 无 res://Resources/… 自引用（否则必加载失败）",
    "; ".join(f"{r}:{p}" for r, p in bad_res_self))
chk(not bad_abs, "A10d 无绝对路径引用", "; ".join(f"{r}:{p}" for r, p in bad_abs))
chk(not unresolved, "A10e 所有相对引用都能在包内解析",
    "; ".join(f"{r}:{p} -> {t}" for r, p, t in unresolved))

# 场景不得引 res:// 之外的 .scn/.res
print("\n--- A11 无禁止的二进制依赖 ---")
banned = []
for root, dirs, files in os.walk(pkg_dir):
    for f in files:
        if f.endswith((".scn", ".res")):
            banned.append(os.path.relpath(os.path.join(root, f), BUILD))
chk(not banned, "A11 包内无 .scn/.res", "; ".join(banned))

# 场景根不得带 CompanionOnly（本包走标准 IXWModRuntimeEntry 入口，不是伴生脚本绑定那条线）
scene_body = read(scene_rel)
chk("mod_character_script_binding" not in scene_body,
    "A12 场景根无 CompanionOnly 元数据（无需伴生脚本绑定）")
# A13：托管运行时四字段（ModLoader.ValidateDeclaredPackageExecutables 329-333 行
#      + XWModManifest 加载校验 1606-1614 行 —— 任一写错 = 整包被拒，不是「不生效」）
chk(mod_json.get("runtimeAssembly") == RUNTIME_ASSEMBLY,
    "A13a runtimeAssembly == 字面量 " + RUNTIME_ASSEMBLY,
    repr(mod_json.get("runtimeAssembly")))
chk(mod_json.get("runtimeEntryType") == RUNTIME_ENTRY_TYPE,
    "A13b runtimeEntryType == " + RUNTIME_ENTRY_TYPE, repr(mod_json.get("runtimeEntryType")))
chk(mod_json.get("runtimeApiVersion") == 1,
    "A13c runtimeApiVersion == 1（必须恰好 1）", repr(mod_json.get("runtimeApiVersion")))
chk(mod_json.get("runtimeAssemblyPolicy") == "optional",
    "A13d runtimeAssemblyPolicy == optional（加载失败不连坐整包）",
    repr(mod_json.get("runtimeAssemblyPolicy")))
chk(RUNTIME_ASSEMBLY in mod_json["resources"],
    "A13e Runtime/ModAssembly.dll 已列入 manifest.resources")

# ============================================================ B. 资源类别 + manifest
print("\n--- B. 资源类别与 manifest 声明 ---")
chk(list(mod_json.keys()) == MANIFEST_KEYS, "B1 manifest 18 键序正确",
    f"实际 {list(mod_json.keys())}")
chk(mod_json["id"] == MOD_ID, "B2 id", mod_json["id"])
chk(mod_json["schemaVersion"] == 2, "B3 schemaVersion == 2")

declared_char = set(mod_json["provides"].get("Character", []))
declared_packet = set(mod_json["provides"].get("Packet", []))
declared_sprite = set(mod_json["provides"].get("CharacterSprite", []))
chk(CHAR_KEY in declared_char, "B4 provides.Character 含角色 key")
chk(CHAR_KEY in declared_packet, "B5 provides.Packet 含 Resources/Cards 文件名（== 注册键 == saveKey）")
chk(CHAR_KEY in declared_sprite, "B5b provides.CharacterSprite 含精灵 key（否则 XWModContentValidation 抛异常）")
chk(not (set(mod_json["provides"]) & set(mod_json["overrides"])), "B6 provides/overrides 无同类别冲突")

# ★ provides 里的每一项都必须真的能注册（ModLoader.ValidateManifestRegistrations）
reg_pairs = set()
for rel in pkg_files + [CARD_REL]:
    c, k = infer_runtime_entry(rel)
    if c:
        reg_pairs.add((c, k))
for cat, keys in mod_json["provides"].items():
    for k in keys:
        chk((cat, k) in reg_pairs, f"B6b provides {cat}/{k} 会被真正注册", f"reg={sorted(reg_pairs)}")

for res in mod_json["resources"]:
    exists = os.path.isfile(R(res))
    c, k = infer_runtime_entry(res)
    chk(exists, f"B7 声明资源存在: {res}")
    # ⚠️ 三类无需推导类别：
    #    · 角色包依赖（Resources/Characters/<Cat>/...）→ IsCharacterPackageDependency 放行
    #    · 角色的动画三件套（.dat/.tres/图集 png）→ 只有自研外观 Mod 才有，同样按包依赖放行
    #      （.dat/.png 无 InferRuntimeEntry 规则，.tres 在 Resources/Animations/ 下也无规则）
    #    · 声明的运行程序集（Runtime/ModAssembly.dll）→ IsDeclaredRuntimeAssembly 放行（ModLoader.cs:534）
    anim_asset = (res in (ANIM_DAT_REL, ANIM_TRES_REL, ANIM_PNG_REL))
    chk(c is not None or is_char_pkg_dep(res) or res == RUNTIME_ASSEMBLY or anim_asset,
        f"B8 声明资源可推导类别: {res}",
        f"{c}/{k} pkgDep={is_char_pkg_dep(res)} animAsset={anim_asset}")
    if c:
        pool = {"Character": declared_char, "Packet": declared_packet,
                "CharacterSprite": declared_sprite}.get(c, set())
        chk(k in pool, f"B9 provides 覆盖 {c}/{k}", f"pool={sorted(pool)}")

# resources 必须是 XWModManifestSyncService.SyncProject 的规范序（OrdinalIgnoreCase 升序），
# 否则编辑器一打开工程就把 mod.json 重写了（字节幂等立刻崩）。
_order = [p.lower() for p in mod_json["resources"]]
chk(_order == sorted(_order), "B9b resources 为 OrdinalIgnoreCase 升序（SyncProject 规范序）",
    str(mod_json["resources"]))

# 包内每个可推导资源都必须在 manifest 里（否则被 SyncProject 加进来或视为未声明）
undeclared = []
for rel in pkg_files:
    if rel.endswith((".uid", ".import", ".cs")):
        continue
    c, k = infer_runtime_entry(rel)
    if c and rel not in mod_json["resources"]:
        undeclared.append(f"{c}/{k}:{rel}")
chk(not undeclared, "B10 包内可推导资源均已声明", "; ".join(undeclared))

# translations 指向真实文件 + 表头
tr = mod_json["translations"]
chk(len(tr) == 1 and tr[0] == "Localization/translations.csv", "B11 translations 指向 CSV", str(tr))
chk(os.path.isfile(R(tr[0])), "B12 翻译文件存在")
csv_head = read(tr[0]).split("\n")[0]
chk(csv_head == "key,zh_CN,en_US", "B13 翻译表头对齐编辑器", csv_head)
note("B14 翻译仅编辑器可见",
     "ModLoader 无 TranslationServer.AddTranslation ⇒ 游戏内不加载它，文案已改为**内联**")
# ★ 2026-09-25：CSV 的键已从 TOWERDEFENSE_* 改成**内联的中文原文本身**（那些 key 全部废弃）
_csv_rows = [ln for ln in read(tr[0]).split("\n")[1:] if ln.strip()]
chk(all(not ln.startswith("TOWERDEFENSE_") for ln in _csv_rows),
    "B15 CSV 不再用 TOWERDEFENSE_* 键（已改字面量键，与资源内联文案同源）", str(_csv_rows))
chk(any(ln.split(",")[0] == PLANT_CN_NAME for ln in _csv_rows),
    "B15b CSV 含以植物中文名为键的那一行", str(_csv_rows))

# ============================================================ B2. 托管运行时程序集
# 依据 ModLoader.cs：327-352 ValidateDeclaredPackageExecutables / 528-551 逐文件分类 /
# 911-947 ResolveDeclaredRuntimeAssembly + IsDeclaredRuntimeAssembly /
# 959-977 IsRuntimeDependencyFile / 667-671 TryInitializeRuntimeEntry 失败 ⇒ 整包回滚。
print("\n--- B2. 托管运行时程序集 ---")
dll_abs = R(RUNTIME_ASSEMBLY)
chk(os.path.isfile(dll_abs), "R1 Runtime/ModAssembly.dll 存在于构建目录", dll_abs)
dll_raw = b""
if os.path.isfile(dll_abs):
    dll_raw = open(dll_abs, "rb").read()
    chk(dll_raw[:2] == b"MZ", "R2 是合法 PE 文件（MZ 头）", dll_raw[:2].hex())
    # 类型名会以 UTF-8 存进 .NET 元数据 #Strings 堆，作为廉价的存在性冒烟检查
    chk(RUNTIME_ENTRY_TYPE.encode() in dll_raw,
        "R3 程序集元数据里含入口类型名 " + RUNTIME_ENTRY_TYPE)
    chk(b"IXWModRuntimeEntry" in dll_raw, "R4 程序集引用了 IXWModRuntimeEntry")
    chk(len(dll_raw) > 2048, "R5 体积合理（>2KB）", f"{len(dll_raw)} B")
    chk(len(dll_raw) < 2 * 1024 * 1024, "R6 体积合理（<2MB）", f"{len(dll_raw)} B")

# R7：Runtime/ 目录下只许有 ModAssembly.dll。
#     多一个 .dll/.exe/.bat/.cmd/.ps1 会被 ValidateDeclaredPackageExecutables（343-346 行）
#     判为 "undeclared executable package file" 直接抛 InvalidDataException（整包拒收）。
runtime_dir = os.path.join(BUILD, "Runtime")
if os.path.isdir(runtime_dir):
    extra_runtime = sorted(f for f in os.listdir(runtime_dir) if f != "ModAssembly.dll")
    chk(not extra_runtime, "R7 Runtime/ 下只有 ModAssembly.dll", str(extra_runtime))
else:
    chk(False, "R7 Runtime/ 目录存在", runtime_dir)

# R8：构建目录里除声明的程序集外，不得再有别的可执行包文件
stray_exec = []
for root, dirs, files in os.walk(BUILD):
    for f in files:
        rel = os.path.relpath(os.path.join(root, f), BUILD).replace("\\", "/")
        if rel.lower().endswith(EXEC_EXTS) and rel != RUNTIME_ASSEMBLY:
            stray_exec.append(rel)
chk(not stray_exec, "R8 构建目录内无未声明的可执行文件", "; ".join(stray_exec[:6]))

# ============================================================ B3. 卡库 / 图鉴一致性
# 需求（用户 2026-09-19）：卡牌不能只出现在图鉴里，必须能在**选卡界面**被选到，
# 且「图鉴里收录的卡」与「卡牌库里可选的卡」保持一致。
# 机制依据（全部来自解包源码，逐条有位置）：
#   · 选卡界面 = Prefab/GUI/DialogBox/... TowerDefenseBattleFeaturePacketBank.cs
#     → CategoryChooseAsync 按 packetBankData.category[分类] 列卡（514 行）
#   · packetBankData = TowerDefenseManager.GetPacketBankData(config.packetBankType)
#     → TowerDefenseLevelPacketBankConfig.packetBankType 默认 "GeneralPlant"
#   · 图鉴 = Almanac.cs:219 WithPlants(GetPacketBankData("GeneralPlant")) ← 同一个库
#   ⇒ 只要本卡进了共享 GeneralPlant.Gold，两边同源一致。
print("\n--- B3. 卡库 / 图鉴一致性 ---")

BANK_JSON = os.path.join(UNPACK, "Asset", "Config", "PacketBank", "PacketBankResource.json")
BANK_SRC = os.path.join(UNPACK, "Registry", "Battle", "Feature", "PacketBank",
                        "Resource", "TowerDefensePacketBankData.cs")
PKBBANK_SRC = os.path.join(UNPACK, "Registry", "Battle", "Feature", "PacketBank",
                           "TowerDefenseBattleFeaturePacketBank.cs")
PKBANK_CFG_SRC = os.path.join(UNPACK, "Registry", "Battle", "Feature", "PacketBank",
                              "Resource", "TowerDefenseLevelPacketBankConfig.cs")
PACKET_CFG_SRC = os.path.join(UNPACK, "Registry", "Battle", "Feature", "PacketBank",
                              "Resource", "Packet", "TowerDefensePacketConfig.cs")
PROGRESS_SRC = os.path.join(UNPACK, "addons", "ModEditor", "ModSystem", "XWModPlayerProgressService.cs")

# ⚠️ 判 DLL 里有没有某个东西，要看它属于哪一类：
#   类型名/成员名 → 元数据 #Strings 堆，**UTF-8**（直接 in dll_raw）；
#   字符串字面量  → #US 堆，**UTF-16LE**。
# ⚠️⚠️ 字面量必须用 `lit.encode("utf-16-le") in dll_raw` **按字节搜**，
#     不能把整个 dll 先 decode 成 str 再 in —— 字面量起始偏移可能是奇数，
#     整体解码会按 0 偏移两两配对，奇数偏移的字面量就永远搜不到（踩过：假红）。
def has_literal(lit):
    return lit.encode("utf-16-le") in dll_raw

chk(os.path.isfile(BANK_JSON), "K1 找到 PacketBankResource.json", BANK_JSON)
banks_raw = json.load(io.open(BANK_JSON, encoding="utf-8")) if os.path.isfile(BANK_JSON) else {}


def _include_closure(bank, seen):
    """重算 Include 闭包（游戏里是 ResourceManager.BuildExpandedPacketBank 的递归合并语义）。"""
    for inc in banks_raw.get(bank, {}).get("Include") or []:
        if inc not in seen:
            seen.add(inc)
            _include_closure(inc, seen)
    return seen


derived = sorted(b for b in banks_raw
                 if b == "GeneralPlant" or "GeneralPlant" in _include_closure(b, set()))
chk(derived == ["GeneralPlant", "Total"], "K2 GeneralPlant 的 Include 闭包派生集 == {GeneralPlant, Total}",
    str(derived))

gp_gold = banks_raw.get("GeneralPlant", {}).get("Category", {}).get("Gold", [])
chk(len(gp_gold) > 0, "K3 GeneralPlant 有 Gold 分类（本卡要并进去的地方）", f"{len(gp_gold)} 张")
chk("Gold" in banks_raw.get("Total", {}).get("Category", {}), "K3b Total 也有 Gold 分类")

# 插件要真的动共享卡库（TOWERDEFENSE_PACKETBANKS 是**成员名** ⇒ UTF-8）
chk(b"TOWERDEFENSE_PACKETBANKS" in dll_raw, "K4 插件引用了 TOWERDEFENSE_PACKETBANKS（共享卡库）")
# 根卡库名与派生库兜底名是**字符串字面量** ⇒ UTF-16LE
for lit in ("GeneralPlant", "Total", "PacketBankResource.json", "Gold", "Include"):
    chk(has_literal(lit), "K5 插件内含字面量 " + lit)

if os.path.isfile(PKBANK_CFG_SRC):
    cfg_src = io.open(PKBANK_CFG_SRC, encoding="utf-8", errors="replace").read()
    chk('packetBankType = "GeneralPlant"' in cfg_src,
        "K6 选卡界面默认读 GeneralPlant（packetBankType 默认值）")
else:
    chk(False, "K6 找到 TowerDefenseLevelPacketBankConfig.cs", PKBANK_CFG_SRC)

if os.path.isfile(PKBBANK_SRC):
    pb_src = io.open(PKBBANK_SRC, encoding="utf-8", errors="replace").read()
    chk("packetBankData.category[_category]" in pb_src,
        "K7 选卡界面按 packetBankData.category[分类] 列卡（机制证据）")
    chk('GetPacketBankData(config.packetBankType)' in pb_src,
        "K7b 选卡界面的卡库取自 config.packetBankType")
else:
    chk(False, "K7 找到 TowerDefenseBattleFeaturePacketBank.cs", PKBBANK_SRC)

if os.path.isfile(BANK_SRC):
    bs = io.open(BANK_SRC, encoding="utf-8", errors="replace").read()
    # GetPlantList() 只认这 6 个键 ⇒ 只进 ModPlants 是选不到的，必须进 Gold
    keys = set(re.findall(r'case "(\w+)":', bs))
    chk(keys == {"White", "Gold", "Diamond", "Colour", "Star", "Original"},
        "K8 GetPlantList 只认 6 个植物分类（不含 ModPlants）⇒ 必须进 Gold", str(sorted(keys)))
else:
    chk(False, "K8 找到 TowerDefensePacketBankData.cs", BANK_SRC)

# 图鉴那份拷贝由 WithPlants 产出 + Mod 植物被塞进 ModPlants（图鉴隔离的成因）
catalog_src = os.path.join(UNPACK, "addons", "ModEditor", "ModSystem", "XWModContentCatalog.cs")
if os.path.isfile(catalog_src):
    cs = io.open(catalog_src, encoding="utf-8", errors="replace").read()
    chk('towerDefensePacketBankData.category["ModPlants"] = array' in cs,
        "K9 WithPlants 把 Mod 植物塞进 ModPlants（隔离成因）")
    chk('PlantCategory = "ModPlants"' in cs, "K9b PlantCategory 常量 == ModPlants")
else:
    chk(False, "K9 找到 XWModContentCatalog.cs", catalog_src)

if os.path.isfile(PACKET_CFG_SRC):
    pc = io.open(PACKET_CFG_SRC, encoding="utf-8", errors="replace").read()
    chk("XWModPlayerProgressService.TryPacketUnlock(this, out var unlocked)" in pc,
        "K10 Unlock() 先问 Mod 进度服务（Mod 卡不走存档解锁）")
else:
    chk(False, "K10 找到 TowerDefensePacketConfig.cs", PACKET_CFG_SRC)

if os.path.isfile(PROGRESS_SRC):
    ps = io.open(PROGRESS_SRC, encoding="utf-8", errors="replace").read()
    chk("if (packet.unlockCheckList == null || packet.unlockCheckList.Count == 0 || IsUnlocked(" in ps
        and "unlocked = true;" in ps,
        "K10b 空 unlockCheckList ⇒ Mod 卡 unlocked = true（本卡是解锁的、能被选中）")
else:
    chk(False, "K10b 找到 XWModPlayerProgressService.cs", PROGRESS_SRC)

# 插件源码侧：补卡库必须在扫描里被调用，且是 check-then-add（幂等）
entry_src = os.path.join(WS, "runtime_src_plant", RUNTIME_ENTRY_TYPE + ".cs")
if os.path.isfile(entry_src):
    es = io.open(entry_src, encoding="utf-8", errors="replace").read()
    chk("TryPatchCardBanks();" in es and "private void TryPatchCardBanks()" in es,
        "K11 插件有 TryPatchCardBanks 且在 ScanScene 里被调用")
    chk("manager.TOWERDEFENSE_PACKETBANKS" in es, "K11b 插件读的是共享卡库实例")
    chk("FallbackDerivedBankKeys" in es, "K11c 派生卡库有兜底常量（json 读不到时用）")

    # ---- ★ 2026-09-24 齐射改版：插件只管大招；常规攻击 = 数据侧齐射（动画 fire 事件）----
    chk("OnFireReady" in es, "K12 订阅 OnFireReady（AttackEntered 里恰好一次 = 一次攻击）")
    chk("fire.OnFireVolley" not in es,
        "K12b 不再订阅 OnFireVolley（齐射一次会连发 7 次信号，概率判定不需要它）")
    # ★ 反转（2026-09-24）：常规齐射恰恰要靠动画 fire 事件触发（AnimeEvent →
    #   FireConfiguredVolley → Fire()）⇒ 插件**不得**再屏蔽发射链
    #   （2026-09-21 的 "modfire" 屏蔽已撤销，否则整株植物哑火）。
    chk('VanillaFireEventName' not in es,
        "K13 已撤销 vanilla 发射链屏蔽（齐射靠动画 fire 事件，屏蔽 = 整株哑火）")
    chk("fire.fireEventName" not in es,
        "K13b 插件不改写 fireEventName（回落定义默认值 \"fire\"）")
    chk("CreateProjectileByData(" in es,
        "K13c 大招走 CreateProjectileByData（狐尾草 TowerDefensePlantHWC.FireVolley 同款 API）")
    chk("fire.Fire()" not in es,
        "K13d 插件不再调 fire.Fire()（它现在一次会打出全部 7 条齐射配置）")
    chk("spriteRotationOverride" in es,
        "K13e 大招 overrides 带 spriteRotationOverride（与 Fire() :3493 同口径，弹体随散射角旋转）")
    chk("fire.fireAnimeClips =" not in es,
        "K13f 插件**不赋值** fireAnimeClips（开火动画必须照播）")
    chk("forceLocalRender = true" in es and "forceCpuPoseRender = true" in es,
        "K14 对自制外观精灵**同时**设 forceLocalRender + forceCpuPoseRender（修动画静止）")
    chk("animeFile" in es and "ResourcePath" in es and "IsOurSkinData" in es,
        "K14b 靠 animeFile/ResourcePath 关键字识别本 Mod 外观（纯预览场景没有战斗角色可依赖）")
    chk("TryPatchSkinRender" in es and "ScanRecursive" in es,
        "K14c 精灵修复挂在整树扫描里 ⇒ 战斗内 / 图鉴 / 选卡 / 种植预览全覆盖")
    # K15 系列（#45 改版）：判定参数已经搬进植物/僵尸**共用**的判定核心，
    # 入口里只剩 `= GatlingVolleyParams.X;` 转发。于是每条拆成两问：
    #   (a) 入口确实转发（谁写回字面量 / 改了转发名，这里立刻红）；
    #   (b) 共用核心里的字面量等于期望值（防「共用核心被改、两版一起悄悄变」）。
    # ★ 2026-09-24 齐射改版：植物常规攻击已是数据侧齐射，入口不再消费
    #   PeasPerAttack / PeaSpacingSeconds（那是僵尸连发链的参数）⇒ 这两条只查 (b)。
    CORE = os.path.join(WS, "runtime_shared", "GatlingVolleyCore.cs")
    if os.path.isfile(CORE):
        core = io.open(CORE, encoding="utf-8", errors="replace").read()
    else:
        core = ""
        chk(False, "K15 找到共用判定核心 runtime_shared/GatlingVolleyCore.cs", CORE)
    VOLLEY = (("PeasPerAttack", "PeasPerAttack", False, 7, "K15 连发链每轮 7 颗（核心记录；僵尸包用）"),
              ("PeaSpacingSeconds", "PeaSpacingSeconds", False, 0.1, "K15b 连发间距 0.1s（核心记录；僵尸包用）"),
              ("UltimateChance", "UltimateChance", True, 0.10, "K15c 大招概率 10%"),
              ("UltimateSeconds", "UltimateSeconds", True, 5.0, "K15d 大招 5 秒"),
              ("UltimatePeas", "UltimatePeas", True, 300, "K15e 大招 300 颗"),
              ("ScatterHalfAngleDeg", "ScatterHalfAngleDeg", True, 15.0, "K15f 散射半角 ±15°"),
              ("MaxPeasPerFrame", "MaxPeasPerFrame", True, 12, "K15g 单帧上限（防掉帧雪崩）"),
              ("StallGapMsec", "StallThresholdMsec", True, 250,
               "K15h 暂停/长卡顿补偿（避免继续瞬间补射几百颗）"))
    for _local, _shared, _fwd, _val, _nm in VOLLEY:
        if _fwd:
            chk(re.search(r"const\s+\w+\s+" + _local
                          + r"\s*=\s*GatlingVolleyParams\." + _shared + r"\s*;", es) is not None,
                _nm + "：入口转发 GatlingVolleyParams." + _shared)
        _m = re.compile(r"const\s+\w+\s+" + _shared + r"\s*=\s*([0-9.]+)\s*;").search(core)
        chk(_m is not None and abs(float(_m.group(1)) - _val) < 1e-9,
            _nm + "：共用核心字面量 = " + repr(_val),
            "找不到" if _m is None else _m.group(1))
    chk("GatlingVolleyJudge.BurstDueMsec(" in es
        and "(index + 1) * GatlingVolleyParams.BurstIntervalMsec" in core,
        "K16 大招按「第 k 颗 = 起点 + k×间隔」算时刻（无浮点漂移 ⇒ 恰好 300 颗 / 5 秒）")
    for _fn in ("GatlingVolleyJudge.RollUltimate(", "GatlingVolleyJudge.ScatterAngleDeg(",
                "GatlingVolleyJudge.StallGap(", "GatlingVolleyJudge.ShiftTimeline("):
        chk(_fn in es, "K19 植物入口真的调用共用判定 " + _fn)
    # K18：两个 csproj 都挂了**同一份**共用源 ⇒ 才算真共用（否则只是各抄一份，照样漂移）
    for _proj in (os.path.join(WS, "runtime_src_plant", "SuperGatlingPeaRuntime.csproj"),
                  os.path.join(WS, "runtime_src_zombie_super_gatling",
                               "SuperGatlingPaperRuntime.csproj")):
        _pt = (io.open(_proj, encoding="utf-8", errors="replace").read()
               if os.path.isfile(_proj) else "")
        chk('Include="..\\runtime_shared\\GatlingVolleyCore.cs"' in _pt,
            "K18 两版 csproj 都 Compile Include 同一份共用源（"
            + os.path.basename(_proj) + "）")
    chk("check.GetProjectile()" in es and "CreateProjectileByData(" in es,
        "K17 大招走 CreateProjectileByData（与 Fire() 同一段弹体创建代码 ⇒ 命中/伤害行为必然一致）")
    # ---- ★ 2026-09-25 图鉴去重（用户口径：删掉「只包含该角色」的独立图鉴，保留在已有的金卡分类里）----
    # 机制：XWModContentCatalog.WithPlants 把所有 Mod 植物**单列**成 category["ModPlants"]
    #   （addons/ModEditor/ModSystem/XWModContentCatalog.cs:15 常量 + :120 写入；全库唯一调用点
    #    Almanac.cs:219），图鉴按 plantPacketBank.category 的键顺序翻页（Almanac.cs:317-328）
    #   ⇒ 本卡**同时**出现在 ModPlants 与 Gold 两个分类里 = 用户看到的重复。
    chk('private const string ModPlantCategory = "ModPlants";' in es,
        "K20 插件有 ModPlantCategory = \"ModPlants\" 常量（图鉴的 Mod 独立分类键名）")
    chk("categories.Remove(ModPlantCategory)" in es,
        "K20b 插件能把空的 ModPlants 分类**整个删掉**（「只含本角色」的独立图鉴随之消失）")
    chk("modPlants.RemoveAt(i)" in es,
        "K20c 插件是**逐条摘掉本卡**而不是整类删（别的 Mod 植物的分类必须留着）")
    chk("almanac.plantCategoryId" in es,
        "K20d 插件删分类后回落 plantCategoryId（否则 InitPlant 的 "
        "`plantCategoryId >= category.Count` 守卫会 return 出空列表）")
    chk("almanac.InitPlant()" in es,
        "K20e 植物页已打开时能主动刷新（否则要手动翻一次分类才看得到）")
    chk("IsPlantPageInitialized" in es,
        "K20f 刷新仍受「植物页已初始化」守卫（不破坏图鉴的懒初始化设计）")
    chk("gold.RemoveAt(i)" in es,
        "K20g 金卡分类里也去重（同一张卡在同一个分类里出现两份的另一条可能路径）")
else:
    chk(False, "K11 找到插件源码", entry_src)

# ============================================================ C. 玩法数值
print("\n--- C. 玩法数值 ---")
cfg = read(f"{PLANT_REL}/Scene/{CHAR_KEY}ComponentSet.tres")
dirs = [float(x) for x in re.findall(r"^dir = (-?[\d.]+)$", cfg, re.M)]
# ★ 2026-09-24 齐射改版：常规攻击 = 数据侧齐射 —— 7 条配置（仅 firePosId 0..6 不同），
#   动画 f62 的 1 个 fire 事件触发 1 次 Fire() 同帧全打出（狐尾草 HWC 同款齐射通道）。
chk(len(dirs) == 7, "C1 恰好 7 条发射配置（齐射）", str(dirs))
chk(all(abs(d) < 1e-9 for d in dirs), "C2 dir 恒为 0（仅直线）", str(dirs))
_pos_ids = [int(x) for x in re.findall(r"^firePosId = (\d+)$", cfg, re.M)]
chk(sorted(_pos_ids) == list(range(7)), "C3a firePosId 恰好 0..6 各一次（= 7 个发射点）", str(_pos_ids))
chk(len(re.findall(r'fireProjectileList = \[(.*?)\]', cfg, re.S)) == 1
    and len(re.findall(r'SubResource\("Fire_Resource_proj\d+"\)', cfg)) == 7,
    "C3 fireProjectileList 恰 7 项（proj0..6）")
chk("fireNumAtOnce" not in cfg, "C4 不含 fireNumAtOnce（默认 false ⇒ 恰好 1 次 Fire() = 一次齐射）")
chk("fireNum = 1" in cfg, "C5 fireNum = 1")
chk("lockProjectileGridY = true" in cfg,
    "C5b lockProjectileGridY = true（横向散布后锁行，命中恒按种植行过滤，BulletField.cs:1473/5598）")
chk(len(re.findall(r'^speed = ', cfg, re.M)) == 7, "C6 每条配置都带 speed（7 条）")
chk(len(re.findall(r'^checkProjectileId = 0$', cfg, re.M)) == 7, "C7 全部指向 check 0（伤害与单发同源）")
chk("fireAnimeTimeScale = 3.0" in cfg, "C8 fireAnimeTimeScale = 3.0（开火动画照播）")

sc = read(scene_rel)
chk("fireInterval = 1.5" in sc, "C9 场景 fireInterval = 1.5")
chk("fireNum = 1" in sc, "C10 场景 fireNum = 1（fireNumAtOnce=false ⇒ 一次 Fire() = 一次齐射）")
chk('projectileName = "Pea"' in sc, "C11 场景 projectileName = Pea")
chk(f'config = ExtResource("5")' in sc, "C12 场景挂载了新配置")
chk("HitBoxDefinition" in sc, "C13 场景有受击盒")
chk('script = ExtResource("3")' in sc, "C14 场景挂载了原版机枪射手脚本")
chk("TowerDefensePlantGatlingPea.cs" in sc, "C15 脚本走 res:// 指向原版")
chk(f'path="../Sprite/{CHAR_KEY}.tscn"' in sc, "C16 精灵场景指向包内自制外观（相对引用）")
# ⚠️ 原来这条写的是 `"GatlingPea.tscn" in sc` —— 它是**假绿**：`SuperGatlingPea.tscn`
#    以 `GatlingPea.tscn` 结尾，子串必然命中，哪怕精灵场景被改回内置 `res://…GatlingPea.tscn`
#    也照样通过。改成断言完整相对路径 + 反例。
chk('path="./' + CHAR_KEY + 'ComponentSet.tres"' in sc, "C16b 组件集走同目录相对引用")
chk('path="../Config/TowerDefensePlant' + CHAR_KEY + '.tres"' in sc,
    "C16c 配置走 ../Config 相对引用")

# ---- C2x 卡片数值（用户指定：600 阳光 / 涨价 100 / 冷却 30s / 金卡）----
print("\n--- C2x 卡片与配置数值 ---")
cfg_body = read(f"{PLANT_REL}/Config/TowerDefensePlant{CHAR_KEY}.tres")
chk(mod_json["provides"]["Packet"] == [CHAR_KEY],
    "C20 卡片注册键 == 角色 key（saveKey 必须与之一致）")
card_body = read(CARD_REL)
pkg_card = read(f"{PLANT_REL}/Packet/{CHAR_KEY}.tres")
chk(prop(cfg_body, "cost") == "600", "C21 阳光花费 = 600", str(prop(cfg_body, "cost")))
chk(prop(cfg_body, "costRise") == "100", "C22 种植涨价 = 100", str(prop(cfg_body, "costRise")))
chk(prop(cfg_body, "packetCooldown") == "30.0", "C23 冷却 = 30.0s",
    str(prop(cfg_body, "packetCooldown")))
chk(prop(cfg_body, "name").strip('"') == CHAR_KEY,
    "C24 config.name == 角色场景文件名（TOWERDEFENSE_CHARCATERS 的键）",
    str(prop(cfg_body, "name")))
for label, body in (("Cards/", card_body), ("包内 Packet/", pkg_card)):
    chk(prop(body, "saveKey").strip('"') == CHAR_KEY, f"C25 {label} saveKey == 注册键",
        str(prop(body, "saveKey")))
    chk(prop(body, "type") == "1", f"C26 {label} type = 1（GOLD 金卡）", str(prop(body, "type")))
    chk(prop(body, "unlockCheckList") == "[]", f"C27 {label} unlockCheckList 为空表",
        str(prop(body, "unlockCheckList")))
    chk('characterConfig = ExtResource("1")' in body, f"C28 {label} 绑定 characterConfig")
    # ---- C29x ★ 2026-09-25 文案**内联**（用户指定的图鉴文本逐字核对）----
    chk(prop_block(body, "name") == PLANT_CN_NAME,
        f"C29 {label} name 是内联中文（不是翻译键）", repr(prop_block(body, "name")))
    chk(prop_block(body, "describe") == PLANT_CN_DESC,
        f"C29b {label} describe 是内联短句（面板会自己包 [color=2f375e]）",
        repr(prop_block(body, "describe")))
    chk(prop_block(body, "handbookDescribe") == PLANT_CN_HANDBOOK_DESC,
        f"C29c {label} handbookDescribe = 5 行数值块（真实换行，不是 \\n 转义）",
        repr(prop_block(body, "handbookDescribe")))
    chk(prop_block(body, "handbookStory") == PLANT_CN_STORY,
        f"C29d {label} handbookStory 逐字等于指定故事段",
        repr(prop_block(body, "handbookStory")))
    chk("TOWERDEFENSE_PLANT_SUPERGATLINGPEA" not in body,
        f"C29e {label} 不含废弃翻译键（游戏内会原样显示 key）")
    chk('describe = "[color=' not in body,
        f"C29f {label} describe 不自带颜色标签（面板会再包一层 ⇒ 嵌套）")
    # 「威力」用户口径：1.5 秒（截图上的 2s 是旧值）
    chk("威力：[color=cc241d]20×7 /1.5秒[/color]" in body,
        f"C29g {label} 威力 = 20×7 /1.5秒（用户 2026-09-25 指定）")
    chk("20×7 /2s" not in body and "20×7 /2秒" not in body,
        f"C29h {label} 不含旧的 2s / 2秒 口径")
    # 头词裸文本 + 数值 [color=cc241d]：与官方 InformationPanel.tscn 自带范例同款
    _hb = (prop_block(body, "handbookDescribe") or "").split("\n")
    chk(len(_hb) == 5, f"C29i {label} 数值块恰好 5 行", str(len(_hb)))
    for _ln in _hb:
        chk(re.match(r"^[^\[\]]+：\[color=cc241d\][^\[\]]+\[/color\]$", _ln) is not None,
            f"C29j {label} 数值块行格式（头词裸文本 + [color=cc241d] 值）：{_ln}")

# ---- C4x 血量 1000 + 「可直接种植」（2026-09-19 用户指定）----
#
# 机制（源码位置见 build_plant_super_gatling.py docstring「数值」一节）：
#   · 血量：TowerDefenseCharacterInstance._Init:317-320
#       hitpointsBase = config.hitpoints; hitpoints = hitpointsBase + hitpointsNearDeath;
#     ⇒ 改 .tres 里的 hitpoints 即可（类默认 300.0）。
#   · 可直接种植：TowerDefenseCellInstance.CanPacketPlant:787-800
#       if (GetPlantCover().Count > 0 && !noLimit) { 找底座; if (!GetCoverCanDirectPlant()) return false; }
#     而 GetCoverCanDirectPlant():500-507 **只在有 _override 时才读它**，否则硬编码 return false
#     ⇒ 必须给卡片内联一个 TowerDefensePacketOverride，只开 coverCanDirectPlant。
print("\n--- C4x 血量 / 可直接种植 ---")
UP = lambda *p: os.path.join(UNPACK, *p)

DEFAULT_HP = 300.0
HITPOINTS = 1000.0

chk(prop(cfg_body, "hitpoints") == "1000.0",
    "C40 config.hitpoints = 1000.0", str(prop(cfg_body, "hitpoints")))
chk(prop(cfg_body, "hitpointsNearDeath") is None,
    "C41 hitpointsNearDeath 不写（保持 0 ⇒ 总血量就是 1000）",
    str(prop(cfg_body, "hitpointsNearDeath")))
# 顺序：TowerDefenseCharacterConfig 里 hitpoints 紧跟 name
i_hp = cfg_body.find("hitpoints = 1000.0")
i_name = cfg_body.find('name = "%s"' % CHAR_KEY)
chk(0 <= i_name < i_hp, "C42 hitpoints 写在 name 之后（对齐类声明顺序，防编辑器重排）",
    "name@%s hitpoints@%s" % (i_name, i_hp))

# 源码侧证据：默认 300 且 config→instance 的搬运存在
_ccfg = open(UP("Resource", "TowerDefense", "Character", "Config",
                "TowerDefenseCharacterConfig.cs"), encoding="utf-8", errors="replace").read()
chk("public double hitpoints = %s;" % DEFAULT_HP in _ccfg,
    "C43 TowerDefenseCharacterConfig.hitpoints 默认 = 300.0（我们覆盖成 1000）")
chk("public double hitpoints = 300.0;" in _ccfg,
    "C43b 确认类默认值字面量为 300.0")
_cinst = open(UP("Resource", "TowerDefense", "Character", "Instance",
                 "TowerDefenseCharacterInstance.cs"), encoding="utf-8", errors="replace").read()
chk("hitpointsBase = config.hitpoints;" in _cinst,
    "C44 TowerDefenseCharacterInstance 从 config.hitpoints 取血")
chk("hitpoints = hitpointsBase + hitpointsNearDeath;" in _cinst,
    "C44b 总血量 = hitpointsBase + hitpointsNearDeath（0 偏移 ⇒ 1000）")

# 覆盖底座仍在（= 双发射手；中文名从 Translate.csv 核对）
chk(prop(cfg_body, "plantCover") == '["PlantPeaShooter"]',
    "C45 plantCover 仍 = [\"PlantPeaShooter\"]（保留「种在双发射手上」这条路）",
    str(prop(cfg_body, "plantCover")))
_tr = open(UP("Asset", "Translate", "Translate.csv"), encoding="utf-8", errors="replace").read()
_peashooter_cn = None
for _l in _tr.splitlines():
    if _l.startswith("TOWERDEFENSE_PLANT_PEASHOOTER_NAME,"):
        _peashooter_cn = _l.split(",")[-1].strip()
chk(_peashooter_cn == "双发射手",
    "C46 PlantPeaShooter 的中文名就是「双发射手」（用户说的底座一致）", str(_peashooter_cn))

for label, body in (("Cards/", card_body), ("包内 Packet/", pkg_card)):
    chk('[sub_resource type="Resource" id="PacketOverride_direct_plant"]' in body,
        f"C47 {label} 内联 PacketOverride_direct_plant 子资源")
    chk(prop(body, "override") == 'SubResource("PacketOverride_direct_plant")',
        f"C48 {label} override 绑定到该子资源", str(prop(body, "override")))
    _sub = body.split('[sub_resource type="Resource" id="PacketOverride_direct_plant"]')[1].split("[resource]")[0]
    chk("coverCanDirectPlant = true" in _sub,
        f"C49 {label} 开启 coverCanDirectPlant = true（否则只能种在双发射手上）")
    # 只允许 script / coverCanDirectPlant / metadata：多写字段可能顶掉 characterConfig 的正常取值
    _extra = [ln.strip() for ln in _sub.splitlines()
              if ln.strip() and not ln.startswith(("script =", "coverCanDirectPlant", "metadata/", "["))]
    chk(_extra == [], f"C50 {label} override 只写 coverCanDirectPlant（其余走类默认 = 不覆盖）", str(_extra))
    chk('path="res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/TowerDefensePacketOverride.cs"'
        in body, f"C51 {label} 引用游戏自带 TowerDefensePacketOverride.cs")

# 反向对照：同一段提取逻辑喂一个「多写了字段」的假 body，必须能报出来。
# （防 C50 因为切片写法不对而变成永远为真的假绿 —— 这个 bug 本轮真踩过一次。）
_FAKE = ('[sub_resource type="Resource" id="PacketOverride_direct_plant"]\n'
         'script = ExtResource("3")\n'
         'cost = 1\n'
         'coverCanDirectPlant = true\n'
         'metadata/_custom_type_script = "x"\n'
         '\n[resource]\n')
_fake_sub = _FAKE.split('[sub_resource type="Resource" id="PacketOverride_direct_plant"]')[1].split("[resource]")[0]
_fake_extra = [ln.strip() for ln in _fake_sub.splitlines()
               if ln.strip() and not ln.startswith(("script =", "coverCanDirectPlant", "metadata/", "["))]
chk(_fake_extra == ["cost = 1"],
    "C50c 反向对照：多写字段时 C50 的提取逻辑必须报出来", str(_fake_extra))

# 机制证据：CanPacketPlant 读 GetCoverCanDirectPlant；后者无 override 时硬编码 false
_pcfg = open(UP("Registry", "Battle", "Feature", "PacketBank", "Resource", "Packet",
                "TowerDefensePacketConfig.cs"), encoding="utf-8", errors="replace").read()
chk("public TowerDefensePacketOverride _override;" in _pcfg,
    "C52 TowerDefensePacketConfig._override 是 [Export] public 字段（tres 属性名 override）")
chk("public bool GetCoverCanDirectPlant()" in _pcfg,
    "C53 GetCoverCanDirectPlant() 存在")
chk(re.search(r"if \(GodotObject\.IsInstanceValid\(_override\)\)\s*\{\s*return _override\.coverCanDirectPlant;\s*\}\s*return false;",
              _pcfg) is not None,
    "C54 GetCoverCanDirectPlant：有 override 才读，否则硬编码 return false")
chk("if (!packetConfig.GetCoverCanDirectPlant())" in
    open(UP("Registry", "Battle", "Feature", "Map", "Resource", "Cell",
            "TowerDefenseCellInstance.cs"), encoding="utf-8", errors="replace").read(),
    "C55 CanPacketPlant 里确实以 !GetCoverCanDirectPlant() 作为拒绝条件")
_ovsrc = open(UP("Registry", "Battle", "Feature", "PacketBank", "Resource", "Packet", "Override",
                 "TowerDefensePacketOverride.cs"), encoding="utf-8", errors="replace").read()
chk("public bool coverCanDirectPlant;" in _ovsrc,
    "C56 TowerDefensePacketOverride.coverCanDirectPlant 是 public bool 字段")
chk("public TowerDefenseCharacterOverride characterOverride = new TowerDefenseCharacterOverride();" in _ovsrc,
    "C57 characterOverride 默认非 null ⇒ 必须确认它是空操作（下一项）")
_cho = open(UP("Resource", "TowerDefense", "Character", "Override",
               "TowerDefenseCharacterOverride.cs"), encoding="utf-8", errors="replace").read()
chk("public double hitpointScale = -1.0;" in _cho and "if (hitpointScale != -1.0)" in _cho,
    "C58 TowerDefenseCharacterOverride 默认 hitpointScale = -1 ⇒ 不碰血量（空操作）")

# 官方正例：内置 Gold 挑战关也是用同一招给机枪盆栽开这个开关
_lvl23 = os.path.join(UNPACK, "Asset", "Config", "Level", "TowerDefense", "Challenge", "Gold",
                      "Challenge_Level2_3.tres")
if os.path.isfile(_lvl23):
    _lv = open(_lvl23, encoding="utf-8", errors="replace").read()
    chk("coverCanDirectPlant = true" in _lv and 'packetName = "PlantGatlingPot"' in _lv,
        "C59 官方正例：Gold 挑战关给 PlantGatlingPot 用的就是这个开关（本机制有官方先例）")
else:
    note("C59 跳过", "离线解包里找不到 Challenge_Level2_3.tres")

# 死字段提醒：plantCoverAll 运行时从未被读取
_ccfg_all = [f for f in (_ccfg,) if "plantCoverAll" in f]
chk(_ccfg_all != [], "C60 确认 plantCoverAll 只声明未被读（运行时死字段，别拿它当开关）")

# 生成器里必须留着这两个常量（防以后改生成器时丢掉需求）
_bld = open(BUILDER, encoding="utf-8").read()
chk("HITPOINTS = %.1f" % HITPOINTS in _bld, "C61 生成器有 HITPOINTS = 1000.0")
chk("COVER_CAN_DIRECT_PLANT = True" in _bld, "C62 生成器有 COVER_CAN_DIRECT_PLANT = True")

# ---- 精灵场景：GetPacketSpriteScene 的查找目标 ----
print("\n--- C3x 精灵场景 ---")
sprite_rel = f"{PLANT_REL}/Sprite/{SPRITE_FILE}"
chk(os.path.isfile(R(sprite_rel)), "C30 存在 Sprite/<Key>.tscn")
sp_body = read(sprite_rel)
c, k = infer_runtime_entry(sprite_rel)
chk(c == "CharacterSprite" and k == CHAR_KEY,
    "C31 Sprite 场景可推导为 CharacterSprite/" + CHAR_KEY, f"{c}/{k}")
# ⚠️ 本 Mod 已换成**自制外观**（自研 .dat 整帧单层 + 头独立分层）：
#    以前这里断言的是「复用游戏自带 GatlingPea.tscn 指针壳」，那条在换自制外观后**必须反转**，
#    否则校验会把正确产物判成 FAIL。
chk("GatlingPea.tscn" not in sp_body, "C32 精灵场景不再复用游戏自带贴图场景（已换自制外观）")
chk(f'path="{ANIM_TRES_REL.replace("Resources/Animations/", "../../../../../Resources/Animations/")}"' in sp_body
    or "SuperGatlingPea.tres" in sp_body,
    "C32b 精灵场景的 flashAnimeData 指向自制 .tres")
chk('Animation/Clip = "BodyIdle"' in sp_body and 'Animation/Clip = "HeadIdle"' in sp_body,
    "C32c 精灵场景已是双图层（根 BodyIdle / Head HeadIdle）")
lookup = prop(card_body, "saveKey").strip('"')
sprite_keys = {kk for cc, kk in reg_pairs if cc == "CharacterSprite"}
chk(lookup in sprite_keys or prop(cfg_body, "name").strip('"') in sprite_keys,
    "C33 CHARCTAER_SPRITE 能命中 saveKey 或 characterConfig.name",
    f"lookup={lookup} sprite_keys={sorted(sprite_keys)}")

# 发射标记点路径必须真实存在于场景
marker = re.search(r'firePosMarkerPaths = \[(.*?)\]', cfg, re.S)
chk(marker is not None, "C17 有 firePosMarkerPaths")
if marker:
    _paths = re.findall(r'NodePath\("([^"]+)"\)', marker.group(1))
    chk(len(_paths) == 7 and all(re.search(r"Marker2D\d*$", p) for p in _paths),
        "C18 firePosMarkerPaths 恰 7 条且都指向 Marker2D*", str(_paths))
    # ★ 2026-09-24：7 个 Marker 节点必须真的在场景里，且位置 = 炮口点 + (dx, 0)
    #   （口径修正：沿**弹道方向 x** 排成一条水平直线 = 「一排」；旧口径沿 y 是「一列」，已废）
    _scn_marks = {}
    for _nm, _px, _py in re.findall(
            r'\[node name="(Marker2D\d*)" [^\]]*\]\nposition = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', sc):
        _scn_marks[_nm] = (float(_px), float(_py))
    chk(len(_scn_marks) == 7, "C19 场景里有 7 个 Marker2D 节点（齐射发射点）", str(sorted(_scn_marks)))
    chk("Marker2D" in _scn_marks, "C19b 基准 Marker2D 存在（= 炮口点）")
    _base = _scn_marks.get("Marker2D", (0.0, 0.0))
    _offs = sorted(round(_scn_marks[n][0] - _base[0], 4) for n in _scn_marks)
    chk(_offs == [0.0, 32.0, 64.0, 96.0, 128.0, 160.0, 192.0],
        "C19c 7 个 Marker 沿弹道 x 的偏移 = {0,32,64,96,128,160,192}px（32 > 豌豆 28 ⇒ 互不重叠）",
        str(_offs))
    chk(all(_scn_marks[n][1] == _base[1] for n in _scn_marks),
        "C19d 各 Marker 的 Y 相同（水平一条直线 = 一排，不是一列）")
    # firePosId 顺序（Marker2D, Marker2D2, ..., Marker2D7）的 x 必须一路向前
    _xs_ord = [round(_scn_marks["Marker2D" if i == 0 else f"Marker2D{i + 1}"][0], 4) for i in range(7)]
    chk(all(b > a for a, b in zip(_xs_ord, _xs_ord[1:])),
        "C19f 各 Marker 的 X 严格递增（按 firePosId 顺序一路向前，不回头）", str(_xs_ord))
    for _p in re.findall(r'NodePath\("([^"]+)"\)', marker.group(1)):
        _nm = _p.rsplit("/", 1)[-1]
        chk(_nm in _scn_marks, f"C19e 路径[{_p}] 在场景里有对应节点")

# ============================================================ D. 产物形态
print("\n--- D. 产物形态 ---")
pmod = os.path.join(DIST, f"{MOD_NAME}.pmod")
chk(os.path.isfile(pmod), "D1 dist/*.pmod 存在")
if os.path.isfile(pmod):
    with zipfile.ZipFile(pmod) as z:
        names = z.namelist()
        chk(names[0] == EXPECTED_HAS_ZIP_ENTRY0, "D2 条目 0 是 mod.json", names[0])
        chk(not any(n.endswith(".pvzmodeproject") for n in names), "D3 包内无工程文件")
        chk(not any(n.endswith(".cs") for n in names), "D4 包内无 .cs")
        chk(not any(n.endswith((".uid", ".import")) for n in names), "D5 包内无 .uid/.import")
        chk(scene_rel in names, "D6 包内有角色场景")
        chk(f"{PLANT_REL}/Scene/{CHAR_KEY}ComponentSet.tres" in names, "D7 包内有组件集")
        chk(sprite_rel in names, "D7b 包内有精灵场景（注册 CharacterSprite 用）")
        chk(CARD_REL in names, "D7c 包内有卡片（Resources/Cards/<Key>.tres）")
        chk(RUNTIME_ASSEMBLY in names, "D7d 包内有 Runtime/ModAssembly.dll（插件入口）")
        if RUNTIME_ASSEMBLY in names:
            chk(z.read(RUNTIME_ASSEMBLY) == dll_raw,
                "D7e 包内 DLL 与构建目录那份逐字节一致", f"{len(dll_raw)} B")
        _exec = [n for n in names if n.lower().endswith(EXEC_EXTS) and n != RUNTIME_ASSEMBLY]
        chk(not _exec, "D7f 包内无其它可执行文件（否则 undeclared executable 整包拒收）",
            "; ".join(_exec[:6]))
        chk(not any(n.startswith("Runtime/Dependencies/") for n in names),
            "D7g 包内无 Runtime/Dependencies/（本插件不依赖外部 dll）")
        for n in names:
            zi = z.getinfo(n)
            chk(zi.date_time == (2026, 1, 1, 0, 0, 0), f"D8 条目固定时间戳: {n}", str(zi.date_time))
    inner = None
    with zipfile.ZipFile(pmod) as z:
        inner = json.loads(z.read("mod.json").decode("utf-8"))
    chk(inner == mod_json, "D9 包内 mod.json 与工作区一致")

install_pmod = os.path.join(MODS, f"{MOD_NAME}.pmod")
chk(os.path.isfile(install_pmod), "D10 已安装到 Mods/")
if os.path.isfile(install_pmod):
    chk(hashlib.sha1(open(pmod, "rb").read()).hexdigest()
        == hashlib.sha1(open(install_pmod, "rb").read()).hexdigest(),
        "D11 安装副本与 dist 字节一致")

proj_dir = os.path.join(MODS, MOD_NAME)
chk(os.path.isdir(proj_dir), "D12 工程目录已镜像到 Mods/")
if os.path.isdir(proj_dir):
    pcs = [f for f in os.listdir(proj_dir) if f.endswith(".pvzmodeproject")]
    chk(len(pcs) == 1 and pcs[0] == f"{MOD_NAME}.pvzmodeproject", "D13 工程文件唯一且同名",
        str(pcs))
    subdirs = sum(len(d) for _, d, _ in os.walk(proj_dir))
    chk(subdirs > 50, "D14 工程目录已铺开标准子目录", f"{subdirs} 个子目录")
    pj_body = io.open(os.path.join(proj_dir, pcs[0]), "rb").read() if pcs else b""
    chk(b"\r\n" in pj_body and b"\n\n" not in pj_body.replace(b"\r\n", b""),
        "D15 工程文件为纯 CRLF")
    chk(not pj_body.startswith(b"\xef\xbb\xbf"), "D16 工程文件无 BOM")
    # 项目文件里不得有 .translation 之类不存在的引用
    pj = json.loads(pj_body.decode("utf-8-sig"))
    chk(list(pj.keys()) == ["Name", "Version", "Author", "Description", "ExportDirectory",
                            "GameDirectory", "CreatedDate", "LastModifiedDate"],
        "D17 工程文件键序正确")
    chk(pj["Name"] == MOD_NAME, "D18 Name == MOD_NAME")

# enabled_mods.json
en = os.path.join(MODS, "enabled_mods.json")
chk(os.path.isfile(en), "D19 enabled_mods.json 存在")
if os.path.isfile(en):
    ids = json.loads(io.open(en, encoding="utf-8").read())
    chk(MOD_ID in ids, "D20 本 Mod id 在启用列表", str(ids))
    chk(ids == sorted(ids, key=lambda s: s.lower()), "D21 启用列表大小写不敏感有序", str(ids))
    chk("vampirepool" in ids, "D22 未误删既有 Mod id")

# 镜像标记（09-16 起改用「工程文件」当标记，替代原来的 .generated 隐藏文件）
chk(os.path.isdir(proj_dir) and os.path.isfile(os.path.join(proj_dir, MOD_NAME + ".pvzmodeproject")),
    "D23 镜像目录带生成标记（工程文件）")

# D24-D26：工程布局必须逐项等于官方 XWModProjectLayout.StandardDirectories（72 项，直接读 C# 源码）
LAYOUT_CS = os.path.join(UNPACK, "addons", "ModEditor", "ModSystem", "XWModProjectLayout.cs")
chk(os.path.isfile(LAYOUT_CS), "D24 找到 XWModProjectLayout.cs", LAYOUT_CS)
if os.path.isfile(LAYOUT_CS):
    src = io.open(LAYOUT_CS, encoding="utf-8", errors="replace").read()
    m = re.search(r"StandardDirectories = new string\[(\d+)\]\s*\{(.*?)\};", src, re.S)
    official = re.findall(r'"([^"]+)"', m.group(2)) if m else []
    chk(m is not None and int(m.group(1)) == len(official),
        "D25 官方标准目录声明数与字面量数一致", f"{m.group(1) if m else '?'} vs {len(official)}")
    chk(len(official) == 72, "D26 官方标准目录 72 项", str(len(official)))
    with io.open(BUILDER, encoding="utf-8") as f:
        bsrc = f.read()
    bm = re.search(r"STANDARD_DIRS = \[(.*?)\n\]", bsrc, re.S)
    mine = re.findall(r'"([^"]+)"', bm.group(1)) if bm else []
    chk(mine == official, "D27 生成器 STANDARD_DIRS 与官方逐项同序",
        f"extra={[x for x in mine if x not in official][:5]} missing={[x for x in official if x not in mine][:5]}")
    # 与另一支构建器逐字一致（用户要求「两构建器行为一致」）
    m2 = re.search(r"STANDARD_DIRS = \[(.*?)\n\]",
                   io.open(MAP_BUILDER, encoding="utf-8").read(), re.S)
    other = re.findall(r'"([^"]+)"', m2.group(1)) if m2 else []
    chk(mine == other, "D28 与 build_map_vampire_pool.py 的 STANDARD_DIRS 逐字相同",
        f"{len(mine)} vs {len(other)}")
    missing_dirs = [d for d in official
                    if not os.path.isdir(os.path.join(proj_dir, d.replace("/", os.sep)))]
    chk(not missing_dirs, "D29 镜像目录里 72 个标准子目录齐全", str(missing_dirs[:5]))

# D30+：工程文件必须与「编辑器自己写出来的」同格式 —— 拿 Mods/新地图-1/ 做真品对照
PROJ_REL = os.path.join(proj_dir, MOD_NAME + ".pvzmodeproject")
pj = {}
if os.path.isfile(PROJ_REL):
    pj = json.loads(io.open(PROJ_REL, encoding="utf-8-sig").read())
MODS_FWD = MODS.replace("\\", "/")
chk(pj.get("ExportDirectory") == MODS_FWD + "/",
    "D30 ExportDirectory = 正斜杠 + 结尾斜杠的 Mods 目录（编辑器同格式）",
    repr(pj.get("ExportDirectory")))
REF_PROJ = os.path.join(MODS, "新地图-1", "新地图-1.pvzmodeproject")     # 游戏 F3 编辑器亲手建的工程
if os.path.isfile(REF_PROJ):
    ref = json.loads(io.open(REF_PROJ, encoding="utf-8-sig").read())
    chk(list(ref.keys()) == list(pj.keys()), "D31 字段集合与顺序同编辑器真品",
        f"{list(ref.keys())} vs {list(pj.keys())}")
    chk(ref.get("ExportDirectory") == pj.get("ExportDirectory"),
        "D32 ExportDirectory 与编辑器真品逐字一致",
        f"{ref.get('ExportDirectory')!r} vs {pj.get('ExportDirectory')!r}")
else:
    note("D31/D32 跳过", "找不到编辑器真品 Mods/新地图-1/*.pvzmodeproject")

# D33/D34：「最近工程」缓存 —— 本工程在内，且**不能把别人的条目清掉**
RECENT = os.path.join(os.path.dirname(MODS), "mod_editor_recent_projects.cfg")
rtxt = io.open(RECENT, encoding="utf-8-sig", errors="replace").read().replace("\r\n", "\n") \
    if os.path.isfile(RECENT) else ""
rpaths = [p.replace("\\", "/") for p in re.findall(r'^path_\d+="(.*)"$', rtxt, re.M)]
want_recent = os.path.join(MODS, MOD_NAME, MOD_NAME + ".pvzmodeproject").replace("\\", "/")
chk(want_recent in rpaths, "D33 最近工程登记了本工程（Mods 下的工程文件）", str(rpaths))
chk(not rpaths or any("吸血鬼屋泳池" in p for p in rpaths),
    "D34 最近工程没有清掉别人的条目（地图那条还在）", str(rpaths))
chk(all(not p.startswith(("D:", "d:")) for p in rpaths),
    "D35 最近工程里没有残留工作区路径（只登记 Mods 下的工程）", str(rpaths))

# ============================================================ E. 发射事件 + 头部抬升
print("\n--- E. 发射事件 + 头部抬升 ---")
# ★★ 依据：动画事件表是**常规攻击唯一的发射触发源**（引擎链路
#    AdobeAnimateSprite.events[frame] → OnAnimeEvent("fire") → FireComponent.AnimeEvent
#    → FireConfiguredVolley → Fire()）。事件表为空 = 实机「只有动画、一颗子弹都没有」。
#    帧号推导 + 内置 143 例交叉验证见 .cache/build_official_skin.py 的 derive_fire_frames()
#    与 .cache/probe_tres_mouth.py；本 Mod 规格（每 1.5 秒 1 轮 7 颗）⇒ 恰好 1 个事件。
TRES_TXT = read(ANIM_TRES_REL)
chk(TRES_TXT.count('"Command": "fire"') == 1,
    "E1 动画事件表含且仅含 1 个 fire 事件（= 每 1.5 秒 1 轮 7 颗）",
    str(TRES_TXT.count('"Command": "fire"')))
chk('"Argument": ""' in TRES_TXT, "E2 事件 Argument 为空串")
_fm = re.search(r"events = \[(.*)\]\s*$", TRES_TXT, re.M | re.S)
_slots = []
if _fm:
    _d, _cur = 1, ""                      # 正则已吃掉最外层 `[` ⇒ 从 1 起算
    for _ch in _fm.group(1):
        if _ch == "[":
            _d += 1
            if _d == 2:
                _cur = ""
            continue
        if _ch == "]":
            if _d == 2:
                _slots.append(_cur)
            _d -= 1
            continue
        if _d == 2:
            _cur += _ch
_ne = [i for i, c in enumerate(_slots) if c.strip()]
# f62 == 射击段(50..74)内头部前冲达最大伸出的首帧 == HeadFire 起点 +12（内置单发家族相位）
chk(_ne == [62], "E3 发射事件帧 == [62]（= HeadFire 起点 +12）", str(_ne))

DAT_BYTES = read(ANIM_DAT_REL, mode="rb")
chk(DAT_BYTES.endswith(b"\x00\x00\x00\x00"), "E4 .dat 尾部事件段存在（Argument 为空串 ⇒ 尾 4 字节为 0）")
_rec = 2 + 2 + (4 + len("fire")) + (4 + 0)      # u16 帧号 + u16 条数 + pascal("fire") + pascal("")
_off = len(DAT_BYTES) - 2 - _rec
chk(_off >= 0 and int.from_bytes(DAT_BYTES[_off:_off + 2], "little") == 1,
    "E5 .dat 事件条数 == 1",
    str(int.from_bytes(DAT_BYTES[_off:_off + 2], "little")) if _off >= 0 else "截断")
chk(_off >= 0 and int.from_bytes(DAT_BYTES[_off + 2:_off + 4], "little") == 62,
    "E6 .dat 事件帧 == 62（.dat 是实机真源，光写 .tres 不够）",
    str(int.from_bytes(DAT_BYTES[_off + 2:_off + 4], "little")) if _off >= 0 else "截断")

_hp = re.search(r'\[node name="Head"[^\]]*\]\n(?:[^\n]*\n)*?position = Vector2\((-?[\d.]+), *(-?[\d.]+)\)',
                sp_body)
# ★ 2026-09-24 口径更正：Head.position 是**死值**（引擎 UpdateChild :5259-5267 每帧覆写
#   `Position = 被跟随层 pose.Origin + 父 offset`），旧断言「(0, 负值) 抬头」钉的是从未
#   生效的机制。现在：position 清零（防死值回流），真正的头位旋钮是 Head.offset =
#   (-37.05, -47)（对齐豌豆射手的反解值，E7b 在下面钉）。
chk(_hp is not None and float(_hp.group(1)) == 0.0 and float(_hp.group(2)) == 0.0,
    "E7 Head.position = (0, 0)（死值清零；引擎每帧覆写它，抬高已改由 Head.offset 承担）",
    "缺 Head.position" if _hp is None else f"({_hp.group(1)}, {_hp.group(2)})")
_ho = re.findall(r'^offset = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', sp_body, re.M)
chk(len(_ho) == 2 and abs(float(_ho[1][0]) - (-37.05)) < 0.01 and abs(float(_ho[1][1]) - (-47.0)) < 0.01,
    "E7b Head.offset = (-37.05, -47)：头位对齐豌豆射手的反解值（根 offset 仍为 (-40,-40)）",
    str(_ho))


def _sgp_dat_clips(buf):
    """按 AdobeAnimateData.cs:1041-1081 的段序走 .dat，取 clip 表（终点必须==文件长）。"""
    def _ps(b, o):
        n = int.from_bytes(b[o:o + 4], "little"); o += 4
        return b[o:o + n].decode("utf-8"), o + n
    fmax = int.from_bytes(buf[4:6], "little")
    off = 18 + int.from_bytes(buf[10:18], "little")
    mn = int.from_bytes(buf[off:off + 2], "little"); off += 2
    for _ in range(mn):
        _, off = _ps(buf, off); off += 16
    ln = int.from_bytes(buf[off:off + 2], "little"); off += 2
    for _ in range(ln):
        _, off = _ps(buf, off)
        for _f in range(fmax):
            n = int.from_bytes(buf[off:off + 2], "little"); off += 2
            off += n * 30
    cn = int.from_bytes(buf[off:off + 2], "little"); off += 2
    out = {}
    for _ in range(cn):
        name, o2 = _ps(buf, off)
        out[name] = (int.from_bytes(buf[o2:o2 + 2], "little"),
                     int.from_bytes(buf[o2 + 2:o2 + 4], "little"))
        off = o2 + 4
    en = int.from_bytes(buf[off:off + 2], "little"); off += 2
    for _ in range(en):
        cnt = int.from_bytes(buf[off + 2:off + 4], "little"); off += 4
        for _k in range(cnt):
            _, off = _ps(buf, off); _, off = _ps(buf, off)
    assert off == len(buf), (off, len(buf))
    return out


_exp_clips = {"BodyIdle": (0, 24), "HeadFire": (50, 74), "HeadIdle": (25, 49)}
_tres_clips = {k: (int(a), int(b)) for k, a, b in
               re.findall(r'"(\w+)": Vector2i\((\d+), (\d+)\)', TRES_TXT)}
chk(_tres_clips == _exp_clips,
    "E8a 包内 .tres clips == {BodyIdle:(0,24), HeadFire:(50,74), HeadIdle:(25,49)}（抽搐修复：射击段口径）",
    str(_tres_clips))
try:
    _dat_clips = _sgp_dat_clips(DAT_BYTES)
except Exception as _ex:
    _dat_clips = f"解析失败: {_ex}"
chk(_dat_clips == _exp_clips,
    "E8b 包内 .dat clip 表与 .tres 一致（引擎加载 .dat 会覆写 clips 字典，只改 .tres = 白改）",
    str(_dat_clips))

# ============================================================ 分节统计
# 分节表**从本文件源码现算**（找所有 print("\n--- 标题 ---")），
# 每条断言按它的调用行号落到最近的前一个分节标题下。
# ⇒ 以后增删小节，这里自动跟随，不会像手写数字那样和实现对不上。
try:
    import collections as _col
    _own = io.open(__file__, encoding="utf-8", errors="replace").read().split("\n")
    _marks = []
    for _i, _ln in enumerate(_own, 1):
        _mm = re.match(r'\s*print\("\\n--- (.*?) ---"\)', _ln)
        if _mm:
            _marks.append((_i, _mm.group(1)))
    _sec = _col.OrderedDict()
    for _ln, _nm in _CHK_LINES:
        _cur = "(文件头)"
        for _ml, _mt in _marks:
            if _ml <= _ln:
                _cur = _mt
            else:
                break
        _sec[_cur] = _sec.get(_cur, 0) + 1
    print()
    print("分节断言数: " + "  |  ".join(f"{k} = {v}" for k, v in _sec.items()))
    _k = _col.Counter()
    for _ln, _nm in _CHK_LINES:
        _g = re.match(r"(K\d+[a-z]?)", _nm)
        _k[_g.group(1) if _g else "非 K 段"] += 1
    _shared = {g: _k[g] for g in sorted(_k) if g.startswith(("K15", "K16", "K18", "K19"))}
    print("共享判定核心断言(K15* / K16 / K18 / K19): "
          + "  ".join(f"{g}={v}" for g, v in _shared.items())
          + "  =>  合计 " + str(sum(_shared.values())))
except Exception as _e:
    print("(分节统计跳过:", _e, ")")

# ============================================================ 汇报
print()
for m in msgs:
    print(m)
print()
print(f"结果: ok={ok}  warn={warn}  FAIL={fail}   ->  {'通过' if fail == 0 else '未通过'}")
sys.exit(0 if fail == 0 else 1)
