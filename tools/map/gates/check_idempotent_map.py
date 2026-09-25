# -*- coding: utf-8 -*-
"""连续性幂等校验：连跑地图生成器 3 次，比较产物的 sha1 是否每次都一样。"""
import hashlib, os, subprocess, sys

WS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
GEN = os.path.join(WS, "build_map_vampire_pool.py")
MODS = os.path.join(os.environ.get("APPDATA", ""), "Godot",
                    "app_userdata", "植物大战僵尸杂交版", "Mods")
NAME = "吸血鬼屋泳池"
BUILD = os.path.join(WS, "VampirePool")

TARGETS = [
    ("dist/吸血鬼屋泳池.pmod", os.path.join(WS, "dist", NAME + ".pmod")),
    ("VampirePool/mod.json", os.path.join(BUILD, "mod.json")),
    ("VampirePool/吸血鬼屋泳池.pvzmodeproject", os.path.join(BUILD, NAME + ".pvzmodeproject")),
    ("VampirePool/Resources/Maps/VampirePool.tres",
     os.path.join(BUILD, "Resources", "Maps", "VampirePool.tres")),
    ("Mods/吸血鬼屋泳池.pmod", os.path.join(MODS, NAME + ".pmod")),
    ("Mods/吸血鬼屋泳池/Resources/Maps/VampirePool.tres",
     os.path.join(MODS, NAME, "Resources", "Maps", "VampirePool.tres")),
    ("Mods/enabled_mods.json", os.path.join(MODS, "enabled_mods.json")),
    ("Mods/mod_editor_recent_projects.cfg",
     os.path.join(os.path.dirname(MODS), "mod_editor_recent_projects.cfg")),
]


def sha(p):
    if not os.path.isfile(p):
        return "<missing>"
    return hashlib.sha1(open(p, "rb").read()).hexdigest()


runs = []
for i in range(3):
    r = subprocess.run([PY, GEN], cwd=WS, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    runs.append({label: sha(p) for label, p in TARGETS})
    print("run%d: exit=%d  %s" % (i + 1, r.returncode, "OK" if r.returncode == 0 else "FAILED"))
    if r.returncode != 0:
        print(r.stdout[-2500:])
        print(r.stderr[-1500:])
        sys.exit(1)

print()
allok = True
for label, _ in TARGETS:
    vals = [r[label] for r in runs]
    same = len(set(vals)) == 1
    allok &= same
    print("  [%s] %-52s %s" % ("OK  " if same else "DIFF", label, vals[0][:12]))

print()
print("幂等结论：", "全部字节稳定（3 连跑一致）" if allok else "存在不稳定产物！")
sys.exit(0 if allok else 1)
