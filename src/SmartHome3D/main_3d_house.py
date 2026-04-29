from ultralytics import YOLO

model = YOLO("yolov8m.pt")

# YOLO COCO sınıfları:
# 0=person, 56=chair, 57=couch, 59=bed,
# 60=dining table, 69=oven, 71=sink, 72=refrigerator
HOME_OBJECT_CLASSES = [0, 56, 57, 59, 60, 69, 71, 72]

from ursina import *
from pathlib import Path
from panda3d.core import Filename
from direct.actor.Actor import Actor
import math
import csv
from datetime import datetime
from ursina.shaders import basic_lighting_shader

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'
CHARACTERS_PATH = ASSETS_PATH / 'characters' / 'exported'
CAPTURES_DIR = ASSETS_PATH / 'captures'
VISION_A_PATH = CAPTURES_DIR / 'vision_A.png'
VISION_B_PATH = CAPTURES_DIR / 'vision_B.png'
YOLO_A_RESULT_PATH = CAPTURES_DIR / 'yolo_A_result.png'
YOLO_B_RESULT_PATH = CAPTURES_DIR / 'yolo_B_result.png'
LOGS_DIR = PROJECT_ROOT / 'logs'
CSV_LOG_PATH = LOGS_DIR / 'smart_home_event_log.csv'
PLAN_VERSION = 'v1'

SCRIPT_DIR = Path(__file__).resolve().parent

CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# APP / WINDOW
# --------------------------------------------------

app = Ursina()

application.asset_folder = SCRIPT_DIR

print("SCRIPT_DIR =", SCRIPT_DIR)
print("FLOOR EXISTS =", (SCRIPT_DIR / 'floor_concrete.jpg').exists())
print("WOOD EXISTS =", (SCRIPT_DIR / 'wood_wall.jpg').exists())

floor_texture = load_texture('floor_concrete.jpg')
wood_texture = load_texture('wood_wall.jpg')

print('floor_texture =', floor_texture)
print('wood_texture =', wood_texture)


window.title = 'Smart Home Digital Twin - Full Demo'
window.borderless = False
window.exit_button.visible = True
window.fps_counter.enabled = True
window.color = color.rgb(214, 230, 240)

mouse.visible = True

# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

PLAYER_SPEED = 4.2
DEBUG_ZONES = False
ceiling_visible = False

notification_timer = 0.0
event_lines = []

current_room_a = 'Outside'
current_room_b = 'Outside'

SCENARIO_MOVE_SPEED = 3.2

scenario_active = False
scenario_name = ''
scenario_steps = []

move_target_a = None
move_target_a_active = False

move_target_b = None
move_target_b_active = False

current_anim_a = None
current_anim_b = None

pose_state_a = 'idle'   # idle / walk / sit_down / sit_idle / stand_up
pose_state_b = 'idle'

is_seated_a = False
is_seated_b = False

seat_target_a = None
seat_target_b = None

seat_timer_a = 0.0
seat_timer_b = 0.0

locked_seat_a = None
locked_seat_b = None

last_move_log_pos_a = None
last_move_log_pos_b = None

active_actor_id = 'A'

last_controlled_actor = 'A'


is_lying_a = False
is_lying_b = False

lying_target_a = None
lying_target_b = None


CAMERA_YAW = 0.0
CAMERA_PITCH = 38.0
CAMERA_DISTANCE = 15.0
CAMERA_ROTATE_SPEED = 220
CAMERA_ZOOM_SPEED = 1.2
startup_camera_timer = 1.2

UI_BLACK = color.rgb(15, 15, 15)
UI_RED = color.rgb(180, 25, 25)

wall_entities = []

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

COCO_LABELS = {
    0: 'person',
    56: 'chair',
    57: 'couch',
    59: 'bed',
    60: 'dining table',
    69: 'oven',
    71: 'sink',
    72: 'refrigerator'
}

ROOM_ALLOWED_OBJECTS = {
    'Living Room': ['person', 'chair', 'couch', 'dining table'],
    'Kitchen': ['person', 'chair', 'dining table', 'oven', 'sink', 'refrigerator'],
    'Bedroom': ['person', 'chair', 'bed'],
    'Bathroom': ['person', 'sink'],
    'Hall': ['person'],
    'Outside': ['person']
}


def filter_yolo_detections_by_room(results, room_name):
    """
    YOLO sonuçlarını oda bilgisine göre temizler.
    Örn: Bedroom içinde refrigerator algılanırsa yok sayılır.
    """
    allowed_labels = ROOM_ALLOWED_OBJECTS.get(room_name, ['person'])

    filtered = []

    for box in results[0].boxes:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        label = COCO_LABELS.get(cls_id, str(cls_id))

        if label not in allowed_labels:
            continue

        x1, y1, x2, y2 = box.xyxy[0].tolist()

        filtered.append({
            'class_id': cls_id,
            'label': label,
            'conf': round(conf, 2),
            'bbox': (round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1))
        })

    return filtered


def print_filtered_detections(actor_id, room_name, detections):
    if not detections:
        print(f'[VISION][{actor_id}] filtered detections in {room_name}: none')
        return

    summary = ', '.join(
        f"{d['label']}({d['conf']})" for d in detections
    )

    print(f'[VISION][{actor_id}] filtered detections in {room_name}: {summary}')

def set_ui_text(text_obj, value, text_color=color.black):
    text_obj.text = value
    text_obj.color = text_color
    text_obj.alpha = 1

def ensure_csv_log_file():
     if not CSV_LOG_PATH.exists():
        with open(CSV_LOG_PATH, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'actor_id',
                'plan_version',
                'scenario_name',
                'room_name',
                'event_code',
                'event_message',
                'device_name',
                'device_state',
                'player_x',
                'player_z'
            ])


def extract_device_info(event_message):
    device_name = '-'
    device_state = '-'

    lower_message = event_message.lower()

    if ':' in event_message:
        left, right = event_message.split(':', 1)
        device_name = left.strip()
        device_state = right.strip()
        return device_name, device_state

    if 'front door opened' in lower_message:
        return 'Front Door', 'OPEN'

    if 'front door closed' in lower_message:
        return 'Front Door', 'CLOSED'

    return device_name, device_state


def append_event_to_csv(event_code, event_message, actor_id='SYSTEM', actor_entity=None, room_name_override='-'):
    ensure_csv_log_file()

    current_scenario = scenario_name if scenario_name else '-'

    if actor_entity is not None:
        player_x = round(actor_entity.x, 2)
        player_z = round(actor_entity.z, 2)
    else:
        player_x = ''
        player_z = ''

    DEVICE_EVENT_CODES = (
        'bathroom_sink_on',
        'bathroom_sink_off',
        'living_lamp_on',
        'living_lamp_off',
        'kitchen_outlet_on',
        'kitchen_outlet_off',
        'coffee_machine_on',
        'coffee_machine_off',
        'toaster_on',
        'toaster_off',
        'kitchen_oven_on',
        'kitchen_oven_off',
        'front_door_opened',
        'front_door_closed',
    )

    if event_code in DEVICE_EVENT_CODES:
        device_name, device_state = extract_device_info(event_message)
    else:
        device_name, device_state = '-', '-'

    with open(CSV_LOG_PATH, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            actor_id,
            PLAN_VERSION,
            current_scenario,
            room_name_override,
            event_code,
            event_message,
            device_name,
            device_state,
            player_x,
            player_z
        ])

def push_notification(message, duration=2.0):
    global notification_timer
    set_ui_text(notification_text, message, color.black)
    notification_timer = duration

def update_event_panel():
    if event_lines:
        set_ui_text(event_log_text, 'Recent Events:\n' + '\n'.join(event_lines[:7]), color.black)
    else:
        set_ui_text(event_log_text, 'Recent Events:\n-', color.black)

def update_scenario_text():
    if scenario_active:
        set_ui_text(scenario_text, f'Scenario: {scenario_name}', color.black)
    else:
        set_ui_text(scenario_text, 'Scenario: -', color.black)


def log_event(code, message, actor_id='SYSTEM', actor_entity=None, room_name_override='-'):
    print(f'[EVENT][{actor_id}] {code}')
    event_lines.insert(0, f'[{actor_id}] {message}')
    if len(event_lines) > 7:
        event_lines.pop()
    update_event_panel()

    # Sürekli hareket loglarını ekranda gösterme
    if code not in ('player_move', 'manual_move_target_set'):
        push_notification(f'[{actor_id}] {message}')

    append_event_to_csv(
        code,
        message,
        actor_id=actor_id,
        actor_entity=actor_entity,
        room_name_override=room_name_override
    )


def save_vision_frame_for(actor_id, output_path, result_path, buffer):
    panda_path = Filename.from_os_specific(str(output_path))

    app.graphicsEngine.renderFrame()
    app.graphicsEngine.renderFrame()

    saved = app.screenshot(
        namePrefix=str(panda_path),
        defaultFilename=False,
        source=buffer
    )

    if saved:
        print(f'[VISION][{actor_id}] saved -> {output_path}')
        log_event(
            f'vision_frame_saved_{actor_id.lower()}',
            f'Vision frame saved for actor {actor_id}'
        )

        results = model.predict(
            source=str(output_path),
            imgsz=960,
            conf=0.25,
            iou=0.35,
            max_det=20,
            classes=HOME_OBJECT_CLASSES
        )

        if actor_id == 'A':
            actor_room = current_room_a
        else:
            actor_room = current_room_b

        filtered_detections = filter_yolo_detections_by_room(results, actor_room)
        print_filtered_detections(actor_id, actor_room, filtered_detections)

        results[0].save(filename=str(result_path))

    else:
        print(f'[VISION][{actor_id}] screenshot failed')
        push_notification(f'Vision save failed for actor {actor_id}')


def save_vision_frame():
    save_vision_frame_for('A', VISION_A_PATH, YOLO_A_RESULT_PATH, vision_buffer_A)
    save_vision_frame_for('B', VISION_B_PATH, YOLO_B_RESULT_PATH, vision_buffer_B)


