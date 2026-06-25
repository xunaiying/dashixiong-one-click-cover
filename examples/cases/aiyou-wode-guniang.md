# 案例：哎呦我的姑娘 / Case: Aiyou Wode Guniang

这个案例用于说明“大尸兄一键翻唱”的典型流程：输入一首原唱歌曲和一个已训练好的声音模型，输出一首带伴奏、带智能混音的翻唱成品。

This case demonstrates the typical DaShiXiong one-click cover workflow: provide an original song and a trained voice model, then export a full mixed cover with instrumental backing.

## 本地案例文件 / Local case files

用户本地提供的两个案例文件：

```text
C:\Users\Amin\Desktop\哎呦我的姑娘（原唱）.mp3
C:\Users\Amin\Desktop\哎呦我的姑娘（翻唱）.mp3
```

The two local case files provided by the user:

```text
C:\Users\Amin\Desktop\哎呦我的姑娘（原唱）.mp3
C:\Users\Amin\Desktop\哎呦我的姑娘（翻唱）.mp3
```

## 文件信息 / File metadata

| 文件 / File | 角色 / Role | 时长 / Duration | 大小 / Size | SHA-256 |
|---|---:|---:|---:|---|
| `哎呦我的姑娘（原唱）.mp3` | 原唱输入 / Original input | 17.162s | 137,661 bytes | `09ac45a9816b2b403aa5b00c1e942a92dedef8c5fc6373c279602dd43faa2cf1` |
| `哎呦我的姑娘（翻唱）.mp3` | 翻唱输出 / Generated cover | 17.136s | 686,445 bytes | `56a19a71419ab51f61dbc62137b64c3cf9df2bb109c466876f520c6672d8c509` |

## 复现步骤 / Reproduction steps

1. 启动 `run-one-click-cover.bat` 或 `大尸兄一键翻唱.bat`。
2. 在“歌曲文件”里选择原唱输入音频。
3. 选择已有模型，或选择“训练新模型”并提供干净的人声素材。
4. 保持默认：
   - 自动估算变调：开启
   - 咬字清晰模式：开启
   - 自动匹配原唱混音：开启
5. 点击“一键生成混音翻唱”。
6. 在 `outputs/covers` 查看 `*_mixed_cover.mp3`。

English:

1. Launch `run-one-click-cover.bat` or `大尸兄一键翻唱.bat`.
2. Select the original song as the song file.
3. Choose an existing model, or train a new model from clean voice samples.
4. Keep the defaults enabled:
   - Auto pitch estimation
   - Pronunciation clarity mode
   - Auto match original mix
5. Click the one-click mixed cover button.
6. Find the final `*_mixed_cover.mp3` under `outputs/covers`.

## 为什么仓库里没有直接附带 MP3 / Why the MP3 files are not committed

公开上传完整原唱或翻唱 MP3 可能涉及版权授权。本仓库把这两个音频作为“本地案例文件”记录其角色、时长、大小与校验值，但默认不公开分发音频本体。

Publicly redistributing the original song or generated cover MP3 may require copyright permission. This repository documents the two audio files as a local case, including role, duration, size, and checksums, but does not publish the audio binaries by default.
