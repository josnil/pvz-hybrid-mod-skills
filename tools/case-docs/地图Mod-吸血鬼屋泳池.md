# 地图 Mod：吸血鬼屋泳池（Map 类）

> 生成器：`build_map_vampire_pool.py`（幂等，可重复运行，一次产出三种东西）
> 构建目录：`VampirePool/`（工作区）；贴图源：`assets/VampirePoolBackground.jpg`
> 游戏侧产物（两种形态，缺一不可，见 §8）：
> * `Mods/吸血鬼屋泳池.pmod` ← 游戏**只加载**这个（4 条目：`mod.json` + tres + 贴图 + DLL）
> * `Mods/吸血鬼屋泳池/` ← Mod 工程目录（72 标准子目录 + `mod.json` + `吸血鬼屋泳池.pvzmodeproject`）
>
> 本轮新增：**背景贴图换图**（走托管运行时，见 §9）与**网格几何按新贴图反推**（见 §5）。
>
> 2026-09-19 贴图更新：泳池贴图由「蓝池」换为**血池版**（`166ef18712cf6b23`，321388 B，仍 1400×600）——
> 只换二进制、**名称 / 路径 / 引用全部保持原样**（见 §9 与 §10）。
>
> 复核脚本：`.cache/check_map_tres.py`（tres 结构 / 几何对齐不变量）、`verify_pmod.py`（包规范）、
> `.cache/check_project_folder.py`（工程目录规范 + runtime 字段）、`.cache/check_idempotent_map.py`（3 连跑字节幂等）、
> `runtime_src/check_gates.cs` + `runtime_src/check_entry.cs`（调真实游戏程序集复核，见 §9）

---

## 1. 它是什么

| 项 | 值 |
|---|---|
| Mod id | `vampirepool` |
| 游戏内显示名 | **吸血鬼屋泳池**（写进 `Map.translate`） |
| 类别 | `Map` |
| `MAPS` 字典 key | `VampirePool`（`provides`，必须是不存在的新键） |
| 包内路径 | `Resources/Maps/VampirePool.tres` |
| 网格 | **9 列 × 6 行**（`gridNum = Vector2i(9, 6)`） |
| 网格起点 / 格大小 | `gridBeginPos = Vector2(260, 74)`、`gridSize = Vector2(80, 83.6667)`（见 §5） |
| 行数 line | `lineUse = [1,2,3,4,5,6]` |
| 水池 | **第 4~5 行 × 第 1~9 列**（18 格） |
| 背景贴图 | `Assets/Images/VampirePoolBackground.jpg`（1400×600，`provides` 声明 key = `VampirePoolBackground`；2026-09-19 起为**血池版** 321388 B `166ef18712cf6b23`） |
| 托管运行时 | `Runtime/ModAssembly.dll` → `VampirePoolRuntimeEntry`（运行期把背景 Sprite2D 的贴图换掉，见 §9） |

路径前缀 `Resources/Maps/` 与文件名 → (category, key) 的推断，来自
`ModLoader.InferRuntimeEntry()`；Map 类别运行时落到 `ResourceManager.Instance.MAPS[key]`
（`XWModRuntimeRegistry` 第 547 行）。因为 `MAPS` 里没有 `VampirePool`，所以走 `provides` 而不是 `overrides`。

游戏侧关卡编辑器的地图下拉是这样填的：

```csharp
// Prefab/GUI/LevelEditor/InformationEditor/LevelEditorInformationEditor.cs:155
foreach (string key2 in ResourceManager.Instance.MAPS.Keys) {
    TowerDefenseMapConfig cfg = (TowerDefenseMapConfig)ResourceManager.Instance.MAPS[key2];
    mapOptionButton.AddItem(cfg.translate);        // ← 直接用 translate 当显示文本
    mapDictionary[cfg.translate] = key2;
}
```

所以 `translate` 直接写中文名**就能正确显示**——这也正是游戏侧编辑器自己的
新建地图模板的写法（`XWTemplateLibrary.cs:631`，`translate = "${DisplayName}"`）。
内置地图写的是 `MAP_VAMPIRE` 这类 i18n key，靠 Godot 的 UI 自动翻译成中文；
我们写中文名不走翻译表，回落原字符串，结果一样。

---

## 2. 坐标约定（由编辑器自身代码确证，不是猜的）

```csharp
// addons/ModEditor/ResourceEditors/GUI/Panels/XWMapVisualResourceEditor.cs:1529
private static Vector4I ToCellConfigPos(Rect2I selection)
    => new Vector4I(selection.Position.X + 1, selection.Position.Y + 1,
                    selection.Position.X + selection.Size.X,
                    selection.Position.Y + selection.Size.Y);
```

