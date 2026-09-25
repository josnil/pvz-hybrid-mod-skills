# 植物数据字段：数值 / 卡入库 / 血量 / 直接种空地

## 1. 费用 / 冷却 / 卡类型 / 涨价

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
（`_override` / `overrideCost` 优先）。
**「种植涨价」是 `costRise`，不是 `cost` 的乘数** —— 别写成乘法。

## 2. 血量（纯数据，不需要插件）

`characterConfig.hitpoints`（`TowerDefenseCharacterConfig`，**类默认 300.0**）。

```csharp
// TowerDefenseCharacterInstance._Init:317-320
hitpointsBase = config.hitpoints;
hitpoints = hitpointsBase + hitpointsNearDeath;
```

⇒ 在 `…/Config/TowerDefensePlant<Key>.tres` 加一行 `hitpoints = 1000.0` 即 1000 血。

⚠️ 写在与**类声明顺序**一致的位置（`hitpoints` 紧跟 `name`），否则编辑器保存会重排。

## 3. ★ 能不能直接种在空地 = `plantCover` + packet override

`plantCover` 是「**可覆盖的底座名单**」。**非空 ⇒ 这张卡就只能种在名单里那些植物上**，
空地种不上。

```csharp
// TowerDefenseCellInstance.CanPacketPlant:787-800
if (packetConfig.GetPlantCover().Count > 0 && !noLimit) {
    foreach (… characterList …) if (… GetPlantCover().Contains(name)) return true;  // 有底座 ⇒ 允许
    if (!packetConfig.GetCoverCanDirectPlant()) return false;                       // 没底座 ⇒ 拒
}
```

⚠️ **查中文名要去 `Asset/Translate/Translate.csv`**：`PlantPeaShooter` = **双发射手**
（不是「豌豆射手」）。**别凭英文猜中文名**。

⚠️⚠️ **`GetCoverCanDirectPlant()` 只在 packet 有 `_override` 时才读，否则硬编码 `return false`**
（`TowerDefensePacketConfig.cs:500-507`）
⇒ **改 `characterConfig` / 改 `plantCover` 都做不到「不改底座还能直接种」**，**必须挂 packet override**。

### 解法（纯数据）：卡片里内联一个 override 子资源，**只开一个字段**

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
  给 `PlantGatlingPot` 开的就是它（**全解包仅 2 例**）。照抄即可，**不是野路子**。
* **为什么只写一个字段就够**：`TowerDefensePacketOverride` 的默认值全是「不覆盖」语义
  （`type=NOONE`；`cost·costRise·costMultiple·packetCooldown·startingCooldown·weight·wavePointCost = -1`；
  `plantCover=[]`（`GetPlantCover` 在 **Count>0** 时才用它 ⇒ 空表回落，**底座名单保住**）；
  `hypnoses=false`）；`islimitGridNum` 默认 `true`，与无 override 时的硬编码 `true` **同值**（中性）。
  唯一无条件生效的是 `characterOverride`，它**默认非 null**（`new TowerDefenseCharacterOverride()`），
  但逐字段是**空操作**（`scale/hitpointScale/walkSpeedScale/animeSpeedScale = -1`、四个数组为空、
  `invisible=false`、`_hasCanMowerMoveOverride=false`）⇒ 不碰血量/缩放/动画。
  **因此别往 override 里多写字段。**
* 好处 = **既能在空地直接种，又保留「种在底座上升级」**（追加能力，不是替换）。
* ⚠️ **`.tres` 属性名 = C# 字段名去掉前导下划线**：`_override` → `override`。
* ⚠️ 想**免疫关卡 override**（关卡用 `packetOverride` 会在 `PlantAtCore` 里临时顶掉 `_override`，
  于是又变回必须底座）⇒ 只能 `plantCover = []`，**代价是失去升级路**。二选一，**问过用户再定**。
* ⚠️⚠️ **`plantCoverAll` 是死字段**：全解包只在编辑器 UI 里被绑定，**运行时从未被读取**，别当开关。

### 断言这两条时的坑（写闸门必看）

* 从 `.tres` 里切 override 子资源，**必须切完整的 `[sub_resource type="Resource" id="…"]` 整行**；
  用 `id="…"` 切片会残留一个 `]` 被当成字段名 ⇒ **假红**。
* 「只允许写这几个字段」这类断言一定要配一个**反向对照**（喂一份故意多写字段的假 body，必须报出来），
  否则切片一写错就变成**永远为真的假绿**。

