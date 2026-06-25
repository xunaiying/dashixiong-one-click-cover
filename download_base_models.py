import shutil
from pathlib import Path
from urllib.request import Request, urlopen

APP_DIR = Path(__file__).resolve().parent
ASSET_URLS = {
    r"rvc\models\predictors\rmvpe.pt": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/rmvpe.pt",
    r"rvc\models\predictors\fcpe.pt": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/fcpe.pt",
    r"rvc\models\embedders\contentvec\pytorch_model.bin": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/pytorch_model.bin",
    r"rvc\models\embedders\contentvec\config.json": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/config.json",
    r"rvc\models\pretraineds\hifi-gan\f0D32k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D32k.pth",
    r"rvc\models\pretraineds\hifi-gan\f0D40k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D40k.pth",
    r"rvc\models\pretraineds\hifi-gan\f0D48k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D48k.pth",
    r"rvc\models\pretraineds\hifi-gan\f0G32k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G32k.pth",
    r"rvc\models\pretraineds\hifi-gan\f0G40k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G40k.pth",
    r"rvc\models\pretraineds\hifi-gan\f0G48k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G48k.pth",
    r"rvc\models\pretraineds\refinegan\f0D24k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D24k.pth",
    r"rvc\models\pretraineds\refinegan\f0G24k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G24k.pth",
    r"rvc\models\pretraineds\refinegan\f0D32k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D32k.pth",
    r"rvc\models\pretraineds\refinegan\f0G32k.pth": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G32k.pth",
    "ffmpeg.exe": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffmpeg.exe",
    "ffprobe.exe": "https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffprobe.exe",
}

for rel, url in ASSET_URLS.items():
    dst = APP_DIR / rel
    if dst.exists():
        print(f"skip {rel}")
        continue
    dst.parent.mkdir(parents=True, exist_ok=True)
    print(f"download {rel}")
    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(req) as resp, open(dst, "wb") as f:
        shutil.copyfileobj(resp, f)
print("done")
