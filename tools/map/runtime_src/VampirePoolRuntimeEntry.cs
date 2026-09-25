using System;
using System.IO;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「吸血鬼屋泳池」地图 Mod 的托管运行时入口。
///
/// 存在原因：战斗里的地图背景**不是** TowerDefenseMapConfig.mapTexturePath 画的，
/// 而是地图场景（TowerDefenseMapVampire.tscn）里那个 Sprite2D 的 [ext_resource] 贴图
/// （内置 res://Asset/Texture/.../Vampire/Vampire.jpg）。Mod 自己的图片没有可被
/// ResourceLoader 按路径加载的通道（ModLoader 是手工解码的，导出构建里 user:// 的
/// jpg 读不了），所以纯数据包改不动战斗背景。
///
/// 本入口在运行时把 Mod 包内的贴图解码出来，替换掉「当前地图是我们这张图」时
/// 场景里那个内置背景 Sprite2D 的贴图。同时顺带覆盖关卡编辑器预览用的
/// editorSprite（它也是拿 mapTexturePath 载入同一个内置贴图）。
///
/// 铁律：Initialize / OnAllModsLoaded / Shutdown 一律**不许抛异常**。
/// 依据 ModLoader.cs：
///   - TryInitializeRuntimeEntry 失败 → 第 671 行无条件 return false（整包被拒，且不受
///     runtimeAssemblyPolicy 保护）；
///   - NotifyAllModsLoaded 失败 → 第 180-183 行 State = Failed。
/// 所以每个回调都整体包 try/catch，失败只记日志。
/// </summary>
public sealed class VampirePoolRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[VampirePool] ";

	/// <summary>与 mod.json 的 provides.Texture 对应；键 = 贴图文件名去扩展。</summary>
	private const string TextureKey = "VampirePoolBackground";

	/// <summary>
	/// 包内贴图候选路径（正斜杠，相对 PackageRoot）。注册表查不到时按序回退读文件。
	/// </summary>
	/// <remarks>
	/// 三个前缀 Assets/Textures、Assets/Texture、Assets/Images 都被
	/// ModLoader.InferRuntimeEntry 认作 Texture 类别，键一律 =「文件名去扩展」，
	/// 所以放哪个目录都注册成同一个键（VampirePoolBackground）。
	/// 这里放两个只是让「直接读文件」的兜底也稳；Assets/Images 是编辑器 72 标准目录
	/// 之一（XWModProjectLayout.StandardDirectories），故优先。
	/// </remarks>
	private static readonly string[] RelativeTexturePaths =
	{
		"Assets/Images/" + TextureKey + ".jpg",
		"Assets/Textures/" + TextureKey + ".jpg",
	};

	/// <summary>内置背景贴图路径后缀：只有还挂着它的 Sprite2D 才是我们要换的。</summary>
	private const string BuiltInTextureSuffix = "Vampire/Vampire.jpg";

	/// <summary>本 Mod 地图资源配置路径后缀，用来判定「当前地图是不是我们这张」。</summary>
	private const string OwnMapResourceSuffix = "VampirePool.tres";

	/// <summary>兜底判定：本 Mod 地图的显示名。</summary>
	private const string OwnMapTranslate = "吸血鬼屋泳池";

	/// <summary>采样节流：每 10 帧查一次（约 6 次/秒）。</summary>
	private const int CheckIntervalFrames = 10;

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	private Texture2D _texture;
	private bool _hooked;
	private bool _connected;
	private int _frameCounter;
	private bool _textureMissingReported;
	private bool _swapDoneReported;
	private bool _faultReported;

	public void Initialize(XWModRuntimeContext context)
	{
		try
		{
			_context = context;
			_texture = null;
			_hooked = false;
			_frameCounter = 0;
			_textureMissingReported = false;
			_swapDoneReported = false;
			_faultReported = false;

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root);
		}
		catch (Exception ex)
		{
			Warn("Initialize 异常（已吞掉，避免整包被拒）：" + ex.Message);
		}
	}

	public void OnAllModsLoaded()
	{
		try
		{
			if (_hooked)
			{
				return;
			}
			_tree = Engine.GetMainLoop() as SceneTree;
			if (_tree == null)
			{
				Warn("拿不到 SceneTree；地图背景贴图替换不会生效（其余功能不受影响）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			_connected = true;
			_hooked = true;
			Info("已挂载 process_frame；进入「" + OwnMapTranslate + "」时将替换地图背景贴图。");
		}
		catch (Exception ex)
		{
			Warn("OnAllModsLoaded 异常（已吞掉）：" + ex.Message);
		}
	}

	public void Shutdown()
	{
		try
		{
			if (_connected && _tree != null && GodotObject.IsInstanceValid(_tree))
			{
				_tree.Disconnect("process_frame", _tickCallable);
			}
		}
		catch (Exception ex)
		{
			Warn("Shutdown 异常（已吞掉）：" + ex.Message);
		}
		finally
		{
			_connected = false;
			_hooked = false;
			_tree = null;
			_texture = null;
		}
	}

	private void OnProcessFrame()
	{
		try
		{
			_frameCounter++;
			if ((_frameCounter % CheckIntervalFrames) != 0)
			{
				return;
			}

			TowerDefenseManager manager = TowerDefenseManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;
			}

			TowerDefenseBattleFeatureMap feature = TowerDefenseManager.GetMapFeature();
			if (feature == null || !GodotObject.IsInstanceValid(feature))
			{
				return;
			}

			TowerDefenseMapConfig config = feature.config;
			if (config == null || !GodotObject.IsInstanceValid(config))
			{
				return;
			}
			if (!IsOwnMap(config))
			{
				return;
			}

			Texture2D texture = ResolveTexture();
			if (texture == null)
			{
				return;
			}

			int swapped = SwapRecursiveSafe(_tree.Root, texture);
			if (swapped > 0 && !_swapDoneReported)
			{
				_swapDoneReported = true;
				Info("已替换地图背景贴图，共命中 " + swapped + " 个 Sprite2D。");
			}
		}
		catch (Exception ex)
		{
			if (!_faultReported)
			{
				_faultReported = true;
				Warn("替换背景贴图时异常（已停止重试）：" + ex.Message);
			}
		}
	}

	private static bool IsOwnMap(TowerDefenseMapConfig config)
	{
		try
		{
			string resourcePath = config.ResourcePath;
			if (!string.IsNullOrEmpty(resourcePath)
				&& resourcePath.EndsWith(OwnMapResourceSuffix, StringComparison.OrdinalIgnoreCase))
			{
				return true;
			}
			return string.Equals(config.translate, OwnMapTranslate, StringComparison.Ordinal);
		}
		catch
		{
			return false;
		}
	}

	/// <summary>
	/// 先问引擎注册表（ModLoader 已按 provides.Texture 手工解码并注册），
	/// 再退回到直接读 Mod 包内的文件。两条路都失败就安静地放弃，绝不影响游戏。
	/// </summary>
	private Texture2D ResolveTexture()
	{
		if (_texture != null && GodotObject.IsInstanceValid(_texture))
		{
			return _texture;
		}

		try
		{
			if (XWModRuntimeRegistry.TryGetRuntimeTexture(TextureKey, out Texture2D registered)
				&& registered != null
				&& GodotObject.IsInstanceValid(registered))
			{
				_texture = registered;
				return _texture;
			}
		}
		catch (Exception ex)
		{
			if (!_textureMissingReported)
			{
				Warn("读取引擎贴图表失败，改读文件：" + ex.Message);
			}
		}

		try
		{
			string root = (_context == null) ? null : _context.PackageRoot;
			if (!string.IsNullOrWhiteSpace(root))
			{
				for (int i = 0; i < RelativeTexturePaths.Length; i++)
				{
					string fullPath = Path.Combine(
						root, RelativeTexturePaths[i].Replace('/', Path.DirectorySeparatorChar));
					if (!File.Exists(fullPath))
					{
						continue;
					}
					Image image = Image.LoadFromFile(fullPath);
					if (image != null && !image.IsEmpty())
					{
						_texture = ImageTexture.CreateFromImage(image);
						return _texture;
					}
				}
			}
		}
		catch (Exception ex)
		{
			if (!_textureMissingReported)
			{
				Warn("从 Mod 包读取贴图失败：" + ex.Message);
			}
		}

		if (!_textureMissingReported)
		{
			_textureMissingReported = true;
			Warn("没有找到贴图（已试 " + string.Join(" / ", RelativeTexturePaths)
				+ "）；将保持内置背景。");
		}
		return null;
	}

	private static int SwapRecursiveSafe(Node root, Texture2D texture)
	{
		int count = 0;
		SwapRecursive(root, texture, ref count);
		return count;
	}

	private static void SwapRecursive(Node node, Texture2D texture, ref int count)
	{
		if (node == null || !GodotObject.IsInstanceValid(node))
		{
			return;
		}

		if (node is Sprite2D sprite)
		{
			Texture2D current = sprite.Texture;
			if (current != null && GodotObject.IsInstanceValid(current))
			{
				string path = current.ResourcePath;
				if (!string.IsNullOrEmpty(path)
					&& path.EndsWith(BuiltInTextureSuffix, StringComparison.OrdinalIgnoreCase))
				{
					sprite.Texture = texture;
					count++;
				}
			}
		}

		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			SwapRecursive(children[i], texture, ref count);
		}
	}

	private void Info(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Log(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.Print
		}
		GD.Print(LogPrefix + message);
	}

	private void Warn(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Warn(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.PushWarning
		}
		GD.PushWarning(LogPrefix + message);
	}
}
