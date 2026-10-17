import math
import os
import random
import shutil
import sys

import bpy
from mathutils import Euler, Vector


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT = os.path.join(ROOT, "output")
MODEL_PATH = os.path.join(OUTPUT, "building.glb")
SOURCE_BACKUP = os.path.join(OUTPUT, "building_source.glb")
BLEND_PATH = os.path.join(OUTPUT, "building_render.blend")
IMAGE_PATH = os.path.join(OUTPUT, "building_hero.png")
PREVIEW_PATH = os.path.join(OUTPUT, "building_preview.png")
PREVIEW = "--preview" in sys.argv
MODEL_ONLY = "--model-only" in sys.argv
VIEW_FILTER = None
if "--view" in sys.argv:
    view_index = sys.argv.index("--view") + 1
    if view_index >= len(sys.argv):
        raise ValueError("--view requires a view name")
    VIEW_FILTER = sys.argv[view_index]
VIEWS = "--views" in sys.argv or VIEW_FILTER is not None
LOW_QUALITY = PREVIEW or MODEL_ONLY or VIEWS
FLOOR_HEIGHT = 3.0
BASEMENT_TOP = 1.5
FLOORS = 13
random.seed(417)


def material(name, color, roughness=0.8, metallic=0.0):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = (*color, 1)
    mat.use_nodes = True
    shader = mat.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return mat


def aged_plaster():
    mat = material("Aged ivory mineral plaster", (0.59, 0.55, 0.45), 0.92)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    shader = nodes.get("Principled BSDF")
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 12.0
    noise.inputs["Detail"].default_value = 4
    noise.inputs["Roughness"].default_value = 0.78
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.19
    ramp.color_ramp.elements[0].color = (0.37, 0.34, 0.27, 1)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (0.68, 0.63, 0.52, 1)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.11
    bump.inputs["Distance"].default_value = 0.025
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


MATERIALS = {}
BATCHES = {}
MODEL_OBJECTS = []
FOOTPRINT = [
    (13.94, 15.20), (3.17, 15.18), (3.18, 12.97), (0.45, 12.97),
    (0.46, 7.72), (-3.56, 7.72), (-3.54, 0.52), (-8.65, 0.42),
    (-8.66, 3.34), (-13.41, 3.33), (-13.41, 0.71), (-17.22, 0.70),
    (-17.19, -11.96), (-13.95, -11.96), (-13.94, -14.20),
    (-3.17, -14.18), (-3.18, -11.97), (-0.45, -11.97),
    (-0.46, -6.72), (3.56, -6.72), (3.54, 0.48), (8.65, 0.58),
    (8.66, -2.34), (13.41, -2.33), (13.41, 0.29), (17.22, 0.30),
    (17.19, 12.96), (13.95, 12.96),
]
BALCONY_EDGE = 18


def add_box(floor, mat_key, center, size, rotation=(0, 0, 0)):
    key = (floor, mat_key)
    batch = BATCHES.get(key)
    if batch is None:
        batch = {"vertices": [], "faces": []}
        BATCHES[key] = batch
    c = Vector(center)
    half = Vector(size) * 0.5
    rot = Euler(rotation).to_matrix()
    corners = [
        (-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1),
        (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1),
    ]
    base = len(batch["vertices"])
    batch["vertices"].extend(
        tuple(c + rot @ Vector((sx * half.x, sy * half.y, sz * half.z)))
        for sx, sy, sz in corners
    )
    batch["faces"].extend(
        (tuple(base + index for index in face) for face in
         ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
          (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)))
    )


def make_mesh(name, vertices, faces, mat, floor=None):
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    MODEL_OBJECTS.append(obj)
    if floor is not None:
        obj.name = "Floor_%02d_%s" % (floor, name)
    return obj


def add_disc(name, center, radius, mat, floor, segments=40, depth=0.08):
    cx, cy, cz = center
    vertices = []
    for y in (-depth / 2, depth / 2):
        vertices.extend(
            (cx + radius * math.cos(i * math.tau / segments),
             cy + y,
             cz + radius * math.sin(i * math.tau / segments))
            for i in range(segments)
        )
    faces = [tuple(range(segments)), tuple(range(segments, 2 * segments))]
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, j + segments, i + segments))
    return make_mesh(name, vertices, faces, mat, floor)


