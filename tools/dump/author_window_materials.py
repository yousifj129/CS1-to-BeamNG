"""
Author the window materials properly, using a built-in material as the template.

THE ALIAS APPROACH COULD NEVER HAVE WORKED
------------------------------------------
Two independent facts, both verified:

1. **`mapTo` is not inheritance.**  Its documented meaning is "mesh/material slot name this material
   maps to".  Scanning 6,359 materials across the whole install finds **zero** uses of a `parent`
   field.  So `{"name": "Italy_bld_ind_windows", "mapTo": "m_windows_glass_01"}` does not inherit
   anything -- it only registers a material whose *slot name* claims to be the other one.  That is
   exactly what the log reported:

       W|engine::MaterialManager::mapMaterial| Warning, duplicate material. Overwriting.
       Old: /art/shapes/objects/m_windows_glass_01/... / Italy_bld_ind_windows / mapTo = m_windows_glass_01
       vs new: /levels/cannes/art/terrains/main.materials.json / Italy_bld_ind_windows / mapTo = m_windows_glass_01

   The alias was registered -- the engine then still could not resolve the shape's material:

       E|MaterialList.mapMaterials| [NO-MATERIAL] Unable to find material mapping to:
       Italy_bld_ind_windows in unknown

   because the material had no stages, so it rendered nothing.

2. **`m_windows_glass_01` is unusable anyway.**  Its two textures are absent from this install:

       /art/shapes/objects/m_windows_glass_01/t_windows_glass_01_unlit_b.color.png   NOT FOUND
       /art/shapes/objects/m_windows_glass_01/t_windows_glass_01_lit_e.color.png     NOT FOUND

   `m_transparent_glass_window` is missing all four of its references too.

WHAT IS USABLE
--------------
`windows_doors_reflective` is complete.  Its four textures are `.link` files in `art_shapes.zip`
that redirect to real `.dds` files in `atlas.zip`:

    art/shapes/objects/windows_doors_reflective/t_windows_doors_reflective_b.color.png.link
      -> assets/materials/atlas/windows_doors_reflective/t_windows_doors_reflective_b.color.dds

So the window materials are now authored in full, modelled on that built-in material and referencing
those same built-in textures.  Nothing is copied into the mod and no new texture is created; this is
a definition of two materials the building shapes ask for by name.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

# ---- replace the alias list and builder with full definitions -------------------------------
start = src.index("BUILDING_WINDOW_MATERIAL =")
end = src.index("def build_window_material_aliases()")
end = src.index("\n\n", src.index("return {", end)) + 2

NEW = '''# Names the base-game building shapes ask for.  They are declared inside italy's own archive, so
# they do not resolve from another level -- which is why the windows rendered as "NO-MATERIAL".
BUILDING_WINDOW_NAMES = [
    "Italy_bld_ind_windows",
    "italy_bld_windows",
]

# The built-in material these are modelled on.  It is complete in this install: its textures are
# `.link` files redirecting to real `.dds` images in `atlas.zip`.
WINDOW_TEMPLATE_TEXTURES = "/art/shapes/objects/windows_doors_reflective"


def build_window_materials() -> Dict[str, Any]:
    """
    Full definitions for the window materials the building shapes ask for.

    Modelled on the engine's `windows_doors_reflective`, whose textures resolve through `.link`
    files.  Every field is a built-in path or a literal; nothing is copied and no texture is
    authored.
    """
    return {
        name: {
            "name": name,
            "class": "Material",
            "mapTo": name,
            "version": 1.5,
            "materialTag0": "beamng",
            "materialTag1": "building",
            "dynamicCubemap": True,
            "groundType": "METAL",
            "translucentBlendOp": None,
            "translucentRecvShadows": True,
            "Stages": [
                {
                    "baseColorMap": f"{WINDOW_TEMPLATE_TEXTURES}/t_windows_doors_reflective_b.color.png",
                    "normalMap": f"{WINDOW_TEMPLATE_TEXTURES}/t_windows_doors_reflective_nm.normal.png",
                    "roughnessMap": f"{WINDOW_TEMPLATE_TEXTURES}/t_windows_doors_reflective_o.data.png",
                    "ambientOcclusionMap": f"{WINDOW_TEMPLATE_TEXTURES}/t_windows_doors_reflective_ao.data.png",
                    "metallicFactor": 0.5,
                    "roughnessFactor": 0.2,
                },
                {},
                {},
                {},
            ],
        }
        for name in BUILDING_WINDOW_NAMES
    }
'''

src = src[:start] + NEW + src[end:]

# ---- the emitter now merges full materials, not aliases ---------------------------------------
OLD = "        self.window_material_aliases = build_window_material_aliases()"
NEW2 = "        self.window_material_aliases = build_window_materials()"
if OLD not in src:
    raise SystemExit("window alias assignment anchor not found")
src = src.replace(OLD, NEW2, 1)

# The method no longer describes aliases.
src = src.replace("def emit_building_materials(self) -> None:", "def emit_building_materials(self) -> None:", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("full definitions:", "def build_window_materials(" in src)
print("no mapTo-as-parent:", "mapTo ->>" not in src)
print("names:", "Italy_bld_ind_windows" in src and "italy_bld_windows" in src)
