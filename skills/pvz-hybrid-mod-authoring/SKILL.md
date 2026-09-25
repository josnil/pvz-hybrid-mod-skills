---
name: pvz-hybrid-mod-authoring
description: 手写/生成《植物大战僵尸杂交版》(Godot 4 + C#) 的 .pmod Mod 包——覆盖内置资源（子弹/地图/角色/关卡/商店/收集物/铲子/推车/生存/教程/NPC对话/BGM/音频/纹理/图集）或做托管代码 Mod。也包含游戏外运行的图形编辑器 mod_editor.py（改数值/打包/校验，免写代码），以及「从单张角色截图制作角色贴图」的抠像 + 逐帧动画流程（透明底、待机/射击、锚点对齐）。当用户要求「做个 Mod」「改游戏资源数值」「覆盖子弹伤害」「打包 pmod」「写 mod.json」「打开 Mod 编辑器」「按这张图做角色贴图」「做待机/射击动画」或提到 .pmod / mod.json / ModLoader / XWModManifest / ModEditor / mod_editor / Mods 目录 / overrides / provides / 角色贴图 / 序列帧 / 图集 / 透明底 时使用。
agent_created: true
---

# 手写 PvZ 杂交版 .pmod Mod

## 前提认知（别搞错）

- 游戏内置的 **「PVZ Mod 编辑器」是个游戏内 GUI**，由 **F3** 唤起（autoload `ModEditorManager`），
  完整打包在 `addons/ModEditor/`（3582 文件 / 574 cs）。**AI 无法驱动它**。
- 但它的产物 `.pmod` **只是一个 zip + 根 `mod.json`**，可以纯脚本手写生成。这是本技能的核心。

## 关键路径（按需查证）

| 用途 | 路径 |
|---|---|
| 源码真相 | `D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28\addons\ModEditor\ModSystem\` |
| 包格式 | `ModExporter.cs`（打包）/ `ModLoader.cs`（加载，71KB）|
| 清单字段 | `XWModManifest.cs`（schemaVersion=2）|
| 类别派发 | `XWModRuntimeRegistry.cs` → `TrySetRuntimeValue` |
| 路径→类别推断 | `ModLoader.InferRuntimeEntry` |
| 工程目录约定 | `XWModProjectLayout.cs`（全部 `Resources/*` 目录名）|
| 编辑器面板 | `ModEditorPanel.cs`、`Tools/GUI/XWModToolsPanel.cs` |
| **可覆盖键名** | `Asset\Config\<类>\<类>Resource.json`（key→uid），例：`Projectile\ProjectileResource.json` |
| 原版资源基底 | `Asset\Config\Projectile\*`、`Asset\Config\Map\*` …（**必须拿来当基底**）|
| 用户 Mod 安装目录 | `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\` |
| 实况日志 | 同目录 `PVZHE_Logs\`、`ModEditor\editor_settings.cfg` |

现成工具链（可直接复用/改写）：
`D:\zzz\pvzHE\解包\植物大战僵尸杂交版\Asset\Anime\Character\Zombie\.workbuddy\ModWorkspace\`
→ `build_pmod.py`（构建+打包+安装）、`verify_pmod.py`（离线校验，22 项）、`README.md`（格式全表）

成套样板（连生成器 + 离线闸门 + 幂等校验一起抄，比从零写快得多）：
| 样板 | 类型 | 看点 |
|---|---|---|
| `build_plant_super_gatling.py` + `runtime_src_plant/` | 植物 + 玩法托管插件 | 概率触发/连射、进图鉴与选卡界面、血量、可直接种空地 |
| `build_zombie_disco_pult.py` + `runtime_src_zombie/` | 僵尸 + 投掷替换托管插件 | 复用内置 `.cs`、僵尸卡入库、投掷单位替换 |
| `build_vampire_pool.py` + `runtime_src/` | 地图 | 换战斗背景贴图（运行期改 `Sprite2D.Texture`） |

每个样板都配三件套：生成器自带 `self_check()`、`runtime_src_*/check_gates_*.cs`（反射直调真函数，
**两份游戏构建各跑一遍**）、`.cache/check_idempotent_*.py`（3 连跑字节稳定 + 增量清理 + 镜像一致），
以及一个只读收尾核对脚本（`.cache/final_report_*.py`）。

## 包结构

```
Xxx.pmod                          # zip, ZIP_DEFLATED
├── mod.json                      # 必须【根】且【唯一】，≤ 1 MiB
├── Resources/Projectiles/A.tres  # 路径前缀决定类别，文件名=key
└── Runtime/ModAssembly.dll       # 只有托管插件才需要；路径是硬编码字面量，见「托管代码 Mod」节
```

打包时**排除**：`.uid` `.import` `.cs` `.csproj` `.sln` `.build/` `bin/` `obj/`
（对应 `ModExporter.ShouldPackageProjectFile`）。
⚠️ `.cs` 被排除、但 `IsExecutablePackageFile` **认**它 ⇒ 包内**绝不能**有 `.cs`，否则整包拒收。

## ⚠️ 两种形态：`.pmod`（游戏加载） vs 工程目录（编辑器）——最容易白忙一场的地方

游戏侧编辑器 `F3` → Mod 工具 建工程后，会在 `user://Mods/` 下产出**文件夹**：

```
user://Mods/新地图-1/
    新地图-1.pvzmodeproject      # 工程元数据：Name/Version/Author/Description/ExportDirectory/GameDirectory/CreatedDate/LastModifiedDate
    Scenes/ Scripts/ Battle/ Resources/… Assets/ Localization/   # 72 个标准空目录
```

**这个文件夹游戏根本不加载。** 判据（`ModSystem/XWModManager.cs`）：

```csharp
Directory.EnumerateFiles(_modsDirectory, "*.pmod", SearchOption.TopDirectoryOnly)
```

- 只认 **`Mods/*.pmod`**，**不递归** → 文件夹形态加载不到，它只是「工程」；
  点「导出」时才 `ModProject.ExportAsync` → `ModExporter.ExportFromDirectory` 压成 `.pmod`。
- **`Mods/enabled_mods.json` 不存在 ⇒ `LoadEnabledIds()` 返回空 ⇒ 一个 mod 都不加载**
  （`XWModManager.EnabledStateFileName = "enabled_mods.json"`，内容就是 `["<manifest.id>"]`，按 id 不按文件名）。
  症状是「Mod 装了但游戏里没有」——第一件要查的就是它，别急着怀疑包结构。
- 所以**要交付就交付 `.pmod`**；文件夹是给「还想用编辑器继续改」的人用的附加物。

要生成「编辑器认可」的工程目录（照抄游戏侧产物）：

1. `XWModProjectLayout.StandardDirectories` 的 **72 个**子目录（顺序无所谓，集合要对）；
2. `<SanitizeDirectoryName(工程名)>.pvzmodeproject`，键序 = `ModProjectSerializeHandler`；
3. 工程内 `mod.json` = `XWModManifest` 的 **18 键全集**（`XWModManifestSerializeHandler` 顺序）；
4. 资源按标准目录放（地图放 `Resources/Maps/`）。
5. **三处名字保持一致**（工程目录名 / `.pvzmodeproject` 名 / `.pmod` 名）→ 编辑器再「导出」会覆盖同一个
   `.pmod`，不会出现两份同 `id` 互相打架的 mod。

字节风格（实测，`.cache/check_project_folder.py` 会断言）：

| 文件 | 换行 | 非 ASCII | 结尾 |
|---|---|---|---|
| `.pvzmodeproject`（`File.WriteAllText` 路径） | **CRLF** | `\uXXXX` **大写 HEX 转义** | 无换行 |
| `mod.json`（`ModExporter` 打进球 zip 的） | LF | 原样中文 | 无换行 |

时间用 .NET 'O' 格式：`2026-09-16T19:54:37.0784110+08:00`（**7 位小数** + 冒号时区）。
想让生成脚本幂等，就**保留已存在的时间戳**，别每次写 `now`。

> `SyncProject` 陷阱：工程目录每次被打开/保存都会 `XWModManifestSyncService.SyncProject` 重扫文件并
> 重写 `mod.json` 的 `resources`。若你的 `resources` 与扫描结果不一致，编辑器一打开就把你的清单改掉。
> 另外：**空工程不会生成 `mod.json`**（集合无变化 → 不落盘），所以 `新地图-1/` 里根本没有 `mod.json`。

## mod.json 最小可用（纯资源 Mod）

```json
{
  "schemaVersion": 2,
  "id": "peaoverhaul",
  "name": "豌豆强化",
  "version": "1.0.0",
  "author": "云漫行",
  "description": "...",
  "dependencies": [], "conflicts": [],
  "provides": {},
  "overrides": { "Projectile": ["PeaDefault", "SnowPea"] },
  "scripts": [], "runtimeAssembly": "", "runtimeEntryType": "",
  "runtimeApiVersion": 0, "runtimeAssemblyPolicy": "",
  "blueprints": [], "translations": [],
  "resources": ["Resources/Projectiles/PeaDefault.tres"]
}
```

## 路径前缀 → (category, key) 全表

移植自 `ModLoader.InferRuntimeEntry`（扩展名限 `.tres`/`.res`）：

| 前缀 | category | 落地 |
|---|---|---|
| `Resources/Projectiles/` | Projectile | `ResourceManager.PROJECTILE_CONFIG` |
| `Resources/Maps/` | Map | `.MAPS` |
| `Resources/Cards/` | Packet | `.TOWERDEFENSE_PACKETS` |
| `Resources/PacketBank/` | PacketBank | `.TOWERDEFENSE_PACKETBANKS` |
| `Resources/LevelCatalogs/` | Level | `.LEVELS` |
| `Resources/Collectables/` | Collectable | `.COLLECTABLES` |
| `Resources/Shovels/` | Shovel | `.SHOVELS` |
| `Resources/Mowers/` | Mower | `.MOWERS` |
| `Resources/Shops/` | Shop | `.SHOPS` |
| `Resources/Survivals/` | Survival | `.SURVIVALS` |
| `Resources/Tutorials/` | Tutorial | `.TUTORIALS` |
| `Resources/NpcTalks/` | NpcTalk | `.TALKS` |
| `Resources/BGMConfigs/` | BGM | `.BGMS` |
| `Resources/ProjectileChanges/` | ProjectileChange | `TowerDefenseProjectileRegistry.ProjectileChangeDataDictionary` |
| `Resources/AnimationAtlasProfiles/` | AnimationAtlas | 图集档案表 |
| `Battle/Features/` | Feature | `TowerDefenseBattleRegistry.BattleFeatureDictionary` |
| `Battle/Processes/` | Process | `.BattleProcessDictionary` |
| `Assets/Textures|Images|Texture/` | Texture | png/jpg/webp/svg/bmp/tga |
| `Assets/Audio/` | Audio | `.AUDIOS`，wav/ogg/mp3/flac |
| `Resources/Characters/<类>/<名>/Scene/*.tscn` | Character | `.TOWERDEFENSE_CHARCATERS` |
| `Resources/Characters/<类>/<名>/Sprite/*.tscn` | CharacterSprite | `.CHARCTAER_SPRITE` |

⚠️ `Resources/Tutorials/Conditions/` 与 `Resources/Tutorials/Steps/` **被显式排除**（伴随依赖）。

## 铁律（违反就加载失败）

1. **`overrides` 的 key 必须已存在** → 否则 `overrides target is missing: cat/key`
2. **`provides` 的 key 必须不存在** → 否则 `provides collision with built-in runtime value`
3. **同 category/key 不许两份文件** → 否则 `ambiguous automatic runtime key`
4. **未声明的可执行文件被拦** → `blocked executable package file`；仅 `Runtime/ModAssembly.dll`
   和 `Runtime/Dependencies/*` 例外
5. **覆盖 `.tres` 必须剥掉 `[gd_resource]` 行的自身 `uid=`**，否则撞内置 UID；
   但 `[ext_resource]` 的 `uid` + `path` **必须原样保留**
6. **必须以原版 `.tres` 为基底改**，不能从零写——未写的字段会回到类默认值，从零写会静默丢字段
7. **生成脚本要「字节幂等」**：`zipfile.write()` 会把文件 mtime 写进条目头 → 每次重跑产物字节都变。
   用固定时间戳的 `ZipInfo` + `writestr()`（如 `ZipInfo(rel, (2026,1,1,0,0,0))`）让 `.pmod` 内容确定即字节确定；
   时间戳类字段（工程 CreatedDate 等）则**读旧值保留**，不要每次写 `now`。
   ⚠️ **隐藏文件不要打进包** —— 收集条目时按 `basename.startswith(".")` 过滤。
8. **验收时判定退出码别用 `cmd; echo "exit=$?"` 里夹 `$(...)`** —— 命令替换先执行会覆盖 `$?`，
   把失败报成 0。要么 `e=$?` 先存，要么用 Python `subprocess` 跑。
9. ⚠️⚠️ **生成器别用 `shutil.rmtree`，也别用「整目录删掉重建」的写法**（WorkBuddy 本机实测）：
   - `shutil.rmtree` 被劫持成 `_safe_shutil_rmtree` → 先「丢回收站」，失败即 fail-closed 抛
     `OSError: SHFileOperationW 失败: 0x2` → 生成器中断、**exit 1**。
     而且是**间歇性**的（同一目标第一次失败、第二次成功），靠重试绕不过去。
   - 换成手写「逐文件 `os.remove` + `os.rmdir`」不会抛了，但**单次删除约 0.6 s**：
     实测删 72 个空目录 **48 s**、一次构建 **75 s**；3 连跑的幂等校验（~225 s）
     会被工具超时 **SIGTERM 杀掉且输出为空** —— 看起来像"脚本根本没跑"，极易误判。
   - ⇒ 一律改成**增量**：`sweep_stale_files(root, keep)` 就地写 + 只删「这次不再产出」的文件；
     `sync_tree(src, dst, marker)` **按字节比对**只写变化的文件，再删 src 里没有的文件与空目录。
     实测 **75 s → 0.7 s**；重跑是「写 0 / 删 0」。
   - 镜像目录（`Mods/<工程名>/`）的归属判定：不存在 / 带标记（用**工程文件**，别用隐藏文件）/
     **零文件的空壳** → 归我们；其它一律跳过不动。隐藏文件当标记会「被增量清理删掉→再写」来回抖动，
     而且标记一丢就**永久静默跳过**（用户以为更新了，其实镜像还是旧的）。

## 标准流程

1. **查键**：读 `Asset\Config\<类>\<类>Resource.json` 拿真实 key（键就是里面每个 JSON key）
2. **拿基底**：读解包里的原版 `.tres`
3. **剥 uid**：只删 `[gd_resource ... uid="..."]` 里的 uid，保留 `ext_resource`
4. **改字段**：在 `[resource]` 段内替换/追加 `prop = value`
5. **打包**：`mod.json` 写在第 0 个 zip 条目
6. **装到** `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\`
7. **离线校验**：跑 `verify_pmod.py`（结构 / 路径安全 / 键存在性 / UID / ext_resource 存在性）
8. **交用户游戏内确认**：F3 → Mod 工具 → 启用 → **应用已安装 Mod 到当前游戏**
   （提示文案：「状态已保存；请使用"重新应用 Mod"，或重启游戏后生效」）

## 常见字段速查（TowerDefenseProjectileConfig）

`baseDamage` / `penetrateNum` / `scale`(Vector2，直接喂 `projectileSprite.Scale`) /
`size`(只影响影子) / `catapultHeight` / `collisionFlags` / `damageFlags` / `hitBody` /
`useRange` + `rangeSize` + `rangeType`("Default"|"Bomb") / `hitTargetEventList` /
`hitGroundEventList` / `splatScene` / `splatAudio` / `behaviorIds` + `behaviors`

## Map 类地图（`TowerDefenseMapConfig`）——比其他类别绕，先读这段

类别名 `Map`（`CategoryMatches("Map","Maps")`）→ 运行时落到 **`ResourceManager.Instance.MAPS[key]`**。
包内路径 `Resources/Maps/<Key>.tres`。**新地图必须走 `provides`**（`MAPS` 里没有这个 key）。
参考 `Asset/Config/Map/**/*.tres`；水池样板 = `Backyard/Config/BackyardMapBackyard.tres`。

### 字段（`Registry/Battle/Feature/Map/Resource/TowerDefenseMapConfig.cs`）
`translate` / `dayNightSwitching`(存"切过去的地图 key"，如 `"BackyardNight"`) /
`mapTexturePath` / `mapScenePath` / `mapSize`(默认 `(1400,600)`) / `mapOffset` /
`plantOffset`(默认 50) / `gridNum`(默认 `Vector2i(9,5)`) / `gridBeginPos`(默认 `(256,45)`) /
`gridSize`(默认 `(80,98)`) / `edge`(默认 `Vector4(200,0,1100,576)`，`edge.Z` = 房子侧边界) /
`cellConfig` / `lineUse` / `isNight` / `useSunFall`(默认 **true**，夜晚图常写 false) /
`enableBattleZoom` / `maximumFps` / `specialRules`

`TryValidateRuntime()` 的硬约束：`gridNum` 每维 **1..50**；`lineUse` 每项必须 **≤ gridNum.Y**；
每个 `cellConfig.pos` 必须 z≥x、w≥y 且整体落在 `1..gridNum` 内；`gridType` 不能为 null；
`gridSize`/`mapSize` 必须有限且为正；`edge` 必须 right>left 且 bottom>top；`specialRules` 的 `id` 不得重复。

### 坐标：`pos = Vector4i(x1, y1, x2, y2)` = (列起, 行起, 列止, 行止)，**1-based 闭区间**
由编辑器自身代码确证 —— `XWMapVisualResourceEditor.ToCellConfigPos(Rect2I)`：
`Vector4i(sel.Pos.X+1, sel.Pos.Y+1, sel.Pos.X+sel.Size.X, sel.Pos.Y+sel.Size.Y)`
（编辑器网格是 0-based，写进 tres 时 +1）。**x 轴 = 列(≤gridNum.X)，y 轴 = 行(≤gridNum.Y)**。
交叉验证：后院图 `gridNum=Vector2i(9,6)`、整盘基底 `Vector4i(1,1,9,6)`、水池 `Vector4i(1,3,9,4)`。

### ⚠️ 三个必踩的坑

1. **`ElementFlags` 不是地形**，是 `ELEMENT_SYSTEM` 位标志 `{ICE=1, FIRE=2, DAY=4, NIGHT=8}`，
   由 `SleepComponent` 消费（`(cell.elementFlags & 8)==0` → 白天睡；`& 4` → 夜晚睡）。
   吸血鬼屋就是拿它做「昼夜元素棋盘」（基底 8，第 2/4/6/8 列与第 2/4 行是 4，8 个交叉点回到 8）。
2. **水域走 `gridType`（`PLANTGRIDTYPE`）**：`NOONE=0, SOIL=1, GROUND=2, WATER=3, AIR=4, LILYPAD=5…`
   普通草坪 **不写** `gridType`（类默认 `[GROUND, AIR]`）；水池写 `gridType = Array[int]([3, 4])`（照抄后院）。
   编辑器刷子默认 `[2, 4]`。**`gridType` 缺省≠null**，不写也能过校验。
3. **`GetEffectiveCellConfig(x,y)` 是「后匹配覆盖」，且不 break**：
   一条 cellConfig 同时携带 `gridType` 和 `ElementFlags`，**后写的把两样一起替换**。
   → 往已有元素棋盘上盖水域时，**不能只追加一条矩形**，否则覆盖区的 `ElementFlags` 被清 0、元素特性全丢。
   正确做法：给**完全落在水域内**的原有条目**就地补 `gridType`**，再按元素分区补新条目；
   配合逐格仿真（复刻上面那个 last-wins 循环）自检，详见 `.workbuddy/ModWorkspace/build_map_vampire_pool.py`。

### ⚠️ 几何：加行不要只看 `gridNum`

**逻辑地图空间 = `TowerDefenseMapConfig.mapSize`，类默认 `(1400, 600)`** —— 这是能画出来的唯一区域。
三条独立路径都把它当硬边界（全部来自 V0.28 运行时，不是编辑器）：

| # | 证据 | 结论 |
|---|---|---|
| ① | `TowerDefenseCameraControl.ClampCameraToMap()`：`camera.GlobalPosition.Y = ClampCameraAxis(y, 0f, size.Y, visibleY)`，且 `ApplySize()` 里 `downRightMarker.GlobalPosition = size`（`size = mapConfig.mapSize`，`Test/Chapter7MapCameraBoundsRuntimeTest.cs` 有断言） | **相机垂直钳在 y ∈ [0, mapSize.Y]** |
| ② | `TowerDefenseBattleFeatureMap.BuildProjectileBoundaryRect()` = `Rect2((-100, 0), mapSize + (200, 0))` | **子弹边界**也是 y ∈ [0, mapSize.Y] |
| ③ | `TowerDefenseManager.cs:1897`：`bottom = gridBeginPos.Y + gridNum.Y * gridSize.Y` | **网格下沿公式** |

所以**任何一行超出 `mapSize.Y` 都会掉到相机与子弹边界之外**。标准 5 行草坪：
`gridBeginPos.Y(75) + 5 × gridSize.Y(98) = 565 ≤ 600` ✓ —— 所以原版地图都不用操心。
一旦加行就要重算，并把 `gridBeginPos.Y` 压回 `mapSize.Y − 行数 × gridSize.Y` 之内
（`gridSize` 默认 `(80, 98)`；`gridBeginPos` 默认 `(256, 45)`，多数地图写 `(260, 75)`）。

三种收尾（改完重跑生成器；**先问用户选哪个**，代价不同）：

| 方案 | 改动 | 代价 |
|---|---|---|
| 压格子高度 | `gridSize = Vector2(80, 87.5)` | 6 行刚好 75→600；格子比原画条纹矮，越往下越不对齐 |
| 整体上移 | `gridBeginPos.Y = (mapSize.Y − 行数×gridSize.Y) / 2` | 保 98 格高；整盘相对背景上移，第 1 行顶到画布边缘 |
| 换底图（最正） | 提供 N 条纹、高度合适的底图，走 `Assets/Textures/...` 覆盖 | 要新画素材；引擎按 `600/贴图高度` 等比缩放，700 高的 6 行图正好 |

⚠️ **`TryValidateRuntime` 不校验「网格必须落在 `edge` 内`」** —— 它只查
`edge.Z > edge.X` 且 `edge.W > edge.Y`。所以这是**画面/相机**问题，不是校验问题，
别指望校验报错提醒你。
⚠️ 另外 `edge` 在玩法代码里**只用到 `.X` / `.Z`（左右）**：
`TargetSystem` 拿 `edge.Z` 当「僵尸来的方向」，推车 `x > edge.Z` 判出走，巨人僵尸用 `edge.X` 判越界；
`.Y` / `.W`（上下）**未被消费**（默认 `edge = Vector4(200, 0, 1100, 576)`，`.W`=576 小于 600 也无所谓）。

编辑器里调最快：游戏内 Map 编辑器拖 `gridBeginPos` / `gridSize` 能实时看网格叠加层，
面板底部有「边界: left/top/right/bottom」读数与 `格子: 9 x 6, 起点 …, 大小 …` 摘要。

### 换底图：把背景草坪 5 行 → 6 行（含把其中两行改成泳池水面）

Vampire.jpg（V0.28 原图 1400×600）实战数据。**草坪不是矩形**，是透视梯形——
直接贴矩形会在左右两侧留下一圈**草锯齿边 + 黑缝**，非常明显。

| 项 | 实测值 |
|---|---|
| 逻辑网格 | `gridBeginPos=(260,75)`、9 列 × 80 → x 260..980；行 y 75..575 |
| 美术草坪左缘 | y ≤ 420 时 x = 250，之后线性收到 x = 236（y=574） |
| 美术草坪右缘 | 抛物线 `x = 978 − 1.148e-4·t² + 0.1014·t`（t = y−74）→ y=74:978 / 320:996 / 574:1000 |
| 草坪上下沿 | y = 74 / 574 |

美术草坪比逻辑网格宽（左多 ~10px、下多 ~9px），多出来的是画师的**锯齿草边**。
所以重排后的水面**必须按逐行轮廓贴**：

```python
mask = Image.new("L", (1400, 600), 0)
d = ImageDraw.Draw(mask)
for y in range(py0, py1):
    d.line([(x_left(y), y), (x_right(y) - 1, y)], fill=255)
out.paste(water_layer, (0, 0), mask.filter(ImageFilter.GaussianBlur(1.2)))  # 1.2 = 抗锯齿
```

自检口径：`changed = ImageChops.difference(out, src)` 再与「允许改动区（草行矩形 ∪ 水面 mask，
外扩 3px 抗锯齿余量）」相减，**必须 = 0**。
⚠️ `ImageDraw.bitmap()` 合 mask 不可靠（静默不生效），要用 `Image.paste(..., box)`。

**行重排**：新 6 行各 500/6 = 83.33px（y = 74,157,241,324,407,491,574）。
每行取原图的一个整行条（100px）**纵向压到 83.33px**、横向不动即可。
原图草坪的明暗是 **160×200 的「格纹」**（奇数行整体偏亮 ~+12、偶数列整体偏亮 ~+10，
**两个方向独立叠加，不是棋盘**；实测四象限均值 EE62 / EO52 / OE74 / OO64 完全符合加性模型）。
按行取条能天然保住条纹节奏；左右下三边的锯齿草边也跟着保留。

**PoolBaseNight.jpg（720×160）**：四周有 ~6px 黑框，必须 `crop((6,6,714,154))` 才是无缝水纹；
**别整图 resize 到目标高**（水纹细节会被拉平），按宽度等比缩放后再纵向平铺。

**夜间水面明度必须标定，别凭感觉调**：
`BackyardNight.jpg` 实测 **池水/草地亮度比 = 1.376**（池水 L=84.3，草地 L≈61）。
把水面调到这个比值才"像游戏里的夜池"。做法：取被替换区域 → `GaussianBlur(~60)` 得到大尺度亮暗 →
乘到水纹上（把场景光带进水里，且不动色相）；再混 **20% 场景色**（先把场景亮度归一化到水面亮度，
否则整体会变暗）。水纹本身 `ImageEnhance.Contrast(1.45)` 让涡纹可见。

**改水色（如"水池改成血红色"）——别重取景，只换 ramp**

几何管线完全不用动，把水纹转灰度再映射到目标色即可：

```python
gray  = ImageOps.autocontrast(tex.convert("L"), cutoff=1)   # tex = 去黑框后的水纹，已平铺
gray  = ImageEnhance.Contrast(gray).enhance(1.75)
water = ImageOps.colorize(gray, black=DARK, mid=MID, white=HIGH)
# 之后照旧走：场景大尺度亮暗相乘 → 混 ~6% 场景色 → 轮廓 mask 贴入
```

血红色实测 ramp（`black=(10,0,3) mid=(74,2,10) white=(170,14,22)`）→ 成图 RGB(100,7,14)，
明度比 0.63。**四条反直觉的坑**（本次迭代 4 轮才过）：

1. **红色不能靠"亮度对齐"定亮度**——红的亮度系数只有 0.299（绿 0.587），要和草地同亮度得把 R 拉到 ~190，
   出来就是"亮红漆"。**血必须比草地暗**（本次草地 L=56 / 血 L=36）。
2. **高光的 G/B 要压死**：高光写成 `(158,24,36)` 这种偏粉值，出图就是**大理石纹/奶血**；收到 `(170,14,22)` 立刻正常。
3. **大块饱和色感知上会"发光"**：同样 L，纯红块远比花斑草地显眼 → 在算出的目标比值上**再往下压 10~20%**。
4. 「流动感」直接吃水纹对比度（1.75~2.0）+ 场景大尺度亮暗，**不用另造噪声**。

⚠️ **改完必须同步网格，两种收尾先问用户要哪种**——底图行高变了，网格不改就错位：
| 方案 | 参数 | 效果 |
|---|---|---|
| 保持原构图（本次采用） | `gridBeginPos.y=74`、`gridSize.y=83.33`、`gridNum=(9,6)` | 草坪仍止于 y≈575，构图不变 |
| 铺满画布 | `gridBeginPos.y=75`、`gridSize.y=87.5` | 6 行到 y=600；**底图也得按 87.5/行重画** |

### `translate` 直接写中文名即可
`LevelEditorInformationEditor.cs:155` 是 `foreach MAPS.Keys → mapOptionButton.AddItem(cfg.translate)`，
**不过 `tr()`**；内置图写 `MAP_VAMPIRE` 靠 Godot UI 自动翻译成中文，写中文名则回落原字符串。
游戏侧编辑器自己的新建地图模板就是这么写的（`XWTemplateLibrary.cs:631`，`translate = "${DisplayName}"`）。
→ 新地图**无需**配翻译表就能正确显示。

## 植物类 / 角色类（`Character` 的 Plant 子类）——又一条独立的绕路

> 👉 **只做「植物」时先看专用技能 `pvz-hybrid-plant-authoring`**（端到端 12 步流程 + 打勾清单 +
> 6 份 references）。本节仍是最全的细节来源，两者冲突以**本节 + 源码**为准。

类别名 `Character`，但**不能**像投射物那样只读路径前缀，`ModLoader` + `XWModContentValidation`
对角色包有 **8 条硬闸门**（`TryInferCharacterScene` / `IsCharacterPackageDependency` /
`PrepareSafeCharacterPackage` / `SanitizeCharacterTextResource` / `CharacterRequiresCompanion` /
`TryGetGodotResourcePath` / `ValidateManifestRegistrations` / `XWModContentValidation.Validate`）。
**任何一条不过 → 整包 apply 被拒（用户看到的就是「游戏加载失败」）**，
所以在写包之前先把下面 8 条过一遍，或直接跑现成的离线复刻脚本
`.workbuddy/ModWorkspace/.cache/check_modloader_gates.py`（28 项，不用进游戏）。

1. **场景路径恰好 6 段**：`Resources/Characters/<类>/<Key>/Scene/<Key>.tscn`，
   且**文件名 == 目录名 == `<Key>`**。`<类>` ∈
   `{Plants, Zombies, Props, Vases, Mowers, Items, Graves, Craters}`（`IsKnownCharacterCategory`）。
   段数不等于 6 / 名字对不上 → 整个角色包不被识别。
2. **精灵场景同样 6 段**，只把第 5 段换成 `Sprite`：
   `Resources/Characters/<类>/<Key>/Sprite/<Key>.tscn` → 注册成 `CHARCTAER_SPRITE[<Key>]`。
   ⚠️ **这个文件不是可选项**（见闸门 6），少了它必然加载失败。
3. **`Resources/Characters/<类>/...`（≥5 段）下的任何文件都算「角色包依赖」**
   → 贴图 `.tscn`、`Config/*.tres`、`Packet/*.tres`、`Scene/*ComponentSet.tres` 放这里都不会
   触发 `unsupported package file`，也**不会**进 `InferRuntimeEntry`。
   ⚠️ 所以这些文件**不推 derived key**，别拿它们去对 `provides`（对不上会被判
   `resource is not unambiguously declared by manifest` → 静默丢弃）。
4. **包内 `.scn/.res` 一律禁用**；`.tscn/.tres` **不得内嵌** `type="GDScript"`/`type="CSharpScript"`。
5. **引脚本必须用 `res://`，自引用必须用「相对路径」**（最容易搞反的一条）：
   * 指向**游戏自带**资源（`res://Prefab|Asset|Script|Resource|Registry|Extends`）→ 必须 `res://`。
     非 `res://` 的 `[ext_resource type="Script"]` 在 `.tscn` 里被**静默剥离**、在 `.tres` 里**直接拒绝**。
   * 指向**包内自己**的文件 → **必须相对**（`./XComponentSet.tres`、`../Config/X.tres`）。
     原因：`ModLoader.TryGetGodotResourcePath` 用 `ProjectSettings.LocalizePath()` 把包内文件
     映射成 `user://ModsCache/<名>/…` 再 `ResourceLoader.Load`，所以**相对引用在 user:// 树内解析**；
     而 `res://Resources/Characters/…` 会在**游戏 pck 根**解析，那里**根本没有 `Resources/` 目录**
     ⇒ 配置/组件集加载失败 ⇒ 角色被拒 ⇒ 整包失败。
     官方模板 `XWResourceCreateRoute.BuildCharacterRuntimeSceneContent()` 也是相对写法。
6. **必须额外交付 Sprite 场景**（对应闸门 2）。`XWModContentValidation.Validate()` 里：
   ```csharp
   string key = CHARCTAER_SPRITE.ContainsKey(saveKey) ? saveKey : characterConfig.name;
   RequireReference(manifest, "CharacterSprite", key);   // 查不到 → throw → 整包被拒
   ```
   运行时 `TowerDefenseManager.GetPacketSpriteScene()`（每张卡渲染都会调）还会
   `GetCharacterSprite(name)` → `throw new KeyNotFoundException`。
7. **`packet.saveKey` 必须等于「注册键」= `Resources/Cards/<文件名去扩展>`**
   （`XWModContentValidation`：不等即 `saveKey 与注册键不一致` → throw）。
   同时 **`characterConfig.name` 必须等于角色场景的 `<Key>`**：
   `TowerDefensePacketConfig.Create()` → `CreateCharacter(characterConfig.name)` →
   `TOWERDEFENSE_CHARCATERS[name]`，mod 角色只可能注册在 `<Key>` 这个键上。
   👉 最稳的做法：让 `<Key>` = `config.name` = `saveKey` = 卡片文件名 = 精灵文件名 **全部同一个字符串**。
8. **`unlockCheckList` 只能空表或 `XWModProgressUnlockCondition`**。照抄原版的
   `UnlockConditionPacketBankCategoryPacketUnlockNumConfig` 会被判
   「必须使用 Mod 专属解锁条件」→ throw。写 `unlockCheckList = []` = 直接可用。
   * 另外：**`provides` 是 all-or-nothing** —— 里面每个键都必须真的注册得上
     （`ValidateManifestRegistrations`），多写一个不存在的键也会整包失败。
   * **通常不需要伴生托管程序集**：`CharacterRequiresCompanion` 只在场景根带
     meta `mod_character_script_binding = "CompanionOnly"` 时为真。
     复用原版 `.cs` → `runtimeAssembly` 留空即可（`TryInstantiateEffectiveCharacter` 会失败并
     **回退**到 `GetChacraterScene`，这是正常路径，不是错误）。

### ✅ 验收：不用开游戏，直接读引擎日志确认「真的加载了」

用户跑过游戏之后，`%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\` 下就有硬证据：

| 位置 | 看什么 |
|---|---|
| `logs\godot.log` | **当前/最近一次**会话。搜 `[ModLoader]` |
| `PVZHE_Logs\godot_startup_*.log` | 历史各次启动（文件名带时间戳，取 mtime 最新的） |
| `ModsCache\<modid>\` | 真的解包过才会有；目录 mtime = 解包时刻 |

成功长这样（实测）：

```
[ModLoader] package extracted safely: supergatlingpea (7 files)
[ModLoader] package applied: supergatlingpea; resources=3; runtimeEntry=False; callbacks=0; diagnostics=1
[ModManager] enabled runtime apply complete: 3/3 packages; rollbackBlocked=False
```

读法：
* `resources=N` = **真的注册了几条**（角色包只有 `Scene`/`Sprite`/`Cards` 三条会注册，
  其余 `Config`/`Packet/`/`ComponentSet` 算「角色包依赖」不注册 —— 所以 N=3 是**正常的**）。
* `extracted (7 files)` = zip 条目数 − `mod.json`。
* `diagnostics=1` 通常是 `Localization/translations.csv` 被判 unsupported（**不致命**）。
* `N/N packages; rollbackBlocked=False` = 没有任何一包被回滚。
* 反例：出现 `... is not unambiguously declared by manifest` / `saveKey 与注册键不一致` /
  `缺少 CharacterSprite/...` → 整包被拒，按上面 8 条闸门对号入座。

### 一个植物 Mod 由 6 个文件组成（样板见 `.workbuddy/ModWorkspace/SuperGatlingPea/`）

| 文件 | 作用 |
|---|---|
| `Resources/Characters/Plants/<Key>/Scene/<Key>.tscn` | 主场景（**唯一的 Character 键源**） |
| `.../Scene/<Key>ComponentSet.tres` | 组件集（改射速/弹数/散射都在这里） |
| `.../Sprite/<Key>.tscn` | **精灵场景（唯一的 CharacterSprite 键源，必须有）** |
| `.../Config/TowerDefensePlant<Key>.tres` | 植物配置（`TowerDefensePlantConfig`，费用/冷却在这） |
| `.../Packet/<Key>.tres` | 该植物的卡片（包内镜像，不注册） |
| `Resources/Cards/<Key>.tres` | **卡池条目**，注册键 = **文件名** `<Key>` |

```json
"provides": { "Character": ["<Key>"], "CharacterSprite": ["<Key>"], "Packet": ["<Key>"] }
```
三者键都正好是 `<Key>`（不是 `<Key>Packet`）—— 因为 `saveKey` 必须 == 注册键，而
`characterConfig.name` 必须 == 场景键，统一成 `<Key>` 才能同时满足。
**都走 `provides`**（新键），同 (类别,键) 重复 → `ambiguous`。

### 费用 / 冷却 / 卡类型写在哪

| 想改 | 字段 | 位置 | 备注 |
|---|---|---|---|
| 阳光花费 | `cost` | `TowerDefenseCharacterConfig`（**植物 Config**，不是卡片） | 默认 100 |
| 种植涨价 | `costRise` | 同上 | 默认 **-1 = 不涨价**；想让同关每再种一张贵 N ⇒ 写 N |
| 夜间价 | `costNight` | 同上 | -1 = 不用 |
| 冷却秒 | `packetCooldown` | 同上 | 默认 5.0 |
| 卡类型（金卡…） | `type` | **卡片**（`TowerDefensePacketConfig`） | `PACKET_TYPE`，见下 |

```csharp
enum PACKET_TYPE { NOONE=-1, WHITE=0, GOLD=1, DIAMOND=2, COLOUR=3, STAR=4, ORIGINAL=5, ZOMBIE=6, COVER=7, GRAY=8 }
```
取值路径：`packet.GetCost() → characterConfig.cost`、`packet.GetCostRise() → characterConfig.costRise`
（`_override` / `overrideCost` 优先）。**"种植涨价" 是 `costRise`，不是 `cost` 的乘数。**


### 发射管线：射速 / 弹数 / 散射全在 ComponentSet

> ### ⚠️⚠️⚠️ 先过这一关：角色场景**必须显式声明 `ComponentSet`**，否则**一颗子弹都打不出来，且零日志**
>
> 这是「做开枪类角色」最容易白忙的坑，而且**加载期完全静默**（不拒包、不告警、不进 diagnostics）。
>
> **症状**：角色走路/啃食/血条全正常，就是**一个弹丸都不出**；插件侧
> `componentManager.GetRuntime<FireComponent>("character.fire")` 返回 **null**。
>
> **根因链**：
> ```csharp
> // TowerDefenseCharacter.cs:703-704
> [Export] public CharacterComponentSet ComponentSet { get; set; }
> // TowerDefenseCharacter.cs:1911-1937  EnsureComponentManagerResource()
> if (IsInstanceValid(ComponentSet)) componentManager.ComponentSet = ComponentSet;  // 只有显式声明才用你的
> // ComponentManager.cs:318-352  InitializeResourceComponents()
> entry.Definition.CreateRuntime();   // 集里没有 Fire 定义 ⇒ 这个 runtime 组件根本不会被 new
> ```
> 而基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:10` 自带
> `ComponentSet = ExtResource("2")` → `TowerDefenseZombieComponentSet.tres:17`
> 内容只有 `BuffZombie, GroundHeightZombie, WaterInteraction, GroundMove, ZombieDeath, Garlic, Swim, AttackZombie`
> —— **没有 FireComponent**。子场景不覆盖 ⇒ 默认集生效 ⇒ 发射组件不存在。
> （植物侧同理：基场景那份也不含 Fire，植物 Mod 一样要覆盖。）
>
> **修法**（两行，纯数据）：
> ```ini
> [ext_resource type="Resource" path="./<Key>ComponentSet.tres" id="15"]
>
> [node name="<Key>" node_paths=… instance=ExtResource("1")]
> ComponentSet = ExtResource("15")     # ★ 必须写在 script 之前，且必须是包内相对路径
> script = ExtResource("2")
> ```
> 内置先例：`TowerDefenseZombieNormalGatlingPea.tscn:25` 就是这么写的。
>
> ⚠️ **`ModLoader.InferRuntimeEntry()` 不检查 `.tscn` 内容** ⇒ 漏了这行**没有任何报错**，
> 只能进游戏放下角色才发现「怎么不打子弹」。
> ⇒ **必须自己加闸门**：断言①场景里有 `ComponentSet = ExtResource(`；
> ②它指向包内相对路径 `./<Key>ComponentSet.tres`；③包内组件集的 `ParentSet` 指向内置集
> 且 `Components` 只加 1 个发射定义（父集带来其余全部）。
> ⇒ 插件侧也**不要**在 `IsUsable(fire)` 为假时静默 `return`（踩过：静默了一整轮），
> 一定要打一次性诊断日志并直接点名「场景可能漏了 `ComponentSet`」。

`TowerDefensePlant`(Node2D) 是基类，各植物一个 C# 子类声明 `[Export] fireInterval / fireNum /
projectileName` 转发给 `FireComponent`。真正生效的数据在 `FireComponentDefinition`：

```csharp
// FireComponent.cs:3413  FireConfiguredVolley()
if (!fireNumAtOnce) { Fire(); return; }
for (int i = 0; i < fireNum; i++) { currentFireNum = i; Fire(i == 0); }
```

| 想要 | 写法 | 原版例子 |
|---|---|---|
| N 颗同方向叠发 | `fireNum = N` + `fireNumAtOnce = false` | 豌豆射手 |
| **一次齐射 N 条不同方向** | `fireNum = 1` + **`fireNumAtOnce = true`** + **N 条 `FireComponentFireProjectileConfig`** | 五角星(5)、三线射手(3) |
| **由插件「逐颗」驱动**（概率/真随机/每颗改向） | **只留 1 条 config（`dir=0`）** + `fireNum=1`、**不要 `fireNumAtOnce`** | 见「玩法类托管插件的标准姿势」 |

⚠️ 最后一行很关键：`Fire()` **一次调用会遍历全部 config** ⇒ 插件逐颗调 N 次时，N 条 config 会变成 **N² 颗重叠**。

* 方向字段是 `dir`，**单位是度，0 = +X（右）**（`FireComponent.cs:3434`：
  `velocity = cfg.speed * Vector2.FromAngle(Mathf.DegToRad(cfg.dir))`）。
* **朝向自动镜像，不用管**：`CreateProjectile`（`:2684`）末尾乘了
  `Mathf.Sign(parent.Scale.X * parent.transformPoint.Scale.X * parent.sprite.Scale.X)`。
  只写一套「向右」的 `dir`，僵尸在左边时自动变成向左。
* `FireComponentFireProjectileConfig` **只有 8 个字段**：
  `checkProjectileId, firePosId, speed(=300), dir(=0), offsetLine, fireNumSkip(=-1), fireEventNeed, projectileFlip`。
* 散射范式：`Starfruit` → 5 条 `dir = 330/270/180/90/30` + `firePosId 0..4`（`speed=500`）；
  `ThreePeater` → 3 条用 `offsetLine = -1/0/+1`（换行）；`SplitPea` → `fireNum=2` + `fireNumSkip=1` + `speed=-300`（向后）。
* 射击动画靠 `fireAnimeClips="HeadFire"` / `spliceIdleAnimeClips="HeadIdle"` / `isSpliceSprite=true`
  + `firePosMarkerPaths = [NodePath("<...>/Marker2D")]`（**指向场景里真实存在的 Marker2D 节点**）。
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
  ⚠️ 挂 `[sub_resource]`/`NodePath` 里**没有**的类型，.tres 不报错，只是静默失效。
* ⚠️⚠️ **没有开火动画 ⇒ 整条「动画驱动发射」链路失效**（这是**设计好的降级路径**，不是 bug）：
  ```csharp
  // FireComponent.cs:3230（AttackEntered 第一句）
  if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(FireRuntimeState.Idle); return; }
  // FireComponent.cs:998 / :1011
  private bool CanPlayFireAnimation(string clipName) { … if (string.IsNullOrEmpty(clipName)) return false; … }
  ```
  ⇒ `fireAnimeClips` 留空（或精灵里根本没有那个 clip）时**一枪都打不出去**。
  想做「没有开火动画的角色也能开枪」⇒ **只能写插件**，并**刻意不写** `fireAnimeClips` /
  `spliceIdleAnimeClips` / `spritePath`（后者留空 ⇒ `FireComponent` 连 `sprite.timeScale` 都不碰）。
  附带好处：**不必去枚举 `.dat` 动画里的 clip 名**（解包树里有些 `.dat` 缺失，枚举不出来）。
* ★★★ **「攻击时只有动画、没有子弹」的唯一真因 = 动画 `events` 表里没有 fire 条目**（2026-09-21 实机实锤）。
  **普通射击 100% 是「动画事件驱动」的，插件只负责大招** ⇒ 只写 `fireAnimeClips="HeadFire"` 让动画播起来**不够**，
  必须让动画在某一帧**发出 `fire` 命令**：
  ```
  AdobeAnimateSprite.events[播放到的帧]
    → OnAnimeEvent?.Invoke(dict["Command"], dict["Argument"])      AdobeAnimateSprite.cs:5327
    → FireComponent.AnimeEvent(cmd, arg)                          （订阅点 FireComponent.cs:1484）
    → cmd ∈ fireEventName.Split("&")     // fireEventName 默认 "fire"   FireComponent.cs:343
    → FireConfiguredVolley()  →  Fire()  → 按 firePosMarkerPaths 生成子弹
  ```
  ⇒ **`.dat` 与 `.tres` 的 `events` 表必须含 `{"Command":"fire","Argument":""}`**，否则**动画照播、一颗弹都没有，且加载期零报错**
  （极易误判成贴图/插件问题，白查半天）。
  - **发射帧定法（A/B 实证，别拍脑袋）**：= `anim_shooting` 起点后「枪口轨(x) **首次**达最大伸出(±1px)」的帧，
    且**必须 `帧 − HeadFire.start == 12`**。证据：扫 143 个内置植物 `.tres`，单发族 7 例
    （PeaShooter/SnowPea/ReCactus/SunflowerPea/SunPeashooter/IceSpearPea/PeaShooterSingle）
    **清一色** `HeadFire=(50,74)` + **恰好 1 条 event @ f62**；多连发按「次极值 −1」取 61/67/73
    （GatlingPea 4 条 @61/67/73/79、ThreeCactus @55/61/67/73）。
    ⚠️ 用严格 `max()` 会落在「平台末端」（本例 f65）⇒ 偏移 15≠12，必须用**首次达峰**语义。
  - **`.dat` 事件段字节布局**：`u16 条数` + 每条(`u16 frameIndex` + `u16 事件数` + 每事件(`PascalString Command` 然后 `PascalString Argument`))。
    ⚠️ **frameIndex 是 `u16` 不是 `u32`**；**`Command` 在前**（`AdobeAnimateData.InitInternal:1352-1372`，`Get16()` + `GetPascalString()`）。
* ★★ **头对位只有两个真旋钮＝`offset` ＋ `offsetRotate`**（2026-09-22 源码实锤，**推翻**此前「只改 `Head.position`」的说法）。
  `AdobeAnimateSprite.UpdateChild()`（`:5259-5281`）**每帧重写**子精灵，而 `usePos`/`useRotate` 默认就是 `true`（`:276`/`:279`）：
  `child.Position = 被跟随图层 pose.Origin + 父精灵 offset`、`child.Rotation = pose.Rotation + child.offsetRotate`（**单位是度**）。
  ⇒ 场景里手写的 `Head.position` / `Head.rotation` 是**死值**（官方 `ZombieNormalGatlingPea.tscn` 也写着
  `position=(-22.2,-76.3)`、`rotation=-0.158`，同属编辑器残留，实机不生效）。
  ⚠️ 同时**纠正另一半**：`offset` **不影响** `Marker2D`/炮口 —— 它只作用于**本精灵自己那份美术**
  （`:7044`/`:7071`/`:7362` `transform.Translated(offset)`）与子精灵落位。「改 offset 炮口会偏」是错的。
  - **跨素材拼装（僵尸身 + 植物头）必须重标定**，不能照抄别处的值：官方 `ZombieNormalGatlingPea` 的
    `Head.offset=(-58,-5)`、`offsetRotate=-0.25` 只对它的身体成立。反解用 `.cache/check_head_fit.py`
    （引擎变换模型 + 官方样本交叉校验 + **负向测试**：旧值必须报错）。照抄错的 offset ⇒ 实机头悬空（实测偏 41.75px）。
* 复用原版贴图：场景里 `[node instance=ExtResource("...")]` 直接实例化原版贴图 `.tscn`，
  标 `[editable path="..."]`，**不要**把素材复制进包。

### ★★★ 子弹生成点（`FireMarker`）—— 「子弹从哪出膛」只由它决定

**真源链路（顺源码查，别凭插槽名字猜）**：
`.tres` 的 `firePosMarkerPaths` →（`FireComponentFireProjectileConfig.cs:10` `public int firePosId;`
默认 0 ⇒ 取第 0 个）→ `FireComponent.CreateProjectile()`（`FireComponent.cs:2698-2714`）
→ `parent.GetLogicalGlobalPosition(marker2D)` → `TowerDefenseCharacter.cs:1607-1619` 的实现就是
`descendant.GlobalPosition`。
⇒ **生成点 = 那个 `Marker2D` 的世界位置**（既不是角色原点，也不是美术上的炮口）。
旁路（一般都不生效）：`snapStraightProjectileToSameCellTarget`（`FireComponentDefinition.cs:121`，默认 false）、
`ResolveOffsetLineRoute`（只在子弹挡路时改 x）。

⚠️ **别以为「挂在 `HeadSlot` 下就跟着头部动画」** —— `HeadSlot` 是原版给护具 / DamagePoint 用的
**静态插槽**（原版 `TowerDefenseZombiePaper.tscn:67-71`：`drawLayerId=-2` /
`position=(-14.015516,-40.408867)` / `rotation=-0.27867758` / `scale=0.79857695`），
其 `position` **不跟头部美术**；护具看着贴在头上，是**护具自己的 `offset` 补掉了差**。
（这个误解真的踩过：子弹从头顶上方 80.77px 处出膛。）

⚠️ **Godot `Transform2D` 只把 `position` 当平移** ⇒ 子节点局部坐标会被父节点的 rot/scale 作用：
```
space = HeadSlot.pos + M(θ_slot, s_slot)·marker + BODY_OFFSET
```
漏掉 `M·` 的写法**只在 `marker == (0,0)` 时**才等价 —— 这个坑很隐蔽（改了 marker 才发现公式失效）。

**对齐炮口要分两层（只要头会动，就缺一不可）**：

1. **静态兜底** —— 反解 `Marker2D.position`（HeadSlot 局部）：
   `p = (1/s)·R(−θ)·(Q − HeadSlot.pos)`，其中 `Q = A·(muzzle_pose + offset) + node − BODY_OFFSET`
   （`A` = 跟随层旋转的横翻矩阵；参考帧取 `body_frame = 0`，与头的 `offset` 同口径）。
2. **每帧动态** —— 头跟 `anim_head1` 逐帧摆 / 播开火动画时，**静态值只能对上参考帧**
   （实测 Idle 段最大离线 10.86px；Eat 段炮口跨 x 42.8 / y 78.2 px）。
   插件在「影子→可见头同步」那一环补一句：
   `marker.GlobalPosition = head.GlobalTransform * HeadMuzzleLocal`，
   其中 `HeadMuzzleLocal = muzzle_pose + offset`（头绘制是 `transform.Translated(offset)` 再画 pose 点
   ⇒ 局部点 = pose + offset）。⇒ 一行拿到炮口世界坐标、天然跟随；
   **改 `offset` 必须同步这个字面量**（用「生成器常量 ↔ 插件字面量」跨语言比对把关，别靠记性）。

**炮口点怎么标定**：从「炮管轨（barrel）**完全伸出帧**」的**不透明区最右列中点**映射到美术 pose 空间
（与植物侧 `ANCHOR_MUZZLE = (88.552, 30.2)` 同一手法）⇒ 两个独立来源可互校。

**判据写法（防假绿）**：「炮口 ← 美术反推」与「生成点 ← **生成的场景 .tscn** 现场反读」两个来源
必须**互相独立**；再配负向（marker 退 `(0,0)` / 只改一个分量 / 符号反 / 整体偏 10px 都必须被判离线）。
工具：`_muzzle_probe.py`（反推）、`_muzzle_scan.py`（扫全部 clip 的炮口范围）、
`_fire_marker_solve.py`（反解 + 回代）、`_marker_ab.py`（旧/静态/每帧 三口径对照图）。

### 换外观（贴图 / 动画）—— 先搞清「三件套」，别以为是一张 PNG

**★ 先选路线**：
| 路线 | 何时用 | 去哪节 |
|---|---|---|
| **A. 官方素材直转（首选）** | 未重置版解包里有该角色的 `*.reanim.compiled` + `reanim/*.png` | 本节末「★★★ 首选：换「官方素材」」 |
| B. 自制单帧 / 手做逐帧素材 | 拿不到 reanim，或只要一张静止图 | 本节「自制 `.dat` 的五个必踩坑」起 |

⚠️ 两条路线的**缩放口径不同**（自制素材常见「放大 2 倍画」⇒ `DISPLAY_SCALE=0.5`；官方素材 `sx/sy` 即最终缩放），**别混用**。

角色的视觉 = **精灵场景 `.tscn` + 动画数据 `.tres`(`AdobeAnimateData`) + `.dat` 二进制图集**。

★★ **`.dat` 是「自包含图集」，图片就塞在里面**（不是散装 PNG）：
```csharp
// addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs:1682-1701  TryReadEmbeddedAtlasImage
fileAccess.GetFloat();                                    // frameRate
fileAccess.Get16();                                       // frameMax
imageAtlasSize = new Vector2I(Get16(), Get16());          // ★ 图集宽/高
int len = (int)fileAccess.Get64();                        // 像素字节数
image = ReadEmbeddedImageAtlasFromDat(...);               // :1630-1646
//   byte[] buffer = file.GetBuffer(len);
//   Image.CreateFromData(w, h, false, Image.Format.Rgba8, buffer);   // ★ RGBA8 原始像素
```
⇒ 换图 = 重新生成 `.dat`。
⚠️ **`.dat` 不在解包树里**（`Asset/.../X.dat` 磁盘上不存在），在游戏 `pck` 内 ⇒
解包树只提供 `*.tscn|*.tres|*.cs`，**图片二进制看不到**，别浪费时间找。

`.tres` 的 `animeFile` **可以写包内相对路径**（Mod 自带动画的入口）。解析顺序
（`AdobeAnimateData.cs:1790-1822 ResolveAnimeFilePath`）：原路径 → `base.ResourcePath` 同目录
→ `TryResolveOwnerBasenameCompanionDat`（**同目录同名 `.dat`**）→ 编辑器缓存路径。

**两条路线：**

| | 复用内置其它角色 | 导入自己的美术 |
|---|---|---|
| 改什么 | `Sprite/<Key>.tscn` 的 `path=` 换成目标角色 `.tscn` | 编辑器导入 `.fla`/`.xfl` → 生成 `.tres`+`.dat` |
| 要不要带 `.dat` | ❌ 用游戏的 | ✅ 必须打包进去 |
| 合法依据 | `ModLoader.cs:1755`：`res://` 且 `ResourceLoader.Exists()` ⇒ 直接放行 | `AnimationAtlas` 通道（见下） |

★ **Mod 有专门的「自定义动画图集」通道**（换动画的官方正路）：
`Resources/AnimationAtlasProfiles/` → category **`AnimationAtlas`**（`ModLoader.cs:1088`），
资源必须 `is AdobeAnimateAtlasProfile`（`:1155-1167`），加载器自动
`TryPreparePackagedAnimationAtlasProfile` + `TryRelocatePackagedAtlasManifestPaths`
（`:1696` / `:1703-1740`）把 manifest 与图集**重定位到包内**。
* `AdobeAnimateAtlasProfile`（36 行）：`ProfileId` / `ManifestPath` / `StartupOnly`。
* `AdobeAnimateGlobalAtlasManifest`：`SourceKeys`（各 `.dat` 的 `res://` 路径）、
  `SourceSignatures`（**内容指纹**）、`MediaRects`（媒体图集矩形）、`PoseAtlasPagePaths` …
  ⚠️ **指纹与矩形不能手写**，必须由编辑器导出流水线生成；手改一个字符就失配。
* 样板：`addons/AdobeAnimateEditor/GeneratedAtlas/Bootstrap/AdobeAnimateBootstrapAtlasProfile.tres`
  + 同名 `…AtlasManifest.tres`；官方回归范例 `Tests/ModEditorAnimationAtlasProfileRuntimeProbe.cs`。

★ **导入器只吃 `.fla` / `.xfl`**（`XWAdobeAnimateImportService.cs:78-81`，
报错原文 "Only Adobe Animate .xfl and .fla files can be imported as animation resources."）；
`:86-96` 生成同名 `.tres`+`.dat`；`:112` `SetAnimeFileForModImport(datPath.GetFile())`
⇒ **`animeFile` 写成文件名（相对）**。编辑器 UI 入口 = 目录右键 `new-animation`
（`XWFileSystemPanel.cs:1938-1941`，"导入 Adobe Animate 动画" 文件框）。

★ **只想换某几张图、不重做动画**：`AdobeAnimateData.cs:562-563 extraMediaReplaceTexturePaths`
（`Array<string>`，png/webp/jpg/svg/bmp/tga）+ 运行时
`AdobeAnimateSprite.SetAtlasReplace(mediaName, texRef)`（`:6000-6022`）。
⚠️ `SetAtlasReplace` 先查 `mediaDictionary.ContainsKey(mediaName)`，
**查不到静默 `return false`** ⇒ 必须用**原媒体名**（如 `GatlingPea_head.png`）。

⚠️⚠️ **换素材必须对齐 clip 名**，否则发射链路断：
`ComponentSet` 里 `fireAnimeClips="HeadFire"` / `spliceIdleAnimeClips="HeadIdle"`，
角色场景 `idleAnimeClip="BodyIdle"`。缺 `HeadFire` ⇒ `FireComponent.cs:3230 AttackEntered`
首句 `CanPlayFireAnimation` 为 false ⇒ **一枪打不出**。
**兜底**：若角色**确有**托管插件**每轮都直调 `Fire()`**（`:3429` 不受状态机约束 ⇒ 在场就能打），
则没有开火动画也照样出膛（只是不抬枪）⇒ 此时才可把三个 fire clip 字段留空。
⚠️⚠️⚠️ **但这只对「插件负责全部射击」的包成立**。**只要射击是引擎驱动（动画事件 → FireComponent），
`.dat`/`.tres` 的 `events` 表就必须有 `{"Command":"fire","Argument":""}`，否则「只有动画、没有子弹」**
（2026-09-21 实机实锤，详见「发射管线」红字链路）。**别把「留空」当默认做法。**

⚠️ 换精灵后 **`Marker2D`（出膛点）位置必须重调**；`firePosMarkerPaths` 必须指向真 `Marker2D`
（`FireComponent.cs:1254` 带类型过滤，指向 `HeadSlot` 会拿到 null、子弹从原点出膛）。

#### ★★★ 自制 `.dat` 的五个「必踩坑」（已实证，照抄）

**⓪ `scale` 是「显示缩放」，写 1.0 会让角色大 2.5~3 倍（最易整段漏掉）。**

素材常按**放大 2 倍**制作（角色实际占 144×170，塞进 176×192 的画布；**单帧素材同理 —— 本 Mod 新图 352×384 恰是 176×192 的精确 2 倍**）⇒ **必须乘 0.5**。

三条独立判据（缺一个都别再猜）：

| 判据 | 怎么读 | 本 Mod 实测 |
|---|---|---|
| 交付基准图 | 素材目录里的 `_source_cutout_1x.png`（或 `_frames.json` 的 `scaleFromSource`，**倒数**即 scale） | `72×85` = 144/2、170/2；`scaleFromSource=2` |
| **内置 `.tres`** | `sliceTransforms` 每 6 个 float 取第 0 个 = `scale` | `GatlingPea` 842 条 = **0.4118 ~ 1.0**；逐条算 `rect_w*scale` ⇒ 渲染最大边 **58.70 px** |
| 素材 bbox | 抠像后字符实际占的像素范围 | 144 × 170（画布 176×192）；单帧素材 290×330（画布 352×384） |

```python
# 逐 slice 精确算内置渲染尺寸（别用「最大 rect × 最大 scale」近似，会偏大）
scales = [st[i] for i in range(0, len(st), 6)]
mx = max(max(rects[m][2] * scales[k], rects[m][3] * scales[k])
         for k, m in enumerate(media_ids))
```

⚠️⚠️ **`origin` 的语义 = 「该层内容 bbox 几何中心，在完整素材画布上量 × `DISPLAY_SCALE`」（跨层公共画布坐标，不是层内局部坐标）。**

用源码定死（别猜）：

```text
AdobeAnimateData.cs:1484-1489  写入 list9.Add(transform.X.X)…(transform.Origin.Y)   ← 直通，无缩放
AdobeAnimateData.cs:2820       读出 new Transform2D(…, Origin.X, Origin.Y)          ← 直通，无缩放
AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform ← 唯一一次作用：
    Transform2D(new Vector2(slice.Xx*sourceSize.X, slice.Xy*sourceSize.X),   // X 基向量 = scale × 帧宽
                new Vector2(slice.Yx*sourceSize.Y, slice.Yy*sourceSize.Y),   // Y 基向量 = scale × 帧高
                new Vector2(slice.Ox + offset.X, slice.Oy + offset.Y));      // origin 直接相加
    return parent * transform2D;
```

⇒ 该层贴图尺寸 = `scale×帧宽` × `scale×帧高`；`(Ox,Oy)` = 该块贴图在**父坐标系**里的落点。
⇒ **`origin` 必须同比乘 `DISPLAY_SCALE`**（只缩 `scale` 不缩 `origin` ⇒ 角色**偏离约 2 倍距离**）。

**两种实证法（推荐做一次，能省一小时瞎猜）**：
1. **拼图对拍**：造两张还原图 —— 按「内容 bbox 中心」摆（`.cache/_recon_by_center.png`）vs 按「层内局部」摆（`_recon_by_origin.png`）。前者拼出完整角色 ✓，后者只出现右下 1/4 ✗。
2. **内置交叉反证**：`PeaShooter.tres` 的 `scale=0.5554` 而 `origin ≈ (19~56, 45~62)`，若当层内局部坐标会**超出自身 `44×22` 的小帧** ⇒ 只能是跨层公共画布坐标。

★ **`scale` 存两份 ⇒ 改必须全跑**：

| 位置 | 写入者 | 布局 |
|---|---|---|
| `.dat` layer 表 | `build_dat.py`（`sc = s['scale']`） | 每元素 30 B：`u16 mediaId` + `f32 xx,xy,yx,yy`（无旋转 ⇒ `xx=yy=scale`、`xy=yx=0`）+ `f32 originX,originY` + `u32 RGBA` |
| `.tres` `sliceTransforms` | `build_tres.py` | 每 slice 6 float：`sc,0,0,sc,ox,oy` |

⇒ 必须 **`build_atlas2.py`（缩放常量就放这）→ `build_dat.py` → `build_tres.py`** 按序全跑；
只重跑后者 = `.dat` 与 `.tres` scale 不一致的隐性故障。

★★★ **「谁乘了 0.5」必须分清（极易二次乘）**：

| 常量 | 来源 | 标定块里怎么用 |
|---|---|---|
| `BODY_ORIGIN` / `HEAD_ORIGIN` | `author2.json` 的 `ox/oy`（`build_atlas2.py:225` 写入时**已乘**） | **不要再乘** |
| `ANCHOR_ROOT` / `ANCHOR_MUZZLE` | **素材画布原生坐标**（如 352×384） | **显式 ÷2** |

★ **自洽信号**：全量 ×0.5 后 `Marker2D` 应恰为旧值**精确一半**（本 Mod `(72,-104) → (36,-52)`，整数）。

⚠️⚠️ **校验脚本必须显式断言 `scale`** —— 本 Mod 的坑正是**只查了结构与「origin 落在画布内」，
从没断言过 `scale`**，所以「角色大 2.5~3 倍」一路绿灯到用户眼前。补两条：

```python
assert sorted({round(s, 6) for s in scales}) == [0.5]        # scale 全 == 期望值，不是 1.0
# ⚠️ origin 的越界判据要跟着素材换 —— 硬编码 90 在单帧素材下会假红（body oy=151.5 天然 > 90）
RENDER_CANVAS_W, RENDER_CANVAS_H = 176, 192                  # 渲染空间 = 素材画布 × DISPLAY_SCALE
assert max(oxs) <= RENDER_CANVAS_W and max(oys) <= RENDER_CANVAS_H
# 未缩 0.5 时 body oy 会是 303 ⇒ 直接越界被抓
```

**① `animeFile` 相对路径层级要按「引用方」算，别手算。**

- 包内**禁止** `res://`（`res://` 只解析游戏自带：`Prefab`/`Asset`/`Script`/`Resource`/`Registry`/`Extends`）。
- Sprite 场景在 `Resources/Characters/Plants/<Key>/Sprite/`（**5 段**），动画在 `Resources/Animations/`
  ⇒ 需要 **5 个 `../`**：
  ```text
  ../../../../../Resources/Animations/<Key>.tres
  ```
  ⚠️ 4 个会解析成 `Resources/Resources/Animations/...` → MISSING。
- `.dat` 侧写 `./<Key>.dat`（同目录同名，命中 `ResolveAnimeFilePath` 的
  `TryResolveOwnerBasenameCompanionDat` 兜底）。
- **别信自己数的层数**：写完用 `posixpath.normpath` 断言「解析结果在包内真实存在」，3/4/5 段都试一遍。

**② `offset` 的语义 = 把「该层 origin 点」挪到「节点原点」；⚠️⚠️⚠️ 但引擎会 **自己把 `origin` 加回去**。**

```csharp
// AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform
new Transform2D(..., new Vector2(slice.Ox + offset.X, slice.Oy + offset.Y));  // ← origin + offset
return parent * transform2D;
```

⇒ **落点 = `origin + offset`** ⇒ `offset` **与 origin 无关**，只 = `-ANCHOR_ROOT`（两层**完全相同**）。

⚠️⚠️⚠️ **别写成 `-(anchor - origin)`** —— 那会让落点 = `2*origin - anchor`，
**头身相对位移被放大 2 倍**（本 Mod 的 `(-5.25,-82.75)` 被放大成 `(-10.5,-165.5)`）
⇒ **实机症状：头压在身体上、身体几乎看不见**。这就是 2026-09-20 那版失败的根因。

**内置反证**：`GatlingPea.tscn` 根 `offset=(-40,-40)`、Head `offset=(-36,-46)` 都是**小整数**，
而各层 `origin` 在 20~60 ⇒ 若公式真是 `-(anchor-origin)`，offset 早该是几十上百的量级。
（`Head.position` 官方文件里也有显式值，但 `UpdateChild()` 每帧会覆盖它 ⇒ **写它等于没写**；
本 Mod 取 `position=(0,0)` + 两层同 offset —— 那行只是占位。**要微调头位请改 `Head.offset`**。）

正确写法（`anchor.root` = 脚底，`anchor.muzzle` = 炮口，**全部取渲染空间值**）：

```text
根   offset = -anchor.root
Head offset = -anchor.root          ← 两层完全相同
Head.position = (0, 0)
Marker2D      = anchor.muzzle - anchor.root

# 渲染空间 = 素材画布坐标 × DISPLAY_SCALE（见坑 ⓪）
# 自洽：Marker2D 是「炮口像素在节点空间的位置」= 素材坐标 - 节点原点(= anchor.root)
```

**本 Mod 实测值（单帧素材 352×384，`DISPLAY_SCALE = 0.5`）**：`anchor.root=(69.25,174.0)`（= 素材 `(138.5,348)` ÷2，内容最低行/双脚行中心）、`anchor.muzzle=(157.0,62.75)`（= 素材 `(314.0,125.5)` ÷2，最右绿色像素 = 炮管末端）、`bodyOrigin=(93.0,151.5)`、`headOrigin=(87.75,68.75)`
⇒ `根 offset = Head offset = (-69.25,-174.0)`、`Marker2D=(87.75,-111.25)`。

（历史值 —— 旧多帧素材 176×192：`root=(40,79)`、`muzzle=(76,27)`、`bodyOrigin=(46.525,76.49)`、`headOrigin=(44.27,34.51)`
⇒ 按**正确公式**应为 `根 offset = Head offset = (-40,-79)`、`Marker2D=(36,-52)`。
⚠️ 当时记录的 `根 offset=(6.525,-2.51)`、`Head offset=(4.27,-44.49)` 是**旧的错误公式 `-(anchor-origin)`** 产物，
整组恰好是 `-(anchor-origin)` 而非 `-anchor` —— **别再照抄**。`Marker2D=(36,-52)` 恰好两种口径都对（它只跟 anchor 有关）。）

★ **四个脚本的标定常量必须逐字一致**（改一处就要同步另三处，否则校验/重建互相打架）：
`.cache/install_skin.py`（标定块 + 预览文案）、`ModWorkspace/build_plant_super_gatling.py`（素材说明块 + 标定常量块 + 预览文案）、
`.cache/verify_skin_assets.py`（期望值常量）、`.cache/verify_head_body_layout.py`（期望值常量）。

**★★★ 验证器分三层，缺一层就会「假绿」（2026-09-20 血泪）**

| 层 | 脚本 | 查什么 | 查不出什么 |
|---|---|---|---|
| ① 结构 | `verify_skin_assets.py` | `.dat` 字节布局 / `.tres` 数组自洽 / 场景字段值 | 各层**拼起来**对不对 |
| ② 拼合 | `verify_head_body_layout.py` | **落点差 == origin 差** + 两层真贴上（非白像素 > 3000）+ 红/蓝点落位 | 游戏内观感 |
| ③ 出包 | `check_plant_super_gatling.py` / `check_project_folder.py` / `run_gates_plant.py` | 工程布局 / 闸门（**两份构建**）/ 幂等 | — |

★ **换官方素材（多帧）时改为「四层独立 + 负向测试」**，见本节末「★★★ 首选：换「官方素材」」的
「验证器：四层独立 + 负向测试」表 —— 关键是**四层各自独立解析、只读磁盘、不复用生成器代码**，
再加 `--negative` 故意写坏副本断言必报错。上面 ①② 两个验证器是**自制单帧素材专用**（对多帧会假红，
现已带 LEGACY GUARD 自动 SKIP）。

⚠️⚠️⚠️ **坑：`self_check()` 里比对「刚生成的内存文本」= 假绿。**
`build_plant_super_gatling.py` 的 `self_check()` 开头会调 `sprite_scene_tscn()` **重新生成**场景文本再断言
⇒ 它只能证明「生成器常量 == 生成结果」，**证明不了磁盘上的文件是对的**。
**负向测试实锤**：把错值直接写进磁盘 `.tscn` 后跑自检，照样打印「自检通过」（内存文本被重新生成覆盖了）。
⇒ **必须另加 on-disk 复核**（读文件 + 比对 + 断言磁盘值），本 Mod 已加为 `#13f`。
★ **规矩：凡「生成器自检」都要配一条 on-disk 断言，并用「故意写坏磁盘文件 → 必须报错」验证它会响。**

**★ 假渲染验证法（本轮救命技巧，强烈推荐）：** 别急着出包进游戏试。写个几十行的 Python 假渲染器
（`pnglib.read_png` 读图集 → 按 `落点 = origin + offset` 把每层 media rect 缩 `SCALE` 后贴到画布 →
`write_png` 出图），**肉眼一看就知道公式对不对**。本轮错误版出图 ~1.3 KB（几乎空白、两层飞出画布），
正确版 ~10 KB（完整角色、红点落脚底、蓝点落炮口）—— **比反复出包试错快一个数量级**。
本 Mod 已固化为 `.cache/verify_head_body_layout.py`（支持 `--png`）。

**③ `.tres` packed 数组的真实语义（写错不报错，只是不画 / 静默异常）。**

| 字段 | 正确语义 | 依据 |
|---|---|---|
| `sliceKeys` | **`(layerId << 16) \| 槽序号`** —— **不是 `\| mediaId`** | `BuildPackedRuntimeData:1480` |
| `sliceDrawOrders` | **per-layer-per-frame 的槽序号**（每层每帧归零），**不是全局递增** | 同上 `:1482` |
| `sliceFlags` | **恒 0** | 同上 `:1483` |
| `frameOffsets` | 每帧起点（长度 == `frameMax`）；`frameCounts` 同长 | `HasPackedRuntimeData:1139-1148` |

（用内置 `GatlingPea.tres` 842 项反证：`sliceKeys == (layerIds<<16)\|mediaIds` **有 586 项不成立**；
实测内置逐帧 `sliceKeys = 0x0,0x10000,…,0x90000`（高位 layerId，**低位恒 0 = 槽序号**），
而 `sliceMediaIds = 8,9,10,15,16,12,…` 各不相同。若某层每帧只 1 个元素 ⇒ `sliceKeys` 只取 {0,65536}、`sliceDrawOrders` 全 0。）

**④ 图集不走重新打包 ⇒ 但别贴着上限。**

`TryBuildStandaloneAllocation`（`AdobeAnimateGlobalAtlasCache.cs:3191-3250`）直接
`Texture2DArray.CreateFromImages([image])` ⇒ **自带 `.dat` 不做重新打包、不检查 2048**；
唯一前置 = 至少 1 条 `mediaRect` 通过 `TryGetValidSourceRect`
（即「宽高 > 0 且完全落在 `.dat` 声明的图集尺寸内」）。
⚠️ 但 `MaxAtlasPageSize = 2048`（`:206`）仍在，图集宽别贴到 2048（实测 2043 只余 5 px）。
⚠️ 失败表现 = `WarnProjectAtlasUnavailable` **只 `GD.PushWarning` 不抛异常** ⇒ **静默不画**。

★ **`.dat` 头精确布局（`<` 小端、无对齐填充；本 Mod 逐字节验证过）** —— 偏移极易算错：

```text
off 0    f32 frameRate          4 B
off 4    u16 frameMax           2 B
off 6    u16 atlasW             2 B
off 8    u16 atlasH             2 B
off 10   i64 pixelByteCount     8 B     ← ⚠️ 不是 off 8！ 4+2+2+2 = 10
off 18   RGBA8 像素区            pixelByteCount B
────────────────────────────────────────
之后：u16 mediaCount → 每 media(PascalString 名 + 4×f32 rect)
     → u16 layerCount → 每 layer(PascalString 名 + 每帧 u16 元素数 + 每元素 30 B)
     → u16 clipCount  → 每 clip(PascalString 名 + u16 start/end)
     → u16 eventFrameCount → 每帧(u16 frame + u16 事件数 + 每事件 2×PascalString)
PascalString = u32 小端长度 + n 字节 UTF-8（无终止符）
```

⚠️ **「off 8 也能读出正确值」是个陷阱**：当 `pixelByteCount` 的高 4 字节为 0（图集 < 4 GB，恒成立）时，
`unpack_from('<q', b, 8)` 与 `@10` **都能**得到同一个值（中间 4 字节全 0）。
⇒ **别用「数值对得上」当验证**；必须用「**像素区首 4 字节 == 图集第 0 颗像素的期望 RGBA**」反查起点定死
（本 Mod `@18` 起 `22 22 28 00` = `(34,34,40,0)` = 已转透明的背景 ✓）。

★ **自检式**：完整解析到 `eventFrameCount` 表末尾，**必须恰好落在文件最后一字节**（本 Mod `466 658 == 466 658` ✓）。
这一条能一次抓出偏移错、元素数错、表长错。

#### ★★ 换「单帧静止贴图」（不是动画）—— 与多帧走同一条管线，只改 4 个量

用户说「**把贴图改成这张图**」时，给的常常是**单帧站立图**（一张 2× 放大的满画角色 PNG），
**不是** 25 帧序列。此时**别把单帧复制 50 份**去凑多帧管线 —— 直接把**帧数降到 1**，
整条链路（`.dat` → `.tres` → 场景 → 校验）一个都不用换，只改 4 个量：

| 量 | 多帧（50 帧） | 单帧 |
|---|---|---|
| `frameMax` | 50 | **1** |
| `slices` 数 | 100（2 层 × 50 帧） | **2**（2 层 × 1 帧） |
| `frameOffsets` | `[0,2,4,…,98]` | **`[0]`** |
| `frameCounts` | 全 `2` | **`[2]`** |
| 三个 clip | `BodyIdle(0,24)` / `HeadIdle(0,24)` / `HeadFire(25,49)` | **全 `(0,0)`** |
| `fireEvents` | `[36]`（开火帧） | ⚠️ **≠ `[]`**：单帧确实无「时间点」，**但多帧素材必须写真实发射帧**（本 Mod 官方素材 = `[62]`）。见下方红字 |

⚠️⚠️ **三个 clip 名必须仍然都在**（`BodyIdle` / `HeadIdle` / `HeadFire`）——
被 `ComponentSet`（`fireAnimeClips` / `spliceIdleAnimeClips`）与角色场景（`idleAnimeClip`）引用，
**缺任一个 ⇒ 发射链路断**。单帧时把 `build_tres.py` 的 clips **从 `author2.json` 读、不要硬编码**，
并 `assert` 三个名字都在（本 Mod 已改）。

⚠️⚠️⚠️ **「`fireEvents` 留空即可」是错的，曾被本技能写下并导致实机 bug**（2026-09-21 推翻）。
当时的推理是「单帧没有开火第 N 帧 ⇒ 发射反正靠插件直调 `Fire()` ⇒ 不需要事件」——**漏掉了最要命的一点：
普通射击根本不走插件，而是走「动画事件 → FireComponent」**（见「发射管线」红字链路）。
结果就是用户看到的「**攻击时只有动画、没有子弹**」。

正确口径：
- **素材有可判定的发射帧 ⇒ 必须写进 `events`**（本 Mod 官方素材 **f62** = `anim_shooting` 起点后枪口首次达峰，
  且满足 `帧 − HeadFire.start == 12`）。
- 只有**真正单帧**（`frameMax == 1`，无时间轴）时，才谈不上「发射帧」；此时**要么补一条 `@f0` 的 fire 事件，
  要么接受「不出膛」**，但**别把「留空」写成推荐做法**。
- 托管插件直调 `Fire()`（`FireComponent.cs:3429`，不受状态机约束）**只适合「大招/额外弹幕」这种叠加行为**，
  不能拿来替代常规射击。
- ★ 配套自检：断言 `.tres`/`.dat` 的 fire 事件条数、帧号、`Command=="fire"`、`Argument==""`；
  并加两条负向测试：**`Command` 改 `noop` 必须报错**、**`.dat` 尾部截 4 字节必须报错**。

**★★★ 换单帧素材的完整流程（本 Mod 实证，5 步）**：

```text
① 背景转透明   .cache/build_source_single.py     ← 新增前置步骤，见下
② 切图集+标定  .cache/build_atlas2.py    SOURCE_MODE='single'
③ 写 .dat      .cache/build_dat.py
④ 写 .tres     .cache/build_tres.py
⑤ 端到端重建   ModWorkspace/build_plant_super_gatling.py
```

**① 背景转透明是必需的，且必须用 flood fill（不能「全图同色即透明」）。**

新素材常见**实心不透明背景**（本 Mod 新图 alpha 全 255、背景实心深灰 `(34,34,40)` 占 48.4%）
⇒ 不处理游戏里会画出一个**深灰方块**。而旧素材 alpha 本来就是 0（透明底）⇒ 多帧版没这一步。

```python
TH_HARD, TH_SOFT = 6, 26     # Chebyshev 距离
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]), abs(a[2]-b[2]))
# ① 从画布外缘 BFS（4 邻域），只对「颜色≈背景(≤TH_HARD)」的像素扩散 ⇒ 置 alpha=0
# ② 软过渡：6 < d ≤ TH_SOFT 且「4 邻域里有已透明像素」⇒ alpha = 255*(d-6)/20
```

⚠️ **绝不能用「全图同色即透明」** —— 角色内部同色暗部/近黑描边会被**误伤**（本图有大量近黑描边）。
判定必须是「**颜色≈背景 AND 连通到画布外缘**」两条同时成立。
实测：判背景 74 609 px（55.2%）、软过渡 1 494 px、剩余内容 bbox `(30,19,320,349)` = 290×330（÷2 = 145×165）。

**② 分层线 `SPLIT_Y` 要挑「颈/领口」那道最细的缝。**
本 Mod `SPLIT_Y=128`（128×192 画布）→ 新素材原生 `y=256`。**先量宽度剖面再定**：
实测原生 `y=240..254` 只有 24~27 px 宽（脖子），`y≥255` 突增到 55 px（肩）⇒ 切得很干净。
（`build_atlas2.py` 单帧分支 `split = SPLIT_Y * 2 = 256`。）

**③ 锚点要重新实测（别沿用旧值）。**
量两处：`root` = **内容最低行/双脚行的水平中心**；`muzzle` = **最右绿色像素**（炮管末端）的中心 y。
本 Mod 实测 `root=(138.5,348)`、`muzzle=(314.0,125.5)`（原生坐标）⇒ ÷2。
脚本：`.cache/measure_anchor_single.py`（逐行/逐列剖面）+ `.cache/calc_anchor_new.py`（常量推导 + 新旧对照）。

**④ `origin` 由脚本自动算**（`build_atlas2.py` 写 `'ox': cx*DISPLAY_SCALE`）——
它就是「该层内容 bbox 中心（在**完整素材画布**上量、**切分前**）× `DISPLAY_SCALE`」，
所以单帧素材只要画布尺寸对，`origin` 无需人工介入；**人工只需管 3 个锚点常量**（root/muzzle/SplitY）。

**⑤ 校验脚本的期望值要成批改（本 Mod 改了 9 处）**，且**判据要语义化、别硬编码魔法数**：

```python
assert frame_max == 1
assert (aw, ah) == (492, 237)                       # 图集尺寸随素材变
assert by_name.get("body") == 1 and by_name.get("head") == 1   # 每层帧数
assert clips == {"BodyIdle": (0,0), "HeadIdle": (0,0), "HeadFire": (0,0)}
assert ev_frame_count == 0 and len(fire_frames) == 0           # ⚠️ 仅「真单帧」成立，勿推广！
#   多帧素材必须改成： ev_frame_count == 1 and fire_frames == [62]
#   且断言 events[62] == [("fire", "")]（Command 在前、Argument 空）
assert n_slices == 2 and frame_offsets == [0] and frame_counts == [2]
assert max(oxs) <= RENDER_CANVAS_W and max(oys) <= RENDER_CANVAS_H   # ⚠️ 别再用 < 90
assert not _near(got_marker, (36.0, -52.0), tol=0.5)           # 反例：不得仍是旧口径
```

⚠️ **`max(oxs) < 90` 这类硬编码判据换素材就假红**（单帧 body `oy=151.5` 天然 > 90）
⇒ 改成「渲染画布上界」语义化断言（`RENDER_CANVAS = 素材画布 × DISPLAY_SCALE`）。

**⑥ 幂等验证**：跑两遍生成器，前后逐字节比对**全部产物**（本 Mod 13 个：12 工程文件 + `dist/*.pmod`）。

#### ★ 双图层父子精灵（头独立）范式 —— 照抄内置 `GatlingPea.tscn`

```text
根 <Key>Sprite（只显示 body）   : Animation/Clip = "BodyIdle"、LayerVisible/{body:true, head:false}
  └─ Head（只显示 head）        : Animation/Clip = "HeadIdle"、LayerVisible/{body:false, head:true}
      script           = res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs  ← ⚠️ 不是 addons/ 那份
      flashAnimeData   = 与根**共用同一份** AnimeData（不是拷贝）
      parentSprite     = NodePath("..")
      Layer = insertLayerId = 2          ← 压在父精灵可见层之后
      followParentSpriteLayerId = 0      ← 被跟随的层（决定落位 + 排序带，见下）
```

> ★★ **`.tscn` 里设精灵属性只认官方那三种键**：`Animation/Clip`、`Animation/LayerVisible/<图层名>`、
> `Animation/MediaReplace/<媒体名>`（`_Set`，`AdobeAnimateSprite.cs:2989-3057`）。
> **裸 `clip` / `mediaReplaceAtlasPaths` / `mediaReplaceUse` / `name_ignore` 都不是属性**，
> 而 **Godot 对 `.tscn` 的未知属性是静默丢弃的**（实测 29 215 行 `godot.log` 里 `Invalid` 命中 **0** 次）
> ⇒ 写了等于没写。实测代价：`Head._clip` 为空 ⇒ `ApplyFlashAnimeDataChange()` 兜成 `clips.Keys[0]` = `BodyIdle`
> （茎叶段）⇒ **头上长出叶子**，白查半天。
> ⚠️ 另外 **`flashAnimeData` 必须排在所有 `Animation/LayerVisible/*` 之前** ——
> 它的 setter（`:1092-1095`）会按图层数把 `_layerVisible` 整表 `Resize` 成全 `true`，排后面写的 `false` 会被冲掉。
> ⇒ 选属性前先核 `[Export]` / `_GetPropertyList` / `_Set` 三处，**别照着别的 mod 抄**。

⚠️ `followParentSpriteLayerId` 的语义 = **被跟随的那一层**（`UpdateChild():5220-5222` `ResolveSpriteChildFollowLayer`）：
它**同时决定**① 子精灵每帧的落位 `Position = 被跟随层 pose.Origin + 父精灵 offset`（`:5262`）
与 ② 渲染排序带（`ResolveSpriteChildFollowLayer:8062-8073` → `ResolveChildSortBand:7957-7964`）。
**不参与可见性**（可见性只看 `LayerVisible/*`）。
⚠️ **想「跟住某个部件」就写那一层的 id**：官方 `ZombieNormalGatlingPea` 写 `7`（它的头部锚层）；
本工坊「僵尸换头」写 **`16`**（= `ZombiePaper.tres` 的 `anim_head1`）。
而植物「头身同源」那种自制皮肤跟 `anim_idle`(8) 基础层 —— 两种场景写的是**不同的层**，别互相照抄。
⚠️ Head 节点名必须是 `Head`、且 `unique_name_in_owner = true`（插件靠 `%Head` 找）。
⚠️ 角色场景里 `Marker2D` 的父路径是 `SpriteGroup/TransformPoint/<节点名>/Head` ——
**`ComponentSet` 写死了这条 NodePath，节点名不能改**。

#### ⚠️⚠️ 生成器脚本必须一起改，否则重跑一次就回退

自制的精灵场景 / `Marker2D` 一旦被生成器硬编码成内置指针壳，
**下次跑生成器会把它们覆盖回内置外观**（很隐蔽：单次构建看不出问题）。
⇒ 改造生成器里的 `sprite_scene_tscn()` / `plant_scene_tscn()`，
并在 `self_check()` 里加**反向断言**（`assert 内置指针壳字符串 not in 产物` + 校验 offset/Marker2D/三件套存在/animeFile）。

⚠️ **反向断言的三个细节**（都踩过）：

1. **浮点用容差**：场景文本写的是 `fmt_f()` 四舍五入后的短小数（`6.525` / `-2.51`），
   而期望值是完整精度元组 ⇒ 精确 `==` 会**假红**。统一用 `abs(a-b) <= 0.01`。
2. **加一条「不得仍是旧口径」的断言**，防「改了常量但忘了重跑生成」：
   例 `assert not near(marker, (72.0, -104.0), 0.5)`。
3. ⚠️⚠️ **换自制外观后，旧的「复用内置贴图场景」断言必须反转**。
   `check_*.py` 里那条 `chk("GatlingPea.tscn" in sp_body, "精灵场景复用游戏自带贴图场景")`
   在换外观后会**把正确产物判成 FAIL**。同批要放行的还有 **B8 类断言**：
   动画三件套（`.dat`/`.tres`/图集 png）**没有 `InferRuntimeEntry` 规则**，
   但和 `Resources/Characters/<Cat>/...` 一样属于**合法包依赖** ⇒ 必须补进白名单，
   否则「声明资源可推导类别」三条全红。

### ★★★ 首选：换「官方素材」——经典未重置版 reanim → 重置版直转

**何时走这条**：用户给的解包里能找到该角色的 `*.reanim.compiled`（+ 同名 XML）和 `reanim/IMAGE_REANIM_*.png`。
这套素材**自带完整逐帧动画**，画质与动作都优于自制（自制只能单帧或手做逐帧），所以**能拿到官方素材就别自制**。
（实测：超级机枪射手 27 轨 × 87 帧直转成功，产物 `.dat` 344 KB / 1168 slice / 两份构建闸门 52/0。）

#### 识别源
- 两套引擎资产形态**完全不同**：经典（未重置版）= `reanim` / `*.reanim.compiled` / `images/*.png`；
  重置版（Godot4+C#）= `*.tres` / `*.dat` / 图集 PNG / `*.tscn`。
- 经典素材常见落点：`<解包根>\compiled\new\<角色>.reanim.compiled`、`<解包根>\reanim\IMAGE_REANIM_*.png`。
- ⇒ **先确认目标角色在未重置版里真有 reanim**；只有 PNG 没有 reanim 时，那只能退回自制路线。

#### 经典 `.reanim.compiled` 二进制格式（已对拍验证）
```text
外壳: d4feadde + u32(解压后长度) + zlib
内层头 28 B: magic c0b493b3 | u32@4 | u32@8=轨道数 | f32@0xC=fps | u32@0x10 | u32@0x14
轨道表 @0x1C: 轨道数 × 3×u32   ← 帧数 = 条目第 2 个 u32
逐轨道: 名字(ASCII, 以 ',' 结尾) + 3 字节 + 帧数据[帧数 × 44B] + 尾部(图片名表)
帧记录 44 B = 11 个 f32: x, y, kx, ky, sx, sy, f, a, ?, ?, ?
未设置字段 = 哨兵 -10000.0f（SENT）
```
- ⚠️ **末轨的图片名表必须自己补扫**：通用解码器靠「正则找下一个轨道名」给尾部定界，**末轨没有下一轨**
  ⇒ 尾部为空 ⇒ 那张图（本例 `overlay2`）悄悄丢失。修法 = 末轨从 `data_off + 帧数*44` **扫到文件尾**再正则
  `IMAGE_[A-Z0-9_]+`。**必须加一条断言**：末轨的那张图名确实出现在最终媒体表里。

#### 映射规则（12 条，照抄即可；每条都有内置反证）
1. **轨道 → 图层 1:1，全部轨道都保留**（`layerId == 轨道序号`）。
   依据：内置 11 个「头身分离」植物里 10 个把无图控制轨（`anim_stem`/`anim_idle`/`_guide…`）**原样保留成空层**。
   ⚠️ 唯一例外 `GatlingPeaZ` 丢了开头两条并重排 —— 那是**早期转换**，别当范本。
2. **帧 → 帧 1:1**（`frameMax` = 经典帧数）。
3. **变换 = 旋转矩阵**（不是斜切）：
   `[Xx, Xy, Yx, Yy, Ox, Oy] = [sx·cos(kx°), sx·sin(kx°), −sy·sin(ky°), sy·cos(ky°), x, y]`
4. ★ **不要乘任何额外缩放**：经典 `sx/sy` **就是最终渲染缩放**。
   ⚠️ 这条推翻了「素材放大 2 倍 ⇒ `DISPLAY_SCALE=0.5`」的口径 —— **那个 0.5 只适用于自制素材**（作者自己放大画的）。混用会把角色缩错一倍。
5. **`SENT(-10000)` = 沿上一帧继承**（编译器按「与上帧相同」去重）。首帧未定义取默认 `x=y=kx=ky=0, sx=sy=1, f=0`。
6. **第 7 个 f32（`f`）是「选图/隐身」开关**：`f < 0` ⇒ 该 (层,帧) **不产 slice**；`f >= 0` ⇒ 索引**该轨自己的 `imgnames`**。
7. **无图控制轨的可见帧要产 `locator.png`（2×2 全透明）占位 slice** —— 这是内置做法
   （`PeaShooter.anim_stem` 25 帧全用 locator）。好处：保住 `sliceDrawOrders == sliceLayerIds`。
8. **clip 边界直接读控制轨的 `f` marker**：本例 `BodyIdle(0,24) / HeadIdle(25,49) / HeadFire(50,86)`。
   命名对齐内置惯例（`BodyIdle`/`HeadIdle`/`HeadFire` 是头身分离植物标准三 clip，共 11 例）。
   ★ 注意把「射击段 **+ 大招段**」都合进 `HeadFire` —— `FireComponent` 循环播 `HeadFire`，
   只给射击段就**看不到大招**。
9. **一张 `.dat` 只能内嵌一张图集** ⇒ 所有 media 打进同一张；`mediaRect` = 每张 PNG 的**完整矩形**（**不切帧**）。
   - `media id` = **显示名按大小写不敏感排序**后的序号（内置四例核对通过：`locator.png` 在 `PeaShooter` 是 0、在 `GatlingPea` 是 7，**只有忽略大小写才排得出来**）。
   - `.tres` 文本里的字典键序 = Godot 的 **ASCII 序**（两者不同，各按各的写）。
   - 显示名换写法：`IMAGE_REANIM_<PREFIX>_<REST>` → `<Prefix>_<rest 小写>.png`（如 `SUPERGATLING_` → `SuperGatlingPea_`）。
10. **根锚点**：内置植物一律 `offset = (−40,−40)` ⇒ 经典 `(40,40)` 就是「种植锚点」。
    先拿同族内置角色核对落地线（本例 `SuperGatling` 与 `GatlingPeaZ` 同为 `y=77.7`）再沿用。
11. **头身同源 ⇒ 零偏移对齐**：Head 的 `offset` 与根**完全相同**（本 Mod 两边都 `(−40,−40)`）。
    `Head.position` 写 `(0,0)` 占位即可 —— 它**不是**真旋钮：`UpdateChild()`（`:5259-5281`）每帧把它改写为
    「被跟随图层 pose.Origin + 父 offset」。⚠️ 内置 `GatlingPea`/`PeaShooter` 的 `offset=(−36,−46)`、
    官方 `ZombieNormalGatlingPea` 的 `Head.offset=(−58,−5)`/`offsetRotate=−0.25` 都是**为它们自己的头素材
    手工标定**的，**不能照抄**到别的体格上（照抄 ⇒ 实机头悬空）。
12. **插层位置** `insertLayerId = max(body 图层 id) + 1`（内置 11 例全部成立：`PeaShooter`/`GatlingPea`=8、`ReCactus`=11、`SunflowerPea`=5）。
    ⚠️ **body 判据 = 该层在 body 段内有可见帧「且用的是真实贴图」**；
    **必须排除「只用 locator 占位」的无图控制轨**（`PeaShooter.anim_stem(8)` 在 0..24 有 25 枚 locator slice，
    但 `insertLayerId` 仍是 8；把它算进 body 就会误得 9/17）。

#### 标定三件套（经典坐标 → 重置版节点）
```text
根 offset   = Head offset = −ANCHOR_ROOT        （内置植物 ANCHOR_ROOT = (40, 40)）
Head.position = (0, 0)                          （死值/占位；真旋钮就是上面那行 offset）
Marker2D    = 炮口(经典坐标) − ANCHOR_ROOT      （写在 Head 子节点下，local 坐标；与 offset 无关）
```
- 炮口求法：取「炮管完全伸出」那一帧的不透明区最右列中点（`x,y` 经旋转矩阵变换后）。
- ⚠️ 传统「换成像素在画布内的几何中心」求 `origin` 那套**在官方素材下不需要** ——
  直接照抄经典 `x,y` 与 `sx,sy` 就对了（见规则 3、4）。

#### 生成器与场景要一起改（否则重跑即回退）
- 让 `sprite_scene_tscn()` **由标定结果文件（如 `skin_params.json`）驱动**：
  - `Animation/LayerVisible/<每个图层名> = true` —— 覆盖**全部**图层（含无图控制轨）+ `AnimeClips`/`AnimeEvents` 两张内建表；
  - `Animation/MediaReplace/<每个媒体名> = null` —— 覆盖**全部**媒体（含 `locator.png`）；
  - Head 节点：`Layer = insertLayerId`、`insertLayerId`、`followParentSpriteLayerId` 三者同值，
    `parentSprite = NodePath("..")`、`position = (0,0)`、`offset` 与根相同。
- `self_check()` 加**反向断言**：拒绝旧自制值（例 `(−69.25,−174.0)` / `(87.75,−111.25)` / `(31.74,−17.82)`）。
- ⚠️ **`main()` 的顺序**：**先写盘、再自检**，并把「生成器升级导致磁盘内容漂移」报为 **info 而非 FAIL**；
  否则「换生成器后第一次跑」必然假红（磁盘还是上一版）。

#### 验证器：四层独立 + 负向测试（**新增，必配**）
**四层必须互相独立、只读磁盘产物、且不复用生成器代码**，否则就是「比内存文本」的假绿：
| 层 | 内容 | 关键判据 |
|---|---|---|
| ① 源 ↔ `.dat` | 独立再解码 reanim，对**全部 (层,帧)** 重算 carry-forward + f 选图 + 旋转矩阵 | mediaId 与 6 个 f32 **逐位**一致；媒体名集合/id 序反推；`mediaRect` vs 源 PNG 真尺寸 |
| ② `.dat` | 自写解析器按引擎规格走完全文 | ★ **解析终点 == 文件总长**；★ **像素区逐字节 == 图集 PNG 真解码像素** |
| ③ `.tres` | 抽 `Packed*Array` 与 `.dat` 互证 | `sliceTransforms` **f32 位级**一致；`sliceKeys=(layerId<<16)\|槽序号`；`sliceDrawOrders==sliceLayerIds` |
| ④ 场景 | Sprite + 主场景 | offset / `insertLayerId` / clip / `Marker2D` / 图层媒体名单 / 相对路径 + **旧值反例** |
| ⑤ 不变量 | 结构性 | 图层**不跨** body/head 边界；`insertLayerId == max(body 真实贴图层)+1`；标定文件全量一致 |

- ★ **写自己的 PNG 解码**（zlib + 5 种 filter + 调色板/tRNS）才算真独立；**官方 PNG 常是调色板类型 `ct=3`**，只支持 RGB/RGBA 会直接 `AssertionError`。
- ★ **负向测试必须做**（`--negative`）：故意写坏**副本**（图集改 1 bit / 场景 offset 改旧错值 / `.tres` frameMax 改错），
  断言**必须报错**。不报错 = 断言失效（假绿）。实测 3/3 报错。

#### 官方素材路线专属陷阱（都在实测中踩到）
1. ⚠️ **末轨图片名表**（见上）—— 会静默丢图，必须补扫 + 断言。
2. ⚠️ **`.tres` 的浮点格式化会把 `-0.0` 写成 `0`** ⇒ 位级比对必须把 **`±0.0` 视为等值**
   （`−sy·sin(0°)` 天然产生 `−0.0`；不处理则上千个浮点里必出假红）。
3. ⚠️ **`layerDictionary` 除图层名外还含 `AnimeClips` / `AnimeEvents` 两张内建表**（值 = 图层数 / 图层数+1）
   ⇒ 断言「字典 == 图层序」会假红。
4. ⚠️ **`LayerVisible`/`MediaReplace` 在根与 Head 两块节点里各写一份** ⇒ 正则统计会翻倍，需**去重**。
5. ⚠️ **资源路径断言别用 `path="…"` 裸正则** —— 会误捕 `NodePath("…")` / `node_paths=PackedStringArray(...)`；
   限定 `^\[ext_resource[^\]]*?path="([^"]+)"` 并按行匹配。
6. ⚠️ 换官方素材后，**旧管线的验证器要退役**：它们硬编码 `frameMax=1`（单帧）/ 2 media / 176×192 画布，
   对多帧官方素材只会**报误导性 FAIL**。做法 = 统一在文件头插 **LEGACY GUARD**
   （读 `.dat` 的 `frameMax`，`!= 1` 时打印 `[SKIP]` 并 `rc=0` 退出），或改名为 `legacy_*`。

### 血量 / 能不能直接种（`plantCover` + packet override，两个都是纯数据）

这两条最常被问，而且**都不需要写插件**。

**血量**：`characterConfig.hitpoints`（`TowerDefenseCharacterConfig`，**类默认 300.0**）。
由 `TowerDefenseCharacterInstance._Init:317-320` 搬进实例：
`hitpointsBase = config.hitpoints; hitpoints = hitpointsBase + hitpointsNearDeath;`
⇒ 在 `…/Config/TowerDefensePlant<Key>.tres` 加一行 `hitpoints = 1000.0` 即 1000 血。
⚠️ 写在与**类声明顺序**一致的位置（`hitpoints` 紧跟 `name`），否则编辑器保存会重排。

**能不能种在空地上 = `plantCover`**：

* `plantCover` 是「**可覆盖的底座名单**」。**非空 ⇒ 这张卡就只能种在名单里那些植物上**，
  空地种不上。闸门 `TowerDefenseCellInstance.CanPacketPlant:787-800`：
  ```csharp
  if (packetConfig.GetPlantCover().Count > 0 && !noLimit) {
      foreach (… characterList …) if (… GetPlantCover().Contains(name)) return true;  // 有底座 ⇒ 允许
      if (!packetConfig.GetCoverCanDirectPlant()) return false;                       // 没底座 ⇒ 拒
  }
  ```
* ⚠️ **查中文名要去 `Asset/Translate/Translate.csv`**：`PlantPeaShooter` = **双发射手**
  （不是「豌豆射手」）。别凭英文猜。
* ⚠️⚠️ **`GetCoverCanDirectPlant()` 只在 packet 有 `_override` 时才读，否则硬编码 `return false`**
  （`TowerDefensePacketConfig.cs:500-507`）⇒ **改 `characterConfig` / 改 `plantCover` 都做不到
  「不改底座还能直接种」**，必须挂 packet override。

**解法（纯数据）**：卡片里内联一个 override 子资源，**只开一个字段**：

```ini
[ext_resource type="Script" path="res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/TowerDefensePacketOverride.cs" id="3"]

[sub_resource type="Resource" id="PacketOverride_direct_plant"]
script = ExtResource("3")
coverCanDirectPlant = true
metadata/_custom_type_script = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/TowerDefensePacketOverride.cs"

[resource]
…
override = SubResource("PacketOverride_direct_plant")
```

* **官方先例**：`Asset/Config/Level/TowerDefense/Challenge/Gold/Challenge_Level2_3.tres`
  给 `PlantGatlingPot` 开的就是它（全解包仅 2 例）。照抄即可，不是野路子。
* **为什么只写一个字段就够**：`TowerDefensePacketOverride` 的默认值全是「不覆盖」语义
  （`type=NOONE` / `cost·costRise·costMultiple·packetCooldown·startingCooldown·weight·wavePointCost = -1` /
  `plantCover=[]`（`GetPlantCover` 在 **Count>0** 时才用它 ⇒ 空表回落，**底座名单保住**）/ `hypnoses=false`）；
  `islimitGridNum` 默认 `true`，与无 override 时的硬编码 `true` **同值**（中性）。
  唯一无条件生效的是 `characterOverride`，它**默认非 null**（`new TowerDefenseCharacterOverride()`），
  但逐字段是**空操作**（`scale/hitpointScale/walkSpeedScale/animeSpeedScale = -1`、四个数组为空、
  `invisible=false`、`_hasCanMowerMoveOverride=false`）⇒ 不碰血量/缩放/动画。**因此别往 override 里多写字段**。
* 好处 = **既能在空地直接种，又保留「种在底座上升级」**（追加能力，不是替换）。
* ⚠️ **tres 属性名 = C# 字段名去掉前导下划线**：`_override` → `override`。
* ⚠️ 想**免疫关卡 override**（关卡用 `packetOverride` 会在 `PlantAtCore` 里临时顶掉 `_override`，
  于是又变回必须底座）⇒ 只能 `plantCover = []`，**代价是失去升级路**。二选一，问过用户再定。
* ⚠️⚠️ **`plantCoverAll` 是死字段**：全解包只在编辑器 UI 里被绑定，**运行时从未被读取**，别当开关。

**断言这两条时的坑**：从 `.tres` 里切 override 子资源，**必须切完整的
`[sub_resource type="Resource" id="…"]` 整行**；用 `id="…"` 切片会残留一个 `]` 被当成字段名 ⇒ **假红**。
另外「只允许写这几个字段」这类断言一定要配一个**反向对照**（喂一份故意多写字段的假 body，必须报出来），
否则切片一写错就变成永远为真的假绿。

### ⚠️ 纯数据**做不到**的东西（别白试）

| 想要 | 为什么不行 |
|---|---|
| **概率触发**（如 10% 大招） | `FireComponentFireProjectileConfig` 无 probability 字段 |
| **持续/延时改模式**（如 5 秒内连发 300 颗） | `FireComponentDefinition` 无对应字段，状态机只有 `idle/attack/restore` 且 `GuardDefinition = null` |
| **真随机** | 唯一随机源 `OnFireVolley(ulong randomSeed)` 种子是**确定性**的（`NetworkDeterministicSeed.ForCharacterEvent`），为联机同步刻意禁掉真随机 |

→ 这三样的**唯一出路是托管脚本 Mod**（`runtimeAssembly`，见下节，**已实测可用的完整配方在
`植物类 / 角色类` 那一节末尾 + 本文件的「托管代码 Mod」节**）。`overrides` 覆盖原版
`FireComponent` 污染面太大（会波及所有植物），不建议。**动手前先跟用户确认取值。**

### ✅ 玩法类托管插件的标准姿势（概率触发 / 连射 / 真随机）

样板（两份，覆盖两种打法）：
- `runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs` —— 超级机枪射手：**数据侧 1 条直射配置（`dir=0`）** +
  插件订阅 `OnFireReady` ⇒ 每 1.5s 发 **7 颗直线**（逐颗 `dir=0`，间隔 0.1s），10% 概率触发 5s/300 颗 ±15° 散射（**逐颗**粒度）；
  同时用 `fireEventName="modfire"` **掐掉原版动画事件链**（动画照播）。
- `runtime_src_zombie_super_gatling/SuperGatlingPaperRuntimeEntry.cs` —— 超级机枪读报僵尸：1.5s/7 颗 + 10% 大招 5s/300 颗 ±15°（**逐颗**粒度）。

```
扫场景找自己的角色（按 config.name，❌ 别按类名——内置 GatlingPea 会误伤）
  → character.componentManager.GetRuntime<FireComponent>("character.fire")
  → ★ 订阅 fire.OnFireReady（delegate，AttackEntered() 里只发一次；FireComponent.cs:255/3258）
      · 或 fire.OnFireVolley（每条 config 各发一次，须用时间窗去抖；FireComponent.cs:673）
  → 命中/每次攻击则用 Time.GetTicksMsec() 做节拍器，逐颗调 FireComponent.Fire()
      · 逐颗 = 每发前改写 fireProjectileList[i].dir 再 Fire()（数据侧只留 1 条 config，见下）
      · 想让原版不再自动开火 ⇒ fire.fireEventName = "modfire"（动画里没有这个名字）
      · 纯数据做不到的另一样：自定义皮肤动画会「静止」，插件需设 forceLocalRender + forceCpuPoseRender（见下）
```

关键结论（都有源码位置，别自己重猜）：

- ⭐ `FireComponent.Fire()`（`FireComponent.cs:3429`）是 **public 且不受状态机约束**：
  只检查 battlefield/alive/parent 有效 + 每条配置的 `fireEventNeed`/`fireNumSkip`，
  然后**逐条执行 N 条发射配置** ⇒ 一次调用 = 一轮 N 颗扇形。
  **它与常规攻击走的是同一段代码**，所以命中盒/伤害/行号行为必然一致 ——
  不用担心"插件子弹打不中僵尸"。这是插件连射最安全的入口。
- ⚠️⚠️ **`Fire()` 一次调用遍历全部 `fireProjectileList`**（引用拷贝 `_fireProjectiles`）⇒
  **要「逐颗」发射（每颗不同角度）时，数据侧必须收敛成恰好 1 条 `FireComponentFireProjectileConfig`**。
  否则：N 条 config × 插件调 N 次 `Fire()` = **N² 颗重叠**（曾差点写错 —— 7 条 config × 7 次调用 = 49 颗）。
  收敛后「一次 `Fire()` = 一颗、角度自定」才成立（见下方「逐发控制」条）。
- 一次齐射会**逐条配置**调 `EmitFireVolley()`（7 条 → 最多 7 次信号）⇒ 用 `OnFireVolley` 必须**去重**，
  否则一次攻击会掷 7 次骰子。**更省事的替代：改用 `OnFireReady`**（`FireComponent.cs:255` 的 delegate，
  在 `AttackEntered()` `:3258` 里**只发一次**）⇒ 天然「本轮攻击开始」信号，无需去抖。
- ⚠️ **掐掉原版自动开火（避免「一次攻击 = 原版一发 + 插件 N 发」）**：
  设 `fire.fireEventName = "modfire"`（public 字段，默认 `"fire"`，`:343`）。
  `AnimeEvent()`（`:3365`）拿 `fireEventName.Split("&")` 当白名单 ⇒ 名字不存在则**整块跳过**；
  **`fireAnimeClips` 不动 ⇒ 动画照播**。⚠️ 但这样一来 `.dat`/`.tres` 里那条 `fire` 事件就**打不出弹了**
  ⇒ 与「events 必须有 fire 条目」那条铁律**不能同时用**，二选一（插件驱动用这个，纯数据驱动用那条）。
- 节拍用 `Time.GetTicksMsec()` 而**不是帧数**：攻速/掉帧都不影响总时长。
  再加单帧上限（如 `MaxVolleysPerFrame = 6`）防掉帧时雪崩式创建几百个子弹对象。
- ⚠️ **`CharacterComponentRuntime` 不是 GodotObject**（`Script/Component/Runtime/CharacterComponentRuntime.cs`
  是纯 C# 抽象类）⇒ 它**没有** `GetInstanceId()`、**不能**传给 `GodotObject.IsInstanceValid()`。
  判活只能 `fire != null && !fire.IsReleased && fire.Owner != null && GodotObject.IsInstanceValid(fire.Owner)`；
  去重只能 `ReferenceEquals`。（编译期就会报 CS1503/CS1061，别以为是 API 找错了。）
- 真随机用 `RandomNumberGenerator.Randomize()`。代价：**联机会与主机不同步**（框架的
  `NetworkDeterministicSeed` 刻意禁真随机），交付时如实标注这是取舍。
- ⭐⭐ **逐发控制（每颗不同角度）—— 改 `fireProjectileList[i].dir`，一定生效**：
  ```csharp
  // FireComponent.cs:443
  public Array<FireComponentFireProjectileConfig> fireProjectileList = new Array<…>();
  // FireComponent.cs:447
  private readonly List<FireComponentFireProjectileConfig> _fireProjectiles = new List<…>();
  // FireComponent.cs:919-929  CopyGodotArray —— ★ 逐元素同引用拷贝
  target.Clear(); for (…) target.Add(source[i]);
  // FireComponent.cs:965（在 :931 private void RefreshExportedArrayCaches() 里）
  CopyGodotArray(fireProjectileList, _fireProjectiles);
  // FireComponent.cs:3462 —— 每一发都现场读 dir，不是缓存
  Vector2 velocity = cfg.speed * Vector2.FromAngle(Mathf.DegToRad(cfg.dir));
  ```
  | 操作 | 生效？ |
  |---|---|
  | 改元素（`cfg.dir = 角度`） | ✅ 两个容器同时可见 |
  | 往 `fireProjectileList` 增删元素 | ❌ `_fireProjectiles` 不跟 |
  ⇒ **只改不增删**；每发前**重新取一遍** `fire.fireProjectileList`（不缓存列表/元素）。
  这样「一次 `Fire()` = 一颗、角度自定」就成立了 —— 与植物版「一轮 N 条配置扇形」互补，看需求选。
- ⭐ 要「**恰好 N 颗 / 恰好 T 秒**」⇒ **按颗数算时刻**：第 k 颗的计划时刻 = 起点 + k×(T/N) ms。
  **别**用「每次 `next += 间隔`」（浮点累加漂移）；**也别**用「N 颗一轮 × M 轮凑总数」
  （那套只在「一轮是原子行为、不可拆」时才需要，如植物版一发 = 7 颗齐射 ⇒ 43 轮 = 301 颗）。
- ⚠️ **暂停 / 长卡顿保护**：`SceneTree.process_frame` 在游戏暂停时**照常发信号** ⇒
  不管就会攒下几百毫秒的「欠账」，恢复时一口气喷出来。对策：两帧间隔 > 阈值（如 250 ms）时，
  把该角色的**所有时间轴整体后移同样间隔**（欠账作废、不补发）；另加「每帧最多补几颗」防雪崩。
- ★★ **自定义皮肤动画「完全静止、按 ESC 暂停一次只跳一帧」⇒ 插件设 `forceLocalRender=true` + `forceCpuPoseRender=true`**：
  ```csharp
  // AdobeAnimateSprite.cs —— 两个都是 public 的普通属性（非 [Export]）⇒ 只有运行时插件能改
  public bool forceLocalRender { … }       // :1141
  public bool forceCpuPoseRender { … }     // :1166
  // :8415 ShouldUseGlobalRuntimeManager() ⇒ _forceLocalRender 为真时返回 false ⇒ 绕开全局姿态图集
  ```
  真因链：自定义 Mod 的 `AdobeAnimateData`（`.tres` + standalone `.dat`）**不在全局图集清单**里
  ⇒ `GpuPoseTextureRid` 无效 ⇒ `_runtimeGpuClockInterpolationActive == false` ⇒ 姿态定格，
  只有 `RequestNodeRedraw`（ESC 暂停菜单→恢复会触发）才前进一帧。
  读法：`mod 内所有用自己皮肤数据的 AdobeAnimateSprite` 都要打标 ⇒ **每 N 帧（如 10）递归全树扫描 + 幂等**
  （战斗/图鉴/选卡/种植预览的实例是各自独立创建的，不打标就有一处静止）。
  引擎先例：`PacketPickControl.cs:401-402`（卡片预览精灵，两开关一起设）。
  ⚠️ 这是**绕开**缺失的全局姿态图集，不是补一张（后者无法随 mod 包分发）。
- ⚠️ **`FireComponent.sprite` 是「Head 本体」不是角色根**——写头身同步/取父节点前先确认：
  ```csharp
  // FireComponent.cs:1241
  sprite = ResolveOwnerNode<AdobeAnimateSprite>(Definition.spritePath);   // 路径 = …/TransformPoint/<精灵>/Head
  ```
  ⇒ 插件拿到的是 `Head`（其父才是 body）。旧写法「`head = 传入节点.GetNodeOrNull("%Head")`」会让
  `body == head` ⇒ **自环、头身同步变空操作**。正确：先判 `node.Name == "Head"` 则 `body = node.GetParent()`，
  否则（拿到根）才 `%Head`。
- 场景根**不带** `mod_character_script_binding="CompanionOnly"` 时**不需要伴生脚本**
  （`CharacterRequiresCompanion` 只在带该元数据时才要求），走标准 `IXWModRuntimeEntry` 即可。

### ⚠️ 翻译表是「编辑器专用」

`ModLoader` 里**一次** `TranslationServer.AddTranslation` 都没有 ——
`translations` 清单字段只有编辑器侧（`XWModManifestSyncService` / 多语言面板 / 校验）会读。
→ **游戏内植物名会显示成原始 key**（如 `TOWERDEFENSE_PLANT_XXX_NAME`）。
仍应按编辑器规范写 `Localization/translations.csv`（表头 `key,zh_CN,en_US`，键按 `OrdinalIgnoreCase` 排），
但在交付说明里**必须如实标注**这个边界。

### 僵尸类（`Character` 的 Zombie 子类）——与植物的四处关键差异

路径形状与植物**完全一样**（6 段，类别换 `Zombies`），包结构/命名硬约束照抄上一节。
但下面四点跟植物**不一样**，照着植物抄会踩空。样板：
- `.workbuddy/ModWorkspace/DiscoGargantuarPult/`（暴走舞王伽刚特尔投石车僵尸 = 复用 `ZombieImppult` 数据 + **投掷替换**插件）；
- `.workbuddy/ModWorkspace/SuperGatlingPaper/`（超级机枪读报僵尸 = 复用 `ZombiePaper` 数据 + **发射**插件 + 包内护具覆盖）。

**差异 1：僵尸卡入库只补一处，三处同时生效**（植物要补「共享卡库 + 派生库 + 图鉴兜底」）
```csharp
// Almanac.cs:220
zombiePacketBank = TowerDefenseManager.GetPacketBankData("GeneralZombie");  // ★ 同一实例，不是拷贝
// Almanac.cs:219
plantPacketBank  = XWModContentCatalog.WithPlants(GetPacketBankData("GeneralPlant")); // 植物页★是深拷贝
```
⇒ 往 `GeneralZombie.category["Zombie"]` 追加卡 key，**图鉴僵尸页 / 选卡界面 / 关卡编辑器同源同变**。
再按 `Include` 闭包补派生库（实测 `GeneralZombie` → `['GeneralZombie','TotalZombie','Total']`）。
刷新图鉴同样**只在反射读到 `_zombieInitialized == true` 时才调 `InitZombie()`**（`Almanac.cs:39/41/450/411`）。
⚠️ 僵尸分类键是 `"Zombie"`（不是 `Gold`/`White` 那套植物色卡）；`GetZombieList()` 只认这个键，
`TotalZombie`/`Total` 靠 `Include` 闭包继承 —— 所以**别只补 `TotalZombie`**。

**差异 2：换「投掷出来的单位」纯数据做不到**（= 上一节「非它不可」的第 ④ 类）
投石车僵尸的投掷单位是**硬编码**的：
```csharp
// Asset/Anime/Character/Zombie/Chapter5/Imppult/Scene/TowerDefenseZombieImppult.cs:135
var cfg = TowerDefenseManager.GetPacketConfig("ZombieImp") as TowerDefenseZombieImpBase;  // ★ 写死
```
`CatapultComponentDefinition.projectileName` 只是**美术层**名字（换它不改变真投出来的单位）。
拦截接缝（时间线已核）：
```
AnimeEvent("fire")                     // TowerDefenseZombieImppult.cs:67-76
  ├─ _catapultComponent.OnFireAnimeEvent();   // CatapultComponent.cs:568 → OnFireEvent?.Invoke()
  │                                           // 事件声明 CatapultComponent.cs:139  => ★ 这一段最早
  ├─ ImpSpawn();                              // ★ async void：先 await ToSignal(…, PhysicsFrame) 才 AddChild
  │                                           //   (:134→:142)  => 事件后【隔一物理帧】小鬼才进树
  └─ UpdateProjectileVisual();
```
⇒ **订阅 `OnFireEvent` 领票 → 监听父节点的 `child_entered_tree`（同步回调）→ 在
`config.name == "ZombieImp"` 的子节点刚进树时 `QueueFree()` 换成目标包**。
父节点取 `TowerDefenseGroundItemBase.characterNode`（`public static Node2D`）。
投掷物理全走公开 API 复刻：`GetFallTime()`（无参）、`OnLand`（`LandEventHandler`）、
`TowerDefenseCharacter.SetLogicalGlobalPosition(Vector2)` / `GetLogicalGlobalPosition()`（**有重载**）、
`GetGroundHeight(double)`、`SetHitpointAndScale(double, Vector2)`、`Hypnoses(double time=-1.0, …)`（**带默认参数**）、
`Idle()`；`instance.hitpointScale` / `instance.hypnoses`。
⚠️ `TowerDefensePacketConfig.Create()` **只创建、不入树也不 Walk** ⇒ 想在落地后开始走，
必须自己订阅 `OnLand` 后 `CallDeferred("Walk")`，并配一条**保险丝**（落地事件没等到时兜底）。
⚠️ 别的投掷系僵尸（`TowerDefenseZombieGargantuarBase.impName` 是 `[Export]`）另有投掷字段，
但**凡是走 `ImpSpawn()` 这条路的**（Imppult）都只有插件一条路。

**差异 3：`attackType` / 体型 / 碰撞这类字段在 `TowerDefenseZombieConfig` 上**
「碾压」= `attackType = "Smash"`（另有 `smashAttack` 与 `attack` 分开写）。
血量语义同植物：`hitpoints` 是**基础血量**，总血 = `hitpoints + hitpointsNearDeath`，
`hitpointsNearDeath` 同时是**濒死线**与濒死流血速率 ⇒ 要「总血 3000」写 `hitpoints=2830` + `hitpointsNearDeath=170`。
字段顺序按**类声明顺序**写（`name` 后面紧跟 `hitpoints`…），否则编辑器一保存就重排。

**差异 4：护具（Armor）——僵尸专属的第二条命，改它要在**包内**做**
角色可以出生就戴护具（场景里 `currentArmor = ["Paper"]`），护具是**独立血量层**。

* 护具数据 = `<Key>/Armor/<Key>ArmorData.tres`（`CharacterArmorData`，6~N 项
  `armorDictionary = { 名: { slotConfig, typeData } }` + 三个 `fliter*Dictionary`）
  + `<Key>/Armor/Config/<Key>Armor<名>.tres`（`ArmorSlotConfig`）。
  内置版本在 `res://Asset/Anime/Character/Zombie/<章>/<角色>/Armor/`，**整份抄进包再改**。
* ⚠️⚠️ **改护具血量要改「SlotConfig 的 `damagePoint`」，不要去动 `res://Registry/Armor/Config/*.tres`**
  （那是全局注册表，改了会波及**所有**戴该护具的角色）：
  ```csharp
  // TowerDefenseArmorInstance 构造函数
  typeData = TowerDefenseArmorRegistry.GetArmorType(slotConfig.armorName);
  damagePointBase = ((slotConfig.damagePoint >= 0.0) ? slotConfig.damagePoint : typeData.damagePoint);
  ```
  ⇒ 包内新建 `Armor/Config/<Key>ArmorX.tres`（只写 `armorName` / `replaceMediaName`（逐字沿用内置）/
  `damagePoint = N` / `destroyFliter`），`ArmorData` 里**只把该护具的 `slotConfig`** 换成它，
  `typeData` 仍指 `res://Registry/Armor/Config/<名>.tres`。
  ⚠️ `ArmorSlotConfig` 字段顺序按类声明：`armorName → replaceMethod → replaceMediaName → slotPath →
  offset → rotation → scale → alphaMultiplier → damagePoint → [Behavior] behaviorIds → behaviors →
  openFliter → closeFliter → destroyFliter`。
* **「几类护具」= `ARMOR_METHOD_FLAGS` 的位**（`TowerDefenseEnum.cs`）：
  `SHIELD = 4`（护具层/二类）、`DAMAGEABLE = 0x40`、`DROPABLE = 0x80`、`ABSORBOVERFLOW = 0x200`。
  内置 `Paper.armorMethodFlags = 68 = SHIELD | DAMAGEABLE`（**不含 `DROPABLE`**）⇒ 天生就是「二类防具」。
  本包**不改任何 flag**，只换血量。
* ⚠️ **护具子目录必须靠「角色包依赖」规则放行**（`ModLoader.IsCharacterPackageDependency`：
  角色包目录下任意 ≥5 段文件都算包依赖）⇒ `Armor/` + `Armor/Config/` 天生合规，不用额外声明。
* ★ **「护具碎 → 某种行为」先看内置脚本有没有现成的**：例如读报僵尸的
  `TowerDefenseZombiePaper.cs` 自带 `ArmorHitpointsEmpty("Paper")` → `SendStateEvent("ToGasp")` →
  `AnimeCompleted("Gasp")` → `timeScaleInit = 3.0; angry = true; Walk();`
  ⇒ **护具碎后暴走 + 移速 ×3 是白送的**，只要场景 `script` 指向那个内置 `.cs` 即可，一行插件都不用写。

**僵尸包同样可以复用游戏自带的 `.cs` 脚本**（`type="Script" path="res://Asset/…/TowerDefenseZombieImppult.cs"`）：
`res://` + 指向游戏自带 ⇒ `SanitizeCharacterTextResource` 放行；不是 `CSharpScript` ⇒ 不触发嵌脚本闸门；
**不写** `mod_character_script_binding` ⇒ 不触发 `CharacterRequiresCompanion`。
（已用于投掷系 + 读报僵尸两例，但**实机尚未验证**，交付时如实标注。）

**差异 5：换「头」（僵尸身 + 植物头）= 抄官方 `ZombieZamboniGatlingPea` 的范式，零自制素材**

官方先例就在眼皮底下：`Asset/Anime/Character/Zombie/Chapter2/Zamboni/Sprite/GatlingPea/ZombieZamboniGatlingPea.tscn`
—— 僵尸 Sprite 场景外面挂一个 `type="Node2D"` 的 **`Head` 子节点**，`flashAnimeData` 指**内置植物**动画：

```ini
[node name="Head" type="Node2D" parent="." node_paths=PackedStringArray("parentSprite")]
script        = ExtResource("…")    # res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs
flashAnimeData = ExtResource("…")   # ★ 内置 Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tres
position      = Vector2(0, 0)       # 定位全靠 offset；想抬高头只改 position.y（负 = 抬高）
scale         = Vector2(-1, 1)      # 僵尸朝左 ⇒ 头部动画镜像
offset        = Vector2(-36, -46)   # ★ 抄内置 GatlingPea.tscn 的 Head
trueFrameRate = 180                 # 内置头部动画帧率（身体那套是 12）
clip          = "HeadIdle"
parentSprite  = NodePath("..")
followParentSpriteLayerId = 16      # = 身体里「头部那一层」的图层号
insertLayerId = 16
```

* `followParentSpriteLayerId` / `insertLayerId` **不能瞎填**：取该僵尸 `.tres` 的 `layerDictionary`
  里头部那层的**值**。读报僵尸 `ZombiePaper.tres` 是 `anim_head1 = 16`；`ZombieZamboni.tres` 是 `Zombie_head = 11`。
* ★★ **身体必须在场景里 `layerVisible` 关掉原头那几层**，否则**原版头从头盔底下透出来**。
  读报僵尸要关 `15..21`（`anim_hair` / `anim_head1` / `anim_head_look` / `anim_head_pupils` /
  `anim_hairpiece` / `anim_head_jaw` / `anim_head_glasses`）+ `0`(`_ground`) + `24`(`AnimeClips`)。
* 战斗场景里那个 `ExtResource` 要指**本包** `../Sprite/<Key>.tscn`（不是内置 `ZombiePaper.tscn`），
  否则等于在战斗场景里又挂一次 Head。
* `offset` 一动 `Marker2D` 炮口跟着跑偏（出膛点就废了）⇒ 抬高头用 `position`，**别动 `offset`**。
* 收益：**零自制贴图 / 零自制动画** ⇒ 画风必然一致，也不用碰 `.dat`/图集/`skin_params.json` 那条重管线。
* 取舍：僵尸若**不播开火动画**（读报僵尸无 `HeadFire`，发射由插件按毫秒节拍驱动），
  头会**恒停 `HeadIdle`**（随身体走、但不自己开火）。要头会开火就得自制带 `HeadFire` 的僵尸动画。

**差异 6：★★ 图鉴僵尸页会「出现两条」——两条来源都删不得，只能在图上侧运行时去重**

`Almanac.InitZombie()`（`Almanac.cs:411-435`）**两条独立来源、且都不去重**：

| # | 来源 | 源码 | 何时命中 |
|---|---|---|---|
| ① | 共享卡库的 `Zombie` 分类 | `:416-425` `foreach zombiePacketBank.GetCategory("Zombie")` | 插件把卡补进 `GeneralZombie`（要做「能选到」就**必须**补） |
| ② | 引擎的 Mod 内容目录 | `:427-430` **无条件** `foreach XWModContentCatalog.GetPackets(plants:false)` | 引擎按 `ModLoader.cs` 的 `("Resources/Cards/", "Packet")` 映射，把包内卡自动注册为 `Packet` |

**两条都删不得**（决定性证据，别再试了）：

* 删 ① ⇒ `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync:509-514` 直读
  `packetBankData.category[分类]`，而 `ResourceManager.BuildExpandedPacketBanks():638-647`
  **只从内置 `PacketBankResource.json` 构建、完全不合并 Mod 注册** ⇒ **选卡界面直接选不到**。
* 删 ② ⇒ `TowerDefenseManager.GetPacketConfigReadOnly(key)` 返回 `null`
  （`TOWERDEFENSE_PACKETS` 来自 `ResourceManager.cs:529` ← `roots.PacketPathByName`）。

⇒ **唯一可行：图上侧运行时去重**。反射 `Almanac._zombieLogicalConfigs`
（`private readonly List<TowerDefensePacketConfig>`）拿**列表引用**，**从后往前**删 `saveKey` 命中的重复项
（从后往前 ⇒ 保留最靠前那条、顺序不变），再调 **public** 的 `QueueZombieVirtualRefresh()` 重建虚拟列表。
共享卡库 / `_packetPaths` / 解锁状态**一个字节都不动**。

⚠️ **别加 `%Almanac` 节点、别提前 `Instantiate()`** —— 图鉴刻意**懒初始化**（`Almanac.cs:391-397`），
项目里有测试（`AlmanacVirtualizedResidencyRuntimeTest`）专门防「提前实例化 / 提前初始化」；
而 `QueueZombieVirtualRefresh()` **自带 `_zombieInitialized` 守卫**，未初始化时直接返回 ⇒ **安全**。
先判 public `ZombieLogicalEntryCount <= 1` 快速返回，避免每帧无谓反射。该路径单独一个「只报一次」标志。

> **对比植物页**：`InitPlant()`（`:311-356`）是**按分类分页**的（`:324-328` 只读当前分类）
> ⇒ 植物页天然不会把两条拼一起。所以这是**僵尸页专有**形态问题
> （植物那边过去踩的是「Mod 植物被单列一类」，不是「同一条出现两次」）。

## 托管代码 Mod（已实测可用）

`runtimeAssembly = "Runtime/ModAssembly.dll"` + `runtimeEntryType`（实现 `IXWModRuntimeEntry`）
+ `runtimeApiVersion = 1` + `runtimeAssemblyPolicy = "required"|"optional"`，
且 `schemaVersion` 必须 = 2（`XWModRuntimeCompatibility.ValidatePackage`）。
运行期可调 `XWModRuntimeRegistry.Register(...)`，能拿到 `TowerDefenseManager` /
`BattleEventBus` / `ResourceManager` / `ObjectManager`（`PVZApiRegistry` 暴露的 4 个类）。

### 什么时候非它不可
**纯数据改不动的东西**，目前四类已实测：

**① 换自定义战斗背景图**：
`mapTexturePath` 只喂 `GetMapTexture()`（裸 `ResourceLoader.Load`，**不查 Mod 贴图表**）；
真正的背景是地图**场景**里那个 `Sprite2D` 的 `[ext_resource] Texture2D`。而 Mod 图片**进不了 `ResourceLoader`**：
`XWModExternalMediaLoader.TryLoadTexture` 是手工 `Image.LoadPngFromBuffer` + `ImageTexture`，
**不注册 `ResourceFormatLoader`**，导出构建又没有 import 管线；且 Mod 一律解到
`user://ModsCache/<pmod名去扩展>/`，影子不了 `res://`（pck 里）。
`provides.Texture` 只是往 `XWModRuntimeRegistry.RuntimeTextures` 塞一个 key，
**运行时没有任何代码消费它**（全仓只有 `Tests/` 在查）⇒ 纯数据换不掉背景。

**② 玩法效果：概率触发 / 延时改发射模式 / 真随机**（见上一节的「标准姿势」）：
`FireComponent` 的公开 API 够用，**不需要** `overrides` 覆盖原版类。

**③ 让 Mod 卡「能被选到」/ 出现在图鉴的内置分类里**（卡库类需求，已实测）。
先记住这条因果链，别改错地方：

| 玩家看到的东西 | 数据来自 | 位置 |
|---|---|---|
| **选卡界面**（一关开始时选卡） | `TowerDefenseManager.GetPacketBankData(config.packetBankType)` 的 `category[分类]` | `TowerDefenseBattleFeaturePacketBank.cs:170` / `:514` |
| `packetBankType` **默认值** | `"GeneralPlant"`（关卡可被 `TowerDefenseLevelConfig.packetBank` / `PacketBankName` 覆盖） | `TowerDefenseLevelPacketBankConfig.cs:9` |
| **图鉴**植物页 | `WithPlants(GetPacketBankData("GeneralPlant"))` —— **同一个库的深拷贝** | `Almanac.cs:219` |

⇒ **根上的修法：往共享卡库 `ResourceManager.Instance.TOWERDEFENSE_PACKETBANKS["GeneralPlant"]
.category["Gold"]` 追加卡 key**（check-then-add，幂等）。
一次改动同时喂到「选卡界面」和「图鉴」⇒ **两边数据天然一致**，不需要各补一份。
- 还要补**派生库**：`ResourceManager.BuildExpandedPacketBank` 沿 `Include` 递归合并分类，
  所以 `Include` 闭包里含 `GeneralPlant` 的库（实测只有 `Total`）运行期是它的超集。
  运行期按 `res://Asset/Config/PacketBank/PacketBankResource.json` 的 `Include` 闭包算，
  别写死（离线重算时会得到 `['GeneralPlant','Total']`）。
- ⚠️ **`GetPlantList()` 只认 White/Gold/Diamond/Colour/Star/Original 六个键**
  （`TowerDefensePacketBankData.cs:48-68`）—— **故意不认 `ModPlants`**。
  这就是「只把它放进图鉴的 `ModPlants` 分类还不够」的硬证据。
- ⚠️ Mod 植物会被 `XWModContentCatalog.WithPlants()`（`XWModContentCatalog.cs:107-123`，
  `PlantCategory="ModPlants"` 见 :15）**单列一类**，全仓只有 `Almanac.cs:219` 调它。
  补完共享卡库后图鉴里它会**出现两次**（`ModPlants` + `Gold`）—— 那是游戏自己的隔离设计，别去删。
- 兜底（可选）：图鉴是按需实例化、每次打开都新拷一份，正常时序下补完共享卡库就够了；
  只有「图鉴已经开着 → 之后才补卡库」才需要再补一次
  `Almanac.plantPacketBank`（**public 字段**，`Almanac.cs:101`）的同一分类。
  ⚠️ 改它之后**只在反射读到 `_plantInitialized == true` 时才调 `InitPlant()`** 刷新
  （图鉴刻意懒初始化，自带测试断言「不得提前初始化隐藏分类/预览节点」，见下一条）。
- 判定「卡是否解锁」：`TowerDefensePacketConfig.Unlock()` 先问
  `XWModPlayerProgressService.TryPacketUnlock`，其中 **Mod 卡的空 `unlockCheckList` ⇒ `unlocked = true`**
  （内置卡空表反而 `return false`）⇒ Mod 卡天然可选，不用配解锁条件。
- ⚠️ **副作用要说清楚**：进了 `Gold` 就等于成为一张正常金卡，凡是按卡库随机取卡的逻辑
  （`GoldShardDropItemHandler`、`TowerDefenseCraterG`、`PanGoldBean`）以及走 `GetPlantList()`
  的（植物礼盒 / LuckyBlover / CubeBox）都可能给出它。交付时**必须如实告知用户**；
  若用户只想要「图鉴里能看到」，就别做这一步。
- `GeneralPlant.Category` 实测只有 6 个键：White178/Gold19/Diamond16/Colour6/Star27/Original20
  （Item/GraveStone/Zombie 在别的卡库）—— 别照 `XWPacketBankVisualResourceEditor.DefaultCategories` 猜。

**④ 换掉「投掷车僵尸投出来的单位」**（已实测）：
`TowerDefenseZombieImppult.ImpSpawn()`（`…/Chapter5/Imppult/Scene/TowerDefenseZombieImppult.cs:135`）
**硬编码** `GetPacketConfig("ZombieImp")`；`projectileName` 只是美术层名字 ⇒ 只有插件一条路。
接缝与时间线见上一节「僵尸类」的差异 2。同节还有僵尸卡入库/血量口径两条差异。

### 四条硬约束（写错 = 整包被拒 / 回滚）
1. `runtimeAssembly` **必须恰好是字面量** `"Runtime/ModAssembly.dll"`（`ModLoader.cs:329-333` +
   `ResolveDeclaredRuntimeAssembly:918`）——写别的路径**硬拒**，`policy` 救不了。
2. `runtimeApiVersion` **必须恰好 `1`**，否则入口 init 返回 false → **无条件整包回滚**；
   `TryInitializeRuntimeEntry` 失败（`ModLoader.cs:667-671`）同样是**不设防硬拒**，
   连 `policy="optional"` 都保不住 ⇒ 三个回调必须 try/catch。
3. `provides`/`overrides` **只要有任何非空条目**，包内**每个**被 `InferRuntimeEntry` 识别的文件
   都必须在里面声明（`ModLoader.cs:526/578/673`）——否则该文件被静默跳过 +
   `ValidateManifestRegistrations` 判**整包失败**。所以自定义贴图**必须**写 `provides.Texture`。
4. `resources` 必须 == `XWModManifestSyncService.SyncProject` 的规范序：**所有**非忽略文件，
   `OrdinalIgnoreCase` 升序（忽略 `.uid/.import/.bak/.tmp/.pvzmodeproject/.csproj/.sln`、
   目录 `.build/.git/.godot/bin/obj`、以及 `mod.json` 自身），否则**编辑器一打开工程就重写 mod.json**。
   ⚠️ `Runtime/ModAssembly.dll` 也要一起进这个列表（它不是可推导类别，但 SyncProject 会算它）。

### ⚠️ `Runtime/` 目录只许有一个文件
`ModLoader.IsExecutablePackageFile` 认 `.dll/.exe/.bat/.cmd/.ps1/.cs/.gd`；
`ValidateDeclaredPackageExecutables`（`ModLoader.cs:343-346`）对**除声明程序集外**的任何一个
抛 `undeclared executable package file` 直接拒收整包。
⇒ `Runtime/` 下只能有 `ModAssembly.dll`。`.pdb` 不在该名单里（会被 `IsDeclaredRuntimeSymbols`
静默跳过），但既然没用就别放。构建脚本结尾加一条"只允许 ModAssembly.dll"的硬护栏。

`runtimeAssemblyPolicy: "optional"` ⇒ `IsRuntimeAssemblyRequired() == false`
⇒ 程序集加载失败**不连坐**整包（新 Mod 建议先 optional）。

### 入口实现纪律
- 三个回调 `Initialize(XWModRuntimeContext)` / `OnAllModsLoaded()` / `Shutdown()`
  **一律 try/catch、绝不抛**（抛 = 上面那条无条件回滚）。
- **别每帧硬干**：`Initialize` 只存 context；`OnAllModsLoaded` 挂 `process_frame` 并自己节流
  （如每 10 帧一次）；`Shutdown` 摘掉。取用前先判空
  （`TowerDefenseManager.Instance` / `GetMapFeature()` / `config` / 目标节点）。
- 只在自己生效的范围动手：例如换背景要先确认**当前地图是自己的**
  （`config.ResourcePath` 以 `自己的键.tres` 结尾 **或** `translate == 中文名`）。
- 贴图取值走**两条腿**：先 `context.TryGetRuntimeTexture(key)`，
  失败再按**包根**（`user://ModsCache/<名>/`）文件兜底（`Image.LoadFromFile` → `ImageTexture.CreateFromImage`）。
- 资源放 `Assets/Images/<Key>.<png|jpg|jpeg|webp|svg|bmp|tga>` 或 `Assets/Textures/…`
  → `InferRuntimeEntry` 推 `("Texture", <文件名去扩展>)`。`Assets`/`Assets/Images` 属 72 标准目录；
  `Assets/Textures` 与 `Runtime/` **不在** 72 项里，但放进去不影响加载（只影响编辑器目录骨架）。
- 编译：`dotnet build -c Release`；**csproj 必须 `<Compile Remove="check_*.cs" />`**，
  否则探针脚本（顶级语句）会被编进库 → CS8805。装机只放 `ModAssembly.dll`，**别带 `.pdb/.deps.json`**。
- ⚠️ **每条出错路径各用一个「已报告」标志，不要共用一个**（如 `_tickFaultReported` /
  `_almanacFaultReported` / `_hookFaultReported` / `_volleyFaultReported`）。
  共用时「先报的那条会把后报的静音掉」：图鉴归类失败（只是难看）会把「大招推进失败」
  （= 玩法真没生效）的日志吃掉，排查时只看到一个不相干的警告。
  同理，日志**措辞要和实际行为一致** —— 只做去重就别写「已停止重试」（其实每帧还在试）。
- ⚠️ **改游戏侧 UI/列表状态时，别破坏它的懒初始化**。图鉴的植物页是
  `PlantButtonPressed` → `if (!_plantInitialized) InitPlant()` 才建列表，
  自带测试（`AlmanacVirtualizedResidencyRuntimeTest`）还专门断言「不得提前初始化隐藏分类 /
  不得提前实例化预览节点」。所以补完分类**只在 `_plantInitialized` 已为 true 时才主动刷新**：
  读私有字段用**缓存一次的 `FieldInfo`**（`BindingFlags.Instance | NonPublic`），
  拿不到就退化成「不刷新」（最坏：用户翻一次分类），绝不硬调 `InitPlant()`。
  扫描间隔（如 10 帧 ≈ 0.17 s）远小于用户点击延迟 ⇒ 正常路径天然不需要刷新。

### 不开游戏怎么验（本机可行）
用 `dotnet run --file x.cs` 跑探针，**反射直调游戏程序集里的真函数**（不启动 Godot）：
- `ModLoader.InferRuntimeEntry` 逐条核对包内路径推出的 `(category,key)` == 我们写的 `provides`；
  ⚠️ 也要核**不该推导**的那些：角色包依赖（`Resources/Characters/<Cat>/…`）与
  `Runtime/ModAssembly.dll` 都必须返回 `false`（靠 `IsCharacterPackageDependency` /
  `IsDeclaredRuntimeAssembly` 放行），返回 `true` 反而是错。
- `XWModManifest.Load` 读回 mod.json，核 4 个 runtime 字段 + `IsRuntimeAssemblyRequired()`；
- `ModLoader.ValidateDeclaredPackageExecutables`（**private static，用 `BindingFlags.NonPublic` 反射调**）
  传**真实 pmod 的 namelist**（`ZipFile.OpenRead` 取）必须不抛；
  再塞一条假 `Runtime/Evil.dll` **必须抛** —— 这是唯一能证明该闸门真在生效的负向对照。
  参数是 `IReadOnlyList<string>`，传 `List<string>` 可行；
- `XWModRuntimeCompatibility.ValidatePackage`（若类型存在）；
- `XWModManifestSyncService.SyncProject` 在**工程副本**上跑，断言返回 `false` 且 mod.json **字节不变**
  （= 编辑器不会重写我们的清单，这是最容易被忽略的一条）。
  ⚠️⚠️ **副本里必须把 `Localization/*.csv` 也拷进去**（`Resources` + `Translations` 两份清单都要拷）：
  SyncProject 把 `Localization/*.csv` 归到 `translations` 段，副本缺该文件时会**把
  `manifest.translations` 重写成 `[]`** ⇒ 假的同步差异（踩过：translations 非空的包必假红）；
- 入口发现：按 `FullName` 找**唯一**的非 abstract `IXWModRuntimeEntry` + public + 公开无参构造 +
  三个方法齐全 + `Activator.CreateInstance` 成功。

游戏程序集在 `<游戏根>\data_PlantsVsZombies_windows_x86_64\`（`PlantsVsZombies.dll` + `GodotSharp.dll`）。
⚠️ 本机有**两份**游戏构建：`D:\zzz\植物大战僵尸杂交版0.28\植物大战僵尸杂交重制版\data_…`
与 `D:\zzz\植物大战僵尸杂交版发布版0.28.0.控制台Csharp\data_…`。
**`PlantsVsZombies.dll` 字节不同**（`GodotSharp.dll` 相同）⇒ 两份都要跑一遍闸门。
小技巧：用发布版目录当 `GodotRefDir` 再编译一次，与本机 DLL **比字节** ——
一致（`build_runtime.py` 会打印「未变」）就说明用到的 API 面在两份构建里完全相同
（本项目的植物插件正是如此）。

📖 **要引源码行号就去看解包源码树**（别凭记忆写行号）：
`D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28\` 下有完整 `.cs`（`addons/ModEditor/ModSystem/`、
`Prefab/GUI/`、`Core/`、`Script/Component/`、`Scene/`）与 `Asset/Config/**.json`。
改文档/注释里的 `xxx.cs:123` 之前，**先打开那个文件确认行号**（版本一变行号就漂）。

参考实现：
- `ModWorkspace/runtime_src/`（地图换贴图）：`VampirePoolRuntimeEntry.cs`、`check_gates.cs`、`check_entry.cs`、`build_runtime.py`；
- `ModWorkspace/runtime_src_plant/`（植物玩法 · 概率触发齐射）：`SuperGatlingPeaRuntimeEntry.cs`、`check_gates_plant.cs`、`build_runtime.py`；
- `ModWorkspace/runtime_src_zombie/`（僵尸 · 投掷替换）：`DiscoGargantuarPultRuntimeEntry.cs`、`check_gates_zombie.cs`、`build_runtime.py`；
- `ModWorkspace/runtime_src_zombie_super_gatling/`（僵尸 · **逐发发射 / 大招 / 卡库入库**）：
  `SuperGatlingPaperRuntimeEntry.cs`、`check_gates_super_gatling_paper.cs`、`check_*.cs`、`build_runtime.py`。
  ⚠️ 四个工程**互相独立**（各自 csproj + build_runtime.py），别混。

⚠️⚠️ **跑检查脚本时别搞错「脚本类型 ↔ 调用方式」（踩过，白跑好几轮）**：

| 脚本 | 正确调用 | 说明 |
|---|---|---|
| `runtime_src_*/check_gates_*.cs` | `dotnet run --file check_gates_plant.cs -- <refDir> <projDir> <pmodPath> <entryTypeFullName>` | **必须给 4 个参数**；参数缺了就 `rc=3762504530`（`args[0]` 越界后句柄异常），**不是脚本坏了** |
| `runtime_src/check_entry.cs` | `dotnet run --file check_entry.cs -- <refDir> <modAssemblyDllAbsolutePath>` | 第 2 参是 **DLL 绝对路径**（不是工程目录、不是 `.pmod`） |
| `ModWorkspace/.cache/run_entry_sgp.py` | `python run_entry_sgp.py` | **真正好用的入口发现检查**（内部已封装 `check_entry.cs` 的两份构建调用）⇒ 优先用它，别自己手搓参数 |
| `ModWorkspace/.cache/check_modloader_gates.py` | `python check_modloader_gates.py` | 整包 ModLoader 闸门（33/1/0）。**纯 Python，不用 dotnet** |
| `runtime_src_*/XxxRuntimeEntry.cs` | ❌ **不是探针** | 那是**插件源码本体**，`dotnet run --file` 会报一堆 `CS0246`（找不到 Godot 类型）—— 它靠 csproj 的 `Reference` 编译，别直接 run |
| `runtime_src_*/build_runtime.py` | `python build_runtime.py` | 编译插件成 `ModAssembly.dll` |

★ **`check_gates_plant.cs` 的 `entryTypeFullName` 是 `SuperGatlingPeaRuntimeEntry`**（不带命名空间）——
传带命名空间的全名会得到 `FAIL RuntimeEntryType == …`（我踩过；这一条 FAIL 是**参数错**，不是包错）。
⚠️ 疑似两份构建只找到一份（`D:\zzz\植物大战僵尸杂交重制版\…`，`PlantsVsZombies.dll` 26 351 104 B）；
`runtime_src`（地图）与发布版那份当前**不存在** ⇒ `run_entry_sgp.py` 会打印「跳过：引用目录不存在」但仍报「全绿」，
**别把它当成「两份都过了」**。

⚠️ 探针脚本（顶级语句）**必须**被 csproj 的 `<Compile Remove="check_*.cs" />` 排除，否则 CS8805。
`dotnet run --file` 会产生大量 CS86xx / IL2xxx 警告，过滤 `" warning "` 再读输出。

⚠️⚠️ **写探针脚本时的两个 C# 编译坑**（都会让整个探针跑不起来，报错信息还很难定位）：

| 坑 | 症状 | 正解 |
|---|---|---|
| **C# 没有「相邻字符串字面量隐式拼接」**（那是 C/C++/Python 的语法） | `CS1003: 语法错误，应输入","`，**报错列在行尾之后一格**，看着像文件末尾坏了 | 长路径拆行必须写 `+`：`ReadRel("a/b/" + "c.tres")` |
| **`dotnet run --file` 编译的独立程序，编译期没有 GodotSharp 引用**（`GodotSharp.dll` 只在运行期由 `AssemblyLoadContext.Resolving` / `LoadFromAssemblyPath` 载入） | `CS0246: 未能找到类型或命名空间名"GodotObject"` | 源码里**禁止**出现 `GodotObject`/`Node` 等 Godot 类型字面量；判类型关系走反射：`alc.LoadFromAssemblyPath(refDir + "\GodotSharp.dll").GetType("Godot.GodotObject")` + `IsAssignableFrom` |

顺带（老坑，仍常犯）：
* 查 **private** 成员要带 `BindingFlags.NonPublic`，否则**假红**（`RefreshExportedArrayCaches` 就是 private）；
* Godot 的 `.tres` 属性名对**字段**与**属性**都成立，断言要写「public 字段**或**属性存在」并回报形态
  （实测 `FireComponent.fireProjectileList`/`fireAudioName` 是**字段**、`IsReleased` 是**属性**、`FireComponentDefinition.*` 是**属性**）；
* `Type.GetMethod(name, flags)` 遇重载抛 `AmbiguousMatchException`（如 `GetLogicalGlobalPosition()`）；
  带默认参数的方法是 C# 补的调用点，按 0 参查**查不到**（如 `Hypnoses(double time = -1.0, …)`）
  ⇒ 统一「按名取**全部**成员再筛参数个数」。
* 长命令别手敲：把「两份构建各跑一遍 + 落盘日志 + 汇总 PASS/FAIL」写成 `.cache/run_gates_*.py`。

### 判「DLL 里到底有没有某个东西」（静态断言常用，两个坑）

| 要查的东西 | 存在哪个堆 | 怎么搜 |
|---|---|---|
| **类型名 / 成员名**（`IXWModRuntimeEntry`、`TOWERDEFENSE_PACKETBANKS`、入口类名） | 元数据 `#Strings` | `b"X" in dll_raw`（**UTF-8**） |
| **字符串字面量**（`"GeneralPlant"`、`"include"`、中文日志） | `#US` | `"X".encode("utf-16-le") in dll_raw`（**UTF-16LE**） |

