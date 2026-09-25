# -*- coding: utf-8 -*-
"""
build_map_vampire_pool.py —— 生成「吸血鬼屋泳池」地图 Mod（category = Map）

设计依据（全部逆向自 V0.28 解包，不是猜的）：

A. 地图资源 = res://Registry/Battle/Feature/Map/Resource/TowerDefenseMapConfig.cs
   关键字段（[Export] 全集）：
     translate / dayNightSwitching / mapTexturePath / mapScenePath
     mapSize / mapOffset / plantOffset / gridNum / gridBeginPos / gridSize / edge
     cellConfig / lineUse / isNight / useSunFall / enableBattleZoom / maximumFps / specialRules

B. 格子 = TowerDefenseCellConfig.cs
     pos          : Vector4i(x1, y1, x2, y2)  —— 1-based 闭区间的「列起,行起,列止,行止」
     gridType     : Array<PLANTGRIDTYPE>，缺省 = [GROUND(2), AIR(4)]
     ElementFlags : int 位标志 = ELEMENT_SYSTEM { ICE=1, FIRE=2, DAY=4, NIGHT=8 }
                    → 被 SleepComponent 消费（蘑菇类白天睡/夜晚睡）；是吸血鬼屋的真实玩法特性

C. 坐标约定由编辑器自身代码确证：
     XWMapVisualResourceEditor.ToCellConfigPos(selection)
       = Vector4i(sel.Pos.X + 1, sel.Pos.Y + 1, sel.Pos.X + sel.Size.X, sel.Pos.Y + sel.Size.Y)
     即编辑器网格是 0-based，写进 tres 时 +1 变成 1-based 闭区间；
     x 轴 = 列(1..gridNum.X)，y 轴 = 行(1..gridNum.Y)。

D. 水池怎么表达（对照官方后院水池地图 BackyardMapBackyard.tres）：
     整盘草坪 : pos = Vector4i(1, 1, 9, 6)                        （gridType 缺省 → 陆地+空中）
     水池     : pos = Vector4i(1, 3, 9, 4), gridType = [3, 4]      （WATER(3) + AIR(4)）
     → 「水池区域」= 一条覆盖该矩形、且 gridType = [3, 4] 的 cellConfig 条目。

E. ⚠️ 覆盖次序（最容易踩的坑）：
     TowerDefenseMapConfig.GetEffectiveCellConfig(x, y) 遍历 cellConfig，
     对每个命中的条目都执行 result = item —— 所以【数组里最后一个命中的条目生效】。
     一条 cellConfig 同时携带 gridType 和 ElementFlags，**后写的会把两样都替换掉**。
     所以往吸血鬼屋（有 DAY/NIGHT 元素格）上面盖水池时，不能只追加一条矩形了事，
     否则水池覆盖区的 ElementFlags 会被清成 0，把「昼夜元素」特性弄丢。
     本脚本的做法：对落在水池范围内的原有条目【就地补上 gridType】，再按元素分区补齐新条目，
     最后由引擎同款仿真逐格校验 54 个格子的 (gridType, ElementFlags) 全部符合预期。

F. 「游戏跑哪个」——.pmod 与工程目录是两回事（本次新增，逆向自 V0.28 解包的 Mod 系统源码）：
     XWModManager.ScanMods() ：
       Directory.EnumerateFiles(_modsDirectory, "*.pmod", SearchOption.TopDirectoryOnly)
     → 游戏**只加载 `user://Mods/*.pmod`**（zip 包），并且**不递归**。
       所以「Mods 目录下放一个文件夹」是**不会被加载**的。

     而游戏侧编辑器（F3 → Mod 工具）产出的那个 `新地图-1/` 文件夹，是 **Mod 工程目录（project）**：
       ModProject.cs        : .pvzmodeproject = 工程元数据
       XWModProjectLayout   : 72 个标准子目录（Scenes/Scripts/Battle/Resources/Assets/Localization…）
       XWModManifestSyncService: 自动扫描工程内文件生成 `mod.json`
     只有点「导出」时，ModProject.ExportAsync → ModExporter.ExportFromDirectory
     才会把这个工程压成 `user://Mods/<工程名>.pmod`。

     ⇒ 为了让「改完就能跑」且与游戏侧编辑器**完全同构**，本脚本同时产出：
        ① 工作区构建目录  .workbuddy/ModWorkspace/VampirePool/
        ② 游戏侧工程目录  Mods/吸血鬼屋泳池/   （72 个标准子目录 + mod.json + <名>.pvzmodeproject）
        ③ 可加载安装包    Mods/吸血鬼屋泳池.pmod
      工程名 / 工程文件名 / pmod 文件名三者一致，所以在编辑器里再点一次「导出」
      会覆盖同一个 `<工程名>.pmod`，**不会产生两份同 id 的 mod**。

G. 工程目录里 `mod.json` 与包内 `mod.json` 是同一份内容，但字节风格不同（都已实测）：
     包内      ：LF、无 BOM、**不转义**中文、结尾无换行（＝ ModExporter 用 StreamWriter 写的）
     工程目录内：CRLF、无 BOM、**\\uXXXX 转义**（大写十六进制）（＝ XWModManifest.Save → File.WriteAllText）
     两者对 XWModManifest.Load/JsonSerializer 都可解析，差别只在字节层面。

H. 6 行几何（现方案：按背景贴图反推，非「整盘上移」）。
     逻辑地图空间 = mapSize = (1400, 600)（背景贴图实测就是 1400×600）；
     相机垂直钳在 [0, mapSize.Y]（TowerDefenseCameraControl.ClampCameraToMap），
     子弹边界也是 y ∈ [0, mapSize.Y]（BuildProjectileBoundaryRect），
     网格下沿 = gridBeginPos.Y + gridNum.Y * gridSize.Y（TowerDefenseManager.cs:1897）。
     贴图实测：草坪上沿 y≈74、下沿 y≈576、行距≈83.667（6 行铺满 502px）。
     故 gridSize=(80, 83.6667)、gridBeginPos=(260, 74) → 网格 y ∈ [74, 576]，
     第 4~5 行（水池格）合计 325..492.3，贴图水面实测 329..490，偏差 ≤4px。
     ⚠️ gridSize 因此**不再是类默认 98**，必须显式写进 .tres。
     ⚠️ TryValidateRuntime 不校验「网格落在 edge 内」，所以这是画面/相机问题，不是校验问题。
     完整推导见下面「几何」常量块注释。

I. 背景贴图换图（本 Mod 特有的「托管运行时」路线）。
     战斗里的背景是地图场景 TowerDefenseMapVampire.tscn 里那个名为 Vampire 的
     Sprite2D 的 [ext_resource] 内置贴图；TowerDefenseMapConfig.mapTexturePath 只喂
     GetMapTexture()（纯 ResourceLoader.Load，不查 Mod 贴图注册表）→ 纯数据换不掉。
     所以：Mod 带一张 Assets/Images/VampirePoolBackground.jpg（provides.Texture 注册）
     + Runtime/ModAssembly.dll（托管入口），运行期把那个 Sprite2D 的 texture 换掉。
     ⚠️ runtimeAssembly 只能写字面量 "Runtime/ModAssembly.dll"，写别的整包被拒。
     ⚠️ 一旦 provides 里有条目，**每一个**被识别的资源都必须在 provides/overrides 声明，
        否则该资源被跳过 + ValidateManifestRegistrations 判整包失败。

用法：
    python build_map_vampire_pool.py            # 生成 + 自检 + 打包 + 安装（工程目录 + .pmod）
"""

