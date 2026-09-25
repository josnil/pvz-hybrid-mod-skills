# PVZ 杂交版 Mod 工坊（手写 .pmod）

> 🖱️ **只想点鼠标改数值？** 直接看 **[`使用说明书.md`](使用说明书.md)**（图形编辑器 `mod_editor.py` 的完整教程）。
> 本文档讲的是**格式与原理**，以及脚本化改造的细节。

> 结论：**能做。** 游戏里的「PVZ Mod 编辑器」（F3）是个游戏内 GUI，我没法帮你点；
> 但它的产物 `.pmod` 本身只是一个 **zip + 根 `mod.json`**，格式我已经从
> `addons/ModEditor/ModSystem/` 的源码里完整逆出来了，所以可以直接手写生成。
> 这个目录就是成品 + 可复用的构建/校验工具链。

---

## 1. 成品

| 文件 | 说明 |
|---|---|
| **`使用说明书.md`** | **面向使用者的操作手册（先看这个）** |
| **`mod_editor.py`** | **图形编辑器 + HTTP 服务端（游戏外运行，见 §6）** |
| **`mod_editor_ui.html`** | 编辑器前端单页 |
| **`start_editor.bat`** | 编辑器启动器（双击即可） |
| `PeaOverhaul/` | Mod 工程目录（含 `mod.json` + `Resources/Projectiles/*.tres`） |
| `PeaOverhaul.pvzmodeproject` | 官方编辑器能识别的工程文件（F3 里可继续改） |
| `dist/PeaOverhaul.pmod` | 打包产物 |
| `build_pmod.py` | 构建脚本：改数值 → 生成工程 → 打包 → 安装 |
| `verify_pmod.py` | 离线校验脚本：复刻 `ModLoader` 的加载规则 |

**示例 Mod「豌豆强化 / PeaOverhaul」** 覆盖了 4 个子弹资源：

| key | 改动 | 原值 |
|---|---|---|
| `PeaDefault` | `baseDamage` 20→**60**，`penetrateNum` 3→**8**，`scale` 1→**1.6** | 未显式设置，走类默认值 |
| `SnowPea` | 同上（保留原有冰冻 Buff 事件链） | 同上 |
| `FirePea` | `baseDamage` 40→**120**，`penetrateNum`→8，`scale`→1.6 | `baseDamage = 40.0` |
| `GoldPea` | 仅 `scale`→1.6（它的伤害走 `hitTargetEventList`，不动） | `baseDamage = 0.0` |

---

## 2. `.pmod` 格式（逆向结论）

### 2.1 包结构

来自 `ModExporter.ExportFromDirectory()`：

```
PeaOverhaul.pmod            ← 就是个 zip，ZIP_DEFLATED
├── mod.json                ← 必须是【根】且【只此一个】（≤ 1 MiB）
└── Resources/Projectiles/  ← 其余条目用「工程相对路径」
    ├── PeaDefault.tres
    ├── SnowPea.tres
    ├── FirePea.tres
    └── GoldPea.tres
```

规则原文：
- `"package must contain exactly one root mod.json"`
- `"mod.json exceeds the 1 MiB limit"`
- `.uid` / `.import` / `.cs` / `.csproj` / `.sln` / `.build/` / `bin/` / `obj/` **不打进包**
  （`ModExporter.ShouldPackageProjectFile`）

### 2.2 `mod.json` 字段全表

来自 `XWModManifest.cs`（`schemaVersion` 当前为 2）：

```jsonc
{
  "schemaVersion": 2,           // 1 或 2；>2 直接抛错
  "id": "peaoverhaul",          // 空则回退文件名
  "name": "豌豆强化",
  "version": "1.0.0",
  "author": "云漫行",
  "description": "...",
  "dependencies": [ { "id": "other.mod", "version": "1.0.0" } ],
  "conflicts":    [ { "id": "xxx", "version": "1.0.0" } ],
  "provides":  { "Projectile": ["NewKey"] },   // 新增：key 必须【不存在】
  "overrides": { "Projectile": ["PeaDefault"] },// 覆盖：key 必须【已存在】
  "scripts": [],                // C# 脚本
  "runtimeAssembly": "",        // 托管程序集，包内固定路径 Runtime/ModAssembly.dll
  "runtimeEntryType": "",       // 需实现 IXWModRuntimeEntry
  "runtimeApiVersion": 0,       // 有托管代码时必须 = 1
  "runtimeAssemblyPolicy": "",  // "required" | "optional"
  "blueprints": [],
  "translations": [],
  "resources": ["Resources/Projectiles/PeaDefault.tres"]
}
```

