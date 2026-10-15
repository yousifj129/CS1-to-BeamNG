"""Record the grass-material and physics findings in the reference document."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
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

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 7g; document is now", len(text.split("\n")), "lines")