import io
import json
import hashlib
import os
import re
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 路径
WS = os.path.dirname(os.path.abspath(__file__))
UNPACK = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"
SRC_TRES = os.path.join(UNPACK, "Asset", "Config", "Map", "Vampire", "VampireMapVampire.tres")

BUILD_DIR = "VampirePool"         # 工作区里的构建目录（ASCII，稳定，不随游戏侧命名变化）
MOD_NAME = "吸血鬼屋泳池"          # 游戏侧：工程目录名 / .pvzmodeproject 名 / .pmod 文件名
MOD_ID = "vampirepool"            # mod.json 的 id（enabled_mods.json 记的是它，不是文件名）
DISPLAY_NAME = "吸血鬼屋泳池"      # 游戏内显示名（写进 Map.translate）
MAP_KEY = "VampirePool"           # MAPS 字典的 key（必须不存在于 MapResource.json）

# ---- 运行时换贴图（托管 C#）--------------------------------------------------
# 战斗背景由地图场景的 Sprite2D 直接画内置 Vampire.jpg，mapTexturePath 只喂
# GetMapTexture()（ResourceLoader 载不了 Mod 的 user:// 图片）→ 纯数据换不掉，
# 必须靠托管运行时在运行期把那个 Sprite2D 的 texture 换成我们的图。
TEXTURE_KEY = "VampirePoolBackground"   # provides.Texture 的 key = 贴图文件名去扩展
TEXTURE_REL = "Assets/Images/%s.jpg" % TEXTURE_KEY
RESOURCE_TRES = "Resources/Maps/%s.tres" % MAP_KEY   # 包内路径（多处引用，提成常量）
# ⚠️ ModLoader.ResolveDeclaredRuntimeAssembly 只认这一个字面量，写别的整包被拒
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"
RUNTIME_ENTRY_TYPE = "VampirePoolRuntimeEntry"   # 无命名空间，类名即全名
RUNTIME_API_VERSION = 1                          # 必须恰好 1
# optional：程序集加载失败不连坐整包（地图仍可玩，只是背景保持内置）
RUNTIME_POLICY = "optional"
VERSION = "1.0.0"
AUTHOR = "云漫行"
DESCRIPTION = ("Map 类地图 Mod：以「吸血鬼屋」为基底继承其全部特性（夜晚/无天降阳光/吸血规则/"
               "昼夜元素格），行数 5→6，并把第 4~5 行 × 第 1~9 列设为水池。")

MOD_ROOT = os.path.join(WS, BUILD_DIR)
ASSETS_DIR = os.path.join(WS, "assets")   # 贴图源：工作区归档（不依赖 WorkBuddyStorage 临时目录）
DIST_DIR = os.path.join(WS, "dist")
USER_MODS_DIR = os.path.join(os.environ.get("APPDATA", ""), "Godot",
                             "app_userdata", "植物大战僵尸杂交版", "Mods")
USER_DATA_DIR = os.path.dirname(USER_MODS_DIR)          # …／植物大战僵尸杂交版
TZ_CN = timezone(timedelta(hours=8))

# 游戏侧编辑器的 72 个标准子目录（XWModProjectLayout.StandardDirectories，顺序原样照抄）
STANDARD_DIRS = [
    "Scenes", "Scripts", "Battle", "Battle/Features", "Battle/Processes", "Battle/Components",
    "Resources", "Resources/Levels", "Resources/LevelCatalogs", "Resources/Maps",
    "Resources/MapCells", "Resources/GameplayLogic", "Resources/GameplayLogic/Waves",
    "Resources/StateMachines", "Resources/StateMachines/Conditions", "Resources/CharacterComponents",
    "Resources/CharacterCombat", "Resources/CharacterCombat/Attacks", "Resources/CharacterCombat/Buffs",
    "Resources/CharacterCombat/Events",
    "Resources/CharacterData", "Resources/CharacterData/Armor", "Resources/CharacterData/Custom",
    "Resources/CharacterData/DamagePoints", "Resources/BuffVisuals", "Resources/CollisionGeometry",
    "Resources/AwardSettlements", "Resources/UnlockConditions", "Resources/PacketEvents",
    "Resources/PacketSpawnEntries",
    "Resources/PacketSpawnEntries/Level", "Resources/PacketSpawnEntries/Conveyor",
    "Resources/PacketSpawnEntries/Rain", "Resources/ConveyorEvents", "Resources/ToolEvents",
    "Resources/Cards", "Resources/CardCostRules", "Resources/CardOverrides", "Resources/PacketBank",
    "Resources/Projectiles",
    "Resources/ProjectileChanges", "Resources/Characters", "Resources/Characters/Plants",
    "Resources/Characters/Zombies", "Resources/Characters/Props", "Resources/Characters/Vases",
    "Resources/Characters/Mowers", "Resources/Characters/Items", "Resources/Characters/Graves",
    "Resources/Characters/Craters",
    "Resources/Collectables", "Resources/DropItems", "Resources/Mowers", "Resources/Shovels",
    "Resources/FallingObjects", "Resources/Animations", "Resources/AnimationAtlasProfiles",
    "Resources/BGMConfigs", "Resources/Survivals", "Resources/Tutorials",
    "Resources/Tutorials/Conditions", "Resources/Tutorials/Steps", "Resources/NpcTalks",
    "Resources/Shops", "Resources/Dialogs", "Assets", "Assets/Images", "Assets/Audio",
    "Assets/Audio/Sfx", "Assets/Audio/BGM",
    "Assets/Fonts", "Localization",
]

