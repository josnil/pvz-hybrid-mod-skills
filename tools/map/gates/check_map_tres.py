# -*- coding: utf-8 -*-
"""check_map_tres.py —— 对生成的 .tres 做「引用完整性 + 资源存在性 + 语义」独立复核。

这不是重复 verify_pmod.py：verify_pmod 只核对包结构与 ModLoader 规则，
本脚本专查 .tres 文本本身（悬空引用 / uid-path 配对 / res:// 是否存在 / 格子语义）。
"""
import io
import os
import re
import sys

UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
TRES = sys.argv[1] if len(sys.argv) > 1 else r"VampirePool\Resources\Maps\VampirePool.tres"

s = io.open(TRES, encoding="utf-8", newline="").read()
ok_all = True


def chk(cond, msg):
    global ok_all
    print(("  [ok] " if cond else "  [!!] ") + msg)
    if not cond:
        ok_all = False


print("=" * 78)
print("复核:", TRES)

# ---------- 1) 头部 ----------
head = s.split("\n")[0]
chk(head.startswith('[gd_resource type="Resource" script_class="TowerDefenseMapConfig"'),
    "头部 script_class = TowerDefenseMapConfig")
chk(' uid="' not in head, "头部未携带自身 uid（避免与官方资源 UID 冲突）")
chk("\r" not in s, "换行为 LF（与官方 .tres 一致）")
chk(not s.startswith("\ufeff"), "无 BOM")
chk(s.endswith("\n") and not s.endswith("\n\n"), "以单个换行收尾")

# ---------- 2) ext_resource 配对 ----------
ext = {}                      # id -> (type, uid, path)
for m in re.finditer(r'\[ext_resource type="([^"]+)" uid="([^"]+)" path="([^"]+)" id="([^"]+)"\]', s):
    ext[m.group(4)] = (m.group(1), m.group(2), m.group(3))
print("  ext_resource 共 %d 条" % len(ext))

# ---------- 3) sub_resource ----------
subs = {}
blocks = re.findall(r'\[sub_resource type="Resource" id="([^"]+)"\]\n((?:(?!\[sub_resource|\[resource\]).*\n)*)', s)
for sid, body in blocks:
    subs[sid] = body
print("  sub_resource 共 %d 条" % len(subs))

# ---------- 4) 引用完整性 ----------
used_ext = set(re.findall(r'ExtResource\("([^"]+)"\)', s))
used_sub = set(re.findall(r'SubResource\("([^"]+)"\)', s))
dangling_ext = sorted(used_ext - set(ext))
dangling_sub = sorted(used_sub - set(subs))
unused_ext = sorted(set(ext) - used_ext)
unused_sub = sorted(set(subs) - used_sub)
chk(not dangling_ext, "无悬空 ExtResource 引用（引用 %d 个）" % len(used_ext))
chk(not dangling_sub, "无悬空 SubResource 引用（引用 %d 个）" % len(used_sub))
chk(not unused_ext, "无未使用的 ext_resource")
chk(not unused_sub, "无未使用的 sub_resource（%d 条全部被 cellConfig 引用）" % len(subs))

# ---------- 5) res:// 资源真实存在 ----------
print("  --- res:// 存在性 ---")
resources = set(p for _t, _u, p in ext.values()) | set(re.findall(r'"(res://[^"]+)"', s))
for r in sorted(resources):
    rel = r.replace("res://", "").replace("/", os.sep)
    chk(os.path.exists(os.path.join(UNPACK, rel)), r)

# ---------- 6) cellConfig 里的每个格子 ----------
print("  --- 格子语义 ---")
arr = re.search(r'cellConfig = Array\[[^]]*\]\(\[(.*?)\]\)\n', s, re.S)
ids = re.findall(r'SubResource\("([^"]+)"\)', arr.group(1))
chk(len(ids) == len(subs) == 20, "cellConfig 恰好引用全部 20 个格子条目（实际 %d）" % len(ids))
chk(len(ids) == len(set(ids)), "cellConfig 中无重复条目")

WATER, AIR, GROUND = 3, 4, 2
DAY, NIGHT = 4, 8
GRID_W, GRID_H = 9, 6


