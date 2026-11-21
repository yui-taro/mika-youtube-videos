# Blender script: 既存の動画2本をスクリーンにして3D空間でショーケースする縦型ショート
# 使い方: blender -b -P blender/showcase.py -- <out_dir> [engine]
import bpy, sys, os, math
argv = sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else []
OUT = os.path.abspath(argv[0] if argv else "render")
ENGINE = argv[1] if len(argv) > 1 else "BLENDER_EEVEE"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS, SECS = 30, 10
os.makedirs(OUT, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.engine = ENGINE
sc.render.resolution_x, sc.render.resolution_y = 720, 1280
sc.render.fps = FPS
sc.frame_start, sc.frame_end = 1, FPS*SECS
sc.render.image_settings.file_format = "PNG"
sc.render.filepath = os.path.join(OUT, "f_")
if ENGINE == "CYCLES":
    sc.cycles.samples = 24; sc.cycles.use_denoising = True; sc.cycles.device = "CPU"
else:
    e = sc.eevee
    e.use_bloom = True; e.bloom_intensity = 0.06
    e.use_ssr = True; e.use_gtao = True; e.taa_render_samples = 16
sc.view_settings.view_transform = "Filmic"; sc.view_settings.look = "Medium High Contrast"

# World: 夜の紫グラデーション
w = bpy.data.worlds.new("W"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.02, 0.01, 0.05, 1); bg.inputs[1].default_value = 1.0

def mat_emit_video(name, path):
    m = bpy.data.materials.new(name); m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    img = bpy.data.images.load(path); img.source = "MOVIE"
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img
    u = tex.image_user; u.frame_duration = img.frame_duration; u.use_auto_refresh = True; u.use_cyclic = True
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs[1].default_value = 1.4
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], out.inputs[0])
    return m

def mat_basic(name, col, rough=0.4, metal=0.0, emit=None, strength=0):
    m = bpy.data.materials.new(name); m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = (*col, 1); p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if emit:
        p.inputs["Emission Color"].default_value = (*emit, 1); p.inputs["Emission Strength"].default_value = strength
    return m

# 床（反射）
bpy.ops.mesh.primitive_plane_add(size=60, location=(0, 0, 0))
bpy.context.object.data.materials.append(mat_basic("Floor", (0.03, 0.03, 0.05), rough=0.15, metal=0.3))

def screen(name, video, x, rot):
    # 9:16 スクリーン + フレーム
    bpy.ops.mesh.primitive_cube_add(location=(x, 0, 2.3))
    fr = bpy.context.object; fr.name = name+"_frame"; fr.scale = (0.98, 0.08, 1.72)
    fr.data.materials.append(mat_basic("Frame", (0.05, 0.05, 0.06), rough=0.3, metal=0.8))
    bpy.ops.mesh.primitive_plane_add(size=1, location=(x, -0.085, 2.3), rotation=(math.radians(90), 0, 0))
    sp = bpy.context.object; sp.name = name; sp.scale = (1.8, 3.2, 1)
    sp.data.materials.append(mat_emit_video(name+"_mat", video))
    sp.parent = fr; sp.matrix_parent_inverse = fr.matrix_world.inverted()
    fr.rotation_euler = (0, 0, math.radians(rot))
    return fr

s1 = screen("Panda", os.path.join(ROOT, "red-panda.mp4"), -1.25, 12)
s2 = screen("Cat", os.path.join(ROOT, "dancing-cat.mov"), 1.25, -12)

# ふわふわ浮く
for i, s in enumerate((s1, s2)):
    for f in range(1, FPS*SECS+1, 15):
        s.location.z = 2.3 + 0.12*math.sin(f/FPS*2 + i*math.pi); s.keyframe_insert("location", index=2, frame=f)

