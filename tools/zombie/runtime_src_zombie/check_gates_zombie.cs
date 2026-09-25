// 离线复核「暴走舞王伽刚特尔投石车僵尸」的**整包闸门 + 接缝**：
// 直接调用游戏程序集里的真实函数，不启动 Godot。
// 与 runtime_src_plant/check_gates_plant.cs、runtime_src/check_gates.cs 同套路，
// 期望值换成僵尸包 + 投石车 + 运行程序集。
//
// 复核八件事：
//   1) ModLoader.InferRuntimeEntry 对包内每个路径推出的 (category, key)；
//   2) XWModManifest.Load 读回真 mod.json 后，runtime* 四字段 / id / provides 是否合规；
//   3) ModLoader.ValidateDeclaredPackageExecutables（private，反射调）正向 + 负向对照；
//   4) XWModRuntimeCompatibility.ValidatePackage（若存在）；
//   5) XWModManifestSyncService.SyncProject 在工程副本上跑，必须返回 false（编辑器不会重写 mod.json）；
//   6) **入口类型本身**：ModAssembly.dll 里的 DiscoGargantuarPultRuntimeEntry
//      必须 public / 非嵌套 / 有无参构造 / 实现 IXWModRuntimeEntry / FullName == manifest 声明；
//   7) 插件用到的**游戏侧接缝**（反射 + 字符串访问，编译器管不到，改版后会静默失效）：
//      CatapultComponent.OnFireEvent、TowerDefenseGroundItemBase.characterNode / OnLand /
//      GetFallTime、TowerDefenseCharacter 的 transformPoint / instance / GetGroundHeight /
//      SetLogicalGlobalPosition / SetHitpointAndScale / Hypnoses、Almanac.zombiePacketBank /
//      _zombieInitialized、TowerDefensePacketBankData.GetZombieList / GetCategory …
//   8) .tres 靠**字段名**生效的接缝：TowerDefenseZombieConfig.physique/attack/smashAttack、
//      CatapultComponentDefinition.*、FireComponentDefinition.*、AttackComponentDefinition.attackType、
//      TowerDefensePacketConfig.type/saveKey/characterConfig、CharacterComponentSet.Components …
//
// 用法: dotnet run --file check_gates_zombie.cs -- <refDir> <projDir> <pmodPath> <entryTypeFullName>
using System;
using System.Collections.Generic;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;

int exit = 0;
void Check(bool ok, string label, string detail = "")
{
    Console.WriteLine((ok ? "  PASS  " : "  FAIL  ") + label + (detail.Length > 0 ? "  :: " + detail : ""));
    if (!ok) exit = 1;
}
void Note(string s) => Console.WriteLine("  ..     " + s);
void Skip(string s) => Console.WriteLine("  SKIP   " + s);

// ⚠️ 不要用 Type.GetMethod(name, flags)：多个重载会抛 AmbiguousMatchException。
//    统一走「按名字取全部成员再筛参数个数」，这类离线探针才能稳定复用。
MethodInfo M(Type t, string name, int argc = -1)
{
    if (t == null) return null;
    return t.GetMethods(BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static)
            .FirstOrDefault(m => m.Name == name && (argc < 0 || m.GetParameters().Length == argc));
}
bool HasMember(Type t, string name)
{
    if (t == null) return false;
    return t.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static) != null
        || t.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static) != null;
}
// Godot 的 .tres 属性名对「public 字段」和「public 属性」都成立：
// 字段（含 `_x` 私有字段 + 生成属性）与属性在 ClassDB 里都变成一个同名属性。
// 所以这里只断言「public 字段或属性存在」，并回报它到底是什么，别把字段当唯一形态。
string Kind(Type t, string name)
{
    if (t == null) return "<无类型>";
    if (t.GetField(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static) != null) return "字段";
    if (t.GetProperty(name, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static) != null) return "属性";
    return "<缺失>";
}

string refDir = args.Length > 0 ? args[0] : "";
string projDir = args.Length > 1 ? args[1] : "";
string pmodPath = args.Length > 2 ? args[2] : "";
string entryName = args.Length > 3 ? args[3] : "";
const string KEY = "ZombieDiscoGargantuarPult";
const string MODID = "discogargantuarpult";