* 编辑器里的网格是 **0-based**，写进 `.tres` 时 **+1** 变成 **1-based 闭区间**。
* `pos = Vector4i(x1, y1, x2, y2)` = **(列起, 行起, 列止, 行止)**。
  * `x` 轴 = 列，范围 `1..gridNum.X`
  * `y` 轴 = 行，范围 `1..gridNum.Y`

交叉验证：官方后院水池地图 `BackyardMapBackyard.tres` 里
`gridNum = Vector2i(9, 6)`，整盘基底 `pos = Vector4i(1, 1, 9, 6)`，水池 `pos = Vector4i(1, 3, 9, 4)`
—— 9/6 恰好对应 (列, 行)，印证 `x=列, y=行`。

> 所以「坐标 4,1 至 5,9」按 **行 4~5 / 列 1~9** 落地为 `pos = Vector4i(1, 4, 9, 5)`。
> （若按 (列,行) 读则行号到 9，超出 6 行，不成立；因此只有行/列这一种读法自洽。）

---

## 3. 水池怎么表达

`ElementFlags` **不是**水域标志，它是 `ELEMENT_SYSTEM` 位标志：

```csharp
// Resource/TowerDefense/TowerDefenseEnum.cs:159
public enum ELEMENT_SYSTEM { ICE = 1, FIRE = 2, DAY = 4, NIGHT = 8 }
```

它由 `SleepComponent` 消费（`(cell.elementFlags & 8) == 0` → 白天睡、`& 4` → 夜晚睡），
是吸血鬼屋「昼夜元素格」的真实玩法特性。

**水域走 `gridType`（`PLANTGRIDTYPE`）**：

```csharp
// Resource/TowerDefense/TowerDefenseEnum.cs:141
public enum PLANTGRIDTYPE { ALL=-1, NOONE=0, SOIL=1, GROUND=2, WATER=3, AIR=4, LILYPAD=5, ... }
```

| 区域 | 写法 |
|---|---|
| 普通草坪 | **不写** `gridType`（类默认 `[GROUND(2), AIR(4)]`） |
| 水池 | `gridType = Array[int]([3, 4])` = `[WATER, AIR]`（照抄官方后院水池） |
| 编辑器刷子默认 | `[2, 4]`（`XWTemplateLibrary.cs:632` 的 map-cell-resource 模板） |

---

## 4. ⚠️ 最容易踩的坑：覆盖次序

```csharp
// TowerDefenseMapConfig.cs:425
internal TowerDefenseCellConfig GetEffectiveCellConfig(int x, int y) {
    TowerDefenseCellConfig result = null;
    foreach (TowerDefenseCellConfig item in cellConfig)
        if (x >= item.pos.X && x <= item.pos.Z && y >= item.pos.Y && y <= item.pos.W)
            result = item;          // ← 循环不 break，最后命中的那条生效
    return result;
}
```

一条 `cellConfig` **同时携带 `gridType` 和 `ElementFlags`**，后写的会把**两样都替换掉**。

吸血鬼屋的格子是「元素格棋盘」——基底层夜晚(8)，第 2/4/6/8 列与第 2/4 行是白天(4)，
8 个交叉点又回到夜晚(8)。实算出来的逐格元素是：

```
第1行  夜 昼 夜 昼 夜 昼 夜 昼 夜
第2行  昼 夜 昼 夜 昼 夜 昼 夜 昼
第3行  夜 昼 夜 昼 夜 昼 夜 昼 夜
第4行  昼 夜 昼 夜 昼 夜 昼 夜 昼
第5行  夜 昼 夜 昼 夜 昼 夜 昼 夜
```

如果只是简单追加一条 `Vector4i(1,4,9,5)` + `gridType=[3,4]`，
那么第 4~5 行所有格子的 `ElementFlags` 会被清成 **0**，昼夜元素特性在这两行**全部丢失**。

**本脚本的做法**（20 条 `cellConfig`，比硬拆 18 个单格干净得多）：

1. 继承原有 15 条，只把行上界 `5 → 6`（多了第 6 行）；
2. 4 条原本就**完全落在水池行内**的条目，**就地补上** `gridType = [3,4]`：
   * `Vector4i(1,4,9,4)`（第 4 行整行，白天元素）
   * `Vector4i(2,4,2,4) / (4,4,4,4) / (6,4,6,4) / (8,4,8,4)`（第 4 行 4 个交叉点，夜晚元素）
   → 第 4 行到此已全部是水，且元素分毫不差；
3. 第 5 行**新增 5 条**：先 `Vector4i(1,5,9,5)` + `[3,4]`（占位，奇数列本就是夜晚元素），
   再用 4 条单格把偶数列修正回白天元素（`(2,5,2,5)`、`(4,5,4,5)`、`(6,5,6,5)`、`(8,5,8,5)`）。

结果：**18 个水池格全部拿到水，54 个格子的元素标志与原版逐格一致**（第 6 行沿用第 5 行样式）。

---

## 5. 6 行几何：已改为「按背景贴图反推」

