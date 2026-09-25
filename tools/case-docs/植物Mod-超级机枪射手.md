# 植物 Mod：超级机枪射手（Plant 类）

> ⚠️ **外观（贴图/动画）已换代，本文 §4「贴图是复用的」等描述为早期形态，勿据此推断现状。**
> **当前外观 = 未重置版官方素材直转**（`SuperGatling.reanim.compiled` 27 轨 × 87 帧 → `.dat` 344 418 B / 图集 256×296 / `insertLayerId=16`）。
> 权威出处：`植物Mod-超级机枪射手-换贴图换动画指南.md` **§11（路线 D）**；生成入口 `.cache/build_official_skin.py` + `verify_official_skin.py`（**114/0**，另有负向测试 **5/5**）。

> 生成器：`build_plant_super_gatling.py`（幂等，可重复运行，一次产出三种东西）
> 插件源码/编译：`runtime_src_plant/`（`SuperGatlingPeaRuntimeEntry.cs` + `build_runtime.py`）
> 构建目录：`SuperGatlingPea/`（工作区）
> 游戏侧产物（两种形态，缺一不可，理由同地图 Mod §7）：
> * `Mods/超级机枪射手.pmod` ← 游戏**只加载**这个
> * `Mods/超级机枪射手/` ← Mod 工程目录（72 标准子目录 + `mod.json` + `超级机枪射手.pvzmodeproject`）
>
> 复核脚本：
> * `.cache/check_modloader_gates.py`（**ModLoader 硬闸门静态复刻**，33 项）
> * `.cache/check_plant_super_gatling.py`（**314 项**规则核对。各段条数由脚本**末尾自带的 `分节断言数:` 行现算**，不再手写：A 13 / A10 10 / A11 7 / B 40 / **B2 程序集 8** / **B3 卡库图鉴 61** / C 20 / **C2x 41** / C4x 31 / C3x 20 / D 52 / E 10 / 文件头 1 = 314。其中「共用判定核心」= **K15 系列 16 + K16 1 + K18 2 + K19 4 = 23 项**，见 §3.7）
> * `runtime_src_plant/check_gates_plant.cs`（**反射直调游戏程序集的真函数**：53 项，两份游戏构建都跑）
> * `.cache/_neg_test_volley.py` / `.cache/_neg_test_head.py` / `.cache/_neg_test_almanac_text.py`（负向测试 8 + 19 + 9 = 36 条）
> * `runtime_src_plant/check_entry.cs` → 用 `runtime_src/check_entry.cs`（入口发现，11 项）
> * `.cache/check_idempotent_plant.py`（3 连跑字节幂等）
>
> 逆向依据：`.cache/植物管线逆向结论.md`

---

## 1. 它是什么

| 项 | 值 |
|---|---|
| Mod id | `supergatlingpea` |
| 统一键 | **`SuperGatlingPea`**（角色目录名 = 场景文件名 = 精灵文件名 = `config.name` = `packet.saveKey` = 卡片文件名） |
| 角色场景 | `Resources/Characters/Plants/SuperGatlingPea/Scene/SuperGatlingPea.tscn` |
| 精灵场景 | `Resources/Characters/Plants/SuperGatlingPea/Sprite/SuperGatlingPea.tscn`（**卡片预览用，必须有**） |
| 卡片 | `Resources/Cards/SuperGatlingPea.tres` |
| 贴图 | **复用原版机枪射手** `GatlingPea.tscn`（`res://` 引用，不复制素材） |
| 场景脚本 | **复用原版** `TowerDefensePlantGatlingPea.cs`（`res://` 引用） |
| **大招** | **每次攻击 10% 概率触发：5 秒内倾泻 ≈300 颗豌豆**（托管运行时插件实现，见 §3） |
| **可选性** | **进图鉴的「金卡」分类 + 进选卡界面**（`GeneralPlant` / `Total` 卡库的 `Gold`，插件运行期补；见 §3.2.2 / §3.5 / §3.6 副作用） |
| **插件** | `Runtime/ModAssembly.dll`，入口 `SuperGatlingPeaRuntimeEntry`（源码 `runtime_src_plant/`）。干三件事：① 大招；② 把卡片补进**共享卡库** `GeneralPlant.Gold`（⇒ **选卡界面能选到**）；③ 兜底补图鉴那份拷贝的同一分类（§3.2 / §3.5） |
| 阳光花费 | **600**（`config.cost`） |
| 种植涨价 | **100**（`config.costRise`，同关每再种一张该卡 +100） |
| 冷却 | **30 秒**（`config.packetCooldown = 30.0`） |
| 卡类型 | **金卡 GOLD**（`packet.type = 1`） |
| **血量** | **1000**（`config.hitpoints = 1000.0`；类默认是 300，见 §2.6） |
| **可种植性** | **空地可直接种**，不再必须种在**双发射手**（`PlantPeaShooter`）上；同时**保留**「种在双发射手上升级」这条路（卡片内联 packet override，见 §2.6） |
| 射速 | **1.5 秒 / 轮**（`fireInterval = 1.5`） |
| 每轮弹数 | **7 颗**（7 条发射配置 + `fireNumAtOnce = true`） |
| 散射 | **±15°**（`dir` 依次 `-15, -10, -5, 0, 5, 10, 15` 度） |
| 弹速 | 500（原版 Starfruit 同值） |
| 子弹 | `Pea` |

---

## 2. 为什么是「7 条发射配置」而不是 `fireNum = 7`

这是本次改造最关键的一处机制对齐。`FireComponent` 里 `fireNum` 有**两种含义**，
靠 `fireNumAtOnce` 开关切换（`FireComponent.cs:3413` `FireConfiguredVolley`）：

```csharp
if (!fireNumAtOnce) { Fire(); return; }
for (int i = 0; i < fireNum; i++) { currentFireNum = i; Fire(i == 0); }
```

| 写法 | 结果 | 原版例子 |
|---|---|---|
| `fireNum = 7` + `fireNumAtOnce = false` | 7 颗**同一方向**层层叠出（视觉像 1 颗） | 豌豆射手 |
| `fireNum = 1` + `fireNumAtOnce = true` + **7 条 config** | 一次齐射 **7 条不同方向** | 五角星（5 条）、三线射手（3 条） |

我们要的是**扇形 7 颗**，所以走第二种：`fireNum = 1`（防止 7×7=49 颗）+ `fireNumAtOnce = true`，
再把方向差异写进 **7 条 `FireComponentFireProjectileConfig`**。

> ⚠️ 注意场景节点（`SuperGatlingPea.tscn` 的 `fireNum`）也写 **1**，与原版
> `TowerDefensePlantGatlingPea.tscn` 完全一致。场景上的 `fireNum` 是走
> `TowerDefensePlantGatlingPea.fireNum` setter，而该 setter 只在 `IsNodeReady()` 为真时才
> 转发给 `FireComponent`；场景属性是在 Ready **之前**赋值的 ⇒ 它其实只是"存档用"的装饰值。
> 真正的 7 发只来自 ComponentSet。写 7 会被 `ExportVariantSave` 存进存档，
> 与组件语义不符，所以对齐原版。

方向字段是 `dir`，**单位是度，0 = +X（右）**（`FireComponent.cs:3434` `Fire()`）：

```csharp
velocity = cfg.speed * Vector2.FromAngle(Mathf.DegToRad(cfg.dir));
```

**朝向翻转不用管**：`CreateProjectile`（`:2684`）末尾做了
`velocity * Mathf.Sign(parent.Scale.X * parent.transformPoint.Scale.X * parent.sprite.Scale.X)`，
所以只写一套「向右」的 `dir`，僵尸在左边时自动镜像成 ±15° 向左。

> 参照范式（全部来自 V0.28 解包）：
> * `Starfruit` —— 5 条 config，`dir = 330/270/180/90/30`，`firePosId = 0..4`，`speed = 500`
> * `ThreePeater` —— 3 条 config，用 `offsetLine = -1/0/+1`（换行，不换角度）
> * `SplitPea` —— `fireNum = 2` + `fireNumSkip = 1` + `speed = -300`（向后打）
> * `Gold/CatGatlingPea` —— 金卡 + `costRise = 100` 的现成范例（本 Mod 数值即照它写）

---

## 2.5 ⚠️「游戏加载失败」的 4 个硬闸门（2026-09-18 修复）

用户反馈「游戏加载失败」。逐行读 `addons/ModEditor/ModSystem/` 后定位到 **4 个各自都能单独
让整包被拒的闸门**，此前全踩了。**修复要点已写成 `.cache/check_modloader_gates.py` 离线复刻**
（下次改包先跑它，30 秒出结论，不用进游戏）。

### 闸门 1：包内自引用不能用 `res://`（**这是真正的加载失败原因**）

```csharp
// ModLoader.TryGetGodotResourcePath
resourcePath = ProjectSettings.LocalizePath(absolutePath);   // → user://ModsCache/<名>/…
resource = ResourceLoader.Load<PackedScene>(resourcePath, "", CacheMode.Ignore);
```

包被解到 `user://ModsCache/超级机枪射手/`，加载时用 **user:// 路径**。于是：

| 引用写法 | 解析结果 | 结果 |
|---|---|---|
| `../Config/X.tres`、`./XComponentSet.tres`（**相对**） | 在 `user://ModsCache/<名>/…` 树内 | ✅ 成功 |
| `res://Resources/Characters/Plants/SuperGatlingPea/…` | 在**游戏 pck 根**解析 → **那里没有 `Resources/` 目录**（解包已确认 res:// 根下无 `Resources/`） | ❌ 配置/组件集加载失败 → 角色被拒 → 整包 apply 失败 |

**结论**：包内自引用一律相对路径；只有指向**游戏自带**资源
（`res://Prefab|Asset|Script|Resource|Registry|Extends`）才用 `res://`。
官方模板 `XWResourceCreateRoute.BuildCharacterRuntimeSceneContent()` 也是这么写的
（`../Config/{0}Config.tres`、`../Sprite/{0}.tscn`）。

### 闸门 2：必须额外交付一个 **Sprite 场景**

`XWModContentValidation.Validate()`：

```csharp
string key = CHARCTAER_SPRITE.ContainsKey(saveKey) ? saveKey : characterConfig.name;
RequireReference(manifest, "CharacterSprite", key);   // 查不到 → throw
```

没有 `Resources/Characters/Plants/<Key>/Sprite/<Key>.tscn`，`CHARCTAER_SPRITE` 里就没有这个键
⇒ **`ApplyMod` 抛异常、整包被拒**。就算侥幸过了这一关，运行时
`TowerDefenseManager.GetPacketSpriteScene()`（`TowerDefenseInGamePacketShow.cs:1161` 每张卡都会调）
还会 `GetCharacterSprite(name)` → `throw new KeyNotFoundException`。
**这正是「缺少通用组件」的真正含义。**

### 闸门 3：`packet.saveKey` 必须等于「注册键」

```csharp
if (towerDefensePacketConfig.saveKey != value.Key)
    throw new InvalidOperationException("Packet/" + value.Key + " 的 saveKey 与注册键不一致");
```

注册键 = `Resources/Cards/<文件名去扩展>`。生成器 v1 文件名是
`SuperGatlingPeaPacket.tres` 而 `saveKey = "SuperGatlingPea"` ⇒ **直接 throw**。
本次把卡片改名为 `Resources/Cards/SuperGatlingPea.tres`，让
`注册键 == saveKey == config.name == 场景键 == 精灵键` 全部统一成 `SuperGatlingPea`。

同理 `characterConfig.name` 必须是**角色场景文件名/目录名**（`<Key>`）：
`TowerDefensePacketConfig.Create()` → `CreateCharacter(characterConfig.name)` →
`ResourceManager.TOWERDEFENSE_CHARCATERS[name]`，而 mod 角色只可能注册在 `<Key>` 这个键上。

### 闸门 4：`unlockCheckList` 只能是空表或 Mod 专属条件

```csharp
if (unlockCheckList != null && unlockCheckList.Any(c => !(c is XWModProgressUnlockCondition)))
    throw new InvalidOperationException("Packet/… 必须使用 Mod 专属解锁条件");
```

原版 GatlingPea 用的是 `UnlockConditionPacketBankCategoryPacketUnlockNumConfig`
（"集齐 GeneralPlant 银行 Original 类 10 张"）——**这是游戏内条件，照抄必炸**。
本 Mod 写 `unlockCheckList = []`（空表 ⇒ 直接可用，`TowerDefensePacketConfig.cs:1222`）。

### 附带发现

* `provides` 里每个键都**必须真的被注册**，否则
  `ModLoader.ValidateManifestRegistrations` 判假 → 整包 apply 失败。所以
  `provides` 只写 `Character / CharacterSprite / Packet` 三项，且键都正好是 `SuperGatlingPea`。
* `CharacterRequiresCompanion` 只在**场景根**带
  `mod_character_script_binding="CompanionOnly"` 时才要求托管程序集 —— 我们没带，所以纯数据可行。
  （`TryInstantiateEffectiveCharacter` 会因此失败并**回退**到 `GetChacraterScene`，属正常路径。）
* 用户问的「通用组件」（`DamagePoint` / `Custom` / `Armor`）**原版 GatlingPea 也没有**
  （其 Config 里 `damagePointData / armorData / customData = null`）。编辑器模板会生成
  `DamagePoint/DamagePointData.tres` 等三件，但那只有坚果类（Wallnut 等）才真正使用。
  **本 Mod 的 Config 与原版 GatlingPea 字段一致**（唯一主动差别是 §2.6 的 `hitpoints`），不需要补。

---

## 2.6 血量 1000 + 「不用种在双发射手上」（2026-09-19）

### 血量：一行字段

`config.hitpoints` 由 `TowerDefenseCharacterInstance._Init` 搬进实例：

```csharp
// Resource/TowerDefense/Character/Instance/TowerDefenseCharacterInstance.cs:317-320
hitpointsNearDeath = config.hitpointsNearDeath;      // 我们没写 ⇒ 0
hitpointsBase      = config.hitpoints;               // 我们写 1000.0
hitpoints          = hitpointsBase + hitpointsNearDeath;   // ⇒ 1000
hitpointsSave      = hitpoints;
```