Console.WriteLine("refDir    = " + refDir);
Console.WriteLine("projDir   = " + projDir);
Console.WriteLine("pmod      = " + pmodPath);
Console.WriteLine("entryType = " + entryName);
Console.WriteLine();

var alc = new AssemblyLoadContext("gateCheckZombie", isCollectible: false);
alc.Resolving += (ctx, name) =>
{
    string p = Path.Combine(refDir, name.Name + ".dll");
    return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
};
Assembly game = alc.LoadFromAssemblyPath(Path.Combine(refDir, "PlantsVsZombies.dll"));
alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));

Type modLoader = game.GetType("PVZHE.ModEditor.ModSystem.ModLoader", throwOnError: false);
Type manType = game.GetType("PVZHE.ModEditor.ModSystem.XWModManifest", throwOnError: false);
Type syncType = game.GetType("PVZHE.ModEditor.ModSystem.XWModManifestSyncService", throwOnError: false);
Type compatType = game.GetType("PVZHE.ModEditor.ModSystem.XWModRuntimeCompatibility", throwOnError: false);
Type entryIface = game.GetType("PVZHE.ModEditor.ModSystem.IXWModRuntimeEntry", throwOnError: false);
Check(modLoader != null && manType != null && syncType != null,
    "找到 ModLoader / XWModManifest / XWModManifestSyncService");
Check(entryIface != null, "找到 IXWModRuntimeEntry 接口",
    entryIface == null ? "<缺失>" : entryIface.FullName);

// ---------------- 1) InferRuntimeEntry ----------------
if (modLoader != null)
{
    MethodInfo infer = modLoader.GetMethod("InferRuntimeEntry",
        BindingFlags.Public | BindingFlags.Static, null,
        new[] { typeof(string), typeof(string).MakeByRefType(), typeof(string).MakeByRefType() }, null);
    Check(infer != null, "ModLoader.InferRuntimeEntry(string,out,out) 可调用");

    var expects = new (string path, bool ok, string cat, string key)[]
    {
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPult.tscn",   true,  "Character",       KEY),
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Sprite/ZombieDiscoGargantuarPult.tscn",  true,  "CharacterSprite", KEY),
        ("Resources/Cards/ZombieDiscoGargantuarPult.tres",                                                true,  "Packet",          KEY),
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPultComponentSet.tres", false, "", ""),
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Scene/ZombieDiscoGargantuarPultFireComponentDefinition.tres", false, "", ""),
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Config/TowerDefenseZombieDiscoGargantuarPult.tres", false, "", ""),
        ("Resources/Characters/Zombies/ZombieDiscoGargantuarPult/Packet/ZombieDiscoGargantuarPult.tres",  false, "", ""),
        ("Runtime/ModAssembly.dll",                                                                       false, "", ""),
        ("mod.json",                                                                                      false, "", ""),
    };
    foreach (var (path, ok, cat, key) in expects)
    {
        object[] a = { path, null, null };
        bool got;
        string gc = "", gk = "";
        try
        {
            got = (bool)infer.Invoke(null, a);
            gc = (string)(a[1] ?? ""); gk = (string)(a[2] ?? "");
        }
        catch (Exception ex)
        {
            Check(false, "InferRuntimeEntry(" + path + ")", ex.GetBaseException().Message);
            continue;
        }
        if (ok)
            Check(got && gc == cat && gk == key,
                "InferRuntimeEntry(" + path + ") == (" + cat + ", " + key + ")",
                got ? "(" + gc + ", " + gk + ")" : "返回 false（会被判 unsupported）");
        else
            Check(!got,
                "InferRuntimeEntry(" + path + ") == false（不作资源条目，靠包依赖/运行时分支放行）",
                got ? "却得到 (" + gc + ", " + gk + ")" : "");
    }
}

