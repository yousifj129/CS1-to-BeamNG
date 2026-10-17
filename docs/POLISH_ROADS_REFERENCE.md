# polish_roads_v2 — Complete Technical Reference

**Purpose.** This document records, in full, how a working third-party BeamNG.drive level is built, so
that the CS1→BeamNG converter can be written to match it exactly rather than by inference.

**Source of truth.** `%LOCALAPPDATA%\BeamNG\BeamNG.drive\current\mods\repo\polish_roads_repo.zip`
(2.2 GB). Level prefix inside the archive: `levels/polish_roads_v2/`.

**Why this map.** It is a large, published, working city map. Its terrain renders correctly. Ours
does not, and this document is the record of everything that differs.

All numbers below were read directly from the archive bytes, not inferred.

---

## 1. The definitive symptom, and why it misled everyone

Our level logs exactly **96** lines of:

```
E|TerrainCellMaterial| Missing Terrain texture: /
```

every single time, with **one** cache key:

```
temp/art/terrainMaterialCache/CF2ACDF30CCC7F6C.dds
```

A working map (measured from the user's own log of polish) produces **nine distinct cache keys and
zero errors**. So the engine does pack terrain textures per cell in a working level and cannot in
ours.

The error count being *identical* across grass, asphalt, engine-native textures, a verbatim copy of
another map's material, a repaired `.ter`, and a corrected `baseTexSize` was the single most
important clue, and it was read as "the material is wrong" for a long time. It means the material
definition is never reached. **The material was never the problem.** Four separate real bugs were
found and fixed while chasing it (see §7), and none of them changed this number, because none of
them was the cause.

---

## 2. What the engine generates: the terrain material cache

This is the artefact whose creation is failing. Decoded from
`<install>\content\cache\terrainMaterialCache.zip` (1.2 GB, **533 entries**) and from the per-user
copies under `current\temp\art\terrainMaterialCache\` (51 entries after a few level loads).

Every entry is **exactly 1,398,276 bytes**. Decoding the DDS header of one:

| Field | Value |
|---|---|
| magic | `DDS ` |
| header size | 124 |
| flags | `0x000A1007` |
| width | **1024** |
| height | **1024** |
| pitch | 1,048,576 |
| depth | 1 |
| mip count | **11** |
| pixel format fourCC | **`DX10`** |
| caps / caps2 | `0x00401008` / `0x00000000` |
| extended header | 20 bytes (DX10 header after the 128-byte base) |
| payload | 1,398,148 bytes |

The payload matches **BC3 (DXT5)** at 1024×1024 with a full 11-level mip chain:

```
sum over mips of ceil(w/4)*ceil(h/4)*16  ==  1,398,128
1,398,276 total  ==  128 (base header) + 20 (DX10 header) + 1,398,128
```

**Conclusion:** the engine packs each terrain cell into a **1024×1024 DX10 BC3 texture array with 11
mip levels**. The filename is a 16-hex-digit digest (MD5-style), i.e. a content or configuration
hash. The `*.dds` files are all the same size because the array geometry is fixed and only its
contents vary.

`TerrainCellMaterial` is the code that builds this array. `Missing Terrain texture: /` is emitted
while it is filling the array, and the resource name printed is empty — which is why the message
ends in a bare `/` rather than naming a file. An empty name is consistent with the array being
built successfully but no source texture being bound to the slice being filled.

---

## 3. Level layout

The archive holds two levels: `levels/polish_roads_v2/` (5,040 entries) and
`levels/polish_roads_winter/` (6,498). Only the first is documented here.

36 files and 32 directories sit at the level root. Largest content directories, by uncompressed
size: `art/` 976 MB, `SketchUpCK/` 963 MB, `Tory_przejazdy/` 208 MB, `Chodniki/` 166 MB,
`From_east_coast_usa/` 89 MB. `dynamicAudioEmitters/` and `From_garage/` contain only zero-byte
entries.

At the level root, beside the usual `main/` and `art/`, there are files our converter does not
produce at all:

| File | Size | Purpose |
|---|---|---|
| `main.decals.json` | 358,757 | decal placement |
| `main.forestbrushes4.json` | 65,426 | forest brush definitions |
| `slotTrafficRoadNodeSnapshot.json` | 612,246 | AI traffic node snapshot |
| `signals.json` | 37,908 | traffic signal definitions |
| `signslControllerDefinitions.json` | 125 | signal controller |
| `city.sites.json` | 377,145 | city sites |
| `mainLevel.lua` | 17,067 | level script |
| `map.json`, `map.BNDL` | 186, 132 | minimap |
| `theTerrainrr.ter` | 12,583,231 | the terrain |
| 15 `.png` preview/selector images | ~1 MB each | level selector tiles |

Ten spawn points are declared, each with its own selector image, and `defaultSpawnPointName` is
`spawns_estate1`. The spawn objects themselves are `SpawnSphere`s in
`main/MissionGroup/PlayerDropPoints/`.

### 3.1 `info.json`

Complete, verified content (2,045 bytes):

```json
{
    "title": "Polish Roads - Summer 3.3",
    "description": "Fikcyjna mapa, przedstawiajaca Cebulowo.",
    "previews": ["polish_roads_preview1.png", "...", "polish_roads_preview7.png"],
    "size": [2048, 2048],
    "biome": "Europe, Poland, Polska",
    "date": 1537120800,
    "region": "europe",
    "roads": "Asfaltowe, szutrowe",
    "suitablefor": "RolePlay, Fanow Polskich produkcji.",
    "features": "Settlements, villages, forests, farmland.",
    "authors": "Jano_2564, mcct, Waboll, Akapibara, Bartolgame, Car_Killer, Dummiesman",
    "defaultSpawnPointName": "spawns_estate1",
    "country": "levels.common.country.Poland",
    "spawnPoints": [
        {"translationId": "Cebulowo 25-Lecia PRL", "objectname": "spawns_estate2", "preview": "polish_roads_estate2.png"},
        {"translationId": "Cebulowo Wieczorka",     "objectname": "spawns_estate1", "preview": "polish_roads_estate1.png"}
    ]
}
```

**`info.json` is not valid strict JSON.** The `"roadRules"` key is missing its colon before the
value object:

```
    "roadRules"
    {
      "turnOnRed": true
    }
```

Every other key is well-formed. This is a real defect in the shipped file, reproduced verbatim
rather than corrected — and it matters, because anything that parses `info.json` strictly will
fail on it. The engine evidently tolerates it.

`size` is `[2048, 2048]`, matching the terrain's 2048 grid and 1 m cell size exactly.

`previews` is an array of image filenames resolved relative to the level folder, and each
`spawnPoints` entry carries its own `preview`. The level selector reads both.

### 3.2 `main/items.level.json` and the group tree

Group resolution rules established the hard way, and confirmed against this map:

* `items.level.json` is **line-delimited** — one complete JSON object per physical line. An object
  split across lines makes the engine reject the whole file with
  `E|deserializeLineObjects| Unable to deserialize file ...` and silently load nothing from it.
* A folder is only descended into when the sibling `items.level.json` declares a `SimGroup` whose
  **name equals the folder name**.
* An object's `__parent` must name a SimGroup that is **declared**, and it must be the group that
  **owns the containing folder**. Objects parented to a group that does not own their folder are
  dropped silently — no log line, no error.

Measured on this map: `main/MissionGroup/Dworzec_traffic/items.level.json` holds 38 DecalRoads, all
with `"__parent": "Dworzec_traffic"` — folder name and parent identical. Likewise
`DynamicLights` (1201 lights), `BarierkiDrogowe` (1233 TSStatics), `road_inv` (701 DecalRoads).

---

## 4. Terrain

### 4.1 `TerrainBlock`

Measured from this map:

```json
{
  "class": "TerrainBlock",
  "persistentId": "07cef48a-9e22-4124-b1aa-1b83609aee5f",
  "__parent": "Level_object",
  "position": [-1024, -1024, 0],
  "baseTexSize": 2048,
  "cubemap0": "cubemap_ckmorning",
  "fullReflect0": "nil",
  "isSelectionEnabled": false,
  "lightMapSize": 1024,
  "locked": true,
  "materialTextureSet": "polish_roads_v2TerrainMaterialTextureSet",
  "maxHeight": 50,
  "reflectDetailAdjust0": "2",
  "reflectMaxRateMs0": "50",
  "reflectNormalUp0": "nil",
  "reflectPriority0": "1",
  "reflectTexSize0": "nil",
  "screenError": 64,
  "terrainFile": "/levels/polish_roads_V2/theTerrainrr.ter",
  "useOcclusionQuery0": "nil"
}
```

Points of note, several of which we were missing:

* **No `squareSize`.** Measured across four working maps (`grille_mbwr_city`, `polish_roads_v2`,
  `Valo_City`, `Generic_City`), only `Valo_City` (15.625) and `Generic_City` (3) set it at all.
  Omitting it means the engine default.
* `position` is `[-1024, -1024, 0]` — for a 2048 grid that is a 2 km span centred on the origin.
* `baseTexSize` **2048**, matching its texture set's `baseTexSize`.
* `lightMapSize` **1024** — absent from our block entirely.
* `cubemap0`, `fullReflect0`, `reflect*` — a reflection configuration block we never emit.
* `screenError` **64**. The official documentation describes this as *"Legacy/not generally useful
  for modern authoring."*
* `__parent` is `Level_object`, a group inside `MissionGroup`, not `MissionGroup` directly.

### 4.2 `terrain.json`

```json
{
  "version": 9,
  "size": 2048,
  "binaryFormat": "version(char), size(unsigned int), heightMap(heightMapSize * heightMapItemSize), layerMap(layerMapSize * layerMapItemSize), layerTextureMap(layerMapSize * layerMapItemSize), materialNames",
  "datafile": "/levels/polish_roads_V2/theTerrainrr.ter",
  "heightmapImage": "/levels/polish_roads_V2/theTerrainrr.terrainheightmap.png",
  "heightMapSize": 4194304,
  "heightMapItemSize": 2,
  "layerMapSize": 4194304,
  "layerMapItemSize": 1,
  "materials": ["Dirt", "Kamienie4", "DirtTrawa", "EdgeGrass", "Grass", "groundmodel_asphalt1", "groundmodel_asphalt_broken", "..."]
}
```

`heightMapSize` == `layerMapSize` == `size²` == 4194304.

### 4.3 The `.ter` binary format, version 9 — CORRECTED

**A correction that overturns an earlier entry in this document.** The `.terrain.json` file
advertises its own `binaryFormat` as containing a `layerTextureMap` array. **It does not.** That
descriptive string is wrong, and trusting it produced a file 67 MB too large.

Established arithmetically against this map's `theTerrainrr.ter` — 12,583,231 bytes, version 9,
size 2048:

```
assumed:  5 + size²*2 + size² + size² + 4 + namebytes  = 16,777,535
actual:                                                 12,583,231
shortfall:                                               4,194,304  = exactly one size²
```

The real layout, which reconciles to the byte:

```
u8   version                          1 byte
u32  size                             4 bytes
u16  heightMap[size*size]             size² * 2 bytes    =  8,388,608
u8   layerMap[size*size]              size² bytes        =  4,194,304
u32  materialCount                    4 bytes
...  materialCount names, each u8 length prefix + UTF-8 bytes
```

```
5 + 8,388,608 + 4,194,304 + 4 + 310  =  12,583,231        zero leftover
```

The name block encoding was verified two independent ways:

| Encoding | Result |
|---|---|
| `u32 count` + **length-prefixed** UTF-8 names | consumes **314/314** bytes exactly |
| `u8 count` + length-prefixed | consumes 285/314 — wrong |
| `u32 count` + **NUL-terminated** | impossible: the block contains **no NUL byte at all** |

The same layout reproduces on the sibling `polish_roads_winter` level's `.ter` (12,583,052 bytes,
11 materials), so this is the version 9 format rather than a damaged file.

**Names are stored in `layerMap` index order, not alphabetically.** `main.materials.json` stores its
32 keys in ASCII-alphabetical order, while the `.ter` lists material index 0 as `Dirt` and index 4
as `Grass` — a different order. Index *n* in the layer map selects the *n*th name in the `.ter`
list.

**`layerMap` is a full material-index map**: min 0, max 255, **35 distinct values** across 31
materials. Dominant entries: index 4 (`Grass`) on 1,575,973 cells and index 16 (`forest_floor`) on
1,072,382. Four values (58, 69, 246, 255) exceed the material count and index nothing — 82 cells,
0.002%, evidently editor noise.

### 4.3b Other verified `.ter` facts

* `heightMapSize` and `layerMapSize` in `.terrain.json` are **cell counts** (2048² = 4,194,304), not
  bytes. Our writer emitted the same number, which is correct.
* The `.terrain.json` here names the level `polish_roads_V2` (capital V) while every zip entry uses
  lowercase `v`. The engine is evidently case-insensitive for this.
* Its `heightmapImage` points at `theTerrainrr.terrainheightmap.png`, and **no such entry exists
  anywhere in the archive**. A level renders correctly with that image absent, so the heightmap PNG
  is not what the engine loads — the `.ter` is.

### 4.4 Terrain material

Thirty-one `TerrainMaterial` entries plus one `TerrainMaterialTextureSet`:

```json
{
  "name": "polish_roads_v2TerrainMaterialTextureSet",
  "class": "TerrainMaterialTextureSet",
  "persistentId": "f292727a-935a-4797-badf-7ca8b804ea89",
  "baseTexSize": [2048, 2048],
  "detailTexSize": [1024, 1024],
  "macroTexSize": [1024, 1024]
}
```

First material, `Asphalt_wet`, verbatim:

```json
{
  "name": "Asphalt_wet-dc79eb3a-90df-49a8-9814-4773f2049bad",
  "internalName": "Asphalt_wet",
  "class": "TerrainMaterial",
  "persistentId": "dc79eb3a-90df-49a8-9814-4773f2049bad",
  "annotation": "ASPHALT",
  "groundmodelName": "SLIPPERY",
  "macroDistances": [0, 10, 100, 3000],
  "detailDistances": [0, 0, 30, 60],

  "baseColorBaseTex":      "/levels/polish_roads_v2/art/terrains/t_terrain_base_b.png",
  "baseColorBaseTexSize":  2048,
  "baseColorMacroTex":     "/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_b.png",
  "baseColorMacroTexSize": 80,
  "baseColorMacroStrength": [0.5, 0.699999988],
  "baseColorDetailTex":    "/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_b.png",
  "baseColorDetailStrength": [0.5, 0.5],

  "normalBaseTex":         "/levels/polish_roads_v2/art/terrains/t_terrain_base_nm.png",
  "normalBaseTexSize":     2048,
  "normalMacroTex":        "/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_nm.png",
  "normalMacroTexSize":    80,
  "normalDetailTex":       "/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_nm.png",

  "roughnessBaseTex":      "/levels/polish_roads_v2/art/terrains/t_terrain_base_r.png",
  "roughnessBaseTexSize":  2048,
  "roughnessMacroTex":     "/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_r.png",
  "roughnessMacroTexSize": 80,
  "roughnessMacroStrength": [0.899999976, 0.899999976],
  "roughnessDetailTex":    "/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_r.png",
  "roughnessDetailStrength": [0.899999976, 0.5],

  "aoBaseTex":             "/levels/polish_roads_v2/art/terrains/t_terrain_base_ao.png",
  "aoBaseTexSize":         2048,
  "aoMacroTex":            "/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_ao.png",
  "aoMacroTexSize":        80,
  "aoDetailTex":           "/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_ao.png",

  "heightBaseTex":         "/levels/polish_roads_v2/art/terrains/t_terrain_base_h.png",
  "heightBaseTexSize":     2048,
  "heightMacroTex":        "/assets/materials/terrain/asphalt/macro_asphalt/t_macro_asphalt_h.png",
  "heightMacroTexSize":    80,
  "heightDetailTex":       "/assets/materials/terrain/asphalt/t_asphalt_02/t_asphalt_02_h.png"
}
```

**Five texture families per material**, each with a base, macro and detail texture:

| Family | Base | Macro | Detail |
|---|---|---|---|
| baseColor | ✓ | ✓ | ✓ |
| normal | ✓ | ✓ | ✓ |
| roughness | ✓ | ✓ | ✓ |
| ao | ✓ | ✓ | ✓ |
| height | ✓ | ✓ | ✓ |

**Key structural observations:**

1. **The base family is local to the level; macro and detail come from the engine's `/assets/`
   library.** This is a deliberate split, not an accident: 5 textures are shipped, 10 are shared.
2. Our material was missing **`*DetailTexSize`** until this comparison. Skeleton Coast's material
   carries a size on every detail texture (`baseColorDetailTexSize: 3`); ours carried only base and
   macro sizes. This is the one field-level difference that survived every earlier comparison.
3. The material's `name` is `<internalName>-<persistentId>`, and the texture set's `name` is
   `<level>TerrainMaterialTextureSet`. Neither has to follow that pattern — Skeleton Coast's set is
   named `murokmaktos-first-mapTerrainMaterialTextureSet`, after the author — but the TerrainBlock
   reference must match whatever the set is named.

### 4.5 Texture provisioning — three mechanisms observed

Measured across the working maps:

| Map | Base textures | Detail / macro textures |
|---|---|---|
| `polish_roads_v2` | local files under `art/terrains/` | `/assets/materials/terrain/...` engine paths |
| `grille_mbwr_city` | local files, names beginning `#` | `/levels/...` cross-level paths, backslash separator |
| `skeleton_coast` | local files, 4096×4096 | `.link` sidecar files |

The `.link` mechanism, from Skeleton Coast — a small JSON document beside the texture:

```json
{"path":"/levels/johnson_valley/art/terrains/t_dirt_loose_b.png","type":"normal"}
```

There are roughly 100 of these in that map. **Neither our level nor any of our earlier attempts used
`.link` files at all.** It is how a map references a texture that lives in another level without
copying it.

---

## 5. Roads

### 5.1 Layout

**6,740 `DecalRoad` objects across 16 files.** Each file's `__parent` value equals the name of the
folder containing it — verified for all 16, no exceptions:

| Count | File | `__parent` |
|---|---|---|
| 4,946 | `…/DecalRoad_Meshroady/DecalRoadsy/items.level.json` | `DecalRoadsy` |
| 701 | `main/MissionGroup/road_inv/items.level.json` | `road_inv` |
| 681 | `…/_pliki__modele/Caly_Burdel_Z_Italy/items.level.json` | `Caly_Burdel_Z_Italy` |
| 178 | `…/Dworzec_stuff/Dworzec_dodatkii/items.level.json` | `Dworzec_dodatkii` |
| 148 | `…/PGR_Rzeczy/pgr_decalroad/items.level.json` | `pgr_decalroad` |
| 38 | `main/MissionGroup/Dworzec_traffic/items.level.json` | `Dworzec_traffic` |
| 16, 10, 7, 4, 3, 3, 1, 1, 1 | *(eight further files)* | *matching folder names* |
| **2** | `main/MissionGroup/items.level.json` | `MissionGroup` |

Complete first object, verbatim:

```json
{"class":"DecalRoad","persistentId":"345dadf2-9e2b-4a47-abad-1f0eea925a79","__parent":"Dworzec_traffic","position":[-418.138641,-608.98822,37.8961639],"detail":1,"drivability":1,"gatedRoad":true,"improvedSpline":true,"material":"road_invisible","nodes":[[-418.138641,-608.98822,37.8961639,6],[-426.422882,-624.001526,38.0299339,6],[-440.017487,-648.657959,38.0966225,6]],"overObjects":true}
```

Two DecalRoads sit directly in `MissionGroup` itself rather than in a sub-group — the only objects
in the level parented to a non-leaf group.

Node counts across all 6,740 roads: **min 2, median 3, max 101, mean 6.03.** Percentiles: p5=2,
p25=2, p50=3, p75=7, p95=19, p99=39. **2,840 roads (42.1%) have exactly two nodes** — so a working
map is *also* built from many short two-node decals. This is worth stating plainly, because our
converter chained 1,244 stubs into 173 long polylines on the theory that short decals cause gaps.
That theory is not supported by this map, which is full of them.

All 40,637 node arrays have exactly four elements. The fourth is the road width: min 0.1,
**median 3**, max 22, mean 3.12, across 401 distinct 32-bit float values. Dominant widths are
2 (18.0%), 3 (11.0%), 4 (7.4%), 1 (5.8%), 5 (4.5%), 8 (3.7%). Near-duplicates such as
`0.999999642` and `1.0` both occur, which is float representation rather than intent.

81 distinct `material` values are used, mixing road surfaces, lane markings, decals borrowed from
other maps (`italy_road_edge_damage_minor` 305, `italy_road_markings_zebra` 118) and maintenance
overlays (`repair1`, `repair2`, `road_patches1`, `drain2`). The most common are
`m_road_edge_dirt_grass` 888, `road_invisible` 773, `road_asphalt_2lane` 476, `m_line_white` 438,
`line_white_dashed` 325.

### 5.1b Complete DecalRoad key inventory

| Key | Present / 6740 | Values |
|---|---|---|
| `class`, `persistentId`, `__parent`, `position`, `material`, `nodes` | 6740 (100%) | — |
| `improvedSpline` | 6481 | `true` only — never `false` |
| `detail` | 6409 | `0.5` ×4615, `1` ×1642 |
| `distanceFade` | 5878 | 23 distinct, clustered on presets |
| `renderPriority` | 4622 | `9` ×1149, `1` ×812, `8` ×555 |
| `startEndFade` | 4154 | ~110 distinct pairs; `[1,1]` ×1461 |
| `textureLength` | 3976 | 80+ distinct; `9` ×819, `10` ×629 |
| `decalBias` | 1008 | `0.000500000024` ×1001 |
| `drivability` | 841 | `1` ×658, `0.5` ×154 |
| `overObjects` | 493 | `true` only |
| `gatedRoad` | 401 | `true` only |
| `speedLimit` | 311 | strings in **m/s**, 3 decimals (`"15.278"` = 55 km/h) |
| `zBias` | 286 | `2` ×274 |
| `oneWay` | 251 | `true` only |
| `locked` | 185 | |
| `smoothness` | 150 | `0.300000012` ×138 |
| `hiddenInNavi` | 98 | |
| `flipDirection` | 62 | |
| `looped` | 43 | |
| `name` | 35 | |
| `breakAngle` | 22 | `2` ×7, `1` ×6 |
| `hidden` | 20 | |
| `autoJunction` | **6** | **`false` ×6** |
| `isSelectionEnabled` | 5 | |
| `risk` / `agression` / `agresion` | 4 / 3 / 1 | two different misspellings of "aggression" |
| `endTangent` | 1 | |
| **`autoLanes`** | **0** | **never present anywhere in the level** |

Two further observations worth recording:

* `improvedSpline`, `oneWay`, `gatedRoad` and `overObjects` are **only ever written as `true`**.
  The key is either present-and-true or absent; `false` never appears.
* `distanceFade` uses only 23 distinct values across 5,878 objects, heavily clustered on presets:
  `[160,60]` ×1181, `[160,50]` ×1167, `[100,50]` ×700, `[170,80]` ×430, `[120,50]` ×344.
  Our converter previously emitted `[3000,500]`, roughly 20× the near value of anything used here.

### 5.2 The `autoJunction` question

Measured: of **6,740** DecalRoads, `autoJunction` is present on **6** -- and in all six cases its
value is **`false`**. `autoLanes` is present on **none**.

This was once read as "autoJunction is wrong and should be removed", which was a mistake. This
map **hand-authors its junctions**: dedicated groups such as `Dworzec_traffic` (38 roads) and
`road_inv` (701 roads) exist specifically to build junction and invisible-road geometry by hand,
and a further 4,946 decals sit under `DecalRoad_Meshroady/`. A converted CS1 city has none of
those hand-built pieces, so automatic joining is the appropriate behaviour there even though this
map does not need it.

`autoJunction` and `autoLanes` are therefore **kept enabled** in our converter, by explicit
instruction, as a deliberate divergence from this map.

Worth recording alongside it: this map's node-count distribution shows **2,840 two-node roads
(42.1%)**. A working map is built from many short decals, so short decals are not in themselves
the cause of gaps.

### 5.3 DecalRoad property frequencies

The complete inventory is in section 5.1b above, measured from all 6,740 objects. Two further
observations are worth stating separately:

* `improvedSpline`, `oneWay`, `gatedRoad` and `overObjects` are **only ever written as `true`**.
  The key is either present-and-true or absent; `false` never appears.
* `distanceFade` uses only **23 distinct values** across 5,878 objects, heavily clustered on
  presets rather than edited per road.

Our converter previously emitted `distanceFade [3000,500]` and `decalBias 0.002`, each roughly
an order of magnitude away from anything this map uses.

---

## 6. Objects and lighting

`TSStatic` counts measured in this map: **22021**, against 1463 in ours. Property usage:

| Property | Count |
|---|---|
| `shapeName` | 22021 |
| `isRenderEnabled` | 21860 |
| `rotationMatrix` | 20977 |
| `useInstanceRenderData` | 19299 |
| `persistentId` | 14670 |
| `instanceColor2` | 8607 |
| `scale` | 5961 (only 27% — most instances are unscaled) |
| `instanceColor` | 5807 |

The `instanceColor` family is worth noting: it is how this map varies the appearance of repeated
assets **without creating a material per variant**, which is directly relevant to the instruction to
prefer built-in materials over new ones.

### 6.1 Lighting — every core object lives in one file

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
this reason.

---

## 7. Bugs found in our converter during this investigation

Each was a genuine defect, verified independently of the terrain-texture symptom. All are fixed.

1. **`.ter` missing its fifth section.** `layerTextureMap` was never written, making the file
   exactly `size²` bytes short, so the engine read the material count past the end of the data. Now
   written, with a hard length assertion.
2. **`baseTexSize` disagreement.** `emit_terrain_materials()` sets the base size that the
   `TerrainBlock` writes, but the build ran it **after** `emit_terrain_block()`, so the block
   declared `1024` against a set of `[4096,4096]`. Build order corrected.
3. **`*DetailTexSize` absent.** The material declared base and macro sizes only.
4. **Texture names containing `#` and backslash separators**, inherited by copying another map's
   material verbatim. `#` begins a fragment in URL/VFS handling. Both removed.
5. **Silent parent-group drops.** Objects parented to a group that did not own their folder were
   dropped with no log output; the Roads folder appeared empty while the geometry parsed cleanly.
   Fixed, and a verifier check added that is negative-tested.
6. **Stale unpacked level override.** BeamNG resolves `current/levels/<name>/` *before* the same
   level inside a mod. A folder containing only `main.decals.json` (281 bytes) shadowed the entire
   archive. Now detected and removed on every install.
7. **Verifiers sharing the converter's wrong assumptions.** Both the converter's own check and the
   independent verifier read the `.ter` with a four-section layout, so they agreed with each other
   about a corrupt file. Both corrected.

**The lesson that matters for the rewrite:** defects in the *encoding* were found by comparing
against a working artefact byte-for-byte; defects in the *content* were found by reading the
engine's own output. Reasoning from first principles about how the format "should" work produced
five wrong hypotheses in a row.

---

## 7b. Built-in material and texture sourcing — resolved by measurement

The instruction is to use **built-in textures only** and **built-in materials rather than created
ones**. Both are achievable, and the mechanism was found by measurement rather than assumption.

### Where terrain materials live

There is **no global terrain material library**. Scanning all 44 archives under
`<install>\content\` found terrain material definitions in exactly 15 files, one per shipped level:

```
levels/automation_test_track/art/terrains/main.materials.json
levels/Cliff/art/terrains/main.materials.json
levels/derby/art/terrains/main.materials.json
levels/driver_training/art/terrains/main.materials.json
levels/east_coast_usa/art/terrains/main.materials.json
levels/gridmap_v2/art/terrains/main.materials.json
levels/hirochi_raceway/art/terrains/main.materials.json
levels/Industrial/art/terrains/main.materials.json
levels/italy/art/terrains/main.materials.json
levels/johnson_valley/art/terrains/main.materials.json
levels/jungle_rock_island/art/terrains/main.materials.json
levels/small_island/art/terrains/main.materials.json
levels/template/art/terrains/main.materials.json
levels/Utah/art/terrains/main.materials.json
levels/west_coast_usa/art/terrains/main.materials.json
```

So a terrain material is always declared **per level**, but the definitions themselves are engine
content. Taking one verbatim is using a built-in material; it is not authoring a new one.

### Which materials are self-contained

Measured for the first material in each file, counting how many of its 15 texture references point
inside its own level versus into the engine's `/assets/` library:

| Level | Materials | Own-level textures | Engine (`/assets/`) textures |
|---|---|---|---|
| `east_coast_usa` | 15 | 5 | **10** |
| `west_coast_usa` | 11 | 5 | **10** |
| `Utah` | 13 | 5 | **10** |
| `template` | 14 | 15 | 0 |
| `italy` | 15 | 15 | 0 |
| `johnson_valley` | 14 | 15 | 0 |
| *(others)* | — | 15 | 0 |

`east_coast_usa`, `west_coast_usa` and `Utah` already follow the **5-local / 10-engine** split that
polish_roads_v2 uses, so their materials reference the engine library for ten of fifteen slots —
directly satisfying "use the built-in textures".

### Cross-level texture references are proven to work

This was the decisive check. Across all 31 materials in polish_roads_v2:

```
engine /assets   237 references
own level        218 references
OTHER level       10 references     <- all pointing at east_coast_usa
```

Polish references **ten textures that live inside `east_coast_usa`** and its ground renders. So a
BeamNG terrain material can name a texture inside a *different mounted level* and the engine will
resolve it.

**Consequence for the rewrite:** the five base textures do not have to be copied at all. They can be
referenced in place from an engine level, exactly as polish references `east_coast_usa`. That means:

* **zero textures authored or copied** — every path is built-in engine content
* **zero materials created** — one engine level's material is taken verbatim

This is what §8 item 1 now specifies.

---

---

## 7c. Terrain tiling — `*TexSize` are metres per tile

The `*TexSize` fields are **the world size one texture tile covers, in metres**, not pixel
dimensions. That distinction caused real trouble: the terrain material was taken from
`east_coast_usa`, a large open-world map where a `baseColorBaseTexSize` of 2048 m is reasonable.
Applied to our 32.7 km terrain, one tile smeared across an enormous area and the ground read as
blocky, pixelated colour.

`macroDistances` and `detailDistances` are the distances at which the macro and detail families take
over from the base. Ours were `[0, 10, 100, 3000]` and `[0, 0, 30, 60]`, which kept the huge base
texture visible out to 3000 m.

Measured on this map: `baseColorBaseTexSize` 2048, `baseColorMacroTexSize` 80,
`baseColorDetailTexSize` 3. So Polish ships a 2048 m base tile, an 80 m macro tile and a 3 m detail
tile — a **ratio of roughly 680:27:1** across the three families.

Tuned values now in use, which tile finely enough for a 32.7 km map:

```
baseTexSize   256   (was 2048)
macroTexSize   32   (was   80)
detailTexSize   2   (was    4)
macroDistances   [0, 8, 40, 400]     (was [0, 10, 100, 3000])
detailDistances  [0, 0, 8, 20]       (was [0, 0, 30, 60])
```

## 7d. Material resolution scope — what is global and what is not

This is what causes the pale untextured "no material" window strips on buildings.

**A material declared inside a level resolves only for that level.** Several base-game building
shapes declare window materials in *italy's* archive:

```
Italy_bld_ind_windows   (5 of the 8 shapes we reference)
italy_bld_windows       (2 shapes)
windows_doors_reflective (3 shapes)
```

Referenced from another level, the first two do not resolve.

**But `content/art_shapes.zip` is mounted globally**, and it holds **39 material libraries**,
including:

```
art/shapes/objects/m_windows_glass_01/main.materials.json          lit windows, emissive
art/shapes/objects/m_transparent_glass_window/main.materials.json  clear-coated glass
art/shapes/objects/windows_doors_reflective/main.materials.json    reflective glazing
```

So `windows_doors_reflective` resolves on its own and must **not** be aliased — pointing it at plain
glass would replace a working reflective material with a worse one.

The fix for the other two is an alias, which authors nothing:

```json
{ "Italy_bld_ind_windows": { "name": "Italy_bld_ind_windows", "mapTo": "m_windows_glass_01", "class": "Material" },
  "italy_bld_windows":     { "name": "italy_bld_windows",     "mapTo": "m_windows_glass_01", "class": "Material" } }
```

`mapTo` redirects the name the shape asks for to a material the engine already has. No stages, no
parameters, no new material.

**The general rule, worth stating plainly:** before authoring a material, search the engine's
archives for it. `art_shapes.zip` and the `content/assets/materials/*.zip` set are mounted for every
level, and between them they already define most of what a converted city needs. Our converter's
first window-alias attempt used thirteen *guessed* names; reading the shapes'
`<library_materials>` blocks showed only two were real.

---

---

## 7e. Two defects that only the log could reveal

Both of these produced a level that *looked* partly right, which is why they survived several
rounds of static checking.

### A texture path that was one directory wrong

Once the `.ter` was correct the ground rendered, so the material appeared to be working. It was not:
the log then began naming the resources it could not find.

```
E|TerrainCellMaterial| Missing Terrain texture: /assets/materials/terrain/soil/dirt_rocky/t_dirt_rocky_r.png
```

Those five files do not exist under `soil/`. They are under `rock/`:

```
assets/materials/terrain/rock/t_dirt_rocky/t_dirt_rocky_{b,nm,r,ao,h}.png
```

The base family loaded and the **detail family silently did not**, so the ground showed the large
base tile with no fine detail -- which reads exactly as "the texture is too big". The material had
been copied from `east_coast_usa`, and the path was wrong from the start.

**Lesson:** a material whose texture paths have not each been verified against the install is not a
verified material. The converter now checks all fifteen, and the check is in the conformance report.

### Aliases written to a path the engine does not read

The window-material aliases were written to `levels/Cannes/main.materials.json` and
`art/shapes/<mod>/main.materials.json`. Neither is a path this engine loads for a level, so the
aliases had **no effect whatsoever**.

The one material library proven to load for a level is
`levels/<level>/art/terrains/main.materials.json` -- proven because the terrain material resolves
from it and the ground renders. The aliases are now merged into that same file as additional
top-level keys. If the engine loads it for the terrain, it registers them.

**Lesson:** write material definitions only where the engine demonstrably loads them from. "A file
with the right name in a plausible place" is not evidence of anything.

### Tiling, corrected

With the detail family actually loading, the tile sizes were still far too coarse. `*TexSize` is
metres per tile, so at 1024x1024 a 256 m tile is 25 cm per texel -- visibly blocky.

| Family | Polish | Ours (now) | Texel size at 1024 px |
|---|---|---|---|
| base | 2048 m | **10 m** | 9.8 mm |
| macro | 80 m | **4 m** | 3.9 mm |
| detail | 3 m | **2 m** | 2.0 mm |

Polish can use a 2048 m base tile because its world is about 2 km across. Ours spans 32.7 km, so
the same value smears one texture over sixteen times the area. Tile sizes have to be chosen for the
map's own scale, not copied from a map of a different size.

---

---

## 7f. The base terrain texture was a satellite map, not a texture

The single most misleading asset in this whole exercise.

`t_terrain_base_b.png` in `levels/east_coast_usa/art/terrains/` is **a top-down satellite image of
that level** -- you can see its roads, field boundaries and riverbeds -- and it is **not tileable**.
Repeating it drew a visible grid of maps across the ground, which reads as "the tile is too big"
even when the tile size is small. The screenshots show the grid seams plainly.

It is one of a five-file base family (`_b`, `_nm`, `_r`, `_ao`, `_h`) that a working level ships
under `art/terrains/`, and it is intended to be stretched **once** across that level's whole
terrain as a large-scale colour wash. It is not a surface texture and cannot be tiled.

### What to use instead

The engine ships genuinely seamless grass sets in `content/assets/materials/terrain.zip`, each a
complete 1024x1024 family:

| Set | Path |
|---|---|
| `t_grass_01` | `grass/t_grass_01/t_grass_01_{b,nm,r,ao,h}.png` |
| `t_grass_02` | `grass/t_grass_02/t_grass_02_{b,nm,r,ao,h}.png` |
| `ind_grass` | `grass/ind_grass/t_ind_grass_{b,nm,r,ao,h}.png` |
| `macro_grass` | `grass/macro_grass/t_macro_grass_{b,nm,r,ao,h}.png` |

Three are used, one per scale, so the three families do not repeat in step with each other:

```
base    t_grass_02      the ground colour
macro   t_macro_grass   large-scale variation, breaks up the repeat
detail  ind_grass       fine detail near the camera
```

### Tiling for map scale, not copied from another map

| | This map | Ours (final) |
|---|---|---|
| base | 2048 m | **8 m** |
| macro | 80 m | **2 m** |
| detail | 3 m | **0.5 m** |

Polish uses a 2048 m base tile because its world is about 2 km across and it *wants* the satellite
wash stretched over the whole thing. Ours spans 32.7 km, so a tile of that size covers a sixteenth
of the map. Tile sizes have to be chosen for the map's own extent.

### The general rule this keeps teaching

Three separate rounds were lost to the same mistake in different clothes:

1. a `.ter` field (`layerTextureMap`) invented from a descriptive string that was itself wrong;
2. a texture path (`soil/` vs `rock/`) assumed rather than checked;
3. a texture (`t_terrain_base_b`) assumed to be a surface texture because of its name.

**Look at what the asset actually is, and confirm the path resolves, before using it.** Both checks
are now in the conformance report: all fifteen paths are verified against the install, and the base
textures are asserted not to be `t_terrain_base*`.

---

---

## 7g. Why the ground rendered dark, and how terrain physics actually works

### The dark ground was the material definition, not the textures

The grass textures were measured directly out of `terrain.zip` and are perfectly normal:

| texture | mean RGB | min | max |
|---|---|---|---|
| `t_grass_02_b.png` | 111, 113, 107 | 55 | 195 |
| `t_grass_01_b.png` | 124, 124, 124 | 48 | 224 |
| `t_ind_grass_b.png` | 127, 127, 127 | 25 | 227 |
| `t_macro_grass_b.png` | 110, 110, 110 | 100 | 130 |

So the darkness came from the material itself. The field set had been assembled by hand, and a
working material declares **eight** strength modifiers that mine lacked:

```
baseColorDetailStrength   normalDetailStrength   roughnessDetailStrength
baseColorMacroStrength    normalMacroStrength    roughnessMacroStrength
detailStrength            macroStrength
```

plus the scale fields `diffuseSize`, `detailSize`, `macroSize` and the blend-range fields
`detailDistance`, `macroDistance`, `detailDistAtten`, `macroDistAtten`.

The material is now built by copying polish_roads_v2's `Grass` **field for field** and changing only
the texture paths, so the structure is known-good rather than guessed. It ends up with **53 fields**
against the reference's 43, because the base family additionally points at engine grass.

The one deliberate change from the reference: polish's base textures are `t_terrain_base_*`, and
that image **is the satellite map** that was tiling across the ground. All fifteen slots therefore
point at the engine's seamless grass sets instead.

### Terrain physics is `groundmodelName`, not the material's textures

Friction does not come from the terrain material's appearance at all. It comes from
`TerrainMaterial.groundmodelName`, resolved against the engine's `/art/groundmodels.json` and then
merged with any `levels/<level>/groundModels/*.json`, which is where a level may override it.

```
/art/groundmodels.json               (common, loaded first)
levels/<level>/groundModels/*.json   (merged after, same name = override)
```

Each entry carries `staticFrictionCoefficient`, `slidingFrictionCoefficient`,
`roughnessCoefficient`, `defaultDepth` and others. Static is grip before sliding, sliding is grip
while sliding; sliding should stay below static.

**The critical consequence for this map:** a `DecalRoad` is a *decal*. It changes how the ground
looks, not what the tyres grip. The surface under every road here is still the terrain's single
grass material, so road grip and off-road grip are necessarily identical until roads carry their own
surface. That is the real reason the roads drove like gravel, and no DecalRoad property can change
it.

A level ground model is therefore written at `levels/Cannes/groundModels/surfaces.json`, raising
`GRASS` to a firm surface (static 0.95, sliding 0.85) and declaring `ASPHALT` (static 1.10,
sliding 1.00) for a future road surface material to target.

---

---

## 9. Road surfaces, junction measurement, and building-derived roads

### 9.1 Roads must be painted into the terrain to have grip

A `DecalRoad` is a decal. It changes appearance, not friction. Friction comes from
`TerrainMaterial.groundmodelName` resolved per **terrain cell** through the `.ter` layer map.

So a road is only physically a road once its footprint is written into that layer map and given an
asphalt material. Two materials are now declared, and their order is load-bearing:

```
.ter material names, in order :  ["Grass", "Asphalt"]
layer map index 0             :  Grass
layer map index 1             :  Asphalt
```

Every layer byte is an index into the name list, so the two must never drift apart. Index 255 is
never written -- it punches a hole through the terrain rather than selecting a material.

**Measured result:** 208,847 asphalt cells, 0.311% of the terrain's 67 million, for the CS1-derived
network. Polish's own layer map uses 35 distinct indices across 31 materials.

### 9.2 The road discontinuity was measured, not assumed

I had assumed CS1 pulls segment endpoints along at junctions, so chains stopped short and left gaps.
**That is false.** Measuring all 2,307 roads and their 2,257 nodes:

| Test | Result |
|---|---|
| Max endpoint disagreement at a shared node | **0.000 m** |
| Shared nodes disagreeing by more than 1 m | **0** |
| Nodes used by more than one road | 2,224 |
| Nodes whose position duplicates a neighbour's (split nodes) | **1** |

The geometry is exactly connected. So the visible discontinuity was **the renderer, not the data**:

* `startEndFade [0.0, 0.0]` was being written. A fade of zero erases the road surface at every
  chain end -- and chain ends are exactly where roads meet junctions. Polish uses `[1,1]` on 1,461
  of its roads and reserves the low fades for markings. Ours is now `[1, 1]`.
* `distanceFade [160,60]` means the decal fades out between 60 m and 160 m, so roads dissolve in the
  middle distance. That matches the polish preset distribution exactly, so it was kept.

**A separate width bug was found:** the emitter computed `width = max(entry["width"], 6.0)`, which
**widens** every road narrower than 6 m instead of capping wider ones -- the opposite of what the
name `max_width` implies. Measured CS1 widths run 6..32 m with a median of 22 m, so most roads were
being resized. This is why so little asphalt appeared at first.

### 9.3 Building-derived roads (`--roads-from-buildings`)

An alternative road network built from where the buildings are, on the premise that a CS1 building
was placed against a road and therefore implies where streets run.

Method: join each building to its nearest few neighbours within 55 m, cap each building's degree at
3 so dense clusters do not become a spiderweb, and bow each connection slightly so consecutive
streets are not ruler-straight.

**Measured comparison:**

| Strategy | Roads | Asphalt cells | Coverage |
|---|---|---|---|
| CS1 road graph (default) | 173 | 208,847 | 0.311% |
| Derived from buildings | 1,695 | 44,804 | 0.067% |

**Two bugs were found while building it, both by measurement rather than inspection:**

1. **Coordinate space applied twice.** `Vec3` stores CS1 coordinates and `Vec3.beamng()` converts
   them. The generator called `.beamng()` on each building *and* stored the result in a `Vec3`, so
   the conversion ran twice. Every derived road landed on `y = 0`, collapsing the whole network onto
   a single line. The giveaway was 1,695 roads painting only 3,426 cells -- a number far too small
   for the geometry claimed, and identical between two very different road counts.

2. **Painted geometry did not match emitted geometry.** The layer map was painted inside
   `build_terrain`, from the CS1 road list, which runs *before* the road strategy is chosen. With
   `--roads-from-buildings` the terrain was therefore painted with CS1 roads while 1,695 different
   decals were drawn on top. Both builds reported exactly 195,967 asphalt cells despite having 173
   and 1,695 roads. Painting now happens in `emit_roads`, from the same chain list that produces the
   decals, and `build()` orders roads ahead of the `.ter` write.

**Honest assessment of the derived network:** it is 2.7x the length of the CS1 network but covers
only a fifth as much ground, because it links building pairs rather than tracing streets. Building
positions record where roads *are*, not how they *connect*, so this is a proximity graph and not a
topology. It is offered as a switch, not as the default.

---

---

## 10. The two defects the second log finally named

Both had been invisible to every static check, because both are things that only the engine decides.

### 10.1 `baseTexSize` is a REQUIRED size, and every texture must match it

```
E|TerrainCellMaterial| Terrain material [Grass] using texture
[/assets/materials/terrain/grass/t_grass_02/t_grass_02_b.png]
dont have required size of 2048-2048 declared in TerrainMaterialTextureSet
named [CannesTerrainMaterialTextureSet]
```

`TerrainMaterialTextureSet.baseTexSize` is not a hint or a maximum. It is the size every texture in
the base family **must** be. A texture that does not match is discarded, and the cache packs a
**black** layer -- which is exactly the permanent black ground, and why it looked like a lighting or
colour problem rather than a size problem.

The value 2048 was inherited from where the material came from. It began as a copy of
east_coast_usa's terrain material, and east_coast_usa's own `t_terrain_base_*` family genuinely is
2048x2048. But every texture used here comes from `content/assets/materials/terrain.zip`, and
measuring all 213 PNGs in that archive shows:

| Size | Complete 5-texture sets |
|---|---|
| 1024x1024 | **38** |
| anything larger | **0** |

So 1024 is the only correct value for this map. It is now set to 1024, and every one of the fifteen
base textures is verified to actually be 1024x1024 against the install.

**The check that was missing:** verifying a path resolves is not enough; the size has to match the
declared size too. That check is now in the conformance report.

### 10.2 `mapTo` is not inheritance, and the engine's glass materials are unusable

Two separate findings, both measured.

**`mapTo` names a mesh slot, not a parent.** Scanning 6,359 materials across the entire install
finds **zero** uses of a `parent` field. So

```json
{"Italy_bld_ind_windows": {"name": "Italy_bld_ind_windows", "mapTo": "m_windows_glass_01"}}
```

inherits nothing. The engine confirmed it registered the entry and then still could not resolve the
building shape:

```
W|engine::MaterialManager::mapMaterial| Warning, duplicate material. Overwriting.
   Old: /art/shapes/objects/m_windows_glass_01/... / Italy_bld_ind_windows / mapTo = m_windows_glass_01
   vs new: /levels/cannes/art/terrains/main.materials.json / Italy_bld_ind_windows / mapTo = m_windows_glass_01

E|MaterialList.mapMaterials| [NO-MATERIAL] Unable to find material mapping to:
   Italy_bld_ind_windows in unknown
```

An entry with no stages renders nothing, so the windows stayed untextured no matter where the file
was placed. Two earlier rounds were spent moving that file between paths -- the placement was never
the problem.

**The engine's own glass materials cannot be used either.** Every candidate references textures that
do not exist in this install:

| Material | Texture references | Missing |
|---|---|---|
| `m_windows_glass_01` | 2 | **2** |
| `m_transparent_glass_window` | 4 | **4** |
| `windows_doors_reflective` | 4 `.link` stubs -> real `.dds` | 0 |

`windows_doors_reflective` is the usable one. Its textures ship as `.dds` in `atlas.zip`, with
`.link` stubs in `art_shapes.zip` pointing at the same images under a `.png` name:

```json
{"path": "/assets/materials/atlas/windows_doors_reflective/t_windows_doors_reflective_b.color.png",
 "type": "normal"}
```

Note the stub targets a `.png` that **also** does not exist as such -- the real entry is the `.dds`.
So the material is modelled on `windows_doors_reflective` and references those `.dds` paths
directly. Nothing is copied into the mod and no texture is authored: two material definitions the
building shapes ask for by name.

Also logged, for the record: 18 further building materials are unresolved
(`street_concrete1`, `tiles_marble_square`, `groundmesh_grass2`, `corrugation`, `highrise`,
`concrete_precast1`, `canal`, `brick_plain`, `stone_joins`, `stone_brick_irregular`,
`weatherboards`, `grass_garden`, `m_condo_cylindrical_LOD`, ...). These are the same class of defect
-- declared inside another level's archive -- and each needs the same treatment.

---

---

## 11. The whitish wash, texture scale, terrain smoothness, and a hidden `_smooth` bug

### 11.1 The whitish filter was the template level's fog

The lighting block is copied from `levels/template`, which ships a much foggier and more tinted
atmosphere than any working map:

| | `fogColor` | `fogDensity` | `visibleDistance` |
|---|---|---|---|
| `levels/template` | `[0.741, 0.816, 0.925]` | **6.0e-4** | 4500 |
| `polish_roads_v2` | `[1, 1, 1]` | **2.8e-4** | 9000 |

The template's density is more than **twelve times** the working value and its colour is a strong
pale blue-grey. Together they wash the entire scene toward white/blue, which reads as a filter over
everything rather than as fog.

The `LevelInfo` clone now overrides all four values to the working map's, plus `decalBias 0.001`.
Note the template ships **two** `LevelInfo` objects with the *same* `persistentId` and different fog
densities (6.0e-4 and 8.0e-4) in two different files -- another reason to override rather than trust
what is copied.

### 11.2 `_smooth` silently changed the array shape on every call

The separable box blur padded for its vertical pass and then sliced **columns** instead of rows:

```python
np.pad(horizontal, 1, mode="edge")[0:-2, :]     # cuts rows, keeps the padded width
```

`horizontal` is already h x w, so padding makes it (h+2, w+2) and `[0:-2, :]` leaves **(h, w+2)** --
two columns too wide and two rows lost. Measured directly:

```
in (2048, 2048) -> out (2048, 2052)
in (100, 100)   -> out (94, 100)
in (7, 9)       -> out (1, 9)
```

This had been there from the beginning and never surfaced, because **every** caller passed the
result through `_as_square`, which crops silently. The only visible symptom was a slight edge
smear. It became a hard error only when the new coarse smoothing blended two grids and
`(2048, 2054)` could not be added to `(2048, 2048)`.

Both passes are now written explicitly with the padded axis named, and the output shape is asserted
against the input for several sizes including degenerate ones.

### 11.3 Terrain smoothness

Steep facets come from `_fill_gaps` interpolating across the sparse gaps between road samples.
`_smooth` is a 3x3 kernel, so three iterations reach about three cells -- roughly 12 m here -- which
removes local noise and does nothing about the long ramps.

Smoothing now runs at two scales: the existing fine pass, plus a coarse pass that downsamples by 4
(so each step covers 16x the ground), smooths, and upsamples back. The coarse result is blended at
0.65 so real elevation differences survive rather than being flattened to a plane.

**Measured:** mean neighbour step **2.63**, median **0**, p99 **15** (u16 units over `maxHeight`).
The maximum is 17,526 -- one isolated cliff, 0.0002% of cells. Worth investigating separately; it is
not representative.

### 11.4 Texture scale

The sets are 1024x1024, so tile size in metres sets the texel size directly:

| | before | now | texel |
|---|---|---|---|
| base | 8 m | **2 m** | 1.95 mm |
| macro | 2 m | **0.5 m** | 0.49 mm |
| detail | 0.5 m | **0.25 m** | 0.24 mm |

---

---

## 12. THE JUNCTION BUG -- roads never actually met

This is the real cause of "the roads are not connected", and it had been present from the first
version. Three separate earlier hypotheses were wrong before this was measured.

### 12.1 What the source data says

Nodes shared by two roads agree to **0.000 m**:

| Test | Result |
|---|---|
| Roads | 2,307 |
| Distinct node ids | 2,257 |
| Shared nodes whose endpoints disagree by >1 m | **0** |
| Maximum disagreement at a shared node | **0.000 m** |

So the topology is exact. Whatever the discontinuity was, it was introduced by the converter.

### 12.2 What the emitted level said

Measured on the built archive, before the fix:

| Test | Result |
|---|---|
| Junction nodes (>=3 roads) | 111 |
| Junction nodes with a chain endpoint on them | **0 / 111** |
| Chain endpoints within 1 m of a junction | **0 / 346** |
| Closest endpoint to its junction | 2.00 m |
| Median endpoint-to-junction distance | 10.00 m |
| Endpoints within 5 m of another chain's centre-line | **0 / 346** |

100% of junctions were unjoined. Not a rendering artefact and not a fade setting -- the geometry
genuinely stopped short everywhere.

### 12.3 The cause

`Road.surface_polyline` averaged the NODE elevation with the BEZIER elevation at the first and last
point, but kept the **Bezier's x/z**:

```python
points[0] = Vec3(first.x, (first.y + self.start_position.y) * 0.5, first.z)
#                 ^^^^^^^ Bezier x                                  ^^^^^^^ Bezier z
```

Its own docstring had the answer all along:

> on 259 segments (mostly Basic Road) its endpoints are pulled along the segment to handle junction
> corners

CS1 pulls Bezier endpoints *inward* at junction corners. The elevation average was added to cancel a
different, unrelated bias (+1.000 m on 1040 segments, -0.300 m on 326) and the x/z were left from the
Bezier -- so every road stopped exactly where CS1 pulled it in. The mean shortfall was 10 m, which is
precisely a junction corner radius.

### 12.4 The fix, and its result

The first and last point now take the **node's x/z**, with the elevation still averaged:

| Test | Before | After |
|---|---|---|
| Junction nodes with a chain endpoint on them | 0 / 111 | **111 / 111** |
| Endpoints sitting exactly on a junction | 0 / 346 | **286 / 346** |
| Endpoints within 0.01 m of another chain | 0 / 346 | **286 / 346** |
| Endpoints landing within the other chain's half-width | 1 / 346 | **287 / 346** |

The remaining 60 endpoints are genuine dead ends at the map edge, not failures.

### 12.5 A wrong fix that had to be reverted

Before finding this, an extension was added that pushed each chain end outward along its own
direction to force overlap. Measuring it showed **zero** coincident endpoint locations: at a
junction the meeting chains approach from *different* directions, so extending both moves their
ends **apart** -- up to 24 m at a right angle. Overshooting only helps two collinear segments, which
is not what a junction is. It was reverted, and the helper deleted so it cannot return.

### 12.6 The pattern, stated plainly

This is the fourth time in this session that a docstring or comment in the code contained the
information needed to find the bug, and the bug was in the line directly beneath it. The others
were the `.ter` `layerTextureMap`, the `soil/` vs `rock/` path, and the `_smooth` axis swap. Every
one was found by measuring the output rather than reasoning about the code.

---

---

## 13. The remaining road gaps: chaining was the cause

After snapping chain endpoints to their nodes (section 12), 83% of endpoints joined and 111 of 111
junctions were covered -- but visible gaps remained, and the user's description pinpointed them:
*"some roads still have a gap... not an intersection"*.

### 13.1 The clue that solved it

> "the gravel/mud texture is perfectly outline all the roads, but the road on top of it is very
> unreliable"

The gravel is the painted terrain surface; the road is the `DecalRoad` on top. Both are generated
from the **same** source list, and measurement confirms chaining consumes **1,244 / 1,244** segments
-- nothing is dropped. So the loss had to be in the *geometry*, not the topology.

### 13.2 Why chaining breaks the middle of a road

Snapping fixed a chain's two ENDS. Inside a chain, consecutive source segments meet at a node, but
each segment's interior points come from **its own Bezier**, and CS1 offsets those. So at every
internal join the polyline can kink or step -- and unlike the chain ends, nothing snaps it. The
longer the chain, the more such joins: the median chain is 176 m and the longest **26.4 km**, from 96
segments.

That matches the symptom exactly: breaks *along* roads, not only at intersections.

### 13.3 Per-segment emission, measured against chaining

| | chained | per segment |
|---|---|---|
| DecalRoads | 173 | 1,244 |
| Endpoints landing on another road | 286 / 346 (**83%**) | **2,481 / 2,488 (99.7%)** |
| Median endpoint gap | 0.0000 m | 0.0000 m |
| **p90 endpoint gap** | **33.5 m** | **0.0000 m** |
| Worst gap | 224 m | 96 m |

The **p90** is the number that matters. In chained mode a tenth of all endpoints were more than
33 m from any other road; per-segment puts a node at every join, so the whole network closes at
0.0000 m. The remaining 7 endpoints are genuine dead ends.

Per-segment is now the default; `--chain-roads` opts back in for comparison.

This also matches the reference map, which the chaining decision had contradicted all along:
polish_roads_v2 ships 6,740 DecalRoads with a **median node count of 3**, and **42.1% of them are
two-node roads**. It uses short decals, not long chained polylines. The original reasoning -- that
short decals cause gaps and chaining would fix them -- was backwards.

### 13.4 Grass colour

The washed-out ground is the texture **blend strengths**, not the texture. `baseColorDetailStrength`
and `baseColorMacroStrength` are `[far, near]` pairs governing how strongly each family mixes over
the base; both were low, so the pale base tile dominated.

| | before | now |
|---|---|---|
| `baseColorDetailStrength` | `[0.4, 0.45]` | `[0.85, 0.95]` |
| `baseColorMacroStrength` | `[0, 0.1]` | `[0.5, 0.7]` |
| base tile | 2 m | 2 m |
| macro tile | 0.5 m | 1 m |
| detail tile | 0.25 m | 0.5 m |

The tile hierarchy was also reordered: detail must be finer than macro, which must be finer than
base. A conformance rule asserts that ordering, which is how the 1.0/0.5 inversion was caught.

---

---

## 14. Hairline decal seams, grass colour, and buildings on roads

### 14.1 Hairline seams: decals that touch still show a break

With one decal per segment, consecutive decals share an endpoint **exactly** (section 13). The user
found in the editor that nudging a decal along its own axis closed the visible gap, so the problem is
that two decals which merely *touch* still show a seam -- each has its own edge, and at the join there
is a break.

Each decal's two ends are now extended along its own local direction by `ROAD_DECAL_OVERLAP`, default
**1.0 m**. That value is the tunable knob: raise it if seams persist, lower it if joins look bloated.

This is deliberately **not** the extension that failed in section 12.5. That one pushed junction ends
by up to 12 m, and made things worse because chains meeting at a junction approach from different
directions -- extending both moved their ends *apart*. This one is a metre, applied at every join, and
its purpose is to make touching decals overlap rather than to bridge an angle.

### 14.2 Grass colour: the blend strengths, then the texture

The washed-out ground had two causes.

**Blend strengths.** `baseColorDetailStrength` and `baseColorMacroStrength` are `[far, near]` weights
for how strongly each family mixes over the base tile. Both were low, so the pale base dominated:

| | before | now |
|---|---|---|
| `baseColorDetailStrength` | `[0.4, 0.45]` | `[0.85, 0.95]` |
| `baseColorMacroStrength` | `[0, 0.1]` | `[0.5, 0.7]` |

**Texture choice.** The detail family carries most of the close-range colour, and it was set to
`ind_grass`, which measures a flat neutral grey (mean RGB **127, 127, 127**). It is now
`t_dirt_vegetation`, which is more saturated. Measured means from `terrain.zip`:

| set | mean RGB |
|---|---|
| `ind_grass` | 127, 127, 127 (neutral) |
| `t_grass_01` | 124, 124, 124 |
| `t_grass_02` | 111, 113, 107 |
| `t_macro_grass` | 110, 110, 110 |
| `t_dirt_vegetation` | *used for detail* |

Tile hierarchy was also corrected to detail < macro < base (0.5 / 1.0 / 2.0 m); an inversion was
caught by the conformance rule.

### 14.3 Buildings on roads

Placement sampled only the terrain under the footprint, so nothing considered the roads at all.
Measured on the built level: **56 of 1,463** buildings had a footprint overlapping a road, the worst
by 10.0 m.

The first fix -- capping the scale by distance to the road -- changed almost nothing, and tracing one
case showed why:

```
b_806   prefab "Road Connection"
nearest centre-line point = (8648.80, 343.43)   half-width 14.00   raw distance 0.00
best_edge = -14.0000        direction length = 0.0000
```

CS1 places "Road Connection" and "Water Pipe Junction" prefabs with their centre **exactly on a road
centre-line**. Scaling cannot fix that -- a footprint cannot be shrunk out of a corridor it is
centred in, and at -14 m the required scale is negative. So there is no direction "away" to use
either.

Three successive corrections were needed, each found by measuring the built output:

1. **Normal fallback.** When the centre is exactly on the centre-line, "away" is undefined; the
   segment normal is used, and whichever side ends up clearer wins (the other may be another
   carriageway).
2. **One uniform rule.** The shrink and push paths had been comparing different quantities. Now a
   single value decides: `effective = centre_edge - half_diagonal - clearance`. Negative means act:
   shrink if the centre is clear, push if it is not.
3. **Iteration, then a measured recheck.** A single push moved the right *distance* (7.969 m) in a
   direction that left the footprint 4.17 m inside the road it was moving away from, so the push
   repeats until it stops improving. A final recheck then measures the landed clearance and shrinks
   by any remaining shortfall -- necessary because the model's half-diagonal is not the CS1
   footprint the scale came from.

Result: **56 -> 0** overlapping, tightest clearance **+1.25 m** (`BUILDING_ROAD_CLEARANCE`).

The check itself also had to be strengthened. A rotated-corner test **under-reports** when the
model's own axes differ from the TSStatic rotation -- one building passed a corner test while still
4.17 m inside a road. The conformance report now tests a **bounding circle**, which is conservative
whatever the rotation, and that is the measure reported above.

---

---

## 15. Terrain colour is a local texture, and the mesh-origin offset that had to be reverted

### 15.1 Every engine terrain texture is neutral grey

Measured means from `content/assets/materials/terrain.zip`:

| texture | mean RGB |
|---|---|
| `grass/t_grass_02/t_grass_02_b.png` | 112, 113, 107 |
| `grass/t_grass_01/t_grass_01_b.png` | 123, 123, 124 |
| `grass/ind_grass/t_ind_grass_b.png` | 127, 127, 127 |
| `grass/groundmesh_grass2/groundmesh_grass_b.color.dds` | 138, 138, 138 |
| `backdrop/island_terrain/island_terrain_grass_b.color.dds` | 128, 128, 128 |
| `asphalt/asphalt/t_asphalt_b.color.dds` | 137, 137, 137 |

**Not one is green.** They are detail maps that modulate a colour supplied by something else. Raising
`baseColorDetailStrength` and `baseColorMacroStrength` -- which was done in an attempt to force colour
out of them -- cannot work: blending more grey over grey produces grey.

### 15.2 Where the colour actually comes from

Every working level's Grass material points its **base** family at the level's own
`art/terrains/t_terrain_base_b.png`, a 2048 or 4096 texture shipped inside the level archive. Its
detail and macro families are the engine's grey maps, applied at **low** strength:

| level | `baseColorDetailStrength` | `baseColorMacroStrength` |
|---|---|---|
| `automation_test_track` | `[0.5, 0]` | `[0.1, 0.1]` |
| `Cliff` | `[0.32, 0]` | `[0.1, 0.2]` |
| `derby` | `[0.35, 0]` | `[0.05, 0.2]` |
| ours, before | `[0.85, 0.95]` | `[0.5, 0.7]` |
| ours, now | `[0.45, 0.0]` | `[0.15, 0.2]` |

The values used earlier were roughly **twice** the working range, and in the second slot 5-10x, in the
wrong direction. They are now in the working range.

There is **no `baseColorFactor` on `TerrainMaterial`** -- the field appears on none of the 191 terrain
materials across the install -- so a material cannot tint the ground either.

**Consequence, stated plainly:** genuinely green ground requires a coloured base texture, which is
something only the level can provide. That is the fix if the colour is still not acceptable; the
strengths can only modulate what the texture already contains.

### 15.3 The mesh-origin offset: measured, applied, and reverted

Every building shape's Collada bounding-box centre is far from its origin:

```
ind_bld_8x8    centre (-4.00, 0.83)      ind_bld_12x30  centre (-15.00, 1.84)
ind_bld_24x60  centre ( 0.00, 5.57)      city_block3    centre (-322.53, 129.05)
```

So the drawn mesh sits half a width to one side of the placement point, which is a strong candidate
explanation for buildings appearing where their collisions are not. It was baked in and applied four
ways, and **every variant made road overlap worse than applying nothing**:

| transform | buildings overlapping a road | total penetration |
|---|---|---|
| **none** | **124** | **642.9 m** |
| minus, rotate +yaw | 161 | 936.5 m |
| add, rotate -yaw | 181 | 948.3 m |
| add, rotate +yaw | 230 | 1032.2 m |
| raw add | 417 | 2194.3 m |

The raw vertex bounds evidently do not describe the placed mesh -- `city_block3` measures **6.3x** its
table size, which shows node transforms or a non-standard axis convention are in play, and no node
`<translate>` exists to account for it. Applying a half-understood offset moved buildings *onto* roads
rather than off them, so it was removed and the code records why.

`BEAMNG_SHAPE_CENTRE_OFFSET` is retained with the measurements and the table above, so the data is not
lost if the axis question is ever resolved.

### 15.4 Correct building placement measurement

The earlier "zero overlap" result was wrong because the rotation used in the test was inconsistent --
it applied `atan2(rm[3], rm[0])` to mixed row/column entries. Testing the real rotated rectangle with
`x' = x cos - y sin`, `y' = x sin + y cos` against the emitted `DecalRoad` corridors gives:

```
buildings sampled      1463
OVERLAPPING roads         0
tightest clearance    -0.555 m (bounding circle) / 0 overlapping (rotated rectangle)
```

The conformance screen is a bounding **circle**, which is conservative by construction and can report
contact where the rectangle clears; its tolerance says so explicitly rather than hiding it.

### 15.5 Decal overlap raised

`ROAD_DECAL_OVERLAP` 1.0 -> **1.75 m**, on the report that the seam had "almost disappeared, just
needs a bit more offset".

---

---

## 16. The green texture, found by scanning everything

Sections 15.1-15.2 concluded that no engine terrain texture is green. That was **too narrow**: the
scan had only looked at `terrain.zip`. Scanning every texture archive in the install for a green bias
(`G - (R+B)/2`) found exactly **four** green-ish textures in the whole game:

| texture | mean RGB | green bias |
|---|---|---|
| `terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png` | 121, 124, 97 | **+15.0** |
| `terrain/forest/t_forest_ground_02/t_forest_ground_03_b.png` | 113, 111, 95 | +7.0 |
| `terrain/asphalt/m_asphalt/t_terrain_base_asphalt_b.png` | 118, 115, 102 | +5.0 |
| `terrain/grass/t_macro_dry_grass/t_macro_dry_grass_02_b.png` | 117, 115, 103 | +5.0 |

Archives scanned: `terrain`, `foliage`, `tree`, `tileable`, `atlas`, `baked_props`, `trim`, `rocks`.
Only four entries exceeded a bias of 4, and `t_forest_ground_02` is the only strong one. The forest
sets -- not the grass sets -- are where the game's green actually lives.

**A second defect found while doing this:** base and detail were pointing at the *same file*, so one
texture was applied twice and the third family contributed nothing distinct. All three families are
now different textures:

```
base    forest/t_forest_ground_02/t_forest_ground_02_*    (green, RGB 121,124,97)
detail  grass/t_grass_02/t_grass_02_*                     (fine detail)
macro   forest/t_macro_forest/t_macro_forest_*            (large-scale mixing)
```

## 17. Floating towers: the west_coast shapes are unusable

The `west_coast_usa` building shapes have mesh origins hundreds of metres from their geometry:

```
city_west2.dae        centre (-844.71,  89.96)
city_block3.dae       centre (-322.53, 129.05)
condo_cylindrical.dae centre (-305.28, 115.46)
```

Placing one at a CS1 position therefore puts the visible mesh a long way from the placement point --
floating high above the map, exactly as observed. `city_block3` additionally measures **6.3x** the
size its table entry claims, confirming its geometry carries node transforms this measurement cannot
resolve.

They are **removed from the model set**. Buildings now use only the seven Italy industrial shapes,
whose origins sit within a few metres of their geometry. Of the 1,463 buildings:

```
ind_bld_12x30   1003      ind_bld_12x24     47
ind_bld_12x15    198      ind_bld_8x8       90
ind_bld_24x60    125
```

## 18. Building/road clearance

`BUILDING_ROAD_CLEARANCE` raised 1.25 -> **2.5 m**. Measured against the emitted road corridors with
the corrected rotation:

```
buildings sampled    1463
OVERLAPPING roads       0
tightest clearance  -1.648 m (bounding circle) / 0 overlapping (rotated rectangle)
```

The two closest buildings are held at the clearance limit; `b_17000` and `b_41773` are shrunk by the
rule rather than nudged, which is the intended behaviour when a footprint cannot be moved far enough
without relocating it arbitrarily.

**One caveat worth recording:** the shapes are multi-mesh and include trim, awnings and rooftop
details that extend past the main mass (`ind_bld_12x30`'s meshes range from 30.0 to 30.22 m). The
footprint test uses the shape's declared size, so a protrusion beyond it is not accounted for. The
measured clearance is therefore a lower bound on the true gap, not an exact figure.

---

---

## 19. Red grass: the mean of a texture does not describe its appearance

Three rounds of grass "fixes" went wrong for one reason: the choice was made by **averaging** texture
pixels, which cannot distinguish a green texture from a red one that happens to have a similar mean.

Rendering the three textures the material actually used made the cause immediate:

| family | texture | what it actually is |
|---|---|---|
| BASE | `forest/t_forest_ground_02` | green -- yellow-green grass with pale stone flecks |
| DETAIL | `grass/t_grass_02` | green/olive, fine |
| MACRO | `forest/t_macro_forest` | **RED / brown** |

`t_macro_forest` averages `(110, 110, 110)` -- which the mean-based scan read as neutral -- but its
pixels are red-brown. Worse, it was tiled at **1 metre**, so it repeated 1024 times and dominated
everything under the camera. That is precisely the reported symptom: red from above, dark mud close
up. The green base was buried underneath.

The contact sheets are written to `build/texture_sheet.png` and `build/current_stack.png`; the
generator is `tools/dump/make_texture_sheet.py`. **Look at a texture before choosing it.**

## 20. The reference grass structure, and why the tile sizes were backwards

polish_roads_v2's `Grass`, field for field:

```
baseColorBaseTex          local t_terrain_base_b      size 2048
baseColorDetailTex        t_grass_01_b                size 3
baseColorMacroTex         t_macro_grass_b             size 80
baseColorDetailStrength   [0.4, 0.45]
baseColorMacroStrength    [0, 0.1]
detailDistances           [0, 0, 50, 80]
macroDistances            [0, 0, 400, 8000]
detailSize 4   macroSize 50   detailDistance 25   macroDistance 1000
detailDistAtten [0, 1]   macroDistAtten [0.35, 1]
```

The shape of it:

* the **base** carries the colour and is **large** -- 2048 m in the reference -- stretched so that no
  repeat is visible. It is the stand-in for a level's own colour texture.
* the **detail** is **small** (3 m) and subtle, adding fine variation near the camera.
* the **macro** is **large** (80 m) and very subtle, adding large-scale variation.

Everything here had been set to 0.5-4 m for all three families, which is the opposite: it made every
layer repeat visibly, and it let the red macro dominate.

Current values, which follow the reference's shape scaled for a 32 km world:

| family | texture | tile | role |
|---|---|---|---|
| base | `forest/t_forest_ground_02` | **200 m** | the colour -- green |
| detail | `grass/t_grass_01` | **4 m** | fine variation |
| macro | `grass/macro_grass` | **60 m** | large-scale variation |

The engine ships no green *terrain* texture other than the forest ground sets -- a scan of every
material archive found only four textures with any green bias, and `t_forest_ground_02` at
`(121, 124, 97)` is the only strong one. A level supplies its own colour texture for this slot; a
converter cannot, so the greenest built-in texture is used with the tile sizes set so its small red
flecks read as ground detail rather than as the ground colour.

Three conformance rules now encode the reference's shape rather than the earlier wrong assumption:
the base must be >= 64 m, the detail 1-12 m, the macro >= 32 m, and base and detail must not be the
same file (an identical pair applies one map twice, which was a real defect here).

---

---

## 21. Dark, bluish, oversaturated ground: it was the tile scale, not the strengths

The ground came out dark, blue-cast and magenta-flecked instead of green. The cause was the base
tile at **200 m**, and it acted through two mechanisms at once:

1. **Pixelation.** A 1024 px texture over 200 m puts ~20 cm of ground on each texel. The grass blades
   in `t_forest_ground_02`, drawn at centimetre scale, were magnified into large smears, and its tiny
   pink and magenta flecks became visible blotches.

2. **Magnified normals.** The base normal map is sampled with the same tile as the base colour, so a
   200x stretch magnifies every bump by 200x. The shading was then dominated by normal detail at a
   scale no eye reads as grass, which is what produced the dark, blue, over-processed look.

**The strengths were not the problem.** `normalDetailStrength [1, 0.3]` and
`normalMacroStrength [0.5, 0.5]` are polish_roads_v2's own Grass values. The mistake was scale.

### Why the reference can stretch its base and this level cannot

polish_roads_v2's Grass base tile is **2048 m**, and it looks right -- because its base image is a
**satellite photograph** of the whole map. A photograph has no usable close-range normal detail, so
magnifying it costs nothing. `t_forest_ground_02` is a close-up grass texture whose normal map is
full of structure; stretching it 200x is what broke the shading. **The reference's base *scale* is not
transferable, because the reference's base *asset* is a different kind of image.**

Its detail scale *is* transferable -- 3 m -- and is now used verbatim.

### Final values

| family | texture | tile | role |
|---|---|---|---|
| base | `forest/t_forest_ground_02` | **16 m** | colour |
| detail | `grass/t_grass_01` | **3 m** | fine variation (the reference's own figure) |
| macro | `grass/macro_grass` | **40 m** | large-scale variation |

`detailDistances [0, 0, 20, 40]` and `macroDistances [0, 0, 60, 300]` were also pulled in, so the
base hands over to the finer families sooner.

### The conformance rules were wrong too, and are corrected

They asserted `base >= 64 m` and `macro >= 32 m`, both taken from the reference's satellite-photo
base. That encoded the wrong model of what the base layer is. The rules now express what actually
matters:

* the base tiles between **8 and 64 m** -- legible, neither pixelated nor stretched;
* the detail between **0.5 and 12 m**;
* the macro coarser than the detail;
* base and detail are **different files** (an identical pair applies one map twice, which was a real
  defect found here).

A rule is only as good as the model behind it. This one had been carrying the satellite-photo
assumption since it was written.

---

---

## 22. Green ground, at last: the level ships its own colour texture

Every previous attempt failed for a structural reason, not a tuning one. A level's terrain **base**
layer is meant to be a large colour texture that the level itself ships -- polish_roads_v2's is a
2048 m satellite photograph of its own map. The engine's own terrain textures measure near-neutral
grey; the greenest found anywhere in the install has a green bias of only **+15**, and no material
field can tint a terrain material (there is no `baseColorFactor` on `TerrainMaterial` -- it appears on
none of the 191 across the install).

So the ground could not be made green from built-in content at all. It needed an image.

### The supplied texture

`textures/grass.jpg`, 893x894 JPEG. Measured **mean RGB (89, 99, 45), green bias +31.7** -- twice as
green as anything the engine ships, and it is real grass rather than gravel speckled with green.

The converter now writes it into the level as
`levels/<level>/art/terrains/t_grass_ground_b.png`:

* converted to PNG, the format every terrain texture reference here uses;
* centre-cropped to a square so it does not stretch, then resized to **1024x1024** and saved as PNG.
  The power of two matters: `baseTexSize` declares a *required* size and the engine discards anything
  that does not match, packing the layer black -- a rule that already cost several rounds.

### Only the colour slot changed

| slot | source |
|---|---|
| **base colour** | **the supplied `grass.jpg`** |
| base normal / roughness / ao / height | engine `forest/t_forest_ground_02` |
| detail | engine `grass/t_grass_01`, 3 m |
| macro | engine `grass/macro_grass`, 40 m |

The engine maps stay on the non-colour slots deliberately: normal, roughness, ao and height are detail
maps that modulate whatever colour is underneath, which is exactly how the engine's own materials are
built. Keeping them means the ground still has proper relief and lighting response rather than being
a flat photograph.

Base tile is **32 m** -- 1024 px over 32 m is about 3 cm per texel, fine enough not to pixelate and
coarse enough not to repeat visibly across a 32 km world.

`convert_custom_terrain_texture` returns None rather than raising when the source is missing, so a
level still builds without it and the reference material is used instead.

### Rules that changed

Three rules had been written when the goal was strictly engine-only content, and they failed against
the supplied texture. Rather than loosening them into meaning nothing, each now states the real
requirement:

| rule | before | now |
|---|---|---|
| texture source split | "all 15 from the engine library" | exactly **one shipped** (the ground colour), **14 engine** |
| copied textures | "no texture is copied into the mod" | no texture shipped *other than* the ground colour |
| install resolution | "every base texture resolves in the install" | every **engine** base texture resolves; the shipped one is checked against the mod |

Plus three new rules for the shipped texture: that it is present, that its size **matches the declared
`baseTexSize`**, and that it is **genuinely green** (bias > +15), since being green is the entire
reason it exists.

### Still to do

Normal, roughness, ao and height maps for the supplied texture. Its current maps come from a different
image, so the relief does not correspond to the visible grass; it reads acceptably but is not correct.

---

---

## 23. Grass tiling reduced 30x, and the family ordering it broke

Base tile reduced from 32 m to **1.07 m**, a factor of 30, on request. At 1024 px that is about
**1 mm per texel**, so the texture's own pixels are far below the visible threshold and the blades
read at their intended size rather than being magnified.

The change broke a relationship that had to be fixed with it: the detail layer was tiled at 3 m --
**coarser than the 1.07 m base it exists to detail**, which is backwards. All three families were
scaled proportionally:

| family | before | now | texel |
|---|---|---|---|
| base | 32 m | **1.07 m** | 1.04 mm |
| detail | 3 m | **0.35 m** | 0.34 mm |
| macro | 40 m | **3 m** | 2.93 mm |

`detail < base < macro` now holds, which is the ordering that matters.

### A conformance rule was wrong again, for an instructive reason

The detail rule asserted an **absolute** range of 0.5-12 m, justified by "the reference's grass uses
3 m". That figure is only meaningful relative to the reference's own base, which is 2048 m -- its
detail is about **680x finer** than its base. An absolute floor becomes meaningless the moment the
base changes scale: against a 1.07 m base, a 3 m "detail" layer is simply wrong.

The rule is now **relative** -- the detail must tile finer than the base, with only a sanity floor
(0.05 m) beneath it.

This is the third rule in this project found to encode an assumption copied from the reference that
did not transfer, after the `base >= 64 m` rule and the "all 15 textures from the engine" rule.
**A value taken from a working example is only valid together with the conditions that made it work.**

---

## 8. What the rewrite must do, concretely

1. **Terrain material: use built-in materials and built-in textures.** Reference
   `/assets/materials/terrain/...` for every slot that exists there, and ship only what must be
   local. Create no new materials.
2. **Emit all three size fields** on every family: base, macro and detail.
3. **Write `TerrainBlock` with the fields this map has**, including `lightMapSize` and the
   `reflect*` block, with `baseTexSize` equal to the texture set's base size, and `squareSize`
   omitted or set to match the source geometry.
4. **`.ter` version 9 with all five sections**, length asserted.
5. **Roads**: one DecalRoad per chained centre-line, `__parent` equal to the owning folder name,
   `autoJunction` and `autoLanes` **enabled**, `distanceFade`/`decalBias`/`detail`/`renderPriority`
   taken from the values in §5.3 rather than invented.
6. **Lighting**: `LevelInfo`, `TimeOfDay`, `ScatterSky`, `CloudLayer`, `Precipitation`,
   `ForestWindEmitter` in a lighting group, copied from a working level.
7. **Buildings**: reference base-game shapes **in place** (cross-level `shapeName`), never copy
   them — a copied DAE keeps `<instance_material>` targets belonging to the source level's material
   library and renders as the "No Mesh" placeholder. Use `instanceColor` for variation instead of
   creating materials.
8. **Groups**: line-delimited files, `SimGroup` per sub-folder matching the folder name, every
   object's `__parent` naming the group that owns its folder.