类默认是 `public double hitpoints = 300.0;`（`TowerDefenseCharacterConfig.cs:14`），
所以「改血量 = 在 `<Key>/Config/TowerDefensePlant<Key>.tres` 里加一行 `hitpoints = 1000.0`」，
**不需要插件**。⚠️ 写在 `name` 之后 —— 与类声明顺序一致，编辑器保存时不会重排。

### 「必须种在双发射手上」是怎么回事

本卡是**覆盖卡**，配置里 `plantCover = ["PlantPeaShooter"]`。
`TOWERDEFENSE_PLANT_PEASHOOTER_NAME` 的中文列就是**双发射手**（`Asset/Translate/Translate.csv`），
所以用户描述的底座完全正确 —— 内置机枪射手 `PlantGatlingPea` 也是这么配的。

闸门在 `TowerDefenseCellInstance.CanPacketPlant`：

```csharp
// Registry/Battle/Feature/Map/Resource/Cell/TowerDefenseCellInstance.cs:787-800
if (packetConfig.GetPlantCover().Count > 0 && !noLimit)
{
    foreach (... characterList ...)                       // ① 这一格里有 plantCover 名单里的植物？
        if (... && packetConfig.GetPlantCover().Contains(character4.config.name))
            return true;                                  //    有 ⇒ 允许（= 升级）
    if (!packetConfig.GetCoverCanDirectPlant())
        return false;                                     // ② 没有 ⇒ 除非开了「也能直接种」，否则拒
}
```

而 `GetCoverCanDirectPlant()` 长这样（`TowerDefensePacketConfig.cs:500-507`）：

```csharp
public bool GetCoverCanDirectPlant()
{
    if (GodotObject.IsInstanceValid(_override)) return _override.coverCanDirectPlant;
    return false;                      // ← 没有 override 就**硬编码 false**
}
```

**关键结论：这个开关不在 `characterConfig` 上，只在 packet 的 `override` 上。**
⇒ 光改 Config / `plantCover` 都做不到「不改底座还能直接种」，必须给卡片挂一个 `override`。

### 解法：卡片内联一个 packet override，只开 `coverCanDirectPlant`

这不是我们发明的路子 —— 官方 Gold 挑战关
`Asset/Config/Level/TowerDefense/Challenge/Gold/Challenge_Level2_3.tres` 给
`PlantGatlingPot` 开的就是这同一个开关（全解包共 2 个正例）。写法照抄：

```ini
[ext_resource type="Script" path="res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/TowerDefensePacketOverride.cs" id="3"]

[sub_resource type="Resource" id="PacketOverride_direct_plant"]
script = ExtResource("3")
coverCanDirectPlant = true
metadata/_custom_type_script = ".../TowerDefensePacketOverride.cs"
```

然后 `override = SubResource("PacketOverride_direct_plant")`。

**为什么只写这一个字段就够了** —— `TowerDefensePacketOverride` 的默认值全是「不覆盖」语义，
所有 `GetXxx()` 都会回落到 `characterConfig`：

| 字段 | 默认 | 后果 |
|---|---|---|
| `type` | `NOONE(-1)` | `_GetType()` 回落 `packet.type` |
| `cost / costRise / costMultiple` | `-1` | `GetCost()` 等回落 |
| `packetCooldown / startingCooldown` | `-1.0` | 回落（冷却仍 30s） |
| `weight / wavePointCost` | `-1` | 回落 |
| `plantCover` | `[]` | `GetPlantCover()` 在 **Count>0** 时才用它 ⇒ 空表回落，**底座名单保住** |
| `hypnoses` | `false` | `GetHypnoses()` 回落 |
| `islimitGridNum` | `true` | 无条件读，但**与无 override 时的硬编码 `true` 同值** ⇒ 中性 |
| `coverCanDirectPlant` | `false` | 无条件读 ⇒ **这就是我们要开的那一个** |
| `characterOverride` | `new TowerDefenseCharacterOverride()` | ⚠️ 非 null ⇒ 每次种植都会 `ExecuteCharacter()`。逐字段核对过：`scale / hitpointScale / walkSpeedScale / animeSpeedScale` 全是 `-1`、四个数组为空、`invisible=false`、`_hasCanMowerMoveOverride=false` ⇒ **完全空操作**，不会碰血量/缩放/动画 |

生成器的自检会**拒绝**往这个 override 里多写字段（只允许
`script` / `coverCanDirectPlant` / `metadata/`），`check_plant_super_gatling.py` 的 **C50** 还会用
一份「故意多写 `cost = 1`」的假 body 做**反向对照**，防止那条断言变成永远为真的假绿。

### 副作用 / 边界（如实记录）

* **好消息**：这是「追加能力」而不是「替换」—— 空地能直接种，**同时**保留种在双发射手上升级。
* ⚠️ **关卡若用 packetOverride 覆盖了本卡，会把这里的值顶掉**（`PlantAtCore` 会临时
  `packetConfig._override = <关卡那份>`），于是又变回「必须底座」。
  想**彻底免疫**（代价是失去升级底座）就把 `plantCover` 置空：`plantCover = []`。
* ⚠️ `plantCoverAll` 是**死字段** —— 全解包只在编辑器 UI 里被绑定，**运行时从未被读取**，
  别拿它当开关。
* 血量改的是**配置**，按卡库随机发放/关卡固定波次生成时同样生效（同一份 config）。

---

## 3. 10% 概率大招：已实现（从「纯数据」升级为「数据 + 托管运行时插件」）

> 2026-09-18 的版本里这一节叫「未实现项」。2026-09-19 起需求第 3 条
> 「每次攻击有 10% 触发大招：5 秒内向前方 ±15° 散射约 300 颗豌豆」**已经做出来了**，
> 走的是**托管运行时程序集**（`Runtime/ModAssembly.dll`）——这是唯一可行的路。
> 下面保留「为什么纯数据做不到」的原始证据，因为那是选这条路的原因。

### 3.1 为什么纯数据做不到（原始证据，别删）

| 缺什么 | 证据 |
|---|---|
| **概率** | `FireComponentFireProjectileConfig` 只有 **8 个字段**：`checkProjectileId, firePosId, speed, dir, offsetLine, fireNumSkip, fireEventNeed, projectileFlip`。没有任何 probability / chance。 |
| **延时 / 持续** | `FireComponentDefinition` 只有 `fireInterval*` 一族，没有「5 秒内改为另一种发射模式」的字段。 |
| **随机性** | `FireComponent` 唯一随机源是 `OnFireVolley(ulong randomSeed)`，种子是**确定性**的（`NetworkDeterministicSeed.ForCharacterEvent(syncId, seq, 4051590893uL)`）——为了联机同步，游戏刻意**不允许**真随机。 |
| **数量** | `FireComponent.AttackProcessing`（FireComponent.cs:3296-3299）只按 `fireInterval` 调 `sprite.timeScale`，公式封顶约 **4 倍速** ⇒ 5 秒最多 ~93 颗，**够不到 300**。 |
| **状态机** | `FireComponentStateMachine.tres` 只有 `idle / attack / restore` 三态，且 `GuardDefinition = null`，没有概率守卫可挂。 |

### 3.2 插件怎么做的（全部只用公开 API）

入口类 `SuperGatlingPeaRuntimeEntry`（`runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs`）实现
`IXWModRuntimeEntry`，**干三件互不相关的事**：

| | 干什么 | 在哪一步 | 依据 |
|---|---|---|---|
| **A** | 10% 概率大招（玩法） | `node is TowerDefenseCharacter` 分支 | §3.2.1 |
| **B** | 把卡并进**共享卡库**的 `Gold` ⇒ **选卡界面能选到** | `TryPatchCardBanks()`（每次扫描都跑，与场景树无关） | §3.2.2 |
| **C** | 兜底：把卡并进**图鉴那份拷贝**的 `Gold` | `node is Almanac` 分支 | §3.2.3 |

B 是**根上的修法**（图鉴本来就是从共享卡库拷出来的 ⇒ 补一次，两边同源一致），
C 只在「图鉴已经开着、来不及重开」时才真的起作用。三件事共用同一次「每 10 帧扫一遍」。

#### 3.2.1 A. 大招（三步）

1. **找自己**：每 10 帧递归扫场景树，找 `config.name == "SuperGatlingPea"` 的 `TowerDefenseCharacter`，
   从 `character.componentManager.GetRuntime<FireComponent>("character.fire")` 取发射组件。
   > ⚠️ 必须按 `config.name` 认，**不能按类名**：内置机枪射手也叫 `GatlingPea`，按类名会误伤原版。
2. **掷骰**：订阅 `FireComponent.OnFireVolley`（**游戏自己声明的 C# event**，FireComponent.cs:673，
   委托类型同文件 261 行）。一次齐射会逐条配置连发最多 7 次信号，用 **200ms 时间窗去重**折叠成
   「一次攻击」，然后掷 10% 骰子（`RandomNumberGenerator.Randomize()`，单机真随机）。
3. **倾泻**：命中后起一个 5 秒的节拍器，按 `Time.GetTicksMsec()`（不用帧数，掉帧/攻速都不影响总时长）
   反复调 **`FireComponent.Fire()`**（public，FireComponent.cs:3429）。
   43 轮 × 7 颗 = **301 颗**（比 300 多 1 颗，因为 7 颗是**不可分割**的一轮）。

**为什么调 `Fire()` 是安全的**：它**不受状态机约束**，只检查 battlefield / alive / parent 有效 +
每条配置的 `fireEventNeed` / `fireNumSkip`，然后逐条执行 7 条发射配置 —— 也就是说它和常规攻击
**走的是同一段代码**，命中盒、伤害计算、行号判定行为必然一致，不会出现「插件子弹打不中僵尸」这类问题。

**已知代价（如实记录）**：
* 单机真随机 ⇒ **联机会与主机不同步**。这是为了手感刻意接受的代价（确定性种子做不到「10%」）。
* 每帧扫场景树有固定开销；已用 10 帧间隔 + 只对已发现植物去重（`ReferenceEquals`）压到可忽略。
* 只对 `config.name == "SuperGatlingPea"` 生效，不碰任何原版植物。

#### 3.2.2 B. 把卡补进共享卡库 ⇒ 选卡界面能选到（**这一步决定「能不能选」**）

`TryPatchCardBanks()` 往 `ResourceManager.TOWERDEFENSE_PACKETBANKS` 里的
**`GeneralPlant.Gold`** 追加本卡；再按 `Include` 闭包算出**派生卡库**（实测只有 `Total`）也补上。

为什么是「共享卡库」而不是别的（逐条有源码位置）：

| 事实 | 位置 |
|---|---|
| 选卡界面按 `packetBankData.category[_category]` **列出可选的卡** | `TowerDefenseBattleFeaturePacketBank.cs:514`（`CategoryChooseAsync`） |
| 它的 `packetBankData` = `TowerDefenseManager.GetPacketBankData(config.packetBankType)` | 同文件 :170 |
| `packetBankType` 的**默认值就是 `"GeneralPlant"`** | `TowerDefenseLevelPacketBankConfig.cs:9` |
| 图鉴也是从同一个库拷出来的 | `Almanac.cs:219` → `WithPlants(GetPacketBankData("GeneralPlant"))` |

⇒ 只要本卡进了 `GeneralPlant.Gold`，**图鉴和选卡界面就同时有它，且同源** ——
这就是需求里「图鉴与卡牌库数据一致」的天然保证（不需要两边各维护一份）。
`Total`（`Include: [GeneralPlant, TotalZombie]`）是它的超集
（`ResourceManager.BuildExpandedPacketBank` 沿 `Include` 递归合并分类），
不补的话 `CommandManager.debugPacketOpenAll`（把卡库切到 `Total`）下又会看不到。

**幂等 + 可恢复**：卡库是全局单例、只在全量资源加载时构建一次
（`LoadFullGameplayRootsOnMainThreadAsync`），但别的 Mod 仍可能通过
`provides.PacketBank` 覆盖同名卡库（`XWModRuntimeRegistry.cs:567-570`），
所以这里**每次扫描都检查一遍**（一个分类里十几条字符串比较，开销可忽略），缺了再补，补上才打日志。

> ⚠️ **`GetPlantList()` 只认 6 个植物分类**（White/Gold/Diamond/Colour/Star/Original，
> `TowerDefensePacketBankData.cs:48-68`），**故意不认 `ModPlants`** ——
> 这就是「只进图鉴分类还不够、必须进 Gold」的硬证据。

#### 3.2.3 C. 兜底：图鉴那份拷贝（整理 + 去重）

扫到 `Almanac` 节点时做两件事（都幂等，`changed` 为假就直接 return）：

1. ★ **摘掉本卡在 `ModPlants` 里的条目**；摘空了就把整个 `ModPlants` 键删掉
   （= 用户要的「删除仅包含该角色的独立图鉴」，见 §3.5.1）；
2. 往 `category["Gold"]` 补本卡（缺才补），并顺手删掉同一分类里的**重复条目**。

正常时序下第 2 步在共享卡库里已经补好，图鉴拷贝里本来就有 —— 这里是**双保险**：
万一「图鉴已经开着 → 用户才点重新应用」，那份旧拷贝里还没有，补一下立即可见。

> ⚠️ **只在「植物页已经建过列表」时才主动刷新**（反射读私有的 `Almanac._plantInitialized`）。
> 没建过就**不碰** —— 图鉴是刻意**懒初始化**的（`PlantButtonPressed` 里
> `if (!_plantInitialized) InitPlant()`），自带的 `AlmanacVirtualizedResidencyRuntimeTest`
> 还专门断言「不得提前初始化隐藏分类 / 不得提前实例化预览节点」。
> 我们的扫描每 10 帧一次，改分类发生在图鉴刚实例化后的 ~0.17 s 内，
> 而用户点「植物」必然更晚 ⇒ 正常路径下天然就是「改好之后才初始化」，不需要我们插手。
> 反射拿不到字段就退化为「不刷新」（最坏：用户翻一次分类就能看到），绝不影响其它功能。
>
> ⚠️ 删了分类 ⇒ **必须回落 `plantCategoryId`**（`plantCategoryId >= category.Count` 时
> `InitPlant()` 会直接 return 出空列表）。回落写法与判据见 §3.5.1。

### 3.3 四条硬约束（违反 = **整包被拒**，不是「不生效」）

