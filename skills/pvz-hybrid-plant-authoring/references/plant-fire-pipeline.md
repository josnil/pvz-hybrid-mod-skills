# 植物发射管线：从"打不出子弹"到精确控弹

## 0. ★★★ 先过这一关：角色场景必须显式声明 `ComponentSet`

> 这是「做开枪类角色」**最容易白忙的坑**，而且**加载期完全静默**（不拒包、不告警、不进 diagnostics）。

**症状**：角色走路/血条全正常，就是**一个弹丸都不出**；插件侧
`componentManager.GetRuntime<FireComponent>("character.fire")` 返回 **null**。

**根因链**：

```csharp
// TowerDefenseCharacter.cs:703-704
[Export] public CharacterComponentSet ComponentSet { get; set; }
// TowerDefenseCharacter.cs:1911-1937  EnsureComponentManagerResource()
if (IsInstanceValid(ComponentSet)) componentManager.ComponentSet = ComponentSet;  // 只有显式声明才用你的
// ComponentManager.cs:318-352  InitializeResourceComponents()
entry.Definition.CreateRuntime();   // 集里没有 Fire 定义 ⇒ 这个 runtime 组件根本不会被 new
```

**正确写法**（`ComponentSet` 必须在 `script` **之前**，且必须是包内相对路径）：

```ini
[node name="<Key>" node_paths=PackedStringArray("…") instance=ExtResource("1")]
ComponentSet = ExtResource("15")
script = ExtResource("2")
```

内置先例：`TowerDefenseZombieNormalGatlingPea.tscn:25` 就是这么写的。

**必须自己加闸门**（`ModLoader.InferRuntimeEntry()` **不检查 `.tscn` 内容**，漏了没有任何报错）：

1. 断言场景里有 `ComponentSet = ExtResource(`；
2. 断言它指向包内相对路径 `./<Key>ComponentSet.tres`；
3. 断言包内组件集的 `ParentSet` 指向内置集，且 `Components` 只加 **1 个**发射定义
  （父集带来其余全部）。

**插件侧纪律**：不要在 `IsUsable(fire)` 为假时静默 `return`（踩过：静默了一整轮），
一定要打一次性诊断日志并直接点名「场景可能漏了 `ComponentSet`」。

## 1. 发射配置的写法（纯数据）

