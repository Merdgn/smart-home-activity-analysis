from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_DIR = PROJECT_ROOT / 'assets' / 'models'
TEXTURES_DIR = PROJECT_ROOT / 'assets' / 'textures'

MAP_KEYS = ('map_Kd', 'map_Ka', 'map_Ks', 'map_Bump', 'bump', 'map_d')

if not MODELS_DIR.exists():
    raise FileNotFoundError(f'Models klasoru bulunamadi: {MODELS_DIR}')

if not TEXTURES_DIR.exists():
    raise FileNotFoundError(f'Textures klasoru bulunamadi: {TEXTURES_DIR}')

patched_count = 0

for mtl_path in MODELS_DIR.glob('*.mtl'):
    original = mtl_path.read_text(encoding='utf-8', errors='ignore').splitlines()
    new_lines = []
    changed = False

    for line in original:
        stripped = line.strip()

        matched = False
        for key in MAP_KEYS:
            if stripped.startswith(key + ' '):
                tex_part = stripped[len(key):].strip()

                # opsiyonlar varsa en sondaki dosya adini al
                tex_name = Path(tex_part.replace('\\', '/').split()[-1]).name
                candidate = TEXTURES_DIR / tex_name

                if candidate.exists():
                    new_line = f'{key} ../textures/{tex_name}'
                    new_lines.append(new_line)
                    changed = True
                else:
                    new_lines.append(line)
                matched = True
                break

        if not matched:
            new_lines.append(line)

    if changed:
        mtl_path.write_text('\n'.join(new_lines), encoding='utf-8')
        patched_count += 1
        print(f'[PATCHED] {mtl_path.name}')
    else:
        print(f'[UNCHANGED] {mtl_path.name}')

print(f'\nToplam guncellenen .mtl sayisi: {patched_count}')