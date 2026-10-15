"""Fill in the lighting / scene-census section of the reference document."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()
placeholder = "*(lighting objects — analysis pending)*"
if placeholder not in text:
    raise SystemExit("lighting placeholder not found")

NEW = '''### 6.1 Lighting — every core object lives in one file

**All seven atmosphere objects sit in a single file**,
`main/MissionGroup/Level_object/items.level.json`, which holds 12 objects: `SimGroup` x2, `Camera`,
`CloudLayer`, `Forest`, `ForestWindEmitter`, `LevelInfo`, `Precipitation`, `ScatterSky`,
`TSStatic`, `TerrainBlock`, `TimeOfDay`. Exactly one of each -- no duplicate sky or time of day.

`LevelInfo`, complete:

```json
{
    "name": "theLevelInfo", "class": "LevelInfo",
    "persistentId": "72f5ad62-f63c-41d6-a97d-23a4e9735bad",
    "__parent": "Level_object",
    "animate": "0", "canvasClearColor": "White",
    "decalBias": 0.00100000005,
    "desc0": "Beautiful Polish landscapes that include settlements, villages, rivers and lakes.",
    "fogAtmosphereHeight": 300, "fogColor": [1, 1, 1, 1],
    "fogDensity": 0.000280000007, "fogDensityOffset": 100,
    "globalEnviromentMap": "cubemap_polish_roads_remaster_reflection",
    "gravity": -9.81000042, "levelName": "Polish Roads 3.1",
    "soundAmbience": "Reverb_IT_Open",
    "temperatureCurveC": [0, 31, 0.2, 31, 0.5, 31, 0.7, 31, 1, 31],
    "visibleDistance": 9000
}
```

The key is spelled **`globalEnviromentMap`** -- missing the `n` in "Environment". That misspelling
is the real field name. Our logs complained
`LevelInfo dont have defined globalEnviromentMap for vehicle's static reflections` precisely because
we omitted it; it wants a cubemap name such as `cubemap_polish_roads_remaster_reflection`.

`temperatureCurveC` is five (time, value) pairs, flat at 31 C around the clock. Note `levelName`
says "Polish Roads 3.1" while `info.json` says "Summer 3.3" -- the shipped file disagrees with
itself.

`TimeOfDay`, complete except the rotation matrix:

```json
{
    "name": "tod", "class": "TimeOfDay", "__parent": "Level_object",
    "animate": "0", "axisTilt": 25, "azimuthOverride": 0,
    "enableStartTimeFallBack": false,
    "latitude": 50.3436432, "longitude": 18.8739395,
    "play": false, "startTime": 0.899999976, "time": 0.899999976,
    "utcOffset": "2", "version": 2
}
```

**The day/night cycle is frozen**: `animate` is `"0"`, `play` is `false`, and `startTime` equals
`time`, both `0.899999976` (about 21:36). Lat/lon are Silesia, Poland. `utcOffset` is a **string**.

`CloudLayer`, complete:

```json
{
    "name": "CloudLayer_1", "class": "CloudLayer", "__parent": "Level_object",
    "Textures": [{}, {}, {}],
    "baseColor": [1, 1, 1, 1], "coverage": 1.0999999, "height": 2,
    "windDirection": [0.906307817, -0.42261827], "windSpeed": 0.1
}
```

**`Textures` is an array of three EMPTY objects** -- no texture paths given -- and the level renders.
This matters: our hand-written `CloudLayer` without a `texture` field made the engine reject the
whole lighting group with `Unable to deserialize file .../sky_and_sun/items.level.json`, leaving
the map black. Copying the template level's block verbatim is the safe course.

`Precipitation` exists but is **inert**: `numDrops: 0`, `animateSplashes: false`. Its name,
`dyszcz`, is Polish for rain.

Two `ForestWindEmitter`s exist with **different property sets** -- one weak local emitter
(`strength: 0.15`, river-reflection cubemap) under `Trawa2D/`, and one global wind
(`radius: 100009`, `radialEmitter: true`, gust and turbulence enabled) under `Level_object/`.

### 6.2 Dynamic lights

PointLight and SpotLight **do** exist: 248 + 1,049 = **1,297** objects, of which **1,201 (92.6%)**
sit in the single file `main/MissionGroup/DynamicLights/items.level.json` (SpotLight 1018,
PointLight 183, SimGroup 1). A sibling folder `DynamicLights/lampy/` holds 321 `TSStatic` lamp
models that the lights attach to.

So illumination is: one `ScatterSky` driven by a **frozen** `TimeOfDay`, plus 1,297 explicit light
objects. No day/night curve is doing the work.

### 6.3 Scene class census

30 distinct `class` values, **31,514 objects** in total:

| Class | Count | Class | Count |
|---|---|---|---|
| `TSStatic` | 22,021 | `BeamNGPointOfInterest` | 20 |
| `DecalRoad` | 6,740 | `BeamNGGameplayArea` | 20 |
| `SpotLight` | 1,049 | `WaterBlock` | 14 |
| `SFXEmitter` | 618 | `MeshRoad` | 12 |
| `PointLight` | 248 | `SpawnSphere` | 10 |
| `SimGroup` | 246 | `Camera` | 4 |
| `BeamNGWaypoint` | 157 | `River` | 3 |
| `BeamNGTrigger` | 121 | `Prefab` | 3 |
| `Portal` | 58 | `ForestWindEmitter` | 2 |
| `ParticleEmitterNode` | 50 | `LevelInfo`, `CloudLayer`, `TerrainBlock`, | 1 each |
| `CameraBookmark` | 37 | `TimeOfDay`, `Precipitation`, `Forest`, | |
| `Zone` | 30 | `ScatterSky` | |

Of the 259 `items.level.json` files under `main/`, **23 are empty** (zero objects) -- an empty group
folder is normal and harmless, and the engine ignores it. No object anywhere lacks a `class`
attribute.

### 6.4 TSStatic field usage

| Property | Count (of 22,021) |
|---|---|
| `shapeName` | 22,021 |
| `isRenderEnabled` | 21,860 |
| `rotationMatrix` | 20,977 |
| `useInstanceRenderData` | 19,299 |
| `persistentId` | 14,670 |
| `instanceColor2` | 8,607 |
| `scale` | 5,961 (27% -- most instances are unscaled) |
| `instanceColor` | 5,807 |

The `instanceColor` family is how this map varies the appearance of repeated base-game shapes
**without creating a material per variant**, which is directly relevant to the instruction to
prefer built-in materials over created ones. Our converter now sets `instanceColor` for exactly
this reason.'''

text = text.replace(placeholder, NEW, 1)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)

print("filled the lighting section")
print("document is now", len(text.split("\n")), "lines")
print("placeholders remaining:", text.count("analysis pending"))
