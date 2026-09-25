# 僵尸 Mod：超级机枪读报僵尸（Zombie 类）

> 产物：`dist/超级机枪读报僵尸.pmod`（181 388 B，sha256 `b054c21bbe8b2c69…`）｜ 包内 **14** 个条目
> 生成器：`build_zombie_super_gatling_paper.py` ｜ 插件源码：`runtime_src_zombie_super_gatling/`
> 复核脚本：`runtime_src_zombie_super_gatling/check_gates_super_gatling_paper.cs`（由 `.cache/run_gates_sgp.py` 驱动，**两份构建各 300/0**）、
> `.cache/check_sgp_idempotent.py`（3 连跑同 sha256）、`.cache/check_head_fit.py`（头对位反解 + 炮口/生成点，含负向测试）、`.cache/_byte_check_head.py`（Sprite / Scene / FireDef 三份产物字节核对）
>
> **2026-09-22 改版（共 6 处）**
> ① 外观 = 读报僵尸的身体 + **超级机枪射手的头**（§2.5，零自制贴图 / 零自制动画）；
> ② 射击判定参数与植物版《超级机枪射手》**共用** `runtime_shared/GatlingVolleyCore.cs`（§7.6 / §9.2）；
> ③ 图鉴僵尸页的**重复条目已在运行期消除**（§7.3）；
> ④ ★ 头部素材换成**超级机枪射手**（包内自带 `Resources/Animations/SuperGatlingPea.*` 三件套，
>    不再借用内置「机枪射手」）；
> ⑤ ★ 头对位**重新标定**（旧值 `(-36,-46)` 偏 **41.75 px** ⇒ 就是截图里的悬空）；
> ⑥ ★ 补上**植物僵尸共用的射击判定**（没有植物不开火、没进场不开火）。
> ④⑤⑥ 的完整取证见 **§2.6**。
>
> **2026-09-23 改版 A（共 2 处，用户：「头摆正、不再歪斜、相对位置保持一致 + 层级调高」）**
> ⑦ ★ ★ 头**不再跟着 `anim_head1` 摆**：两个头都写 `usePos = true` / `useRotate = false` / `rotation = 0.0`，
>    对位重解为 `Head.offset = (-54.19, -10.11)`（§2.7.10 ②③④）；
> ⑧ ★ ★ 可见头写 `z_index = 1`，**显式**压在身体与报纸之上（§2.7.10 ⑤）。
> 完整取证 + 该轮抓出的两个「假绿断言」见 **§2.7.10**，实测见 **§2.7.12**。
>
> **2026-09-23 改版 B（共 2 处，用户：「回退到上一版本的僵尸头部动画，然后在此基础上把头部
> 初始位置从偏左向右上方向微微移动」）—— ★ 本页现状**
> ⑨ ★ ★ **⑦ 已按用户要求回退**：两个头**三行全部撤掉**（`HEAD_FIX_HEAD_ROTATE = False`）
>    ⇒ 引擎恢复每帧覆写 `Rotation` ⇒ 头**重新跟 `anim_head1` 摆动**（Idle 净旋转 −16.03°..+1.01°）。
>    开关与机制**保留**（随时可切回），取证见 §2.7.10（留档）。
> ⑩ ★ ★ 头部**初始位置往右上微移**：新增 `HEAD_PLACE_SHIFT = (8, -4)`（**屏幕空间** px，y 向下），
>    对位重解为 `Head.offset = (-59.9377, -10.0515)`；判据从「中心距 ≤2px」改成
>    「**屏幕位移逐字 = (+8, −4)**」+「头块覆盖原头 ≥ 60%」（§2.7.13）。
> ⑧ 的 `z_index = 1` **不受回退影响**（用户只要求回退动画，层级那条需求仍成立）。
> 交付对照图：**`僵尸Mod-超级机枪读报僵尸-头部动画与位置对照.png`**（上排 = 上一版冻结，下排 = 本版；
> bf 0 / 12 / 20 同帧对比）、**`僵尸Mod-超级机枪读报僵尸-头部右移幅度候选.png`**（shift 0 / +4−2 / **+8−4** / +12−6）。

---

## 1. 它是什么

一个**新增僵尸卡**：外形与移动方式完全沿用**读报僵尸**，但在它身上装了一门机枪 ——
每 1.5 秒向前直线连发 7 颗豌豆，每轮开火有 10% 概率进入 5 秒狂暴、向 ±15° 散射 300 颗；
身上的报纸有 500 点独立血量，**报纸被打掉就暴走、移速 ×3**。

需求逐条对照（**16 条**；其中第 13 条已按第 15 条回退，见 §2.7.13）：

| # | 需求 | 落地位置 | 值 / 结论 |
|---|---|---|---|
| 1 | 显示名 = 超级机枪读报僵尸 | 卡片 `packet.name` 等 5 个显示字段 + 场景 `mod_display_name` | `超级机枪读报僵尸` |
| 2 | 以读报僵尸为原型，把头部换成「超级机枪射手」的头，风格与原游戏一致（2026-09-22 升级） | 精灵场景 = 内置 `ZombiePaper.tscn` 实例 + 一个 `Head` 子节点，动画数据**直接复用内置** `GatlingPea.tres` | **零自制贴图 / 零自制动画** ⇒ 画风天然一致（§2.5） |
| 3 | 每 1.5 秒向前方直线发射 7 颗豌豆，仅 7 颗 | **托管插件**（纯数据做不到，见 §2.1） | 周期 1500 ms；周期起点第 1 颗，之后每 100 ms 一颗 ⇒ 恰好 7 颗 |
| 4 | 每次攻击有 10% 概率触发大招，5 秒内向 ±15° 散射 300 颗 | 同上，插件 | `Randf() < 0.10`；第 k 颗时刻 = 起点 + k×(5000/300) ms ⇒ **恰好 300 颗 / 恰好 5 秒**；角度每颗独立 `RandfRange(-15,+15)` |
| 5a | 血量 500（二类防具）+ 1250（本体） | 护具槽 `damagePoint = 500.0`；`hitpoints + hitpointsNearDeath` | 500 / 1180 + 70 = **1250** |
| 5b | 移速 = 普通僵尸 | **什么都不写**（不覆盖 `walkSpeedScale`/`timeScale`） | 与内置普通僵尸逐字一致 |
| 5c | 伤害 800，伤害类型 = 啃食 | `characterConfig.attack` + 父组件集默认 `attackType` | `800.0` / `Eat` |
| 6 | 二类防具掉落后移速 ×3 | **白送**：复用内置读报僵尸脚本自带的暴走链路 | `timeScaleInit = 3.0` |
| 7 | 与植物版**共用**同一套射击判定逻辑（2026-09-22） | 判定抽进 `runtime_shared/GatlingVolleyCore.cs`；两个 csproj 各 `Compile Include` **同一份源文件** | 单一真源：改一处两边同时生效（§7.6） |
| 8 | 图鉴重复显示：只纳入可选卡表即可，不必再单独往图鉴加（2026-09-22） | 插件在**图鉴侧**运行期去重 —— 两条来源本身都删不得，见 §7.3 | 图鉴僵尸页**只剩一条** |
| 9 | 细节微调、风格与原游戏一致 | 头 / 身**全部是官方素材**（内置 `ZombiePaper.tscn` + 包内 `SuperGatlingPea.tres`）+ 藏掉原版头部的 7 个图层 | 物理上不可能不像（§2.5） |
| 10 | 头部贴图必须是**超级机枪射手**的，不是机枪射手的（2026-09-22 二次改版） | 皮肤三件套（`.dat`/`.tres`/`Atlas.png`）复制进包 `Resources/Animations/`，`Head.flashAnimeData` 指**包内** `.tres` | 内置素材库里**根本没有**「超级机枪射手」，只有 `GatlingPea` 等 8 个变体（§2.6 ①） |
| 11 | 头不能悬空、要和身体协调（2026-09-22 二次改版；09-23 改版 B 再微调位置） | `Head.offset` 由 `.cache/check_head_fit.py` 按引擎变换反解 | 当前值 **`(-59.9377,-10.0515)`**（= 跟随口径基准 `(-51.46,-7.21)` + 屏幕位移 `(+8,-4)`；位移误差 **0.000009 px**、覆盖原头 **95.1%**）；历代值 `(-36,-46)` / `(-49.07,-5.24)` / `(-54.19,-10.11)` / 纯几何 `(-51.46,-7.21)` / **方向坑（把 shift 直接加在 offset 上）** 全部被负向用例判失败（§2.6 ②、§2.7.10 ④、§2.7.13） |
| 12 | **植物僵尸共用的攻击判定**：没有植物不攻击、进场内才攻击（2026-09-22 二次改版） | 插件 `HasFireTarget()` → 引擎 `FireComponent.CanFireCheckOnceByData()` | 与原生 `idle fire check` **同一套判定**（§2.6 ③） |
| 13 | **头部摆正、不再歪斜**，且与身体的**相对位置保持一致**（2026-09-23 三次改版 A）—— ⚠️ **已被第 15 条按用户要求回退** | 两个头都写 `usePos = true` + `useRotate = false` + `rotation = 0.0` ⇒ 引擎不再覆写 `Rotation`，但 `Position` 仍每帧跟随 | 冻在 **0°**（= 该美术在植物里的**原生朝向**，实测植物跟随层全帧 +0.000°）；歪斜源 `anim_head1` Idle −16.03°..+1.01° 被彻底旁路（§2.7.10 ①②③，**留档**） |
| 14 | 头部的**渲染层级调高**，显示在身体及其他元素之上，不遮挡不穿插（2026-09-23 三次改版 A） | 可见头写 `z_index = 1`（`z_as_relative` 默认 true） | 全局排序键第一位是 `ZIndex`（`AdobeAnimateSortPath.cs:37-48`）⇒ effective z 高于身体，**对树序不敏感**（§2.7.10 ⑤）。**改版 B 未回退此项** |
| 15 | **回退到上一版本的僵尸头部动画**（2026-09-23 三次改版 B） | 把第 13 条的三行**全部撤掉**（`HEAD_FIX_HEAD_ROTATE = False`）⇒ 两个 `[Export]` 开关回默认 `true` ⇒ 引擎恢复每帧覆写 `Position`/`Rotation` | 头重新跟 `anim_head1`(L16) 摆动，Idle 净旋转 **−16.03°..+1.01°**（25 帧）；插件**零改动**（`SyncHeadPairs()` 本就是每帧抄位姿）——§2.7.13 ① |
| 16 | 头部**初始位置从偏左向右上方向微微移动**，使整体构图更协调（2026-09-23 三次改版 B） | 新增 `HEAD_PLACE_SHIFT = (8, -4)`（**屏幕空间** px，y 向下）；对位重解 `(-59.9377,-10.0515)` | 实测「偏左」= 整头块比身体左轮廓多伸出 **13.77px** ⇒ 移后剩 **5.8px**（≈身体宽度 8%，属「微微」）；**位移逐字 = (+8,−4)**，覆盖原头 95.1%——§2.7.13 ②③ |
| 17 | **子弹生成位置靠左一点、对齐子弹发射口**（2026-09-24 四次改版） | 场景 `FireMarker.position` 重解为 HeadSlot 局部 `(-35.697232, 94.988609)`（静态兜底） **+ 插件 `SyncHeadPairs()` 每帧**把 `marker.GlobalPosition` 覆写成 `head.GlobalTransform × (MUZZLE_POSE + HEAD_OFFSET)` | 真源 = `FireComponentDefinition.firePosMarkerPaths` 指向的 `Marker2D` 的**世界位置**（`FireComponent.cs:2698-2714` ⇒ `marker2D.GlobalPosition`）。修正前比真炮口**偏右 6.540px、偏上 80.771px**（豌豆从**头顶上方**出膛）；炮口点由 barrel 轨美术独立反推 `(88.552, 30.2)`，与植物侧标定差 **0.0000px**；静态值在参考帧 bf=0 离线 **0.000004px**，Idle 段实测最大离线 **10.86px**（头在摆）⇒ 每帧由插件覆写（§2.7.14） |

包内 **14** 个条目：

```
mod.json
Resources/Animations/SuperGatlingPea.dat                                         ← 皮肤三件套①（自包含图集，图片塞在里面）
Resources/Animations/SuperGatlingPea.tres                                        ← 皮肤三件套②（29 图层 / 24 媒体 / 3 clip）
Resources/Animations/SuperGatlingPeaAtlas.png                                    ← 皮肤三件套③（图集 PNG，仅供人看/校验）
Resources/Cards/ZombieSuperGatlingPaper.tres                                     ← 注册卡片
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Armor/Config/ZombieSuperGatlingPaperArmorPaper.tres   ← 护具槽（500 血）
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Armor/ZombieSuperGatlingPaperArmorData.tres          ← 护具表（6 项）
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Config/TowerDefenseZombieSuperGatlingPaper.tres
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Packet/ZombieSuperGatlingPaper.tres
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Scene/ZombieSuperGatlingPaper.tscn
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Scene/ZombieSuperGatlingPaperComponentSet.tres
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Scene/ZombieSuperGatlingPaperFireComponentDefinition.tres
Resources/Characters/Zombies/ZombieSuperGatlingPaper/Sprite/ZombieSuperGatlingPaper.tscn
Runtime/ModAssembly.dll                                                          ← 托管插件 24,064 B、sha256 `e28f38d73c0f84e4`（含共用判定核心 + 本地位姿渲染兜底 + 影子→可见头每帧同步 + **子弹生成点每帧对齐炮口** + 开火动画）
```

---

## 2. 设计总纲：一条数据 + 一个插件

### 2.1 纯数据为什么发射不出「1.5 秒 / 7 颗 / 10% / 300 颗 / ±15°」

**证据 1 —— 发射配置字段全集（只有 8 个）**
`Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs`

```
checkProjectileId / firePosId / speed / dir / offsetLine / fireNumSkip / fireEventNeed / projectileFlip
```

**没有任何概率、随机角、时窗、颗数字段。** 离线闸门第 8a 节拿反射把类的
public 成员列全（13 个，其中 6 个是 Godot 基类自带的 `ResourceName/ResourcePath/…`），
并用「禁用词表」反证没有任何 `chance / probability / random / angle / duration / window` 成员。

**证据 2 —— 原生发射节拍不是固定 1.5 秒，而且「无目标不发」**
`FireComponent` 的自发发射链路是
`IdleProcessing`（`:3124`）→ idle fire check（`:3164`）→ `SetFireState(Attack)` → 动画事件 `fire`
→ `AnimeEvent` → `FireConfiguredVolley`（`:3413`）。
节拍由**动画长度**决定，而 idle fire check 只在**有目标**时通过。
⇒ 需求 3 要的「固定 1.5 秒 / 恰好 7 颗」它做不到。
⚠️ 但**那道「有目标才过」的闸门正是需求 12 要保留的行为** —— 插件把它原样搬进了自己的节拍里，
所以本包最终表现是「**插件控节奏 + 引擎那套目标判定**」，不是「无条件开火」（§2.6③）。

**证据 3 —— `Fire()` 是 public 且不受状态机约束**（这就是我们的出路）
`FireComponent.cs:3429` `public void Fire()` → `:3434` `private void Fire(bool playAudio)`
第一句（`:3436`）：

```csharp
if (!base.CanExecuteGameplay || !alive || !GodotObject.IsInstanceValid(parent)
    || !GodotObject.IsInstanceValid(parent.instance)) { return; }
```

`CanExecuteGameplay => IsInsideComponentBattlefield`（`CharacterComponentRuntime.cs:86`）
—— 只要僵尸在战斗场内就能打，**与它是走、是吃、有没有目标无关**（这正是插件能自己控节奏的根据）。
⚠️ 可**用户明确要求「没有植物不攻击、进场内才攻击」**（需求 12）⇒ 插件**主动把这层自由收回**，
在每轮普攻开始前补一道与引擎同源的判定 —— 所以现在的实际行为**不是**「无条件开火」（§2.6③）。
⚠️ 它**不播开火动画、不改 sprite.timeScale、不碰状态机**，副作用只有一条：播 `fireAudioName`。

### 2.2 「打不出子弹」有**两层**原因：① 场景缺 `ComponentSet` 声明（bug，已修）② 没有开火动画（设计好的降级路径）

#### ① ★★ 场景必须显式声明 `ComponentSet` —— 本包第一版就是漏在这里（已修，必修项）

**症状**：僵尸能走、能吃、能被啃死，但**一颗豌豆都不出**；`godot.log` 里**连一条 warning 都没有**。

**根因**：基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:10` 自带

```ini
ComponentSet = ExtResource("2")     ; → TowerDefenseZombieComponentSet.tres
```

而那份组件集里有 8 个组件、**没有 FireComponent**：

```ini
; Prefab/TowerDefense/Character/ComponentSets/TowerDefenseZombieComponentSet.tres:17
Components = [Buff, GroundHeight, WaterInteraction, GroundMove, ZombieDeath, Garlic, Swim, AttackZombie]
```

子场景**不覆盖** `ComponentSet` ⇒ 继承的就是这一份 ⇒ **发射组件根本不会被创建**。整条链（源码位置已逐行核过）：

| 环节 | 位置 | 行为 |
|---|---|---|
| 声明 | `TowerDefenseCharacter.cs:703-704` | `[Export] public CharacterComponentSet ComponentSet { get; set; }` |
| 取用 | `TowerDefenseCharacter.cs:1911-1930` `EnsureComponentManagerResource()` | `ComponentSet` 有效就用它；否则回落到 `componentManager.ComponentSet`（即场景继承来的那份） |
| 创建 | `ComponentManager.cs:318-346` `InitializeResourceComponents()` | 按 `ComponentSet.GetCreationPlan()` **逐条 `entry.Definition.CreateRuntime()`** |
| 插件 | 本包 `TryHookCharacter()` | `GetRuntime<FireComponent>("character.fire")` 返回 **null** ⇒ `IsUsable()` 判否 ⇒ **静默 return**（第一版就是这样悄悄不发射的） |

组件虽然「在集里才有」，但 `OnBound()`（`FireComponent.cs:1082-1099`）才是填充发射表的地方
（`ApplyDefinitionOnce → ResolveReferences → DuplicateRuntimeResources → RefreshConfiguration`
→ `RefreshExportedArrayCaches` 把 `fireProjectileList` 拷进私有 `_fireProjectiles`）
⇒ **集里没有这个组件，后面整条链一步都不会走**。

**修法**（现在就是这样）：

```ini
; Resources/Characters/Zombies/ZombieSuperGatlingPaper/Scene/ZombieSuperGatlingPaper.tscn
[ext_resource type="Resource" path="./ZombieSuperGatlingPaperComponentSet.tres" id="15"]

[node name="ZombieSuperGatlingPaper" … instance=ExtResource("1")]
ComponentSet = ExtResource("15")     ; ★ 本包组件集 = 内置僵尸组件集(父) + 1 个发射组件
script = ExtResource("2")
```

先例：内置机枪豌豆僵尸场景 `TowerDefenseZombieNormalGatlingPea.tscn:25` 就是在自己场景里把
`ComponentSet` 覆盖成含 FireComponent 的 `TowerDefenseZombieNormalGatlingPeaComponentSet.tres`。

> ⚠️ 为什么整包仍能正常加载、只是不发射？因为 `ModLoader.InferRuntimeEntry()` 只看「路径段数 / 类别 / Key」，
> 场景**内容**它不作检查 ⇒ 这类错误**不会**在加载期报出来，只能靠运行期日志或离线闸门发现。

配套加固（`SuperGatlingPaperRuntimeEntry.cs`）：插件现在会在「认出僵尸、却拿不到 `character.fire`」时
报**一次**警告，不再静默：

```text
[SuperGatlingPaper] 找到了「ZombieSuperGatlingPaper」但拿不到组件 "character.fire"
（豌豆不会发射；僵尸仍会正常行走/啃食）。最常见原因：角色场景根节点漏了
`ComponentSet = ExtResource(…)`，于是基场景那份不含 FireComponent 的组件集生效。
```

#### ② 读报僵尸天然「打不出子弹」——这是设计好的降级路径，本包顺着它走

内置机枪豌豆僵尸能自动开火，靠的是精灵上的开火动画：

| 项 | 内置机枪豌豆僵尸 | 读报僵尸 |
|---|---|---|
| 精灵场景 | `ZombieNormalPeaShooterSingle.tscn`，`Head` 子精灵带 `HeadFire` / `HeadIdle` | `ZombiePaper.tscn` —— **只有头部插槽，没有 Head 子精灵、没有 `HeadFire`** |
| 发射配置 | `spritePath = …/Head`、`fireAnimeClips = "HeadFire"`、`isSpliceSprite = true` | 本包**不写**这三个字段 |

`FireComponent.AttackEntered()`（`:3230`）第一句：

```csharp
if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(FireRuntimeState.Idle); return; }
```

而 `CanPlayFireAnimation("")` 恒为 `false`（`private bool CanPlayFireAnimation(string clipName)` 在 `:998`，
`if (string.IsNullOrEmpty(clipName))` 在 `:1011`）⇒ **整条动画驱动发射链路必然失效**。

⇒ 结论：本包**刻意不依赖**开火动画。`fireAnimeClips` 留空、`spliceIdleAnimeClips` 留空
（后者为空时 `FireComponent` 连 `sprite.timeScale` 都不碰），
`FireComponent` 老老实实待在 Idle，豌豆**全部**由插件调 `FireComponent.Fire()` 打出去。
这同时也规避了「读报僵尸的 `.dat` 动画文件不在解包树里、无法枚举 clip 名」这个不确定性。

### 2.3 逐发改方向：为什么改 `fire.fireProjectileList[i].dir` 一定生效

看起来改不到 —— `Fire()` 内层循环读的是**私有** `_fireProjectiles`。但：

```csharp
// FireComponent.cs:443
public Array<FireComponentFireProjectileConfig> fireProjectileList = new Array<…>();

