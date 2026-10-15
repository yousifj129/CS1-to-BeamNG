"""
Derive TerrainMaterialTextureSet sizes from the material itself.

The engine packs each texture group into a texture ARRAY whose dimensions come from the
TerrainMaterialTextureSet.  If the set disagrees with the material's own `*TexSize` values, the
pack fails and every slot reports

    E|TerrainCellMaterial| Missing Terrain texture: /

which is exactly the grey ground we have been seeing.  The working level used as the source has
these equal:

    material  baseColorBaseTexSize = 2048   macro TexSize = 40   detail = 1024
    set       baseTexSize [2048,2048]       macroTexSize [40,40]  detailTexSize [1024,1024]

Earlier revisions imposed a hard-coded 1024 set on top of a material that asked for 2048/40,
which is why nothing packed.  The set is now taken from the material's own values, so the two
can never disagree.

macros may legitimately be set to auto in a texture set
----------------------------------------------------------------------------------------
BeamNG accepts the string "auto" for these sizes, which lets the engine derive them.  If an
explicit size still fails to pack, switching these to "auto" is the next thing to try.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD = '''        texture_set = dict(CS1_TERRAIN_TEXTURE_SET or {})
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()
'''
NEW = '''        # The texture set sizes MUST equal the material's own *TexSize values, or the texture
        # arrays cannot be packed and every slot reports "Missing Terrain texture: /".  Deriving
        # them here means the two can never disagree.
        def _size(field: str, fallback: int) -> int:
            value = definition.get(field)
            return int(value) if isinstance(value, (int, float)) and value > 0 else fallback

        base_size = _size("baseColorBaseTexSize", 1024)
        macro_size = _size("baseColorMacroTexSize", 64)
        detail_size = _size("baseColorDetailTexSize", base_size)

        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [base_size, base_size],
            "macroTexSize": [macro_size, macro_size],
            "detailTexSize": [detail_size, detail_size],
        }
        self.report["terrainMaterial"] = {
            "internalName": definition.get("internalName"),
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "baseTexSize": base_size,
            "macroTexSize": macro_size,
            "detailTexSize": detail_size,
        }
'''

if OLD not in src:
    raise SystemExit("texture set anchor not found")
src = src.replace(OLD, NEW, 1)

# The material's own `name` field collides with the level name conventions; drop it so the
# material is identified by internalName alone (as `internalName` is what the .ter references).
src = src.replace(
    '''        definition["internalName"] = self.terrain_materials[0]
        definition["persistentId"] = new_id()''',
    '''        definition["internalName"] = self.terrain_materials[0]
        definition["name"] = self.terrain_materials[0]
        definition["persistentId"] = new_id()''',
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("derived texture set :", "base_size = _size(" in src)
print("material name set   :", 'definition["name"] = self.terrain_materials[0]' in src)
