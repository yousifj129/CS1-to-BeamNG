"""
Repair the region of tools/beamng_convert.py where two splices interleaved the sky method and
the terrain-material method.

Current (broken) layout, 1-based:
    ...1610  def emit_sky_and_sun
       1611-1736   new template-based sky body (list of 4 objects, write, self.sky_objects=objects)
       1738-1829   v1.5 emit_terrain_materials body, WRONGLY nested inside the sky method
       1831-1949   the OLD sky body resuming (docstring + hand-written objects + write)
    ...1951  def build

Target layout:
    ...1610  def emit_sky_and_sun
       1611-1736   template sky body          (kept)
    ...1738  def emit_terrain_materials
       1739-1829   v1.5 material body         (moved up, re-indented as a method)
       1831-1949   OLD sky body               (dropped)
    ...1951  def build

The v1.5 body is currently indented as a method, so it can be lifted verbatim; it simply needs
its `def`/docstring header again.
"""

import io

PATH = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\beamng_convert.py"

lines = io.open(PATH, encoding="utf-8").read().split("\n")


def find(predicate, start=0, end=None):
    for i in range(start, end if end is not None else len(lines)):
        if predicate(lines[i]):
            return i
    raise SystemExit("anchor not found")


sky_def = find(lambda l: l.strip().startswith("def emit_sky_and_sun(self)"))
sky_write = find(lambda l: l.strip() == "self.sky_objects = objects", sky_def)

v15_doc = find(lambda l: "A v1.5 (PBR) terrain material" in l, sky_write)
v15_def = v15_doc - 2  # the def line, then the docstring open quote
assert lines[v15_def].strip().startswith("def emit_terrain_materials"), lines[v15_def]

v15_end = find(
    lambda l: l.strip() == 'self.write_json(os.path.join(target, "main.materials.json"), definitions)',
    v15_def,
)

old_doc = find(lambda l: "Lighting.  Without this the level loads pitch black" in l, v15_end)
old_start = old_doc
old_end = find(lambda l: l.strip() == "self.sky_objects = objects", old_doc)

build_def = find(lambda l: l.strip().startswith("def build(self)"), old_end)

print(f"sky def            : {sky_def + 1}")
print(f"sky body ends      : {sky_write + 1}")
print(f"v1.5 def (nested)  : {v15_def + 1} .. {v15_end + 1}")
print(f"stale sky body     : {old_start + 1} .. {old_end + 1}   (dropped)")
print(f"def build          : {build_def + 1}")

# 1. Keep the header and the template sky body exactly as they are.
head = lines[: sky_write + 1]

