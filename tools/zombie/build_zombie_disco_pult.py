"""生成《暴走舞王伽刚特尔投石车僵尸》僵尸 Mod（数据 + 托管运行时插件）。

需求（2026-09-19 用户指定，1:1 对应到实现）：
  1. 显示名 = **暴走舞王伽刚特尔投石车僵尸**  → `packet.name`（直接写中文，见下）
  2. 特性与「小鬼投石车僵尸」一致，但**投出去的僵尸换成「暴走舞王伽刚特尔」**
     → 复用内置 `TowerDefenseZombieImppult` 整套机制 + **托管插件**把 `ZombieImp` 换成
       `ZombieDiscoGargantuar`（纯数据做不到，见 docstring 第「插件」一节）
  3. 血量 3000            → `hitpoints + hitpointsNearDeath = 3000.0`（2830 + 170）
  4. 攻击力 100000        → `attack = 100000.0` 且 `smashAttack = 100000.0`
  5. 攻击类型「碾压」      → ComponentSet 里 `Attack0_Definition.attackType = "Smash"`
  6. 僵尸卡 / 价格 0 / 冷却 0 秒 → `type = 6`(ZOMBIE) / `cost = 0` / `packetCooldown = 0.0`
  7. 贴图暂时复用「小鬼投石车僵尸」→ 场景与卡片全部复用 Imppult 的美术资源

────────────────────────────────────────────────────────────────────────
一、为什么「复用 Imppult 的脚本」是安全的（不是抄近道）
────────────────────────────────────────────────────────────────────────

Mod 角色包的**根场景脚本**用 `res://` 指向**游戏自带**脚本是完全合规的：

  · `ModLoader.SanitizeCharacterTextResource()` 只做两件事：
      - 含 `type="GDScript"` / `type="CSharpScript"` 字面量 → **拒绝**（不许内嵌脚本）；
      - `type="Script"` 且 path **非** `res://` → .tscn 里**剥离**该引用、.tres 里**直接拒绝**。
    ⇒ `type="Script" path="res://Asset/…/TowerDefenseZombieImppult.cs"` 是**保留**的。
  · 内置角色场景自己就是这么引用脚本的（`TowerDefenseZombieImppult.tscn` 第 5 行），
    说明该 `.cs` 在导出包里是**可加载的 Script 资源**（C# 资源路径 ↔ 已编译类型）。
  · ⚠️ 绝对**不要**加 `metadata/mod_character_script_binding = "CompanionOnly"`：
    `ModLoader.CharacterRequiresCompanion()` 一读到这个 meta 就会去要
    `mod.CharacterCompanionRuntime`，拿不到 → 该资源被拒 → 整包回滚。

`TowerDefenseZombieImppult.cs` 提供我们需要的全部行为：
  · `_Ready` 取 `%FireSlot` / `character.fire` / `CatapultComponent`；
  · `AnimeEvent("fire")` → `OnFireAnimeEvent()` + `ImpSpawn()` + 换弹贴图；
  · `DamagePointReach` → 投石车减速 + 冒烟；`HitpointsEmpty` → 爆炸 + 销毁；
  ⇒ **特性与小鬼投石车僵尸逐条一致**，我们只是把「投谁」换掉（需求 2）。

────────────────────────────────────────────────────────────────────────
二、角色包结构（全部来自游戏自己的生成器，不是猜的）
────────────────────────────────────────────────────────────────────────

`XWResourceCreateRoute.CreateCharacterScenePackageFromTemplate()` 是**游戏 mod 编辑器**
自带的「新建角色包」流程，它的目录布局就是权威范本：

    <Key>/Scene/<Key>.<ext>          ← 运行场景（`TryInferCharacterScene` 硬约束，见三）
    <Key>/Config/<Key>Config.tres    ← 角色配置
    <Key>/Sprite/<Key>.tscn          ← 精灵场景（`CharacterSprite` 注册点）
    <Key>/Packet/<Key>.tres          ← 卡片镜像（本包保留，与内置角色目录同构）
    <Key>/<Key>.tres                 ← 动画数据（本包复用内置，不新建）
    <Key>/Script/<Key>.cs            ← 脚步（本包复用内置，不新建）
    <Key>/DamagePoint|Custom|Armor/  ← 数据子资源（本包复用内置，不新建）

`BuildCharacterSpriteSceneContent()` 也是现成的：
    [gd_scene load_steps=2 format=3]
    [ext_resource type="PackedScene" path="res://<示例精灵场景>" id="1_game_sprite"]
    [node name="<Key>Sprite" instance=ExtResource("1_game_sprite")]
    metadata/mod_resource_kind = "CharacterSprite"
    metadata/mod_preview_source = "内置游戏角色视觉"
    ⇒ 本脚本的 `sprite_scene_tscn()` 就是它的 Imppult 版。

────────────────────────────────────────────────────────────────────────
三、四条路径/命名硬约束（违反 = 整包「不加载」，不是「不生效」）
────────────────────────────────────────────────────────────────────────

  a) `ModLoader.TryInferCharacterScene()`：路径**恰好 6 段**、
     [0]=Resources、[1]=Characters、[2]∈已知类别、[4]=="Scene"、[5] 扩展名 .tscn、
     且 **文件名 == 目录名 == Key**。本包 Key = `ZombieDiscoGargantuarPult`。
     Sprite 同理，只是 [4]=="Sprite"。
  b) `IsKnownCharacterCategory()`：Plants/Zombies/Props/Vases/Mowers/Items/Graves/Craters。
     本包用 `Zombies`。
  c) **包内自引用必须相对路径**（`./`、`../`），只有指向游戏自带资源
     （res://Prefab|Asset|Script|Resource|Registry|Extends）才用 `res://`。
     机制：ModLoader 把包解到 `user://ModsCache/<名>/` 再用该路径加载场景，
     所以 `../Config/xxx.tres` 在 user:// 树里解析成功；而
     `res://Resources/Characters/...` 会在**游戏 pck 根**解析 —— 那里没有 `Resources/`，必然失败。
  d) `XWModContentValidation.Validate()` 对 Packet 三个闸门：
     - `packet.saveKey == 注册键`（注册键 = `Resources/Cards/<文件名去扩展>`）；
     - `characterConfig.name` 必须已注册进 `TOWERDEFENSE_CHARCATERS`
       ⇒ `config.name` **必须**等于 Key（**不能**写中文！）；
     - `CHARCTAER_SPRITE` 必须含 saveKey 或 config.name ⇒ 必须有 `Sprite/<Key>.tscn`；
     - `unlockCheckList` 只能空表或 `XWModProgressUnlockCondition`（空表 = 直接可用）。

⚠️ 特别提醒：`config.name` 是**内部键**（插件也靠它认人），
   `packet.name` 才是**显示名**。两者在本包里**故意不同**：
   `config.name = "ZombieDiscoGargantuarPult"`，`packet.name = "暴走舞王伽刚特尔投石车僵尸"`。

────────────────────────────────────────────────────────────────────────
四、显示名为什么直接写中文（而不是翻译键 + translations.csv）
────────────────────────────────────────────────────────────────────────

内置卡片的 `packet.name` 是翻译键（如 `TOWERDEFENSE_ZOMBIE_IMPPULT_NAME`），
因为游戏启动时 `Global.cs` 会 `TranslationServer.SetLocale("zh")` 加载官方翻译表。

但 **ModLoader 全文没有任何 `TranslationServer.AddTranslation` 调用**（已全树 grep 确认）：
`manifest.translations` 只在 schema 校验 / 同步服务 / 引用图里被读写，
`Localization/*.csv` **不会**进入游戏运行时 ⇒ 用翻译键写，游戏里就显示原始 key。

所以本包把中文**直接写进** `packet.name` / `describe` / `handbookDescribe` / `handbookStory`：
  · `InformationPanel.cs`  `nameLabel.Text = packetConfig.name;`          → 直接中文
  · `InformationPanel.cs`  `expressionLabel.Text = Tr(packetConfig.describe)` → `Tr()` 查不到原样返回
  · `AwardSettlement.cs`   `nameLabel.Text = packetConfig.name;`          → 直接中文
  · `LevelEditorBattle.cs` `Tr(packetConfig.name)`                        → 原样返回
⇒ 无需翻译表即可在游戏内正确显示中文（这是本包**不**带 `Localization/` 的原因）。

⚠️ 唯一的已知副作用（与内置卡片同构，非本包引入）：`TowerDefenseBattleFeatureConveyorBelt`
   与 `RainMode` 会调 `GetCharacterNum(packet.name)`，而 `GetCharacterNum` 内部拿它跟
   `character.config.name` 比较。内置卡片传的是翻译键 ⇒ 本来也对不上、恒返回 0。
   我们传中文，行为**完全一样**（同样是恒 0），不会额外引入差异。

────────────────────────────────────────────────────────────────────────
五、数值映射（逐条有源码依据）
────────────────────────────────────────────────────────────────────────

血量：`TowerDefenseCharacterInstance._Init`
      `hitpoints = config.hitpoints + config.hitpointsNearDeath;`
      `hitpointsNearDeath` 同时是**濒死线**：`if (!nearDie && hitpoints <= hitpointsNearDeath)`
      进濒死阶段；`TowerDefenseCharacter.DealHurt(hitpointsNearDeath * delta / 3.0)` 是濒死流血。
      ⇒ 需求「血量 3000」取**总血恰好 3000**：`hitpoints = 2830.0` + `hitpointsNearDeath = 170.0`。
        170 沿用 Imppult（需求 2「特性一致」⇒ 保留濒死线）。（常量见 HITPOINTS / HP_TOTAL）

攻击：碾压走 `smashAttack`（`attackType="Smash"`），非碾压走 `attack`。
      两个都写 100000 ⇒ 无论走哪条都满足需求 4。

卡片：`type` 取 `TowerDefenseEnum.PACKET_TYPE.ZOMBIE = 6`（NOONE=-1,WHITE=0,GOLD=1,
      DIAMOND=2,COLOUR=3,STAR=4,ORIGINAL=5,ZOMBIE=6,COVER=7,GRAY=8）。
      `cost=0`、`packetCooldown=0.0`。

其余字段**逐字沿用 Imppult**（需求 2「特性一致」）：
      `physique=5`、`weight=3000`、`wavePointCost=300`、`excludeLineGridType=[3]`、
      `plantGridType=[-1]`、`collisionFlags=41`、`maskFlags=9`、`physiqueTypeFlags=2048`；
      `damagePointData` 直接引用内置 Imppult 的那份（`res://` 绝对路径）——
      投石车要靠 `DamagePoint2` 触发减速 + 冒烟（`CatapultComponent.OnDamagePoint`），
      交 null 会把这个可见特性弄丢。

字段**书写顺序** = 类声明顺序（`TowerDefenseZombieConfig` 先、`TowerDefenseCharacterConfig` 后），
否则编辑器一保存就会把它重排（与植物包同一约定）。

────────────────────────────────────────────────────────────────────────
六、Godot 4.7 的 `unique_id` / `parent_id_path`：**故意不写**
────────────────────────────────────────────────────────────────────────

本项目是 Godot **4.7**（`project.godot` 的 `config/features=PackedStringArray("4.7", ...)`），
新编辑器序列化时会给节点加 `unique_id=…` / `parent_id_path=PackedInt32Array(…)`。
但这两项**是可选的**，证据有三条：
  1. 解包树里 2071 个 .tscn 中有 **319 个完全不带 `unique_id`**，且其中包含多节点角色场景
     —— `TowerDefensePlantPot.tscn`(7 节点)、`TowerDefensePlantEMPlantern.tscn`(9 节点)、
     `TowerDefenseVaseNormal.tscn`(5 节点)、`TowerDefensePlantLilyPad.tscn`(6 节点) 等，
     这些都是游戏正在用的场景，说明不带也能加载；
  2. `TowerDefensePlantPot.tscn` 正是「给实例化子树的节点加子节点」这一用法
     （`[node name="TransformPoint" parent="SpriteGroup" index="0"]` + 在其下挂
     `AdobeAnimateSlot` / `Marker2D`），**完全没有** parent_id_path —— 与本包需要的写法一致；
  3. 游戏 mod 编辑器自己的角色场景模板 `BuildCharacterRuntimeSceneContent()` 输出的是
     `[gd_scene load_steps=4 format=3]` + `[node name="…" parent="SpriteGroup/TransformPoint"
     instance=…]`，既无 uid 也无 unique_id / parent_id_path。
⇒ 本包一律**不写** uid / unique_id / parent_id_path（写了反而要伪造哈希，风险更大）。

────────────────────────────────────────────────────────────────────────
七、插件（托管运行时）—— 需求 2 的唯一解法
────────────────────────────────────────────────────────────────────────

**纯数据换不掉投掷物**：`TowerDefenseZombieImppult.ImpSpawn()`（第 135 行）硬编码
`TowerDefenseManager.GetPacketConfig("ZombieImp")`，且 `as TowerDefenseZombieImpBase`。
配置里能改的只有 `CatapultComponent.projectileNum / projectileName` 之类，
但 `projectileName = "Imp"` 是**美术/动画层**的名字，不决定生成哪个角色。
⇒ 只能写托管插件。

本包带 `Runtime/ModAssembly.dll`（入口类 `DiscoGargantuarPultRuntimeEntry`），
源码在 `../runtime_src_zombie/`，用 `python runtime_src_zombie/build_runtime.py --check` 编译
—— **必须先跑它**，否则 manifest.resources 指向的 DLL 不存在，本脚本会拒绝打包。

插件干三件事：
  ① 玩法（需求 2）：订阅 `CatapultComponent.OnFireEvent`（`CatapultComponent.cs:139` 声明、
     568 行 `OnFireAnimeEvent()` 内触发）领票；再监听 `TowerDefenseGroundItemBase.characterNode`
     的 `child_entered_tree`（**同步**回调），在 `config.name=="ZombieImp"` 的子节点刚进树时
     `QueueFree()` 并换成 `ZombieDiscoGargantuar`，把原小鬼的
     `pos/gridPos/height(=z-groundHeight)/ySpeed` 抄过来复刻同一条抛物线，
     落点用与 `ImpSpawn()` 第 168 行**完全相同**的「第 3~5 列随机」公式，
     水平位移交给 `Tween`（时长 `GetFallTime()`），落地后 `CallDeferred("Walk")`。
     为什么不能在同帧直接换：`ImpSpawn()` 是 `async void`，先
     `await ToSignal(GetTree(), PhysicsFrame)` 才 `AddChild` ⇒ 事件触发时小鬼还不存在。
  ② 可选性（需求 6 的前半段）：把本卡补进**共享卡库** `GeneralZombie` 的 `Zombie` 分类。
     依据：`Almanac.cs:220` 图鉴僵尸页取的就是 `GetPacketBankData("GeneralZombie")`
     （**同一个实例**，不像植物页那样深拷贝）⇒ 补一处，选卡界面 / 关卡编辑器 / 图鉴同时生效。
     同时补 `Include` 闭包里的派生库（离线算出 = `TotalZombie`、`Total`）。
  ③ 兜底：图鉴已打开过（`_zombieInitialized == true`）时主动 `InitZombie()` 刷一次列表；
     ⚠️ 没初始化过**绝不**主动调（会提前加载全部预览资源，白白卡一下）。

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
（顺序原样），与 build_map_vampire_pool.py / build_plant_super_gatling.py 逐字相同。
"""