⚠️⚠️ 字面量**必须按字节搜**，**不能**把整个 dll `decode("utf-16-le")` 成 str 再 `in`：
字面量起始偏移可能是**奇数**，整体解码会从 0 偏移两两配对，奇数偏移的那条就永远搜不到
（踩过：`GeneralPlant`/`Total` 假红，而 `Gold`/`Include` 侥幸通过 —— 正是这个错位现象）。

### 反射访问的接缝要单独加闸门

编译器能验证的引用，靠「两份构建编译出的 DLL 字节相同」就够了；
但**反射/字符串访问**的成员（如 `Almanac._plantInitialized` 这种 private 字段、`plantPacketBank`
这种 public 字段、`TOWERDEFENSE_PACKETBANKS` 这种属性）编译器管不到，改版后会**静默失效**。
⇒ 在 `check_gates_plant.cs` 这类探针里加一组「接缝存在性」断言
（`GetField(name, BindingFlags.Instance|NonPublic)` / `GetProperty` / `GetMethod`），对**两份**游戏程序集各跑一遍。

⚠️ **`.tres` 里的字段名也是「接缝」**：靠**字段名**生效的数值（`hitpoints`、`_override`、
`coverCanDirectPlant`…）一旦被改名，`.tres` 里那行就变成没人认领的属性，游戏**静默回落默认值**
（血量又变 300、又不能直接种），而且**不产生任何日志** ⇒ 必须同样用反射把
「字段名 + 类型」钉在两份构建上（见 `check_gates_plant.cs` 第 7 组）。
注意 `_override` 的**属性名要去掉前导下划线**（`.tres` 里写 `override`）。

