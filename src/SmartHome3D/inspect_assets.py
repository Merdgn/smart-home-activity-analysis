from ursina import *
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'

app = Ursina()
application.asset_folder = ASSETS_PATH

window.title = 'Asset Inspector'
window.borderless = False
window.exit_button.visible = True
window.fps_counter.enabled = True
window.color = color.rgb(210, 230, 240)

ground = Entity(
    model='plane',
    scale=(20, 1, 20),
    texture='white_cube',
    texture_scale=(20, 20),
    color=color.light_gray
)

sun = DirectionalLight()
sun.look_at(Vec3(1, -1, -1))

ambient = AmbientLight()
ambient.color = color.rgba(120, 120, 120, 0.7)

Sky()

camera.position = (0, 6, -12)
camera.rotation_x = 25

info_text = Text(
    text='1=Couch | 2=Carpet | 3=Table | 4=Window | Q/E rotate | Z/X scale | WASD move | R/F up-down',
    position=(-0.85, 0.45),
    scale=1.0,
    background=True
)

status_text = Text(
    text='Hazir',
    position=(-0.85, 0.40),
    scale=1.0,
    background=True
)

current_entity = None
current_name = ''

asset_map = {
    '1': 'Couch_Small2.obj',
    '2': 'Carpet_Round.obj',
    '3': 'Table_RoundSmall.obj',
    '4': 'Window_Small1.obj',
}

def load_asset(file_name):
    global current_entity, current_name

    if current_entity:
        destroy(current_entity)
        current_entity = None

    mesh = load_model(file_name)
    if not mesh:
        status_text.text = f'Yuklenemedi: {file_name}'
        return

    current_entity = Entity(
        model=mesh,
        position=(0, 0, 0),
        scale=1.0,
        rotation=(0, 0, 0),
        color=color.white
    )
    current_name = file_name
    status_text.text = f'Loaded: {file_name}'

def input(key):
    global current_entity

    if key == 'escape':
        application.quit()

    if key in asset_map:
        load_asset(asset_map[key])

    if not current_entity:
        return

    if key == 'q':
        current_entity.rotation_y -= 10
    elif key == 'e':
        current_entity.rotation_y += 10
    elif key == 'z':
        current_entity.scale *= 0.9
    elif key == 'x':
        current_entity.scale *= 1.1
    elif key == 'w':
        current_entity.z += 0.2
    elif key == 's':
        current_entity.z -= 0.2
    elif key == 'a':
        current_entity.x -= 0.2
    elif key == 'd':
        current_entity.x += 0.2
    elif key == 'r':
        current_entity.y += 0.2
    elif key == 'f':
        current_entity.y -= 0.2

    status_text.text = (
        f'{current_name} | '
        f'pos=({current_entity.x:.2f}, {current_entity.y:.2f}, {current_entity.z:.2f}) | '
        f'scale={current_entity.scale} | '
        f'rotY={current_entity.rotation_y:.1f}'
    )

app.run()