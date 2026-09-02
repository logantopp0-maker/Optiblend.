bl_info = {
    "name": "OptiBlend",
    "author": "Logan Topp",
    "version": (1, 0, 0),
    "blender": (4, 0, 0),
    "location": "3D Viewport > OptiBlend asset bar / Q workflow wheel",
    "description": "A guided Blender workflow helper with progressive modes, asset placement, materials, scene tools and advanced pipeline checks.",
    "category": "3D View",
}

import bpy
import os
import math
import time
import bmesh
from mathutils import Vector, Quaternion
from bpy_extras.io_utils import ImportHelper

try:
    import gpu
    import blf
    from gpu_extras.batch import batch_for_shader
    DRAW_OK = True
except Exception:
    DRAW_OK = False


# =============================================================================
# OptiBlend V1.0.0 - FINAL V1 RELEASE
# =============================================================================
# OptiBlend started as a scene-optimisation experiment and grew into a workflow
# helper aimed at making Blender less intimidating at the start without hiding
# the real tools forever. Beginner, Intermediate and Advanced modes progressively
# reveal more of Blender and more of OptiBlend.
#
# The internal v123 operator/class namespace is intentionally left in place from
# development. Renaming every registered identifier for the public tag would add
# risk without changing anything the user sees.
# =============================================================================


# -----------------------------------------------------------------------------
# global state
# -----------------------------------------------------------------------------
KEYMAPS = []
ASSET_BAR_HANDLE = None
XYZ_HELPER_HANDLE = None
ASSET_BAR_RUNNING = False
FANCY_WHEEL_RUNNING = False
LAST_MODE_SEEN = None
ASSET_BAR_RECTS = {}
TEXTURE_CACHE = {}
PREVIEW_NAME = "OptiBlend_V123_Placement_Preview"
AREA_TYPE_BACKUP = {}
WORKSPACE_GUARD_ACTIVE = False
ASSET_LISTENER_GENERATION = 0

# Placement state is kept together because the asset bar, snapping and workspace
# switching all touch the same modal drag operation.
DRAG_STATE = {
    "kind": None,
    "key": None,
    "start": (0, 0),
    "mouse": (0, 0),
    "preview": None,
    "moved": False,
    "rotation_angle": 0.0,
    "rotation_axis": "Z",
    "axis_override": False,
    "last_normal": None,
    "last_target": None,
    "center_active": False,
}

# Beginner = the three tabs from the reference screenshot.
# Intermediate adds the next practical workspaces and Advanced unlocks almost all.
BEGINNER_WORKSPACES = ["Layout"]
INTERMEDIATE_WORKSPACES = ["Layout", "Modeling", "Sculpting", "Shading", "Rendering"]
ADVANCED_WORKSPACES = [
    "Layout", "Modeling", "Sculpting", "UV Editing", "Texture Paint",
    "Shading", "Animation", "Rendering", "Compositing", "Geometry Nodes",
    "Scripting",
]
DEFAULT_WORKSPACE_NAMES = set(ADVANCED_WORKSPACES + ["Video Editing"])

GREEN = (0.05, 1.0, 0.36, 1.0)
GREEN_SOFT = (0.05, 1.0, 0.36, 0.18)
CYAN = (0.15, 0.86, 1.0, 1.0)
ORANGE = (1.0, 0.48, 0.12, 1.0)
PURPLE = (0.60, 0.30, 1.0, 1.0)
WHITE = (0.93, 0.98, 0.95, 1.0)
TEXT_SOFT = (0.76, 0.84, 0.80, 1.0)
DARK = (0.018, 0.024, 0.022, 0.97)
DARK_2 = (0.035, 0.045, 0.041, 0.98)

# OptiMint is the fixed V1 visual language: mint for actions/positive state, cyan
# for guidance/snapping, purple for materials/advanced depth and orange for warnings.
THEME_NAME = "OptiMint"

# Guide content stays data-driven so the viewport overlay can change instructions
# without opening another Blender panel or adding more persistent UI.
GUIDE_CONTENT = {
    "Q": {"title":"Press Q = Helper", "accent":"CYAN", "lines":["Press Q to open or close the OptiBlend Helper.", "Use the helper when you forget where a tool is.", "Hover a big card to reveal smaller OptiBlend mini-tools.", "Pick Shapes, Materials or Guide to keep the workflow simple."], "footer":"TIP  Press Q again any time to bring the Helper back."},
    "G": {"title":"G = Move", "accent":"CYAN", "lines":["Select an object, then press G to move it.", "Press X, Y or Z after G to lock the movement to one axis.", "In Beginner mode the Move tool is turned on automatically as a visual backup.", "Try moving the object a small amount, then left click to confirm."], "footer":"LIVE  Watch the XYZ helper around the object while you move it."},
    "R": {"title":"R = Rotate", "accent":"CYAN", "lines":["Select an object, then press R to rotate it.", "Press X, Y or Z after R to rotate around one axis only.", "While dragging a new shape, the mouse wheel also rotates it live.", "Tap R during shape placement for a quick 90 degree turn."], "footer":"LIVE  Cylinder and Capsule now start on a sideways-friendly axis."},
    "S": {"title":"S = Scale", "accent":"CYAN", "lines":["Select an object, then press S to scale it.", "Press X, Y or Z after S to scale on one axis only.", "Scaling is easier to read when the object's bounding box centre is used.", "Use small changes first so the result stays easy to control."], "footer":"TIP  Bounding-box centre is used instead of a confusing mesh origin."},
    "TAB": {"title":"Tab = Edit Mode", "accent":"CYAN", "lines":["Press Tab to switch between Object Mode and Edit Mode.", "In Edit Mode, OptiBlend can switch to friendlier snapping choices automatically.", "Use Edit Mode when you want to change the mesh itself, not just move the object.", "Press Tab again to return to Object Mode."], "footer":"LIVE  The guide updates when Blender enters or leaves Edit Mode."},
    "AXIS": {"title":"X Y Z = Axis Lock", "accent":"CYAN", "lines":["After G, R or S, press X, Y or Z to constrain the action.", "This is one of Blender's most important beginner shortcuts.", "OptiBlend also draws a visible XYZ helper around the object, not at the origin.", "Use it to understand direction before learning more advanced tools."], "footer":"TIP  Try G then X for left/right movement, or R then Z for flat rotation."},
}


# -----------------------------------------------------------------------------
# shape library - more geometry so the scroll system actually has a purpose
# -----------------------------------------------------------------------------
SHAPES = {
    "CUBE": ("Cube", "shape_cube.png", "Blocks, walls and simple hard-surface guide."),
    "SPHERE": ("Sphere", "shape_sphere.png", "Rounded forms, heads and smooth shading guide."),
    "ICOSPHERE": ("Ico Sphere", "shape_icosphere.png", "Even triangular topology for rounded forms."),
    "CIRCLE": ("Circle", "shape_circle.png", "Flat circular base geometry."),
    "CYLINDER": ("Cylinder", "shape_cylinder.png", "Cups, poles, wheels and tubes."),
    "CONE": ("Cone", "shape_cone.png", "Spikes, roofs and tapered forms."),
    "PLANE": ("Plane", "shape_plane.png", "Floors, walls and flat modelling starts."),
    "TORUS": ("Torus", "shape_torus.png", "Rings, tyres and looped forms."),
    "MONKEY": ("Suzanne", "shape_monkey.png", "Blender's test mesh for shading and modifiers."),
    "GRID": ("Grid", "shape_grid.png", "A subdivided flat mesh for terrain or deformation."),
    "PYRAMID": ("Pyramid", "shape_pyramid.png", "Simple four-sided point form."),
    "CAPSULE": ("Capsule", "shape_capsule.png", "Rounded body shape for blockouts and characters."),
}


# -----------------------------------------------------------------------------
# procedural material library
# -----------------------------------------------------------------------------
# These categories mirror the kind of organisation used by large material
# browsers. Every preset creates an OptiBlend node GROUP, not just a colour value.
# Presets are intentionally lightweight procedural starting points, not a replacement
# for production texture libraries.
MATERIAL_LIBRARY = {
    # Common Surfaces
    "WOOD":       {"name":"Wood",       "category":"COMMON",     "icon":"mat_wood.png",       "style":"WOOD",   "c1":(0.28,0.10,0.035,1), "c2":(0.72,0.34,0.08,1), "rough":0.48},
    "METAL":      {"name":"Metal",      "category":"COMMON",     "icon":"mat_metal.png",      "style":"METAL",  "c1":(0.33,0.38,0.44,1),  "c2":(0.70,0.76,0.82,1), "rough":0.22},
    "GLASS":      {"name":"Glass",      "category":"COMMON",     "icon":"mat_glass.png",      "style":"GLASS",  "c1":(0.45,0.78,0.95,1),  "c2":(0.85,0.97,1.0,1),  "rough":0.06},
    "STONE":      {"name":"Stone",      "category":"COMMON",     "icon":"mat_stone.png",      "style":"NOISE",  "c1":(0.18,0.19,0.18,1),  "c2":(0.48,0.46,0.42,1), "rough":0.72},
    "BRICK":      {"name":"Brick",      "category":"COMMON",     "icon":"mat_brick.png",      "style":"BRICK",  "c1":(0.35,0.055,0.025,1),"c2":(0.68,0.22,0.09,1),  "rough":0.68},
    "CONCRETE":   {"name":"Concrete",   "category":"COMMON",     "icon":"mat_concrete.png",   "style":"NOISE",  "c1":(0.25,0.26,0.25,1),  "c2":(0.52,0.53,0.50,1), "rough":0.82},
    "TILES":      {"name":"Tiles",      "category":"COMMON",     "icon":"mat_tiles.png",      "style":"BRICK",  "c1":(0.10,0.28,0.38,1),  "c2":(0.45,0.75,0.82,1), "rough":0.30},
    "MARBLE":     {"name":"Marble",     "category":"COMMON",     "icon":"mat_marble.png",     "style":"MARBLE", "c1":(0.75,0.76,0.73,1),  "c2":(0.22,0.28,0.34,1), "rough":0.24},

    # Fabrics & Textiles
    "VELVET":     {"name":"Velvet",     "category":"FABRICS",    "icon":"mat_velvet.png",     "style":"VELVET", "c1":(0.18,0.012,0.07,1), "c2":(0.52,0.04,0.20,1),  "rough":0.76},
    "SUEDE":      {"name":"Suede",      "category":"FABRICS",    "icon":"mat_suede.png",      "style":"FABRIC", "c1":(0.27,0.13,0.06,1),  "c2":(0.58,0.31,0.14,1),  "rough":0.82},
    "LEATHER":    {"name":"Leather",    "category":"FABRICS",    "icon":"mat_leather.png",    "style":"LEATHER","c1":(0.12,0.035,0.012,1),"c2":(0.42,0.16,0.045,1), "rough":0.48},
    "EMBROIDERY": {"name":"Embroidery", "category":"FABRICS",    "icon":"mat_embroidery.png", "style":"FABRIC", "c1":(0.18,0.04,0.34,1),  "c2":(0.72,0.24,0.88,1),  "rough":0.62},
    "FLAT_WEAVE": {"name":"Flat Weave", "category":"FABRICS",    "icon":"mat_flat_weave.png", "style":"WEAVE",  "c1":(0.46,0.33,0.20,1),  "c2":(0.78,0.64,0.43,1),  "rough":0.78},
    "JACQUARD":   {"name":"Jacquard",   "category":"FABRICS",    "icon":"mat_jacquard.png",   "style":"WEAVE",  "c1":(0.025,0.12,0.26,1), "c2":(0.36,0.68,0.90,1),  "rough":0.68},

    # Natural Elements
    "GROUND":     {"name":"Ground",     "category":"NATURAL",    "icon":"mat_ground.png",     "style":"NOISE",  "c1":(0.15,0.095,0.04,1), "c2":(0.38,0.26,0.10,1),  "rough":0.92},
    "ROCK":       {"name":"Rock",       "category":"NATURAL",    "icon":"mat_rock.png",       "style":"NOISE",  "c1":(0.12,0.13,0.11,1),  "c2":(0.38,0.40,0.35,1),  "rough":0.88},
    "GRASS":      {"name":"Grass",      "category":"NATURAL",    "icon":"mat_grass.png",      "style":"NOISE",  "c1":(0.025,0.15,0.025,1),"c2":(0.18,0.50,0.08,1),  "rough":0.86},
    "SAND":       {"name":"Sand",       "category":"NATURAL",    "icon":"mat_sand.png",       "style":"NOISE",  "c1":(0.48,0.31,0.12,1),  "c2":(0.85,0.68,0.36,1),  "rough":0.92},
    "SOIL":       {"name":"Soil",       "category":"NATURAL",    "icon":"mat_soil.png",       "style":"NOISE",  "c1":(0.09,0.045,0.02,1), "c2":(0.28,0.12,0.045,1), "rough":0.95},
    "ICE":        {"name":"Ice",        "category":"NATURAL",    "icon":"mat_ice.png",        "style":"ICE",    "c1":(0.48,0.78,0.94,1),  "c2":(0.88,0.97,1.0,1),   "rough":0.14},
    "LIQUID":     {"name":"Liquid",     "category":"NATURAL",    "icon":"mat_liquid.png",     "style":"LIQUID", "c1":(0.015,0.20,0.42,1), "c2":(0.12,0.62,0.88,1),  "rough":0.12},

    # Man-made / Industrial
    "PLASTIC":    {"name":"Plastic",    "category":"INDUSTRIAL", "icon":"mat_plastic.png",    "style":"PLASTIC","c1":(0.025,0.20,0.60,1), "c2":(0.15,0.55,0.95,1),  "rough":0.32},
    "RUBBER":     {"name":"Rubber",     "category":"INDUSTRIAL", "icon":"mat_rubber.png",     "style":"RUBBER", "c1":(0.012,0.014,0.014,1),"c2":(0.09,0.10,0.10,1),   "rough":0.88},
    "ASPHALT":    {"name":"Asphalt",    "category":"INDUSTRIAL", "icon":"mat_asphalt.png",    "style":"NOISE",  "c1":(0.035,0.038,0.035,1),"c2":(0.20,0.21,0.19,1),  "rough":0.96},
    "PAPER":      {"name":"Paper",      "category":"INDUSTRIAL", "icon":"mat_paper.png",      "style":"PAPER",  "c1":(0.72,0.69,0.58,1),  "c2":(0.94,0.92,0.82,1),  "rough":0.86},
    "PLASTER":    {"name":"Plaster",    "category":"INDUSTRIAL", "icon":"mat_plaster.png",    "style":"NOISE",  "c1":(0.62,0.60,0.54,1),  "c2":(0.88,0.86,0.79,1),  "rough":0.88},
    "PAVING":     {"name":"Paving",     "category":"INDUSTRIAL", "icon":"mat_paving.png",     "style":"BRICK",  "c1":(0.22,0.19,0.15,1),  "c2":(0.49,0.42,0.32,1),  "rough":0.82},
    "ROOFING":    {"name":"Roofing",    "category":"INDUSTRIAL", "icon":"mat_roofing.png",    "style":"BRICK",  "c1":(0.14,0.11,0.10,1),  "c2":(0.42,0.31,0.27,1),  "rough":0.72},

    # Organic / Specialized
    "FOOD":       {"name":"Food",       "category":"ORGANIC",    "icon":"mat_food.png",       "style":"ORGANIC","c1":(0.50,0.16,0.035,1), "c2":(0.90,0.48,0.10,1),  "rough":0.50},
    "HUMAN":      {"name":"Human",      "category":"ORGANIC",    "icon":"mat_human.png",      "style":"ORGANIC","c1":(0.42,0.20,0.13,1),  "c2":(0.78,0.45,0.32,1),  "rough":0.46},
    "CERAMIC":    {"name":"Ceramic",    "category":"ORGANIC",    "icon":"mat_ceramic.png",    "style":"CERAMIC","c1":(0.64,0.70,0.78,1), "c2":(0.94,0.97,1.0,1),   "rough":0.18},
    "TECH":       {"name":"Tech",       "category":"ORGANIC",    "icon":"mat_tech.png",       "style":"TECH",   "c1":(0.005,0.06,0.08,1), "c2":(0.02,0.85,0.66,1),  "rough":0.26},

    # OptiBlend extras / beta tools
    "GLOW":       {"name":"Glow [BETA]", "category":"BETA",       "icon":"mat_glow.png",       "style":"GLOW",   "c1":(0.005,0.09,0.02,1), "c2":(0.02,1.0,0.30,1),   "rough":0.30},
    "CUSTOM":     {"name":"Custom",      "category":"BETA",       "icon":"mat_custom.png",     "style":"CUSTOM", "c1":(0.05,0.65,1.0,1),    "c2":(0.05,0.65,1.0,1),   "rough":0.38},
}

CATEGORY_LABELS = {
    "ALL":"All Materials",
    "COMMON":"Common Surfaces",
    "FABRICS":"Fabrics & Textiles",
    "NATURAL":"Natural Elements",
    "INDUSTRIAL":"Man-made / Industrial",
    "ORGANIC":"Organic & Specialized",
    "BETA":"OptiBlend / Beta",
}


# =============================================================================
# drawing helpers
# =============================================================================
def _rect(x, y, w, h, color):
    if not DRAW_OK:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    verts = ((x, y), (x + w, y), (x + w, y + h), (x, y + h))
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def _outline(x, y, w, h, color, thickness=1):
    _rect(x, y, w, thickness, color)
    _rect(x, y + h - thickness, w, thickness, color)
    _rect(x, y, thickness, h, color)
    _rect(x + w - thickness, y, thickness, h, color)


def _text(text, x, y, size=11, color=WHITE):
    if not DRAW_OK:
        return
    font = 0
    blf.size(font, size)
    blf.color(font, color[0], color[1], color[2], color[3])
    blf.position(font, x, y, 0)
    blf.draw(font, text)


def _circle(cx, cy, radius, color, segments=48):
    if not DRAW_OK:
        return
    verts = [(cx, cy)]
    for i in range(segments + 1):
        a = (i / segments) * math.tau
        verts.append((cx + math.cos(a) * radius, cy + math.sin(a) * radius))
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts})
    gpu.state.blend_set("ALPHA")
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    gpu.state.blend_set("NONE")


def _line(x1, y1, x2, y2, color, width=1.0):
    if not DRAW_OK:
        return
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batch = batch_for_shader(shader, "LINES", {"pos": [(x1, y1), (x2, y2)]})
    gpu.state.blend_set("ALPHA")
    try:
        gpu.state.line_width_set(width)
    except Exception:
        pass
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)
    try:
        gpu.state.line_width_set(1.0)
    except Exception:
        pass
    gpu.state.blend_set("NONE")


def asset_path(group, filename):
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", group, filename)


def _draw_image(filepath, x, y, w, h, angle=0.0):
    if not DRAW_OK:
        return False
    try:
        image = TEXTURE_CACHE.get(filepath)
        if image is None:
            image = bpy.data.images.load(filepath, check_existing=True)
            TEXTURE_CACHE[filepath] = image
        texture = gpu.texture.from_image(image)
        shader = gpu.shader.from_builtin("IMAGE")

        cx, cy = x + w / 2, y + h / 2
        local = [(-w/2,-h/2),(w/2,-h/2),(w/2,h/2),(-w/2,h/2)]
        ca, sa = math.cos(angle), math.sin(angle)
        verts = []
        for px, py in local:
            verts.append((cx + px*ca - py*sa, cy + px*sa + py*ca))
        uvs = ((0, 0), (1, 0), (1, 1), (0, 1))
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": verts, "texCoord": uvs})
        gpu.state.blend_set("ALPHA")
        shader.bind()
        shader.uniform_sampler("image", texture)
        batch.draw(shader)
        gpu.state.blend_set("NONE")
        return True
    except Exception:
        return False


# =============================================================================
# asset browser filtering / scrolling
# =============================================================================
def filtered_asset_keys(props):
    if props.asset_bar_mode == "SHAPES":
        q = props.shape_search.strip().lower()
        keys = list(SHAPES.keys())
        if q:
            keys = [k for k in keys if q in SHAPES[k][0].lower() or q in SHAPES[k][2].lower()]
        return keys

    q = props.material_search.strip().lower()
    category = props.material_category
    keys = []
    for key, data in MATERIAL_LIBRARY.items():
        if category != "ALL" and data["category"] != category:
            continue
        haystack = (data["name"] + " " + data["category"] + " " + data["style"]).lower()
        if q and q not in haystack:
            continue
        keys.append(key)
    return keys


def asset_bar_geometry(context):
    # This only scales OptiBlend. It does not touch Blender's global UI scale, which
    # is important because the whole point is to simplify Blender rather than change it.
    props = context.scene.optiblend_v123
    scale = max(0.70, min(1.50, props.ui_scale))
    width, height = context.region.width, context.region.height
    bar_h = int(124 * scale)
    bar_w = min(int(1080 * scale), width - 32)
    x = max(16, (width - bar_w) / 2)
    y = height - bar_h - int(22 * scale)
    return x, y, bar_w, bar_h


