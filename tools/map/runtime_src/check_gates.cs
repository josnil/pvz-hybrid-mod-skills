// 离线复核「吸血鬼屋泳池」的运行时换贴图链路：直接调用**游戏程序集里的真实函数**，
// 而不是我自己复刻的规则。不启动 Godot（只碰纯 BCL 的方法）。
//
// 复核三件事：
//   1) ModLoader.InferRuntimeEntry 对我们包内每个路径推出的 (category, key)，
//      是否与我们写进 mod.json 的 provides 完全对上（标签其实就是「文件名去扩展」）；
//   2) XWModManifest.Load 读回我们的 mod.json 后，runtime* 四个字段是否合规
//      （runtimeAssembly 必须是字面量 "Runtime/ModAssembly.dll"，api 必须恰好 1）；
//   3) XWModManifestSyncService.SyncProject 在**工程目录副本**上跑一遍，
//      是否返回 false（= 无需重写）。若返回 true 就说明编辑器一打开工程就会改我们的 mod.json。
//
// 用法: dotnet run --file check_gates.cs -- <refDir> <projDir> <entryTypeFullName>
using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.Loader;

int exit = 0;
void Check(bool ok, string label, string detail = "")
{
    Console.WriteLine((ok ? "  PASS  " : "  FAIL  ") + label + (detail.Length > 0 ? "  :: " + detail : ""));
    if (!ok) exit = 1;
}
void Note(string s) => Console.WriteLine("  ..     " + s);

string refDir = args.Length > 0 ? args[0] : "";
string projDir = args.Length > 1 ? args[1] : "";
string entryName = args.Length > 2 ? args[2] : "";
Console.WriteLine("refDir    = " + refDir);
Console.WriteLine("projDir   = " + projDir);
Console.WriteLine("entryType = " + entryName);
Console.WriteLine();

var alc = new AssemblyLoadContext("gateCheck", isCollectible: false);
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
Check(modLoader != null && manType != null && syncType != null, "找到 ModLoader / XWModManifest / XWModManifestSyncService");

// ---------------- 1) InferRuntimeEntry ----------------
if (modLoader != null)
{
    MethodInfo infer = modLoader.GetMethod("InferRuntimeEntry",
        BindingFlags.Public | BindingFlags.Static, null,
        new[] { typeof(string), typeof(string).MakeByRefType(), typeof(string).MakeByRefType() }, null);
    Check(infer != null, "ModLoader.InferRuntimeEntry(string,out,out) 可调用");

    var expects = new (string path, bool ok, string cat, string key)[]
    {
        ("Assets/Images/VampirePoolBackground.jpg", true,  "Texture", "VampirePoolBackground"),
        ("Assets/Textures/VampirePoolBackground.jpg", true, "Texture", "VampirePoolBackground"),
        ("Resources/Maps/VampirePool.tres",          true,  "Map",     "VampirePool"),
        ("Runtime/ModAssembly.dll",                   false, "",        ""),
        ("mod.json",                                  false, "",        ""),
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
                got ? "(" + gc + ", " + gk + ")" : "返回 false（未识别，会被当 unsupported 或跳过）");
        else
            Check(!got, "InferRuntimeEntry(" + path + ") == false（不作为资源条目）"
                , got ? "却得到 (" + gc + ", " + gk + ")" : "");
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

        var provides = (Dictionary<string, List<string>>)manType.GetProperty("Provides").GetValue(manifest);
        bool hasMap = provides.ContainsKey("Map") && provides["Map"].Contains("VampirePool");
        bool hasTex = provides.ContainsKey("Texture") && provides["Texture"].Contains("VampirePoolBackground");
        Check(hasMap && hasTex, "provides 同时声明 Map/VampirePool 与 Texture/VampirePoolBackground",
            string.Join(" | ", provides.Keys));

        // optional 的语义：程序集缺失/加载失败时不连坐整包
        bool required = (bool)manType.GetMethod("IsRuntimeAssemblyRequired").Invoke(manifest, null);
        Check(!required, "IsRuntimeAssemblyRequired() == false（policy=optional，加载失败不毁整包）");
    }
}

// ---------------- 3) SyncProject 幂等（在副本上跑，绝不动真工程） ----------------
if (syncType != null && manifest != null)
{
    string tmp = Path.Combine(Path.GetTempPath(), "xwmod_sync_probe_" + Guid.NewGuid().ToString("N").Substring(0, 8));
    try
    {
        // 只复制 SyncProject 会在意的文件（mod.json + resources 三类），目录骨架对扫描无影响
        Directory.CreateDirectory(tmp);
        foreach (string rel in new[]
        {
            "mod.json",
            "Resources/Maps/VampirePool.tres",
            "Assets/Images/VampirePoolBackground.jpg",
            "Runtime/ModAssembly.dll",
        })
        {
            string dst = Path.Combine(tmp, rel.Replace('/', Path.DirectorySeparatorChar));
            Directory.CreateDirectory(Path.GetDirectoryName(dst)!);
            File.Copy(Path.Combine(projDir, rel.Replace('/', Path.DirectorySeparatorChar)), dst, true);
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

Console.WriteLine();
Console.WriteLine(exit == 0 ? "全部通过 ✓" : "存在失败 ✗");
return exit;