def find_asset_path(base_name):
    candidates = [
        ASSETS_PATH / 'models_glb' / f'{base_name}.glb',   # ← try GLB first
        ASSETS_PATH / 'models_bam' / f'{base_name}.bam',   # ← then BAM
        ASSETS_PATH / 'models' / f'{base_name}.obj',        # ← OBJ last
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def create_click_box(parent, min_b, max_b):
    size_x = max(0.20, max_b.x - min_b.x)
    size_y = max(0.20, max_b.y - min_b.y)
    size_z = max(0.20, max_b.z - min_b.z)

    center_x = (min_b.x + max_b.x) / 2
    center_y = (min_b.y + max_b.y) / 2
    center_z = (min_b.z + max_b.z) / 2

    click_box = Entity(
        parent=parent,
        model='cube',
        position=(center_x, center_y, center_z),
        scale=(size_x, size_y, size_z),
        color=color.rgba(0, 0, 0, 0),
        collider='box'
    )
    return click_box


def make_placeholder_box(name, position=(0, 0, 0), scale=(1, 1, 1), rotation=(0, 0, 0), color_value=color.gray, parent=scene):
    e = Entity(
        parent=parent,
        model='cube',
        position=position,
        rotation=rotation,
        scale=scale,
        color=color_value,
        collider='box'
    )
    e.asset_name = name
    e.click_box = e
    return e


def load_static_model(base_name, position=(0, 0, 0), rotation=(0, 0, 0), target_size=1.0, parent=scene, tint=None):
    asset_path = find_asset_path(base_name)

    if asset_path is None:
        print(f'[MODEL] not found -> {base_name}')
        placeholder = make_placeholder_box(
            name=f'{base_name}_placeholder',
            position=position,
            rotation=rotation,
            scale=(target_size * 0.6, target_size * 0.6, target_size * 0.6),
            color_value=color.rgb(180, 100, 100),
            parent=parent
        )
        return placeholder

    wrapper = Entity(
        parent=parent,
        position=position,
        rotation=rotation
    )

    panda_path = Filename.from_os_specific(str(asset_path))
    node = app.loader.loadModel(panda_path)
    node.reparentTo(wrapper)
    node.setTwoSided(True)

    # FIX 1: Apply shader to the actual geometry node, not the wrapper
    node.setShaderAuto()

    # FIX 2: Apply tint as a color scale on the geometry node
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

        min_b, max_b = node.getTightBounds()
        wrapper.click_box = create_click_box(wrapper, min_b, max_b)
    else:
        wrapper.click_box = make_placeholder_box(
            name=f'{base_name}_clickbox',
            parent=wrapper,
            scale=(target_size, target_size, target_size),
            color_value=color.rgba(0, 0, 0, 0)
        )

    wrapper.model_node = node
    wrapper.asset_name = base_name
    print(f'[MODEL] loaded -> {base_name} ({asset_path.name})')
    return wrapper


def add_wall(position, scale, wall_color=color.white, wall_texture=None, texture_scale=(1, 1)):
    wall = Entity(
        model='cube',
        position=position,
        scale=scale,
        color=wall_color,
        texture=wall_texture,
        collider='box'
    )

    if wall_texture:
        wall.texture_scale = texture_scale

    wall_entities.append(wall)
    return wall


def add_room_floor(position, scale, color_value):
    floor = Entity(
        model='cube',
        position=position,
        scale=scale,
        color=color_value,
        collider='box'
    )
    floor.walkable = True
    return floor

def can_move_to(actor_entity, new_position):
    original_position = Vec3(actor_entity.position)

    actor_entity.position = new_position
    hit_wall = False

    for wall in wall_entities:
        if actor_entity.intersects(wall).hit:
            hit_wall = True
            break

    actor_entity.position = original_position
    return not hit_wall


def move_with_wall_collision(actor_entity, move_vector, speed):
    if move_vector.length() == 0:
        return

    step = move_vector * speed * time.dt

    # önce X
    test_pos_x = Vec3(actor_entity.x + step.x, actor_entity.y, actor_entity.z)
    if can_move_to(actor_entity, test_pos_x):
        actor_entity.x = test_pos_x.x

    # sonra Z
    test_pos_z = Vec3(actor_entity.x, actor_entity.y, actor_entity.z + step.z)
    if can_move_to(actor_entity, test_pos_z):
        actor_entity.z = test_pos_z.z

        
def create_zone(position, scale, tint=color.rgba(255, 255, 0, 35)):
    zone = Entity(
        model='cube',
        position=position,
        scale=scale,
        collider='box',
        visible=False
    )

    if DEBUG_ZONES:
        Entity(
            model='cube',
            position=position,
            scale=scale,
            color=tint
        )
    return zone


def get_click_target(entity):
    return entity.click_box if hasattr(entity, 'click_box') else entity

def step_move(x, z, threshold=0.35):
    return {
        'type': 'move',
        'target': Vec3(x, 0, z),
        'threshold': threshold,
    }

def step_wait(seconds):
    return {
        'type': 'wait',
        'duration': seconds,
        'remaining': seconds,
    }

def step_device(device, desired_state):
    return {
        'type': 'device',
        'device': device,
        'state': desired_state,
    }

def step_door(desired_open):
    return {
        'type': 'door',
        'state': desired_open,
    }

def step_note(text):
    return {
        'type': 'note',
        'text': text,
    }

def start_scenario(name, steps):
    global scenario_active, scenario_name, scenario_steps
    scenario_active = True
    scenario_name = name
    scenario_steps = steps.copy()
    push_notification(f'Scenario started: {name}')
    log_event(f'scenario_started_{name.lower().replace(" ", "_")}', f'Scenario started: {name}')
    update_scenario_text()

def stop_scenario(completed=False):
    global scenario_active, scenario_name, scenario_steps
    old_name = scenario_name

    scenario_active = False
    scenario_name = ''
    scenario_steps = []

    if completed:
        push_notification(f'Scenario completed: {old_name}')
        log_event(f'scenario_completed_{old_name.lower().replace(" ", "_")}', f'Scenario completed: {old_name}')
    else:
        push_notification('Scenario stopped')
        if old_name:
            log_event(f'scenario_stopped_{old_name.lower().replace(" ", "_")}', f'Scenario stopped: {old_name}')

    update_scenario_text()

def update_scenario_text():
    if scenario_active:
        set_ui_text(scenario_text, f'Scenario: {scenario_name}', color.black)
    else:
        set_ui_text(scenario_text, 'Scenario: -', color.black)

def get_scenario_move():
    global scenario_steps

    if not scenario_active:
        return None

    while scenario_steps:
        step = scenario_steps[0]
        step_type = step['type']

        if step_type == 'note':
            push_notification(step['text'])
            log_event('scenario_note', step['text'])
            scenario_steps.pop(0)
            continue

        if step_type == 'device':
            device = step['device']
            desired_state = step['state']

            if device.is_on != desired_state:
                device.set_state(desired_state)
            scenario_steps.pop(0)
            continue

        if step_type == 'door':
            desired_state = step['state']
            if front_door.is_open != desired_state:
                front_door.toggle()
            scenario_steps.pop(0)
            continue

        if step_type == 'wait':
            step['remaining'] -= time.dt
            if step['remaining'] <= 0:
                scenario_steps.pop(0)
                continue
            return Vec3(0, 0, 0)

        if step_type == 'move':
            target = step['target']
            delta = Vec3(target.x - player_a.x, 0, target.z - player_a.z)

            if delta.length() <= step['threshold']:
                scenario_steps.pop(0)
                continue

            return delta.normalized()

    stop_scenario(completed=True)
    return Vec3(0, 0, 0)

# --------------------------------------------------
# SMART DEVICE
# --------------------------------------------------

class SmartDevice:
    def __init__(
        self,
        name,
        entity,
        state_off='OFF',
        state_on='ON',
        indicator_offset=(0, 1.0, 0),
        indicator_scale=0.14,
        indicator_off=color.dark_gray,
        indicator_on=color.lime,
        on_turn_on=None,
        on_turn_off=None,
        before_toggle=None,
    ):
        self.name = name
        self.entity = entity
        self.state_off = state_off
        self.state_on = state_on
        self.is_on = False
        self.on_turn_on = on_turn_on
        self.on_turn_off = on_turn_off
        self.before_toggle = before_toggle
        self.indicator_off = indicator_off
        self.indicator_on = indicator_on

        self.indicator = Entity(
            parent=entity,
            model='sphere',
            position=indicator_offset,
            scale=indicator_scale,
            color=self.indicator_off
        )

        click_target = get_click_target(entity)
        click_target.on_click = self.toggle
        click_target.smart_device = self

    def toggle(self):
        target_state = not self.is_on

        if self.before_toggle:
            allowed = self.before_toggle(target_state, self)
            if not allowed:
                return

        self.set_state(target_state)

    def set_state(self, state, silent=False):
        self.is_on = state
        self.indicator.color = self.indicator_on if state else self.indicator_off

        if self.is_on:
            if self.on_turn_on:
                self.on_turn_on()
            if not silent:
                log_event(f'{self.name.lower().replace(" ", "_")}_on', f'{self.name}: {self.state_on}')
        else:
            if self.on_turn_off:
                self.on_turn_off()
            if not silent:
                log_event(f'{self.name.lower().replace(" ", "_")}_off', f'{self.name}: {self.state_off}')

        update_device_panel()


class AnimatedDoor:
    def __init__(self, name, pivot, panel):
        self.name = name
        self.pivot = pivot
        self.panel = panel
        self.is_open = False
        self.target_y = 0

        click_target = get_click_target(panel)
        click_target.on_click = self.toggle
        click_target.smart_device = self

    def toggle(self):
        self.is_open = not self.is_open

        if self.is_open:
            self.target_y = 95
            log_event(f'{self.name.lower().replace(" ", "_")}_opened', f'{self.name} opened')
        else:
            self.target_y = 0
            log_event(f'{self.name.lower().replace(" ", "_")}_closed', f'{self.name} closed')

        update_device_panel()

# --------------------------------------------------
# ROOM DEFINITIONS
# --------------------------------------------------

ROOMS = {
    'Living Room': {'x_min': -10.8, 'x_max': 2.8, 'z_min': 0.0, 'z_max': 8.8},
    'Kitchen':     {'x_min': -10.8, 'x_max': 2.8, 'z_min': -8.8, 'z_max': -1.2},
    'Hall':        {'x_min': -2.2,  'x_max': 3.2, 'z_min': -8.8, 'z_max': 8.8},
    'Bedroom':     {'x_min': 3.2,   'x_max': 10.8, 'z_min': 1.7, 'z_max': 8.8},
    'Bathroom':    {'x_min': 3.2,   'x_max': 10.8, 'z_min': -8.8, 'z_max': 1.2},
}


def get_room_name(position):
    for room_name, bounds in ROOMS.items():
        if (
            bounds['x_min'] <= position.x <= bounds['x_max']
            and bounds['z_min'] <= position.z <= bounds['z_max']
        ):
            return room_name
    return 'Outside'


# --------------------------------------------------
# SCENE / FLOOR / WALLS
# --------------------------------------------------

ground = Entity(
    model='plane',
    scale=(30, 1, 30),
    texture=floor_texture,
    texture_scale=(8, 8),
    color=color.white,
    collider='mesh'
)
ground.walkable = True

floor_main = Entity(
    model='cube',
    position=(0, -0.55, 0),
    scale=(22, 0.12, 18),
    texture=floor_texture,
    color=color.white
)
floor_main.texture_scale = (6, 6)

# room floor colors

living_floor = add_room_floor(
    position=(-4.0, -0.48, 4.4),
    scale=(14, 0.02, 8.6),
    color_value=color.rgb(210, 195, 175)   # ← daha sıcak bej
)

# Mutfak - soğuk gri-mavi
kitchen_floor = add_room_floor(
    position=(-4.0, -0.48, -4.9),
    scale=(14, 0.02, 7.6),
    color_value=color.rgb(195, 208, 218)   # ← hafif mavi-gri
)

# Koridor - nötr
hall_floor = add_room_floor(
    position=(0.4, -0.48, 0.0),
    scale=(5.0, 0.02, 18.0),
    color_value=color.rgb(210, 208, 205)   # ← hafif bej-gri
)

# Yatak odası - lavanta/mor ton
bedroom_floor = add_room_floor(
    position=(7.0, -0.48, 5.2),
    scale=(8.0, 0.02, 7.2),
    color_value=color.rgb(205, 195, 215)   # ← hafif mor
)

# Banyo - açık mavi-yeşil
bathroom_floor = add_room_floor(
    position=(7.0, -0.48, -5.0),
    scale=(8.0, 0.02, 7.8),
    color_value=color.rgb(195, 218, 222)   # ← açık turkuaz
)


living_floor.enabled = False
kitchen_floor.enabled = False
hall_floor.enabled = False
bedroom_floor.enabled = False
bathroom_floor.enabled = False
#outer_wall_color = color.orange

# outer walls with front door gap
add_wall(
    position=(-11, 1.5, 0),
    scale=(0.35, 3, 18),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(2, 2)
)

add_wall(
    position=(11, 1.5, 0),
    scale=(0.35, 3, 18),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(2, 2)
)

add_wall(
    position=(0, 1.5, 9),
    scale=(22, 3, 0.35),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(4, 2)
)

add_wall(
    position=(-6.5, 1.5, -9),
    scale=(9.0, 3, 0.35),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(3, 2)
)

add_wall(
    position=(6.5, 1.5, -9),
    scale=(9.0, 3, 0.35),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(3, 2)
)

add_wall(
    position=(0, 2.55, -9),
    scale=(4.0, 0.9, 0.35),
    wall_color=color.white,
    wall_texture=wood_texture,
    texture_scale=(2, 1)
)

# inner walls
inner_wall_color = color.white66

# left side kitchen / living separator
add_wall(position=(-6.5, 1.5, -1.2), scale=(9.0, 3, 0.30), wall_color=inner_wall_color)

# right side main vertical split, with two openings
add_wall(position=(3.0, 1.5, 7.2), scale=(0.30, 3, 3.4), wall_color=inner_wall_color)
add_wall(position=(3.0, 1.5, 0.0), scale=(0.30, 3, 9.2), wall_color=inner_wall_color)
add_wall(position=(3.0, 1.5, -7.2), scale=(0.30, 3, 3.4), wall_color=inner_wall_color)

# bathroom / bedroom separator
add_wall(position=(7.0, 1.5, 1.5), scale=(8.0, 3, 0.30), wall_color=inner_wall_color)

# ceiling pieces
ceiling_parts = []

for pos, scl in [
    ((-4.0, 3.05, 4.4), (14.0, 0.12, 8.6)),
    ((-4.0, 3.05, -4.9), (14.0, 0.12, 7.6)),
    ((0.4, 3.05, 0.0), (5.0, 0.12, 18.0)),
    ((7.0, 3.05, 5.2), (8.0, 0.12, 7.2)),
    ((7.0, 3.05, -5.0), (8.0, 0.12, 7.8)),
]:
    c = Entity(
        model='cube',
        position=pos,
        scale=scl,
        color=color.rgb(185, 185, 185),
        enabled=ceiling_visible
    )
    ceiling_parts.append(c)

# --------------------------------------------------
# LIGHTS / SKY
# --------------------------------------------------

sun = DirectionalLight()
sun.look_at(Vec3(1, -1, -1))
sun.color = color.rgba(235, 235, 235, 1.0)

ambient = AmbientLight()
ambient.color = color.rgba(35, 35, 35, 0.22)

Sky()

# --------------------------------------------------
# PLAYERS + ACTORS
# --------------------------------------------------

player_a = Entity(
    model='cube',
    color=color.rgba(0, 0, 0, 0),
    scale=(0.75, 1.7, 0.75),
    position = (-0.5, 0.85, -5.8),
    collider='box',
    visible=False
)

player_b = Entity(
    model='cube',
    color=color.rgba(0, 0, 0, 0),
    scale=(0.75, 1.7, 0.75),
    position = (1.2, 0.85, -5.8),
    collider='box',
    visible=False
)

megan_root = Entity(position=(player_a.x, 0, player_a.z))
sophie_root = Entity(position=(player_b.x, 0, player_b.z))

megan = None
sophie = None

# --- Megan paths ---
megan_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_idle.glb').resolve())
).getFullpath()

