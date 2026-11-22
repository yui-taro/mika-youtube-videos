# 夜桜シアター: 夜桜の下の野外スクリーンで既存動画(dancing-cat.mov)を上映する縦型ショート
# 使い方: xvfb-run -a blender -b -P blender/yozakura_theater.py -- <out_dir>
#   FRAMES=1,150,300 を付けるとテスト用に指定フレームだけ静止画レンダリング
import bpy, sys, os, math, random
from mathutils import Vector, noise

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "render")
os.makedirs(OUT, exist_ok=True)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIDEO = os.path.join(ROOT, "dancing-cat.mov")
FPS, SECS, PREROLL = 30, 10, 90          # 花びら・蛍を事前に舞わせておくためのプリロール
F0, F1 = PREROLL + 1, PREROLL + FPS * SECS
random.seed(3)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = "BLENDER_EEVEE"
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, F1
sc.render.image_settings.file_format = "PNG"
sc.render.resolution_percentage = int(os.environ.get("PCT", 100))
e = sc.eevee
e.taa_render_samples = int(os.environ.get("SAMPLES", 24))
e.use_bloom = True; e.bloom_threshold = 0.9; e.bloom_intensity = 0.05; e.bloom_radius = 5
e.use_ssr = True; e.use_ssr_refraction = False; e.use_gtao = True
e.use_volumetric_lights = True; e.use_volumetric_shadows = True
e.volumetric_tile_size = "8"; e.volumetric_samples = 32; e.volumetric_end = 40
e.use_motion_blur = True; e.motion_blur_shutter = 0.5
e.use_soft_shadows = True; e.shadow_cube_size = "512"
sc.view_settings.view_transform = "Filmic"; sc.view_settings.look = "High Contrast"
sc.view_settings.exposure = 0.3


def nodes_mat(name):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    return m, nt, nt.nodes.new("ShaderNodeOutputMaterial")


def principled(name, col, rough=0.5, emit=None, strength=0.0, sss=0.0, trans=0.0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*col, 1)
    p.inputs["Roughness"].default_value = rough
    p.inputs["Subsurface Weight"].default_value = sss
    p.inputs["Transmission Weight"].default_value = trans
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1)
        p.inputs["Emission Strength"].default_value = strength
    return m


def emission(name, col, strength):
    m, nt, out = nodes_mat(name)
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs[0].default_value = (*col, 1); em.inputs[1].default_value = strength
    nt.links.new(em.outputs[0], out.inputs[0])
    return m


def link(obj, mat):
    obj.data.materials.append(mat); return obj


# ---------------------------------------------------------------- 夜空（グラデーション＋星）と霧
w = bpy.data.worlds.new("Night"); sc.world = w; w.use_nodes = True
nt = w.node_tree; nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputWorld")
tc = nt.nodes.new("ShaderNodeTexCoord")
sep = nt.nodes.new("ShaderNodeSeparateXYZ"); nt.links.new(tc.outputs["Generated"], sep.inputs[0])
ramp = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(sep.outputs["Z"], ramp.inputs[0])
ramp.color_ramp.elements[0].position = 0.0; ramp.color_ramp.elements[0].color = (0.10, 0.05, 0.16, 1)
ramp.color_ramp.elements[1].position = 0.45; ramp.color_ramp.elements[1].color = (0.006, 0.010, 0.035, 1)
mid = ramp.color_ramp.elements.new(0.02); mid.color = (0.20, 0.08, 0.20, 1)
vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.inputs["Scale"].default_value = 260
nt.links.new(tc.outputs["Generated"], vor.inputs["Vector"])
sr = nt.nodes.new("ShaderNodeMapRange")
sr.inputs["From Min"].default_value = 0.035; sr.inputs["From Max"].default_value = 0.0
sr.inputs["To Min"].default_value = 0.0; sr.inputs["To Max"].default_value = 3.0
sr.clamp = True; nt.links.new(vor.outputs["Distance"], sr.inputs[0])
up = nt.nodes.new("ShaderNodeMath"); up.operation = "MULTIPLY"
nt.links.new(sr.outputs[0], up.inputs[0])
hz = nt.nodes.new("ShaderNodeMapRange"); hz.inputs["From Min"].default_value = 0.0
hz.inputs["From Max"].default_value = 0.25; nt.links.new(sep.outputs["Z"], hz.inputs[0])
nt.links.new(hz.outputs[0], up.inputs[1])
add = nt.nodes.new("ShaderNodeMixRGB"); add.blend_type = "ADD"; add.inputs[0].default_value = 1
nt.links.new(ramp.outputs[0], add.inputs[1]); nt.links.new(up.outputs[0], add.inputs[2])
bg = nt.nodes.new("ShaderNodeBackground"); bg.inputs[1].default_value = 1.0
nt.links.new(add.outputs[0], bg.inputs[0]); nt.links.new(bg.outputs[0], out.inputs["Surface"])
vol = nt.nodes.new("ShaderNodeVolumePrincipled")
vol.inputs["Color"].default_value = (0.55, 0.6, 0.9, 1); vol.inputs["Density"].default_value = 0.006
vol.inputs["Anisotropy"].default_value = 0.45
nt.links.new(vol.outputs[0], out.inputs["Volume"])

