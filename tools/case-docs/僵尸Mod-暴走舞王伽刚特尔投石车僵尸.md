# 僵尸 Mod：暴走舞王伽刚特尔投石车僵尸（Zombie 类）

> 产物：`dist/暴走舞王伽刚特尔投石车僵尸.pmod`（16 180 B，sha256 `4cb669fe0040…f48`）
> 生成器：`build_zombie_disco_pult.py` ｜ 插件源码：`runtime_src_zombie/`
> 复核脚本：`runtime_src_zombie/check_gates_zombie.cs`、`.cache/check_idempotent_zombie.py`

---

## 1. 它是什么

一个**新增僵尸卡**：外形是「小鬼投石车僵尸」，机制也完全照搬它 —— 唯一的区别是
**投石车里扔出来的不是小鬼，而是「暴走舞王伽刚特尔」**。

需求逐条对照（7 条，全部落地）：

| # | 需求 | 落地位置 | 值 |
|---|---|---|---|
| 1 | 显示名 = 暴走舞王伽刚特尔投石车僵尸 | 卡片 `packet.name` 等 4 个显示字段 | `暴走舞王伽刚特尔投石车僵尸` |
| 2 | 特性与小鬼投石车僵尸一致，但投掷物换成暴走舞王伽刚特尔 | 复用内置 `TowerDefenseZombieImppult` 整套（场景脚本 + 组件集 + 美术），**托管插件**换投掷单位 | `ZombieImp` → `ZombieDiscoGargantuar` |
| 3 | 血量 3000 | `characterConfig.hitpoints + hitpointsNearDeath` | 2830 + 170 = **3000** |
| 4 | 攻击力 100000 | `attack` 与 `smashAttack` 同设 | `100000.0` / `100000.0` |
| 5 | 攻击类型「碾压」 | ComponentSet 的 `Attack0_Definition.attackType` | `"Smash"` |
| 6 | 作为僵尸卡 / 价格 0 / 冷却 0 秒 | `type` / `cost` / `packetCooldown` | `6`(ZOMBIE) / `0` / `0.0` |
| 7 | 贴图暂时复用「小鬼投石车僵尸」 | 场景与卡片全部引用内置 Imppult 资源 | 无新素材 |

包内 9 个条目：

```
mod.json
Resources/Cards/ZombieDiscoGargantuarPult.tres                                   ← 注册卡片
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Config/TowerDefenseZombieDiscoGargantuarPult.tres
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Packet/ZombieDiscoGargantuarPult.tres
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPult.tscn
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPultComponentSet.tres
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPultFireComponentDefinition.tres
Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Sprite/ZombieDiscoGargantuarPult.tscn
Runtime/ModAssembly.dll                                                          ← 托管插件 19 456 B
```

---

## 2. 设计总纲：一条数据 + 一个插件

### 2.1 纯数据为什么换不掉投掷物（这是需求 2 的全部难点）

**证据（解包源码）**：`Asset/Anime/Character/Zombie/Chapter5/Imppult/Scene/TowerDefenseZombieImppult.cs:135`

```csharp
TowerDefensePacketConfig packetConfig = TowerDefenseManager.GetPacketConfig("ZombieImp");
...
TowerDefenseZombieImpBase imp = packetConfig.Create(...) as TowerDefenseZombieImpBase;
```

`"ZombieImp"` 是**硬编码字符串字面量**，不从任何配置字段读取。
配置里唯一能碰的 `CatapultComponent.projectileName = "Imp"` 是**美术/动画层的名字**
（决定投掷物用哪套图集/动画），不决定生成哪个角色。

所以：**想让投石车扔出别的东西，只有「托管插件」一条路。**

### 2.2 复用内置 Imppult 的脚本为什么是合规的（不是抄近道）

`ModLoader.SanitizeCharacterTextResource()`（`ModLoader.cs:1418`）对角色包里的
`.tscn` / `.tres` 只做两件事：

| 情况 | 处理 |
|---|---|
| 文本里出现 `type="GDScript"` / `type="CSharpScript"` 字面量 | **直接拒绝整包**（`ModLoader.cs:1423`） |
| `type="Script"` 且 `path` **不是** `res://` 开头 | `.tscn` 里**剥离该引用**并移除用到它的行；`.tres` 里**直接拒绝**（`ModLoader.cs:1439`） |
| `type="Script"` 且 `path` 是 `res://` 开头 | **保留**（游戏自带脚本就是这个形态） |

我们的场景写的是：

```
[ext_resource type="Script" path="res://Asset/Anime/Character/Zombie/Chapter5/Imppult/Scene/TowerDefenseZombieImppult.cs" id="3"]
```

⇒ 是 `res://`，保留；不是 `CSharpScript`，不触发嵌脚本闸门。
而且内置场景 `TowerDefenseZombieImppult.tscn` 自己就是这么引用它的，
说明这个 `.cs` 在导出包里是可加载的 Script 资源。

于是我们**免费**拿到 Imppult 的全部行为，与需求 2「特性一致」逐条对上：

