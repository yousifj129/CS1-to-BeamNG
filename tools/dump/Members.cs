using System;
using System.IO;
using System.Linq;
using System.Reflection;

internal static class Members
{
    private static int Main(string[] args)
    {
        string managed = args[0];
        string typeName = args[1];
        AppDomain.CurrentDomain.AssemblyResolve += (s, e) =>
        {
            string n = new AssemblyName(e.Name).Name;
            string p = Path.Combine(managed, n + ".dll");
            return File.Exists(p) ? Assembly.LoadFrom(p) : null;
        };

        foreach (string file in new[] { "Assembly-CSharp.dll", "ColossalManaged.dll", "Assembly-CSharp-firstpass.dll" })
        {
            Assembly asm;
            try { asm = Assembly.LoadFrom(Path.Combine(managed, file)); } catch { continue; }

            Type t = asm.GetType(typeName);
            if (t == null)
            {
                continue;
            }

            Console.WriteLine("===== " + t.FullName + " (in " + file + ") =====");
            foreach (MemberInfo m in t.GetMembers(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly).OrderBy(x => x.Name))
            {
                if (m.Name.StartsWith("get_") || m.Name.StartsWith("set_") || m.Name.StartsWith("add_") || m.Name.StartsWith("remove_"))
                {
                    continue;
                }

                string d = string.Empty;
                if (m is FieldInfo)
                {
                    d = ((FieldInfo)m).FieldType.Name;
                }
                else if (m is PropertyInfo)
                {
                    d = ((PropertyInfo)m).PropertyType.Name;
                }
                else if (m is MethodInfo)
                {
                    MethodInfo mi = (MethodInfo)m;
                    d = mi.ReturnType.Name + " (" + string.Join(", ", mi.GetParameters().Select(p => p.ParameterType.Name + " " + p.Name).ToArray()) + ")";
                }

                Console.WriteLine("  " + m.MemberType + " " + d + " " + m.Name);
            }

            return 0;
        }

        Console.WriteLine("type not found: " + typeName);
        return 1;
    }
}
