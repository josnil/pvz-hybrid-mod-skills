# -*- coding: utf-8 -*-
"""
verify_pmod.py —— 离线校验 .pmod，复刻 ModLoader 的加载规则

对照源码：
  addons/ModEditor/ModSystem/ModLoader.cs
    - ValidatePackageArchive / TryReadPackageMetadata   包结构与 root mod.json
    - ValidateArchiveEntryPath                          条目路径安全
    - InferRuntimeEntry                                 路径 -> (category, key)
    - ApplyMod                                          歧义键 / 可执行文件 / 声明匹配
  addons/ModEditor/ModSystem/XWModRuntimeCompatibility.cs
  addons/ModEditor/ModSystem/XWModRuntimeRegistry.cs    overrides 目标必须已存在

离线无法覆盖的部分（需要游戏进程内注册表）会明确标为「待游戏内确认」。

用法：
    python verify_pmod.py dist/PeaOverhaul.pmod
    python verify_pmod.py dist/PeaOverhaul.pmod --json report.json
"""

import io
import json
import os
import posixpath
import sys
import zipfile

UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
ROOT_MANIFEST = "mod.json"
MAX_MANIFEST_BYTES = 1024 * 1024

# InferRuntimeEntry 的路径前缀表（源码里的 17 项 + 媒体项）
PREFIX_TABLE = [
    ("Battle/Features/", "Feature"),
    ("Battle/Processes/", "Process"),
    ("Resources/LevelCatalogs/", "Level"),
    ("Resources/Maps/", "Map"),
    ("Resources/Cards/", "Packet"),
    ("Resources/PacketBank/", "PacketBank"),
    ("Resources/Projectiles/", "Projectile"),
    ("Resources/ProjectileChanges/", "ProjectileChange"),
    ("Resources/Collectables/", "Collectable"),
    ("Resources/Mowers/", "Mower"),
    ("Resources/Shovels/", "Shovel"),
    ("Resources/Survivals/", "Survival"),
    ("Resources/Tutorials/", "Tutorial"),
    ("Resources/NpcTalks/", "NpcTalk"),
    ("Resources/Shops/", "Shop"),
    ("Resources/AnimationAtlasProfiles/", "AnimationAtlas"),
    ("Resources/BGMConfigs/", "BGM"),
]

TEXTURE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".tga"}
AUDIO_EXT = {".wav", ".ogg", ".mp3", ".flac"}
RESOURCE_EXT = {".tres", ".res"}
EXECUTABLE_EXT = {".dll", ".exe", ".so", ".dylib", ".pdb"}

# category -> 离线可核对的注册表 JSON（来自 ResourceManager 的 LoadResourceDictionary 调用）
REGISTRY_JSON = {
    "Projectile": "Asset/Config/Projectile/ProjectileResource.json",
    "Map": "Asset/Config/Map/MapResource.json",
    "Audio": "Asset/Config/Audio/AudioResource.json",
    "NpcTalk": "Asset/Config/Npc/TalkResource.json",
    "Tutorial": "Asset/Config/Tutorial/TutorialResource.json",
    "Collectable": "Asset/Config/Collectable/CollectableResource.json",
    "Shovel": "Asset/Config/Shovel/ShovelResource.json",
    "Mower": "Asset/Config/Mower/MowerResource.json",
    "Shop": "Asset/Config/Shop/ShopResource.json",
    "Survival": "Asset/Config/Survival/SurvivalResource.json",
    "BGM": "Asset/Config/BGM/BGMResource.json",
    "Character": "Asset/Config/Character/CharacterResource.json",
    "Level": "Asset/Config/Level/LevelResource.json",
    "PacketBank": "Asset/Config/PacketBank/PacketBankResource.json",
}

OK, WARN, BAD = "OK", "WARN", "FAIL"


class Report(object):
    def __init__(self):
        self.items = []

    def add(self, level, code, msg):
        self.items.append({"level": level, "code": code, "msg": msg})

    def has_fail(self):
        return any(i["level"] == BAD for i in self.items)


