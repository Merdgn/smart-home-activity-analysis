from pathlib import Path
from panda3d.core import loadPrcFileData, Filename
from direct.showbase.ShowBase import ShowBase

# Pencere açılmasın
loadPrcFileData('', 'window-type none')
loadPrcFileData('', 'audio-library-name null')

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_PATH = PROJECT_ROOT / 'assets'
GLB_DIR = ASSETS_PATH / 'models_glb'
BAM_DIR = ASSETS_PATH / 'models_bam'

BAM_DIR.mkdir(parents=True, exist_ok=True)

FILES = [
    'Kitchen_Fridge',
    'Kitchen_Sink',
    'Kitchen_Oven_Large',
    'Kitchen_Cabinet1',
    'Kitchen_2Drawers',
]

base = ShowBase()

for name in FILES:
    glb_path = GLB_DIR / f'{name}.glb'
    bam_path = BAM_DIR / f'{name}.bam'

    if not glb_path.exists():
        print(f'[YOK] {glb_path}')
        continue

    try:
        model = base.loader.loadModel(Filename.from_os_specific(str(glb_path)))
        model.writeBamFile(Filename.from_os_specific(str(bam_path)))
        print(f'[OK] {name}.glb -> {name}.bam')
    except Exception as e:
        print(f'[HATA] {name}: {e}')

print('Donusum tamamlandi.')
base.destroy()