megan_walk_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_walk.glb').resolve())
).getFullpath()

megan_sit_down_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_sit_down.glb').resolve())
).getFullpath()

megan_sit_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_sit_idle.glb').resolve())
).getFullpath()

megan_stand_up_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_stand_up.glb').resolve())
).getFullpath()

megan_lie_down_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_lie_down.glb').resolve())
).getFullpath()

megan_sleep_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_sleep_idle.glb').resolve())
).getFullpath()

megan_get_up_from_bed_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_get_up_from_bed.glb').resolve())
).getFullpath()


# --- Sophie paths ---
sophie_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_idle.glb').resolve())
).getFullpath()

sophie_walk_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_walk.glb').resolve())
).getFullpath()

sophie_sit_down_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_sit_down.glb').resolve())
).getFullpath()

sophie_sit_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_sit_idle.glb').resolve())
).getFullpath()

sophie_stand_up_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_stand_up.glb').resolve())
).getFullpath()

sophie_lie_down_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_lie_down.glb').resolve())
).getFullpath()

sophie_sleep_idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_sleep_idle.glb').resolve())
).getFullpath()

sophie_get_up_from_bed_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_get_up_from_bed.glb').resolve())
).getFullpath()

try:
    megan = Actor(
    megan_idle_path,
    {
        'idle': megan_idle_path,
        'walk': megan_walk_path,
        'sit_down': megan_sit_down_path,
        'sit_idle': megan_sit_idle_path,
        'stand_up': megan_stand_up_path,
        'lie_down': megan_lie_down_path,
        'sleep_idle': megan_sleep_idle_path,
        'get_up_from_bed': megan_get_up_from_bed_path,
    }
)
    megan.reparentTo(megan_root)

    bounds = megan.getTightBounds()
    if bounds and bounds[0] is not None and bounds[1] is not None:
        min_b, max_b = bounds
        size_x = max_b.x - min_b.x
        size_y = max_b.y - min_b.y
        size_z = max_b.z - min_b.z
        max_dim = max(size_x, size_y, size_z, 0.0001)

        target_size = 1.85
        uniform_scale = target_size / max_dim
        megan.setScale(uniform_scale)

        min_b, max_b = megan.getTightBounds()
        center_x = (min_b.x + max_b.x) / 2
        center_z = (min_b.z + max_b.z) / 2
        megan.setPos(-center_x, -min_b.y, -center_z)

    megan.setH(0)

    if 'idle' in megan.getAnimNames():
        megan.loop('idle')
        current_anim_a = 'idle'
        print('Megan anims ->', megan.getAnimNames())

except Exception as e:
    print(f'[MEGAN ACTOR ERROR] {e}')
    megan = None

try:
    sophie = Actor(
    sophie_idle_path,
    {
        'idle': sophie_idle_path,
        'walk': sophie_walk_path,
        'sit_down': sophie_sit_down_path,
        'sit_idle': sophie_sit_idle_path,
        'stand_up': sophie_stand_up_path,
        'lie_down': sophie_lie_down_path,
        'sleep_idle': sophie_sleep_idle_path,
        'get_up_from_bed': sophie_get_up_from_bed_path,
    }
)
    sophie.reparentTo(sophie_root)

    bounds = sophie.getTightBounds()
    if bounds and bounds[0] is not None and bounds[1] is not None:
        min_b, max_b = bounds
        size_x = max_b.x - min_b.x
        size_y = max_b.y - min_b.y
        size_z = max_b.z - min_b.z
        max_dim = max(size_x, size_y, size_z, 0.0001)

        target_size = 1.75
        uniform_scale = target_size / max_dim
        sophie.setScale(uniform_scale)

        min_b, max_b = sophie.getTightBounds()
        center_x = (min_b.x + max_b.x) / 2
        center_z = (min_b.z + max_b.z) / 2
        sophie.setPos(-center_x, -min_b.y, -center_z)

    sophie.setH(0)

    if 'idle' in sophie.getAnimNames():
        sophie.loop('idle')
        current_anim_b = 'idle'
        print('Sophie anims ->', sophie.getAnimNames())

except Exception as e:
    print(f'[SOPHIE ACTOR ERROR] {e}')
    sophie = None

# --------------------------------------------------
# CAMERA
# --------------------------------------------------

camera.position = Vec3(0, 20, -22)
camera.look_at(Vec3(0, 0, 0))


# --------------------------------------------------
# OFFSCREEN VISION CAMERA
# --------------------------------------------------

# -------- CAMERA A --------
vision_buffer_A = app.win.makeTextureBuffer('VisionBufferA', 640, 640)
vision_buffer_A.setSort(-100)

vision_cam_A = app.makeCamera(vision_buffer_A)
vision_cam_A.reparentTo(app.render)

# -------- CAMERA B --------
vision_buffer_B = app.win.makeTextureBuffer('VisionBufferB', 640, 640)
vision_buffer_B.setSort(-100)

vision_cam_B = app.makeCamera(vision_buffer_B)
vision_cam_B.reparentTo(app.render)

# --------------------------------------------------
# UI
# --------------------------------------------------

info_text = Text(
    text='WASD=A | Arrows=B | Mouse click moves active actor | E=A interact | Right Shift=B interact | Middle drag camera | R door | T vision | ESC exit',
    position=(-0.86, 0.46),
    scale=0.90,
    background=True,
    color=color.white
)

room_text = Text(
    text='Room: Outside',
    position=(-0.86, 0.40),
    scale=0.95,
    background=False,
    color=color.black
)

position_text = Text(
    text='',
    position=(-0.86, 0.35),
    scale=0.90,
    background=False,
    color=color.black
)

hint_text = Text(
    text='Nearest: -',
    position=(-0.86, 0.30),
    scale=0.90,
    background=False,
    color=color.black
)

scenario_text = Text(
    text='Scenario: -',
    position=(-0.86, 0.25),
    scale=0.90,
    background=False,
    color=color.black
)

device_text = Text(
    text='',
    position=(-0.86, 0.10),
    scale=0.88,
    background=False,
    color=color.black
)

event_log_text = Text(
    text='Recent Events:\n-',
    position=(0.38, 0.28),
    scale=0.72,
    background=False,
    color=color.black
)

notification_text = Text(
    text='',
    position=(-0.12, 0.18),
    scale=1.25,
    background=False,
    color=color.black
)

interaction_text = Text(
    text='',
    position=(-0.86, 0.24),
    scale=0.92,
    background=False,
    color=color.azure
)

position_text.enabled = False
hint_text.enabled = False
device_text.enabled = False
room_text.enabled = False
scenario_text.enabled = False
event_log_text.enabled = False
interaction_text.enabled = False
info_text.enabled = False
notification_text.enabled = False

target_marker = Entity(
    model='sphere',
    scale=0.18,
    color=color.yellow,
    y=0.05,
    enabled=False
)

highlighted_device = None
DEFAULT_INDICATOR_SCALE = 0.14
HIGHLIGHT_INDICATOR_SCALE = 0.22


# --------------------------------------------------
# LIVING ROOM OBJECTS
# --------------------------------------------------

living_carpet = load_static_model(
    'Carpet_Round',
    position=(-5.0, 0.01, 4.5),
    rotation=(0, 0, 0),
    target_size=3.2,
    tint=color.rgb(140, 80, 70)
)

living_couch = load_static_model(
    'Couch_Small2',
    position=(-8.8, 0.0, 5.3),
    rotation=(0, 90, 0),
    target_size=2.8,
    tint=color.rgb(120, 95, 80)
)

living_couch_2 = load_static_model(
    'Couch_Large2',
    position=(-4.7, 0.0, 1.8),
    rotation=(0, 180, 0),
    target_size=3.2,
    tint=color.rgb(125, 100, 85)
)


living_table = load_static_model(
    'Table_RoundSmall',
    position=(-5.0, 0.0, 4.6),
    rotation=(0, 0, 0),
    target_size=1.3,
    tint=color.hex("#D8B08C")
)

living_lamp_entity = load_static_model(
    'Light_Stand1',
    position=(-9.3, 0.0, 2.2),
    rotation=(0, 0, 0),
    target_size=1.6,
    tint=color.rgb(210, 190, 120)
)

