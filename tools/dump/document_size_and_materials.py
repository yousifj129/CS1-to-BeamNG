"""Document the texture-size and material-authoring findings."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
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

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 10; document is now", len(text.split("\n")), "lines")