| Imppult 脚本里的行为 | 我们是否保留 |
|---|---|
| `_Ready()` 取 `%FireSlot` / `character.fire` / `CatapultComponent` | ✅ 保留（场景节点树逐字复刻） |
| `AnimeEvent("fire")` → `OnFireAnimeEvent()` + `ImpSpawn()` + 换弹贴图 | ✅ 保留（投谁被插件改了） |
| `DamagePointReach` → 投石车减速 + 冒烟 | ✅ 保留（引用了内置的 DamagePointData） |
| `HitpointsEmpty` → 爆炸特效 + 销毁 | ✅ 保留 |
| `AnimeCompleted("Fire")` → 弹量视觉分档 | ✅ 保留 |

⚠️ **绝对不要**加 `metadata/mod_character_script_binding = "CompanionOnly"`：
`ModLoader.CharacterRequiresCompanion()`（`ModLoader.cs:630`）一读到这个 meta 就会去要
`mod.CharacterCompanionRuntime`，拿不到 → 该资源被拒 → 整包回滚。
本包不写这个 meta，自检里也有专门一条断言禁止它出现。

### 2.3 插件的工作方式（时间线）

关键时序（全部有源码位置）：

```
CatapultComponent.WalkProcessing()            ← 每帧推进
  └─ TryBeginFiring() → CanStartFire()        ← useCanFireCheck=false，看 fireComponent.timer
  └─ parent.Idle() → 播 "Fire" 动画
        └─ AnimeEvent("fire")                 ← TowerDefenseZombieImppult.cs:70
              ├─ _catapultComponent.OnFireAnimeEvent()   ← CatapultComponent.cs:568 内部触发 OnFireEvent
              │     └─ 【插件】：订阅了 OnFireEvent ⇒ 领一张「已开火」票
              ├─ ImpSpawn()                   ← ★ 注意：async void
              │     ├─ await ToSignal(GetTree(), PhysicsFrame)   ← ★ 先等一个物理帧
              │     └─ characterNode.AddChild(imp)
              │           └─ 【插件】：监听 characterNode 的 child_entered_tree（同步回调）
              │                 ⇒ 发现 config.name == "ZombieImp" 的子节点刚进树
              │                 ⇒ QueueFree() 掉它，换成 ZombieDiscoGargantuar
              └─ UpdateProjectileVisual()
```

**为什么必须用「领票 + child_entered_tree」而不是在事件里直接换**：
`OnFireEvent` 触发的那一刻 `ImpSpawn()` 还没跑（它在同一个 `AnimeEvent` 分支里**后面**才调），
而且 `ImpSpawn()` 是 `async void`，`AddChild` 之前还 `await` 了一个物理帧 ——
所以事件时小鬼**根本不存在**。用「同一个父节点的 child_entered_tree」做同步拦截最简单可靠。

**票是 FIFO 队列**（超时 700 ms 自动丢弃）：同一帧两只一起开火也能一一对上；
即使对不上，也只是「谁投的不重要」，结果不变。

---

## 3. 数据包结构

### 3.1 角色包布局（来自游戏自己的生成器，不是猜的）

`addons/ModEditor/FileSystem/XWResourceCreateRoute.cs` 的
`CreateCharacterScenePackageFromTemplate()` 是**游戏 mod 编辑器自带**的「新建角色包」流程，
它就是权威范本：

```
<Key>/Scene/<Key>.<ext>          ← 运行场景（6 段硬约束）
<Key>/Config/<Key>Config.tres    ← 角色配置
<Key>/Sprite/<Key>.tscn          ← 精灵场景（CharacterSprite 注册点）
<Key>/Packet/<Key>.tres          ← 卡片（本包也放了一份镜像，与内置角色目录同构）
<Key>/<Key>.tres                 ← 动画数据（本包复用内置，不新建）
<Key>/Script/<Key>.cs            ← 脚本（本包复用内置，不新建）
<Key>/DamagePoint|Custom|Armor/  ← 数据子资源（本包复用内置，不新建）
```

本包 Key = `ZombieDiscoGargantuarPult`，目录类别 = `Zombies`。

### 3.2 四条路径/命名硬约束（违反 = 整包「不加载」）

| 约束 | 源码 | 本包取值 |
|---|---|---|
| 路径**恰好 6 段**，`[0]=Resources`、`[1]=Characters`、`[2]∈已知类别`、`[4]=="Scene"`、`[5]` 为 `.tscn`，且**文件名 == 目录名 == Key** | `ModLoader.cs:1275` `TryInferCharacterScene` | `Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPult.tscn` |
| 同上，`[4]=="Sprite"` | 同上（folder 参数） | `…/Sprite/ZombieDiscoGargantuarPult.tscn` |
| 类别必须 ∈ `Plants/Zombies/Props/Vases/Mowers/Items/Graves/Craters` | `ModLoader.cs:1292` `IsKnownCharacterCategory` | `Zombies` |
| 角色包目录下**任意** ≥5 段文件都算「包依赖」，不会被判 unsupported | `ModLoader.cs:1301` `IsCharacterPackageDependency` | ComponentSet / FireComponentDefinition / Config / Packet 都靠这条放行 |

### 3.3 三处命名必须统一（`XWModContentValidation.Validate`）

