// 离线复刻 ModLoader 的运行入口发现逻辑，验证 ModAssembly.dll 能被正确认出来。
// 依据 XWModCharacterCompanionRuntime.TryInitializeRuntimeEntry:
//   1) manifest.RuntimeEntryType 非空
//   2) manifest.RuntimeApiVersion == 1
//   3) GetTypes() 里有一个 非 abstract + 实现 IXWModRuntimeEntry + FullName 完全等于 入口类型的 Type
//   4) Activator.CreateInstance(type) 能成功（公开无参构造函数）
// 用法: dotnet run check_entry.cs -- <refDir> <modAssemblyPath> <entryTypeFullName>
using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;

int exit = 0;
void Check(bool ok, string label, string detail = "")
{
    Console.WriteLine((ok ? "  PASS  " : "  FAIL  ") + label + (detail.Length > 0 ? "  :: " + detail : ""));
    if (!ok) exit = 1;
}

string refDir = args.Length > 0 ? args[0] : "";
string modDll = args.Length > 1 ? args[1] : "";
string entryName = args.Length > 2 ? args[2] : "";

Console.WriteLine("refDir      = " + refDir);
Console.WriteLine("modDll      = " + modDll);
Console.WriteLine("entryType   = " + entryName);
Console.WriteLine();

Check(Directory.Exists(refDir), "引用目录存在");
Check(File.Exists(modDll), "ModAssembly.dll 存在");

// 只解析到引用目录，避免把 Mod 自己的目录当解析根
var resolver = new AssemblyDependencyResolver(modDll);
var alc = new AssemblyLoadContext("entryCheck", isCollectible: true);
alc.Resolving += (ctx, name) =>
{
    string p = Path.Combine(refDir, name.Name + ".dll");
    if (File.Exists(p)) return ctx.LoadFromAssemblyPath(p);
    string r = resolver.ResolveAssemblyToPath(name);
    if (!string.IsNullOrEmpty(r) && File.Exists(r)) return ctx.LoadFromAssemblyPath(r);
    return null;
};

Assembly game = alc.LoadFromAssemblyPath(Path.Combine(refDir, "PlantsVsZombies.dll"));
Assembly godot = alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));
Assembly mod = alc.LoadFromAssemblyPath(modDll);

Console.WriteLine();
Console.WriteLine("-- ModAssembly 引用表 --");
foreach (var r in mod.GetReferencedAssemblies())
    Console.WriteLine("     " + r.Name + " " + r.Version);

Console.WriteLine();
Type iface = game.GetType("PVZHE.ModEditor.ModSystem.IXWModRuntimeEntry", throwOnError: false);
Check(iface != null, "找到 IXWModRuntimeEntry（game 程序集）");

Type[] types;
try { types = mod.GetTypes(); }
catch (ReflectionTypeLoadException ex) { types = ex.Types.Where(t => t != null).ToArray()!; }

Console.WriteLine();
Console.WriteLine("-- ModAssembly 类型 --");
foreach (var t in types) Console.WriteLine("     " + t.FullName);

Type? entry = types.SingleOrDefault(t =>
    t != null && !t.IsAbstract && iface != null && iface.IsAssignableFrom(t)
    && string.Equals(t.FullName, entryName.Trim(), StringComparison.Ordinal));

Check(entry != null, "唯一命中 入口类型 == '" + entryName + "'");

if (entry != null)
{
    Check(entry.IsPublic, "入口类型 public");
    var ctor = entry.GetConstructor(Type.EmptyTypes);
    Check(ctor != null && ctor.IsPublic, "有公开无参构造函数");

    // 三个接口方法都要在
    foreach (var m in new[] { "Initialize", "OnAllModsLoaded", "Shutdown" })
        Check(entry.GetMethod(m) != null, "实现方法 " + m);

    object? inst = null;
    try { inst = Activator.CreateInstance(entry); } catch (Exception ex) { Check(false, "Activator.CreateInstance", ex.Message); }
    Check(inst != null, "Activator.CreateInstance 成功");
    if (inst is IDisposable d) d.Dispose();

    // 入口类型 FullName 必须与 mod.json 里声明的一致（无命名空间 = 纯类名）
    Check(!entryName.Contains('+'), "入口类型不是嵌套类型");
}

Console.WriteLine();
Console.WriteLine(exit == 0 ? "全部通过 ✓" : "存在失败 ✗");
return exit;
