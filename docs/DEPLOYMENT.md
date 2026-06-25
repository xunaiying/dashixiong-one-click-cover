# 部署说明 / Deployment Guide

本文档说明如何在 Windows 本地部署 **大尸兄一键翻唱**，并下载必要的基础模型与运行件。

This guide explains how to deploy **DaShiXiong One-Click AI Song Cover** locally on Windows and download the required base models/runtime assets.

## 1. 推荐环境 / Recommended environment

### 中文

- 系统：Windows 10 / Windows 11
- 显卡：推荐 NVIDIA GPU，显存 6GB 以上更稳
- 磁盘：建议预留 15GB 以上空间
- 路径：建议放在纯英文路径，例如：

```text
D:\Applio
D:\dashixiong-one-click-cover
```

不建议放在含中文、特殊符号或空格很复杂的路径里，因为部分音频/AI 依赖对路径比较挑。

### English

- OS: Windows 10 / Windows 11
- GPU: NVIDIA GPU recommended; 6GB+ VRAM is preferred
- Disk: reserve at least 15GB
- Path: use a simple ASCII-only path, for example:

```text
D:\Applio
D:\dashixiong-one-click-cover
```

Avoid complex paths containing non-ASCII characters or special symbols when possible.

## 2. 下载项目 / Download the project

### 方式 A：直接下载 ZIP / Option A: Download ZIP

打开 GitHub 仓库页面：

```text
https://github.com/xunaiying/dashixiong-one-click-cover
```

点击：

```text
Code -> Download ZIP
```

解压到推荐路径，例如：

```text
D:\Applio
```

### 方式 B：Git 克隆 / Option B: Git clone

```powershell
git clone https://github.com/xunaiying/dashixiong-one-click-cover.git D:\Applio
cd /d D:\Applio
```

## 3. 安装环境 / Install dependencies

### 一键方式 / One-click method

双击：

```text
run-ui.bat
```

然后在启动器里点击：

```text
安装环境
```

启动器会自动：

- 安装/复用 Miniconda
- 创建项目内 Python 环境 `env`
- 安装 Applio 依赖
- 安装 Demucs 分离依赖

### PowerShell 方式 / PowerShell method

```powershell
cd /d D:\Applio
powershell -ExecutionPolicy Bypass -File .\install_env.ps1
```

安装日志在：

```text
D:\Applio\logs\launcher-install.log
```

## 4. 下载基础模型与运行件 / Download base models and runtime assets

### 一键方式 / One-click method

双击：

```text
run-ui.bat
```

然后点击：

```text
检查缺失
下载缺失
```

### 命令行方式 / Command line method

```powershell
cd /d D:\Applio
env\python.exe download_base_models.py
```

如果 Python 环境还没安装，也可以先用系统 Python：

```powershell
python download_base_models.py
```

所有基础模型与运行件下载链接见：

```text
docs\MODEL_DOWNLOADS.md
```

## 5. 启动一键翻唱 / Launch one-click cover

双击任意一个：

```text
run-one-click-cover.bat
大尸兄一键翻唱.bat
```

或从启动器里点击：

```text
大尸兄一键翻唱
```

## 6. 第一次使用流程 / First run workflow

1. 打开一键翻唱窗口。
2. 选择歌曲文件。
3. 如果已有模型，选择“自动选择最新可用模型”。
4. 如果没有模型，选择“训练新模型”，填写模型名并选择干净的人声素材文件夹。
5. 保持默认：
   - 自动估算变调
   - 咬字清晰模式
   - 自动匹配原唱混音
6. 点击“一键生成混音翻唱”。
7. 成品在：

```text
outputs\covers
```

English:

1. Open the one-click cover window.
2. Choose a song file.
3. Select automatic model discovery if you already have a model.
4. If you do not have a model, choose new model training and provide clean voice samples.
5. Keep the defaults enabled:
   - Auto pitch estimation
   - Pronunciation clarity mode
   - Auto match original mix
6. Click the one-click mixed cover button.
7. Find the output under:

```text
outputs\covers
```

## 7. 训练素材建议 / Voice sample recommendations

中文：

- 推荐 10–30 分钟清晰干声。
- 尽量不要有伴奏、混响、强降噪、爆音。
- 做唱歌翻唱时，最好提供你的清唱/唱歌素材。
- 如果咬字糊，优先补充更清晰的 z/c/s、zh/ch/sh、t/k/p 等发音素材。

English:

- Use 10–30 minutes of clean dry voice when possible.
- Avoid backing music, heavy reverb, aggressive denoise artifacts, and clipping.
- For singing covers, singing/acapella samples are better than speech-only samples.
- If pronunciation is blurry, add clearer consonant-heavy samples.

## 8. 常见问题 / FAQ

### 下载很慢怎么办？

基础模型来自 Hugging Face。可以手动打开 `docs\MODEL_DOWNLOADS.md` 中的链接下载，然后放到对应路径。

### 没有 NVIDIA 显卡能用吗？

可以尝试 CPU，但训练和推理会明显更慢。推荐 NVIDIA GPU。

### 成品只有伴奏或人声太小？

确认使用的是最新版脚本，并保持“自动匹配原唱混音”开启。必要时把“人声微调”调到 `1.10` 或 `1.20`。

### 咬字不清怎么办？

保持“咬字清晰模式”开启；可以把“辅音保护”调到 `0.55`–`0.65`，并适当降低“索引强度”。