**结论先说**（二轮改造，取代旧方案）：
`gridBeginPos` = **`Vector2(260, 74)`**，`gridSize` = **`Vector2(80, 83.6667)`**（⚠️ 已不再是类默认 `(80, 98)`，
所以**必须显式写进 `.tres`**）。整盘 y ∈ **[74, 576]**，横向 x ∈ [260, 980]。

数值来自用户新背景图 `VampirePoolBackground.jpg`（1400×600）的实测：

| 量 | 实测值 | 取用 |
|---|---|---|
| 草坪上沿 | y ≈ 74 | `GRID_BEGIN_Y = 74` |
| 草坪下沿 | y ≈ 576 | 由 `GRID_BEGIN_Y + 6×行距` 自然落位 |
| 行距（自相关） | ≈ 83.667 | `GRID_SIZE_Y = 83.6667`（= 502/6） |
| 水面范围 | y ≈ 329 .. 490 | 水池格（第 4~5 行）实测 325.0 .. 492.3 → **偏差 ≤ 4px** |
| 水面横向 | 第 1~9 列 | 与 `gridNum.X = 9` 一致 |

### 为什么必须动它（硬证据，全部来自 V0.28 运行时，不是编辑器）

逻辑地图空间 = `TowerDefenseMapConfig.mapSize`，类默认 **(1400, 600)**；背景贴图实测恰好 **1400×600**。
三条独立路径都把可用区域限制在 `[0, mapSize.Y]`：

| # | 证据 | 说明 |
|---|---|---|
| ① | `TowerDefenseCameraControl.ClampCameraToMap()`<br>`camera.GlobalPosition.Y = ClampCameraAxis(y, 0f, size.Y, visibleY)` | `size = mapConfig.mapSize` → **相机垂直被钳在 y ∈ [0, 600]** |
| ② | `TowerDefenseBattleFeatureMap.BuildProjectileBoundaryRect()`<br>`= new Rect2((-100, 0), mapSize + (200, 0))` | **子弹边界** → y ∈ [0, 600]，超出即被回收 |
| ③ | `TowerDefenseManager.cs:1897`<br>`bottom = gridBeginPos.Y + gridNum.Y * gridSize.Y` | **网格下沿公式** |

`Test/Chapter7MapCameraBoundsRuntimeTest.cs` 还断言了 `downRightMarker.GlobalPosition == mapSize`，与 ① 互证。

代入数值：

| 方案 | 下沿 = `gridBeginPos.Y + 6 × gridSize.Y` | 判定 |
|---|---|---|
| 原版 5 行 | 75 + 5×98 = **565** | ≤ 600 ✓ |
| 旧方案（上移居中，98 格高） | 6 + 6×98 = **594** | ≤ 600 ✓，但条纹整体错位 69px |
| **当前（对齐贴图）** | 74 + 6×83.6667 = **576.0002** | ≤ 600 ✓，且**与贴图草坪/水面严丝合缝** |

### 每行落位

```
第 1 行 y =  74.0 .. 158.0
第 2 行 y = 158.0 .. 241.7
第 3 行 y = 241.7 .. 325.0     ← 贴图草坪上沿 74 / 水面顶 329
第 4 行 y = 325.0 .. 408.7     ← 水池
第 5 行 y = 408.7 .. 492.3     ← 水池（水面底 490）
第 6 行 y = 492.3 .. 576.0
```

### 代价（说清楚，别指望没有）

* **上下留白不再对称**：上 74px / 下 24px（旧方案是对称 6/6）。这是「网格去对齐贴图、而不是对齐画布」的必然结果。
* 旧方案的「条纹对不齐」问题**也随之消失** —— 因为新贴图就是按 6 行画的，网格现在压在它自己的条纹上。
* 自检里原来的「留白对称」断言已相应换成「**对齐贴图草坪 / 行距**」断言（`build_map_vampire_pool.py` 与
  `.cache/check_map_tres.py` 都改了）。

### 如果以后想改（改完重跑生成器即可）

| 方案 | 改动 | 代价 |
|---|---|---|
| **对齐贴图（当前）** | `gridSize = Vector2(80, 83.6667)`、`GRID_BEGIN_Y = 74` | 上下留白不对称（74 / 24）；**换贴图就得重算这两个数** |
| B. 上移居中（旧方案） | `gridBeginPos.Y = (600 − 6×98)/2 = 6`，`gridSize` 走默认 98 | 条纹整体错位 69px，第 1 行顶到画布边缘 |

⚠️ **换贴图时必须同步重算** `GRID_SIZE_Y` 与 `GRID_BEGIN_Y`，否则网格与画面错位。
生成器已把贴图尺寸与「草坪上沿 / 下沿 / 行距」写成常量（`ART_LAWN_TOP` / `ART_LAWN_BOTTOM` / `ART_ROW_PITCH`）
并在自检里断言，所以换图后跑一次 `build_map_vampire_pool.py`，对不上的地方会**直接报错**而不是悄悄错位。

