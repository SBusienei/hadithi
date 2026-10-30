import argparse
import sys
from pathlib import Path

import bpy
from mathutils import Quaternion, Vector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--preview", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def clear_scene() -> None:
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for data_collection in (bpy.data.meshes, bpy.data.curves, bpy.data.cameras, bpy.data.lights):
        for data_block in list(data_collection):
            if not data_block.users:
                data_collection.remove(data_block)


def set_principled_material(
    material: bpy.types.Material,
    color: tuple[float, float, float, float],
    roughness: float,
    metallic: float = 0.0,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
    replace_base_color_texture: bool = False,
) -> None:
    material.use_nodes = True
    principled = material.node_tree.nodes.get("Principled BSDF")
    if replace_base_color_texture:
        for input_name in ("Base Color", "Alpha"):
            for link in list(principled.inputs[input_name].links):
                material.node_tree.links.remove(link)
    principled.inputs["Base Color"].default_value = color
    principled.inputs["Roughness"].default_value = roughness
    principled.inputs["Metallic"].default_value = metallic
    principled.inputs["Alpha"].default_value = color[3]
    if emission:
        principled.inputs["Emission Color"].default_value = emission
        principled.inputs["Emission Strength"].default_value = emission_strength
    if color[3] < 1:
        if hasattr(material, "surface_render_method"):
            material.surface_render_method = "DITHERED"
        material.use_transparency_overlap = False