// ---------------- 2) XWModManifest.Load ----------------
object manifest = null;
string manifestPath = Path.Combine(projDir, "mod.json");
if (manType != null && File.Exists(manifestPath))
{
    try
    {
        manifest = manType.GetMethod("Load", BindingFlags.Public | BindingFlags.Static)
                          .Invoke(null, new object[] { manifestPath });
    }
    catch (Exception ex) { Check(false, "XWModManifest.Load 未抛异常", ex.GetBaseException().Message); }
    Check(manifest != null, "XWModManifest.Load 成功解析工程内 mod.json");

    if (manifest != null)
    {
        string Str(string prop) => (string)manType.GetProperty(prop).GetValue(manifest) ?? "";
        int Int(string prop) => (int)manType.GetProperty(prop).GetValue(manifest);

        Check(Str("RuntimeAssembly") == "Runtime/ModAssembly.dll",
            "RuntimeAssembly == \"Runtime/ModAssembly.dll\"（ModLoader 只认这个字面量）", Str("RuntimeAssembly"));
        Check(Str("RuntimeEntryType") == entryName, "RuntimeEntryType == " + entryName, Str("RuntimeEntryType"));
        Check(Int("RuntimeApiVersion") == 1, "RuntimeApiVersion == 1", Int("RuntimeApiVersion").ToString());
        Check(Str("RuntimeAssemblyPolicy") == "optional",
            "RuntimeAssemblyPolicy == optional", Str("RuntimeAssemblyPolicy"));
        Check(Str("Id") == MODID, "Id == " + MODID, Str("Id"));
        Check(Int("SchemaVersion") == 2, "SchemaVersion == 2", Int("SchemaVersion").ToString());

        var provides = (Dictionary<string, List<string>>)manType.GetProperty("Provides").GetValue(manifest);
        bool pchar = provides.TryGetValue("Character", out var vc) && vc.Contains(KEY);
        bool pspr = provides.TryGetValue("CharacterSprite", out var vs) && vs.Contains(KEY);
        bool ppkt = provides.TryGetValue("Packet", out var vp) && vp.Contains(KEY);
        Check(pchar && pspr && ppkt, "provides 同时声明 Character / CharacterSprite / Packet：" + KEY,
            string.Join(" | ", provides.Keys));

        var overrides = (Dictionary<string, List<string>>)manType.GetProperty("Overrides").GetValue(manifest);
        Check(overrides.Count == 0, "overrides 为空（不覆盖任何内置资源）", overrides.Count + " 项");

        var trans = (List<string>)manType.GetProperty("Translations").GetValue(manifest);
        Check(trans.Count == 0, "translations 为空表（显示名直接写中文）", trans.Count + " 项");

        bool required = (bool)manType.GetMethod("IsRuntimeAssemblyRequired").Invoke(manifest, null);
        Check(!required, "IsRuntimeAssemblyRequired() == false（policy=optional，加载失败不毁整包）");
    }
}

