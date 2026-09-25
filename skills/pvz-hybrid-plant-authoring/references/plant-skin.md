# 换植物外观：三件套 / 官方素材直转 / 自制 / 复用

## 0. 先搞清「三件套」——不是一张 PNG

```
精灵场景 <Key>.tscn  +  动画数据 <Key>.tres (AdobeAnimateData)  +  <Key>.dat (二进制图集含图)
```

★ **`.dat` 是「自包含图集」，图片就塞在里面**（不是散装 PNG）：

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

**`.tres` 走 `animeFile="./<Key>.dat"` = standalone**（不重打包、加载失败只 `GD.PushWarning` ⇒ **静默不画**）。

## 1. 选路线

| 路线 | 何时用 |
|---|---|
| **A. 官方素材直转（首选）** | 未重置版解包里有该角色的 `*.reanim.compiled` + `reanim/IMAGE_REANIM_*.png` |
| B. 自制单帧 / 手做逐帧 | 拿不到 reanim，或只要一张静止图 |
| C. 复用原版贴图 | 只改数值不改画 ⇒ 场景里 `instance` 原版 `.tscn` + `[editable path="…"]`，**不复制素材进包** |

⚠️ **A 与 B 的缩放口径不同**（自制素材常「放大 2 倍画」⇒ `DISPLAY_SCALE=0.5`；
官方素材 `sx/sy` **即最终缩放**），**绝不可混用**。

## 2. 路线 A：经典 reanim → 重置版直转

入口脚本：`.cache/build_official_skin.py`
（reanim → `.dat` / `.tres` / 图集 / `skin_params.json`，**自检含 on-disk 断言 + 负向测试**）
⇒ 再由 `build_plant_<名>.py::sync_skin_assets()` 按 `skin_params.json` 生成 Sprite/Scene。

实测：超级机枪射手 **27 轨 × 87 帧**直转成功，`.dat` 344 KB / 1168 slice，两份构建闸门 52/0。

### 2.1 识别源

* 经典（未重置版）= `reanim` / `*.reanim.compiled` / `images/*.png`；
  重置版（Godot 4 + C#）= `*.tres` / `*.dat` / 图集 PNG / `*.tscn`。
* 常见落点：`<解包根>\compiled\new\<角色>.reanim.compiled`、`<解包根>\reanim\IMAGE_REANIM_*.png`。
* ⇒ **先确认目标角色在未重置版里真有 reanim**；只有 PNG 没有 reanim ⇒ 退回自制路线。

### 2.2 `.reanim.compiled` 二进制格式（已对拍验证）

```text
外壳: d4feadde + u32(解压后长度) + zlib
内层头 28 B: magic c0b493b3 | u32@4 | u32@8=轨道数 | f32@0xC=fps | u32@0x10 | u32@0x14
轨道表 @0x1C: 轨道数 × 3×u32   ← 帧数 = 条目第 2 个 u32
逐轨道: 名字(ASCII, 以 ',' 结尾) + 3 字节 + 帧数据[帧数 × 44B] + 尾部(图片名表)
帧记录 44 B = 11 个 f32: x, y, kx, ky, sx, sy, f, a, ?, ?, ?
未设置字段 = 哨兵 -10000.0f（SENT）
```

⚠️ **末轨的图片名表必须自己补扫**：通用解码器靠「正则找下一个轨道名」给尾部定界，
**末轨没有下一轨** ⇒ 尾部为空 ⇒ 那张图悄悄丢失（实测丢了 `overlay2`）。
修法 = 末轨从 `data_off + 帧数*44` **扫到文件尾**再正则 `IMAGE_[A-Z0-9_]+`。
**必须加断言**：末轨那张图名确实出现在最终媒体表里。

### 2.3 映射规则（12 条，照抄即可；每条都有内置反证）