# ネオンリングと浮遊キューブ
ring = bpy.data.materials.new("Neon"); ring.use_nodes = True
nt = ring.node_tree; nt.nodes.clear()
em = nt.nodes.new("ShaderNodeEmission"); em.inputs[0].default_value = (1.0, 0.25, 0.7, 1); em.inputs[1].default_value = 6
o = nt.nodes.new("ShaderNodeOutputMaterial"); nt.links.new(em.outputs[0], o.inputs[0])
bpy.ops.mesh.primitive_torus_add(major_radius=3.4, minor_radius=0.04, location=(0, 0.6, 0.05))
bpy.context.object.data.materials.append(ring)
neon2 = ring.copy(); neon2.node_tree.nodes["Emission"].inputs[0].default_value = (0.2, 0.7, 1.0, 1)
import random; random.seed(7)
for k in range(28):
    a = random.uniform(0, 2*math.pi); r = random.uniform(3.5, 7)
    bpy.ops.mesh.primitive_cube_add(size=random.uniform(0.08, 0.25),
        location=(r*math.cos(a), r*math.sin(a)+2, random.uniform(0.5, 6)))
    c = bpy.context.object; c.data.materials.append(neon2 if k % 2 else ring)
    c.rotation_euler = (random.random()*3, random.random()*3, 0); c.keyframe_insert("rotation_euler", frame=1)
    c.rotation_euler.z += math.radians(random.choice([-1, 1])*240); c.keyframe_insert("rotation_euler", frame=FPS*SECS)

# タイトル文字
bpy.ops.object.text_add(location=(0, -0.3, 4.75), rotation=(math.radians(90), 0, 0))
t = bpy.context.object; t.data.body = "MIKA ZOO"; t.data.align_x = "CENTER"; t.data.size = 0.75
t.data.extrude = 0.06; t.data.bevel_depth = 0.01
t.data.materials.append(mat_basic("Title", (1, 0.85, 0.3), emit=(1, 0.75, 0.2), strength=3))
t.scale = (0.01, 0.01, 0.01); t.keyframe_insert("scale", frame=1)
t.scale = (1.15, 1.15, 1.15); t.keyframe_insert("scale", frame=24)
t.scale = (1, 1, 1); t.keyframe_insert("scale", frame=32)

# ライト
for loc, col, en in (((-4, -3, 6), (1, 0.4, 0.8), 800), ((4, -3, 6), (0.3, 0.6, 1), 800), ((0, 4, 5), (1, 1, 1), 400)):
    bpy.ops.object.light_add(type="AREA", location=loc); L = bpy.context.object
    L.data.energy = en; L.data.color = col; L.data.size = 3
    d = L.constraints.new("TRACK_TO"); d.target = s1.parent if s1.parent else s1

# カメラ: 寄りから引きつつ周回
tgt = bpy.data.objects.new("Target", None); sc.collection.objects.link(tgt); tgt.location = (0, 0, 2.6)
for L in [o for o in sc.objects if o.type == "LIGHT"]: L.constraints[0].target = tgt
bpy.ops.object.camera_add(); cam = bpy.context.object; sc.camera = cam
cam.data.lens = 30; cam.data.dof.use_dof = True; cam.data.dof.focus_object = tgt; cam.data.dof.aperture_fstop = 2.8
tc = cam.constraints.new("TRACK_TO"); tc.target = tgt
N = FPS*SECS
for f in range(1, N+1, 10):
    p = (f-1)/(N-1); ang = math.radians(-35 + 70*p)
    dist = 4.5 + 4.5*math.sin(p*math.pi*0.5)
    cam.location = (dist*math.sin(ang), -dist*math.cos(ang), 2.2 + 1.2*p)
    cam.keyframe_insert("location", frame=f)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "showcase.blend"))
if os.environ.get("FRAMES"):  # テスト用: FRAMES=1,120 のように個別フレーム
    for f in map(int, os.environ["FRAMES"].split(",")):
        sc.frame_set(f); sc.render.filepath = os.path.join(OUT, f"test_{f:04d}.png"); bpy.ops.render.render(write_still=True)
else:
    bpy.ops.render.render(animation=True)
