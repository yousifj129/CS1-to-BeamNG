// ============================================================================================
//  CS1-to-BeamNG :: Part 1 :: Cities: Skylines 1 Data Exporter
// ============================================================================================
//  A single-file Cities: Skylines 1 mod that walks the live simulation and dumps every road
//  segment (as an exact cubic Bezier with its control points) and every placed building
//  (position / rotation / footprint / prefab) into a structured `city_layout.json`.
//
//  Every game API member used below was verified by reflection against the real
//  Assembly-CSharp.dll / ColossalManaged.dll of Cities: Skylines 1.17 (see tools/dump/).
//
//  Depends only on: UnityEngine, ColossalFramework, ColossalFramework.UI, ICities,
//                   System, System.IO, System.Reflection, System.Globalization.
//  No Newtonsoft, no System.Text.Json, no Harmony, no external DLLs.
//
//  ---------------------------------------------------------------------------------------
//  INSTALL (no compiler needed -- the game compiles this for you)
//  ---------------------------------------------------------------------------------------
//    1. Create this folder:
//         %LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\Mods\CS1ToBeamNGExporter\
//    2. Drop this single .cs file inside it.  The folder must contain EXACTLY ONE .cs file:
//       the in-game compiler compiles every .cs in the folder into one assembly, and this
//       file is deliberately self-contained for that reason.
//    3. Start Cities: Skylines.  It compiles the file on startup into
//         <Install>\Cities_Data\Mods\CS1ToBeamNGExporter.dll
//       Compile errors go to: %LOCALAPPDATA%\Colossal Order\Cities_Skylines\output_log.txt
//    4. Content Manager > Mods > enable "CS1-to-BeamNG Exporter".
//    5. Load a save, then press Ctrl+Shift+E or click "EXPORT CITY JSON".
//       The JSON is written to your Desktop under CS1ToBeamNG\ (see the log line for the
//       exact path; the game folder and persistentDataPath are used as fallbacks).
//
//  ---------------------------------------------------------------------------------------
//  JSON SHAPE (stable contract for Part 2 -- the Python converter)
//  ---------------------------------------------------------------------------------------
//    {
//      "schemaVersion": 1,
//      "meta":      { provenance: game version, city name, counts, skipped slots, warnings },
//      "districts": [ { "id", "name" } ],
//      "roads":     [ { "segmentId", "startNodeId", "endNodeId", "prefabName", "roadClass",
//                       "vehicleTypes", "isOneWay", "isStraight", "halfWidth",
//                       "measuredWidth", "laneCount", "averageLength", "trafficDensity",
//                       "startPosition":{x,y,z}, "endPosition":{...},
//                       "startDirection":{...}, "endDirection":{...},
//                       "middlePosition":{...},
//                       "bezier":{ "start","control1","control2","end" } } ],
//      "buildings": [ { "buildingId", "prefabName", "assetTitle", "category",
//                       "service", "subService", "position":{x,y,z},
//                       "angleRadians", "angleDegrees", "width", "length", "height",
//                       "prefabSize":{x,y,z}, "districtId", "isCollapsed", "isAbandoned" } ]
//    }
//
//  COORDINATE SYSTEM: metres in Unity left-handed Y-up space exactly as the game stores them.
//  No conversion happens here on purpose -- Part 2 owns the Unity -> BeamNG axis mapping
//  (BeamNG is right-handed Z-up: x_bng = -x_cs1, y_bng = z_cs1, z_bng = y_cs1).  Keeping the
//  raw values makes the exporter auditable and keeps the conversion testable in pure Python.
// ============================================================================================

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using ColossalFramework;
using ColossalFramework.Globalization;
using ColossalFramework.Math;
using ColossalFramework.UI;
using ICities;
using UnityEngine;

namespace CS1ToBeamNGExporter
{
    // ========================================================================================
    //  0.  CONSTANTS
    // ========================================================================================
    internal static class ModInfo
    {
        public const string Name = "CS1-to-BeamNG Exporter";
        public const string Version = "1.1.0";
        public const int SchemaVersion = 1;
        public const string OutputFileName = "city_layout.json";
        public const string LogFileName = "CS1ToBeamNGExporter.log";

        /// <summary>CS1 stores building m_width/m_length in whole 8 m cells.</summary>
        public const float BuildingCellSize = 8f;

        /// <summary>
        /// Optional project folder for the pipeline.  When this path exists, the export is
        /// written here FIRST (into an "exports" subfolder) and to the Desktop as well, so the
        /// converter can pick the newest file up without any copying.  Leave empty to disable.
        /// </summary>
        public const string ProjectExportDirectory = @"D:\Developer\open source projects\cities-skylines-to-beamng-map\exports";
    }

    // ========================================================================================
    //  1.  MOD ENTRY POINT  (IUserMod)
    // ========================================================================================
    public class CS1ToBeamNGExporterMod : IUserMod
    {
        public string Name
        {
            get { return ModInfo.Name; }
        }

        public string Description
        {
            get { return "Exports roads, buildings and districts to city_layout.json for the BeamNG.drive converter. Hotkey: Ctrl+Shift+E."; }
        }

        public void OnSettingsUI(UIHelperBase helper)
        {
            try
            {
                UIHelperBase group = helper.AddGroup(ModInfo.Name + " v" + ModInfo.Version);
                group.AddButton("Export now (needs a loaded city)", () => Exporter.RequestExport("settings button"));
                group.AddButton("Open export folder", Exporter.OpenOutputDirectory);
                group.AddButton("Log last export report", Exporter.PrintLastReport);
            }
            catch (Exception e)
            {
                ModLog.Error("OnSettingsUI failed", e);
            }
        }
    }

    // ========================================================================================
    //  2.  LOADING EXTENSION  (ICities.LoadingExtensionBase)
    // ========================================================================================
    public class ExporterLoadingExtension : LoadingExtensionBase
    {
        private ExporterRunner _runner;

        public override void OnLevelLoaded(LoadMode mode)
        {
            if (mode != LoadMode.NewGame && mode != LoadMode.LoadGame &&
                mode != LoadMode.NewGameFromScenario && mode != LoadMode.LoadScenario)
            {
                return; // No UI in the map/asset editors or the main menu.
            }

            try
            {
                Exporter.Reset();
                GameObject host = new GameObject("CS1ToBeamNGExporter_Host");
                UnityEngine.Object.DontDestroyOnLoad(host);
                _runner = host.AddComponent<ExporterRunner>();
                _runner.BuildUI();
                ModLog.Info("Ready. Hotkey = " + ExporterRunner.HotkeyDescription + ".");
            }
            catch (Exception e)
            {
                ModLog.Error("OnLevelLoaded failed", e);
            }
        }

        public override void OnLevelUnloading()
        {
            try
            {
                if (_runner != null)
                {
                    UnityEngine.Object.Destroy(_runner.gameObject);
                    _runner = null;
                }

                Exporter.Reset();
            }
            catch (Exception e)
            {
                ModLog.Error("OnLevelUnloading failed", e);
            }
        }

        public override void OnReleased()
        {
            OnLevelUnloading();
        }
    }

