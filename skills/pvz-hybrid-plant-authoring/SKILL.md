---
name: pvz-hybrid-plant-authoring
description: 为《植物大战僵尸杂交版》(Godot 4 + C#) 从零制作或改造一个「植物」Mod 的端到端流程——建包、写植物配置与卡片、让卡进选卡界面与图鉴、调发射（射速/弹数/散射/动画事件表）、换外观（经典 reanim 官方素材直转或自制逐帧）、必要时写托管 C# 插件做概率/连射/真随机/修「动画静止」，以及全套离线闸门与实机验收。当用户要求「做一个植物 Mod」「加个新植物」「改某植物的射速/伤害/血量/费用/冷却」「让它进图鉴/能在选卡里选到」「换植物贴图或动画」「植物打不出子弹」「植物动画不动/暂停才跳帧」「植物种不到空地」或提到 TowerDefensePlantConfig / TowerDefensePacketConfig / ComponentSet / FireComponent / FireComponentFireProjectileConfig / CharacterSprite / build_plant_*.py / 植物 .pmod 时使用。
agent_created: true
---

# 制作 PvZ 杂交版「植物」Mod —— 端到端流程

一条植物 Mod 从需求到「装机可玩」的完整走法。**先读第 1、2 节再动手**，能省掉 80% 的返工。

## 0. 权威来源与边界（务必先看）

| 层级 | 位置 | 用途 |
|---|---|---|
| **可执行样板（最重要）** | `<Zombie>/.workbuddy/ModWorkspace/build_plant_super_gatling.py` + `runtime_src_plant/` | **一切从它复制**，别从零写 |
| 细节百科 | 技能 `pvz-hybrid-mod-authoring`（`SKILL.md`，尤以 §「植物类 / 角色类」一节） | 通用包格式、8 条闸门、僵尸/地图/编辑器 |
| 项目内细节 | `<Zombie>/.workbuddy/memory/REFERENCE.md` | 本项目踩过的全部坑原文 |
| 交付文档 | `<Zombie>/.workbuddy/ModWorkspace/植物Mod-超级机枪射手.md`、`…-换贴图换动画指南.md` | 讲给用户看的 |
| 引擎源码真相 | `D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28\` | `addons/ModEditor/ModSystem/`、`Script/Component/` |

> 本技能是**植物专用精简流程**。凡与 `pvz-hybrid-mod-authoring` 冲突，**以那份 + 源码为准**（它更新更勤）。
> 本技能负责「按什么顺序做、每步的硬约束、哪一步最容易白忙」。

**已知边界**：游戏内置的「PVZ Mod 编辑器」是游戏内 GUI（F3 唤起），**AI 无法驱动它**。但它的产物
`.pmod` = zip + 根 `mod.json`，**可以纯脚本生成** —— 这就是整套工具链的基础。

## 1. 先做三个决定（决定后面 80% 的工作量）

### 决定 A：复用内置植物 还是 全新植物？

| | 复用内置（推荐） | 全新 |
|---|---|---|
| 做法 | 角色场景 `[node instance=ExtResource("res://Asset/Anime/Character/Plant/…")]` 实例化原版场景 | 自己搭场景树 |
| 好处 | 命中盒、组件、动画骨架全部继承，改动面小 | 完全自由 |
| 代价 | 要摸清继承链（`ComponentSet` 走 `ParentSet` 差量） | 极易漏组件 ⇒ 打不出弹、种不下去 |

> **除非用户明确要「全新的美术 + 全新机制」，否则一律走复用 + 差量覆盖。**

### 决定 B：需要写托管 C# 插件吗？

**纯数据做不到的四类**（照下面判，别试错）：

| 需求 | 为什么纯数据不行 | 出路 |
|---|---|---|
| 概率触发（如 10% 大招） | `FireComponentFireProjectileConfig` 无 probability 字段 | 插件 |
| 延时/持续改发射模式（5 秒内连发 300 颗） | `FireComponentDefinition` 无字段，状态机只有 `idle/attack/restore` | 插件 |
| 真随机（非确定性） | 唯一随机源 `OnFireVolley(ulong randomSeed)` 的种子是**确定性**的（联机同步刻意禁真随机） | 插件 |
| 「逐颗」发射（每颗单独角度/节奏） | 数据侧一次 `Fire()` 会**遍历全部 config** ⇒ 拆不开 | 插件 |
| 换自定义战斗背景、投掷单位替换、自定义皮肤动画静止 | 见 `references/plant-runtime-plugin.md` | 插件 |

**其余全部走纯数据**（射速、弹数、扇形散射、伤害、血量、费用、冷却、卡类型、能不能直接种、
进选卡/图鉴）—— 别为了「稳」就上插件。

### 决定 C：外观走哪条路？

| 路线 | 何时用 | 去哪 |
|---|---|---|
| **A. 经典未重置版 reanim → 官方素材直转（首选）** | 解包里有该角色的 `*.reanim.compiled` + `reanim/*.png` | `references/plant-skin.md` |
| B. 自制逐帧 / 单帧静止图 | 拿不到 reanim，或只要一张图 | `references/plant-skin.md` 后半 |
| C. 复用原版贴图 | 只改数值、不改画 | 场景里 `instance` 原版 `.tscn`，**不复制素材** |

⚠️ 三条路**缩放口径不同**（自制素材常「放大 2 倍画」⇒ `DISPLAY_SCALE=0.5`；官方素材 `sx/sy` 即最终缩放），**绝不可混用**。

## 2. 关键路径（按需查证）

| 用途 | 路径 |
|---|---|
| 工作区（生成器/插件源码/闸门/文档） | `…<Zombie>/.workbuddy/ModWorkspace/` |
| 装机目录（游戏真正读的） | `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\` |
| 引擎日志（**不开游戏也能验收**） | 同目录 `logs\godot.log`、`PVZHE_Logs\godot_startup_*.log` |
| Mod 解包缓存 | 同目录 `ModsCache\<modid>\` |
| 源码真相 | `D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28\addons\ModEditor\ModSystem\` |
| 经典未重置版素材（reanim 来源） | `D:\zzz\extract_1789988101` |
| 中文名对照（查内置植物中文名必用） | `Asset/Translate/Translate.csv` |

> ⚠️ 本机有**两份游戏构建**（remake / console）⇒ 闸门**两边各跑一遍**。

## 3. 标准流程（12 步）

### Step 0 — 把需求问全（缺一项后面就得返工）

1. **改哪个植物**：复用哪个内置角色（中文名/英文 key）还是全新？
2. **数值**：阳光费用、冷却、卡类型（白/金/钻石…）、血量、种植涨价；
3. **能不能直接种在空地**（默认覆盖类植物**不能**，见 Step 8）；
4. **要不要进选卡界面 / 图鉴**（要 ⇒ Step 7，且必须告知副作用）；
5. **要不要换外观**（路线 A/B/C）；
6. **玩法是否纯数据做不到**（决定 B）—— 若需要，**动手前先把取值跟用户确认**（概率、时长、颗数、角度）。

### Step 1 — 复制生成器（不要从零写）

```bash
cp .workbuddy/ModWorkspace/build_plant_super_gatling.py .workbuddy/ModWorkspace/build_plant_<新名>.py
cp -r .workbuddy/ModWorkspace/runtime_src_plant .workbuddy/ModWorkspace/runtime_src_<新名>   # 只有需要插件时
```

生成器的结构（照着替换，不要重构）：

| 区段 | 行数（样板） | 内容 |
|---|---|---|
| 常量头 | ~163–395 | `BUILD_DIR / MOD_NAME / MOD_ID / CHAR_KEY`、`.tres` 基底路径、数值常量、标定值 |
| 工具函数 | ~478–630 | `write_bytes(_if_changed)` / `fmt_f` / `godot_json` / `sweep_stale_files` / `sync_tree` |
| **内容生成器** | ~635–1017 | `plant_config_tres` / `component_set_tres` / `plant_scene_tscn` / `sprite_scene_tscn` / `packet_tres` / `build_manifest` / `translation_file` |
| 安装与打包 | ~1025–1200 | `install_project_dir` / `merge_enabled_mods` / `package_pmod` |
| **自检** | ~1206–1568 | `self_check()` —— 必须同步改，否则报假红/假绿 |

⚠️ **改了一处生成逻辑，必须同时改 `self_check()`**；只改生成器不改自检 = 下次重跑静默回退。

### Step 2 — 改顶部常量

必须一起改的 6 个（**全部指向同一个字符串**最稳）：

```python
BUILD_DIR  = "SuperGatlingPea"   # 工作区构建目录（ASCII）
MOD_NAME   = "超级机枪射手"        # 工程目录名 / .pvzmodeproject / .pmod 文件名
MOD_ID     = "supergatlingpea"   # manifest.id
CHAR_KEY   = "SuperGatlingPea"   # ★ 角色 key = 目录名 = 场景文件名 = config.name = saveKey = 卡片文件名
```

> ★ **`CHAR_KEY` 是整条链的主键**：`Resources/Characters/Plants/<CHAR_KEY>/Scene/<CHAR_KEY>.tscn`、
> `…/Sprite/<CHAR_KEY>.tscn`、`Config/TowerDefensePlant<CHAR_KEY>.tres`、`Resources/Cards/<CHAR_KEY>.tres`
> **四处同名**，且必须等于 `characterConfig.name` 与 `packet.saveKey`。不一致 ⇒ 整包被拒（见 `references/plant-package-and-gates.md` 闸门 7）。

数值常量（样板名 → 落点）：

| 常量 | 落到 |
|---|---|
| `FIRE_INTERVAL` | `ComponentSet` 的 `fireInterval`（秒） |
| `PEA_COUNT` / `dirs` / `PEA_SPEED` / `PROJECTILE_NAME` | `fireProjectileList` 每条 config；**插件逐颗发射时收敛成 1 条 `dir=0`** |
| `COST` / `COST_RISE` / `PACKET_COOLDOWN` | `TowerDefenseCharacterConfig`（**植物 Config**，不是卡片） |
| `PACKET_TYPE` | **卡片** `TowerDefensePacketConfig.type` |
| `HITPOINTS` | `TowerDefenseCharacterConfig.hitpoints` |
| `COVER_CAN_DIRECT_PLANT` | 卡片内联的 packet override 子资源 |

### Step 3 — 包内六个文件（缺一个就加载失败）

| 文件 | 作用 | 注册？ |
|---|---|---|
| `Resources/Characters/Plants/<Key>/Scene/<Key>.tscn` | 主场景（**唯一 Character 键源**） | ✅ 注册为 Character |
| `…/Scene/<Key>ComponentSet.tres` | 组件集（射速/弹数/散射都在这） | ❌ 角色包依赖 |
| `…/Sprite/<Key>.tscn` | **精灵场景（唯一 CharacterSprite 键源，必须有）** | ✅ 注册为 CharacterSprite |
| `…/Config/TowerDefensePlant<Key>.tres` | 植物配置（费用/冷却/血量） | ❌ |
| `…/Packet/<Key>.tres` | 包内卡片镜像 | ❌ |
| `Resources/Cards/<Key>.tres` | **卡池条目**，注册键 = **文件名** | ✅ 注册为 Packet |

```json
"provides": { "Character": ["<Key>"], "CharacterSprite": ["<Key>"], "Packet": ["<Key>"] }
```

细节与 8 条硬闸门 → `references/plant-package-and-gates.md`。

### Step 4 — ★★ 角色场景必须显式声明 `ComponentSet`（否则一颗弹都打不出、且零日志）

```ini
[node name="<Key>" node_paths=PackedStringArray("…") instance=ExtResource("1")]
ComponentSet = ExtResource("15")     # ★ 必须在 script 之前，且必须是包内相对路径
script = ExtResource("2")
```

- 漏了这行 ⇒ 基场景那份组件集生效 ⇒ **没有 FireComponent ⇒ 子弹打不出来**，
  且加载期**完全静默**（不拒包、不告警、不进 diagnostics）。
- `ModLoader.InferRuntimeEntry()` **不检查 `.tscn` 内容** ⇒ 必须自己加断言。
- 插件侧**不要**在 `IsUsable(fire)` 为假时静默 `return` —— 打一次性日志并点名「场景可能漏了 ComponentSet」。

### Step 5 — 发射：先定「数据驱动」还是「插件驱动」

| 想要的 | 写法 |
|---|---|
| N 颗同方向叠发 | `fireNum = N` + `fireNumAtOnce = false` |
| **一次齐射 N 条不同方向**（扇形） | `fireNum = 1` + `fireNumAtOnce = true` + **N 条 config** |
| **插件逐颗驱动**（概率/真随机/每颗改向） | **只留 1 条 config（`dir = 0`）** + `fireNum = 1`，**不要 `fireNumAtOnce`** |

⚠️ 最后一行是硬约束：`FireComponent.Fire()` **一次调用会遍历全部 `fireProjectileList`**
⇒ 插件逐颗调 N 次时，若还留着 N 条 config，会变成 **N² 颗重叠**。

⚠️⚠️ **「攻击时只有动画、没有子弹」的唯一真因 = 动画 `events` 表里没有 `fire` 条目。**
普通射击 **100% 是动画事件驱动**的；只写 `fireAnimeClips="HeadFire"` 让动画播起来**不够**，
必须让动画在某帧发出 `fire` 命令，且 `.dat` / `.tres` 的 `events` 表都要有。
链路图、发射帧推导（内置 143 植物扫描的 A/B 实证）、`.dat` 事件段字节布局
→ `references/plant-fire-pipeline.md`。

### Step 6 — 外观

- 三件套 = 精灵场景 `.tscn` + 动画数据 `.tres`(`AdobeAnimateData`) + **`.dat` 二进制图集**（图片塞在 `.dat` 里，不是散装 PNG）。
- 官方素材直转走 `.cache/build_official_skin.py`（reanim → `.dat`/`.tres`/图集/`skin_params.json`，带 on-disk 断言）。
- 头位/炮口标定、双图层父子精灵（头独立）范式、自制 `.dat` 的 5 个必踩坑
  → `references/plant-skin.md`。

### Step 7 — 让卡「能被选到」+ 进图鉴（**只有需要时才做**）

因果链：

| 玩家看到的 | 数据来自 | 位置 |
|---|---|---|
| 选卡界面 | `GetPacketBankData(config.packetBankType).category[分类]` | `TowerDefenseBattleFeaturePacketBank.cs` |
| 图鉴植物页 | `WithPlants(GetPacketBankData("GeneralPlant"))` —— **同一个库的深拷贝** | `Almanac.cs` |

⇒ 根上的修法：往共享卡库 `TOWERDEFENSE_PACKETBANKS["GeneralPlant"].category["Gold"]`
**追加卡 key**（check-then-add，幂等）。一次改动同时喂到选卡和图鉴 ⇒ 两边天然一致。
还要补 `Include` 闭包里的派生库（`BuildExpandedPacketBank` 递归合并，实测只有 `Total`）。

⚠️ **副作用必须如实告知用户**：进了 `Gold` 就等于成为一张正常金卡，按卡库随机取卡的逻辑
（金卡碎片掉落、地雷、金豆等）和走 `GetPlantList()` 的（植物礼盒 / LuckyBlover）都可能给出它。
**用户只想要「图鉴能看到」就别做这一步。**
细节（哪些分类键被认、`ModPlants` 单列一类、懒初始化禁忌）→ `references/plant-data-fields.md`。

### Step 8 — 血量 / 直接种空地 / 费用

| 想改 | 字段 | 位置 |
|---|---|---|
| 血量 | `hitpoints` | 植物 **Config**（类默认 300） |
| 阳光花费 / 涨价 / 冷却 | `cost` / `costRise` / `packetCooldown` | 植物 **Config** |
| 卡类型（金卡…） | `type` | **卡片** |
| **能不能直接种在空地** | 卡片内联 packet override 的 **`coverCanDirectPlant = true`** | **卡片** |

⚠️ «直接种空地» 这条有三个陷阱，**照抄现成写法**（否则一定失败）：

1. `plantCover` **非空** ⇒ 这张卡**只能种在名单里的底座植物上**，空地种不上；
2. `GetCoverCanDirectPlant()` **只在 packet 有 `_override` 时才读**，否则**硬编码 `return false`**
   ⇒ 改 `plantCover` / 改 `characterConfig` 都**做不到**，**必须挂 packet override**；
3. `.tres` 里的属性名 = C# 字段名**去掉前导下划线**（`_override` → `override`）。

override 里**只写 `coverCanDirectPlant` 一个字段**（其余默认值全是「不覆盖」语义，多写会误伤）。
完整可抄片段 + 官方先例 → `references/plant-data-fields.md`。

### Step 9 — 需要插件时（决定 B）

四条硬约束（写错 = **整包被拒/回滚**）：

1. `runtimeAssembly` **必须恰好是字面量** `"Runtime/ModAssembly.dll"`；
2. `runtimeApiVersion` **必须恰好 `1`**；入口三个回调**一律 try/catch 绝不抛**（抛 = 无条件整包回滚）；
3. `provides`/`overrides` 非空时，包内**每个**被识别的文件都必须在里面声明；
4. `Runtime/` 目录**只许有一个** `ModAssembly.dll`（`.dll/.exe/.bat/.cmd/.ps1/.cs/.gd` 都算可执行文件，多一个就拒收）。

配方（已实测）：概率大招、逐颗连射、真随机、**掐掉原版开火链**、**修「动画静止」**、
**与僵尸版「共用判定逻辑」（共享源文件 + 两问守卫）**
→ `references/plant-runtime-plugin.md`（§7 讲共用源文件的坑）。

### Step 10 — 写/跑闸门（**这一步不能省**）

生成器自带 `self_check()` **不够** —— 它比的是刚生成的内存文本（**假绿重灾区**）。
必须配 on-disk 断言 + 负向测试 + 离线复刻的 ModLoader 闸门。

清单与跑法 → `references/plant-verification.md`。

### Step 11 — 装机

生成器会把 `.pmod` 落到 `Mods\`，并把**工程目录**镜像到 `Mods\<MOD_NAME>\`，
再合并 `enabled_mods.json`（**缺这个文件 ⇒ 零 Mod 加载**）。
⚠️ 游戏只扫 `Mods/*.pmod` **不递归**。

### Step 12 — 实机验收（不开游戏也能先验一半）

先读 `logs\godot.log` 搜 `[ModLoader]`：

```
[ModLoader] package extracted safely: <modid> (N files)
[ModLoader] package applied: <modid>; resources=3; runtimeEntry=False; callbacks=0; diagnostics=1
[ModManager] enabled runtime apply complete: 3/3 packages; rollbackBlocked=False
```

- `resources=3` = 只注册了 `Scene`/`Sprite`/`Cards` 三条，**正常**（`Config`/`Packet`/`ComponentSet` 算依赖不注册）。
- `diagnostics=1` 通常是 `translations.csv` 被判 unsupported，**不致命**。
- `rollbackBlocked=False` = 没有任何一包被回滚。
- 反例关键词：`is not unambiguously declared by manifest` / `saveKey 与注册键不一致` /
  `缺少 CharacterSprite` / `undeclared executable package file` ⇒ 按 8 条闸门对号入座。

**必须逐项确认的观感项**（静态闸门保证不了）：贴图/动画是否动、头身接缝、炮口位置、
子弹出膛点、命中判定、图鉴与选卡里显示是否正常、费用/冷却读出来对不对。

## 4. 坑 Top 15（每条都能白忙半天）

1. **漏 `ComponentSet` 声明** ⇒ 打不出弹、零日志。见 Step 4。
2. **`.dat` 的 `events` 表没有 `fire` 条目** ⇒ 只有动画没有子弹，加载期零报错。见 Step 5。
3. **插件逐颗发射却没把 config 收敛成 1 条** ⇒ N² 颗重叠。见 Step 5。
4. **`CHAR_KEY` 四处不一致** ⇒ `saveKey 与注册键不一致` ⇒ 整包被拒。
5. **包内自引用写成 `res://`**（或反之）⇒ 配置加载失败 ⇒ 角色被拒。**自引用必须相对**（`./X.tres`、`../Config/X.tres`），
   指向游戏自带资源才用 `res://`。
6. **`resources` 列表没按规范序**（全部非忽略文件 `OrdinalIgnoreCase` 升序）⇒ 编辑器一打开工程就重写 `mod.json`。
7. **`Runtime/` 里多放了一个文件**（含 `.pdb`）⇒ `undeclared executable package file` ⇒ 整包拒收。
8. **`.cs` 被打进包** ⇒ `IsExecutablePackageFile` 认它 ⇒ 整包拒收（打包时要排除）。
9. **只改生成器不改 `self_check()`** ⇒ 下次重跑静默回退。
10. **自检「假绿」**：`self_check()` 比内存文本；切片断言写错会变成「永远为真」。
    ⇒ 必配 **on-disk 断言 + 负向对照**。
11. ~~**改了 `Head.offset` 想调头位** ⇒ 作为 Head 子节点的 `Marker2D`（炮口）跟着跑偏。~~
    ~~⇒ **只改 `Head.position`、绝不动 `offset`**。~~
    ⇒ **2026-09-22 更正：上面这条反了。** `AdobeAnimateSprite.UpdateChild()`（`:5259-5281`，`usePos`/`useRotate`
    默认 `true`，`:276`/`:279`）**每帧重写**子精灵的 `Position`/`Rotation`
    （`Position = 被跟随图层 pose.Origin + 父精灵 offset`）⇒ 场景里的 `Head.position` 是**死值**；
    而 `offset` 只作用于本精灵自己的美术（`:7044`/`:7071`/`:7362` `transform.Translated(offset)`），
    **不影响** `Marker2D`。⇒ **要调头位就改 `Head.offset`**；跨体格拼装（僵尸身+植物头）必须**重标定**，
    用 `.cache/check_head_fit.py` 反解（带负向测试），别照抄别处的值。
12. **自定义皮肤动画「完全静止、按 ESC 暂停一次跳一帧」**：
    自定义 `.dat` 不在全局图集清单 ⇒ `GpuPoseTextureRid` 无效 ⇒ 姿态定格。
    ⇒ 插件设 `forceLocalRender = true` + `forceCpuPoseRender = true`（见 `references/plant-runtime-plugin.md`）。
    ⚠️ **但前提是「这个精灵不被父精灵代画」** —— 见坑 14；子精灵设了**也无效**。
13. **「源码里必须含某个字面量」的断言是重构陷阱**：一旦把值搬到共享源/常量表/配置，
    这类断言**必然假红**（本项目实测：抽出共享判定核心后，生成器 + 校验脚本一次红 7 条，
    生成器直接**拒绝写盘 exit 3**）。⇒ 顺手升级成「转发在不在 + 唯一真源在不在 + 值对不对」两问，
    **绝不删断言、绝不跳过校验**（见 `references/plant-runtime-plugin.md` §7）。
14. ★★★ **子精灵必被父代画 ⇒ 跨 `.tres` 的子精灵会变成「一团别的角色的图集碎片」**。
    根因：`CollectOwnedChildBindings`（`AdobeAnimateSprite.cs:5365`，判定 `:5385`）**只按 Godot 节点类型**
    收集子精灵，**完全不看 `parentSprite`** ⇒ 「精灵的直接子精灵」必被收 ⇒
    `IsRenderedByParentSpriteForRender`（`:9559`）true ⇒ `_Draw()`（`:9534`）**首行 return**
    ⇒ 子精灵自己的 `forceLocalRender` / `forceCpuPoseRender` **永远读不到**；它的切片改由**父精灵的渲染批次**
    代画（`AppendChildSprites:833`）⇒ 采样**父精灵那一张图集**（`ResolveMediaRect:921` 落 `BaseAtlasPage = 0`
    ⇒ `AdobeAnimateVisualTextureArray.png`，全部角色拼一张）。
    ⇒ **本植物包侥幸没事的唯一原因**：`root` 与 `Head` **共用同一份 `.tres`** ⇒ 同 definition ⇒
    同 `MediaAtlasPages`。**只要你把子精灵换成另一份 `.tres`（换头！）或自制皮肤，就立刻中招。**
    * ⚠️ 两个「看起来能躲」但躲不掉的写法：① `insertLayerId = -1` **不等于**不插入
      （`ResolveSpriteChildInsertLayer:8039` 回落顶层）；② 挂到普通 `Node2D` 容器下**也躲不掉**
      （`CollectOwnedChildBindings:5397` 只在中间节点有 `ownerSlot` 时截断，
      而 `ResolveSpriteChildFollowLayer` **优先读子精灵自己的** `followParentSpriteLayerId`）。
    * ✅ **唯一有效修法 = 三节点**：`<Root>` 下留 `HeadShadow`（**身体的直接子精灵**，
      `visible=false` + **全层 false** ⇒ 零切片，唯一作用是吃 `UpdateChild()` 每帧写的
      `Position = 被跟随层 pose.Origin + 父 offset` / `Rotation = pose.Rotation + child.offsetRotate`；
      **该循环没有可见性判断** ⇒ `visible=false` 不拦截定位） + `HeadHolder`（普通 `Node2D`，identity）
      + `HeadHolder/Head`（**独立渲染**的子精灵，全层 true，**不写** `parentSprite`/`insertLayerId`/
      `followParentSpriteLayerId`/`position`/`rotation`/`visible`）。两者 `scale`/`offset`/`offsetRotate` 逐字相同。
      可见头挂普通容器下**仍**能被引擎定位（`ResolveSpriteChildFollowLayer` 用 `_parentSprite`
      = `FindParentSpriteAncestor():7797`，最近**祖先精灵**）⇒ 位姿由插件每帧从影子同步。
    * 官方先例：引擎自带 `Test/AdobeAnimateDetachedChildOwnershipProbe.cs`。
15. ⚠️ **`.tscn` 节点头收尾必须是 `]`**；写成 `>` ⇒ **Godot 静默吞行**（不报错不警告，
    节点根本没建出来，零日志）。本项目实测：三节点明明写对了，可实机还是不对，
    就因为这个字符；而**生成器自检当时放行了**，因为断言写成
    `f'[node name="Head" type="Node2D" parent="HeadHolder"'`（**没带闭合括号**）
    ⇒ **断言与实现同错 = 假绿**。
    ⇒ 修法：① 模板改 `]`；② 自检加**通用扫描**（任何 `[node ` 行不以 `]` 收尾即报错）。
    ⇒ ⚠️ 附带一条取证纪律：**结构类结论一律以字节级读取为准**
    （`Read` 预览曾把这一行的 `>` **显示成** `]`，差点骗过我）。
    这类「断言写成不带闭合符的前缀匹配」的假绿，与坑 13 同源，凡新增结构断言都要自问一句
    **「它能不能拦住一个语法坏掉但前缀正确的产物」**。

## 5. 闸门总览

| 闸门 | 位置 | 作用 |
|---|---|---|
| `self_check()` | 生成器内 | 内容断言（**配 on-disk 断言才可信**） |
| `check_plant_<名>.py` | `.cache/` | 包内容 + 源码证据双层断言 |
| `run_gates_plant.py` | `.cache/` | 反射直调 **ModLoader / 校验器真函数**，**两份构建各跑一遍** |
| `check_modloader_gates.py` | `.cache/` | 离线复刻 8 条角色包硬闸门 |
| `check_project_folder.py` | `.cache/` | 工程目录形态（编辑器视角） |
| `check_sgp_idem_single.py` | `.cache/` | 幂等（3 连跑字节稳定 + 增量清理 + 镜像一致） |
| `verify_official_skin.py` | `../.cache/` | 官方素材直转的四层独立交叉 + `--negative` 负向测试 |

## 6. references 索引

| 文件 | 什么时候读 |
|---|---|
| `references/plant-package-and-gates.md` | 建包 / 改路径 / 报「加载失败」时 |
| `references/plant-data-fields.md` | 改数值字段 / 卡入库 / 直接种空地 / 血量 |
| `references/plant-fire-pipeline.md` | 发射不管是打不出弹、射速不对、扇形不对 |
| `references/plant-skin.md` | 换外观（官方素材 / 自制 / 复用原版） |
| `references/plant-runtime-plugin.md` | 决定 B 命中（概率/连射/真随机/抑制原版/动画静止/**与僵尸版共用判定核心**） |
| `references/plant-verification.md` | Step 10 写闸门、结果可疑、实机前 |
| `references/plant-pmod-hotpatch.md` | **只有 .pmod 没有生成器**，直接热补丁数值属性（cost/射速/血量…）时 |
| `assets/新建植物清单.md` | **Step 0 一开始就打开**，逐项打勾 |
