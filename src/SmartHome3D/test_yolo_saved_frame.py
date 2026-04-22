from pathlib import Path
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CAPTURES_DIR = PROJECT_ROOT / 'assets' / 'captures'

input_image = CAPTURES_DIR / 'vision_test.png'
output_dir = CAPTURES_DIR / 'yolo_output'

print('Input image:', input_image)
print('Output dir :', output_dir)

if not input_image.exists():
    raise FileNotFoundError(f'vision_test.png bulunamadi: {input_image}')

model = YOLO('yolov8n.pt')

results = model.predict(
    source=str(input_image),
    imgsz=640,
    conf=0.25,
    save=True,
    project=str(output_dir),
    name='run1',
    exist_ok=True
)

print('YOLO prediction tamamlandi.')

run_dir = output_dir / 'run1'
candidates = list(run_dir.glob('vision_test.*'))

if candidates:
    print('Annotated image olustu:', candidates[0])
else:
    print('Annotated image bulunamadi, klasoru kontrol et.')