# ---------------------------------------------------------------- 地形: 小高い丘の島 + 水面 + 遠景の山
def ground_z(x, y):
    r = math.hypot(x + 0.5, (y - 2.0) * 0.8)
    return 0.75 * math.exp(-(r / 6.0) ** 2) - 0.22


bpy.ops.mesh.primitive_grid_add(x_subdivisions=160, y_subdivisions=160, size=24, location=(0, 2, 0))
land = bpy.context.object; land.name = "Land"
vg = land.vertex_groups.new(name="grass")
for v in land.data.vertices:
    co = land.matrix_world @ v.co
    z = ground_z(co.x, co.y) + 0.06 * noise.noise(Vector((co.x * 0.6, co.y * 0.6, 0)))
    v.co.z = z
    vg.add([v.index], max(0.0, min(1.0, (z - 0.02) * 6)), "REPLACE")
bpy.ops.object.shade_smooth()
link(land, principled("Soil", (0.05, 0.06, 0.035), rough=0.9))

bpy.ops.mesh.primitive_plane_add(size=300, location=(0, 0, 0))
water = bpy.context.object; water.name = "Water"
m, nt, out = nodes_mat("Water")
gl = nt.nodes.new("ShaderNodeBsdfPrincipled")
gl.inputs["Base Color"].default_value = (0.004, 0.006, 0.014, 1)
gl.inputs["Roughness"].default_value = 0.04; gl.inputs["Specular IOR Level"].default_value = 0.8
wn = nt.nodes.new("ShaderNodeTexNoise"); wn.inputs["Scale"].default_value = 3.0; wn.inputs["Detail"].default_value = 4
mp = nt.nodes.new("ShaderNodeMapping"); tcw = nt.nodes.new("ShaderNodeTexCoord")
nt.links.new(tcw.outputs["Object"], mp.inputs[0]); nt.links.new(mp.outputs[0], wn.inputs["Vector"])
mp.inputs["Scale"].default_value = (1, 3.5, 1)
bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.12
nt.links.new(wn.outputs["Fac"], bump.inputs["Height"]); nt.links.new(bump.outputs[0], gl.inputs["Normal"])
nt.links.new(gl.outputs[0], out.inputs[0])
link(water, m)
# さざ波を流す
mp.inputs["Location"].default_value = (0, 0, 0); mp.inputs["Location"].keyframe_insert("default_value", frame=1)
mp.inputs["Location"].default_value = (0.6, 1.2, 0.8); mp.inputs["Location"].keyframe_insert("default_value", frame=F1)
bpy.ops.object.lightprobe_add(type="PLANAR", location=(0, 0, 0.001))
probe = bpy.context.object; probe.scale = (60, 60, 1); probe.data.falloff = 0.2

