# CS1-to-BeamNG

An automated pipeline that exports a city from **Cities: Skylines 1** and turns it into a
drivable map for **BeamNG.drive**.

**Status:** both parts work end to end. The exporter is implemented and compiles against the real
game assemblies; the converter produces an installable BeamNG level from its output, and
`tools/dump/conformance.py` checks the result against measurements taken from a working map.

Maps produced so far are **playable and incomplete**. The road network, terrain and buildings are
present and drivable; the terrain's ground colour is approximate, and some building materials
inherited from the base game do not resolve (see "Known limitations" below).

---

## Pipeline architecture

```
 ┌─────────────────────────────┐        ┌──────────────────────────────┐        ┌───────────────────────┐
 │  PART 1  (C# mod, in-game)  │        │  PART 2  (Python, offline)   │        │  BeamNG.drive         │
 │                             │        │                              │        │                       │
 │  NetManager.m_segments      │        │  validate + analyse          │        │  decalroads.json      │
 │    -> Bezier centre-lines   │        │  Unity -> BeamNG axis map    │        │  items.level.json     │
 │  BuildingManager.m_buildings│──JSON──▶  road spline -> decal road    │──────▶  terrain heightmap   │
 │    -> position/rotation/box │        │  building -> proxy box       │        │  materials / terrain  │
 │  DistrictManager.m_districts│        │  terrain heightmap bake      │        │                       │
 └─────────────────────────────┘        └──────────────────────────────┘        └───────────────────────┘
        city_layout.json                    convert + emit                    a drivable level
```

Part 1 deliberately does **no** coordinate conversion. It ships raw Unity values plus a full
provenance block so every later step stays auditable and testable in pure Python.

---

## Repository layout

| Path | What it is |
| --- | --- |
| [`mod/CS1ToBeamNGExporter.cs`](mod/CS1ToBeamNGExporter.cs) | **Part 1.** The complete single-file CS1 exporter mod. |
| [`tools/make-beamng-map.cmd`](tools/make-beamng-map.cmd) | **Double-click this** to convert an export into a BeamNG level. |
| [`tools/beamng_convert.py`](tools/beamng_convert.py) | **Part 2.** The converter (also runnable directly). |
| [`tools/watch-mod-load.cmd`](tools/watch-mod-load.cmd) | Double-click to check the CS1 mod's install status and read the game log. |
| [`tools/validate_city_layout.py`](tools/validate_city_layout.py) | Schema/geometry validator and statistics for a `city_layout.json`. |
| [`tools/verify_conversion.py`](tools/verify_conversion.py) | Conformance test: re-derives the conversion independently and compares. |
| [`tools/mutation_test.py`](tools/mutation_test.py) | Proves the conformance test can fail, by corrupting a copy nine ways. |
| [`tools/beamng/cs1_verify.lua`](tools/beamng/cs1_verify.lua) | In-game probe reporting what BeamNG actually instantiated. |
| [`tools/watch-mod-load.ps1`](tools/watch-mod-load.ps1) | The script behind the CS1 launcher (`-Restart`, `-Build`, `-Follow`). |
| [`tools/test/JsonWriterTests.cs`](tools/test/JsonWriterTests.cs) | Harness that exercises the shipping JSON writer outside the game. |
| `tools/dump/` | Dev-only reflection probes used to verify the CS1 game API. |
| `exports/` | Where the CS1 mod writes `city_layout.json` (plus the Desktop). |
| `dist/` | Converter output: the level folder, its zip, and JSON reports. |

---

## Troubleshooting: the mod doesn't appear in Content Manager

Cities: Skylines scans `Addons\Mods` and compiles source mods **exactly once, at game
startup**. Loading a save, or using "Reload" in the Content Manager, does **not** rescan. If
you copy the file in while the game is already open, nothing happens — this is the single most
common cause of "I added it and nothing appeared".

Symptom in `Cities_Data\output_log.txt`:

```
No source files found: CS1ToBeamNGExporter  [Mods - Internal]
```

The folder name is echoed correctly, so the game *did* find and scan the folder — it was just
empty at that moment.

**Fix:** fully quit the game and start it again.

Use the bundled diagnostic to see all of this at once:

```powershell
.\tools\watch-mod-load.cmd            # status + the relevant log lines
.\tools\watch-mod-load.cmd -Restart   # close the game, reset the log, relaunch, and watch
.\tools\watch-mod-load.cmd -Follow    # stream the log until Ctrl+C
```

The launcher exists because the script is not digitally signed; running the `.ps1` directly can
fail with *"cannot be loaded … is not digitally signed"* depending on your execution policy.
The launcher bypasses that for its own run only.

### Two rules for the mod folder

1. **Never put both a `.cs` and a `.dll` in the mod folder.** The game compiles every `.cs` it
   finds — *recursively*, so hiding one in a subfolder does not help — and would then see the
   same classes twice.
