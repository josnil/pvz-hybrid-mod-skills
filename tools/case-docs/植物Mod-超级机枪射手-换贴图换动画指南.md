# 超级机枪射手（SuperGatlingPea）—— 换贴图 / 换动画完全指南

> 面向：想把这个 Mod 角色的**外观**从「机枪射手（GatlingPea）」换成别的素材。
> 所有结论都已经在解包源码里逐行核实过，关键处标了 `文件:行号`。
> 核实版本：杂交版 0.28 解包树 `D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28`。

---

## 0. 先看结论（TL;DR）

这个角色的外观**不是一张 PNG，而是一套三件套**：

| 件 | 现在是什么 | 换外观时要不要动 |
|---|---|---|
| **精灵场景** `Sprite/<Key>.tscn` | **双图层父子场景**（根 body + 子 Head），由 `skin_params.json` 驱动 | 换成你的素材场景 |
| **动画数据** `<Key>.tres`（`AdobeAnimateData`） | **官方素材直转** `./SuperGatlingPea.tres` → `./SuperGatlingPea.dat`（**27 轨 × 87 帧**） | 换成你的 `.tres`（**必须与 `.dat` 一起**） |
| **`.dat` 二进制图集** | **官方素材直转**，**自包含图片**（当前 **344 418 B**，87 帧 / 1168 slice / 图集 256×296） | 必须由你提供 |

> ⚠️ 本文档 §1 / §3 描述的是**更早的形态**（复用内置 `GatlingPea` 指针壳），保留作为背景与「路线 A」说明。
> **§10** = 自制单帧素材（路线 C，**已退役**）。
> **本 Mod 实际已落地「路线 D：官方素材直转」，见 §11 —— 这是当前首选路线。**

> ★★ **当前素材 = 「未重置版官方素材直转」**：`SuperGatling.reanim.compiled` **27 轨 × 87 帧**（2026-09-20 换代）。
> 画质与动作完整度优于自制素材，且**不需要背景转透明**。**完整说明见 §11。**
> ⛔ 上一代「自制单帧静止图 352×384」（路线 C）**已退役**，其格式知识保留在 §10（两条路线共用）。

**路线 A / B（历史与备选）：**

> ★ **首选是路线 D（官方素材直转），见 §11** —— 本 Mod 当前生效的就是它。

| | 路线 A：复用内置其它角色 | 路线 B：用你自己的新美术 |
|---|---|---|
| 做什么 | 把精灵场景指向另一个内置角色的 `.tscn` | 用编辑器导入你的 `.fla/.xfl` → 生成 `.tres`+`.dat` |
| 要不要带 `.dat` | ❌ 不用（用游戏的） | ✅ 必须带上（打包进 `.pmod`） |
| 素材门槛 | 零 | 需要 Adobe Animate 工程 |
| Clip 名要求 | 必须**对齐你选的那个角色**的 clip | 必须**自己造出同名 clip** |
| 难度 | 低 | 中（但有官方工具链） |

⚠️ **最容易踩的死坑**：这个角色的发射逻辑硬依赖 clip 名 `HeadFire` / `HeadIdle` / `BodyIdle`。
**换任何素材，都必须让新素材里有这三个 clip，否则一枪都打不出去**（详见 §5）。

---

## 1. 现状：外观是从哪来的

当前工程 `ModWorkspace/SuperGatlingPea/` 只有 3 个和外观有关的文件：

```
Resources/Characters/Plants/SuperGatlingPea/
├── Sprite/SuperGatlingPea.tscn          ← 376 B，只做一件事：实例化内置 GatlingPea 精灵
├── Scene/SuperGatlingPea.tscn           ← 角色场景，里面挂了 Sprite 节点 + Marker2D
└── Scene/SuperGatlingPeaComponentSet.tres ← 开火配置（含 clip 名！）
```

**① 精灵文件**（`Sprite/SuperGatlingPea.tscn`，全文就 8 行）：

```ini
[gd_scene load_steps=2 format=3]
[ext_resource type="PackedScene" path="res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tscn" id="1_game_sprite"]
[node name="SuperGatlingPeaSprite" instance=ExtResource("1_game_sprite")]
metadata/mod_resource_kind = "CharacterSprite"
metadata/mod_preview_source = "内置游戏角色视觉（GatlingPea）"
```

⇒ 它**没有自己的图**，只是一个「指针」。**要换外观，改这一行 path 是最省事的做法。**

**② 角色场景**（`Scene/SuperGatlingPea.tscn`）里外观相关的部分：

```ini
[ext_resource type="PackedScene" path="res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.tscn" id="6"]
...
idleAnimeClip = "BodyIdle"                                  ← 待机 clip 名
sprite = NodePath("SpriteGroup/TransformPoint/GatlingPea")   ← 精灵节点名，换素材要对齐
...
[node name="GatlingPea" parent="SpriteGroup/TransformPoint" instance=ExtResource("6")]
position = Vector2(0, -30)
trueFrameRate = 180.0

[node name="Marker2D" type="Marker2D" parent=".../GatlingPea/Head" index="0"]
position = Vector2(31.740002, -17.82)                        ← ★ 子弹出膛点
```

> ⚠️ **2026-09-24 齐射改版后本包是 7 个 Marker，不是 1 个**：
> `Marker2D`（= 炮口点 `(51.502, -16.8)`）+ `Marker2D2`..`Marker2D7`，
> 沿**弹道方向**（+x）依次 +32px（偏移 `0/32/64/96/128/160/192`，**y 全部相同 ⇒ 屏幕上一排**）。
> 上面 snippet 的 `(31.740002, -17.82)` 是**内置 GatlingPea 的旧标定值**（本包已作废，
> 新素材必须按新炮口重算）。完整口径见 `植物Mod-超级机枪射手.md` §9 / §13。

**③ 真正定义动画的**是 `ComponentSet` 里的这几行（`:82-91`）：

```ini
firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/GatlingPea/Head/Marker2D")]
spritePath = NodePath("SpriteGroup/TransformPoint/GatlingPea/Head")   ← 播开火动画的那层
fireAnimeClipsArray = ["HeadFire"]        ← ★ 开火动画 clip 名
fireAnimeClips = "HeadFire"               ← ★
fireAnimeTimeScale = 3.0
spliceIdleAnimeClips = "HeadIdle"         ← ★ 开火后回落的待机 clip 名
isSpliceSprite = true
```

**④ 内置素材本体在哪**（解包树里能看到 `Asset/...` 源码，但**图片二进制看不到**）：

```
Asset/Anime/Character/Plant/Cover/GatlingPea/
├── GatlingPea.tscn     ← 精灵场景（Node2D + Head 子节点）
├── GatlingPea.tres     ← AdobeAnimateData，72 KB
├── GatlingPeaSprite.cs ← 877 B
├── Config/TowerDefensePlantGatlingPea.tres
└── Scene/…（角色场景 + ComponentSet）
```

`GatlingPea.tres` 的头部（`frameRate = 12.0`、`frameMax = 89`）：

```ini
[resource]
script = ExtResource("1")
animeFile = "res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.dat"   ← ★ 真正指向图集
frameRate = 12.0
frameMax = 89
clips = {
"BodyIdle": Vector2i(0, 24),      ← 帧区间 0~24
"HeadFire": Vector2i(50, 88),     ← 帧区间 50~88
"HeadIdle": Vector2i(25, 49)      ← 帧区间 25~49
}
mediaDictionary = {
"GatlingPea_barrel.png": 0, "GatlingPea_blink1.png": 1, … "locator.png": 7
}
layerDictionary = {
"AnimeClips": 20, "GatlingPea_barrel1": 15, … "stalk_top": 4
}
```

`GatlingPea.tscn` 里的图层/媒体名（换素材时这些名字要对得上）：

```
图层 21 个：GatlingPea_barrel1..4 / GatlingPea_helmet / GatlingPea_mouth /
           GatlingPea_mouth_overlay / PeaShooter_eyebrow / anim_face / anim_idle /
           anim_stem / backleaf(+2 个 tip) / frontleaf(+2 个 tip) /
           idle_shoot_blink / stalk_bottom / stalk_top
媒体 17 个：GatlingPea_barrel.png / GatlingPea_blink1.png / GatlingPea_blink2.png /
           GatlingPea_head.png / GatlingPea_helmet.png / GatlingPea_mouth.png /
           GatlingPea_mouth_overlay.png / PeaShooter_backleaf.png /
           PeaShooter_backleaf_lefttip.png / PeaShooter_backleaf_righttip.png /
           PeaShooter_eyebrow.png / PeaShooter_frontleaf.png /
           PeaShooter_frontleaf_lefttip.png / PeaShooter_frontleaf_righttip.png /
           PeaShooter_stalk_bottom.png / PeaShooter_stalk_top.png / locator.png
```

---

## 2. ★★ 素材到底在哪：`.dat` 是**自包含图集**

**这是整件事最关键的一条事实**，很多人以为图是散装 PNG，其实不是。

`addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs:1682-1701`：

```csharp
public bool TryReadEmbeddedAtlasImage(out Image image, out Vector2I imageAtlasSize)
{
    string text = ResolveAnimeFilePath();
    if (string.IsNullOrWhiteSpace(text) || !Godot.FileAccess.FileExists(text)) return false;
    Godot.FileAccess fileAccess = Godot.FileAccess.Open(text, Godot.FileAccess.ModeFlags.Read);
    fileAccess.GetFloat();                                        // frameRate
    fileAccess.Get16();                                           // frameMax
    imageAtlasSize = new Vector2I(fileAccess.Get16(), fileAccess.Get16());   // ★ 图集宽高
    int len = (int)fileAccess.Get64();                            // 像素数据长度
    image = ReadEmbeddedImageAtlasFromDat(fileAccess, imageAtlasSize, len, out var decoded);
}
```

`:1630-1646`：

```csharp
byte[] buffer = file.GetBuffer(imageAtlasDataBufferLength);
long num = (long)imageAtlasSize.X * (long)imageAtlasSize.Y * 4;   // ★ RGBA8 原始像素
if (buffer == null || buffer.Length != num) return CreateTransparentFallbackImage();
return Image.CreateFromData(imageAtlasSize.X, imageAtlasSize.Y, useMipmaps: false, Image.Format.Rgba8, buffer);
```

**⇒ `.dat` 的结构**（小端）：

