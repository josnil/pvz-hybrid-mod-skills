"""生成《超级机枪射手》植物 Mod（数据 + 托管运行时插件）。

设计要点（全部依据 V0.28 解包逆向，见 .cache/植物管线逆向结论.md）：
  1. 路径硬约束：ModLoader.TryInferCharacterScene 要求
     `Resources/Characters/Plants/<Key>/Scene/<Key>.tscn` 恰好 6 段，文件名 == 目录名 == Key。
  2. 一切在 `Resources/Characters/Plants/<Key>/` 下的文件都算「角色包依赖」，不会触发 unsupported。
  3. 包内 .tscn/.tres 里引用脚本必须用 `res://` 绝对路径指向原版脚本；
     非 res:// 的 Script 引用会被剥离(.tscn) 或直接拒绝(.tres)。
  4. 不需要伴生托管程序集：只有场景根带 `mod_character_script_binding="CompanionOnly"` 才需要。
  5. ★ 2026-09-24 齐射改版：一次攻击**同时**射出 7 颗豌豆 —— 数据侧 7 条
     `FireComponentFireProjectileConfig`（同 speed/dir/伤害，仅 `firePosId = 0..6` 不同），
     `.dat` 里 f62 的 1 个 `fire` 事件 → `AnimeEvent → FireConfiguredVolley → Fire()`（3434 行）
     一次遍历全部配置 = 7 颗同一帧出膛（引擎自己的齐射通道，参考狐尾草 HWC 的
     `TowerDefensePlantHWCFireComponentDefinition.tres` + `TowerDefensePlantHWC.FireVolley`）。
  6. 互不重叠 = 横向位置偏移：Head 下 7 个 Marker2D，相邻间距 32px（豌豆贴图 28×28）
     ⇒ ±96px 散布；`lockProjectileGridY = true` 把每颗豌豆的行**锁死在本排**
     （FireComponent.cs:2743 → BulletField.cs:1473/5598：锁行后命中判定恒按种植行过滤，
     子弹像素 Y 变化不改变归属行 ⇒ 散布不改变「前方一行」的命中行为）。
  7. ⚠️ 「10% 概率大招 + 5 秒 300 发」**纯数据做不到** —— FireComponentFireProjectileConfig 只有 8 个字段，
     没有概率/时窗字段；`AttackProcessing` 只按 fireInterval 调 timeScale，最高约 4 倍速 ⇒ 5 秒最多 ~93 颗；
     `Fire()` 的唯一随机源 OnFireVolley(seed) 用的是**确定性**种子（联机同步需要）。
     ⇒ 已改由**托管运行时插件**实现（见下面「插件」一节 + 植物Mod-超级机枪射手.md §3）。

── 以下 4 条是 09-18「游戏加载失败」的根因（ModLoader 的硬性闸门，违反即整包被拒）──

  8. ⚠️ **包内自引用必须用「相对路径」，不能用 res://**。
     依据：ModLoader.TryGetGodotResourcePath() 走 ProjectSettings.LocalizePath()
     → ModsCache 下的文件被映射成 `user://ModsCache/<名>/...`，Godot 再用该路径加载场景，
     于是 .tscn 里的相对引用（../Config/…、./XComponentSet.tres）在 user:// 树内解析成功；
     而 `res://Resources/Characters/Plants/<Key>/...` 会在**游戏 pck 根**解析 —— 那里没有
     `Resources/` 目录（本机解包已确认 res:// 根下不存在 Resources/），必然加载失败，
     角色场景 → 被拒 → 整包 apply 失败。
     指向**游戏自带**资源（res://Prefab/…、res://Asset/…、res://Script/…）时仍必须用 res://。
     参考实现：XWResourceCreateRoute.BuildCharacterRuntimeSceneContent()。

  9. ⚠️ **必须额外交付一个 Sprite 场景**：`Resources/Characters/Plants/<Key>/Sprite/<Key>.tscn`
     （6 段：文件夹名 == 文件名 == <Key>）→ 注册进 `ResourceManager.CHARCTAER_SPRITE[<Key>]`。
     否则 XWModContentValidation 第 35-36 行 `RequireReference(manifest,"CharacterSprite",…)` 直接
     throw「缺少 CharacterSprite/<Key>」；而且运行时 TowerDefenseManager.GetPacketSpriteScene()
     会在 CHARCTAER_SPRITE 里查 saveKey / characterConfig.name，查不到就抛 KeyNotFoundException。
     例：原版 PlantGatlingPea 的 CHARCTAER_SPRITE 键就是 "PlantGatlingPea"。

 10. ⚠️ **packet.saveKey 必须等于「注册键」**，即 `Resources/Cards/<文件名去扩展>`
     （XWModContentValidation:30-33，不等即 throw「saveKey 与注册键不一致」）。
     同时 `characterConfig.name` 必须是 **角色场景的文件名/目录名 = <Key>**，
     因为 TowerDefensePacketConfig.Create() 用 `characterConfig.name` 去查
     TOWERDEFENSE_CHARCATERS，而 mod 角色只能注册在 <Key> 这个键上。
     本包三处统一为 "SuperGatlingPea"。

 11. ⚠️ **packet.unlockCheckList 必须为空、或只放 XWModProgressUnlockCondition**
     （XWModContentValidation:37-40）。原版用的 UnlockConditionPacketBankCategoryPacketUnlockNumConfig
     是游戏内条件 → throw「必须使用 Mod 专属解锁条件」。空表 = 直接可用（TowerDefensePacketConfig:1222）。

幂等：所有产物字节确定（.tscn/.tres 手写模板、zip 用固定时间戳 ZipInfo）。
工程目录 / Mods 镜像都走**增量**写入 + 增量清理（`sweep_stale_files` / `sync_tree`），
第二次以后运行不写一个字节、不删一个文件。

⚠️ 本机运行环境的文件删除钩子**每次调用约 0.6 s**（实测：删 72 个空目录 48 s，
3 连跑的幂等校验会因超时被杀成 SIGTERM）。所以：
  · 不用 `shutil.rmtree`（它更进一步——被劫持成「丢回收站」，失败即 fail-closed 抛
    `SHFileOperationW 0x2`，直接让生成器退出码 1）；
  · 也不用「整目录删掉重建」的写法（哪怕手写逐文件删除也太慢）。
`safe_rmtree()` 仍然保留，只在人工需要整目录重置时用。
镜像前有安全护栏：`mirror_is_ours()` 判定不是我们生成的目录（带 `超级机枪射手.pvzmodeproject`
或是个零文件的空壳）→ 跳过不动，绝不误删用户目录。镜像里不再放 `.generated` 标记文件
（那会让标记本身在「写→下次被增量清理删掉→再写」之间来回抖动）；改用工程文件当标记，
和 build_map_vampire_pool.py 完全一致，而且**自愈**（工程文件本身就会同步进镜像）。

工程目录结构照抄游戏侧编辑器：`STANDARD_DIRS` = XWModProjectLayout.StandardDirectories 的 72 项
（顺序原样），与 build_map_vampire_pool.py 逐字相同。

── 插件（托管运行时）── 2026-09-19

本包自 v1.0.0 起带 `Runtime/ModAssembly.dll`（入口类 `SuperGatlingPeaRuntimeEntry`），
源码在 `../runtime_src_plant/`，用 `python runtime_src_plant/build_runtime.py --check` 编译
—— **必须先跑它**，否则 manifest.resources 指向的 DLL 不存在，本脚本会拒绝打包。

插件干三件事（②③ 是 2026-09-19 加的用户反馈）：
  ① 玩法：每次攻击 10% 概率触发 5 秒大招（43 轮 × 7 颗 = 301 颗豌豆）；
  ② **可选性（根上的修法）**：把本卡补进**共享卡库** `TOWERDEFENSE_PACKETBANKS["GeneralPlant"]`
     的 `Gold` 分类（+ 按 `Include` 闭包算出的派生库 `Total`）。
     依据：选卡界面 `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync` 按
     `packetBankData.category[分类]` 列卡，而 `packetBankType` 默认就是 `"GeneralPlant"`
     （`TowerDefenseLevelPacketBankConfig.cs:9`）⇒ 补完它 = **选卡界面能选到**。
  ③ 兜底：也补进**图鉴自己那份卡库拷贝**的 `Gold`（图鉴由 `Almanac.cs:219` 从 `GeneralPlant`
     拷出来，所以 ② 做完图鉴本来就有；③ 只防「图鉴已经开着 → 才补上卡库」的时序）。
     ⚠️ Mod 植物还会被游戏单列到 `ModPlants` 分类（`XWModContentCatalog.WithPlants`），
     我们**没删**那一类，只保证 `Gold` 里也有它。
  ⚠️ 副作用（= 成为正常金卡）：按卡库取卡的随机/奖励逻辑都可能给出这张卡 —— 清单见 doc §3.6。

── 数值（2026-09-19 用户指定）──

· 血量 `hitpoints = 1000.0`（值取自 `HITPOINTS`），写在
  `Resources/Characters/Plants/<Key>/Config/TowerDefensePlant<Key>.tres`。
  依据：`TowerDefenseCharacterInstance._Init:317-320`
  `hitpointsBase = config.hitpoints; hitpoints = hitpointsBase + config.hitpointsNearDeath;`
  （类默认 300.0，`hitpointsNearDeath` 保持 0 ⇒ 就是 1000）。

· 「**可以直接种、不必种在双发射手上**」= 卡片内联一个 `TowerDefensePacketOverride`
  子资源、只开 `coverCanDirectPlant = true`（常量 `COVER_CAN_DIRECT_PLANT`）。
  - 本卡是**覆盖卡**：`plantCover = ["PlantPeaShooter"]`，而
    `TOWERDEFENSE_PLANT_PEASHOOTER_NAME` 的中文列就是「双发射手」（`Asset/Translate/Translate.csv`）。
  - 闸门 `TowerDefenseCellInstance.CanPacketPlant:787-800`：
    `if (GetPlantCover().Count > 0 && !noLimit) { 找底座; if (!GetCoverCanDirectPlant()) return false; }`
  - 而 `TowerDefensePacketConfig.GetCoverCanDirectPlant():500-507`
    **只在 `_override` 有效时才读它**，否则硬编码 `return false`
    ⇒ 光改 `characterConfig` 做不到，必须走 packet override。
  - 写法照抄官方 Gold 挑战关
    `Asset/Config/Level/TowerDefense/Challenge/Gold/Challenge_Level2_3.tres`
    （它给 `PlantGatlingPot` 开的就是这个开关，是本机制的正例）。
  - override 里**只写 `coverCanDirectPlant`**，其余全走类默认值 = 「不覆盖」语义
    （type=NOONE / cost·costRise·cooldown=-1 / plantCover=[] / hypnoses=false ⇒ 各 GetXxx() 回落）；
    `islimitGridNum` 默认 true 与无 override 时的硬编码 true 一致；
    唯一无条件生效的 `characterOverride` 默认值全是空操作（scale/hitpointScale= -1、数组为空）
    ⇒ 不会碰血量、缩放、动画。生成器的自检会**拒绝**往 override 里多写字段。
  - 好处：空地能直接种，**同时保留**「种在双发射手上升级」这条路。
  - ⚠️ 若某关卡用 packetOverride 覆盖了本卡，那份 override 会顶掉这里的值 ⇒ 又变回必须底座。
    想彻底免疫（代价是失去升级底座）就把 `plantCover` 置空 = `[]`。
  - ⚠️ `plantCoverAll` 是**死字段**（运行时从未被读取，只有编辑器 UI 绑定），别指望它。

四条硬约束（2026-09-18 地图 Mod 实测，违反即整包被拒，不是「不生效」而是「不加载」）：
  a) `runtimeAssembly` 只能是**字面量** `"Runtime/ModAssembly.dll"`（ModLoader 字符串相等判定，
     不认别的路径 / 大小写 / 子目录）。本脚本用常量 RUNTIME_ASSEMBLY，改这里没意义。
  b) `runtimeApiVersion` 必须**恰好**是 1。
  c) `runtimeAssemblyPolicy = "optional"`：程序集缺失/加载失败时**不连坐整包**
     （植物本身照常能用，只是没有大招）。若改成 required，DLL 一旦加载失败连植物都没了。
  d) ⚠️ `TryInitializeRuntimeEntry` 失败 → ModLoader.cs 667-671 行**无条件整包回滚**，
     **不受 policy 保护**。所以入口的 Initialize / OnAllModsLoaded / Shutdown **一律不许抛异常**
     （已有实测：入口构造或 Initialize 抛错 = 这个 Mod 直接装不上）。
  e) 入口类型 FullName 必须等于 `runtimeEntryType`（无命名空间 ⇒ 就是纯类名），
     且必须 public + 公开无参构造 + 非嵌套类型。
  f) `Runtime/ModAssembly.dll` 不是可推导的资源类别（InferRuntimeEntry → false），
     但它必须**同时**出现在 manifest.resources 里，且位置遵守 SyncProject 的规范序
     （OrdinalIgnoreCase 升序 ⇒ `Resources/…` 在前、`Runtime/…` 在后），
     否则编辑器一打开工程就会重写 mod.json。

为什么这个插件「必然能生效」（不是猜的，逐条有源码位置，见 doc §3.2 / §3.3）：
  · ★ 2026-09-24 齐射改版后插件只管**大招**：订阅游戏自己声明的 C# event
    `FireComponent.OnFireReady`（FireComponent.cs:667，委托 `FireReadyEventHandler()`
    同文件 255 行）——它在 `AttackEntered()`（3258 行）里恰好调一次，
    是「一次攻击开始」的精确信号；命中就掷 10% 骰开大招，不命中就什么都不做
    （常规齐射由 vanilla 动画事件自己完成，见下）。
  · 常规攻击 = **数据侧齐射**（2026-09-21 曾由插件逐颗发、2026-09-24 改回数据侧）：
    `.dat` 里 f62 的 `fire` 事件 → `AnimeEvent`（fireEventName 默认 "fire"）
    → `FireConfiguredVolley()`（fireNumAtOnce=false ⇒ 恰好 1 次 `Fire()`）
    → 7 条配置同帧全打出。所以插件**不得**再改写 fireEventName 屏蔽发射链
    （2026-09-21 的 "modfire" 屏蔽已撤销），否则整株植物哑火。
  · 大招逐颗散射调 `CreateProjectileByData()`（FireComponent.cs:3049，狐尾草
    `TowerDefensePlantHWC.FireVolley` 同款 API）：**不能再调 `Fire()`**——
    它现在一次会打出全部 7 条齐射配置。CreateProjectileByData → CreateProjectile
    （2684 行）走同一段弹体创建代码 ⇒ 命中盒/伤害/行号行为必然一致；
    collisionFlags 传 -1 ⇒ `parent.instance.collisionFlags`，与
    `Fire()` 里 useParentCollision=true 的默认路径（FireComponentCheckConfig.cs:57-64
    GetCollisionFlags() 返回 -1）完全一致。
  · 识别本植物用 `config.name == "SuperGatlingPea"`（内置机枪射手也叫 GatlingPea，按类名认会误伤）。
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

BUILD_DIR = "SuperGatlingPea"          # 工作区构建目录（ASCII）
MOD_NAME = "超级机枪射手"                 # 游戏侧工程目录名 / .pvzmodeproject / .pmod 文件名
MOD_ID = "supergatlingpea"             # manifest.id
CHAR_KEY = "SuperGatlingPea"           # 角色 key（= CharacterResource 里的键 = 目录名 = 场景文件名）
MOD_ROOT = os.path.join(WS, BUILD_DIR)
DIST_DIR = os.path.join(WS, "dist")

# 原版资源（res:// 前缀，游戏内解析；本机解包用于校验存在性）
BASE_GATLING_SCENE = "res://Asset/Anime/Character/Plant/Cover/GatlingPea/Scene/TowerDefensePlantGatlingPea.tscn"
BASE_GATLING_SPRITE = "res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tscn"
BASE_PLANT_SCENE = "res://Prefab/TowerDefense/Character/TowerDefensePlant.tscn"
# mod 包内唯一可用的精灵基类（addons/AdobeAnimateEditor/Node/AdobeAnimateSprite.cs 在包内不可用）
SPRITE_BASE_SCRIPT = "res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs"


def anim_tres_res():
    """精灵场景里引用 AnimeData 的**包内相对路径**（延迟求值，避免与下面的常量定义顺序耦合）。

    ⚠️ 为什么是相对路径而不是 `res://Resources/Animations/...`：
      ModLoader 把 .pmod 挂到游戏根的 **一个派生目录**下（不是游戏根本身），
      `res://` 只解析游戏自带资源（Prefab/Asset/Script/Resource/Registry/Extends），
      包内资源写 `res://` 会被当成「游戏里不存在的路径」⇒ 加载期报找不到。
      相对路径由 Godot 按「引用方所在目录」解析，包重定位/改目录名都不会失效。

    ⚠️⚠️ 相对路径的层级必须按「引用方」算，不能拍脑袋写 `./`：
      Sprite 场景位于  Resources/Characters/Plants/<Key>/Sprite/<Key>.tscn
      动画 .tres 位于  Resources/Animations/<Key>.tres
      ⇒ Sprite/ 目录本身在包根下 4 层（Resources / Characters / Plants / <Key>），
        从它出发上 4 层回到包根，再进 Resources/Animations/ ⇒ `../../../../Resources/Animations/<Key>.tres`。
      写错层级 = 场景加载期报「找不到资源」⇒ 整只角色不出现（比贴图错更难查）。
    """
    # 「Sprite 场景所在目录」相对包根的层数
    up = f"{PKG_REL}/Sprite".count("/") + 1          # Resources/Characters/Plants/<Key>/Sprite -> 4 段
    return f"{'../' * up}{ANIM_DIR_REL}/{ANIM_BASENAME}.tres"
BASE_PLANT_COMPONENT_SET = "res://Prefab/TowerDefense/Character/ComponentSets/TowerDefensePlantComponentSet.tres"
BASE_FIRE_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentStateMachine.tres"
BASE_FIRE_DEFINITION_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentDefinition.cs"
BASE_AABBRAY_SCRIPT = "res://Resource/TowerDefense/Collision/AabbRay2DResource.cs"
BASE_CREATEDATA_SCRIPT = "res://Registry/Projectile/Resource/TowerDefenseProjectileCreateData.cs"
BASE_PROJ_SINGLE_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/Projectile/FireComponentProjectileSingle.cs"
BASE_CHECK_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentCheckConfig.cs"
BASE_FIRE_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs"
BASE_COMPONENT_SET_SCRIPT = "res://Script/Component/Runtime/CharacterComponentSet.cs"
BASE_PLANT_CONFIG_SCRIPT = "res://Resource/TowerDefense/Character/Config/TowerDefensePlantConfig.cs"
BASE_HITBOX_SCRIPT = "res://Resource/TowerDefense/Collision/CharacterHitBoxDefinition.cs"
BASE_PACKET_SCRIPT = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs"
BASE_PACKET_OVERRIDE_SCRIPT = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/TowerDefensePacketOverride.cs"
BASE_UNLOCK_SCRIPT = "res://Resource/UnlockCondition/UnlockConditionPacketBankCategoryPacketUnlockNumConfig.cs"

# 调参（2026-09-21 改版；2026-09-24 齐射再改版）
#
# ★ 2026-09-24 齐射改版（用户需求：像狐尾草一样把一轮子弹一次性齐射出去，不逐发连打）
#
#   常规攻击回到**数据侧**：7 条 `FireComponentFireProjectileConfig`（firePosId = 0..6，
#   同 speed / dir=0 / 同 check 0 ⇒ 伤害、速度、碰撞行为与单发逐字一致），挂在 7 个
#   Marker2D 上（相邻 32px，豌豆 28×28 ⇒ 互不重叠）。动画 f62 的 1 个 `fire` 事件触发
#   `FireConfiguredVolley()`（fireNumAtOnce=false ⇒ 恰好 1 次 `Fire()`），`Fire()`（3434 行）
#   一次遍历 `_fireProjectiles` 全部 7 条 = 7 颗**同一帧**出膛 —— 引擎自己的齐射通道。
#   参考实现 = 狐尾草（HWC）：`TowerDefensePlantHWCFireComponentDefinition.tres`（多
#   firePosMarkerPaths）+ `TowerDefensePlantHWC.FireVolley`（一次循环把所有弹打出去）。
#
#   ⚠️ 行归属：`lockProjectileGridY = true` 仍然保留（FireComponent.cs:2743 读取
#     ⇒ overrides.gridYOverride = 种植行 ⇒ BulletField.cs:5598 lockGridY=true ⇒ 1473 行
#     恒用锁定的行）⇒ 7 颗的命中判定**恒按种植行过滤**，与单发完全一致（「前方一行」）。
#     ★ 2026-09-24 二次修正：排列改为**只沿 x（弹道方向）**铺开 ⇒ 屏幕上排成一条
#     **水平直线**（用户口径：「一排，不是一列」）。7 颗的像素 Y 全 = 炮口 Y，
#     所以锁行从「防止窜排的补丁」升级为「显式不变量护栏」（断言见 self_check 13c-4 / 13f-4）。
#
#   ⚠️ 插件角色变化：常规攻击交还 vanilla（撤销 2026-09-21 的 fireEventName="modfire"
#     屏蔽，fireEventName 回落定义默认值 "fire"）；插件只管**大招**（10% → 5s 300 颗），
#     且大招改走 `CreateProjectileByData()`（狐尾草 FireVolley 同款 API）单颗直调 ——
#     因为 `Fire()` 现在会一次打出全部 7 条齐射配置，不能再拿来逐颗发射。
FIRE_INTERVAL = 1.5           # 每 1.5 秒一轮
VOLLEY_COUNT = 7              # 一次齐射的颗数（= 数据侧 fireProjectileList 条数 = Marker 数）
VOLLEY_SPACING = 32.0         # 相邻两颗的间距（px，**沿弹道方向**排成一条水平直线）：豌豆 28×28 ⇒ 32 保证不重叠
VOLLEY_FORWARD_SIGN = 1.0     # ★ 散布方向：只沿**弹道方向**（本地 +x）向前铺。链路里没有任何镜像
                              #   （Sprite root offset=(-40,-40) / Head offset=(-37.05,-47) / 无 scale 覆写），
                              #   且 MARKER2D_POS = 炮口(88.552,30.2) + HEAD_OFFSET ⇒ 本地 +x = 屏幕右
                              #   = 弹道正前方。要反向只改这一个常量（但反向会让豌豆从植物背后冒出来）。
ULTIMATE_SPREAD_DEG = 15.0    # 大招散射半角（±15°，只在插件里用，不落数据）
ULTIMATE_PEAS = 300           # 大招总颗数
ULTIMATE_SECONDS = 5.0        # 大招持续秒数
PEA_SPEED = 500.0             # 与原版 Starfruit 同速（原版豌豆默认 300，散射用 500 手感更好）
PROJECTILE_NAME = "Pea"

# 卡片 / 配置数值（2026-09-18 用户指定；字段名依据 TowerDefenseCharacterConfig）
COST = 600                    # 阳光花费
COST_RISE = 100               # 种植涨价（每次种下一张，同关后续同卡 +100）
PACKET_COOLDOWN = 30.0        # 冷却 30 秒
PACKET_TYPE = 1               # TowerDefenseEnum.PACKET_TYPE.GOLD（NOONE=-1,WHITE=0,GOLD=1,…COVER=7）

# 血量 / 可种植性（2026-09-19 用户指定）
#
# 血量：TowerDefenseCharacterInstance._Init 里
#   hitpointsBase = config.hitpoints; hitpoints = hitpointsBase + config.hitpointsNearDeath;
#   ⇒ 写 hitpoints = 1000.0 就是 1000 血（类默认 300.0；hitpointsNearDeath 保持 0）。
#
# 可种植性：本卡 plantCover = ["PlantPeaShooter"]（= 双发射手，见 Translate.csv
#   TOWERDEFENSE_PLANT_PEASHOOTER_NAME 的中文列）⇒ 它是「覆盖卡」，默认**只能**种在双发射手上。
#   闸门在 TowerDefenseCellInstance.CanPacketPlant(:787-800)：
#     if (GetPlantCover().Count > 0 && !noLimit) { 找底座; if (!GetCoverCanDirectPlant()) return false; }
#   而 GetCoverCanDirectPlant() **只在 packet 有 _override 时才可读**，否则硬编码 return false。
#   ⇒ 纯数据解法 = 给卡片内联一个 TowerDefensePacketOverride 子资源、只开
#      coverCanDirectPlant = true（其余字段保持默认 = 空操作，见下表）。
#   好处：既能在空地直接种，**也不影响**原有的「种在双发射手上升级」这条路。
#   ⚠️ 若关卡用 packetOverride 覆盖了本卡，那份 override 会顶掉这里的值 ⇒ 又变回必须底座。
#      想彻底免疫（但会一并失去升级底座）就把 plantCover 置空 = []。
#   ⚠️ 不要指望 plantCoverAll：它在运行时**从未被读取**（只有编辑器 UI 绑定），是死字段。
HITPOINTS = 1000.0            # 血量
COVER_CAN_DIRECT_PLANT = True # 覆盖卡也能直接种在地上（内联 packet override 实现）

# 包内相对路径（⚠️ 见 docstring 第 8-11 条：mod 自引用一律相对，禁 res://）
PKG_REL = f"Resources/Characters/Plants/{CHAR_KEY}"
CFG_FILE = f"TowerDefensePlant{CHAR_KEY}.tres"
SCENE_FILE = f"{CHAR_KEY}.tscn"
COMPONENT_SET_FILE = f"{CHAR_KEY}ComponentSet.tres"
SPRITE_FILE = f"{CHAR_KEY}.tscn"
CARD_REL = f"Resources/Cards/{CHAR_KEY}.tres"          # 注册键 == 文件名 == saveKey

# 托管运行时（见 docstring「插件（托管运行时）」一节；改动前务必读完那 6 条约束）
RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"          # ⚠️ 只能是这个字面量
RUNTIME_ENTRY_TYPE = "SuperGatlingPeaRuntimeEntry"    # 无命名空间 ⇒ 类名即 FullName
RUNTIME_API_VERSION = 1                               # ⚠️ 必须恰好 1
RUNTIME_POLICY = "optional"                           # 加载失败不连坐整包（植物仍可用，只是没大招）
RUNTIME_SRC_DIR = os.path.join(WS, "runtime_src_plant")   # 源码 + build_runtime.py 所在

# ---- 共享射击判定核心（#45）：与「超级机枪读报僵尸」共用同一份源文件 ----
# 两个 csproj 各自 <Compile Include="../runtime_shared/GatlingVolleyCore.cs" />，
# 于是「掷大招骰 / 散射角 / 大招排期 / 卡顿补偿」只有一份实现，改一处两边同时生效。
# 下面这些是**生成器侧的期望值记录**，自检会逐个与共用核心的字面量比对：
# 谁改了共用核心却忘了同步这里 ⇒ 生成阶段直接报错，不会带着漂移打包。
SHARED_CORE = os.path.join(WS, "runtime_shared", "GatlingVolleyCore.cs")
# ★ 2026-09-24 齐射改版后：植物常规攻击已是**数据侧齐射**（VOLLEY_COUNT 条配置一次打出），
#   插件不再用「逐发链」，所以 PeasPerAttack / PeaSpacingSeconds 两个核心常量只对
#   僵尸包（超级机枪读报僵尸）的连发链有意义。这里仍记录它们的期望值（核心字面量比对），
#   但自检 #16 **不再要求植物入口转发**这两个常量（其余 6 个仍要求转发）。
#   不变式：齐射颗数必须与核心的 PeasPerAttack 一致（同一份用户需求，两处各说各话 = 漂移）。
PEAS_PER_ATTACK = 7         # 共用核心记录：连发链每轮颗数（僵尸包用；植物侧 = VOLLEY_COUNT）
PEA_SPACING = 0.1           # 共用核心记录：连发链颗间距（秒，僵尸包用）
ULTIMATE_CHANCE = 0.10      # 每次攻击触发大招的概率
MAX_PEAS_PER_FRAME = 12     # 单帧发射上限（掉帧保护）
STALL_THRESHOLD_MSEC = 250  # 暂停 / 长卡顿判定阈值（毫秒）


def _p(*parts):
    """包内路径（MOD_ROOT/<角色包目录>/<parts...>）的绝对路径。"""
    return os.path.join(MOD_ROOT, PKG_REL.replace("/", os.sep), *parts)


def _abs(rel):
    """MOD_ROOT 下任意相对路径 → 绝对路径。"""
    return os.path.join(MOD_ROOT, rel.replace("/", os.sep))


# ---------------------------------------------------------------- 卡片文案
#
# ★ 2026-09-25 起改为**内联字面量**（不再走翻译键）—— 原因见 translation_file() 的说明：
#   Mod 的 `Localization/translations.csv` 在**游戏运行时不会被加载**
#   （ModLoader 全文无 `TranslationServer.AddTranslation`；`project.godot` 只挂内置的
#     `res://Asset/Translate/Translate.{en,es,zh}.translation`；解包出来的 `.csv` 也不在
#     `ModLoader.cs:1006 TryResolveDeclaredResourceCandidate` 的扩展名白名单里）
#   ⇒ 字段里写 key，进游戏就**原样显示 key 本身**。所以四个文案字段一律内联真实文本。
#   `saveKey` 才是身份标识（== 注册键 == 卡片文件名去扩展），改 `name` 不破坏注册。
#
# 文案口径 = 官方 `InformationPanel.tscn` 自带范例 + 用户 2026-09-25 截图：
#   · 头词（韧性 / 威力 / 范围 / 特点 / 大招）→ **裸文本**，吃面板 default_color #8F431B（棕）
#   · 数值 / 短语                            → `[color=cc241d]`（#CC241D 红）
#   · `describe`（「大哥登场！」）             → 面板自己包 `[color=2f375e]`，**不要再自己包色**
#   · `.tres` 多行字符串用**真实换行**（与官方 `Challenge_Level13_3.tres` 一致，不写 `\n` 转义）
#   · 「花费：600」/「冷却速度：30.0 秒」两行由面板自己拼，**不写进这些字段**
#
# ⚠️ 「威力」按用户 2026-09-25 口径：`20×7 /1.5秒`（截图上原为 `20×7 /2s`）。
# ⚠️ 历史翻译键（TOWERDEFENSE_PLANT_SUPERGATLINGPEA_{NAME,EXPRESTION,HANDBOOK_EXPRESTION,
#    HANDBOOK_STORY}）**已全部废弃**：资源里不再出现，translations.csv 也改用字面量。
PLANT_CN_NAME = "超级机枪射手"
PLANT_CN_DESC = "大哥登场！"
PLANT_CN_HANDBOOK_DESC = (
    "韧性：[color=cc241d]1000[/color]\n"
    "威力：[color=cc241d]20×7 /1.5秒[/color]\n"
    "范围：[color=cc241d]前方一行[/color]\n"
    "特点：[color=cc241d]每次攻击有10%概率释放大招[/color]\n"
    "大招：[color=cc241d]小范围散射约300枚子弹[/color]"
)
PLANT_CN_STORY = (
    "超级机枪射手完美诠释了“火力优势学说”，在那个属于他的时空，"
    "他的每次发怒都是无数僵尸的梦魇。然而，他也有属于自己脆弱的一面，"
    "比如他背地里其实很害怕史莱姆。"
)
PLANT_EN_NAME = "Super Gatling Pea"
PLANT_EN_DESC = "The big brother is here!"
# 英文版数值块：口径与中文一致（头词裸文本 + [color=cc241d] 数值），只给编辑器留底。
PLANT_EN_HANDBOOK_DESC = (
    "Durability: [color=cc241d]1000[/color]\n"
    "Power: [color=cc241d]20×7 /1.5s[/color]\n"
    "Range: [color=cc241d]one lane ahead[/color]\n"
    "Trait: [color=cc241d]10% chance per attack to release an ultimate[/color]\n"
    "Ultimate: [color=cc241d]scatters about 300 peas in a small area[/color]"
)
PLANT_EN_STORY = (
    "Super Gatling Pea is the perfect embodiment of the Theory of Firepower Superiority. "
    "In the timeline that belongs to him, every one of his rages was the nightmare of countless zombies. "
    "Yet he also has a fragile side — deep down he is actually very afraid of slimes."
)

# ============================================================================
# ★★★ 自制外观（2026-09-19 加入，2026-09-20 换成单帧素材）
#
# 素材（当前）：source/SuperGatlingPea_single.png —— **单帧静止图 352x384 RGBA8**
#       来源 = 用户提供的戴战术头盔/墨镜/耳机的机枪射手立绘；
#       背景为不透明深灰 (34,34,40) ⇒ 由 .cache/build_source_single.py 做
#         「flood fill 外缘连通背景 → alpha=0」+ 软过渡后落盘。
#       352x384 恰为 176x192 的精确 2 倍 ⇒ DISPLAY_SCALE=0.5 不变。
#       分层：原生 y<256 为 head（头/头盔/炮管），y>=256 为 body（茎/叶）——
#             该线正好切在颈/领口（原生 y=240..254 是宽约 24~27px 的脖子，
#             y>=255 突增到 55px 是肩），分得很干净。
#       anchor（由 .cache/calc_anchor_new.py 实测）：
#             root   = (138.5, 348) 原生 ÷2 = (69.25, 174.0)
#             muzzle = (314.0, 125.5) 原生 ÷2 = (157.0, 62.75)
#
# 素材（历史，已被替换）：deliver/PeaShooterVeteran_idle_00..24.png + _shoot_00..24.png
#       各 25 帧，每帧 176x192 RGBA8 透明底；frameRate=12.0
#       锚点 anchor.root=[80,158]（角色根点）、muzzle=[152,54]；分层线 y=128
#
# 不能只替换 .png（详见《植物Mod-超级机枪射手-换贴图换动画指南.md》）：
#   AdobeAnimateGlobalAtlasCache.TryGetOrBuild -> TryBuildStandaloneAllocation，
#   图集纹理**只能**来自 .dat 内嵌的像素区；没有真 .dat
#   ⇒ WarnProjectAtlasUnavailable（只 PushWarning 不抛）⇒ 精灵静默什么都不画。
#   而且**一个 .dat 只承载一张图集** ⇒ head/body 必须拼进同一张图。
#
# 三件套落盘位置：Resources/Animations/<Key>.dat | <Key>.tres | <Key>Atlas.png
#   ★ .tres 与 .dat **必须同目录同名** —— AdobeAnimateData.ResolveAnimeFilePath
#     (:1790-1822) 的两条兜底都依赖这个：
#       ResourcePath.GetBaseDir().PathJoin("./<Key>.dat") / TryResolveOwnerBasenameCompanionDat()
#     animeFile 因此写「同目录相对路径 ./SuperGatlingPea.dat」，不写 res:// 绝对路径。
# ============================================================================
ANIM_DIR_REL = "Resources/Animations"
ANIM_BASENAME = CHAR_KEY                       # SuperGatlingPea
ANIM_DAT_REL = f"{ANIM_DIR_REL}/{ANIM_BASENAME}.dat"
ANIM_TRES_REL = f"{ANIM_DIR_REL}/{ANIM_BASENAME}.tres"
ANIM_PNG_REL = f"{ANIM_DIR_REL}/{ANIM_BASENAME}Atlas.png"

# 自制外观源文件（由 .cache 下的脚本生成；改用「源目录 -> 包内」的同步方式）
SKIN_SRC_DIR = os.path.join(WS, "..", ".cache")

# ★★★ offset / Marker2D 标定（同 .cache/install_skin.py 的推导）
#
# 渲染期位置公式（`AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform`）：
#     Transform2D( (scale*帧宽,0), (0,scale*帧高), (slice.Ox + offset.X, slice.Oy + offset.Y) )
#     再乘 parent（父节点全局变换）
#   ⇒ 贴图左上角落点(相对节点) = **origin + offset**（引擎自己会把 origin 加回去！）
#
# ⚠️⚠️⚠️ 因此 `offset` **与 origin 无关**，它只是「把 anchor 挪到节点原点」的位移：
#     根   offset = -ANCHOR_ROOT（两层都一样）
#     Head offset = -ANCHOR_ROOT，且 Head.position = (0,0)
#   ⇒ 两层落点分别为 origin_body-anchor / origin_head-anchor，
#     差值恰 = origin_head - origin_body ⇒ 完美复原素材里的相对位置。
#
# ⚠️⚠️⚠️ 历史错误（2026-09-20 实机「头压在身上、身体几乎看不见」的真因）：
#     曾写成 offset = -(ANCHOR - ORIGIN) ⇒ 落点 = 2*origin - anchor
#     ⇒ 头身相对位移被**放大 2 倍**，两层直接飞开。
#     反证内置：`GatlingPea.tscn` 根 offset=(-40,-40)、Head offset=(-36,-46) 都是**小整数**，
#              而各层 origin 在 20~60 ⇒ offset 与 origin 无关，量级就是「-anchor」。
#
# 内置反标定（实测）：Head.offset=(-36,-46) / anim_idle 首帧 origin=(36.60,47.70)
#   / Marker2D=(31.740002,-17.82) ⇒ 反解 Marker2D 对应画布点 = (100.74,72.26)（合理）
#
# ★ 根与 Head 必须让「同一个世界点」当节点原点，否则头相对身错位。
#   本 Mod = 素材 anchor.root 对齐节点原点。
#
# ★★★ 素材换代（2026-09-20）：**官方素材直转**，DISPLAY_SCALE 概念作废
#
#   旧：自制图集（PeaShooterVeteran 切块 / 单帧静止图 352x384 ÷2）
#   新：未重置版官方 reanim —— `compiled/new/SuperGatling.reanim.compiled`
#       27 轨 × 87 帧 @12fps，含 hair1~5 / helmet / glasses / barrel / overlay2 等 23 张贴图
#
#   ⚠️⚠️ 关键纠正：**经典 reanim 的 sx/sy 就是最终渲染缩放，不需要任何额外缩放**。
#     实测内置 GatlingPeaZ 全轨 sx=sy=0.5550，png 44×22 → 渲染 24.4×12.2（正是植物该有的大小）。
#     「素材放大 2 倍 ÷2」只适用于**自制**素材（352×384 = 176×192 的精确 2 倍），已作废。
#
#   锚点：内置植物（PeaShooter / GatlingPea / GatlingPeaZ）**一律 offset = (-40,-40)**
#     ⇒ 经典 reanim 的 (40,40) 即「种植锚点」。实测 SuperGatling 与 GatlingPeaZ 落地线
#       同为 y=77.7（复用同一批 PeaShooter 叶/茎图）⇒ 同一坐标系，直接沿用。
#
#   头身：body/head 图层来自同一份 reanim、同一坐标系 ⇒ 根 offset = -ANCHOR_ROOT 不变；
#     但 Head.offset **不等于** 根 offset —— 引擎每帧用「被跟随图层（L16 anim_idle）的
#     pose.Origin + 父 offset」覆写 Head.position（AdobeAnimateSprite.cs:5259-5267），
#     而 anim_idle 的 pose.Origin 并非 (40,40) 而是 f0=(37.6,48.7) ⇒ 零偏移会把头画低。
#     ★ 2026-09-24（头位对齐豌豆射手）：以内置 PeaShooter 为基准反解：
#         P(头内容, 相对植株原点) = 跟随层pose + 父offset + 头图层origin + Head.offset
#       全待机周期 f0..24 逐帧比对「内置 PeaShooter（L8 anim_stem / offset(-36,-46) /
#       头图层 anim_face）」与「本 Mod（L16 anim_idle / 头图层 anim_face）」，
#       Δ = P_pea − P_sg 是刚性平移（x∈[2.87,3.05], y∈[-7.17,-6.90]，波动 ≤0.27px），
#       参考帧 f0（相对相位 0，与插件头部相位同步口径一致）：
#         Δ(f0) = (+2.95, −7.00)  ⇒  HEAD_OFFSET = (−40,−40) + Δ = **(−37.05, −47.00)**
#       即旧头位比豌豆射手偏左 2.95px、偏低 7.00px（旧 8px「抬头」写进了被引擎覆写的
#       Head.position，从未生效 —— 见 head_position() 的说明）。
#
#   炮口：官方 barrel 轨只在 56..68 可见，f62 完全伸出；取其**不透明区最右列中点**
#     = (88.552, 30.20)（经典坐标）。
#     ★ Marker2D 恒等式：**MARKER2D_POS = ANCHOR_MUZZLE + HEAD_OFFSET**。
#       因为「画出来的炮口」= 跟随层pose + 父offset + 炮口canvas + Head.offset，
#       而「Marker2D 世界位」= 跟随层pose + 父offset + marker_local，
#       两者相等的充要条件就是 marker_local = 炮口canvas + Head.offset
#       ⇒ Head.offset 改多少，Marker2D 必须同步平移多少，炮口点才始终粘在炮管上。
#       （旧口径 marker = 炮口 − ANCHOR_ROOT 只在 Head.offset=(−40,−40) 时成立。）
#     参照：内置 GatlingPea 的 Marker2D 反推炮口 = (75.34, 25.80)，同样落在炮管口内一寸。
# ============================================================================
DISPLAY_SCALE = 1.0                            # 经典 reanim 素材 1:1（sx/sy 已含最终缩放）
ANCHOR_ROOT = (40.0, 40.0)                     # 经典 reanim 坐标里的种植锚点
ANCHOR_MUZZLE = (88.552, 30.2)                 # barrel 完全伸出帧（f62）的不透明炮口点
ROOT_OFFSET = (-ANCHOR_ROOT[0], -ANCHOR_ROOT[1])
# ★ 2026-09-24 头位对齐豌豆射手的反解值（推导见上方注释块；自检 13b 会钉死它）
HEAD_OFFSET = (-37.05, -47.00)
# Head.position 见 head_position()（引擎每帧覆写，是死值；真旋钮就是上面的 HEAD_OFFSET）
MARKER2D_POS = (ANCHOR_MUZZLE[0] + HEAD_OFFSET[0],
                ANCHOR_MUZZLE[1] + HEAD_OFFSET[1])

# ★ 2026-09-24（射击后抽搐修复）：植物包把 HeadFire 收窄为**射击段 (50,74)**。
#   经典 SuperGatling.reanim 的 75..86 是「大招蓄力段」——3 帧一循环的剧烈抖动
#   （头部轨道 (22,7)↔(19.5,13.8)↔(17.9,19.5) 每帧跳变，垂直振幅 ~12.5px，重复 4 次）。
#   旧口径 HeadFire=(50,86) 让 FireComponent 在**每一轮普攻**都把这 12 帧抖完
#   （AttackEntered :3259 以 loop:true 播，AnimeCompleted :3542 播完才回 HeadIdle）
#   ⇒ 表现为「一轮射击打完后头部抽搐」，随后从 f86 位姿硬切回 HeadIdle@0.2 再抖一下。
#   内置单发家族（PeaShooter 等 7 例）的 HeadFire **一律是 (50,74)**（闭合循环：
#   f50 与 f74 头部位姿相同），本包对齐该口径 ⇒ 抽搐段不再被任何 clip 引用。
#   同步落盘：.tres 的 clips 字典 + .dat 的 clip 表（见 sync_skin_assets 的等长字节补丁）。
#   ⚠️ 发射事件仍在 f62（50+12 < 74），且 .dat 帧数据本身一帧不少（75..86 只是
#      不再被 clip 引用）；大招期间的视觉反馈 = 引擎每 1.5s 照常循环 Attack（见
#      插件 OnFireReadyFrom 的 BurstActive 分支注释），不需要这 12 帧。
HEADFIRE_CLIP_PLANT = (50, 74)


def skin_params():
    """读 .cache/skin_params.json —— `build_official_skin.py` 的标定产物（唯一真源）。

    ★ 2026-09-20 起外观改为「官方素材直转」：`.cache/build_official_skin.py` 把未重置版
      `compiled/new/SuperGatling.reanim.compiled`（27 轨 × 87 帧）转成重置版三件套，
      并把 offset / insertLayerId / Marker2D / 图层名表 / 媒体名表一起写成 json。
      本脚本的 Sprite 场景**由该 json 驱动**，避免「常量与生成物各说各话」。
    """
    p = os.path.join(SKIN_SRC_DIR, "skin_params.json")
    if not os.path.isfile(p):
        raise FileNotFoundError(
            f"缺外观标定文件 {p}\n请先运行：.cache/build_official_skin.py")
    with open(p, encoding="utf8") as f:
        return json.load(f)


def head_position():
    """Head 节点 `position` —— 恒 (0,0)。

    ⚠️⚠️ 2026-09-24 定论：Head.position 是**死值**，写多少都不生效。
      引擎 AdobeAnimateSprite.UpdateChild()（AdobeAnimateSprite.cs:5259-5267）每帧执行
      `child.Position = 被跟随图层 pose.Origin + 父精灵 offset`（usePos 默认 true），
      而根精灵循环播 BodyIdle（0..24），被跟随层 L16 anim_idle 每帧都有 locator slice
      ⇒ Position 每帧都被覆写。2026-09-21 写的 (0,-8)「抬头 8px」从未生效过
      （当时用户看到的 7px 偏低与此吻合，本轮已改由 HEAD_OFFSET 真正修正）。
      场景里写 (0,0) 只是清理死值，避免误导后来人。
    """
    return (0.0, 0.0)

# 游戏侧编辑器的 72 个标准子目录，**原样照抄** XWModProjectLayout.StandardDirectories（顺序也一致）
#   ⚠️ 2026-09-16 修正：此前这里是一份**臆造**的 120 项列表（含 Resources/ChessMaps2、
#      Resources/VampireMaps、Resources/Collectables2 等游戏中不存在的目录），
#      并且漏掉 MapCells / GameplayLogic / StateMachines / CharacterCombat … 共 39 项，
#      与 build_map_vampire_pool.py 的列表不一致。以 C# 源码为准，两边现在逐字相同。
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


def _near(a, b, tol=0.01):
    """浮点容差比对。

    ⚠️ 场景里写出的是 fmt_f() 四舍五入后的**短小数**（如 6.525 / -2.51），
       而期望值是完整精度的元组（如 6.524999999999999）。
       直接 `==` 会假红 ⇒ 一律用本函数（与 verify_skin_assets.py 的 tol 一致）。
    """
    return abs(float(a) - float(b)) <= tol


def _near_pt(got, exp, tol=0.01):
    """二维点容差比对，返回 (ok, 说明串)。"""
    ok = _near(got[0], exp[0], tol) and _near(got[1], exp[1], tol)
    return ok, f"{tuple(got)} vs 期望 {tuple(round(float(x), 6) for x in exp)}"


def _volley_shape_fails(positions, where):
    """★ 齐射排列形态检查（用户口径：「要一排，不是一列」）。

    入参 = 从**文本解析出来的** 7 个 Marker 位置（内存文本或磁盘文本，都由调用方解析）。
    返回 FAIL 列表（空 = 通过）。判据：
      ① 条数恰 VOLLEY_COUNT；
      ② **y 全相同** —— 屏幕上才是「一条水平直线」（一排）；出现多个 y ⇒ 竖直一列，FAIL；
      ③ x 严格递增、步距恒 == VOLLEY_SPACING 且 > 豌豆宽 ⇒ 不重叠；
      ④ 首颗 x == MARKER2D_POS.x（炮口点恒等式：散布不能挪走 Marker2D）。
    ⚠️ 断言只吃「解析值」，不拿生成常量自比（防「恒真比较」型假绿）；但期望值本身来自常量。
    """
    out = []
    if len(positions) != VOLLEY_COUNT:
        out.append(f"{where}齐射 Marker 解析到 {len(positions)} 个，应为 {VOLLEY_COUNT}")
        return out
    ys = {round(float(p[1]), 6) for p in positions}
    if len(ys) != 1:
        out.append(f"{where}齐射 Marker 的 y 不唯一 {sorted(ys)} ⇒ 屏幕上是**一列**而不是一排")
    xs = [float(p[0]) for p in positions]
    if not _near(xs[0], MARKER2D_POS[0], 0.01):
        out.append(f"{where}齐射首颗 x={xs[0]} != 炮口点 x={MARKER2D_POS[0]}（Marker2D 被挪动了）")
    steps = [b - a for a, b in zip(xs, xs[1:])]
    if any(s <= 0 for s in steps):
        out.append(f"{where}齐射 Marker 的 x 非严格递增：{xs}")
    for s in steps:
        if not _near(s, VOLLEY_SPACING, 1e-6):
            out.append(f"{where}齐射 Marker 的 x 步距 {s} != {VOLLEY_SPACING:g} ⇒ 间距错/可能重叠")
            break
    return out


def _strip_cs_comments(text):
    """去掉 C# 里的注释（`//…` 行注释 + `/*…*/` 块注释），字符串字面量原样保留。

    ⚠️ 为什么需要（2026-09-25 负向测试实锤的一类**假绿**）：
    对插件源码做子串断言时，把整条语句**注释掉**就能骗过它 ——
    `/* categories.Remove(ModPlantCategory); */` 里那个子串还在，断言照样绿，
    但运行时那一行根本不执行。所以结构断言必须吃「去注释后的代码」，
    也就是要求**真的有一条活语句**。
    （顺手也修掉反向假红：注释里写 `fire.Fire()` 不该被当成真的调用了它。）
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == '"':
            # 字符串字面量整体保留；`@"…"` 是逐字串（内部 `""` 表示一个引号）
            verbatim = i > 0 and text[i - 1] == "@"
            out.append(c)
            i += 1
            while i < n:
                ch = text[i]
                if verbatim:
                    if ch == '"':
                        if i + 1 < n and text[i + 1] == '"':
                            out.append('""')
                            i += 2
                            continue
                        out.append('"')
                        i += 1
                        break
                else:
                    if ch == "\\" and i + 1 < n:
                        out.append(text[i:i + 2])
                        i += 2
                        continue
                    if ch == '"':
                        out.append('"')
                        i += 1
                        break
                out.append(ch)
                i += 1
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


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
    回收站失败时 **fail-closed 直接抛 OSError**（实测 `SHFileOperationW 失败: 0x2`），
    于是生成器在 `install_project_dir` 一步中断、退出码 1（2026-09-16 复现两次）。

    ⚠️⚠️ 但逐文件 `os.remove` 在这个环境里**单次约 0.6 s**（实测删 72 个空目录要 48 s），
    所以主流程**已经不再调用它** —— 改成 sweep_stale_files() + sync_tree() 的增量清理。
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
                os.chmod(fp, stat.S_IWRITE)      # 只读文件（如 .generated）兜底
                os.remove(fp)
        for dn in dirs:
            os.rmdir(os.path.join(root, dn))
    os.rmdir(path)
    return True