// FireComponent.cs:447
private readonly List<FireComponentFireProjectileConfig> _fireProjectiles = new List<…>();

// FireComponent.cs:919-929
private static void CopyGodotArray(Array<FireComponentFireProjectileConfig> source,
                                  List<FireComponentFireProjectileConfig> target)
{
    target.Clear();
    if (source != null)
        for (int i = 0; i < source.Count; i++)
            target.Add(source[i]);          // ★ 逐元素 Add —— 元素是**同一批对象**
}

// FireComponent.cs:965（在 private void RefreshExportedArrayCaches() 里，该方法在 :931）
CopyGodotArray(fireProjectileList, _fireProjectiles);
```

⇒ **容器不同，元素同引用**：

| 操作 | 是否生效 | 插件怎么做 |
|---|---|---|
| 改元素（`cfg.dir = 角度`） | ✅ 两个容器同时可见 | **就用这个** —— 每颗前重新取列表、重新取元素，不缓存 |
| 往 `fireProjectileList` 增删元素 | ❌ `_fireProjectiles` 不会跟着变 | 插件**绝不**增删，只改现有元素的 `dir` |

而 `Fire()` 每一发都**现场读** `cfg.dir`（`:3462`，不是缓存）：

```csharp
Vector2 velocity = fireComponentFireProjectileConfig.speed
                 * Vector2.FromAngle(Mathf.DegToRad(fireComponentFireProjectileConfig.dir));
```

⚠️ `DuplicateRuntimeResources()`（`:1259`）虽然会 `Duplicate(deep:true)`，但被 `_runtimeResourcesIsolated`
守卫、只在组件装配期跑一次，运行期不会把对象换掉。

### 2.4 插件的节拍设计

```
每帧（SceneTree.process_frame）
  └─ OnProcessFrame()
       ├─ gap = now - lastFrame；stalled = gap > 250ms
       ├─ AdvanceAll(now, stalled, gap)
       │    └─ 每只僵尸：stalled 时三条时间轴整体 += gap（★ 暂停/长卡顿不补发）
       │         ├─ BurstActive ? AdvanceBurst : AdvanceNormalAttack
       └─ 每 10 帧 ScanScene()  ← 发现自己人（config.name 匹配）+ 补卡库
```

| 阶段 | 规则 |
|---|---|
| 普攻 | 周期起点（`NextAttackMsec`，步长 1500 ms）打第 1 颗，之后每 100 ms 一颗 ⇒ 恰好 7 颗（0.0 ~ 0.6 s） |
| 大招判定 | **只在普攻周期起点**掷一次 `Randf() < 0.10`（用户选择「每次攻击」= 每轮开火） |
| 大招 | 第 k 颗的计划时刻 = `BurstStartMsec + k × (5000/300)` ms（k 从 1 数）⇒ **恰好 300 颗 / 恰好 5 秒**，无浮点累加漂移 |
| 大招期间 | **暂停普攻**（用户选择）；结束后重新起算 1500 ms |
| 计时基准 | `Time.GetTicksMsec()`（毫秒墙钟），与帧率、攻速加成无关 |
| 音效 | 普攻开 `fireAudioName = "ProjectileThrow"`；大招期间置空静音（300 颗 5 秒 ≈ 60 次/秒的爆音） |
| 掉帧保护 | 每帧最多补 12 颗（`MaxPeasPerFrame`），避免雪崩式创建子弹对象 |

> ⚠️ 刻意**不用**「7 颗一轮 × 43 轮 = 301 颗」那一套（上一版植物 Mod 的做法）：那次是因为「一轮 7 颗」
> 是原子行为、无法只发半轮；本合同没有这个约束（逐颗发射），所以能做到**恰好 300 颗**。

---

### 2.5 外观：读报僵尸的身体 + 超级机枪射手的头（2026-09-22）

用户需求：**以读报僵尸为原型，把头部换成「超级机枪射手」的头，补充适量细节与微调，确保风格与原游戏一致。**

**做法 = 抄官方自己的「僵尸身 + 机枪头」范式，零自制素材。**

先例就在眼皮底下：`Asset/Anime/Character/Zombie/Chapter2/Zamboni/Sprite/GatlingPea/ZombieZamboniGatlingPea.tscn`
—— 根节点是 `ZombieZamboni`（`flashAnimeData` 指**僵尸自己**的 `ZombieZamboni.tres`），
外面挂一个 `type="Node2D"` 的 **`Head` 子节点**，`flashAnimeData` 指**内置的**
`Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tres`，并用
`parentSprite = NodePath("..")` + `followParentSpriteLayerId` + `insertLayerId` 把头**插进身体的图层序列**。

⚠️ **但「一个 `Head` 子节点」这个形状本身是错的**（2026-09-22 晚实机发现，详见 §2.7）：
头挂在身体下 ⇒ 被引擎「父代画」⇒ `forceLocalRender` 失效 ⇒ 头的切片被拿去采样**全局共享大图**
⇒ 画出来是一团**别的角色的图集碎片**。修法 = 改成**三节点**：

本包的产物精灵场景（`…/Sprite/ZombieSuperGatlingPaper.tscn`，**7,131 B**，先前冻结版 7,215 B / 单节点版 4,110 B）：
> ⚠️ 下面标 ★ 的行是**本版（改版 B）实际会写出来的**；标 ⌫ 的行是改版 A 有、本版**已撤掉**的
> （列出来是为了让你知道「回退掉的是什么」，以及重新打开开关时该有什么）。

```ini
[ext_resource type="PackedScene" path="res://…/Zombie/Chapter1/Paper/ZombiePaper.tscn"             id="1_game_sprite"]
[ext_resource type="Script"       path="res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs" id="2_head_script"]
[ext_resource type="Resource"     path="../../../../../Resources/Animations/SuperGatlingPea.tres"   id="3_head_data"]

[node name="ZombieSuperGatlingPaperSprite" instance=ExtResource("1_game_sprite")]
Animation/Clip = "Idle"
Animation/LayerVisible/anim_hair        = false      # ← 藏掉原版头的 7 层（15~21）
…（anim_head1 / anim_head_look / anim_head_pupils / anim_hairpiece / anim_head_jaw / anim_head_glasses）

# ① 位姿影子：身体的**直接子精灵**，不可见 + 29 层全 false。
#    唯一作用 = 吃 UpdateChild() 每帧写的「被跟随层 pose.Origin + 父 offset」。
[node name="HeadShadow" type="Node2D" parent="." node_paths=PackedStringArray("parentSprite")]
visible        = false                        # ★ 它会被身体代画；不可见 + 全层关 ⇒ 零切片
scale          = Vector2(-1, 1)
script         = ExtResource("2_head_script")
flashAnimeData = ExtResource("3_head_data")
offset         = Vector2(-59.9377, -10.0515)   # ★ 与可见头**逐字相同**
offsetRotate   = 0.0                          # ★ 基准倾角，必须 0（非零会让 offset 失效）
# ⌫ usePos = true / useRotate = false / rotation = 0.0 —— 改版 A 的冻结三行，改版 B 已撤掉
trueFrameRate  = 180
parentSprite   = NodePath("..")               # ★ 只有它能吃到引擎定位
Animation/Clip = "HeadIdle"
Animation/LayerVisible/<29 个图层名> = false   # ★ 全 false
Animation/MediaReplace/<24 个媒体名> = null
Layer = 16
insertLayerId = 16                            # 插在读报僵尸 anim_head1(16) 之后
followParentSpriteLayerId = 16                # 跟随 anim_head1(16)

# ② 普通 Node2D（identity）—— 打断「父代画」的那层容器。
#    身体扫到它时 collectSpriteChildren 已是 false ⇒ 里面的精灵不被收集。
[node name="HeadHolder" type="Node2D" parent="."]

# ③ 可见头：挂在容器下 ⇒ 独立渲染 ⇒ 用它自己那张纹理数组（page 0 = 皮肤图集）。
#    不写 parentSprite / insertLayerId / followParentSpriteLayerId / position / visible。
[node name="Head" type="Node2D" parent="HeadHolder"]
unique_name_in_owner = true
z_index        = 1                            # ★★ 层级：排序键第一位是 ZIndex ⇒ 压在身体与报纸之上
scale          = Vector2(-1, 1)               # 僵尸朝左 ⇒ 头部动画镜像
script         = ExtResource("2_head_script")
flashAnimeData = ExtResource("3_head_data")   # ★ 必须在所有 Animation/LayerVisible/* 之前
offset         = Vector2(-59.9377, -10.0515)   # ★ 唯一对位真源（check_head_fit.py 反解）
offsetRotate   = 0.0                          # ★ 同上：基准倾角 0
# ⌫ usePos = true / useRotate = false / rotation = 0.0 —— 改版 A 的冻结三行，改版 B 已撤掉
trueFrameRate  = 180
Animation/Clip = "HeadIdle"                   # ★ 必须写 Animation/Clip，不能写裸 `clip`（见 §2.6②）
Animation/LayerVisible/<29 个图层名> = true    # ★ 全 true
Animation/MediaReplace/<24 个媒体名> = null
```

> ⚠️ **两个头都不写 `position` / `visible`** —— 影子的 `position` 由 `UpdateChild()`（`:5259-5281`）每帧改写，
> 可见头的由**插件每帧从影子同步**（`SyncHeadPairs()`）。
> ⚠️ **改版 B 起 `rotation` 也不许写**（改版 A 曾允许，前提是同块有 `useRotate = false`）：
> 现在两个 `[Export]` 开关都是默认 `true` ⇒ 引擎每帧覆写 `Rotation` ⇒ 单独留一行 `rotation`
> 是**死值**，只会在下次改的人眼里冒充「有个角度在起作用」。生成器的自检直接禁掉这三行。
>
> 生成器的自检里有一组反向断言：可见头块内**不许**出现 `parentSprite` / `insertLayerId` /
> `followParentSpriteLayerId` / `position =` / `visible =`；`usePos` / `useRotate` / `rotation`
> 两个头**都不许**出现；`z_index` 则**必须**有且只能出现在可见头上。

关键设计（逐条有依据）：

| 决定 | 值 | 依据 |
|---|---|---|
| 头用哪份动画数据 | **包内** `Resources/Animations/SuperGatlingPea.tres` | 与官方 `ZombieZamboniGatlingPea` 同一手法（僵尸身 + 植物头）⇒ 画风必然一致；但用户指定要**超级机枪射手**而非机枪射手，所以走「把皮肤三件套复制进包」（§2.6①） |
| **为什么是三个节点而不是一个** | `HeadShadow` + `HeadHolder` + `Head` | ★★ 头挂在身体下会被「父代画」⇒ `forceLocalRender` 失效 ⇒ 采样全局共享大图 ⇒ 碎片拼贴。完整链条见 §2.7 |
| 影子 `insertLayerId` / `followParentSpriteLayerId` | `16` | 读报僵尸 `ZombiePaper.tres` 的 `layerDictionary` 里 `anim_head1 = 16`（脖子那层）⇒ 影子跟它 ⇒ 位置与原头一致 |
| 可见头为什么要另起一格 | `HeadHolder`（普通 `Node2D`） | `CollectOwnedChildBindings` 递归到「非精灵但有子节点」的中间节点时，`collectSpriteChildren` 传的是 `ownerSlot != null` = **false** ⇒ 普通容器下面的精灵**不被收**（`AdobeAnimateSprite.cs:5397`） |
| 身体要藏掉哪几层 | `15,16,17,18,19,20,21` | 分别对应 `anim_hair` / `anim_head1` / `anim_head_look` / `anim_head_pupils` / `anim_hairpiece` / `anim_head_jaw` / `anim_head_glasses`。不藏的话**原版读报僵尸的头会从头盔底下透出来**（7 层照原样叠画） |
| 身体其余层 | `0`（`_ground`）与 `24`（`AnimeClips`）关，`1~14` 全开 | 与内置 `ZombiePaper.tscn` 的取景一致 |
| `offset` | `(-59.9377, -10.0515)` | ★ **唯一对位真源**（影子的 `Position` = 被跟随层 pose.Origin + 父 `offset`）。旧值抄的 `(-36,-46)` 是**植物体内** Head 的值。**与旋转 / 平移量耦合** ⇒ 改 `HEAD_FIXED_ROT_DEG` 或 `HEAD_PLACE_SHIFT` 都要重解：`python .cache/head_place.py [--shift=8,-4] [--node-rot-degs=<角>]`（§2.7.10④ / §2.7.13②）。两个头必须**逐字相同** —— 只要相同，「可见头」与「影子若可见」的渲染结果就完全一致 |
| `usePos` / `useRotate` / `rotation` | **三行都不写**（2026-09-23 改版 B 回退） | ★★ 见 §2.7.13①：三行都不写 ⇒ 两个 `[Export]` 开关回默认 `true` ⇒ 引擎每帧覆写 `Position`/`Rotation` ⇒ 头**跟 `anim_head1` 摆动**（Idle −16.03°..+1.01°）。改版 A 曾写 `true` / `false` / `0.0` 把它冻成常量（§2.7.10②③，留档）；生成器把开关 `HEAD_FIX_HEAD_ROTATE` 设回 `True` 即可一键切回 |
| `z_index`（仅可见头） | `1` | ★★ 见 §2.7.10⑤：全局排序键第一位是 `ZIndex`（`AdobeAnimateSortPath.cs:37-48`），`EffectiveZIndex` 沿父链累加 Godot `z_index`（`AdobeAnimateSprite.cs:6513-6531`）⇒ 比身体高 1 ⇒ 一定后画。影子**不写** |
| `offsetRotate` | `0.0` | ⚠️ **改版 B 起它又"生效"了**（跟随口径下它加在 net 旋转上）—— 正因如此更要钉死 0：它是头的**基准倾角**，非零 ⇒ `HEAD_OFFSET` 立刻失效。生成器自检 + `.cache/check_head_fit.py` 都会拦非零值。改版 A 时它则是**彻底不读**的死配置 |
| `trueFrameRate` | `180` | 内置 `GatlingPea.tres` 头部动画的帧率（身体那套是 12） |

**收益**：完全不需要自制贴图或动画 ⇒ 不存在「画风不像」的问题，也不需要动
`.dat` / 图集 / `skin_params.json` 那条重管线（那条只有**植物版**才走，见《换贴图换动画指南》）。

> ✅ 头顶用的是包内超级机枪射手皮肤的头段（`HeadIdle(25,49)` / `HeadFire(50,86)`）。
> 读报僵尸本身没有 `HeadFire`，发射完全由插件按毫秒节拍驱动（见 §2.2②），
> 所以**开火动画由插件自己接**：`FirePea()` 每打出一颗豌豆就把可见头切到 `HeadFire`
> 并把窗口续到 `now + 220ms`，窗口过后 `ExpireHeadFire()` 切回 `HeadIdle`
> —— 于是连发 7 颗（0/100/…/600ms）与 5 秒大招都表现为「整段保持开火姿势」，且整段只重头播一次。
> 详见 §2.7③。

---

## 2.6 ★ 三条修正（2026-09-22 二次改版）

用户原话（一次收到三条）：

> 「你这头为什么这么不协调，而且我要你用的头部贴图是**超级机枪射手**的头部贴图，
> 而不是**机枪射手**的头部贴图，而且**植物僵尸的攻击判定你也没有加**（没有植物不攻击，进场才攻击）。」

### ① 头部素材：内置根本没有「超级机枪射手」

先把事实摆出来 —— **内置素材库里不存在「超级机枪射手」这个植物**：

```
Asset/Anime/Character/Plant/**/ 下与"机枪"相关的只有 8 个：
GatlingPea / GatlingPeaZ / GatlingCat / GatlingPot / CatGatlingPea /
GatlingCabbage / DisguiserGatling / Item_GatlingTX
```

`.cache/check_head_fit.py` 与生成器自检都会在包内查找 `res://Asset/Anime/Character/Plant/…` 的引用并**报错**，
防止回退到内置机枪射手。唯一合法来源是**本工坊自己的植物包**，所以做法是：

> 把 `SuperGatlingPea.{tres,dat}` + `SuperGatlingPeaAtlas.png` **三件套复制进本包**
> `Resources/Animations/`，`Head.flashAnimeData` 指向**包内的** `../../../../../Resources/Animations/SuperGatlingPea.tres`。

三条必须同时满足的硬约束：

| 约束 | 原因 |
|---|---|
| `.dat` 必须与 `.tres` **同目录** | `.tres` 里写的是 `animeFile = "./SuperGatlingPea.dat"`（standalone，相对本文件） |
| 三件套**必须各自完整**，`.pmod` 之间不能互相引用 | 每个包独立解到 `user://ModsCache/<包名>/`，植物包的文件在僵尸包里**看不到** |
| `mod.json` 的 `resources` 要**逐条列出**这 3 个新文件 | 引擎按 `resources` 建索引；漏了就等于没打进包 |

### ② 头对位：`offset` 是**唯一**真旋钮（顺带纠正一条被源码推翻的旧结论）

**旧结论（错）**：「抬高头就改 `Head.position.y`，**绝不能动 `offset`**，否则 `Marker2D` 炮口会跟着跑偏。」

源码事实 —— `AdobeAnimateSprite.UpdateChild()`（`addons/AdobeAnimateEditor/Node/AdobeAnimateSprite.cs:5255-5281`）：

```csharp
if (adobeAnimateSprite.usePos)                       // usePos 默认 true（:276）
{
    Vector2 vector = transform3.Origin + offset;      // ★ = 被跟随图层的 pose 原点 + 父精灵的 offset
    if (adobeAnimateSprite.Position != vector) { adobeAnimateSprite.Position = vector; … }
    if (adobeAnimateSprite.useRotate)                 // useRotate 默认 true（:279）
    {
        float num3 = (float)(transform3.Rotation + adobeAnimateSprite.offsetRotate);
        adobeAnimateSprite.Rotation = num3;           // ★ 单位 = 弧度（曾误记为「度」，见 §2.7.10）
    }
}
```

⇒ 结论两条，正好各自纠正一半：

1. **`Head.position` 是死值**，每帧被覆盖。官方样本自己也写了
   （`ZombieNormalGatlingPea.tscn` 的 `Head.position=(-22.221416,-76.32331)`、`rotation=-0.15840983`），
   同属编辑器残留 ⇒ 想调头位**只能改 `offset` / `offsetRotate`**。
   ⚠️ **`rotation` 有例外**：把 `useRotate` 关掉之后它就不是死值了（§2.7.10，2026-09-23 新增）。
2. **`offset` 不影响 `Marker2D`（炮口）**。`offset` 只作用于**本精灵自己那份美术**
   （`:7044`/`:7071`/`:7362` `transform = transform.Translated(offset)`）与子精灵落位；
   `FireMarker` 是场景里 `HeadSlot` 的独立子节点，跟 `Head.offset` 没有任何关系。

**新值怎么来的**：跨素材拼装（僵尸身 + 植物头）**必须重标定**，不能照抄别处的值。
`.cache/check_head_fit.py` 按引擎变换解：

```text
offset = A⁻¹ · ( 原头中心 − ( A·头块中心 + node ) )
A = [[cosθ·sx, −sinθ·sy], [sinθ·sx, cosθ·sy]] ，θ = 被跟随层 rotation + offsetRotate
node = 被跟随层 pose.Origin + 父精灵 offset
```

输出（局部，逐字，**2026-09-23 改版 B：跟随摆动 + 屏幕位移 (+8,−4)**）：

```
⇒ 与官方手调值 (-58,-5) 相差 4.61 px（阈值 6.0）        ← 官方样本交叉校验（与本包口径无关，长期不变）
   （`offsetRotate = -0.25` 是**弧度** ⇒ -14.324°；按「度」读会得到 3.96px 的假值）
★ 反解 offset = (-59.9377, -10.0515)      [原头中心 + shift(+8.00, -4.00)]
生成器 HEAD_OFFSET      = (-59.9377, -10.0515)
生成器 HEAD_PLACE_SHIFT = (8, -4)
口径 = 跟随 anim_head1（net -8.06° @ frame0）
差 = 0.000009 px（阈值 0.001）
落点核对：屏幕位移 (+8.0000, -4.0000) 与 HEAD_PLACE_SHIFT 差 0.000009px（<=0.001）
          覆盖原头面积比例 0.951（>=0.60）
回退核对：HEAD_FIX_HEAD_ROTATE=False ⇒ 头跟 L16 摆动，Idle 净旋转 -16.03°..+1.01°（25 帧）
负向：(-36,-46) 位移误差 43.19px／(-49.07,-5.24) 11.89px／(-54.19,-10.11) 5.75px／
      纯几何 (-51.46,-7.21) 8.94px／★方向坑（shift 直接加在 offset 上）8.94px（均 >0.001 ⇒ 正确失败）
PASS 换头对位反解与生成器常量一致（官方样本交叉校验 + 单位负向 + 屏幕位移逐字核对 + 覆盖率 + 5 条历史/方向负向）
```

