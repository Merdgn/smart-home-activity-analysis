from ursina import *
from ursina.prefabs.editor_camera import EditorCamera
from pathlib import Path
from panda3d.core import Filename, TransparencyAttrib
from ursina.shaders import unlit_shader

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'

app = Ursina()
application.asset_folder = ASSETS_PATH

window.title = 'Scene Layout Lab'
window.borderless = False
window.exit_button.visible = True
window.fps_counter.enabled = True
window.color = color.rgb(210, 230, 240)

# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def load_bam_entity(file_name, position=(0, 0, 0), target_size=1.0, rotation=(0, 0, 0), tint=color.white):
    asset_path = (ASSETS_PATH / 'models_bam' / file_name).resolve()

    if not asset_path.exists():
        print(f'[BAM] bulunamadi -> {asset_path}')
        return None

    try:
        wrapper = Entity(
            position=position,
            rotation=rotation
        )

        panda_path = Filename.from_os_specific(str(asset_path))
        node = app.loader.loadModel(panda_path)
        node.reparentTo(wrapper)

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

        # Renk zorla uygula
        node.clearColor()
        node.clearColorScale()
        node.setTextureOff(1)
        node.setMaterialOff(1)
        node.setShaderAuto()
        node.setTransparency(TransparencyAttrib.M_none)
        node.setTwoSided(True)
        node.setColor(tint[0], tint[1], tint[2], tint[3])

        wrapper.model_node = node

        print(f'[BAM] yüklendi -> {file_name}')
        return wrapper

    except Exception as e:
        print(f'[BAM LOAD ERROR] {file_name}: {e}')
        return None


def load_obj_entity(file_name, position=(0, 0, 0), scale=1.0, rotation=(0, 0, 0), tint=color.white):
    asset_path = ASSETS_PATH / 'models' / file_name

    if not asset_path.exists():
        print(f'[OBJ] bulunamadi -> {asset_path}')
        return None

    try:
        mesh = load_model(file_name)
        if not mesh:
            print(f'[OBJ] yuklenemedi -> {file_name}')
            return None

        entity = Entity(
            model=mesh,
            position=position,
            scale=scale,
            rotation=rotation,
            color=tint
        )

        entity.setTextureOff(1)
        entity.setMaterialOff(1)
        entity.setTwoSided(True)

        print(f'[OBJ] yüklendi -> {file_name}')
        return entity

    except Exception as e:
        print(f'[OBJ LOAD ERROR] {file_name}: {e}')
        return None


# --------------------------------------------------
# SCENE
# --------------------------------------------------

ground = Entity(
    model='plane',
    scale=(24, 1, 24),
    texture='white_cube',
    texture_scale=(24, 24),
    color=color.light_gray
)


# --------------------------------------------------
# HOUSE FLOOR PLAN
# --------------------------------------------------

floor_main = Entity(
    model='cube',
    position=(0, -0.55, 0),
    scale=(22, 0.1, 18),
    color=color.rgb(205, 205, 205),
    collider='box'
)

# dış duvarlar
wall_left = Entity(
    model='cube',
    position=(-11, 1.5, 0),
    scale=(0.4, 3, 18),
    color=color.white
)

wall_right = Entity(
    model='cube',
    position=(11, 1.5, 0),
    scale=(0.4, 3, 18),
    color=color.white
)

wall_back = Entity(
    model='cube',
    position=(0, 1.5, 9),
    scale=(22, 3, 0.4),
    color=color.white
)

wall_front_left = Entity(
    model='cube',
    position=(-6.5, 1.5, -9),
    scale=(9, 3, 0.4),
    color=color.white
)

wall_front_right = Entity(
    model='cube',
    position=(6.5, 1.5, -9),
    scale=(9, 3, 0.4),
    color=color.white
)

# ana giriş boşluğu üstüne kapı için alan
main_door_top = Entity(
    model='cube',
    position=(0, 2.55, -9),
    scale=(4, 0.9, 0.4),
    color=color.white
)

# iç bölme duvarı: sağ tarafı iki odaya ayıracak ana dikey duvar
inner_main_split = Entity(
    model='cube',
    position=(3.0, 1.5, 0.0),
    scale=(0.35, 3, 18),
    color=color.white
)

# sağ üst ve sağ alt odaları ayıran yatay duvar
inner_right_split = Entity(
    model='cube',
    position=(7.0, 1.5, 1.5),
    scale=(8.0, 3, 0.35),
    color=color.white
)

# yatak odası kapı boşluğu çevresi
bedroom_door_top = Entity(
    model='cube',
    position=(3.0, 2.55, 4.8),
    scale=(0.35, 0.9, 2.2),
    color=color.white
)

bedroom_door_bottom_part = Entity(
    model='cube',
    position=(3.0, 0.45, 4.8),
    scale=(0.35, 0.9, 2.2),
    color=color.white
)

# banyo kapı boşluğu çevresi
bathroom_door_top = Entity(
    model='cube',
    position=(3.0, 2.55, -4.8),
    scale=(0.35, 0.9, 2.2),
    color=color.white
)

bathroom_door_bottom_part = Entity(
    model='cube',
    position=(3.0, 0.45, -4.8),
    scale=(0.35, 0.9, 2.2),
    color=color.white
)

# tavana sonra tek tuşla aç/kapat yapmak için grup
ceiling_parts = []