1. **轨道 → 图层 1:1，全部轨道都保留**（`layerId == 轨道序号`）。
   依据：内置 11 个「头身分离」植物里 10 个把无图控制轨（`anim_stem`/`anim_idle`/`_guide…`）**原样保留成空层**。
   ⚠️ 唯一例外 `GatlingPeaZ` 丢了开头两条并重排 —— 那是**早期转换**，别当范本。
2. **帧 → 帧 1:1**（`frameMax` = 经典帧数）。
3. **变换 = 旋转矩阵**（不是斜切）：
   `[Xx, Xy, Yx, Yy, Ox, Oy] = [sx·cos(kx°), sx·sin(kx°), −sy·sin(ky°), sy·cos(ky°), x, y]`
4. ★ **不要乘任何额外缩放**：经典 `sx/sy` **就是最终渲染缩放**。
   ⚠️ 这条推翻了「素材放大 2 倍 ⇒ `DISPLAY_SCALE=0.5`」的口径 —— **那个 0.5 只适用于自制素材**。混用会把角色缩错一倍。
5. **`SENT(-10000)` = 沿上一帧继承**（编译器按「与上帧相同」去重）。
   首帧未定义取默认 `x=y=kx=ky=0, sx=sy=1, f=0`。
6. **第 7 个 f32（`f`）是「选图/隐身」开关**：`f < 0` ⇒ 该 (层,帧) **不产 slice**；
   `f >= 0` ⇒ 索引**该轨自己的 `imgnames`**。
7. **无图控制轨的可见帧要产 `locator.png`（2×2 全透明）占位 slice** —— 这是内置做法
   （`PeaShooter.anim_stem` 25 帧全用 locator）。好处：保住 `sliceDrawOrders == sliceLayerIds`。
8. **clip 边界直接读控制轨的 `f` marker**：本例 `BodyIdle(0,24) / HeadIdle(25,49) / HeadFire(50,86)`。
   命名对齐内置惯例（`BodyIdle`/`HeadIdle`/`HeadFire` 是头身分离植物标准三 clip，共 11 例）。
   ★ 注意把「射击段 **+ 大招段**」都合进 `HeadFire` —— `FireComponent` 循环播 `HeadFire`，
   只给射击段就**看不到大招**。
9. **一张 `.dat` 只能内嵌一张图集** ⇒ 所有 media 打进同一张；
   `mediaRect` = 每张 PNG 的**完整矩形**（**不切帧**）。
   * `media id` = **显示名按大小写不敏感排序**后的序号（内置四例核对通过：`locator.png` 在 `PeaShooter` 是 0、在 `GatlingPea` 是 7，**只有忽略大小写才排得出来**）。
   * `.tres` 文本里的字典键序 = Godot 的 **ASCII 序**（两者不同，各按各的写）。
   * 显示名换写法：`IMAGE_REANIM_<PREFIX>_<REST>` → `<Prefix>_<rest 小写>.png`（如 `SUPERGATLING_` → `SuperGatlingPea_`）。
10. **根锚点**：内置植物一律 `offset = (−40,−40)` ⇒ 经典 `(40,40)` 就是「种植锚点」。
    先拿同族内置角色核对落地线（本例 `SuperGatling` 与 `GatlingPeaZ` 同为 `y=77.7`）再沿用。
11. **头身同源 ⇒ 零偏移对齐**：Head 的 `offset` 与根**默认完全相同**（本 Mod 两边都 `(−40,−40)`）。
    `Head.position` 写 `(0,0)` 占位即可 —— 它**不是**真旋钮：`AdobeAnimateSprite.UpdateChild()`
    （`:5259-5281`，`usePos`/`useRotate` 默认 `true`）每帧把它改写为「被跟随图层 pose.Origin + 父 offset」。
    ⚠️ 内置 `GatlingPea`/`PeaShooter` 的 `offset=(−36,−46)`、官方 `ZombieNormalGatlingPea` 的
    `Head.offset=(−58,−5)`/`offsetRotate=−0.25` 都是**为它们自己的头素材手工标定**的，**不能照抄**。