⚠️ **上面这段就是「纯数据改动也要加闸门」的理由**：纯数据不经过插件，
出错时既没有异常也没有日志，唯一的信号就是你自己的断言。

★ **可以反射直调游戏自己的校验函数，把「能不能加载」提前到离线**（比读日志强得多）：
```csharp
// SanitizeCharacterTextResource 是 private static（ModLoader.cs:1418）⇒ 要 NonPublic
MethodInfo sanitize = modLoader.GetMethod("SanitizeCharacterTextResource",
    BindingFlags.NonPublic | BindingFlags.Static);
// 签名 (LoadedMod, string relativePath, string absolutePath, bool canStripScripts)
// 第 1 个参数只在**失败**路径用于 AddDiagnostic ⇒ 传 null 安全
bool ok = (bool)sanitize.Invoke(null, new object[] { null, rel, abs, strip });
```
把包内**每一个** `.tscn`/`.tres` 的真实文件喂进去，然后断言
①返回 `true`（不拒包）②**文件逐字节未变**（它剥 `type="Script"` 的包内引用时会**回写文件**，
所以「未变」才是我们要的）③新增的 `type="Resource"` 引用**仍在**（剥的是 Script，Resource 不动）。
⚠️ 每次跑闸门前先给这些文件存快照 —— 这个函数**会改文件**。

