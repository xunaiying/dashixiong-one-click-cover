<!--
  大尸兄一键翻唱 / DaShiXiong One-Click AI Song Cover
  This project is a Windows-first local packaging and workflow layer built on top of Applio.
-->

# 大尸兄一键翻唱

**大尸兄一键翻唱** 是基于 [IAHispano/Applio](https://github.com/IAHispano/Applio) 定制的 Windows 本地一键 AI 翻唱工具。它把模型训练、歌曲人声/伴奏分离、RVC 声线转换、自动变调、智能混音和成品输出整理到更顺手的本地 UI 里，适合希望“放入自己的声音 + 放入歌曲 = 输出完整混音翻唱”的用户。

> 合规提醒：请只处理你拥有版权、已获授权或允许二次创作的音频。公开分发原唱、伴奏或翻唱成品前，请自行确认版权与授权。

## 功能说明（中文）

- **一键翻唱窗口**：双击 `run-one-click-cover.bat` 或 `大尸兄一键翻唱.bat` 打开。
- **自动识别模型**：自动查找 `logs/<模型名>` 下可用的 `.pth` 与 `.index`。
- **训练新声音模型**：选择“训练新模型”，填入模型显示名并选择新声音素材文件夹；显示名支持中文，内部自动使用安全英文 ID。
- **训练进度显示**：训练时显示当前轮次/总轮数、总进度百分比、step、速度、剩余时间和预计完成时间，并提供进度条。
- **自动分离歌曲**：调用 Demucs 把歌曲拆成原唱人声与伴奏。
- **自动估算变调**：按歌曲人声和目标模型自动估算 pitch shift。
- **咬字清晰模式**：默认提高辅音保护并限制过高索引强度，减少糊字。
- **智能混音**：参考原唱人声/伴奏比例，自动匹配翻唱人声与伴奏音量，并做轻微伴奏让位。
- **完整成品输出**：输出带伴奏、带混音和响度处理的 `*_翻唱成品.mp3`，成功后自动清理中间人声/伴奏文件。
- **原唱/翻唱对比预览**：截取短片段生成原唱预览和翻唱后预览，可直接播放对比音色与咬字。
- **自动参数试听矩阵**：一键批量生成多组短试听，对比不同变调、索引强度和辅音保护，快速找到最自然参数。
- **自动更新提示**：启动时检查 GitHub 最新 Release，发现新版可一键下载覆盖程序文件，并保留本地环境、模型和输出。
- **一键清理训练缓存**：训练完成后可自动/手动清理切片、特征、F0、TensorBoard、G/D checkpoint 和旧权重，只保留可翻唱的声音模型。

## Features (English)

- **One-click cover UI**: launch with `run-one-click-cover.bat` or `大尸兄一键翻唱.bat`.
- **Automatic model discovery**: finds available `.pth` and `.index` files under `logs/<model_name>`.
- **New voice training**: train a new local RVC model from your own clean voice samples; Chinese display names are supported with an automatic ASCII-safe internal ID.
- **Training progress display**: shows current/total epochs, total percentage, steps, speed, remaining time, ETA, and a progress bar.
- **Song separation**: uses Demucs to split the source song into vocals and instrumental.
- **Automatic pitch estimation**: estimates a suitable pitch shift for the selected voice model.
- **Pronunciation clarity mode**: improves consonant protection and avoids overly blurry index settings.
- **Smart auto-mixing**: matches the original song's vocal/instrumental balance and applies light backing-track ducking.
- **Finished mixed output**: exports a mastered `*_翻唱成品.mp3` instead of vocal-only audio and cleans temporary stems automatically.
- **Original/cover A-B preview**: generates short original and converted preview clips for quick voice and pronunciation checks.
- **Automatic parameter preview matrix**: batch-generates short clips with different pitch, index rate, and protect settings for quick A/B tuning.
- **Auto update prompt**: checks the latest GitHub Release and can update program files in-place while preserving local env, models, and outputs.
- **One-click training cache cleanup**: automatically or manually removes slices, features, F0 files, TensorBoard logs, G/D checkpoints, and old weights while keeping the usable voice model.

## 快速开始 / Quick Start

> 下面就是完整部署步骤和基础模型下载链接。你不需要先去翻其它文档；照着本页操作即可。
>
> Full deployment steps and base model download links are listed directly below. You can follow this page without opening separate docs first.

### 1. 下载项目 / Download

#### 方式 A：下载 Release ZIP（推荐）

打开 Release 页面：

[https://github.com/xunaiying/dashixiong-one-click-cover/releases/tag/v1.0.10](https://github.com/xunaiying/dashixiong-one-click-cover/releases/tag/v1.0.10)

直接下载：

[https://github.com/xunaiying/dashixiong-one-click-cover/releases/download/v1.0.10/dashixiong-one-click-cover-v1.0.10.zip](https://github.com/xunaiying/dashixiong-one-click-cover/releases/download/v1.0.10/dashixiong-one-click-cover-v1.0.10.zip)

解压到纯英文路径，例如：

```text
D:\Applio
```

> 注意：推荐纯英文路径，避免部分音频/AI 依赖遇到中文路径、空格或特殊符号出错。

#### 方式 B：Git 克隆

```powershell
git clone https://github.com/xunaiying/dashixiong-one-click-cover.git D:\Applio
cd /d D:\Applio
```

English:

- Download the Release ZIP or clone the repo.
- Extract/clone it to a simple ASCII path such as `D:\Applio`.

### 2. 安装运行环境 / Install environment

#### 一键图形方式（推荐）

双击：

```text
run-ui.bat
```

在启动器里点击：

```text
安装环境
```

它会自动：

- 下载/复用 Miniconda
- 创建项目内 Python 环境 `env`
- 安装 Applio 依赖
- 安装 Demucs 人声/伴奏分离依赖

#### PowerShell 方式

```powershell
cd /d D:\Applio
powershell -ExecutionPolicy Bypass -File .\install_env.ps1
```

安装日志路径：

```text
D:\Applio\logs\launcher-install.log
```

### 3. 下载基础模型与运行件 / Download base models and runtime assets

#### 一键图形方式（推荐）

双击：

```text
run-ui.bat
```

依次点击：

```text
检查缺失
下载缺失
```

#### 命令行方式

如果已经安装好环境：

```powershell
cd /d D:\Applio
env\python.exe download_base_models.py
```

如果还没有项目内环境，也可以临时使用系统 Python：

```powershell
cd /d D:\Applio
python download_base_models.py
```

#### 手动下载链接和放置路径 / Manual download links and target paths

如果自动下载失败，就手动打开下面链接下载，然后放到对应“项目内目标路径”。例如项目在 `D:\Applio`，目标路径 `rvc\models\predictors\rmvpe.pt` 的完整路径就是：

```text
D:\Applio\rvc\models\predictors\rmvpe.pt
```

| 类型 / Type | 项目内目标路径 / Target path inside project | 下载链接 / Download link |
|---|---|---|
| F0 predictor | `rvc\models\predictors\rmvpe.pt` | [rmvpe.pt](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/rmvpe.pt) |
| F0 predictor | `rvc\models\predictors\fcpe.pt` | [fcpe.pt](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/predictors/fcpe.pt) |
| ContentVec embedder | `rvc\models\embedders\contentvec\pytorch_model.bin` | [pytorch_model.bin](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/pytorch_model.bin) |
| ContentVec config | `rvc\models\embedders\contentvec\config.json` | [config.json](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/embedders/contentvec/config.json) |
| HiFi-GAN D 32k | `rvc\models\pretraineds\hifi-gan\f0D32k.pth` | [f0D32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D32k.pth) |
| HiFi-GAN D 40k | `rvc\models\pretraineds\hifi-gan\f0D40k.pth` | [f0D40k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D40k.pth) |
| HiFi-GAN D 48k | `rvc\models\pretraineds\hifi-gan\f0D48k.pth` | [f0D48k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0D48k.pth) |
| HiFi-GAN G 32k | `rvc\models\pretraineds\hifi-gan\f0G32k.pth` | [f0G32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G32k.pth) |
| HiFi-GAN G 40k | `rvc\models\pretraineds\hifi-gan\f0G40k.pth` | [f0G40k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G40k.pth) |
| HiFi-GAN G 48k | `rvc\models\pretraineds\hifi-gan\f0G48k.pth` | [f0G48k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/pretrained_v2/f0G48k.pth) |
| RefineGAN D 24k | `rvc\models\pretraineds\refinegan\f0D24k.pth` | [f0D24k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D24k.pth) |
| RefineGAN G 24k | `rvc\models\pretraineds\refinegan\f0G24k.pth` | [f0G24k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G24k.pth) |
| RefineGAN D 32k | `rvc\models\pretraineds\refinegan\f0D32k.pth` | [f0D32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0D32k.pth) |
| RefineGAN G 32k | `rvc\models\pretraineds\refinegan\f0G32k.pth` | [f0G32k.pth](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/refinegan/f0G32k.pth) |
| FFmpeg | `ffmpeg.exe` | [ffmpeg.exe](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffmpeg.exe) |
| FFprobe | `ffprobe.exe` | [ffprobe.exe](https://huggingface.co/IAHispano/Applio/resolve/main/Resources/ffprobe.exe) |

#### 额外依赖链接 / Additional dependency links

| 用途 / Purpose | 下载链接 / Download link |
|---|---|
| Miniconda Windows installer | [Miniconda3-py312_25.11.1-1-Windows-x86_64.exe](https://repo.anaconda.com/miniconda/Miniconda3-py312_25.11.1-1-Windows-x86_64.exe) |
| PyTorch CUDA wheels index | [https://download.pytorch.org/whl/cu128](https://download.pytorch.org/whl/cu128) |
| Applio upstream resources | [https://huggingface.co/IAHispano/Applio/tree/main/Resources](https://huggingface.co/IAHispano/Applio/tree/main/Resources) |

### 4. 启动大尸兄一键翻唱 / Launch DaShiXiong One-Click Cover

双击任意一个：

```text
run-one-click-cover.bat
大尸兄一键翻唱.bat
```

或者打开启动器：

```text
run-ui.bat
```

然后点击：

```text
大尸兄一键翻唱
```

### 5. 第一次生成翻唱 / First cover generation

1. 打开一键翻唱窗口。
2. 选择歌曲文件。
3. 如果已有模型，选择“自动选择最新可用模型”。
4. 如果没有模型，选择“训练新模型”，填写模型名并选择干净的人声素材文件夹。
5. 保持默认开启：
   - 自动估算变调
   - 咬字清晰模式
   - 自动匹配原唱混音
6. 点击“一键生成混音翻唱”。
7. 成品默认输出到：

```text
outputs\covers
```


### 输出目录更清爽 / Cleaner output folders

成功生成后默认只保留真正需要试听或发布的结果：

- 普通一键翻唱：`outputs\covers\时间_歌曲_模型_翻唱成品.mp3`
- 声音预览：`outputs\covers\previews\*_original_preview.mp3` 与 `*_cover_preview.mp3`
- 参数试听矩阵：矩阵目录内只保留 `00_原唱片段.mp3`、每组 `*_翻唱混音.mp3` 和 `参数试听矩阵说明.txt`

人声/伴奏分离文件、RVC 中间 wav、临时工作目录会在成功后自动清理。

### 6. 训练素材建议 / Voice sample recommendations

- 推荐 10–30 分钟清晰干声。
- 尽量不要有伴奏、混响、强降噪、爆音。
- 做唱歌翻唱时，最好提供你的清唱/唱歌素材。
- 如果咬字糊，优先补充更清晰的 z/c/s、zh/ch/sh、t/k/p 等发音素材。

English:

- Use 10–30 minutes of clean dry voice when possible.
- Avoid backing music, heavy reverb, aggressive denoise artifacts, and clipping.
- For singing covers, singing/acapella samples are better than speech-only samples.
- If pronunciation is blurry, add clearer consonant-heavy samples.

### 7. 常见问题 / FAQ

#### 下载很慢怎么办？

基础模型来自 Hugging Face。你可以直接用上面的表格链接手动下载，然后放到对应路径。

#### 没有 NVIDIA 显卡能用吗？

可以尝试 CPU，但训练和推理会明显更慢。推荐 NVIDIA GPU。

#### 成品只有伴奏或人声太小？

确认使用最新版脚本，并保持“自动匹配原唱混音”开启。必要时把“人声微调”调到 `1.10` 或 `1.20`。

#### 咬字不清怎么办？

保持“咬字清晰模式”开启；可以把“辅音保护”保持在 `0.45`–`0.50`，并适当降低“索引强度”。

### 8. 补充文档 / Extra docs

下面文档只是补充备查；部署步骤和下载链接已经完整放在本页上。

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/MODEL_DOWNLOADS.md`](docs/MODEL_DOWNLOADS.md)
- [`docs/PROJECT_REFERENCES.md`](docs/PROJECT_REFERENCES.md)
## 案例说明 / Example Case

本仓库包含一个案例说明页，展示“原唱输入 → 大尸兄一键翻唱输出”的工作流：

- 案例文档：[`examples/cases/aiyou-wode-guniang.md`](examples/cases/aiyou-wode-guniang.md)
- 示例音频目录说明：[`examples/audio/README.md`](examples/audio/README.md)

由于公开上传完整原唱/翻唱 MP3 可能涉及版权，本仓库默认不提交音频二进制文件。你可以把自己的授权音频放入 `examples/audio/`，按照案例文档复现。

## 项目引用 / Credits

本项目是一个本地工作流封装与增强版本，核心语音转换能力来自 Applio 与其依赖生态。完整引用见：

- [`docs/PROJECT_REFERENCES.md`](docs/PROJECT_REFERENCES.md)
- 上游项目：[IAHispano/Applio](https://github.com/IAHispano/Applio)

---

## Upstream Applio README

<h1 align="center">
  <a href="https://applio.org" target="_blank"><img src="https://github.com/IAHispano/Applio/assets/133521603/78e975d8-b07f-47ba-ab23-5a31592f322a" alt="Applio"></a>
</h1>

<p align="center">
    <img alt="Contributors" src="https://img.shields.io/github/contributors/iahispano/applio?style=for-the-badge&color=FFFFFF" />
    <img alt="Release" src="https://img.shields.io/github/release/iahispano/applio?style=for-the-badge&color=FFFFFF" />
    <img alt="Stars" src="https://img.shields.io/github/stars/iahispano/applio?style=for-the-badge&color=FFFFFF" />
    <img alt="Fork" src="https://img.shields.io/github/forks/iahispano/applio?style=for-the-badge&color=FFFFFF" />
    <img alt="Issues" src="https://img.shields.io/github/issues/iahispano/applio?style=for-the-badge&color=FFFFFF" />
</p>

<p align="center">A simple, high-quality voice conversion tool, focused on ease of use and performance.</p>

<p align="center">
  <a href="https://applio.org" target="_blank">🌐 Website</a>
  •
  <a href="https://docs.applio.org" target="_blank">📚 Documentation</a>
  •
  <a href="https://discord.gg/wY7gmqTyEV" target="_blank">☎️ Discord</a>
</p>

<p align="center">
  <a href="https://github.com/IAHispano/Applio-Plugins" target="_blank">🛒 Plugins</a>
  •
  <a href="https://huggingface.co/IAHispano/Applio/tree/main/Compiled" target="_blank">📦 Compiled</a>
  •
  <a href="https://applio.org/playground" target="_blank">🎮 Playground</a>
  •
  <a href="https://colab.research.google.com/github/iahispano/applio/blob/main/assets/Applio.ipynb" target="_blank">🔎 Google Colab (UI)</a>
  •
  <a href="https://colab.research.google.com/github/iahispano/applio/blob/main/assets/Applio_NoUI.ipynb" target="_blank">🔎 Google Colab (No UI)</a>
</p>

> [!NOTE]  
> Applio will no longer receive frequent updates. Going forward, development will focus mainly on security patches, dependency updates, and occasional feature improvements. This is because the project is already stable and mature with limited room for further improvements.

## Introduction

Applio is a powerful voice conversion tool focused on simplicity, quality, and performance. Whether you're an artist, developer, or researcher, Applio offers a straightforward platform for high-quality voice transformations. Its flexible design allows for customization through plugins and configurations, catering to a wide range of projects.

## Terms of Use and Commercial Usage

Using Applio responsibly is essential.

- Users must respect copyrights, intellectual property, and privacy rights.
- Applio is intended for lawful and ethical purposes, including personal, academic, and investigative projects.
- Commercial usage is permitted, provided users adhere to legal and ethical guidelines, secure appropriate rights and permissions, and comply with the [MIT license](./LICENSE).

The source code and model weights in this repository are licensed under the permissive [MIT license](./LICENSE), allowing modification, redistribution, and commercial use.

However, if you choose to use this official version of Applio (as provided in this repository, without significant modification), you must also comply with our [Terms of Use](./TERMS_OF_USE.md). These terms apply to our integrations, configurations, and default project behavior, and are intended to ensure responsible and ethical use without limiting their use in any way.

For commercial use, we recommend contacting us at [support@applio.org](mailto:support@applio.org) to ensure your usage aligns with ethical standards. All audio generated with Applio must comply with applicable copyright laws. If you find Applio helpful, consider supporting its development [through a donation](https://ko-fi.com/iahispano).

By using the official version of Applio, you accept full responsibility for complying with both the MIT license and our Terms of Use. Applio and its contributors are not liable for misuse. For full legal details, see the [Terms of Use](./TERMS_OF_USE.md).

## Getting Started

### 1. Installation

Run the installation script based on your operating system:

- **Windows:** Double-click `run-install.bat`.
- **Linux/macOS:** Execute `run-install.sh`.

### 2. Running Applio

Start Applio using:

- **Windows (one-click launcher):** Double-click `run-ui.bat`.
- **Windows (one-click song cover):** Double-click `run-one-click-cover.bat`.
- **Windows:** Double-click `run-applio.bat`.
- **Linux/macOS:** Run `run-applio.sh`.

This launches the Gradio interface in your default browser.

The one-click song cover tool now defaults to the complete cover workflow:

- Automatically uses the newest local model under `logs` when possible.
- Separates the source song into named vocal and instrumental files.
- Estimates the pitch shift from the song vocal and the selected voice model.
- Converts the vocal, then automatically matches the original song's vocal/instrumental balance.
- Applies a small automatic accompaniment ducking effect while the new vocal is present, then masters the result.
- Writes one final mastered `*_翻唱成品.mp3` under `outputs/covers` and removes temporary vocal/instrumental working files after success.

In the one-click cover window, **Auto match original mix** is enabled by default.  
The **Vocal trim** and **Instrumental trim** fields are now fine-tuning multipliers:

- `1.0` keeps the automatic mix result.
- Increase **Vocal trim** if the converted vocal is still too quiet.
- Decrease **Instrumental trim** if the backing track still covers the vocal.
- Disable **Auto match original mix** only when you want fully manual fixed-volume mixing.

For clearer pronunciation, **Pronunciation clarity mode** is enabled by default in the one-click cover window:

- It raises consonant protection to help preserve s, t, k, sh, ch, breath and word endings.
- It prevents excessive index strength from making the converted vocal sound too thick or blurry.
- If the voice becomes less similar to the model, lower **Consonant protect** slightly, for example from `0.50` to `0.40`.
- If consonants are still unclear, try **Consonant protect** around `0.45` to `0.50` (the current Applio CLI accepts up to `0.50`).

To train a new voice from a new voice folder in the one-click cover window:

- Double-click `run-one-click-cover.bat`.
- In **Voice Model**, choose **Train new model**.
- Fill **New model name**, for example `my_voice_2`.
- Choose your new clean voice sample folder in **Training samples folder**.
- Choose a song file and click the one-click cover button.
- The trained model is saved under `logs/<new_model_name>`.

### 3. Optional: TensorBoard Monitoring

To monitor training or visualize data:

- **Windows:** Run `run-tensorboard.bat`.
- **Linux/macOS:** Run `run-tensorboard.sh`.

For more detailed instructions, visit the [documentation](https://docs.applio.org).

## References

Applio is made possible thanks to these projects and their references:

- [gradio-screen-recorder](https://huggingface.co/spaces/gstaff/gradio-screen-recorder) by gstaff
- [rvc-cli](https://github.com/blaisewf/rvc-cli) by blaisewf

### Contributors

<a href="https://github.com/IAHispano/Applio/graphs/contributors" target="_blank">
  <img src="https://contrib.rocks/image?repo=IAHispano/Applio" />
</a>





