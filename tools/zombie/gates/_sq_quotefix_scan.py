# -*- coding: utf-8 -*-
"""全库扫描：Godot 属性名「引号写法」是否正确。

规则（由官方文件实证）：
  · 整条属性名不含空格且全 ASCII   ⇒ 裸写        `Animation/LayerVisible/1 = true`
  · 否则                          ⇒ **整条**加引号 `"Animation/LayerVisible/图层_1" = true`
错误形态：
  A. 只给「层名/末段」加引号：`Animation/LayerVisible/"图层_1" = true`  ⇒ 解析出的名字带引号 ⇒ 静默失效
  B. 含空格 / 非 ASCII 却裸写   ⇒ 名字被拆碎 ⇒ 静默失效
失效后果：`AdobeAnimateSprite._Set` 里 `layerDictionary.ContainsKey(name)` 为假 ⇒
        该层保持初值 true ⇒ **永远可见**（这就是「多出一个头」的成因）。
"""
import io
import os
import re
import sys


def scan(root, label, max_show=40):
    bad_a, bad_b, bad_o = [], [], []
    nfiles = 0
    for dp, dn, fn in os.walk(root):
        if "obj" in dp.split(os.sep) or ".git" in dp:
            continue
        for f in fn:
            if not (f.endswith(".tscn") or f.endswith(".tres")):
                continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace("\\", "/")
            try:
                lines = io.open(p, encoding="utf-8", errors="replace").read().splitlines()
            except Exception:
                continue
            nfiles += 1
            for i, ln in enumerate(lines, 1):
                if "=" not in ln or ln.lstrip().startswith("["):
                    continue
                key = ln.split("=", 1)[0].strip()
                if not key or "=" in key:
                    continue
                # ⚠️ 2026-09-25 修：**多行字符串值的续行**会被误判成 B 型。
                #   例：`.tres` 里 `handbookDescribe` 用**真实换行**，续行长这样 ——
                #       速度：[color=cc241d]慢[/color]
                #   第一个 `=` 落在 BBCode `[color=cc241d]` 里 ⇒ key = `速度：[color`，
                #   含非 ASCII ⇒ 被当成「该加引号却裸写」。实测这一条占了 B 型的**全部 18 条**。
                #   判据：合法的 Godot 属性名**一定**以 ASCII 字母/下划线开头（`Animation/…` / `z_index`），
                #   或整条被引号包住；否则一律视为字符串续行，跳过。
                if not (key.startswith('"') or re.match(r"^[A-Za-z_]", key)):
                    continue
                if key.startswith('"') and key.endswith('"') and len(key) > 1:
                    name = key[1:-1]          # 整条加引号（正确形态）
                else:
                    name = key
                has_q = '"' in key
                need_q = (" " in name) or (not name.isascii())
                if has_q and not (key.startswith('"') and key.endswith('"')):
                    bad_a.append("%s:%d | %s" % (rel, i, ln.strip()))
                elif need_q and not has_q:
                    bad_b.append("%s:%d | %s" % (rel, i, ln.strip()))
                elif name.startswith("Animation/") and need_q and not has_q:
                    bad_o.append("%s:%d | %s" % (rel, i, ln.strip()))
    sys.stdout.write("\n############ %s（扫了 %d 个文件）############\n" % (label, nfiles))
    sys.stdout.write("A 型「只给末段加引号」：%d 条\n" % len(bad_a))
    for x in bad_a[:max_show]:
        sys.stdout.write("    %s\n" % x)
    sys.stdout.write("B 型「该加引号却裸写」：%d 条\n" % len(bad_b))
    for x in bad_b[:max_show]:
        sys.stdout.write("    %s\n" % x)
    return len(bad_a), len(bad_b)


if __name__ == "__main__":
    a1, b1 = scan(r"D:/zzz/pvzHE/解包/植物大战僵尸杂交版/Asset/Anime/Character/Zombie/.workbuddy/ModWorkspace",
                  "工坊（我们的产物）")
    a2, b2 = scan(r"D:/zzz/pvzHE/解包/植物大战僵尸杂交版V0.28/Asset", "官方 Asset（对照组）")
    sys.stdout.write("\n=== 汇总：工坊 A=%d B=%d ；官方 A=%d B=%d ===\n" % (a1, b1, a2, b2))
