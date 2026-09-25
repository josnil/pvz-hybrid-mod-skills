# -*- coding: utf-8 -*-
"""僵尸 Mod 交付物最终核对（只读，v2：修正上一版 3 处错误断言）。

上一版的错误假设：
  1. 「构建目录条目数 == 9」——构建目录里还有 `.pvzmodeproject`（**本来就不入包**），
     文件数应为 10；真正该断言的是 **zip 内条目数 == 9**。
  2. 「Mods 镜像子目录数 == 72」——72 是 `STANDARD_DIRS` 的数量，镜像还要加上
     本包自己造出来的目录（`Runtime` + 角色 5 层子目录），正确值 = 72 + 6 = 78。
  3. `runtimeEntry` —— `mod.json` 里的真名是 **`runtimeEntryType`**。
"""
import ast
import hashlib
import io
import json
import os
import zipfile

WS = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版\Asset\Anime\Character\Zombie\.workbuddy\ModWorkspace"
BUILD = os.path.join(WS, "DiscoGargantuarPult")
DIST = os.path.join(WS, "dist")
MODS = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
GEN = os.path.join(WS, "build_zombie_disco_pult.py")
NAME = "暴走舞王伽刚特尔投石车僵尸"
CHAR_KEY = "ZombieDiscoGargantuarPult"


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 16), b""):
            h.update(c)
    return h.hexdigest()


def walk_rel(base):
    out = []
    for root, dirs, files in os.walk(base):
        for fn in files:
            out.append(os.path.relpath(os.path.join(root, fn), base).replace("\\", "/"))
    return sorted(out)


def walk_dirs(base):
    out = []
    for root, dirs, files in os.walk(base):
        for d in dirs:
            out.append(os.path.relpath(os.path.join(root, d), base).replace("\\", "/"))
    return sorted(out)


def standard_dirs():
    """从生成器源码里取 STANDARD_DIRS（用 AST，不执行模块）。"""
    tree = ast.parse(io.open(GEN, encoding="utf-8").read())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "STANDARD_DIRS" for t in node.targets):
            return [e.value for e in node.value.elts]
    raise AssertionError("生成器里找不到 STANDARD_DIRS")


fails = []
def line(tag, ok, detail=""):
    print(("[%s] " % ("PASS" if ok else "FAIL")) + tag + ("  " + detail if detail else ""))
    if not ok:
        fails.append(tag)
    return ok


print("=" * 74)
print("僵尸 Mod 交付物最终核对 v2")
print("=" * 74)

# ---- 1. .pmod 两份位置 ----
src = os.path.join(DIST, NAME + ".pmod")
dst = os.path.join(MODS, NAME + ".pmod")
for tag, p in (("工作区 dist", src), ("游戏 Mods", dst)):
    if os.path.isfile(p):
        line("%s 的 .pmod 存在" % tag, True,
             "%d B  sha256=%s" % (os.path.getsize(p), sha256(p)))
    else:
        line("%s 的 .pmod 存在" % tag, False, p)
if os.path.isfile(src) and os.path.isfile(dst):
    a = open(src, "rb").read()
    b = open(dst, "rb").read()
    line("dist 与 Mods 的 .pmod 逐字节一致", a == b)

# ---- 2. zip 内容 ----
print("-" * 74)
with zipfile.ZipFile(src) as z:
    infos = z.infolist()
    znames = [i.filename for i in infos]
    first = znames[0]
    txt = z.read("mod.json").decode("utf-8")
    man = json.loads(txt)
    bad = [n for n in znames if n.endswith((".uid", ".import", ".cs", ".pvzmodeproject"))
           or os.path.basename(n).startswith(".")]
    bad = [n for n in bad if not n.endswith(".cs") or "/" in n]
    cs = [n for n in znames if n.endswith(".cs")]
    pvj = [n for n in znames if n.endswith(".pvzmodeproject")]
line("zip 条目数 == 9", len(znames) == 9, "实际 %d" % len(znames))
line("mod.json 是第 0 个条目", first == "mod.json", repr(first))
line("zip 内不含 .cs（禁用内嵌脚本）", not cs, repr(cs))
line("zip 内不含 .pvzmodeproject（工程文件不入包）", not pvj, repr(pvj))
line("zip 内无 .uid/.import/dotfile", not bad, repr(bad))
manual = walk_rel(BUILD)
packed = [r for r in manual if not r.endswith(".pvzmodeproject")]
# 注意：不能比顺序 —— zip 把 mod.json 固定排第 0，而文件系统按字母序排在最后（'R' < 'm'）。
line("zip 条目集 == 构建目录文件集（去掉 .pvzmodeproject）",
     sorted(znames) == sorted(packed),
     "zip %d / 构建目录 %d，差集 %s" % (len(znames), len(packed),
                                       sorted(set(znames) ^ set(packed))))
