// Throwaway developer utility (Part 1 build verification).
// Dumps the exact CS1 API surface we depend on so the exporter can be compiled against the
// real game assemblies instead of guessed signatures.
//
// Build:  csc /nologo /out:tools\dump\ApiDump.exe tools\dump\ApiDump.cs
// Run:    tools\dump\ApiDump.exe "E:\...\Cities_Data\Managed"

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;

internal static class ApiDump
{
    private static readonly string[] InterestingFields =
    {
        "m_startNode", "m_endNode", "m_startDirection", "m_endDirection", "m_flags", "m_lanes",
        "m_averageLength", "m_trafficDensity", "m_position", "m_angle", "m_width", "m_length",
        "m_height", "m_info", "m_district", "m_halfWidth", "m_class", "m_vehicleTypes", "m_netAI",
        "m_laneType", "m_direction", "m_finalDirection", "m_vehicleType", "m_color", "m_name",
        "m_districts", "m_buildings", "m_segments", "m_nodes", "m_buffer", "m_size", "m_metaData",
        "m_CityName", "m_MapThemeMetaData", "m_currentTickIndex", "m_subCategory", "m_cellWidth",
        "m_cellLength", "m_roadWidth", "m_category"
    };

    private static Assembly _csharp;
    private static Assembly _firstpass;

    private static int Main(string[] args)
    {
        string managed = args.Length > 0 ? args[0] : @"E:\games\epic games\CitiesSkylines\Cities_Data\Managed";

        AppDomain.CurrentDomain.AssemblyResolve += (sender, e) =>
        {
            string simpleName = new AssemblyName(e.Name).Name;
            string candidate = Path.Combine(managed, simpleName + ".dll");
            return File.Exists(candidate) ? Assembly.LoadFrom(candidate) : null;
        };

        _csharp = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp.dll"));
        _firstpass = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp-firstpass.dll"));

        Console.WriteLine("Assembly-CSharp: " + _csharp.GetName().Version);

        ShowType("NetSegment", "m_", "Info");
        ShowStaticMethods("NetSegment", "Calculate");
        ShowNestedEnum("NetSegment", "Flags");
        ShowType("NetNode", "m_");
        ShowType("NetInfo", "m_halfWidth", "m_lanes", "m_class", "m_vehicleTypes", "m_flags", "m_netAI", "m_width", "m_roadWidth", "m_connectGroup", "m_hasTrafficLights", "m_averageVehicleLaneSpeed");
        ShowType("NetInfo+Lane", "m_position", "m_width", "m_direction", "m_finalDirection", "m_laneType", "m_vehicleType", "m_speedLimit");
        ShowNestedEnum("NetInfo", "ItemClass");
        ShowType("ItemClass", "m_name", "name");
        ShowType("Building", "m_position", "m_angle", "m_width", "m_length", "m_height", "m_flags", "m_info", "m_district");
        ShowNestedEnum("Building", "Flags");
        ShowType("BuildingInfo", "m_subCategory", "m_cellWidth", "m_cellLength", "m_width", "m_length", "category");
        ShowType("District", "m_flags", "m_color", "m_name", "m_info");
        ShowNestedEnum("District", "Flags");
        ShowType("DistrictManager", "m_districts");
        ShowType("SimulationManager", "m_metaData", "m_currentTickIndex");
        ShowType("SimulationMetaData", "m_CityName", "m_MapThemeMetaData");
        ShowType("MapThemeMetaData", "name");
        ShowType("Array16`1", "m_buffer", "m_size");
        ShowType("PrefabInfo", "name", "m_class");
        ShowStaticFields("VehicleInfo", "VehicleType");
        ShowNestedEnum("VehicleInfo", "VehicleType");
        ShowNestedEnum("NetInfo", "LaneType");
        ShowNestedEnum("NetInfo", "Direction");

        // UI types live in ColossalManaged.dll.
        try
        {
            Assembly colossal = Assembly.LoadFrom(Path.Combine(managed, "ColossalManaged.dll"));
            Type panel = colossal.GetType("ColossalFramework.UI.UIPanel");
            Type button = colossal.GetType("ColossalFramework.UI.UIButton");
            Type label = colossal.GetType("ColossalFramework.UI.UILabel");
            Console.WriteLine("===== UI present: UIPanel=" + (panel != null) + " UIButton=" + (button != null) + " UILabel=" + (label != null));

            if (panel != null)
            {
                Console.WriteLine("  UIPanel AddUIComponent: " + Describe(panel.GetMethods().FirstOrDefault(m => m.Name == "AddUIComponent")));
            }

            if (button != null)
            {
                foreach (string m in new[] { "eventClick", "textScale", "wordWrap", "autoSize", "playAudioEvents", "normalBgSprite", "hoveredBgSprite", "pressedBgSprite", "focusedBgSprite", "disabledBgSprite", "hoveredTextColor" })
                {
                    MemberInfo member = (MemberInfo)button.GetEvent(m) ?? button.GetField(m) ?? (MemberInfo)button.GetProperty(m);
                    Console.WriteLine("  UIButton." + m + " -> " + (member == null ? "MISSING" : member.MemberType.ToString()));
                }
            }

            Type fontManager = colossal.GetType("ColossalFramework.UI.UIFontManager");
            Console.WriteLine("  UIFontManager.Default -> " + (fontManager == null || fontManager.GetField("Default") == null ? "MISSING" : fontManager.GetField("Default").FieldType.Name));
            Type atlas = colossal.GetType("ColossalFramework.UI.UITextureAtlas");
            Console.WriteLine("  UITextureAtlas.GetSprite -> " + Describe(atlas == null ? null : atlas.GetMethod("GetSprite")));
        }
        catch (Exception e)
        {
            Console.WriteLine("UI dump failed: " + e.Message);
        }

        return 0;
    }