def add_ring(name, center, outer_radius, inner_radius, mat, floor, segments=40):
    cx, cy, cz = center
    vertices = []
    for radius in (outer_radius, inner_radius):
        vertices.extend(
            (cx + radius * math.cos(i * math.tau / segments), cy,
             cz + radius * math.sin(i * math.tau / segments))
            for i in range(segments)
        )
    faces = []
    for i in range(segments):
        j = (i + 1) % segments
        faces.append((i, j, segments + j, segments + i))
    return make_mesh(name, vertices, faces, mat, floor)


def edge_basis(edge_index):
    start = Vector(FOOTPRINT[edge_index])
    end = Vector(FOOTPRINT[(edge_index + 1) % len(FOOTPRINT)])
    tangent = (end - start).normalized()
    inward = Vector((-tangent.y, tangent.x))
    return start, end, tangent, inward, (end - start).length


def edge_box(floor, key, edge_index, along, z, width, height, depth, outward=0.0):
    start, _, tangent, inward, _ = edge_basis(edge_index)
    boundary = start + tangent * along
    center = boundary - inward * (outward + depth / 2)
    add_box(floor, key, (center.x, center.y, z), (width, depth, height),
            (0, 0, math.atan2(tangent.y, tangent.x)))


def make_prism(name, z_bottom, z_top, mat, floor=None):
    count = len(FOOTPRINT)
    vertices = [(x, y, z_bottom) for x, y in FOOTPRINT]
    vertices.extend((x, y, z_top) for x, y in FOOTPRINT)
    faces = [tuple(reversed(range(count))), tuple(range(count, count * 2))]
    for index in range(count):
        following = (index + 1) % count
        faces.append((index, following, following + count, index + count))
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(mat)
    mesh.validate(verbose=False)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    if floor is not None:
        obj.name = "Floor_%02d" % floor
    MODEL_OBJECTS.append(obj)
    return obj


def build_edge_window(floor, edge_index, along, z, width, height, frame_key):
    warm = ((floor or 0) * 13 + edge_index * 3 + round(along * 2)) % 17 == 0
    edge_box(floor, "reveal", edge_index, along, z, width + 0.24, height + 0.25,
             0.055, -0.050)
    edge_box(floor, "glass_warm" if warm else "glass", edge_index, along, z,
             width - 0.14, height - 0.14, 0.055, -0.040)
    bar = 0.075
    for vertical_offset in (-height / 2 + bar / 2, height / 2 - bar / 2):
        edge_box(floor, frame_key, edge_index, along, z + vertical_offset,
                 width, bar, 0.11, -0.075)
    for horizontal_offset in (-width / 2 + bar / 2, width / 2 - bar / 2):
        edge_box(floor, frame_key, edge_index, along + horizontal_offset, z,
                 bar, height, 0.11, -0.075)
    edge_box(floor, "frame_repaired", edge_index, along, z,
             0.035, height - 0.14, 0.055, -0.015)
    edge_box(floor, "sills", edge_index, along, z - height / 2 - 0.075,
             width + 0.18, 0.12, 0.22, -0.175)

    if (((floor or 0) * 7 + edge_index * 5 + round(along)) % 11) == 0:
        edge_box(floor, "metal", edge_index, along + width * 0.38,
                 z - height / 2 - 0.25, 0.70, 0.36, 0.42, 0.28)


