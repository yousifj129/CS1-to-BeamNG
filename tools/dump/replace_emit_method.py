"""Replace emit_terrain_materials wholesale, using line boundaries."""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")

NEW_METHOD = '''    def emit_terrain_materials(self) -> None:
        """
        Emit the terrain material replicated from skeleton_coast, with its textures provisioned.

        Every field of the source material is written unchanged apart from `internalName`, `name`
        and a fresh `persistentId`.  Texture values come from provision_skeleton_terrain(), which
        copies the base family in and writes `.link` sidecars for the detail and macro families.
        """
        if self.terrain is None:
            return

        resolved = provision_skeleton_terrain(self.level_root, self.level_name)
        for name in sorted(resolved):
            self.report["files"].append(
                os.path.relpath(
                    os.path.join(self.level_root, "art", "terrains", name), self.mod_root
                )
            )
        if not resolved:
            self.report["warnings"].append(
                "terrain textures could not be provided; the ground will render untextured"
            )

        material_name = self.terrain_materials[0]

        definition: Dict[str, Any] = {}
        for field, value in CS1_TERRAIN_MATERIAL.items():
            definition[field] = resolved.get(field, value)
        definition["internalName"] = material_name
        definition["name"] = material_name
        definition["persistentId"] = new_id()

        texture_set = dict(CS1_TERRAIN_TEXTURE_SET)
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()

        definitions = {
            f"{self.level_name}TerrainMaterialTextureSet": texture_set,
            f"{material_name}-{new_id()}": definition,
        }

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)
        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        # The base family is 4096 in the source map, and the TerrainBlock must agree with it.
        self.terrain_texture_base_size = int((texture_set.get("baseTexSize") or [4096])[0])
        self.report["terrainMaterial"] = {
            "internalName": material_name,
            "groundmodelName": definition.get("groundmodelName"),
            "textureSet": texture_set["name"],
            "texturesResolved": len(resolved),
            "baseTexSize": self.terrain_texture_base_size,
            "detailTexSize": definition.get("baseColorDetailTexSize"),
            "source": "skeleton_coast",
        }
'''

lines = io.open(TARGET, encoding="utf-8").read().split("\n")
start = next(i for i, l in enumerate(lines) if l.strip().startswith("def emit_terrain_materials"))
end = next(i for i, l in enumerate(lines) if i > start and l.strip().startswith("def emit_preview_image"))

lines = lines[:start] + NEW_METHOD.split("\n") + [""] + lines[end:]
src = "\n".join(lines)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("copied references left:", src.count("copied"), "(other functions use it legitimately)")
body = src[src.index("def emit_terrain_materials"):src.index("def emit_preview_image")]
print("emit method uses 'copied':", "copied" in body)