**40.24 px** 这个数字与用户截图里的「头悬空错位」量级吻合 —— 旧值是植物体内 `Head` 的 `(-36,-46)`，
对它自己的身体成立，对读报僵尸的身体不成立。

### ③ 攻击判定：没有植物不攻击、进场内才攻击

用户要的这两条，**引擎本来就有一份实现**（原生发射链 `idle fire check`，见 §2.1 证据 2）。
本包因为**绕开了状态机自建节拍**，把这道闸门一起绕掉了 ⇒ 实测日志里的直接后果是：

```
[Mod:supergatlingpaper] 已挂上第 1 只「ZombieSuperGatlingPaper」的发射组件。
ERROR: [BulletField:E_MAP_BOUNDS_UNAVAILABLE] projectile map bounds are unavailable
   at: Godot.Rect2 FireComponent.ComputeProjectileMapRect()
   … [3] FireComponent.Fire(bool)  [4] SuperGatlingPaperRuntimeEntry.FirePea(…)
ERROR: [BulletField:E_FIELD_UNAVAILABLE] projectile='Pea' reason='BulletField could not be mounted'
```

（`logs/godot.log`，2026-09-22）—— **在没有 BulletField 的地方也硬开火**（图鉴/预览这类没有战场的场景），
弹丸创建直接报错。修法就是让插件复用引擎那套判定：

```csharp
// SuperGatlingPaperRuntimeEntry.cs：每轮普攻起点先问一次
private bool HasFireTarget(FireComponent fire)
{
    var checks = fire.fireCheckList;                       // 数据侧第一条 check
    var data = checks[0].GetProjectile();                  // projectile 无效时自己返回 null
    return fire.CanFireCheckOnceByData(data);              // ★ 引擎判定
}
```

`CanFireCheckOnceByData()` 里就含用户要的两条：

| 用户要的 | 引擎里的位置 | 行为 |
|---|---|---|
| **进场内才攻击** | `FireComponent.cs:1766`：`parent.GetLogicalGlobalPosition().X > groundRight ⇒ false` | `groundRight = GetMapGroundRight() + gridSize.X × offscreenTargetMarginColumns`（余量默认 1 列）⇒ 僵尸从屏幕右侧外出生、还没走进场地时判定失败 |
| **没有植物不攻击** | `CheckTarget(...)`（`:1808`）→ `HasOpposingFireCandidates`（`:1862`）→ 逐条 `CheckRayHit`（`:1836`） | 同队列没有对立阵营候选 ⇒ false；本包射线 `AabbRay2DResource_backward`、`TargetPosition=(-2000,0)` ⇒ **只打正前方同一行 2000px 内的植物** |

三条刻意的取舍（都写进源码注释，免得以后被当 bug 改掉）：

1. **只挡「开启新一轮」**，连发链已经开始的 7 颗会打完 —— 与引擎「一轮打完才重新判定」一致；
2. 判定不通过时把节拍推成 `NextAttackMsec = now + interval`（**用 `=` 不用 `+=`**）——
   否则僵尸站着不动时会攒下一串欠账，一有植物进场就把攒的十几轮一次性砸出去；
3. **判定本身抛异常时放行**（返回 `true`，只报一次日志）—— 宁可多打一颗，也不要让僵尸变成站着不还手的靶子。

⚠️ 用 `CanFireCheckOnce*` 而**不是** `CanFire`：后者多一道 `timer > 0f`（`:1738`），那是引擎状态机的冷却，
本插件绕开了状态机，`timer` 归不归零不可控。

---

### 2.7 ★★★ 头的碎片拼贴：子精灵必被父代画 + 图集错位（2026-09-22 晚三改）

用户实机截图（`QQ_1790080152667.png`）：读报僵尸头顶糊着**一团彩色碎片**——蓝白菱形、黄橙块、
紫块、青蓝小方块、白豌豆、橙点。既不是机枪射手，也不是超级机枪射手，而是**一堆别的角色的图集碎片**。
同一份皮肤放进植物包却完全正常。这一节把这个差异钉死。

#### 2.7.1 症状的形态学：碎片来自哪张图

碎片**不是随机噪声**，它们是**同一张图上不同区域的内容**——这说明采样用的纹理**是对的**（存在且已加载），
只是**被采样的矩形算错了**。所以问题不在「图集丢了」，而在「**拿哪本图集算矩形**」。

#### 2.7.2 根因链条（逐条源码实锤）

```text
① CollectOwnedChildBindings（AdobeAnimateSprite.cs:5365，判定 :5385）
   只按 Godot 节点类型收集子精灵，完全不看 parentSprite。
   ⇒ 头只要是身体的（直接）子精灵，就被收进 _spriteChildren / _insertedSprites。
      （对「非精灵但有子节点」的中间节点会递归，但那一刻传
        collectSpriteChildren = (ownerSlot != null)  ⇒ 普通容器下面的精灵不再被收，:5397）

② ⇒ OwnsSpriteChildForRender（:7774）true ⇒ IsRenderedByParentSpriteForRender（:9559）true
   ⇒ _Draw()（:9534）第一行就 return。
   ⇒ 头自己的 forceLocalRender 永远走不到 —— 它只在 :9549 / :9551 被读，
     而那两行在 return 之后。

③ ⇒ 头切片改由身体的渲染批次代画（AppendChildSprites，:833）
   + TryGetChildRenderLayerForRender（:7986）里的 ResolveSpriteChildInsertLayer（:7998）
     「不返回 -1」⇒ 整批共用身体那一张纹理数组。

④ 自制皮肤不在全局图集清单里
   （RefreshAtlas :3489 是**构建期**才写 res://…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres）
   ⇒ MediaAtlasPages 解析不到 ⇒ 落 BaseAtlasPage = 0
     （AdobeAnimateDrawItemBuilder.ResolveMediaRect:921）
   ⇒ 采样 AdobeAnimateVisualTextureArray.png（**全部角色拼一张**）
   ⇒ 画出来的就是别的角色的碎片拼贴。
```

**一句话**：头挂身体下 ⇒ 引擎按「父代画」走 ⇒ 头部切片被迫去用身体那份 definition 的图集映射
⇒ 而自制皮肤没有全局图集映射 ⇒ 回落到 0 号共享大图。

#### 2.7.3 为什么植物包（`植物Mod-超级机枪射手`）没有这个病

**纯属侥幸**：植物包的 root 与 Head **共用同一份 `.tres`** ⇒ 同一个 definition ⇒ 同一份 `MediaAtlasPages`
⇒ 哪怕真走了「父代画」，算出来的矩形也是对的。

⚠️ 反过来说：**任何「跨 `.tres` 的子精灵」都会中招**，不管它是植物还是僵尸。
这条限制是引擎级的，不是本包特有的。

#### 2.7.4 ⚠️ 两个「看起来能躲」但躲不掉的写法

| 想法 | 为什么不成立 |
|---|---|
| 「把头写成 `insertLayerId = -1`，它就不插到父批次里了」 | `ResolveSpriteChildInsertLayer`（`:8039`）对 `-1` **回落顶层**，不是「不插入」 |
| 「把头挂到 `TransformPoint` 之类的兄弟节点下就行」 | `ResolveSpriteChildFollowLayer` **优先读子精灵自己的** `followParentSpriteLayerId`（=16）⇒ 取到的是**身体图层 16**，而 `CollectOwnedChildBindings` 判「是否子精灵」时**穿过**非精灵容器（`:5397` 只在「中间节点有 ownerSlot」时截断）⇒ 依旧被父代画 |

⇒ 唯一能真正断开的，是**让头不再是身体的子精灵**。

#### 2.7.5 修法：换头「三节点」

数据侧（`build_zombie_super_gatling_paper.py::sprite_scene_tscn()`）改成三层：

```text
ZombieSuperGatlingPaperSprite          （内置僵尸 Sprite 实例，身体）
├── HeadShadow  type="Node2D"          ① 位姿影子：身体的直接子精灵
│                                        visible = false + 29 层全 false
│                                        parentSprite = NodePath("..")
│                                        Layer = insertLayerId = followParentSpriteLayerId = 16
├── HeadHolder  type="Node2D"          ② 普通容器（identity ⇒ 与身体同一坐标系）
│   └── Head    type="Node2D"          ③ 可见头：HeadHolder 的子精灵，独立渲染
                                          29 层全 true、不写 parentSprite / insertLayerId /
                                          followParentSpriteLayerId / position / rotation / visible
```

三者分工：

| 节点 | 作用 | 关键点 |
|---|---|---|
| **`HeadShadow`** | 唯一作用 = 吃 `UpdateChild()`（`:5208-5286`，定位段 `:5259-5281`）每帧写的 `Position = 被跟随层 pose.Origin + 父 offset` / `Rotation = pose.Rotation + child.offsetRotate` | ① 该循环**没有可见性判断** ⇒ `visible=false` **不拦截**定位；② 层全 false ⇒ **零切片** ⇒ 不会产生任何碎片；③ 它仍是「身体的子精灵」⇒ 父代画照常，但**没有东西可画** |
| **`HeadHolder`** | 打断「父代画」的容器 | 必须是 identity（不写 position/rotation/scale），否则坐标会再叠一层 |
| **`Head`** | 真正被看到的那个头 | 29 层全 true ⇒ 引擎走自己的 `_Draw()`（`GetSpriteChildrenForRender()` `:7486` 只返回收集表）⇒ 独立渲染 ⇒ 用**自己 definition** 的 `MediaAtlasPages` ⇒ 图集映射正确 ⇒ 能播 `HeadFire` |

**为什么头不是身体的子精灵、却仍能被引擎定位？**
`UpdateChild()` 的 `ResolveSpriteChildFollowLayer` 最终用 `_parentSprite`（= `FindParentSpriteAncestor():7797`，
**最近的祖先精灵**）⇒ 可见头挂在 `HeadHolder` 下**仍**能解析到 `_parentSprite`（因为 `HeadHolder` 不是精灵）
⇒ `TryGetInterpolatedLayerPose` 成功。所以引擎**照旧**会把位姿写进 `Head` —— 但这一步不重要，
因为可见头的落位由插件同步，且两个头的 `scale` / `offset` / `offsetRotate` **逐字相同**
⇒ 渲染结果与「影子若可见」完全一致。

⚠️ 两个头的 `scale` / `offset` / `offsetRotate` 必须**逐字相同**
（**2026-09-23 改版 B**：`Vector2(-1,1)` / `Vector2(-59.9377,-10.0515)` / `0.0`）——
只要这几项相同，「可见头」与「影子若可见」的渲染结果就完全一致。这是闸门里的一组断言（§8.1）。
⚠️ **改版 B 起 `usePos` / `useRotate` / `rotation` 两个头都不写**（改版 A 曾写 `true` / `false` / `0.0`）——
见 §2.7.13①。

**官方先例**：引擎自带 `Test/AdobeAnimateDetachedChildOwnershipProbe.cs` 就是专门验证「脱离父精灵的子精灵所有权」这个形状的。

#### 2.7.6 插件侧：影子 → 可见头 每帧同步

可见头独立渲染后，「谁去驱动它」这件事落回插件身上（`SuperGatlingPaperRuntimeEntry.cs`）：

```csharp
private sealed class HeadPair { public AdobeAnimateSprite Shadow; public AdobeAnimateSprite Visible; }
private readonly List<HeadPair> _headPairs = new List<HeadPair>();
private const int ScanIntervalFrames = 10;   // 登记节拍

// OnProcessFrame：AdvanceAll(...) 之后、ScanIntervalFrames 早退**之前**
SyncHeadPairs();     // ★ 必须每帧跑；process_frame 早于节点 _process ⇒ 1 帧延迟
```

- **登记**：`ScanRecursive` 的精灵分支里 `TryRegisterHeadPair(animeSprite)`，每 `ScanIntervalFrames` 帧扫一次。
- **同步**：`SyncHeadPairs()` 把 `Shadow.Position / Rotation / Scale` 拷给 `Visible`（逐帧）。
  低速动画下 1 帧延迟远小于 1px，肉眼不可见。
- 未登记 / 已销毁的用 `IsLiveSprite()`（static）剔除，避免引用到已释放节点。

#### 2.7.7 顺带把「射击动画」接上（用户明确要的第二件事）

僵尸原本**不播开火动画**（内置僵尸 Sprite 无 `HeadFire` 轨），此前是这份皮肤的已知取舍。
现在可见头独立渲染 + 有 `HeadFire(50,86)` 轨 ⇒ 可以播了：

```csharp
private const string HeadClipName     = "HeadIdle";
private const string HeadFireClipName = "HeadFire";
private const ulong  HeadFireWindowMsec = 220;   // HeadFire 37 帧 ÷ trueFrameRate 180 ≈ 206ms

// FirePea() 每打一颗 → MarkHeadFire()
hook.HeadFireUntilMsec = now + HeadFireWindowMsec;   // 续窗口
SetHeadClip(hook, HeadFireClipName);
// 每帧 ExpireHeadFire()（AdvanceAll 之后）：窗口过了 ⇒ SetHeadClip(hook, HeadClipName)
```

- `SetHeadClip()` **只在 clip 真的变化时才调 `SetClip()`** ⇒ 7 颗连发（0/100/…/600ms）与
  300 颗/5s 大招都表现为「**整段保持开火姿势**」且只重头播一次，不会卡成逐帧抖动。
- 220ms 依据：`HeadFire` 37 帧 ÷ `trueFrameRate 180` ≈ 206ms（留一点余量）。

#### 2.7.8 同时修掉的三个连带坑

| 坑 | 症状 | 修法 |
|---|---|---|
| `TryEnforceHeadSwap` 按「clip ≠ `HeadIdle` 就纠」 | 会把开火窗口**腰斩**（刚切 `HeadFire` 就被纠回 `HeadIdle`） | 改成「**既不是 `HeadIdle` 也不是 `HeadFire` 才纠**」 |
| `TryEnforceHeadSwap` 找身体用 `sprite.GetParent() as AdobeAnimateSprite` | 可见头挂在 `HeadHolder` 下 ⇒ `null` ⇒ **静默失效** | 新增 `ResolveBodyForHead()`：快路径「`HeadHolder` 的父」，兜底「沿祖先链找最近精灵」 |
| `TryPatchSkinRender` 给所有精灵打 `forceLocalRender` 标 | 给 `HeadShadow` 打标**无意义**（零切片）且只刷日志 | 开头 `if (sprite.Name == HeadShadowNodeName) return;`。⚠️ 更根本的是**这一招必须配合三节点才有效**，否则 `_Draw` 在读到 `_forceLocalRender` 之前就 return（§2.7.2 ②） |

⚠️ `ResolveHeadForFire()` 找可见头：`fire.Owner as Node` → `FindChild("Head", recursive: true, **owned: false**)`。
`.tscn` 里新增的节点**没有 owner**，用 `owned:true` 会把它们**全部过滤掉**。

#### 2.7.9 ⚠️⚠️ 三节点修完之后仍然「没生效」—— 节点头**收尾写成了 `>`**（当晚第二次踩）

三节点结构落地、生成器自检 `fails = 0`、插件编译通过……**实机仍然不对**。原因在产物字节里：

```text
第 91 行（坏）： [node name="Head" type="Node2D" parent="HeadHolder">    ← 收尾是 `>`，不是 `]`
第 91 行（好）： [node name="Head" type="Node2D" parent="HeadHolder"]
```

Godot 的 `.tscn` 解析器**不会报错**（连 warning 都没有），只是把这一行当**普通文本吞掉**
⇒ `Head` 节点**根本没建出来** ⇒ 头上没有任何美术。

而**闸门抓住了它**（**285 PASS / 0 FAIL** 里那一条 9.12③「可见头挂在 `HeadHolder` 下」直接红）：

```text
FAIL  ★★ 换头三节点③ 可见头挂在 HeadHolder 下（**不是**身体下）
```

⇒ **闸门比生成器自检更可信**。为什么自检漏了？因为它的断言写成了

```python
if f'[node name="{HEAD_NODE_NAME}" type="Node2D" parent="{HEAD_HOLDER_NODE_NAME}"' not in sp:
```

—— **没带闭合括号**，等于把 bug 一起写进了断言里（**断言与实现同错**，典型假绿）。

修法两条，缺一不可：

1. 模板那行改成 `]`；
2. 自检加一条**通用扫描**（不再逐条写死关键词，任何节点行坏掉都会被拦）：

```python
for name, body in (("Sprite", sp), ("Scene", sc)):
    for ln in body.splitlines():
        if ln.startswith("[node ") and not ln.endswith("]"):
            fails.append(f"{name} 场景的节点头语法坏了（必须以 `]` 收尾）：{ln!r}")
```

并在负向测试里加一条反例「节点头结尾写成 `>`」（`verify_head_structure.py`，现 **15 条**）。

> ⚠️ 连带发现：`Read` 工具在**本文件**上把这一行显示成了 `…HeadHolder"]`（看着是对的），
> 而 `open(p,'rb').read()` 的十六进制显示第 91 行最后一个字节是 **`3e`（`>`）**。
> ⇒ **结构类结论一律以字节级读取为准，别拿带渲染的预览当证据。**

#### 2.7.10 ★★ 头「摆正 + 不再歪斜」+ 层级压住身体（2026-09-23 改版 A）

> ⚠️⚠️ **本节记录的是「改版 A」的做法，其中 ①②③④ 已被「改版 B」（§2.7.13）按用户要求**回退**。**
> **为什么整节保留**：① 生成器里 `HEAD_FIX_HEAD_ROTATE` 开关还在，随时可切回；
> ② 「官方 `offsetRotate = −0.25` 是**弧度**、且属**另一套美术**」这个结论是本节独有的记载；
> ③ 「`rotation` 单独写是死值」这条纪律在改版 B 里**同样适用**（甚至更严）。
> 只有 **⑤（`z_index`）在改版 B 里仍然生效**。

用户原话：

> 「请调整"超级机枪读报僵尸"的头部位置：参照示例图2，使头部**摆正、不再歪斜**，
> 并与身体的**相对位置保持一致**。同时将头部的**渲染层级调高**，确保头部显示在身体及其他
> 元素之上，避免被遮挡或出现穿插。」

##### ① 歪斜的根因：`Rotation` 被引擎每帧写成「被跟随层的姿态旋转」

`ZombiePaper.tres` 的 `anim_head1`（L16 = `Zombie_head.png`）**本身带大幅摆头**：

| clip | `anim_head1` 旋转范围 |
|---|---|
| Idle | −16.03° .. +1.01°（f0 = −8.06°） |
| Walk | −19.52° .. +23.15° |
| Eat | −27.63° .. +29.70° |

逐帧连续插值 ⇒ 头**一直在摆**。官方 `ZombieNormalGatlingPea` 跟的也是 `anim_head1`
（在 `ZombieNormal.tres` 里是 L7），它靠 `offsetRotate = -0.25`（**弧度**）凑姿态、把摆动当「自然摆头」接受。
用户要的是「不再歪斜」⇒ 只能**把 `Rotation` 冻成常量**。量化依据：`.cache/head_pose_probe.py`。

##### ② 冻结机制：引擎自带开关 `useRotate`（纯数据，不动插件）

`AdobeAnimateSprite.cs:275-282` 有 `[Export] public bool usePos = true;` / `useRotate = true;`，
而 `:5259-5276` 里 `Rotation` 的赋值**包在 `if (useRotate)` 内**、`Position` 的赋值包在 `if (usePos)` 内。

⇒ 场景里给**两个头**（影子 + 可见头）都写：

```
usePos = true
useRotate = false
rotation = 0.0
```

- `useRotate = false` ⇒ 引擎**不再改** `Rotation`，节点自写值生效 ⇒ **摆正、不再歪斜**；
- `usePos = true` ⇒ `Position` 仍每帧跟随 `anim_head1` ⇒ **与身体的相对位置保持一致**。

官方先例 14 处：`ZombieGargantuar.tscn:141`、`ZombieFootballGargantuar.tscn:109`、
`ZombieSkeletuar.tscn:105`、`ZombieGargantuarDigger.tscn:152`、`TowerDefensePlantPeaPot.tscn:53` …
运行期先例：`TowerDefenseZombieNormalSquash.cs:62-63`
（`_zombieSprite.head.usePos = false; _zombieSprite.head.useRotate = false;`）。

> ⚠️ **`rotation` 只有在同块内有 `useRotate = false` 时才不是死值** ⇒ 自检与闸门必须**成对**校验，
> 否则就是「写了等于没写」的静默失效。

