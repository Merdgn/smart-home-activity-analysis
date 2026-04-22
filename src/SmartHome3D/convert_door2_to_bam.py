from pathlib import Path
from panda3d.core import loadPrcFileData, Filename
from direct.showbase.ShowBase import ShowBase

loadPrcFileData("", "window-type none")
loadPrcFileData("", "audio-library-name null")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
GLB_PATH = PROJECT_ROOT / "assets" / "models_glb" / "Door_2.glb"
BAM_PATH = PROJECT_ROOT / "assets" / "models_bam" / "Door_2.bam"

class ConverterApp(ShowBase):
    def __init__(self):
        super().__init__()

if __name__ == "__main__":
    app = ConverterApp()

    if not GLB_PATH.exists():
        print(f"[HATA] Dosya bulunamadı: {GLB_PATH}")
    else:
        try:
            panda_path = Filename.from_os_specific(str(GLB_PATH))
            model = app.loader.loadModel(panda_path)

            if model.isEmpty():
                print("[HATA] Door_2 modeli yüklenemedi.")
            else:
                bam_filename = Filename.from_os_specific(str(BAM_PATH))
                model.writeBamFile(bam_filename)
                print(f"[OK] Dönüştürüldü: {GLB_PATH.name} -> {BAM_PATH.name}")

        except Exception as e:
            print(f"[HATA] Dönüştürme sırasında sorun oluştu: {e}")

    app.destroy()