// 离线复核「超级机枪读报僵尸」的**整包闸门 + 接缝 + 事实依据**：
// 直接调用游戏程序集里的真实函数 + 直接读解包源码树做事实断言，**不启动 Godot**。
// 与 runtime_src/check_gates.cs、runtime_src_plant/check_gates_plant.cs、
// runtime_src_zombie/check_gates_zombie.cs 同套路，期望值换成本包。
//
// 复核九件事：
//   1) ModLoader.InferRuntimeEntry 对包内每个路径推出的 (category, key)；
//   2) XWModManifest.Load 读回真 mod.json 后，runtime* 四字段 / id / provides 是否合规；
//   3) ModLoader.ValidateDeclaredPackageExecutables（private，反射调）正向 + 负向对照；
//   4) XWModRuntimeCompatibility.ValidatePackage；
//   5) XWModManifestSyncService.SyncProject 在工程副本上跑，必须返回 false（编辑器不会重写 mod.json）；
//   6) **入口类型本身**：ModAssembly.dll 里的 SuperGatlingPaperRuntimeEntry
//      必须 public / 非嵌套 / 有无参构造 / 实现 IXWModRuntimeEntry / FullName == manifest 声明；
//   7) 插件用到的**游戏侧接缝**（反射，编译器管不到，改版后会静默失效）：
//      FireComponent.Fire / CanExecuteGameplay / fireProjectileList / _fireProjectiles /
//      RefreshExportedArrayCaches / fireAudioName / IsReleased / Owner、
//      TowerDefenseCharacter.config / componentManager、ComponentManager.GetRuntime、
//      ResourceManager.TOWERDEFENSE_PACKETBANKS、TowerDefensePacketBankData.category / GetCategory、
//      Almanac.zombiePacketBank / InitZombie …
//   8) .tres 靠**字段名**生效的接缝：TowerDefenseZombieConfig / TowerDefenseCharacterConfig /
//      FireComponentDefinition / FireComponentFireProjectileConfig / CharacterComponentSet /
//      TowerDefensePacketConfig / CharacterArmorData / ArmorSlotConfig / TowerDefenseArmorTypeData，
//      以及「PACKET_TYPE.ZOMBIE == 6」「ARMOR_METHOD_FLAGS.SHIELD == 4」两个枚举事实。
//   9) **读解包源码树核对需求依据**（不信任先前的口头结论）：
//      · Paper 的 armorMethodFlags 必须真的带 SHIELD 位（= 二类护具层）；
//      · ArmorRegistry.json 必须真的把 "Paper" 指到那份 tres；
//      · 内置读报僵尸脚本必须真的有 `ToGasp` + `timeScaleInit = 3.0`（需求 6 就是它）；
//      · 内置普通僵尸与读报僵尸都**不覆盖** walkSpeedScale（需求 5「移速 = 普通僵尸」）；
//      · 父组件集里的 AttackComponentZombieDefinition **不写** attackType ⇒ 默认 "Eat"（啃食）；
//      · 内置发射配置只有 8 个字段、**没有**任何概率/时窗字段（需求 4 必须走插件的铁证）；
//      · 本包产物里的数值逐条对得上。
//
// 用法: dotnet run --file check_gates_super_gatling_paper.cs -- <refDir> <projDir> <pmodPath> <entryTypeFullName> <gameRoot>

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

// ---- 连带 private/internal 一起找：用来查清「游戏内部到底怎么实现」，不是要去调它 ----
const BindingFlags ANY = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic;
MethodInfo MAny(Type t, string name, int argc = -1)
{
    if (t == null) return null;
    return t.GetMethods(ANY).FirstOrDefault(m => m.Name == name && (argc < 0 || m.GetParameters().Length == argc));
}
FieldInfo FAny(Type t, string name) => t?.GetField(name, ANY);
Type MemberType(Type t, string name)
{
    if (t == null) return null;
    FieldInfo f = t.GetField(name, ANY);
    if (f != null) return f.FieldType;
    return t.GetProperty(name, ANY)?.PropertyType;
}
// 泛型容器（Array<T> / List<T> / …）的元素类型；非泛型/无参返回 null。
Type ElemType(Type t)
{
    if (t == null || !t.IsGenericType) return null;
    Type[] ga = t.GetGenericArguments();
    return ga.Length >= 1 ? ga[0] : null;
}
Type MemberContainerType(Type t, string name) => MemberType(t, name);
Type MemberElementType(Type t, string name) => ElemType(MemberType(t, name));
Type FieldElementType(FieldInfo f) => f == null ? null : ElemType(f.FieldType);

string refDir = args.Length > 0 ? args[0] : "";
string projDir = args.Length > 1 ? args[1] : "";
string pmodPath = args.Length > 2 ? args[2] : "";
string entryName = args.Length > 3 ? args[3] : "";
string gameRoot = args.Length > 4 ? args[4] : "";
const string KEY = "ZombieSuperGatlingPaper";
const string MODID = "supergatlingpaper";

Console.WriteLine("refDir    = " + refDir);
Console.WriteLine("projDir   = " + projDir);
Console.WriteLine("pmod      = " + pmodPath);
Console.WriteLine("entryType = " + entryName);
Console.WriteLine("gameRoot  = " + gameRoot);
Console.WriteLine();

var alc = new AssemblyLoadContext("gateCheckSGP", isCollectible: false);
alc.Resolving += (ctx, name) =>
{
    string p = Path.Combine(refDir, name.Name + ".dll");
    return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
};
Assembly game = alc.LoadFromAssemblyPath(Path.Combine(refDir, "PlantsVsZombies.dll"));
// ⚠️ 本脚本是 `dotnet run --file` 编译的**独立程序**，编译期并没有引用 GodotSharp.dll
//    （它只在运行期由上面的 Resolving / 这里显式 LoadFromAssemblyPath 载入）。
//    ⇒ 源码里**绝不能**出现 `GodotObject` / `Node` 这类 Godot 类型的字面量，
//      需要判断类型关系时一律拿 Type 对象做反射（下面 8) 节的 IsAssignableFrom 就是）。
Assembly godotAsm = alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));

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
Console.WriteLine();
Console.WriteLine("--- 1) InferRuntimeEntry ---");
if (modLoader != null)
{
    MethodInfo infer = modLoader.GetMethod("InferRuntimeEntry",
        BindingFlags.Public | BindingFlags.Static, null,
        new[] { typeof(string), typeof(string).MakeByRefType(), typeof(string).MakeByRefType() }, null);
    Check(infer != null, "ModLoader.InferRuntimeEntry(string,out,out) 可调用");

    var expects = new (string path, bool ok, string cat, string key)[]
    {
        ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}.tscn",                                   true,  "Character",       KEY),
        ($"Resources/Characters/Zombies/{KEY}/Sprite/{KEY}.tscn",                                  true,  "CharacterSprite", KEY),
        ($"Resources/Cards/{KEY}.tres",                                                            true,  "Packet",          KEY),
        ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}ComponentSet.tres",                       false, "", ""),
        ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}FireComponentDefinition.tres",            false, "", ""),
        ($"Resources/Characters/Zombies/{KEY}/Config/TowerDefense{KEY}.tres",                      false, "", ""),
        ($"Resources/Characters/Zombies/{KEY}/Packet/{KEY}.tres",                                  false, "", ""),
        ($"Resources/Characters/Zombies/{KEY}/Armor/{KEY}ArmorData.tres",                          false, "", ""),
        ($"Resources/Characters/Zombies/{KEY}/Armor/Config/{KEY}ArmorPaper.tres",                  false, "", ""),
        ("Runtime/ModAssembly.dll",                                                                 false, "", ""),
        ("mod.json",                                                                                false, "", ""),
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
Console.WriteLine();
Console.WriteLine("--- 2) manifest ---");
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

        // resources 必须与磁盘一一对应
        var resources = (List<string>)manType.GetProperty("Resources").GetValue(manifest);
        var missing = resources.Where(r => !File.Exists(Path.Combine(projDir, r.Replace('/', Path.DirectorySeparatorChar)))).ToList();
        Check(missing.Count == 0, "manifest.resources 每一项都真实存在", missing.Count == 0 ? resources.Count + " 项" : string.Join(",", missing));
        var orderLower = resources.Select(p => p.ToLowerInvariant()).ToList();
        Check(orderLower.SequenceEqual(orderLower.OrderBy(x => x, StringComparer.Ordinal)),
            "resources 是 OrdinalIgnoreCase 升序（编辑器 SyncProject 不会再重排）");
    }
}

