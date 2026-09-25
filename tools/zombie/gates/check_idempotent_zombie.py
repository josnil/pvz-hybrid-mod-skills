# -*- coding: utf-8 -*-
"""连续性幂等校验：连跑「暴走舞王伽刚特尔投石车僵尸」生成器 3 次，比较全部产物的 sha1。

另外验证两件事：
  · 历史改名文件（不再产出的旧路径）会被 sweep_stale_files 清掉；
  · Mods/ 镜像目录与工作区构建目录内容一致（含 Runtime/ModAssembly.dll）。
"""
import hashlib
import os
import subprocess
import sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GEN = os.path.join(WS, "build_zombie_disco_pult.py")
MODS = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
NAME = "暴走舞王伽刚特尔投石车僵尸"
KEY = "ZombieDiscoGargantuarPult"
BUILD = os.path.join(WS, "DiscoGargantuarPult")
PKG = os.path.join(BUILD, "Resources", "Characters", "Zombies", KEY)

TARGETS = [
    (f"dist/{NAME}.pmod", os.path.join(WS, "dist", f"{NAME}.pmod")),
    ("DiscoGargantuarPult/mod.json", os.path.join(BUILD, "mod.json")),
    (f"DiscoGargantuarPult/{NAME}.pvzmodeproject",
     os.path.join(BUILD, f"{NAME}.pvzmodeproject")),
    (".../Scene/ZombieDiscoGargantuarPult.tscn",
     os.path.join(PKG, "Scene", f"{KEY}.tscn")),
    (".../Scene/ZombieDiscoGargantuarPultComponentSet.tres",
     os.path.join(PKG, "Scene", f"{KEY}ComponentSet.tres")),
    (".../Scene/ZombieDiscoGargantuarPultFireComponentDefinition.tres",
     os.path.join(PKG, "Scene", f"{KEY}FireComponentDefinition.tres")),
    (".../Sprite/ZombieDiscoGargantuarPult.tscn",
     os.path.join(PKG, "Sprite", f"{KEY}.tscn")),
    (".../Config/TowerDefenseZombieDiscoGargantuarPult.tres",
     os.path.join(PKG, "Config", f"TowerDefense{KEY}.tres")),
    (".../Packet/ZombieDiscoGargantuarPult.tres",
     os.path.join(PKG, "Packet", f"{KEY}.tres")),
    (f"Resources/Cards/{KEY}.tres",
     os.path.join(BUILD, "Resources", "Cards", f"{KEY}.tres")),
    (f"Mods/{NAME}.pmod", os.path.join(MODS, f"{NAME}.pmod")),
    ("Mods/enabled_mods.json", os.path.join(MODS, "enabled_mods.json")),
    ("Mods/mod_editor_recent_projects.cfg", os.path.join(MODS, "..", "mod_editor_recent_projects.cfg")),
    # 托管运行时程序集（由 runtime_src_zombie/build_runtime.py 产出，生成器只负责搬运与镜像）
    ("DiscoGargantuarPult/Runtime/ModAssembly.dll", os.path.join(BUILD, "Runtime", "ModAssembly.dll")),
    (f"Mods/{NAME}/Runtime/ModAssembly.dll", os.path.join(MODS, NAME, "Runtime", "ModAssembly.dll")),
]


def sha(p):
    if not os.path.isfile(p):
        return "<missing>"
    return hashlib.sha1(open(p, "rb").read()).hexdigest()


# --- 先埋两个「历史改名」的假旧产物，验证增量清理真的会清掉它们 -------------------
STALE = [
    os.path.join(BUILD, "Resources", "Cards", "ZombieDiscoGargantuarPultPacket.tres"),
    os.path.join(PKG, "Scene", "OldZombieDiscoGargantuarPult.tscn"),
    os.path.join(BUILD, "Localization", "translations.csv"),
]
for p in STALE:
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write("stale\n")
print("已埋 %d 个假旧产物用于验证增量清理" % len(STALE))

runs = []
for i in range(3):
    r = subprocess.run([PY, GEN], cwd=WS, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    ok = (r.returncode == 0)
    runs.append({label: sha(p) for label, p in TARGETS})
    runs[-1]["__exit__"] = r.returncode
    print(f"run{i+1}: exit={r.returncode}  " + ("OK" if ok else "FAILED"))
    if not ok:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        sys.exit(1)

print()
allok = True
for label, _ in TARGETS:
    vals = [r[label] for r in runs]
    same = len(set(vals)) == 1
    allok &= same
    flag = "OK  " if same else "DIFF"
    print(f"  [{flag}] {label:56s} {vals[0][:12]}")

print()
stale_left = [p for p in STALE if os.path.exists(p)]
if stale_left:
    allok = False
    print("  [DIFF] 假旧产物没被清理：")
    for p in stale_left:
        print("         ", os.path.relpath(p, WS))
else:
    print("  [OK  ] 增量清理生效：3 个假旧产物已被 sweep_stale_files 删掉")

# --- Mods 镜像与工作区构建目录逐字节一致（除 .pvzmodeproject 也是同步的） -----------
mirror_mismatch = []
mirror_root = os.path.join(MODS, NAME)
for r, dirs, files in os.walk(BUILD):
    for fn in files:
        src = os.path.join(r, fn)
        rel = os.path.relpath(src, BUILD)
        dst = os.path.join(mirror_root, rel)
        if not os.path.isfile(dst) or sha(src) != sha(dst):
            mirror_mismatch.append(rel)
if mirror_mismatch:
    allok = False
    print("  [DIFF] Mods 镜像与构建目录不一致：", mirror_mismatch[:10])
else:
    print("  [OK  ] Mods 镜像与工作区构建目录逐字节一致")

print()
print("幂等结论：", "全部字节稳定（3 连跑一致）" if allok else "存在不稳定产物！")
sys.exit(0 if allok else 1)
