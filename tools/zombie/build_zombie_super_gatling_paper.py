"""生成《超级机枪读报僵尸》僵尸 Mod（数据 + 托管运行时插件）。

需求（2026-09-19 用户指定，1:1 对应到实现）：
  1. 名称 = **超级机枪读报僵尸**         → `packet.name`（直接写中文，见第四节）
  2. 贴图暂用读报僵尸的贴图               → 场景 / 卡片全部复用内置 `Chapter1/Paper` 的美术资源
  3. 每 1.5 秒向前方直线发射 7 颗豌豆，仅 7 颗
       → 形态取「连发成链」（约 0.1s 一颗，7 颗排成一条直线）；
         节拍与颗数**纯数据做不到** ⇒ 由托管插件逐颗调 `FireComponent.Fire()`（见第五/七节）
  4. 每次攻击有 10% 概率触发大招：5 秒内向 ±15° 范围内散射 300 颗豌豆
       → 同样是插件（`FireComponentFireProjectileConfig` 没有概率/时窗/逐发随机角字段）
  5. 血量 500（二类防具）+ 1250（本体），移速 = 普通僵尸，伤害 800，伤害类型 = 啃食
       → 防具 = 包内 SlotConfig `damagePoint = 500.0`（Paper 内置 flags = 68 = SHIELD|DAMAGEABLE
         ⇒ 天然的「二类护具层」）；本体 = `hitpoints + hitpointsNearDeath = 1250`
       → 移速 = **什么都不写**（普通僵尸与读报僵尸都沿用基场景 `walkSpeedScale = 1.0`）
       → 伤害 800 = `TowerDefenseZombieConfig.attack`；啃食 = AttackComponent 默认 `attackType = "Eat"`
  6. 二类防具掉落后移速 ×3
       → **内置读报僵尸脚本自带**：`ArmorHitpointsEmpty("Paper")` → `SendStateEvent("ToGasp")`
         → `AnimeCompleted("Gasp")` → `timeScaleInit = 3.0; angry = true; Walk();`
         ⇒ 场景脚本直接引用 `res://…/Paper/Scene/TowerDefenseZombiePaper.cs`，零插件成本

────────────────────────────────────────────────────────────────────────
一、为什么「复用内置读报僵尸的脚本」是安全的（不是抄近道）
────────────────────────────────────────────────────────────────────────

Mod 角色包的**根场景脚本**用 `res://` 指向**游戏自带**脚本是完全合规的：

  · `ModLoader.SanitizeCharacterTextResource()`（`ModLoader.cs:1418-1463`）只做两件事：
      - 含 `type="GDScript"` / `type="CSharpScript"` 字面量 → **拒绝**（不许内嵌脚本）；
      - `[ext_resource … type="Script"]` 的 path **非** `res://` →
        .tscn 里**剥离**该引用及其 `ExtResource("id")` 行、.tres 里**直接拒绝**整包。
    ⇒ `type="Script" path="res://Asset/…/Paper/Scene/TowerDefenseZombiePaper.cs"` 是**保留**的。
  · 内置角色场景自己就是这么引用脚本的（`TowerDefenseZombiePaper.tscn` 第 4 行），
    说明该 `.cs` 在导出包里是**可加载的 Script 资源**。
  · ⚠️ 绝对**不要**加 `metadata/mod_character_script_binding = "CompanionOnly"`：
    `ModLoader.CharacterRequiresCompanion()` 一读到这个 meta 就会去要
    `mod.CharacterCompanionRuntime`，拿不到 → 该资源被拒 → 整包回滚。

`TowerDefenseZombiePaper.cs` 提供我们需要的两条关键行为：
  · `ArmorHitpointsEmpty("Paper")` → `ToGasp` 状态 → 3 倍速暴走（**需求 6**，白送）；
  · `angry = true` 后把 `walkAnimeClip / attackAnimeClip` 换成 `AngryWalk / AngryEat`，并换掉头部贴图。
  ⇒ 我们只是「换数值 + 加一门机枪」，暴走机制**逐字沿用**。

────────────────────────────────────────────────────────────────────────
二、包结构（角色包 6 段硬约束 + 本包新增的 Armor 子目录）
────────────────────────────────────────────────────────────────────────

    <Key>/Scene/<Key>.tscn                    ← 运行场景（6 段硬约束）
    <Key>/Scene/<Key>ComponentSet.tres        ← 组件集（父集 + 一个发射组件）
    <Key>/Scene/<Key>FireComponentDefinition.tres
    <Key>/Config/TowerDefense<Key>.tres       ← 角色配置
    <Key>/Sprite/<Key>.tscn                   ← 精灵场景（CharacterSprite 注册点）
    <Key>/Packet/<Key>.tres                   ← 卡片镜像（本包保留，与内置角色目录同构）
    <Key>/Armor/<Key>ArmorData.tres           ← ★ 本包新增：护具表（Paper 换成 500 血的那份）
    <Key>/Armor/Config/<Key>ArmorPaper.tres   ← ★ 本包新增：Paper 的 SlotConfig（damagePoint = 500）
    + Resources/Cards/<Key>.tres              ← ★ 注册位置（Packet 键 = 文件名去扩展）
    + Runtime/ModAssembly.dll                 ← 托管插件

⚠️ `PrepareSafeCharacterPackage`（`ModLoader.cs:1389-1416`）会遍历
   `Resources/Characters/<类>/<Key>/` 前缀下的**每一个**文件：
     · `.scn` / `.res` → 拒绝整包（所以包内不许出现二进制资源）；
     · `.tscn` / `.tres` → 逐个跑 `SanitizeCharacterTextResource`。
   ⇒ 我们的两个 Armor `.tres` 也在该前缀下，必须同样满足「Script 引用必须是 res://」。

────────────────────────────────────────────────────────────────────────
三、路径/命名硬约束（违反 = 整包「不加载」，不是「不生效」）
────────────────────────────────────────────────────────────────────────

  a) `ModLoader.TryInferCharacterScene()`：路径**恰好 6 段**、
     [0]=Resources、[1]=Characters、[2]∈已知类别、[4]=="Scene"、[5] 扩展名 .tscn、
     且 **文件名 == 目录名 == Key**。本包 Key = `ZombieSuperGatlingPaper`。
     Sprite 同理，只是 [4]=="Sprite"。
  b) `IsKnownCharacterCategory()`：Plants/Zombies/Props/Vases/Mowers/Items/Graves/Craters。
     本包用 `Zombies`。
  c) **包内自引用必须相对路径**（`./`、`../`），只有指向游戏自带资源
     （res://Prefab|Asset|Script|Resource|Registry|Extends|addons）才用 `res://`。
     机制：ModLoader 把包解到 `user://ModsCache/<名>/` 再用该路径加载场景，
     所以 `../Config/xxx.tres` 在 user:// 树里解析成功；而
     `res://Resources/Characters/...` 会在**游戏 pck 根**解析 —— 那里没有 `Resources/`，必然失败。
  d) `XWModContentValidation.Validate()` 对 Packet 三个闸门：
     - `packet.saveKey == 注册键`（注册键 = `Resources/Cards/<文件名去扩展>`，`ModLoader.cs:1077`）；
     - `characterConfig.name` 必须已注册进 `TOWERDEFENSE_CHARCATERS`
       ⇒ `config.name` **必须**等于 Key（**不能**写中文！）；
     - `CHARCTAER_SPRITE` 必须含 saveKey 或 config.name ⇒ 必须有 `Sprite/<Key>.tscn`；
     - `unlockCheckList` 只能空表或 `XWModProgressUnlockCondition`（空表 = 直接可用）。

⚠️ 特别提醒：`config.name` 是**内部键**（插件也靠它认人），
   `packet.name` 才是**显示名**。两者在本包里**故意不同**：
   `config.name = "ZombieSuperGatlingPaper"`，`packet.name = "超级机枪读报僵尸"`。

────────────────────────────────────────────────────────────────────────
四、显示名为什么直接写中文（而不是翻译键 + translations.csv）
────────────────────────────────────────────────────────────────────────

内置卡片的 `packet.name` 是翻译键（如 `TOWERDEFENSE_ZOMBIE_NEWSPAPER_NAME`），
因为游戏启动时 `Global.cs` 会 `TranslationServer.SetLocale("zh")` 加载官方翻译表。

但 **ModLoader 全文没有任何 `TranslationServer.AddTranslation` 调用**（已全树 grep 确认）：
`manifest.translations` 只在 schema 校验 / 同步服务 / 引用图里被读写，
`Localization/*.csv` **不会**进入游戏运行时 ⇒ 用翻译键写，游戏里就显示原始 key。

所以本包把中文**直接写进** `packet.name` / `describe` / `handbookDescribe` / `handbookStory`。
⇒ 无需翻译表即可在游戏内正确显示中文（这是本包**不**带 `Localization/` 的原因）。

────────────────────────────────────────────────────────────────────────
五、数值映射（逐条有源码依据）
────────────────────────────────────────────────────────────────────────

**血量**：`TowerDefenseCharacterInstance._Init`
    `hitpoints = config.hitpoints + config.hitpointsNearDeath;`
    `hitpointsNearDeath` 同时是**濒死线**。
    ⇒ 需求「本体 1250」取**总血恰好 1250**：`hitpoints = 1180.0` + `hitpointsNearDeath = 70.0`。
      70 沿用内置读报僵尸（`TowerDefenseZombiePaper.tres` 就是 70.0），保住濒死阶段与暴走衔接。

**二类防具 500 血**：`TowerDefenseArmorInstance` 构造函数第 114 行
    `damagePointBase = ((slotConfig.damagePoint >= 0.0) ? slotConfig.damagePoint : typeData.damagePoint);`
    ⇒ 只要在 **SlotConfig** 上写 `damagePoint = 500.0`，就覆盖内置 `Paper` 的 150.0，
      **不需要**动 `Registry/Armor/Config/Paper.tres`（那是游戏注册表，只读）。
    「二类（护具）层」= `armorMethodFlags & SHIELD(4)`；内置 `Paper` 的 flags = **68 = 4|64**
      （`SHIELD | DAMAGEABLE`，且**没有** DROPABLE）⇒ 天生就是二类护具。
      文案依据：`Test/PlantWallnutQXLaserScreenDoorRuntimeTest.cs:92`「真实铁栅门必须进入 SHIELD 二类护具层。」

**移速 = 普通僵尸**：普通僵尸与读报僵尸**都不覆盖** `walkSpeedScale / timeScale`
    （两边的 .tscn 里都搜不到这两个键）⇒ 都沿用基场景 `TowerDefenseZombie.tscn` 的
    `walkSpeedScale = 1.0`。移动速度只由各自精灵 GroundSlot 动画驱动
    （`GroundMoveComponent` 读 slot 逐帧位移）。⇒ **本包什么都不写**，即是「与普通僵尸同速」。

**伤害 800 / 啃食**：`attack = 800.0`（`useAttackDps = true` ⇒ 800 作为每秒 DPS）。
    啃食 = `AttackComponentDefinition.attackType` 的默认值 `"Eat"`，
    **父组件集已带**（`TowerDefenseZombieComponentSet.tres` 引用
    `AttackComponentZombieDefinition.tres`，该文件未写 attackType ⇒ 用默认 "Eat"）。
    ⇒ 本包**不**再覆盖攻击组件（重复声明同一个 `InstanceId` 风险更大），只加发射组件。

**护具掉落后移速 ×3**：内置脚本链路，见开头需求 6。

**卡片**：`type` 取 `TowerDefenseEnum.PACKET_TYPE.ZOMBIE = 6`
    （NOONE=-1,WHITE=0,GOLD=1,DIAMOND=2,COLOUR=3,STAR=4,ORIGINAL=5,ZOMBIE=6,COVER=7,GRAY=8）；
    `cost = 100`、`packetCooldown = 5.0`（用户 2026-09-19 明确指定）。

其余字段**逐字沿用读报僵尸**（需求 2「贴图暂用读报僵尸」）：
    `weight = 2000`、`wavePointCost = 150`、`plantGridType = [-1]`、`maskFlags = 9`、
    `homeWorld = 1`、`ashScene = ZombieGeneralAsh.tscn`、
    `damagePointData` / `HitBoxDefinition` 直接引用内置读报僵尸的那两份（`res://` 绝对路径）——
    护具砸落、Arm/Head 两个部位的伤害点全靠它们；交 null 会把这些可见特性弄丢。

字段**书写顺序** = 类声明顺序（`TowerDefenseZombieConfig` 先、`TowerDefenseCharacterConfig` 后），
否则编辑器一保存就会把它重排（与植物包/上一版僵尸包同一约定）。

────────────────────────────────────────────────────────────────────────
六、★ 发射组件为什么「静默回落」，以及插件怎么打豌豆
────────────────────────────────────────────────────────────────────────

⚠️⚠️ **前置条件：场景必须显式声明 `ComponentSet`**（本包第一版漏了，症状 = 一颗豌豆都不出、
   且日志里连一条 warning 都没有）。基场景自带的那份组件集**不含 FireComponent**，
   子场景不覆盖 ⇒ 发射组件不会被创建 ⇒ 插件 `GetRuntime<FireComponent>("character.fire")`
   返回 null、`IsUsable()` 判否、hook 都挂不上。**修法就是场景根节点加一行**
   `ComponentSet = ExtResource("15")` 指向本包的 `<Key>ComponentSet.tres`
   （凭据见 `zombie_scene_tscn()` 的 docstring）。

读报僵尸的精灵 `ZombiePaper.tscn` **没有 Head 子精灵、也没有 HeadFire clip**
（只有 HeadSlot / ArmSlot / PaperSlot / GroundSlot 四个插槽）。
而 `FireComponent.AttackEntered()`（`FireComponent.cs:3224-3234`）第一句就是
    `if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(Idle); return; }`
`CanPlayFireAnimation("")` 恒为 false（`:1011-1014`）⇒ **动画驱动的发射链路整条失效**。

这是**设计好的降级路径**（数据层没有开火动画时打不出去），不是 bug。本包就顺着它走：
  · `fireAnimeClips` / `spritePath` / `isSpliceSprite` **一律不写**（写了也指不到东西）；
  · `FireComponent` 老实待在 Idle（`spliceIdleAnimeClips` 为空 ⇒ 连 `sprite.timeScale` 都不碰）；
  · 豌豆全部由插件调 **`FireComponent.Fire()`** 打出去。

`Fire()` 是 public（`:3429`）且**不受状态机约束**：
  只检查 `CanExecuteGameplay && alive && parent 有效 && parent.instance 有效`（`:3436`），
  然后 `for (i < _fireProjectiles)` 逐条创建子弹（`:3449-3502`）。
  `CanExecuteGameplay => IsInsideComponentBattlefield`（`CharacterComponentRuntime.cs:86`）
  —— 只要僵尸在战斗场内就能打，与它当前是走、是吃、有没有目标**无关**。
  ⇒ 正是需求 3/4 要的「无条件、按固定节拍」。

★ **逐发改方向为什么一定生效**：`Fire()` 读的是**私有** `_fireProjectiles`，
但 `RefreshExportedArrayCaches()`（`:964-965`）是
    `CopyGodotArray(fireCheckList, _fireChecks); CopyGodotArray(fireProjectileList, _fireProjectiles);`
—— **按引用拷贝**，两边是**同一批 Resource 对象**；`DuplicateRuntimeResources()` 的
`Duplicate(deep:true)` 被 `_runtimeResourcesIsolated` 守卫，只在装配期跑一次。
⇒ 运行期写 `fireProjectileList[i].dir = 角度` 后 `Fire()` 立刻按新角度发射。

★ **`firePosMarkerPaths` 必须是真正的 `Marker2D`**：
`ResolveReferences()`（`:1229-1234`）走 `ResolveOwnerNode<Marker2D>(path)`，
而 `ResolveOwnerNode<T>` 只做 `parent.GetNodeOrNull<T>(path)`。
`AdobeAnimateSlot`（如 `HeadSlot`）是普通 `Node2D` ⇒ 传进去只会得到 null、豌豆从僵尸原点出膛。
⇒ 本包在场景里**新增**一个 `Marker2D`：
    `SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker`
   挂在 `HeadSlot` 下面 ⇒ 自动跟随头部动画（含暴走换头），不需要我们算任何世界坐标。
   ⚠️ 这是**唯一**「靠猜」的坐标：`position = Vector2(0, 0)`（头部插槽原点）。
      出膛点若想再往嘴部挪，只改这一行即可（见交付文档「可微调点」）。

────────────────────────────────────────────────────────────────────────
七、插件（托管运行时）—— 需求 3 / 4 的唯一解法
────────────────────────────────────────────────────────────────────────

`FireComponentFireProjectileConfig` 只有 8 个字段
（`checkProjectileId / firePosId / speed / dir / offsetLine / fireNumSkip / fireEventNeed / projectileFlip`）
—— **没有概率、没有时窗、没有逐发随机角**。所以：

  · 需求 4（10% 概率 + 5 秒 + ±15° 随机）纯数据不可能；
  · 需求 3（**每 1.5 秒**整点连发 7 颗）也做不到：`FireComponent` 的自发发射是
    「有目标就发 → 动画事件 fire」，节拍由动画长度决定，且**无目标时一枪不发**。

本包带 `Runtime/ModAssembly.dll`（入口类 `SuperGatlingPaperRuntimeEntry`），
源码在 `../runtime_src_zombie_super_gatling/`，用
`python runtime_src_zombie_super_gatling/build_runtime.py --check` 编译
—— **必须先跑它**，否则 manifest.resources 指向的 DLL 不存在，本脚本会拒绝打包。

插件干两件事：
  ① 玩法（需求 3/4）：扫场景找 `config.name == "ZombieSuperGatlingPaper"` 的僵尸，
     取 `character.fire` 组件；之后按墙钟节拍逐颗调 `fire.Fire()`。
        · 普攻：每 1.5s 一个周期，周期起点打第 1 颗，随后每 0.1s 一颗 ⇒ 恰好 7 颗；
        · 大招：周期起点掷 10% 骰子，命中后 5s 内发 **300 颗**，
          第 k 颗时刻 = 起点 + k×(5000/300) ms（**按颗数算时刻，无浮点累加漂移**），
          角度 = 每颗独立 `RandfRange(-15, +15)`；期间**暂停普攻**，结束重新计时 1.5s。
  ② 可选性（需求 1 的「能选到它」）：把本卡补进**共享卡库** `GeneralZombie` 的 `Zombie` 分类。
     依据：`Almanac.cs:220` 图鉴僵尸页取的就是 `GetPacketBankData("GeneralZombie")`
     （**同一个实例**，不像植物页那样深拷贝）⇒ 补一处，选卡界面 / 关卡编辑器 / 图鉴同时生效。
     同时补 `Include` 闭包里的派生库（离线算出 = `TotalZombie`、`Total`）。

托管四字段硬约束（改错 = 整包被拒，不是「不生效」）：
  · `runtimeAssembly` 只能是**字面量** `"Runtime/ModAssembly.dll"`（ModLoader 字符串相等判定）；
  · `runtimeApiVersion` **恰好** 1；
  · `runtimeAssemblyPolicy = "optional"`（DLL 挂了不连坐角色）；
  · ⚠️ `TryInitializeRuntimeEntry` 失败 → `ModLoader.cs:667-671` **无条件整包回滚**，
    **不受 policy 保护** ⇒ 入口的 Initialize / OnAllModsLoaded / Shutdown **一律不许抛异常**。

幂等：所有产物字节确定（手写 .tscn/.tres 模板、zip 用固定时间戳 ZipInfo）。
工程目录 / Mods 镜像都走**增量**写入 + 增量清理（`sweep_stale_files` / `sync_tree`），
第二次以后运行不写一个字节、不删一个文件。

⚠️ 本机运行环境的文件删除钩子**每次调用约 0.6 s**，所以：
  · 不用 `shutil.rmtree`（被劫持成「丢回收站」，失败即 fail-closed 抛
    `SHFileOperationW 0x2`）；
  · 也不用「整目录删掉重建」的写法。
`safe_rmtree()` 保留，只在人工需要整目录重置时用。

工程目录结构照抄游戏侧编辑器：`STANDARD_DIRS` = XWModProjectLayout.StandardDirectories 的 72 项
（顺序原样），与 build_map_vampire_pool.py / build_plant_super_gatling.py / build_zombie_disco_pult.py 逐字相同。
"""

import io
import json
import math
import os
import re
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 路径与常量

HERE = os.path.dirname(os.path.abspath(__file__))            # ModWorkspace\
WS = HERE
MODS_DIR = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
USER_DATA_DIR = os.path.dirname(MODS_DIR)

BUILD_DIR = "SuperGatlingPaper"               # 工作区构建目录（ASCII）
MOD_NAME = "超级机枪读报僵尸"                    # Mods 下工程目录名 / .pvzmodeproject / .pmod 文件名
MOD_ID = "supergatlingpaper"                  # manifest.id（与 vampirepool / supergatlingpea 同为全小写）
CHAR_KEY = "ZombieSuperGatlingPaper"          # 角色 key（目录名 == 场景文件名 == config.name）
PKG_CAT = "Zombies"                           # IsKnownCharacterCategory 里的类别目录
MOD_ROOT = os.path.join(WS, BUILD_DIR)
DIST_DIR = os.path.join(WS, "dist")

# 原版资源（res:// 前缀，游戏内解析；本机解包用于校验存在性）
BASE_ZOMBIE_SCENE = "res://Prefab/TowerDefense/Character/TowerDefenseZombie.tscn"
BASE_ZOMBIE_COMPONENT_SET = "res://Prefab/TowerDefense/Character/ComponentSets/TowerDefenseZombieComponentSet.tres"
BASE_COMPONENT_SET_SCRIPT = "res://Script/Component/Runtime/CharacterComponentSet.cs"
BASE_ZOMBIE_CONFIG_SCRIPT = "res://Resource/TowerDefense/Character/Config/TowerDefenseZombieConfig.cs"
BASE_PACKET_SCRIPT = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs"