##### ③ 冻在**哪个角**：`0°`，不是官方那个 −14.32°（★ 上一版在这里选错了）

三条独立证据（`.cache/_ab_angle.json`、`.cache/_native_compare.py`）：

1. **【最强】同一套头美术在植物里的原生净旋转就是 0**：植物 `Sprite/SuperGatlingPea.tscn` 的
   `Head` 节点**没有任何旋转覆写**（无 `rotation` / `useRotate` / `offsetRotate` ⇒ 默认
   `useRotate = true`、`offsetRotate = 0`）⇒ 其旋转 = 跟随层 L16(`anim_idle`) 姿态旋转 + 0；
   实测该层 **BodyIdle 全 24 帧恒为 +0.000°** ⇒ 植物头就是以 **net 0°** 渲染的，
   而用户已接受植物外观 ⇒「这套美术在 0° 时是正的」是**既成事实**。
2. 离线渲染细扫：θ 越负炮口越下垂；θ = 0 炮口水平，θ = −14.32° 明显下垂 ——
   而用户投诉的正是「下垂/歪斜」，交付 −14.32° **等于没修**。
3. 与植物卡面原生美术并排：θ = 0 的头盔/护目镜/炮口朝向与卡面一致。

> ★ 上一版错在哪：拿官方 `ZombieNormalGatlingPea.tscn` 的 `offsetRotate = −0.25` 当对齐目标，
> 但那是**另一套美术**（内置机枪豌豆僵尸），它那支枪本来就设计成略微下垂。
> **跨素材拼装的头，朝向要锚「该美术自己的原生朝向」，不能锚另一个角色的调参值。**

##### ④ `offset` 随旋转**重解**（offset 作用在节点旋转**之前**，两者耦合）

```
python .cache/head_place.py --node-rot-degs=0        # → (-54.19, -10.11)（改版 A 口径）
```

历代值（全部被 `.cache/check_head_fit.py` 的负向用例钉死）：

| offset | 出处 | 现状 |
|---|---|---|
| `(-36,-46)` | 照抄植物体内 `Head` 的 offset | ✘ 悬空（位移误差 43.19px / 覆盖原头仅 29.7%） |
| `(-51.46,-7.21)` | 跟随 `anim_head1` 时（net −8.06°）的**纯几何对齐**解 | ✘ 改版 B 里它 = **忘了加右上微移** ⇒ 位移误差 8.94px |
| `(-49.07,-5.24)` | 改版 A 之前冻在 −14.32° 的解 | ✘ 炮口下垂（锚错参照物） |
| `(-54.19,-10.11)` | 改版 A：冻在 0°（美术原生朝向） | — **已被改版 B 回退**（改版 B 下位移误差 5.75px）；留档 |
| **`(-59.9377,-10.0515)`** | **改版 B：跟随摆动 + 屏幕位移 `(+8,-4)`** | ✔ 位移误差 **0.000009px**；覆盖原头 **95.1%** |

> 四边超出从 9.79px（θ=−14.32°）降到 **3.66px**（θ=0）—— 因为 0° 时头块与原头**同朝向**，
> 包围盒不再被旋转撑大。这是「0° 才对」的第四个旁证（改版 A 的论据，留档）。
>
> ⚠️ **改版 B 换了判据**：「四边最大超出 ≤10px」这类绝对阈值在本版**不能再当门槛** ——
> 偏移是**故意**的，它只会随位移量单调变差。真正要防的是「悬空/飞出去」，改用
> **覆盖面积比例 ≥ 60%** 表达（§2.7.13③）。

##### ⑤ 层级：给可见头写 `z_index = 1`

引擎**全局**绘制排序键的第一位就是 `ZIndex`（`AdobeAnimateSortPath.CompareTo`，
`AdobeAnimateSortPath.cs:37-48`；统一排序处 `AdobeAnimateRenderManager.cs:753`），
而 `EffectiveZIndex` 就是**沿父链累加 Godot 的 `z_index`**（`AdobeAnimateSprite.cs:6513-6531`）。

⇒ 可见头写 `z_index = 1`（`z_as_relative` 默认 true ⇒ 在父级基础上再 +1）
⇒ effective z 比身体高 1 ⇒ **必然排在身体（含报纸/手臂）之后绘制**，不遮挡、不穿插。

为什么不只靠节点顺序：`HeadHolder` 排在 `GroundSlot` 之后确实已在身体之后，
但那只用到排序键的**第二位**，且依赖内置 `ZombiePaper.tscn` 的子节点次序；
写 `z_index` 把它变成对树序**不敏感**的显式保证（幂等、无副作用）。
⚠️ 影子**不写** `z_index`（它 `visible = false` 且零切片，写了无意义还会误导）。

##### ⑥ 本轮抓出的**两个假绿断言**（比 bug 本身更值得记）

改了断言之后按惯例做负向测试（篡改常量、看断言会不会响），结果**两条没响**：

| 断言 | 为什么是假绿 | 修法 |
|---|---|---|
| `HEAD_NODE_Z_INDEX = 0` 不报错 | 整段 (C) 被 `if HEAD_NODE_Z_INDEX:` 门控，而 `z_lines` 是**同一个门控** ⇒ 把常量改成 0，场景里 `z_index` 消失、断言也一起被跳过 ⇒「层级调高」这条硬需求**能被静默关掉且全绿** | 去掉门控，改成「常量必须是**正整数**」+ 场景里**恒须**有那行 |
| `HEAD_OFFSET = (-36,-46)` 不报错 | 断言写成 `if f"offset = Vector2({HEAD_OFFSET[0]}, …)" not in sp` —— 拿**常量**比**由同一常量渲染出的文本**，恒真 | 新增**金标锚点** `HEAD_*_GOLDEN`（独立记录的字面量），自检拿「活常量」比「金标」 |

> 教训：**只跑一遍正向自检说明不了任何事。** 必须逐条篡改常量做负向测试，
> 否则「断言与实现同错」的假绿永远看不出来（本节的两条 + §2.7.9 的节点括号那条，共三次同类问题）。
> 负向测试脚本：`.cache/_neg_test_head.py`。（改版 A 时 **8/8**；改版 B 追加 6 条用例后
> **14/14**，含 2 条**注入式** —— 见 §2.7.13①③⑤。）

#### 2.7.11 验证（2026-09-22 第二轮实测）

| 项 | 结果 |
|---|---|
| 生成器自检 | `fails = 0` |
| 结构负向测试 `.cache/verify_head_structure.py` | **15/15 正反例全过**（含新增「节点头结尾写成 `>`」） |
| 插件编译 | 24 064 B，sha256 `e28f38d73c0f84e4`，**两次编译字节一致**，0 warning |
| 闸门（两份构建） | remake **285 PASS / 0 FAIL**、console **285 PASS / 0 FAIL** |
| 幂等 | 三连跑 pmod = 180 976 B / sha256 `9cbf18f7cf8f8dc0` / 条目 14，逐次一致 |
| 安装镜像 | `…/Sprite/ZombieSuperGatlingPaper.tscn` = **7 107 B**、`LayerVisible true=29 / false=36 / MediaReplace=48`、LF、**0 条坏节点头**、三节点父路径全对 |

⚠️ **以上全部是「离线/结构」层面的验证。**「头真的画对了、射击动画真的播出来了」这一步
**必须进游戏看**（§11），本轮未做 —— 如实记录。

#### 2.7.12 验证（2026-09-23 改版 A 实测：头部摆正 + 层级 —— ⚠️ 摆正部分已回退）

| 项 | 结果 |
|---|---|
| 生成器自检 | `SELF_CHECK: PASS (0 fails)` |
| 负向测试（篡改常量）`.cache/_neg_test_head.py` | **8/8 全中**（原先是 1/5 —— 两个假绿已修） |
| 对位回归门 `.cache/check_head_fit.py` | PASS；反解 `(-54.19,-10.11)` 差 **0.001px**；落点中心距 **0.00px**、四边最大超出 **3.66px**；三条历史值负向全部如期失败 |
| 字节级核对 `.cache/_byte_check_head.py` | PASS；工作区与安装镜像**逐字节相同**（**7 215 B**）；8 条期望串全部在可见头块内；节点头全部以 `]` 收尾 |
| 闸门（两份构建） | remake **292 PASS / 0 FAIL**、console **292 PASS / 0 FAIL** |
| 插件编译 | 24 064 B，sha256 `e28f38d73c0f84e4`（第四次改版**动了代码**：`SyncHeadPairs()` 新增生成点覆写；`build_runtime.py --check` 两次编译字节一致） |
| 幂等 | `.cache/check_sgp_idempotent.py` 全部通过 |
| 交付对照图 | ~~`僵尸Mod-超级机枪读报僵尸-头部摆正对照.png`~~ —— ⚠️ **已删除**：它画的是「冻结 net 0°」那个**已被改版 B 回退**的状态，留着会与产物事实矛盾。改版 B 的对照图见 §2.7.13 |

⚠️ 同样：**「实机上头是不是正的、有没有被遮挡」仍需进游戏确认**（§11），本轮未做。

#### 2.7.13 ★★ 回退头部动画 + 头部初始位置向右上微移（2026-09-23 改版 B）

用户原话：

> 「请回退到上一版本的僵尸头部动画，然后在此基础上进行以下调整：将头部的初始位置从偏左向
> 右上方向微微移动，使整体构图更加协调。」

##### ① 「回退」= 把三行全部撤掉（不是改值）

改版 A 的冻结靠场景里三行（`usePos = true` / `useRotate = false` / `rotation = 0.0`）。
本版 `HEAD_FIX_HEAD_ROTATE = False` ⇒ `rot_lines = ""` ⇒ **三行一个都不写**
（`sprite_scene_tscn()` 里本来就有这个分支，属当初特意留的**一键回滚**）。

- 两个 `[Export]` 开关回到默认 `true`（`AdobeAnimateSprite.cs:275-282`）
  ⇒ 引擎恢复每帧覆写（`:5259-5276`）
  ⇒ 头**重新跟 `anim_head1`(L16) 摆动**：Idle 净旋转 **−16.03°..+1.01°**（25 帧，逐帧插值）。
- **插件零改动**：`SyncHeadPairs()` 本来就是「每帧把影子的 `Position`/`Rotation` 抄给可见头」，
  与旋转是引擎算的还是场景冻住的**无关**（改版 A 时它是幂等空转，本版才是真正在搬运摆动）。
- ⚠️ **`rotation` 也一并禁掉**（自检 + 闸门都查）：没有同块的 `useRotate = false` 时它是**死值**，
  只会在下次改的人眼里冒充「这里有个角度在起作用」。负向测试里专门有两条**注入式**用例
  （往渲染出的场景文本里塞 `rotation = 0.0` / `useRotate = false`）证明这两条断言真的会响。
- 生成器里的开关 / 金标 / 机制说明**全部保留** ⇒ 想切回改版 A，只需把常量改回 `True` 并重解 offset。

##### ② 「偏左」是多少：整头块比身体左轮廓多伸出 **13.77 px**

`.cache/_shift_probe.py` 实测（身体 = `ZombiePaper` 去掉 7 层原头后的并集包围盒）：

| 量 | 值 |
|---|---|
| 身体（去头）包围盒 | x **−49.40 .. 47.72**（宽 97.12），中心 `(−0.84, +3.67)` |
| 回退后整头块（shift 0,0） | x **−63.17 .. 28.02** ⇒ 左侧多伸出 **13.77 px** |
| 原因 | 机枪炮管朝左伸得很远，视觉重心被拽到左边 |

> ⚠️ `Skin.bbox` 给的是**精灵局部**坐标，身体要靠父精灵 `offset = (−40,−80)` 搬进来
> （`UpdateChild` 里 `Position = pose.Origin + 父精灵 offset`）。第一版探针忘了补这一步，
> 算出「身体中心 x=+39.16」这种明显不对的数 —— 已修（`_shift_probe.py` 里 `shift(body_raw, *P.body_off)`）。

##### ③ 微移量怎么定 + ★ 一个方向坑

候选表（`.cache/_ab_shift_amt.json` → `僵尸Mod-超级机枪读报僵尸-头部右移幅度候选.png`）：

| `HEAD_PLACE_SHIFT` | 整头块 x 范围 | 相对身体中心 dx | 结论 |
|---|---|---|---|
| `(0, 0)` | −63.17 .. 28.02 | −16.73 | 纯几何对齐（回退后的基准） |
| `(+4, −2)` | −59.2 .. 32.0 | −12.73 | 几乎看不出 |
| **`(+8, −4)`** | −55.2 .. 36.0 | −8.73 | ★ **本版采用**：左侧伸出 13.8 → **5.8 px**，≈身体宽度 8%，属「微微」 |
| `(+12, −6)` | −51.2 .. 40.0 | −4.73 | 已与身体左轮廓齐平，偏大 |

★★ **方向坑（本版新踩、已固化成负向用例）**：位移量必须加在**锚点**上，**不能**加在 `offset` 上。

```
offset = A⁻¹·(target − (A·mass_center + node))      # target = 原头中心 + shift
```

`offset` 住在头的**局部空间**，画之前还要过 `A = rot_scale(θ, sx=−1, sy=1)`（含**横向翻转**）：

- 把 `(+6,−3)` 直接加到 `offset` 上 ⇒ 屏幕实际位移 **(−6.36, −2.13)**（**横向正负完全相反**）；
- 把 `(+8,−4)` 直接加到 `offset` 上 ⇒ **(−8.48, −2.84)**；
- 加在**锚点**上 ⇒ `screen_delta` **逐字等于** `shift`（实测 `0.000009 px`）。

因为平移的是锚点，`place_box` 回投出来的屏幕位移就是可断言量，这条被写成了几何门的核心判据。

##### ④ 判据换了（旧判据必然假红，别照抄）

| | 改版 A | 改版 B |
|---|---|---|
| 位置判据 | 头块中心距原头中心 **≤ 2 px** | **屏幕位移逐字 = `HEAD_PLACE_SHIFT`**（≤ 0.001 px） |
| 防悬空判据 | 四边最大超出 ≤ 10 px（绝对阈值） | **头块覆盖原头面积比例 ≥ 60%**（实测 95.1%） |
| offset 差阈值 | 0.05 px（常量写 2 位小数） | **0.001 px**（常量写 4 位小数 ⇒ 理论 ≤ 7e-5，收紧 50×） |
| 口径断言 | `HEAD_FIX_HEAD_ROTATE` 必须 `True` | **必须 `False`** + 「Idle 净旋转跨度 ≥ 1°」（证明真的在跟 `anim_head1`） |

⚠️ 改版 A 那两条位置判据在本版**必然失败** —— 因为偏移是**故意的**。
「绝对阈值」遇上有意偏移只会单调变差，所以换成**语义更准**的两条：位移量对不对 + 还压不压得住原头。

负向用例也从 3 条历史值扩到 **5 条**（新增「改版 A 的 `(−54.19,−10.11)`」「本版纯几何 `(−51.46,−7.21)`」
「★ 把 shift 直接加到 offset 上的方向坑」），负向测试总表 **14/14** 全中。

##### ⑤ 改版 B 实测

| 项 | 结果 |
|---|---|
| 生成器自检 | `SELF_CHECK: PASS (0 fails)` |
| 负向测试 `.cache/_neg_test_head.py` | **14/14**（含 2 条注入式：偷塞 `rotation` / `useRotate`） |
| 对位回归门 `.cache/check_head_fit.py` | PASS；反解 `(-59.9377,-10.0515)` 差 **0.000009 px**；屏幕位移 **(+8.0000,−4.0000)** 逐字符合；覆盖原头 **95.1%**；官方样本交叉校验 4.61 px 仍过；**5 条**历史/方向负向全部如期失败 |
| 字节级核对 `.cache/_byte_check_head.py` | PASS；工作区与安装镜像**逐字节相同**（**7 131 B**）；**负向**：全文无 `useRotate` / `usePos` / `rotation` |
| 闸门（两份构建） | remake **292 PASS / 0 FAIL**、console **292 PASS / 0 FAIL**（9.13 组 4 条由「必须冻结」翻成「必须不冻结」，条数不变）；第四次改版新增 9.15 / 9.15b 共 **8** 条 ⇒ **300 / 0** |
| 幂等 | 3 连跑 pmod = **180 991 B** / sha256 `4794b056cdd455b9` / 条目 14，逐次一致（第四次改版后为 **181 388 B** / `b054c21bbe8b2c69`，见 §2.7.14） |
| 插件编译 | **零改动**（只改了注释）⇒ DLL 字节与改版 A 相同 |
| 交付对照图 | `僵尸Mod-超级机枪读报僵尸-头部动画与位置对照.png`（上排改版 A 冻结 / 下排改版 B，bf 0·12·20 同帧）、`僵尸Mod-超级机枪读报僵尸-头部右移幅度候选.png` |

> ⚠️ 微移量是**主观**量 —— 想更大/更小，改 `HEAD_PLACE_SHIFT` 一个数、
> 跑 `python .cache/head_place.py --shift=<dx,dy>` 取新 offset、同步 `*_GOLDEN` 即可（三步，见 §8.2）。

⚠️ 同样：**「实机上头是不是在摆、位置顺不顺眼」仍需进游戏确认**（§11），本轮未做。

---


#### 2.7.14 ★★ 子弹生成点对齐炮口（2026-09-24 四次改版）

用户原话：「让子弹生成位置靠左一点，对齐子弹发射口」。

**真源（顺源码查出来的，不是猜的）** —— 子弹生成点 = `firePosMarkerPaths` 指向的那个
`Marker2D` 的**世界位置**：

| 环节 | 源码 | 结论 |
|---|---|---|
| 场景里声明 | `…FireComponentDefinition.tres` → `firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker")]` | 生成点就是这个 `Marker2D` |
| 取第几个 marker | `FireComponentFireProjectileConfig.cs:10` `public int firePosId;`（默认 0，本包不写） | 第 0 个 |
| 怎么算位置 | `FireComponent.CreateProjectile()`（`FireComponent.cs:2698-2714`）⇒ `parent.GetLogicalGlobalPosition(marker2D)`，而 `TowerDefenseCharacter.cs:1607-1619` 的实现就是 `descendant.GlobalPosition` | **`marker2D.GlobalPosition`** |
| 同格吸附 / 高速改 x | `snapStraightProjectileToSameCellTarget`（`FireComponentDefinition.cs:121`，默认 false）/ `ResolveOffsetLineRoute`（只在子弹挡路时改 x） | 本包都不生效 |

⇒ 生成点 = Marker2D 的世界坐标。**既不是僵尸原点，也不是炮口。**

**改前差多少（实测）**：

| 口径 | 渲染 space 坐标 |
|---|---|
| 生成点（改前 `FireMarker.position = (0, 0)`） | `(-54.0155, -120.4089)` |
| 参考帧 bf=0 的真炮口 | `(-60.5560, -39.6378)` |
| **差** | **偏右 6.540px、偏上 80.771px** |

「偏上 80.77px」是主问题 ⇒ 豌豆从**头顶上方**出膛。

⚠️ 生成器里原先写的理由「`FireMarker` 挂在 `HeadSlot` 下 ⇒ 自动跟随头部动画」**是错的**。
`HeadSlot` 是**原版给护具 / DamagePoint 用的静态插槽**（原版 `TowerDefenseZombiePaper.tscn:67-71`：
`drawLayerId=-2` / `position=(-14.015516,-40.408867)` / `rotation=-0.27867758` / `scale=0.79857695`），
护具之所以看着贴在头上，是**护具自己的 `offset` 补掉了这段差**。⇒ 生成点必须显式搬到炮口。

**炮口点从哪来（两个独立来源，差 0.0000px）**：

| 来源 | 值 |
|---|---|
| 植物侧历史标定（`build_plant_super_gatling.py` 的 `ANCHOR_MUZZLE`，配 `ANCHOR_ROOT=(40,40)`） | 头 pose 空间 `(88.552, 30.2)` |
| 本轮独立反推（`.cache/_muzzle_probe.py`：barrel 轨（图层 19 / media 13 `SuperGatlingPea_barrel.png`）在**完全伸出帧** hf=62 取**不透明区最右列中点** = 局部像素 `(43.0, 24.0)`，映射到 pose 空间） | `(88.5520, 30.2000)` |
| **差** | **0.0000 px** |

本包僵尸头用的就是**同一份** `SuperGatlingPea.tres` ⇒ pose 空间逐字相同。

**实现分两层（缺一不可）**：

1. **静态兜底** —— 场景 `FireMarker.position` 重解为 HeadSlot 局部 `(-35.697232, 94.988609)`
   （工具 `.cache/_fire_marker_solve.py`，回代差 **0.000004 px**）：
   ```
   head_local   = MUZZLE_POSE + HEAD_OFFSET          = (28.6143, 20.1485)
   muzzle_space = A·head_local + node                （A = rot_scale(层旋转, −1, +1)；参考帧 bf=0）
   Q            = muzzle_space − BODY_OFFSET(-40,-80) （身体精灵局部）
   p            = (1/s)·R(−θ)·(Q − HeadSlot.pos)      ⇒  FIRE_MARKER_POS
   ```
   ⚠️ HeadSlot 的 `rotation=-0.27867758`（≈ −15.97°）/ `scale=0.79857695` **会作用在子节点局部坐标**上
   （Godot `Transform2D` 只把 `position` 当平移）⇒ 把方向量直接加进 `offset` 会**又缩放又旋转**。