mount_mat = principled("Mountain", (0.012, 0.014, 0.03), rough=1)
for (cx, cy, h, s) in ((-30, 85, 22, 70), (25, 95, 30, 80), (60, 70, 16, 50), (-70, 70, 14, 50)):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=40, size=s, location=(cx, cy, 0))
    mo = bpy.context.object
    for v in mo.data.vertices:
        d = math.hypot(v.co.x / (s * 0.5), v.co.y / (s * 0.5))
        v.co.z = max(0.0, h * max(0.0, 1 - d) ** 1.6 * (0.75 + 0.35 * noise.fractal(Vector((v.co.x * 0.08 + cx, v.co.y * 0.08, 0)), 0.6, 2.0, 5)))
    bpy.ops.object.shade_smooth(); link(mo, mount_mat)

# 月と月光
bpy.ops.mesh.primitive_uv_sphere_add(radius=5, segments=64, ring_count=32, location=(-22, 120, 38))
moon = bpy.context.object
m, nt, out = nodes_mat("Moon")
mn = nt.nodes.new("ShaderNodeTexNoise"); mn.inputs["Scale"].default_value = 3; mn.inputs["Detail"].default_value = 6
mr = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(mn.outputs["Fac"], mr.inputs[0])
mr.color_ramp.elements[0].color = (1.0, 0.93, 0.78, 1); mr.color_ramp.elements[1].color = (0.82, 0.78, 0.7, 1)
me = nt.nodes.new("ShaderNodeEmission"); me.inputs[1].default_value = 14
nt.links.new(mr.outputs[0], me.inputs[0]); nt.links.new(me.outputs[0], out.inputs[0])
link(moon, m)
bpy.ops.object.light_add(type="SUN", rotation=(math.radians(-62), 0, math.radians(190)))
sun = bpy.context.object; sun.data.energy = 0.35; sun.data.color = (0.6, 0.7, 1.0); sun.data.angle = math.radians(2)

# ---------------------------------------------------------------- 桜の木（Sapling）
bpy.ops.preferences.addon_enable(module="add_curve_sapling")
import addon_utils
_sap = [m for m in addon_utils.modules() if m.__name__ == "add_curve_sapling"][0]
preset = eval(open(os.path.join(os.path.dirname(_sap.__file__), "presets", "japanese_maple.py")).read())
preset.update(dict(showLeaves=True, leaves=28, leafScale=0.2, leafScaleX=1.0, leafShape="hex",
                   leafDist="6", seed=11, bevel=True, handleType="1", makeMesh=False,
                   leafScaleV=0.3, leafDownAngle=60, armAnim=False, leafAnim=False, useArm=False))
for k in ("presetName", "limitImport", "do_update", "chooseSet", "frameRate", "loopFrames", "previewArm"):
    preset.pop(k, None)
tree_props = {p.identifier for p in bpy.ops.curve.tree_add.get_rna_type().properties}
bpy.ops.curve.tree_add(**{k: v for k, v in preset.items() if k in tree_props})
tree = [o for o in sc.objects if o.type == "CURVE"][0]
leaves = [o for o in sc.objects if o.parent == tree and o.type == "MESH"]
TREE_POS = Vector((-2.9, 2.6, ground_z(-2.9, 2.6) - 0.05))
tree.location = TREE_POS; tree.scale = (0.78, 0.78, 0.78); tree.rotation_euler.z = math.radians(200)
tree.data.materials.append(principled("Bark", (0.035, 0.022, 0.018), rough=0.85))
m, nt, out = nodes_mat("Blossom")
p = nt.nodes.new("ShaderNodeBsdfPrincipled")
p.inputs["Base Color"].default_value = (1.0, 0.52, 0.68, 1); p.inputs["Roughness"].default_value = 0.6
p.inputs["Subsurface Weight"].default_value = 0.3; p.inputs["Subsurface Radius"].default_value = (1, 0.4, 0.5)
p.inputs["Emission Color"].default_value = (1.0, 0.55, 0.72, 1)
rnd = nt.nodes.new("ShaderNodeObjectInfo")
oi = nt.nodes.new("ShaderNodeTexNoise"); oi.inputs["Scale"].default_value = 1.2
gm = nt.nodes.new("ShaderNodeMapRange"); gm.inputs["To Min"].default_value = 0.0; gm.inputs["To Max"].default_value = 0.4
nt.links.new(oi.outputs["Fac"], gm.inputs[0]); nt.links.new(gm.outputs[0], p.inputs["Emission Strength"])
tr = nt.nodes.new("ShaderNodeBsdfTranslucent"); tr.inputs[0].default_value = (1.0, 0.6, 0.75, 1)
mx = nt.nodes.new("ShaderNodeMixShader"); mx.inputs[0].default_value = 0.35
nt.links.new(p.outputs[0], mx.inputs[1]); nt.links.new(tr.outputs[0], mx.inputs[2])
nt.links.new(mx.outputs[0], out.inputs[0])
blossom = m
for lv in leaves:
    lv.data.materials.clear(); lv.data.materials.append(blossom)