    private static string Describe(MethodInfo method)
    {
        if (method == null)
        {
            return "MISSING";
        }

        return method.ReturnType.Name + " (" + string.Join(", ", method.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name).ToArray()) + ")";
    }

    private static Type Resolve(string name)
    {
        Type t = _csharp.GetType(name, false);
        if (t == null)
        {
            t = _firstpass.GetType(name, false);
        }

        return t;
    }

    private static void ShowType(string name, params string[] filters)
    {
        Type t = Resolve(name);
        if (t == null)
        {
            Console.WriteLine("===== " + name + " :: TYPE NOT FOUND");
            return;
        }

        Console.WriteLine("===== " + name + (t.IsValueType ? " (struct)" : string.Empty) + " =====");

        foreach (FieldInfo f in t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            if (filters.Length > 0 && !filters.Any(x => f.Name.StartsWith(x, StringComparison.Ordinal)))
            {
                continue;
            }

            Console.WriteLine("  field " + f.FieldType.Name + " " + f.Name);
        }

        foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
        {
            if (filters.Length > 0 && !filters.Any(x => p.Name.StartsWith(x, StringComparison.Ordinal)))
            {
                continue;
            }

            Console.WriteLine("  prop  " + p.PropertyType.Name + " " + p.Name);
        }
    }

    private static void ShowStaticMethods(string name, string prefix)
    {
        Type t = Resolve(name);
        if (t == null)
        {
            return;
        }

        Console.WriteLine("===== " + name + " static methods starting with '" + prefix + "' =====");
        foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.Static))
        {
            if (!m.Name.StartsWith(prefix, StringComparison.Ordinal))
            {
                continue;
            }

            Console.WriteLine("  " + Describe(m));
        }
    }

    private static void ShowStaticFields(string name, string prefix)
    {
        Type t = Resolve(name);
        if (t == null)
        {
            return;
        }

        Console.WriteLine("===== " + name + " static fields starting with '" + prefix + "' =====");
        foreach (FieldInfo f in t.GetFields(BindingFlags.Public | BindingFlags.Static))
        {
            if (!f.Name.StartsWith(prefix, StringComparison.Ordinal))
            {
                continue;
            }

            Console.WriteLine("  " + f.FieldType.Name + " " + f.Name);
        }
    }

    private static void ShowNestedEnum(string name, string enumName)
    {
        Type t = Resolve(name);
        if (t == null)
        {
            return;
        }

        Type e = t.GetNestedType(enumName, BindingFlags.Public | BindingFlags.NonPublic);
        if (e == null)
        {
            Console.WriteLine("===== " + name + "." + enumName + " :: NOT FOUND");
            return;
        }

        Console.WriteLine("===== " + name + "." + enumName + " = " + string.Join(", ", Enum.GetNames(e)));
    }
}