# 内置读报僵尸（本包复用的整套美术 / 脚本 / 状态机 / 伤害点）—— 需求 2
PAPER_DIR = "res://Asset/Anime/Character/Zombie/Chapter1/Paper"
PAPER_SCENE_SCRIPT = f"{PAPER_DIR}/Scene/TowerDefenseZombiePaper.cs"
PAPER_STATE_MACHINE = f"{PAPER_DIR}/Scene/TowerDefenseZombiePaperStateMachine.tres"
PAPER_SPRITE_SCENE = f"{PAPER_DIR}/ZombiePaper.tscn"
PAPER_DAMAGE_POINT_DATA = f"{PAPER_DIR}/DamagePoint/ZombiePaperDamagePointData.tres"
PAPER_DAMAGE_POINT_CONFIG_DIR = f"{PAPER_DIR}/DamagePoint/Config"
PAPER_ARMOR_CONFIG_DIR = f"{PAPER_DIR}/Armor/Config"
PAPER_HITBOX = "res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_44x70_At_4_n2.tres"
BASE_ASH_SCENE = "res://Asset/Anime/Character/Zombie/Ash/General/ZombieGeneralAsh.tscn"
BASE_WATER_LINE_SCENE = "res://Asset/Anime/Character/Zombie/WaterLine/ZombieWaterLine.tscn"

# ---------------------------------------------------------------------------
# 需求 1（2026-09-22 修正）：把僵尸的头换成「超级机枪射手」的头
# ---------------------------------------------------------------------------
#
# 方案 = 官方「僵尸身 + 换头」范式（`Asset/Anime/Character/Zombie/Chapter1/Normal/
#        Sprite/GatlingPea/ZombieNormalGatlingPea.tscn` 与 `…/Chapter2/Zamboni/
#        Sprite/GatlingPea/ZombieZamboniGatlingPea.tscn` 两份内置样本同构）：
#   在僵尸精灵场景里挂一个 `AdobeAnimateSprite` 子节点 `Head`，它的
#   `flashAnimeData` 指向**超级机枪射手**的动画数据，靠 `parentSprite` +
#   `followParentSpriteLayerId` 插进僵尸身体的图层流。
#
# ⚠️ 2026-09-22 修正三处（用户指着截图说「头不协调 / 用错了贴图 / 判定没加」）：
#
#  (a) **素材**：此前 `flashAnimeData` 指 `res://…/Plant/Cover/GatlingPea/
#      GatlingPea.tres` —— 那是**机枪射手**（GatlingPea），不是**超级机枪射手**
#      （SuperGatlingPea）。内置 `Asset/Anime/` 树里**根本没有**「超级机枪射手」
#      这个角色（只有 GatlingPea / GatlingPeaZ / GatlingCat / GatlingPot /
#      CatGatlingPea / GatlingCabbage / DisguiserGatling / Item/GatlingTX 与 4 个
#      僵尸换头变体），唯一来源是本工坊植物包自制的 `SuperGatlingPea.{tres,dat}`
#      （经典未重置版 `SuperGatling.reanim.compiled` 27 轨 × 87 帧官方素材直转）。
#      ⚠️ `.pmod` 之间**不能互相引用** ⇒ 三件套（`.tres` / `.dat` / 图集 PNG）
#      必须**复制进本包** `Resources/Animations/`（`copy_skin_assets()`），
#      Sprite 场景用**相对路径**引用（`head_data_rel()`；本包 =
#      `../../../../../Resources/Animations/SuperGatlingPea.tres`，与植物包
#      `SuperGatlingPea.tscn` 的 `ExtResource("2_data")` 同深）。
#
#  (b) **对位**：只有 `offset`（+ `offsetRotate`）能调位置 —— 见下面的「对位模型」。
#      现行值由 `.cache/check_head_fit.py` 离线反解得到，**不是抄来的**。
#
#  (c) **场景属性名**：此前写的是 `clip` / `layerVisible = [...]` /
#      `mediaReplaceAtlasPaths` / `mediaReplaceUse` / `name_ignore`。其中
#      `clip`、`mediaReplaceAtlasPaths`、`mediaReplaceUse`、`name_ignore`
#      **在 `AdobeAnimateSprite` / `AdobeAnimateSpriteBase` 上根本不存在**
#      （`:3019` 的 `_Set` 只认 `Animation/Clip`、`Animation/LayerVisible/<图层名>`、
#      `Animation/MediaReplace/<媒体名>`、`Layer`、`Parent Sprite/Insert Layer`；
#      `_mediaReplaceUse` 等是 **private 字段**；`name_ignore` 全游戏树 0 命中）。
#      ⚠️ Godot 4.7 载入 `.tscn` 时对不存在的属性是**静默丢弃**（写进游戏日志的
#      实测：整份 `godot.log` 里 `Invalid` 命中 **0** 次）⇒ 这几行**从来没生效过**，
#      后果是 `Head` 的 `_clip` 一直是空串，被 `ApplyFlashAnimeDataChange()`
#      （`:10222-10230`）兜成 `clips.Keys[0]` = **`BodyIdle`**（茎叶段！）。
#      现在全部改成官方的 `Animation/*` 写法（键名 = `.tres` 字典键，ASCII 序）。
#
# ★★ 对位模型（引擎真实语义；读源码 + 官方样本交叉校验确认）
#   `AdobeAnimateSprite.UpdateChild()`（`addons/AdobeAnimateEditor/Node/
#   AdobeAnimateSprite.cs:5259-5281`）**每帧覆盖**被跟随图层的子精灵：
#       child.Position = <被跟随图层 L 的 pose>.Origin + <父精灵的 offset>
#       child.Rotation = <被跟随图层 L 的 pose>.Rotation + child.offsetRotate
#   ⇒ 场景里写的 `position` / `rotation` 是**死值**，一个像素都不生效；
#     能自由调的只有 `offset` 与 `offsetRotate`。
#   子精灵画自己美术时 `transform = transform.Translated(offset)`（`:7044 / :7071 /
#   :7362`；Godot 4 的 `Translated(Vector2)` 是**纯原点平移**，不按基向量旋转）
#   ⇒ 整个偏移落在节点自身的旋转 × scale 之下：
#       P = A · (pose_art + offset) + node
#       A    = [[cosθ·sx, −sinθ·sy], [sinθ·sx, cosθ·sy]]
#       θ    = 被跟随图层 rot + offsetRotate
#       node = L.origin + 父精灵 offset
#   于是「让新头的头块压住原头」的解析解是
#       offset = A⁻¹ · (origin_head_center − (A·mass_center + node))
#   标定脚本 = `.cache/check_head_fit.py`：离线读两份 `.tres` 的切片数据反解，
#   并用官方 `ZombieNormalGatlingPea` 的已知 `offset = (-58, -5)` 做交叉校验
#   （残差 3.96px ⇒ 模型与锚点正确）。**改 `HEAD_OFFSET` 必须重跑它。**
#
# 关键索引（读报僵尸 `ZombiePaper.tres` 的 layerDictionary，值 = 图层 id）：
#   _ground 0 / Zombie_paper_body 12 / anim_hair 15 / anim_head1 16 /
#   anim_head_look 17 / anim_head_pupils 18 / anim_hairpiece 19 /
#   anim_head_jaw 20 / anim_head_glasses 21 / Zombie_paper_paper 22 /
#   Zombie_paper_hands 23 / AnimeClips 24
# 官方 Zamboni 取 `Zombie_head = 11` 当 follow/insert 层；读报僵尸对应的「头」层
# 就是 `anim_head1 = 16` ⇒ 取 16。
# ⚠️ 官方样本 `ZombieNormalGatlingPea` 里「`Animation/LayerVisible/anim_head1 = false`
# （把原头藏了）」与「`Head.followParentSpriteLayerId = 7`（= 同一个 `anim_head1` 层）」
# **并存** —— 因为跟随姿态读的是 `TryGetInterpolatedPose()` 的**托管姿态轨**
# （`:7266-7281`，与 `_layerVisible` 无关）⇒ 藏掉被跟随层**不会**让头跟着消失。
# 本包同款：藏 7 层原头 + 跟 L16。
#
# ⚠️ 可见性表的长度陷阱：`ApplyFlashAnimeDataChange()`（`:10190-10205` /
# `:10267-10275`）在 `_layerVisible.Count != 图层数` 时会把整表**重置为全 true**；
# 而 `flashAnimeData` 的 setter（`:1092-1095`）会**先**调
# `PrepareFlashAnimeDataSerializedOverrides()` 把表 resize 成「全 true」，
# 场景里后写的 `Animation/LayerVisible/*` 才生效
# ⇒ **`flashAnimeData` 必须排在所有 `Animation/LayerVisible/*` 之前**（内置/植物同款）。
ADOBE_SPRITE_BASE_SCRIPT = "res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs"

# ★★★ 换头必须是「三节点」结构（2026-09-22 定稿）—— 单节点（头 = 身体的直接子精灵）
#     会把头画成「一团随机图集碎片」。
#
# 事故现象：头所在的那块区域糊着别的角色的碎片
#           （冰系蓝白菱形 / 黄橙块 / 紫块 / 青蓝小方块 / 白豌豆…）。
# 根因链条（全部源码实锤）：
#   1. `CollectOwnedChildBindings`（`AdobeAnimateSprite.cs:5365`，判定 `:5385`）
#      **只按 Godot 节点类型**收集子精灵，**完全不看 `parentSprite`**；
#      对「非精灵但有子节点」的中间节点会递归（`:5397`），但那里把
#      `collectSpriteChildren` 传成 `ownerSlot != null` ⇒ **普通容器下面不再收精灵**。
#   2. ⇒ 只要头是身体的（直接）子精灵，就进身体的 `_spriteChildren`/`_insertedSprites`
#      ⇒ `OwnsSpriteChildForRender`（`:7774`）true
#      ⇒ `IsRenderedByParentSpriteForRender`（`:9559`）true
#      ⇒ `_Draw()`（`:9532`）**第一行就 return**
#      ⇒ 头自己的 `forceLocalRender`（public 属性 `:1141`，`_Draw` 用的是 `:9549`/`:9551`）
#        **永远走不到** —— 这就是「插件明明打了 forceLocalRender、画面还是乱的」的原因。
#   3. ⇒ 头的切片由**身体的渲染批次代画**（`AppendChildSprites` `:833` → 头自己的
#      definition 出 rect，但整批共用**身体那一张纹理数组**）
#      ⇒ 自制皮肤不在全局图集清单里（`RefreshAtlas:3489` 是**构建期**才写
#        `res://…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres`，运行期无补救 API）
#      ⇒ `MediaAtlasPages` 解析不到 ⇒ 落 `BaseAtlasPage = 0`（`DrawItemBuilder:921`）
#      ⇒ 采样 `AdobeAnimateVisualTextureArray.png`（**把全部角色拼在一张的大图**）
#      ⇒ **各种角色碎片拼贴**，与实机截图逐像素吻合。
#   · 植物包为什么没这病：它的 root 与 Head **共用同一份 `.tres`** ⇒ 同 definition
#     ⇒ 同 `MediaAtlasPages` ⇒ 身体代画也是对的。
#   · ⚠️ `insertLayerId = -1` **不等于**「不插入」：`ResolveSpriteChildInsertLayer`
#     （`:8039`）会回落到顶层 ⇒ 照样被代画。
#
# 修法（在引擎语义下唯一可行）：**让可见头脱离身体的子树**，但姿势仍要跟身体。
#   ① `HeadShadow` = 身体的子精灵，**不可见**、29 层全 `false`：
#      只为吃 `UpdateChild()`（`:5208-5286`）每帧写的
#      `Position = 被跟随层 pose.Origin + 父精灵 offset`、
#      `Rotation = pose.Rotation + offsetRotate`。
#      ⚠️ 该循环**没有可见性判断**（定位在 `:5259-5281`）⇒ `visible = false` 不影响被定位。
#      层全 false 还顺带保证它**不产生任何切片** ⇒ 不会污染身体的批次。
#   ② `HeadHolder` = 普通 `Node2D`（identity）—— 打断「父代画」的容器：
#      身体扫到它时 `collectSpriteChildren` 已是 `false` ⇒ 里面的精灵不被收集
#      ⇒ `Head` 的 `_parentSprite` 只看得到身体，但 `OwnsSpriteChildForRender` 为 false
#      ⇒ `_Draw()` 正常执行 ⇒ 独立渲染 ⇒ 用**皮肤自己那张纹理数组**（page 0 = 皮肤图集）✓
#   ③ `Head` = 可见头（`HeadHolder` 的子节点）= 真正给人看的那个。
#      因为 ② 断了「父代画」，它必须**由插件每帧**从 ① 抄 `Position`/`Rotation`
#      （`runtime_src_zombie_super_gatling/SuperGatlingPaperRuntimeEntry.cs`）。
#      两者 `scale`/`offset`/`offsetRotate` 必须逐字相同 ⇒ 渲染结果与 ① 若可见时一模一样。
#
# ── 2026-09-23 第二轮修（用户：「使头部摆正、不再歪斜 … 相对位置保持一致 … 层级调高」）
#
#   ⚠️⚠️ 2026-09-23 第三轮：**本段的「冻结」已按用户要求关闭**（`HEAD_FIX_HEAD_ROTATE = False`
#      ⇒ 头恢复跟 `anim_head1` 逐帧摆头）。**机制与证据原样保留**，因为：
#      ① 开关还在，用户可能再要求打开；② 下面是「官方 offsetRotate = -0.25 是弧度」
#      这类结论的唯一记录处；③ 关掉不等于结论作废 —— 只是本版不采用。
#      第三轮的诉求与落点见下方「(D) 本轮」段。
#
#   (A) 为什么头以前是**歪的**（实锤，不是猜）：头节点的 net 旋转被引擎每帧写成
#       `Rotation = <anim_head1 图层 pose>.Rotation + offsetRotate`（`:5258-5276`）。
#       而 `ZombiePaper.tres` 的 `anim_head1`（L16 = `Zombie_head.png`）本身带大幅摆头：
#       Idle −16.03°..+1.01°、Walk −19.52°..+23.15°、Eat −27.63°..+29.70°（逐帧连续插值，
#       f0 = −8.06°）。换跟随层解决不了 —— 官方 `ZombieNormalGatlingPea` 跟的也是
#       `anim_head1`（在 `ZombieNormal.tres` 里是 L7），官方那套效果靠
#       `offsetRotate = -0.25`（弧度）凑出来，摆动本身被当成「自然摆头」接受。
#       用户的诉求是「不再歪斜」⇒ 只能**把 Rotation 冻成常量**。
#       量化依据见 `.cache/head_pose_probe.py`（逐图层逐 clip 的旋转/位移范围）。
#
#   (B) ★★★ 冻在**哪个角**：0°（= 这套头美术的原生朝向），不是官方那个 −14.32°
#
#       为什么是 0°（三条独立证据，2026-09-23 修正 —— 上一版取 −0.25 rad 是照抄官方，错的）：
#       ① 【最强】同一套头美术在**植物**里的原生净旋转就是 0：
#          植物 Sprite 场景 `SuperGatlingPea.tscn` 的 `Head` 节点**没有任何旋转覆写**
#          （无 `rotation` / `useRotate` / `offsetRotate` ⇒ 默认 `useRotate = true`、
#           `offsetRotate = 0`）⇒ 它的旋转 = 跟随层 L16(`anim_idle`) 的姿态旋转 + 0。
#          而实测该层 **BodyIdle 全 24 帧旋转恒为 +0.000°**（见 `.cache/head_place.py` 同法探测）
#          ⇒ 植物头就是以 **net 0°** 渲染的，且用户已接受植物外观
#          ⇒ 「这套美术在 0° 时是正的」是既成事实，不是我们的选择。
#       ② 离线渲染细扫（`.cache/_ab_angle.json` → `_ab_angle.png`）：θ 越大越负，
#          炮口越是下垂；θ = 0 时炮口水平，θ = −14.32° 时明显下垂 ——
#          而用户投诉的正是「下垂/歪斜」，交付 −14.32° 等于没修。
#       ③ 与植物卡面原生美术并排（`.cache/_native_compare.py` → `_native_vs_angles_big.png`）：
#          θ = 0 的头盔/护目镜/炮口朝向与卡面一致，θ = −14.32 明显顺时针倒。
#       ⚠️ 上一版为什么错：拿官方的 `offsetRotate = −0.25` 当"对齐目标"，但那是**另一套美术**
#          （内置机枪豌豆僵尸），它那支枪本来就是设计成略微下垂的。锚错了参照物。
#
#       冻结的机制（**纯数据**，不需要动插件）—— 引擎自带开关：
#       `AdobeAnimateSprite.cs:275-282` 有 `[Export] public bool usePos = true;` /
#       `useRotate = true;`；`:5259-5276` 里 `Rotation` 的赋值**包在 `if (useRotate)` 内**、
#       `Position` 的赋值包在 `if (usePos)` 内。
#       ⇒ 场景写 `useRotate = false` + 显式 `rotation = 0.0`：
#         引擎**不再改** `Rotation`（节点自写值生效）⇒ 头不再跟着 `anim_head1` 摆头
#         （该层 Idle −16.03°..+1.01°、Walk −19.52°..+23.15°、Eat −27.63°..+29.70°，逐帧插值）
#         ——「摆正、不再歪斜」；
#         而 `Position` 仍每帧跟随 ⇒「与身体的相对位置保持一致」。
#       官方先例（14 处）：`.../ZombieGargantuar.tscn:141`、
#         `.../ZombieFootballGargantuar.tscn:109`、`.../ZombieSkeletuar.tscn:105`、
#         `.../ZombieGargantuarDigger.tscn:152`、`.../TowerDefensePlantPeaPot.tscn:53` …
#       运行期先例：`TowerDefenseZombieNormalSquash.cs:62-63`
#         （`_zombieSprite.head.usePos = false; _zombieSprite.head.useRotate = false;`）。
#       ⚠️ 单位：`rotation` / `offsetRotate` 都是**弧度**（0.0 两种写法同值，但概念要清楚；
#          正是「度/弧度」搞混让 `.cache/check_head_fit.py` 的交叉校验残差被算成 3.96px，
#          真值 4.61px —— 错得不明显，所以一直没红）。
#       ⚠️ `useRotate = false` 时引擎**不读** `offsetRotate` ⇒ 必须保持 0（下方有自检拦）。
#       ⚠️ 影子与可见头都要写：插件每帧 `pair.Visible.Rotation = pair.Shadow.Rotation`
#          （`SuperGatlingPaperRuntimeEntry.cs:887-892`）⇒ 影子冻住，可见头自动跟着冻；
#          两边都写则再叠一层保险（DLL 缺失时可见头自己也是正的）。
#
#   (C) 层级（用户：「渲染层级调高 … 避免被遮挡或出现穿插」）：
#       引擎的**全局**绘制排序键（`AdobeAnimateSortPath.CompareTo`，`AdobeAnimateSortPath.cs:37-48`），
#       第一位就是 `ZIndex`（= `EffectiveZIndex`），之后才轮到 `TreeOrderPath` / `LayerOrder` …；
#       所有 draw item 统一走 `AdobeAnimateDrawItemComparer` 排序
#       （`AdobeAnimateRenderManager.cs:753`）。而 `EffectiveZIndex` 的算法
#       （`AdobeAnimateSprite.cs:6513-6531`）就是**沿父链累加 Godot 的 `z_index`**。
#       ⇒ 给可见头写 `z_index = 1`（`z_as_relative` 默认 true ⇒ 在父级基础上再 +1），
#         它的 effective z 比身体高 1 ⇒ **必然排在身体之后绘制**。
#       为什么不只靠节点顺序：`HeadHolder` 排在 `GroundSlot` 之后确实已在身体之后，
#         但那只用到排序键的**第二位**，且依赖内置 `ZombiePaper.tscn` 的子节点次序；
#         写 `z_index` 把它变成对树序**不敏感**的显式保证（幂等、无副作用、可一键回滚）。
#
# ── 2026-09-23 第三轮修（用户：「回退到上一版本的僵尸头部动画，然后在此基础上
#    ……将头部的初始位置从偏左向右上方向微微移动，使整体构图更加协调」）
#
#   (D-1) 「回退到上一版本的头部动画」= 把头**重新交给引擎逐帧覆写** `Rotation`
#         ⇒ 撤掉 `useRotate = false` / `usePos = true` / `rotation` 三行
#         （`HEAD_FIX_HEAD_ROTATE = False`；`sprite_scene_tscn()` 里 `rot_lines = ""`，
#          自检改成断言「两处都不许出现 useRotate / usePos / rotation」——
#          留一行 `rotation` 而没有 `useRotate = false` 是**死值**，只会误导下次改的人）。
#         ⇒ 头恢复跟 `anim_head1`（L16）摆动：Idle 内 net −16.03°..+1.01°（逐帧插值）。
#         ⚠️ 插件**不需要改**：`SyncHeadPairs()` 本来就是「每帧把影子的
#            `Position`/`Rotation` 抄给可见头」，与旋转是否被冻结无关。
#
#   (D-2) 「头部初始位置往右上微微移动」= 在**锚点**上给一个屏幕空间位移
#         （`HEAD_PLACE_SHIFT`，px，y 向下 ⇒ 右上 = +x / −y）。
#         ★ 为什么加在**锚点**而不是直接加在 `offset` 上（这条是踩过的方向坑）：
#           `offset` 住在头的**局部空间**，画之前还要过
#               A = rot_scale(θ, sx=−1, sy=1) = [[−cosθ, −sinθ], [−sinθ, cosθ]]
#               （横翻 sx=−1 把第一列反号 ⇒ 局部 +x 在屏幕上是 **−x**）
#           实测（θ = 跟随层 −8.06°）：把 Δ=(+6,−3) 直接加到 `offset` 上，
#           屏幕实际位移是 **(−6.36, −2.13)** —— 横向**正负完全反了**（想往右跑结果往左），
#           纵向也被 A 的交叉项缩水；Δ=(+8,−4) ⇒ (−8.48, −2.84) 同理。
#           加在锚点上则恒有 `screen_delta == HEAD_PLACE_SHIFT`（逐字相等，可断言）。
#
#   (D-3) 幅度怎么定的（.cache/_shift_probe.py 的实测表）：
#         身体（去掉 7 层原头）并集包围盒 = x −49.40..47.72（宽 97.1），
#         而回退后整头块 = x −63.17..28.02 ⇒ **比身体左轮廓还多伸出 13.77px**
#         —— 这就是用户说的「偏左」（机枪炮管朝左伸出，视觉重心被拽到左边）。
#         候选表（整头块左/右边界 · 相对身体中心的 dx）：
#           shift (0,0)   ⇒ x −63.2..28.0  dx −16.73   ← 纯几何对齐（回退后的基准）
#           shift (+4,−2) ⇒ x −59.2..32.0  dx −12.73
#           shift (+8,−4) ⇒ x −55.2..36.0  dx  −8.73   ← ★ 本版取它
#           shift (+12,−6)⇒ x −51.2..40.0  dx  −4.73   （已与身体左轮廓齐平，偏大）
#         取 (+8,−4)：约为身体宽度的 8%，属「微微」；左侧伸出量 13.8 → 5.8px，
#         方向明确是右上，且**没有**把炮管压到身体上（`check_head_fit.py` 会让它过）。
#         ⚠️ 这一定是**主观**量 —— 交付时把候选图一并给出，用户一句话即可调参。
#
#   (D-4) 「回退」对**层级**（(C) 的 `z_index = 1`）**无影响**：用户只要求回退动画，
#         层级那条需求（避免被遮挡/穿插）仍然成立，保持不动。
HEAD_NODE_NAME = "Head"                  # ③ 可见头（自绘、独立渲染、能播 HeadFire）
HEAD_SHADOW_NODE_NAME = "HeadShadow"     # ① 位姿影子（被身体代画，但全层 false ⇒ 零切片）
HEAD_HOLDER_NODE_NAME = "HeadHolder"     # ② 普通容器（identity ⇒ 与身体同一坐标系）
HEAD_INSERT_LAYER_ID = 16
HEAD_FOLLOW_LAYER_ID = 16
HEAD_CLIP = "HeadIdle"
HEAD_TRUE_FRAME_RATE = 180.0
# 横向翻转：读报僵尸朝左、超级机枪射手素材朝右（官方 Zamboni 的 Head 同样 -1,1）
HEAD_SCALE = (-1.0, 1.0)
# ★ 由 `.cache/head_place.py` 反解、`.cache/check_head_fit.py` 对账（官方样本交叉校验 4.61px）：
#   把「头块 = SuperGatlingPea 的 GatlingPea_helmet 层」的并集包围盒中心对到
#   「原头 = ZombiePaper 的 anim_head1 层」的并集包围盒中心 **+ HEAD_PLACE_SHIFT**。
#   ⚠️ 用「头块」而不是「整块」：机枪炮管向侧面伸出，拿整块对齐会有 ~40px 假残差。
#   ⚠️ offset 与旋转**耦合**（offset 作用在节点旋转**之前**的头局部空间）⇒
#      改旋转角**或**改 `HEAD_PLACE_SHIFT` 都必须重解：
#         python .cache/head_place.py                       # 跟随时（本版口径）基准
#         python .cache/head_place.py --shift=8,-4          # 再加「右上微移」
#         python .cache/head_place.py --node-rot-degs=0     # 若开关重新打开（冻结口径）
#   历代值（都被负向用例钉死在 `.cache/check_head_fit.py` 里）：
#     (-36,-46)             照抄**植物体内 Head** 的 offset，偏差 41.75px = 截图上的悬空
#     (-51.46,-7.21)        跟随时（net = 身体层 −8.06°）的**纯几何对齐**解
#     (-49.07,-5.24)        冻在 −14.32° 的解（锚错参照物，炮口明显下垂）
#     (-54.19,-10.11)       冻在 0°（美术原生）的解 —— 第二轮交付
#     (-59.9377,-10.0515)   ★ 本版：跟随摆动 + 锚点右移 8px / 上移 4px 的解
HEAD_OFFSET = (-59.9377, -10.0515)
# ★ 头部「有意位移」：屏幕/身体空间 (dx, dy) px，y 向下 ⇒ **右上 = (+x, −y)**。
#   语义是「在纯几何对齐的基础上，故意把锚点挪这么多」—— 纯审美，不是几何必需。
#   ⚠️ 它是**屏幕空间**量（直接就是画面上的位移）；`HEAD_OFFSET` 才是头局部空间的量。
#      把同一个数直接加在 `offset` 上会得到**左右相反**的结果（见上方 (D-2) 的实测）。
#   ⚠️ 改它必须重解 `HEAD_OFFSET`（上面的命令）并同步 `HEAD_PLACE_SHIFT_GOLDEN`。
HEAD_PLACE_SHIFT = (8.0, -4.0)
# ★ 头部姿态开关：True = 写 `useRotate = false` + 固定 `rotation`（摆正、不再歪斜）；
#   **False = 交还给引擎逐帧覆写** ⇒ 头跟 `anim_head1` 摆动（= 上一版的行为）。
#   ⚠️ 2026-09-23 第三轮用户要求「回退头部动画」⇒ 置 False。开关本体**保留**
#      （机制与证据见上方 (B) 段，(B) 段不改是因为它记录的结论与本次开关无关）。
HEAD_FIX_HEAD_ROTATE = False
# 固定 net 旋转。**弧度是主值**（写进场景的就是它）：0.0 rad = 0°
# ⚠️ 别写成 `math.radians(角度字面量)` —— 非零值会带上浮点脏尾；
#    0.0 本身干净，但仍保持「弧度为主值」的写法一致性。
# ⚠️ 开关为 False 时这两个常量**不写进场景**（引擎每帧覆写 ⇒ 写了是死值）。
#    保留现值 + 金标，是为了重新打开开关时能被「上一个通过核对的值」拦住。
HEAD_FIXED_ROT_RAD = 0.0
# 同一角度的度数形式（= degrees(HEAD_FIXED_ROT_RAD)），只用于阅读 / 文档 / 对账
HEAD_FIXED_ROT_DEG = 0.0
# ⚠️ useRotate=false 时引擎不读它（自检会拦非零值），保留 0 以免误读
HEAD_OFFSET_ROTATE = 0.0
# ★ 可见头的 z_index：引擎全局排序键第一位是 EffectiveZIndex ⇒ 正数即压在身体之上
HEAD_NODE_Z_INDEX = 1

