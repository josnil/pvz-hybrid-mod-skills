// 离线复核「超级机枪射手」的**整包闸门**：直接调用游戏程序集里的真实函数，不启动 Godot。
// 与 runtime_src/check_gates.cs（地图那支）同套路，但期望值换成植物包 + 运行时程序集。
//
// 复核五件事：
//   1) ModLoader.InferRuntimeEntry 对包内每个路径推出的 (category, key) ——
//      角色包依赖与 Runtime/ModAssembly.dll 都必须「不被当成 unsupported」；
//   2) XWModManifest.Load 读回真 mod.json 后，runtime* 四个字段是否合规；
//   3) ModLoader.ValidateDeclaredPackageExecutables（private，反射调）：
//      真实包条目清单必须不抛；再塞一个假 Runtime/Evil.dll 必须抛
//      （即「包内不许有未声明的可执行文件」这条闸门真的在生效）；
//   4) XWModRuntimeCompatibility.ValidatePackage 若存在则一并跑（整包兼容性闸门）；
//   5) XWModManifestSyncService.SyncProject 在工程副本上跑，必须返回 false（= 编辑器不会重写 mod.json）。
//   6) 插件依赖的**反射/字符串访问**接缝还在（Almanac._plantInitialized、TOWERDEFENSE_PACKETBANKS…）；
//   7) 2026-09-19 新增数值的落地接缝还在（hitpoints / _override / coverCanDirectPlant …）
//      —— 这些靠 .tres 里的**字段名**生效，改名会静默回落默认值，编译器管不到。
//
// 用法: dotnet run --file check_gates_plant.cs -- <refDir> <projDir> <pmodPath> <entryTypeFullName>
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

string refDir = args.Length > 0 ? args[0] : "";
string projDir = args.Length > 1 ? args[1] : "";
string pmodPath = args.Length > 2 ? args[2] : "";
string entryName = args.Length > 3 ? args[3] : "";
Console.WriteLine("refDir    = " + refDir);
Console.WriteLine("projDir   = " + projDir);
Console.WriteLine("pmod      = " + pmodPath);
Console.WriteLine("entryType = " + entryName);
Console.WriteLine();

var alc = new AssemblyLoadContext("gateCheckPlant", isCollectible: false);
alc.Resolving += (ctx, name) =>
{
    string p = Path.Combine(refDir, name.Name + ".dll");
    return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
};
Assembly game = alc.LoadFromAssemblyPath(Path.Combine(refDir, "PlantsVsZombies.dll"));
Assembly godot = alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));

Type modLoader = game.GetType("PVZHE.ModEditor.ModSystem.ModLoader", throwOnError: false);
Type manType = game.GetType("PVZHE.ModEditor.ModSystem.XWModManifest", throwOnError: false);
Type syncType = game.GetType("PVZHE.ModEditor.ModSystem.XWModManifestSyncService", throwOnError: false);
Type compatType = game.GetType("PVZHE.ModEditor.ModSystem.XWModRuntimeCompatibility", throwOnError: false);
Check(modLoader != null && manType != null && syncType != null,
    "找到 ModLoader / XWModManifest / XWModManifestSyncService");

