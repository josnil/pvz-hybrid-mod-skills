# 换外观第二路：**内置 `.tres` 切片数据 + 经典版原画**重建

> 2026-09-30 实测落地：**超级汉堡射手**改用官方素材（`BurgerSkin/build_skin_official.py`）。
> 适用场景：**想要官方画质与真动画，但 reanim 路线走不通**（解不出、或角色在经典版没有 reanim）。

## 0. 什么时候走这条路

| 手里有什么 | 走哪条 |
|---|---|
| 有该角色的 `*.reanim.compiled` + `reanim/*.png` **且解码器能完整解出** | 主 SKILL 的「官方素材直转」（reanim → dat） |
| **有该角色的官方原画 PNG，但 reanim 解码失败 / 角色只在内置 `.tres` 里有动画** | **本文** |
| 只有一张截图 | `selfmade-skin-from-screenshot.md`（画质天花板低，仅兜底） |

★ 关键判据：**内置 `.tres` 里已经有逐帧的 `(layer, media, scale, ox, oy, alpha)`** ——
  它就是一份「带时间轴的拼装说明书」。只要能把 `mediaDictionary` 里的**媒体名**
  对应到磁盘上的原画 PNG，就能离线把任意一帧**逐位复刻**出来。

## 1. 素材对得上吗？先做这一步

内置 `.tres` 的 `mediaDictionary` 值形如 `hamburger_0001_11.png`、`SuperGatlingPea_helmet.png`，
而经典版 `reanim/` 里的原画文件名**常常就是同一个名字**（本项目的汉堡射手 11/11 全对上）。

```python
# 逐媒体核对
for i, name in sorted(inv_media.items()):
    ok = os.path.isfile(os.path.join(CLASSIC, "reanim", name))
```

⚠️ **对不上的媒体要成对处理**：既不能留（会变成空白切片），也不能只删 slice 不删 media
（`mediaRects` 与 `sliceMediaIds` 会错位）。做法 = **整层丢弃**（见 §3），
然后 **`mediaId` 重映射**（本项目丢掉的正好是排在最后的皮肤层，0..10 保持不变，纯属运气好；
一般情况下必须自己重排）。

## 2. 离屏合帧：验证 + 出预览（也是最终 .dat 的底座）

```python
# Transform2D: output = origin + u*X轴 + v*Y轴,  X轴=(sc,xy)*w,  Y轴=(yx,yy)*h,  (u,v)∈[0,1]²
Xx, Xy = sc * w, xy * w
Yx, Yy = yx * h, yy * h
det = Xx*Yy - Yx*Xy
i00,i01 =  Yy/det, -Yx/det          # A⁻¹
i10,i11 = -Xy/det,  Xx/det
tx, ty = ox - off_x, oy - off_y
PIL_Image.AFFINE = (i00*w, i01*w, -(i00*tx+i01*ty)*w,
                    i10*h, i11*h, -(i10*tx+i11*ty)*h)
```

★★ **PIL 的 `AFFINE` 系数把「输出**像素**」映到「输入**像素**」**，而 Transform2D 的 `(u,v)`
是 `[0,1]²` **归一化**坐标 ⇒ **必须先求 `A⁻¹` 再乘 `(w,h)`**。
漏了这一步，采样区域几乎全落在图像之外 ⇒**整帧透明、看上去像"什么都没贴上去"**（本项目实测踩过，
排查了一轮才定位）。

* 画布 = 全动画所有 slice 四角并集 bbox，绘制时整体平移 `-bbox.min`。
* 一排 10 个代表帧的对照图 = 最快的「素材对不对」判据（本项目用它一眼确认了 11 个部件与动画节奏）。

## 3. 为什么这次是**单精灵**（不是头身双精灵）

判据：**按 y 切一刀会不会把角色切成两半**。

* 汉堡射手 = 11 个部件摞成的一整摞汉堡（底面包→酱汁→生菜→瓜皮圈→西瓜→豌豆头→炮口→蓝莓
  →叶子→黄油→顶面包）⇒ 切了必然头身分离 ⇒ **单精灵 + 角色自己的两个 clip**。
* 豌豆家族（茎叶在下、头在上，中间有"脖子"）⇒ 双精灵头身分离才划算。