`TowerDefensePlant`(Node2D) 是基类，各植物一个 C# 子类声明 `[Export] fireInterval / fireNum /
projectileName` 转发给 `FireComponent`。**真正生效的数据在 `FireComponentDefinition`**：

```csharp
// FireComponent.cs:3413  FireConfiguredVolley()
if (!fireNumAtOnce) { Fire(); return; }
for (int i = 0; i < fireNum; i++) { currentFireNum = i; Fire(i == 0); }
```

| 想要 | 写法 | 原版例子 |
|---|---|---|
| N 颗同方向叠发 | `fireNum = N` + `fireNumAtOnce = false` | 豌豆射手 |
| **一次齐射 N 条不同方向** | `fireNum = 1` + **`fireNumAtOnce = true`** + **N 条 `FireComponentFireProjectileConfig`** | 五角星(5)、三线射手(3) |
| **由插件「逐颗」驱动**（概率/真随机/每颗改向） | **只留 1 条 config（`dir = 0`）** + `fireNum = 1`、**不要 `fireNumAtOnce`** | 见 `plant-runtime-plugin.md` |

⚠️⚠️ **`Fire()`（`FireComponent.cs:3429`）一次调用会遍历全部 `fireProjectileList`**
（引用拷贝 `_fireProjectiles`）⇒ 插件逐颗调 N 次时，若数据侧还留着 N 条 config，
就是 **N × N = N² 颗重叠**（实际踩过：7 条 config × 7 次调用 = 49 颗）。
**要逐颗就先把 config 收敛成恰好 1 条。**

* 方向字段是 `dir`，**单位是度，0 = +X（右）**：
  ```csharp
  // FireComponent.cs:3434 / :3462
  velocity = cfg.speed * Vector2.FromAngle(Mathf.DegToRad(cfg.dir));
  ```
* **朝向自动镜像，不用管**：`CreateProjectile`（`:2684`）末尾乘了
  `Mathf.Sign(parent.Scale.X * parent.transformPoint.Scale.X * parent.sprite.Scale.X)`。
  只写一套「向右」的 `dir`，僵尸在左边时自动变成向左。
* `FireComponentFireProjectileConfig` **只有 8 个字段**：
  `checkProjectileId, firePosId, speed(=300), dir(=0), offsetLine, fireNumSkip(=-1), fireEventNeed, projectileFlip`。
* 散射范式：`Starfruit` → 5 条 `dir = 330/270/180/90/30` + `firePosId 0..4`（`speed=500`）；
  `ThreePeater` → 3 条用 `offsetLine = -1/0/+1`（换行）；`SplitPea` → `fireNum=2` + `fireNumSkip=1` + `speed=-300`（向后）。

## 2. 射击动画与出膛点

* 射击动画靠 `fireAnimeClips="HeadFire"` / `spliceIdleAnimeClips="HeadIdle"` / `isSpliceSprite=true`
  \+ `firePosMarkerPaths = [NodePath("<...>/Marker2D")]`（**指向场景里真实存在的 Marker2D 节点**）。
* ⚠️⚠️ **`firePosMarkerPaths` 必须指向真正的 `Marker2D`**：
  ```csharp
  // FireComponent.cs:1232（ResolveReferences）
  Marker2D item = ResolveOwnerNode<Marker2D>(Definition.firePosMarkerPaths[i]);
  // FireComponent.cs:1254
  return parent.GetNodeOrNull<T>(path);        // ★ 带类型过滤
  ```
  ⇒ 指向 `AdobeAnimateSlot`（如僵尸的 `HeadSlot`）会拿到 **null**，子弹从角色**原点**出膛。
  要在场景里自己挂一个，例如
  `[node name="FireMarker" type="Marker2D" parent="SpriteGroup/TransformPoint/<精灵>/HeadSlot" index="0"]`。
  ⚠️ 挂 `[sub_resource]`/`NodePath` 里**没有**的类型，`.tres` 不报错，只是静默失效。
* ⚠️ **`FireComponent.sprite` 是「Head 本体」不是角色根**：
  ```csharp
  // FireComponent.cs:1241
  sprite = ResolveOwnerNode<AdobeAnimateSprite>(Definition.spritePath);   // 路径 = …/TransformPoint/<精灵>/Head
  ```
  ⇒ 插件拿到的是 `Head`（其父才是 body）。写头身同步时**先判 `node.Name == "Head"`** 则
  `body = node.GetParent()`，否则（拿到根）才 `%Head`。旧写法会让 `body == head` ⇒ **自环、同步变空操作**。

## 3. ⚠️ 没有开火动画 ⇒ 整条「动画驱动发射」链路失效（设计好的降级，不是 bug）

```csharp
// FireComponent.cs:3230（AttackEntered 第一句）
if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(FireRuntimeState.Idle); return; }
// FireComponent.cs:998 / :1011
private bool CanPlayFireAnimation(string clipName) { … if (string.IsNullOrEmpty(clipName)) return false; … }
```

⇒ `fireAnimeClips` 留空（或精灵里根本没有那个 clip）时**一枪都打不出去**。

想做「没有开火动画的角色也能开枪」⇒ **只能写插件**，并**刻意不写**
`fireAnimeClips` / `spliceIdleAnimeClips` / `spritePath`（后者留空 ⇒ `FireComponent` 连
`sprite.timeScale` 都不碰）。附带好处：**不必去枚举 `.dat` 动画里的 clip 名**
（解包树里有些 `.dat` 缺失，枚举不出来）。

## 4. ★★★ 「攻击时只有动画、没有子弹」的唯一真因 = 动画 `events` 表里没有 fire 条目

**普通射击 100% 是「动画事件驱动」的，插件只负责大招** ⇒ 只写 `fireAnimeClips="HeadFire"`
让动画播起来**不够**，必须让动画在某一帧**发出 `fire` 命令**：

```
AdobeAnimateSprite.events[播放到的帧]
  → OnAnimeEvent?.Invoke(dict["Command"], dict["Argument"])      AdobeAnimateSprite.cs:5327
  → FireComponent.AnimeEvent(cmd, arg)                          （订阅点 FireComponent.cs:1484）
  → cmd ∈ fireEventName.Split("&")     // fireEventName 默认 "fire"   FireComponent.cs:343
  → FireConfiguredVolley()  →  Fire()  → 按 firePosMarkerPaths 生成子弹