| 约束 | 出处 | 值 |
|---|---|---|
| `runtimeAssembly` 只能是**字面量** | ModLoader.cs:329-333 字符串相等判定 | `"Runtime/ModAssembly.dll"` |
| `runtimeApiVersion` 必须**恰好** 1 | `XWModCharacterCompanionRuntime` | `1` |
| `runtimeAssemblyPolicy` | ModLoader.cs:1606-1609 只认 required/optional | `"optional"`（加载失败不毁整包：植物照常能用，只是没大招） |
| 入口类型 FullName == `runtimeEntryType` | `TryInitializeRuntimeEntry` | `SuperGatlingPeaRuntimeEntry`（**无命名空间** ⇒ 类名即全名；必须 public + 公开无参构造 + 非嵌套） |

**额外四条**：

* ⚠️ `TryInitializeRuntimeEntry` 失败 → ModLoader.cs:667-671 **无条件整包回滚**，**不受 policy 保护**。
  所以入口的 `Initialize` / `OnAllModsLoaded` / `Shutdown` **一律不许抛异常**（代码里三个回调全 try/catch）。
* ⚠️ `Runtime/` 目录下**只许有 `ModAssembly.dll` 一个文件**。多一个 `.dll/.exe/.bat/.cmd/.ps1/.cs`
  → `ValidateDeclaredPackageExecutables`（ModLoader.cs:343-346）抛 `undeclared executable package file`。
  `build_runtime.py` 结尾有硬护栏；`sweep_stale_files` 也会清掉残留。
* ⚠️ `Runtime/ModAssembly.dll` **不是可推导的资源类别**（`InferRuntimeEntry` → false，靠
  `IsDeclaredRuntimeAssembly` 放行），但它**必须同时列进 `manifest.resources`**，且遵守
  `SyncProject` 的规范序（OrdinalIgnoreCase 升序 ⇒ `Resources/…` 在前、`Runtime/…` 在后），
  否则编辑器一打开工程就重写 `mod.json`。
* 本包场景根**没有** `mod_character_script_binding="CompanionOnly"` 元数据，
  所以**不需要伴生脚本**（`CharacterRequiresCompanion` 只在带该元数据时才要求），走标准入口即可。

### 3.4 ★ 2026-09-25 已修复：文案改为**内联**（不再走翻译键）

**结论（三条独立证据，全链路复核过一遍）**：

| 证据 | 内容 |
|---|---|
| 全库零调用 | `TranslationServer.AddTranslation` 在**整个游戏源码 + addons 里一次都没有**（只有一个同名的私有方法 `XWUniversalResourcePreview.AddTranslationPreview`，与 Godot 翻译无关） |
| `project.godot` 只挂内置表 | `internationalization/locale/translations` 只有 `res://Asset/Translate/Translate.{en,es,zh}.translation` —— Mod 加不进去 |
| ModLoader 不解析 CSV | 解包后的 `.csv` 不在 `TryResolveDeclaredResourceCandidate` 的扩展名白名单里（`ModLoader.cs:1006`）⇒ `Localization/translations.csv` **只在编辑器面板里有意义** |

⇒ 旧版本把 `name`/`describe`/`handbookDescribe`/`handbookStory` 写成
`TOWERDEFENSE_PLANT_SUPERGATLINGPEA_*` 这类 key，**进游戏就原样显示 key 本身**。

**修法**：四个字段一律写**内联真实文本**（见 §9 / §14），
于是图鉴里显示的就是中文原文，与用户给的截图逐字一致。

> ✅ `saveKey` 才是身份标识（== 注册键 == 卡片文件名去扩展 == `SuperGatlingPea`），
> 改 `name` 为字面量**不破坏注册**；官方 `XWInlineTextCoverageContract.cs:13-15` 也把
> `TowerDefensePacketConfig.name / describe / handbookDescribe` 声明为 `Title / Description`
> = **允许内联覆盖**。
>
> 🙋 副作用（如实记录）：`Localization/translations.csv` 现在退化成「给编辑器留个英文底」，
> 键改成**内联的中文原文本身**（原来的 `TOWERDEFENSE_*` 键全部废弃）；
> 多行的 `handbookDescribe` / `handbookStory` 因为会破坏朴素 CSV 行结构而**不收录**。
> 保留该文件只是因为 `mod.json` 的 `translations` 字段必须指向真实文件（`ModLoader.ValidateManifestRegistrations`）。

### 3.5 为什么 Mod 植物会「单列一类」、以及怎么既进图鉴又进选卡界面

**现象**（2026-09-19 用户两次反馈）：
1. 图鉴里本卡出现在**单独一个分类**里，而不是和内置金卡放一起；
2. 本卡**只存在于图鉴**，选卡界面（可选卡牌库）里选不到它。

**成因**（有源码位置，别删）：

| 位置 | 干了什么 |
|---|---|
| `addons/ModEditor/ModSystem/XWModContentCatalog.cs:107-123` `WithPlants()` | 把 `GeneralPlant` 卡库**深拷贝**一份，然后把所有 Mod 植物塞进**新建**的 `category["ModPlants"]`（`PlantCategory = "ModPlants"`，同文件 :15） |
| `Almanac.cs:219` | **全仓库唯一**调用 `WithPlants()` 的地方：`plantPacketBank = XWModContentCatalog.WithPlants(TowerDefenseManager.GetPacketBankData("GeneralPlant"))` |
| `Almanac.cs:324-328` | 图鉴植物页按 `category[array[plantCategoryId]]` 翻分类 ⇒ Mod 植物天然被**单列一类**，金卡分类里根本看不到 |

也就是说：**这是 Mod 系统的设计（把 Mod 内容单独隔离），不是我们包写错了**。
纯数据改不动它（`category` 是运行时 `Dictionary`，不在 `.tres` 里）——只能靠插件。

**分类键名实测**（`Asset/Config/PacketBank/PacketBankResource.json` → `GeneralPlant.Category`，
只有 6 个键；Item / GraveStone / Zombie 在别的卡库里）：

| 分类 | White | **Gold** | Diamond | Colour | Star | Original |
|---|---|---|---|---|---|---|
| 内置卡数 | 178 | **19** | 16 | 6 | 27 | 20 |

所以本卡并进去以后，金卡分类是 **20** 张。`WithPlants()` 新建的 `ModPlants` 是**第 7 个键**，
排在最后。

**修法（本包已实现，三处一起，见 §3.2.2 / §3.2.3）**：

1. **主修**：往**共享卡库** `TOWERDEFENSE_PACKETBANKS["GeneralPlant"].category["Gold"]` 追加本卡
   （+ 按 `Include` 闭包算出的派生库 `Total`）⇒ 选卡界面能选到，图鉴同源一致。
2. **兜底**：往**图鉴自己那份拷贝** `Almanac.plantPacketBank.category["Gold"]` 也补一次
   （`plantPacketBank` 是 public 字段，`Almanac.cs:101`），防「图鉴已经开着」的时序。
   图鉴是按需实例化的（`DialogManager.DialogCreate` → `Instantiate()`，
   MainMenu.cs:261 / TowerDefenseControlOld.cs:122），每次打开都是一份新拷贝 ⇒ 每次扫到都要补。
3. ★ **2026-09-25 新增 —— 把本卡从 `ModPlants` 里摘掉**（用户口径：
   「删除仅包含该角色的独立图鉴，将其保留在已有的金卡类型图鉴中」）：
   只进 Gold 还不够，`ModPlants` 那个分类仍然存在 ⇒ 本卡在图鉴里**同时出现在两个分类**
   = 用户看到的「重复」。

> ⚠️ 图鉴刷列表这一步是**有条件**的：只有 `Almanac._plantInitialized` 已经为 true（植物页建过列表）
> 才调 `InitPlant()`。图鉴刻意懒初始化（`Almanac.cs:391-397`），提前调会把预览节点和角色资源
> 在打开图鉴的瞬间就加载出来 —— 详见 §3.2.3。

#### 3.5.1 ★ 图鉴去重（2026-09-25）的实现口径

| 要点 | 做法 | 为什么不能图省事 |
|---|---|---|
| 摘的是**条目**，不是整个分类 | 倒序遍历 `category["ModPlants"]`，`RemoveAt` 掉等于 `SuperGatlingPea` 的项 | `ModPlants` 是**所有** Mod 植物共用的分类。整类删会把别的 Mod 植物一起藏起来 |
| 摘完**空了**才删键 | `if (modPlants.Count == 0) categories.Remove(ModPlantCategory);` | 用户口径要的就是「只含本角色的独立图鉴消失」；还有别的 Mod 植物在时**必须**留着分类 |
| 顺手给 Gold 去重 | 同一分类里出现两份本卡时删掉多余的（倒序删、保留下标最小的一份） | 「重复出现」的另一条可能路径，顺手堵死 |
| 删键后**回落** `plantCategoryId` | `if (almanac.plantCategoryId >= categories.Count && categories.Count > 0) almanac.plantCategoryId = categories.Count - 1;` | `Almanac.InitPlant()` 开头就是 `if (… \|\| plantCategoryId >= plantPacketBank.category.Count)` ⇒ **直接 return 出空列表**。`ModPlants` 追加在末尾，只有「正好停在这一页」才会越界，但统一回落一次最稳 |
| 刷新**仍受懒初始化守卫** | 只有 `IsPlantPageInitialized(almanac)` 为真才 `almanac.InitPlant()` | 见 §3.2.3 的三条理由，不能因为「顺手」就打破游戏原本的懒加载设计 |

> 📌 分类切换的源码口径：`PlantNextButtonPressed` / `PlantPreButtonPressed` 都是
> `plantCategoryId = (id ± 1) % category.Count`（`Almanac.cs:380 / 387`），
> `InitPlant()` 用 `category.Keys` 的**枚举顺序**取 `array[plantCategoryId]`（:323-328）。
> 所以「删掉一个键」只影响「正好停在被删那一页」的情况 —— 这也解释了为什么回落写法是
> `Min(plantCategoryId, Count-1)` 而不是粗暴归零。

### 3.6 ⚠️ 把卡放进金卡池之后的**副作用**（如实记录，这是需求本身带来的）

「能在选卡界面里被选用」= 「成为一张正常的金卡」，所以凡是**按卡库取卡**的逻辑都可能给出这张卡：

| 位置 | 会怎样 |
|---|---|
| `GoldShardDropItemHandler.cs:15` | 金色碎片/金币类掉落里 `GetCategory("Gold").PickRandom()` ⇒ 可能掉出这张卡 |
| `TowerDefenseCraterG.cs:101` | 陨石坑补卡同理（从 Gold 随机） |
| `TowerDefensePlantPanGoldBean.cs:85` | 金豆类效果的 Gold 随机池 |
| `TowerDefensePlantPresentBox(.Green).cs` / `TowerDefensePlantLuckyBlover.cs` / `TowerDefensePlantCubeBox.cs` | 走 `GetPlantList()` ⇒ 植物礼盒/幸运四叶草/方块盒可能给到它 |
| 普通关卡选卡界面 | `packetBankType` 默认 `GeneralPlant` ⇒ 各种关卡都能选（随机池按 `type=GOLD` 归类，同内置金卡） |

以上都是**内置金卡本来就会发生的事**，不算 Bug；但如果想要「只在图鉴里能看到、不进任何卡池」，
那就得回到只补图鉴那份拷贝（把 `TryPatchCardBanks()` 的调用去掉即可，一个开关）。

> 💡 若将来游戏大版本改了字段名，两处补丁都会在各自的 `try/catch` 里失败并打一行
> `补共享卡库…失败` / `补图鉴…失败` —— **不影响大招和植物本身**，也不会整包回滚。
> 离线闸门 `check_gates_plant.cs` 第 6 组会直接核对
> `Almanac.plantPacketBank` / `Almanac._plantInitialized` / `TOWERDEFENSE_PACKETBANKS`
> 这些接缝在两份构建里都还在。

---

### 3.7 ★ 与僵尸版**共用**同一套射击判定逻辑（2026-09-22）

僵尸版《超级机枪读报僵尸》的需求之一是「**植物僵尸共用**的射击判定逻辑」。
本植物版因此与它共享同一份判定源码 —— 详见《僵尸Mod-超级机枪读报僵尸》**§7.6**（含取舍与守卫细节），
这里只记植物侧要点：

* **单一真源**：`runtime_shared/GatlingVolleyCore.cs`
  （`GatlingVolleyParams` 参数 + `GatlingVolleyJudge` 判定函数）。
  两个 csproj **各自** `<Compile Include="..\runtime_shared\GatlingVolleyCore.cs" Link="…" />`
  ⇒ 同一份源编译进两个 `ModAssembly.dll`。**不是**共享程序集
  （每个 `.pmod` 必须自带 `Runtime/ModAssembly.dll`，且两版 `runtimeEntryType` 不同）。
* **本包入口里的常量全是转发**：`private const double UltimateChance = GatlingVolleyParams.UltimateChance;`
  —— 仍是编译期常量，取值处零开销；**数值只在共用核心里出现一次**。
* **两版的节拍外壳故意不统一**：僵尸自建毫秒计时器；本植物版由引擎
  `FireComponent.OnFireReady` 触发。外壳不同，但「掷大招骰 / 散射角 / 大招排期 / 卡顿补偿」
  四类判定完全一样，所以只共享 `GatlingVolleyJudge`。
* **顺带收掉两处两版漂移**：单帧上限 `8 → 12`；卡顿阈值 `400 ms（StallGapMsec）→ 250 ms`。

**防漂移守卫（植物侧，共四处；合计 23 条）**：

