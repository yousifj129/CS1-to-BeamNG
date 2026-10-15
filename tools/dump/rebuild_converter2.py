"""
Reconstruct tools/beamng_convert.py deterministically.

State of the file after earlier edits:
  * lines 1..1841          good code, ending with emit_sky_and_sun (... self.sky_objects = objects)
  * lines 1843..1991       module-level building helpers that were wrongly placed INSIDE the class
                           (make_building_dae, build_material_definitions, the service map,
                           building_material_name) -- they carry 4-space indentation
  * lines 1992..3131       a duplicate copy of class BeamNGLevelBuilder
  * lines 3132..end        the good tail (zip_mod, find_beamng_user_mods, verify_level, ...)

Also, emit_terrain_materials() was DESTROYED by the bad edit, so it is re-emitted here with the
template-verified texture paths and sizes.
"""

import collections
import io

PATH = r"D:\Developer\open source projects\cities-skylines-to-beamng-map\tools\beamng_convert.py"

lines = io.open(PATH, encoding="utf-8").read().split("\n")
print(f"input: {len(lines)} lines")


def idx(pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("anchor not found")


# ---- sections -------------------------------------------------------------------------
sky_end = idx(lambda l: l.strip() == "self.sky_objects = objects")
helpers_start = idx(lambda l: l.strip().startswith("def make_building_dae("), sky_end)
class2 = idx(lambda l: l.startswith("class BeamNGLevelBuilder"), helpers_start)
tail_start = idx(lambda l: l.startswith("def zip_mod("), class2)

print(f"  good head      : 1..{sky_end + 1}")
print(f"  helpers        : {helpers_start + 1}..{class2} ({class2 - helpers_start} lines)")
print(f"  duplicate class: {class2 + 1}..{tail_start}")
print(f"  good tail      : {tail_start + 1}..{len(lines)}")

# ---- 1. dedent the misplaced helper block ---------------------------------------------
block = lines[helpers_start:class2]
while block and block[-1].strip() == "":
    block.pop()
dedented = [l[4:] if l.startswith("    ") else l for l in block]

# ---- 2. the destroyed method, re-emitted with template-verified values -----------------
METHOD = '''
    def emit_terrain_materials(self) -> None:
        """
        A v1.5 (PBR) TerrainMaterial, copied field-for-field from the template level's `Grass`.

        BeamNG has TWO terrain material generations and the TerrainBlock decides which applies:

          * v1 classic -- no `materialTextureSet`; materials use diffuseMap/normalMap.
          * v1.5 PBR   -- TerrainBlock references a TerrainMaterialTextureSet; materials use
                          baseColor/normal/roughness/ao/height *Tex at base, macro, detail scales.

        Every modern level uses v1.5, so a classic material is unresolvable and drops to
        WARNING_MATERIAL, which renders as flat grey.

        The values below are not invented.  An earlier revision guessed them -- pointing every
        slot at `/levels/template/...` and using *TexSize 150/80 -- and the terrain packed no
        textures at all.  The real material uses:

          base   : /levels/template/art/terrains/t_terrain_base_grass_*
          detail : /assets/materials/terrain/grass/ind_grass/t_ind_grass_*
          macro  : /assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_*
          sizes  : base 512, macro 64   (world metres per tile)
        """
        if self.terrain is None:
            return

        base = "/levels/template/art/terrains"
        grass = "/assets/materials/terrain/grass/ind_grass"
        macro = "/assets/materials/terrain/soil/macro_clumply"
        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = {
            "internalName": material_name,
            "class": "TerrainMaterial",
            "persistentId": new_id(),
            "groundmodelName": "GRASS",
            "macroDistances": [0, 10, 100, 3000],
            # --- base colour ---
            "baseColorBaseTex": f"{base}/t_terrain_base_grass_b.png",
            "baseColorBaseTexSize": 512,
            "baseColorMacroTex": f"{macro}/t_macro_clumpy_b.png",
            "baseColorMacroTexSize": 64,
            "baseColorMacroStrength": [0.05, 0.12],
            "baseColorDetailTex": f"{grass}/t_ind_grass_b.png",
            "baseColorDetailStrength": [0.25, 0.25],
            # --- normal ---
            "normalBaseTex": f"{base}/t_terrain_base_grass_nm.png",
            "normalBaseTexSize": 512,
            "normalMacroTex": f"{macro}/t_macro_clumpy_nm.png",
            "normalMacroTexSize": 64,
            "normalMacroStrength": [0.2, 0.4],
            "normalDetailTex": f"{grass}/t_ind_grass_nm.png",
            "normalDetailStrength": [0.7, 0.15],
            # --- roughness ---
            "roughnessBaseTex": f"{base}/t_terrain_base_grass_r.png",
            "roughnessBaseTexSize": 512,
            "roughnessMacroTex": f"{macro}/t_macro_clumpy_r.png",
            "roughnessMacroTexSize": 64,
            "roughnessMacroStrength": [0.15, 0.8],
            "roughnessDetailTex": f"{grass}/t_ind_grass_r.png",
            "roughnessDetailStrength": [0.3, 0.3],
            # --- ambient occlusion ---
            "aoBaseTex": f"{base}/t_terrain_base_grass_ao.png",
            "aoBaseTexSize": 512,
            "aoMacroTex": f"{macro}/t_macro_clumpy_ao.png",
            "aoMacroTexSize": 64,
            "aoDetailTex": f"{grass}/t_ind_grass_ao.png",
            # --- height drives layer blending, not shading ---
            "heightBaseTex": f"{base}/t_terrain_base_grass_h.png",
            "heightBaseTexSize": 512,
            "heightMacroTex": f"{macro}/t_macro_clumpy_h.png",
            "heightMacroTexSize": 64,
            "heightDetailTex": f"{grass}/t_ind_grass_h.png",
        }

        # The TerrainBlock resolves this BY NAME from THIS level's material library; it is not
        # global.  Every shipped level declares its own.  Omitting it reports
        # "Failed to find TerrainMaterialTextureSet" and then falls back to WARNING_MATERIAL.
        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [512, 512],
            "macroTexSize": [1024, 1024],
            "detailTexSize": [1024, 1024],
        }

        definitions = {
            f"{self.level_name}_1.5TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        # Modern levels use art/terrains/; art/terrain/ is the older spelling.
        for folder in ("terrains", "terrain"):
            target = os.path.join(self.level_root, "art", folder)
            os.makedirs(target, exist_ok=True)
            self.write_json(os.path.join(target, "main.materials.json"), definitions)

'''

# ---- 3. assemble ----------------------------------------------------------------------
# head (1..sky_end) + helpers (dedented, at module level) + METHOD inside the class
head = lines[: sky_end + 1]
rest = lines[tail_start:]

# The helpers must sit at module level, so they go after the class.  Simpler and safe: put
# them immediately before `class BeamNGLevelBuilder` in the head.
class1 = next(i for i, l in enumerate(head) if l.startswith("class BeamNGLevelBuilder"))

assembled = (
    head[:class1]
    + dedented
    + [""]
    + head[class1:]
)

# Insert METHOD as the last method of the class: just before the module-level `def zip_mod(`
# in `rest`.  But the class body lives in `head`, so append METHOD to the end of head instead.
assembled = assembled + METHOD.split("\n") + rest

text = "\n".join(assembled)
io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)

# ---- 4. verify ------------------------------------------------------------------------
final = text.split("\n")
tops = collections.Counter(l for l in final if l.startswith(("class ", "def ")))
dups = {k: v for k, v in tops.items() if v > 1}
print()
print(f"final: {len(final)} lines")
print(f"duplicate top-level constructs: {dups if dups else 'NONE'}")
for want in ("class BeamNGLevelBuilder", "def make_building_dae", "def zip_mod",
             "def verify_level", "def build_material_definitions"):
    print(f"  {want:<32} x{sum(1 for l in final if l.startswith(want))}")
print(f"  emit_terrain_materials           x{text.count('def emit_terrain_materials(self)')}")
print(f"  emit_sky_and_sun                 x{text.count('def emit_sky_and_sun(self)')}")