living_window = load_static_model(
    'Window_Small1',
    position=(-10.75, 1.7, 4.9),
    rotation=(0, 90, 0),
    target_size=2.2,
    tint=color.rgb(180, 205, 220)
)


living_plant = load_static_model(
    'Houseplant_1',
    position=(-5.2, 0.0, 7.8),
    rotation=(0, 270, 0),
    target_size=1.3,
    tint=color.rgb(80, 145, 85)
)

living_shelf = load_static_model(
    'Shelf_Large',
    position=(-10.5, 0.0, 1.5),
    rotation=(0, 90, 0),
    target_size=2.2,
    tint=color.rgb(120, 85, 55)
)


# --------------------------------------------------
# BEDROOM OBJECTS
# --------------------------------------------------

bed = load_static_model(
    'Bed_King',
    position=(7.1, 0.0, 5.4),
    rotation=(0, 180, 0),
    target_size=3.2,
    tint=color.rgb(210, 205, 195)
)

bed_single = load_static_model(
    'Bed_Single',
    position=(4.9, 0.0, 5.7),
    rotation=(0, 180, 0),
    target_size=2.3,
    tint=color.rgb(205, 200, 190)
)

nightstand_right = load_static_model(
    'NightStand_2',
    position=(9.3, 0.0, 5.0),
    rotation=(0, 180, 0),
    target_size=1.0,
    tint=color.rgb(110, 80, 55)
)

bedroom_drawer = load_static_model(
    'Drawer_2',
    position=(10.3, 0.0, 8.0),
    rotation=(0, 270, 0),
    target_size=1.5,
    tint=color.rgb(120, 88, 60)
)


bedroom_plant_2 = load_static_model(
    'Houseplant_3',
    position=(4.1, 0.0, 7.7),
    rotation=(0, 0, 0),
    target_size=1.25,
    tint=color.rgb(80, 145, 85)
)

bedroom_floor_lamp = load_static_model(
    'Light_Stand2',
    position=(10.4, 0.0, 4.0),
    rotation=(0, 0, 0),
    target_size=1.85,
    tint=color.rgb(220, 200, 140)
)


# --------------------------------------------------
# BATHROOM OBJECTS
# --------------------------------------------------

bath_sink = load_static_model(
    'Bathroom_Sink',
    position=(6.3, 0.0, -1.2),
    rotation=(0, 0, 0),
    target_size=1.6,
    tint=color.rgb(180, 195, 200)
)

bath_mirror = load_static_model(
    'Bathroom_Mirror1',
    position=(6.3, 1.9, -1.2),
    rotation=(0, 0, 0),
    target_size=1.9,
    tint=color.rgb(140, 165, 180)
)

bath_toilet = load_static_model(
    'Bathroom_Toilet',
    position=(9.5, 0.0, -3.8),
    rotation=(0, 90, 0),
    target_size=1.5,
    tint=color.rgb(200, 210, 215)
)

bath_shower = load_static_model(
    'Bathroom_Shower1',
    position=(9.55, 0.0, -7.35),
    rotation=(0, 90, 0),
    target_size=2.15,
    tint=color.rgb(180, 210, 225)
)

bath_washer = load_static_model(
    'Bathroom_WashingMachine',
    position=(6.4, 0.0, -6.8),
    rotation=(0, 180, 0),
    target_size=1.5,
    tint=color.rgb(200, 205, 215)  # ← beyaz makine
)

bath_towel = load_static_model(
    'Bathroom_Towel',
    position=(10.6, 1.4, -4.8),
    rotation=(0, 270, 0),
    target_size=1.4,
    tint=color.rgb(80, 170, 230)
)

bath_toilet_paper_pile = load_static_model(
    'Bathroom_ToiletPaperPile',
    position=(9.3, 0.7, -0.4),
    rotation=(0, 0, 0),
    target_size=0.8,
    tint=color.rgb(245, 245, 245)
)

bath_trashcan = load_static_model(
    'Trashcan_Cylindric',
    position=(10.3, 0.3, -0.2),
    rotation=(0, 0, 0),
    target_size=0.9,
    tint=color.rgb(45, 45, 45)
)

bath_bathtub = load_static_model(
    'Bathroom_Bathtub',
    position=(4.0, 0.0, -1.0),
    rotation=(0, 180, 0),
    target_size=2.6,
    tint=color.rgb(210, 220, 225)
)

# --------------------------------------------------
# KITCHEN OBJECTS
# --------------------------------------------------

kitchen_counter = Entity(
    model='cube',
    position=(-5.0, 0.45, -7.25),
    scale=(7.9, 0.90, 1.15),
    color=color.rgb(188, 188, 196),
    collider='box'
)

kitchen_back_splash = Entity(
    model='cube',
    position=(-5.0, 1.55, -8.55),
    scale=(8.1, 1.7, 0.12),
    color=color.rgb(228, 228, 232)
)

# SOL TARAFTA GÖRÜNÜR BUZDOLABI

fridge = load_static_model(
    'Kitchen_Fridge',
    position=(-9.85, 0.0, -2.15),
    rotation=(0, 0, 0),
    target_size=3.0,
    # Daha tok ve koyu bir füme/gri tonu:
    tint=color.hex("#591C21")   
)
fridge.texture = None

# Buzdolabının sağında küçük tezgah
stove_counter = Entity(
    model='cube',
    position=(-10.25, 0.45, -4.35),
    scale=(1.20, 0.90, 3.00),
    color=color.white,
    collider='box'
)

# Beyaz gövdenin üstüne koyu kaplama
stove_counter_cover = Entity(
    model='cube',
    position=(-10.25, 0.46, -4.35),
    scale=(1.22, 0.92, 3.02),
    color=color.dark_gray,
    collider=None
)

kitchen_oven_model = Entity(
    model='cube',
    position=(-10.25, 0.94, -4.35),
    scale=(0.95, 0.04, 2.25),
    color=color.black,
    collider='box'
)

for sx in [-0.25, 0.25]:
    for sz in [-0.65, 0.65]:
        Entity(
            parent=kitchen_oven_model,
            model='torus',
            position=(sx, 0.06, sz),
            rotation=(90, 0, 0),
            scale=0.13,
            color=color.white
        )

kitchen_sink_model = load_static_model(
    'Kitchen_Sink',
    position=(-8.65, 0.88, -7.25),
    rotation=(0, 180, 0),
    target_size=1.25,
    tint=color.rgb(170, 180, 185)
)

kitchen_cabinet = load_static_model(
    'Kitchen_Cabinet1',
    position=(-6.2, 0.0, -7.25),
    rotation=(0, 180, 0),
    target_size=1.55,
    tint=color.rgb(160, 115, 70)
)

kitchen_drawers = load_static_model(
    'Kitchen_2Drawers',
    position=(-4.2, 0.0, -7.25),
    rotation=(0, 180, 0),
    target_size=1.5,
    tint=color.rgb(175, 130, 80)
)

kitchen_table = load_static_model(
    'Table_RoundSmall',
    position=(-6.60, 0.0, -3.55),
    rotation=(0, 0, 0),
    target_size=2.0,
    tint=color.hex("#D8B08C")
)

kitchen_table.texture = None

kitchen_chair_1 = load_static_model(
    'Chair_1',
    position=(-6.60, 0.0, -2.10),
    rotation=(0, 360, 0),
    target_size=1.20,
    tint=color.rgb(150, 105, 70)
)

kitchen_chair_2 = load_static_model(
    'Chair_1',
    position=(-6.60, 0.0, -4.75),
    rotation=(0, 180, 0),
    target_size=1.20,
    tint=color.rgb(150, 105, 70)
)

# outlet / toaster / coffee machine are placeholders because this pack does not clearly include direct models

kitchen_outlet_entity = make_placeholder_box(
    name='Kitchen_Outlet',
    position=(-3.6, 1.35, -8.55),
    scale=(0.80, 0.80, 0.22),
    color_value=color.rgb(255, 80, 80)
)

toaster_entity = make_placeholder_box(
    name='Toaster',
    position=(-4.6, 1.04, -7.05),
    scale=(0.42, 0.18, 0.28),
    color_value=color.dark_gray
)
Entity(parent=toaster_entity, model='cube', position=(-0.12, 0.12, 0), scale=(0.06, 0.16, 0.12), color=color.light_gray)
Entity(parent=toaster_entity, model='cube', position=(0.12, 0.12, 0), scale=(0.06, 0.16, 0.12), color=color.light_gray)

coffee_machine_entity = make_placeholder_box(
    name='Coffee_Machine',
    position=(-6.0, 1.08, -7.05),
    scale=(0.40, 0.40, 0.35),
    color_value=color.rgb(45, 45, 45)
)
Entity(parent=coffee_machine_entity, model='cube', position=(0, -0.18, 0.14), scale=(0.18, 0.14, 0.08), color=color.rgb(220, 220, 220))

kitchen_plate = load_static_model(
    'Plate_1',
    position=(-5.15, 1.37, -7.05),
    rotation=(0, 0, 0),
    target_size=0.55,
    tint=color.rgb(240, 235, 220)
)

kitchen_spoon = load_static_model(
    'Spoon',
    position=(-4.80, 1.39, -7.15),
    rotation=(0, 35, 0),
    target_size=0.48,
    tint=color.rgb(185, 185, 180)
)

kitchen_fork = load_static_model(
    'Fork',
    position=(-4.52, 1.39, -7.05),
    rotation=(0, -25, 0),
    target_size=0.48,
    tint=color.rgb(185, 185, 180)
)

kitchen_knife = load_static_model(
    'Knife',
    position=(-4.22, 1.39, -7.05),
    rotation=(0, 10, 0),
    target_size=0.48,
    tint=color.rgb(165, 165, 165)
)

# --------------------------------------------------
# FRONT DOOR
# --------------------------------------------------

door_pivot = Entity(position=(0, 0, -8.82), rotation=(0, 0, 0))
door_panel = load_static_model(
    'Door_1',
    position=(0.50, 0.0, 0.0),
    rotation=(0, 0, 0),
    target_size=2.35,
    parent=door_pivot,
    tint=color.rgb(140, 95, 55)
)


# Hall -> Bedroom
bedroom_hall_pivot = Entity(
    position=(2.92, 0.0, 5.55),
    rotation=(0, 0, 0)
)
bedroom_hall_door = load_static_model(
    'Door_1',
    position=(0.42, 0.0, 0.0),   # pivot'tan yana kaydır
    rotation=(0, 90, 0),
    target_size=2.15,
    parent=bedroom_hall_pivot,
    tint=color.rgb(175, 120, 65)
)

# Hall -> Bathroom
bathroom_hall_pivot = Entity(
    position=(2.92, 0.0, -5.55),
    rotation=(0, 0, 0)
)
bathroom_hall_door = load_static_model(
    'Door_1',
    position=(0.42, 0.0, 0.0),   # pivot'tan yana kaydır
    rotation=(0, 90, 0),
    target_size=2.15,
    parent=bathroom_hall_pivot,
    tint=color.rgb(175, 120, 65)
)


bedroom_door = AnimatedDoor('Bedroom Door', bedroom_hall_pivot, bedroom_hall_door)
bathroom_door = AnimatedDoor('Bathroom Door', bathroom_hall_pivot, bathroom_hall_door)

# --------------------------------------------------
# DEVICE VISUALS
# --------------------------------------------------

lamp_light = PointLight(parent=scene, position=(-9.3, 2.2, 2.2), color=color.rgb(255, 230, 170))
lamp_light.enabled = False

