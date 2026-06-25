import argparse
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


APP_DIR = Path(__file__).resolve().parent
ENV_PYTHON = APP_DIR / "env" / "python.exe"
PYTHON = ENV_PYTHON if ENV_PYTHON.exists() else Path(sys.executable)
FFMPEG = APP_DIR / "ffmpeg.exe"
DEFAULT_OUTPUT_DIR = APP_DIR / "outputs" / "covers"
LOG_DIR = APP_DIR / "logs"
AUTO_MODEL_LABEL = "自动选择最新可用模型"
TRAIN_MODEL_LABEL = "训练新模型（使用新声音）"
MANUAL_MODEL_LABEL = "手动选择 .pth + .index"

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff", ".webm", ".mp4"}


def slugify(value: str) -> str:
    value = value.strip() or "my_voice"
    value = re.sub(r"[^\w.-]+", "_", value, flags=re.ASCII)
    value = value.strip("._-")
    return value or "my_voice"


def safe_filename(value: str, default: str = "song") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return value or default


def run_command(args: list[str], log, cwd: Path = APP_DIR) -> None:
    env = os.environ.copy()
    env["PATH"] = str(APP_DIR) + os.pathsep + env.get("PATH", "")
    log("$ " + " ".join(f'"{a}"' if " " in str(a) else str(a) for a in args))
    process = subprocess.Popen(
        [str(a) for a in args],
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    for line in process.stdout or []:
        log(line.rstrip())
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"Command failed with exit code {code}: {' '.join(map(str, args))}")


def latest_file(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def find_model_files(model_name: str) -> tuple[Path | None, Path | None]:
    model_dir = APP_DIR / "logs" / model_name
    if not model_dir.exists():
        return None, None

    pth_candidates = [
        p
        for p in model_dir.rglob("*.pth")
        if not p.name.startswith("G_") and not p.name.startswith("D_")
    ]
    index_candidates = list(model_dir.rglob("*.index"))
    return latest_file(pth_candidates), latest_file(index_candidates)


def discover_models() -> list[dict[str, object]]:
    if not LOG_DIR.exists():
        return []

    models: list[dict[str, object]] = []
    for model_dir in LOG_DIR.iterdir():
        if not model_dir.is_dir():
            continue
        pth, index = find_model_files(model_dir.name)
        if not pth or not index:
            continue
        updated = max(pth.stat().st_mtime, index.stat().st_mtime)
        models.append(
            {
                "name": model_dir.name,
                "pth": pth,
                "index": index,
                "updated": updated,
                "label": f"{model_dir.name}  ({datetime.fromtimestamp(updated).strftime('%m-%d %H:%M')})",
            }
        )
    return sorted(models, key=lambda item: float(item["updated"]), reverse=True)


def build_index_if_possible(model_name: str, log) -> tuple[Path | None, Path | None]:
    pth, index = find_model_files(model_name)
    if pth and index:
        return pth, index

    feature_dir = LOG_DIR / model_name / "extracted"
    if pth and feature_dir.exists() and any(feature_dir.glob("*.npy")):
        log(f"检测到模型 {model_name} 还没有索引，正在自动生成 .index。")
        run_command(
            [
                str(PYTHON),
                "core.py",
                "index",
                "--model_name",
                model_name,
                "--index_algorithm",
                "Auto",
            ],
            log,
        )
        return find_model_files(model_name)
    return pth, index


def resolve_existing_model(model_name: str, log) -> tuple[str, Path, Path] | None:
    requested = (model_name or "").strip()
    if requested and requested.lower() not in {"auto", "自动", AUTO_MODEL_LABEL.lower()}:
        resolved_name = slugify(requested)
        pth, index = build_index_if_possible(resolved_name, log)
        if pth and index:
            log(f"使用已识别模型：{resolved_name}")
            return resolved_name, pth, index

    models = discover_models()
    if not models:
        return None

    selected = models[0]
    resolved_name = str(selected["name"])
    log(f"自动选择最新模型：{resolved_name}")
    return resolved_name, Path(selected["pth"]), Path(selected["index"])


def find_separated_files(separated_root: Path) -> tuple[Path, Path]:
    vocals = list(separated_root.rglob("vocals.wav"))
    instrumental = list(separated_root.rglob("no_vocals.wav"))
    if not vocals or not instrumental:
        raise FileNotFoundError(f"Could not find Demucs vocals/no_vocals under {separated_root}")
    return latest_file(vocals), latest_file(instrumental)


def ensure_demucs(log) -> None:
    code = (
        "import importlib.util; "
        "raise SystemExit(0 if importlib.util.find_spec('demucs') else 1)"
    )
    result = subprocess.run([str(PYTHON), "-c", code], cwd=str(APP_DIR))
    if result.returncode == 0:
        log("Demucs is already installed.")
        return
    log("Installing Demucs for vocal separation. This can take a few minutes.")
    run_command([str(PYTHON), "-m", "uv", "pip", "install", "demucs"], log)


def median_model_f0(model_name: str) -> float | None:
    f0_dir = LOG_DIR / model_name / "f0_voiced"
    if not f0_dir.exists():
        return None

    import numpy as np

    chunks = []
    files = sorted(f0_dir.glob("*.npy"), key=lambda p: p.stat().st_mtime, reverse=True)[:96]
    for file in files:
        try:
            values = np.asarray(np.load(file), dtype=np.float32).reshape(-1)
        except Exception:
            continue
        values = values[np.isfinite(values)]
        values = values[(values >= 50) & (values <= 1100)]
        if values.size:
            chunks.append(values)

    if not chunks:
        return None
    sample = np.concatenate(chunks)
    if sample.size > 200_000:
        sample = sample[:: math.ceil(sample.size / 200_000)]
    return float(np.median(sample))


def median_audio_f0(audio_path: Path) -> float | None:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=16000, mono=True, duration=180)
    if y.size < sr:
        return None

    frame_length = 2048
    hop_length = 512
    f0 = librosa.yin(
        y,
        fmin=50,
        fmax=1100,
        sr=sr,
        frame_length=frame_length,
        hop_length=hop_length,
    )
    rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
    frames = min(len(f0), len(rms))
    f0 = f0[:frames]
    rms = rms[:frames]

    valid = np.isfinite(f0) & (f0 >= 50) & (f0 <= 1100)
    if rms.size:
        energy_floor = max(float(np.percentile(rms, 60)), float(np.max(rms)) * 0.03)
        valid = valid & (rms >= energy_floor)
    values = f0[valid]
    if values.size < 8:
        return None
    return float(np.median(values))