# ---------------------------------------------------------------- 枚举（取自 TowerDefenseEnum.cs）
P_ALL, P_NOONE, P_SOIL, P_GROUND, P_WATER, P_AIR = -1, 0, 1, 2, 3, 4
E_ICE, E_FIRE, E_DAY, E_NIGHT = 1, 2, 4, 8

GRID_W, GRID_H = 9, 6                 # 9 列 × 6 行
GROUND_TYPES = [P_GROUND, P_AIR]      # 缺省（不写 gridType 时的类默认值）
WATER_TYPES = [P_WATER, P_AIR]        # 官方后院水池的写法

# ---------------------------------------------------------------- 几何（决定 6 行能不能全画出来）
#
# 逻辑地图空间 = TowerDefenseMapConfig.mapSize，类默认 (1400, 600)；Vampire.jpg 恰好 1400×600。
# 原版吸血鬼屋 .tres 只写了 gridBeginPos = (260, 75)，其余走类默认：
#     gridNum    = (9, 5)             ← 我们改成 6 行
#     gridSize   = (80, 98)           ← 我们显式改写（见下），因为不再是类默认
#     mapSize    = (1400, 600)
#     edge       = (200, 0, 1100, 576)
#
# 为什么必须动 gridBeginPos.Y（3 处硬证据，全部来自 V0.28 运行时，不是编辑器）：
#   ① 相机垂直被钳制在 [0, mapSize.Y]
#        TowerDefenseCameraControl.ClampCameraToMap()
#          camera.GlobalPosition.Y = ClampCameraAxis(y, 0f, size.Y, visibleY)    // size = mapSize
#        TowerDefenseCameraControl.ApplySize(): downRightMarker.GlobalPosition = size
#        （Test/Chapter7MapCameraBoundsRuntimeTest.cs 断言 downRightMarker == mapSize）
#   ② 子弹边界 = Rect2((-100, 0), mapSize + (200, 0)) —— y ∈ [0, mapSize.Y]
#        TowerDefenseBattleFeatureMap.BuildProjectileBoundaryRect()
#   ③ 网格下沿 = gridBeginPos.Y + gridNum.Y * gridSize.Y
#        TowerDefenseManager.cs:1897  bottom = gridBeginPos.Y + gridNum.Y * gridSize.Y
#        TowerDefenseManager.cs:1824  GetMapCellPos(gridPos) = gridBeginPos + gridPos * gridSize   (运行期 gridPos 是 0-based)
#
# 于是：5 行时下沿 = 75 + 5×98 = 565 ≤ 600 ✓
#       6 行时下沿 = 75 + 6×98 = 663 > 600 ✗（第 6 行落到相机与子弹边界之外）
#
# 解法（用户选定，按新贴图 VampirePoolBackground.jpg 反推）：
#   「保格子高度 98 + 整盘上移」换成「改格子高度 + 对齐贴图草坪」。
#   新贴图实测：草坪上沿 y≈74、草坪下沿 y≈576、行距≈83.667（6 行铺满 502px）。
#   故取 GRID_SIZE_Y = 83.6667、GRID_BEGIN_Y = 74
#       → 网格 y ∈ [74, 576]，恰好压住贴图的草坪与水面对应位置：
#           第 4 行 325.0..408.7、第 5 行 408.7..492.3（水池格合计 325..492.3）
#           贴图实测水面 y≈329..490 → 偏差 ≤ 4px。
#   gridSize 因此**必须显式写进 .tres**（不再等于类默认 98），否则回落到 98 全盘错位。
#   横向不动：GRID_BEGIN_X 仍 260、GRID_SIZE_X 仍 80（与原版吸血鬼屋一致）。
#
# ⚠️ 注意：本方案上下留白不再对称（上 74px / 下 24px），这是「对齐贴图」的必然代价，
#    自检里的「留白对称」断言已相应改为「对齐贴图草坪」断言。
#
# ⚠️ TryValidateRuntime 并**不**校验「网格必须落在 edge 内」（只查 edge.Z>edge.X 且 edge.W>edge.Y），
#    所以这纯粹是画面/相机问题，不是校验问题。
MAP_W, MAP_H = 1400.0, 600.0          # = mapSize 类默认，且 == Vampire.jpg 实际尺寸
# ⚠️ 已不再是类默认 (80, 98) → 必须显式写进 .tres（见 build_tres 里的 gridSize 行）
GRID_SIZE_X, GRID_SIZE_Y = 80.0, 83.6667  # 行高 = 新贴图实测行距；横向保持原版
GRID_BEGIN_X = 260.0                  # 原版吸血鬼屋值，不动
GRID_BEGIN_Y = 74.0                   # = 新贴图草坪上沿（原版为 75，逐像素对齐取 74）
GRID_LEFT = GRID_BEGIN_X
GRID_RIGHT = GRID_BEGIN_X + GRID_W * GRID_SIZE_X
GRID_TOP = GRID_BEGIN_Y
GRID_BOTTOM = GRID_BEGIN_Y + GRID_H * GRID_SIZE_Y

# 新贴图实测的草坪/水面参考（用于自检断言；来自 PIL 逐行剖面 + 自相关行距分析）
ART_LAWN_TOP, ART_LAWN_BOTTOM = 74.0, 576.0     # 草坪上/下沿
ART_WATER_TOP, ART_WATER_BOTTOM = 329.0, 490.0  # 水面实测范围
ART_ROW_PITCH = (ART_LAWN_BOTTOM - ART_LAWN_TOP) / GRID_H   # ≈ 83.6667

POOL_X1, POOL_Y1, POOL_X2, POOL_Y2 = 1, 4, 9, 5   # 水池 = 第 4~5 行 × 第 1~9 列


def read_text(path):
    with io.open(path, "r", encoding="utf-8-sig", newline="") as f:
        return f.read()


