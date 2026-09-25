# GatlingPea.tres = 自描述格式（重大更正）

## 纠正旧笔记
- 旧笔记说 .tres 是「运行时模式，只存 animeFile+frameRate+frameMax+mediaRects+字典+clips」= **错**。
- 实际：.tres 是 **完整自描述**，含 sliceKeys / sliceTransforms / sliceLayerIds / sliceDrawOrders / sliceFlags / sliceAlpha / frameOffsets / frameCounts / events。
- animeFile 指向的 GatlingPea.dat **在解包树里不存在**（全工程 .dat 仅 icudt_godot.dat）。⇒ .dat 已被烘焙，.tres 内的 authored 数据是权威。

## 顶层键（19 个）
script, animeFile, frameRate, frameMax, frameOffsets, frameCounts, sliceKeys, sliceMediaIds,
sliceLayerIds, sliceDrawOrders, sliceFlags, sliceTransforms, sliceAlpha, mediaRects, events,
clips, mediaDictionary, layerDictionary, rasterCompositeData

## 实测规模（GatlingPea）
- frameRate=12.0, frameMax=89
- frameOffsets/frameCounts 各 89 项
- sliceKeys/sliceLayerIds/sliceMediaIds/sliceDrawOrders/sliceFlags/sliceAlpha 各 842 项
- sliceTransforms 5052 项 = 842 x 6
- mediaRects 68 项 = 17 rect
- layerDictionary 21 项, mediaDictionary 17 项
- events 89 项；非空的在第 62/68/74/80 帧，Command="fire"（★ HeadFire=50..88，即第 4 帧起每 6 帧一发，共 4 发）
- clips = { BodyIdle:(0,24), HeadIdle:(25,49), HeadFire:(50,88) }

## sliceKeys 编码（已实证）
sliceKeys[i] = (layerId << 16) | mediaId
frame0 实测：0,65536,131072,... 对应 layer 0..9 + mediaId 0..9

## mediaRects 字段顺序 = (X, Y, W, H) ★ 已定论
证据（用 mediaDictionary 的 idx->名 反查）：
- idx4 HELMET = (0, 0, 82, 87)：头盔竖长 82x87 ✓（若按 (Y,X,W,H) 读成 0x0 无意义）
- idx3 HEAD   = (82, 0, 70, 65)：紧贴头盔右侧同一行 y=0 ✓
- idx7 locator= (155, 125, 2, 2)：2x2 点，★ 旧笔记「125 宽细横条」判据是错的
- idx0 barrel = (201, 22, 43, 27)
- 图集尺寸 = 283 x 137（max(x+w)=283, max(y+h)=137）
⇒ 旧笔记假设 A/B 都作废，正确答案是 (X,Y,W,H)。

## sliceTransforms 的 6 个数 = (xx, xy, yx, yy, ox, oy)
实测 GatlingPea：xx=yy=0.55540466, xy=yx=0 ⇒ **纯缩放+平移，无旋转**。
- 0.55540466 = 缩放系数（源素材被缩小到 0.555）
- 部分 slice scale=1（如 layer 8/9）
★ 与 Addons 里 BuildSliceTransform 的「按源矩形归一化」不同：
  这里 authored 值直接就是显示缩放，**不需要再乘源宽高**。

## origin 语义 = 中心 ★ 已定论
用 frame0 交叉验证（scale=0.5554）：
- 按「左上」读：各部散在 x[19,76] y[45,94]，无重叠、跑出画布
- 按「中心」读：全部聚在 x[8,56] y[21,70]，形成约 48x49 的完整角色
⇒ origin = **该 slice 显示后的中心点**（画布像素坐标）。
   左上 = origin - (w*scale/2, h*scale/2)

## 画布/缩放推算（对自制 .dat 很重要）
- 内置 sprite 场景 offset = Vector2(-40,-40)，Head 子节点 offset = Vector2(-36,-46)，Head.position=(3.6,3.62)
- 角色本体在画布内约 48x49 单位
⇒ 若要 1:1 呈现用户 176x192 素材，令 scale = 176/画布宽。
   具体画布宽待定（建议画布 = 176x192 原尺寸，scale=1，origin 直接就是像素中心）。


---

# 第二波取证：运行时到底走哪条路（结论：必须写 .dat）

## 决定性证据链
1.  (AdobeAnimateData.cs:1139-1148)
   = 只检查 sliceKeys/frameOffsets/frameCounts/sliceMediaIds/sliceLayerIds/
     sliceDrawOrders/sliceFlags/sliceTransforms(len==n*6)/sliceAlpha(len==n)
     的**数组自洽性**，与 .dat 无关。
   ⇒ .tres 里若有完整 packed 数组， 直接 return true，
     **根本不会去碰 .dat**。（这是我一度以为「不用写 .dat」的理由。）

2. ★ 但图集纹理另有出处（这是真正的闸门）：
    (:3102-3131)
     - 先查 manifest 分配
     - 失败则  (:3191)

3.  (:3191-3250) 第一条件（:3194）：
     
    (:1682-1709) **直接从 .dat 读**：
     先 ，再读 float/16/16/16/64 头
     +  解出**内嵌像素区**。
   ⇒ **没有真 .dat ⇒ 没有图集 ⇒ WarnProjectAtlasUnavailable ⇒ 什么都不画。**

4. ★★ 且  只建**一张**图（:3211 ），
    、、
    （**全 0** ⇒ 所有 media 都在第 0 页）。
   ⇒ **一个 .dat 只能承载一张图集**，head + body 必须拼到**同一张**图里。

## 因此最终路线（已锁定）
写一个真 .dat，内含：
  - 头部 float frameRate（12.0）
  - u16 frameMax（50）
  - u16 atlasW / atlasH（= 合并后图集尺寸）
  - i64 pixelByteCount + **内嵌 RGBA8 像素区**（head 与 body 拼在同一张图）
  - u16 mediaCount + 每项 Pascal 名 + 4×float rect   ← rect 顺序 = (X,Y,W,H)（本图集自己的坐标）
  - u16 layerCount + 每层名 + frameMax×(u16 元素数 + 元素×30B)
  - u16 clipCount + 每项 Pascal 名 + u16 start + u16 end
  - u16 eventFrameCount + 每项 (u16 frame + u16 事件数 + 事件×2 Pascal)
  ⇒ 注意 runtime 侧用字节数：元素 = 2 + 4*4 + 4*2 + 4 = 30 字节（与 :1071 的  一致）
  ⇒  = Godot 内置 = **int32 长度前缀 + UTF8**（不是 u8）。须实测确认。

## mediaRects 与 .tres 的关系
 (:1711-1723) 优先读 （.tres 内），
回落 。⇒ .tres 的 mediaRects 也是权威，必须与 .dat 内的 rect **一致**。

## TryReadEmbeddedAtlasImage 读头顺序（:1696-1700，逐字）
  fileAccess.GetFloat();          // frameRate
  fileAccess.Get16();             // frameMax
  imageAtlasSize = new Vector2I(Get16(), Get16());   // atlasW, atlasH
  bufferLen = (int)Get64();       // 像素字节数
  ReadEmbeddedImageAtlasFromDat(fileAccess, imageAtlasSize, bufferLen, out decoded)