### 2.3 路径 → (category, key) 推断表

**核心机制**：包里的文件路径决定它属于哪个资源类别，文件名（去扩展名）就是 key。
移植自 `ModLoader.InferRuntimeEntry`：

| 包内路径前缀 | category | 落地到游戏里的位置 |
|---|---|---|
| `Resources/Projectiles/` | `Projectile` | `ResourceManager.PROJECTILE_CONFIG` |
| `Resources/Maps/` | `Map` | `ResourceManager.MAPS` |
| `Resources/Cards/` | `Packet` | `ResourceManager.TOWERDEFENSE_PACKETS` |
| `Resources/PacketBank/` | `PacketBank` | `ResourceManager.TOWERDEFENSE_PACKETBANKS` |
| `Resources/LevelCatalogs/` | `Level` | `ResourceManager.LEVELS` |
| `Resources/Collectables/` | `Collectable` | `ResourceManager.COLLECTABLES` |
| `Resources/Shovels/` | `Shovel` | `ResourceManager.SHOVELS` |
| `Resources/Mowers/` | `Mower` | `ResourceManager.MOWERS` |
| `Resources/Shops/` | `Shop` | `ResourceManager.SHOPS` |
| `Resources/Survivals/` | `Survival` | `ResourceManager.SURVIVALS` |
| `Resources/Tutorials/` | `Tutorial` | `ResourceManager.TUTORIALS` |
| `Resources/NpcTalks/` | `NpcTalk` | `ResourceManager.TALKS` |
| `Resources/BGMConfigs/` | `BGM` | `ResourceManager.BGMS` |
| `Resources/ProjectileChanges/` | `ProjectileChange` | `TowerDefenseProjectileRegistry.ProjectileChangeDataDictionary` |
| `Resources/AnimationAtlasProfiles/` | `AnimationAtlas` | 内部图集档案表 |
| `Battle/Features/` | `Feature` | `TowerDefenseBattleRegistry.BattleFeatureDictionary` |
| `Battle/Processes/` | `Process` | `TowerDefenseBattleRegistry.BattleProcessDictionary` |
| `Assets/Textures/` `Assets/Images/` `Assets/Texture/` | `Texture` |（png/jpg/webp/svg/bmp/tga）|
| `Assets/Audio/` | `Audio` | `ResourceManager.AUDIOS`（wav/ogg/mp3/flac）|
| `Resources/Characters/<类>/<名>/Scene/*.tscn` | `Character` | `ResourceManager.TOWERDEFENSE_CHARCATERS` |
| `Resources/Characters/<类>/<名>/Sprite/*.tscn` | `CharacterSprite` | `ResourceManager.CHARCTAER_SPRITE` |

> ⚠️ `Resources/Tutorials/Conditions/` 和 `Resources/Tutorials/Steps/` 会被**显式排除**，
> 它们是 Tutorial 的伴随依赖，不单独注册。

### 2.4 三条会让 Mod 加载失败的硬规则

来自 `XWModRuntimeRegistry.RegisterCore`：

1. **`overrides` 的目标必须已存在** —— 否则报
   `overrides target is missing: <category>/<key>; declare it under provides instead`
2. **`provides` 不能和内置/已注册冲突** —— 否则报
   `provides collision with built-in runtime value: ...; declare it under overrides to replace it`
3. **同一 category/key 不能出现两份文件** —— 否则报
   `ambiguous automatic runtime key: ...`

另外：包内出现**未声明的可执行文件**会被拦截
（`blocked executable package file`），只有 `Runtime/ModAssembly.dll` 与
`Runtime/Dependencies/*` 例外。