## 4. ★ 让卡进「选卡界面」和「图鉴」（只有需要时才做）

先记住因果链，**别改错地方**：

| 玩家看到的东西 | 数据来自 | 位置 |
|---|---|---|
| **选卡界面**（一关开始时选卡） | `TowerDefenseManager.GetPacketBankData(config.packetBankType)` 的 `category[分类]` | `TowerDefenseBattleFeaturePacketBank.cs:170` / `:514` |
| `packetBankType` **默认值** | `"GeneralPlant"`（关卡可被 `TowerDefenseLevelConfig.packetBank` / `PacketBankName` 覆盖） | `TowerDefenseLevelPacketBankConfig.cs:9` |
| **图鉴**植物页 | `WithPlants(GetPacketBankData("GeneralPlant"))` —— **同一个库的深拷贝** | `Almanac.cs:219` |

⇒ **根上的修法：往共享卡库 `ResourceManager.Instance.TOWERDEFENSE_PACKETBANKS["GeneralPlant"]
.category["Gold"]` 追加卡 key**（check-then-add，幂等）。
一次改动同时喂到「选卡界面」和「图鉴」⇒ **两边数据天然一致**，不需要各补一份。

* 还要补**派生库**：`ResourceManager.BuildExpandedPacketBank` 沿 `Include` 递归合并分类，
  所以 `Include` 闭包里含 `GeneralPlant` 的库（实测只有 `Total`）运行期是它的超集。
  运行期按 `res://Asset/Config/PacketBank/PacketBankResource.json` 的 `Include` 闭包算，
  **别写死**（离线重算时会得到 `['GeneralPlant','Total']`）。
* ⚠️ **`GetPlantList()` 只认 White/Gold/Diamond/Colour/Star/Original 六个键**
  （`TowerDefensePacketBankData.cs:48-68`）—— **故意不认 `ModPlants`**。
  这就是「只把它放进图鉴的 `ModPlants` 分类还不够」的硬证据。
* ⚠️ Mod 植物会被 `XWModContentCatalog.WithPlants()`（`XWModContentCatalog.cs:107-123`，
  `PlantCategory="ModPlants"` 见 `:15`）**单列一类**，全仓只有 `Almanac.cs:219` 调它。
  补完共享卡库后图鉴里它会**出现两次**（`ModPlants` + `Gold`）—— 那是游戏自己的隔离设计，**别去删**。
* 兜底（可选）：图鉴是按需实例化、每次打开都新拷一份，正常时序下补完共享卡库就够了；
  只有「图鉴已经开着 → 之后才补卡库」才需要再补一次
  `Almanac.plantPacketBank`（**public 字段**，`Almanac.cs:101`）的同一分类。
  ⚠️ 改它之后**只在反射读到 `_plantInitialized == true` 时才调 `InitPlant()`** 刷新
  （图鉴刻意懒初始化，自带测试 `AlmanacVirtualizedResidencyRuntimeTest` 断言
  「不得提前初始化隐藏分类/预览节点」）。
* ⚠️ **副作用必须说清楚**：进了 `Gold` 就等于成为一张正常金卡，凡是按卡库随机取卡的逻辑
  （`GoldShardDropItemHandler`、`TowerDefenseCraterG`、`PanGoldBean`）以及走 `GetPlantList()`
  的（植物礼盒 / LuckyBlover / CubeBox）都可能给出它。**交付时必须如实告知用户**；
  若用户只想要「图鉴里能看到」，**就别做这一步**。
* `GeneralPlant.Category` 实测只有 6 个键：`White178 / Gold19 / Diamond16 / Colour6 / Star27 / Original20`
  （Item/GraveStone/Zombie 在别的卡库）—— **别照** `XWPacketBankVisualResourceEditor.DefaultCategories` 猜。

## 5. 翻译 / 名称

* 名字 key 形如 `TOWERDEFENSE_PLANT_<KEY大写>_NAME` / `_EXPRESTION`（注意原版拼写是 `EXPRESTION`，
  不是 `EXPRESSION`）/ `_HANDBOOK_EXPRESTION` / `_HANDBOOK_STORY`。
* ⚠️ 见 `plant-package-and-gates.md` §11：翻译**只在编辑器可见**，游戏内会显示原始 key，
  **必须在交付说明里标注**。