def asset_visible_capacity(context):
    x, y, bar_w, bar_h = asset_bar_geometry(context)
    scale = context.scene.optiblend_v123.ui_scale
    usable = max(120, bar_w - 190 * scale)
    return max(1, int(usable // (88 * scale)))


def clamp_scroll(context):
    props = context.scene.optiblend_v123
    total = len(filtered_asset_keys(props))
    cap = asset_visible_capacity(context)
    max_scroll = max(0.0, float(total - cap))
    props.asset_scroll_target = min(max(props.asset_scroll_target, 0.0), max_scroll)
    props.asset_scroll_current = min(max(props.asset_scroll_current, 0.0), max_scroll)


def asset_tile_rects(context):
    props = context.scene.optiblend_v123
    clamp_scroll(context)
    x, y, bar_w, bar_h = asset_bar_geometry(context)
    keys = filtered_asset_keys(props)
    scale = props.ui_scale
    start_x = x + 166 * scale
    tile_w = 80 * scale
    tile_h = 82 * scale
    gap = 8 * scale
    tile_y = y + 23 * scale
    span = tile_w + gap
    scroll = props.asset_scroll_current

    rects = []
    for i, key in enumerate(keys):
        tx = start_x + (i - scroll) * span
        if tx + tile_w < start_x - 8 or tx > x + bar_w - 42:
            continue
        rects.append((key, (tx, tile_y, tile_w, tile_h), i))
    return rects


def asset_under_mouse(context, mx, my):
    for key, (x, y, w, h), index in asset_tile_rects(context):
        if x <= mx <= x + w and y <= my <= y + h:
            return key
    return None


def point_in_asset_bar(context, mx, my):
    x, y, w, h = asset_bar_geometry(context)
    return x <= mx <= x + w and y <= my <= y + h


def ui_accent(props):
    # Mode colour is the base identity now, then temporary drag states sit on top of it.
    # This gives each level a clearer visual feel instead of every mode looking almost the same.
    mode_colour = {"BEGINNER": CYAN, "INTERMEDIATE": GREEN, "ADVANCED": PURPLE}.get(getattr(props, "mode", "BEGINNER"), GREEN)
    if DRAG_STATE["kind"] == "SHAPE":
        return CYAN
    if DRAG_STATE["kind"] == "MATERIAL":
        return ORANGE
    if props.asset_bar_mode == "MATERIALS":
        return PURPLE if getattr(props, "mode", "BEGINNER") != "BEGINNER" else CYAN
    return mode_colour


def draw_asset_bar():
    if not DRAW_OK:
        return
    context = bpy.context
    if not context or not context.scene or not hasattr(context.scene, "optiblend_v123"):
        return
    if not context.area or context.area.type != "VIEW_3D":
        return

    props = context.scene.optiblend_v123
    if not props.asset_bar_visible:
        return

    x, y, bar_w, bar_h = asset_bar_geometry(context)
    scale = props.ui_scale
    pulse = (math.sin(time.time() * 3.0) + 1.0) / 2.0
    accent = ui_accent(props)

    # full-bar glow changes colour depending on what is happening. It is a small
    # visual cue rather than another text instruction taking up the viewport.
    for pad, alpha in ((12,0.018),(8,0.028),(4,0.045)):
        _rect(x-pad, y-pad, bar_w+pad*2, bar_h+pad*2, (accent[0],accent[1],accent[2],alpha + pulse*alpha))
    _rect(x, y, bar_w, bar_h, DARK)
    _outline(x, y, bar_w, bar_h, (accent[0],accent[1],accent[2],0.72), 1)
    _rect(x, y + bar_h - 3, bar_w, 3, (accent[0],accent[1],accent[2],0.72 + pulse*0.22))

    # brand block
    _rect(x, y, 154*scale, bar_h, (0.012,0.055,0.032,0.97))
    _text("OPTIBLEND", x + 13*scale, y + 86*scale, max(9,int(15*scale)), WHITE)
    _text("V1 FINAL", x + 13*scale, y + 68*scale, max(7,int(8*scale)), ui_accent(props))
    _text("PRESS Q = HELPER", x + 13*scale, y + 55*scale, max(6,int(7*scale)), CYAN)
    mode_label = "SHAPES" if props.asset_bar_mode == "SHAPES" else "MATERIALS"
    _text(mode_label, x + 13*scale, y + 42*scale, max(7,int(10*scale)), accent)
    _text(props.mode.title(), x + 13*scale, y + 25*scale, max(7,int(9*scale)), TEXT_SOFT)

    if props.asset_bar_mode == "MATERIALS":
        _text(CATEGORY_LABELS.get(props.material_category, "All"), x + 13*scale, y + 10*scale, max(6,int(7*scale)), TEXT_SOFT)
    else:
        _text("Scroll for more", x + 13*scale, y + 10*scale, max(6,int(7*scale)), TEXT_SOFT)

    entries = SHAPES if props.asset_bar_mode == "SHAPES" else MATERIAL_LIBRARY
    group = "shape_previews" if props.asset_bar_mode == "SHAPES" else "material_previews"
    hovered = props.hover_asset

    for key, (tx, ty, tw, th), index in asset_tile_rects(context):
        data = entries[key]
        is_hover = key == hovered
        phase = time.time()*2.2 + index*0.55
        bob = math.sin(phase) * (1.5 if props.animate_assets else 0.0)
        glow = (math.sin(phase*1.3)+1)/2
        yy = ty + bob

        if is_hover:
            for pad in (6,3):
                _rect(tx-pad, yy-pad, tw+pad*2, th+pad*2, (accent[0],accent[1],accent[2],0.04 + glow*0.035))
        elif props.ui_glow_enabled:
            _rect(tx-2, yy-2, tw+4, th+4, (accent[0],accent[1],accent[2],0.008 + glow*0.012))

        _rect(tx, yy, tw, th, (0.045,0.060,0.052,0.99) if not is_hover else (0.035,0.16,0.09,0.99))
        _outline(tx, yy, tw, th, accent if is_hover else (0.22,0.29,0.26,1), 2 if is_hover else 1)

        icon_name = data[1] if props.asset_bar_mode == "SHAPES" else data["icon"]
        angle = math.sin(phase*0.75) * 0.035 if props.animate_assets else 0.0
        _draw_image(asset_path(group, icon_name), tx+5*scale, yy+22*scale, tw-10*scale, 54*scale, angle)
        _rect(tx, yy, tw, 20*scale, (0.015,0.022,0.019,0.96))
        label = data[0] if props.asset_bar_mode == "SHAPES" else data["name"]
        _text(label[:16], tx+6*scale, yy+6*scale, max(6,int(8*scale)), WHITE)

    # scrollbar, because with 30+ materials it needs to feel like a browser now.
    keys = filtered_asset_keys(props)
    cap = asset_visible_capacity(context)
    if len(keys) > cap:
        track_x = x + 166*scale
        track_w = bar_w - 210*scale
        track_y = y + 8*scale
        _rect(track_x, track_y, track_w, 3*scale, (0.15,0.20,0.18,0.9))
        max_scroll = max(1.0, len(keys)-cap)
        thumb_w = max(34*scale, track_w * (cap/len(keys)))
        thumb_x = track_x + (track_w-thumb_w) * (props.asset_scroll_current/max_scroll)
        _rect(thumb_x, track_y-1*scale, thumb_w, 5*scale, (accent[0],accent[1],accent[2],0.85))

    # Bigger close target after class feedback. The old 28px X looked neat but was
    # unnecessarily fiddly, especially when the shelf was scaled down.
    close_rect = (x + bar_w - 48*scale, y + bar_h - 43*scale, 38*scale, 38*scale)
    ASSET_BAR_RECTS[context.area.as_pointer()] = {"close": close_rect}
    _rect(*close_rect, (0.055,0.10,0.075,0.98))
    _outline(*close_rect, (CYAN[0],CYAN[1],CYAN[2],0.7), 1)
    _text("X", close_rect[0]+13*scale, close_rect[1]+11*scale, max(10,int(14*scale)), CYAN)

    # Compact hover teaching. It is attached to the bar instead of being a large
    # floating note panel in the corner.
    if hovered and props.show_hover_tips and props.mode != "ADVANCED" and hovered in entries:
        if props.asset_bar_mode == "SHAPES":
            title = entries[hovered][0]
            tip = entries[hovered][2]
        else:
            title = entries[hovered]["name"]
            tip = "Procedural node-group preset. Drag onto a mesh to apply."
        tip_x = x + 168*scale
        tip_y = y - 30*scale
        tip_w = min(620*scale, bar_w - 200*scale)
        _rect(tip_x, tip_y, tip_w, 25*scale, (0.012,0.032,0.027,0.97))
        _outline(tip_x, tip_y, tip_w, 25*scale, (accent[0],accent[1],accent[2],0.56), 1)
        _text(title + "  -  " + tip, tip_x+9*scale, tip_y+8*scale, max(6,int(8*scale)), TEXT_SOFT)

    if DRAG_STATE["kind"]:
        mx, my = DRAG_STATE["mouse"]
        key = DRAG_STATE["key"]
        if DRAG_STATE["kind"] == "MATERIAL":
            label = MATERIAL_LIBRARY[key]["name"]
            _rect(mx+15, my+10, 145, 25, (0.02,0.035,0.028,0.96))
            _outline(mx+15, my+10, 145, 25, ORANGE, 1)
            _text("Drop material: " + label[:15], mx+22, my+18, 8, WHITE)
        elif DRAG_STATE["kind"] == "SHAPE" and DRAG_STATE.get("preview") is not None:
            # Contextual help follows the dragged object instead of bringing the old
            # giant notes card back. This is only visible while the action matters.
            label = SHAPES[key][0]
            target = DRAG_STATE.get("last_target")
            centered = DRAG_STATE.get("center_active", False)
            box_w = 330
            _rect(mx+16, my+12, box_w, 42, (0.012,0.032,0.027,0.96))
            _outline(mx+16, my+12, box_w, 42, CYAN if not centered else ORANGE, 1)
            state = "CENTRE -> " + target.name[:18] if centered and target else "Drag " + label
            _text(state, mx+24, my+36, 9, WHITE)
            _text("Wheel rotate | R = 90 turn | Alt+R reset | Ctrl=centre | X/Y/Z axis", mx+24, my+20, 7, TEXT_SOFT)


# =============================================================================
# centred XYZ helper + drag visibility helper
# =============================================================================
# Feedback specifically asked for XYZ around the visible object rather than the origin.
# Imported objects can have their origin somewhere completely unrelated to the mesh, so
# I calculate the world-space bounding-box centre instead. This is also why Beginner
# mode switches Blender's pivot to BOUNDING_BOX_CENTER below.
def object_bbox_center_world(obj):
    if not obj:
        return Vector((0,0,0))
    if not getattr(obj, "bound_box", None):
        return obj.matrix_world.translation.copy()
    pts=[obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return sum(pts,Vector((0,0,0))) / max(1,len(pts))


def object_bbox_radius_world(obj):
    centre=object_bbox_center_world(obj)
    if not obj or not getattr(obj,"bound_box",None):
        return 1.0
    pts=[obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    return max((p-centre).length for p in pts) or 1.0


def guide_status_text(context, key):
    # The guide updates from live Blender state instead of acting like a static help poster.
    # These status lines are intentionally small and defensive so a missing object
    # or a strange mode switch never throws a traceback during a teaching moment.
    try:
        if key == "TAB":
            return "STATUS  COMPLETE" if str(context.mode).startswith("EDIT") else "STATUS  PRESS TAB TO ENTER EDIT MODE"
        if key in {"G", "R", "S", "AXIS"}:
            obj = context.active_object
            if obj:
                return f"STATUS  Active object: {obj.name}"
            return "STATUS  Select one object first"
        if key == "Q":
            return "STATUS  Helper ready"
    except Exception:
        pass
    return "STATUS  Guide active"


def activate_live_guide(context, key):
    props = context.scene.optiblend_v123
    info = GUIDE_CONTENT.get(key, GUIDE_CONTENT.get("Q"))
    props.live_guide_visible = True
    props.live_guide_key = key
    props.live_guide_title = info.get("title", "Guide")
    props.live_guide_footer = info.get("footer", "")
    try:
        set_move_tool(context)
    except Exception:
        pass
    tag_redraw(context)


def clear_live_guide(context=None):
    try:
        props = (context.scene if context else bpy.context.scene).optiblend_v123
        props.live_guide_visible = False
        props.live_guide_key = ""
        props.live_guide_title = ""
        props.live_guide_footer = ""
    except Exception:
        pass
    tag_redraw(context)


def draw_live_guide_overlay(context, props):
    if not getattr(props, "live_guide_visible", False):
        return
    info = GUIDE_CONTENT.get(props.live_guide_key, GUIDE_CONTENT.get("Q"))
    accent_name = info.get("accent", "CYAN")
    accent = CYAN if accent_name == "CYAN" else PURPLE if accent_name == "PURPLE" else GREEN

    # This card is deliberately bigger than the old tiny notes. The learner should be
    # able to read it without squinting, then get back to the viewport straight away.
    x, y = 32, 56
    w, h = 610, 214
    pulse = (math.sin(time.time() * 3.0) + 1.0) / 2.0
    _rect(x, y, w, h, (0.015, 0.03, 0.03, 0.95))
    _outline(x, y, w, h, (accent[0], accent[1], accent[2], 1.0), 2)
    _outline(x-4, y-4, w+8, h+8, (accent[0], accent[1], accent[2], 0.08 + pulse*0.07), 4)
    _text(props.live_guide_title or info.get("title", "Guide"), x + 18, y + h - 36, 18, WHITE)
    _text(guide_status_text(context, props.live_guide_key), x + 18, y + h - 58, 10, accent)

    lines = info.get("lines", [])
    for idx, line in enumerate(lines[:6]):
        _text(line, x + 18, y + h - 92 - idx*24, 11, WHITE if idx == 0 else TEXT_SOFT)

    footer = props.live_guide_footer or info.get("footer", "")
    if footer:
        _rect(x + 14, y + 14, w - 28, 30, (0.025, 0.05, 0.05, 0.88))
        _outline(x + 14, y + 14, w - 28, 30, (accent[0], accent[1], accent[2], 0.55), 1)
        _text(footer, x + 24, y + 22, 10, accent)

    _text("GUIDE ACTIVE  |  Press Q for Helper  |  Esc closes drag actions", x + 18, y + 8, 9, TEXT_SOFT)


def draw_xyz_helper():
    if not DRAW_OK:
        return
    context=bpy.context
    if not context or not context.scene or not hasattr(context.scene,"optiblend_v123"):
        return
    props=context.scene.optiblend_v123
    if not props.object_xyz_helper or props.mode=="ADVANCED":
        return
    if not context.area or context.area.type!="VIEW_3D" or not context.region_data:
        return
    obj=context.active_object
    if not obj or obj.type!="MESH":
        return
    try:
        from bpy_extras import view3d_utils
        centre=object_bbox_center_world(obj)
        radius=max(0.35,object_bbox_radius_world(obj)*0.45)
        c2=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,centre)
        if c2 is None:
            return
        pulse=(math.sin(time.time()*3.2)+1)/2
        axes=(
            (Vector((radius,0,0)),(1.0,0.18,0.18,1.0),"X"),
            (Vector((0,radius,0)),(0.18,1.0,0.28,1.0),"Y"),
            (Vector((0,0,radius)),(0.22,0.55,1.0,1.0),"Z"),
        )
        for vec,col,label in axes:
            e2=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,centre+vec)
            if e2 is None: continue
            _line(c2.x,c2.y,e2.x,e2.y,(col[0],col[1],col[2],0.10+pulse*0.07),7)
            _line(c2.x,c2.y,e2.x,e2.y,col,2)
            _text(label,e2.x+4,e2.y+4,10,col)
        _circle(c2.x,c2.y,6,(0.7,1.0,0.85,0.55))

        # Matthew's feedback was that a dragged object should be impossible to lose.
        # The preview is already wireframe; this adds a second glowing 2D bounding box.
        preview=DRAG_STATE.get("preview")
        if preview is not None:
            pts=[]
            for corner in preview.bound_box:
                p=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,preview.matrix_world@Vector(corner))
                if p is not None: pts.append(p)
            if pts:
                minx,maxx=min(p.x for p in pts),max(p.x for p in pts)
                miny,maxy=min(p.y for p in pts),max(p.y for p in pts)
                _outline(minx-4,miny-4,(maxx-minx)+8,(maxy-miny)+8,(CYAN[0],CYAN[1],CYAN[2],0.95),2)
                _outline(minx-8,miny-8,(maxx-minx)+16,(maxy-miny)+16,(CYAN[0],CYAN[1],CYAN[2],0.12+pulse*0.08),5)

        draw_live_guide_overlay(context, props)
    except Exception:
        # Visual teaching code should never be allowed to stop modelling.
        pass


def enable_xyz_helper_draw():
    global XYZ_HELPER_HANDLE
    if DRAW_OK and XYZ_HELPER_HANDLE is None:
        XYZ_HELPER_HANDLE=bpy.types.SpaceView3D.draw_handler_add(draw_xyz_helper,(),"WINDOW","POST_PIXEL")


def disable_xyz_helper_draw():
    global XYZ_HELPER_HANDLE
    if XYZ_HELPER_HANDLE is not None:
        try: bpy.types.SpaceView3D.draw_handler_remove(XYZ_HELPER_HANDLE,"WINDOW")
        except Exception: pass
        XYZ_HELPER_HANDLE=None


def enable_asset_bar_draw():
    global ASSET_BAR_HANDLE
    if DRAW_OK and ASSET_BAR_HANDLE is None:
        ASSET_BAR_HANDLE = bpy.types.SpaceView3D.draw_handler_add(draw_asset_bar, (), "WINDOW", "POST_PIXEL")


def disable_asset_bar_draw():
    global ASSET_BAR_HANDLE
    if ASSET_BAR_HANDLE is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(ASSET_BAR_HANDLE, "WINDOW")
        except Exception:
            pass
        ASSET_BAR_HANDLE = None


def tag_redraw(context=None):
    # Global redraw is slower than redrawing one area, but it is the safe fallback.
    # I would rather redraw two viewports than crash because a workspace changed and
    # the modal operator is still holding a dead area context for one timer tick.
    try:
        wm = bpy.context.window_manager
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()
    except Exception:
        pass


def safe_area_redraw(context=None):
    """Redraw the current viewport if it still exists, otherwise redraw all viewports."""
    # This specifically fixes the R3 NoneType/tag_redraw traceback from workspace
    # switching. Modal TIMER events are allowed to arrive with context.area == None.
    try:
        area = getattr(context, "area", None) if context is not None else None
        if area is not None and area.type == "VIEW_3D":
            area.tag_redraw()
            return
    except (ReferenceError, AttributeError, RuntimeError):
        # ReferenceError matters here because Blender RNA objects can become invalid
        # after a screen/workspace gets replaced even if Python still has a reference.
        pass
    tag_redraw(context)


def safe_area_pointer(context=None):
    # Rect dictionaries are keyed per viewport. If the viewport disappeared during a
    # workspace switch, None is a perfectly valid answer and the close-button test can
    # simply be skipped for that event.
    try:
        area = getattr(context, "area", None) if context is not None else None
        return area.as_pointer() if area is not None else None
    except (ReferenceError, AttributeError, RuntimeError):
        return None


def redraw_update(self, context):
    self.asset_scroll_current = 0.0
    self.asset_scroll_target = 0.0
    tag_redraw(context)


# -----------------------------------------------------------------------------
# modal listener lifetime helpers
# -----------------------------------------------------------------------------
def invalidate_asset_bar_listener():
    global ASSET_BAR_RUNNING, ASSET_LISTENER_GENERATION
    # Workspace changes can invalidate the screen/area that started a modal operator.
    # Bumping this number tells the old listener that it belongs to the old screen.
    ASSET_LISTENER_GENERATION += 1
    ASSET_BAR_RUNNING = False


def restart_asset_bar_listener_timer():
    # A short delay gives Blender time to finish swapping the workspace before I ask
    # for a new VIEW_3D context. This is intentionally boring/reliable over clever.
    try:
        if bpy.context.scene and hasattr(bpy.context.scene, "optiblend_v123"):
            ensure_asset_bar_listener(bpy.context)
            if ASSET_BAR_RUNNING:
                return None
    except Exception as e:
        print("OptiBlend listener restart waiting:", e)
    return 0.20


def queue_asset_bar_listener_restart():
    try:
        bpy.app.timers.register(restart_asset_bar_listener_timer, first_interval=0.20)
    except Exception:
        # If timers are unavailable during shutdown/reload the add-on can still open
        # the listener next time the user presses Shapes or Materials.
        pass


# =============================================================================
# workspace + beginner interface control
# This is still the section I expect to break most between Blender versions because
# Workspaces are stored data blocks as well as live UI state. The Test Lab
# workspace button around until I have tried this on several fresh startup files.
# =============================================================================
def startup_blend_candidates():
    paths = []
    try:
        user_config = bpy.utils.user_resource("CONFIG")
        if user_config:
            paths.append(os.path.join(user_config, "startup.blend"))
    except Exception:
        pass
    for resource_type in ("LOCAL", "SYSTEM"):
        try:
            base = bpy.utils.resource_path(resource_type)
            paths.append(os.path.join(base, "datafiles", "startup.blend"))
            paths.append(os.path.join(base, "config", "startup.blend"))
        except Exception:
            pass
    try:
        binary_dir = os.path.dirname(bpy.app.binary_path)
        version_folder = f"{bpy.app.version[0]}.{bpy.app.version[1]}"
        paths.append(os.path.join(binary_dir, version_folder, "datafiles", "startup.blend"))
        paths.append(os.path.join(os.path.dirname(binary_dir), version_folder, "datafiles", "startup.blend"))
    except Exception:
        pass
    clean = []
    for path in paths:
        if path and os.path.isfile(path) and path not in clean:
            clean.append(path)
    return clean


def append_real_workspace(context, name):
    if name in bpy.data.workspaces:
        return True

    # Library loading is less context-sensitive than the old operator method.
    # This should bring the real saved Modeling/Shading workspace back instead of
    # making a renamed clone of Layout like the early build did.
    for filepath in startup_blend_candidates():
        try:
            with bpy.data.libraries.load(filepath, link=False) as (data_from, data_to):
                if name in data_from.workspaces:
                    data_to.workspaces = [name]
            if name in bpy.data.workspaces:
                return True
        except Exception as e:
            print("OptiBlend workspace library load skipped:", name, e)

    # Fallback for installs where workspaces are not exposed through library load.
    for filepath in startup_blend_candidates():
        try:
            bpy.ops.workspace.append_activate(idname=name, filepath=filepath)
            if name in bpy.data.workspaces:
                return True
        except Exception:
            pass
    return False


def safe_remove_workspace(ws):
    try:
        bpy.data.workspaces.remove(ws)
        return True
    except Exception:
        try:
            bpy.data.workspaces.remove(ws, do_unlink=True)
            return True
        except Exception:
            return False


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def wanted_workspaces_for_mode(mode):
    if mode == "BEGINNER":
        return BEGINNER_WORKSPACES
    if mode == "INTERMEDIATE":
        return INTERMEDIATE_WORKSPACES
    return ADVANCED_WORKSPACES


def apply_workspace_set(context, wanted):
    # Changing workspaces is one of the most context-sensitive things this add-on does.
    # I invalidate the old asset listener first so it cannot keep trying to redraw the
    # workspace that Blender is about to remove. The delayed restart happens in
    # apply_mode() after the workspace list is stable again.
    invalidate_asset_bar_listener()

    for name in wanted:
        append_real_workspace(context, name)

    fallback = bpy.data.workspaces.get(wanted[0]) if wanted else None
    wanted_set = set(wanted)

    # Every open window is moved to an allowed workspace before removal. This is
    # the missing step that can leave old tabs stuck around if Blender still has a
    # window referencing one of them.
    if fallback:
        for window in bpy.context.window_manager.windows:
            try:
                if window.workspace.name not in wanted_set:
                    window.workspace = fallback
            except Exception:
                pass

    removed = []
    for ws in list(bpy.data.workspaces):
        if ws.name in DEFAULT_WORKSPACE_NAMES and ws.name not in wanted_set:
            if safe_remove_workspace(ws):
                removed.append(ws.name)

    # Reattach the asset listener after the screen swap. This also covers the Test Lab
    # workspace test and the delayed guard pass, not just the normal mode buttons.
    queue_asset_bar_listener_restart()
    return removed


def enforce_workspace_mode_once():
    global WORKSPACE_GUARD_ACTIVE
    try:
        scene = bpy.context.scene
        if not scene or not hasattr(scene, "optiblend_v123"):
            WORKSPACE_GUARD_ACTIVE = False
            return None
        props = scene.optiblend_v123
        if props.workspace_lock_enabled:
            apply_workspace_set(bpy.context, wanted_workspaces_for_mode(props.mode))
    except Exception as e:
        print("OptiBlend workspace guard skipped:", e)
    WORKSPACE_GUARD_ACTIVE = False
    return None


def queue_workspace_guard():
    global WORKSPACE_GUARD_ACTIVE
    if WORKSPACE_GUARD_ACTIVE:
        return
    WORKSPACE_GUARD_ACTIVE = True
    try:
        bpy.app.timers.register(enforce_workspace_mode_once, first_interval=0.45)
    except Exception:
        WORKSPACE_GUARD_ACTIVE = False


def simplify_beginner_ui(context, enabled):
    # Beginner uses the former Properties-side area as the main Outliner, while the
    # original Outliner becomes a UV helper. That leaves one clear scene tree instead
    # of two duplicate Outliners. Original editor types are stored so the normal
    # Properties + Outliner layout can be restored in Intermediate/Advanced.
    props = context.scene.optiblend_v123
    if not props.simplify_beginner_ui:
        enabled = False

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            key = area.as_pointer()

            # Save the starting type once for the two side editors OptiBlend changes.
            if key not in AREA_TYPE_BACKUP and area.type in {"PROPERTIES", "OUTLINER"}:
                AREA_TYPE_BACKUP[key] = area.type

            original_type = AREA_TYPE_BACKUP.get(key)

            if not enabled:
                # Leaving Beginner restores the original Blender editor types.
                if original_type and area.type != original_type:
                    try:
                        area.type = original_type
                    except Exception:
                        pass

                if original_type == "OUTLINER" and area.type == "OUTLINER":
                    try:
                        area.spaces.active.display_mode = "VIEW_LAYER"
                    except Exception:
                        pass
                elif original_type == "PROPERTIES" and area.type == "PROPERTIES":
                    try:
                        area.spaces.active.context = 'OBJECT'
                    except Exception:
                        pass
                continue

            # BEGINNER MODE ------------------------------------------------------
            if original_type == "PROPERTIES":
                # Beginner layout rule:
                # put the Properties-side editor BACK to a normal Outliner.
                try:
                    area.type = "OUTLINER"
                    area.spaces.active.display_mode = "VIEW_LAYER"
                except Exception:
                    pass

            elif original_type == "OUTLINER":
                # Keep the other side editor useful but different, otherwise the user
                # ends up with two identical Scene Collection panels again.
                try:
                    area.type = "IMAGE_EDITOR"
                    try:
                        area.ui_type = 'UV'
                    except Exception:
                        pass
                except Exception:
                    pass

            if area.type == "VIEW_3D":
                space = area.spaces.active
                try:
                    # Beginner stays visually calm. The Move tool/gizmo itself is still
                    # available automatically, but the extra toolbar/sidebar clutter is hidden.
                    space.show_region_toolbar = False
                    space.show_region_ui = False
                except Exception:
                    pass


def apply_transform_setup(context, mode):
    try:
        context.scene.transform_orientation_slots[0].type = "GLOBAL"
        # Beginner/Intermediate use the centre of the visible object rather than its
        # origin. This makes the XYZ helper and Blender's pivot teach the same idea.
        context.scene.tool_settings.transform_pivot_point = "BOUNDING_BOX_CENTER" if mode != "ADVANCED" else "MEDIAN_POINT"
    except Exception:
        pass

    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type != "VIEW_3D":
                continue
            space = area.spaces.active
            space.show_gizmo = True
            try:
                space.show_gizmo_tool = True
                space.show_gizmo_navigate = True
            except Exception:
                pass
            space.overlay.show_floor = True
            space.overlay.show_axis_x = True
            space.overlay.show_axis_y = True
            space.overlay.show_stats = mode == "ADVANCED"
            space.overlay.show_relationship_lines = mode != "BEGINNER"
            try:
                space.overlay.show_cursor = mode != "BEGINNER"
            except Exception:
                pass
            if mode == "BEGINNER":
                space.shading.type = "MATERIAL"
            elif mode == "INTERMEDIATE":
                space.shading.type = "SOLID"
            else:
                try:
                    space.shading.type = "RENDERED" if context.scene.render.engine == 'BLENDER_EEVEE' else "MATERIAL"
                except Exception:
                    space.shading.type = "MATERIAL"


def set_move_tool(context):
    try:
        bpy.ops.wm.tool_set_by_id(name="builtin.move")
    except Exception:
        pass


def apply_blender_snapping(context):
    props = context.scene.optiblend_v123
    ts = context.scene.tool_settings
    try:
        # Edit mode is separate from the drag-placement system. A new modeller is much
        # more likely to want vertices, edges, faces and midpoints than floor increments
        # while editing actual mesh geometry, so I switch the targets automatically.
        if getattr(context, "mode", "") == "EDIT_MESH" and props.edit_mode_smart_snap:
            ts.use_snap = True
            try:
                ts.snap_elements = {"VERTEX", "EDGE", "FACE", "EDGE_MIDPOINT", "FACE_MIDPOINT"}
            except Exception:
                ts.snap_elements = {"VERTEX", "EDGE", "FACE"}
            try: ts.snap_target = "CLOSEST"
            except Exception: pass
            for attr,value in (("use_snap_self",True),("use_snap_edit",True),("use_snap_nonedit",True)):
                try: setattr(ts,attr,value)
                except Exception: pass
            return

        if props.preview_snap_mode == "GRID":
            ts.use_snap = True
            ts.snap_elements = {"INCREMENT"}
            ts.use_snap_align_rotation = False
        elif props.preview_snap_mode == "SURFACE":
            ts.use_snap = True
            ts.snap_elements = {"FACE"}
            ts.use_snap_align_rotation = False
        else:
            ts.use_snap = False
    except Exception:
        pass


def mode_watch_timer():
    # Pressing Tab to enter Edit Mode does not call an OptiBlend button, so this tiny
    # watcher reapplies snapping when Blender's mode changes. Half a second keeps it
    # responsive without turning this into a permanent high-frequency background task.
    global LAST_MODE_SEEN
    try:
        context=bpy.context
        if not context.scene or not hasattr(context.scene,"optiblend_v123"):
            return 0.5
        current=getattr(context,"mode","")
        if current != LAST_MODE_SEEN:
            LAST_MODE_SEEN=current
            apply_blender_snapping(context)
            tag_redraw(context)
    except Exception:
        pass
    return 0.5


def set_report(context, text):
    try:
        context.scene.optiblend_v123.report = text
    except Exception:
        pass


def apply_mode(context, mode):
    props = context.scene.optiblend_v123
    props.mode = mode
    # If the layout mode changes, I clear the old guide so a beginner does not see
    # instructions that belong to a previous complexity level.
    clear_live_guide(context)

    if mode == "BEGINNER":
        props.preview_snap_mode = "GRID"
        props.show_hover_tips = True
        props.asset_bar_visible = True
        props.asset_bar_mode = "SHAPES"
        if props.auto_beginner_lights:
            ensure_default_lighting(context)
    elif mode == "INTERMEDIATE":
        # Intermediate opens Blender back up a bit more. The learner should still have
        # guidance, but the layout should start feeling like a real modelling workspace.
        props.preview_snap_mode = "GRID"
        props.show_hover_tips = True
        props.asset_bar_visible = True
    else:
        # Advanced intentionally gives more depth and fewer training wheels.
        props.preview_snap_mode = "SURFACE"
        props.show_hover_tips = False
        props.asset_bar_visible = True

    removed = apply_workspace_set(context, wanted_workspaces_for_mode(mode)) if props.workspace_lock_enabled else []
    simplify_beginner_ui(context, mode == "BEGINNER")
    apply_transform_setup(context, mode)
    apply_blender_snapping(context)
    set_move_tool(context)
    queue_workspace_guard()

    set_report(context, f"{mode.title()} mode applied.\nWorkspaces visible: {', '.join(wanted_workspaces_for_mode(mode))}\nRemoved extra standard tabs: {len(removed)}\nPress Q to open/close the OptiBlend Helper.")
    # Start a fresh listener after Blender has had a moment to settle into the new
    # screen. Calling it immediately used to leave the old and new UI contexts mixed.
    queue_asset_bar_listener_restart()
    tag_redraw(context)


# =============================================================================
# normal scene helpers
# These helpers are intentionally small. If camera/light setup gets more complicated
# later I should split it into its own module instead of turning __init__.py into soup.
# =============================================================================
def ensure_camera(context):
    for obj in context.scene.objects:
        if obj.type == "CAMERA":
            context.scene.camera = obj
            return obj
    bpy.ops.object.camera_add(location=(0, -7, 4), rotation=(math.radians(60), 0, 0))
    cam = context.object
    cam.name = "OptiBlend Camera"
    context.scene.camera = cam
    return cam


def find_light(name):
    obj = bpy.data.objects.get(name)
    return obj if obj and obj.type == "LIGHT" else None


def ensure_default_lighting(context):
    sun = find_light("OptiBlend Sun")
    if not sun:
        bpy.ops.object.light_add(type="SUN", location=(4, -4, 6))
        sun = context.object
        sun.name = "OptiBlend Sun"
        sun.rotation_euler = (math.radians(28), math.radians(-18), math.radians(32))
        sun.data.energy = 2.0

    point = find_light("OptiBlend Point")
    if not point:
        bpy.ops.object.light_add(type="POINT", location=(2.5, -2.5, 3.5))
        point = context.object
        point.name = "OptiBlend Point"
        point.data.energy = 700
        point.data.shadow_soft_size = 1.0
    return sun, point


# =============================================================================
# camera + compositor helpers
# =============================================================================
# Render setup is kept small on purpose. A beginner mainly needs: a camera, a way
# to look through it, a way to align it to the current view, then F12 / Ctrl+F12.
def active_camera(context):
    cam=context.scene.camera
    if cam and cam.type=="CAMERA":
        return cam
    return ensure_camera(context)


def ensure_compositor_glare(scene, glare_type="FOG_GLOW"):
    scene.use_nodes=True
    tree=scene.node_tree
    if tree is None:
        return None
    nodes=tree.nodes; links=tree.links
    composite=next((n for n in nodes if n.type=="COMPOSITE"),None)
    if composite is None:
        composite=nodes.new("CompositorNodeComposite"); composite.location=(420,0)
    glare=nodes.get("OptiBlend Glow")
    if glare is None or glare.type!="GLARE":
        glare=nodes.new("CompositorNodeGlare")
        glare.name="OptiBlend Glow"; glare.label="OptiBlend Glow / Glare"; glare.location=(150,0)
    props=scene.optiblend_v123
    glare.glare_type=glare_type
    glare.quality="HIGH"
    glare.threshold=props.glare_threshold
    glare.size=int(props.glare_size)
    try: glare.mix=0.0
    except Exception: pass

    # Insert the helper into the existing image path instead of clearing the whole
    # compositor. That makes this much less destructive for Intermediate users.
    source_socket=None
    image_input=composite.inputs.get("Image")
    # If this is an update of an existing OptiBlend node, keep the original source
    # already feeding the glare instead of falling back to Render Layers and silently
    # bypassing someone's earlier compositor chain.
    if glare.inputs.get("Image") and glare.inputs["Image"].links:
        source_socket=glare.inputs["Image"].links[0].from_socket
    if image_input:
        for link in list(image_input.links):
            if link.from_node != glare:
                source_socket=link.from_socket
                try: links.remove(link)
                except Exception: pass
                break
    if source_socket is None:
        render=next((n for n in nodes if n.type=="R_LAYERS"),None)
        if render is None:
            render=nodes.new("CompositorNodeRLayers"); render.location=(-180,0)
        source_socket=render.outputs.get("Image")

    # Repeated presses update one named node rather than creating a stack of glows.
    for socket in (glare.inputs.get("Image"), image_input):
        if socket:
            for link in list(socket.links):
                try: links.remove(link)
                except Exception: pass
    if source_socket and glare.inputs.get("Image"):
        links.new(source_socket,glare.inputs["Image"])
    if glare.outputs.get("Image") and image_input:
        links.new(glare.outputs["Image"],image_input)
    return glare


def disable_compositor_glare(scene):
    if not scene.use_nodes or not scene.node_tree:
        return False
    tree=scene.node_tree; nodes=tree.nodes; links=tree.links
    glare=nodes.get("OptiBlend Glow")
    if glare is None:
        return False
    composite=next((n for n in nodes if n.type=="COMPOSITE"),None)
    source=None
    if glare.inputs.get("Image") and glare.inputs["Image"].links:
        source=glare.inputs["Image"].links[0].from_socket
    if composite and composite.inputs.get("Image"):
        for link in list(composite.inputs["Image"].links):
            try: links.remove(link)
            except Exception: pass
        if source:
            try: links.new(source,composite.inputs["Image"])
            except Exception: pass
    try: nodes.remove(glare)
    except Exception: pass
    return True


# =============================================================================
# procedural material node GROUP generation
# =============================================================================
def input_socket(node, names):
    for name in names:
        if name in node.inputs:
            return node.inputs[name]
    return None


def set_input(node, names, value):
    sock = input_socket(node, names)
    if sock is not None:
        sock.default_value = value
        return True
    return False


def new_group_socket(group, name, in_out, socket_type):
    try:
        return group.interface.new_socket(name=name, in_out=in_out, socket_type=socket_type)
    except Exception:
        try:
            if in_out == "OUTPUT":
                return group.outputs.new(socket_type, name)
            return group.inputs.new(socket_type, name)
        except Exception:
            return None


def build_material_group(key):
    data = MATERIAL_LIBRARY[key]
    group_name = "OptiBlend Group | " + data["name"].replace(" [BETA]", "")
    existing = bpy.data.node_groups.get(group_name)
    if existing:
        return existing

    group = bpy.data.node_groups.new(group_name, "ShaderNodeTree")
    new_group_socket(group, "Shader", "OUTPUT", "NodeSocketShader")
    nodes = group.nodes
    links = group.links
    out = nodes.new("NodeGroupOutput")
    out.location = (520, 0)
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (220, 0)

    style = data["style"]
    c1, c2 = data["c1"], data["c2"]
    rough = data["rough"]
    set_input(bsdf, ["Base Color"], c1)
    set_input(bsdf, ["Roughness"], rough)

    if style == "CUSTOM":
        # Custom stays simple because the wheel values change live in the material,
        # not in a shared group. The group still exists so it follows the same library structure.
        pass

    elif style in {"GLASS", "ICE", "LIQUID"}:
        set_input(bsdf, ["Base Color"], c1)
        set_input(bsdf, ["Transmission Weight", "Transmission"], 1.0)
        set_input(bsdf, ["IOR"], 1.45 if style != "LIQUID" else 1.333)
        set_input(bsdf, ["Roughness"], rough)
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (-420, -120)
        noise.inputs["Scale"].default_value = 3.2 if style == "ICE" else 1.4
        noise.inputs["Detail"].default_value = 5.0
        bump = nodes.new("ShaderNodeBump")
        bump.location = (-40, -150)
        bump.inputs["Strength"].default_value = 0.12 if style == "LIQUID" else 0.18
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        normal = input_socket(bsdf, ["Normal"])
        if normal:
            links.new(bump.outputs["Normal"], normal)

    elif style == "METAL":
        set_input(bsdf, ["Metallic"], 1.0)
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (-360, -90)
        noise.inputs["Scale"].default_value = 18.0
        noise.inputs["Detail"].default_value = 2.0
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.location = (-120, -80)
        ramp.color_ramp.elements[0].color = c1
        ramp.color_ramp.elements[1].color = c2
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], input_socket(bsdf,["Base Color"]))

    elif style == "GLOW":
        set_input(bsdf, ["Base Color"], c1)
        set_input(bsdf, ["Emission Color", "Emission"], c2)
        set_input(bsdf, ["Emission Strength"], 6.0)
        set_input(bsdf, ["Roughness"], rough)

    elif style == "WOOD":
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (-520, 30)
        noise.inputs["Scale"].default_value = 3.4
        noise.inputs["Detail"].default_value = 5.0
        noise.inputs["Roughness"].default_value = 0.68
        wave = nodes.new("ShaderNodeTexWave")
        wave.location = (-520, -190)
        wave.wave_type = "BANDS"
        wave.bands_direction = "X"
        wave.inputs["Scale"].default_value = 4.0
        wave.inputs["Distortion"].default_value = 6.0
        mix = nodes.new("ShaderNodeMixRGB")
        mix.blend_type = "MULTIPLY"
        mix.location = (-250, 0)
        mix.inputs[0].default_value = 0.55
        links.new(noise.outputs["Fac"], mix.inputs[1])
        links.new(wave.outputs["Color"], mix.inputs[2])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.location = (-20, 30)
        ramp.color_ramp.elements[0].color = c1
        ramp.color_ramp.elements[1].color = c2
        links.new(mix.outputs["Color"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], input_socket(bsdf,["Base Color"]))
        bump = nodes.new("ShaderNodeBump")
        bump.location = (0, -170)
        bump.inputs["Strength"].default_value = 0.22
        links.new(mix.outputs["Color"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], input_socket(bsdf,["Normal"]))

    elif style in {"BRICK"}:
        tex = nodes.new("ShaderNodeTexBrick")
        tex.location = (-420, 30)
        tex.inputs["Color1"].default_value = c1
        tex.inputs["Color2"].default_value = c2
        tex.inputs["Mortar"].default_value = (0.05,0.05,0.05,1)
        tex.inputs["Scale"].default_value = 5.0
        links.new(tex.outputs["Color"], input_socket(bsdf,["Base Color"]))
        bump = nodes.new("ShaderNodeBump")
        bump.location = (-20, -120)
        bump.inputs["Strength"].default_value = 0.28
        links.new(tex.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], input_socket(bsdf,["Normal"]))

    elif style == "MARBLE":
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (-480, 20)
        noise.inputs["Scale"].default_value = 2.1
        noise.inputs["Detail"].default_value = 8.0
        noise.inputs["Distortion"].default_value = 5.0
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.location = (-160, 20)
        ramp.color_ramp.elements[0].position = 0.36
        ramp.color_ramp.elements[0].color = c1
        ramp.color_ramp.elements[1].position = 0.58
        ramp.color_ramp.elements[1].color = c2
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], input_socket(bsdf,["Base Color"]))

    else:
        # The generic procedural base handles stone, concrete, fabrics, natural
        # surfaces, paper and other lightweight presets. The style-specific values
        # below still give the groups different behaviour without 30 duplicate functions.
        noise = nodes.new("ShaderNodeTexNoise")
        noise.location = (-470, 20)
        noise.inputs["Scale"].default_value = 7.0 if style in {"FABRIC","WEAVE","PAPER"} else 4.0
        noise.inputs["Detail"].default_value = 6.0
        noise.inputs["Roughness"].default_value = 0.72
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.location = (-170, 20)
        ramp.color_ramp.elements[0].color = c1
        ramp.color_ramp.elements[1].color = c2
        links.new(noise.outputs["Fac"], ramp.inputs["Fac"])
        links.new(ramp.outputs["Color"], input_socket(bsdf,["Base Color"]))

        bump = nodes.new("ShaderNodeBump")
        bump.location = (-10, -150)
        bump.inputs["Strength"].default_value = 0.12 if style in {"PLASTIC","CERAMIC","ORGANIC"} else 0.30
        links.new(noise.outputs["Fac"], bump.inputs["Height"])
        links.new(bump.outputs["Normal"], input_socket(bsdf,["Normal"]))

        if style == "VELVET":
            set_input(bsdf, ["Sheen Weight", "Sheen"], 0.75)
            set_input(bsdf, ["Roughness"], 0.78)
        elif style == "LEATHER":
            set_input(bsdf, ["Coat Weight", "Coat"], 0.18)
        elif style == "PLASTIC":
            set_input(bsdf, ["Coat Weight", "Coat"], 0.22)
            set_input(bsdf, ["Roughness"], rough)
        elif style == "RUBBER":
            set_input(bsdf, ["Roughness"], 0.92)
        elif style == "CERAMIC":
            set_input(bsdf, ["Coat Weight", "Coat"], 0.35)
            set_input(bsdf, ["Roughness"], 0.16)
        elif style == "TECH":
            set_input(bsdf, ["Metallic"], 0.55)
            set_input(bsdf, ["Emission Color", "Emission"], c2)
            set_input(bsdf, ["Emission Strength"], 0.45)

    links.new(bsdf.outputs["BSDF"], out.inputs["Shader"])
    group["optiblend_material_key"] = key
    group["optiblend_version"] = "1.20FINAL"
    return group


