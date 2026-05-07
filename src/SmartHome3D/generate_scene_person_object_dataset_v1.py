from ursina import *
from pathlib import Path
from panda3d.core import Filename, Point2, Point3
from direct.actor.Actor import Actor
import random
import math
import cv2

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

ASSETS_PATH = PROJECT_ROOT / "assets"
MODELS_GLB = ASSETS_PATH / "models_glb"
CHARACTERS_PATH = ASSETS_PATH / "characters" / "exported"

DATASET_ROOT = PROJECT_ROOT / "datasets" / "smart_home_scene_v1"
IMAGE_DIR = DATASET_ROOT / "images" / "preview"
LABEL_DIR = DATASET_ROOT / "labels" / "preview"
PREVIEW_BOX_DIR = DATASET_ROOT / "images" / "preview_boxes"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
LABEL_DIR.mkdir(parents=True, exist_ok=True)
PREVIEW_BOX_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# CLASSES
# --------------------------------------------------

CLASS_MAP = {
    "person": 0,
    "couch": 1,
    "chair": 2,
    "table": 3,
    "bed": 4,
    "sink": 5,
    "toilet": 6,
    "bathtub": 7,
    "fridge": 8,
    "oven": 9,
    "door": 10,
    "lamp": 11,
    "plant": 12,
    "cabinet": 13,
    "drawer": 14,
}

# --------------------------------------------------
# APP
# --------------------------------------------------

IMAGE_SIZE = 960
PREVIEW_COUNT = 500

app = Ursina(borderless=False)
window.size = (IMAGE_SIZE, IMAGE_SIZE)
window.color = color.rgb(215, 225, 235)
application.asset_folder = Path(__file__).resolve().parent

# --------------------------------------------------
# LIGHTING
# --------------------------------------------------

sun = DirectionalLight()
sun.look_at(Vec3(1, -1, -1))
sun.color = color.rgba(235, 235, 235, 1)

ambient = AmbientLight()
ambient.color = color.rgba(80, 80, 80, 0.35)

# --------------------------------------------------
# SCENE BASICS
# --------------------------------------------------

floor_texture = load_texture("floor_concrete.jpg")
wood_texture = load_texture("wood_wall.jpg")

ground = Entity(
    model="plane",
    scale=(30, 1, 30),
    texture=floor_texture,
    texture_scale=(8, 8),
    color=color.white,
)

back_wall = Entity(
    model="cube",
    position=(0, 1.5, 9),
    scale=(22, 3, 0.25),
    texture=wood_texture,
    texture_scale=(4, 2),
    color=color.white,
)

side_wall = Entity(
    model="cube",
    position=(-11, 1.5, 0),
    scale=(0.25, 3, 18),
    texture=wood_texture,
    texture_scale=(2, 2),
    color=color.white,
)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

tracked = []


def find_asset_path(base_name):
    path = MODELS_GLB / f"{base_name}.glb"
    if path.exists():
        return path
    return None


def load_static_model(
    base_name,
    class_name,
    position=(0, 0, 0),
    rotation=(0, 0, 0),
    target_size=1.0,
    tint=None,
):
    asset_path = find_asset_path(base_name)

    if asset_path is None:
        print("[SKIP] missing model:", base_name)
        return None

    wrapper = Entity(position=position, rotation=rotation)

    panda_path = Filename.from_os_specific(str(asset_path))
    node = app.loader.loadModel(panda_path)
    node.reparentTo(wrapper)
    node.setTwoSided(True)
    node.setShaderAuto()

    if tint is not None:
        r = tint[0] if tint[0] <= 1.0 else tint[0] / 255.0
        g = tint[1] if tint[1] <= 1.0 else tint[1] / 255.0
        b = tint[2] if tint[2] <= 1.0 else tint[2] / 255.0
        node.setColorScale(r, g, b, 1.0)

    bounds = node.getTightBounds()
    if bounds and bounds[0] is not None and bounds[1] is not None:
        min_b, max_b = bounds

        size_x = max_b.x - min_b.x
        size_y = max_b.y - min_b.y
        size_z = max_b.z - min_b.z
        max_dim = max(size_x, size_y, size_z, 0.0001)

        uniform_scale = target_size / max_dim
        node.setScale(uniform_scale)

        min_b, max_b = node.getTightBounds()
        center_x = (min_b.x + max_b.x) / 2
        center_z = (min_b.z + max_b.z) / 2
        node.setPos(-center_x, -min_b.y, -center_z)

    wrapper.model_node = node
    wrapper.class_name = class_name
    wrapper.asset_name = base_name

    tracked.append(wrapper)
    print(f"[MODEL] {base_name} -> {class_name}")

    return wrapper