ceiling_living = Entity(
    model='cube',
    position=(-4.0, 3.05, 0.0),
    scale=(14, 0.15, 18),
    color=color.rgb(235, 235, 235),
    visible=False
)
ceiling_parts.append(ceiling_living)

ceiling_bedroom = Entity(
    model='cube',
    position=(7.0, 3.05, 5.25),
    scale=(8.0, 0.15, 7.5),
    color=color.rgb(235, 235, 235),
    visible=False
)
ceiling_parts.append(ceiling_bedroom)

ceiling_bathroom = Entity(
    model='cube',
    position=(7.0, 3.05, -5.25),
    scale=(8.0, 0.15, 7.5),
    color=color.rgb(235, 235, 235),
    visible=False
)
ceiling_parts.append(ceiling_bathroom)


Sky()

editor_camera = EditorCamera(
    rotation_speed=100,
    panning_speed=10,
    zoom_speed=2
)
editor_camera.position = (0, 12, -18)
editor_camera.rotation_x = 35

# --------------------------------------------------
# ASSETS
# --------------------------------------------------

assets = {}

assets['carpet'] = load_bam_entity(
    'Carpet_Round.bam',
    position=(-6, 0.01, 4),
    target_size=2.8,
    rotation=(0, 0, 0),
    tint=color.rgb(180, 60, 60)
)

assets['table'] = load_bam_entity(
    'Table_RoundSmall.bam',
    position=(0, 0.0, 4),
    target_size=1.2,
    rotation=(0, 0, 0),
    tint=color.rgb(150, 150, 150)
)

assets['couch'] = load_bam_entity(
    'Couch_Small2.bam',
    position=(6, 0.0, 4),
    target_size=2.3,
    rotation=(0, 180, 0),
    tint=color.rgb(70, 120, 210)
)

assets['lamp'] = load_bam_entity(
    'Light_Stand1.bam',
    position=(-6, 0.0, -2),
    target_size=1.4,
    rotation=(0, 0, 0),
    tint=color.rgb(230, 210, 90)
)

assets['door'] = load_bam_entity(
    'Door_1.bam',
    position=(0, 0.0, -2),
    target_size=2.1,
    rotation=(0, 0, 0),
    tint=color.rgb(140, 90, 50)
)

assets['chair'] = load_obj_entity(
    'Chair_1.obj',
    position=(6, 0.0, -2),
    scale=1.0,
    rotation=(0, 180, 0),
    tint=color.rgb(60, 40, 20)
)

assets['window'] = load_obj_entity(
    'Window_Small1.obj',
    position=(0, 0.5, -7),
    scale=1.6,
    rotation=(0, 90, 0),
    tint=color.rgb(80, 170, 220)
)


# --------------------------------------------------
# UI
# --------------------------------------------------

info_text = Text(
    text='1 carpet | 2 table | 3 couch | 4 lamp | 5 door | 6 chair | 7 window',
    position=(-0.85, 0.45),
    scale=1.0,
    background=True
)

info_text2 = Text(
    text='Arrows move X/Z | R/F Y | Q/E rotate | Z/X scale | ESC exit',
    position=(-0.85, 0.40),
    scale=1.0,
    background=True
)

status_text = Text(
    text='Secili: yok',
    position=(-0.85, 0.35),
    scale=1.0,
    background=True
)

selected_key = None
selected_entity = None


def select_asset(key_name):
    global selected_key, selected_entity
    selected_key = key_name
    selected_entity = assets.get(key_name)
    update_status()


def update_status():
    if not selected_entity:
        status_text.text = 'Secili: yok'
        return

    status_text.text = (
        f'Secili: {selected_key} | '
        f'pos=({selected_entity.x:.2f}, {selected_entity.y:.2f}, {selected_entity.z:.2f}) | '
        f'scale={selected_entity.scale} | '
        f'rot=({selected_entity.rotation_x:.1f}, {selected_entity.rotation_y:.1f}, {selected_entity.rotation_z:.1f})'
    )



def input(key):
    print('BASILAN KEY =', key)

    if key == 'escape':
        application.quit()

    key_map = {
        '1': 'carpet',
        '2': 'table',
        '3': 'couch',
        '4': 'lamp',
        '5': 'door',
        '6': 'chair',
        '7': 'window',

        'numpad 1': 'carpet',
        'numpad 2': 'table',
        'numpad 3': 'couch',
        'numpad 4': 'lamp',
        'numpad 5': 'door',
        'numpad 6': 'chair',
        'numpad 7': 'window',
    }

    if key in key_map:
        select_asset(key_map[key])
        return

    if not selected_entity:
        return

    step = 0.2
    rot_step = 10

    if key == 'left arrow':
        selected_entity.x -= step
    elif key == 'right arrow':
        selected_entity.x += step
    elif key == 'up arrow':
        selected_entity.z += step
    elif key == 'down arrow':
        selected_entity.z -= step
    elif key == 'r':
        selected_entity.y += step
    elif key == 'f':
        selected_entity.y -= step
    elif key == 'q':
        selected_entity.rotation_y -= rot_step
    elif key == 'e':
        selected_entity.rotation_y += rot_step
    elif key == 'z':
        selected_entity.scale *= 0.9
    elif key == 'x':
        selected_entity.scale *= 1.1

    update_status()


app.run()