def material_from_preset(context, key):
    data = MATERIAL_LIBRARY[key]
    name = "OptiBlend | " + data["name"].replace(" [BETA]", "")
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (260, 0)
    group_node = nodes.new("ShaderNodeGroup")
    group_node.location = (-20, 0)
    group_node.node_tree = build_material_group(key)
    links.new(group_node.outputs["Shader"], output.inputs["Surface"])
    mat.diffuse_color = data["c1"]

    if key == "CUSTOM":
        # Custom is the exception: it keeps the group structure but also uses a
        # local Principled node so the colour wheel can update instantly.
        nodes.clear()
        output = nodes.new("ShaderNodeOutputMaterial")
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        props = context.scene.optiblend_v123
        set_input(bsdf,["Base Color"],tuple(props.custom_color))
        set_input(bsdf,["Metallic"],props.material_metallic)
        set_input(bsdf,["Roughness"],props.material_roughness)
        links.new(bsdf.outputs["BSDF"],output.inputs["Surface"])
        mat.diffuse_color = tuple(props.custom_color)
    return mat


def assign_material(obj, mat):
    if not obj or obj.type != "MESH":
        return False
    if len(obj.data.materials) == 0:
        obj.data.materials.append(mat)
    else:
        obj.data.materials[0] = mat
    obj.active_material = mat
    return True


def update_custom_colour(self, context):
    try:
        mat = material_from_preset(context, "CUSTOM")
        for obj in context.selected_objects:
            assign_material(obj, mat)
    except Exception:
        pass


# =============================================================================
# shape placement + object interaction
# =============================================================================
# This section is doing more than just "put a cube under the mouse" now.
# Placement behaves like a compact modelling workflow with snapping and rotation state:
#
# 1) predictable ground/grid placement for beginners
# 2) raycast placement when another mesh is underneath the cursor
# 3) Ctrl object-centre snapping for exact alignment tests
# 4) automatic surface-normal alignment so objects can sit on walls/slopes
# 5) a separate spin value so the user can rotate *around* that surface normal
# 6) overlap cleanup after normal drops, but NOT after intentional centre-to-centre snap
#
# V1 uses object-centre and surface snapping. Face-centre snapping and collision-state
# colouring are deliberately outside the first public release.
# =============================================================================
def remove_preview():
    obj = bpy.data.objects.get(PREVIEW_NAME)
    if obj:
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception:
            pass


def primitive_height(key, size):
    if key in {"CUBE","SPHERE","ICOSPHERE","CAPSULE"}:
        return size
    if key in {"PLANE","CIRCLE","GRID"}:
        return 0.02
    if key == "TORUS":
        return size * 0.45
    return size * 2.0


def mouse_ray(context, event):
    try:
        from bpy_extras import view3d_utils
        coord = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, coord)
        direction = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, coord)
        return origin, direction.normalized()
    except Exception:
        return None, None


def raycast_object(context, event, hide_obj=None):
    origin, direction = mouse_ray(context, event)
    if origin is None:
        return None, None, None
    old_hidden = None
    if hide_obj is not None:
        try:
            old_hidden = hide_obj.hide_get()
            hide_obj.hide_set(True)
            context.view_layer.update()
        except Exception:
            pass
    result = (None, None, None)
    try:
        depsgraph = context.evaluated_depsgraph_get()
        hit, loc, normal, face_index, obj, matrix = context.scene.ray_cast(depsgraph, origin, direction, distance=10000)
        if hit:
            result = (obj, loc, normal)
    except Exception:
        pass
    if hide_obj is not None and old_hidden is not None:
        try:
            hide_obj.hide_set(old_hidden)
            context.view_layer.update()
        except Exception:
            pass
    return result


def object_world_center(obj):
    # Bounding-box centre is more useful than obj.location here because imported meshes
    # often have an origin somewhere weird. This makes Ctrl-centre snap visually honest.
    try:
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        if corners:
            return sum(corners, Vector((0.0, 0.0, 0.0))) / len(corners)
    except Exception:
        pass
    try:
        return obj.matrix_world.translation.copy()
    except Exception:
        return Vector((0.0, 0.0, 0.0))


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def object_world_up(obj):
    # Surface rotation needs a sensible fallback axis when centre snapping does not have
    # a hit normal. Using the target object's local Z means a rotated object still feels
    # like the preview is rotating "around" that object rather than around world Z.
    try:
        up = obj.matrix_world.to_3x3() @ Vector((0.0, 0.0, 1.0))
        if up.length > 0.0001:
            return up.normalized()
    except Exception:
        pass
    return Vector((0.0, 0.0, 1.0))


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def rotation_axis_vector(axis_name):
    if axis_name == "X":
        return Vector((1.0, 0.0, 0.0))
    if axis_name == "Y":
        return Vector((0.0, 1.0, 0.0))
    return Vector((0.0, 0.0, 1.0))


def apply_preview_rotation(context, obj, normal=None):
    # There are two rotation behaviours on purpose:
    # - on a surface, local Z follows the surface normal and the wheel spins around it
    # - on the ground/cursor, X/Y/Z chooses a normal Blender-style free rotation axis
    props = context.scene.optiblend_v123
    angle = math.radians(DRAG_STATE.get("rotation_angle", 0.0))

    try:
        if normal is not None and props.align_preview_to_surface and not DRAG_STATE.get("axis_override", False):
            axis = normal.normalized()
            align = axis.to_track_quat("Z", "Y")
            spin = Quaternion(axis, angle)
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = spin @ align
        else:
            axis = rotation_axis_vector(DRAG_STATE.get("rotation_axis", "Z"))
            obj.rotation_mode = "QUATERNION"
            obj.rotation_quaternion = Quaternion(axis, angle)
    except Exception as e:
        # Rotation should never make dragging unusable. If a weird imported object or
        # zero-length normal slips through, placement still works without alignment.
        print("OptiBlend preview rotation skipped:", e)


def ground_location(context, event, half_height):
    origin, direction = mouse_ray(context, event)
    if origin is None or abs(direction.z) < 0.0001:
        return Vector((0,0,half_height))
    t = (half_height-origin.z)/direction.z
    loc = origin + direction*t
    return Vector((loc.x,loc.y,half_height))


def snap_value(value, grid):
    return round(value/grid)*grid if grid > 0 else value