// ---------------- 3) ValidateDeclaredPackageExecutables ----------------
Console.WriteLine();
Console.WriteLine("--- 3) 包内可执行文件声明 ---");
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
    Check(pmodEntries.Contains($"Resources/Characters/Zombies/{KEY}/Armor/{KEY}ArmorData.tres"), "pmod 内含包内护具表");
    Check(pmodEntries.Contains($"Resources/Characters/Zombies/{KEY}/Armor/Config/{KEY}ArmorPaper.tres"), "pmod 内含包内护具槽配置");
    Check(!pmodEntries.Any(e => e.EndsWith(".cs")), "pmod 内不含任何 .cs（角色包不许带脚本源码）");
    Check(!pmodEntries.Any(e => e.EndsWith(".pvzmodeproject")), "pmod 内不含 .pvzmodeproject（工程标记不进包）");
    Check(!pmodEntries.Any(e => e.EndsWith(".scn") || e.EndsWith(".res")),
        "pmod 内不含 .scn/.res（PrepareSafeCharacterPackage 见到就整包拒绝）");
}
else
{
    Skip("pmod 不存在 —— 跳过");
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

        var bad2 = new List<string>(pmodEntries) { $"Resources/Characters/Zombies/{KEY}/Scene/Extra.cs" };
        bool threw2 = false; string badMsg2 = "";
        try { vde.Invoke(null, new object[] { manifest, bad2 }); }
        catch (Exception ex) { threw2 = true; badMsg2 = Ex(ex); }
        Check(threw2, "负向对照：包内多一个 .cs 被拒", badMsg2);
    }
}

// ---------------- 4) XWModRuntimeCompatibility.ValidatePackage ----------------
Console.WriteLine();
Console.WriteLine("--- 4) 运行时兼容性 ---");
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
Console.WriteLine();
Console.WriteLine("--- 5) SyncProject 幂等 ---");
if (syncType != null && manifest != null)
{
    string tmp = Path.Combine(Path.GetTempPath(), "xwmod_sync_sgp_" + Guid.NewGuid().ToString("N").Substring(0, 8));
    try
    {
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
        // 反例：三个回调的方法体**一律不许抛**（TryInitializeRuntimeEntry 失败 = 无条件整包回滚）。
        // 离线没法执行，只能确认它们是 public 实例方法且**都不带 throws 语义**（C# 没有 throws，
        // 所以这里改为断言它们不是 abstract / 不是泛型，且类上不带 [Obsolete]）。
        Check(!entry.IsAbstract, "入口类型不是 abstract（否则 new 不出来 ⇒ 整包回滚）");
        Check(entry.GetCustomAttributes().All(a => a.GetType().Name != "ObsoleteAttribute"),
            "入口类型没被标 [Obsolete]（标了会在宿主里变成编译期错误/警告）");

        // ★★★ 9.15b 炮口字面量 / 生成点路径（第四轮：子弹生成点对齐炮口）
        //   ⚠️ 闸门里**不能出现 Godot 类型字面量**（本脚本没编译期引用 GodotSharp）⇒
        //      读 `Vector2` 也得走反射拿 X/Y 属性。
        //   跨语言一致性（这两个字面量 ↔ 生成器 `HEAD_MUZZLE_LOCAL`）由 Python 侧
        //   `check_head_fit.py` / 生成器自检逐字比对；这里只确认字段存在且值合理。
        FieldInfo fMuzzle = entry.GetField("HeadMuzzleLocal", ANY);
        Check(fMuzzle != null,
            "★★ 插件里有炮口局部点 `HeadMuzzleLocal`（`head.GlobalTransform * 它` = 炮口世界坐标）");
        if (fMuzzle != null)
        {
            // ⚠️ Godot 的 `Vector2` 里 `X`/`Y` 是**字段**（不是属性）⇒ 字段优先、属性兜底。
            object mv = fMuzzle.GetValue(null);
            var got = new List<float>();
            foreach (string nm in new[] { "X", "Y" })
            {
                Type vt = mv?.GetType();
                FieldInfo ff = vt?.GetField(nm, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static);
                PropertyInfo pp = ff == null
                    ? vt?.GetProperty(nm, BindingFlags.Instance | BindingFlags.Public | BindingFlags.Static)
                    : null;
                if (ff != null) got.Add(Convert.ToSingle(ff.GetValue(mv)));
                else if (pp != null) got.Add(Convert.ToSingle(pp.GetValue(mv)));
            }
            if (got.Count != 2)
            {
                Check(false, "HeadMuzzleLocal 是带 X/Y 的二元量（Vector2）（字段或属性）",
                    "拿到 " + got.Count + " 个分量");
            }
            else
            {
                Check(Math.Abs(got[0] - 28.6143f) < 0.001f && Math.Abs(got[1] - 20.1485f) < 0.001f,
                    "★★ 插件 HeadMuzzleLocal ≈ (28.6143, 20.1485)"
                    + "（= 生成器 MUZZLE_POSE(88.552,30.2) + HEAD_OFFSET(-59.9377,-10.0515)）",
                    "(" + got[0] + ", " + got[1] + ")");
            }
        }
        FieldInfo fMkPath = entry.GetField("FireMarkerNodePath", ANY);
        Check(fMkPath != null && (string)fMkPath.GetValue(null) == "HeadSlot/FireMarker",
            "★ 插件里的生成点相对路径 == \"HeadSlot/FireMarker\"（与场景节点路径、.tres 里的 NodePath 一致）",
            fMkPath == null ? "字段不存在" : Convert.ToString(fMkPath.GetValue(null)));
    }
}
else
{
    Skip("ModAssembly.dll 不存在或未传 entryType —— 跳过");
}

// ---------------- 7) 插件依赖的运行时接缝 ----------------
Console.WriteLine();
Console.WriteLine("--- 7) 插件依赖的运行时接缝（反射 / 字符串访问）---");

Type fireType = game.GetType("FireComponent", throwOnError: false);
Type charType = game.GetType("TowerDefenseCharacter", throwOnError: false);
Type compMgrType = game.GetType("ComponentManager", throwOnError: false);
Type compRuntimeType = game.GetType("CharacterComponentRuntime", throwOnError: false);
Type resType = game.GetType("ResourceManager", throwOnError: false);
Type bankDataType = game.GetType("TowerDefensePacketBankData", throwOnError: false);
Type almanacType = game.GetType("Almanac", throwOnError: false);
Type fireCfgType = game.GetType("FireComponentFireProjectileConfig", throwOnError: false);