def infer_runtime_entry(rel):
    """移植 ModLoader.InferRuntimeEntry。返回 (category, key) 或 (\"\", \"\")。"""
    p = (rel or "").replace("\\", "/").strip("/")
    ext = posixpath.splitext(p)[1].lower()

    if p.lower().startswith("assets/audio/") and ext in AUDIO_EXT:
        return "Audio", posixpath.splitext(posixpath.basename(p))[0]
    for pre in ("assets/textures/", "assets/texture/", "assets/images/"):
        if p.lower().startswith(pre) and ext in TEXTURE_EXT:
            return "Texture", posixpath.splitext(posixpath.basename(p))[0]

    # TryInferCharacterScene(text) -> Resources/Characters/.../Scene/xxx.tscn
    parts = p.split("/")
    if len(parts) >= 2 and parts[-2] == "Scene" and parts[-1].endswith(".tscn"):
        return "Character", posixpath.splitext(parts[-1])[0]
    if len(parts) >= 2 and parts[-2] == "Sprite" and parts[-1].endswith(".tscn"):
        return "CharacterSprite", posixpath.splitext(parts[-1])[0]

    if ext not in RESOURCE_EXT:
        return "", ""
    low = p.lower()
    if low.startswith("resources/tutorials/conditions/") or low.startswith("resources/tutorials/steps/"):
        return "", ""

    for pre, cat in PREFIX_TABLE:
        if low.startswith(pre.lower()):
            return cat, posixpath.splitext(posixpath.basename(p))[0]
    return "", ""


def safe_entry_path(entry):
    """移植 ModLoader.ValidateArchiveEntryPath 的路径安全判定。"""
    if not entry or entry.endswith("/"):
        return "目录条目"
    norm = entry.replace("\\", "/")
    if norm.startswith("/"):
        return "绝对路径"
    if len(norm) > 1 and norm[1] == ":":
        return "带盘符的绝对路径"
    parts = norm.split("/")
    if any(seg == ".." for seg in parts):
        return "包含 .. 越界段"
    if norm != posixpath.normpath(norm):
        return "路径未规范化"
    return None


def load_registry_keys(category):
    """离线读取该类别的合法 key 集合。None = 离线无法核对。"""
    rel = None
    for k, v in REGISTRY_JSON.items():
        if k.lower() == str(category).lower():
            rel = v
            break
    if not rel:
        return None
    path = os.path.join(UNPACK, rel.replace("/", os.sep))
    if not os.path.exists(path):
        return None
    with io.open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return set(data.keys())
    return None


