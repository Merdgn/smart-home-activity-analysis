from ursina import *
from pathlib import Path
from panda3d.core import Filename
from direct.actor.Actor import Actor

# --------------------------------------------------
# PATHS
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'
CHARACTERS_PATH = ASSETS_PATH / 'characters' / 'exported'

# --------------------------------------------------
# APP
# --------------------------------------------------

app = Ursina()
application.asset_folder = ASSETS_PATH

window.title = 'Sophie Animation Test'
window.borderless = False
window.exit_button.visible = True
window.fps_counter.enabled = True
window.color = color.rgb(210, 230, 240)

# --------------------------------------------------
# SCENE
# --------------------------------------------------

ground = Entity(
    model='plane',
    scale=(12, 1, 12),
    texture='white_cube',
    texture_scale=(12, 12),
    color=color.light_gray
)

sun = DirectionalLight()
sun.look_at(Vec3(1, -1, -1))

ambient = AmbientLight()
ambient.color = color.rgba(120, 120, 120, 0.8)

Sky()

# --------------------------------------------------
# SOPHIE FILE PATHS
# --------------------------------------------------

idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_idle.glb').resolve())
).getFullpath()

walk_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'sophie_walk.glb').resolve())
).getFullpath()

print('idle_path =', idle_path)
print('walk_path =', walk_path)

# --------------------------------------------------
# LOAD ACTOR
# --------------------------------------------------

sophie_root = Entity(position=(0, 0, 0))
sophie = None

try:
    sophie = Actor(
        idle_path,
        {
            'idle': idle_path,
            'walk': walk_path,
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

        target_size = 1.8
        uniform_scale = target_size / max_dim
        sophie.setScale(uniform_scale)

        min_b, max_b = sophie.getTightBounds()
        center_x = (min_b.x + max_b.x) / 2
        center_z = (min_b.z + max_b.z) / 2
        sophie.setPos(-center_x, -min_b.y, -center_z)

    sophie.setH(180)

    anim_names = sophie.getAnimNames()
    print('Anim names =', anim_names)

    if 'idle' in anim_names:
        sophie.loop('idle')
    elif anim_names:
        sophie.loop(anim_names[0])

except Exception as e:
    print(f'[SOPHIE ACTOR ERROR] {e}')

# --------------------------------------------------
# CAMERA
# --------------------------------------------------

camera.position = (0, 1.8, -5)
camera.look_at(Vec3(0, 1.0, 0))

# --------------------------------------------------
# UI
# --------------------------------------------------

info_text = Text(
    text='1 = idle | 2 = walk | ESC = exit',
    position=(-0.85, 0.45),
    scale=1.0,
    background=True
)

status_text = Text(
    text='Sophie test ready',
    position=(-0.85, 0.40),
    scale=1.0,
    background=True
)

# --------------------------------------------------
# INPUT
# --------------------------------------------------

def input(key):
    if key == '1':
        if sophie and 'idle' in sophie.getAnimNames():
            sophie.loop('idle')
            status_text.text = 'Animation: idle'

    elif key == '2':
        if sophie and 'walk' in sophie.getAnimNames():
            sophie.loop('walk')
            status_text.text = 'Animation: walk'

    elif key == 'escape':
        application.quit()

# --------------------------------------------------
# RUN
# --------------------------------------------------

app.run()