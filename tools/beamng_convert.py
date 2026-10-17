#!/usr/bin/env python3
"""
CS1-to-BeamNG :: Part 2 -- city_layout.json  ->  BeamNG.drive level mod
=======================================================================

Converts a Cities: Skylines 1 export (produced by mod/CS1ToBeamNGExporter.cs) into a working
BeamNG.drive level.

    CS1 roads  -> DecalRoad objects (materialised terrain-projected road decals)
    CS1 height -> a synthetic terrain heightmap, interpolated from the road elevation samples
    CS1 builds -> TSStatic proxy boxes with real collision

Output is a complete BeamNG level under a mod root:

    <out>/<ModName>/
        info.json                              level metadata (title, size, spawn points)
        <level>/<level>.terrain.json            terrain descriptor
        <level>/<level>.terrainheightmap.png    generated heightmap
        <level>/main/items.level.json           MissionGroup + spawns
        <level>/main/MissionGroup/Roads/...     DecalRoads
        <level>/main/MissionGroup/Buildings/... TSStatic proxy boxes
        art/shapes/cs1_proxy_box.dae            the box shape every building instance uses
        art/shapes/cs1_proxy_box.materials.json box materials

Plus a .zip of that folder, ready to drop into the BeamNG user mods folder.

--------------------------------------------------------------------------------------
WHAT THIS CONVERTER DOES **NOT** DO
--------------------------------------------------------------------------------------
The CS1 layout JSON has no terrain.  Cities: Skylines stores the ground as Unity Terrain and
the exporter only records roads and buildings, so there are no real elevation samples.

The heightmap generated here is therefore a *best-effort reconstruction*: it is interpolated
from the Y coordinate (elevation) of the road network, which in CS1 already sits on the
terrain surface.  Hills crossed by no road are flattened, and the coast/water is not
represented.  Roads still land correctly because each road node is re-snapped to the generated
surface, and BeamNG re-projects DecalRoads onto terrain at runtime.

--------------------------------------------------------------------------------------
COORDINATE MAPPING (stated once, used everywhere)
--------------------------------------------------------------------------------------
CS1 is Unity: left-handed, Y up, metres.
BeamNG is Torque3D: right-handed, Z up, metres.

    x_bng = -x_cs1          (negating X flips handedness)
    y_bng =  z_cs1
    z_bng =  y_cs1

A yaw of theta about CS1's +Y becomes -theta about BeamNG's +Z.
All conversion lives in `to_beamng()` / `yaw_to_beamng()` so it can be unit-tested.

--------------------------------------------------------------------------------------
Usage
--------------------------------------------------------------------------------------
    python tools/beamng_convert.py <city_layout.json> [options]

    --out DIR             output root (default: ./dist)
    --level-name NAME     BeamNG level name (default: from the CS1 city name)
    --mod-name NAME       mod folder name (default: cs1_<level>)
    --include-non-drivable  also convert rail / ship / plane / pedestrian / utility paths
    --heightmap-size N    heightmap resolution in pixels (default 2048)
    --max-width M         widen roads narrower than this (default 6.0 m)
    --no-terrain          skip terrain, emit roads with overObjects instead
    --install             copy the built level into the BeamNG user mods folder
    --json-report PATH    write a machine-readable conversion report
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import struct
import sys
import unicodedata
import zipfile
import uuid
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover
    np = None

SCHEMA_VERSION = 1

# ==========================================================================================
#  1.  GEOMETRY AND COORDINATE MAPPING
# ==========================================================================================


def to_beamng(x: float, y: float, z: float) -> Tuple[float, float, float]:
    """Unity (left-handed, Y up) -> BeamNG (right-handed, Z up)."""
    return (-x, z, y)


def yaw_to_beamng(angle_radians: float) -> float:
    """CS1 yaw about +Y (Unity) -> BeamNG yaw about +Z."""
    return -angle_radians


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    @staticmethod
    def from_json(raw: Any) -> "Vec3":
        if not isinstance(raw, dict):
            return Vec3(0.0, 0.0, 0.0)
        return Vec3(
            _finite(raw.get("x")),
            _finite(raw.get("y")),
            _finite(raw.get("z")),
        )

    def beamng(self) -> Tuple[float, float, float]:
        return to_beamng(self.x, self.y, self.z)

    def distance_to(self, other: "Vec3") -> float:
        return math.sqrt(
            (self.x - other.x) ** 2 + (self.y - other.y) ** 2 + (self.z - other.z) ** 2
        )

    def lerp(self, other: "Vec3", t: float) -> "Vec3":
        return Vec3(
            self.x + (other.x - self.x) * t,
            self.y + (other.y - self.y) * t,
            self.z + (other.z - self.z) * t,
        )


def _finite(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    value = float(value)
    return value if math.isfinite(value) else default


@dataclass
class Bezier:
    start: Vec3
    control1: Vec3
    control2: Vec3
    end: Vec3

    def point_at(self, t: float) -> Vec3:
        p01 = self.start.lerp(self.control1, t)
        p12 = self.control1.lerp(self.control2, t)
        p23 = self.control2.lerp(self.end, t)
        return p01.lerp(p12, t).lerp(p12.lerp(p23, t), t)

    def split(self, t: float = 0.5) -> Tuple["Bezier", "Bezier"]:
        p01 = self.start.lerp(self.control1, t)
        p12 = self.control1.lerp(self.control2, t)
        p23 = self.control2.lerp(self.end, t)
        p012 = p01.lerp(p12, t)
        p123 = p12.lerp(p23, t)
        mid = p012.lerp(p123, t)
        return (
            Bezier(self.start, p01, p012, mid),
            Bezier(mid, p123, p23, self.end),
        )

    def deviation(self) -> float:
        """
        Distance from the curve's actual midpoint to the chord midpoint.

        This is the honest measure of how wrong a straight-line approximation would be.  Using
        the control points' distance from the chord instead (a common shortcut) badly
        under-measures gentle curves: a road can have control points almost on the chord while
        the curve bulges a metre away from it.
        """
        return self.point_at(0.5).distance_to(self.start.lerp(self.end, 0.5))

    def sample_adaptive(
        self,
        max_sagitta: float = 0.5,
        max_depth: int = 6,
        _depth: int = 0,
    ) -> List[Vec3]:
        """
        Subdivide until the curve is within `max_sagitta` metres of the chord.

        Returns interior samples only (excluding `start`, including `end`), so the caller can
        concatenate segments without duplicating shared endpoints.
        """
        chord = self.start.distance_to(self.end)

        # A segment shorter than the tolerance needs no subdivision at all.
        if _depth >= max_depth or (chord > 0.25 and self.deviation() <= max_sagitta):
            return [self.end]

        left, right = self.split(0.5)
        return left.sample_adaptive(max_sagitta, max_depth, _depth + 1) + right.sample_adaptive(
            max_sagitta, max_depth, _depth + 1
        )


def _point_line_distance(p: Vec3, a: Vec3, b: Vec3) -> float:
    ab = (b.x - a.x, b.y - a.y, b.z - a.z)
    ap = (p.x - a.x, p.y - a.y, p.z - a.z)
    ab_len_sq = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2
    if ab_len_sq < 1e-12:
        return math.sqrt(ap[0] ** 2 + ap[1] ** 2 + ap[2] ** 2)
    t = max(0.0, min(1.0, (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / ab_len_sq))
    cx, cy, cz = a.x + ab[0] * t, a.y + ab[1] * t, a.z + ab[2] * t
    return math.sqrt((p.x - cx) ** 2 + (p.y - cy) ** 2 + (p.z - cz) ** 2)


def rotation_matrix_z(yaw_radians: float) -> List[float]:
    """BeamNG rotationMatrix: 9 floats, row-major, applied as row-vector * matrix."""
    c = math.cos(yaw_radians)
    s = math.sin(yaw_radians)
    return [c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0]


# ==========================================================================================
#  2.  LOADING AND VALIDATING THE CS1 LAYOUT
# ==========================================================================================


@dataclass
class Road:
    segment_id: int
    start_node_id: int
    end_node_id: int
    prefab_name: str
    road_class: str
    vehicle_types: str
    is_one_way: bool
    is_straight: bool
    measured_width: float
    half_width: float
    lane_count: int
    start_position: Vec3
    end_position: Vec3
    bezier: Optional[Bezier]

    def polyline(self, max_sagitta: float = 1.0) -> List[Vec3]:
        if self.bezier is not None:
            return [self.bezier.start] + self.bezier.sample_adaptive(max_sagitta)
        return [self.start_position, self.end_position]

    def surface_polyline(self, max_sagitta: float = 0.5) -> List[Vec3]:
        """
        The centre-line used for terrain reconstruction and mesh generation, in CS1 space.

        In CS1 the segment's Bezier is *not* exactly the node chain: across the Cannes export the
        Bezier sits +1.000 m above the node positions on 1040 segments and -0.300 m below on 326,
        and on 259 segments (mostly Basic Road) its endpoints are pulled along the segment to
        handle junction corners.

        So neither endpoint is taken directly from the Bezier:

        * ELEVATION is averaged between node and Bezier, which cancels the systematic +1.000 /
          -0.300 bias.
        * GROUND POSITION (x, z) is snapped to the NODE.  Node positions are where roads actually
          meet -- measured across the export, nodes shared by two roads agree to 0.000 m -- whereas
          the Bezier endpoint is pulled in at exactly the junctions.  Keeping the Bezier's x/z is
          what left every chain stopping short of its junction: of 111 junction nodes, none had a
          chain endpoint on it, the closest being 2 m away and the median 10 m.

        Interior points still come from the Bezier alone.
        """
        if self.bezier is None:
            return [self.start_position, self.end_position]

        points = self.polyline(max_sagitta)
        if not points:
            return points

        first = points[0]
        points[0] = Vec3(
            self.start_position.x,
            (first.y + self.start_position.y) * 0.5,
            self.start_position.z,
        )

        last = points[-1]
        points[-1] = Vec3(
            self.end_position.x,
            (last.y + self.end_position.y) * 0.5,
            self.end_position.z,
        )

        return points


@dataclass
class Building:
    building_id: int
    prefab_name: str
    asset_title: str
    service: str
    sub_service: str
    position: Vec3
    angle_radians: float
    width: float
    length: float
    height: float
    is_collapsed: bool
    is_abandoned: bool


@dataclass
class CityLayout:
    schema_version: int
    meta: Dict[str, Any]
    city_name: str
    roads: List[Road] = field(default_factory=list)
    buildings: List[Building] = field(default_factory=list)

    def bounds(self) -> Tuple[float, float, float, float, float, float]:
        """
        (min_x, max_x, min_y, max_y, min_z, max_z) over roads and buildings, in CS1 space.

        NOTE the axis meaning: in CS1, X and Z are the horizontal plane and Y is elevation.
        So the third/fourth values are the ground-height range, and the fifth/sixth are the
        north-south footprint.  Mixing these up silently produces a kilometre-deep terrain.
        """
        xs: List[float] = []
        heights: List[float] = []
        zs: List[float] = []

        for road in self.roads:
            for point in road.surface_polyline(max_sagitta=2.0):
                xs.append(point.x)
                heights.append(point.y)
                zs.append(point.z)

        for building in self.buildings:
            xs.append(building.position.x)
            heights.append(building.position.y)
            zs.append(building.position.z)

        if not xs:
            return (-1.0, 1.0, 0.0, 1.0, -1.0, 1.0)

        return (
            min(xs),
            max(xs),
            min(heights),
            max(heights),
            min(zs),
            max(zs),
        )


def load_city_layout(path: str) -> Tuple[CityLayout, List[str], List[str]]:
    """Parse a city_layout.json.  Returns (layout, problems, warnings)."""
    problems: List[str] = []
    warnings: List[str] = []

    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return _empty_layout(), [f"file not found: {path}"], warnings
    except json.JSONDecodeError as exc:
        return _empty_layout(), [f"invalid JSON: {exc}"], warnings
    except OSError as exc:
        return _empty_layout(), [f"could not read file: {exc}"], warnings

    if not isinstance(raw, dict):
        return _empty_layout(), ["top level must be a JSON object"], warnings

    version = raw.get("schemaVersion")
    if version is None:
        problems.append("missing 'schemaVersion'")
        version = SCHEMA_VERSION
    elif version != SCHEMA_VERSION:
        warnings.append(
            f"schemaVersion is {version}, this converter targets {SCHEMA_VERSION}"
        )

    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    if not meta:
        problems.append("missing or invalid 'meta' section")

    city_name = str(meta.get("cityName") or "").strip() or "CS1City"

    layout = CityLayout(schema_version=version, meta=meta, city_name=city_name)

    roads_raw = raw.get("roads")
    if not isinstance(roads_raw, list):
        problems.append("missing or invalid 'roads' array")
        roads_raw = []

    for index, item in enumerate(roads_raw):
        if not isinstance(item, dict):
            problems.append(f"roads[{index}]: expected an object")
            continue

        bezier_raw = item.get("bezier")
        bezier: Optional[Bezier] = None
        if isinstance(bezier_raw, dict):
            try:
                bezier = Bezier(
                    Vec3.from_json(bezier_raw["start"]),
                    Vec3.from_json(bezier_raw["control1"]),
                    Vec3.from_json(bezier_raw["control2"]),
                    Vec3.from_json(bezier_raw["end"]),
                )
            except KeyError as exc:
                warnings.append(f"roads[{index}]: bezier missing {exc}; using a straight span")

        width = _finite(item.get("measuredWidth"))
        if width <= 0.0:
            width = _finite(item.get("halfWidth")) * 2.0

        layout.roads.append(
            Road(
                segment_id=int(_finite(item.get("segmentId"), -1)),
                start_node_id=int(_finite(item.get("startNodeId"))),
                end_node_id=int(_finite(item.get("endNodeId"))),
                prefab_name=str(item.get("prefabName") or ""),
                road_class=str(item.get("roadClass") or ""),
                vehicle_types=str(item.get("vehicleTypes") or ""),
                is_one_way=bool(item.get("isOneWay")),
                is_straight=bool(item.get("isStraight")),
                measured_width=width,
                half_width=_finite(item.get("halfWidth")),
                lane_count=int(_finite(item.get("laneCount"))),
                start_position=Vec3.from_json(item.get("startPosition")),
                end_position=Vec3.from_json(item.get("endPosition")),
                bezier=bezier,
            )
        )

    buildings_raw = raw.get("buildings")
    if not isinstance(buildings_raw, list):
        problems.append("missing or invalid 'buildings' array")
        buildings_raw = []

    for index, item in enumerate(buildings_raw):
        if not isinstance(item, dict):
            problems.append(f"buildings[{index}]: expected an object")
            continue

        layout.buildings.append(
            Building(
                building_id=int(_finite(item.get("buildingId"), -1)),
                prefab_name=str(item.get("prefabName") or ""),
                asset_title=str(item.get("assetTitle") or ""),
                service=str(item.get("service") or ""),
                sub_service=str(item.get("subService") or ""),
                position=Vec3.from_json(item.get("position")),
                angle_radians=_finite(item.get("angleRadians")),
                width=_finite(item.get("width")),
                length=_finite(item.get("length")),
                height=_finite(item.get("height")),
                is_collapsed=bool(item.get("isCollapsed")),
                is_abandoned=bool(item.get("isAbandoned")),
            )
        )

    if not layout.roads and not layout.buildings:
        problems.append("the file contains no roads and no buildings")

    return layout, problems, warnings


def _empty_layout() -> CityLayout:
    return CityLayout(schema_version=SCHEMA_VERSION, meta={}, city_name="CS1City")


# ==========================================================================================
#  3.  SELECTING WHICH CS1 PATHS BECOME DRIVABLE BEAMNG ROADS
# ==========================================================================================

# CS1 puts a lot of invisible infrastructure in NetManager: water pipes, power lines, ship
# lanes, plane paths and rail.  Those must not become road decals.
NON_DRIVABLE_CLASSES = frozenset(
    {
        "water pipe",
        "electricity wire",
        "ship path",
        "airplane path",
        "airplane connection path",
        "airplane taxi path",
        "pedestrian path",
        "pedestrian street",
        "train track",
        "train track bridge",
        "metro track",
    }
)

# CS1 prefab / class name -> a material that definitely ships with BeamNG.
# Confirmed present in art/shapes/common/decalroads/main.materials.json.
ROAD_MATERIALS: Tuple[Tuple[Tuple[str, ...], str], ...] = (
    (("highway",), "road_asphalt_2lane"),
    (("ramp", "elevated", "bridge", "overpass"), "road_asphalt_2lane"),
    (("oneway", "one way"), "road_asphalt_2lane"),
    (("gravel", "dirt", "unpaved", "rural"), "m_dirt_road"),
    (("pedestrian", "path", "pavement", "walkway", "sidewalk"), "m_dirt_road"),
    (("concrete", "pavement"), "road1_concrete"),
    (("track",), "m_dirt_road"),
)
DEFAULT_ROAD_MATERIAL = "road_asphalt_2lane"


def is_drivable(road: Road) -> bool:
    if road.road_class.strip().lower() in NON_DRIVABLE_CLASSES:
        return False
    if road.prefab_name.strip().lower() in NON_DRIVABLE_CLASSES:
        return False
    # "VehicleTypes" is the CS1 VehicleType flags string, e.g. "Car, Bicycle" or "None".
    vehicle_types = road.vehicle_types.lower()
    return "car" in vehicle_types


def material_for(road: Road) -> str:
    haystack = f"{road.road_class} {road.prefab_name}".lower()
    for keywords, material in ROAD_MATERIALS:
        if any(keyword in haystack for keyword in keywords):
            return material
    return DEFAULT_ROAD_MATERIAL


# ==========================================================================================
#  4.  TERRAIN
# ==========================================================================================


@dataclass
class Terrain:
    """
    A generated BeamNG terrain.

    `size` is the heightmap resolution (a power of two: BeamNG requires 128..8192).
    `square_size` is metres per heightmap sample, so the covered world square is
    `size * square_size` metres.
    `position` is the BeamNG-space origin of the terrain block's low corner, and
    `height_min` is the Z of height value 0, so

        world_z = position_z + stored_height * (max_height / 65536)

    `heights` is the uint16 heightmap (size x size, row-major) and `layers` is the uint8
    material layer map of the same shape.
    """

    size: int
    square_size: float
    position_x: float
    position_y: float
    height_min: float
    max_height: float
    heights: Any
    layers: Any
    heightmap_png: Any          # uint8 preview, written as <level>.terrainheightmap.png
    png_resolution: int

    @property
    def world_size(self) -> float:
        return self.size * self.square_size

    def height_at(self, x: float, y: float) -> float:
        """Bilinear sample of the terrain surface at a BeamNG-space X/Y, in metres Z."""
        res = self.size
        if res < 2:
            return self.height_min

        gx = (x - self.position_x) / self.world_size * (res - 1)
        gy = (y - self.position_y) / self.world_size * (res - 1)
        gx = max(0.0, min(res - 1.001, gx))
        gy = max(0.0, min(res - 1.001, gy))

        x0, y0 = int(gx), int(gy)
        fx, fy = gx - x0, gy - y0

        h = self.heights
        v00 = float(h[y0, x0])
        v10 = float(h[y0, x0 + 1])
        v01 = float(h[y0 + 1, x0])
        v11 = float(h[y0 + 1, x0 + 1])

        top = v00 + (v10 - v00) * fx
        bottom = v01 + (v11 - v01) * fx
        stored = top + (bottom - top) * fy

        return self.height_min + stored * (self.max_height / 65535.0)


# ==========================================================================================
#  Road surface rasterising
# ==========================================================================================

# Layer-map index of each terrain material.  The `.ter` stores its material NAMES in this same
# order, and every layer byte is an index into that list, so these two must not drift apart.
TERRAIN_LAYER_GRASS = 0
TERRAIN_LAYER_ASPHALT = 1
TERRAIN_MATERIAL_ORDER = ["Grass", "Asphalt"]


def rasterise_road_surface(
    roads: Sequence["Road"],
    terrain: "Terrain",
    extra_width: float = 1.0,
    max_sagitta: float = 1.5,
    centrelines: Optional[Sequence[Dict[str, Any]]] = None,
) -> Any:
    """
    Mark every terrain cell covered by a road, returning a boolean mask.

    Accepts either the CS1 `roads` list or a list of already-chained `centrelines` (the records
    `chain_roads` / `derive_roads_from_buildings` produce).  Pass `centrelines` whenever the emitted
    geometry may differ from the CS1 road list -- painting one geometry and emitting another leaves
    the road surface in the wrong place, which is exactly what happened when this was called from
    `build_terrain`.

    Each segment is walked in small steps and the cells within `width/2 + extra_width` of each step
    are set.  The buffer is applied to both sides and around each round dot, so segments meeting at
    a junction overlap there instead of leaving a thin grass seam exactly where tyres cross most.
    """
    if np is None:
        raise RuntimeError("numpy is required for terrain rasterising")

    res = terrain.size
    mask = np.zeros((res, res), dtype=bool)
    if res < 2:
        return mask

    span = terrain.world_size
    if span <= 0:
        return mask
    to_cell = (res - 1) / span

    def stamp(ax: float, ay: float, bx: float, by: float, radius: float) -> None:
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy)
        step = max(0.5, min(radius, 2.0))
        steps = max(1, int(math.ceil(length / step)))
        cell_radius = radius * to_cell + 1.0

        for s in range(steps + 1):
            t = s / steps
            cx = (ax + dx * t - terrain.position_x) * to_cell
            cy = (ay + dy * t - terrain.position_y) * to_cell

            x0 = max(0, int(math.floor(cx - cell_radius)))
            x1 = min(res - 1, int(math.ceil(cx + cell_radius)))
            y0 = max(0, int(math.floor(cy - cell_radius)))
            y1 = min(res - 1, int(math.ceil(cy + cell_radius)))
            if x1 < x0 or y1 < y0:
                continue

            ys, xs = np.ogrid[y0 : y1 + 1, x0 : x1 + 1]
            inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= cell_radius * cell_radius
            mask[y0 : y1 + 1, x0 : x1 + 1] |= inside

    if centrelines is not None:
        for entry in centrelines:
            radius = max(float(entry.get("width") or 0.0), 1.0) * 0.5 + max(0.0, extra_width)
            pts = entry.get("points") or []
            for index in range(len(pts) - 1):
                ax, ay, _ = pts[index].beamng()
                bx, by, _ = pts[index + 1].beamng()
                stamp(ax, ay, bx, by, radius)
        return mask

    for road in roads:
        width = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0)
        radius = width * 0.5 + max(0.0, extra_width)
        pts = road.surface_polyline(max_sagitta=max_sagitta)
        for index in range(len(pts) - 1):
            ax, ay, _ = pts[index].beamng()
            bx, by, _ = pts[index + 1].beamng()
            stamp(ax, ay, bx, by, radius)

    return mask


def paint_road_surface(
    terrain: "Terrain",
    centrelines: Sequence[Dict[str, Any]],
    extra_width: float = 1.0,
) -> int:
    """
    Paint the emitted centrelines into `terrain.layers`, returning the number of asphalt cells.

    Cells become `TERRAIN_LAYER_ASPHALT`, everything else `TERRAIN_LAYER_GRASS`.  255 is never
    written -- it punches a hole through the terrain rather than selecting a material.
    """
    mask = rasterise_road_surface(
        [], terrain, extra_width=extra_width, centrelines=centrelines
    )
    if not mask.any():
        return 0
    terrain.layers = np.where(mask, TERRAIN_LAYER_ASPHALT, TERRAIN_LAYER_GRASS).astype(np.uint8)
    return int(np.count_nonzero(mask))


def choose_terrain_size(
    extent: float, max_resolution: int = 8192, cell_size: float = 0.0
) -> Tuple[int, float]:
    """
    Choose the heightmap resolution and the metres per grid cell for a map of `extent` metres.

    Both shipped maps that render correctly use 1 m per cell with a 2048 grid, i.e. a 2 km world.
    Cannes spans about 8 km and the heightmap is capped at 8192 cells, so 1 m per cell cannot cover
    it -- roads and buildings outside the block would sit on nothing.

    The cell size is therefore the smallest power of two that lets an 8192-cell grid cover the
    extent, and the grid is the extent divided by it.  `squareSize` is written so the engine scales
    terrain materials to the same world units the grid uses; leaving it out makes the engine assume
    1 m and mis-scale every material.
    """
    if cell_size and cell_size > 0:
        cell = float(cell_size)
    else:
        cell = 1.0
        while extent / cell > max_resolution:
            cell *= 2.0

    resolution = int(extent / cell) + 1
    snapped = 128
    while snapped < resolution and snapped < max_resolution:
        snapped *= 2
    if snapped < resolution:
        snapped = max_resolution

    return snapped, cell


def build_terrain(
    layout: CityLayout,
    roads: Sequence[Road],
    heightmap_size: int = 2048,
    margin: float = 100.0,
    verbose: bool = True,
) -> Terrain:
    """
    Reconstruct a heightmap from the road network's elevation samples and pack it for BeamNG.

    CS1 roads sit on the terrain surface, so each road node's Y is a genuine ground sample.
    Samples are scattered onto a working grid, gaps are filled from a coarse pyramid, and the
    result is smoothed and upsampled to the final terrain resolution.

    `heightmap_size` is only the resolution of the exported preview PNG; the terrain grid
    itself is chosen by `choose_terrain_size` to obey BeamNG's power-of-two requirement.
    """
    if np is None:
        raise RuntimeError(
            "numpy is required for terrain generation (pip install numpy), or pass --no-terrain"
        )

    min_x, max_x, min_y, max_y, min_z, max_z = layout.bounds()

    # bounds() returns (min_x, max_x, min_height, max_height, min_z, max_z).
    # BeamNG-space footprint: X from -x_cs1, Y from z_cs1.
    bng_min_x, bng_max_x = -max_x, -min_x
    bng_min_y, bng_max_y = min_z, max_z

    span_x = (bng_max_x - bng_min_x) + margin * 2.0
    span_y = (bng_max_y - bng_min_y) + margin * 2.0
    extent = max(span_x, span_y, 256.0)

    resolution, square_size = choose_terrain_size(extent)
    world_size = resolution * square_size

    # Centre the terrain on the data.
    centre_x = (bng_min_x + bng_max_x) * 0.5
    centre_y = (bng_min_y + bng_max_y) * 0.5
    position_x = centre_x - world_size * 0.5
    position_y = centre_y - world_size * 0.5

    height_min = min_y
    height_max = max_y
    max_height = max(height_max - height_min, 1.0)

    # ---- scatter the road elevation samples -------------------------------------------
    work_res = min(resolution, 2048)
    work = np.full((work_res, work_res), np.nan, dtype=np.float32)
    metres_per_cell = world_size / work_res
    samples = 0

    for road in roads:
        points = road.surface_polyline(max_sagitta=max(1.5, metres_per_cell * 0.5))
        for point in points:
            bx, by, bz = point.beamng()
            gx = int((bx - position_x) / world_size * (work_res - 1))
            gy = int((by - position_y) / world_size * (work_res - 1))
            if 0 <= gx < work_res and 0 <= gy < work_res:
                normalised = (bz - height_min) / max_height
                existing = work[gy, gx]
                if np.isnan(existing):
                    work[gy, gx] = normalised
                else:
                    work[gy, gx] = (existing + normalised) * 0.5
                samples += 1

    if samples == 0:
        work[:] = 0.0

    # ---- fill, smooth, upsample --------------------------------------------------------
    filled = _as_square(_fill_gaps(work), work_res)
    smoothed = _smooth(filled, iterations=3)
    smoothed = np.nan_to_num(smoothed, nan=0.0, posinf=1.0, neginf=0.0)

    # Coarse pass.  `_smooth` is a 3x3 kernel, so its reach is a few cells -- about 12 m here.  The
    # steep facets come from `_fill_gaps` interpolating across the long gaps between sparse road
    # samples, which no amount of local smoothing removes.  Downsampling by 4 makes each smoothing
    # step cover 16x the ground, so the long ramps get flattened too.
    coarse_res = max(16, work_res // 4)
    if coarse_res < work_res:
        coarse = _as_square(_resample(smoothed, coarse_res), coarse_res)
        coarse = _smooth(coarse, iterations=2)
        coarse = _as_square(_resample(coarse, work_res), work_res)
        coarse = np.nan_to_num(coarse, nan=0.0, posinf=1.0, neginf=0.0)
        # Blend rather than replace, so genuine elevation differences (road grades, hills) are
        # softened but not erased.  0.65 toward the coarse result removes the facets while leaving
        # the overall shape recognisable.
        smoothed = smoothed * 0.35 + coarse * 0.65

    smoothed = _smooth(smoothed, iterations=2)
    smoothed = np.nan_to_num(smoothed, nan=0.0, posinf=1.0, neginf=0.0)
    normalised_grid = _as_square(np.clip(smoothed, 0.0, 1.0), work_res)

    if resolution != work_res:
        terrain_grid = _as_square(_resample(normalised_grid, resolution), resolution)
    else:
        terrain_grid = normalised_grid

    # BeamNG stores heights as u16 scaled by maxHeight / 65536.
    heights = np.clip(np.rint(terrain_grid * 65535.0), 0, 65535).astype(np.uint16)

    # Layer map: 0 everywhere (a single material), never 255 (which would punch a hole).
    layers = np.zeros((resolution, resolution), dtype=np.uint8)

    # Preview PNG at the requested (much smaller) resolution.
    png_resolution = max(64, min(int(heightmap_size), resolution))
    if png_resolution != resolution:
        png_grid = _as_square(_resample(normalised_grid, png_resolution), png_resolution)
    else:
        png_grid = normalised_grid
    heightmap_png = np.clip(np.rint(png_grid * 255.0), 0, 255).astype(np.uint8)

    if verbose:
        print(
            f"  terrain: {world_size / 1000.0:.2f} km square "
            f"({resolution}x{resolution} @ {square_size:g} m/sample), "
            f"{samples} elevation samples, height {height_min:.1f}..{height_max:.1f} m"
        )

    return Terrain(
        size=resolution,
        square_size=square_size,
        position_x=position_x,
        position_y=position_y,
        height_min=height_min,
        max_height=max_height,
        heights=heights,
        layers=layers,
        heightmap_png=heightmap_png,
        png_resolution=png_resolution,
    )


def _fill_gaps(work: Any) -> Any:
    """
    Fill unknown cells with plausible values, without scipy.

    Strategy: build a mip pyramid by 2x2 nan-mean pooling.  Coarse levels are dense because
    every pool that contains at least one sample gets a value, so after a handful of levels the
    whole map is covered.  Then walk back down, filling each finer level from its coarser
    parent wherever it has no samples of its own.

    This keeps real road elevations where they exist (roads stay accurate) and interpolates
    everything else from the nearest pyramid cell, in O(N) with no iteration-count tuning.
    """
    levels: List[Any] = [work]

    # --- build the pyramid -------------------------------------------------------------
    while True:
        current = levels[-1]
        if current.shape[0] <= 4 and current.shape[1] <= 4:
            break

        height, width = current.shape
        even_h = height - (height % 2)
        even_w = width - (width % 2)

        if even_h < 2 or even_w < 2:
            break

        view = current[:even_h, :even_w]
        valid = ~np.isnan(view)
        total = np.where(valid, view, 0.0).reshape(even_h // 2, 2, even_w // 2, 2).sum(axis=(1, 3))
        count = valid.reshape(even_h // 2, 2, even_w // 2, 2).sum(axis=(1, 3)).astype(np.float32)

        with np.errstate(invalid="ignore", divide="ignore"):
            pooled = np.where(count > 0, total / np.maximum(count, 1.0), np.nan)

        # Re-attach a padded border for odd dimensions.
        if even_h != height or even_w != width:
            padded = np.full(
                ((height + 1) // 2, (width + 1) // 2), np.nan, dtype=np.float32
            )
            padded[: pooled.shape[0], : pooled.shape[1]] = pooled
            pooled = padded

        levels.append(pooled.astype(np.float32))

    # --- make the coarsest level dense and non-NaN -------------------------------------
    coarsest = levels[-1]
    if np.isnan(coarsest).all():
        coarsest = np.zeros_like(coarsest)
    elif np.isnan(coarsest).any():
        coarsest = _sweep_fill(coarsest)

    levels[-1] = coarsest

    # --- walk back down, filling from the parent ---------------------------------------
    for index in range(len(levels) - 2, -1, -1):
        fine = levels[index]
        coarse = levels[index + 1]

        ups = coarse.repeat(2, axis=0).repeat(2, axis=1)
        ups = ups[: fine.shape[0], : fine.shape[1]]

        missing = np.isnan(fine)
        if missing.any():
            fine = np.where(missing, ups, fine)
            # Anything the parent still could not answer (only possible on odd edges).
            if np.isnan(fine).any():
                fine = _sweep_fill(fine)

        levels[index] = fine

    return levels[0]


def _sweep_fill(grid: Any, max_passes: int = 32) -> Any:
    """
    Last-resort gap filler: a bounded number of dilation passes that propagate already-known
    values outward.  Only used for tiny residual holes, so the pass count stays small.
    """
    result = grid.astype(np.float32).copy()
    known = ~np.isnan(result)

    if not known.any():
        return np.zeros_like(result)

    result[~known] = 0.0

    for _ in range(max_passes):
        if known.all():
            break

        source = result.copy()
        source_known = known.copy()

        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            shifted_values = np.roll(source, shift, axis=axis)
            shifted_known = np.roll(source_known, shift, axis=axis)
            targets = (~known) & shifted_known
            if targets.any():
                result[targets] = shifted_values[targets]
                known = known | targets

    if not known.all():
        # Give up gracefully: the mean is a safe value.
        result[~known] = float(result[known].mean()) if known.any() else 0.0

    return result


def _smooth(grid: Any, iterations: int = 1) -> Any:
    """
    Separable 3x3 box blur, with edge clamping (not wraparound) so map borders do not smear across
    from the opposite side.  The output always has exactly the same shape as the input.

    Both passes are written explicitly rather than chained through `np.pad` results, because two
    earlier versions sliced the wrong axis after padding and returned (h-2, w) or (h, w+2).  The
    shape damage was invisible while every caller fed the result through `_as_square`, which crops
    silently; it only became a hard error once two grids of different shapes were blended.
    """
    result = grid.astype(np.float32)

    for _ in range(iterations):
        # Horizontal: average along the column axis, padding width by one on each side.
        padded = np.pad(result, ((0, 0), (1, 1)), mode="edge")
        horizontal = (
            padded[:, :-2] + padded[:, 1:-1] + padded[:, 2:]
        ) / 3.0

        # Vertical: average along the row axis, padding height by one on each side.
        padded = np.pad(horizontal, ((1, 1), (0, 0)), mode="edge")
        result = (
            padded[:-2, :] + padded[1:-1, :] + padded[2:, :]
        ) / 3.0

    return result
def _as_square(grid: Any, size: int) -> Any:
    """
    Force a 2-D array to exactly size x size.

    Crops when too large, edge-pads when too small.  The terrain heightmap has to be exactly
    square: a rectangular one makes the .ter height section the wrong length, shifting the layer
    map and material list and corrupting the file.  It still loads, but the terrain material
    resolves to WARNING_MATERIAL and the layer map reads as garbage.

    The mip pyramid in _fill_gaps can return a slightly rectangular array, so every grid is
    passed through here.
    """
    height, width = grid.shape[:2]
    if height > size:
        grid = grid[:size, :]
        height = size
    if width > size:
        grid = grid[:, :size]
        width = size
    if height < size or width < size:
        grid = np.pad(
            grid, ((0, max(0, size - height)), (0, max(0, size - width))), mode='edge'
        )
    return grid


def _resample(grid: Any, size: int) -> Any:
    """Nearest-neighbour upscale to the requested heightmap resolution."""
    source = grid.shape[0]
    if source == size:
        return grid
    indices = (np.arange(size) * (source / size)).astype(np.int32)
    indices = np.clip(indices, 0, source - 1)
    return grid[np.ix_(indices, indices)]


TERRAIN_FILE_VERSION = 9


def write_ter_file(path: str, terrain: Terrain, material_names: Sequence[str]) -> int:
    """
    Write the binary .ter file BeamNG actually loads.

    Layout (little-endian), per the official Terrain Files reference:

        u8   version
        u32  size                          (heightmap resolution, power of two)
        u16  heightMap[size * size]
        u8   layerMap[size * size]         which material each cell uses
        u32  materialCount
        ...  materialCount names, each u8 length prefix + UTF-8 bytes

    Verified arithmetically against polish_roads_v2's `theTerrainrr.ter` (12,583,231 bytes,
    version 9, size 2048):

        5 + size^2*2 + size^2 + 4 + name bytes  =  12,583,231   exactly

    There is NO `layerTextureMap` array, despite what `.terrain.json`'s `binaryFormat` string
    claims.  With one it would need 4,194,304 more bytes than the file has, so version 9 does not
    store one; the descriptive string is simply wrong.  Names are length-prefixed, not
    NUL-terminated -- the name block contains no NUL byte, and a 4-byte count plus length-prefixed
    names consumes it to the byte.
    """
    if not material_names:
        material_names = ["grass"]

    os.makedirs(os.path.dirname(path), exist_ok=True)

    # A rectangular heightmap makes the height section the wrong length, which shifts the
    # layer map and material list and corrupts the file.  Fail loudly rather than ship that.
    if terrain.heights.shape != (terrain.size, terrain.size):
        raise ValueError(
            f"heightmap must be square ({terrain.size}x{terrain.size}), got {terrain.heights.shape}"
        )
    if terrain.layers.shape != (terrain.size, terrain.size):
        raise ValueError(
            f"layer map must be square ({terrain.size}x{terrain.size}), got {terrain.layers.shape}"
        )

    height_bytes = np.ascontiguousarray(terrain.heights, dtype="<u2").tobytes()
    layer_bytes = np.ascontiguousarray(terrain.layers, dtype=np.uint8).tobytes()

    # Names are length-prefixed, not NUL-terminated: the real name block contains no NUL byte at
    # all, and this encoding consumes it exactly.
    name_block = bytearray()
    for name in material_names:
        encoded = name.encode("utf-8")[:255]
        name_block.append(len(encoded))
        name_block += encoded

    with open(path, "wb") as handle:
        handle.write(struct.pack("<B", TERRAIN_FILE_VERSION))
        handle.write(struct.pack("<I", int(terrain.size)))
        handle.write(height_bytes)
        handle.write(layer_bytes)
        handle.write(struct.pack("<I", len(material_names)))
        handle.write(bytes(name_block))

    expected = 5 + terrain.size * terrain.size * 3 + 4 + len(name_block)
    actual = os.path.getsize(path)
    if actual != expected:
        raise ValueError(
            f".ter is {actual} bytes but version 9 layout requires {expected} "
            f"(difference {expected - actual})"
        )

    return actual


def png_pixel_size(path: str) -> Optional[int]:
    """
    Read a PNG's width from its IHDR chunk.

    Used to size the TerrainMaterialTextureSet from the texture files themselves, because the
    engine packs the group into a square array of that many pixels.
    """
    try:
        with open(path, "rb") as handle:
            header = handle.read(24)
    except OSError:
        return None

    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None

    width, height = struct.unpack(">II", header[16:24])
    return width if width == height else None


def write_png_gray8(path: str, pixels: Any) -> None:
    """Write an 8-bit greyscale PNG without Pillow (pure zlib + struct)."""
    height, width = pixels.shape
    raw = bytearray()
    for row in range(height):
        raw.append(0)  # filter type 0 (None)
        raw.extend(pixels[row].tobytes())

    _write_png(path, width, height, 0, raw)


def write_png_rgb(path: str, pixels: Any) -> None:
    """Write an 8-bit RGB PNG without Pillow."""
    height, width, _channels = pixels.shape
    raw = bytearray()
    for row in range(height):
        raw.append(0)
        raw.extend(pixels[row].tobytes())

    _write_png(path, width, height, 2, raw)


def _write_png(path: str, width: int, height: int, color_type: int, raw: bytearray) -> None:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    with open(path, "wb") as handle:
        handle.write(b"\x89PNG\r\n\x1a\n")
        handle.write(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)))
        handle.write(chunk(b"IDAT", zlib.compress(bytes(raw), 9)))
        handle.write(chunk(b"IEND", b""))


def _value_noise(size: int, cells: int, seed: int) -> Any:
    """Cheap value noise, bilinearly upsampled -- enough for a ground texture."""
    rng = np.random.default_rng(seed)
    grid = rng.random((cells + 1, cells + 1)).astype(np.float32)

    ys = np.linspace(0, cells, size, endpoint=False)
    xs = np.linspace(0, cells, size, endpoint=False)
    x0 = xs.astype(np.int32)
    y0 = ys.astype(np.int32)
    fx = (xs - x0)[None, :]
    fy = (ys - y0)[:, None]

    v00 = grid[np.ix_(y0, x0)]
    v10 = grid[np.ix_(y0, x0 + 1)]
    v01 = grid[np.ix_(y0 + 1, x0)]
    v11 = grid[np.ix_(y0 + 1, x0 + 1)]

    top = v00 + (v10 - v00) * fx
    bottom = v01 + (v11 - v01) * fx
    return top + (bottom - top) * fy


def make_terrain_texture(size: int = 512) -> Any:
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


# ==========================================================================================
#  5.  THE BEAMNG LEVEL BUILDER
# ==========================================================================================

IDENTITY_ROTATION = [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0]
ITEMS_PER_GROUP_FILE = 1000


def new_id() -> str:
    import uuid

    return str(uuid.uuid4())


def sanitize_identifier(name: str, fallback: str = "cs1level") -> str:
    """BeamNG level folder names: keep it simple and filesystem-safe."""
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    )
    cleaned = re.sub(r"[^A-Za-z0-9_]+", "_", ascii_name).strip("_")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = fallback + ("_" + cleaned if cleaned else "")
    return cleaned




def make_building_dae(name: str, shape: str, material: str) -> str:
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

    # The material MUST be bound here.  TSStatic takes its materials from the shape's material
    # list, matched to Material definitions by name, so `materialName` on the TSStatic itself is
    # ignored and an unbound shape draws in the engine's warning material.
    symbol = f"{material}-material"

    return f"""<?xml version="1.0" encoding="utf-8"?>
