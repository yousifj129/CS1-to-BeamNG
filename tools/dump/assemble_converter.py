"""
Assemble the final tools/beamng_convert.py from verified parts.

Sources
  backup (build/beamng_convert.py.bak) : the last state whose class section was correct
  broken (build/beamng_convert.py.broken): holds the new template sky method and the building
                                            helpers, but spliced mid-class

Parts
  A  head            backup 1..1603            imports, geometry, loader, terrain, png helpers
  B  sky method      broken 1712..1842         new template-based emit_sky_and_sun (indent 4)
  C  class body      backup, from `class BeamNGLevelBuilder` to end of emit_proxy_box_shape
                                               (the stale emit_terrain_materials is excluded)
  D  building helpers broken 1843..1991, dedented to module level, plus make_terrain_texture
  E  emit_terrain_materials  written fresh with template-verified paths and sizes
  F  tail            backup, from `def zip_mod(` onward
"""

import collections
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
bak = io.open(os.path.join(REPO, "build", "beamng_convert.py.bak"), encoding="utf-8").read().split("\n")
broken = io.open(os.path.join(REPO, "build", "beamng_convert.py.broken"), encoding="utf-8").read().split("\n")


def find(lines, pred, start=0, end=None):
    for i in range(start, end if end is not None else len(lines)):
        if pred(lines[i]):
            return i
    raise SystemExit("anchor not found")


# ---- A: head ---------------------------------------------------------------------------
head = bak[:1603]

# ---- B: sky method ---------------------------------------------------------------------
b_sky_start = find(broken, lambda l: l.strip().startswith("def emit_sky_and_sun(self)"))
b_sky_end = find(broken, lambda l: l.strip().startswith("def make_building_dae("), b_sky_start + 1)
sky = broken[b_sky_start:b_sky_end]
while sky and sky[-1].strip() == "":
    sky.pop()

# ---- C: class body (up to and including emit_proxy_box_shape) --------------------------
c_class = find(bak, lambda l: l.startswith("class BeamNGLevelBuilder"))
c_last = find(bak, lambda l: l.strip().startswith("def emit_sky_and_sun(self)"), c_class)
class_body = bak[c_class:c_last]
while class_body and class_body[-1].strip() == "":
    class_body.pop()