line("zip 条目顺序 = mod.json 优先 + 字典序",
     znames == sorted(znames, key=lambda r: (r != "mod.json", r)))
for n in znames:
    print("      - %s" % n)

# ---- 3. manifest ----
print("-" * 74)
line("schemaVersion == 2", man.get("schemaVersion") == 2)
line("id == discogargantuarpult", man.get("id") == "discogargantuarpult", repr(man.get("id")))
line("name == 需求中文名（显示名直接写中文）", man.get("name") == NAME, repr(man.get("name")))
line("translations == []", man.get("translations") == [])
line("runtimeAssembly == 'Runtime/ModAssembly.dll'（字面量硬约束）",
     man.get("runtimeAssembly") == "Runtime/ModAssembly.dll", repr(man.get("runtimeAssembly")))
line("runtimeEntryType == 'DiscoGargantuarPultRuntimeEntry'",
     man.get("runtimeEntryType") == "DiscoGargantuarPultRuntimeEntry",
     repr(man.get("runtimeEntryType")))
line("runtimeApiVersion == 1（恰好）", man.get("runtimeApiVersion") == 1)
line("runtimeAssemblyPolicy == 'optional'", man.get("runtimeAssemblyPolicy") == "optional",
     repr(man.get("runtimeAssemblyPolicy")))
res = man.get("resources")
need = sorted([r for r in znames if r != "mod.json"])
line("manifest.resources == zip 去掉 mod.json（规范序）", res == need,
     "manifest %d / zip %d" % (len(res or []), len(need)))
prov = man.get("provides") or {}
line("provides 三键均 == [%s]" % CHAR_KEY,
     sorted(prov.keys()) == ["Character", "CharacterSprite", "Packet"]
     and all(v == [CHAR_KEY] for v in prov.values()),
     json.dumps(prov, ensure_ascii=False))

# ---- 4. Runtime 目录 ----
print("-" * 74)
rt = os.path.join(BUILD, "Runtime")
rt_files = sorted(os.listdir(rt)) if os.path.isdir(rt) else []
line("Runtime/ 下只有 ModAssembly.dll（硬约束）", rt_files == ["ModAssembly.dll"], repr(rt_files))
dll = os.path.join(rt, "ModAssembly.dll")
if os.path.isfile(dll):
    line("DLL 大小 == 19456 B", os.path.getsize(dll) == 19456,
         "%d B  sha256=%s" % (os.path.getsize(dll), sha256(dll)))
    dll_in_zip = hashlib.sha256(zipfile.ZipFile(src).read("Runtime/ModAssembly.dll")).hexdigest()
    line("包内 DLL 与构建目录 DLL 一致", dll_in_zip == sha256(dll), dll_in_zip[:24])

# ---- 5. Mods 镜像 ----
print("-" * 74)
mirror = os.path.join(MODS, NAME)
std = standard_dirs()
pkg_dirs = [d for d in walk_dirs(BUILD)]
mir_dirs = walk_dirs(mirror)
expect = sorted(set(std) | set(pkg_dirs))
line("STANDARD_DIRS 数量 == 72", len(std) == 72, "实际 %d" % len(std))
line("镜像内文件与构建目录一致", walk_rel(mirror) == manual,
     "镜像 %d / 构建 %d" % (len(walk_rel(mirror)), len(manual)))
line("镜像目录集 == STANDARD_DIRS ∪ 包内目录（%d 个）" % len(expect),
     mir_dirs == expect,
     "镜像 %d / 期望 %d，差集 %s" % (len(mir_dirs), len(expect),
                                    sorted(set(mir_dirs) ^ set(expect))))
line("镜像含 72 个标准目录", all(d in mir_dirs for d in std),
     "缺 %s" % [d for d in std if d not in mir_dirs])

# ---- 6. enabled_mods / 最近工程 ----
print("-" * 74)
with io.open(os.path.join(MODS, "enabled_mods.json"), encoding="utf-8") as f:
    ids = json.load(f)
line("enabled_mods.json 含 discogargantuarpult", "discogargantuarpult" in ids, repr(ids))
dup = sorted({x for x in ids if x.lower() == "discogargantuarpult" and x != "discogargantuarpult"})
line("无大小写重名残留", not dup, repr(dup))
line("未丢别人的条目（PeaOverhaul/supergatlingpea/vampirepool 都在）",
     {"PeaOverhaul", "supergatlingpea", "vampirepool"} <= set(ids))
rp = os.path.join(MODS, "mod_editor_recent_projects.cfg")
if os.path.isfile(rp):
    raw = open(rp, "rb").read()
    line("最近工程记录无 CR（已归一化 LF）", b"\r" not in raw,
         "CR 个数 %d" % raw.count(b"\r"))
    line("最近工程记录含本包", NAME.encode("utf-8") in raw)

print("=" * 74)
if fails:
    print("结果：FAIL -> %s" % fails)
    raise SystemExit(3)
print("结果：全部 PASS")