2. **每帧动态** —— 插件 `SyncHeadPairs()` 在抄完影子位姿之后，把 `marker.GlobalPosition`
   覆写成 `head.GlobalTransform × HeadMuzzleLocal`（`HeadMuzzleLocal = (28.6143f, 20.1485f)`）。
   `head.GlobalTransform` 含头的 `Position`/`Rotation`（每帧从影子抄）与 `scale=(-1,1)`
   ⇒ 一行就得到炮口世界坐标，天然跟随。

**为什么非要第二层**：改版 B 之后头是跟 `anim_head1` **逐帧摆动**的 ⇒ 炮口每帧都在动。
扫全部身体 clip（`.cache/_muzzle_scan.py`）：

| clip | 帧 | 炮口 x 跨 | 炮口 y 跨 |
|---|---|---|---|
| Idle | 0..24 | 4.85 | 20.12 |
| Walk | 25..71 | 23.66 | 53.97 |
| Eat | 72..95 | 42.76 | 78.20 |
| AngryWalk | 145..191 | 23.66 | 53.97 |
| AngryEat | 192..215 | 42.76 | 78.20 |
| Death 96..131 / Gasp 132..144 | — | 该段 L16 没有切片（头不跟随） | |

⇒ **静态 `FireMarker.position` 只能对上参考帧 bf=0**；实测 Idle 段最大离线 **10.86 px**
（对照图第 3 格 bf20 时静态点离线 **9.03 px**），理论上限 ~44 px。
「每一帧都对齐」只能靠插件覆写 —— 这正是两层都要做的原因。

**验证**（全部可复跑）：

| 项 | 结果 |
|---|---|
| 生成器自检 | `fails = 0`。新增 (E)/(E2) 组：炮口/生成点常量形状与派生式（`HEAD_MUZZLE_LOCAL == MUZZLE_POSE + HEAD_OFFSET`）；场景里 `FireMarker.position` 必须是解出的值且**不许**是 `(0,0)`；**跨语言**断言插件 `HeadMuzzleLocal` 字面量 == 生成器 `HEAD_MUZZLE_LOCAL`（两个独立文件的比对，非同源恒真） |
| 负向测试 `.cache/_neg_test_head.py` | **19/19**（新增 5 条：`FIRE_MARKER_POS` 退 (0,0) / 只改 y / `MUZZLE_POSE` 挪走 / `HEAD_MUZZLE_LOCAL` 与派生式不符 / **注入**场景 `FireMarker` 偷写回 (0,0)） |
| 几何门 `.cache/check_head_fit.py` | PASS。**判据 ④** 两个来源互相独立：炮口 ← barrel 轨美术反推；生成点 ← **场景 .tscn** 现场反读（HeadSlot 的 rot/scale 会作用在 marker 局部坐标上）；差 **0.000004 px**；**5 条生成点负向**（退 (0,0) 离线 81.04px、只改 y 28.51px、只改 x 75.86px、符号反 162.07px、整体偏 10px 7.99px）全部如期离线 |
| 字节级核对 `.cache/_byte_check_head.py` | PASS。新增 **Scene**（5 452 B）与 **FireComponentDefinition.tres**（2 601 B）两组；工作区与安装镜像**逐字节相同** |
| 闸门（两份构建） | 新增 9.15 / 9.15b 共 **8** 条 ⇒ remake **300 PASS / 0 FAIL**、console **300 PASS / 0 FAIL** |
| 交付对照图 | `僵尸Mod-超级机枪读报僵尸-子弹生成点对齐炮口.png`（灰 = 修正前 `(0,0)`；红 = 静态兜底；青 = 每帧真炮口；4 格 = bf 0/12/20·hf62 + bf0·hf35） |

⚠️ 老规矩：**「实机上豌豆是不是真的从喇叭口出来」仍需进游戏确认**（§11），本轮未做。

## 3. 数据包结构

### 3.1 角色包布局（来自游戏自己的生成器，不是猜的）

> ★ 本包比官方模板多两个文件：`Scene/<Key>ComponentSet.tres` + `Scene/<Key>FireComponentDefinition.tres`。
> **前者必须在 `<Key>/Scene/<Key>.tscn` 的根节点上被 `ComponentSet = ExtResource("15")` 引用**，
> 光把文件放进包里是**没有任何作用**的（组件不会被创建）—— 见 §2.2 ①。

`addons/ModEditor/FileSystem/XWResourceCreateRoute.cs` 的
`CreateCharacterScenePackageFromTemplate()` 是**游戏 mod 编辑器自带**的「新建角色包」流程，权威范本：

```
<Key>/Scene/<Key>.<ext>          ← 运行场景（6 段硬约束）
<Key>/Config/<Key>Config.tres    ← 角色配置
<Key>/Sprite/<Key>.tscn          ← 精灵场景（CharacterSprite 注册点）
<Key>/Packet/<Key>.tres          ← 卡片（本包也放一份镜像，与内置角色目录同构）
<Key>/Armor/<Key>ArmorData.tres  ← 护具表（本包**新建**：把 Paper 换成包内槽配置）
<Key>/Armor/Config/*.tres        ← 护具槽配置（本包**新建**）
<Key>/<Key>.tres                 ← 动画数据（本包复用内置，不新建）
<Key>/Script/<Key>.cs            ← 脚本（本包复用内置，不新建）
```

本包 Key = `ZombieSuperGatlingPaper`，目录类别 = `Zombies`。

### 3.2 四条路径/命名硬约束（违反 = 整包「不加载」）

| 约束 | 源码 | 本包取值 |
|---|---|---|
| 路径**恰好 6 段**，`[0]=Resources`、`[1]=Characters`、`[2]∈已知类别`、`[4]=="Scene"`、`[5]` 为 `.tscn`，且**文件名 == 目录名 == Key** | `ModLoader.cs:1275` `TryInferCharacterScene` | `Resources/Characters/Zombies/ZombieSuperGatlingPaper/Scene/ZombieSuperGatlingPaper.tscn` |
| 同上，`[4]=="Sprite"` | 同上（folder 参数） | `…/Sprite/ZombieSuperGatlingPaper.tscn` |
| 类别必须 ∈ `Plants/Zombies/Props/Vases/Mowers/Items/Graves/Craters` | `ModLoader.cs:1292` `IsKnownCharacterCategory` | `Zombies` |
| 角色包目录下**任意** ≥5 段文件都算「包依赖」，不会被判 unsupported | `ModLoader.cs:1301` `IsCharacterPackageDependency` | ComponentSet / FireDefinition / Config / Packet / **Armor 两个**都靠这条放行 |

### 3.3 三处命名必须统一（`XWModContentValidation.Validate`）

| 项 | 值 | 依据 |
|---|---|---|
| 卡片注册键 | `Resources/Cards/ZombieSuperGatlingPaper`（= 文件名去扩展） | `ModLoader.InferRuntimeEntry` 的 `Resources/Cards/` → Packet 分支 |
| `packet.saveKey` | `ZombieSuperGatlingPaper` | `XWModContentValidation.cs:30-33`，不等即 throw |
| `characterConfig.name` | `ZombieSuperGatlingPaper` | `XWModContentValidation.cs:34` 拿它查 `TOWERDEFENSE_CHARCATERS` |
| `CHARCTAER_SPRITE` 键 | `ZombieSuperGatlingPaper` | `XWModContentValidation.cs:35-36`，缺 = throw「缺少 CharacterSprite/…」 |
| `manifest.provides` | `Character` / `CharacterSprite` / `Packet` 三键都是 `["ZombieSuperGatlingPaper"]` | `provides` 里每个 key 都必须真的注册上 |
| `packet.unlockCheckList` | `[]`（空表 = 直接可用） | `XWModContentValidation.cs:37-40`，放游戏内条件会被判「必须使用 Mod 专属解锁条件」 |

⚠️ **`config.name` 与 `packet.name` 在本包里故意不同**：
前者是内部键（`ZombieSuperGatlingPaper`，**插件也靠它认人**），后者是显示名（中文）。
混起来会同时踩到「查不到角色」和「游戏里显示成英文 key」。

### 3.4 包内自引用必须相对路径 / 引用游戏资源才用 `res://`

| 引用 | 写法 | 为什么 |
|---|---|---|
| `Config/TowerDefense…tres` → `../Armor/…ArmorData.tres` | **相对** | 包内文件 |
| ArmorData → `./Config/ZombieSuperGatlingPaperArmorPaper.tres` | **相对** | 包内文件 |
| Config → `res://Asset/…/Paper/DamagePoint/ZombiePaperDamagePointData.tres` | `res://` | 游戏自带 |
| Scene → `res://Asset/…/Paper/Scene/TowerDefenseZombiePaper.cs` | `res://` | 游戏自带脚本（**需求 6 的关键**） |

`ModLoader.SanitizeCharacterTextResource()`（`ModLoader.cs:1418`）的规则：

| 情况 | 处理 |
|---|---|
| 文本里出现 `type="GDScript"` / `type="CSharpScript"` 字面量 | **直接拒绝整包**（`:1423`） |
| `type="Script"` 且 `path` **不是** `res://` 开头 | `.tscn` 里**剥离该引用**并移除用到它的行；`.tres` 里**直接拒绝**（`:1439`） |
| `type="Script"` 且 `path` 是 `res://` 开头 | **保留** |

⚠️ **绝对不要**加 `metadata/mod_character_script_binding = "CompanionOnly"`：
`ModLoader.CharacterRequiresCompanion()`（`ModLoader.cs:630`）一读到这个 meta 就会去要
`mod.CharacterCompanionRuntime`，拿不到 → 该资源被拒 → 整包回滚。本包不写这个 meta。

---

## 4. 数值映射（逐条有源码依据）

### 4.1 血量 1250 —— 一个需要说清楚的算术

`TowerDefenseCharacterInstance._Init`：

```csharp
hitpointsBase = config.hitpoints;
hitpoints     = hitpointsBase + config.hitpointsNearDeath;   // ← 有效总血
```

而 `hitpointsNearDeath` 不只是「额外血」，它同时是**濒死线**：
`if (!nearDie && hitpoints <= hitpointsNearDeath)` → 进入濒死阶段；
`TowerDefenseCharacter.DealHurt(config.hitpointsNearDeath * delta / 3.0)` → 濒死流血。

**决策**：需求 5 说「本体 1250」，我按**有效总血恰好 1250** 落地：

```
hitpointsNearDeath = 70.0     （逐字沿用内置读报僵尸，保住「濒死阶段」这一可见特性 + 需求 6 的暴走链路）
hitpoints          = 1180.0   （= 1250 − 70）
```

⚠️ **如果你更希望 `.tres` 里直接看到 `hitpoints = 1250.0`**，改生成器顶部两个常量即可
（`HP_NEAR_DEATH = 0.0` 让总血恰好 1250 但**取消濒死阶段**）。见 §10.1。

### 4.2 「二类防具 500 血」的落点 —— 不动游戏注册表

`TowerDefenseArmorInstance` 构造函数（`Resource/TowerDefense/Character/Instance/TowerDefenseArmorInstance.cs`）：

```csharp
typeData = TowerDefenseArmorRegistry.GetArmorType(slotConfig.armorName);
damagePointBase = ((slotConfig.damagePoint >= 0.0) ? slotConfig.damagePoint : typeData.damagePoint);
hitPoints = damagePointBase;
```

⇒ `slotConfig.damagePoint >= 0` 会**覆盖**注册表的 `typeData.damagePoint`。
所以：**不改** `res://Registry/Armor/Config/Paper.tres`（游戏注册表，改了会影响所有戴 Paper 的角色），
改成在包内新建一份槽配置：

```gdscript
# Armor/Config/ZombieSuperGatlingPaperArmorPaper.tres
armorName = "Paper"
replaceMediaName = &"Zombie_paper_paper1.png"       # 逐字沿用内置
damagePoint = 500.0                                 # ★ 需求 5a
destroyFliter = "Zombie_paper_paper"
```

再新建 `Armor/ZombieSuperGatlingPaperArmorData.tres`：6 项与内置**逐字相同**，只把 `Paper` 的
`slotConfig` 指向上面这份包内槽配置，`typeData` 仍指向 `res://Registry/Armor/Config/Paper.tres`。

### 4.3 「二类防具」= 哪个位？—— `SHIELD`，内置 Paper 天生就是

`TowerDefenseEnum.ARMOR_METHOD_FLAGS`：

| 名 | 值 |
|---|---|
| `SHIELD` | **4** |
| `DAMAGEABLE` | `0x40` = 64 |
| `DROPABLE` | `0x80` |
| `ABSORBOVERFLOW` | `0x200` |

内置 `Registry/Armor/Config/Paper.tres` 的 `armorMethodFlags = 68 = SHIELD | DAMAGEABLE`。

⇒ **报纸天生就是「二类（护具）层」**，而且**不含 `DROPABLE`** —— 它属于「被打掉」而不是「可掉落头盔」那一类，
与内置读报僵尸的设定一致。本包不需要改任何 flag，只要把血量换成 500。

### 4.4 需求 6 白送：防具掉落 → 移速 ×3

`Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.cs`：

```csharp
public override void ArmorHitpointsEmpty(string armorName)
{
    base.ArmorHitpointsEmpty(armorName);
    if (armorName == "Paper")
    {
        SendStateEvent("ToGasp");
        AudioManager.Instance.AudioPlay("NewspaperRip");
    }
}

public override void AnimeCompleted(string clip)
{
    base.AnimeCompleted(clip);
    if (clip == "Gasp")
    {
        AudioManager.Instance.AudioPlay("NewspaperRarrgh");
        timeScaleInit = 3.0;      // ★ = 移速 ×3
        angry = true;
        Walk();
    }
}
```

本包场景的 `script` 直接指向 `res://Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.cs`
⇒ **完全免费**拿到「报纸碎 → 吼叫 → 暴走 → 移速 ×3 → 换 `AngryWalk`/`AngryEat` 动画」，一行插件代码都不用写。
状态机也照抄内置 `TowerDefenseZombiePaperStateMachine.tres`（含 `zombie.paper.gasp` 状态 + `ToGasp` 转换）。

### 4.5 「移速 = 普通僵尸」= 什么都不写

移速 = 走路动画驱动：`GroundMoveComponent` 读精灵的 `GroundSlot` 逐帧位移 × `_moveScale`，
再乘 `TowerDefenseCharacter.timeScale`（默认 1.0）。

* 基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn`：`walkSpeedScale = 1.0`；
* 内置 `TowerDefenseZombieNormal.tscn`：**不覆盖** `walkSpeedScale`；
* 内置 `TowerDefenseZombiePaper.tscn`：**也不覆盖**。

⇒ 「普通僵尸」与「读报僵尸」本来就同速，本包**只要什么都不写**就是对的。
生成器自检里有断言禁止产物里出现 `walkSpeedScale` / `timeScale` / `animeSpeedScale`。

### 4.6 其余数值

| 字段 | 值 | 依据 / 为什么 |
|---|---|---|
| `attack` | `800.0` | `TowerDefenseZombie.tscn` `useAttackDps = true` ⇒ 800 = 每秒啃食伤害 |
| `smashAttack` | **不写** | 需求只要啃食；写了反而会让它获得碾压能力 |
| `attackType` | （不写，走父组件集的默认 `"Eat"`） | `AttackComponentDefinition.attackType` 的 Enum 提示串 = `"Default,Eat,Smash,Chomp"`；父组件集的 `AttackComponentZombieDefinition.tres` **不写** `attackType` ⇒ 默认 Eat |
| `type` | `6` | `TowerDefenseEnum.PACKET_TYPE`：`WHITE=0, GOLD=1, …, ORIGINAL=5, **ZOMBIE=6**, COVER=7, GRAY=8` |
| `cost` | `100` | 用户选择 |
| `packetCooldown` | `5.0` | 用户选择（`costRise` 保持默认 `-1` = 不涨价） |
| `physique` | （不写，默认 `NORMAL`） | 不是投石车/巨人那类特殊体型 |
| `weight` / `wavePointCost` | `2000` / `150` | 逐字沿用内置读报僵尸（出怪权重与原版一致） |
| `homeWorld` | `1` | 逐字沿用 |
| `damagePointData` | 内置 `ZombiePaperDamagePointData.tres`（`res://`） | 掉手/掉头等伤害点表现 |
| `ashScene` | 内置 `ZombieGeneralAsh.tscn` | 死亡成灰 |
| `plantGridType` / `maskFlags` | `[-1]` / `9` | 逐字沿用内置读报僵尸 |
| `HitBoxDefinition` | 内置 `Rect_44x70_At_4_n2.tres` | 与读报僵尸同体型（贴图复用 ⇒ 命中盒必须一致） |
| 豌豆配置 | `projectileName = &"Pea"`、`speed = -300.0`、`catapultHeight = 400.0` | **逐字沿用内置机枪豌豆僵尸**的发射配置 |
| `fireInterval` | `1.5` | 与插件普攻周期一致；⚠️ 因为动画链路失效，它**只有文档意义**（真正节拍在插件里） |
| `fireAudioName` | `"ProjectileThrow"` | 内置机枪豌豆僵尸同款；大招期间插件把它置空 |
| `InstanceId` | `character.fire` | 插件 `GetRuntime<FireComponent>("character.fire")` 的查找键，**不能改** |

**字段书写顺序**严格按类声明顺序（`TowerDefenseZombieConfig` 先、`TowerDefenseCharacterConfig` 后），
否则编辑器一保存就会把它重排（与植物包同一约定，自检里有断言）。

### 4.7 ⚠️ 唯一靠推断的值：`FireMarker.position = Vector2(0, 0)`

发射位置必须是一个**真 `Marker2D`**。依据：

```csharp
// FireComponent.cs:1232（ResolveReferences 内）
Marker2D item = ResolveOwnerNode<Marker2D>(Definition.firePosMarkerPaths[i]);
// FireComponent.cs:1254
return parent.GetNodeOrNull<T>(path);
```

`GetNodeOrNull<Marker2D>` 是**带类型过滤**的 ⇒ 直接指向头部插槽 `AdobeAnimateSlot HeadSlot` 会拿到 `null`，
豌豆会从僵尸原点出膛。所以本包在场景里新增一个 `Marker2D`：

```
[node name="FireMarker" type="Marker2D" parent="SpriteGroup/TransformPoint/ZombiePaper/HeadSlot" index="0"]
position = Vector2(0, 0)
```

挂在 `HeadSlot` 下面 ⇒ **自动跟随头部动画**（含暴走换头）。

`position = Vector2(0, 0)` 取的是「头部插槽原点」，属于**推断值**：
`HeadSlot` 本身带 `rotation = -0.2787` / `scale = 0.7986`，同插槽里的报纸贴图在
`ArmorConfig` 里偏移到 `ZombiePaper1.png` 的位置。
若实机看到豌豆出膛点偏了，**只改这一行 `position` 即可**（重新生成器 → 重打包，不用重编译插件）。见 §10.3。

---

## 5. 显示名为什么直接写中文（而不是翻译键 + translations.csv）

内置卡片的 `packet.name` 是**翻译键**（如 `TOWERDEFENSE_ZOMBIE_NEWSPAPER_NAME`），
因为游戏启动时 `Global.cs` 会 `TranslationServer.SetLocale("zh")` 加载官方翻译表。

但 **ModLoader 全文没有任何 `TranslationServer.AddTranslation` 调用**：
`manifest.translations` 只在 schema 校验 / 同步服务 / 引用图里被读写，
`Localization/*.csv` **不会**进入游戏运行时。⇒ 用翻译键写，游戏里就显示原始 key。

所以本包把中文**直接写进** 5 个显示字段（`packet.name` / `describe` / `handbookDescribe` /
`handbookStory` + 场景的 `metadata/mod_display_name`）：

| 消费点 | 源码 | 结果 |
|---|---|---|
| `packet.name` | `InformationPanel.cs` `nameLabel.Text = packetConfig.name;` | 直接显示中文 ✅ |
| `packet.describe` | `InformationPanel.cs` `expressionLabel.Text = Tr(packetConfig.describe)` | `Tr()` 查不到 → 原样返回 ✅ |
| `packet.name` | `AwardSettlement.cs` `nameLabel.Text = packetConfig.name;` | 直接显示中文 ✅ |
| `packet.name` | `LevelEditorBattle.cs` `Tr(packetConfig.name)` | 原样返回 ✅ |

这也是本包**不带** `Localization/translations.csv`、`manifest.translations` 为空表的原因。

---

## 6. ⚠️ Godot 4.7 的 `unique_id` / `parent_id_path` / `uid`：**故意不写**