def preview_transform(context, event, key, preview_obj=None, force_center=False):
    """Return location, target object, rotation normal, and whether centre snap is active."""
    props = context.scene.optiblend_v123
    half = primitive_height(key, props.preview_size) / 2.0

    # One raycast is reused for smart placement, centre snapping and rotation alignment.
    # This is a small performance improvement over the R3 version which could raycast
    # twice in the same mouse move depending on the snap mode.
    hit_obj = loc = normal = None
    if props.smart_object_interaction or props.preview_snap_mode == "SURFACE" or force_center:
        hit_obj, loc, normal = raycast_object(context, event, preview_obj)

    # Ctrl = intentional centre-to-centre placement. This is useful for concentric
    # objects, modifier tests, wheels, cylinders, helper meshes, etc. It is deliberately
    # not run through the overlap resolver later because overlap is the point here.
    if force_center and props.center_snap_enabled and hit_obj is not None and hit_obj.type == "MESH":
        centre = object_world_center(hit_obj)
        return centre, hit_obj, object_world_up(hit_obj), True

    # Smart interaction still works in Beginner GRID mode. If the mouse is on a useful
    # upward-facing surface, the object can sit on it rather than burying itself in it.
    if props.smart_object_interaction and hit_obj is not None and hit_obj.type == "MESH" and normal is not None:
        allow_surface = props.preview_snap_mode == "SURFACE" or normal.z > 0.45
        if allow_surface:
            result = loc + normal.normalized() * (half + 0.002)
            if props.preview_snap_mode == "GRID":
                result.x = snap_value(result.x, props.preview_grid_size)
                result.y = snap_value(result.y, props.preview_grid_size)
            return result, hit_obj, normal.normalized(), False

    if props.preview_snap_mode == "SURFACE" and hit_obj is not None and hit_obj.type == "MESH" and normal is not None:
        return loc + normal.normalized() * (half + 0.002), hit_obj, normal.normalized(), False

    if props.preview_snap_mode == "CURSOR":
        cursor_loc = context.scene.cursor.location.copy()
        cursor_loc.z += half
        return cursor_loc, None, None, False

    # Default beginner behaviour: ground level + grid. Keeping this boring is useful;
    # beginners should be able to predict where an object will land every single time.
    result = ground_location(context, event, half)
    result.x = snap_value(result.x, props.preview_grid_size)
    result.y = snap_value(result.y, props.preview_grid_size)
    result.z = half
    return result, None, None, False


def update_preview_transform(context, event, key, preview_obj=None):
    # This wrapper updates both placement and rotation and stores enough information for
    # wheel rotation to work even if the mouse has not moved since the last raycast.
    force_center = bool(getattr(event, "ctrl", False))
    loc, target, normal, centered = preview_transform(context, event, key, preview_obj, force_center)
    DRAG_STATE["last_target"] = target
    DRAG_STATE["last_normal"] = normal
    DRAG_STATE["center_active"] = centered

    if preview_obj is not None:
        preview_obj.location = loc
        apply_preview_rotation(context, preview_obj, normal)
    return loc


def create_preview_primitive(context, key):
    s = context.scene.optiblend_v123.preview_size
    if key == "SPHERE":
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=s/2)
    elif key == "ICOSPHERE":
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=s/2)
    elif key == "CIRCLE":
        bpy.ops.mesh.primitive_circle_add(vertices=48, radius=s/2, fill_type="NGON")
    elif key == "CYLINDER":
        bpy.ops.mesh.primitive_cylinder_add(vertices=40, radius=s/2, depth=s*2)
    elif key == "CONE":
        bpy.ops.mesh.primitive_cone_add(vertices=40, radius1=s/2, depth=s*2)
    elif key == "PLANE":
        bpy.ops.mesh.primitive_plane_add(size=s)
    elif key == "TORUS":
        bpy.ops.mesh.primitive_torus_add(major_radius=s*0.38, minor_radius=s*0.12, major_segments=40, minor_segments=14)
    elif key == "MONKEY":
        bpy.ops.mesh.primitive_monkey_add(size=s)
    elif key == "GRID":
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=12, y_subdivisions=12, size=s)
    elif key == "PYRAMID":
        bpy.ops.mesh.primitive_cone_add(vertices=4, radius1=s*0.7, depth=s*1.6)
    elif key == "CAPSULE":
        # Capsule is made as a UV sphere stretched slightly. Later I could replace
        # this with a dedicated capsule mesh if cleaner topology becomes necessary.
        bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=s/2)
        context.object.scale.z = 1.45
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    else:
        bpy.ops.mesh.primitive_cube_add(size=s)

    obj = context.object
    obj.name = PREVIEW_NAME
    obj.display_type = "WIRE"
    obj.show_in_front = True
    obj.color = (0.0,1.0,0.30,0.95)
    try:
        obj.data.materials.clear()
    except Exception:
        pass
    return obj


def world_bounds(obj):
    try:
        pts = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        return (
            min(p.x for p in pts), max(p.x for p in pts),
            min(p.y for p in pts), max(p.y for p in pts),
            min(p.z for p in pts), max(p.z for p in pts),
        )
    except Exception:
        return None


def aabb_overlap(a,b):
    if not a or not b:
        return False
    return a[0] < b[1] and a[1] > b[0] and a[2] < b[3] and a[3] > b[2] and a[4] < b[5] and a[5] > b[4]


def resolve_object_overlap(context, obj):
    # This is intentionally a simple vertical collision helper, not a physics sim.
    # For a beginner it prevents the most obvious case where a newly dropped object
    # is half buried inside another mesh.
    props = context.scene.optiblend_v123
    if not props.smart_object_interaction or obj.type != "MESH":
        return False

    moved = False
    for _ in range(6):
        own = world_bounds(obj)
        best_shift = 0.0
        for other in context.scene.objects:
            if other == obj or other.type != "MESH" or other.hide_viewport:
                continue
            ob = world_bounds(other)
            if aabb_overlap(own, ob):
                shift = (ob[5] - own[4]) + 0.003
                if shift > best_shift:
                    best_shift = shift
        if best_shift <= 0.0001:
            break
        obj.location.z += best_shift
        context.view_layer.update()
        moved = True
    return moved


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def finish_preview(context, obj, key, preserve_center=False):
    obj.name = "OptiBlend " + SHAPES[key][0]
    obj.display_type = "TEXTURED"
    obj.show_in_front = False
    obj.color = (1,1,1,1)

    # A normal drag gets the simple overlap safety pass. Ctrl-centre snapping skips it
    # because moving the object afterwards would defeat the exact centre alignment the
    # user intentionally asked for.
    if not preserve_center:
        resolve_object_overlap(context,obj)

    if context.scene.optiblend_v123.live_auto_collection:
        sort_object_into_optiblend_collection(context,obj)


# =============================================================================
# collection organisation + teaching / guide tracking
# =============================================================================
def ensure_collection(name):
    col = bpy.data.collections.get(name)
    if col:
        return col
    col = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(col)
    return col


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def target_collection_for_object(obj):
    if obj.type == "MESH":
        return "OptiBlend | Geometry"
    if obj.type == "LIGHT":
        return "OptiBlend | Lights"
    if obj.type == "CAMERA":
        return "OptiBlend | Cameras"
    return "OptiBlend | Helpers"


def sort_object_into_optiblend_collection(context,obj):
    target = ensure_collection(target_collection_for_object(obj))
    if obj.name not in target.objects:
        target.objects.link(obj)

    # Remove duplicate links from old collections. This is the bit the last
    # version missed, which is why Collection and OptiBlend groups both showed up.
    for col in list(obj.users_collection):
        if col != target:
            try:
                col.objects.unlink(obj)
            except Exception:
                pass
    return target


def cleanup_empty_collections():
    protected = {
        "OptiBlend | Geometry","OptiBlend | Lights","OptiBlend | Cameras","OptiBlend | Helpers"
    }
    removed = []
    for col in list(bpy.data.collections):
        if col.name in protected:
            continue
        # I only remove Blender's default Collection and old OptiBlend collections.
        # Empty custom collections from the user should not disappear just because
        # they ran this organiser once.
        if col.name != "Collection" and not col.name.startswith("OptiBlend |"):
            continue
        if len(col.objects) == 0 and len(col.children) == 0:
            try:
                removed.append(col.name)
                bpy.data.collections.remove(col)
            except Exception:
                pass
    return removed


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
def bump_guide(context, field):
    props = context.scene.optiblend_v123
    try:
        setattr(props, field, getattr(props, field) + 1)
    except Exception:
        pass


# =============================================================================
# properties
# =============================================================================
class OPTIBLEND_V123_Props(bpy.types.PropertyGroup):
    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("BEGINNER","Beginner","Layout only. Simplified interface, guided snapping and core Blender shortcuts."),
            ("INTERMEDIATE","Intermediate","Opens Blender up more for confident users while still keeping the layout tidier."),
            ("ADVANCED","Advanced","Unlocks the full workflow, advanced retopology and pipeline helper tools."),
        ],
        default="BEGINNER",
    )

    asset_bar_visible: bpy.props.BoolProperty(name="Asset Bar", default=True)
    asset_bar_mode: bpy.props.EnumProperty(name="Asset Bar", items=[("SHAPES","Shapes","Geometry browser"),("MATERIALS","Materials","Material browser")], default="SHAPES", update=redraw_update)
    hover_asset: bpy.props.StringProperty(default="")
    show_hover_tips: bpy.props.BoolProperty(name="Hover Help", default=True)
    animate_assets: bpy.props.BoolProperty(name="Animate Assets", default=True)
    ui_glow_enabled: bpy.props.BoolProperty(name="Animated UI Glow", default=True)
    asset_scroll_current: bpy.props.FloatProperty(default=0.0)
    asset_scroll_target: bpy.props.FloatProperty(default=0.0)
    shape_search: bpy.props.StringProperty(name="Search Shapes", default="", update=redraw_update)
    material_search: bpy.props.StringProperty(name="Search Materials", default="", update=redraw_update)
    material_category: bpy.props.EnumProperty(
        name="Category",
        items=[(k,v,"Filter to " + v) for k,v in CATEGORY_LABELS.items()],
        default="ALL",
        update=redraw_update,
    )

    preview_snap_mode: bpy.props.EnumProperty(name="Snap", items=[("GRID","Grid","Ground / grid placement"),("SURFACE","Surface","Surface raycast placement"),("CURSOR","3D Cursor","3D cursor placement")], default="GRID")
    preview_grid_size: bpy.props.FloatProperty(name="Grid Size", default=1.0, min=0.1, max=10.0)
    preview_size: bpy.props.FloatProperty(name="Shape Size", default=2.0, min=0.1, max=10.0)
    smart_object_interaction: bpy.props.BoolProperty(name="Smart Object Interaction", default=True)
    center_snap_enabled: bpy.props.BoolProperty(
        name="Ctrl Centre Snap",
        description="Hold Ctrl while dragging a shape to snap its centre to the centre of the mesh under the mouse.",
        default=True,
    )
    align_preview_to_surface: bpy.props.BoolProperty(
        name="Align To Surface",
        description="When a preview is on another object, align its local Z axis to that surface before applying wheel rotation.",
        default=True,
    )
    rotation_step_degrees: bpy.props.FloatProperty(
        name="Rotation Step",
        description="Mouse-wheel rotation step while dragging. Hold Shift for quarter steps.",
        default=15.0,
        min=1.0,
        max=90.0,
    )

    custom_color: bpy.props.FloatVectorProperty(name="Colour", subtype="COLOR", size=4, min=0.0, max=1.0, default=(0.05,0.65,1.0,1.0), update=update_custom_colour)
    material_metallic: bpy.props.FloatProperty(name="Metallic", default=0.0, min=0.0, max=1.0, update=update_custom_colour)
    material_roughness: bpy.props.FloatProperty(name="Roughness", default=0.38, min=0.0, max=1.0, update=update_custom_colour)

    # HCI controls. I grouped these together because they are all about readability
    # and reducing memory load rather than adding another modelling feature.
    ui_scale: bpy.props.FloatProperty(name="OptiBlend Menu Scale", description="Scale only the OptiBlend asset bar and helper menu.", default=1.0, min=0.70, max=1.50, update=redraw_update)
    show_q_hint: bpy.props.BoolProperty(name="Show Press Q Hint", default=True)
    object_xyz_helper: bpy.props.BoolProperty(name="Centred XYZ Helper", description="Show XYZ around the visible centre of the selected mesh instead of a misplaced origin.", default=True, update=redraw_update)
    edit_mode_smart_snap: bpy.props.BoolProperty(name="Edit Mode Smart Snap", description="Use vertex, edge, face and midpoint snapping while editing a mesh.", default=True)

    glare_mode: bpy.props.EnumProperty(name="Glow Type", items=[("FOG_GLOW","Glow","Soft fog glow"),("STREAKS","Streaks","Star-like streaks"),("GHOSTS","Ghosts","Lens ghost glare"),("SIMPLE_STAR","Simple Star","Simple star glare")], default="FOG_GLOW")
    glare_threshold: bpy.props.FloatProperty(name="Glow Threshold", default=1.0, min=0.0, max=20.0)
    glare_size: bpy.props.IntProperty(name="Glow Size", default=6, min=6, max=9)
    retopo_target_faces: bpy.props.IntProperty(name="Quad Target Faces", description="Approximate face count for Advanced QuadriFlow retopology.", default=4000, min=100, max=200000)

    workspace_lock_enabled: bpy.props.BoolProperty(name="Lock Workspace Set", default=True)
    simplify_beginner_ui: bpy.props.BoolProperty(name="Simplify Beginner UI", default=True)
    auto_beginner_lights: bpy.props.BoolProperty(name="Beginner Sun + Point", default=True)
    live_auto_collection: bpy.props.BoolProperty(name="Live Auto Collection", default=False)
    developer_test_menu: bpy.props.BoolProperty(name="Show Test Lab", default=False)

    high_poly_limit: bpy.props.IntProperty(name="High Poly Limit", default=5000, min=100, max=1000000)

    # Import / advanced character checks. These are deliberately opt-in so a beginner
    # never has to understand pipeline settings just to drag a cube into the scene.
    import_auto_organize: bpy.props.BoolProperty(
        name="Auto Organise Imports",
        description="Move newly imported objects into OptiBlend collections after import.",
        default=True,
    )
    import_run_scan: bpy.props.BoolProperty(
        name="Scan After Import",
        description="Run a small object/poly count check after importing an external model.",
        default=True,
    )
    mixamo_last_score: bpy.props.IntProperty(name="Mixamo Readiness", default=0, min=0, max=100)
    mixamo_last_report: bpy.props.StringProperty(default="Run Mixamo Readiness Check to begin.")
    topology_last_report: bpy.props.StringProperty(default="Run Topology Audit to begin.")
    rig_last_report: bpy.props.StringProperty(default="Run Rig / Modifier Audit to begin.")

    report: bpy.props.StringProperty(default="OptiBlend V1.0 loaded.")

    guide_shapes: bpy.props.IntProperty(default=0)
    guide_materials: bpy.props.IntProperty(default=0)
    guide_collections: bpy.props.IntProperty(default=0)
    guide_lights: bpy.props.IntProperty(default=0)

    # Live guide state. I keep this on the scene so it survives small UI redraws without
    # needing yet another modal operator just to remember which guide card is active.
    live_guide_visible: bpy.props.BoolProperty(name="Live Guide", default=False, update=redraw_update)
    live_guide_key: bpy.props.StringProperty(default="")
    live_guide_title: bpy.props.StringProperty(default="")
    live_guide_footer: bpy.props.StringProperty(default="")


# =============================================================================
# asset bar modal listener - drag + scrolling + animation timer
# Shape placement is one of the busiest parts of the add-on, so the state changes are
# heavily because mouse events + timers + workspace switches are where small bugs hide.
# Later I may split shape dragging and material dragging into separate state handlers.
# =============================================================================
def reset_drag():
    # Reset everything that belongs to one drag. Leaving the rotation angle behind was
    # surprisingly confusing in early testing because the next cube could start rotated.
    DRAG_STATE.update({
        "kind": None,
        "key": None,
        "start": (0, 0),
        "mouse": (0, 0),
        "preview": None,
        "moved": False,
        "rotation_angle": 0.0,
        "rotation_axis": "Z",
        "axis_override": False,
        "last_normal": None,
        "last_target": None,
        "center_active": False,
    })


def preferred_drag_axis(shape_key):
    # This is a tiny HCI change but it matters a lot in use. A cylinder rotating around
    # Z just spins like a turntable and never tips onto its side, which made the wheel
    # control feel broken even though the maths was technically working. Tall / round
    # primitives therefore start on Y so the first wheel movement visibly tips them.
    #
    # Primitive rotation uses sensible default axes; per-shape saved axes are not part of V1.
    # Beginner mode avoids another setting here.
    if shape_key in {"CYLINDER", "CONE", "CAPSULE", "TORUS"}:
        return "Y"
    return "Z"


def ensure_asset_bar_listener(context):
    global ASSET_BAR_RUNNING
    if ASSET_BAR_RUNNING:
        return
    try:
        if context.area and context.area.type == "VIEW_3D":
            bpy.ops.optiblend_v123.asset_bar_listener("INVOKE_DEFAULT")
            return
    except Exception:
        pass
    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type != "VIEW_3D":
                    continue
                region = next((r for r in area.regions if r.type == "WINDOW"),None)
                if region:
                    with bpy.context.temp_override(window=window,screen=window.screen,area=area,region=region):
                        bpy.ops.optiblend_v123.asset_bar_listener("INVOKE_DEFAULT")
                    return
    except Exception as e:
        print("OptiBlend asset bar listener could not start:",e)


class OPTIBLEND_V123_OT_asset_bar_listener(bpy.types.Operator):
    bl_idname = "optiblend_v123.asset_bar_listener"
    bl_label = "OptiBlend Asset Bar Listener"
    bl_options = {"INTERNAL"}

    def invoke(self,context,event):
        global ASSET_BAR_RUNNING
        if not context.area or context.area.type != "VIEW_3D":
            return {"CANCELLED"}
        ASSET_BAR_RUNNING = True
        self._generation = ASSET_LISTENER_GENERATION
        self._timer = context.window_manager.event_timer_add(1/30,window=context.window)
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def finish_listener(self,context):
        global ASSET_BAR_RUNNING
        # Do not mark a newer listener as stopped just because an old workspace's
        # listener finally received its cancellation event.
        if getattr(self, "_generation", -1) == ASSET_LISTENER_GENERATION:
            ASSET_BAR_RUNNING = False
        try:
            context.window_manager.event_timer_remove(self._timer)
        except Exception:
            pass

    def modal(self,context,event):
        # Workspace switching was the source of the R3 traceback. If this operator
        # belongs to an older screen generation, or Blender gives it no active area,
        # stop cleanly and let the restart timer attach a fresh listener later.
        if getattr(self, "_generation", -1) != ASSET_LISTENER_GENERATION:
            self.finish_listener(context)
            return {"CANCELLED"}
        if getattr(context, "area", None) is None or getattr(context, "region", None) is None:
            self.finish_listener(context)
            queue_asset_bar_listener_restart()
            return {"CANCELLED"}
        if context.area.type != "VIEW_3D":
            self.finish_listener(context)
            queue_asset_bar_listener_restart()
            return {"CANCELLED"}
        if not hasattr(context.scene,"optiblend_v123"):
            self.finish_listener(context)
            return {"CANCELLED"}

        props = context.scene.optiblend_v123
        mx,my = event.mouse_region_x,event.mouse_region_y
        DRAG_STATE["mouse"]=(mx,my)

        if event.type == "TIMER":
            diff = props.asset_scroll_target-props.asset_scroll_current
            if abs(diff) > 0.005:
                props.asset_scroll_current += diff*0.22
            else:
                props.asset_scroll_current = props.asset_scroll_target
            if props.asset_bar_visible and props.animate_assets:
                safe_area_redraw(context)
            return {"PASS_THROUGH"}

        if props.asset_bar_visible and point_in_asset_bar(context,mx,my) and event.type in {"WHEELUPMOUSE","WHEELDOWNMOUSE"}:
            direction = -2.0 if event.type == "WHEELUPMOUSE" else 2.0
            props.asset_scroll_target += direction
            clamp_scroll(context)
            safe_area_redraw(context)
            return {"RUNNING_MODAL"}

        if props.asset_bar_visible and DRAG_STATE["kind"] is None:
            hovered = asset_under_mouse(context,mx,my) or ""
            if props.hover_asset != hovered:
                props.hover_asset = hovered
                safe_area_redraw(context)

        if event.type == "LEFTMOUSE" and event.value == "PRESS" and props.asset_bar_visible:
            close = ASSET_BAR_RECTS.get(safe_area_pointer(context),{}).get("close")
            if close:
                x,y,w,h=close
                if x<=mx<=x+w and y<=my<=y+h:
                    props.asset_bar_visible=False
                    props.hover_asset=""
                    safe_area_redraw(context)
                    return {"RUNNING_MODAL"}

            key=asset_under_mouse(context,mx,my)
            if key:
                DRAG_STATE["kind"]="SHAPE" if props.asset_bar_mode=="SHAPES" else "MATERIAL"
                DRAG_STATE["key"]=key
                DRAG_STATE["start"]=(mx,my)
                DRAG_STATE["moved"]=False
                DRAG_STATE["rotation_angle"]=0.0
                DRAG_STATE["rotation_axis"]=preferred_drag_axis(key) if DRAG_STATE["kind"]=="SHAPE" else "Z"
                DRAG_STATE["axis_override"]=False
                return {"RUNNING_MODAL"}
            if point_in_asset_bar(context,mx,my):
                return {"RUNNING_MODAL"}

        # While a shape is being dragged, the wheel becomes a rotation control instead
        # of scrolling the asset browser. This feels closer to manipulating the object
        # directly and means I do not need another permanent rotation panel for Beginner.
        if DRAG_STATE["kind"] == "SHAPE" and DRAG_STATE["preview"] is not None and event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE"}:
            step = props.rotation_step_degrees * (0.25 if getattr(event, "shift", False) else 1.0)
            DRAG_STATE["rotation_angle"] += step if event.type == "WHEELUPMOUSE" else -step
            apply_preview_rotation(context, DRAG_STATE["preview"], DRAG_STATE.get("last_normal"))
            safe_area_redraw(context)
            return {"RUNNING_MODAL"}

        # R is a quick reset. X/Y/Z only matter when the preview is not currently
        # aligned to a surface normal; on a surface the wheel rotates around that surface.
        if DRAG_STATE["kind"] == "SHAPE" and DRAG_STATE["preview"] is not None and event.value == "PRESS":
            if event.type == "R":
                # Keep this close to Blender's normal mental model: R means rotate. During
                # drag placement it gives a clear 90 degree turn, which is especially handy
                # for cylinders/capsules that need to lie on their side. Alt+R follows
                # Blender's familiar "clear rotation" idea and resets the preview.
                if getattr(event, "alt", False):
                    DRAG_STATE["rotation_angle"] = 0.0
                else:
                    DRAG_STATE["rotation_angle"] += 90.0
                apply_preview_rotation(context, DRAG_STATE["preview"], DRAG_STATE.get("last_normal"))
                safe_area_redraw(context)
                return {"RUNNING_MODAL"}
            if event.type in {"X", "Y", "Z"}:
                # Explicit axis choice wins over surface alignment. This means a user can
                # still tip a cylinder sideways while it is hovering over another mesh,
                # instead of the surface normal silently taking control back every frame.
                DRAG_STATE["rotation_axis"] = event.type
                DRAG_STATE["axis_override"] = True
                apply_preview_rotation(context, DRAG_STATE["preview"], DRAG_STATE.get("last_normal"))
                safe_area_redraw(context)
                return {"RUNNING_MODAL"}

        if event.type == "MOUSEMOVE" and DRAG_STATE["kind"]:
            sx,sy=DRAG_STATE["start"]
            DRAG_STATE["moved"] = DRAG_STATE["moved"] or math.hypot(mx-sx,my-sy)>8

            if DRAG_STATE["kind"]=="SHAPE" and DRAG_STATE["moved"]:
                if DRAG_STATE["preview"] is None and not point_in_asset_bar(context,mx,my):
                    DRAG_STATE["preview"]=create_preview_primitive(context,DRAG_STATE["key"])
                obj=DRAG_STATE["preview"]
                if obj is not None:
                    update_preview_transform(context,event,DRAG_STATE["key"],obj)
            safe_area_redraw(context)
            return {"RUNNING_MODAL"}

        if event.type=="LEFTMOUSE" and event.value=="RELEASE" and DRAG_STATE["kind"]:
            kind,key,moved=DRAG_STATE["kind"],DRAG_STATE["key"],DRAG_STATE["moved"]

            if kind=="SHAPE":
                obj=DRAG_STATE["preview"]
                if obj is not None and moved and not point_in_asset_bar(context,mx,my):
                    finish_preview(context,obj,key,preserve_center=DRAG_STATE.get("center_active",False))
                    bpy.ops.object.select_all(action="DESELECT")
                    obj.select_set(True)
                    context.view_layer.objects.active=obj
                    set_move_tool(context)
                    bump_guide(context,"guide_shapes")
                    set_report(
                        context,
                        SHAPES[key][0] + " placed. " +
                        ("Centre snap kept exact alignment." if DRAG_STATE.get("center_active", False) else "Smart interaction checked overlap / surface contact.")
                    )
                else:
                    remove_preview()

            else:
                if key=="CUSTOM" and not moved:
                    reset_drag()
                    bpy.ops.optiblend_v123.colour_wheel("INVOKE_DEFAULT")
                    safe_area_redraw(context)
                    return {"RUNNING_MODAL"}

                if moved and not point_in_asset_bar(context,mx,my):
                    obj,loc,normal=raycast_object(context,event)
                    if obj and obj.type=="MESH":
                        assign_material(obj,material_from_preset(context,key))
                        bump_guide(context,"guide_materials")
                        set_report(context,MATERIAL_LIBRARY[key]["name"]+" dropped onto "+obj.name)
                    else:
                        set_report(context,"Material drop missed a mesh object.")
                elif not moved:
                    mat=material_from_preset(context,key)
                    count=0
                    for obj in context.selected_objects:
                        if assign_material(obj,mat):
                            count+=1
                    if count:
                        bump_guide(context,"guide_materials")
                    set_report(context,MATERIAL_LIBRARY[key]["name"]+f" applied to {count} selected object(s).")

            reset_drag()
            safe_area_redraw(context)
            return {"RUNNING_MODAL"}

        if event.type in {"ESC","RIGHTMOUSE"} and DRAG_STATE["kind"]:
            remove_preview(); reset_drag(); safe_area_redraw(context); return {"RUNNING_MODAL"}

        return {"PASS_THROUGH"}