def sweep_stale_files(root, keep):
    """删掉 root 下「这次不再产出」的文件（增量清理，正常运行时一个都不删）。

    ⚠️ 用它取代「整目录 rmtree + 重建」：本机删除钩子单次约 0.6 s，
    重建 72 个目录要 48 s，会让 3 连跑的幂等校验直接超时被杀（SIGTERM）。
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


# ---------------------------------------------------------------- 内容生成

def plant_config_tres():
    """TowerDefensePlantConfig：字段顺序对齐原版 Gold/CatGatlingPea 配置。

    ⚠️ name 必须是「角色场景文件名」= CHAR_KEY：TowerDefensePacketConfig.Create()
    用 characterConfig.name 去查 ResourceManager.TOWERDEFENSE_CHARCATERS，
    而 mod 角色只能注册在 <Key> 这个键上（ModLoader.TryInferCharacterScene）。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefensePlantConfig" format=3]

[ext_resource type="Script" path="{BASE_PLANT_CONFIG_SCRIPT}" id="1"]

[resource]
script = ExtResource("1")
name = "{CHAR_KEY}"
hitpoints = {fmt_f(HITPOINTS)}
canCopy = false
damagePointData = null
armorData = null
customData = null
ashScene = null
homeWorld = 1
costRise = {COST_RISE}
cost = {COST}
packetCooldown = {fmt_f(PACKET_COOLDOWN)}
plantCover = ["PlantPeaShooter"]
maskFlags = 9
metadata/_custom_type_script = "{BASE_PLANT_CONFIG_SCRIPT}"
"""


def component_set_tres():
    """★ 2026-09-24 齐射改版：7 条 FireComponentFireProjectileConfig，一次 Fire() 全部打出。

    · 每条配置**仅 firePosId 不同**（0..6 → 7 个 Marker2D），speed / dir=0 /
      checkProjectileId 完全相同 ⇒ 7 颗的伤害、速度、碰撞行为与单发逐字一致。
    · 触发链 = 动画 f62 的 1 个 `fire` 事件 → `AnimeEvent`（fireEventName 默认 "fire"）
      → `FireConfiguredVolley()`（fireNumAtOnce=false ⇒ 恰好 1 次 `Fire()`）
      → `Fire()`（FireComponent.cs:3434）一次遍历全部 7 条 = 同帧齐射。
      参考狐尾草 HWC：`TowerDefensePlantHWCFireComponentDefinition.tres` 的多
      firePosMarkerPaths + `TowerDefensePlantHWC.FireVolley` 的一次性齐射循环。
    · `lockProjectileGridY = true`：把每颗豌豆的行锁死在种植行（FireComponent.cs:2743
      → BulletField.cs:1473/5598）⇒ 横向散布不改变「前方一行」的命中行为。
    """
    n = VOLLEY_COUNT
    # （VOLLEY_COUNT == PEAS_PER_ATTACK 的不变式在 self_check #0 断言 —— 生成与 --check 两条路都走它）

    lines = []
    lines.append('[gd_resource type="Resource" script_class="CharacterComponentSet" format=3]')
    lines.append('')
    lines.append(f'[ext_resource type="Resource" path="{BASE_FIRE_STATE_MACHINE}" id="1"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_AABBRAY_SCRIPT}" id="2"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_CREATEDATA_SCRIPT}" id="3"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_PROJ_SINGLE_SCRIPT}" id="4"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_CHECK_CONFIG_SCRIPT}" id="5"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_FIRE_CONFIG_SCRIPT}" id="6"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_FIRE_DEFINITION_SCRIPT}" id="7"]')
    lines.append(f'[ext_resource type="Resource" path="{BASE_PLANT_COMPONENT_SET}" id="8"]')
    lines.append(f'[ext_resource type="Script" path="{BASE_COMPONENT_SET_SCRIPT}" id="9"]')
    lines.append('')
    lines.append('[sub_resource type="Resource" id="Fire_AabbRay2DResource_forward"]')
    lines.append('script = ExtResource("2")')
    lines.append('')
    lines.append('[sub_resource type="Resource" id="Fire_Resource_createData"]')
    lines.append('script = ExtResource("3")')
    lines.append(f'projectileName = &"{PROJECTILE_NAME}"')
    lines.append('catapultHeight = 400.0')
    lines.append('')
    lines.append('[sub_resource type="Resource" id="Fire_Resource_single"]')
    lines.append('script = ExtResource("4")')
    lines.append('projectileData = SubResource("Fire_Resource_createData")')
    lines.append(f'metadata/_custom_type_script = "{BASE_PROJ_SINGLE_SCRIPT}"')
    lines.append('')
    lines.append('[sub_resource type="Resource" id="Fire_Resource_check"]')
    lines.append('script = ExtResource("5")')
    lines.append('projectile = SubResource("Fire_Resource_single")')
    lines.append(f'metadata/_custom_type_script = "{BASE_CHECK_CONFIG_SCRIPT}"')
    lines.append('')

    sub_ids = []
    for i in range(n):
        sid = f"Fire_Resource_proj{i}"
        sub_ids.append(sid)
        lines.append(f'[sub_resource type="Resource" id="{sid}"]')
        lines.append('script = ExtResource("6")')
        lines.append(f'speed = {PEA_SPEED}')
        lines.append('dir = 0.0')
        lines.append('checkProjectileId = 0')
        # 唯一的区别：从第 i 个 Marker 出膛（横向排开 ⇒ 互不重叠）
        lines.append(f'firePosId = {i}')
        lines.append(f'metadata/_custom_type_script = "{BASE_FIRE_CONFIG_SCRIPT}"')
        lines.append('')

    marker_paths = ", ".join(
        f'NodePath("SpriteGroup/TransformPoint/GatlingPea/Head/{nm}")'
        for nm in volley_marker_names())
    lines.append('[sub_resource type="Resource" id="FireDefinition"]')
    lines.append('script = ExtResource("7")')
    lines.append(f'firePosMarkerPaths = [{marker_paths}]')
    lines.append('spritePath = NodePath("SpriteGroup/TransformPoint/GatlingPea/Head")')
    lines.append('checkRayResources = [SubResource("Fire_AabbRay2DResource_forward")]')
    lines.append('fireAnimeClipsArray = ["HeadFire"]')
    lines.append('fireAnimeClips = "HeadFire"')
    lines.append('fireAnimeTimeScale = 3.0')
    lines.append('spliceIdleAnimeClips = "HeadIdle"')
    lines.append('isSpliceSprite = true')
    lines.append('fireNum = 1')
    # ⚠️ 刻意**不写** fireNumAtOnce：false（默认）⇒ FireConfiguredVolley() 恰好调 1 次
    #    Fire() ⇒ 7 条配置一次全打出 = 齐射。写 true + fireNum=1 语义相同，但会误导。
    # ⚠️ lockProjectileGridY = true：横向散布后子弹像素 Y 离开炮口线，BulletField 每帧按
    #    像素位置重算弹的行（BulletField.cs:1473）⇒ 不锁行会打进别的排；锁行后命中
    #    恒按种植行过滤（FireComponent.cs:2743 → overrides.gridYOverride ⇒ :5598）。
    lines.append('lockProjectileGridY = true')
    lines.append('fireCheckList = [SubResource("Fire_Resource_check")]')
    lines.append('fireProjectileList = [' + ", ".join(f'SubResource("{s}")' for s in sub_ids) + ']')
    lines.append('ComponentTypeId = "FireComponent"')
    lines.append(f'DefinitionId = "mod.{MOD_ID}.component.fire.character.plant.supergatlingpea"')
    lines.append('InstanceId = "character.fire"')
    lines.append('WireIndex = 0')
    lines.append('StateMachineDefinition = ExtResource("1")')
    lines.append('LegacyNodeNames = [&"FireComponent"]')
    lines.append('')
    lines.append('[resource]')
    lines.append('script = ExtResource("9")')
    lines.append('ParentSet = ExtResource("8")')
    lines.append('Components = [SubResource("FireDefinition")]')
    lines.append('')
    return "\n".join(lines)


def volley_marker_names():
    """齐射 Marker 节点名列表：Marker2D（中心，= 原发射点）+ Marker2D2..Marker2D{N}。"""
    return ["Marker2D"] + [f"Marker2D{i + 2}" for i in range(VOLLEY_COUNT - 1)]


def volley_marker_dx(index):
    """第 index 个 Marker（0 基）**沿弹道方向**（本地 +x）的偏移（px）。

    ★ index 0 = 原有的 Marker2D，**恒为 0**（它就是炮口点 MARKER2D_POS，13c-2 的
      「marker = 炮口 + Head.offset」恒等式钉在它身上，不能挪）。
    其余依次向前铺：+32, +64, +96, +128, +160, +192（7 颗共 192px 一条直线；
    间距 VOLLEY_SPACING=32px > 豌豆 28×28 ⇒ 相邻两颗不重叠）。

    ⚠️ 2026-09-24 **口径修正**：只沿 x 铺 —— 屏幕上是**一条水平直线（「一排」）**。
      旧口径沿 y 铺（0/±32/±64/±96）在屏幕上是**竖直一列**，用户明确否掉（「要一排，不是一列」）。
      向前（+x）而不是向后：Marker2D 的世界位在炮口，往后铺的 3 颗会落在植物身体里/背后，
      看起来像从植物后面冒出来。
    """
    return index * VOLLEY_SPACING * VOLLEY_FORWARD_SIGN


def plant_scene_tscn():
    """`Resources/Characters/Plants/<Key>/Scene/<Key>.tscn`（6 段硬约束）。

    ⚠️ 包内自引用全部走相对路径（docstring 第 8 条）：
      - `./{COMPONENT_SET_FILE}`  同目录
      - `../Config/{CFG_FILE}`    兄弟目录
    指向游戏自带资源（基础 Prefab / 脚本 / 碰撞盒 / 精灵场景）的引用保持 res://。
    ⚠️ 场景上 `fireNum = 1`（与原版 GatlingPea 一致）：`fireNumAtOnce=false`（默认）⇒
       FireConfiguredVolley() 恰好 1 次 `Fire()`，7 条配置一次全打出 = 齐射（见
       `component_set_tres` 的改版说明）。
    ★ 2026-09-19 起 `ExtResource("6")` 指向**自制精灵场景** `../Sprite/<Key>.tscn`
      （原来是 res:// 内置 GatlingPea.tscn）。
    ★ Marker2D 必须按**新素材**重算：内置的 (31.740002, -17.82) 是为旧素材标定的。
      公式 Marker2D = (anchor.muzzle - headOrigin) + Head.offset，推导见文件顶部常量块。
      保留节点名 `GatlingPea` 与路径 `.../GatlingPea/Head/Marker2D` —— ComponentSet 里
      写死了这条 NodePath，改名会断。
    ★ 2026-09-24 齐射改版：Head 下共 **7 个 Marker2D**（`volley_marker_names()`）。
      Marker2D 仍在炮口点 MARKER2D_POS；其余 6 个 = 炮口点 + (dx, 0)，dx = +32/+64/+96/+128/+160/+192
      （`volley_marker_dx`，**沿弹道方向**排成一条水平直线，y 全部相同 = 「一排」；
      间距 32px > 豌豆 28×28 ⇒ 齐射互不重叠）。
      ComponentSet 的 firePosMarkerPaths 与这里的节点名一一对应（firePosId = 数组下标）。
    """
    marker_nodes = []
    for i, nm in enumerate(volley_marker_names()):
        dx = volley_marker_dx(i)
        pos = "Vector2({}, {})".format(
            fmt_f(MARKER2D_POS[0] + dx), fmt_f(MARKER2D_POS[1]))
        marker_nodes.append(
            f'[node name="{nm}" type="Marker2D" parent="SpriteGroup/TransformPoint/GatlingPea/Head" index="{i}"]\n'
            f'position = {pos}\n')
    markers = "\n".join(marker_nodes)
    return f"""[gd_scene format=3]