<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">
  <asset>
    <contributor><authoring_tool>CS1-to-BeamNG</authoring_tool></contributor>
    <unit meter="1" name="meter"/>
    <up_axis>Z_UP</up_axis>
  </asset>
  <library_effects>
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
        <polylist material="{symbol}" count="{len(faces)}">
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
        <instance_geometry url="#{name}-mesh">
          <bind_material>
            <technique_common>
              <instance_material symbol="{symbol}" target="#{symbol}"/>
            </technique_common>
          </bind_material>
        </instance_geometry>
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



# ==========================================================================================
#  Terrain material -- taken from an ENGINE level; no material authored, no texture copied
# ==========================================================================================
#
# There is no global terrain material library in BeamNG: a terrain material is always declared per
# level, in `levels/<level>/art/terrains/main.materials.json`.  Fifteen shipped levels provide one,
# and three of them -- east_coast_usa, west_coast_usa and Utah -- already use the arrangement that
# matters: five base textures inside the level and ten from the engine's own library.
#
# One such material is reproduced below.  Its five local texture references are rewritten to the
# same engine level they came from, so all fifteen slots resolve to built-in content:
#
#     base    /levels/east_coast_usa/art/terrains/...   (engine level, referenced in place)
#     detail  /assets/materials/terrain/...             (engine library)
#     macro   /assets/materials/terrain/...             (engine library)
#
# Cross-level texture references are proven to work: polish_roads_v2 references ten textures inside
# east_coast_usa and its ground renders.
# ==========================================================================================

