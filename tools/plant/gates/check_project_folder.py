# -*- coding: utf-8 -*-
"""check_project_folder.py —— 校验「游戏侧编辑器规格的 Mod 工程目录」是否真的合规。

为什么需要它：游戏**只加载** user://Mods/*.pmod（XWModManager.ScanMods 只扫
TopDirectoryOnly 的 *.pmod），工程目录是给编辑器打开/导出用的另一种形态。
两种形态必须同时对，否则「装了但游戏里没有」或者「编辑器一打开就把 mod.json 改回原样」。

校验项（全部对齐 V0.28 解包源码的实际行为）：
  1) 目录骨架 == XWModProjectLayout.StandardDirectories（72 项，与游戏侧编辑器 新地图-1 同构；
     本 Mod 额外需要 Runtime/ 放托管程序集，白名单放行）
  2) <Name>.pvzmodeproject 的 JSON 键序/命名/时间格式/编码风格 == ModProjectSerializeHandler 实测产物
  3) 工程内 mod.json == XWModManifest 的 18 键全集，且能被 XWModManifestSyncService 判定为「无需重写」
     （含 provides 必须同时声明 Map 与 Texture；runtime* 四个字段；resources 必须是
      SyncProject 规范序 = tres + jpg + dll 按 OrdinalIgnoreCase 升序）
  4) 工程内的 tres / 贴图 / DLL 与打包内的一致（否则编辑器一改就分叉）
  5) Mods/enabled_mods.json 里含本 mod id（没有它 → LoadEnabledIds 返回空 → 一个 mod 都不加载）
  6) .pmod 只含 mod.json + 声明的 resources（mod.json 是第 0 条目、工程文件没被打进包）

用法：
    python .cache/check_project_folder.py            # 用默认路径
    python .cache/check_project_folder.py <工程目录> <pmod路径>
"""

import io
import json
import os
import re
import sys
import zipfile

APPDATA = os.environ.get("APPDATA", "")
USER_DATA = os.path.join(APPDATA, "Godot", "app_userdata", "植物大战僵尸杂交版")
MODS = os.path.join(USER_DATA, "Mods")
MOD_NAME = "吸血鬼屋泳池"
MOD_ID = "vampirepool"
MAP_KEY = "VampirePool"

# ---- 运行时换贴图相关的期望值（必须与 build_map_vampire_pool.py 的常量一致）----
TEXTURE_KEY = "VampirePoolBackground"
TEXTURE_REL = "Assets/Images/%s.jpg" % TEXTURE_KEY
RESOURCE_TRES = "Resources/Maps/%s.tres" % MAP_KEY
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"      # ModLoader 只认这个字面量
RUNTIME_ENTRY_TYPE = "VampirePoolRuntimeEntry"
RUNTIME_API_VERSION = 1
RUNTIME_POLICY = "optional"
# SyncProject 规范序：工程目录里所有非忽略文件（此处 tres + jpg + dll），OrdinalIgnoreCase 升序
WANT_RES = sorted([RESOURCE_TRES, TEXTURE_REL, RUNTIME_ASSEMBLY], key=lambda p: p.lower())

OK, WARN, BAD = "ok", "warn", "bad"
ITEMS = []


def add(level, code, msg):
    ITEMS.append({"level": level, "code": code, "msg": msg})


def need(cond, code, msg, level=BAD):
    add(OK if cond else level, code, msg)
    return cond


