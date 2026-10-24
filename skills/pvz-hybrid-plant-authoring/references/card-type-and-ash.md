# 卡类型 / 价格与冷却 / 灰烬（Crater）—— 三个常被问到的"标签类"需求

> 2026-09-30 实证（电能超级机枪射手：钻卡 + 2000 阳光 + 60s 冷却 + 不涨价 + 灰烬伤害）。
> 全部字段都在 **`TowerDefensePlantConfig`** / **`TowerDefensePacketConfig`** 里，**纯数据可达，不用写插件**。

## 1. 卡类型（白/金/钻/彩/星…）—— `PACKET_TYPE`

```csharp
public enum PACKET_TYPE   // TowerDefenseEnum
{
    NOONE = -1,
    WHITE,      // 0  白卡
    GOLD,       // 1  金卡
    DIAMOND,    // 2  ★ 钻卡
    COLOUR,     // 3  彩卡
    STAR,       // 4  星卡
    ORIGINAL,   // 5
    ZOMBIE,     // 6
    COVER,      // 7
    GRAY        // 8
}
```

写在 **两处**（都要改，否则选卡界面与卡库不一致）：
- `Resources/Characters/Plants/<KEY>/Packet/<KEY>.tres` → `type = 2`
- `Resources/Cards/<KEY>.tres` → `type = 2`

✅ 对账口径：内置「超级机枪射手」= `type = 1`（GOLD），与它 mod.json 里写的"金卡"一致 ⇒ 枚举值可信。

## 2. 阳光 / 冷却 / **重复种植涨价**

全在 **`TowerDefensePlantConfig`**（`Resources/Characters/Plants/<KEY>/Config/TowerDefensePlant<KEY>.tres`）：

| 字段 | 含义 | 备注 |
|---|---|---|
| `cost` | 阳光消耗 | 例：`cost = 2000` |
| `packetCooldown` | 卡片冷却（秒） | 例：`packetCooldown = 60.0` |
| **`costRise`** | **重复种植涨价**（每再种一株 +N 阳光） | ★ **不涨价就写 `0`**；内置模板默认 `100` |
| `canCopy` | 能否被全息投影花盆复制 | ★ **必须 `true`**（内置金卡根本不写这字段 = 默认 true；写 false 会让花盆收不到模板） |
| `hitpoints` | 韧性 | |
| **`ashScene`** | 该角色的"灰烬/残骸"场景 | `PackedScene`，可空 |
| `plantCover` / `maskFlags` / `homeWorld` | 覆盖关系 / 掩码 / 世界 | 照抄同族内置值 |

## 3. 灰烬（Crater）—— "僵尸被该伤害击杀则化为灰烬"

游戏侧的灰烬 = **一个独立角色 `TowerDefenseCrater`**（配置在
`Asset/Anime/Character/Crater/Crater*/Config/*.res`，如 `CraterDayGround` / `CraterLava` / `CraterImp` / `CraterK`…）。

**API**：

```csharp
// TowerDefenseCharacter.cs:4469
public void CraterCreate(bool nolimit = false, string craterName = "CraterDayGround", bool halfCrater = false)
// 内部：TowerDefenseManager.GetPacketConfig(craterName).Plant(gridPos, playAudio:false, noLimit:true)
// 自带 cell.CanCraterCreate() 去重；nolimit=true 时对植物直接 Destroy

public bool IsDie()   // :3991，读 die 字段
```

★ **实现「被该伤害击杀才化灰」的正确姿势**（插件侧）：
1. 造成伤害前，把**这次命中的敌方目标**记下来（`GetCharactersIntersectingRect` 自己收集）；
2. ⚠️ **伤害是异步排队的**（`TowerDefenseExplode.CreateProjectileExplode` → `QueueProjectileExplode` → 下一物理帧才结算）
   ⇒ **不能当场 `IsDie()`**；
3. **下一帧**再遍历那批目标，`c.IsDie()` 为真才 `c.CraterCreate(false, "CraterDayGround", false)`。
   ⇒ 这样只给"被本次伤害打死"的目标加灰，而不是无脑给所有死亡目标加灰。
4. `CraterCreate` 内部有格位去重，重复调用安全。

## 4. 克隆模板建包（最快的闭环路径）

```text
1. 选一个**已实机验证过**的同族包当模板（本例：SuperGatlingPea）
2. 整目录复制到新包名；文件名/目录名里的 key 全部替换
3. 外观三件套（.dat/.tres/Atlas.png）**二进制原样复制**，只改：
     · 文件名
     · `.tres` 里的 `animeFile = "./<新KEY>.dat"`
     · Sprite 场景里的 ExtResource 路径
4. 逐文件改：PlantConfig（cost/cooldown/costRise/canCopy）、Packet+Cards（type/saveKey/name/文案）、
   Scene（fireInterval / Marker 数量 / metadata.mod_display_name / config 路径）、
   ComponentSet（fireProjectileList 条数 = 一轮颗数）+ mod.json（id / runtimeEntryType / resources 清单）
5. 清掉模板残留（`.bak*`、不属本 Mod 的 `.pvzmodeproject`）—— ★ 克隆流程每次重跑都会把它们带回来，生成器里要主动删
6. 打包 = zip（`ZIP_DEFLATED` + **固定时间戳** ⇒ 幂等；`mod.json` 必须是第 0 个条目）
```