12. **插层位置** `insertLayerId = max(body 图层 id) + 1`
    （内置 11 例全部成立：`PeaShooter`/`GatlingPea`=8、`ReCactus`=11、`SunflowerPea`=5）。
    ⚠️ **body 判据 = 该层在 body 段内有可见帧「且用的是真实贴图」**；
    **必须排除「只用 locator 占位」的无图控制轨**（`PeaShooter.anim_stem(8)` 在 0..24 有 25 枚 locator slice，
    但 `insertLayerId` 仍是 8；把它算进 body 就会误得 9/17）。

### 2.4 标定三件套（经典坐标 → 重置版节点）

```text
根 offset   = Head offset = −ANCHOR_ROOT        （内置植物 ANCHOR_ROOT = (40, 40)）
Head.position = (0, 0)                          （**死值/占位**；要调头位改下面的 Head.offset）
Marker2D    = 炮口(经典坐标) − ANCHOR_ROOT      （写在 Head 子节点下，local 坐标；与 offset 无关）
```

* 炮口求法：取「炮管完全伸出」那一帧的不透明区最右列中点（`x,y` 经旋转矩阵变换后）。
* ⚠️ 传统「换成像素在画布内的几何中心」求 `origin` 那套**在官方素材下不需要** ——
  直接照抄经典 `x,y` 与 `sx,sy` 就对了（见规则 3、4）。
* ★ **头位微调 = 改 `Head.offset`（不是 `Head.position`）**（2026-09-22 更正，旧说法反了）：
  `AdobeAnimateSprite.UpdateChild()`（`:5259-5281`，`usePos`/`useRotate` 默认 `true`）每帧重写子精灵
  `Position`/`Rotation` ⇒ 场景里写的 `Head.position` 是**死值**；而 `offset` 只作用于**本精灵自己那份美术**
  （`:7044`/`:7071`/`:7362` `transform.Translated(offset)`），**不影响**作为 Head 子节点的 `Marker2D`（炮口）。
  ⇒ 头身同源时两层 `offset` **默认相同**（= `−ANCHOR_ROOT`，就是上面的零偏移对齐）；
  **要单独抬高/压低头，就在 Head 上把 `offset.y` 往负/正调** —— 这正是官方 `GatlingPea`/`ZombieNormalGatlingPea`
  的 `(-36,-46)` / `(-58,-5)` 那种手工标定值。⚠️ **跨素材拼装（僵尸身 + 植物头）必须重标定**，
  用 `.cache/check_head_fit.py` 反解（引擎变换模型 + 官方样本交叉校验 + 负向测试），别照抄。

### 2.5 生成器与场景要一起改（否则重跑即回退）

让 `sprite_scene_tscn()` **由标定结果文件（如 `skin_params.json`）驱动**：

* `Animation/LayerVisible/<每个图层名> = true` —— 覆盖**全部**图层（含无图控制轨）
  \+ `AnimeClips` / `AnimeEvents` 两张内建表；
* `Animation/MediaReplace/<每个媒体名> = null` —— 覆盖**全部**媒体（含 `locator.png`）；
* Head 节点：`Layer`、`insertLayerId`、`followParentSpriteLayerId` **三者同值**，
  `parentSprite = NodePath("..")`、`position = (0,0)`、`offset` 与根相同。

`self_check()` 加**反向断言**：拒绝旧自制值（例 `(−69.25,−174.0)` / `(87.75,−111.25)` / `(31.74,−17.82)`）。

⚠️ **`main()` 的顺序**：**先写盘、再自检**，并把「生成器升级导致磁盘内容漂移」报为 **info 而非 FAIL**；
否则「换生成器后第一次跑」必然假红（磁盘还是上一版）。

### 2.6 验证器：四层独立 + 负向测试（**必配**）

**四层必须互相独立、只读磁盘产物、且不复用生成器代码**，否则就是「比内存文本」的假绿：