[ext_resource type="PackedScene" path="{BASE_PLANT_SCENE}" id="1"]
[ext_resource type="Resource" path="./{COMPONENT_SET_FILE}" id="2"]
[ext_resource type="Script" path="res://Asset/Anime/Character/Plant/Cover/GatlingPea/Scene/TowerDefensePlantGatlingPea.cs" id="3"]
[ext_resource type="Resource" path="res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_44x70_At_0_0.tres" id="4"]
[ext_resource type="Resource" path="../Config/{CFG_FILE}" id="5"]
[ext_resource type="PackedScene" path="../Sprite/{SPRITE_FILE}" id="6"]

[node name="{CHAR_KEY}" node_paths=PackedStringArray("sprite") instance=ExtResource("1")]
ComponentSet = ExtResource("2")
script = ExtResource("3")
HitBoxDefinition = ExtResource("4")
fireInterval = {FIRE_INTERVAL}
fireNum = 1
projectileName = "{PROJECTILE_NAME}"
idleAnimeClip = "BodyIdle"
config = ExtResource("5")
sprite = NodePath("SpriteGroup/TransformPoint/GatlingPea")
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "{PLANT_CN_NAME}"
metadata/mod_character_category = "Plant"
metadata/mod_character_config_path = "../Config/{CFG_FILE}"
metadata/mod_character_sprite_scene = "../Sprite/{SPRITE_FILE}"