def verify(pmod_path):
    rep = Report()
    name = os.path.basename(pmod_path)

    if not os.path.exists(pmod_path):
        rep.add(BAD, "package.missing", "包不存在: %s" % pmod_path)
        return rep

    try:
        zf = zipfile.ZipFile(pmod_path)
    except Exception as e:
        rep.add(BAD, "package.unreadable", "无法作为 zip 打开: %s" % e)
        return rep

    names = zf.namelist()
    rep.add(OK, "package.readable", "zip 可读，%d 个条目，%d 字节"
            % (len(names), os.path.getsize(pmod_path)))

    # 1) 根 mod.json 唯一
    root_manifests = [n for n in names
                      if n.replace("\\", "/").strip("/").lower() == ROOT_MANIFEST]
    if len(root_manifests) != 1:
        rep.add(BAD, "manifest.count",
                "根 mod.json 必须正好 1 个，实际 %d 个" % len(root_manifests))
        return rep
    if names[0] != root_manifests[0]:
        rep.add(WARN, "manifest.order",
                "mod.json 不是第一个条目（官方导出器会写在第 0 位）")
    else:
        rep.add(OK, "manifest.order", "mod.json 位于第 0 个条目")
    rep.add(OK, "manifest.count", "根 mod.json 唯一: %s" % root_manifests[0])

    # 2) 大小限制
    info = zf.getinfo(root_manifests[0])
    if info.file_size > MAX_MANIFEST_BYTES:
        rep.add(BAD, "manifest.size", "mod.json 超过 1 MiB 限制: %d" % info.file_size)
    else:
        rep.add(OK, "manifest.size", "mod.json %d 字节（限 1 MiB）" % info.file_size)

    # 3) 清单解析
    raw = zf.read(root_manifests[0]).decode("utf-8-sig")
    try:
        mf = json.loads(raw)
    except Exception as e:
        rep.add(BAD, "manifest.json", "mod.json 不是合法 JSON: %s" % e)
        return rep

    schema = mf.get("schemaVersion", 0)
    if schema not in (1, 2):
        rep.add(BAD, "manifest.schema", "schemaVersion 必须为 1 或 2，实际 %r" % schema)
    else:
        rep.add(OK, "manifest.schema", "schemaVersion=%d" % schema)

    for fld in ("id", "name", "version"):
        v = mf.get(fld) or ""
        if not str(v).strip():
            rep.add(WARN, "manifest.field", "%s 为空（ModLoader 会回退到文件名）" % fld)
    rep.add(OK, "manifest.identity",
            "id=%s name=%s version=%s author=%s"
            % (mf.get("id"), mf.get("name"), mf.get("version"), mf.get("author")))

    # 4) 托管代码声明一致性（XWModRuntimeCompatibility.ValidatePackage）
    asm = (mf.get("runtimeAssembly") or "").strip()
    entry = (mf.get("runtimeEntryType") or "").strip()
    policy = (mf.get("runtimeAssemblyPolicy") or "").strip().lower()
    if asm or entry:
        if schema != 2 or mf.get("runtimeApiVersion") != 1:
            rep.add(BAD, "managed.api",
                    "声明托管代码时需 schemaVersion=2 且 runtimeApiVersion=1")
        if entry and not asm:
            rep.add(BAD, "managed.assembly", "声明了 runtimeEntryType 但没有 runtimeAssembly")
        if asm and policy not in ("required", "optional"):
            rep.add(BAD, "managed.policy",
                    "runtimeAssemblyPolicy 必须是 required|optional，实际 %r" % policy)
        rep.add(OK, "managed.declared", "含托管程序集: %s" % asm)
    else:
        rep.add(OK, "managed.declared", "纯资源 Mod，无托管代码（ValidatePackage 直接通过）")

    # 5) 自依赖 / 依赖环
    deps = [d.get("id") for d in (mf.get("dependencies") or []) if isinstance(d, dict)]
    if mf.get("id") in deps:
        rep.add(BAD, "deps.self", "Mod 依赖了自身: %s" % mf.get("id"))
    else:
        rep.add(OK, "deps.self", "无自依赖" if deps else "无依赖")

    # 6) 条目逐个检查
    declared_over = mf.get("overrides") or {}
    declared_pro = mf.get("provides") or {}
    declared_any = set()
    for cat, keys in list(declared_over.items()) + list(declared_pro.items()):
        for k in keys or []:
            declared_any.add((cat.lower(), str(k).lower()))

    candidates = {}       # (cat, key) -> [entry...]
    unsupported = []
    for n in names:
        if n == root_manifests[0]:
            continue
        bad = safe_entry_path(n)
        if bad:
            rep.add(BAD, "entry.unsafe", "条目路径不安全（%s）: %s" % (bad, n))
            continue
        ext = posixpath.splitext(n)[1].lower()
        if ext in EXECUTABLE_EXT:
            rel = n.replace("\\", "/")
            if not (rel == "Runtime/ModAssembly.dll"
                    or rel.startswith("Runtime/Dependencies/")
                    or rel in ("Runtime/ModAssembly.pdb",)):
                rep.add(BAD, "entry.executable",
                        "未声明的可执行条目会被拦截: %s" % n)
            continue
        cat, key = infer_runtime_entry(n)
        if not cat:
            unsupported.append(n)
            continue
        candidates.setdefault((cat, key), []).append(n)

    if not unsupported:
        rep.add(OK, "entry.supported", "全部条目都能被 InferRuntimeEntry 归类")
    else:
        for n in unsupported:
            rep.add(WARN, "entry.unsupported",
                    "无法归类，ApplyMod 会记 unsupported package file: %s" % n)

    # 7) 歧义键
    for (cat, key), lst in candidates.items():
        if len(lst) > 1:
            rep.add(BAD, "entry.ambiguous",
                    "同一 category/key 出现多份: %s/%s -> %s" % (cat, key, lst))
    if candidates:
        rep.add(OK, "entry.unique", "%d 个 (category,key) 映射唯一" % len(candidates))

    # 8) 资源文件必须被 manifest 声明（HasExplicitRuntimeEntries 为真时）
    has_explicit = any((v or []) for v in declared_over.values()) or \
                   any((v or []) for v in declared_pro.values())
    for (cat, key) in sorted(candidates):
        if has_explicit and (cat.lower(), key.lower()) not in declared_any:
            rep.add(BAD, "binding.undeclared",
                    "资源存在但 manifest 未声明 provides/overrides: %s/%s" % (cat, key))

    # 9) 声明了 override 但没有对应文件 / 键不存在
    for cat, keys in (declared_over or {}).items():
        known = load_registry_keys(cat)
        for k in keys or []:
            has_file = any(c.lower() == cat.lower() and kk.lower() == str(k).lower()
                           for (c, kk) in candidates)
            if not has_file:
                rep.add(BAD, "override.no_file",
                        "声明 overrides 但没有对应资源文件: %s/%s" % (cat, k))
            if known is None:
                rep.add(WARN, "override.unchecked",
                        "overrides %s/%s 的键存在性需游戏内确认（离线无该注册表）" % (cat, k))
            elif str(k) not in known:
                rep.add(BAD, "override.missing",
                        "overrides 目标不存在，ModLoader 会拒绝: %s/%s" % (cat, k))
            else:
                rep.add(OK, "override.exists",
                        "overrides 目标存在: %s/%s" % (cat, k))

    for cat, keys in (declared_pro or {}).items():
        known = load_registry_keys(cat)
        for k in keys or []:
            if known is None:
                rep.add(WARN, "provide.unchecked",
                        "provides %s/%s：离线无该注册表，需游戏内确认不与内置冲突" % (cat, k))
            elif str(k) in known:
                # XWModRuntimeRegistry.TrySetRuntimeValue：provides 是「新增」，
                # 键已存在会直接抛错 -> 必须改成 overrides。
                rep.add(BAD, "provide.exists",
                        "provides 的键已存在（应改用 overrides）: %s/%s" % (cat, k))
            else:
                rep.add(OK, "provide.new", "provides 目标为新键: %s/%s" % (cat, k))

    # 10) 覆盖资源自身的内容体检
    for (cat, key), lst in sorted(candidates.items()):
        for n in lst:
            if posixpath.splitext(n)[1].lower() not in RESOURCE_EXT:
                continue
            text = zf.read(n).decode("utf-8-sig", errors="replace")
            head = text.split("\n", 1)[0]
            if "uid=\"uid://" in head:
                rep.add(WARN, "tres.uid",
                        "覆盖资源仍带原版 uid，可能与内置资源 UID 冲突: %s" % n)
            else:
                rep.add(OK, "tres.uid", "%s 已剥离自身 uid，无 UID 冲突" % n)
            if "script_class=" not in head:
                rep.add(WARN, "tres.class", "%s 头部缺 script_class，类型推断可能失败" % n)
            refs = [ln for ln in text.split("\n")
                    if ln.startswith("[ext_resource") and 'path="res://' in ln]
            rep.add(OK, "tres.refs",
                    "%s 引用 %d 个内置 res:// 资源（需存在于正式版）" % (n, len(refs)))

    return rep


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_json = None
    if "--json" in sys.argv:
        out_json = sys.argv[sys.argv.index("--json") + 1]

    if not args:
        here = os.path.dirname(os.path.abspath(__file__))
        args = [os.path.join(here, "dist", "PeaOverhaul.pmod")]

    for pmod in args:
        print("=" * 72)
        print("校验:", pmod)
        rep = verify(pmod)
        n_ok = n_warn = n_bad = 0
        for it in rep.items:
            tag = {OK: "  ok  ", WARN: " warn ", BAD: " FAIL "}[it["level"]]
            print("%s [%s] %s" % (tag, it["code"], it["msg"]))
            n_ok += it["level"] == OK
            n_warn += it["level"] == WARN
            n_bad += it["level"] == BAD
        print("-" * 72)
        print("结果: ok=%d  warn=%d  FAIL=%d   ->  %s"
              % (n_ok, n_warn, n_bad, "不通过" if n_bad else "通过"))
        if out_json:
            with io.open(out_json, "w", encoding="utf-8") as f:
                json.dump(rep.items, f, ensure_ascii=False, indent=2)
            print("报告: %s" % out_json)
        if n_bad:
            sys.exit(1)


if __name__ == "__main__":
    main()
