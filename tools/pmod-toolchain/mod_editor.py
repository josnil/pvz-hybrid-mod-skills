# -*- coding: utf-8 -*-
"""
mod_editor.py —— 《植物大战僵尸杂交版》独立 Mod 编辑器（游戏外运行）

为什么需要它：
  游戏内置的「PVZ Mod 编辑器」是游戏内 GUI（F3），只能手点、无法脚本化。
  本工具把同一套 .pmod 格式搬到外面来，浏览器点鼠标 / 脚本改 JSON 都行。

它能自动推导：
  注册表 JSON  ->  该类别的真实键名（overrides 只能用真实存在的键）
  键 -> uid -> 原版 .tres 文件
    .tres -> C# 配置类 -> [Export] 字段表（带类型/默认值/分组/枚举/范围）

用法：
    python mod_editor.py                    # 启动编辑器，自动开浏览器
    python mod_editor.py --port 8765
    python mod_editor.py --build            # 不开服务，直接按工程文件构建
    python mod_editor.py --build --project mod_project.json

设计要点：
  * 覆盖资源一律「以原版 .tres 为基底 + 补丁」，未改动的字段（含复杂引用）原样保留
  * 生成 .tres 时剥掉 [gd_resource] 行自身的 uid，避免与内置资源 UID 冲突
  * 构建后自动跑离线校验（复用 verify_pmod 的规则）
"""

import argparse
import base64
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import sys
import threading
import webbrowser
import zipfile
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---------------------------------------------------------------- 路径配置

DEF_UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
UNPACK = os.environ.get("PVZHE_UNPACK", DEF_UNPACK)

PROJECT_FILE = os.path.join(HERE, "mod_project.json")
DIST_DIR = os.path.join(HERE, "dist")
CACHE_DIR = os.path.join(HERE, ".cache")
UI_FILE = os.path.join(HERE, "mod_editor_ui.html")

USER_MODS_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "Godot", "app_userdata", "植物大战僵尸杂交版", "Mods",
)

# ------------------------------------------------- 类别定义（全部来自源码逆向）

# out: 包内输出目录，对应 ModLoader.InferRuntimeEntry 的路径前缀
# reg: Asset/Config 下的注册表 JSON（键名真相来源）
# src: 原版 .tres 所在目录（扫描用）
CATEGORIES = {
    "Projectile": {
        "label": "子弹", "out": "Resources/Projectiles",
        "reg": "Asset/Config/Projectile/ProjectileResource.json",
        "src": ["Asset/Config/Projectile"],
        "desc": "豌豆 / 西瓜 / 星星等所有弹道。改伤害、穿透、缩放、命中效果。",
    },
    "Map": {
        "label": "地图", "out": "Resources/Maps",
        "reg": "Asset/Config/Map/MapResource.json",
        "src": ["Asset/Config/Map"],
        "desc": "关卡的场地布局与地形。",
    },
    "Collectable": {
        "label": "收集物", "out": "Resources/Collectables",
        "reg": "Asset/Config/Collectable/CollectableResource.json",
        "src": ["Asset/Config/Collectable"],
        "desc": "掉落的收集物 / 图鉴物。",
    },
    "Shovel": {
        "label": "铲子", "out": "Resources/Shovels",
        "reg": "Asset/Config/Shovel/ShovelResource.json",
        "src": ["Asset/Config/Shovel"],
        "desc": "各种铲子及其触发事件。",
    },
    "Mower": {
        "label": "小推车", "out": "Resources/Mowers",
        "reg": "Asset/Config/Mower/MowerResource.json",
        "src": ["Asset/Config/Mower"],
        "desc": "割草机 / 小推车。",
    },
    "Shop": {
        "label": "商店", "out": "Resources/Shops",
        "reg": "Asset/Config/Shop/ShopResource.json",
        "src": ["Asset/Config/Shop"],
        "desc": "商店页面与商品配置。",
    },
    "Survival": {
        "label": "生存模式", "out": "Resources/Survivals",
        "reg": "Asset/Config/Survival/SurvivalResource.json",
        "src": ["Asset/Config/Survival"],
        "desc": "生存模式的波次与难度。",
    },
    "Tutorial": {
        "label": "教程流程", "out": "Resources/Tutorials",
        "reg": "Asset/Config/Tutorial/TutorialResource.json",
        "src": ["Asset/Config/Tutorial"],
        "desc": "新手教程的步骤与条件。",
    },
    "NpcTalk": {
        "label": "NPC 对话", "out": "Resources/NpcTalks",
        "reg": "Asset/Config/Npc/TalkResource.json",
        "src": ["Asset/Config/Npc"],
        "desc": "关卡内 NPC 对话。",
    },
    "BGM": {
        "label": "背景音乐", "out": "Resources/BGMConfigs",
        "reg": "Asset/Config/BGM/BGMResource.json",
        "src": ["Asset/Config/BGM"],
        "desc": "BGM 配置（多为音频文件替换型）。",
    },
    "Audio": {
        "label": "音效", "out": "Assets/Audio",
        "reg": "Asset/Config/Audio/AudioResource.json",
        "src": ["Asset/Config/Audio"],
        "desc": "音效（音频文件替换型）。",
    },
    "ProjectileChange": {
        "label": "子弹变化", "out": "Resources/ProjectileChanges",
        "reg": None,
        "src": ["Asset/Config/ProjectileChange"],
        "desc": "子弹命中/飞行途中的变形规则（无独立注册表，键名按文件名）。",
    },
}