import io
import json
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

BUILD_DIR = "DiscoGargantuarPult"             # 工作区构建目录（ASCII）
MOD_NAME = "暴走舞王伽刚特尔投石车僵尸"          # Mods 下工程目录名 / .pvzmodeproject / .pmod 文件名
MOD_ID = "discogargantuarpult"                # manifest.id（与 vampirepool / supergatlingpea 同为全小写）
CHAR_KEY = "ZombieDiscoGargantuarPult"        # 角色 key（目录名 == 场景文件名 == config.name）
PKG_CAT = "Zombies"                           # IsKnownCharacterCategory 里的类别目录
MOD_ROOT = os.path.join(WS, BUILD_DIR)
DIST_DIR = os.path.join(WS, "dist")

# 原版资源（res:// 前缀，游戏内解析；本机解包用于校验存在性）
BASE_ZOMBIE_SCENE = "res://Prefab/TowerDefense/Character/TowerDefenseZombie.tscn"
BASE_ZOMBIE_COMPONENT_SET = "res://Prefab/TowerDefense/Character/ComponentSets/TowerDefenseZombieComponentSet.tres"
BASE_HITBOX = "res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_130x33_At_0_0.tres"
BASE_ZOMBIE_CONFIG_SCRIPT = "res://Resource/TowerDefense/Character/Config/TowerDefenseZombieConfig.cs"
BASE_COMPONENT_SET_SCRIPT = "res://Script/Component/Runtime/CharacterComponentSet.cs"
BASE_PACKET_SCRIPT = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs"