# =============================================================================
# fancy Q wheel - spread out, glowing, node-like connectors, draggable centre
# The wheel currently opens near the cursor rather than storing a position per workspace.
# the mouse every time. I also want to try subtle connector motion, but only if it stays
# readable and does not start looking like decoration for the sake of decoration.
# =============================================================================
class OPTIBLEND_V123_OT_fancy_wheel(bpy.types.Operator):
    bl_idname = "optiblend_v123.fancy_wheel"
    bl_label = "OptiBlend Helper"
    bl_description = "Press Q to open the OptiBlend Helper. Hover a section to reveal its OptiBlend mini-tools. Press Q again to close it."
    bl_options = {"INTERNAL"}

    # Main cards stay deliberately broad. The smaller hover cards below are the
    # progressive-disclosure layer: a beginner sees a few understandable choices first,
    # then only sees the detailed tools when they actually hover the relevant section.
    # This is much less overwhelming than putting every Blender action on screen at once.
    all_items = (
        ("SHAPES","Shapes","Drag geometry",-315,150),
        ("COLOUR","Materials","Colour + surfaces",150,150),
        ("MODE","Mode","Change complexity",-355,25),
        ("MODIFIERS","Modifiers","Non-destructive edits",190,25),
        ("LIGHTS","Lights","Sun + Point",-315,-105),
        ("RENDER","Render","Camera + output",150,-105),
        ("TOOLS","Scene Tools","Sort + optimise",-250,-230),
        ("GUIDE","Guide","Basic Blender keys",85,-230),
    )

    # These are not Blender's default popup menus. They are drawn by OptiBlend itself
    # and appear only while their parent card is active. Labels stay short because
    # the point is recognition at a glance, not another paragraph of instructions.
    child_items = {
        "SHAPES": (
            ("OPEN_SHAPES","Shape Shelf","Drag any shape"),
            ("IMPORT_EXTERNAL","Import Model","FBX / OBJ / GLTF"),
            ("CUBE_FILTER","Cube","Simple block"),
            ("CYLINDER_FILTER","Cylinder","Wheel / R tips side"),
            ("MORE_SHAPES","More...","Scroll full library"),
        ),
        "COLOUR": (
            ("OPEN_MATERIALS","Material Shelf","Search + drag"),
            ("COLOUR_WHEEL","Colour Wheel","Custom material"),
            ("METAL_PRESET","Metal","Node preset"),
            ("GLOW_PRESET","Glow","Emission preset"),
        ),
        "MODE": (
            ("MODE_BEGINNER","Beginner","Layout + guide"),
            ("MODE_INTERMEDIATE","Intermediate","Model + shade"),
            ("MODE_ADVANCED","Advanced","Full workflow"),
        ),
        "MODIFIERS": (
            ("MOD_SUBSURF","Subdivision","Smooth detail"),
            ("MOD_BEVEL","Bevel","Soft edges"),
            ("MOD_MIRROR","Mirror","Symmetry"),
            ("MOD_SOLIDIFY","Solidify","Add thickness"),
            ("MOD_ARRAY","Array","Repeat object"),
        ),
        "LIGHTS": (
            ("LIGHT_SETUP","Sun + Point","Simple setup"),
            ("LIGHT_SELECT_SUN","Select Sun","Overall light"),
            ("LIGHT_SELECT_POINT","Select Point","Local light"),
        ),
        "RENDER": (
            ("CAMERA_SETUP","Camera","Create / select"),
            ("CAMERA_VIEW","Numpad 0","Camera view"),
            ("CAMERA_ALIGN","Ctrl+Alt+0","Align to view"),
            ("IMAGE_RENDER","F12","Photo render"),
            ("VIDEO_RENDER","Ctrl+F12","Animation render"),
            ("GLOW_COMPOSITOR","FX","Glow / glare"),
        ),
        "TOOLS": (
            ("AUTO_COLLECTIONS","Auto Collections","Sort scene"),
            ("SCAN_SCENE","Scan Scene","Check complexity"),
            ("CLEAN_DATA","Clean Data","Remove unused"),
            ("RETOPO_QUADS","Quad Retopo","Advanced"),
            ("MIXAMO_CHECK","Mixamo Check","Rig readiness"),
            ("TOPOLOGY_AUDIT","Topology","Quads / tris / ngons"),
            ("PIPELINE_EXPORT","FBX Prep","Pipeline fixes"),
            ("TEAM_COLLECTIONS","Team Blocks","Shared assets"),
        ),
        "GUIDE": (
            ("INFO_Q","Q","Open / close Helper"),
            ("INFO_G","G","Move selected object"),
            ("INFO_R","R","Rotate selected object"),
            ("INFO_S","S","Scale selected object"),
            ("INFO_TAB","Tab","Object / Edit mode"),
            ("INFO_AXIS","X Y Z","Constrain an axis"),
        ),
    }

    hover_help = {
        "SHAPES":"Drag visual primitives into the viewport. Grid placement stays predictable in Beginner mode.",
        "COLOUR":"Browse procedural materials or open Blender's real colour wheel from the mini-tools.",
        "MODE":"Beginner hides complexity. Intermediate brings modelling back. Advanced restores the full workflow.",
        "MODIFIERS":"Common non-destructive modelling tools. These are hidden from the Beginner helper on purpose.",
        "LIGHTS":"Use a Sun for overall direction and a Point light for a local highlight.",
        "RENDER":"Create or align a camera, render an image, or add compositor glow without hunting through Blender tabs.",
        "TOOLS":"Organisation and optimisation tools. Kept out of Beginner mode so the first experience stays simple.",
        "GUIDE":"Core Blender shortcuts first: Q Helper, G move, R rotate, S scale, Tab edit, X/Y/Z axis.",
    }

    child_help = {
        "COLOUR_WHEEL":"Opens Blender's native colour wheel and keeps the same colour available in the Materials shelf.",
        "CYLINDER_FILTER":"Cylinder drag starts on the Y rotation axis, so the mouse wheel or R can actually tip it onto its side.",
        "GLOW_COMPOSITOR":"Adds or updates OptiBlend's Glare node in the compositor using the current glow settings.",
        "MOD_SUBSURF":"Adds Subdivision Surface. Use this after clean topology when you want a smoother model.",
        "MOD_BEVEL":"Adds Bevel to soften sharp edges without permanently changing the base mesh.",
        "INFO_G":"G is Blender's normal Move command. Press X, Y or Z afterwards to lock the movement to one axis.",
        "INFO_R":"R is Blender's normal Rotate command. While dragging an OptiBlend shape, R gives a quick 90 degree turn.",
        "INFO_S":"S scales the selected object. X/Y/Z after S limits the scaling to one axis.",
        "INFO_TAB":"Tab switches between Object Mode and Edit Mode. OptiBlend also changes Edit Mode snapping automatically.",
        "IMPORT_EXTERNAL":"Open a file browser and bring FBX, OBJ, GLTF/GLB or STL models directly into OptiBlend.",
        "MIXAMO_CHECK":"Advanced heuristic based on Adobe guidance. It checks what Python can measure and clearly labels anatomy/pose as manual checks.",
        "TOPOLOGY_AUDIT":"Counts quads, triangles, ngons, non-manifold edges, loose geometry and connected mesh islands.",
    }

    def visible_items(self, context):
        # Beginner only gets the things needed to make, colour, light, render and learn.
        # Modifiers and scene optimisation still exist, but they appear after the user
        # deliberately moves to Intermediate. This is the main simplification pass.
        mode = context.scene.optiblend_v123.mode
        allowed = {"SHAPES","COLOUR","MODE","LIGHTS","RENDER","GUIDE"}
        if mode == "INTERMEDIATE":
            allowed |= {"MODIFIERS","TOOLS"}
        elif mode == "ADVANCED":
            allowed = {item[0] for item in self.all_items}
        return tuple(item for item in self.all_items if item[0] in allowed)

    def invoke(self,context,event):
        global FANCY_WHEEL_RUNNING
        if not DRAW_OK:
            return {"CANCELLED"}
        clear_live_guide(context)
        FANCY_WHEEL_RUNNING=True
        self.scale=context.scene.optiblend_v123.ui_scale
        margin=min(340*self.scale, max(120, context.region.width*0.30))
        self.cx=min(max(event.mouse_region_x,margin),max(margin,context.region.width-margin))
        self.cy=min(max(event.mouse_region_y,235*self.scale),max(235*self.scale,context.region.height-235*self.scale))
        self.hover=None
        self.active_parent=None
        self.hover_child=None
        self.drag_center=False
        self.drag_offset=(0,0)
        self.handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_wheel,(),"WINDOW","POST_PIXEL")
        context.window_manager.modal_handler_add(self)
        safe_area_redraw(context)
        return {"RUNNING_MODAL"}

    def card_rect(self,dx,dy,index=0):
        scale=self.scale
        float_y=math.sin(time.time()*2.0+index*0.8)*2.0*scale
        return self.cx+dx*scale,self.cy+dy*scale+float_y,170*scale,68*scale

    def parent_rect(self,key):
        for i,(k,title,sub,dx,dy) in enumerate(self.visible_items(bpy.context)):
            if k==key:
                return self.card_rect(dx,dy,i)
        return None

    def child_rects(self,parent_key):
        parent=self.parent_rect(parent_key)
        if not parent:
            return []
        px,py,pw,ph=parent
        children=self.child_items.get(parent_key,())
        # Mixamo / topology pipeline checks stay Advanced-only. Intermediate users still
        # get useful cleanup tools without being dropped into character pipeline jargon.
        try:
            if parent_key == "TOOLS" and bpy.context.scene.optiblend_v123.mode != "ADVANCED":
                advanced_actions = {"RETOPO_QUADS", "MIXAMO_CHECK", "TOPOLOGY_AUDIT", "PIPELINE_EXPORT", "TEAM_COLLECTIONS"}
                children = tuple(child for child in children if child[0] not in advanced_actions)
        except Exception:
            pass
        cw=190*self.scale
        ch=46*self.scale
        gap=8*self.scale

        # Final V1 behaviour: the mini-tools now always appear to the right of the hovered
        # parent card. That keeps the flow consistent and makes the helper feel more
        # like a readable branch instead of cards jumping from side to side.
        cx = px + pw + 18*self.scale
        total=len(children)*ch + max(0,len(children)-1)*gap
        start_y=py+ph/2-total/2

        try:
            region=bpy.context.region
            if cx + cw > region.width - 8*self.scale:
                cx = max(8*self.scale, px - cw - 18*self.scale)
            start_y=max(8*self.scale,min(start_y,region.height-total-8*self.scale))
        except Exception:
            pass

        out=[]
        for i,child in enumerate(children):
            out.append((child,(cx,start_y+i*(ch+gap),cw,ch)))
        return out

    def child_icon_text(self, action):
        # Short custom chips are easier to read here than forcing Blender icons into the GPU UI.
        # to force Blender's built-in icons into a GPU-drawn menu that is meant to look
        # like OptiBlend instead of a standard dropdown.
        mapping = {
            "OPEN_SHAPES":"+", "IMPORT_EXTERNAL":"IM", "CUBE_FILTER":"[]", "CYLINDER_FILTER":"CY", "MORE_SHAPES":">>",
            "OPEN_MATERIALS":"M", "COLOUR_WHEEL":"CW", "METAL_PRESET":"Fe", "GLOW_PRESET":"GL",
            "MODE_BEGINNER":"B", "MODE_INTERMEDIATE":"I", "MODE_ADVANCED":"A",
            "MOD_SUBSURF":"SD", "MOD_BEVEL":"BV", "MOD_MIRROR":"MR", "MOD_SOLIDIFY":"SO", "MOD_ARRAY":"AR",
            "LIGHT_SETUP":"L", "LIGHT_SELECT_SUN":"SU", "LIGHT_SELECT_POINT":"PT",
            "CAMERA_SETUP":"C", "CAMERA_VIEW":"0", "CAMERA_ALIGN":"A0", "IMAGE_RENDER":"F12", "VIDEO_RENDER":"C+F", "GLOW_COMPOSITOR":"FX",
            "AUTO_COLLECTIONS":"AC", "SCAN_SCENE":"SC", "CLEAN_DATA":"CL", "RETOPO_QUADS":"QF", "RETOPO_TRI":"TR", "MIXAMO_CHECK":"MX", "TOPOLOGY_AUDIT":"TP", "PIPELINE_EXPORT":"FBX", "TEAM_COLLECTIONS":"TM",
            "INFO_Q":"Q", "INFO_G":"G", "INFO_R":"R", "INFO_S":"S", "INFO_TAB":"Tb", "INFO_AXIS":"XYZ",
        }
        return mapping.get(action, "*")

    def draw_wheel(self):
        pulse=(math.sin(time.time()*3.0)+1)/2
        items=self.visible_items(bpy.context)

        for i,(key,title,sub,dx,dy) in enumerate(items):
            x,y,w,h=self.card_rect(dx,dy,i)
            tx=x+w/2; ty=y+h/2
            for width,alpha in ((8,0.025),(4,0.05),(1.5,0.55)):
                _line(self.cx,self.cy,tx,ty,(GREEN[0],GREEN[1],GREEN[2],alpha+pulse*alpha*0.25),width)

        for r,a in ((67*self.scale,0.025),(58*self.scale,0.055),(49*self.scale,0.14)):
            _circle(self.cx,self.cy,r,(0.0,1.0,0.35,a+pulse*a*0.25))
        _circle(self.cx,self.cy,46*self.scale,(0.012,0.025,0.018,0.98))
        _text("OPTI",self.cx-18*self.scale,self.cy+10*self.scale,max(8,int(12*self.scale)),WHITE)
        _text("V1.0",self.cx-14*self.scale,self.cy-10*self.scale,max(7,int(8*self.scale)),ui_accent(bpy.context.scene.optiblend_v123))
        _text("Q = CLOSE",self.cx-25*self.scale,self.cy-29*self.scale,max(6,int(7*self.scale)),TEXT_SOFT)

        for i,(key,title,sub,dx,dy) in enumerate(items):
            x,y,w,h=self.card_rect(dx,dy,i)
            hover=self.hover==key or self.active_parent==key
            accent=CYAN if key in {"SHAPES","GUIDE"} else PURPLE if key=="COLOUR" else ORANGE if key=="RENDER" else GREEN
            if hover:
                for pad in (9,5):
                    _rect(x-pad,y-pad,w+pad*2,h+pad*2,(accent[0],accent[1],accent[2],0.035+pulse*0.04))
            _rect(x,y,w,h,(0.03,0.045,0.039,0.98) if not hover else (0.035,0.13,0.075,0.99))
            _outline(x,y,w,h,accent if hover else (0.18,0.27,0.23,1),2 if hover else 1)
            _circle(x+18*self.scale,y+h/2,7*self.scale,(accent[0],accent[1],accent[2],0.28 if not hover else 0.9))
            _text(title,x+34*self.scale,y+37*self.scale,max(8,int(11*self.scale)),WHITE)
            _text(sub,x+34*self.scale,y+16*self.scale,max(7,int(8*self.scale)),accent if hover else TEXT_SOFT)

        # The hover children are deliberately a different shape/scale from the parent
        # cards so it is obvious they are the next level down, not another main category.
        if self.active_parent:
            parent=self.parent_rect(self.active_parent)
            accent=PURPLE if self.active_parent=="COLOUR" else ORANGE if self.active_parent=="RENDER" else CYAN if self.active_parent=="GUIDE" else GREEN
            for (action,title,sub),(x,y,w,h) in self.child_rects(self.active_parent):
                hover=self.hover_child==action
                if parent:
                    px,py,pw,ph=parent
                    sx=px+pw if x>px else px
                    sy=py+ph/2
                    ex=x if x>px else x+w
                    ey=y+h/2
                    _line(sx,sy,ex,ey,(accent[0],accent[1],accent[2],0.32),1.2*self.scale)
                if hover:
                    _rect(x-4*self.scale,y-4*self.scale,w+8*self.scale,h+8*self.scale,(accent[0],accent[1],accent[2],0.07+pulse*0.04))
                _rect(x,y,w,h,(0.018,0.034,0.028,0.99) if not hover else (0.045,0.16,0.09,0.99))
                _outline(x,y,w,h,accent if hover else (0.20,0.31,0.27,1),2 if hover else 1)
                chip_w = 30*self.scale
                chip_h = 22*self.scale
                chip_x = x + w - chip_w - 8*self.scale
                chip_y = y + (h-chip_h)/2
                _rect(chip_x, chip_y, chip_w, chip_h, (accent[0], accent[1], accent[2], 0.12 if not hover else 0.26))
                _outline(chip_x, chip_y, chip_w, chip_h, accent, 1)
                _text(self.child_icon_text(action), chip_x + 5*self.scale, chip_y + 6*self.scale, max(6,int(7*self.scale)), WHITE)
                _text(title,x+10*self.scale,y+26*self.scale,max(7,int(9*self.scale)),WHITE)
                _text(sub,x+10*self.scale,y+9*self.scale,max(6,int(7*self.scale)),accent if hover else TEXT_SOFT)

        msg=None
        if self.hover_child:
            msg=self.child_help.get(self.hover_child)
        if not msg and self.active_parent:
            msg=self.hover_help.get(self.active_parent)
        if msg:
            w=490*self.scale; h=38*self.scale; hx=self.cx-w/2; hy=self.cy+247*self.scale
            _rect(hx,hy,w,h,(0.01,0.035,0.028,0.98))
            _outline(hx,hy,w,h,(CYAN[0],CYAN[1],CYAN[2],0.72),1)
            _text(msg[:98],hx+10*self.scale,hy+13*self.scale,max(7,int(8*self.scale)),TEXT_SOFT)


    def finish(self,context):
        global FANCY_WHEEL_RUNNING
        FANCY_WHEEL_RUNNING=False
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle,"WINDOW")
        except Exception:
            pass
        safe_area_redraw(context)

    def hit_parent(self,mx,my):
        for i,(key,title,sub,dx,dy) in enumerate(self.visible_items(bpy.context)):
            x,y,w,h=self.card_rect(dx,dy,i)
            if x<=mx<=x+w and y<=my<=y+h:
                return key
        return None

    def hit_child(self,mx,my):
        if not self.active_parent:
            return None
        for (action,title,sub),(x,y,w,h) in self.child_rects(self.active_parent):
            if x<=mx<=x+w and y<=my<=y+h:
                return action
        return None

    def open_filtered_shelf(self,context,mode,search=""):
        props=context.scene.optiblend_v123
        props.asset_bar_mode=mode
        props.asset_bar_visible=True
        props.asset_scroll_current=0
        props.asset_scroll_target=0
        if mode=="SHAPES":
            props.shape_search=search
        else:
            props.material_search=search
        ensure_asset_bar_listener(context)
        tag_redraw(context)

    def apply_material_quick(self,context,key):
        mat=material_from_preset(context,key)
        count=0
        for obj in context.selected_objects:
            if assign_material(obj,mat):
                count+=1
        if count:
            bump_guide(context,"guide_materials")
            set_report(context,MATERIAL_LIBRARY[key]["name"]+f" applied to {count} selected object(s).")
            return True
        # No selection should not feel like a failure to a beginner. Open the shelf
        # filtered to that material so they can drag it onto the thing they want.
        self.open_filtered_shelf(context,"MATERIALS",MATERIAL_LIBRARY[key]["name"])
        return True

    def execute_child(self,context,action):
        # Final V1 behaviour: guide cards now open a live on-screen guide, then the Q Helper
        # closes so the learner can actually see the viewport while following the steps.
        if action.startswith("INFO_"):
            mapping = {"INFO_Q":"Q", "INFO_G":"G", "INFO_R":"R", "INFO_S":"S", "INFO_TAB":"TAB", "INFO_AXIS":"AXIS"}
            activate_live_guide(context, mapping.get(action, "Q"))
            return True

        if action=="OPEN_SHAPES": self.open_filtered_shelf(context,"SHAPES","")
        elif action=="IMPORT_EXTERNAL": bpy.ops.optiblend_v123.import_external("INVOKE_DEFAULT")
        elif action=="CUBE_FILTER": self.open_filtered_shelf(context,"SHAPES","Cube")
        elif action=="CYLINDER_FILTER": self.open_filtered_shelf(context,"SHAPES","Cylinder")
        elif action=="MORE_SHAPES": self.open_filtered_shelf(context,"SHAPES","")
        elif action=="OPEN_MATERIALS": self.open_filtered_shelf(context,"MATERIALS","")
        elif action=="COLOUR_WHEEL": bpy.ops.optiblend_v123.colour_wheel("INVOKE_DEFAULT")
        elif action=="METAL_PRESET": return self.apply_material_quick(context,"METAL")
        elif action=="GLOW_PRESET": return self.apply_material_quick(context,"GLOW")
        elif action=="MODE_BEGINNER": apply_mode(context,"BEGINNER")
        elif action=="MODE_INTERMEDIATE": apply_mode(context,"INTERMEDIATE")
        elif action=="MODE_ADVANCED": apply_mode(context,"ADVANCED")
        elif action.startswith("MOD_"):
            mapping={"MOD_SUBSURF":"SUBSURF","MOD_BEVEL":"BEVEL","MOD_MIRROR":"MIRROR","MOD_SOLIDIFY":"SOLIDIFY","MOD_ARRAY":"ARRAY"}
            bpy.ops.optiblend_v123.add_modifier(modifier_type=mapping[action])
        elif action=="LIGHT_SETUP": bpy.ops.optiblend_v123.default_lights()
        elif action=="LIGHT_SELECT_SUN":
            ensure_default_lighting(context); obj=bpy.data.objects.get("OptiBlend Sun")
            if obj: bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True); context.view_layer.objects.active=obj
        elif action=="LIGHT_SELECT_POINT":
            ensure_default_lighting(context); obj=bpy.data.objects.get("OptiBlend Point")
            if obj: bpy.ops.object.select_all(action="DESELECT"); obj.select_set(True); context.view_layer.objects.active=obj
        elif action=="CAMERA_SETUP": bpy.ops.optiblend_v123.camera_create_select()
        elif action=="CAMERA_VIEW": bpy.ops.optiblend_v123.camera_view()
        elif action=="CAMERA_ALIGN": bpy.ops.optiblend_v123.camera_align_view()
        elif action=="IMAGE_RENDER": bpy.ops.optiblend_v123.render_image()
        elif action=="VIDEO_RENDER": bpy.ops.optiblend_v123.render_video()
        elif action=="GLOW_COMPOSITOR": bpy.ops.optiblend_v123.enable_glare()
        elif action=="AUTO_COLLECTIONS": bpy.ops.optiblend_v123.auto_collections()
        elif action=="SCAN_SCENE": bpy.ops.optiblend_v123.scan_scene()
        elif action=="CLEAN_DATA": bpy.ops.optiblend_v123.clean_data()
        elif action=="RETOPO_QUADS": bpy.ops.optiblend_v123.retopo_quads()
        elif action=="RETOPO_TRI": bpy.ops.optiblend_v123.retopo_triangles()
        elif action=="MIXAMO_CHECK": bpy.ops.optiblend_v123.mixamo_check("INVOKE_DEFAULT")
        elif action=="TOPOLOGY_AUDIT": bpy.ops.optiblend_v123.topology_audit("INVOKE_DEFAULT")
        elif action=="PIPELINE_EXPORT": bpy.ops.optiblend_v123.pipeline_export_prep()
        elif action=="TEAM_COLLECTIONS": bpy.ops.optiblend_v123.team_collections_setup()
        return True

    def modal(self,context,event):
        if event.type=="Q" and event.value=="PRESS":
            self.finish(context)
            return {"CANCELLED"}

        mx,my=event.mouse_region_x,event.mouse_region_y
        dist=math.hypot(mx-self.cx,my-self.cy)

        if event.type=="LEFTMOUSE" and event.value=="PRESS" and dist<49*self.scale:
            self.drag_center=True
            self.drag_offset=(mx-self.cx,my-self.cy)
            return {"RUNNING_MODAL"}
        if event.type=="MOUSEMOVE" and self.drag_center:
            ox,oy=self.drag_offset
            self.cx=mx-ox; self.cy=my-oy
            safe_area_redraw(context); return {"RUNNING_MODAL"}
        if event.type=="LEFTMOUSE" and event.value=="RELEASE" and self.drag_center:
            self.drag_center=False
            return {"RUNNING_MODAL"}

        parent=self.hit_parent(mx,my)
        if parent:
            self.hover=parent
            self.active_parent=parent
        else:
            self.hover=None

        child=self.hit_child(mx,my)
        if child!=self.hover_child:
            self.hover_child=child
            safe_area_redraw(context)

        # The parent stays open while the cursor travels into its mini-tools. It changes
        # only when another main card is hovered, which avoids annoying flicker between
        # the parent and child rectangles.
        if event.type=="MOUSEMOVE":
            safe_area_redraw(context)

        if event.type=="LEFTMOUSE" and event.value=="RELEASE":
            if self.hover_child:
                action=self.hover_child
                keep_open=not self.execute_child(context,action)
                if keep_open:
                    safe_area_redraw(context)
                    return {"RUNNING_MODAL"}
                self.finish(context)
                return {"FINISHED"}
            if parent:
                self.active_parent=parent
                safe_area_redraw(context)
                return {"RUNNING_MODAL"}

        if event.type in {"ESC","RIGHTMOUSE"}:
            self.finish(context)
            return {"CANCELLED"}
        return {"RUNNING_MODAL"}