# 2. Re-create emit_terrain_materials from the nested v1.5 body.
material_block = [
    "",
    "    def emit_terrain_materials(self) -> None:",
    '        """',
    "        A v1.5 (PBR) terrain material built from BeamNG's shared `levels/template` textures.",
    "",
    "        BeamNG has TWO terrain material generations, and which one applies is decided",
    "        entirely by the TerrainBlock:",
    "",
    "          * v1 classic -- no `materialTextureSet`, materials use `diffuseMap`/`normalMap`.",
    "          * v1.5 PBR   -- TerrainBlock references a TerrainMaterialTextureSet and materials",
    "                          use `baseColor*Tex`/`normal*Tex`/`roughness*Tex`/`ao*Tex`/",
    "                          `height*Tex` at base, macro and detail scales.",
    "",
    "        Every modern shipped level uses v1.5, so a classic material is unresolvable and the",
    "        engine falls back to WARNING_MATERIAL, which renders as the 'no material' placeholder.",
    "",
    "        Textures point at `/levels/template/art/terrains/...`, which ships with the game and",
    "        is what working third-party maps reference.  Names and size/strength conventions were",
    "        taken from a real template material, substituting the grass texture family.",
    '        """',
    "        if self.terrain is None:",
    "            return",
    "",
    '        base = "/levels/template/art/terrains"',
    "        material_name = self.terrain_materials[0]",
    "",
    "        # The *TexSize values are the world metres one tile covers, matching the template's",
    "        # own conventions.  Texture PIXEL sizes must match templateTerrainMaterialTextureSet,",
    "        # which declares base [512,512] and macro/detail [1024,1024]; a mismatch makes the",
    "        # texture-array packing fail and drops the material back to the warning texture.",
    "        definition: Dict[str, Any] = {",
    '            "internalName": material_name,',
    '            "class": "TerrainMaterial",',
    '            "persistentId": new_id(),',
    '            "annotation": "GRASS",',
    '            "groundmodelName": "GRASS",',
    '            "macroDistances": [0, 10, 100, 3000],',
    '            "detailDistances": [0, 0, 30, 50],',
    "            # --- base colour ---",
    '            "baseColorBaseTex": f"{base}/t_terrain_base_grass_b.png",',
    '            "baseColorBaseTexSize": 150,',
    '            "baseColorMacroTex": f"{base}/t_macro_grass2_b.png",',
    '            "baseColorMacroTexSize": 80,',
    '            "baseColorMacroStrength": [0.2, 0.1],',
    '            "baseColorDetailTex": f"{base}/t_grass1_b.png",',
    '            "baseColorDetailStrength": [0.3, 0],',
    "            # --- normal ---",
    '            "normalBaseTex": f"{base}/t_terrain_base_grass_nm.png",',
    '            "normalBaseTexSize": 150,',
    '            "normalMacroTex": f"{base}/t_macro_grass2_nm.png",',
    '            "normalMacroTexSize": 80,',
    '            "normalMacroStrength": [0.6, 0.6],',
    '            "normalDetailTex": f"{base}/t_grass1_nm.png",',
    '            "normalDetailStrength": [0.6, 0.2],',
    "            # --- roughness ---",
    '            "roughnessBaseTex": f"{base}/t_terrain_base_grass_r.png",',
    '            "roughnessBaseTexSize": 150,',
    '            "roughnessMacroTex": f"{base}/t_macro_grass2_r.png",',
    '            "roughnessMacroTexSize": 80,',
    '            "roughnessMacroStrength": [0.7, 1],',
    '            "roughnessDetailTex": f"{base}/t_grass1_r.png",',
    '            "roughnessDetailStrength": [1, 0],',
    "            # --- ambient occlusion ---",
    '            "aoBaseTex": f"{base}/t_terrain_base_grass_ao.png",',
    '            "aoBaseTexSize": 150,',
    '            "aoMacroTex": f"{base}/t_macro_grass2_ao.png",',
    '            "aoMacroTexSize": 80,',
    '            "aoMacroStrength": [1, 0.5],',
    '            "aoDetailTex": f"{base}/t_grass1_ao.png",',
    '            "aoDetailStrength": [1, 0],',
    "            # --- height drives layer blending, not shading ---",
    '            "heightBaseTex": f"{base}/t_terrain_base_grass_h.png",',
    '            "heightBaseTexSize": 150,',
    '            "heightMacroTex": f"{base}/t_macro_grass2_h.png",',
    '            "heightMacroTexSize": 80,',
    '            "heightDetailTex": f"{base}/t_grass1_h.png",',
    "        }",
    "",
    '        definitions = {f"{material_name}-{new_id()}": definition}',
    "",
    "        # Modern levels use art/terrains/; art/terrain/ is the older spelling.  Both are",
    "        # written because different engine paths look in different places.",
    '        for folder in ("terrains", "terrain"):',
    "            target = os.path.join(self.level_root, \"art\", folder)",
    "            os.makedirs(target, exist_ok=True)",
    '            self.write_json(os.path.join(target, "main.materials.json"), definitions)',
]

new = head + material_block + lines[build_def:]
text = "\n".join(new)

# Sanity checks before writing.
for required in (
    "def emit_sky_and_sun(self)",
    "def emit_terrain_materials(self)",
    "def build(self)",
    "def verify_level(",
    "def zip_mod(",
):
    if text.count(required) != 1:
        raise SystemExit(f"{required!r} appears {text.count(required)} times")

if "Lighting.  Without this the level loads pitch black" in text:
    raise SystemExit("stale sky body still present")
if "clouds_low" in text:
    raise SystemExit("stale clouds_low still present")

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print()
print(f"wrote {PATH}: {len(new)} lines")