编辑器里微调最快：游戏内打开 Map 编辑器，拖 `gridBeginPos` / `gridSize` 能实时看网格叠加层，
面板底部有「边界: left/top/right/bottom」实时读数，以及 `格子: 9 x 6, 起点 … , 大小 …` 摘要。

### 关于 `edge`

* **`edge`**：`.tres` 不写 → 用类默认 `Vector4(200, 0, 1100, 576)`。
  ⚠️ 注意 `edge.W`（下沿 576）**小于**画布 600，但**玩法代码只用 `edge.X` / `edge.Z`（左右）**
  （`TargetSystem` 取 `edge.Z` 当僵尸来的方向，推车用 `edge.Z` 判出走、巨人僵尸用 `edge.X` 判越界），
  `.W` 未被消费。而且 `TryValidateRuntime` **只校验** `edge.Z > edge.X` 且 `edge.W > edge.Y`，
  **不校验「网格必须落在 edge 内」** —— 所以这纯粹是画面/相机问题，不是校验问题。

> 对比一下：**`gridSize` 以前是「不写就走默认 `(80,98)`」，现在必须显式写**。
> 这是本轮最容易忘的一处 —— 忘了写就静默回落 `(80, 98)`，整盘错位且**没有任何校验会报错**（`TryValidateRuntime`
> 只查 `IsFinitePositive`）。所以 `.cache/check_map_tres.py` 现在专门断言 `gridSize == Vector2(80, 83.6667)` 这一行。

---

## 6. 验收

| 检查 | 结果 |
|---|---|
| 生成器内置自检（逐格仿真 `GetEffectiveCellConfig`：水池范围 / 元素分布 / 边界 / **几何对齐贴图**） | **54 格全绿**（+ 6 行元素 + 20 条 pos + 几何 10 项） |
| `verify_pmod.py`（复刻 ModLoader 规则：包结构、manifest、provides 新键、uid 剥离） | **ok=13 warn=1 FAIL=0**（warn = `provides Texture` 离线无该注册表，属预期；⚠️ 早前误记成 `22/0/0`，那是 `PeaOverhaul.pmod` 的数） |
| `.cache/check_map_tres.py`（引用完整性 / res:// 存在性 / 字段增量 / **几何对齐不变量**） | **全部通过** |
| `.cache/check_project_folder.py`（工程目录与编辑器同构 / 清单键序 / **runtime 四字段** / 启用开关 / 包工程一致） | **ok=40 warn=0 FAIL=0** |
| `.cache/check_idempotent_map.py`（生成器字节幂等） | 3 连跑，8 个产物 sha 全不变 |
| **几何**：网格 x ∈ [260, 980] ⊂ [0, 1400]，y ∈ [74, 576] ⊂ [0, 600]；行距 83.6667 == 贴图行距 | **全绿** |
| **运行时闸门** `runtime_src/check_gates.cs`（调用**真实游戏程序集**里的真实函数，见 §9） | **16 项全绿** |
| **运行时入口** `runtime_src/check_entry.cs`（复刻 `TryInitializeRuntimeEntry` 的发现逻辑） | **9 项全绿**（唯一命中/公开/无参构造/三方法/可实例化） |
| 悬空 `ExtResource` / `SubResource` | 无（4 + 20 条全部配对且被引用） |
| 6 个 `res://` 引用（3 个 cs 脚本、1 个规则资源、1 张贴图、1 个场景） | 全部存在于正式版 |
| `.pmod` 内条目 | 恰好 4 条：`mod.json` + tres + 贴图 + DLL（`pmod.exact` 断言） |
| 工程目录与游戏侧 `新地图-1` | 72 个标准子目录集合等同 + 本 Mod 特有的 `Runtime/`（白名单放行） |
| `ModAssembly.dll` 两次编译字节一致 | **8704 B `e1ad0cc1`**（`build_runtime.py --check`） |
| **两份**游戏构建都跑过 `check_gates.cs` | 均 **16/16**（`…\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64` 与 `…\植物大战僵尸杂交版发布版0.28.0.控制台Csharp\data_…`，两边 DLL 字节不同） |
| 成品指纹 | `dist/吸血鬼屋泳池.pmod` **327435 B `be08ca00c38f4a3d`** · 贴图 **321388 B `166ef18712cf6b23`**（1400×600，血池版） · DLL 8704 B `e1ad0cc1`（未变） |
| 已安装并启用 | `Mods/吸血鬼屋泳池.pmod`（同 sha）+ `Mods/吸血鬼屋泳池/` 工程目录；`enabled_mods.json` 含 `vampirepool` |

---

## 7. 游戏侧结构：为什么这样放（本次改造的核心）

游戏侧编辑器（`F3` → **Mod 工具**）自己产出的 `新地图-1/` 是这样的：