| 项 | 值 | 依据 |
|---|---|---|
| 卡片注册键 | `Resources/Cards/ZombieDiscoGargantuarPult`（= 文件名去扩展） | `ModLoader.InferRuntimeEntry` 的 `Resources/Cards/` → Packet 分支 |
| `packet.saveKey` | `ZombieDiscoGargantuarPult` | `XWModContentValidation.cs:30-33`，不等即 throw |
| `characterConfig.name` | `ZombieDiscoGargantuarPult` | `XWModContentValidation.cs:34` 拿它查 `TOWERDEFENSE_CHARCATERS` |
| `CHARCTAER_SPRITE` 键 | `ZombieDiscoGargantuarPult` | `XWModContentValidation.cs:35-36`，缺 = throw「缺少 CharacterSprite/…」 |
| `manifest.provides` | `Character` / `CharacterSprite` / `Packet` 三键都是 `["ZombieDiscoGargantuarPult"]` | `provides` 里每个 key 都必须真的注册上 |
| `packet.unlockCheckList` | `[]`（空表 = 直接可用） | `XWModContentValidation.cs:37-40`，放游戏内条件会被判「必须使用 Mod 专属解锁条件」 |

⚠️ **`config.name` 与 `packet.name` 在本包里故意不同**：
前者是内部键（`ZombieDiscoGargantuarPult`，插件也靠它认人），后者是显示名（中文）。
把它们混起来会同时踩到「查不到角色」和「游戏里显示成英文 key」。

---

## 4. 数值映射（逐条有源码依据）

### 4.1 血量 3000 —— 一个需要说清楚的算术

`TowerDefenseCharacterInstance._Init`：

```csharp
hitpointsBase = config.hitpoints;
hitpoints     = hitpointsBase + config.hitpointsNearDeath;   // ← 有效总血
```

而 `hitpointsNearDeath` 不只是「额外血」，它同时是**濒死线**：

* `if (!nearDie && hitpoints <= hitpointsNearDeath)` → 进入濒死阶段（掉头、断肢等）；
* `TowerDefenseCharacter.DealHurt(config.hitpointsNearDeath * delta / 3.0)` → 濒死流血；
* 伤害点阈值也用它做基准：`hitpointsNearDeath + (hitpointsSave - hitpointsNearDeath) * 百分比`。

**决策**：需求 3 说「血量设定为 3000」，我按**有效总血恰好 3000** 落地：

```
hitpointsNearDeath = 170.0   （逐字沿用 Imppult，保住「濒死阶段」这一可见特性 ⇒ 满足需求 2）
hitpoints          = 2830.0  （= 3000 − 170）
```

⇒ 游戏里挨打总伤害 3000 才会死，濒死线在 170。

⚠️ **如果你更希望 `.tres` 里直接看到 `hitpoints = 3000.0`**，改生成器顶部两个常量即可
（`HP_TOTAL = 3170.0` 让总血变 3170；或 `HP_NEAR_DEATH = 0.0` 让总血恰好 3000 但**取消濒死阶段**）。
见 §9.1。

### 4.2 其余数值

| 字段 | 值 | 依据 / 为什么 |
|---|---|---|
| `attack` / `smashAttack` | `100000.0` / `100000.0` | 碾压走 `smashAttack`、非碾压走 `attack`；两个都写就两条路都满足需求 4 |
| `Attack0_Definition.attackType` | `"Smash"` | `AttackComponentDefinition.attackType` 的合法枚举名 ⇒ 需求 5 |
| `type` | `6` | `TowerDefenseEnum.PACKET_TYPE`：`NOONE=-1, WHITE=0, GOLD=1, DIAMOND=2, COLOUR=3, STAR=4, ORIGINAL=5, **ZOMBIE=6**, COVER=7, GRAY=8` |
| `cost` | `0` | 需求 6 |
| `packetCooldown` | `0.0` | 需求 6（`costRise` 保持默认 `-1` = 不涨价） |
| `physique` | `5` | 逐字沿用 Imppult（投石车形态） |
| `weight` / `wavePointCost` | `3000` / `300` | 逐字沿用 Imppult（出怪权重与原版一致） |
| `excludeLineGridType` | `[3]` | 逐字沿用 Imppult |
| `plantGridType` | `[-1]` | 逐字沿用 Imppult（`-1` = NOONE） |
| `collisionFlags` / `maskFlags` | `41` / `9` | 逐字沿用 Imppult |
| `physiqueTypeFlags` | `2048` | 逐字沿用 Imppult |
| `damagePointData` | 内置 `ImppultDamagePointData.tres`（`res://` 绝对路径） | **必须给**：投石车靠 `DamagePoint2` 触发「减速 + 冒烟」（`CatapultComponent.OnDamagePoint`），交 `null` 会把这个可见特性弄丢 |
| `CatapultDefinition.projectileNum` / `fireInterval` | `4` / `3.0` | 逐字沿用 Imppult（4 发、每发 3 秒） |
| `CatapultDefinition.speedDamagePointName` | （不写，走默认 `"DamagePoint2"`） | 与 Imppult 一致 |

