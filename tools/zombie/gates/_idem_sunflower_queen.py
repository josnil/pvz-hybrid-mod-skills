# -*- coding: utf-8 -*-
"""幂等验证：记录产物指纹 → 重跑生成器 → 比较字节是否变化。

用法：python .cache/_idem_sunflower_queen.py
"""
from __future__ import annotations

import hashlib
import io
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

PY = PY
WS = MOD_WORKSPACE
PMOD = os.path.join(WS, "dist", "向日葵女王僵尸.pmod")
DLL = os.path.join(WS, "SunFlowerQueen", "Runtime", "ModAssembly.dll")
MODS = _os.path.join(MODS, "向日葵女王僵尸")
MODS_DLL = os.path.join(MODS, "Runtime", "ModAssembly.dll")


def h(p):
    with io.open(p, "rb") as f:
        b = f.read()
    return len(b), hashlib.sha256(b).hexdigest()[:16]


def snap():
    out = {}
    for name, p in (("dist.pmod", PMOD), ("src.dll", DLL), ("mods.dll", MODS_DLL)):
        out[name] = h(p) if os.path.isfile(p) else None
    return out


def w(s):
    sys.stdout.write(s + "\n")


a = snap()
w("--- 第一次指纹 ---")
for k in a:
    w("  %-10s %s" % (k, a[k]))

r = subprocess.run([PY, os.path.join(WS, "build_zombie_sunflower_queen.py")],
                   cwd=WS, capture_output=True, text=True, encoding="utf-8")
if r.returncode != 0:
    w("!! 生成器重跑失败 rc=%d" % r.returncode)
    w(r.stdout or "")
    w(r.stderr or "")
    raise SystemExit(1)

b = snap()
w("--- 第二次指纹 ---")
for k in b:
    w("  %-10s %s" % (k, b[k]))

bad = 0
for k in a:
    if a[k] != b[k]:
        w("!! %s 字节变了：%s -> %s" % (k, a[k], b[k]))
        bad += 1
w("=" * 60)
if bad:
    w("幂等验证 FAIL：%d 处变化" % bad)
    raise SystemExit(1)
w("幂等验证通过：三处产物字节完全一致")

# 顺带跑编译器的 --check
bc = os.path.join(WS, "runtime_src_zombie_sunflower_queen", "build_runtime.py")
if os.path.isfile(bc):
    r2 = subprocess.run([PY, bc, "--check"], cwd=os.path.dirname(bc),
                        capture_output=True, text=True, encoding="utf-8")
    w("--- build_runtime.py --check ---")
    w((r2.stdout or "").strip())
    if r2.stderr:
        w((r2.stderr or "").strip())
