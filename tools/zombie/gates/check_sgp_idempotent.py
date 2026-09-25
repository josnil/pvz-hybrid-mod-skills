#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「超级机枪读报僵尸」收尾校验：3 连跑幂等 + 产物字节指纹。

做三件事：
  1. 连跑 3 次 build_zombie_super_gatling_paper.py，每次都记录
        · dist/超级机枪读报僵尸.pmod 的 sha256
        · 每个包内条目的 (相对路径, 大小, sha256)
     三次必须**逐字节一致**（生成器用固定时间戳 ZipInfo + 增量写盘）。
  2. 独立复算 .pmod 的条目清单与 manifest.resources 是否一一对应（不信任生成器的自检）。
  3. 只读核对关键数值是否真的落在产物文本里（血量 / 攻击 / 防具 500 / 单条发射配置 / Marker2D
     / ★★ 场景根节点的 ComponentSet 声明）。

⚠️ 只读 + 只跑生成器；不删除任何文件（本机删除钩子单次约 0.6 s，且整目录删重建是禁忌）。
用法：python .cache/check_sgp_idempotent.py
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))            # ModWorkspace/.cache
WS = os.path.dirname(HERE)                                   # ModWorkspace
PY = sys.executable
BUILDER = os.path.join(WS, "build_zombie_super_gatling_paper.py")

MOD_NAME = "超级机枪读报僵尸"
MOD_ROOT = os.path.join(WS, "SuperGatlingPaper")
PMOD = os.path.join(WS, "dist", MOD_NAME + ".pmod")