⚠️ **插件效果只能游戏内确认**（DLL 在游戏进程里才跑得起来），交付时如实标注，并给出
`logs/godot.log` 的排查法：`[ModLoader] package applied: <id>; resources=N; runtimeEntry=True/False; diagnostics=M`
（`runtimeEntry=True` 才说明入口真的初始化了；入口抛异常会是**整包回滚**，
日志里是 `package rolled back after runtime entry failure`）。

## ★ 两个 Mod「共用同一套逻辑」= 共享源文件，不是共享程序集（2026-09-22 实测落地）

需求形态：「给 A 版和 B 版**共用**同一套 XX 逻辑」（本项目的实例：植物《超级机枪射手》与
僵尸《超级机枪读报僵尸》共用「射击判定」）。

**共享程序集做不到**：每个 `.pmod` 都必须自带路径**恰好**为 `Runtime/ModAssembly.dll` 的程序集，
且两版 `runtimeEntryType` 不同（数字签名/类名都不同）⇒ 结构上没法共用一个 DLL。

**做法：共享源文件（single source of truth）**

```
ModWorkspace/
├── runtime_shared/GatlingVolleyCore.cs              ← 判定核心：参数 + 判定函数，两版共用
├── runtime_src_plant/SuperGatlingPeaRuntime.csproj
│     <Compile Include="..\runtime_shared\GatlingVolleyCore.cs" Link="GatlingVolleyCore.cs" />
└── runtime_src_zombie_super_gatling/SuperGatlingPaperRuntime.csproj
      <Compile Include="..\runtime_shared\GatlingVolleyCore.cs" Link="GatlingVolleyCore.cs" />
```