// ---------------- 1) InferRuntimeEntry ----------------
if (modLoader != null)
{
    MethodInfo infer = modLoader.GetMethod("InferRuntimeEntry",
        BindingFlags.Public | BindingFlags.Static, null,
        new[] { typeof(string), typeof(string).MakeByRefType(), typeof(string).MakeByRefType() }, null);
    Check(infer != null, "ModLoader.InferRuntimeEntry(string,out,out) 可调用");

    // 期望来自 ModLoader.InferRuntimeEntry 的实现：6 段角色路径推 Character/CharacterSprite，
    // 其余 Resources/Characters/Plants/<Key>/… 一律是角色包依赖（不推导 key），
    // Runtime/ModAssembly.dll 走 IsDeclaredRuntimeAssembly 分支（也不推导 key）。
    var expects = new (string path, bool ok, string cat, string key)[]
    {
        ("Resources/Characters/Plants/SuperGatlingPea/Scene/SuperGatlingPea.tscn",   true,  "Character",       "SuperGatlingPea"),
        ("Resources/Characters/Plants/SuperGatlingPea/Sprite/SuperGatlingPea.tscn",  true,  "CharacterSprite", "SuperGatlingPea"),
        ("Resources/Cards/SuperGatlingPea.tres",                                      true,  "Packet",          "SuperGatlingPea"),
        ("Resources/Characters/Plants/SuperGatlingPea/Scene/SuperGatlingPeaComponentSet.tres", false, "", ""),
        ("Resources/Characters/Plants/SuperGatlingPea/Config/TowerDefensePlantSuperGatlingPea.tres", false, "", ""),
        ("Resources/Characters/Plants/SuperGatlingPea/Packet/SuperGatlingPea.tres",   false, "", ""),
        ("Runtime/ModAssembly.dll",                                                   false, "", ""),
        ("Localization/translations.csv",                                             false, "", ""),
        ("mod.json",                                                                  false, "", ""),
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
string pmodJson = Path.Combine(projDir, "mod.json");
if (manType != null && File.Exists(pmodJson))
{
    try
    {
        manifest = manType.GetMethod("Load", BindingFlags.Public | BindingFlags.Static)
                          .Invoke(null, new object[] { pmodJson });
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
        Check(Str("Id") == "supergatlingpea", "Id == supergatlingpea", Str("Id"));

        var provides = (Dictionary<string, List<string>>)manType.GetProperty("Provides").GetValue(manifest);
        bool pchar = provides.TryGetValue("Character", out var vc) && vc.Contains("SuperGatlingPea");
        bool pspr = provides.TryGetValue("CharacterSprite", out var vs) && vs.Contains("SuperGatlingPea");
        bool ppkt = provides.TryGetValue("Packet", out var vp) && vp.Contains("SuperGatlingPea");
        Check(pchar && pspr && ppkt,
            "provides 同时声明 Character / CharacterSprite / Packet：SuperGatlingPea",
            string.Join(" | ", provides.Keys));

        bool required = (bool)manType.GetMethod("IsRuntimeAssemblyRequired").Invoke(manifest, null);
        Check(!required, "IsRuntimeAssemblyRequired() == false（policy=optional，加载失败不毁整包）");
    }
}

// ---------------- 3) ValidateDeclaredPackageExecutables（可执行文件闸门） ----------------
List<string> pmodEntries = new List<string>();
if (File.Exists(pmodPath))
{
    using var zip = ZipFile.OpenRead(pmodPath);
    pmodEntries = zip.Entries.Select(e => e.FullName.Replace('\\', '/')).ToList();
    Check(pmodEntries.Count > 0, "读到 pmod 条目清单", pmodEntries.Count + " 条");
    Check(pmodEntries.Contains("Runtime/ModAssembly.dll"), "pmod 内含 Runtime/ModAssembly.dll");
    Check(pmodEntries[0] == "mod.json", "pmod 条目 0 是 mod.json", pmodEntries[0]);
}

if (modLoader != null && manifest != null && pmodEntries.Count > 0)
{
    MethodInfo vde = modLoader.GetMethod("ValidateDeclaredPackageExecutables",
        BindingFlags.NonPublic | BindingFlags.Static);
    Check(vde != null, "找到 ModLoader.ValidateDeclaredPackageExecutables（private static）");
    if (vde != null)
    {
        string Ex(Exception e) => e.GetBaseException().Message;

        // 3a. 真实条目清单 → 必须不抛
        try
        {
            vde.Invoke(null, new object[] { manifest, pmodEntries });
            Check(true, "真实包条目通过 ValidateDeclaredPackageExecutables（无未声明可执行文件）");
        }
        catch (Exception ex)
        {
            Check(false, "真实包条目通过 ValidateDeclaredPackageExecutables", Ex(ex));
        }

        // 3b. 负向对照：多一个 Runtime/Evil.dll → 必须抛（证明这条闸门真的在生效）
        var bad = new List<string>(pmodEntries) { "Runtime/Evil.dll" };
        bool threw = false;
        string badMsg = "";
        try { vde.Invoke(null, new object[] { manifest, bad }); }
        catch (Exception ex) { threw = true; badMsg = Ex(ex); }
        Check(threw, "负向对照：Runtime/Evil.dll 被拒（整包 fail-closed）", badMsg);

        // 3c. 负向对照：漏掉声明的程序集 → 必须见 "declared runtime assembly is missing"
        //     （这条只在 policy=required 时才致命，但清单里确实少一条，顺手确认不抛）
        var missingDll = pmodEntries.Where(e => e != "Runtime/ModAssembly.dll").ToList();
        try
        {
            vde.Invoke(null, new object[] { manifest, missingDll });
            Note("清单里去掉 ModAssembly.dll 本身不触发本闸门（由 ResolveDeclaredRuntimeAssembly + policy 决定）");
        }
        catch (Exception ex)
        {
            Note("清单里去掉 ModAssembly.dll → " + Ex(ex));
        }
    }
}

// ---------------- 4) XWModRuntimeCompatibility.ValidatePackage（若存在） ----------------
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
    string tmp = Path.Combine(Path.GetTempPath(), "xwmod_sync_plant_" + Guid.NewGuid().ToString("N").Substring(0, 8));
    try
    {
        // 只复制 SyncProject 会在意的文件：mod.json + 全部 resources + 全部 translations。
        // ⚠️ translations 必须一起复制！SyncProject 把 Localization/*.csv 归到 translations 段，
        //    副本里没有该文件时它会把 manifest.translations 重写成 []（植物包非空 ⇒ 假红）。
        //    （地图那支 check_gates.cs 的 translations 是空的，所以没踩到这个坑。）
        Directory.CreateDirectory(tmp);
        var resources = (List<string>)manType.GetProperty("Resources").GetValue(manifest);
        List<string> translations = new List<string>();
        try
        {
            var tp = manType.GetProperty("Translations");
            if (tp != null) translations = (List<string>)tp.GetValue(manifest) ?? new List<string>();
        }
        catch { }
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

// ---------------- 6) 插件依赖的游戏侧「接缝」在两份构建里都存在 ----------------
// 这些是插件在**运行期**要用到的成员。编译期能验证的（有引用）已经由 DLL 两份构建字节一致证明；
// 这里重点补 **反射/字符串访问** 的那几个 —— 编译器管不到，改版后会静默失效：
//   · Almanac._plantInitialized（private，插件用反射读，用来判断要不要刷新植物页）
//   · Almanac.plantPacketBank（public 字段，图鉴那份拷贝的入口）
//   · Almanac.plantCategoryId（public int 字段：删掉 ModPlants 分类后要回落，否则 InitPlant
//     的 `plantCategoryId >= category.Count` 守卫会直接 return 出空列表）
//   · ResourceManager.TOWERDEFENSE_PACKETBANKS（共享卡库，选卡界面的数据源）
Console.WriteLine();
Console.WriteLine("--- 6) 插件依赖的运行时接缝 ---");

Type almanacType = game.GetType("Almanac", throwOnError: false);
Type bankDataType = game.GetType("TowerDefensePacketBankData", throwOnError: false);
Type resType = game.GetType("ResourceManager", throwOnError: false);

Check(almanacType != null, "找到 Almanac 类型");
if (almanacType != null)
{
    FieldInfo ppb = almanacType.GetField("plantPacketBank", BindingFlags.Instance | BindingFlags.Public);
    Check(ppb != null && ppb.FieldType == bankDataType,
        "Almanac.plantPacketBank 是 public 字段且类型为 TowerDefensePacketBankData",
        ppb == null ? "<缺失>" : ppb.FieldType.Name);

    FieldInfo pci = almanacType.GetField("plantCategoryId", BindingFlags.Instance | BindingFlags.Public);
    Check(pci != null && pci.FieldType == typeof(int),
        "Almanac.plantCategoryId 是 public int 字段（插件删分类后要回落它，防翻页越界）",
        pci == null ? "<缺失> ⇒ 删掉 ModPlants 后可能停在越界页（空列表）" : pci.FieldType.Name);

    FieldInfo pi = almanacType.GetField("_plantInitialized", BindingFlags.Instance | BindingFlags.NonPublic);
    Check(pi != null && pi.FieldType == typeof(bool),
        "Almanac._plantInitialized 是 private bool 字段（插件反射刷新的开关）",
        pi == null ? "<缺失> ⇒ 插件会退化为「不刷新植物页」" : pi.FieldType.Name);

    MethodInfo ip = almanacType.GetMethod("InitPlant", BindingFlags.Instance | BindingFlags.Public);
    Check(ip != null && ip.GetParameters().Length == 0, "Almanac.InitPlant() 是 public 无参方法");
}

if (resType != null)
{
    PropertyInfo banks = resType.GetProperty("TOWERDEFENSE_PACKETBANKS",
        BindingFlags.Instance | BindingFlags.Public);
    Check(banks != null, "ResourceManager.TOWERDEFENSE_PACKETBANKS 是 public 实例属性",
        banks == null ? "<缺失>" : banks.PropertyType.Name);
}

if (bankDataType != null)
{
    FieldInfo cat = bankDataType.GetField("category", BindingFlags.Instance | BindingFlags.Public);
    Check(cat != null, "TowerDefensePacketBankData.category 是 public 字段",
        cat == null ? "<缺失>" : cat.FieldType.Name);
    MethodInfo gpl = bankDataType.GetMethod("GetPlantList", BindingFlags.Instance | BindingFlags.Public);
    Check(gpl != null, "TowerDefensePacketBankData.GetPlantList() 存在");
}

Type catalogType = game.GetType("PVZHE.ModEditor.ModSystem.XWModContentCatalog", throwOnError: false);
Check(catalogType != null, "找到 XWModContentCatalog（图鉴隔离 Mod 植物的那个类）");
if (catalogType != null)
{
    MethodInfo wp = catalogType.GetMethod("WithPlants", BindingFlags.Public | BindingFlags.Static);
    Check(wp != null, "XWModContentCatalog.WithPlants 存在（图鉴的卡库拷贝入口）");
}

// ---------------- 7) 2026-09-19 新增数值的落地接缝 ----------------
// 两项用户需求都靠**资源里的字段名**生效，编译器管不到：字段一旦改名/挪窝，
// .tres 里那行就变成「无人认领的属性」，游戏静默回落默认值（血量又变 300、又不能直接种）。
// 所以这里按名字把它们钉在两份构建上：
//   · TowerDefenseCharacterConfig.hitpoints（我们写 hitpoints = 1000.0 的就是它）
//   · TowerDefenseCharacterInstance.hitpointsBase / hitpoints（config → 实例的搬运）
//   · TowerDefensePacketConfig._override（tres 里写作 override）
//   · TowerDefensePacketOverride.coverCanDirectPlant（真正让覆盖卡能种在地上的开关）
//   · TowerDefensePacketConfig.GetCoverCanDirectPlant / TowerDefenseCellInstance.CanPacketPlant
//     （CanPacketPlant:787-800 读的就是上面那个开关）
Console.WriteLine();
Console.WriteLine("--- 7) 血量 / 可直接种植 的字段接缝 ---");

Type charCfgType = game.GetType("TowerDefenseCharacterConfig", throwOnError: false);
Type charInstType = game.GetType("TowerDefenseCharacterInstance", throwOnError: false);
Type pktCfgType = game.GetType("TowerDefensePacketConfig", throwOnError: false);
Type pktOvType = game.GetType("TowerDefensePacketOverride", throwOnError: false);
Type cellType = game.GetType("TowerDefenseCellInstance", throwOnError: false);

Check(charCfgType != null && pktCfgType != null && cellType != null,
    "找到 TowerDefenseCharacterConfig / TowerDefensePacketConfig / TowerDefenseCellInstance");

if (charCfgType != null)
{
    // ⚠️ 用 GetField 逐级向上找：hitpoints 声明在基类 TowerDefenseCharacterConfig 上
    FieldInfo hp = charCfgType.GetField("hitpoints", BindingFlags.Instance | BindingFlags.Public);
    Check(hp != null && hp.FieldType == typeof(double),
        "TowerDefenseCharacterConfig.hitpoints 是 public double（tres 里的 hitpoints = 1000.0）",
        hp == null ? "<缺失> ⇒ 血量会静默回落 300" : hp.FieldType.Name);
    FieldInfo hpn = charCfgType.GetField("hitpointsNearDeath", BindingFlags.Instance | BindingFlags.Public);
    Check(hpn != null && hpn.FieldType == typeof(double),
        "TowerDefenseCharacterConfig.hitpointsNearDeath 是 public double（我们保持 0）",
        hpn == null ? "<缺失>" : hpn.FieldType.Name);
    FieldInfo pc = charCfgType.GetField("plantCover", BindingFlags.Instance | BindingFlags.Public);
    Check(pc != null, "TowerDefenseCharacterConfig.plantCover 是 public 字段（本卡 = [PlantPeaShooter]）",
        pc == null ? "<缺失>" : pc.FieldType.Name);
}

if (charInstType != null)
{
    // _Init: hitpointsBase = config.hitpoints; hitpoints = hitpointsBase + hitpointsNearDeath;
    foreach (string f in new[] { "hitpoints", "hitpointsBase", "hitpointsNearDeath" })
    {
        FieldInfo fi = charInstType.GetField(f, BindingFlags.Instance | BindingFlags.Public);
        Check(fi != null && fi.FieldType == typeof(double),
            "TowerDefenseCharacterInstance." + f + " 是 public double",
            fi == null ? "<缺失>" : fi.FieldType.Name);
    }
}

if (pktCfgType != null)
{
    // ⚠️ C# 字段名 _override，Godot 生成的属性名去掉前导下划线 ⇒ .tres 里写 `override =`
    FieldInfo ov = pktCfgType.GetField("_override", BindingFlags.Instance | BindingFlags.Public);
    Check(ov != null && ov.FieldType == pktOvType,
        "TowerDefensePacketConfig._override 是 public TowerDefensePacketOverride 字段"
        + "（tres 属性名 = override）",
        ov == null ? "<缺失> ⇒ 内联 override 不会被绑定" : ov.FieldType.Name);

    MethodInfo gc = pktCfgType.GetMethod("GetCoverCanDirectPlant",
        BindingFlags.Instance | BindingFlags.Public);
    Check(gc != null && gc.GetParameters().Length == 0 && gc.ReturnType == typeof(bool),
        "TowerDefensePacketConfig.GetCoverCanDirectPlant() 是 public 无参 bool 方法");

    MethodInfo gp = pktCfgType.GetMethod("GetPlantCover", BindingFlags.Instance | BindingFlags.Public);
    Check(gp != null, "TowerDefensePacketConfig.GetPlantCover() 存在（覆盖底座判定入口）");
}

if (pktOvType != null)
{
    FieldInfo cdp = pktOvType.GetField("coverCanDirectPlant", BindingFlags.Instance | BindingFlags.Public);
    Check(cdp != null && cdp.FieldType == typeof(bool),
        "TowerDefensePacketOverride.coverCanDirectPlant 是 public bool（我们唯一开启的字段）",
        cdp == null ? "<缺失> ⇒ 卡片又只能种在双发射手上" : cdp.FieldType.Name);
    FieldInfo pco = pktOvType.GetField("plantCover", BindingFlags.Instance | BindingFlags.Public);
    Check(pco != null, "TowerDefensePacketOverride.plantCover 是 public 字段（我们刻意不写它）",
        pco == null ? "<缺失>" : pco.FieldType.Name);
    FieldInfo cho = pktOvType.GetField("characterOverride", BindingFlags.Instance | BindingFlags.Public);
    Check(cho != null, "TowerDefensePacketOverride.characterOverride 是 public 字段"
        + "（默认非 null 但全是空操作，不会碰血量）",
        cho == null ? "<缺失>" : cho.FieldType.Name);
}

if (cellType != null)
{
    MethodInfo cpp = cellType.GetMethod("CanPacketPlant", BindingFlags.Instance | BindingFlags.Public);
    Check(cpp != null, "TowerDefenseCellInstance.CanPacketPlant 存在（:787-800 读 coverCanDirectPlant 的地方）");
}

Console.WriteLine();
Console.WriteLine(exit == 0 ? "全部通过 ✓" : "存在失败 ✗");
return exit;