**字段书写顺序**严格按类声明顺序（`TowerDefenseZombieConfig` 先、`TowerDefenseCharacterConfig` 后），
否则编辑器一保存就会把它重排（与植物包同一约定，自检里有断言）。

---

## 5. 显示名为什么直接写中文（而不是翻译键 + translations.csv）

内置卡片的 `packet.name` 是**翻译键**（如 `TOWERDEFENSE_ZOMBIE_IMPPULT_NAME`），
因为游戏启动时 `Global.cs` 会 `TranslationServer.SetLocale("zh")` 加载官方翻译表。

但 **ModLoader 全文没有任何 `TranslationServer.AddTranslation` 调用**（已全树 grep 确认）：
`manifest.translations` 只在 schema 校验 / 同步服务 / 引用图里被读写，
`Localization/*.csv` **不会**进入游戏运行时。⇒ 用翻译键写，游戏里就显示原始 key。

所以本包把中文**直接写进** 4 个显示字段：

| 消费点 | 源码 | 结果 |
|---|---|---|
| `packet.name` | `InformationPanel.cs` `nameLabel.Text = packetConfig.name;` | 直接显示中文 ✅ |
| `packet.describe` | `InformationPanel.cs` `expressionLabel.Text = Tr(packetConfig.describe)` | `Tr()` 查不到 → 原样返回 ✅ |
| `packet.name` | `AwardSettlement.cs` `nameLabel.Text = packetConfig.name;` | 直接显示中文 ✅ |
| `packet.name` | `LevelEditorBattle.cs` `Tr(packetConfig.name)` | 原样返回 ✅ |

这也是本包**不带** `Localization/translations.csv`、`manifest.translations` 为空表的原因。

⚠️ **已知副作用（与内置卡片同构，非本包引入）**：
`TowerDefenseBattleFeatureConveyorBelt` 与 `TowerDefenseBattleFeatureRainMode` 会调
`GetCharacterNum(packet.name)`，而 `GetCharacterNum` 内部拿它跟 `character.config.name` 比较。
内置卡片传的是翻译键 ⇒ 本来也对不上、恒返回 0；我们传中文，行为**完全一样**（同样恒 0），
不会额外引入差异。

---

## 6. ⚠️ Godot 4.7 的 `unique_id` / `parent_id_path`：**故意不写**

本项目是 Godot **4.7**（`project.godot`：`config/features=PackedStringArray("4.7", "C#", "Forward Plus")`）。
新编辑器序列化时会顺手给节点加 `unique_id=…` / `parent_id_path=PackedInt32Array(…)`，
比如内置的 `TowerDefenseZombieImppult.tscn` 就有。**但这两项是可选的**，证据三条：

1. 解包树里 **2071 个 `.tscn` 中有 319 个完全不带 `unique_id`**，且其中包含多节点角色场景
   —— `TowerDefensePlantPot.tscn`（7 节点）、`TowerDefensePlantEMPlantern.tscn`（9 节点）、
   `TowerDefenseVaseNormal.tscn`（5 节点）、`TowerDefensePlantLilyPad.tscn`（6 节点）等，
   这些都在游戏里正常用着。
2. `TowerDefensePlantPot.tscn` 正是我们需要的那个用法 ——
   「给实例化子树的节点加子节点」：
   ```
   [node name="TransformPoint" parent="SpriteGroup" index="0"]
   ...
   [node name="AdobeAnimateSlot" type="Node2D" parent="SpriteGroup/TransformPoint/Pot" index="0"]
   ```
   **完全没有** `parent_id_path`。
3. 游戏 mod 编辑器自己的角色场景模板 `BuildCharacterRuntimeSceneContent()` 输出的是
   `[gd_scene load_steps=4 format=3]` + `[node name="…" parent="SpriteGroup/TransformPoint" instance=…]`
   —— 既无 `uid` 也无 `unique_id` / `parent_id_path`。

⇒ 本包一律**不写** `uid` / `unique_id` / `parent_id_path`。
写了反而要伪造一个我们推不出来的哈希（试过 `djb2(name)` 等，对不上），风险更大。
自检里有专门一条：出现即失败。

---

## 7. 插件细节（`Runtime/ModAssembly.dll`，入口 `DiscoGargantuarPultRuntimeEntry`）

源码 `runtime_src_zombie/DiscoGargantuarPultRuntimeEntry.cs`（32 KB，中文注释）。
编译：`python runtime_src_zombie/build_runtime.py --check`（两次编译比 sha256，字节确定）。

### 7.1 三条职责

**① 玩法（需求 2）** —— 换投掷单位。
订阅 `CatapultComponent.OnFireEvent`（`CatapultComponent.cs:139` 声明、`:568` 触发）领票；
再监听 `TowerDefenseGroundItemBase.characterNode`（`public static Node2D`）的
`child_entered_tree` 同步回调，发现 `config.name == "ZombieImp"` 的子节点刚进树时：

1. 抄原小鬼的参数：`pos = imp.GetLogicalGlobalPosition()`、`gridPos = imp.gridPos`、
   `height = imp.z − imp.groundHeight`、`ySpeed = imp.ySpeed`；
   再从 shooter 抄 `hitpointScale / scale / hypnoses / invisible`；
