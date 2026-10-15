"""
Generate one building shape per material, each binding that material in the DAE.

BeamNG's TSStatic reference: materials come from the shape's own material list, matched to
Material definitions by name.  There is no per-instance material override, so `materialName` on
the TSStatic does nothing and a shape with no binding renders as the engine's warning material
(the flat orange seen in game).

A working shipped shape uses exactly this form:

    <material id="lod_vertcol-material" name="lod_vertcol">
    <instance_material symbol="lod_vertcol-material" target="#lod_vertcol-material">

so the same structure is emitted here, with the material name matching the key (and `mapTo`) in
main.materials.json.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
s = io.open(TARGET, encoding="utf-8").read()

# ---- 1. DAE gains a bound material ----------------------------------------------------
OLD_TAIL = """    positions = " ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts)
    indices = " ".join(" ".join(str(i) for i in f) for f in faces)
    vcount = " ".join("4" for _ in faces)
"""
NEW_TAIL = """    positions = " ".join(f"{x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts)
    indices = " ".join(" ".join(str(i) for i in f) for f in faces)
    vcount = " ".join("4" for _ in faces)

    # The material MUST be bound here.  TSStatic takes its materials from the shape's material
    # list, matched to Material definitions by name, so `materialName` on the TSStatic itself is
    # ignored and an unbound shape draws in the engine's warning material.
    symbol = f"{material}-material"
"""
if OLD_TAIL not in s:
    raise SystemExit("DAE tail anchor not found")
s = s.replace(OLD_TAIL, NEW_TAIL, 1)

# signature
s = s.replace(
    'def make_building_dae(name: str, shape: str) -> str:',
    'def make_building_dae(name: str, shape: str, material: str) -> str:',
    1,
)

# library_effects / materials, and the bound instance
s = s.replace(
    '''  <library_geometries>
    <geometry id="{name}-mesh" name="{name}">''',
    '''  <library_effects>
    <effect id="{symbol}-effect">
      <profile_COMMON>
        <technique sid="common">
          <lambert>
            <emission><color>0 0 0 1</color></emission>
            <ambient><color>0.35 0.35 0.35 1</color></ambient>
            <diffuse><color>0.72 0.72 0.70 1</color></diffuse>
          </lambert>
        </technique>
      </profile_COMMON>
    </effect>
  </library_effects>
  <library_materials>
    <material id="{symbol}" name="{material}">
      <instance_effect url="#{symbol}-effect"/>
    </material>
  </library_materials>
  <library_geometries>
    <geometry id="{name}-mesh" name="{name}">''',
    1,
)

s = s.replace(
    '''        <polylist count="{len(faces)}">
          <input semantic="VERTEX" source="#{name}-vertices" offset="0"/>''',
    '''        <polylist material="{symbol}" count="{len(faces)}">
          <input semantic="VERTEX" source="#{name}-vertices" offset="0"/>''',
    1,
)

s = s.replace(
    '''      <node id="{name}-node" name="{name}" type="NODE">
        <instance_geometry url="#{name}-mesh"/>
      </node>''',
    '''      <node id="{name}-node" name="{name}" type="NODE">
        <instance_geometry url="#{name}-mesh">
          <bind_material>
            <technique_common>
              <instance_material symbol="{symbol}" target="#{symbol}"/>
            </technique_common>
          </bind_material>
        </instance_geometry>
      </node>''',
    1,
)

# ---- 2. emit one shape per material ---------------------------------------------------
OLD_EMIT = '''        for shape in ("block", "tower"):
            name = f"cs1_building_{shape}"
            dae_path = os.path.join(shape_dir, f"{name}.dae")
            with open(dae_path, "w", encoding="utf-8") as handle:
                handle.write(make_building_dae(name, shape))
            self.report["files"].append(os.path.relpath(dae_path, self.mod_root))
'''
NEW_EMIT = '''        # One shape per (silhouette, material) pair, because the material is bound inside the
        # DAE and TSStatic has no per-instance material override.
        for shape in ("block", "tower"):
            for key, _colour, _roughness in BUILDING_PALETTE:
                material = f"cs1_building_{key}"
                name = f"cs1_building_{shape}_{key}"
                dae_path = os.path.join(shape_dir, f"{name}.dae")
                with open(dae_path, "w", encoding="utf-8") as handle:
                    handle.write(make_building_dae(name, shape, material))
                self.report["files"].append(os.path.relpath(dae_path, self.mod_root))
'''
if OLD_EMIT not in s:
    raise SystemExit("shape emit anchor not found")
s = s.replace(OLD_EMIT, NEW_EMIT, 1)

# ---- 3. TSStatic points at the shape for its material ---------------------------------
s = s.replace(
    '                "shapeName": f"/art/shapes/{self.mod_name}/cs1_building_{shape}.dae",',
    '                "shapeName": (\n'
    '                    f"/art/shapes/{self.mod_name}/cs1_building_{shape}_"\n'
    '                    f"{BUILDING_MATERIAL_FOR_SERVICE.get(building.service, \'default\')}.dae"\n'
    '                ),',
    1,
)
# materialName is ignored by TSStatic; keep it only as documentation of intent.
s = s.replace(
    '                "materialName": building_material_name(building.service),',
    '                # Informational only: TSStatic has no per-instance material override, the\n'
    '                # binding lives in the shape.  Kept so the level file records the intent.\n'
    '                "materialName": building_material_name(building.service),',
    1,
)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(s)
print("patched make_building_dae signature :", "def make_building_dae(name: str, shape: str, material: str)" in s)
print("one shape per material              :", "for key, _colour, _roughness in BUILDING_PALETTE:" in s)
print("TSStatic shapeName per material     :", "cs1_building_{shape}_" in s)