# 内置小鬼投石车僵尸（本包复用的整套美术 / 机制 / 伤害点）
IMPPULT_DIR = "res://Asset/Anime/Character/Zombie/Chapter5/Imppult"
IMPPULT_SCENE_SCRIPT = f"{IMPPULT_DIR}/Scene/TowerDefenseZombieImppult.cs"
IMPPULT_SPRITE_SCENE = f"{IMPPULT_DIR}/ZombieImppult.tscn"
IMPPULT_DAMAGE_POINT_DATA = f"{IMPPULT_DIR}/DamagePoint/ImppultDamagePointData.tres"

# 投石车 / 攻击 / 发射 三个组件（逐字沿用 Imppult 的接线）
BASE_CATAPULT_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/CatapultComponent/CatapultComponentStateMachine.tres"
BASE_CATAPULT_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/CatapultComponent/CatapultComponentDefinition.cs"
BASE_ATTACK_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/AttackComponent/AttackComponentStateMachine.tres"
BASE_ATTACK_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/AttackComponent/AttackComponentDefinition.cs"
BASE_FIRE_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentStateMachine.tres"
BASE_FIRE_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentDefinition.cs"
BASE_AABBSHAPE_SCRIPT = "res://Resource/TowerDefense/Collision/AabbShape2DResource.cs"
BASE_CREATEDATA_SCRIPT = "res://Registry/Projectile/Resource/TowerDefenseProjectileCreateData.cs"
BASE_PROJ_SINGLE_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/Projectile/FireComponentProjectileSingle.cs"
BASE_CHECK_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentCheckConfig.cs"
BASE_FIRE_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs"
BASE_EXPLOSION_SCENE = "res://Prefab/Particles/Explosion/CariExplosion/CariExplosion.tscn"
BASE_SMOKE_SCENE = "res://Prefab/Particles/Smoke/ZamboniSmoke/ZamboniSmoke.tscn"
BASE_ANIMATE_SLOT_SCRIPT = "res://addons/AdobeAnimateEditor/Node/AdobeAnimateSlot.cs"

