using System;
using System.IO;
using System.Linq;
using System.Reflection;

// Targeted signature dump for the exact members the exporter calls.
internal static class Sig
{
    private static Assembly _g;

    private static int Main(string[] args)
    {
        string managed = args[0];
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string n = new AssemblyName(e.Name).Name;
            string p = Path.Combine(managed, n + ".dll");
            return File.Exists(p) ? Assembly.LoadFrom(p) : null;
        };

        _g = Assembly.LoadFrom(Path.Combine(managed, "Assembly-CSharp.dll"));

        Methods("NetSegment", "GenerateBezier", "CalculateMiddlePoints", "IsStraight", "GetDirection");
        Props("Building");
        Props("BuildingInfo");
        Props("NetNode");
        Methods("BuildingManager", "GetBuildingName", "FindBuilding");
        Methods("DistrictManager", "GetDistrictName");
        EnumValues("ItemClass+Service");
        EnumValues("ItemClass+SubService");
        EnumValues("Building+Flags");
        EnumValues("District+Flags");
        StaticMembers("PrefabCollection`1");
        StaticMembers("PrefabCollection");
        TypeInfo("Bezier3");
        EnumValues("NetInfo+Direction");

        return 0;
    }

    private static void TypeInfo(string name)
    {
        Type t = _g.GetType(name);
        Console.WriteLine("===== TYPE " + name + " : " + (t == null ? "MISSING" : (t.IsValueType ? "struct" : "class")) + " =====");
        if (t == null) { return; }
        foreach (FieldInfo f in t.GetFields(BindingFlags.Public | BindingFlags.Instance))
        {
            Console.WriteLine("  field " + f.FieldType.Name + " " + f.Name);
        }
        foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance))
        {
            Console.WriteLine("  prop " + p.PropertyType.Name + " " + p.Name);
        }
    }

    private static void StaticMembers(string name)
    {
        Type t = _g.GetType(name) ?? typeof(int).Assembly.GetType(name);
        Console.WriteLine("===== STATIC " + name + " : " + (t == null ? "MISSING" : "found") + " =====");
        if (t == null) { return; }
        foreach (FieldInfo f in t.GetFields(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static))
        {
            Console.WriteLine("  static field " + f.FieldType.Name + " " + f.Name);
        }
        foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static))
        {
            if (m.IsSpecialName) { continue; }
            Console.WriteLine("  static method " + m.ReturnType.Name + " " + m.Name + "(" + string.Join(", ", m.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name).ToArray()) + ")");
        }
        foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Static))
        {
            Console.WriteLine("  static prop " + p.PropertyType.Name + " " + p.Name);
        }
    }

    private static void EnumValues(string name)
    {
        Type t = _g.GetType(name);
        Console.WriteLine("===== ENUM " + name + " : " + (t == null ? "MISSING" : string.Join(", ", Enum.GetNames(t))) + " =====");
    }

    private static void Props(string name)
    {
        Type t = _g.GetType(name);
        Console.WriteLine("===== PROPS " + name + " =====");
        if (t == null) { Console.WriteLine("  MISSING"); return; }
        foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static))
        {
            Console.WriteLine("  prop " + p.PropertyType.Name + " " + p.Name + (p.GetGetMethod(true) != null && p.GetGetMethod(true).IsStatic ? " [static]" : string.Empty));
        }
    }

    private static void Methods(string typeName, params string[] names)
    {
        Type t = _g.GetType(typeName);
        Console.WriteLine("===== METHODS " + typeName + " =====");
        if (t == null) { Console.WriteLine("  MISSING"); return; }
        foreach (MethodInfo m in t.GetMethods(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static))
        {
            if (!names.Contains(m.Name)) { continue; }
            Console.WriteLine("  " + (m.IsStatic ? "static " : string.Empty) + m.ReturnType.Name + " " + m.Name + "(" +
                string.Join(", ", m.GetParameters().Select(p => (p.IsOut ? "out " : (p.ParameterType.IsByRef ? "ref " : string.Empty)) + p.ParameterType.Name.Replace("&", string.Empty) + " " + p.Name).ToArray()) + ")");
        }
    }
}