Check(fireType != null, "找到 FireComponent");
if (fireType != null)
{
    Check(M(fireType, "Fire", 0) != null,
        "FireComponent.Fire() 是 public 无参方法（插件逐颗打豌豆的唯一入口）",
        M(fireType, "Fire", 0) == null ? "<缺失> ⇒ 整门机枪打不出去" : M(fireType, "Fire", 0).IsPublic.ToString());
    Check(M(fireType, "Fire", 0) == null || M(fireType, "Fire", 0).IsPublic,
        "Fire() 是 public（不是 internal/protected）");
    Check(HasMember(fireType, "fireProjectileList"),
        "FireComponent.fireProjectileList 是 public 成员（插件改写 dir 的那张表）", Kind(fireType, "fireProjectileList"));
    Check(HasMember(fireType, "fireAudioName"),
        "FireComponent.fireAudioName 是 public 成员（大招期间置空静音）", Kind(fireType, "fireAudioName"));
    Check(HasMember(fireType, "fireInterval"),
        "FireComponent.fireInterval 是 public 成员");
    Check(HasMember(fireType, "IsReleased"),
        "FireComponent.IsReleased 可用（CharacterComponentRuntime 不是 GodotObject，判活只能靠它）",
        Kind(fireType, "IsReleased"));
    Check(HasMember(fireType, "Owner"),
        "FireComponent.Owner 可用（Owner 是 TowerDefenseCharacter，是 Node ⇒ 能 IsInstanceValid）");
    // ★ 本条是「插件改 dir 为什么立即生效」的**唯一**根据，必须查清可访问性与元素类型。
    //   源码事实（FireComponent.cs:447 / :919 / :931 / :965）：
    //     private readonly List<FireComponentFireProjectileConfig> _fireProjectiles = new …();   ← Fire() 读的是它
    //     private static void CopyGodotArray(Array<T> source, List<T> target) { … target.Add(source[i]); }  ← 逐元素同引用拷贝
    //     private void RefreshExportedArrayCaches() { … CopyGodotArray(fireProjectileList, _fireProjectiles); }
    //   ⇒ Array 与 List 的**元素是同一批对象**，但**容器不同**：
    //      改元素（cfg.dir = …）两个容器同时可见 ✅（插件靠这个）
    //      往 Array 里增减元素 list 不会变 ❌（插件因此**绝不**增删，只改现有元素）
    MethodInfo refresh = MAny(fireType, "RefreshExportedArrayCaches", 0);
    Check(refresh != null,
        "FireComponent.RefreshExportedArrayCaches() 存在（fireProjectileList → 私有 _fireProjectiles 的拷贝点）",
        refresh == null ? "<缺失>" : (refresh.IsPrivate ? "private（插件不能也不需要调它）" : "public"));
    FieldInfo privList = FAny(fireType, "_fireProjectiles");
    Type pubListElem = MemberElementType(fireType, "fireProjectileList");
    Type privListElem = FieldElementType(privList);
    Check(privList != null, "Fire() 内部的私有列表 _fireProjectiles 存在（逐发读 cfg.dir 的那张表）",
        privList == null ? "<缺失>" : privList.FieldType.FullName);
    Check(privListElem != null && pubListElem != null && privListElem == pubListElem,
        "★ public fireProjectileList 与私有 _fireProjectiles 的**元素类型相同** ⇒ 改元素两容器同时可见（插件改 dir 立即生效）",
        "pub=" + (pubListElem?.Name ?? "<无>") + " / priv=" + (privListElem?.Name ?? "<无>"));
    Check(privList != null && privList.FieldType != MemberContainerType(fireType, "fireProjectileList"),
        "★ 但两者的**容器类型不同**（Array<T> vs List<T>）⇒ 往 fireProjectileList 增删元素对 Fire() 无效，插件只改不增",
        privList == null ? "<缺失>"
            : privList.FieldType.FullName + " vs " + (MemberContainerType(fireType, "fireProjectileList")?.FullName ?? "<无>"));

    if (compRuntimeType != null)
    {
        // ★ 这里刻意**不写** `typeof(GodotObject)`：本脚本编译期没有 GodotSharp 引用（见文件头）。
        //   改成从运行期载入的 GodotSharp 程序集里取 Type，效果等价。
        Type godotObjectType = godotAsm.GetType("Godot.GodotObject", throwOnError: false);
        bool isGodotObject = godotObjectType != null && godotObjectType.IsAssignableFrom(compRuntimeType);
        Note("CharacterComponentRuntime 基类 = " + compRuntimeType.BaseType?.FullName
            + "；是否 GodotObject = " + isGodotObject);
        Check(godotObjectType != null, "GodotSharp.dll 里找到 Godot.GodotObject（反射判定的前提）",
            godotObjectType == null ? "<缺失>" : godotObjectType.FullName);
        Check(isGodotObject == false,
            "确认 CharacterComponentRuntime **不是** GodotObject（所以插件只能用 IsReleased/Owner 判活 + ReferenceEquals 去重）");
    }
}

if (charType != null)
{
    Check(HasMember(charType, "config"), "TowerDefenseCharacter.config 是 public 成员（插件靠 config.name 认人）");
    Check(HasMember(charType, "componentManager"), "TowerDefenseCharacter.componentManager 是 public 成员");
}
if (compMgrType != null)
{
    var getRuntime = M(compMgrType, "GetRuntime");
    Check(getRuntime != null, "ComponentManager.GetRuntime<T>(string) 存在（插件用它取 character.fire）",
        getRuntime == null ? "<缺失>" : "形参 " + getRuntime.GetParameters().Length + " 个");
}

if (resType != null)
{
    Check(HasMember(resType, "TOWERDEFENSE_PACKETBANKS"),
        "ResourceManager.TOWERDEFENSE_PACKETBANKS 是 public 成员（补卡库的入口）");
    Check(HasMember(resType, "TOWERDEFENSE_CHARCATERS"),
        "ResourceManager.TOWERDEFENSE_CHARCATERS 是 public 成员");
    Check(HasMember(resType, "CHARCTAER_SPRITE"),
        "ResourceManager.CHARCTAER_SPRITE 是 public 成员（XWModContentValidation 用的）");
}

if (bankDataType != null)
{
    Check(HasMember(bankDataType, "category"), "TowerDefensePacketBankData.category 是 public 成员");
    Check(M(bankDataType, "GetCategory", 1) != null,
        "TowerDefensePacketBankData.GetCategory(string) 存在（列卡走的那个数组）");
    Check(M(bankDataType, "GetZombieList", 0) != null,
        "TowerDefensePacketBankData.GetZombieList() 存在（僵尸图鉴/选卡的来源）");
}

if (almanacType != null)
{
    FieldInfo zpb = almanacType.GetField("zombiePacketBank", BindingFlags.Instance | BindingFlags.Public);
    Check(zpb != null && (bankDataType == null || zpb.FieldType == bankDataType),
        "Almanac.zombiePacketBank 是 public 字段且类型为 TowerDefensePacketBankData",
        zpb == null ? "<缺失>" : zpb.FieldType.Name);
    Check(M(almanacType, "InitZombie", 0) != null,
        "Almanac.InitZombie() 是 public 方法（僵尸页已打开时主动刷新）");
}

// ---------------- 8) .tres / .tscn 靠字段名生效的接缝 ----------------
Console.WriteLine();
Console.WriteLine("--- 8) 资源字段名接缝（改名会静默回落默认值，编译器管不到）---");

Type zCfgType = game.GetType("TowerDefenseZombieConfig", throwOnError: false);
Type cCfgType = game.GetType("TowerDefenseCharacterConfig", throwOnError: false);
Check(zCfgType != null && cCfgType != null, "找到 TowerDefenseZombieConfig / TowerDefenseCharacterConfig");
if (cCfgType != null)
{
    foreach (string f in new[] { "name", "hitpoints", "hitpointsNearDeath", "damagePointData",
                                 "armorData", "customData", "ashScene", "homeWorld", "cost",
                                 "packetCooldown", "plantGridType", "maskFlags" })
    {
        Check(HasMember(cCfgType, f),
            "TowerDefenseCharacterConfig." + f + " 是 public 成员（tres 里写了它）", Kind(cCfgType, f));
    }
    var hp = cCfgType.GetField("hitpoints", BindingFlags.Instance | BindingFlags.Public);
    Check(hp != null && hp.FieldType == typeof(double), "hitpoints 是 double 字段（写 1180.0 合法）");
    var ar = cCfgType.GetField("armorData", BindingFlags.Instance | BindingFlags.Public);
    Check(ar != null && ar.FieldType.Name == "CharacterArmorData", "armorData 的类型是 CharacterArmorData",
        ar == null ? "<缺失>" : ar.FieldType.Name);
}
if (zCfgType != null)
{
    foreach (string f in new[] { "physique", "attack", "smashAttack", "weight", "wavePointCost",
                                 "canSpawnPlantfood", "excludeLineGridType", "spawnLineNeed" })
    {
        Check(HasMember(zCfgType, f),
            "TowerDefenseZombieConfig." + f + " 是 public 成员", Kind(zCfgType, f));
    }
}

// FireComponentFireProjectileConfig：★ 这是「需求 4 只能靠插件」的铁证
Console.WriteLine();
Console.WriteLine("  --- 8a) 发射配置字段全集（证明纯数据做不到概率/时窗）---");
Check(fireCfgType != null, "找到 FireComponentFireProjectileConfig");
if (fireCfgType != null)
{
    var members = fireCfgType.GetFields(BindingFlags.Instance | BindingFlags.Public)
        .Select(f => f.Name)
        .Concat(fireCfgType.GetProperties(BindingFlags.Instance | BindingFlags.Public).Select(p => p.Name))
        .Distinct().OrderBy(x => x, StringComparer.Ordinal).ToList();
    Note("public 成员共 " + members.Count + " 个：" + string.Join(", ", members));
    foreach (string f in new[] { "checkProjectileId", "firePosId", "speed", "dir",
                                "offsetLine", "fireNumSkip", "fireEventNeed", "projectileFlip" })
    {
        Check(members.Contains(f), "FireComponentFireProjectileConfig." + f + " 存在（本包写/依赖它）");
    }
    string[] forbidden = { "chance", "probability", "random", "angle", "duration", "window", "interval", "count" };
    var bad = members.Where(m => forbidden.Any(w => m.ToLowerInvariant().Contains(w))).ToList();
    Check(bad.Count == 0,
        "★ 发射配置里**没有**任何 概率/随机/角度/时窗/颗数 字段 ⇒ 需求 3(整点 7 颗) 与需求 4(10%/5s/±15°/300 颗) 纯数据不可能，必须走插件",
        bad.Count == 0 ? "已确认 " + members.Count + " 个成员全为静态参数" : "却存在：" + string.Join(",", bad));
}