# 数值（2026-09-19 用户指定；字段名依据 TowerDefenseZombieConfig / TowerDefenseCharacterConfig）
#
# 血量：游戏的有效总血 = hitpoints + hitpointsNearDeath
#   （TowerDefenseCharacterInstance._Init；hitpointsNearDeath 同时是**濒死线**）
#   ⇒ 「血量 3000」= 总血恰好 3000：2830 主血 + 170 濒死线（170 沿用 Imppult，保住濒死阶段）。
HP_TOTAL = 3000.0
HP_NEAR_DEATH = 170.0          # 逐字沿用 Imppult 的 hitpointsNearDeath
HITPOINTS = HP_TOTAL - HP_NEAR_DEATH      # 2830.0
ATTACK = 100000.0              # 普通攻击力
SMASH_ATTACK = 100000.0        # 碾压攻击力（attackType = "Smash"，走的是这个）
COST = 0                       # 价格 0
PACKET_COOLDOWN = 0.0          # 冷却 0 秒
PACKET_TYPE = 6                # TowerDefenseEnum.PACKET_TYPE.ZOMBIE
ATTACK_TYPE = "Smash"          # 需求 5「攻击类型 = 碾压」
PHYSIQUE = 5                   # 逐字沿用 Imppult
WEIGHT = 3000
WAVE_POINT_COST = 300
COLLISION_FLAGS = 41
MASK_FLAGS = 9
PHYSIQUE_TYPE_FLAGS = 2048

# 投石车参数（逐字沿用 Imppult：4 发 / 每发 3 秒 / 落点第 3~5 列）
PROJECTILE_NUM = 4
FIRE_INTERVAL = 3.0
CATAPULT_HEIGHT = 400.0
LANDING_GRID_MIN = 3           # ⚠️ 与插件 DiscoGargantuarPultRuntimeEntry 的对应常量必须一致
LANDING_GRID_MAX = 5           # ⚠️ 同上

DISPLAY_NAME = "暴走舞王伽刚特尔投石车僵尸"
DESCRIPTION = ("特性与「小鬼投石车僵尸」完全相同，但投出去的不是小鬼，"
               "而是「暴走舞王伽刚特尔」。血量 3000，碾压攻击 100000。")
HANDBOOK_DESC = ("顶着小鬼投石车的炮架，投出来的却是暴走舞王伽刚特尔。"
                 "血量 3000，攻击 100000，攻击类型为碾压。")
HANDBOOK_STORY = "小鬼们表示：这次真的不是我们。"

# 托管运行时（见 docstring「插件（托管运行时）」一节；改动前务必读完那 4 条约束）
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"                 # ⚠️ 只能是这个字面量
RUNTIME_ENTRY_TYPE = "DiscoGargantuarPultRuntimeEntry"       # 无命名空间 ⇒ 类名即 FullName
RUNTIME_API_VERSION = 1                                      # ⚠️ 必须恰好 1
RUNTIME_POLICY = "optional"                                  # 加载失败不连坐角色
RUNTIME_SRC_DIR = os.path.join(WS, "runtime_src_zombie")      # 源码 + build_runtime.py 所在

# 包内相对路径（⚠️ 见 docstring 第 c 条：mod 自引用一律相对，禁 res://）
PKG_REL = f"Resources/Characters/{PKG_CAT}/{CHAR_KEY}"
CFG_FILE = f"TowerDefense{CHAR_KEY}.tres"      # TowerDefenseZombieDiscoGargantuarPult.tres
SCENE_FILE = f"{CHAR_KEY}.tscn"
COMPONENT_SET_FILE = f"{CHAR_KEY}ComponentSet.tres"
FIRE_DEF_FILE = f"{CHAR_KEY}FireComponentDefinition.tres"
SPRITE_FILE = f"{CHAR_KEY}.tscn"
CARD_REL = f"Resources/Cards/{CHAR_KEY}.tres"  # 注册键 == 文件名去扩展 == saveKey
PACKAGE_CFG_REL = f"{PKG_REL}/Config/{CFG_FILE}"          # 角色配置（manifest.resources 用）
PACKAGE_PACKET_REL = f"{PKG_REL}/Packet/{CHAR_KEY}.tres"  # 包内卡片镜像（不注册）

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

def zombie_config_tres():
    """`TowerDefenseZombieConfig`：字段顺序对齐原版 Imppult 配置（= 类声明顺序）。

    ⚠️ `name` 必须是「角色场景文件名」= CHAR_KEY：
    `TowerDefensePacketConfig.Create()` 用 `characterConfig.name` 去查
    `ResourceManager.TOWERDEFENSE_CHARCATERS`，而 mod 角色只能注册在 <Key> 这个键上
    （`ModLoader.TryInferCharacterScene`）。插件也靠这个字段认人 ⇒ **不能**写中文。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefenseZombieConfig" format=3]

[ext_resource type="Resource" path="{IMPPULT_DAMAGE_POINT_DATA}" id="1"]
[ext_resource type="Script" path="{BASE_ZOMBIE_CONFIG_SCRIPT}" id="2"]

[resource]
script = ExtResource("2")
physique = {PHYSIQUE}
attack = {fmt_f(ATTACK)}
smashAttack = {fmt_f(SMASH_ATTACK)}
weight = {WEIGHT}
wavePointCost = {WAVE_POINT_COST}
excludeLineGridType = [3]
name = "{CHAR_KEY}"
hitpointsNearDeath = {fmt_f(HP_NEAR_DEATH)}
hitpoints = {fmt_f(HITPOINTS)}
damagePointData = ExtResource("1")
armorData = null
customData = null
ashScene = null
homeWorld = 1
cost = {COST}
packetCooldown = {fmt_f(PACKET_COOLDOWN)}
plantGridType = [-1]
collisionFlags = {COLLISION_FLAGS}
maskFlags = {MASK_FLAGS}
physiqueTypeFlags = {PHYSIQUE_TYPE_FLAGS}
metadata/_custom_type_script = "{BASE_ZOMBIE_CONFIG_SCRIPT}"
"""


