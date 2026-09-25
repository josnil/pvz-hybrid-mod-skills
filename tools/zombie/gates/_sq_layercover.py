# -*- coding: utf-8 -*-
"""判定：tscn 里每个 head 类节点的 LayerVisible 覆盖是否完整。
   缺失的层名 ⇒ _layerVisible 保持初值 = true ⇒ 仍会绘制（这就是「多出来一个头」的典型成因）。"""
import io
import re
import sys

TRES = (r"D:/zzz/pvzHE/解包/植物大战僵尸杂交版V0.28/Asset/Anime/Character/Plant/"
        r"Gold/QueenSunFlower/QueenSunFlower.tres")
TSCN = (r"D:/zzz/pvzHE/解包/植物大战僵尸杂交版/Asset/Anime/Character/Zombie/"
        r".workbuddy/ModWorkspace/SunFlowerQueen/Resources/Characters/Zombies/"
        r"ZombieSunFlowerQueen/Sprite/ZombieSunFlowerQueen.tscn")

t = io.open(TRES, encoding="utf-8", errors="replace").read()
s = io.open(TSCN, encoding="utf-8", errors="replace").read()

m = re.search(r"^layerDictionary = \{(.*?)^\}", t, re.S | re.M)
layer = {}
for ln in m.group(1).strip().splitlines():
    mm = re.match(r'^"(.+?)":\s*(\d+),?$', ln.strip())
    if mm:
        layer[mm.group(1)] = int(mm.group(2))
MAXID = max(layer.values())
sys.stdout.write("layerDictionary: %d 个名字，id 0..%d\n" % (len(layer), MAXID))
id2name = {v: k for k, v in layer.items()}
sys.stdout.write("id->名字: %s\n\n" % ", ".join(
    "%d=%r" % (i, id2name.get(i, "?")) for i in range(MAXID + 1)))

# 切分 tscn 的节点块
blocks = re.split(r"^\[node ", s, flags=re.M)
for b in blocks[1:]:
    head = b.split("]", 1)[0]
    nm = re.search(r'name="([^"]+)"', head)
    node = nm.group(1) if nm else "?"
    if node not in ("HeadShadow", "Head", "Aura"):
        continue
    body = b.split("]", 1)[1]
    seen = {}
    # ⚠️ 属性名可能被**整条**加引号（`"Animation/LayerVisible/图层_1" = false`）⇒
    #    必须先把整条 key 的引号剥掉，否则会把 `图层_1"` 当成层名（曾因此误报「缺失」）。
    for mm in re.finditer(r'^\s*("?)(Animation/LayerVisible/(.*?))\1\s*=\s*(\w+)', body, re.M):
        seen[mm.group(3)] = mm.group(4)
    # 注意：Godot 属性名里的引号形式 "图层_1" 已由上面剥掉 => 名字原样
    sys.stdout.write("\n== 节点 %s：写了 %d 条 LayerVisible ==\n" % (node, len(seen)))
    miss = [id2name[i] for i in range(MAXID + 1)
            if id2name.get(i) is not None and id2name[i] not in seen]
    sys.stdout.write("   缺失（⇒ 默认 true = 会绘制）: %s\n"
                     % (", ".join(repr(x) for x in miss) if miss else "(无)"))
    extra = [k for k in seen if k not in layer]
    sys.stdout.write("   多余（字典里没有，写了个寂寞）: %s\n"
                     % (", ".join(repr(x) for x in extra) if extra else "(无)"))
    on = [k for k, v in seen.items() if v == "true"]
    sys.stdout.write("   显式 true 的层: %s\n"
                     % (", ".join(repr(x) for x in on) if on else "(无)"))
    off = [k for k, v in seen.items() if v == "false" and k in layer]
    sys.stdout.write("   显式 false 的层数: %d\n" % len(off))