| 层 | 内容 | 关键判据 |
|---|---|---|
| ① 源 ↔ `.dat` | 独立再解码 reanim，对**全部 (层,帧)** 重算 carry-forward + f 选图 + 旋转矩阵 | mediaId 与 6 个 f32 **逐位**一致；媒体名集合/id 序反推；`mediaRect` vs 源 PNG 真尺寸 |
| ② `.dat` | 自写解析器按引擎规格走完全文 | ★ **解析终点 == 文件总长**；★ **像素区逐字节 == 图集 PNG 真解码像素** |
| ③ `.tres` | 抽 `Packed*Array` 与 `.dat` 互证 | `sliceTransforms` **f32 位级**一致；`sliceKeys=(layerId<<16)\|槽序号`；`sliceDrawOrders==sliceLayerIds` |
| ④ 场景 | Sprite + 主场景 | offset / `insertLayerId` / clip / `Marker2D` / 图层媒体名单 / 相对路径 + **旧值反例** |
| ⑤ 不变量 | 结构性 | 图层**不跨** body/head 边界；`insertLayerId == max(body 真实贴图层)+1`；标定文件全量一致 |

* ★ **写自己的 PNG 解码**（zlib + 5 种 filter + 调色板/tRNS）才算真独立；
  **官方 PNG 常是调色板类型 `ct=3`**，只支持 RGB/RGBA 会直接 `AssertionError`。
* ★ **负向测试必须做**（`--negative`）：故意写坏**副本**（图集改 1 bit / 场景 offset 改旧错值 /
  `.tres` frameMax 改错 / `.dat` 事件段截断），断言**必须报错**。
  不报错 = 断言失效（假绿）。实测 **5/5 报错**。
* ⚠️ 换官方素材后，**旧管线验证器要退役**：它们硬编码 `frameMax=1`（单帧）/ 2 media / 176×192 画布，
  对多帧官方素材只会**报误导性 FAIL**。做法 = 统一在文件头插 **LEGACY GUARD**
  （读 `.dat` 的 `frameMax`，`!= 1` 时打印 `[SKIP]` 并 `rc=0` 退出），或改名为 `legacy_*`。

### 2.7 路线 A 专属陷阱（都在实测中踩到）

1. ⚠️ **末轨图片名表**（见 2.2）—— 会静默丢图，必须补扫 + 断言。
2. ⚠️ **`.tres` 的浮点格式化会把 `-0.0` 写成 `0`** ⇒ 位级比对必须把 **`±0.0` 视为等值**
   （`−sy·sin(0°)` 天然产生 `−0.0`；不处理则上千个浮点里必出假红）。
3. ⚠️ **`layerDictionary` 除图层名外还含 `AnimeClips` / `AnimeEvents` 两张内建表**
   （值 = 图层数 / 图层数+1）⇒ 断言「字典 == 图层序」会假红。
4. ⚠️ **`LayerVisible` / `MediaReplace` 在根与 Head 两块节点里各写一份** ⇒ 正则统计会翻倍，需**去重**。
5. ⚠️ **资源路径断言别用 `path="…"` 裸正则** —— 会误捕 `NodePath("…")` / `node_paths=PackedStringArray(...)`；
   限定 `^\[ext_resource[^\]]*?path="([^"]+)"` 并按行匹配。
6. ⚠️ 末轨 / 相对路径段数（Sprite 场景在 5 段目录 ⇒ 5 个 `../`）—— 数错 = 静默不画。

## 3. 路线 B：自制单帧 / 逐帧（只用真拿不到 reanim 时）

管线：`build_atlas2.py`（缩放常量在这）→ `build_dat.py` → `build_tres.py`，
**必须按序全跑**（只重跑后者 = `.dat` 与 `.tres` 的 `scale` 不一致的隐性故障）。