| 偏移 | 类型 | 含义 |
|---|---|---|
| 0 | `float` | frameRate |
| 4 | `u16` | frameMax |
| 6 | `u16` | 图集宽 |
| 8 | `u16` | 图集高 |
| 10 | `u64` | 像素数据字节数（应 = 宽×高×4） |
| 18 | `byte[]` | **整张图集的 RGBA8 原始像素** |
| … | … | 后续：媒体矩形、图层表、Clip 帧区间、事件帧 |

**⇒ 三条硬结论：**

1. **图片是塞进 `.dat` 里的**，不是外部 PNG。换图 = 重新生成 `.dat`。
2. `.dat` **不在解包树里**（`Asset/.../GatlingPea.dat` 文件在磁盘上不存在）——它在游戏 `pck` 包内，运行时通过 `res://` 读到。
   - 已核实：`植物大战僵尸杂交版发布版0.28.1.Csharp.pck`（464 MB）内含字符串
     `res://Asset/Anime/Character/Plant/Cover/GatlingPea/GatlingPea.dat`（偏移 102780 是路径表，136114424 是资源条目）。
3. `.tres` 里的 `animeFile` **可以写包内相对路径**（如 `"./MyGatling.dat"`），
   Mod 加载器会把它重定位到解包目录 —— 这是走路线 B 的关键（见 §3.2）。

---

## 3. 路线 A：复用内置其它角色（最省事，推荐先试）

### 3.1 原理

Mod 的 `Sprite/<Key>.tscn` 本质是「指向内置精灵场景的指针」。
`ModLoader.cs:1755`（`TryRelocatePackagedPath`）明确允许 `res://` 引用**已存在**的内置资源：

```csharp
if (declaredPath.StartsWith("res://", StringComparison.OrdinalIgnoreCase) && ResourceLoader.Exists(declaredPath))
{
    relocatedPath = declaredPath;
    return true;
}
```

所以只要把 path 改成另一个内置角色的场景，就能白拿它的全部美术。

### 3.2 具体要改哪些文件（4 处）

| # | 文件 | 改什么 |
|---|---|---|
| 1 | `Sprite/SuperGatlingPea.tscn` | `path=` 改成目标角色的精灵 `.tscn` |
| 2 | `Scene/SuperGatlingPea.tscn` | `[ext_resource … id="6"]` 的 `path=` 同上；子节点名（现在叫 `GatlingPea`）改成目标场景的根节点名 |
| 3 | `Scene/SuperGatlingPea.tscn` | `idleAnimeClip` 改成目标角色**真实存在**的待机 clip |
| 4 | `Scene/SuperGatlingPeaComponentSet.tres` | `firePosMarkerPaths` / `spritePath` 里的节点路径改名；`fireAnimeClips` / `spliceIdleAnimeClips` 改成目标角色真实 clip |

### 3.3 内置候选（同目录下就能找到）

已核实存在的「机枪类」内置角色（都可作为复用目标）：

| 角色 | 精灵场景 | 备注 |
|---|---|---|
| `GatlingPea` | `Plant/Cover/GatlingPea/GatlingPea.tscn` | ← 当前用的 |
| `GatlingPeaZ` | `Plant/Cover/GatlingPeaZ/GatlingPeaZ.tscn` | 有独立 `TimerComponentDefinition` |
| `GatlingCat` | `Plant/Cover/GatlingCat/` | 猫尾草版机枪 |
| `CatGatlingPea` | `Plant/Gold/CatGatlingPea/CatGatlingPea.tscn` | 金卡 |
| `GatlingCabbage` | `Plant/Other/GatlingCabbage/` | 卷心菜版 |

⚠️ **选谁就要对齐谁的 clip 名**。目标角色的 clip 名去它的 `.tres` 里看
（搜 `clips = {` 那一段），或直接在游戏里用 Mod 编辑器打开预览。

### 3.4 优点 / 代价

- ✅ **不用带任何二进制**，`.pmod` 体积不变，零素材门槛。
- ⚠️ 外观是「现成的」，做不出你独家美术。
- ⚠️ 若目标角色没有 `HeadFire`/`HeadIdle`（比如 `GatlingCabbage` 可能只有 `BodyIdle`），
  就得把 ComponentSet 的 clip 名改成它有的，或退化成「无开火动画」——
  而**无开火动画会让发射链路整条失效**（见 §5）。

---

## 4. 路线 B：导入你自己的美术（生成 `.dat`）

### 4.1 官方工具链（不用手写二进制）

编辑器自带导入器，已核实：

`addons/AdobeAnimateEditor/Tools/XWAdobeAnimateImportService.cs:70-97`：

```csharp
string text = Path.GetExtension(ToAbsolutePath(sourcePath)).ToLowerInvariant();
if (!(text == ".xfl") && !(text == ".fla"))
    return PreparedFailure("Only Adobe Animate .xfl and .fla files can be imported as animation resources.");
...
return new PreparedImport {
    ResourcePath = targetDirectory.PathJoin(name + ".tres"),   // 生成 .tres
    DatPath      = targetDirectory.PathJoin(name + ".dat")     // 生成 .dat
};
```

`:99-135` 完成时会：
```csharp
adobeAnimateData.SetAnimeFileForModImport(datPath.GetFile());   // animeFile = "你的.dat"（文件名，相对）
ResourceSaver.Save(adobeAnimateData, resourcePath);
instance.RegisterManifestPath(resourcePath);  // 登记进 manifest
instance.RegisterManifestPath(datPath);       // ★ .dat 也会被打包
```

**编辑器 UI 操作路径**（`XWFileSystemPanel.cs:1938-1941`）：

> 在 Mod 工程里选中 `Resources/AnimationAtlasProfiles/`（或动画目录）
> → 右键「新建动画」(`new-animation`)
> → 弹出「导入 Adobe Animate 动画」文件选择框
> → 选中你的 `.fla` / `.xfl`
> → 自动生成同名 `.tres` + `.dat`

### 4.2 ★ 关键：怎么让「自定义图集」被游戏认出来（`AnimationAtlas`）

这是 Mod 系统**专为换动画准备的官方通道**，很多人不知道。

**识别规则**（`ModLoader.cs:1088` 与 `:1155-1167`）：

```csharp
("Resources/AnimationAtlasProfiles/", "AnimationAtlas"),
...
if (candidate.Category.Equals("AnimationAtlas", StringComparison.OrdinalIgnoreCase))
{
    if (!(resource is AdobeAnimateAtlasProfile profile))  // 类型不对 ⇒ 拒包
    { AddDiagnostic(...); return false; }
    if (!TryPreparePackagedAnimationAtlasProfile(mod, candidate, profile, out var diag))
    { AddDiagnostic(...); return false; }
}
```

⇒ **只要把一个 `AdobeAnimateAtlasProfile` 放在 `Resources/AnimationAtlasProfiles/` 下，
加载器就会自动帮你把 manifest 及其引用的图集全部重定位到包内**（`TryRelocatePackagedAtlasManifestPaths`，`:1696/:1703-1740`）。

**Profile 的资源结构**（`addons/AdobeAnimateEditor/Runtime/AdobeAnimateAtlasProfile.cs`，全文 36 行）：

```csharp
[GlobalClass]
public partial class AdobeAnimateAtlasProfile : Resource
{
    [Export] public string ProfileId { get; set; } = "";
    [Export(PropertyHint.File, "*.tres")] public string ManifestPath { get; set; } = "";
    [Export] public bool StartupOnly { get; set; }
    public string GetStableCacheKey() { … }
    public AdobeAnimateGlobalAtlasManifest LoadManifest() { … }
}
```

**最小可用样板**（照抄内置 bootstrap，`addons/AdobeAnimateEditor/GeneratedAtlas/Bootstrap/AdobeAnimateBootstrapAtlasProfile.tres`）：

```ini
[gd_resource type="Resource" script_class="AdobeAnimateAtlasProfile" load_steps=2 format=3]

[ext_resource type="Script" path="res://addons/AdobeAnimateEditor/Runtime/AdobeAnimateAtlasProfile.cs" id="1_profile"]

[resource]
script = ExtResource("1_profile")
ProfileId = "bootstrap-loading"
ManifestPath = "res://addons/AdobeAnimateEditor/GeneratedAtlas/Bootstrap/AdobeAnimateBootstrapAtlasManifest.tres"
StartupOnly = true
```

对应 manifest（`AdobeAnimateGlobalAtlasManifest.cs`，字段已全部核实）：

```ini
[ext_resource type="Script" path="res://addons/AdobeAnimateEditor/Runtime/AdobeAnimateGlobalAtlasManifest.cs" id="1"]
[resource]
script = ExtResource("1")
AtlasTextureArrayPath = "…/VisualTextureArray.png"
AtlasTextureArrayLayerSize = Vector2(128, 128)
AtlasTextureArrayLayerCount = 1
AtlasTextureArrayColumns = 1
SourceKeys = Array[String](["res://Asset/…/LoadBarSprout.dat", …])   ← ★ 对应你的 .dat 的 res:// 路径
SourceStarts = Array[int]([0, 4])
SourceCounts = Array[int]([4, 5])
SourceSignatures = Array[String](["A07E1D80864B0FA5", …])            ← ★ 内容指纹
PoseTextureArrayPath = "…/PoseTextureArray.exr"
PoseAtlasPagePaths = Array[String]([…])
SourcePoseAtlasPages = Array[int]([0, 0])
SourcePoseTexelStarts = Array[int]([0, 2925])
SourcePoseTexelCounts = Array[int]([2925, 3410])
SourcePoseSignatures = Array[String]([…])
MediaAtlasPages = Array[int]([0, 0, …])
MediaRects = Array[Rect2]([Rect2(20, 16, 10, 10), …])                ← ★ 每个媒体的图集矩形
```

⚠️ **重要**：`SourceSignatures` / `SourcePoseSignatures` 是**内容指纹**，`MediaRects` 是**图集布局**。
**这三样都不能手写** —— 必须由编辑器的导出流水线生成。手改一个字符就会指纹不匹配。
⇒ 路线 B 的可行前提是：**能用编辑器正常导入并导出**，而不是手工拼 manifest。

### 4.3 官方还有一个「换图」的低门槛入口：`extraMediaReplaceTexturePaths`

如果你**只想换某几张图、不想重做整套动画**，`AdobeAnimateData.cs:562-563` 提供了这条路：

```csharp
[Export(PropertyHint.File, "*.png,*.webp,*.jpg,*.jpeg,*.svg,*.bmp,*.tga")]
public Array<string> extraMediaReplaceTexturePaths { get; set; } = new Array<string>();
```

配合运行时接口（`AdobeAnimateSprite.cs:6000-6022`，此前已核实）：