2. The `.cs` file must sit directly in `Addons\Mods\<ModName>\`, and `<ModName>` becomes the
   mod's assembly name. It does not need to match the class name.

To switch to a pre-built DLL (no in-game compilation):

```powershell
.\tools\watch-mod-load.cmd -Build
```

That compiles `mod\CS1ToBeamNGExporter.cs` into the mod folder and removes the `.cs` so the two
cannot conflict. The master copy of the source always lives in the repo.

> **Note:** the game's bundled Mono compiler (`Mono\lib\mono\unity\smcs.exe`) cannot be run
> standalone — it immediately requires `System.CodeDom.Compiler`, which the shipped Mono profile
> does not contain, so it dies with a `ReflectionTypeLoadException`. `-Build` therefore uses the
> Windows .NET Framework `csc.exe` against the game's own reference assemblies.

### Verifying it actually loaded

A successful load looks like this in `output_log.txt`:

```
Loading ...\Addons\Mods\CS1ToBeamNGExporter\CS1ToBeamNGExporter.dll  [Mods - Internal]
Assembly CS1ToBeamNGExporter, Version=0.0.0.0, ... loaded.  [Mods - Internal]
```

The assembly is reported once per mod entry it is discovered through, so seeing it several times
is normal.

Then, after the mod is enabled **and a save is loaded**, the mod writes its own log:

```powershell
Get-Content "$env:LOCALAPPDATA\Colossal Order\Cities_Skylines\CS1ToBeamNGExporter.log"
```

If that file does not exist, the loading extension has not run yet — which always means no save
has been loaded since the mod was enabled. The export panel and the Ctrl+Shift+E hotkey are both
created in `OnLevelLoaded`, so neither exists in the main menu or the map/asset editor.

---

## Part 1 — installing the exporter

The mod is **one self-contained `.cs` file**. It uses no external libraries beyond
`UnityEngine`, `ColossalFramework`, `ColossalFramework.UI`, `ICities` and the `.NET` base
class library — no Newtonsoft, no `System.Text.Json`, no Harmony.

### Option A — let the game compile it (no toolchain required)

1. Create this folder:

   ```
   %LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\Mods\CS1ToBeamNGExporter\
   ```

2. Copy `mod/CS1ToBeamNGExporter.cs` into it.

   The folder must contain **exactly one `.cs` file**. The in-game compiler compiles every
   `.cs` it finds in a mod folder into a single assembly, which is why this file is not split
   across multiple files.

3. Start Cities: Skylines. The game compiles it at startup into:

   ```
   <Install>\Cities_Data\Mods\CS1ToBeamNGExporter.dll
   ```

4. In-game: **Content Manager → Mods → enable "CS1-to-BeamNG Exporter"**.

Compile errors are written to `%LOCALAPPDATA%\Colossal Order\Cities_Skylines\output_log.txt`.

### Option B — compile it yourself (useful while iterating)

The game bundles a Mono C# compiler, so no SDK install is needed:

```powershell
$g   = 'E:\games\epic games\CitiesSkylines'      # your install
$mono = "$g\Mono\bin\mono.exe"
$smcs = "$g\Mono\lib\mono\unity\smcs.exe"
$man  = "$g\Cities_Data\Managed"

& $mono $smcs -target:library -nologo `
    -r:"$man\UnityEngine.dll" -r:"$man\Assembly-CSharp.dll" `
    -r:"$man\ColossalManaged.dll" -r:"$man\ICities.dll" `
    -out:build\CS1ToBeamNGExporter.dll mod\CS1ToBeamNGExporter.cs
```

