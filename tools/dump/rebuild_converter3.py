"""
Final, deterministic reconstruction of tools/beamng_convert.py.

Use the pre-breakage backup (build/beamng_convert.py.bak) as the source of truth for the class,
because its section boundaries were verified earlier:

    head     : 1..1603            code before emit_sky_and_sun
    sky      : 1604..1731         NEW template-based emit_sky_and_sun
    v1.5 mat : 1732..1961         the v1.5 emit_terrain_materials (to be replaced)
    stale    : 1962..2006         old duplicate emit_terrain_materials (drop)
    tail     : 2007..end          build() onward

Target file:
    head + sky
      + [new module-level building helpers, dedented]
      + emit_terrain_materials  (rebuilt with template-verified paths/sizes)
      + tail  (build() onward, with emit_preview_image wired in)
"""

import collections
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
BACKUP = os.path.join(REPO, "build", "beamng_convert.py.bak")
BROKEN = os.path.join(REPO, "build", "beamng_convert.py.broken")
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

bak = io.open(BACKUP, encoding="utf-8").read().split("\n")
broken = io.open(BROKEN, encoding="utf-8").read().split("\n")


def idx(lines, pred, start=0):
    for i in range(start, len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("anchor not found")


# ---- sections from the backup ---------------------------------------------------------
sky_start = idx(bak, lambda l: l.strip().startswith("def emit_sky_and_sun(self)"))
v15_start = idx(bak, lambda l: l.strip().startswith("def emit_terrain_materials(self)"), sky_start + 1)
stale_start = idx(bak, lambda l: l.strip().startswith("def emit_terrain_materials(self)"), v15_start + 1)
tail_start = idx(bak, lambda l: l.strip().startswith("def build(self)"), stale_start + 1)
print(f"backup: head 1..{sky_start}, sky {sky_start+1}..{v15_start}, "
      f"v1.5 {v15_start+1}..{stale_start}, stale {stale_start+1}..{tail_start}, tail {tail_start+1}..")

head = bak[:sky_start]          # everything before the sky method
sky = bak[sky_start:v15_start]  # the new template sky method
tail = bak[tail_start:]         # build() onward

# ---- building helpers, taken from the broken file and dedented ------------------------
h_start = idx(broken, lambda l: l.strip().startswith("def make_building_dae("))
h_end = idx(broken, lambda l: l.strip().startswith("def emit_terrain_materials(self)"), h_start + 1)
helpers = broken[h_start:h_end]
while helpers and helpers[-1].strip() == "":
    helpers.pop()
# The lead line is already flush; the rest are indented one level (they lived in a class).
helpers = [helpers[0]] + [l[4:] if l.startswith("    ") else l for l in helpers[1:]]
print(f"helpers: {len(helpers)} lines, starts {helpers[0]!r}")

# ---- rebuilt emit_terrain_materials ---------------------------------------------------
METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        A v1.5 (PBR) TerrainMaterial, copied field-for-field from the template level's `Grass`.

        The TerrainBlock decides which generation applies:

          * v1 classic -- no `materialTextureSet`; materials use diffuseMap/normalMap.
          * v1.5 PBR   -- TerrainBlock references a TerrainMaterialTextureSet; materials use
                          baseColor/normal/roughness/ao/height *Tex at base, macro, detail scales.

        Every modern level uses v1.5, so a classic material is unresolvable and drops to
        WARNING_MATERIAL, which renders as flat grey.

        The values below are NOT invented.  An earlier revision guessed them -- pointing every
        slot at `/levels/template/...` with *TexSize 150/80 -- and the terrain packed no textures
        at all.  The real template material uses:

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
            "baseColorBaseTex": f"{base}/t_terrain_base_grass_b.png",
            "baseColorBaseTexSize": 512,
            "baseColorMacroTex": f"{macro}/t_macro_clumpy_b.png",
            "baseColorMacroTexSize": 64,
            "baseColorMacroStrength": [0.05, 0.12],
            "baseColorDetailTex": f"{grass}/t_ind_grass_b.png",
            "baseColorDetailStrength": [0.25, 0.25],
            "normalBaseTex": f"{base}/t_terrain_base_grass_nm.png",
            "normalBaseTexSize": 512,
            "normalMacroTex": f"{macro}/t_macro_clumpy_nm.png",
            "normalMacroTexSize": 64,
            "normalMacroStrength": [0.2, 0.4],
            "normalDetailTex": f"{grass}/t_ind_grass_nm.png",
            "normalDetailStrength": [0.7, 0.15],
            "roughnessBaseTex": f"{base}/t_terrain_base_grass_r.png",
            "roughnessBaseTexSize": 512,
            "roughnessMacroTex": f"{macro}/t_macro_clumpy_r.png",
            "roughnessMacroTexSize": 64,
            "roughnessMacroStrength": [0.15, 0.8],
            "roughnessDetailTex": f"{grass}/t_ind_grass_r.png",
            "roughnessDetailStrength": [0.3, 0.3],
            "aoBaseTex": f"{base}/t_terrain_base_grass_ao.png",
            "aoBaseTexSize": 512,
            "aoMacroTex": f"{macro}/t_macro_clumpy_ao.png",
            "aoMacroTexSize": 64,
            "aoDetailTex": f"{grass}/t_ind_grass_ao.png",
            "heightBaseTex": f"{base}/t_terrain_base_grass_h.png",
            "heightBaseTexSize": 512,
            "heightMacroTex": f"{macro}/t_macro_clumpy_h.png",
            "heightMacroTexSize": 64,
            "heightDetailTex": f"{grass}/t_ind_grass_h.png",
        }

        # The TerrainBlock resolves this BY NAME from THIS level's material library; it is not a
        # global.  Every shipped level declares its own.  Omitting it reports
        # "Failed to find TerrainMaterialTextureSet" and falls back to WARNING_MATERIAL, which
        # then causes the GPU assert that crashes the game.
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

# ---- assemble -------------------------------------------------------------------------
# The class lives in `head`; helpers must be module-level, so they precede the class.
class_at = idx(head, lambda l: l.startswith("class BeamNGLevelBuilder"))
assembled = (
    head[:class_at]
    + helpers
    + [""]
    + head[class_at:]
    + sky
    + METHOD.split("\n")
    + tail
)

text = "\n".join(assembled)
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(text)

final = text.split("\n")
tops = collections.Counter(l for l in final if l.startswith(("class ", "def ")))
dups = {k: v for k, v in tops.items() if v > 1}
print()
print(f"wrote {TARGET}: {len(final)} lines")
print(f"duplicate top-level constructs: {dups if dups else 'NONE'}")
print(f"  emit_terrain_materials   x{text.count('def emit_terrain_materials(self)')}")
print(f"  emit_sky_and_sun         x{text.count('def emit_sky_and_sun(self)')}")
print(f"  emit_preview_image       x{text.count('def emit_preview_image(self)')}")
print(f"  make_building_dae        x{text.count('def make_building_dae(')}")
print(f"  old stale clouds_low     x{text.count('clouds_low')}")
