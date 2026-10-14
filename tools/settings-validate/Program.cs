using System;
using System.IO;
using System.Reflection;
using System.Text;
using System.Text.Json;

namespace ValidateSettings;

/// <summary>
/// 离线校验一个 .pmod 或 mod.json 里的 settings 声明 —— **不用开游戏**。
///
/// 做法：把 mod.json 反序列化成宿主自己的 XWModManifest 类型，再反射调用
/// 宿主的 XWModSettingsService.ValidateDefinitions(manifest, out string error)。
/// 于是"校验规则"永远是宿主那一份，本工具不自己实现一套（避免两边规则漂移）。
///
/// 用法：
///   ValidateSettings.exe &lt;宿主目录&gt; &lt;mod.json 或 .pmod&gt; [更多...]
/// 宿主目录 = 含 PlantsVsZombies.dll 的目录（一般是
///   &lt;游戏目录&gt;\data_PlantsVsZombies_windows_x86_64）
///
/// 退出码：0 = 全部通过；1 = 校验失败；2 = 环境/用法问题。
/// </summary>
internal static class Program
{
	private static int Main(string[] args)
	{
		Console.OutputEncoding = Encoding.UTF8;

		if (args.Length < 2)
		{
			Console.WriteLine("用法: ValidateSettings <宿主目录> <mod.json 或 .pmod> [更多...]");
			Console.WriteLine(@"例:   ValidateSettings ""C:\...\data_PlantsVsZombies_windows_x86_64"" .\mod.json");
			return 2;
		}

		string hostDir = args[0];
		string hostDll = Path.Combine(hostDir, "PlantsVsZombies.dll");
		if (!File.Exists(hostDll))
		{
			Console.WriteLine($"FAIL: {hostDir} 下没有 PlantsVsZombies.dll（宿主目录指错了）");
			return 2;
		}

		// 宿主程序集依赖同目录的 GodotSharp 等，靠 AssemblyResolve 从宿主目录补
		AppDomain.CurrentDomain.AssemblyResolve += delegate (object _, ResolveEventArgs e)
		{
			string candidate = Path.Combine(hostDir, new AssemblyName(e.Name).Name + ".dll");
			return File.Exists(candidate) ? Assembly.LoadFrom(candidate) : null;
		};

		Assembly host;
		try
		{
			host = Assembly.LoadFrom(hostDll);
		}
		catch (Exception ex)
		{
			Console.WriteLine("FAIL: 载入宿主程序集失败：" + ex.GetBaseException().Message);
			return 2;
		}

		Type manifestType = host.GetType("PVZHE.ModEditor.ModSystem.XWModManifest");
		Type serviceType = host.GetType("PVZHE.ModEditor.ModSystem.XWModSettingsService");
		if (manifestType == null || serviceType == null)
		{
			Console.WriteLine("FAIL: 宿主里找不到 XWModManifest / XWModSettingsService");
			Console.WriteLine("      （0.29.0 及更早没有 Mod 配置面板，本工具需要 0.30.0+）");
			return 2;
		}

		MethodInfo validate = serviceType.GetMethod(
			"ValidateDefinitions", BindingFlags.Public | BindingFlags.Static);
		if (validate == null)
		{
			Console.WriteLine("FAIL: XWModSettingsService 上没有 ValidateDefinitions");
			return 2;
		}

		int failed = 0;
		foreach (string raw in args[1..])
		{
			string path = Path.GetFullPath(raw);
			if (!File.Exists(path))
			{
				Console.WriteLine($"  {raw,-44} FAIL  文件不存在");
				failed++;
				continue;
			}

			string json;
			try
			{
				json = ReadManifestJson(path);
			}
			catch (Exception ex)
			{
				Console.WriteLine($"  {raw,-44} FAIL  读包失败：{ex.GetBaseException().Message}");
				failed++;
				continue;
			}

			object manifest;
			try
			{
				manifest = JsonSerializer.Deserialize(json, manifestType);
			}
			catch (Exception ex)
			{
				Console.WriteLine($"  {raw,-44} FAIL  反序列化失败：{ex.GetBaseException().Message}");
				failed++;
				continue;
			}

			if (manifest == null)
			{
				Console.WriteLine($"  {raw,-44} FAIL  mod.json 解析为 null");
				failed++;
				continue;
			}

			object[] callArgs = { manifest, null };
			bool ok;
			try
			{
				ok = (bool)validate.Invoke(null, callArgs);
			}
			catch (Exception ex)
			{
				Console.WriteLine($"  {raw,-44} FAIL  调用校验器异常：{ex.GetBaseException().Message}");
				failed++;
				continue;
			}

			string errors = callArgs[1] as string;
			if (ok)
			{
				string count = CountSettings(json);
				Console.WriteLine($"  {raw,-44} OK    settings 声明通过（{count} 项）");
			}
			else
			{
				Console.WriteLine($"  {raw,-44} FAIL  {errors}");
				failed++;
			}
		}

		Console.WriteLine();
		Console.WriteLine(failed == 0 ? "全部通过。" : $"{failed} 个未通过。");
		return failed == 0 ? 0 : 1;
	}

	/// <summary>mod.json 或 .pmod（zip）都能收 —— 直接读 zip 里的根 mod.json。</summary>
	private static string ReadManifestJson(string path)
	{
		if (path.EndsWith(".pmod", StringComparison.OrdinalIgnoreCase))
		{
			using var zip = System.IO.Compression.ZipFile.OpenRead(path);
			var entry = zip.GetEntry("mod.json")
				?? throw new InvalidDataException("包里没有根 mod.json");
			using var reader = new StreamReader(entry.Open(), Encoding.UTF8);
			return reader.ReadToEnd();
		}
		return File.ReadAllText(path, Encoding.UTF8);
	}

	private static string CountSettings(string json)
	{
		try
		{
			using var doc = JsonDocument.Parse(json);
			if (doc.RootElement.TryGetProperty("settings", out var settings)
				&& settings.ValueKind == JsonValueKind.Array)
			{
				return settings.GetArrayLength().ToString();
			}
			return "0";
		}
		catch
		{
			return "?";
		}
	}
}
