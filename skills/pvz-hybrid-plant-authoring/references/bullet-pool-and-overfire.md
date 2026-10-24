# 子弹对象池（BulletField）与「过火」（火炬树桩）机制

> 2026-09-30 源码级核对。回答三个问题：**子弹池有几个**、**子弹的生命周期**、**火炬树桩是不是各自一个池**。

## 1. 池：**全局唯一一个**

| 事实 | 位置 |
|---|---|
| `public static BulletField Instance { get; private set; }`，`_Ready()` 里 `Instance = this`；`_ExitTree()` 里 `Instance = null` | `Prefab/TowerDefense/Projectile/BulletField/BulletField.cs:696` / `:771` / `:796-800` |
| 所有发射都经 **`BulletField.EnsureMountedOnCharacterNode()`** 取同一个节点 | `Script/.../FireComponent/FireComponent.cs:2753` / `:2812` / `:2839` |
| 池容量写死 **65536** 槽：`_freeList = new int[65536]` + `_freeCount`，初始化时 `_freeList[i] = 65535 - i` | `BulletField.cs:354` / `:360` / `:775-779` |
| 分配 = 从 freelist 弹一个 index（`_freeList[--_freeCount]`）；回收 = 压回（`_freeList[_freeCount++] = index`） | `BulletField.cs:879-883` / `:933` / `:1002` |

⇒ **不存在"每个植物一个池"或"每个火炬一个池"**；全场景子弹共用这一个池的 65536 个槽。
（只有 `Test/*.cs` 里会 `new BulletField()` 造独立池做单测。）

## 2. 生命周期

```
生成  FireComponent.CreateProjectile*  →  SpawnBulletField()
        →  BulletField.EnsureMountedOnCharacterNode()
        →  TrySpawnFromConfig(...)          // 从 _freeList 取 index，写入 _data[index] 的 BulletData
运行  池每帧模拟；若 _allZones.Count > 0，对每颗活跃子弹调 ProcessZonesForBullet(index)
        →  区域的 OnBulletIntersect(ref BulletData b, int index)   // 火炬在这里下手
结束  BulletLifecycleTerminalReason { Landed, BlockedBounce, Despawned }
        +  BulletLifecycleEndedEventHandler(source, ownerSequence, slot, reason) 回调
        →  Despawn(index)  →  _freeList[_freeCount++] = index      // 槽位回收，供任意子弹复用
```
* "回收"回收的是**槽位**，不是销毁对象；渲染/行为模板走缓存字典
  （`_preparedProjectileChanges`、`_templateConfigCache`、atlas 缓存…），换配置只是重新绑定。

## 3. 过火（火炬树桩）：**同一个槽就地改**，改不了才换槽

火炬树桩自己**没有池**，它只是一个"区域"：

* 组件 `ChangeProjectileComponent`（实现 `IProjectileZone` / `IProjectileZoneBinding`）：
  * `OnActivated()` → `BindBulletField(BulletField.Instance)`；`OnDetaching()` → `BindBulletField(null)`
    （`ChangeProjectileComponent.cs:127-156`）；
  * 注册到**那唯一一个池**的区域列表：`RegisterZone` → `_allZones` / `_zonesByRow` / `_zoneEntries`
    （`BulletField.cs:6349-6365`、`:686-690`）。
* 触发表 = 数据：定义里的 `changeName`（`Fire` / `IceFire` / `MegaFire` / `Star` / `GarlicFire`…），
  查表 `TowerDefenseProjectileRegistry.GetProjectileChange(fromName, changeName)`
  （`ChangeProjectileComponent.cs:245-246`，表在 `Asset/Config/ProjectileChange/*.tres`）。
* 触发区：`checkShape`，火炬用的是 `RectangleShape2D size=(100,98)` + `LocalTransform` 平移 `(3,0)`
  （`Definitions/FireOffset3Definition.tres`）。
* 命中后的改动路径（**先就地、后换槽**）：
  ```
  ChangeBulletData(index, newConfig, changeCharacter, damageOverride)      BulletField.cs:6602
    ├ TryChangeBulletDataInPlace → ApplyPreparedProjectileChange(index,…)  :3889
    │    直接改 _data[index] 的 config / renderMode / damage / damageFlags /
    │    penetrateNum / 动画定义 …，并复位 hitOver/over/collisionEnabled/lastHitInstanceId
    │    ★ 保留原槽位、位置、速度、旋转  → 返回 Changed ⇒ `return index`（同槽）
    ├ 仅当 `fireMethodFlags != reference.fireMethodFlags` ⇒ RequiresReplacement   :3894-3896
    └ RequiresReplacement：先逐字段抄下 40+ 个状态（pos/vel/speed/gridPos/gridY/camp/
      collisionFlags/gravity/catapult*/target/hitBoxScale…），再 `Despawn(index)` 释放旧槽
      → `TrySpawnFromConfig(...)` 从**同一个池**重新分配一个槽 → 状态搬回去   :6640-6700
  ```

**去重与串联**：
* 同一火炬对同一颗弹**不重复触发**：`b.zoneExclusionOwner == this` 且未过期时直接返回并续期
  （`ChangeProjectileComponent.cs:225-241`）。
* 换成**另一个**火炬时不受此排除 ⇒ 可再次转换（例如豌豆→火焰豌豆→巨型火焰豌豆），
  前提是目标表的 `from` 里有该名字。
* 入口守卫：`b.camp` 必须与火炬同阵营；`!b.checkAll && b.gridPos.Y != parent.gridPos.Y` ⇒ 不同行不处理；
  **`(b.fireMethodFlags & 2) != 0` ⇒ 该子弹不可被火焰改变**（`ChangeProjectileComponent.cs:238-243`）。

## 4. ★★★ 权威数据源：`Registry/Projectile/ProjectileRegistry.json`