```csharp
public bool SetAtlasReplace(StringName mediaName, string textureReference, bool queueUpdate = true)
```

⚠️ **注意它的静默陷阱**：`SetAtlasReplace` 先查 `_flashAnimeData.mediaDictionary.ContainsKey(mediaName)`，
**查不到直接 return false，不报错**。⇒ 换的图必须用**原媒体名**（如 `GatlingPea_head.png`）。

### 4.4 优点 / 代价

- ✅ 完全自定义美术。
- ⚠️ 需要 Adobe Animate 工程（`.fla` / `.xfl`）。
- ⚠️ `.dat` + 图集会让 `.pmod` 明显变大（当前整个包才 15 KB 级，图集会到 MB 级）。
- ⚠️ manifest 指纹/矩形依赖编辑器导出，**不能手工重制**。

---

## 5. ★★ 无论哪条路线都必须满足的 Clip 约束

这是最容易白忙一场的地方，务必先读。

### 5.1 发射逻辑硬依赖这三个名字

`Scene/SuperGatlingPeaComponentSet.tres:82-91` + 角色场景：

| Clip 名 | 谁在用 | 缺了会怎样 |
|---|---|---|
| `BodyIdle` | 角色场景 `idleAnimeClip`、Packet `packetAnimeClip`、卡片预览 | 待机/卡片缩略图异常 |
| `HeadFire` | `fireAnimeClips` / `fireAnimeClipsArray` | ★ **一枪都打不出去** |
| `HeadIdle` | `spliceIdleAnimeClips` | 开火后不回落到待机 |

### 5.2 为什么缺 `HeadFire` 就完全打不出子弹

`FireComponent.cs:3230`（`AttackEntered` 第一句）：

```csharp
if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(FireRuntimeState.Idle); return; }
```

`FireComponent.cs:998 / :1011`：

```csharp
private bool CanPlayFireAnimation(string clipName) { … if (string.IsNullOrEmpty(clipName)) return false; … }
```

⇒ clip 名对不上（或留空）时，原生「动画驱动发射」链路**整条失效**。

### 5.3 两条出路

**出路一（推荐）**：让新素材**真的有这三个 clip**，名字一字不差。
- 路线 A：选的目标角色本来就有这些 clip；没有就换目标或改名对齐。
- 路线 B：在 Adobe Animate 里按这三个名字造 clip。

**出路二（兜底）**：走**托管插件直接调 `FireComponent.Fire()`**——本 Mod 已经在这么做了！

> ★ 本 Mod 的 `Runtime/ModAssembly.dll`（`SuperGatlingPeaRuntimeEntry`）**本来就是绕开动画链路、自己按节拍调 `Fire()`** 的。
> `public void Fire()`（`FireComponent.cs:3429`）**不受状态机约束**（`:3436` 只查
> `CanExecuteGameplay && alive && parent 有效 && parent.instance 有效`）⇒ **在场就能打**。
>
> ⇒ 所以即使新素材没有 `HeadFire`，**只要插件还在、节拍还在，豌豆照样出膛**，
> 只是**没有开火动画**（视觉上「不抬枪」而已）。
> 这种情况下应**同步删掉** ComponentSet 里的 `fireAnimeClips` / `fireAnimeClipsArray` /
> `spliceIdleAnimeClips`（留空），避免半死不活的判断。

---

## 6. 完整替换流程（路线 A，逐步骤）

### 步骤 0：备份
```bash
# 整个工程目录先复制一份，出问题能回滚
```
⚠️ 别用 `shutil.rmtree` / 整目录删重建（本机被劫持过，会 `OSError: SHFileOperationW 0x2`）；
要删就增量 `os.remove` / `os.rmdir`。

### 步骤 1：定目标
在解包树里选一个内置角色，记下三样：
① 精灵场景 `res://…/<名>.tscn`；② 它的根节点名；③ 它的 `clips` 名（打开它的 `.tres` 搜 `clips = {`）。

### 步骤 2：改精灵指针
`SuperGatlingPea/Resources/Characters/Plants/SuperGatlingPea/Sprite/SuperGatlingPea.tscn`
→ 改 `path=`。

### 步骤 3：改角色场景
`…/Scene/SuperGatlingPea.tscn`：
- `[ext_resource … id="6"]` 的 `path=` 改为新精灵场景；
- 子节点 `[node name="GatlingPea" …]` 及其下 `Head` / `Marker2D` 的**父路径要跟着改**
  （节点名不再是 `GatlingPea`）；
- `idleAnimeClip` 改成新角色的待机 clip。
- ⚠️ **`Marker2D` 是子弹出膛点，位置要按新素材的枪口重新调**。
  依据：`FireComponent.cs:1232/1254` 的 `ResolveOwnerNode<Marker2D>` 只做 `GetNodeOrNull<T>`
  ⇒ **必须指向真正的 `Marker2D`**；指向 `HeadSlot`/`AdobeAnimateSlot` 会拿到 `null`、**子弹从原点出膛**。
- ⚠️ **齐射改版后是 7 个 Marker**（`Marker2D` + `Marker2D2..Marker2D7`）：换素材时**首颗随新炮口平移，
  其余沿弹道方向（+x）依次 +32px、y 与首颗相同**；改完跑生成器自检（13c-4/13f-4 会校验「同 y + 步距 32 + 首颗 = 炮口」）。

### 步骤 4：改 ComponentSet
`…/Scene/SuperGatlingPeaComponentSet.tres`：
```ini
firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/<新节点名>/Head/Marker2D")]
spritePath         = NodePath("SpriteGroup/TransformPoint/<新节点名>/Head")
fireAnimeClipsArray = ["<新的开火 clip>"]
fireAnimeClips      = "<新的开火 clip>"
spliceIdleAnimeClips = "<新的待机 clip>"
```

> ⚠️ **齐射改版后 `firePosMarkerPaths` 是 7 条**（`Marker2D`+`Marker2D2`..`Marker2D7`，
> 依次对应 `fireProjectileList` 的 `firePosId = 0..6`），上面写的 1 条只是**格式示例**。
> 路径的父节点名（`<新节点名>`）要 7 条一起改；节点名本身仍必须是 `Marker2D*`
> （`ResolveOwnerNode<Marker2D>` 按类型找，见上）。

### 步骤 5：重跑生成器 + 校验
```bash
python build_super_gatling_pea.py       # 重新打 .pmod
# 然后跑离线闸门 + 入口发现 + 幂等（脚本在 .cache/）
```

### 步骤 6：装机
装到 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\`。
⚠️ **同 id 两个 `.pmod` 不能同时在 `Mods/`**；`enabled_mods.json` 不存在 ⇒ 一个 Mod 都不加载。

### 步骤 7：进游戏实测（离线只能验字段，验不了观感）
放下植物看四件事：① 外观对不对；② 豌豆是否 7 颗/1.5s；③ **出膛点是否贴枪口**；④ 大招 10%/5s/300 颗/±15°。

---

## 7. 需要你提供什么（如果要我动手）

按你选的路线，最少需要下面这些。**给一半我也能开工，但会来回问。**

### 路线 A（我只需要一个决定）
> **「换成哪个内置角色？」** 给我角色名就行（如 `GatlingPeaZ` / `CatGatlingPea`），
> 剩下的路径、clip 名、Marker2D 位置我去解包树里查。

可选加分项：
- 出膛点的大致位置（「枪口在嘴上方 8 像素」这类口头描述也行，我会算坐标）。

### 路线 B（我需要素材 + 工程）
1. **Adobe Animate 源文件**：`.fla` 或 `.xfl`（二选一，这是唯一被支持的两格式：
   `XWAdobeAnimateImportService.cs:78-81`）。
2. **如果是 `.xfl`**：`DOMDocument.xml` + 素材目录（`LIBRARY/` 里的所有 PNG/SVG）要**在一起**。
3. **必须包含的 clip 名**（否则请明确告诉我走 §5.3 出路二）：
   `BodyIdle` / `HeadFire` / `HeadIdle`。
4. **图层/媒体命名规则**：如果你希望沿用现有的图层结构（`Head` / `barrel` / `leaf`…），
   请按同名命名；如果重新设计，请给一份「图层名 → 用途」的对照表。
5. **参考尺寸**：内置 `GatlingPea` 的图集是自包含的（尺寸在 `.dat` 头里，`u16 × u16`），
   帧率 `frameRate = 12.0`、`frameMax = 89`、`Head` 子节点 `offset = Vector2(-36, -46)`。
   你的素材**不要求和它同尺寸**，但**建议同量级**（单帧大致 100×100 上下），否则出膛点/缩放要重调。

### 文档参考（我能自己读，你只要点头）
下面这些我已经读过并核实过行号，**不需要你另外提供**：
- `addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs`（`.dat` 解析）
- `addons/AdobeAnimateEditor/Runtime/AdobeAnimateAtlasProfile.cs` + `AdobeAnimateGlobalAtlasManifest.cs`
- `addons/AdobeAnimateEditor/Tools/XWAdobeAnimateImportService.cs`（导入器）
- `addons/ModEditor/ModSystem/ModLoader.cs`（`AnimationAtlas` 通道、路径重定位）
- `Tests/ModEditorAnimationAtlasProfileRuntimeProbe.cs`（官方回归探针，可当用法范例）
- `FireComponent.cs` / `TowerDefenseCharacter.cs`（发射链路）

---

## 8. 硬约束清单（违反 = 不加载 / 不生效 / 静默失败）

| # | 约束 | 依据 |
|---|---|---|
| 1 | 包内自引用**必须相对路径** `./…`；指向游戏内置才用 `res://` | `ModLoader` 解包到 `user://ModsCache/` |
| 2 | **角色场景必须显式声明 `ComponentSet`** | 否则基场景那份（不含 FireComponent）生效 ⇒ 一颗弹都不出、零日志 |
| 3 | `Sprite/<Key>.tscn` 与 `Scene/<Key>.tscn` 文件名 == 目录名 == `Key` | `XWModContentValidation:35-36` |
| 4 | 包内**禁** `.scn` / `.res` / `.cs`、禁内嵌脚本 | `PrepareSafeCharacterPackage` 会拒包 |
| 5 | `[ext_resource type="Script"]` 的 path 非 `res://` ⇒ `.tres` 拒包 / `.tscn` 剥行并**回写文件** | `SanitizeCharacterTextResource`；⚠️ `type="Resource"` 不受影响 |
| 6 | 新图集**不能手写 manifest**（`SourceSignatures` / `MediaRects` 是指纹+布局） | 必须走编辑器导出 |
| 7 | `HeadFire` / `HeadIdle` / `BodyIdle` 名字一字不差（或明确走插件兜底） | `ComponentSet:82-91` + `FireComponent:3230` |
| 8 | `firePosMarkerPaths` 必须指向真 `Marker2D` | `FireComponent:1254` 带类型过滤 |
| 9 | 改完**必须重跑生成器**（`.pmod` 是从工程重新打的） | 工程改动不会自动同步 |

