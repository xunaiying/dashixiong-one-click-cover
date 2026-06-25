# 项目引用说明 / Project References

## 中文

**大尸兄一键翻唱** 是在 Windows 本地使用场景下，对 Applio/RVC 翻唱流程做的一键化封装与增强。项目本身不声称拥有上游模型、算法或第三方依赖的版权；使用者应遵守对应项目许可证和音频素材版权要求。

### 主要上游项目

- [IAHispano/Applio](https://github.com/IAHispano/Applio)：核心 RVC/Applio 训练、推理与 Web UI 能力。
- [Demucs](https://github.com/facebookresearch/demucs)：歌曲人声与伴奏分离。
- [FFmpeg](https://ffmpeg.org/)：音频转码、混音后编码、响度处理。
- [PyTorch](https://pytorch.org/)：深度学习运行时。
- RVC 生态相关模型与工具：声线转换、特征提取、F0 估计等能力。

### 本项目新增/整理的内容

- Windows 本地一键启动器。
- 一键翻唱 Tkinter GUI。
- 自动模型识别与新模型训练入口。
- 自动歌曲分离、自动变调估算、咬字清晰模式。
- 参考原唱声伴比例的智能混音逻辑。
- 中英文项目说明、案例说明和本地使用指引。

### 音频与版权

请只上传、处理和公开分发你拥有版权、已获授权或允许二次创作的音频。尤其是“原唱”“伴奏”“翻唱成品”可能涉及音乐作品、录音制品、表演者权利和平台条款。

## English

**DaShiXiong One-Click AI Song Cover** is a Windows-first workflow layer and usability package built on top of Applio/RVC. This project does not claim ownership of upstream models, algorithms, or third-party dependencies. Users must comply with the corresponding licenses and with all audio copyright requirements.

### Main upstream projects

- [IAHispano/Applio](https://github.com/IAHispano/Applio): core RVC/Applio training, inference, and Web UI features.
- [Demucs](https://github.com/facebookresearch/demucs): vocal/instrumental source separation.
- [FFmpeg](https://ffmpeg.org/): audio transcoding, post-mix encoding, and loudness processing.
- [PyTorch](https://pytorch.org/): deep learning runtime.
- RVC ecosystem tools and models: voice conversion, feature extraction, F0 estimation, and related components.

### What this package adds

- Windows local one-click launcher.
- One-click song-cover Tkinter GUI.
- Automatic model discovery and new voice training entry point.
- Automatic song separation, pitch estimation, and pronunciation clarity mode.
- Smart auto-mixing based on the original vocal/instrumental balance.
- Bilingual project documentation, example case notes, and local usage guidance.

### Audio and copyright

Only upload, process, and publicly distribute audio that you own, are authorized to use, or are legally allowed to transform. Original songs, instrumentals, and generated covers may involve musical work rights, sound recording rights, performer rights, and platform terms.