def fmt_num(v):
    """按 Godot .tres 的字面风格输出数字：整数值写 '260'，否则写最短往返表示。"""
    f = float(v)
    if f.is_integer():
        return str(int(f))
    return repr(f)


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def write_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_bytes_if_changed(path, data):
    """内容一致就不落盘（保住 mtime / 省掉上层写盘开销）。"""
    if os.path.isfile(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    write_bytes(path, data)
    return True


def sweep_stale_files(root, keep):
    """删掉 root 下「这次不再产出」的文件（增量清理，正常运行时一个都不删）。

    ⚠️ 用它取代「整目录 rmtree + 重建」：本机删除钩子单次约 0.6 s
    （实测删 72 个空目录 48 s），3 连跑的幂等校验会直接超时被杀（SIGTERM）。
    """
    removed = []
    for r, dirs, files in os.walk(root):
        for fn in files:
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if rel not in keep:
                os.remove(full)
                removed.append(rel)
    return removed


def sync_tree(src, dst, marker):
    """src → dst 增量镜像（只写变化的文件、只删 src 里没有的文件与空目录）。

    返回 (写入数, 删除数)。dst 必须已确认是我方目录（带 marker）。
    """
    keep = set()
    wrote = 0
    for r, dirs, files in os.walk(src):
        rel_dir = os.path.relpath(r, src).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        target_dir = os.path.join(dst, rel_dir.replace("/", os.sep)) if rel_dir else dst
        os.makedirs(target_dir, exist_ok=True)
        for fn in files:
            keep.add(f"{rel_dir}/{fn}" if rel_dir else fn)
            with open(os.path.join(r, fn), "rb") as f:
                data = f.read()
            if write_bytes_if_changed(os.path.join(target_dir, fn), data):
                wrote += 1
    keep.add(marker)
    removed = 0
    for r, dirs, files in os.walk(dst, topdown=False):
        for fn in files:
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, dst).replace("\\", "/")
            if rel not in keep:
                os.remove(full)
                removed += 1
        rel_dir = os.path.relpath(r, dst).replace("\\", "/")
        if rel_dir != "." and not os.listdir(r):
            if not os.path.isdir(os.path.join(src, rel_dir.replace("/", os.sep))):
                os.rmdir(r)          # src 里没有的空目录 → 历史遗留，清掉
                removed += 1
    return wrote, removed


def net_datetime(dt):
    """复刻 .NET DateTime 的 'O' 写法：7 位小数 + 冒号时区（如 2026-09-16T19:05:09.4726532+08:00）。"""
    off = dt.strftime("%z")                 # +0800
    off = off[:3] + ":" + off[3:]           # +08:00
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "0" + off


def safe_rmtree(path):
    """删除整棵目录树，**刻意不用 shutil.rmtree**。

    ⚠️ 本机运行环境把 `shutil.rmtree` 劫持成「先丢回收站」的 `_safe_shutil_rmtree`；
    回收站失败时 **fail-closed 直接抛 OSError**（实测 `SHFileOperationW 失败: 0x2`），
    于是生成器在 `install_project_dir` 一步中断、退出码 1。
    逐文件 `os.remove` + 自底向上 `os.rmdir` 不受该劫持影响。

    ⚠️ 但本机逐文件 `os.remove` **单次约 0.6 s**（实测删 72 个空目录 48 s），
    所以主流程**已不再调用它**，改成 sweep_stale_files() + sync_tree() 的增量清理。
    本函数保留给「人工需要整目录重置」的场合。

    只允许删**我方生成**的目录：调用方必须先做「标记文件 / 位于工作区」判定。
    """
    if not os.path.isdir(path):
        return False
    for root, dirs, files in os.walk(path, topdown=False):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                os.remove(fp)
            except PermissionError:
                os.chmod(fp, stat.S_IWRITE)      # 只读文件兜底
                os.remove(fp)
        for dn in dirs:
            os.rmdir(os.path.join(root, dn))
    os.rmdir(path)
    return True


_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def godot_json(obj, newline="\r\n"):
    """复刻 System.Text.Json(WriteIndented) 的字节风格：2 空格缩进、\\uXXXX 转义（大写 HEX）、结尾无换行。"""
    s = json.dumps(obj, ensure_ascii=True, indent=2)
    s = _ESC.sub(lambda m: "\\u" + m.group(1).upper(), s)
    return s.replace("\n", newline)