## 5. 交付配闸门（两道，缺一不可）

| 闸门 | 查什么 |
|---|---|
| `check_xxx_params.py` | **插件源码**里的参数常量（GOLD 字面量 + 自洽性如 `250×3=750`）+ `--neg` |
| `check_xxx_pack.py` | **包数据侧**：cost / packetCooldown / **costRise** / canCopy / type / saveKey / baseDamage / penetrateNum / fireInterval / 发射条目数 / Marker 数 / mod.json 身份 / .pmod 结构 + `--neg` |


---

## 6. 「无限穿透」的正确配方（2026-09-30 实证：照抄仙人三叶草）

**全项目 6314 个 `.tres` 里只有 3 个用 `penetrateNum = -1`**，最标准的样例是
**仙人三叶草 `CactusBlover`**（`Script/Component/TowerDefense/Character/BloverComponent/Definitions/CactusBloverComponentDefinition.tres`）：

```gdscript
projectileName = &"Spike"
damageFlags = 2
collisionFlags = 11
fireMethodFlags = 5          # ★ 1(SHOOTER) | 4(PENETRATE) —— PENETRATE 位必须置
penetrateNum = -1            # 无限穿透（BulletField.cs:3585 里 == -1 ⇒ 命中后不消失）
overridePenetrateNum = true  # ★★ 关键开关：不加它，penetrateNum 根本不会被写进 config
```

★★★ **最容易踩的坑**：`TowerDefenseProjectileCreateData.ApplyOverride()` 里是

```csharp
if (overridePenetrateNum) { config.penetrateNum = penetrateNum; }
```

**只写 `penetrateNum = -1` 而漏掉 `overridePenetrateNum = true` ⇒ 等于没写**（config 仍是默认 `3`，只能穿 3 个）。
且 `overridePenetrateNum` **没有 Setter**，插件里只能直接赋 `public bool` 字段：

```csharp
data.penetrateNum = -1;
data.overridePenetrateNum = true;
data.fireMethodFlags |= (int)TowerDefenseEnum.PROJECTILE_FIRE_METHOD_FLAG.PENETRATE;
```

## 7. 新增一颗「自己的子弹」（不污染内置）

**别去覆盖内置 `Pea`**（所有豌豆植物都会跟着变）。正确做法 = **provides 新键**：

```text
mod.json
  "provides": { ..., "Projectile": ["ElectricPea"] }
  "resources": [ ..., "Resources/Projectiles/ElectricPea.tres",
                      "Resources/Projectiles/ElectricPea/ProjectileElectricPea.png",
                      "Resources/Projectiles/ElectricPea/ProjectileElectricPea.tscn" ]

Resources/Projectiles/ElectricPea.tres                       ← TowerDefenseProjectileConfig
Resources/Projectiles/ElectricPea/ProjectileElectricPea.png  ← 一张 PNG（内置口径 ~28×28）
Resources/Projectiles/ElectricPea/ProjectileElectricPea.tscn ← Sprite2D + texture
```

`.tres` 最小结构（照抄内置 `PeaDefault.tres`）：

```gdscript
[gd_resource type="Resource" script_class="TowerDefenseProjectileConfig" format=3]
[ext_resource type="PackedScene" path="./ElectricPea/ProjectileElectricPea.tscn" id="1"]
[ext_resource type="Script" path="res://Resource/TowerDefense/Projectile/TowerDefenseProjectileConfig.cs" id="2"]
[resource]
script = ExtResource("2")
name = "ElectricPea"
projectileScene = ExtResource("1")
projectileObject = 301
collisionFlags = 1
catapultHeight = 400.0
```

★★ **路径坑**：子弹的 `.tscn` **父目录不能叫 `Sprite` / `Scene`**！`ModLoader.InferRuntimeEntry`
（`verify_pmod.py:105`）会把 `.../Sprite/xxx.tscn` **一律**推断成 `CharacterSprite/<xxx>`
⇒ manifest 没声明就 `binding.undeclared` **FAIL**。放 `Resources/Projectiles/<KEY>/` 下即可
（`.tscn` 不在 `RESOURCE_EXT` 里，只要不匹配 Scene/Sprite 规则就直接返回空、不参与推断）。

## 8. 植物外观替换 = AdobeAnimate 图集（**不是**一张 PNG）

植物（和僵尸）的外观是 **`AdobeAnimateSprite` → `flashAnimeData`(`AdobeAnimateData` .tres) → `.dat` 自包含图集**；
`.tscn` 里只有 3 行（script + flashAnimeData + offset）。

