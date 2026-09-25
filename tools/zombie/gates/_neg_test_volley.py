#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""★ 2026-09-24 齐射改版负向测试：逐条篡改 ⇒ 生成器 --check 必须报警 ⇒ 还原。

覆盖齐射新断言里最容易被「同名值稀释 / 结构漂移」打穿的几条：
  NEG-V1  场景 Marker2D5 的 **x** 被挪动（回到旧列位置）  ⇒ 13f-3 磁盘复核报警
  NEG-V2  ComponentSet 锁行开关被关          ⇒ 13 段 lockProjectileGridY 报警
  NEG-V3  某条 firePosId 被改成重复值        ⇒ 13 段 firePosId 0..6 各一次报警
  NEG-V4  fireProjectileList 少一条（7→6）  ⇒ 13 段 proj 引用序列报警
  NEG-V5  插件源码回流 fire.Fire()           ⇒ 17b 报警
  NEG-V6  插件源码回流 fireEventName 改写    ⇒ 17a 报警
  ★ NEG-V7  单个 Marker 的 **y** 被挪（制造「一列」）      ⇒ 13f-4 形态断言（y 不唯一）报警
  ★ NEG-V8  整组 6 个 Marker 回到**旧列布局**（用户否掉的形态） ⇒ 13f-4「一列」报警

