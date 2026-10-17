import math
import os
import random
import sys

import bpy
from mathutils import Vector


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(ROOT, "output", "building.glb")
BLEND_PATH = os.path.join(ROOT, "output", "building_render.blend")
IMAGE_PATH = os.path.join(ROOT, "output", "building_hero.png")
random.seed(417)


def set_principled(material, color, roughness=0.75, metallic=0.0):
    material.diffuse_color = (*color, 1.0)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1.0)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return shader


def material(name, color, roughness=0.75, metallic=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    set_principled(mat, color, roughness, metallic)
    return mat


def make_weathered_concrete():
    mat = bpy.data.materials.get("Concrete") or bpy.data.materials.new("Concrete")
    shader = set_principled(mat, (0.68, 0.65, 0.56), 0.88)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 38.0
    noise.inputs["Detail"].default_value = 3.0
    noise.inputs["Roughness"].default_value = 0.72
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.22
    ramp.color_ramp.elements[0].color = (0.43, 0.42, 0.37, 1.0)
    ramp.color_ramp.elements[1].position = 0.8
    ramp.color_ramp.elements[1].color = (0.76, 0.73, 0.64, 1.0)
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.13
    bump.inputs["Distance"].default_value = 0.045
    links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], shader.inputs["Base Color"])
    links.new(noise.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], shader.inputs["Normal"])
    return mat


class BoxMesh:
    def __init__(self, name, mat):
        self.name = name
        self.mat = mat
        self.vertices = []
        self.faces = []

    def add(self, center, tangent, normal, width, height, depth):
        c = Vector(center)
        t = Vector((tangent[0], tangent[1], 0.0)).normalized()
        n = Vector((normal[0], normal[1], 0.0)).normalized()
        z = Vector((0.0, 0.0, 1.0))
        start = len(self.vertices)
        for side_z in (-0.5, 0.5):
            for side_n in (-0.5, 0.5):
                for side_t in (-0.5, 0.5):
                    point = c + t * (side_t * width) + n * (side_n * depth) + z * (side_z * height)
                    self.vertices.append(tuple(point))
        self.faces.extend(
            (
                (start + 0, start + 1, start + 3, start + 2),
                (start + 4, start + 6, start + 7, start + 5),
                (start + 0, start + 4, start + 5, start + 1),
                (start + 2, start + 3, start + 7, start + 6),
                (start + 0, start + 2, start + 6, start + 4),
                (start + 1, start + 5, start + 7, start + 3),
            )
        )

    def create(self):
        mesh = bpy.data.meshes.new(self.name)
        mesh.from_pydata(self.vertices, [], self.faces)
        mesh.materials.append(self.mat)
        obj = bpy.data.objects.new(self.name, mesh)
        bpy.context.collection.objects.link(obj)
        return obj