⇒ 编译进两个 DLL，判定只有一份实现，**改一处两边同时生效**。要点：

* 入口里的常量改成**转发**（仍是编译期常量，取值处零开销）：
  ```csharp
  private const double UltimateChance = GatlingVolleyParams.UltimateChance;
  private const ulong  StallThresholdMsec = GatlingVolleyParams.StallThresholdMsec;
  ```
* 共享源里的「毫秒」要写成**字面量常量**，别写 `(ulong)Math.Round(1.5*1000)` ——
  那不是编译期常量，没法给 `const` 赋值。
* **别强行统一「节拍外壳」**：植物由 `FireComponent.OnFireReady` 触发，僵尸自建毫秒计时器
  （`process_frame`）。外壳不同、判定相同 ⇒ **只共享判定函数**，不抽状态机基类
  （零收益纯重构 + 会搅乱两版已验证的产物字节）。
* 共享源**不引用任何游戏类型**（只用 Godot 的 `RandomNumberGenerator` + `System.Math`），
  否则两个工程都得配齐引用/源码生成器。
* 人名/名字不一致的常量用**映射**处理（例：植物侧旧名 `StallGapMsec` → 共用核心 `StallThresholdMsec`）。

**抽出核心时会立刻暴露两处「两版漂移」**（本项目实测：单帧上限植物 `8` vs 僵尸 `12`、
卡顿阈值植物 `400ms` vs 僵尸 `250ms`）—— 「各写一份」必然漂，统一取值并**如实记录影响**。