[node name="ShadowSprite" parent="." index="0"]
position = Vector2(0, 30)

[node name="TransformPoint" parent="SpriteGroup" parent_id_path=PackedInt32Array(1006029617) index="0"]
position = Vector2(0, 30)

[node name="GatlingPea" parent="SpriteGroup/TransformPoint" index="0" instance=ExtResource("6")]
position = Vector2(0, -30)
trueFrameRate = 180.0

[node name="Head" parent="SpriteGroup/TransformPoint/GatlingPea" index="0"]
trueFrameRate = 180.0

{markers}[editable path="SpriteGroup/TransformPoint/GatlingPea"]
"""


def sprite_scene_tscn():
    """`Resources/Characters/Plants/<Key>/Sprite/<Key>.tscn`（6 段，文件夹==文件名==<Key>）。

    ⚠️ 没有这个文件就没有 CHARACTER_SPRITE[<Key>]，XWModContentValidation 会 throw。

    ★ 2026-09-20 起改为**官方素材直转**（不再是自制图集）：
      与内置 GatlingPea.tscn 同构的「根 + Head 双精灵共用一份 AnimeData」范式。
        根    : clip=BodyIdle（0..24，只画茎叶）/ 显示全部图层（头部图层在 BodyIdle 段本就不可见）
        Head  : clip=HeadIdle（25..49，只画头）/ parentSprite 指回根
      脚本必须用 `res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs`
      （addons/ 下的 AdobeAnimateSprite.cs 在 mod 包内不可用）。

    ⚠️ 内置做法：两边的 `Animation/LayerVisible/*` **全写 true** —— 可见性由 clip 段决定
      （body 件在 25..86 的 f=-1 ⇒ 不产 slice），不是靠 LayerVisible 关。照抄。
    ⚠️ `LayerVisible` / `MediaReplace` 的键**必须是图层名 / 媒体名**（不是索引），
      且键按 ASCII 序书写（Godot 保存 .tscn 时的实际排法，内置一致）。
    ⚠️ Head 的 `insertLayerId = followParentSpriteLayerId = max(body 图层)+1`
      （本 Mod = 16 = `anim_idle` 层）。内置 11 例全部遵守该式
      （PeaShooter/GatlingPea/…=8、ReCactus=11、SunflowerPea=5、ThreeCactus=9）。
      语义：把「头」整棵子树插到茎叶之上的排序带 ⇒ 头压在茎叶上（内置同款观感）。
    ⚠️ `insertLayerId` 必须落在 `[0, 图层数)` 内，否则 AutoInsertChildSprites 直接跳过。
    """
    p = skin_params()
    layer_keys = sorted(list(p["layer_names"]) + ["AnimeClips", "AnimeEvents"])
    media_keys = sorted(p["media_names"])
    vis = "\n".join(f"Animation/LayerVisible/{k} = true" for k in layer_keys)
    med = "\n".join(f"Animation/MediaReplace/{k} = null" for k in media_keys)
    ins = int(p["insert_layer_id"])
    root_off = "Vector2({}, {})".format(fmt_f(ROOT_OFFSET[0]), fmt_f(ROOT_OFFSET[1]))
    head_off = "Vector2({}, {})".format(fmt_f(HEAD_OFFSET[0]), fmt_f(HEAD_OFFSET[1]))
    hp = head_position()
    head_pos = "Vector2({}, {})".format(fmt_f(hp[0]), fmt_f(hp[1]))
    return f"""[gd_scene load_steps=4 format=3]

[ext_resource type="Script" path="{SPRITE_BASE_SCRIPT}" id="1_root"]
[ext_resource type="Resource" path="{anim_tres_res()}" id="2_data"]
[ext_resource type="Script" path="{SPRITE_BASE_SCRIPT}" id="3_base"]

[node name="{CHAR_KEY}Sprite" type="Node2D"]
script = ExtResource("1_root")
flashAnimeData = ExtResource("2_data")
useMultiMesh = true
offset = {root_off}
useTween = false
Animation/Clip = "BodyIdle"
{vis}
{med}
metadata/mod_resource_kind = "CharacterSprite"
metadata/mod_preview_source = "官方素材直转：未重置版 SuperGatling.reanim.compiled {p['layer_count']} 轨 × {p['frame_max']} 帧，头身分离 3 clip"

[node name="Head" type="Node2D" parent="." node_paths=PackedStringArray("parentSprite")]
unique_name_in_owner = true
position = {head_pos}
script = ExtResource("3_base")
flashAnimeData = ExtResource("2_data")
useMultiMesh = true
offset = {head_off}
useTween = false
skipLastFrame = false
parentSprite = NodePath("..")
Animation/Clip = "HeadIdle"
{vis}
{med}
Layer = {ins}
insertLayerId = {ins}
followParentSpriteLayerId = {ins}
metadata/mod_resource_kind = "CharacterSprite"
"""


def packet_tres(config_rel):
    """卡片：**文案全部内联**（name / describe / handbookDescribe / handbookStory）。
    ⚠️ 为什么不走翻译键（2026-09-25 修正，上一版是写 key）：ModLoader 运行时**不会**加载
    Mod 的 `Localization/translations.csv`（见 translation_file() 的三条证据）⇒ 写 key 就显示 key。
    三闸门（docstring 第 10-11 条 + XWModContentValidation）：
      - `saveKey` 必须 == 注册键 == 卡片文件名去扩展 == `{CHAR_KEY}`
      - `characterConfig` 必须能加载，且它的 name 已注册进 TOWERDEFENSE_CHARACTERS
      - `unlockCheckList` 必须为空表（放游戏内条件会被判「必须使用 Mod 专属解锁条件」）
    `config_rel`：本文件所在目录到 Config 的相对路径（两处分发目录深度不同）。

    ⚠️ `.tres` 多行字符串：直接写**真实换行**（官方的 `Challenge_Level13_3.tres` 同款写法），
    Godot 的 VariantParser 支持引号内跨行；**不要**写 `\\n` 转义（会原样显示成反斜杠 n）。
    面板侧对应 `InformationPanel.cs:228-234`：
      nameLabel ← name ｜ expressionLabel ← `[color=2f375e]{describe}[/color]`（面板自己包色）
      handbookExpressionLabel ← handbookDescribe ｜ handbookStoryLabel ← handbookStory
    即 `describe` **不能**自己再加颜色标签，加了会嵌套。

    「能直接种在空地上」= 内联一个 TowerDefensePacketOverride 子资源并只开
    `coverCanDirectPlant = true`。写法照抄官方 Gold 挑战关
    `Asset/Config/Level/TowerDefense/Challenge/Gold/Challenge_Level2_3.tres`
    （它给 PlantGatlingPot 开的就是这个开关）。
    ⚠️ 其余字段一律不写 ⇒ 用类默认值，而默认值全部是「不覆盖」语义：
      type=NOONE / cost=-1 / costRise=-1 / packetCooldown=-1 / startingCooldown=-1 /
      weight=-1 / wavePointCost=-1 / plantCover=[] / hypnoses=false
      ⇒ 各 GetXxx() 都会回落到 characterConfig 的值；
      islimitGridNum 默认 true，与无 override 时的硬编码 true 一致。
    唯一无条件生效的是 `characterOverride`（默认值 `new TowerDefenseCharacterOverride()`，
    非 null 但 **全是空操作**：scale/hitpointScale/walkSpeedScale/animeSpeedScale 都是 -1、
    各数组为空、invisible=false）⇒ 不会碰血量、缩放、动画。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefensePacketConfig" format=3]