def load_actor(name_prefix, class_name, position, target_size=1.8):
    idle_path = CHARACTERS_PATH / f"{name_prefix}_idle.glb"
    sit_path = CHARACTERS_PATH / f"{name_prefix}_sit_idle.glb"
    sleep_path = CHARACTERS_PATH / f"{name_prefix}_sleep_idle.glb"
    walk_path = CHARACTERS_PATH / f"{name_prefix}_walk.glb"

    idle = Filename.from_os_specific(str(idle_path.resolve())).getFullpath()
    sit = Filename.from_os_specific(str(sit_path.resolve())).getFullpath()
    sleep = Filename.from_os_specific(str(sleep_path.resolve())).getFullpath()
    walk = Filename.from_os_specific(str(walk_path.resolve())).getFullpath()

    root = Entity(position=position)

    actor = Actor(
        idle,
        {
            "idle": idle,
            "sit_idle": sit,
            "sleep_idle": sleep,
            "walk": walk,
        }
    )

    actor.reparentTo(root)

    bounds = actor.getTightBounds()
    if bounds and bounds[0] is not None and bounds[1] is not None:
        min_b, max_b = bounds

        size_x = max_b.x - min_b.x
        size_y = max_b.y - min_b.y
        size_z = max_b.z - min_b.z
        max_dim = max(size_x, size_y, size_z, 0.0001)

        uniform_scale = target_size / max_dim
        actor.setScale(uniform_scale)

        min_b, max_b = actor.getTightBounds()
        center_x = (min_b.x + max_b.x) / 2
        center_z = (min_b.z + max_b.z) / 2
        actor.setPos(-center_x, -min_b.y, -center_z)

    root.actor_node = actor
    root.class_name = class_name
    root.asset_name = name_prefix

    tracked.append(root)

    return root


def set_actor_pose(actor_root, pose):
    actor = actor_root.actor_node

    if pose in actor.getAnimNames():
        actor.loop(pose)


def bbox_from_entity(entity):
    node = entity.actor_node if hasattr(entity, "actor_node") else entity.model_node

    bounds = node.getTightBounds(app.render)
    if not bounds or bounds[0] is None or bounds[1] is None:
        return None

    min_b, max_b = bounds

    corners = [
        Point3(min_b.x, min_b.y, min_b.z),
        Point3(min_b.x, min_b.y, max_b.z),
        Point3(min_b.x, max_b.y, min_b.z),
        Point3(min_b.x, max_b.y, max_b.z),
        Point3(max_b.x, min_b.y, min_b.z),
        Point3(max_b.x, min_b.y, max_b.z),
        Point3(max_b.x, max_b.y, min_b.z),
        Point3(max_b.x, max_b.y, max_b.z),
    ]

    xs = []
    ys = []

    for p_world in corners:
        p_cam = app.camera.getRelativePoint(app.render, p_world)

        p2d = Point2()
        if not app.camLens.project(p_cam, p2d):
            continue

        x = (p2d.x + 1) / 2
        y = 1 - ((p2d.y + 1) / 2)

        xs.append(x)
        ys.append(y)

    if len(xs) < 2 or len(ys) < 2:
        return None

    x1 = max(0.0, min(xs))
    y1 = max(0.0, min(ys))
    x2 = min(1.0, max(xs))
    y2 = min(1.0, max(ys))

    w = x2 - x1
    h = y2 - y1

    if w <= 0.02 or h <= 0.02:
        return None

    xc = (x1 + x2) / 2
    yc = (y1 + y2) / 2

    return x1, y1, x2, y2, xc, yc, w, h


