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
- **训练新声音模型**：选择“训练新模型”，填入模型名并选择新声音素材文件夹。
- **自动分离歌曲**：调用 Demucs 把歌曲拆成原唱人声与伴奏。
- **自动估算变调**：按歌曲人声和目标模型自动估算 pitch shift。
- **咬字清晰模式**：默认提高辅音保护并限制过高索引强度，减少糊字。
- **智能混音**：参考原唱人声/伴奏比例，自动匹配翻唱人声与伴奏音量，并做轻微伴奏让位。
- **完整成品输出**：输出带伴奏、带混音和响度处理的 `*_mixed_cover.mp3`。

## Features (English)

- **One-click cover UI**: launch with `run-one-click-cover.bat` or `大尸兄一键翻唱.bat`.
- **Automatic model discovery**: finds available `.pth` and `.index` files under `logs/<model_name>`.
- **New voice training**: train a new local RVC model from your own clean voice samples.
- **Song separation**: uses Demucs to split the source song into vocals and instrumental.
- **Automatic pitch estimation**: estimates a suitable pitch shift for the selected voice model.
- **Pronunciation clarity mode**: improves consonant protection and avoids overly blurry index settings.
- **Smart auto-mixing**: matches the original song's vocal/instrumental balance and applies light backing-track ducking.
- **Finished mixed output**: exports a mastered `*_mixed_cover.mp3` instead of vocal-only audio.

## 快速开始 / Quick Start

详细部署和模型下载说明：

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)：Windows 部署、安装环境、一键启动、常见问题。
- [`docs/MODEL_DOWNLOADS.md`](docs/MODEL_DOWNLOADS.md)：基础模型、预训练权重、FFmpeg 运行件下载链接和放置路径。

1. 下载本仓库 ZIP 或使用 Git 克隆。
2. 建议放在纯英文路径，例如 `D:\Applio`，避免部分音频/AI 依赖遇到中文路径问题。
3. 双击 `run-ui.bat` 打开启动器，先检查/安装环境和基础模型。
4. 双击 `run-one-click-cover.bat` 或 `大尸兄一键翻唱.bat` 打开一键翻唱窗口。
5. 选择歌曲文件，选择现有模型或训练新模型，然后点击“一键生成混音翻唱”。
6. 成品默认输出到 `outputs/covers`。

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
- Writes the final mastered file as `*_mixed_cover.mp3` under `outputs/covers`.

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
- If consonants are still unclear, try **Consonant protect** around `0.55` to `0.65`.

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