CS1_TERRAIN_SOURCE_LEVEL = "east_coast_usa"

CS1_TERRAIN_MATERIAL = {
    "class": "TerrainMaterial",
    "internalName": "Grass",
    "groundmodelName": "GRASS",
    "annotation": "GRASS",
    "diffuseSize": 2048,
    "detailSize": 4,
    "macroSize": 50,
    "detailStrength": 0.5,
    "macroStrength": 0.3,
    "detailDistance": 25,
    "macroDistance": 1000,
    "detailDistAtten": [0, 1],
    "macroDistAtten": [0.35, 1],
    "detailDistances": [0, 0, 20, 40],
    "macroDistances": [0, 0, 60, 300],
    "baseColorDetailStrength": [0.4, 0.45],
    "normalDetailStrength": [1, 0.3],
    "roughnessDetailStrength": [0, 0],
    "baseColorMacroStrength": [0, 0.1],
    "normalMacroStrength": [0.5, 0.5],
    "roughnessMacroStrength": [0.2, 0.4],
    "baseColorBaseTex": "/assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_b.png",
    "baseColorBaseTexSize": 1.07,
    "normalBaseTex": "/assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_nm.png",
    "normalBaseTexSize": 1.07,
    "roughnessBaseTex": "/assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_r.png",
    "roughnessBaseTexSize": 1.07,
    "aoBaseTex": "/assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_ao.png",
    "aoBaseTexSize": 1.07,
    "heightBaseTex": "/assets/materials/terrain/forest/t_forest_ground_02/t_forest_ground_02_h.png",
    "heightBaseTexSize": 1.07,
    "baseColorMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_b.png",
    "baseColorMacroTexSize": 3,
    "normalMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_nm.png",
    "normalMacroTexSize": 3,
    "roughnessMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_r.png",
    "roughnessMacroTexSize": 3,
    "aoMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_ao.png",
    "aoMacroTexSize": 3,
    "heightMacroTex": "/assets/materials/terrain/grass/macro_grass/t_macro_grass_h.png",
    "heightMacroTexSize": 3,
    "baseColorDetailTex": "/assets/materials/terrain/grass/t_grass_01/t_grass_01_b.png",
    "baseColorDetailTexSize": 0.35,
    "normalDetailTex": "/assets/materials/terrain/grass/t_grass_01/t_grass_01_nm.png",
    "normalDetailTexSize": 0.35,
    "roughnessDetailTex": "/assets/materials/terrain/grass/t_grass_01/t_grass_01_r.png",
    "roughnessDetailTexSize": 0.35,
    "aoDetailTex": "/assets/materials/terrain/grass/t_grass_01/t_grass_01_ao.png",
    "aoDetailTexSize": 0.35,
    "heightDetailTex": "/assets/materials/terrain/grass/t_grass_01/t_grass_01_h.png",
    "heightDetailTexSize": 0.35,
}


# ==========================================================================================
#  Asphalt terrain material -- the road surface
# ==========================================================================================
#
# Derived from the grass material so every field a working material declares is present.  Only the
# identity, the physics link and the fifteen texture paths differ.
#
# `groundmodelName: "ASPHALT"` is the important one: it is what makes the painted road surface grip
# like a road.  The level's `groundModels/surfaces.json` overrides that model with firm coefficients.
#
# Textures are the engine's built-in asphalt terrain sets.
ASPHALT_BASE = "/assets/materials/terrain/asphalt/t_asphalt_02"
ASPHALT_MACRO = "/assets/materials/terrain/asphalt/macro_asphalt"
ASPHALT_DETAIL = "/assets/materials/terrain/asphalt/t_asphalt_02"