---

## 9. 我现在就能帮你做的

- **路线 A**：你报一个内置角色名，我可以直接把上述 4 处改完、重打包、跑全套离线校验。
- **路线 A'**：如果你想要「换图不换动画」，我可以评估用 `extraMediaReplaceTexturePaths`
  只替换若干媒体名的可行范围（会把能换和不能换的列清楚）。
- **路线 B**：先给我 `.fla` / `.xfl` 和 clip 名，我按导入器的要求盘点素材完整性，
  再走编辑器导入 → 生成 `.dat`/`.tres` → 接进包。
- **兜底**：如果你想用没有 `HeadFire` 的素材，我可以帮你把 ComponentSet 调成
  「无开火动画 + 插件 `Fire()` 兜底」的形态（§5.3 出路二），保证豌豆照打。

---

## 10. ⛔ 路线 C（**已退役**）：自制 `.dat` + 头独立分层

> ⚠️ **2026-09-20 起本 Mod 已改用「路线 D：官方素材直转」（见 §11）**。
> 本节保留，因为：① `.dat`/`.tres` 的**格式知识两条路线共用**；② 若将来确实拿不到官方 reanim 而必须自制素材，仍走这条链。
> 对应脚本 `.cache/build_source_single.py → build_atlas2.py → build_dat.py → build_tres.py`（`DISPLAY_SCALE=0.5`），
> 以及 5 个单帧专用验证器（现已带 LEGACY GUARD，`frameMax != 1` 时自动 SKIP）。

> 本节记录当时**实际完成的替换（路线 C）**。路线为「**自制 `.dat`（整帧单层）+ 头独立分层**」，
> 并**按素材 muzzle 精确对准出膛点**。
>
> **素材已换代两次**：
> 1. `PeaShooterVeteran` **25 帧 idle + 25 帧 shoot**（每帧 176×192，动画）
> 2. **单帧静止图 352×384**（2026-09-20，用户要求「把动画换成单张贴图」）——**已被路线 D 取代**

### 10.1 素材规格（对照检查用）

#### 10.1.1 素材：单帧静止图（2026-09-20 起用；⛔ 已被路线 D 取代，见 §11）

| 项 | 值 |
|---|---|
| 源文件 | `source/SuperGatlingPea_single.png`（由 `.cache/build_source_single.py` 从用户原图生成） |
| 尺寸 / 格式 | **352×384** RGBA8（**恰为 176×192 的精确 2 倍**） |
| **原图背景** | ⚠️ **不透明深灰 `(34,34,40)`，alpha 全 255**（占 48.4%）—— 必须先转透明 |
| 背景处理 | `build_source_single.py`：**flood fill（BFS 从画布外缘）+ 软过渡** |
| 内容 bbox | `(30, 19, 320, 349)` = 290×330 ⇒ 渲染 145×165 |
| 分层规则 | `SPLIT_Y = 128`（画布空间）；单帧下实际切在原生 `y=256`（= 128×2） |
| 帧数 | **1 帧**（`frameMax = 1`） |
| 锚点（实测） | `root = (138.5, 348)` ÷2 = **(69.25, 174.0)**；`muzzle = (314.0, 125.5)` ÷2 = **(157.0, 62.75)** |

> ★ **`SPLIT_Y=256`（原生）正好切在颈/领口**：原生 `y=240..254` 是宽约 24~27 px 的脖子，
> `y≥255` 突增到 55 px 是肩部 ⇒ 头/身分得很干净，不需要微调分层线。

#### 10.1.2 历史素材：多帧动画（已被替换）

| 项 | 值 |
|---|---|
| 帧文件 | `PeaShooterVeteran_idle_00..24.png` + `..._shoot_00..24.png`（各 25 帧） |
| 单帧尺寸 / 格式 | **176×192**，RGBA8，透明底 |
| 元数据 | `frameRate=12.0`；`anchor.root=[80,158]`（脚底）；`anchor.muzzle=[152,54]`；shoot `fireFrame=11` |
| 分层规则 | `SPLIT_Y = 128`（`y<128` = head，`y≥128` = body） |
| 帧序 | idle `0..24` → shoot `25..49`（**共 50 帧**） |

### 10.2 三件套产物

#### 10.2.1 产物（单帧，2026-09-20；⛔ 已被路线 D 取代，见 §11）

| 文件 | 大小 | 关键字段 |
|---|---|---|
| `Resources/Animations/SuperGatlingPea.dat` | **466 658 B** | `frameRate=12.0` / `frameMax=1` / 图集 **492×237** / `mediaCount=2`(head=(0,0,291,237), body=(292,0,200,94)) / `layerCount=2`（各 1 个元素）/ `clipCount=3` / **`eventFrameCount=0`** |
| `Resources/Animations/SuperGatlingPea.tres` | **1 161 B** | `animeFile = "./SuperGatlingPea.dat"` / **2 slice** / `sliceTransforms` 两组 `scale=0.5`，origin `(93.0,151.5)` / `(87.75,68.75)` |
| `Resources/Animations/SuperGatlingPeaAtlas.png` | **53 451 B** | 左 head(291×237) 右 body(200×94)；仅供肉眼查看，游戏不读 |

**clip 定义**：`BodyIdle = (0,0)`、`HeadIdle = (0,0)`、`HeadFire = (0,0)`（单帧 ⇒ 三个 clip 全指向第 0 帧）。
⚠️ **三个 clip 名必须都存在**（`ComponentSet` 引用 `fireAnimeClips="HeadFire"` / `spliceIdleAnimeClips="HeadIdle"`，
角色场景 `idleAnimeClip="BodyIdle"`），哪怕它们都指向同一帧。
⚠️ **`fireEvents` 留空** —— 单帧没有「开火第 N 帧」这种时间点；本 Mod 的发射由**托管插件直调 `Fire()`**，
不依赖动画事件（见 §5）。

#### 10.2.2 历史（多帧动画，已被替换）

| 文件 | 大小 | 关键字段 |
|---|---|---|
| `SuperGatlingPea.dat` | 5 127 238 B | `frameMax=50` / 图集 2043×627 / `eventFrameCount=1`(帧 36, `fire`) |
| `SuperGatlingPea.tres` | 7 080 B | 100 slice |
| `SuperGatlingPeaAtlas.png` | 1 919 172 B | — |

**历史 clip 定义**：`BodyIdle=(0,24)`、`HeadIdle=(0,24)`、`HeadFire=(25,49)`；`fire` 事件帧 = `25+11 = 36`。

### 10.3 ★★★ `animeFile` 的相对路径层级（最容易错）

- **不要写 `res://Resources/Animations/...`**：`res://` 只解析游戏自带资源（`Prefab`/`Asset`/`Script`/`Resource`/`Registry`/`Extends`）⇒ 包内资源加载期找不到。
- **层级必须按「引用方」算**。Sprite 场景位于 `Resources/Characters/Plants/<Key>/Sprite/`（**5 段**），
  动画位于 `Resources/Animations/` ⇒ 需要 **5 个 `../`**：

  ```text
  ../../../../../Resources/Animations/SuperGatlingPea.tres
  ```

  ⚠️ 写成 4 个 `../` 会解析成 `Resources/Resources/Animations/...` → **MISSING**。
  **不要手算层数**，写完用 `posixpath.normpath` 断言「解析结果在包内真实存在」。
- `.dat` 侧写 `./SuperGatlingPea.dat`（同目录同名，命中 `ResolveAnimeFilePath` 的 `TryResolveOwnerBasenameCompanionDat` 兜底）。

### 10.4 ★★★ `offset` / `Marker2D` 标定（出膛点对准 muzzle）

**⚠️⚠️⚠️ 先看这条（2026-09-20 实机「头压在身体上」的真因）**

引擎**自己会把 `origin` 加回去**：

```csharp
// AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform
new Transform2D(..., new Vector2(slice.Ox + offset.X, slice.Oy + offset.Y));  // ← origin + offset
return parent * transform2D;
```

⇒ **落点 = `origin + offset`** ⇒ **`offset` 与 `origin` 无关**，只 = 「把 anchor 挪到节点原点」的位移。

| | 公式 | 结果 |
|---|---|---|
| ✗ 错（曾用） | `根 offset = -(anchor - bodyOrigin)`、`Head offset = -(anchor - headOrigin)` | 落点 = `2*origin - anchor` ⇒ **头身位移 ×2** ⇒ **头压在身体上** |
| ✓ 对 | `根 offset = Head offset = -anchor`、`Head.position=(0,0)` | 落点 = `origin - anchor` ⇒ 相对位移恰 = origin 差 ⇒ **拼合正确** |

**内置反证**：`GatlingPea.tscn` 根 `offset=(-40,-40)`、Head `offset=(-36,-46)` 都是**小整数**，
而各层 `origin` 在 20~60 ⇒ 若公式真是 `-(anchor-origin)`，offset 早该是几十上百的量级。
（`Head.position=(3.6000023,3.616665)` 是**显式存在**的；本 Mod 取 `Head.position=(0,0)` + 两层同 offset，**数学等价**。）

⚠️ **头身相对位置完全由各自 `origin` 决定**；两层用**同一个** `offset` 时，节点原点重合，
落点差恰 = `origin` 差 ⇒ 拼合自然正确。

#### 10.4.1 ⚠️⚠️⚠️ 先做显示缩放，再算 offset（**最容易漏的一步**）

**踩过的坑**：所有 offset/Marker2D 都按「素材画布像素」直接算 —— 结果角色**比内置大 2.5~3 倍**。

**真因**：素材是**放大 2 倍**画的（角色 144×170 塞进 176×192 画布）。
交付目录里另有基准图 `_source_cutout_1x.png` = **72×85**，恰是 144×170 的 **1/2**，
也等于 `_frames.json` 的 `scaleFromSource=2` 的倒数。**正确 `DISPLAY_SCALE` = 0.5。**

对照证据（三条独立来源）：