2. `imp.QueueFree()`；
3. `packet.Create(pos, gridPos, height) as TowerDefenseZombie`（`ZombieDiscoGargantuar` 的卡片配置）；
4. 设 `ySpeed`，算 `landX`（**与 `ImpSpawn()` 第 168 行完全相同的「第 3~5 列随机」公式**）、
   `fallTime = thrown.GetFallTime()`；
5. 订阅 `thrown.OnLand`（落地推进），`AddChild(thrown, false, InternalMode.Disabled)`；
6. `SetHitpointAndScale(hitpointScale, scale)` + `SetDeferred("invisible", …)` + `Hypnoses()`；
7. `Tween.TweenMethod(Callable.From<Vector2>(SetLogicalGlobalPosition), from, new Vector2(landX, from.Y), fallTime)`
   —— 只动水平位移，垂直由投掷物理自己走。

**落地推进**：`TowerDefensePacketConfig.Create()` **只创建、不入树、不调 `Walk()`**
（`TowerDefenseManager.IsZombieWalk()` 才会等一帧后 `CallDeferred("Walk")`）。
插件因此自己订阅 `OnLand` → `CallDeferred("Walk")`，并挂一条 **3 秒保险丝**
（万一没收到 `OnLand` 也不会永远站着不动）。

**② 卡库入库（需求 6 前半段，「能不能选到」）**
把 `ZombieDiscoGargantuarPult` 补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类，
以及 `Include` 闭包算出的派生库（离线算得 `TotalZombie`、`Total`）。

依据：`Almanac.cs:220` —— 图鉴僵尸页是
`zombiePacketBank = TowerDefenseManager.GetPacketBankData("GeneralZombie")`，
**取的是同一个实例**（不像植物页 `Almanac.cs:219` 那样走 `XWModContentCatalog.WithPlants()` 深拷贝）。
⇒ 补一处，**选卡界面 / 关卡编辑器 / 图鉴僵尸页同时生效**，天然同源。

派生库必须在**运行期**按 `PacketBankResource.json` 的 `Include` 闭包算，不写死；
读不到 json 才回落到离线算好的 `[GeneralZombie, TotalZombie, Total]`。
只补 `GeneralZombie` 的话，`CommandManager.debugPacketOpenAll`（切到 `Total`）下又会看不到。

**③ 图鉴兜底刷新**
图鉴是**刻意懒初始化**的（`Almanac.cs:450` `if (!_zombieInitialized) InitZombie();`，
另有 `Almanac.cs:487` 的 `_zombieRefreshQueued` 去抖）。
所以插件只在**反射读到 `_zombieInitialized == true`**（= 僵尸页已经建过列表）时才主动
`InitZombie()` 刷一次；没初始化过**绝不**主动调 —— 那会在打开图鉴的瞬间把预览节点和角色资源
全加载出来，白白多一次卡顿。

### 7.2 四条硬约束（违反 = **整包被拒**，不是「不生效」）

| 约束 | 源码 | 本包 |
|---|---|---|
| `runtimeAssembly` 只能是**字面量** `"Runtime/ModAssembly.dll"`（字符串相等判定，不认别的路径/大小写/子目录） | `ModLoader.IsDeclaredRuntimeAssembly` | ✅ |
| `runtimeApiVersion` 必须**恰好** 1 | — | ✅ |
| `runtimeAssemblyPolicy = "optional"`：DLL 挂了不连坐角色 | `XWModManifest.IsRuntimeAssemblyRequired()` | ✅ |
| ⚠️ `TryInitializeRuntimeEntry` 失败 → **无条件整包回滚**，**不受 policy 保护** ⇒ 入口的 Initialize / OnAllModsLoaded / Shutdown **一律不许抛异常** | `ModLoader.cs:670` | ✅ 三个回调全部 try/catch 吞掉 |

另外两条易错点：

* 入口类型 **FullName 必须等于 `runtimeEntryType`**（无命名空间 ⇒ 就是纯类名），
  且必须 `public` + 公开无参构造 + **非嵌套**（嵌套类型的 `FullName` 带 `+`）。
* `Runtime/ModAssembly.dll` 不是可推导的资源类别，但必须**同时**出现在 `manifest.resources` 里，
  且位置遵守 `SyncProject` 的规范序（`OrdinalIgnoreCase` 升序 ⇒ `Resources/…` 在前、`Runtime/…` 在后），
  否则编辑器一打开工程就会重写 `mod.json`。

### 7.3 组件两个 `InstanceId` 是运行时查找键，**绝不能改**

| InstanceId | 谁在查 | 源码 |
|---|---|---|
| `character.catapult` | 插件 `componentManager.GetRuntime<CatapultComponent>("character.catapult")` | 插件源码常量 |
| `character.fire` | `TowerDefenseZombieImppult._Ready()` + `ImpSpawn()` 的 `_fireComponent.firePosMarker[0]` | `TowerDefenseZombieImppult.cs:23 / 136` |

少了 `character.fire`，`ImpSpawn()` 会在取 `firePosMarker[0]` 时直接炸。