# ── ★★ 金标锚点（golden anchors）—— 只为「常量被静默改动」这件事兜底 ────────────
# 为什么需要它（2026-09-23 负向测试抓出来的真空洞）：
#   原先的自检写的是
#       if f"offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})" not in sp: fail
#   —— 拿**常量**去比**由同一常量渲染出的文本**，只要模板插了值就恒成立。
#   把 HEAD_OFFSET 改成任何错值（实测 (-36,-46)），自检照样全绿。
#   这是「断言与实现同错 = 假绿」的又一例。
# 做法：把**独立记录**的字面量钉在这里，自检拿「活常量」比「金标」；
#   两处不同 ⇒ 报错。金标不是几何真值，只是上一次**反解并核对通过**的快照。
# ⚠️ 几何真值由 `.cache/check_head_fit.py` 负责（它真的重解几何，已含正向 + 负向用例）；
#    本金标**不替代**它，只保证「没人偷偷改常量而不跑回归门」。
# 改 `HEAD_OFFSET` / 旋转角 / `HEAD_PLACE_SHIFT` 的正确流程（都要改，且必须重解 offset）：
#   python .cache/head_place.py [--shift=<dx,dy>] [--node-rot-degs=<角度>]   # 取反解 offset
#   python .cache/check_head_fit.py                                          # 几何门全绿
#   然后把新值同时写进 HEAD_* 与下面的 *_GOLDEN。
HEAD_OFFSET_GOLDEN = (-59.9377, -10.0515)
HEAD_PLACE_SHIFT_GOLDEN = (8.0, -4.0)
HEAD_FIXED_ROT_RAD_GOLDEN = 0.0
HEAD_NODE_Z_INDEX_GOLDEN = 1

# ── ★★★ 炮口 / 子弹生成点（2026-09-24 第四轮）─────────────────────────────────
# 用户原话：「让子弹生成位置靠左一点，对齐子弹发射口。」
#
# 【真因】`FireComponentDefinition.firePosMarkerPaths` 指向的那个 `Marker2D` 就是**子弹生成点**。
#   `FireComponent.CreateProjectile()`（`:2698-2714`）在 `posId`
#   （= `fireProjectileList[i].firePosId`；`int` 默认 0，本包 .tres 没写）落在
#   `_firePosMarkers` 范围内时取
#       logicalGlobalPosition = parent.GetLogicalGlobalPosition(marker2D)  // = marker2D.GlobalPosition
#   ⇒ 生成点 = **Marker2D 的世界位置**（既不是僵尸原点，也不是炮口）。
#   ⚠️ `_firePosMarkers` 由 `CopyGodotArray(firePosMarker, _firePosMarkers)`（`:946`）从
#      `ResolveReferences()`（`:1229-1233`）填好的 `firePosMarker` 抄来 ⇒ 链路成立。
#
#   本包此前把 `FireMarker` 放在 `HeadSlot` 原点（`position = (0, 0)`），
#   理由写的是「挂在 HeadSlot 下面就会跟着头部动画」——**那个理由是错的**：
#   `HeadSlot` 是原版给「护具 / DamagePoint」用的**静态插槽**
#   （`TowerDefenseZombiePaper.tscn` 原值，`drawLayerId = -2`），它的 position 不跟随头部美术；
#   护具之所以看起来贴在头上，是因为**护具美术自己的 offset 补掉了这段差**。
#   ⇒ 实测（`.cache/_muzzle_probe.py`）：生成点比真炮口**偏右 6.54px、偏上 80.77px**。
#     垂直那 80.77px 才是主要问题：豌豆从**头顶上方**出膛。
#
# 【炮口点怎么来的（不是猜的，也不是手抄）】
#   植物侧 `build_plant_super_gatling.py` 早就标定过炮口：
#       ANCHOR_ROOT   = (40.0, 40.0)     # 经典 reanim 的种植锚点
#       ANCHOR_MUZZLE = (88.552, 30.2)   # barrel 轨完全伸出帧（f62）的**不透明炮口点**
#       Marker2D(local) = ANCHOR_MUZZLE - ANCHOR_ROOT = (48.552, -9.8)
#   实测植物生成场景 `SuperGatlingPea.tscn` 的 `.../Head/Marker2D` 正是 `(48.552, -9.8)`，
#   而该场景 `Head.offset = (-40, -40)` ⇒ 反推 **炮口在头 `.tres` pose 空间 = (88.552, 30.2)**。
#   本包僵尸头用的是**同一份** `SuperGatlingPea.tres` ⇒ pose 空间逐字相同，直接可用。
#   独立复核：`.cache/_muzzle_probe.py` 从 barrel 轨的**不透明区最右列中点**重算一次，
#   得 (88.5520, 30.2000) —— 与上面的历史值**差 0.0000 px**。
MUZZLE_POSE = (88.552, 30.2)
# ★ 插件要用的量：炮口在**头节点局部**空间 = `muzzle_pose + offset`。
#   ⇒ 运行期 `head.GlobalTransform * HEAD_MUZZLE_LOCAL` 即炮口世界坐标
#   （节点局部点 = `pose + offset`，因为引擎画切片时是 `transform.Translated(offset)`）。
#   ⚠️ 它随 `HEAD_OFFSET` 走，**插件里的字面量必须同步**（闸门会逐个比对）。
HEAD_MUZZLE_LOCAL = (MUZZLE_POSE[0] + HEAD_OFFSET[0], MUZZLE_POSE[1] + HEAD_OFFSET[1])

# `HeadSlot` 的变换 = **原版读报僵尸**给的值，勿改（它同时是护具 / DamagePoint 插槽）。
#   来源：`Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.tscn`
#   ⚠️ `rotation` 是**弧度**（Godot 惯例：0.27867758 rad ≈ 15.967°）。
HEAD_SLOT_POS = (-14.015516, -40.408867)
HEAD_SLOT_ROT_RAD = -0.27867758
HEAD_SLOT_SCALE = 0.79857695

# ★ `FireMarker.position`（**HeadSlot 局部**）—— 让生成点落在炮口上。
#   反解：`Q = HeadSlot.pos + R(θ)·(s·p)` ⇒ `p = (1/s)·R(-θ)·(Q - HeadSlot.pos)`，
#   其中 `Q` = 炮口在**身体精灵局部**的位置 = `muzzle_space - BODY_OFFSET(-40,-80)`；
#   `muzzle_space = A·(muzzle_pose + HEAD_OFFSET) + node`，参考帧 `bf = 0`
#   （与 `HEAD_OFFSET` 同口径）。工具：`.cache/_fire_marker_solve.py`（带回代核对）。
#   ⚠️ 改 `HEAD_OFFSET` / `HEAD_PLACE_SHIFT` / 参考帧 都必须重跑它。
#   ⚠️ 这是**静态兜底**值（插件没跑起来时生成点也落在炮口）；
#      插件跑起来后由 `SyncHeadPairs()` 每帧覆盖为**当帧真炮口**。
#      为什么非要动态：头现在是跟 `anim_head1` 摆的（`HEAD_FIX_HEAD_ROTATE = False`），
#      炮口随动画跑 —— Walk 段 x 跨 23.7px / y 跨 54.0px，Eat 段 x 跨 42.8px / y 跨 78.2px
#      （`.cache/_muzzle_scan.py`）⇒ 静态值最坏离线 ~44px。
FIRE_MARKER_POS = (-35.697232, 94.988609)

# 金标：炮口 / 生成点这两个新常量同样不许被静默改动。
MUZZLE_POSE_GOLDEN = (88.552, 30.2)
FIRE_MARKER_POS_GOLDEN = (-35.697232, 94.988609)
HEAD_SLOT_POS_GOLDEN = (-14.015516, -40.408867)

# 皮肤三件套的真源（植物包产物）与包内镜像位置。
# ⚠️ 生成器**不**在这里硬编码图层/媒体名表 —— 见 `head_layer_names()`。
SKIN_SRC_DIR = os.path.join(WS, "SuperGatlingPea", "Resources", "Animations")
SKIN_TRES_FILE = "SuperGatlingPea.tres"
SKIN_DAT_FILE = "SuperGatlingPea.dat"
SKIN_ATLAS_FILE = "SuperGatlingPeaAtlas.png"
ANIM_SKIN_REL = "Resources/Animations"        # STANDARD_DIRS 里已有这个目录


def skin_tres_src():
    """植物包里那份皮肤 `.tres` 的绝对路径（唯一真源）。"""
    return os.path.join(SKIN_SRC_DIR, SKIN_TRES_FILE)


def _pkg_root_prefix(rel_dir):
    """包内某目录 → 包根的 `../` 串（`Resources/Animations` 这类引用要用）。"""
    return "../" * len(rel_dir.split("/"))


def head_data_rel():
    """Sprite 场景里引用包内皮肤 `.tres` 的相对路径。

    包内自引用**禁 `res://`**（`.pmod` 之间不能互相引用）⇒ 只能相对。
    Sprite 场景在 `Resources/Characters/Zombies/<Key>/Sprite/`（5 段）
    ⇒ 回包根要 5 个 `../`，与植物包 `SuperGatlingPea.tscn` 的写法同深。
    """
    return _pkg_root_prefix(f"{PKG_REL}/Sprite") + f"{ANIM_SKIN_REL}/{SKIN_TRES_FILE}"


def skin_anim_dir():
    """包内 `Resources/Animations/` 的绝对路径。"""
    return _abs(ANIM_SKIN_REL)


def _skin_tres_text():
    with io.open(skin_tres_src(), "r", encoding="utf-8") as f:
        return f.read()


def _tres_dict_keys(text, name, where):
    """读 `.tres` 里 `name = { … }` 字典的**键序**（Godot 保存时按 ASCII 序）。

    用它取代两张硬编码的图层/媒体名表 ⇒ 皮肤换素材、增删图层时场景文件
    **自动跟随**，再也不会出现「表比数据短 ⇒ 引擎把可见性整表重置为全 true」
    这类静默事故（`.tres` 改了但表没改 = 最难查的一类 bug）。
    """
    m = re.search(r"\n" + name + r" = \{\n(.*?)\n\}", text, re.S)
    if not m:
        raise RuntimeError(f"{where} 里找不到 `{name} = {{…}}` 字典")
    keys = re.findall(r'^"([^"]+)":', m.group(1), re.M)
    if not keys:
        raise RuntimeError(f"{where} 的 {name} 字典里没有键")
    return keys


def head_layer_names():
    """皮肤 `.tres` 的图层名（顺序 = layerDictionary 的值序 = 场景 LayerVisible 的索引序）。"""
    return _tres_dict_keys(_skin_tres_text(), "layerDictionary", SKIN_TRES_FILE)


def head_media_names():
    """皮肤 `.tres` 的媒体名（`Animation/MediaReplace/<名>` 要用）。"""
    return _tres_dict_keys(_skin_tres_text(), "mediaDictionary", SKIN_TRES_FILE)


def head_clip_names():
    """皮肤 `.tres` 的 clip 名（用来断言 `HeadIdle` 真的存在）。"""
    return _tres_dict_keys(_skin_tres_text(), "clips", SKIN_TRES_FILE)


# 原版僵尸的头 = 7 个图层（头发 / 头 / 朝向 / 瞳孔 / 发饰 / 下巴 / 眼镜）。
# 内置 `ZombiePaper.tscn` 把这 7 层**显式写 true**（不是留空继承默认值），
# 所以本包必须**显式覆写 false** —— 否则原头会从头盔底下透出来。
# 报纸(22) / 手(23) 不动。
BODY_HIDDEN_HEAD_LAYERS = ("anim_hair", "anim_head1", "anim_head_look", "anim_head_pupils",
                           "anim_hairpiece", "anim_head_jaw", "anim_head_glasses")

# 护具体系
ARMOR_REGISTRY_CONFIG_DIR = "res://Registry/Armor/Config"
ARMOR_SLOT_SCRIPT = "res://Resource/General/Character/Armor/ArmorSlotConfig.cs"
ARMOR_DATA_SCRIPT = "res://Resource/General/Character/Armor/CharacterArmorData.cs"

# 发射组件
BASE_FIRE_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentStateMachine.tres"
BASE_FIRE_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentDefinition.cs"
BASE_RAY_SCRIPT = "res://Resource/TowerDefense/Collision/AabbRay2DResource.cs"
BASE_CREATEDATA_SCRIPT = "res://Registry/Projectile/Resource/TowerDefenseProjectileCreateData.cs"
BASE_PROJ_SINGLE_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/Projectile/FireComponentProjectileSingle.cs"
BASE_CHECK_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentCheckConfig.cs"
BASE_FIRE_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs"

# 数值（2026-09-19 用户指定）
#
# 血量：游戏的有效总血 = hitpoints + hitpointsNearDeath
#   ⇒ 「本体 1250」= 总血恰好 1250：1180 主血 + 70 濒死线（70 沿用内置读报僵尸）。
HP_TOTAL = 1250.0
HP_NEAR_DEATH = 70.0
HITPOINTS = HP_TOTAL - HP_NEAR_DEATH        # 1180.0
ATTACK = 800.0                              # 伤害 800（useAttackDps ⇒ 每秒）
ATTACK_TYPE = "Eat"                         # 啃食（父组件集默认值，本包不覆盖）
COST = 100                                  # 价格 100
PACKET_COOLDOWN = 5.0                       # 冷却 5 秒
PACKET_TYPE = 6                             # TowerDefenseEnum.PACKET_TYPE.ZOMBIE
# 其余逐字沿用内置读报僵尸
WEIGHT = 2000
WAVE_POINT_COST = 150
MASK_FLAGS = 9

# 护具：Paper（内置 flags = 68 = SHIELD|DAMAGEABLE ⇒ 二类护具层），血量覆盖成 500
ARMOR_NAME = "Paper"
ARMOR_DAMAGE_POINT = 500.0
ARMOR_REPLACE_MEDIA = "Zombie_paper_paper1.png"     # 与内置 ZombiePaperArmorPaper.tres 逐字一致
ARMOR_DESTROY_FLITER = "Zombie_paper_paper"
# armorList 顺序 = 内置 ZombiePaperArmorData.tres 的顺序（BlackHelmet, Bucket, Cone, Helmet, Paper, SpecialHelmet）
ARMOR_LIST_ORDER = ["BlackHelmet", "Bucket", "Cone", "Helmet", "Paper", "SpecialHelmet"]

# 豌豆（逐字沿用内置机枪豌豆僵尸的发射配置）
PEA_NAME = "Pea"
PEA_SPEED = -300.0          # 负数 = 「向前」（僵尸朝左；朝向镜像由 CreateProjectile 自行处理）
PEA_CATAPULT_HEIGHT = 400.0
FIRE_INTERVAL = 1.5         # 文档用：与插件普攻周期一致；动画链路失效 ⇒ 只有文档意义
FIRE_AUDIO = "ProjectileThrow"
CHECK_RAY_TARGET = "Vector2(-2000, 0)"
FIRE_MARKER_PATH = "SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker"

# 插件侧常量（⚠️ #45 起数值只在 runtime_shared/GatlingVolleyCore.cs 里出现**一次**；
# 这里是生成器侧的「期望值记录」，自检会逐个与共用核心里的字面量比对）
PLUGIN_ATTACK_INTERVAL = 1.5
PLUGIN_PEAS_PER_ATTACK = 7
PLUGIN_PEA_SPACING = 0.1
PLUGIN_ULTIMATE_CHANCE = 0.10
PLUGIN_ULTIMATE_SECONDS = 5.0
PLUGIN_ULTIMATE_PEAS = 300
PLUGIN_SCATTER_HALF_ANGLE = 15.0
PLUGIN_MAX_PEAS_PER_FRAME = 12
PLUGIN_STALL_THRESHOLD_MSEC = 250