# 2本目の小さな桜（奥・右）
tree2 = tree.copy(); tree2.data = tree.data.copy(); sc.collection.objects.link(tree2)
tree2.location = Vector((4.2, 6.5, ground_z(4.2, 6.5) - 0.05)); tree2.scale = (0.6, 0.6, 0.6)
tree2.rotation_euler.z = math.radians(40)
for lv in leaves:
    l2 = lv.copy(); sc.collection.objects.link(l2); l2.parent = tree2

# ライトアップ（下から桜を照らす）
for pos, tgt, col, en in (((-1.8, 0.6), (-2.9, 2.6, 4.5), (1.0, 0.55, 0.7), 900),
                          ((-4.5, 1.0), (-2.9, 2.6, 4.0), (1.0, 0.75, 0.6), 700),
                          ((3.0, 4.6), (4.2, 6.5, 3.5), (1.0, 0.55, 0.75), 600)):
    bpy.ops.object.light_add(type="SPOT", location=(pos[0], pos[1], ground_z(*pos) + 0.1))
    L = bpy.context.object; L.data.energy = en; L.data.color = col
    L.data.spot_size = math.radians(70); L.data.spot_blend = 0.8; L.data.shadow_soft_size = 0.3
    L.rotation_euler = (Vector(tgt) - L.location).to_track_quat("-Z", "Y").to_euler()

# ---------------------------------------------------------------- 野外スクリーン（布＋木の柱＋ロープ）
SX, SY = 0.35, 0.9
GZ = ground_z(SX, SY)
W_, H_ = 1.6, 1.6 * 16 / 9
TOP = GZ + 0.7 + H_
wood = principled("Wood", (0.09, 0.05, 0.03), rough=0.7)
for dx in (-W_ / 2 - 0.12, W_ / 2 + 0.12):
    bpy.ops.mesh.primitive_cylinder_add(radius=0.055, depth=TOP - GZ + 0.35, vertices=16,
                                        location=(SX + dx, SY, (TOP + GZ + 0.35) / 2 - 0.05))
    po = bpy.context.object; po.rotation_euler = (random.uniform(-.03, .03), random.uniform(-.03, .03), 0)
    link(po, wood)
bpy.ops.mesh.primitive_cylinder_add(radius=0.012, depth=W_ + 0.3, vertices=8, location=(SX, SY, TOP + 0.04),
                                    rotation=(0, math.radians(90), 0))
link(bpy.context.object, principled("Rope", (0.5, 0.42, 0.3), rough=0.9))

bpy.ops.mesh.primitive_grid_add(x_subdivisions=40, y_subdivisions=70, size=1, location=(SX, SY, TOP - H_ / 2),
                                rotation=(math.radians(90), 0, 0))
sheet = bpy.context.object; sheet.name = "Screen"; sheet.scale = (W_, H_, 1)
bpy.ops.object.transform_apply(scale=True)
for v in sheet.data.vertices:          # 上端を支点に、下に行くほどふくらむ
    t = (TOP - (sheet.matrix_world @ v.co).z) / H_
    v.co.z += 0.06 * t * math.sin(math.pi * (v.co.x / W_ + 0.5))