// ---------------- 3) ValidateDeclaredPackageExecutables ----------------
List<string> pmodEntries = new List<string>();
if (File.Exists(pmodPath))
{
    using var zip = ZipFile.OpenRead(pmodPath);
    pmodEntries = zip.Entries.Select(e => e.FullName.Replace('\\', '/')).ToList();
    Check(pmodEntries.Count > 0, "读到 pmod 条目清单", pmodEntries.Count + " 条");
    Check(pmodEntries.Contains("Runtime/ModAssembly.dll"), "pmod 内含 Runtime/ModAssembly.dll");
    Check(pmodEntries[0] == "mod.json", "pmod 条目 0 是 mod.json", pmodEntries[0]);
    Check(pmodEntries.Contains($"Resources/Cards/{KEY}.tres"), "pmod 内含注册卡片 Resources/Cards/" + KEY + ".tres");
    Check(pmodEntries.Contains($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}.tscn"), "pmod 内含角色场景（6 段）");
    Check(pmodEntries.Contains($"Resources/Characters/Zombies/{KEY}/Sprite/{KEY}.tscn"), "pmod 内含角色精灵场景（6 段）");
    Check(!pmodEntries.Any(e => e.EndsWith(".cs")), "pmod 内不含任何 .cs（角色包不许带脚本源码）");
    Check(!pmodEntries.Any(e => e.EndsWith(".pvzmodeproject")), "pmod 内不含 .pvzmodeproject（工程标记不进包）");
}

if (modLoader != null && manifest != null && pmodEntries.Count > 0)
{
    MethodInfo vde = modLoader.GetMethod("ValidateDeclaredPackageExecutables",
        BindingFlags.NonPublic | BindingFlags.Static);
    Check(vde != null, "找到 ModLoader.ValidateDeclaredPackageExecutables（private static）");
    if (vde != null)
    {
        string Ex(Exception e) => e.GetBaseException().Message;
        try
        {
            vde.Invoke(null, new object[] { manifest, pmodEntries });
            Check(true, "真实包条目通过 ValidateDeclaredPackageExecutables（无未声明可执行文件）");
        }
        catch (Exception ex) { Check(false, "真实包条目通过 ValidateDeclaredPackageExecutables", Ex(ex)); }

        var bad = new List<string>(pmodEntries) { "Runtime/Evil.dll" };
        bool threw = false; string badMsg = "";
        try { vde.Invoke(null, new object[] { manifest, bad }); }
        catch (Exception ex) { threw = true; badMsg = Ex(ex); }
        Check(threw, "负向对照：Runtime/Evil.dll 被拒（整包 fail-closed）", badMsg);

        var bad2 = new List<string>(pmodEntries) { "Resources/Characters/Zombies/" + KEY + "/Scene/Extra.cs" };
        bool threw2 = false; string badMsg2 = "";
        try { vde.Invoke(null, new object[] { manifest, bad2 }); }
        catch (Exception ex) { threw2 = true; badMsg2 = Ex(ex); }
        Check(threw2, "负向对照：包内多一个 .cs 被拒", badMsg2);
    }
}

// ---------------- 4) XWModRuntimeCompatibility.ValidatePackage ----------------
if (compatType != null && manifest != null)
{
    MethodInfo vp = compatType.GetMethod("ValidatePackage", BindingFlags.Public | BindingFlags.Static);
    Check(vp != null, "找到 XWModRuntimeCompatibility.ValidatePackage");
    if (vp != null)
    {
        object[] a = { manifest, null };
        bool ok;
        try { ok = (bool)vp.Invoke(null, a); }
        catch (Exception ex) { ok = false; Note("ValidatePackage 抛：" + ex.GetBaseException().Message); }
        Check(ok, "XWModRuntimeCompatibility.ValidatePackage 通过", (string)(a[1] ?? ""));
    }
}
else
{
    Skip("XWModRuntimeCompatibility 不存在或 manifest 未加载 —— 跳过");
}

// ---------------- 5) SyncProject 幂等（在副本上跑，绝不动真工程） ----------------
if (syncType != null && manifest != null)
{
    string tmp = Path.Combine(Path.GetTempPath(), "xwmod_sync_zombie_" + Guid.NewGuid().ToString("N").Substring(0, 8));
    try
    {
        // 只复制 SyncProject 会在意的文件：mod.json + 全部 resources + 全部 translations。
        // ⚠️ translations 必须一起复制：SyncProject 把 Localization/*.csv 归到 translations 段，
        //    副本里没有该文件时它会把 manifest.translations 重写掉（本包为空，但仍按通用写法处理）。
        Directory.CreateDirectory(tmp);
        var resources = (List<string>)manType.GetProperty("Resources").GetValue(manifest);
        var translations = (List<string>)manType.GetProperty("Translations").GetValue(manifest) ?? new List<string>();
        foreach (string rel in new[] { "mod.json" }.Concat(resources).Concat(translations))
        {
            string src = Path.Combine(projDir, rel.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(src)) { Note("副本缺少 " + rel); continue; }
            string dst = Path.Combine(tmp, rel.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(dst)!);
            File.Copy(src, dst, true);
        }
        byte[] before = File.ReadAllBytes(Path.Combine(tmp, "mod.json"));

        bool changed = (bool)syncType.GetMethod("SyncProject", BindingFlags.Public | BindingFlags.Static)
                                   .Invoke(null, new object[] { tmp });

        byte[] after = File.ReadAllBytes(Path.Combine(tmp, "mod.json"));
        Check(!changed, "SyncProject 返回 false → 编辑器打开工程**不会**重写 mod.json");
        Check(before.AsSpan().SequenceEqual(after), "mod.json 字节在 SyncProject 前后完全一致");
        if (changed)
            Note("被改写后的 mod.json:\n" + File.ReadAllText(Path.Combine(tmp, "mod.json")));
    }
    catch (Exception ex)
    {
        Check(false, "SyncProject 探针未抛异常", ex.GetBaseException().Message);
    }
    finally
    {
        try { if (Directory.Exists(tmp)) Directory.Delete(tmp, true); } catch { }
    }
}

// ---------------- 6) 入口类型本身（ModAssembly.dll） ----------------
Console.WriteLine();
Console.WriteLine("--- 6) 托管入口类型 ---");
string dllPath = Path.Combine(projDir, "Runtime", "ModAssembly.dll");
if (File.Exists(dllPath) && entryName.Length > 0)
{
    Type entry = null;
    try
    {
        Assembly modAsm = alc.LoadFromAssemblyPath(Path.GetFullPath(dllPath));
        entry = modAsm.GetType(entryName, throwOnError: false);
        Check(entry != null, "ModAssembly.dll 里找到类型 " + entryName,
            entry == null ? "实际类型：" + string.Join(",", modAsm.GetTypes().Select(t => t.FullName)) : "");
    }
    catch (Exception ex) { Check(false, "加载 ModAssembly.dll", ex.GetBaseException().Message); }

    if (entry != null)
    {
        Check(entry.IsPublic, "入口类型是 public");
        Check(!entry.IsNested, "入口类型是非嵌套类型（嵌套类型的 FullName 带 '+'，等于 runtimeEntryType 才对）");
        Check(entry.FullName == entryName, "入口类型 FullName == runtimeEntryType", entry.FullName);
        Check(entry.GetConstructor(Type.EmptyTypes) != null, "入口类型有公开无参构造");
        Check(entry.IsClass && !entry.IsAbstract, "入口类型是具体类");
        if (entryIface != null)
            Check(entryIface.IsAssignableFrom(entry), "入口类型实现了 IXWModRuntimeEntry");
        foreach (string m in new[] { "Initialize", "OnAllModsLoaded", "Shutdown" })
        {
            Check(M(entry, m, 1) != null || M(entry, m, 0) != null,
                "入口类型有 public 实例方法 " + m);
        }
    }
}
else
{
    Skip("ModAssembly.dll 不存在或未传 entryType —— 跳过");
}

// ---------------- 7) 插件依赖的运行时接缝 ----------------
Console.WriteLine();
Console.WriteLine("--- 7) 插件依赖的运行时接缝（反射 / 字符串访问）---");

Type catapultType = game.GetType("CatapultComponent", throwOnError: false);
Type groundItemType = game.GetType("TowerDefenseGroundItemBase", throwOnError: false);
Type charType = game.GetType("TowerDefenseCharacter", throwOnError: false);
Type charInstType = game.GetType("TowerDefenseCharacterInstance", throwOnError: false);
Type almanacType = game.GetType("Almanac", throwOnError: false);
Type bankDataType = game.GetType("TowerDefensePacketBankData", throwOnError: false);
Type resType = game.GetType("ResourceManager", throwOnError: false);
Type mgrType = game.GetType("TowerDefenseManager", throwOnError: false);
Type zombieBase = game.GetType("TowerDefenseZombie", throwOnError: false);
Type pktCfgType = game.GetType("TowerDefensePacketConfig", throwOnError: false);

Check(catapultType != null, "找到 CatapultComponent");
if (catapultType != null)
{
    EventInfo fire = catapultType.GetEvent("OnFireEvent", BindingFlags.Instance | BindingFlags.Public);
    Check(fire != null, "CatapultComponent.OnFireEvent 是 public 实例事件（插件靠它领票）",
        fire == null ? "<缺失> ⇒ 投掷替换不会触发" : fire.EventHandlerType.Name);
    Check(M(catapultType, "OnFireAnimeEvent") != null,
        "CatapultComponent.OnFireAnimeEvent() 是 public（游戏在 AnimeEvent(\"fire\") 里调它）");
    Check(M(catapultType, "OnDamagePoint") != null,
        "CatapultComponent.OnDamagePoint(string) 是 public（碾压血线触发减速+冒烟）");
}

Check(groundItemType != null, "找到 TowerDefenseGroundItemBase");
if (groundItemType != null)
{
    FieldInfo cn = groundItemType.GetField("characterNode", BindingFlags.Static | BindingFlags.Public);
    Check(cn != null, "TowerDefenseGroundItemBase.characterNode 是 public static 字段"
        + "（ImpSpawn 把投掷物 AddChild 到这里 ⇒ 插件监听它的 child_entered_tree）",
        cn == null ? "<缺失> ⇒ 换不到投掷单位" : cn.FieldType.Name);

    EventInfo land = groundItemType.GetEvent("OnLand", BindingFlags.Instance | BindingFlags.Public);
    Check(land != null, "TowerDefenseGroundItemBase.OnLand 是 public 实例事件（落地后 Walk）",
        land == null ? "<缺失> ⇒ 只能靠保险丝兜底" : land.EventHandlerType.Name);

    Check(M(groundItemType, "GetFallTime", 0) != null,
        "TowerDefenseGroundItemBase.GetFallTime() 无参可调（Tween 时长 = 与内置一致的落地时间）");
}

Check(charType != null, "找到 TowerDefenseCharacter");
if (charType != null)
{
    Check(HasMember(charType, "transformPoint"),
        "TowerDefenseCharacter.transformPoint 是 public 成员（抄缩放用）");
    Check(HasMember(charType, "instance"),
        "TowerDefenseCharacter.instance 是 public 成员（抄 hitpointScale / hypnoses）");
    Check(HasMember(charType, "componentManager"),
        "TowerDefenseCharacter.componentManager 是 public 成员");
    Check(HasMember(charType, "config"),
        "TowerDefenseCharacter.config 是 public 成员（插件靠 config.name 认人）");
    Check(HasMember(charType, "invisible"),
        "TowerDefenseCharacter.invisible 是 public 成员（SetDeferred(\"invisible\", …) 要它可写）");
    foreach (var (m, argc) in new[] { ("SetLogicalGlobalPosition", 1), ("GetLogicalGlobalPosition", 0),
                                      ("GetGroundHeight", 1), ("SetHitpointAndScale", 2) })
    {
        Check(M(charType, m, argc) != null,
            "TowerDefenseCharacter." + m + "(" + argc + " 参) 是 public 方法");
    }
    // ⚠️ Hypnoses 带可选参数（`Hypnoses(double time = -1.0, bool canFliter = true, …)`）
    //    ⇒ 源码里 `imp.Hypnoses()` 能编译，但反射按 0 参查是**查不到**的，只能按名字查。
    Check(M(charType, "Hypnoses") != null,
        "TowerDefenseCharacter.Hypnoses(...) 是 public 方法（带默认参数，无参调用合法）",
        M(charType, "Hypnoses") == null ? "<缺失> ⇒ 被魅惑时投掷物不会一起被魅惑"
            : M(charType, "Hypnoses").GetParameters().Length + " 个形参");
    Check(M(charType, "Idle", 0) != null, "TowerDefenseCharacter.Idle() 是 public 方法");
}

if (charInstType != null)
{
    Check(HasMember(charInstType, "hypnoses"),
        "TowerDefenseCharacterInstance.hypnoses 是 public 成员（被魅惑的投掷物也要被魅惑）");
    Check(HasMember(charInstType, "hitpointScale"),
        "TowerDefenseCharacterInstance.hitpointScale 是 public 成员（沿用小鬼的缩放）");
}

if (zombieBase != null)
{
    Check(M(zombieBase, "Walk", 0) != null,
        "TowerDefenseZombie.Walk() 是 public 虚方法（落地后 CallDeferred(\"Walk\") 的目标）");
}

if (pktCfgType != null)
{
    MethodInfo create = pktCfgType.GetMethods(BindingFlags.Instance | BindingFlags.Public)
        .FirstOrDefault(m => m.Name == "Create" && m.GetParameters().Length >= 3
            && m.GetParameters()[0].ParameterType.Name == "Vector2"
            && m.GetParameters()[1].ParameterType.Name == "Vector2I");
    Check(create != null, "TowerDefensePacketConfig.Create(Vector2, Vector2I, double?, …) 存在"
        + "（插件用它生成暴走舞王伽刚特尔）");
}

if (mgrType != null)
{
    Check(M(mgrType, "GetPacketConfig", 1) != null,
        "TowerDefenseManager.GetPacketConfig(string) 存在");
    Check(M(mgrType, "GetPacketBankData", 1) != null,
        "TowerDefenseManager.GetPacketBankData(string) 存在（图鉴僵尸页取 GeneralZombie 的入口）");
    Check(M(mgrType, "GetMapCellPos", 1) != null,
        "TowerDefenseManager.GetMapCellPos(Vector2I) 存在（落点第 3~5 列换算）");
}

if (resType != null)
{
    Check(HasMember(resType, "TOWERDEFENSE_PACKETBANKS"),
        "ResourceManager.TOWERDEFENSE_PACKETBANKS 是 public 成员（补卡库的入口）");
    Check(HasMember(resType, "TOWERDEFENSE_CHARCATERS"),
        "ResourceManager.TOWERDEFENSE_CHARCATERS 是 public 成员");
    Check(HasMember(resType, "CHARCTAER_SPRITE"),
        "ResourceManager.CHARCTAER_SPRITE 是 public 成员（XWModContentValidation:35 用的）");
}

if (bankDataType != null)
{
    Check(HasMember(bankDataType, "category"),
        "TowerDefensePacketBankData.category 是 public 成员");
    Check(M(bankDataType, "GetZombieList", 0) != null,
        "TowerDefensePacketBankData.GetZombieList() 存在");
    Check(M(bankDataType, "GetCategory", 1) != null,
        "TowerDefensePacketBankData.GetCategory(string) 存在（列卡走的那个数组）");
}

if (almanacType != null)
{
    FieldInfo zpb = almanacType.GetField("zombiePacketBank", BindingFlags.Instance | BindingFlags.Public);
    Check(zpb != null && zpb.FieldType == bankDataType,
        "Almanac.zombiePacketBank 是 public 字段且类型为 TowerDefensePacketBankData",
        zpb == null ? "<缺失>" : zpb.FieldType.Name);
    FieldInfo zi = almanacType.GetField("_zombieInitialized", BindingFlags.Instance | BindingFlags.NonPublic);
    Check(zi != null && zi.FieldType == typeof(bool),
        "Almanac._zombieInitialized 是 private bool 字段（插件反射刷新的开关）",
        zi == null ? "<缺失> ⇒ 插件退化为「不刷新僵尸页」" : zi.FieldType.Name);
    Check(M(almanacType, "InitZombie", 0) != null,
        "Almanac.InitZombie() 是 public 方法（僵尸页已打开时主动刷新）");
    Check(M(almanacType, "InitPlant", 0) != null,
        "Almanac.InitPlant() 仍在（反向对照：僵尸侧不能误用植物页入口）");
}

// ---------------- 8) .tres / .tscn 靠字段名生效的接缝 ----------------
Console.WriteLine();
Console.WriteLine("--- 8) 资源字段名接缝（改名会静默回落默认值，编译器管不到）---");

Type zCfgType = game.GetType("TowerDefenseZombieConfig", throwOnError: false);
Check(zCfgType != null, "找到 TowerDefenseZombieConfig");
if (zCfgType != null)
{
    foreach (string f in new[] { "physique", "attack", "smashAttack", "weight", "wavePointCost",
                                 "canSpawnPlantfood", "excludeLineGridType", "spawnLineNeed" })
    {
        Check(HasMember(zCfgType, f),
            "TowerDefenseZombieConfig." + f + " 是 public 成员（tres 里写了它）", Kind(zCfgType, f));
    }
    // 基类上的（tres 里也写了）
    Type cCfg = game.GetType("TowerDefenseCharacterConfig", throwOnError: false);
    foreach (string f in new[] { "name", "hitpoints", "hitpointsNearDeath", "damagePointData",
                                 "homeWorld", "cost", "packetCooldown", "plantGridType",
                                 "collisionFlags", "maskFlags", "physiqueTypeFlags" })
    {
        Check(HasMember(cCfg, f),
            "TowerDefenseCharacterConfig." + f + " 是 public 成员（tres 里写了它）", Kind(cCfg, f));
    }
}

Type catDefType = game.GetType("CatapultComponentDefinition", throwOnError: false);
Check(catDefType != null, "找到 CatapultComponentDefinition");
if (catDefType != null)
{
    foreach (string f in new[] { "projectileNum", "projectileName", "useCanFireCheck",
                                 "explosionEffect", "smokeParticlePath", "fireSlotPath",
                                 "speedDamagePointName", "showSmokeOnSpeedDamage" })
    {
        Check(HasMember(catDefType, f),
            "CatapultComponentDefinition." + f + " 是 public 成员", Kind(catDefType, f));
    }
}

Type atkDefType = game.GetType("AttackComponentDefinition", throwOnError: false);
Check(atkDefType != null, "找到 AttackComponentDefinition");
if (atkDefType != null)
{
    foreach (string f in new[] { "attackType", "useParentHitBox", "useCheckAreaGridColumn", "checkLine", "checkVase" })
    {
        Check(HasMember(atkDefType, f),
            "AttackComponentDefinition." + f + " 是 public 成员（attackType = \"Smash\" 就靠它）", Kind(atkDefType, f));
    }
}

Type fireDefType = game.GetType("FireComponentDefinition", throwOnError: false);
Check(fireDefType != null, "找到 FireComponentDefinition");
if (fireDefType != null)
{
    // ⚠️ 这几个在源码里是 `public ... { get; set; }` **属性**（不是字段），
    //    .tres 里的属性名照样成立 ⇒ 必须用「字段或属性」判定，别只查字段。
    foreach (string f in new[] { "firePosMarkerPaths", "checkShapeResources", "fireInterval",
                                 "fireCheckList", "fireProjectileList", "checkHeight", "catapultFirstFar" })
    {
        Check(HasMember(fireDefType, f),
            "FireComponentDefinition." + f + " 是 public 成员", Kind(fireDefType, f));
    }
}

Type compSetType = game.GetType("CharacterComponentSet", throwOnError: false);
Check(compSetType != null, "找到 CharacterComponentSet");
if (compSetType != null)
{
    // ⚠️ ParentSet / Components / RemovedInstanceIds 也是**属性**（`public X { get; set; }`）。
    foreach (string f in new[] { "ParentSet", "Components", "RemovedInstanceIds" })
    {
        Check(HasMember(compSetType, f),
            "CharacterComponentSet." + f + " 是 public 成员", Kind(compSetType, f));
    }
}

if (pktCfgType != null)
{
    foreach (string f in new[] { "saveKey", "unlockCheckList", "name", "describe",
                                 "handbookDescribe", "handbookStory", "packetAnimeOffset",
                                 "packetAnimeScale", "type", "canChangeCost" })
    {
        Check(HasMember(pktCfgType, f),
            "TowerDefensePacketConfig." + f + " 是 public 成员", Kind(pktCfgType, f));
    }
}

// 枚举值：type = 6 必须是 ZOMBIE；attackType "Smash" 必须是合法枚举名
Type enumType = game.GetType("TowerDefenseEnum", throwOnError: false);
if (enumType != null)
{
    Type pt = enumType.GetNestedType("PACKET_TYPE", BindingFlags.Public);
    Check(pt != null, "找到 TowerDefenseEnum.PACKET_TYPE");
    if (pt != null)
    {
        string[] names = Enum.GetNames(pt);
        int idx = Array.IndexOf(names, "ZOMBIE");
        Check(idx >= 0, "PACKET_TYPE.ZOMBIE 存在", string.Join(",", names));
        if (idx >= 0)
            Check(Convert.ToInt32(Enum.Parse(pt, "ZOMBIE")) == 6,
                "PACKET_TYPE.ZOMBIE == 6（卡片里写的就是 type = 6）",
                Convert.ToInt32(Enum.Parse(pt, "ZOMBIE")).ToString());
    }
}

Console.WriteLine();
Console.WriteLine(exit == 0 ? "全部通过 ✓" : "存在失败 ✗");
return exit;
