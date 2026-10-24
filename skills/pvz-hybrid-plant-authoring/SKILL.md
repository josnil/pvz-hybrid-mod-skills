---
name: pvz-hybrid-plant-authoring
description: 为《植物大战僵尸杂交版》(Godot 4 + C#) 从零制作或改造一个「植物」Mod 的端到端流程——建包、写植物配置与卡片、让卡进选卡界面与图鉴、调发射（射速/弹数/散射/动画事件表）、换外观（经典 reanim 官方素材直转或自制逐帧）、必要时写托管 C# 插件做概率/连射/真随机/修「动画静止」，以及全套离线闸门与实机验收。当用户要求「做一个植物 Mod」「加个新植物」「改某植物的射速/伤害/血量/费用/冷却」「让它进图鉴/能在选卡里选到」「换植物贴图或动画」「植物打不出子弹」「植物动画不动/暂停才跳帧」「植物种不到空地」或提到 TowerDefensePlantConfig / TowerDefensePacketConfig / ComponentSet / FireComponent / FireComponentFireProjectileConfig / CharacterSprite / build_plant_*.py / **csproj `<AssemblyName>` / 程序集名唯一 / 安卓加载失败 / runtimeAssembly 能不能改** / 植物 .pmod 时使用。
agent_created: true
---

# 制作 PvZ 杂交版「植物」Mod —— 端到端流程

> ## 🏛 官方模板基线（最高优先级 · 2026-10-24 对齐）
>
> 本技能的**流程 / 字段契约 / 身份 / 版本 / 构建 / 安装 / 验证 / 目录**一律以
> [pvzhe-mod-template](https://github.com/axh-xecoy/pvzhe-mod-template) 为准（植物侧入口 `pvzhe-plant-create`，
> 按需组合 `pvzhe-character-fire` / `character-armor` / `character-skin` / `pvzhe-resource-edit`）。
> **重复或冲突一律以模板为准**；本技能只保留模板未覆盖的**实测细节**。
> 全文与冲突表：[`../pvz-hybrid-mod-authoring/references/official-template-baseline.md`](../pvz-hybrid-mod-authoring/references/official-template-baseline.md)
>
> 速记：`schemaVersion: 3` ｜ `version` 用 **SemVer 三段** ｜ `id` 为 `[0-9a-z_.-]` 1–32 位 ｜
> 构建走 `tools/mod.py prepare/build/check/install/verify` ｜ 判据来自**已发布发行版**（无需源码）｜
> 包内禁止宿主 DLL / 整份 `bin/`。

一条植物 Mod 从需求到「装机可玩」的完整走法。**先读第 1、2 节再动手**，能省掉 80% 的返工。

## ★ 踩坑总表（植物专场） —— `references/plant-pitfalls.md`

本项目开发过程中**实际踩过**的坑，已统一成「**现象 · 触发场景 · 原因 · 正确做法**」四段式。
**开工前先扫一遍；出问题时先 Ctrl-F 现象里的一句话**（如「零日志」「假绿」「整包被拒」「原地滑步」）。

## 0. 权威来源与边界（务必先看）

| 层级 | 位置 | 用途 |
|---|---|---|
| **① 上游模板（权威）** | 模板 `.agents/skills/pvzhe-plant-create/`，按需组合 `pvzhe-character-fire` / `pvzhe-character-armor` / `pvzhe-character-skin` / `pvzhe-resource-edit` / `pvzhe-projectile-create` | 制作入口、字段契约、构建与验收纪律 |
| **② 本仓库通用技能** | `pvz-hybrid-mod-authoring`（`SKILL.md` + `references/official-template-baseline.md`） | 包格式、清单契约、版本与身份规范、闸门 |
| **③ 本技能（植物细节）** | 本文 + `references/*` | 执行顺序、硬约束、实测数值与踩坑现象 |
| ④ 本机历史工坊 | `<本机 ModWorkspace>/build_plant_*.py` + `runtime_src_plant/` | **仅作历史参考**，不再要求他人复制 |
| ⑤ 本机历史记忆 | `<本机 .workbuddy>/memory/REFERENCE.md` | 本项目踩过的坑原文（**不外发**） |
| ⑥ 源码（可选内部查证） | 本机解包树 `addons/ModEditor/ModSystem/`、`Script/Component/` | 只用于解释机制；**不作为他人前置条件** |

> 本技能是**植物专用精简流程**：负责「按什么顺序做、每步的硬约束、哪一步最容易白忙」。
> 契约与纪律不在此重复；冲突时按 **① 模板 > ② 本仓库通用 > ③ 本文** 的顺序取舍。
> （旧文「以 `pvz-hybrid-mod-authoring` + 源码为准」**作废** —— 源码不再有最高效力。）

**已知边界（模板口径）**：上游模板**不使用**游戏内「PVZ Mod 编辑器」（F3），也**不需要游戏源码**；
`.pmod` = ZIP（`mod.json` + `Runtime/ModAssembly.dll` + `resources` 里显式列出的自有资源），
**不是** Godot PCK，**不要** `--export-pack`。

> **⛔ 解包双通道（别用一条否定另一条）**
> - **工程级还原**（要 `.cs` / `.tscn` / 可编辑工程树）→ **只能用** [GDRE Tools（gdsdecomp）](https://github.com/GDRETools/gdsdecomp/releases)（[下载说明](../../UNPACKING.md)）；禁止其他解包器或自制解析脚本。自检：树里同时有 `Asset/`、`Prefab/`、`addons/ModEditor/ModSystem/`，且能搜到 `Asset/Config/Projectile/ProjectileResource.json`。
> - **发行版按需取资源**（模板玩家路径，不需要源码）→ `python tools/mod.py prepare`（生成 `.work/pck-index.json`）+ `python tools/mod.py extract --pck … --path/--prefix …`。这是模板官方工具链，**不属于**「其他解包器」，见基线文档 §8。

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
| **A′. 内置 `.tres` 切片数据 + 经典版原画重建**（官方画质 + 真动画的**第二条**路） | reanim 解不出来（或角色只在重置版 `.tres` 里有动画），但 `reanim/` 里有同名原画 | **`references/tres-slice-reskin.md`** |
| B. 自制逐帧 / 单帧静止图 | 拿不到 reanim，或只要一张图 | `references/plant-skin.md` 后半 |
| **B′. 从「一张游戏内截图」起步**（有纹理底 + 相框、要分层 + 程序化动画） | 用户只给一张全身图，角色游戏里不存在 | **`references/selfmade-skin-from-screenshot.md`** |
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

**★ 「卡面 / 立绘」从哪来 + 先检查解包完整性（2026-09-28 实测，做识别/外观类 Mod 必看）**

* 一个角色在 `Asset/Config/Character/CharacterResource.json` 里就是**三键 uid 引用**：
  `{ "Packet": {"<卡key>": uid}, "Scene": uid, "Sprite": uid }`（V0.29 实测 583 条全是这个形状）
  * `Packet` → `.../Packet/<卡key>.tres`（`TowerDefensePacketConfig`：`saveKey` / `cost` /
    `packetAnimeOffset` / `packetAnimeScale` / `unlockCheckList` / `characterConfig`）；
  * `Scene` → `.../Scene/TowerDefensePlant<Key>.tscn`（战斗中的植物）；
  * **`Sprite` → 同级 `.../<Key>.tscn`** ← **这就是「卡面/立绘预览」**
    （`AdobeAnimateSpriteBase` + `flashAnimeData` + `Animation/Clip = "Idle"`）。
* ⇒ **卡槽里显示的不是现成 PNG，而是同一套植物精灵按 `packetAnimeOffset/Scale` 摆放**。
  因此「换卡面」动的是**同一份资源，会同时影响卡槽与场上单位**——做外观类 Mod 必须先拍板这点。
* ★★ **「离线取立绘」的终局答案（2026-09-28 实测 484 MB 官方 pck，三轮查证；先前两条中间结论已作废）**：
  **发行版里根本没有 `.dat`，图片被合进了 GPU 纹理数组。**
  1. `.dat` 是**编辑器期**资源：`[Export(PropertyHint.File,"*.dat")]` +
     `Godot.FileAccess.Open(path, Read)`（`AdobeAnimateData.cs:447` / `:1035` / `:1293`）
     ⇒ 它就是个普通二进制文件，但**发行 pck 里没有它**。
     实测 `gdre_tools --headless --list-files=<pck>` ⇒ 26522 个 `res://` 条目，
     全库含 `.dat` 的只有 `icudt_godot.dat`（ICU 数据）⇒ **330 个植物的 `.dat` 一个都没打包**。
     （所以"解包树里找不到 `.dat`"**不是解包出错**：解包日志显示 full recover `Extracted 26522 files, no errors detected!`）
  2. **`.tres` / `.res` 里也没有图**：`Asset/.../<Key>.tres` 的 `rasterCompositeData`
     在 330 个植物上**全部为 `null`**；`.godot/exported/adobe_animate/**/*.res`（624 个）用
     `gdre_tools --bin-to-txt` 转文本后与同名 `.tres` **逐字符相同**（同为 63901 字符）⇒ 只是同资源的二进制形态。
     `animeFile` 仍写着 `res://.../<Key>.dat`，**只是残留路径字符串**（读不到会回退）。
  3. **★ 真图集在 `.godot/imported/` 的 4 个纹理数组里**：
     `AdobeAnimateBootstrapPoseTextureArray.exr-*.ctexarray` /
     `AdobeAnimateVisualTextureArray.png-*.s3tc.ctexarray` /
     `AdobeAnimateGpuPoseTextureArray.exr-*.ctexarray` /
     `AdobeAnimateBootstrapVisualTextureArray.png-*.s3tc.ctexarray`
     ⇒ 所有 Adobe Animate 动画的视觉纹理**合并进了 Texture2DArray**，`Pose` 那个是姿态数据。
     （与运行时的 `AdobeAnimateDefinitionCache.GetBakedGpuPoseTexturePath`、
     `AdobeAnimateGlobalAtlasCache` 正好对上。）
     反向验证：`.godot/imported/` 里 3799 个 `.ctex` 中，含植物名的**只有 `Award*Custom0.png` 皮肤图**
     （`Peashooter` 1 条、`Cactus` 6 条，全是 Award 皮肤）⇒ **植物主体图不在 `.ctex` 里**。
  ⇒ **结论与选路**：
  * 想**离线**取立绘 ⇒ 必须解 `.ctexarray`（Godot 压缩纹理数组 + s3tc/DXT 解压 + 数组层索引 +
    再按 `mediaRects` 对齐切片）。**理论可行、成本高，不推荐**（也可试"用 GDRE 内置 Godot 跑一段 GDScript"导出）。
  * ✅ **推荐路线 = 游戏内预热**：实例化 `<Key>.tscn`（或 `TowerDefenseManager.GetPacketSpriteScene`）→
    `SubViewport` 渲染 → `GetImage()` 回读 → 算特征 → 落盘缓存。
    零格式逆向；上游 STS2 Mod 的 `PortraitGpuImageLoader` 就是现成同款实现，可照抄。
* ✅ 顺带（仍然成立）：`XWModProjectLayout.cs:306` 把 `<Key>.dat` 当**角色包依赖**豁免
  ⇒ **Mod 包内可以自带 `.dat`**（自制皮肤走这条路）。
* ⚠️ **只解了源码/资源的解包树里没有 `.dll/.exe/.pck/data_*`** ⇒ 不能编译插件、不能实机验证；
  开发前先确认手上有**游戏本体**（`<本体>/data_PlantsVsZombies_*/PlantsVsZombies.dll` + `GodotSharp.dll` + `.pck`）。
* **图片替换的正规入口**：`<Key>.tscn` 里逐媒体列着
  `Animation/MediaReplace/<媒体名>.png = null` 槽位（如 `.../CactusBlover_head.png`）。
  比"改节点 `Texture`"规矩，但**是逐媒体替换**（一个植物十几个图层），批量做不现实。
* **「自定义皮肤」≠ 贴任意图**：`Custom/<Key>CoustomData.tres`(`CharacterCustomData`) +
  `Custom/Config/<Key>Custom0.tres`(`CharacterCustomConfig`) 靠
  `animeFliterOpen` / `animeFliterClose`（如 `"skin1&skin2"` / `"Blover_head&Blover_petals"`）
  **切图层显隐**，前提是美术已在 `.dat` 里预置 `skin1..skin8` 图层。
* **规模基准（V0.29 实测，用来判断"按图遍历全卡池"这类需求的难度）**：
  植物目录 **330 个**（Chapter0 41 / Other 47 / Cover 28 / Star 27 / Gold 19 / …）、
  `CharacterResource.json` **583 条**、`PacketBankResource.json` **顶层 12 个卡池**、
  `GeneralPlant` 共 **276 张**（White188 / Gold19 / Diamond16 / Colour6 / Star27 / Original20，
  `Include: ["OriginalPlant"]`）。
  ⚠️ 与旧口径（V0.28 的"22 池 / White178"）不同，引用数字时**先按手上的版本核一遍**。

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

五条硬约束（写错 = **整包被拒/回滚**）：

1. `runtimeAssembly` **必须恰好是字面量** `"Runtime/ModAssembly.dll"`（**这是包内物理路径，不许改**）；
2. `runtimeApiVersion` **必须恰好 `1`**；入口三个回调**一律 try/catch 绝不抛**（抛 = 无条件整包回滚）；
3. `provides`/`overrides` 非空时，包内**每个**被识别的文件都必须在里面声明；
4. `Runtime/` 目录**只许有一个** `ModAssembly.dll`（`.dll/.exe/.bat/.cmd/.ps1/.cs/.gd` 都算可执行文件，多一个就拒收）；
5. ★★★ **`.csproj` 必须写 `<AssemblyName>【本 Mod 的 id】</AssemblyName>`** ——
   **安卓**的 DLL 加载方式与 PC 不同（全 Mod 共用一个非可回收上下文，程序集名撞车直接
   `Android Mod assemblies share one non-collectible context, so main assembly names must be unique`）；
   而 `mod.json` 的 `runtimeAssembly` **仍保持** `"Runtime/ModAssembly.dll"` 不变
   （容器里的文件名永远是它，变的是**程序集身份**）。
   构建脚本取产物要写成 `os.path.join(out_dir, ASSEMBLY_NAME + ".dll")` 再改名为 `ModAssembly.dll` 装机。
   **依据 + 三条自检 → `references/plant-runtime-plugin.md` §1.1**。

配方（已实测）：概率大招、逐颗连射、真随机、**掐掉原版开火链**、**修「动画静止」**、
**与僵尸版「共用判定逻辑」（共享源文件 + 两问守卫）**
→ `references/plant-runtime-plugin.md`（§1.1 程序集名，§7 讲共用源文件的坑）。

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

## 4. 坑 Top 24（每条都能白忙半天）

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
16. ★★★ **「跨图集换头」= 三精灵结构 + 插件同步位姿**（2026-09-30 实测落地，别再重新发明）。
    场景：要让角色 A 的身体 + 角色 B 的头拼在一起（例：猫猫星机枪的身体 + 超级机枪射手的头）。
    **同一份 `.tres` 才能被父代画**（坑 14）⇒ 跨图集时头必须独立渲染，于是：
    ```
    Root 身体 : flashAnimeData = A.tres（游戏内置 / 包内均可），clip = BodyIdle
       ├─ Cap  : **同一份 A.tres**，clip = HeadIdle，layerVisible 只开要保留的层，
       │         写 parentSprite=".." ⇒ 被父代画（同图集 ⇒ 不花屏）+ **引擎每帧自动写位姿**
       └─ HeadHolder (普通 Node2D)
             └─ Head : **B.tres**，**不写** parentSprite/insertLayerId/followParentSpriteLayerId
                       ⇒ 独立 draw call（官方探针 AdobeAnimateDetachedChildOwnershipProbe）
    ```
    * ★ **代价**：独立渲染的那个引擎**不写**它的 `Position` ⇒ **必须由插件每帧 `head.Position = cap.Position`**
      （`cap` 就是那个被代画、位姿由引擎维护的「影子」）。只同步 clip 名，**别同步帧号**
      （两份 `.tres` 的同名 clip 长度可以不同）。
    * ★ 自检要**按节点块**断言（把 `.tscn` 按 `[node ...]` 切成块后查），
      而不是全文件 `in` —— 否则「Head 不得写 parentSprite」这类断言会被 Cap 的写法误判成通过。
    * ★ 引用游戏内置 `.tres` 时用**包内相对 / `res://`** 都行（本 Mod 用 `res://`，实测闸门放行）；
      但**节点属性写法建议统一**（本项目统一用 `Animation/Clip` + `Animation/LayerVisible/<层名>`，
      是已验证有效的写法；游戏原版 `.tscn` 用的是 `clip` + `layerVisible` 数组，两套都能读）。
    * ★ 顺带：**「特点照搬某内置植物」的最省做法 = 直接引用它的植物脚本**
      （例：`TowerDefensePlantCatGatlingPea.cs` 自带「4 常规 + 5 径向 TRACK 星 + 每 10 轮大星星」，
      引用它 ⇒ 插件零代码）。前提是 `sprite` 节点的脚本类型能满足它的强转与 `%Head` 依赖。
      想改「一轮几颗」只改数据侧 `fireNum`（引擎按这个次数重播开火动画，每次到 `fire` 帧发一颗），
      「多久一轮」只改 `fireInterval` —— 都不用插件。
    * ★★ **跨图集时 `offset` 必须换坐标系**（2026-09-30 实机踩的「头身彻底分离」）：
      `offset` 是"**图集坐标系内**的美术平移"，A 角色的头位 offset **不能**直接搬到 B 角色身上。
      正确做法：让两个"头美术"落在同一处 ⇒ Head 的 `offset` 取**宿主角色头节点的 offset**
      （本例宿主是猫猫星机枪 ⇒ `(20,25)`；照搬 SGP 的 `(-37.05,-47)` 会让头整体偏左上约 (57,72)px，
      实机截图里就是"头飘在左上、身体留在右下"）。
      推导：`Cap.position + Cap.offset` 就是宿主头的落点；插件里 `head.position = cap.position`
      ⇒ `head.offset` 取同一个值即可对齐。
      ⚠️ 连带影响：`Marker2D(炮口) = ANCHOR_MUZZLE + HEAD_OFFSET` 这条恒等式会自动跟随，
        所以 offset 一改，`MARKER2D_POS` 也要跟着变 —— 生成器里用同一个常量算，**别手写**。
    * ⚠️ 本结构下 `layerVisible` / `mediaReplace*` **必须用数组写法**，见坑 17。

17. ★★★ **精灵场景的属性名：先分清「注册名 / 导出名 / 死属性」三类**（2026-09-30 源码级复核，**本条修正了之前的错误结论**）。
    `AdobeAnimateSprite._GetPropertyList()`（`:2765-2810`）只注册三个**路径名**：
    `Animation/Clip`、`Animation/LayerVisible/<层名>`、`Animation/MediaReplace/<媒体名>`。
    但 `[Export]` 还额外暴露了裸名 `clip` / `layerVisible` / `mediaReplaceAtlasPaths` /
    `mediaReplaceUse` / `offset` / `trueFrameRate` / `skipLastFrame` / `flashAnimeData` /
    `insertLayerId` / `followParentSpriteLayerId` / `parentSprite` / `timeScale` / `playBack` / `pause`
    ⇒ **两类名字都有效**（之前的"简写必失效"结论不成立）。
    ★ **真正的死属性是 `useMultiMesh` / `useTween`** —— 它们**不在**那 28 个 `[Export]` 成员里，
      写了不报错、也完全不生效（超级机枪射手与星星版的场景里都写了 `useTween = false`，纯属无效）。
    ★ 关于「关层」：
      · `_Set("Animation/LayerVisible/<名>")` 有 `id < _layerVisible.Count` 守卫；
      · `_layerVisible` 初值是空数组（`:341`），但 `ApplyFlashAnimeDataChange()` /
        `PrepareFlashAnimeDataSerializedOverrides()`（`:10194-10200` / `:10271-10277`）会把它
        **Resize 到图层数并全填 true**。
      ⇒ 结论：**要关某层，最稳的是写 `layerVisible = [...]` 数组**（长度 == 图层数）；
        只写路径简写时，效果取决于 `_layerVisible` 是否已被初始化 —— 别赌。
      ⇒ 本项目做法（最保险）：**两种都写**。`.tscn` 里务必把 `flashAnimeData` 写在最前。
    参考：超级机枪射手的精灵场景用的是**路径名**（`Animation/Clip` 等），实机验证可用。

18. ⚠️ **插件给 `FireComponent.CreateProjectileByData()` 补弹时，`gridYOverride` 必须显式给**。
    不给 ⇒ 日志刷 `[BulletField:E_FIELD_UNAVAILABLE] projectile='…' could not be mounted`，
    子弹**一颗都出不来**（实测一次大招刷 1214 条），表现为「大招完全没触发 / 技能没反应」。
    引擎自己的 `Fire()` 之所以没事，是因为 `lockProjectileGridY = true` 时它内部替你填了；
    **而不写这个字段的植物（例如照抄猫猫星机枪的配置）就没有这层保护** ⇒ 只能插件自己填
    `overrides.gridYOverride = <植物>.gridPos.Y`（`FireComponent.parent` 就是 `TowerDefenseCharacter`）。
    ⚠️ 排查心法：**"技能没反应"先去 `logs/godot.log` 搜 ERROR**，不要先怀疑触发概率 ——
    本例里大招其实**触发了 1214 次**，全被 BulletField 挡在门外。

19. ★★ **关层时不能按"图层名"猜，必须按"媒体"反查所有层**。
    同一张图会被**多个图层共用** —— 实测 `SuperGatlingPea_helmet.png`（那顶军帽）同时挂在
    `GatlingPea_helmet`(layer 22) **和** `helmet2`(layer 23) 两层上（两份 `.tres` 的
    `sliceMediaIds` 都指向同一个媒体 id）；只关 `GatlingPea_helmet` ⇒ **帽子照旧显示**，
    而且不报错、不告警，看起来像"关层完全没生效"。
    ⇒ 换头/去件前先做**数据级诊断**：解析 `.tres` 的 `frameOffsets` / `frameCounts` /
    `sliceMediaIds` / `sliceLayerIds`，列出「每个 clip 段里各 layer 用了哪些 media」，
    并反查「某个 media 出现在哪些 layer」。本项目现成脚本：
    `.cache/_diag_ssg_head_layers.py`（改路径即可复用到任何角色）。
    ⇒ 判据：**要移除一件东西，就把它用到的所有 layer 都关掉**，而不是关"名字最像的那一个"。
    ⚠️ 反向教训：`SuperGatlingPea_helmet2.png` 那张图只出现在 `anim_power`(layer 0)，
    而 `anim_power` **不属于任何 clip**（clips 只覆盖 0..74）⇒ 它永远画不到。
    "看起来像黄色披风件"纯是我看联络表时的臆测 —— **别靠看图猜层名，要查数据**。

20. ★★ **两个精灵拼成一个"部件"时，必须逐帧同步 `frameIndex`，不能只同步 clip**。
    三精灵换头里，帽子（Cap，宿主图集）与头（Head，自制图集）是两个独立精灵，
    各自按 `trueFrameRate` 推进；而**宿主精灵脚本**（如
    `CatGatlingPeaSprite.BatchPhysicsUpdate`）只会去改它认的那个 `%Head` 的 `timeScale`
    （2.0 / 0.5 / 1.0 追身体相位）⇒ 另一个精灵的相位与速度都会漂开，
    视觉上就是「**帽子在头上滑动 / 与头运动幅度速度不一致**」。
    修法（插件里每帧做）：
    ```
    int capRel = (capLen == headLen) ? headRel
                                     : round(headRel * capLen / headLen);   // 长度不同按比例
    cap.frameIndex = cap.clipRange.X + capRel;   // frameIndex 是 public int 字段，可直接写
    cap.timeScale  = head.timeScale;             // 速度也抄过来
    ```
    前提：两份 `.tres` 的同名 clip **帧布局一致**（本例都是
    `BodyIdle(0,24) / HeadIdle(25,49)`，只有 `HeadFire` 长度不同：宿主 50..88 / 自制 50..74）。

21. ★★ **移植/派生一个既有生成器时：它的包目录里不能放你的工具脚本。**
    `build_plant_*.py` 末尾的 `sweep_stale_files(MOD_ROOT, keep)` 会删掉包目录里
    「本次不产出的文件」—— 把 `build_skin.py` 放在 `<BUILD_DIR>/` 下，**跑一次就被删**（2026-09-30 实测）。
    ⇒ 外观/校验工具放**独立目录**或 `.cache/`。
22. ★★ **`TowerDefensePlantGatlingPea/CatGatlingPea.projectileName` 会把 `fireCheckList[0]` 强转
    `FireComponentProjectileSingle`**（`:73` setter 与 `:134` `ImportVariantSave`）⇒ 想用
    `FireComponentProjectileWeight`（随机子弹）时必须
    `fireCheckList = [0] 占位单体 + [1] 随机池`、`checkProjectileId = 1`，
    插件取弹种也按 `fireProjectileList[0].checkProjectileId` 取，**别写死 `checks[0]`**。
23. ★★ **子精灵只有「父的直接子精灵」才被父代画**：`CollectOwnedChildBindings`
    (`AdobeAnimateSprite.cs:5365-5401`) 遇到「非精灵且有子节点」的中间节点会把
    `collectSpriteChildren` 置 false ⇒ 把子精灵挂**普通 `Node2D` 容器**下 ⇒ 独立渲染，
    **`Position` 也不会被 `UpdateChild()` 每帧覆写**。同一份 `.tres` 的两层结构用这条路最省。
    落点通式与 `Marker2D` 口径（**`Marker2D = 炮口画布坐标`**，不是 `炮口 + HEAD_OFFSET`）
    → `references/selfmade-skin-from-screenshot.md` §4。
24. ★★★ **「贴图不行」的第一动作是去解包树找官方原画，不是修抠图。**
    只要 `reanim/` 里有与该角色 `mediaDictionary` **同名**的 PNG，就能用
    「内置 `.tres` 的逐帧切片数据 + 那些 PNG」离线复刻出**官方画质 + 真动画**的外观
    （本项目的汉堡射手 11/11 全对上）—— 比从截图抠像强一个量级。
    流程与陷阱 → `references/tres-slice-reskin.md`。
    判据一句话：**能不能把 `.tres` 的媒体名对应到磁盘上的原画**。
25. ★★ **结构由素材决定，不是由习惯决定**：**按 y 切一刀会不会把角色切成两半**？
    会（整摞汉堡 / 一体化造型）⇒ **单精灵** + 角色自己的两个 clip，
    并且 `isSpliceSprite` / `spliceIdleAnimeClips` 一律不写、`spritePath` 指向精灵本身；
    不会（茎叶在下、头在上，中间有脖子）⇒ 才用头身双精灵。
    ⚠️ 出膛点也**别硬套别的角色的口径**：一体化角色用「炮管层伸出最远那帧的最右点」反解，
    该点**落在本格之外是正常的**。
    ★ 如果素材本身是"身体层只在前半段有 slice、头层只在后半段有 slice"，而你又想用单精灵
    ⇒ **帧重映射**：`out 0..24 = 身体(src 0..24) + 头(src 25..49)`、`out 25..49 = 身体(src 0..24) + 头(src 50..74)`，
      clip 变成 `Idle(0,24)` / `Fire(25,49)`。观感与双精灵等价，且**回避了 `Head.position` 被引擎覆写**
      这个最容易翻车的点（那要求 `head_offset = −(被跟随层 origin)`，而 origin 逐帧变化）。
      ⚠️ 脚本要断言「任何图层都不得跨身体/头部边界」。
      ★★ **身体段必须「循环」取（`B0 + k % LEN`），不能线性取（`B0 + k`）** ——
      本项目实测：线性取会让**整段开火动画的叶/茎图层数 = 0**，实机表现正是
      「开火时底部叶子消失」。而且**必须加逐帧断言**（每帧都要含全部身体图层；
      另外单独统计叶/茎条数），肉眼扫预览图很不可靠。
27. ★★ **优先找 Adobe Animate 导出（`anim.json` + `texture.json` + `texture.png`）当数据源**，
    比二进制 reanim 稳：每帧**直接给 `image` 名**（不用解二进制、没有「末轨 trailer 丢图」坑），
    图集清单**直接给每个部件的 x/y/w/h**（不用去解包树找散图）。
    实测同一角色：二进制 22 张 vs 导出 23 张 —— 多出来的那个在二进制侧被**误判成"无图控制轨"**
    （末轨 trailer 定界窗口所致），所以**丢弃"无图控制轨"之前先确认它真的无图**。

28. ★★★ **「没有待机动画」的**真正根因是结构**：`FireComponent` 会**接管** `spritePath` 指着的那一个精灵。**
    （本条在 2026-09-30 被连续修正两次，**最终结论是结构级**，前面两条不完整，一并记下当排除项。）
    ```csharp
    // AttackEntered() :3265 —— 无条件把 sprite 切到开火 clip
    sprite.SetAnimation(fireAnimeClips, loop: true, ...);
    // IdleEntered()   :3103 —— ★只在非空时才切回待机
    if (spliceIdleAnimeClips != "") sprite.SetAnimation(spliceIdleAnimeClips, loop: true, 0.2);
    ```
    * **排除项 1（有效但不充分）**：`spliceIdleAnimeClips` 必须与 `fireAnimeClips` **成对写**，
      否则打完一轮回不到待机。**但即使写成对，只要 `spritePath` 指着"唯一那个精灵"，待机仍然不稳。**
    * **排除项 2（有效但不充分）**：属性名要用引擎注册的路径形式
      （`Animation/Clip` / `Animation/LayerVisible/<层名>` / `Animation/MediaReplace/<媒体名>`）；
      `clip` / `layerVisible` / `mediaReplaceAtlasPaths` 这些 `[Export]` 裸名**也是有效的**；
      真正**死**的只有 `useTween` / `useMultiMesh`（全项目 C# 里根本没有这两个成员）。
    ★★ **正解 = 抄超级机枪射手的两精灵结构**（已实机验证可用）：
    ```
    根精灵  Animation/Clip = "BodyIdle"   offset (-40,-40)   只画身体层
      └─ HeadHolder（普通 Node2D）
           └─ Head  Animation/Clip = "HeadIdle"  offset (0,0) 只画头部层
    ComponentSet: spritePath → Head、fireAnimeClips = "HeadFire"、
                  spliceIdleAnimeClips = "HeadIdle"、isSpliceSprite = true
    ```
    ⇒ **火控只碰头精灵**，根精灵的 `BodyIdle` 从头到尾自由循环 ⇒ **待机常驻**。
    ⚠️ 对应的 `.tres` 也用**素材天然分段**（BodyIdle/HeadIdle/HeadFire 各 25 帧，帧号可与 0 不对齐），
      **不要**做帧重映射。无图控制轨保留（`locator.png` 占位）以对齐 SGP 的转换口径。
    ★ **排查套路**：先量产物帧间位移排除"素材没动画"，再做**机械属性 diff**
      （把参考包与本包的所有 `.tscn/.tres` 逐键列出对照）—— 别靠印象。
29. ★★★ **头部的「动态」与「高度」都要**实测反解**，别照抄参考实现的数字**（本坑 2026-09-30 被修正过一次）。
    **A. 头部动态（为什么会"只有茎在动"）**：
    参考 mod（超级机枪射手 / 超级星星机枪射手）的 `Head.position` **每帧被引擎覆写**成
    `被跟随层(anim_idle) 的 pose.Origin + 根 offset`，而 `anim_idle` 是**跟着茎摆的控制轨**
    （横向 ~9.8px、纵向 ~−5.9px）⇒ **头跟着茎一起晃**。
    若你把头挂在**静态 `Node2D`** 下（为了拿到确定落点），`Position` 不被覆写
    ⇒ 头只吃自己 clip 里的那 0.3px 横向 ⇒ 实机观感就是「头部几乎不动，只有茎在动」。
    ★ **修法（确定性等价）**：把这段位移**烘进头层逐帧变换**——
      `ΔP(k) = P_anim_idle(B0 + k%LEN) − P_anim_idle(B0)`，头部层在 HeadIdle 与 HeadFire
      两段都 `+= ΔP(k)`。这样头的横向摆幅 = 茎的摆幅，节奏与参考**同源同帧**。
    ★ **先量再改**：三个角色的 `stalk_top` 摆幅 / `anim_face` 自身起伏往往**逐位相同**
      （同素材家族）⇒ 数据没问题时，差异一定在**结构**上。

    **B. 头部高度（别把"抵消项"当成"上抬量"）**：
    参考实现的 `Head.offset.y = −47`（根是 −40）看着像"抬高 7px"，**但那是误读** ——
    那 −7 是用来**抵消 `anim_idle` 的 origin（y ≈ +48.7）**的，不是对原始位置的上抬。
    正确做法是**反解它的头落点**：
      `头落点 = 头的 slice origin + (P_跟随层(f0) − 根offset) + Head.offset`
    超级机枪射手实测 = **(−20.25, −20.50)**，而"经典坐标 − (40,40)"= (−20.80, −22.20)
    ⇒ 等效位移只有 **(+0.55, +1.70)** ⇒ **参考的头基本就在原始高度**。
    ⚠️ **Marker 的连锁修正**：若做了 A 的烘焙，`muzzle`（从已烘焙的 elements 量的）**已含 ΔP**；
      Marker 是 Head 的**场景子节点、不参与图层烘焙** ⇒ local 直接取该值，**不要再加一次 ΔP**。

30. ★★ **`config.canCopy` 别乱写 —— 它决定「全息投影花盆」能不能投影你的植物**（2026-09-30 实证）。
    `Asset/.../Plant/Star/PotQX/Scene/TowerDefensePlantPotQX.cs` 的
    `CreateHologramCharacter():192` 只收集**长在自己这一格上**、且满足三条的植物做投影模板：
    ```csharp
    item != this && item.config.canCopy && item.camp == base.camp
      && item.config.plantGridOverrideType == PLANTGRIDTYPE.NOONE
    ```
    然后把模板投影到**同一列的其他行**（`cellGet.CanPacketPlant(packet)` → `packet.Plant(...)`
    → 延迟一帧打全息着色器），30 秒后收回并在原地补一个普通花盆。
    ★ **铁律：`canCopy` 必须为 `true`，且 `plantGridOverrideType` 必须保持默认（不写 = `NOONE = 0`）。**
    * **内置金卡根本不写 `canCopy`**（类默认 `true`，`TowerDefenseCharacterConfig.cs:40`）——
      所以正确的做法是**照抄内置卡，别自己加这个字段**。
    * 踩坑记录：本项目脚手架模板里带了 `canCopy = false` ⇒ 花盆完全不投影；
      兄弟包 `SuperGatlingPea` 的**盘上**包是 `true` 但**生成器**里还是 `false`
      （说明那次是手工改的盘、没改生成器，一重建就回归）⇒ 改完要**同时改生成器**。
    * 加两条自检：`canCopy = true` 必须在 config 里；`plantGridOverrideType` **必须不出现**。
    * 配套确认（改完 `canCopy` 后逐项过一遍，别只改一处）：
      ① 能否种在花盆格上 —— `plantGridType` 默认 `{GROUND, POT, LILYPAD}` ⇒ 不写即含 POT ✓；
      ② 花盆能否收到模板 —— 上面三条 ✓；
      ③ 投影到其他行 —— 默认 grid 含 GROUND ✓；
      ④ packet 能否解析 —— 包内必须提供 `Packet: <Key>` ✓。
    * ⚠️ 顺带一个格式坑：**`.tres` 里不要写 `#` 注释**（Godot 配置文件格式不支持），
      要写说明就写在生成器 Python 侧的注释里。

31. ★★ **「产阳光」是组件，不是场景字段**；「随机子弹池」是纯数据，插件不用改（2026-09-30 实证）。
    **A. 产阳光**：
    * 机制 = `ProduceComponent` + `ProduceComponentDefinition`
      （`Script/Component/TowerDefense/Character/ProduceComponent/`）：
      `produceType`(默认 `Sun`) / **`produceInterval`（类默认就是 `25f`）** / `num`(每次数量) /
      `markerPaths`(生成点) / `initialDelayRange`(默认 3~6s 首次) / `glowLeadTime`。
    * ★ **要"每 X 秒产 N 阳光"，就在 ComponentSet 里加一个 `ProduceComponentDefinition` 子资源**
      并追加进 `Components` 数组；再在植物场景放一个 Marker 当生成点。
      内置汉堡 `HamburgerProduceComponentDefinition.tres` 就是现成参考：
      只写 `num = 50` + `markerPaths`，**不写 `produceInterval`**（= 默认 25s）。
    * ⚠️ **场景字段是陷阱**：`TowerDefensePlantHamburger.tscn` 里有
      `produceInterval = 25.0` / `sunNum = 50`，但 `TowerDefensePlant.cs` /
      `TowerDefenseCharacter.cs` 里**都没有这两个成员** ⇒ **死属性**（同 `useTween` 那类）。
      照抄那两行**不会生效**。
    **B. 随机子弹池**：
    * 选弹**完全在数据里**：`fireCheckList[idx]` → `FireComponentProjectileWeight.GetProjectile()`
      （每次现掷 ⇒ 每颗独立随机）；插件只调 `CreateProjectileByData()`，**零改动**。
    * 池结构可以简化成**单级**：`FireComponentProjectileWeight(averageWeight = true)`
      + N 个 `FireComponentProjectileWeightItem → FireComponentProjectileSingle →
      TowerDefenseProjectileCreateData(projectileName = &"<名字>")`。
      **不必**照抄内置汉堡的「0.97 / 0.03 两层」。
    * ★ **换成"全游戏子弹"要走枚举而不是手抄**：扫 `Asset/Config/Projectile/**` 里
      `script_class="TowerDefenseProjectileConfig"` 的 .tres → 取 `name` → **按 name 去重**
      → 排黑名单。本项目实测：138 份配置、去重 92 种、排掉 17 种后入池 75 种。
    * ★★ **"魅惑子弹"的判据有两条，缺一就漏**：引用
      **`TowerDefenseCharacterBuffHypnoses`**（如 `Puff/HypnoPuff.tres`）
      **或 `TowerDefenseCharacterEventHypnoses`**（如 `Cupid/CupidDefault.tres`）。
      只扫 Buff 类会漏掉 Cupid。
    * ⚠️ 负向黑名单别用裸名：池里的**子弹名**可能含你要查的片段
      （本项目用 `"CatGatlingPea"` 查"是否引用内置素材"，被 `StarBigCatGatlingPea` 误伤）
      ⇒ **用路径片段**（`"/CatGatlingPea/"`）。
    * ⚠️ 扩容后**不要逐条覆盖 `baseDamage`/`damageFlags`** —— 手抄几十条既费事又与游戏版本脱节，
      直接用子弹自己的配置。

32. ★★★ **要"全游戏子弹"清单，只认 `Registry/Projectile/ProjectileRegistry.json`，别扫目录**（2026-09-30 实证）。
    * 运行时注册表 = `TowerDefenseProjectileRegistry.REGISTRY_JSON` = `res://Registry/Projectile/ProjectileRegistry.json`，
      `RegisterInit()` 读 `Projectiles`（名字→路径，加载成 **`TowerDefenseProjectileData`**）/ `Skins` / **`Changes`（转换表）** 三段。
    * ⚠️ **子弹配置有两套类 + 两个目录**：`Asset/Config/Projectile/**` 是 `TowerDefenseProjectileConfig`（138 份），
      `Registry/Projectile/Config/**` 是 `TowerDefenseProjectileData`（98 份）—— **前者不是注册表**，
      本项目按它枚举时**混进 23 个没注册的名字（按名字打不出来）+ 漏掉 42 个已注册的**，双向出错。
    * ⚠️ **转换表也要读 JSON 别读 `.tres`**：`Asset/Config/ProjectileChange/*.tres` 是编辑器侧资源，
      与运行时 JSON **内容不同**（JSON 有第 5 张表 **`GarlicFire`** 大蒜火炬；`Fire` 6 条 vs 文件 8 条）。
    * 实操配方：`Projectiles` 的键 − 魅惑（引用 `TowerDefenseCharacterBuffHypnoses` / `EventHypnoses`）−
      产资源（`Coin*`/`Sun*`）− 僵尸专用（`Axe`/`Basketball`/`Ladder`）⇒ 本项目 97 − 10 = **87 种**。
    * 判定某子弹"是不是植物在用"：`grep -rl 'projectileName = &"<名字>"' Asset/Anime/Character/{Plant,Item,Zombie}`；
      **也有靠代码生成**的（`TowerDefensePlantRichwood.cs` 宝藏树桩 `new StringName("Chest")`）⇒ 还要查
      `CreateProjectileByName(..., "X")` 与 `new StringName("X")`。
    * 详见 `references/bullet-pool-and-overfire.md`。

26. ★★★ **卡片 / 图鉴里「没有图」= `packetAnimeScale` 没写。**

    `TowerDefensePacketConfig` 的 `packetAnimeOffset` / `packetAnimeScale` 默认是
    **`Vector2.Zero`**（源码 :42/:45），而卡片显示与**图鉴植物页**共用
    `TowerDefenseInGamePacketShow.UpdateSpriteLayout()`：
    `sprite.Scale = config.packetAnimeScale` ⇒ **缩放 0 ⇒ 预览缩成一个点**（不是缺资源！）。
    内置每一张卡都显式写了这三个字段（GatlingPea `(21,23)/0.5`、Hamburger `(21,30)/0.325`），
    **`packetAnimeClip` 默认 `"Idle"`**。
    取值法：与同族内置卡比「经典画布并集」，按画布高之比缩放 scale，再按
    「植株中心落在卡片同一点」反解 offset（例：我方 97.15×86.89 / 中心 (41.11,35.84)，
    内置 GatlingPea 91.56×86.38 / 中心 (47.66,36.09)、卡面点 (24.83,21.05)
    ⇒ `scale=0.5`、`offset=(24,23)`）。
    ⚠️ 自检必须断言**该值非零** —— 光断言"字段存在"拦不住 `Vector2(0,0)`。
    ⚠️ **从别的生成器手抄 `packet_tres()` 时最容易漏的就是这三行**（本项目实测漏过，实机表现为图鉴缺图）。

21. ★★★ **「混源合成图集」= 从两个角色各取一部分零件，离线合成一份新 .tres/图集**（2026-09-30 落地）。
    场景：要「A 的身体/帽子 + B 的头/眼镜」。**不要**用「引用两份游戏资源 + 拼多个精灵」去做
    —— 那是跨图集，会连踩坑 14 / 17 / 20。正确做法是**离线合成一份图集**，回到
    「单 `.tres` 双精灵」范式（头身天生同源同帧，无需插件同步）。
    做法（复制 `build_official_skin.py` 改成自己的 builder；本项目 = `.cache/build_ssg_skin.py`）：
      · 声明 `TRACK_PLAN = [(源标记, 轨名), ...]`，**顺序即 layer id**，逐轨指定取自哪个 reanim；
        只列白名单 ⇒ 另一角色自带的头/帽自然被丢弃（本例丢掉了 S 的帽子、Cat 的头部件）；
      · `load_tracks()` 读两个文件，按计划挑轨并**重排 `Track.index` = 计划下标**；
      · **两源帧数常常不同**（本例 93 vs 91）⇒ `nframes = max(...)`，取帧时
        `k = min(j, t.nframes-1)` **夹取到该轨末帧**（尾部通常是静止段，观感无损）；
      · `media_display_name()` 要认识**两套前缀**（长前缀先匹配，如 `SUPERGATLINGS_` 先于 `SUPERGATLING_`）；
      · ★ **「图层跨 body/head 边界」不能直接 raise**：A 的身体件可能在**全程**都有 slice
        （"披风一直飘"那种动画），不像 B 只在 BodyIdle 段有。改成输出 `cross_layers`
        （= 跨界且**有真实贴图**的层），由生成器写进「Head 精灵的 layerVisible = false」
        ——**头身分离改由 layerVisible 保证**，不再依赖"帧段天然分离"；

      · ★★★ **clips 绝不能硬编码 —— 必须从「控制轨的可见段」推导**（2026-09-30 血泪）。
        这是"每一帧都缺一点部件"的真凶：素材常有**前置空帧**，不同角色的空帧数不同。
        本图集实测 身体件可见段 = **4..28**、头待机 = **29..53**、开击 = **54..92**，
        而 `build_official_skin.py` 里给 SuperGatling 硬编码的 `(0,24)/(25,49)/(50,86)`
        **整整错位 4 帧** ⇒ BodyIdle 前 4 帧没身体、HeadIdle 前 4 帧没头。
        ✅ 做法：`BodyIdle = anim_idle 的可见段`、`HeadIdle = anim_head_idle 的可见段`、
        `HeadFire = anim_shooting 的可见段`（控制轨本来就是"这一段演什么"的标记），
        并断言三段严格递增不重叠；`BODY_LAST_FRAME` 同步改成 `BodyIdle[1]`。
        ⚠️ 配套：自检里"clip 必须覆盖 0..N"这条要**放宽**（允许开头留前置空帧），
        否则会把正确的推导判成错；预览的取帧列表也要改成按新 clips 取样（硬编码帧号会取到空帧）。

      · ★★★ **推导出 clips 之后，还要把「前置空帧」整段裁掉，让 clip 从 0 开始**
        （2026-09-30 第二次血泪，症状极具误导性：**不攻击 + 部件消失 + 像没有待机动作**）。
        引擎 / 自检 / 预览都**默认 clip 从 0 开始**；若照搬带偏移的 `(4,28)/(29,53)/(54,92)`：
          - `HeadFire` 段与事件帧对不上 ⇒ 打不出子弹；
          - 部件的 slice 落在 clip 之外 ⇒ 不渲染（表现成"某部件没了"）；
          - 播到的是错位帧 ⇒ 看着像角色静止不动。
        ✅ 做法：用控制轨 `anim_idle` 的可见起点当"公共前置空帧数"，逐轨 `frames = frames[lead:]`，
        归一化后 clips 应正好是 `(0,24)/(25,49)/(50,88)`（与内置家族一致）；
        ⚠️ 裁帧后可能有个别轨"全程无 slice"（整段落在被裁区间里）⇒ **剔除并重排 layer id**，
        不要让它触发"图层全程无 slice"的报错；
        ⚠️ 生成器侧的 `HEADFIRE_CLIP_PLANT` 也要同步改回归一化后的值。
        ✅ 归一化成功的最强信号：**炮口/事件帧回到 `HeadFire 起点 + 12`（= f62）**。
      · 排查顺序（省时间）：**先比图源**（atlas 的 `texture.json` vs `reanim/*.png` 的逐项尺寸对照，
        0 缺失就说明图没问题）→ **再比数据源**（两种源算出的 `slices` 总数是否一致）
        → ★ **最后打印「每帧的可见部件清单」**（哪个部件在哪些帧可见），
        这一步才是找"缺件"的决定性证据。
      · ★ **超采样素材必须先降采样**：`cloak*_yellow.png` 是 1080x1440，而游戏内置同媒体只有
        270x360（正好 1/4），且该轨 `sx/sy` 全程未定义（默认 1.0）⇒ 不缩放会让图集涨到
        1084x6120、`.dat` 26.5 MB（还可能超 GPU 纹理上限）。做一次整数倍盒式降采样即可
        （纯 Python 够快，不必依赖 PIL）；
      · **单一素材源的硬断言要降级**：如「发射帧偏移 == 内置单发家族 +12」在混源后必然不成立
        （实测 16）⇒ 降为提示，保留「落在射击段内 / 首次最大伸出」两条硬校验。
    ⚠️ **交付前一定看 builder 自产的 `preview_official_composed.png`**（根+头合成观感），
      必要时再做「有/无某部件」的 A/B 预览 —— 比实机跑一趟便宜得多。本项目就是靠 A/B 预览
      确认了"猫头盔虽大（139x144）但没把 S 的头（70x65）完全遮住、眼睛与脸仍露出"。
    ⚠️ 顺带一条取证技巧：要判断"两套素材坐标系是否一致"，直接对比同名轨的 x/y
      （本例两个 `anim_face` 在 f30 都是 x=19.3 y=16.2 ⇒ 逐位相同 ⇒ 可直接叠加）。


22. ★★★ **ComponentSet 里的每一个 `NodePath` 都要能真解析到节点 —— 否则"完全不攻击且零 ERROR"**。
    2026-09-30 实机踩穿：把 Sprite 场景从三精灵改成双精灵（去掉中间节点 `HeadHolder`）后，
    生成器里 `spritePath` 与 `firePosMarkerPaths[0]` 还写着
    `SpriteGroup/TransformPoint/GatlingPea/HeadHolder/Head` ⇒
    `FireComponent.sprite == null` ⇒ 组件拿不到精灵、不播 `fireAnimeClips` ⇒ **一颗子弹都打不出**，
    而日志里**一条 ERROR 都没有**（只有一条对所有 mod 都报的无害 CompanionOnly 警告）。
    ⇒ **改场景节点结构时，必须同步搜一遍所有 NodePath 字符串**（`spritePath` /
      `firePosMarkerPaths` / `res://` 引用），并**加一条自检**：
      把「角色场景 + 被 instance 的 Sprite 场景」拼成路径集合，逐个核对每条 NodePath。
      负向测试：把路径改回旧结构，闸门必须报错（本项目已用此法验证，命中 rc=3）。
    ⇒ 排查心法：**"零 ERROR 但不工作" ⇒ 先查"引用/路径类"配置**（NodePath、资源路径、
      节点名），而不是查代码逻辑。
23. ⚠️ **"预览里对、实机里错" ⇒ 多半是把值写到了引擎会覆写的死字段上**。
    本例：builder 的合成预览用 `head_dy = 8` 抬高头部（注释还写着"= 实机观感"），
    但实机 `Head.position` 是**死值**（引擎 `UpdateChild` 每帧覆写）
    ⇒ 那 8px **从没生效**，实机头比预览低 8px（用户报"头偏下"）。
    ⇒ 需要"抬高/挪位"时，**写 `offset`（只作用于本精灵美术，不受引擎影响）**，
      而不是 `position`；并牢记 `MARKER2D_POS = ANCHOR_MUZZLE + HEAD_OFFSET` 会自动跟随。
    ⇒ 顺带：给 `Head` 加 `scale` 是**安全**的（Marker2D 是其子节点、与世界一起缩放），
      上面那条炮口恒等式在任意缩放下仍成立。


24. ★★★ **"图集降采样" 必须同步放大该轨的 `sx/sy`，否则部件会缩小 N 倍（看起来像"部件丢了"）**。
    2026-09-30 实机踩穿：为了压体积，把 `cloak*_yellow.png` 从 **1080x1440 降到 1/4（270x360）**，
    但**没改该轨的 `sx/sy`** ⇒ 渲染尺寸 = 270x360 × 0.105 = **28x38**（应有的 1/4），
    症状是"披风整条不见了"——其实它还在，只是缩成左上角一个小黄块（要放大 6 倍才看得见）。
    ⇒ 判据：**图尺寸改了，变换里的缩放就必须同倍反向补偿**；
      ⚠️ `SENT`（未定义/继承）的帧要**原样保留**，×N 后会变成"看起来有效的大负值"，
        被 `carry()` 当成真值 ⇒ 部件瞬间消失。
    ⇒ 交叉验证手段（强烈推荐）：把我们的逐帧 `x/y/sx/sy` 与**游戏内置同名角色的 `.tres`**
      逐项对照 —— 本例对照后立刻看出 `sx` 差 4 倍（0.42 vs 0.105），
      而两边的**显示尺寸本应相同**。这条对照法对"位置/缩放类"问题几乎一击必中。
    ⇒ 顺带记一条美术结构口径（换外套类部件的挂点/朝向怎么写）：
      **挂点**看该轨的 transform（相对角色根，不在头/茎上）；**层级**看它的 `layerId`
      落在谁之后（本例 `cloak1` = 8，在茎叶 0..7 之后、头部件之前）；
      **随动**看它属于哪个 clip 段（本例 BodyIdle 0..24 ⇒ 挂在 Root 精灵上循环播）。

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
| `references/tres-slice-reskin.md` | **内置 `.tres` 切片数据 + 经典版原画重建**（官方画质 + 真动画的第二条路）：素材名校验、离屏合帧的 PIL `AFFINE` 归一化陷阱、**单精灵 vs 头身双精灵的判据**（按 y 切一刀会不会切断角色）、皮肤层整层丢弃、标定沿用内置 / 出膛点反解 |
| `references/selfmade-skin-from-screenshot.md` | **只有一张游戏内截图**时：抠像（描边当屏障的 flood）、分层 + 重叠带、头挂普通 `Node2D` 下独立渲染、落点通式与 `Marker2D` 口径、程序化动画；**移植既有 mod 时的两条坑**（生成器会删包目录里的工具脚本 / `projectileName` 强转 `fireCheckList[0]`） |
| `references/bullet-pool-and-overfire.md` | **子弹对象池与「过火」**：池是**全局单例** `BulletField.Instance`（65536 槽 freelist）、子弹完整生命周期（生成/运行/终态回收）、火炬树桩**没有自己的池**（只是往唯一池注册 `IProjectileZone`）、过火转换**优先同槽就地改**（`TryChangeBulletDataInPlace`）、`RequiresReplacement` 的触发条件、`fireMethodFlags & 2` = 免疫过火、转换表只有 8 条 |
| `references/plant-runtime-plugin.md` | 决定 B 命中（概率/连射/真随机/抑制原版/动画静止/**与僵尸版共用判定核心**） |
| `references/plant-verification.md` | Step 10 写闸门、结果可疑、实机前 |
| `references/plant-pmod-hotpatch.md` | **只有 .pmod 没有生成器**，直接热补丁数值属性（cost/射速/血量…）时 |
| `assets/新建植物清单.md` | **Step 0 一开始就打开**，逐项打勾 |


33. ★★★ **拿到外部素材，第一件事是体检「有没有动画定义」**（2026-09-30 实证：PvZ1 二创 `megagatling`）。
    **贴图齐全 ≠ 能做。** 判定三连：
      ① 找 `<角色>.reanim` / `<角色>.reanim.compiled`（经典引擎）或 `*.tres`(AdobeAnimateData)（重置版）；
      ② **全目录按字节 grep 角色名**（含 exe / 图片容器）—— **0 命中 = 动画根本没接入，素材是半成品**；
      ③ 看 mtime：解包日统一时间戳之外**单独冒出来的那批** = 作者后来加的（本例 19 张 PNG 跨 5 个月分批画的）。
    ⇒ **只有贴图、没有动画定义**时，仍有两条退路（都不如"问主人要一份真 reanim"）：
      * **借轨换皮**：拿**同族内置角色**的 `.reanim.compiled` 当骨架（部件名常常一一对应），
        把贴图按轨映射过去 ⇒ 再走路线 A 直转。代价 = **逐部件标定**
        （外部素材与内置同部件尺寸比常 1.1×~3.3×，且**各件不一致** ⇒ **不能用一个统一缩放系数**）
        ＋ **新增/合并轨**（例：外部把 4 根枪管画成**一张图**，而内置是 4 条独立 `barrel1..4` 轨
        ⇒ 必须合并成 1 轨，否则同一张图叠画 4 次）。
      * **自制图集**（路线 B）：自己写 Idle/Fire 两个 clip（见坑 25 / 坑 21）。
    ★★ **PvZ1 reanim 的真实结构（换素材前必须知道）**：**身体与头在同一条时间轴的不同帧段**，
      引擎**双通道各播各的**：
        `GatlingPea`  `anim_idle(4..28)` 只含茎叶 / `anim_head_idle(29..53)` 才含头·盔·枪管 / `anim_shooting(54..92)`
        `PeaShooter`  `anim_idle(4..28)` + `anim_head_idle(29..53)` + `anim_shooting(54..78)` + **`anim_full_idle(79..103)` 全身**
      ⇒ **离线复刻 / 预览必须「身体帧 + 头部帧」叠加**，只取一帧会得到"半截角色"（本项目踩过）。
      ⇒ 这正是我们「双精灵 / 帧重映射」范式的**同源出处**：`.reanim` 的 `anim_idle`/`anim_head_idle`
        就是我们的 `BodyIdle`/`HeadIdle`；`<f> < 0` = 该 (轨,帧) **不产 slice**。
    ★ 工具：`Zombie/.workbuddy/.cache/reanim_xml.py`（reanim XML 解析，含 SENT 继承展开）＋
      `preview_megagatling_skeleton.py`（骨架换皮离线预演：AFFINE 绕左上角旋转、按"骨架部件尺寸 × sx/sy"等比对齐）。
      详见 `references/plant-skin.md` §5。


34. ★★★ **跨引擎素材移植评估：拿到一个「别的引擎做的 PvZ 角色 MOD」，先做三问再谈能不能用**（2026-09-30 实证：PVZ Fusion 的 BepInEx 包）。
    **三问**：① **引擎**是什么？② **资源容器**是什么？③ 代码挂在什么**框架**上？
    本次实例 = `MegaSuperGatling-五阶超级大哥系列`：
      ① **PVZ Fusion(PVZRH)**，Unity **2022.3.20f1c1 + Il2Cpp**；
      ② `BepInEx/plugins/*.dll` 里**内嵌 UnityFS AssetBundle**（+ 3 个独立 `skin/skin_*` bundle）；
      ③ BepInEx + Harmony（IL 打补丁）+ `CustomizeLib.BepInEx`（PVZRHCustomization 的公共 API 层）。
    ⇒ 结论模型（可直接套用）：**美术可移、代码零复用、动画要另找路**。
      * ✅ 可移：全部 PNG（源画 + Sprite 部件）、**部件清单与层级语义**、数值与机制设计（照着重写）。
      * ❌ 不可移：C# 逻辑（Il2Cpp/Harmony/自定义库 API）、AnimationClip、Prefab/AnimatorController/ParticleSystem、自定义 Shader。
      * ⚠️ 动画：Unity 的 `AnimationClip` 在这类包里通常是 **MuscleClip 压缩态**
        （`m_PositionCurves/m_RotationCurves/m_FloatCurves` **全空**，真数据在 `m_MuscleClip.m_IndexArray/m_ValueArrayDelta`）
        ⇒ **Python 侧读不出明文关键帧**，要么在 Unity 里用 `AnimationUtility.GetCurveBindings/GetEditorCurve` 导出，
        要么**根本不用它**——见下面的"有利面"。
      * ★★ **有利面**：这类 MOD 常常**直接沿用原版 PvZ 部件名**（`PeaShooter_backleaf` / `GatlingPea_head` / `paokou1..6`）
        ⇒ 与杂交版内置角色**同一套骨架语义** ⇒ **骨架动画直接借杂交版内置角色的 `.tres`/reanim**，
        **只要贴图 + 部件映射表**（做法同坑 33 的「借轨换皮」）。
        本次实测：PVZ Fusion 的电能超级机枪射手的 `Skin2` 外观（草帽 + 长刀）**就是** PvZ1 二创包 megagatling 的同一套美术。
    ★ **工具链（本机已装，可直接复用）**：
      · `dotnet tool install -g ilspycmd` ⇒ `~/.dotnet/tools/ilspycmd.exe -p -o <dir> <dll>` 反编译（PVZ Fusion 插件代码量仅 ~25 KB）。
      · `pip install UnityPy`（managed venv）⇒ 读 bundle。
      · 工具脚本：`.cache/extract_fusion_bundles.py`（**从 PE 里按 `UnityFS` 头 `size` 字段定长抠出内嵌 bundle** + dump 全部对象）、
        `.cache/fusion_prefab_tree.py`（Prefab 层级树）、`.cache/fusion_compose.py`（角色立绘离线合成）、
        `.cache/fusion_export_sprites.py`（全量 Sprite 导出）。
    ★★ **两个必踩的坑**：
      * **`Sprite.image` 在 DXT5/BC3 压缩图集上会抛内部 `TypeError`（UnityPy 的 logger 格式串 bug），不是"素材缺失"**。
        ✅ 正解：取 `Sprite.m_RD.texture`（Texture2D 的 PPtr）+ `m_RD.textureRect`，**自己从 Texture2D 的 image 上 crop**；
        ⚠️ Unity 的 `textureRect` 是**左下原点、y 向上** ⇒ `top = texH - (y + h)`。
      * **合成时必须除 `m_PixelsToUnits`（默认 100）**：sprite 的"像素尺寸"要 `/ppu` 才是"世界单位"，
        否则部件按原图像素（300 px）画、位置按单位（3）定位 ⇒ **全堆在左上角、看起来像"只剩头和特效"**（本次白查了两轮）。


35. ★★★ **让「子弹自己会做事」只有一条路：继承 `ProjectileBehaviorKernel`**（2026-09-30 首次打通）。
    需求里凡是出现「**子弹**每 X 秒做某事 / 命中第 N 次做某事」的，**纯数据做不到** ——
    `config.useRange` 只在**命中/落地各爆一次**（`BulletField.cs:3666-3671`/`:3821-3823`），
    与"每 X 秒一次"不是一回事。
    挂载链（行号实证）：`TowerDefenseProjectileConfig.behaviors : Array<ProjectileBehaviorDefinition>`
      → `BulletField.cs:7399-7448` 编译成 kernel → `:4432` 写 `BulletData.behaviorProgramId`
      → `:7476-7545` **每帧** `kernel.Process(index, ref bullet, delta)`；命中走 `kernel.OnHitTarget(...)`。
    ★ **现成范例 = `ProjectileBehaviorYMoveSin`**（正弦飘动 + 内嵌 `SineKernel`），照它的形状抄。
    ★ 关键配套：无限穿透 = `config.penetrateNum = -1`（`:3585`）；
      范围伤害 = `TowerDefenseExplode.CreateProjectileExplode(pos, config, exclude, camp,
      canHitShieldedTargets, runtimeDamage, damageFlags, fireMethodFlags, collisionFlags)`（`:305`），
      范围口径 `GetMapGridSize() * 2f * config.rangeSize`（`:540-541`）⇒ **`rangeSize=1.5` = 3×3 格 = 半径 1.5 格**；
      定身 = `TowerDefenseCharacterBuffConfig.CreateBuffByKey("MagicImmobilize")` + `buff.AddBuff(cfg)`；
      范围找角色 = `TowerDefenseManager.Instance.GetCharactersIntersectingRect(rect, false, 0)`。
    ⚠️ 三个编译级坑：`BuffComponent` **不是 GodotObject**（只能判 null）；`GetGlobalPositionForPhysicsFrame` 是 **protected**
      （用 `Node2D.GlobalPosition`）；入口接口在 **`PVZHE.ModEditor.ModSystem`** 命名空间。
    ⚠️ `[GlobalClass]` 在"不用 Godot.NET.Sdk 的插件工程"里能否注册 **仍待实机验证**。
    ⇒ 详见 `references/bullet-behavior-api.md`（含完整签名、范围口径、5 个坑、参数闸门做法）。


36. ★★ **「钻卡 / 特定价格 / 特定冷却 / 不涨价 / 灰烬伤害」全是纯数据，别去写插件**（2026-09-30 实证）。
    · **卡类型** = `TowerDefensePacketConfig.type`，枚举 `TowerDefenseEnum.PACKET_TYPE`：
      `NOONE=-1, WHITE=0, **GOLD=1**, **DIAMOND=2（钻卡）**, COLOUR=3, STAR=4, ORIGINAL=5, ZOMBIE=6, COVER=7, GRAY=8`
      ⇒ 钻卡写 **`type = 2`**；★ **两处都要写**（`Characters/Plants/<KEY>/Packet/<KEY>.tres` + `Resources/Cards/<KEY>.tres`）。
    · **价格 / 冷却 / 不涨价** 全在 `TowerDefensePlantConfig`：`cost` / `packetCooldown`(秒) /
      ★ **`costRise`（重复种植每株加价，**不涨价就写 0**，内置默认 100）** / `canCopy`（必须 true）/ `hitpoints` / `ashScene`。
    · **灰烬伤害** = 游戏里的灰烬是**独立角色 `TowerDefenseCrater`**（`CraterDayGround` / `CraterLava` / …），
      入口 `TowerDefenseCharacter.CraterCreate(nolimit, craterName="CraterDayGround", halfCrater)`（`:4469`）。
      ★ 要"**被该伤害击杀才化灰**"就必须**延后一帧判定**：先记下本次命中的目标 →
      （伤害是 `QueueProjectileExplode` **异步排队**、下一物理帧才结算）→ 下一帧再 `IsDie()` 为真才 `CraterCreate()`。
    · **最快的闭环路径 = 克隆一个已验证的同族包**（整目录复制 + 全量替换 key + 外观三件套二进制原样搬），
      ⚠️ 但**克隆流程会把模板残留带回来**（`.bak*`、别人的 `.pvzmodeproject`）⇒ 生成器里要**主动删**。
    · 交付配**两道参数闸门**：源码侧 + 包数据侧（都带 `--neg`）。
    ⇒ 详见 `references/card-type-and-ash.md`。

> ★ **交付打包**（「打包到桌面」/「做全量包」）在 `pvz-hybrid-mod-authoring/SKILL.md`
> 的〈交付给用户时的「工作目录 zip」格式〉一节，含 **全量包 vs 单包** 的区分口径与
> `_pack_all.py` 的 `WANT` 清单维护规则（新增/拆包一个 Mod 后必须同步改，否则新包不进 zip）。
---

## ★★ 最省事的「复用内置角色」路线（2026-09-29 实测：经典模仿者 Mod）

当需求是「**内置某植物的行为不对，但不要改它，另建一个植物**」时，**不要**照 §3 的 12 步全套走
（那套是给"全新美术 + 全新机制"的）。可以只生成 **6 个资源文件**，外观/组件全部 `instance` 内置的。

### 做法

```ini
# <Key>/Scene/<Key>.tscn —— 整个角色场景直接 instance 内置角色场景
[gd_scene format=3]
[ext_resource type="PackedScene" path="res://Asset/Anime/Character/Plant/Chapter0/Imitater/Scene/TowerDefensePlantImitater.tscn" id="1"]
[ext_resource type="Resource" path="../Config/TowerDefensePlant<Key>.tres" id="2"]
[ext_resource type="Resource" path="./<Key>ComponentSet.tres" id="3"]

[node name="<Key>" instance=ExtResource("1")]
ComponentSet = ExtResource("3")
config = ExtResource("2")
# 需要改的内置 [Export] 字段直接在这里覆盖（instance 节点可以覆盖任何导出属性）
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "…"
metadata/mod_character_category = "Plant"
metadata/mod_character_config_path = "../Config/TowerDefensePlant<Key>.tres"
metadata/mod_character_sprite_scene = "../Sprite/<Key>.tscn"
```

```ini
# <Key>/Sprite/<Key>.tscn —— 精灵场景同样直接 instance
[gd_scene format=3]
[ext_resource type="PackedScene" path="res://Asset/Anime/Character/Plant/Chapter0/Imitater/Imitater.tscn" id="1"]

[node name="<Key>" instance=ExtResource("1")]
metadata/mod_resource_kind = "CharacterSprite"
```

```ini
# <Key>/Scene/<Key>ComponentSet.tres —— 直接继承内置的组件定义
[resource]
script = ExtResource("3")            # CharacterComponentSet.cs
ParentSet = ExtResource("2")         # res://Prefab/TowerDefense/Character/ComponentSets/TowerDefensePlantComponentSet.tres
Components = [ExtResource("1")]      # 内置角色的 xxxExplodeDefinition.tres / FireComponent 定义
```

**因为 instance 的是完整内置场景**（它自带 `ComponentSet = …`），所以 **Step 4 那条"必须显式声明
ComponentSet"的坑不适用** —— 但**仍要**在 `metadata/mod_character_sprite_scene` 指向**包内**精灵场景，
否则 `XWModContentValidation` 会因为查不到 `CHARACTER_SPRITE[<Key>]` 而 throw。

### ⛔⛔ 但"只 instance 内置场景、不写 C#"这条路**跑不通**（2026-09-29 实测定案）

**症状**：Mod 加载成功、卡能显示能选，但**种下时报**：

```
WARNING: [TowerDefenseManager] Mod 角色脚本实例化失败，回退内置场景路径：<Key>: 角色场景缺少 CompanionOnly 伴随脚本元数据。
```

⇒ **种出来的其实是内置角色**，于是走了内置角色的技能
（本次实例：新模仿者被种下后按内置模仿者的 `Explode()` **随机变身**）。

**机制**（`addons/ModEditor/ModSystem/XWModCharacterCompanionRuntime.cs:160-220` `TryCreateInstance`）：
1. 实例化 Mod 的场景 → `authoredRoot`
2. 读它的元数据 `mod_character_script_binding` 与 `mod_character_script_path`
3. **`binding` 必须恰好是字面量 `"CompanionOnly"`，且 `path` 非空**，否则直接失败
4. `expectedTypeName = Path.GetFileNameWithoutExtension(path)`
   （如 `./ImitaterClassic.tscn` → `ImitaterClassic`；⚠️ **别用 `.cs`**，会被判可执行文件拒包）
5. 在 **Mod 的 DLL** 里找满足 `!IsAbstract && Name == expectedTypeName
   && authoredRoot.GetType().IsAssignableFrom(type)` 的类型
6. `Activator.CreateInstance(type)` **反射建实例**，再把壳节点的**属性 + 子节点**搬过去，丢弃壳

⇒ **Mod 角色 = 「壳场景（instance 游戏 Prefab）+ DLL 里一个同名 C# 类」**，两者缺一不可。
包内的**声明文件**只被"取文件名"，但 ⛔ **不能用 `.cs`** ——
`ModLoader.IsExecutablePackageFile` 的扩展名白名单**包含 `.cs`**（还有 `.gd`/`.bat`/`.exe`/`.cmd`/`.ps1`），
包内出现它会被判 `undeclared executable package file`、**整包拒收**。
⇒ **正确做法：`mod_character_script_path` 直接指向场景文件自己（`./<Key>.tscn`）** ——
   引擎只做 `Path.GetFileNameWithoutExtension()`，**不读文件内容**，类名同样是 `<Key>`。

⚠️ 结论：**"纯数据复用内置角色、一行 C# 都不写"是不成立的** —— 引擎一定会走 Companion 通道。
如果实在不想写 C# 逻辑，**至少也要放一个空的 `public partial class <Key> : <基类> { }`**。

**官方生成器模板**（`addons/ModEditor/FileSystem/XWResourceCreateRoute.cs:754` 的格式串，照抄即可）：

```ini
[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="res://Prefab/TowerDefense/Character/TowerDefensePlant.tscn" id="1_base"]
[ext_resource type="Resource" path="../Config/{Key}Config.tres" id="3_config"]
[ext_resource type="PackedScene" path="../Sprite/{Key}.tscn" id="4_sprite"]

[node name="{Key}" node_paths=PackedStringArray("sprite") instance=ExtResource("1_base")]
config = ExtResource("3_config")
sprite = NodePath("SpriteGroup/TransformPoint/{Key}Sprite")
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "{中文名}"
metadata/mod_character_category = "Plant"
metadata/mod_character_config_path = "../Config/{Key}Config.tres"
metadata/mod_character_script_path = "./{Key}.tscn"
metadata/mod_character_script_binding = "CompanionOnly"
metadata/mod_character_sprite_scene = "../Sprite/{Key}.tscn"

[node name="{Key}Sprite" parent="SpriteGroup/TransformPoint" instance=ExtResource("4_sprite")]
position = Vector2(0, -30)

[editable path="SpriteGroup/TransformPoint/{Key}Sprite"]
```

DLL 侧：`public partial class <Key> : <authoredRoot 的基类> { }`（可空壳；
`IsAssignableFrom` 要求它继承**壳场景根节点的类型**，不是随便找个基类）。

### ★ 想改内置脚本里"硬编码的卡池/分类"时：换个自定义 bank，别复刻逻辑

典型案例：内置模仿者 `TowerDefensePlantImitater.Explode()` 里写死了
`packetBankData.GetCategory("White") + packetBankData.GetCategory("Original")`，
`Explode()` 又**不是 virtual** 无法覆写，而 Mod 的 `.cs` 也**不能进包**（会被判可执行文件拒收）。

⇒ 正解：**运行时注册一个自定义卡池**，把内置硬编码要取的那个分类名（这里是 `White`）
直接填成你真正想要的卡列表：

```csharp
var rm = ResourceManager.Instance;
var data = new TowerDefensePacketBankData();
data.category["White"] = 你的卡 key 列表;      // ← 填进"内置硬编码会读的那个分类名"
data.category["Original"] = new Godot.Collections.Array();
rm.TOWERDEFENSE_PACKETBANKS["你的Bank名"] = data;   // Dictionary 可写（属性是 private set，但内容可改）
```

再把角色场景的 `packetBank = "你的Bank名"` ⇒ 零逻辑复刻、零副作用、不动内置资源。
（`TowerDefenseManager.GetPacketBankData(name)` 就是从这个字典查的。）

需要"随机抽卡"时：`GetPacketBankData(bank).GetCategory("White").PickRandom()`，
再 `TowerDefenseManager.GetPacketConfig(key)`。
⚠️ **别忘了把自己的卡排除掉**，否则随机抽到自己 → 死循环。

### 卡池分类名与 `PACKET_TYPE` 数值

```
NOONE=-1, WHITE=0, GOLD=1, DIAMOND=2, COLOUR=3, STAR=4, ORIGINAL=5, ZOMBIE=6, COVER=7, GRAY=8
```
（内置模仿者卡片写的是 `type = 5` = **ORIGINAL**，不是 STAR —— 别数错。）

要进选卡/图鉴：往 `TOWERDEFENSE_PACKETBANKS["GeneralPlant"].category["<分类>"]` 追加卡 key
（check-then-add 幂等），并补 `Include` 闭包里的派生库（实测只有 `Total`）。

### 自写打包脚本的两个必踩坑（2026-09-29 实测）

1. **资源忘进包**：手写 `zipfile` 时很容易只写 `mod.json` + `Runtime/ModAssembly.dll`，
   把 `Resources/` 整个漏掉（包会小得可疑，加载期报"缺少 CharacterSprite"）。
   ⇒ 必须 `os.walk(Resources)` 全部写入。
2. **"mod.json 在根"的护栏写成 `sorted(namelist)[0]`** ⇒ **必然误报**：
   排序后 `Resources/...` 排在 `mod.json` 前面（`'R'`=82 < `'m'`=109）。
   ⇒ 用 **`z.namelist()[0]`（写入顺序）** 判断，并补一条
   "`mod.json.resources` 声明 vs 包内实际文件"的一致性断言（两边排序后逐项比对）。

---

### ★ 「Mod 植物」页签是 ModLoader 自动加的 —— 想去掉只能在运行时做（2026-09-29 定案）

**现象**：装了带卡片（`provides.Packet`）的 Mod 后，选卡界面右上角**必然**多出一个
「Mod 植物」页签，图鉴里也多一类。**`mod.json` 里没有任何开关能关掉它。**

**源码证据**：
- `addons/ModEditor/ModSystem/XWModContentCatalog.cs:107` `WithPlants(original)`：
  **深拷贝**传入卡池，再 `category["ModPlants"] = 所有 Mod 植物 Packet 的 key`。
  收集条件（`GetPackets(plants:true)`）：`characterConfig is TowerDefensePlantConfig`
  **且** `TOWERDEFENSE_CHARCATERS` 含它 **且** `CHARCTAER_SPRITE` 含它
  ⇒ 所以你必须同时 `provides` **Character + CharacterSprite + Packet** 才会被收进去。
- **调用点**：选卡界面 `TowerDefenseBattleFeaturePacketBank.SetPacketBankData()` L248
  （仅当 `packetBankType == "GeneralPlant"` 且 seedBank 是 `CHOOSE` 模式）；
  图鉴 `Almanac.cs:219`。
- `TowerDefenseBattleFeaturePacketBank.cs:250`：页签按钮是 `cardSort/CardMod`，
  `Visible = packetBankData.category.ContainsKey("ModPlants")`。

**⛔ 为什么不能"干脆不声明 `provides.Packet`"**：
`TowerDefensePacketConfig.Unlock()` → `XWModPlayerProgressService.TryPacketUnlock()`
先查 `GetContentOwner("Packet", saveKey)`：
- 非 Mod 卡（owner 空）⇒ 落到原逻辑 ⇒ **`unlockCheckList` 为空时 `return false`（判定未解锁）**
  ⇒ 卡变灰点不动；
- Mod 卡 + `unlockCheckList` 为空 ⇒ `unlocked = true` ✅（正是我们要的"开局即解锁"）。
⇒ **必须声明 `provides.Packet`。**

**运行时去掉的办法**（要"只出现在钻卡页"时）：
```csharp
// 1) 全局卡池：往目标分类追加自己的 key（check-then-add 幂等）
var gp = TowerDefenseManager.GetPacketBankData("GeneralPlant");
var arr = gp.category["Diamond"].AsGodotArray();
if (!arr.Contains(MyKey)) { arr.Add(MyKey); gp.category["Diamond"] = arr; }

// 2) 关卡内的卡池副本：从 ModPlants 摘掉自己
var pb = (TowerDefensePacketBankData)GetMember(bankFeature, "packetBankData");  // 反射
if (pb.category.ContainsKey("ModPlants")) {
    var mp = pb.category["ModPlants"].AsGodotArray();
    mp.Remove(MyKey);
    if (mp.Count > 0) pb.category["ModPlants"] = mp;   // 还有别的 Mod 卡 ⇒ 只摘自己
    else {
        pb.category.Remove("ModPlants");
        // ★ 必须手动隐藏按钮：它的 Visible 只在 SetPacketBankData() 里设过一次
        var btn = ((Node)GetMember(GetMember(bankFeature,"packetBank"), "cardSort"))
                  ?.GetNodeOrNull<Control>("CardMod");
        if (btn != null) btn.Visible = false;
    }
}
```
⚠️ **只摘自己的 key，别删别人的**（`ModPlants` 里可能还有其它 Mod 的卡）。
⚠️ 每帧跑（进关卡时 `packetBankData` 会被 `WithPlants()` 重新构造）。

**追加到目标分类不会"冲突"**：两个分类引用同一个 key，选中/取消行为一致，
只是玩家在两个页签都能看到这张卡。

### 让卡"条件不满足时不可选"的最省事做法

把 `TowerDefenseInGamePacketShow.alive` 置 `false`：
- `alive` 的 setter 会调 `ColorSet()` ⇒ **卡面变灰**；
- `Pressed()` 的守卫 `else if ((alive || allowPressWhenUnavailable) && !(pressDelayTimer > 0))`
  ⇒ 点下去**完全没反应**。
⚠️ **跳过 `select == true`（已入组）和 `@lock == true` 的卡** —— 卡入组时游戏自己会把
   `alive` 设为 false，那是正常状态，不能被你的"恢复 true"覆盖掉。