toaster_glow = Entity(
    parent=toaster_entity,
    model='sphere',
    position=(0, 0.20, 0),
    scale=0.12,
    color=color.rgba(255, 80, 60, 0),
    enabled=False
)

coffee_glow = Entity(
    parent=coffee_machine_entity,
    model='sphere',
    position=(0, 0.32, 0),
    scale=0.12,
    color=color.rgba(170, 120, 80, 0),
    enabled=False
)

oven_glow = Entity(
    parent=kitchen_oven_model,
    model='cube',
    position=(0, 0.55, 0.12),
    scale=(0.65, 0.20, 0.04),
    color=color.rgba(255, 150, 60, 0),
    enabled=False
)

sink_glow = Entity(
    parent=bath_sink,
    model='sphere',
    position=(0, 0.85, 0),
    scale=0.14,
    color=color.rgba(80, 180, 255, 0),
    enabled=False
)

# --------------------------------------------------
# DEVICE RULES
# --------------------------------------------------

def requires_outlet(target_state, _device):
    if target_state and not kitchen_outlet.is_on:
        log_event('outlet_required', 'Turn ON the kitchen outlet first')
        return False
    return True


def lamp_on():
    lamp_light.enabled = True


def lamp_off():
    lamp_light.enabled = False


def toaster_on():
    toaster_glow.enabled = True
    toaster_glow.color = color.rgb(255, 90, 70)


def toaster_off():
    toaster_glow.enabled = False


def coffee_on():
    coffee_glow.enabled = True
    coffee_glow.color = color.rgb(165, 120, 90)


def coffee_off():
    coffee_glow.enabled = False


def oven_on():
    oven_glow.enabled = True
    oven_glow.color = color.rgb(255, 145, 60)


def oven_off():
    oven_glow.enabled = False


def sink_on():
    sink_glow.enabled = True
    sink_glow.color = color.rgb(90, 180, 255)


def sink_off():
    sink_glow.enabled = False


front_door = AnimatedDoor('Front Door', door_pivot, door_panel)

living_lamp = SmartDevice(
    name='Living Lamp',
    entity=living_lamp_entity,
    state_off='OFF',
    state_on='ON',
    indicator_offset=(0, 1.85, 0),
    indicator_scale=0.16,
    on_turn_on=lamp_on,
    on_turn_off=lamp_off
)

kitchen_outlet = SmartDevice(
    name='Kitchen Outlet',
    entity=kitchen_outlet_entity,
    state_off='OFF',
    state_on='ON',
    indicator_offset=(0, 0.35, 0.03),
    indicator_scale=0.10
)

toaster_device = SmartDevice(
    name='Toaster',
    entity=toaster_entity,
    state_off='OFF',
    state_on='HEATING',
    indicator_offset=(0, 0.18, 0),
    indicator_scale=0.10,
    indicator_on=color.red,
    on_turn_on=toaster_on,
    on_turn_off=toaster_off,
    before_toggle=requires_outlet
)

coffee_device = SmartDevice(
    name='Coffee Machine',
    entity=coffee_machine_entity,
    state_off='OFF',
    state_on='BREWING',
    indicator_offset=(0, 0.34, 0),
    indicator_scale=0.10,
    indicator_on=color.orange,
    on_turn_on=coffee_on,
    on_turn_off=coffee_off,
    before_toggle=requires_outlet
)

oven_device = SmartDevice(
    name='Kitchen Oven',
    entity=kitchen_oven_model,
    state_off='OFF',
    state_on='COOKING',
    indicator_offset=(0, 1.0, 0),
    indicator_scale=0.12,
    indicator_on=color.orange,
    on_turn_on=oven_on,
    on_turn_off=oven_off,
    before_toggle=requires_outlet
)

sink_device = SmartDevice(
    name='Bathroom Sink',
    entity=bath_sink,
    indicator_offset=(0, 1.1, 0),
    indicator_scale=0.12,
    indicator_off=color.orange, # Kapalıyken Turuncu (daha belirgin)
    indicator_on=color.azure,    # Açıkken Mavi
    on_turn_on=sink_on,
    on_turn_off=sink_off
)

all_devices = [
    front_door,
    bedroom_door,
    bathroom_door,
    living_lamp,
    kitchen_outlet,
    toaster_device,
    coffee_device,
    oven_device,
    sink_device,
]

def build_scenario_1():
    return [
        step_note('Entry and bathroom routine'),
        step_door(True),
        step_move(0.2, -6.8),
        step_wait(0.8),
        step_door(False),
        step_move(5.8, -4.8),
        step_wait(0.6),
        step_device(sink_device, True),
        step_wait(2.0),
        step_device(sink_device, False),
        step_wait(0.5),
        step_move(1.0, -3.5),
    ]

def build_scenario_2():
    return [
        step_note('Kitchen breakfast routine'),
        step_move(-5.3, -5.7),
        step_wait(0.5),
        step_device(kitchen_outlet, True),
        step_wait(0.5),
        step_device(coffee_device, True),
        step_wait(1.5),
        step_device(toaster_device, True),
        step_wait(2.0),
        step_device(toaster_device, False),
        step_wait(1.0),
        step_device(coffee_device, False),
    ]

def build_scenario_3():
    return [
        step_note('Evening cooking routine'),
        step_move(-5.4, -5.4),
        step_device(kitchen_outlet, True),
        step_wait(0.5),
        step_device(oven_device, True),
        step_wait(2.5),
        step_device(oven_device, False),
        step_wait(0.5),
        step_move(-7.3, 4.2),
        step_device(living_lamp, True),
        step_wait(1.5),
    ]

def build_scenario_4():
    return [
        step_note('Night shutdown routine'),
        step_move(-5.4, -5.4),
        step_device(toaster_device, False),
        step_device(coffee_device, False),
        step_device(oven_device, False),
        step_device(kitchen_outlet, False),
        step_wait(0.5),
        step_move(-7.3, 4.2),
        step_device(living_lamp, False),
        step_wait(0.5),
        step_move(6.6, 5.0),
    ]

# --------------------------------------------------
# SEAT POINTS
# --------------------------------------------------

seat_points = [
    # --- Couch_Small2 (-8.8, 5.3, rot=90) ---
    {
        'name': 'Small Couch Left',
        'position': Vec3(-8.8, 0.0, 5.65),
        'rotation_y': 90,
        'seat_type': 'couch',
        'occupied_by': None,
        'offset': Vec3(-0.35, 0.58, 0.0),
    },
    {
        'name': 'Small Couch Right',
        'position': Vec3(-8.8, 0.0, 4.95),
        'rotation_y': 90,
        'seat_type': 'couch',
        'occupied_by': None,
        'offset': Vec3(-0.35, 0.58, 0.0),
    },

    # --- Couch_Large2 (-4.7, 1.8, rot=180) ---
    {
        'name': 'Large Couch Left',
        'position': Vec3(-5.7, 0.0, 1.8),
        'rotation_y': 180,
        'seat_type': 'couch',
        'occupied_by': None,
        'offset': Vec3(0.0, 0.58, -0.35),
    },
    {
        'name': 'Large Couch Center',
        'position': Vec3(-4.7, 0.0, 1.8),
        'rotation_y': 180,
        'seat_type': 'couch',
        'occupied_by': None,
        'offset': Vec3(0.0, 0.58, -0.35),
    },
    {
        'name': 'Large Couch Right',
        'position': Vec3(-3.7, 0.0, 1.8),
        'rotation_y': 180,
        'seat_type': 'couch',
        'occupied_by': None,
        'offset': Vec3(0.0, 0.58, -0.35),
    },

    # --- Bathroom Toilet ---
    {
        'name': 'Bathroom Toilet',
        'position': Vec3(9.5, 0.0, -3.8),
        'rotation_y': 90,
        'seat_type': 'toilet',
        'occupied_by': None,
        'offset': Vec3(-0.42, 0.92, -0.65),
    },
        # --- Kitchen Table Chairs ---
    {
        'name': 'Kitchen Chair Front',
        'position': Vec3(-6.60, 0.0, -4.75),
        'rotation_y': 180,
        'seat_type': 'chair',
        'occupied_by': None,
        'offset': Vec3(0.0, 0.58, -0.12),
    },
    {
        'name': 'Kitchen Chair Back',
        'position': Vec3(-6.60, 0.0, -2.10),
        'rotation_y': 0,
        'seat_type': 'chair',
        'occupied_by': None,
        'offset': Vec3(0.0, 0.58, 0.12),
    },
]


bed_points = [
    {
        'name': 'King Bed Left',
        'position': Vec3(6.55, 0.0, 5.55),
        'rotation_y': 90,
        'occupied_by': None,
        'offset': Vec3(-0.10, 1.55, 0.00),
        'stand_position': Vec3(5.35, 0.85, 5.35),
    },
    {
        'name': 'King Bed Right',
        'position': Vec3(7.65, 0.0, 5.55),
        'rotation_y': 90,
        'occupied_by': None,
        'offset': Vec3(0.10, 1.55, 0.00),
        'stand_position': Vec3(8.95, 0.85, 5.35),
    },
    {
        'name': 'Single Bed',
        'position': Vec3(4.75, 0.0, 5.65),
        'rotation_y': 90,
        'occupied_by': None,
        'offset': Vec3(0.00, 1.20, 0.00),
        'stand_position': Vec3(3.85, 0.85, 5.20),
    },
]

# --------------------------------------------------
# SENSOR ZONES
# --------------------------------------------------

door_zone = create_zone(position=(0, 1.0, -8.1), scale=(2.2, 2.2, 2.4), tint=color.rgba(0, 150, 255, 35))
kitchen_zone = create_zone(position=(-5.0, 1.0, -5.0), scale=(8.2, 2.2, 7.0), tint=color.rgba(255, 170, 0, 35))
bathroom_zone = create_zone(position=(7.0, 1.0, -5.0), scale=(7.5, 2.2, 7.5), tint=color.rgba(80, 180, 255, 35))

door_zone_active_a = False
door_zone_active_b = False

kitchen_zone_active_a = False
kitchen_zone_active_b = False

bathroom_zone_active_a = False
bathroom_zone_active_b = False

# --------------------------------------------------
# DEVICE PANEL
# --------------------------------------------------

def update_device_panel():
    door_state = 'OPEN' if front_door.is_open else 'CLOSED'
    lamp_state = 'ON' if living_lamp.is_on else 'OFF'
    outlet_state = 'ON' if kitchen_outlet.is_on else 'OFF'
    toaster_state = 'ON' if toaster_device.is_on else 'OFF'
    coffee_state = 'ON' if coffee_device.is_on else 'OFF'
    oven_state = 'ON' if oven_device.is_on else 'OFF'
    sink_state = 'ON' if sink_device.is_on else 'OFF'

    set_ui_text(
        device_text,
        'Devices:\n'
        f'Door: {door_state} | Lamp: {lamp_state}\n'
        f'Outlet: {outlet_state} | Toaster: {toaster_state}\n'
        f'Coffee: {coffee_state} | Oven: {oven_state}\n'
        f'Bathroom Sink: {sink_state}',
        color.black
    )

update_device_panel()
update_event_panel()
update_scenario_text()

kitchen_outlet.set_state(True, silent=True)

# --------------------------------------------------
# INTERACTION HELPERS
# --------------------------------------------------

def get_device_world_position(device):
    if isinstance(device, AnimatedDoor):
        return device.pivot.world_position
    return device.entity.world_position