DISPLAY_NAME = "超级机枪读报僵尸"
DESCRIPTION = ("每 1.5 秒向前方直线连发 7 颗豌豆；每次开火有 10% 概率触发大招："
               "5 秒内向 ±15° 散射 300 颗豌豆。护具 500，本体 1250，"
               "报纸被打掉后暴走，移速 ×3。")
HANDBOOK_DESC = ("报纸底下藏着一门机枪。每 1.5 秒向前连发 7 颗豌豆；每轮开火有 10% 概率"
                 "进入 5 秒狂暴，向 ±15° 散射 300 颗豌豆。身上的报纸（500 点护具）被打掉后"
                 "会暴走，移速 ×3。本体血量 1250，啃食伤害 800。")
HANDBOOK_STORY = "「今天的头条是：我。」"

# 托管运行时（见 docstring 第七节；改动前务必读完那 4 条约束）
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"                      # ⚠️ 只能是这个字面量
RUNTIME_ENTRY_TYPE = "SuperGatlingPaperRuntimeEntry"              # 无命名空间 ⇒ 类名即 FullName
RUNTIME_API_VERSION = 1                                          # ⚠️ 必须恰好 1
RUNTIME_POLICY = "optional"                                       # 加载失败不连坐角色
RUNTIME_SRC_DIR = os.path.join(WS, "runtime_src_zombie_super_gatling")
# 植物 / 僵尸**共用**的射击判定核心源文件（#45：两个 csproj 都 Compile Include 它）
SHARED_CORE = os.path.join(WS, "runtime_shared", "GatlingVolleyCore.cs")

# 包内相对路径（⚠️ 见 docstring 第三条 c：mod 自引用一律相对，禁 res://）
PKG_REL = f"Resources/Characters/{PKG_CAT}/{CHAR_KEY}"
CFG_FILE = f"TowerDefense{CHAR_KEY}.tres"       # TowerDefenseZombieSuperGatlingPaper.tres
SCENE_FILE = f"{CHAR_KEY}.tscn"
COMPONENT_SET_FILE = f"{CHAR_KEY}ComponentSet.tres"
FIRE_DEF_FILE = f"{CHAR_KEY}FireComponentDefinition.tres"
SPRITE_FILE = f"{CHAR_KEY}.tscn"
ARMOR_DATA_FILE = f"{CHAR_KEY}ArmorData.tres"
ARMOR_SLOT_FILE = f"{CHAR_KEY}ArmorPaper.tres"
CARD_REL = f"Resources/Cards/{CHAR_KEY}.tres"   # 注册键 == 文件名去扩展 == saveKey
PACKAGE_CFG_REL = f"{PKG_REL}/Config/{CFG_FILE}"
PACKAGE_PACKET_REL = f"{PKG_REL}/Packet/{CHAR_KEY}.tres"
ARMOR_DATA_REL = f"{PKG_REL}/Armor/{ARMOR_DATA_FILE}"
ARMOR_SLOT_REL = f"{PKG_REL}/Armor/Config/{ARMOR_SLOT_FILE}"

# 游戏侧编辑器的 72 个标准子目录，**原样照抄** XWModProjectLayout.StandardDirectories（顺序也一致）
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

MANIFEST_KEYS = [
    "schemaVersion", "id", "name", "version", "author", "description",
    "dependencies", "conflicts", "provides", "overrides", "scripts",
    "runtimeAssembly", "runtimeEntryType", "runtimeApiVersion", "runtimeAssemblyPolicy",
    "blueprints", "translations", "resources",
]
PROJECT_KEYS = [
    "Name", "Version", "Author", "Description", "ExportDirectory", "GameDirectory",
    "CreatedDate", "LastModifiedDate",
]

TZ_CN = timezone(timedelta(hours=8))
FIXED_T = (2026, 1, 1, 0, 0, 0)


def _p(*parts):
    """包内路径（MOD_ROOT/<角色包目录>/<parts...>）的绝对路径。"""
    return os.path.join(MOD_ROOT, PKG_REL.replace("/", os.sep), *parts)


def _abs(rel):
    """MOD_ROOT 下任意相对路径 → 绝对路径。"""
    return os.path.join(MOD_ROOT, rel.replace("/", os.sep))


# ---------------------------------------------------------------- 基础工具

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


def fmt_f(v):
    """Godot .tres 的 double 字段风格：至少保留一位小数（30.0 而不是 30）。"""
    s = f"{float(v):.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s


def write_text(path, text, newline="\n"):
    write_bytes(path, text.replace("\n", newline).encode("utf-8"))


def read_json(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def dump_json(path, obj):
    """包内 mod.json 风格：LF、原样 CJK、末尾无换行。"""
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2), "\n")


_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def godot_json(obj, newline="\r\n"):
    s = json.dumps(obj, ensure_ascii=True, indent=2)
    s = _ESC.sub(lambda m: "\\u" + m.group(1).upper(), s)
    return s.replace("\n", newline)


def net_datetime(dt):
    off = dt.strftime("%z")
    off = off[:3] + ":" + off[3:] if off else "+08:00"
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "0" + off


def safe_rmtree(path):
    """删除整棵目录树，**刻意不用 shutil.rmtree**。

    ⚠️ 本机运行环境把 `shutil.rmtree` 劫持成「先丢回收站」的 `_safe_shutil_rmtree`；
    回收站失败时 **fail-closed 直接抛 OSError**（实测 `SHFileOperationW 失败: 0x2`）。
    ⚠️⚠️ 逐文件 `os.remove` 在这个环境里**单次约 0.6 s**，所以主流程**不调用它**，
    改成 sweep_stale_files() + sync_tree() 的增量清理。保留给「人工整目录重置」。
    """
    if not os.path.isdir(path):
        return False
    for root, dirs, files in os.walk(path, topdown=False):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                os.remove(fp)
            except PermissionError:
                os.chmod(fp, stat.S_IWRITE)
                os.remove(fp)
        for dn in dirs:
            os.rmdir(os.path.join(root, dn))
    os.rmdir(path)
    return True


def sweep_stale_files(root, keep):
    """删掉 root 下「这次不再产出」的文件（增量清理，正常运行时一个都不删）。"""
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


# ---------------------------------------------------------------- 内容生成
#
# ⚠️ 本包**不写** uid / unique_id / parent_id_path（见交付文档「Godot 4.7 可选字段」一节）：
#    · uid 冲突比缺失更糟 —— 抄内置资源的 uid 会让两个资源撞号；
#    · unique_id / parent_id_path 是 4.7 新编辑器序列化出来的**可选**字段，
#      解包里 319 个 .tscn 完全不带它们（含多节点角色场景），说明不写也能加载。


def zombie_config_tres():
    """`TowerDefenseZombieConfig`：字段顺序对齐类声明顺序（防编辑器重排）。

    ⚠️ `name` 必须是「角色场景文件名」= CHAR_KEY：
    `TowerDefensePacketConfig.Create()` 用 `characterConfig.name` 去查
    `ResourceManager.TOWERDEFENSE_CHARCATERS`，而 mod 角色只能注册在 <Key> 这个键上
    （`ModLoader.TryInferCharacterScene`）。插件也靠这个字段认人 ⇒ **不能**写中文。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefenseZombieConfig" format=3]

[ext_resource type="Resource" path="../Armor/{ARMOR_DATA_FILE}" id="1"]
[ext_resource type="PackedScene" path="{BASE_ASH_SCENE}" id="2"]
[ext_resource type="Resource" path="{PAPER_DAMAGE_POINT_DATA}" id="3"]
[ext_resource type="Script" path="{BASE_ZOMBIE_CONFIG_SCRIPT}" id="4"]

[resource]
script = ExtResource("4")
attack = {fmt_f(ATTACK)}
weight = {WEIGHT}
wavePointCost = {WAVE_POINT_COST}
name = "{CHAR_KEY}"
hitpointsNearDeath = {fmt_f(HP_NEAR_DEATH)}
hitpoints = {fmt_f(HITPOINTS)}
damagePointData = ExtResource("3")
armorData = ExtResource("1")
customData = null
ashScene = ExtResource("2")
homeWorld = 1
cost = {COST}
packetCooldown = {fmt_f(PACKET_COOLDOWN)}
plantGridType = [-1]
maskFlags = {MASK_FLAGS}
metadata/_custom_type_script = "{BASE_ZOMBIE_CONFIG_SCRIPT}"
"""


def armor_slot_tres():
    """`ArmorSlotConfig`（包内 Paper 槽）—— 与内置 `ZombiePaperArmorPaper.tres` 逐字一致，
    只多加 `damagePoint = 500.0`。

    依据 `TowerDefenseArmorInstance` 构造函数第 114 行：
        `damagePointBase = ((slotConfig.damagePoint >= 0.0) ? slotConfig.damagePoint : typeData.damagePoint);`
    ⇒ 槽上的 damagePoint ≥ 0 时**覆盖**注册表里 Paper 的 150.0 ⇒ 需求「二类防具 500 血」。

    ⚠️ `replaceMediaName` / `destroyFliter` **必须照抄内置**：
      它们指的是精灵场景里那条媒体图层（`Zombie_paper_paper1.png` / `Zombie_paper_paper`），
      改一个字就会导致护具贴上不显示、碎纸动画不触发。

    字段顺序 = `ArmorSlotConfig` 类声明顺序（armorName → replaceMediaName → damagePoint → destroyFliter）。
    """
    return f"""[gd_resource type="Resource" script_class="ArmorSlotConfig" format=3]

[ext_resource type="Script" path="{ARMOR_SLOT_SCRIPT}" id="1"]

[resource]
script = ExtResource("1")
armorName = "{ARMOR_NAME}"
replaceMediaName = &"{ARMOR_REPLACE_MEDIA}"
damagePoint = {fmt_f(ARMOR_DAMAGE_POINT)}
destroyFliter = "{ARMOR_DESTROY_FLITER}"
"""


def armor_data_tres():
    """`CharacterArmorData` —— 与内置 `ZombiePaperArmorData.tres` 同构，
    只把 `Paper` 那一项换成**包内**的 500 血槽配置。

    为什么保留其余 5 个头盔：内置读报僵尸的同一份表里就有它们，
    关卡编辑器/第三方给僵尸戴帽子时靠这张表取 slotConfig（`GetOrCreateSlotConfig`）。
    删掉它们会让「戴帽子」这条既有能力静默消失 ⇒ **逐字保留**，只换 Paper 一项。

    四个字典都由 `CharacterArmorData.Init()` 从 `armorList` + `ArmorRegistry.json` 重建，
    这里照样**显式写出来**（与内置文件同构，且保证 Init 还没来得及跑时读到的也是正确值）。
    """
    slot_by_name = {
        "BlackHelmet": f"{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorBlackHelmet.tres",
        "Bucket": f"{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorBucket.tres",
        "Cone": f"{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorCone.tres",
        "Helmet": f"{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorHelmet.tres",
        "Paper": f"./Config/{ARMOR_SLOT_FILE}",                       # ★ 包内
        "SpecialHelmet": f"{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorSpecialHelmet.tres",
    }
    type_by_name = {n: f"{ARMOR_REGISTRY_CONFIG_DIR}/{n}.tres" for n in ARMOR_LIST_ORDER}

    lines = ['[gd_resource type="Resource" script_class="CharacterArmorData" format=3]', ""]
    ext_ids = {}
    nid = 1
    # 交错声明：与内置文件同序（槽 → 类型），便于人眼对照
    for name in ARMOR_LIST_ORDER:
        ext_ids[f"slot:{name}"] = str(nid)
        lines.append(f'[ext_resource type="Resource" path="{slot_by_name[name]}" id="{nid}"]')
        nid += 1
        ext_ids[f"type:{name}"] = str(nid)
        lines.append(f'[ext_resource type="Resource" path="{type_by_name[name]}" id="{nid}"]')
        nid += 1
    lines.append(f'[ext_resource type="Script" path="{ARMOR_DATA_SCRIPT}" id="{nid}"]')
    script_id = str(nid)
    lines.append("")
    lines.append("[resource]")
    lines.append(f'script = ExtResource("{script_id}")')
    lines.append("armorList = [" + ", ".join(
        f'ExtResource("{ext_ids["slot:" + n]}")' for n in ARMOR_LIST_ORDER) + "]")

    def dict_block(field, value_for):
        out = [f"{field} = {{"]
        for i, name in enumerate(ARMOR_LIST_ORDER):
            out.append(f'"{name}": {value_for(name)}' + ("," if i < len(ARMOR_LIST_ORDER) - 1 else ""))
        out.append("}")
        return out

    lines += dict_block("armorDictionary", lambda n: (
        "{\n"
        f'"slotConfig": ExtResource("{ext_ids["slot:" + n]}"),\n'
        f'"typeData": ExtResource("{ext_ids["type:" + n]}")\n'
        "}"))
    # Paper 的 destroyFliter = "Zombie_paper_paper" ⇒ Init() 会把它拆成 ["Zombie_paper_paper"]
    lines += dict_block("fliterAllDictionary", lambda n: (
        f'["{ARMOR_DESTROY_FLITER}"]' if n == ARMOR_NAME else "[]"))
    lines += dict_block("fliterOpenDictionary", lambda n: "[]")
    lines += dict_block("fliterCloseDictionary", lambda n: "[]")
    return "\n".join(lines) + "\n"


def fire_definition_tres():
    """`FireComponentDefinition` —— 本包唯一的「新增组件」。

    ★ 为什么**不写** `spritePath` / `fireAnimeClips` / `isSpliceSprite`：
      读报僵尸的精灵没有 Head 子精灵、没有 HeadFire clip，写了只会指向空节点；
      而 `AttackEntered()` 首句 `!CanPlayFireAnimation("")` 就 return
      ⇒ 动画链路整条失效本就是**预期的降级路径**（见 docstring 第六节）。
      插件走 `FireComponent.Fire()`，与动画完全解耦。

    ★ 豌豆参数**逐字沿用**内置机枪豌豆僵尸（`TowerDefenseZombieNormalGatlingPeaFireComponentDefinition.tres`）：
      · `speed = -300.0`：**负号 = 向前**。`CreateProjectile`（`:2738`）用
        `Mathf.Sign(parent.Scale.X * parent.transformPoint.Scale.X * parent.sprite.Scale.X)` 做朝向镜像；
        僵尸基础场景这三层都是 +1 ⇒ 取负号才是「向僵尸面朝方向飞」。
      · `projectileFlip = true`：让豌豆贴图与飞行方向一致。
      · `fireCheckList` 一条 + `fireProjectileList` **恰好一条**
        ⇒ 一次 `Fire()` 只出 **1 颗**（插件逐颗调用，正好能做到「恰好 300 颗」）。
      · `checkRayResources`：与内置同款的向后 2000px 射线，用于锁定同一路的最近目标。
    """
    return f"""[gd_resource type="Resource" script_class="FireComponentDefinition" format=3]

[ext_resource type="Resource" path="{BASE_FIRE_STATE_MACHINE}" id="1"]
[ext_resource type="Script" path="{BASE_RAY_SCRIPT}" id="2"]
[ext_resource type="Script" path="{BASE_CREATEDATA_SCRIPT}" id="3"]
[ext_resource type="Script" path="{BASE_PROJ_SINGLE_SCRIPT}" id="4"]
[ext_resource type="Script" path="{BASE_CHECK_CONFIG_SCRIPT}" id="5"]
[ext_resource type="Script" path="{BASE_FIRE_CONFIG_SCRIPT}" id="6"]
[ext_resource type="Script" path="{BASE_FIRE_DEF_SCRIPT}" id="7"]

[sub_resource type="Resource" id="AabbRay2DResource_backward"]
script = ExtResource("2")
TargetPosition = {CHECK_RAY_TARGET}

[sub_resource type="Resource" id="Resource_pea"]
script = ExtResource("3")
projectileName = &"{PEA_NAME}"
catapultHeight = {fmt_f(PEA_CATAPULT_HEIGHT)}

[sub_resource type="Resource" id="Resource_proj_single"]
script = ExtResource("4")
projectileData = SubResource("Resource_pea")
metadata/_custom_type_script = "{BASE_PROJ_SINGLE_SCRIPT}"

[sub_resource type="Resource" id="Resource_fcchk"]
script = ExtResource("5")
projectile = SubResource("Resource_proj_single")
metadata/_custom_type_script = "{BASE_CHECK_CONFIG_SCRIPT}"

[sub_resource type="Resource" id="Resource_fcfpc"]
script = ExtResource("6")
speed = {fmt_f(PEA_SPEED)}
projectileFlip = true
metadata/_custom_type_script = "{BASE_FIRE_CONFIG_SCRIPT}"

[resource]
script = ExtResource("7")
firePosMarkerPaths = [NodePath("{FIRE_MARKER_PATH}")]
checkRayResources = [SubResource("AabbRay2DResource_backward")]
fireInterval = {fmt_f(FIRE_INTERVAL)}
fireAudioName = "{FIRE_AUDIO}"
fireCheckList = [SubResource("Resource_fcchk")]
fireProjectileList = [SubResource("Resource_fcfpc")]
ComponentTypeId = "FireComponent"
DefinitionId = "mod.{MOD_ID}.component.fire"
InstanceId = "character.fire"
WireIndex = 0
StateMachineDefinition = ExtResource("1")
LegacyNodeNames = [&"FireComponent"]
"""


def component_set_tres():
    """`CharacterComponentSet` —— 父集（内置僵尸组件集）+ **只加**一个发射组件。

    与内置机枪豌豆僵尸（`TowerDefenseZombieNormalGatlingPeaComponentSet.tres`）完全同构。

    · **不**重复声明攻击组件：父集里 `AttackComponentZombieDefinition.tres` 已经带来
      `InstanceId = "character.attack.0"` 且 `attackType` 未写 = 默认 `"Eat"`（= 啃食，需求 5）。
      再声明一次同一个 InstanceId 属于自找麻烦。
    · `InstanceId = "character.fire"`：插件 `componentManager.GetRuntime<FireComponent>("character.fire")`
      就是靠它找组件 ⇒ **不能改**。
    · `DefinitionId` 是本 Mod 自己的命名空间（不参与运行时查找，改它安全）。
    """
    return f"""[gd_resource type="Resource" script_class="CharacterComponentSet" format=3]

[ext_resource type="Resource" path="./{FIRE_DEF_FILE}" id="1"]
[ext_resource type="Resource" path="{BASE_ZOMBIE_COMPONENT_SET}" id="2"]
[ext_resource type="Script" path="{BASE_COMPONENT_SET_SCRIPT}" id="3"]

[resource]
script = ExtResource("3")
ParentSet = ExtResource("2")
Components = [ExtResource("1")]
"""