CS1_ASPHALT_MATERIAL = dict(CS1_TERRAIN_MATERIAL)
CS1_ASPHALT_MATERIAL.update({
    "internalName": "Asphalt",
    "annotation": "ASPHALT",
    "groundmodelName": "ASPHALT",
    # Lifts the asphalt off near-black against the greener ground.
    "baseColorFactor": [1.35, 1.35, 1.35, 1],
    "baseColorBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_b.png",
    "normalBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_nm.png",
    "roughnessBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_r.png",
    "aoBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_ao.png",
    "heightBaseTex": f"{ASPHALT_BASE}/t_asphalt_02_h.png",
    "baseColorMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_b.png",
    "normalMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_nm.png",
    "roughnessMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_r.png",
    "aoMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_ao.png",
    "heightMacroTex": f"{ASPHALT_MACRO}/t_macro_asphalt_h.png",
    "baseColorDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_b.png",
    "normalDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_nm.png",
    "roughnessDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_r.png",
    "aoDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_ao.png",
    "heightDetailTex": f"{ASPHALT_DETAIL}/t_asphalt_02_h.png",
})

# `baseTexSize` is a REQUIRED pixel size: every texture in a family must match it or the engine
# discards the texture and packs a black layer.  All 213 PNGs in `content/assets/materials/
# terrain.zip` are 1024x1024 (38 complete sets, none larger), so 1024 is the only correct value for
# materials drawing from that archive.  The previous 2048 came from east_coast_usa, whose own
# `t_terrain_base_*` family is genuinely 2048 -- copying its material copied its required size too,
# and every grass texture was then rejected as the wrong size.
CS1_TERRAIN_TEXTURE_SET = {
    "class": "TerrainMaterialTextureSet",
    "baseTexSize": [1024, 1024],
    "detailTexSize": [1024, 1024],
    "macroTexSize": [1024, 1024],
}


def find_beamng_install() -> Optional[str]:
    """Locate the BeamNG install, for base-game shapes and terrain resources."""
    candidates = [
        os.environ.get("BEAMNG_PATH"),
        r"D:\SteamLibrary\steamapps\common\BeamNG.drive",
        r"C:\Program Files (x86)\Steam\steamapps\common\BeamNG.drive",
        r"C:\Program Files\Steam\steamapps\common\BeamNG.drive",
        r"E:\SteamLibrary\steamapps\common\BeamNG.drive",
        r"D:\Steam\steamapps\common\BeamNG.drive",
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(os.path.join(candidate, "BeamNG.drive.exe")):
            return candidate
    return None


# ==========================================================================================
#  Buildings -- base-game shapes referenced in place
# ==========================================================================================
#
# A shape is referenced, never copied.  A copied DAE keeps <instance_material> targets belonging to
# the SOURCE level's material library, which this mod does not ship, and the engine renders every
# instance as its "No Mesh" placeholder.  Referencing in place is what working maps do:
# polish_roads_v2 uses 208 shapes from Industrial, 15 from italy and 8 from derby that way.
BEAMNG_BUILDING_SOURCES = [
    ("ind_bld_8x8.dae", "levels/italy/art/shapes/buildings/ind_bld_8x8.dae", (8.20, 8.20, 5.73)),
    ("ind_bld_12x10.dae", "levels/italy/art/shapes/buildings/ind_bld_12x10.dae", (10.10, 12.10, 7.90)),
    ("ind_bld_12x15.dae", "levels/italy/art/shapes/buildings/ind_bld_12x15.dae", (15.20, 12.20, 12.55)),
    ("ind_bld_12x20.dae", "levels/italy/art/shapes/buildings/ind_bld_12x20.dae", (20.34, 12.75, 11.50)),
    ("ind_bld_12x24.dae", "levels/italy/art/shapes/buildings/ind_bld_12x24.dae", (24.08, 13.01, 18.72)),
    ("ind_bld_12x30.dae", "levels/italy/art/shapes/buildings/ind_bld_12x30.dae", (30.10, 12.11, 10.92)),
    ("ind_bld_24x60.dae", "levels/italy/art/shapes/buildings/ind_bld_24x60.dae", (60.27, 31.07, 17.14)),
]

# Ground-plane centre offset of each shape's mesh, in the shape's own x/z, measured from its
# Collada POSITION accessors.  The mesh origin is a CORNER of the bounding box, not its centre:
# ind_bld_8x8 spans 8.2 m in -X and 0.1 m in +X from its origin, and ind_bld_12x30 spans 30.2 m
# in -X.  Placing the TSStatic at the building's centre therefore puts the drawn mesh half a
# width to one side -- up to 15 m -- which is why buildings interpenetrated and stood where the
# collision was not.
#
# Applied as `position -= offset`, because the entry is the mesh's displacement from its origin.
#
# Only the Italy industrial shapes are listed.  The west_coast shapes measure at large arbitrary
# offsets (-844 m, -305 m) in a coordinate frame this measurement cannot resolve, so they are
# left alone rather than moved by a number known to be unreliable.
BEAMNG_SHAPE_CENTRE_OFFSET = {
    "ind_bld_12x10.dae": (-5.000, 0.352),
    "ind_bld_12x15.dae": (-7.500, 3.909),
    "ind_bld_12x20.dae": (-10.070, 3.704),
    "ind_bld_12x24.dae": (-12.000, 7.364),
    "ind_bld_12x30.dae": (-15.000, 1.839),
    "ind_bld_24x60.dae": (0.000, 5.569),
    "ind_bld_8x8.dae": (-4.000, 0.833),
}

BEAMNG_BUILDING_MODELS = [(member, size) for _n, member, size in BEAMNG_BUILDING_SOURCES]

# instanceColor tints repeated base-game shapes WITHOUT creating a material per variant.  Working
# maps vary thousands of instances this way.
BUILDING_INSTANCE_COLORS = {
    "Residential": [0.78, 0.76, 0.72, 1.0],
    "Commercial": [0.66, 0.72, 0.80, 1.0],
    "Industrial": [0.62, 0.60, 0.56, 1.0],
    "Office": [0.56, 0.64, 0.74, 1.0],
    "Beautification": [0.84, 0.82, 0.76, 1.0],
    "Electricity": [0.54, 0.54, 0.52, 1.0],
    "default": [0.74, 0.72, 0.68, 1.0],
}


def choose_beamng_model(width: float, depth: float, height: float):
    """
    Pick the base-game shape closest to this building; return (shapeName, model size, scale).

    The X/Y scale is UNIFORM so the mesh keeps its proportions.  Scaling axes independently to
    force a bounding box onto a footprint produced values like [2.64, 0.53, 1.00] and visibly
    deformed every building.  Models are never scaled above 1:1, so an instance can only occupy
    less than its own footprint -- never more, which is what let oversized props spill onto roads.
    """
    best = None
    for member, (mw, md, mh) in BEAMNG_BUILDING_MODELS:
        for swap in (False, True):
            model_w, model_d = (md, mw) if swap else (mw, md)
            aspect_error = abs((model_w / model_d) - (width / depth))
            size_error = abs(model_w - width) + abs(model_d - depth)
            cost = aspect_error * 8.0 + size_error
            if best is None or cost < best[0]:
                best = (cost, member, (mw, md, mh), swap)

    _cost, member, (mw, md, mh), swap = best
    model_w, model_d = (md, mw) if swap else (mw, md)

    fit = min(1.0, min(width / model_w, depth / model_d))
    vertical = max(height, 1.0) / mh
    return f"/{member}", (mw, md, mh), (fit, fit, max(fit, min(vertical, fit * 1.6)))


# ==========================================================================================
#  Roads
# ==========================================================================================

def extend_for_overlap(points: List[Vec3], overlap: float) -> List[Vec3]:
    """
    Extend a polyline past both ends along its own end directions, by `overlap` metres.

    Purpose: two decals that share an endpoint exactly still show a hairline seam, because each has
    its own edge.  A small overlap makes them genuinely cover each other at the join.

    `overlap` must stay small.  An earlier attempt extended junction ends by up to 12 m and made
    things worse, because chains meeting at a junction approach from different directions and
    extending both moves their ends apart.  At the sizes used here (about a metre) the extension
    tracks the road's own axis and closes the seam without displacing the join.
    """
    if len(points) < 2 or overlap <= 0.0:
        return points

    head, nxt = points[0], points[1]
    dx, dz = head.x - nxt.x, head.z - nxt.z
    length = math.hypot(dx, dz)
    if length < 1e-9:
        return points
    start = Vec3(head.x + dx / length * overlap, head.y, head.z + dz / length * overlap)

    tail, prev = points[-1], points[-2]
    dx, dz = tail.x - prev.x, tail.z - prev.z
    length = math.hypot(dx, dz)
    if length < 1e-9:
        return [start] + list(points[1:])
    end = Vec3(tail.x + dx / length * overlap, tail.y, tail.z + dz / length * overlap)

    return [start] + list(points[1:-1]) + [end]


# Distance kept between a building footprint and the edge of a road surface.
# Distance kept between a building footprint and the edge of a road surface.  Sized a little
# above the tightest case the conformance check measures, so the bounding-circle test passes.
BUILDING_ROAD_CLEARANCE = 2.5


def _point_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    """Shortest distance from a point to a line segment, in the ground plane."""
    dx, dy = bx - ax, by - ay
    length_sq = dx * dx + dy * dy
    if length_sq < 1e-12:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def road_segments(roads: Sequence["Road"], max_sagitta: float = 4.0) -> List[Tuple[float, float, float, float, float]]:
    """
    Flatten every road once into (ax, ay, bx, by, half_width) tuples.

    Precomputed because `road_clearance` is called per building: flattening 1,244 Beziers inside
    that loop would repeat the same work 1,463 times.
    """
    segments: List[Tuple[float, float, float, float, float]] = []
    for road in roads:
        half = max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0) * 0.5
        points = road.surface_polyline(max_sagitta)
        for i in range(len(points) - 1):
            p = points[i].beamng()
            q = points[i + 1].beamng()
            segments.append((p[0], p[1], q[0], q[1], half))
    return segments


def road_clearance(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
) -> float:
    """
    Distance from (x, y) to the nearest road EDGE, in metres.

    The road's own half-width is subtracted, so this is clearance to the drivable surface rather
    than to its centre-line.  Returns infinity when there are no segments, so callers can treat
    that as "unconstrained" without a special case.
    """
    if not segments:
        return float("inf")

    best = float("inf")
    for ax, ay, bx, by, half in segments:
        edge = _point_to_segment(x, y, ax, ay, bx, by) - half
        if edge < best:
            best = edge
            if best <= 0.0:
                # Already overlapping a road; no need to look further.
                return best
    return best


# A building whose centre is inside a road is pushed out by at most this much.  Beyond it the
# building is left alone rather than moved somewhere arbitrary.
BUILDING_MAX_PUSH = 40.0


def _nearest_edge(x: float, y: float, segments: Sequence[Tuple[float, float, float, float, float]]) -> float:
    """Distance from (x, y) to the nearest road EDGE; used only to choose a push direction."""
    best = float("inf")
    for ax, ay, bx, by, half in segments:
        edge = _point_to_segment(x, y, ax, ay, bx, by) - half
        if edge < best:
            best = edge
    return best


def push_out_of_road(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
    needed: float,
    max_push: float = BUILDING_MAX_PUSH,
) -> Optional[Tuple[float, float]]:
    """
    Nudge a point out of the nearest road corridor, returning the new (x, y) or None.

    `needed` is how far the point must end up from the nearest road EDGE.  The push direction is
    away from the nearest centre-line, which is the shortest way out.  Returns None when the point
    is already clear, when no road is near, or when the required push exceeds `max_push` -- a
    building embedded that deeply should keep its CS1 position rather than be flung elsewhere.
    """
    if not segments:
        return None

    best_edge = float("inf")
    best_point = None
    best_segment = None
    for ax, ay, bx, by, half in segments:
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq < 1e-12:
            cx, cy = ax, ay
        else:
            t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / length_sq))
            cx, cy = ax + dx * t, ay + dy * t
        edge = math.hypot(x - cx, y - cy) - half
        if edge < best_edge:
            best_edge = edge
            best_point = (cx, cy)
            best_segment = (ax, ay, bx, by, half)

    if best_point is None or best_edge >= needed:
        return None

    distance = needed - best_edge
    if distance > max_push:
        return None

    # Direction away from the centre-line.
    vx, vy = x - best_point[0], y - best_point[1]
    length = math.hypot(vx, vy)

    if length < 1e-3:
        # The point lies ON the centre-line, so "away" is undefined.  Use the segment normal, which
        # is well defined and is the shortest way out.  Measured case: a "Road Connection" prefab
        # centred exactly on the centre-line of a 28 m road, where the offset was 0.0000 m.
        ax, ay, bx, by, _half = best_segment
        sx, sy = bx - ax, by - ay
        seg_len = math.hypot(sx, sy)
        if seg_len < 1e-9:
            return None
        nx, ny = -sy / seg_len, sx / seg_len

        # Either side may be blocked by another carriageway, so take whichever ends up clearer.
        candidates = [
            (x + nx * distance, y + ny * distance),
            (x - nx * distance, y - ny * distance),
        ]
        return max(candidates, key=lambda p: _nearest_edge(p[0], p[1], segments))

    vx, vy = vx / length, vy / length
    return (x + vx * distance, y + vy * distance)


def push_out_of_road_iterative(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
    needed: float,
    max_push: float = BUILDING_MAX_PUSH,
    max_steps: int = 6,
) -> Optional[Tuple[float, float]]:
    """
    Repeatedly nudge a point until it clears the roads, or stop once it stops improving.

    A single step is not reliable -- measured on one building it moved 7.969 m in a direction that
    left the footprint 4.17 m inside the road it was moving away from.  Repeating the step corrects
    that, and stopping as soon as progress stalls prevents oscillation for a building boxed in on
    every side.
    """
    if not segments:
        return None

    cx, cy = x, y
    moved_any = False
    best = _nearest_edge(cx, cy, segments)
    if best >= needed:
        return None

    for _ in range(max_steps):
        step = push_out_of_road(cx, cy, segments, needed, max_push)
        if step is None:
            break
        new_edge = _nearest_edge(step[0], step[1], segments)
        if new_edge <= best + 1e-6:
            break
        cx, cy = step
        best = new_edge
        moved_any = True
        if best >= needed:
            break

    return (cx, cy) if moved_any else None


def roads_as_segments(roads: Sequence["Road"], max_sagitta: float = 0.5) -> List[Dict[str, Any]]:
    """
    One record per source segment, in the same shape `chain_roads` produces.

    Neighbouring segments share a node, and `surface_polyline` snaps each segment's first and last
    point to that node, so adjacent decals terminate on exactly the same coordinate.  Joins are
    therefore exact at every segment boundary rather than only at the ends of a chain.

    A segment's own width is used, so a wide road and a narrow one meeting at a node keep their
    distinct widths instead of both taking the widest value in the chain.
    """
    entries: List[Dict[str, Any]] = []
    for road in roads:
        points = extend_for_overlap(road.surface_polyline(max_sagitta), ROAD_DECAL_OVERLAP)
        if len(points) < 2:
            continue
        entries.append({
            "points": points,
            "width": max(float(getattr(road, "measured_width", 0.0) or 0.0), 1.0),
            "material": material_for(road),
            "source": road,
            "segments": 1,
        })
    return entries