wav = sheet.modifiers.new("Breeze", "WAVE")
wav.use_normal = False; wav.use_x = True; wav.use_y = False
wav.height = 0.018; wav.width = 1.1; wav.speed = 0.05; wav.narrowness = 1.2
bpy.ops.object.shade_smooth()
m, nt, out = nodes_mat("ScreenVideo")
img = bpy.data.images.load(VIDEO); img.source = "MOVIE"
tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
iu = tex.image_user; iu.frame_duration = img.frame_duration; iu.frame_start = F0; iu.use_auto_refresh = True
em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.1
# 映写開始のフェードイン（最初の0.7秒で光る）
mul = nt.nodes.new("ShaderNodeMixRGB"); mul.blend_type = "MULTIPLY"; mul.inputs[0].default_value = 1
mul.inputs[2].default_value = (0, 0, 0, 1)
mul.inputs[2].keyframe_insert("default_value", frame=F0)
mul.inputs[2].default_value = (1, 1, 1, 1); mul.inputs[2].keyframe_insert("default_value", frame=F0 + 21)
cloth = nt.nodes.new("ShaderNodeBsdfDiffuse"); cloth.inputs[0].default_value = (0.08, 0.08, 0.08, 1)
addsh = nt.nodes.new("ShaderNodeAddShader")
nt.links.new(tex.outputs[0], mul.inputs[1]); nt.links.new(mul.outputs[0], em.inputs[0])
nt.links.new(em.outputs[0], addsh.inputs[0]); nt.links.new(cloth.outputs[0], addsh.inputs[1])
nt.links.new(addsh.outputs[0], out.inputs[0])
link(sheet, m)
# 画面からこぼれる光
bpy.ops.object.light_add(type="AREA", location=(SX, SY - 0.25, TOP - H_ / 2), rotation=(math.radians(-90), 0, 0))
scr_light = bpy.context.object; scr_light.data.size = W_; scr_light.data.size_y = H_
scr_light.data.shape = "RECTANGLE"; scr_light.data.color = (0.85, 0.75, 1.0)
scr_light.data.energy = 0; scr_light.data.keyframe_insert("energy", frame=F0)
scr_light.data.energy = 60; scr_light.data.keyframe_insert("energy", frame=F0 + 21)
for fc in scr_light.data.animation_data.action.fcurves:  # 映像のちらつき
    nm = fc.modifiers.new("NOISE"); nm.scale = 3; nm.strength = 25; nm.phase = 7

# ---------------------------------------------------------------- 提灯の列（カテナリー）
paper, nt, out = nodes_mat("LanternPaper")
ln = nt.nodes.new("ShaderNodeTexWave"); ln.wave_type = "BANDS"
ln.bands_direction = "Z"; ln.inputs["Scale"].default_value = 9; ln.inputs["Distortion"].default_value = 0.5
lr = nt.nodes.new("ShaderNodeValToRGB"); nt.links.new(ln.outputs["Fac"], lr.inputs[0])
lr.color_ramp.elements[0].color = (0.45, 0.05, 0.02, 1); lr.color_ramp.elements[1].color = (1.0, 0.35, 0.08, 1)
lr.color_ramp.elements[0].position = 0.1
le = nt.nodes.new("ShaderNodeEmission"); le.inputs[1].default_value = 7
nt.links.new(lr.outputs[0], le.inputs[0]); nt.links.new(le.outputs[0], out.inputs[0])
cap = principled("LanternCap", (0.02, 0.02, 0.02), rough=0.4)
string = principled("String", (0.1, 0.08, 0.06), rough=0.9)


