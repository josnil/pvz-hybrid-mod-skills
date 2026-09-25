# 植物包结构 / 命名 / 8 条硬闸门

类别名是 `Character`，但**不能**像投射物那样只读路径前缀 —— `ModLoader` + `XWModContentValidation`
对角色包有 **8 条硬闸门**。**任何一条不过 ⇒ 整包 apply 被拒**（用户看到的就是「游戏加载失败」）。

离线复刻这 8 条：`.cache/check_modloader_gates.py`（不用进游戏）。

## 1. 场景路径恰好 6 段

```
Resources/Characters/<类>/<Key>/Scene/<Key>.tscn
Resources/Characters/<类>/<Key>/Sprite/<Key>.tscn
```

* `<类>` ∈ `{Plants, Zombies, Props, Vases, Mowers, Items, Graves, Craters}`（`IsKnownCharacterCategory`）。
* **文件名 == 目录名 == `<Key>`**；段数 ≠ 6 或名字对不上 ⇒ 整个角色包不被识别。
* `Sprite/` 那个**不是可选项**，少了必然加载失败（闸门 6）。

## 2. `Resources/Characters/<类>/…`（≥5 段）下任何文件都算「角色包依赖」

⇒ 贴图 `.tscn`、`Config/*.tres`、`Packet/*.tres`、`Scene/*ComponentSet.tres` 放这里
**不会**触发 `unsupported package file`，也**不会**进 `InferRuntimeEntry`。

⚠️ 所以这些文件**不推 derived key**，**别拿它们去对 `provides`**
（对不上会被判 `resource is not unambiguously declared by manifest` → 静默丢弃）。

## 3. 禁用项

* 包内 `.scn` / `.res` **一律禁用**；
* `.tscn` / `.tres` **不得内嵌** `type="GDScript"` / `type="CSharpScript"`。

## 4. ★ 引脚本用 `res://`，**自引用必须相对**（最容易搞反）

| 指向 | 写法 |
|---|---|
| 游戏自带资源（`res://Prefab\|Asset\|Script\|Resource\|Registry\|Extends`） | **必须 `res://`**。非 `res://` 的 `[ext_resource type="Script"]` 在 `.tscn` 里被**静默剥离**、在 `.tres` 里**直接拒绝** |
| 包内自己的文件 | **必须相对**（`./XComponentSet.tres`、`../Config/X.tres`） |

原因：`ModLoader.TryGetGodotResourcePath` 用 `ProjectSettings.LocalizePath()` 把包内文件映射成
`user://ModsCache/<名>/…` 再 `ResourceLoader.Load`，所以**相对引用在 `user://` 树内解析**；
而 `res://Resources/Characters/…` 会在**游戏 pck 根**解析，那里**根本没有 `Resources/` 目录**
⇒ 配置/组件集加载失败 ⇒ 角色被拒 ⇒ 整包失败。官方模板
`XWResourceCreateRoute.BuildCharacterRuntimeSceneContent()` 也是相对写法。

⚠️ **Sprite 场景在 5 段目录下 ⇒ 相对路径要 5 个 `../`**（例如
`../../../../../Resources/Animations/<Key>.tres`）。段数数错 = 静默不画。

## 5. 必须额外交付 Sprite 场景

```csharp
string key = CHARCTAER_SPRITE.ContainsKey(saveKey) ? saveKey : characterConfig.name;
RequireReference(manifest, "CharacterSprite", key);   // 查不到 → throw → 整包被拒
```

运行时 `TowerDefenseManager.GetPacketSpriteScene()`（**每张卡渲染都会调**）还会
`GetCharacterSprite(name)` → `throw new KeyNotFoundException`。

## 6. ★ `saveKey` == 注册键 == `characterConfig.name` == 场景 `<Key>`

* `packet.saveKey` 必须等于「注册键」= `Resources/Cards/<文件名去扩展>`；
* `characterConfig.name` 必须等于角色场景的 `<Key>`
  （`TowerDefensePacketConfig.Create()` → `CreateCharacter(characterConfig.name)` → `TOWERDEFENSE_CHARCATERS[name]`，
  mod 角色只可能注册在 `<Key>` 这个键上）。

👉 **最稳做法：让 `<Key>` = `config.name` = `saveKey` = 卡片文件名 = 精灵文件名 全部同一个字符串。**

## 7. `unlockCheckList` 只能空表或 `XWModProgressUnlockCondition`

