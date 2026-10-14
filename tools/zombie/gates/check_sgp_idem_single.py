# -*- coding: utf-8 -*-
"""幂等性验证（单帧素材版）：
   跑两遍 build_plant_super_gatling.py，断言 14 个产物文件的字节【完全一致】。

⚠️ 与 check_sgp_idempotent.py 的区别：那个脚本断言「第二次跑没有变化」，
   本脚本直接前后各取一次 sha256 + size 做逐字节比对，覆盖三件套 + 场景 + 包。
"""
import hashlib
import os
import subprocess
import sys
# --- 本机路径适配（自动注入；换机器只改 tools/_env.py）---
import os as _os
import sys as _sys

_TOOLS = _os.path.dirname(_os.path.abspath(__file__))
while not _os.path.isfile(_os.path.join(_TOOLS, "_env.py")):
    _parent = _os.path.dirname(_TOOLS)
    if _parent == _TOOLS:
        break
    _TOOLS = _parent
if _TOOLS not in _sys.path:
    _sys.path.insert(0, _TOOLS)
_PIPE = _os.path.join(_TOOLS, 'zombie')
if _os.path.isdir(_PIPE) and _PIPE not in _sys.path:
    _sys.path.insert(0, _PIPE)

from _env import (  # noqa: E402
    GAME, UNPACK, CLASSIC, MODS, USER_DATA_DIR, PY, WORKSPACE, REF_DIR,
    require_ref_dir, require_classic, ensure_mods, unpack_status, describe,
)
try:  # 从属脚本：向上找 _gen.py 定位本流水线的工作区
    from _gen import MOD_WORKSPACE  # noqa: F401,E402
except ImportError:
    MOD_WORKSPACE = None
# --- 适配块结束 ---

WS = MOD_WORKSPACE
BUILD = os.path.join(WS, "build_plant_super_gatling.py")
PY = PY

PROJ = os.path.join(WS, "SuperGatlingPea")
DIST = os.path.join(WS, "dist")

TARGETS = [
    os.path.join(PROJ, "mod.json"),
    os.path.join(PROJ, "Localization", "translations.csv"),
    os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPea.dat"),
    os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPea.tres"),
    os.path.join(PROJ, "Resources", "Animations", "SuperGatlingPeaAtlas.png"),
    os.path.join(PROJ, "Resources", "Cards", "SuperGatlingPea.tres"),
    os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea", "Config",
                 "TowerDefensePlantSuperGatlingPea.tres"),
    os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea", "Packet",
                 "SuperGatlingPea.tres"),
    os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea", "Scene",
                 "SuperGatlingPea.tscn"),
    os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea", "Scene",
                 "SuperGatlingPeaComponentSet.tres"),
    os.path.join(PROJ, "Resources", "Characters", "Plants", "SuperGatlingPea", "Sprite",
                 "SuperGatlingPea.tscn"),
    os.path.join(PROJ, "Runtime", "ModAssembly.dll"),
    os.path.join(DIST, "超级机枪射手.pmod"),
]


def snap():
    out = {}
    for p in TARGETS:
        if not os.path.exists(p):
            out[p] = ("MISSING", -1)
            continue
        b = open(p, "rb").read()
        out[p] = (hashlib.sha256(b).hexdigest(), len(b))
    return out


def run_build(tag):
    r = subprocess.run([PY, BUILD], cwd=WS, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    print("[%s] rc=%d" % (tag, r.returncode))
    if r.returncode != 0:
        print(r.stdout[-3000:])
        print(r.stderr[-3000:])
        sys.exit(1)
    return r.stdout


print("=" * 78)
print("幂等验证：两遍构建，逐字节比对 %d 个产物" % len(TARGETS))
print("=" * 78)

run_build("run1")
a = snap()
run_build("run2")
b = snap()

bad = 0
for p in TARGETS:
    rel = os.path.relpath(p, WS)
    ha, sa = a[p]
    hb, sb = b[p]
    if ha == hb and sa == sb:
        print("  [一致] %10d  %s  %s" % (sa, ha[:16], rel))
    else:
        bad += 1
        print("  [★不同] %s" % rel)
        print("           run1=%s (%d)" % (ha[:16], sa))
        print("           run2=%s (%d)" % (hb[:16], sb))

print()
print("RESULT: %d 一致 / %d 不同  ->  %s" % (len(TARGETS) - bad, bad,
                                             "幂等 ✔" if bad == 0 else "非幂等 ✘"))
sys.exit(1 if bad else 0)