def sha256_file(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def pmod_fingerprint():
    """返回 (整体 sha256, {条目: (大小, sha256)})。"""
    with zipfile.ZipFile(PMOD) as z:
        items = {}
        for info in z.infolist():
            data = z.read(info.filename)
            items[info.filename] = (len(data), hashlib.sha256(data).hexdigest())
        # 条目顺序也纳入指纹（mod.json 必须是第 0 个）
        order = [i.filename for i in z.infolist()]
    return sha256_file(PMOD), items, order


def run_builder():
    proc = subprocess.run([PY, BUILDER], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or ""), (proc.stderr or "")


def main() -> int:
    fails = []
    runs = []
    for i in range(1, 4):
        code, out, err = run_builder()
        if code != 0:
            print(f"[FAIL] 第 {i} 次运行生成器 exit={code}")
            print(out)
            print(err)
            return 3
        whole, items, order = pmod_fingerprint()
        runs.append((whole, items, order))
        print(f"第 {i} 次   pmod={os.path.getsize(PMOD)} B  sha256={whole[:16]}  条目 {len(items)}")

    if not (runs[0][0] == runs[1][0] == runs[2][0]):
        fails.append("3 次跑出的 .pmod 整体 sha256 不一致 ⇒ 不幂等")
    if not (runs[0][1] == runs[1][1] == runs[2][1]):
        a, b = runs[0][1], runs[2][1]
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                fails.append(f"条目字节漂移 {k}: {a.get(k)} -> {b.get(k)}")
    if not (runs[0][2] == runs[1][2] == runs[2][2]):
        fails.append(f"条目顺序漂移：{runs[0][2]} -> {runs[2][2]}")

    whole, items, order = runs[0]
    print(f"最终 sha256 = {whole}")
    if order and order[0] != "mod.json":
        fails.append(f"条目 0 不是 mod.json：{order[0]}")
    for bad in ("UI端到端自测.pmod", "编辑器自测v2.pmod"):
        if bad in os.path.basename(PMOD):
            fails.append("自测产物被当成正式包")

    # --- 独立复算：manifest.resources 与包内条目一一对应
    mf = json.load(io.open(os.path.join(MOD_ROOT, "mod.json"), "r", encoding="utf-8-sig"))
    declared = sorted(mf["resources"], key=lambda p: p.lower())
    actual = [e for e in order if e != "mod.json"]
    if declared != actual:
        fails.append(f"manifest.resources 与包内条目不一致：\n  only-declared={set(declared) - set(actual)}\n"
                     f"  only-packed={set(actual) - set(declared)}")
    else:
        print(f"manifest.resources 与包内 {len(actual)} 个条目一一对应 OK")

    # --- 只读核对关键数值（直接读产物文本，不看生成器的自检结论）
    def read_pkg(rel):
        p = os.path.join(MOD_ROOT, rel.replace("/", os.sep))
        with io.open(p, "r", encoding="utf-8-sig") as f:
            return f.read()

    KEY = "ZombieSuperGatlingPaper"
    cfg = read_pkg(f"Resources/Characters/Zombies/{KEY}/Config/TowerDefense{KEY}.tres")
    slot = read_pkg(f"Resources/Characters/Zombies/{KEY}/Armor/Config/{KEY}ArmorPaper.tres")
    fire = read_pkg(f"Resources/Characters/Zombies/{KEY}/Scene/{KEY}FireComponentDefinition.tres")
    scene = read_pkg(f"Resources/Characters/Zombies/{KEY}/Scene/{KEY}.tscn")
    compset = read_pkg(f"Resources/Characters/Zombies/{KEY}/Scene/{KEY}ComponentSet.tres")
    card = read_pkg(f"Resources/Cards/{KEY}.tres")
    mf_txt = json.dumps(mf, ensure_ascii=False)

    checks = [
        ("本体总血 = 1180 + 70 = 1250", "hitpoints = 1180.0" in cfg and "hitpointsNearDeath = 70.0" in cfg),
        ("啃食伤害 800", "attack = 800.0" in cfg),
        ("不吃碾压（无 smashAttack）", "smashAttack" not in cfg),
        ("二类防具 Paper 500 血", 'armorName = "Paper"' in slot and "damagePoint = 500.0" in slot),
        ("防具槽沿用内置媒体名", 'replaceMediaName = &"Zombie_paper_paper1.png"' in slot
         and 'destroyFliter = "Zombie_paper_paper"' in slot),
        ("Config 的 armorData 是包内相对路径", "../Armor/" in cfg),
        ("场景出生即戴 Paper", 'currentArmor = ["Paper"]' in scene),
        ("场景复用内置读报僵尸脚本（掉落 ×3 移速）",
         "Paper/Scene/TowerDefenseZombiePaper.cs" in scene),
        ("场景自带 Marker2D FireMarker", '[node name="FireMarker" type="Marker2D"' in scene),
        ("★★ 场景根节点声明 ComponentSet（漏了 ⇒ 发射组件不创建 ⇒ 一颗豌豆都不出）",
         'ComponentSet = ExtResource("15")' in scene),
        ("★★ ComponentSet 指向包内相对路径（包内自引用禁 res://）",
         f'path="./{KEY}ComponentSet.tres"' in scene and f'path="./{KEY}FireComponentDefinition.tres"' in compset),
        ("组件集 = 父集(内置僵尸) + 只加 1 个发射组件",
         "TowerDefenseZombieComponentSet.tres" in compset and 'Components = [ExtResource("1")]' in compset),
        ("发射位置指向 Marker2D", "HeadSlot/FireMarker" in fire),
        ("恰好 1 条发射配置（一次 Fire() = 1 颗）", fire.count('id="Resource_fcfpc"') == 1),
        ("豌豆向前（speed 为负）", "speed = -300.0" in fire),
        ("FireComponentDefinition 不带动画/精灵字段（开火动画由插件直接驱动可见头，不走 fireAnimeClips）",
         "fireAnimeClips" not in fire and "isSpliceSprite" not in fire and "spritePath" not in fire),
        ("整包不覆盖移速/时标", "walkSpeedScale" not in scene and "timeScale" not in scene),
        ("卡片 = ZOMBIE 类型", "type = 6" in card),
        ("卡片价格 100 / 冷却 5 秒", "cost = 100" in cfg and "packetCooldown = 5.0" in cfg),
        ("卡片显示名为中文", "name = \"超级机枪读报僵尸\"" in card),
        ("卡片解锁条件为空表", "unlockCheckList = []" in card),
        ("runtime 四字段合规",
         mf["runtimeAssembly"] == "Runtime/ModAssembly.dll" and mf["runtimeApiVersion"] == 1
         and mf["runtimeAssemblyPolicy"] == "optional"
         and mf["runtimeEntryType"] == "SuperGatlingPaperRuntimeEntry"),
        ("provides 三键均声明", all(mf["provides"].get(k) == [KEY]
                                    for k in ("Character", "CharacterSprite", "Packet"))),
        ("翻译表为空（中文直写）", mf["translations"] == []),
        ("包内不含 .cs/.scn/.res 二进制", not any(e.endswith((".cs", ".scn", ".res")) for e in actual)),
        ("包内不含工程标记", not any(e.endswith(".pvzmodeproject") for e in actual)),
        ("描述里没有翻译键残留", "TOWERDEFENSE_" not in mf_txt and "TOWERDEFENSE_" not in card),
    ]
    for label, ok in checks:
        print(("  PASS  " if ok else "  FAIL  ") + label)
        if not ok:
            fails.append(label)

    # --- DLL 指纹（判字符串用字节搜：#Strings=UTF-8 / #US=UTF-16LE）
    dll = os.path.join(MOD_ROOT, "Runtime", "ModAssembly.dll")
    raw = open(dll, "rb").read()
    for name, enc in (("SuperGatlingPaperRuntimeEntry", "utf-8"),):
        if name.encode(enc) not in raw:
            fails.append(f"DLL 里搜不到类型名 {name}（#Strings 应为 UTF-8）")
        else:
            print(f"  PASS  DLL #Strings 含 {name}")
    for lit in ("character.fire", "ZombieSuperGatlingPaper", "GeneralZombie"):
        if lit.encode("utf-16-le") not in raw:
            fails.append(f"DLL 里搜不到字符串字面量 {lit}（#US 应为 UTF-16LE）")
        else:
            print(f"  PASS  DLL #US 含 {lit}")
    # 新增的诊断：认出僵尸却拿不到 character.fire 时要报一次（本次静默失败教训）
    diag = "（豌豆不会发射；僵尸仍会正常行走/啃食）。"
    if diag.encode("utf-16-le") not in raw:
        fails.append("DLL 里搜不到「拿不到发射组件」的诊断文案（#US 应为 UTF-16LE）")
    else:
        print("  PASS  DLL #US 含「拿不到 character.fire」诊断文案")
    print(f"  ..     DLL 大小 {len(raw)} B  sha256={hashlib.sha256(raw).hexdigest()[:16]}")

    print()
    if fails:
        print("存在失败 ✗")
        for f in fails:
            print("   -", f)
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
