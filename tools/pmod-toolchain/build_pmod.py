# -*- coding: utf-8 -*-
"""
build_pmod.py —— 手写 PVZ 杂交版 Mod 包（.pmod）

原理（逆向自 addons/ModEditor/ModSystem/ModExporter.cs + ModLoader.cs）：
  .pmod 就是一个 zip：
    - 根条目名必须正好是 "mod.json"（ModLoader: "package must contain exactly one root mod.json"）
    - 其余条目用「工程相对路径」，路径前缀决定资源类别，文件名（去扩展名）决定 key
      ModLoader.InferRuntimeEntry():
        Resources/Projectiles/<Key>.tres  -> category=Projectile
        Resources/Maps/<Key>.tres         -> category=Map
        Resources/Cards/<Key>.tres        -> category=Packet
        Resources/Collectables/<Key>.tres -> category=Collectable
        Assets/Textures/<Key>.png         -> category=Texture
        Assets/Audio/<Key>.ogg            -> category=Audio
        ... 完整表见 ModLoader.InferRuntimeEntry
    - 可选 Runtime/ModAssembly.dll（托管代码 Mod，本工程不用）

  运行时：ModLoader.ApplyMod -> XWModRuntimeRegistry.Register(owner, category, key, value, allowOverride)
  对 category=Projectile 会写进 ResourceManager.Instance.PROJECTILE_CONFIG[key]
  → 于是覆盖了原版子弹。overrides 声明的 key 必须【已存在】，否则报
    "overrides target is missing"。

用法：
    python build_pmod.py            # 生成工程文件 + 打包 .pmod
"""

import io
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone, timedelta

# ---------------- 路径 ----------------
WS = os.path.dirname(os.path.abspath(__file__))
UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
SRC_PROJ = os.path.join(UNPACK, "Asset", "Config", "Projectile", "Pea")

MOD_ID = "peaoverhaul"
MOD_NAME = "PeaOverhaul"
DISPLAY_NAME = "豌豆强化"
VERSION = "1.0.0"
AUTHOR = "云漫行"
DESCRIPTION = "演示用 Mod：放大豌豆类子弹并提升伤害与穿透（覆盖 Projectile 资源）"

MOD_ROOT = os.path.join(WS, MOD_NAME)
DIST_DIR = os.path.join(WS, "dist")

USER_MODS_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    "Godot", "app_userdata", "植物大战僵尸杂交版", "Mods",
)

# ---------------- 覆盖内容 ----------------
# key = PROJECTILE_CONFIG 里的键名（取自 Asset/Config/Projectile/ProjectileResource.json）
# src = 解包里的原始 .tres（作为基底，保证不丢字段）
# patch = 要改写的 [resource] 段属性
OVERRIDES = [
    {
        "key": "PeaDefault",
        "src": os.path.join(SRC_PROJ, "PeaDefault.tres"),
        "patch": {
            "baseDamage": "60.0",
            "scale": "Vector2(1.6, 1.6)",
            "penetrateNum": "8",
        },
        "note": "普通豌豆：伤害 20→60，穿透 3→8，视觉放大 1.6 倍",
    },
    {
        "key": "SnowPea",
        "src": os.path.join(SRC_PROJ, "SnowPea.tres"),
        "patch": {
            "baseDamage": "60.0",
            "scale": "Vector2(1.6, 1.6)",
            "penetrateNum": "8",
        },
        "note": "寒冰豌豆：同上，保留原有冰冻 Buff 事件链",
    },
    {
        "key": "FirePea",
        "src": os.path.join(SRC_PROJ, "FirePea.tres"),
        "patch": {
            "baseDamage": "120.0",
            "scale": "Vector2(1.6, 1.6)",
            "penetrateNum": "8",
        },
        "note": "火焰豌豆：伤害 40→120，穿透 3→8",
    },
    {
        "key": "GoldPea",
        "src": os.path.join(SRC_PROJ, "GoldPea.tres"),
        "patch": {
            "scale": "Vector2(1.6, 1.6)",
        },
        "note": "黄金豌豆：仅放大（其伤害走 hitTargetEventList，不动）",
    },
]


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read()