| 位置 | 断言 |
|---|---|
| 生成器 `self_check()` **第 16 节** | 两问：入口必须转发 `GatlingVolleyParams.X`；共用核心里的字面量必须等于生成器侧期望值 |
| `.cache/check_plant_super_gatling.py` **K15 / K15b…K15h** | 同样两问（`ok=1` 表示转发在位，字面量相等）；8 组 × 2 问 = **16 条** |
| **K16** | 大招排期走 `GatlingVolleyJudge.BurstDueMsec`（共用核心里是 `(index + 1) × BurstIntervalMsec`，无浮点漂移）；**1 条** |
| **K18 / K19** | K18：两个 csproj **都**真的挂了同一份源（只挂一边 = 另版本质上还是各抄一份）；**2 条**。K19：本包入口**真的在调用**共用判定（`RollUltimate` / `ScatterAngleDeg` / `StallGap` / `ShiftTimeline`）；**4 条** |
| **合计** | **16 + 1 + 2 + 4 = 23 条**。脚本里只有 **6 个 `chk(` 调用点**（K15 的两条 + K16 + K18 + K19 各一，另有一条「共用核心文件缺失」兜底），条数是**循环展开**出来的 ⇒ 别按 `chk(` 出现次数数。准确值以脚本末尾 `共享判定核心断言(K15* / K16 / K18 / K19): … => 合计 23` 行为准 |

> 这类「断言源码里含某个字面量」的检查，会在「把字面量搬到别处」的重构里**假红**。
> 本次修的就是这个：K15/K16 原来直查 `PeasPerAttack = 7` 之类，改共用核心后一次红 7 条 ——
> **要改的是断言本身，不是绕过它**。

---

## 4. 贴图是复用的，没做新素材

需求第 4 条「暂时用游戏已有的机枪射手贴图」。做法是场景里**直接实例化原版贴图场景**
（`ext_resource` 指向 `res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tscn`，
节点上标 `[editable path=...]`），而**不是**把 tscn 复制进包里。
好处：以后你想换贴图，只要往包里放一份自己的 `GatlingPea.tscn` 或改这一处 `ext_resource` 路径即可，
别的文件都不用动。

结构（与原版 `TowerDefensePlantGatlingPea.tscn` 同构）：

```
SuperGatlingPea (TowerDefensePlant 实例 + TowerDefensePlantGatlingPea.cs)
├── ShadowSprite
└── SpriteGroup
    └── TransformPoint
        └── GatlingPea            ← 原版贴图场景实例，position = (0, -30)
            └── Head
                └── Marker2D      ← 发射点 (31.74, -17.82)，被 ComponentSet 的 firePosMarkerPaths 引用
```

> **精灵场景是另一回事**：`Sprite/SuperGatlingPea.tscn` 只用来注册
> `CHARCTAER_SPRITE["SuperGatlingPea"]`（卡片/图鉴预览），与上面这棵树无关。
> 它同样只做了一层"包一层原版贴图场景"，避免两层实例嵌套导致 `[editable]` 失效。

---

## 5. 路径硬约束（改包结构前必读）

`ModLoader` 对角色类 Mod 有 6 条硬规则，全部由 `.cache/check_modloader_gates.py` +
`.cache/check_plant_super_gatling.py` 的 A 组断言住：

| 规则 | 出处 | 我们怎么满足 |
|---|---|---|
| 场景路径**恰好 6 段**：`Resources/Characters/<Cat>/<Key>/Scene/<Key>.tscn`，且文件名 == 目录名 == `<Key>` | `ModLoader.TryInferCharacterScene` | `…/Plants/SuperGatlingPea/Scene/SuperGatlingPea.tscn` |
| **精灵**同样 6 段，但第 5 段是 `Sprite` | 同上（`folder="Sprite"`） | `…/Plants/SuperGatlingPea/Sprite/SuperGatlingPea.tscn` |
| `<Cat>` 必须在已知集合内 | `IsKnownCharacterCategory` | `Plants` ∈ {Plants, Zombies, Props, Vases, Mowers, Items, Graves, Craters} |
| `Resources/Characters/<Cat>/...`（≥5 段）下的文件算**角色包依赖**，不会触发 "unsupported package file" | `IsCharacterPackageDependency` | Config/ComponentSet/Packet 都放这个前缀下 |
| 包内 `.scn/.res` **禁用**；`.tscn/.tres` 不得内嵌脚本 | `PrepareSafeCharacterPackage` | 包里只有 `.tscn` + `.tres`，且 0 个 `.scn/.res` |
| **自引用必须相对**、**引脚本必须 `res://`** | `TryGetGodotResourcePath` / `SanitizeCharacterTextResource` | 见 §2.5 闸门 1 |

---

## 6. manifest 三个易错点

```json
"provides": {
    "Character":       ["SuperGatlingPea"],
    "CharacterSprite": ["SuperGatlingPea"],
    "Packet":          ["SuperGatlingPea"]
}
```

* **`Packet` 的键是文件名，不是角色名**。`InferRuntimeEntry` 从
  `Resources/Cards/<文件名>.tres` 取键 ⇒ 必须是 `SuperGatlingPea`（卡片就叫这个名）。
  写错 → 该资源被判 "resource is not unambiguously declared by manifest" → **卡片被静默丢弃**；
  更糟的是 `saveKey ≠ 注册键` 会直接让整包被拒（§2.5 闸门 3）。
* **`provides` 的每一项都必须真的注册得上**（`ValidateManifestRegistrations` 是 all-or-nothing）。
  多写一个不存在的键 = 整包失败。所以只写这三项。
* **`Character` 走 `provides` 而不是 `overrides`**：我们新增角色，不覆盖任何内置物。
  `provides` 与 `overrides` 出现同 (类别,键) → `ambiguous automatic runtime key`。

---

## 7. 验收

| 检查 | 结果 |
|---|---|
| 生成器内置自检（扇形端点/递增、`fireNumAtOnce`、场景 `fireInterval`/`fireNum=1`、Scene+Sprite 双 6 段、自引用相对且包内可解析、`cost/costRise/packetCooldown/type`、**`hitpoints` 且写在 `name` 之后**、**`coverCanDirectPlant` 内联 override 且不多写任何字段**、`saveKey==键`、`unlockCheckList` 空、manifest 键序与 provides/resources、**运行时四字段 + resources 规范序 + DLL 存在**、CSV 表头） | **全绿，exit 0** |
| `.cache/check_modloader_gates.py`（ModLoader 闸门复刻：注册/provides 对齐、跨资源一致性、相对解析、二进制依赖、zip 形态、res:// 存在性、`hitpoints` + `coverCanDirectPlant` 内联 override） | **ok=33 warn=1 FAIL=0** |
| `.cache/check_plant_super_gatling.py`（A 路径 13 + A10 10 + A11 7 + B 资源/manifest 40 + **B2 运行时程序集 8** + **B3 卡库/图鉴一致性 61** + C 玩法 20 + **C2x 卡片数值（含 C29x 文案 12×2）41** + **C4x 血量/可种植性 31** + C3x 精灵场景 20 + D 产物 52 + E 发射链 10 + 文件头 1，**合计 314 项**；各段条数见脚本末尾 `分节断言数:` 行） | **ok=314 warn=1 FAIL=0** |
| 唯一 WARN | `翻译仅编辑器可见`（已知限制 → 文案已改**内联**，见 §3.4）+ `Localization/translations.csv` 会被记为 unsupported（不致命） |
| `runtime_src_plant/check_gates_plant.cs`（**反射直调 ModLoader / XWModManifest / XWModManifestSyncService / XWModRuntimeCompatibility 的真函数**：`InferRuntimeEntry` 9 条路径、`XWModManifest.Load` 四字段、`ValidateDeclaredPackageExecutables` 正向 + 负向对照、`ValidatePackage`、`SyncProject` 幂等；**第 6 组**另核插件依赖的运行时接缝：`Almanac._plantInitialized`（private）/`plantPacketBank`/**`plantCategoryId`（2026-09-25 新增：删分类后回落用）**/`InitPlant()`/`TOWERDEFENSE_PACKETBANKS`/`GetPlantList`/`WithPlants`；**第 7 组 14 项**核 §2.6 新增数值的落地接缝：`TowerDefenseCharacterConfig.hitpoints`(double)/`hitpointsNearDeath`/`plantCover`、`TowerDefenseCharacterInstance.hitpoints{,Base,NearDeath}`、`TowerDefensePacketConfig._override`(类型 `TowerDefensePacketOverride`)/`GetCoverCanDirectPlant()`/`GetPlantCover()`、`TowerDefensePacketOverride.coverCanDirectPlant`(bool)/`plantCover`/`characterOverride`、`TowerDefenseCellInstance.CanPacketPlant`） | **53 PASS / 0 FAIL**（重制版 + 发布版两份游戏程序集都跑过） |
| `runtime_src/check_entry.cs`（入口发现：类型唯一命中、public、公开无参构造、三方法齐全、`Activator.CreateInstance`） | **11 PASS / 0 FAIL** |
| `build_runtime.py --check`（同一份源码编译两次 + 与发布版程序集编译对比） | **两次字节一致**；DLL **22 016 B**，sha256 `9298e407b9b599df`（2026-09-25 图鉴去重改版后复跑确认），**两份游戏构建产出的 DLL 逐字节相同**（`--godot-ref-dir` 指向发布版时提示「未变」） |
| `.cache/check_idempotent_plant.py`（连跑 3 次比 **14** 个产物 sha1 + 残留旧产物检查） | **全部字节稳定**，无残留 |
| pmod 包结构 | **12 条目**（`mod.json` + `Localization/translations.csv` + **3 个外观文件**（`.dat` / `.tres` / 图集 `.png`）+ 6 个数据资源 + `Runtime/ModAssembly.dll`），`mod.json` 在第 0 位，全部固定时间戳 `2026-01-01 00:00:00`，无 `.cs/.uid/.import/.pvzmodeproject/隐藏文件` |
| `python verify_pmod.py dist/超级机枪射手.pmod` | **ok=12 warn=9 FAIL=0**（warn 是离线复刻不认识角色包依赖/声明的程序集，已在 `check_gates_plant.cs` 用真函数消掉） |
| 安装副本 | `Mods/超级机枪射手.pmod`（**178 046 B**，sha256 `332e561932eab22a`）与 `dist/` 字节一致；`Mods/超级机枪射手/Runtime/ModAssembly.dll`（**22 016 B**，sha256 `9298e407…`）也与工作区一致 |
| **图鉴文案内联**（2026-09-25） | 卡片 `name/describe/handbookDescribe/handbookStory` 全部是**内联字面量**（不再有 `TOWERDEFENSE_*` 键）⇒ 游戏内显示的就是中文原文（§3.4 / §9.3）。生成器自检 **13h**（内存+磁盘双查）+ 门禁 **C29x（12 条 × 2 份卡片）**盯着它，`_neg_test_almanac_text.py` 有 5 条负向用例 |
| **图鉴去重**（2026-09-25） | 插件把本卡从 `ModPlants` 独立分类里摘掉（摘空了删键），只保留金卡那一张（§3.5.1）。生成器自检 **18 节**（7 条活语句断言）+ 门禁 **K20a–K20g** 盯着它，另有 4 条负向用例（含「注释掉」「`false &&` 死分支」两种反模式） |
| **血量 / 可直接种植**（2026-09-19） | `config.hitpoints = 1000.0`；卡片内联 `PacketOverride_direct_plant`（只开 `coverCanDirectPlant = true`）⇒ 空地可直接种，且**保留**双发射手升级路（§2.6）。新增 31 + 5 + 14 条断言盯着它，含一条**反向对照**（C50c） |
| **共用判定核心**（2026-09-22） | 判定参数与判定函数在 `runtime_shared/GatlingVolleyCore.cs`，与僵尸版《超级机枪读报僵尸》**共用同一份源**；本包入口只留 `= GatlingVolleyParams.X;` 转发（§3.7；**2026-09-24 起植物侧不再转发 `PeasPerAttack`/`PeaSpacingSeconds`**，见 §9.1）。生成器第 16 节 + `check_plant_super_gatling.py` K15 系列 / K16 / K18 / K19 盯着它 | **全绿**（`ok=314 FAIL=0`；DLL 内已含 `GatlingVolleyJudge` 符号） |
| **可选性（选卡界面）** | 插件把本卡补进**共享卡库** `GeneralPlant.Gold`（+ 派生库 `Total`）⇒ `packetBankType` 默认就是 `GeneralPlant`，所以选卡界面里能选到；**图鉴同源**（图鉴就是从这个库拷的）⇒ 两边数据一致（§3.2.2 / §3.5） |
| 副作用（如实记录） | 成为正常金卡后，按卡库取卡的随机/奖励逻辑（金色碎片、陨石坑补卡、植物礼盒、幸运四叶草、方块盒…）都可能给出这张卡 —— 清单见 §3.6 |
| **游戏内实际加载**（读 `logs/godot.log`） | 加插件**之前**实测：`package applied: supergatlingpea; resources=3; diagnostics=1` + `3/3 packages; rollbackBlocked=False`。**加插件后需你进游戏再确认一次**（见 §8） |
| 工程目录 | `Mods/超级机枪射手/` **72 个标准子目录**（= `XWModProjectLayout.StandardDirectories`，逐项同序）+ `mod.json` + `Runtime/ModAssembly.dll` + 唯一同名 `.pvzmodeproject`（纯 CRLF、无 BOM、8 键序正确、`ExportDirectory` 与编辑器真品逐字一致） |
| 启用开关 | `enabled_mods.json = ["discogargantuarpult","PeaOverhaul","supergatlingpaper","supergatlingpea","vampirepool"]`（大小写不敏感有序，未误删既有 id） |
| 最近工程 | `mod_editor_recent_projects.cfg` 里 **本工程 + 地图工程两条都在**（正斜杠、本工程在前；见 §11） |
| 生成器耗时 | 首次 ~0.9 s、之后 ~0.7 s（改为增量写 + 增量清理前是 75 s，见 §10） |

---

## 8. 进游戏测试

1. 确认 `Mods/` 下有三样东西：

   ```
   C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods\
       超级机枪射手.pmod          ← 必须有（游戏只加载 *.pmod）
       enabled_mods.json          ← 里面要有 "supergatlingpea"
       超级机枪射手\              ← 想继续在编辑器里改才需要
   ```

2. 游戏内 `F3` → **Mod 工具** → **重新扫描**，确认列表里「**超级机枪射手**」是**启用**状态，
   然后点 **重新应用**（联机战斗期间会被拒绝）。
   > `enabled_mods.json` 只是启用清单；真正的加载动作由 Mod 工具面板发起
   > （`XWModManager.LoadEnabledModsWithResult()`），面板 `_Ready` 不会自动加载。