def get_nearest_device_for(actor_entity, max_distance=4.0):
    nearest = None
    nearest_dist = 9999.0

    for device in all_devices:
        pos = get_device_world_position(device)
        dist = distance(actor_entity.world_position, pos)
        if dist < nearest_dist and dist <= max_distance:
            nearest = device
            nearest_dist = dist

    return nearest, nearest_dist

def get_nearest_seat_for(actor_entity, actor_id, max_distance=4.2):
    nearest = None
    nearest_dist = 9999.0

    for seat in seat_points:
        if seat.get('occupied_by') not in (None, actor_id):
            continue

        dist = distance(actor_entity.world_position, seat['position'])
        if dist < nearest_dist and dist <= max_distance:
            nearest = seat
            nearest_dist = dist

    return nearest, nearest_dist


def play_actor_anim(actor, anim_name, loop=False):
    if actor is None:
        return

    if anim_name not in actor.getAnimNames():
        return

    if loop:
        actor.loop(anim_name)
    else:
        actor.play(anim_name)


def set_move_target_for(actor_id, world_point, should_log=True):
    global move_target_a, move_target_a_active, move_target_b, move_target_b_active

    if world_point is None:
        return

    target = Vec3(
        clamp(world_point.x, -10.3, 10.3),
        0,
        clamp(world_point.z, -9.8, 8.4)
    )

    if actor_id == 'A':
        move_target_a = target
        move_target_a_active = True
        if should_log:
            log_event(
                'manual_move_target_set',
                f'A move target -> x:{target.x:.2f}, z:{target.z:.2f}',
                actor_id='A',
                actor_entity=player_a,
                room_name_override=current_room_a
            )
    elif actor_id == 'B':
        move_target_b = target
        move_target_b_active = True
        if should_log:
            log_event(
                'manual_move_target_set',
                f'B move target -> x:{target.x:.2f}, z:{target.z:.2f}',
                actor_id='B',
                actor_entity=player_b,
                room_name_override=current_room_b
            )

def get_hovered_device():
    hovered = mouse.hovered_entity
    if hovered and hasattr(hovered, 'smart_device'):
        return hovered.smart_device
    return None



def set_device_highlight(device):
    global highlighted_device

    if highlighted_device is device:
        return

    if highlighted_device and hasattr(highlighted_device, 'indicator'):
        highlighted_device.indicator.scale = DEFAULT_INDICATOR_SCALE

    highlighted_device = device

    if highlighted_device and hasattr(highlighted_device, 'indicator'):
        highlighted_device.indicator.scale = HIGHLIGHT_INDICATOR_SCALE


def clear_device_highlight():
    global highlighted_device
    if highlighted_device and hasattr(highlighted_device, 'indicator'):
        highlighted_device.indicator.scale = DEFAULT_INDICATOR_SCALE
    highlighted_device = None


def hovered_device_from_mouse():
    hovered = mouse.hovered_entity
    while hovered is not None:
        if hasattr(hovered, 'smart_device'):
            return hovered.smart_device
        hovered = getattr(hovered, 'parent', None)
    return None   


def sit_actor(actor_id):
    global is_seated_a, is_seated_b
    global pose_state_a, pose_state_b
    global seat_target_a, seat_target_b
    global seat_timer_a, seat_timer_b
    global locked_seat_a, locked_seat_b
    global move_target_a_active, move_target_b_active
    global current_anim_a, current_anim_b

    if actor_id == 'A':
        if is_seated_a:
            return

        nearest_seat, nearest_dist = get_nearest_seat_for(player_a, 'A')
        if nearest_seat is None:
            push_notification('A: No seat nearby')
            return

        seat_base = nearest_seat['position']
        seat_offset = nearest_seat.get('offset', Vec3(0, 0.45, 0))
        final_pos = seat_base + seat_offset

        player_a.position = final_pos
        megan_root.position = final_pos
        player_a.y = final_pos.y
        megan_root.rotation_y = nearest_seat['rotation_y']

        play_actor_anim(megan, 'sit_down', loop=False)
        current_anim_a = 'sit_down'
        pose_state_a = 'sit_down'
        seat_timer_a = 1.2
        seat_target_a = nearest_seat
        locked_seat_a = nearest_seat
        nearest_seat['occupied_by'] = 'A'
        move_target_a_active = False

        log_event(
            'sit_down_started',
            f"A started sitting on {nearest_seat['name']}",
            actor_id='A',
            actor_entity=player_a,
            room_name_override=current_room_a
        )

    elif actor_id == 'B':
        if is_seated_b:
            return

        nearest_seat, nearest_dist = get_nearest_seat_for(player_b, 'B')
        if nearest_seat is None:
            push_notification('B: No seat nearby')
            return

        seat_base = nearest_seat['position']
        seat_offset = nearest_seat.get('offset', Vec3(0, 0.45, 0))
        final_pos = seat_base + seat_offset

        player_b.position = final_pos
        sophie_root.position = final_pos
        player_b.y = final_pos.y
        sophie_root.rotation_y = nearest_seat['rotation_y']

        play_actor_anim(sophie, 'sit_down', loop=False)
        current_anim_b = 'sit_down'
        pose_state_b = 'sit_down'
        seat_timer_b = 1.2
        seat_target_b = nearest_seat
        locked_seat_b = nearest_seat
        nearest_seat['occupied_by'] = 'B'
        move_target_b_active = False

        log_event(
            'sit_down_started',
            f"B started sitting on {nearest_seat['name']}",
            actor_id='B',
            actor_entity=player_b,
            room_name_override=current_room_b
        )

def stand_actor(actor_id):
    global is_seated_a, is_seated_b
    global pose_state_a, pose_state_b
    global seat_timer_a, seat_timer_b
    global locked_seat_a, locked_seat_b
    global current_anim_a, current_anim_b

    if actor_id == 'A':
        if not is_seated_a:
            return

        play_actor_anim(megan, 'stand_up', loop=False)
        current_anim_a = 'stand_up'
        pose_state_a = 'stand_up'
        seat_timer_a = 1.1
        is_seated_a = False
        if locked_seat_a:
            locked_seat_a['occupied_by'] = None

        log_event(
            'stand_up_started',
            'A started standing up',
            actor_id='A',
            actor_entity=player_a,
            room_name_override=current_room_a
        )

    elif actor_id == 'B':
        if not is_seated_b:
            return

        play_actor_anim(sophie, 'stand_up', loop=False)
        current_anim_b = 'stand_up'
        pose_state_b = 'stand_up'
        seat_timer_b = 1.1
        is_seated_b = False
        if locked_seat_b:
            locked_seat_b['occupied_by'] = None

        log_event(
            'stand_up_started',
            'B started standing up',
            actor_id='B',
            actor_entity=player_b,
            room_name_override=current_room_b
        )

def get_nearest_bed_for(actor_entity, actor_id, max_distance=6.0):
    candidates = []

    for bed_point in bed_points:
        if bed_point['occupied_by'] not in (None, actor_id):
            continue

        # Megan sadece büyük yatağı kullansın
        if actor_id == 'A' and 'King Bed' not in bed_point['name']:
            continue

        # Sophie sadece tek kişilik yatağı kullansın
        if actor_id == 'B' and 'Single Bed' not in bed_point['name']:
            continue

        dist = distance(actor_entity.position, bed_point['position'])
        if dist <= max_distance:
            candidates.append((bed_point, dist))

    if not candidates:
        return None, 9999.0

    candidates.sort(key=lambda x: x[1])
    return candidates[0]


def lie_actor(actor_id):
    global is_lying_a, is_lying_b
    global lying_target_a, lying_target_b
    global pose_state_a, pose_state_b
    global current_anim_a, current_anim_b

    actor_entity = player_a if actor_id == 'A' else player_b
    actor_root = megan_root if actor_id == 'A' else sophie_root
    actor_model = megan if actor_id == 'A' else sophie

    nearest_bed, _ = get_nearest_bed_for(actor_entity, actor_id)

    if nearest_bed is None:
        push_notification(f'{actor_id}: No bed nearby')
        return

    nearest_bed['occupied_by'] = actor_id

    bed_base = nearest_bed['position']
    bed_offset = nearest_bed.get('offset', Vec3(0, 1.18, 0))
    final_pos = bed_base + bed_offset

    actor_entity.position = final_pos
    actor_root.position = final_pos
    actor_root.rotation_y = nearest_bed['rotation_y']

        # lying animasyonu yatağın eksenine daha iyi otursun
    if actor_id == 'A':
        megan_root.rotation_x = 0
        megan_root.rotation_z = 0
    else:
        sophie_root.rotation_x = 0
        sophie_root.rotation_z = 0

    if actor_id == 'A':
        is_lying_a = True
        lying_target_a = nearest_bed
        pose_state_a = 'lie_down'
    else:
        is_lying_b = True
        lying_target_b = nearest_bed
        pose_state_b = 'lie_down'

    if actor_model and 'lie_down' in actor_model.getAnimNames():
        actor_model.play('lie_down')

    log_event(
        'lie_down_started',
        f'{actor_id} started lying on {nearest_bed["name"]}',
        actor_id=actor_id,
        actor_entity=actor_entity,
        room_name_override=get_room_name(actor_entity.position)
    )

def get_up_actor(actor_id):
    global is_lying_a, is_lying_b
    global lying_target_a, lying_target_b
    global pose_state_a, pose_state_b
    global current_anim_a, current_anim_b

    actor_entity = player_a if actor_id == 'A' else player_b
    actor_root = megan_root if actor_id == 'A' else sophie_root
    actor_model = megan if actor_id == 'A' else sophie

    stand_pos = None

    if actor_id == 'A':
        if lying_target_a:
            stand_pos = lying_target_a.get('stand_position')
            lying_target_a['occupied_by'] = None
        lying_target_a = None
        is_lying_a = False
        pose_state_a = 'get_up_from_bed'
    else:
        if lying_target_b:
            stand_pos = lying_target_b.get('stand_position')
            lying_target_b['occupied_by'] = None
        lying_target_b = None
        is_lying_b = False
        pose_state_b = 'get_up_from_bed'

    if stand_pos is not None:
        actor_entity.position = Vec3(stand_pos.x, stand_pos.y, stand_pos.z)
        actor_root.position = Vec3(stand_pos.x, stand_pos.y, stand_pos.z)

        if actor_id == 'A':
            megan_root.rotation_y = 90
        else:
            sophie_root.rotation_y = 270

    if actor_model and 'get_up_from_bed' in actor_model.getAnimNames():
        actor_model.play('get_up_from_bed')

    log_event(
        'get_up_from_bed_started',
        f'{actor_id} started getting up from bed',
        actor_id=actor_id,
        actor_entity=actor_entity,
        room_name_override=get_room_name(actor_entity.position)
    )

def get_action_actor():
    return active_actor_id

def handle_shared_sit_stand():
    actor_id = get_action_actor()

    if actor_id == 'A':
        if is_seated_a:
            stand_actor('A')
        else:
            sit_actor('A')

    elif actor_id == 'B':
        if is_seated_b:
            stand_actor('B')
        else:
            sit_actor('B')


def handle_shared_lie_getup():
    actor_id = get_action_actor()

    if actor_id == 'A':
        if is_lying_a:
            get_up_actor('A')
        else:
            lie_actor('A')
    else:
        if is_lying_b:
            get_up_actor('B')
        else:
            lie_actor('B')

# --------------------------------------------------
# INPUT
# --------------------------------------------------

