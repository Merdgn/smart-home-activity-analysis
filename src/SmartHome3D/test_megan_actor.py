from ursina import *
from pathlib import Path
from panda3d.core import Filename
from direct.actor.Actor import Actor

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'
CHARACTERS_PATH = ASSETS_PATH / 'characters' / 'exported'

app = Ursina()
application.asset_folder = ASSETS_PATH

window.title = 'Megan Animation Test'
window.borderless = False
window.exit_button.visible = True
window.fps_counter.enabled = True
window.color = color.rgb(210, 230, 240)

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

idle_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_idle.glb').resolve())
).getFullpath()

walk_path = Filename.from_os_specific(
    str((CHARACTERS_PATH / 'megan_walk.glb').resolve())
).getFullpath()

print('idle_path =', idle_path)
print('walk_path =', walk_path)

megan_root = Entity(position=(0, 0, 0))

megan = Actor(
    idle_path,
    {
        'idle': idle_path,
        'walk': walk_path,
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

    target_size = 1.8
    uniform_scale = target_size / max_dim
    megan.setScale(uniform_scale)

    min_b, max_b = megan.getTightBounds()
    center_x = (min_b.x + max_b.x) / 2
    center_z = (min_b.z + max_b.z) / 2
    megan.setPos(-center_x, -min_b.y, -center_z)

megan.setH(180)

anim_names = megan.getAnimNames()
print('Anim names =', anim_names)

if 'walk' in anim_names:
    megan.loop('walk')
elif anim_names:
    megan.loop(anim_names[0])

camera.position = (0, 1.8, -5)
camera.look_at(Vec3(0, 1.0, 0))

info_text = Text(
    text='1=idle | 2=walk | ESC=exit',
    position=(-0.85, 0.45),
    scale=1.0,
    background=True
)

def input(key):
    if key == '1':
        if 'idle' in megan.getAnimNames():
            megan.loop('idle')
    elif key == '2':
        if 'walk' in megan.getAnimNames():
            megan.loop('walk')
    elif key == 'escape':
        application.quit()

app.run()