# ---- 从源码抄来的 72 个标准子目录（与 build_map_vampire_pool.py 同源）
STANDARD_DIRS = [
    "Scenes", "Scripts", "Battle", "Battle/Features", "Battle/Processes", "Battle/Components",
    "Resources", "Resources/Levels", "Resources/LevelCatalogs", "Resources/Maps",
    "Resources/MapCells", "Resources/GameplayLogic", "Resources/GameplayLogic/Waves",
    "Resources/StateMachines", "Resources/StateMachines/Conditions", "Resources/CharacterComponents",
    "Resources/CharacterCombat", "Resources/CharacterCombat/Attacks", "Resources/CharacterCombat/Buffs",
    "Resources/CharacterCombat/Events",
    "Resources/CharacterData", "Resources/CharacterData/Armor", "Resources/CharacterData/Custom",
    "Resources/CharacterData/DamagePoints", "Resources/BuffVisuals", "Resources/CollisionGeometry",
    "Resources/AwardSettlements", "Resources/UnlockConditions", "Resources/PacketEvents",
    "Resources/PacketSpawnEntries",
    "Resources/PacketSpawnEntries/Level", "Resources/PacketSpawnEntries/Conveyor",
    "Resources/PacketSpawnEntries/Rain", "Resources/ConveyorEvents", "Resources/ToolEvents",
    "Resources/Cards", "Resources/CardCostRules", "Resources/CardOverrides", "Resources/PacketBank",
    "Resources/Projectiles",
    "Resources/ProjectileChanges", "Resources/Characters", "Resources/Characters/Plants",
    "Resources/Characters/Zombies", "Resources/Characters/Props", "Resources/Characters/Vases",
    "Resources/Characters/Mowers", "Resources/Characters/Items", "Resources/Characters/Graves",
    "Resources/Characters/Craters",
    "Resources/Collectables", "Resources/DropItems", "Resources/Mowers", "Resources/Shovels",
    "Resources/FallingObjects", "Resources/Animations", "Resources/AnimationAtlasProfiles",
    "Resources/BGMConfigs", "Resources/Survivals", "Resources/Tutorials",
    "Resources/Tutorials/Conditions", "Resources/Tutorials/Steps", "Resources/NpcTalks",
    "Resources/Shops", "Resources/Dialogs", "Assets", "Assets/Images", "Assets/Audio",
    "Assets/Audio/Sfx", "Assets/Audio/BGM",
    "Assets/Fonts", "Localization",
]

PROJECT_KEYS = ["Name", "Version", "Author", "Description", "ExportDirectory",
                "GameDirectory", "CreatedDate", "LastModifiedDate"]
MANIFEST_KEYS = ["schemaVersion", "id", "name", "version", "author", "description",
                 "dependencies", "conflicts", "provides", "overrides", "scripts",
                 "runtimeAssembly", "runtimeEntryType", "runtimeApiVersion",
                 "runtimeAssemblyPolicy", "blueprints", "translations", "resources"]
TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{7}[+-]\d{2}:\d{2}$")