**别去扫目录！** `TowerDefenseProjectileRegistry.REGISTRY_JSON` =
`res://Registry/Projectile/ProjectileRegistry.json`，`RegisterInit()` 读三段：

| 段 | 含义 |
|---|---|
| `Projectiles` | 名字 → 路径（加载成 **`TowerDefenseProjectileData`**）⇒ **这就是"游戏里有哪些子弹"的定义**（本项目 97 种） |
| `Skins` | 皮肤（名字 → {ProjectileScene, SplatScene}） |
| `Changes` | **转换表**：`changeName` → {from: to}（本项目 5 张） |

⚠️⚠️ **两个曾把本项目坑惨的错**（2026-09-30 修正，务必照抄结论）：

1. **子弹配置有"两套类 + 两个目录"，而且目录 ≠ 注册表**：
   · `Asset/Config/Projectile/**` → `TowerDefenseProjectileConfig`（本项目 138 份）——**其中 23 个名字根本没注册，按名字打不出来**；
   · `Registry/Projectile/Config/**` → `TowerDefenseProjectileData`（98 份）——才是注册表的落点。
   ⇒ **按目录枚举会"双向出错"**：混进打不出来的死名字 + 漏掉一大批真子弹。
2. **转换表也要读 JSON，别读 `.tres`**：`Asset/Config/ProjectileChange/*.tres` 是**编辑器侧资源**，
   与运行时 JSON **内容不同** —— JSON 里有第 5 张表 **`GarlicFire`**（大蒜火炬），
   且 `Fire` 只有 6 条（文件里 8 条）。只读文件会漏掉整张大蒜表。

### 五张转换表（JSON，运行时权威）

| 表 | 条数 | 映射 |
|---|---|---|
| `Fire`（普通火炬） | 6 | `Pea→FirePea` `PeaBomb→FirePeaBomb` `SnowPea→Pea` `ZombiePea→FireZombiePea` `FriedKernel→Popcorn` `MagicPea→MagicPeaFire` |
| `IceFire`（寒冰火炬） | 7 | `FirePea→IceFirePea` `Pea→IceFirePea` `SnowPea→IceFirePea` `FriedKernel→IcePopcorn` `Popcorn→IcePopcorn` `MagicPea→MagicPeaFireBlue` `MagicPeaFire→MagicPeaFireBlue` |
| `MegaFire`（巨型火炬） | 9 | `FirePea→MegaFirePea` `FirePeaS→FirePeaU` `IceFirePea→MegaFirePea` `Pea→MegaFirePea` `SnowPea→MegaFirePea` `WhiteFirePea→MegaFirePea` `MagicPea→MagicPeaFireMega` `MagicPeaFire→MagicPeaFireMega` `MagicPeaFireBlue→MagicPeaFireMega` |
| `Star`（星星火炬） | 4 | `BigStar→BigFireStar` `SnowStar→Star` `Star→FireStar` `StarBigCatGatlingPea→FireStarBigCatGatlingPea`（**后两条的 from/to 都没注册 ⇒ 死条目**） |
| **`GarlicFire`（大蒜火炬）** | 6 | `Pea→GarlicFirePea` `SnowPea→GarlicFirePea` `FirePea→GarlicFirePea` `MagicPea→MagicPeaGarlicFire` `MagicPeaFire→MagicPeaGarlicFire` **`Garlic→GarlicP`** |

产出去重后 **19 种**，其中 18 种在注册表里（唯一不在的 `FireStarBigCatGatlingPea` 连 its `from` 也没注册 ⇒ 本来触发不了）。
反直觉映射：`SnowPea→Pea`、`SnowStar→Star`（**火把冰融化**）、`FriedKernel→Popcorn`（炸玉米→爆米花）。

## 5. 实操要点

* **随机池的正确做法**：从 `ProjectileRegistry.json` 的 `Projectiles` 取名字，
  排除魅惑（引用 `TowerDefenseCharacterBuffHypnoses` / `EventHypnoses` 的那几个）+
  产资源（`Coin*`/`Sun*`）+ 僵尸专用（`Axe`/`Basketball`/`Ladder`）。
  本项目结果：97 − 10 = **87 种**。
* **判定"某子弹是不是植物在用"别看名字猜**：
  `grep -rl 'projectileName = &"<名字>"' Asset/Anime/Character/{Plant,Item,Zombie}`
  —— 本项目据此抓出 3 处误判（`ZombiePea`/`FireZombiePea`/`CaskPea` 实际由
  僵尸豌豆射手 / 机枪射手Z / 海盗豌豆发射，名字里的 "Zombie" 是**植物的名字**不是阵营）。
  也有靠**代码**生成的：`TowerDefensePlantRichwood.cs`（**宝藏树桩**）里
  `new StringName("Chest")` ⇒ 宝箱子弹是它打的。
* **要按"类别"筛子弹时，别只看名字模式**：名字里带 `Cob`/`Cannon` 的不一定是加农炮 ——
  本项目实测 `CabbageCob*` 其实是**玉米卷迫击炮（Cabbage Cob Mortar）/ 玉米卷重炮手（CabbageCob-X）**；
  而 `WildMineCannon`（狂野土豆雷）看名字像地雷，实际**复用 `PotatoCobCannonCob` 弹体 + 落地爆炸**，
  是加农炮。⇒ 判定要用三条交叉：**中文名（Translate.csv）+ 引用它的植物 + 弹体资源路径**。
* **出膛点决定能不能被过火**：区域是 100×98（≈1.25 格）、偏 +3px；自制植物的炮口若离本体太远
  （例如落在邻格深处），仍会在邻格火炬的区内 ⇒ 能过火；但若 `fireMethodFlags` 带了 bit 2 就直接免疫。