def estimate_pitch_shift(model_name: str, vocals_path: Path, log) -> int | None:
    target_f0 = median_model_f0(model_name)
    source_f0 = median_audio_f0(vocals_path)
    if not target_f0 or not source_f0:
        log("自动变调：可用音高信息不足，沿用手动变调。")
        return None

    shift = int(round(12 * math.log2(target_f0 / source_f0)))
    shift = max(-12, min(12, shift))
    log(
        "自动变调："
        f"歌曲人声中位音高 {source_f0:.1f}Hz，"
        f"目标声音中位音高 {target_f0:.1f}Hz，"
        f"建议 {shift:+d} 半音。"
    )
    return shift


def prepare_model(
    model_name: str,
    voice_dir: Path | None,
    sample_rate: int,
    epochs: int,
    batch_size: int,
    gpu: str,
    log,
    force_train: bool = False,
) -> tuple[str, Path, Path]:
    existing = None if force_train else resolve_existing_model(model_name, log)
    if existing:
        return existing

    if not voice_dir or not voice_dir.exists():
        raise FileNotFoundError("没有找到可用模型。请选择声音素材文件夹，或手动选择 .pth 和 .index。")

    audio_files = [p for p in voice_dir.rglob("*") if p.suffix.lower() in AUDIO_EXTS]
    if not audio_files:
        raise FileNotFoundError(f"声音素材文件夹里没有支持的音频文件：{voice_dir}")

    auto_names = {"auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}
    model_name = slugify(model_name if model_name.lower() not in auto_names else "my_voice")
    cpu_cores = max(1, min(8, os.cpu_count() or 4))
    save_every = max(1, min(epochs, 10))
    log(f"没有现成模型，开始训练 '{model_name}'，素材数量：{len(audio_files)}。")

    run_command(
        [
            str(PYTHON),
            "core.py",
            "preprocess",
            "--model_name",
            model_name,
            "--dataset_path",
            str(voice_dir),
            "--sample_rate",
            str(sample_rate),
            "--cpu_cores",
            str(cpu_cores),
            "--cut_preprocess",
            "Automatic",
            "--process_effects",
            "False",
            "--noise_reduction",
            "False",
            "--noise_reduction_strength",
            "0.7",
            "--chunk_len",
            "3.0",
            "--overlap_len",
            "0.3",
            "--normalization_mode",
            "none",
        ],
        log,
    )
    run_command(
        [
            str(PYTHON),
            "core.py",
            "extract",
            "--model_name",
            model_name,
            "--f0_method",
            "rmvpe",
            "--cpu_cores",
            str(cpu_cores),
            "--gpu",
            gpu,
            "--sample_rate",
            str(sample_rate),
            "--embedder_model",
            "contentvec",
            "--include_mutes",
            "2",
        ],
        log,
    )
    run_command(
        [
            str(PYTHON),
            "core.py",
            "train",
            "--model_name",
            model_name,
            "--vocoder",
            "HiFi-GAN",
            "--save_every_epoch",
            str(save_every),
            "--save_only_latest",
            "True",
            "--save_every_weights",
            "True",
            "--total_epoch",
            str(epochs),
            "--sample_rate",
            str(sample_rate),
            "--batch_size",
            str(batch_size),
            "--gpu",
            gpu,
            "--pretrained",
            "True",
            "--custom_pretrained",
            "False",
            "--overtraining_detector",
            "False",
            "--cleanup",
            "False",
            "--cache_data_in_gpu",
            "False",
            "--index_algorithm",
            "Auto",
        ],
        log,
    )

    pth, index = build_index_if_possible(model_name, log)
    if not pth or not index:
        raise FileNotFoundError(f"训练完成，但没有在 logs/{model_name} 找到 .pth 和 .index")
    return model_name, pth, index


def separate_song(song_path: Path, work_dir: Path, log) -> tuple[Path, Path]:
    ensure_demucs(log)
    separated_root = work_dir / "separated"
    run_command(
        [
            str(PYTHON),
            "-m",
            "demucs",
            "--two-stems",
            "vocals",
            "-n",
            "htdemucs",
            "--out",
            str(separated_root),
            str(song_path),
        ],
        log,
    )
    vocals, instrumental = find_separated_files(separated_root)
    song_stem = safe_filename(song_path.stem)
    named_vocals = work_dir / f"{song_stem}_01_original_vocals.wav"
    named_instrumental = work_dir / f"{song_stem}_02_instrumental.wav"
    shutil.copy2(vocals, named_vocals)
    shutil.copy2(instrumental, named_instrumental)
    log(f"分离人声：{named_vocals}")
    log(f"分离伴奏：{named_instrumental}")
    return named_vocals, named_instrumental


def infer_vocals(
    vocals_path: Path,
    pth_path: Path,
    index_path: Path,
    output_path: Path,
    pitch: int,
    index_rate: float,
    protect: float,
    log,
) -> Path:
    index_rate = max(0.0, min(1.0, float(index_rate)))
    protect = max(0.0, min(0.75, float(protect)))
    log(f"推理参数：变调 {pitch:+d}，索引强度 {index_rate:.2f}，辅音保护 {protect:.2f}")
    run_command(
        [
            str(PYTHON),
            "core.py",
            "infer",
            "--pitch",
            str(pitch),
            "--index_rate",
            f"{index_rate:.2f}",
            "--volume_envelope",
            "1.0",
            "--protect",
            f"{protect:.2f}",
            "--f0_method",
            "rmvpe",
            "--input_path",
            str(vocals_path),
            "--output_path",
            str(output_path),
            "--pth_path",
            str(pth_path),
            "--index_path",
            str(index_path),
            "--split_audio",
            "True",
            "--f0_autotune",
            "True",
            "--f0_autotune_strength",
            "1.0",
            "--clean_audio",
            "False",
            "--export_format",
            "WAV",
            "--embedder_model",
            "contentvec",
        ],
        log,
    )
    return output_path


def mix_cover(
    vocal_path: Path,
    instrumental_path: Path,
    output_path: Path,
    log,
    vocal_gain: float = 1.0,
    instrumental_gain: float = 1.0,
    reference_vocal_path: Path | None = None,
    auto_mix: bool = True,
) -> Path:
    if not FFMPEG.exists():
        raise FileNotFoundError(f"ffmpeg.exe not found at {FFMPEG}")

    import numpy as np
    import soundfile as sf
    from scipy.signal import resample_poly

    eps = 1e-9

    def load_audio(path: Path) -> tuple[np.ndarray, int]:
        audio, sr = sf.read(str(path), always_2d=True, dtype="float32")
        if audio.shape[1] == 1:
            audio = np.repeat(audio, 2, axis=1)
        elif audio.shape[1] > 2:
            audio = audio[:, :2]
        return audio.astype(np.float32, copy=False), int(sr)

    def resample_if_needed(audio: np.ndarray, sr: int, target_sr: int) -> np.ndarray:
        if sr == target_sr:
            return audio
        gcd = math.gcd(sr, target_sr)
        up = target_sr // gcd
        down = sr // gcd
        channels = [resample_poly(audio[:, ch], up, down).astype(np.float32) for ch in range(audio.shape[1])]
        return np.stack(channels, axis=1)

    def pad_or_trim(audio: np.ndarray, length: int) -> np.ndarray:
        if len(audio) == length:
            return audio
        if len(audio) > length:
            return audio[:length]
        return np.pad(audio, ((0, length - len(audio)), (0, 0)))

    def mono(audio: np.ndarray) -> np.ndarray:
        if audio.ndim == 1:
            return audio.astype(np.float32, copy=False)
        return np.mean(audio, axis=1).astype(np.float32, copy=False)

    def clamp(value: float, min_value: float, max_value: float) -> float:
        return max(min_value, min(max_value, float(value)))

    def rms(audio: np.ndarray, mask: np.ndarray | None = None) -> float:
        data = mono(audio)
        if mask is not None and len(mask) == len(data) and np.any(mask):
            data = data[mask]
        if data.size == 0:
            return eps
        data64 = data.astype(np.float64, copy=False)
        return float(np.sqrt(np.mean(data64 * data64)) + eps)

    def to_db(value: float) -> float:
        return 20.0 * math.log10(max(value, eps))

    def frame_rms_values(audio: np.ndarray, frame: int, hop: int) -> tuple[np.ndarray, np.ndarray]:
        data = mono(audio)
        if len(data) == 0:
            return np.array([], dtype=np.int64), np.array([], dtype=np.float32)
        if len(data) <= frame:
            return np.array([len(data) // 2], dtype=np.int64), np.array([rms(data)], dtype=np.float32)
        starts = np.arange(0, len(data) - frame + 1, hop, dtype=np.int64)
        values = np.empty(len(starts), dtype=np.float32)
        for i, start in enumerate(starts):
            chunk = data[start : start + frame]
            chunk64 = chunk.astype(np.float64, copy=False)
            values[i] = float(np.sqrt(np.mean(chunk64 * chunk64)) + eps)
        centers = starts + frame // 2
        return centers, values

    def build_active_mask(reference: np.ndarray, sample_rate: int, length: int) -> np.ndarray:
        frame = max(1024, int(sample_rate * 0.046))
        hop = max(256, frame // 4)
        centers, values = frame_rms_values(reference, frame, hop)
        if values.size == 0:
            return np.ones(length, dtype=bool)
        positive = values[values > eps]
        if positive.size == 0:
            return np.ones(length, dtype=bool)
        high = float(np.percentile(positive, 95))
        floor = float(np.percentile(positive, 20))
        threshold = max(high * (10.0 ** (-32.0 / 20.0)), floor * 1.8, 1e-5)
        active_frames = values >= threshold
        if np.mean(active_frames) < 0.02:
            threshold = max(high * (10.0 ** (-42.0 / 20.0)), 1e-6)
            active_frames = values >= threshold

        mask = np.zeros(length, dtype=bool)
        half = frame // 2
        for center, is_active in zip(centers, active_frames):
            if not is_active:
                continue
            start = max(0, int(center) - half)
            end = min(length, int(center) + half)
            mask[start:end] = True
        if not np.any(mask):
            return np.ones(length, dtype=bool)
        return mask

    def build_duck_curve(vocal_audio: np.ndarray, active_mask: np.ndarray, sample_rate: int, depth: float) -> np.ndarray:
        length = len(vocal_audio)
        if length == 0 or depth <= 0:
            return np.ones(length, dtype=np.float32)
        frame = max(1024, int(sample_rate * 0.050))
        hop = max(256, frame // 4)
        centers, values = frame_rms_values(vocal_audio, frame, hop)
        if values.size == 0:
            return np.ones(length, dtype=np.float32)
        x = np.arange(length, dtype=np.float32)
        envelope = np.interp(x, centers.astype(np.float32), values.astype(np.float32)).astype(np.float32)
        active_values = envelope[active_mask] if len(active_mask) == length and np.any(active_mask) else envelope
        scale = float(np.percentile(active_values, 95)) if active_values.size else 0.0
        if scale <= eps:
            return np.ones(length, dtype=np.float32)
        envelope = np.clip(envelope / scale, 0.0, 1.0)
        curve = 1.0 - clamp(depth, 0.0, 0.30) * envelope
        if len(active_mask) == length:
            curve = np.where(active_mask, curve, 1.0)
        return curve.astype(np.float32)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    vocal_gain = clamp(vocal_gain, 0.05, 5.0)
    instrumental_gain = clamp(instrumental_gain, 0.05, 5.0)

    log(f"混音输入人声：{vocal_path}")
    log(f"混音输入伴奏：{instrumental_path}")

    vocal, vocal_sr = load_audio(vocal_path)
    instrumental, instrumental_sr = load_audio(instrumental_path)
    target_sr = 48000
    vocal = resample_if_needed(vocal, vocal_sr, target_sr)
    instrumental = resample_if_needed(instrumental, instrumental_sr, target_sr)

    length = max(len(vocal), len(instrumental))
    vocal = pad_or_trim(vocal, length)
    instrumental = pad_or_trim(instrumental, length)

    final_vocal_gain = vocal_gain
    final_instrumental_gain = instrumental_gain
    duck_curve = np.ones(length, dtype=np.float32)

    if auto_mix and reference_vocal_path and reference_vocal_path.exists():
        reference_vocal, reference_sr = load_audio(reference_vocal_path)
        reference_vocal = resample_if_needed(reference_vocal, reference_sr, target_sr)
        reference_vocal = pad_or_trim(reference_vocal, length)
        active_mask = build_active_mask(reference_vocal, target_sr, length)

        reference_vocal_rms = rms(reference_vocal, active_mask)
        converted_vocal_rms = rms(vocal, active_mask)
        instrumental_rms = rms(instrumental, active_mask)
        original_balance_db = to_db(reference_vocal_rms) - to_db(instrumental_rms)

        auto_vocal_gain = clamp((reference_vocal_rms / max(converted_vocal_rms, eps)) * 1.06, 0.25, 4.0)
        final_vocal_gain = clamp(auto_vocal_gain * vocal_gain, 0.05, 6.0)
        final_instrumental_gain = clamp(1.0 * instrumental_gain, 0.05, 3.0)

        # 原唱越容易被伴奏盖住，ducking 越保守；原唱本来很靠前，就稍微给人声让位。
        duck_depth = clamp(0.10 + (original_balance_db + 10.0) * 0.006, 0.07, 0.18)
        duck_curve = build_duck_curve(vocal * final_vocal_gain, active_mask, target_sr, duck_depth)

        ducked_instrumental = instrumental * final_instrumental_gain * duck_curve[:, None]
        final_balance_db = to_db(rms(vocal * final_vocal_gain, active_mask)) - to_db(
            rms(ducked_instrumental, active_mask)
        )
        log(
            "自动混音："
            f"原唱声伴比例 {original_balance_db:+.1f} dB，"
            f"成品声伴比例 {final_balance_db:+.1f} dB，"
            f"人声自动增益 {auto_vocal_gain:.2f}×，"
            f"手动微调 人声 {vocal_gain:.2f}× / 伴奏 {instrumental_gain:.2f}×，"
            f"伴奏让位约 {duck_depth * 100:.0f}%"
        )
    else:
        if auto_mix:
            log("自动混音：未找到原唱参考人声，已退回手动音量混合。")
        else:
            log("自动混音已关闭：使用手动音量混合。")
        final_vocal_gain = clamp(vocal_gain, 0.1, 3.0)
        final_instrumental_gain = clamp(instrumental_gain, 0.1, 3.0)

    mixed = instrumental * final_instrumental_gain * duck_curve[:, None] + vocal * final_vocal_gain
    peak = float(np.max(np.abs(mixed))) if mixed.size else 0.0
    if peak > 0.98:
        mixed *= 0.98 / peak

    temp_wav = output_path.with_suffix(".mixed_tmp.wav")
    sf.write(str(temp_wav), mixed, target_sr, subtype="PCM_16")

    log(
        f"已完成波形混合：最终人声增益 {final_vocal_gain:.2f}，"
        f"最终伴奏增益 {final_instrumental_gain:.2f}，峰值 {peak:.3f}"
    )
    run_command(
        [
            str(FFMPEG),
            "-y",
            "-i",
            str(temp_wav),
            "-af",
            "alimiter=limit=0.98,loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "320k",
            str(output_path),
        ],
        log,
    )
    try:
        temp_wav.unlink()
    except OSError:
        pass
    return output_path


def create_cover(
    song_path: Path,
    model_name: str,
    voice_dir: Path | None,
    pth_path: Path | None,
    index_path: Path | None,
    output_dir: Path,
    pitch: int,
    epochs: int,
    batch_size: int,
    sample_rate: int,
    index_rate: float,
    gpu: str,
    log,
    auto_pitch: bool = True,
    clarity_mode: bool = True,
    protect: float = 0.50,
    auto_mix: bool = True,
    vocal_gain: float = 1.0,
    instrumental_gain: float = 1.0,
    force_train: bool = False,
) -> Path:
    if not song_path.exists():
        raise FileNotFoundError(f"Song file not found: {song_path}")
    requested_model_name = (model_name or "").strip()
    model_name = "auto" if not requested_model_name else requested_model_name
    output_dir.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    work_dir = output_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{safe_filename(song_path.stem)}"
    work_dir.mkdir(parents=True, exist_ok=True)

    if pth_path and index_path:
        pth, index = pth_path, index_path
        model_name = safe_filename(pth.stem, "manual_model")
        log(f"使用手动模型：{pth}")
        log(f"使用手动索引：{index}")
    else:
        if force_train and model_name.lower() in {"auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}:
            model_name = "new_voice"
        model_name, pth, index = prepare_model(
            model_name,
            voice_dir,
            sample_rate,
            epochs,
            batch_size,
            gpu,
            log,
            force_train=force_train,
        )

    vocals, instrumental = separate_song(song_path, work_dir, log)
    if auto_pitch:
        estimated_pitch = estimate_pitch_shift(model_name, vocals, log)
        if estimated_pitch is not None:
            pitch = estimated_pitch

    song_stem = safe_filename(song_path.stem)
    model_stem = safe_filename(model_name, "model")
    converted_vocals = work_dir / f"{song_stem}_{model_stem}_03_converted_vocals.wav"
    effective_index_rate = max(0.0, min(1.0, float(index_rate)))
    effective_protect = max(0.0, min(0.75, float(protect)))
    if clarity_mode:
        effective_index_rate = min(effective_index_rate, 0.45)
        effective_protect = max(effective_protect, 0.50)
        log(
            "咬字清晰模式已开启："
            f"索引强度控制为 {effective_index_rate:.2f}，辅音保护提高到 {effective_protect:.2f}"
        )
    else:
        log("咬字清晰模式已关闭：使用当前索引强度和辅音保护。")
    infer_vocals(vocals, pth, index, converted_vocals, pitch, effective_index_rate, effective_protect, log)
    final_path = output_dir / f"{work_dir.name}_{model_stem}_mixed_cover.mp3"
    latest_path = output_dir / f"{song_stem}_{model_stem}_mixed_cover.mp3"
    mix_cover(
        converted_vocals,
        instrumental,
        final_path,
        log,
        vocal_gain=vocal_gain,
        instrumental_gain=instrumental_gain,
        reference_vocal_path=vocals,
        auto_mix=auto_mix,
    )
    if latest_path != final_path:
        shutil.copy2(final_path, latest_path)
    log(f"完成混音成品：{final_path}")
    log(f"最新成品副本：{latest_path}")
    log(f"中间文件目录：{work_dir}")
    return final_path


class CoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("大尸兄一键翻唱")
        self.root.geometry("920x680")
        self.root.minsize(860, 620)
        self.queue: queue.Queue[str] = queue.Queue()
        self.running = False

        self.song = tk.StringVar()
        self.voice_dir = tk.StringVar()
        self.model_name = tk.StringVar(value="my_voice")
        self.pth = tk.StringVar()
        self.index = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.pitch = tk.IntVar(value=0)
        self.epochs = tk.IntVar(value=200)
        self.batch_size = tk.IntVar(value=8)
        self.sample_rate = tk.IntVar(value=48000)
        self.index_rate = tk.DoubleVar(value=0.50)
        self.gpu = tk.StringVar(value="0")

        self.build_ui()
        self.root.after(200, self.poll)

    def build_ui(self):
        pad = {"padx": 10, "pady": 6}
        header = ttk.Frame(self.root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="大尸兄一键翻唱", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(header, text="选择你的声音素材或已有模型，再选择歌曲，自动分离、转换、混音。", foreground="#555").pack(anchor="w")

        files = ttk.LabelFrame(self.root, text="输入")
        files.pack(fill="x", **pad)
        self.row(files, "歌曲文件", self.song, self.choose_song)
        self.row(files, "我的声音素材文件夹", self.voice_dir, self.choose_voice_dir)
        self.row(files, "已有 .pth 模型", self.pth, self.choose_pth)
        self.row(files, "已有 .index 索引", self.index, self.choose_index)
        self.row(files, "输出目录", self.output_dir, self.choose_output_dir)

        opts = ttk.LabelFrame(self.root, text="参数")
        opts.pack(fill="x", **pad)
        grid = ttk.Frame(opts)
        grid.pack(fill="x", padx=8, pady=8)
        self.labeled_entry(grid, "模型名", self.model_name, 0, 0)
        self.labeled_spin(grid, "变调", self.pitch, -24, 24, 0, 2)
        self.labeled_spin(grid, "训练轮数", self.epochs, 1, 10000, 1, 0)
        self.labeled_spin(grid, "Batch", self.batch_size, 1, 50, 1, 2)
        self.labeled_combo(grid, "采样率", self.sample_rate, [32000, 40000, 48000], 2, 0)
        self.labeled_entry(grid, "GPU", self.gpu, 2, 2)
        self.labeled_entry(grid, "索引强度", self.index_rate, 3, 0)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="安装/检查翻唱依赖", command=self.install_deps).pack(side="left", padx=6)
        ttk.Button(actions, text="一键生成翻唱", command=self.start_cover).pack(side="left", padx=6)
        ttk.Button(actions, text="打开输出目录", command=self.open_output).pack(side="left", padx=6)

        log_frame = ttk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)
        self.write("准备就绪。第一次没有模型时会先训练，可能需要较长时间。")

    def row(self, parent, label, var, command):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(frame, text=label, width=18).pack(side="left")
        ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="选择", command=command).pack(side="left", padx=(8, 0))

    def labeled_entry(self, parent, label, var, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Entry(parent, textvariable=var, width=20).grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)
        parent.columnconfigure(col + 1, weight=1)

    def labeled_spin(self, parent, label, var, minv, maxv, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Spinbox(parent, textvariable=var, from_=minv, to=maxv, width=18).grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)

    def labeled_combo(self, parent, label, var, values, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Combobox(parent, textvariable=var, values=values, width=18, state="readonly").grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)

    def choose_song(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a *.ogg *.aac *.mp4 *.webm"), ("All files", "*.*")])
        if path:
            self.song.set(path)

    def choose_voice_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.voice_dir.set(path)
            if self.model_choice.get() == AUTO_MODEL_LABEL:
                self.model_choice.set(TRAIN_MODEL_LABEL)
                self.apply_model_choice(write_log=False)
            self.status.set(f"已选择训练素材：{Path(path).name}")

    def choose_pth(self):
        path = filedialog.askopenfilename(filetypes=[("RVC model", "*.pth"), ("All files", "*.*")])
        if path:
            self.pth.set(path)

    def choose_index(self):
        path = filedialog.askopenfilename(filetypes=[("RVC index", "*.index"), ("All files", "*.*")])
        if path:
            self.index.set(path)

    def choose_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def open_output(self):
        path = Path(self.output_dir.get())
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def write(self, message: str):
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def log_threadsafe(self, message: str):
        self.queue.put(message)

    def poll(self):
        try:
            while True:
                self.write(self.queue.get_nowait())
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def install_deps(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行。")
            return
        self.running = True

        def task():
            try:
                ensure_demucs(self.log_threadsafe)
                self.log_threadsafe("翻唱依赖已就绪。")
            except Exception as exc:
                self.log_threadsafe(f"失败：{exc}")
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def start_cover(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行。")
            return
        if not self.song.get():
            messagebox.showerror("缺少歌曲", "请先选择歌曲文件。")
            return
        if (self.pth.get() and not self.index.get()) or (self.index.get() and not self.pth.get()):
            messagebox.showerror("模型不完整", "已有模型模式需要同时选择 .pth 和 .index。")
            return

        self.running = True

        def task():
            try:
                result = create_cover(
                    song_path=Path(self.song.get()),
                    model_name=self.model_name.get(),
                    voice_dir=Path(self.voice_dir.get()) if self.voice_dir.get() else None,
                    pth_path=Path(self.pth.get()) if self.pth.get() else None,
                    index_path=Path(self.index.get()) if self.index.get() else None,
                    output_dir=Path(self.output_dir.get()),
                    pitch=int(self.pitch.get()),
                    epochs=int(self.epochs.get()),
                    batch_size=int(self.batch_size.get()),
                    sample_rate=int(self.sample_rate.get()),
                    index_rate=float(self.index_rate.get()),
                    gpu=self.gpu.get().strip() or "0",
                    log=self.log_threadsafe,
                )
                self.log_threadsafe(f"生成完成：{result}")
            except Exception as exc:
                self.log_threadsafe(f"失败：{exc}")
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()


class CoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("大尸兄一键翻唱")
        self.root.geometry("980x720")
        self.root.minsize(900, 640)
        self.queue: queue.Queue[str] = queue.Queue()
        self.running = False
        self.model_lookup: dict[str, dict[str, object]] = {}

        self.song = tk.StringVar()
        self.voice_dir = tk.StringVar()
        self.model_choice = tk.StringVar(value=AUTO_MODEL_LABEL)
        self.model_name = tk.StringVar(value="auto")
        self.pth = tk.StringVar()
        self.index = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT_DIR))
        self.auto_pitch = tk.BooleanVar(value=True)
        self.clarity_mode = tk.BooleanVar(value=True)
        self.auto_mix = tk.BooleanVar(value=True)
        self.pitch = tk.IntVar(value=0)
        self.epochs = tk.IntVar(value=200)
        self.batch_size = tk.IntVar(value=8)
        self.sample_rate = tk.IntVar(value=48000)
        self.index_rate = tk.DoubleVar(value=0.50)
        self.protect = tk.DoubleVar(value=0.50)
        self.vocal_gain = tk.DoubleVar(value=1.0)
        self.instrumental_gain = tk.DoubleVar(value=1.0)
        self.gpu = tk.StringVar(value="0")
        self.open_when_done = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="就绪")

        self.build_ui()
        self.refresh_models(write_log=False)
        self.root.after(200, self.poll)

    def build_ui(self):
        pad = {"padx": 10, "pady": 6}
        header = ttk.Frame(self.root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="大尸兄一键翻唱", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="选择歌曲后自动找模型、分离人声和伴奏、估算变调、转换声线，并按原唱声伴比例智能混音。",
            foreground="#555",
        ).pack(anchor="w")

        files = ttk.LabelFrame(self.root, text="1. 歌曲与输出")
        files.pack(fill="x", **pad)
        self.row(files, "歌曲文件", self.song, self.choose_song)
        self.row(files, "输出目录", self.output_dir, self.choose_output_dir)

        model_box = ttk.LabelFrame(self.root, text="2. 声音模型")
        model_box.pack(fill="x", **pad)
        model_row = ttk.Frame(model_box)
        model_row.pack(fill="x", padx=8, pady=4)
        ttk.Label(model_row, text="模型", width=18).pack(side="left")
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_choice, state="readonly")
        self.model_combo.pack(side="left", fill="x", expand=True)
        self.model_combo.bind("<<ComboboxSelected>>", lambda _event: self.apply_model_choice())
        ttk.Button(model_row, text="刷新", command=self.refresh_models).pack(side="left", padx=(8, 0))
        ttk.Button(model_row, text="自动识别", command=self.auto_detect_model).pack(side="left", padx=(8, 0))
        self.entry_row(model_box, "新模型名", self.model_name)
        self.row(model_box, "训练素材文件夹", self.voice_dir, self.choose_voice_dir)
        self.row(model_box, "手动 .pth", self.pth, self.choose_pth)
        self.row(model_box, "手动 .index", self.index, self.choose_index)

        opts = ttk.LabelFrame(self.root, text="3. 一键参数")
        opts.pack(fill="x", **pad)
        grid = ttk.Frame(opts)
        grid.pack(fill="x", padx=8, pady=8)
        ttk.Checkbutton(grid, text="自动估算变调", variable=self.auto_pitch).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        self.labeled_spin(grid, "手动变调", self.pitch, -24, 24, 0, 1)
        self.labeled_entry(grid, "索引强度", self.index_rate, 0, 3)
        ttk.Checkbutton(grid, text="自动匹配原唱混音", variable=self.auto_mix).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        self.labeled_entry(grid, "人声微调", self.vocal_gain, 1, 1)
        self.labeled_entry(grid, "伴奏微调", self.instrumental_gain, 1, 3)
        ttk.Checkbutton(grid, text="咬字清晰模式", variable=self.clarity_mode).grid(row=2, column=0, sticky="w", padx=6, pady=4)
        self.labeled_entry(grid, "辅音保护", self.protect, 2, 1)
        self.labeled_entry(grid, "GPU", self.gpu, 2, 3)
        self.labeled_spin(grid, "训练轮数", self.epochs, 1, 10000, 3, 0)
        self.labeled_spin(grid, "Batch", self.batch_size, 1, 50, 3, 2)
        self.labeled_combo(grid, "采样率", self.sample_rate, [32000, 40000, 48000], 3, 4)
        for col in (1, 3, 5):
            grid.columnconfigure(col, weight=1)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="安装/检查依赖", command=self.install_deps).pack(side="left", padx=6)
        ttk.Button(actions, text="一键生成混音翻唱", command=self.start_cover).pack(side="left", padx=6)
        ttk.Button(actions, text="打开输出目录", command=self.open_output).pack(side="left", padx=6)
        ttk.Checkbutton(actions, text="完成后打开输出目录", variable=self.open_when_done).pack(side="left", padx=16)

        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(status_bar, textvariable=self.status, foreground="#555").pack(anchor="w")

        log_frame = ttk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)
        self.write("准备就绪。一般只要选择歌曲，再点“一键生成混音翻唱”。默认会自动匹配原唱人声/伴奏比例。")

    def row(self, parent, label, var, command):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(frame, text=label, width=18).pack(side="left")
        ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="选择", command=command).pack(side="left", padx=(8, 0))

    def entry_row(self, parent, label, var):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", padx=8, pady=4)
        ttk.Label(frame, text=label, width=18).pack(side="left")
        ttk.Entry(frame, textvariable=var).pack(side="left", fill="x", expand=True)
        ttk.Label(frame, text="训练新模型时使用", foreground="#666").pack(side="left", padx=(8, 0))

    def labeled_entry(self, parent, label, var, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Entry(parent, textvariable=var, width=14).grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)

    def labeled_spin(self, parent, label, var, minv, maxv, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Spinbox(parent, textvariable=var, from_=minv, to=maxv, width=12).grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)

    def labeled_combo(self, parent, label, var, values, row, col):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=6, pady=4)
        ttk.Combobox(parent, textvariable=var, values=values, width=12, state="readonly").grid(row=row, column=col + 1, sticky="ew", padx=6, pady=4)

    def refresh_models(self, write_log: bool = True):
        models = discover_models()
        self.model_lookup = {str(item["label"]): item for item in models}
        choices = [AUTO_MODEL_LABEL, TRAIN_MODEL_LABEL] + list(self.model_lookup.keys()) + [MANUAL_MODEL_LABEL]
        self.model_combo.configure(values=choices)
        if self.model_choice.get() not in choices:
            self.model_choice.set(AUTO_MODEL_LABEL)
        self.apply_model_choice(write_log=False)
        self.status.set(f"已识别 {len(models)} 个可用模型")
        if write_log:
            self.write(f"已刷新模型列表：{len(models)} 个可用模型。")

    def auto_detect_model(self):
        self.model_choice.set(AUTO_MODEL_LABEL)
        self.refresh_models(write_log=True)

    def apply_model_choice(self, write_log: bool = True):
        choice = self.model_choice.get()
        if choice == AUTO_MODEL_LABEL:
            self.model_name.set("auto")
            if self.model_lookup:
                latest = next(iter(self.model_lookup.values()))
                self.pth.set(str(latest["pth"]))
                self.index.set(str(latest["index"]))
                self.status.set(f"自动模式将使用：{latest['name']}")
            else:
                self.pth.set("")
                self.index.set("")
                self.status.set("未发现现成模型；可选择训练素材文件夹")
            return
        if choice == TRAIN_MODEL_LABEL:
            if self.model_name.get().strip().lower() in {"", "auto", "自动", AUTO_MODEL_LABEL.lower()}:
                self.model_name.set("new_voice")
            self.pth.set("")
            self.index.set("")
            self.status.set("训练新模型：请输入新模型名，并选择新声音素材文件夹")
            if write_log:
                self.write("已切换到训练新模型模式。")
            return
        if choice == MANUAL_MODEL_LABEL:
            self.status.set("手动模型模式")
            return
        item = self.model_lookup.get(choice)
        if item:
            self.model_name.set(str(item["name"]))
            self.pth.set(str(item["pth"]))
            self.index.set(str(item["index"]))
            self.status.set(f"已选择模型：{item['name']}")
            if write_log:
                self.write(f"已选择模型：{item['name']}")

    def choose_song(self):
        path = filedialog.askopenfilename(filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a *.ogg *.aac *.mp4 *.webm"), ("All files", "*.*")])
        if path:
            self.song.set(path)
            self.status.set(f"已选择歌曲：{Path(path).name}")

    def choose_voice_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.voice_dir.set(path)
            if self.model_choice.get() == AUTO_MODEL_LABEL:
                self.model_choice.set(TRAIN_MODEL_LABEL)
                self.apply_model_choice(write_log=False)
            self.status.set(f"已选择训练素材：{Path(path).name}")

    def choose_pth(self):
        path = filedialog.askopenfilename(filetypes=[("RVC model", "*.pth"), ("All files", "*.*")])
        if path:
            self.pth.set(path)
            self.model_choice.set(MANUAL_MODEL_LABEL)
            self.model_name.set(Path(path).stem)
            self.status.set("已切换到手动模型模式")

    def choose_index(self):
        path = filedialog.askopenfilename(filetypes=[("RVC index", "*.index"), ("All files", "*.*")])
        if path:
            self.index.set(path)
            self.model_choice.set(MANUAL_MODEL_LABEL)
            self.status.set("已切换到手动模型模式")

    def choose_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir.set(path)

    def open_output(self):
        path = Path(self.output_dir.get())
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def write(self, message: str):
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def log_threadsafe(self, message: str):
        self.queue.put(message)

    def status_threadsafe(self, message: str):
        self.queue.put(f"__STATUS__:{message}")

    def poll(self):
        try:
            while True:
                message = self.queue.get_nowait()
                if message == "__REFRESH_MODELS__":
                    self.refresh_models(write_log=False)
                    continue
                if message.startswith("__STATUS__:"):
                    self.status.set(message.split(":", 1)[1])
                    continue
                self.write(message)
                if message.startswith("完成混音成品："):
                    self.status.set("生成完成")
        except queue.Empty:
            pass
        self.root.after(200, self.poll)

    def install_deps(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行。")
            return
        self.running = True
        self.status.set("正在检查依赖…")

        def task():
            try:
                ensure_demucs(self.log_threadsafe)
                self.log_threadsafe("翻唱依赖已就绪。")
                self.status_threadsafe("依赖已就绪")
            except Exception as exc:
                self.log_threadsafe(f"失败：{exc}")
                self.status_threadsafe("依赖检查失败")
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def start_cover(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行。")
            return
        if not self.song.get():
            messagebox.showerror("缺少歌曲", "请先选择歌曲文件。")
            return

        choice = self.model_choice.get()
        manual_mode = choice == MANUAL_MODEL_LABEL
        train_mode = choice == TRAIN_MODEL_LABEL
        if manual_mode and (not self.pth.get() or not self.index.get()):
            messagebox.showerror("模型不完整", "手动模型模式需要同时选择 .pth 和 .index。")
            return
        if train_mode:
            new_name = self.model_name.get().strip()
            if not new_name or new_name.lower() in {"auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}:
                messagebox.showerror("缺少新模型名", "请给这次新声音填写一个模型名，例如 my_voice_2。")
                return
            if not self.voice_dir.get():
                messagebox.showerror("缺少训练素材", "请先选择新声音素材文件夹。")
                return

        self.running = True
        self.status.set("正在生成翻唱…")
        self.write("开始任务：分离歌曲、转换声线、混音输出。")

        def task():
            try:
                model_name = self.model_name.get().strip() or "auto"
                pth_path = Path(self.pth.get()) if manual_mode else None
                index_path = Path(self.index.get()) if manual_mode else None
                result = create_cover(
                    song_path=Path(self.song.get()),
                    model_name=model_name,
                    voice_dir=Path(self.voice_dir.get()) if self.voice_dir.get() else None,
                    pth_path=pth_path,
                    index_path=index_path,
                    output_dir=Path(self.output_dir.get()),
                    pitch=int(self.pitch.get()),
                    epochs=int(self.epochs.get()),
                    batch_size=int(self.batch_size.get()),
                    sample_rate=int(self.sample_rate.get()),
                    index_rate=float(self.index_rate.get()),
                    gpu=self.gpu.get().strip() or "0",
                    log=self.log_threadsafe,
                    auto_pitch=bool(self.auto_pitch.get()),
                    clarity_mode=bool(self.clarity_mode.get()),
                    protect=float(self.protect.get()),
                    auto_mix=bool(self.auto_mix.get()),
                    vocal_gain=float(self.vocal_gain.get()),
                    instrumental_gain=float(self.instrumental_gain.get()),
                    force_train=train_mode,
                )
                self.log_threadsafe(f"生成完成：{result}")
                if self.open_when_done.get():
                    os.startfile(str(Path(result).parent))
            except Exception as exc:
                self.log_threadsafe(f"失败：{exc}")
                self.status_threadsafe("生成失败")
            finally:
                self.running = False
                self.queue.put("__REFRESH_MODELS__")

        threading.Thread(target=task, daemon=True).start()


def gui_main() -> None:
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    CoverApp(root)
    root.mainloop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a DaShiXiong one-click song cover.")
    parser.add_argument("--song")
    parser.add_argument("--voice-dir")
    parser.add_argument("--model-name", default="auto")
    parser.add_argument("--pth")
    parser.add_argument("--index")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--pitch", type=int, default=0)
    parser.add_argument("--no-auto-pitch", action="store_true")
    parser.add_argument("--no-clarity-mode", action="store_true")
    parser.add_argument("--protect", type=float, default=0.50)
    parser.add_argument("--no-auto-mix", action="store_true")
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--force-train", action="store_true")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--sample-rate", type=int, default=48000)
    parser.add_argument("--index-rate", type=float, default=0.50)
    parser.add_argument("--vocal-gain", type=float, default=1.0)
    parser.add_argument("--instrumental-gain", type=float, default=1.0)
    parser.add_argument("--gpu", default="0")
    parser.add_argument("--install-deps", action="store_true")
    return parser.parse_args()


def cli_main(args: argparse.Namespace) -> None:
    def log(message: str) -> None:
        print(message, flush=True)

    if args.install_deps:
        ensure_demucs(log)
        return
    if not args.song:
        gui_main()
        return
    result = create_cover(
        song_path=Path(args.song),
        model_name=args.model_name,
        voice_dir=Path(args.voice_dir) if args.voice_dir else None,
        pth_path=Path(args.pth) if args.pth else None,
        index_path=Path(args.index) if args.index else None,
        output_dir=Path(args.output_dir),
        pitch=args.pitch,
        epochs=args.epochs,
        batch_size=args.batch_size,
        sample_rate=args.sample_rate,
        index_rate=args.index_rate,
        gpu=args.gpu,
        log=log,
        auto_pitch=not args.no_auto_pitch,
        clarity_mode=not args.no_clarity_mode,
        protect=args.protect,
        auto_mix=not args.no_auto_mix,
        vocal_gain=args.vocal_gain,
        instrumental_gain=args.instrumental_gain,
        force_train=args.force_train,
    )
    print(result)


if __name__ == "__main__":
    cli_main(parse_args())