3. **验「能选到」**（这是本轮新修的）：进一关（或直接看**选卡界面**），点**金卡**分类，
   `超级机枪射手`（花费 600 / 冷却 30s）应当**和内置金卡排在一起、可以直接拖/点选**。
   最硬的证据在日志里：`[SuperGatlingPea] 已把「SuperGatlingPea」补进卡库「GeneralPlant」的
   「Gold」分类 ⇒ 选卡界面里可以选到它了。`
   * 这一步不依赖「图鉴有没有打开」—— 补卡库是按每 10 帧的扫描走的，和场景树无关；
   * 想立刻验证单卡玩法，也可以**关卡编辑器 → 直接往地图上放这个角色**（`Character` 已 provide）。
   > 若在选卡界面看不到它：先确认这关的卡库不是被关卡单独指定成了别的库
   > （`TowerDefenseLevelConfig.packetBank` / `PacketBankName`；默认是 `GeneralPlant`）。
4. 「额外新增」的卡还有一条兜底：按成本取卡的场合（如 `GetPacketConfigCostLower(cost, GOLD)`）
   会扫 `TOWERDEFENSE_PACKETS` 带上它。
5. **验玩法**：种下去，僵尸进入射程后应当每 **1.5 秒**打出**扇形 7 颗**豌豆（±15°），
   朝左朝右自动镜像。
6. **验大招**：让它连续打一会儿（10% 概率 ⇒ 平均约 10 次攻击 / 15 秒出一次）。
   触发时会看到**豌豆成串倾泻 5 秒**，节奏比常规射速快得多。
   最硬的证据在日志里（`logs/godot.log`），关键三行：
   * 加载时：`[ModLoader] package applied: supergatlingpea; resources=7; runtimeEntry=True; …`
     （`resources=7` + `runtimeEntry=True` ⇒ 数据资源 + 插件入口都成功）
   * 挂钩时：`[SuperGatlingPea] 已挂上第 1 个「SuperGatlingPea」发射组件。`
   * 触发时：`[SuperGatlingPea] 触发大招（第 N 次）：5s 内连射 43 轮 ≈ 301 颗豌豆，节拍 116.3ms/轮。`
     结束还有一行 `大招结束：共连射 43 轮 = 301 颗豌豆`。
   > 若只有 `resources=7` 但没有挂钩日志 ⇒ 插件加载成功但没找到植物（多半是 `config.name` 或
   > 场景没生效）；若连 `runtimeEntry=True` 都没有 ⇒ 插件没加载，看 `diagnostics` 数字和
   > `[ModLoader]` 的 warning（会明说是 "运行入口初始化失败" 还是
   > "invalid declared runtime assembly path"）。
7. **验图鉴分类**：打开**图鉴** → 植物页
   * ★ 翻分类时**不应再看到「ModPlants」这一页**（它只含本卡 ⇒ 按用户 2026-09-25 口径整个删掉了）；
   * 翻到**金卡**分类，本卡应当和内置金卡**排在一起**（原来它自己占一个「ModPlants」分类，见 §3.5）。
   正常时序下第 3 步已经补好共享卡库，图鉴拷贝里本来就有它 —— **不会**额外打兜底日志。
   若打了 `兜底：已把…并进图鉴那份拷贝…`，说明「图鉴先开着、之后才补上卡库」，
   兜底生效（`N` 递增是正常的，图鉴每次打开都是新拷贝）。
   > ✅ 本卡**只会出现一次**（金卡分类第 20 张）。若还在 `ModPlants` 里看到它，
   > 说明插件没生效 —— 看日志里有没有 `图鉴去重：本卡是该分类里唯一的植物 ⇒ 已删除「ModPlants」分类本身`。
   > ⚠️ 若**别人**的 Mod 植物也在 `ModPlants` 里，那个分类会**保留**（只摘本卡），
   > 日志会是 `图鉴去重：已把「SuperGatlingPea」从「ModPlants」分类里摘掉（该分类还剩 N 个其它 Mod 植物…）`。
   * ★ **验文案**：点开本卡，信息面板应当逐字等于截图内容（`大哥登场！` / 韧性 1000 /
     **威力：20×7 /1.5秒** / 范围 前方一行 / 特点 / 大招 / 故事段 / 花费 600 / 冷却速度 30.0 秒）。
     若看到 `TOWERDEFENSE_PLANT_SUPERGATLINGPEA_NAME` 之类的东西 ⇒ 装的是旧包（文案还没内联）。
8. **验数值**：卡片显示 600 阳光；同关再种第 2、3 张时价格应递增 100；种完等 30 秒才转好。
9. **验「不用种在双发射手上」**（§2.6）：把卡片**直接种在一块没有植物的空地上**——应当一次成功。
   再测一次**升级路**：先在空地上种一张**双发射手**，再把本卡放上去 —— 也应当成功（会替换掉它）。
   > 若**空地种不上**（卡片拖过去格子变红 / 点了没反应）：
   > ① 确认游戏里加载的是**新的** `超级机枪射手.pmod`（sha1 `9fcdabfe…`，13296 B），
   >    旧包（13256/13159 B）没有这个 override；
   > ② 打开工程看 `Resources/Characters/Plants/SuperGatlingPea/Packet/SuperGatlingPea.tres`
   >    里是否有 `override = SubResource("PacketOverride_direct_plant")` ——
   >    若用**编辑器手改过**这张卡，编辑器可能把 override 写没了，重跑生成器覆盖即可；
   > ③ 若只有**某一关**种不上：那关给本卡设了 packetOverride，会顶掉这个开关（§2.6 边界）。
10. **验血量 1000**：种下后让僵尸啃/让橄榄球撞，肉眼对比 —— 它应当明显比同场 300 血植物耐打
    （约 3.3 倍）。想精确验证：开 `F3` 调试或直接看后面跟的伤害跳字/血条消耗速度。
    > 血量来自 Config，**不需要插件**；改 `HITPOINTS` 后重跑生成器即可（§9.3）。
11. 想继续手改：`F3` → **Mod 工具** → 工程管理 → **打开工程**，
   选 `Mods\超级机枪射手\超级机枪射手.pvzmodeproject`（生成器已登记进「最近工程」）。
   改完「导出」落回 `Mods\超级机枪射手.pmod`，再「重新应用」。
   > ⚠️ 编辑器**导出会把 `Runtime/ModAssembly.dll` 一起带出去**（它就是包内普通文件），
   > 所以手改数据后不必重跑 `build_runtime.py`；只有改了 `runtime_src_plant/*.cs` 才需要。

### 8.1 插件没生效时的排查顺序

| 现象 | 先看哪里 | 结论 |
|---|---|---|
| 游戏里**根本没这个植物**了 | `logs/godot.log` 的 `[ModLoader]` 行 | 整包被拒（不是插件问题）。注意：入口抛异常会导致**无条件整包回滚**（§3.3） |
| 植物在，但**没有大招**、日志也无 `[SuperGatlingPea]` | 有没有 `package applied: … supergatlingpea` | 没有 ⇒ 没点「重新应用」或没勾启用 |
| 有 `运行入口已初始化` 但**没有挂钩日志** | 是否真的在战斗里种下了它 | 挂钩只在战斗内扫到角色时才发生；菜单/编辑器里不会 |
| 挂钩了但大招**极少出现** | 攻击次数的量级 | 10% 是概率，10 次里大约 1 次；想快速验证就把 `UltimateChance` 临时调成 `1.0` 重编译 |
| 大招期间**卡顿** | `MaxVolleysPerFrame`（默认 6） | 掉帧时一帧最多补 6 轮，若仍卡就调小 |
| **联机**时大招行为不同步 | 见 §3.2 已知代价 | 单机真随机做不到联机一致，当前是刻意取舍 |
| **选卡界面里选不到本卡** | 有没有 `补进卡库「GeneralPlant」的「Gold」分类` 这一行 | 有 ⇒ 该关卡的卡库被单独指定成了别的库（`TowerDefenseLevelConfig.packetBank`）；没有 ⇒ 见下行 |
| 有 `补共享卡库「Gold」分类失败` 警告 | 警告后面的异常消息 | 该版本 `TOWERDEFENSE_PACKETBANKS`/分类名变了；**只影响可选性**，大招与植物本身照常 |
| 图鉴里本卡**还是孤零零一个分类** | 有没有 `并进图鉴那份拷贝` / `补进卡库` 任一行 | 有 ⇒ 图鉴没刷新（关掉重开图鉴）；都没有 ⇒ 见下行 |
| 有 `补图鉴「金卡」分类失败` 警告 | 警告后面的异常消息 | 该版本 `plantPacketBank`/分类名变了；**只影响图鉴兜底**，共享卡库那条仍是好的 |
| **空地种不上**（只能放双发射手上） | 卡片里有没有 `override = SubResource("PacketOverride_direct_plant")` | 没有 ⇒ 用的是旧包/被编辑器改没了，重跑生成器（§2.6）。**注意：这条不产生任何日志**（纯数据，不经过插件） |
| 只有**某一关**种不上 | 该关有没有给本卡设 packetOverride | 有 ⇒ 关卡那份 override 顶掉了开关；要么改关卡，要么把 `plantCover` 置空（§2.6） |
| 血量不是 1000 | Config 里有没有 `hitpoints = 1000.0` | 没有 ⇒ 旧包；有 ⇒ 该关/该 pattern 另有 override 改血量 |

> 生成器每次运行都会自动做完第 1 步的三件事（镜像工程目录、合并启用清单、登记最近工程），
> 且是**增量**的：只写变化的文件、只删「这次不再产出」的旧文件（正常重跑什么也不动）。
> 所有写操作都是**幂等**的：连跑 3 次产物 sha1 不变，耗时约 0.7 s。

---

## 9. 想改数值？只动一个地方

`build_plant_super_gatling.py` 顶部常量区（**数据侧**，改完只需重跑生成器）：

```python
FIRE_INTERVAL   = 1.5    # 每 1.5 秒一轮（只写进 .tres 的文档值 fireInterval；真正节拍在引擎 FireComponent）
VOLLEY_COUNT    = 7      # ★ 一次齐射的颗数（= fireProjectileList 条数 = Marker 数；必须 == PEAS_PER_ATTACK）
VOLLEY_SPACING  = 32.0   # 相邻两颗的间距（px，**沿弹道方向**排成一条水平直线）：豌豆 28×28 ⇒ 32 保证不重叠
VOLLEY_FORWARD_SIGN = 1.0  # ★ 散布方向：只沿弹道方向（本地 +x = 屏幕右 = 弹道正前方）
ULTIMATE_SPREAD_DEG = 15.0   # 大招散射半角 ±15°（只在插件用，不落数据）
ULTIMATE_PEAS       = 300    # 大招总颗数
ULTIMATE_SECONDS    = 5.0    # 大招持续秒数
PEA_SPEED       = 500.0  # 弹速
PROJECTILE_NAME = "Pea"
COST            = 600    # 阳光花费（config.cost）
COST_RISE       = 100    # 种植涨价（config.costRise）
PACKET_COOLDOWN = 30.0   # 冷却秒（config.packetCooldown）
PACKET_TYPE     = 1      # 卡类型：1=GOLD 金卡；0=WHITE 3=DIAMOND 4=COLOUR 5=STAR 6=ORIGINAL 8=GRAY
HITPOINTS       = 1000.0 # 血量（config.hitpoints；类默认 300.0）
COVER_CAN_DIRECT_PLANT = True  # 覆盖卡也能直接种在地上（内联 packet override，见 §2.6）
```

`PACKET_TYPE` 取值见 `TowerDefenseEnum.PACKET_TYPE`（注意它是 **0 起**、`NOONE = -1`）：
`WHITE=0, GOLD=1, DIAMOND=2, COLOUR=3, STAR=4, ORIGINAL=5, ZOMBIE=6, COVER=7, GRAY=8`。

> ⚠️ **2026-09-24 齐射改版**：常规攻击现在是**数据侧齐射** —— `fireProjectileList` 7 条配置
> （speed=500 / dir=0 / `firePosId` 0..6 各一次）+ `firePosMarkerPaths` 7 条 Marker + `lockProjectileGridY = true`，
> 动画 `fire` 事件一次 `Fire()` 就把 7 颗**同帧全部打出**（`FireComponent.Fire()` 一次遍历全部配置，
> `FireComponent.cs:3434`）。
>
> ★ **排列形态（口径修正，2026-09-24 二次）**：7 个 Marker **只沿弹道方向（x）铺开**，
> 位置 = `MARKER2D_POS + (dx, 0)`，`dx = 0/32/64/96/128/160/192` ⇒ 屏幕上 **y 全同、水平一条直线 = 「一排」**。
> ⚠️ 旧口径是沿 **y** 铺（`0/±32/±64/±96`）= 屏幕上**竖直一列**，用户明确否掉（「要一排，不是一列」）。
> 方向由 `VOLLEY_FORWARD_SIGN` 控制，**只向前（+x）**：链路无镜像（Sprite root `offset=(-40,-40)` /
> Head `offset=(-37.05,-47)` / 无 scale 覆写）+ `dir=0 ⇒ velocity = speed·(1,0)`（`FireComponent.cs:3462`）
> ⇒ +x 恒为屏幕右 = 弹道正前方；往后铺的 3 颗会落进植物身体/背后。
> 两个形态不变量已写成断言（`self_check` 13c-4 / 13f-4、门禁 C19c/C19d/C19f）：
> **y 唯一**（否则是一列）· **x 严格递增且步距恒 32**（否则重叠/回头）· **首颗 x = 炮口 x**。
> **插件只管大招**，常规齐射不经过插件。详见 §13。

### 9.1 大招参数（改完**必须重编译插件** —— **两个工程都要**）

⚠️ **2026-09-22 起，这些数值的唯一真源是 `runtime_shared/GatlingVolleyCore.cs`**
（`GatlingVolleyParams`），僵尸版《超级机枪读报僵尸》共用同一份（§3.7）。
本包入口里只剩**转发**（仍是编译期常量）。

> ⚠️ **2026-09-24 齐射改版后**：`PeasPerAttack` / `PeaSpacingSeconds` **不再被植物入口转发**
> （那是僵尸连发链参数；植物常规攻击已是数据侧齐射，不消费它们）。其余照旧转发：

