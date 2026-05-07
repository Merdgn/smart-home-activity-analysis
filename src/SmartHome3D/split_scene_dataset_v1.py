from pathlib import Path
import random
import shutil

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_ROOT = PROJECT_ROOT / "datasets" / "smart_home_scene_v1"

IMG_SRC = DATASET_ROOT / "images" / "preview"
LBL_SRC = DATASET_ROOT / "labels" / "preview"

IMG_TRAIN = DATASET_ROOT / "images" / "train"
IMG_VAL = DATASET_ROOT / "images" / "val"
LBL_TRAIN = DATASET_ROOT / "labels" / "train"
LBL_VAL = DATASET_ROOT / "labels" / "val"

for p in [IMG_TRAIN, IMG_VAL, LBL_TRAIN, LBL_VAL]:
    p.mkdir(parents=True, exist_ok=True)

for p in [IMG_TRAIN, IMG_VAL, LBL_TRAIN, LBL_VAL]:
    for f in p.glob("*"):
        f.unlink()

images = sorted(IMG_SRC.glob("*.png"))
pairs = []

for img in images:
    label = LBL_SRC / f"{img.stem}.txt"
    if label.exists():
        pairs.append((img, label))

random.seed(42)
random.shuffle(pairs)

val_ratio = 0.2
val_count = int(len(pairs) * val_ratio)

val_pairs = pairs[:val_count]
train_pairs = pairs[val_count:]

def copy_pairs(pairs, img_dst, lbl_dst):
    for img, label in pairs:
        shutil.copy2(img, img_dst / img.name)
        shutil.copy2(label, lbl_dst / label.name)

copy_pairs(train_pairs, IMG_TRAIN, LBL_TRAIN)
copy_pairs(val_pairs, IMG_VAL, LBL_VAL)

print("[DONE] split completed")
print("train:", len(train_pairs))
print("val:", len(val_pairs))
print("total:", len(pairs))