def zombie_scene_tscn():
    """`Scene/<Key>.tscn`（6 段硬约束，见 docstring 第三条）。

    节点树**逐字复刻**内置 `TowerDefenseZombiePaper.tscn`（去掉 uid / unique_id / parent_id_path，
    理由见本节开头的注），因为护具 / 伤害点 / 精灵全是按 NodePath 找接点的：

      · `sprite`         = SpriteGroup/TransformPoint/ZombiePaper
      · `headSlot`       = …/ZombiePaper/HeadSlot        （暴走时改 followSlotId 换头）
      · `duckytobeSprite`/`waterLineSprite`              （水上表现，逐字保留）
      · damagePart / damagePartSlot                      （Arm / Head / 5 种头盔的伤害点）
      · currentArmor = ["Paper"]                         （出生就戴着那面报纸）

    ★★ **必须显式声明 `ComponentSet`** —— 这一条曾经漏掉，直接导致「一颗豌豆都打不出来」。
       基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:10` 自带
       `ComponentSet = ExtResource("2")` → `TowerDefenseZombieComponentSet.tres`，
       **那份里没有 FireComponent**。子场景不覆盖 ⇒ 发射组件根本不会被创建
       ⇒ 插件 `componentManager.GetRuntime<FireComponent>("character.fire")` 拿到 null、
          `IsUsable()` 判否、连 hook 都挂不上，日志里连一条 warning 都不会有（静默不发射）。
       依据（`TowerDefenseCharacter.cs`）：
         · `[Export] public CharacterComponentSet ComponentSet`（:703-704）；
         · `EnsureComponentManagerResource()`（:1911-1930）—— `ComponentSet` 有效就用它，
           否则回落到基场景继承来的那份；
         · `ComponentManager.InitializeResourceComponents()`（`ComponentManager.cs:318-346`）
           按 `ComponentSet.GetCreationPlan()` **逐条 `CreateRuntime()`** ⇒ 集里没有就真的没有。
       ⇒ 内置机枪豌豆僵尸场景就是这么干的（`TowerDefenseZombieNormalGatlingPea.tscn:25`
         把 `ComponentSet` 覆盖成自己那套含 FireComponent 的集），本包照抄这一行。

    ★ 本包只加**一个**新节点：`…/ZombiePaper/HeadSlot/FireMarker`（Marker2D）。
      必须挂在 HeadSlot 下 —— `FireComponent.ResolveReferences()` 走
      `ResolveOwnerNode<Marker2D>(path)`，也就是 `parent.GetNodeOrNull<Marker2D>(path)`：
        · 传 `AdobeAnimateSlot`（HeadSlot 自己）会因为类型不符拿到 null ⇒ 豌豆从僵尸原点出膛；
        · 挂在 HeadSlot 下面则自动跟随头部动画（含暴走换头），不需要我们算世界坐标。
      ⚠️ `position = Vector2(0, 0)` 是**唯一靠推断**的值（头部插槽原点，即头部中心）。
         想出膛点更靠嘴，只改这一行；这是交付文档里标注的「可微调点」。

    `[editable path="…/ZombiePaper"]` 必须保留：往实例子树里塞新节点要靠它。

    ⚠️ **只写我们真要改的属性，且一律用官方的 `Animation/*` 键名**。
    历史上这里写过 `clip` / `mediaReplaceAtlasPaths` / `mediaReplaceUse` ——
    三个都不是 `AdobeAnimateSprite` 的属性，被 Godot 静默丢弃（顶部「需求 1(c)」）。
    其中那张 `res://Asset/AtlasSource/Armor/…/ZombiePaper1.png` **千万不能激活**：
    报纸贴图的替换由**护具系统**在运行期做 ——
    `CharacterArmorData.cs:160-171` 按 `armorSlotConfig.replaceMethod == "Media"` 调
    `sprite.SetAtlasReplace(replaceMediaName, stageAnimeTexturePath)`，
    护具被打掉时 `TowerDefenseArmorInstance.cs:389` 用 `SetAtlasReplace(name, "")`
    还原内置图集。场景里再插一手 = 两套逻辑抢同一个媒体槽。
    """
    hide_head = "\n".join(f"Animation/LayerVisible/{n} = false" for n in BODY_HIDDEN_HEAD_LAYERS)
    return f"""[gd_scene format=3]

[ext_resource type="PackedScene" path="{BASE_ZOMBIE_SCENE}" id="1"]
[ext_resource type="Script" path="{PAPER_SCENE_SCRIPT}" id="2"]
[ext_resource type="Resource" path="{PAPER_HITBOX}" id="3"]
[ext_resource type="Resource" path="{PAPER_STATE_MACHINE}" id="4"]
[ext_resource type="Resource" path="../Config/{CFG_FILE}" id="5"]
[ext_resource type="Resource" path="{PAPER_DAMAGE_POINT_CONFIG_DIR}/ZombiePaperDamagePointArm.tres" id="6"]
[ext_resource type="Resource" path="{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorBlackHelmet.tres" id="7"]
[ext_resource type="Resource" path="{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorBucket.tres" id="8"]
[ext_resource type="Resource" path="{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorCone.tres" id="9"]
[ext_resource type="Resource" path="{PAPER_DAMAGE_POINT_CONFIG_DIR}/ZombiePaperDamagePointHead.tres" id="10"]
[ext_resource type="Resource" path="{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorHelmet.tres" id="11"]
[ext_resource type="Resource" path="{PAPER_ARMOR_CONFIG_DIR}/ZombiePaperArmorSpecialHelmet.tres" id="12"]
[ext_resource type="PackedScene" path="../Sprite/{SPRITE_FILE}" id="13"]
[ext_resource type="PackedScene" path="{BASE_WATER_LINE_SCENE}" id="14"]
[ext_resource type="Resource" path="./{COMPONENT_SET_FILE}" id="15"]

[node name="{CHAR_KEY}" node_paths=PackedStringArray("duckytobeSprite", "waterLineSprite", "sprite", "headSlot") instance=ExtResource("1")]
ComponentSet = ExtResource("15")
script = ExtResource("2")
HitBoxDefinition = ExtResource("3")
MainStateMachineDefinition = ExtResource("4")
duckytobeSprite = NodePath("SpriteGroup/TransformPoint/ZombiePaper/ZombieDuckytube")
waterLineSprite = NodePath("SpriteGroup/TransformPoint/ZombieWaterLine")
waterHeight = 20.0
config = ExtResource("5")
sprite = NodePath("SpriteGroup/TransformPoint/ZombiePaper")
headSlot = NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot")
damagePart = {{
"Arm": ExtResource("6"),
"BlackHelmet": ExtResource("7"),
"Bucket": ExtResource("8"),
"Cone": ExtResource("9"),
"Head": ExtResource("10"),
"Helmet": ExtResource("11"),
"SpecialHelmet": ExtResource("12")
}}
damagePartSlot = {{
"Arm": NodePath("SpriteGroup/TransformPoint/ZombiePaper/ArmSlot"),
"BlackHelmet": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot"),
"Bucket": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot"),
"Cone": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot"),
"Head": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot"),
"Helmet": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot"),
"SpecialHelmet": NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot")
}}
currentArmor = ["{ARMOR_NAME}"]
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "{DISPLAY_NAME}"
metadata/mod_character_category = "Zombie"
metadata/mod_character_config_path = "../Config/{CFG_FILE}"
metadata/mod_character_sprite_scene = "../Sprite/{SPRITE_FILE}"

[node name="TransformPoint" parent="SpriteGroup" index="0"]
position = Vector2(12, 33)

[node name="ZombiePaper" parent="SpriteGroup/TransformPoint" index="0" instance=ExtResource("13")]
position = Vector2(-16, -37)
Animation/Clip = "Idle"
{hide_head}

[node name="ZombieDuckytube" parent="SpriteGroup/TransformPoint/ZombiePaper" index="0"]
position = Vector2(-10.319496, -38.513157)
rotation = -0.07512771
Animation/Clip = "Idle"
followParentSpriteLayerId = 12

[node name="HeadSlot" parent="SpriteGroup/TransformPoint/ZombiePaper" index="1"]
drawLayerId = -2
position = Vector2({HEAD_SLOT_POS[0]}, {HEAD_SLOT_POS[1]})
rotation = {HEAD_SLOT_ROT_RAD}
scale = Vector2({HEAD_SLOT_SCALE}, {HEAD_SLOT_SCALE})

[node name="FireMarker" type="Marker2D" parent="SpriteGroup/TransformPoint/ZombiePaper/HeadSlot" index="0"]
position = Vector2({FIRE_MARKER_POS[0]}, {FIRE_MARKER_POS[1]})

[node name="ArmSlot" parent="SpriteGroup/TransformPoint/ZombiePaper" index="2"]
position = Vector2(9.27762, -0.8128052)
rotation = -0.1722636
scale = Vector2(0.6995205, 0.6995205)

[node name="PaperSlot" parent="SpriteGroup/TransformPoint/ZombiePaper" index="3"]
position = Vector2(-25.832891, 1.6327133)
rotation = -0.02570264
scale = Vector2(0.7015697, 0.7015697)

[node name="GroundSlot" parent="SpriteGroup/TransformPoint/ZombiePaper" index="4"]
position = Vector2(-40, -80)

[node name="ZombieWaterLine" parent="SpriteGroup/TransformPoint" index="1" instance=ExtResource("14")]
visible = false
position = Vector2(3, -36)
trueFrameRate = 180.0
Animation/Clip = "Idle"

[editable path="SpriteGroup/TransformPoint/ZombiePaper"]
"""


def sprite_scene_tscn():
    """`Sprite/<Key>.tscn`（6 段，文件夹 == 文件名 == <Key>）。

    ⚠️ 依据 docstring 第三条 c/d：没有这个文件就没有 `CHARCTAER_SPRITE[<Key>]`，
    `XWModContentValidation` 第 35-36 行直接 throw「缺少 CharacterSprite/<Key>」，
    运行时 `GetPacketSpriteScene()` 也会抛 `KeyNotFoundException`。

    结构 = 内置 `ZombiePaper.tscn`（读报僵尸身体，保住四肢 / 报纸 / 插槽全部原始表现）
           + **三个**换头节点（★ 为什么不是「一个 Head 子节点」见顶部 `HEAD_NODE_NAME` 上方
             那整段根因说明 —— 单节点会被身体「父代画」⇒ 采样全局共享大图 ⇒ 碎片拼贴）：

             `HeadShadow`  ← 身体的子精灵，`visible = false` + 29 层全 `false`
                             （**位姿影子**：只吃 `UpdateChild()` 的每帧定位，零切片）
             `HeadHolder`  ← 普通 `Node2D`（identity），**打断「父代画」**的容器
             `Head`        ← `HeadHolder` 的子节点 = **给人看的那个头**
                             （29 层全 `true`，独立渲染，插件每帧从影子抄位姿）

    ★ 2026-09-23 起，影子与可见头各多三行（见顶部 (A)/(B)/(C) 三段长注释）：
        `usePos = true`       ← 显式写出来（默认也是 true）：Position 仍跟 `anim_head1`
        `useRotate = false`   ← 关掉引擎对 `Rotation` 的每帧覆写 ⇒ 头**摆正、不再歪斜**
        `rotation = -0.25`    ← 固定 net 旋转（弧度 −0.25 = −14.324°，官方同款取值）
      可见头另有 `z_index = 1` ← 排序键第一位是 EffectiveZIndex ⇒ 压住身体与报纸

    对位模型见本文件顶部「需求 1」注释块；官方同款写法见
    `Asset/Anime/Character/Zombie/Chapter1/Normal/Sprite/GatlingPea/ZombieNormalGatlingPea.tscn`
    与 `…/Chapter2/Zamboni/Sprite/GatlingPea/ZombieZamboniGatlingPea.tscn`
    （本包的 `Head` 与植物 `SuperGatlingPea.tscn` 的 `Head` 逐字段同构）。
    `useRotate = false` 的官方先例见 `…/ZombieGargantuar.tscn:141` 等 14 处。

    ⚠️ 属性一律用官方的 `Animation/Clip`、`Animation/LayerVisible/<图层名>`、
    `Animation/MediaReplace/<媒体名>` 写法 —— 裸的 `clip` / `mediaReplaceAtlasPaths` /
    `mediaReplaceUse` / `name_ignore` **不是** `AdobeAnimateSprite` 的属性，会被
    Godot 静默丢弃（详见顶部「需求 1 (c)」）。
    ⚠️ `flashAnimeData` 必须写在所有 `Animation/LayerVisible/*` **之前**。

    ⚠️ 两个场景文件都靠 `Scene/<Key>.tscn` 的 `ExtResource("13")` 与
    `metadata/mod_character_sprite_scene` 指过来 ⇒ **改一处即可**。
    """
    layer_keys = head_layer_names()
    media_keys = head_media_names()
    # ③ 可见头：29 层全 true —— 它独立渲染，切片由**它自己**的 definition +
    #    它自己的纹理数组（standalone ⇒ page 0 == 皮肤图集）解析 ⇒ 不会错位。
    vis_on = "\n".join(f"Animation/LayerVisible/{k} = true" for k in layer_keys)
    # ① 影子：29 层全 false —— 它仍然被身体代画，但**一层都不画**
    #    ⇒ 零切片 ⇒ 既不产生碎片，也不会让身体的批次颜色/图集对不上。
    vis_off = "\n".join(f"Animation/LayerVisible/{k} = false" for k in layer_keys)
    med = "\n".join(f"Animation/MediaReplace/{k} = null" for k in media_keys)
    # 身体：显式关掉原头的 7 层（内置 ZombiePaper.tscn 把它们写死成 true 了）
    hide_head = "\n".join(f"Animation/LayerVisible/{n} = false" for n in BODY_HIDDEN_HEAD_LAYERS)
    # (B) 姿态冻结：`useRotate = false` ⇒ 引擎不再覆写 `Rotation`
    #     （`AdobeAnimateSprite.cs:5258-5276`，赋值包在 `if (useRotate)` 内），
    #     节点自写的 `rotation` 生效；`Position` 仍由 `usePos = true` 每帧跟随
    #     ⇒ 「摆正、不再歪斜」+「与身体的相对位置保持一致」。
    #     影子与可见头**用同一串**（逐字相同是硬约束），由 `SyncHeadPairs()` 每帧传递。
    #     开关关掉 ⇒ 两行都不写 ⇒ 回到跟 `anim_head1` 摆头的旧行为（一键回滚）。
    # ⚠️ 2026-09-23 第三轮用户要求「回退头部动画」⇒ 当前 `HEAD_FIX_HEAD_ROTATE = False`
    #    ⇒ `rot_lines = ""`：**三行一个都不写**（`rotation` 单独留着是死值，只会误导）。
    if HEAD_FIX_HEAD_ROTATE:
        rot_lines = (f"usePos = true\n"
                     f"useRotate = false\n"
                     f"rotation = {HEAD_FIXED_ROT_RAD}")
    else:
        rot_lines = ""
    # (C) 层级：排序键第一位是 EffectiveZIndex(= z_index 沿父链累加) ⇒ 正数即压住身体
    z_lines = f"z_index = {HEAD_NODE_Z_INDEX}" if HEAD_NODE_Z_INDEX else ""
    return f"""[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="{PAPER_SPRITE_SCENE}" id="1_game_sprite"]
[ext_resource type="Script" path="{ADOBE_SPRITE_BASE_SCRIPT}" id="2_head_script"]
[ext_resource type="Resource" path="{head_data_rel()}" id="3_head_data"]

[node name="{CHAR_KEY}Sprite" instance=ExtResource("1_game_sprite")]
Animation/Clip = "Idle"
{hide_head}
metadata/mod_resource_kind = "CharacterSprite"
metadata/mod_preview_source = "读报僵尸身体（ZombiePaper）+ 超级机枪射手的头（包内自带的官方素材直转皮肤 SuperGatlingPea）"

[node name="{HEAD_SHADOW_NODE_NAME}" type="Node2D" parent="." node_paths=PackedStringArray("parentSprite")]
visible = false
scale = Vector2({HEAD_SCALE[0]:g}, {HEAD_SCALE[1]:g})
script = ExtResource("2_head_script")
flashAnimeData = ExtResource("3_head_data")
useMultiMesh = true
offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})
offsetRotate = {HEAD_OFFSET_ROTATE}
{rot_lines}
trueFrameRate = {HEAD_TRUE_FRAME_RATE:g}
useTween = false
skipLastFrame = false
parentSprite = NodePath("..")
Animation/Clip = "{HEAD_CLIP}"
{vis_off}
{med}
Layer = {HEAD_INSERT_LAYER_ID}
insertLayerId = {HEAD_INSERT_LAYER_ID}
followParentSpriteLayerId = {HEAD_FOLLOW_LAYER_ID}

[node name="{HEAD_HOLDER_NODE_NAME}" type="Node2D" parent="."]

[node name="{HEAD_NODE_NAME}" type="Node2D" parent="{HEAD_HOLDER_NODE_NAME}"]
unique_name_in_owner = true
{z_lines}
scale = Vector2({HEAD_SCALE[0]:g}, {HEAD_SCALE[1]:g})
script = ExtResource("2_head_script")
flashAnimeData = ExtResource("3_head_data")
useMultiMesh = true
offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})
offsetRotate = {HEAD_OFFSET_ROTATE}
{rot_lines}
trueFrameRate = {HEAD_TRUE_FRAME_RATE:g}
useTween = false
skipLastFrame = false
Animation/Clip = "{HEAD_CLIP}"
{vis_on}
{med}
metadata/mod_resource_kind = "CharacterSprite"
"""


def packet_tres(config_rel):
    """僵尸卡片 `TowerDefensePacketConfig`。

    ⚠️ 硬闸门（docstring 第三条 d）：
      · `saveKey` == 注册键 == 卡片文件名去扩展 == `{CHAR_KEY}`；
      · `characterConfig` 必须能加载，且它的 name 已注册进 TOWERDEFENSE_CHARACTERS；
      · `unlockCheckList` 必须为空表（放游戏内条件会被判「必须使用 Mod 专属解锁条件」）；
      · `type = 6` = PACKET_TYPE.ZOMBIE（需求「作为僵尸卡使用」）。
    `config_rel`：本文件所在目录到 Config 的相对路径（两处分发目录深度不同）。

    ⚠️ `name`/`describe`/`handbook*` 直接写中文（理由见 docstring 第四条）——
    内置卡片这里是翻译键，但 ModLoader 从不调用 `TranslationServer.AddTranslation`，
    翻译表进不了游戏运行时，写键只会显示成键本身。

    `packetAnimeOffset / packetAnimeScale` 照抄内置读报僵尸卡（同一套美术）。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefensePacketConfig" format=3]

[ext_resource type="Resource" path="{config_rel}" id="1"]
[ext_resource type="Script" path="{BASE_PACKET_SCRIPT}" id="2"]

[resource]
script = ExtResource("2")
saveKey = "{CHAR_KEY}"
unlockCheckList = []
name = "{DISPLAY_NAME}"
describe = "{DESCRIPTION}"
handbookDescribe = "{HANDBOOK_DESC}"
handbookStory = "{HANDBOOK_STORY}"
packetAnimeOffset = Vector2(25, 60)
packetAnimeScale = Vector2(0.75, 0.75)
characterConfig = ExtResource("1")
type = {PACKET_TYPE}
override = null
metadata/_custom_type_script = "{BASE_PACKET_SCRIPT}"
"""


def build_manifest():
    """manifest 键序必须严格等于 XWModManifestSerializeHandler 的顺序。

    ⚠️ `provides` 里出现的每个 key 都必须真的被注册，否则
    `ModLoader.ValidateManifestRegistrations` 判定失败 → 整包 apply 失败。
    ModLoader 推导出的 key（`ModLoader.cs:1077` 一带的规则表）：
      - Character       = `Resources/Characters/Zombies/<Key>/Scene/<Key>.tscn` 的 <Key>
      - CharacterSprite = `Resources/Characters/Zombies/<Key>/Sprite/<Key>.tscn` 的 <Key>
      - Packet          = `Resources/Cards/<文件名去扩展>`
    三者在（含 sprite）本包统一为 `{CHAR_KEY}`。
    两个 Armor `.tres` 与 ComponentSet/FireDefinition/角色配置/包内 Packet 都**不作资源条目**
    （`InferRuntimeEntry` 返回 false），但要进 `resources` 清单 —— 那是「包内全部产物」的账本。

    ⚠️ `Resources/Animations/SuperGatlingPea.{tres,dat}` + 图集 PNG 是**皮肤资源副本**
    （从植物包镜像过来的），不是注册类别，但必须进 `resources`：
      1. 打包时按这个清单收条目（`collect_entries` 只认清单里的文件？—— 否，它整目录收；
         但 `main()` 会拿清单校验「文件是否存在」，缺了就在这里报错）；
      2. `.tres` 走 standalone（`animeFile = "./SuperGatlingPea.dat"`）⇒ `.dat` 必须与
         `.tres` **同目录**，否则 `.dat` 载入失败只会 `GD.PushWarning` 然后**静默不画**。
    植物包 `SuperGatlingPea/mod.json` 里同样是这 3 条（逐字同款）。

    resources 的顺序 = `XWModManifestSyncService.SyncProject` 的规范序
    （`NormalizeManifestCollections` 会排序）⇒ 这里**用 sorted(key=lower) 生成**，
    否则编辑器一打开工程就重写 mod.json。
    ⚠️ `Runtime/ModAssembly.dll` 也会落进 Resources 段（它不是可推导类别），必须一起排序声明。
    ⚠️ 本包**不带** `Localization/`，所以 `translations` 为空表（见 docstring 第四条）。
    """
    return {
        "schemaVersion": 2,
        "id": MOD_ID,
        "name": MOD_NAME,
        "version": "1.0.0",
        "author": "云漫行",
        "description": DESCRIPTION + "（含托管运行时插件 Runtime/ModAssembly.dll）",
        "dependencies": [],
        "conflicts": [],
        "provides": {
            "Character": [CHAR_KEY],
            "CharacterSprite": [CHAR_KEY],
            "Packet": [CHAR_KEY],
        },
        "overrides": {},
        "scripts": [],
        "runtimeAssembly": RUNTIME_ASSEMBLY,
        "runtimeEntryType": RUNTIME_ENTRY_TYPE,
        "runtimeApiVersion": RUNTIME_API_VERSION,
        "runtimeAssemblyPolicy": RUNTIME_POLICY,
        "blueprints": [],
        "translations": [],
        "resources": sorted([
            CARD_REL,
            ARMOR_DATA_REL,
            ARMOR_SLOT_REL,
            PACKAGE_CFG_REL,
            PACKAGE_PACKET_REL,
            f"{ANIM_SKIN_REL}/{SKIN_TRES_FILE}",
            f"{ANIM_SKIN_REL}/{SKIN_DAT_FILE}",
            f"{ANIM_SKIN_REL}/{SKIN_ATLAS_FILE}",
            f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}",
            f"{PKG_REL}/Scene/{FIRE_DEF_FILE}",
            f"{PKG_REL}/Scene/{SCENE_FILE}",
            f"{PKG_REL}/Sprite/{SPRITE_FILE}",
            RUNTIME_ASSEMBLY,
        ], key=lambda p: p.lower()),
    }


def copy_skin_assets():
    """把植物包的皮肤三件套增量镜像进本包 `Resources/Animations/`。

    ⚠️ 为什么不直接 `res://` 引用植物包？—— `.pmod` 之间**不能互相引用**
    （ModLoader 每个包独立挂载，跨包相对路径越界；`res://` 只解析游戏自带资源）。
    ⇒ 只能复制一份。复制是**幂等**的（`write_bytes_if_changed` 内容相同不落盘），
    所以植物包改了皮肤，这里重跑一次就会跟上。

    返回写入的文件数。
    """
    os.makedirs(skin_anim_dir(), exist_ok=True)
    wrote = 0
    for fn in (SKIN_TRES_FILE, SKIN_DAT_FILE, SKIN_ATLAS_FILE):
        src = os.path.join(SKIN_SRC_DIR, fn)
        if not os.path.isfile(src):
            raise RuntimeError(
                f"缺皮肤源文件 {src} —— 先跑 build_plant_super_gatling.py 生成植物包皮肤")
        with open(src, "rb") as f:
            data = f.read()
        if write_bytes_if_changed(os.path.join(skin_anim_dir(), fn), data):
            wrote += 1
    return wrote


# ---------------------------------------------------------------- 组装

def ensure_project_layout(project_dir):
    n = 0
    for d in STANDARD_DIRS:
        os.makedirs(os.path.join(project_dir, d.replace("/", os.sep)), exist_ok=True)
        n += 1
    return n