```csharp
// runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs
private const double UltimateChance      = GatlingVolleyParams.UltimateChance;       // 0.10
private const double UltimateSeconds     = GatlingVolleyParams.UltimateSeconds;      // 5.0
private const int    UltimatePeas        = GatlingVolleyParams.UltimatePeas;         // 300
private const double ScatterHalfAngleDeg = GatlingVolleyParams.ScatterHalfAngleDeg;  // 15.0
private const int    MaxPeasPerFrame     = GatlingVolleyParams.MaxPeasPerFrame;      // 12
private const ulong  StallGapMsec        = GatlingVolleyParams.StallThresholdMsec;   // 250
private const float  FallbackPeaSpeed    = 500f;  // 大招弹速兜底（正常路径实时读 fireProjectileList[0].speed）
```

生成器里另外记着一份**期望值**供自检比对（改共用核心时同步它，否则自检第 16 节拒绝写盘）：

```python
PEAS_PER_ATTACK      = 7     # 与 VOLLEY_COUNT 的不变式（自检第 0 节：必须相等）
ULTIMATE_CHANCE      = 0.10  # 大招概率
MAX_PEAS_PER_FRAME   = 12    # 单帧上限
STALL_THRESHOLD_MSEC = 250   # 卡顿阈值
```

改完按这个顺序跑：

```
python runtime_src_plant/build_runtime.py --check       # 编译 + 两次字节比对
python runtime_src_zombie_super_gatling/build_runtime.py --check   # ★ 僵尸那份也要重编译
python build_plant_super_gatling.py                     # 重打包（搬运新 DLL + 镜像到 Mods/）
python build_zombie_super_gatling_paper.py              # ★ 僵尸包也要重打
python .cache/run_gates_plant.py && python .cache/run_gates_sgp.py
python .cache/check_plant_super_gatling.py
```

### 9.2 卡库 / 图鉴归类 + 图鉴文案（改完必须重编译插件）
```csharp
GoldCategory         = "Gold";         // 要并进哪个分类（图鉴与选卡界面都用这个键名）
ModPlantCategory     = "ModPlants";    // ★ 2026-09-25：图鉴里「只有 Mod 植物」的独立分类，
                                       //   本卡要从它里面摘掉（摘空了就删键）—— 见 §3.5.1
RootPlantBankKey     = "GeneralPlant"; // 根卡库：选卡界面 packetBankType 的默认值
PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";
                                       // 运行期按 Include 闭包算派生库（实测只有 Total）
FallbackDerivedBankKeys = { "GeneralPlant", "Total" };  // json 读不到时的兜底
```

> ⚠️ 改这几个常量后：`FallbackDerivedBankKeys` 若与实算结果不一致，
> `.cache/check_plant_super_gatling.py` 的 **K2** 会红（它按真 json 重算 Include 闭包）；
> 图鉴去重那几条写在 **K20x**（要求是**活语句**，注释掉/改成 `false &&` 死分支都会红）。
> 想要「只在图鉴里能看到、不进任何卡池」，把 `ScanScene()` 里的 `TryPatchCardBanks();` 删掉即可。

### 9.3 图鉴文案（改完**只需重跑生成器**，不用重编译插件）

文案在 `build_plant_super_gatling.py` 顶部的常量区，**直接内联进卡片**（§3.4）：

```python
PLANT_CN_NAME = "超级机枪射手"                    # → 卡片 name（图鉴标题）
PLANT_CN_DESC = "大哥登场！"                       # → describe（面板自动包 [color=2f375e] 深藏青）
PLANT_CN_HANDBOOK_DESC = (                       # → handbookDescribe（多行块，**真实换行**）
    "韧性：[color=cc241d]1000[/color]\n"
    "威力：[color=cc241d]20×7 /1.5秒[/color]\n"   # ★ 用户 2026-09-25 指定（截图原为 20×7 /2s）
    "范围：[color=cc241d]前方一行[/color]\n"
    "特点：[color=cc241d]每次攻击有10%概率释放大招[/color]\n"
    "大招：[color=cc241d]小范围散射约300枚子弹[/color]"
)
PLANT_CN_STORY = "超级机枪射手完美诠释了“火力优势学说”，…很害怕史莱姆。"   # → handbookStory
```

**写作口径**（照抄官方 `Prefab/GUI/InformationPanel/InformationPanel.tscn` 自带的范例模板 +
`InformationPanel.cs:228-234` 的渲染方式）：

| 面板控件 | 来源字段 | 面板怎么渲染 |
|---|---|---|
| `NameLabel` | `name` | 原样 |
| `ExpressionLabel` | `describe` | **自动**包 `[color=2f375e]…[/color]` ⇒ 自己**别再加**颜色标签（会嵌套） |
| `HandbookExpressionLabel` | `handbookDescribe` | 裸 BBCode 直渲：**头词写裸文本**（吃面板 `default_color` `#8F431B` 棕）＋ **数值包 `[color=cc241d]`**（`#CC241D` 红） |
| `HandbookStoryLabel` | `handbookStory` | 裸 BBCode 直渲 |
| `InformationCostLabel` / `InformationColdDownLabel` | —— | 面板自己拼（`花费：600` / `冷却速度：30.0 秒`），**不要**写进上面四个字段 |

> ⚠️ 三条硬规矩（生成器自检 **13h** 会逐条核对磁盘产物，`_neg_test_almanac_text.py` 有 5 条负向用例）：
> ① `.tres` 多行字符串用**真实换行**，**不要**写 `\n` 转义（会原样显示成反斜杠 n）；
> ② 不许出现 `TOWERDEFENSE_PLANT_SUPERGATLINGPEA*` 旧键（游戏内会原样显示 key，§3.4）；
> ③ `describe` 不许自带 `[color=…]`。

> ⚠️ 改共用核心的 `PeasPerAttack`（或生成器的 `PEAS_PER_ATTACK`）**两边必须同步**，
> 且植物侧 `VOLLEY_COUNT` 必须跟着改（自检第 0 节不变式 `VOLLEY_COUNT == PEAS_PER_ATTACK`，
> 违反时 `--check` 模式退出码 3；重建模式直接拒绝写盘）—— 这是刻意设计的护栏，别绕过。
> 注意齐射改版后 `PeasPerAttack` 只剩「僵尸连发链 + 植物侧颗数不变式」两个消费者，
> 植物入口不再转发它；改完重编译：`python runtime_src_plant/build_runtime.py --check`（僵尸版也要），然后重跑生成器打包。

### 9.3 血量 / 可种植性（改完**只需重跑生成器**，不用重编译插件）

都在生成器顶部常量区：

```python
HITPOINTS              = 1000.0   # 血量 → Config 的 hitpoints
COVER_CAN_DIRECT_PLANT = True     # True = 空地可直接种（内联 packet override）
```

* `HITPOINTS` 直接写进 `<Key>/Config/TowerDefensePlant<Key>.tres`；
  改成别的值后 `.cache/check_plant_super_gatling.py` 的 **C40 / C41** 会红（它们钉死 1000.0）。
* `COVER_CAN_DIRECT_PLANT = False` 时：生成器改为回写 `override = null`（自检里的 `else` 分支），
  卡片立刻退回「**只能**种在双发射手上」。
* 想**彻底不受关卡 override 影响**（代价：失去双发射手升级路）：把生成器里
  `plantCover = ["PlantPeaShooter"]` 改成 `plantCover = []`。两种做法对比见 §2.6「副作用 / 边界」。
* 改 `HITPOINTS` 之后会重新生成 `.tres` ⇒ pmod 哈希变，但 **DLL 不用动**（`ModAssembly.dll` 与血量和种植无关）。

五类失败日志**各有一个「只报一次」标志**（`_tickFaultReported` / `_almanacFaultReported` /
`_bankFaultReported` / `_hookFaultReported` / `_volleyFaultReported`），互不干扰 ——
这样「补卡库失败」或「图鉴归类失败」**不会**把「大招推进失败」的日志吃掉
（共用一个标志时就是这样，排查时只能看到一个不相干的警告）。

---

## 10. ⚠️ 构建器的环境坑：不要用 `shutil.rmtree`，也不要「整目录删掉重建」

这一节是 2026-09-16 踩出来并修掉的，**换环境/换机器时容易复发**。

### 现象

生成器跑完自检后突然 `exit 1`，栈里是：

```
File "...\ModWorkspace\build_plant_super_gatling.py", line 567, in install_project_dir
    shutil.rmtree(dst)
  File "...\vendor\shim\sitecustomize.py", line 1144, in _safe_shutil_rmtree
    _try_trash(abs_path, recursive=True)
  File "...\vendor\shim\sitecustomize.py", line 146, in _platform_trash
    raise OSError("SHFileOperationW 失败: 0x%x" % result)
OSError: SHFileOperationW 失败: 0x2
```

### 根因（两层，都会咬人）

1. **`shutil.rmtree` 被运行环境劫持**成 `_safe_shutil_rmtree` → 先尝试「丢进回收站」；
   回收站调用失败（`SHFileOperationW 0x2`）就 **fail-closed 直接抛异常**。
   → 生成器中断在镜像那一步，`.pmod` 已经复制过去了、`enabled_mods.json` 还没合并。
2. 换成手写「逐文件 `os.remove` + 自底向上 `os.rmdir`」后异常没了，但**单次删除约 0.6 s**
   —— 实测 `safe_rmtree(MOD_ROOT)` **47.9 s**、`safe_rmtree(镜像)` **43.9 s**，
   一次构建 **75 s**；3 连跑的幂等校验（约 225 s）直接被工具超时杀掉（SIGTERM，输出为空）。

### 修法（现在的写法）

| 旧写法 | 新写法 | 收益 |
|---|---|---|
| `shutil.rmtree(MOD_ROOT)` + 全量重写 | **不删目录**：就地写 + `sweep_stale_files(MOD_ROOT, keep)` 只删「这次不再产出」的文件 | 正常重跑 0 删除 |
| `rmtree(镜像) + shutil.copytree` | `sync_tree(src, dst, marker)`：**按字节比对**只写变化的文件；再删 `src` 里没有的文件与空目录 | 第二次起 写 0 / 删 0 |
| 用隐藏文件 `.generated` 当镜像标记 | 用**工程文件** `<工程名>.pvzmodeproject` 当标记（它本身会被同步进镜像 → **自愈**，不会出现「标记丢了就永久跳过」） | 与地图构建器一致 |
| —— | 新增 `mirror_is_ours()` 护栏：不存在 / 带标记 / **零文件的空壳** → 归我们；**其它一律跳过不动** | 不误删用户目录 |

结果：**75 s → 0.7 s**（约 100×），`safe_rmtree()` 保留但主流程不再调用（只留给人工整目录重置）。

### 顺带修掉的一个真错：`STANDARD_DIRS` 是臆造的

原 `STANDARD_DIRS` 有 **120 项**，其中 `Resources/ChessMaps2`、`Resources/VampireMaps`、
`Resources/Collectables2`、`Resources/HitBoxes` 等在游戏里**根本不存在**，
同时**漏掉**官方 72 项里的 `Resources/MapCells`、`Resources/GameplayLogic`、
`Resources/StateMachines`、`Resources/CharacterCombat`、`Resources/CharacterData/*` … 共 **39 项**。

现在两边构建器都**逐字照抄** `XWModProjectLayout.StandardDirectories`（72 项、同序），
并加断言 `D25/D26/D27/D28`：直接读 `XWModProjectLayout.cs` 解析出官方清单，
与生成器、与地图构建器三方比对 —— 以后再漂移会当场 FAIL。

> 顺带确认：`Config/` 下的配置文件**文件名不受约束**（`XWModContentValidation` 只校验
> 注册键/`saveKey`/`characterConfig.name`，不校验 `Config/<Key>Config.tres` 这种命名；
> 那个命名只出现在编辑器「受保护文件」判定 `IsProtectedCharacterPackageBaseFile` 里）。
> 所以本包的 `TowerDefensePlantSuperGatlingPea.tres` 不影响加载。

---

## 11. 编辑器侧三件套：工程文件 / 最近工程 / 导出目录格式

`.pmod` 只负责「游戏能加载」；要在**游戏内编辑器**（`F3` → Mod 工具 → 工程管理）里能直接
打开这份工程，还差三样东西。2026-09-18 逐条对着**编辑器亲手建的工程**（`Mods/新地图-1/`）校准过：

### ① `.pvzmodeproject` 的 `ExportDirectory` 必须是「正斜杠 + 结尾斜杠」

| | `ExportDirectory` |
|---|---|
| 编辑器真品（`新地图-1`） | `"C:/Users/…/植物大战僵尸杂交版/Mods/"` |
| 地图构建器（一直是对的） | `USER_MODS_DIR.replace("\\","/") + "/"` |
| ❌ 植物构建器（本轮修） | `"C:\\Users\\…\\Mods"` ← 反斜杠、且无结尾斜杠 |

依据：`ModProject.cs:79` 默认值就是 `ProjectSettings.GlobalizePath("user://Mods/")`。
导出时走的是 `ModExporter.ExportFromDirectory` → `Path.Combine(outputDir, GetPackageFileName(...))`，
`Path.Combine`/`Path.GetFullPath` 会容错，所以**缺结尾斜杠不会真的写错位置**（这点要说清楚，
不是致命 bug）——但和编辑器/另一支构建器写法不一致，属于该对齐的格式问题。

### ② 「最近工程」缓存：**绝不能把别人的条目清掉**（这个是真 bug）

`user://mod_editor_recent_projects.cfg` 是编辑器「最近工程」列表。植物构建器原本登记的是
**工作区路径**（`D:\…\ModWorkspace\SuperGatlingPea\…`），而编辑器只从 `Mods/` 下打开工程 → 登记了也没用。

更糟的是**两支构建器会互相清空**：旧写法用 `^path_\d+="(.*)"$` 匹配行尾，而这个文件是 **CRLF**，
行尾是 `\r\n` → **一条都匹配不到** → 于是把整个列表重写成「只剩自己一条」。
实测：跑一次 `build_map_vampire_pool.py`，植物那条就被抹掉了（`count` 从 2 掉回 1）。

现在两边都是：先把 CRLF 归一化成 LF 再解析 → 统一正斜杠 + 大小写不敏感去重 → **保留所有既有条目**，
新条目插到最前；植物构建器登记的是 `Mods/超级机枪射手/超级机枪射手.pvzmodeproject`。

