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

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)

DOTNET = r"C:\Program Files\dotnet\dotnet.exe"
REF_DIRS = [
    ("remake", r"D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64"),
    ("console", r"D:\zzz\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64"),
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