def build_project_file(existing=None):
    """⚠️ 幂等要求：LastModifiedDate 必须「读回旧值」，不能写 now。

    否则每次运行都会改字节，与其余生成器的字节幂等约定冲突。
    只有创建时（无旧文件）才写入当前时间。
    """
    now = datetime.now(TZ_CN)
    created = existing.get("CreatedDate") if existing else None
    if not created:
        created = net_datetime(now)
    modified = existing.get("LastModifiedDate") if existing else None
    if not modified:
        modified = net_datetime(now)
    obj = {
        "Name": MOD_NAME,
        "Version": "1.0.0",
        "Author": "云漫行",
        "Description": f"新增僵尸「{DISPLAY_NAME}」（数据 + 托管运行时插件）",
        # ⚠️ 必须和编辑器自己写出的形态一致：**正斜杠 + 结尾斜杠**
        "ExportDirectory": MODS_DIR.replace("\\", "/") + "/",
        "GameDirectory": "",
        "CreatedDate": created,
        "LastModifiedDate": modified,
    }
    assert list(obj.keys()) == PROJECT_KEYS, "工程文件键序不符"
    return obj


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
    """把工程目录增量镜像到 Mods/ 下。dst 里不放 .pmod，所以不污染 ScanMods(*.pmod)。"""
    if not mirror_is_ours(dst, marker):
        return "跳过（%s 已存在且不是本工程，未改动）" % dst
    wrote, removed = sync_tree(src, dst, marker)
    return "已镜像到 %s（写 %d / 删 %d）" % (dst, wrote, removed)


def merge_enabled_mods(mods_dir, mod_id):
    """把本 Mod 的 id 并进 `Mods/enabled_mods.json`。

    ⚠️ 2026-09-19 踩到并修掉的坑：`MOD_ID` 只改了**大小写**
    （`discogargantuarPult` → `discogantuarpult`）时，这个函数原来「只增不删」，
    于是列表里同时留下新旧两条 id —— 游戏会拿旧 id 去扫 `Mods/*.pmod`，
    扫不到就报一条未知 Mod 的告警，而且**再跑生成器也不会自愈**。
    现在：仅大小写相同的 id 视为「本 Mod 自己的历史 id」直接清掉
    （别的 Mod 不可能与本 Mod 的 id 只差大小写），并回报被清掉的那几条。

    ⚠️ 另外注意 id 的**前缀包含**关系不算「同 id」：`supergatlingpea`（植物 Mod）
    与 `supergatlingpaper`（本 Mod）是两个不同的 Mod，必须能共存，绝不能互删。
    """
    p = os.path.join(mods_dir, "enabled_mods.json")
    ids = []
    if os.path.isfile(p):
        try:
            v = read_json(p)
            if isinstance(v, list):
                ids = [x for x in v if isinstance(x, str)]
        except Exception:
            ids = []
    dropped = sorted({x for x in ids if x != mod_id and x.lower() == mod_id.lower()})
    if dropped:
        ids = [x for x in ids if x not in dropped]
    if mod_id not in ids:
        ids.append(mod_id)
    ids = sorted(set(x.strip() for x in ids if x.strip()), key=lambda s: s.lower())
    write_text(p, json.dumps(ids, ensure_ascii=False, indent=2), "\n")
    return ids, dropped


def merge_recent_project(project_file_abs):
    """把工程登记进编辑器「最近工程」缓存（`mod_editor_recent_projects.cfg`，与 `Mods/` 同级）。

    ⚠️ 三个必须守住的点（实测踩过，别改回去）：
      1. **不能丢别人的条目**：解析前必须先把 CRLF 归一化成 LF，
         否则 `^path_\\d+="(.*)"$` 一条都匹配不到，整个列表被重写成「只剩自己一条」。
      2. 路径一律写**正斜杠**；登记的是 **Mods 下**那份工程（编辑器只认那里）。
      3. 保留原文件的换行风格与末尾换行。
    """
    cfg = os.path.join(USER_DATA_DIR, "mod_editor_recent_projects.cfg")
    if not os.path.isfile(cfg):
        return None
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
        return len(paths)
    paths.insert(0, want)
    body = "[projects]\n\ncount=%d\n" % len(paths)
    body += "".join('path_%d="%s"\n' % (i, p) for i, p in enumerate(paths))
    if not trailing:
        body = body[:-1]
    write_text(cfg, body, nl)
    return len(paths)


def collect_entries():
    entries = []
    for root, dirs, files in os.walk(MOD_ROOT):
        dirs.sort()
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, MOD_ROOT).replace("\\", "/")
            if rel.endswith((".uid", ".import")) or rel.endswith(".cs"):
                continue
            if rel.endswith(".pvzmodeproject"):
                continue
            if os.path.basename(rel).startswith("."):
                continue
            entries.append(rel)
    # mod.json 必须是第 0 个条目
    entries.sort(key=lambda r: (r != "mod.json", r))
    return entries