```
Mods/新地图-1/
    新地图-1.pvzmodeproject        ← 工程元数据（Name/Version/Author/Description/ExportDirectory/…）
    Resources/Maps/  … 等 72 个空目录
```

**但游戏并不加载它。** `XWModManager.ScanMods()`（`ModSystem/XWModManager.cs:110`）：

```csharp
foreach (string item in Directory.EnumerateFiles(_modsDirectory, "*.pmod",
                                                 SearchOption.TopDirectoryOnly))
```

* 只扫 **`Mods/*.pmod`**，而且 **TopDirectoryOnly（不递归）**
  → 所以 `新地图-1/` 这种**文件夹形态是加载不到的**，它只是编辑器的「工程」。
* 没有 `Mods/enabled_mods.json` 时 `LoadEnabledIds()` 返回**空集合** → **一个 mod 都不会加载**
  （这一点很容易被误判成「Mod 格式不对」，其实是**没启用**）。

所以我们两种形态都产出，并且**三处名字统一**（工程目录名 / `.pvzmodeproject` 名 / `.pmod` 名 = `吸血鬼屋泳池`），
这样在编辑器里再点一次「导出」会**覆盖同一个 `.pmod`**，不会出现两份同 `id` 的 mod 互相打架：

| 形态 | 路径 | 谁用它 |
|---|---|---|
| 可加载包 | `Mods/吸血鬼屋泳池.pmod` | **游戏本体**（`ScanMods` → `LoadMod` → `ApplyMod`） |
| 工程目录 | `Mods/吸血鬼屋泳池/` | **游戏侧编辑器**（工程管理 → 打开工程 → 继续改 → 导出） |
| 启用开关 | `Mods/enabled_mods.json` = `["vampirepool"]` | `LoadEnabledModsWithResult` 决定加载哪些 |

工程目录内容（`XWModProjectLayout.EnsureProjectLayout` 的 72 个子目录 + 我们的 5 个文件）：

```
Mods/吸血鬼屋泳池/
    吸血鬼屋泳池.pvzmodeproject         8 个键，CRLF + \uXXXX 转义（与 Godot 实测产物同字节风格）
    mod.json                           18 个键（XWModManifest 全集），LF + 不转义中文
    Resources/Maps/VampirePool.tres    地图配置（网格 6 行 + 水池）
    Assets/Images/VampirePoolBackground.jpg   背景贴图（1400×600）
    Runtime/ModAssembly.dll            托管运行时入口（换贴图用）
    Scenes/ Scripts/ Battle/ Resources/… Assets/ Localization/     ← 72 个标准子目录
```

> `Assets/Images/` 就是 72 个标准子目录之一（`XWModProjectLayout.cs:119` 的 DropRule 认 `png/jpg/jpeg/webp/svg/bmp/tga`），
> 所以贴图放这里既合规又是编辑器「导入图片」的默认去处。
> `Runtime/` **不在** 72 项里，是本 Mod 为了托管程序集额外加的（`ModLoader.ResolveDeclaredRuntimeAssembly`
> 只认 `"Runtime/ModAssembly.dll"` 这一个字面量）。

> **`mod.json` / `.pvzmodeproject` 的字节风格**是实测对齐的，不是随手写的：
> Godot 的 `.pvzmodeproject` 是 **CRLF + 大写 HEX 的 `\uXXXX` 转义 + 结尾无换行**（`File.WriteAllText` 路径），
> 而 `ModExporter` 打进包里的 `mod.json` 是 **LF + 原样中文 + 结尾无换行**（对照你自己的 `PeaOverhaul.pmod` 内的 `mod.json`）。
> 两者 `XWModManifest.Load` / `JsonSerializer` 都能解析，差别只在字节层面；
> `.cache/check_project_folder.py` 会把这两套风格都断言住。

另外：工程目录里的 `mod.json` 已经写成「`resources` 恰好等于编辑器扫描结果（且已按规范序排好）」的样子，
所以**用编辑器打开这个工程时 `XWModManifestSyncService.SyncProject` 判定无需改动，不会把你的清单改回去**。

这条**不是推理，是实测**：`runtime_src/check_gates.cs` 会把工程目录复制到临时目录、调用**真实的**
`XWModManifestSyncService.SyncProject()`，断言它返回 `false` 且 `mod.json` 字节前后一致（见 §9）。

`resources` 的规范序（`OrdinalIgnoreCase` 升序，来自 `NormalizePathList`）：

```json
"resources": [
  "Assets/Images/VampirePoolBackground.jpg",
  "Resources/Maps/VampirePool.tres",
  "Runtime/ModAssembly.dll"
]
```

⚠️ 三个都在里面 —— `SyncProject` 会把工程目录里**所有非忽略文件**扫进 `Resources`
（忽略项只有 `mod.json` 本身、`.uid/.import/.bak/.tmp/.pvzmodeproject/.csproj/.sln`，
以及 `.build/.git/.godot/bin/obj` 目录）。少列一个，编辑器一打开就会被补上并重写 `mod.json`。