### 2.5 覆盖资源的 `.tres` 注意事项

- **必须剥掉 `[gd_resource]` 行里的 `uid="uid://..."`**，否则和内置资源 UID 撞车
  （`build_pmod.py:strip_header_uid` 已处理）。
- `[ext_resource]` 的 `uid` 和 `path` 要**原样保留**，它们指向游戏内置子资源
  （场景、脚本、粒子等），正式版里都存在。
- `script_class="TowerDefenseProjectileConfig"` 这种全局类名要保留，靠它绑定 C# 类型。
- **只写想改的字段**：没写的字段回到类的默认值。所以覆盖包要以**原版 `.tres` 为基底**改，
  不能从零写，否则会静默丢字段。

### 2.6 托管代码 Mod（`Runtime/ModAssembly.dll`）—— 已实测可用

**什么时候才需要**：纯数据做不到的效果 —— 概率触发、延时改发射模式、真随机、跨组件联动，
以及**运行期改游戏自身的 UI/状态**。样板 `超级机枪射手` 三件事都是：
① 每次攻击 10% 概率、5 秒内倾泻约 300 颗豌豆；
② **把 Mod 卡补进共享卡库 `GeneralPlant.Gold`** ⇒ 选卡界面里能选到
   （选卡界面按 `packetBankType` 取库，默认就是 `GeneralPlant`；
   不补则 Mod 卡只存在于图鉴 —— 图鉴由 `XWModContentCatalog.WithPlants()` 深拷贝
   `GeneralPlant` 并把 Mod 植物单列成 `ModPlants`，纯数据改不动）；
③ 兜底再补一次图鉴那份拷贝。②③ 详解见 `植物Mod-超级机枪射手.md` §3.2.2 / §3.5 / §3.6。

**四条硬约束（违反 = 整包被拒，不是「不生效」）**：

| 字段/项 | 值 | 出处 |
|---|---|---|
| `runtimeAssembly` | 只能是**字面量** `"Runtime/ModAssembly.dll"` | ModLoader.cs:329-333 |
| `runtimeApiVersion` | 必须**恰好** `1` | `XWModCharacterCompanionRuntime` |
| `runtimeAssemblyPolicy` | `"optional"`（加载失败不连坐整包）或 `"required"` | ModLoader.cs:1606-1609 |
| `runtimeEntryType` | 入口类 FullName，**无命名空间** ⇒ 就是类名；必须 public + 公开无参构造 + 非嵌套 | `TryInitializeRuntimeEntry` |

**另外三条踩过的坑**：

1. ⚠️ 入口的 `Initialize` / `OnAllModsLoaded` / `Shutdown` **一律不许抛异常** ——
   `TryInitializeRuntimeEntry` 失败会**无条件整包回滚**（ModLoader.cs:667-671），
   **不受 `runtimeAssemblyPolicy` 保护**。
2. ⚠️ `Runtime/` 下**只许有 `ModAssembly.dll`**。`IsExecutablePackageFile` 认
   `.dll/.exe/.bat/.cmd/.ps1/.cs/.gd`，多一个就抛 `undeclared executable package file`
   （ModLoader.cs:343-346）。`.pdb` 不在其中，但同名的 `Runtime/ModAssembly.pdb` 会被静默跳过，
   建议干脆别放。
3. ⚠️ `Runtime/ModAssembly.dll` **不是可推导资源**（`InferRuntimeEntry` → false，靠
   `IsDeclaredRuntimeAssembly` 放行），但**必须列进 `manifest.resources`**，且遵守
   `SyncProject` 的规范序（OrdinalIgnoreCase 升序：`Resources/…` 在前、`Runtime/…` 在后），
   否则编辑器一打开工程就重写 `mod.json`。

**离线验证（不启动游戏）**：`runtime_src_plant/check_gates_plant.cs` + `runtime_src/check_entry.cs`
用 `dotnet run --file` **反射直调游戏程序集的真函数**（`ModLoader.InferRuntimeEntry`、
`XWModManifest.Load`、`ValidateDeclaredPackageExecutables`、`XWModManifestSyncService.SyncProject`）。
编译 `dotnet build -c Release`，产物用固定 `<Deterministic>true</Deterministic>` + 关 pdb 保证字节可重现。