def write_text(path, text, newline="\n"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Godot 的 .tres 用 LF
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def strip_header_uid(tres_text):
    """去掉 [gd_resource ...] 行里的 uid="..."。

    覆盖包不能沿用原版资源的 uid，否则 Godot 会报重复 UID。
    ext_resource 的 uid 必须保留（它们指向内置子资源）。
    """
    lines = tres_text.split("\n")
    for i, line in enumerate(lines):
        if not line.startswith("[gd_resource"):
            continue
        if " uid=\"" not in line:
            break
        head, tail = line.split(" uid=\"", 1)
        close = tail.find("\"")
        rest = tail[close + 1:].strip()          # 形如  format=3]  或  ]
        head = head.rstrip()
        if rest.startswith("]"):
            lines[i] = head + rest               # uid 是最后一个属性
        else:
            lines[i] = head + " " + rest
        break
    return "\n".join(lines)


def patch_resource_block(tres_text, patch):
    """在 [resource] 段内改写/追加属性。"""
    lines = tres_text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "[resource]":
            start = i
            break
    if start is None:
        raise ValueError("找不到 [resource] 段")

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("[") and lines[i].strip().endswith("]"):
            end = i
            break

    body = lines[start + 1:end]
    while body and body[-1].strip() == "":
        body.pop()

    remaining = dict(patch)
    for i, line in enumerate(body):
        if "=" not in line:
            continue
        prop = line.split("=", 1)[0].strip()
        if prop in remaining:
            body[i] = "%s = %s" % (prop, remaining.pop(prop))

    for prop, value in remaining.items():
        body.append("%s = %s" % (prop, value))

    lines[start + 1:end] = body + [""]
    return "\n".join(lines)


def build_manifest():
    return {
        "schemaVersion": 2,
        "id": MOD_ID,
        "name": DISPLAY_NAME,
        "version": VERSION,
        "author": AUTHOR,
        "description": DESCRIPTION,
        "dependencies": [],
        "conflicts": [],
        "provides": {},
        "overrides": {
            "Projectile": [o["key"] for o in OVERRIDES],
        },
        "scripts": [],
        "runtimeAssembly": "",
        "runtimeEntryType": "",
        "runtimeApiVersion": 0,
        "runtimeAssemblyPolicy": "",
        "blueprints": [],
        "translations": [],
        "resources": [
            "Resources/Projectiles/%s.tres" % o["key"] for o in OVERRIDES
        ],
    }


def build_project_file():
    now = datetime.now(timezone(timedelta(hours=8))).isoformat()
    return {
        "Name": MOD_NAME,
        "Version": VERSION,
        "Author": AUTHOR,
        "Description": DESCRIPTION,
        "ExportDirectory": USER_MODS_DIR.replace("\\", "/") + "/",
        "GameDirectory": "",
        "CreatedDate": now,
        "LastModifiedDate": now,
    }


def dump_json(path, obj, newline="\n"):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2), newline=newline)


def main():
    print("=" * 72)
    print("构建 Mod 工程:", MOD_ROOT)

    # 1) 生成覆盖资源
    written = []
    for o in OVERRIDES:
        if not os.path.exists(o["src"]):
            raise SystemExit("原始资源不存在: %s" % o["src"])
        text = read_text(o["src"])
        text = strip_header_uid(text)
        text = patch_resource_block(text, o["patch"])
        dst = os.path.join(MOD_ROOT, "Resources", "Projectiles", o["key"] + ".tres")
        write_text(dst, text)
        written.append(dst)
        print("  [ok] Resources/Projectiles/%s.tres  <- %s"
              % (o["key"], os.path.basename(o["src"])))
        print("       %s" % o["note"])

    # 2) 工程清单
    dump_json(os.path.join(MOD_ROOT, "mod.json"), build_manifest())
    print("  [ok] mod.json")

    # 3) 官方编辑器可识别的工程文件（可选，方便 F3 里继续改）
    dump_json(os.path.join(MOD_ROOT, MOD_NAME + ".pvzmodeproject"), build_project_file())
    print("  [ok] %s.pvzmodeproject" % MOD_NAME)

    # 4) 打包 .pmod —— mod.json 必须是第一个条目且位于根
    os.makedirs(DIST_DIR, exist_ok=True)
    pmod = os.path.join(DIST_DIR, MOD_NAME + ".pmod")

    entries = ["mod.json"]
    rel_root = []
    for dirpath, _, filenames in os.walk(MOD_ROOT):
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, MOD_ROOT).replace("\\", "/")
            if rel == "mod.json":
                continue
            if rel.endswith((".uid", ".import", ".cs", ".csproj", ".sln",
                             ".pvzmodeproject", ".pmod")):
                continue  # 与 ModExporter.ShouldPackageProjectFile 一致
            rel_root.append(rel)
    entries += sorted(rel_root)

    with zipfile.ZipFile(pmod, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in entries:
            src = os.path.join(MOD_ROOT, rel)
            z.write(src, rel)

    print("  [ok] 打包完成: %s (%d 条目, %d 字节)"
          % (pmod, len(entries), os.path.getsize(pmod)))

    # 5) 安装到游戏 Mods 目录
    if USER_MODS_DIR and os.path.isdir(USER_MODS_DIR):
        target = os.path.join(USER_MODS_DIR, MOD_NAME + ".pmod")
        shutil.copy2(pmod, target)
        print("  [ok] 已安装到: %s" % target)
    else:
        print("  [!!] 未找到 Mods 目录，跳过安装: %s" % USER_MODS_DIR)

    print("=" * 72)
    print("条目顺序：")
    for i, e in enumerate(entries):
        print("   %2d  %s" % (i, e))


if __name__ == "__main__":
    main()