---

## 8. 进游戏测试

1. 确认 `Mods/` 下有三样东西：

   ```
   C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods\
       吸血鬼屋泳池.pmod          ← 必须有（本轮已从 4→? 条目：含贴图与 DLL）
       enabled_mods.json          ← 里面要有 "vampirepool"
       吸血鬼屋泳池\              ← 想继续在编辑器里改才需要
   ```

2. 游戏内 `F3` → **Mod 工具** → 确认列表里「**吸血鬼屋泳池**」是**启用**状态
   （没启用就点一下启用；`enabled_mods.json` 就是这一步写出来的）。
3. 点 **重新应用**（联机战斗期间会被拒绝）。
4. 打开**关卡编辑器** → 地图下拉应出现「**吸血鬼屋泳池**」。
5. **重点看几何**：
   * 网格应为 **9 列 × 6 行**，**6 行全部可见**，最下面一行不跑到背景外面；
   * 编辑器网格叠加层底部读数应是 `格子: 9 x 6, 起点 (260, 74), 大小 (80, 83.6667)`；
   * 第 4~5 行整行是**水池**（种植物会要求荷叶）；
   * 网格应正好压在**你那张新图的草坪条纹**上（本轮就是为对齐它才改的几何）。
6. **重点看背景贴图**（本轮新增的运行时换图）：
   * 进入「吸血鬼屋泳池」的战斗，背景应变成 `VampirePoolBackground.jpg`，
     且**位置/大小与 1400×600 原图完全一致**（DLL 只换纹理，不动 `centered`/`scale`）；
   * 若背景没变，去看引擎日志（见 §9 的排错表）。
7. 想继续手改：`F3` → **Mod 工具** → 工程管理 → **打开工程**，
   选 `Mods\吸血鬼屋泳池\吸血鬼屋泳池.pvzmodeproject`（生成器已把它登记进「最近工程」列表）。

---

## 9. 背景贴图换图：为什么必须走「托管运行时」

### 结论：纯数据换不掉

`VampirePool.tres` 里那个 `mapTexturePath` **不是战斗背景的来源**。查证如下：

| 事实 | 证据 |
|---|---|
| 战斗背景是地图**场景**里的一个 `Sprite2D` | `TowerDefenseMapVampire.tscn`：`[node name="Vampire" type="Sprite2D"]` + `texture = ExtResource("3_i3eg2")` = 内置 `Vampire.jpg`（`centered=false`、`scale=(1,1)`） |
| `mapTexturePath` 只喂 `GetMapTexture()` | `TowerDefenseMapConfig.cs:512` `ResourceLoader.Load<Texture2D>(mapTexturePath, …)` —— **纯 ResourceLoader，不查 Mod 贴图注册表** |
| Mod 自己的图片**没有**能按路径加载的通道 | `ModLoader` 是手工解码后塞进 `XWModRuntimeRegistry` 的（键 = 文件名去扩展），导出构建里 `ResourceLoader` 读不了 `user://` 的 jpg |

所以「把 `mapTexturePath` 指向自己的图」这条路是**死的**（`ResourceLoader` 直接失败）。

### 解法：Mod 带一张贴图 + 一个托管入口

| 组成 | 路径 | 作用 |
|---|---|---|
| 贴图 | `Assets/Images/VampirePoolBackground.jpg` | 1400×600，与原图同尺寸 → 1:1 顶替，无需缩放 |
| 声明 | `provides: {"Texture": ["VampirePoolBackground"]}` | **必须声明**（见下方 ⚠️） |
| 运行程序集 | `Runtime/ModAssembly.dll` | 8704 B，`VampirePoolRuntimeEntry` 实现 `IXWModRuntimeEntry` |
| 入口契约 | `runtimeAssembly` / `runtimeEntryType` / `runtimeApiVersion=1` / `runtimeAssemblyPolicy=optional` | 见下方 ⚠️ |

运行时逻辑（`runtime_src/VampirePoolRuntimeEntry.cs`）：挂 `process_frame`（每 10 帧一次），
当活动地图是「吸血鬼屋泳池」时，把场景树里所有 `ResourcePath` 以 `Vampire/Vampire.jpg` 结尾的
`Sprite2D.Texture` 换成从 Mod 包里解出来的那张图。

> 为什么是「按 ResourcePath 结尾匹配」而不是按节点名：这样**无论背景是场景里直接挂的 Sprite2D，
> 还是某处 `GetMapTexture()` 取出后赋给 Sprite2D 的**，都能命中 —— 两条路得到的都是同一个缓存资源，
> `ResourcePath` 都是那个内置路径。

### ⚠️ 四个不能错的硬约束（都踩过/都查证过）