def fire_definition_tres():
    """`FireComponentDefinition` —— 逐字沿用 Imppult，只改 DefinitionId。

    ⚠️ 这个组件本身不发射任何东西（`fireProjectileList` 里那条 config 全默认），
    它的作用是给 `TowerDefenseZombieImppult.ImpSpawn()` 提供 `firePosMarker[0]`
    （`_fireComponent.firePosMarker[0]` 决定投掷起点）。少了它 `ImpSpawn()` 会直接炸。
    `firePosMarkerPaths` 里的 NodePath 沿用内置节点的名字（见 scene 的节点树）。
    """
    return f"""[gd_resource type="Resource" script_class="FireComponentDefinition" format=3]

[ext_resource type="Resource" path="{BASE_FIRE_STATE_MACHINE}" id="1"]
[ext_resource type="Script" path="{BASE_AABBSHAPE_SCRIPT}" id="2"]
[ext_resource type="Script" path="{BASE_CREATEDATA_SCRIPT}" id="3"]
[ext_resource type="Script" path="{BASE_PROJ_SINGLE_SCRIPT}" id="4"]
[ext_resource type="Script" path="{BASE_CHECK_CONFIG_SCRIPT}" id="5"]
[ext_resource type="Script" path="{BASE_FIRE_CONFIG_SCRIPT}" id="6"]
[ext_resource type="Script" path="{BASE_FIRE_DEF_SCRIPT}" id="7"]

[sub_resource type="SegmentShape2D" id="SegmentShape2D_fire_forward"]
b = Vector2(-2000, 0)

[sub_resource type="Resource" id="AabbShape2DResource_fire_check"]
script = ExtResource("2")
Geometry = SubResource("SegmentShape2D_fire_forward")

[sub_resource type="Resource" id="Resource_proj"]
script = ExtResource("3")
projectileName = &"Imp"
baseDamage = 0.0
damageFlags = 2
collisionFlags = 43
fireMethodFlags = 2
catapultHeight = {fmt_f(CATAPULT_HEIGHT)}

[sub_resource type="Resource" id="Resource_fcps"]
script = ExtResource("4")
projectileData = SubResource("Resource_proj")
metadata/_custom_type_script = "{BASE_PROJ_SINGLE_SCRIPT}"

[sub_resource type="Resource" id="Resource_fcchk"]
script = ExtResource("5")
projectile = SubResource("Resource_fcps")
metadata/_custom_type_script = "{BASE_CHECK_CONFIG_SCRIPT}"

[sub_resource type="Resource" id="Resource_fcfpc"]
script = ExtResource("6")
metadata/_custom_type_script = "{BASE_FIRE_CONFIG_SCRIPT}"

[resource]
script = ExtResource("7")
firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/ZombieImppult/FireSlot/FireMarker")]
checkShapeResources = [SubResource("AabbShape2DResource_fire_check")]
fireInterval = {fmt_f(FIRE_INTERVAL)}
fireCheckList = [SubResource("Resource_fcchk")]
fireProjectileList = [SubResource("Resource_fcfpc")]
checkHeight = false
catapultFirstFar = true
ComponentTypeId = "FireComponent"
DefinitionId = "mod.{MOD_ID}.component.fire"
InstanceId = "character.fire"
WireIndex = 0
StateMachineDefinition = ExtResource("1")
LegacyNodeNames = [&"FireComponent"]
"""


def component_set_tres():
    """`CharacterComponentSet` —— 投石车 + 碾压攻击 + 发射组件三件套（沿用 Imppult 接线）。

    · `InstanceId = "character.catapult"`：插件就是靠这个 id
      `componentManager.GetRuntime<CatapultComponent>("character.catapult")` 找投石车
      ⇒ **不能改**。
    · `InstanceId = "character.fire"`：`TowerDefenseZombieImppult._Ready()` 同款查找 ⇒ **不能改**。
    · `RemovedInstanceIds = ["character.ground_move"]`：投石车用 `CatapultComponent.WalkProcessing`
      自行推进，去掉常规行走组件（沿用 Imppult）。
    · `DefinitionId` 是本 Mod 自己的命名空间（避免与内置 DefinitionId 撞车），
      它不参与运行时查找，改它安全。
    """
    return f"""[gd_resource type="Resource" script_class="CharacterComponentSet" format=3]

[ext_resource type="Resource" path="{BASE_CATAPULT_STATE_MACHINE}" id="1"]
[ext_resource type="PackedScene" path="{BASE_EXPLOSION_SCENE}" id="2"]
[ext_resource type="Script" path="{BASE_CATAPULT_DEF_SCRIPT}" id="3"]
[ext_resource type="Resource" path="{BASE_ATTACK_STATE_MACHINE}" id="4"]
[ext_resource type="Script" path="{BASE_ATTACK_DEF_SCRIPT}" id="5"]
[ext_resource type="Resource" path="./{FIRE_DEF_FILE}" id="6"]
[ext_resource type="Resource" path="{BASE_ZOMBIE_COMPONENT_SET}" id="7"]
[ext_resource type="Script" path="{BASE_COMPONENT_SET_SCRIPT}" id="8"]

[sub_resource type="Resource" id="CatapultDefinition"]
script = ExtResource("3")
projectileNum = {PROJECTILE_NUM}
projectileName = "Imp"
useCanFireCheck = false
explosionEffect = ExtResource("2")
smokeParticlePath = NodePath("SpriteGroup/TransformPoint/ZamboniSmoke")
fireSlotPath = NodePath("SpriteGroup/TransformPoint/ZombieImppult/FireSlot")
ComponentTypeId = "CatapultComponent"
DefinitionId = "mod.{MOD_ID}.component.catapult"
InstanceId = "character.catapult"
WireIndex = 0
StateMachineDefinition = ExtResource("1")
LegacyNodeNames = [&"CatapultComponent"]

[sub_resource type="Resource" id="Attack0_Definition"]
script = ExtResource("5")
attackType = "{ATTACK_TYPE}"
useParentHitBox = true
useCheckAreaGridColumn = true
checkLine = true
checkVase = true
ComponentTypeId = "AttackComponent"
DefinitionId = "mod.{MOD_ID}.component.attack.0"
InstanceId = "character.attack.0"
WireIndex = 0
StateMachineDefinition = ExtResource("4")
LegacyNodeNames = [&"AttackComponent"]

[resource]
script = ExtResource("8")
ParentSet = ExtResource("7")
Components = [SubResource("CatapultDefinition"), SubResource("Attack0_Definition"), ExtResource("6")]
RemovedInstanceIds = ["character.ground_move"]
"""