    // ========================================================================================
    //  3.  RUNTIME RUNNER  -- UI + hotkey + the batched coroutine that does the work, so a
    //      100k-segment city cannot freeze the editor.
    // ========================================================================================
    public class ExporterRunner : MonoBehaviour
    {
        public const KeyCode Hotkey = KeyCode.E;
        public const string HotkeyDescription = "Ctrl+Shift+E";
        public const string PanelName = "CS1ToBeamNGExporterPanel";

        private const int SegmentsPerFrame = 1500;
        private const int BuildingsPerFrame = 3000;

        private ExporterPanel _panel;
        private CityLayout _layout;
        private bool _busy;

        public void BuildUI()
        {
            try
            {
                UIView view = UIView.GetAView();
                if (view == null)
                {
                    ModLog.Warn("UIView.GetAView() returned null; no UI button (the hotkey still works).");
                    return;
                }

                if (view.FindUIComponent<ExporterPanel>(PanelName) != null)
                {
                    return; // already built for this view
                }

                _panel = view.AddUIComponent(typeof(ExporterPanel)) as ExporterPanel;
                if (_panel == null)
                {
                    ModLog.Warn("Could not create the exporter panel (the hotkey still works).");
                    return;
                }

                _panel.Setup(this);
            }
            catch (Exception e)
            {
                ModLog.Error("BuildUI failed", e);
            }
        }

        private void Update()
        {
            if (_busy || _panel == null)
            {
                return;
            }

            try
            {
                bool ctrl = Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl);
                bool shift = Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift);

