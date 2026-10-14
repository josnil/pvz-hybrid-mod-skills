#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线跑 runtime_src/check_entry.cs，校验本包 DLL 能被 ModLoader 认出来。

- 与 runtime_src/check_gates*.cs 同一套路：dotnet run --file，不落中间产物。
- 只读；不删任何文件。
用法：python .cache/run_entry_sgp.py
"""
from __future__ import annotations

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

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)

DOTNET = r"C:\Program Files\dotnet\dotnet.exe"
REF_DIRS = [
    ("ref", REF_DIR),   # 本机只有一份构建
    
]
MOD_DLL = os.path.join(WS, "SuperGatlingPaper", "Runtime", "ModAssembly.dll")
ENTRY = "SuperGatlingPaperRuntimeEntry"
SRC = os.path.join(WS, "runtime_src", "check_entry.cs")


def main() -> int:
    if not os.path.isfile(SRC):
        print("[FAIL] 缺 " + SRC)
        return 3
    if not os.path.isfile(MOD_DLL):
        print("[FAIL] 缺 " + MOD_DLL)
        return 3
    rc_all = 0
    for tag, ref in REF_DIRS:
        if not os.path.isdir(ref):
            print(f"[{tag}] 跳过：引用目录不存在 {ref}")
            continue
        proc = subprocess.run(
            [DOTNET, "run", "--file", SRC, "--", ref, MOD_DLL, ENTRY],
            cwd=os.path.join(WS, "runtime_src"),
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        out = "\n".join(l for l in (proc.stdout or "").splitlines() if " warning " not in l)
        dst = os.path.join(HERE, f"_out_entry_sgp_{tag}.txt")
        io.open(dst, "w", encoding="utf-8", newline="\n").write(out + "\n")
        npass = out.count("  PASS  ")
        nfail = out.count("  FAIL  ")
        print(f"[{tag}] rc={proc.returncode} PASS={npass} FAIL={nfail} -> {dst}")
        if nfail:
            for l in out.splitlines():
                if "  FAIL  " in l:
                    print("    " + l.strip())
        rc_all |= (proc.returncode or 0)
    print("总结: " + ("全绿 ✔" if rc_all == 0 else "有失败 ✗"))
    return rc_all


if __name__ == "__main__":
    sys.exit(main())