1. **`runtimeAssembly` 只能是字面量 `"Runtime/ModAssembly.dll"`**
   —— `ModLoader.cs:918` 不匹配就 `package rejected`（**硬拒整包，policy 也救不了**）。
2. **`runtimeApiVersion` 必须恰好 `1`**
   —— `XWModCharacterCompanionRuntime.cs:100` 不等就返回 false → 入口初始化失败 → **整包回滚**。
3. **`provides` 一旦非空，每个被识别的资源都必须声明**
   —— `ModLoader.cs:578` 起，未声明者被**跳过**；且 `ValidateManifestRegistrations`（`:673`）会让整包失败。
   所以贴图必须写进 `provides.Texture`。
4. **入口的三个回调一律不许抛异常**
   —— `TryInitializeRuntimeEntry` 失败（`:667`）是无条件 `return false`，不受 `policy` 保护。
   代码里 `Initialize` / `OnAllModsLoaded` / `Shutdown` 全部整体 `try/catch`，失败只记日志。

`runtimeAssemblyPolicy: "optional"` 的作用：程序集**加载失败**时（`ModLoader.cs:520`）不连坐整包，
地图本身仍可玩，只是背景保持内置 —— 比整张地图被拒好得多。

### 离线怎么验（不开游戏）

| 脚本 | 验什么 | 结果 |
|---|---|---|
| `runtime_src/check_gates.cs` | 调**真实** `ModLoader.InferRuntimeEntry` / `XWModManifest.Load` / `IsRuntimeAssemblyRequired` / `XWModManifestSyncService.SyncProject` | 16 项全绿 |
| `runtime_src/check_entry.cs` | 复刻 `TryInitializeRuntimeEntry` 的发现逻辑（唯一命中 / public / 无参构造 / 三方法 / 可实例化） | 9 项全绿 |
| `runtime_src/build_runtime.py --check` | 两次编译字节一致 | 8704 B `e1ad0cc1` ✓ |

`check_gates.cs` 里最关键的一条是**用真实 `SyncProject` 在临时副本上跑了幂等**（返回 false、mod.json 字节不变），
这比「我读代码推测它不会改」强得多。

### 若背景没变，怎么排查

引擎日志（`%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\logs\godot.log`）里找这些：

| 日志 | 含义 / 处理 |
|---|---|
| `[ModLoader] package rejected: … invalid declared runtime assembly path` | `runtimeAssembly` 字面量写错了 |
| `找不到运行入口类型` / `运行 API 版本不兼容` | 入口类名或 `runtimeApiVersion` 不对 |
| `[VampirePool] 运行入口已初始化` | 入口跑起来了（好现象） |
| `[VampirePool] 已替换地图背景贴图，共命中 N 个 Sprite2D` | 换图成功 |
| `[VampirePool] 没有找到贴图（已试 …）` | 贴图没进包 / 路径不对 |
| 什么都没有 | `ModsCache/吸血鬼屋泳池/` 里看看有没有 `Assets/Images/…jpg` 与 `Runtime/ModAssembly.dll` |

> 另：`.pmod` 改动后**必须重新应用**（`F3` → Mod 工具 → 重新应用），否则 `ModsCache/` 里还是旧内容。
   改完点「导出」，产物会落回 `Mods\吸血鬼屋泳池.pmod`，再「重新应用」即可。

> 生成器每次运行都会自动做第 1 步里的三件事（镜像工程目录、合并启用清单、登记最近工程），
> 并且会删掉改名前的旧文件 `Mods/VampirePool.pmod`（同 `id`，留着就是重复 mod）。
> 所有写操作都是**合并/覆盖式**且**字节幂等**，重跑不会有抖动；旧文件名那份内容仍留在
> 工作区 `dist/VampirePool.pmod` 作为历史备份。
>
> 2026-09-16 起镜像改成**增量**（`sync_tree`：按字节只写变化的文件、只删 src 里没有的），
> 因为本机运行环境的删除钩子被劫持成「丢回收站，失败即抛异常」，且逐文件删除单次约 0.6 s
> （整目录重建一次要 48 s，3 连跑的幂等校验会被超时杀掉）。现在一次跑完 **0.6 s**，
> 重跑「写 0 / 删 0」。详见 `植物Mod-超级机枪射手.md` §10。
>
> ⚠️ 同轮还修了一个**会误伤别的工程**的 bug：「最近工程」缓存（`mod_editor_recent_projects.cfg`）
> 旧写法用 `$` 匹配行尾，而该文件是 CRLF → 一条 path 都解析不出来 → 整个列表被重写成
> 「只剩本工程一条」，把「超级机枪射手」那条抹掉了。现在解析前先归一化 CRLF，
> 统一正斜杠、去重、保留所有既有条目。详见 `植物Mod-超级机枪射手.md` §11。

---

## 10. 贴图更新记录（2026-09-19：蓝池 → 血池）