def add_edge_balcony(floor, edge_index, along, width, depth, base_z, railing=True):
    start, _, tangent, inward, _ = edge_basis(edge_index)
    outward = -inward
    point = start + tangent * along
    center = point + outward * depth / 2
    angle = math.atan2(tangent.y, tangent.x)
    add_box(floor, "concrete", (center.x, center.y, base_z + 0.13),
            (width, depth, 0.24), (0, 0, angle))
    if not railing:
        return
    rail_center = point + outward * (depth - 0.10)
    rail_z = base_z + 1.10

    def rail_box(position, along_axis, box_width, box_depth, box_height, box_z):
        add_box(floor, "metal", (position.x, position.y, box_z),
                (box_width, box_depth, box_height), (0, 0, angle))

    rail_box(rail_center, tangent, width, 0.055, 0.07, rail_z + 0.36)
    rail_box(rail_center, tangent, width, 0.045, 0.05, rail_z - 0.08)
    count = max(5, round(width / 0.26))
    for index in range(count + 1):
        position = rail_center + tangent * (-width / 2 + width * index / count)
        rail_box(position, tangent, 0.035, 0.035, 0.46, rail_z + 0.14)
    for side in (-1, 1):
        side_center = point + tangent * (side * (width / 2 - 0.02)) + outward * depth / 2
        rail_box(side_center, tangent, depth, 0.045, 0.07, rail_z + 0.36)
        rail_box(side_center, tangent, depth, 0.035, 0.05, rail_z - 0.08)
        for index in range(1, max(3, round(depth / 0.28))):
            position = point + tangent * (side * (width / 2 - 0.02)) + outward * (depth * index / max(3, round(depth / 0.28)))
            rail_box(position, tangent, 0.035, 0.035, 0.46, rail_z + 0.14)


def add_stair_flight(floor, base_z, x_side):
    tread_mat = "concrete"
    steps = 10
    run = 2.2
    rise = 1.38
    start_y = -11.55
    end_y = start_y + run
    step_depth = run / steps
    for index in range(steps):
        y = start_y + step_depth * (index + 0.5)
        z = base_z + 0.17 + rise * (index + 0.5) / steps
        x = x_side
        add_box(floor, tread_mat, (x, y, z), (0.84, step_depth + 0.035, 0.16))
    add_box(floor, "metal", (x_side, (start_y + end_y) / 2, base_z + rise / 2 + 0.17),
            (0.045, run, 0.045), (math.atan2(rise, run), 0, 0))


def point_in_footprint(x, y):
    inside = False
    previous = FOOTPRINT[-1]
    for current in FOOTPRINT:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y):
            crossing_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < crossing_x:
                inside = not inside
        previous = current
    return inside


def place_roof_box_inside(name, preferred, size, mat_key):
    half_x, half_y = size[0] / 2, size[1] / 2
    min_x = min(point[0] for point in FOOTPRINT) + half_x + 0.2
    max_x = max(point[0] for point in FOOTPRINT) - half_x - 0.2
    min_y = min(point[1] for point in FOOTPRINT) + half_y + 0.2
    max_y = max(point[1] for point in FOOTPRINT) - half_y - 0.2
    candidates = []
    x = min_x
    while x <= max_x:
        y = min_y
        while y <= max_y:
            if all(
                point_in_footprint(x + dx, y + dy)
                for dx in (-half_x, 0, half_x)
                for dy in (-half_y, 0, half_y)
            ) and all(
                point_in_footprint(x + dx, y + dy)
                for dx in (-half_x, 0, half_x)
                for dy in (-half_y, 0, half_y)
                if dx == 0 or dy == 0
            ):
                distance = (x - preferred[0]) ** 2 + (y - preferred[1]) ** 2
                candidates.append((distance, x, y))
            y += 0.4
        x += 0.4
    if not candidates:
        raise RuntimeError("Rooftop object does not fit inside building footprint: " + name)
    _, x, y = min(candidates)
    add_box(None, mat_key, (x, y, preferred[2]), size)