Then drop `build\CS1ToBeamNGExporter.dll` into
`%LOCALAPPDATA%\Colossal Order\Cities_Skylines\Addons\Mods\CS1ToBeamNGExporter\`.

> The Windows `csc.exe` from `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319` also works when
> you point it at the game's own reference assemblies:
> `csc /nologo /target:library /nostdlib+ /noconfig /r:<Managed>\mscorlib.dll /r:<Managed>\System.dll ...`
> That is how this file was verified.

### Using it

Load a save, then either:

* press **Ctrl+Shift+E**, or
* click the **EXPORT CITY JSON** panel button (bottom-right, draggable), or
* use **Content Manager → Mods → CS1-to-BeamNG Exporter → Export now**.

The JSON is written to **both** of these, so the converter can find it either way:

* `<repo>\exports\<CityName>_city_layout.json` — the copy the converter reads, written first
* `Desktop\CS1ToBeamNG\<CityName>_city_layout.json` — the zero-config copy

If the repo path does not exist on the machine running the game, only the Desktop copy is
written (plus the game folder and `persistentDataPath` as further fallbacks). Writes are atomic
(temp file + move), so a crash mid-export never leaves a truncated file. Progress is shown in
the panel and a full report is logged to
`%LOCALAPPDATA%\Colossal Order\Cities_Skylines\CS1ToBeamNGExporter.log`.

The project path is the `ProjectExportDirectory` constant at the top of the mod source — edit it
if you move the project.

The export runs as a **coroutine in batches** (1500 segments / 3000 buildings per frame), so
even a 100k-segment city does not freeze the editor.

---

## The `city_layout.json` contract (schema v1)

```jsonc
{
  "schemaVersion": 1,
  "meta": {
    "generator": "CS1-to-BeamNG Exporter v1.0.0",
    "modVersion": "1.0.0",
    "trigger": "hotkey Ctrl+Shift+E",
    "exportedAtUtc": "2024-01-01T00:00:00Z",
    "cityName": "Testburg",
    "gameVersion": "1.17.0", "unityVersion": "5.6.7f1", "mapTheme": "European",
    "coordinateSystem": 0,
    "coordinateSystemName": "Unity left-handed Y-up, metres, unconverted",
    "exportMilliseconds": 1234, "simulationTick": 987654,
    "roadCount": 2, "buildingCount": 1, "districtCount": 1,
    "skippedDeletedSegments": 0, "skippedIncompleteSegments": 0,
    "skippedNoPrefabSegments": 0, "skippedUnreadableSegments": 0,
    "skippedDeletedBuildings": 0, "skippedUnreadableBuildings": 0,
    "warnings": []
  },
  "districts": [ { "id": 1, "name": "Downtown" } ],
  "roads": [
    {
      "segmentId": 100, "startNodeId": 11, "endNodeId": 12,
      "prefabName": "Basic Road", "roadClass": "Road", "vehicleTypes": "Car, Bicycle",
      "isOneWay": false, "isStraight": true, "inverted": false,
      "halfWidth": 8, "measuredWidth": 16, "laneCount": 4,
      "averageLength": 64, "trafficDensity": 128,
      "startPosition":   { "x": -100, "y": 12.5, "z": 200 },
      "endPosition":     { "x": -36,  "y": 12.5, "z": 200 },
      "startDirection":  { "x": 64,   "y": 0,    "z": 0 },
      "endDirection":    { "x": -64,  "y": 0,    "z": 0 },
      "middlePosition":  { "x": -68,  "y": 12.5, "z": 200 },
      "bezier": {
        "start":    { "x": -100,      "y": 12.5, "z": 200 },
        "control1": { "x": -78.667,   "y": 12.5, "z": 200 },
        "control2": { "x": -57.333,   "y": 12.5, "z": 200 },
        "end":      { "x": -36,       "y": 12.5, "z": 200 }
      },
      "bezierOrientedFromStart": true
    }
  ],
  "buildings": [
    {
      "buildingId": 7, "prefabName": "House 01", "assetTitle": "Small House",
      "category": "Residential", "service": "Residential", "subService": "ResidentialLow",
      "position": { "x": 10, "y": 12, "z": 30 },
      "angleRadians": 1.5707964, "angleDegrees": 90,
      "width": 16, "length": 24, "height": 9.5,
      "prefabSize": { "x": 16, "y": 9.5, "z": 24 },
      "districtId": 1, "isCollapsed": false, "isAbandoned": false, "isHistorical": false
    }
  ]
}
```

Notes that matter for Part 2:

* **Coordinates are raw Unity**: left-handed, Y-up, metres, unshifted. The BeamNG mapping is
  `x_bng = -x_cs1`, `y_bng = z_cs1`, `z_bng = y_cs1` — applied in Python, never here.
* **`bezier` is the authoritative road shape.** It comes from
  `NetSegment.GenerateBezier(segmentId, startNodeId)`, i.e. the game's own cubic Bézier, and
  already encodes CS1's three-part road construction (two curved ends plus a straight middle).
  It is `null` only if the game call failed; the validator treats that as a warning and the
  converter must synthesise a straight span.
* **`bezierOrientedFromStart`** confirms the curve runs start-node → end-node, matching
  `startPosition`/`endPosition`. Check it before assuming orientation.
* **`measuredWidth`** is derived from the prefab's lane layout (outermost lane offset + half its
  width, doubled) — the drivable surface. `halfWidth * 2` is the cruder prefab value; both are
  exported so Part 2 can pick.
* **`width`/`length` on buildings are in metres**, already converted from the game's 8 m cell
  counts. `height` comes from the prefab mesh bounding box (`BuildingInfo.m_size.y`), which is
  the best height proxy the simulation exposes.
* **`angleRadians` is canonical**; `angleDegrees` is precomputed so the converter cannot get the
  unit conversion wrong. Around the Unity Y axis: forward = `(sin θ, 0, cos θ)`.
* **`districtId` 0 means "no district"**, as does district index 0 in `districts`.
* Floats are rounded to 3 decimals and are always formatted with `InvariantCulture`, so a player
  on a comma-decimal locale still gets valid JSON.

---

## Part 2 — converting an export into a BeamNG level

Once you have a `city_layout.json`, **double-click [`tools/make-beamng-map.cmd`](tools/make-beamng-map.cmd)**.
With no arguments it finds the newest export automatically (from `exports/`, else from the
Desktop) and writes a complete, ready-to-install BeamNG level.

```powershell
# double-click, or from a terminal:
.\tools\make-beamng-map.cmd                     # newest export -> dist\
.\tools\make-beamng-map.cmd --install           # ...and copy the zip into BeamNG
.\tools\make-beamng-map.cmd --include-non-drivable
.\tools\make-beamng-map.cmd "C:\path\city_layout.json"
python tools\beamng_convert.py --help           # all options
```

### What it produces

```
dist/cs1_<city>/
    info.json                                  level metadata, size, spawn points
    levels/<Level>/<Level>.ter                 the binary terrain (loaded by the engine)
    levels/<Level>/<Level>.terrain.json        terrain descriptor
    levels/<Level>/<Level>.terrainheightmap.png  exported preview of the heightmap
    levels/<Level>/art/terrains/main.materials.json
    levels/<Level>/main/items.level.json       MissionGroup declaration
    levels/<Level>/main/MissionGroup/items.level.json   spawn + camera + TerrainBlock
    levels/<Level>/main/MissionGroup/Roads/...          DecalRoads, split at 1000 per file
    levels/<Level>/main/MissionGroup/Buildings/...      TSStatic proxy boxes