| 来源 | 数值 | 结论 |
|---|---|---|
| 素材角色 bbox | 144 × 170 | 基准的 2 倍 |
| 交付基准 `_source_cutout_1x.png` | 72 × 85 | = 144/2, 170/2（精确到 4 位） |
| 内置 `GatlingPea.tres` | `sliceTransforms` scale **0.4118 ~ 1.0**，842 条逐条算 `rect_w*scale` ⇒ 渲染最大边 **58.70 px** | 内置同样走「大图 + scale 缩小」 |

⚠️ **写 `scale=1.0` ⇒ 按 144×170 满画 ⇒ 约 2.5~3 倍大。**

**★★★ `origin` 必须跟着一起乘 0.5**：`origin` 是**跨层公共画布坐标**，
渲染时先做 `transform(含 origin)` **再整体乘 `scale`**。
⇒ 只缩 `scale` 不缩 `origin`，角色会偏离约 **2 倍距离**。
（注意：这跟上面的 `offset` 是**两件独立的事** —— `origin` 要乘 0.5，但 `offset` **不等于** `-anchor ± origin`。）

**渲染空间换算（当前素材 = 单帧 352×384）**：

```text
素材（画布空间，÷2）              渲染/写盘空间
anchor.root   = (138.5, 348)   →  (69.25, 174.0)
anchor.muzzle = (314.0, 125.5) →  (157.0, 62.75)
bodyOrigin    = ( 93.0, 151.5)  ← author2.json 直接给（**已 ×0.5**，仅自检用）
headOrigin    = ( 87.75, 68.75) ← author2.json 直接给（**已 ×0.5**，仅自检用）

根   offset = -(69.25, 174.0)                      = (-69.250,-174.000)
Head offset = -(69.25, 174.0)                      = (-69.250,-174.000)   ← 与根**完全相同**
Head.position                                       = (  0.000,   0.000)
Marker2D    = anchor.muzzle - anchor.root          = ( 87.750,-111.250)
```

⚠️ **`Marker2D` 别再叠加一次 offset**：它是子节点，`position` 就是**相对节点原点**的位置，
而节点原点已经 == `anchor.root`（由 offset 摆好）⇒ 直接 `anchor.muzzle - anchor.root` 即可。

⚠️ **「谁乘了 0.5」要分清**：
- `bodyOrigin` / `headOrigin` 取自 `author2.json` 的 `ox/oy`，那里**已经乘过** `DISPLAY_SCALE`
  （`build_atlas2.py:225`：`'ox': cx * DISPLAY_SCALE`）⇒ **不要再乘一次**。
- `anchor.root` / `anchor.muzzle` 在标定块里是**素材画布坐标**，**需要显式 ÷2**。

#### 10.4.1b ★ `origin` 的坐标语义（用真实源码反查确认）

`.tres` 的 `sliceTransforms` 每 slice 6 个 float，直通 `Transform2D(Xx, Xy, Yx, Yy, Ox, Oy)`
（`AdobeAnimateData.cs:1484-1489` 写入、`:2820` 读出，**全程无额外缩放**）。
渲染时由 `AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform` 组装：

```csharp
new Transform2D(
    new Vector2(slice.Xx * sourceSize.X, slice.Xy * sourceSize.X),   // X 基向量 = scale × 帧宽
    new Vector2(slice.Yx * sourceSize.Y, slice.Yy * sourceSize.Y),   // Y 基向量 = scale × 帧高
    new Vector2(slice.Ox + offset.X,     slice.Oy + offset.Y));      // origin 直接相加
```

⇒ 该层贴图尺寸 = `scale × 帧宽` × `scale × 帧高`，而 **`(Ox, Oy)` 就是这块贴图在父坐标系里的落点**。
实测拼回（`.cache/_recon_by_center.png`）证明 **`(Ox,Oy)` 是「该层内容 bbox 的几何中心」**，
即：`origin = (内容 bbox 中心，在完整素材画布上量) × DISPLAY_SCALE` —— 这正是 `build_atlas2.py` 的算法。

> 交叉验证：内置 `PeaShooter.tres` / `GatlingPea.tres` 的 `sliceTransforms` 里
> `scale=0.5554` 但 `origin ≈ (19~56, 45~62)`，若把 origin 当成「层内局部坐标」会超出
> 自身 `44×22` 的小帧 ⇒ 反证 origin 是**跨层的公共画布坐标**，与本节结论一致。

#### 10.4.2 标定值一览（**单帧素材口径**；⛔ 已被路线 D 取代，见 §11）

```text
DISPLAY_SCALE = 0.5
ANCHOR_ROOT   = (69.25, 174.0)      # 素材实测 (138.5,348)  ÷2
ANCHOR_MUZZLE = (157.0, 62.75)      # 素材实测 (314,125.5) ÷2
BODY_ORIGIN   = (93.0, 151.5)       # author2.json（已 ×0.5，勿再乘；仅自检用）
HEAD_ORIGIN   = (87.75, 68.75)      # author2.json（已 ×0.5，勿再乘；仅自检用）

根   offset   = (-69.250,-174.000)  # = -ANCHOR_ROOT
Head offset   = (-69.250,-174.000)  # = -ANCHOR_ROOT（与根**完全相同**）
Head.position = (  0.000,   0.000)
Marker2D      = ( 87.750,-111.250)  # = ANCHOR_MUZZLE - ANCHOR_ROOT
```

自洽校验：`Marker2D`（子节点，相对节点原点）== 炮口像素在节点空间的位置 `ANCHOR_MUZZLE - ANCHOR_ROOT` == `(87.75,-111.25)` ✓。
（⚠️ **别再写成 `ANCHOR_MUZZLE + HEAD_OFFSET`** —— 那是把 `offset` 当节点位移，会多减一个 `ANCHOR_ROOT`。）
**推导自洽；实机仍需肉眼确认。**

> 历史（多帧素材）标定值，仅作对照：
> `ANCHOR_ROOT=(40,79)` / `ANCHOR_MUZZLE=(76,27)` ⇒ 按**正确公式** 根 offset = Head offset = `(-40,-79)` / `Marker2D=(36,-52)`。
> ⚠️ 当时记录的 `根 offset(6.525,-2.51)` / `Head offset(4.27,-44.49)` 是**旧错公式 `-(anchor-origin)`** 的产物，**别再照抄**。

**调法**：若实机炮口偏高/偏低，只微调 `Marker2D` 的 y；若整只角色站位不对，**同时**平移两个 `offset`（两层必须保持相同）；
**若整只角色大小不对，改 `DISPLAY_SCALE`（同时 `origin` 必须同比变）——别只调 `offset`。**

#### 10.4.3 ⚠️ `scale` 存在两处，改必须一起重跑

| 位置 | 写入者 | 说明 |
|---|---|---|
| `.dat` 的 layer 表（每元素 30 B：`u16 mediaId` + `f32 xx,xy,yx,yy` + `f32 originX,originY` + `u32 RGBA`） | `build_dat.py`（`sc = s['scale']`） | **`.dat` 也带 scale/origin** |
| `.tres` 的 `sliceTransforms`（每 slice 6 个 float：`sc,0,0,sc,ox,oy`） | `build_tres.py` | 同上 |

⇒ **改 `DISPLAY_SCALE` 必须 `build_atlas2.py` → `build_dat.py` → `build_tres.py` 全部重跑**，
只重跑 `build_tres.py` 会留下「`.dat` 与 `.tres` scale 不一致」的隐性故障。

### 10.5 双图层父子精灵场景（对齐内置范式）

```text
[node name="SuperGatlingPeaSprite" type="Node2D"]     ← 根：只显示 body
  script        = res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs
  flashAnimeData= ExtResource("2_data")   ← ./…/SuperGatlingPea.tres
  Animation/Clip                = "BodyIdle"
  Animation/LayerVisible/body   = true
  Animation/LayerVisible/head   = false
  offset = Vector2(-69.25, -174.0)        ← = -ANCHOR_ROOT

[node name="Head" type="Node2D" parent="."]            ← 子：只显示 head
  unique_name_in_owner = true
  position      = Vector2(0, 0)           ← ★ 必须 0（两层同 offset 时不能再偏移）
  script        = 同一份 AdobeAnimateSpriteBase.cs
  flashAnimeData= 同一份 AnimeData（**共用，不是拷贝**）
  parentSprite  = NodePath("..")
  Animation/Clip                = "HeadIdle"
  Animation/LayerVisible/body   = false
  Animation/LayerVisible/head   = true
  Layer = 2   insertLayerId = 2   followParentSpriteLayerId = 0
  offset = Vector2(-69.25, -174.0)        ← ★ 与根**完全相同**
```

- **`followParentSpriteLayerId = 0`** = 对齐父精灵的**动画基底层** `body`
  （内置是 `8`，因为内置 `layerDictionary["anim_idle"] = 8`；**不是** `GatlingPea_helmet`(19)）。
  它只影响渲染排序带（`ResolveSpriteChildFollowLayer:8062-8073`），**不参与可见性**。
- `Layer` / `insertLayerId = 2` = 压在父精灵可见层数（`body`=0、`head`=1 之后）之上。

> ⚠️⚠️ **这个「`Head` 直接挂根精灵下」的形状有隐患**（2026-09-22 晚由僵尸侧实锤，见 §11.9）：
> 头是**父精灵的子精灵** ⇒ 引擎走「**父代画**」⇒ 头自己那份 `forceLocalRender` / `forceCpuPoseRender`
> **永远读不到**（`AdobeAnimateSprite._Draw():9534` 首行就 `return`）⇒ 头切片由**父精灵的渲染批次**代画，
> 采样的是**父精灵那本图集**。
>
> ⇒ **本植物包侥幸没出事**：root 与 `Head` **共用同一份 `.tres`** ⇒ 同一个 definition ⇒ 同一份
> `MediaAtlasPages` ⇒ 算出来的矩形仍然是对的。
> ⇒ **但只要你把 `Head` 换成另一份 `.tres`（换头！），或换成一个不在全局图集清单里的自制皮肤，
> 就会立刻变成「一团别的角色的图集碎片」**。
>
> 正确形状见 §11.9（三节点：`HeadShadow` + `HeadHolder` + `Head`）。

### 10.6 角色场景改动

| 位置 | 改成 |
|---|---|
| `ExtResource("6")`（sprite） | `../Sprite/SuperGatlingPea.tscn`（**不再指向内置 GatlingPea**） |
| `Marker2D` position | `Vector2(36, -52)`（**不再沿用内置 `(31.740002,-17.82)`**，也不是对半缩放前的 `(72,-104)`） |
| 节点名 | 保留 `GatlingPea` 与 `.../TransformPoint/GatlingPea/Head/Marker2D`（`ComponentSet` 写死该 NodePath，**不能改**） |