def build_building():
    plaster = aged_plaster()
    MATERIALS.update({
        "wall": plaster,
        "concrete": material("Exposed weathered concrete", (0.62, 0.60, 0.52), 0.91),
        "band": material("Panel edges and floor bands", (0.67, 0.64, 0.55), 0.9),
        "joint": material("Recessed panel joints", (0.38, 0.37, 0.33), 0.95),
        "repair": material("Uneven repaint patches", (0.81, 0.78, 0.68), 0.92),
        "frame": material("Old ivory window frames", (0.83, 0.80, 0.70), 0.6),
        "frame_repaired": material("Replaced pale blue window frames", (0.58, 0.68, 0.68), 0.55),
        "glass": material("Smoky blue window glass", (0.10, 0.19, 0.25), 0.2, 0.22),
        "glass_warm": material("Warm occupied window glass", (0.26, 0.23, 0.16), 0.28, 0.1),
        "reveal": material("Deep window recess", (0.19, 0.20, 0.19), 0.9),
        "sills": material("Concrete window sills", (0.70, 0.67, 0.57), 0.86),
        "metal": material("Dark iron railings and frames", (0.13, 0.17, 0.18), 0.45, 0.55),
        "metal_dark": material("AC grille shadow", (0.045, 0.06, 0.065), 0.7, 0.18),
        "roof": material("Aged black roof membrane", (0.08, 0.09, 0.085), 0.94),
        "roof_edge": material("Roof parapets", (0.57, 0.55, 0.48), 0.9),
        "entry_glass": material("Entrance glazing", (0.075, 0.14, 0.17), 0.2, 0.22),
        "canopy": material("Dark blue entrance canopy", (0.055, 0.10, 0.16), 0.78),
        "cloth_blue": material("Faded blue laundry", (0.28, 0.40, 0.44), 0.96),
        "cloth_white": material("Sunlit hanging laundry", (0.72, 0.69, 0.58), 0.96),
        "cloth_rust": material("Faded terracotta laundry", (0.48, 0.25, 0.17), 0.96),
    })

    make_prism("Raised basement plinth", 0, BASEMENT_TOP, MATERIALS["concrete"])
    for floor in range(1, FLOORS + 1):
        z0 = BASEMENT_TOP + (floor - 1) * FLOOR_HEIGHT
        zc = z0 + FLOOR_HEIGHT / 2
        make_prism("Residential storey", z0, z0 + FLOOR_HEIGHT - 0.08,
                   MATERIALS["wall"], floor)
        for edge_index in range(len(FOOTPRINT)):
            _, _, _, _, length = edge_basis(edge_index)
            if length < 1.65:
                continue
            is_side_wall = edge_index in (3, 17)
            is_rear_gallery = edge_index == 6
            is_front_gallery_windows = edge_index == BALCONY_EDGE
            is_projecting_front = edge_index == 14
            is_window_strip_after_three = edge_index == 16
            is_balcony_wing = edge_index == 20
            start, end, _, _, _ = edge_basis(edge_index)
            is_vertical = abs(end.y - start.y) > abs(end.x - start.x)
            count = (
                3 if edge_index in (0, 14)
                else 1 if is_side_wall or is_rear_gallery or is_front_gallery_windows
                or is_window_strip_after_three
                else 0 if is_vertical
                else 3 if is_projecting_front
                else max(1, int(length / 2.65))
            )
            spacing = length / count if count else length
            for bay in range(count):
                along = spacing * (bay + 0.5)
                if floor == FLOORS and edge_index in (0, 14):
                    continue
                if is_rear_gallery:
                    build_edge_window(floor, edge_index, along, z0 + 1.56,
                                      min(3.25, length * 0.68), 2.12, "frame")
                elif is_front_gallery_windows:
                    build_edge_window(floor, edge_index, along, z0 + 1.56,
                                      min(2.05, spacing * 0.68), 1.82, "frame")
                elif is_balcony_wing:
                    build_edge_window(floor, edge_index, along, z0 + 1.56,
                                      min(1.75, spacing * 0.68), 2.16, "frame")
                elif is_side_wall:
                    build_edge_window(floor, edge_index,
                                      length / 2,
                                      z0 + 1.58, min(1.05, length * 0.5),
                                      1.62, "frame")
                elif is_projecting_front:
                    build_edge_window(floor, edge_index, along, z0 + 1.58,
                                      min(1.48, spacing * 0.56), 1.62, "frame")
                elif not is_vertical and length > 2.5:
                    build_edge_window(
                        floor, edge_index, along, z0 + 1.58,
                        min(1.48, spacing * 0.56),
                        1.48 if length < 5 else 1.62,
                        "frame_repaired" if (floor + bay) % 9 == 0 else "frame",
                    )
            edge_box(floor, "band", edge_index, length / 2,
                     z0 + FLOOR_HEIGHT - 0.12, length, 0.10, 0.08, 0.035)
            if length > 3.0:
                for seam in range(1, count):
                    edge_box(floor, "joint", edge_index, spacing * seam,
                             zc, 0.035, FLOOR_HEIGHT - 0.35, 0.035, 0.025)
            if is_rear_gallery:
                add_edge_balcony(floor, edge_index, length / 2,
                                 min(4.85, length * 0.88), 1.35, z0,
                                 railing=True)
            if is_balcony_wing:
                add_edge_balcony(floor, edge_index, length / 2,
                                 min(6.4, length * 0.88), 1.35, z0,
                                 railing=True)
        if floor == FLOORS:
            for edge_index in (0, 14):
                start, _, tangent, inward, length = edge_basis(edge_index)
                outward = -inward
                for fraction in (1 / 6, 0.5, 5 / 6):
                    point = start + tangent * (length * fraction) - outward * 0.035
                    add_disc("Round upper-floor window glass",
                             (point.x, point.y, z0 + FLOOR_HEIGHT / 2), 0.78,
                             MATERIALS["glass"], floor)
                    add_ring("Round upper-floor window surround",
                             (point.x + outward.x * 0.04,
                              point.y + outward.y * 0.04,
                              z0 + FLOOR_HEIGHT / 2),
                             0.96, 0.76, MATERIALS["frame"], floor)

    for edge_index in (12, 14, 18):
        _, _, _, _, length = edge_basis(edge_index)
        count = max(1, int(length / 3.4))
        for bay in range(count):
            along = length * (bay + 0.5) / count
            build_edge_window(None, edge_index, along, BASEMENT_TOP * 0.52,
                              min(1.05, length / count * 0.48), 0.72, "frame")

    roof_z = BASEMENT_TOP + FLOORS * FLOOR_HEIGHT
    make_prism("Irregular roof membrane", roof_z, roof_z + 0.20, MATERIALS["roof"])
    for edge_index in range(len(FOOTPRINT)):
        _, _, _, _, length = edge_basis(edge_index)
        edge_box(None, "roof_edge", edge_index, length / 2, roof_z + 0.36,
                 length, 0.32, 0.22, outward=-0.22)
    add_box(None, "wall", (0.0, 0.8, roof_z + 1.2), (6.0, 6.0, 2.4))
    place_roof_box_inside("Roof service block", (-7.3, -2.0, roof_z + 0.65),
                          (3.6, 2.8, 1.2), "concrete")
    for x, y, height in ((-10.0, -3.8, 1.0), (-7.8, -5.0, 0.8),
                         (3.4, 5.5, 1.0), (10.4, 5.0, 0.9)):
        place_roof_box_inside("Rooftop service unit", (x, y, roof_z + height / 2),
                              (0.72, 0.72, height), "roof_edge")

    # The rear entrance occupies the recessed bay immediately left of the
    # balcony stack; align the stair run with that wall's outward normal.
    entry_edge = 16
    entry_start, _, entry_tangent, entry_inward, entry_length = edge_basis(entry_edge)
    entry_along = entry_length / 2
    entry_boundary = entry_start + entry_tangent * entry_along
    entry_outward = -entry_inward
    entry_x, entry_y = entry_boundary.x, entry_boundary.y
    for offset in (-0.62, 0.0, 0.62):
        edge_box(None, "entry_glass", entry_edge, entry_along + offset,
                 2.60, 0.56, 2.18, 0.07, 0.04)
    edge_box(None, "canopy", entry_edge, entry_along, 4.05,
             2.65, 0.16, 1.55, 0.78)
    for side in (-1, 1):
        edge_box(None, "concrete", entry_edge, entry_along + side * 1.32,
                 3.48, 0.12, 1.18, 0.90, 0.48)
    edge_box(None, "concrete", entry_edge, entry_along, 1.58,
             2.65, 0.22, 1.3, 0.65)
    stair_run = 3.1
    stair_width = 2.15
    for step in range(10):
        distance = 1.45 + stair_run * (step + 0.5) / 10
        point = entry_boundary + entry_outward * distance
        z = BASEMENT_TOP - (BASEMENT_TOP - 0.12) * (step + 0.5) / 10
        add_box(None, "concrete", (point.x, point.y, z),
                (stair_width, stair_run / 10 + 0.035, 0.17),
                (0, 0, math.atan2(entry_tangent.y, entry_tangent.x)))
    for side in (-1, 1):
        rail_point = entry_boundary + entry_outward * (1.45 + stair_run / 2)
        rail_point += entry_tangent * side * (stair_width / 2 + 0.12)
        add_box(None, "metal", (rail_point.x, rail_point.y, 0.92),
                (0.055, stair_run, 0.055),
                (math.atan2(BASEMENT_TOP - 0.12, stair_run), 0,
                 math.atan2(entry_tangent.y, entry_tangent.x)))

    for (floor, key), data in BATCHES.items():
        name = "Facade_%s" % key if floor is not None else "Building_misc_%s" % key
        make_mesh(name, data["vertices"], data["faces"], MATERIALS[key], floor)