Type fireDefType = game.GetType("FireComponentDefinition", throwOnError: false);
Check(fireDefType != null, "找到 FireComponentDefinition");
if (fireDefType != null)
{
    // ⚠️ 这几个在源码里是 `public ... { get; set; }` **属性**（不是字段），
    //    .tres 里的属性名照样成立 ⇒ 必须用「字段或属性」判定，别只查字段。
    foreach (string f in new[] { "firePosMarkerPaths", "spritePath", "checkRayResources", "checkShapeResources",
                                 "fireInterval", "fireAnimeClips", "isSpliceSprite", "spliceIdleAnimeClips",
                                 "fireAudioName", "fireCheckList", "fireProjectileList",
                                 "ComponentTypeId", "DefinitionId", "InstanceId", "StateMachineDefinition" })
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
        Check(HasMember(compSetType, f), "CharacterComponentSet." + f + " 是 public 成员", Kind(compSetType, f));
    }
}

Type pktCfgType = game.GetType("TowerDefensePacketConfig", throwOnError: false);
Check(pktCfgType != null, "找到 TowerDefensePacketConfig");
if (pktCfgType != null)
{
    foreach (string f in new[] { "saveKey", "unlockCheckList", "name", "describe",
                                 "handbookDescribe", "handbookStory", "packetAnimeOffset",
                                 "packetAnimeScale", "characterConfig", "type", "override" })
    {
        Check(HasMember(pktCfgType, f), "TowerDefensePacketConfig." + f + " 是 public 成员", Kind(pktCfgType, f));
    }
}

// 护具体系
Console.WriteLine();
Console.WriteLine("  --- 8b) 护具体系（需求 5「二类防具 500 血」的落点）---");
Type armorData = game.GetType("CharacterArmorData", throwOnError: false);
Type armorSlot = game.GetType("ArmorSlotConfig", throwOnError: false);
Type armorTypeData = game.GetType("TowerDefenseArmorTypeData", throwOnError: false);
Type armorInst = game.GetType("TowerDefenseArmorInstance", throwOnError: false);
Type armorReg = game.GetType("TowerDefenseArmorRegistry", throwOnError: false);
Check(armorData != null && armorSlot != null && armorTypeData != null && armorInst != null,
    "找到 CharacterArmorData / ArmorSlotConfig / TowerDefenseArmorTypeData / TowerDefenseArmorInstance");
if (armorData != null)
{
    foreach (string f in new[] { "armorList", "armorDictionary", "fliterAllDictionary",
                                 "fliterOpenDictionary", "fliterCloseDictionary" })
    {
        Check(HasMember(armorData, f), "CharacterArmorData." + f + " 是 public 成员", Kind(armorData, f));
    }
    Check(M(armorData, "GetSlotConfig", 1) != null, "CharacterArmorData.GetSlotConfig(string) 存在");
    Check(M(armorData, "GetOrCreateSlotConfig", 1) != null, "CharacterArmorData.GetOrCreateSlotConfig(string) 存在");
}
if (armorSlot != null)
{
    foreach (string f in new[] { "armorName", "replaceMethod", "replaceMediaName", "slotPath",
                                 "offset", "rotation", "scale", "alphaMultiplier", "damagePoint",
                                 "openFliter", "closeFliter", "destroyFliter" })
    {
        Check(HasMember(armorSlot, f), "ArmorSlotConfig." + f + " 是 public 成员", Kind(armorSlot, f));
    }
    var dp = armorSlot.GetField("damagePoint", BindingFlags.Instance | BindingFlags.Public);
    Check(dp != null && dp.FieldType == typeof(double),
        "ArmorSlotConfig.damagePoint 是 double（写 500.0 才能覆盖 typeData）");
}
if (armorTypeData != null)
{
    foreach (string f in new[] { "armorName", "damagePoint", "stagePersontage",
                                 "stageAnimeTexturePaths", "impactAudio", "armorMethodFlags", "limitMaxHit" })
    {
        Check(HasMember(armorTypeData, f), "TowerDefenseArmorTypeData." + f + " 是 public 成员", Kind(armorTypeData, f));
    }
}
if (armorReg != null)
{
    Check(M(armorReg, "GetArmorType", 1) != null,
        "TowerDefenseArmorRegistry.GetArmorType(string) 存在（ArmorInstance 就是用它查 typeData 的）");
}
if (armorInst != null)
{
    // 构造函数 (TowerDefenseCharacter, ArmorSlotConfig) —— 本包「防具 500 血」就是靠它内部那行三目
    var ctor = armorInst.GetConstructors(BindingFlags.Instance | BindingFlags.Public)
        .FirstOrDefault(c => c.GetParameters().Length == 2
                          && c.GetParameters()[1].ParameterType == armorSlot);
    Check(ctor != null, "TowerDefenseArmorInstance(TowerDefenseCharacter, ArmorSlotConfig) 构造函数存在");
    Check(HasMember(armorInst, "hitPoints"), "TowerDefenseArmorInstance.hitPoints 是 public 成员（= 防具血量）");
    Check(HasMember(armorInst, "armorMethodFlags"), "TowerDefenseArmorInstance.armorMethodFlags 是 public 成员");
}

// 枚举事实
Type enumType = game.GetType("TowerDefenseEnum", throwOnError: false);
Check(enumType != null, "找到 TowerDefenseEnum");
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
    Type amf = enumType.GetNestedType("ARMOR_METHOD_FLAGS", BindingFlags.Public);
    Check(amf != null, "找到 TowerDefenseEnum.ARMOR_METHOD_FLAGS");
    if (amf != null)
    {
        int shield = Convert.ToInt32(Enum.Parse(amf, "SHIELD"));
        Check(shield == 4, "ARMOR_METHOD_FLAGS.SHIELD == 4（「二类护具层」的判定位）", shield.ToString());
        int damageable = Convert.ToInt32(Enum.Parse(amf, "DAMAGEABLE"));
        Check(damageable == 0x40, "ARMOR_METHOD_FLAGS.DAMAGEABLE == 0x40", damageable.ToString());
        // 68 = 4 | 64 ⇒ SHIELD|DAMAGEABLE ⇒ 既有护具层又可被打 ⇒ 「二类防具」
        Check((68 & shield) != 0 && (68 & damageable) != 0,
            "68 == SHIELD|DAMAGEABLE ⇒ 内置 Paper 就是「二类防具」（本包在它上面加 500 血）");
        Check((68 & Convert.ToInt32(Enum.Parse(amf, "DROPABLE"))) == 0,
            "68 不含 DROPABLE ⇒ 报纸不是「可掉落头盔」那一类，符合内置读报僵尸的设定");
    }
}

// AttackComponentDefinition.attackType 的枚举提示必须含 Eat（= 啃食，需求 5）
Type atkDefType = game.GetType("AttackComponentDefinition", throwOnError: false);
Check(atkDefType != null, "找到 AttackComponentDefinition");
if (atkDefType != null)
{
    Check(HasMember(atkDefType, "attackType"),
        "AttackComponentDefinition.attackType 是 public 成员（啃食走它的默认值）", Kind(atkDefType, "attackType"));
    var attrs = atkDefType.GetField("attackType", BindingFlags.Instance | BindingFlags.Public)?.GetCustomAttributes(true)
        ?? (atkDefType.GetProperty("attackType", BindingFlags.Instance | BindingFlags.Public)?.GetCustomAttributes(true)
            ?? Array.Empty<object>());
    string hint = "";
    foreach (var a in attrs)
    {
        var p = a.GetType().GetProperty("HintString") ?? a.GetType().GetProperty("hintString");
        if (p != null) { hint = (string)(p.GetValue(a) ?? ""); break; }
    }
    Note("attackType 的 Enum 提示串 = \"" + hint + "\"");
    Check(hint.Contains("Eat"), "attackType 的合法取值里含 Eat（需求 5「伤害类型 = 啃食」= 默认值）");
}