本项目是 Godot **4.7**（`project.godot`：`config/features=PackedStringArray("4.7", "C#", "Forward Plus")`）。
新编辑器序列化时会顺手给节点加 `unique_id=…` / `parent_id_path=PackedInt32Array(…)`。**但这两项是可选的**：

1. 解包树里 **2071 个 `.tscn` 中有 319 个完全不带 `unique_id`**，且含多节点角色场景
   （`TowerDefensePlantPot.tscn` 7 节点、`TowerDefensePlantEMPlantern.tscn` 9 节点等），都在游戏里正常用着。
2. `TowerDefensePlantPot.tscn` 正是我们要的用法 —— 「给实例化子树的节点加子节点」，
   **完全没有** `parent_id_path`。
3. 游戏 mod 编辑器自己的角色场景模板 `BuildCharacterRuntimeSceneContent()` 输出
   `[gd_scene load_steps=4 format=3]` + `[node name="…" parent="SpriteGroup/TransformPoint" instance=…]`
   —— 既无 `uid` 也无 `unique_id` / `parent_id_path`。

⇒ 本包一律**不写** `uid` / `unique_id` / `parent_id_path`（写了反而要伪造一个推不出来的哈希，风险更大）。
自检里有专门一条：出现即失败。

---

## 7. 插件细节（`Runtime/ModAssembly.dll`，入口 `SuperGatlingPaperRuntimeEntry`）

源码 `runtime_src_zombie_super_gatling/SuperGatlingPaperRuntimeEntry.cs`（**1 853 行**，中文注释）。
判定参数与判定函数**不在这个文件里**，在植物/僵尸共用的
`runtime_shared/GatlingVolleyCore.cs`（§7.6）—— 本文件只保留 `= GatlingVolleyParams.X;` 转发。
编译：`python runtime_src_zombie_super_gatling/build_runtime.py --check`（两次编译比 sha256，字节确定）。

### 7.1 五条职责

**① 玩法（需求 3 / 4）** —— 按固定节拍逐颗打豌豆。
`SceneTree.process_frame` 每帧推进每只已挂载僵尸的时间轴，到期就调
`FireComponent.Fire()`；每次调用前把 `fireProjectileList` 里所有元素的 `dir` 写成目标角度。

**② 卡库入库（需求 1 的「能选到」）**
把 `ZombieSuperGatlingPaper` 补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类，
以及 `Include` 闭包算出的派生库（实测 `['GeneralZombie','TotalZombie','Total']`）。

依据：`Prefab/GUI/DialogBox/Almanac/Almanac.cs:220` —— 图鉴僵尸页是
`zombiePacketBank = TowerDefenseManager.GetPacketBankData("GeneralZombie")`，
**取的是同一个实例**（不像植物页那样走 `XWModContentCatalog.WithPlants()` 深拷贝）。
⇒ 补一处，**选卡界面 / 关卡编辑器 / 图鉴僵尸页同时生效**，天然同源。

派生库必须在**运行期**按 `PacketBankResource.json` 的 `Include` 闭包算，不写死；
读不到 json 才回落到离线算好的 `['GeneralZombie','TotalZombie','Total']`。
只补 `GeneralZombie` 的话，`CommandManager.debugPacketOpenAll`（切到 `Total`）下又会看不到。

**③ 幂等**：每次扫描（每 10 帧）都检查一遍卡库，几十条字符串比较，开销可忽略；缺了再补，补上才打日志。

**④ 图鉴去重（需求 8，2026-09-22）** —— 见 §7.3。扫到 `Almanac` 节点时（同一趟 10 帧扫描里），
反射取 `_zombieLogicalConfigs` 把本卡的重复项抹掉（保留最靠前的那条、顺序不变），
再用**公开**的 `QueueZombieVirtualRefresh()` 重建虚拟列表；
共享卡库 / `_packetPaths` / 解锁状态**一个字节都不动**。

**⑤ 子弹生成点每帧对齐炮口（需求 17，2026-09-24）** —— 见 §2.7.14。
`SyncHeadPairs()` 在抄完影子位姿之后，把 `HeadSlot/FireMarker`（Marker2D）的 `GlobalPosition`
覆写成 `head.GlobalTransform × HeadMuzzleLocal`（= 炮口世界坐标）。
为什么必须每帧：头跟 `anim_head1` 逐帧摆动 ⇒ 炮口每帧都在动（Idle 段静态点最坏离线 10.86 px）。
找不到 marker 时只报**一次**日志并退回场景静态兜底值，绝不抛。

### 7.2 四条硬约束（违反 = **整包被拒**，不是「不生效」）

| 约束 | 源码 | 本包 |
|---|---|---|
| `runtimeAssembly` 只能是**字面量** `"Runtime/ModAssembly.dll"`（字符串相等判定，不认别的路径/大小写/子目录） | `ModLoader.IsDeclaredRuntimeAssembly` | ✅ |
| `runtimeApiVersion` 必须**恰好** 1 | — | ✅ |
| `runtimeAssemblyPolicy = "optional"`：DLL 挂了不连坐角色 | `XWModManifest.IsRuntimeAssemblyRequired()` | ✅ |
| ⚠️ `TryInitializeRuntimeEntry` 失败 → **无条件整包回滚**，**不受 policy 保护** ⇒ 入口的 Initialize / OnAllModsLoaded / Shutdown **一律不许抛** | `ModLoader.cs:667-671` | ✅ 三个回调全部 try/catch；连 `Info/Warn` 内部也再套一层 try/catch（日志本身绝不能成为异常源） |

另外两条易错点：

* 入口类型 **FullName 必须等于 `runtimeEntryType`**（无命名空间 ⇒ 就是纯类名），
  且必须 `public` + 公开无参构造 + **非嵌套**（嵌套类型的 `FullName` 带 `+`）。
* `Runtime/ModAssembly.dll` 不是可推导的资源类别，但必须**同时**出现在 `manifest.resources` 里，
  且位置遵守 `SyncProject` 的规范序（`OrdinalIgnoreCase` 升序 ⇒ `Resources/…` 在前、`Runtime/…` 在后），
  否则编辑器一打开工程就会重写 `mod.json`。

### 7.3 ✅ 图鉴僵尸页重复：**已在运行期消除**（需求 8，2026-09-22）

**症状**：本卡在**图鉴的僵尸页**里出现**两条**（一条在 `ModZombies` 之类、一条在 `Zombie` 分类里）。

**根因 —— `Almanac.InitZombie()`（`Almanac.cs:411-435`）有两条独立来源，且都不去重**：

| # | 来源 | 源码 | 本包为什么正好命中 |
|---|---|---|---|
| 1 | 遍历**共享卡库**的 `Zombie` 分类 | `:416-425` `foreach zombiePacketBank.GetCategory("Zombie")` | 插件职责 ② 亲手把本卡补进了 `GeneralZombie.category["Zombie"]` |
| 2 | 遍历**引擎的 Mod 内容目录** | `:427-430` **无条件** `foreach XWModContentCatalog.GetPackets(plants:false)` | 引擎按 `ModLoader.cs:1071-1090` 的 `("Resources/Cards/", "Packet")` 映射，把包内 `Resources/Cards/ZombieSuperGatlingPaper.tres` 自动注册为 `Packet` 类别 |

两条来源**都删不得**（这是关键的取证结论，别再试了）：

* **删卡库那条** ⇒ 选卡界面立刻选不到 —— `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync:509-514`
  直读 `packetBankData.category[分类]`，而 `ResourceManager.BuildExpandedPacketBanks():638-647`
  **只从内置 `PacketBankResource.json` 构建，完全不合并 Mod 注册**。
* **删 `Resources/Cards/` 那条** ⇒ `TowerDefenseManager.GetPacketConfigReadOnly(key)` 返回 `null` ——
  `TOWERDEFENSE_PACKETS`（`ResourceManager.cs:529` ← `roots.PacketPathByName`）就是从这里来的。

**对比：植物页为什么没这个问题** —— `Almanac.InitPlant()`（`:311-356`）是**按分类分页**的
（`:324-328` 只读当前分类 `category[array[plantCategoryId]]`），天然不会把两条拼在一起。
僵尸页则是一次性把两个来源**都拼**进一个列表。所以这是**僵尸页专有**的形态问题。

**修法（图上侧去重，运行时）**：`TryDedupeAlmanacZombie(Almanac)`

```
扫到 Almanac 节点
  ├─ ZombieLogicalEntryCount <= 1 ?           → 直接返回（僵尸页还没建列表，或本来就只有一条）
  ├─ 反射取 private readonly Almanac._zombieLogicalConfigs（List<TowerDefensePacketConfig>）列表引用
  ├─ 从后往前遍历，saveKey == "ZombieSuperGatlingPaper" 的项：
  │     第一个命中的保留（从后往前 ⇒ 命中的第一个就是原本最靠前那条 ⇒ 顺序不变）
  │     其余 RemoveAt
  └─ 有删才调 almanac.QueueZombieVirtualRefresh()（public，不必反射）并打一条 Info
```

为什么选这条路，而不是往场景里加 `%Almanac` 节点或提前实例化图鉴：
**图鉴是刻意懒初始化的**（`Almanac.cs:391-397`），提前 `Instantiate()` 会把预览节点和角色资源
在打开图鉴的瞬间就加载出来 —— 项目里有一条测试 `AlmanacVirtualizedResidencyRuntimeTest`（34 号）
正是防这件事。而 `QueueZombieVirtualRefresh()` **自带 `_zombieInitialized` 守卫**，
未初始化时直接返回 ⇒ **不会**提前初始化，正好绕开该风险。

> 幂等性：每 10 帧扫一次，`InitZombie()` 每次重建列表后都会被重新收敛；
> 反射字段名对不上（换游戏版本）时返回 null、静默沿用旧行为，并只报一次
> `图鉴僵尸页去重失败（本条只报一次；不影响僵尸本体、豌豆发射与选卡）：…`。
> 该路径有**独立**的 `_dedupeFaultReported` 标志（§7.5）。
>
> 去重生效时会打：
> `图鉴僵尸页去重：抹掉 1 条重复的「ZombieSuperGatlingPaper」（共享卡库 + 引擎 Mod 内容目录各列了一次；累计 N 条）。选卡界面 / 关卡编辑器不受影响。`

### 7.4 ⚠️ `CharacterComponentRuntime` 不是 `GodotObject`

它是**纯 C# 抽象类**（`CharacterComponentRuntime` 基类是 `System.Object`，反射验证过），
所以 `FireComponent` 既没有 `GodotObject.IsInstanceValid()` 也没有 `GetInstanceId()`：

* 判活只能 `!fire.IsReleased && fire.Owner != null && GodotObject.IsInstanceValid(fire.Owner)`（Owner 是 `Node`）；
* 去重只能 `ReferenceEquals`。

### 7.5 七个独立「已报告」标志

`_tickFaultReported` / `_bankFaultReported` / `_hookFaultReported` / `_fireFaultReported` /
`_fireMissingReported` / `_shapeMismatchReported` / `_dedupeFaultReported`（2026-09-22 新增，去重路径）
—— **每条出错路径各用一个**。共用会把关键日志静音（上一版僵尸 Mod 踩过）。

其中 `_fireMissingReported` 是这次新加的：以前「认出僵尸却拿不到 `character.fire`」是**静默 return**，
第 2.2 节①那个 ComponentSet 缺声明就是这么被藏了一整轮。现在会明确报一次并**指出最可能的原因**。

### 7.6 ★ 与植物版**共用**同一套射击判定逻辑（需求 7，2026-09-22）

**为什么不是「共享程序集」**：每个 `.pmod` 都必须自带一份路径**恰好**为
`Runtime/ModAssembly.dll` 的程序集，且两版的 `runtimeEntryType` 不同
（`SuperGatlingPaperRuntimeEntry` vs `SuperGatlingPeaRuntimeEntry`）
⇒ 结构上就没法共用一个 DLL。

**做法 = 共享源文件（single source of truth）**：把判定抽成
`runtime_shared/GatlingVolleyCore.cs`，两个 csproj **各自编译同一份源**：

```xml
<ItemGroup>
  <Compile Include="..\runtime_shared\GatlingVolleyCore.cs" Link="GatlingVolleyCore.cs" />
</ItemGroup>
```

⇒ 判定只有一份实现，改一处两边同时生效，永远不会出现「植物改了、僵尸忘了」。
（对应的守卫见本节末，两版生成器 + 植物侧校验器都会拦。）

```csharp
internal static class GatlingVolleyParams      // 参数：数值全工程只在这里出现一次
{
    public const double AttackIntervalSeconds = 1.5;    // 普攻周期
    public const ulong  AttackIntervalMsec    = 1500;   // 字面量才够「编译期常量」
    public const int    PeasPerAttack         = 7;
    public const double PeaSpacingSeconds     = 0.1;
    public const ulong  PeaSpacingMsec        = 100;
    public const double UltimateChance        = 0.10;
    public const double UltimateSeconds       = 5.0;
    public const int    UltimatePeas          = 300;
    public const double ScatterHalfAngleDeg   = 15.0;
    public const double BurstIntervalMsec     = UltimateSeconds * 1000.0 / UltimatePeas;
    public const int    MaxPeasPerFrame       = 12;
    public const ulong  StallThresholdMsec    = 250;
}

internal static class GatlingVolleyJudge       // 判定函数：四类
{
    bool  RollUltimate(rng)                            // 掷大招骰
    float ScatterAngleDeg(rng)                         // 大招单颗散射角 ±15°
    ulong BurstDueMsec(burstStartMsec, index)          // 大招第 k 颗的计划时刻（无浮点漂移）
    void  ShiftTimeline(ref a, ref b, ref c, gapMsec)  // 僵尸 3 轴：普攻轴 + 连发轴 + 大招轴
    void  ShiftTimeline(ref a, ref b, gapMsec)         // 植物 2 轴：连发轴 + 大招轴
    ulong StallGap(lastMsec, now)                      // 本帧补偿量（0 = 正常帧）
}
```

**两版的「节拍外壳」故意不统一**：僵尸自建毫秒计时器（`process_frame` 驱动），
植物由引擎 `FireComponent.OnFireReady` 触发。外壳不同但**判定内容**完全一样，
所以就只共享 `GatlingVolleyJudge`，不为了「对称」去抽一个状态机基类
（那是零收益的纯重构，还会把两版已验证的产物搅乱）。

该文件刻意**不引用任何游戏类型**（只用 Godot 的 `RandomNumberGenerator` 与 `System.Math`），
所以两个工程都能原样编译，也便于单独推理。

**顺带收掉的两处「两版漂移」**（原先两版数值就不一致，本可各写各的一直漂下去）：

| 参数 | 植物版原值 | 僵尸版原值 | 统一后 | 影响 |
|---|---|---|---|---|
| 单帧发射上限 | `8` | `12` | **`12`** | 掉帧时植物每帧最多补 12 颗（原 8 颗）。上限抬高不破坏观感，只让极端掉帧时追得更快 |
| 卡顿阈值 | `400 ms`（名字还叫 `StallGapMsec`） | `250 ms` | **`250 ms`** | 植物遇到 250~400 ms 的顿卡也会补偿（不再补吐欠账豌豆），更稳 |

**防漂移守卫 —— 生成器 `self_check()` 里两问，缺一不可**：

1. **入口源码里的每个可调参数必须是转发**（`= GatlingVolleyParams.X;`）；
2. **字面量在共用核心里只能出现一次**，且必须等于生成器侧记录的期望值。

> 只看第 1 问 → 抓不到「共用核心被人改了」；只看第 2 问 → 抓不到「入口偷偷绕开核心写死自己的数」。
> 任一条不过，生成器**拒绝写盘**（退出码 3）。僵尸侧在 `build_zombie_super_gatling_paper.py`
> 第 14 节，植物侧在 `build_plant_super_gatling.py` 第 16 节（**两节完全对称**）。

植物侧校验器 `.cache/check_plant_super_gatling.py` 做同样两问（编号 `K15` / `K15b`…`K15h`，8 组 × 2 问 = **16 条**），
另加两条：

* **K18**：两个 csproj **都**真的 `Compile Include` 了同一份源
  （只挂一边 = 另一版本质上还是各抄一份，照样漂移）；**2 条**；
* **K19**：植物入口**真的在调用**共用判定函数
  （`RollUltimate` / `ScatterAngleDeg` / `StallGap` / `ShiftTimeline` 逐个查）；**4 条**。

> 「共用判定核心」四组（`K15*` / `K16` / `K18` / `K19`）**合计 23 条**，但脚本里只有 **6 个 `chk(` 调用点**
> —— 条数是**循环展开**出来的。⚠️ 所以「共几项」这个数字**不要手抄**：脚本末尾会自己打印
> `分节断言数: …` 与 `共享判定核心断言(K15* / K16 / K18 / K19): … => 合计 23` 两行，
> 分节表是**从脚本自身源码现算**的（增删小节自动跟随）。文档一律引用这两行，不再维护手写数字
> （曾经的「共 12 项」就是这么写歪的）。

---

## 8. 验收

### 8.1 离线闸门（两份游戏构建各跑一遍）

```
python .cache/run_gates_sgp.py
# 内部对两份构建各跑一次：
#   dotnet run --file runtime_src_zombie_super_gatling/check_gates_super_gatling_paper.cs -- \
#       <refDir> <projDir> <pmod> SuperGatlingPaperRuntimeEntry <解包根>
```

| 构建 | `PlantsVsZombies.dll` 位置 | 结果 |
|---|---|---|
| 重制版 | `D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64` | **292 PASS / 0 FAIL** |
| 控制台版 | `D:\zzz\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64`（⚠️ 目录名带「**杂交**」二字） | **292 PASS / 0 FAIL** |

日志：`.cache/_out_gates_sgp_remake.txt`、`.cache/_out_gates_sgp_console.txt`。

> 计数变化：268 → 285 → 292 → **292**（改版 B **条数不变**，只是 9.13 的判据翻面）。
> · 268 → 285：09-22 晚三改新增 **9.12「换头必须是三节点」** 那一组：
>   三节点存在与父路径 / **负向**「可见头没写成身体直接子节点」/ 书写顺序 / 影子三属性 /
>   可见头**不含**三属性与两死值 / `visFalse == visTrue + 7`（**不写死计数**）/
>   两个头三件套逐字相同 / `Animation/Clip = "HeadIdle"` / 5 个 `../` 相对路径 /
>   负向不引内置 `Plant` / `anim_head1 = false`。
> · 285 → 292：09-23 改版 A 新增 **9.13「姿态冻结」+ 9.14「可见头 z_index」** 两组：
>   `usePos = true` / `useRotate = false` / `rotation = 0.0`（两个头各一条）/
>   **负向**「写了 `rotation` 却没有 `useRotate = false`」/ 可见头 `z_index = 1` /
>   **负向**「影子不写 `z_index`」/ **负向**「没有任何节点把 `z_index` 写成 0」；
>   同时把 9.12 里那条「可见头不写 `rotation`」**删除**（否则与 9.13 自相矛盾 ⇒ 必假红）。
> · 292 → **292**：09-23 改版 B 把 9.13 那 4 条**翻面**（`usePos=true`/`useRotate=false`/`rotation=0.0`/
>   负向「写了 rotation 却没 useRotate=false」⇒ `!useRotate` / `!usePos` / `!rotation = ` /
>   负向「整份场景无 `useRotate`」）⇒ ADD 4 / DEL 4，**净 0**。9.14 与两个头三件套的那组
>   只改了 `offset` 字面量（`(-54.19,-10.11)` → `(-59.9377,-10.0515)`，条数不变）。
>
> ⚠️ **闸门计数必须随断言变化如实更新** —— 这是排查时判断「跑的到底是哪一版」的第一参照。
> ⚠️ 反过来：计数**没变**也可能是改了一大堆（本版就是）⇒ 别拿计数当"没改"的证据，
>    要看具体断言文案。

覆盖 10 组：

1. `InferRuntimeEntry` 对包内 **11 条路径**的推导（3 条注册 + 8 条「不作资源条目」）；
2. `XWModManifest.Load` 读回真 `mod.json`：runtime 四字段 / id / provides / overrides 空 / translations 空 / resources 升序；
3. `ValidateDeclaredPackageExecutables` 正向 + **两个负向对照**（塞 `Runtime/Evil.dll`、塞包内 `.cs`）+ 包内不含 `.scn/.res`；
4. `XWModRuntimeCompatibility.ValidatePackage`；
5. `SyncProject` 在工程副本上返回 `false` 且 `mod.json` 字节前后一致（= 编辑器不会重写）；
6. 入口类型本身：public / 非嵌套 / 有无参构造 / 实现 `IXWModRuntimeEntry` / FullName 相符 / 非 abstract / 无 `[Obsolete]`；
7. 插件依赖的**运行时接缝**（`Fire()`、`fireProjectileList`、`_fireProjectiles`、`fireAudioName`、`IsReleased`、`Owner`、
   `CharacterComponentRuntime` 不是 `GodotObject`、`Almanac.zombiePacketBank`、`TOWERDEFENSE_PACKETBANKS`…）；