### 7.4 顺带说明：为什么场景里的精灵节点还叫 `ZombieImppult`

投石车/发射组件是按 **NodePath** 找接点的：

```
sprite          = SpriteGroup/TransformPoint/ZombieImppult
headSlot        = …/ZombieImppult/HeadSlot
FireSlot        = …/ZombieImppult/FireSlot          （unique_name_in_owner，脚本用 %FireSlot）
FireMarker      = …/FireSlot/FireMarker             （FireComponentDefinition.firePosMarkerPaths）
ZamboniSmoke    = SpriteGroup/TransformPoint/ZamboniSmoke
```

保留内置的节点名 ⇒ 这五条 NodePath 可以**原样照抄**内置资源，一次改名都不用做。
角色的对外身份由 `config` 决定，与节点名无关。

---

## 8. 验收

### 8.1 离线闸门（两份游戏构建各跑一遍）

`dotnet run --file runtime_src_zombie/check_gates_zombie.cs -- <refDir> <projDir> <pmod> DiscoGargantuarPultRuntimeEntry`

| 构建 | `PlantsVsZombies.dll` | 结果 |
|---|---|---|
| `D:\zzz\植物大战僵尸杂交版0.28\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64` | 26 115 584 B | **146 PASS / 0 FAIL** |
| `D:\zzz\植物大战僵尸杂交版发布版0.28.0.控制台Csharp\data_PlantsVsZombies_windows_x86_64` | 26 102 784 B | **146 PASS / 0 FAIL** |

覆盖 8 组：

1. `InferRuntimeEntry` 对包内 9 条路径的推导（3 条注册 + 6 条「不作资源条目」）；
2. `XWModManifest.Load` 读回真 `mod.json`：runtime 四字段 / id / provides / overrides 空 / translations 空；
3. `ValidateDeclaredPackageExecutables` 正向 + **两个负向对照**（塞 `Runtime/Evil.dll`、塞包内 `.cs`）；
4. `XWModRuntimeCompatibility.ValidatePackage`；
5. `SyncProject` 在工程副本上返回 `false` 且 `mod.json` 字节前后一致（= 编辑器不会重写）；
6. 入口类型本身：public / 非嵌套 / 有无参构造 / 实现 `IXWModRuntimeEntry` / FullName 相符；
7. 插件依赖的**运行时接缝**（`OnFireEvent`、`characterNode`、`OnLand`、`GetFallTime`、
   `Hypnoses`…、`Almanac.zombiePacketBank`、`_zombieInitialized`、`TOWERDEFENSE_PACKETBANKS`…）；
8. `.tres` 靠**字段名**生效的接缝（`TowerDefenseZombieConfig.*`、`CatapultComponentDefinition.*`、
   `FireComponentDefinition.*`、`AttackComponentDefinition.attackType`、`CharacterComponentSet.*`…）
   + `PACKET_TYPE.ZOMBIE == 6` 的枚举值断言。

### 8.2 字节幂等（`.cache/check_idempotent_zombie.py`）

* 生成器**连跑 3 次**，15 个产物的 sha1 每次都一样；
* 预埋 3 个「历史改名」假旧产物 → 全部被 `sweep_stale_files` 清掉；
* `Mods/暴走舞王伽刚特尔投石车僵尸/` 镜像与工作区构建目录**逐字节一致**。

### 8.3 产物指纹

| 产物 | 大小 | sha256 |
|---|---|---|
| `dist/暴走舞王伽刚特尔投石车僵尸.pmod` | 16 180 B | `4cb669fe00402117b2ac3041029c1b04f19458cf005c77040c1949dcde800f48` |
| `Runtime/ModAssembly.dll` | 19 456 B | `e30a6bc4877dc80f6bcf718b3f4dd015d218abefa6e88fed705c1b61fba26a18` |

DLL 字符串指纹（`#Strings` = UTF-8 / `#US` = UTF-16LE，**必须按字节搜**）：
`ZombieDiscoGargantuar`×12、`ZombieImp`×5、`child_entered_tree`×5、
`ZombieDiscoGargantuarPult`×5、`GeneralZombie`×3。

### 8.4 安装状态

* `Mods/暴走舞王伽刚特尔投石车僵尸.pmod` ✅
* `Mods/暴走舞王伽刚特尔投石车僵尸/`（72 个标准目录 + 全量资源 + `.pvzmodeproject`）✅
* `Mods/enabled_mods.json` = `["discogargantuarpult", "PeaOverhaul", "supergatlingpea", "vampirepool"]` ✅
* `mod_editor_recent_projects.cfg` 已登记（3 条，未丢别人条目）✅

---

## 9. 想改数值？只动一个地方

### 9.1 数值 / 卡片字段（改完**只需重跑生成器**，不用重编译插件）

全在 `build_zombie_disco_pult.py` 顶部常量区：