---

## 3. 用法

```bash
# 打包（会同时安装到游戏 Mods 目录）
python build_pmod.py

# 离线校验
python verify_pmod.py dist/PeaOverhaul.pmod
python verify_pmod.py dist/PeaOverhaul.pmod --json report.json     # 输出机器可读报告
```

安装位置：`%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\PeaOverhaul.pmod`

### 游戏内怎么启用

1. 启动游戏 → 按 **F3** 打开「PVZ Mod 编辑器」
2. 左侧/下方 **Mod 工具**面板 → **导入 Mod** 或直接 **启用 Mod**
3. 点 **应用已安装 Mod 到当前游戏**（提示：`状态已保存；请使用"重新应用 Mod"，或重启游戏后生效`）
4. 进关卡看豌豆——应该明显变大、更疼、能穿透更多

> 卸载：删掉 `Mods\PeaOverhaul.pmod`，或在「Mod 工具」里点 **停用**。
> 再点一次 F3 关闭编辑器。

---

## 4. 想改成别的 Mod

改 `build_pmod.py` 顶部的 `OVERRIDES` 列表即可，每项：

```python
{
  "key": "PeaDefault",                                  # 必须是真实存在的 key
  "src": r"...\Asset\Config\Projectile\Pea\PeaDefault.tres",  # 原版文件当基底
  "patch": { "baseDamage": "60.0", "scale": "Vector2(1.6, 1.6)" },  # 改哪个字段
  "note": "说明",
}
```

换个类别就换 `src` 的目录（例：`Asset/Config/Map/`、`Asset/Config/Collectable/`），
并同步改 `mod.json` 里 `overrides` 的类别名。**key 一定先查注册表 JSON**：

```
Asset/Config/Projectile/ProjectileResource.json   → 子弹键名
Asset/Config/Map/MapResource.json                 → 地图
Asset/Config/Character/CharacterResource.json     → 角色
Asset/Config/Level/LevelResource.json             → 关卡
Asset/Config/Shop/ShopResource.json               → 商店
...
```

`verify_pmod.py` 会自动拿这张表核对 `overrides` 的 key 是否真实存在。

---

## 5. 诚实的边界

| 事情 | 状态 |
|---|---|
| 手写 `.pmod`、打包、装到 Mods 目录 | ✅ 已完成，22 项校验通过 |
| 静态校验（结构/路径安全/键存在性/UID/引用存在性） | ✅ 完成 |
| **游戏内实际生效** | ⚠️ **需要你启动游戏确认**。我无法在游戏进程里点 F3、点启用。 |
| 驱动 F3 那个 GUI 本体 | ❌ 我做不了，它是游戏内渲染的窗口 |
| 托管代码 Mod（`Runtime/ModAssembly.dll`） | ✅ **已完成**（2026-09-19；超级机枪射手的「10% 概率大招」就是靠它做的）。四条硬约束见 §2.6，完整配方见 `植物Mod-超级机枪射手.md` §3 |
| 蓝图 / 状态机 / 2D 场景类 Mod | ⚡ 格式已摸清（`Resources/Blueprints`、`Resources/StateMachines`…），但资源结构复杂，需要编辑器生成才稳妥 |

---

## 6. 图形编辑器 `mod_editor.py`（游戏外运行）

上面 §3/§4 是「改代码里的常量再跑脚本」。**`mod_editor.py` 把同一套格式搬到了浏览器里**，
不用碰代码也能改数值。它和游戏内 F3 那个「PVZ Mod 编辑器」是两回事——这个是独立进程。

```
start_editor.bat                      # 双击即可（自动开浏览器，默认 http://127.0.0.1:8765/）
start_editor.bat --build              # 不开界面，直接按 mod_project.json 打包+安装
start_editor.bat --unpack "D:\别的解包目录"
```