def create_material(
    name: str,
    color: tuple[float, float, float, float],
    roughness: float,
    emission: tuple[float, float, float, float] | None = None,
    emission_strength: float = 0.0,
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    set_principled_material(
        material,
        color,
        roughness,
        emission=emission,
        emission_strength=emission_strength,
    )
    return material


def reshape_source_dress() -> bpy.types.Object:
    dress_object = next(
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
        and any(slot.material and slot.material.name == "dress" for slot in obj.material_slots)
    )
    min_z = min(vertex.co.z for vertex in dress_object.data.vertices)
    skirt_start = 1.72
    for vertex in dress_object.data.vertices:
        z = vertex.co.z
        if z < skirt_start:
            progress = max(0.0, min(1.0, (skirt_start - z) / (skirt_start - min_z)))
            vertex.co.z = 0.04 + ((z - min_z) / (skirt_start - min_z)) * (skirt_start - 0.04)
            vertex.co.x *= 1.0 + progress * 0.42
            vertex.co.y *= 1.0 + progress * 0.28
        elif z < 2.52:
            torso_progress = (2.52 - z) / (2.52 - skirt_start)
            vertex.co.x *= 1.04 + torso_progress * 0.08
            vertex.co.y *= 1.03 + torso_progress * 0.06
    dress_object.data.update()
    dress_object.name = "LloronaModestGown"
    return dress_object


def find_bone(armature: bpy.types.Object, fragment: str) -> str:
    for bone in armature.data.bones:
        if fragment in bone.name:
            return bone.name
    raise RuntimeError(f"Required bone containing {fragment!r} was not found.")


def create_mournful_idle(armature: bpy.types.Object) -> None:
    scene = bpy.context.scene
    source_action = armature.animation_data.action
    scene.frame_set(0)
    bpy.context.view_layer.update()

    base_pose = {}
    for bone in armature.pose.bones:
        bone.rotation_mode = "QUATERNION"
        base_pose[bone.name] = {
            "location": bone.location.copy(),
            "rotation": bone.rotation_quaternion.copy(),
            "scale": bone.scale.copy(),
        }

    action = bpy.data.actions.new("Mournful_Idle")
    armature.animation_data.action = action
    scene.frame_start = 1
    scene.frame_end = 160

    animated_bones = {
        "mixamorig:Hips": find_bone(armature, "mixamorig:Hips"),
        "mixamorig:Spine": find_bone(armature, "mixamorig:Spine_"),
        "mixamorig:Spine1": find_bone(armature, "mixamorig:Spine1"),
        "mixamorig:Spine2": find_bone(armature, "mixamorig:Spine2"),
        "mixamorig:Neck": find_bone(armature, "mixamorig:Neck"),
        "mixamorig:Head": find_bone(armature, "mixamorig:Head_"),
        "mixamorig:LeftArm": find_bone(armature, "mixamorig:LeftArm"),
        "mixamorig:RightArm": find_bone(armature, "mixamorig:RightArm"),
        "mixamorig:LeftForeArm": find_bone(armature, "mixamorig:LeftForeArm"),
        "mixamorig:RightForeArm": find_bone(armature, "mixamorig:RightForeArm"),
    }

    poses = {
        1: {
            "hips_x": -0.008,
            "hips_z": 0.0,
            "spine_x": 0.018,
            "spine_z": -0.012,
            "head_x": 0.105,
            "head_z": 0.018,
            "arms": 0.025,
            "forearms": 0.018,
        },
        40: {
            "hips_x": 0.012,
            "hips_z": 0.014,
            "spine_x": 0.028,
            "spine_z": 0.018,
            "head_x": 0.13,
            "head_z": -0.025,
            "arms": 0.045,
            "forearms": 0.032,
        },
        80: {
            "hips_x": 0.02,
            "hips_z": 0.005,
            "spine_x": 0.036,
            "spine_z": 0.028,
            "head_x": 0.16,
            "head_z": -0.04,
            "arms": 0.058,
            "forearms": 0.04,
        },
        120: {
            "hips_x": 0.004,
            "hips_z": 0.012,
            "spine_x": 0.025,
            "spine_z": -0.01,
            "head_x": 0.125,
            "head_z": 0.012,
            "arms": 0.038,
            "forearms": 0.026,
        },
        160: {
            "hips_x": -0.008,
            "hips_z": 0.0,
            "spine_x": 0.018,
            "spine_z": -0.012,
            "head_x": 0.105,
            "head_z": 0.018,
            "arms": 0.025,
            "forearms": 0.018,
        },
    }

    for frame, pose in poses.items():
        scene.frame_set(frame)
        for bone in armature.pose.bones:
            base = base_pose[bone.name]
            bone.location = base["location"]
            bone.rotation_quaternion = base["rotation"]
            bone.scale = base["scale"]

        for fragment, scale_factor in (
            ("breast_l", 0.62),
            ("breast_r", 0.62),
            ("booty_l", 0.82),
            ("booty_r", 0.82),
            ("belly", 0.9),
        ):
            bone = armature.pose.bones[find_bone(armature, fragment)]
            bone.scale = base_pose[bone.name]["scale"] * scale_factor

        hips = armature.pose.bones[animated_bones["mixamorig:Hips"]]
        hips.location += Vector((pose["hips_x"], 0.0, pose["hips_z"]))

        for label, factor in (
            ("mixamorig:Spine", 0.35),
            ("mixamorig:Spine1", 0.65),
            ("mixamorig:Spine2", 1.0),
        ):
            bone = armature.pose.bones[animated_bones[label]]
            adjustment = Quaternion((1.0, 0.0, 0.0), pose["spine_x"] * factor)
            adjustment @= Quaternion((0.0, 0.0, 1.0), pose["spine_z"] * factor)
            bone.rotation_quaternion = base_pose[bone.name]["rotation"] @ adjustment

        neck = armature.pose.bones[animated_bones["mixamorig:Neck"]]
        neck_adjustment = Quaternion((1.0, 0.0, 0.0), pose["head_x"] * 0.42)
        neck_adjustment @= Quaternion((0.0, 0.0, 1.0), pose["head_z"] * 0.35)
        neck.rotation_quaternion = base_pose[neck.name]["rotation"] @ neck_adjustment

        head = armature.pose.bones[animated_bones["mixamorig:Head"]]
        head_adjustment = Quaternion((1.0, 0.0, 0.0), pose["head_x"])
        head_adjustment @= Quaternion((0.0, 0.0, 1.0), pose["head_z"])
        head.rotation_quaternion = base_pose[head.name]["rotation"] @ head_adjustment

        left_arm = armature.pose.bones[animated_bones["mixamorig:LeftArm"]]
        right_arm = armature.pose.bones[animated_bones["mixamorig:RightArm"]]
        left_arm.rotation_quaternion = (
            base_pose[left_arm.name]["rotation"]
            @ Quaternion((0.0, 0.0, 1.0), pose["arms"])
        )
        right_arm.rotation_quaternion = (
            base_pose[right_arm.name]["rotation"]
            @ Quaternion((0.0, 0.0, 1.0), -pose["arms"])
        )

        left_forearm = armature.pose.bones[animated_bones["mixamorig:LeftForeArm"]]
        right_forearm = armature.pose.bones[animated_bones["mixamorig:RightForeArm"]]
        left_forearm.rotation_quaternion = (
            base_pose[left_forearm.name]["rotation"]
            @ Quaternion((0.0, 1.0, 0.0), pose["forearms"])
        )
        right_forearm.rotation_quaternion = (
            base_pose[right_forearm.name]["rotation"]
            @ Quaternion((0.0, 1.0, 0.0), -pose["forearms"])
        )

        for bone in armature.pose.bones:
            bone.keyframe_insert("location", frame=frame)
            bone.keyframe_insert("rotation_quaternion", frame=frame)
            bone.keyframe_insert("scale", frame=frame)

    for curve in action.fcurves:
        for keyframe in curve.keyframe_points:
            keyframe.interpolation = "BEZIER"
        curve.modifiers.new("CYCLES")

    if source_action and source_action != action:
        bpy.data.actions.remove(source_action)


def point_camera(camera: bpy.types.Object, target: Vector) -> None:
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()


def set_up_preview(preview_path: Path) -> None:
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(preview_path)
    scene.render.film_transparent = False
    scene.world.color = (0.006, 0.014, 0.025)

    camera_data = bpy.data.cameras.new("CharacterStudyCamera")
    camera = bpy.data.objects.new("CharacterStudyCamera", camera_data)
    bpy.context.collection.objects.link(camera)
    camera.location = (0.08, -6.8, 1.65)
    camera_data.lens = 58
    point_camera(camera, Vector((0.05, 0.0, 1.62)))
    scene.camera = camera

    key_data = bpy.data.lights.new("MoonKey", "AREA")
    key_data.energy = 720
    key_data.color = (0.5, 0.66, 1.0)
    key_data.shape = "DISK"
    key_data.size = 4.5
    key = bpy.data.objects.new("MoonKey", key_data)
    bpy.context.collection.objects.link(key)
    key.location = (-3.2, -4.0, 6.0)
    point_camera(key, Vector((0.0, 0.0, 1.7)))

    fill_data = bpy.data.lights.new("WaterFill", "AREA")
    fill_data.energy = 360
    fill_data.color = (0.22, 0.62, 0.7)
    fill_data.size = 5.0
    fill = bpy.data.objects.new("WaterFill", fill_data)
    bpy.context.collection.objects.link(fill)
    fill.location = (3.0, -1.5, 1.2)
    point_camera(fill, Vector((0.0, 0.0, 1.4)))

    rim_data = bpy.data.lights.new("MoonRim", "AREA")
    rim_data.energy = 900
    rim_data.color = (0.7, 0.8, 1.0)
    rim_data.size = 3.0
    rim = bpy.data.objects.new("MoonRim", rim_data)
    bpy.context.collection.objects.link(rim)
    rim.location = (-1.8, 2.8, 3.8)
    point_camera(rim, Vector((0.0, 0.0, 2.0)))

    ground_material = create_material(
        "RiverMistGround",
        (0.012, 0.035, 0.045, 1.0),
        0.72,
    )
    bpy.ops.mesh.primitive_plane_add(size=18, location=(0.0, 0.0, -0.025))
    ground = bpy.context.object
    ground.name = "CharacterStudyGround"
    ground.data.materials.append(ground_material)


def main() -> None:
    args = parse_args()
    source_path = Path(args.source).resolve()
    output_path = Path(args.output).resolve()
    preview_path = Path(args.preview).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)

    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(source_path))

    armature = next(obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE")
    armature.name = "LaLloronaRig"

    material_updates = {
        "dress": ((0.7, 0.79, 0.9, 0.82), 0.9, (0.08, 0.15, 0.24, 1.0), 0.14, True),
        "skin": ((0.35, 0.43, 0.5, 0.84), 0.82, (0.035, 0.07, 0.11, 1.0), 0.08, True),
        "hair": ((0.012, 0.018, 0.028, 1.0), 0.96, None, 0.0, False),
        "eyes": ((0.25, 0.34, 0.42, 0.42), 0.55, (0.06, 0.12, 0.2, 1.0), 0.2, True),
        "nails": ((0.3, 0.37, 0.43, 0.72), 0.86, None, 0.0, True),
    }
    for (
        name,
        (color, roughness, emission, emission_strength, replace_base_color_texture),
    ) in material_updates.items():
        material = bpy.data.materials.get(name)
        if material:
            set_principled_material(
                material,
                color,
                roughness,
                emission=emission,
                emission_strength=emission_strength,
                replace_base_color_texture=replace_base_color_texture,
            )

    reshape_source_dress()

    create_mournful_idle(armature)
    bpy.context.scene.frame_set(80)
    bpy.ops.export_scene.gltf(
        filepath=str(output_path),
        export_format="GLB",
        export_animations=True,
        export_skins=True,
        export_morph=True,
        export_yup=True,
    )
    set_up_preview(preview_path)
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path.with_suffix(".blend")))
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    main()