照抄原版的 `UnlockConditionPacketBankCategoryPacketUnlockNumConfig` 会被判
「必须使用 Mod 专属解锁条件」→ throw。写 `unlockCheckList = []` = **直接可用**。

> 附带好消息：判定「卡是否解锁」走 `XWModPlayerProgressService.TryPacketUnlock`，
> 其中 **Mod 卡的空 `unlockCheckList` ⇒ `unlocked = true`**（内置卡空表反而 `return false`）
> ⇒ Mod 卡天然可选，不用配解锁条件。

## 8. `provides` 是 all-or-nothing

里面每个键都必须**真的注册得上**（`ValidateManifestRegistrations`），多写一个不存在的键也会整包失败。

```json
"provides": { "Character": ["<Key>"], "CharacterSprite": ["<Key>"], "Packet": ["<Key>"] }
```

三键都正好是 `<Key>`（**不是** `<Key>Packet`）—— 因为 `saveKey` 必须 == 注册键，
而 `characterConfig.name` 必须 == 场景键，统一成 `<Key>` 才能同时满足。
**都走 `provides`**（新键），同 (类别,键) 重复 → `ambiguous`。

**通常不需要伴生托管程序集**：`CharacterRequiresCompanion` 只在场景根带 meta
`mod_character_script_binding = "CompanionOnly"` 时为真。复用原版 `.cs` ⇒ `runtimeAssembly` 留空即可
（`TryInstantiateEffectiveCharacter` 会失败并**回退**到 `GetChacraterScene`，这是**正常路径，不是错误**）。

## 9. `resources` 列表必须按规范序

`ModLoader` 会比对 `XWModManifestSyncService.SyncProject` 的规范序：
**所有**非忽略文件、`OrdinalIgnoreCase` 升序
（忽略 `.uid/.import/.bak/.tmp/.pvzmodeproject/.csproj/.sln`、
目录 `.build/.git/.godot/bin/obj`、以及 `mod.json` 自身），
否则**编辑器一打开工程就重写 `mod.json`**。

⚠️ `Runtime/ModAssembly.dll` 也要一起进这个列表（它不是可推导类别，但 `SyncProject` 会算它）。

## 10. 六个包内文件一览（含外观与本地化）

| 文件 | 作用 | 走 `provides`？ |
|---|---|---|
| `Resources/Characters/Plants/<Key>/Scene/<Key>.tscn` | 主场景（唯一 Character 键源） | ✅ `Character` |
| `…/Scene/<Key>ComponentSet.tres` | 组件集（射速/弹数/散射） | ❌ 依赖 |
| `…/Sprite/<Key>.tscn` | 精灵场景（唯一 CharacterSprite 键源） | ✅ `CharacterSprite` |
| `…/Config/TowerDefensePlant<Key>.tres` | 植物配置（费用/冷却/血量） | ❌ 依赖 |
| `…/Packet/<Key>.tres` | 包内卡片镜像 | ❌ 依赖 |
| `Resources/Cards/<Key>.tres` | 卡池条目（注册键 = 文件名） | ✅ `Packet` |
| `Resources/Animations/<Key>.dat` / `.tres` / `<Key>Atlas.png` | 外观三件套（`.tres` 走 standalone） | ❌ 依赖 |
| `Localization/translations.csv` | 翻译（**仅编辑器可见**，见下） | ❌ |
| `Runtime/ModAssembly.dll` | 托管插件（只有需要时才放） | ❌（但要进 `resources` 列表） |

## 11. ⚠️ 翻译表是「编辑器专用」

`ModLoader` 里**一次** `TranslationServer.AddTranslation` 都没有 —— `translations` 清单字段只有编辑器侧
（`XWModManifestSyncService` / 多语言面板 / 校验）会读。
⇒ **游戏内植物名会显示成原始 key**（如 `TOWERDEFENSE_PLANT_XXX_NAME`）。
仍应按编辑器规范写 `Localization/translations.csv`（表头 `key,zh_CN,en_US`，键按 `OrdinalIgnoreCase` 排），
但**必须在交付说明里如实标注这个边界**。

## 12. 打包排除项

排除：`.uid` `.import` `.cs` `.csproj` `.sln` `.build/` `bin/` `obj/`
（对应 `ModExporter.ShouldPackageProjectFile`）。

⚠️ `.cs` 被排除、但 `IsExecutablePackageFile` **认**它 ⇒ 包内**绝不能**有 `.cs`，否则整包拒收。