### 10.7 ⚠️ 改完必须重跑生成器（`build_plant_super_gatling.py`）

**该脚本已改造为生成自制外观**，否则重跑一次就会回退成内置贴图：

- `sprite_scene_tscn()` → 生成上面 §10.5 的双图层父子场景（不再是内置指针壳）
- `plant_scene_tscn()` → `ExtResource("6") = ../Sprite/<Key>.tscn`、`Marker2D = (36,-52)`
- `build_manifest()["resources"]` 含三件套
- `sync_skin_assets()` → 把 `.cache/` 的三件套同步进 `Resources/Animations/`
- `self_check()` 含 `#13`~`#13e` 反向校验（外观/offset/Marker2D/三件套/animeFile）；
  ⚠️ offset/Marker2D 用 `_near(..., tol=0.01)` **容差比对**（场景里写的是四舍五入短小数，
  精确 `==` 会假红），并额外断言「不得仍是 `(72,-104)` 旧口径」

产出脚本链（在 `.cache/`，**按序**）：`build_atlas2.py` → `build_dat.py` → `build_tres.py`；
`build_atlas2.py` 顶部有 `DISPLAY_SCALE = 0.5`（`scale` 与 `ox/oy` 都乘它）。
校验 `.cache/verify_skin_assets.py`（**79 OK / 0 FAIL**，含 3 条 `scale` 断言 + 两层 offset 必须相同 + `Head.position==(0,0)` + 2 条旧错值反例）。

### 10.8 ⚠️ 已知边界与待确认项

| 项 | 说明 |
|---|---|
| **实机验证** | `Marker2D=(87.75,-111.25)` 与 `offset=(-69.25,-174.0)`（**根/Head 相同**）数值推导自洽、假渲染已确认头身拼合，但**必须进游戏肉眼核对**头身接缝、炮口位置、站位与**渲染大小（应约 145×165 px，与内置 58.7 px 同量级）** |
| **⚠️ `offset` 公式** | **落点 = `origin + offset`**（`AdobeAnimateDrawItemBuilder.cs:1079` 引擎自加 origin）⇒ `offset` **与 origin 无关**，只 = `-anchor.root`，两层必须**完全相同**。曾错写 `-(anchor-origin)` ⇒ 头身位移 ×2 ⇒ **实机「头压在身体上」** |
| **显示缩放**（路线 C 专用） | `DISPLAY_SCALE = 0.5`。⚠️ 曾漏写（=1.0）⇒ 角色大 2.5~3 倍；`origin` 必须同比乘（层内坐标，渲染时整体再乘 scale） |
| **图集宽度余量** | 当前 492 / `MaxAtlasPageSize` 2048 ⇒ **余量充足**。（历史 2043 版只剩 5 px。）standalone 分支不校验 2048 |
| **单帧模式的 `clips`** | 三个 clip **全指向 `(0,0)`**，但**名字必须都存在**（`ComponentSet` 与角色场景都会引用）；`fireEvents` 留空（发射靠托管插件直调 `Fire()`） |
| **`.import`** | 不需要。`.dat`/`.png` 由 `FileAccess` 直接读；`.png` 仅供肉眼查看 |
| **`.tres` 语义写法** | `sliceKeys = (layerId<<16) \| 槽序号`（**不是 `\| mediaId`**）；`sliceDrawOrders` 是 **per-layer-per-frame**（本 Mod 每层每帧 1 个元素 ⇒ 全 0）。依据 `BuildPackedRuntimeData:1480/:1482`，并用内置 `GatlingPea.tres` 842 项反证（旧写法有 586 项不成立） |

### 10.9 验收证据（离线，单帧素材版）

- `build_plant_super_gatling.py` 自检通过；包内 **12 条目**；装到 `Mods/超级机枪射手.pmod`（**122 773 B**，`md5 c96b01537a340b28…`）+ `Mods/超级机枪射手/`
  （对比：多帧版是 `3 865 432 B` —— 单帧把 5 MB 动画数据压到 0.47 MB）
- `verify_skin_assets.py` **79 OK / 0 FAIL**（含 3 条 `scale`/origin 断言 + 两层 offset 全等断言 + `Head.position==(0,0)` + 2 条旧错值反例断言）
- `check_plant_super_gatling.py` **220 ok / 0 FAIL / 1 warn**；`check_project_folder.py` **40 ok / 0 FAIL**；`verify_pmod.py` **12 ok / 0 FAIL / 9 warn**
- ModLoader 闸门 **33 ok / 1 warn / 0 FAIL**；入口发现全绿（`总结: 全绿 ✔`）；**C# 闸门两份构建各 52 PASS / 0 FAIL**（`.cache/run_gates_plant.py`）
- 整包重建 **13 文件字节全稳定（幂等 0 差异）**（`check_sgp_idem_single.py`）
- 包内每个 `res://` 都指向游戏自带资源、每个相对引用都能解析到真实条目（已逐条核对）
- 假渲染 `.cache/_render_fixed.png` / `_render_fixed_3x.png`（按「落点 = origin + offset」重绘）已肉眼确认
  **头身按 origin 差正确拼合**、红点（节点原点）落在叶片底部、蓝点（muzzle）落在炮口

### 10.10 ★ 素材形态澄清（回应「把动画当贴图了」）

#### 单帧贴图（2026-09-20 起；⛔ 已被路线 D 取代，见 §11）

用户指出上一版「25+25 帧动画」不是他要的「单张贴图」，并提供了**单帧静止图**。
现在的外观是**一张图集 + 两个图层 + 1 帧**：

```text
SuperGatlingPeaAtlas.png（492×237，53 451 B）
├── media[0] head  rect (  0, 0, 291, 237)   ← 单帧
└── media[1] body  rect (292, 0, 200,  94)   ← 单帧
```

- `.dat`：`frameMax=1`、`clipCount=3`（三个 clip 全 `(0,0)`）、`eventFrameCount=0`
- `.tres`：**只有 2 个 slice**（body + head），`frameOffsets=[0]`、`frameCounts=[2]`
- 头/身仍分层（根 `body` + 子 `Head`），**共用同一份 AnimeData** —— 这是为了让
  `Head` 子节点能独立承载 `Marker2D`（出膛点必须挂在 Head 上，随头一起动）

⚠️ **背景必须处理**：用户原图是**不透明深灰底**（`(34,34,40)`，alpha 全 255）。
`build_source_single.py` 用 **flood fill（BFS 从画布外缘）+ 软过渡**转透明 ——
**只把「颜色≈背景 且 连通到外缘」的像素置 0**，避免误伤角色内部的近黑暗部/描边。
（用「全图同色即透明」会毁掉描边。）

#### 历史：多帧动画（已被替换）

```text
SuperGatlingPeaAtlas.png（2043×627，1 919 172 B）
├── media[0] head  rect (0,   0, 2029, 475)   ← 25 帧竖排
└── media[1] body  rect (0, 357, 2043, 270)   ← 25 帧竖排
```

游戏**不是**把这张 PNG 当一张静态贴图整个显示，而是靠 `.dat` 的索引**逐帧从图集里取子矩形**：
`ComponentSet` 声明 `fireAnimeClips="HeadFire"` ⇒ 开火切到 `HeadFire`（帧 25–49）；
帧 36 触发 `fire` 事件 ⇒ 从 `Head/Marker2D` 生成豌豆。

**内置 `GatlingPea` 也是同样的结构**（89 帧、17 个 media、842 个 slice 挤在一张图集里），
这是 `AdobeAnimateData` 格式的固有形态（「大图 + scale 缩小 + 逐帧索引」），
**不是**「一张 PNG 当贴图用」。

> ★ **单帧与多帧走完全相同的管线**，只是 `frameMax` 50→1、`slices` 100→2、clips 收敛到 `(0,0)`、
> `fireEvents` 清空。`build_atlas2.py` 里用 `SOURCE_MODE = 'single' | 'deliver'` 一个开关切换。

---

## 11. ★★★ 路线 D（**当前首选，已落地**）：官方素材直转

### 11.0 这条路线是什么

**植物大战僵尸杂交版的「未重置版本」就是经典 PvZ 引擎**，里面**比重置版多**很多角色的原始素材：
每个角色都有 `*.reanim.compiled`（完整逐帧骨骼/部件动画）+ `reanim/IMAGE_REANIM_*.png`（官方贴图）。
本 Mod 的「超级机枪射手」在未重置版里就是 **`SuperGatling.reanim.compiled` —— 27 轨 × 87 帧 @12fps**。

⇒ **直接用官方素材逐帧直转**成重置版的 `.dat`/`.tres`/图集，**画质、动作完整度都远好于自制单帧素材**，
且**不需要任何抠像/背景转透明**（官方 PNG 本就带 alpha）。

| 对比 | 路线 C（自制，已退役） | **路线 D（官方直转，现行）** |
|---|---|---|
| 素材来源 | 自己画 / 从单张图抠像 | 未重置版 `*.reanim.compiled` + `reanim/*.png` |
| 帧数 | **1 帧**（静止） | **87 帧**（逐帧动画） |
| 图层 | 2（body + head） | **27**（全部轨道保留） |
| slice 数 | 2 | **1168** |
| `.dat` | 466 658 B | **344 418 B**（更小，因为图集更紧凑） |
| 缩放口径 | 素材放大 2 倍画 ⇒ `DISPLAY_SCALE=0.5` | **无额外缩放**（经典 `sx/sy` 即最终缩放） |
| 生成入口 | `build_source_single → build_atlas2 → build_dat → build_tres` | **`.cache/build_official_skin.py`（一条链）** |
| 验证器 | `verify_skin_assets` 等 5 个（**已退役**） | **`.cache/verify_official_skin.py`** |

### 11.1 素材在哪

```text
D:\zzz\extract_1789988101\                 ← 未重置版（经典引擎）解包根
├── compiled\new\SuperGatling.reanim.compiled    ← 二进制动画（27 轨 × 87 帧）
├── compiled\new\SuperGatling.reanim              ← 同名 XML（人看/对拍用）
└── reanim\IMAGE_REANIM_SUPERGATLING_*.png        ← 官方贴图（本角色用到 23 张）
```

两套引擎资产形态**完全不同**，别找错：

| | 经典（未重置版） | 重置版（Godot4 + C#） |
|---|---|---|
| 动画 | `*.reanim.compiled` / `*.reanim`(XML) | `*.tres`(`AdobeAnimateData`) |
| 贴图 | `reanim/*.png`（**散装、带 alpha**） | `*.dat`（**自包含图集，图片塞在里面**） |
| 场景 | `*.reanim` 里的 track | `*.tscn` |

