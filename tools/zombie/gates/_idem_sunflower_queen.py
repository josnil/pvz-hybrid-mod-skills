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

PY = r"C:/Users/yanxulin002/.workbuddy/binaries/python/versions/3.13.12/python.exe"
WS = r"D:/zzz/pvzHE/解包/植物大战僵尸杂交版/Asset/Anime/Character/Zombie/.workbuddy/ModWorkspace"
PMOD = os.path.join(WS, "dist", "向日葵女王僵尸.pmod")
DLL = os.path.join(WS, "SunFlowerQueen", "Runtime", "ModAssembly.dll")
MODS = r"C:/Users/yanxulin002/AppData/Roaming/Godot/app_userdata/植物大战僵尸杂交版/Mods/向日葵女王僵尸"
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