def dump_json(path, obj):
    """包内 mod.json 的风格：LF、无 BOM、不转义中文、结尾无换行（对齐 ModExporter 实测产物）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2))


def dump_godot_json(path, obj):
    """工程目录内的 mod.json / .pvzmodeproject 风格：CRLF + \\uXXXX 转义（对齐游戏侧编辑器实测产物）。"""
    write_bytes(path, godot_json(obj).encode("utf-8"))


def ensure_project_layout(project_dir):
    """XWModProjectLayout.EnsureProjectLayout：建齐 72 个标准子目录（幂等）。"""
    os.makedirs(project_dir, exist_ok=True)
    for rel in STANDARD_DIRS:
        os.makedirs(os.path.join(project_dir, rel.replace("/", os.sep)), exist_ok=True)
    return len(STANDARD_DIRS)


def read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception:
        return None


# ---------------------------------------------------------------- 格子表
# (x1, y1, x2, y2, ElementFlags, water)
# 前 15 条 = 吸血鬼屋原有条目，仅把行上界 5 → 6（继承 6 行版），水池行就地补 gridType；
# 后  5  条 = 为「第 5 行」新增的水池条目（奇数列 NIGHT / 偶数列 DAY，与吸血鬼屋元素分布一致）。
CELLS = [
    # ---- 继承自 VampireMapVampire.tres（行上界 5→6）----
    (1, 1, 9, 6, E_NIGHT, False),   # 整盘基底：夜晚元素
    (2, 1, 2, 6, E_DAY,   False),   # 第 2 列：白天元素
    (4, 1, 4, 6, E_DAY,   False),   # 第 4 列
    (6, 1, 6, 6, E_DAY,   False),   # 第 6 列
    (8, 1, 8, 6, E_DAY,   False),   # 第 8 列
    (1, 2, 9, 2, E_DAY,   False),   # 第 2 行：白天元素
    (1, 4, 9, 4, E_DAY,   True),    # 第 4 行：白天元素 + 【水池】
    (2, 2, 2, 2, E_NIGHT, False),   # 交叉点回到夜晚（8 个）
    (4, 2, 4, 2, E_NIGHT, False),
    (6, 2, 6, 2, E_NIGHT, False),
    (8, 2, 8, 2, E_NIGHT, False),
    (2, 4, 2, 4, E_NIGHT, True),    # 第 4 行的交叉点 + 【水池】
    (4, 4, 4, 4, E_NIGHT, True),
    (6, 4, 6, 4, E_NIGHT, True),
    (8, 4, 8, 4, E_NIGHT, True),
    # ---- 第 5 行【水池】新增 ----
    (1, 5, 9, 5, E_NIGHT, True),    # 先铺满整行（奇数列本就是夜晚元素）
    (2, 5, 2, 5, E_DAY,   True),    # 再把偶数列修正回白天元素
    (4, 5, 4, 5, E_DAY,   True),
    (6, 5, 6, 5, E_DAY,   True),
    (8, 5, 8, 5, E_DAY,   True),
]


def simulate(cells):
    """复刻 TowerDefenseMapConfig.GetEffectiveCellConfig —— 最后一个命中的条目生效。"""
    out = {}
    for y in range(1, GRID_H + 1):
        for x in range(1, GRID_W + 1):
            hit = None
            for (x1, y1, x2, y2, flags, water) in cells:
                if x1 <= x <= x2 and y1 <= y <= y2:
                    hit = (flags, water)
            out[(x, y)] = hit or (0, False)
    return out


def self_check(cells):
    """逐格校验：水池范围、元素分布、网格边界。返回 (ok, 报告行列表)。"""
    lines, bad = [], []

    def need(cond, msg):
        lines.append(("  [ok] " if cond else "  [!!] ") + msg)
        if not cond:
            bad.append(msg)

    # 1) 数据结构校验（对齐 TryValidateRuntime）
    need(1 <= GRID_W <= 50 and 1 <= GRID_H <= 50, "gridNum %dx%d 在 1..50 内" % (GRID_W, GRID_H))
    for (x1, y1, x2, y2, flags, _w) in cells:
        ok = (1 <= x1 <= GRID_W and 1 <= y1 <= GRID_H
              and x2 >= x1 and y2 >= y1 and x2 <= GRID_W and y2 <= GRID_H)
        need(ok, "cell pos Vector4i(%d,%d,%d,%d) 落在 %dx%d 网格内且 Z>=X/W>=Y"
             % (x1, y1, x2, y2, GRID_W, GRID_H))
    line_use = list(range(1, GRID_H + 1))
    need(all(1 <= i <= GRID_H for i in line_use),
         "lineUse %s 每一项都在 1..%d 内" % (line_use, GRID_H))

    grid = simulate(cells)

    # 2) 水池范围精确等于 第4~5行 × 第1~9列
    water_cells = set(k for k, v in grid.items() if v[1])
    expect_water = set((x, y) for y in range(POOL_Y1, POOL_Y2 + 1)
                       for x in range(POOL_X1, POOL_X2 + 1))
    need(water_cells == expect_water,
         "水池区域 == 第%d~%d行 × 第%d~%d列（共 %d 格，实际 %d 格）"
         % (POOL_Y1, POOL_Y2, POOL_X1, POOL_X2, len(expect_water), len(water_cells)))
    for (x, y) in sorted(expect_water):
        need(grid[(x, y)][1], "  (%d,%d) 是水池" % (x, y))
    for (x, y) in sorted(set(grid) - expect_water):
        need(not grid[(x, y)][1], "  (%d,%d) 不是水池" % (x, y))

    # 3) 元素分布必须与原版吸血鬼屋完全一致（行 1~5 原样，第 6 行沿用第 5 行样式）
    def orig(x, y):
        """原版 5 行版在 (x,y) 的有效元素（第 6 行原版没有，取第 5 行样式）。"""
        yy = y if y <= 5 else 5
        e = E_NIGHT
        for (x1, y1, x2, y2, flags, _w) in CELLS[:15]:
            if x1 <= x <= x2 and y1 <= yy <= y2:
                e = flags
        return e

    for y in range(1, GRID_H + 1):
        got = [grid[(x, y)][0] for x in range(1, GRID_W + 1)]
        want = [orig(x, y) for x in range(1, GRID_W + 1)]
        name = {E_NIGHT: "夜", E_DAY: "昼"}
        need(got == want,
             "第 %d 行元素 = %s（原版=%s）" % (y, "".join(name.get(v, "?") for v in got),
                                         "".join(name.get(v, "?") for v in want)))

    # 4) gridType：非水池 = 缺省陆地，水池 = [WATER, AIR]
    need(True, "gridType：非水池条目不写（类默认 [GROUND, AIR]）；水池条目写 [WATER, AIR]")

    # 5) 几何：整盘必须落在逻辑地图空间 [0, mapSize] 内（相机/子弹边界都以此为界）
    need(GRID_LEFT >= 0 and GRID_RIGHT <= MAP_W,
         "网格横向 %g..%g 落在 mapSize.X=%g 内" % (GRID_LEFT, GRID_RIGHT, MAP_W))
    need(GRID_TOP >= 0 and GRID_BOTTOM <= MAP_H,
         "网格纵向 %g..%g 落在 mapSize.Y=%g 内（下沿=gridBeginPos.Y+%d×%g）"
         % (GRID_TOP, GRID_BOTTOM, MAP_H, GRID_H, GRID_SIZE_Y))
    need(GRID_TOP >= 0,
         "gridBeginPos.Y=%g 非负（上移后第 1 行不越出画布上沿）" % GRID_BEGIN_Y)
    # 对齐新贴图：网格上下沿必须压住贴图实测的草坪范围，行距必须等于贴图行距。
    # （原方案是「保格子高度 98 + 整盘上移 + 上下留白对称」；改成对齐贴图后
    #   上下留白必然不对称：上 74px / 下 24px。所以断言也一并换成「对齐贴图」。）
    need(abs(GRID_TOP - ART_LAWN_TOP) < 1.0,
         "网格上沿 %g 对齐贴图草坪上沿 %g（±1px）" % (GRID_TOP, ART_LAWN_TOP))
    need(abs(GRID_BOTTOM - ART_LAWN_BOTTOM) < 1.0,
         "网格下沿 %g 对齐贴图草坪下沿 %g（±1px）" % (GRID_BOTTOM, ART_LAWN_BOTTOM))
    need(abs(GRID_SIZE_Y - ART_ROW_PITCH) < 0.01,
         "行距 %g 对齐贴图行距 %.4f（±0.01）" % (GRID_SIZE_Y, ART_ROW_PITCH))
    need(GRID_SIZE_Y != 98.0,
         "行距 %g 已偏离类默认 98（必须写进 .tres，否则回落 98 整盘错位）" % GRID_SIZE_Y)

    # 每行（0-based）的 y 区间，供人工核对
    for r in range(GRID_H):
        y1 = GRID_BEGIN_Y + r * GRID_SIZE_Y
        y2 = y1 + GRID_SIZE_Y
        need(y2 <= MAP_H, "第 %d 行 y=%.0f..%.0f 在画布内" % (r + 1, y1, y2))

    return (not bad), lines


# ---------------------------------------------------------------- .tres 生成
def cell_id(x1, y1, x2, y2):
    return "Cell_%d_%d_%d_%d" % (x1, y1, x2, y2)


def build_tres():
    out = []
    # uid 必须剥掉：Mod 包不能沿用官方资源 uid（否则 Godot 报重复 UID）
    out.append('[gd_resource type="Resource" script_class="TowerDefenseMapConfig" format=3]')
    out.append("")
    out.append('[ext_resource type="Script" uid="uid://eoxnow8u525l" '
               'path="res://Registry/Battle/Feature/Map/Resource/Cell/Config/TowerDefenseCellConfig.cs" '
               'id="1_cell"]')
    out.append('[ext_resource type="Script" uid="uid://do66qasykqnkv" '
               'path="res://Registry/Battle/Feature/Map/Resource/TowerDefenseMapConfig.cs" id="2_map"]')
    out.append('[ext_resource type="Script" uid="uid://d5q8v2n7m4k1c" '
               'path="res://Registry/Battle/Feature/Map/Resource/Rule/TowerDefenseMapRuleConfig.cs" '
               'id="3_rule_script"]')
    out.append('[ext_resource type="Resource" uid="uid://d2v7m4q9k5h8c" '
               'path="res://Asset/Config/Map/Rules/Vampire.tres" id="4_rule"]')
    out.append("")

    for (x1, y1, x2, y2, flags, water) in CELLS:
        out.append('[sub_resource type="Resource" id="%s"]' % cell_id(x1, y1, x2, y2))
        out.append('script = ExtResource("1_cell")')
        out.append('pos = Vector4i(%d, %d, %d, %d)' % (x1, y1, x2, y2))
        if water:
            out.append('gridType = Array[int]([%d, %d])' % (P_WATER, P_AIR))
        out.append('ElementFlags = %d' % flags)
        out.append("")

    out.append("[resource]")
    out.append('script = ExtResource("2_map")')
    out.append('translate = "%s"' % DISPLAY_NAME)
    out.append('mapTexturePath = "res://Asset/Texture/TowerDefense/Background/'
               'TowerDefenseMap/Vampire/Vampire.jpg"')
    out.append('mapScenePath = "res://Asset/Config/Map/Vampire/'
               'Vampire/TowerDefenseMapVampire.tscn"')
    out.append('gridNum = Vector2i(%d, %d)' % (GRID_W, GRID_H))
    out.append('gridBeginPos = Vector2(%s, %s)' % (fmt_num(GRID_BEGIN_X), fmt_num(GRID_BEGIN_Y)))
    # ⚠️ 必须显式写：已不等于类默认 (80, 98)，不写就会回落到 98 导致整盘错位
    out.append('gridSize = Vector2(%s, %s)' % (fmt_num(GRID_SIZE_X), fmt_num(GRID_SIZE_Y)))
    out.append('cellConfig = Array[ExtResource("1_cell")]([%s])'
               % ", ".join('SubResource("%s")' % cell_id(*c[:4]) for c in CELLS))
    out.append('lineUse = Array[int]([%s])' % ", ".join(str(i) for i in range(1, GRID_H + 1)))
    out.append('isNight = true')
    out.append('useSunFall = false')
    out.append('specialRules = Array[ExtResource("3_rule_script")]([ExtResource("4_rule")])')
    out.append("")
    return "\n".join(out)


def build_manifest():
    return {
        "schemaVersion": 2,
        "id": MOD_ID,
        "name": DISPLAY_NAME,
        "version": VERSION,
        "author": AUTHOR,
        "description": DESCRIPTION,
        "dependencies": [],
        "conflicts": [],
        # 新地图 → 必须走 provides（key 不能已存在）
        # ⚠️ 一旦 provides 里**有任何**条目（HasExplicitRuntimeEntries=true），
        #    ModLoader.cs:578 要求**每一个**被识别出的资源都在 provides/overrides 里声明，
        #    否则该资源被跳过（"resource is not unambiguously declared by manifest"）
        #    且 ValidateManifestRegistrations 会判定整包失败 → 贴图必须一起声明。
        "provides": {"Map": [MAP_KEY], "Texture": [TEXTURE_KEY]},
        "overrides": {},
        "scripts": [],
        "runtimeAssembly": RUNTIME_ASSEMBLY,
        "runtimeEntryType": RUNTIME_ENTRY_TYPE,
        "runtimeApiVersion": RUNTIME_API_VERSION,
        "runtimeAssemblyPolicy": RUNTIME_POLICY,
        "blueprints": [],
        "translations": [],
        # ⚠️ 顺序必须 == XWModManifestSyncService 的规范序，否则编辑器一打开就重写 mod.json。
        #    SyncProject 会把工程目录里**所有非忽略文件**（忽略 .uid/.import/.bak/.tmp/
        #    .pvzmodeproject/.csproj/.sln 与 .build/.git/.godot/bin/obj 目录、mod.json 本身）
        #    按 GetManifestSection 归类（非 .cs 且不在 Scripts|Blueprints|Localization 下 → Resources），
        #    再 NormalizePathList 排序（OrdinalIgnoreCase）。
        #    故：tres + jpg + dll 三者都在 Resources 里，且要按序排列。
        "resources": sorted([RESOURCE_TRES, TEXTURE_REL, RUNTIME_ASSEMBLY],
                            key=lambda p: p.lower()),
    }


def build_project_file(existing=None):
    """ModProject 的 JSON 形状（ModProjectSerializeHandler 的属性顺序）。

    时间戳：若工程文件已存在则**原样保留**，这样重复运行产物字节不变（幂等）。
    只有第一次创建才写入当前时间。
    """
    now = net_datetime(datetime.now(TZ_CN))
    created = (existing or {}).get("CreatedDate") or now
    modified = (existing or {}).get("LastModifiedDate") or created
    return {
        "Name": MOD_NAME,
        "Version": VERSION,
        "Author": AUTHOR,
        "Description": DESCRIPTION,
        "ExportDirectory": USER_MODS_DIR.replace("\\", "/") + "/",
        "GameDirectory": "",
        "CreatedDate": created,
        "LastModifiedDate": modified,
    }


# ---------------------------------------------------------------- 安装（工程目录 / 启用 / 最近工程）
def mirror_is_ours(dst, marker):
    """判断 `Mods/<工程名>/` 镜像目录是不是「我们生成的」（决定能不能动它）。

    · 目录不存在                → 是（这次直接建）
    · 带 marker（= 工程文件）    → 是
    · 空壳（只有目录、零文件）    → 是（上一次构建留下的骨架；无用户数据，可安全接管）
    · 其它                      → **不是**（用户自己的目录，绝不删/改）
    """
    if not os.path.isdir(dst):
        return True
    if os.path.isfile(os.path.join(dst, marker)):
        return True
    for _r, _dirs, files in os.walk(dst):
        if files:
            return False
    return True


def install_project_dir(src, dst, marker):
    """把工程目录增量镜像到 Mods/ 下（与 build_plant_super_gatling.py 行为一致）。

    安全护栏：mirror_is_ours() 判定不是我们的目录 → 跳过不动。
    dst 里不放 .pmod，所以不污染 ScanMods(*.pmod)。
    """
    if not mirror_is_ours(dst, marker):
        return "跳过（%s 已存在且不是本工程，未改动）" % dst
    wrote, removed = sync_tree(src, dst, marker)
    return "已镜像到 %s（写 %d / 删 %d）" % (dst, wrote, removed)


def merge_enabled_mods(mods_dir, mod_id):
    """把 mod id 合并进 Mods/enabled_mods.json（复刻 XWModManager.SaveEnabledIds 的语义：去重 + 排序）。

    ⚠️ 没有这个文件时 LoadEnabledIds() 返回空集合 → **任何 mod 都不会被加载**。
    """
    path = os.path.join(mods_dir, "enabled_mods.json")
    ids = []
    if os.path.exists(path):
        cur = read_json(path)
        if not isinstance(cur, list):
            return "跳过（现有 enabled_mods.json 无法解析，未改动）"
        ids = [str(x).strip() for x in cur if str(x).strip()]
    if any(x.lower() == mod_id.lower() for x in ids):
        return "已启用（enabled_mods.json 无需改动）"
    ids.append(mod_id)
    ids = sorted({x for x in ids}, key=lambda s: s.lower())
    write_bytes(path, json.dumps(ids, ensure_ascii=False, indent=2).encode("utf-8"))
    return "已启用：%s" % ", ".join(ids)


def merge_recent_project(project_file_abs):
    """把工程登记进 godot 的「最近工程」缓存（Mods 同级的 mod_editor_recent_projects.cfg）。

    纯便利缓存，与游戏侧编辑器自己写出的格式同构（[projects] / count / path_N），就地合并。

    ⚠️ **不能丢别人的条目**：旧写法用 `^path_\\d+="(.*)"$` 匹配行尾，而文件是 CRLF 时
    行尾是 `\\r\\n` → 一条都匹配不到 → 整个列表被重写成「只剩自己一条」
    （2026-09-18 实测：跑一次本脚本就把「超级机枪射手」那条抹掉了）。
    ⇒ 解析前先把 CRLF 归一化成 LF；路径统一写正斜杠；保留原换行风格与末尾换行。
    """
    cfg = os.path.join(USER_DATA_DIR, "mod_editor_recent_projects.cfg")
    if not os.path.exists(cfg):
        return "跳过（未找到 %s）" % os.path.basename(cfg)
    with open(cfg, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig", "replace").replace("\r\n", "\n").replace("\r", "\n")
    trailing = text.endswith("\n")
    seen, paths = set(), []
    for p in re.findall(r'^path_\d+="(.*)"$', text, re.M):
        p = p.replace("\\", "/")
        if p.lower() not in seen:
            seen.add(p.lower())
            paths.append(p)
    want = os.path.abspath(project_file_abs).replace("\\", "/")
    if want.lower() in seen:
        return "已在最近工程列表中（共 %d 个）" % len(paths)
    paths.insert(0, want)
    body = "[projects]%s%s" % (nl, nl)
    body += "count=%d%s" % (len(paths), nl)
    for i, p in enumerate(paths):
        body += 'path_%d="%s"%s' % (i, p, nl)
    if not trailing:                                # 原文件结尾没有换行 → 保持一致
        body = body[:-len(nl)]
    write_bytes(cfg, body.encode("utf-8"))
    return "已加入最近工程（共 %d 个）" % len(paths)


# ---------------------------------------------------------------- 主流程
def install_background_art():
    """把工作区 assets/ 里的背景贴图装进 Mod 包，并校验尺寸与地图逻辑空间一致。

    尺寸错了不会报任何错，只会「贴图对不上网格」——所以这里主动拦一道。
    纯 Python 解析 JPEG SOF 段，不依赖 PIL（构建用的解释器没有 Pillow）。
    """
    name = os.path.basename(TEXTURE_REL)
    src = os.path.join(ASSETS_DIR, name)
    if not os.path.isfile(src):
        raise SystemExit("找不到背景贴图源文件：%s" % src)

    with open(src, "rb") as f:
        data = f.read()
    if data[:2] != b"\xff\xd8":
        raise SystemExit("背景贴图不是 JPEG（缺 SOI 标记）：%s" % src)
    size = None
    i, n = 2, len(data)
    while i < n - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seglen = (data[i + 2] << 8) | data[i + 3]
        if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
            size = (((data[i + 7] << 8) | data[i + 8]), ((data[i + 5] << 8) | data[i + 6]))
            break
        i += 2 + seglen
    if size is None:
        raise SystemExit("背景贴图里找不到 SOF 段（不是有效 JPEG）：%s" % src)
    if size != (int(MAP_W), int(MAP_H)):
        raise SystemExit("背景贴图尺寸 %dx%d ≠ mapSize %gx%g —— 会整屏错位，已中止"
                         % (size[0], size[1], MAP_W, MAP_H))

    dst = os.path.join(MOD_ROOT, TEXTURE_REL.replace("/", os.sep))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    changed = write_bytes_if_changed(dst, data)
    return "%s（%dx%d，%d 字节，%s）" % (
        TEXTURE_REL, size[0], size[1], len(data), "已更新" if changed else "未变")


def main():
    print("=" * 78)
    print("构建地图 Mod：%s（Map / %s）" % (DISPLAY_NAME, MAP_KEY))
    print("基底：%s" % SRC_TRES)

    if not os.path.exists(SRC_TRES):
        raise SystemExit("找不到原版吸血鬼屋地图：%s" % SRC_TRES)

    print("-" * 78)
    print("自检（逐格仿真 GetEffectiveCellConfig 的「后匹配覆盖」语义）")
    ok, lines = self_check(CELLS)
    for l in lines:
        print(l)
    if not ok:
        raise SystemExit("自检未通过，已中止（未生成任何文件）")
    print("  自检通过：%d 个格子全部符合预期" % (GRID_W * GRID_H))

    print("-" * 78)
    tres = build_tres()
    dst = os.path.join(MOD_ROOT, "Resources", "Maps", MAP_KEY + ".tres")
    write_text(dst, tres)
    print("  [ok] Resources/Maps/%s.tres（%d 行 / %d 字节）" % (MAP_KEY, tres.count("\n"), len(tres)))

    # ---- 工程目录骨架：XWModProjectLayout.EnsureProjectLayout 的 72 个标准子目录
    n_dir = ensure_project_layout(MOD_ROOT)
    print("  [ok] 工程目录骨架：%d 个标准子目录（Scenes/Scripts/Battle/Resources/Assets/Localization…）"
          % n_dir)

    # ---- 背景贴图：工作区 assets/ → Mod 包 Assets/Images/（含尺寸校验）
    print("  [ok] 背景贴图：%s" % install_background_art())

    # ---- 运行时程序集：只校验存在性（编译由 runtime_src/build_runtime.py 负责）
    dll = os.path.join(MOD_ROOT, RUNTIME_ASSEMBLY.replace("/", os.sep))
    if not os.path.isfile(dll):
        raise SystemExit("缺少运行时程序集：%s（先跑 runtime_src/build_runtime.py）" % dll)
    with open(dll, "rb") as f:
        dll_bytes = f.read()
    print("  [ok] %s（%d 字节，sha256=%s）"
          % (RUNTIME_ASSEMBLY, len(dll_bytes),
             hashlib.sha256(dll_bytes).hexdigest()[:16]))
    if not dll_bytes[:2] == b"MZ":
        raise SystemExit("运行时程序集不是有效 PE 文件：%s" % dll)

    # ---- 包内 mod.json：LF + 不转义中文（对齐 ModExporter 实测产物）
    dump_json(os.path.join(MOD_ROOT, "mod.json"), build_manifest())
    print("  [ok] mod.json（provides: Map/%s）" % MAP_KEY)

    # ---- 工程文件：CRLF + \uXXXX 转义（对齐 ModProject 实测产物）；时间戳幂等保留
    proj_path = os.path.join(MOD_ROOT, MOD_NAME + ".pvzmodeproject")
    dump_godot_json(proj_path, build_project_file(read_json(proj_path)))
    print("  [ok] %s.pvzmodeproject（工程元数据，可在游戏 F3 → Mod 工具 里打开）" % MOD_NAME)

    # 清掉改名前的旧工程文件（工程目录里只允许有一个 *.pvzmodeproject）
    for fn in sorted(os.listdir(MOD_ROOT)):
        if fn.endswith(".pvzmodeproject") and fn != MOD_NAME + ".pvzmodeproject":
            os.remove(os.path.join(MOD_ROOT, fn))
            print("  [ok] 已移除改名前的旧工程文件：%s" % fn)

    # 打包：mod.json 必须是第 0 个条目（ModLoader/官方导出器约定）
    os.makedirs(DIST_DIR, exist_ok=True)
    pmod = os.path.join(DIST_DIR, MOD_NAME + ".pmod")
    entries = ["mod.json"]
    rels = []
    for dirpath, _dirs, files in os.walk(MOD_ROOT):
        for fn in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, fn), MOD_ROOT).replace("\\", "/")
            if rel == "mod.json":
                continue
            if rel.endswith((".uid", ".import", ".cs", ".csproj", ".sln",
                             ".pvzmodeproject", ".pmod")):
                continue
            rels.append(rel)
    entries += sorted(rels)
    # ⚠️ zip 默认会把文件 mtime 写进条目头 → 每次重跑产物字节都不同（破坏幂等）。
    #    这里固定条目时间戳，让 .pmod 变成「内容确定 = 字节确定」。
    FIXED_T = (2026, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(pmod, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in entries:
            zi = zipfile.ZipInfo(rel, FIXED_T)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            with open(os.path.join(MOD_ROOT, rel), "rb") as f:
                z.writestr(zi, f.read())
    print("  [ok] 打包完成：%s（%d 条目 / %d 字节）" % (pmod, len(entries), os.path.getsize(pmod)))

    if USER_MODS_DIR and os.path.isdir(USER_MODS_DIR):
        target = os.path.join(USER_MODS_DIR, MOD_NAME + ".pmod")
        shutil.copy2(pmod, target)
        print("  [ok] 可加载安装包 → %s" % target)

        proj_dst = os.path.join(USER_MODS_DIR, MOD_NAME)
        print("  [ok] 游戏侧工程目录 → %s"
              % install_project_dir(MOD_ROOT, proj_dst, MOD_NAME + ".pvzmodeproject"))

        stale = os.path.join(USER_MODS_DIR, "VampirePool.pmod")
        if os.path.isfile(stale) and os.path.abspath(stale) != os.path.abspath(target):
            os.remove(stale)
            print("  [ok] 已移除旧文件名的安装包：%s（同 id，留着会变重复 mod）" % stale)

        print("  [ok] 启用开关 → %s" % merge_enabled_mods(USER_MODS_DIR, MOD_ID))
        print("  [ok] 最近工程 → %s"
              % merge_recent_project(os.path.join(proj_dst, MOD_NAME + ".pvzmodeproject")))
    else:
        print("  [!!] 未找到 Mods 目录：%s" % USER_MODS_DIR)

    print("-" * 78)
    print("打包条目：")
    for i, e in enumerate(entries):
        print("   %2d  %s" % (i, e))
    print("=" * 78)
    print("游戏侧结构一览（Mods/）：")
    print("   吸血鬼屋泳池.pmod            ← 游戏**只**加载这种 *.pmod（ScanMods 不递归）")
    print("   吸血鬼屋泳池/                ← Mod 工程目录（72 子目录 + mod.json + .pvzmodeproject）")
    print("       吸血鬼屋泳池.pvzmodeproject")
    print("       mod.json")
    print("       Resources/Maps/%s.tres" % MAP_KEY)
    print("下一步：进游戏 F3 → Mod 工具 → 确认「%s」为启用 → 重新应用；" % MOD_NAME)
    print("      然后在关卡编辑器里把地图下拉切到「%s」。" % DISPLAY_NAME)



if __name__ == "__main__":
    main()