### 11.2 经典 reanim 二进制格式

```text
外壳: d4feadde + u32(解压后长度) + zlib
内层头 28 B: magic c0b493b3 | u32@4 | u32@8 = 轨道数 | f32@0xC = fps | u32@0x10 | u32@0x14
轨道表 @0x1C: 轨道数 × 3×u32        ← 帧数 = 条目第 2 个 u32
逐轨道: 名字(ASCII, 以 ',' 结尾) + 3 字节 + 帧数据[帧数 × 44 B] + 尾部(图片名表)
帧记录 44 B = 11 个 f32: x, y, kx, ky, sx, sy, f, a, ?, ?, ?
未设置字段 = 哨兵 -10000.0f（SENT = 继承上一帧）
```

- ⚠️ **末轨的图片名表必须自己从文件尾补扫**：通用解码器靠「找下一个轨道名」给尾部定界，
  末轨没有下一轨 ⇒ 尾部为空 ⇒ 那张图（本例 `overlay2`）会**悄悄丢失**。修法 = 末轨从
  `data_off + 帧数×44` **扫到文件尾**再正则 `IMAGE_[A-Z0-9_]+`。

### 11.3 映射规则（12 条，全部经内置角色反证）

1. **轨道 → 图层 1:1，全部轨道都保留**（`layerId == 轨道序号`）。无图控制轨（`anim_idle`/`anim_head_idle`/`anim_shooting`/`anim_power`）也保留成层。
2. **帧 → 帧 1:1**（`frameMax = 87`）。
3. **变换 = 旋转矩阵**：`[sx·cos(kx°), sx·sin(kx°), −sy·sin(ky°), sy·cos(ky°), x, y]`（4 位小数对拍通过）。
4. ★ **不要乘任何额外缩放**：经典 `sx/sy` **就是**最终渲染缩放（`GatlingPeaZ` 全轨 `sx=sy=0.5550`，PNG 44×22 → 渲染 24.4×12.2）。
5. **`SENT(-10000)` = 继承上一帧**；首帧未定义取默认。
6. **第 7 个 f32 `f`**：`f < 0` ⇒ 该 (层,帧) **不产 slice**；`f >= 0` ⇒ 索引该轨的 `imgnames`。
7. **无图控制轨的可见帧产 `locator.png`（2×2 全透明）占位 slice** —— 内置 `PeaShooter.anim_stem` 同做法，借此保住 `sliceDrawOrders == sliceLayerIds`。
8. **clip 边界读控制轨 marker** ⇒ `BodyIdle(0,24) / HeadIdle(25,49) / HeadFire(50,86)`。
   ★ `HeadFire` 必须**同时覆盖射击段（50..74）和大招段（75..86）** —— `FireComponent` 循环播它，只给射击段就看不到大招。
   ⚠️★ **2026-09-24 植物包例外**：这条规则只对**僵尸包**成立。植物包由 `FireComponent`
   在**每一轮 1.5s 普攻**都播一遍 `HeadFire`，把 75..86（3 帧一循环的剧烈抖动，头部轨道
   `(22,7)↔(19.5,13.8)↔(17.9,19.5)` 每帧跳变、振幅 ~12.5px、重复 4 次）也播进去 ⇒
   实机表现就是「**一轮射击打完后头部抽搐**」。植物包已在生成器里把 HeadFire 收窄为
   **(50,74)**（= 内置单发家族口径，f50 与 f74 位姿相同=闭合循环），`75..86` 不再被任何
   clip 引用；共享三件套不动，补丁只打在植物包内副本（`build_plant_super_gatling.py`
   的 `HEADFIRE_CLIP_PLANT` / `_patch_skin_for_plant`）。
9. **一张 `.dat` 只嵌一张图集** ⇒ 全部 media 打进同一张；`mediaRect` = 每张 PNG 的**完整矩形**（不切帧）。
   `media id` = 显示名**大小写不敏感排序**；`.tres` 字典键序 = **ASCII 序**。
10. **根锚点** `offset = (−40,−40)`（内置植物一律如此 ⇒ 经典 `(40,40)` 即种植锚点）。
11. **头身同源 ⇒ 零偏移**：`Head.position=(0,0)`、`offset` 与根**相同**。
    （内置 `GatlingPea` 的 `(3.6,3.6)`/`(−36,−46)` 是它手工微调自己头素材，**不适用**。）
12. **插层** `insertLayerId = max(body 真实贴图层) + 1` ⇒ 本例 **16**（== `anim_idle` 层）。
    ⚠️ body 判据须**排除「只用 locator 占位」的控制轨**，否则会误得 17。

### 11.4 标定结果（`skin_params.json`）

| 项 | 值 |
|---|---|
| 根 offset / Head offset | `(−40, −40)` / `(−40, −40)` |
| Head.position | `(0, −8)` —— ⚠️ **死值**（2026-09-22 更正）：`AdobeAnimateSprite.UpdateChild()`（`:5259-5281`）每帧把它改写成「被跟随图层 pose.Origin + 父 offset」，写多少都不生效。真正决定头位的是 **`Head.offset`** |
| ★ fire 事件 | **`{"Command":"fire","Argument":""}` @ f62**（= HeadFire 起点 +12，对齐内置单发族相位；**留空 ⇒ 只有动画没有子弹**） |
| 射击段 `shoot_range` | `[50, 74]`（大招段 75..86 不发射） |
| `insertLayerId` / `followParentSpriteLayerId` | `16` / `16`（层名 `anim_idle`）|
| body / head 图层 | `[8..15]` / `[0..7, 16..26]` |
| clip | `BodyIdle(0,24)` · `HeadIdle(25,49)` · `HeadFire(50,86)` |
| 炮口（经典坐标） | `(88.552, 30.2)` @ f62 |
| `Marker2D`（Head 子节点，local） | `(48.552, −9.8)` = 炮口 − `(40,40)` |
| 图集 | `256 × 296` |

### 11.5 产物与校验结果

> ⚠️ **本节 = 2026-09-21「路线 D」交付当时的快照**（下面的体积 / sha / 闸门条数是那一天的值，**不是现值**）。
> 后续功能轮次（齐射改版、图鉴去重 + 文案内联）已刷新产物 ⇒ **现值一律以主文档 `植物Mod-超级机枪射手.md`
> 的 §7 验收表 / §14.5 指纹为准**。例：pmod 已由 `175 001 B` → **178 046 B / `332e561932eab22a`**、
> DLL 由 `16 896 B` → **22 016 B / `9298e407b9b599df`**、闸门 52 → **53 PASS**、主门禁 227 → **314 ok**。

| 文件 | 体积 | 哈希 |
|---|---|---|
| `Resources/Animations/SuperGatlingPea.dat` | 344 418 B | `9d62ac6c45b5217d` |
| `…/SuperGatlingPea.tres` | 142 749 B | `fb0c11b58028d409` |
| `…/SuperGatlingPeaAtlas.png`（256×296） | 64 693 B | `d0afaa8a5f8ab318` |
| `dist/超级机枪射手.pmod` | 175 001 B | `2588485551e7acc9` |
| `Runtime/ModAssembly.dll` | 16 896 B | `4a3d8f8ca0042179` |

| 校验 | 结果 |
|---|---|
| `.cache/verify_official_skin.py` | **114 OK / 0 FAIL** ✔（2026-09-21 起含 fire 事件帧/头位断言） |
| 同上 `--negative`（故意写坏副本） | **5/5 报错** ✔（图集篡改 / 场景 offset / `frameMax` / **事件 Command→noop** / **`.dat` 尾部截 4B**） |
| `build_official_skin.py` 自检 | **全绿（0 项）** ✔ |
| `run_gates_plant.py`（remake + console 两份构建） | **各 52 PASS / 0 FAIL** ✔ |
| `check_plant_super_gatling.py` | **227 ok / 1 warn / 0 FAIL** ✔（含新增 §E1–E7） |
| `check_project_folder.py` | **40 ok / 0 warn / 0 FAIL** ✔ |
| `check_modloader_gates.py` | **33 ok / 1 warn / 0 FAIL** ✔ |
| `check_sgp_idem_single.py`（幂等） | **13 一致 / 0 不同** ✔ |

### 11.6 怎么改（换成别的官方角色）

```text
1. 在未重置版解包里定位目标角色的 *.reanim.compiled 与 reanim/IMAGE_REANIM_*.png
2. 改 .cache/build_official_skin.py 顶部：
     REANIM_BIN / REANIM_PNG_DIR / KEY / CLIP_NAMES / BODY_LAST_FRAME / ANCHOR_ROOT
     + media_display_name() 里的前缀映射表
3. 跑 build_official_skin.py ⇒ 产出 .dat/.tres/图集/skin_params.json/预览
4. 跑 ModWorkspace/build_plant_super_gatling.py ⇒ 由 skin_params.json 生成 Sprite/Scene + 出包
   （自检必须全绿；它会拒绝旧自制值）
5. 跑 .cache/verify_official_skin.py（+ --negative）⇒ 114/0 + 5/5
6. 跑 .cache/run_gates_plant.py（两份构建 52/0）+ 幂等检查
7. 装机，进游戏确认观感（离线只能验字段与像素，验不了手感）
```

### 11.7 ★★ 换完外观必查的两件事（2026-09-21 实机 bug 复盘）

用户实机反馈两条：**「攻击时只有动画、没有子弹」**、**「头有点偏下，调高一点」**。都已修复，真因如下。

**① 只有动画没有子弹 = 动画 `events` 表为空。**
普通射击**不由插件驱动**，而是走「动画事件 → FireComponent」：

```
AdobeAnimateSprite.events[当前帧]
  → OnAnimeEvent?.Invoke(Command, Argument)      AdobeAnimateSprite.cs:5327
  → FireComponent.AnimeEvent                     （订阅 FireComponent.cs:1484）
  → Command ∈ fireEventName.Split("&")           fireEventName 默认 "fire"（:343）
  → FireConfiguredVolley() → Fire() 出膛
```

⇒ **`.dat` 与 `.tres` 的 `events` 表都必须含 `{"Command":"fire","Argument":""}`**。
之前写成空表（当时误以为「发射全靠插件」）⇒ 动画照播、**零子弹、加载期零报错**。