回归断言 `D33/D34/D35`：本工程在列表里、地图那条没被清掉、列表里没有残留工作区路径。

### ③ 工程目录骨架 = 官方 72 项

见 §10 末（`STANDARD_DIRS` 曾是臆造的 120 项）。

> 一句话记法：**`.pmod` 给游戏；`.pvzmodeproject` + 72 目录 + 最近工程给编辑器。**
> 前者错了游戏不认，后者错了只是编辑器里不方便/打不开，两者别混为一谈。

---

## 12. ★ 2026-09-24：头位对齐豌豆射手 + 射击后抽搐修复

两项实机反馈，均已落地（生成器 `build_plant_super_gatling.py` + 门禁同步更新）。

### 12.1 头部位置对齐普通豌豆射手

**根因**：引擎每帧用「被跟随图层 pose.Origin + 父 offset」覆写 `Head.position`
（`AdobeAnimateSprite.cs:5259-5267`），2026-09-21 写的 `(0,-8)` 抬头**从未生效**；
而 `Head.offset=(-40,-40)` 隐含「跟随层 pose=(40,40)」的错误假设 —— 实测
`anim_idle@f0=(37.6,48.7)` ⇒ 头比豌豆射手**偏左 2.95px、偏低 7.00px**。

**修法**（以内置 PeaShooter 为基准逐帧反解，f0..24 全周期 Δ 是刚性平移，波动 ≤0.27px）：

| 常量 | 旧 | 新 | 说明 |
|---|---|---|---|
| `HEAD_OFFSET`（Sprite 场景 Head） | `(-40, -40)` | **`(-37.05, -47.00)`** | `= 旧值 + Δ(f0)`；Δ = P_pea − P_sg @ 相对相位 0 |
| `Head.position` | `(0, -8)`（死值） | **`(0, 0)`** | 清理死值，防误导 |
| `MARKER2D_POS`（角色场景） | `(48.552, -9.8)` | **`(51.502, -16.8)`** | 恒等式 `marker = 炮口canvas + HEAD_OFFSET`，炮口始终粘在炮管上 |
| 根 `ROOT_OFFSET` | `(-40, -40)` | 不变 | 身体位置永不动 |

### 12.2 射击后抽搐（抖动）修复

**根因**（三层证据）：皮肤 clip `HeadFire=(50,86)` 把经典 `SuperGatling.reanim` 的
**大招蓄力段 75..86** 也包了进去 —— 那是 3 帧一循环的剧烈抖动（头部轨道
`(22,7)↔(19.5,13.8)↔(17.9,19.5)` 每帧跳变，垂直振幅 ~12.5px，重复 4 次）。
`FireComponent.AttackEntered`（:3259）在**每一轮 1.5s 普攻**都 `SetAnimation("HeadFire", loop:true)`
播完整段，播完 `AnimeCompleted`（:3542）才回 `HeadIdle@0.2` ⇒ 用户看到：
7 颗豌豆打完（0.6s）→ 头部继续狂抖 ~0.4s → 硬切回待机再弹一下。
**动画时长与攻击间隔的匹配本身没问题**（25 帧射击段 @2.886x ≈ 0.72s，内置单发家族同构），
问题纯粹是 clip 段位选错。

**修法**：植物包 `HeadFire` 收窄为 **(50,74)**（= 内置单发家族口径；f50 与 f74 位姿相同，
闭合循环，收尾自然回待机）。共享三件套不动（僵尸包《超级机枪读报僵尸》仍需 (50,86)），
补丁只打在植物包副本：`.tres` clips 文本替换 + `.dat` clip 表 **等长字节补丁**（u16 end
86→74，事件段零位移）。`75..86` 帧数据仍在 `.dat` 里，只是不再被任何 clip 引用；
发射事件仍在 f62；大招期间视觉反馈 = 引擎照常每 1.5s 循环 Attack（插件 BurstActive 分支）。

### 12.3 门禁与负向（本轮全部重跑）

| 检查 | 结果 |
|---|---|
| 生成器自检（含新增 13b 新不变量 / 13b-2 死值清零 / 13c-2 新恒等式 / 13e-2b .dat clip 表 / 13f-2 角色场景 on-disk 复核） | 全绿 |
| `check_modloader_gates.py` | ok=33 warn=1 FAIL=0 |
| `check_plant_super_gatling.py`（E7 改口径 + 新增 E7b/E8a/E8b） | **ok=262 warn=1 FAIL=0** |
| `check_project_folder.py` / `verify_pmod.py` | 40/0 与 12 ok/9 warn/0 FAIL |
| `run_gates_plant.py`（两份构建） | 各 52 PASS / 0 FAIL |
| `check_idempotent_plant.py` | 3 连跑字节稳定 |
| **负向测试**（篡改→必须报警→还原） | **5/5 报警**（.tres clip 回旧 / .dat clip 回旧 / Head offset 回旧 / Head.position 死值回流 / Marker 回旧 + 场景漂移） |

**负向测试还抓出并修掉一个既有盲区**：`self_check` 的 13f 只复核 Sprite 场景的磁盘内容，
角色场景（Marker2D 所在文件）被改旧值时自检照样「通过」⇒ 已补 13f-2。
另：植物生成器 `main()` 没有 `--self-check` 分支（总是先重建再自检，会把篡改修掉），
本轮新增 **`--check`**（只验证磁盘现状、不重建）。

### 12.4 产物指纹（本轮，改完必刷）

| 产物 | 值（★ 每轮改完必须刷新，最新见 §14.5） |
|---|---|
| `dist/超级机枪射手.pmod` | **178 046 B**，sha256 `332e561932eab22a…` |
| `Mods/超级机枪射手.pmod` | 与 dist 逐字节一致 |
| `Runtime/ModAssembly.dll` | **22 016 B**，sha256 `9298e407b9b599df…` |

> ⚠️ **实机待验收**（离线验不了观感）：① 头位与豌豆射手并排比对；② 一轮射击结束后头部是否
> 平稳回落待机（无抖动/无硬切感）；③ 大招期间观感（循环 Attack，无独立蓄力段属预期取舍）；
> ④ 豌豆出膛点是否仍贴炮口（Marker2D 已随头位同步平移，公式上必然对齐，但建议肉眼确认）。

---

## 13. ★ 2026-09-24：齐射改版 —— 常规攻击一次打出 7 颗（狐尾草范式）

### 13.1 需求

常规攻击从「插件逐发连射」改为像**狐尾草（HWC）**那样：一次攻击把所有子弹**同时生成、同时射出**，
子弹之间**互不重叠**（横向位置排布），参考经典版超级机枪射手的齐射处理，**伤害/速度等属性不变**。

「未重置版/经典版」素材定位：`D:/zzz/extract_1789988101`（`NewPlantStrings.txt`：
超级机枪射手描述 =「发射 7 枚豌豆，概率发射大量豌豆」⇒ 7 颗齐射 + 10% 大招，与本 Mod 完全对应）。

### 13.2 狐尾草范式考证（重制版源码）

- 数据侧：`TowerDefensePlantHWCFireComponentDefinition.tres` 用**多条 `firePosMarkerPaths`**
  （3 个 Marker）+ `onlyEmitSignal=true`，把发射交给场景脚本。
- 场景脚本：`TowerDefensePlantHWC.FireVolley` 订阅 `OnFireVolley`，循环调
  `CreateProjectileByData(i, velocity, ...)` 一次性把所有弹打出。
- 本 Mod 没有「场景脚本托管」通道（ModAssembly 只能写运行时入口）⇒ 齐射部分改用
  **引擎原生多配置一次 Fire() 通道**（数据侧齐射，效果等价）；大招部分沿用狐尾草的
  `CreateProjectileByData` API（插件侧单颗直调）。

### 13.3 数据侧齐射方案（`build_plant_super_gatling.py`）

- `fireProjectileList` **7 条** `FireComponentFireProjectileConfig`（speed=500 / dir=0 /
  checkProjectileId=0 / `firePosId` 0..6 各一次）；刻意**不写 `fireNumAtOnce`**
  （默认 false ⇒ `FireConfiguredVolley()` 恰好 1 次 `Fire()`，`FireComponent.cs`）。
- `FireComponent.Fire()`（`FireComponent.cs:3434`）一次遍历 `_fireProjectiles` 全部配置**同帧打出**
  —— 触发链不变：动画 `fire` 事件 → `AnimeEvent`（fireEventName 默认 "fire"）→ `Fire()`。
- **横向散布（★ 口径见 §13.7）**：`firePosMarkerPaths` 7 条 → 场景里 7 个 Marker 节点
  （`Marker2D`/`Marker2D2`..`Marker2D7`），位置 = `(MARKER2D_POS.x + dx, MARKER2D_POS.y)`，
  `dx ∈ {0, 32, 64, 96, 128, 160, 192}`（`volley_marker_dx()` 沿**弹道方向**递增；
  **`Marker2D` 恒为炮口点**，13c-2 恒等式钉在它身上）。豌豆 `ProjectilePea.png` 实测 28×28 ⇒
  间距 32 px 保证不重叠。`CreateProjectile` 的 `offset` 参数是死参数（V0.28 函数体从未使用），
  偏移只能走 Marker 位置。
- **锁行**：BulletField 每帧按像素位置重算弹的 gridY（`BulletField.cs:1473`）⇒
  `fireComponent.lockProjectileGridY = true`（`FireComponent.cs:2743` → `overrides.gridYOverride`
  = 种植行 → `BulletField.cs:5598` `lockGridY=true`）⇒ 命中判定恒按种植行过滤，与单发逐字一致。
  （改版前排开在 y 上时它是**必需**的；现在 7 颗 y 全同，它升级为**显式不变量护栏**。）
- 常量：`VOLLEY_COUNT = 7`（自检第 0 节不变式 `VOLLEY_COUNT == PEAS_PER_ATTACK`）、
  `VOLLEY_SPACING = 32.0`；`PEA_COUNT` 已删除。

### 13.4 插件角色变化（`runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs`）

- **撤销 vanilla 发射链屏蔽**：删掉 `ApplyVanillaFireSuppression` / `VanillaFireEventName` /
  `PeasLeft` / `NextPeaMsec` / `AdvanceNormalAttack` —— 常规攻击回到纯数据链，插件不再碰。
- **大招改走狐尾草同款 API**：`FireUltimatePea(hook, angleDeg)` 实时读
  `fireProjectileList[0].speed`（弹速与常规齐射**同源单一真源**，兜底 `FallbackPeaSpeed=500f`），
  `fire.CreateProjectileByData(0, velocity, checks[0].GetProjectile(), -1, PLANT, Vector2.Zero,
  overrides)`；`collisionFlags=-1` ⇒ 与 `Fire()` 的 `useParentCollision=true` 默认路径一致
  （`FireComponentCheckConfig.cs:57-64`）；`overrides` 带 `spriteRotationOverride`（与
  `Fire()` :3493 同口径）+ `flipXOverride`（= 本体 Scale.X<0）。
  伤害走 `GetProjectile()` 原值一个字段不改。
- `OnFireReadyFrom` 只掷大招骰；`AdvanceHooks` 只推大招轴。`UpdateChild`/`SyncHeads` 未动。

### 13.5 门禁与负向测试

| 检查 | 结果 |
|---|---|
| 生成器自检（新增 #0 不变式 / #13c-3、#13f-3 七 Marker 双重复核 / **#13c-4、#13f-4 排列形态四判据** / **#13g ComponentSet on-disk 复核** / #16 转发口径 / #17 插件结构证据） | 全绿（齐射口径打印，含「一排，非一列」） |
| `check_plant_super_gatling.py`（C1=7 条、C3a firePosId 0..6 各一次、C4 禁 fireNumAtOnce、C5b 锁行、C19x 场景 7 Marker + **C19c/C19d/C19f 形态**、E 段 K13x 插件不回流发射链、K15 五元组） | **ok=314 warn=1 FAIL=0**（2026-09-25 扩容，见 §14.4） |
| `check_modloader_gates.py` / `check_project_folder.py` / `verify_pmod.py` | 33/0、40/0、12 ok(9 warn)/0 |
| `build_runtime.py --check`（改版后**复跑**） | 两次编译字节一致，`9298e407b9b599df` |
| `check_idempotent_plant.py` | 3 连跑字节稳定 |
| `check_gates_plant.cs` / `run_gates_plant.py`（两份构建） | 53 PASS / 0 FAIL（remake + console） |
| **负向测试** `_neg_test_head.py`（既有 19 条） | 19/19 如期报警 |
| **负向测试** `_neg_test_volley.py`（8 条：场景 Marker **x** 篡改 / 锁行被关 / firePosId 重复 / 齐射少一条 / 插件回流 fire.Fire() / 插件回流 fireEventName / **单颗脱离水平线** / **整组回退成旧「一列」布局**） | **8/8 如期报警**，还原后自检全绿 |
| **负向测试** `_neg_test_almanac_text.py`（9 条，2026-09-25 新增，见 §14.4） | **9/9 如期报警**，还原后自检全绿 |

> 负向测试实锤并修掉两个盲区：① 场景模板硬编码 `Marker2D` 与循环生成节点**同名重复**
> （Godot 同名节点互相覆盖）—— NEG-V1 注入目标缺失暴露；② ComponentSet 的 self_check 只比
> 内存文本、磁盘篡改照样报绿 —— 补 **#13g** on-disk 复核。

### 13.6 产物指纹（本轮，改完必刷）

| 产物 | 值（★ 最新见 §14.5） |
|---|---|
| `dist/超级机枪射手.pmod` | **178 046 B**，sha256 `332e561932eab22a` |
| `Mods/超级机枪射手.pmod` | 与 dist 逐字节一致 |
| `Runtime/ModAssembly.dll`（工作区 = 安装副本） | **22 016 B**，sha256 `9298e407b9b599df` |

> ⚠️ **实机待验收**（离线验不了观感）：① 常规攻击一次打出 **7 颗**、屏幕上呈**水平一条直线**
> （`dx = 0/32/…/192`）不重叠；② 7 颗全部只打**种植行**（不窜排）；③ 出膛点从炮口点起向前排开；
> ④ 大招期间常规齐射照常打出、不叠加新大招、弹速与常规一致；
> ⑤ §12 的头位验收项不受本轮影响。

