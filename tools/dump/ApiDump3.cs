// Throwaway developer utility (Part 1 build verification) -- UI pass.
// Prints the real ColossalFramework.UI surface for sprites, atlases, fonts and text fields.
//
// Build:  csc /nologo /out:tools\dump\ApiDump3.exe /r:"<managed>\ColossalManaged.dll" tools\dump\ApiDump3.cs
// Run:    tools\dump\ApiDump3.exe "E:\...\Cities_Data\Managed"

using System;
using System.IO;
using System.Linq;
using System.Reflection;

internal static class ApiDump3
{
    private static Assembly _colossal;

    private static int Main(string[] args)
    {
        string managed = args.Length > 0 ? args[0] : @"E:\games\epic games\CitiesSkylines\Cities_Data\Managed";

        AppDomain.CurrentDomain.AssemblyResolve += (sender, e) =>
        {
            string simple = new AssemblyName(e.Name).Name;
            string candidate = Path.Combine(managed, simple + ".dll");
            return File.Exists(candidate) ? Assembly.LoadFrom(candidate) : null;
        };

        _colossal = Assembly.LoadFrom(Path.Combine(managed, "ColossalManaged.dll"));

        Console.WriteLine("===== Types in ColossalFramework.UI matching Atlas/Sprite/Font =====");
        foreach (Type t in _colossal.GetTypes().Where(t => t.IsPublic && (t.Name.Contains("Atlas") || t.Name.Contains("Sprite") || t.Name.Contains("Font"))).OrderBy(t => t.Name))
        {
            Console.WriteLine("  " + t.FullName);
        }

        DumpType("ColossalFramework.UI.UITextureAtlas");
        DumpType("ColossalFramework.UI.UIFontManager");
        DumpType("ColossalFramework.UI.UIFont");
        DumpType("ColossalFramework.UI.UISprite");
        DumpType("ColossalFramework.UI.UITextureSprite");
        DumpType("ColossalFramework.UI.UITextComponent", "font", "textScale", "textColor");
        DumpType("ColossalFramework.UI.UILabel", "font");
        DumpType("ColossalFramework.UI.UIButton", "font", "normalBgSprite", "atlas", "sprite");
        DumpType("ColossalFramework.UI.UIView", "focused", "GetAView", "AddUIComponent");
        DumpType("ColossalFramework.UI.UIInput", "focused");

        Console.WriteLine("===== Text field lookalikes =====");
        foreach (Type t in _colossal.GetTypes().Where(t => t.IsPublic && t.Name.StartsWith("UIText", StringComparison.Ordinal)).OrderBy(t => t.Name))
        {
            Console.WriteLine("  " + t.FullName);
        }

        Console.WriteLine("===== Fonts loaded by the game =====");
        try
        {
            Type fontManager = _colossal.GetType("ColossalFramework.UI.UIFontManager");
            if (fontManager != null)
            {
                PropertyInfo fonts = fontManager.GetProperty("fonts", BindingFlags.Public | BindingFlags.Static);
                Console.WriteLine("  UIFontManager.fonts = " + (fonts == null ? "MISSING" : fonts.PropertyType.Name));
            }
        }
        catch (Exception e)
        {
            Console.WriteLine("  font probe failed: " + e.Message);
        }

        return 0;
    }

    private static void DumpType(string name, params string[] filters)
    {
        Type t = _colossal.GetType(name);
        Console.WriteLine("===== " + name + " =====");
        if (t == null)
        {
            Console.WriteLine("  TYPE NOT FOUND");
            return;
        }

        foreach (MemberInfo m in t.GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly).OrderBy(m => m.Name))
        {
            if (filters.Length > 0 && !filters.Any(x => m.Name.IndexOf(x, StringComparison.OrdinalIgnoreCase) >= 0))
            {
                continue;
            }

            string detail = string.Empty;
            if (m is FieldInfo)
            {
                detail = ((FieldInfo)m).FieldType.Name;
            }
            else if (m is PropertyInfo)
            {
                detail = ((PropertyInfo)m).PropertyType.Name;
            }
            else if (m is MethodInfo)
            {
                MethodInfo mi = (MethodInfo)m;
                detail = mi.ReturnType.Name + " (" + string.Join(", ", mi.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name).ToArray()) + ")";
            }

            Console.WriteLine("  " + m.MemberType + " " + detail + " " + m.Name);
        }
    }
}