# =============================================================================
# regular menus / header
# =============================================================================
# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
class OPTIBLEND_V123_MT_mode(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_mode"; bl_label="OptiBlend Mode"
    def draw(self,context):
        l=self.layout
        l.operator("optiblend_v123.mode_beginner",text="Beginner",icon="HOME")
        l.operator("optiblend_v123.mode_intermediate",text="Intermediate",icon="MODIFIER")
        l.operator("optiblend_v123.mode_advanced",text="Advanced",icon="CONSOLE")
        l.separator(); p=context.scene.optiblend_v123
        l.prop(p,"workspace_lock_enabled",text="Lock Workspace Tabs")
        l.prop(p,"simplify_beginner_ui",text="Simplify Beginner Right Side")
        l.operator("optiblend_v123.reapply_mode",text="Re-Apply Mode Now",icon="FILE_REFRESH")


class OPTIBLEND_V123_MT_lights(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_lights"; bl_label="Lights"
    def draw(self,context):
        l=self.layout
        l.label(text="Sun = overall direction")
        l.label(text="Point = local lamp / highlight")
        l.separator(); l.operator("optiblend_v123.default_lights",text="Create / Reset Sun + Point",icon="LIGHT")


class OPTIBLEND_V123_MT_modifiers(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_modifiers"; bl_label="Modifiers"
    def draw(self,context):
        l=self.layout
        l.label(text="Non-destructive modelling",icon="MODIFIER")
        for kind,label,icon in (("SUBSURF","Subdivision Surface","MOD_SUBSURF"),("BEVEL","Bevel","MOD_BEVEL"),("MIRROR","Mirror","MOD_MIRROR"),("SOLIDIFY","Solidify","MOD_SOLIDIFY"),("ARRAY","Array","MOD_ARRAY")):
            op=l.operator("optiblend_v123.add_modifier",text=label,icon=icon); op.modifier_type=kind
        l.separator(); l.menu("OPTIBLEND_V123_MT_retopology",text="Advanced Retopology",icon="MODIFIER")


class OPTIBLEND_V123_MT_retopology(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_retopology"; bl_label="Retopology"
    def draw(self,context):
        l=self.layout; p=context.scene.optiblend_v123
        l.label(text="Advanced mesh cleanup",icon="MODIFIER")
        l.prop(p,"retopo_target_faces")
        l.operator("optiblend_v123.retopo_quads",text="Quad Retopo (QuadriFlow)",icon="MODIFIER")
        l.operator("optiblend_v123.retopo_triangles",text="Triangulate Non-Destructively",icon="MODIFIER")
        l.operator("optiblend_v123.subdivision_ready",text="Subdivision-Ready Setup",icon="MOD_SUBSURF")


class OPTIBLEND_V123_MT_compositor(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_compositor"; bl_label="Compositor Glow"
    def draw(self,context):
        l=self.layout; p=context.scene.optiblend_v123
        l.label(text="Glare / glow compositor helper",icon="NODETREE")
        l.prop(p,"glare_mode")
        l.prop(p,"glare_threshold")
        l.prop(p,"glare_size")
        l.operator("optiblend_v123.enable_glare",text="Enable / Update Glow",icon="LIGHT")
        l.operator("optiblend_v123.disable_glare",text="Disable OptiBlend Glow",icon="X")


class OPTIBLEND_V123_MT_render(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_render"; bl_label="Render"
    def draw(self,context):
        l=self.layout
        l.label(text="Camera",icon="CAMERA_DATA")
        l.operator("optiblend_v123.camera_create_select",text="Create / Select Camera",icon="CAMERA_DATA")
        l.operator("optiblend_v123.camera_view",text="Look Through Camera",icon="HIDE_OFF")
        l.operator("optiblend_v123.camera_align_view",text="Align Camera To Current View",icon="CAMERA_DATA")
        l.separator()
        l.operator("optiblend_v123.render_image",text="Image Render   [F12]",icon="RENDER_STILL")
        l.operator("optiblend_v123.render_video",text="Video Render   [Ctrl + F12]",icon="RENDER_ANIMATION")
        l.separator(); l.menu("OPTIBLEND_V123_MT_compositor",text="Compositor Glow / Glare",icon="NODETREE")


class OPTIBLEND_V123_MT_tools(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_tools"; bl_label="Scene Tools"
    def draw(self,context):
        l=self.layout; p=context.scene.optiblend_v123
        l.operator("optiblend_v123.scan_scene",text="Scan Scene",icon="VIEWZOOM")
        l.operator("optiblend_v123.clean_data",text="Clean Unused Data",icon="BRUSH_DATA")
        l.operator("optiblend_v123.auto_collections",text="Auto Collections + Remove Empty",icon="OUTLINER_COLLECTION")
        l.prop(p,"live_auto_collection",text="Sort New Objects Automatically")
        l.separator()
        l.label(text="Placement Controls", icon="SNAP_ON")
        l.prop(p,"center_snap_enabled")
        l.prop(p,"align_preview_to_surface")
        l.prop(p,"rotation_step_degrees")
        l.prop(p,"edit_mode_smart_snap")
        l.prop(p,"object_xyz_helper")
        l.separator(); l.label(text="Interface / HCI",icon="PREFERENCES")
        l.prop(p,"ui_scale")
        l.prop(p,"show_q_hint")
        l.prop(p,"show_hover_tips")
        l.prop(p,"ui_glow_enabled")
        l.prop(p,"developer_test_menu",text="Show Test Lab Button")
        l.separator(); l.menu("OPTIBLEND_V123_MT_modifiers",text="Modifiers",icon="MODIFIER")
        if p.mode == "ADVANCED":
            l.separator()
            l.menu("OPTIBLEND_V123_MT_advanced_pipeline", text="Advanced Pipeline Fixes", icon="TOOL_SETTINGS")
        l.operator("optiblend_v123.licenses",text="Licenses + References",icon="TEXT")
        l.separator(); l.operator("optiblend_v123.status_popup",text="Status",icon="INFO")


class OPTIBLEND_V123_MT_advanced_pipeline(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_advanced_pipeline"; bl_label="Advanced Pipeline Fixes"
    def draw(self,context):
        l=self.layout
        l.label(text="Performance and pipeline helpers", icon="TOOL_SETTINGS")
        l.operator("optiblend_v123.performance_audit", text="Performance Audit", icon="VIEWZOOM")
        l.operator("optiblend_v123.import_external", text="Import External Model", icon="IMPORT")
        l.menu("OPTIBLEND_V123_MT_rig_check", text="Rig / Mixamo Readiness", icon="ARMATURE_DATA")
        l.operator("optiblend_v123.pipeline_export_prep", text="FBX / Export Prep", icon="EXPORT")
        l.operator("optiblend_v123.team_collections_setup", text="Team Collection Blocks", icon="OUTLINER_COLLECTION")
        l.operator("optiblend_v123.open_uv_helper", text="Open UV Helper", icon="UV")
        l.operator("optiblend_v123.weighted_normals_fix", text="Weighted Normals Fix", icon="MOD_NORMALEDIT")
        l.operator("optiblend_v123.modifier_stack_helper", text="Modifier Stack Helper", icon="MODIFIER")
        l.separator()
        l.label(text="These target Blender workflow limits", icon="INFO")
        l.label(text="Large scenes, FBX scale/bake issues, team structure,")
        l.label(text="modifier rigidity, UV bottlenecks and normal editing.")



class OPTIBLEND_V123_MT_rig_check(bpy.types.Menu):
    bl_idname = "OPTIBLEND_V123_MT_rig_check"
    bl_label = "Rig / Mixamo Readiness"

    def draw(self, context):
        layout = self.layout
        props = context.scene.optiblend_v123
        layout.label(text="Advanced Character Pipeline", icon="ARMATURE_DATA")
        layout.operator("optiblend_v123.mixamo_check", text="Run Mixamo Readiness Check", icon="CHECKMARK")
        layout.operator("optiblend_v123.topology_audit", text="Topology Audit", icon="MESH_DATA")
        layout.operator("optiblend_v123.rig_modifier_audit", text="Rig / Modifier / Particle Audit", icon="MODIFIER")
        layout.separator()
        layout.operator("optiblend_v123.retopo_quads", text="Quad Retopo", icon="MODIFIER")
        layout.operator("optiblend_v123.retopo_triangles", text="Triangulate", icon="MODIFIER")
        layout.operator("optiblend_v123.subdivision_ready", text="Subdivision-Ready Setup", icon="MOD_SUBSURF")
        layout.separator()
        layout.operator("optiblend_v123.pipeline_export_prep", text="FBX / Export Prep", icon="EXPORT")
        layout.operator("optiblend_v123.mixamo_research", text="Research Used By Checker", icon="INFO")
        layout.separator()
        row = layout.row()
        row.enabled = False
        row.label(text=f"Last heuristic score: {props.mixamo_last_score}/100")


class OPTIBLEND_V123_MT_import(bpy.types.Menu):
    bl_idname = "OPTIBLEND_V123_MT_import"
    bl_label = "Import"

    def draw(self, context):
        layout = self.layout
        props = context.scene.optiblend_v123
        layout.label(text="External Objects", icon="IMPORT")
        layout.operator("optiblend_v123.import_external", text="Import FBX / OBJ / GLTF / STL", icon="IMPORT")
        layout.separator()
        layout.prop(props, "import_auto_organize")
        layout.prop(props, "import_run_scan")
        layout.label(text="Imported objects stay selected and the Move tool turns on.", icon="INFO")


class OPTIBLEND_V123_PT_advanced_pipeline(bpy.types.Panel):
    bl_label = "OptiBlend Advanced"
    bl_idname = "OPTIBLEND_V123_PT_advanced_pipeline"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OptiBlend"

    @classmethod
    def poll(cls, context):
        return hasattr(context.scene, "optiblend_v123") and context.scene.optiblend_v123.mode == "ADVANCED"

    def draw(self, context):
        layout = self.layout
        props = context.scene.optiblend_v123

        box = layout.box()
        box.label(text="Character / Mixamo", icon="ARMATURE_DATA")
        box.operator("optiblend_v123.mixamo_check", text="Mixamo Readiness")
        box.operator("optiblend_v123.topology_audit", text="Topology Audit")
        box.operator("optiblend_v123.rig_modifier_audit", text="Rig + Modifier + Particle Audit")
        box.label(text=f"Last score: {props.mixamo_last_score}/100")

        box = layout.box()
        box.label(text="Retopology", icon="MODIFIER")
        box.prop(props, "retopo_target_faces")
        box.operator("optiblend_v123.retopo_quads", text="QuadriFlow Quads")
        box.operator("optiblend_v123.retopo_triangles", text="Triangulate Modifier")
        box.operator("optiblend_v123.subdivision_ready", text="Subdivision Ready")

        box = layout.box()
        box.label(text="Pipeline / Import", icon="TOOL_SETTINGS")
        box.operator("optiblend_v123.import_external", text="Import External Model", icon="IMPORT")
        box.operator("optiblend_v123.pipeline_export_prep", text="FBX / Export Prep", icon="EXPORT")
        box.operator("optiblend_v123.performance_audit", text="Performance Audit", icon="VIEWZOOM")
        box.operator("optiblend_v123.team_collections_setup", text="Team Collection Blocks", icon="OUTLINER_COLLECTION")
        box.operator("optiblend_v123.open_uv_helper", text="UV Helper", icon="UV")
        box.operator("optiblend_v123.weighted_normals_fix", text="Weighted Normals", icon="MOD_NORMALEDIT")
        box.operator("optiblend_v123.modifier_stack_helper", text="Modifier Stack Helper", icon="MODIFIER")

        box = layout.box()
        box.label(text="Research / HCI", icon="INFO")
        box.operator("optiblend_v123.mixamo_research", text="Mixamo Research Notes")
        box.operator("optiblend_v123.licenses", text="Licenses + References", icon="TEXT")
        box.prop(props, "ui_scale")


class OPTIBLEND_V123_MT_guide(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_guide"; bl_label="OptiBlend Guide"
    def draw(self,context):
        p=context.scene.optiblend_v123; l=self.layout
        l.label(text="OPTIBLEND QUICK GUIDE",icon="INFO")
        l.label(text="Q  - open / close OptiBlend Helper")
        l.label(text="L  - open OptiBlend Test Lab")
        l.separator()
        l.label(text="Basic Blender keys",icon="INFO")
        l.label(text="G  - Move")
        l.label(text="R  - Rotate")
        l.label(text="S  - Scale")
        l.label(text="X / Y / Z  - choose an axis")
        l.label(text="Tab  - Object Mode / Edit Mode")
        l.label(text="Ctrl + Z  - Undo")
        l.separator()
        l.label(text="OptiBlend placement",icon="SNAP_ON")
        l.label(text="Drag from Shapes -> release to place")
        l.label(text="Mouse wheel -> rotate preview")
        l.label(text="R -> quick 90 degree turn while dragging")
        l.label(text="Alt + R -> reset preview rotation")
        l.label(text="Ctrl while dragging -> centre snap")
        l.separator()
        l.label(text="Render",icon="RENDER_STILL")
        l.label(text="F12  - image render")
        l.label(text="Ctrl + F12  - animation render")
        l.label(text="Numpad 0  - camera view")
        l.separator(); l.label(text="Small practice goals",icon="CHECKMARK")
        tasks=[
            (p.guide_shapes>=3,"Place 3 shapes",f"{min(p.guide_shapes,3)}/3"),
            (p.guide_materials>=1,"Apply a material",f"{min(p.guide_materials,1)}/1"),
            (p.guide_lights>=1,"Create Sun + Point",f"{min(p.guide_lights,1)}/1"),
        ]
        for done,label,count in tasks:
            row=l.row(); row.label(text=("DONE  " if done else "TRY   ")+label,icon="CHECKMARK" if done else "RADIOBUT_OFF"); row.label(text=count)
        l.separator(); l.operator("optiblend_v123.reset_guide",text="Reset Guide Progress",icon="LOOP_BACK")


def draw_header_tabs(self,context):
    if not hasattr(context.scene,"optiblend_v123"):
        return
    p=context.scene.optiblend_v123; l=self.layout; row=l.row(align=True)
    row.separator(); row.label(text="OptiBlend",icon="SHADERFX")

    # Beginner header is intentionally tiny. Earlier builds technically simplified the
    # workspace but then put a wall of OptiBlend buttons across the top, which defeated
    # the point. The advanced tools are still one Q press away through progressive hover.
    if p.show_q_hint and p.mode != "ADVANCED":
        hint=row.row(align=True); hint.alert=True; hint.label(text="PRESS Q = HELPER",icon="INFO")

    op=row.operator("optiblend_v123.show_asset_bar",text="Shapes",icon="MESH_CUBE",depress=p.asset_bar_visible and p.asset_bar_mode=="SHAPES"); op.bar_mode="SHAPES"
    op=row.operator("optiblend_v123.show_asset_bar",text="Materials",icon="MATERIAL",depress=p.asset_bar_visible and p.asset_bar_mode=="MATERIALS"); op.bar_mode="MATERIALS"

    if p.asset_bar_visible:
        if p.asset_bar_mode=="SHAPES":
            row.prop(p,"shape_search",text="",icon="VIEWZOOM")
        else:
            row.prop(p,"material_search",text="",icon="VIEWZOOM")
            row.prop(p,"material_category",text="")
            row.prop(p,"custom_color",text="")

    # Beginner gets only the things needed to learn. Intermediate restores practical
    # modelling/render buttons. Advanced gets the full OptiBlend header.
    row.menu("OPTIBLEND_V123_MT_guide",text="Guide",icon="INFO")
    row.menu("OPTIBLEND_V123_MT_mode",text=p.mode.title(),icon="PREFERENCES")

    if p.mode in {"INTERMEDIATE","ADVANCED"}:
        row.menu("OPTIBLEND_V123_MT_modifiers",text="Modifiers",icon="MODIFIER")
        row.menu("OPTIBLEND_V123_MT_lights",text="Lights",icon="LIGHT")
        row.menu("OPTIBLEND_V123_MT_render",text="Render",icon="RENDER_STILL")
        row.menu("OPTIBLEND_V123_MT_import",text="Import",icon="IMPORT")
        row.menu("OPTIBLEND_V123_MT_tools",text="Tools",icon="TOOL_SETTINGS")

    if p.mode == "ADVANCED":
        row.menu("OPTIBLEND_V123_MT_rig_check",text="Rig Check",icon="ARMATURE_DATA")

    if p.developer_test_menu:
        row.menu("OPTIBLEND_V123_MT_test_lab",text="Test",icon="TOOL_SETTINGS")


# =============================================================================
# main operators
# =============================================================================
class OPTIBLEND_V123_OT_show_asset_bar(bpy.types.Operator):
    bl_idname="optiblend_v123.show_asset_bar"; bl_label="Show Asset Bar"
    bar_mode:bpy.props.EnumProperty(items=[("SHAPES","Shapes",""),("MATERIALS","Materials","")],default="SHAPES")

    @classmethod
    def description(cls,context,properties):
        if getattr(properties,"bar_mode","SHAPES")=="MATERIALS":
            return "Open the material shelf. Drag presets onto meshes; Custom and the header swatch open Blender's colour wheel."
        return "Open the shape shelf. Drag a named primitive into the viewport and release to place it."

    def execute(self,context):
        p=context.scene.optiblend_v123
        if p.asset_bar_visible and p.asset_bar_mode==self.bar_mode:
            p.asset_bar_visible=False
        else:
            p.asset_bar_mode=self.bar_mode; p.asset_bar_visible=True
        p.hover_asset=""; p.asset_scroll_current=0; p.asset_scroll_target=0
        ensure_asset_bar_listener(context); tag_redraw(context); return {"FINISHED"}


class OPTIBLEND_V123_OT_mode_beginner(bpy.types.Operator):
    bl_idname="optiblend_v123.mode_beginner"; bl_label="Beginner Mode"; bl_options={"REGISTER","UNDO"}
    def execute(self,context): apply_mode(context,"BEGINNER"); return {"FINISHED"}
class OPTIBLEND_V123_OT_mode_intermediate(bpy.types.Operator):
    bl_idname="optiblend_v123.mode_intermediate"; bl_label="Intermediate Mode"; bl_options={"REGISTER","UNDO"}
    def execute(self,context): apply_mode(context,"INTERMEDIATE"); return {"FINISHED"}
class OPTIBLEND_V123_OT_mode_advanced(bpy.types.Operator):
    bl_idname="optiblend_v123.mode_advanced"; bl_label="Advanced Mode"; bl_options={"REGISTER","UNDO"}
    def execute(self,context): apply_mode(context,"ADVANCED"); return {"FINISHED"}
class OPTIBLEND_V123_OT_reapply_mode(bpy.types.Operator):
    bl_idname="optiblend_v123.reapply_mode"; bl_label="Re-Apply Current Mode"
    def execute(self,context): apply_mode(context,context.scene.optiblend_v123.mode); return {"FINISHED"}


class OPTIBLEND_V123_OT_colour_wheel(bpy.types.Operator):
    bl_idname="optiblend_v123.colour_wheel"; bl_label="Custom Colour Wheel"; bl_options={"REGISTER","UNDO"}
    def invoke(self,context,event): return context.window_manager.invoke_props_dialog(self,width=390)
    def draw(self,context):
        p=context.scene.optiblend_v123; l=self.layout
        l.label(text="Custom Material",icon="COLOR"); l.prop(p,"custom_color",text="Colour"); l.prop(p,"material_metallic"); l.prop(p,"material_roughness")
        l.label(text="Click the colour swatch to use Blender's native wheel.")
    def execute(self,context):
        mat=material_from_preset(context,"CUSTOM"); count=0
        for obj in context.selected_objects:
            if assign_material(obj,mat): count+=1
        if count: bump_guide(context,"guide_materials")
        set_report(context,f"Custom colour applied to {count} object(s)."); return {"FINISHED"}


# This is defensive on purpose because Blender context can change underneath modal tools.
# I would rather skip one update than throw an error and stop the whole workflow.
class OPTIBLEND_V123_OT_default_lights(bpy.types.Operator):
    bl_idname="optiblend_v123.default_lights"; bl_label="Default Sun + Point"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        sun,point=ensure_default_lighting(context); bump_guide(context,"guide_lights"); set_report(context,"Lighting ready: "+sun.name+" + "+point.name); return {"FINISHED"}


# =============================================================================
# final modelling / camera / render operators
# =============================================================================
# These are intentionally small wrapper tools around Blender's own systems. The HCI
# The goal is recognition over recall: a beginner should see a named action instead of
# needing to remember where Blender buried it or which shortcut changes the result.
class OPTIBLEND_V123_OT_add_modifier(bpy.types.Operator):
    bl_idname="optiblend_v123.add_modifier"; bl_label="Add Modifier"; bl_options={"REGISTER","UNDO"}
    modifier_type:bpy.props.EnumProperty(items=[("SUBSURF","Subdivision Surface","Smooth/add geometry"),("BEVEL","Bevel","Round edges"),("MIRROR","Mirror","Symmetrical modelling"),("SOLIDIFY","Solidify","Give thickness"),("ARRAY","Array","Repeat geometry")],default="SUBSURF")

    @classmethod
    def description(cls,context,properties):
        tips={
            "SUBSURF":"Smooths the selected mesh non-destructively by subdividing the surface.",
            "BEVEL":"Rounds hard edges with a small three-segment bevel.",
            "MIRROR":"Mirrors geometry across local X for symmetrical modelling.",
            "SOLIDIFY":"Adds real thickness to a flat/open mesh.",
            "ARRAY":"Repeats the object three times along X.",
        }
        return tips.get(properties.modifier_type,"Add an OptiBlend modifier")

    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!="MESH":
            self.report({"WARNING"},"Select a mesh first")
            return {"CANCELLED"}
        kind=self.modifier_type
        names={"SUBSURF":"OptiBlend Subdivision","BEVEL":"OptiBlend Bevel","MIRROR":"OptiBlend Mirror","SOLIDIFY":"OptiBlend Solidify","ARRAY":"OptiBlend Array"}
        mod=obj.modifiers.new(names[kind],kind)
        try:
            if kind=="SUBSURF":
                mod.levels=2; mod.render_levels=2
            elif kind=="BEVEL":
                mod.width=max(0.01,object_bbox_radius_world(obj)*0.035); mod.segments=3; mod.limit_method="ANGLE"
            elif kind=="MIRROR":
                mod.use_axis[0]=True; mod.use_clip=True
            elif kind=="SOLIDIFY":
                mod.thickness=max(0.02,object_bbox_radius_world(obj)*0.05)
            elif kind=="ARRAY":
                mod.count=3; mod.relative_offset_displace=(1.25,0.0,0.0)
        except Exception:
            # Defaults still leave a valid modifier even if one Blender version names
            # a secondary option differently, so this is safer than failing outright.
            pass
        set_report(context,f"Added {names[kind]} to {obj.name}.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_retopo_quads(bpy.types.Operator):
    bl_idname="optiblend_v123.retopo_quads"; bl_label="Quad Retopo"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced: run Blender QuadriFlow to rebuild the selected mesh mainly as quads. This changes topology and may take time."
    def execute(self,context):
        p=context.scene.optiblend_v123; obj=context.active_object
        if p.mode!="ADVANCED":
            self.report({"WARNING"},"Quad Retopo is kept in Advanced mode")
            return {"CANCELLED"}
        if not obj or obj.type!="MESH" or context.mode!="OBJECT":
            self.report({"WARNING"},"Select one mesh in Object Mode")
            return {"CANCELLED"}
        try:
            bpy.ops.object.quadriflow_remesh(use_mesh_symmetry=False,use_preserve_sharp=True,use_preserve_boundary=True,preserve_attributes=True,smooth_normals=True,mode="FACES",target_faces=p.retopo_target_faces)
            set_report(context,f"QuadriFlow completed near target {p.retopo_target_faces} faces.")
            return {"FINISHED"}
        except Exception as e:
            self.report({"ERROR"},"QuadriFlow could not run: "+str(e))
            return {"CANCELLED"}


class OPTIBLEND_V123_OT_retopo_triangles(bpy.types.Operator):
    bl_idname="optiblend_v123.retopo_triangles"; bl_label="Triangulate"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced: add a non-destructive Triangulate modifier using Beauty methods."
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!="MESH":
            self.report({"WARNING"},"Select a mesh first"); return {"CANCELLED"}
        mod=obj.modifiers.new("OptiBlend Triangulate","TRIANGULATE")
        try:
            mod.quad_method="BEAUTY"; mod.ngon_method="BEAUTY"; mod.keep_custom_normals=True
        except Exception: pass
        return {"FINISHED"}


class OPTIBLEND_V123_OT_subdivision_ready(bpy.types.Operator):
    bl_idname="optiblend_v123.subdivision_ready"; bl_label="Subdivision Ready"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: smooth shading plus a level-2 Subdivision Surface modifier."
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!="MESH":
            self.report({"WARNING"},"Select a mesh first"); return {"CANCELLED"}
        try:
            for poly in obj.data.polygons: poly.use_smooth=True
        except Exception: pass
        mod=obj.modifiers.new("OptiBlend Subdivision Ready","SUBSURF"); mod.levels=2; mod.render_levels=2
        return {"FINISHED"}


class OPTIBLEND_V123_OT_camera_create_select(bpy.types.Operator):
    bl_idname="optiblend_v123.camera_create_select"; bl_label="Create / Select Camera"; bl_options={"REGISTER","UNDO"}
    bl_description="Select the scene camera, or create an OptiBlend camera if the scene does not have one."
    def execute(self,context):
        cam=active_camera(context)
        try: bpy.ops.object.select_all(action="DESELECT")
        except Exception: pass
        cam.select_set(True); context.view_layer.objects.active=cam
        set_report(context,"Active camera: "+cam.name)
        return {"FINISHED"}


class OPTIBLEND_V123_OT_camera_view(bpy.types.Operator):
    bl_idname="optiblend_v123.camera_view"; bl_label="Camera View"
    bl_description="Switch the current 3D View into the active camera view."
    def execute(self,context):
        active_camera(context)
        try: bpy.ops.view3d.view_camera()
        except Exception:
            self.report({"WARNING"},"Run this from a 3D Viewport")
            return {"CANCELLED"}
        return {"FINISHED"}


class OPTIBLEND_V123_OT_camera_align_view(bpy.types.Operator):
    bl_idname="optiblend_v123.camera_align_view"; bl_label="Align Camera To View"; bl_options={"REGISTER","UNDO"}
    bl_description="Move the active camera to exactly match the current viewport view."
    def execute(self,context):
        active_camera(context)
        try: bpy.ops.view3d.camera_to_view()
        except Exception:
            self.report({"WARNING"},"Run this from a 3D Viewport")
            return {"CANCELLED"}
        return {"FINISHED"}


class OPTIBLEND_V123_OT_enable_glare(bpy.types.Operator):
    bl_idname="optiblend_v123.enable_glare"; bl_label="Enable Compositor Glow"; bl_options={"REGISTER","UNDO"}
    bl_description="Insert or update one OptiBlend Glare node before the Composite output."
    def execute(self,context):
        p=context.scene.optiblend_v123
        node=ensure_compositor_glare(context.scene,p.glare_mode)
        set_report(context,"Compositor glare enabled: "+p.glare_mode.replace("_"," ").title())
        return {"FINISHED"} if node else {"CANCELLED"}


class OPTIBLEND_V123_OT_disable_glare(bpy.types.Operator):
    bl_idname="optiblend_v123.disable_glare"; bl_label="Disable Compositor Glow"; bl_options={"REGISTER","UNDO"}
    bl_description="Remove only the OptiBlend glare node and reconnect the previous image source."
    def execute(self,context):
        disable_compositor_glare(context.scene); set_report(context,"OptiBlend compositor glare disabled."); return {"FINISHED"}


class OPTIBLEND_V123_OT_licenses(bpy.types.Operator):
    bl_idname="optiblend_v123.licenses"; bl_label="Licenses + References"
    bl_description="Show the licenses and research references shipped with OptiBlend."
    def invoke(self,context,event): return context.window_manager.invoke_props_dialog(self,width=620)
    def draw(self,context):
        l=self.layout
        l.label(text="OptiBlend V1.0 - Licenses",icon="TEXT")
        l.label(text="Python add-on code: GNU GPL v3 or later")
        l.label(text="Included original preview icons/assets: CC0 1.0")
        l.label(text="Blender: GNU GPL")
        l.label(text="Blender developer documentation: CC BY-SA 4.0 for documentation text")
        l.label(text="BlenderKit: interaction research/reference only; no BlenderKit code bundled")
        l.separator(); l.label(text="See LICENSES.txt inside the add-on folder for full reference links.")
    def execute(self,context): return {"FINISHED"}


class OPTIBLEND_V123_OT_render_image(bpy.types.Operator):
    bl_idname="optiblend_v123.render_image"; bl_label="Image Render"; bl_description="Same core render action as F12."
    def execute(self,context): ensure_camera(context); bpy.ops.render.render("INVOKE_DEFAULT"); return {"FINISHED"}
class OPTIBLEND_V123_OT_render_video(bpy.types.Operator):
    bl_idname="optiblend_v123.render_video"; bl_label="Video Render"; bl_description="Animation render, like Ctrl + F12."
    def execute(self,context): ensure_camera(context); bpy.ops.render.render("INVOKE_DEFAULT",animation=True); return {"FINISHED"}


class OPTIBLEND_V123_OT_scan_scene(bpy.types.Operator):
    bl_idname="optiblend_v123.scan_scene"; bl_label="Scan Scene"
    def execute(self,context):
        p=context.scene.optiblend_v123; meshes=[o for o in context.scene.objects if o.type=="MESH"]; polys=sum(len(o.data.polygons) for o in meshes); high=[o for o in meshes if len(o.data.polygons)>p.high_poly_limit]
        set_report(context,f"Scene Scan\nObjects: {len(context.scene.objects)}\nMeshes: {len(meshes)}\nPolygons: {polys}\nHigh-poly: {len(high)}"); return {"FINISHED"}


class OPTIBLEND_V123_OT_clean_data(bpy.types.Operator):
    bl_idname="optiblend_v123.clean_data"; bl_label="Clean Unused Data"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        count=0
        for mesh in list(bpy.data.meshes):
            if mesh.users==0: bpy.data.meshes.remove(mesh); count+=1
        for mat in list(bpy.data.materials):
            if mat.users==0: bpy.data.materials.remove(mat); count+=1
        set_report(context,f"Unused meshes/materials removed: {count}"); return {"FINISHED"}


class OPTIBLEND_V123_OT_auto_collections(bpy.types.Operator):
    bl_idname="optiblend_v123.auto_collections"; bl_label="Auto Collections"; bl_options={"REGISTER","UNDO"}
    def execute(self,context):
        count=0
        for obj in list(context.scene.objects):
            sort_object_into_optiblend_collection(context,obj); count+=1
        removed=cleanup_empty_collections()
        bump_guide(context,"guide_collections")
        set_report(context,f"Auto Collections sorted {count} objects.\nEmpty/default collections removed: {len(removed)}\nGeometry, Lights, Cameras and Helpers are now separated.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_reset_guide(bpy.types.Operator):
    bl_idname="optiblend_v123.reset_guide"; bl_label="Reset Guide"
    def execute(self,context):
        p=context.scene.optiblend_v123; p.guide_shapes=0; p.guide_materials=0; p.guide_collections=0; p.guide_lights=0; return {"FINISHED"}


class OPTIBLEND_V123_OT_status_popup(bpy.types.Operator):
    bl_idname="optiblend_v123.status_popup"; bl_label="OptiBlend Status"
    def invoke(self,context,event): return context.window_manager.invoke_props_dialog(self,width=520)
    def draw(self,context):
        p=context.scene.optiblend_v123; l=self.layout
        l.label(text="OptiBlend V1.0",icon="INFO"); l.label(text="Mode: "+p.mode); l.label(text="Snap: "+p.preview_snap_mode); l.prop(p,"high_poly_limit"); l.separator()
        for line in p.report.split("\n"): l.label(text=line)
    def execute(self,context): return {"FINISHED"}



# =============================================================================
# Advanced character / Mixamo / topology research helpers
# =============================================================================
# Adobe's current Mixamo guidance is mostly about clean, centered humanoid characters
# with no unrelated scene content. It also says the auto-rigger is for bipedal humanoids.
# Python can verify mechanical scene data, but it cannot reliably determine whether a character
# tell whether a character is "human enough" or in a good neutral pose. Those stay as
# manual checks in the report instead of pretending the add-on knows more than it does.
#
# Research references are also copied into MIXAMO_RESEARCH.md in the add-on folder.

def _safe_len(value):
    try:
        return len(value)
    except Exception:
        return 0


def mesh_topology_stats(obj):
    """Return a defensive topology summary for one mesh object."""
    result = {
        "vertices": 0,
        "edges": 0,
        "faces": 0,
        "triangles": 0,
        "quads": 0,
        "ngons": 0,
        "non_manifold_edges": None,
        "loose_vertices": None,
        "loose_edges": None,
        "components": None,
    }
    if not obj or obj.type != "MESH" or not obj.data:
        return result

    mesh = obj.data
    result["vertices"] = len(mesh.vertices)
    result["edges"] = len(mesh.edges)
    result["faces"] = len(mesh.polygons)
    for poly in mesh.polygons:
        sides = len(poly.vertices)
        if sides == 3:
            result["triangles"] += 1
        elif sides == 4:
            result["quads"] += 1
        elif sides > 4:
            result["ngons"] += 1

    # BMesh gives much better topology checks than guessing from polygon counts.
    # I skip the expensive connected-island walk on truly huge meshes because a tool
    # designed to help performance should not freeze the viewport while auditing it.
    bm = None
    try:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        result["non_manifold_edges"] = sum(1 for e in bm.edges if not e.is_manifold)
        result["loose_vertices"] = sum(1 for v in bm.verts if not v.link_edges)
        result["loose_edges"] = sum(1 for e in bm.edges if not e.link_faces)

        if len(bm.verts) <= 120000:
            visited = set()
            components = 0
            for start in bm.verts:
                if start in visited:
                    continue
                components += 1
                stack = [start]
                visited.add(start)
                while stack:
                    current = stack.pop()
                    for edge in current.link_edges:
                        other = edge.other_vert(current)
                        if other not in visited:
                            visited.add(other)
                            stack.append(other)
            result["components"] = components
    except Exception as e:
        print("OptiBlend topology audit skipped part of BMesh check:", e)
    finally:
        try:
            if bm:
                bm.free()
        except Exception:
            pass
    return result


def object_particle_summary(obj):
    legacy = 0
    modifiers = []
    geometry_nodes = []
    if not obj:
        return legacy, modifiers, geometry_nodes
    try:
        legacy = len(obj.particle_systems)
    except Exception:
        legacy = 0
    for mod in getattr(obj, "modifiers", []):
        if mod.type in {"PARTICLE_SYSTEM", "PARTICLE_INSTANCE"}:
            modifiers.append(mod.name)
        elif mod.type == "NODES":
            geometry_nodes.append(mod.name)
    return legacy, modifiers, geometry_nodes


def armature_for_object(obj):
    if not obj:
        return None
    try:
        if obj.parent and obj.parent.type == "ARMATURE":
            return obj.parent
    except Exception:
        pass
    for mod in getattr(obj, "modifiers", []):
        if mod.type == "ARMATURE" and getattr(mod, "object", None):
            return mod.object
    return None


def mixamo_mechanical_report(context, obj):
    """Create a heuristic readiness score without pretending to detect anatomy."""
    if not obj or obj.type != "MESH":
        return 0, [
            "Select one character mesh first.",
            "OptiBlend cannot run a Mixamo check without an active mesh object.",
        ]

    stats = mesh_topology_stats(obj)
    armature = armature_for_object(obj)
    armatures = [o for o in context.scene.objects if o.type == "ARMATURE"]
    legacy_particles, particle_mods, geo_nodes = object_particle_summary(obj)
    modifiers = [m for m in obj.modifiers]
    score = 100
    lines = []

    # Transforms are one of the easiest pipeline mistakes to identify automatically.
    unapplied_scale = any(abs(v - 1.0) > 0.001 for v in obj.scale)
    unapplied_rotation = any(abs(v) > 0.001 for v in obj.rotation_euler)
    if unapplied_scale or unapplied_rotation:
        score -= 12
        lines.append("WARN  Unapplied rotation/scale detected.")
    else:
        lines.append("PASS  Rotation and scale are applied.")

    centre = object_bbox_center_world(obj)
    radius = max(object_bbox_radius_world(obj), 0.001)
    centered = centre.length <= max(0.05, radius * 0.05)
    if not centered:
        score -= 10
        lines.append(f"WARN  Character centre is away from world origin ({centre.length:.3f}).")
    else:
        lines.append("PASS  Character is centred close to world origin.")

    if stats["ngons"] > 0:
        score -= min(12, 4 + stats["ngons"] // 100)
        lines.append(f"WARN  Ngons detected: {stats['ngons']}.")
    else:
        lines.append("PASS  No ngons detected.")

    if stats["non_manifold_edges"] not in {None, 0}:
        score -= 12
        lines.append(f"WARN  Non-manifold/boundary edges: {stats['non_manifold_edges']}.")
    elif stats["non_manifold_edges"] == 0:
        lines.append("PASS  Mesh manifold edge check passed.")

    if stats["loose_vertices"] not in {None, 0} or stats["loose_edges"] not in {None, 0}:
        score -= 8
        lines.append(f"WARN  Loose verts/edges: {stats['loose_vertices'] or 0}/{stats['loose_edges'] or 0}.")

    if stats["components"] and stats["components"] > 1:
        score -= min(15, 5 + stats["components"])
        lines.append(f"WARN  Disconnected mesh islands: {stats['components']}.")
    elif stats["components"] == 1:
        lines.append("PASS  Mesh is one connected island.")
    elif stats["components"] is None:
        lines.append("INFO  Connected-island check skipped on a very heavy mesh.")

    if legacy_particles or particle_mods:
        score -= 10
        lines.append(f"WARN  Particle systems/modifiers detected: {legacy_particles + len(particle_mods)}.")
    else:
        lines.append("PASS  No legacy particle systems on the character mesh.")

    if geo_nodes:
        score -= 4
        lines.append(f"INFO  Geometry Nodes modifiers: {len(geo_nodes)}. Verify export result.")

    # Unapplied modifiers are not automatically wrong, but they are worth surfacing.
    visible_mods = [m for m in modifiers if m.type != "ARMATURE"]
    if visible_mods:
        score -= min(8, len(visible_mods) * 2)
        lines.append("INFO  Non-armature modifiers: " + ", ".join(m.type for m in visible_mods[:8]))
    else:
        lines.append("PASS  No extra mesh modifiers to review.")

    if armature:
        try:
            bone_count = len(armature.data.bones)
        except Exception:
            bone_count = 0
        lines.append(f"INFO  Armature detected: {armature.name} ({bone_count} bones).")
        lines.append("INFO  Adobe documents rigged-character uploads as FBX.")
    else:
        lines.append("INFO  No armature attached: this is an auto-rig candidate.")

    if len(armatures) > 1:
        score -= 6
        lines.append(f"WARN  Multiple armatures in scene: {len(armatures)}.")

    # Adobe says unrelated scene content can interfere with auto-rigging. We do not
    # delete anything here; we tell the user to export/select only the character.
    allowed_ids = {obj.as_pointer()}
    if armature:
        allowed_ids.add(armature.as_pointer())
    extras = [o for o in context.scene.objects if o.as_pointer() not in allowed_ids and not o.hide_render]
    if extras:
        score -= min(10, len(extras))
        lines.append(f"WARN  Other visible scene objects: {len(extras)}. Export selected character only.")
    else:
        lines.append("PASS  No unrelated visible scene objects detected.")

    # A humanoid shape and neutral pose are semantic checks. I list them as manual
    # requirements because a false PASS would be worse than admitting the limit.
    lines.append("MANUAL  Confirm biped humanoid shape: clear head, body, two arms and two legs.")
    lines.append("MANUAL  Confirm a neutral/default pose with no large props, wings or tails.")
    lines.append("MANUAL  Confirm no visible gaps between body parts before upload.")

    score = max(0, min(100, int(score)))
    return score, lines


def topology_report_text(obj):
    if not obj or obj.type != "MESH":
        return "Select one mesh object first."
    s = mesh_topology_stats(obj)
    total = max(1, s["faces"])
    quad_pct = (s["quads"] / total) * 100.0
    tri_pct = (s["triangles"] / total) * 100.0
    return "\n".join([
        f"Object: {obj.name}",
        f"Vertices: {s['vertices']} | Edges: {s['edges']} | Faces: {s['faces']}",
        f"Quads: {s['quads']} ({quad_pct:.1f}%)",
        f"Triangles: {s['triangles']} ({tri_pct:.1f}%)",
        f"Ngons: {s['ngons']}",
        f"Non-manifold/boundary edges: {s['non_manifold_edges'] if s['non_manifold_edges'] is not None else 'skipped'}",
        f"Loose vertices: {s['loose_vertices'] if s['loose_vertices'] is not None else 'skipped'}",
        f"Loose edges: {s['loose_edges'] if s['loose_edges'] is not None else 'skipped'}",
        f"Connected islands: {s['components'] if s['components'] is not None else 'skipped/heavy mesh'}",
    ])


def rig_modifier_report_text(context, obj):
    if not obj or obj.type != "MESH":
        return "Select one mesh object first."
    arm = armature_for_object(obj)
    legacy, particle_mods, geo_nodes = object_particle_summary(obj)
    mods = list(obj.modifiers)
    lines = [f"Object: {obj.name}"]
    lines.append("Armature: " + (arm.name if arm else "none"))
    if arm:
        try:
            lines.append(f"Bones: {len(arm.data.bones)}")
        except Exception:
            pass
    lines.append("Modifiers: " + (", ".join(f"{m.name} [{m.type}]" for m in mods[:12]) if mods else "none"))
    lines.append(f"Legacy particle systems: {legacy}")
    lines.append("Particle modifiers: " + (", ".join(particle_mods) if particle_mods else "none"))
    lines.append("Geometry Nodes: " + (", ".join(geo_nodes) if geo_nodes else "none"))
    if len(mods) > 8:
        lines.append("WARN  Heavy modifier stack. Test deformation/export before applying anything.")
    if arm and getattr(obj, "parent", None) not in {None, arm}:
        lines.append("INFO  Character has a non-armature parent; verify export hierarchy.")
    return "\n".join(lines)



class OPTIBLEND_V123_OT_import_external(bpy.types.Operator, ImportHelper):
    bl_idname = "optiblend_v123.import_external"
    bl_label = "Import External Model"
    bl_description = "Import FBX, OBJ, glTF/GLB or STL through OptiBlend, then select and optionally organise the new objects."
    bl_options = {"REGISTER", "UNDO"}

    filename_ext = ""
    filter_glob: bpy.props.StringProperty(
        default="*.fbx;*.obj;*.gltf;*.glb;*.stl",
        options={"HIDDEN"},
    )

    def execute(self, context):
        filepath = self.filepath
        ext = os.path.splitext(filepath)[1].lower()
        before = {obj.as_pointer() for obj in bpy.data.objects}
        imported = False
        error_text = ""

        # Blender has changed some import operator names across versions. I use a
        # current operator first and keep one fallback where it is realistic. This is
        # much safer for a release build than assuming every Blender install is exact.
        try:
            if ext == ".fbx":
                bpy.ops.import_scene.fbx(filepath=filepath)
                imported = True
            elif ext == ".obj":
                try:
                    bpy.ops.wm.obj_import(filepath=filepath)
                except Exception:
                    bpy.ops.import_scene.obj(filepath=filepath)
                imported = True
            elif ext in {".gltf", ".glb"}:
                bpy.ops.import_scene.gltf(filepath=filepath)
                imported = True
            elif ext == ".stl":
                try:
                    bpy.ops.wm.stl_import(filepath=filepath)
                except Exception:
                    bpy.ops.import_mesh.stl(filepath=filepath)
                imported = True
            else:
                error_text = "Unsupported file type. Use FBX, OBJ, GLTF/GLB or STL."
        except Exception as e:
            error_text = str(e)

        if not imported:
            self.report({"ERROR"}, "Import failed: " + (error_text or "unknown import error"))
            set_report(context, "IMPORT FAILED\n" + (error_text or "Unknown import error."))
            return {"CANCELLED"}

        new_objects = [obj for obj in bpy.data.objects if obj.as_pointer() not in before]
        scene_new = [obj for obj in new_objects if context.scene.objects.get(obj.name) is obj]

        try:
            bpy.ops.object.select_all(action="DESELECT")
        except Exception:
            pass
        for obj in scene_new:
            try:
                obj.select_set(True)
            except Exception:
                pass

        active = next((o for o in scene_new if o.type == "MESH"), scene_new[0] if scene_new else None)
        if active:
            try:
                context.view_layer.objects.active = active
            except Exception:
                pass

        props = context.scene.optiblend_v123
        if props.import_auto_organize:
            for obj in scene_new:
                try:
                    sort_object_into_optiblend_collection(context, obj)
                except Exception:
                    pass
            cleanup_empty_collections()

        set_move_tool(context)

        mesh_count = sum(1 for o in scene_new if o.type == "MESH")
        poly_count = sum(len(o.data.polygons) for o in scene_new if o.type == "MESH" and o.data)
        lines = [
            "EXTERNAL IMPORT COMPLETE",
            f"File: {os.path.basename(filepath)}",
            f"Objects imported: {len(scene_new)}",
            f"Mesh objects: {mesh_count}",
        ]
        if props.import_run_scan:
            lines.append(f"Imported polygons: {poly_count}")
            if active and active.type == "MESH":
                if any(abs(v - 1.0) > 0.001 for v in active.scale):
                    lines.append("WARN  Imported active mesh has unapplied scale.")
                if len(active.data.polygons) > props.high_poly_limit:
                    lines.append("WARN  Imported active mesh is over the High Poly Limit.")
        lines.append("Move tool enabled so the import can be positioned straight away.")
        set_report(context, "\n".join(lines))
        self.report({"INFO"}, f"Imported {len(scene_new)} object(s)")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_mixamo_check(bpy.types.Operator):
    bl_idname = "optiblend_v123.mixamo_check"
    bl_label = "Mixamo Readiness Check"
    bl_description = "Advanced heuristic check based on Adobe Mixamo guidance: transforms, scene content, topology, particles, modifiers, centering and rig state."

    def _run(self, context):
        props = context.scene.optiblend_v123
        obj = context.active_object
        score, lines = mixamo_mechanical_report(context, obj)
        props.mixamo_last_score = score
        props.mixamo_last_report = "\n".join(lines)
        set_report(context, f"MIXAMO READINESS: {score}/100\n" + props.mixamo_last_report)

    def invoke(self, context, event):
        self._run(context)
        return context.window_manager.invoke_props_dialog(self, width=650)

    def execute(self, context):
        self._run(context)
        return {"FINISHED"}

    def draw(self, context):
        p = context.scene.optiblend_v123
        layout = self.layout
        row = layout.row()
        row.scale_y = 1.35
        row.label(text=f"Mixamo Readiness (heuristic): {p.mixamo_last_score}/100", icon="ARMATURE_DATA")
        box = layout.box()
        for line in p.mixamo_last_report.split("\n"):
            icon = "CHECKMARK" if line.startswith("PASS") else "ERROR" if line.startswith("WARN") else "INFO"
            box.label(text=line, icon=icon)
        layout.separator()
        layout.label(text="Manual checks cannot be automated: humanoid proportions, neutral pose and large props.", icon="INFO")
        layout.label(text="Adobe documents Mixamo auto-rig as biped humanoid only; rigged-character upload uses FBX.")


class OPTIBLEND_V123_OT_topology_audit(bpy.types.Operator):
    bl_idname = "optiblend_v123.topology_audit"
    bl_label = "Topology Audit"
    bl_description = "Check quads, triangles, ngons, non-manifold edges, loose geometry and connected mesh islands."

    def _run(self, context):
        p = context.scene.optiblend_v123
        p.topology_last_report = topology_report_text(context.active_object)
        set_report(context, "TOPOLOGY AUDIT\n" + p.topology_last_report)

    def invoke(self, context, event):
        self._run(context)
        return context.window_manager.invoke_props_dialog(self, width=560)

    def execute(self, context):
        self._run(context)
        return {"FINISHED"}

    def draw(self, context):
        p = context.scene.optiblend_v123
        layout = self.layout
        layout.label(text="Topology Audit", icon="MESH_DATA")
        box = layout.box()
        for line in p.topology_last_report.split("\n"):
            box.label(text=line)
        layout.separator()
        layout.operator("optiblend_v123.retopo_quads", text="Quad Retopo (QuadriFlow)", icon="MODIFIER")
        layout.operator("optiblend_v123.retopo_triangles", text="Add Triangulate Modifier", icon="MODIFIER")
        layout.operator("optiblend_v123.subdivision_ready", text="Subdivision-Ready Setup", icon="MOD_SUBSURF")


class OPTIBLEND_V123_OT_rig_modifier_audit(bpy.types.Operator):
    bl_idname = "optiblend_v123.rig_modifier_audit"
    bl_label = "Rig / Modifier / Particle Audit"
    bl_description = "Check armature state, modifiers, legacy particle systems and Geometry Nodes before animation/export."

    def _run(self, context):
        p = context.scene.optiblend_v123
        p.rig_last_report = rig_modifier_report_text(context, context.active_object)
        set_report(context, "RIG / MODIFIER / PARTICLE AUDIT\n" + p.rig_last_report)

    def invoke(self, context, event):
        self._run(context)
        return context.window_manager.invoke_props_dialog(self, width=600)

    def execute(self, context):
        self._run(context)
        return {"FINISHED"}

    def draw(self, context):
        p = context.scene.optiblend_v123
        layout = self.layout
        layout.label(text="Rig / Modifier / Particle Audit", icon="ARMATURE_DATA")
        box = layout.box()
        for line in p.rig_last_report.split("\n"):
            box.label(text=line)
        layout.separator()
        layout.menu("OPTIBLEND_V123_MT_modifiers", text="Open Modifier Tools", icon="MODIFIER")
        layout.operator("optiblend_v123.pipeline_export_prep", text="Run Export Prep", icon="EXPORT")


class OPTIBLEND_V123_OT_mixamo_research(bpy.types.Operator):
    bl_idname = "optiblend_v123.mixamo_research"
    bl_label = "Mixamo Research Notes"
    bl_description = "Show the researched Mixamo conditions used by the readiness checker."

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=610)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Adobe Mixamo research used by OptiBlend", icon="INFO")
        for line in (
            "Auto-rigger is for bipedal humanoid characters.",
            "Character should be in a neutral/default pose.",
            "Large extra appendages/props can stop auto-rigging.",
            "Character should be centred at the world origin.",
            "Clean/error-free meshes improve rigging reliability.",
            "Unrelated scene content should not be included in the upload.",
            "Mixamo upload formats documented by Adobe: FBX, OBJ and ZIP.",
            "Rigged-character uploads are documented as FBX.",
        ):
            layout.label(text=line)
        layout.separator()
        layout.label(text="Full links and research notes are in MIXAMO_RESEARCH.md.", icon="TEXT")

    def execute(self, context):
        return {"FINISHED"}


class OPTIBLEND_V123_OT_performance_audit(bpy.types.Operator):
    bl_idname="optiblend_v123.performance_audit"; bl_label="Performance Audit"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: audit heavy scenes, polygon load and object counts."
    def execute(self,context):
        meshes=[o for o in context.scene.objects if o.type=="MESH"]
        polys=sum(len(o.data.polygons) for o in meshes)
        high=[o.name for o in meshes if len(o.data.polygons)>context.scene.optiblend_v123.high_poly_limit][:10]
        set_report(context, "PERFORMANCE AUDIT\n" + f"Objects: {len(context.scene.objects)}\nMeshes: {len(meshes)}\nPolygons: {polys}\nHigh-poly examples: {', '.join(high) if high else 'none'}\nSuggestion: split scenes, use collections and reduce heavy live viewport loads.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_pipeline_export_prep(bpy.types.Operator):
    bl_idname="optiblend_v123.pipeline_export_prep"; bl_label="FBX / Export Prep"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: reduce common export issues like unapplied transforms, scale mismatches and missing animation prep reminders."
    def execute(self,context):
        bad=[]
        for obj in context.selected_objects or context.scene.objects:
            if obj.type in {"MESH","ARMATURE","EMPTY","CAMERA","LIGHT"}:
                scale_problem = any(abs(v-1.0)>0.001 for v in obj.scale)
                rot_problem = any(abs(v)>0.001 for v in getattr(obj,'rotation_euler',(0,0,0)))
                if scale_problem or rot_problem:
                    bad.append(obj.name)
        set_report(context, "FBX / EXPORT PREP\n" + (f"Objects needing transform cleanup: {', '.join(bad[:12])}" if bad else "Transforms look clean for the current selection/scene.") + "\nReminder: verify units, bake animation when needed and test one export before pipeline batch work.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_team_collections_setup(bpy.types.Operator):
    bl_idname="optiblend_v123.team_collections_setup"; bl_label="Team Collection Blocks"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: create clearer collection blocks for multi-artist scenes."
    def execute(self,context):
        names=["01_Geo","02_Lights","03_Cameras","04_Exports","05_Reference","06_Helpers"]
        made=[]
        root=context.scene.collection
        for name in names:
            col=bpy.data.collections.get(name)
            if not col:
                col=bpy.data.collections.new(name)
                root.children.link(col)
                made.append(name)
        set_report(context, "TEAM COLLECTION BLOCKS\nCreated: " + (', '.join(made) if made else 'none') + "\nUse these blocks to separate artist tasks and reduce shared-scene confusion.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_open_uv_helper(bpy.types.Operator):
    bl_idname="optiblend_v123.open_uv_helper"; bl_label="Open UV Helper"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: switch one area to a UV-style editor for unwrap work."
    def execute(self,context):
        changed=False
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type in {"OUTLINER","PROPERTIES","IMAGE_EDITOR"}:
                    try:
                        area.type="IMAGE_EDITOR"
                        try: area.ui_type='UV'
                        except Exception: pass
                        changed=True
                        raise StopIteration
                    except StopIteration:
                        break
                    except Exception:
                        pass
            else:
                continue
            break
        set_report(context, "UV HELPER\n" + ("A side area was switched to UV work." if changed else "Could not switch a side area to UV in this layout."))
        return {"FINISHED"}


class OPTIBLEND_V123_OT_weighted_normals_fix(bpy.types.Operator):
    bl_idname="optiblend_v123.weighted_normals_fix"; bl_label="Weighted Normals Fix"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: improve hard-surface shading with smooth shading and a Weighted Normal modifier."
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!="MESH":
            self.report({"WARNING"},"Select a mesh first")
            return {"CANCELLED"}
        try:
            for poly in obj.data.polygons: poly.use_smooth=True
        except Exception:
            pass
        mod = obj.modifiers.get("OptiBlend Weighted Normal") or obj.modifiers.new("OptiBlend Weighted Normal","WEIGHTED_NORMAL")
        try:
            mod.keep_sharp=True
            mod.weight=50
        except Exception:
            pass
        set_report(context, f"WEIGHTED NORMALS\nApplied smooth shading and Weighted Normal to {obj.name}.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_modifier_stack_helper(bpy.types.Operator):
    bl_idname="optiblend_v123.modifier_stack_helper"; bl_label="Modifier Stack Helper"; bl_options={"REGISTER","UNDO"}
    bl_description="Advanced helper: provide a safer starting stack for non-destructive modelling."
    def execute(self,context):
        obj=context.active_object
        if not obj or obj.type!="MESH":
            self.report({"WARNING"},"Select a mesh first")
            return {"CANCELLED"}
        needed=[("Mirror","MIRROR"),("Bevel","BEVEL"),("Subdivision","SUBSURF"),("Weighted Normal","WEIGHTED_NORMAL")]
        added=[]
        for name, kind in needed:
            if not any(m.type==kind for m in obj.modifiers):
                m=obj.modifiers.new("OptiBlend " + name, kind)
                added.append(name)
                try:
                    if kind=="BEVEL":
                        m.limit_method='ANGLE'; m.segments=2
                    elif kind=="SUBSURF":
                        m.levels=2; m.render_levels=2
                    elif kind=="MIRROR":
                        m.use_axis[0]=True; m.use_clip=True
                    elif kind=="WEIGHTED_NORMAL":
                        m.keep_sharp=True
                except Exception:
                    pass
        set_report(context, "MODIFIER STACK HELPER\nAdded: " + (', '.join(added) if added else 'none, stack already exists') + "\nThis gives Advanced mode a clearer non-destructive starting point.")
        return {"FINISHED"}


class OPTIBLEND_V123_OT_toggle_test_lab(bpy.types.Operator):
    bl_idname="optiblend_v123.toggle_test_lab"; bl_label="Toggle Test Lab"
    bl_description="Open the OptiBlend Test Lab with L and keep the header button available for development testing."
    def execute(self,context):
        p=context.scene.optiblend_v123
        p.developer_test_menu=True
        try:
            bpy.ops.wm.call_menu(name="OPTIBLEND_V123_MT_test_lab")
        except Exception:
            pass
        set_report(context, "TEST LAB\nL pressed. Test Lab opened for development checks.")
        return {"FINISHED"}


# =============================================================================
# TEST LAB - deliberately separate from the normal user workflow
# =============================================================================
# Each major mechanic can be tested independently without crowding Beginner mode.
class OPTIBLEND_V123_MT_test_lab(bpy.types.Menu):
    bl_idname="OPTIBLEND_V123_MT_test_lab"; bl_label="OptiBlend Test Lab"
    def draw(self,context):
        p=context.scene.optiblend_v123; l=self.layout
        l.label(text="Mechanic Testing  [L]",icon="TOOL_SETTINGS")
        l.operator("optiblend_v123.test_workspaces",text="Test Workspace Lock",icon="FILE_FOLDER")
        l.operator("optiblend_v123.test_shape_bar",text="Test Shape Bar + Scroll",icon="MESH_CUBE")
        l.operator("optiblend_v123.test_material_groups",text="Build / Test Material Groups",icon="NODETREE")
        l.operator("optiblend_v123.test_collision",text="Toggle Smart Placement",icon="SNAP_ON")
        l.operator("optiblend_v123.test_snap_controls",text="Test Centre + Rotation Snap",icon="ORIENTATION_GLOBAL")
        l.operator("optiblend_v123.test_collections",text="Test Auto Collections",icon="OUTLINER_COLLECTION")
        l.operator("optiblend_v123.test_beginner_ui",text="Toggle Beginner Declutter",icon="WINDOW")
        l.operator("optiblend_v123.test_glow",text="Toggle UI Glow",icon="LIGHT")
        l.operator("optiblend_v123.test_final_helpers",text="Test XYZ + Edit Snap + Compositor",icon="CHECKMARK")
        l.separator()
        l.label(text="Final V1 Pipeline Tests", icon="ARMATURE_DATA")
        l.operator("optiblend_v123.import_external", text="Test External Import", icon="IMPORT")
        l.operator("optiblend_v123.mixamo_check", text="Test Mixamo Readiness", icon="ARMATURE_DATA")
        l.operator("optiblend_v123.topology_audit", text="Test Topology Audit", icon="MESH_DATA")
        l.operator("optiblend_v123.rig_modifier_audit", text="Test Rig / Modifiers / Particles", icon="MODIFIER")
        l.separator(); l.prop(p,"developer_test_menu",text="Keep Test Button In Header")


class OPTIBLEND_V123_OT_test_workspaces(bpy.types.Operator):
    bl_idname="optiblend_v123.test_workspaces"; bl_label="Test Workspaces"
    def execute(self,context):
        apply_workspace_set(context,wanted_workspaces_for_mode(context.scene.optiblend_v123.mode)); names=", ".join(ws.name for ws in bpy.data.workspaces); set_report(context,"WORKSPACE TEST\nCurrent tabs: "+names); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_shape_bar(bpy.types.Operator):
    bl_idname="optiblend_v123.test_shape_bar"; bl_label="Test Shape Bar"
    def execute(self,context):
        p=context.scene.optiblend_v123; p.asset_bar_mode="SHAPES"; p.asset_bar_visible=True; p.asset_scroll_target=min(4,max(0,len(SHAPES)-asset_visible_capacity(context))); ensure_asset_bar_listener(context); set_report(context,"SHAPE BAR TEST\nBar opened and scroll target moved to test animation."); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_material_groups(bpy.types.Operator):
    bl_idname="optiblend_v123.test_material_groups"; bl_label="Test Material Groups"
    def execute(self,context):
        ok=0; failed=[]
        for key in MATERIAL_LIBRARY:
            try:
                if build_material_group(key): ok+=1
            except Exception as e:
                failed.append(key)
        set_report(context,f"MATERIAL GROUP TEST\nBuilt/found: {ok}/{len(MATERIAL_LIBRARY)}\nFailed: {', '.join(failed) if failed else 'none'}"); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_collision(bpy.types.Operator):
    bl_idname="optiblend_v123.test_collision"; bl_label="Test Smart Placement"
    def execute(self,context):
        p=context.scene.optiblend_v123; p.smart_object_interaction=not p.smart_object_interaction; set_report(context,"SMART PLACEMENT TEST\nSmart object interaction: "+str(p.smart_object_interaction)); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_snap_controls(bpy.types.Operator):
    bl_idname="optiblend_v123.test_snap_controls"
    bl_label="Test Centre + Rotation Snap"

    def execute(self,context):
        p=context.scene.optiblend_v123
        p.asset_bar_mode="SHAPES"
        p.asset_bar_visible=True
        p.center_snap_enabled=True
        p.align_preview_to_surface=True
        ensure_asset_bar_listener(context)
        set_report(
            context,
            "SNAP CONTROL TEST\nDrag a shape, use the wheel to rotate.\nHold Ctrl over another mesh for centre snap.\nR resets rotation; X/Y/Z changes free axis."
        )
        tag_redraw(context)
        return {"FINISHED"}


class OPTIBLEND_V123_OT_test_collections(bpy.types.Operator):
    bl_idname="optiblend_v123.test_collections"; bl_label="Test Collections"
    def execute(self,context): bpy.ops.optiblend_v123.auto_collections(); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_beginner_ui(bpy.types.Operator):
    bl_idname="optiblend_v123.test_beginner_ui"; bl_label="Test Beginner UI"
    def execute(self,context):
        p=context.scene.optiblend_v123; p.simplify_beginner_ui=not p.simplify_beginner_ui; simplify_beginner_ui(context,p.mode=="BEGINNER"); set_report(context,"BEGINNER UI TEST\nSimplified UI: "+str(p.simplify_beginner_ui)); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_glow(bpy.types.Operator):
    bl_idname="optiblend_v123.test_glow"; bl_label="Test Glow"
    def execute(self,context):
        p=context.scene.optiblend_v123; p.ui_glow_enabled=not p.ui_glow_enabled; tag_redraw(context); set_report(context,"UI GLOW TEST\nGlow: "+str(p.ui_glow_enabled)); return {"FINISHED"}


class OPTIBLEND_V123_OT_test_final_helpers(bpy.types.Operator):
    bl_idname="optiblend_v123.test_final_helpers"; bl_label="Test Final Helpers"
    bl_description="Turn on the final centred XYZ, edit-mode snapping and compositor glow helpers together for testing."
    def execute(self,context):
        p=context.scene.optiblend_v123
        p.object_xyz_helper=True; p.edit_mode_smart_snap=True
        ensure_compositor_glare(context.scene,p.glare_mode)
        apply_blender_snapping(context); tag_redraw(context)
        set_report(context,"FINAL HELPER TEST\nCentred XYZ: ON\nEdit smart snap: ON\nCompositor glare: configured")
        return {"FINISHED"}


# =============================================================================
# startup / keymap / registration
# Reload testing matters here. Blender add-ons can appear fine on the first install but
# leave handlers/keymaps behind after reload, so every new modal or draw handler needs
# a matching cleanup path in unregister().
# =============================================================================
def boot_addon():
    try:
        if bpy.context.scene and hasattr(bpy.context.scene,"optiblend_v123"):
            apply_mode(bpy.context,"BEGINNER")
            p=bpy.context.scene.optiblend_v123; p.asset_bar_visible=True; p.asset_bar_mode="SHAPES"
            ensure_asset_bar_listener(bpy.context)
            queue_workspace_guard()
    except Exception as e:
        print("OptiBlend V1.0 boot skipped:",e)
    return None


def register_keymap():
    kc=bpy.context.window_manager.keyconfigs.addon
    if not kc: return
    km=kc.keymaps.new(name="3D View",space_type="VIEW_3D")
    kmi=km.keymap_items.new("optiblend_v123.fancy_wheel",type="Q",value="PRESS")
    KEYMAPS.append((km,kmi))
    # L is just for my testing flow. It is intentionally separate from the user-facing
    # Helper so development checks do not clutter the normal beginner UI.
    kmi=km.keymap_items.new("optiblend_v123.toggle_test_lab",type="L",value="PRESS")
    KEYMAPS.append((km,kmi))


def unregister_keymap():
    for km,kmi in KEYMAPS:
        try: km.keymap_items.remove(kmi)
        except Exception: pass
    KEYMAPS.clear()


classes=(
    OPTIBLEND_V123_Props,
    OPTIBLEND_V123_OT_asset_bar_listener,
    OPTIBLEND_V123_OT_fancy_wheel,
    OPTIBLEND_V123_MT_mode,
    OPTIBLEND_V123_MT_lights,
    OPTIBLEND_V123_MT_modifiers,
    OPTIBLEND_V123_MT_retopology,
    OPTIBLEND_V123_MT_compositor,
    OPTIBLEND_V123_MT_render,
    OPTIBLEND_V123_MT_tools,
    OPTIBLEND_V123_MT_advanced_pipeline,
    OPTIBLEND_V123_MT_rig_check,
    OPTIBLEND_V123_MT_import,
    OPTIBLEND_V123_MT_guide,
    OPTIBLEND_V123_MT_test_lab,
    OPTIBLEND_V123_PT_advanced_pipeline,
    OPTIBLEND_V123_OT_show_asset_bar,
    OPTIBLEND_V123_OT_mode_beginner,
    OPTIBLEND_V123_OT_mode_intermediate,
    OPTIBLEND_V123_OT_mode_advanced,
    OPTIBLEND_V123_OT_reapply_mode,
    OPTIBLEND_V123_OT_colour_wheel,
    OPTIBLEND_V123_OT_default_lights,
    OPTIBLEND_V123_OT_add_modifier,
    OPTIBLEND_V123_OT_retopo_quads,
    OPTIBLEND_V123_OT_retopo_triangles,
    OPTIBLEND_V123_OT_subdivision_ready,
    OPTIBLEND_V123_OT_camera_create_select,
    OPTIBLEND_V123_OT_camera_view,
    OPTIBLEND_V123_OT_camera_align_view,
    OPTIBLEND_V123_OT_enable_glare,
    OPTIBLEND_V123_OT_disable_glare,
    OPTIBLEND_V123_OT_licenses,
    OPTIBLEND_V123_OT_render_image,
    OPTIBLEND_V123_OT_render_video,
    OPTIBLEND_V123_OT_scan_scene,
    OPTIBLEND_V123_OT_clean_data,
    OPTIBLEND_V123_OT_auto_collections,
    OPTIBLEND_V123_OT_reset_guide,
    OPTIBLEND_V123_OT_status_popup,
    OPTIBLEND_V123_OT_import_external,
    OPTIBLEND_V123_OT_mixamo_check,
    OPTIBLEND_V123_OT_topology_audit,
    OPTIBLEND_V123_OT_rig_modifier_audit,
    OPTIBLEND_V123_OT_mixamo_research,
    OPTIBLEND_V123_OT_performance_audit,
    OPTIBLEND_V123_OT_pipeline_export_prep,
    OPTIBLEND_V123_OT_team_collections_setup,
    OPTIBLEND_V123_OT_open_uv_helper,
    OPTIBLEND_V123_OT_weighted_normals_fix,
    OPTIBLEND_V123_OT_modifier_stack_helper,
    OPTIBLEND_V123_OT_toggle_test_lab,
    OPTIBLEND_V123_OT_test_workspaces,
    OPTIBLEND_V123_OT_test_shape_bar,
    OPTIBLEND_V123_OT_test_material_groups,
    OPTIBLEND_V123_OT_test_collision,
    OPTIBLEND_V123_OT_test_snap_controls,
    OPTIBLEND_V123_OT_test_collections,
    OPTIBLEND_V123_OT_test_beginner_ui,
    OPTIBLEND_V123_OT_test_glow,
    OPTIBLEND_V123_OT_test_final_helpers,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.optiblend_v123=bpy.props.PointerProperty(type=OPTIBLEND_V123_Props)
    try:
        bpy.types.VIEW3D_HT_header.append(draw_header_tabs)
    except Exception as e:
        print("OptiBlend header could not register:",e)
    enable_asset_bar_draw(); enable_xyz_helper_draw(); register_keymap()
    try:
        if not bpy.app.timers.is_registered(mode_watch_timer):
            bpy.app.timers.register(mode_watch_timer,first_interval=0.5,persistent=True)
    except Exception:
        pass
    try:
        bpy.app.timers.register(boot_addon,first_interval=0.65)
    except Exception:
        pass
    print("OptiBlend V1.0 registered.")


def unregister():
    global ASSET_BAR_RUNNING
    unregister_keymap(); disable_asset_bar_draw(); disable_xyz_helper_draw(); remove_preview(); ASSET_BAR_RUNNING=False; reset_drag()
    try:
        if bpy.app.timers.is_registered(mode_watch_timer): bpy.app.timers.unregister(mode_watch_timer)
    except Exception:
        pass
    try:
        bpy.types.VIEW3D_HT_header.remove(draw_header_tabs)
    except Exception:
        pass
    try:
        if bpy.context.scene and hasattr(bpy.context.scene,"optiblend_v123"):
            simplify_beginner_ui(bpy.context,False)
    except Exception:
        pass
    if hasattr(bpy.types.Scene,"optiblend_v123"):
        del bpy.types.Scene.optiblend_v123
    for cls in reversed(classes):
        try: bpy.utils.unregister_class(cls)
        except Exception: pass
    print("OptiBlend V1.0 unregistered.")


if __name__=="__main__":
    register()