### 13.7 ★ 排列口径修正（同日，用户："子弹要直线一排，不是直线一列"）

**现象**：13.3 首版把 7 个 Marker 沿 **y** 铺开（`0/±32/±64/±96`）⇒ 界面上 7 颗豌豆是
**竖直一列**；用户要的是**水平一排**。

**根因**：把需求里的「横向位置偏移」当成了「垂直于弹道的横向」（= y），
实际应为「屏幕水平方向」（= 沿弹道的 x）。因为豌豆沿 +x 飞行，**唯一能排出水平直线的轴就是 x**。

**改法（只动数据侧，插件与 DLL 不变）**：

```python
VOLLEY_FORWARD_SIGN = 1.0      # 方向常量（反向只改它）
def volley_marker_dx(i):       # 原 volley_marker_offset（返回 dy）已重命名+改轴
    return i * VOLLEY_SPACING * VOLLEY_FORWARD_SIGN     # 0,32,64,…,192（**只向前**）
# 场景：position = (MARKER2D_POS.x + dx, MARKER2D_POS.y)   ← y 恒定
```

**方向为什么是 +x**（三重证据）：① 链路无镜像（Sprite root `offset=(-40,-40)` /
Head `offset=(-37.05,-47)` / 无 `scale` 覆写）；② `MARKER2D_POS = 炮口(88.552, 30.2) + HEAD_OFFSET`
⇒ 经典坐标的炮口在锚点**右侧** 48.55px，符号未被翻转；③ `FireComponent.cs:3462`
`velocity = speed * Vector2.FromAngle(deg2rad(dir))`，`dir=0` ⇒ `(1,0)` = +x。
**只向前不向后**：Marker2D 的世界位就是炮口，往后铺的 3 颗（`dx<0`，本地 x ≈ −12.5/−44.5）
会落进植物身体或背后，看起来像从植物后面冒出来。

**新增护栏**（把「一排」写成不变量，防再退化）：
`self_check` **13c-4 / 13f-4**（内存 + 磁盘各一遍，四判据：条数 7 · **y 唯一** ·
**x 严格递增且步距恒 32** · **首颗 x = 炮口 x**）+ 门禁 **C19c**（x 偏移集合精确等于
`{0,32,…,192}`）· **C19d**（y 全相同）· **C19f**（x 按 firePosId 顺序严格递增）；
负向测试新增 **NEG-V7**（单颗脱离水平线 ⇒ 报「一列」）与 **NEG-V8**（整组回退旧列布局 ⇒ 报「一列」）。

**验证**：生成器自检全绿；门禁 **ok=277 FAIL=0**（当轮值）；负向 **8/8**（+ 既有 19/19）；
`run_gates_plant.py` 两份构建各 52 PASS / 0 FAIL；幂等 3 连跑字节稳定；
产物 `177 283 B / 58db2085b053fe9c`（DLL 未变 ⇒ `dc9426dc9e13a416`）。

---

## 14. ★ 2026-09-25：图鉴去重 + 描述文案替换（用户截图口径）

### 14.1 需求（用户原话）

> 「修复图鉴重复出现的问题：删除仅包含该角色的独立图鉴，将其保留在已有的金卡类型图鉴中。
> 同时将该角色的图鉴描述文本替换为指定图片中的文本内容，其中技能数值的描述由
> “威力：20×7/2秒”修改为“威力：20×7/1.5秒”。」（附截图 `QQ_1790288195860.png`）

拆成两条独立改动：**① 图鉴去重**（插件侧）· **② 文案替换 + 数值改 1.5 秒**（数据侧）。

### 14.2 ① 图鉴重复出现的成因与修法

**成因（有源码位置）**：`XWModContentCatalog.WithPlants()`（`XWModContentCatalog.cs:107-123`）
把 `GeneralPlant` 卡库深拷贝一份，然后把所有 Mod 植物塞进**新建**的
`category["ModPlants"]`（`PlantCategory = "ModPlants"`，同文件 :15）；
`Almanac.cs:219` 是**全库唯一**调用点，图鉴就按这份拷贝的分类翻页（`Almanac.cs:317-328`）。
于是本包「补进 Gold」之后，本卡**同时**出现在
「`ModPlants`（只有它自己）」和「`Gold`」两个分类里 ⇒ 用户看到的「重复」。
`ModPlants` 在 `Asset/Config/PacketBank/PacketBankResource.json` 里根本没有（那是运行时硬塞的），
纯数据改不动它 —— **只能靠插件**。

**修法**（`runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs` 的 `TryPatchAlmanac`，见 §3.5.1）：

| 步 | 做什么 | 关键点 |
|---|---|---|
| ① | 倒序 `modPlants.RemoveAt(i)` 摘掉 `SuperGatlingPea` | **摘条目不是删分类** —— `ModPlants` 是所有 Mod 植物共用的 |
| ①b | 摘完 `Count == 0` ⇒ `categories.Remove(ModPlantCategory)` | 这才是用户要的「删除仅包含该角色的独立图鉴」 |
| ② | `Gold` 里缺则补，多则去重 | 图鉴已开着时的兜底 |
| ③ | `changed` 为真才：回落 `plantCategoryId` ⇒ `IsPlantPageInitialized` 时 `almanac.InitPlant()` | 不破坏懒初始化；不越界 |

**为什么 ③ 不能省**：`Almanac.InitPlant()` 第 317 行就是
`if (!IsInstanceValid(plantPacketBank) || plantCategoryId >= plantPacketBank.category.Count) { … return; }`
⇒ 删掉分类后若 `plantCategoryId` 停在越界值，**直接返回空列表**（图鉴空白）。
`ModPlants` 追加在键序末尾，所以只有「正好停在这一页」才会越界；统一回落
`categories.Count - 1` 一次最稳。

**验证接缝**：`runtime_src_plant/check_gates_plant.cs` 第 6 组新增
`Almanac.plantCategoryId 是 public int 字段`（两份游戏构建都跑）——
这是插件新增的唯一「非反射但编译期管不到」的字段访问，改版后会静默失效。

### 14.3 ② 文案替换（逐字，含 1.5 秒）

| 面板位置 | 字段 | 值（**内联**） |
|---|---|---|
| 标题 | `name` | `超级机枪射手` |
| 深藏青短句（面板自动包色） | `describe` | `大哥登场！` |
| 数值块 | `handbookDescribe` | `韧性：[color=cc241d]1000[/color]`⏎`威力：[color=cc241d]20×7 /1.5秒[/color]`⏎`范围：[color=cc241d]前方一行[/color]`⏎`特点：[color=cc241d]每次攻击有10%概率释放大招[/color]`⏎`大招：[color=cc241d]小范围散射约300枚子弹[/color]` |
| 故事 | `handbookStory` | `超级机枪射手完美诠释了“火力优势学说”，在那个属于他的时空，他的每次发怒都是无数僵尸的梦魇。然而，他也有属于自己脆弱的一面，比如他背地里其实很害怕史莱姆。` |
| 花费 / 冷却 | —— | 面板自己拼（`花费：600` / `冷却速度：30.0 秒`），**不写进字段** |

**为什么必须内联**：见 §3.4 的三条证据 —— Mod 的 `translations.csv` 在游戏运行时**不加载**，
写 key 就显示 key。旧版四个字段都是 `TOWERDEFENSE_PLANT_SUPERGATLINGPEA_*`，
游戏内显示的就是这串大写英文。
`saveKey` 才是身份标识 ⇒ 改 `name` 不破坏注册；官方
`XWInlineTextCoverageContract.cs:13-15` 也把这三个字段声明为 `Title/Description`（允许内联）。

**格式口径**：与官方 `Prefab/GUI/InformationPanel/InformationPanel.tscn` 自带范例模板
**逐字符同款** —— 头词裸文本（吃面板 `default_color = Color(0.560784,0.262745,0.105882)` = `#8F431B` 棕）
+ 数值 `[color=cc241d]`（`#CC241D` 红）；`describe` 由面板自己包 `[color=2f375e]`（`InformationPanel.cs:229`）。
截图逐像素取样也吻合（头词 `(143,67,27)` / 数值 `(204,36,29)`）。
`.tres` 多行用**真实换行**（与官方 `Challenge_Level13_3.tres` 同）。

**translations.csv 的处置**：键从 `TOWERDEFENSE_*` 改成**内联中文原文本身**，
只留单行的 `name` / `describe` 两行（多行的数值块/故事会破坏朴素 CSV 行结构，不收录）；
文件本身**保留** —— `mod.json` 的 `translations` 字段必须指向真实文件
（`ModLoader.ValidateManifestRegistrations`）。

### 14.4 本轮新增的护栏（全部为「防假绿」而加）

| 位置 | 内容 |
|---|---|
| 生成器 `self_check` **13h / 13h-2** | **读磁盘**逐字核对：4 个字段是内联字面量、无 `TOWERDEFENSE_*` 残留、`describe` 不带颜色标签、威力 = `20×7 /1.5秒`、不含旧 `2s/2秒`；数值块恰 5 行且**每行**匹配 `头词：\[color=cc241d\]值\[/color\]` |
| 生成器 `self_check` **12 段**（重写） | 翻译 CSV **读磁盘**核表头 + 无 `TOWERDEFENSE_*` 键 + 含以中文名为键的行（原来是拿 `translation_file()` 自比 = 恒真） |
| 生成器 `self_check` **18 段**（新增） | 插件侧 7 条**活语句**断言（常量 / `categories.Remove(ModPlantCategory);` / `if (modPlants.Count == 0)` / `modPlants.RemoveAt(i);` / `almanac.plantCategoryId = categories.Count - 1;` / 越界守卫 / `almanac.InitPlant();` / `IsPlantPageInitialized(almanac)` / `gold.RemoveAt(i);`） |
| 生成器 **`_strip_cs_comments()`**（新增） | ★ **本轮最有价值的发现**：对插件源码做子串断言时，**把那一行注释掉就能骗过断言**（`/* categories.Remove(ModPlantCategory); */` 里子串还在）⇒ 第 17/18 节的断言一律改吃「去注释后的代码」（字符串字面量内的 `//` 不误伤，`@"…"` 逐字串已处理） |
| 生成器断言口径 | 从「子串级」（`"RemoveAt(" not in cs`）升级为「**整条活语句**」（`"modPlants.RemoveAt(i);"`）+ 关键**条件表达式**也要在（`if (modPlants.Count == 0)`）⇒ `false &&` 型死分支骗不过 |
| 门禁 `check_plant_super_gatling.py` **C29 / C29b–C29j**（12 条 × 2 份卡片 = 新增 24 条） | `prop_block()` 新助手（读**跨行**字符串属性）；逐字核对 4 个字段 + 5 行数值块 + 格式正则 + 无旧键 + 无旧 `2s` 口径 |
| 门禁 **B15 / B15b** | 翻译 CSV 不再用 `TOWERDEFENSE_*` 键、含以中文名为键的行 |
| 门禁 **K20a–K20g** | 插件源码里 7 条图鉴去重的活语句/条件 |
| 负向测试 **`_neg_test_almanac_text.py`（9 条）** | T1 威力改回 `2s` · T2 name 改回翻译键 · T3 describe 自带颜色 · T4 数值块塌成 `\n` 转义 · T5 CSV 键改回旧 key · T6 **注释掉**删分类 · T7 不回落 `plantCategoryId` · T8 改成整类清空 · T9 判定改 `false &&` 死分支 —— **9/9 如期报警** |

### 14.5 产物指纹（本轮，改完必刷）

| 产物 | 值 |
|---|---|
| `dist/超级机枪射手.pmod` | **178 046 B**，sha256 `332e561932eab22a` |
| `Mods/超级机枪射手.pmod` | 与 dist 逐字节一致（已复算比对） |
| `Runtime/ModAssembly.dll`（工作区 = 安装副本） | **22 016 B**，sha256 `9298e407b9b599df` |

（上一轮：pmod 177 283 B / `58db2085b053fe9c`，DLL 20 992 B / `dc9426dc9e13a416`。）

### 14.6 本轮门禁全跑（一次通过）

| 检查 | 结果 |
|---|---|
| `build_runtime.py --check` | 两次编译字节一致，`9298e407b9b599df` |
| `build_plant_super_gatling.py`（落盘 + 内置自检） | 全绿，exit 0 |
| `check_plant_super_gatling.py` | **ok=314 warn=1 FAIL=0** |
| `check_modloader_gates.py` / `check_project_folder.py` | 33/1/0、40/0/0 |
| `verify_pmod.py dist/超级机枪射手.pmod` | 12 ok / 9 warn / 0 FAIL |
| `check_gates_plant.cs`（`run_gates_plant.py`，两份构建） | **53 PASS / 0 FAIL**（remake + console） |
| `check_idempotent_plant.py`（3 连跑） | 全部字节稳定，无残留 |
| `_neg_test_volley.py` / `_neg_test_head.py` / `_neg_test_almanac_text.py` | 8/8 · 19/19 · **9/9** |
| `.cache/_check_handover_doc.py` | PASS（107 OK / 0 FAIL） |

### 14.7 ⚠️ 实机待验收（离线验不了）

1. **图鉴分类**：植物页翻分类时**不再有** `ModPlants` 这一页；本卡**只出现一次**，在**金卡**分类里
   （金卡第 20 张，与内置金卡排在一起）。
2. **文案逐字**：点开本卡 ⇒ 标题 / `大哥登场！` / 韧性 1000 / **威力：20×7 /1.5秒** /
   范围 前方一行 / 特点 / 大招 / 故事段 与截图逐字一致；`花费：600` / `冷却速度：30.0 秒` 由面板生成。
3. **日志**：`[SuperGatlingPea] 图鉴去重：本卡是该分类里唯一的植物 ⇒ 已删除「ModPlants」分类本身`
   （若装了别的含植物的 Mod，则会是「已把…从「ModPlants」分类里摘掉（该分类还剩 N 个其它 Mod 植物…）」）。
4. **回归**：§12 头位 / §13 齐射「水平一排」/ 大招照常 —— 本轮只动图鉴分类与卡片文案，
   未碰发射链、动画、外观。

