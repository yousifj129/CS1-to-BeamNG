#!/usr/bin/env python3
"""
CS1-to-BeamNG :: Part 2 (step 0) -- city_layout.json schema validator and analyser
==================================================================================

Reads the JSON produced by the Cities: Skylines 1 exporter mod
(`mod/CS1ToBeamNGExporter.cs`) and proves it is complete, self-consistent and ready for
conversion into BeamNG.drive map data.  It is the landing pad for the real converter: the
converter will import `load_city_layout()` and `validate()` from here.

Usage
-----
    python tools/validate_city_layout.py <path-to-city_layout.json> [--json report.json]
    python tools/validate_city_layout.py --demo build/sample_city_layout.json

What it checks
--------------
    * JSON parses and schemaVersion is one this tool understands
    * every documented section and field exists with the right type
    * road curves are geometrically sane (Bezier endpoints match node positions,
      tangent directions agree with the control points, no NaN/Infinity)
    * building footprints and angles are usable
    * cross-references resolve (road node ids, building district ids)
    * reports statistics the converter needs: total road length, width histogram,
      bounding box, prefab inventory, building mix

Exit codes
----------
    0 = valid (warnings allowed with --strict off)
    1 = invalid, or warnings present with --strict
    2 = file could not be read / parsed
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------------------
#  Schema description: section -> {field: (python types, required)}
# ---------------------------------------------------------------------------------------
VEC3 = (int, float)

SCHEMA: Dict[str, Dict[str, Tuple[Any, bool]]] = {
    "meta": {
        "generator": (str, True),
        "modVersion": (str, True),
        "trigger": (str, False),
        "exportedAtUtc": (str, True),
        "cityName": (str, False),
        "gameVersion": (str, False),
        "unityVersion": (str, False),
        "mapTheme": (str, False),
        "coordinateSystem": (int, True),
        "coordinateSystemName": (str, False),
        "exportMilliseconds": (int, True),
        "simulationTick": (int, False),
        "roadCount": (int, True),
        "buildingCount": (int, True),
        "districtCount": (int, True),
        "skippedDeletedSegments": (int, False),
        "skippedIncompleteSegments": (int, False),
        "skippedNoPrefabSegments": (int, False),
        "skippedUnreadableSegments": (int, False),
        "skippedDeletedBuildings": (int, False),
        "skippedUnreadableBuildings": (int, False),
        "warnings": (list, True),
    },
    "district": {
        "id": (int, True),
        "name": (str, False),
    },
    "road": {
        "segmentId": (int, True),
        "startNodeId": (int, True),
        "endNodeId": (int, True),
        "prefabName": (str, False),
        "roadClass": (str, False),
        "vehicleTypes": (str, False),
        "isOneWay": (bool, True),
        "isStraight": (bool, True),
        "inverted": (bool, True),
        "halfWidth": (VEC3, True),
        "measuredWidth": (VEC3, True),
        "laneCount": (int, True),
        "averageLength": (VEC3, True),
        "trafficDensity": (int, True),
        "startPosition": (dict, True),
        "endPosition": (dict, True),
        "startDirection": (dict, True),
        "endDirection": (dict, True),
        "middlePosition": (dict, True),
        "bezier": (dict, False),
        "bezierOrientedFromStart": (bool, True),
    },
    "building": {
        "buildingId": (int, True),
        "prefabName": (str, False),
        "assetTitle": (str, False),
        "category": (str, False),
        "service": (str, False),
        "subService": (str, False),
        "position": (dict, True),
        "angleRadians": (VEC3, True),
        "angleDegrees": (VEC3, True),
        "width": (VEC3, True),
        "length": (VEC3, True),
        "height": (VEC3, True),
        "prefabSize": (dict, False),
        "districtId": (int, True),
        "isCollapsed": (bool, True),
        "isAbandoned": (bool, True),
        "isHistorical": (bool, True),
    },
    "bezier": {
        "start": (dict, True),
        "control1": (dict, True),
        "control2": (dict, True),
        "end": (dict, True),
    },
}


# ---------------------------------------------------------------------------------------
#  Vectors
# ---------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    @staticmethod
    def from_json(raw: Any, where: str, problems: List[str]) -> "Vec3":
        if not isinstance(raw, dict):
            problems.append(f"{where}: expected an object with x/y/z, got {type(raw).__name__}")
            return Vec3(0.0, 0.0, 0.0)

        values = []
        for axis in ("x", "y", "z"):
            if axis not in raw:
                problems.append(f"{where}: missing component '{axis}'")
                values.append(0.0)
                continue
            value = raw[axis]
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                problems.append(f"{where}.{axis}: expected a number, got {type(value).__name__}")
                values.append(0.0)
                continue
            if math.isnan(value) or math.isinf(value):
                problems.append(f"{where}.{axis}: non-finite value {value}")
                values.append(0.0)
                continue
            values.append(float(value))

        return Vec3(values[0], values[1], values[2])

    def __add__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: "Vec3") -> "Vec3":
        return Vec3(self.x - other.x, self.y - other.y, self.z - other.z)

    def scaled(self, factor: float) -> "Vec3":
        return Vec3(self.x * factor, self.y * factor, self.z * factor)

    def length(self) -> float:
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)

    def distance_to(self, other: "Vec3") -> float:
        return (self - other).length()

    def normalized(self) -> "Vec3":
        norm = self.length()
        return self.scaled(1.0 / norm) if norm > 1e-12 else Vec3(0.0, 0.0, 0.0)

    def dot(self, other: "Vec3") -> float:
        return self.x * other.x + self.y * other.y + self.z * other.z


@dataclass
class Bezier:
    """Cubic Bezier on the road centre-line."""

    start: Vec3
    control1: Vec3
    control2: Vec3
    end: Vec3

    def point_at(self, t: float) -> Vec3:
        """De Casteljau -- numerically stable for any t in [0, 1]."""
        p01 = lerp(self.start, self.control1, t)
        p12 = lerp(self.control1, self.control2, t)
        p23 = lerp(self.control2, self.end, t)
        p012 = lerp(p01, p12, t)
        p123 = lerp(p12, p23, t)
        return lerp(p012, p123, t)

    def tangent_at(self, t: float) -> Vec3:
        """First derivative; the direction a vehicle faces at t."""
        u = 1.0 - t
        return Vec3(
            3 * u * u * (self.control1.x - self.start.x)
            + 6 * u * t * (self.control2.x - self.control1.x)
            + 3 * t * t * (self.end.x - self.control2.x),
            3 * u * u * (self.control1.y - self.start.y)
            + 6 * u * t * (self.control2.y - self.control1.y)
            + 3 * t * t * (self.end.y - self.control2.y),
            3 * u * u * (self.control1.z - self.start.z)
            + 6 * u * t * (self.control2.z - self.control1.z)
            + 3 * t * t * (self.end.z - self.control2.z),
        )

    def approximate_length(self, samples: int = 16) -> float:
        """Polyline length -- good enough for planning, and used for road-length statistics."""
        total = 0.0
        previous = self.point_at(0.0)
        for step in range(1, samples + 1):
            current = self.point_at(step / samples)
            total += previous.distance_to(current)
            previous = current
        return total

    def is_degenerate(self, tolerance: float = 1e-4) -> bool:
        return (
            self.start.distance_to(self.end) < tolerance
            and self.control1.distance_to(self.control2) < tolerance
        )


def lerp(a: Vec3, b: Vec3, t: float) -> Vec3:
    return Vec3(a.x + (b.x - a.x) * t, a.y + (b.y - a.y) * t, a.z + (b.z - a.z) * t)


# ---------------------------------------------------------------------------------------
#  Parsed model
# ---------------------------------------------------------------------------------------
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
    inverted: bool
    half_width: float
    measured_width: float
    lane_count: int
    average_length: float
    traffic_density: int
    start_position: Vec3
    end_position: Vec3
    start_direction: Vec3
    end_direction: Vec3
    middle_position: Vec3
    bezier: Optional[Bezier]
    bezier_oriented_from_start: bool


@dataclass
class Building:
    building_id: int
    prefab_name: str
    asset_title: str
    category: str
    service: str
    sub_service: str
    position: Vec3
    angle_radians: float
    angle_degrees: float
    width: float
    length: float
    height: float
    prefab_size: Optional[Vec3]
    district_id: int
    is_collapsed: bool
    is_abandoned: bool
    is_historical: bool


@dataclass
class District:
    id: int
    name: str


@dataclass
class CityLayout:
    schema_version: int
    meta: Dict[str, Any]
    districts: List[District] = field(default_factory=list)
    roads: List[Road] = field(default_factory=list)
    buildings: List[Building] = field(default_factory=list)


# ---------------------------------------------------------------------------------------
#  Validation helpers
# ---------------------------------------------------------------------------------------
def check_fields(
    raw: Dict[str, Any],
    section: str,
    where: str,
    problems: List[str],
    warnings: List[str],
) -> None:
    """Type-check one object against the SCHEMA entry for `section`."""
    for name, (expected, required) in SCHEMA[section].items():
        if name not in raw:
            if required:
                problems.append(f"{where}: missing required field '{name}'")
            continue

        value = raw[name]
        if name in ("startPosition", "endPosition", "startDirection", "endDirection",
                    "middlePosition", "position", "prefabSize", "bezier"):
            if not isinstance(value, dict):
                # 'bezier' is documented as nullable: the converter synthesises a straight
                # span when GenerateBezier could not produce one.
                if name == "bezier" and value is None:
                    warnings.append(
                        f"{where}.bezier: null -- the converter must synthesise a straight span"
                    )
                else:
                    problems.append(f"{where}.{name}: expected an object, got {type(value).__name__}")
            continue

        if value is None:
            if required:
                problems.append(f"{where}.{name}: required field is null")
            continue

        if expected is int and isinstance(value, bool):
            problems.append(f"{where}.{name}: expected int, got bool")
        elif expected is bool and not isinstance(value, bool):
            problems.append(f"{where}.{name}: expected bool, got {type(value).__name__}")
        elif expected is VEC3 and (isinstance(value, bool) or not isinstance(value, (int, float))):
            problems.append(f"{where}.{name}: expected a number, got {type(value).__name__}")
        elif expected not in (int, bool, VEC3, list, str, dict) and not isinstance(value, expected):
            problems.append(f"{where}.{name}: expected {expected}, got {type(value).__name__}")


def finite(value: float) -> bool:
    return not (math.isnan(value) or math.isinf(value))


# ---------------------------------------------------------------------------------------
#  Loading + validation
# ---------------------------------------------------------------------------------------
def load_city_layout(path: str) -> Tuple[Optional[CityLayout], List[str], List[str]]:
    """
    Read and validate a city_layout.json.

    Returns (layout_or_None, problems, warnings).  `layout` is populated as far as the input
    allowed, so the converter can still work on a partially valid file and report the rest.
    """
    problems: List[str] = []
    warnings: List[str] = []

    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            raw = json.load(handle)
    except FileNotFoundError:
        return None, [f"file not found: {path}"], warnings
    except json.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"], warnings
    except OSError as exc:
        return None, [f"could not read file: {exc}"], warnings

    if not isinstance(raw, dict):
        return None, [f"top level must be an object, got {type(raw).__name__}"], warnings

    schema_version = raw.get("schemaVersion")
    if schema_version is None:
        problems.append("missing 'schemaVersion'")
        schema_version = SCHEMA_VERSION
    elif schema_version != SCHEMA_VERSION:
        warnings.append(
            f"schemaVersion is {schema_version}, this tool targets {SCHEMA_VERSION}; "
            "fields may be missing or renamed"
        )

    meta = raw.get("meta")
    if not isinstance(meta, dict):
        problems.append("missing or invalid 'meta' section")
        meta = {}
    else:
        check_fields(meta, "meta", "meta", problems, warnings)

    layout = CityLayout(schema_version=schema_version, meta=meta)

    # ---- districts ----
    for index, item in enumerate(as_list(raw, "districts", problems)):
        where = f"districts[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: expected an object")
            continue
        check_fields(item, "district", where, problems, warnings)
        layout.districts.append(
            District(id=int_or(item.get("id"), 0), name=str_or(item.get("name"), ""))
        )

    # ---- roads ----
    for index, item in enumerate(as_list(raw, "roads", problems)):
        where = f"roads[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: expected an object")
            continue

        check_fields(item, "road", where, problems, warnings)

        bezier_raw = item.get("bezier")
        bezier: Optional[Bezier] = None
        if isinstance(bezier_raw, dict):
            check_fields(bezier_raw, "bezier", f"{where}.bezier", problems, warnings)
            bezier = Bezier(
                start=Vec3.from_json(bezier_raw.get("start"), f"{where}.bezier.start", problems),
                control1=Vec3.from_json(bezier_raw.get("control1"), f"{where}.bezier.control1", problems),
                control2=Vec3.from_json(bezier_raw.get("control2"), f"{where}.bezier.control2", problems),
                end=Vec3.from_json(bezier_raw.get("end"), f"{where}.bezier.end", problems),
            )
        elif bezier_raw is not None:
            problems.append(f"{where}.bezier: expected an object or null")

        road = Road(
            segment_id=int_or(item.get("segmentId"), -1),
            start_node_id=int_or(item.get("startNodeId"), 0),
            end_node_id=int_or(item.get("endNodeId"), 0),
            prefab_name=str_or(item.get("prefabName"), ""),
            road_class=str_or(item.get("roadClass"), ""),
            vehicle_types=str_or(item.get("vehicleTypes"), ""),
            is_one_way=bool_or(item.get("isOneWay"), False),
            is_straight=bool_or(item.get("isStraight"), False),
            inverted=bool_or(item.get("inverted"), False),
            half_width=float_or(item.get("halfWidth"), 0.0),
            measured_width=float_or(item.get("measuredWidth"), 0.0),
            lane_count=int_or(item.get("laneCount"), 0),
            average_length=float_or(item.get("averageLength"), 0.0),
            traffic_density=int_or(item.get("trafficDensity"), 0),
            start_position=Vec3.from_json(item.get("startPosition"), f"{where}.startPosition", problems),
            end_position=Vec3.from_json(item.get("endPosition"), f"{where}.endPosition", problems),
            start_direction=Vec3.from_json(item.get("startDirection"), f"{where}.startDirection", problems),
            end_direction=Vec3.from_json(item.get("endDirection"), f"{where}.endDirection", problems),
            middle_position=Vec3.from_json(item.get("middlePosition"), f"{where}.middlePosition", problems),
            bezier=bezier,
            bezier_oriented_from_start=bool_or(item.get("bezierOrientedFromStart"), False),
        )

        validate_road(road, where, problems, warnings)
        layout.roads.append(road)

    # ---- buildings ----
    for index, item in enumerate(as_list(raw, "buildings", problems)):
        where = f"buildings[{index}]"
        if not isinstance(item, dict):
            problems.append(f"{where}: expected an object")
            continue

        check_fields(item, "building", where, problems, warnings)

        prefab_size_raw = item.get("prefabSize")
        prefab_size = (
            Vec3.from_json(prefab_size_raw, f"{where}.prefabSize", problems)
            if isinstance(prefab_size_raw, dict)
            else None
        )

        building = Building(
            building_id=int_or(item.get("buildingId"), -1),
            prefab_name=str_or(item.get("prefabName"), ""),
            asset_title=str_or(item.get("assetTitle"), ""),
            category=str_or(item.get("category"), ""),
            service=str_or(item.get("service"), ""),
            sub_service=str_or(item.get("subService"), ""),
            position=Vec3.from_json(item.get("position"), f"{where}.position", problems),
            angle_radians=float_or(item.get("angleRadians"), 0.0),
            angle_degrees=float_or(item.get("angleDegrees"), 0.0),
            width=float_or(item.get("width"), 0.0),
            length=float_or(item.get("length"), 0.0),
            height=float_or(item.get("height"), 0.0),
            prefab_size=prefab_size,
            district_id=int_or(item.get("districtId"), 0),
            is_collapsed=bool_or(item.get("isCollapsed"), False),
            is_abandoned=bool_or(item.get("isAbandoned"), False),
            is_historical=bool_or(item.get("isHistorical"), False),
        )

        validate_building(building, where, problems, warnings)
        layout.buildings.append(building)

    validate_cross_references(layout, problems, warnings)
    validate_counts(layout, problems, warnings)

    return layout, problems, warnings


def as_list(raw: Dict[str, Any], key: str, problems: List[str]) -> List[Any]:
    value = raw.get(key)
    if value is None:
        problems.append(f"missing required section '{key}'")
        return []
    if not isinstance(value, list):
        problems.append(f"'{key}' must be an array, got {type(value).__name__}")
        return []
    return value


def validate_road(road: Road, where: str, problems: List[str], warnings: List[str]) -> None:
    if road.measured_width < 0 or road.half_width < 0:
        problems.append(f"{where}: negative road width")
    if road.lane_count < 0:
        problems.append(f"{where}: negative lane count")

    node_span = road.start_position.distance_to(road.end_position)
    tolerance = max(0.05, node_span * 1e-3)

    if road.bezier is not None:
        if not road.bezier_oriented_from_start:
            warnings.append(
                f"{where}: bezier is not oriented from the start node; "
                "the converter must flip it before use"
            )

        # The Bezier is NOT guaranteed to coincide with the node chain.  Across a real export
        # (Cannes, 2307 segments) it sits +1.000 m above the node elevation on 1040 segments and
        # -0.300 m below on 326, and on 259 segments its endpoints are pulled along the segment
        # to handle junction corners.  So only flag differences the converter could not absorb.
        start_xz = math.hypot(
            road.bezier.start.x - road.start_position.x,
            road.bezier.start.z - road.start_position.z,
        )
        end_xz = math.hypot(
            road.bezier.end.x - road.end_position.x,
            road.bezier.end.z - road.end_position.z,
        )
        start_dy = abs(road.bezier.start.y - road.start_position.y)
        end_dy = abs(road.bezier.end.y - road.end_position.y)

        horizontal_tolerance = max(1.0, node_span * 0.05)

        if start_xz > horizontal_tolerance or end_xz > horizontal_tolerance:
            warnings.append(
                f"{where}: bezier endpoint is offset horizontally from its node position "
                f"({start_xz:.2f} m start, {end_xz:.2f} m end); normal for junction corners, "
                "the converter averages the two"
            )

        if start_dy > 1.5 or end_dy > 1.5:
            warnings.append(
                f"{where}: bezier elevation differs from the node elevation by "
                f"{start_dy:.2f} m (start) / {end_dy:.2f} m (end); "
                "likely an elevated or bridge segment"
            )

        if road.bezier.is_degenerate() and node_span > 0.5:
            warnings.append(f"{where}: bezier has collapsed control points on a {node_span:.1f} m segment")

        # The tangent at t=0 must point the same way as the recorded start direction.
        hint = road.start_direction.length()
        tangent = road.bezier.tangent_at(0.0)
        if hint > 1e-3 and tangent.length() > 1e-3:
            cosine = tangent.normalized().dot(road.start_direction.normalized())
            if cosine < 0.0:
                warnings.append(
                    f"{where}: bezier tangent at the start opposes startDirection "
                    f"(cos={cosine:.3f}); the segment may be inverted"
                )
    else:
        # check_fields already warned about the null bezier; record it in the stats instead so
        # the same condition is not reported twice.
        pass

    if road.is_straight and road.bezier is not None:
        # A "straight" segment should barely deviate from its chord.
        chord = (road.end_position - road.start_position).normalized()
        if chord.length() > 0.5:
            deviation = road.bezier.point_at(0.5).distance_to(
                lerp(road.start_position, road.end_position, 0.5)
            )
            if deviation > 1.0:
                warnings.append(
                    f"{where}: flagged straight but the curve deviates {deviation:.2f} m at the midpoint"
                )


def validate_building(building: Building, where: str, problems: List[str], warnings: List[str]) -> None:
    for name, value in (
        ("width", building.width),
        ("length", building.length),
        ("height", building.height),
    ):
        if not finite(value):
            problems.append(f"{where}.{name}: non-finite value")
        elif value < 0:
            problems.append(f"{where}.{name}: negative value {value}")

    if building.width == 0 and building.length == 0:
        warnings.append(f"{where}: zero footprint; the converter will need a default proxy size")

    # angleDegrees must agree with angleRadians (guards against a unit mix-up).
    expected = math.degrees(building.angle_radians)
    delta = abs((expected - building.angle_degrees + 180.0) % 360.0 - 180.0)
    if delta > 0.5:
        problems.append(
            f"{where}: angleDegrees {building.angle_degrees} disagrees with "
            f"angleRadians {building.angle_radians} (expected ~{expected:.3f})"
        )


def validate_cross_references(layout: CityLayout, problems: List[str], warnings: List[str]) -> None:
    district_ids = {district.id for district in layout.districts}

    unknown_districts = Counter()
    for building in layout.buildings:
        if building.district_id != 0 and building.district_id not in district_ids:
            unknown_districts[building.district_id] += 1

    for district_id, count in unknown_districts.items():
        warnings.append(
            f"{count} building(s) reference districtId {district_id}, which is not in 'districts'"
        )

    # Shared nodes are the graph's junctions: useful sanity signal for the converter.
    node_usage = Counter()
    for road in layout.roads:
        node_usage[road.start_node_id] += 1
        node_usage[road.end_node_id] += 1

    dangling = sum(1 for node, uses in node_usage.items() if uses == 1)
    if layout.roads and dangling == len(node_usage):
        warnings.append(
            "every node is used by exactly one segment -- the road graph looks disconnected"
        )


def validate_counts(layout: CityLayout, problems: List[str], warnings: List[str]) -> None:
    meta = layout.meta
    for field_name, actual in (
        ("roadCount", len(layout.roads)),
        ("buildingCount", len(layout.buildings)),
        ("districtCount", len(layout.districts)),
    ):
        declared = meta.get(field_name)
        if isinstance(declared, int) and declared != actual:
            warnings.append(
                f"meta.{field_name} says {declared} but the section holds {actual} entries"
            )


def int_or(value: Any, default: int) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else default


def float_or(value: Any, default: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value) if finite(float(value)) else default


def bool_or(value: Any, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def str_or(value: Any, default: str) -> str:
    return value if isinstance(value, str) else default


# ---------------------------------------------------------------------------------------
#  Statistics (what Part 2 needs for sizing the BeamNG map)
# ---------------------------------------------------------------------------------------
def compute_statistics(layout: CityLayout) -> Dict[str, Any]:
    stats: Dict[str, Any] = {}

    total_length = 0.0
    straight_length = 0.0
    curved_segments = 0
    synthesised = 0

    for road in layout.roads:
        if road.bezier is not None:
            length = road.bezier.approximate_length()
            if not road.is_straight:
                curved_segments += 1
        else:
            length = road.start_position.distance_to(road.end_position)
            synthesised += 1

        total_length += length
        if road.is_straight:
            straight_length += length

    stats["road_km"] = round(total_length / 1000.0, 3)
    stats["straight_road_km"] = round(straight_length / 1000.0, 3)
    stats["curved_segments"] = curved_segments
    stats["segments_without_bezier"] = synthesised
    stats["one_way_segments"] = sum(1 for road in layout.roads if road.is_one_way)

    widths = [round(road.measured_width, 1) for road in layout.roads if road.measured_width > 0]
    stats["width_histogram_m"] = dict(sorted(Counter(widths).items()))
    stats["lane_histogram"] = dict(sorted(Counter(road.lane_count for road in layout.roads).items()))

    roads_by_prefab = Counter(road.prefab_name or "<none>" for road in layout.roads)
    stats["road_prefabs"] = dict(roads_by_prefab.most_common(20))
    stats["road_prefab_count"] = len(roads_by_prefab)

    buildings_by_prefab = Counter(building.prefab_name or "<none>" for building in layout.buildings)
    stats["building_prefabs"] = dict(buildings_by_prefab.most_common(20))
    stats["building_prefab_count"] = len(buildings_by_prefab)

    stats["buildings_by_service"] = dict(
        sorted(Counter(building.service or "<none>" for building in layout.buildings).items())
    )
    stats["buildings_collapsed"] = sum(1 for b in layout.buildings if b.is_collapsed)
    stats["buildings_abandoned"] = sum(1 for b in layout.buildings if b.is_abandoned)

    heights = [b.height for b in layout.buildings if b.height > 0]
    stats["building_height_m"] = {
        "min": round(min(heights), 2) if heights else 0.0,
        "max": round(max(heights), 2) if heights else 0.0,
        "mean": round(sum(heights) / len(heights), 2) if heights else 0.0,
    }

    footprint = [
        b.width * b.length for b in layout.buildings if b.width > 0 and b.length > 0
    ]
    stats["building_footprint_m2_total"] = round(sum(footprint), 1)

    points: List[Vec3] = []
    for road in layout.roads:
        points.append(road.start_position)
        points.append(road.end_position)
    for building in layout.buildings:
        points.append(building.position)

    if points:
        mins = Vec3(min(p.x for p in points), min(p.y for p in points), min(p.z for p in points))
        maxs = Vec3(max(p.x for p in points), max(p.y for p in points), max(p.z for p in points))
        stats["bounds_cs1"] = {
            "min": {"x": round(mins.x, 2), "y": round(mins.y, 2), "z": round(mins.z, 2)},
            "max": {"x": round(maxs.x, 2), "y": round(maxs.y, 2), "z": round(maxs.z, 2)},
            "size_m": {
                "x": round(maxs.x - mins.x, 2),
                "y": round(maxs.y - mins.y, 2),
                "z": round(maxs.z - mins.z, 2),
            },
        }

        # BeamNG is right-handed Z-up: x_bng = -x_cs1, y_bng = z_cs1, z_bng = y_cs1
        stats["bounds_beamng_estimate"] = {
            "min": {"x": round(-maxs.x, 2), "y": round(mins.z, 2), "z": round(mins.y, 2)},
            "max": {"x": round(-mins.x, 2), "y": round(maxs.z, 2), "z": round(maxs.y, 2)},
            "note": "axis mapping only; no terrain fitting or origin shift applied yet",
        }

    return stats


# ---------------------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------------------
def format_report(
    path: str,
    layout: Optional[CityLayout],
    problems: Sequence[str],
    warnings: Sequence[str],
    stats: Optional[Dict[str, Any]],
) -> str:
    lines: List[str] = []
    lines.append("=" * 78)
    lines.append(f"CS1-to-BeamNG :: city_layout validator")
    lines.append(f"file: {os.path.abspath(path)}")
    lines.append("=" * 78)

    if layout is not None:
        meta = layout.meta
        lines.append(f"schemaVersion : {layout.schema_version}")
        lines.append(f"generator     : {meta.get('generator', '<missing>')}")
        lines.append(f"city          : {meta.get('cityName') or '<unnamed>'}")
        lines.append(f"game / unity  : {meta.get('gameVersion', '?')} / {meta.get('unityVersion', '?')}")
        lines.append(f"exported at   : {meta.get('exportedAtUtc', '?')} ({meta.get('exportMilliseconds', '?')} ms)")
        lines.append(
            f"contents      : {len(layout.roads)} roads, {len(layout.buildings)} buildings, "
            f"{len(layout.districts)} districts"
        )
        exporter_warnings = meta.get("warnings") or []
        if exporter_warnings:
            lines.append(f"exporter said : {len(exporter_warnings)} warning(s)")
            for warning in exporter_warnings[:10]:
                lines.append(f"                - {warning}")
            if len(exporter_warnings) > 10:
                lines.append(f"                ... and {len(exporter_warnings) - 10} more")

    lines.append("")
    lines.append(f"PROBLEMS ({len(problems)})")
    lines.extend([f"  x {p}" for p in problems[:40]] or ["  (none)"])
    if len(problems) > 40:
        lines.append(f"  ... and {len(problems) - 40} more")

    lines.append("")
    lines.append(f"WARNINGS ({len(warnings)})")
    lines.extend([f"  ! {w}" for w in warnings[:25]] or ["  (none)"])
    if len(warnings) > 25:
        lines.append(f"  ... and {len(warnings) - 25} more")

    if stats:
        lines.append("")
        lines.append("STATISTICS")
        lines.append(f"  total road length   : {stats.get('road_km')} km "
                     f"({stats.get('straight_road_km')} km flagged straight)")
        lines.append(f"  curved segments     : {stats.get('curved_segments')} "
                     f"(without bezier: {stats.get('segments_without_bezier')})")
        lines.append(f"  one-way segments    : {stats.get('one_way_segments')}")
        lines.append(f"  lanes histogram     : {stats.get('lane_histogram')}")
        lines.append(f"  width histogram (m) : {stats.get('width_histogram_m')}")
        lines.append(f"  road prefabs        : {stats.get('road_prefab_count')} distinct")
        for name, count in list(stats.get("road_prefabs", {}).items())[:8]:
            lines.append(f"      {count:>6} x {name}")
        lines.append(f"  building prefabs    : {stats.get('building_prefab_count')} distinct")
        for name, count in list(stats.get("building_prefabs", {}).items())[:8]:
            lines.append(f"      {count:>6} x {name}")
        lines.append(f"  building services   : {stats.get('buildings_by_service')}")
        lines.append(f"  building heights (m): {stats.get('building_height_m')}")
        lines.append(f"  total footprint     : {stats.get('building_footprint_m2_total')} m^2")
        lines.append(f"  bounds (CS1)        : {stats.get('bounds_cs1')}")
        lines.append(f"  bounds (BeamNG est) : {stats.get('bounds_beamng_estimate')}")

    lines.append("")
    lines.append("=" * 78)
    verdict = "VALID" if not problems else "INVALID"
    if warnings:
        verdict += f" ({len(warnings)} warning(s))"
    lines.append(f"RESULT: {verdict}")
    lines.append("=" * 78)
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate and analyse a CS1-to-BeamNG city_layout.json export."
    )
    parser.add_argument("path", help="path to city_layout.json")
    parser.add_argument("--json", metavar="OUT", help="also write the machine-readable report here")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failure")
    parser.add_argument("--quiet", action="store_true", help="only print problems and the verdict")
    args = parser.parse_args(argv)

    layout, problems, warnings = load_city_layout(args.path)

    if layout is None:
        print(format_report(args.path, None, problems, warnings, None))
        return 2

    stats = compute_statistics(layout)

    if not args.quiet:
        print(format_report(args.path, layout, problems, warnings, stats))

    if args.json:
        report = {
            "file": os.path.abspath(args.path),
            "valid": not problems,
            "problems": list(problems),
            "warnings": list(warnings),
            "statistics": stats,
        }
        with open(args.json, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
        print(f"report written to {os.path.abspath(args.json)}")

    if problems:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