def parse(sid):
    body = subs[sid]
    pos = [int(v) for v in re.search(r"pos = Vector4i\((\d+), (\d+), (\d+), (\d+)\)", body).groups()]
    g = re.search(r"gridType = Array\[int\]\(\[([\d, ]+)\]\)", body)
    gt = [int(v) for v in g.group(1).split(",")] if g else [GROUND, AIR]
    fl = int(re.search(r"ElementFlags = (\d+)", body).group(1))
    return pos, gt, fl


cells = [parse(i) for i in ids]
for pos, gt, fl in cells:
    chk(1 <= pos[0] <= GRID_W and 1 <= pos[1] <= GRID_H and pos[2] >= pos[0]
        and pos[3] >= pos[1] and pos[2] <= GRID_W and pos[3] <= GRID_H,
        "pos Vector4i%s 在 %dx%d 网格内" % (tuple(pos), GRID_W, GRID_H))

# 复刻 GetEffectiveCellConfig：最后一个命中的条目生效
eff = {}
for y in range(1, GRID_H + 1):
    for x in range(1, GRID_W + 1):
        hit = None
        for pos, gt, fl in cells:
            if pos[0] <= x <= pos[2] and pos[1] <= y <= pos[3]:
                hit = (gt, fl)
        eff[(x, y)] = hit
chk(all(v is not None for v in eff.values()), "54 个格子都能匹配到 cellConfig（无空洞）")

water = set(k for k, v in eff.items() if v[0][0] == WATER)
want = set((x, y) for y in (4, 5) for x in range(1, 10))
chk(water == want, "水池 = 第4~5行 × 第1~9列（共 %d 格）" % len(water))
chk(all(eff[k][0] == [WATER, AIR] for k in want), "水池格子 gridType 均为 [WATER, AIR] = [%d, %d]" % (WATER, AIR))
chk(all(eff[k][0] == [GROUND, AIR] for k in set(eff) - want),
    "非水池格子 gridType 均为 [GROUND, AIR] = [%d, %d]" % (GROUND, AIR))

# 元素分布：必须与原版吸血鬼屋逐格一致（第 6 行沿用第 5 行样式）
SRC = os.path.join(UNPACK, "Asset", "Config", "Map", "Vampire", "VampireMapVampire.tres")
src = io.open(SRC, encoding="utf-8", newline="").read()
sarr = re.search(r'cellConfig = Array\[[^]]*\]\(\[(.*?)\]\)\n', src, re.S).group(1)
sblocks = re.findall(r'\[sub_resource type="Resource" id="([^"]+)"\]\n((?:(?!\[sub_resource|\[resource\]).*\n)*)', src)
smap = dict(sblocks)
orig = []
for sid in re.findall(r'SubResource\("([^"]+)"\)', sarr):
    b = smap[sid]
    p = [int(v) for v in re.search(r"pos = Vector4i\((\d+), (\d+), (\d+), (\d+)\)", b).groups()]
    f = int(re.search(r"ElementFlags = (\d+)", b).group(1))
    orig.append((p, f))


def orig_elem(x, y):
    yy = y if y <= 5 else 5
    e = NIGHT
    for p, f in orig:
        if p[0] <= x <= p[2] and p[1] <= yy <= p[3]:
            e = f
    return e


diff = [k for k in eff if eff[k][1] != orig_elem(*k)]
chk(not diff, "54 格元素标志与原版吸血鬼屋逐格一致（含新第 6 行沿用第 5 行样式）")
if diff:
    print("       差异:", diff[:10])
name = {NIGHT: "夜", DAY: "昼"}
for y in range(1, GRID_H + 1):
    row = "".join(name.get(eff[(x, y)][1], "?") for x in range(1, GRID_W + 1))
    mark = "  <-- 水池行" if y in (4, 5) else ""
    print("       第%d行 %s%s" % (y, row, mark))

# ---------- 7) [resource] 段关键属性 ----------
print("  --- [resource] 段 ---")
res_block = s.split("[resource]\n", 1)[1]


def prop(k):
    m = re.search(r"(?m)^%s = (.*)$" % re.escape(k), res_block)
    return m.group(1) if m else None


chk(prop("translate") == '"吸血鬼屋泳池"', "translate = 吸血鬼屋泳池（%s）" % prop("translate"))
chk(prop("gridNum") == "Vector2i(9, 6)", "gridNum = Vector2i(9, 6)（%s）" % prop("gridNum"))