```

⇒ **`.dat` 与 `.tres` 的 `events` 表必须含 `{"Command":"fire","Argument":""}`**，
否则**动画照播、一颗弹都没有，且加载期零报错**（极易误判成贴图/插件问题，白查半天）。

> ⚠️ 与「插件用 `fireEventName = "modfire"` 掐掉原版开火链」**不能同时用**，二选一：
> 纯数据驱动用这条；插件驱动用那条（否则一次攻击 = 原版一发 + 插件 N 发）。

### 4.1 发射帧定法（A/B 实证，别拍脑袋）

= `anim_shooting` 起点后「枪口轨(x) **首次**达最大伸出(±1px)」的帧，
且**必须 `帧 − HeadFire.start == 12`**。

* **证据 A（内置扫描）**：扫 143 个 remake 植物 `.tres`，单发族 7 例
  （PeaShooter / SnowPea / ReCactus / SunflowerPea / SunPeashooter / IceSpearPea / PeaShooterSingle）
  **清一色** `HeadFire=(50,74)` + **恰好 1 条 event @ f62**；
  多连发按「次极值 −1」：内置 GatlingPea 4 条 @61/67/73/79、ThreeCactus @55/61/67/73。
* **证据 B（本 Mod 数值）**：`GatlingPea_mouth` 的 x 在 **f62 首次达 max** 并保持到 f65。
  ⚠️ 用严格 `max()` 会落到平台末端 **f65** ⇒ 偏移 15≠12，被自检门槛拦住。
  改用 `min(j for j, v in xs.items() if v >= mx - 1.0)`。

### 4.2 `.dat` 事件段字节布局

```
u16 eventCount
  每条: u16 frameIndex  +  u16 entryCount  +  entryCount × (PascalString Command, PascalString Argument)
```

⚠️ **两个易错点**：① `frameIndex` 是 **`u16` 不是 `u32`**（曾把 checker 误按 u32 写）；
② **`Command` 在前、`Argument` 在后**（顺序反了会静默解析错位）。
出处：`AdobeAnimateData.InitInternal:1352-1372`（`Get16()` + `GetPascalString()`）。

> `.tres` 侧：
> ```ini
> events = { 62: [{ "Command": "fire", "Argument": "" }] }
> ```
> ⚠️ 字典键序 = **ASCII 序** ⇒ `Argument` 在 `Command` 前。

## 5. ★ 双图层父子精灵（头独立）范式 —— 照抄内置 `GatlingPea.tscn`

* 结构：根 `AdobeAnimateSprite`(body) → 子节点 `Head`(也是 `AdobeAnimateSprite`)，各自播 body / head 的 clip。
* `clip` 取控制轨 marker：`BodyIdle(0,24)` / `HeadIdle(25,49)` / `HeadFire(50,86)`。
* **根 / Head 的 `offset` 都是 `−(40,40)`**；`Marker2D` = 炮口 − (40,40)。
* ★ **头位微调改的是 `Head.offset`，不是 `Head.position`**（2026-09-22 更正）：
  `AdobeAnimateSprite.UpdateChild()`（`:5259-5281`，`usePos`/`useRotate` 默认 `true`）每帧重写子精灵的
  `Position/Rotation` ⇒ 场景里写的 `Head.position` 是**死值**；而 `offset` 只作用于本精灵自己的美术
  （`:7044`/`:7071`/`:7362`），**不影响** `Marker2D`（炮口）。头身**同源**时两层 `offset` 必须相同，
  跨素材拼装（僵尸身 + 植物头）才用 `Head.offset` 反解（见 `plant-skin.md` §2.4）。
* ⚠️ **`insertLayerId = max(body 真实贴图层) + 1`**（头要盖在身体之上）。

## 6. 插件驱动时的触发点选择

| 触发点 | 声明 | 特点 |
|---|---|---|
| `FireComponent.OnFireReady` | delegate，`FireComponent.cs:255` | **`AttackEntered()`（`:3258`）里只发一次** ⇒ 天然「本轮攻击开始」信号，**无需去抖** |
| `FireComponent.OnFireVolley` | event，`FireComponent.cs:673` | **每条 config 各发一次** ⇒ 一次齐射会掷 N 次骰子，**必须去抖**（200ms 时间窗） |

**节奏仍由引擎状态机给**：`IdleEntered(:3089)` → `Refresh(:2377)` 设
`timer = fireInterval ± offset` → 每物理帧递减 → 归零且有目标 ⇒ `AttackEntered` ⇒ `OnFireReady`。
⇒ 插件**不要自己造节拍器来定"每 1.5 秒一轮"**，跟着 `OnFireReady` 走就与游戏一致。