def package_pmod(out_path):
    entries = collect_entries()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in entries:
            zi = zipfile.ZipInfo(rel, FIXED_T)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            full = os.path.join(MOD_ROOT, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as f:
                z.writestr(zi, f.read())
    return entries


# ---------------------------------------------------------------- 自检

def self_check():
    fails = []
    # 皮肤源是生成场景/断言的前置条件：缺了就直接给一条明确的话，别抛裸 traceback
    if not os.path.isfile(skin_tres_src()):
        return [f"缺皮肤源 {skin_tres_src()} —— 先跑 build_plant_super_gatling.py"
                "（本包把植物包的皮肤三件套复制进 Resources/Animations/，.pmod 之间不能互引）"]
    cfg = zombie_config_tres()
    txt = component_set_tres()
    fire = fire_definition_tres()
    sc = zombie_scene_tscn()
    sp = sprite_scene_tscn()
    ar_data = armor_data_tres()
    ar_slot = armor_slot_tres()
    pk_card = packet_tres(f"../Characters/{PKG_CAT}/{CHAR_KEY}/Config/{CFG_FILE}")
    pk_pkg = packet_tres(f"../Config/{CFG_FILE}")

    # 1. 6 段路径约束（Scene 与 Sprite 两条）
    for folder, fn in (("Scene", SCENE_FILE), ("Sprite", SPRITE_FILE)):
        parts = f"{PKG_REL}/{folder}/{fn}".split("/")
        if len(parts) != 6:
            fails.append(f"{folder} 路径段数 {len(parts)} != 6")
        if parts[2] != PKG_CAT:
            fails.append(f"{folder} 类别目录应为 {PKG_CAT}：{parts}")
        if parts[3] != CHAR_KEY or parts[5] != CHAR_KEY + ".tscn":
            fails.append(f"{folder} 路径/文件名与 key 不一致：{parts}")
    # 2. 包内自引用禁 res://（只允许 res:// 指向游戏自带资源）
    game_ok = ("res://Prefab/", "res://Asset/", "res://Script/", "res://Resource/",
               "res://Registry/", "res://Extends/", "res://addons/")
    texts = (("ComponentSet", txt), ("FireDefinition", fire), ("Scene", sc),
             ("Sprite", sp), ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg),
             ("ArmorData", ar_data), ("ArmorSlot", ar_slot))
    for name, body in texts:
        for path in re.findall(r'path="([^"]+)"', body):
            if path.startswith("res://"):
                if not path.startswith(game_ok):
                    fails.append(f"{name} 的 res:// 引用不是游戏自带资源：{path}")
            elif path.startswith("user:/") or ":" in path.split("/")[0]:
                fails.append(f"{name} 含绝对/非法引用：{path}")
    # 3. .tres 里的 Script 引用必须是 res://（.tres 非 res:// 会被直接拒绝）
    for name, body in (("ComponentSet", txt), ("FireDefinition", fire), ("Config", cfg),
                       ("Card", pk_card), ("PkgPacket", pk_pkg),
                       ("ArmorData", ar_data), ("ArmorSlot", ar_slot)):
        for line in body.splitlines():
            if "[ext_resource" in line and 'type="Script"' in line:
                m = re.search(r'path="([^"]+)"', line)
                if not (m and m.group(1).startswith("res://")):
                    fails.append(f"{name} 的 Script 引用非 res://：{line.strip()}")
    # 4. 不得内嵌脚本（ModLoader 见到 GDScript/CSharpScript 字面量直接拒包）
    for name, body in texts:
        if 'type="CSharpScript"' in body or 'type="GDScript"' in body:
            fails.append(f"{name} 含内嵌脚本")
    # 5. 不得出现 .scn / .res 引用（PrepareSafeCharacterPackage 会直接拒包）
    for name, body in texts:
        if re.search(r'path="[^"]+\.(scn|res)"', body):
            fails.append(f"{name} 引用了 .scn/.res 二进制资源（整包会被拒）")
    # 6. Godot 4.7 的 uid / unique_id / parent_id_path 一律不写
    for name, body in (("Scene", sc), ("Sprite", sp), ("Config", cfg), ("ArmorData", ar_data),
                       ("ArmorSlot", ar_slot), ("Card", pk_card), ("PkgPacket", pk_pkg),
                       ("ComponentSet", txt), ("FireDefinition", fire)):
        if "unique_id=" in body or "parent_id_path=" in body or "uid://" in body:
            fails.append(f"{name} 不应写 uid / unique_id / parent_id_path（可选字段，写了要伪造哈希）")
    # 7. ⚠️ 不许出现 CompanionOnly（会让 ModLoader 去要伴随运行时 → 拿不到就拒包）
    if "CompanionOnly" in sc or "mod_character_script_binding" in sc:
        fails.append("场景不得带 mod_character_script_binding（CompanionOnly 会被拒包）")

    # 8. 配置数值（需求 5）
    if f"hitpoints = {fmt_f(HITPOINTS)}" not in cfg:
        fails.append(f"config.hitpoints 应为 {fmt_f(HITPOINTS)}")
    if f"hitpointsNearDeath = {fmt_f(HP_NEAR_DEATH)}" not in cfg:
        fails.append(f"config.hitpointsNearDeath 应为 {fmt_f(HP_NEAR_DEATH)}")
    if abs((HITPOINTS + HP_NEAR_DEATH) - HP_TOTAL) > 1e-9:
        fails.append(f"总血 {HITPOINTS + HP_NEAR_DEATH} != 需求 {HP_TOTAL}")
    if f"attack = {fmt_f(ATTACK)}" not in cfg:
        fails.append(f"config.attack 应为 {fmt_f(ATTACK)}")
    if f"cost = {COST}" not in cfg:
        fails.append(f"config.cost 应为 {COST}")
    if f"packetCooldown = {fmt_f(PACKET_COOLDOWN)}" not in cfg:
        fails.append(f"config.packetCooldown 应为 {fmt_f(PACKET_COOLDOWN)}")
    if f'name = "{CHAR_KEY}"' not in cfg:
        fails.append("config.name 必须等于角色场景文件名（TOWERDEFENSE_CHARCATERS 的键）")
    if "smashAttack" in cfg:
        fails.append("本包不应写 smashAttack（默认即可，写了会偏向碾压）")
    if cfg.index(f"hitpoints = {fmt_f(HITPOINTS)}") < cfg.index(f'name = "{CHAR_KEY}"'):
        fails.append("hitpoints 必须写在 name 之后（对齐类声明顺序，防编辑器重排）")
    if cfg.index("attack = ") > cfg.index("weight = "):
        fails.append("attack 必须写在 weight 之前（TowerDefenseZombieConfig 声明顺序）")
    if cfg.index("homeWorld = ") > cfg.index(f"cost = {COST}"):
        fails.append("homeWorld 必须写在 cost 之前（TowerDefenseCharacterConfig 声明顺序）")
    if cfg.index(f"packetCooldown = {fmt_f(PACKET_COOLDOWN)}") > cfg.index("plantGridType = "):
        fails.append("packetCooldown 必须写在 plantGridType 之前（类声明顺序）")
    # 移速：整包不得出现速度/时标覆盖（需求 5「移速 = 普通僵尸」）
    for name, body in (("Scene", sc), ("Config", cfg)):
        for k in ("walkSpeedScale", "timeScale", "animeSpeedScale"):
            if k in body:
                fails.append(f"{name} 不应写 {k}（需求 5 要求与普通僵尸同速 = 一个都不写）")

    # 9. 二类防具 500（需求 5 前半）
    if f'armorName = "{ARMOR_NAME}"' not in ar_slot:
        fails.append(f"ArmorSlot.armorName 应为 {ARMOR_NAME}")
    if f"damagePoint = {fmt_f(ARMOR_DAMAGE_POINT)}" not in ar_slot:
        fails.append(f"ArmorSlot.damagePoint 应为 {fmt_f(ARMOR_DAMAGE_POINT)}（覆盖注册表的 150）")
    if f'replaceMediaName = &"{ARMOR_REPLACE_MEDIA}"' not in ar_slot:
        fails.append("ArmorSlot.replaceMediaName 必须照抄内置（否则护具贴图不显示）")
    if f'destroyFliter = "{ARMOR_DESTROY_FLITER}"' not in ar_slot:
        fails.append("ArmorSlot.destroyFliter 必须照抄内置（否则碎纸动画不触发）")
    if "damagePoint" not in ar_slot.split("[resource]")[1]:
        fails.append("damagePoint 必须写在 [resource] 段里")
    #     四个字典必须与 armorList 一致
    for name in ARMOR_LIST_ORDER:
        if f'"{name}": {{' not in ar_data:
            fails.append(f"ArmorData.armorDictionary 缺 {name}")
        if f'"{name}": [' not in ar_data:
            fails.append(f"ArmorData 的 fliter 字典缺 {name}")
    order_in_file = [ar_data.index(f'"{n}": {{') for n in ARMOR_LIST_ORDER]
    if order_in_file != sorted(order_in_file):
        fails.append("ArmorData 的字典键序应与 armorList 顺序一致（防编辑器重排）")
    if f'armorList = [' not in ar_data:
        fails.append("ArmorData 缺 armorList")
    if ar_data.index('"Paper": {') < ar_data.index('"Helmet": {'):
        fails.append("ArmorData 的 armorList 顺序应为 黑盔/铁桶/路障/铁盔/报纸/特种盔")
    if f"./Config/{ARMOR_SLOT_FILE}" not in ar_data:
        fails.append("ArmorData 里 Paper 的 slotConfig 必须指向包内 ./Config/…（相对路径）")
    if f"../Armor/{ARMOR_DATA_FILE}" not in cfg:
        fails.append("Config 里 armorData 必须是相对路径 ../Armor/…（包内自引用禁 res://）")
    if f'{ARMOR_REGISTRY_CONFIG_DIR}/{ARMOR_NAME}.tres' not in ar_data:
        fails.append("ArmorData 里 Paper 的 typeData 必须指向注册表 res://Registry/Armor/Config/Paper.tres")

    # 10. 场景：ArmorName / 脚本 / 状态机 / NodePath（需求 6 的内置链路）
    if f'currentArmor = ["{ARMOR_NAME}"]' not in sc:
        fails.append("场景 currentArmor 应为 [\"Paper\"]（出生戴着那面报纸）")
    if PAPER_SCENE_SCRIPT not in sc:
        fails.append("场景脚本应复用内置 TowerDefenseZombiePaper.cs（护具掉落 ×3 移速靠它）")
    if PAPER_STATE_MACHINE not in sc:
        fails.append("场景状态机应复用内置 TowerDefenseZombiePaperStateMachine.tres（ToGasp 转换靠它）")
    if PAPER_HITBOX not in sc:
        fails.append("场景 HitBox 应沿用内置读报僵尸的 Rect_44x70_At_4_n2.tres")
    if PAPER_DAMAGE_POINT_DATA not in cfg:
        fails.append("Config 应沿用内置读报僵尸的 DamagePointData")
    if PAPER_SPRITE_SCENE not in sp:
        fails.append("Sprite 场景应复用内置 ZombiePaper.tscn（需求 2）")
    for np in ('sprite = NodePath("SpriteGroup/TransformPoint/ZombiePaper")',
               'headSlot = NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot")',
               'duckytobeSprite = NodePath("SpriteGroup/TransformPoint/ZombiePaper/ZombieDuckytube")',
               'waterLineSprite = NodePath("SpriteGroup/TransformPoint/ZombieWaterLine")'):
        if np not in sc:
            fails.append(f"场景缺少 {np}")
    for part in ("Arm", "BlackHelmet", "Bucket", "Cone", "Head", "Helmet", "SpecialHelmet"):
        if f'"{part}": ExtResource(' not in sc:
            fails.append(f"场景 damagePart 缺 {part}")
        if f'"{part}": NodePath(' not in sc:
            fails.append(f"场景 damagePartSlot 缺 {part}")
    if '[editable path="SpriteGroup/TransformPoint/ZombiePaper"]' not in sc:
        fails.append("场景缺 [editable path=…/ZombiePaper]（往实例子树加 FireMarker 要靠它）")

    # 10b. ★★ 场景必须显式声明 ComponentSet（漏了 ⇒ 发射组件不创建 ⇒ 一颗豌豆都打不出来）
    if f'[ext_resource type="Resource" path="./{COMPONENT_SET_FILE}" id="15"]' not in sc:
        fails.append("场景必须把包内 ComponentSet 作为 ext_resource 引进来")
    if 'ComponentSet = ExtResource("15")' not in sc:
        fails.append('场景根节点必须写 ComponentSet = ExtResource("15")'
                     "（基场景那份不含 FireComponent，不覆盖就永远不打豌豆）")
    elif sc.index('ComponentSet = ExtResource("15")') > sc.index('script = ExtResource('):
        fails.append("ComponentSet 应写在 script 之前（与内置场景一致，便于人眼对照）")
    if f"./{COMPONENT_SET_FILE}" not in sc.split("[node ")[0]:
        fails.append("ComponentSet 必须是包内相对路径 ./…（包内自引用禁 res://）")

    # 11. 发射组件：Marker2D / 单条配置 / 不依赖动画
    if f'firePosMarkerPaths = [NodePath("{FIRE_MARKER_PATH}")]' not in fire:
        fails.append("FireDefinition.firePosMarkerPaths 应指向 HeadSlot/FireMarker")
    if f'[node name="FireMarker" type="Marker2D" parent="{FIRE_MARKER_PATH.rsplit("/", 1)[0]}"' not in sc:
        fails.append("场景里必须真的有一个 Marker2D 节点 FireMarker（ResolveOwnerNode<Marker2D> 只认它）")
    for bad in ("spritePath", "fireAnimeClips", "isSpliceSprite", "spliceIdleAnimeClips"):
        if f"{bad} =" in fire:
            fails.append(f"FireDefinition 不应写 {bad}（读报僵尸没有开火动画，写了指向空节点）")
    if fire.count("[sub_resource type=\"Resource\" id=\"Resource_fcfpc\"]") != 1:
        fails.append("FireDefinition 应恰好 1 条 Resource_fcfpc")
    if "fireProjectileList = [SubResource(\"Resource_fcfpc\")]" not in fire:
        fails.append("fireProjectileList 应恰好 1 条（一次 Fire() = 1 颗；插件逐颗调用才能精确 300）")
    if "fireCheckList = [SubResource(\"Resource_fcchk\")]" not in fire:
        fails.append("fireCheckList 应恰好 1 条（checkProjectileId = 0 要能索引到）")
    if f"speed = {fmt_f(PEA_SPEED)}" not in fire:
        fails.append(f"fireProjectileConfig.speed 应为 {fmt_f(PEA_SPEED)}（正数会朝反方向飞）")
    if "projectileFlip = true" not in fire:
        fails.append("fireProjectileConfig.projectileFlip 应为 true（与内置机枪豌豆僵尸一致）")
    if f'projectileName = &"{PEA_NAME}"' not in fire:
        fails.append(f"fireCheckList 的 projectileData.projectileName 应为 &\"{PEA_NAME}\"")
    if f"fireInterval = {fmt_f(FIRE_INTERVAL)}" not in fire:
        fails.append(f"fireInterval 应为 {fmt_f(FIRE_INTERVAL)}（与插件普攻周期一致，便于对照）")
    if f'fireAudioName = "{FIRE_AUDIO}"' not in fire:
        fails.append(f'fireAudioName 应为 "{FIRE_AUDIO}"（插件大招期间会临时置空静音）')
    if 'InstanceId = "character.fire"' not in fire:
        fails.append('FireDefinition.InstanceId 必须是 "character.fire"（插件靠它 GetRuntime）')
    if 'ComponentTypeId = "FireComponent"' not in fire:
        fails.append('FireDefinition.ComponentTypeId 必须是 "FireComponent"')

    # 12. 组件集：父集沿用僵尸组件集，只加发射组件（啃食沿用父集的 attackType=Eat）
    if f'ParentSet = ExtResource("2")' not in txt:
        fails.append("ComponentSet 缺 ParentSet")
    if BASE_ZOMBIE_COMPONENT_SET not in txt:
        fails.append("ComponentSet 的父集应为内置 TowerDefenseZombieComponentSet.tres")
    if 'Components = [ExtResource("1")]' not in txt:
        fails.append("ComponentSet.Components 应只含一个发射组件")
    if "attackType" in txt:
        fails.append("ComponentSet 不应覆盖 attackType（父集已是 Eat = 啃食）")
    if "InstanceId" in txt:
        fails.append("ComponentSet 不应重复声明组件 InstanceId（父集已带来 character.attack.0）")

    # 13. 卡片三闸门 + type
    for name, body in (("Card", pk_card), ("PkgPacket", pk_pkg)):
        if f'saveKey = "{CHAR_KEY}"' not in body:
            fails.append(f"{name} 的 saveKey 必须等于注册键 {CHAR_KEY}")
        if f"type = {PACKET_TYPE}" not in body:
            fails.append(f"{name} 的 type 应为 {PACKET_TYPE}(ZOMBIE)")
        if "unlockCheckList = []" not in body:
            fails.append(f"{name} 的 unlockCheckList 必须为空表（XWModContentValidation）")
        if 'characterConfig = ExtResource("1")' not in body:
            fails.append(f"{name} 缺 characterConfig 绑定")
        if "override = null" not in body:
            fails.append(f"{name} 的 override 应为 null（僵尸卡不走植物覆盖机制）")
        if f'name = "{DISPLAY_NAME}"' not in body:
            fails.append(f"{name} 的显示名应为中文「{DISPLAY_NAME}」（需求 1）")
    # 14. ★ #45 共享射击判定核心：**两问**校验（判定逻辑已抽到植物/僵尸共用源文件）
    #     (a) 入口源码里的常量必须是 `= GatlingVolleyParams.X;` 转发
    #         —— 谁把它写回字面量、或改了转发名，这里立刻报错；
    #     (b) 字面量只在 runtime_shared/GatlingVolleyCore.cs 里出现一次，
    #         必须逐个等于生成器侧记录的期望值。
    #     两问缺一不可：只看 (a) 抓不到「共用核心被人改了」，
    #     只看 (b) 抓不到「入口偷偷绕开共用核心写死了自己的数」。
    src = os.path.join(RUNTIME_SRC_DIR, "SuperGatlingPaperRuntimeEntry.cs")
    if not os.path.isfile(src):
        fails.append("缺插件源码 " + src)
    else:
        with io.open(src, "r", encoding="utf-8-sig") as f:
            cs = f.read()
        core = ""
        if not os.path.isfile(SHARED_CORE):
            fails.append("缺共用判定核心 " + SHARED_CORE)
        else:
            with io.open(SHARED_CORE, "r", encoding="utf-8-sig") as f:
                core = f.read()
        for local_name, shared_name, value in (
            ("AttackIntervalSeconds", "AttackIntervalSeconds", PLUGIN_ATTACK_INTERVAL),
            ("PeasPerAttack", "PeasPerAttack", PLUGIN_PEAS_PER_ATTACK),
            ("PeaSpacingSeconds", "PeaSpacingSeconds", PLUGIN_PEA_SPACING),
            ("UltimateChance", "UltimateChance", PLUGIN_ULTIMATE_CHANCE),
            ("UltimateSeconds", "UltimateSeconds", PLUGIN_ULTIMATE_SECONDS),
            ("UltimatePeas", "UltimatePeas", PLUGIN_ULTIMATE_PEAS),
            ("ScatterHalfAngleDeg", "ScatterHalfAngleDeg", PLUGIN_SCATTER_HALF_ANGLE),
            ("MaxPeasPerFrame", "MaxPeasPerFrame", PLUGIN_MAX_PEAS_PER_FRAME),
            ("StallThresholdMsec", "StallThresholdMsec", PLUGIN_STALL_THRESHOLD_MSEC),
        ):
            fwd = re.compile(r"const\s+\w+\s+" + local_name
                             + r"\s*=\s*GatlingVolleyParams\." + shared_name + r"\s*;")
            if not fwd.search(cs):
                fails.append(f"入口源码里的常量 {local_name} 应为"
                             f" `= GatlingVolleyParams.{shared_name};` 转发（共用核心）")
            lit = re.compile(r"const\s+\w+\s+" + shared_name + r"\s*=\s*([0-9.]+)\s*;")
            m = lit.search(core)
            if not m:
                fails.append(f"共用核心 GatlingVolleyCore.cs 里找不到常量 {shared_name} 的字面量")
            elif abs(float(m.group(1)) - float(value)) > 1e-9:
                fails.append(f"常量 {shared_name} 不一致：共用核心 = {m.group(1)}，"
                             f"生成器 = {value}")
        if f'CharacterConfigName = "{CHAR_KEY}"' not in cs:
            fails.append(f"插件源码的 CharacterConfigName 应为 {CHAR_KEY}")
        if f'FireInstanceId = "character.fire"' not in cs:
            fails.append('插件源码的 FireInstanceId 应为 "character.fire"')
        if RUNTIME_ENTRY_TYPE not in cs:
            fails.append(f"插件源码里应能搜到入口类名 {RUNTIME_ENTRY_TYPE}")

    # 15. manifest
    mf = build_manifest()
    if list(mf.keys()) != MANIFEST_KEYS:
        fails.append("manifest 键序不符")
    if set(mf["provides"]) & set(mf["overrides"]):
        fails.append("provides/overrides 键冲突")
    for cat in ("Character", "CharacterSprite", "Packet"):
        if mf["provides"].get(cat) != [CHAR_KEY]:
            fails.append(f"provides.{cat} 应为 [{CHAR_KEY}]")
    need = {
        CARD_REL,
        ARMOR_DATA_REL,
        ARMOR_SLOT_REL,
        PACKAGE_CFG_REL,
        PACKAGE_PACKET_REL,
        f"{ANIM_SKIN_REL}/{SKIN_TRES_FILE}",
        f"{ANIM_SKIN_REL}/{SKIN_DAT_FILE}",
        f"{ANIM_SKIN_REL}/{SKIN_ATLAS_FILE}",
        f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}",
        f"{PKG_REL}/Scene/{FIRE_DEF_FILE}",
        f"{PKG_REL}/Scene/{SCENE_FILE}",
        f"{PKG_REL}/Sprite/{SPRITE_FILE}",
        RUNTIME_ASSEMBLY,
    }
    if set(mf["resources"]) != need:
        fails.append(f"manifest.resources 与预期不符：差集 {set(mf['resources']) ^ need}")
    if mf["translations"] != []:
        fails.append("translations 应为空表（本包显示名直接写中文，不带翻译表）")

    # 16. ★★ 换头（需求 1/2）：皮肤镜像 + 图层/媒体表 + 属性键名 + 对位值
    #     四问缺一不可：
    #       (a) 皮肤三件套必须真的在包内且与植物包**逐字节相同**（.pmod 之间不能互引）；
    #       (b) Sprite 场景必须**相对**引用包内皮肤（不是 res://、不是植物包路径）；
    #       (c) 图层/媒体表必须**逐键**来自 .tres（表短了引擎会把可见性整表重置为全 true）；
    #       (d) 只允许官方 `Animation/*` 键名 —— 裸 clip/mediaReplace*/name_ignore 会被
    #           Godot **静默丢弃**（`.tscn` 里写了等于没写，日志里连一行错误都没有）。
    for fn in (SKIN_TRES_FILE, SKIN_DAT_FILE, SKIN_ATLAS_FILE):
        srcf = os.path.join(SKIN_SRC_DIR, fn)
        dstf = os.path.join(skin_anim_dir(), fn)
        if not os.path.isfile(srcf):
            fails.append(f"缺皮肤源 {srcf} —— 先跑 build_plant_super_gatling.py 生成植物包")
        elif not os.path.isfile(dstf):
            fails.append(f"包内缺皮肤副本 {dstf} —— 先跑本生成器（copy_skin_assets）")
        else:
            # ★ on-disk 断言：副本必须与真源逐字节相同（不是「刚生成的内存文本」）
            with open(srcf, "rb") as a, open(dstf, "rb") as b:
                if a.read() != b.read():
                    fails.append(f"包内皮肤副本与植物包真源不一致（内容漂了）：{dstf}")
    # ★★★ 节点头语法（2026-09-22 晚真踩的坑）：`[node … ]` 必须以 `]` 收尾。
    #     上一版把可见头那行写成了 `… parent="HeadHolder">`（收尾是 `>`），
    #     Godot 的 .tscn 解析器**不会**报错，只是**整行被当普通文本吞掉** ⇒
    #     那个节点根本不存在 ⇒ 头上还是旧的美术 / 插件找不到 Head（`ResolveHeadForFire` 返回 null）。
    #     ⚠️ 上一版自检之所以放行，是因为断言写的是 `… parent="HeadHolder"`（**没带闭合括号**），
    #     等于把 bug 一起写进了断言里 —— 典型「断言与实现同错」的假绿。这里改成通用扫描。
    for name, body in (("Sprite", sp), ("Scene", sc)):
        for ln in body.splitlines():
            if ln.startswith("[node ") and not ln.endswith("]"):
                fails.append(f"{name} 场景的节点头语法坏了（必须以 `]` 收尾）：{ln!r}")
    for key in ("clip", "name_ignore", "mediaReplaceAtlasPaths", "mediaReplaceUse"):
        for name, body in (("Sprite", sp), ("Scene", sc)):
            if re.search(rf"^{key} = ", body, re.M):
                fails.append(f"{name} 写了不存在的属性 `{key}`（Godot 静默丢弃 ⇒ 等于没写）")
    if f'Animation/Clip = "{HEAD_CLIP}"' not in sp:
        fails.append(f'Head 节点必须写 `Animation/Clip = "{HEAD_CLIP}"`（裸 `clip` 会被丢弃 ⇒ '
                     f"头的 _clip 留空 ⇒ ApplyFlashAnimeDataChange 兜成 clips.Keys[0] = BodyIdle 茎叶段）")
    if "res://Asset/Anime/Character/Plant" in sp:
        fails.append("Sprite 场景不得引用内置 GatlingPea.tres —— 那是「机枪射手」，"
                     "本 Mod 要的是「超级机枪射手」（包内 SuperGatlingPea.tres）")
    if head_data_rel() not in sp:
        fails.append(f"Sprite 场景应相对引用包内皮肤：{head_data_rel()}")
    lay, med_keys, clips = head_layer_names(), head_media_names(), head_clip_names()
    if HEAD_CLIP not in clips:
        fails.append(f"皮肤 .tres 里没有 clip `{HEAD_CLIP}`（只有 {clips}）")

    # ⚠️ 必须**分块**检查：身体块里有那 7 层 `= false`、影子块里有 29 层 `= false`、
    #    可见头块里有 29 层 `= true` —— 拿整份场景一次查必假红（名字都对得上，但归属错）。
    def _blk(scene_text, node_name):
        """取 `[node name="X" …]` 这一段的文本（切到下一个 `[` 行首为止）。"""
        marker = f'[node name="{node_name}"'
        if marker not in scene_text:
            return ""
        return (marker + scene_text.split(marker, 1)[1]).split("\n[", 1)[0]

    shadow_block = _blk(sp, HEAD_SHADOW_NODE_NAME)
    holder_block = _blk(sp, HEAD_HOLDER_NODE_NAME)
    head_block = _blk(sp, HEAD_NODE_NAME)
    if not shadow_block:
        fails.append(f"Sprite 场景缺 `{HEAD_SHADOW_NODE_NAME}` —— 它是可见头的**位姿来源**"
                     "（三节点结构见文件顶部 HEAD_NODE_NAME 上方那整段根因说明）")
    if not holder_block:
        fails.append(f"Sprite 场景缺 `{HEAD_HOLDER_NODE_NAME}` —— 打断「父代画」的普通容器")
    if not head_block:
        fails.append(f"Sprite 场景缺可见头 `{HEAD_NODE_NAME}`")

    # (e) ★★★ 结构硬判据：可见头**绝不能**是身体（或任何精灵）的直接子节点。
    #     直接挂身体 ⇒ `CollectOwnedChildBindings:5385` 收走 ⇒ `IsRenderedByParentSpriteForRender:9559`
    #     true ⇒ `_Draw():9534` 首行 return ⇒ 头自己的 forceLocalRender 失效
    #     ⇒ 由身体批次代画 ⇒ 自制皮肤不在全局图集 ⇒ 采样 AdobeAnimateVisualTextureArray.png
    #     ⇒ **别的角色碎片拼贴**（这正是 09-22 本次实机截图的现象）。
    if f'[node name="{HEAD_NODE_NAME}" type="Node2D" parent="{HEAD_HOLDER_NODE_NAME}"]' not in sp:
        fails.append(f"`{HEAD_NODE_NAME}` 必须挂在 `{HEAD_HOLDER_NODE_NAME}` 下"
                     "（挂到身体下 = 被父代画 = 图集错位 = 碎片拼贴）")
    if f'[node name="{HEAD_SHADOW_NODE_NAME}" type="Node2D" parent="."' not in sp:
        fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 必须是身体（Sprite 场景根）的直接子节点"
                     "（只有这样才能吃到 UpdateChild() 的每帧定位）")
    if f'[node name="{HEAD_HOLDER_NODE_NAME}" type="Node2D" parent="."' not in sp:
        fails.append(f"`{HEAD_HOLDER_NODE_NAME}` 必须是身体（Sprite 场景根）的直接子节点")
    if shadow_block and holder_block and sp.index(HEAD_SHADOW_NODE_NAME) > sp.index(HEAD_HOLDER_NODE_NAME):
        fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 应写在 `{HEAD_HOLDER_NODE_NAME}` 之前")

    # ⚠️ 下面每条都**先判 blk 非空**再取属性：节点整块缺失时 `str.index` 会抛
    #    ValueError（那会让自检自己崩掉，把「缺节点」这件真事掩盖成一次崩溃）。
    # 影子：`visible = false` + 29 层全 false + 保留 parentSprite / insertLayerId / follow…
    if shadow_block:
        if "visible = false" not in shadow_block:
            fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 必须写 `visible = false`"
                         "（它会被身体代画；29 层全 false 是阻断碎片的第二道保险）")
        if 'parentSprite = NodePath("..")' not in shadow_block:
            fails.append(f'`{HEAD_SHADOW_NODE_NAME}` 必须写 `parentSprite = NodePath("..")`'
                         "（UpdateChild 靠它 + followParentSpriteLayerId 才能定位）")
        for k, want in (("insertLayerId", HEAD_INSERT_LAYER_ID),
                        ("followParentSpriteLayerId", HEAD_FOLLOW_LAYER_ID)):
            if f"{k} = {want}" not in shadow_block:
                fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 缺 `{k} = {want}`")
        for k in lay:
            if f"Animation/LayerVisible/{k} = false" not in shadow_block:
                fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 缺 `Animation/LayerVisible/{k} = false`")

    # 可见头：29 层全 true；且**不许**出现 parentSprite/insertLayerId/follow/position/visible
    # —— 前三者会把身体重新拉回来代画它；`position` / `visible` 是「写了也会被每帧覆盖」的死值。
    # ⚠️ `rotation` 的准入**跟着 `HEAD_FIX_HEAD_ROTATE` 走**（见下面 (B) 段）：
    #    开关 True 时本包主动写固定值（同块必须有 `useRotate = false` 才生效）；
    #    开关 False 时它连同 `usePos`/`useRotate` 一起被禁 —— 引擎每帧覆写，写了是死值。
    if head_block:
        for k in lay:
            if f"Animation/LayerVisible/{k} = true" not in head_block:
                fails.append(f"可见头 `{HEAD_NODE_NAME}` 缺 `Animation/LayerVisible/{k} = true`")
        for bad in ("parentSprite", "insertLayerId", "followParentSpriteLayerId",
                    "position = Vector2", "visible = "):
            if re.search(rf"^{re.escape(bad)}", head_block, re.M):
                fails.append(f"可见头 `{HEAD_NODE_NAME}` 不该写 `{bad.strip()}`"
                             "（它必须完全脱离身体的精灵收集/渲染路径；位移由插件每帧同步）")

    # (B) ★ 头部姿态开关（用户第二轮：「摆正、不再歪斜」→ 第三轮：「回退动画」）
    #     两个头**必须永远步调一致**（它们渲染同一份美术，只有位姿来源不同）：
    #     · 开关 True  ⇒ 都必须写 `usePos = true` + `useRotate = false` + **逐字相同**的
    #                     `rotation`（`useRotate=false` 才不会被 UpdateChild 覆写 Rotation；
    #                      `usePos=true` 才继续跟 anim_head1 的位移）；
    #     · 开关 False ⇒ 都**不许**写 `useRotate` / `usePos` / `rotation`。
    #                     `rotation` 单独留着是**死值**（引擎每帧覆写）——
    #                     只会在下次改的人眼里冒充"这里有个角度在起作用"，所以一并禁掉。
    if HEAD_FIX_HEAD_ROTATE:
        want_rot = f"rotation = {HEAD_FIXED_ROT_RAD}"
        for nm, blk in ((HEAD_SHADOW_NODE_NAME, shadow_block), (HEAD_NODE_NAME, head_block)):
            if not blk:
                continue
            for k, v in (("usePos", "true"), ("useRotate", "false")):
                if f"{k} = {v}" not in blk:
                    fails.append(f"`{nm}` 缺 `{k} = {v}`"
                                 "（useRotate=false 才不会被 UpdateChild 每帧覆写 Rotation；"
                                 "usePos=true 才继续跟 anim_head1 的位移）")
            if want_rot not in blk:
                fails.append(f"`{nm}` 缺 `{want_rot}`（固定 net 旋转；两处必须逐字相同）")
        if abs(math.degrees(HEAD_FIXED_ROT_RAD) - HEAD_FIXED_ROT_DEG) > 1e-6:
            fails.append(f"HEAD_FIXED_ROT_DEG({HEAD_FIXED_ROT_DEG}) 与 "
                         f"HEAD_FIXED_ROT_RAD({HEAD_FIXED_ROT_RAD} rad) 对不上"
                         "（它们是同一角度的两种写法，必须同步改）")
        if abs(HEAD_OFFSET_ROTATE) > 1e-9:
            fails.append("HEAD_FIX_HEAD_ROTATE=True 时引擎**不读** offsetRotate"
                         f"（AdobeAnimateSprite.cs:5268-5276）⇒ HEAD_OFFSET_ROTATE "
                         f"必须保持 0（现为 {HEAD_OFFSET_ROTATE}），非零是死配置")
    else:
        for nm, blk in ((HEAD_SHADOW_NODE_NAME, shadow_block), (HEAD_NODE_NAME, head_block)):
            if not blk:
                continue
            for bad in ("useRotate", "usePos", "rotation"):
                if re.search(rf"^{re.escape(bad)} = ", blk, re.M):
                    fails.append(f"`{nm}` 写了 `{bad}`，但 HEAD_FIX_HEAD_ROTATE=False"
                                 "（引擎每帧覆写 Position/Rotation ⇒ 这三行都是死值，"
                                 "留着只会冒充「有个值在起作用」；要冻结请把开关打开）")
        # ⚠️ 跟随口径下 `offsetRotate` **是生效的**（它加在 net 旋转上），所以它不像冻结
        #    口径那样"写了等于没写"——但**本包必须保持 0**：它是头的基准倾角，
        #    一旦非零，`HEAD_OFFSET`（在 offsetRotate=0 下反解出来的）立刻失效，
        #    而自检无法察觉（几何真值在 `.cache/check_head_fit.py`）。
        #    所以这里把它钉死，逼改的人走「重解 offset + 更新金标」的正规流程。
        if abs(HEAD_OFFSET_ROTATE) > 1e-9:
            fails.append(f"跟随口径下 HEAD_OFFSET_ROTATE 必须为 0（现为 {HEAD_OFFSET_ROTATE}）"
                         "—— 它是头的基准倾角，非零会让 HEAD_OFFSET 失效；"
                         "要改请先 `python .cache/head_place.py` 重解 offset 并同步金标")

    # (B2) ★ `HEAD_PLACE_SHIFT` —— 「有意偏离纯几何对齐」的量，必须是**屏幕空间**的二元组。
    #      它本身没有"对错"，只有两件事必须成立：
    #      ① 形状合法（两个有限实数）；② 与 `HEAD_OFFSET` 一致 —— 后者由金标 + 几何门管。
    #      ⚠️ 不做「必须非零」的断言：shift=(0,0) 是合法的一档（回到纯几何对齐）。
    if (not isinstance(HEAD_PLACE_SHIFT, (tuple, list)) or len(HEAD_PLACE_SHIFT) != 2
            or not all(isinstance(v, float) and math.isfinite(v) for v in HEAD_PLACE_SHIFT)):
        fails.append(f"HEAD_PLACE_SHIFT 必须是两个有限浮点数的元组（现为 {HEAD_PLACE_SHIFT!r}）"
                     "—— 它是屏幕空间的 (dx, dy) px，y 向下（右上 = +x, −y）")

    # (C) ★ 可见头 z_index（用户：「渲染层级调高 … 避免被遮挡或出现穿插」）
    #     全局排序键第一位是 `EffectiveZIndex`（`AdobeAnimateSortPath.cs:37-48`），
    #     而它就是**沿父链累加 Godot 的 `z_index`**（`AdobeAnimateSprite.cs:6513-6531`）
    #     ⇒ 可见头写正数即保证排在身体（含报纸）之后绘制。
    # ⚠️ 这一段**不设门控**（2026-09-23 负向测试抓出来的真空洞）：
    #    早先写成 `if HEAD_NODE_Z_INDEX:`，而 `sprite_scene_tscn()` 里的 `z_lines`
    #    是**同一个门控** ⇒ 把常量改成 0，场景里 `z_index` 消失、断言也一起被跳过
    #    ⇒ 用户那条硬需求「层级调高」**可以被静默关掉且全绿**。教科书级假绿。
    #    所以：常量本身必须是正整数（无开关），场景里必须**恒有**那行。
    if not isinstance(HEAD_NODE_Z_INDEX, int) or isinstance(HEAD_NODE_Z_INDEX, bool) \
            or HEAD_NODE_Z_INDEX <= 0:
        fails.append(f"HEAD_NODE_Z_INDEX 必须是正整数（现为 {HEAD_NODE_Z_INDEX!r}）—— "
                     "用户要求头部层级高于身体，没有「关掉」这一档；"
                     "要回滚请整体回退本次改动（排序键见 AdobeAnimateSortPath.cs:37-48）")
    if head_block and not re.search(rf"^z_index = {HEAD_NODE_Z_INDEX}$", head_block, re.M):
        fails.append(f"可见头 `{HEAD_NODE_NAME}` 缺 `z_index = {HEAD_NODE_Z_INDEX}`"
                     "（排序键第一位是 ZIndex ⇒ 正数才保证压在身体与报纸之上）")
    if shadow_block and re.search(r"^z_index = ", shadow_block, re.M):
        fails.append(f"`{HEAD_SHADOW_NODE_NAME}` 不该写 z_index"
                     "（它 visible=false、零切片，写 z 无意义还会误导）")
    for k in med_keys:
        for nm, blk in ((HEAD_NODE_NAME, head_block), (HEAD_SHADOW_NODE_NAME, shadow_block)):
            if blk and f"Animation/MediaReplace/{k} = null" not in blk:
                fails.append(f"`{nm}` 缺 `Animation/MediaReplace/{k} = null`")
    # scale/offset/offsetRotate 必须逐字相同 ⇒ 可见头与影子的渲染结果**完全一致**
    # （影子的 Position/Rotation 由引擎算，可见头照抄 ⇒ 只要这三样一样，画面就一样）
    for nm, blk in ((HEAD_NODE_NAME, head_block), (HEAD_SHADOW_NODE_NAME, shadow_block)):
        if not blk:
            continue
        if f'Animation/Clip = "{HEAD_CLIP}"' not in blk:
            fails.append(f'`{nm}` 必须写 `Animation/Clip = "{HEAD_CLIP}"`'
                         "（裸 `clip` 会被 Godot 丢弃 ⇒ _clip 留空 ⇒ "
                         "ApplyFlashAnimeDataChange 兜成 clips.Keys[0] = BodyIdle 茎叶段）")
        for k, want in (("scale", f"Vector2({HEAD_SCALE[0]:g}, {HEAD_SCALE[1]:g})"),
                        ("offset", f"Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})"),
                        ("offsetRotate", f"{HEAD_OFFSET_ROTATE}")):
            if f"{k} = {want}" not in blk:
                fails.append(f"`{nm}` 的 `{k}` 应为 `{want}`（两个头必须逐字相同）")
        if "flashAnimeData = ExtResource" not in blk:
            fails.append(f"`{nm}` 缺 `flashAnimeData = ExtResource(…)`")
        elif blk.index("flashAnimeData = ExtResource") > blk.index("Animation/LayerVisible/"):
            fails.append(f"`{nm}` 的 flashAnimeData 必须写在所有 Animation/LayerVisible/* 之前"
                         "（其 setter 会先 PrepareFlashAnimeDataSerializedOverrides 把表 resize 成全 true）")
    # 反方向也要查：写多 / 拼错的名字同样会让表与 .tres 对不上
    got_lay = set(re.findall(r"^Animation/LayerVisible/(\S+) = ", head_block, re.M))
    got_med = set(re.findall(r"^Animation/MediaReplace/(\S+) = ", head_block, re.M))
    if got_lay - set(lay):
        fails.append(f"Head 节点写了 .tres 里不存在的图层名：{sorted(got_lay - set(lay))}")
    if got_med - set(med_keys):
        fails.append(f"Head 节点写了 .tres 里不存在的媒体名：{sorted(got_med - set(med_keys))}")
    if f'animeFile = "./{SKIN_DAT_FILE}"' not in _skin_tres_text():
        fails.append(f'皮肤 .tres 的 animeFile 应为 "./{SKIN_DAT_FILE}"'
                     "（standalone，必须与本 .tres 同目录，否则只 PushWarning 然后静默不画）")
    # 对位：offset 用反解值、offsetRotate 显式写 0
    # ⚠️ 下面这条只验证「模板把常量插进去了」——它**不可能**发现常量本身错了
    #    （左边和右边来自同一个变量 ⇒ 恒真）。真正的守护是再往下那条金标比对。
    if f"offset = Vector2({HEAD_OFFSET[0]}, {HEAD_OFFSET[1]})" not in sp:
        fails.append(f"Sprite 场景 Head.offset 应为 {HEAD_OFFSET}"
                     "（.cache/head_place.py 反解、check_head_fit.py 对账；"
                     "历代值 (-36,-46) / (-49.07,-5.24) / (-54.19,-10.11) 均已作废）")

    # ★★ 金标比对（非恒真）：活常量 vs **独立记录**的字面量。
    #    这是自检里唯一能抓到「HEAD_OFFSET / 平移量 / 旋转角 / z_index 被静默改动」的地方；
    #    几何真值仍归 `.cache/check_head_fit.py`（重解几何 + 正负用例）。
    for label, live, golden, tol in (
        ("HEAD_OFFSET", HEAD_OFFSET, HEAD_OFFSET_GOLDEN, 1e-9),
        ("HEAD_PLACE_SHIFT", HEAD_PLACE_SHIFT, HEAD_PLACE_SHIFT_GOLDEN, 1e-12),
        ("HEAD_FIXED_ROT_RAD", HEAD_FIXED_ROT_RAD, HEAD_FIXED_ROT_RAD_GOLDEN, 1e-12),
        ("HEAD_NODE_Z_INDEX", HEAD_NODE_Z_INDEX, HEAD_NODE_Z_INDEX_GOLDEN, 0),
        ("MUZZLE_POSE", MUZZLE_POSE, MUZZLE_POSE_GOLDEN, 1e-12),
        ("FIRE_MARKER_POS", FIRE_MARKER_POS, FIRE_MARKER_POS_GOLDEN, 1e-12),
        ("HEAD_SLOT_POS", HEAD_SLOT_POS, HEAD_SLOT_POS_GOLDEN, 1e-12),
    ):
        if isinstance(golden, tuple):
            same = len(live) == len(golden) and all(
                abs(float(a) - float(b)) <= tol for a, b in zip(live, golden))
        else:
            same = abs(float(live) - float(golden)) <= tol
        if not same:
            fails.append(f"{label} = {live} 与金标 {golden} 不符 —— "
                         "若这是有意重解出来的新值，请同时改 HEAD_*_GOLDEN，"
                         "并先跑 `python .cache/head_place.py` + `python .cache/check_head_fit.py` 核对")

    if f"offsetRotate = {HEAD_OFFSET_ROTATE}" not in sp:
        fails.append(f"Sprite 场景 Head.offsetRotate 应为 {HEAD_OFFSET_ROTATE}")
    # ⚠️ `position` 仍然禁止（`usePos = true` 时 UpdateChild 每帧覆盖，写了只是误导）；
    #    `rotation` 不再是死值 —— `useRotate = false` 下它**生效**（由上面 (B) 断言把守）。
    if re.search(r"^position = Vector2",
                 sp.split(f'[node name="{HEAD_NODE_NAME}"', 1)[-1], re.M):
        fails.append("Head 节点不该写 `position` —— usePos=true 时 UpdateChild() 每帧覆盖，"
                     "写了只是误导（要改落点请改 HEAD_OFFSET）")

    # (E) ★★★ 子弹生成点必须落在炮口上（2026-09-24 第四轮，用户：「让子弹生成位置靠左一点，
    #     对齐子弹发射口」）。机制与实测见顶部「炮口 / 子弹生成点」长注释段。
    #     本段只做**模板/常量自洽**（不需要 .tres）；真正的几何（炮口点 ↔ 生成点）
    #     由 `.cache/check_head_fit.py` 重新反解把关（含负向用例）。
    for nm, v in (("MUZZLE_POSE", MUZZLE_POSE), ("HEAD_MUZZLE_LOCAL", HEAD_MUZZLE_LOCAL),
                  ("FIRE_MARKER_POS", FIRE_MARKER_POS), ("HEAD_SLOT_POS", HEAD_SLOT_POS)):
        if (not isinstance(v, (tuple, list)) or len(v) != 2
                or not all(isinstance(q, float) and math.isfinite(q) for q in v)):
            fails.append(f"{nm} 必须是两个有限浮点数的元组（现为 {v!r}）")
    if len(HEAD_MUZZLE_LOCAL) == 2 and len(MUZZLE_POSE) == 2 and len(HEAD_OFFSET) == 2:
        want_ml = (MUZZLE_POSE[0] + HEAD_OFFSET[0], MUZZLE_POSE[1] + HEAD_OFFSET[1])
        if any(abs(a - b) > 1e-12 for a, b in zip(HEAD_MUZZLE_LOCAL, want_ml)):
            fails.append(f"HEAD_MUZZLE_LOCAL({HEAD_MUZZLE_LOCAL}) 应恒等于 "
                         f"MUZZLE_POSE + HEAD_OFFSET = {want_ml}"
                         "（插件靠这个字面量算炮口世界坐标）")
    # 场景里 FireMarker 的 position 必须是解出来的值 —— 且**不许**再是 HeadSlot 原点
    if f"position = Vector2({FIRE_MARKER_POS[0]}, {FIRE_MARKER_POS[1]})" not in sc:
        fails.append(f"Scene 场景 `FireMarker.position` 应为 {FIRE_MARKER_POS}"
                     "（.cache/_fire_marker_solve.py 反解；旧的 (0, 0) = HeadSlot 原点，"
                     "实测比真炮口偏右 6.54px、偏上 80.77px）")
    _fmb = re.search(r'\[node name="FireMarker"[^\]]*\]\nposition = Vector2\(([^)]*)\)', sc)
    if not _fmb:
        fails.append("Scene 场景里找不到 `FireMarker` 的 position")
    elif _fmb.group(1).replace(" ", "") in ("0,0", "0.0,0.0"):
        fails.append("`FireMarker.position` 仍是 HeadSlot 原点 (0, 0) ⇒ 子弹从**头顶上方**出膛"
                     "（HeadSlot 是原版护具用的静态插槽，不跟头部美术）")

    # (E2) ★★ 跨语言一致性：插件里的炮口字面量必须等于 `HEAD_MUZZLE_LOCAL`。
    #      这是**两个独立文件**之间的比对（C# 源码 vs Python 常量）⇒ 不是「同源恒真」。
    #      为什么必须把关：插件靠 `head.GlobalTransform * HeadMuzzleLocal` 算炮口世界坐标，
    #      而那个局部点随 `HEAD_OFFSET` 走 ⇒ 改了 offset 不同步插件 = 子弹又打偏（且无日志）。
    #      容差 1e-4：C# 侧写的是 `f` 后缀的 float 字面量，精度低于 Python 的 double。
    cs_entry = os.path.join(RUNTIME_SRC_DIR, "SuperGatlingPaperRuntimeEntry.cs")
    if not os.path.isfile(cs_entry):
        fails.append(f"缺插件源码 {cs_entry}")
    else:
        with io.open(cs_entry, "r", encoding="utf-8-sig") as f:
            cs_txt = f.read()
        _mm = re.search(
            r"HeadMuzzleLocal\s*=\s*new\s+Vector2\(\s*(-?[\d.]+)f?\s*,\s*(-?[\d.]+)f?\s*\)",
            cs_txt)
        if not _mm:
            fails.append("插件源码里找不到 `HeadMuzzleLocal = new Vector2(...)`"
                         "（炮口世界坐标靠它算，见 FireMarkerNodePath 注释）")
        else:
            got_cs = (float(_mm.group(1)), float(_mm.group(2)))
            if any(abs(a - b) > 1e-4 for a, b in zip(got_cs, HEAD_MUZZLE_LOCAL)):
                fails.append("插件 `HeadMuzzleLocal` = %r 与生成器 `HEAD_MUZZLE_LOCAL` = %r "
                             "不一致 —— 改 HEAD_OFFSET / 炮口点必须同步插件字面量"
                             % (got_cs, HEAD_MUZZLE_LOCAL))
        for _tok, _why in (
                ("FireMarkerNodePath", "生成点相对路径常量"),
                ("GlobalTransform * HeadMuzzleLocal", "炮口世界坐标的算法"),
                ("pair.Marker.GlobalPosition", "每帧把生成点覆写到炮口"),
                ("SyncHeadPairs", "每帧同步的那一环")):
            if _tok not in cs_txt:
                fails.append(f"插件源码缺 `{_tok}`（{_why}）")

    # 17. ★★ 需求 2 的另一半：原版僵尸的头 = 7 层，两个场景都必须显式关掉
    #     （内置 ZombiePaper.tscn 把这 7 层写死成 true，不覆写 ⇒ 原头从头盔底下透出来）
    for name, body in (("Sprite", sp), ("Scene", sc)):
        for n in BODY_HIDDEN_HEAD_LAYERS:
            if f"Animation/LayerVisible/{n} = false" not in body:
                fails.append(f"{name} 场景缺 `Animation/LayerVisible/{n} = false`")

    # 18. ★ #49 目标判定（需求 3）：没有植物不开火、还没进场不开火
    #     用 `CanFireCheckOnceByData`（不用 `CanFire`：本插件绕过状态机自建毫秒节拍，
    #     `CanFire` 多一道 `timer > 0` 会把节奏再拖一轮）。
    src2 = os.path.join(RUNTIME_SRC_DIR, "SuperGatlingPaperRuntimeEntry.cs")
    with io.open(src2, "r", encoding="utf-8-sig") as f:
        cs2 = f.read()
    for token in ("private bool HasFireTarget(", "CanFireCheckOnceByData(", "fireCheckList",
                  "HasFireTarget(", "GetProjectile("):
        if token not in cs2:
            fails.append(f"插件源码缺 `{token}`（需求 3 的射击判定）")
    if not re.search(r"if \(!HasFireTarget\([^)]*\)\)", cs2):
        fails.append("插件源码里 HasFireTarget 没有被真正调用（判定形同虚设）")
    if "CanFire(" in cs2.replace("CanFireCheckOnceByData(", "").replace("CanFireCheckOnce(", ""):
        fails.append("插件不应调用 `CanFire()` —— 它会多卡一道状态机 timer，本插件自建节拍")

    # 19. ★ 自制 .dat 皮肤 ⇒ 必须切本地 CPU 位姿渲染（否则动画静止、ESC 一次跳一帧）
    shared_render = os.path.join(WS, "runtime_shared", "AnimeSpriteLocalRender.cs")
    if not os.path.isfile(shared_render):
        fails.append(f"缺共用源 {shared_render}（自制皮肤静止问题的修法）")
    else:
        with io.open(shared_render, "r", encoding="utf-8-sig") as f:
            ar = f.read()
        for token in ("forceLocalRender", "forceCpuPoseRender", "public static int Patch(",
                      "AnimeSpriteLocalRender"):
            if token not in ar:
                fails.append(f"AnimeSpriteLocalRender.cs 缺 `{token}`")
    if "AnimeSpriteLocalRender.Patch(" not in cs2:
        fails.append("插件入口没有调用 AnimeSpriteLocalRender.Patch（皮肤会静止）")
    proj = os.path.join(RUNTIME_SRC_DIR, "SuperGatlingPaperRuntime.csproj")
    if os.path.isfile(proj):
        with io.open(proj, "r", encoding="utf-8-sig") as f:
            pj = f.read()
        for inc in ("AnimeSpriteLocalRender.cs", "GatlingVolleyCore.cs"):
            if inc not in pj:
                fails.append(f"csproj 没有 Compile Include 共用源 {inc}"
                             "（只挂一边 = 本质还是各抄一份）")

    # 20. 托管运行时四字段
    if mf["runtimeAssembly"] != RUNTIME_ASSEMBLY:
        fails.append(f"runtimeAssembly 必须是字面量 {RUNTIME_ASSEMBLY!r}（ModLoader 字符串相等判定）")
    if mf["runtimeEntryType"] != RUNTIME_ENTRY_TYPE:
        fails.append(f"runtimeEntryType 应为 {RUNTIME_ENTRY_TYPE!r}")
    if mf["runtimeApiVersion"] != 1:
        fails.append("runtimeApiVersion 必须恰好是 1")
    if mf["runtimeAssemblyPolicy"] != "optional":
        fails.append('runtimeAssemblyPolicy 应为 "optional"（加载失败不连坐角色）')
    order = [p.lower() for p in mf["resources"]]
    if order != sorted(order):
        fails.append(f"resources 不是 OrdinalIgnoreCase 升序：{mf['resources']}")
    if not os.path.isfile(_abs(RUNTIME_ASSEMBLY)):
        fails.append("缺 Runtime/ModAssembly.dll —— 先跑 python runtime_src_zombie_super_gatling/build_runtime.py --check")
    # 21. 注册键 == 卡片文件名去扩展 == saveKey
    if CARD_REL != f"Resources/Cards/{CHAR_KEY}.tres":
        fails.append("卡片注册键与 saveKey 不一致")
    # 22. 工程布局必须等于官方 XWModProjectLayout.StandardDirectories（72 项）
    if len(STANDARD_DIRS) != 72:
        fails.append(f"STANDARD_DIRS 应为 72 项（官方 XWModProjectLayout），实为 {len(STANDARD_DIRS)}")
    if len(set(STANDARD_DIRS)) != len(STANDARD_DIRS):
        fails.append("STANDARD_DIRS 有重复项")
    # 23. 角色包自引用必须是相对路径 —— 渲染进文本再查一遍
    for name, body in (("Scene", sc), ("Sprite", sp), ("Card", pk_card), ("PkgPacket", pk_pkg),
                       ("Config", cfg), ("ArmorData", ar_data)):
        for path in re.findall(r'path="([^"]+)"', body):
            if path.startswith("res://") and "/Characters/" in path:
                fails.append(f"{name} 自引用写成了游戏根下的 res://：{path}")
    return fails