# ---- D: module-level helpers -----------------------------------------------------------
D_BLOCK = '''def make_terrain_texture(size: int = 512) -> Any:
    """
    A low-contrast mid-tone grass texture.

    Kept deliberately gentle: the v1 terrain shader tiles this across the whole ground, so a
    busy or high-contrast texture reads as noise from a car, and mid-tone leaves headroom for
    the engine's macro/detail blending.
    """
    coarse = _value_noise(size, 8, 1)
    medium = _value_noise(size, 32, 2)
    fine = _value_noise(size, 96, 3)

    blend = 0.55 * coarse + 0.30 * medium + 0.15 * fine
    blend = (blend - blend.min()) / max(float(blend.max() - blend.min()), 1e-6)

    base = np.array([0.34, 0.44, 0.23], dtype=np.float32)
    variation = (blend - 0.5)[:, :, None] * 0.28
    rgb = np.clip(base[None, None, :] + variation, 0.0, 1.0)

    speckle = (_value_noise(size, 256, 4) - 0.5)[:, :, None] * 0.05
    rgb = np.clip(rgb + speckle, 0.0, 1.0)

    return (rgb * 255.0 + 0.5).astype(np.uint8)


def make_building_dae(name: str, shape: str) -> str:
    """
    Build a small Collada building mesh with NO material binding.

    Deliberately no <library_materials>/<bind_material>: BeamNG then leaves the surface unbound
    and the `materialName` on each TSStatic decides the finish.  That gives per-building control
    from the level file, and it removes the earlier failure where the DAE's own material name did
    not resolve so every building drew in the engine's flat orange warning material.

    Geometry spans X/Y in -0.5..0.5 (centred on the instance) and Z in 0..1 (base at Z=0), so an
    instance scale of (halfWidth, halfLength, height) plus a rotation about Z stands the mass on
    the terrain, centred on the building.

      "block"  a rectangular mass with a roof cap.
      "tower"  the same plus two setbacks, so tall buildings are not plain cuboids.
    """
    verts = []
    faces = []

    def add_box(x0, y0, z0, x1, y1, z1):
        b = len(verts)
        verts.extend([
            (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
            (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
        ])
        faces.extend([
            (b + 0, b + 3, b + 2, b + 1),
            (b + 4, b + 5, b + 6, b + 7),
            (b + 0, b + 1, b + 5, b + 4),
            (b + 1, b + 2, b + 6, b + 5),
            (b + 2, b + 3, b + 7, b + 6),
            (b + 3, b + 0, b + 4, b + 7),
        ])

    if shape == "tower":
        add_box(-0.5, -0.5, 0.0, 0.5, 0.5, 0.72)
        add_box(-0.4, -0.4, 0.72, 0.4, 0.4, 0.88)
        add_box(-0.28, -0.28, 0.88, 0.28, 0.28, 1.0)
    else:
        add_box(-0.5, -0.5, 0.0, 0.5, 0.5, 0.88)
        add_box(-0.52, -0.52, 0.88, 0.52, 0.52, 0.97)

    positions = " ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts)
    indices = " ".join(" ".join(str(i) for i in f) for f in faces)
    vcount = " ".join("4" for _ in faces)

    return f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <contributor><authoring_tool>CS1-to-BeamNG</authoring_tool></contributor>
    <unit meter="1" name="meter"/>
    <up_axis>Z_UP</up_axis>
  </asset>
  <library_geometries>
    <geometry id="{name}-mesh" name="{name}">
      <mesh>
        <source id="{name}-positions">
          <float_array id="{name}-positions-array" count="{len(verts) * 3}">{positions}</float_array>
          <technique_common>
            <accessor source="#{name}-positions-array" count="{len(verts)}" stride="3">
              <param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>
            </accessor>
          </technique_common>
        </source>
        <vertices id="{name}-vertices">
          <input semantic="POSITION" source="#{name}-positions"/>
        </vertices>
        <polylist count="{len(faces)}">
          <input semantic="VERTEX" source="#{name}-vertices" offset="0"/>
          <vcount>{vcount}</vcount>
          <p>{indices}</p>
        </polylist>
      </mesh>
    </geometry>
  </library_geometries>
  <library_visual_scenes>
    <visual_scene id="{name}-scene" name="{name}-scene">
      <node id="{name}-node" name="{name}" type="NODE">
        <instance_geometry url="#{name}-mesh"/>
      </node>
    </visual_scene>
  </library_visual_scenes>
  <scene><instance_visual_scene url="#{name}-scene"/></scene>
</COLLADA>
"""


# Building materials, one per CS1 service, so a converted city is not monochrome.  A broken
# material binding renders as a hot orange, which is exactly what one iteration looked like.
BUILDING_PALETTE = [
    ("residential", [0.74, 0.72, 0.67], 0.85),
    ("commercial", [0.62, 0.68, 0.76], 0.55),
    ("industrial", [0.58, 0.56, 0.52], 0.90),
    ("office", [0.52, 0.60, 0.70], 0.35),
    ("civic", [0.80, 0.78, 0.72], 0.70),
    ("utility", [0.50, 0.50, 0.48], 0.80),
    ("default", [0.70, 0.68, 0.64], 0.80),
]

BUILDING_MATERIAL_FOR_SERVICE = {
    "Residential": "residential",
    "Commercial": "commercial",
    "Industrial": "industrial",
    "Office": "office",
    "Beautification": "civic",
    "Electricity": "utility",
    "Water": "utility",
    "Garbage": "utility",
    "HealthCare": "civic",
    "PoliceDepartment": "civic",
    "FireDepartment": "civic",
    "Education": "civic",
    "PublicTransport": "utility",
    "Monument": "civic",
}


def building_material_name(service: str) -> str:
    return f"cs1_building_{BUILDING_MATERIAL_FOR_SERVICE.get(service, 'default')}"


def build_material_definitions() -> Dict[str, Any]:
    definitions: Dict[str, Any] = {}
    for key, colour, roughness in BUILDING_PALETTE:
        material_name = f"cs1_building_{key}"
        definitions[material_name] = {
            "name": material_name,
            "mapTo": material_name,
            "class": "Material",
            "persistentId": new_id(),
            "Stages": [
                {"baseColorFactor": colour + [1.0], "roughnessFactor": roughness},
                {"baseColorFactor": colour + [1.0], "roughnessFactor": roughness},
                {},
                {},
            ],
            "materialTag0": "beamng",
            "version": 1.5,
        }
    return definitions
'''