### ★★ 头号坑：`scale` 是「显示缩放」，写 1.0 会让角色大 2.5~3 倍

素材常按**放大 2 倍**制作（角色实际占 144×170，塞进 176×192 画布） ⇒ **必须乘 0.5**。

三条独立判据（缺一个都别再猜）：

| 判据 | 怎么读 | 实测 |
|---|---|---|
| 交付基准图 | 素材目录里的 `_source_cutout_1x.png`（或 `_frames.json` 的 `scaleFromSource`，**倒数**即 scale） | `72×85`；`scaleFromSource=2` |
| **内置 `.tres`** | `sliceTransforms` 每 6 个 float 取第 0 个 = `scale` | `GatlingPea` 842 条 = **0.4118 ~ 1.0** |
| 素材 bbox | 抠像后字符实际占的像素范围 | 144 × 170（画布 176×192） |

```python
# 逐 slice 精确算内置渲染尺寸（别用「最大 rect × 最大 scale」近似，会偏大）
scales = [st[i] for i in range(0, len(st), 6)]
mx = max(max(rects[m][2] * scales[k], rects[m][3] * scales[k])
         for k, m in enumerate(media_ids))
```

⚠️⚠️ **`origin` 的语义 = 「该层内容 bbox 几何中心，在完整素材画布上量 × `DISPLAY_SCALE`」
（跨层公共画布坐标，不是层内局部坐标）。**

```text
AdobeAnimateData.cs:1484-1489  写入 list9.Add(transform.X.X)…(transform.Origin.Y)   ← 直通，无缩放
AdobeAnimateData.cs:2820       读出 new Transform2D(…, Origin.X, Origin.Y)          ← 直通，无缩放
AdobeAnimateDrawItemBuilder.cs:1079 BuildSliceTransform ← 唯一一次作用：
    Transform2D(new Vector2(slice.Xx*sourceSize.X, slice.Xy*sourceSize.X),   // X 基向量 = scale × 帧宽
                new Vector2(slice.Yx*sourceSize.Y, slice.Yy*sourceSize.Y),   // Y 基向量 = scale × 帧高
                new Vector2(slice.Ox + offset.X, slice.Oy + offset.Y));      // origin 直接相加
    return parent * transform2D;
```

⇒ **`origin` 必须同比乘 `DISPLAY_SCALE`**（只缩 `scale` 不缩 `origin` ⇒ 角色**偏离约 2 倍距离**）。

**`scale` 存两份 ⇒ 改必须全跑**：

| 位置 | 写入者 | 布局 |
|---|---|---|
| `.dat` layer 表 | `build_dat.py` | 每元素 30 B：`u16 mediaId` + `f32 xx,xy,yx,yy`（无旋转 ⇒ `xx=yy=scale`、`xy=yx=0`）+ `f32 originX,originY` + `u32 RGBA` |
| `.tres` `sliceTransforms` | `build_tres.py` | 每 slice 6 float：`sc,0,0,sc,ox,oy` |

★★★ **「谁乘了 0.5」必须分清（极易二次乘）**：

| 常量 | 来源 | 标定块里怎么用 |
|---|---|---|
| `BODY_ORIGIN` / `HEAD_ORIGIN` | `author2.json` 的 `ox/oy` | **不要再乘** |
| `ANCHOR_ROOT` / `ANCHOR_MUZZLE` | **素材画布原生坐标**（如 352×384） | **显式 ÷2** |

★ **自洽信号**：全量 ×0.5 后 `Marker2D` 应恰为旧值**精确一半**（实测 `(72,-104) → (36,-52)`，整数）。

⚠️⚠️ **校验脚本必须显式断言 `scale`** —— 本项目的坑正是**只查了结构与「origin 落在画布内」，
从没断言过 `scale`**，所以「角色大 2.5~3 倍」一路绿灯到用户眼前：