- **发射帧 = f62**：`anim_shooting` 起点后枪口轨**首次达最大伸出**的帧；判据 `帧 − HeadFire.start == 12`。
  实证：143 个内置植物里单发族 7 例**全部** `HeadFire=(50,74)` + 恰 1 条 event @ **f62**；多连发按「次极值−1」（61/67/73）。
- **`.dat` 事件段字节布局**：`u16 条数` + 每条(`u16 frameIndex` + `u16 事件数` + 每事件(`PascalString Command`, `PascalString Argument`))。
  ⚠️ **frameIndex 是 `u16`（不是 u32）**，**`Command` 在前**。

**② 头偏低 = 改 `Head.offset`（**不是** `Head.position`）。**（2026-09-22 更正：旧版这段写反了）

- 源码事实：`AdobeAnimateSprite.UpdateChild()`（`addons/AdobeAnimateEditor/Node/AdobeAnimateSprite.cs:5255-5281`）里
  `child.Position = 被跟随图层 pose.Origin + 父精灵 offset`、`child.Rotation = pose.Rotation + child.offsetRotate`
  （`usePos`/`useRotate` 默认 `true`，`:276`/`:279`）⇒ **场景里写的 `Head.position` / `Head.rotation` 每帧被覆盖，是死值**。
  官方样本自己也写着（`ZombieNormalGatlingPea.tscn` 的 `Head.position=(-22.2,-76.3)`、`rotation=-0.158`），同属编辑器残留。
- 另一半也要纠正：**`offset` 不影响 `Marker2D`（炮口）**。它只作用于**本精灵自己那份美术**
  （`:7044`/`:7071`/`:7362` `transform = transform.Translated(offset)`）与子精灵落位；
  `FireMarker` 是 `HeadSlot` 的独立子节点，跟 `Head.offset` 无关。
- ⇒ 头身**同源**时两层 `offset` 应当**相同**（= `−ANCHOR_ROOT`，即上面的零偏移对齐）；
  **要单独抬高/压低头，就在 `Head` 上把 `offset.y` 往负/正调**。
- ⚠️ 因此 `skin_params.json` 里的 `head_raise_px` / `head_position` 目前喂给的是 `Head.position` —— **不生效**。
  真要抬高头，得把 `head_raise_px` 改成写进 `Head.offset`（`build_plant_super_gatling.py::sprite_scene_tscn()` 改一行）。
  **本轮未动植物生成器**（该包已实机可用，不动为妙），此处只把口径更正记下来。
  ★ **2026-09-24 已按此口径落地**（植物包）：`Head.position` 清零（死值不再写 -8），
  真正的头位修正改由 **`Head.offset = (-37.05, -47)`** 承担 —— 以内置豌豆射手为基准
  逐帧反解（Δ 刚性平移，波动 ≤0.27px），同时 `Marker2D = 炮口canvas + Head.offset =
  (51.502, -16.8)` 保持炮口粘在炮管上。推导与断言见 `build_plant_super_gatling.py`
  常量块「2026-09-24 头位对齐」+ 自检 13b/13b-2/13c-2/13f-2。

> ⚠️ **仍未实机确认**：头身接缝、炮口位置、整体观感，`HeadFire` 循环下「射击段 → 大招段」的过渡，
> 以及抬高 8px 后的头身比例。离线只能验字段/字节/像素，**手感与观感必须进游戏**。

---

### 11.8 与「共用判定核心」的交叉影响（2026-09-22）

换外观这条管线**不碰**射击判定，但两者共用同一个生成器与自检，所以会撞到一条**新护栏**：

自 2026-09-22 起，玩法数值的唯一真源搬到了 `runtime_shared/GatlingVolleyCore.cs`
（本植物版与僵尸版《超级机枪读报僵尸》**共用同一份源**），
`build_plant_super_gatling.py` 的 `self_check()` **第 16 节**会做**两问**校验：

1. `runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs` 里每个可调参数必须是
   `= GatlingVolleyParams.X;` 形式的**转发**；
2. 字面量只能在共用核心里出现一次，且必须等于生成器侧记录的期望值。

⇒ 若你在换外观的同时顺手改了插件源码（比如把某个常量写回字面量、或改了转发名），
生成器会**拒绝写盘**（退出码 3），报
`入口源码里的常量 X 应为 \`= GatlingVolleyParams.Y;\` 转发（共用核心）`。
**别绕过它** —— 正确做法是改共用核心里的 `GatlingVolleyParams`，然后
**僵尸版也要一起重编译 + 重打包**（详见《植物Mod-超级机枪射手》§3.7
与《僵尸Mod-超级机枪读报僵尸》§7.6）。

**外观侧完全不受影响**：`.dat` / `.tres` / 图集 PNG / `skin_params.json` 三件套与判定核心无关，
本节之前的所有流程（含 §11 路线 D 的标定值）照旧。

---

### 11.9 ★★★ 引擎级硬约束：**子精灵必被父代画** ⇒ 跨 `.tres` 的子精灵会变成「碎片拼贴」

（2026-09-22 晚在僵尸侧《超级机枪读报僵尸》实机踩到并彻底钉死；**植物侧同源，务必先读这一节**。）

**症状**：某个挂在精灵下面的子精灵，画出来是**一团别的角色的图集碎片**（蓝白菱形 / 黄橙块 / 白豌豆…），
而它**单独拿出来是好的**。

**根因链条（逐条源码实锤）**：

```text
① CollectOwnedChildBindings（AdobeAnimateSprite.cs:5365，判定 :5385）
   **只按 Godot 节点类型**收集子精灵，**完全不看 parentSprite**。
   ⇒ 只要是「精灵的直接子精灵」就被收进 _spriteChildren / _insertedSprites。
   （对「非精灵但有子节点」的中间节点会递归，但那一刻传
     collectSpriteChildren = (ownerSlot != null) ⇒ 普通容器下面的精灵不再被收，:5397）

② ⇒ OwnsSpriteChildForRender（:7774）true ⇒ IsRenderedByParentSpriteForRender（:9559）true
   ⇒ _Draw()（:9534）**第一行就 return**。
   ⇒ 这个子精灵自己的 forceLocalRender 永远走不到（它只在 :9549/:9551 被读，在 return 之后）。

③ ⇒ 子精灵的切片改由**父精灵的渲染批次**代画（AppendChildSprites，:833）；
   TryGetChildRenderLayerForRender（:7986）里的 ResolveSpriteChildInsertLayer（:7998）
   「不返回 -1」⇒ 整批共用**父精灵那一张纹理数组**。

④ 若这个子精灵用的是**另一份 `.tres`**（另一套 definition）⇒ 它的 media 名 / 槽位在父精灵的
   MediaAtlasPages 里对不上 ⇒ 落 BaseAtlasPage = 0
   （AdobeAnimateDrawItemBuilder.ResolveMediaRect:921）
   ⇒ 采样 AdobeAnimateVisualTextureArray.png（**全部角色拼一张**）
   ⇒ 画出来就是**别的角色的碎片拼贴**。

⑤ 自制皮肤更早一步就死：它不在全局图集清单里
   （RefreshAtlas:3489 是**构建期**才写 res://…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres）
   ⇒ MediaAtlasPages 直接解析不到 ⇒ 同样落 0 号共享大图。
```

**⇒ 本植物包为什么侥幸没事**：`root` 与 `Head` **共用同一份 `.tres`** ⇒ 同 definition ⇒ 同 `MediaAtlasPages`
⇒ 哪怕真走了「父代画」，算出来的矩形也是对的。
**⇒ 但这条保护只对「同 `.tres`」成立**：任何**跨 `.tres` 的子精灵**都会中招。

**两个「看起来能躲」但躲不掉的写法**：

| 想法 | 为什么不成立 |
|---|---|
| 「写成 `insertLayerId = -1` 就不插进父批次了」 | `ResolveSpriteChildInsertLayer`（`:8039`）对 `-1` **回落顶层**，不是「不插入」 |
| 「挂到 `TransformPoint` 之类普通节点下就行」 | `ResolveSpriteChildFollowLayer` **优先读子精灵自己的** `followParentSpriteLayerId` ⇒ 取到的是**父精灵的图层**；而 `CollectOwnedChildBindings` 判定时**穿过**非精灵容器（`:5397` 只在中间节点有 ownerSlot 时截断）⇒ 依旧被父代画 |

**唯一能真正断开的写法 = 三节点**（僵尸侧 `build_zombie_super_gatling_paper.py::sprite_scene_tscn()` 已落地）：

```text
<Root>Sprite（身体）
├── HeadShadow  type="Node2D"       ① 位姿影子：身体的直接子精灵
│                                     visible = false + **全层 false**（⇒ 零切片 ⇒ 不产生碎片）
│                                     parentSprite = NodePath("..")
│                                     Layer = insertLayerId = followParentSpriteLayerId = <body 真实贴图层 id>
│                                     唯一作用 = 吃 UpdateChild()（:5208-5286）每帧写的
│                                       Position = 被跟随层 pose.Origin + 父 offset
│                                       Rotation = pose.Rotation + child.offsetRotate
│                                     ⚠️ 该循环**没有可见性判断** ⇒ visible=false **不拦截**定位
├── HeadHolder  type="Node2D"       ② 普通容器（identity，不写 position/rotation/scale）
│   └── Head    type="Node2D"       ③ 可见头：HeadHolder 的子精灵 ⇒ **独立渲染**
│                                     全层 true；**不写** parentSprite / insertLayerId /
│                                       followParentSpriteLayerId / position / rotation / visible
```

- 两个头的 `scale` / `offset` / `offsetRotate` 必须**逐字相同** ⇒ 可见头与「影子若可见」渲染结果完全一致。
- 可见头的**位姿**由插件每帧从影子同步（`process_frame` 早于节点 `_process` ⇒ 1 帧延迟，
  低速动画下 < 1px，肉眼不可见）。
- 可见头挂普通容器下**仍能**被引擎定位：`ResolveSpriteChildFollowLayer` 最终用 `_parentSprite`
  （= `FindParentSpriteAncestor():7797`，最近的**祖先精灵**）⇒ 穿过 `HeadHolder`。

**官方先例**：引擎自带 `Test/AdobeAnimateDetachedChildOwnershipProbe.cs`，就是专门验证这个形状的。

> ⚠️ **本条目前尚未回灌到植物生成器**：`build_plant_super_gatling.py` 仍是老的两节点形状。
> 因为植物包「同 `.tres`」使它对当前素材无害，**但在你换头（换成另一份 `.tres` / 自制皮肤）之前，
> 必须先把它改成三节点**，否则一定出现碎片拼贴。