def lantern_row(a, b, n, sag):
    pts = []
    for i in range(n + 1):
        t = i / n
        p = a.lerp(b, t); p.z -= sag * 4 * t * (1 - t); pts.append(p)
    cd = bpy.data.curves.new("wire", "CURVE"); cd.dimensions = "3D"; cd.bevel_depth = 0.006
    sp = cd.splines.new("POLY"); sp.points.add(len(pts) - 1)
    for i, p in enumerate(pts): sp.points[i].co = (*p, 1)
    wo = bpy.data.objects.new("Wire", cd); sc.collection.objects.link(wo); wo.data.materials.append(string)
    for i in range(1, n, 2):
        p = pts[i] - Vector((0, 0, 0.32))
        bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=24, ring_count=16, location=p)
        lo = bpy.context.object; lo.scale = (0.16, 0.16, 0.22); bpy.ops.object.shade_smooth(); link(lo, paper)
        for dz in (0.2, -0.2):
            bpy.ops.mesh.primitive_cylinder_add(radius=0.09, depth=0.05, location=p + Vector((0, 0, dz)))
            link(bpy.context.object, cap)
        bpy.ops.object.light_add(type="POINT", location=p)
        L = bpy.context.object; L.data.energy = 18; L.data.color = (1.0, 0.45, 0.15); L.data.shadow_soft_size = 0.15; L.data.use_shadow = False
        # 風でゆらゆら
        for o in (lo,):
            o.rotation_euler = (0, 0, 0); ph = random.random() * 6
            for f in range(1, F1 + 1, 12):
                o.rotation_euler.x = 0.06 * math.sin(f / 18 + ph); o.keyframe_insert("rotation_euler", index=0, frame=f)


lantern_row(Vector((-2.4, 2.2, 3.3)), Vector((SX - W_ / 2 - 0.12, SY, TOP + 0.2)), 8, 0.35)
lantern_row(Vector((SX + W_ / 2 + 0.12, SY, TOP + 0.2)), Vector((3.6, 5.6, 3.4)), 10, 0.45)

# ---------------------------------------------------------------- 舞い散る花びら
bpy.ops.mesh.primitive_circle_add(vertices=12, radius=1, fill_type="NGON", location=(0, -50, -50))
petal = bpy.context.object; petal.name = "Petal"
for v in petal.data.vertices:
    v.co.x *= 0.6
    if v.co.y > 0.85: v.co.y = 0.75                     # 先端に切れ込み
    v.co.z = 0.25 * v.co.x ** 2                         # 少し反る
pmat = principled("PetalMat", (1.0, 0.78, 0.86), rough=0.5, emit=(1.0, 0.6, 0.75), strength=0.9, sss=0.2)
pmat.use_backface_culling = False; link(petal, pmat)

bpy.ops.mesh.primitive_plane_add(size=1, location=(-1.6, 2.2, 6.2))
pe = bpy.context.object; pe.name = "PetalEmitter"; pe.scale = (7, 5, 1); pe.show_instancer_for_render = False
pps = pe.modifiers.new("Petals", "PARTICLE_SYSTEM").particle_system.settings
pps.count = 1100; pps.frame_start = 1; pps.frame_end = F1; pps.lifetime = 320
pps.normal_factor = 0; pps.factor_random = 0.3; pps.brownian_factor = 0.9
pps.effector_weights.gravity = 0.14; pps.drag_factor = 0.4; pps.damping = 0.0
pps.render_type = "OBJECT"; pps.instance_object = petal; pps.particle_size = 0.045; pps.size_random = 0.5
pps.use_rotations = True; pps.rotation_mode = "NONE"; pps.rotation_factor_random = 1.0
pps.angular_velocity_mode = "RAND"; pps.angular_velocity_factor = 6
pps.use_dynamic_rotation = True; pps.timestep = 0.04
pe2 = pe.copy(); pe2.show_instancer_for_render = False; sc.collection.objects.link(pe2); pe2.location = (1.0, -5.5, 4.5); pe2.scale = (5, 6, 1)
pe2.modifiers["Petals"].particle_system.seed = 5
# 地面に散った花びら
carpet = land.modifiers.new("Fallen", "PARTICLE_SYSTEM").particle_system
cs = bpy.data.particles.new("FallenSet"); carpet.settings = cs; carpet.vertex_group_density = "grass"
cs.type = "HAIR"; cs.count = 22000; cs.hair_length = 0.05; cs.render_type = "OBJECT"; cs.instance_object = petal
cs.use_rotations = True; cs.rotation_mode = "NOR"; cs.phase_factor_random = 2.0; cs.size_random = 0.5
cs.particle_size = 0.06; cs.use_advanced_hair = True
bpy.ops.object.effector_add(type="WIND", location=(-9, 1, 3), rotation=(0, math.radians(80), math.radians(-15)))
wind = bpy.context.object; wind.field.strength = 0.7; wind.field.noise = 1.5
bpy.ops.object.effector_add(type="TURBULENCE", location=(0, 1, 3))
tb = bpy.context.object; tb.field.strength = 0.6; tb.field.size = 1.6