8. `.tres` 靠**字段名**生效的接缝（`TowerDefenseZombieConfig.*`、`FireComponentDefinition.*`、
   `FireComponentFireProjectileConfig.*`、`CharacterArmorData.*`、`ArmorSlotConfig.*`、`AttackComponentDefinition.attackType`…）
   + 枚举事实（`PACKET_TYPE.ZOMBIE == 6`、`SHIELD == 4`、`DAMAGEABLE == 0x40`、`68 == SHIELD|DAMAGEABLE`、`68 & DROPABLE == 0`）；
   **8a**：用「禁用词表」反证发射配置里**没有**任何概率/随机角/时窗字段（需求 3/4 必须走插件的铁证）；
9. 读解包源码树核对需求依据 + 本包产物数值逐条对得上（含 **`FireComponent.cs` 本体实现**的 8 条文本断言）；
10. ★★ **ComponentSet 必修项的证据链 + 真跑 ModLoader 清洗函数**：
    * `zombieCompSet` 里**没有** `Fire` / 基场景自带 `ComponentSet` / `TowerDefenseCharacter.cs:703,1924` /
      `ComponentManager.cs:318,352` / 内置机枪豌豆僵尸场景覆盖 `ComponentSet` 的先例；
    * 本包场景根节点确实写了 `ComponentSet = ExtResource(…)` 且指向包内 `./…ComponentSet.tres`；
    * **反射直调** `ModLoader.SanitizeCharacterTextResource(LoadedMod, rel, abs, canStripScripts)`
      （private static）把本包 **10 个 `.tscn`/`.tres` 逐个喂进去**：全部返回 `true`（0 拒包），
      且**清洗后文件逐字节未变**（一条引用都没被剥）—— 因为它只剥 `type="Script"` 且 path 非 `res://` 的
      `ext_resource`，而本包的 ComponentSet 是 `type="Resource"` + `./` 相对路径，**不受影响**。

### 8.2 字节幂等 + 产物终检（`.cache/check_sgp_idempotent.py`）

```
第 1 次   pmod=181388 B  sha256=b054c21bbe8b2c69  条目 14
第 2 次   pmod=181388 B  sha256=b054c21bbe8b2c69  条目 14
第 3 次   pmod=181388 B  sha256=b054c21bbe8b2c69  条目 14
manifest.resources 与包内 13 个条目一一对应 OK
全部通过 ✓   ← 只读产物断言全 PASS（**条数以脚本实际输出为准，本处不写死数字**）
```

断言覆盖：血量算术（1180+70=1250）、啃食伤害 800、**不吃碾压**、二类防具 Paper 500 血、
防具槽沿用内置媒体名、Config 的 `armorData` 是包内相对路径、场景出生即戴 Paper、
场景复用内置读报僵尸脚本、场景自带 `Marker2D FireMarker`、
**★★ 场景根节点声明 `ComponentSet`（漏了 ⇒ 发射组件不创建 ⇒ 一颗豌豆都不出）**、
**★★ ComponentSet 指向包内相对路径**、组件集 = 父集 + 只加 1 个发射组件、发射位置指向 Marker2D、
**恰好 1 条发射配置**（一次 `Fire()` = 1 颗）、豌豆向前（speed 为负）、
**`FireComponentDefinition` 不带动画/精灵字段**（开火动画由插件直接驱动可见头，不走 `fireAnimeClips`）、
整包不覆盖移速/时标、卡片 ZOMBIE 类型 / 价格 100 / 冷却 5 秒 / 中文显示名 / 空解锁表、
runtime 四字段合规、provides 三键、翻译表为空、包内不含 `.cs/.scn/.res`、包内不含工程标记、
描述里没有翻译键残留、DLL 字符串指纹（含新增的「拿不到 `character.fire`」诊断文案）。

### 8.3 产物指纹

| 产物 | 大小 | sha256 |
|---|---|---|
| `dist/超级机枪读报僵尸.pmod` | 181 388 B | `b054c21bbe8b2c69a7d1a9a7b9c79ca1dcb43774921cf72f77523090ac3e5638` |
| `Mods/超级机枪读报僵尸.pmod`（安装镜像） | 181 388 B | **与上面逐字节一致** |
| `Runtime/ModAssembly.dll` | 24 064 B | `e28f38d73c0f84e4…`（四次改版 `SyncHeadPairs()` 新增生成点覆写；0 warning） |
| `…/Sprite/ZombieSuperGatlingPaper.tscn` | 7 131 B | **四节点**：身体根 + `HeadShadow` + `HeadHolder` + `Head`（§2.5 / §2.7 / §2.7.13）。⚠️ 全文**无** `usePos` / `useRotate` / `rotation`（改版 B 回退） |
| `…/Scene/ZombieSuperGatlingPaper.tscn` | 5 452 B | `HeadSlot` 保持原版三件套 + `FireMarker.position = (-35.697232, 94.988609)`（§2.7.14） |
| `…/Scene/ZombieSuperGatlingPaperFireComponentDefinition.tres` | 2 601 B | `firePosMarkerPaths` 指向 `HeadSlot/FireMarker`（§2.7.14） |
| `Resources/Animations/SuperGatlingPea.tres` / `.dat` / `SuperGatlingPeaAtlas.png` | 与**植物包同款三件套逐字节一致** | 由 `copy_skin_assets()` 从 `dist/超级机枪射手.pmod` 的构建目录镜像（§2.6①） |

DLL 字符串指纹（`#Strings` = UTF-8 / `#US` = UTF-16LE，**必须按字节搜**）：
`SuperGatlingPaperRuntimeEntry`（`#Strings`）、`character.fire` / `ZombieSuperGatlingPaper` / `GeneralZombie`（`#US`）。

### 8.4 安装状态

* `Mods/超级机枪读报僵尸.pmod` ✅
* `Mods/超级机枪读报僵尸/`（72 个标准目录 + 全量资源 + `.pvzmodeproject`）✅
* `Mods/enabled_mods.json` = `["discogargantuarpult", "PeaOverhaul", "supergatlingpaper", "supergatlingpea", "vampirepool"]` ✅
* `mod_editor_recent_projects.cfg` 已登记（4 条，未丢别人条目）✅

### 8.5 运行入口发现（`.cache/run_entry_sgp.py`）

离线复刻 `ModLoader` 的入口发现逻辑（`runtime_src/check_entry.cs`）：

```
python .cache/run_entry_sgp.py
# 对两份构建各跑一次；日志 .cache/_out_entry_sgp_{remake,console}.txt
```

| 构建 | 结果 |
|---|---|
| 重制版 | **11 PASS / 0 FAIL** |
| 控制台版 | **11 PASS / 0 FAIL** |

校验项：引用目录 / DLL 存在、`IXWModRuntimeEntry` 能在游戏程序集里找到、ModAssembly 全部类型列出、
入口类型**唯一命中**且 `public` 非嵌套、有公开无参构造、`Initialize`/`OnAllModsLoaded`/`Shutdown` 三方法齐全、
`Activator.CreateInstance` 成功。

---

## 9. 想改数值？只动一个地方

### 9.1 数值 / 卡片字段（改完**只需重跑生成器**，不用重编译插件）

全在 `build_zombie_super_gatling_paper.py` 顶部常量区（第 254–327 行左右）：

```python
HP_TOTAL = 1250.0                 # 有效总血（= HITPOINTS + HP_NEAR_DEATH）
HP_NEAR_DEATH = 70.0              # 濒死线；改用 0.0 = 取消濒死阶段（且总血仍为 1250）
HITPOINTS = HP_TOTAL - HP_NEAR_DEATH   # 1180.0
ATTACK = 800.0                    # 伤害 800（useAttackDps ⇒ 每秒）
ATTACK_TYPE = "Eat"               # 啃食（父组件集默认值，本包不覆盖）
COST = 100
PACKET_COOLDOWN = 5.0
ARMOR_NAME = "Paper"
ARMOR_DAMAGE_POINT = 500.0        # ★ 需求 5a 的「二类防具 500 血」
PEA_NAME = "Pea"
PEA_SPEED = -300.0                # 负数 = 「向前」（僵尸朝左；朝向镜像由 CreateProjectile 自动处理）
PEA_CATAPULT_HEIGHT = 400.0
FIRE_INTERVAL = 1.5               # ⚠️ 只有文档意义，真正节拍在插件里
FIRE_AUDIO = "ProjectileThrow"
FIRE_MARKER_PATH = "SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker"
```

改完 `python build_zombie_super_gatling_paper.py`；自检不过会**拒绝写盘**（退出码 3）。

### 9.2 玩法参数：节拍 / 概率 / 大招（改完**必须重编译插件** —— **两个工程都要**）

⚠️ **2026-09-22 起，数值的唯一真源不是本包入口源码，而是
`runtime_shared/GatlingVolleyCore.cs`**（植物版《超级机枪射手》共用同一份，见 §7.6）。

入口源码里只剩**转发**（仍是编译期常量，取值处零开销）：

```csharp
// runtime_src_zombie_super_gatling/SuperGatlingPaperRuntimeEntry.cs
private const double AttackIntervalSeconds = GatlingVolleyParams.AttackIntervalSeconds;
private const int    PeasPerAttack         = GatlingVolleyParams.PeasPerAttack;
private const double PeaSpacingSeconds     = GatlingVolleyParams.PeaSpacingSeconds;
private const double UltimateChance        = GatlingVolleyParams.UltimateChance;
private const double UltimateSeconds       = GatlingVolleyParams.UltimateSeconds;
private const int    UltimatePeas          = GatlingVolleyParams.UltimatePeas;
private const double ScatterHalfAngleDeg   = GatlingVolleyParams.ScatterHalfAngleDeg;
private const int    MaxPeasPerFrame       = GatlingVolleyParams.MaxPeasPerFrame;
private const ulong  StallThresholdMsec    = GatlingVolleyParams.StallThresholdMsec;
```

**要改值就改共用核心那一处**（`runtime_shared/GatlingVolleyCore.cs` → `GatlingVolleyParams`），
它同时决定植物与僵尸两边；改完**两个工程都要重编译、两个包都要重打包**：

```
python runtime_src_zombie_super_gatling/build_runtime.py --check    # 僵尸：编译 + 两次字节比对
python runtime_src_plant/build_runtime.py --check                   # 植物：同上
python build_zombie_super_gatling_paper.py                          # 僵尸：重打包 + 镜像到 Mods/
python build_plant_super_gatling.py                                 # 植物：重打包 + 镜像到 Mods/
python .cache/run_gates_sgp.py           # 僵尸闸门（两份构建各 292 项）
python .cache/run_gates_plant.py         # 植物闸门（两份构建各 52 项）
python .cache/check_plant_super_gatling.py   # 植物详细校验（259 项）
python .cache/check_sgp_idempotent.py        # 僵尸产物字节终检
```

⚠️ 生成器 `self_check()` 的**两问**守卫（§7.6 末）会在「只改了一半」时直接**拒绝写盘**（退出码 3），
所以「改了一边忘另一边」这条路已经被堵死 —— 不用靠记性。

⚠️ 生成器里的 `FIRE_INTERVAL = 1.5` 只影响 `.tres` 里的**文档值**
（`fireInterval`，真正节拍由插件决定）；它记录的是同一个数，改共用核心时建议同步。

### 9.3 豌豆出膛位置（改完**只需重跑生成器**）

想微调出膛点，改生成器里的 `FIRE_MARKER_POS`（对应产物场景里
`[node name="FireMarker" …]` 的 `position`）。见 §4.7。

### 9.4 头部的**姿态 / 位置**（改完**只需重跑生成器**；插件不用动）

生成器头部常量区（`build_zombie_super_gatling_paper.py` 的 `HEAD_*` 块）三件事：

| 想改什么 | 改哪个常量 | 必做步骤 |
|---|---|---|
| 头**摆不摆** | `HEAD_FIX_HEAD_ROTATE`（`False` = 跟 `anim_head1` 摆 / `True` = 冻成常量） | 切 `True` 时还要把 `HEAD_OFFSET` 按 `--node-rot-degs=<HEAD_FIXED_ROT_DEG>` 重解 |
| 头部**落点**（左右上下） | `HEAD_PLACE_SHIFT`（**屏幕空间** dx,dy；右上 = `+x,−y`） | 重解 `HEAD_OFFSET`（下面第 ① 步） |
| 层级 | `HEAD_NODE_Z_INDEX`（正整数；影子不写） | 无（但要同步 `HEAD_NODE_Z_INDEX_GOLDEN`） |

改完**必须**同步三处，否则金标断言 / 几何门 / C# 闸门会分别红：

```
# ① 取反解 offset（屏幕空间位移；冻结口径再加 --node-rot-degs）
python .cache/head_place.py --shift=8,-4
#    → OFFSET offset_rot=0.0000  node_rot=-8.0615  xy=-59.9377,-10.0515  screen_delta=8.0000,-4.0000

# ② 写进生成器：HEAD_PLACE_SHIFT / HEAD_OFFSET / HEAD_PLACE_SHIFT_GOLDEN / HEAD_OFFSET_GOLDEN
#    以及 C# 闸门里那条 "offset = Vector2(-59.9377, -10.0515)" 字面量

# ③ 验（四道，缺一不可）
python .cache/check_head_fit.py          # 几何门：屏幕位移逐字核对 + 覆盖率 + 官方样本 + 5 条负向
python .cache/_neg_test_head.py          # 负向测试：14 条（含注入式）
python .cache/_dump_head_block.py        # 肉眼看一眼真正会写进 .tscn 的那几行
python build_zombie_super_gatling_paper.py   # 重打包 + 镜像；失败会以退出码 3 拒绝写盘
```

辅助探针（只看不改）：

```
python .cache/_shift_probe.py    # 「头相对身体中心偏了多少」的量化表（定位移幅度用）
python .cache/_swing_probe.py    # 回退后逐帧的 net 旋转与整头落点（确认摆幅与不越界）

# 出「上一版 vs 本版」对照图（起止帧 / 位移量写在 spec JSON 里）
python .cache/head_ab.py --spec .cache/_ab_shift_amt.json \
       --out xxx.png --cols 4 --box=-135,-115,75,75 --scale=3
```

> ⚠️ **位移量只能加在锚点上**（`head_place.solve(shift=…)`），**别直接加到 `offset`**：
> 横向会**反向**（§2.7.13③）。`check_head_fit.py` 里有专门一条负向用例钉这个坑。
> ⚠️ 出对照图时 `solve_body_frame`（求解帧）与 `bf`（渲染帧）**必须分开** ——
> 场景里的 `offset` 是常量，跟着 `bf` 逐帧重解会画出「每帧都完美对齐」的**假象**。

---

## 10. 本次新踩到的**八**个坑（都已固化进代码/脚本）

### 坑 1：C# **不支持**相邻字符串字面量隐式拼接

离线闸门脚本里写了：

```csharp
string gp = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Normal/Scene/GatlingPea/"
                    "TowerDefenseZombieNormalGatlingPeaFireComponentDefinition.tres");
```

这在 **C / C++ / Python** 里合法，在 **C# 里非法**（`CS1003: 语法错误，应输入","`，
报错位置在行尾之后一格，极易看错）。**必须写 `+`**。

> 已固化：新增只读扫描器 `.cache/scan_adjacent_literals.py`，对任意 C# 文件扫
> 「行尾是 `"` 且下一行以 `"` 开头」的可疑写法。

### 坑 2：`dotnet run --file` 编译的独立程序**没有 GodotSharp 引用**

`GodotSharp.dll` 是运行期由 `AssemblyLoadContext.Resolving` / `LoadFromAssemblyPath` 载入的，
**编译期不存在**。所以脚本源码里**绝不能出现** `GodotObject` / `Node` 这类 Godot 类型的字面量
（`CS0246: 未能找到类型或命名空间名"GodotObject"`）。
需要判断类型关系时一律拿 `Type` 对象做反射：

```csharp
Assembly godotAsm = alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));
Type godotObjectType = godotAsm.GetType("Godot.GodotObject", throwOnError: false);
bool isGodotObject = godotObjectType != null && godotObjectType.IsAssignableFrom(compRuntimeType);
```

### 坑 3：★★ 角色场景**没声明 `ComponentSet`** ⇒ 发射组件根本不创建（本包第一版就是死在这）

**症状**：僵尸能正常走路、正常啃植物、血条也正常，但**一颗豌豆都打不出来**，
而且 `logs/godot.log` 里**连一条 warning 都没有** —— 三条日志全都没有：

```
[SuperGatlingPaper] 挂上第 N 只…      ← 没有
[SuperGatlingPaper] 拿不到组件…       ← 也没有（第一版这里是静默 return）
[SuperGatlingPaper] 读取僵尸发射组件失败… ← 也没有
```

**根因链**（逐行核过）：

1. `TowerDefenseCharacter.cs:703-704`：`[Export] public CharacterComponentSet ComponentSet { get; set; }`；
2. `TowerDefenseCharacter.cs:1911-1937 EnsureComponentManagerResource()`：
   `if (IsInstanceValid(ComponentSet)) componentManager.ComponentSet = ComponentSet;`
   —— **只有显式声明了才用你的；没声明就用组件管理器自己那份默认的**；
3. `ComponentManager.cs:318-352 InitializeResourceComponents()`：按
   `ComponentSet.GetCreationPlan()` 逐条 `entry.Definition.CreateRuntime()` ——
   **集里没有 `FireComponent` 的定义 ⇒ 这个 runtime 组件压根不会被 new 出来**；
4. 本包场景是 `instance=ExtResource("1")`（基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn`），
   而基场景 `:10` 写了 `ComponentSet = ExtResource("2")` →
   `TowerDefenseZombieComponentSet.tres:17` 的内容是
   `[BuffZombie, GroundHeightZombie, WaterInteraction, GroundMove, ZombieDeath, Garlic, Swim, AttackZombie]`
   —— **没有 Fire**。

⇒ 子场景不覆盖 ⇒ 默认集生效 ⇒ `GetRuntime<FireComponent>("character.fire")` 返回 `null`
⇒ 插件 `IsUsable(fire)` 判否 ⇒ 一条 hook 都挂不上 ⇒ 静默不打豌豆。

**修法**（就两行，见 §2.2 ①）：

```ini
[ext_resource type="Resource" path="./ZombieSuperGatlingPaperComponentSet.tres" id="15"]

[node name="ZombieSuperGatlingPaper" node_paths=… instance=ExtResource("1")]
ComponentSet = ExtResource("15")
script = ExtResource("2")
```

内置先例就在眼皮底下：`TowerDefenseZombieNormalGatlingPea.tscn:25` 同样写了
`ComponentSet = ExtResource("2")`，指向它自己那份含 FireComponent 的组件集。

> ⚠️ **最难的地方是它「不报错」**：`ModLoader.InferRuntimeEntry()` 只按 DLL 里的类型找入口，
> **不检查 `.tscn` 的内容** ⇒ 这类漏写在**加载期完全静默**，既没有拒包也没有告警，
> 只有进游戏放下僵尸才发现「怎么不打子弹」。
> **已三重固化**：
> 1. 插件侧 `TryHookCharacter()` 里那句静默 `return` 改成一次性警告
>    （`_fireMissingReported`），并把「场景漏声明 `ComponentSet`」直接写进警告文案；
> 2. 生成器 `self_check()` 第 **10b** 组断言：`ComponentSet = ExtResource("15")` 必须在场、
>    必须写在 `script` 之前、必须是**包内相对路径** `./…`；
> 3. 离线闸门新增 **9.10**（产物三连：声明在场 / 指向包内相对路径 / 组件集只加 1 个发射组件）、
>    **9.11**（把「基场景集不含 Fire」这条前提用源码字符串钉死，防止上游改版后假设失效）、
>    **9.12**（把本包 9 个 `.tscn`/`.tres` 真实文件喂给游戏自己的
>    `ModLoader.SanitizeCharacterTextResource`，断言 0 拒包 / 0 剥离 / 逐字节未变）。

### 坑 4：把判定抽成「共用源」后，**生成器里旧的「字面量直查」自检会假红**

`build_zombie_super_gatling_paper.py` 第 14 节原本逐个断言入口源码里含
`UltimateChance = 0.10` 这样的字面量。改成共用核心后入口只剩
`= GatlingVolleyParams.UltimateChance;` ⇒ 自检报 7 条「插件源码里找不到常量 X」并**拒绝写盘**（退出 3）。

**注意：自检是对的，它要防的就是漂移** —— 要改的是断言本身，不是绕过它。修法是把它升级成**两问**：

```python
# (a) 入口必须转发（谁写回字面量 / 改了转发名，立刻红）
fwd = re.compile(r"const\s+\w+\s+" + local_name
                 + r"\s*=\s*GatlingVolleyParams\." + shared_name + r"\s*;")