```python
assert sorted({round(s, 6) for s in scales}) == [0.5]        # scale 全 == 期望值，不是 1.0
# ⚠️ origin 的越界判据要跟着素材换 —— 硬编码 90 在单帧素材下会假红
RENDER_CANVAS_W, RENDER_CANVAS_H = 176, 192                  # 渲染空间 = 素材画布 × DISPLAY_SCALE
assert max(oxs) <= RENDER_CANVAS_W and max(oys) <= RENDER_CANVAS_H
```

> 路线 B 还有 ②–④ 号坑（`animeFile` 相对路径层级、`offset`/`Marker2D` 标定、
> 抠像底图若是软泥/苔藓纹理时色相法必失败、部件分层动画法、交付自检口径）。
> 需要时读 `pvz-hybrid-mod-authoring` 的 §「自制 `.dat` 的五个必踩坑」与
> §「从单张参考图制作角色贴图」。

## 4. 换完外观必查的五件事（清单）

1. **`.dat`/`.tres` 的 `events` 表必须有 `{"Command":"fire","Argument":""}`**
   （换精灵不会自动带上它；没有 ⇒「只有动画、没有子弹」）。
2. **`Marker2D`（出膛点）位置必须重调**；`firePosMarkerPaths` 必须指向真 `Marker2D`
   （`FireComponent.cs:1254` 带类型过滤，指向 `HeadSlot` 会拿到 null、子弹从原点出膛）。
3. **改过 `Head.offset`（不是 `position`）后，重新核对头身接缝 + 炮口位置**
   （`offset` 不影响炮口，但要确认头没被推歪；跨素材拼装用 `.cache/check_head_fit.py` 反解）。
4. ★★★ **换头（子精灵换成另一份 `.tres` / 自制皮肤）之前，必须先把场景改成「三节点」**
   —— 否则头会画成**一团别的角色的图集碎片**。原因与完整修法见 `SKILL.md` §4 坑 14：
   头是**父精灵的直接子精灵**时，引擎走「**父代画**」⇒ 头自己的 `forceLocalRender` / `forceCpuPoseRender`
   **永远读不到**（`_Draw():9534` 首行 return），切片由父精灵批次代画 ⇒ 采样父那一张图集。
   * **本植物包现在没事，只是因为 `root` 与 `Head` 共用同一份 `.tres`**（同 definition ⇒ 同
     `MediaAtlasPages`）—— **这是巧合，不是安全**。
   * 形状：`<Root>` 下留 `HeadShadow`（身体的直接子精灵，`visible=false` + 全层 false ⇒ 零切片，
     只吃 `UpdateChild()` 定位） + `HeadHolder`（普通 `Node2D`，identity） +
     `HeadHolder/Head`（独立渲染；不写 `parentSprite`/`insertLayerId`/`followParentSpriteLayerId`/
     `position`/`rotation`/`visible`）。两头 `scale`/`offset`/`offsetRotate` **逐字相同**；
     位姿由插件每帧从影子同步（`process_frame` 早于节点 `_process` ⇒ 1 帧延迟，低速下 < 1px）。
   * ⚠️ `insertLayerId = -1` **躲不掉**（`ResolveSpriteChildInsertLayer:8039` 回落顶层）；
     挂到普通 `Node2D` 容器下**也躲不掉**（判定时穿过容器，`:5397`）。
   * 参考实现：`build_zombie_super_gatling_paper.py::sprite_scene_tscn()`（僵尸侧已落地）。
5. ⚠️ **`.tscn` 节点头收尾必须是 `]`**（写成 `>` ⇒ Godot **静默吞行**，节点不建、零日志）。
   生成器自检要加一条**通用扫描**：
   `if ln.startswith("[node ") and not ln.endswith("]"): fail`。
   ⚠️ 别把断言写成不带闭合括号的前缀匹配（`… parent="HeadHolder"`）—— 那是**断言与实现同错**的假绿。
   取证时**以字节级读取为准**（`Read` 预览曾把 `>` 显示成 `]`）。
