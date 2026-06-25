# 基础模型下载链接 / Base Model Download Links

本文档列出 **大尸兄一键翻唱** 需要的基础模型、预训练权重和 FFmpeg 运行件。  
这些文件默认由启动器的“下载缺失”按钮或 `download_base_models.py` 自动下载。

This document lists the base models, pretrained weights, and FFmpeg runtime assets required by **DaShiXiong One-Click AI Song Cover**.  
They are downloaded automatically by the launcher's **Download missing** button or by `download_base_models.py`.

## 自动下载 / Automatic download

```powershell
cd /d D:\Applio
env\python.exe download_base_models.py
```

或者打开：

```text
run-ui.bat
```

点击：

```text
检查缺失 -> 下载缺失
```

## 手动下载说明 / Manual download instructions

如果自动下载失败，可以逐个打开下面的链接，把文件保存到“项目内目标路径”。  
例如目标路径是：

```text
rvc\models\predictors\rmvpe.pt
```

如果项目在 `D:\Applio`，完整路径就是：

```text
D:\Applio\rvc\models\predictors\rmvpe.pt
```

If automatic download fails, open the links below manually and save each file to the target path inside the project folder.

## 下载清单 / Download list

| 类型 / Type | 目标路径 / Target path | 下载链接 / Download link |
|---|---|---|
| F0 predictor | `rvc\models\predictors\rmvpe.pt` | [rmvpe.pt](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/rmvpe.pt) |
| F0 predictor | `rvc\models\predictors\fcpe.pt` | [fcpe.pt](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/fcpe.pt) |
| ContentVec embedder | `rvc\models\embedders\contentvec\pytorch_model.bin` | [pytorch_model.bin](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/pytorch_model.bin) |
| ContentVec config | `rvc\models\embedders\contentvec\config.json` | [config.json](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/config.json) |
| HiFi-GAN discriminator 32k | `rvc\models\pretraineds\hifi-gan\f0D32k.pth` | [f0D32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D32k.pth) |
| HiFi-GAN discriminator 40k | `rvc\models\pretraineds\hifi-gan\f0D40k.pth` | [f0D40k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D40k.pth) |
| HiFi-GAN discriminator 48k | `rvc\models\pretraineds\hifi-gan\f0D48k.pth` | [f0D48k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D48k.pth) |
| HiFi-GAN generator 32k | `rvc\models\pretraineds\hifi-gan\f0G32k.pth` | [f0G32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G32k.pth) |
| HiFi-GAN generator 40k | `rvc\models\pretraineds\hifi-gan\f0G40k.pth` | [f0G40k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G40k.pth) |
| HiFi-GAN generator 48k | `rvc\models\pretraineds\hifi-gan\f0G48k.pth` | [f0G48k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G48k.pth) |
| RefineGAN discriminator 24k | `rvc\models\pretraineds\refinegan\f0D24k.pth` | [f0D24k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D24k.pth) |
| RefineGAN generator 24k | `rvc\models\pretraineds\refinegan\f0G24k.pth` | [f0G24k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G24k.pth) |
| RefineGAN discriminator 32k | `rvc\models\pretraineds\refinegan\f0D32k.pth` | [f0D32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D32k.pth) |
| RefineGAN generator 32k | `rvc\models\pretraineds\refinegan\f0G32k.pth` | [f0G32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G32k.pth) |
| FFmpeg | `ffmpeg.exe` | [ffmpeg.exe](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffmpeg.exe) |
| FFprobe | `ffprobe.exe` | [ffprobe.exe](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffprobe.exe) |

## 额外依赖链接 / Additional dependency links

| 用途 / Purpose | 链接 / Link |
|---|---|
| Miniconda Windows installer | [Miniconda3-py312_25.11.1-1-Windows-x86_64.exe](https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe) |
| PyTorch CUDA wheels index | [https://download.pytorch.org/whl/cu128](https://download.pytorch.org/whl/cu128) |
| Applio upstream resources | [IAHispano/Applio on Hugging Face](https://huggingface.co/IAHispano/Applio) |

## 校验结果 / Link check

上述基础模型和运行件链接已在本地验证可访问，HTTP 状态为 `200 OK`。如果以后链接失效，请优先查看上游：

```text
https://huggingface.co/IAHispano/Applio/tree/main/Resources
```
