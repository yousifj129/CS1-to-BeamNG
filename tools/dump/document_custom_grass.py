"""Document the supplied ground texture and the rules it changed."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "docs", "POLISH_ROADS_REFERENCE.md")

text = io.open(PATH, encoding="utf-8").read()

SECTION = '''
---

## 22. Green ground, at last: the level ships its own colour texture

Every previous attempt failed for a structural reason, not a tuning one. A level's terrain **base**
layer is meant to be a large colour texture that the level itself ships -- polish_roads_v2's is a
2048 m satellite photograph of its own map. The engine's own terrain textures measure near-neutral
grey; the greenest found anywhere in the install has a green bias of only **+15**, and no material
field can tint a terrain material (there is no `baseColorFactor` on `TerrainMaterial` -- it appears on
none of the 191 across the install).

So the ground could not be made green from built-in content at all. It needed an image.

### The supplied texture

`textures/grass.jpg`, 893x894 JPEG. Measured **mean RGB (89, 99, 45), green bias +31.7** -- twice as
green as anything the engine ships, and it is real grass rather than gravel speckled with green.

The converter now writes it into the level as
`levels/<level>/art/terrains/t_grass_ground_b.png`:

* converted to PNG, the format every terrain texture reference here uses;
* centre-cropped to a square so it does not stretch, then resized to **1024x1024** and saved as PNG.
  The power of two matters: `baseTexSize` declares a *required* size and the engine discards anything
  that does not match, packing the layer black -- a rule that already cost several rounds.

### Only the colour slot changed

| slot | source |
|---|---|
| **base colour** | **the supplied `grass.jpg`** |
| base normal / roughness / ao / height | engine `forest/t_forest_ground_02` |
| detail | engine `grass/t_grass_01`, 3 m |
| macro | engine `grass/macro_grass`, 40 m |

The engine maps stay on the non-colour slots deliberately: normal, roughness, ao and height are detail
maps that modulate whatever colour is underneath, which is exactly how the engine's own materials are
built. Keeping them means the ground still has proper relief and lighting response rather than being
a flat photograph.

Base tile is **32 m** -- 1024 px over 32 m is about 3 cm per texel, fine enough not to pixelate and
coarse enough not to repeat visibly across a 32 km world.

`convert_custom_terrain_texture` returns None rather than raising when the source is missing, so a
level still builds without it and the reference material is used instead.

### Rules that changed

Three rules had been written when the goal was strictly engine-only content, and they failed against
the supplied texture. Rather than loosening them into meaning nothing, each now states the real
requirement:

| rule | before | now |
|---|---|---|
| texture source split | "all 15 from the engine library" | exactly **one shipped** (the ground colour), **14 engine** |
| copied textures | "no texture is copied into the mod" | no texture shipped *other than* the ground colour |
| install resolution | "every base texture resolves in the install" | every **engine** base texture resolves; the shipped one is checked against the mod |

Plus three new rules for the shipped texture: that it is present, that its size **matches the declared
`baseTexSize`**, and that it is **genuinely green** (bias > +15), since being green is the entire
reason it exists.

### Still to do

Normal, roughness, ao and height maps for the supplied texture. Its current maps come from a different
image, so the relief does not correspond to the visible grass; it reads acceptably but is not correct.

'''

anchor = "## 8. What the rewrite must do, concretely"
if anchor not in text:
    raise SystemExit("section 8 anchor not found")
text = text.replace(anchor, SECTION.strip() + "\n\n---\n\n" + anchor, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(text)
print("appended section 22; document is now", len(text.split("\n")), "lines")