用法：python .cache/_neg_test_volley.py   （自恢复，失败时也会还原）
"""
import importlib.util as _u
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)          # .cache 的上一级 = ModWorkspace
BUILD = os.path.join(WS, "SuperGatlingPea")
SCENE = os.path.join(BUILD, "Resources", "Characters", "Plants", "SuperGatlingPea",
                     "Scene", "SuperGatlingPea.tscn")
CSET = os.path.join(BUILD, "Resources", "Characters", "Plants", "SuperGatlingPea",
                    "Scene", "SuperGatlingPeaComponentSet.tres")
ENTRY = os.path.join(WS, "runtime_src_plant", "SuperGatlingPeaRuntimeEntry.cs")

_gen_spec = _u.spec_from_file_location("sgp_gen", os.path.join(WS, "build_plant_super_gatling.py"))
GEN = _u.module_from_spec(_gen_spec)
_gen_spec.loader.exec_module(GEN)


def run_check():
    """跑生成器 --check 口径的自检（只验证磁盘现状，不重建）。返回 FAIL 列表。"""
    return GEN.self_check()


def case(name, path, old, new, expect_key):
    """全量替换 old→new ⇒ 自检必须出现含 expect_key 的 FAIL ⇒ 还原。"""
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    if old not in src:
        return (name, False, "注入目标字面量不存在（用例本身坏了）")
    try:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src.replace(old, new))
        fails = run_check()
        hit = [m for m in fails if expect_key in m]
        return (name, bool(hit),
                ("报警 0 条（假绿！）" if not fails else
                 f"报警 {len(fails)} 条但都不是 {expect_key!r}：{fails[:2]}") if not hit else
                f"✔ 报警 {len(fails)} 条，含目标断言")
    finally:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src)


def case_multi(name, path, pairs, expect_key):
    """一次性做多组全量替换（模拟「整组回退」）⇒ 自检必须出现 expect_key 的 FAIL ⇒ 还原。

    ⚠️ NEG-V8 这类「整组回退」会同时触发多条 FAIL（每个 Marker 的逐一比对 + 形态断言），
      这里只要求**目标断言（形态）**出现在 FAIL 列表里 —— 避免被别的断言「掩盖」造成假绿。
    """
    with io.open(path, "r", encoding="utf-8") as f:
        src = f.read()
    for old, _ in pairs:
        if old not in src:
            return (name, False, f"注入目标字面量不存在（用例本身坏了）：{old!r}")
    new_src = src
    for old, new in pairs:
        new_src = new_src.replace(old, new)
    try:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(new_src)
        fails = run_check()
        hit = [m for m in fails if expect_key in m]
        return (name, bool(hit),
                ("报警 0 条（假绿！）" if not fails else
                 f"报警 {len(fails)} 条但都不是 {expect_key!r}：{fails[:2]}") if not hit else
                f"✔ 报警 {len(fails)} 条，含目标断言")
    finally:
        with io.open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src)


results = []

# NEG-V1：Marker2D5 的 x（179.502 → 51.502，即回到旧「一列」的 x）——只动磁盘场景，
#   内存文本由生成器重算 ⇒ 必须由「13f-3 磁盘复核」抓到（13c-3 查内存，抓不到 ⇒ 防门控共用假绿）。
results.append(case(
    "NEG-V1 Marker2D5 x 篡改（磁盘）", SCENE,
    '[node name="Marker2D5" type="Marker2D" parent="SpriteGroup/TransformPoint/GatlingPea/Head" index="4"]\nposition = Vector2(179.502, -16.8)',
    '[node name="Marker2D5" type="Marker2D" parent="SpriteGroup/TransformPoint/GatlingPea/Head" index="4"]\nposition = Vector2(51.502, -16.8)',
    "磁盘 Marker2D5"))

# NEG-V2：锁行开关被关（齐射散布会打进别的排）
results.append(case(
    "NEG-V2 lockProjectileGridY 被关", CSET,
    "lockProjectileGridY = true", "lockProjectileGridY = false",
    "lockProjectileGridY"))

# NEG-V3：某条 firePosId 改成重复值（两条配置从同一个点出膛 ⇒ 互相重叠）
results.append(case(
    "NEG-V3 firePosId 重复", CSET,
    "firePosId = 5", "firePosId = 4",
    "firePosId"))

# NEG-V4：齐射少一颗（7 → 6）
results.append(case(
    "NEG-V4 齐射少一条配置", CSET,
    ", SubResource(\"Fire_Resource_proj5\"), SubResource(\"Fire_Resource_proj6\")]",
    ", SubResource(\"Fire_Resource_proj5\")]",
    "fireProjectileList"))

# NEG-V5：插件回流 fire.Fire()（会把 7 颗齐射配置一次全打出）
results.append(case(
    "NEG-V5 插件回流 fire.Fire()", ENTRY,
    "fire.CreateProjectileByData(0, velocity, data, -1,",
    "fire.Fire(); fire.CreateProjectileByData(0, velocity, data, -1,",
    "fire.Fire()"))

# NEG-V6：插件回流 fireEventName 改写（屏蔽动画事件发射链 = 常规齐射哑火）
results.append(case(
    "NEG-V6 插件回流 fireEventName 屏蔽", ENTRY,
    "fire.OnFireReady += hook.ReadyHandler;",
    "fire.OnFireReady += hook.ReadyHandler;\n\t\tfire.fireEventName = \"modfire\";",
    "fireEventName"))

# ★ NEG-V7：单个 Marker 的 y 被挪（-16.8 → 15.2）⇒ 该颗脱离水平线
#   ⇒ 13f-4 形态断言必须报「y 不唯一 / 一列」（这条断言看不看 firePosId 顺序，
#     专门盯「一排」这个**用户口径**，与逐点比对互补）。
results.append(case(
    "NEG-V7 单颗脱离水平线（y 篡改）", SCENE,
    '[node name="Marker2D5" type="Marker2D" parent="SpriteGroup/TransformPoint/GatlingPea/Head" index="4"]\nposition = Vector2(179.502, -16.8)',
    '[node name="Marker2D5" type="Marker2D" parent="SpriteGroup/TransformPoint/GatlingPea/Head" index="4"]\nposition = Vector2(179.502, 15.2)',
    "一列"))

# ★ NEG-V8：整组回到**旧「一列」布局**（用户明确否掉的形态：6 个非基准 Marker 沿 y 铺开）
#   ⇒ 形态断言必须报「一列」。这是本轮口径修正的**回归护栏**：谁再把 volley_marker_dx 改回
#     沿 y 铺 / 或磁盘上被回退成旧布局，这条断言立刻红。
_column_pairs = [
    ("position = Vector2(83.502, -16.8)", "position = Vector2(51.502, 15.2)"),
    ("position = Vector2(115.502, -16.8)", "position = Vector2(51.502, -48.8)"),
    ("position = Vector2(147.502, -16.8)", "position = Vector2(51.502, 47.2)"),
    ("position = Vector2(179.502, -16.8)", "position = Vector2(51.502, -80.8)"),
    ("position = Vector2(211.502, -16.8)", "position = Vector2(51.502, 79.2)"),
    ("position = Vector2(243.502, -16.8)", "position = Vector2(51.502, -112.8)"),
]
results.append(case_multi(
    "NEG-V8 整组回退成旧『一列』布局", SCENE, _column_pairs, "一列"))

# 还原后必须全绿（自恢复验证）
fails = run_check()
restored_ok = not fails
ok = sum(1 for _, good, _ in results if good)
print()
for name, good, msg in results:
    print(f"  [{name}] {'✔ ' + msg if good else '✘ ' + msg}")
print(f"\n还原后生成器自检：{'全绿 ✓' if restored_ok else '仍有 FAIL（还原失败！）: ' + str(fails[:3])}")
print(f"\n齐射负向测试：{ok}/{len(results)} 条如期报警；还原自检{'通过' if restored_ok else '未通过'}")
sys.exit(0 if (ok == len(results) and restored_ok) else 1)
