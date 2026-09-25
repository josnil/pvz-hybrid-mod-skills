# -*- coding: utf-8 -*-
"""连续性幂等校验：连跑生成器 3 次，比较全部产物的 sha1 是否每次都一样。"""
import hashlib, os, subprocess, sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GEN = os.path.join(WS, "build_plant_super_gatling.py")
MODS = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
NAME = "超级机枪射手"
PKG = os.path.join(WS, "SuperGatlingPea", "Resources", "Characters", "Plants", "SuperGatlingPea")

TARGETS = [
    ("dist/超级机枪射手.pmod", os.path.join(WS, "dist", f"{NAME}.pmod")),
    ("SuperGatlingPea/mod.json", os.path.join(WS, "SuperGatlingPea", "mod.json")),
    ("SuperGatlingPea/超级机枪射手.pvzmodeproject",
     os.path.join(WS, "SuperGatlingPea", f"{NAME}.pvzmodeproject")),
    (".../Scene/SuperGatlingPeaComponentSet.tres",
     os.path.join(PKG, "Scene", "SuperGatlingPeaComponentSet.tres")),
    (".../Scene/SuperGatlingPea.tscn", os.path.join(PKG, "Scene", "SuperGatlingPea.tscn")),
    (".../Sprite/SuperGatlingPea.tscn", os.path.join(PKG, "Sprite", "SuperGatlingPea.tscn")),
    (".../Config/TowerDefensePlantSuperGatlingPea.tres",
     os.path.join(PKG, "Config", "TowerDefensePlantSuperGatlingPea.tres")),
    (".../Packet/SuperGatlingPea.tres", os.path.join(PKG, "Packet", "SuperGatlingPea.tres")),
    ("Resources/Cards/SuperGatlingPea.tres",
     os.path.join(WS, "SuperGatlingPea", "Resources", "Cards", "SuperGatlingPea.tres")),
    ("Mods/超级机枪射手.pmod", os.path.join(MODS, f"{NAME}.pmod")),
    ("Mods/enabled_mods.json", os.path.join(MODS, "enabled_mods.json")),
    ("SuperGatlingPea/Localization/translations.csv",
     os.path.join(WS, "SuperGatlingPea", "Localization", "translations.csv")),
    # 托管运行时程序集（由 runtime_src_plant/build_runtime.py 产出，生成器只负责搬运与镜像）
    ("SuperGatlingPea/Runtime/ModAssembly.dll",
     os.path.join(WS, "SuperGatlingPea", "Runtime", "ModAssembly.dll")),
    ("Mods/超级机枪射手/Runtime/ModAssembly.dll",
     os.path.join(MODS, NAME, "Runtime", "ModAssembly.dll")),
]


def sha(p):
    if not os.path.isfile(p):
        return "<missing>"
    return hashlib.sha1(open(p, "rb").read()).hexdigest()


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
    print(f"  [{flag}] {label:52s} {vals[0][:12]}")

print()
print("幂等结论：", "全部字节稳定（3 连跑一致）" if allok else "存在不稳定产物！")

# 旧产物必须已被清理（改名过的 SuperGatlingPeaPacket.tres 之类不能残留）
stale = []
for cand in [
    os.path.join(WS, "SuperGatlingPea", "Resources", "Cards", "SuperGatlingPeaPacket.tres"),
    os.path.join(WS, "SuperGatlingPea", "Resources", "Characters", "Plants", "SuperGatlingPea",
                 "Packet", "PlantSuperGatlingPea.tres"),
]:
    if os.path.exists(cand):
        stale.append(cand)
if stale:
    allok = False
    print("  [DIFF] 残留旧产物：", stale)
else:
    print("  [OK  ] 无残留旧产物（历史改名文件已清理）")

sys.exit(0 if allok else 1)