def input(key):
    global CAMERA_DISTANCE, active_actor_id

    actor_id = get_action_actor()  # 🔥 bunu en üste al

    if key == 'escape':
        application.quit()

    if key == 'tab':
        active_actor_id = 'B' if active_actor_id == 'A' else 'A'
        push_notification(f'Active Actor: {"Megan" if active_actor_id == "A" else "Sophie"}')
        return

    if key in ('t', 'T'):
        save_vision_frame()
        return

    if key in ('r', 'R'):
        if door_zone_active_a or door_zone_active_b:
            front_door.toggle()
        else:
            push_notification('Go near the front door')
        return

    if key in ('q', 'Q'):
        handle_shared_sit_stand()
        return

    if key in ('f', 'F'):
        handle_shared_lie_getup()
        return

    if key in ('e', 'E'):
        if actor_id == 'A':
            actor_entity = player_a
            room_name = current_room_a
        else:
            actor_entity = player_b
            room_name = current_room_b

        hovered_device = hovered_device_from_mouse()

        if hovered_device:
            hovered_device.toggle()
            log_event(
                'device_interaction',
                f'{actor_id} interacted with {hovered_device.name}',
                actor_id=actor_id,
                actor_entity=actor_entity,
                room_name_override=room_name
            )
        else:
            nearest_device, _ = get_nearest_device_for(actor_entity)
            if nearest_device:
                nearest_device.toggle()
                log_event(
                    'device_interaction',
                    f'{actor_id} interacted with {nearest_device.name}',
                    actor_id=actor_id,
                    actor_entity=actor_entity,
                    room_name_override=room_name
                )
            else:
                push_notification(f'{actor_id}: No device nearby')
        return

    if key == 'left mouse down':
        hovered_device = hovered_device_from_mouse()
        if hovered_device is None and mouse.world_point is not None:
            set_move_target_for(active_actor_id, mouse.world_point, should_log=True)
        return

    if key == 'right mouse down':
        if mouse.world_point is not None:
            set_move_target_for(active_actor_id, mouse.world_point, should_log=True)
        return

    if key == 'scroll up':
        CAMERA_DISTANCE = max(8.0, CAMERA_DISTANCE - CAMERA_ZOOM_SPEED)
        return

    if key == 'scroll down':
        CAMERA_DISTANCE = min(40.0, CAMERA_DISTANCE + CAMERA_ZOOM_SPEED)
        return

# --------------------------------------------------
# UPDATE
# --------------------------------------------------