# ---------------------------------------------------------------- 蛍
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=(0, -50, -40))
fly = bpy.context.object; link(fly, emission("Firefly", (0.75, 1.0, 0.35), 60))
fe = land.modifiers.new("Fireflies", "PARTICLE_SYSTEM").particle_system
fs = bpy.data.particles.new("FireflySet"); fe.settings = fs
fs.type = "EMITTER"; fs.count = 150; fs.frame_start = 1; fs.frame_end = 2; fs.lifetime = F1 + 10
fs.normal_factor = 0.25; fs.factor_random = 0.08; fs.brownian_factor = 0.25
fs.effector_weights.gravity = 0; fs.effector_weights.wind = 0.05; fs.effector_weights.turbulence = 0.3
fs.drag_factor = 0.6; fs.render_type = "OBJECT"; fs.instance_object = fly; fs.size_random = 0.6; fs.particle_size = 0.025
fs.emit_from = "FACE"; fs.distribution = "RAND"; fe.vertex_group_density = "grass"; fs.timestep = 0.04
fs.render_type = "OBJECT"
for pss in (pps, fs):
    pss.display_method = "DOT"

# ---------------------------------------------------------------- カメラ: 水面すれすれ → 花びらの中を上昇しつつ寄る
tgt = bpy.data.objects.new("Target", None); sc.collection.objects.link(tgt)
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 32; cam.data.sensor_width = 36
cam.data.dof.use_dof = True; cam.data.dof.focus_object = sheet; cam.data.dof.aperture_fstop = 1.8
cam.data.clip_end = 400
c = cam.constraints.new("TRACK_TO"); c.target = tgt; c.up_axis = "UP_Y"; c.track_axis = "TRACK_NEGATIVE_Z"
keys = [  # (frame offset, cam pos, target pos)
    (0,   (4.0, -10.5, 0.55), (0.0, 2.0, 1.9)),
    (110, (2.2, -8.2, 0.9),   (-0.3, 1.5, 2.3)),
    (210, (0.4, -6.2, 1.9),   (-0.2, 1.2, 2.6)),
    (300, (-0.6, -4.9, 2.25), (0.1, 1.0, 2.55)),
]
for fo, cp, tp in keys:
    cam.location = cp; tgt.location = tp
    cam.keyframe_insert("location", frame=F0 + fo); tgt.keyframe_insert("location", frame=F0 + fo)
for ob in (cam, tgt):
    for fc in ob.animation_data.action.fcurves:
        for kp in fc.keyframe_points: kp.interpolation = "BEZIER"; kp.easing = "AUTO"
for fc in tgt.animation_data.action.fcurves:   # 手持ち感
    nm = fc.modifiers.new("NOISE"); nm.scale = 45; nm.strength = 0.05
cam.data.dof.keyframe_insert("aperture_fstop", frame=F0)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "yozakura_theater.blend"))

# ---------------------------------------------------------------- レンダリング（粒子は先頭から順に計算）
frames = [int(f) for f in os.environ["FRAMES"].split(",")] if os.environ.get("FRAMES") else None
targets = [F0 - 1 + f for f in frames] if frames else list(range(F0, F1 + 1))
for f in range(1, max(targets) + 1):
    sc.frame_set(f)
    if f in targets:
        sc.render.filepath = os.path.join(OUT, f"f_{f - F0 + 1:04d}.png")
        if os.path.exists(sc.render.filepath):   # 途中再開用
            continue
        bpy.ops.render.render(write_still=True)