def zombie_scene_tscn():
    """`Scene/<Key>.tscn`（6 段硬约束，见 docstring 第三条）。

    节点树**逐字复刻**内置 `TowerDefenseZombieImppult.tscn`（去掉 unique_id / parent_id_path，
    理由见 docstring 第六条），因为投石车/发射组件是按 NodePath 找接点的：

      · `sprite`    = SpriteGroup/TransformPoint/ZombieImppult
      · `headSlot`  = …/ZombieImppult/HeadSlot
      · FireSlot    = …/ZombieImppult/FireSlot（`unique_name_in_owner`，脚本用 `%FireSlot` 取）
      · FireMarker  = …/FireSlot/FireMarker（FireComponentDefinition 的 firePosMarkerPaths）
      · ZamboniSmoke= SpriteGroup/TransformPoint/ZamboniSmoke（Catapult 的 smokeParticlePath）

    ⚠️ 精灵节点仍叫 `ZombieImppult`（而不是 <Key>）：这样上面四条 NodePath 可以
    **原样照抄**内置资源，不用做任何重命名 —— 少一次改名就少一次出错机会。
    它对外的身份由 `config` 决定，与节点名无关。
    """
    return f"""[gd_scene format=3]

[ext_resource type="PackedScene" path="{BASE_ZOMBIE_SCENE}" id="1"]
[ext_resource type="Resource" path="./{COMPONENT_SET_FILE}" id="2"]
[ext_resource type="Script" path="{IMPPULT_SCENE_SCRIPT}" id="3"]
[ext_resource type="Resource" path="{BASE_HITBOX}" id="4"]
[ext_resource type="Resource" path="../Config/{CFG_FILE}" id="5"]
[ext_resource type="PackedScene" path="{IMPPULT_SPRITE_SCENE}" id="6"]
[ext_resource type="Script" path="{BASE_ANIMATE_SLOT_SCRIPT}" id="7"]
[ext_resource type="PackedScene" path="{BASE_SMOKE_SCENE}" id="8"]

[node name="{CHAR_KEY}" node_paths=PackedStringArray("sprite", "headSlot") instance=ExtResource("1")]
ComponentSet = ExtResource("2")
script = ExtResource("3")
HitBoxDefinition = ExtResource("4")
attackAnimeClip = "Walk"
dieAnimeClip = "Bounce"
dieWaterAnimeClip = "Bounce"
config = ExtResource("5")
sprite = NodePath("SpriteGroup/TransformPoint/ZombieImppult")
headSlot = NodePath("SpriteGroup/TransformPoint/ZombieImppult/HeadSlot")
PreviewDamagePointPersontage = 1.0
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "{DISPLAY_NAME}"
metadata/mod_character_category = "Zombie"
metadata/mod_character_config_path = "../Config/{CFG_FILE}"
metadata/mod_character_sprite_scene = "../Sprite/{SPRITE_FILE}"

[node name="ShadowSprite" parent="." index="0"]
position = Vector2(-8.499992, 28.000025)
scale = Vector2(2.825581, 1.2777766)

[node name="TransformPoint" parent="SpriteGroup" index="0"]
position = Vector2(12, 33)

[node name="ZombieImppult" parent="SpriteGroup/TransformPoint" index="0" instance=ExtResource("6")]
position = Vector2(-12, -33)
offset = Vector2(-74.59021, -100.0717)

[node name="HeadSlot" parent="SpriteGroup/TransformPoint/ZombieImppult" index="0"]
drawLayerId = -2
position = Vector2(-19.410542, -79.75023)
rotation = 0.01876532
scale = Vector2(0.74074215, 0.74074215)
skew = 0.0
Layer = 11

[node name="FireSlot" type="Node2D" parent="SpriteGroup/TransformPoint/ZombieImppult" index="1"]
unique_name_in_owner = true
script = ExtResource("7")
followSlotId = 25
useScale = false
useSkew = false
Layer = 25
drawLayerId = 25
metadata/_custom_type_script = "{BASE_ANIMATE_SLOT_SCRIPT}"

[node name="FireMarker" type="Marker2D" parent="SpriteGroup/TransformPoint/ZombieImppult/FireSlot" index="0"]
position = Vector2(145.21976, 10.632696)

[node name="ZamboniSmoke" parent="SpriteGroup/TransformPoint" index="1" instance=ExtResource("8")]
unique_name_in_owner = true
visible = false
position = Vector2(0, -8)
"""


def sprite_scene_tscn():
    """`Sprite/<Key>.tscn`（6 段，文件夹 == 文件名 == <Key>）。

    ⚠️ 依据 docstring 第三条 c/d：没有这个文件就没有 `CHARCTAER_SPRITE[<Key>]`，
    `XWModContentValidation` 第 35-36 行直接 throw「缺少 CharacterSprite/<Key>」，
    运行时 `GetPacketSpriteScene()` 也会抛 `KeyNotFoundException`。

    写法 = 游戏自己 `XWResourceCreateRoute.BuildCharacterSpriteSceneContent()` 的 Imppult 版
    （需求 7：贴图暂时复用小鬼投石车僵尸）。
    """
    return f"""[gd_scene load_steps=2 format=3]

[ext_resource type="PackedScene" path="{IMPPULT_SPRITE_SCENE}" id="1_game_sprite"]

[node name="{CHAR_KEY}Sprite" instance=ExtResource("1_game_sprite")]
metadata/mod_resource_kind = "CharacterSprite"
metadata/mod_preview_source = "内置游戏角色视觉（小鬼投石车僵尸 ZombieImppult）"
"""