**单精灵的配套改动**（照抄内置该角色的 `ComponentSet` / 场景）：

| 项 | 值 |
|---|---|
| 精灵场景 | 只有一个 `Node2D`，`clip = "Idle"`（角色自己的 clip 名），无 `Head` 子精灵 |
| `FireDefinition.spritePath` | 指向**精灵本身** |
| `fireAnimeClips` | 角色自己的开火 clip 名（本项目 `"Fire"`） |
| `isSpliceSprite` / `spliceIdleAnimeClips` | **不写**（内置该角色也没有） |
| 插件侧 | 不用改：`TryLinkHead` 找不到名为 `Head` 的节点会**静默跳过** |

## 4. 皮肤层：**整层丢弃**而不是留空

内置场景里 `Animation/LayerVisible/<皮肤层> = false` 的层（本项目 12 个 `skin*`）：
它们**本来就不显示**，而且原画常**不在解包树里**（本项目 15 张 `hamburger_skin*` 全缺）。
⇒ 造 .dat/.tres 时把这些层的 slice 与 media **一起删掉**，并在自检里断言
`for sk in SKIN_LAYERS: assert sk not in tres_text`。

## 5. 标定：**沿用内置，不要自己推**

* `offset`：直接抄内置 `<角色>.tscn` 的 `offset`（本项目 `(-40,-40)`，与经典豌豆家族同坐标系）
  ⇒ 落位与内置逐像素一致，不用重标定。
* **出膛点**：内置用 `AdobeAnimateSlot`（`followSlotId` 跟着某一层走）⇒ 别去解槽位；
  直接从数据反解：**取「炮管/炮口那一层的 media」在「伸出最远」那一帧的最右点**，
  再 − `ANCHOR_ROOT` 得到节点空间坐标。
  ⚠️ 该点**可能落在本格之外**（本项目 x = 60.37，本格 ±40）—— **这是忠实的**：
  炮管伸出时出膛点就在那里。生成器里那条「炮口必须落在 ±40 内」的断言要**按素材改**，
  别硬套上一个角色的口径。

## 6. 变体：**有 reanim 但想用单精灵** ⇒ 帧重映射

实测案例（超级汉堡射手 / `SuperGatlingB.reanim.compiled`）：
reanim 里身体层只在 `anim_idle(4..28)` 有 slice、头层只在 `anim_head_idle(29..53)` 与
`anim_shooting(54..78)` 有 slice。若按传统双精灵做，就要面对
`Head` 作为父的直接子精灵时 `Position` 被每帧覆写成 `被跟随层 pose.Origin + 父 offset`
（要求 `head_offset = −(被跟随层 origin)`，而 origin 逐帧变化、要手工反解 + 容忍漂移）。

⇒ **把两段烘焙进同一条时间轴**，只用一个精灵：

```
out 0..24  = 身体层(src 4+i)  + 头层(src 29+i)    → clip "Idle"
out 25..49 = 身体层(src 4+i)  + 头层(src 54+i)    → clip "Fire"
```

* 段长必须相等（脚本里断言；不等长就不能这样映射）。
* 断言「**任何图层都不跨身体/头部边界**」—— 这是本方案成立的前提。
* ★★★ **身体段必须「循环」取，不能线性取**（2026-09-30 实机反馈踩过）：
  ```python
  s_body = B0 + k          # ✗ k ≥ 段长 时越界到身体层不可见的区间
  s_body = B0 + (k % LEN)  # ✓ 在身体段内循环
  ```
  本项目实测：线性取会让 **out 25..49（整段开火动画）的叶/茎图层数 = 0**
  —— 实机表现就是「开火时底部叶子消失」。
  循环点天然连续（out 24 取 src 28、out 25 取 src 4，而 4..28 恰是一整圈）⇒ 接缝无跳变。
  这正是内置结构的行为：内置是「**根精灵循环播 BodyIdle**」，本方案把那段烘进时间轴。
* ★★ **两道机械防线**（光靠肉眼看预览不够）：
  1. 生成侧：`body_names - per_frame_layers[j]` 非空即**抛错、不写盘**；
  2. 自检侧：**逐帧**断言每帧都含**全部**身体图层，单独统计叶/茎并断言其条数 ≥ 期望值
     （防"叶子部件本身没进媒体表"这种另一类失败）。