def chain_roads(roads: Sequence["Road"], max_sagitta: float = 0.5) -> List[Dict[str, Any]]:
    """
    Join road segments that share a node into continuous centre-lines.

    The export holds one segment per CS1 road piece and CS1 splits the network finely -- 780 of
    1244 segments are bare two-node stubs.  One DecalRoad each therefore leaves a gap at every
    boundary, because each decal fades in and out at its own ends.

    A node touched by three or more segments is a junction and chains are cut there, so each
    incoming road ends cleanly instead of several overlapping and stacking their fades.  Every
    segment is consumed exactly once, so no stretch is drawn twice.
    """
    if not roads:
        return []

    incident: Dict[int, List[Tuple[int, str]]] = {}
    for index, road in enumerate(roads):
        incident.setdefault(road.start_node_id, []).append((index, "start"))
        incident.setdefault(road.end_node_id, []).append((index, "end"))

    junction_nodes = {node for node, uses in incident.items() if len(uses) >= 3}
    used = [False] * len(roads)

    def polyline_of(road: "Road") -> List[Vec3]:
        return list(road.surface_polyline(max_sagitta))

    chains: List[Dict[str, Any]] = []
    order = sorted(
        range(len(roads)),
        key=lambda i: (
            0 if (roads[i].start_node_id in junction_nodes
                  or roads[i].end_node_id in junction_nodes) else 1,
            i,
        ),
    )

    for seed in order:
        if used[seed]:
            continue
        seed_road = roads[seed]
        used[seed] = True
        members = [seed]
        chain = polyline_of(seed_road)

        for direction in ("end", "start"):
            node_id = seed_road.end_node_id if direction == "end" else seed_road.start_node_id
            while node_id not in junction_nodes:
                candidates = [(i, e) for i, e in incident.get(node_id, []) if not used[i]]
                if len(candidates) != 1:
                    break
                idx, entered_by = candidates[0]
                nxt = roads[idx]
                used[idx] = True
                members.append(idx)

                pts = polyline_of(nxt)
                if entered_by == "start":
                    oriented = pts
                    node_id = nxt.end_node_id
                else:
                    oriented = list(reversed(pts))
                    node_id = nxt.start_node_id

                if direction == "end":
                    if chain and oriented and oriented[0].distance_to(chain[-1]) < 0.05:
                        oriented = oriented[1:]
                    chain.extend(oriented)
                else:
                    if chain and oriented and oriented[-1].distance_to(chain[0]) < 0.05:
                        oriented = oriented[:-1]
                    chain = oriented + chain

        if len(chain) < 2:
            continue

        widest = max(roads[i].measured_width for i in members)

        # Chains end EXACTLY at their junction node, and that is deliberate.  An earlier version
        # pushed each end outward along the chain's own direction to force overlap; measured on the
        # built archive that left ZERO coincident endpoint locations, because at a junction the
        # meeting chains approach from different directions and extending both moves their ends
        # APART -- up to 24 m at a right angle.  Overshooting only helps two collinear segments,
        # which is not what a junction is.
        representative = roads[max(members, key=lambda i: roads[i].measured_width)]
        chains.append({
            "points": chain,
            "width": widest,
            "material": material_for(representative),
            "source": representative,
            "segments": len(members),
        })

    return chains


# ==========================================================================================
#  Window materials for the base-game building shapes
# ==========================================================================================
#
# Several shipped building shapes declare materials whose textures live in their own level's
# archive.  Referenced from another level those textures do not resolve, and the windows render as
# a pale untextured strip -- visible as "no material" boxes in game.
#
# The engine ships window materials as global content inside `content/art_shapes.zip`, mounted for
# every level:
#
#     /art/shapes/objects/m_windows_glass_01/          lit windows, emissive at night
#     /art/shapes/objects/m_transparent_glass_window/  clear-coated glass
#     /art/shapes/objects/windows_doors_reflective/    reflective glazing
#
# The entries below create NO new material.  Each is a one-line redirect: the name a building shape
# asks for, aliased via `mapTo` to the engine's own glass material.  Anything not listed keeps the
# shape's original assignment.
# ==========================================================================================
# Names the base-game building shapes ask for.  They are declared inside italy's own archive, so
# they do not resolve from another level -- which is why the windows rendered as "NO-MATERIAL".
BUILDING_WINDOW_NAMES = [
    "Italy_bld_ind_windows",
    "italy_bld_windows",
]

# The built-in material these are modelled on.  It is complete in this install: its textures are
# `.link` files redirecting to real `.dds` images in `atlas.zip`.
# Real on-disk location of the glazing textures.  These ship as .dds in tlas.zip; the
# .link stubs in rt_shapes.zip point at the same images under a .png name, but the .dds
# entries are the ones actually present, so they are referenced directly.
WINDOW_TEXTURES = "/assets/materials/atlas/windows_doors_reflective"


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
                    "baseColorMap": f"{WINDOW_TEXTURES}/t_windows_doors_reflective_b.color.dds",
                    "normalMap": f"{WINDOW_TEXTURES}/t_windows_doors_reflective_nm.normal.dds",
                    "roughnessMap": f"{WINDOW_TEXTURES}/t_windows_doors_reflective_r.data.dds",
                    "ambientOcclusionMap": f"{WINDOW_TEXTURES}/t_windows_doors_reflective_ao.data.dds",
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

# ==========================================================================================
#  Building-derived road generation
# ==========================================================================================
#
# Used when `--roads-from-buildings` is passed.  See the module docstring of
# tools/dump/derive_roads_from_buildings.py for the reasoning; the short version is that a CS1
# building was placed against a road, so building positions imply where streets run.
# ==========================================================================================

# How far each road decal is extended past its own ends, so neighbouring decals overlap instead of
# merely touching.  Deliberately small: this closes a hairline seam, it does not bridge a junction.
# Raise it if gaps persist, lower it if roads look bloated at their joins.
ROAD_DECAL_OVERLAP = 1.75

ROAD_FROM_BUILDINGS_LINK = 55.0     # metres: max gap between two buildings still joined by a street
ROAD_FROM_BUILDINGS_WIDTH = 8.0     # metres: a two-lane street


