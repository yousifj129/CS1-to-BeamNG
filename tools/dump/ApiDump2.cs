// Throwaway developer utility (Part 1 build verification) -- second pass.
// Probes the members the exporter needs that the first dump did not cover.
//
// Build:  csc /nologo /out:tools\dump\ApiDump2.exe tools\dump\ApiDump2.cs
// Run:    tools\dump\ApiDump2.exe "E:\...\Cities_Data\Managed"

using System;
using System.Linq;
using System.Reflection;
using System.IO;

internal static class ApiDump2
{
    private static Assembly _game;
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

        _game = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp.dll"));
        _colossal = Assembly.LoadFrom(Path.Combine(managed, "ColossalManaged.dll"));

        Show("DistrictManager", "GetDistrict", "District");
        Show("BuildingManager", "m_buildings");
        Show("NetManager", "m_segments", "m_nodes", "m_lanes");
        Show("BuildingInfo", "m_cellWidth", "m_cellLength", "m_height", "m_category", "m_class", "m_subCategory", "m_size", "m_lot");
        Show("PrefabCollection`1", "m_prefabs", "m_collection");
        Show("PrefabCollection", "m_prefabs");
        ShowNested("PrefabCollection`1", "m_prefabs");
        Show("District", "m_name", "m_color", "m_flags", "m_info");
        Show("Vehicle", "m_flags");

        Console.WriteLine("===== ColossalFramework.UI =====");
        ShowColossal("ColossalFramework.UI.UIFontManager", "Default");
        ShowColossal("ColossalFramework.UI.UITextureAtlas", "GetSprite", "name", "sprites");
        ShowColossal("ColossalFramework.UI.UISpriteInfo", "sprite", "atlas", "name");
        ShowColossal("ColossalFramework.UI.UIView", "GetAView", "fixedWidth", "fixedHeight", "focusedComponent", "AddUIComponent");
        ShowColossal("ColossalFramework.UI.UIComponent", "AddUIComponent", "absolutePosition", "relativePosition", "backgroundSprite", "atlas");
        ShowColossal("ColossalFramework.UI.UITextField", "text");
        Type tf = _colossal.GetType("ColossalFramework.UI.UITextField");
        Type ta = _colossal.GetType("ColossalFramework.UI.UITextArea");
        Console.WriteLine("  UITextField=" + (tf != null) + " UITextArea=" + (ta != null));

        Type element = _game.GetType("DistrictManager");
        Console.WriteLine("===== Array8<T> (DistrictManager.m_districts) =====");
        if (element != null)
        {
            FieldInfo f = element.GetField("m_districts", BindingFlags.Public | BindingFlags.Instance);
            if (f != null)
            {
                Console.WriteLine("  district array type = " + f.FieldType.FullName);
                foreach (FieldInfo x in f.FieldType.GetFields(BindingFlags.Public | BindingFlags.Instance))
                {
                    Console.WriteLine("    " + x.FieldType.Name + " " + x.Name);
                }
            }
        }

        Console.WriteLine("===== BuildingInfo full field list =====");
        Type bi = _game.GetType("BuildingInfo");
        if (bi != null)
        {
            foreach (FieldInfo f in bi.GetFields(BindingFlags.Public | BindingFlags.Instance).OrderBy(x => x.Name))
            {
                Console.WriteLine("  " + f.FieldType.Name + " " + f.Name);
            }
        }

        Console.WriteLine("===== BuildingInfo properties =====");
        if (bi != null)
        {
            foreach (PropertyInfo p in bi.GetProperties(BindingFlags.Public | BindingFlags.Instance).OrderBy(x => x.Name))
            {
                Console.WriteLine("  " + p.PropertyType.Name + " " + p.Name);
            }
        }

        return 0;
    }

    private static void ShowNested(string name, string member)
    {
        Type t = _game.GetType(name);
        Console.WriteLine("===== nested check " + name + " -> " + member + " : " + (t == null ? "type missing" : "type ok"));
    }

    private static void Show(string name, params string[] filters)
    {
        Type t = _game.GetType(name);
        Console.WriteLine("===== " + name + " =====");
        if (t == null)
        {
            Console.WriteLine("  TYPE NOT FOUND");
            return;
        }

        foreach (FieldInfo f in t.GetFields(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (filters.Length > 0 && !filters.Any(x => f.Name.StartsWith(x, StringComparison.Ordinal)))
            {
                continue;
            }

            Console.WriteLine("  field " + f.FieldType.Name + " " + f.Name + (f.IsStatic ? " [static]" : string.Empty));
        }

        foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (filters.Length > 0 && !filters.Any(x => p.Name.StartsWith(x, StringComparison.Ordinal)))
            {
                continue;
            }

            Console.WriteLine("  prop " + p.PropertyType.Name + " " + p.Name);
        }

        foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (filters.Length == 0 || !filters.Any(x => m.Name.StartsWith(x, StringComparison.Ordinal)))
            {
                continue;
            }

            if (m.IsSpecialName)
            {
                continue;
            }

            Console.WriteLine("  method " + m.ReturnType.Name + " " + m.Name + "(" +
                string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name).ToArray()) + ")");
        }
    }

    private static void ShowColossal(string fullName, params string[] filters)
    {
        Type t = _colossal.GetType(fullName);
        Console.WriteLine("===== " + fullName + " =====");
        if (t == null)
        {
            Console.WriteLine("  TYPE NOT FOUND");
            return;
        }

        foreach (MemberInfo m in t.GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            if (filters.Length > 0 && !filters.Any(x => m.Name.StartsWith(x, StringComparison.Ordinal)))
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

            Console.WriteLine("  " + m.MemberType + " " + detail + " " + m.Name);
        }
    }
}