需求：把「吸血鬼屋泳池」用到的贴图**全部替换为最新版**，同时**不改变名称 / 路径 / 引用关系**，不留旧引用。

### 10.1 先把「引用点」找全（替换范围 = 3 份二进制 + 8 处文字引用）

全工作区 + 游戏侧 `Mods/` 扫描 `VampirePoolBackground` / `Assets/Images` / 全部图片文件后，结论是：

| 类型 | 位置 | 处理 |
|---|---|---|
| **源贴图（唯一真相源）** | `assets/VampirePoolBackground.jpg` | **换二进制**（生成器只从这一份拷） |
| **包内贴图** | `VampirePool/Assets/Images/VampirePoolBackground.jpg` | 生成器自动覆盖 |
| **游戏侧工程镜像** | `Mods/吸血鬼屋泳池/Assets/Images/VampirePoolBackground.jpg` | 生成器自动镜像 |
| 包容器 | `dist/吸血鬼屋泳池.pmod`、`Mods/吸血鬼屋泳池.pmod` | 重新打包（含新贴图字节） |
| 文字引用（**保持原样**） | `build_map_vampire_pool.py`（`TEXTURE_KEY`/`TEXTURE_REL`）、`VampirePool/mod.json`（`provides.Texture` + `resources`）、`runtime_src/VampirePoolRuntimeEntry.cs`（`TextureKey`）、`runtime_src/check_gates.cs`、`.cache/check_project_folder.py`、`.cache/check_modloader_gates.py`、`地图Mod-吸血鬼屋泳池.md` | 全部以**名字**为键 ⇒ 换图不需要动 |
| **不是**本泳池贴图 | 内置 `Asset/Config/Map/Vampire/Vampire.jpg`（`mapTexturePath` 指向它，仅供**编辑器预览**；战斗背景由 DLL 运行期替换，见 §9） | 不动 |

### 10.2 为什么可以只换二进制（不需要同步改材质 / 配置）

| 检查项 | 旧图 | 新图 | 结论 |
|---|---|---|---|
| 尺寸 | 1400×600 | 1400×600 | 与 `mapSize` 同 ⇒ **1:1 顶替，无需缩放** |
| 文件格式 | JPEG（SOI `FF D8`） | JPEG | 生成器的尺寸校验照常通过 |
| 像素差异包围盒 | — | **(240, 320) – (1008, 496)** | 完全落在水池带内 |
| 逻辑水池格区 | — | x 260–980（9 列 × 80）、y 325.0–492.3（第 4~5 行） | 水池绘制区**新旧重合**，网格与贴图对齐不变 |

⇒ 除「水的颜色 / 纹理」外没有任何变化：`gridBeginPos`、`gridSize`、`gridNum`、`lineUse`、水池格、`mapTexturePath`、`mod.json`、DLL **一个都不用改**。

> 生成器自带的「网格上沿/下沿/行距 == 贴图草坪边线（±1px）」断言在换图后依旧全绿（54 格自检），
> 这是「换图后几何仍对齐」的机械证据，不靠肉眼。

### 10.3 新旧指纹

| | 旧（蓝池） | 新（血池） |
|---|---|---|
| 贴图 | 324307 B `26c1ec51dcd4f8db` | **321388 B `166ef18712cf6b23`** |
| `dist/吸血鬼屋泳池.pmod` | 330210 B `59e4b2741420` | **327435 B `be08ca00c38f4a3d`** |
| `Runtime/ModAssembly.dll` | 8704 B `e1ad0cc16ae5` | **未变**（只换贴图，不碰代码） |

旧贴图已归档到 `.cache/backup/VampirePoolBackground.old-26c1ec51dcd4.jpg`（**回滚用**，不在任何 Mod 包 / 工程目录内，不构成引用）。

### 10.4 换图后的回归

| 校验 | 结果 |
|---|---|
| `check_project_folder.py` | ok=40 **warn=0 FAIL=0** |
| `verify_pmod.py` | ok=13 warn=1 FAIL=0（唯一 warn = 离线无 Texture 注册表，需游戏内确认，属预期） |
| `check_map_tres.py` | 全部通过（含 `mapTexturePath` 仍指内置 `Vampire.jpg` 的断言） |
| `check_idempotent_map.py` | 3 连跑字节稳定 |
| `runtime_src/check_gates.cs`（**两份游戏构建**） | 各 16/16 全绿 |
| `runtime_src/check_entry.cs`（**两份游戏构建**） | 各 9/9 全绿 |
| 残留旧贴图引用扫描 | 除回滚备份外 **0 处**（含 `.pmod` 内部条目按字节比对） |

> ⚠️ **换图效果只能游戏内确认**：跑完生成器后需 `F3` → Mod 工具 → **重新应用**，
> 否则 `ModsCache/` 里还是旧贴图。日志里应看到 `[VampirePool] 已替换地图背景贴图，共命中 N 个 Sprite2D`。