### ⚠️⚠️ 守卫：把字面量搬进共享源后，「断言源码里有字面量」的检查全会假红

生成器 `self_check()` 与校验脚本原本直查 `UltimateChance = 0.10` 这种字面量 ⇒ 一次红 7 条，
**生成器直接拒绝写盘（exit 3）**。**要改的是断言，不是绕过它**，把它拆成**两问**：

```python
# (a) 入口必须转发（谁把值写回字面量 / 改了转发名 ⇒ 立刻红）
fwd = re.compile(r"const\s+\w+\s+" + local_name
                 + r"\s*=\s*GatlingVolleyParams\." + shared_name + r"\s*;")
# (b) 字面量只在共用核心里出现一次，且等于生成器侧记录的期望值
lit = re.compile(r"const\s+\w+\s+" + shared_name + r"\s*=\s*([0-9.]+)\s*;")
```

两版生成器要做成**完全对称**的两节（本项目：僵尸第 14 节 / 植物第 16 节），再加两条：
**两个 csproj 都真的 `Include` 了同一份源**（只挂一边 = 另版本质还是各抄一份）、
**入口真的在调用共用判定函数**（植物侧编号 `K15*` 16 条 / `K16` 1 / `K18` 2 / `K19` 4 = **合计 23 条**）。