```python
HP_TOTAL = 3000.0            # 有效总血（= HITPOINTS + HP_NEAR_DEATH）
HP_NEAR_DEATH = 170.0        # 濒死线；改用 0.0 = 取消濒死阶段
HITPOINTS = HP_TOTAL - HP_NEAR_DEATH
ATTACK = 100000.0
SMASH_ATTACK = 100000.0
COST = 0
PACKET_COOLDOWN = 0.0
ATTACK_TYPE = "Smash"        # ← 需求 5
PROJECTILE_NUM = 4           # 投几发
FIRE_INTERVAL = 3.0          # 每发间隔（秒）
DISPLAY_NAME = "暴走舞王伽刚特尔投石车僵尸"
```

改完 `python build_zombie_disco_pult.py`；自检不过会**拒绝写盘**（退出码 3）。

### 9.2 投掷单位 / 落点 / 保险丝（改完**必须重编译插件**）

`runtime_src_zombie/DiscoGargantuarPultRuntimeEntry.cs` 顶部常量：

```csharp
private const string ThrownPacketName = "ZombieDiscoGargantuar";   // 想换投别的僵尸就改这里
private const string ImpPacketName    = "ZombieImp";               // 要换掉的单位（内置硬编码的那个）
private const int LandingGridMin = 3;                              // 落点列区间，与 ImpSpawn() 一致
private const int LandingGridMax = 5;
```

⚠️ `LandingGridMin/Max` 与生成器里的 `LANDING_GRID_MIN/MAX` 是**两份拷贝**，改一处要同步另一处
（生成器 docstring 里已标注）。改完 `python runtime_src_zombie/build_runtime.py --check`，
再重跑生成器（它会把新 DLL 搬进包并镜像到 `Mods/`）。

---

## 10. 本次新踩到的三个坑（都已固化进代码/自检）

### 坑 1：`enabled_mods.json` 只增不删 → 改名后留下两个 id

`MOD_ID` 从 `discogargantuarPult` 改成 `discogargantuarpult`（只为与
`vampirepool` / `supergatlingpea` 的全小写风格统一）之后，
`Mods/enabled_mods.json` 里**同时**留下新旧两条：

```json
["discogargantuarPult", "discogargantuarpult", "PeaOverhaul", ...]
```

游戏会拿旧 id 去扫 `Mods/*.pmod`，扫不到就报一条未知 Mod 告警，而且**再跑生成器也不自愈**。

**修法**：`merge_enabled_mods()` 现在会把「与本 Mod id **仅差大小写**」的条目视为
本 Mod 自己的历史 id 直接清掉并回报（别的 Mod 不可能与本 Mod id 只差大小写，所以安全）。
本次残留也已手动清掉。

### 坑 2：反射离线探针不能只用 `GetField`，也不能只用 `GetMethod(name)`

* `CharacterComponentSet.ParentSet` / `Components` / `RemovedInstanceIds` 与
  `FireComponentDefinition.firePosMarkerPaths` / `fireInterval` … 在源码里都是
  **`public X { get; set; }` 属性**（不是字段）⇒ `GetField` 查不到，会误报 FAIL。
  Godot 的 `.tres` 属性名对**字段和属性都成立**（生成器/godot 都会在 ClassDB 里注册同名属性），
  ⇒ 断言必须写成「**public 字段或属性存在**」，并回报它到底是什么。
* `Type.GetMethod(name, flags)` 在**有重载**时抛
  `AmbiguousMatchException`（本次死在 `GetLogicalGlobalPosition()` 上）；
  `Hypnoses(double time = -1.0, …)` 带默认参数，按 0 参查**查不到**（虽然源码里 `Hypnoses()` 能编译）。
  ⇒ 统一改成「按名字取全部成员再筛参数个数」。

### 坑 3：`unique_id` / `parent_id_path` 是 Godot 4.7 的可选字段

见 §6。别为了让场景「跟内置长得一样」而伪造它们（哈希规则没破出来，硬写风险更大）。
判断「可不可选」的通用办法：**在解包树里找同类资源中不带该字段的现网样本**（这次找到 319 个）。

---

## 11. 进游戏测试 / 排查顺序

1. **先在游戏里确认 Mod 被加载**：看 `logs/godot.log` 里有没有
   `[ModLoader] package applied: … resources=9; runtimeEntry=DiscoGargantuarPultRuntimeEntry`。
   没有这一行 ⇒ 包级别就没过（多半是 `manifest` / 路径 / 可执行文件闸门），先跑 §8.1 的离线校验。
2. **选卡界面 / 关卡编辑器能不能选到它**：这是插件职责 ②。选不到就看
   `[DiscoGargantuarPult]` 前缀的日志 ——
   `已把「ZombieDiscoGargantuarPult」补进卡库「GeneralZombie」的「Zombie」分类`。
   没有这条 ⇒ `TOWERDEFENSE_PACKETBANKS` 还没加载完 / 卡库被别的 Mod 覆盖了。