def check(proj_dir, pmod):
    # ---------- 1) 目录骨架
    need(len(STANDARD_DIRS) == 72, "layout.count", "标准子目录定义 72 项")
    missing = [d for d in STANDARD_DIRS
               if not os.path.isdir(os.path.join(proj_dir, d.replace("/", os.sep)))]
    need(not missing, "layout.dirs", "72 个标准子目录全部齐备" if not missing
         else "缺少子目录 %d 个: %s" % (len(missing), missing[:5]))

    if os.path.isdir(os.path.join(MODS, "新地图-1")):
        ref, got = set(), set()
        for root, bag in ((os.path.join(MODS, "新地图-1"), ref),
                          (proj_dir, got)):
            for dp, dns, _fns in os.walk(root):
                for d in dns:
                    bag.add(os.path.relpath(os.path.join(dp, d), root).replace("\\", "/"))
        # 本 Mod 额外需要 Runtime/（放托管程序集 ModAssembly.dll）。
        # 新地图-1 是纯数据地图、没有这一层 → 白名单放行；其余任何多余目录仍算 FAIL。
        ALLOWED_EXTRA_DIRS = {"Runtime"}
        extra = sorted(d for d in (got - ref) if d not in ALLOWED_EXTRA_DIRS)
        lack = sorted(ref - got)
        need(not lack, "layout.same", "与游戏侧编辑器 新地图-1 的目录集合一致"
             if not lack else "比 新地图-1 少了目录: %s" % lack)
        need(not extra, "layout.extra",
             "目录集合 == 新地图-1 ∪ {Runtime}（本 Mod 带托管程序集）" if not extra
             else "多出 新地图-1 没有、也不在白名单的目录: %s" % extra)

    # ---------- 2) .pvzmodeproject
    proj_file = os.path.join(proj_dir, MOD_NAME + ".pvzmodeproject")
    need(os.path.isfile(proj_file), "proj.exists", "%s.pvzmodeproject 存在" % MOD_NAME)
    if os.path.isfile(proj_file):
        raw = open(proj_file, "rb").read()
        need(not raw.startswith(b"\xef\xbb\xbf"), "proj.bom", "无 BOM")
        need(b"\r\n" in raw and b"\n" not in raw.replace(b"\r\n", b""),
             "proj.crlf", "换行全部为 CRLF（= Godot 实测产物风格）")
        need(b"\\u" in raw, "proj.escape", "非 ASCII 以 \\uXXXX 转义")
        hexes = re.findall(rb"\\u([0-9A-Fa-f]{4})", raw)
        lower = [h for h in hexes if h != h.upper()]
        need(not lower, "proj.hexcase",
             "转义 HEX 全为大写（共 %d 处，如 %s）" % (len(hexes), hexes[0].decode() if hexes else "-")
             if not lower else "存在小写 HEX 转义: %s" % lower[:4])
        o = json.loads(raw.decode("utf-8"))
        need(list(o.keys()) == PROJECT_KEYS, "proj.keys",
             "键序 == ModProjectSerializeHandler: %s" % list(o.keys()))
        need(o["Name"] == MOD_NAME, "proj.name", "Name == 工程目录名: %s" % o["Name"])
        need(o["ExportDirectory"].replace("\\", "/").rstrip("/") == MODS.replace("\\", "/"),
             "proj.exportdir", "ExportDirectory 指向 %s" % MODS)
        need(o["GameDirectory"] == "", "proj.gamedir", "GameDirectory 为空（同游戏侧）")
        need(TS_RE.match(o["CreatedDate"]) and TS_RE.match(o["LastModifiedDate"]),
             "proj.timefmt", "时间格式 == .NET 'O'（7 位小数 + 冒号时区）: %s" % o["CreatedDate"])

    # ---------- 3) 工程内 mod.json
    proj_manifest = os.path.join(proj_dir, "mod.json")
    need(os.path.isfile(proj_manifest), "manifest.exists", "工程内 mod.json 存在")
    if os.path.isfile(proj_manifest):
        mraw = open(proj_manifest, "rb").read()
        m = json.loads(mraw.decode("utf-8"))
        need(list(m.keys()) == MANIFEST_KEYS, "manifest.keys",
             "18 个键且顺序 == XWModManifestSerializeHandler")
        need(m["schemaVersion"] == 2, "manifest.schema", "schemaVersion=2")
        need(m["id"] == MOD_ID, "manifest.id", "id=%s" % m["id"])
        need(m["name"] == MOD_NAME, "manifest.name", "name=%s" % m["name"])
        need(m["provides"] == {"Map": [MAP_KEY], "Texture": [TEXTURE_KEY]}, "manifest.provides",
             "provides == {Map:[%s], Texture:[%s]}（背景贴图也要声明：一旦 provides 非空，"
             "每个被识别的资源都必须声明，否则被跳过 + 整包判失败）"
             % (MAP_KEY, TEXTURE_KEY))
        need(m["overrides"] == {}, "manifest.overrides", "overrides 为空（新键走 provides）")
        want_res = WANT_RES
        need(m["resources"] == want_res, "manifest.resources",
             "resources == SyncProject 规范序（tres+jpg+dll 三个，OrdinalIgnoreCase 升序）: %s"
             % m["resources"])
        need(m["runtimeAssembly"] == RUNTIME_ASSEMBLY, "manifest.runtime.asm",
             "runtimeAssembly == %s（⚠️ 只认这一个字面量，写别的整包被拒）" % RUNTIME_ASSEMBLY)
        need(m["runtimeEntryType"] == RUNTIME_ENTRY_TYPE, "manifest.runtime.entry",
             "runtimeEntryType == %s" % RUNTIME_ENTRY_TYPE)
        need(m["runtimeApiVersion"] == RUNTIME_API_VERSION, "manifest.runtime.api",
             "runtimeApiVersion == %d（必须恰好 1，否则运行入口被拒、整包回滚）"
             % RUNTIME_API_VERSION)
        need(m["runtimeAssemblyPolicy"] == RUNTIME_POLICY, "manifest.runtime.policy",
             "runtimeAssemblyPolicy == %s（程序集加载失败不连坐整包）" % RUNTIME_POLICY)
        # XWModManifestSyncService 会不会把它改回去？resources 集合必须已经 == 排序后的自身
        scanned = sorted(m["resources"], key=lambda p: p.lower())
        need(scanned == m["resources"], "manifest.sync",
             "resources 已是 SyncProject 规范序 → 编辑器打开时不会重写 mod.json")

    # ---------- 4) tres / 贴图 / DLL 三份都在工程目录里
    in_proj = os.path.join(proj_dir, "Resources", "Maps", MAP_KEY + ".tres")
    need(os.path.isfile(in_proj), "tres.exists", "工程内 Resources/Maps/%s.tres 存在" % MAP_KEY)

    in_tex = os.path.join(proj_dir, TEXTURE_REL.replace("/", os.sep))
    need(os.path.isfile(in_tex), "texture.exists", "工程内 %s 存在" % TEXTURE_REL)

    rt_dir = os.path.dirname(os.path.join(proj_dir, RUNTIME_ASSEMBLY.replace("/", os.sep)))
    in_dll = os.path.join(proj_dir, RUNTIME_ASSEMBLY.replace("/", os.sep))
    need(os.path.isfile(in_dll), "runtime.exists", "工程内 %s 存在" % RUNTIME_ASSEMBLY)
    if os.path.isdir(rt_dir):
        only = sorted(os.listdir(rt_dir))
        need(only == ["ModAssembly.dll"], "runtime.only",
             "Runtime/ 下只有 ModAssembly.dll（不带 .pdb/.deps.json）: %s" % only)

    # ---------- 5) enabled_mods.json
    en = os.path.join(MODS, "enabled_mods.json")
    if os.path.isfile(en):
        ids = json.loads(io.open(en, encoding="utf-8").read())
        need(isinstance(ids, list) and any(
            str(i).strip().lower() == MOD_ID for i in ids), "enable.listed",
            "enabled_mods.json 含 %s（%s）" % (MOD_ID, ids))
    else:
        need(False, "enable.listed",
             "缺少 enabled_mods.json → LoadEnabledIds() 返回空 → 所有 mod 都不会加载")

    # ---------- 6) .pmod
    if os.path.isfile(pmod):
        with zipfile.ZipFile(pmod) as z:
            names = z.namelist()
            need(names[0] == "mod.json", "pmod.order", "mod.json 是第 0 个条目")
            need(not [n for n in names if n.endswith(".pvzmodeproject")], "pmod.noproj",
                 "工程文件没有被打进包（打进会触发 InferRuntimeEntry 未归类告警）")
            need(RESOURCE_TRES in names, "pmod.tres", "包内含地图资源")
            need(TEXTURE_REL in names, "pmod.texture", "包内含背景贴图 %s" % TEXTURE_REL)
            need(RUNTIME_ASSEMBLY in names, "pmod.runtime",
                 "包内含托管程序集 %s" % RUNTIME_ASSEMBLY)
            # 打包只该有「mod.json + 声明的 resources」，别的都算漏进来
            want_names = {"mod.json"} | set(WANT_RES)
            stray = sorted(set(names) - want_names)
            need(not stray, "pmod.exact",
                 "包内条目 == mod.json + 声明的 resources（%d 条）" % len(names)
                 if not stray else "包内多出未声明条目: %s" % stray)
            pm = json.loads(z.read("mod.json").decode("utf-8"))
            need(pm == json.loads(open(proj_manifest, encoding="utf-8").read())
                 if os.path.isfile(proj_manifest) else False, "pmod.samemanifest",
                 "包内 mod.json 与工程内 mod.json 语义一致")
            praw = z.read(RESOURCE_TRES)
        if os.path.isfile(in_proj):
            need(open(in_proj, "rb").read() == praw, "pmod.sametres",
                 "包内 tres 与工程内 tres 字节一致")
    else:
        need(False, "pmod.exists", "找不到安装包: %s" % pmod)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    proj = args[0] if args else os.path.join(MODS, MOD_NAME)
    pmod = args[1] if len(args) > 1 else os.path.join(MODS, MOD_NAME + ".pmod")
    print("=" * 74)
    print("校验 Mod 工程目录:", proj)
    print("校验安装包       :", pmod)
    check(proj, pmod)
    n_ok = n_warn = n_bad = 0
    for it in ITEMS:
        tag = {OK: "  ok  ", WARN: " warn ", BAD: " FAIL "}[it["level"]]
        print("%s [%s] %s" % (tag, it["code"], it["msg"]))
        n_ok += it["level"] == OK
        n_warn += it["level"] == WARN
        n_bad += it["level"] == BAD
    print("-" * 74)
    print("结果: ok=%d  warn=%d  FAIL=%d   ->  %s"
          % (n_ok, n_warn, n_bad, "不通过" if n_bad else "通过"))
    if n_bad:
        sys.exit(1)


if __name__ == "__main__":
    main()