> ⚠️ **别把「共几项」手写进文档** —— 这些条数是**循环展开**出来的（脚本里只有 6 个 `chk(` 调用点），
> 手抄必歪（本项目就写过一次错的「共 12 项」）。正确做法：**让校验脚本自己打印分组统计**
> （本项目 `check_plant_super_gatling.py` 末尾的 `分节断言数: …` / `共享判定核心断言… => 合计 N`，
> 分节表**从脚本自身源码现算**，增删小节自动跟随），文档引用那两行即可。

> 通用教训：任何「源码里必须含某个字面量」的断言都是**重构陷阱** —— 把值搬到别处
> （共享源 / 常量表 / 配置）后必然假红。搬家时顺手升级断言，**不要删断言或跳过校验**。

## 已知坑

- ⚠️⚠️⚠️ **「生成器自检」比对「刚生成的内存文本」= 假绿**：`build_*.py` 的 `self_check()` 常这么写 ——
  `sp = sprite_scene_tscn()` 重新生成文本，再对 `sp` 做正则断言。它只能证明「生成器常量 == 生成结果」，
  **证明不了磁盘上的文件是对的**。**负向测试实锤**：把错值直接写进磁盘 `.tscn`，自检照样打印「自检通过」
  （内存文本被重新生成覆盖了）。⇒ **凡生成器自检都要配一条 on-disk 断言**（读文件 + 比对值 + 断言磁盘值），
  并且用**「故意写坏磁盘文件 → 必须报错」**验证这条断言真的会响。只验内存 = 自欺。
- ⚠️⚠️ **验证器要分层，「拼合」那一层最容易被漏**：结构层（字节布局 / 数组自洽 / 字段值）全绿 ≠ 画面对。
  外观类至少三层：① 结构（`verify_skin_assets.py`）；② **拼合**（`verify_head_body_layout.py`：
  **落点差 == origin 差** + 两层真贴上 + 锚点落位）；③ 出包（工程布局 / 闸门 / 幂等）。
  只做①就会漏掉「头压在身体上」这种「每个字段都对、拼起来全错」的故障。
  ★ **换官方素材（逐帧）时升级为「四层独立 + 负向测试」**：① 源↔产物（对**全部 (层,帧)** 逐值反查）
  ② `.dat`（解析终点==文件长 + 像素区逐字节==自写 PNG 解码）③ `.tres`（f32 位级一致）
  ④ 场景 + 结构性不变量（图层不跨 body/head 边界）。**四层都不许复用生成器代码**，
  并加 `--negative`（写坏副本必须报错）。实测 101/0 + 3/3。
- ⚠️ **编辑器的 `F3` 会调 `set_mod_editor_cursor_blocked` 屏蔽自绘光标；关编辑器恢复。**
- Mod 环境在**联机战斗期间**拒绝变更：`Mod 环境正在确认或用于联机战斗...`
- 用户已有工程在 `Mods\1\1.pvzmodeproject`（`ModProject.Load` 读的 `.pvzmodeproject` 是
  `{Name,Version,Author,Description,ExportDirectory,GameDirectory,CreatedDate,LastModifiedDate}`）。
- bash 工具无 `cp/ls/head/tail/grep/dirname`，一律用 Python 处理文件与输出。
- ⚠️ **文件删除在本机很贵且会被劫持**：`shutil.rmtree` 抛 `SHFileOperationW 0x2`，
  逐文件 `os.remove` 单次约 0.6 s。任何"清空重建"式脚本都要改成增量（见铁律 9）。
- ⚠️ 工程目录的 `STANDARD_DIRS` **必须照抄** `XWModProjectLayout.StandardDirectories` 的 **72 项**
  （`addons/ModEditor/ModSystem/XWModProjectLayout.cs`，顺序也一致）。别凭印象写 ——
  曾经写出一份 120 项的臆造清单（混进 `Resources/ChessMaps2`/`VampireMaps`/`Collectables2`
  这类不存在的目录，同时漏掉 `MapCells`/`GameplayLogic`/`StateMachines`/`CharacterCombat` 等 39 项）。
  校验时**直接正则解析那个 .cs** 再与生成器比对，别维护第二份手抄名单。
- ⚠️ **「游戏能加载」≠「编辑器能打开」**，是两套东西：
  `.pmod` 给游戏（`Mods/*.pmod`，`ScanMods` 不递归）；
  `.pvzmodeproject` + 72 标准目录 + `mod_editor_recent_projects.cfg` 给游戏内编辑器（F3 → Mod 工具）。
  后者错了**不报错**，只是编辑器里打不开/看不到。
  * `.pvzmodeproject` 的 `ExportDirectory` 写**正斜杠 + 结尾斜杠**的 Mods 目录
    （编辑器默认值 `ModProject.cs:79` = `GlobalizePath("user://Mods/")`）。
    写反斜杠/缺尾斜杠**不会**导出到错位置（`Path.Combine` 容错），属格式不一致。
  * ⚠️ 写回「最近工程」缓存前**必须先把 CRLF 归一化**：用 `^path_\d+="(.*)"$` 直接匹配 CRLF 文件
    会**一条都解析不出来** → 然后把整个列表重写成「只剩自己一条」（实测两个生成器互相清空）。
    统一正斜杠 + 大小写不敏感去重 + 保留既有条目。
  * 登记的是 **Mods 下**的工程文件路径，不是工作区构建目录。
  * 想校准格式，最快的办法是**拿编辑器亲手建的工程当参照物**（如 `Mods/新地图-1/*.pvzmodeproject`），
    比读 C# 快得多。
