from ursina import *
from pathlib import Path
from panda3d.core import Filename

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'

app = Ursina()
application.asset_folder = ASSETS_PATH

window.title = 'Test Couch BAM'
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
ambient.color = color.rgba(120, 120, 120, 0.8)

Sky()

camera.position = (0, 6, -12)
camera.rotation_x = 25

info_text = Text(
    text='Q/E rotate | Z/X scale | WASD move | R/F up-down | ESC exit',
    position=(-0.85, 0.45),
    scale=1.0,
    background=True
)

status_text = Text(
    text='Couch_Small2.bam yukleniyor...',
    position=(-0.85, 0.40),
    scale=1.0,
    background=True
)

couch_path = (ASSETS_PATH / 'models_bam' / 'Couch_Small2.bam').resolve()

if not couch_path.exists():
    raise FileNotFoundError(f'BAM bulunamadi: {couch_path}')

panda_path = Filename.from_os_specific(str(couch_path))

couch = app.loader.loadModel(panda_path)
couch.reparentTo(app.render)
couch.setPos(0, 0, 0)
couch.setScale(1.0)
couch.setHpr(0, 0, 0)

current_scale = 1.0
current_rot_y = 0.0

def update_status():
    pos = couch.getPos()
    status_text.text = (
        f'pos=({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f}) | '
        f'scale={current_scale:.2f} | '
        f'rotY={current_rot_y:.1f}'
    )

update_status()

def input(key):
    global current_scale, current_rot_y

    if key == 'escape':
        application.quit()

    if key == 'q':
        current_rot_y -= 10
        couch.setH(current_rot_y)
    elif key == 'e':
        current_rot_y += 10
        couch.setH(current_rot_y)
    elif key == 'z':
        current_scale *= 0.9
        couch.setScale(current_scale)
    elif key == 'x':
        current_scale *= 1.1
        couch.setScale(current_scale)
    elif key == 'w':
        couch.setY(couch.getY() + 0.2)
    elif key == 's':
        couch.setY(couch.getY() - 0.2)
    elif key == 'a':
        couch.setX(couch.getX() - 0.2)
    elif key == 'd':
        couch.setX(couch.getX() + 0.2)
    elif key == 'r':
        couch.setZ(couch.getZ() + 0.2)
    elif key == 'f':
        couch.setZ(couch.getZ() - 0.2)

    update_status()

app.run()