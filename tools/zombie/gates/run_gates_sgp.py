# -*- coding: utf-8 -*-
"""离线闸门运行器（「超级机枪读报僵尸」）。

对**两份**游戏构建各跑一遍 runtime_src_zombie_super_gatling/check_gates_super_gatling_paper.cs，
输出落 .cache/_out_gates_sgp_<tag>.txt，方便回看与归档。

用法:
    python .cache/run_gates_sgp.py
退出码: 0 = 两份都全绿；1 = 有 FAIL；2 = 编译失败 / 环境问题
"""
import os
import subprocess
import sys

WS = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版\Asset\Anime\Character\Zombie\.workbuddy\ModWorkspace"
SRC = os.path.join(WS, "runtime_src_zombie_super_gatling")
SCRIPT = os.path.join(SRC, "check_gates_super_gatling_paper.cs")
PROJ = os.path.join(WS, "SuperGatlingPaper")
PMOD = os.path.join(WS, "dist", "超级机枪读报僵尸.pmod")
GAME_ROOT = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
ENTRY = "SuperGatlingPaperRuntimeEntry"

# 两份构建的 PlantsVsZombies.dll 字节不同，都必须验。
BUILDS = [
    ("remake", r"D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64"),
    ("console", r"D:\zzz\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64"),
]


def run(ref, tag):
    cmd = ["dotnet", "run", "--file", SCRIPT, "--", ref, PROJ, PMOD, ENTRY, GAME_ROOT]
    # ⚠️ 本机偶发 CoreCLR 起不来（`GC heap initialization failed` / `0xC0000142`），
    #    属**环境故障**，不是断言失败。判据：rc != 0 且一条 PASS/FAIL 都没打印出来。
    #    这种情况重试一次；仍失败则归类为环境故障（exit 2），绝不混进「构建不通过」。
    lines, err, rc = [], [], -1
    for attempt in (1, 2):
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", cwd=SRC)
        out = (r.stdout or "").splitlines()
        lines = [ln for ln in out if " warning " not in ln]
        err = [ln for ln in (r.stderr or "").splitlines() if " warning " not in ln]
        rc = r.returncode
        if any(ln.strip().startswith(("PASS", "FAIL", "SKIP")) for ln in lines):
            break
        if attempt == 1:
            print("[%s] 第 1 次没产出任何断言（rc=%s）⇒ 判定为环境故障，重试…" % (tag, rc))
            for ln in err[:3]:
                print("        stderr: " + ln.strip())
    dst = os.path.join(WS, ".cache", "_out_gates_sgp_" + tag + ".txt")
    with open(dst, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines))
        if err:
            f.write("\n--- stderr ---\n" + "\n".join(err))
    npass = sum(1 for ln in lines if ln.strip().startswith("PASS"))
    nfail = sum(1 for ln in lines if ln.strip().startswith("FAIL"))
    nskip = sum(1 for ln in lines if ln.strip().startswith("SKIP"))
    infra = (npass == 0 and nfail == 0)
    print("[%s] rc=%s PASS=%d FAIL=%d SKIP=%d%s -> %s"
          % (tag, rc, npass, nfail, nskip, "  ★环境故障" if infra else "", dst))
    for ln in lines:
        if ln.strip().startswith("FAIL"):
            print("   " + ln.strip())
        if "error CS" in ln:
            print("   " + ln.strip())
    return rc, nfail, lines, infra


def main():
    bad = 0
    compile_err = False
    infra_err = False
    for tag, ref in BUILDS:
        if not os.path.isdir(ref):
            print("[%s] 跳过（构建目录不存在）: %s" % (tag, ref))
            continue
        rc, nfail, lines, infra = run(ref, tag)
        if any("error CS" in ln for ln in lines):
            compile_err = True
        if infra:
            infra_err = True
            continue
        if rc != 0 or nfail:
            bad += 1
    if infra_err:
        print("环境故障（CoreCLR 未能启动，非断言失败）⇒ 稍后重跑，别当成代码问题")
        return 2
    if compile_err:
        print("编译失败 ⇒ 先修源码")
        return 2
    print("总结: " + ("全绿 ✔" if bad == 0 else "有 %d 份构建不通过 ✗" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