[ext_resource type="Resource" path="{config_rel}" id="1"]
[ext_resource type="Script" path="{BASE_PACKET_SCRIPT}" id="2"]
[ext_resource type="Script" path="{BASE_PACKET_OVERRIDE_SCRIPT}" id="3"]

[sub_resource type="Resource" id="PacketOverride_direct_plant"]
script = ExtResource("3")
coverCanDirectPlant = {str(COVER_CAN_DIRECT_PLANT).lower()}
metadata/_custom_type_script = "{BASE_PACKET_OVERRIDE_SCRIPT}"

[resource]
script = ExtResource("2")
saveKey = "{CHAR_KEY}"
unlockCheckList = []
name = "{PLANT_CN_NAME}"
describe = "{PLANT_CN_DESC}"
handbookDescribe = "{PLANT_CN_HANDBOOK_DESC}"
handbookStory = "{PLANT_CN_STORY}"
packetAnimeClip = "BodyIdle"
packetAnimeOffset = Vector2(21, 23)
packetAnimeScale = Vector2(0.5, 0.5)
characterConfig = ExtResource("1")
type = {PACKET_TYPE}
override = SubResource("PacketOverride_direct_plant")
metadata/_custom_type_script = "{BASE_PACKET_SCRIPT}"
"""


def build_manifest():
    """manifest 键序必须严格等于 XWModManifestSerializeHandler 的顺序。

    ⚠️ provides 里出现的每个 key 都必须真的被注册，否则
    ModLoader.ValidateManifestRegistrations 判定失败 → 整包 apply 失败。
    ModLoader 推导出的 key：
      - Character       = `Resources/Characters/Plants/<Key>/Scene/<Key>.tscn` 的 <Key>
      - CharacterSprite = `Resources/Characters/Plants/<Key>/Sprite/<Key>.tscn` 的 <Key>
      - Packet          = `Resources/Cards/<文件名去扩展>`（不是目录/角色名！）
    三者在（含 sprite）本包统一为 `{CHAR_KEY}`。

    resources 的顺序 = XWModManifestSyncService.SyncProject 的规范序（OrdinalIgnoreCase 升序）：
    它会把工程目录里所有非忽略文件按 GetManifestSection 归类后 NormalizePathList 排序，
    顺序不对 ⇒ 编辑器一打开工程就重写 mod.json（与 build_map_vampire_pool.py 同一处理）。
    所以这里**用 sorted(key=lower) 生成**，而不是手写列表。
    ⚠️ `Runtime/ModAssembly.dll` 也会落进 Resources 段（它不是可推导类别），必须一起排序声明。
    """
    return {
        "schemaVersion": 2,
        "id": MOD_ID,
        "name": MOD_NAME,
        "version": "1.0.0",
        "author": "云漫行",
        "description": (
            f"新增植物「{PLANT_CN_NAME}」：每 1.5 秒向前方一次齐射 7 颗豌豆（横向排开、互不重叠）；"
            f"每次攻击有 10% 概率触发大招 —— 5 秒内倾泻约 300 颗豌豆。"
            f"金卡，{COST} 阳光，冷却 {fmt_f(PACKET_COOLDOWN)} 秒。"
            f"（含托管运行时插件 Runtime/ModAssembly.dll）"
        ),
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
        "translations": ["Localization/translations.csv"],
        "resources": sorted([
            ANIM_DAT_REL,          # 自制外观三件套：图集源（渲染必需）
            ANIM_TRES_REL,         #                自描述 packed 数组
            ANIM_PNG_REL,          #                仅供人眼/工具查看，运行时不用
            CARD_REL,
            f"{PKG_REL}/Config/{CFG_FILE}",
            f"{PKG_REL}/Packet/{CHAR_KEY}.tres",
            f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}",
            f"{PKG_REL}/Scene/{SCENE_FILE}",
            f"{PKG_REL}/Sprite/{SPRITE_FILE}",
            RUNTIME_ASSEMBLY,
        ], key=lambda p: p.lower()),
    }


def translation_file():
    """`Localization/translations.csv` —— **只对编辑器内的「多语言」面板有用**。

    ⚠️ 诚实说明（2026-09-25 全链路复核，别再指望它）：
      · ModLoader 全文没有任何 `TranslationServer.AddTranslation` 调用；
      · `project.godot` 只挂内置的 `res://Asset/Translate/Translate.{en,es,zh}.translation`；
      · ModLoader 解包后的 `.csv` 也不在可解析扩展名白名单里
        （`ModLoader.cs:1006 TryResolveDeclaredResourceCandidate`）；
      · manifest 的 `translations` 字段只在 schema 校验 / 同步服务 / 引用图里被读写。
      ⇒ **游戏运行时不会加载这份 CSV**；字段里写 key 就显示 key。
      正因如此，2026-09-25 起 packet 的四个文案字段已改成**内联字面量**，
      本表退化为「编辑器里给英文留个底」。

    ⚠️ 键 = **内联的中文原文本身**（不再是 `TOWERDEFENSE_*` 那些 key —— 那些已全部废弃）。
    ⚠️ 只收录**单行**文案：`handbookDescribe` / `handbookStory` 是多行 + 含 `[color=...]`
       标签，塞进朴素 CSV 会破坏行结构，故**不收录**（它们只以中文内联形式存在）。
    表头与 locale 取值（zh_CN/en_US）对齐 `XWLocalizationTable.SaveToCsvFile()`，
    key 按 OrdinalIgnoreCase 升序（同步服务的规范序）。
    """
    rows = [
        (PLANT_CN_NAME, PLANT_CN_NAME, PLANT_EN_NAME),
        (PLANT_CN_DESC, PLANT_CN_DESC, PLANT_EN_DESC),
    ]
    rows.sort(key=lambda r: r[0].lower())
    out = ["key,zh_CN,en_US"]
    for k, zh, en in rows:
        out.append(f"{k},{zh},{en}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------- 组装

def ensure_project_layout(project_dir):
    n = 0
    for d in STANDARD_DIRS:
        os.makedirs(os.path.join(project_dir, d.replace("/", os.sep)), exist_ok=True)
        n += 1
    return n


def build_project_file(existing=None):
    """⚠️ 幂等要求：LastModifiedDate 必须「读回旧值」，不能写 now。

    否则每次运行都会改字节，与 build_map_vampire_pool.py 的字节幂等约定冲突。
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
        "Description": f"新增植物「{PLANT_CN_NAME}」（数据 + 托管运行时插件）",
        # ⚠️ 必须和编辑器自己写出的形态一致：**正斜杠 + 结尾斜杠**
        #    （ModProject.cs:79 默认值 = GlobalizePath("user://Mods/")；实测 新地图-1/吸血鬼屋泳池 都是这个形态）
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
    """把工程目录增量镜像到 Mods/ 下（与 build_map_vampire_pool.py 行为一致）。

    安全护栏：mirror_is_ours() 判定不是我们的目录 → 跳过不动。
    dst 里不放 .pmod，所以不污染 ScanMods(*.pmod)。
    """
    if not mirror_is_ours(dst, marker):
        return "跳过（%s 已存在且不是本工程，未改动）" % dst
    wrote, removed = sync_tree(src, dst, marker)
    return "已镜像到 %s（写 %d / 删 %d）" % (dst, wrote, removed)


def merge_enabled_mods(mods_dir, mod_id):
    p = os.path.join(mods_dir, "enabled_mods.json")
    ids = []
    if os.path.isfile(p):
        try:
            v = read_json(p)
            if isinstance(v, list):
                ids = [x for x in v if isinstance(x, str)]
        except Exception:
            ids = []
    if mod_id not in ids:
        ids.append(mod_id)
    ids = sorted(set(x.strip() for x in ids if x.strip()), key=lambda s: s.lower())
    write_text(p, json.dumps(ids, ensure_ascii=False, indent=2), "\n")
    return ids


