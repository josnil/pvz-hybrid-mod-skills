#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""编译「吸血鬼屋泳池」Mod 的托管运行时程序集 Runtime/ModAssembly.dll。

为什么要单独编译：
  战斗里的地图背景来自地图场景里 Sprite2D 的 [ext_resource] 内置贴图，Mod 自己的图片
  没有可被 ResourceLoader 按路径加载的通道，所以必须靠托管运行时在运行期换贴图。
  入口类型 VampirePoolRuntimeEntry 实现 IXWModRuntimeEntry（在 PlantsVsZombies.dll 里），
  所以必须引用游戏的 GodotSharp.dll + PlantsVsZombies.dll。

用法：python build_runtime.py [--check] [--godot-ref-dir <dir>]
  --check   编译两次并比对字节，验证可重现（幂等）
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(HERE)
MOD_DIR = os.path.join(WORKSPACE, "VampirePool")
TARGET_DLL = os.path.join(MOD_DIR, "Runtime", "ModAssembly.dll")

DEFAULT_REF_DIR = (
    r"D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版"
    r"\data_PlantsVsZombies_windows_x86_64"
)
FALLBACK_REF_DIRS = [
    DEFAULT_REF_DIR,
    r"D:\zzz\植物大战僵尸杂交重制版"
    r"\data_PlantsVsZombies_windows_x86_64",
]


def find_dotnet() -> str:
    for cand in (
        r"C:\Program Files\dotnet\dotnet.exe",
        shutil.which("dotnet"),
    ):
        if cand and os.path.isfile(cand):
            return cand
    raise SystemExit("找不到 dotnet.exe（需要 .NET SDK 才能编译运行时程序集）")


def pick_ref_dir(explicit: str | None) -> str:
    if explicit:
        if not os.path.isdir(explicit):
            raise SystemExit("--godot-ref-dir 不存在：" + explicit)
        return explicit
    for d in FALLBACK_REF_DIRS:
        if os.path.isfile(os.path.join(d, "GodotSharp.dll")) and os.path.isfile(
            os.path.join(d, "PlantsVsZombies.dll")
        ):
            return d
    raise SystemExit("找不到含 GodotSharp.dll / PlantsVsZombies.dll 的目录")


def build(dotnet: str, ref_dir: str, out_dir: str) -> None:
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    cmd = [
        dotnet,
        "build",
        os.path.join(HERE, "VampirePoolRuntime.csproj"),
        "-c",
        "Release",
        "-o",
        out_dir,
        "-p:GodotRefDir=" + ref_dir,
        "--nologo",
        "-v",
        "quiet",
    ]
    proc = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.stdout.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        raise SystemExit("dotnet build 失败，exit=%d" % proc.returncode)
    warn = [ln for ln in (proc.stdout + proc.stderr).splitlines() if "warning" in ln.lower()]
    for ln in warn:
        print("   build warning:", ln.strip())


def sha256(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def install(out_dir: str) -> str:
    src = os.path.join(out_dir, "ModAssembly.dll")
    if not os.path.isfile(src):
        raise SystemExit("编译产物里没有 ModAssembly.dll：" + out_dir)
    os.makedirs(os.path.dirname(TARGET_DLL), exist_ok=True)
    # 内容相同就不写盘（保持 mtime，便于幂等校验）
    data = open(src, "rb").read()
    if os.path.isfile(TARGET_DLL) and open(TARGET_DLL, "rb").read() == data:
        return "未变"
    with open(TARGET_DLL, "wb") as fh:
        fh.write(data)
    return "已写入"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="编译两次比对字节，验证可重现")
    ap.add_argument("--godot-ref-dir", default=None)
    args = ap.parse_args()

    dotnet = find_dotnet()
    ref_dir = pick_ref_dir(args.godot_ref_dir)
    print("dotnet   :", dotnet)
    print("引用目录 :", ref_dir)

    out1 = os.path.join(HERE, ".build", "a")
    build(dotnet, ref_dir, out1)
    h1 = sha256(os.path.join(out1, "ModAssembly.dll"))
    print("第 1 次   大小=%d sha256=%s" % (os.path.getsize(os.path.join(out1, "ModAssembly.dll")), h1[:16]))

    if args.check:
        out2 = os.path.join(HERE, ".build", "b")
        build(dotnet, ref_dir, out2)
        h2 = sha256(os.path.join(out2, "ModAssembly.dll"))
        print("第 2 次   大小=%d sha256=%s" % (os.path.getsize(os.path.join(out2, "ModAssembly.dll")), h2[:16]))
        if h1 != h2:
            print("!! 两次编译字节不一致 —— 产物不可重现")
            return 1
        print("两次编译字节一致 ✓")

    state = install(out1)
    print("安装到   :", TARGET_DLL, "->", state)
    print("最终 sha256 =", sha256(TARGET_DLL)[:16])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