# (b) 字面量只在共用核心里，且等于生成器侧期望值
lit = re.compile(r"const\s+\w+\s+" + shared_name + r"\s*=\s*([0-9.]+)\s*;")
```

同一类假红还出现在植物侧校验器 `.cache/check_plant_super_gatling.py` 的 K15/K16
（一次 7 条 FAIL）⇒ 一并改成两问 + 补 K18/K19。
**教训**：任何「断言源码里含某个字面量」的检查，都会在「把字面量搬到别处」的重构里假红；
搬家时**顺手改断言**，别把自检关掉了事。

### 坑 5：★★ `.tscn` 节点头**收尾写成 `>`** ⇒ Godot **静默吞行**，节点根本没建出来

`[node name="Head" type="Node2D" parent="HeadHolder">` —— 最后一个字符是 `>` 而不是 `]`。
Godot **不报错、不警告**，只是把整行当普通文本跳过 ⇒ 节点不存在 ⇒ 头上没有美术。
而生成器自检之所以放行，是断言写成了**不带闭合括号**的前缀匹配（`… parent="HeadHolder"`），
等于把 bug 写进了断言里 —— **断言与实现同错**。

修法：模板改正之后，再加一条**通用**扫描（不再逐条写死关键词）：

```python
for name, body in (("Sprite", sp), ("Scene", sc)):
    for ln in body.splitlines():
        if ln.startswith("[node ") and not ln.endswith("]"):
            fails.append(f"{name} 场景的节点头语法坏了（必须以 `]` 收尾）：{ln!r}")
```

并在 `.cache/verify_head_structure.py` 里补反例「节点头结尾写成 `>`」（该脚本现 **15 条**，全过）。

> ⚠️ 同一轮还发现：`Read` 工具把这个文件的那一行**显示成** `…HeadHolder"]`（看着是对的），
> 而 `open(p,'rb').read()` 的十六进制里第 91 行末字节是 **`3e`（`>`）**。
> ⇒ **结构类结论一律以字节级读取为准；带渲染的预览不能当证据。**

### 坑 6：★★ 屏幕空间的「向右上微移」**不能**直接加到 `offset` 上（横向会反向）

2026-09-23 改版 B：用户要「头部初始位置从偏左向**右上**方向微微移动」。

直觉写法是把 `(+8,−4)` 加到 `HEAD_OFFSET` 上 —— **错**。`offset` 住在头的**局部空间**，
画之前还要过 `A = rot_scale(θ, sx=−1, sy=1)`（横翻把第一列反号）：

| 做法 | 屏幕上实际去哪 |
|---|---|
| `offset += (+6,−3)` | **(−6.36, −2.13)** ← 往**左下**跑了，方向完全相反 |
| `offset += (+8,−4)` | **(−8.48, −2.84)** |
| 加在**锚点**上（`solve(shift=(+8,−4))`） | **(+8.0000, −4.0000)** ← 逐字符合 |

修法：位移量只进 `head_place.Placement.solve(shift=…)` 的**锚点**，由它反解出 `offset`。
已固化成：
* `head_place.py` 的 `--shift=` 参数 + `screen_delta()`（回投出屏幕位移，可直接断言）；
* `.cache/check_head_fit.py` 里一条**专门的负向用例**（`base + (8,−4)` 必须被判失败）；
* 生成器里那个常量叫 `HEAD_PLACE_SHIFT` 而不是 `HEAD_OFFSET_DELTA` —— 名字就提示它是**屏幕空间**量。

> ⚠️ 同一个坑还有个**计量版**：`Skin.bbox` 给的是**精灵局部**坐标，身体的并集包围盒必须补上
> 父精灵 `offset = (−40,−80)` 才是世界里的位置；`_shift_probe.py` 第一版忘补，算出
> 「身体中心 x = +39.16」这种跟渲染图对不上的数。**凡是拿两个 bbox 相减，先确认它们在同一坐标系。**
> ⚠️ 第三个**工具版**：出对照图时「求解 offset 的帧」与「渲染的帧」必须分开
> （`head_ab.py` 的 `solve_body_frame` vs `bf`）。跟着 `bf` 逐帧重解 offset 会画出
> 「每帧都完美对齐」的**假象** —— 对「验证相对位置是否保持」这件事恰好是**反向**证据。

### 坑 7：把「挂在 `HeadSlot` 下」当成了「跟随头部动画」（2026-09-24）

生成器里原先写着「`FireMarker` 挂在 `HeadSlot` 下 ⇒ 自动跟随头部动画」——**这是错的**。
`HeadSlot` 是原版给护具 / DamagePoint 用的**静态插槽**：它的 `position` 不跟头部美术走；
护具看着贴在头上，只是因为**护具自己的 `offset` 补掉了这段差**。
⇒ 真因是「子弹生成点到底是什么」这件事**没查证**，只凭插槽名字想当然。
**修法**：① 顺着 `firePosMarkerPaths` 摸到 `FireComponent.cs:2698-2714`，确认取的是
`marker2D.GlobalPosition`；② 炮口点从 barrel 轨美术**独立反推**（不抄记忆里的常量）；
③ 两侧判据分别用「场景 .tscn 反读」与「美术反推」，**不同源**才有区分度。

### 坑 8（同一轮）：静态值只能对上**参考帧**，别把「能对上」当成「一直能对上」

第一版只改了 `FireMarker.position` 就以为完事 —— 但头是跟 `anim_head1` **逐帧摆动**的，
炮口每帧都在动（Idle 段炮口跨 x 4.85 / y 20.12 px；Eat 段 x 42.76 / y 78.20 px）。
实测 Idle 段静态点最大离线 **10.86 px**（bf20 时 9.03 px）。
**修法**：静态值当兜底 + 插件每帧覆写；并且把「天花板」**显式写进文档与断言输出**，
免得下次有人看见「参考帧 0.00px」就以为全帧都对。

### 顺带复习（上一版已踩过，这次仍然适用）

* 反射离线探针不能只用 `GetField`：`FireComponentDefinition.*` / `CharacterArmorData.armorLists` 等
  在源码里是 `public X { get; set; }` **属性**（这次还发现 `FireComponent.fireProjectileList` 是**字段**、
  `fireAudioName` 是**字段**、`IsReleased` 是**属性**）⇒ 断言一律写成「public 字段**或**属性存在」并回报形态。
* `Type.GetMethod(name, flags)` 有重载时会抛 `AmbiguousMatchException` ⇒ 统一「按名字取全部成员再筛参数个数」；
  查 private 成员要额外带 `BindingFlags.NonPublic`。

---

## 11. 进游戏测试 / 排查顺序

1. **先在游戏里确认 Mod 被加载**：看 `logs/godot.log` 里有没有
   `[ModLoader] package applied: … resources=11; runtimeEntry=SuperGatlingPaperRuntimeEntry`。
   没有这一行 ⇒ 包级别就没过（多半是 `manifest` / 路径 / 可执行文件闸门），先跑 §8.1 的离线校验。
2. **插件有没有起起来**：找 `[SuperGatlingPaper]` 前缀的日志，第一条应是
   `运行入口已初始化；PackageRoot=…；普攻 1.5s/7 颗（连发间距 100ms）；大招概率 10%，5s 内散射 300 颗 ±15°。`
   接着应有 `已挂载 process_frame；并发把「ZombieSuperGatlingPaper」补进卡库「GeneralZombie」的「Zombie」分类（⇒ 选卡界面可选）。`
3. **选卡界面 / 关卡编辑器能不能选到它**：这是插件职责 ②。选不到就找
   `已把「ZombieSuperGatlingPaper」补进卡库「GeneralZombie」的「Zombie」分类 ⇒ 选卡界面/关卡编辑器里可以选到它了。`
   没有这条 ⇒ `TOWERDEFENSE_PACKETBANKS` 还没加载完 / 卡库被别的 Mod 覆盖了。
3b. **图鉴僵尸页**（需求 8）：打开图鉴 → 僵尸页，本卡应当**只出现一条**。
   * 打了一次 `图鉴僵尸页去重：抹掉 1 条重复的「ZombieSuperGatlingPaper」…` ⇒ 正常（首次数到重复）。
   * 打了很多次同一条日志、`累计` 一直变大 ⇒ 异常（每次 `InitZombie()` 都重新造出重复，
     通常是「卡库那条被别的 Mod 又补了一遍」），把日志贴出来。
   * 打了 `图鉴僵尸页去重失败（本条只报一次；…）：…` ⇒ 反射字段名对不上（换游戏版本），
     **只影响图鉴去重**，僵尸本体 / 豌豆 / 选卡都不受影响。
   * 仍是两条且**没有任何**去重日志 ⇒ 扫描没覆盖到 `Almanac` 节点，或本卡只命中一条来源。
4. **豌豆打不打出来**：放下僵尸后应看到
   `已挂上第 1 只「ZombieSuperGatlingPaper」的发射组件。`
   然后每轮开火应看到 `触发大招（第 N 次）：5s 内散射 300 颗 ±15°，节拍 16.7ms/颗。`（约 10% 的概率）
   与 `大招结束：共散射 300 颗，用时 X.Xs。`
   完全没有豌豆 ⇒ 按这个顺序看：
   * `拿不到 SceneTree；豌豆不会发射（僵尸本身仍可正常行走/啃食）。` —— 插件没挂上帧循环；
   * **★★ `找到了「ZombieSuperGatlingPaper」但拿不到组件 "character.fire"（豌豆不会发射…）。`
     最常见原因：角色场景根节点漏了 `ComponentSet = ExtResource(…)`** —— 见 §2.2 ①（本包第一版就是这个）；
   * `已挂上第 N 只…` 没出现 —— `config.name` 没对上，或 ComponentSet 的 `InstanceId` 被改了；
   * `读取僵尸发射组件失败（本条只报一次；不影响僵尸正常行走/啃食）：…` —— `GetRuntime` 抛了；
   * `调用 FireComponent.Fire() 失败（本条只报一次；僵尸仍会行走/啃食）：…` —— 发射内部异常；
   * `fireProjectileList 有 N 条配置（预期恰好 1 条）；…` —— ComponentSet 形状变了（仍会发，但请核对）；
   * `发射节拍推进异常（本条只报一次，仍会继续尝试）：…` —— 节拍主循环异常。
5. **血量 / 伤害 / 二类防具 / 暴走**：
   * 本体承受总伤害 **1250** 后死亡，濒死线 70；
   * 报纸（**500** 点独立血量）被打掉时应播「报纸撕裂」音效 → 吼叫 → 换 `AngryWalk` 动画 + **移速 ×3**；
   * 啃食伤害 800/秒，**不会**碾压植物（没写 `smashAttack`）。
   数值只能实战验（离线闸门只证明「字段写对了、接缝都在」）。
6. **暂停/卡顿行为**：暂停游戏再恢复，**不应**出现「恢复瞬间一口气喷出几百颗」。若出现，
   说明 `GatlingVolleyParams.StallThresholdMsec`（= 250 ms，共用核心 §7.6）太宽松（或 `SceneTree.process_frame` 在暂停时不再发信号 —— 那就不会攒欠账）。

### ⚠️ 未验证项（如实记录）

* **插件在运行期的实际效果只能进游戏确认**（离线闸门只证明「接缝都在、字节确定、包能过审」，
  不能证明 Godot 运行时的节点树时序 100% 如预期）。
* **复用了内置读报僵尸的 `.cs`**：合规性已由 ModLoader 的脚本消毒规则证明（§3.4），
  但「Mod 场景引用游戏自带脚本」这条路**还没在真机跑过**（上一版僵尸 Mod 同样如此，实机也待确认）。
  ⇒ 需求 6（暴走 + 移速 ×3）能否实机复现，取决于这条路走不走得通。
* **`FireMarker.position = Vector2(0, 0)` 是推断值**（§4.7），实机看豌豆出膛点是否贴合头部。
* **需求 12 的判定已接上，但要实机确认两件事**（§2.6③）：① 图鉴/选卡预览里**不再**出现
  `BulletField could not be mounted` 报错；② 场上有植物时才开火、僵尸刚出生在屏幕外时不开火。
* **外观（2026-09-22 已按需求 2 换成「读报僵尸身 + 超级机枪头」）**：方案与依据见 §2.5，结构见 §2.7。
  离线只能验「节点 / 字段 / 图层号写对了」，**观感必须进游戏看**，重点四处：
  * **★ 头上不能是碎片拼贴**（09-22 实机截图那个现象，根因见 §2.7）⇒ 头必须**独立渲染**。
    离线已验：`Head` 挂在 `HeadHolder`（普通 `Node2D`）下、**不是**身体子精灵、29 层全 `true`、不写
    `parentSprite` / `insertLayerId` / `followParentSpriteLayerId`。**实机只看一件事：头是不是「超级机枪射手」。**
  * **★ 射击动画**：普攻/大招开火时头应切到 `HeadFire` 并保持约 **220ms**，之后回 `HeadIdle`
    （7 颗连发与 300 颗大招都只应表现为「整段保持开火姿势」，不抖）。头**不动**或**不切** ⇒
    看日志里有没有 `找不到可见头「Head」…`（`ResolveHeadForFire` 靠 `FindChild(..., owned: false)`）。
  * 头的位姿同步：`HeadShadow` → `Head` 每帧同步（1 帧延迟，低速下 < 1px）。
    若头**不跟身体走**（飘在原地）⇒ 影子被删了或 `parentSprite` 没了（§2.7.5）。
  * 原版读报僵尸的头有没有从头盔底下**透出来** ⇒ `BODY_HIDDEN_HEAD_LAYERS = (15..21)` 是否够。
    ✅ 已逐名核对：`anim_hair=15 / anim_head1=16 / anim_head_look=17 / anim_head_pupils=18 /
      anim_hairpiece=19 / anim_head_jaw=20 / anim_head_glasses=21`（`ZombiePaper.tres` 的 `layerDictionary`）；
    场景里 Sprite 根 + Scene 的 `ZombiePaper` 子实例**两处**都写了 `Animation/LayerVisible/<名> = false`，
    运行期还有第二道兜底（插件 `EnforceBodyHeadLayersHidden`，仅在表长 == 图层数时才改）。
* **★ 头部动画 + 位置 + 层级（需求 13/14/15/16；改版 A 方案见 §2.7.10、改版 B 见 §2.7.13）**，实机重点看四条：
  * **头在摆**（改版 B 需求 15）：`Head` 应能看出**轻微的摆头**（跟 `anim_head1` 走，Idle 净旋转 −16.03°..+1.01°）。
    若**完全不动** ⇒ 场景里残留了 `useRotate = false` 之类（改版 A 的冻结没撤干净）。
  * **相对位置不变**：头仍应贴着肩颈部随身体移动（引擎每帧覆写 `Position`）。若头**卡住不动** ⇒
    `usePos` 之类被写上了；若头**飘在原地不跟身体** ⇒ `HeadShadow` / `parentSprite` 没了（§2.7.5）。
  * **头压在身体与报纸之上**（需求 14，改版 B 未回退）：报纸/手臂/黑衣**不得**盖住头的任何部位，也不得与头**穿插**。
    `z_index = 1` 的生效前提是父链 `z_as_relative` 为默认 true（本包未改）。
    ⚠️ 若第 2 帧才正常、第 1 帧仍被压，多半是**首帧还没排进 `_unifiedDrawItems`**，
    先确认 `HeadHolder` 的父是身体根（`parent="."`）。
  * **构图是否协调**（需求 16）：头的初始落点已按 `HEAD_PLACE_SHIFT = (8,-4)` 向右上挪过
    （`offset` 重解为 `(-59.9377,-10.0515)`）。**嫌不够/过头就这么调**（三步）：
    ```
    # ① 取新 offset（屏幕空间 dx,dy；右上 = +x,−y）
    python .cache/head_place.py --shift=12,-6
    # ② 把新值写进生成器三处：HEAD_PLACE_SHIFT / HEAD_OFFSET / HEAD_PLACE_SHIFT_GOLDEN(+HEAD_OFFSET_GOLDEN)
    # ③ 验
    python .cache/check_head_fit.py && python .cache/_neg_test_head.py && python build_zombie_super_gatling_paper.py
    ```
    ⚠️ **别把位移量直接加到 `offset` 上**（横向会**反向**，§2.7.13③）；也别只改 `HEAD_PLACE_SHIFT` 不改 offset。
    若想改成「摆正不摆头」，把 `HEAD_FIX_HEAD_ROTATE` 改回 `True` 并**重解 offset**
    （`python .cache/head_place.py --node-rot-degs=0`）。
  * ⚠️ 「离线只能验模型自洽 + 官方样本交叉校验 + 覆盖比例」，**观感最后还得进游戏看**。
  * ⚠️ **别再把官方 `ZombieNormalGatlingPea.tscn` 的 `offsetRotate = -0.25` 当对齐目标** ——
    那是另一套美术的调参值，改版 A 就是这么选错成 −14.32° 的（§2.7.10③）。
  > 本轮曾评估「换成机枪僵尸贴图」（`ZombieNormalGatlingPea.tscn`），**用户决定不换** ——
  > 既然「打不出子弹」的真因是 §2.2 ① 那个 `ComponentSet` 缺声明（纯数据问题），就没有换贴图的必要。
  > 记一笔当时的取证结论，免得下次重走：机枪僵尸精灵的动画数据是 `ZombieNormal.tres`，它**只有**
  > `Walk1/Walk2`、`Idle1/Idle2`、`Death1/Death2`、`Swim`、`Waterdeath`，**没有** `Gasp` / `AngryWalk` / `AngryEat`；
  > 而本包需求 6 走的是内置读报僵尸脚本的「护具碎 → `ToGasp` → 播 `Gasp` → `AnimeCompleted("Gasp")` → 移速 ×3」链路。
  > ⇒ 一旦换成机枪僵尸精灵，`SetAnimation("Gasp")` 播不出任何 clip ⇒ `AnimeCompleted` 永不触发 ⇒
  > 僵尸会**卡在 `zombie.paper.gasp` 状态**，需求 6 直接失效（届时必须改由插件轮询 `armorList` 补 ×3）。
  > 换的话还要连带改 `damagePart`（`ZombieNormal*` 那套伤害点/护具槽，它们的 `slotPath` 是
  > `BucketSlot`/`ConeSlot` 而非 `HeadSlot`）、开火点（机枪僵尸自带 `Head/Marker2D`，可替掉本包自造的 `FireMarker`）等一串。
* **代价（需求本身带来的）**：本卡进了共享卡库，所以「随机取卡 / 植物礼盒 / debug 全开卡池」
  都可能把它给你 —— 这是「能被选到」的必要条件。
  ✅ 图鉴僵尸页的**重复条目已在运行期消除**（§7.3，2026-09-22），不再有两份。
* **联机不同步**：10% 骰子用的是引擎随机源（真随机），联机会与主机不同步 —— 这是需求 4
  「真随机」的**刻意**代价，已在插件注释里标注。

---

## 12. 交付物终检（`.cache/check_sgp_idempotent.py`）

**只读**的收尾核对脚本（内部会重跑 3 次生成器验幂等），把「日志里能看到的东西」换成「本地就能断言的字节事实」：

```
python .cache/check_sgp_idempotent.py
# 3 连跑对比 sha256；只读断言全绿；退出码 0 = 全绿，3 = 有 FAIL
# 本轮实测：3 次构建同 sha256（b054c21bbe8b2c69）、14 个条目、只读断言全绿
```

它断言的四组事实：

| 组 | 断言 | 结果 |
|---|---|---|
| `.pmod` 两份位置 | `dist/` 与 `Mods/` 各 **181,388 B**、sha256 `b054c21bbe8b2c69…`、**逐字节一致** | PASS |
| zip 结构 | 条目数 **14**、`mod.json` 排第 0、**不含 `.cs` / `.pvzmodeproject` / `.uid` / dotfile**、条目集 == 构建目录（去掉 `.pvzmodeproject`） | PASS |
| `mod.json` 字段 | `schemaVersion=2`、`id`、`name`（中文显示名）、`translations=[]`、`runtimeAssembly` 字面量、`runtimeEntryType`、`runtimeApiVersion=1`、`runtimeAssemblyPolicy=optional`、`resources` == zip 去 `mod.json`（规范序）、`provides` 三键 | PASS |
| `Runtime/` | 只有 `ModAssembly.dll`、**24,064 B**、sha256 `e28f38d73c0f84e4…`、**包内 DLL 与构建目录一致**（且含共用判定核心符号 `GatlingVolleyJudge`） | PASS |
| Mods 镜像 | `STANDARD_DIRS` 恰 72、镜像文件集 == 构建目录、镜像目录集 ⊇ 72 标准目录 | PASS |
| 装订 | `enabled_mods.json` 含 `supergatlingpaper` 且**无大小写重名残留**、未丢别人的 4 条、最近工程记录**无 CR** | PASS |

> 写这类脚本时的三个老坑（上一版记过，这次仍然适用）：
> ① 「构建目录文件数」≠「zip 内条目数」（前者多一个 `.pvzmodeproject`）；
> ② 「Mods 镜像子目录数」= 72 标准目录 + 本包自己造的 `Runtime` + 角色 5 层子目录；
> ③ manifest 里的字段真名是 **`runtimeEntryType`**（不是 `runtimeEntry`）。
> 另外 **zip 条目顺序 ≠ 文件系统字母序**（`mod.json` 被强制排第 0）⇒ 比对条目时比**集合**，顺序另立断言。
