"""Headless Eevee scene: a stainless booster with no legs, a tower, and catch arms.

Run:
  blender -b -P video/blender/no_legs.py -- --beats beats.json --out clean.mp4
  blender -b -P video/blender/no_legs.py -- --beats beats.json --stills /tmp/stills

The camera yaw keeps increasing, so the shot never freezes.
Facts stay in the caption pass. This file only builds the picture.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def args_after_dd():
    argv = sys.argv
    if "--" not in argv:
        return {}
    tail = argv[argv.index("--") + 1:]
    out = {}
    i = 0
    while i < len(tail):
        if tail[i].startswith("--"):
            key = tail[i][2:]
            if i + 1 < len(tail) and not tail[i + 1].startswith("--"):
                out[key] = tail[i + 1]
                i += 2
            else:
                out[key] = "1"
                i += 1
        else:
            i += 1
    return out


def smooth(a, b, x):
    if b <= a:
        return 1.0
    u = max(0.0, min(1.0, (x - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


def lerp(a, b, u):
    return a + (b - a) * u


def material(name, color, metallic=0.92, rough=0.32, emit=0.0, emit_color=None):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (color[0], color[1], color[2], 1)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = rough
    if emit_color is None:
        emit_color = color
    bsdf.inputs["Emission Color"].default_value = (emit_color[0], emit_color[1], emit_color[2], 1)
    bsdf.inputs["Emission Strength"].default_value = emit
    return mat


def look_at(obj, target):
    direction = Vector(target) - Vector(obj.location)
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def span(name, a, b, radius, mat, verts=8):
    a, b = Vector(a), Vector(b)
    d = b - a
    dist = max(0.05, d.length)
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=dist, location=(a + b) / 2)
    obj = bpy.context.object
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = d.to_track_quat("Z", "Y")
    obj.data.materials.append(mat)
    obj.name = name
    return obj


# dist, yaw, eye z, focus x, focus y, focus z
# Wide enough that a 71 m booster fits in a vertical frame.
PRESET = {
    "base": (28.0, 0.55, 10.0, 0.0, 0.0, 16.0),
    "tower": (100.0, 0.9, 48.0, 8.0, 0.0, 42.0),
    "arms": (46.0, 1.25, 58.0, 8.0, 0.0, 62.0),
    "risk": (115.0, 0.6, 62.0, 8.0, 0.0, 46.0),
    "flight": (70.0, 0.35, 32.0, 0.0, -6.0, 36.0),
    "catch": (52.0, 1.05, 52.0, 7.0, 0.0, 55.0),
    "diagram": (24.0, 2.2, 14.0, -18.0, 8.0, 8.0),
    "next": (58.0, 0.2, 108.0, 0.0, -6.0, 100.0),
}


def blend_preset(a, b, u):
    return tuple(lerp(x, y, u) for x, y in zip(a, b))


def build(beats, fps, duration):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1080
    scene.render.resolution_y = 1920
    scene.render.resolution_percentage = 100
    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = max(2, int(round(duration * fps)))
    ee = scene.eevee
    ee.taa_render_samples = 2
    ee.use_bloom = True
    ee.bloom_threshold = 0.6
    ee.bloom_intensity = 0.18
    ee.bloom_radius = 6.0
    ee.use_gtao = True
    try:
        scene.view_settings.view_transform = "AgX"
        scene.view_settings.look = "AgX - Medium High Contrast"
    except TypeError:
        scene.view_settings.view_transform = "Filmic"
        scene.view_settings.look = "High Contrast"
    scene.view_settings.exposure = 0.15

    world = bpy.data.worlds.new("Dusk")
    scene.world = world
    world.use_nodes = True
    wnodes = world.node_tree.nodes
    wlinks = world.node_tree.links
    wnodes.clear()
    wout = wnodes.new("ShaderNodeOutputWorld")
    wbg = wnodes.new("ShaderNodeBackground")
    wcoord = wnodes.new("ShaderNodeTexCoord")
    wsep = wnodes.new("ShaderNodeSeparateXYZ")
    wramp = wnodes.new("ShaderNodeValToRGB")
    wramp.color_ramp.elements[0].position = 0.0
    wramp.color_ramp.elements[0].color = (0.95, 0.38, 0.08, 1)
    wramp.color_ramp.elements[1].position = 1.0
    wramp.color_ramp.elements[1].color = (0.02, 0.04, 0.12, 1)
    band = wramp.color_ramp.elements.new(0.42)
    band.color = (0.18, 0.10, 0.32, 1)
    wlinks.new(wcoord.outputs["Window"], wsep.inputs["Vector"])
    wlinks.new(wsep.outputs["Y"], wramp.inputs["Fac"])
    wlinks.new(wramp.outputs["Color"], wbg.inputs["Color"])
    wbg.inputs["Strength"].default_value = 1.15
    wlinks.new(wbg.outputs["Background"], wout.inputs["Surface"])

    steel = material("steel", (0.72, 0.66, 0.62), 0.95, 0.22)
    soot = material("soot", (0.18, 0.16, 0.15), 0.7, 0.55)
    dark = material("dark", (0.08, 0.08, 0.09), 0.8, 0.4)
    eng_mat = material("flame", (1.0, 0.35, 0.05), 0.0, 0.4, emit=4.0, emit_color=(1.0, 0.28, 0.02))
    red_mat = material("leg", (1.0, 0.12, 0.08), 0.2, 0.35, emit=2.2, emit_color=(1.0, 0.15, 0.05))
    cyan_mat = material("cargo", (0.05, 0.85, 0.95), 0.15, 0.25, emit=3.0, emit_color=(0.1, 0.9, 1.0))
    ground_mat = material("ground", (0.07, 0.045, 0.04), 0.15, 0.85)

    bpy.ops.mesh.primitive_plane_add(size=400, location=(0, 0, 0))
    ground = bpy.context.object
    ground.name = "Ground"
    ground.data.materials.append(ground_mat)

    root = bpy.data.objects.new("Booster", None)
    scene.collection.objects.link(root)

    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=4.5, depth=71, location=(0, 0, 35.5))
    body = bpy.context.object
    body.name = "Body"
    body.data.materials.append(steel)
    body.parent = root

    bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=4.52, depth=16, location=(0, 0, 8))
    skirt = bpy.context.object
    skirt.data.materials.append(soot)
    skirt.parent = root

    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=4.2, depth=1.2, location=(0, 0, 71.2))
    cap = bpy.context.object
    cap.data.materials.append(steel)
    cap.parent = root

    for i in range(4):
        ang = i * math.pi / 2 + 0.4
        x, y = math.cos(ang) * 5.3, math.sin(ang) * 5.3
        bpy.ops.mesh.primitive_cube_add(size=1, location=(x, y, 64))
        fin = bpy.context.object
        fin.name = f"Fin{i}"
        fin.scale = (3.2, 0.18, 2.4)
        fin.rotation_euler = (0, 0, ang)
        fin.data.materials.append(dark)
        fin.parent = root

    for i in range(12):
        ang = i * math.tau / 12
        ring = 2.6 if i < 8 else 0.0
        if i >= 8 and i != 8:
            continue
        x = math.cos(ang) * (2.6 if i < 8 else 0)
        y = math.sin(ang) * (2.6 if i < 8 else 0)
        bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.72, radius2=0.15, depth=1.5, location=(x, y, -0.2))
        bell = bpy.context.object
        bell.rotation_euler = (math.pi, 0, 0)
        bell.data.materials.append(eng_mat)
        bell.parent = root
    # a bright plume under the cluster
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=2.4, radius2=0.2, depth=6.0, location=(0, 0, -3.2))
    plume = bpy.context.object
    plume.name = "Plume"
    plume.rotation_euler = (math.pi, 0, 0)
    plume.data.materials.append(eng_mat)
    plume.parent = root

    light_data = bpy.data.lights.new("EngineLight", "POINT")
    light_data.color = (1.0, 0.32, 0.05)
    light_data.energy = 0
    light_data.shadow_soft_size = 3
    eng_light = bpy.data.objects.new("EngineLight", light_data)
    eng_light.location = (0, 0, -1)
    eng_light.parent = root
    scene.collection.objects.link(eng_light)

    # Tower
    posts = [(-2.2, -2.2), (2.2, -2.2), (2.2, 2.2), (-2.2, 2.2)]
    tower_x = 16.0
    for i, (dx, dy) in enumerate(posts):
        span(f"Post{i}", (tower_x + dx, dy, 0), (tower_x + dx, dy, 105), 0.45, dark, verts=6)
    for z in range(8, 100, 12):
        for i in range(4):
            a = posts[i]
            b = posts[(i + 1) % 4]
            span(f"Brace{z}_{i}", (tower_x + a[0], a[1], z), (tower_x + b[0], b[1], z), 0.22, dark, verts=6)

    arm_l = span("ArmL", (tower_x, 8, 62), (3.2, 8, 62), 0.55, steel, verts=10)
    arm_r = span("ArmR", (tower_x, -8, 66), (3.2, -8, 66), 0.55, steel, verts=10)

    # Mount ring
    bpy.ops.mesh.primitive_torus_add(major_radius=7, minor_radius=0.45, location=(0, 0, 0.4))
    ring = bpy.context.object
    ring.data.materials.append(dark)

    # Diagram: legs versus the cargo they replace. No numbers on the model.
    diagram = bpy.data.collections.new("Diagram")
    scene.collection.children.link(diagram)

    def into(obj, col):
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        col.objects.link(obj)

    bpy.ops.mesh.primitive_cube_add(size=1, location=(-18, 8, 5.2))
    beam = bpy.context.object
    beam.scale = (7.5, 0.35, 0.28)
    beam.data.materials.append(dark)
    into(beam, diagram)
    bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=0.7, depth=1.4, location=(-18, 8, 4.2))
    ful = bpy.context.object
    ful.data.materials.append(dark)
    into(ful, diagram)
    legs = []
    for i, dx in enumerate((-2.2, -1.1, 0.2, 1.3)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.28, depth=3.2, location=(-22 + dx, 8, 7.2))
        leg = bpy.context.object
        leg.rotation_euler = (0, 0.22 if i % 2 == 0 else -0.22, 0)
        leg.data.materials.append(red_mat)
        legs.append(leg)
        into(leg, diagram)
    bpy.ops.mesh.primitive_cube_add(size=1, location=(-13.2, 8, 7.4))
    cargo = bpy.context.object
    cargo.name = "Cargo"
    cargo.scale = (1.6, 1.6, 1.6)
    cargo.data.materials.append(cyan_mat)
    into(cargo, diagram)
    # Arrow from the legs toward the cargo.
    bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.12, depth=3.2, location=(-17.2, 8, 9.6))
    shaft = bpy.context.object
    shaft.rotation_euler = (0, math.pi / 2, 0)
    shaft.data.materials.append(cyan_mat)
    into(shaft, diagram)
    bpy.ops.mesh.primitive_cone_add(vertices=12, radius1=0.38, depth=0.9, location=(-15.2, 8, 9.6))
    head = bpy.context.object
    head.rotation_euler = (0, -math.pi / 2, 0)
    head.data.materials.append(cyan_mat)
    into(head, diagram)

    # Ship, shown only on the last beat group: pointed stage, no legs.
    ship_col = bpy.data.collections.new("Ship")
    scene.collection.children.link(ship_col)
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=4.5, depth=28, location=(0, -6, 96))
    ship_body = bpy.context.object
    ship_body.data.materials.append(steel)
    into(ship_body, ship_col)
    bpy.ops.mesh.primitive_cone_add(vertices=48, radius1=4.5, depth=12, location=(0, -6, 116))
    nose = bpy.context.object
    nose.data.materials.append(steel)
    into(nose, ship_col)
    for side in (-1, 1):
        bpy.ops.mesh.primitive_cube_add(size=1, location=(side * 5.2, -6, 108))
        flap = bpy.context.object
        flap.scale = (1.4, 0.12, 2.2)
        flap.rotation_euler = (0.4 * side, 0, 0.3 * side)
        flap.data.materials.append(dark)
        into(flap, ship_col)

    sun_data = bpy.data.lights.new("Sun", "SUN")
    sun_data.energy = 6.5
    sun_data.color = (1.0, 0.72, 0.45)
    sun_data.angle = 0.4
    sun = bpy.data.objects.new("Sun", sun_data)
    sun.rotation_euler = (math.radians(58), math.radians(-20), math.radians(25))
    scene.collection.objects.link(sun)

    rim_data = bpy.data.lights.new("Rim", "AREA")
    rim_data.energy = 2500
    rim_data.color = (0.15, 0.75, 1.0)
    rim_data.shape = "RECTANGLE"
    rim_data.size = 18
    rim_data.size_y = 40
    rim = bpy.data.objects.new("Rim", rim_data)
    rim.location = (-20, 30, 40)
    look_at(rim, (0, 0, 40))
    scene.collection.objects.link(rim)

    cam_data = bpy.data.cameras.new("Cam")
    fill_data = bpy.data.lights.new("Fill", "AREA")
    fill_data.energy = 6000
    fill_data.color = (1.0, 0.78, 0.55)
    fill_data.shape = "RECTANGLE"
    fill_data.size = 30
    fill_data.size_y = 50
    fill = bpy.data.objects.new("Fill", fill_data)
    fill.location = (40, -50, 35)
    scene.collection.objects.link(fill)
    look_at(fill, (4, 0, 36))

    cam_data.lens = 18
    cam_data.sensor_fit = "VERTICAL"
    cam_data.clip_end = 800
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam

    state = {
        "beats": beats,
        "fps": fps,
        "duration": duration,
        "root": root,
        "plume": plume,
        "eng": eng_mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"],
        "eng_light": light_data,
        "arm_l": arm_l,
        "arm_r": arm_r,
        "diagram": diagram,
        "ship": ship_col,
        "cargo": cargo,
        "legs": legs,
        "cam": cam,
    }
    flight_t0 = next(b["t0"] for b in beats if b["shot"] == "flight")
    catch_t0 = next(b["t0"] for b in beats if b["shot"] == "catch")
    state["flight_t0"] = flight_t0
    state["catch_t0"] = catch_t0

    def update(scene, _deps=None):
        t = (scene.frame_current - 1) / state["fps"]
        beats_ = state["beats"]
        idx = 0
        for k, b in enumerate(beats_):
            if t < b["t1"] or k == len(beats_) - 1:
                idx = k
                break
        cur = beats_[idx]
        prev_shot = beats_[idx - 1]["shot"] if idx else cur["shot"]
        u = smooth(cur["t0"], cur["t0"] + 0.5, t)
        # The closing second returns to the opening angle so the Short can loop.
        if t > state["duration"] - 1.7:
            u2 = smooth(state["duration"] - 1.7, state["duration"] - 0.15, t)
            preset = blend_preset(blend_preset(PRESET[prev_shot], PRESET[cur["shot"]], u), PRESET["base"], u2)
        else:
            preset = blend_preset(PRESET[prev_shot], PRESET[cur["shot"]], u)
        dist, yaw, ez, fx, fy, fz = preset
        yaw = yaw + t * 0.18
        focus = Vector((fx, fy, fz))
        pos = booster_location(t, state["flight_t0"], state["catch_t0"])
        state["root"].location = pos
        if cur["shot"] in ("flight", "catch") and t < state["duration"] - 1.7:
            focus = pos + Vector((0, 0, 40))
        eye = Vector((focus.x + dist * math.cos(yaw), focus.y + dist * math.sin(yaw), ez))
        # A little engine shake, never a full stop.
        if state["flight_t0"] <= t <= state["catch_t0"] + 1.6:
            eye.x += 0.15 * math.sin(t * 37)
            eye.z += 0.1 * math.sin(t * 29)
        state["cam"].location = eye
        look_at(state["cam"], focus)

        firing = state["flight_t0"] - 0.2 <= t <= state["catch_t0"] + 1.5
        flicker = 0.82 + 0.18 * math.sin(t * 45) if firing else 1.0
        state["eng"].default_value = (16.0 if firing else 0.35) * flicker
        state["eng_light"].energy = 12000 if firing else 80
        state["plume"].scale = (1, 1, 1.15 if firing else 0.15)

        gap = 13.5
        if t >= state["catch_t0"]:
            gap = lerp(13.5, 5.3, smooth(state["catch_t0"], state["catch_t0"] + 2.1, t))
        # The arm cylinders sit on the Y axis. Open is a wide gap; closed pinches the 9 m body.
        state["arm_l"].location.y = gap
        state["arm_r"].location.y = -gap

        show_d = cur["shot"] == "diagram" and t < state["duration"] - 1.7
        state["diagram"].hide_render = not show_d
        du = 0.0
        if show_d:
            d0 = next(b["t0"] for b in beats_ if b["shot"] == "diagram")
            d1 = max(b["t1"] for b in beats_ if b["shot"] == "diagram")
            du = smooth(d0, d1, t)
        for leg in state["legs"]:
            leg.scale = (1, 1, lerp(1.15, 0.35, du))
        state["cargo"].scale = (lerp(0.6, 1.8, du),) * 3
        state["ship"].hide_render = cur["shot"] != "next" or t > state["duration"] - 1.5

    bpy.app.handlers.frame_change_pre.clear()
    bpy.app.handlers.frame_change_pre.append(update)
    update(scene)
    return scene


def booster_location(t, flight_t0, catch_t0):
    if t < flight_t0:
        return Vector((0, 0, 0))
    if t < catch_t0:
        u = smooth(flight_t0, catch_t0, t)
        return Vector((0, lerp(-36, -3, u), lerp(48, 0, u)))
    u = smooth(catch_t0, catch_t0 + 2.0, t)
    return Vector((0, lerp(-3, 0, u), 0))


def main():
    opt = args_after_dd()
    spec = json.loads(Path(opt["beats"]).read_text())
    fps = int(spec.get("fps") or 24)
    beats = spec["beats"]
    duration = float(spec.get("duration") or beats[-1]["t1"])
    scene = build(beats, fps, duration)
    stills = opt.get("stills")
    if stills:
        folder = Path(stills)
        folder.mkdir(parents=True, exist_ok=True)
        scene.render.image_settings.file_format = "PNG"
        # A handful of times across the Short, for a look check.
        times = [0.4, 3.0, 8.0, 14.0, 21.0, 26.5, 31.0, max(0.2, duration - 0.4)]
        for t in times:
            scene.frame_set(max(1, int(t * fps)))
            scene.render.filepath = str(folder / f"t{t:.1f}.png")
            bpy.ops.render.render(write_still=True)
        print("STILLS", folder)
        return
    out = opt.get("out") or "/tmp/no-legs-clean.mp4"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.ffmpeg.ffmpeg_preset = "GOOD"
    scene.render.ffmpeg.audio_codec = "NONE"
    scene.render.filepath = out
    bpy.ops.render.render(animation=True)
    print("RENDERED", out, "frames", scene.frame_end)


if __name__ == "__main__":
    main()