* 无图控制轨（`anim_idle` / `anim_shooting` / `anim_power` / `overlay2`…）**整条丢弃**：
  它们的可见性已通过每帧的 `f` 字段烘进数据，保留只会多出 2×2 全透明占位切片。
  ⚠️ **但先确认它真的是"无图"** —— 二进制 reanim 的**末轨** trailer 会因定界窗口丢图，
  让一个**有图**的层看起来像控制轨（本项目 `overlay2` 就踩过）。
* clip 名沿用角色自己的（本例 `Idle` / `Fire`），并同步改
  `ComponentSet.fireAnimeClips` / 场景 `clip` / 卡片 `packetAnimeClip`。

### 6.1 更优的数据源：**Anim 导出（`anim.json` + `texture.json` + `texture.png`）**

如果手上是 Adobe Animate 的导出（三个文件：动画 JSON / 图集清单 JSON / 图集 PNG），
**优先用它而不是二进制 reanim**：

* `anim.json` 的 `document.tracks[i].transforms[j]` **每帧直接给 `image` 名** ⇒
  不需要解析二进制、也没有上面那个「末轨 trailer」坑；字段是稀疏的（缺省 = 继承上一帧），
  可见性判据 = `f >= 0`；
* `texture.json` 的 `items` 直接给每个部件的 `x/y/w/h` ⇒ 从 `texture.png` 裁即可，
  不用去解包树里逐个找散图；
* 实测：同一角色，二进制路线 22 张、导出路线 **23 张**（多出来的正是一个被误判成控制轨的部件）；
  两边同名部件的矩形尺寸**逐个一致**（可作交叉校验）。


## 7. 顺带：`packetAnimeScale` 忘了写 ⇒ 卡片与图鉴「没有图」

**症状**：选卡界面 / 图鉴里条目存在，但**没有图像**（不是缺资源）。

**根因**：`TowerDefensePacketConfig.packetAnimeOffset` / `packetAnimeScale` 的类默认值是
`Vector2.Zero`；卡片显示与图鉴植物页共用
`TowerDefenseInGamePacketShow.UpdateSpriteLayout()` → `sprite.Scale = config.packetAnimeScale`
⇒ **缩放 0 = 缩成一个点**。内置每张卡都显式写了：

```
packetAnimeClip = "Idle"          # 类默认就是 Idle
packetAnimeOffset = Vector2(21, 23)
packetAnimeScale = Vector2(0.5, 0.5)
```

**取值法**（与同族内置卡比）：
1. 量两边的「经典画布并集」bbox 与中心；
2. `scale = 内置卡 scale × (内置画布高 / 我方画布高)`；
3. `offset = 内置卡的卡面中心点 − (我方中心 − 锚点) × scale`
   （内置 GatlingPea 的卡面中心点 = `offset + (center − anchor) × scale`）。

自检要断言**数值非零**（只断言字段存在拦不住 `Vector2(0,0)`）。

## 8. 附带发现：`reanim_decode.py` 的尾巴定界窗口太小

`reanim_decode.decode()` 用「找下一个 `[ -~]+?,`」给每条轨道的 trailer 定界，
窗口写死 **4096 字节**。`SaleBurger.reanim.compiled` 的某条轨道 trailer 长达 **13192 字节**
⇒ 找不到 → 判定 trailer 为 0 → **后续轨道全部错位**（报 `{'error': 'name@14872'}`）。

* 症状：`load_tracks()` 抛 `reanim 解析失败：{'error': 'name@N'}`。
* 定位手法：把内层 raw 解出来，按 `0x1C + 12*ntracks` 起逐轨走，
  在失败处 dump 十六进制 —— 这次一眼看到 `1e 00 00 00 "IMAGE_REANIM_..."`（长度前缀字符串），
  说明 `fend` 其实是对的，是**窗口**没扫到下一轨的名字。
* 现成绕法 = **改走本文这条路**（用内置 `.tres`，完全不需要解 reanim）。
  修解码器的话：把窗口放大到 64 KB，或改成「按长度前缀解析 trailer」。
