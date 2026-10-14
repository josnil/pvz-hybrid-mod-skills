# -*- coding: utf-8 -*-
"""离线闸门运行器（「超级机枪射手」植物 Mod）。

对**两份**游戏构建各跑一遍 runtime_src_plant/check_gates_plant.cs，
输出落 .cache/_out_gates_skin.txt / _out_gates_skin_console.txt。

用法:
    python .cache/run_gates_plant.py
退出码: 0 = 两份都全绿；1 = 有 FAIL；2 = 编译失败 / 环境问题
"""
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
_PIPE = _os.path.join(_TOOLS, 'plant')
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
SRC = os.path.join(WS, "runtime_src_plant")
SCRIPT = os.path.join(SRC, "check_gates_plant.cs")
PROJ = os.path.join(WS, "SuperGatlingPea")
PMOD = os.path.join(WS, "dist", "超级机枪射手.pmod")
GAME_ROOT = UNPACK
ENTRY = "SuperGatlingPeaRuntimeEntry"

# 两份构建的 PlantsVsZombies.dll 字节不同，都必须验。
BUILDS = [
    ("ref", REF_DIR),   # 本机只有一份构建；原双构建（remake/console）已收敛成一份
    
]


def run(ref, tag):
    cmd = ["dotnet", "run", "--file", SCRIPT, "--", ref, PROJ, PMOD, ENTRY, GAME_ROOT]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=SRC)
    out = (r.stdout or "").splitlines()
    lines = [ln for ln in out if " warning " not in ln]
    err = [ln for ln in (r.stderr or "").splitlines() if " warning " not in ln]
    dst = os.path.join(WS, ".cache", "_out_gates_skin_%s.txt" % tag)
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        if err:
            f.write("\n--- stderr ---\n" + "\n".join(err))
    npass = sum(1 for ln in lines if ln.strip().startswith("PASS"))
    nfail = sum(1 for ln in lines if ln.strip().startswith("FAIL"))
    nskip = sum(1 for ln in lines if ln.strip().startswith("SKIP"))
    print("[%s] rc=%s PASS=%d FAIL=%d SKIP=%d -> %s" % (tag, r.returncode, npass, nfail, nskip, dst))
    for ln in lines:
        if ln.strip().startswith("FAIL"):
            print("   " + ln.strip())
        if "error CS" in ln:
            print("   " + ln.strip())
    return r.returncode, nfail, lines


def main():
    bad = 0
    compile_err = False
    ran = 0
    for tag, ref in BUILDS:
        if not os.path.isdir(ref):
            print("[%s] 跳过（构建目录不存在）: %s" % (tag, ref))
            continue
        ran += 1
        rc, nfail, lines = run(ref, tag)
        if any("error CS" in ln for ln in lines):
            compile_err = True
        if rc != 0 or nfail:
            bad += 1
    if compile_err:
        print("编译失败 ⇒ 先修源码")
        return 2
    if ran == 0:
        print("两份构建目录都不存在 ⇒ 无法验证（环境问题）")
        return 2
    print("总结: " + ("全绿 ✔" if bad == 0 else "有 %d 份构建不通过 ✗" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