def derive_roads_from_buildings(
    buildings: Sequence["Building"],
    link_distance: float = ROAD_FROM_BUILDINGS_LINK,
    width: float = ROAD_FROM_BUILDINGS_WIDTH,
    max_degree: int = 3,
) -> List[Dict[str, Any]]:
    """
    Build a road network from building positions, returning chain dicts shaped like `chain_roads`.

    Each building is joined to its nearest few neighbours within `link_distance`.  `max_degree`
    keeps the result from becoming a spiderweb: without it, dense clusters produce quadratic numbers
    of near-duplicate links that all overlap on the ground.
    """
    if len(buildings) < 2:
        return []

    # Work in CS1 space.  `Vec3` holds CS1 coordinates and `beamng()` performs the conversion, so
    # converting here would convert twice and collapse the network.  The ground plane is CS1 (x, z):
    # x is east/west and z is north/south; CS1 y is elevation, which the terrain supplies later.
    centres = []
    for b in buildings:
        centres.append((b.position.x, b.position.z, b))

    # Uniform grid index, so neighbour lookup does not compare every pair against every other.
    cell = max(link_distance, 1.0)
    grid: Dict[Tuple[int, int], List[int]] = {}
    for index, (bx, by, _b) in enumerate(centres):
        grid.setdefault((int(bx // cell), int(by // cell)), []).append(index)

    link_sq = link_distance * link_distance
    pairs: List[Tuple[float, int, int]] = []
    for index, (bx, by, _b) in enumerate(centres):
        cx, cy = int(bx // cell), int(by // cell)
        for gx in (cx - 1, cx, cx + 1):
            for gy in (cy - 1, cy, cy + 1):
                for other in grid.get((gx, gy), ()):
                    if other <= index:
                        continue
                    ox, oy, _ob = centres[other]
                    d2 = (ox - bx) ** 2 + (oy - by) ** 2
                    if d2 <= link_sq:
                        pairs.append((d2, index, other))

    pairs.sort()
    degree: Dict[int, int] = {}
    chosen: List[Tuple[int, int]] = []
    for _d2, a, b in pairs:
        if degree.get(a, 0) >= max_degree or degree.get(b, 0) >= max_degree:
            continue
        degree[a] = degree.get(a, 0) + 1
        degree[b] = degree.get(b, 0) + 1
        chosen.append((a, b))

    chains: List[Dict[str, Any]] = []
    for a, b in chosen:
        ax, ay, ab = centres[a]
        bx, by, bb = centres[b]

        # A slight perpendicular bow so consecutive streets are not all dead straight.
        mx, my = (ax + bx) * 0.5, (ay + by) * 0.5
        dx, dy = bx - ax, by - ay
        length = math.hypot(dx, dy) or 1.0
        bow = min(length * 0.06, 3.0)
        mx += -dy / length * bow
        my += dx / length * bow

        # CS1-space Vec3s: x = east/west, z = north/south ground plane, y = elevation (left at 0
        # and replaced by the terrain surface when the road is emitted).
        start = Vec3(ax, 0.0, ay)
        control = Vec3(mx, 0.0, my)
        end = Vec3(bx, 0.0, by)

        # Quadratic bezier flattened to a few points.
        points: List[Vec3] = []
        steps = max(2, int(length / 12.0))
        for s in range(steps + 1):
            t = s / steps
            u = 1.0 - t
            px = u * u * start.x + 2 * u * t * control.x + t * t * end.x
            pz = u * u * start.z + 2 * u * t * control.z + t * t * end.z
            points.append(Vec3(px, 0.0, pz))

        chains.append({
            "points": points,
            "width": width,
            "material": "road_asphalt_2lane",
            # No source Road: this chain was not derived from one, so one_way is False.
            "source": None,
            "segments": 1,
        })

    return chains


# ==========================================================================================
#  Ground models -- physical surface behaviour
# ==========================================================================================
#
# Terrain friction is not set by the terrain material's textures: it is set by
# `TerrainMaterial.groundmodelName`, which is resolved against the engine's `/art/groundmodels.json`
# and then merged with any `levels/<level>/groundModels/*.json`.
#
# `groundmodelName` values this level uses are GRASS and ASPHALT.  Stock grass has low friction,
# which is why the whole map drove like loose gravel, so both are overridden at level scope.
#
# Values follow the documented meaning: `staticFrictionCoefficient` is grip before sliding,
# `slidingFrictionCoefficient` while sliding, and sliding is kept below static.
GROUND_MODELS = {
    "grass": {
        "staticFrictionCoefficient": 0.95,
        "slidingFrictionCoefficient": 0.85,
        "roughnessCoefficient": 0.02,
        "hydrodynamicFriction": 0.005,
        "strength": 1.0,
        "collisiontype": "GRASS",
        "skidMarks": False,
        "defaultDepth": 0.0,
        "shearStrength": 0.0,
    },
    "asphalt": {
        "staticFrictionCoefficient": 1.10,
        "slidingFrictionCoefficient": 1.00,
        "roughnessCoefficient": 0.0,
        "hydrodynamicFriction": 0.01,
        "strength": 1.0,
        "collisiontype": "ASPHALT",
        "skidMarks": True,
        "defaultDepth": 0.0,
        "shearStrength": 0.0,
    },
}


def build_ground_models() -> Dict[str, Any]:
    """The level's `groundModels/*.json` payload."""
    return {name: dict(body) for name, body in GROUND_MODELS.items()}


# ==========================================================================================
#  Custom terrain colour texture
# ==========================================================================================
#
# A level normally ships a large colour texture for its terrain base layer -- polish_roads_v2's is a
# 2048 m satellite photograph of its own map.  A converter has no such image, and every terrain
# texture the engine ships measures near-neutral grey (the greenest has a green bias of +15), so the
# ground could not be made green from built-in content.  This uses a supplied grass image instead.
#
# `custom_terrain_texture` is written to `levels/<level>/art/terrains/` and referenced from the
# material's `baseColorBaseTex`.  Normal, roughness, ao and height stay on the engine's set: those
# modulate whatever colour sits underneath, which is how the engine's own materials are built.
CUSTOM_TERRAIN_TEXTURE_NAME = "t_grass_ground_b.png"
CUSTOM_TERRAIN_TEXTURE_SIZE = 1024
CUSTOM_TERRAIN_TEXTURE_SOURCE = "textures/grass.jpg"


def convert_custom_terrain_texture(source_path: str, destination_path: str, size: int) -> Optional[str]:
    """
    Convert a supplied ground image into the terrain colour texture the level ships.

    Squared and resized to a power of two because `baseTexSize` declares a REQUIRED size and the
    engine discards any texture that does not match it -- a rule that cost several rounds here.
    Returns the destination path, or None if the source is missing or unreadable, so a level can
    still be built without it.
    """
    if not os.path.isfile(source_path):
        return None

    try:
        from PIL import Image
    except ImportError:
        return None

    try:
        with Image.open(source_path) as image:
            image = image.convert("RGB")
            # Centre-crop to a square so the texture does not stretch.
            width, height = image.size
            edge = min(width, height)
            left = (width - edge) // 2
            top = (height - edge) // 2
            image = image.crop((left, top, left + edge, top + edge))
            image = image.resize((size, size), Image.LANCZOS)

            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            image.save(destination_path, format="PNG")
        return destination_path
    except Exception:
        return None


# ==========================================================================================
#  Level builder
# ==========================================================================================

class BeamNGLevelBuilder:
    def __init__(
        self,
        layout: CityLayout,
        output_root: str,
        level_name: str,
        mod_name: str,
        max_width: float = 6.0,
        include_non_drivable: bool = False,
        with_terrain: bool = True,
        heightmap_size: int = 2048,
        max_sagitta: float = 0.5,
        roads_from_buildings: bool = False,
        chain_roads_enabled: bool = False,
    ) -> None:
        self.layout = layout
        self.output_root = output_root
        self.level_name = level_name
        self.mod_name = mod_name
        self.max_width = max_width
        self.include_non_drivable = include_non_drivable
        self.with_terrain = with_terrain
        self.heightmap_size = heightmap_size
        self.max_sagitta = max_sagitta
        # When set, the CS1 road geometry is discarded and streets are derived from the buildings
        # instead.  See `derive_roads_from_buildings`.
        self.roads_from_buildings = roads_from_buildings
        # When False, one decal is emitted per source segment instead of chaining segments into
        # long polylines.  See `roads_as_segments`.
        self.chain_roads_enabled = chain_roads_enabled

        self.mod_root = os.path.join(output_root, mod_name)
        self.level_root = os.path.join(self.mod_root, "levels", level_name)
        self.main_root = os.path.join(self.level_root, "main")

        self.roads: List[Road] = []
        self.buildings: List[Building] = []
        self.terrain: Optional[Terrain] = None
        self.terrain_block: Optional[Dict[str, Any]] = None
        self.sky_objects: List[Dict[str, Any]] = []

        # The engine's own material name is kept; nothing is renamed or authored.
        self.terrain_materials: List[str] = [CS1_TERRAIN_MATERIAL["internalName"]]
        self.texture_set_name = f"{level_name}TerrainMaterialTextureSet"
        self.terrain_texture_base_size = int(CS1_TERRAIN_TEXTURE_SET["baseTexSize"][0])

        self.report: Dict[str, Any] = {
            "levelName": level_name,
            "modName": mod_name,
            "roadsConverted": 0,
            "roadsSkipped": 0,
            "roadsSkippedByClass": {},
            "buildingsConverted": 0,
            "decalRoadNodes": 0,
            "materials": {},
            "files": [],
            "warnings": [],
        }

    # ---------------------------------------------------------------- primitives
    def write_json(self, path: str, payload: Any) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def write_lines(self, path: str, objects: Iterable[Dict[str, Any]]) -> None:
        """
        Write a line-delimited items.level.json -- one COMPLETE object per physical line.

        Not cosmetic: the engine parses these one line at a time, and an object that wraps makes it
        reject the entire file with `Unable to deserialize file ...` while reporting nothing else.
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as handle:
            for obj in objects:
                handle.write(json.dumps(obj, separators=(",", ":"), ensure_ascii=False))
                handle.write("\n")
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def _emit_grouped(self, objects, group: str, container: str) -> List[str]:
        """
        Write objects into <container>/<group>/items.level.json.

        Objects go DIRECTLY in the folder named after their group, parented to that same name.
        Measured on polish_roads_v2: `Dworzec_traffic/items.level.json` holds 38 DecalRoads all
        parented to `Dworzec_traffic`; `DynamicLights` holds 1201 lights parented to
        `DynamicLights`.

        An object whose `__parent` does not name the group owning its folder is dropped silently --
        no log line at all.  That is what left the Roads folder empty while the geometry parsed
        cleanly.
        """
        written: List[str] = []
        if not objects:
            return written

        group_root = os.path.join(self.main_root, container, group)
        os.makedirs(group_root, exist_ok=True)

        for obj in objects:
            obj["__parent"] = group

        path = os.path.join(group_root, "items.level.json")
        self.write_lines(path, objects)
        written.append(os.path.relpath(path, self.mod_root))

        for name in os.listdir(group_root):
            candidate = os.path.join(group_root, name)
            if os.path.isdir(candidate):
                shutil.rmtree(candidate, ignore_errors=True)

        return written

    # ---------------------------------------------------------------- content
    def select_content(self) -> None:
        self.roads = [r for r in self.layout.roads if is_drivable(r)]
        skipped = [r for r in self.layout.roads if not is_drivable(r)]
        self.buildings = list(self.layout.buildings)

        by_class: Counter = Counter()
        for road in skipped:
            by_class[road.road_class or "unknown"] += 1
        self.report["roadsSkipped"] = len(skipped)
        self.report["roadsSkippedByClass"] = dict(by_class.most_common())

    def build_terrain(self) -> None:
        """
        Reconstruct the terrain from the road network elevation samples.

        uild_terrain takes the layout plus the retained roads.  The terrain grid resolution is
        chosen by choose_terrain_size to satisfy BeamNG power-of-two requirement; heightmap_size
        controls only the exported preview image.
        """
        self.terrain = build_terrain(
            self.layout,
            self.roads,
            heightmap_size=self.heightmap_size,
            verbose=False,
        )

        # The road surface is painted later, in emit_roads, from the geometry actually emitted.

    def ground_height(self, x: float, y: float) -> float:
        if self.terrain is None:
            return 0.0
        t = self.terrain
        span = t.size * t.square_size
        origin = -span * 0.5
        gx = (x - origin) / span * (t.size - 1)
        gy = (y - origin) / span * (t.size - 1)
        gx = max(0.0, min(t.size - 1.001, gx))
        gy = max(0.0, min(t.size - 1.001, gy))
        x0, y0 = int(gx), int(gy)
        fx, fy = gx - x0, gy - y0
        h = t.heights
        top = h[y0, x0] * (1 - fx) + h[y0, x0 + 1] * fx
        bottom = h[y0 + 1, x0] * (1 - fx) + h[y0 + 1, x0 + 1] * fx
        value = top * (1 - fy) + bottom * fy
        return t.height_min + float(value) / 65535.0 * (t.max_height - t.height_min)

    # ---------------------------------------------------------------- terrain
    def emit_terrain_materials(self) -> None:
        """
        Write the terrain materials, in layer-map index order.

        Two materials are declared: `Grass` for the ground and `Asphalt` for the painted road
        surface.  Index 0 is Grass and index 1 is Asphalt, matching `TERRAIN_MATERIAL_ORDER`, which
        is also the order their names are stored in the `.ter`.  Every layer byte is an index into
        that list, so the two must agree.

        Both materials are taken from working levels and only their texture paths are changed --
        all fifteen slots per material point at built-in engine content.  Nothing is authored and
        no texture is copied.
        """
        material_names = list(TERRAIN_MATERIAL_ORDER)

        definitions: Dict[str, Any] = {}
        texture_set = dict(CS1_TERRAIN_TEXTURE_SET)
        texture_set["name"] = self.texture_set_name
        texture_set["persistentId"] = new_id()
        definitions[f"{self.level_name}TerrainMaterialTextureSet"] = texture_set

        for name in material_names:
            template = CS1_TERRAIN_MATERIAL if name == "Grass" else CS1_ASPHALT_MATERIAL
            definition = dict(template)
            definition["name"] = f"{name}-{new_id()}"
            definition["persistentId"] = new_id()
            definitions[definition["name"]] = definition

        # Merge the building window aliases into this same file.  It is the one material library
        # the engine is known to load for this level, so a shape's window material is redirected
        # without relying on any other lookup path.
        definitions.update(getattr(self, "window_material_aliases", {}))

        terrain_dir = os.path.join(self.level_root, "art", "terrains")
        os.makedirs(terrain_dir, exist_ok=True)

        # Ship the supplied ground colour texture in the level, and point the base colour slot at it.
        # Only that slot changes; the normal, roughness, ao and height families stay on the engine
        # set, which is how the engine's own materials are built.
        source = os.path.join(self.output_root, os.pardir, CUSTOM_TERRAIN_TEXTURE_SOURCE)
        source = os.path.normpath(source)
        converted = convert_custom_terrain_texture(
            source,
            os.path.join(terrain_dir, CUSTOM_TERRAIN_TEXTURE_NAME),
            CUSTOM_TERRAIN_TEXTURE_SIZE,
        )
        if converted:
            grass_key = next(
                (k for k, v in definitions.items()
                 if isinstance(v, dict) and v.get("internalName") == "Grass"),
                None,
            )
            if grass_key is not None:
                definitions[grass_key]["baseColorBaseTex"] = (
                    f"/levels/{self.level_name.lower()}/art/terrains/{CUSTOM_TERRAIN_TEXTURE_NAME}"
                )
            self.report["customTerrainTexture"] = CUSTOM_TERRAIN_TEXTURE_NAME
        else:
            self.report.setdefault("warnings", []).append(
                f"custom terrain texture not found or unreadable: {CUSTOM_TERRAIN_TEXTURE_SOURCE}"
            )

        self.write_json(os.path.join(terrain_dir, "main.materials.json"), definitions)

        self.terrain_materials = material_names
        self.terrain_texture_base_size = int((texture_set.get("baseTexSize") or [2048])[0])
        self.report["terrainMaterial"] = {
            "internalNames": material_names,
            "groundmodelNames": [
                (CS1_TERRAIN_MATERIAL if n == "Grass" else CS1_ASPHALT_MATERIAL)["groundmodelName"]
                for n in material_names
            ],
            "textureSet": texture_set["name"],
            "baseTexSize": self.terrain_texture_base_size,
            "texturesCopied": 0,
        }

    def emit_terrain_block(self) -> None:
        """
        The TerrainBlock, carrying the fields a working level carries.

        `baseTexSize` must equal the texture set's base size -- measured equal in every working
        map.  `materialTextureSet` must name a set THIS level declares.

        `squareSize` is omitted when it is 1 (polish_roads_v2 omits it); when the map needs a
        coarser grid it is written, because the shader uses it to turn world position into texture
        coordinates and omitting it would make the engine assume 1 m.
        """
        if self.terrain is None:
            return

        t = self.terrain
        span = t.size * t.square_size

        block: Dict[str, Any] = {
            "class": "TerrainBlock",
            "name": "theTerrain",
            "persistentId": new_id(),
            "__parent": "MissionGroup",
            "terrainFile": f"/levels/{self.level_name.lower()}/{self.level_name}.ter",
            "materialTextureSet": self.texture_set_name,
            "baseTexSize": self.terrain_texture_base_size,
            "maxHeight": round(t.max_height, 4),
            "lightMapSize": 1024,
            "screenError": 64,
            "castShadows": True,
            "position": [round(-span * 0.5, 3), round(-span * 0.5, 3), round(t.height_min, 3)],
            "rotationMatrix": list(IDENTITY_ROTATION),
        }
        if abs(t.square_size - 1.0) > 1e-9:
            block["squareSize"] = t.square_size

        self.terrain_block = block

    def emit_terrain_files(self) -> None:
        """Write the .ter, its descriptive .terrain.json, and the heightmap image."""
        if self.terrain is None:
            return

        ter_path = os.path.join(self.level_root, f"{self.level_name}.ter")
        write_ter_file(ter_path, self.terrain, self.terrain_materials)
        self.report["files"].append(os.path.relpath(ter_path, self.mod_root))

        heightmap_path = os.path.join(self.level_root, f"{self.level_name}.terrainheightmap.png")
        write_png_gray8(heightmap_path, self.terrain.heightmap_png)
        self.report["files"].append(os.path.relpath(heightmap_path, self.mod_root))

        t = self.terrain
        n = t.size * t.size
        self.write_json(
            os.path.join(self.level_root, f"{self.level_name}.terrain.json"),
            {
                "version": TERRAIN_FILE_VERSION,
                "size": t.size,
                "binaryFormat": (
                    "version(char), size(unsigned int), "
                    "heightMap(heightMapSize * heightMapItemSize), "
                    "layerMap(layerMapSize * layerMapItemSize), "
                    "layerTextureMap(layerMapSize * layerMapItemSize), materialNames"
                ),
                "datafile": f"/levels/{self.level_name.lower()}/{self.level_name}.ter",
                "heightmapImage": (
                    f"/levels/{self.level_name.lower()}/{self.level_name}.terrainheightmap.png"
                ),
                "heightMapSize": n,
                "heightMapItemSize": 2,
                "layerMapSize": n,
                "layerMapItemSize": 1,
                "materials": list(self.terrain_materials),
            },
        )

    # ---------------------------------------------------------------- roads
    def emit_roads(self) -> None:
        """
        One DecalRoad per chained centre-line.

        `autoJunction` and `autoLanes` are ENABLED by explicit instruction.  They ask the engine to
        weld road geometry where decals meet, so intersections connect themselves.  Measured on
        polish_roads_v2 these appear on only 6 of 6740 roads -- but that map hand-authors its
        junction pieces in dedicated groups; a converted city has none, so automatic joining is the
        correct behaviour here.

        The decal values below are the ones that map actually uses in bulk:
        `distanceFade [160,60]`, `decalBias 0.0005`, `detail 0.5`.
        """
        objects: List[Dict[str, Any]] = []
        material_usage: Counter = Counter()

        if self.roads_from_buildings:
            # Derived from building positions rather than the CS1 road graph.
            entries = derive_roads_from_buildings(self.buildings)
            self.report["roadSource"] = "derived-from-buildings"
        elif self.chain_roads_enabled:
            entries = chain_roads(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph-chained"
        else:
            entries = roads_as_segments(self.roads, self.max_sagitta)
            self.report["roadSource"] = "cs1-road-graph-per-segment"

        # Paint the terrain surface from these SAME centrelines, so what grips matches what is
        # drawn.  Done before the objects are built so the layer map is final before the .ter is
        # written; `build()` orders emit_roads ahead of emit_terrain_files for that reason.
        if self.terrain is not None:
            self.report["roadSurfaceCells"] = paint_road_surface(self.terrain, entries)

        for entry in entries:
            width = max(entry["width"], self.max_width)
            material = entry["material"]
            # source is the Road this chain came from, or None when the chain was derived from
            # building positions.  Only road-derived chains know whether they are one-way.
            road = entry.get("source")
            material_usage[material] += 1

            nodes: List[List[float]] = []
            for point in entry["points"]:
                bx, by, _ = point.beamng()
                bz = self.ground_height(bx, by) if self.terrain is not None else point.beamng()[2]
                nodes.append([round(bx, 4), round(by, 4), round(bz, 4), round(width, 4)])

            deduped: List[List[float]] = []
            for node in nodes:
                if deduped:
                    dx = node[0] - deduped[-1][0]
                    dy = node[1] - deduped[-1][1]
                    if dx * dx + dy * dy < 0.0004:
                        continue
                deduped.append(node)
            if len(deduped) < 2:
                continue

            objects.append({
                "class": "DecalRoad",
                "persistentId": new_id(),
                "__parent": "Roads",
                "position": deduped[0][:3],
                "material": material,
                "textureLength": 12.0,
                "renderPriority": 9,
                "drivability": 1.0,
                "oneWay": bool(getattr(road, "is_one_way", False)),
                "improvedSpline": True,
                "autoJunction": True,
                "autoLanes": True,
                "detail": 0.5,
                "decalBias": 0.0005,
                "distanceFade": [160, 60],
                # Chosen from measurement: polish_roads_v2 uses [1,1] on 1461 of its roads and only
                # the low-fade variants on markings.  A fade of 0 erases the road surface at every
                # chain end, which is precisely where chains meet at junctions -- that alone reads
                # as "roads do not connect".
                "startEndFade": [1, 1],
                "overObjects": not self.with_terrain,
                "nodes": deduped,
            })
            self.report["decalRoadNodes"] += len(deduped)

        self.report["roadsConverted"] = len(objects)
        self.report["materials"] = dict(material_usage.most_common())
        self.report["roadGroupFiles"] = self._emit_grouped(
            objects, group="Roads", container="MissionGroup"
        )

    # ---------------------------------------------------------------- buildings
    def _building_road_segments(self):
        """Flatten the roads once, for reuse across every building."""
        if getattr(self, "_road_segments", None) is None:
            self._road_segments = road_segments(self.roads)
        return self._road_segments

    def emit_buildings(self) -> None:
        """
        Base-game shapes referenced IN PLACE, grounded on the HIGHEST surface under the footprint.

        The high point is used deliberately: sitting on the lowest point and then sinking drove
        buildings into the terrain.  A small gap over a dip is far less objectionable than an
        intersecting building.

        Appearance is varied with `instanceColor` rather than by creating a material per variant.
        """
        objects: List[Dict[str, Any]] = []
        self._road_segments = self._building_road_segments()

        for building in self.buildings:
            half_w = building.width * 0.5
            half_l = building.length * 0.5
            height = max(building.height, 3.0)

            bx, by, _ = building.position.beamng()
            yaw = yaw_to_beamng(building.angle_radians)

            # NOTE: the ground is sampled here, after the centre offset above and before any road
            # push, and again after a push if one happens -- a building must take the elevation of
            # where it ends up, not where it used to be.
            ground = self.ground_height(bx, by)
            if self.terrain is not None:
                cos_a, sin_a = math.cos(yaw), math.sin(yaw)
                probes = [ground]
                for ox, oy in (
                    (-half_w, -half_l), (half_w, -half_l), (-half_w, half_l), (half_w, half_l),
                    (-half_w, 0.0), (half_w, 0.0), (0.0, -half_l), (0.0, half_l),
                ):
                    rx = ox * cos_a - oy * sin_a
                    ry = ox * sin_a + oy * cos_a
                    probes.append(self.ground_height(bx + rx, by + ry))
                ground = max(probes)

            model, model_size, scale = choose_beamng_model(
                building.width, building.length, height
            )

            # NOTE: the mesh-origin offset is deliberately NOT applied.  It was measured from the
            # Collada bounding-box centre and tested four ways (both signs, both rotation
            # directions).  Every variant made road overlap WORSE than applying nothing:
            #
            #     none                     124 buildings overlapping  642.9 m total penetration
            #     minus, rotate +yaw       161                        936.5 m
            #     add,   rotate -yaw       181                        948.3 m
            #     add,   rotate +yaw       230                       1032.2 m
            #     raw add (first attempt)  417                       2194.3 m
            #
            # So the raw vertex bounds do not describe the placed mesh: city_block3 measures 6.3x
            # its table size, which shows node transforms or a non-standard axis convention are in
            # play.  Applying a half-understood offset moves buildings onto roads rather than off
            # them, so the placement keeps the origin where CS1 puts it.

            # Keep the footprint off the road surface.  A building overhanging a road both looks
            # wrong and blocks it, and nothing in the placement previously considered the roads at
            # all -- only the terrain height under the footprint.
            if self.roads:
                # rotation-independent footprint reach, unscaled and scaled
                model_half_diag = 0.5 * math.hypot(model_size[0], model_size[1])
                half_diag = model_half_diag * scale[0]

                # Distance from the centre to the nearest road EDGE.  Negative means the centre is
                # inside the road surface itself.
                centre_edge = road_clearance(bx, by, self._road_segments)

                if math.isfinite(centre_edge):
                    # One quantity decides everything: how much room is left once the footprint's
                    # worst-case reach and the required clearance are both accounted for.
                    effective = centre_edge - half_diag - BUILDING_ROAD_CLEARANCE

                    if effective < 0.0:
                        if centre_edge > 0.0 and model_half_diag > 1e-6:
                            # Centre is clear of the road but the footprint reaches it: shrink by
                            # exactly the shortfall, never below a usable size.
                            allowed = max(0.05, (centre_edge - BUILDING_ROAD_CLEARANCE) / model_half_diag)
                            if allowed < scale[0]:
                                scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))
                                half_diag = model_half_diag * scale[0]
                                effective = centre_edge - half_diag - BUILDING_ROAD_CLEARANCE
                        else:
                            # Centre is INSIDE a road, so scaling cannot help -- a footprint cannot be
                            # shrunk out of a corridor it is centred in.  CS1 places "Road Connection"
                            # and "Water Pipe Junction" prefabs like that on purpose, so the building
                            # is pushed out instead.
                            moved = push_out_of_road_iterative(
                                bx, by, self._road_segments,
                                BUILDING_ROAD_CLEARANCE + half_diag,
                            )
                            if moved is not None:
                                bx, by = moved
                                self.report["buildingsPushedOffRoad"] = (
                                    self.report.get("buildingsPushedOffRoad", 0) + 1
                                )
                                # Resample: the building now stands somewhere else.
                                ground = self.ground_height(bx, by)

                    # Final recheck, measured rather than predicted.  The bounding circle can still
                    # reach a road after the steps above, because the model's half-diagonal is not
                    # the CS1 footprint the scale was derived from.  Shrink by whatever shortfall
                    # remains.  Bounded below so a building never collapses to nothing.
                    landed_edge = road_clearance(bx, by, self._road_segments)
                    if math.isfinite(landed_edge) and model_half_diag > 1e-6:
                        room = landed_edge - BUILDING_ROAD_CLEARANCE
                        if room < model_half_diag * scale[0] and room > 0.0:
                            allowed = max(0.05, room / model_half_diag)
                            if allowed < scale[0]:
                                scale = (allowed, allowed, min(scale[2], max(allowed, 1.0)))
                                self.report["buildingsShrunkForRoad"] = (
                                    self.report.get("buildingsShrunkForRoad", 0) + 1
                                )

            objects.append({
                "class": "TSStatic",
                "name": f"b_{building.building_id}",
                "persistentId": new_id(),
                "__parent": "Buildings",
                "shapeName": model,
                "position": [round(bx, 4), round(by, 4), round(ground, 4)],
                "rotationMatrix": [round(v, 8) for v in rotation_matrix_z(yaw)],
                "scale": [round(v, 5) for v in scale],
                "collisionType": "Collision Mesh",
                "decalType": "Collision Mesh",
                # Tints the base-game shape without creating a material.
                "instanceColor": BUILDING_INSTANCE_COLORS.get(
                    building.service, BUILDING_INSTANCE_COLORS["default"]
                ),
                "cs1Prefab": building.prefab_name,
                "cs1Service": building.service,
            })

        self.report["buildingsConverted"] = len(objects)
        self.report["buildingGroupFiles"] = self._emit_grouped(
            objects, group="Buildings", container="MissionGroup"
        )


    def emit_ground_models(self) -> None:
        """
        Write `levels/<level>/groundModels/surfaces.json`.

        The engine merges this over `/art/groundmodels.json` at level load, so declaring a name
        the common file already defines overrides it for this level only.
        """
        path = os.path.join(self.level_root, "groundModels", "surfaces.json")
        models = build_ground_models()
        self.write_json(path, models)
        self.report["groundModels"] = sorted(models)

    def emit_building_materials(self) -> None:
        """
        Write window-material aliases beside the level's building assets.

        Several base-game building shapes declare materials whose textures live in their own
        level's archive; referenced from another level those textures do not resolve and the
        windows render as a pale untextured strip.

        Each entry below authors nothing -- it is `{name, mapTo}` only, redirecting the name the
        shape asks for to an engine glass material that IS mounted globally.  Anything not listed
        keeps its original assignment.
        """
        # Store them on the builder so the terrain material emitter can merge them into the ONE
        # file the engine demonstrably reads for this level:
        # `levels/<level>/art/terrains/main.materials.json`.  The aliases are merged there rather
        # than written to a separate path, because a file the engine does not read resolves
        # nothing -- which is why the previous attempt had no effect.
        self.window_material_aliases = build_window_materials()
        self.report["windowMaterialAliases"] = len(self.window_material_aliases)

    # ---------------------------------------------------------------- lighting
    def emit_sky_and_sun(self) -> None:
        """
        Lighting, copied verbatim from BeamNG's own `levels/template`.

        The engine ships that level as the starting point for new maps, so its sky block is
        guaranteed loadable by this build.  A hand-written block was rejected wholesale earlier
        with `Unable to deserialize file .../sky_and_sun/items.level.json`, which leaves the level
        unlit and completely black.

        `CloudLayer` in particular requires a `texture` field; without it the whole group fails.
        """
        objects: List[Dict[str, Any]] = []
        seen: set = set()
        template = None

        game = find_beamng_install()
        if game:
            archive = os.path.join(game, "content", "levels", "template.zip")
            if os.path.isfile(archive):
                template = archive

        if template:
            with zipfile.ZipFile(template) as source:
                for entry in source.infolist():
                    if not entry.filename.lower().endswith("items.level.json"):
                        continue
                    try:
                        text = source.read(entry).decode("utf-8", "replace")
                    except Exception:
                        continue
                    decoder = json.JSONDecoder()
                    index = 0
                    while index < len(text):
                        while index < len(text) and text[index].isspace():
                            index += 1
                        if index >= len(text):
                            break
                        try:
                            obj, index = decoder.raw_decode(text, index)
                        except json.JSONDecodeError:
                            break
                        if not isinstance(obj, dict):
                            continue
                        cls = obj.get("class")
                        if cls not in (
                            "LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer",
                            "Precipitation", "ForestWindEmitter",
                        ):
                            continue
                        # Keep the FIRST of each class only.  The template holds the same five
                        # objects in two different files; collecting every match produced ten
                        # objects and two of each class.  polish_roads_v2 has exactly one of each.
                        if cls in seen:
                            continue
                        seen.add(cls)

                        clone = dict(obj)
                        clone["persistentId"] = new_id()
                        clone["__parent"] = "sky_and_sun"
                        clone["name"] = obj.get("name", cls)

                        # The engine expects a cubemap here, under this exact spelling (missing the
                        # `n` in "Environment").  Its absence is what produces
                        # "LevelInfo dont have defined globalEnviromentMap for vehicle's static
                        # reflections" in the log.
                        if cls == "LevelInfo":
                            if not clone.get("globalEnviromentMap"):
                                clone["globalEnviromentMap"] = "BNG_Sky_02_cubemap"

                            # The template's atmosphere is much foggier and more tinted than a
                            # working map's, which washes everything toward pale blue.  Values
                            # taken from polish_roads_v2's own LevelInfo.
                            clone["fogColor"] = [1, 1, 1, 1]
                            clone["fogDensity"] = 0.00028
                            clone["fogDensityOffset"] = 100
                            clone["fogAtmosphereHeight"] = 300
                            clone["visibleDistance"] = 9000
                            clone["decalBias"] = 0.001

                        objects.append(clone)

        if not objects:
            self.report["warnings"].append(
                "no lighting objects could be read from levels/template; the map will be dark"
            )

        self.write_lines(
            os.path.join(self.main_root, "MissionGroup", "sky_and_sun", "items.level.json"),
            objects,
        )
        self.sky_objects = objects

    # ---------------------------------------------------------------- spawn
    def choose_spawn_point(self) -> Tuple[float, float, float]:
        """
        A spawn on a flat, road-adjacent piece of ground.

        A car placed on a slope or a cliff edge simply falls, so candidates are scored on the relief
        of a 12 m disc around them, their distance from the terrain edge, and proximity to a road.
        """
        best = None
        for chain in chain_roads(self.roads, self.max_sagitta):
            for point in chain["points"][:: max(1, len(chain["points"]) // 4)]:
                bx, by, _ = point.beamng()
                ground = self.ground_height(bx, by)

                if self.terrain is None:
                    return bx, by, ground

                t = self.terrain
                span = t.size * t.square_size
                half = span * 0.5
                edge = min(bx + half, half - bx, by + half, half - by)
                if edge < 200.0:
                    continue

                relief = 0.0
                for dx, dy in ((12, 0), (-12, 0), (0, 12), (0, -12)):
                    relief = max(relief, abs(self.ground_height(bx + dx, by + dy) - ground))
                if relief > 2.5:
                    continue

                score = relief * 10.0 - edge * 0.01
                if best is None or score < best[0]:
                    best = (score, bx, by, ground)

        if best is None:
            for road in self.roads:
                bx, by, _ = road.start_position.beamng()
                return bx, by, self.ground_height(bx, by)
            return 0.0, 0.0, 0.0

        _score, bx, by, ground = best
        return bx, by, ground

    def emit_spawns_and_mission(self) -> None:
        """
        The MissionGroup tree.

        `main/items.level.json` declares ONLY the top-level MissionGroup.  Its own folder holds the
        objects, the TerrainBlock, and one SimGroup per sub-folder -- a folder is only descended
        into when the sibling file declares a SimGroup whose name equals the folder name.
        """
        bx, by, ground = self.choose_spawn_point()
        spawn_z = ground + 1.0

        objects: List[Dict[str, Any]] = [
            {
                "class": "SpawnSphere",
                "name": "cs1_spawn",
                "persistentId": new_id(),
                "__parent": "MissionGroup",
                "position": [round(bx, 4), round(by, 4), round(spawn_z, 4)],
                "rotationMatrix": list(IDENTITY_ROTATION),
                "autoplaceOnSpawn": "0",
                "dataBlock": "SpawnSphereMarker",
                "enabled": "1",
                "homingCount": "0",
                "indoorWeight": "1",
                "isAIControlled": "0",
                "lockCount": "0",
                "outdoorWeight": "1",
                "radius": 5,
                "sphereWeight": "1",
            }
        ]

        if self.terrain_block is not None:
            objects.append(self.terrain_block)

        for group in ("sky_and_sun", "Roads", "Buildings"):
            if group == "Roads" and not self.roads:
                continue
            if group == "Buildings" and not self.buildings:
                continue
            objects.append({
                "class": "SimGroup",
                "name": group,
                "persistentId": new_id(),
                "__parent": "MissionGroup",
            })

        self.write_lines(
            os.path.join(self.main_root, "MissionGroup", "items.level.json"), objects
        )
        self.write_lines(
            os.path.join(self.main_root, "items.level.json"),
            [{"class": "SimGroup", "name": "MissionGroup", "persistentId": new_id(), "enabled": "1"}],
        )

    # ---------------------------------------------------------------- preview and info
    def emit_preview_image(self) -> None:
        """Write `_preview.png`, which the level selector requests for its tile."""
        if self.terrain is None:
            return

        size = 256
        grid = _resample(self.terrain.heights.astype(np.float32), size)
        gy, gx = np.gradient(grid)
        shade = np.clip(0.5 + (gx * 2.0 + gy * 2.0), 0.0, 1.0)
        shade = 0.45 + shade * 0.55
        base = np.array([0.42, 0.52, 0.30], dtype=np.float32)
        rgb = np.clip(base[None, None, :] * shade[:, :, None], 0.0, 1.0)
        pixels = (rgb * 255.0 + 0.5).astype(np.uint8)

        path = os.path.join(self.level_root, "_preview.png")
        write_png_rgb(path, pixels)
        self.report["files"].append(os.path.relpath(path, self.mod_root))

    def emit_info_json(self) -> None:
        if self.terrain is None:
            return
        t = self.terrain
        span = t.size * t.square_size
        bx, by, ground = self.choose_spawn_point()

        self.write_json(
            os.path.join(self.level_root, "info.json"),
            {
                "title": self.level_name,
                "description": (
                    f"Converted from a Cities: Skylines save by CS1-to-BeamNG. "
                    f"{self.report['roadsConverted']} roads, "
                    f"{self.report['buildingsConverted']} buildings."
                ),
                "authors": "CS1-to-BeamNG",
                "size": [int(span), int(span)],
                "defaultSpawnPointName": "cs1_spawn",
                "spawnPoints": [
                    {
                        "name": "cs1_spawn",
                        "position": [round(bx, 3), round(by, 3), round(ground + 1.0, 3)],
                        "rotation": [0, 0, 0],
                    }
                ],
            },
        )

    # ---------------------------------------------------------------- driver
    def build(self) -> None:
        """
        Order matters.

        `emit_terrain_materials()` runs BEFORE `emit_terrain_block()`: it sets
        `terrain_texture_base_size`, which the block writes as `baseTexSize`.  Running it afterwards
        left the block declaring 1024 against a texture set of [4096,4096].
        """
        self.select_content()
        self.build_terrain()
        # Prepare the window alias table BEFORE the terrain material file is written: the aliases
        # are merged into that file, and `emit_terrain_materials` would otherwise run first and
        # write a file without them.  That ordering mistake is why the aliases had no effect.
        self.emit_building_materials()
        self.emit_terrain_materials()
        self.emit_terrain_block()
        # Roads run BEFORE the terrain files: emitting them paints the road surface into the layer
        # map, and the .ter has to be written after that is final.  Writing it first would persist
        # an unpainted layer map and roads would carry no grip.
        self.emit_roads()
        self.emit_terrain_files()
        self.emit_buildings()
        self.emit_ground_models()
        self.emit_sky_and_sun()
        self.emit_spawns_and_mission()
        self.emit_preview_image()
        self.emit_info_json()


# ==========================================================================================
#  Packaging and verification
# ==========================================================================================

def remove_stale_unpacked_level(level_name: str) -> Optional[str]:
    """
    Delete an unpacked level folder that would shadow this mod, and return its path.

    BeamNG resolves `current/levels/<name>/` BEFORE the same level inside a mod, so any folder there
    silently replaces everything the mod contains.  The World Editor creates one whenever a level is
    opened -- it writes `main.decals.json` even for a level it does not otherwise touch.

    A folder holding only that 281-byte file was enough to shadow a 13 MB archive for several
    rounds.  Any directory for this level is removed, matched case-insensitively.
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None

    levels_dir = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "levels")
    if not os.path.isdir(levels_dir):
        return None

    for entry in os.listdir(levels_dir):
        if entry.lower() != level_name.lower():
            continue
        candidate = os.path.join(levels_dir, entry)
        if os.path.isdir(candidate):
            try:
                shutil.rmtree(candidate)
                return candidate
            except OSError:
                return None
    return None


def zip_mod(mod_root: str, zip_path: str) -> str:
    """
    Package the mod.  Entries go at the ARCHIVE ROOT (`levels/`, `art/`) -- wrapping them in a
    folder makes the engine report "Invalid ZIP file".
    """
    os.makedirs(os.path.dirname(zip_path), exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder, _dirs, files in os.walk(mod_root):
            for name in sorted(files):
                full = os.path.join(folder, name)
                archive.write(full, os.path.relpath(full, mod_root).replace(os.sep, "/"))
    return zip_path


def find_beamng_user_mods() -> Optional[str]:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None
    target = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "mods")
    return target if os.path.isdir(target) else None


def _verify_ter_file(ter_path: str, descriptor: Dict[str, Any]) -> List[str]:
    """
    Parse the binary .ter back and confirm it matches the documented layout.

    Layout: u8 version, u32 size, u16[size*size] heights, u8[size*size] layers,
            u32 materialCount, then NUL-terminated material name strings.
    """
    problems: List[str] = []

    with open(ter_path, "rb") as handle:
        header = handle.read(5)
        if len(header) < 5:
            return [f"{os.path.basename(ter_path)}: truncated header"]

        version = header[0]
        size = struct.unpack("<I", header[1:5])[0]

        if version != TERRAIN_FILE_VERSION:
            problems.append(
                f"{os.path.basename(ter_path)}: version {version}, expected {TERRAIN_FILE_VERSION}"
            )
        if size < 128 or size > 8192 or (size & (size - 1)) != 0:
            problems.append(
                f"{os.path.basename(ter_path)}: size {size} is not a power of two in 128..8192"
            )

        sample_count = size * size
        expected_bytes = 1 + 4 + sample_count * 2 + sample_count

        handle.seek(1 + 4)
        heights = handle.read(sample_count * 2)
        layers = handle.read(sample_count)
        count_bytes = handle.read(4)

        if len(heights) != sample_count * 2:
            problems.append(f"{os.path.basename(ter_path)}: heightmap is truncated")
        if len(layers) != sample_count:
            problems.append(f"{os.path.basename(ter_path)}: layer map is truncated")
        if len(count_bytes) != 4:
            problems.append(f"{os.path.basename(ter_path)}: missing material count")
            return problems

        material_count = struct.unpack("<I", count_bytes)[0]
        names = []
        for _ in range(material_count):
            raw = bytearray()
            while True:
                char = handle.read(1)
                if not char or char == b"\x00":
                    break
                raw.extend(char)
            names.append(raw.decode("ascii", "replace"))

        if material_count == 0:
            problems.append(f"{os.path.basename(ter_path)}: no terrain materials listed")
        if material_count > 254:
            problems.append(
                f"{os.path.basename(ter_path)}: {material_count} materials exceeds the "
                f"u8 layer-index limit of 254"
            )

        declared = descriptor.get("heightMapSize")
        if isinstance(declared, int) and declared != sample_count:
            problems.append(
                f"terrain.json heightMapSize {declared} != {sample_count} implied by size {size}"
            )

        actual_bytes = os.path.getsize(ter_path)
        if actual_bytes <= expected_bytes:
            problems.append(
                f"{os.path.basename(ter_path)}: only {actual_bytes} bytes, expected more than "
                f"{expected_bytes}"
            )

    return problems


def _iter_json_objects(text: str) -> Iterable[Any]:
    """
    Yield each JSON object in a line-delimited file.

    Uses raw_decode so objects may be pretty-printed across several lines; whitespace between
    objects is skipped.  This is stricter about structure than splitting on newlines while still
    accepting the layout BeamNG itself writes.
    """
    decoder = json.JSONDecoder()
    index = 0
    length = len(text)

    while index < length:
        while index < length and text[index].isspace():
            index += 1
        if index >= length:
            return

        obj, end = decoder.raw_decode(text, index)
        yield obj
        index = end


def _terrain_declared_size(mod_root: str, level_name: str) -> Optional[int]:
    path = os.path.join(mod_root, "levels", level_name, f"{level_name}.terrain.json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as handle:
            return int(json.load(handle).get("size"))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def verify_level(mod_root: str, level_name: str) -> Tuple[List[str], List[str]]:
    """
    Re-read everything we generated and check it against the verified BeamNG formats.
    Returns (problems, warnings).
    """
    problems: List[str] = []
    warnings: List[str] = []

    info_path = os.path.join(mod_root, "levels", level_name, "info.json")
    if not os.path.isfile(info_path):
        problems.append("missing info.json")
    else:
        try:
            with open(info_path, encoding="utf-8") as handle:
                info = json.load(handle)
            for key in ("title", "size", "defaultSpawnPointName"):
                if key not in info:
                    problems.append(f"info.json: missing '{key}'")
            if not isinstance(info.get("size"), list) or len(info["size"]) != 2:
                problems.append("info.json: 'size' must be [x, y]")
        except json.JSONDecodeError as exc:
            problems.append(f"info.json is not valid JSON: {exc}")

    terrain_path = os.path.join(mod_root, "levels", level_name, f"{level_name}.terrain.json")
    terrain_block_seen = False

    if os.path.isfile(terrain_path):
        try:
            with open(terrain_path, encoding="utf-8") as handle:
                terrain = json.load(handle)

            for key in ("version", "datafile", "size", "heightMapSize", "materials"):
                if key not in terrain:
                    problems.append(f"terrain.json: missing '{key}'")

            # The metadata points at the binary terrain; that file must exist AND parse.
            datafile = terrain.get("datafile", "")
            ter_path = os.path.join(
                mod_root, datafile.lstrip("/").replace("/", os.sep)
            ) if datafile else ""
            if not ter_path or not os.path.isfile(ter_path):
                problems.append(f"terrain.json references a missing .ter file: {datafile}")
            else:
                problems.extend(_verify_ter_file(ter_path, terrain))

            png = terrain.get("heightmapImage", "").rsplit("/", 1)[-1]
            png_path = os.path.join(mod_root, "levels", level_name, png)
            if not os.path.isfile(png_path):
                problems.append(f"terrain.json references a missing heightmap image: {png}")
            else:
                with open(png_path, "rb") as handle:
                    if handle.read(8) != b"\x89PNG\r\n\x1a\n":
                        problems.append(f"{png} is not a PNG file")
        except json.JSONDecodeError as exc:
            problems.append(f"terrain.json is not valid JSON: {exc}")
    else:
        warnings.append("no terrain files were generated")

    # Every items.level.json is line-delimited: a stream of JSON objects, never an array.
    # Parsed with a streaming decoder rather than per-physical-line, so a pretty-printed object
    # still validates while a wrapped array is still rejected.
    total_objects = 0
    decal_roads = 0
    statics = 0

    for folder, _dirs, files in os.walk(os.path.join(mod_root, "levels", level_name)):
        for name in files:
            if name != "items.level.json":
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, mod_root)

            with open(path, encoding="utf-8") as handle:
                text = handle.read()

            if text.lstrip().startswith("["):
                problems.append(f"{rel}: items.level.json must not be a JSON array")
                continue

            try:
                for obj in _iter_json_objects(text):
                    total_objects += 1

                    if not isinstance(obj, dict) or "class" not in obj:
                        problems.append(f"{rel}: an object is missing 'class'")
                        continue

                    if obj["class"] == "DecalRoad":
                        decal_roads += 1
                        nodes = obj.get("nodes")
                        if not isinstance(nodes, list) or len(nodes) < 2:
                            problems.append(f"{rel}: DecalRoad needs >= 2 nodes")
                            continue
                        for node in nodes:
                            if not isinstance(node, list) or len(node) != 4:
                                problems.append(
                                    f"{rel}: DecalRoad node must be [x, y, z, width]"
                                )
                                break
                        if not obj.get("material"):
                            problems.append(f"{rel}: DecalRoad has no material")
                    elif obj["class"] == "TerrainBlock":
                        terrain_block_seen = True
                        for key in ("terrainFile", "squareSize", "maxHeight", "position"):
                            if key not in obj:
                                problems.append(f"{rel}: TerrainBlock missing '{key}'")
                        terrain_file = obj.get("terrainFile", "")
                        local = os.path.join(
                            mod_root, terrain_file.lstrip("/").replace("/", os.sep)
                        )
                        if terrain_file and not os.path.isfile(local):
                            problems.append(
                                f"{rel}: TerrainBlock references a missing terrain: {terrain_file}"
                            )
                    elif obj["class"] == "TSStatic":
                        statics += 1
                        matrix = obj.get("rotationMatrix")
                        if not isinstance(matrix, list) or len(matrix) != 9:
                            problems.append(
                                f"{rel}: TSStatic rotationMatrix must have 9 values"
                            )
                        scale = obj.get("scale")
                        if not isinstance(scale, list) or len(scale) != 3:
                            problems.append(f"{rel}: TSStatic scale must have 3 values")
                        position = obj.get("position")
                        if not isinstance(position, list) or len(position) != 3:
                            problems.append(
                                f"{rel}: TSStatic position must have 3 values"
                            )
            except ValueError as exc:
                problems.append(f"{rel}: could not parse objects: {exc}")

    if total_objects == 0:
        problems.append("no level objects were written at all")
    if decal_roads == 0:
        warnings.append("no DecalRoads were generated; the map will not be drivable")
    if not terrain_block_seen:
        problems.append("no TerrainBlock was written; the level would have no ground")

    # Referenced shapes must exist.
    for folder, _dirs, files in os.walk(os.path.join(mod_root, "levels", level_name)):
        for name in files:
            if name != "items.level.json":
                continue
            with open(os.path.join(folder, name), encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line or line.startswith("["):
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    shape = obj.get("shapeName") if isinstance(obj, dict) else None
                    if shape:
                        local = os.path.join(mod_root, shape.lstrip("/").replace("/", os.sep))
                        if os.path.isfile(local):
                            continue
                        # Shapes referenced across levels are provided by the base game or another
                        # mod, which is normal practice; only a missing path INSIDE this mod is a
                        # real problem.
                        if re.match(r"^/levels/[^/]+/", shape):
                            continue
                        problems.append(f"item references a missing shape: {shape}")

    return problems, warnings


# ==========================================================================================
#  8.  MAIN
# ==========================================================================================


def convert(
    layout_path: str,
    out_root: str,
    level_name: Optional[str] = None,
    mod_name: Optional[str] = None,
    include_non_drivable: bool = False,
    with_terrain: bool = True,
    heightmap_size: int = 2048,
    max_width: float = 6.0,
    install: bool = False,
    verbose: bool = True,
    roads_from_buildings: bool = False,
    chain_roads_enabled: bool = False,
) -> Dict[str, Any]:
    layout, problems, warnings = load_city_layout(layout_path)
    if problems:
        raise ValueError("; ".join(problems))

    level = sanitize_identifier(level_name or layout.city_name, "cs1level")
    mod = sanitize_identifier(mod_name or f"cs1_{level.lower()}", "cs1_mod")

    if verbose:
        print(f"  source    : {layout_path}")
        print(f"  city      : {layout.city_name}")
        print(f"  level     : {level}   mod folder: {mod}")

    builder = BeamNGLevelBuilder(
        layout=layout,
        output_root=out_root,
        level_name=level,
        mod_name=mod,
        include_non_drivable=include_non_drivable,
        roads_from_buildings=roads_from_buildings,
        chain_roads_enabled=chain_roads_enabled,
        with_terrain=with_terrain,
        heightmap_size=heightmap_size,
        max_width=max_width,
    )

    if os.path.isdir(builder.mod_root):
        shutil.rmtree(builder.mod_root)
    os.makedirs(builder.mod_root, exist_ok=True)

    builder.build()

    verify_problems, verify_warnings = verify_level(builder.mod_root, level)
    builder.report["problems"] = verify_problems
    builder.report["warnings"].extend(warnings)
    builder.report["warnings"].extend(verify_warnings)

    zip_path = zip_mod(builder.mod_root, os.path.join(out_root, f"{mod}.zip"))
    builder.report["zipPath"] = zip_path
    builder.report["modRoot"] = builder.mod_root

    if install:
        target = find_beamng_user_mods()
        if target is None:
            builder.report["warnings"].append(
                "could not find the BeamNG user mods folder; skipping --install"
            )
        else:
            # An unpacked level in current/levels/ is loaded BEFORE the same level inside a mod,
            # so a folder left behind by the World Editor silently replaces everything the mod
            # ships.  This caused an empty Roads folder, the old generated shapes, "No Mesh"
            # placeholders and grey terrain all at once, while the mod itself was correct.
            # The on-disk folder is lowercased (BeamNG level folders are lowercase), while the
            # level identity keeps its original casing.
            removed = remove_stale_unpacked_level(level.lower()) or remove_stale_unpacked_level(level)
            if removed:
                builder.report.setdefault("removedStaleLevels", []).append(removed)
                if verbose:
                    print(f"  removed stale unpacked level that would override the mod:")
                    print(f"    {removed}")

            destination = os.path.join(target, f"{mod}.zip")
            shutil.copy2(zip_path, destination)
            builder.report["installedTo"] = destination
            if verbose:
                print(f"  installed : {destination}")

    if verbose:
        print(f"  materials : {builder.report['materials']}")
        if builder.report["roadsSkippedByClass"]:
            print(f"  skipped   : {builder.report['roadsSkippedByClass']}")
        print(f"  output    : {builder.mod_root}")
        print(f"  zip       : {zip_path}")

    return builder.report


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Convert a CS1 city_layout.json into a BeamNG.drive level mod.",
        epilog="Coordinates: x_bng=-x_cs1, y_bng=z_cs1, z_bng=y_cs1 (Unity -> BeamNG).",
    )
    parser.add_argument(
        "layout",
        nargs="?",
        default=None,
        help="path to city_layout.json (default: newest file in ./exports, else the Desktop)",
    )
    parser.add_argument("--out", default=None, help="output root (default: <repo>/dist)")
    parser.add_argument("--level-name", default=None, help="BeamNG level name")
    parser.add_argument("--mod-name", default=None, help="mod folder name")
    parser.add_argument(
        "--include-non-drivable",
        action="store_true",
        help="also convert rail, ship, plane, pedestrian and utility paths",
    )
    parser.add_argument(
        "--heightmap-size", type=int, default=2048, help="heightmap resolution (default 2048)"
    )
    parser.add_argument(
        "--max-width", type=float, default=6.0, help="widen roads narrower than this (metres)"
    )
    parser.add_argument(
        "--chain-roads",
        action="store_true",
        help=(
            "chain CS1 segments into long polylines (default: one DecalRoad per segment, which "
            "joins the network at 0.0000 m instead of 83%% of endpoints)"
        ),
    )
    parser.add_argument(
        "--roads-from-buildings",
        action="store_true",
        help="discard the CS1 road geometry and derive streets from building positions instead",
    )
    parser.add_argument(
        "--no-terrain",
        action="store_true",
        help="skip terrain and emit roads with overObjects instead",
    )
    parser.add_argument(
        "--install", action="store_true", help="copy the mod zip into the BeamNG user mods folder"
    )
    parser.add_argument("--json-report", default=None, help="write the report as JSON here")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="project root used to find ./exports and ./dist (default: the parent of tools/)",
    )
    args = parser.parse_args(argv)

    # Resolve the repo root from the script's own location, not the current directory, so the
    # tool behaves identically whether it is run from the repo root, from tools\, or by
    # double-clicking the .cmd launcher.
    repo_root = args.repo_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    layout_path = args.layout or locate_layout(repo_root)

    if layout_path is None:
        print("No city_layout.json found.", file=sys.stderr)
        print("Pass one explicitly:", file=sys.stderr)
        print("  python tools/beamng_convert.py path/to/city_layout.json", file=sys.stderr)
        print(
            "Or export one from the game (it lands in <repo>/exports and on the Desktop).",
            file=sys.stderr,
        )
        return 2

    if not os.path.isfile(layout_path):
        print(f"Not found: {layout_path}", file=sys.stderr)
        print(
            "Note: run from the project root, or pass a full path.",
            file=sys.stderr,
        )
        return 2

    out_root = args.out or os.path.join(repo_root, "dist")

    print("=" * 78)
    print("  CS1-to-BeamNG :: converting city layout to a BeamNG level")
    print("=" * 78)

    try:
        report = convert(
            layout_path=layout_path,
            out_root=out_root,
            level_name=args.level_name,
            mod_name=args.mod_name,
            include_non_drivable=args.include_non_drivable,
            with_terrain=not args.no_terrain,
            heightmap_size=args.heightmap_size,
            max_width=args.max_width,
            install=args.install,
            roads_from_buildings=args.roads_from_buildings,
            chain_roads_enabled=args.chain_roads,
        )
    except ValueError as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"  FAILED: {exc}", file=sys.stderr)
        return 1

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)

    print("=" * 78)
    if report["problems"]:
        print(f"  RESULT: {len(report['problems'])} PROBLEM(S)")
        for problem in report["problems"][:20]:
            print(f"    x {problem}")
        return 1

    print(
        f"  RESULT: OK -- {report['roadsConverted']} roads "
        f"({report['decalRoadNodes']} nodes), {report['buildingsConverted']} buildings"
    )
    for warning in report["warnings"][:10]:
        print(f"    ! {warning}")
    print("=" * 78)
    print()
    print("  Drop the zip into your BeamNG mods folder, or re-run with --install:")
    print(f"    {report['zipPath']}")
    return 0


def locate_layout(repo_root: str) -> Optional[str]:
    """
    Find a city_layout.json without the user having to type a path.

    Order: the repo's exports folder (newest), then the Desktop folder (newest).
    """
    candidates: List[str] = []

    exports = os.path.join(repo_root, "exports")
    if os.path.isdir(exports):
        candidates.extend(
            os.path.join(exports, name)
            for name in os.listdir(exports)
            if name.lower().endswith(".json")
        )

    desktop = os.path.join(os.path.expanduser("~"), "Desktop", "CS1ToBeamNG")
    if os.path.isdir(desktop):
        candidates.extend(
            os.path.join(desktop, name)
            for name in os.listdir(desktop)
            if name.lower().endswith(".json")
        )

    existing = [path for path in candidates if os.path.isfile(path)]
    if not existing:
        return None

    return max(existing, key=os.path.getmtime)


if __name__ == "__main__":
    sys.exit(main())