# ---- E: emit_terrain_materials ---------------------------------------------------------
METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        A v1.5 (PBR) TerrainMaterial, copied field-for-field from the template level's `Grass`.

        The TerrainBlock decides which generation applies:

          * v1 classic -- no `materialTextureSet`; materials use diffuseMap/normalMap.
          * v1.5 PBR   -- TerrainBlock references a TerrainMaterialTextureSet; materials use
                          baseColor/normal/roughness/ao/height *Tex at base, macro and detail.

        Every modern level uses v1.5, so a classic material is unresolvable and drops to
        WARNING_MATERIAL, which renders as flat grey.

        These values are NOT invented.  An earlier revision guessed them -- every slot pointing at
        `/levels/template/...` with *TexSize 150/80 -- and the terrain packed no textures at all.
        The real template material uses:

          base   : /levels/template/art/terrains/t_terrain_base_grass_*
          detail : /assets/materials/terrain/grass/ind_grass/t_ind_grass_*
          macro  : /assets/materials/terrain/soil/macro_clumply/t_macro_clumpy_*
          sizes  : base 512, macro 64    (world metres per tile)
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
        # global, and every shipped level declares its own.  Omitting it reports
        # "Failed to find TerrainMaterialTextureSet", falls back to WARNING_MATERIAL, and that
        # missing binding is what produced the D3D12 assert that crashed the game.
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

        for folder in ("terrains", "terrain"):
            target = os.path.join(self.level_root, "art", folder)
            os.makedirs(target, exist_ok=True)
            self.write_json(os.path.join(target, "main.materials.json"), definitions)

    def emit_preview_image(self) -> None:
        """
        Write `_preview.png` beside the level.

        BeamNG's free-roam selector requests this and logs a 404 on every render without it, so
        the level shows a blank tile in the list.
        """
        if self.terrain is None:
            return

        size = 256
        grid = _resample(self.terrain.heights.astype(np.float32), size)
        gy, gx = np.gradient(grid)
        shade = np.clip(0.5 + (gx * 2.0 + gy * 2.0), 0.0, 1.0)
        shade = 0.45 + shade * 0.55

        base_colour = np.array([0.42, 0.52, 0.30], dtype=np.float32)
        rgb = np.clip(base_colour[None, None, :] * shade[:, :, None], 0.0, 1.0)
        pixels = (rgb * 255.0 + 0.5).astype(np.uint8)

        path = os.path.join(self.level_root, "_preview.png")
        write_png_rgb(path, pixels)
        self.report["files"].append(os.path.relpath(path, self.mod_root))
'''

# ---- F: tail ---------------------------------------------------------------------------
f_tail = find(bak, lambda l: l.startswith("def zip_mod("))
tail = bak[f_tail:]

# ---- assemble --------------------------------------------------------------------------
class_at = find(head, lambda l: l.startswith("class BeamNGLevelBuilder"))
parts = (
    head[:class_at]
    + D_BLOCK.split("\n")
    + [""]
    + head[class_at:]
    + sky
    + [""]
    + METHOD.split("\n")
    + [""]
    + tail
)
text = "\n".join(parts)

# Wire emit_preview_image into build(), and keep the sky/material calls in order.
text = text.replace(
    "        self.emit_terrain_files()\n        self.emit_info_json()",
    "        self.emit_terrain_files()\n        self.emit_preview_image()\n        self.emit_info_json()",
)

io.open(os.path.join(REPO, "tools", "beamng_convert.py"), "w", encoding="utf-8", newline="\n").write(text)

final = text.split("\n")
tops = collections.Counter(l for l in final if l.startswith(("class ", "def ")))
dups = {k: v for k, v in tops.items() if v > 1}
print(f"wrote {len(final)} lines")
print(f"duplicate top-level constructs: {dups if dups else 'NONE'}")
for want in ("class BeamNGLevelBuilder", "def make_building_dae", "def make_terrain_texture",
             "def build_material_definitions", "def zip_mod", "def verify_level"):
    print(f"  {want:<34} x{sum(1 for l in final if l.startswith(want))}")
for want in ("def emit_terrain_materials(self)", "def emit_sky_and_sun(self)",
             "def emit_preview_image(self)", "def emit_proxy_box_shape(self)",
             "def emit_buildings(self)", "def build(self)"):
    print(f"  {want:<34} x{text.count(want)}")