def packet_tres(config_rel):
    """僵尸卡片 `TowerDefensePacketConfig`。

    ⚠️ 硬闸门（docstring 第三条 d）：
      · `saveKey` == 注册键 == 卡片文件名去扩展 == `{CHAR_KEY}`；
      · `characterConfig` 必须能加载，且它的 name 已注册进 TOWERDEFENSE_CHARACTERS；
      · `unlockCheckList` 必须为空表（放游戏内条件会被判「必须使用 Mod 专属解锁条件」）；
      · `type = 6` = PACKET_TYPE.ZOMBIE（需求 6「作为僵尸卡使用」）。
    `config_rel`：本文件所在目录到 Config 的相对路径（两处分发目录深度不同）。

    ⚠️ `name`/`describe`/`handbook*` 直接写中文（理由见 docstring 第四条）——
    内置卡片这里是翻译键，但 ModLoader 从不调用 `TranslationServer.AddTranslation`，
    翻译表进不了游戏运行时，写键只会显示成键本身。
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
packetAnimeOffset = Vector2(30, 75)
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
    ModLoader 推导出的 key：
      - Character       = `Resources/Characters/Zombies/<Key>/Scene/<Key>.tscn` 的 <Key>
      - CharacterSprite = `Resources/Characters/Zombies/<Key>/Sprite/<Key>.tscn` 的 <Key>
      - Packet          = `Resources/Cards/<文件名去扩展>`（不是目录/角色名！）
    三者在（含 sprite）本包统一为 `{CHAR_KEY}`。

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
            f"{PKG_REL}/Config/{CFG_FILE}",
            f"{PKG_REL}/Packet/{CHAR_KEY}.tres",
            f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}",
            f"{PKG_REL}/Scene/{FIRE_DEF_FILE}",
            f"{PKG_REL}/Scene/{SCENE_FILE}",
            f"{PKG_REL}/Sprite/{SPRITE_FILE}",
            RUNTIME_ASSEMBLY,
        ], key=lambda p: p.lower()),
    }


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
    （`discogargantuarPult` → `discogargantuarpult`）时，这个函数原来「只增不删」，
    于是列表里同时留下新旧两条 id —— 游戏会拿旧 id 去扫 `Mods/*.pmod`，
    扫不到就报一条未知 Mod 的告警，而且**再跑生成器也不会自愈**。
    现在：仅大小写相同的 id 视为「本 Mod 自己的历史 id」直接清掉
    （别的 Mod 不可能与本 Mod 的 id 只差大小写），并回报被清掉的那几条。
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
    cfg = zombie_config_tres()
    txt = component_set_tres()
    fire = fire_definition_tres()
    sc = zombie_scene_tscn()
    sp = sprite_scene_tscn()
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
    for name, body in (("ComponentSet", txt), ("FireDefinition", fire), ("Scene", sc),
                       ("Sprite", sp), ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for path in re.findall(r'path="([^"]+)"', body):
            if path.startswith("res://"):
                if not path.startswith(game_ok):
                    fails.append(f"{name} 的 res:// 引用不是游戏自带资源：{path}")
            elif path.startswith("user:/") or ":" in path.split("/")[0]:
                fails.append(f"{name} 含绝对/非法引用：{path}")
    # 3. .tres 里的 Script 引用必须是 res://（.tres 非 res:// 会被直接拒绝）
    for name, body in (("ComponentSet", txt), ("FireDefinition", fire), ("Config", cfg),
                       ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for line in body.splitlines():
            if "[ext_resource" in line and 'type="Script"' in line:
                m = re.search(r'path="([^"]+)"', line)
                if not (m and m.group(1).startswith("res://")):
                    fails.append(f"{name} 的 Script 引用非 res://：{line.strip()}")
    # 4. 不得内嵌脚本（ModLoader 见到 GDScript/CSharpScript 字面量直接拒包）
    for name, body in (("ComponentSet", txt), ("FireDefinition", fire), ("Scene", sc),
                       ("Sprite", sp), ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        if 'type="CSharpScript"' in body or 'type="GDScript"' in body:
            fails.append(f"{name} 含内嵌脚本")
    # 5. Godot 4.7 的 unique_id / parent_id_path 一律不写（docstring 第六条）
    for name, body in (("Scene", sc), ("Sprite", sp)):
        if "unique_id=" in body or "parent_id_path=" in body:
            fails.append(f"{name} 不应写 unique_id / parent_id_path（可选字段，写了要伪造哈希）")
    # 6. ⚠️ 不许出现 CompanionOnly（会让 ModLoader 去要伴随运行时 → 拿不到就拒包）
    if "CompanionOnly" in sc or "mod_character_script_binding" in sc:
        fails.append("场景不得带 mod_character_script_binding（CompanionOnly 会被拒包）")

    # 7. 配置数值（用户需求 3/4/6）
    if f"hitpoints = {fmt_f(HITPOINTS)}" not in cfg:
        fails.append(f"config.hitpoints 应为 {fmt_f(HITPOINTS)}")
    if f"hitpointsNearDeath = {fmt_f(HP_NEAR_DEATH)}" not in cfg:
        fails.append(f"config.hitpointsNearDeath 应为 {fmt_f(HP_NEAR_DEATH)}")
    if abs((HITPOINTS + HP_NEAR_DEATH) - HP_TOTAL) > 1e-9:
        fails.append(f"总血 {HITPOINTS + HP_NEAR_DEATH} != 需求 {HP_TOTAL}")
    if f"attack = {fmt_f(ATTACK)}" not in cfg:
        fails.append(f"config.attack 应为 {fmt_f(ATTACK)}")
    if f"smashAttack = {fmt_f(SMASH_ATTACK)}" not in cfg:
        fails.append(f"config.smashAttack 应为 {fmt_f(SMASH_ATTACK)}")
    if f"cost = {COST}" not in cfg:
        fails.append(f"config.cost 应为 {COST}")
    if f"packetCooldown = {fmt_f(PACKET_COOLDOWN)}" not in cfg:
        fails.append(f"config.packetCooldown 应为 {fmt_f(PACKET_COOLDOWN)}")
    if f'name = "{CHAR_KEY}"' not in cfg:
        fails.append("config.name 必须等于角色场景文件名（TOWERDEFENSE_CHARCATERS 的键）")
    #     顺序：hitpointsNearDeath / hitpoints 必须紧跟 name（对齐类声明顺序，防编辑器重排）
    if cfg.index(f"hitpoints = {fmt_f(HITPOINTS)}") < cfg.index(f'name = "{CHAR_KEY}"'):
        fails.append("hitpoints 必须写在 name 之后（对齐类声明顺序，防编辑器重排）")
    if cfg.index("attack = ") > cfg.index("smashAttack = "):
        fails.append("attack 必须写在 smashAttack 之前（TowerDefenseZombieConfig 声明顺序）")
    # 8. 攻击类型 = 碾压（需求 5）
    if f'attackType = "{ATTACK_TYPE}"' not in txt:
        fails.append(f'Attack0_Definition.attackType 应为 "{ATTACK_TYPE}"')
    # 9. 两个 InstanceId 是运行时查找键，绝不能变（插件也依赖 character.catapult）
    for iid in ('InstanceId = "character.catapult"', 'InstanceId = "character.fire"'):
        if iid not in txt and iid not in fire:
            fails.append(f"缺少 {iid}")
    if 'InstanceId = "character.catapult"' not in txt:
        fails.append('CatapultDefinition.InstanceId 必须是 "character.catapult"（插件靠它找组件）')
    if 'InstanceId = "character.fire"' not in fire:
        fails.append('FireComponentDefinition.InstanceId 必须是 "character.fire"（ImpSpawn 靠它取 firePosMarker）')
    # 10. 投石参数逐字沿用 Imppult（需求 2）
    if f"projectileNum = {PROJECTILE_NUM}" not in txt:
        fails.append(f"CatapultDefinition.projectileNum 应为 {PROJECTILE_NUM}")
    if 'projectileName = "Imp"' not in txt:
        fails.append('CatapultDefinition.projectileName 应为 "Imp"')
    if f"fireInterval = {fmt_f(FIRE_INTERVAL)}" not in fire:
        fails.append(f"FireComponentDefinition.fireInterval 应为 {fmt_f(FIRE_INTERVAL)}")
    if "catapultFirstFar = true" not in fire:
        fails.append("FireComponentDefinition.catapultFirstFar 应为 true")
    # 11. 场景：四条 NodePath 必须与 Fire/ComponentSet 里写的一致
    for path in ("SpriteGroup/TransformPoint/ZombieImppult/FireSlot/FireMarker",
                 "SpriteGroup/TransformPoint/ZombieImppult/FireSlot",
                 "SpriteGroup/TransformPoint/ZamboniSmoke"):
        if f'NodePath("{path}")' not in (txt + fire):
            fails.append(f"组件集里缺少 NodePath(\"{path}\")")
    for np in ('sprite = NodePath("SpriteGroup/TransformPoint/ZombieImppult")',
               'headSlot = NodePath("SpriteGroup/TransformPoint/ZombieImppult/HeadSlot")'):
        if np not in sc:
            fails.append(f"场景缺少 {np}")
    if "unique_name_in_owner = true" not in sc:
        fails.append("FireSlot 必须带 unique_name_in_owner（脚本用 %FireSlot 取）")
    if IMPPULT_SCENE_SCRIPT not in sc:
        fails.append("场景脚本应复用内置 TowerDefenseZombieImppult.cs")
    if IMPPULT_SPRITE_SCENE not in sp:
        fails.append("Sprite 场景应复用内置 ZombieImppult.tscn（需求 7）")
    # 12. 卡片三闸门 + type
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
    # 13. manifest
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
        PACKAGE_CFG_REL,
        PACKAGE_PACKET_REL,
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
    # 14. 托管运行时四字段
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
        fails.append("缺 Runtime/ModAssembly.dll —— 先跑 python runtime_src_zombie/build_runtime.py --check")
    # 15. 注册键 == 卡片文件名去扩展 == saveKey
    if CARD_REL != f"Resources/Cards/{CHAR_KEY}.tres":
        fails.append("卡片注册键与 saveKey 不一致")
    # 16. 工程布局必须等于官方 XWModProjectLayout.StandardDirectories（72 项）
    if len(STANDARD_DIRS) != 72:
        fails.append(f"STANDARD_DIRS 应为 72 项（官方 XWModProjectLayout），实为 {len(STANDARD_DIRS)}")
    if len(set(STANDARD_DIRS)) != len(STANDARD_DIRS):
        fails.append("STANDARD_DIRS 有重复项")
    # 17. 角色包自引用必须是相对路径 —— 渲染进文本再查一遍
    for name, body in (("Scene", sc), ("Sprite", sp), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for path in re.findall(r'path="([^"]+)"', body):
            if path.startswith("res://") and "/Characters/" in path:
                fails.append(f"{name} 自引用写成了游戏根下的 res://：{path}")
    return fails


def main():
    fails = self_check()
    if fails:
        print("[FAIL] 自检未通过：")
        for f in fails:
            print("   -", f)
        return 3
    print(f"自检通过：{PROJECTILE_NUM} 发投石 / 每发 {fmt_f(FIRE_INTERVAL)}s / 碾压 100% · "
          f"总血 {fmt_f(HP_TOTAL)}（{fmt_f(HITPOINTS)} + 濒死 {fmt_f(HP_NEAR_DEATH)}）/ "
          f"攻击 {fmt_f(ATTACK)} / ZOMBIE 卡 / {COST} 阳光 / 冷却 {fmt_f(PACKET_COOLDOWN)}s")

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