- ⚠️ **`enabled_mods.json` 的合并逻辑「只增不删」会留改名残骸**：改过 `MOD_ID`（连大小写都算）后，
  列表里会同时留着新旧两条 id，之后再怎么跑生成器都**不自愈**。生成器里要显式清掉
  「与当前 `mod_id` **仅差大小写**」的历史 id 并打一行告警（别的 Mod 的 id 一律不动）。
- ⚠️ **manifest 托管四字段的真名**：`runtimeAssembly` / **`runtimeEntryType`** / `runtimeApiVersion` /
  `runtimeAssemblyPolicy`。写校验脚本时别把 `runtimeEntryType` 写成 `runtimeEntry`（会得到 `None` 的假红）。
- ⚠️ **断言「构建目录里有几个文件」要记得 `.pvzmodeproject` 也在里面**——它**本来就不入包**
  （`collect_entries` 排除它）。正确的断言是 **zip 内条目数**；且 **zip 里 `mod.json` 被强制排第 0**，
  而文件系统字母序里 `R`(0x52) < `m`(0x6D) ⇒ 它会排最后 ⇒ **比对条目用集合，顺序另立一条断言**。
- ⚠️ **Godot 4.7 的 `unique_id` / `parent_id_path` 是可选字段**：2071 个 `.tscn` 里 319 个不带，
  连游戏自己的 `BuildCharacterRuntimeSceneContent()` 模板也不带 ⇒ **别为「跟内置长得一样」硬造**
  （哈希规则没破出来，硬写风险更大）。`uid` 同理，一律不写。
- ⚠️ **离线反射探针的三个陷阱**（写 `check_*.cs` 时必踩）：
  ① `Type.GetMethod(name, flags)` 遇重载抛 `AmbiguousMatchException`（如 `GetLogicalGlobalPosition()`）；
  ② `GetField` **查不到** `public X { get; set; }` **属性**（`FireComponentDefinition.*`、
  `CharacterComponentSet.ParentSet/Components/RemovedInstanceIds` 都是属性）；
  ③ **带默认参数的签名按「实参个数」查不到**（如 `Hypnoses(double time = -1.0, …)`）。
  ⇒ 统一写「按名取全部成员再筛参数个数」的辅助方法 + `HasMember`/`Kind`（字段/属性）判定。
- ⚠️⚠️⚠️ **子精灵必被父代画 ⇒ 跨 `.tres` 的子精灵 = 一团别的角色的图集碎片**（2026-09-22 实机钉死）。
  `CollectOwnedChildBindings`（`AdobeAnimateSprite.cs:5365`，判定 `:5385`）**只按 Godot 节点类型**收集子精灵，
  **完全不看 `parentSprite`** ⇒「精灵的直接子精灵」必被收 ⇒ `IsRenderedByParentSpriteForRender`（`:9559`）
  true ⇒ `_Draw()`（`:9534`）**首行 return** ⇒ 子精灵自己的 `forceLocalRender` / `forceCpuPoseRender`
  （只在 `:9549/:9551` 读）**永远走不到**；它的切片改由**父精灵渲染批次**代画
  （`AppendChildSprites:833`）⇒ 采样**父那一张图集**：不在全局图集清单（`RefreshAtlas:3489` 是**构建期**才写
  `…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres`）⇒ `ResolveMediaRect:921` 落 `BaseAtlasPage = 0`
  ⇒ 采 `AdobeAnimateVisualTextureArray.png`（全部角色拼一张）⇒ **碎片拼贴**。
  * **只在「子精灵与父精灵共用同一份 `.tres`」时无害**（同 definition ⇒ 同 `MediaAtlasPages`）。
    跨 `.tres` 的子精灵、或任何自制皮肤，一律中招。
  * ⚠️ 两个「看起来能躲」但躲不掉：① `insertLayerId = -1` ≠ 不插入
    （`ResolveSpriteChildInsertLayer:8039` 回落顶层）；② 挂到普通 `Node2D` 容器下也躲不掉
    （`:5397` 只在中间节点有 `ownerSlot` 时截断；且 `ResolveSpriteChildFollowLayer`
    **优先读子精灵自己的** `followParentSpriteLayerId`）。
  * ✅ **唯一有效修法 = 三节点**：`HeadShadow`（身体的直接子精灵，`visible=false` + **全层 false** ⇒ 零切片，
    只吃 `UpdateChild()`（`:5208-5286`）每帧定位；**该循环没有可见性判断** ⇒ `visible=false` 不拦截定位）
    + `HeadHolder`（普通 `Node2D`，identity）+ `HeadHolder/Head`（独立渲染；**不写** `parentSprite`/
    `insertLayerId`/`followParentSpriteLayerId`/`position`/`rotation`/`visible`）。
    两头 `scale`/`offset`/`offsetRotate` **逐字相同**，位姿由插件每帧从影子同步。
    可见头挂普通容器下**仍**能被引擎定位（`_parentSprite = FindParentSpriteAncestor():7797`，最近**祖先精灵**）。
  * 官方先例：引擎自带 `Test/AdobeAnimateDetachedChildOwnershipProbe.cs`。
  * 参考实现：`build_zombie_super_gatling_paper.py::sprite_scene_tscn()`。
- ⚠️⚠️ **`.tscn` 节点头收尾必须是 `]`；写成 `>` ⇒ Godot 静默吞行**（不报错、不警告，节点根本没建出来，零日志）。
  本项目实测：三节点场景明明写对了，实机仍不对，就是这个字符。而**生成器自检放行了**，因为断言写成
  `f'[node name="Head" type="Node2D" parent="HeadHolder"'`（**没带闭合括号**）⇒ **断言与实现同错 = 假绿**。
  * 修法：① 模板改 `]`；② 自检加**通用扫描**：
    `for ln in body.splitlines(): if ln.startswith("[node ") and not ln.endswith("]"): fail`；
    ③ 负向测试补一条反例。
  * ⚠️ **负向用例本身也会假绿（2026-09-24 实证）**：篡改必须**全量替换**（`replace(old, new)`），
    不能只改一处（`replace(..., 1)`）—— 同一个值（数字 / 路径）在文档与产物里常有**多处**，
    只改一处 ⇒ 其余处仍满足断言 ⇒ **0 条 FAIL = 假绿**。实测：交接文档对账脚本 `--neg` 首跑只有 1/3 报警，
    改全量后 3/3。另：**别只看「fails 非空」**，要断言「**被测的那一条**」出现在 FAIL 列表里，
    否则可能被别的断言碰巧掩盖（每条用例「总 FAIL 恰为 1」最干净）。
  * ⚠️ 取证纪律：**结构类结论一律以字节级读取为准** —— `Read` 预览曾把这一行的 `>` **显示成** `]`。
  * 凡新增结构断言都自问一句：**「它能不能拦住一个语法坏掉但前缀正确的产物？」**

## 从单张参考图制作角色贴图（抠像 + 逐帧动画）

当用户给一张角色截图，要求"做成游戏角色贴图 / 待机 + 射击动画 / 透明底 / 按帧序列组织"时走这条线。
**注意：这类请求通常不需要生成模型**，是确定性图像处理；先确认交付格式再动手。

### 先问清三件事（会实质改变交付物）
1. **交付格式**：逐帧序列帧 / 游戏原生图集（`AdobeAnimateData`+`.tres`+`.tscn`）/ 两者都要
2. **帧尺寸**：原图等比 N× / 1:1 / 对齐游戏单帧占位
3. **帧数与帧率**：对齐游戏（12fps、25 帧/clip）通常是最稳的默认

### 游戏内角色美术的真实位置（别找错）
```
Asset/Anime/Character/Plant/Chapter0/<角色名>/
├── <角色名>_1.png          ← 图集（不是逐帧散图！）
├── <角色名>.tres           ← AdobeAnimateData：帧率/切片/变换
├── <角色名>.tscn           ← 根 Node2D + Head 子节点
├── Config/TowerDefensePlant<角色名>.tres
├── Packet/Plant<角色名>.tres
└── Scene/TowerDefensePlant<角色名>.{tscn,cs}
```
⚠️ 不在 `Asset/Texture/TowerDefense/` 下（那里只有背景/子弹/种子包底图）。

### PeaShooter 实测规范（可直接当模板）
| 项 | 值 |
|---|---|
| `frameRate` | **12.0** |
| clip 分段 | `BodyIdle`=0–24、`HeadIdle`=25–49、`HeadFire`=**50–74**（各 25 帧） |
| 发射事件 | 某帧挂 `{"Command":"fire"}` |
| 单帧图层数 | 9（idle）/ 19（射击段，头部独立） |
| 切片变换 | `scale≈0.555` + 每层独立 offset |
| 定位 | 靠代码 `offset`（根 `(-40,-40)`、`Head(-36,-46)`）+ 图集切片矩形，**不靠画布对齐** |
| 种子卡 | `packetAnimeClip="BodyIdle"`、`packetAnimeScale=(0.5,0.5)` |

关键机制：**body 与 head 是两个独立 sprite**，运行时用 `timeScale` 做非线性同步
（`PeaShooterSprite.cs:25-40`）——所以"点头/待机"是两层错位叠加，不是单层整体晃。

### 抠像：底图若是"软泥/苔藓纹理"，色相法必失败
常见坑：参考图背景是**深绿软泥**，与角色自身的绿（叶/炮管）色相接近。
连续 4 种方案都会翻车：

| 方案 | 判据 | 失败原因 |
|---|---|---|
| 绿幕比值 | `(g-max(r,b))/255` 阈值 | 背景 greenness≈0.35 与叶子重叠 → 全图判前景 |
| 色相区间 | H 100–150 且 V≤0.68 | 叶子也在区间内 → 只留上半身 |
| 局部方差 | std 或亮度阈值 | 软泥也有低方差平块 → 碎片化 |
| ✅ **色相 + R 通道联合** | H 116–136 **且 R<45** 且 V>0.30 | 背景 R≈0–30、角色叶 R≈40–75 → 干净分离 |

**诊断手法**（比盲试快 10 倍）：沿几条垂直线打印 `RGB/H/S/V`，一眼看出背景 R 恒 <45、叶子 R>45。

**完整抠像管线**：
1. `classify()` 显式豁免为前景：纯黑描边(V<0.02)、蓝青(H 160–210 且 b>90)、橙红黄(H<62 或 H>335)、R≥45 的绿
2. 仅"正绿软泥"（H 116–136 且 s≥0.75 且 R<45）判为背景
3. 从**图像边缘** flood fill 扩散（保证不误吃角色内部同色区）
4. **形态学闭(r=2) 补内部镂空 → 开(r=1) 切断底部细桥** → 取最大连通域 → 与原前景求交（本次保留 96.7%）
5. 清除宽度 <3 的孤立横条；alpha 用 MedianFilter(3) + GaussianBlur(0.5) 去毛刺

⚠️ 三条硬教训：
- **底部残留碎点不能用连通域面积过滤**——它们通过 1–2px 细桥连着主体。
  必须先 `erode(1)` 断桥再取连通域；且开运算后要**与原 mask 求交**，否则轮廓被削钝。
- **天线蓝珠/发光件（H≈181、b>90）会被判成背景而直接丢失** → 必须显式豁免蓝青区间。
- 原图若四周有纯黑 padding（本次 8px），先裁掉再处理，否则 flood fill 的种子会落错地方。

### 部件分层动画法（比整体 warp 更有生命感）
把角色按 y 切成 4 层，各层独立变换后按序 `alpha_composite`：
| 层 | 范围 | 可做的变换 |
|---|---|---|
| 天线 | 顶部细杆 + 发光珠 | 小幅摆动 + **亮度呼吸**（发光件最出效果） |
| 头 | 盔/镜/炮管/围巾 | 绕**头茎交界**旋转 + 上下位移 + 炮管前推 |
| 茎 | 中段 | 纵向缩放（伸缩） |
| 叶 | 底部叶簇 | 极小幅挤压/摆动，几乎不动 → 稳定重心 |

**枢轴要取真实关节**：头部枢轴 = 头茎交界；整体摇摆枢轴 = 植株扎根点（不是几何中心）。

**画布必须预留摆幅边距**（本次左右 16、上 10、下 12 @2×），否则旋转时炮口/叶尖被裁掉。

### 交付自检口径（可量化，别靠目测）
- 全部帧 `size` 集合**唯一值只有 1 个**
- 全部帧 `mode == "RGBA"`
- **待机重心漂移**：逐帧 alpha bbox 中心 x/y 的极差（本次水平 1.5px、垂直 1.0px = PASS）
- **首尾无缝**：`diff(frame0, frameN-1)` ≈ `diff(frame0, frame1)`
- 射击阶段：明确列出 预备/蓄力/发射/后坐/归位 的帧区间 + **fire 帧号**

### 交付物清单
逐帧 PNG 序列 + 横向图集 + 竖向图集 + `preview_*.gif` + 全帧展开对照图
+ `_frames.json`（尺寸/帧率/时长/锚点/阶段/fire 帧）+ `README.txt` + 透明底棋盘验证图。

## 便利入口：图形编辑器 `mod_editor.py`（先看这里，能不写代码就别写）

同一目录下还有一套**游戏外运行**的图形编辑器（不是游戏内 F3 那个 GUI）。
只要用户是「想改个数值 / 试试效果」，优先用它，别手写 `build_pmod.py` 的 OVERRIDES。

```
start_editor.bat                       # 双击：自动开浏览器 http://127.0.0.1:8765/
start_editor.bat --build               # 不开界面，按 mod_project.json 直接打包+安装
start_editor.bat --unpack "D:\别的解包目录"
python mod_editor.py --no-browser --port 8765    # 等价（脚本化时用这个）
```

界面：左=类别+键搜索 · 中=按 `[ExportGroup]` 分组的字段表单 · 右=Mod信息/条目/产物预览/校验/已装Mod。
改动实时渲染 `.tres` 给你看；「构建并安装」直接落 Mods 目录。支持 12 类（137/45/18/11/2/1/140/12/43/12/123/46 键）。

它**自动推导**能改哪些字段，全仓无手工字段表：
```
Asset/Config/<类>/<类>Resource.json → 键名 → uid → .tres真身（音频走 .import 的 source_file）
  → 文件头 ext_resource(type=Script, path 含 /Resource/) → C# 配置类
  → 解析 [Export]/[Export(hint,hint_string)]/[ExportGroup|ExportCategory] → 类型感知表单
```
- C# 默认值要解析 `new Vector2(28f, 28f)` / `new StringName("Default")` / `EnumType.MEMBER` / `Colors.White`；
  空默认值 → 类型零值。
- 字段**同名取首条**（对齐 Godot `ka()/PROPS_ALL`）。
- uid 索引缓存 `.cache/uid_index.json`（v2，10197 条，首扫 5~7s）；枚举缓存 `.cache/enum_index.json`。
- HTTP 接口 `/api/state|keys|resource|project|preview|build|upload|uninstall|installed|reindex|reveal`。
- ⚠️ 前端 HTML 每次 `GET /` **现读磁盘**，改 HTML 不用重启；但**改 `verify_pmod.py` 必须重启服务端**
  （`build_package` 里 `import verify_pmod` 只生效一次，模块被缓存）。

### 三个已修的真 Bug（别再踩）

1. **`[Export(PropertyHint.Enum, "...")]` 在 `int` 字段上时，`.tres` 存的是整数，不是字符串。**
   全仓：`string` 31 处、`int` 3 处（如 `AdobeAnimateSlot.mode = Follow,Drive`）。
   当成字符串枚举会写出 `mode = "Follow"` 这种**类型不匹配的坏值**。
   → 正确做法：int + Enum hint ⇒ 枚举下拉但**写整数**（Godot Enum hint 值是下标；`"A:0,B:2"` 写法用显式值）。
2. **`provides` 的键撞内置（`provide.exists`）必须在离线校验里真核对注册表**，
   不能只给一条 WARN——这是 `XWModRuntimeRegistry` 的硬规则，撞了直接抛错。
3. **前端「左栏搜索框看不见」= 在 `height:auto` 父元素上用百分比 `max-height`。**
   `#cats` 曾用内联 `style="max-height:38%"`，父 `.sect` 没有 flex 声明 → 高度 `auto`
   → 百分比无法解析被当 `none` → 类别块长到全内容高（19 项 ≈555px）。父块占满后，
   兄弟「键」区（`flex:1` ≡ `flex:1 1 0%`，负剩余空间里分不到收缩量）**塌成 1px**，
   里面的搜索框（固定在区块标题下方 ≈28px）溢出 `#left` 底边、被底部输出栏盖住
   → `elementFromPoint` 打到 Footer，**鼠标点不进、键盘输不了**。
   触发条件：**浏览器可视高度 ≲800px**（1440×900 下完全看不出来，笔记本 768 必现）。
   → 修法：百分比挪到 **`flex-basis`** 上（`#left>.sect.cats{flex:0 1 38%}` /
   `#left>.sect.grow{flex:1 1 62%}`），它相对 `#left` 的高度，而 `#left` 由 `main{flex:1}` 拉伸决定，是确定值。
   右栏同理：`#right{overflow-y:auto}` + `#right>.sect{flex:0 0 auto}`（5 个区块都不收缩），
   否则窗口一矮，「构建并安装」按钮就被下一个区块的标题盖住点不到。

### 另外几条实测结论

- 「⌀ 用默认」= 从 `.tres` **删掉**该属性行，回落 C# 类默认值。
  统计「改动数」时**必须把 unset 也算进去**，否则「只看已改」会把这类字段藏起来、撤不回。
- 二进制条目（音效 `.ogg/.wav`）只能整文件替换；**扩展名必须和原版一致**
  （Godot 按扩展名挑 loader）。工程里存文件路径，不要把 base64 塞进工程 JSON。
- 新增键（provides）时记得改 `.tres` 里的 `name` 字段，否则基地名的 `name` 不变、游戏内会撞名。
- **`id` 收敛别用"过滤非法字符 + 兜底"**：中文名会被削成 `mod`（「豌豆强化」→ `mod`、「豌豆强化v2」→ `v2`），
  于是**两个不同 Mod 撞同一个 id**。正确做法是保留可读 ASCII 部分 + 挂名字哈希后缀：
  `豌豆强化 → mod_0a0a5a`、`pea_strong → pea_strong`（纯 ASCII 原样保留）。
- 产物 `.tres` 的字段顺序 = **原版顺序在前，你改的、原版没有的字段追加到 `[resource]` 段末尾**。
- 工程 JSON 不含绝对路径（只有 `category/key/edits/unset`），
  唯一例外是音效条目的 `sourceFile`（替换文件的绝对路径）。
- 构建**渲染阶段失败会直接中止**，不写文件也不安装。

### 文档分工（本工作区）

| 文件 | 写给谁 |
|---|---|
| `使用说明书.md` | **面向使用者**：启动 / 界面导览 / 上手 / 编辑动作 / 控件对照 / Mod 信息 / 校验怎么读 / 进游戏 / 排错 |
| `README.md` | **面向格式与原理**：`.pmod` 结构、`mod.json` 全字段、路径→类别表、三条硬规则、`.tres` 注意事项、验收脚本 |
| `地图Mod-*.md` / `植物Mod-*.md` / `僵尸Mod-*.md` | **单个 Mod 的交付文档**（每个 Mod 一份）：需求映射表 / 为什么走插件 / 包结构 / 硬约束清单 / 数值依据 / 「可微调点」/ 已知副作用 / 验收结果与指纹 / 进游戏排查顺序 / 未验证项。⚠️ 写新 Mod 时**先照抄上一份的结构**，并如实记录「本次新踩的坑」 |

## 真机浏览器验收：不用装 Playwright

`agent-browser` 要下 ~500MB Chromium，通常不值得。**Node 22 自带全局 `WebSocket`**，
直接连本机 Edge 的调试端口即可（本机路径 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`）。

参考实现 `.workbuddy/ModWorkspace/.cache/verify_ui.js`：

```js
spawn(BROWSER, ['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check',
                '--hide-scrollbars','--window-size=1440,900',
                '--remote-debugging-port='+PORT,'--user-data-dir='+prof,'about:blank'])
// 轮询 http://127.0.0.1:PORT/json/list 拿 webSocketDebuggerUrl
// 用 Runtime.evaluate 把【一整个 async IIFE】丢进页面跑完整套流程，返回 JSON 报告
```
- 页面里能直接访问顶层 `const S` / `function pickCategory` 等（经典脚本的顶层词法声明在同一个
  global 上下文），**但 `window.S` 取不到** → 判断存在要用 `typeof S !== 'undefined'`。
- 截图：`Page.captureScreenshot`；设备仿真：`Emulation.setDeviceMetricsOverride`。
- 断言要等**面板真的更新**，不能只等日志字符串（异步 `await refreshInstalled()` 在日志之后）。
- 切类别时 `pickCategory` **同步**设 `S.cat`、keys 是异步填的 → 等条件写成
  `S.cat===X && S.keys.length===N`，否则读到上一类的键数。
- 页面自动保存有 **400ms 防抖** → 从外部 `POST /api/project` 清空工程会被它写回。
  验收脚本顺序：**navigate → 外部重置工程 → `Page.reload` → 再跑流程**。

### ⚠️ 合成点击测不出布局 Bug —— 必须用真鼠标事件 + 多视口高度

`element.click()` 会**绕过命中检测**：元素被别的元素盖住、被挤出容器、`pointer-events:none`，
它照样"点得动"。所以 `.cache/verify_ui.js` 那种全 JS 合成点击的用例
**永远测不出「看不见 / 点不到」这类问题**——上面那个搜索框 Bug 就是这么漏掉的。

凡是涉及**可见性 / 命中 / 是否被遮挡**的验收，一律：

1. 坐标取 `getBoundingClientRect()`，用 **`Input.dispatchMouseEvent`**
   （`mouseMoved` → `mousePressed` → `mouseReleased`）发**真鼠标事件**；
   键盘用 **`Input.dispatchKeyEvent`**（`keyDown` 带 `text`/`unmodifiedText`/`code`/`windowsVirtualKeyCode`，
   再补 `keyUp`），**别用 `Input.insertText`**（不一定触发 `input` 事件，过滤逻辑不跑）。
2. 命中判定用 **`document.elementFromPoint(cx, cy) === el`**，并顺带断言
   `rect.bottom <= footerTop`（没被底栏吃掉）与 `document.activeElement === el`（真的能聚焦）。
3. **跨多档视口高度跑**（`Emulation.setDeviceMetricsOverride`，建议
   900/800/768/720/680/640/600/560/500/440 十档，每档 `Page.navigate` 重载重排）。
   只在 1440×900 跑 = 白跑。

参考实现：`.workbuddy/ModWorkspace/.cache/verify_search_flow.js`（真鼠标/真键盘 ×10 档，70 项）
与 `.cache/shot_ab.js`（A/B 取证：用 `document.createElement('style')` **注入旧 CSS 复现故障**
→ 移除后对比，落两张截图）。A/B 注入是验证"根因判断是否正确"最省事的办法，
比重读一遍 CSS 推理靠谱得多。

- 验收四件套（都要先起服务端）：
  `verify_pmod.py`（离线 22 项）· `.cache/test_api2.py`（接口 133 项）·
  `.cache/verify_ui.js`（真机合成点击 51 项）· `.cache/verify_search_flow.js`（真鼠标 ×10 视口 70 项）