def make_cube(name, location, dimensions, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Soft worn edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 3
        obj.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
    return obj


def make_tree(name, x, y, height, palette):
    trunk_mat = material(name + " bark", (0.22, 0.16, 0.10), 0.96)
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=12, radius=0.22, depth=height * 0.62,
        location=(x, y, height * 0.31),
    )
    trunk = bpy.context.object
    trunk.name = name + " trunk"
    trunk.data.materials.append(trunk_mat)
    trunk.modifiers.new("Soft trunk normals", "WEIGHTED_NORMAL")
    for index in range(9):
        z = height * (0.38 + (index % 4) * 0.14)
        ox = math.sin(index * 13.4) * height * 0.20
        oy = math.cos(index * 8.2) * height * 0.16
        radius = height * (0.13 if index < 6 else 0.10)
        bpy.ops.mesh.primitive_ico_sphere_add(
            subdivisions=2, radius=radius,
            location=(x + ox, y + oy, z),
        )
        crown = bpy.context.object
        crown.name = name + " foliage"
        crown.scale = (1.0, 0.92, 1.15)
        crown.data.materials.append(palette[index % len(palette)])
        for face in crown.data.polygons:
            face.use_smooth = True


def make_car(name, x, y, paint):
    body = material(name + " paint", paint, 0.32, 0.12)
    glass = MATERIALS["glass"]
    tire = material(name + " rubber", (0.025, 0.03, 0.032), 0.88)
    hub = material(name + " wheel alloy", (0.36, 0.38, 0.37), 0.3, 0.72)
    make_cube(name + " lower body", (x, y, 0.68), (2.0, 4.35, 0.76), body, 0.22)
    make_cube(name + " cabin", (x, y + 0.12, 1.23), (1.62, 2.18, 0.68), body, 0.20)
    make_cube(name + " windscreen", (x, y - 0.12, 1.25), (1.46, 0.06, 0.47), glass, 0.04)
    make_cube(name + " rear window", (x, y + 1.17, 1.25), (1.42, 0.055, 0.43), glass, 0.04)
    for side in (-1, 1):
        for axle in (-1.35, 1.35):
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=24, radius=0.36, depth=0.23,
                location=(x + side * 0.94, y + axle, 0.44),
                rotation=(0, math.pi / 2, 0),
            )
            wheel = bpy.context.object
            wheel.name = name + " tire"
            wheel.data.materials.append(tire)
            bpy.ops.mesh.primitive_cylinder_add(
                vertices=24, radius=0.19, depth=0.245,
                location=(x + side * 0.95, y + axle, 0.44),
                rotation=(0, math.pi / 2, 0),
            )
            wheel = bpy.context.object
            wheel.name = name + " hub"
            wheel.data.materials.append(hub)
    for side in (-1, 1):
        make_cube(name + " headlight", (x + side * 0.69, y - 2.18, 0.77),
                  (0.42, 0.055, 0.20), MATERIALS["frame"], 0.04)
        make_cube(name + " tail light", (x + side * 0.71, y + 2.18, 0.75),
                  (0.28, 0.05, 0.19), MATERIALS["repair"], 0.03)