// ---------------- 9) 读解包源码树核对需求依据 ----------------
Console.WriteLine();
Console.WriteLine("--- 9) 读游戏源码树核对需求依据（不看本包，看游戏自己）---");

if (gameRoot.Length == 0 || !Directory.Exists(gameRoot))
{
    Skip("未传 gameRoot 或目录不存在 —— 跳过事实依据核对");
}
else
{
    string root = gameRoot;
    string R(params string[] parts) => Path.Combine(new[] { root }.Concat(parts).ToArray());

    string[] ReadLinesOrEmpty(params string[] parts)
    {
        string p = R(parts);
        return File.Exists(p) ? File.ReadAllLines(p) : new string[0];
    }
    string ReadOrEmpty(params string[] parts)
    {
        string p = R(parts);
        return File.Exists(p) ? File.ReadAllText(p) : "";
    }
    string P(string rel) => Path.Combine(root, rel.Replace('/', Path.DirectorySeparatorChar));
    string ReadRel(string rel) => File.Exists(P(rel)) ? File.ReadAllText(P(rel)) : "";

    // 9.1 Paper 的 armorMethodFlags 必须真的带 SHIELD 位
    string paperArmor = ReadRel("Registry/Armor/Config/Paper.tres");
    Check(paperArmor.Length > 0, "读到内置 Registry/Armor/Config/Paper.tres");
    Check(paperArmor.Contains("armorMethodFlags = 68"),
        "内置 Paper.armorMethodFlags = 68（= SHIELD|DAMAGEABLE ⇒ 二类护具层）",
        paperArmor.Contains("armorMethodFlags") ? "有该字段" : "缺该字段");
    Check(paperArmor.Contains("damagePoint = 150.0"),
        "内置 Paper.damagePoint = 150.0（本包用 SlotConfig 覆盖成 500，不动注册表）");

    // 9.2 ArmorRegistry.json 必须把 Paper 指到上面那份
    string regJson = ReadRel("Registry/Armor/ArmorRegistry.json");
    Check(regJson.Length > 0, "读到 Registry/Armor/ArmorRegistry.json");
    Check(regJson.Contains("\"Paper\"") && regJson.Contains("res://Registry/Armor/Config/Paper.tres"),
        "注册表里 Paper -> res://Registry/Armor/Config/Paper.tres（ArmorInstance 查 typeData 的入口）");

    // 9.3 内置读报僵尸脚本必须真的有 ToGasp + timeScaleInit = 3.0（需求 6）
    string paperCs = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.cs");
    Check(paperCs.Length > 0, "读到内置 TowerDefenseZombiePaper.cs");
    Check(paperCs.Contains("ArmorHitpointsEmpty") && paperCs.Contains("\"Paper\"") && paperCs.Contains("ToGasp"),
        "★ 需求 6 依据：ArmorHitpointsEmpty(\"Paper\") → SendStateEvent(\"ToGasp\")");
    Check(paperCs.Contains("timeScaleInit = 3.0"),
        "★ 需求 6 依据：AnimeCompleted(\"Gasp\") 里 timeScaleInit = 3.0（= 移速 ×3）");
    Check(paperCs.Contains("AngryWalk") && paperCs.Contains("AngryEat"),
        "★ 依据：暴走后换 AngryWalk / AngryEat 动画");

    // 9.4 状态机里必须有 ToGasp 转换 + zombie.paper.gasp 状态
    string paperSm = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaperStateMachine.tres");
    Check(paperSm.Length > 0, "读到内置 TowerDefenseZombiePaperStateMachine.tres");
    Check(paperSm.Contains("zombie.paper.gasp") && paperSm.Contains("ToGasp"),
        "状态机含 zombie.paper.gasp 状态 + ToGasp 转换（暴走链路完整）");

    // 9.5 场景结构：currentArmor、HeadSlot、且**没有**开火动画
    string paperScene = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.tscn");
    Check(paperScene.Length > 0, "读到内置 TowerDefenseZombiePaper.tscn");
    Check(paperScene.Contains("currentArmor = [\"Paper\"]"), "内置读报僵尸出生就戴 Paper（本包沿用）");
    Check(paperScene.Contains("Rect_44x70_At_4_n2.tres"), "内置 HitBox = Rect_44x70_At_4_n2.tres（本包沿用）");
    string paperSprite = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Paper/ZombiePaper.tscn");
    Check(paperSprite.Length > 0, "读到内置 ZombiePaper.tscn（精灵场景）");
    Check(paperSprite.Contains("HeadSlot"), "精灵场景有 HeadSlot（本包把 Marker2D 挂在它下面）");
    Check(!paperSprite.Contains("HeadFire") && !paperScene.Contains("HeadFire"),
        "★ 读报僵尸**没有** HeadFire（⇒ FireComponent 的动画发射链路必然失效，本包据此改走插件）");

    // 9.6 移速：普通僵尸与读报僵尸都不覆盖 walkSpeedScale
    string baseZombie = ReadRel("Prefab/TowerDefense/Character/TowerDefenseZombie.tscn");
    Check(baseZombie.Length > 0, "读到基场景 TowerDefenseZombie.tscn");
    Check(baseZombie.Contains("walkSpeedScale = 1.0"), "基场景 walkSpeedScale = 1.0");
    string normalScene = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Normal/Scene/Base/TowerDefenseZombieNormal.tscn");
    Check(normalScene.Length > 0, "读到内置普通僵尸场景 TowerDefenseZombieNormal.tscn");
    Check(!normalScene.Contains("walkSpeedScale") && !paperScene.Contains("walkSpeedScale"),
        "★ 需求 5 依据：普通僵尸与读报僵尸**都不覆盖** walkSpeedScale ⇒ 两者同速；本包也不写 = 与普通僵尸一致");

    // 9.7 父组件集里的攻击组件不写 attackType ⇒ 默认 Eat
    string atkZombie = ReadRel("Script/Component/TowerDefense/Character/AttackComponent/AttackComponentZombieDefinition.tres");
    Check(atkZombie.Length > 0, "读到内置 AttackComponentZombieDefinition.tres（父组件集引用它）");
    Check(atkZombie.Contains("InstanceId = \"character.attack.0\""),
        "它占用 InstanceId = character.attack.0（本包**不**重复声明，避免同 id 冲突）");
    Check(!atkZombie.Contains("attackType"),
        "★ 需求 5 依据：它不写 attackType ⇒ 用 AttackComponentDefinition 默认 \"Eat\" = 啃食");
    string zombieCompSet = ReadRel("Prefab/TowerDefense/Character/ComponentSets/TowerDefenseZombieComponentSet.tres");
    Check(zombieCompSet.Contains("AttackComponent/AttackComponentZombieDefinition.tres"),
        "内置僵尸组件集确实包含上面那个攻击组件");

    // 9.8 内置机枪豌豆僵尸 = 本包发射配置的样板
    // ⚠️ C# **不支持**相邻字符串字面量隐式拼接（那是 C/C++/Python 的语法），这里必须写 `+`。
    string gp = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Normal/Scene/GatlingPea/"
                        + "TowerDefenseZombieNormalGatlingPeaFireComponentDefinition.tres");
    Check(gp.Length > 0, "读到内置机枪豌豆僵尸的发射配置（本包逐字沿用其豌豆参数）");
    Check(gp.Contains("speed = -300.0"), "★ 依据：内置用 speed = -300.0 表示「向前」");
    Check(gp.Contains("projectileName = &\"Pea\""), "★ 依据：内置用 projectileName = &\"Pea\"");
    Check(gp.Contains("catapultHeight = 400.0"), "★ 依据：内置 catapultHeight = 400.0");

    // 9.9 FireComponent.cs **本体实现**（最硬的一组证据：不靠猜，直接读游戏源码文本）
    //     它同时解释了两件事：
    //       (a) 为什么「读报僵尸没有 HeadFire」会让动画驱动发射整条失效 → 本包改走插件；
    //       (b) 为什么「改 fireProjectileList 里元素的 dir」一定生效、而「往 Array 里加元素」不生效。
    string fireSrc = ReadRel("Script/Component/TowerDefense/Character/FireComponent/FireComponent.cs");
    Check(fireSrc.Length > 0, "读到游戏源码 FireComponent.cs（本体实现）");
    Check(fireSrc.Contains("public Array<FireComponentFireProjectileConfig> fireProjectileList"),
        "FireComponent.cs:443 —— fireProjectileList 是 public Godot Array（插件能读能改它的元素）");
    Check(fireSrc.Contains("private readonly List<FireComponentFireProjectileConfig> _fireProjectiles"),
        "FireComponent.cs:447 —— _fireProjectiles 是 private readonly List（Fire() 真正逐发读的那张表）");
    Check(fireSrc.Contains("private static void CopyGodotArray(Array<FireComponentFireProjectileConfig> source, List<FireComponentFireProjectileConfig> target)")
          && fireSrc.Contains("target.Clear();")
          && fireSrc.Contains("target.Add(source[i]);"),
        "★ FireComponent.cs:919-929 —— CopyGodotArray 是 `target.Clear()` + 逐条 `target.Add(source[i])`"
        + " ⇒ Array 与 List 的**元素是同一批对象**（同引用），改元素两边同时可见");
    Check(fireSrc.Contains("CopyGodotArray(fireProjectileList, _fireProjectiles);"),
        "FireComponent.cs:965 —— 拷贝点就是 fireProjectileList → _fireProjectiles");
    Check(fireSrc.Contains("private void RefreshExportedArrayCaches()") && !fireSrc.Contains("public void RefreshExportedArrayCaches()"),
        "★ FireComponent.cs:931 —— RefreshExportedArrayCaches 是 **private**（装配期跑一次；插件不该也无法调它，只能改元素）");
    Check(fireSrc.Contains("public void Fire()"),
        "FireComponent.cs:3429 —— Fire() 是 public 无参（插件逐颗打豌豆的唯一入口）");
    Check(fireSrc.Contains("Vector2 velocity = fireComponentFireProjectileConfig.speed * Vector2.FromAngle(Mathf.DegToRad(fireComponentFireProjectileConfig.dir));"),
        "★ FireComponent.cs:3462 —— 弹速方向**每一发都现场读 cfg.dir**（不是缓存）⇒ 改完立刻生效");
    Check(fireSrc.Contains("private bool CanPlayFireAnimation(string clipName)")
          && fireSrc.Contains("if (string.IsNullOrEmpty(clipName))")
          && fireSrc.Contains("if (!CanPlayFireAnimation(fireAnimeClips))"),
        "★ FireComponent.cs:998/1011/3230 —— 开火动画链路在 fireAnimeClips 为空时直接 return ⇒"
        + " 读报僵尸无 HeadFire，动画驱动发射必然失效（本包据此**刻意不依赖**它）");

    // 9.10 本包产物：数值逐条对得上
    Console.WriteLine();
    Console.WriteLine("  --- 9b) 本包产物数值 ---");
    string pkgCfg = ReadRel($"Resources/Characters/Zombies/{KEY}/Config/TowerDefense{KEY}.tres");
        // ⚠️ gameRoot 是**解包树**，本包产物不在它下面 ⇒ 用 projDir 读
    pkgCfg = File.Exists(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY, "Config", $"TowerDefense{KEY}.tres"))
        ? File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY, "Config", $"TowerDefense{KEY}.tres")) : "";
    string pkgScene = File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY, "Scene", KEY + ".tscn"));
    string pkgSlot = File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY, "Armor", "Config", KEY + "ArmorPaper.tres"));
    string pkgCard = File.ReadAllText(Path.Combine(projDir, "Resources", "Cards", KEY + ".tres"));
    string pkgFireDef = File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY,
        "Scene", KEY + "FireComponentDefinition.tres"));

    Check(pkgCfg.Contains("hitpoints = 1180.0") && pkgCfg.Contains("hitpointsNearDeath = 70.0"),
        "本包本体 = 1180 + 濒死 70 = 1250（需求 5）");
    Check(pkgCfg.Contains("attack = 800.0"), "本包 attack = 800.0（需求 5）");
    Check(pkgCfg.Contains("cost = 100") && pkgCfg.Contains("packetCooldown = 5.0"),
        "本包卡片 价格 100 / 冷却 5 秒");
    Check(pkgSlot.Contains("damagePoint = 500.0"), "本包护具槽 damagePoint = 500.0（需求 5 二类防具）");
    Check(pkgScene.Contains("currentArmor = [\"Paper\"]"), "本包场景出生即戴 Paper");
    Check(pkgScene.Contains("Marker2D") && pkgScene.Contains("FireMarker"),
        "本包场景自带 Marker2D FireMarker（firePosMarkerPaths 必须是真 Marker2D）");
    // ★★ 必修项：场景根节点必须显式声明 ComponentSet。
    //    第一版漏了这一行 ⇒ 发射组件根本没被创建 ⇒ 一颗豌豆都打不出来，而且**一句日志都没有**。
    Check(pkgScene.Contains("ComponentSet = ExtResource("),
        "★★ 本包场景根节点声明了 ComponentSet（漏了 ⇒ 发射组件不创建 ⇒ 豌豆一颗都打不出来）");
    Check(pkgScene.Contains($"path=\"./{KEY}ComponentSet.tres\""),
        "★★ 它指向包内 ./" + KEY + "ComponentSet.tres（相对路径，包内自引用禁 res://）");
    string pkgCompSet = File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY,
        "Scene", KEY + "ComponentSet.tres"));
    Check(pkgCompSet.Contains($"path=\"./{KEY}FireComponentDefinition.tres\"")
          && pkgCompSet.Contains("Components = [ExtResource(\"1\")]"),
        "本包组件集 = 只加 1 个发射组件（父集带来其余全部）");
    Check(pkgScene.Contains("TowerDefenseZombiePaper.cs"),
        "本包场景脚本复用内置读报僵尸脚本（需求 6 白送）");
    Check(pkgCard.Contains("type = 6") && pkgCard.Contains("超级机枪读报僵尸"),
        "本包卡片 = ZOMBIE 类型 + 中文显示名（需求 1）");
    Check(!pkgScene.Contains("walkSpeedScale") && !pkgCfg.Contains("walkSpeedScale"),
        "本包不写任何速度缩放 ⇒ 移速 = 普通僵尸（需求 5）");

    // ★★★ 9.12 换头必须是「影子 + 容器 + 可见头」三节点（2026-09-22 定稿）
    //   为什么：头若是身体的（直接）子精灵 ⇒ `CollectOwnedChildBindings`（AdobeAnimateSprite.cs:5385）
    //   只看节点类型就把它收走 ⇒ `IsRenderedByParentSpriteForRender`（:9559）true ⇒
    //   `_Draw()`（:9534）**第一行** return ⇒ 头自己的 `forceLocalRender` **永远走不到**
    //   ⇒ 头的切片由身体批次代画 ⇒ 自制皮肤不在全局图集清单 ⇒ `MediaAtlasPages` 解析不到
    //   ⇒ 落 `BaseAtlasPage = 0`（DrawItemBuilder:921）⇒ 采样 AdobeAnimateVisualTextureArray.png
    //   （全部角色拼在一张的共享大图）⇒ **别的角色碎片拼贴**（= 09-22 实机截图现象）。
    string pkgSprite = File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY,
        "Sprite", KEY + ".tscn"));
    int iShadow = pkgSprite.IndexOf("[node name=\"HeadShadow\"", StringComparison.Ordinal);
    int iHolder = pkgSprite.IndexOf("[node name=\"HeadHolder\"", StringComparison.Ordinal);
    int iHead = pkgSprite.IndexOf("[node name=\"Head\"", StringComparison.Ordinal);
    Func<int, string> Blk = i =>
    {
        if (i < 0) return "";
        int j = pkgSprite.IndexOf("\n[", i, StringComparison.Ordinal);
        return j < 0 ? pkgSprite.Substring(i) : pkgSprite.Substring(i, j - i);
    };
    string shadowBlk = Blk(iShadow);
    string headBlk = Blk(iHead);

    Check(pkgSprite.Contains("[node name=\"HeadShadow\" type=\"Node2D\" parent=\".\""),
        "★ 换头三节点① HeadShadow 是身体（Sprite 场景根）的直接子精灵 —— 位姿影子");
    Check(pkgSprite.Contains("[node name=\"HeadHolder\" type=\"Node2D\" parent=\".\"]"),
        "★ 换头三节点② HeadHolder 是普通 Node2D（identity）—— 打断「父代画」的容器");
    Check(pkgSprite.Contains("[node name=\"Head\" type=\"Node2D\" parent=\"HeadHolder\"]"),
        "★★ 换头三节点③ 可见头挂在 HeadHolder 下（**不是**身体下）");
    Check(!pkgSprite.Contains("[node name=\"Head\" type=\"Node2D\" parent=\".\""),
        "★ 负向：可见头**没有**写成身体的直接子节点（那样就是碎片拼贴那个 bug）");
    Check(iShadow >= 0 && iHolder >= 0 && iHead >= 0 && iShadow < iHolder && iHolder < iHead,
        "节点书写顺序 HeadShadow → HeadHolder → Head（先有容器再放头）");
    Check(shadowBlk.Contains("visible = false"),
        "★ 影子 `visible = false`（它被身体代画，靠不可见 + 全层关来保证零切片）");
    Check(shadowBlk.Contains("parentSprite = NodePath(\"..\")")
          && shadowBlk.Contains("insertLayerId = 16") && shadowBlk.Contains("followParentSpriteLayerId = 16"),
        "★★ 影子保留 parentSprite/insertLayerId/followParentSpriteLayerId —— 唯一让它吃到 UpdateChild 定位的写法");
    Check(!headBlk.Contains("parentSprite") && !headBlk.Contains("insertLayerId")
          && !headBlk.Contains("followParentSpriteLayerId"),
        "★ 可见头**不写** parentSprite/insertLayerId/followParentSpriteLayerId（写了会被拉回身体批次）");
    Check(!headBlk.Contains("\nposition = Vector2")
          && !headBlk.Contains("\nvisible = "),
        "★ 可见头不写 position/visible（位姿由插件每帧从影子同步；写了只是死值）");
    // ★★★ 9.13 头部姿态 = **交还给引擎逐帧覆写**（2026-09-23 第三轮，用户：「回退到上一版本的
    //   僵尸头部动画」⇒ 撤掉第二轮的冻结）
    //
    //   机制（`AdobeAnimateSprite.cs:275-282` 的 `[Export] usePos / useRotate`；
    //        `:5258-5276` 的 `UpdateChild()` 把 Rotation 的赋值**包在 `if (useRotate)` 内**、
    //        Position 的赋值包在 `if (usePos)` 内）—— 这条**仍然成立**，只是本轮取"开"的一侧：
    //      · 都不写 ⇒ 两个开关默认都是 true ⇒ 引擎每帧把
    //        `Position = <L16 pose>.Origin + 父 offset`、`Rotation = <L16 pose>.Rotation + offsetRotate`
    //        写进影子；插件 `SyncHeadPairs()` 再把影子的位姿抄给可见头
    //        ⇒ **头跟着 `anim_head1` 摆动**（Idle 净旋转 −16.03°..+1.01°，逐帧插值）。
    //      · 第二轮曾写 `useRotate = false` + `rotation = 0.0` 把它冻成常量（"摆正"），
    //        本轮按用户要求回退 ⇒ **三行一个都不许出现**。
    //   ⚠️ 为什么连 `rotation` 也禁：它只有在同块内有 `useRotate = false` 时才生效；
    //      单独留一行是**死值**，只会在下次改的人眼里冒充"这里有个角度在起作用"。
    //   ⚠️ 单位提醒（第二轮踩过的坑，保留）：`rotation`/`offsetRotate` 都是**弧度**；
    //      「度/弧度」搞混曾让官方样本交叉校验残差被算成 3.96px（真值 4.61px）。
    Check(!shadowBlk.Contains("useRotate") && !headBlk.Contains("useRotate"),
        "★★ 回退头部动画：两个头都**不写** `useRotate` ⇒ 引擎恢复每帧覆写 Rotation ⇒ 跟 anim_head1 摆动");
    Check(!shadowBlk.Contains("usePos") && !headBlk.Contains("usePos"),
        "★ 回退头部动画：两个头都**不写** `usePos`（留一半等于半个冻结，语义含糊）");
    Check(!shadowBlk.Contains("\nrotation = ") && !headBlk.Contains("\nrotation = "),
        "★★ 负向：两个头都**不写** `rotation` —— 没有 `useRotate = false` 时它是死值，只会误导");
    Check(!pkgSprite.Contains("useRotate"),
        "★ 负向：整份 Sprite 场景里没有任何 `useRotate`（防止「只在一处撤掉」的半回退）");
    // ★★★ 9.14 可见头 z_index（2026-09-23，用户：「渲染层级调高 … 避免被遮挡或出现穿插」）
    //   引擎**全局**绘制排序键的第一位就是 ZIndex（`AdobeAnimateSortPath.CompareTo`，
    //   `AdobeAnimateSortPath.cs:37-48`；统一排序处 `AdobeAnimateRenderManager.cs:753`），
    //   而 `EffectiveZIndex` 就是**沿父链累加 Godot 的 `z_index`**（`AdobeAnimateSprite.cs:6513-6531`）。
    //   ⇒ 可见头写正数 ⇒ effective z 高于身体（含报纸/手臂）⇒ 必定排在它们之后绘制。
    Check(headBlk.Contains("\nz_index = 1"),
        "★★ 可见头 z_index = 1（排序键第一位是 ZIndex ⇒ 显式压在身体与报纸之上，不依赖树序）");
    Check(!shadowBlk.Contains("\nz_index = "),
        "★ 负向：影子不写 z_index（它 visible=false 且零切片，写了无意义还会误导）");
    Check(!pkgSprite.Contains("\nz_index = 0"),
        "★ 负向：没有任何节点把 z_index 写成 0（那等于回到与身体同层，遮挡问题会复发）");
    string[] sprLines = pkgSprite.Split('\n');
    int visTrue = sprLines.Count(l => l.StartsWith("Animation/LayerVisible/") && l.TrimEnd().EndsWith(" = true"));
    int visFalse = sprLines.Count(l => l.StartsWith("Animation/LayerVisible/") && l.TrimEnd().EndsWith(" = false"));
    // 不写死数字：可见头开几层，影子就关几层；总数比它多 7（身体上构成原头的 7 层）。
    Check(visTrue > 0 && visFalse == visTrue + 7,
        "★ 可见头全开 / 影子全关 / 身体原头 7 层全关（false == true + 7）",
        "true=" + visTrue + " false=" + visFalse);
    // 两个头必须逐字相同的三件套：只要它们相同，可见头与「影子若可见」渲染结果就完全一致。
    // ⚠️ offset 是**随旋转 / 平移量重解**的（`.cache/head_place.py` 反解、`.cache/check_head_fit.py` 对账）。
    //    本版（跟随摆动 + 锚点右上 +8/−4 ⇒ 屏幕位移逐字 = (+8, −4)）⇒ (-59.9377, -10.0515)。
    //    历代值：(-36,-46) 照抄植物 Head 的 offset（偏 41.75px，头悬空）、
    //            (-51.46,-7.21) 跟随摆动 + **纯几何对齐**、
    //            (-49.07,-5.24) 冻在 −14.32° 的解（锚错参照物 ⇒ 炮口下垂）、
    //            (-54.19,-10.11) 第二轮交付：冻在 0°（美术原生）的解。
    //    ⚠️ 改 offset 必须同时改这里 + 生成器常量 + 金标，并跑 `.cache/check_head_fit.py`。
    foreach (string k in new[] { "scale = Vector2(-1, 1)", "offset = Vector2(-59.9377, -10.0515)", "offsetRotate = 0.0" })
    {
        Check(shadowBlk.Contains(k) && headBlk.Contains(k),
            "两个头逐字相同：" + k);
    }
    Check(pkgSprite.Contains("Animation/Clip = \"HeadIdle\""),
        "★ 可见头写官方键 `Animation/Clip = \"HeadIdle\"`（裸 clip 会被 Godot 静默丢弃）");
    Check(pkgSprite.Contains("../../../../../Resources/Animations/SuperGatlingPea.tres"),
        "★ Sprite 场景用**相对路径**引包内皮肤（5 个 ../ ；包内自引用禁 res://）");
    Check(!pkgSprite.Contains("res://Asset/Anime/Character/Plant"),
        "★ 负向：没有引用内置 GatlingPea（那是「机枪射手」，不是「超级机枪射手」）");
    Check(pkgSprite.Contains("Animation/LayerVisible/anim_head1 = false"),
        "★ 身体上原版头那一层（anim_head1）被显式关掉");

    // ★★★ 9.15 子弹生成点必须落在炮口上（2026-09-24 第四轮，用户：「让子弹生成位置靠左一点，
    //   对齐子弹发射口」）。真源 = `FireComponentDefinition.firePosMarkerPaths` 指向的 `Marker2D`
    //   的**世界位置**（`FireComponent.cs:2698-2714`：`parent.GetLogicalGlobalPosition(marker2D)`
    //   == `marker2D.GlobalPosition`）—— 既不是僵尸原点，也不是炮口。
    //   静态值是**参考帧 bf=0** 的兜底（`FIRE_MARKER_POS`，HeadSlot 局部空间）；
    //   头跟 `anim_head1` 逐帧摆动 ⇒ 炮口每帧都在动（Idle 段最大离线 10.86px），
    //   「每帧都对上」由插件 `SyncHeadPairs()` 覆写 `marker.GlobalPosition` 完成。
    Check(pkgFireDef.Contains(
        "firePosMarkerPaths = [NodePath(\"SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker\")]"),
        "★★ 生成点路径指向 HeadSlot/FireMarker（与场景节点路径、插件里的 `HeadSlot/FireMarker` 同名）");
    int iMarker = pkgScene.IndexOf("[node name=\"FireMarker\"", StringComparison.Ordinal);
    Check(iMarker >= 0, "★★ Scene 场景里有 FireMarker（Marker2D）节点");
    if (iMarker >= 0)
    {
        int iNext = pkgScene.IndexOf("\n[", iMarker, StringComparison.Ordinal);
        string markerBlk = iNext < 0 ? pkgScene.Substring(iMarker)
                                     : pkgScene.Substring(iMarker, iNext - iMarker);
        Check(markerBlk.Contains("position = Vector2(-35.697232, 94.988609)"),
            "★★ FireMarker.position = (-35.697232, 94.988609)（HeadSlot 局部；"
            + "`.cache/_fire_marker_solve.py` 反解，回代离线 0.000004px）", markerBlk.Trim());
        // 负向：退回 HeadSlot 原点 = 子弹从**头顶上方**出膛（实测偏上 80.77px）
        Check(!markerBlk.Contains("position = Vector2(0, 0)")
              && !markerBlk.Contains("position = Vector2(0.0, 0.0)")
              && !markerBlk.Contains("position = Vector2(0, 0.0)"),
            "★ 负向：FireMarker 不再是 HeadSlot 原点 (0,0)（那等于子弹从头顶上方出膛）");
    }
    // HeadSlot 必须**保持原版值**：它是原版给护具 / DamagePoint 用的静态插槽
    // （`TowerDefenseZombiePaper.tscn:67-71`），我们的偏移加在 FireMarker 上，不动它。
    Check(pkgScene.Contains("position = Vector2(-14.015516, -40.408867)")
          && pkgScene.Contains("rotation = -0.27867758")
          && pkgScene.Contains("scale = Vector2(0.79857695, 0.79857695)"),
        "★★ HeadSlot 保持原版三件套（护具/DamagePoint 依赖它）");

    // ★★ 9.11 为什么「场景没声明 ComponentSet」= 发射组件根本不存在（本次真踩的坑，完整证据链）
    string baseZombieScene = ReadRel("Prefab/TowerDefense/Character/TowerDefenseZombie.tscn");
    Check(baseZombieScene.Contains("ComponentSet = ExtResource("),
        "基场景 TowerDefenseZombie.tscn:10 自带 ComponentSet ⇒ 子场景**不写就继承它**");
    Check(!zombieCompSet.Contains("Fire"),
        "★★ 而基场景那份 TowerDefenseZombieComponentSet.tres 里**没有 FireComponent** ⇒"
        + " 不在自己场景里覆盖 ComponentSet，就永远不会有发射组件（第一版就是栽在这：一颗豌豆都不出、且零日志）");
    string charSrc = ReadRel("Prefab/TowerDefense/Character/TowerDefenseCharacter.cs");
    Check(charSrc.Contains("public CharacterComponentSet ComponentSet { get; set; }")
          && charSrc.Contains("componentManager.ComponentSet = ComponentSet;"),
        "依据：TowerDefenseCharacter.cs:703/1924 —— ComponentSet 是 [Export]，"
        + "EnsureComponentManagerResource() 里「有效就用它、否则回落继承来的那份」");
    string cmSrc = ReadRel("Script/Component/ComponentManager.cs");
    Check(cmSrc.Contains("public void InitializeResourceComponents()")
          && cmSrc.Contains("entry.Definition.CreateRuntime();"),
        "依据：ComponentManager.cs:318/352 —— 组件是**按 ComponentSet 的创建计划逐条 CreateRuntime()** 建出来的");
    string gpScene = ReadRel("Asset/Anime/Character/Zombie/Chapter1/Normal/Scene/GatlingPea/"
                             + "TowerDefenseZombieNormalGatlingPea.tscn");
    Check(gpScene.Contains("ComponentSet = ExtResource("),
        "先例：内置机枪豌豆僵尸场景就是在自己场景里覆盖 ComponentSet（本包照抄这一行）");

    // ★★ 9.12 把本包**真实文件**喂给 ModLoader 的清洗函数：证明「不会被拒」且「引用没被剥」
    //     `SanitizeCharacterTextResource(LoadedMod, relPath, absPath, canStripScripts)` 是 private static；
    //     它只剥 `type="Script"` 且 path 非 res:// 的 ext_resource（.tscn 剥 + 回写，.tres 直接拒包）。
    //     这里传 mod = null：该参数只在**失败路径**（AddDiagnostic）才用，而本包文件都是干净引用。
    MethodInfo sanitize = modLoader?.GetMethod("SanitizeCharacterTextResource",
        BindingFlags.NonPublic | BindingFlags.Static);
    Check(sanitize != null, "找到 ModLoader.SanitizeCharacterTextResource（private static，可反射调用）");
    if (sanitize != null)
    {
        var targets = new (string rel, bool strip)[]
        {
            ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}.tscn",                      true),
            ($"Resources/Characters/Zombies/{KEY}/Sprite/{KEY}.tscn",                     true),
            ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}ComponentSet.tres",          false),
            ($"Resources/Characters/Zombies/{KEY}/Scene/{KEY}FireComponentDefinition.tres", false),
            ($"Resources/Characters/Zombies/{KEY}/Config/TowerDefense{KEY}.tres",         false),
            ($"Resources/Characters/Zombies/{KEY}/Armor/{KEY}ArmorData.tres",             false),
            ($"Resources/Characters/Zombies/{KEY}/Armor/Config/{KEY}ArmorPaper.tres",     false),
            ($"Resources/Characters/Zombies/{KEY}/Packet/{KEY}.tres",                     false),
            ($"Resources/Cards/{KEY}.tres",                                               false),
        };
        int cleaned = 0;
        foreach (var (rel, strip) in targets)
        {
            string abs = Path.Combine(projDir, rel.Replace('/', Path.DirectorySeparatorChar));
            if (!File.Exists(abs)) { Check(false, "清洗目标存在：" + rel); continue; }
            string before = File.ReadAllText(abs);
            bool ok;
            try { ok = (bool)sanitize.Invoke(null, new object[] { null, rel, abs, strip }); }
            catch (Exception ex) { Check(false, "Sanitize(" + rel + ")", ex.GetBaseException().Message); continue; }
            Check(ok, "ModLoader 接受（不拒包）：" + rel);
            // 它剥引用后**会回写文件** ⇒ 本包所有 script 引用都是 res://，文件必须逐字节未变。
            Check(File.ReadAllText(abs) == before,
                "清洗后逐字节未变（一条引用都没被剥）：" + rel);
            if (ok) cleaned++;
        }
        Check(cleaned == targets.Length,
            "本包 9 个 .tscn/.tres 全部通过 ModLoader 清洗（0 拒包 / 0 剥离）", cleaned + "/" + targets.Length);
        Check(File.ReadAllText(Path.Combine(projDir, "Resources", "Characters", "Zombies", KEY,
                  "Scene", KEY + ".tscn")).Contains($"path=\"./{KEY}ComponentSet.tres\""),
            "★★ 清洗之后 ComponentSet 的 ext_resource 仍在"
            + "（剥的是 type=\"Script\"，我们的是 type=\"Resource\"）");
    }
}

Console.WriteLine();
Console.WriteLine(exit == 0 ? "全部通过 ✓" : "存在失败 ✗");
return exit;
