// 侦察探针：把游戏程序集里「运行时入口 + 植物发射」相关的 API 全 dump 出来，
// 供写植物插件前确认「我打算调的东西到底存不存在、是不是 public」。
// 不启动 Godot，只反射。
//
// 用法: dotnet run --file check_api.cs -- <refDir> [outFile]
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.Loader;
using System.Text;

string refDir = args.Length > 0 ? args[0] : "";
string outFile = args.Length > 1 ? args[1] : "";
var sb = new StringBuilder();
void W(string s) { sb.AppendLine(s); }

var alc = new AssemblyLoadContext("apiProbe", isCollectible: false);
alc.Resolving += (ctx, name) =>
{
    string p = Path.Combine(refDir, name.Name + ".dll");
    return File.Exists(p) ? ctx.LoadFromAssemblyPath(p) : null;
};
Assembly game = alc.LoadFromAssemblyPath(Path.Combine(refDir, "PlantsVsZombies.dll"));
alc.LoadFromAssemblyPath(Path.Combine(refDir, "GodotSharp.dll"));
Type[] all;
try { all = game.GetTypes(); }
catch (ReflectionTypeLoadException ex) { all = ex.Types.Where(t => t != null).ToArray(); }
W("总类型数: " + all.Length);

string Sig(MethodBase m)
{
    string ps = string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name));
    string rt = (m as MethodInfo)?.ReturnType.Name ?? "void";
    string vis = m.IsPublic ? "public" : m.IsFamily ? "protected" : m.IsAssembly ? "internal" : "private";
    return vis + " " + (m.IsStatic ? "static " : "") + rt + " " + m.Name + "(" + ps + ")";
}

void DumpType(Type t, bool includeNonPublic = false)
{
    if (t == null) { W("  <类型不存在>"); return; }
    W("### " + t.FullName + (t.IsInterface ? "  [interface]" : t.IsAbstract ? "  [abstract]" : "") +
      "  base=" + (t.BaseType?.FullName ?? "-"));
    var flags = BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly;
    if (includeNonPublic) flags |= BindingFlags.NonPublic;
    foreach (var p in t.GetProperties(flags).OrderBy(x => x.Name))
        W("  prop " + (p.GetMethod?.IsPublic == true ? "public " : "") + p.PropertyType.Name + " " + p.Name);
    foreach (var f in t.GetFields(flags).OrderBy(x => x.Name))
        W("  field " + (f.IsPublic ? "public " : f.IsPrivate ? "private " : "internal ") +
          (f.IsStatic ? "static " : "") + f.FieldType.Name + " " + f.Name);
    foreach (var m in t.GetMethods(flags).Where(m => !m.IsSpecialName).OrderBy(x => x.Name))
        W("  " + Sig(m));
    foreach (var e in t.GetEvents(flags).OrderBy(x => x.Name))
        W("  event " + e.EventHandlerType.Name + " " + e.Name);
}

Type T(string full) => game.GetType(full, throwOnError: false);

W("\n" + new string('=', 70));
W("1) IXWModRuntimeEntry / XWModRuntimeContext");
W(new string('=', 70));
DumpType(T("PVZHE.ModEditor.ModSystem.IXWModRuntimeEntry"));
DumpType(T("PVZHE.ModEditor.ModSystem.XWModRuntimeContext"));
DumpType(T("PVZHE.ModEditor.ModSystem.XWModRuntimeRegistry"));
DumpType(T("PVZHE.ModEditor.ModSystem.PVZApiRegistry"));

W("\n" + new string('=', 70));
W("2) 含 Companion 的运行时类型（Character 类 Mod 可能走额外闸门）");
W(new string('=', 70));
foreach (var t in all.Where(t => t != null && t.Name.Contains("Companion", StringComparison.Ordinal)).OrderBy(t => t.FullName))
    DumpType(t, includeNonPublic: true);

W("\n" + new string('=', 70));
W("3) 植物 / 发射组件：公开成员");
W(new string('=', 70));
foreach (var name in new[] {
    "PVZHE.Battle.Feature.Character.TowerDefensePlant",
    "TowerDefensePlant",
    "TowerDefenseCharacter",
    "FireComponent",
    "FireComponentDefinition",
    "FireComponentFireProjectileConfig",
    "FireComponentStateMachine",
    "BattleEventBus" })
{
    var hits = all.Where(t => t != null && (t.FullName == name || t.Name == name)).ToList();
    foreach (var t in hits) { W("--- 按名匹配 " + name + " -> " + t.FullName); DumpType(t); }
    if (hits.Count == 0) W("--- 按名匹配 " + name + " -> <无>");
}

W("\n" + new string('=', 70));
W("4) 全程序集：方法名含 Fire/Volley/Shoot 的公开方法");
W(new string('=', 70));
foreach (var t in all.Where(t => t != null).OrderBy(t => t.FullName))
{
    MethodInfo[] ms;
    try { ms = t.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly); }
    catch { continue; }
    foreach (var m in ms.Where(m => !m.IsSpecialName &&
        (m.Name.Contains("Fire") || m.Name.Contains("Volley") || m.Name.Contains("Shoot"))))
        W("  " + t.FullName + " :: " + Sig(m));
}

W("\n" + new string('=', 70));
W("5) 植物子类清单（继承 TowerDefensePlant 的类型，前 40 个）");
W(new string('=', 70));
Type basePlant = all.FirstOrDefault(t => t != null && t.Name == "TowerDefensePlant");
if (basePlant != null)
{
    int n = 0;
    foreach (var t in all.Where(t => t != null && t != basePlant && basePlant.IsAssignableFrom(t)).OrderBy(t => t.Name))
    {
        if (n++ >= 40) break;
        W("  " + t.FullName);
    }
    W("  (共 " + all.Count(t => t != null && t != basePlant && basePlant.IsAssignableFrom(t)) + " 个)");
}

W("\n" + new string('=', 70));
W("6) Character 类 Mod 的加载路径相关：含 Runtime/Entry/Mod 的静态方法");
W(new string('=', 70));
foreach (var t in all.Where(t => t != null && (t.Name.Contains("XWMod"))).OrderBy(t => t.FullName))
{
    MethodInfo[] ms;
    try { ms = t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.DeclaredOnly); }
    catch { continue; }
    foreach (var m in ms.Where(m => !m.IsSpecialName &&
        (m.Name.Contains("Runtime") || m.Name.Contains("Entry") || m.Name.Contains("Validate"))))
        W("  " + t.FullName + " :: " + Sig(m) + "   [" + t.Assembly.GetName().Name + "]");
}

if (outFile.Length > 0) File.WriteAllText(outFile, sb.ToString(), new UTF8Encoding(false));
Console.WriteLine(sb.ToString());
