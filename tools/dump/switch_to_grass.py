"""Switch the terrain detail/macro references from the asphalt family to grass."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()
before = src

src = src.replace("/t_asphalt_02/t_asphalt_02_", "/grass/ind_grass/t_ind_grass_")
src = src.replace("/macro_asphalt/t_macro_asphalt_", "/soil/macro_clumply/t_macro_clumpy_")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)

print("changed              :", src != before)
print("t_ind_grass present  :", "t_ind_grass_b.png" in src)
print("t_macro_clumpy present:", "t_macro_clumpy_b.png" in src)
print("asphalt refs left    :", src.count("t_asphalt_02"), src.count("t_macro_asphalt"))