def save_labels(label_path):
    lines = []
    preview_boxes = []

    for entity in tracked:
        if not entity.enabled:
            continue

        bbox = bbox_from_entity(entity)
        if bbox is None:
            continue

        x1, y1, x2, y2, xc, yc, w, h = bbox

        class_name = entity.class_name
        class_id = CLASS_MAP[class_name]

        lines.append(f"{class_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}")
        preview_boxes.append((class_name, x1, y1, x2, y2))

    with open(label_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return preview_boxes


def draw_preview_boxes(image_path, output_path, boxes):
    img = cv2.imread(str(image_path))

    if img is None:
        print("[WARN] could not read image:", image_path)
        return

    h, w = img.shape[:2]

    for class_name, x1, y1, x2, y2 in boxes:
        px1 = int(x1 * w)
        py1 = int(y1 * h)
        px2 = int(x2 * w)
        py2 = int(y2 * h)

        cv2.rectangle(img, (px1, py1), (px2, py2), (0, 180, 255), 2)
        cv2.putText(
            img,
            class_name,
            (px1, max(20, py1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 180, 255),
            2
        )

    cv2.imwrite(str(output_path), img)


def render_image(image_path):
    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()

    panda_path = Filename.from_os_specific(str(image_path))

    app.screenshot(
        namePrefix=str(panda_path),
        defaultFilename=False,
    )


def set_camera_near_focus(focus, mode="default"):
    if mode == "kitchen":
        height = random.choice([5.2, 5.6, 6.0])
        distance = random.choice([8.0, 8.8, 9.5])
        look_height = random.choice([1.0, 1.2, 1.4])
        yaw = random.choice([-20, -12, 0, 12, 20])

    elif mode == "bedroom":
        height = random.choice([4.8, 5.2, 5.6])
        distance = random.choice([8.2, 8.8, 9.4])
        look_height = random.choice([1.0, 1.2, 1.4])
        yaw = random.choice([-25, -15, 15, 25])

    elif mode == "bathroom":
        height = random.choice([4.6, 5.0, 5.4])
        distance = random.choice([6.8, 7.5, 8.2])
        look_height = random.choice([1.0, 1.2, 1.4])
        yaw = random.choice([-18, -8, 0, 8, 18])

    else:
        height = random.choice([5.0, 5.3, 5.6])
        distance = random.choice([8.5, 9.0, 9.5])
        look_height = random.choice([1.1, 1.3, 1.5])
        yaw = random.choice([-15, -8, 0, 8, 15])

    rad = math.radians(yaw)

    cam_x = focus.x + math.sin(rad) * 2.4
    cam_z = focus.z - distance
    cam_y = height

    camera.position = Vec3(cam_x, cam_y, cam_z)
    camera.look_at(Vec3(focus.x, look_height, focus.z))


def hide_all_tracked():
    for e in tracked:
        e.enabled = False


# --------------------------------------------------
# LOAD TARGET OBJECTS
# --------------------------------------------------

# Living room
living_couch = load_static_model("Couch_Large2", "couch", (-4.7, 0, 1.8), (0, 180, 0), 3.2, color.rgb(125, 100, 85))
living_table = load_static_model("Table_RoundSmall", "table", (-5.0, 0, 4.6), (0, 0, 0), 1.3, color.hex("#D8B08C"))
living_plant = load_static_model("Houseplant_1", "plant", (-5.2, 0, 7.8), (0, 270, 0), 1.3, color.rgb(80, 145, 85))
living_lamp = load_static_model("Light_Stand1", "lamp", (-9.3, 0, 2.2), (0, 0, 0), 1.6, color.rgb(210, 190, 120))

# Kitchen
kitchen_table = load_static_model("Table_RoundSmall", "table", (-6.6, 0, -3.55), (0, 0, 0), 2.0, color.hex("#D8B08C"))
kitchen_chair_1 = load_static_model("Chair_1", "chair", (-6.6, 0, -2.1), (0, 0, 0), 1.2, color.rgb(150, 105, 70))
kitchen_chair_2 = load_static_model("Chair_1", "chair", (-6.6, 0, -4.75), (0, 180, 0), 1.2, color.rgb(150, 105, 70))
fridge = load_static_model("Kitchen_Fridge", "fridge", (-9.85, 0, -2.15), (0, 0, 0), 3.0, color.hex("#591C21"))
kitchen_sink = load_static_model("Kitchen_Sink", "sink", (-8.65, 0.88, -7.25), (0, 180, 0), 1.25, color.rgb(170, 180, 185))
cabinet = load_static_model("Kitchen_Cabinet1", "cabinet", (-6.2, 0, -7.25), (0, 180, 0), 1.55, color.rgb(160, 115, 70))
drawer = load_static_model("Kitchen_2Drawers", "drawer", (-4.2, 0, -7.25), (0, 180, 0), 1.5, color.rgb(175, 130, 80))

oven = Entity(model="cube", position=(-10.25, 0.94, -4.35), scale=(0.95, 0.04, 2.25), color=color.black)
oven.class_name = "oven"
oven.asset_name = "Kitchen_Oven_Cube"
oven.model_node = oven
tracked.append(oven)

# Bedroom
bed_king = load_static_model("Bed_King", "bed", (7.1, 0, 5.4), (0, 180, 0), 3.2, color.rgb(210, 205, 195))
bed_single = load_static_model("Bed_Single", "bed", (4.9, 0, 5.7), (0, 180, 0), 2.3, color.rgb(205, 200, 190))
bed_lamp = load_static_model("Light_Stand2", "lamp", (10.4, 0, 4.0), (0, 0, 0), 1.85, color.rgb(220, 200, 140))
bed_drawer = load_static_model("Drawer_2", "drawer", (10.3, 0, 8.0), (0, 270, 0), 1.5, color.rgb(120, 88, 60))

# Bathroom
bath_sink = load_static_model("Bathroom_Sink", "sink", (6.3, 0, -1.2), (0, 0, 0), 1.6, color.rgb(180, 195, 200))
bath_toilet = load_static_model("Bathroom_Toilet", "toilet", (9.5, 0, -3.8), (0, 90, 0), 1.5, color.rgb(200, 210, 215))
bath_bathtub = load_static_model("Bathroom_Bathtub", "bathtub", (4.0, 0, -1.0), (0, 180, 0), 2.6, color.rgb(210, 220, 225))

# Door
front_door = load_static_model("Door_1", "door", (0, 0, -8.82), (0, 0, 0), 2.35, color.rgb(140, 95, 55))

# Persons
megan = load_actor("megan", "person", Vec3(-3.7, 0, 1.45), 1.85)
sophie = load_actor("sophie", "person", Vec3(-6.6, 0, -1.98), 1.75)

# --------------------------------------------------
# SCENARIOS
# --------------------------------------------------

def enable_entities(entities):
    hide_all_tracked()
    for e in entities:
        if e:
            e.enabled = True


def scenario_living_sitting():
    enable_entities([living_couch, living_table, living_plant, living_lamp, megan])
    megan.position = Vec3(-3.25, 0, 2.10)
    megan.rotation_y = 160
    set_actor_pose(megan, "sit_idle")
    return Vec3(-3.7, 0, 1.45)


def scenario_kitchen_sitting():
    enable_entities([kitchen_table, kitchen_chair_1, kitchen_chair_2, fridge, kitchen_sink, cabinet, drawer, oven, sophie])
    sophie.position = Vec3(-6.6, 0, -1.98)
    sophie.rotation_y = 180
    set_actor_pose(sophie, "sit_idle")
    return Vec3(-6.6, 0, -1.98)


def scenario_bedroom_lying():
    enable_entities([bed_king, bed_single, bed_lamp, bed_drawer, megan])
    megan.position = Vec3(7.10, 1.45, 5.05)
    megan.rotation_y = 90
    set_actor_pose(megan, "sleep_idle")
    return Vec3(7.10, 0, 5.05)


def scenario_bathroom_standing():
    enable_entities([bath_sink, bath_toilet, bath_bathtub, sophie])
    sophie.position = Vec3(6.0, 0, -3.4)
    sophie.rotation_y = 180
    set_actor_pose(sophie, "idle")
    return Vec3(7.2, 0, -3.0)


SCENARIOS = [
    scenario_living_sitting,
    scenario_kitchen_sitting,
    scenario_bedroom_lying,
    scenario_bathroom_standing,
]

# --------------------------------------------------
# MAIN GENERATION
# --------------------------------------------------

def main():
    print("[START] generating preview scene dataset")

    for i in range(PREVIEW_COUNT):
        scenario = random.choice(SCENARIOS)
        focus = scenario()

        if scenario.__name__ == "scenario_kitchen_sitting":
            set_camera_near_focus(focus, mode="kitchen")
        elif scenario.__name__ == "scenario_bedroom_lying":
            set_camera_near_focus(focus, mode="bedroom")
        elif scenario.__name__ == "scenario_bathroom_standing":
            set_camera_near_focus(focus, mode="bathroom")
        else:
            set_camera_near_focus(focus, mode="default")

        filename = f"scene_preview_{i:04d}"
        image_path = IMAGE_DIR / f"{filename}.png"
        label_path = LABEL_DIR / f"{filename}.txt"
        preview_box_path = PREVIEW_BOX_DIR / f"{filename}_boxes.png"

        render_image(image_path)
        boxes = save_labels(label_path)
        draw_preview_boxes(image_path, preview_box_path, boxes)

        print(f"[OK] {filename} -> labels: {len(boxes)}")

    print("\n[DONE]")
    print("Images:", IMAGE_DIR)
    print("Labels:", LABEL_DIR)
    print("Preview boxes:", PREVIEW_BOX_DIR)

    application.quit()


main()