art/shapes/<mod>/cs1_proxy_box.dae             the unit cube every building instance scales
art/shapes/<mod>/main.materials.json
```

`dist/cs1_<city>.zip` is the same tree zipped for the BeamNG mods folder.

> **The zip must not contain a wrapper folder.** The archive root has to hold `levels/` and
> `art/` directly, *not* a single folder named after the mod. BeamNG mounts the archive and
> lists the mod either way, but with a wrapper it never finds the level inside, so the map is
> missing from the level selector while the mod still appears in the mods list. Verified against
> two working level mods, whose first entry is `levels/`. The converter gets this right, and
> `verify_conversion.py` now fails if the archive is wrapped.

### How the conversion works

| Step | Detail |
| --- | --- |
| **Axis mapping** | `x_bng = -x_cs1`, `y_bng = z_cs1`, `z_bng = y_cs1` (negating X flips Unity's left-handed frame into BeamNG's right-handed one). A CS1 yaw θ about +Y becomes −θ about BeamNG's +Z. |
| **Roads** | Each CS1 segment's Bézier is adaptively subdivided until it is within 0.5 m of a straight line, then emitted as one `DecalRoad` with `[x, y, z, width]` nodes. Every node is re-snapped to the generated terrain surface. |
| **Terrain** | Reconstructed from road elevations (see the caveat below), written as a genuine binary `.ter` (version 9) plus a descriptive `.terrain.json` and a preview PNG, and instantiated by a `TerrainBlock`. |
| **Buildings** | Each becomes a `TSStatic` referencing one generated `cs1_proxy_box.dae` unit cube, scaled to the building footprint with a real `rotationMatrix`, standing on the terrain. |
| **Non-roads** | CS1 keeps water pipes, power lines, ship lanes, plane paths and rail in the same `NetManager`. These are filtered out by default (`--include-non-drivable` keeps them). |

### Important caveat: the terrain is reconstructed, not exported

`city_layout.json` contains **no terrain data** — the exporter records roads, buildings and
districts, and CS1 stores the ground as Unity Terrain. The converter therefore interpolates a
heightmap from the road network's own elevations (roads sit on the ground in CS1, so each road
node is a genuine ground sample): samples are scattered onto a grid, gaps are filled from a
coarse pyramid, and the result is smoothed.

The practical consequences:

* Roads and buildings land accurately, because everything is snapped to the generated surface —
  in the Cannes conversion the worst error is **0.0001 m**.
* Hills and valleys that no road crosses are flattened toward the nearest road height.
* Coastlines and water are **not** represented; CS1 water is invisible to the exporter.

If you need real topography, the CS1 heightmap has to be exported too — that is the natural next
step for the exporter mod (sample `TerrainManager` into the same JSON).

### Verifying a conversion

Two tools prove the output, and they are different in kind:

```powershell
.\tools\make-beamng-map.cmd                    # converts, and self-checks as it writes
python tools\verify_conversion.py exports\Cannes_city_layout.json
python tools\mutation_test.py     exports\Cannes_city_layout.json
```

**`verify_conversion.py`** is a *conformance test*, not a self-check by the converter. It reads
the source `city_layout.json` and the generated level with its own independent code — its own
JSON streaming, its own coordinate arithmetic, its own curve sampling, its own binary `.ter`
parser — and compares the two. A sign error, an axis swap, a units mistake or a dropped road
cannot pass both sides, because the expected values are not produced by the code under test.

On the Cannes conversion it runs 1507 checks and reports:

```
. .ter: 8192x8192, version 9, 192.0 MB, materials ['cs1_ground']
. objects: 1244 DecalRoad, 1463 TSStatic, 1 TerrainBlock, 2 SpawnSphere
. road endpoints compared: 1244, worst horizontal mapping error 0.0000 m
. road nodes on terrain: max deviation 0.000124 m
. buildings on terrain: max deviation 0.000058 m
PASSED -- all 1507 checks
```

It verifies, among other things: the terrain header is version 9 with a power-of-two size;
`terrain.json`'s sample counts agree with the binary; the layer map contains no `255` (which
would punch a hole in the terrain and delete collision); every road node maps from CS1 space to
BeamNG space by exactly `(-x, z, y)` **and** lies on the generated surface; every building's
`rotationMatrix` is a genuine rotation (orthonormal, determinant +1); every referenced shape and
terrain file exists; and each `SimGroup` has the folder it names, without which its items would
be silently dropped.

**`mutation_test.py`** proves the verifier can actually fail. It applies nine realistic
corruptions one at a time to a throwaway copy and requires each to be caught:

```
baseline (unmodified copy): PASSES as expected
ter_version        DETECTED   .ter version changed from 9 to 7
ter_size           DETECTED   .ter size changed to 5000 (not a power of two)
terrain_hole       DETECTED   layer map set to 255 (punches a terrain hole)
rotation           DETECTED   first building rotationMatrix made non-orthonormal
wrapped_array      DETECTED   items.level.json wrapped in a JSON array
missing_shape      DETECTED   proxy box .dae deleted while buildings still reference it
info_size          DETECTED   info.json size disagrees with the terrain
terrain_metadata   DETECTED   terrain.json heightMapSize set to 12345
missing_terrain    DETECTED   .ter deleted while TerrainBlock still references it
RESULT: OK -- all 9 corruptions were detected, baseline passes
```

### Two things a level cannot load without

Both of these were discovered by loading a converted level in-game, and neither is discoverable
from the level's own files — they are *absences*, and an absence looks fine in every syntax check.

**Lighting.** A BeamNG level gets its sun, sky and fog from four scene objects, and nothing else
supplies them. Omit them and the map loads **pitch black**. The converter emits a `sky_and_sun`
SimGroup containing:

| Object | Role |
| --- | --- |
| `LevelInfo` | ambient/fog defaults, gravity, near clip, visible distance |
| `TimeOfDay` | the day cycle. `startTime` is set to `0.3` (mid-morning) so the map is lit on first load; `0` is midnight, `0.5` is noon |
| `ScatterSky` | the actual sun: elevation, azimuth, scattering, shadow distance |
| `CloudLayer` | the sky dome |
| `PointLight` | a fallback fill light, in case `ScatterSky` fails to resolve on a given build |

Note the group must also be **declared** as a `SimGroup` in `main/items.level.json`, or its
folder is never loaded.

**Spawn points.** A `SpawnSphere` with just a position and a rotation is not a usable spawn
marker. BeamNG's spawn code reads `dataBlock: "SpawnSphereMarker"`, `radius`, and
`sphereWeight`; without them the vehicle is not placed on the marker. The converter also *picks*
the spawn rather than taking the first road it finds — segment 0 can be a bridge, a ramp or a
cliff edge — by scoring candidate road nodes for flatness (surface relief within a 12 m disc),
distance from the map edge, and proximity to other roads, then starting the car 1 m above the
surface so the wheels settle onto it.

Verifying a conversion now fails loudly if any lighting object is missing or a spawn lacks its
marker fields, and `mutation_test.py` covers both.

**Sun exposure must come from the observed range, not a single sample.** Taking `ScatterSky`
values from one working level produced a map that was pitch black with a bright glow in the sky.
A survey of nine working levels showed why — `exposure` was 0.5, 1.2, 2, 2, 15, 15, 100, and
unset twice. The level I copied happened to be the `100` outlier: it blew out the sky while
leaving the ground black. The converter now uses the middle of that range (`exposure: 2`,
`ambientScale: 0.6`, `startTime: 0.17`), which is where the working levels cluster.

**A colourless light renders magenta.** An earlier revision added a `PointLight` as a "fallback
fill light". Without an explicit `lightColor` the engine uses its default, which is a hot
magenta, and it tinted the entire map pink. Outdoor levels are lit by `ScatterSky`; the fill
light is gone, and the verifier now rejects any `PointLight`/`SpotLight` with no `lightColor`.

**A textureless TerrainMaterial renders as "no material".** A v1 `TerrainMaterial` needs actual
texture paths — a definition carrying only an `internalName` loads but draws as the engine's
"no material" placeholder, which is what textured-looking ground turns into. Shared texture sets
such as `levels/template/art/terrains/` are **not** present in every installation, so referencing
one would fail on some machines: the converter instead generates its own 512x512 ground texture
and points `diffuseMap` at it, keeping the mod self-contained. The verifier checks that the
`diffuseMap` exists both as a field and as a file.

### What is *not* yet verified

**The level has not been loaded inside BeamNG.** Everything above proves the files are
well formed, mutually consistent, and conform to the formats read out of an installed BeamNG
0.39 — but only the engine can confirm that it renders, collides, and drives.

That check could not be automated here: BeamNG's engine binary will not start standalone (it
exits immediately after `Null device found` and needs its launcher), and the launcher accepts
only a support token, so `-level` / `-lua` cannot be injected. To do it manually, launch BeamNG
and start the level **Cannes** from the level selector. A probe is provided that reports what the
engine actually built:

```powershell
# install the probe, then start BeamNG and pick the level
copy tools\beamng\cs1_verify.lua "%LOCALAPPDATA%\BeamNG\BeamNG.drive\current\lua\ge\extensions\"
# the results land in the log and in:
type "%LOCALAPPDATA%\BeamNG\BeamNG.drive\current\cs1_verify_result.json"
```

It reports the level name, whether a `TerrainBlock` exists and which `.ter` it loaded, and the
counts of `DecalRoad`, `TSStatic` and `SpawnSphere` objects actually instantiated. Expected
values are 1244 / 1463 / 2.

---

## How a BeamNG level actually gets built

Everything below was read out of installed content, not inferred. The single most useful fact
is that **base-game levels live in `content/levels/*.zip`** — including `template.zip`, the level
the engine ships as the starting point for new maps, and `west_coast_usa.zip`, `italy.zip`, etc.
Those archives are the authoritative reference for every format question, and third-party maps
reference the template's shared textures rather than shipping their own.

### Terrain has two incompatible material generations

Which one applies is decided **entirely by the `TerrainBlock`**:

| | v1 classic | v1.5 PBR |
| --- | --- | --- |
| `TerrainBlock.materialTextureSet` | absent | set, e.g. `templateTerrainMaterialTextureSet` |
| Material fields | `diffuseMap`, `normalMap`, `macroMap`, `detailMap` | `baseColor*Tex`, `normal*Tex`, `roughness*Tex`, `ao*Tex`, `height*Tex` at base/macro/detail |
| Used by | only the ancient `autotest` | **every modern level** |

A material written in the wrong generation cannot be resolved. The engine does not fail loudly —
it substitutes `WARNING_MATERIAL`, which is why a terrain can load perfectly and still show the
**"no material"** placeholder:

```
E|BeamNGCollision::addTerrainBlock|
  ground model not found for collision: 'WARNING_MATERIAL' - using asphalt (0) instead
```

A complete v1.5 material needs **15** texture references (five groups × base/macro/detail), and
the texture pixel sizes must match the `TerrainMaterialTextureSet` exactly — the template's
declares `baseTexSize [512,512]`, `macroTexSize [1024,1024]`, `detailTexSize [1024,1024]` — or
the texture-array packing fails and it degrades to the warning material again.

### The level must define its OWN TerrainMaterialTextureSet

`TerrainBlock.materialTextureSet` is a **name reference resolved against the current level's
material library**. It is *not* a global: every shipped level defines its own
(`CliffTerrainMaterialTextureSet`, `italyTerrainMaterialTextureSet`, …). Pointing at the template
level's set by name fails, because the template level is not loaded:

```
E|TerrainCellMaterial| Failed to find TerrainMaterialTextureSet with name: templateTerrainMaterialTextureSet
E|BeamNGCollision::addTerrainBlock| ground model not found for collision: 'WARNING_MATERIAL'
```

A missing texture set is worse than a cosmetic problem. Because no material can be packed, the
terrain never binds a texture, and the result is a **GPU assert that kills the game**:

```
E|engine::GFXd3d12CmdBuffer::_updateStatesInternal| D3D12 cmd: root cbv has null gpu va ...
E|assert| d3d12CmdBuffer.cpp(546) : Fatal-ISV - D3D12: root cbv with 0 gpu va reached the bind path
```

So the chain is: dangling texture-set reference → material packing fails → `WARNING_MATERIAL` →
null GPU binding → crash. The converter now declares a per-level set
(`<Level>TerrainMaterialTextureSet`) whose declared pixel sizes match the template grass textures
(base 512², macro/detail 1024²), and `verify_conversion.py` fails if the reference does not
resolve or if a material named in the `.ter` is not defined.

Material names must also be unique; reusing a base-game name logs
`TerrainMaterial::onAdd() - Internal name collision; 'grass' already exists!`, so the converter
uses `cs1_grass`.

The converter builds its material from `/levels/template/art/terrains/...`, copying a real
template material's field names and size/strength conventions. Note that some template textures
are `.link` files rather than data (`t_macro_grass_*`), so the real families are the ones to use:
the grass set is `t_terrain_base_grass_*`, `t_grass1_*`, `t_macro_grass2_*`.

### Lighting is a scene group, and a rejected group is invisible

A level gets its sun, sky and fog from four objects in a `sky_and_sun` group, declared as a
`SimGroup` in `main/items.level.json`. If that group fails to deserialize, the engine logs it and
moves on — the level still reports `Level loaded`, and the map is simply black:

```
E|bng::json::deserializeLineObjectsRecursive|
  Unable to deserialize file /levels/cannes/main/sky_and_sun/items.level.json
```

`CloudLayer` in particular needs a `texture` field. The converter emits the template level's sky
block verbatim (only positions and `TimeOfDay` adjusted), because that guarantees every field the
deserializer expects is present.

### Other hard-won specifics

* A `PointLight`/`SpotLight` with no `lightColor` renders in the engine default — a hot magenta
  that tints the whole map. Outdoor levels are lit by `ScatterSky` alone.
* A `CameraBookmark` without a `dataBlock` is rejected: `no datablock on shape 18016:CameraBookmark`.
* `ScatterSky.exposure` across nine working levels: 0.5, 1.2, 2, 2, 15, 15, 100, unset, unset.
  Copying the single `100` produced a blown-out sky over black ground. The converter uses the
  middle of the range.
* `.ter.depth.png` is optional; without it the log notes that fluids are disabled as a ground type.

### Terrain size must stay inside the shipped envelope

Measured across every level in `content/levels`, the terrain grid runs **1024–4096** over worlds
of **614–4096 m**; the largest is a 4096 grid at 0.75 m samples. Nothing ships an 8192 grid.

An early revision chose the smallest `squareSize` that fit, which for a 17 km city produced an
**8192² grid over a 32 km world** — 2× the largest shipped grid, 8× the world area, 4× the
sample count. The converter now grows `squareSize` instead of the grid, so the world still covers
the whole city while the sample count stays in the shipped range (Cannes: 2048² at 16 m/sample
over 32 km). For a city map the coarser grid is invisible, because the terrain is a smooth
interpolation from road elevations anyway.

**The heightmap must be exactly square.** A rectangular one makes the `.ter` height section the
wrong length, which shifts the layer map and material list — the file still loads, but the
terrain material resolves to `WARNING_MATERIAL` and the layer map reads as garbage. `write_ter_file`
now raises on a non-square grid, and `_as_square()` guarantees one.

### Engine crashes

`0xC0000005 STATUS_ACCESS_VIOLATION` with

```
Fatal-ISV assert failed at file: ...\dxd12\d3d12CmdBuffer.cpp Line: 546
Message: "D3D12: root cbv with 0 gpu va reached the bind path, see preceding log"
```

is a **GPU-side engine assert, not a content error**. It was present in every BeamNG log on this
machine — including runs before the level existed — so the level is not its cause. The machine
runs `"displayDevice": "D3D12"`; switching to D3D11 in the launcher's graphics options is the
usual workaround.

### A folder is only loaded if its parent declares a SimGroup for it

This is the most expensive mistake in the whole pipeline, because it fails **completely
silently**. BeamNG loads `items.level.json` recursively, but it only descends into a sibling
folder when the parent file declares a `SimGroup` whose name matches that folder:

```jsonc
// main/items.level.json           -> must declare the top-level group
{"class": "SimGroup", "name": "MissionGroup", "enabled": "1"}
```
```jsonc
// main/MissionGroup/items.level.json  -> declares the groups INSIDE MissionGroup
{"class": "SimGroup", "name": "sky_and_sun", "__parent": "MissionGroup"}
{"class": "SimGroup", "name": "Roads",       "__parent": "MissionGroup"}
{"class": "SimGroup", "name": "Buildings",   "__parent": "MissionGroup"}
```

An earlier revision declared `sky_and_sun` but not `Roads` or `Buildings`, and put the
sub-group declarations in the wrong file. The result: the terrain, spawn point and sky loaded,
and **zero roads and zero buildings were created** — with no error in the log. In the World
Editor the scene tree showed only `sky_and_sun`, `cs1_spawn` and the terrain, because nothing
else existed. `sky_and_sun` appeared to work purely because it happened to be declared.

`verify_conversion.py` now walks every `items.level.json` and fails if a folder containing
objects is not declared by its parent, and if a declared group such as `Roads` or `Buildings`
has no folder behind it.

### Other requirements

* `_preview.png` beside the level is requested by the free-roam selector; without it BeamNG logs
  `request_fail | reason=NOT_FOUND url=levels/<name>/_preview.png` on every level-list render.
* `CloudLayer` needs a `texture` field.
* A `CameraBookmark` without a `dataBlock` is rejected.
* `.ter.depth.png` is optional; without it the log notes fluids are disabled as a ground type.

---

# Reference material

## Verified BeamNG formats

Both parts were built against the real thing rather than from prose docs, and the generated
output is re-parsed and checked by `verify_level()` on every run. A 201 MB `.ter`, a wrapped
`items.level.json` array, a bad `rotationMatrix`, a missing shape reference, a node that is not
`[x, y, z, width]`, or a `TerrainBlock` pointing at a missing terrain are all hard failures.

Details confirmed against an installed BeamNG 0.39 and a real workshop city map
(`Bob_City_Map` → `levels/LosInjurus`):

| Fact | Value |
| --- | --- |
| `items.level.json` | **Line**-delimited: one JSON object per line, never wrapped in `[]`. An object must not be pretty-printed across lines. |
| Nested groups | The engine loads a folder's `items.level.json` when a `SimGroup` with that name exists in the parent — hence the `Roads/Roads_0/` split. |
| `DecalRoad` nodes | `[x, y, z, width]`; width is interpolated, node Z is re-projected onto terrain at runtime. |
| Road materials | Real names confirmed in `art/shapes/common/decalroads/main.materials.json`, e.g. `road_asphalt_2lane`, `m_dirt_road`, `road1_concrete`. |
| `.ter` binary | `u8 version`, `u32 size`, `u16[size²]` heights, `u8[size²]` layers, `u32 materialCount`, then NUL-terminated names. Little-endian. Current version **9**. |
| Terrain resolution | Must be a power of two, 128–8192. `world size = size × squareSize`. Height is `maxHeight / 65536` per stored unit. |
| Layer value 255 | Means "hole" (no terrain). The converter never writes it. |
| Terrain materials | Omitting `materialTextureSet` on the `TerrainBlock` selects the classic v1 path, so no texture arrays must be authored for terrain to render. |
| `TSStatic` | `shapeName`, `position`, `rotationMatrix` (9 floats, row-major), `scale` (3 floats). |
| Mod zip layout | `levels/` and `art/` must sit at the **archive root**, never inside a folder named after the mod. Both working reference mods start with `levels/`. |
| Level lighting | A level needs `LevelInfo`, `TimeOfDay`, `ScatterSky` and `CloudLayer`, plus a `SimGroup` declaration in `main/items.level.json`. Without them the map loads black. |
| Spawn markers | `SpawnSphere` needs `dataBlock: "SpawnSphereMarker"`, `radius` and `sphereWeight`; a bare sphere is not used for spawning. |
| Terrain materials | Reference by `internalName`, and use a name that exists. Confirmed in shipped content: `grass`, `Dirt`, `rock`, `gravel`, `sand`, `asphalt`, `rockydirt`. An invented name falls back to the warning material. A classic (v1) material also needs a real `diffuseMap` or the ground renders as the "no material" placeholder. |
| `ScatterSky.exposure` | Working levels cluster at 0.5–15 (median ~2) with `ambientScale` ~0.55–0.65. A value of 100 blows out the sky and leaves the ground black. |
| Colourless lights | A `PointLight`/`SpotLight` without `lightColor` renders in the engine default, a hot magenta that tints the whole map. |

### Converting the sample city

The Cannes export (2307 segments, 1463 buildings) converts in ~5 seconds:

```
terrain: 32.77 km square (8192x8192 @ 4 m/sample), 2493 elevation samples, height -5.3..647.2 m
materials : {'road_asphalt_2lane': 1244}
skipped   : {'Airplane Path': 431, 'Train Track': 303, 'Water Pipe': 194, 'Ship Path': 113, ...}
RESULT: OK -- 1244 roads (4400 nodes), 1463 buildings
```

### Standalone validator

The converter validates as it goes, but the schema/statistics checker is also useful on its own:

```bash
python tools/validate_city_layout.py path/to/city_layout.json
python tools/validate_city_layout.py city_layout.json --json report.json   # machine-readable
python tools/validate_city_layout.py city_layout.json --strict             # warnings fail
```

It checks the schema, curve geometry, building footprints and angles, district cross-references,
and prints statistics: total road km, width/lane histograms, prefab inventories, building mix,
height range, and CS1 plus estimated BeamNG bounding boxes.
Exit codes: `0` valid, `1` invalid (or warnings under `--strict`), `2` unreadable.

> A note on what it does *not* flag: CS1's Bézier does not coincide with the node chain. Across
> the Cannes export it sits **+1.000 m** above the node elevation on 1040 segments and
> **−0.300 m** below on 326, and on 259 segments its endpoints are pulled along the segment to
> handle junction corners. Neither value is authoritative, so the converter averages the node and
> Bézier elevations at segment ends to cancel the bias. The validator reports these as warnings,
> not errors.

---

## How the game API was verified

Game mods break silently when a field is wrong, so every member this mod touches was confirmed
by reflection against the shipping assemblies rather than from memory. The probes are kept in
`tools/dump/`. Confirmed findings that shaped the code:

| Fact | Why it matters |
| --- | --- |
| `NetSegment.GenerateBezier(ushort, ushort)` **is an instance method** and returns `ColossalFramework.Math.Bezier3` (in `ColossalManaged.dll`) | This is the road shape. `CalculateSegmentBezier` does **not** exist. |
| `Bezier3` fields are `a`, `b`, `c`, `d` | The four cubic control points. |
| `Building.m_width` / `m_length` are `byte` **cell counts**, not metres | Multiply by 8; `Building.Width`/`Length` properties already decode them. |
| `BuildingInfo.m_size` is the mesh bounding box in metres | Only source of a usable building height. |
| `Building` has **no** `m_district` field | District is sampled via `DistrictManager.GetDistrict(Vector3)`. |
| `District` holds only `m_flags`/name metadata — no colour, no prefab | Old tutorials that read `District.m_color` do not apply. |
| `NetSegment.Flags.Invert` (not `Inverted`) | The flag genuinely does not exist under that name. |
| `UIFontManager.Default` and `UITextureAtlas.GetSprite` do **not** exist | Fonts come from `UIView.defaultFont`; sprites from the `atlas[name]` indexer. |
| `UIView.HasInputFocus()` is **static** | Guards the hotkey against firing while typing. |
| `Path.Combine` has no 3-argument overload in the game's runtime | Use nested two-argument calls. |
| C# forbids `yield return` inside a `try` with a `catch` | Forced the batched harvest into the shape it now has. |

`tools/dump/ApiProbe.cs.txt` is a snippet to drop next to the mod temporarily if you ever need
to enumerate the actually-loaded atlases and sprite names at runtime.

---

## Testing without launching the game

The JSON writer and all DTOs are plain `System.*` code, so they are exercised outside the game:

```powershell
$man = 'E:\games\epic games\CitiesSkylines\Cities_Data\Managed'
csc /nologo /target:exe /nostdlib+ /noconfig `
  /r:"$man\mscorlib.dll" /r:"$man\System.dll" /r:"$man\System.Core.dll" `
  /r:"$man\UnityEngine.dll" /r:"$man\Assembly-CSharp.dll" `
  /r:"$man\ColossalManaged.dll" /r:"$man\ICities.dll" `
  /out:build\JsonWriterTests.exe mod\CS1ToBeamNGExporter.cs tools\test\JsonWriterTests.cs
.\build\JsonWriterTests.exe build
python tools\validate_city_layout.py build\sample_city_layout.json
```

The harness deliberately writes under a `de-DE` culture (comma decimals) and covers NaN,
Infinity, null curves, null strings, embedded quotes/newlines/tabs and non-ASCII text.

---

## Roadmap

* **Export the real CS1 terrain.** The biggest remaining gap: sample `TerrainManager`'s
  heightmap into the JSON so the terrain stops being an interpolation. This single change would
  fix coastlines, hills away from roads, and water.
* Water: export CS1 water sources so the sea and rivers can be placed as BeamNG `WaterPlane`s.
* Building fidelity: real meshes instead of proxy boxes for common prefabs, and export the CS1
  asset names so a future step can substitute BeamNG-native buildings.
* Road materials: map CS1 road classes onto richer BeamNG decal materials (lane markings, kerbs)
  using the width and lane histograms the validator already reports.
* Merge collinear CS1 segments into longer `DecalRoad`s to cut object count and improve AI lanes.
* Rails and paths: convert `Train Track` / `Pedestrian Path` into a separate group rather than
  dropping them, so they can be re-enabled with `--include-non-drivable`.
* Elevation: export CS1's elevated/bridge flags so elevated roads stay off the ground instead of
  being snapped to the terrain surface.

---

## Known limitations

Recorded because they are real and unresolved, not because they are being worked on immediately.

* **Ground colour is approximate.** A level normally ships its own large colour texture for the
  terrain's base layer. A converter cannot, and the engine ships no green *terrain* texture, so the
  greenest built-in set is used instead. Everything else about the ground -- tiling, detail, macro,
  normals, ground model -- is set from measured values.
* **Some base-game building materials do not resolve.** Materials declared inside another level's
  archive are not available when a shape is referenced from a different level, and the engine falls
  back to a warning material. Several are unresolved; the window materials have been defined.
* **`city_block3` and the other `west_coast_usa` building shapes are excluded** because their mesh
  origins sit hundreds of metres from their geometry, which makes them float when placed.
* **Terrain smoothness has one outlier.** The mean neighbour step is 2.6, but a single cell pair
  differs by a large amount -- one isolated cliff, about 0.0002% of cells.
* **`info.json` is written strictly**, while at least one shipped map ships a malformed one. No
  attempt is made to reproduce that.

## Repository layout

```
mod/       C# mod for Cities: Skylines 1 -- exports the city to JSON
tools/     Python converter, validator and conformance checker
docs/      Research notes, including a full technical reference for a working BeamNG map
exports/   Example city export
```

`docs/POLISH_ROADS_REFERENCE.md` is the most useful file here if you are building something similar.
It documents, from measurement rather than assumption, how a shipped BeamNG level is put together:
the `.ter` binary layout, terrain materials and their texture families, how ground physics is wired
through `groundmodelName`, the group and `__parent` rules for `items.level.json`, DecalRoad anatomy,
and lighting.

## A note on how this was built

Almost every difficult bug in this project was found by **measuring the built output**, not by
reading the code. The research notes record each one, including several where the first fix made
things worse and had to be reverted. If you extend this, the conformance checker
(`tools/dump/conformance.py`) is the thing that keeps those fixes from regressing -- it encodes the
rules learned the hard way, and it is worth running after every change.