def main():
    # 皮肤三件套是自检的**前置条件**（自检要按字节比对「包内副本 vs 植物包真源」），
    # 所以先同步再自检 —— 它本身是幂等的（内容相同不落盘）。
    if not os.path.isfile(skin_tres_src()):
        print(f"[FAIL] 缺皮肤源 {skin_tres_src()}")
        print("       → 先跑 build_plant_super_gatling.py 生成植物包"
              "（本包把它的皮肤三件套复制进 Resources/Animations/；.pmod 之间不能互相引用）")
        return 3
    skin_wrote = copy_skin_assets()
    if skin_wrote:
        print(f"同步皮肤资源 {skin_wrote} 个 → {ANIM_SKIN_REL}/")

    fails = self_check()
    if fails:
        print("[FAIL] 自检未通过：")
        for f in fails:
            print("   -", f)
        return 3
    print(f"自检通过：普攻 {fmt_f(PLUGIN_ATTACK_INTERVAL)}s/{PLUGIN_PEAS_PER_ATTACK} 颗（间距 "
          f"{PLUGIN_PEA_SPACING}s）· 大招 {PLUGIN_ULTIMATE_CHANCE * 100:.0f}% / "
          f"{fmt_f(PLUGIN_ULTIMATE_SECONDS)}s / {PLUGIN_ULTIMATE_PEAS} 颗 ±"
          f"{fmt_f(PLUGIN_SCATTER_HALF_ANGLE)}° · 总血 {fmt_f(HP_TOTAL)}"
          f"（{fmt_f(HITPOINTS)} + 濒死 {fmt_f(HP_NEAR_DEATH)}）· 攻击 {fmt_f(ATTACK)} 啃食 · "
          f"护具 {ARMOR_NAME} {fmt_f(ARMOR_DAMAGE_POINT)} 血 · ZOMBIE 卡 {COST} 阳光 / 冷却 "
          f"{fmt_f(PACKET_COOLDOWN)}s")

    # --- 先取回旧工程文件时间戳（幂等：不能每次写 now）
    proj_file = os.path.join(MOD_ROOT, f"{MOD_NAME}.pvzmodeproject")
    existing = None
    if os.path.isfile(proj_file):
        try:
            existing = read_json(proj_file)
        except Exception:
            existing = None

    # --- 工作区：**就地增量重建**（不做整目录 rmtree —— 本机删除钩子单次约 0.6 s）
    assert os.path.abspath(MOD_ROOT).startswith(os.path.abspath(WS) + os.sep), "MOD_ROOT 必须位于工作区内"

    # --- 构建工作区产物
    dump_json(os.path.join(MOD_ROOT, "mod.json"), build_manifest())
    write_text(_p("Config", CFG_FILE), zombie_config_tres(), "\n")
    write_text(_p("Armor", ARMOR_DATA_FILE), armor_data_tres(), "\n")
    write_text(_p("Armor", "Config", ARMOR_SLOT_FILE), armor_slot_tres(), "\n")
    write_text(_p("Scene", FIRE_DEF_FILE), fire_definition_tres(), "\n")
    write_text(_p("Scene", COMPONENT_SET_FILE), component_set_tres(), "\n")
    write_text(_p("Scene", SCENE_FILE), zombie_scene_tscn(), "\n")
    write_text(_p("Sprite", SPRITE_FILE), sprite_scene_tscn(), "\n")
    # 同一张卡分发到两处：Cards/ 是**注册**位置；包内 Packet/ 是镜像（角色包依赖，不注册）
    write_text(_abs(PACKAGE_PACKET_REL),
               packet_tres(f"../Config/{CFG_FILE}"), "\n")
    write_text(_abs(CARD_REL),
               packet_tres(f"../Characters/{PKG_CAT}/{CHAR_KEY}/Config/{CFG_FILE}"), "\n")

    ensure_project_layout(MOD_ROOT)

    write_text(proj_file, godot_json(build_project_file(existing), "\r\n"), "\n")

    # --- 清掉「这次不再产出」的旧文件（含改名前的 .pvzmodeproject / 旧卡片名）
    keep_files = set(build_manifest()["resources"])
    keep_files |= {"mod.json", f"{MOD_NAME}.pvzmodeproject"}
    stale = sweep_stale_files(MOD_ROOT, keep_files)
    if stale:
        print(f"清理旧产物 {len(stale)} 个：")
        for r in sorted(stale):
            print("   -", r)

    # --- 打包 + 安装
    os.makedirs(DIST_DIR, exist_ok=True)
    missing = [r for r in build_manifest()["resources"]
               if not os.path.isfile(os.path.join(MOD_ROOT, r.replace("/", os.sep)))]
    if missing:
        print("[FAIL] manifest.resources 指向的文件缺失：")
        for m in missing:
            print("   -", m)
        return 3
    entries = package_pmod(os.path.join(DIST_DIR, f"{MOD_NAME}.pmod"))
    os.makedirs(MODS_DIR, exist_ok=True)
    shutil.copy2(os.path.join(DIST_DIR, f"{MOD_NAME}.pmod"),
                 os.path.join(MODS_DIR, f"{MOD_NAME}.pmod"))
    mirror = install_project_dir(MOD_ROOT, os.path.join(MODS_DIR, MOD_NAME),
                                 f"{MOD_NAME}.pvzmodeproject")
    ids, dropped_ids = merge_enabled_mods(MODS_DIR, MOD_ID)
    if dropped_ids:
        print(f"⚠️ enabled_mods.json 里清掉了本 Mod 的旧 id（只差大小写的改名残留）：{dropped_ids}")
    # ⚠️ 登记 **Mods 下**那份工程（编辑器只从那里打开工程），不是工作区构建目录
    cnt = merge_recent_project(os.path.join(MODS_DIR, MOD_NAME, f"{MOD_NAME}.pvzmodeproject"))

    print(f"包内条目 {len(entries)} 个：")
    for e in entries:
        print("   ", e)
    print(f"已安装：Mods/{MOD_NAME}.pmod  +  Mods/{MOD_NAME}/（{len(STANDARD_DIRS)} 个标准目录）")
    print(f"{mirror}")
    print(f"enabled_mods.json = {ids}")
    print(f"最近工程数 = {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