# 几何按**背景贴图实测**反推（不再是「保 98 + 整盘上移居中」）：
#   贴图 1400×600；草坪上沿 y≈74、下沿 y≈576 → 行距 502/6 = 83.6667
MAP_W, MAP_H = 1400.0, 600.0
GX, GY = 260.0, 74.0
GSX, GSY = 80.0, 83.6667
GW, GH = 9, 6
ART_LAWN_TOP, ART_LAWN_BOTTOM = 74.0, 576.0
ART_WATER_TOP, ART_WATER_BOTTOM = 329.0, 490.0
grid_bottom = GY + GH * GSY
grid_right = GX + GW * GSX

chk(prop("gridBeginPos") == "Vector2(260, 74)",
    "gridBeginPos = Vector2(260, 74)（对齐贴图草坪上沿；实际 %s）" % prop("gridBeginPos"))
# ⚠️ 83.6667 已不是类默认 98 → 必须显式写进 .tres，不写就整盘回落 98、错位
chk(prop("gridSize") == "Vector2(80, 83.6667)",
    "gridSize = Vector2(80, 83.6667)（⚠️ 已非类默认，必须显式写；实际 %s）" % prop("gridSize"))
chk(grid_bottom <= MAP_H, "网格下沿 %.4f ≤ mapSize.Y %.0f（相机钳制上界）" % (grid_bottom, MAP_H))
chk(grid_right <= MAP_W, "网格右沿 %.0f ≤ mapSize.X %.0f" % (grid_right, MAP_W))
chk(GY >= 0, "gridBeginPos.Y %.0f ≥ 0" % GY)
chk(abs(GY - ART_LAWN_TOP) < 1.0, "网格上沿 %.0f 对齐贴图草坪上沿 %.0f" % (GY, ART_LAWN_TOP))
chk(abs(grid_bottom - ART_LAWN_BOTTOM) < 1.0,
    "网格下沿 %.4f 对齐贴图草坪下沿 %.0f" % (grid_bottom, ART_LAWN_BOTTOM))
chk(abs(GSY - (ART_LAWN_BOTTOM - ART_LAWN_TOP) / GH) < 0.01,
    "行距 %.4f ≈ 贴图行距 %.4f" % (GSY, (ART_LAWN_BOTTOM - ART_LAWN_TOP) / GH))

# 水池格 = 第 4~5 行 → y ∈ [GY+3*GSY, GY+5*GSY]，应压住贴图实测水面
pool_top, pool_bottom = GY + 3 * GSY, GY + 5 * GSY
chk(abs(pool_top - ART_WATER_TOP) <= 6 and abs(pool_bottom - ART_WATER_BOTTOM) <= 6,
    "水池格 y %.1f..%.1f 对齐贴图水面 %.0f..%.0f（偏差 ≤6px）"
    % (pool_top, pool_bottom, ART_WATER_TOP, ART_WATER_BOTTOM))
chk(prop("lineUse") == "Array[int]([1, 2, 3, 4, 5, 6])", "lineUse = 1..6（%s）" % prop("lineUse"))
chk(prop("isNight") == "true", "isNight = true（继承夜晚）")
chk(prop("useSunFall") == "false", "useSunFall = false（继承无天降阳光）")
chk(prop("specialRules") == 'Array[ExtResource("3_rule_script")]([ExtResource("4_rule")])',
    "specialRules 指向 res://Asset/Config/Map/Rules/Vampire.tres（继承吸血规则）")
chk("Vampire.jpg" in (prop("mapTexturePath") or ""),
    "mapTexturePath 仍指内置 Vampire.jpg（编辑器预览用；战斗背景由运行时 DLL 换掉）")
chk("TowerDefenseMapVampire.tscn" in (prop("mapScenePath") or ""), "沿用吸血鬼屋场景")

# ---------- 8) 原版没有的字段是否被误加 ----------
extra = []
for k in re.findall(r"(?m)^([A-Za-z_][A-Za-z0-9_]*) = ", res_block):
    if k not in ("script", "translate", "mapTexturePath", "mapScenePath", "gridNum", "gridBeginPos",
                 "gridSize", "cellConfig", "lineUse", "isNight", "useSunFall", "specialRules"):
        extra.append(k)
chk(not extra,
    "[resource] 段未引入白名单之外的字段（白名单含原版 11 项 + gridSize；实际多出 %s）"
    % (extra or "无"))

print("-" * 78)
print("结论:", "全部通过" if ok_all else "存在未通过项")
sys.exit(0 if ok_all else 1)