- 想换外部美术 ⇒ 必须生成 `.tres` + `.dat`（不是塞张 PNG 就行）。
- 现成链路：`.cache/build_official_skin.py`（**吃经典 `.reanim.compiled`**）。
  ⚠️ 若素材来自 **Unity prefab**（Transform + SpriteRenderer），中间**缺一个转换器**：
  要么把 prefab 导成"单帧 reanim"再喂它，要么改造 `build_ssg_skin.py` 直接产出 AdobeAnimateData。
- `.cache/build_source_single.py` 只是**抠背景**预处理，不是图集生成器。


---

## 9. ★★★ 写 mod 资源文件的三个硬约束（2026-09-30 自踩：**整包 apply 失败**）

症状：mod 装上了、也在 `enabled_mods.json` 里，但**整个包被拒**。日志形如：

```
ERROR: .../XComponentSet.tres:22 - Parse Error: Expected value,
ERROR: .../X.tscn:11 - Parse Error: [ext_resource] referenced no...
ERROR: .../Resources/Projectiles/X.tres:1 - Parse Error: Expected '('
WARNING: [ModManager] <id>: required runtime resource failed: Projectile/X: ...
WARNING: [ModManager] failed to apply enabled package: <id>
```

| # | 约束 | 踩了会怎样 |
|---|---|---|
| ① | **`.tres` / `.tscn` 里绝对不能写 `#` 注释**（Godot 配置格式不支持注释） | `Parse Error: Expected value`；**说明文字一律写进生成器的 Python 注释里** |
| ② | **改生成器（尤其含三引号模板）必须用 Write 写 `.py` 补丁文件再跑，禁止 bash 内联 `python -c`** | shell 吞掉模板里的 `"` ⇒ 生成 `type=Resource` 这种残废资源 ⇒ `Parse Error: Expected '('` |
| ③ | **同 id 的旧 `.pmod` 必须清掉** | 两份同 id 冲突；**加载失败的那份会被游戏侧改名成 `<id>-<hash>.pmod`**，还必须连带清 `ModsCache/<id>-<hash>/` |

★ **排查顺序**（照做）：`Mods/enabled_mods.json` 看有没有被启用 → `logs/godot.log` 里 grep 包 id →
**看到 `Parse Error` 就直接去报错行号看那个文件**（99% 是注释/引号/相对路径这三类）。
★ `Mods` 目录里出现 `<id>-<hash>.pmod` 这种名字，通常意味着**那份包曾经加载失败**（别当成正常装机）。


---

## 10. ★★★ mod 包里的裸 `.png` **不能**当 `Texture2D` 用（2026-09-30 实证）

**症状**（能在日志里直接看到）：
```
ERROR: No loader found for resource: A/ModsCache/<id>/.../X.png (expected type: Texture2D)
ERROR: .../X.tscn:N - Parse Error: [ext_resource] referenced non-existent resource
ERROR: [BulletField:E_FIELD_UNAVAILABLE] projectile='X' scene='.../X.tscn' reason='BulletField coul...'
```
→ 子弹一颗打不出、或植物/道具显示空白。**不是路径错，是根本没有 loader。**

**原因**：导出时**所有 `.png` 已被烘焙成 `.ctex`**（`.godot/imported/` → 打进 pck）。
运行期的 `ResourceLoader` **对裸 PNG 没有 loader**，`No loader found` 就是这么来的。
（这也是为什么 `verify_pmod` 只看得到 `.tres/.res/.tscn` 能归类，`.png` 走的是"媒体"那条路。）

**三条正确做法**（按推荐顺序）：

| 做法 | 适用 | 说明 |
|---|---|---|
| **① 用 `.dat` 自包含图集**（AdobeAnimate） | 角色 / 子弹 / 需要动画 | 图片**塞在 `.dat` 二进制里**，由 `animeFile` 读走，**不经过 Texture2D 加载** ✓ 这是本作的正统做法 |
| **② 插件自己读字节** | 运行时贴图 / UI 图标 | `FileAccess.GetFileAsBytes()`（或 `Image.load_from_file`）→ `ImageTexture.CreateFromImage()`。**ProbeV029 的 `Resources/Stickers/*.png` 就是这么用的**（`EnsureStickersLoaded()`） |
| **③ 引用内置资源** | 只是想要"能用" | `projectileScene` / `texture` 直接指向 `res://` 下的内置资源（它们已在 pck 里） |

**反面教材**（本轮踩的）：新建子弹时写
```gdscript
[ext_resource type="Texture2D" path="./ProjectileX.png" id="1"]
[node name="ProjectileX" type="Sprite2D"]
texture = ExtResource("1")
```
—— 结构本身没错，但那个 PNG 是**mod 包里的裸 PNG** ⇒ 加载失败 ⇒ 整个子弹场景失效。

★ 另外记一条：**`projectileName` 只能用 `ProjectileRegistry.json` 的 `Projectiles` 里存在的键**。
长得像的配置文件名（如 `Cyber`）不一定在注册表里 —— 用之前先查 JSON，否则同样拿不到子弹。