def update():
    global notification_timer, current_anim_a, current_anim_b
    global current_room_a, current_room_b
    global door_zone_active_a, door_zone_active_b
    global kitchen_zone_active_a, kitchen_zone_active_b
    global bathroom_zone_active_a, bathroom_zone_active_b
    global move_target_a_active, move_target_b_active
    global move_target_a, move_target_b
    global CAMERA_YAW, CAMERA_PITCH
    global last_move_log_pos_a, last_move_log_pos_b
    global startup_camera_timer
    global active_actor_id
    global pose_state_a, pose_state_b
    global is_seated_a, is_seated_b
    global seat_timer_a, seat_timer_b
    global locked_seat_a, locked_seat_b
    global seat_target_a, seat_target_b
    global last_controlled_actor


    if held_keys['right mouse'] and mouse.world_point is not None:
        set_move_target_for(active_actor_id, mouse.world_point, should_log=False)


    # --------------------------------
    # A actor movement
    # --------------------------------

    manual_move_a = Vec3(
        held_keys['d'] - held_keys['a'],
        0,
        held_keys['w'] - held_keys['s']
    )

    move_a = Vec3(0, 0, 0)

    if pose_state_a in ('sit_down', 'sit_idle', 'stand_up', 'lie_down', 'sleep_idle', 'get_up_from_bed'):
        manual_move_a = Vec3(0, 0, 0)
        move_target_a_active = False

        
    if manual_move_a.length() > 0:
        move_a = manual_move_a.normalized()
        move_target_a_active = False
        active_actor_id = 'A'

    elif move_target_a_active and move_target_a is not None:
        delta_a = Vec3(move_target_a.x - player_a.x, 0, move_target_a.z - player_a.z)
        if delta_a.length() <= 0.18:
            move_target_a_active = False
        else:
            move_a = delta_a.normalized()

    is_moving_a = move_a.length() > 0

    if is_moving_a:
        move_with_wall_collision(player_a, move_a, PLAYER_SPEED)

        player_a.x = clamp(player_a.x, -10.3, 10.3)
        player_a.z = clamp(player_a.z, -9.8, 8.4)

        heading_a = math.degrees(math.atan2(move_a.x, move_a.z))
        megan_root.rotation_y = heading_a + 180

    megan_root.position = Vec3(player_a.x, player_a.y, player_a.z)

    if megan:
        if pose_state_a == 'sit_down':
            seat_timer_a -= time.dt
            if seat_timer_a <= 0:
                play_actor_anim(megan, 'sit_idle', loop=True)
                current_anim_a = 'sit_idle'
                pose_state_a = 'sit_idle'
                is_seated_a = True
                log_event(
                    'sit_idle_started',
                    f"A is now seated on {locked_seat_a['name'] if locked_seat_a else 'seat'}",
                    actor_id='A',
                    actor_entity=player_a,
                    room_name_override=current_room_a
                )

        elif pose_state_a == 'stand_up':
            seat_timer_a -= time.dt
            if seat_timer_a <= 0:
                play_actor_anim(megan, 'idle', loop=True)
                current_anim_a = 'idle'
                pose_state_a = 'idle'
                locked_seat_a = None
                player_a.y = 0.85
                megan_root.y = 0.85
                log_event(
                    'stand_up_completed',
                    'A is now standing',
                    actor_id='A',
                    actor_entity=player_a,
                    room_name_override=current_room_a
                )

        elif pose_state_a == 'lie_down':
            if current_anim_a != 'lie_down':
                play_actor_anim(megan, 'lie_down', loop=False)
                current_anim_a = 'lie_down'

            if not megan.getCurrentAnim():
                play_actor_anim(megan, 'sleep_idle', loop=True)
                current_anim_a = 'sleep_idle'
                pose_state_a = 'sleep_idle'
                log_event(
                    'sleep_idle_started',
                    'A is now lying on bed',
                    actor_id='A',
                    actor_entity=player_a,
                    room_name_override=current_room_a
                )

        elif pose_state_a == 'get_up_from_bed':
            if current_anim_a != 'get_up_from_bed':
                play_actor_anim(megan, 'get_up_from_bed', loop=False)
                current_anim_a = 'get_up_from_bed'

            if not megan.getCurrentAnim():
                play_actor_anim(megan, 'idle', loop=True)
                current_anim_a = 'idle'
                pose_state_a = 'idle'
                log_event(
                    'get_up_from_bed_completed',
                    'A got up from bed',
                    actor_id='A',
                    actor_entity=player_a,
                    room_name_override=current_room_a
                )

        elif pose_state_a == 'sit_idle':
            if current_anim_a != 'sit_idle':
                play_actor_anim(megan, 'sit_idle', loop=True)
                current_anim_a = 'sit_idle'

        elif pose_state_a == 'sleep_idle':
            if current_anim_a != 'sleep_idle':
                play_actor_anim(megan, 'sleep_idle', loop=True)
                current_anim_a = 'sleep_idle'

        elif pose_state_a == 'idle':
            if is_moving_a:
                if current_anim_a != 'walk':
                    play_actor_anim(megan, 'walk', loop=True)
                    current_anim_a = 'walk'
            else:
                if current_anim_a != 'idle':
                    play_actor_anim(megan, 'idle', loop=True)
                    current_anim_a = 'idle'

    # --------------------------------
    # seat animation flow A
    # --------------------------------
    if pose_state_a == 'sit_down':
        seat_timer_a -= time.dt
        if seat_timer_a <= 0:
            play_actor_anim(megan, 'sit_idle', loop=True)
            current_anim_a = 'sit_idle'
            pose_state_a = 'sit_idle'
            is_seated_a = True
            log_event(
                'sit_idle_started',
                f"A is now seated on {locked_seat_a['name'] if locked_seat_a else 'seat'}",
                actor_id='A',
                actor_entity=player_a,
                room_name_override=current_room_a
            )

    elif pose_state_a == 'stand_up':
        seat_timer_a -= time.dt
        if seat_timer_a <= 0:
            play_actor_anim(megan, 'idle', loop=True)
            current_anim_a = 'idle'
            pose_state_a = 'idle'
            locked_seat_a = None
            log_event(
                'stand_up_completed',
                'A is now standing',
                actor_id='A',
                actor_entity=player_a,
                room_name_override=current_room_a
            )

    if megan and pose_state_a == 'idle':
        if is_moving_a and 'walk' in megan.getAnimNames():
            if current_anim_a != 'walk':
                megan.loop('walk')
                current_anim_a = 'walk'
        elif not is_moving_a and 'idle' in megan.getAnimNames():
            if current_anim_a != 'idle':
                megan.loop('idle')
                current_anim_a = 'idle'


    # --------------------------------
    # B actor movement
    # --------------------------------
    # YENİ — B her zaman ok tuşları

    manual_move_b = Vec3(
        held_keys['right arrow'] - held_keys['left arrow'],
        0,
        held_keys['up arrow'] - held_keys['down arrow']
    )

    move_b = Vec3(0, 0, 0)

    if pose_state_b in ('sit_down', 'sit_idle', 'stand_up', 'lie_down', 'sleep_idle', 'get_up_from_bed'):
        manual_move_b = Vec3(0, 0, 0)
        move_target_b_active = False

    if manual_move_b.length() > 0:
        move_b = manual_move_b.normalized()
        move_target_b_active = False
        active_actor_id = 'B'

    elif move_target_b_active and move_target_b is not None:
        delta_b = Vec3(move_target_b.x - player_b.x, 0, move_target_b.z - player_b.z)
        if delta_b.length() <= 0.18:
            move_target_b_active = False
        else:
            move_b = delta_b.normalized()

    is_moving_b = move_b.length() > 0

    if is_moving_b:
        move_with_wall_collision(player_b, move_b, PLAYER_SPEED)

        player_b.x = clamp(player_b.x, -10.3, 10.3)
        player_b.z = clamp(player_b.z, -9.8, 8.4)

        heading_b = math.degrees(math.atan2(move_b.x, move_b.z))
        sophie_root.rotation_y = heading_b + 180

    sophie_root.position = Vec3(player_b.x, player_b.y, player_b.z)

    if sophie:
        if pose_state_b == 'sit_down':
            seat_timer_b -= time.dt
            if seat_timer_b <= 0:
                play_actor_anim(sophie, 'sit_idle', loop=True)
                current_anim_b = 'sit_idle'
                pose_state_b = 'sit_idle'
                is_seated_b = True
                log_event(
                    'sit_idle_started',
                    f"B is now seated on {locked_seat_b['name'] if locked_seat_b else 'seat'}",
                    actor_id='B',
                    actor_entity=player_b,
                    room_name_override=current_room_b
                )

        elif pose_state_b == 'stand_up':
            seat_timer_b -= time.dt
            if seat_timer_b <= 0:
                play_actor_anim(sophie, 'idle', loop=True)
                current_anim_b = 'idle'
                pose_state_b = 'idle'
                locked_seat_b = None
                player_b.y = 0.85
                sophie_root.y = 0.85
                log_event(
                    'stand_up_completed',
                    'B is now standing',
                    actor_id='B',
                    actor_entity=player_b,
                    room_name_override=current_room_b
                )

        elif pose_state_b == 'lie_down':
            if current_anim_b != 'lie_down':
                play_actor_anim(sophie, 'lie_down', loop=False)
                current_anim_b = 'lie_down'

            if not sophie.getCurrentAnim():
                play_actor_anim(sophie, 'sleep_idle', loop=True)
                current_anim_b = 'sleep_idle'
                pose_state_b = 'sleep_idle'
                log_event(
                    'sleep_idle_started',
                    'B is now lying on bed',
                    actor_id='B',
                    actor_entity=player_b,
                    room_name_override=current_room_b
                )

        elif pose_state_b == 'get_up_from_bed':
            if current_anim_b != 'get_up_from_bed':
                play_actor_anim(sophie, 'get_up_from_bed', loop=False)
                current_anim_b = 'get_up_from_bed'

            if not sophie.getCurrentAnim():
                play_actor_anim(sophie, 'idle', loop=True)
                current_anim_b = 'idle'
                pose_state_b = 'idle'
                log_event(
                    'get_up_from_bed_completed',
                    'B got up from bed',
                    actor_id='B',
                    actor_entity=player_b,
                    room_name_override=current_room_b
                )

        elif pose_state_b == 'sit_idle':
            if current_anim_b != 'sit_idle':
                play_actor_anim(sophie, 'sit_idle', loop=True)
                current_anim_b = 'sit_idle'

        elif pose_state_b == 'sleep_idle':
            if current_anim_b != 'sleep_idle':
                play_actor_anim(sophie, 'sleep_idle', loop=True)
                current_anim_b = 'sleep_idle'

        elif pose_state_b == 'idle':
            if is_moving_b:
                if current_anim_b != 'walk':
                    play_actor_anim(sophie, 'walk', loop=True)
                    current_anim_b = 'walk'
            else:
                if current_anim_b != 'idle':
                    play_actor_anim(sophie, 'idle', loop=True)
                    current_anim_b = 'idle'

    # --------------------------------
    # seat animation flow B
    # --------------------------------
    if pose_state_b == 'sit_down':
        seat_timer_b -= time.dt
        if seat_timer_b <= 0:
            play_actor_anim(sophie, 'sit_idle', loop=True)
            current_anim_b = 'sit_idle'
            pose_state_b = 'sit_idle'
            is_seated_b = True
            log_event(
                'sit_idle_started',
                f"B is now seated on {locked_seat_b['name'] if locked_seat_b else 'seat'}",
                actor_id='B',
                actor_entity=player_b,
                room_name_override=current_room_b
            )

    elif pose_state_b == 'stand_up':
        seat_timer_b -= time.dt
        if seat_timer_b <= 0:
            play_actor_anim(sophie, 'idle', loop=True)
            current_anim_b = 'idle'
            pose_state_b = 'idle'
            locked_seat_b = None
            log_event(
                'stand_up_completed',
                'B is now standing',
                actor_id='B',
                actor_entity=player_b,
                room_name_override=current_room_b
            )

    if sophie and pose_state_b == 'idle':
        if is_moving_b and 'walk' in sophie.getAnimNames():
            if current_anim_b != 'walk':
                sophie.loop('walk')
                current_anim_b = 'walk'
        elif not is_moving_b and 'idle' in sophie.getAnimNames():
            if current_anim_b != 'idle':
                sophie.loop('idle')
                current_anim_b = 'idle'

    # --------------------------------
    # sampled movement logging
    # --------------------------------
    if last_move_log_pos_a is None:
        last_move_log_pos_a = Vec3(player_a.x, player_a.y, player_a.z)
    if last_move_log_pos_b is None:
        last_move_log_pos_b = Vec3(player_b.x, player_b.y, player_b.z)

    if pose_state_a == 'idle' and distance(player_a.position, last_move_log_pos_a) >= 1.0:
        log_event(
            'player_move',
            f'A moved to x:{player_a.x:.2f}, z:{player_a.z:.2f}',
            actor_id='A',
            actor_entity=player_a,
            room_name_override=current_room_a
        )
        last_move_log_pos_a = Vec3(player_a.x, player_a.y, player_a.z)

    if pose_state_b == 'idle' and distance(player_b.position, last_move_log_pos_b) >= 1.0:
        log_event(
            'player_move',
            f'B moved to x:{player_b.x:.2f}, z:{player_b.z:.2f}',
            actor_id='B',
            actor_entity=player_b,
            room_name_override=current_room_b
        )
        last_move_log_pos_b = Vec3(player_b.x, player_b.y, player_b.z)



    # --------------------------------
    # camera follow both
    # --------------------------------
    midpoint = Vec3(
        (player_a.x + player_b.x) / 2,
        0,
        (player_a.z + player_b.z) / 2
    )

    if startup_camera_timer > 0:
        startup_camera_timer -= time.dt
        camera.position = Vec3(0, 24, -28)
        camera.look_at(Vec3(0, 0, 0))
    else:
        players_dist = distance(player_a.position, player_b.position)

        cam_height = 19 + min(players_dist * 0.45, 6.0)
        cam_back = 18 + min(players_dist * 0.50, 7.0)

        cam_target = midpoint + Vec3(0, cam_height, -cam_back)

        camera.position = cam_target
        camera.look_at(midpoint)



    # --------------------------------
    # UI
    # --------------------------------
    active_name = 'Megan' if active_actor_id == 'A' else 'Sophie'

    set_ui_text(
        hint_text,
        f'Active: {active_name} | TAB switch | WASD move | Q sit/stand | E interact | R door',
     
        color.black
    )

    nearest_a, nearest_dist_a = get_nearest_device_for(player_a)
    nearest_b, nearest_dist_b = get_nearest_device_for(player_b)

    hovered_device = hovered_device_from_mouse()

    if hovered_device is not None:
        set_device_highlight(hovered_device)
    elif nearest_a:
        set_device_highlight(nearest_a)
    elif nearest_b:
        set_device_highlight(nearest_b)
    else:
        clear_device_highlight()

    a_hint = f'A: {nearest_a.name} ({nearest_dist_a:.2f}m) -> E' if nearest_a else 'A: -'
    b_hint = f'B: {nearest_b.name} ({nearest_dist_b:.2f}m) -> Right Shift' if nearest_b else 'B: -'

    set_ui_text(interaction_text, f'{a_hint} | {b_hint}', color.azure)
    set_ui_text(
    hint_text,
    f'Active Actor: {active_actor_id} | Mouse click moves active actor | Middle drag camera',
    color.black
)

    if notification_timer > 0:
        notification_timer -= time.dt
        if notification_timer <= 0:
            set_ui_text(notification_text, '', color.black)

    # --------------------------------
    # room tracking A
    # --------------------------------
    new_room_a = get_room_name(player_a.position)
    if new_room_a != current_room_a:
        current_room_a = new_room_a
        log_event(
            f'room_changed_{current_room_a.lower().replace(" ", "_")}',
            f'A entered: {current_room_a}',
            actor_id='A',
            actor_entity=player_a,
            room_name_override=current_room_a
        )

    # --------------------------------
    # room tracking B
    # --------------------------------
    new_room_b = get_room_name(player_b.position)
    if new_room_b != current_room_b:
        current_room_b = new_room_b
        log_event(
            f'room_changed_{current_room_b.lower().replace(" ", "_")}',
            f'B entered: {current_room_b}',
            actor_id='B',
            actor_entity=player_b,
            room_name_override=current_room_b
        )

    set_ui_text(room_text, f'A Room: {current_room_a} | B Room: {current_room_b}', color.black)

    # --------------------------------
    # zone tracking A
    # --------------------------------
    in_door_zone_a = door_zone.intersects(player_a).hit
    if in_door_zone_a and not door_zone_active_a:
        door_zone_active_a = True
        log_event('door_zone_entered', 'A entered front door zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)
    elif not in_door_zone_a and door_zone_active_a:
        door_zone_active_a = False
        log_event('door_zone_exited', 'A exited front door zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)

    in_kitchen_zone_a = kitchen_zone.intersects(player_a).hit
    if in_kitchen_zone_a and not kitchen_zone_active_a:
        kitchen_zone_active_a = True
        log_event('kitchen_zone_entered', 'A entered kitchen zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)
    elif not in_kitchen_zone_a and kitchen_zone_active_a:
        kitchen_zone_active_a = False
        log_event('kitchen_zone_exited', 'A exited kitchen zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)

    in_bathroom_zone_a = bathroom_zone.intersects(player_a).hit
    if in_bathroom_zone_a and not bathroom_zone_active_a:
        bathroom_zone_active_a = True
        log_event('bathroom_zone_entered', 'A entered bathroom zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)
    elif not in_bathroom_zone_a and bathroom_zone_active_a:
        bathroom_zone_active_a = False
        log_event('bathroom_zone_exited', 'A exited bathroom zone', actor_id='A', actor_entity=player_a, room_name_override=current_room_a)

    # --------------------------------
    # zone tracking B
    # --------------------------------
    in_door_zone_b = door_zone.intersects(player_b).hit
    if in_door_zone_b and not door_zone_active_b:
        door_zone_active_b = True
        log_event('door_zone_entered', 'B entered front door zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)
    elif not in_door_zone_b and door_zone_active_b:
        door_zone_active_b = False
        log_event('door_zone_exited', 'B exited front door zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)

    in_kitchen_zone_b = kitchen_zone.intersects(player_b).hit
    if in_kitchen_zone_b and not kitchen_zone_active_b:
        kitchen_zone_active_b = True
        log_event('kitchen_zone_entered', 'B entered kitchen zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)
    elif not in_kitchen_zone_b and kitchen_zone_active_b:
        kitchen_zone_active_b = False
        log_event('kitchen_zone_exited', 'B exited kitchen zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)

    in_bathroom_zone_b = bathroom_zone.intersects(player_b).hit
    if in_bathroom_zone_b and not bathroom_zone_active_b:
        bathroom_zone_active_b = True
        log_event('bathroom_zone_entered', 'B entered bathroom zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)
    elif not in_bathroom_zone_b and bathroom_zone_active_b:
        bathroom_zone_active_b = False
        log_event('bathroom_zone_exited', 'B exited bathroom zone', actor_id='B', actor_entity=player_b, room_name_override=current_room_b)

    door_pivot.rotation_y = lerp(door_pivot.rotation_y, front_door.target_y, 6 * time.dt)
    bedroom_hall_pivot.rotation_y = lerp(bedroom_hall_pivot.rotation_y, bedroom_door.target_y, 6 * time.dt)
    bathroom_hall_pivot.rotation_y = lerp(bathroom_hall_pivot.rotation_y, bathroom_door.target_y, 6 * time.dt)

    # vision camera A actor üzerinde kalsın
    mid_x = (player_a.x + player_b.x) / 2
    mid_z = (player_a.z + player_b.z) / 2

 
    CAM_HEIGHT = 7.0      
    CAM_OFFSET_Z = -5.5  

    vision_cam_A.setPos(player_a.x, CAM_HEIGHT, player_a.z + CAM_OFFSET_Z)
    vision_cam_A.lookAt(player_a.x, 1.0, player_a.z)

    vision_cam_B.setPos(player_b.x, CAM_HEIGHT, player_b.z + CAM_OFFSET_Z)
    vision_cam_B.lookAt(player_b.x, 1.0, player_b.z)

    if held_keys['t']:
        print(f"A cam pos: {vision_cam_A.getPos()}")
        print(f"B cam pos: {vision_cam_B.getPos()}")

# --------------------------------------------------
# STARTUP EVENTS
# --------------------------------------------------

log_event('system_ready', 'Scene loaded', actor_id='SYSTEM', actor_entity=None, room_name_override='-')
push_notification('Digital twin ready')

app.run()