def create_site():
    grass = material("Courtyard grass", (0.09, 0.16, 0.07), 1)
    path = material("Old concrete footpath", (0.31, 0.29, 0.24), 0.94)
    asphalt = material("Courtyard asphalt", (0.13, 0.145, 0.14), 0.95)
    curb = material("Curb stone", (0.59, 0.57, 0.50), 0.85)
    make_cube("Ground", (0, -3.2, -0.48), (150, 150, 0.5), grass)
    make_cube("Building apron", (0, -8.8, -0.16), (42, 22, 0.18), path, 0.06)
    make_cube("Parking and street", (0, -24, -0.15), (90, 12, 0.2), asphalt, 0.03)
    make_cube("Front curb", (0, -17.4, -0.04), (90, 0.3, 0.25), curb, 0.04)

    for x in (-18, 17):
        make_tree("Courtyard tree", x, -12, 13, [
            material("Tree leaf green", (0.07, 0.18, 0.045), 0.96),
            material("Tree leaf sunlit", (0.13, 0.23, 0.065), 0.96),
            material("Tree leaf dark", (0.035, 0.11, 0.035), 0.98),
        ])
    for x, color in (
        (-6.3, (0.68, 0.70, 0.69)),
        (-2.1, (0.13, 0.22, 0.38)),
        (2.1, (0.55, 0.16, 0.12)),
        (6.3, (0.40, 0.43, 0.42)),
    ):
        make_car("Parked car", x, -15.3, color)

    pole_mat = material("Street light paint", (0.12, 0.15, 0.15), 0.6, 0.3)
    for x in (-14.5, 14.8):
        bpy.ops.mesh.primitive_cylinder_add(vertices=12, radius=0.095, depth=8,
                                            location=(x, -17.0, 4.0))
        bpy.context.object.name = "Street light pole"
        bpy.context.object.data.materials.append(pole_mat)
        make_cube("Street light arm", (x + (1.15 if x < 0 else -1.15), -17.0, 7.8),
                  (2.5, 0.11, 0.10), pole_mat, 0.04)
        make_cube("Street light head", (x + (2.25 if x < 0 else -2.25), -17.0, 7.7),
                  (0.52, 0.35, 0.17), MATERIALS["frame"], 0.05)

    wire_mat = material("Overhead utility wires", (0.035, 0.045, 0.045), 0.5, 0.25)
    for z in (21.1, 23.2):
        curve = bpy.data.curves.new("Overhead power line", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = 0.018
        curve.bevel_resolution = 2
        spline = curve.splines.new("POLY")
        spline.points.add(2)
        for point, coord in zip(spline.points, (
            (-32, -18.5, z + 0.7, 1),
            (0, -18.7, z - 0.1, 1),
            (32, -18.5, z + 0.7, 1),
        )):
            point.co = coord
        wire = bpy.data.objects.new("Overhead wire", curve)
        bpy.context.collection.objects.link(wire)
        wire.data.materials.append(wire_mat)


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 12 if VIEWS else 20 if LOW_QUALITY else 64
    scene.cycles.use_denoising = True
    scene.cycles.preview_samples = 12
    scene.render.resolution_x = 720 if VIEWS else 960 if LOW_QUALITY else 1600
    scene.render.resolution_y = 870 if VIEWS else 1160 if LOW_QUALITY else 1900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 18
    scene.render.film_transparent = False
    scene.render.filepath = PREVIEW_PATH if LOW_QUALITY else IMAGE_PATH
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = -0.8
    scene.world = bpy.data.worlds.new("Clear Tbilisi daylight")
    scene.world.use_nodes = True
    world_nodes = scene.world.node_tree.nodes
    world_links = scene.world.node_tree.links
    background = world_nodes.get("Background")
    sky = world_nodes.new("ShaderNodeTexSky")
    sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(48)
    sky.sun_rotation = math.radians(135)
    sky.air_density = 0.8
    sky.dust_density = 0.7
    world_links.new(sky.outputs["Color"], background.inputs["Color"])
    background.inputs["Strength"].default_value = 0.35

    bpy.ops.object.light_add(type="SUN", location=(-30, -42, 56))
    sun = bpy.context.object
    sun.name = "Warm late morning sun"
    sun.rotation_euler = (math.radians(29), math.radians(-23), math.radians(-33))
    sun.data.energy = 1.25
    sun.data.angle = math.radians(13)
    bpy.ops.object.light_add(type="AREA", location=(3, -36, 27))
    fill = bpy.context.object
    fill.name = "Soft daylight facade fill"
    fill.data.energy = 500
    fill.data.shape = "DISK"
    fill.data.size = 28
    fill.rotation_euler = (Vector((0, -1, 18)) - fill.location).to_track_quat("-Z", "Y").to_euler()

    camera_data = bpy.data.cameras.new("Reference facade camera")
    camera = bpy.data.objects.new("Reference facade camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (20, -68, 28)
    target = Vector((0, -1.8, 18.4))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 44
    camera_data.sensor_width = 36
    camera_data.dof.use_dof = False
    scene.camera = camera
    scene.render.use_file_extension = True
    scene.render.use_motion_blur = False


def main():
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError("Original building model is missing: " + MODEL_PATH)
    if not os.path.isfile(SOURCE_BACKUP):
        shutil.copy2(MODEL_PATH, SOURCE_BACKUP)

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    build_building()
    create_site()
    setup_scene()

    import json
    with open(os.path.join(OUTPUT, "building_config.json"), "w", encoding="utf-8") as f:
        json.dump({"footprint": FOOTPRINT}, f, indent=2)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    if not PREVIEW and not VIEWS:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in MODEL_OBJECTS:
            obj.select_set(True)
        bpy.context.view_layer.objects.active = MODEL_OBJECTS[0]
        bpy.ops.export_scene.gltf(
            filepath=MODEL_PATH,
            export_format="GLB",
            use_selection=True,
            export_yup=True,
        )
        print("Rebuilt web model:", MODEL_PATH)
    if VIEWS:
        scene = bpy.context.scene
        camera = scene.camera
        target = Vector((0, -0.5, 21))
        views = (
            ("front", (10, -65, 27)),
            ("rear", (-10, 65, 27)),
            ("left", (-65, -1, 27)),
            ("right", (65, 1, 27)),
            ("top", (0, -0.5, 95)),
            ("front_oblique", (-43, -52, 34)),
        )
        camera.data.lens = 44
        for name, position in views:
            if VIEW_FILTER is not None and name != VIEW_FILTER:
                continue
            camera.data.type = "PERSP"
            scene.render.resolution_x = 720
            scene.render.resolution_y = 870
            camera.location = position
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
            if name == "top":
                camera.data.type = "ORTHO"
                camera.data.ortho_scale = 44
                scene.render.resolution_x = 960
                scene.render.resolution_y = 720
                camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
                top_samples = scene.cycles.samples
                scene.cycles.samples = 4
                site_prefixes = (
                    "Building apron", "Parking and street", "Front curb",
                    "Courtyard tree", "Parked car", "Street light", "Overhead wire",
                )
                hidden_for_top = []
                for obj in scene.objects:
                    if obj.name.startswith(site_prefixes):
                        hidden_for_top.append((obj, obj.hide_render))
                        obj.hide_render = True
            else:
                hidden_for_top = []
            scene.render.filepath = os.path.join(OUTPUT, "building_view_%s.png" % name)
            bpy.ops.render.render(write_still=True)
            for obj, was_hidden in hidden_for_top:
                obj.hide_render = was_hidden
            if name == "top":
                scene.cycles.samples = top_samples
            print("View render:", scene.render.filepath)
    elif not MODEL_ONLY:
        bpy.ops.render.render(write_still=True)
        print("Preview render:" if PREVIEW else "Hero render:",
              PREVIEW_PATH if PREVIEW else IMAGE_PATH)
    print("Editable Blender scene:", BLEND_PATH)


if __name__ == "__main__":
    main()