界面三栏：**左**类别 + 键搜索 · **中**按 `[ExportGroup]` 分组的字段表单 · **右**Mod 信息 /
工程条目 / 产物预览 / 校验结果 / 已装 Mod，底部是日志。改动会实时渲染出 `.tres` 给你看，
点「构建并安装」直接落到游戏 Mods 目录。

### 它为什么能自动列出「能改什么」

工具链是**全自动推导**的，不靠手工维护字段表：

```
Asset/Config/<类>/<类>Resource.json   注册表 → 该类别的真实键名（overrides 只能用真实键）
        ↓ key
      uid  →  .tres / .res 真身       （音频走 .import 的 source_file 反查）
        ↓ 文件头 ext_resource
     C# 配置类 (.cs)                  → 解析 [Export] / [ExportGroup] / [ExportCategory]
        ↓
   类型感知表单：bool→勾选框 · int/float→数字（带 Range 的带 min/max/step）
                string→文本框 · Vector2/2I→双数字框 · Color→色板+alpha
                Enum → 下拉 · 枚举字段 → 展开成 下拉（含显式值）
                Array/Dictionary/资源引用 → 只读（保留原值）
```

覆盖 12 个类别：子弹 / 地图 / 收集物 / 铲子 / 小推车 / 商店 / 生存 / 教程 / NPC对话 /
背景音乐 / 音效 / 子弹变化。另有 **7 个类别明确不支持并说明原因**（关卡、卡包、角色、
动画图集、战斗 Feature/Process、纹理），不静默出错。

### 三种编辑动作

| 动作 | 效果 | 产物变化 |
|---|---|---|
| 改值 | 把该字段写进 `.tres` | 覆盖该 key |
| **↺ 还原** | 撤掉这次改动，回到原版 `.tres` 的写法 | — |
| **⌀ 用默认** | 从 `.tres` 里**删掉**这个属性行，回落到 C# 类默认值 | 覆盖该 key |
| **复制为新键** | 以当前键为基底，另存成一个新 key | 走 `provides`（新增） |

### 两条硬规则前端也会拦

- 覆盖一个**不存在**的键 → 渲染阶段就报「找不到原版资源」
- 新增一个**已存在**的键（该用 overrides）→ 校验报 `provide.exists`

### 二进制条目（音效 / 纹理）

音效这类不是 `.tres`，只能整文件替换。界面会给一个**拖拽区**：把 `.ogg/.wav` 拖进去
（或点击选择），文件会上传到 `.cache/uploads/`，工程里只存路径。
扩展名和原版不一致时会**黄色警告**（Godot 按扩展名挑 loader，容易加载不了）。

### 工程文件

`mod_project.json` 存 meta + 条目（`category / key / edits / unset / mode / sourceFile`）。
界面上每次改动会 400ms 防抖自动保存，所以关掉浏览器不丢。

### 新增的接口

| 路由 | 说明 |
|---|---|
| `GET /api/state` | 路径、类别表、已装 Mod、当前工程 |
| `GET /api/keys?category=` | 该类别的键 + uid + 原版文件 + 是否缺文件 |
| `GET /api/resource?category=&key=` | 字段全表（类型/分组/原值/默认值/枚举选项） |
| `GET/POST /api/project` | 读写 `mod_project.json` |
| `GET/POST /api/preview` | 只渲染不落盘，返回每个 `.tres` 的文本 |
| `POST /api/build` | 打包（+可选安装），附完整校验报告 |
| `POST /api/upload` | 上传替换文件（base64 → 落盘） |
| `POST /api/uninstall` · `GET /api/installed` | 卸载 / 列举 Mods |
| `POST /api/reindex` · `POST /api/reveal` | 重建 uid 索引 / 打开资源管理器 |

### ⚠️ 前端布局不变式（改 `mod_editor_ui.html` 前必读）

左栏用 flex 按 **38% / 62%** 分配「资源类别」和「键」两块，右栏整体可滚、各区块**不收缩**。
这几条不是审美选择，是踩过坑之后立下的规矩：