                if (ctrl && shift && Input.GetKeyDown(Hotkey) && !TextInputActive())
                {
                    BeginExport("hotkey " + HotkeyDescription);
                }
            }
            catch (Exception e)
            {
                ModLog.Error("Update failed", e);
            }
        }

        /// <summary>True while the player is typing into a text field, so hotkeys must not fire.</summary>
        private static bool TextInputActive()
        {
            try
            {
                // UIView.HasInputFocus is a static member on this game version.
                return UIView.HasInputFocus();
            }
            catch
            {
                return false;
            }
        }

        // ------------------------------------------------------------------------------------
        //  Export entry point -- used by the panel button, the hotkey and the settings UI.
        // ------------------------------------------------------------------------------------
        public void BeginExport(string trigger)
        {
            if (_busy)
            {
                ModLog.Warn("An export is already running; ignoring trigger (" + trigger + ").");
                return;
            }

            if (!IsSimulationReady())
            {
                ModLog.Warn("No city loaded yet; ignoring trigger (" + trigger + ").");
                if (_panel != null)
                {
                    _panel.SetStatus("Load a city first");
                }

                return;
            }

            StartCoroutine(ExportRoutine(trigger));
        }

        private static bool IsSimulationReady()
        {
            try
            {
                SimulationManager simulation = Singleton<SimulationManager>.instance;
                return simulation != null && simulation.m_metaData != null;
            }
            catch
            {
                return false;
            }
        }

        private IEnumerator ExportRoutine(string trigger)
        {
            _busy = true;
            System.Diagnostics.Stopwatch stopwatch = System.Diagnostics.Stopwatch.StartNew();

            if (_panel != null)
            {
                _panel.SetBusy(true);
                _panel.SetStatus("Exporting...");
            }

            _layout = new CityLayout();
            _layout.Meta = ExportMetadata.Collect(trigger);

            // ---- Phase 1: districts ---------------------------------------------------------
            yield return null;
            try
            {
                ExportHarvester.HarvestDistricts(_layout);
            }
            catch (Exception e)
            {
                ModLog.Error("District harvest failed", e);
                _layout.Meta.Warnings.Add("District harvest failed: " + e.Message);
            }

            // ---- Phase 2: road network ------------------------------------------------------
            if (_panel != null)
            {
                _panel.SetStatus("Reading roads...");
            }

            yield return null;

            NetSegment[] segmentBuffer = null;
            int segmentCount = 0;

            try
            {
                NetManager netManager = Singleton<NetManager>.instance;
                segmentBuffer = netManager.m_segments.m_buffer;
                segmentCount = Math.Min((int)netManager.m_segments.m_size, segmentBuffer.Length);
            }
            catch (Exception e)
            {
                ModLog.Error("NetManager unavailable", e);
                _layout.Meta.Warnings.Add("NetManager unavailable: " + e.Message);
            }

            // C# forbids "yield return" inside a try block that has a catch clause, so the
            // per-item work sits in its own try/catch and only the frame hand-back is outside.
            if (segmentBuffer != null)
            {
                int frameBudget = 0;

                for (int i = 0; i < segmentCount; i++)
                {
                    RoadDto road = null;

                    try
                    {
                        road = ExportHarvester.ReadSegment(segmentBuffer, i, _layout.Meta);
                    }
                    catch (Exception e)
                    {
                        _layout.Meta.Warnings.Add("Segment " + i + " failed: " + e.Message);
                    }

                    if (road != null)
                    {
                        _layout.Roads.Add(road);
                    }

                    if (++frameBudget >= SegmentsPerFrame)
                    {
                        frameBudget = 0;
                        if (_panel != null)
                        {
                            _panel.SetStatus("Roads " + i + " / " + segmentCount);
                        }

                        yield return null;
                    }
                }
            }

            // ---- Phase 3: buildings ---------------------------------------------------------
            if (_panel != null)
            {
                _panel.SetStatus("Reading buildings...");
            }

            yield return null;

            Building[] buildingBuffer = null;
            int buildingCount = 0;

            try
            {
                BuildingManager buildingManager = Singleton<BuildingManager>.instance;
                buildingBuffer = buildingManager.m_buildings.m_buffer;
                buildingCount = Math.Min((int)buildingManager.m_buildings.m_size, buildingBuffer.Length);
            }
            catch (Exception e)
            {
                ModLog.Error("BuildingManager unavailable", e);
                _layout.Meta.Warnings.Add("BuildingManager unavailable: " + e.Message);
            }

            if (buildingBuffer != null)
            {
                int frameBudget = 0;

                for (int i = 0; i < buildingCount; i++)
                {
                    BuildingDto building = null;

                    try
                    {
                        building = ExportHarvester.ReadBuilding(buildingBuffer, i, _layout.Meta);
                    }
                    catch (Exception e)
                    {
                        _layout.Meta.Warnings.Add("Building " + i + " failed: " + e.Message);
                    }

                    if (building != null)
                    {
                        _layout.Buildings.Add(building);
                    }

                    if (++frameBudget >= BuildingsPerFrame)
                    {
                        frameBudget = 0;
                        if (_panel != null)
                        {
                            _panel.SetStatus("Buildings " + i + " / " + buildingCount);
                        }

                        yield return null;
                    }
                }
            }

            // ---- Phase 4: serialize + write -------------------------------------------------
            if (_panel != null)
            {
                _panel.SetStatus("Writing JSON...");
            }

            yield return null;

            stopwatch.Stop();
            _layout.Meta.ExportMilliseconds = stopwatch.ElapsedMilliseconds;
            _layout.Meta.RoadCount = _layout.Roads.Count;
            _layout.Meta.BuildingCount = _layout.Buildings.Count;
            _layout.Meta.DistrictCount = _layout.Districts.Count;

            string writtenPath = null;

            try
            {
                writtenPath = ExportWriter.Write(_layout);
            }
            catch (Exception e)
            {
                ModLog.Error("Writing " + ModInfo.OutputFileName + " failed", e);
            }

            if (writtenPath != null)
            {
                ModLog.Info(string.Format(CultureInfo.InvariantCulture,
                    "Export complete: {0} roads, {1} buildings, {2} districts in {3} ms -> {4}",
                    _layout.Roads.Count, _layout.Buildings.Count, _layout.Districts.Count,
                    stopwatch.ElapsedMilliseconds, writtenPath));

                for (int w = 0; w < _layout.Meta.Warnings.Count; w++)
                {
                    ModLog.Warn("  - " + _layout.Meta.Warnings[w]);
                }

                if (_panel != null)
                {
                    _panel.SetStatus(_layout.Roads.Count + " roads / " + _layout.Buildings.Count + " buildings");
                }
            }
            else if (_panel != null)
            {
                _panel.SetStatus("Export FAILED (see log)");
            }

            _busy = false;
            if (_panel != null)
            {
                _panel.SetBusy(false);
            }
        }
    }

    // ========================================================================================
    //  4.  THE UI  -- one small draggable panel, built from the game's own "Ingame" atlas.
    // ========================================================================================
    public class ExporterPanel : UIPanel
    {
        private const string AtlasName = "Ingame";
        private const string PanelSprite = "InfoPanelBack";
        private const string ButtonSprite = "ButtonMenu";
        private const string ButtonHoverSprite = "ButtonMenuHover";
        private const string ButtonPressedSprite = "ButtonMenuPressed";

        private ExporterRunner _runner;
        private UIButton _exportButton;
        private UILabel _statusLabel;

        public void Setup(ExporterRunner runner)
        {
            _runner = runner;

            try
            {
                name = ExporterRunner.PanelName;
                isVisible = true;
                isInteractive = true;
                canFocus = true;
                color = new Color32(255, 255, 255, 255);

                // Size first: absolutePosition (assigned below) depends on it.
                width = 214f;
                height = 98f;

                UITextureAtlas atlas = null;
                try
                {
                    atlas = UIView.GetAView() != null ? UIView.GetAView().defaultAtlas : null;
                }
                catch (Exception e)
                {
                    ModLog.Warn("defaultAtlas unavailable: " + e.Message);
                }

                if (atlas == null)
                {
                    atlas = FindAtlas(AtlasName);
                }

                if (atlas != null && atlas[PanelSprite] != null)
                {
                    this.atlas = atlas;
                    backgroundSprite = PanelSprite;
                }

                UIView view = UIView.GetAView();
                if (view != null)
                {
                    absolutePosition = new Vector3(
                        view.fixedWidth - width - 24f,
                        view.fixedHeight - height - 200f);
                }

                BuildButton(atlas);
                BuildStatusLabel();

                ModLog.Info("Export button added. Hotkey = " + ExporterRunner.HotkeyDescription + ".");
            }
            catch (Exception e)
            {
                ModLog.Error("ExporterPanel.Setup failed", e);
            }
        }

        private void BuildButton(UITextureAtlas atlas)
        {
            _exportButton = AddUIComponent<UIButton>();
            _exportButton.name = "ExportButton";
            _exportButton.text = "EXPORT CITY JSON";
            _exportButton.textScale = 0.85f;
            _exportButton.textColor = new Color32(255, 255, 255, 255);
            _exportButton.hoveredTextColor = new Color32(255, 240, 160, 255);
            _exportButton.pressedTextColor = new Color32(200, 200, 200, 255);
            _exportButton.disabledTextColor = new Color32(140, 140, 140, 255);
            _exportButton.wordWrap = false;
            _exportButton.autoSize = false;
            _exportButton.size = new Vector2(198f, 38f);
            _exportButton.relativePosition = new Vector3(8f, 8f);
            _exportButton.playAudioEvents = true;

            if (atlas != null)
            {
                _exportButton.atlas = atlas;
                if (atlas[ButtonSprite] != null)
                {
                    _exportButton.normalBgSprite = ButtonSprite;
                }

                if (atlas[ButtonHoverSprite] != null)
                {
                    _exportButton.hoveredBgSprite = ButtonHoverSprite;
                    _exportButton.focusedBgSprite = ButtonHoverSprite;
                }

                if (atlas[ButtonPressedSprite] != null)
                {
                    _exportButton.pressedBgSprite = ButtonPressedSprite;
                }
            }

            UIFont font = ResolveFont();
            if (font != null)
            {
                _exportButton.font = font;
            }

            _exportButton.eventClick += OnExportClicked;
        }

        private void BuildStatusLabel()
        {
            _statusLabel = AddUIComponent<UILabel>();
            _statusLabel.name = "StatusLabel";
            _statusLabel.text = "Hotkey: " + ExporterRunner.HotkeyDescription;
            _statusLabel.textScale = 0.7f;
            _statusLabel.textColor = new Color32(190, 200, 210, 255);
            _statusLabel.autoSize = false;
            _statusLabel.size = new Vector2(198f, 34f);
            _statusLabel.relativePosition = new Vector3(8f, 50f);

            UIFont font = ResolveFont();
            if (font != null)
            {
                _statusLabel.font = font;
            }
        }

        private static UIFont ResolveFont()
        {
            try
            {
                UIView view = UIView.GetAView();
                return view != null ? view.defaultFont : null;
            }
            catch
            {
                return null;
            }
        }

        private static UITextureAtlas FindAtlas(string atlasName)
        {
            try
            {
                UITextureAtlas[] atlases = Resources.FindObjectsOfTypeAll<UITextureAtlas>();
                if (atlases == null)
                {
                    return null;
                }

                for (int i = 0; i < atlases.Length; i++)
                {
                    if (atlases[i] != null && atlases[i].name == atlasName)
                    {
                        return atlases[i];
                    }
                }
            }
            catch (Exception e)
            {
                ModLog.Warn("FindAtlas('" + atlasName + "') failed: " + e.Message);
            }

            return null;
        }

        private void OnExportClicked(UIComponent component, UIMouseEventParameter eventParam)
        {
            try
            {
                if (_runner != null)
                {
                    _runner.BeginExport("UI button");
                }
            }
            catch (Exception e)
            {
                ModLog.Error("Button click handler failed", e);
            }
        }

        /// <summary>Locks the button while an export coroutine is running.</summary>
        public void SetBusy(bool busy)
        {
            try
            {
                if (_exportButton != null)
                {
                    _exportButton.isEnabled = !busy;
                }
            }
            catch (Exception e)
            {
                ModLog.Error("SetBusy failed", e);
            }
        }

        public void SetStatus(string text)
        {
            try
            {
                if (_statusLabel != null)
                {
                    _statusLabel.text = text ?? string.Empty;
                }
            }
            catch
            {
                // Status text is cosmetic; never let it break an export.
            }
        }
    }

    // ========================================================================================
    //  5.  HARVESTERS  -- read the live simulation into plain data objects.
    //      Every field access is defensive: prefab classes vary between game versions and
    //      workshop content, and one bad prefab must never abort the whole export.
    // ========================================================================================
    internal static class ExportHarvester
    {
        // ---- Roads ----------------------------------------------------------------------
        /// <summary>Reads one NetSegment.  Returns null when the slot is empty or unreadable.</summary>
        public static RoadDto ReadSegment(NetSegment[] buffer, int index, ExportMeta meta)
        {
            try
            {
                if (buffer == null || index < 0 || index >= buffer.Length)
                {
                    return null;
                }

                NetSegment segment = buffer[index];
                NetSegment.Flags flags = segment.m_flags;

                if ((flags & NetSegment.Flags.Created) == NetSegment.Flags.None)
                {
                    return null;
                }

                if ((flags & (NetSegment.Flags.Deleted | NetSegment.Flags.Collapsed)) != NetSegment.Flags.None)
                {
                    meta.SkippedDeletedSegments++;
                    return null;
                }

                if (segment.m_startNode == 0 || segment.m_endNode == 0)
                {
                    meta.SkippedIncompleteSegments++;
                    return null;
                }

                NetInfo info = segment.Info;
                if (info == null)
                {
                    meta.SkippedNoPrefabSegments++;
                    return null;
                }

                ushort id = (ushort)index;
                NetNode[] nodes = Singleton<NetManager>.instance.m_nodes.m_buffer;

                RoadDto road = new RoadDto();
                road.SegmentId = index;
                road.StartNodeId = segment.m_startNode;
                road.EndNodeId = segment.m_endNode;
                road.PrefabName = ReadPrefabName(info);
                road.RoadClass = ReadClassName(info);
                road.VehicleTypes = ReadVehicleTypes(info);
                road.IsOneWay = ReadIsOneWay(info);
                road.IsStraight = segment.IsStraight();
                road.Inverted = (flags & NetSegment.Flags.Invert) != NetSegment.Flags.None;
                road.AverageLength = SafeFloat(segment.m_averageLength);
                road.TrafficDensity = segment.m_trafficDensity;
                road.HalfWidth = SafeFloat(info.m_halfWidth);
                road.MeasuredWidth = MeasureRoadWidth(info, road.HalfWidth);
                road.LaneCount = info.m_lanes != null ? info.m_lanes.Length : 0;

                road.StartPosition = ToVector3Dto(ReadNodePosition(nodes, segment.m_startNode));
                road.EndPosition = ToVector3Dto(ReadNodePosition(nodes, segment.m_endNode));
                road.StartDirection = ToVector3Dto(segment.m_startDirection);
                road.EndDirection = ToVector3Dto(segment.m_endDirection);
                road.MiddlePosition = ToVector3Dto(segment.m_middlePosition);

                // The authoritative road shape: the game's own cubic Bezier for this segment,
                // oriented from the START node (isStart = true) so it matches our field order.
                // GenerateBezier is an instance method on NetSegment, so pass the struct by value.
                BezierDto bezier = ReadBezier(segment, id, segment.m_startNode);
                road.Bezier = bezier;
                road.BezierOrientedFromStart = bezier != null;

                if (bezier == null)
                {
                    meta.Warnings.Add("Segment " + index + ": GenerateBezier failed; control points unavailable.");
                }

                return road;
            }
            catch (Exception e)
            {
                meta.Warnings.Add("Segment " + index + " skipped: " + e.Message);
                meta.SkippedUnreadableSegments++;
                return null;
            }
        }

        /// <summary>
        /// NetSegment.GenerateBezier(segmentID, startNodeID) returns the segment's centre-line as
        /// a cubic Bezier (ColossalFramework.Math.Bezier3) whose control points already encode
        /// CS1's three-part road shape.  Passing the START node id keeps it oriented start->end.
        /// </summary>
        private static BezierDto ReadBezier(NetSegment segment, ushort segmentId, ushort startNodeId)
        {
            try
            {
                Bezier3 curve = segment.GenerateBezier(segmentId, startNodeId);

                BezierDto dto = new BezierDto();
                dto.Start = ToVector3Dto(curve.a);
                dto.Control1 = ToVector3Dto(curve.b);
                dto.Control2 = ToVector3Dto(curve.c);
                dto.End = ToVector3Dto(curve.d);
                return dto;
            }
            catch (Exception e)
            {
                ModLog.Warn("GenerateBezier(" + segmentId + ") failed: " + e.Message);
                return null;
            }
        }

        private static Vector3 ReadNodePosition(NetNode[] nodes, ushort nodeId)
        {
            try
            {
                if (nodes == null || nodeId >= nodes.Length)
                {
                    return Vector3.zero;
                }

                return nodes[nodeId].m_position;
            }
            catch
            {
                return Vector3.zero;
            }
        }

        /// <summary>
        /// Road width in metres, measured from the prefab's lane layout:
        /// outermost lane offset plus half of that lane's width, mirrored on both sides.
        /// Falls back to the prefab half-width; Part 2 decides how to map it onto BeamNG.
        /// </summary>
        private static float MeasureRoadWidth(NetInfo info, float halfWidth)
        {
            try
            {
                if (info.m_lanes != null && info.m_lanes.Length > 0)
                {
                    float maxOffset = 0f;
                    bool found = false;

                    for (int i = 0; i < info.m_lanes.Length; i++)
                    {
                        NetInfo.Lane lane = info.m_lanes[i];
                        float offset = SafeFloat(lane.m_position);
                        if (Math.Abs(offset) < 0.01f)
                        {
                            continue;
                        }

                        found = true;
                        float outer = Math.Abs(offset) + SafeFloat(lane.m_width) * 0.5f;
                        if (outer > maxOffset)
                        {
                            maxOffset = outer;
                        }
                    }

                    if (found && maxOffset > 0.01f)
                    {
                        return SafeFloat(maxOffset * 2f);
                    }
                }
            }
            catch
            {
                // fall through to the prefab half-width
            }

            return SafeFloat(halfWidth * 2f);
        }

        private static string ReadClassName(NetInfo info)
        {
            try
            {
                return info.m_class.name ?? "Unknown";
            }
            catch
            {
                return "Unknown";
            }
        }

        private static string ReadVehicleTypes(NetInfo info)
        {
            try
            {
                return info.m_vehicleTypes.ToString();
            }
            catch
            {
                return "None";
            }
        }

        private static bool ReadIsOneWay(NetInfo info)
        {
            try
            {
                return info.IsOneWay();
            }
            catch
            {
                return false;
            }
        }

        // ---- Buildings ------------------------------------------------------------------
        /// <summary>Reads one Building.  Returns null when the slot is empty or unreadable.</summary>
        public static BuildingDto ReadBuilding(Building[] buffer, int index, ExportMeta meta)
        {
            try
            {
                if (buffer == null || index < 0 || index >= buffer.Length)
                {
                    return null;
                }

                Building building = buffer[index];
                Building.Flags flags = building.m_flags;

                if ((flags & Building.Flags.Created) == Building.Flags.None)
                {
                    return null;
                }

                if ((flags & Building.Flags.Deleted) != Building.Flags.None)
                {
                    meta.SkippedDeletedBuildings++;
                    return null;
                }

                BuildingInfo info = building.Info;

                BuildingDto dto = new BuildingDto();
                dto.BuildingId = index;
                dto.PrefabName = ReadPrefabName(info);
                dto.AssetTitle = ReadAssetTitle(info);
                dto.Category = ReadCategory(info);
                dto.Service = ReadService(info);
                dto.SubService = ReadSubService(info);

                dto.Position = ToVector3Dto(building.m_position);
                dto.AngleRadians = SafeFloat(building.m_angle);
                dto.AngleDegrees = SafeFloat(building.m_angle * Mathf.Rad2Deg);

                // Building.m_width / m_length are whole 8 m cells, NOT metres.
                int cells = building.Width;
                if (cells <= 0)
                {
                    cells = building.m_width;
                }

                int cellLength = building.Length;
                if (cellLength <= 0)
                {
                    cellLength = building.m_length;
                }

                dto.Width = SafeFloat(cells * ModInfo.BuildingCellSize);
                dto.Length = SafeFloat(cellLength * ModInfo.BuildingCellSize);

                // The prefab carries the real mesh bounding box (metres) -- the best proxy size
                // for a physics box, and the only place a building height is available.
                if (info != null)
                {
                    Vector3 size = info.m_size;
                    dto.PrefabSize = ToVector3Dto(size);
                    dto.Height = SafeFloat(size.y);

                    if (dto.Width <= 0.01f && info.m_cellWidth > 0)
                    {
                        dto.Width = SafeFloat(info.m_cellWidth * ModInfo.BuildingCellSize);
                    }

                    if (dto.Length <= 0.01f && info.m_cellLength > 0)
                    {
                        dto.Length = SafeFloat(info.m_cellLength * ModInfo.BuildingCellSize);
                    }
                }

                dto.DistrictId = ReadDistrictId(building.m_position);
                dto.IsCollapsed = (flags & Building.Flags.Collapsed) != Building.Flags.None;
                dto.IsAbandoned = (flags & Building.Flags.Abandoned) != Building.Flags.None;
                dto.IsHistorical = (flags & Building.Flags.Historical) != Building.Flags.None;

                return dto;
            }
            catch (Exception e)
            {
                meta.Warnings.Add("Building " + index + " skipped: " + e.Message);
                meta.SkippedUnreadableBuildings++;
                return null;
            }
        }

        /// <summary>
        /// The Building struct in this game version has no district field, so the district is
        /// sampled from the building's world position (0 = no district).
        /// </summary>
        private static ushort ReadDistrictId(Vector3 position)
        {
            try
            {
                return Singleton<DistrictManager>.instance.GetDistrict(position);
            }
            catch
            {
                return 0;
            }
        }

        private static string ReadAssetTitle(BuildingInfo info)
        {
            try
            {
                return info != null ? info.GetLocalizedTitle() : null;
            }
            catch
            {
                return null;
            }
        }

        private static string ReadCategory(BuildingInfo info)
        {
            try
            {
                return info != null ? info.category : null;
            }
            catch
            {
                return null;
            }
        }

        private static string ReadService(BuildingInfo info)
        {
            try
            {
                return info != null ? info.m_class.m_service.ToString() : null;
            }
            catch
            {
                return null;
            }
        }

        private static string ReadSubService(BuildingInfo info)
        {
            try
            {
                return info != null ? info.m_class.m_subService.ToString() : null;
            }
            catch
            {
                return null;
            }
        }

        // ---- Districts ------------------------------------------------------------------
        /// <summary>
        /// District holds only flags/name metadata -- there is no colour or prefab on the struct
        /// in this game version, so the name comes from DistrictManager.GetDistrictName.
        /// </summary>
        public static void HarvestDistricts(CityLayout layout)
        {
            DistrictManager manager = Singleton<DistrictManager>.instance;
            District[] buffer = manager.m_districts.m_buffer;
            int count = Math.Min((int)manager.m_districts.m_size, buffer.Length);

            for (int i = 1; i < count; i++) // index 0 is the "no district" sentinel
            {
                try
                {
                    if ((buffer[i].m_flags & District.Flags.Created) == District.Flags.None)
                    {
                        continue;
                    }

                    DistrictDto dto = new DistrictDto();
                    dto.Id = i;
                    dto.Name = manager.GetDistrictName(i);
                    layout.Districts.Add(dto);
                }
                catch (Exception e)
                {
                    layout.Meta.Warnings.Add("District " + i + " skipped: " + e.Message);
                }
            }
        }

        // ---- Helpers --------------------------------------------------------------------
        /// <summary>
        /// Prefab name, falling back to the GameObject name (which is what the asset editor
        /// shows) and finally to the CLR type name so the field is never silently null.
        /// </summary>
        internal static string ReadPrefabName(PrefabInfo info)
        {
            if (info == null)
            {
                return null;
            }

            try
            {
                if (!string.IsNullOrEmpty(info.name))
                {
                    return info.name;
                }

                if (info.gameObject != null)
                {
                    return info.gameObject.name;
                }
            }
            catch
            {
                // fall through
            }

            return info.GetType().Name;
        }

        internal static Vector3Dto ToVector3Dto(Vector3 v)
        {
            Vector3Dto dto = new Vector3Dto();
            dto.X = SafeFloat(v.x);
            dto.Y = SafeFloat(v.y);
            dto.Z = SafeFloat(v.z);
            return dto;
        }

        internal static float SafeFloat(float value)
        {
            return (float.IsNaN(value) || float.IsInfinity(value)) ? 0f : value;
        }
    }

    // ========================================================================================
    //  6.  METADATA
    // ========================================================================================
    internal static class ExportMetadata
    {
        public static ExportMeta Collect(string trigger)
        {
            ExportMeta meta = new ExportMeta();

            try
            {
                meta.ModVersion = ModInfo.Version;
                meta.Trigger = trigger;
                meta.ExportedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture);
                meta.UnityVersion = Application.unityVersion;
                meta.GameVersion = typeof(SimulationManager).Assembly.GetName().Version.ToString();

                SimulationManager simulation = Singleton<SimulationManager>.instance;
                if (simulation != null)
                {
                    meta.SimulationTick = simulation.m_currentTickIndex;

                    if (simulation.m_metaData != null)
                    {
                        meta.CityName = simulation.m_metaData.m_CityName;

                        if (simulation.m_metaData.m_MapThemeMetaData != null)
                        {
                            meta.MapTheme = ReadThemeName(simulation.m_metaData.m_MapThemeMetaData.name);
                        }
                    }
                }
            }
            catch (Exception e)
            {
                ModLog.Error("Metadata collection failed", e);
                meta.Warnings.Add("Metadata collection failed: " + e.Message);
            }

            return meta;
        }

        private static string ReadThemeName(string themeName)
        {
            try
            {
                if (string.IsNullOrEmpty(themeName))
                {
                    return null;
                }

                string localized = Locale.Get("MAPTHEME", themeName);
                return string.IsNullOrEmpty(localized) ? themeName : localized;
            }
            catch
            {
                return themeName;
            }
        }
    }

    // ========================================================================================
    //  7.  DATA TRANSFER OBJECTS  -- the JSON contract.  Plain public fields, no logic, so the
    //      writer can serialize them by reflection and Part 2 can rely on stable names.
    // ========================================================================================
    public class CityLayout
    {
        public int SchemaVersion = ModInfo.SchemaVersion;
        public ExportMeta Meta = new ExportMeta();
        public List<DistrictDto> Districts = new List<DistrictDto>();
        public List<RoadDto> Roads = new List<RoadDto>();
        public List<BuildingDto> Buildings = new List<BuildingDto>();
    }

    public class ExportMeta
    {
        public string Generator = ModInfo.Name + " v" + ModInfo.Version;
        public string ModVersion = ModInfo.Version;
        public string Trigger = "unknown";
        public string ExportedAtUtc = string.Empty;
        public string CityName = string.Empty;
        public string GameVersion = string.Empty;
        public string UnityVersion = string.Empty;
        public string MapTheme = string.Empty;

        /// <summary>0 = Unity left-handed, Y-up, metres, raw (no conversion applied).</summary>
        public int CoordinateSystem;

        public string CoordinateSystemName = "Unity left-handed Y-up, metres, unconverted";
        public long ExportMilliseconds;
        public uint SimulationTick;

        public int RoadCount;
        public int BuildingCount;
        public int DistrictCount;

        public int SkippedDeletedSegments;
        public int SkippedIncompleteSegments;
        public int SkippedNoPrefabSegments;
        public int SkippedUnreadableSegments;
        public int SkippedDeletedBuildings;
        public int SkippedUnreadableBuildings;

        public List<string> Warnings = new List<string>();
    }

    public class Vector3Dto
    {
        public float X;
        public float Y;
        public float Z;
    }

    /// <summary>Cubic Bezier: p(t) = (1-t)^3*a + 3(1-t)^2*t*b + 3(1-t)t^2*c + t^3*d.</summary>
    public class BezierDto
    {
        public Vector3Dto Start;
        public Vector3Dto Control1;
        public Vector3Dto Control2;
        public Vector3Dto End;
    }

    public class RoadDto
    {
        public int SegmentId;
        public ushort StartNodeId;
        public ushort EndNodeId;
        public string PrefabName;
        public string RoadClass;
        public string VehicleTypes;

        public bool IsOneWay;
        public bool IsStraight;

        /// <summary>Game flipped this segment relative to its node order.</summary>
        public bool Inverted;

        public float HalfWidth;
        public float MeasuredWidth;
        public int LaneCount;
        public float AverageLength;

        /// <summary>Traffic accumulator, 0-255 (byte on NetSegment).</summary>
        public int TrafficDensity;

        public Vector3Dto StartPosition;
        public Vector3Dto EndPosition;
        public Vector3Dto StartDirection;
        public Vector3Dto EndDirection;
        public Vector3Dto MiddlePosition;

        /// <summary>Exact centre-line curve from NetSegment.GenerateBezier.</summary>
        public BezierDto Bezier;

        /// <summary>True when the Bezier runs start-node -> end-node (matches our positions).</summary>
        public bool BezierOrientedFromStart;
    }

    public class BuildingDto
    {
        public int BuildingId;
        public string PrefabName;
        public string AssetTitle;
        public string Category;
        public string Service;
        public string SubService;

        public Vector3Dto Position;
        public float AngleRadians;
        public float AngleDegrees;

        /// <summary>Footprint from the building's 8 m cell counts.</summary>
        public float Width;

        public float Length;

        /// <summary>Prefab mesh bounding box height in metres (best available proxy).</summary>
        public float Height;

        public Vector3Dto PrefabSize;

        public ushort DistrictId;
        public bool IsCollapsed;
        public bool IsAbandoned;
        public bool IsHistorical;
    }

    public class DistrictDto
    {
        public int Id;
        public string Name;
    }

    // ========================================================================================
    //  8.  JSON WRITER  -- small dependency-free serializer.
    //      - public fields and properties, emitted under camelCase keys
    //      - pretty-printed and diffable
    //      - floats rounded (3 dp) and ALWAYS formatted with CultureInfo.InvariantCulture,
    //        so a player on a comma-decimal locale still gets valid JSON
    //      - NaN/Infinity sanitised to 0, reference-cycle protection
    // ========================================================================================
    public sealed class JsonWriter : IDisposable
    {
        private readonly TextWriter _writer;
        private readonly HashSet<object> _visited = new HashSet<object>(ReferenceComparer.Instance);
        private int _indent;
        private int _depth;

        private const int MaxDepth = 48;

        public JsonWriter(TextWriter writer)
        {
            if (writer == null)
            {
                throw new ArgumentNullException("writer");
            }

            _writer = writer;
        }

        public void Dispose()
        {
            _visited.Clear();
        }

        public void WriteValue(object value)
        {
            if (_depth > MaxDepth)
            {
                _writer.Write("null");
                return;
            }

            if (value == null)
            {
                _writer.Write("null");
                return;
            }

            Type type = value.GetType();

            if (IsSimple(type))
            {
                WriteScalar(value, type);
                return;
            }

            if (value is IDictionary)
            {
                WriteDictionary((IDictionary)value);
                return;
            }

            if (value is IEnumerable)
            {
                WriteEnumerable((IEnumerable)value);
                return;
            }

            WriteObject(value, type);
        }

        private void WriteObject(object value, Type type)
        {
            if (!_visited.Add(value))
            {
                _writer.Write("null");
                return;
            }

            _writer.Write('{');
            _indent++;
            _depth++;

            bool first = true;
            List<MemberInfo> members = new List<MemberInfo>();
            members.AddRange(type.GetFields(System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public));
            members.AddRange(type.GetProperties(System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.Public));

            for (int i = 0; i < members.Count; i++)
            {
                System.Reflection.MemberInfo member = members[i];
                System.Reflection.PropertyInfo property = member as System.Reflection.PropertyInfo;
                System.Reflection.FieldInfo field = member as System.Reflection.FieldInfo;

                if (property != null && (!property.CanRead || property.GetIndexParameters().Length > 0))
                {
                    continue;
                }

                if (field != null && field.IsStatic)
                {
                    continue;
                }

                object memberValue;
                try
                {
                    memberValue = field != null ? field.GetValue(value) : property.GetValue(value, null);
                }
                catch
                {
                    continue; // unreadable member: skip rather than fail the export
                }

                if (memberValue is Delegate)
                {
                    continue;
                }

                if (!first)
                {
                    _writer.Write(',');
                }

                NewLine();
                WriteStringLiteral(ToCamelCase(member.Name));
                _writer.Write(": ");
                WriteValue(memberValue);
                first = false;
            }

            _depth--;
            _indent--;
            if (!first)
            {
                NewLine();
            }

            _writer.Write('}');
            _visited.Remove(value);
        }

        private void WriteEnumerable(IEnumerable items)
        {
            _writer.Write('[');
            _indent++;
            _depth++;

            bool first = true;
            foreach (object item in items)
            {
                if (!first)
                {
                    _writer.Write(',');
                }

                NewLine();
                WriteValue(item);
                first = false;
            }

            _depth--;
            _indent--;
            if (!first)
            {
                NewLine();
            }

            _writer.Write(']');
        }

        private void WriteDictionary(IDictionary dictionary)
        {
            _writer.Write('{');
            _indent++;
            _depth++;

            bool first = true;
            foreach (DictionaryEntry entry in dictionary)
            {
                if (!first)
                {
                    _writer.Write(',');
                }

                NewLine();
                WriteStringLiteral(entry.Key == null ? "null" : entry.Key.ToString());
                _writer.Write(": ");
                WriteValue(entry.Value);
                first = false;
            }

            _depth--;
            _indent--;
            if (!first)
            {
                NewLine();
            }

            _writer.Write('}');
        }

        private void WriteScalar(object value, Type type)
        {
            if (type == typeof(string))
            {
                WriteStringLiteral((string)value);
                return;
            }

            if (type == typeof(bool))
            {
                _writer.Write(((bool)value) ? "true" : "false");
                return;
            }

            if (type == typeof(char))
            {
                WriteStringLiteral(value.ToString());
                return;
            }

            if (type.IsEnum)
            {
                WriteStringLiteral(value.ToString());
                return;
            }

            if (type == typeof(float))
            {
                float f = (float)value;
                _writer.Write((float.IsNaN(f) || float.IsInfinity(f))
                    ? "0.0"
                    : Round(f, 3).ToString("0.###", CultureInfo.InvariantCulture));
                return;
            }

            if (type == typeof(double))
            {
                double d = (double)value;
                _writer.Write((double.IsNaN(d) || double.IsInfinity(d))
                    ? "0.0"
                    : d.ToString("0.##########", CultureInfo.InvariantCulture));
                return;
            }

            if (type == typeof(decimal))
            {
                _writer.Write(((decimal)value).ToString(CultureInfo.InvariantCulture));
                return;
            }

            _writer.Write(Convert.ToString(value, CultureInfo.InvariantCulture));
        }

        private static float Round(float value, int digits)
        {
            float scale = (float)Math.Pow(10, digits);
            return (float)Math.Round(value * scale, MidpointRounding.AwayFromZero) / scale;
        }

        /// <summary>
        /// "SegmentId" -> "segmentId".  Numeric run boundaries are preserved so "Vector3Dto"
        /// would become "vector3Dto" and "IsOneWay" becomes "isOneWay".
        /// </summary>
        private static string ToCamelCase(string name)
        {
            if (string.IsNullOrEmpty(name) || !char.IsUpper(name[0]))
            {
                return name;
            }

            char[] chars = name.ToCharArray();
            chars[0] = char.ToLowerInvariant(chars[0]);

            // "X" -> "x" (single char); "ID" -> "id"; "IOError" -> "ioError".
            for (int i = 1; i < chars.Length; i++)
            {
                if (!char.IsUpper(chars[i]))
                {
                    break;
                }

                bool lastChar = i == chars.Length - 1;
                if (!lastChar && char.IsLower(chars[i + 1]))
                {
                    break;
                }

                chars[i] = char.ToLowerInvariant(chars[i]);
            }

            return new string(chars);
        }

        private static bool IsSimple(Type type)
        {
            return type.IsPrimitive
                || type.IsEnum
                || type == typeof(string)
                || type == typeof(decimal)
                || type == typeof(char);
        }

        private void WriteStringLiteral(string text)
        {
            _writer.Write('"');

            if (text != null)
            {
                for (int i = 0; i < text.Length; i++)
                {
                    char c = text[i];
                    switch (c)
                    {
                        case '"': _writer.Write("\\\""); break;
                        case '\\': _writer.Write("\\\\"); break;
                        case '\b': _writer.Write("\\b"); break;
                        case '\f': _writer.Write("\\f"); break;
                        case '\n': _writer.Write("\\n"); break;
                        case '\r': _writer.Write("\\r"); break;
                        case '\t': _writer.Write("\\t"); break;
                        default:
                            if (c < ' ')
                            {
                                _writer.Write("\\u");
                                _writer.Write(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                            }
                            else
                            {
                                _writer.Write(c);
                            }

                            break;
                    }
                }
            }

            _writer.Write('"');
        }

        private void NewLine()
        {
            _writer.Write('\n');
            for (int i = 0; i < _indent; i++)
            {
                _writer.Write("  ");
            }
        }

        private sealed class ReferenceComparer : IEqualityComparer<object>
        {
            public static readonly ReferenceComparer Instance = new ReferenceComparer();

            public new bool Equals(object a, object b)
            {
                return ReferenceEquals(a, b);
            }

            public int GetHashCode(object obj)
            {
                return System.Runtime.CompilerServices.RuntimeHelpers.GetHashCode(obj);
            }
        }
    }

    // ========================================================================================
    //  9.  EXPORTER  -- output location, atomic write, helpers for the settings UI.
    // ========================================================================================
    public static class Exporter
    {
        private static string _lastOutputPath;
        private static string _lastReport;

        public static void RequestExport(string trigger)
        {
            ExporterRunner runner = UnityEngine.Object.FindObjectOfType<ExporterRunner>();
            if (runner == null)
            {
                ModLog.Warn("No active session to export from. Load a city first.");
                return;
            }

            runner.BeginExport(trigger);
        }

        public static void OpenOutputDirectory()
        {
            try
            {
                string directory = ExportWriter.ResolveOutputDirectory();
                if (string.IsNullOrEmpty(directory))
                {
                    ModLog.Warn("Could not resolve an output directory.");
                    return;
                }

                Directory.CreateDirectory(directory);
                System.Diagnostics.Process.Start("explorer.exe", "\"" + directory + "\"");
            }
            catch (Exception e)
            {
                ModLog.Error("OpenOutputDirectory failed", e);
            }
        }

        public static void PrintLastReport()
        {
            if (string.IsNullOrEmpty(_lastOutputPath))
            {
                ModLog.Info("No export has been written yet in this session.");
                return;
            }

            ModLog.Info("Last export: " + _lastOutputPath);
            if (!string.IsNullOrEmpty(_lastReport))
            {
                ModLog.Info(_lastReport);
            }
        }

        internal static void Reset()
        {
            _lastOutputPath = null;
            _lastReport = null;
        }

        internal static void Remember(string path, string report)
        {
            _lastOutputPath = path;
            _lastReport = report;
        }
    }

    internal static class ExportWriter
    {
        /// <summary>
        /// Atomic write: fill a .tmp file, then move it over the target, so a killed game never
        /// leaves a truncated JSON behind.  Falls back across candidate directories.
        /// </summary>
        public static string Write(CityLayout layout)
        {
            List<string> errors = new List<string>();
            List<string> written = new List<string>();
            string primaryPath = null;
            string[] candidates = BuildCandidateDirectories();

            for (int i = 0; i < candidates.Length; i++)
            {
                string directory = candidates[i];
                if (string.IsNullOrEmpty(directory))
                {
                    continue;
                }

                try
                {
                    Directory.CreateDirectory(directory);

                    string finalPath = Path.Combine(directory, BuildFileName(layout));
                    string tempPath = finalPath + ".tmp";

                    using (FileStream stream = new FileStream(tempPath, FileMode.Create, FileAccess.Write, FileShare.None))
                    using (StreamWriter textWriter = new StreamWriter(stream, new UTF8Encoding(false)))
                    using (JsonWriter json = new JsonWriter(textWriter))
                    {
                        json.WriteValue(layout);
                        textWriter.Flush();
                        stream.Flush();
                    }

                    if (File.Exists(finalPath))
                    {
                        File.Delete(finalPath);
                    }

                    File.Move(tempPath, finalPath);

                    string report = string.Format(CultureInfo.InvariantCulture,
                        "roads={0} buildings={1} districts={2} warnings={3} bytes={4}",
                        layout.Roads.Count, layout.Buildings.Count, layout.Districts.Count,
                        layout.Meta.Warnings.Count, new FileInfo(finalPath).Length);

                    written.Add(finalPath);

                    if (primaryPath == null)
                    {
                        primaryPath = finalPath;
                        Exporter.Remember(finalPath, report);
                    }
                }
                catch (Exception e)
                {
                    errors.Add(directory + " -> " + e.Message);
                    ModLog.Warn("Could not write to '" + directory + "': " + e.Message);
                }
            }

            if (primaryPath != null)
            {
                // Written to every location that was available, so the project folder and the
                // Desktop both end up with a copy.
                if (written.Count > 1)
                {
                    ModLog.Info("Also wrote copies to: " + string.Join(", ", written.ToArray()));
                }

                return primaryPath;
            }

            throw new IOException("All output locations failed: " + string.Join(" | ", errors.ToArray()));
        }

        public static string ResolveOutputDirectory()
        {
            string[] candidates = BuildCandidateDirectories();
            for (int i = 0; i < candidates.Length; i++)
            {
                if (string.IsNullOrEmpty(candidates[i]))
                {
                    continue;
                }

                try
                {
                    Directory.CreateDirectory(candidates[i]);
                    return candidates[i];
                }
                catch
                {
                    // try the next candidate
                }
            }

            return null;
        }

        private static string[] BuildCandidateDirectories()
        {
            List<string> directories = new List<string>();

            // 1. The CS1-to-BeamNG project folder, when the pipeline lives on this machine.
            //    This is the copy the Python converter reads, so it is written first.
            try
            {
                if (!string.IsNullOrEmpty(ModInfo.ProjectExportDirectory) &&
                    Directory.Exists(Path.GetDirectoryName(ModInfo.ProjectExportDirectory)))
                {
                    directories.Add(ModInfo.ProjectExportDirectory);
                }
            }
            catch (Exception e)
            {
                ModLog.Warn("Project export path unavailable: " + e.Message);
            }

            // 2. Desktop\CS1ToBeamNG  (the zero-config handoff)
            try
            {
                string desktop = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
                if (!string.IsNullOrEmpty(desktop))
                {
                    directories.Add(Path.Combine(desktop, "CS1ToBeamNG"));
                }
            }
            catch (Exception e)
            {
                ModLog.Warn("Desktop path unavailable: " + e.Message);
            }

            // 3. <Install>\Cities_Data\CS1ToBeamNG
            try
            {
                if (!string.IsNullOrEmpty(Application.dataPath))
                {
                    directories.Add(Path.Combine(Application.dataPath, "CS1ToBeamNG"));
                }
            }
            catch (Exception e)
            {
                ModLog.Warn("Game data path unavailable: " + e.Message);
            }

            // 4. persistentDataPath
            try
            {
                if (!string.IsNullOrEmpty(Application.persistentDataPath))
                {
                    directories.Add(Path.Combine(Application.persistentDataPath, "CS1ToBeamNG"));
                }
            }
            catch (Exception e)
            {
                ModLog.Warn("Persistent data path unavailable: " + e.Message);
            }

            return directories.ToArray();
        }

        private static string BuildFileName(CityLayout layout)
        {
            try
            {
                if (layout != null && layout.Meta != null && !string.IsNullOrEmpty(layout.Meta.CityName))
                {
                    string safe = SanitizeFileName(layout.Meta.CityName);
                    if (!string.IsNullOrEmpty(safe))
                    {
                        return safe + "_city_layout.json";
                    }
                }
            }
            catch
            {
                // fall back to the default name
            }

            return ModInfo.OutputFileName;
        }

        private static string SanitizeFileName(string name)
        {
            char[] invalid = Path.GetInvalidFileNameChars();
            StringBuilder builder = new StringBuilder(name.Length);

            for (int i = 0; i < name.Length; i++)
            {
                char c = name[i];
                bool bad = false;

                for (int j = 0; j < invalid.Length; j++)
                {
                    if (invalid[j] == c)
                    {
                        bad = true;
                        break;
                    }
                }

                builder.Append(bad ? '_' : c);
            }

            return builder.ToString().Trim().Trim('.');
        }
    }

    // ========================================================================================
    //  10. LOGGING  -- the game log (Debug.Log) plus a file next to output_log.txt so a failed
    //      export can be diagnosed after the fact.
    // ========================================================================================
    public static class ModLog
    {
        private static readonly object Gate = new object();
        private static string _logPath;

        public static void Info(string message)
        {
            Write("INFO", message, null);
        }

        public static void Warn(string message)
        {
            Write("WARN", message, null);
        }

        public static void Error(string message)
        {
            Write("ERROR", message, null);
        }

        public static void Error(string message, Exception exception)
        {
            Write("ERROR", message, exception);
        }

        private static void Write(string level, string message, Exception exception)
        {
            string line = string.Format(CultureInfo.InvariantCulture,
                "[{0}] [{1}] [{2}] {3}{4}",
                DateTime.Now.ToString("HH:mm:ss", CultureInfo.InvariantCulture),
                level,
                ModInfo.Name,
                message ?? string.Empty,
                exception != null ? " :: " + exception : string.Empty);

            try
            {
                if (level == "ERROR")
                {
                    Debug.LogError(line);
                }
                else if (level == "WARN")
                {
                    Debug.LogWarning(line);
                }
                else
                {
                    Debug.Log(line);
                }
            }
            catch
            {
                // Debug logging must never throw.
            }

            try
            {
                lock (Gate)
                {
                    if (_logPath == null)
                    {
                        _logPath = ResolveLogPath();
                    }

                    if (!string.IsNullOrEmpty(_logPath))
                    {
                        File.AppendAllText(_logPath, line + Environment.NewLine, new UTF8Encoding(false));
                    }
                }
            }
            catch
            {
                // File logging is best-effort only.
            }
        }

        private static string ResolveLogPath()
        {
            try
            {
                string localAppData = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                if (!string.IsNullOrEmpty(localAppData))
                {
                    // Nested Combine: the game's runtime only offers the two-argument overload.
                    string directory = Path.Combine(Path.Combine(localAppData, "Colossal Order"), "Cities_Skylines");
                    if (Directory.Exists(directory))
                    {
                        return Path.Combine(directory, ModInfo.LogFileName);
                    }
                }

                if (!string.IsNullOrEmpty(Application.persistentDataPath))
                {
                    Directory.CreateDirectory(Application.persistentDataPath);
                    return Path.Combine(Application.persistentDataPath, ModInfo.LogFileName);
                }
            }
            catch
            {
                // fall through
            }

            return null;
        }
    }
}
