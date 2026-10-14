# settings 声明离线校验工具

**不启动游戏**就能验 `mod.json` 里的 `settings` 声明是否合法。

## 为什么需要它

游戏 0.30.0 的 Mod 配置面板对 `settings` 有一堆硬性要求（`enum` 必须有非空且不重复的 `options`、`key` 不能空/重复/带首尾空白 …）。
这些错误**只有打开游戏、进到 Mod 管理界面才会发现** —— 而每次验证都要装机 + 重启，代价很高。

本工具把**宿主自己的校验器**跑一遍：反射调用
`PVZHE.ModEditor.ModSystem.XWModSettingsService.ValidateDefinitions(XWModManifest, out string error)`，
所以校验规则永远是宿主那一份，**不会出现"工具说没问题、游戏说不合法"的漂移**。

## 用法

```powershell
# 宿主目录 = 含 PlantsVsZombies.dll 的目录
$HOST = "<游戏目录>\data_PlantsVsZombies_windows_x86_64"

# 单个
dotnet pvz-hybrid-mod-skills\tools\settings-validate\bin\Release\ValidateSettings.dll $HOST mods\FpsDisplay\mod.json

# 批量（也可直接验 .pmod，工具会自己读包里的根 mod.json）
dotnet ...\ValidateSettings.dll $HOST mods\*\dist\*.pmod
```

首次使用前构建一次（**零第三方依赖，离线可构建**，约 3 秒）：

```powershell
dotnet build pvz-hybrid-mod-skills\tools\settings-validate\ValidateSettings.csproj -c Release -o pvz-hybrid-mod-skills\tools\settings-validate\bin\Release --nologo
```

## 输出与退出码

```
  <路径>  OK    settings 声明通过（4 项）
  <路径>  FAIL  Mod 'fixture-bad' 配置 'corner'：选项必须包含不重复的有效值。
```

| 退出码 | 含义 |
|---|---|
| 0 | 全部通过 |
| 1 | 有声明不合法（不是环境问题） |
| 2 | 环境/用法问题（宿主目录错、宿主太旧没有这套 API、文件不存在…） |

## 自测（负向测试）

`fixtures/` 下三个夹具，用来证明闸门**真的会拦**，而不是永远输出 OK：

| 夹具 | 期望 |
|---|---|
| `ok.json` | OK —— bool + enum(带 options) + int(min/max/step) + text 展示项 + `visibleWhen` |
| `bad-enum-no-options.json` | FAIL —— `enum` 的 `options` 为空（宿主要求非空） |
| `bad-duplicate-key.json` | FAIL —— 两个设置项用同一个 `key` |

```powershell
$T = "pvz-hybrid-mod-skills\tools\settings-validate"
dotnet $T\bin\Release\ValidateSettings.dll "<宿主目录>" $T\fixtures\ok.json $T\fixtures\bad-enum-no-options.json $T\fixtures\bad-duplicate-key.json
# 期望：ok 那行 OK、另两行 FAIL，退出码 1
```

**实测结果（2026-10-09，0.30.0）**：

```
ok.json                   OK    settings 声明通过（4 项）
bad-enum-no-options.json  FAIL  Mod 'fixture-bad' 配置 'corner'：选项必须包含不重复的有效值。
bad-duplicate-key.json    FAIL  Mod 'fixture-dup' 配置 'a'：配置键为空、含首尾空白或重复。
```

## 注意

- 本工具**在 0.29.0 上会以退出码 2 失败** —— 那时宿主里没有 `XWModSettingsService`（Mod 配置面板是 0.30.0 才有的）。
- 它只校验**声明**，不校验运行时代码读配置的方式（`Get<T>` 的类型是否对得上等），那部分靠装机实测。