# 结构复杂、需要专门 UI 的类别（明确不支持，而不是静默出错）
ADVANCED_CATEGORIES = {
    "Level": "关卡注册表是深嵌套结构（章节→关卡→难度→uid），且官方用专门的关卡编辑器维护，本工具暂不做可视化编辑。",
    "PacketBank": "卡包注册表是深嵌套结构（Include + Category 分组），暂不做可视化编辑。",
    "Character": "角色是「文件夹包」（Resources/Characters/<类>/<名>/Scene|Sprite/*.tscn + 配置），需要场景与脚本，不是单文件覆盖。",
    "AnimationAtlas": "动画图集涉及 .dat / 图集页 / 姿态数组，需配套二进制资源，暂不支持。",
    "Feature": "战斗 Feature 是 C# 类实例（Battle/Features/*.tres 引脚本），需谨慎验证，暂不开放。",
    "Process": "同上，战斗 Process 暂不开放。",
    "Texture": "纹理走 Assets/Textures/ 文件名键，需逐个核对游戏内引用点，暂无可靠键表。",
}

# ---------------------------------------------------------------- 基础工具


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read().replace("\r\n", "\n").replace("\r", "\n")


def write_text(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def rel_under(root, path):
    return os.path.relpath(path, root).replace("\\", "/")


def ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(DIST_DIR, exist_ok=True)


# ---------------------------------------------------------------- uid 索引

_UID_INDEX = None
_UID_LOCK = threading.Lock()


def build_uid_index(force=False):
    """扫描工程内所有 .tres/.res 的头部 uid，建 uid -> 绝对路径 索引（带磁盘缓存）。"""
    global _UID_INDEX
    with _UID_LOCK:
        if _UID_INDEX is not None and not force:
            return _UID_INDEX

        cache_file = os.path.join(CACHE_DIR, "uid_index.json")
        if not force and os.path.exists(cache_file):
            try:
                with io.open(cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("unpack") == UNPACK and data.get("v") == 2 and \
                        isinstance(data.get("index"), dict):
                    _UID_INDEX = data["index"]
                    return _UID_INDEX
            except Exception:
                pass

        index = {}
        for dirpath, dirnames, filenames in os.walk(UNPACK):
            dirnames[:] = [d for d in dirnames
                           if d not in (".godot", ".autoconverted", "Icons", "docs")]
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                low = fn.lower()
                try:
                    if low.endswith((".tres", ".res", ".tscn")):
                        with io.open(full, "r", encoding="utf-8-sig", errors="replace") as f:
                            head = f.readline()
                        m = re.search(r'uid="(uid://[^"]+)"', head)
                        if m:
                            index[m.group(1)] = full
                    elif low.endswith(".import"):
                        # 音频 / 纹理等：uid 在 .import 里，source_file 才是真身
                        with io.open(full, "r", encoding="utf-8-sig", errors="replace") as f:
                            body = f.read(4096)
                        mu = re.search(r'uid="(uid://[^"]+)"', body)
                        ms = re.search(r'source_file="res://([^"]+)"', body)
                        if mu and ms:
                            index[mu.group(1)] = os.path.join(
                                UNPACK, ms.group(1).replace("/", os.sep))
                except Exception:
                    continue

        try:
            ensure_cache_dir()
            with io.open(cache_file, "w", encoding="utf-8") as f:
                json.dump({"unpack": UNPACK, "v": 2, "index": index},
                          f, ensure_ascii=False)
        except Exception:
            pass

        _UID_INDEX = index
        return index


def resolve_uid(uid):
    if not uid:
        return None
    return build_uid_index().get(uid)


# ---------------------------------------------------------------- 注册表


_REG_CACHE = {}


def load_registry(cat):
    """返回 (keys_dict, note)。值为 uid 字符串时进入 keys_dict。带内存缓存。"""
    if cat in _REG_CACHE:
        return _REG_CACHE[cat]
    cfg = CATEGORIES.get(cat)
    if not cfg:
        return {}, "未知类别"
    if not cfg.get("reg"):
        # 无注册表：按源目录里的 .tres 文件名当键
        out = {}
        for d in cfg["src"]:
            base = os.path.join(UNPACK, d.replace("/", os.sep))
            for dp, _, fns in os.walk(base):
                for fn in fns:
                    if fn.endswith(".tres"):
                        out.setdefault(os.path.splitext(fn)[0],
                                       "file:" + rel_under(UNPACK, os.path.join(dp, fn)))
        res = (out, "按文件名推断键（该类别无注册表）")
        _REG_CACHE[cat] = res
        return res

    path = os.path.join(UNPACK, cfg["reg"].replace("/", os.sep))
    if not os.path.exists(path):
        return {}, "注册表不存在: %s" % cfg["reg"]
    with io.open(path, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    out = {}
    nested = 0
    for k, v in data.items():
        if isinstance(v, str):
            out[k] = v
        else:
            nested += 1
    note = ""
    if nested:
        note = "（%d 个键是嵌套结构，本工具只列出可单文件覆盖的 %d 个）" % (nested, len(out))
    _REG_CACHE[cat] = (out, note)
    return out, note


def category_list():
    items = []
    for cat, cfg in CATEGORIES.items():
        items.append({"id": cat, "label": cfg["label"], "out": cfg["out"],
                      "desc": cfg["desc"], "supported": True})
    for cat, why in ADVANCED_CATEGORIES.items():
        items.append({"id": cat, "label": cat, "out": None,
                      "desc": why, "supported": False})
    return items


# ---------------------------------------------------------------- .tres 解析


def _balanced_tail(s):
    """判断一行属性的括号是否已闭合（用于多行值续行）。"""
    depth = 0
    in_str = False
    esc = False
    for ch in s:
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
    return depth <= 0


def parse_tres(text):
    """把 .tres 解析成结构，复杂值按原样字符串保留。"""
    lines = text.split("\n")
    res = {
        "header": "",
        "header_attrs": {},
        "ext_resources": [],   # (raw, attrs)
        "sub_blocks": [],      # raw 行数组
        "props": [],           # (name, raw_value)
    }
    i = 0
    n = len(lines)
    while i < n and not lines[i].startswith("[gd_resource"):
        i += 1
    if i < n:
        res["header"] = lines[i]
        for m in re.finditer(r'(\w+)="([^"]*)"', lines[i]):
            res["header_attrs"][m.group(1)] = m.group(2)
        i += 1

    while i < n:
        line = lines[i]
        if line.startswith("[ext_resource"):
            attrs = dict(re.findall(r'(\w+)="([^"]*)"', line))
            res["ext_resources"].append((line, attrs))
            i += 1
            continue
        if line.startswith("[sub_resource"):
            block = [line]
            i += 1
            while i < n and not lines[i].startswith("[") and \
                    not lines[i].strip().startswith("[resource]"):
                block.append(lines[i])
                i += 1
            while block and block[-1].strip() == "":
                block.pop()
            res["sub_blocks"].append(block)
            continue
        if line.strip().startswith("[resource]"):
            i += 1
            while i < n and not lines[i].startswith("["):
                cur = lines[i]
                if "=" in cur and cur.strip() and not cur.strip().startswith(";"):
                    name = cur.split("=", 1)[0].strip()
                    value = cur.split("=", 1)[1].strip()
                    j = i + 1
                    while not _balanced_tail(value) and j < n:
                        value += "\n" + lines[j]
                        j += 1
                    res["props"].append((name, value))
                    i = j
                    continue
                i += 1
            continue
        i += 1
    return res


def strip_header_uid(header):
    if ' uid="' not in header:
        return header
    head, tail = header.split(' uid="', 1)
    close = tail.find('"')
    rest = tail[close + 1:].strip()
    head = head.rstrip()
    if rest.startswith("]"):
        return head + rest
    return head + " " + rest


def serialize_tres(parsed, edits=None, unset=None):
    """按「基底 + 补丁」重建 .tres 文本。edits: {name: raw_literal}"""
    edits = dict(edits or {})
    unset = set(unset or [])
    out = [strip_header_uid(parsed["header"]), ""]
    for raw, _ in parsed["ext_resources"]:
        out.append(raw)
    out.append("")
    for block in parsed["sub_blocks"]:
        out.extend(block)
        out.append("")
    out.append("[resource]")
    seen = set()
    for name, value in parsed["props"]:
        if name in unset:
            continue
        if name in edits:
            out.append("%s = %s" % (name, edits[name]))
            seen.add(name)
        else:
            out.append("%s = %s" % (name, value))
    for name, value in edits.items():
        if name not in seen:
            out.append("%s = %s" % (name, value))
    return "\n".join(out).rstrip("\n") + "\n"


# ---------------------------------------------------------------- C# 字段表

_EXPORT_LINE = re.compile(r"^\[Export(?:\((.*)\))?\]\s*$")
_FIELD_LINE = re.compile(r"^public\s+(.+?)\s+(\w+)\s*(?:=\s*(.*?))?;\s*$")
_GROUP_LINE = re.compile(r'^\[Export(?:Group|Category)\(\s*"([^"]*)"')

# 可以在编辑器里安全改写的类型
SCALAR_TYPES = {"bool", "double", "float", "int", "long", "uint", "ulong",
                "string", "StringName", "Vector2", "Vector2I", "Color"}


def _split_args(s):
    parts, depth, buf, in_str = [], 0, "", False
    for ch in s:
        if ch == '"':
            in_str = not in_str
            buf += ch
            continue
        if not in_str:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
            elif ch == "," and depth == 0:
                parts.append(buf)
                buf = ""
                continue
        buf += ch
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts]


def parse_cs_fields(cs_path):
    """从 C# 配置类里抽出 [Export] 字段（类型 / 默认值 / 分组 / 枚举 / 范围）。"""
    if not cs_path or not os.path.exists(cs_path):
        return []
    src = read_text(cs_path)
    lines = src.split("\n")
    fields = []
    group = "常规"
    pending = None

    for raw in lines:
        line = raw.strip()
        gm = _GROUP_LINE.match(line)
        if gm:
            group = gm.group(1) or "常规"
            pending = None
            continue
        if line == "[Export]":
            pending = {"hint": "", "hint_string": ""}
            continue
        em = _EXPORT_LINE.match(line)
        if em:
            inner = em.group(1) or ""
            args = _split_args(inner) if inner else []
            pending = {
                "hint": args[0] if args else "",
                "hint_string": (args[1].strip('"') if len(args) > 1 else ""),
            }
            continue
        if pending is not None:
            fm = _FIELD_LINE.match(line)
            if fm:
                ftype = fm.group(1).strip()
                fname = fm.group(2)
                default = (fm.group(3) or "").strip()
                if fname.startswith("_"):
                    pending = None
                    continue
                kind, extra = classify_field(ftype, pending)
                fields.append({
                    "name": fname, "csharpType": ftype, "kind": kind,
                    "default": default, "group": group,
                    "hint": pending["hint"], "hintString": pending["hint_string"],
                    **extra
                })
                pending = None
            elif line.startswith("[") or line.startswith("}") or line.startswith("//"):
                pending = None
            continue

    # 去重（同名取首条，与 Godot ka()/PROPS_ALL 行为一致）
    seen, uniq = set(), []
    for f in fields:
        if f["name"] in seen:
            continue
        seen.add(f["name"])
        uniq.append(f)
    return uniq


def _parse_enum_hint(hs):
    """Godot 的 Enum hint 有 "A,B,C" 与 "A:0,B:2" 两种写法。"""
    opts = []
    used = 0
    for raw in hs.split(","):
        raw = raw.strip()
        if raw == "":
            continue
        if ":" in raw:
            nm, _, vv = raw.rpartition(":")
            try:
                opts.append({"name": nm.strip(), "value": int(vv.strip())})
                used += 1
                continue
            except ValueError:
                pass
        opts.append({"name": raw, "value": used})
        used += 1
    return opts


def classify_field(ftype, pending):
    hint = pending.get("hint", "")
    hs = pending.get("hint_string", "")
    extra = {}

    if "Enum" in hint and hs:
        # ⚠️ 关键区别：Godot 里
        #   string 字段 + Enum hint -> .tres 存「字符串」
        #   int    字段 + Enum hint -> .tres 存「整数下标/显式整数值」
        # 两者都当字符串写会让 int 字段变成类型不匹配的坏值。
        if ftype in ("int", "long", "uint", "ulong", "short"):
            return "enumtype", {"enumType": "", "owner": "",
                                "inlineOptions": _parse_enum_hint(hs)}
        return "enum", {"options": [x for x in hs.split(",") if x != ""]}
    if ftype == "bool":
        return "bool", {}
    if ftype in ("double", "float"):
        if "Range" in hint and hs:
            p = [x.strip() for x in hs.split(",")]
            try:
                extra["min"] = float(p[0]) if len(p) > 0 and p[0] else None
                extra["max"] = float(p[1]) if len(p) > 1 and p[1] else None
                extra["step"] = float(p[2]) if len(p) > 2 and p[2] else 0.01
            except Exception:
                pass
        return "float", extra
    if ftype in ("int", "long", "uint", "ulong", "short"):
        if "Range" in hint and hs:
            p = [x.strip() for x in hs.split(",")]
            try:
                extra["min"] = float(p[0]) if len(p) > 0 and p[0] else None
                extra["max"] = float(p[1]) if len(p) > 1 and p[1] else None
                extra["step"] = 1
            except Exception:
                pass
        return "int", extra
    if ftype in ("string", "StringName"):
        if "Multiline" in hint:
            return "text", {}
        if "Enum" in hint and hs:
            return "enum", {"options": [x for x in hs.split(",") if x != ""]}
        return "string", {}
    if ftype == "Vector2":
        return "vec2", {}
    if ftype == "Vector2I":
        return "vec2i", {}
    if ftype == "Color":
        return "color", {}
    if "Array" in ftype or "Dictionary" in ftype:
        return "complex", {"reason": "数组/字典，需在游戏内编辑器里编辑"}
    if ftype.startswith("ObjectManager") or ftype[0].isupper() and "." in ftype:
        return "enumtype", {"enumType": ftype.split(".")[-1], "owner": ftype.split(".")[0]}
    if ftype.endswith("Config") or ftype.endswith("Data") or ftype.endswith("Definition") \
            or ftype in ("PackedScene", "Resource", "Texture2D", "AudioStream", "Font",
                         "Material", "Gradient", "Curve", "StyleBox", "Theme"):
        return "complex", {"reason": "资源引用，保留原值"}
    return "complex", {"reason": "类型 %s 暂不支持直接编辑，保留原值" % ftype}


# ---------------------------------------------------------------- 枚举解析

_ENUM_INDEX = None


def enum_index():
    global _ENUM_INDEX
    if _ENUM_INDEX is not None:
        return _ENUM_INDEX
    cache_file = os.path.join(CACHE_DIR, "enum_index.json")
    if os.path.exists(cache_file):
        try:
            with io.open(cache_file, "r", encoding="utf-8") as f:
                _ENUM_INDEX = json.load(f)
            return _ENUM_INDEX
        except Exception:
            pass

    idx = {}
    pat = re.compile(r"^\s*(?:public|internal|private|protected)?\s*enum\s+(\w+)")
    member_pat = re.compile(r"^\s*(\w+)\s*(?:=\s*(-?\d+))?\s*,?\s*$")
    for dirpath, dirnames, filenames in os.walk(UNPACK):
        dirnames[:] = [d for d in dirnames if d not in (".godot", ".autoconverted", "Icons")]
        for fn in filenames:
            if not fn.endswith(".cs"):
                continue
            full = os.path.join(dirpath, fn)
            try:
                src = read_text(full)
            except Exception:
                continue
            lines = src.split("\n")
            for i, line in enumerate(lines):
                m = pat.match(line)
                if not m:
                    continue
                name = m.group(1)
                if name in idx:
                    continue
                # 花括号可能和声明同行，也可能在下一行
                members, depth, entered, j = [], 0, False, i
                while j < len(lines):
                    cur = lines[j]
                    if not entered:
                        depth += cur.count("{") - cur.count("}")
                        if depth > 0:
                            entered = True
                        j += 1
                        if not entered and j > i + 2:
                            break
                        continue
                    if cur.strip().startswith("}"):
                        break
                    cm = member_pat.match(cur)
                    if cm:
                        members.append([cm.group(1),
                                        int(cm.group(2)) if cm.group(2) is not None else None])
                    depth += cur.count("{") - cur.count("}")
                    j += 1
                    if depth <= 0:
                        break
                if members:
                    idx[name] = members
    try:
        ensure_cache_dir()
        with io.open(cache_file, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False)
    except Exception:
        pass
    _ENUM_INDEX = idx
    return idx


# ---------------------------------------------------------------- 取值/写值


def _clean_num(s):
    return float(re.sub(r"[fFdDmMlL]$", "", str(s).strip()))


COLOR_NAMES = {
    "white": [1.0, 1.0, 1.0, 1.0], "black": [0.0, 0.0, 0.0, 1.0],
    "red": [1.0, 0.0, 0.0, 1.0], "green": [0.0, 1.0, 0.0, 1.0],
    "blue": [0.0, 0.0, 1.0, 1.0], "yellow": [1.0, 1.0, 0.0, 1.0],
    "transparent": [1.0, 1.0, 1.0, 0.0], "gray": [0.5, 0.5, 0.5, 1.0],
}


def literal_to_python(kind, lit, field=None):
    """同时吃 .tres 字面量 和 C# 表达式（new Xxx(...) / 28f / EnumType.MEMBER）。"""
    if lit is None:
        return None
    if str(lit).strip() == "":
        # C# 里没有显式默认值 -> 该类型的零值
        return {"bool": False, "int": 0, "float": 0.0, "string": "",
                "text": "", "enum": "", "vec2": [0.0, 0.0], "vec2i": [0, 0],
                "color": [1.0, 1.0, 1.0, 1.0]}.get(kind, "")
    s = re.sub(r"^new\s+", "", str(lit).strip())
    try:
        if kind == "bool":
            return s.lower() == "true"
        if kind == "int":
            return int(_clean_num(s))
        if kind == "float":
            return _clean_num(s)
        if kind in ("string", "text", "enum"):
            m = re.search(r'"((?:[^"\\]|\\.)*)"', s)
            if m:
                return m.group(1).replace('\\"', '"')
            return s
        if kind == "enumtype":
            if re.fullmatch(r"-?\d+", s):
                return int(s)
            m = re.search(r"\.(\w+)\s*$", s)          # EnumType.MEMBER
            nm = m.group(1) if m else (s if re.fullmatch(r"\w+", s) else None)
            et = (field or {}).get("enumType") or ""
            for i, mem in enumerate(enum_index().get(et, []) if et else []):
                if mem[0] == nm:
                    return mem[1] if mem[1] is not None else i
            for o in ((field or {}).get("inlineOptions") or []):
                if o.get("name") == nm:
                    return o.get("value")
            if m:
                return m.group(1)
            return s
        if kind in ("vec2", "vec2i"):
            m = re.search(r"Vector2i?\(\s*([^,]+?)\s*,\s*([^)]+?)\s*\)", s)
            if m:
                return [_clean_num(m.group(1)), _clean_num(m.group(2))]
            return [0.0, 0.0]
        if kind == "color":
            m = re.search(r"Colors?\.(\w+)", s)
            if m and m.group(1).lower() in COLOR_NAMES:
                return list(COLOR_NAMES[m.group(1).lower()])
            m = re.search(r"Color\(\s*([^)]*)\)", s)
            if m:
                parts = [p.strip() for p in m.group(1).split(",") if p.strip()]
                vals = [_clean_num(p) for p in parts]
                while len(vals) < 4:
                    vals.append(1.0)
                return vals[:4]
            return [1.0, 1.0, 1.0, 1.0]
    except Exception:
        pass
    return s


def python_to_literal(kind, val, csharp_type=""):
    if kind == "bool":
        return "true" if val else "false"
    if kind == "int":
        return str(int(round(float(val))))
    if kind == "float":
        v = float(val)
        return ("%r" % v) if v != int(v) else ("%d.0" % int(v))
    if kind in ("string",):
        return json.dumps(str(val), ensure_ascii=False)
    if kind in ("enum", "text"):
        return json.dumps(str(val), ensure_ascii=False)
    if kind == "enumtype":
        # 枚举在 C# 里是整型字段，.tres 里写数字
        return str(int(float(val)))
    if kind == "vec2":
        return "Vector2(%s, %s)" % (_num(val[0]), _num(val[1]))
    if kind == "vec2i":
        return "Vector2i(%d, %d)" % (int(val[0]), int(val[1]))
    if kind == "color":
        return "Color(%s)" % ", ".join(_num(x) for x in val)
    raise ValueError("不支持的类型: %s" % kind)


def _num(v):
    f = float(v)
    return ("%r" % f) if f != int(f) else ("%d.0" % int(f))


# ---------------------------------------------------------------- 工程模型

DEFAULT_PROJECT = {
    "meta": {"id": "", "name": "", "version": "1.0.0", "author": "",
             "description": ""},
    "entries": [],
}


def load_project():
    if os.path.exists(PROJECT_FILE):
        try:
            with io.open(PROJECT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            data.setdefault("meta", dict(DEFAULT_PROJECT["meta"]))
            data.setdefault("entries", [])
            return data
        except Exception:
            pass
    return json.loads(json.dumps(DEFAULT_PROJECT))


def save_project(proj):
    write_text(PROJECT_FILE, json.dumps(proj, ensure_ascii=False, indent=2))
    return PROJECT_FILE


def sanitize_id(s):
    """把任意名字收敛成安全的 Mod id。

    Mod id 只允许 ASCII 字母/数字/`-`/`_`。但直接过滤会把中文名削光：
    「豌豆强化」-> "" -> 兜底成 "mod"，「豌豆强化v2」-> "v2" —— 于是**两个不同中文 Mod
    会拿到同一个 id**（id 会进依赖/冲突判定，撞了很麻烦）。
    所以名字里含非 ASCII 时，保留可读部分再挂一个名字哈希后缀，保证稳定且唯一。
    """
    s = (s or "").strip()
    core = re.sub(r"[^0-9A-Za-z\-_]", "_", s).strip("_")
    if core and not any(ord(c) > 127 for c in s):
        return core
    h = hashlib.md5(s.encode("utf-8")).hexdigest()[:6] if s else "000000"
    return (core + "_" + h) if core else ("mod_" + h)


# ---------------------------------------------------------------- 生成产物


def build_entry(cat, entry):
    """把一条 entry 渲染成包内相对路径 + 文件内容。"""
    cfg = CATEGORIES.get(cat)
    if not cfg:
        raise ValueError("未知类别: %s" % cat)
    key = entry["key"]
    edits = entry.get("edits") or {}
    unset = entry.get("unset") or []

    src_path = None
    if entry.get("mode") == "provide" and entry.get("baseKey"):
        src_path = find_source_file(cat, entry["baseKey"])[1]
    if src_path is None:
        src_path = find_source_file(cat, key)[1]
    if not src_path or not os.path.exists(src_path):
        raise ValueError("找不到原版资源: %s/%s" % (cat, key))

    ext = os.path.splitext(src_path)[1].lower()
    out_rel = "%s/%s%s" % (cfg["out"], key, ext)

    if ext in (".tres", ".res"):
        parsed = parse_tres(read_text(src_path))
        # provide 模式：改名，避免与原版同名（名称字段通常也叫 name）
        if entry.get("mode") == "provide" and entry.get("renameField"):
            edits = dict(edits)
            edits.setdefault(entry["renameField"],
                             json.dumps(key, ensure_ascii=False))
        content = serialize_tres(parsed, edits, unset)
        return out_rel, content, src_path

    # 非 .tres（音频等）：文件替换型
    # 优先用 sourceFile（上传后落盘的路径，工程 JSON 里只存路径不吃内存），
    # 其次兼容内联 fileBase64。
    src_file = entry.get("sourceFile")
    if src_file and os.path.exists(src_file):
        with open(src_file, "rb") as f:
            return out_rel, f.read(), src_path
    data = entry.get("fileBase64")
    if not data:
        raise ValueError("%s 是文件替换型条目，请先选一个替换文件" % key)
    return out_rel, base64.b64decode(data), src_path


def find_source_file(cat, key):
    """返回 (uid_or_none, 绝对路径)。"""
    cfg = CATEGORIES.get(cat)
    if not cfg:
        return None, None
    reg, _ = load_registry(cat)
    uid = reg.get(key)
    if uid and uid.startswith("uid://"):
        p = resolve_uid(uid)
        if p:
            return uid, p
    if uid and uid.startswith("file:"):
        p = os.path.join(UNPACK, uid[5:].replace("/", os.sep))
        if os.path.exists(p):
            return None, p
    # 回退：在源目录里按文件名找
    for d in cfg["src"]:
        base = os.path.join(UNPACK, d.replace("/", os.sep))
        for dp, _, fns in os.walk(base):
            for fn in fns:
                if os.path.splitext(fn)[0] == key and fn.endswith(".tres"):
                    return uid, os.path.join(dp, fn)
    return uid, None


def build_manifest(proj):
    meta = proj.get("meta") or {}
    name = (meta.get("name") or "").strip() or "新Mod"
    overrides, provides = {}, {}
    resources = []
    for e in proj.get("entries") or []:
        cat = e.get("category")
        key = e.get("key")
        bucket = provides if e.get("mode") == "provide" else overrides
        bucket.setdefault(cat, [])
        if key not in bucket[cat]:
            bucket[cat].append(key)
        cfg = CATEGORIES.get(cat)
        if not cfg:
            continue
        src_key = e.get("baseKey") if e.get("mode") == "provide" else key
        try:
            ext = os.path.splitext(find_source_file(cat, src_key)[1])[1] or ".tres"
        except Exception:
            ext = ".tres"
        resources.append("%s/%s%s" % (cfg["out"], key, ext))
    return {
        "schemaVersion": 2,
        "id": sanitize_id(meta.get("id") or name),
        "name": name,
        "version": (meta.get("version") or "1.0.0").strip(),
        "author": (meta.get("author") or "").strip(),
        "description": (meta.get("description") or "").strip(),
        "dependencies": [], "conflicts": [],
        "provides": provides, "overrides": overrides,
        "scripts": [], "runtimeAssembly": "", "runtimeEntryType": "",
        "runtimeApiVersion": 0, "runtimeAssemblyPolicy": "",
        "blueprints": [], "translations": [],
        "resources": resources,
    }


def render_files(proj):
    """返回 ({包内相对路径: 内容(str|bytes)}, [错误...])。"""
    files, errors = {}, []
    for e in proj.get("entries") or []:
        try:
            rel, content, _src = build_entry(e.get("category"), e)
            files[rel] = content
        except Exception as ex:
            errors.append("%s/%s: %s" % (e.get("category"), e.get("key"), ex))
    return files, errors


def ext_warnings(proj):
    """替换文件的扩展名和原版不一致时给出提醒（Godot 按扩展名选 loader）。"""
    warns = []
    for e in proj.get("entries") or []:
        cat, key = e.get("category"), e.get("key")
        sf = e.get("sourceFile")
        if not sf or not os.path.exists(sf):
            continue
        try:
            src = find_source_file(cat, key)[1]
        except Exception:
            src = None
        if not src:
            continue
        want = os.path.splitext(src)[1].lower()
        got = os.path.splitext(sf)[1].lower()
        if want and got and want != got:
            warns.append("%s/%s：原版是 %s，替换文件是 %s —— 扩展名不一致，游戏可能加载不了"
                         % (cat, key, want, got))
    return warns


def render_preview(proj):
    """只渲染不落盘，供 UI 预览。"""
    files, errors = render_files(proj)
    summary = {}
    for rel, content in files.items():
        if isinstance(content, bytes):
            summary[rel] = {"binary": True, "size": len(content)}
        else:
            summary[rel] = {"text": content}
    return {
        "manifest": build_manifest(proj),
        "files": summary,
        "errors": errors,
        "warnings": ext_warnings(proj),
    }


def package_name(proj):
    meta = proj.get("meta") or {}
    raw = (meta.get("name") or "").strip() or "新Mod"
    safe = re.sub(r'[\\/:*?"<>|]', "_", raw)
    return safe + ".pmod"


def build_package(proj, install=True):
    """生成 .pmod；返回结果字典。"""
    files, errors = render_files(proj)
    if errors:
        return {"ok": False, "stage": "render", "errors": errors}
    if not files:
        return {"ok": False, "stage": "render", "errors": ["工程里没有条目"]}

    ensure_cache_dir()
    os.makedirs(DIST_DIR, exist_ok=True)
    pmod = os.path.join(DIST_DIR, package_name(proj))
    manifest = build_manifest(proj)
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)

    entries = ["mod.json"] + sorted(files.keys())
    tmp = pmod + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("mod.json", manifest_json)
        for rel in sorted(files.keys()):
            z.writestr(rel, files[rel])
    shutil.move(tmp, pmod)

    result = {"ok": True, "pmod": pmod, "entries": entries,
              "size": os.path.getsize(pmod), "manifest": manifest,
              "installed": None, "validation": None}

    if install and os.path.isdir(USER_MODS_DIR):
        tgt = os.path.join(USER_MODS_DIR, os.path.basename(pmod))
        shutil.copy2(pmod, tgt)
        result["installed"] = tgt

    try:
        import verify_pmod
        rep = verify_pmod.verify(pmod)
        result["validation"] = rep.items
    except Exception as ex:
        result["validation"] = [{"level": "WARN", "code": "validate.error",
                                 "msg": "校验器异常: %s" % ex}]
    return result


# ---------------------------------------------------------------- 已装 Mod


def upload_blob(name, b64):
    """把前端选中的替换文件落盘，返回路径（工程 JSON 只存路径，不吃内存）。"""
    if not b64:
        return {"ok": False, "error": "没有收到文件内容"}
    name = os.path.basename(name or "upload.bin")
    stem, ext = os.path.splitext(name)
    safe = re.sub(r'[\\/:*?"<>|\s]+', "_", stem)[:60] or "upload"
    up_dir = os.path.join(CACHE_DIR, "uploads")
    os.makedirs(up_dir, exist_ok=True)
    dst = os.path.join(up_dir, safe + ext)
    n = 1
    while os.path.exists(dst):
        dst = os.path.join(up_dir, "%s_%d%s" % (safe, n, ext))
        n += 1
    try:
        data = base64.b64decode(b64)
    except Exception as ex:
        return {"ok": False, "error": "base64 解码失败: %s" % ex}
    with open(dst, "wb") as f:
        f.write(data)
    return {"ok": True, "path": dst, "size": len(data), "ext": ext.lower()}


def list_installed():
    out = []
    if not os.path.isdir(USER_MODS_DIR):
        return out
    for fn in sorted(os.listdir(USER_MODS_DIR)):
        if not fn.lower().endswith(".pmod"):
            continue
        full = os.path.join(USER_MODS_DIR, fn)
        info = {"file": fn, "path": full, "size": os.path.getsize(full),
                "mtime": datetime.fromtimestamp(os.path.getmtime(full)).strftime("%Y-%m-%d %H:%M"),
                "manifest": None, "error": None}
        try:
            with zipfile.ZipFile(full) as z:
                info["manifest"] = json.loads(z.read("mod.json").decode("utf-8-sig"))
        except Exception as ex:
            info["error"] = str(ex)
        out.append(info)
    return out


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "PVZModEditor/1.0"

    def log_message(self, fmt, *args):
        pass  # 静音

    # ---- helpers
    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except BrokenPipeError:
            pass

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        return json.loads(self.rfile.read(n).decode("utf-8"))

    # ---- routes
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        p = unquote(u.path)
        try:
            if p in ("/", "/index.html"):
                if not os.path.exists(UI_FILE):
                    return self._send(500, "缺少 mod_editor_ui.html", "text/plain")
                return self._send(200, read_text(UI_FILE), "text/html; charset=utf-8")
            if p == "/api/state":
                return self._json({
                    "unpack": UNPACK, "unpackExists": os.path.isdir(UNPACK),
                    "modsDir": USER_MODS_DIR,
                    "modsDirExists": os.path.isdir(USER_MODS_DIR),
                    "distDir": DIST_DIR,
                    "projectFile": PROJECT_FILE,
                    "categories": category_list(),
                    "installed": list_installed(),
                    "project": load_project(),
                })
            if p == "/api/keys":
                cat = (q.get("category") or [""])[0]
                reg, note = load_registry(cat)
                items = []
                for k, v in sorted(reg.items()):
                    src = find_source_file(cat, k)[1]
                    items.append({
                        "key": k, "uid": v if str(v).startswith("uid://") else None,
                        "hasFile": bool(src),
                        "file": rel_under(UNPACK, src) if src else None,
                        "ext": os.path.splitext(src)[1].lower() if src else None,
                    })
                return self._json({"category": cat, "keys": items, "note": note})
            if p == "/api/resource":
                cat = (q.get("category") or [""])[0]
                key = (q.get("key") or [""])[0]
                return self._json(load_resource_detail(cat, key))
            if p == "/api/project":
                return self._json(load_project())
            if p == "/api/preview":
                return self._json(render_preview(load_project()))
            if p == "/api/installed":
                return self._json({"installed": list_installed()})
            return self._send(404, "not found", "text/plain")
        except Exception as ex:
            import traceback
            return self._json({"error": str(ex),
                               "trace": traceback.format_exc()}, 500)

    def do_POST(self):
        u = urlparse(self.path)
        p = unquote(u.path)
        try:
            body = self._body()
            if p == "/api/project":
                save_project(body.get("project") or {})
                return self._json({"ok": True, "path": PROJECT_FILE})
            if p == "/api/preview":
                return self._json(render_preview(body.get("project") or load_project()))
            if p == "/api/build":
                proj = body.get("project") or load_project()
                save_project(proj)
                return self._json(build_package(proj, install=body.get("install", True)))
            if p == "/api/upload":
                return self._json(upload_blob(body.get("name"), body.get("base64")))
            if p == "/api/uninstall":
                fn = body.get("file") or ""
                full = os.path.join(USER_MODS_DIR, os.path.basename(fn))
                if os.path.exists(full):
                    os.remove(full)
                    return self._json({"ok": True, "removed": full})
                return self._json({"ok": False, "error": "不存在: %s" % full}, 404)
            if p == "/api/reveal":
                target = body.get("target")
                path = {"mods": USER_MODS_DIR, "dist": DIST_DIR,
                        "project": HERE,
                        "uploads": os.path.join(CACHE_DIR, "uploads")}.get(target, HERE)
                if os.path.isdir(path):
                    os.startfile(path)  # noqa
                    return self._json({"ok": True, "path": path})
                return self._json({"ok": False, "error": "目录不存在: %s" % path}, 404)
            if p == "/api/reindex":
                build_uid_index(force=True)
                return self._json({"ok": True, "count": len(build_uid_index())})
            return self._send(404, "not found", "text/plain")
        except Exception as ex:
            import traceback
            return self._json({"error": str(ex),
                               "trace": traceback.format_exc()}, 500)


def load_resource_detail(cat, key):
    """给 UI 一份完整的「原版值 + 可改字段」描述。"""
    uid, src = find_source_file(cat, key)
    detail = {"category": cat, "key": key, "uid": uid,
              "file": rel_under(UNPACK, src) if src else None,
              "tres": None, "scriptPath": None, "fields": [],
              "groups": [], "error": None}
    if not src:
        detail["error"] = "找不到原版资源文件（该键可能在正式版里，但解包目录里没有对应 .tres）"
        return detail
    if os.path.splitext(src)[1].lower() not in (".tres", ".res"):
        detail["kind"] = "binary"
        detail["error"] = "文件替换型条目：请上传替换文件（%s）" % os.path.splitext(src)[1]
        return detail

    text = read_text(src)
    parsed = parse_tres(text)
    detail["kind"] = "tres"
    detail["tres"] = text
    detail["headerClass"] = parsed["header_attrs"].get("script_class", "")

    # 找配置类脚本
    script_path = None
    for raw, attrs in parsed["ext_resources"]:
        if attrs.get("type") == "Script" and "/Resource/" in attrs.get("path", ""):
            cand = os.path.join(UNPACK, attrs["path"].replace("res://", "").replace("/", os.sep))
            base = attrs["path"].split("/")[-1]
            # 精确匹配配置类名
            if base.lower().startswith(parsed["header_attrs"].get("script_class", "\0").lower()):
                script_path = cand
                break
    if script_path is None:
        for raw, attrs in parsed["ext_resources"]:
            if attrs.get("type") == "Script" and "/Resource/" in attrs.get("path", ""):
                script_path = os.path.join(
                    UNPACK, attrs["path"].replace("res://", "").replace("/", os.sep))
                break
    detail["scriptPath"] = rel_under(UNPACK, script_path) if script_path else None

    fields = parse_cs_fields(script_path)
    props = dict(parsed["props"])

    for f in fields:
        name = f["name"]
        present = name in props
        raw = props.get(name)
        f["present"] = present
        f["rawValue"] = raw
        f["source"] = "tres" if present else "default"
        if f["kind"] == "enumtype":
            members = enum_index().get(f.get("enumType") or "", []) if f.get("enumType") else []
            if members:
                f["options"] = [{"name": m[0], "value": (m[1] if m[1] is not None else i)}
                                for i, m in enumerate(members)]
            else:
                # int 字段上的内联 Enum hint（hint_string 里直接给名字）
                f["options"] = f.get("inlineOptions") or []
        f["editable"] = f["kind"] != "complex"
        f["value"] = literal_to_python(f["kind"], raw if present else f.get("default"), f)

    # 记录原版 .tres 里存在但不属于 [Export] 字段的属性（也允许改）
    extra = []
    known = {f["name"] for f in fields}
    for name, raw in parsed["props"]:
        if name in known or name in ("script",):
            continue
        extra.append({"name": name, "rawValue": raw, "kind": "extra"})

    detail["fields"] = fields
    detail["extraProps"] = extra
    detail["groups"] = []
    seen = []
    for f in fields:
        if f["group"] not in seen:
            seen.append(f["group"])
    detail["groups"] = seen
    return detail


# ---------------------------------------------------------------- 入口


def cli_build(proj_path=None):
    global PROJECT_FILE
    if proj_path:
        PROJECT_FILE = proj_path
    proj = load_project()
    if not proj.get("entries"):
        print("工程里没有条目: %s" % PROJECT_FILE)
        return 1
    res = build_package(proj, install=True)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    if res.get("validation"):
        bad = [v for v in res["validation"] if v["level"] == "FAIL"]
        print("校验: %d 项，FAIL %d" % (len(res["validation"]), len(bad)))
        for v in bad:
            print("  FAIL [%s] %s" % (v["code"], v["msg"]))
    return 0 if res.get("ok") and not any(
        v["level"] == "FAIL" for v in (res.get("validation") or [])) else 1


def main():
    ap = argparse.ArgumentParser(description="PVZ 杂交版独立 Mod 编辑器")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--build", action="store_true", help="不开服务，直接构建")
    ap.add_argument("--project", default=None, help="工程 JSON 路径")
    ap.add_argument("--unpack", default=None, help="解包目录")
    args = ap.parse_args()

    global UNPACK, PROJECT_FILE
    if args.unpack:
        UNPACK = args.unpack
    if args.project:
        PROJECT_FILE = args.project

    if args.build:
        return cli_build()

    if not os.path.isdir(UNPACK):
        print("!! 解包目录不存在: %s" % UNPACK)
        print("   用 --unpack 指定，或设环境变量 PVZHE_UNPACK")
        return 2

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    url = "http://%s:%d/" % (args.host, args.port)
    print("=" * 66)
    print("  PVZ 杂交版 Mod 编辑器")
    print("  解包目录 : %s" % UNPACK)
    print("  Mods 目录: %s %s" % (USER_MODS_DIR,
                                 "" if os.path.isdir(USER_MODS_DIR) else "(不存在)"))
    print("  工程文件 : %s" % PROJECT_FILE)
    print("  打开地址 : %s" % url)
    print("=" * 66)
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    return 0


if __name__ == "__main__":
    sys.exit(main())