def make_box(name, location, scale, mat, bevel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    obj.data.materials.append(mat)
    if bevel:
        modifier = obj.modifiers.new("Soft edges", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
        obj.modifiers.new("Weighted normals", "WEIGHTED_NORMAL")
    return obj


def add_plane(name, center, dimensions, mat):
    obj = make_box(name, center, (dimensions[0], dimensions[1], 0.12), mat, 0.04)
    return obj


def add_windows_and_joints(outline, z_levels):
    plaster = material("Aged window frames", (0.78, 0.74, 0.64), 0.65)
    frame_alt = material("Repaired window frames", (0.62, 0.68, 0.66), 0.56)
    glass = material("Smoky blue glazing", (0.12, 0.19, 0.22), 0.2, 0.22)
    warm_glass = material("Warm occupied glazing", (0.34, 0.29, 0.20), 0.3, 0.1)
    joint = material("Concrete panel joints", (0.51, 0.49, 0.43), 0.9)
    repair = material("Patch repairs", (0.74, 0.70, 0.60), 0.9)
    metal = material("Balcony railings", (0.12, 0.15, 0.15), 0.45, 0.55)
    ac_metal = material("Air conditioner housings", (0.73, 0.72, 0.66), 0.68, 0.12)
    sill = material("Window sills", (0.60, 0.58, 0.51), 0.82)

    glass_boxes = BoxMesh("Facade glazing", glass)
    warm_boxes = BoxMesh("Warm facade glazing", warm_glass)
    frame_boxes = BoxMesh("Facade window frames", plaster)
    alternate_frames = BoxMesh("Replaced frames", frame_alt)
    seam_boxes = BoxMesh("Facade panel seams", joint)
    repair_boxes = BoxMesh("Painted repair patches", repair)
    metal_boxes = BoxMesh("Balcony and AC metalwork", metal)
    ac_boxes = BoxMesh("Window AC units", ac_metal)
    sill_boxes = BoxMesh("Concrete window sills", sill)

    for edge_index, (start, end) in enumerate(zip(outline, outline[1:] + outline[:1])):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 0.5:
            continue
        tangent = (dx / length, dy / length)
        normal = (tangent[1], -tangent[0])
        midpoint = ((start[0] + end[0]) * 0.5, (start[1] + end[1]) * 0.5)
        front = normal[1] < -0.32
        side = abs(normal[1]) <= 0.32 and abs(normal[0]) > 0.5

        for floor in range(1, 13):
            seam_boxes.add(
                (midpoint[0], midpoint[1], floor * 3.0),
                tangent,
                normal,
                length - 0.08,
                0.035,
                0.05,
            )

        if not front and not side:
            continue

        count = max(1, int(length / (2.35 if front else 3.6)))
        window_width = min(1.25 if front else 1.05, (length - 0.5) / count * 0.56)
        for floor in range(13):
            floor_z = floor * 3.0
            row_width = count
            if side and floor % 2:
                row_width = max(1, count - 1)
            for index in range(row_width):
                fraction = (index + 0.5) / row_width
                along = length * fraction
                x = start[0] + tangent[0] * along
                y = start[1] + tangent[1] * along
                if front and x < -13.2 and x > -18.3:
                    continue
                width = window_width * random.uniform(0.88, 1.04)
                height = random.uniform(1.26, 1.56)
                window_z = floor_z + 1.55
                frame = alternate_frames if (floor + index + edge_index) % 5 == 0 else frame_boxes
                pane = warm_boxes if (floor * 11 + index * 7 + edge_index) % 13 == 0 else glass_boxes
                face_offset = 0.14
                pane.add(
                    (x + normal[0] * (face_offset + 0.055), y + normal[1] * (face_offset + 0.055), window_z),
                    tangent,
                    normal,
                    width - 0.16,
                    height - 0.17,
                    0.085,
                )
                bar = 0.075
                frame.add((x, y, window_z - height / 2 + bar / 2), tangent, normal, width, bar, 0.16)
                frame.add((x, y, window_z + height / 2 - bar / 2), tangent, normal, width, bar, 0.16)
                frame.add((x - tangent[0] * (width / 2 - bar / 2), y - tangent[1] * (width / 2 - bar / 2), window_z), tangent, normal, bar, height, 0.16)
                frame.add((x + tangent[0] * (width / 2 - bar / 2), y + tangent[1] * (width / 2 - bar / 2), window_z), tangent, normal, bar, height, 0.16)
                frame.add((x, y, window_z), tangent, normal, bar * 0.65, height - bar * 1.5, 0.17)
                sill_boxes.add((x, y, window_z - height / 2 - 0.07), tangent, normal, width + 0.15, 0.10, 0.22)

                if (floor * 3 + index * 5 + edge_index) % 6 == 0:
                    ac_x = x + tangent[0] * (width * 0.34)
                    ac_y = y + tangent[1] * (width * 0.34)
                    ac_z = floor_z + 0.58
                    ac_boxes.add((ac_x, ac_y, ac_z), tangent, normal, 0.64, 0.38, 0.43)
                    for fin in range(3):
                        metal_boxes.add(
                            (ac_x, ac_y, ac_z - 0.10 + fin * 0.09),
                            tangent,
                            normal,
                            0.50,
                            0.025,
                            0.46,
                        )

                if front and floor < 8 and (floor + index * 2 + edge_index) % 8 == 1:
                    patch_width = width * random.uniform(1.35, 1.75)
                    patch_height = height * random.uniform(1.15, 1.5)
                    patch_x = x + tangent[0] * width * 0.1
                    patch_y = y + tangent[1] * width * 0.1
                    repair_boxes.add(
                        (patch_x, patch_y, window_z),
                        tangent,
                        normal,
                        patch_width,
                        patch_height,
                        0.035,
                    )

    # The open communal balcony shaft is a defining feature in the reference photographs.
    shaft_x, shaft_y = -15.57, -11.96
    for floor in range(13):
        z = floor * 3.0
        make_box(
            "Communal balcony slab",
            (shaft_x, shaft_y - 0.55, z + 0.08),
            (3.16, 1.32, 0.20),
            sill,
            0.035,
        )
        rail_y = shaft_y - 1.18
        metal_boxes.add((shaft_x, rail_y, z + 1.08), (1.0, 0.0), (0.0, 1.0), 3.0, 0.075, 0.075)
        metal_boxes.add((shaft_x, rail_y, z + 0.58), (1.0, 0.0), (0.0, 1.0), 3.0, 0.045, 0.045)
        for baluster in range(13):
            bx = shaft_x - 1.45 + baluster * 0.242
            metal_boxes.add((bx, rail_y, z + 0.82), (1.0, 0.0), (0.0, 1.0), 0.035, 0.56, 0.035)
        if floor in (1, 4, 7, 10):
            # A few enclosed balconies reflect the mismatched glazing seen in the photos.
            for offset in (-0.9, 0.0, 0.9):
                pane_mat = warm_boxes if floor == 4 else glass_boxes
                pane_mat.add(
                    (shaft_x + offset, rail_y + 0.22, z + 1.48),
                    (1.0, 0.0),
                    (0.0, 1.0),
                    0.82,
                    1.16,
                    0.06,
                )

    glass_boxes.create()
    warm_boxes.create()
    frame_boxes.create()
    alternate_frames.create()
    seam_boxes.create()
    repair_boxes.create()
    metal_boxes.create()
    ac_boxes.create()
    sill_boxes.create()

    # Circular upper-floor windows on the left-hand wing.
    porthole_mat = material("Upper-floor porthole glazing", (0.10, 0.16, 0.19), 0.18, 0.22)
    trim_mat = material("Porthole trim", (0.78, 0.74, 0.64), 0.68)
    for edge_index, (start, end) in enumerate(zip(outline, outline[1:] + outline[:1])):
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length < 0.5:
            continue
        tangent = (dx / length, dy / length)
        normal = (tangent[1], -tangent[0])
        if normal[1] < -0.32 and start[0] < -10 and end[0] < -10:
            for fraction in (0.35, 0.65):
                x = start[0] + dx * fraction
                y = start[1] + dy * fraction
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=32,
                    radius=0.42,
                    depth=0.13,
                    location=(x + normal[0] * 0.13, y + normal[1] * 0.13, 37.62),
                )
                pane = bpy.context.object
                pane.name = "Thirteenth-floor circular window"
                pane.rotation_euler[0] = math.pi / 2
                pane.data.materials.append(porthole_mat)
                bpy.ops.mesh.primitive_torus_add(
                    major_radius=0.43,
                    minor_radius=0.055,
                    major_segments=32,
                    minor_segments=8,
                    location=(x + normal[0] * 0.22, y + normal[1] * 0.22, 37.62),
                )
                trim = bpy.context.object
                trim.name = "Circular window surround"
                trim.rotation_euler[0] = math.pi / 2
                trim.data.materials.append(trim_mat)


def setup_materials():
    make_weathered_concrete()
    colors = {
        "Asphalt": (0.12, 0.14, 0.14),
        "RoofBitumen": (0.085, 0.095, 0.09),
        "SlabBand": (0.57, 0.54, 0.47),
        "Partition": (0.57, 0.55, 0.49),
        "Metal": (0.13, 0.16, 0.16),
        "Leaf": (0.12, 0.24, 0.10),
        "Conifer": (0.08, 0.18, 0.10),
        "Car": (0.18, 0.22, 0.24),
    }
    for name, color in colors.items():
        mat = bpy.data.materials.get(name)
        if mat:
            shader = set_principled(mat, color, 0.76, 0.05 if name == "Metal" else 0.0)
            if name in ("Leaf", "Conifer"):
                shader.inputs["Roughness"].default_value = 0.92


def create_environment():
    grass = material("Soft green ground", (0.15, 0.22, 0.12), 0.96)
    paving = material("Warm gray paving", (0.31, 0.30, 0.27), 0.88)
    road = material("Street asphalt", (0.10, 0.115, 0.12), 0.91)
    white = material("Road markings", (0.76, 0.73, 0.65), 0.78)
    make_box("Landscape base", (0.0, 0.0, -0.30), (180.0, 180.0, 0.20), grass, 0.0)
    make_box("Building footpath", (0.0, -1.0, -0.13), (45.0, 43.0, 0.16), paving, 0.08)
    make_box("Parking and street apron", (1.0, -31.0, -0.13), (100.0, 28.0, 0.16), road, 0.03)

    # Subtle parking bay markings in front of the existing model cars.
    for x in range(-36, 39, 6):
        make_box("Parking bay line", (x, -25.5, -0.035), (0.055, 5.0, 0.018), white)

    curb = material("Curb stone", (0.50, 0.48, 0.42), 0.86)
    make_box("Front curb", (1.0, -16.7, -0.02), (100.0, 0.32, 0.20), curb, 0.04)

    # Keep the imported trees and street fixtures, while replacing the empty oversized ground.
    for obj in bpy.context.scene.objects:
        if obj.name == "Ground":
            obj.hide_render = True
            obj.hide_viewport = True


def setup_scene(outline):
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.preview_samples = 16
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.film_transparent = False
    scene.render.image_settings.compression = 18
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.render.filepath = IMAGE_PATH

    world = bpy.data.worlds.new("Clear pale blue sky") if not bpy.data.worlds else bpy.data.worlds[0]
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.48, 0.62, 0.76, 1.0)
    background.inputs["Strength"].default_value = 0.45

    bpy.ops.object.light_add(type="SUN", location=(-35.0, -45.0, 58.0))
    sun = bpy.context.object
    sun.name = "Late morning sun"
    sun.rotation_euler = (math.radians(27), math.radians(-22), math.radians(-28))
    sun.data.energy = 2.1
    sun.data.angle = math.radians(18)

    bpy.ops.object.light_add(type="AREA", location=(2.0, -42.0, 31.0))
    fill = bpy.context.object
    fill.name = "Soft facade fill"
    fill.data.energy = 2500
    fill.data.shape = "DISK"
    fill.data.size = 30
    fill.rotation_euler = (Vector((0.0, -1.0, 18.0)) - fill.location).to_track_quat("-Z", "Y").to_euler()

    camera_data = bpy.data.cameras.new("Hero camera")
    camera = bpy.data.objects.new("Hero camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = (-31.0, -79.0, 31.0)
    target = Vector((-1.0, -1.0, 18.3))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera_data.lens = 54
    camera_data.sensor_width = 36
    camera_data.dof.use_dof = False
    scene.camera = camera
    scene.render.resolution_percentage = 100
    scene.render.filepath = IMAGE_PATH

    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.render.use_file_extension = True
    scene.world.color = (0.4, 0.5, 0.6)

    # Add the aerial reference's broad framing without clipping the roof or street context.
    bpy.context.view_layer.objects.active = camera
    bpy.ops.wm.save_as_mainfile(filepath=BLEND_PATH)
    bpy.ops.render.render(write_still=True)


def main():
    if not os.path.isfile(MODEL_PATH):
        raise FileNotFoundError("Building GLB not found: " + MODEL_PATH)
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=MODEL_PATH)

    setup_materials()
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH" and any(mat.name == "Concrete" for mat in obj.data.materials if mat):
            obj.color = (0.68, 0.65, 0.56, 1.0)

    # Source GLB is Y-up; the importer converts it to Blender Z-up. Convert its footprint likewise.
    import json
    with open(os.path.join(ROOT, "output", "building_config.json"), "r") as f:
        footprint_source = json.load(f)["footprint"]
    footprint = [(x, -z) for x, z in footprint_source]
    create_environment()
    add_windows_and_joints(footprint, range(14))
    setup_scene(footprint)
    print("Saved Blender scene:", BLEND_PATH)
    print("Rendered image:", IMAGE_PATH)


if __name__ == "__main__":
    main()
