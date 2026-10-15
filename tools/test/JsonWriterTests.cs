// ============================================================================================
//  CS1-to-BeamNG :: JsonWriter contract test  (tools/test/)
// ============================================================================================
//  The exporter's JSON writer is pure System.* + DTO code, so it can be exercised OUTSIDE the
//  game.  This harness builds one fully populated CityLayout and one deliberately awkward one
//  (NaN, a float, empty lists, a newline in a string, an enum) and writes them out, so the
//  Python side can prove the emitted JSON is valid and matches the documented schema.
//
//  It links against the real exporter source file, so it always tests the shipping code.
//
//  Build + run (no game needed):
//    csc /nologo /target:exe /out:build\JsonWriterTests.exe ^
//        /r:<Managed>\mscorlib.dll /r:<Managed>\System.dll /r:<Managed>\System.Core.dll ^
//        /r:<Managed>\UnityEngine.dll /r:<Managed\Assembly-CSharp.dll ^
//        /r:<Managed>\ColossalManaged.dll /r:<Managed>\ICities.dll ^
//        mod\CS1ToBeamNGExporter.cs tools\test\JsonWriterTests.cs
// ============================================================================================

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Threading;
using CS1ToBeamNGExporter;

internal static class JsonWriterTests
{
    private static int Main(string[] args)
    {
        string outputDirectory = args.Length > 0 ? args[0] : "build";
        Directory.CreateDirectory(outputDirectory);

        // Force a comma-decimal locale: if the writer leaks the current culture, the JSON breaks.
        Thread.CurrentThread.CurrentCulture = new CultureInfo("de-DE");

        CityLayout layout = BuildSampleLayout();

        string path = Path.Combine(outputDirectory, "sample_city_layout.json");
        WriteLayout(layout, path);
        Console.WriteLine("wrote " + path + " (" + new FileInfo(path).Length + " bytes)");

        CityLayout edge = BuildEdgeCaseLayout();
        string edgePath = Path.Combine(outputDirectory, "edge_case_city_layout.json");
        WriteLayout(edge, edgePath);
        Console.WriteLine("wrote " + edgePath + " (" + new FileInfo(edgePath).Length + " bytes)");

        // UTF-16 ranges that are easy to get wrong must survive a round trip.
        Console.WriteLine("culture during write was de-DE (comma decimals): " + Thread.CurrentThread.CurrentCulture.Name);

        return 0;
    }

    private static void WriteLayout(CityLayout layout, string path)
    {
        using (FileStream stream = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None))
        using (StreamWriter textWriter = new StreamWriter(stream, new UTF8Encoding(false)))
        using (JsonWriter json = new JsonWriter(textWriter))
        {
            json.WriteValue(layout);
            textWriter.Flush();
            stream.Flush();
        }
    }

    private static Vector3Dto V(float x, float y, float z)
    {
        Vector3Dto v = new Vector3Dto();
        v.X = x;
        v.Y = y;
        v.Z = z;
        return v;
    }

    private static CityLayout BuildSampleLayout()
    {
        CityLayout layout = new CityLayout();
        layout.Meta.Trigger = "test harness";
        layout.Meta.CityName = "Testburg";
        layout.Meta.ExportedAtUtc = "2024-01-01T00:00:00Z";
        layout.Meta.GameVersion = "1.17.0";
        layout.Meta.UnityVersion = "5.6.7f1";
        layout.Meta.MapTheme = "European";
        layout.Meta.RoadCount = 2;
        layout.Meta.BuildingCount = 1;
        layout.Meta.DistrictCount = 1;
        layout.Meta.ExportMilliseconds = 1234;
        layout.Meta.SimulationTick = 987654;
        layout.Meta.SkippedDeletedSegments = 3;
        layout.Meta.Warnings.Add("Segment 42: GenerateBezier failed; control points unavailable.");

        DistrictDto district = new DistrictDto();
        district.Id = 1;
        district.Name = "Downtown";
        layout.Districts.Add(district);

        RoadDto road = new RoadDto();
        road.SegmentId = 100;
        road.StartNodeId = 11;
        road.EndNodeId = 12;
        road.PrefabName = "Basic Road";
        road.RoadClass = "Road";
        road.VehicleTypes = "Car, Bicycle";
        road.IsOneWay = false;
        road.IsStraight = true;
        road.Inverted = false;
        road.HalfWidth = 8f;
        road.MeasuredWidth = 16f;
        road.LaneCount = 4;
        road.AverageLength = 64f;
        road.TrafficDensity = 128;
        road.StartPosition = V(-100f, 12.5f, 200f);
        road.EndPosition = V(-36f, 12.5f, 200f);
        road.StartDirection = V(64f, 0f, 0f);
        road.EndDirection = V(-64f, 0f, 0f);
        road.MiddlePosition = V(-68f, 12.5f, 200f);
        road.Bezier = new BezierDto
        {
            Start = V(-100f, 12.5f, 200f),
            Control1 = V(-78.666664f, 12.5f, 200f),
            Control2 = V(-57.333332f, 12.5f, 200f),
            End = V(-36f, 12.5f, 200f)
        };
        road.BezierOrientedFromStart = true;
        layout.Roads.Add(road);

        BuildingDto building = new BuildingDto();
        building.BuildingId = 7;
        building.PrefabName = "House 01";
        building.AssetTitle = "Small House";
        building.Category = "Residential";
        building.Service = "Residential";
        building.SubService = "ResidentialLow";
        building.Position = V(10f, 12f, 30f);
        building.AngleRadians = 1.5707964f;
        building.AngleDegrees = 90f;
        building.Width = 16f;
        building.Length = 24f;
        building.Height = 9.5f;
        building.PrefabSize = V(16f, 9.5f, 24f);
        building.DistrictId = 1;
        layout.Buildings.Add(building);

        return layout;
    }

    private static CityLayout BuildEdgeCaseLayout()
    {
        CityLayout layout = new CityLayout();
        layout.Meta.Trigger = "edge cases";
        layout.Meta.CityName = string.Empty;
        layout.Meta.Warnings.Add("quote \" backslash \\ newline \n tab \t done");
        layout.Meta.Warnings.Add("unicode: ü ö ä é 日本語");

        RoadDto degenerate = new RoadDto();
        degenerate.SegmentId = 0;
        degenerate.PrefabName = null;
        degenerate.RoadClass = string.Empty;
        degenerate.HalfWidth = float.NaN;
        degenerate.MeasuredWidth = float.PositiveInfinity;
        degenerate.AverageLength = float.NegativeInfinity;
        degenerate.StartPosition = V(float.NaN, 0f, 0f);
        degenerate.EndPosition = V(1e-8f, 123456.789f, -0.0004f);
        // Bezier intentionally left null.
        layout.Roads.Add(degenerate);

        BuildingDto building = new BuildingDto();
        building.BuildingId = 1;
        building.Position = V(0f, 0f, 0f);
        building.AngleRadians = -0f;
        building.DistrictId = 0;
        layout.Buildings.Add(building);

        return layout;
    }
}
