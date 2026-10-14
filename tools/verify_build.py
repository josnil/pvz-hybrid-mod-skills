# -*- coding: utf-8 -*-
"""构建验证三件套（本项目 R9/R16/R20 三次踩坑后固化）。

用法：
    python pvz-hybrid-mod-skills/tools/verify_build.py            # 验证全部 Mod
    python pvz-hybrid-mod-skills/tools/verify_build.py FpsDisplay # 只验证指定 Mod

它检查每一步都不可省的 3 件事：

  ① 编译：源码比 DLL 新？（时间戳）
  ② 打包：dist 包比源码新？装机包 == dist 包？（sha256）
  ③ 内容：包内 mod.json 与源码逐字段比对（version / author / runtimeApiVersion /
     settings 数量与键集合 / playInstructions / resources）

**为什么需要它**（三次真实事故）：
  R9   build_mod.py 硬编码 runtimeApiVersion=1  ⇒ 4 个 Mod 打包被拒
  R16  build_mod.py 每次构建重写 mod.json      ⇒ 元信息被清（构建即回退）
  R20  build_pmod.py 同样硬编码 API=1          ⇒ 6 个 Mod 打包静默失败，包长期陈旧

共同教训：**只看构建脚本的输出不算验证**（过滤输出会把「打包失败，终止。」吞掉）。
"""
import hashlib
import json
import os
import pathlib
import sys
import time
import zipfile

WS = pathlib.Path(__file__).resolve().parents[2]          # …/植物大战僵尸杂交重制版
MODS = WS / "mods"
USER_MODS = pathlib.Path(os.environ.get("APPDATA", "")) / "Godot" / "app_userdata" / "植物大战僵尸杂交版" / "Mods"

ONLY = sys.argv[1] if len(sys.argv) > 1 else None

ok_all = True


def fail(msg):
    global ok_all
    ok_all = False
    print("      ❌ " + msg)


def note(msg):
    print("      · " + msg)


for d in sorted(MODS.iterdir()):
    if not d.is_dir() or (ONLY and d.name != ONLY):
        continue
    mj = d / "mod.json"
    if not mj.is_file():
        continue

    print(f"\n  === {d.name} ===")
    src = json.loads(mj.read_text(encoding="utf-8"))

    # ── ① 编译产物是否新于源码 ────────────────────────────────
    dll = d / "Runtime" / "ModAssembly.dll"
    if not dll.is_file():
        fail("缺少 Runtime/ModAssembly.dll")
        continue
    newest_cs = max((p.stat().st_mtime for p in (d / "runtime_src").rglob("*.cs")
                     if "obj" not in p.parts), default=0)
    if dll.stat().st_mtime < newest_cs:
        fail(f"DLL 比源码旧（源码 {time.strftime('%m-%d %H:%M', time.localtime(newest_cs))} > "
             f"DLL {time.strftime('%m-%d %H:%M', time.localtime(dll.stat().st_mtime))}）⇒ 没重新编译")
    else:
        note("编译：DLL 新于源码 ✓")

    # ── ② dist 包 / 装机包 ───────────────────────────────────
    dist = d / "dist" / f"{d.name}.pmod"
    inst = USER_MODS / f"{d.name}.pmod"
    if not dist.is_file():
        fail("没有 dist/*.pmod")
        continue
    if dist.stat().st_mtime < newest_cs:
        fail("dist 包比源码旧 ⇒ 打包被跳过/失败（查 build_pmod.py 是否提前 return）")
    else:
        note(f"打包：dist {time.strftime('%m-%d %H:%M', time.localtime(dist.stat().st_mtime))} ✓")
    if not inst.is_file():
        fail("装机目录里没有这个包（未安装）")
        continue
    hd = hashlib.sha256(dist.read_bytes()).hexdigest()
    hi = hashlib.sha256(inst.read_bytes()).hexdigest()
    if hd != hi:
        fail("装机包 ≠ dist 包 ⇒ 装机那步没跑（--install 漏了？）")
    else:
        note("装机：dist == 装机（sha256 一致）✓")

    # ── ③ 包内 mod.json 与源码逐字段比对 ────────────────────
    try:
        with zipfile.ZipFile(inst) as z:
            j = json.loads(z.read("mod.json").decode("utf-8"))
    except Exception as ex:
        fail("读包内 mod.json 失败：" + str(ex))
        continue

    for k, label in (("version", "版本"), ("author", "作者"),
                     ("runtimeApiVersion", "API 版本"), ("runtimeEntryType", "入口类")):
        if j.get(k) != src.get(k):
            fail(f"包内 {label} 与源码不一致：包={j.get(k)!r} 源码={src.get(k)!r}")

    ss = [s.get("key") for s in (src.get("settings") or [])]
    ps = [s.get("key") for s in (j.get("settings") or [])]
    if ss != ps:
        fail(f"配置项不一致：包内 {len(ps)} 项 / 源码 {len(ss)} 项；"
             f"缺少={sorted(set(ss) - set(ps))} 多余={sorted(set(ps) - set(ss))}")
    else:
        note(f"内容：version/author/API/入口 一致，配置项 {len(ss)} 项一致 ✓")

    if bool(j.get("playInstructions")) != bool(src.get("playInstructions")):
        fail("playInstructions 有无不一致")

    # resources 清单（宿主会校验）
    if (j.get("resources") or []) != (src.get("resources") or []):
        fail(f"resources 清单不一致：包={j.get('resources')} 源码={src.get('resources')}")

print()
print("  " + "=" * 60)
print("  ✅ 全部通过（编译 / 打包 / 装机 / 包内容 三件套）" if ok_all
      else "  ❌ 存在问题（见上面 ❌ 行）")
sys.exit(0 if ok_all else 1)