1. **禁止在 `height:auto` 的父元素上用百分比 `max-height`。**
   最初 `#cats` 写的是内联 `style="max-height:38%"`，而它的父 `.sect` 没有 flex 声明
   → 高度由内容撑（`auto`）→ 百分比无法解析 → 被当成 `none` → 类别块长到全内容高
   （19 项 ≈ 555px，整块 516~587px）。等父块高度被 flex 固化后 38% 才生效把**列表**裁短，
   但**父块**已经占着 516~587px 不放，留给「键」区的只剩零头。
2. **`flex:1` 等价于 `flex:1 1 0%`（basis 0%），在负剩余空间里救不了场。**
   于是「键」区的 `.sect` 在窗口矮的时候塌成 **1px**，里面的搜索框（位置固定在区块标题下方
   ≈28px 处）直接溢出 `#left` 的下边界、被底部输出栏盖住 —— `elementFromPoint` 打到的是
   输出栏，**鼠标点不进去，键盘自然也输不了**。
   触发条件：浏览器可视高度 **≲800px**。（所以 1440×900 下测是绿的，笔记本 768 就中招。）
3. **改法**：`#left>.sect.cats{flex:0 1 38%}` / `#left>.sect.grow{flex:1 1 62%}`
   —— 百分比放在 **`flex-basis`** 上，它相对 `#left` 的高度，而 `#left` 的高度由
   `main{flex:1}` 拉伸决定，是**确定值**，能正常解析。
4. **右栏同理**：5 个区块总高在窄窗口下必然超出，若允许互相压缩，
   底部区块塌成 1px、上方区块内容溢到兄弟区块底下 —— 「构建并安装」按钮就是这么被盖住点不到的。
   所以改成 `#right{overflow-y:auto}` + `#right>.sect{flex:0 0 auto}`（都不收缩），
   预览区只在有多余空间时撑开（`#right>.sect.grow{flex:1 0 auto}` + `body{max-height:32vh}`）。

> 教训：**`element.click()` 这类合成点击会绕过命中检测**，元素被盖住照样"点得动"。
> 所以 `.cache/verify_ui.js` 那种全 JS 合成点击的用例**测不出这类布局 Bug**。
> 凡是涉及「看不看得见 / 点不点得到」的验收，一律走 **CDP `Input.dispatchMouseEvent`
> 真鼠标事件 + `document.elementFromPoint` 命中检测**，且必须**跨多个视口高度**跑
> —— 见 `.cache/verify_search_flow.js` 与 `.cache/shot_ab.js`。

---

## 7. 验收脚本

| 脚本 | 覆盖 | 结果 |
|---|---|---|
| `verify_pmod.py` | 离线复刻 ModLoader 规则 | PeaOverhaul 22 项 0 FAIL |
| `.cache/test_api2.py` | 接口 + 端到端 + 两条硬规则 + 二进制替换 + 新增键 | **133 项 0 FAIL** |
| `.cache/verify_ui.js` | **真实浏览器**（系统 Edge + CDP）点完整个 UI 流程 | **51 项 0 FAIL**（连跑两次一致） |
| `.cache/verify_search_flow.js` | **真鼠标/真键盘**（CDP `Input.*`）在 **10 档视口高度** 900→440 下走「点类别→搜索框→输入→点键」 | **70 项 0 FAIL** |
| `.cache/shot_ab.js` | 布局 Bug 的 A/B 取证（注入旧 CSS 复现 → 移除看修复），落两张截图 | BEFORE 命中=false / AFTER 命中=true |

`verify_ui.js` 不需要装 Playwright：Node 22 自带 `WebSocket`，直接连本机 Edge 的
`--remote-debugging-port`，在页面里真点真改真构建（选类别→搜键→改字段→看预览→
⌀用默认→↺还原→构建并安装→切二进制类别→无横向溢出），最后截图到 `.cache/ui_shot.png`。

```bash
node .cache/verify_ui.js                                   # 需先起服务端
python .cache/test_api2.py                                 # 需先起服务端
```

> ⚠️ 改过 `verify_pmod.py` 之后要**重启服务端**：`build_package` 里 `import verify_pmod`
> 只生效一次，模块会被缓存。

