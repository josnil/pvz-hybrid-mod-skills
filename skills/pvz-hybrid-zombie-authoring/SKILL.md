---
name: pvz-hybrid-zombie-authoring
description: 为《植物大战僵尸杂交版》(Godot 4 + C#) 从零制作或改造一个「僵尸」Mod 的端到端流程——选基底僵尸、建包（13 个文件）、本体配置（血量/濒死/啃食伤害）、**补数值与属性（生命值/啃食伤害/伤害类型 attackType/移动速度/手册五行属性块）**、**让僵尸真的能往前走（动画 `_ground` 根运动层）与调速**、护具 Armor 三件套、换头「三节点」结构、换外观（经典 reanim 官方素材直转）、给僵尸加发射（自建 Fire 组件 + 托管插件驱动节拍）、植物僵尸共用的攻击判定（没植物不开火、进场才开火）、子弹生成点对齐炮口（FireMarker）、**用 buff 做控场（让全场植物停止发射的攻速归零 buff）**、**多体节 BOSS（N 个独立受击判定共用一条血条 / `physique = 6` 启用内置 Boss 血条 / 多部件素材拼链）**、图鉴去重，以及闸门/负向测试/幂等全套离线验证。当用户要求「做个僵尸 Mod」「把僵尸换成 XX」「给僵尸换头/换贴图/换动画」「让僵尸会开枪/会发射」「僵尸加护具」「植物僵尸的攻击判定」「改僵尸血量/伤害/移动速度/伤害类型」「**僵尸不动/不往前走/不移动/原地滑步**」「让植物停止发射/暂停行动/控场」「**做个多体节 BOSS / 多个部位共享血条 / Boss 血条**」「**给几张部件图自行裁剪组装 / 体节加长 / 消接缝 / 让身体自然弯曲 / 蛇形游走**」「**走路头部太飘 / 头部晃动 / 让头部稳一点** / **攻击时刀刃朝向不对 / 刀刃横着砸 / 让刀刃朝下刺 / 武器朝下戳** / **做这个僵尸需要什么素材 / 我该给你什么图 / 有素材吗 / 直接复用原版素材行不行 / 素材要什么格式和尺寸**」或提到 .pmod / Zombie / 僵尸 / 护具 / Armor / FireMarker / 子弹生成点 / attackType / walkSpeedScale / **_ground 根运动** / AttackSpeedDown / physique / BOSS / BossHealthBar / DamagePoint / 最小转弯半径 / R_min / seg_stretch / OVL / 接缝 / **素材 / 逐帧 PNG / reanim / tileSize / RasterComposite / 部件图** / ModAssembly.dll / **csproj `<AssemblyName>` / 程序集名唯一 / 安卓加载失败 / runtimeAssembly 能不能改** / 图鉴僵尸页 / **倒地（保 1 血 / 濒死不倒 / 场上有同伴才倒）/ 单膝跪地 / 跪姿 / 突进冲撞 / 三档受损贴图（面具 / 盾分档）/ 盾碎后贴图「复活」/ 防具换图不生效 / 破损贴图不显示 / 动画冻住不动（卡在第 0 帧）/ 免疫魅惑 / 生成时召唤同伴 / 自定义防具盾 / 托管 DLL 状态机 / **素材里没有想要的姿态（膝触地 / 单膝跪 / 撑刀插地）/ 程序化关节装配摆姿态 / 关节整组旋转 / 倒地入场动画 / 复用源 clip 播一次 / 全员倒地即死 / 换图静默失效 / UpdateMediaReplace / G30 防回归 / **换图真根因（引擎只认预烘 Texture2DArray 图集 / DisableUnsharedMediaReplaceTextures / SetReplace 在 pmod 里不可能生效）/ 烘进动画自带图集 / SetFliter 切层 / GetFliter 层名存在性自检 / 三档受损图是图集里的兄弟部件（parts_*.json 的 chain / 子节点 matrix 逐位相同）/ 同尺寸兄弟图层隔离归一化 + 统一媒体画布 / layerVisible 索引不要 ±1 / 生成时按概率替换（5% 概率替换成某僵尸）/ BattleEventBus.OnCharacterSpawned 是死代码 / WeightPickMathine 只用于图鉴 / PacketBank 是纯白名单无权重 / Discover 轮询 + 实例 id 去重 + 先造后删 / SceneTree.NodeAdded / G31 防回归 / 版本号替换脚本必须在编译前跑完（DLL 过期）/ 闸门方法体断言要对齐真实调用链 / **替换只出一个（别变出一对）/ 掐断派生链 / 派生链 NoFollower / 出生召唤同伴不要重复触发 / 登记与置位分两步（别在 CreateCharacter 刚返回就建状态 / 抢先 HookUnit 会丢事件订阅）** / **替换后直接出现在指定列（放到第 9 列 / 从入口走进来 / 挪到第 N 列再变身）** / **凭空把单位挪到指定格＝三件套（1-based gridPos / GetMapCellPosCenter 格子中心 / 该格 GetGroundHeight 高度曲线）** / **groundHeight 要按目标格重算（否则先浮空再被 lerp 拉回地面）** / GetMapGridNum / GetMapCellPosCenter / CheckMapGridPosIn / static GetMapCell / **GetMapCellPosCenter 与 GetMapCellPlantPos 是对偶（中心 vs 格角）别混用** / **gridPos 是 1-based（不是 0-based）** / **TowerDefenseFloorQX.SpawnHologramProjection（按行列生成僵尸的引擎先例 / 行列夹取口径）** / **地图 gridNum 实测（Backyard/Valley 9x6、CreekLawn/MagicGarden 9x5、FrontlawnBig 11x7、FrontlawnSuperBig 27x15）** / **第 9 列只在标准图等于最右列（大图 11 列 / 超大图 27 列不是）** / **按地图取点必须有兜底（Instance==null 就退回原位置，别把整个机制吞掉）** / **走 CreateCharacter 不要重复补引擎已经做的事（内部已 AddChild / packetConfig.Create 内部已 IsZombieWalk）** / G32 防回归 / **撤销 / 回退一个已上线的机制（回退类改动优先整体删除而不是留 bool 开关）** / **回退时闸门断言要翻成负向（不该出现的必须不出现，别只删断言）** / **哪些守卫该留：问「那道守卫在旧功能里也有吗」（IsFollower 防套娃必须留）** / **替换出来的僵尸也带同伴 / 一次触发本体+派生一对 / 兵力口径 5%≈10%** / **兵力量化要说清并记录权衡，主人知情后仍选就停止重复提议** / **核验 .NET DLL 字符串用 UTF-16LE 不是 UTF-8（utf-8 搜全盘 False）** / **注释不进 DLL，核实历史说明注释要读源码** 时使用。
agent_created: true
---

# 制作 PvZ 杂交版「僵尸」Mod —— 端到端流程

> ## 🏛 官方模板基线（最高优先级 · 2026-10-24 对齐）
>
> 本技能的**流程 / 字段契约 / 身份 / 版本 / 构建 / 安装 / 验证 / 目录**一律以
> [pvzhe-mod-template](https://github.com/axh-xecoy/pvzhe-mod-template) 为准（僵尸侧入口 `pvzhe-zombie-create`，
> 按需组合 `pvzhe-character-fire` / `character-armor` / `character-skin` / `pvzhe-resource-edit`）。
> **重复或冲突一律以模板为准**；本技能只保留模板未覆盖的**实测细节**。
> 全文与冲突表：[`../pvz-hybrid-mod-authoring/references/official-template-baseline.md`](../pvz-hybrid-mod-authoring/references/official-template-baseline.md)
>
> 速记：`schemaVersion: 3` ｜ `version` 用 **SemVer 三段** ｜ `id` 为 `[0-9a-z_.-]` 1–32 位 ｜
> 构建走 `tools/mod.py prepare/build/check/install/verify` ｜ 判据来自**已发布发行版**（无需源码）｜
> 包内禁止宿主 DLL / 整份 `bin/`。

> 姊妹技能：`pvz-hybrid-mod-authoring`（全量/通用，含包格式与编辑器）、`pvz-hybrid-plant-authoring`（植物端到端）。
> 本技能只讲**僵尸**这条路，以及它与植物的**每一个差异**。
>
> ★★★ **开工第一件事是「问素材」，不是「写代码」**：先确认用户手上有哪些素材（**部位 / 格式 / 尺寸**），
> 并**主动告知可以复用原杂交版已有的素材**（`Chapter1\*` 里的基底僵尸、护具、独立头、卡库都能直接照抄）。
> 问卷模板 + 官方规格基准（单帧 / 图集 / 帧号布局）+ 素材来源地图 + 没有素材时的降级路线
> ⇒ **`references/zombie-asset-requirements.md`**（Step 0 强制先读）。

## ★ 踩坑总表（僵尸专场） —— `references/zombie-pitfalls.md`

本项目开发过程中**实际踩过**的坑，已统一成「**现象 · 触发场景 · 原因 · 正确做法**」四段式。
**开工前先扫一遍；出问题时先 Ctrl-F 现象里的一句话**（如「零日志」「假绿」「整包被拒」「原地滑步」）。

## 0. 权威来源与边界（务必先看）

| 优先级 | 用途 | 路径 |
|---|---|---|
| **① 上游模板（权威）** | 制作入口与契约 | 模板 `.agents/skills/pvzhe-zombie-create/`，按需组合 `pvzhe-character-fire` / `character-armor` / `character-skin` / `pvzhe-resource-edit` |
| **② 本仓库通用** | 包格式、清单、版本、身份 | `pvz-hybrid-mod-authoring` + `references/official-template-baseline.md` |
| **③ 本技能（僵尸细节）** | 顺序、硬约束、实测数值 | 本文 + `references/*` |
| ④ 基底僵尸（读报/普通/路障…） | 资源线索 | `Asset\Anime\Character\Zombie\Chapter1\<Name>\` |
| ④ 内置僵尸基场景 | 资源线索 | `Prefab\TowerDefense\Character\TowerDefenseZombie.tscn` |
| ④ 内置僵尸组件集 | 资源线索 | `Prefab\TowerDefense\Character\ComponentSets\TowerDefenseZombieComponentSet.tres` |
| ④ 护具体系 | 资源线索 | `Registry\Armor\`、`Script\Component\TowerDefense\Character\Armor\` |
| ④ 发射体系 | 资源线索 | `Script\Component\TowerDefense\Character\FireComponent\FireComponent.cs` |
| ④ 图鉴 | 资源线索 | `Prefab\GUI\DialogBox\Almanac\Almanac.cs` |
| ④ 用户 Mod 目录 | 安装位置 | `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\` |
| ④ 实况日志 | 验证证据 | 同上目录 `PVZHE_Logs\`、`logs\godot.log` |
| ⑥ 源码（可选内部查证） | 只用于解释机制 | 本机解包树 `.cs`（**不作为他人前置**） |

> 冲突时按 **① 模板 > ② 本仓库通用 > ③ 本文** 取舍。
> 上表 ④ 行只是**资源线索**，字段真伪仍须回到已发布 DLL/PCK 与实际运行核验。

**边界（模板口径）**：上游模板**不使用**游戏内「PVZ Mod 编辑器」（F3），也**不需要游戏源码**；
`.pmod` = ZIP（`mod.json` + `Runtime/ModAssembly.dll` + `resources` 显式列出的自有资源），**不是** Godot PCK。
旧文「动手前先确认用户已有可复制的生成器」**作废** —— 构建入口统一为 `tools/mod.py`；
本机 `build_zombie_super_gatling_paper.py` 等生成器**仅作历史参考**，不再要求他人复制。

---

## 1. 先做四个决定（决定后面 80% 的工作量）

### 决定 A：复用什么基底僵尸？

| 基底 | 特点 | 什么时候选 |
|---|---|---|
| `Chapter1\Paper\`（读报僵尸） | **自带护具 + 状态机 + 暴走**（`ArmorHitpointsEmpty("Paper")` → `ToGasp` → 3 倍速） | 要护具 / 要「血量掉光后暴走」的机制 |
| `Chapter1\Normal\`（普通僵尸） | 最干净：只有身体 + 头 | 只换外观、不加机制 |
| 其它（路障/铁桶/舞王…） | 各自带护具或特殊动画 | 想白拿它的护具/动画 |

⚠️ **基底僵尸的「脚本」不能复制进包**（包内禁 `.cs`）—— 见 Step 4 的剥离手法。

### 决定 B：要僵尸「发射」吗？

**僵尸默认没有 `FireComponent`**（`TowerDefenseZombieComponentSet.tres` 里没有 Fire，只有 Armor/Attack 等）。
「啃食」是 `AttackComponent` 默认的 `attackType = "Eat"`，**不是发射**。
⇒ 只要想做「会开枪的僵尸」，就必须：

1. 数据侧：新建 `…ComponentSet.tres`，**基于内置僵尸组件集再加 1 个 FireComponent**；
2. 代码侧：写托管插件（僵尸没有植物那种「内置发射动画链」，节拍要自己驱动）。

### 决定 C：外观走哪条路？

* ★ **先定素材**：这条路选哪条，取决于**用户手上有什么**（逐帧 / reanim / 参考图 / 部件图 / 什么都没有）
  ⇒ 先读 `references/zombie-asset-requirements.md`（含「能复用原版就别要新素材」的省事顺序）。
* **官方素材直转**（首选）：经典未重置版 reanim → 重置版 `.dat`/`.tres`/图集（见 `references/zombie-skin-and-head.md`）。
* **只换头**：走「三节点换头」（`HeadShadow` + `HeadHolder` + `Head`）—— 见 Step 5 与 references。
* **自制逐帧**：能走，但要处理「自制 `.dat` 皮肤静止」⇒ 运行期 `forceLocalRender` + `forceCpuPoseRender`。

### 决定 D：要不要图鉴 / 卡库？

僵尸的卡库是 `GeneralZombie`，**补一处 = 选卡界面 / 关卡编辑器 / 图鉴僵尸页同时生效**
（`Almanac.cs:220` 取的是**同一个实例**，不像植物页那样深拷贝）。
但副作用是**图鉴僵尸页会多出第二条** ⇒ 见 Step 9。

---

## 2. 关键路径（按需查证）

```
<包>/
  mod.json
  Resources/Cards/<Key>.tres                                  ① 卡片（类型 ZOMBIE）
  Resources/Characters/Zombies/<Key>/Config/TowerDefense<Key>.tres       ② 本体配置
  Resources/Characters/Zombies/<Key>/Packet/<Key>.tres                 ③ 卡包条目
  Resources/Characters/Zombies/<Key>/Scene/<Key>.tscn                  ④ 场景
  Resources/Characters/Zombies/<Key>/Scene/<Key>ComponentSet.tres      ⑤ 组件集
  Resources/Characters/Zombies/<Key>/Scene/<Key>FireComponentDefinition.tres  ⑥ 发射定义（要发射才需要）
  Resources/Characters/Zombies/<Key>/Scene/<Key>AttackComponentDefinition.tres  ⑥b 攻击定义（要改「伤害类型」才需要）
  Resources/Characters/Zombies/<Key>/Sprite/<Key>.tscn                 ⑦ 精灵场景
  Resources/Characters/Zombies/<Key>/Armor/Zombie<Key>ArmorData.tres   ⑧ 护具数据
  Resources/Characters/Zombies/<Key>/Armor/Config/Zombie<Key>Armor<X>.tres   ⑨ 护具槽配置
  Resources/Animations/<Skin>.{dat,tres,Atlas.png}                     ⑩ 外观三件套（换贴图时）
  Runtime/ModAssembly.dll                                             ⑪ 托管插件（**这个路径不许改**）
  <中文名>.pvzmodeproject                                              ⑫ 工程标记（**不进包**；时间戳必须读回旧值，否则字节不幂等）
```

**路径硬约束**：`Resources/Characters/Zombies/<Key>/{Scene,Sprite}/<Key>.tscn` —— 恰 **6 段**；
类别目录必须是 `Zombies`；文件名必须等于 `<Key>`。违反 = `ModLoader.InferRuntimeEntry` 推不出类别。
★ **Config 故意不遵守这条**：② 是 `Config/TowerDefense<Key>.tres`（带 `TowerDefense` 前缀），
与 ④ 场景的 `<Key>.tscn` **不对称**，这是既有可用包（如 `StarrySerpent`）的惯例，别「顺手统一」。

**⚠️ 把场景命名成 `Scene/TowerDefense<Key>.tscn` 会怎样（实测症状，2026-10-02）**：
`InferRuntimeEntry` 只从 `.../Scene/<basename>.tscn` 反推 Character 键 ⇒ 它推出 `TowerDefense<Key>`，
而 manifest 声明的是 `<Key>`，于是离线闸门报（**3 条 FAIL**）：
```
FAIL [binding.undeclared] 资源存在但 manifest 未声明 provides/overrides: Character/TowerDefense<Key>
```
**诊断陷阱**：报错里出现的是**场景基名**（`TowerDefense<Key>`）而不是你声明的键，
很容易让人去改 manifest（错！）—— **要改的是文件名**。修完再跑必须是 `FAIL=0`。
（`verify_pmod.py:101-106` 与 `ModLoader.InferRuntimeEntry` 同源；生成器可在打包前
`import verify_pmod.infer_runtime_entry` 自证，别等装机才发现。）

**⚠️⚠️ `provides.Packet` 写几个键，就必须发几张 `Resources/Cards/<Key>.tres`（实测症状，2026-10-02）**：
Packet 的**唯一注册来源**是 `Resources/Cards/<Key>.tres`（`ModLoader.cs:1082` 前缀表）；
包内 `Resources/Characters/Zombies/<Key>/Packet/<Key>.tres` **只是镜像、不注册**。
`ModLoader.ValidateManifestRegistrations`（`ModLoader.cs:1519-1545`）要求 `provides` 里**每个键都真的被注册**，
少一个即：
```
WARNING: required manifest runtime entry is not registered: <id>: provides: Packet/<Key>
WARNING: failed to apply enabled package: <id>
[ModManager] enabled runtime apply complete: 7/8 packages        ← 少的就是你的包
```
⇒ `ApplyMod` 返回 false ⇒ **整包不生效**（僵尸一个都不会出现）。
★★ **症状极具误导性：零崩溃、零 ERROR，插件还会照打 `运行入口已初始化`**
（运行时入口先于校验执行：`ModLoader.cs:672` vs `:678`），所以「插件日志正常」不等于「包生效了」。
★ 另一条同族判据：日志里出现 **`unsupported package file`** 也是**失败证据** ——
`XWModManager.cs:932-934` **只在失败分支**才把全部 diagnostics `PushWarning` 出来；包成功时一条都不打。
⇒ **别 grep `ERROR`，要盯 `package applied: <id>; resources=N` 与 `enabled runtime apply complete: n/N`.**
★ 修法：**按「来源」给每个 Packet 键配一张卡**。若某些角色只是被召唤物（不需要玩家选卡），
也有两条正路可选 ——
(a) **照样发卡**（先例：`向日葵女王僵尸.pmod` = 召唤者 + 被召唤物 = 2 角色 2 卡），
    发卡**不会**污染选卡表（引擎不合并 Mod 注册进卡表），只是让它们进图鉴 + 能被注册；
(b) **不发卡、也不把它写进 `provides.Packet`**，插件改用运行时注册表的 `Character` 直取 `PackedScene` 生成
    （先例：`星空机械蜿蜒` 的 9 体节 + 尾 —— `provides.Packet` 只列头段 1 个）。
⛔ **绝不可以**「声明了却不注册」（本坑），也不可以「注册了却不声明」（`binding.undeclared`）。
★ 生成器侧把它钉死：`Resources/Cards/*.tres` 文件名集合 ⇄ `provides.Packet` ⇄ `provides.Character`
**三者两两相等**，并双向查漏；`verify_pmod.py` 的 `provide.unregistered`（配 `strict_provides=True`）是第二道。

**★★ 「有卡」≠「选卡界面能选」（2026-10-02 实测澄清）**：
引擎**不会**把 Mod 注册的 Packet 自动并进卡表 —— `ResourceManager.BuildExpandedPacketBanks:638-647`
只从内置 `Asset/Config/PacketBank/PacketBankResource.json` 构建、**不合并** Mod 注册；
`TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync:509-514` 是 `packetBankData.category[分类]` **直读**。
Mod 卡的**自动**去处只有**图鉴**的僵尸页（`Almanac.cs:427` → `XWModContentCatalog.GetPackets(plants:false)`）。
⇒ 要在**选卡界面**里选到，必须由**插件主动往卡库实例 append**
（先例：`runtime_src_zombie_super_gatling/SuperGatlingPaperRuntimeEntry.cs` 第四/五节，
补进共享卡库 `GeneralZombie` 的 `Zombie` 分类；日志会打「已把「…」补进卡库…」）。

**★★★ 程序集名的硬约束（安卓专属，`Runtime/ModAssembly.dll` 那条不算）**：
包内 `Runtime/ModAssembly.dll` 的**路径**一个字都不能改，但 `.csproj` 里的 `<AssemblyName>`
**必须改成自己的 `id`**（`id` 取自 `mod.json`，如 `<AssemblyName>supergatlingpaper</AssemblyName>`）。
安卓全 Mod 共用一个非可回收加载上下文，程序集名撞车会直接
`Android Mod assemblies share one non-collectible context, so main assembly names must be unique`
⇒ 第二个 Mod 加载失败。**详见 `references/zombie-package-and-gates.md` §5.1**。

---

## 3. 标准流程（12 步）

### Step 0 — ★★★ 先问素材，再把需求问全

**第一件事永远是「问素材」**（素材形态决定路线与工作量；而且用户往往不知道原版素材可以直接复用）。
问什么、怎么问、每类素材的规格基准与降级方案 ⇒ **`references/zombie-asset-requirements.md`**。

> **准则：能复用原版就别要新素材。** 顺序是
> ① 复用原版外观（`Chapter1\Normal` 最干净）→ ② 换头（身体用原版 + 头换一个，官方已有
> `Asset\Anime\Character\Zombie\Chapter1\Normal\Sprite\Sunflower\SunFlowerHead.tscn` 这种先例）→ ③ 要一张参考图走抠像 → ④ 部件图拼链（最费）。
> **别一上来就要求用户交「图集」**：图集排版是脚本的事，用户只需给**逐帧 PNG 序列 / reanim / 参考图**之一。

素材确认后，再问全需求：① 基底僵尸？② 要不要护具、护具多少血？③ 要不要发射、射速/弹数/散射？
④ 头部贴图换不换、用哪个角色的？⑤ 要不要「没植物不开火、进场才开火」？
⑥ 血量/啃食伤害/卡片价格冷却？⑦ 大招之类的特殊机制？
**缺一项后面就得返工**（尤其④⑤，它们决定要不要写插件）。

### Step 1 — 复制生成器，别从零写

```bash
cp build_zombie_super_gatling_paper.py build_zombie_<新Key>.py
```

生成器要包含：`self_check()`（含 `*_GOLDEN` 金标）、场景/配置渲染函数、`Build` 落盘、
`dotnet build` 调用（或独立 `build_runtime.py`）、打包 `.pmod`、安装到 `Mods/`、镜像到 `%APPDATA%`。
**改常量永远只改一个文件**。

### Step 2 — 定 Key 与中文名

* `<Key>`：ASCII，如 `ZombieSuperGatlingPaper`（**进图鉴的键、也是插件识别角色的锚**）。
* 中文名：`translate` 里**直接写中文**（不需要 `translations.csv`；写了反而要多维护一份）。
* 每个 `.tres` 的 `script_class` / `metadata/_custom_type_script` 要与内置基底对齐。

### Step 3 — 包内 13 个文件

逐个从基底改。最容易漏的是 **③ Packet**（没它卡在包里但选不到）与 **⑨ 护具槽**。

### Step 4 — ★★ 场景必须**显式声明** `ComponentSet`（在 `script` **之前**）

基场景 `TowerDefenseZombie.tscn:10` 自带 `ComponentSet = ExtResource(...)`
⇒ **子场景不写就继承它**。而它指向的 `TowerDefenseZombieComponentSet.tres` 里**没有 FireComponent**
⇒ 「僵尸不会开枪」而且是**零日志**（组件根本没被创建）。

```gdscript
[node name="Zombie<Key>" instance=ExtResource("1")]
ComponentSet = ExtResource("<你的组件集 id>")     # ← 必须在 script 之前
script = ExtResource("<内置僵尸脚本 id>")
```

**继承内置脚本时**：包内**禁止** `.cs` / `.scn` / `.res` ⇒ 只能引用**内置**的 `res://` 路径，
且要**剥掉**基底场景里指向包内的 `ExtResource` 行（否则 ModLoader 会拒整包）。

### Step 5 — 精灵场景：换头走「三节点」

**为什么不能直接换子精灵的贴图**（我踩过）：`CollectOwnedChildBindings`（`:5385`）只看节点类型，
`_Draw`（`:9534`）首行就 `return` ⇒ **子精灵的切片一定被父批次代画、采样父那一张图集**
⇒ 跨 `.tres` / 自制皮肤的子精灵 = **别的角色碎片拼贴**。

**修法（唯一可行）**：身体下留三个节点：

| 节点 | 类型 | 作用 |
|---|---|---|
| `HeadShadow` | 与身体同类精灵 | `visible = false` + **全层 false** ⇒ 零切片；只为吃 `UpdateChild()` 的每帧定位 |
| `HeadHolder` | 普通 `Node2D`（identity） | 打断「父代画」的容器 |
| `Head` | 独立渲染的精灵 | 给人看的那个；写 `z_index = 1` 压住身体 |

> **⚠️ 反过来「要让子精灵排在父后面」怎么办？**（贴图光环、脚底特效等）
> 这时 `z_index = -1` **完全无效** —— 被父代画的子精灵，它的 `ZIndex` 排序位取的是**父精灵**的
> `EffectiveZIndex`。**唯一**有效手段是显式写 `insertLayerId = <id>`（按**父精灵**的
> `layerDictionary` 解释；一般 `id = 0` 是内建隐藏背景板，可见层从 `1` 起 ⇒ 取 `0` 就画在父**后面**）。
> 详见 `references/zombie-skin-and-head.md` **§9**。

两头（`HeadShadow` 与 `Head`）的 `scale` / `offset` / `offsetRotate` **逐字相同**，
位姿由插件每帧从影子抄给可见头（见 Step 8）。
**原版头部的 7 个图层必须在身体上显式关掉**（`Animation/LayerVisible/<原头层> = false`），
否则原头会从头盔底下透出来。

> **⚠️⚠️ 写 `Animation/LayerVisible/…` 时，引号必须包住「整条」属性名**（2026-09-25 用一天换来的教训）：
> 层名含**空格或非 ASCII**（`图层_1` / `skin2_2 ` / `cloak1 复制` …）时：
> ```
> 正确： "Animation/LayerVisible/图层_1" = false     ← 官方写法（全库 6941 个文件零例外）
> 错误： Animation/LayerVisible/"图层_1" = false     ← 只包末段 ⇒ 这一行**完全无效**
> ```
> 坏写法**不报错、不留日志**：`_Set()` 里 `layerDictionary.ContainsKey()` 拿到带引号的名字 ⇒ 为假 ⇒
> 直接 `return true` ⇒ 该层保持**初值 `true`**（`:9049-9069` 没写进 `_layerVisible` 的下标一律按可见算）
> ⇒ **永远可见**。后果实测：`HeadShadow` 的「全层 false」白写 6 层（含**另一张脸 `skin2_2`**、皇冠、
> 花瓣、火圈、光环、披风）⇒ 身体上**多长出一个完整的头**，且光环/披风怎么关都关不掉。
> ⇒ 生成器统一走 `_prop(key)`（判据作用在**整条 key** 上）+ 常驻自检 `_bad_prop_keys()`；
> 全库对照扫描 `.cache/_sq_quotefix_scan.py`。**ASCII/纯数字层名裸写是对的**（`Animation/LayerVisible/1 = true`）。

### Step 6 — 外观三件套

见 `references/zombie-skin-and-head.md`（含经典 reanim 直转、`.dat` 二进制规格、头对位反解）。
**关键：僵尸朝左**（`scale = (-1, 1)` 横翻）⇒ 所有屏幕坐标都要过横翻矩阵，别直接加。

### Step 7 — 发射：数据侧只做两件事

1. **组件集**：基于内置僵尸组件集 + 加 1 个 FireComponent（`InstanceId` 用固定的接线键）。
2. **发射定义** `.tres`：
   * `firePosMarkerPaths = [NodePath("…/HeadSlot/FireMarker")]` —— 指向 Marker2D（**子弹生成点**，见 references）；
   * `fireProjectileList` 只留 **1 条** config（`Fire()` 一次遍历全部弹 ⇒ 逐颗发射必须在插件里循环）；
   * `speed` 为**负**（僵尸朝左，负值才是向前）；
   * 僵尸的场景里要有真实 `Marker2D` 节点（`firePosMarkerPaths` 必须是真 Marker2D）。

⚠️ **数据侧做不到的事**（只能插件）：概率 / 延时改模式 / 真随机 / 改投掷单位 / 逐颗发射 / 特殊大招。

### Step 8 — 托管插件（僵尸的真正工作量在这里）

入口类放在**无命名空间**下（`runtimeEntryType` 是类名），实现 `IXWModRuntimeEntry`，
三个回调（`Initialize` / `OnAllModsLoaded` / `Shutdown`）**一律不许抛**（抛了 = 无条件整包回滚）。

插件的几件典型职责（照抄本仓 `SuperGatlingPaperRuntimeEntry.cs`）：

| 职责 | 要点 |
|---|---|
| 自建节拍 | 挂 `SceneTree.process_frame` 自己推进毫秒时间轴（**不要**去骗内置状态机） |
| 射击判定 | 必须用 `FireComponent.CanFireCheckOnceByData()`（**不是** `CanFire` —— 后者多一道 `timer > 0` 会把节奏拖一轮）；「没植物不开火、进场才开火」都在这里 |
| 开火动画 | 头独立渲染后，头 clip 完全归插件管：`MarkHeadFire()` 切 `HeadFire` 并**续**窗口；`SetHeadClip()` 只在 clip 真变了才 `SetClip()`（否则每颗豌豆都把动画打回第 0 帧） |
| 换头位姿 | 每帧把影子 `Position`/`Rotation` 抄给可见头（10 帧一档的扫描会抖） |
| **子弹生成点** | 每帧 `marker.GlobalPosition = head.GlobalTransform * HeadMuzzleLocal`（见 references/zombie-fire-and-marker.md） |
| 卡库入库 | 把角色补进 `GeneralZombie` 的派生库（按 `Include` 闭包**运行期**算，别写死） |
| 图鉴去重 | 反射去 `_zombieLogicalConfigs` 的重复项 + 公开的 `QueueZombieVirtualRefresh()` |

**编译**：`python runtime_src_zombie_super_gatling/build_runtime.py --check`（两次编译比 sha256）。
⚠️ **生成器不会自动重编 DLL** —— 改了 `.cs` 必须单独跑一次构建，否则打进包的还是旧 DLL（踩过：DLL 停在两天前）。

**★★★ 两条「名字」的硬约束（照抄旧工程最容易踩）**：

| | 写在哪 | 值 | 能改吗 |
|---|---|---|---|
| 包内**物理路径** | `mod.json` → `runtimeAssembly` | **恰好** `"Runtime/ModAssembly.dll"` | ❌ 硬校验，改 = 整包被拒 |
| **程序集身份** | `.csproj` → `<AssemblyName>` | **该 Mod `mod.json` 的 `id`**（小写无分隔，≠ 驼峰/中文的 `name`） | ✅ **必须改**（安卓要求主程序集名唯一） |

```xml
<PropertyGroup>
  <AssemblyName>supergatlingpaper</AssemblyName>   <!-- ❌ 不要写 ModAssembly -->
</PropertyGroup>
```
```python
# build_runtime.py 取产物时也要跟着改（装机名仍叫 ModAssembly.dll）
ASSEMBLY_NAME = "SuperGatlingPaper"
src = os.path.join(out_dir, ASSEMBLY_NAME + ".dll")
```
**根因**：安卓走 `LoadAndroidAssembly`（`XWModAssemblyLoader.cs:191-193`）→ 全 Mod 共享一个非可回收上下文，
按简单程序集名（`OrdinalIgnoreCase`）记账，撞上即
`throw BuildAndroidAssemblyConflict`（`:314`，文案 `:338-341`）；PC 走 `ModLoadContext`（`:195-197`，
**每 Mod 一个独立 ALC**）所以从不暴露。`runtimeEntryType` 按 `Type.FullName` 匹配
（`XWModCharacterCompanionRuntime.cs:105`）**与程序集名无关** ⇒ 改名只影响构建脚本取产物名。
完整依据、三条自检 → `references/zombie-package-and-gates.md` §5.1。

### Step 9 — 让它「能被选到」+ 图鉴

* 补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类，以及 `Include` 闭包算出的派生库
  （实测 `['GeneralZombie','TotalZombie','Total']`）——只补根库的话，`debugPacketOpenAll` 切到 `Total` 又看不到。
* **图鉴僵尸页会多一条**（`Almanac.cs:411-435` 两条来源都不去重）⇒ 运行期反射去重（Step 8 表末行）。

### Step 10 — 写/跑闸门（**不能省**）

见 §5 与 `references/zombie-package-and-gates.md`。**离线能抓的错绝不留给实机**。

### Step 11 — 装机

生成器负责：写 `dist/<中文名>.pmod` → 复制到 `Mods/` → 解到 `Mods/<中文名>/`（**72 个标准目录**）→
**启用**：优先按模板口径 —— `python tools/mod.py install --mods-dir <Mods>` 后，在 **Mod 管理界面勾选启用并重启**；
**不要手工覆盖 `enabled_mods.json`**（模板明令，会连带清掉别人的条目）。
仅在做**自动化验收**、确实需要脚本启用时，才以「读→合并→写回」方式追加自己的 id（**保留其他人的条目**），
并在交付说明里标为本机测试步骤，不是给玩家的操作。`mod_editor_recent_projects.cfg` 只服务**游戏内编辑器**流程，
上游模板已不使用（基线文档 §7.2），不需要登记。
**改完包重启游戏即可**，别手删 `ModsCache`。

### Step 12 — 实机验收

离线验不了的（并且**必须如实告诉用户**）：
「头真的画对了 / 动画在动 / 子弹真的从炮口出来 / 没被遮挡 / 图鉴只有一条」。
先看 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\PVZHE_Logs\` 的加载日志。

---

## 4. 坑 Top 10（僵尸专属，每条都能白忙半天）

1. **★★ 场景没显式写 `ComponentSet` ⇒ 发射组件根本不创建，且零日志**（Step 4）。
2. **★★ 子精灵必被父代画** ⇒ 换头必须「三节点」（Step 5），直接换贴图只会得到别的角色碎片。
   **同一条规则的第二个面**：既然被父代画，子精灵自己的 **`z_index` 也失效** ⇒ 想让它排在父**后面**
   只能写 `insertLayerId = <id>`（`-1` = 默认 ⇒ 回落顶层 = 画在最前）。
   详见 references/zombie-skin-and-head.md §9。
3. **★★ 子弹生成点 = `firePosMarkerPaths` 指向的 `Marker2D.GlobalPosition`**，
   不是角色原点、也不是炮口；而 `HeadSlot` **是原版护具用的静态插槽、不跟头部美术**
   （「挂在 HeadSlot 下就跟着头」是错的）⇒ 见 references/zombie-fire-and-marker.md。
4. **★ 头在摆 ⇒ 静态值只能对上参考帧**：只要头跟 `anim_head1` 逐帧摆，炮口每帧都在动
   （Idle 段就跨 20px）⇒ 必须插件每帧覆写。
5. **★ `CanFire` vs `CanFireCheckOnceByData`**：自建节拍必须用后者。
6. **★ 僵尸朝左**（`scale=(-1,1)`）⇒ 「屏幕向右上微移」**不能直接加到 `offset` 上**（横向会反向）；
   必须加在**锚点**上再反解（本仓 `HEAD_PLACE_SHIFT`）。
7. **★ 改完 `.cs` 生成器不会重编 DLL** ⇒ 包里的还是旧 DLL（对比 mtime 立刻能看出来）。
8. **★ 图鉴僵尸页两条** ⇒ 运行期去重。
9. **★★ Godot 对 `.tscn` 的坏写法「静默容忍」**——两类都已实证，都不报错、零日志：
   * **节点头收尾必须是 `]`**：写成 `>` ⇒ **静默吞行**（节点不建）；断言别写成不带闭合括号的前缀匹配
     （**断言与实现同错 = 假绿**）。
   * **属性名引号要包「整条」**：`Animation/LayerVisible/"图层_1" = false`（只包末段）⇒ 该行**完全无效**，
     层保持默认 `true`（详见 Step 5 的警示框）⇒ 会凭空多出一个头。
   ⇒ 规程：**只认官方同源文件的写法**（拿同一份 `.tres` 的官方 `.tscn` 逐字对照），
     再配「复刻负向」（把实现改回坏写法，断言必须打红）。
10. **★ 「断言与实现同错 = 假绿」**：① 恒真比较（拿常量比由同一常量渲染的文本）⇒ 加 `*_GOLDEN` 金标；
    ② 门控共用 ⇒ 硬需求写成无开关不变量；③ 前缀匹配漏字节；④ 目标行在当前口径下不生成 ⇒ **打桩注入**。
    **写完/改完断言必须逐条篡改常量确认报警。**
11. **★★ 尺寸 / 位置类需求（「头调大调小一点」「头往上挪一点」）都别目测猜** —— 目测必被下一张图推翻。
    **尺寸**（用户给目标截图）走三步：**① 泛洪分割**量参考图轮廓（从四边泛洪，黑框/草坪判据）→
    **② 离线合成渲染**扫候选倍率（共享图集 + `Manifest` + `PIL.AFFINE` 逆矩阵，量真实像素 bbox）→
    **③ 同高度归一并排**目视复核。至少两个独立判据，取落在参考图两侧最近的一档。
    ⚠️ 归一化要**剔掉尺寸恒定的装饰**（固定像素的光环会稀释倍率差异）。
    ⚠️ 改完 `head_scale` **必须重解 `head_offset`**（`A = rot_scale(θ, −s, +s)` 含节点 scale）。
    **位置**（「跟那张图一样高」）拿**两张真实图直接比**，**别经过离线渲染**（帧/姿势未必一致），四个坑：
    ① 画幅不同 ⇒ 绝对 y 不可比，先找「与头无关」的身体标尺；
    ② 标尺**不能选会被遮挡的量**（裤子常被脚底光环截断 ⇒ 改用**头宽**，且只能比**宽**）；
    ③ 头块取「**最靠上的橙色大块**」（脚底光环常比头大好几倍）；
    ④ 头的锚点**必须"刚性"** —— 头 bbox 含**火焰花瓣**且火焰**逐帧变**，
       顶/底/中心都会被帧差污染（实测「头块中心」少算 **20%**）；只用**脸 / 王冠**这种刚性子块。
    ⇒ 位移**加在锚点上**反解，别直接加到 `offset` 上（`A` 含横翻 + 交叉项）。
    ★★ **「改为现在的 N 倍」= 相对放大**（在上次定标结果上再乘 N，不是「N 倍于原素材」），三条口径：
    ⑴ `head_scale = 旧值 × N`；⑵ 解 `offset` 时**沿用当前 `shift`**（否则上移量会被一起解掉、头掉回原位）；
    ⑶ **旧 `offset` 不许复用**，必须重解。✅「原地放大」的判据 = **头块落点中心逐字不变**。
    ⚠️ 别用启发式取块量放大前后的尺寸（火焰花瓣逐帧变 ⇒ 两倍率下不是同一块，实测给出 `1.19` 假比值）；
    尺寸比报**解析值**。⭐ 对照图最干净画法：同 `box`、`k`、`shift` 渲两张，画**解析锚点十字**；
    且离线渲染落盘是 **RGBA** ⇒ 「旧轮廓叠新图」**直接取 alpha 通道**（`MinFilter(3)` 腐蚀相减），零启发式。
    ★★ **没给参考图**时（「再往右上方移一点」）：铁律 30 仍**禁止目测猜** ⇒ **先问量级**，
    问不到就**按口径定**（查本项目历史同义先例、取保守值；实测先例 18px / 20.16px ⇒ 取 **12px**），
    并写明「**这是默认值、一句话可改**」；**多角色同一句话 ⇒ 同一增量**；位移用**累计 `shift`** 重解。
    ⚠️ **隐藏基准坑**：离线渲染器 `--mult` 实为 `S = 0.45 × mult`，`0.45` 是**女王包历史口径** ⇒
    给**别的角色**渲图必须用 **`--head-scale`**（直接给绝对 `S`），否则头会被渲小 2.2 倍。
    详见 references/zombie-skin-and-head.md §10 / §10b / §10c / §10d。
12. **★★ 「移动速度 / 伤害类型」不在 config 里**，别在 `TowerDefenseZombieConfig` 里找：
    **伤害类型** = `attackType`，只在 `Scene/<Key>AttackComponentDefinition.tres` 上
    （取值 `Default/Eat/Smash/Chomp`，「啃食」= `Eat`）；**移动速度** = 角色 `.tscn` 节点属性
    `walkSpeedScale`（内置口径：普通僵尸 `1.0` = 手册「慢」，橄榄球僵尸 `2.0` = 手册「快」）。
    攻击定义要**覆盖**内置，必须逐字对齐 `InstanceId = "character.attack.0"` /
    `ComponentTypeId = "AttackComponent"` / `WireIndex = 0`，否则 `CanReplaceInheritedDefinition`
    只报错**不替换**（还有 `useParentHitBox` / `checkLine` / `StateMachineDefinition` 也不能漏）。
    另外 `hitpointsNearDeath` **是濒死掉血速率、不是阈值**，别按血量比例缩放。
    手册五行属性块（`血量/伤害/佩戴/类型/移速`）格式见 references/zombie-stats-and-cc.md §A。
13. **★★ `.tres` 字符串不能有裸换行** ⇒ 多行手册文案必须走 `\n` 转义。
    写成真换行时**包能打出来、闸门全绿、装机也成功，只有进游戏才解析不开**
    ⇒ 加机械闸门（`key = "…"` 行必须以 `"` 收尾且引号数为偶数）。
14. **★★ 想让植物「停止发射」，`timeScaleInit = 0` 不够** ——
    `FireComponent:1687`（IZM 分支）与 `CannonComponent:1344`（`flag ? 1.0 : timeScale`）
    **绕开了 timeScale**，植物照打。唯一全路径有效的杠杆是
    `buff.GetAttackSpeedMultiplier()` ⇒ 挂
    `TowerDefenseCharacterBuffAttackSpeedDown { timeScaleValue = 0, time = N }`。
    三条纪律：**只摘自己挂的**（`BuffGet` 已存在且非自己挂 ⇒ 跳过，埃德加二世的火球是真实碰撞场景）、
    **每次给新实例**（`EnterBuff` 不克隆）、**`Shutdown` 兜底摘**
    （否则关掉 Mod 植物永远开不了火）。详见 references/zombie-stats-and-cc.md §B。
15. **★★ 自建皮肤的僵尸一步都走不了 —— 皮肤里缺 `_ground` 层。**
    全仓**只有** `GroundMoveComponent` 会平移角色（`grep TranslateForPhysicsFrame` 只命中它），
    而它按**名字**从 `layerDictionary` 解析 `"_ground"`，读该层逐帧位姿差当位移：
    `vector2 = 上帧 − 本帧` → `TranslateParent(vector2 * _moveScale)`。
    没有这一层 ⇒ `_usingGroundLayerSource = false` ⇒ `_moveDelta == 0` ⇒ **原地不动**。
    配方：`.dat` 多写一层（原生就是「每层 × 每帧 × 若干元素」，不用改格式），
    元素 **`alpha = 0`**（只做根运动、不可见）、变换**非 Identity**（第 k 帧 origin 取 `(k+1)·step`）；
    **一个剪辑只放一条完整锯齿，回跳必须落在剪辑边界上**
    （边界会置 `sprite.blend`，`BatchUpdateValidated` 开头 `if (pause || blend) { ResetGroundTracking(); return; }`
    才吃得掉）；`Idle*` / `Eat` / `Death*` **绝对不要加**，否则站/啃/倒都会自己滑。
    ⚠️ 同时纠正一个常见误解：**`walkSpeedScale` 不影响移速**（基类从不读它），
    真正的移速 = 该层位移速率（内置普通僵尸 50px/47 帧 = 12.77 px/s）。
    ⚠️ 每帧强制切剪辑必须用 `SetClip` 而非 `SetAnimation` —— 后者置 `blend`，位移会被整段丢掉。
    ★★★ **2026-10-02 补充：这条的「症状指纹」与「第一动作」（真实踩了 20+ 轮，务必照做）**
    - **症状指纹（四联）**：状态机在跑（剪辑帧号在推进）+ 剪辑正确 + `Δx ≡ 0` + 日志**零 ERROR**
      ⇒ **立刻认定是本条**，**不要**再去查数据（`.dat`/`.tres`/图集一致性）、组件集、配置、
      碰撞 flag、绘制序 —— 那些本轮全部查过，全部无罪。
    - **第一动作**：打开
      `Script/Component/TowerDefense/Character/GroundMoveComponent/GroundMoveComponentDefinition.tres`
      看 **`groundLayerName`**（内置 = `&"_ground"`），再到 `GroundMoveComponent.cs:191-231
      ResolveMovementSource()` 确认**第 1 优先级**就是按名找这一层；`:322-355` 逐帧取**原点**算 Δ。
    - ⚠️⚠️ **`GroundSlot` 节点不能替代本层**（本轮踩的死胡同）：`ResolveMovementSource()` 只在
      **找不到 `_ground` 层**时才退回 `sprite/GroundSlot` 节点，而那个节点没有位移源 ⇒ 推不出任何 Δ。
      「精灵场景里补了 `GroundSlot` 却仍然不动」= 本条的铁证，不是另一个 bug。
    - ⚠️ **层名字面量别被「安全化」**：本仓的部件名安全化函数（`re.sub(r'[^0-9A-Za-z_]+','_')` + `.strip('_')`）
      会把 `_ground` 变成 `ground` ⇒ `TryResolveLayerIdForRender("_ground")` 解析不到 ⇒ 又不动。
      必须在生成器里**原样覆盖**该层的资源名，并让它成为**第 0 层**（最先绘制、最底）。
    - 内置实测 Δ（anime 原点空间/帧，`frameRate = 12`；工具：工坊 `.cache/_ground_probe3.py`）：
      `ZombiePolestriker` Run/Walk 均 **0.83333**｜`ZombiePolevaulter` Run **0.83333** / Walk **1.54318**｜
      `ZombieDancer`（无 Run 态）Walk **1.43750**。`Run` 态另有 `timeScale ×3` ⇒ 实际 3 倍速。
      方向：origin.x **递增** ⇒ Δ < 0 ⇒ 角色向**左**（房屋方向）。
    - **闸门化**：把「`_ground` 在 `layerDictionary`/`_params.layers` 里 + `Run`/`Walk` 每帧恰好一个切片 +
      原点 x 逐帧递增 + 精灵场景 `LayerVisible/_ground = false`」写成 `self_check()` 的一条断言，
      别等实机才发现（先例：`build_zombie_tour_dance.py::self_check()` **§I**）。
    - **参考实现（可直接抄）**：`<融合版解包>/_work/anime_part_build.py` 的 `GROUND_LAYER_NAME /
      GROUND_MEDIA_NAME / GROUND_BASE_X / GROUND_Y / GROUND_STEP`（8×8 全透明占位 media +
      逐帧一个切片 + 原点线性递增；`part_sort` 给 `(-1,-1)` 排到第 0 层）。
    详见 references/zombie-stats-and-cc.md §B0。
16. **★★★ 从 Unity prefab「部件式烘焙」外观时：先量骨架，别急着上 FK；「关节离群」多半不是 bug。**
    （2026-10-02 在《融合版三僵尸包》上实测锁定，脚本 `<融合版解包>/_work/_fk_probe*.py`）
    - **先量两个判据**：① 父链深度分布 ② 有没有**顶层（不含 `/`）轨道**。
      实测那三套 rig：Jackson 22/25 直接挂根、DancePolZombie2 **24/24 全平**、三套**都没有顶层轨道**
      ⇒ 层级 FK（`M_child = M_parent·inv(bind_parent)·bind_child·localAnim`）**没有链条可复合**，
      是空操作。「必须改走层级 FK」这类**方法论断言**必须先被这两个判据验一遍再动手。
    - **公式（实测最优）**：`parts_pos = 符号(-1,-1) · (PTU·bsc) · anim.XY + 全局常量 root`
      （枚举 符号±(X,Y) × 6 档缩放选出来的；`root` 就是 `part_const_offsets` 求的那个全局平移）。
      该口径下 **t=0 逐件残差 = 0.000px** ⇒ **逐件偏移恒等于同一常量**，
      所以任何"逐件独立拟合 / MLS 局部加权拟合"都是**过拟合**。把这句做成**构建期断言**
      （`最大偏差 <= 10px`），以后有人再引入拟合会立刻炸。
    - **隐藏只靠 X 停车**：`|X| > 1.5`（实测 738 处）是源表达"这帧不用这件"的**唯一**手段；
      `scale≈0` **不是**隐藏机制（实测 0 处）。⚠️ **Y 可以合法超过 1.5**
      （`..._run` 里高举过顶的杆 Y=+1.80）⇒ 判据**只能看 X**；写成 `max(|X|,|Y|)` 会把 `Run` 帧的杆整段吞掉。
    - **「多出一只手/一根杆」= 源里的重复实例**：判据 = 两件共享**完全相同的 `(tex_pid, rect)`**
      （实测唯一一对：`Zombie_polevaulter_outerarm_lower` 与 `..._outerarm_lower (1)` = pid 148 / [4,263,26,31]）。
      规则 = 「同一 `(tex_pid,rect)` **只留一个**；胜者 = 本 clip **有轨道**优先，同分取**规范名**（不带 ` (N)`）」。
      ⚠️ 别用"名字像重复"当判据：`Zombie_Jackson_innerarm_hand2`、DancePol2 的 `(1)` 都是**真的另一件**
      （rect 不同）。旧口径的 `EXCLUSIVE_GROUPS` 不但硬编码，还**救反了方向**（丢掉有轨道的那件）。
    - **别删源里"看起来多余"的部件**：失杆剪辑里杆的 **Y = +0.07（≈9px，地面高度）**
      = 源自己就把杆**丢在地上**；当年据此删掉杆层是**偏离源**。
    - **推论（最重要）**：`_arm_link.py` / `_joint_check.py` 量出的"肘/肩链间距离群"**不是 bug**，
      那是**源自己的动作幅度**（跳跃伸臂、举杆）。当年据此打的"刚性跟随"补丁是在**抹掉真动画**——
      删掉后离线重放 IoU 反而**升高**（白撑杆 0.8669→0.9033、伴舞 0.8570→0.8953）。
      ⇒ **改外观必须出像素级 A/B 对照图**（`_fk_ab.py` 那种，上下两半），**缩略图会骗人**
      （本轮被缩略图误导两次：先误判"idle 没杆"，又把 `max(|X|,|Y|)` 的回归看成没问题）。
    - **★★★ 尺寸必须「逐件」取，不能用统一的根缩放**（2026-10-02 实测，肉眼级事故）：
      内置杂交版的切片线性**逐件各不相同、甚至非均匀** —— 实测
      `Zombie_polevaulter_pole2 复制` = **(1.1171, 0.8000)**，其余 21 件 = (0.8000, 0.8000)。
      我们这边对应的真值是 `parts.matrix` 的**各轴长度** `(hypot(m00,m10), hypot(m01,m11))`。
      踩过的坑：用一个全局 `bsc`（1.25）覆盖 ⇒ `pole2`（真实 1.745）被画小 **28%**，
      **同一只僵尸手上两根杆差 41.6px ⇒ 肉眼就是「杆断成两截 / 部件位置不对」**；
      Jackson 的 `outerleg_foot`（真实 1.044）被画大 15%。
      ⇒ 口径：**位置**用根缩放 `bsc`（位置空间的缩放确实是根缩放），**尺寸**用该件各轴长度：
         `T(−100·bsc·anim.XY + root) · R(−rotZ) · S(bsx·sx, bsy·sy)`
      ⇒ **必须配构建期断言**：逐件比对 bind 处线性与 `parts.matrix`（容差 1%），不符即 SystemExit
         （先例：`bake2.part_const_offsets` 的 `bind 线性断言`）。修完离线重放 IoU 会**升高**
         （本次 0.9004/0.9033/0.8953 → **0.9103/0.9151/0.9068**）。
    - **内置的落点口径**（做对照时照这个量）：唯一落点旋钮 = `sprite.offset`，它被**加到每个切片的 origin 上**
      （`BuildSliceTransform`）；角色场景 `TransformPoint(23,44)` × `sprite 节点(−23,−44)`
      **净位移 = 0**（纯抵消，不是定位用的）；地面参考 = `ShadowSprite.position = (12.6, 40)`；
      位置单位 = **像素**，尺寸 = `切片线性 × media 像素尺寸`。**内置没有"部件偏移表"这种东西。**
    - **★ 别把同一个常量在两地各写一份**：卡片的 `packetAnimeScale` / `packetAnimeOffset`
      （只喂编辑器卡片预览 `XWCardVisualResourceEditor` / `XWCardBehaviorPreviewSnapshot`，**不是实机角色**）
      一度写死 0.8，而烘焙用 0.66 ⇒ 预览比实机大 1.21×。
      ⇒ 让 builder **直接读**烘焙产物的 `_params.json`（`game_scale` / `sprite_offset`）并加断言。
    - **⏰ `GAME_SCALE` 与 `sprite.offset` 是耦合的**：`sprite.offset.y ≈ 43.1 − 8.0×GAME_SCALE`；
      改其中一个必须重算另一个（0.8→0.66 时正确值应由 36.7 变 37.82）。
    - **★★★「变体臂件」在无轨道剪辑里必须隐藏**（2026-10-02 实机截图定位）：
      融合版里 `Zombie_innerarm_hand`、`Zombie_polevaulter_outerarm_lower (1)` 这类件
      **只在 Walk/Eat/Die 有轨道**，到了 Idle/Run/Jump **无轨道** ⇒ 若按"无轨道就摆 bind"处理，
      实机就是**「贴着手臂/躯干多出一只手 + 一段前臂」**（看起来像手臂错位/三只手）。
      ⇒ 口径：**这些件只在有轨道的剪辑里画，无轨道时隐藏**；
      ★ 边界很重要：有轨道时照画 ⇒ 用户点名要用的单图贴图（tex 2904/2506）仍在用。
      ⚠️ **三条"更通用"的判据实测都分不开，别重复踩**：
        ①「bind 离它所有动画位置都远」⇒ `dmin` **恒 ≈ 0**（因为 t=0 就是 bind）；
        ②「与别的件共享同一 `(tex_pid, rect)`」⇒ 覆盖不全（单图补件 rect 各不相同）；
        ③「与其它件位置重叠 <45px」⇒ 角色只 ~150px 高，**合法邻接对一次列出 24 对** ⇒ 信噪比不够。
    - **★ 外观排障「三件套」（先上工具再动刀，能省几轮）**：
      `_partmap.py <key> <clip> <t> <out>` ——**部件着色图 + 图例**：逐件独立颜色，
        实机截图里有残件时**一眼点名是哪个部件**（比任何推理都快）；
      `_sbs_compare.py` —— 用户实机截图 × 我们各剪辑，**按同身高并排** ⇒ 先确定用户截的是哪个剪辑；
      `_probe_chain_from_source.py` —— **不渲染**、直接从 anim 的 Translations 量关节链缝隙/两根杆的接合
        ⇒ 判定「缝隙是源数据本来如此，还是我们画错」（本轮实测：Jump 的肘距 115.7px / 中位 17.4 = **6.65×**
          是**源自己的动作**，Idle/Run 都是 1.00~1.24 倍 ⇒ 不是我们的 bug）。
      ⚠️ **别用"离中心多远"当离群判据**：Jump 里杆会飞出去（x 到 2.15 单位 ≈ 269px），
        帧内均值中心被拖走 ⇒ 会大量假阳性。
    - **★★★ 最大的盲区：`_verify_anime.py` 的重放 IoU 是"我们自己的数学"，天生看不见引擎侧分歧。**
      2026-10-02 实测：把**用户给的融合版全图**当标准答案（`_ref_overlay.py` 自动搜最像的一帧 + 叠差图），
      伴舞的离线渲染与参考**逐像素一致（IoU 0.853，头/嘴/手 4× 对比全中）**，
      **而同一姿态在实机截图里"大腿缺失、只剩细棍"** ⇒ **引擎画出来的 ≠ 我们 `.dat/.tres` 声明的**。
      ⇒ 只要出现「**离线闸门全绿但实机不对**」，立刻停止调离线数学，改做**引擎帧对拍**：
        · 探针 `--tourdance-render-dump`（运行时入口里 `RenderDumpLimit`；**只在该命令行 flag 下落盘**）
        · 产物 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\tourdance_dump_NN.png`
        · 与 `_work/anime_part/<Anime>/_preview.png` **同帧**对比 ⇒ 把差异钉到具体部件。
      ★ 用参考图当 oracle 的正确姿势：先按**同身高归一化 + 轮廓 IoU**自动配姿（找对是哪个剪辑的哪一帧），
        再叠 红=参考有/我们没有、绿=我们多出、灰=重合 的差图；**只比轮廓会漏掉"内容错"**（形状对、贴错图），
        所以再补一次**局部 4× 放大逐个部位看**。
    - **★★ 实机落盘探针：Godot 4 的 `OS.GetCmdlineUserArgs()` 只返回 `++` 之后的参数！**
      （踩过：只扫这一个来源时 `exe --flag` **收不到**，游戏照常起、**一张都不落盘**、零报错。）
      ⇒ 判命令行开关要**两个来源都扫**：`OS.GetCmdlineArgs()` + `OS.GetCmdlineUserArgs()`，
        并兼容 `--flag` / `+flag` / `++flag` 三种写法。
      ⇒ 落盘位置 `user://` = `%APPDATA%\Godot\app_userdata\<游戏名>\`；
        **标题/主菜单界面通常已经摆着本包的角色当装饰 ⇒ 不必进关卡就能拿到引擎帧。**
      ⇒ 拿到帧后与 `_work/anime_part/<Anime>/_preview.png` **同身高并排**看：实测能直接看到
        「举杆的手与前臂断开、腿从躯干侧面冒出、地面附近有游离残肢」这类**逐部件位移**，
        而同一份 `.dat/.tres` 的离线重放是**完全正常的**。
    - **★ 给用户的启动器（`.bat`）要守三条**：纯 ASCII（当前代码页逐字节读）、**CRLF**（Write 工具出的是 LF）、
      括号平衡；**中文路径不要写成字面量** —— 用 `cd /d "%~dp0"` + `for %%F in (*关键字*.exe) do call :run "%%~fF"`。
    - **★★★ 引擎帧对拍的「精确同帧」技巧（别靠猜剪辑）**：探针落盘时**同时在日志里记下每个精灵节点的
      `frameIndex`**（`渲染落盘 #NN：… <节点名>:f<K> …`）⇒ `grep "渲染落盘" godot.log` 就能知道
      **引擎当时在播哪个对象的第几帧**；再用同一帧的离线渲染对位，才是 apples-to-apples。
      实测映射示例：`ZombieWhitePoleKing:f6` → `..._idle` 第 6 帧（Idle[0,18]）；
      `ZombieTourDanceCommander:f116` → **ArmRise**（ArmRise[91,131]）；`f32` → **Walk**（Walk[25,65]）。
      ★ 顺带：**标题/主菜单界面通常已摆着本包角色当装饰**（走 Idle）⇒ 不进关卡也能拿到引擎帧；
        要拿 Walk/Run/Jump 的引擎帧则必须在关卡内。
      ★ 实测结论（2026-10-02）：探针修好后，把引擎帧与同帧离线渲染并排看 → **结构一致**（无缺件/游离件）；
        也就是说「离线闸门绿 + 实机不对」**不必然**是引擎侧问题，**先确认用户截图是不是旧构建**。


---

## 4b. ★★ 多体节 BOSS 僵尸（N 个独立受击判定共用一条血条）

需求形态：「一个 BOSS 由 1 头 + 9 体节 + 1 尾共 11 个**独立受击判定**组成，全部**共享同一条血条**」。
2026-09-27 勘察《星空机械蜿蜒》时把三条链路全部落到源码，照这套做即可，**不用自制 UI**。

### 4b.1 三条关键事实（先看这个，能省一整天）

| 想知道 | 结论 | 源码 |
|---|---|---|
| 怎么让内置 **Boss 血条**接管 | **`config.physique = 6`**（`ZOMBIE_PHYSIQUE.BOSS`）即自动生效，条数/比例/淡出/最多同时 3 条全白送 | `Prefab/GUI/BossHealthBar/TowerDefenseBossHealthBarManager.cs:597 IsBossCharacter()`；比例 `:615-660` `hitpoints / hitpointsSave`（护具另算 `shieldRatio`）。**图标按 `config.name` 匹配**（`ResolveStyle :664`，未知名字 ⇒ `icon = null`，只剩色条） |
| 一个角色能有几个 hitbox | **只有一个**（`CharacterHitBoxDefinition { Size, LocalTransform }`）⇒ 「N 个独立受击判定」**只能靠 N 个角色实例**，不是给一个角色挂 N 个盒子 | `Resource/TowerDefense/Collision/CharacterHitBoxDefinition.cs`；命中判定 `Core/TowerDefenseManager/SubSystem/TargetSystem.cs:643 / :806`（`checkCharacter.IsHitBoxEnabled` + `WorldHitRect`） |
| 怎么共享血池 | 每帧轮询归一化：`pool = TOTAL − Σ(baseᵢ − hpᵢ)`，回写全部 N 段的 `hitpoints` + `hitpointsSave` | `Resource/TowerDefense/Character/Instance/TowerDefenseCharacterInstance.cs:45 public double hitpoints`（**可写**）、`:42 hitpointsSave`、`:252 event Action hitpointsEmpty`。⚠️ **没有「受伤」事件** ⇒ 只能 `_Process` 轮询（不要去找 hitpointsChanged，不存在） |

### 4b.2 照抄的配方

1. **11 个同源实例**：同一份 `Config/Scene/Sprite`，插件在运行期额外生成 10 个，用节点名/自定义字段打段索引。
2. **只有 0 号（头）`physique = 6`**，其余取 **`HUGE`（同伽刚特尔），绝不能取 `SMALL/NORMAL`** ——
   `TargetSystem.cs:462` 会按 `zombiePhysique >= HUGE` 过滤，取小了某些植物直接不索敌。
   ★★ **枚举真值（`Resource/TowerDefense/TowerDefenseEnum.cs:114`）**：
   `NOONE=0, SMALL=1, NORMAL=2, MID=3, **HUGE=4**, CAR=5, BOSS=6` ⇒
   **体节要写 `4`，不要写 `5`（`5` 是 `CAR`＝车）**。这条极易写错，
   本项目计划书原稿就写成了 5，靠负向用例才逼出来。
3. **11 段全部摘掉 `GroundMove`**（组件集 `RemovedInstanceIds = ["character.ground_move"]`），
   位移交给插件 `TowerDefenseCharacter.SetLogicalGlobalPosition(Vector2)` 驱动 ——
   绕开铁律 15「自建皮肤缺 `_ground` 层 ⇒ 原地不动」那整条坑。
   ⚠️ **Scene 上必须显式写 `ComponentSet = ExtResource("compset")`** —— 基场景
   `TowerDefenseZombie.tscn` 自带一份（那份里没有你要摘的东西），不覆盖 ⇒ 摘除**完全不生效且零日志**。
   另：非头段再摘 `character.show_health`（否则场上晃 N 条小血条，先例 `GraveStone` / `MushroomMinis`）
   + `character.attack.0`（否则 N 倍啃食伤害）。
4. **共享血池每帧归一化**。本项目已跑通的闭式（`hitpointsSave` 每帧一起写，天然免疫难度缩放）：
   ```
   frameDamage = Σ_i max(0, expected[i] − hp[i])     # expected = 上一次写回值
   totalDamage += frameDamage                        # clamp 到 TOTAL
   pool    = TOTAL − totalDamage
   每段写：hitpoints = pool / N ；hitpointsSave = TOTAL / N
   ```
   ⇒ 头段 Boss 血条比例 = `(pool/N) / (TOTAL/N)` = **`pool / TOTAL`** ✓；
   `pool = 0` ⇒ N 段 **同帧** `hitpoints` 归零 ⇒ `hitpointsEmpty` 同帧触发。
   （写 `hitpoints = pool` / `hitpointsSave = TOTAL` 也等价 —— 只要**比例**是 `pool/TOTAL`。
     但 ⚠️ 别只写 `hitpointsSave = TOTAL` 而忘了同时改 `hitpoints`，那样比例恒为 1。）
   数据侧各段 `hitpoints` 写 `TOTAL/N`，且**不写** `hitpointsNearDeath`（默认 0）⇒
   `hitpointsSave == hitpoints == TOTAL/N`（`TowerDefenseCharacterInstance.cs:318-320`）。
   ⚠️ `hitpointScale`（难度缩放）的 setter 会**同时**缩放 `hitpointsSave` 与 `hitpoints`（`:206-230`）
   ⇒ 每帧写回即覆盖，不用手动反除。
   ⚠️ **没有「受伤」事件** ⇒ 只能每帧轮询（`hitpointsChanged` 不存在）。
5. **隐藏非头段的小血条**（`ShowHealthComponent`），否则 11 段各一条小血条。
6. **`unUseBuffFlags` 别直接抄 BOSS 的 `1020`** —— 那是「免疫一大堆 buff」的口径，
   会连带影响你自己的判定；逐项核过再写。
7. **段间跟随 = 链式约束（每段朝前一段、保持 `link[i]` 间距）+ 关节**绝对角度限幅**
   ⇒ 天然蛇形，且**帧率无关**（限幅要写成「绝对朝向 clamp」，不是「每帧加多少」）。
   ★ 把算法抽成**单一真源模块**（本项目 `_src/_ss_spine.py`：`spine_pose` / `render_pose` / `poly_path` / `r_min`），
   mockup 脚本与游戏内插件**共用同一份**，否则离线渲得好看、进游戏对不上。
   ⚠️ 用**拖尾**（本体沿头部走过的轨迹铺开）而不是硬贴曲线，才是蛇的真实运动学。
   **受击部位跟随是结构自带的**（每段是独立角色，hitbox 随节点走），不用额外写。

### 4b.3 官方 BOSS 样板（拿来当骨料，别从零写）

| 路径 | 可抄什么 |
|---|---|
| `Asset/Anime/Character/Zombie/Boss/Boss/`（僵王） | `physique = 6` 的 config；`DamagePoint/` 三阶段外观；`Constraint` 副角色（`Driver`）+ 载具（`RVNode`）；`BallSpawnMarker` / `SpawnMarker` 生成点；组件集里一串 `attackType = "Smash"` 的 `character.attack.N` |
| `Asset/Anime/Character/Zombie/Boss/EdgarII/`（埃德加二世） | 同型 BOSS 的 `Config/Packet/Scene` 三件套最干净写法（`hitpoints = 500000`、`weight = 6000`、`wavePointCost = 2000`、`cost = 1000`、`collisionFlags/maskFlags = 9`） |
| `Asset/Anime/Character/Zombie/Boss/BossDave/` | 带护具的 BOSS（`Asset/Anime/Character/Zombie/Boss/BossDave/Armor/Config/ZombieBossDaveArmorBossDaveDoomShield.tres` + `Registry/Armor/Config/BossDaveDoomShield.tres`） |

⚠️ **`DamagePoint` 不是受击盒**：`CharacterDamagePointData` / `CharacterDamagePointConfig`
（`Resource/General/Character/DamagePoint/`）是**外观阶段**系统 —— `damagePersontage` 当**阈值**排序，
到点切 `animeFliterOpen/Close` + `replaceMediaName` 换贴图/播特效。**与「多处独立受击」无关**，别搞混。

### 4b.4 直接 `res://` 复用僵王火球（不用复制美术）

```
弹体：res://Asset/Config/Projectile/EdgarII/ZombieBossEdgarIIFireball.tres
      （baseDamage=2000, scale=(2.25,2.25), fireMethodFlags=4, penetrateNum=-1,
        damageFlags=7, collisionFlags=63, useDurabilityBlockingSweep=true, splatScene=FireSplats）
粒子：res://Asset/Anime/Character/Zombie/Boss/Boss/Effect/FireBall/FireBall.tscn
      （GPUParticles2D + FuelBall.tres 的 ParticleProcessMaterial，纹理 …/Particles/FireBall/FireballParticles.png）
```
包内 `res://` 指向**游戏自带**资源是**合法**的（`SanitizeCharacterTextResource` 放行），
只有指向**包内自己**才必须写相对路径。

### 4b.5 多部件素材拼链（「给了头/体节/尾三张图，自行裁剪组装」）

用户给几张**部件特写**图 + 一张全身参考图时，**先定每张图的朝向再谈裁切**（2026-09-27 实测）：

1. **先判视角**：三张部件图若都是**正视/俯视特写**（左右对称、有「正面正对镜头」的观感），
   而参考全身图是**侧视横排**，则部件必须**旋转 90°**才能拼成侧视链。
2. **旋转方向靠「三个独立判据」定，别猜**：
   ① 前进方向（僵尸朝左）⇒ 口器/头部尖端要落在左边；
   ② 冠状角刺在侧视里应朝**上下**（若在部件图里朝左右 ⇒ 说明它是俯视，转 90° 后正好）；
   ③ 尾端必须「锥形环在左、大眼在右、尾刺朝右」—— **尾图往往要转 CCW 而头/身转 CW**，
      这一步最易搞反（转了 CW 会整条尾左右颠倒）。
3. **比例自洽的硬判据**（用来证明不是「看着差不多」）：
   单环宽高比必须等于参考图里单环的宽高比。本项目实测 `694:1795 = 0.3866` vs 官方 `116:300 = 0.3867`。
   头宽 / 环宽也应与参考图一致（本项目 5.1 vs 官方 5.04）。
4. **★★ 逐链间距不要用「统一 overlap 百分比」**：`spacing = 宽 × 0.90` 在
   **头（宽 295）→ 首环（宽 63）**这种悬殊跳变处会留下可见空档（头是菱形体，右端本就收细）。
   正确口径是**逐链像素重叠**：`link[i] = w[i]/2 + w[i+1]/2 − OVL[i]`，
   `OVL` 按链接逐个给（本项目 `{0:118, 1..8:14, 9:78}`）。
   ⚠️ `OVL[0]` 常常不是「设」出来的而是**结果的副产物**（头半宽 147.5 + 首节半宽 63 − 深插 92.5 = 118）。
5. **抠底一律 flood fill（限「颜色≈背景 **且** 连通到画布外缘」）**，禁止「全图同色即透明」
   （内部近黑描边会被误伤）。
   ★★ **「只保留最大连通域」一举去掉右下角 AI 水印** —— 水印字符是独立小连通域，
   比写专门的去水印逻辑简单可靠得多。
6. ⚠️ 脚本里 `Image.new((w, h))` 的 `w` 若来自 `sum()`/`max()` 会是 `float` ⇒
   `TypeError: 'float' object cannot be interpreted as an integer`，记得 `int()`。
7. **★★★ 「某档位 + 某手法」必须反解，不许想当然**（2026-09-27 实测）：
   用户要「体节加到 C 档尺寸（in-game `126×163`, w/h 0.773）+ 用**横向拉伸**实现」——
   单环 trim 后 ratio 是 `0.4110`（不是外框的 `0.3866`），所以拉伸倍率 = `0.7730/0.4110 = **1.875**`，
   **不是**直觉上的 2.0（2.0 会得到 `134×163 / 0.822`，档位就错了）。
   ⇒ 任何「倍率」「比例」都写一个探针脚本实测反解（本项目 `_src/step8_ring_probe.py`），
   半分钟的事，能挡住一整轮返工。
8. **★★ 锚点取「bbox 中心」时，必须检查「实体」而不是「外框」能不能接上**：
   本项目尾部实体球在 bbox 内**居中偏左**（逐列 alpha 覆盖率 `x≈10..118 / 171`），右半是一根细长刺。
   按 bbox 中心当锚点时，26px 重叠会让**球体够不到前一段** ⇒ 上方张开楔形缺口
   （实测 223px 封闭空洞，肉眼明显）。可行带 `[62, 86]`，取 78。
   ⇒ 诊断命令：`逐列覆盖率 = (alpha>0).mean(axis=0)`，找 «覆盖率首次 ≥0.55 的列»。
9. **★★ 最小转弯半径是硬约束：`R_min = link / (2·sin(θmax/2))`**
   （2026-09-27 实测：`106.5 / (2·sin5.5°) = **566 px**`）。草坪本体才 720px 宽 ⇒
   **每关节 11° + 节距 106px 时，本体最紧只能弯 566px 半径，S 型只能呈现为缓和长弧**，
   做不到紧绷蛇形；渲染图里会看到多个关节**顶在 ±θmax 上限**、本体「抄近路」穿过 S 路径。
   ⇒ 「关节角」与「节距」是耦合的，**选角度时必须同时算 R_min**，别只说「最多能弯 N×θmax 度」。
   ⇒ 想更蛇形就同步加大 θmax **和** OVL（但它们不是单调关系，见第 10 条）。
10. **★★★ 接缝闸门的方法论（踩过，代价大）**
    - **差分指标抓不到「两件根本没接上」**：以「同角刚性姿态」为基线（这是抵消美术自带镂空的唯一干净办法）时，
      若 link 太大导致两件不相接，**刚性与弯曲都不接** ⇒ 差分 = 0 ⇒ **假绿**。
      ⇒ 必须再配一个**绝对**指标（缝处腰宽 / 厚度比 / 连通性）。
    - **绝对指标的阈值跨关节不通用**：环→环在视觉已干净的 OVL=14 处 ratio 仅 **0.73**；
      尾→环在视觉仍有缺口的 OVL=26 处 0.76，要到 78 才 **0.98**。⇒ 单阈值不可行。
    - **可行性是「有界区间」不是单调的**：重叠太小露缝、**太大从另一侧穿出** ⇒
      **不能二分**，要逐点扫剖面（本项目 `_src/step12_ovl_profile.py`）。
    - **最终值以「2× 放大 + 纯色底」的视觉扫描为准**（本项目 `step9b_tail_zoom.py`：青底 → 漏底即为缝），
      闸门只负责「弯曲不新增缝」的**回归防护**。**把这条局限如实写进脚本 docstring。**
    - 底用**青色**（`(0,255,255)`）最灵：任何漏底一眼可见；白底会被高光骗过去。
11. **★ 弯曲/游走演示图的作图铁律**（不遵守就出「看不出 S」的废图）
    - **路径总长必须 ≈ 链长**：本体只覆盖「头当前位置往后**一个链长**」这一段
      （拖尾运动学）。路径 3600px 而链 966px 时，无论怎么渲都只是「一小段弧」。
      ⇒ 给路径函数加 `target_len` 归一化。
    - **缩放要绕「外框中心」不要绕「形心」**：形心不在外框中心 ⇒ 本体被偏置出画。
      最稳的最终做法 = **渲到透明画布 → `getbbox()` 取内容外框 → 居中贴到底图**（永不出画）。
    - **把头走过的路径画成青色虚线**：本体「抄近路」的差值一眼可见，是解释 R_min 最好的图。
    - 关节角**标在图上**（`±11°`），一眼就能看出是否顶到上限。

### 4b.6 包骨架：「N 段零污染」+ 自制图集零换算（2026-09-27 已全套闸门验证）

| 想知道 | 结论 |
|---|---|
| N 段会不会污染**卡库 / 图鉴 / 波次** | **不会，只要只给头段写 `Resources/Cards/<Key>.tres`**。`Resources/Cards/` 才是**注册**位置；其余段的 Packet 只写进包内镜像 `Packet/<Key>.tres`（不注册）。插件生成它们 **直接从运行时注册表取 PackedScene**（见 §4b.8 —— ⚠️ **不要**用 `ModLoader.TryInstantiateEffectiveCharacter`，它对纯资源包会失败且可能整包回滚），只依赖 manifest 的 **`provides.Character`** ⇒ **不需要 Packet** |
| `provides` 怎么写 | `Character`: N 个键全列；`CharacterSprite`: N 个键全列；**`Packet`: 只头段 1 个键** |
| ⚠️ 上一条的**适用前提**（2026-10-02 踩坑补充） | 「只发 1 张卡」**仅在「其余 N−1 段不是卡牌放置角色」时成立** —— 它们的生成必须走运行时注册表的 `Character` 直取 `PackedScene`（§4b.8 那条路）。<br>★ 反例：**巡演舞王指挥官** 的三只是**各自独立可放置的僵尸**（`Packet.Create` 召唤），⇒ **三只都必须发 `Resources/Cards/<Key>.tres`**、`provides.Packet` 列 3 个键。写成 1 个键 + 1 张卡会得到 `required manifest runtime entry is not registered` ⇒ 整包不生效。<br>★ 判据一句话：**「它会不会被 `TowerDefenseManager.GetPacketConfig(key)` + `packet.Create` 生成？」会 ⇒ 必须有卡。** |
| 自制 `.dat` 的锚点口径 | 把 `sliceTransforms` 设为 **identity**、`origin = (0,0)` ⇒ 每张部件图的**图像中心 = 角色原点** ⇒ 上游算好的 `link[i]`（圆心间距口径）**可直接当角色原点间距**，插件零换算。Scene 里再用 `TransformPoint(12,36)` + `<Key>(−12,−36)` 让净位移 = 0 来闭合 |
| 能不能只做一份图集 | 能：N 段**共用同一份** `.tres`，靠 `Animation/Clip` 选自己那一帧（`.dat` 一个文件承载一张图集 ⇒ 把 N 片拼一张） |
| 两份构建要各跑一遍吗 | 要（`remake` / `console` 的 `PlantsVsZombies.dll` 字节不同）。★ 但实测**插件编译产物两份完全相同**（程序集引用只记名/版本，不记 MVID）⇒ 差异只在运行期。⚠️ console 那份的真实目录是 `D:\zzz\植物大战僵尸**杂交**重制版\data_PlantsVsZombies_windows_x86_64` |

### 4b.7 ★★★ 手写 `.tscn` 的「三方一致」：`[node parent]` / `NodePath` / 实际路径

**症状**（`《星空机械蜿蜒》` 实机首测，2026-09-27）：
图鉴里卡牌**图片与描述全空**；卡牌能选中但**拖放后场上什么都不画**；**零崩溃、零显眼报错**。

日志只给两条（但足够定案）：
```text
ERROR: [InformationPanel] Character preview 'X' has incompatible serialized properties.
ERROR: [TowerDefenseCharacter] Disabled invalid runtime character 'X': config or sprite is null/invalid.
```

**根因**：场景里写了

```text
sprite = NodePath("SpriteGroup/TransformPoint/<Key>")            # ① 期望路径
[node name="<Key>" parent="SpriteGroup/TransformPoint/<Key>" …]  # ② 实际会挂成 …/<Key>/<Key>
```

Godot 里 `[node name="X" parent="P"]` 的**完整路径 = `P/X`** ⇒ ②比①**多一层**
⇒ `NodePath` 解析为 **null**。而 Godot 对「`parent` 路径中不存在的中间节点」会
**静默造一个匿名 `Node2D` 占位**（日志里的 `'@Node2D@1370'` 就是它）⇒ 现场一片安静。

**为什么「图鉴空」和「场上不画」是同一个 bug** —— 两处 C# 判据都是 `sprite == null`：
- `Prefab/GUI/InformationPanel/InformationPanel.cs:151-157`：命中即 `PushError` 后**直接 `return`**
  ⇒ 后面的 `nameLabel` / `expressionLabel` / 数值**一个都没赋**；
- `Prefab/TowerDefense/Character/TowerDefenseCharacter.cs` `DisableInvalidRuntimeCharacter()`：命中即判 invalid。

**正确写法（三处交叉验证，别自己发明）**：
`addons/ModEditor/FileSystem/XWResourceCreateRoute.cs:650`（ModEditor 官方「新建角色」模板，
逐字 `[node name="{0}Sprite" parent="SpriteGroup/TransformPoint" …]`）
＋ `SuperGatlingPaper`（实机可用的换头僵尸，`parent="SpriteGroup/TransformPoint"`）
＋ 基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:39`（`TransformPoint` 的 parent 是 `SpriteGroup`）。

**纪律**：
- ★ 自检**必须连「整个节点声明行」一起断言**（`[node name="{key}" parent="…" index="0" instance=…]`），
  只查 `sprite = NodePath(…)` 那一行是**自检盲区** ⇒ 全绿而实机不画（假绿第 ④ 类）。
- ★ 再加一条**负向**断言：源码里不得出现 `parent="…/<Key>"`（复刻这个 bug 的形态）。
- ★ **调试第一动作 = 读 `logs/godot.log` 的 ERROR/WARN，再读源码，别推理。**
  日志在 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\logs\godot.log`（最新会话）
  ＋ `godot<时间戳>.log` 归档 ＋ `PVZHE_Logs/godot_startup_*.log`。
  「零崩溃、零报错、就是不显示」这类症状，日志几乎一定有 `ERROR`。

### 4b.8 ★★★ `CompanionOnly` 是双刃：找不到类会**整包回滚**——纯资源包别用

**症状**：`WARNING: 生成第 N 段失败…诊断：角色场景缺少 CompanionOnly 伴随脚本元数据。`

**机制**：`ModLoader.TryInstantiateEffectiveCharacter`（`addons/ModEditor/ModSystem/ModLoader.cs:843`）
**只走** `XWModCharacterCompanionRuntime.TryCreateInstance`（`XWModCharacterCompanionRuntime.cs:160`），硬要求：

1. 场景 root 带 `metadata/mod_character_script_binding = "CompanionOnly"`（`:180`）；
2. `metadata/mod_character_script_path` 非空，且**文件名去扩展**得到的类型名
   **必须存在于 mod 的托管程序集里**、非抽象、且 `authoredRoot.GetType().IsAssignableFrom(type)`（`:185-192`）
   —— 然后 `Activator.CreateInstance(type)` 造新节点**替换**场景 root。

★★ **致命点**（`ModLoader.cs:630-638`）：场景带了 `CompanionOnly` 却找不到该类 ⇒
`TryCreateInstance` false ⇒ **`return false` 把整包回滚**
（`[ModLoader] package rolled back after companion binding failure: <id>`）。
⇒ 对「纯资源包」（场景就是普通 `TowerDefenseZombie`、没有 per-segment 脚本）**根本不是可选项**。

**正路**：直接用运行时注册表自取场景并实例化 ——

```csharp
if (XWModRuntimeRegistry.TryGetEffectiveRegistration("Character", key, out XWModRuntimeRegistry.Registration reg))
{
    PackedScene scene = reg.ModValue.As<PackedScene>();   // = ModLoader.cs:644-653 注册的 Variant
    Node root = scene.Instantiate();
    TowerDefenseCharacter seg = root as TowerDefenseCharacter;
    if (seg == null) { root.Free(); }
    // AddChild 之后再 SetGlobalPosition（入树才 _Ready ⇒ _Init ⇒ hitpointsSave 才有值）
}
```

`Registration.ModValue` 就是 `ModLoader` 在 `ApplyMod` 时注册进 `Category == "Character"`
的那份 PackedScene ⇒ 「资源能否加载」与卡牌放置时**完全同源**。
⇒ 生成器 `BANNED_TOKENS` 里加 `"CompanionOnly"`（产物侧扫描）+ 自检加断言防它回来 + 一条负向用例。

### 4b.9 ★★★ 缩放：**拆成两层**（单卡 / 整体布局），间距还要带「不重叠下界」

**背景**：自制 `.dat` 的 `sliceTransforms` 是 identity + `origin = (0,0)` ⇒ 部件图像
**1 px : 1 游戏单位**落地（草坪 = 9 格 × 80 = 720）。而 Phase 1 的 `skin_params.json`
是**像素域**真源（`Σlink = 1022 px`）⇒ 直接落包会比草坪还长 74%。
⚠️ Phase 1 的 `display_scale` **只用于预览图**（把 1400×600 地图按真实比例渲到交接图），
**从来没有进入包** —— 别以为它在生效。

**修法**：拆成**两层**常量，职责分离 —— 只有这样「用户说放大 N 倍」才说得清**作用在哪**：

| 层 | 常量 | **作用对象** | 落点 |
|---|---|---|---|
| **A 单卡缩放** | `GAME_SCALE = S` | **每一个部件自身**（= "单张卡片"）。**不决定段间距** | Sprite 节点 `scale = Vector2(S, S)`；hitbox `Size = Vector2(w×S, h×S)`；图鉴/卡面预览 `packetAnimeScale`/`Offset` |
| **B 整体布局缩放** | `LINK_SPREAD = k` | **段间原点间距**（= "整体"的水平跨度）。**完全不动部件尺寸** | 插件里那 N−1 个数 |
| C 不重叠预留缝 | `LINK_GAP_GAME` | 相邻两段「半宽和」之外再留的缝 | 同上 |

⇒ `link[i] = max( 像素值 × S × k , (w[i] + w[i+1]) / 2 × S + GAP )`

★★ **那个 `max` 不是装饰**：上游 `links[]` 里通常含**刻意重叠**
（为让接缝零漏缝，例：`OVL[0]=118` 头→首节深插、`OVL[9]=78` 末节→尾）。
它们是「间距 < 半宽和」的**负**重叠 ⇒ **线性缩放的倍率改不了符号**
（实测：间距 ×4 之后这两处**仍**重叠 12.75 / 5.75 游戏单位）。
⇒ 用户只要说"**不重叠**"，就必须用下界顶高，否则乘几倍都还压着。

**⚠️ 漏乘的后果分三种，别混**：
- **A 漏**（Sprite 不缩）⇒ 1 px 源素材 = 1 游戏单位，整体过大；
- **B 漏**（间距不缩）⇒ 部件缩了而间距没缩（或反之）⇒ **蛇身处处脱节**；
- **hitbox 漏** ⇒ 判定悬在图像外（打不到 + 打空），**零日志**。

**纪律**：
- ⚠️ **不要**改 `skin_params.json`（含 `links[]`）：Phase 1 的两道闸门读它 ⇒ 一改就红。
  缩放只加在**生成器给游戏侧的**那份上。
- ⚠️ **不要**改 `.dat` 的 `sliceTransforms`（`.tres` 会与 `.dat` 对不上，`verify_pmod` 与自检都会红）。
- ★ 断言里的期望值要用**独立基线常量**（`GOLD_GAME_SCALE` 等）算，**不要**复用产物侧那个已经乘过的 helper
  （`_scaled(w * GOLD_GAME_SCALE)` = 双重缩放 ⇒ 自己造出 N 条红；实测被自检当场抓住）。
- ★ 「像素原值不得出现」这类负向判据要**条件化**：当等效倍率 `S × k == 1` 时它与"正确值"
  本来就重合 ⇒ 那种口径下只会**假红**。改判「下界是否真的被顶起来了」。
- ★ **必做三条断言**（都是用户口径，不能只靠"我算过"）：
  ① **不重叠** `link[i] >= (w[i]+w[i+1])/2 × S`（逐关节）；
  ② **不溢出** `首半宽 + Σlink + 末半宽 <= 地图宽`
     ⚠️ "溢出"= 超出**地图**；**不是**超出草坪（一行 9×80=720）—— Boss 比草坪长属设计；
  ③ **口径史**：用户会反复改（实测 `0.75 → 0.25 → 0.50` ＋ 布局 `×2`）⇒ 历史写进 docstring，
     保证"改回只需动固定几处 + 有断言兜底"。
- ★★ **「要不要重叠」是观感问题，不是对错 ⇒ 做成显式开关**（用户实际两次改主意：先要不重叠，
  看到效果又回退）。`LINK_ENFORCE_NO_OVERLAP = False`（忠实沿用上游 `links[]` ⇒ **连成一条**，
  含刻意重叠）/ `True`（下界顶高 ⇒ **段段分开**）。✔ 断言必须**跟着模式条件化**
  （§16 分走「重叠量 == `OVL × S`」或「逐关节不重叠」两条路），并配一条负向专门守
  「断言真的按模式走」（把金标切到 True 而实现留 False ⇒ 立刻红）。
  ⚠️ **诊断脚本的结论文案也要跟着口径走** —— 本例布局表原来**写死**"必须不重叠"，
  模式一关就把**预期行为**报成 `FAIL`（**假红与假绿同样带偏判断**）。
- ★ 交付时给一张**布局验算表**（脚本 import 生成器取真源，改口径自动跟着变）：
  逐段的像素/游戏尺寸、链上原点 x、与上段的间隙（负数 = 重叠）＋ 整体跨度 ＋ 不重叠/不溢出结论。
  （本仓样板：`.cache/_layout_table_ss.py`。）

### 4b.11 ★★ 排查「自制 `.dat` 角色不显示」的正确顺序（2026-09-28 实证，含两次误判）

**别急着改渲染设置 —— 按这个顺序查，每一步都要有日志或源码依据：**

1. **先读 `logs/godot.log`**（第一动作，不要先推理）。`sprite is null` /
   `incompatible serialized properties` / `Disabled invalid runtime character`
   这三条只要命中一条，**根因就在场景 NodePath 或 config**（见 §4b.7），与美术/渲染设置无关。
2. **看节点是否被反复重建**：日志里 `已生成 N 段（累计 M）`，**M 持续增长 = 有段在被外部销毁**
   ⇒ 屏幕上当然看不到（或只闪一下）。此时**加诊断日志**（打印**具体键** + `IsInstanceValid` 判定 + 帧号）
   比继续翻渲染代码有效得多。
3. **最后才查渲染设置**，且必须**对齐一个同类型、实机可画的金标包**
   （僵尸/植物：`SuperGatlingPea` / `UltimateCherryGod`）。

**⚠️⚠️ 关于 `forceLocalRender` / `forceCpuPoseRender`（两个高频误区）：**
- 它们治的是「**动画静止 / ESC 暂停跳帧**」（= **能显示但不动**），**不是"完全不显示"** ——
  症状别认错，认错就是白忙一整天（实测踩过）；
- 它们是 **`public` 非 `[Export]`** ⇒ **写在 `.tscn` 里完全无效**（Godot 静默忽略，连 warn 都没有），
  只能在**插件运行时**用 C# 赋值。**产物场景里不该出现这两行。**
- 实机可画的金标包**都没有**它们，而**都有**：`useMultiMesh = true` / `useTween = false` /
  `Animation/LayerVisible/<每个层名> = true` / `Animation/MediaReplace/<每个媒体名> = null`。
  （层名 / media 名从图集 `*_params.json` 的 `layer_name` / `media_names` 读，别手写。）

**⚠️ 同一语义在不同代码路径上可能结论相反（差点被骗）：**
`AdobeAnimateSprite._Get()` 里判 `Animation/LayerVisible` 是
`num < _layerVisible.Count && _layerVisible[num]` ⇒ **空数组返回 false**；
但**渲染真正消费**的是 `_cachedAllLayersVisible`（`:9045-9062`）⇒ 空数组时 `i >= num` 恒真 ⇒
**保持 true（全可见）**。⇒ **必须找"真正被渲染消费的那个变量"**，不能看到第一处 `return false` 就下结论。

**⚠️ `alpha.getbbox()` 对抠图产物没有判别力**：低 alpha 噪点会把框撑满整幅图
（实测 11 张全部 `(0,0,w,h)`）⇒ 必须**按阈值**（如 `>= 128`）过滤后再取 bbox，
或直接统计"四角 / 四边中点 alpha"。

**⚠️⚠️ 最重要的一条：「日志里没有本 mod 的报错」≠「本 mod 没问题」。**
真凶可能发生在**别的子系统**里，backtrace 里**根本不出现 mod 名字**。
本仓实证：插件生成的段被 `CharacterRegister` 自动注册进 `TowerDefenseManager`，
而关卡编辑器保存时（`LevelEditorMapEditor.Save()`）会**遍历所有已注册角色**并调
`CreatePreSpawnConfig`，其中 `:702` 有一行**裸访问** `character.packet.saveKey`
⇒ 段的 `packet` 为 null（它不是"卡牌放置"来的）⇒ **NRE** ⇒ 编辑器保存/测试失败
⇒ 用户"拖放后看不到任何结果"。
⇒ **查"mod 不生效"时，除了 grep mod 名，一定要把同期全部 ERROR/WARN 看一遍**
（用 `sed -n 'A,Bp'` 看上下文，别只 grep）。修复：`packet` 是 public 字段，插件给它补上
（引擎先例 `BugOverviewDolphinPlacementJumpBlockRuntimeTest`）。

**⚠️ 同理：自检/诊断日志本身也会误报。** 本仓"段失效"日志最初把
**首次生成前的 `null` 空位**报成"被回收"（`第 1 段…C# 引用为 null；帧=518`）⇒
必须加"**曾经生成过**"门控再报警。

**⚠️⚠️ 给"运行时生成的伴随角色"补 `packet` 时，必须成对设 `characterFilter = true`。**
本仓实证的完整因果（走了一轮冤枉路）：
- 关卡编辑器 `LevelEditorMapEditor.Save()` 会**遍历 `TowerDefenseManager.GetCharacter()`
  的每个已注册角色**，为每条写 `preSpawnList`（`packetName = character.packet.saveKey`，
  `:702` 是**裸访问**）⇒ 伴随角色 `packet == null` 就 **NRE**（编辑器保存/测试失败）；
- ⇒ 补 `seg.packet = 头段的 packet` 修好了 NRE，**却把 10 段"伪装"成头段** ⇒
  10 条 `packetName` 全等于头段 ⇒ **进关卡时引擎 spawn 出 11 个头段**；
- ⇒ **正解**：`seg.packet = …`（挡 NRE）**＋** `seg.characterFilter = true`
  （`TowerDefenseCharacter.cs:365` public 字段；`TowerDefenseManager.cs:520-529`
  `GetCharacter()` 里 `if (!item.characterFilter) array.Add(item)` ⇒ 设 true 就不进这份清单；
  UI 标签「只响应角色」`XWBattleFeaturePresenter:508`；引擎自己就这么排除推车
  `TowerDefenseBattleFeatureMower:107`）。**它不动 `characterRegistry`** ⇒
  索敌/碰撞/受击全不受影响，只是"不被当作可保存的关卡内容" —— 正是伴随角色应有的语义。

**⇒ 通用纪律：给"运行时生成、不属于关卡存档"的对象补上"关卡内容才有的字段"时，
必须同时把它从"关卡内容枚举"里排除出去。两条缺一不可。**

### 4b.12 ★★ 贴图相对受击盒「偏右下」⇒ 缺居中 `offset`（自制 `.dat`，2026-09-28 实证）

**症状**：11 段都能显示、也排成一条，但**贴图整体偏到受击判定的右下方**（偏移量约半个图幅）。

**根因**：`AdobeAnimateDrawItemBuilder.cs:683-689`（走 `sprite.Texture` 的那条路径）
```csharp
rect      = ResolveSpriteSourceRect(sprite, texture);     // 源矩形（**像素**尺寸）
vector    = ResolveSpriteDrawOrigin(sprite, rect.Size);   // = sprite.Offset − size/2（仅当 Centered）
transform = new Transform2D(axisX * size.X, axisY * size.Y, vector);
```
纹理 `[0,1]²` 映射到「**以 `vector` 为左上角**、边长 `size`」的矩形 ⇒ **`vector` 就是图像左上角**。
⚠️ `AdobeAnimateSprite` 在这条路径下 `Centered` **不是** true（它自己管绘制原点）
⇒ `ResolveSpriteDrawOrigin` 里那个 `− size/2` **不会**发生
⇒ 只给 `offset = 0` 就等于「**图像左上角落在角色原点**」⇒ 整幅偏**右下**。

（`externalAtlasCentered`（`AdobeAnimatePart.cs:33`，默认 **true**）只作用于**外部图集部件**
 `AdobeAnimatePart` 那条路径；自制皮肤走的是 `sprite.Texture` 路径，用不到它 ——
 别看到它默认 true 就以为已经居中了。）

**修法**：Sprite 节点显式给 **`offset = Vector2(−w/2, −h/2)`**，**像素值**
（`offset` 在节点本地空间生效、会随 `scale` 一起缩放 ⇒ **不要**乘 GAME_SCALE）。
每个部件按自己的 `w/h` 给，不要统一一个值。

**★ 交叉证据（以后照这个查）**：拿一个**实机可画的同类包**看它的 `offset` ——
它一定与"图像尺寸的一半"有明确关系。本仓：`UltimateCherryGod` 帧 138×129 给
`offset = (-69, -93)`，其中 **x 分量 `-69` 恰好 = `−138/2`**（自己补居中量），
多出来的 y 是它把锚点放在**脚底**（比中心再低 28.5px）。

**★ 概念区分（易混）**：`.dat` 的 `origin = (0,0)` 是**数据侧口径**，只表达
"部件图像中心 = 角色原点"这个**设计意图**；要**让引擎真的按这个画**，
还必须在 Sprite 节点上给足 `offset`。**两者不是一回事，缺后者就偏。**

## 4c. ★★★ 纯贴图路线：`.tres`/`.dat` 换贴图 · 防具 N 档 · 尺寸铁律（2026-10-05 实证）

> 适用：**只改外观、不碰机制**。参考对象 `ZombieTimeMage`
> （`V0.29/Asset/Anime/Character/Zombie/Chapter10/TimeMage/`）。

### 4c.1 贴图到底放在哪 —— 先确认载体，别找错文件

| 载体 | 内容 | 备注 |
|---|---|---|
| `<角色>.tres`（`AdobeAnimateData` format=4） | **几何 + 媒体表 + 图层表** | 骨架/动画的权威 |
| `.dat`（=`.tres` 的 `animeFile`，如 `res://ModAssets/<X>.dat`） | **图集像素 `px` + 媒体矩形** | ★ **绝大多数角色的贴图真身在这里** |

- 实测：`AlphaSquadAnime.tres` 里 `rasterCompositeData = null`、`extraMediaReplaceTexturePaths = []`，
  **一条 `res://…png` 都没有** —— 贴图全在 `.dat` 的 `px` 里。
- ⇒ **改外观 = 改 `.dat` 图集像素**（或改 `mediaRects` 指向新文件）；只在 `.tres` 上翻找不到图。
- 解析/重打包：`_redo/dat_lib.py` 的 `parse_dat()` / `render_frame()` / `build_dat()`。

### 4c.2 `.tres`（format=4）字段顺序与逐 slice 对齐（照抄，别再猜）

字段顺序（`ZombieTimeMage.tres` 实测）：
`script / animeFile / frameRate / frameMax / frameOffsets / frameCounts / sliceKeys / sliceMediaIds /
sliceLayerIds / sliceDrawOrders / sliceFlags / sliceTransforms / sliceAlpha / mediaRects / events / clips /
mediaDictionary / layerDictionary / rasterCompositeData / extraMediaReplaceTexturePaths`
（⚠️ `sliceFlags` 与 `sliceAlpha` 的相对位置**不固定**，按**字段名**取，别按下标。）

- ★ **`sliceMediaIds[i]` = 第 i 个切片的媒体 id** —— 「换贴图」就是换它。
  ⚠️ **坑：`sliceKeys[i]` 低 16 位恒为 0**（`sliceKey == layerId<<16`），**不是**媒体 id；按它找图会全指到 `Ground`。
- `sliceLayerIds[i] / sliceMediaIds[i] / sliceDrawOrders[i] / sliceAlpha[i]` 与
  `sliceTransforms[6i:6i+6] = [xx,xy,yx,yy,ox,oy]` 按 **slice 序号**对齐；
  第 f 帧切片段 = `frameOffsets[f] .. +frameCounts[f]`。
- ★★ **`sliceLayerIds` 与 `sliceDrawOrders` 逐项完全相同**（`ZombieNormal` / `ZombieTimeMage` 都成立）
  ⇒ **绘制顺序 = 图层 id 升序（自下而上）**；「盖最上层」= 插到帧末。
- 图层显隐**不在 `.tres`**，在 `.tscn` 根节点的 `Animation/LayerVisible/<图层名>`；
  换图在 `Animation/MediaReplace/<媒体名>`（`null` = 用内置）。
- 通用解析器：`_redo/legion/_layer_table.py`（带 `layerIds==drawOrders` 自检，导出 `_layers_<标签>.json`）。

### 4c.3 ★★★ 尺寸铁律：贴图尺寸 == 宿主图层媒体矩形

实测无例外 ⇒ **每个插槽的目标画布 = 该层 `mediaRects` 的 `w × h`**（见 `_layers_*.json` 的 `rect`）。
同层多媒体的例子：`Zombie_outerarm_upper`→`upper.png`+`upper2.png`（断臂残端）；
`Zombie_outerarm_hand`→`hand.png`+`hand2.png`；`Zombie_whitewater`→3 张。

### 4c.4 防具受损 = 「一个图层 + 它的媒体」，三档 = 同媒体位三张**同尺寸**贴图

- 数据：`Registry/Armor/Config/<ArmorName>.tres`（脚本类 `TowerDefenseArmorTypeData`）：
  `armorName / damagePoint(总耐久) / stagePersontage(阈值数组，setter 内降序) /
  stageAnimeTexturePaths(各档贴图，数量=档数) / impactAudio / damageAudio / limitMaxHit /
  explodePersontage / armorMethodFlags`
- 槽位：`Anime/Character/<类>/<角色>/Armor/Config/<...>.tres`（`ArmorSlotConfig`）：
  `replaceMethod`（**`Media`=换某 media 贴图 / `Sprite`=建独立 Part 挂 `slotPath`**）/
  `replaceMediaName` / `slotPath` / `offset` / `rotation` / `scale` / `alphaMultiplier` /
  `destroyFliter` / `openFliter` / `closeFliter`（`&` 分隔的图层名）
- 运行时 `CharacterArmorData.SetArmorReplace(sprite, armorName, stage)`（`Armor/CharacterArmorData.cs:157-174`）：
  `stage = Mathf.Clamp(stage, 0, paths.Count-1)`；Media ⇒ `sprite.SetAtlasReplace(replaceMediaName, paths[stage])`；
  Sprite ⇒ `CreateArmorPartNode()`（同文件 176-194：按贴图**自身尺寸 × scale** 建件）。
- 阈值口径（`[0.666,0.333]`）：比例 **>0.666** 用第 0 张（完整）、**0.333~0.666** 第 1 张、**≤0.333** 第 2 张。
- 内置样板（**每套 3 张、三档同画布同相对位置**）：
  `ZombieShield1/2/3.png`=66×123 · `ZombieBucket1/2/3`=62×67 · `ZombieCone1/2/3`=59×57 ·
  `ZombieBlackHelmet1/2/3`=66×73 · `GuardNut_sheild1/2/3`=54×92 · `NanoSheildD1/D2/D3`=46×75，
  路径 `Asset/AtlasSource/Armor/Texture/Character/Armor/<Name>/`。
- ★★ **三档必须同画布 + 同相对位置**，否则换档时盾/面具**跳位**。
- ★★ **`.pmod` 做三档：走「烘进动画自带图集 + `SetFliter` 切层」，不要走 `SetAtlasReplace`/`SetReplace`**
  （后两者在 `.pmod` 里都**不可能生效** —— 纹理进不了预烘 `Texture2DArray`，实测见 `zombie-pitfalls.md` A7-01/A7-02）。
  做法：把三档图按 **`.dat` 图层名**烘成**并列图层**（本例 `Zombie_head`/`head2`/`head1`、`shield`/`shield1`/`shield2`），
  `.tres` 的 `layerVisible` 里**非完整档默认 false**，运行时 `SetFliter(层名, bool)` 三档互斥切换；
  用 `GetFliter` 做「打开→读回」**层名存在性自检**（写错层名是**静默 no-op**）。
  三档图**多半本来就在源图集里**（基础件的兄弟部件）—— 先查 `parts_*.json` 的 `chain`，别自己重画（A7-03）。
- ★ 档数**不固定**：宝箱 `CoinChest1_1.._5`、`CloneTank_1_1.._5` = 5 档 ⇒ 由 `stageAnimeTexturePaths` 长度决定。

### 4c.5 本体部位受损 = `DamagePoint`（与防具无关的另一套）

- 单点：`<角色>/DamagePoint/Config/*.tres`（`CharacterDamagePointConfig`）：
  `damagePointName / damagePersontage / animeFliterClose(关哪些图层，`&` 分隔) /
  replaceMediaName + replaceMediaTexturePath`
- 汇总：`DamagePoint/<角色>DamagePointData.tres`（`CharacterDamagePointData`）：
  `damagePointList / damagePointDictionary(Name→{Close,Config,Open}) / fliterCloseAll`
- 实例 `ZombieTimeMage`：`Head` 关 `anim_head1&anim_head2&anim_innerhat&anim_outerhat`（头飞掉）；
  `Arm` 关 `Zombie_outerarm_hand&Zombie_outerarm_lower` + `Zombie_TimeMage_outerarm_upper.png → …_upper2.png`（断臂残端）。
- 受损图存 `Asset/AtlasSource/DamagePoint/Anime/Character/<类>/<角色>/DamagePoint/`。
- `extraMediaReplaceTexturePaths`（`.tres` 内）= 与本套呼应的受损替换图清单。

### 4c.6 拼装词汇表（`ZombieNormal` / `ZombieTimeMage` 共用）

`anim_innerarm1/2/3`（远臂上/小臂/手）· `Zombie_outerarm_upper/lower/hand`（近臂）·
`Zombie_innerleg_upper/lower/foot` · `Zombie_outerleg_upper/lower/foot` ·
`anim_head1`(头) / `anim_head2`(颌，媒体 `Zombie_jaw.png`) / `Zombie_neck` ·
`Zombie_body`（TimeMage 拆 `_body2..body5` 共 5 片）· `anim_innerhat`/`anim_outerhat`/`anim_hair`/`anim_tongue` ·
道具 `stick`/`rune1..3`/`watch`/`TX*`/`Clock*`/`Layer 1..5`；`_ground`(层 0) 常隐；
`AnimeClips`/`AnimeEvents` 是元数据层**不绘制**。

### 4c.7 挂点（Slot）

`.tscn` 根下 `Node2D` + `AdobeAnimateSlot.cs`：`followSlotId`(跟随哪个图层运动) /
`drawLayerId`(画在该层层级) / `offset` / `position` / `scale`。
`ArmorSlotConfig.slotPath = NodePath("HeadSlot")` 即挂到这些点上。
`armorData = null` ⇒ 该角色无防具（`ZombieTimeMage` 的帽子是**骨架层**，不是 armor）。

### 4c.8 「完整 / 轻微 / 严重」的定量判定法（给三档素材排序，别靠眼看）

按 **bbox 右上角对齐、不缩放**，算「缺失材质 / 多出材质」面积占比：
**缺得多 = 更严重**；「多出」≈0 ⇒ 同源减材质（确证同一件）。
⚠️ 先 resize 到同宽再比会造假（宽 112 vs 120 ⇒ 凭空多出 6.5%）。参考 `_redo/legion/_dmg_quant2.py`。

### 4c.9 ★★★ 离线渲染任意内置角色（换骨架 / 对位前的必杀工具）

不启游戏，就能把**任意内置角色的原始贴图**抽出来、并用它的**骨架几何**离线渲染任意帧。

**（a）抽原始贴图** —— 全局图集 + 清单：
`<V0.29>/addons/AdobeAnimateEditor/GeneratedAtlas/AdobeAnimateVisualTextureArray.png`
= **40960 × 2048**（20 页 × 2048 横排，**页 p 原点 x = p*2048**）；
清单 `…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres`：
`SourceKeys`(源 `.dat` 路径) / `SourceStarts[i]` / `SourceCounts[i]` / `MediaAtlasPages[j]` / `MediaRects[j]`。
取件 = 源下标 → 媒体区间 → `crop((p*2048+x, y, p*2048+x+w, y+h))`。

⚠️ **坑**：`MediaRects` 是 `Array[Rect2]([Rect2(x,y,w,h), …])` —— **不能「抓所有整数」**，
`Rect2` 里的 **2** 会被当数据（44 条能被解析成 12831 条）。必须按 `Rect2\(...\)` 正则取。
工具：`_redo/legion/_atlas_extract.py <角色名关键字> <输出目录>`（实测 TimeMage 区间 `[7493,7537)`、p7–p11）。

**（b）`.tres` 直接渲染**：`_redo/legion/_tres_lib.py::parse_tres()` 把 `.tres` 解析成
**与 `dat_lib.parse_dat` 同构**的 dict，`pack_atlas()` 自建图集后即可调
`dat_lib.render_frame()`。⇒ **不必凑齐 `.dat`**，内置角色也能离线预演与逐帧比对。

**（c）换骨架前先查「基础僵尸要哪些 clip」**：`Prefab/TowerDefense/Character/TowerDefenseZombie.cs`
用**通用 clip 名** —— `:117 walkAnimeClip="Walk"` / `:123 swimAnimeClip="Walk"` /
`:129 attackAnimeClip="Eat"` / `:135 dieAnimeClip="Death"`。
⇒ 骨架只要有 `Walk`/`Eat`/`Death`(+`Idle`) 就能跑；`Walk1/Walk2` 这类编号名**不是必需**。

---

### 4c.10 ★★★ 「借骨架换皮」的锚点法（换贴图后怎么定位，别再手调 offset）

> 2026-10-05 实测（《阿尔法小队》换 `ZombieTimeMage` 骨架）。全文 `REFERENCE.md §40`。

**前提 1 —— `M` 不是恒等。** 内置僵尸的切片变换是 `M = 0.8 × 旋转`
（实测 `anim_head1  M=(0.8000,0,0,0.8000)`，整表缩放谱峰值 = 0.8）。
⇒ 「媒体矩形尺寸 = 屏幕尺寸」只在把 `M` 改成恒等时才成立；沿用原 `M` 时要乘 0.8。

**前提 2 —— 枢轴 = 媒体左上角**（`screen = O + M·p`，`p=0 ⇒ screen=O`）。
所以 `O` 就是该 slice 绕之旋转的点；肢体段的 `O` 恰在肩/肘/腕/髋/膝/踝。

**公式**：取一对对应点 `C_tm`（源层媒体坐标）/ `C_our`（自备件媒体坐标），令二者屏幕上恒重合：

```python
M_our,f = (k / s) * M_tm,f          # s = |M_tm| = 0.8
O_our,f = O_tm,f + M_tm,f·C_tm - M_our,f·C_our
```

这是刚体+相似变换 ⇒ **旋转完全同步、关节不脱位**。三种取法：

| 取法 | C_tm | C_our | 用在哪 |
|---|---|---|---|
| 关节对齐 | `(0,0)` | 件里的关节像素 | **肢体段**（上臂/小臂/大腿/小腿/脚） |
| 中心对齐 | 源媒体矩形中心 | 件 bbox 中心 | 头 / 小件 |
| 任意比例 | `(r.w·u₁, r.h·v₁)` | `(w·u₂, h·v₂)` | 躯干 / 披肩 / 道具握把 |

**k 不能全用一个数**：骨架的段长 ≠ 原画比例。取法 = `骨架段长 / 原画段长`：
- 臂 40.3 / 56.7 = **0.71**；腿 47.0 / 51.3 = **0.92**；头/整figure ≈ **0.45**。
- 用单一 0.45 ⇒ 远段够不到关节、一走路就脱节。折中取「主 0.45 / 臂 0.62 / 腿 0.66」。

**拆解整肢件：切点取「骨架关节比例」，不是「原画看得到的弯折处」。**
实测原画肘弯在整臂 25%、骨架肘在 60%；膝：原画 68% vs 骨架 56%。
⇒ `切点 = 近端 + 比例 × (远端 − 近端)`，法线指向近端。
重绘三件事：① 圆头（半径 = 该处肢体半厚）；② 断口补色（八邻域最近像素扩散）；
③ 复描边（**只压新增边界**，重压原边界会让原画发胖）。

**两个必踩的坑**：
- **一件大衣只能进一个体节层**。`Zombie_body / body2 / body3` 是长袍的主体/侧片/后片，
  三层各塞一件大衣 ⇒ 髋部叠成黑块、把腿整个盖住。
- **道具插在手层之前 = 被手握住**（`Alpha_shield`/`Alpha_blade` 在 `Zombie_outerarm_hand` 之前）；
  插在之后 = 盖住手。

**工具**：`_geom.py`（定点合成，量逐层 alpha 足迹）、`_split_draw.py`（拆解重绘 + 产出
`parts_index.json`，含每件的 `joint` 像素坐标，装配器直接读）、`build_parts.py`（装配器）、
`_compare_fig.py`（图×成品×原版按整figure高度归一出对照图）、`_inspect.py`（逐层着色查错位）。

### 4c.11 ★★★ 「贴合原画」的定量法 + 自定义动画节奏

> 2026-10-05 实测（《阿尔法小队》第 6 轮）。全文 `REFERENCE.md §41`。

**① 逐行宽度轮廓对比（对位通用方法）**：bbox 看不出「哪一段太窄」。
把**目标原画**与**我们的装配**都归一化成 `÷整figure高 ×100`，逐行取 left/right/width：
```python
H, W = m.shape                       # m = alpha>40，已裁到 bbox
for i in range(21):
    r = np.where(m[int(i/20*(H-1))])[0]
    left, right, width = r.min()/H*100, r.max()/H*100, (r.max()-r.min())/H*100
```
差异 >6 的段就是要改的地方；再用「单画一层」查是谁占着最左/最右。
实测：头部 0–25% 差异仅 −1（k_主 对了），差异全在半身道具。

**② 从原画定量抠道具尺寸**（别目测）：用「亮度+位置」分割 ——
深色盾 `lum<55 & x<125 & y>200` ⇒ 124×191（占宽 38.3% / 高 45.5%）；
亮刀 `lum>150 & x>150` ⇒ 约 140×75。「逐行最左 x」突降的那一行 = 盾顶高度。
`k = 目标屏幕尺寸 / 件内容 bbox`（先用 `getbbox()` 去掉画布留白）。

**③ k = 骨架段长 / 原画段长，且同一肢体两段要互相校验**：
臂 24.2/34.0 = 16.1/22.7 = **0.71 ✔**；腿 26.5/28.7 = 20.5/22.5 = **0.92 ✔**；头 ≈0.45。
★ **手必须单列一档**（手套 45×49，按 0.71 会画到 32×35，比它握的匕首还大）⇒ 0.55。

**④ 绘制序的三条冲突**：道具要看得见（远臂原在大衣**后面**，静止帧完全落在
大衣轮廓内 ⇒ 一点看不见）／抬臂不能挡脸（远臂提到头之上就会盖住面罩）／面罩是辨识度。
⇒ 远臂的**上臂·小臂**留在大衣后面，只把**「道具+手」**提到大衣之上，**头放整层序末尾**。

**⑤ 自定义动画节奏：先量原 clip 里哪条链在动**，别猜。
逐帧打印各层 `math.degrees(math.atan2(e[2], e[1]))` 与该层 `O`。
实测 TimeMage 的 `Shooting`：**近臂全程 −3.0° 不动**，远臂 −5.8°→+99.3°→−5.8°
（`SpellMuzzleSlot` 跟的 `stick` 也属远臂）⇒ 施法臂 = 远臂。
改法：`M' = R(θ)·M`、`O' = C + R(θ)·(O−C)`（`C` = 该段枢轴 = 它的 `O` = 关节）；
整链套同一 θ = 整臂绕肩，再对「肘以远」套 φ = 单独屈伸。曲线按
「抬到位 → 短暂定格 → 快扫 5 帧 60~70° → 缓慢回位」写才有力度。

**⑥ 道具预旋转**：件跟手走时改朝向，最省事是把图本身转好
（`im.rotate(deg, expand=True)` 后重新 `getbbox()`），握把锚点 (u,v) 在转后的图上取。

**工具**：`_profile.py`（轮廓对比）、`_ksweep.py`（多组 k 批量横评）、`_rhythm.py`（节奏曲线）。

### 4c.12 ★★ 道具（盾/刀）对齐原画的三个坑

> 2026-10-05 实测（《阿尔法小队》第 7 轮）。全文 `REFERENCE.md §41.8–41.11`。

**① 量道具位置必须用「根局部固定原点」。**
用渲染画布的 bbox 当原点会「改了半天数值不动」——画布原点是由**全部可见层的几何框**
推出来的，被量的层一挪原点跟着挪。实测：盾的偏移从 −23 改到 −28，量出来一直是 `x7..43`。

**② 判断「谁压在谁身上」不能只看 alpha 并集**（被遮的像素照样在并集里）。
要逐层按绘制序（layerIndex 升序）**覆盖写「最上层编号」**：
```python
top = -np.ones((H, W), np.int16)
for li in sorted(vis): top[mask(li)] = li     # 后画覆盖先画
被压像素 = mask[道具] & (top != 道具层号)
```

**③ 求「道具在原画里的位置与倍率」用模板匹配，评分必须 IoU。**
目测和暗像素分割会被**同色的大件**污染（深色盾 vs 深色大衣/靴子）。
用「召回」评分会让**小模板钻进大块深色里拿满分**（实测假阳性 score 1.000）。
IoU 才靠谱（实测真盾 score 0.780）。

**④ 手持大件用「固定朝向」**（`M_our = k·R(θ_fix)` 常量、`O` 仍由锚点公式推）
⇒ 跟着手走但**不随腕旋转**。表盘、盾牌这类原画里全程竖直的件必须这么做。

**⑤ 反例：「让骨架的手臂去够道具」是死路。**
道具跟随手 ⇒ 转臂时道具跟着走，**间隙不会缩小**；若道具又是固定朝向，臂一转就更「飘」。
⇒ 间隙要靠**道具的锚点 (u,v) 或 k** 去消。
（给整条臂加静态旋转时，旋转中心必须**逐帧用该帧自己的枢轴**，用 f0 的固定点会让非首帧整体漂移。）

### 4c.13 ★★★ 接线口径 + 一条**硬边界**（`.pmod` 用不了外部替换贴图）

> 2026-10-05 实测（《阿尔法小队》接线轮）。全文 `REFERENCE.md §42`。

**★★★ 硬边界**：`.pmod` **无法**让 Armor / DamagePoint 的 `SetAtlasReplace` 生效。
链路：`SetArmorReplace` → `SetAtlasReplace(mediaName, path)` →
`AdobeAnimateGlobalAtlasCache.TryGetReplaceTextureAllocation(path)` →
路径**只接受 `res://` / `uid://`** → 在全局清单 `ExternalTexturePaths` 里**纯查表**。
而全局清单 1117 条**全是工程原生路径**、`GetManifest()` 读死路径；
mod 解包在 `user://ModsCache/`，图集扫描只扫 `res://` ⇒ **mod 贴图永远进不去**。
`replaceMethod="Media"` 与 `"Sprite"` 两条路都堵，且**失败是静默的**（不报错、贴图不换）。

> ★★★ **2026-10-06 v9.1.0.0 更正（本节原绕法②已被证伪，勿再用）**：
> 原绕法②「托管 DLL 直接把 `Texture2D` 赋给 `sprite.mediaReplace[mediaId]`」（即 `SetReplace(Texture2D)`）
> **在 `.pmod` 里同样不可能生效**。实机日志：
> `WARNING: … replacement texture is missing from the shared Texture2DArray atlas; replacement drawing was disabled`
> ⇒ 引擎三条渲染通路（`_Draw`/`DrawExternalAtlasTexture`/管理版 `TryBuildGpuState`）**全部要求纹理在预烘的
> 全局 `Texture2DArray` 图集里**，mod 自带 PNG 进不去 ⇒ 引擎**主动把该精灵的替换整个关掉**。
> **唯一正解 ＝ 把三档图烘进「动画自带图集」＋ `AdobeAnimateSprite.SetFliter(层名, bool)` 切图层**
> （破损/分档图大概率**本来就在源图集里**，且是基础件的兄弟部件 —— 先查 `parts_*.json` 的 `chain`）。
> 详见 `references/zombie-pitfalls.md` **A7-01 / A7-02 / A7-03**。

**四个接线口径**：

| 项 | 口径 |
|---|---|
| `sliceDrawOrders` | **写层号**（= `sliceLayerIds`）。写成「层内序号」会让槽位在层姿态失败后**回退到 drawOrder**，口径漂移 |
| `animeFile` | 三步解析：①原路径直读 ②**相对路径**按 `.tres` 目录 join ③**同名 companion `<tres基名>.dat` 就近解析**。推荐写 `./X.dat` |
| 槽位 | `followSlotId = layerIndex + 1`（引擎用 `followSlotId - 1` 取层号） |
| mod 内引用 | 一律**相对路径**（`../Sprite/X.tscn`），别用 `res://` |

**`armorMethodFlags` 位表**：`NOONE1 BODY2 SHIELD4 HELM8 METALLIC16 INVINCIBLE32
DAMAGEABLE64 DROPABLE128 PASSDAMAGE256 ABSORBOVERFLOW512 CANT_PENETRATE1024
HEAD_COVER2048 BURST_WHEEL4096 BLOCK_PROJ8192`。
内置 `Bucket/Helmet/Cone=216`、`Shield=1236`、`Screendoor=212`。
**不脱落 ⇒ 去掉 `DROPABLE(128)`**。

**工具**：`pack_alpha2.py`（接线生成 + 打包，含全部模板）、`gate_alpha2.py`（装机前离线闸门：
resources 齐备 / `.tres` 与 `.dat` 对账 / LayerVisible 与 MediaReplace 名字存在 /
`followSlotId` 不越界 / clip 名存在 / ext_resource 相对路径可解析 / 外部替换贴图标注）。

### 4c.14 ★★★ 拼不齐就别拼 —— **照搬成品图**（按关节切成件）

> 2026-10-05 实测（《阿尔法小队》v3.0.0）。全文 `REFERENCE.md §43`。

**用「部件表」逐件拼装永远拼不齐**（各件比例、切点、明暗都对不上，实测 Idle IoU 只有 0.882）。
正解：**直接拿完成品图**（整装插画）按解剖关节切成 N 件，每件像素原样搬，再把
「件的关节」对齐骨架同层的枢轴。因为切的是**同一张图** ⇒ **全局只有一个 k**，
原姿下重组 = 成品图（缩放+平移）**逐像素一致**（实测 IoU **0.965**）。

**定位公式**（对每层 L，`J_L` = 它在成品图里的关节）：
```
C_our = J_L − 件bbox左上
C_tm  = M_tm,0⁻¹ · (k·J_L + T − O_tm,0)     # 第 0 帧反解一次即可
M_our,f = (k/0.8)·M_tm,f
O_our,f = O_tm,f + M_tm,f·C_tm − M_our,f·C_our
```
新增层（骨架没有的，如盾/匕首）要另立 **FOLLOW 表** 指向一个「载体层」。

**定 (k,T)**：★ 改 k/T 只是对整幅结果做相似变换 ⇒ **只渲一次**，之后纯数学搜 IoU 最大
（千万别每个候选都重新构建，几十次构建会超时被杀）。

**两条必踩的坑**：
1. **切区会漏** —— 成品图里常有「一整块连体形状」（本项目底部是一整块大鞋底 x90..300），
   只按关节画小框会漏掉半边。先打**网格** + **逐行打印不透明 x 范围**核对跨度。
2. **切区允许重叠** —— 重叠处像素本来就相同 ⇒ 原姿逐像素不变；只有动画时有轻微拖影。
   **宁可给足、别切漏。**

**验收指标**：alpha 掩膜 IoU（归一化到同一 figure 高 + 质心对齐）——
静止/走路帧 ≥0.95；Eat/Death 这类换姿势的帧 0.55~0.6 属正常。

### 4c.15 ★★★ 「MOD 加载不了」先查日志 —— 头号真凶是 `.tres` 里的 `#` 注释

> 2026-10-05 实测（《阿尔法小队》排障）。全文 `REFERENCE.md §44`。

**规则**：Godot 的 `.tres` / `.tscn` 文本解析器**不支持 `#` 注释行**。
写了会让**整份资源加载失败**，而报错是极具误导性的
`Parse Error: Unexpected end of file.`（完全不提示「不认识 `#`」）。

**症状链**：Config 挂 → 卡（Packet）报 `[ext_resource] referenced non-existent resource` →
角色建不出来 ⇒ 玩家说的「MOD 加载不了」。
⇒ 生成器写盘前统一剔除注释行（本项目 `pack_alpha2.py::_deslash()`）；说明写进生成器源码或 `.md`。

**排查顺序（务必先看日志再看代码）**：
| 位置 | 内容 |
|---|---|
| `%APPDATA%\Godot\app_userdata\<游戏>\logs\godot.log` | 本次运行 |
| `…\logs\godot<时间戳>.log` | 历史运行 |
| `…\PVZHE_Logs\godot_startup_<时间戳>.log` | 崩溃导出副本 |

grep：mod id、`ERROR`、`Failed loading resource`、`referenced non-existent resource`。
**再看 `Mods/enabled_mods.json`** —— mod 被摘出这个数组 = UI 里「没启用」= 「加载不了」。

**两条看着像错其实没错的日志**：
- `unsupported package file: Resources/Animations/x.dat` —— 只是诊断；
  能用的 mod（超级汉堡射手等）同样布局。不是失败原因。
- `package applied: … resources=N` —— N = **成功注册的 provides 键数**，不是 `resources` 条数。

**闸门两条新规则**（`gate_alpha2.py`）：
- **G10** `.tres`/`.tscn` 不得含 `#` 注释行；
- **G11** 用到的 `ExtResource("N")` 必须有同文件的 `[ext_resource … id="N"]` 定义。

### 4c.16 ★★★ 「卡注册了但无法选卡」—— 卡（Packet）≠ 卡池（PacketBank）

> 2026-10-05 实测（《阿尔法小队》）。全文 `REFERENCE.md §45`。

**两级结构，缺第二级就选不到卡**：

| 层 | 资源 | 由路径推断的类别 | 作用 |
|---|---|---|---|
| 卡 | `Resources/Cards/X.tres`（`TowerDefensePacketConfig`） | `Packet` | 只**注册**卡 |
| **卡池** | `Resources/PacketBank/<Pool>.tres`（`TowerDefensePacketBankData`） | `PacketBank` | **决定选卡界面/图鉴出不出现** |

编辑器与图鉴都读卡池：`GetPacketBankData(levelConfig.packetBank).category[分类]`。
僵尸关默认池 **`GeneralZombie`**，其 `Zombie` 分类实测 **183 条**。

**引擎侧卡池来自 JSON**：`Asset/Config/PacketBank/PacketBankResource.json`（22 个池），
支持 `Include` 继承（`BuildExpandedPacketBank` → `MergePacketBankCategories`：
后者 `AddRange` 到前者**之后**，照抄要保序）。

**mod 侧唯一途径 = 整份替换卡池**（registry 对 PacketBank 是**赋值**不是追加）：
1. 读 JSON → 按引擎口径展开 `Include`；
2. 往 `Zombie` 分类**追加**卡键（= 卡的 `saveKey`）；
3. 写 `Resources/PacketBank/<Pool>.tres`；
4. **`mod.json` 里 `"overrides": {"PacketBank": ["<Pool>", …]}`** ——
   `AllowOverride` 来自这里（`ModLoader.cs:588-594`），不声明会被 registry 拒绝。

本项目覆盖 `GeneralZombie` / `TotalZombie` / `Total`；**别**往
PresentBox / Elite / Chess / Original / VaseNormal 这些特化池里塞普通僵尸。

**闸门 G12**：`Resources/PacketBank/*.tres` 必须含本卡键，且池名必须在
`overrides.PacketBank` 里声明；一个池都没有 ⇒ FAIL。

★ 通用教训：**资源「注册成功」≠「功能可用」**（`.tres` 解析、卡池归属都是两级），
闸门必须把第二级也验上。

### 4c.17 ★★★ 三件事：挥砍攻击 / 刚性装配 / 图鉴去重（含 mod DLL 契约）

> 2026-10-05 实测（《阿尔法小队》v4.0.0）。全文 `REFERENCE.md §46`。

**① 攻击改挥砍（海豚骑士口径）**：`TowerDefenseZombieConfig.smashAttack` = 挥砍伤害
（`attack` 是啃食）；`AttackComponent.attackType = "Smash"`（**非 Export 字段** ⇒ 只能代码设）；
动画命中帧挂 `hit` 事件（`events` 是逐帧 `Array<Array<Dictionary>>`），代码里
`case "hit": attackComponent.AttackExecute(config.smashAttack)`。

**② ★★★ 照搬成稿后必须「刚性装配」**：件彼此咬死（成稿里常是连体形状），
让各段按骨架各自旋转会反向跑开（实测两腿 12~23 px）⇒ 白洞 + 重影。
修法：所有件**共用同一个整体运动**——
```
R_f = M_躯干,f · M_躯干,0⁻¹ ； M_L,f = R_f·M_L,0 ； O_L,f = O_躯干,f + R_f·(O_L,0 − O_躯干,0)
```
Walk/Idle/Eat/Death 跟随躯干；攻击用**自编整体摆动**（后仰举起 → 前压下砸）。
★ 坑：躯干参照必须取**躯干层自己的逐帧**，写成当前层的会让整体偏移。

**③ 图鉴重复（mod 新增角色必踩）**：`Almanac.InitZombie()` 拼两次且**不去重**——
卡池（选卡必需）+ `XWModContentCatalog.GetPackets(...)`（mod 注册的 Packet）。
`Effective()` 会排除 `entry.OverridesBuiltIn`，而该标记 =「替换了内置键」，
**mod 新增键天然 false、manifest 无字段表达** ⇒ 只能托管代码改：
`foreach (var r in XWModRuntimeRegistry.GetRegistrationStack("Packet", key)) r.OverridesBuiltIn = true;`

**④ ★★ mod 托管 DLL 契约**：`net9.0`，`AssemblyName` = mod id，引用游戏
`PlantsVsZombies.dll` + `GodotSharp.dll`（`Private=false`），产物改名
`Runtime/ModAssembly.dll`；manifest 四字段 `runtimeAssembly / runtimeEntryType /
runtimeApiVersion=1 / runtimeAssemblyPolicy=optional`；
接口 `IXWModRuntimeEntry{Initialize(XWModRuntimeContext); OnAllModsLoaded(); Shutdown();}`。
★ 新增内容放 **`provides`**；放 `overrides` 会报 `overrides target is missing`。

### 4c.18 ★★★ 照搬成稿角色的三条行为修法（v4.1.0）

> 2026-10-05 实测（《阿尔法小队》）。全文 `REFERENCE.md §47`。

**① 去掉啃食伤害（只留挥砍）**：
`TowerDefenseZombie.useAttackDps = false`（public 属性，默认 true）。
`AttackProcessing` 里唯一用 `config.attack` 的就是这条 DPS 路径 ⇒ 关掉即无啃食。
（`smashAttack` 走的是另一条：动画 `hit` 事件 → `AttackExecute(smashAttack)`。）

**② 攻击「身体直立、只挥刀」**：
- 手臂件的裁切框**带着大衣像素**，一抬臂就把那块大衣甩出来（实测头旁出黑团）⇒ 手臂链别动；
- 成稿里看不见的那条臂 ⇒ 直接空着；
- **武器改 FOLLOW 一只可见的手**（手套画在刀柄之上 ⇒ 转起来握把一直被盖住）；
- 挥砍 = 武器绕**自身关节**旋转。
- ★ 枢轴必须用**成稿坐标** `K·J+T`；部件加载函数返回的「件内局部坐标」不是枢轴，用错会飞出去。
- ★ 挥角符号：y-down 屏幕系里 `_rot(deg)` 的 **deg>0 = 顺时针** ——
  刀尖在握把右上方时 **负角 = 举起、正角 = 下刺**（现场试，别猜）。

**③ 「没播走路动画」的真因**：参照层的 Walk 里**躯干只动 1~2 px**（动的是腿），
刚性跟随躯干 ⇒ 整体几乎静止 ⇒ 看起来像没播。
修法：走路用**自编重心摇摆**（绕**脚底中点**）：
`θ = ROCK_DEG·sin(2π·t·CYCLES)`，`t_vec = (SWAY·sin, −BOB·|sin|)`，
整个装配一起摇 + 颠 ⇒ 看得见、且零错位。

### 4c.19 按参考视频对动作（v4.2.0）

用  自带的 ffmpeg（）
把参考录屏抽帧（）→ 拼帧表逐帧看，量出「动作分段 + 节奏 + 幅度」再照着写曲线。
走路要真迈步：rigidify 加 **"legs" 模式**（腿层恢复骨架逐帧，其余钉静止）；
**连体鞋底必须整块归一条腿**，否则双腿分开会在鞋底中间露洞。

## 5. 闸门总览（离线全套，缺一层就可能白跑实机）

| 门 | 命令 | 验什么 |
|---|---|---|
| 生成器自检 | `python build_zombie_<Key>.py --self-check` | 常量/结构/金标/跨语言一致性（`fails = 0`） |
| 负向测试 | `python .cache/_neg_test_head.py` | 逐条篡改常量，断言**必须响**（含注入式用例） |
| 几何门 | `python .cache/check_head_fit.py` | 头对位反解 + 换头落点 + **炮口/生成点**（两个独立来源） |
| 字节核对 | `python .cache/_byte_check_head.py` | 落盘产物**按字节**核对（含工作区 == 安装镜像） |
| 插件入口 | `python .cache/run_entry_sgp.py` | 入口类型 public/非嵌套/有无参构造/实现接口 |
| ModLoader 闸门 | `python .cache/run_gates_sgp.py` | **两份构建**各跑一遍 `check_gates_*.cs`（反射读 DLL + 真产物文本） |
| 幂等 | `python .cache/check_sgp_idempotent.py` | 3 连跑同 sha256 + 只读产物断言 |

**两份构建都要跑**：remake `…\0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64`；
console `D:\zzz\植物大战僵尸**杂交**重制版\data_PlantsVsZombies_windows_x86_64`
（⚠️ 旧笔记里的 `D:\zzz\植物大战僵尸重制版\…` **不存在**）。

**交付文档与产物必须事实一致**：改完代码顺手刷指纹（大小 / sha256 / 条目数 / 场景字节数 / 闸门条数）。

### 5.1 ★★★ 负向测试的六类「假绿」（2026-09-27 先抓 9 条、同日再补 3 条，务必逐条自查）

写下任何断言后，**先问「把实现改坏了这条会不会响」**，再问「有没有可能实现和断言同时被改」：

1. **断言与实现同源**：`if _num(cfg, "physique") != seg["physique"]` —— 而 `seg["physique"]`
   就是写进 cfg 的那个值 ⇒ 常量改成 5（= `CAR`）也 0 条失败。
   ⇒ **断言必须比 `GOLD_*` 字面量**，不能比生成常量。（本仓铁律：`GOLD_` 声明了却没人引用 = 红旗。）
2. **★★ 断言里内联了同一个字面量**（比 `GOLD_` 前缀稀释更隐蔽）：
   `position = Vector2(12, 36)`、`Size = Vector2({seg['w']}, {seg['h']})`、
   `LocalTransform = Transform2D(1, 0, 0, 1, 0, 0)`、`unlockCheckList = []` 这类字面量
   在源码里**各出现两次** —— 一次在**模板**（实现）、一次在**断言**里内联（金标）。
   `str.replace(old, new)` 全量替换会把两边一起改 ⇒ 恒真 ⇒ 假绿。
   ⇒ 锚点必须带**模板专属上下文**（例：`'position = Vector2(12, 36)\n\n[node name="{key}" parent="{base}"'`）。
   （`GOLD_` 前缀 / 行首 `\n` 只能挡住第一类，挡不住这一类。）
3. **判据抓不到被测常量**：`len(SEGS)` 只由上游 json 决定 ⇒ `N_SEG` 常量被改时抓不到；
   段号判据又用 `N_SEG - 1` 跟着漂。
   ⇒ 直接钉常量本身（`if N_SEG != GOLD_N_SEG`），并用 `GOLD_N_SEG - 1` 判段号。
4. **★★ 只钉「属性行」不钉「节点行」**（同日新增，代价最大的一次）：
   自检只断言 `sprite = NodePath("SpriteGroup/TransformPoint/<Key>")` 这一**属性行**，
   **没断言**承载它的 `[node name="<Key>" parent="…"]` **节点声明行** ⇒
   节点挂错层（`parent` 多一级）时自检**全绿**，而实机「图鉴空 + 场上不画」。
   ⇒ 场景这类**结构化文本**必须连**整行声明**一起断言 + 一条负向（禁止复刻该形态）。
   （详见 §4b.7。）
5. **期望值双重换算**（同日新增）：断言里写成 `_scaled(w * GOLD_GAME_SCALE)` —— 而
   `_scaled()` 内部已经乘过一次 `GAME_SCALE` ⇒ 结果 ×S² 。这类错误**自检会当场抓住**
   （实测 11 条 `[受击盒]` 全红），但若只在负向测试里跑就会误判成「断言太严」。
   ⇒ 期望值用**纯格式化 helper**（只补 `.0`，不乘任何系数）+ **独立基线常量**算。
6. **★★ 只断言「抄写目标 vs 金标」，放空「实现产物」**（同日新增，最贵的一条）：
   生成器**算出来的**值（如段间距数组 `LINKS_GAME`）与"产物里**手写**的常量"是**两份东西**。
   只断言「产物里手写的 == 金标期望」会放空前者：实测把整体布局倍率常量改了却 **0 条失败**
   —— 因为抄写目标与金标两边都没动，而生成器算的那个数组漂了、**没有任何断言盯着**（它此前
   只是"给人抄的草稿"）。
   ⇒ **凡是"算出来准备给别人抄"的值，也要有一条对它自己的断言** —— 实现产物必须自我对账。

⚠️ **断言自身也会被负向测试打崩**（同日实证）：
- ★ 循环上界若用**金标常量**、却索引**由被测常量决定的数组** ⇒ 上游一改就 `IndexError`
  **把整个 `self_check` 崩掉**（而不是报 FAIL）。
  ⇒ 先做**长度守卫**（长度不符就 `append` 一条 FAIL），再 `range(min(金标长度, 实际长度))`。
- ★ 新增断言后，老负向用例的 `expects` 可能从"命中 A"变成"命中 B"（更早更准）⇒
  看到"未命中"先确认是不是新旧断言换位，别急着删用例。

⚠️ **环境坑**：测试脚本 `main()` 里既有读全局 `BAD` 又有 `BAD += 1` ⇒ 不写 `global BAD`
会让它变成局部名，末尾 `if BAD:` 抛 `UnboundLocalError` —— 而报错发生在**所有步骤都跑完之后**，
日志看起来全绿，极易误判成「通过」。（另外：`verify_pmod.py` 在 `ModWorkspace/` **根**，不在 `.cache/`。）

---

## 6. references 索引

| 文件 | 内容 |
|---|---|
| **`references/zombie-asset-requirements.md`** | ★★★ **开工先读**：素材问卷（可照抄的问法）、官方规格基准（`tileSize 105×134` / 图集 `3360×1206` / `columns 32` / `trueFrameRate 180.0` / 各插槽 `offset`）、素材来源地图（哪些原版资源可直接复用）、三种素材形态的处理路径、**没有素材时的降级路线**、素材自检四步 |
| `references/zombie-package-and-gates.md` | 包结构逐字段、护具体系、卡库/图鉴、闸门与幂等脚本写法 |
| `references/zombie-fire-and-marker.md` | 发射体系（僵尸侧）、真源链路、**子弹生成点对齐炮口**（两层实现 + 判据写法） |
| `references/zombie-stats-and-cc.md` | **数值/速度/伤害类型**的字段落点（`attackType`、`hitpointsNearDeath` 语义）、手册五行属性块格式、**`.tres` 裸换行陷阱**、**★★★ `_ground` 根运动层（僵尸为什么不走 + 配方 + 移速怎么调 + 闸门）**、**用 buff 让植物停止发射**（`timeScaleInit=0` 为何无效 + 全路径杠杆 + 三条纪律），全部附源码行号 |
| `references/zombie-skin-and-head.md` | 换外观：经典 reanim 直转、`.dat` 二进制规格、换头三节点与头对位反解、**§9 子精灵排序（`insertLayerId`）**、**§10 尺寸类需求的量化流程**、**§11 换「被跟随层」修抬头段头/身接缝（1D+2D 判据）**、**§11b 位姿必须同帧（`process_frame` 早于 `_process` ⇒ 头落后 1 帧，用 `CallDeferred` 覆盖）** |