def merge_recent_project(project_file_abs):
    """把工程登记进编辑器「最近工程」缓存（`mod_editor_recent_projects.cfg`，与 `Mods/` 同级）。

    ⚠️ 三个必须守住的点（2026-09-18 实测踩过，别改回去）：
      1. **不能丢别人的条目**：旧写法用 `^path_\\d+="(.*)"$` 匹配行尾，而本文件是 CRLF 时
         行尾是 `\\r\\n` → **一条都匹配不到** → 于是把整个列表重写成「只剩自己一条」。
         实测：跑一次 `build_map_vampire_pool.py` 就把本工程那条抹掉了。
         ⇒ 解析前必须先把 CRLF 归一化成 LF。
      2. 路径一律写**正斜杠**：编辑器自己就写 `C:/…/Mods/<工程>.pvzmodeproject`。
         而且登记的是 **Mods 下**那份工程（编辑器也只认这个位置），不是工作区里的构建目录。
      3. 保留原文件的换行风格与末尾换行，别顺手把别人的文件格式改了。
    """
    cfg = os.path.join(USER_DATA_DIR, "mod_editor_recent_projects.cfg")
    if not os.path.isfile(cfg):
        return None
    with open(cfg, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig", "replace").replace("\r\n", "\n").replace("\r", "\n")
    trailing = text.endswith("\n")
    # 统一成正斜杠 + 去重（大小写不敏感，Windows 语义）
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


def _dat_pascal_string(buf, off):
    """`.dat` 里的字符串 = u32 长度前缀 + UTF-8 字节（AdobeAnimateData.cs:1004-1012）。"""
    n = int.from_bytes(buf[off:off + 4], "little")
    off += 4
    return buf[off:off + n].decode("utf-8"), off + n


def _dat_locate_clip_table(dat):
    """按 AdobeAnimateData.cs 的读取顺序（:1041-1081）逐段走 `.dat`，返回
    (clips 字典, {clip名: (start字节偏移, end字节偏移)})。

    段序：头 18B → 像素区 → u16 媒体数×(名字+Rect2 16B) → u16 图层数×
    (名字 + frameMax×(u16 元素数 + 元素数×30B)) → u16 clip 数×(名字+u16+u16)。
    解析终点必须恰好 == 文件长（差一个字节都说明段落走错了，立刻抛错）。
    """
    frame_max = int.from_bytes(dat[4:6], "little")
    pixel_len = int.from_bytes(dat[10:18], "little")
    off = 18 + pixel_len
    media_n = int.from_bytes(dat[off:off + 2], "little"); off += 2
    for _ in range(media_n):
        _, off = _dat_pascal_string(dat, off)
        off += 16
    layer_n = int.from_bytes(dat[off:off + 2], "little"); off += 2
    for _ in range(layer_n):
        _, off = _dat_pascal_string(dat, off)
        for _f in range(frame_max):
            n = int.from_bytes(dat[off:off + 2], "little"); off += 2
            off += n * 30
    clip_n = int.from_bytes(dat[off:off + 2], "little"); off += 2
    clips, spans = {}, {}
    for _ in range(clip_n):
        name, o2 = _dat_pascal_string(dat, off)
        start = int.from_bytes(dat[o2:o2 + 2], "little")
        end = int.from_bytes(dat[o2 + 2:o2 + 4], "little")
        clips[name] = (start, end)
        spans[name] = (o2, o2 + 4)
        off = o2 + 4
    ev_n = int.from_bytes(dat[off:off + 2], "little"); off += 2
    for _ in range(ev_n):
        cnt = int.from_bytes(dat[off + 2:off + 4], "little"); off += 4
        for _k in range(cnt):
            _, off = _dat_pascal_string(dat, off)
            _, off = _dat_pascal_string(dat, off)
    if off != len(dat):
        raise ValueError(f".dat 段落解析终点 {off} != 文件长 {len(dat)}（布局与引擎读取顺序不符）")
    return clips, spans


def _patch_skin_for_plant(dat_bytes, tres_bytes):
    """把「共享三件套」补丁成植物包口径：HeadFire (50,86) → (50,74)（抽搐修复）。

    ⚠️ 共享源（`../.cache/`）同时喂给僵尸包《超级机枪读报僵尸》（它的 HeadFire 必须
      保持 (50,86)，大招段要循环播），所以**只能改包内副本**，动不了共享源。
    - `.tres`：clips 字典文本替换（1 处，断言恰好命中 1 次）。
    - `.dat`：clip 表里 HeadFire 的 end u16（86→74）—— **等长补丁**，事件段等
      后续字节零位移；打补丁前先整文件走一遍段落解析（上面 _dat_locate_clip_table，
      终点==文件长才动手），补丁后复读校验。
    """
    old_s, old_e = 50, 86
    new_s, new_e = HEADFIRE_CLIP_PLANT
    if (new_s, new_e) == (old_s, old_e):
        return dat_bytes, tres_bytes
    # ---- .tres ----
    tres = tres_bytes.decode("utf-8")
    old_line = f'"HeadFire": Vector2i({old_s}, {old_e})'
    new_line = f'"HeadFire": Vector2i({new_s}, {new_e})'
    if tres.count(old_line) != 1:
        raise ValueError(f".tres 里 {old_line!r} 出现 {tres.count(old_line)} 次（应恰好 1 次），拒绝补丁")
    tres = tres.replace(old_line, new_line)
    # ---- .dat ----
    clips, spans = _dat_locate_clip_table(dat_bytes)
    if clips.get("HeadFire") != (old_s, old_e):
        raise ValueError(f".dat clip 表 HeadFire={clips.get('HeadFire')}，期望 {(old_s, old_e)}，拒绝补丁")
    s_off, e_off = spans["HeadFire"]
    if int.from_bytes(dat_bytes[s_off:s_off + 2], "little") != new_s:
        raise ValueError(".dat clip 表 HeadFire.start 与期望不符")
    dat = bytearray(dat_bytes)
    dat[e_off - 2:e_off] = new_e.to_bytes(2, "little")
    dat = bytes(dat)
    got, _ = _dat_locate_clip_table(dat)
    if got.get("HeadFire") != (new_s, new_e):
        raise ValueError(".dat 补丁后复读校验失败")
    return dat, tres.encode("utf-8")


def sync_skin_assets():
    """把 .cache 下的**官方素材直转三件套**同步进包内 `Resources/Animations/`。

    ⚠️ 这三件套是二进制（.dat 内嵌图集）/ 自描述文本（.tres），**不由本脚本生成**，
      而由 .cache/build_official_skin.py 一次性产出（经典 reanim → 重置版）：
         build_official_skin.py -> SuperGatlingPeaAtlas.png + SuperGatlingPea.dat
                                 + SuperGatlingPea.tres + skin_params.json

    幂等：只在字节不同时才写（避免每次运行都改 mtime / 破坏「3 连跑字节稳定」）。
    返回实际同步的包内相对路径列表；源文件缺失则抛错（不静默跳过）。
    ★ 2026-09-24：同步时对 .dat/.tres 应用植物包 clip 补丁（HeadFire→(50,74)，
      见 _patch_skin_for_plant / HEADFIRE_CLIP_PLANT）；图集 PNG 不受影响。
    """
    映射 = [(os.path.join(SKIN_SRC_DIR, f"{ANIM_BASENAME}.dat"), ANIM_DAT_REL),
            (os.path.join(SKIN_SRC_DIR, f"{ANIM_BASENAME}.tres"), ANIM_TRES_REL),
            (os.path.join(SKIN_SRC_DIR, f"{ANIM_BASENAME}Atlas.png"), ANIM_PNG_REL)]
    loaded = {}
    for src, rel in 映射:
        if not os.path.isfile(src):
            raise FileNotFoundError(
                f"缺外观源文件 {src}\n"
                f"请先运行：.cache/build_official_skin.py"
            )
        with open(src, "rb") as f:
            loaded[rel] = f.read()
    # 植物包 clip 补丁（.dat 与 .tres 必须同步改，二者输入输出成对处理）
    dat_patched, tres_patched = _patch_skin_for_plant(loaded[ANIM_DAT_REL], loaded[ANIM_TRES_REL])
    loaded[ANIM_DAT_REL] = dat_patched
    loaded[ANIM_TRES_REL] = tres_patched
    done = []
    for _src, rel in 映射:
        if write_bytes_if_changed(_abs(rel), loaded[rel]):
            done.append(rel)
    return done


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
            # ⚠️ 隐藏文件一律不打包（游戏侧工程目录里可能有、包里不该有）
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
            if not os.path.isfile(full):     # 隐藏文件（如 .generated）不打包
                continue
            with open(full, "rb") as f:
                z.writestr(zi, f.read())
    return entries


# ---------------------------------------------------------------- 自检

def self_check():
    fails = []
    hp_expect = head_position()
    txt = component_set_tres()
    sc = plant_scene_tscn()
    sp = sprite_scene_tscn()
    cfg = plant_config_tres()
    pk_card = packet_tres(f"../Characters/Plants/{CHAR_KEY}/Config/{CFG_FILE}")
    pk_pkg = packet_tres(f"../Config/{CFG_FILE}")

    # 1. ★ 2026-09-24 齐射改版：恰好 VOLLEY_COUNT 条发射配置，dir 恒为 0（仅直线）
    dirs = [float(x) for x in re.findall(r"^dir = (-?[\d.]+)$", txt, re.M)]
    if len(dirs) != VOLLEY_COUNT:
        fails.append(f"dir 条数 {len(dirs)} != {VOLLEY_COUNT}")
    if any(abs(d) > 1e-9 for d in dirs):
        fails.append(f"常规攻击必须全是直线 dir=0，实为 {dirs}")
    # 2. fireProjectileList 恰 VOLLEY_COUNT 项；firePosId 恰好 0..6 各一次；
    #    **不得**出现 fireNumAtOnce（false=默认 ⇒ FireConfiguredVolley 恰好 1 次 Fire()）；
    #    必须 lockProjectileGridY = true（散布后锁行，命中恒按种植行过滤）
    sub_refs = re.findall(r'fireProjectileList = \[(.*?)\]', txt, re.S)
    if len(sub_refs) != 1:
        fails.append("ComponentSet 的 fireProjectileList 应恰好 1 行")
    else:
        refs = re.findall(r'SubResource\("([^"]+)"\)', sub_refs[0])
        if refs != [f"Fire_Resource_proj{i}" for i in range(VOLLEY_COUNT)]:
            fails.append(f"fireProjectileList 应依次引用 proj0..proj{VOLLEY_COUNT - 1}，实为 {refs}")
    pos_ids = [int(x) for x in re.findall(r"^firePosId = (\d+)$", txt, re.M)]
    if sorted(pos_ids) != list(range(VOLLEY_COUNT)):
        fails.append(f"firePosId 应恰好 0..{VOLLEY_COUNT - 1} 各一次，实为 {sorted(pos_ids)}")
    if "fireNumAtOnce" in txt:
        fails.append("不应出现 fireNumAtOnce（默认 false ⇒ 恰好 1 次 Fire() = 一次齐射）")
    if "lockProjectileGridY = true" not in txt:
        fails.append("缺 lockProjectileGridY = true（散布子弹必须锁行，否则每帧按像素重算行会打进别的排）")
    # 2b. firePosMarkerPaths 必须恰好 VOLLEY_COUNT 条，且与 volley_marker_names() 一一对应
    mp = re.search(r'firePosMarkerPaths = \[(.*?)\]', txt, re.S)
    if not mp:
        fails.append("缺 firePosMarkerPaths")
    else:
        got_paths = re.findall(r'NodePath\("([^"]+)"\)', mp.group(1))
        want_paths = [f"SpriteGroup/TransformPoint/GatlingPea/Head/{nm}"
                      for nm in volley_marker_names()]
        if got_paths != want_paths:
            fails.append(f"firePosMarkerPaths 应为 {want_paths}，实为 {got_paths}")
    # 3. 场景 fireInterval / fireNum=1（7 颗 = 7 条配置被一次 Fire() 全打出 = 齐射）
    if f"fireInterval = {FIRE_INTERVAL}" not in sc:
        fails.append("场景 fireInterval 不符")
    if "fireNum = 1\n" not in sc:
        fails.append("场景 fireNum 应为 1")
    # 4. 6 段路径约束（Scene 与 Sprite 两条）
    for folder, fn in (("Scene", SCENE_FILE), ("Sprite", SPRITE_FILE)):
        parts = f"{PKG_REL}/{folder}/{fn}".split("/")
        if len(parts) != 6:
            fails.append(f"{folder} 路径段数 {len(parts)} != 6")
        if parts[3] != CHAR_KEY or parts[5] != CHAR_KEY + ".tscn":
            fails.append(f"{folder} 路径/文件名与 key 不一致：{parts}")
    # 5. ⚠️ res:// 只允许指向**游戏自带资源**（docstring 第 8 条）：
    #      ModLoader 把 .pmod 挂到游戏根的派生目录下，res:// 解析不到包内资源
    #      ⇒ 包内自引用一律相对路径（./xxx 或 ../xxx）。
    #      例外：.tres/.res 里的 [ext_resource type="Script"] 必须 res://（下面的规则 6 单独管）。
    #      注意：只扫 [ext_resource ...] 行 —— 节点属性里的 path="SpriteGroup/..." 是 NodePath，不是资源路径。
    game_ok = ("res://Prefab/", "res://Asset/", "res://Script/", "res://Resource/",
               "res://Registry/", "res://Extends/")
    for name, body in (("ComponentSet", txt), ("Scene", sc), ("Sprite", sp),
                       ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for line in body.splitlines():
            if not line.lstrip().startswith("[ext_resource"):
                continue
            m = re.search(r'path="([^"]+)"', line)
            if not m:
                continue
            path = m.group(1)
            if path.startswith("res://"):
                if not path.startswith(game_ok):
                    fails.append(f"{name} 的 res:// 引用不是游戏自带资源：{path}")
            elif path.startswith("user:/") or ":" in path.split("/")[0]:
                fails.append(f"{name} 含绝对/非法引用：{path}")
            elif not (path.startswith("./") or path.startswith("../")):
                fails.append(f"{name} 的包内引用既非 res:// 也非相对路径：{path}")
    # 6. .tres 里的 Script 引用必须是 res://（.tres 非 res:// 会被直接拒绝）
    for name, body in (("ComponentSet", txt), ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for line in body.splitlines():
            if "[ext_resource" in line and 'type="Script"' in line:
                m = re.search(r'path="([^"]+)"', line)
                if not (m and m.group(1).startswith("res://")):
                    fails.append(f"{name} 的 Script 引用非 res://：{line.strip()}")
    # 7. 不得内嵌脚本 / 不得有 .scn/.res 依赖
    for name, body in (("ComponentSet", txt), ("Scene", sc), ("Sprite", sp),
                       ("Config", cfg), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        if 'type="CSharpScript"' in body or 'type="GDScript"' in body:
            fails.append(f"{name} 含内嵌脚本")
    # 8. 配置数值（用户指定）
    if f"cost = {COST}" not in cfg:
        fails.append(f"cost 应为 {COST}")
    if f"costRise = {COST_RISE}" not in cfg:
        fails.append(f"costRise 应为 {COST_RISE}")
    if f"packetCooldown = {fmt_f(PACKET_COOLDOWN)}" not in cfg:
        fails.append(f"packetCooldown 应为 {fmt_f(PACKET_COOLDOWN)}")
    if f'name = "{CHAR_KEY}"' not in cfg:
        fails.append("config.name 必须等于角色场景文件名（TOWERDEFENSE_CHARCATERS 的键）")
    # 8b. 血量 + 可种植性（2026-09-19 用户指定）
    if f"hitpoints = {fmt_f(HITPOINTS)}" not in cfg:
        fails.append(f"config.hitpoints 应为 {fmt_f(HITPOINTS)}")
    #     顺序：TowerDefenseCharacterConfig 里 hitpoints 紧跟 name（hitpointsNearDeath=0 被省略）
    if cfg.index(f"hitpoints = {fmt_f(HITPOINTS)}") < cfg.index(f'name = "{CHAR_KEY}"'):
        fails.append("hitpoints 必须写在 name 之后（对齐类声明顺序，防编辑器重排）")
    # 9. 卡片三闸门
    for name, body in (("Card", pk_card), ("PkgPacket", pk_pkg)):
        if f'saveKey = "{CHAR_KEY}"' not in body:
            fails.append(f"{name} 的 saveKey 必须等于注册键 {CHAR_KEY}")
        if f"type = {PACKET_TYPE}" not in body:
            fails.append(f"{name} 的 type 应为 {PACKET_TYPE}(GOLD)")
        if "unlockCheckList = []" not in body:
            fails.append(f"{name} 的 unlockCheckList 必须为空表（XWModContentValidation）")
        if 'characterConfig = ExtResource("1")' not in body:
            fails.append(f"{name} 缺 characterConfig 绑定")
        # 9b. 「能直接种在空地上」的开关：必须是内联 override，且只开 coverCanDirectPlant
        if COVER_CAN_DIRECT_PLANT:
            if 'override = SubResource("PacketOverride_direct_plant")' not in body:
                fails.append(f"{name} 的 override 必须指向内联的 PacketOverride_direct_plant")
            if "[sub_resource type=\"Resource\" id=\"PacketOverride_direct_plant\"]" not in body:
                fails.append(f"{name} 缺 PacketOverride_direct_plant 子资源")
            if 'coverCanDirectPlant = true' not in body:
                fails.append(f"{name} 必须开 coverCanDirectPlant = true（否则只能种在双发射手上）")
            # 其余字段绝不能写：写了就可能顶掉 characterConfig 的正常取值
            sub = body.split('[sub_resource type="Resource" id="PacketOverride_direct_plant"]')[1]
            sub = sub.split("[resource]")[0]
            extra = [ln.strip() for ln in sub.splitlines()
                     if ln.strip() and not ln.startswith(("script =", "coverCanDirectPlant", "metadata/", "["))]
            if extra:
                fails.append(f"{name} 的 packet override 只允许写 coverCanDirectPlant，多了：{extra}")
            if f'path="{BASE_PACKET_OVERRIDE_SCRIPT}"' not in body:
                fails.append(f"{name} 缺 TowerDefensePacketOverride 脚本引用")
        else:
            if "override = null" not in body:
                fails.append(f"{name} 的 override 应为 null")
    # 10. manifest：键序 / provides 与 resources
    mf = build_manifest()
    if list(mf.keys()) != MANIFEST_KEYS:
        fails.append("manifest 键序不符")
    if set(mf["provides"]) & set(mf["overrides"]):
        fails.append("provides/overrides 键冲突")
    for cat in ("Character", "CharacterSprite", "Packet"):
        if mf["provides"].get(cat) != [CHAR_KEY]:
            fails.append(f"provides.{cat} 应为 [{CHAR_KEY}]")
    need = {
        ANIM_DAT_REL,
        ANIM_TRES_REL,
        ANIM_PNG_REL,
        CARD_REL,
        f"{PKG_REL}/Config/{CFG_FILE}",
        f"{PKG_REL}/Scene/{SCENE_FILE}",
        f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}",
        f"{PKG_REL}/Sprite/{SPRITE_FILE}",
        f"{PKG_REL}/Packet/{CHAR_KEY}.tres",
        RUNTIME_ASSEMBLY,
    }
    if set(mf["resources"]) != need:
        fails.append(f"manifest.resources 与预期不符：差集 {set(mf['resources']) ^ need}")
    # 10b. 托管运行时四字段（docstring「插件」一节 a-d；改错 = 整包被拒，不是「不生效」）
    if mf["runtimeAssembly"] != RUNTIME_ASSEMBLY:
        fails.append(f"runtimeAssembly 必须是字面量 {RUNTIME_ASSEMBLY!r}（ModLoader 字符串相等判定）")
    if mf["runtimeEntryType"] != RUNTIME_ENTRY_TYPE:
        fails.append(f"runtimeEntryType 应为 {RUNTIME_ENTRY_TYPE!r}")
    if mf["runtimeApiVersion"] != 1:
        fails.append("runtimeApiVersion 必须恰好是 1")
    if mf["runtimeAssemblyPolicy"] != "optional":
        fails.append("runtimeAssemblyPolicy 应为 \"optional\"（加载失败不连坐整包）")
    # 10c. resources 必须已是 SyncProject 规范序（OrdinalIgnoreCase 升序），否则编辑器会重写 mod.json
    order = [p.lower() for p in mf["resources"]]
    if order != sorted(order):
        fails.append(f"resources 不是 OrdinalIgnoreCase 升序：{mf['resources']}")
    if RUNTIME_ASSEMBLY in mf["resources"] and not os.path.isfile(_abs(RUNTIME_ASSEMBLY)):
        fails.append(
            "缺 Runtime/ModAssembly.dll —— 先跑 python runtime_src_plant/build_runtime.py --check"
        )
    # 11. 注册键 == 卡片文件名去扩展 == saveKey
    if f"Resources/Cards/{CHAR_KEY}.tres" != CARD_REL:
        fails.append("卡片注册键与 saveKey 不一致")
    # 12. 翻译 CSV：表头 + 键口径。★ 2026-09-25 起**读磁盘**核对（比对 `translation_file()`
    #     的输出是恒真自比，抓不到「生成器没落盘 / 磁盘被外部改回旧 key」）。
    _csv_path = os.path.join(MOD_ROOT, "Localization", "translations.csv")
    if not os.path.isfile(_csv_path):
        fails.append("缺 Localization/translations.csv")
    else:
        _csv_lines = [ln for ln in open(_csv_path, encoding="utf8").read().splitlines() if ln.strip()]
        if not _csv_lines or _csv_lines[0] != "key,zh_CN,en_US":
            fails.append(f"翻译 CSV 表头不符：{_csv_lines[:1]}")
        if any(ln.startswith("TOWERDEFENSE_") for ln in _csv_lines[1:]):
            fails.append("翻译 CSV 仍用 TOWERDEFENSE_* 键（已废弃；文案改内联后键 = 中文原文本身）")
        if not any(ln.split(",")[0] == PLANT_CN_NAME for ln in _csv_lines[1:]):
            fails.append(f"翻译 CSV 应含以「{PLANT_CN_NAME}」为键的行")
    # 13. Sprite 场景必须是**官方素材直转的双精灵外观**（不是内置 GatlingPea 的指针壳）：
    #     根 clip=BodyIdle / Head clip=HeadIdle / 共用同一份 AnimeData /
    #     脚本走 res://Extends（addons 下的在包内不可用）
    sp_params = skin_params()
    INS = int(sp_params["insert_layer_id"])
    if BASE_GATLING_SPRITE in sp:
        fails.append("Sprite 场景仍是内置 GatlingPea 指针壳，未换成直转外观")
    if f'path="{SPRITE_BASE_SCRIPT}"' not in sp:
        fails.append("Sprite 场景的脚本未指向 res://Extends/.../AdobeAnimateSpriteBase.cs")
    if sp.count(f'path="{SPRITE_BASE_SCRIPT}"') != 2:
        fails.append("Sprite 场景根与 Head 应共用同一份 AdobeAnimateSpriteBase.cs")
    if sp.count(f'path="{anim_tres_res()}"') != 1:
        fails.append("Sprite 场景的 flashAnimeData 未指向自制 .tres")
    if sp.count('flashAnimeData = ExtResource("2_data")') != 2:
        fails.append("Sprite 场景根与 Head 未共用同一份 AnimeData")
    if 'Animation/Clip = "BodyIdle"' not in sp:
        fails.append("Sprite 根节点 clip 应为 BodyIdle")
    if 'Animation/Clip = "HeadIdle"' not in sp:
        fails.append("Sprite Head 节点 clip 应为 HeadIdle")
    if 'parentSprite = NodePath("..")' not in sp:
        fails.append("Sprite Head.parentSprite 应指回根")
    if f'followParentSpriteLayerId = {INS}' not in sp:
        fails.append(f"Sprite Head.followParentSpriteLayerId 应为 {INS}（= max(body 图层)+1）")
    # 13a-2. LayerVisible / MediaReplace 必须按「图层名 / 媒体名」全列（内置范式，全 true / null）
    for k in sorted(list(sp_params["layer_names"]) + ["AnimeClips", "AnimeEvents"]):
        if f"Animation/LayerVisible/{k} = true" not in sp:
            fails.append(f"Sprite 场景缺 LayerVisible/{k} = true")
    for k in sorted(sp_params["media_names"]):
        if f"Animation/MediaReplace/{k} = null" not in sp:
            fails.append(f"Sprite 场景缺 MediaReplace/{k} = null")
    if f"Layer = {INS}\ninsertLayerId = {INS}\n" not in sp.replace("\r", ""):
        fails.append(f"Sprite Head 的 Layer/insertLayerId 都应为 {INS}")
    if not (0 <= INS < int(sp_params["layer_count"])):
        fails.append(f"insertLayerId {INS} 越界（AutoInsertChildSprites 会直接跳过）")
    # 13b. offset 标定（出膛点/站位基准，最容易错）
    offs = re.findall(r'^offset = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', sp, re.M)
    if len(offs) != 2:
        fails.append(f"Sprite 场景应有 2 处 offset（根 + Head），实为 {len(offs)}")
    else:
        got_root = (float(offs[0][0]), float(offs[0][1]))
        got_head = (float(offs[1][0]), float(offs[1][1]))
        ok_r, msg_r = _near_pt(got_root, ROOT_OFFSET)
        ok_h, msg_h = _near_pt(got_head, HEAD_OFFSET)
        if not ok_r:
            fails.append(f"根 offset 不符（渲染空间，已 ×{DISPLAY_SCALE}）：{msg_r}")
        if not ok_h:
            fails.append(f"Head offset 不符（渲染空间，已 ×{DISPLAY_SCALE}）：{msg_h}")
        # ★★ 2026-09-24 起根/Head offset **故意不同**（头位对齐豌豆射手，见常量块推导），
        #    旧的「两层必须相同」断言作废。新的不变量：
        #    ① 根 = -ANCHOR_ROOT（身体位置永不变）；
        if not _near_pt(got_root, (-40.0, -40.0), tol=0.01)[0]:
            fails.append(f"根 offset {got_root} 必须 = -ANCHOR_ROOT (-40,-40)")
        #    ② Head offset 不得回落旧口径 (−40,−40)（那是未对齐豌豆射手的旧值）；
        if _near_pt(got_head, (-40.0, -40.0), tol=0.01)[0]:
            fails.append("Head offset 仍是旧口径 (-40,-40)（未做头位对齐，见常量块 2026-09-24 注释）")
        #    ③ Marker2D 恒等式：marker = 炮口canvas + Head.offset（炮口粘在炮管上）。
        if not _near_pt((MARKER2D_POS[0] - HEAD_OFFSET[0], MARKER2D_POS[1] - HEAD_OFFSET[1]),
                        ANCHOR_MUZZLE, tol=0.01)[0]:
            fails.append(f"Marker2D 恒等式破坏：MARKER2D_POS - HEAD_OFFSET 应 = 炮口 {ANCHOR_MUZZLE}")
        # ★★ 反向断言：不得残留此前「自制素材 ×0.5」时期的旧口径
        PREV_SELF_MADE = (-69.25, -174.0)
        if _near_pt(got_root, PREV_SELF_MADE, tol=0.5)[0] or _near_pt(got_head, PREV_SELF_MADE, tol=0.5)[0]:
            fails.append(
                f"offset 仍是「自制素材 ×0.5」时期的旧值 {PREV_SELF_MADE}；"
                f"官方素材直转应为 {ROOT_OFFSET}/{HEAD_OFFSET}")
        # 旧「-(anchor - origin)」错误口径也必须拦下
        for bad in ((23.75, -22.5), (18.5, -105.25)):
            if _near_pt(got_root, bad, tol=0.5)[0] or _near_pt(got_head, bad, tol=0.5)[0]:
                fails.append(f"offset 仍是「-(anchor - origin)」错误口径 {bad}，应为 {ROOT_OFFSET}/{HEAD_OFFSET}")
        # 13b-2. Head.position 恒 (0,0) —— 它是**死值**（引擎 UpdateChild 每帧覆写，
        #   AdobeAnimateSprite.cs:5259-5267），2026-09-21 写的 (0,-8) 抬头从未生效；
        #   真正的头位旋钮是 HEAD_OFFSET（见常量块）。这里断言 (0,0) 防止死值回流。
        mhp = re.search(r'\[node name="Head"[^\]]*\]\n(?:[^\n]*\n)*?position = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', sp)
        if not mhp:
            fails.append("Sprite 场景里找不到 Head 节点的 position")
        else:
            got_hp = (float(mhp.group(1)), float(mhp.group(2)))
            if not _near_pt(got_hp, hp_expect, tol=1e-6)[0]:
                fails.append(f"Head.position 应为 {hp_expect}（死值清零；真旋钮 = HEAD_OFFSET），实为 {got_hp}")
    # 13c. Marker2D 必须按**官方素材**重算，不能沿用任何历史值
    mm = re.search(r'\[node name="Marker2D"[^\]]*\]\nposition = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', sc)
    if not mm:
        fails.append("场景里找不到 Marker2D 节点")
    else:
        got_marker = (float(mm.group(1)), float(mm.group(2)))
        ok_m, msg_m = _near_pt(got_marker, MARKER2D_POS)
        if not ok_m:
            fails.append(f"Marker2D 不符：{msg_m}")
        for bad, why in (((31.740002, -17.82), "内置 GatlingPea 旧值"),
                         ((87.75, -111.25), "自制素材 ×0.5 时期旧值"),
                         ((48.552, -9.8), "旧口径「炮口-ANCHOR_ROOT」（未随 2026-09-24 头位修正同步）")):
            if _near_pt(got_marker, bad, tol=0.5)[0]:
                fails.append(f"Marker2D 仍是{why} {bad}；应为 {MARKER2D_POS}")
    # 13c-3. ★ 2026-09-24 齐射改版：7 个 Marker 必须齐全，且位置 = 炮口点 + (dx, 0)
    #    （Marker2D 本身 dx=0；其余沿弹道方向 +32/+64/.../+192）
    volley_pos_mem = []
    for i, nm in enumerate(volley_marker_names()):
        m2 = re.search(r'\[node name="%s" [^\]]*\]\nposition = Vector2\((-?[\d.]+), *(-?[\d.]+)\)' % nm, sc)
        if not m2:
            fails.append(f"场景里找不到齐射 Marker 节点 {nm}")
            continue
        want2 = (MARKER2D_POS[0] + volley_marker_dx(i), MARKER2D_POS[1])
        got2 = (float(m2.group(1)), float(m2.group(2)))
        volley_pos_mem.append(got2)
        if not _near_pt(got2, want2, tol=0.01)[0]:
            fails.append(f"{nm} 位置 {got2} != 期望 {want2}")
    # 13c-4. ★★ 排列形态（用户口径「要一排，不是一列」）：从**场景文本解析出的** 7 个位置
    #   必须 ① y 全相同（屏幕上是水平一条直线）② x 严格递增且步距 == VOLLEY_SPACING（不重叠）。
    #   ⚠️ 只用解析值判断（不拿生成常量自比，避免「恒真比较」型假绿）。
    fails += _volley_shape_fails(volley_pos_mem, "内存")
    # 13c-2. Marker2D 的「经典 reanim 坐标」反推必须与标定文件一致（炮口 = barrel 最右列中点）
    #   ★ 2026-09-24 恒等式：MARKER2D_POS = 炮口 + HEAD_OFFSET（不是 − ANCHOR_ROOT）
    back = (MARKER2D_POS[0] - HEAD_OFFSET[0], MARKER2D_POS[1] - HEAD_OFFSET[1])
    if not _near_pt(back, tuple(sp_params["muzzle_reanim"]), tol=0.01)[0]:
        fails.append(f"Marker2D 反推的炮口 {back} != 标定 muzzle_reanim {sp_params['muzzle_reanim']}")
    # 13d. 三件套文件必须已存在（由 .cache/build_official_skin.py 产出并同步）
    for rel in (ANIM_DAT_REL, ANIM_TRES_REL, ANIM_PNG_REL):
        if not os.path.isfile(_abs(rel)):
            fails.append(f"缺外观文件：{rel}（先跑 .cache/build_official_skin.py）")
    # 13e. .tres 的 animeFile 必须是同目录相对路径（ResolveAnimeFilePath 的两条兜底靠它）
    if os.path.isfile(_abs(ANIM_TRES_REL)):
        tr = open(_abs(ANIM_TRES_REL), encoding="utf8").read()
        if f'animeFile = "./{ANIM_BASENAME}.dat"' not in tr:
            fails.append(f'{ANIM_TRES_REL} 的 animeFile 应为 "./{ANIM_BASENAME}.dat"（同目录相对路径）')
        # 13e-2. ★ 内容必须与标定文件一致（防「换了 json 却没重跑转换器」）
        if f"frameMax = {sp_params['frame_max']}" not in tr:
            fails.append(f"{ANIM_TRES_REL} 的 frameMax 应为 {sp_params['frame_max']}")
        # ★ 2026-09-24：包内 clip 以「共享标定 + 植物包补丁」为准 —— HeadFire 收窄为
        #   射击段 (50,74)（抽搐修复）；共享 json 里的 (50,86) 只对僵尸包成立。
        clips_expect = dict(sp_params["clips"])
        if tuple(HEADFIRE_CLIP_PLANT) != tuple(clips_expect.get("HeadFire", (-1, -1))):
            clips_expect["HeadFire"] = tuple(HEADFIRE_CLIP_PLANT)
        for cname, (c0, c1) in clips_expect.items():
            if f'"{cname}": Vector2i({c0}, {c1})' not in tr:
                fails.append(f"{ANIM_TRES_REL} 缺 clip {cname}=({c0},{c1})")
        if f'"HeadFire": Vector2i({sp_params["clips"]["HeadFire"][0]}, {sp_params["clips"]["HeadFire"][1]})' in tr \
                and tuple(sp_params["clips"]["HeadFire"]) != tuple(HEADFIRE_CLIP_PLANT):
            fails.append(f"{ANIM_TRES_REL} 的 HeadFire 仍是共享口径 {sp_params['clips']['HeadFire']}"
                         f"（应已补丁为 {tuple(HEADFIRE_CLIP_PLANT)}）")
        # 13e-2b. ★ 包内 .dat 的 clip 表必须与 .tres 一致（引擎加载 .dat 时会覆写 clips 字典，
        #   AdobeAnimateData.cs:1075-1081 ⇒ 只改 .tres 不改 .dat = 白改）。
        if os.path.isfile(_abs(ANIM_DAT_REL)):
            db = open(_abs(ANIM_DAT_REL), "rb").read()
            try:
                dat_clips, _spans = _dat_locate_clip_table(db)
            except Exception as ex:
                fails.append(f"{ANIM_DAT_REL} 段落解析失败：{ex}")
            else:
                if dat_clips != {k: (int(v[0]), int(v[1])) for k, v in clips_expect.items()}:
                    fails.append(f"{ANIM_DAT_REL} clip 表 {dat_clips} != 期望 {clips_expect}")
        for lname in sp_params["layer_names"]:
            if not re.search(r'"%s": \d+' % re.escape(lname), tr):
                fails.append(f"{ANIM_TRES_REL} 缺图层 {lname}")
        for mname in sp_params["media_names"]:
            if not re.search(r'"%s": \d+' % re.escape(mname), tr):
                fails.append(f"{ANIM_TRES_REL} 缺媒体 {mname}")
        nkey = len(re.findall(r"sliceKeys = PackedInt32Array\(([^)]*)\)", tr)[0].split(",")) \
            if re.search(r"sliceKeys = PackedInt32Array\(([^)]*)\)", tr) else -1
        if nkey != int(sp_params["n_slices"]):
            fails.append(f"{ANIM_TRES_REL} 的 sliceKeys 条数 {nkey} != {sp_params['n_slices']}")
    # 13e-3. ★★ 发射事件必须在**包内成品**里 —— 没有它 = 实机「只有动画、一颗子弹都没有」。
    #   发射链路（引擎源码实证，见 .cache/build_official_skin.py 常量块 FIRE_EVENT_*）：
    #   events[frame] → OnAnimeEvent("fire") → FireComponent.AnimeEvent → FireConfiguredVolley → Fire()。
    ff = list(sp_params.get("fire_frames") or [])
    fe = sp_params.get("fire_event") or {}
    f_cmd, f_arg = fe.get("Command"), fe.get("Argument")
    if not ff:
        fails.append("skin_params.fire_frames 为空 ⇒ 动画事件表为空，实机不会发射任何子弹")
    if f_cmd != "fire":
        fails.append(f"skin_params.fire_event.Command 应为 \"fire\"，实为 {f_cmd!r}")
    if ff and os.path.isfile(_abs(ANIM_TRES_REL)):
        tr = open(_abs(ANIM_TRES_REL), encoding="utf8").read()
        if tr.count(f'"Command": "{f_cmd}"') != len(ff):
            fails.append(f"{ANIM_TRES_REL} 的 fire 事件条数 "
                         f"{tr.count(chr(34) + 'Command' + chr(34) + ': ' + chr(34) + str(f_cmd) + chr(34))}"
                         f" != {len(ff)}")
    if ff and os.path.isfile(_abs(ANIM_DAT_REL)):
        db = open(_abs(ANIM_DAT_REL), "rb").read()
        # 事件段是文件尾部；本转换器的记录长度是固定的：
        #   u16 帧号 + u16 条目数 + pascalString(Command) + pascalString(Argument)
        rec = 2 + 2 + (4 + len(f_cmd.encode("utf8"))) + (4 + len((f_arg or "").encode("utf8")))
        off = len(db) - 2 - rec * len(ff)
        if off < 0:
            fails.append(f"{ANIM_DAT_REL} 太短，放不下 {len(ff)} 条事件记录")
        else:
            n_ev = int.from_bytes(db[off:off + 2], "little")
            if n_ev != len(ff):
                fails.append(f"{ANIM_DAT_REL} 事件条数 {n_ev} != {len(ff)}"
                             f" ⇒ 事件表没写进 .dat（实机不会发射）")
            else:
                for k, frm in enumerate(ff):
                    p0 = off + 2 + k * rec
                    got_fr = int.from_bytes(db[p0:p0 + 2], "little")
                    got_cnt = int.from_bytes(db[p0 + 2:p0 + 4], "little")
                    if (got_fr, got_cnt) != (frm, 1):
                        fails.append(f"{ANIM_DAT_REL} 第{k}条事件 (帧{got_fr}, 条数{got_cnt}) "
                                     f"!= ({frm}, 1)")
    # 13f. ★★ offset / Head.position 的 on-disk 复核
    #   ⚠️ 为什么必须单独查磁盘：上面 13b 比对的是 sprite_scene_tscn() **刚生成的内存文本**
    #   ⇒ 它只能证明「生成器常量 == 生成结果」，**证明不了磁盘上的文件是对的**。
    #   （负向测试实锤：把错值写进磁盘文件后自检照样报「通过」—— 因为内存文本被重新生成覆盖了。）
    sprite_rel = f"Resources/Characters/Plants/{CHAR_KEY}/Sprite/{CHAR_KEY}.tscn"
    sprite_path = _abs(sprite_rel)
    if not os.path.isfile(sprite_path):
        fails.append(f"缺 Sprite 场景文件：{sprite_rel}")
    else:
        on_disk = open(sprite_path, encoding="utf8").read()
        if on_disk != sp:
            fails.append(f"{sprite_rel} 磁盘内容与生成结果不一致（生成器未落盘 / 被外部改动）")
        d_offs = re.findall(r'^offset = Vector2\((-?[\d.]+), *(-?[\d.]+)\)', on_disk, re.M)
        if len(d_offs) != 2:
            fails.append(f"磁盘 Sprite 场景 offset 应为 2 处，实为 {len(d_offs)}")
        else:
            d_root = (float(d_offs[0][0]), float(d_offs[0][1]))
            d_head = (float(d_offs[1][0]), float(d_offs[1][1]))
            if not _near_pt(d_root, ROOT_OFFSET)[0] or not _near_pt(d_head, HEAD_OFFSET)[0]:
                fails.append(f"磁盘 Sprite offset {d_root}/{d_head} != 期望 "
                             f"{ROOT_OFFSET}/{HEAD_OFFSET}（2026-09-24 头位对齐口径）")
            # ★ 2026-09-24 起两层**故意不同**（见常量块）；这里只拦「头又回落到与根相同」的旧口径
            if _near_pt(d_head, d_root, tol=0.01)[0]:
                fails.append(f"磁盘 Head offset ({d_head}) 与根相同 = 旧口径，头位未对齐豌豆射手")
        d_hp = re.search(r'\[node name="Head"[^\]]*\]\n(?:[^\n]*\n)*?position = Vector2\((-?[\d.]+), *(-?[\d.]+)\)',
                         on_disk)
        if not d_hp:
            fails.append("磁盘 Sprite 场景里找不到 Head 节点的 position")
        elif not _near_pt((float(d_hp.group(1)), float(d_hp.group(2))), hp_expect, tol=1e-6)[0]:
            fails.append(f"磁盘 Head.position 应为 {hp_expect}，实为 "
                         f"({d_hp.group(1)}, {d_hp.group(2)})")
    # 13f-2. ★★ 角色场景（Marker2D 所在文件）同样必须 on-disk 复核 —— 2026-09-24 负向测试
    #   实锤的盲区：13c 只比内存文本，磁盘上的 Marker2D 被改旧值时自检照样「通过」。
    scene_rel = f"Resources/Characters/Plants/{CHAR_KEY}/Scene/{SCENE_FILE}"
    scene_path = _abs(scene_rel)
    if not os.path.isfile(scene_path):
        fails.append(f"缺角色场景文件：{scene_rel}")
    else:
        on_disk_scn = open(scene_path, encoding="utf8").read()
        if on_disk_scn != sc:
            fails.append(f"{scene_rel} 磁盘内容与生成结果不一致（生成器未落盘 / 被外部改动）")
        d_mm = re.search(r'\[node name="Marker2D"[^\]]*\]\nposition = Vector2\((-?[\d.]+), *(-?[\d.]+)\)',
                         on_disk_scn)
        if not d_mm:
            fails.append("磁盘角色场景里找不到 Marker2D 节点")
        else:
            got_dm = (float(d_mm.group(1)), float(d_mm.group(2)))
            if not _near_pt(got_dm, MARKER2D_POS)[0]:
                fails.append(f"磁盘 Marker2D {got_dm} != 期望 {MARKER2D_POS}")
        # 13f-3. ★ 2026-09-24：磁盘上的 7 个齐射 Marker 逐一复核（防「内存文本对、磁盘旧」）
        volley_pos_disk = []
        for i, nm in enumerate(volley_marker_names()):
            d_m2 = re.search(r'\[node name="%s" [^\]]*\]\nposition = Vector2\((-?[\d.]+), *(-?[\d.]+)\)' % nm,
                             on_disk_scn)
            if not d_m2:
                fails.append(f"磁盘角色场景里找不到齐射 Marker {nm}")
                continue
            want2 = (MARKER2D_POS[0] + volley_marker_dx(i), MARKER2D_POS[1])
            got2 = (float(d_m2.group(1)), float(d_m2.group(2)))
            volley_pos_disk.append(got2)
            if not _near_pt(got2, want2, tol=0.01)[0]:
                fails.append(f"磁盘 {nm} {got2} != 期望 {want2}")
        # 13f-4. ★★ 磁盘侧的排列形态（同 13c-4 四判据：同 y / x 递增 / 步距 32 / 首颗 = 炮口）
        fails += _volley_shape_fails(volley_pos_disk, "磁盘")
    # 13g. ★★ ComponentSet（齐射配置所在文件）同样必须 on-disk 复核 —— 2026-09-24 负向测试
    #   实锤的盲区：#1/#2 查的是内存文本，磁盘上的组件集被篡改（锁行被关 / firePosId 重复 /
    #   齐射少一条）时自检照样「通过」。与 13f / 13f-2 同一思路：磁盘 == 内存 + 关键不变量重查。
    cset_rel = f"{PKG_REL}/Scene/{COMPONENT_SET_FILE}"
    cset_path = _abs(cset_rel)
    if not os.path.isfile(cset_path):
        fails.append(f"缺 ComponentSet 文件：{cset_rel}")
    else:
        on_disk_cs = open(cset_path, encoding="utf8").read()
        if on_disk_cs != txt:
            fails.append(f"{cset_rel} 磁盘内容与生成结果不一致（生成器未落盘 / 被外部改动）")
        d_pos = [int(x) for x in re.findall(r"^firePosId = (\d+)$", on_disk_cs, re.M)]
        if sorted(d_pos) != list(range(VOLLEY_COUNT)):
            fails.append(f"磁盘 firePosId 应 0..{VOLLEY_COUNT - 1} 各一次，实为 {sorted(d_pos)}")
        if "lockProjectileGridY = true" not in on_disk_cs:
            fails.append("磁盘 ComponentSet 缺 lockProjectileGridY = true（散布子弹必须锁行）")
        d_refs = re.findall(
            r'SubResource\("([^"]+)"\)',
            (re.findall(r'fireProjectileList = \[(.*?)\]', on_disk_cs, re.S) or [""])[0])
        if d_refs != [f"Fire_Resource_proj{i}" for i in range(VOLLEY_COUNT)]:
            fails.append(f"磁盘 fireProjectileList 应依次 proj0..proj{VOLLEY_COUNT - 1}，实为 {d_refs}")
    # 13h. ★★ 卡片文案必须**内联在磁盘产物里**（2026-09-25 新增）。
    #   负向盲区（同 13f/13f-2/13g 的思路）：第 9 节只比**内存文本**，磁盘上被改回翻译键、
    #   或「威力」被改回旧的 2s 口径时，自检照样「通过」。这里直接读磁盘、逐字核对。
    #   依据：ModLoader 运行时**不加载** Mod 的 translations.csv（见 translation_file()）⇒ 写 key 就显示 key。
    pkg_card_rel = f"{PKG_REL}/Packet/{CHAR_KEY}.tres"
    for label, rel, expect in (("Cards/", CARD_REL, pk_card),
                               ("包内 Packet/", pkg_card_rel, pk_pkg)):
        if not os.path.isfile(_abs(rel)):
            fails.append(f"缺卡片文件：{rel}")
            continue
        on_disk_pk = open(_abs(rel), encoding="utf8").read()
        if on_disk_pk != expect:
            fails.append(f"{rel} 磁盘内容与生成结果不一致（生成器未落盘 / 被外部改动）")
        for field, want in (("name", PLANT_CN_NAME), ("describe", PLANT_CN_DESC),
                            ("handbookStory", PLANT_CN_STORY)):
            if f'{field} = "{want}"' not in on_disk_pk:
                fails.append(f"磁盘 {label} 的 {field} 必须是**内联字面量**「{want}」"
                             f"（写翻译键的话游戏内会原样显示 key 本身）")
        if f'handbookDescribe = "{PLANT_CN_HANDBOOK_DESC}"' not in on_disk_pk:
            fails.append(f"磁盘 {label} 的 handbookDescribe 必须是内联 5 行数值块"
                         f"（真实换行，不是 \\n 转义）")
        if "TOWERDEFENSE_PLANT_SUPERGATLINGPEA" in on_disk_pk:
            fails.append(f"磁盘 {label} 仍残留废弃翻译键 TOWERDEFENSE_PLANT_SUPERGATLINGPEA*")
        # 威力口径（用户 2026-09-25）：1.5 秒；截图上的 2s 是旧值
        if "威力：[color=cc241d]20×7 /1.5秒[/color]" not in on_disk_pk:
            fails.append(f"磁盘 {label} 的「威力」必须是 `20×7 /1.5秒`")
        if "20×7 /2s" in on_disk_pk or "20×7 /2秒" in on_disk_pk:
            fails.append(f"磁盘 {label} 的「威力」仍是旧的 2s / 2秒 口径")
        # describe 由 InformationPanel.cs 自己包 [color=2f375e] ⇒ 自己再包一层会嵌套
        if 'describe = "[color=' in on_disk_pk:
            fails.append(f"磁盘 {label} 的 describe 不得自带颜色标签（面板会包 [color=2f375e]）")
    # 13h-2. 数值块逐行口径（头词裸文本 + 数值 [color=cc241d]）—— 与官方 InformationPanel.tscn 范例同款
    _hb_lines = PLANT_CN_HANDBOOK_DESC.split("\n")
    if len(_hb_lines) != 5:
        fails.append(f"handbookDescribe 应为 5 行（韧性/威力/范围/特点/大招），实为 {len(_hb_lines)}")
    for _ln in _hb_lines:
        if not re.match(r"^[^\[\]]+：\[color=cc241d\][^\[\]]+\[/color\]$", _ln):
            fails.append(f"handbookDescribe 行格式不符（头词裸文本 + [color=cc241d] 数值）：{_ln}")
    # 14. 工程布局必须等于官方 XWModProjectLayout.StandardDirectories（72 项；顺序由校验脚本比对源码）
    if len(STANDARD_DIRS) != 72:
        fails.append(f"STANDARD_DIRS 应为 72 项（官方 XWModProjectLayout），实为 {len(STANDARD_DIRS)}")
    if len(set(STANDARD_DIRS)) != len(STANDARD_DIRS):
        fails.append("STANDARD_DIRS 有重复项")
    # 15. 角色包自引用必须是相对路径（docstring 第 8 条）——渲染进文本再查一遍
    for name, body in (("Scene", sc), ("Sprite", sp), ("Card", pk_card), ("PkgPacket", pk_pkg)):
        for path in re.findall(r'path="([^"]+)"', body):
            if path.startswith("res://") and "/Characters/" in path:
                fails.append(f"{name} 自引用写成了游戏根下的 res://：{path}")
    # 16. ★ #45 共享射击判定核心：植物与僵尸必须真的共用同一份源文件，且数值不漂移。
    #     与僵尸生成器（build_zombie_super_gatling_paper.py 第 14 节）完全对称的两问：
    #       (a) 入口源码里每个可调参数必须是 `= GatlingVolleyParams.X;` 转发；
    #       (b) 字面量只在共用核心里出现一次，必须等于生成器侧记录的期望值。
    #     ★ 2026-09-24 齐射改版：植物常规攻击已是数据侧齐射，入口**不再**消费
    #       PeasPerAttack / PeaSpacingSeconds（那是僵尸连发链的参数），
    #       所以这两个只查 (b) 核心字面量，不查 (a) 转发；其余 6 个两问都查。
    entry_src = os.path.join(RUNTIME_SRC_DIR, RUNTIME_ENTRY_TYPE + ".cs")
    cs = ""
    core = ""
    if not os.path.isfile(entry_src):
        fails.append("缺插件源码 " + entry_src)
    else:
        with io.open(entry_src, "r", encoding="utf-8-sig") as f:
            cs = f.read()
    if not os.path.isfile(SHARED_CORE):
        fails.append("缺共用判定核心 " + SHARED_CORE)
    else:
        with io.open(SHARED_CORE, "r", encoding="utf-8-sig") as f:
            core = f.read()
    for local_name, shared_name, value, need_forward in (
        ("PeasPerAttack", "PeasPerAttack", PEAS_PER_ATTACK, False),
        ("PeaSpacingSeconds", "PeaSpacingSeconds", PEA_SPACING, False),
        ("UltimateChance", "UltimateChance", ULTIMATE_CHANCE, True),
        ("UltimateSeconds", "UltimateSeconds", ULTIMATE_SECONDS, True),
        ("UltimatePeas", "UltimatePeas", ULTIMATE_PEAS, True),
        ("ScatterHalfAngleDeg", "ScatterHalfAngleDeg", ULTIMATE_SPREAD_DEG, True),
        ("MaxPeasPerFrame", "MaxPeasPerFrame", MAX_PEAS_PER_FRAME, True),
        ("StallGapMsec", "StallThresholdMsec", STALL_THRESHOLD_MSEC, True),
    ):
        if need_forward and cs:
            fwd = re.compile(r"const\s+\w+\s+" + local_name
                             + r"\s*=\s*GatlingVolleyParams\." + shared_name + r"\s*;")
            if not fwd.search(cs):
                fails.append(f"入口源码里的常量 {local_name} 应为"
                             f" `= GatlingVolleyParams.{shared_name};` 转发（共用核心）")
        if core:
            lit = re.compile(r"const\s+\w+\s+" + shared_name + r"\s*=\s*([0-9.]+)\s*;")
            m = lit.search(core)
            if not m:
                fails.append(f"共用核心 GatlingVolleyCore.cs 里找不到常量 {shared_name} 的字面量")
            elif abs(float(m.group(1)) - float(value)) > 1e-9:
                fails.append(f"常量 {shared_name} 不一致：共用核心 = {m.group(1)}，"
                             f"生成器 = {value}")
    # 0. ★ 2026-09-24 齐射不变式：数据侧齐射颗数 == 共用核心记录的用户需求颗数
    if VOLLEY_COUNT != PEAS_PER_ATTACK:
        fails.append(f"VOLLEY_COUNT={VOLLEY_COUNT} 与共用核心 PeasPerAttack={PEAS_PER_ATTACK} "
                     f"不一致（同一份需求，禁止漂移）")
    # 17. ★ 2026-09-24 齐射改版的插件侧不变量（结构证据，防旧机制回流）：
    #     ⚠️ 一律吃 `code`（= `_strip_cs_comments(cs)`）而不是原始源码：
    #        否则「把那一行注释掉」就能骗过子串断言（2026-09-25 负向测试实锤）。
    code = _strip_cs_comments(cs) if cs else ""
    if code:
        # 17a. 常规攻击交还 vanilla：插件**不得**再改写 fireEventName 屏蔽动画事件发射链
        #      （现在发射恰恰要靠动画里那个 "fire" 事件触发齐射）
        if "fireEventName = " in code:
            fails.append("插件不得再写 fire.fireEventName（常规齐射靠动画 'fire' 事件触发，屏蔽 = 整株哑火）")
        # 17b. 插件**不得**再调 Fire()：它现在一次打出全部 7 条齐射配置，
        #      大招逐颗散射必须走 CreateProjectileByData（狐尾草 HWC.FireVolley 同款）
        if re.search(r"\bfire\.Fire\(\s*\)", code):
            fails.append("插件不得再调 fire.Fire()（一次会打出全部齐射配置）；大招请走 CreateProjectileByData")
        if "CreateProjectileByData(" not in code:
            fails.append("大招必须走 fire.CreateProjectileByData(...)（狐尾草 TowerDefensePlantHWC.FireVolley 同款 API）")
        # 17c. 大招散射角写入 spawn overrides 的 spriteRotationOverride（与 Fire() 的口径一致）
        if "spriteRotationOverride" not in code:
            fails.append("大招 CreateProjectileByData 的 overrides 应含 spriteRotationOverride（与 Fire() 同口径，弹体随散射角旋转）")
        # 18. ★ 2026-09-25 图鉴去重（用户口径：删掉「只包含该角色」的独立图鉴，保留在已有的金卡分类里）
        #   机制：XWModContentCatalog.WithPlants 把 Mod 植物**单列**成 category["ModPlants"]
        #     （addons/ModEditor/ModSystem/XWModContentCatalog.cs:15 常量 + :120 写入；
        #      全库唯一调用点是 Almanac.cs:219），而图鉴就是按 plantPacketBank.category
        #      的**键顺序**翻页（Almanac.cs:317-328）⇒ 本卡会同时出现在 `ModPlants` 和 `Gold`
        #      两个分类里 = 用户看到的「重复」。
        #   修法：把本卡从 ModPlants 数组里摘掉；**摘完若 ModPlants 空了就整个删键**
        #     （这样「只含本角色」的独立图鉴就消失了），但**不能**因为别的 Mod 植物也在里面就整类删掉。
        #   删键让分类数 -1 ⇒ 正在显示的那页可能越界（InitPlant 的
        #     `plantCategoryId >= category.Count` 会直接 return 出**空列表**）⇒ 必须回落 plantCategoryId。
        #   断言一律要求**整条活语句**（含分号/赋值），子串级匹配挡不住「改成 no-op」型篡改。
        for _needle, _why in (
            ('private const string ModPlantCategory = "ModPlants";',
             '插件缺 ModPlantCategory = "ModPlants" 常量（图鉴独立分类的键名）'),
            ("categories.Remove(ModPlantCategory);",
             "插件必须能把空的 ModPlants 分类整个删掉（否则「只含本角色」的分类仍在）"),
            ("if (modPlants.Count == 0)",
             "「空分类才删键」的判定必须是**真条件**（`false &&` 之类死分支骗不过这条）"),
            ("modPlants.RemoveAt(i);",
             "插件必须**逐条**从 ModPlants 里摘掉本卡（整类删会连累别的 Mod 植物）"),
            ("almanac.plantCategoryId = categories.Count - 1;",
             "插件删分类后必须真的回落 plantCategoryId（否则翻页越界 ⇒ InitPlant 出空列表）"),
            ("if (almanac.plantCategoryId >= categories.Count && categories.Count > 0)",
             "越界回落必须挂在**真条件**上（死分支 = 没回落）"),
            ("almanac.InitPlant();",
             "插件改完分类后必须能在植物页已打开时刷新"),
            ("IsPlantPageInitialized(almanac)",
             "刷新必须仍受「植物页已初始化」守卫（不破坏图鉴的懒初始化设计）"),
            ("gold.RemoveAt(i);",
             "金卡分类里也要去重（同一张卡在同一分类里出现两份的另一条路径）"),
        ):
            if _needle not in code:
                fails.append(f"图鉴去重：{_why}（缺活语句 {_needle!r}）")
    return fails


def main():
    # ★ --check 模式（2026-09-24 新增）：**只跑 self_check，不重建**。
    #   负向测试专用 —— main() 默认先落盘重建，会把「故意篡改的磁盘产物」修掉，
    #   导致负向测试永远全绿（本轮实证）。要验证磁盘现状 / 做负向测试，用：
    #     python -c "import importlib.util as u; s=u.spec_from_file_location('g','build_plant_super_gatling.py'); \
    #                g=u.module_from_spec(s); s.loader.exec_module(g); import sys; sys.exit(3 if g.self_check() else 0)"
    #   或这里的 --check 开关（等价，不写盘）。
    if "--check" in sys.argv:
        fails = self_check()
        if fails:
            print("[FAIL] 磁盘现状自检未通过：")
            for f in fails:
                print("   -", f)
            return 3
        print("自检通过（--check：只验证磁盘现状，未重建）")
        return 0

    # ⚠️ 自检放在**写盘之后**（见下方）：否则「改了生成器」的第一跑必然因磁盘还是旧内容而失败。
    #    为了不丢掉「磁盘 vs 生成结果」这条防线，这里先给旧磁盘内容拍个快照，
    #    写盘后由 self_check 比对「快照 == 生成结果」，不一致就打印变更提示（结构升级提示，不算失败）。
    ws_files = [os.path.join(MOD_ROOT, r.replace("/", os.sep))
                for r in (f"Resources/Characters/Plants/{CHAR_KEY}/Sprite/{SPRITE_FILE}",
                          f"Resources/Characters/Plants/{CHAR_KEY}/Scene/{SCENE_FILE}")]
    snapshot = {}
    for p in ws_files:
        snapshot[p] = open(p, encoding="utf8").read() if os.path.isfile(p) else None

    # --- 先取回旧工程文件时间戳（幂等：不能每次写 now）
    proj_file = os.path.join(MOD_ROOT, f"{MOD_NAME}.pvzmodeproject")
    existing = None
    if os.path.isfile(proj_file):
        try:
            existing = read_json(proj_file)
        except Exception:
            existing = None

    # --- 工作区：**就地重建**（不做整目录 rmtree —— 本机删除钩子单次约 0.6 s，重建要 48 s）
    #     改过名/删过的旧产物由 sweep_stale_files() 按「本次产出清单」清掉。
    assert os.path.abspath(MOD_ROOT).startswith(os.path.abspath(WS) + os.sep), "MOD_ROOT 必须位于工作区内"

    # --- 构建工作区产物
    dump_json(os.path.join(MOD_ROOT, "mod.json"), build_manifest())
    write_text(os.path.join(MOD_ROOT, "Localization", "translations.csv"), translation_file(), "\n")
    write_text(_p("Config", CFG_FILE), plant_config_tres(), "\n")
    write_text(_p("Scene", COMPONENT_SET_FILE), component_set_tres(), "\n")
    write_text(_p("Scene", SCENE_FILE), plant_scene_tscn(), "\n")
    write_text(_p("Sprite", SPRITE_FILE), sprite_scene_tscn(), "\n")
    # 同一张卡分发到两处：Cards/ 是**注册**位置；包内 Packet/ 是镜像（角色包依赖，不注册）
    write_text(_p("Packet", f"{CHAR_KEY}.tres"),
               packet_tres(f"../Config/{CFG_FILE}"), "\n")
    write_text(_abs(CARD_REL), packet_tres(f"../Characters/Plants/{CHAR_KEY}/Config/{CFG_FILE}"), "\n")

    # --- 自制外观三件套：从 .cache 同步到包内（.dat / .tres / Atlas.png）
    #     ⚠️ 这三个是二进制/大文件，**不能**由本脚本用字符串生成，必须由 .cache 下的
    #        build_atlas2.py -> build_dat.py -> build_tres.py 产出后同步过来。
    #        用 write_bytes_if_changed 保证字节幂等（跑几次都一样）。
    skin = sync_skin_assets()
    if skin:
        print(f"自制外观三件套已同步（{len(skin)} 个）：")
        for r in skin:
            print(f"    {os.path.getsize(_abs(r)):>9d}  {r}")

    ensure_project_layout(MOD_ROOT)

    # --- 自检（此时工作区已全部落盘 ⇒ 自检的 on-disk 断言才有意义）
    fails = self_check()
    drift = [p for p, old in snapshot.items()
             if old is not None and old != open(p, encoding="utf8").read()]
    if drift:
        print("提示：以下文件内容因生成器升级而被改写（属正常结构变更）：")
        for p in drift:
            print("    ", os.path.relpath(p, MOD_ROOT))
    if fails:
        print("[FAIL] 自检未通过：")
        for f in fails:
            print("   -", f)
        return 3
    print(f"自检通过：齐射口径 = {VOLLEY_COUNT} 条配置（dir=0 / firePosId 0..{VOLLEY_COUNT - 1} / "
          f"{VOLLEY_SPACING:g}px 间距**沿弹道排成一条水平直线（一排，非一列）** / 锁行）"
          f"由动画 fire 事件一次 Fire() 同帧打出；"
          f"间隔 {FIRE_INTERVAL}s；大招 {ULTIMATE_SECONDS:g}s / {ULTIMATE_PEAS} 颗 / "
          f"±{ULTIMATE_SPREAD_DEG:g}°（插件，CreateProjectileByData）；"
          f"GOLD 卡 / {COST} 阳光 / 涨价 {COST_RISE} / 冷却 {fmt_f(PACKET_COOLDOWN)}s")

    write_text(proj_file, godot_json(build_project_file(existing), "\r\n"), "\n")

    # --- 清掉「这次不再产出」的旧文件（含改名前的 .pvzmodeproject / 旧卡片名）
    keep_files = set(build_manifest()["resources"])
    keep_files |= {"mod.json", "Localization/translations.csv", f"{MOD_NAME}.pvzmodeproject"}
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
    ids = merge_enabled_mods(MODS_DIR, MOD_ID)
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