3. **投石时投出来的是不是暴走舞王伽刚特尔**：这是插件职责 ①。
   如果投出来仍是小鬼，按这个顺序看日志：
   * `运行入口已初始化；PackageRoot=…` —— 插件有没有被起起来；
   * `已挂上第 N 个「ZombieDiscoGargantuarPult」投石组件` ——
     没这条说明 `config.name` 没对上（或 `CatapultComponent` 的 `InstanceId` 被改了）；
   * `已监听「…」的 child_entered_tree（第 N 次绑定）` —— 没这条说明父节点没拿到
     （`TowerDefenseGroundItemBase.characterNode` 还没建好，或该字段为 null）；
   * `第 N 次投掷替换：ZombieImp → ZombieDiscoGargantuar，落点 x=…，飞行 …s。` ——
     **这条才是替换成功的标志**；没有它请对照下面几条：
     * `找不到 characterNode，本次保留原小鬼。` —— 投掷那一刻父节点还是 null（时序没对上）；
     * `找不到包「ZombieDiscoGargantuar」，本次保留原小鬼。` —— 目标包没进卡库（多半是别的
       Mod 覆盖了 `TOWERDEFENSE_CHARCATERS` / 包名写错）；
     * `生成「ZombieDiscoGargantuar」失败，本次投掷为空。` —— `PacketConfig.Create()` 抛了；
     * `替换投掷单位异常（本条只报一次，仍会继续尝试）：…` —— 替换逻辑内部异常，看异常消息。
   替换**成功**后还应看到投掷单位**落地就开始走**；若它落地后傻站着，看有没有
   `投掷单位落地事件超时（已用保险丝强推行走）。` —— 有这条说明 `OnLand` 没等到、被 3 秒保险丝兜住了
   （能走就行，但值得查为什么没等到）。
4. **血量 / 攻击 / 碾压**：`InformationPanel`（选卡信息面板）和图鉴僵尸页应显示中文名与说明；
   数值只能实战验（血量 3000 = 承受总伤害 3000 后死亡，濒死线 170）。

### ⚠️ 未验证项（如实记录）

* **插件在运行期的实际效果只能进游戏确认**（离线闸门只证明「接缝都在、字节确定、包能过审」，
  不能证明 Godot 运行时的节点树时序 100% 如预期）。
* **复用小鬼投石车僵尸的 `.cs`**：合规性已由 ModLoader 的脚本消毒规则证明（§2.2），
  但「Mod 场景引用游戏自带脚本」这条路我们此前没在真机跑过（植物包走的是同一条路，实机也待确认）。
* **贴图复用**：外形仍是小鬼投石车僵尸（需求 7 明确要求「暂时复用」）。
* **代价（需求本身带来的）**：本卡进了共享卡库，所以「随机取卡 / 植物礼盒 / debug 全开卡池」
  都可能把它给你 —— 这是「能被选到」的必要条件，不能既进池子又不进池子。

---

## 12. 交付物终检（`.cache/final_report_zombie.py`，32 条全 PASS）

这是一个**只读**的收尾核对脚本，把「日志里能看到的东西」换成「本地就能断言的字节事实」。
跑法：

```
python .cache/final_report_zombie.py
# 输出重定向到 .cache/_out_final_zombie2.txt，退出码 0 = 全绿，3 = 有 FAIL
```

它断言的四组事实：

| 组 | 断言 | 结果 |
|---|---|---|
| `.pmod` 两份位置 | `dist/` 与 `Mods/` 各 16180 B、sha256 `4cb669fe…`、**逐字节一致** | PASS |
| zip 结构 | 条目数 9、`mod.json` 排第 0、**不含 `.cs` / `.pvzmodeproject` / `.uid` / dotfile**、条目集 == 构建目录（去掉 `.pvzmodeproject`）、顺序 == `mod.json` 优先 + 字典序 | PASS |
| `mod.json` 字段 | `schemaVersion=2`、`id`、`name`（中文显示名）、`translations=[]`、`runtimeAssembly` 字面量、`runtimeEntryType`、`runtimeApiVersion=1`、`runtimeAssemblyPolicy=optional`、`resources` == zip 去 `mod.json`（规范序）、`provides` 三键 | PASS |
| `Runtime/` | 只有 `ModAssembly.dll`、19456 B、sha256 `e30a6bc4…`、**包内 DLL 与构建目录一致** | PASS |
| Mods 镜像 | `STANDARD_DIRS` 恰 72、镜像文件集 == 构建目录、**镜像目录集 == `STANDARD_DIRS` ∪ 包内目录（78 个）**、72 个标准目录一个不缺 | PASS |
| 装订 | `enabled_mods.json` 含 `discogargantuarpult` 且**无大小写重名残留**、未丢别人的 3 条、最近工程记录**无 CR** | PASS |

> 写这个脚本时**先踩了三个错断言**（记在这里免得下次再犯）：
> ① 以为「构建目录文件数 == 9」——其实构建目录里还有 `.pvzmodeproject`（**本来就不入包**），
> 文件数是 10，该断言的是 **zip 内条目 == 9**；
> ② 以为「Mods 镜像子目录 == 72」——72 是 `STANDARD_DIRS` 的数量，镜像还要加本包自己造的
> `Runtime` + 角色 5 层子目录，正确值是 **78**；
> ③ 以为 manifest 里的字段叫 `runtimeEntry` —— 真名是 **`runtimeEntryType`**。
> 另外 **zip 条目顺序 ≠ 文件系统字母序**（`mod.json` 被强制排第 0，而字母序里 `R` < `m`
> 会让它排最后）⇒ 比对条目时比**集合**，顺序另立一条断言。
