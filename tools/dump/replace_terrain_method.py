"""Replace emit_terrain_materials wholesale with a correctly indented version."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("    def emit_terrain_materials(self) -> None:")
end = src.index("    def emit_preview_image(self) -> None:", start)

METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit the terrain material in the arrangement that working maps use.

        Verified against polish_roads_v2, a large working third-party map.  Its terrain material
        splits the texture families deliberately:

            *BaseTex    shipped inside the level, 2048x2048
            *DetailTex  referenced from the engine library, 1024x1024
            *MacroTex   referenced from the engine library, 1024x1024

        and its TerrainMaterialTextureSet mirrors that exactly:

            baseTexSize   [2048, 2048]
            detailTexSize [1024, 1024]
            macroTexSize  [1024, 1024]

        The set sizes must match the textures the engine actually loads.  When they disagree the
        arrays cannot be packed and every slot reports "Missing Terrain texture: /", which renders
        the ground flat grey -- the failure we chased for several rounds.

        Only the five base textures are copied in, resized to the declared size; the other ten come
        from `/assets/materials/terrain/...` and are resolved by the engine.
        """
        if self.terrain is None:
            return

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)

        base_size = 2048
        copied = copy_base_terrain_textures(terrain_dir, base_size)
        for _name, path in sorted(copied.items()):
            self.report["files"].append(os.path.relpath(path, self.mod_root))
        if not copied:
            self.report["warnings"].append(
                "no base terrain textures could be copied; the ground will render untextured"
            )

        # Confirm the files really are the size we are about to declare.
        measured = [png_pixel_size(p) for p in copied.values()]
        measured = [m for m in measured if m]
        if measured:
            base_size = max(set(measured), key=measured.count)

        detail_size = 1024
        macro_size = 1024
        vfs = f"/levels/{self.level_name.lower()}/art/terrains"
        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = {
            "name": material_name,
            "internalName": material_name,
            "class": "TerrainMaterial",
            "persistentId": new_id(),
            "groundmodelName": "GRASS",
            "annotation": "GRASS",
            "macroDistances": [0, 10, 100, 3000],
            "detailDistances": [0, 0, 30, 60],
        }

        for field, filename in CS1_TERRAIN_BASE_TEX.items():
            definition[field] = f"{vfs}/{filename}"
        for field in ("baseColorBaseTexSize", "normalBaseTexSize", "roughnessBaseTexSize",
                      "aoBaseTexSize", "heightBaseTexSize"):
            definition[field] = base_size

        definition.update(CS1_TERRAIN_ENGINE_TEX)
        for field in ("baseColorMacroTexSize", "normalMacroTexSize", "roughnessMacroTexSize",
                      "aoMacroTexSize", "heightMacroTexSize"):
            definition[field] = 80

        definition["baseColorMacroStrength"] = [0.05, 0.12]
        definition["baseColorDetailStrength"] = [0.25, 0.25]
        definition["normalMacroStrength"] = [0.2, 0.4]
        definition["normalDetailStrength"] = [0.7, 0.15]
        definition["roughnessMacroStrength"] = [0.15, 0.8]
        definition["roughnessDetailStrength"] = [0.3, 0.3]

        texture_set = {
            "class": "TerrainMaterialTextureSet",
            "name": self.texture_set_name,
            "persistentId": new_id(),
            "baseTexSize": [base_size, base_size],
            "detailTexSize": [detail_size, detail_size],
            "macroTexSize": [macro_size, macro_size],
        }

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        self.report["terrainMaterial"] = {
            "internalName": material_name,
            "groundmodelName": definition["groundmodelName"],
            "textureSet": texture_set["name"],
            "baseTexSize": base_size,
            "detailTexSize": detail_size,
            "macroTexSize": macro_size,
            "localTextures": sorted(copied),
        }

        # art/terrains/ is the modern location; mirror to art/terrain/ for older lookup paths.
        legacy = os.path.join(self.level_root, "art", "terrain")
        os.makedirs(legacy, exist_ok=True)
        for name, path in copied.items():
            with open(path, "rb") as source, open(os.path.join(legacy, name), "wb") as target:
                target.write(source.read())
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)
        self.write_json(os.path.join(legacy, "main.materials.json"), definitions)

'''

src = src[:start] + METHOD + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("replaced emit_terrain_materials")
print("base/engine split present :", "CS1_TERRAIN_ENGINE_TEX" in src)
