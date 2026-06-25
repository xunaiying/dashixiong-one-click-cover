import argparse
import math
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import json
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.request import Request, urlopen


APP_DIR = Path(__file__).resolve().parent
ENV_PYTHON = APP_DIR / "env" / "python.exe"
PYTHON = ENV_PYTHON if ENV_PYTHON.exists() else Path(sys.executable)
FFMPEG = APP_DIR / "ffmpeg.exe"
DEFAULT_OUTPUT_DIR = APP_DIR / "outputs" / "covers"
LOG_DIR = APP_DIR / "logs"
AUTO_MODEL_LABEL = "自动选择最新可用模型"
TRAIN_MODEL_LABEL = "训练新模型（使用新声音）"
MANUAL_MODEL_LABEL = "手动选择 .pth + .index"
APP_VERSION = "1.0.9"
GITHUB_REPO = "xunaiying/dashixiong-one-click-cover"
GITHUB_API_LATEST = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases/latest"
PRESERVE_UPDATE_TOPLEVEL = {
    ".git",
    "__pycache__",
    "env",
    "logs",
    "outputs",
    "updates",
    "tmp",
    "temp",
}
PRESERVE_UPDATE_FILES = {
    "ffmpeg.exe",
    "ffprobe.exe",
}

AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".aiff", ".webm", ".mp4"}


def slugify(value: str) -> str:
    value = value.strip() or "my_voice"
    value = re.sub(r"[^\w.-]+", "_", value, flags=re.ASCII)
    value = value.strip("._-")
    return value or "my_voice"


def safe_filename(value: str, default: str = "song") -> str:
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return value or default


def parse_version(value: str) -> tuple[int, ...]:
    text = (value or "").strip().lower()
    if text.startswith("v"):
        text = text[1:]
    parts = re.findall(r"\d+", text)
    return tuple(int(part) for part in parts) if parts else (0,)


def is_newer_version(remote: str, local: str = APP_VERSION) -> bool:
    left = list(parse_version(remote))
    right = list(parse_version(local))
    width = max(len(left), len(right))
    left.extend([0] * (width - len(left)))
    right.extend([0] * (width - len(right)))
    return tuple(left) > tuple(right)


def latest_release_info(timeout: int = 10) -> dict[str, object]:
    req = Request(
        GITHUB_API_LATEST,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"DaShiXiong-OneClickCover/{APP_VERSION}",
        },
    )
    with urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    tag = str(data.get("tag_name") or "").strip()
    assets = data.get("assets") or []
    zip_url = ""
    zip_name = ""
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = str(asset.get("name") or "")
            url = str(asset.get("browser_download_url") or "")
            if name.lower().endswith(".zip") and url:
                zip_name = name
                zip_url = url
                break
    return {
        "tag": tag,
        "version": tag[1:] if tag.lower().startswith("v") else tag,
        "html_url": str(data.get("html_url") or GITHUB_RELEASES_URL),
        "zip_url": zip_url,
        "zip_name": zip_name or f"dashixiong-one-click-cover-{tag}.zip",
        "body": str(data.get("body") or ""),
    }


def check_update_available() -> dict[str, object]:
    info = latest_release_info()
    version = str(info.get("version") or "")
    info["current_version"] = APP_VERSION
    info["is_newer"] = is_newer_version(version, APP_VERSION)
    return info


def download_file(url: str, destination: Path, log, progress_hook=None, timeout: int = 30) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": f"DaShiXiong-OneClickCover/{APP_VERSION}"})
    with urlopen(req, timeout=timeout) as resp, open(destination, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            f.write(chunk)
            downloaded += len(chunk)
            if progress_hook and total:
                progress_hook(min(100.0, downloaded / total * 100.0))
    log(f"下载完成：{destination} ({human_size(file_size(destination))})")
    return destination


def is_preserved_update_path(relative_path: Path) -> bool:
    if not relative_path.parts:
        return True
    first = relative_path.parts[0]
    first_lower = first.lower()
    if first_lower in PRESERVE_UPDATE_TOPLEVEL:
        return True
    if len(relative_path.parts) == 1 and first_lower in PRESERVE_UPDATE_FILES:
        return True
    return False


def find_zip_root(extract_dir: Path) -> Path:
    children = list(extract_dir.iterdir())
    dirs = [p for p in children if p.is_dir()]
    files = [p for p in children if p.is_file()]
    if len(dirs) == 1 and not files and (dirs[0] / "one_click_cover.py").exists():
        return dirs[0]
    return extract_dir


def apply_update_zip(zip_path: Path, app_dir: Path, log) -> dict[str, int]:
    if not zip_path.exists():
        raise FileNotFoundError(f"更新包不存在：{zip_path}")
    updates_dir = app_dir / "updates"
    extract_dir = updates_dir / f"extract_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    source_root = find_zip_root(extract_dir)

    copied_files = 0
    skipped_files = 0
    created_dirs = 0
    for src in sorted(source_root.rglob("*"), key=lambda p: len(p.parts)):
        relative = src.relative_to(source_root)
        if is_preserved_update_path(relative):
            if src.is_file():
                skipped_files += 1
            continue
        dst = app_dir / relative
        if src.is_dir():
            if not dst.exists():
                dst.mkdir(parents=True, exist_ok=True)
                created_dirs += 1
            continue
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied_files += 1

    try:
        shutil.rmtree(extract_dir)
    except OSError:
        pass
    log(f"更新覆盖完成：复制 {copied_files} 个文件，跳过 {skipped_files} 个本地文件，创建 {created_dirs} 个目录。")
    return {"copied_files": copied_files, "skipped_files": skipped_files, "created_dirs": created_dirs}


def download_and_apply_update(info: dict[str, object], log, progress_hook=None) -> dict[str, int]:
    zip_url = str(info.get("zip_url") or "")
    if not zip_url:
        raise RuntimeError("最新 Release 没有找到可下载的 zip 包。")
    tag = str(info.get("tag") or "latest")
    zip_name = safe_filename(str(info.get("zip_name") or f"update_{tag}.zip"), "update.zip")
    updates_dir = APP_DIR / "updates"
    package_path = updates_dir / zip_name
    log(f"开始下载更新包：{zip_url}")
    download_file(zip_url, package_path, log, progress_hook=progress_hook)
    log("开始应用更新：会保留 env/logs/outputs/updates 等本地数据。")
    result = apply_update_zip(package_path, APP_DIR, log)
    version_file = APP_DIR / "VERSION"
    try:
        version_file.write_text(str(info.get("version") or tag).strip() + "\n", encoding="utf-8")
    except OSError:
        pass
    return result


def new_model_default_name() -> str:
    return f"new_voice_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def model_internal_name(display_name: str) -> str:
    """Return an ASCII-safe internal model id while allowing Chinese display names."""
    raw = (display_name or "").strip()
    ascii_name = re.sub(r"[^\w.-]+", "_", raw, flags=re.ASCII).strip("._-")
    if ascii_name:
        if ascii_name[0].isdigit():
            ascii_name = f"voice_{ascii_name}"
        return ascii_name
    return new_model_default_name()


def model_display_file(model_name: str) -> Path:
    return LOG_DIR / model_name / "display_name.txt"


def read_model_display_name(model_name: str) -> str:
    path = model_display_file(model_name)
    if path.exists():
        try:
            display = path.read_text(encoding="utf-8").strip()
            if display:
                return display
        except OSError:
            pass
    return model_name


def write_model_display_name(model_name: str, display_name: str) -> None:
    display = (display_name or "").strip()
    if not display or display == model_name:
        return
    path = model_display_file(model_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(display, encoding="utf-8")


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


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "--:--"
    seconds = max(0, int(seconds))
    return str(timedelta(seconds=seconds))


def latest_training_checkpoints(model_name: str) -> list[dict[str, object]]:
    model_dir = LOG_DIR / model_name
    if not model_dir.exists():
        return []
    checkpoints: list[dict[str, object]] = []
    pattern = re.compile(r"_(\d+)e_(\d+)s\.pth$", re.IGNORECASE)
    for pth in model_dir.glob("*.pth"):
        if pth.name.startswith(("G_", "D_")):
            continue
        match = pattern.search(pth.name)
        if not match:
            continue
        epoch = int(match.group(1))
        step = int(match.group(2))
        checkpoints.append(
            {
                "path": pth,
                "epoch": epoch,
                "step": step,
                "mtime": pth.stat().st_mtime,
            }
        )
    return sorted(checkpoints, key=lambda item: float(item["mtime"]), reverse=True)


def count_filelist_rows(model_name: str) -> int:
    filelist = LOG_DIR / model_name / "filelist.txt"
    if not filelist.exists():
        return 0
    try:
        with filelist.open("r", encoding="utf-8", errors="ignore") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def read_tensorboard_progress(model_name: str) -> dict[str, float] | None:
    eval_dir = LOG_DIR / model_name / "eval"
    if not eval_dir.exists():
        return None
    try:
        from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

        ea = EventAccumulator(str(eval_dir), size_guidance={"scalars": 0})
        ea.Reload()
        tags = ea.Tags().get("scalars", [])
        if not tags:
            return None
        preferred = [
            "grad_avg_50/norm_g",
            "loss_avg_50/g/total",
            "learning_rate",
            "loss/g/total",
        ]
        tag = next((candidate for candidate in preferred if candidate in tags), tags[0])
        events = ea.Scalars(tag)
        if not events:
            return None
        latest = events[-1]
        data: dict[str, float] = {
            "last_step": float(latest.step),
            "last_wall_time": float(latest.wall_time),
        }
        if len(events) >= 2 and events[-1].step > events[0].step:
            first = events[0]
            data["sec_per_step"] = float((latest.wall_time - first.wall_time) / (latest.step - first.step))
        return data
    except Exception:
        return None


def get_training_progress(model_name: str, total_epochs: int, batch_size: int) -> dict[str, object] | None:
    model_name = (model_name or "").strip()
    if not model_name:
        return None
    total_epochs = max(1, int(total_epochs or 1))
    batch_size = max(1, int(batch_size or 1))
    model_dir = LOG_DIR / model_name
    if not model_dir.exists():
        return None

    checkpoints = latest_training_checkpoints(model_name)
    latest_checkpoint = checkpoints[0] if checkpoints else None
    filelist_rows = count_filelist_rows(model_name)
    fallback_steps_per_epoch = math.ceil(filelist_rows / batch_size) if filelist_rows else 0

    steps_per_epoch: float | None = None
    if latest_checkpoint and int(latest_checkpoint["epoch"]) > 0:
        steps_per_epoch = float(latest_checkpoint["step"]) / float(latest_checkpoint["epoch"])
    elif fallback_steps_per_epoch:
        steps_per_epoch = float(fallback_steps_per_epoch)
    if not steps_per_epoch or steps_per_epoch <= 0:
        return None

    tb = read_tensorboard_progress(model_name) or {}
    current_step = tb.get("last_step")
    last_wall_time = tb.get("last_wall_time")
    sec_per_step = tb.get("sec_per_step")

    if current_step is None and latest_checkpoint:
        current_step = float(latest_checkpoint["step"])
    if sec_per_step is None and len(checkpoints) >= 2:
        newest = checkpoints[0]
        older = checkpoints[1]
        step_delta = float(newest["step"]) - float(older["step"])
        time_delta = float(newest["mtime"]) - float(older["mtime"])
        if step_delta > 0 and time_delta > 0:
            sec_per_step = time_delta / step_delta
    if current_step is None:
        return None

    total_steps = steps_per_epoch * total_epochs
    current_epoch = current_step / steps_per_epoch
    progress_percent = max(0.0, min(100.0, current_step / total_steps * 100.0))
    remaining_seconds = None
    eta = None
    steps_per_minute = None
    if sec_per_step and sec_per_step > 0:
        remaining_steps = max(0.0, total_steps - current_step)
        remaining_seconds = remaining_steps * sec_per_step
        eta = datetime.now() + timedelta(seconds=remaining_seconds)
        steps_per_minute = 60.0 / sec_per_step

    return {
        "model_name": model_name,
        "current_step": int(current_step),
        "total_steps": int(round(total_steps)),
        "current_epoch": current_epoch,
        "total_epochs": total_epochs,
        "progress_percent": progress_percent,
        "steps_per_epoch": steps_per_epoch,
        "filelist_rows": filelist_rows,
        "batch_size": batch_size,
        "steps_per_minute": steps_per_minute,
        "remaining_seconds": remaining_seconds,
        "eta": eta,
        "last_wall_time": last_wall_time,
        "latest_checkpoint_epoch": int(latest_checkpoint["epoch"]) if latest_checkpoint else None,
        "latest_checkpoint_step": int(latest_checkpoint["step"]) if latest_checkpoint else None,
        "latest_checkpoint_path": latest_checkpoint["path"] if latest_checkpoint else None,
    }


def format_training_progress(snapshot: dict[str, object] | None) -> str:
    if not snapshot:
        return "训练进度：等待训练日志写入…"
    current_epoch = float(snapshot["current_epoch"])
    total_epochs = int(snapshot["total_epochs"])
    percent = float(snapshot["progress_percent"])
    current_step = int(snapshot["current_step"])
    total_steps = int(snapshot["total_steps"])
    speed = snapshot.get("steps_per_minute")
    remaining = snapshot.get("remaining_seconds")
    eta = snapshot.get("eta")
    speed_text = f"{float(speed):.1f} step/分钟" if speed else "速度计算中"
    eta_text = eta.strftime("%H:%M:%S") if isinstance(eta, datetime) else "--:--"
    return (
        f"训练进度：第 {current_epoch:.1f}/{total_epochs} 轮，总进度 {percent:.1f}%，"
        f"step {current_step}/{total_steps}，{speed_text}，"
        f"剩余约 {format_duration(float(remaining)) if remaining is not None else '--:--'}，"
        f"预计 {eta_text} 完成"
    )


def run_training_command(
    args: list[str],
    model_name: str,
    total_epochs: int,
    batch_size: int,
    log,
    progress_hook=None,
    cwd: Path = APP_DIR,
) -> None:
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

    stop_event = threading.Event()
    last_reported_step: int | None = None

    def monitor() -> None:
        nonlocal last_reported_step
        time.sleep(5)
        while not stop_event.is_set():
            snapshot = get_training_progress(model_name, total_epochs, batch_size)
            if snapshot:
                step = int(snapshot["current_step"])
                if step != last_reported_step:
                    last_reported_step = step
                    message = format_training_progress(snapshot)
                    log(message)
                    if progress_hook:
                        progress_hook(snapshot)
            stop_event.wait(15)

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    try:
        for line in process.stdout or []:
            log(line.rstrip())
        code = process.wait()
    finally:
        stop_event.set()
        monitor_thread.join(timeout=1)

    snapshot = get_training_progress(model_name, total_epochs, batch_size)
    if snapshot:
        message = format_training_progress(snapshot)
        log(message)
        if progress_hook:
            progress_hook(snapshot)
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


def human_size(num_bytes: int | float) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return 0


def resolve_model_for_cleanup(model_name: str) -> tuple[str, Path, Path, str]:
    requested = (model_name or "").strip()
    models = discover_models()
    auto_names = {"", "auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}

    selected: dict[str, object] | None = None
    if requested.lower() in auto_names:
        selected = models[0] if models else None
    else:
        requested_lower = requested.lower()
        for item in models:
            internal_name = str(item["name"])
            display_name = str(item.get("display_name") or internal_name)
            label = str(item.get("label") or "")
            if requested in {internal_name, display_name, label} or requested_lower in {
                internal_name.lower(),
                display_name.lower(),
                label.lower(),
            }:
                selected = item
                break
        if selected is None:
            internal_name = model_internal_name(requested)
            pth, index = find_model_files(internal_name)
            if pth and index:
                display_name = read_model_display_name(internal_name)
                return internal_name, pth, index, display_name

    if selected is None:
        raise FileNotFoundError("没有找到可清理的模型。请先选择一个已有模型，或训练完成后再清理。")

    internal_name = str(selected["name"])
    pth, index = find_model_files(internal_name)
    if not pth or not index:
        raise FileNotFoundError(f"模型不完整，无法清理：logs/{internal_name} 里没有同时找到 .pth 和 .index。")
    display_name = str(selected.get("display_name") or internal_name)
    return internal_name, pth, index, display_name


def is_model_training_active(model_name: str) -> bool:
    """Best-effort guard: avoid deleting cache while this model is still training."""
    if os.name != "nt" or not model_name:
        return False
    script = r"""
$name = $env:APPLIO_MODEL_NAME
Get-CimInstance Win32_Process |
  Where-Object {
    $_.CommandLine -and
    $_.CommandLine.Contains($name) -and
    ($_.CommandLine -match 'core\.py\s+train|rvc\\train\\train\.py')
  } |
  Select-Object -First 1 -ExpandProperty ProcessId
"""
    env = os.environ.copy()
    env["APPLIO_MODEL_NAME"] = model_name
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            env=env,
            text=True,
            encoding="utf-8",
            errors="ignore",
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except Exception:
        return False
    return bool(out)


def cleanup_model_training_cache(model_name: str, log=None) -> dict[str, object]:
    """Delete heavy RVC training cache while keeping the usable voice model files."""
    if log is None:
        log = lambda _message: None

    internal_name, pth, index, display_name = resolve_model_for_cleanup(model_name)
    model_dir = (LOG_DIR / internal_name).resolve()
    logs_root = LOG_DIR.resolve()
    if logs_root not in model_dir.parents and model_dir != logs_root:
        raise RuntimeError(f"拒绝清理非模型目录：{model_dir}")
    if is_model_training_active(internal_name):
        raise RuntimeError(f"模型仍在训练中，暂不能清理：{display_name} [{internal_name}]")

    keep_paths = {pth.resolve(), index.resolve()}
    for name in ("display_name.txt", "config.json", "model_info.json"):
        keep_file = model_dir / name
        if keep_file.exists():
            keep_paths.add(keep_file.resolve())

    deleted_files = 0
    deleted_dirs = 0
    reclaimed = 0

    for file_path in sorted(model_dir.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not file_path.is_file():
            continue
        resolved = file_path.resolve()
        if resolved in keep_paths:
            continue
        reclaimed += file_size(file_path)
        file_path.unlink()
        deleted_files += 1

    for dir_path in sorted(
        [p for p in model_dir.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            next(dir_path.iterdir())
        except StopIteration:
            dir_path.rmdir()
            deleted_dirs += 1
        except OSError:
            pass

    kept = "\n".join(f"  - {p}" for p in sorted(keep_paths, key=lambda item: str(item).lower()))
    log(f"清理完成：{display_name} [{internal_name}]")
    log(f"已释放约 {human_size(reclaimed)}，删除 {deleted_files} 个缓存文件、{deleted_dirs} 个空目录。")
    log("已保留声音模型文件：\n" + kept)
    return {
        "model_name": internal_name,
        "display_name": display_name,
        "reclaimed": reclaimed,
        "deleted_files": deleted_files,
        "deleted_dirs": deleted_dirs,
        "kept_pth": pth,
        "kept_index": index,
    }


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
        display_name = read_model_display_name(model_dir.name)
        if display_name != model_dir.name:
            title = f"{display_name}  [{model_dir.name}]"
        else:
            title = model_dir.name
        models.append(
            {
                "name": model_dir.name,
                "display_name": display_name,
                "pth": pth,
                "index": index,
                "updated": updated,
                "label": f"{title}  ({datetime.fromtimestamp(updated).strftime('%m-%d %H:%M')})",
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
    models = discover_models()
    if requested and requested.lower() not in {"auto", "自动", AUTO_MODEL_LABEL.lower()}:
        requested_lower = requested.lower()
        for item in models:
            internal_name = str(item["name"])
            display_name = str(item.get("display_name") or internal_name)
            label = str(item.get("label") or "")
            if requested in {internal_name, display_name, label} or requested_lower in {
                internal_name.lower(),
                display_name.lower(),
                label.lower(),
            }:
                pth, index = build_index_if_possible(internal_name, log)
                if pth and index:
                    if display_name != internal_name:
                        log(f"使用已识别模型：{display_name} [{internal_name}]")
                    else:
                        log(f"使用已识别模型：{internal_name}")
                    return internal_name, pth, index

        resolved_name = model_internal_name(requested)
        pth, index = build_index_if_possible(resolved_name, log)
        if pth and index:
            display_name = read_model_display_name(resolved_name)
            if display_name != resolved_name:
                log(f"使用已识别模型：{display_name} [{resolved_name}]")
            else:
                log(f"使用已识别模型：{resolved_name}")
            return resolved_name, pth, index

    if not models:
        return None

    selected = models[0]
    resolved_name = str(selected["name"])
    display_name = str(selected.get("display_name") or resolved_name)
    if display_name != resolved_name:
        log(f"自动选择最新模型：{display_name} [{resolved_name}]")
    else:
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

    tmp_audio: Path | None = None
    try:
        y, sr = librosa.load(str(audio_path), sr=16000, mono=True, duration=180)
    except Exception:
        # Some Windows audio backends still stumble on Chinese/non-ASCII paths.
        # Copying to an ASCII temp path keeps auto pitch from aborting the whole cover.
        tmp_dir = DEFAULT_OUTPUT_DIR / "_tmp_pitch"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        suffix = audio_path.suffix if audio_path.suffix else ".wav"
        tmp_audio = tmp_dir / f"pitch_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{suffix}"
        shutil.copy2(audio_path, tmp_audio)
        try:
            y, sr = librosa.load(str(tmp_audio), sr=16000, mono=True, duration=180)
        finally:
            try:
                tmp_audio.unlink()
            except OSError:
                pass
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
    if not target_f0:
        log("自动变调：模型音高缓存不足，沿用手动变调。")
        return None
    try:
        source_f0 = median_audio_f0(vocals_path)
    except Exception as exc:
        log(f"自动变调：歌曲人声音高分析失败，沿用手动变调。原因：{exc}")
        return None
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
    progress_hook=None,
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
    requested_display_name = (model_name or "").strip()
    if not requested_display_name or requested_display_name.lower() in auto_names:
        requested_display_name = new_model_default_name()
    internal_model_name = model_internal_name(requested_display_name)

    if force_train:
        for item in discover_models():
            existing_internal = str(item["name"])
            existing_display = str(item.get("display_name") or existing_internal)
            if existing_display == requested_display_name and existing_internal != internal_model_name:
                raise FileExistsError(
                    f"模型显示名 '{requested_display_name}' 已经存在，对应内部ID：{existing_internal}\n"
                    "为了避免误用旧模型，请换一个新的中文显示名。"
                )

    model_name = internal_model_name
    model_dir = LOG_DIR / model_name
    if force_train and model_dir.exists():
        existing_artifacts = list(model_dir.glob("*.pth")) + list(model_dir.glob("*.index"))
        if existing_artifacts:
            raise FileExistsError(
                f"新模型内部ID '{model_name}' 已经存在：{model_dir}\n"
                "为了避免误用旧 checkpoint 导致训练一秒结束，请换一个新的模型显示名，"
                "例如“阿明男声2”，或先手动备份/删除这个旧模型目录。"
            )
    cpu_cores = max(1, min(8, os.cpu_count() or 4))
    save_every = max(1, min(epochs, 10))
    if requested_display_name != model_name:
        log(f"没有现成模型，开始训练“{requested_display_name}”（内部ID：{model_name}），素材数量：{len(audio_files)}。")
    else:
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
    train_started_at = datetime.now().timestamp()
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
    run_training_command(
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
        model_name=model_name,
        total_epochs=epochs,
        batch_size=batch_size,
        log=log,
        progress_hook=progress_hook,
    )

    pth, index = build_index_if_possible(model_name, log)
    if not pth or pth.stat().st_mtime < train_started_at:
        raise FileNotFoundError(
            f"训练命令结束了，但没有生成新的 .pth 权重：logs/{model_name}\n"
            "这通常是同名旧模型/旧 checkpoint 被复用，或训练进程提前退出。"
            "请换一个全新的模型名重新训练，并查看窗口日志里的 train 报错。"
        )
    if not index or index.stat().st_mtime < train_started_at:
        raise FileNotFoundError(
            f"训练后没有生成新的 .index 索引：logs/{model_name}\n"
            "请确认特征提取成功，或重新点击训练。"
        )
    write_model_display_name(model_name, requested_display_name)
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


def extract_audio_segment(
    input_path: Path,
    output_path: Path,
    start_seconds: float,
    duration_seconds: float,
    log,
) -> Path:
    if not FFMPEG.exists():
        raise FileNotFoundError(f"ffmpeg.exe not found at {FFMPEG}")
    start_seconds = max(0.0, float(start_seconds))
    duration_seconds = max(3.0, min(120.0, float(duration_seconds)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".wav":
        codec_args = ["-ac", "2", "-ar", "44100", "-c:a", "pcm_s16le"]
    else:
        codec_args = ["-ac", "2", "-ar", "44100", "-c:a", "libmp3lame", "-b:a", "320k"]
    log(f"截取预览片段：从 {start_seconds:.1f}s 开始，时长 {duration_seconds:.1f}s")
    run_command(
        [
            str(FFMPEG),
            "-y",
            "-ss",
            f"{start_seconds:.3f}",
            "-t",
            f"{duration_seconds:.3f}",
            "-i",
            str(input_path),
            "-vn",
            *codec_args,
            str(output_path),
        ],
        log,
    )
    return output_path


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
    progress_hook=None,
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
            model_name = new_model_default_name()
        model_name, pth, index = prepare_model(
            model_name,
            voice_dir,
            sample_rate,
            epochs,
            batch_size,
            gpu,
            log,
            force_train=force_train,
            progress_hook=progress_hook,
        )

    vocals, instrumental = separate_song(song_path, work_dir, log)
    if auto_pitch:
        estimated_pitch = estimate_pitch_shift(model_name, vocals, log)
        if estimated_pitch is not None:
            pitch = estimated_pitch

    song_stem = safe_filename(song_path.stem)
    display_model_name = read_model_display_name(model_name)
    model_stem = safe_filename(display_model_name, "model")
    if display_model_name != model_name:
        log(f"模型显示名：{display_model_name}（内部ID：{model_name}）")
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


def create_voice_preview(
    song_path: Path,
    model_name: str,
    pth_path: Path | None,
    index_path: Path | None,
    output_dir: Path,
    pitch: int,
    index_rate: float,
    gpu: str,
    log,
    auto_pitch: bool = True,
    clarity_mode: bool = True,
    protect: float = 0.50,
    auto_mix: bool = True,
    vocal_gain: float = 1.0,
    instrumental_gain: float = 1.0,
    start_seconds: float = 30.0,
    duration_seconds: float = 20.0,
) -> dict[str, Path]:
    """Create short A/B previews: original source segment and converted cover segment."""
    if not song_path.exists():
        raise FileNotFoundError(f"Song file not found: {song_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_root = output_dir / "previews"
    preview_root.mkdir(parents=True, exist_ok=True)

    requested_model_name = (model_name or "").strip() or "auto"
    if pth_path and index_path:
        pth, index = pth_path, index_path
        resolved_model_name = safe_filename(pth.stem, "manual_model")
        display_model_name = resolved_model_name
        log(f"预览使用手动模型：{pth}")
        log(f"预览使用手动索引：{index}")
    else:
        existing = resolve_existing_model(requested_model_name, log)
        if not existing:
            raise FileNotFoundError("没有找到可预览的已训练模型。请先训练完成，或手动选择 .pth 和 .index。")
        resolved_model_name, pth, index = existing
        display_model_name = read_model_display_name(resolved_model_name)

    song_stem = safe_filename(song_path.stem)
    model_stem = safe_filename(display_model_name, "model")
    work_dir = preview_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{song_stem}_{model_stem}_preview"
    work_dir.mkdir(parents=True, exist_ok=True)

    original_mix = work_dir / f"{song_stem}_00_original_mix_preview.mp3"
    extract_audio_segment(song_path, original_mix, start_seconds, duration_seconds, log)

    vocals, instrumental = separate_song(original_mix, work_dir, log)
    original_vocals = work_dir / f"{song_stem}_01_original_vocals_preview.wav"
    original_instrumental = work_dir / f"{song_stem}_02_instrumental_preview.wav"
    shutil.copy2(vocals, original_vocals)
    shutil.copy2(instrumental, original_instrumental)

    if auto_pitch:
        estimated_pitch = estimate_pitch_shift(resolved_model_name, original_vocals, log)
        if estimated_pitch is not None:
            pitch = estimated_pitch

    effective_index_rate = max(0.0, min(1.0, float(index_rate)))
    effective_protect = max(0.0, min(0.75, float(protect)))
    if clarity_mode:
        effective_index_rate = min(effective_index_rate, 0.45)
        effective_protect = max(effective_protect, 0.50)
        log(
            "预览咬字清晰模式已开启："
            f"索引强度 {effective_index_rate:.2f}，辅音保护 {effective_protect:.2f}"
        )
    else:
        log("预览咬字清晰模式已关闭。")

    converted_vocals = work_dir / f"{song_stem}_{model_stem}_03_cover_vocals_preview.wav"
    infer_vocals(
        original_vocals,
        pth,
        index,
        converted_vocals,
        pitch,
        effective_index_rate,
        effective_protect,
        log,
    )

    cover_mix = work_dir / f"{song_stem}_{model_stem}_04_cover_mix_preview.mp3"
    mix_cover(
        converted_vocals,
        original_instrumental,
        cover_mix,
        log,
        vocal_gain=vocal_gain,
        instrumental_gain=instrumental_gain,
        reference_vocal_path=original_vocals,
        auto_mix=auto_mix,
    )

    latest_original = preview_root / f"{song_stem}_original_preview.mp3"
    latest_cover = preview_root / f"{song_stem}_{model_stem}_cover_preview.mp3"
    shutil.copy2(original_mix, latest_original)
    shutil.copy2(cover_mix, latest_cover)

    log(f"原唱预览：{latest_original}")
    log(f"翻唱预览：{latest_cover}")
    log(f"原唱人声预览：{original_vocals}")
    log(f"翻唱人声预览：{converted_vocals}")
    log(f"预览中间文件目录：{work_dir}")
    return {
        "original_mix": latest_original,
        "cover_mix": latest_cover,
        "original_vocals": original_vocals,
        "cover_vocals": converted_vocals,
        "work_dir": work_dir,
    }


def unique_int_candidates(values: list[int], min_value: int = -24, max_value: int = 24, limit: int = 3) -> list[int]:
    result: list[int] = []
    for value in values:
        item = max(min_value, min(max_value, int(round(value))))
        if item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def unique_float_candidates(values: list[float], min_value: float, max_value: float, limit: int) -> list[float]:
    result: list[float] = []
    for value in values:
        item = round(max(min_value, min(max_value, float(value))), 2)
        if item not in result:
            result.append(item)
        if len(result) >= limit:
            break
    return result


def pitch_matrix_candidates(base_pitch: int, estimated_pitch: int | None) -> list[int]:
    if estimated_pitch is not None:
        return unique_int_candidates([estimated_pitch, estimated_pitch - 3, estimated_pitch + 3, 0], -12, 12, 3)
    if int(base_pitch) == 0:
        return [0, -5, -12]
    return unique_int_candidates([base_pitch, base_pitch - 3, base_pitch + 3, 0], -12, 12, 3)


def index_matrix_candidates(base_index: float) -> list[float]:
    return unique_float_candidates([base_index, 0.35, 0.50, 0.65], 0.0, 1.0, 3)


def protect_matrix_candidates(base_protect: float) -> list[float]:
    return unique_float_candidates([base_protect, 0.60, 0.45, 0.70], 0.0, 0.75, 2)


def parameter_slug(pitch: int, index_rate: float, protect: float) -> str:
    pitch_part = f"p{'p' if pitch >= 0 else 'm'}{abs(int(pitch)):02d}"
    index_part = f"i{int(round(index_rate * 100)):03d}"
    protect_part = f"pr{int(round(protect * 100)):03d}"
    return f"{pitch_part}_{index_part}_{protect_part}"


def create_parameter_preview_matrix(
    song_path: Path,
    model_name: str,
    pth_path: Path | None,
    index_path: Path | None,
    output_dir: Path,
    pitch: int,
    index_rate: float,
    protect: float,
    log,
    auto_pitch: bool = True,
    auto_mix: bool = True,
    vocal_gain: float = 1.0,
    instrumental_gain: float = 1.0,
    start_seconds: float = 30.0,
    duration_seconds: float = 15.0,
) -> dict[str, object]:
    """Generate a batch of short A/B cover previews with different inference parameters."""
    if not song_path.exists():
        raise FileNotFoundError(f"Song file not found: {song_path}")
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_root = output_dir / "previews"
    preview_root.mkdir(parents=True, exist_ok=True)

    requested_model_name = (model_name or "").strip() or "auto"
    if pth_path and index_path:
        pth, index = pth_path, index_path
        resolved_model_name = safe_filename(pth.stem, "manual_model")
        display_model_name = resolved_model_name
        log(f"矩阵试听使用手动模型：{pth}")
        log(f"矩阵试听使用手动索引：{index}")
    else:
        existing = resolve_existing_model(requested_model_name, log)
        if not existing:
            raise FileNotFoundError("没有找到可试听的已训练模型。请先训练完成，或手动选择 .pth 和 .index。")
        resolved_model_name, pth, index = existing
        display_model_name = read_model_display_name(resolved_model_name)

    song_stem = safe_filename(song_path.stem)
    model_stem = safe_filename(display_model_name, "model")
    matrix_duration = max(3.0, min(15.0, float(duration_seconds)))
    if matrix_duration < float(duration_seconds):
        log(f"矩阵试听为节省时间，单段时长限制为 {matrix_duration:.1f}s。")

    work_dir = preview_root / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}_{song_stem}_{model_stem}_matrix"
    work_dir.mkdir(parents=True, exist_ok=True)

    original_mix = work_dir / f"{song_stem}_00_original_mix_matrix.mp3"
    extract_audio_segment(song_path, original_mix, start_seconds, matrix_duration, log)
    vocals, instrumental = separate_song(original_mix, work_dir, log)
    original_vocals = work_dir / f"{song_stem}_01_original_vocals_matrix.wav"
    original_instrumental = work_dir / f"{song_stem}_02_instrumental_matrix.wav"
    shutil.copy2(vocals, original_vocals)
    shutil.copy2(instrumental, original_instrumental)

    estimated_pitch: int | None = None
    if auto_pitch:
        estimated_pitch = estimate_pitch_shift(resolved_model_name, original_vocals, log)
        if estimated_pitch is not None:
            log(f"矩阵试听：自动估算中心变调为 {estimated_pitch:+d}。")

    pitch_values = pitch_matrix_candidates(int(pitch), estimated_pitch)
    index_values = index_matrix_candidates(float(index_rate))
    protect_values = protect_matrix_candidates(float(protect))
    combinations = [
        (p, idx, pr)
        for p in pitch_values
        for idx in index_values
        for pr in protect_values
    ]
    log(
        "开始参数试听矩阵："
        f"变调 {pitch_values} × 索引 {index_values} × 辅音保护 {protect_values}，"
        f"共 {len(combinations)} 组。"
    )

    cover_files: list[Path] = []
    summary_lines = [
        "大尸兄一键翻唱 - 自动参数试听矩阵",
        f"歌曲：{song_path}",
        f"模型：{display_model_name} [{resolved_model_name}]",
        f"预览起点：{float(start_seconds):.1f}s",
        f"预览时长：{matrix_duration:.1f}s",
        "",
        "建议听法：先听混音 mp3；咬字糊就选 protect 高一点；不像本人就选 index 高一点；音高怪就换 pitch。",
        "",
        "文件\tpitch\tindex_rate\tprotect",
    ]

    total = len(combinations)
    for number, (candidate_pitch, candidate_index, candidate_protect) in enumerate(combinations, start=1):
        slug = parameter_slug(candidate_pitch, candidate_index, candidate_protect)
        prefix = f"{number:02d}_{slug}"
        log(
            f"[{number}/{total}] 生成矩阵试听："
            f"pitch {candidate_pitch:+d}, index {candidate_index:.2f}, protect {candidate_protect:.2f}"
        )
        converted_vocals = work_dir / f"{prefix}_cover_vocals.wav"
        infer_vocals(
            original_vocals,
            pth,
            index,
            converted_vocals,
            candidate_pitch,
            candidate_index,
            candidate_protect,
            log,
        )
        cover_mix = work_dir / f"{prefix}_cover_mix.mp3"
        mix_cover(
            converted_vocals,
            original_instrumental,
            cover_mix,
            log,
            vocal_gain=vocal_gain,
            instrumental_gain=instrumental_gain,
            reference_vocal_path=original_vocals,
            auto_mix=auto_mix,
        )
        cover_files.append(cover_mix)
        summary_lines.append(
            f"{cover_mix.name}\t{candidate_pitch:+d}\t{candidate_index:.2f}\t{candidate_protect:.2f}"
        )

    latest_original = preview_root / f"{song_stem}_matrix_original_preview.mp3"
    shutil.copy2(original_mix, latest_original)
    summary_path = work_dir / "参数试听矩阵说明.txt"
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    log(f"矩阵原唱预览：{latest_original}")
    log(f"矩阵试听目录：{work_dir}")
    log(f"矩阵说明文件：{summary_path}")
    if cover_files:
        log(f"第一条矩阵试听：{cover_files[0]}")
    return {
        "original_mix": latest_original,
        "matrix_dir": work_dir,
        "summary": summary_path,
        "cover_files": cover_files,
        "first_cover": cover_files[0] if cover_files else None,
    }


class CoverApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("大尸兄一键翻唱")
        self.root.geometry("920x680")
        self.root.minsize(860, 620)
        self.queue: queue.Queue[object] = queue.Queue()
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
        self.root.geometry("1020x780")
        self.root.minsize(940, 700)
        self.queue: queue.Queue[object] = queue.Queue()
        self.running = False
        self.update_running = False
        self.latest_update_info: dict[str, object] | None = None
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
        self.cleanup_after_train = tk.BooleanVar(value=True)
        self.preview_start = tk.DoubleVar(value=30.0)
        self.preview_duration = tk.DoubleVar(value=20.0)
        self.last_original_preview = tk.StringVar()
        self.last_cover_preview = tk.StringVar()
        self.last_matrix_dir = tk.StringVar()
        self.status = tk.StringVar(value="就绪")
        self.training_progress_text = tk.StringVar(value="训练进度：未开始")
        self.training_progress_value = tk.DoubleVar(value=0.0)

        self.build_ui()
        self.refresh_models(write_log=False)
        self.root.after(200, self.poll)
        self.root.after(1500, lambda: self.check_for_updates(auto=True))

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
        self.entry_row(model_box, "新模型显示名", self.model_name)
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

        preview_box = ttk.LabelFrame(self.root, text="4. 声音预览")
        preview_box.pack(fill="x", **pad)
        preview_grid = ttk.Frame(preview_box)
        preview_grid.pack(fill="x", padx=8, pady=8)
        self.labeled_entry(preview_grid, "预览起点秒", self.preview_start, 0, 0)
        self.labeled_entry(preview_grid, "预览时长秒", self.preview_duration, 0, 2)
        ttk.Button(preview_grid, text="生成原唱/翻唱预览", command=self.start_preview).grid(row=0, column=4, sticky="ew", padx=6, pady=4)
        ttk.Button(preview_grid, text="播放原唱预览", command=self.play_original_preview).grid(row=1, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(preview_grid, text="播放翻唱预览", command=self.play_cover_preview).grid(row=1, column=2, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(preview_grid, text="打开预览目录", command=self.open_preview_dir).grid(row=1, column=4, sticky="ew", padx=6, pady=4)
        ttk.Button(preview_grid, text="自动参数试听矩阵", command=self.start_parameter_matrix).grid(row=2, column=0, columnspan=2, sticky="ew", padx=6, pady=4)
        ttk.Button(preview_grid, text="打开矩阵目录", command=self.open_matrix_dir).grid(row=2, column=2, columnspan=2, sticky="ew", padx=6, pady=4)
        for col in (1, 3, 4):
            preview_grid.columnconfigure(col, weight=1)

        actions = ttk.Frame(self.root)
        actions.pack(fill="x", **pad)
        ttk.Button(actions, text="安装/检查依赖", command=self.install_deps).pack(side="left", padx=6)
        ttk.Button(actions, text="一键生成混音翻唱", command=self.start_cover).pack(side="left", padx=6)
        ttk.Button(actions, text="一键清理训练缓存", command=self.cleanup_selected_model).pack(side="left", padx=6)
        ttk.Button(actions, text="打开输出目录", command=self.open_output).pack(side="left", padx=6)
        ttk.Button(actions, text="检查更新", command=lambda: self.check_for_updates(auto=False)).pack(side="left", padx=6)
        ttk.Button(actions, text="一键更新", command=self.start_update).pack(side="left", padx=6)
        ttk.Checkbutton(actions, text="训练后自动清理缓存", variable=self.cleanup_after_train).pack(side="left", padx=16)
        ttk.Checkbutton(actions, text="完成后打开输出目录", variable=self.open_when_done).pack(side="left", padx=6)

        status_bar = ttk.Frame(self.root)
        status_bar.pack(fill="x", padx=10, pady=(0, 6))
        ttk.Label(status_bar, textvariable=self.status, foreground="#555").pack(anchor="w")
        ttk.Label(status_bar, textvariable=self.training_progress_text, foreground="#555").pack(anchor="w", pady=(2, 0))
        ttk.Progressbar(
            status_bar,
            variable=self.training_progress_value,
            maximum=100.0,
            mode="determinate",
        ).pack(fill="x", pady=(2, 0))

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
        ttk.Label(frame, text="可填中文；内部自动生成安全ID", foreground="#666").pack(side="left", padx=(8, 0))

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
                latest_display = str(latest.get("display_name") or latest["name"])
                if latest_display != str(latest["name"]):
                    self.status.set(f"自动模式将使用：{latest_display} [{latest['name']}]")
                else:
                    self.status.set(f"自动模式将使用：{latest['name']}")
            else:
                self.pth.set("")
                self.index.set("")
                self.status.set("未发现现成模型；可选择训练素材文件夹")
            return
        if choice == TRAIN_MODEL_LABEL:
            current_name = self.model_name.get().strip()
            current_internal = model_internal_name(current_name) if current_name else ""
            if (
                current_name.lower() in {"", "auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}
                or (current_internal and (LOG_DIR / current_internal).exists())
            ):
                self.model_name.set(new_model_default_name())
            self.pth.set("")
            self.index.set("")
            self.status.set("训练新模型：显示名可填中文，请选择新声音素材文件夹")
            if write_log:
                self.write("已切换到训练新模型模式。显示名可填中文，程序会自动使用英文安全ID，避免覆盖/续训旧模型。")
            return
        if choice == MANUAL_MODEL_LABEL:
            self.status.set("手动模型模式")
            return
        item = self.model_lookup.get(choice)
        if item:
            self.model_name.set(str(item["name"]))
            self.pth.set(str(item["pth"]))
            self.index.set(str(item["index"]))
            display_name = str(item.get("display_name") or item["name"])
            if display_name != str(item["name"]):
                self.status.set(f"已选择模型：{display_name} [{item['name']}]")
            else:
                self.status.set(f"已选择模型：{item['name']}")
            if write_log:
                if display_name != str(item["name"]):
                    self.write(f"已选择模型：{display_name} [{item['name']}]")
                else:
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

    def open_preview_dir(self):
        path = Path(self.output_dir.get()) / "previews"
        path.mkdir(parents=True, exist_ok=True)
        os.startfile(str(path))

    def open_matrix_dir(self):
        path_text = self.last_matrix_dir.get().strip()
        if path_text and Path(path_text).exists():
            os.startfile(path_text)
            return
        self.open_preview_dir()

    def play_preview_path(self, path_text: str, title: str):
        path_text = (path_text or "").strip()
        if not path_text:
            messagebox.showinfo("暂无预览", f"还没有{title}。请先点击“生成原唱/翻唱预览”。")
            return
        path = Path(path_text)
        if not path.exists():
            messagebox.showerror("预览文件不存在", f"找不到{title}文件：\n{path}")
            return
        os.startfile(str(path))

    def play_original_preview(self):
        self.play_preview_path(self.last_original_preview.get(), "原唱预览")

    def play_cover_preview(self):
        self.play_preview_path(self.last_cover_preview.get(), "翻唱预览")

    def selected_model_name_for_preview(self) -> str:
        choice = self.model_choice.get()
        item = self.model_lookup.get(choice)
        if item:
            return str(item["name"])
        if choice == AUTO_MODEL_LABEL:
            return "auto"
        return self.model_name.get().strip() or "auto"

    def start_preview(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行，请等当前任务结束后再生成预览。")
            return
        if not self.song.get():
            messagebox.showerror("缺少歌曲", "请先选择歌曲文件。")
            return

        choice = self.model_choice.get()
        manual_mode = choice == MANUAL_MODEL_LABEL
        if manual_mode and (not self.pth.get() or not self.index.get()):
            messagebox.showerror("模型不完整", "手动模型模式需要同时选择 .pth 和 .index。")
            return
        if choice == TRAIN_MODEL_LABEL:
            messagebox.showinfo("需要已有模型", "声音预览需要已训练完成的模型。请训练完成后刷新模型列表，再选择该模型预览。")
            return

        self.running = True
        self.status.set("正在生成声音预览…")
        self.write("开始生成声音预览：会输出原唱预览和翻唱后预览。")

        def task():
            try:
                pth_path = Path(self.pth.get()) if manual_mode else None
                index_path = Path(self.index.get()) if manual_mode else None
                result = create_voice_preview(
                    song_path=Path(self.song.get()),
                    model_name=self.selected_model_name_for_preview(),
                    pth_path=pth_path,
                    index_path=index_path,
                    output_dir=Path(self.output_dir.get()),
                    pitch=int(self.pitch.get()),
                    index_rate=float(self.index_rate.get()),
                    gpu=self.gpu.get().strip() or "0",
                    log=self.log_threadsafe,
                    auto_pitch=bool(self.auto_pitch.get()),
                    clarity_mode=bool(self.clarity_mode.get()),
                    protect=float(self.protect.get()),
                    auto_mix=bool(self.auto_mix.get()),
                    vocal_gain=float(self.vocal_gain.get()),
                    instrumental_gain=float(self.instrumental_gain.get()),
                    start_seconds=float(self.preview_start.get()),
                    duration_seconds=float(self.preview_duration.get()),
                )
                self.queue.put(f"__ORIGINAL_PREVIEW__:{result['original_mix']}")
                self.queue.put(f"__COVER_PREVIEW__:{result['cover_mix']}")
                self.status_threadsafe("声音预览完成")
                if self.open_when_done.get():
                    os.startfile(str(Path(result["work_dir"])))
            except Exception as exc:
                self.log_threadsafe(f"预览失败：{exc}")
                self.status_threadsafe("预览失败")
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def start_parameter_matrix(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行，请等当前任务结束后再生成参数矩阵。")
            return
        if not self.song.get():
            messagebox.showerror("缺少歌曲", "请先选择歌曲文件。")
            return

        choice = self.model_choice.get()
        manual_mode = choice == MANUAL_MODEL_LABEL
        if manual_mode and (not self.pth.get() or not self.index.get()):
            messagebox.showerror("模型不完整", "手动模型模式需要同时选择 .pth 和 .index。")
            return
        if choice == TRAIN_MODEL_LABEL:
            messagebox.showinfo("需要已有模型", "参数矩阵需要已训练完成的模型。请训练完成后刷新模型列表，再选择该模型。")
            return

        ok = messagebox.askyesno(
            "确认生成参数试听矩阵",
            "将生成最多 18 个短试听文件：\n"
            "- 3 个变调\n"
            "- 3 个索引强度\n"
            "- 2 个辅音保护\n\n"
            "只会截取短片段，且只分离一次，但仍可能需要几分钟。继续吗？",
        )
        if not ok:
            return

        self.running = True
        self.status.set("正在生成参数试听矩阵…")
        self.write("开始生成自动参数试听矩阵：完成后请打开矩阵目录逐个试听。")

        def task():
            try:
                pth_path = Path(self.pth.get()) if manual_mode else None
                index_path = Path(self.index.get()) if manual_mode else None
                result = create_parameter_preview_matrix(
                    song_path=Path(self.song.get()),
                    model_name=self.selected_model_name_for_preview(),
                    pth_path=pth_path,
                    index_path=index_path,
                    output_dir=Path(self.output_dir.get()),
                    pitch=int(self.pitch.get()),
                    index_rate=float(self.index_rate.get()),
                    protect=float(self.protect.get()),
                    log=self.log_threadsafe,
                    auto_pitch=bool(self.auto_pitch.get()),
                    auto_mix=bool(self.auto_mix.get()),
                    vocal_gain=float(self.vocal_gain.get()),
                    instrumental_gain=float(self.instrumental_gain.get()),
                    start_seconds=float(self.preview_start.get()),
                    duration_seconds=float(self.preview_duration.get()),
                )
                self.queue.put(f"__ORIGINAL_PREVIEW__:{result['original_mix']}")
                if result.get("first_cover"):
                    self.queue.put(f"__COVER_PREVIEW__:{result['first_cover']}")
                self.queue.put(f"__MATRIX_DIR__:{result['matrix_dir']}")
                self.status_threadsafe("参数试听矩阵完成")
                if self.open_when_done.get():
                    os.startfile(str(Path(result["matrix_dir"])))
            except Exception as exc:
                self.log_threadsafe(f"参数矩阵失败：{exc}")
                self.status_threadsafe("参数矩阵失败")
            finally:
                self.running = False

        threading.Thread(target=task, daemon=True).start()

    def cleanup_target_model_name(self) -> str:
        choice = self.model_choice.get()
        item = self.model_lookup.get(choice)
        if item:
            return str(item["name"])
        if choice == AUTO_MODEL_LABEL and self.model_lookup:
            return str(next(iter(self.model_lookup.values()))["name"])
        if choice == MANUAL_MODEL_LABEL and self.pth.get():
            try:
                relative = Path(self.pth.get()).resolve().relative_to(LOG_DIR.resolve())
                if relative.parts:
                    return relative.parts[0]
            except ValueError:
                pass
        return self.model_name.get().strip() or "auto"

    def cleanup_selected_model(self):
        if self.running:
            messagebox.showinfo("提示", "已有任务正在运行，请等训练/生成结束后再清理。")
            return
        target = self.cleanup_target_model_name()
        try:
            internal_name, pth, index, display_name = resolve_model_for_cleanup(target)
        except Exception as exc:
            messagebox.showerror("无法清理", str(exc))
            return
        if is_model_training_active(internal_name):
            messagebox.showwarning("训练仍在进行", f"模型仍在训练中，暂不能清理：{display_name} [{internal_name}]")
            return

        ok = messagebox.askyesno(
            "确认清理训练缓存",
            f"将清理模型：{display_name} [{internal_name}]\n\n"
            "会保留：\n"
            f"- 最新声音权重：{pth.name}\n"
            f"- 最新索引文件：{index.name}\n"
            "- 中文显示名/少量配置文件\n\n"
            "会删除：\n"
            "- sliced_audios / extracted / f0 / eval 等训练缓存\n"
            "- G_*.pth / D_*.pth 续训 checkpoint\n"
            "- 旧 epoch 权重和其它训练过程文件\n\n"
            "删除后不可恢复，但不影响正常翻唱。确定继续吗？",
        )
        if not ok:
            return

        self.running = True
        self.status.set("正在清理训练缓存…")

        def task():
            try:
                result = cleanup_model_training_cache(internal_name, self.log_threadsafe)
                self.status_threadsafe(f"清理完成，释放约 {human_size(int(result['reclaimed']))}")
            except Exception as exc:
                self.log_threadsafe(f"清理失败：{exc}")
                self.status_threadsafe("清理失败")
            finally:
                self.running = False
                self.queue.put("__REFRESH_MODELS__")

        threading.Thread(target=task, daemon=True).start()

    def write(self, message: str):
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def log_threadsafe(self, message: str):
        self.queue.put(message)

    def status_threadsafe(self, message: str):
        self.queue.put(f"__STATUS__:{message}")

    def update_progress_threadsafe(self, percent: float):
        self.queue.put(("__UPDATE_PROGRESS__", float(percent)))

    def check_for_updates(self, auto: bool = False):
        if self.update_running:
            return

        def task():
            try:
                info = check_update_available()
                self.queue.put(("__UPDATE_INFO__", info, auto))
            except Exception as exc:
                if not auto:
                    self.queue.put(("__UPDATE_ERROR__", str(exc), auto))

        if not auto:
            self.write("正在检查 GitHub 最新版本…")
            self.status.set("正在检查更新…")
        threading.Thread(target=task, daemon=True).start()

    def handle_update_info(self, info: dict[str, object], auto: bool = False):
        self.latest_update_info = info
        current = str(info.get("current_version") or APP_VERSION)
        version = str(info.get("version") or info.get("tag") or "未知")
        if bool(info.get("is_newer")):
            zip_url = str(info.get("zip_url") or "")
            self.write(f"发现新版本：v{version}（当前 v{current}）")
            if not zip_url:
                self.write(f"新版本没有可自动下载的 zip，请手动打开：{info.get('html_url')}")
                if not auto:
                    messagebox.showwarning("发现新版本", f"发现 v{version}，但没有找到 zip 包，请手动打开 Release 页面。")
                return
            if auto:
                if messagebox.askyesno(
                    "发现新版本",
                    f"发现新版本 v{version}，当前版本 v{current}。\n\n"
                    "是否现在一键更新？\n\n"
                    "会保留 env、logs、outputs、updates 等本地数据。",
                ):
                    self.start_update()
            else:
                messagebox.showinfo("发现新版本", f"发现新版本 v{version}。\n点击“一键更新”即可自动下载并覆盖程序文件。")
            self.status.set(f"发现新版本 v{version}")
        else:
            self.status.set(f"已是最新版本 v{current}")
            if not auto:
                self.write(f"已是最新版本：v{current}")
                messagebox.showinfo("已是最新", f"当前已是最新版本：v{current}")

    def start_update(self):
        if self.running:
            messagebox.showinfo("提示", "当前正在训练/生成/预览，请等任务结束后再更新。")
            return
        if self.update_running:
            messagebox.showinfo("提示", "更新任务正在运行。")
            return
        info = self.latest_update_info
        if not info or not bool(info.get("is_newer")):
            self.write("还没有可用的新版本信息，先检查更新。")
            self.check_for_updates(auto=False)
            return
        version = str(info.get("version") or info.get("tag") or "未知")
        if not messagebox.askyesno(
            "确认一键更新",
            f"准备更新到 v{version}。\n\n"
            "会覆盖程序文件，但保留：\n"
            "- env 环境\n"
            "- logs 模型/训练记录\n"
            "- outputs 输出成品\n"
            "- updates 下载包\n"
            "- ffmpeg/ffprobe\n\n"
            "更新完成后请关闭并重新打开窗口。继续吗？",
        ):
            return

        self.update_running = True
        self.status.set(f"正在更新到 v{version}…")
        self.training_progress_text.set("更新进度：开始下载…")
        self.training_progress_value.set(0.0)

        def task():
            try:
                result = download_and_apply_update(
                    info,
                    self.log_threadsafe,
                    progress_hook=self.update_progress_threadsafe,
                )
                self.queue.put(("__UPDATE_DONE__", result, version))
            except Exception as exc:
                self.queue.put(("__UPDATE_ERROR__", str(exc), False))
            finally:
                self.update_running = False

        threading.Thread(target=task, daemon=True).start()

    def training_progress_threadsafe(self, snapshot: dict[str, object]):
        self.queue.put(("__TRAIN_PROGRESS__", snapshot))

    def apply_training_progress(self, snapshot: dict[str, object] | None):
        message = format_training_progress(snapshot)
        self.training_progress_text.set(message)
        if snapshot:
            percent = max(0.0, min(100.0, float(snapshot.get("progress_percent", 0.0))))
            self.training_progress_value.set(percent)
            self.status.set(message)

    def poll(self):
        try:
            while True:
                message = self.queue.get_nowait()
                if isinstance(message, tuple) and len(message) == 2 and message[0] == "__TRAIN_PROGRESS__":
                    snapshot = message[1] if isinstance(message[1], dict) else None
                    self.apply_training_progress(snapshot)
                    continue
                if isinstance(message, tuple) and len(message) >= 2 and message[0] == "__UPDATE_INFO__":
                    info = message[1] if isinstance(message[1], dict) else {}
                    auto = bool(message[2]) if len(message) >= 3 else False
                    self.handle_update_info(info, auto=auto)
                    continue
                if isinstance(message, tuple) and len(message) >= 2 and message[0] == "__UPDATE_PROGRESS__":
                    percent = max(0.0, min(100.0, float(message[1])))
                    self.training_progress_value.set(percent)
                    self.training_progress_text.set(f"更新进度：下载 {percent:.1f}%")
                    self.status.set(f"正在下载更新… {percent:.1f}%")
                    continue
                if isinstance(message, tuple) and len(message) >= 3 and message[0] == "__UPDATE_DONE__":
                    result = message[1] if isinstance(message[1], dict) else {}
                    version = str(message[2])
                    self.training_progress_value.set(100.0)
                    self.training_progress_text.set(f"更新完成：v{version}")
                    self.status.set("更新完成，请重启窗口")
                    self.write(
                        "更新完成："
                        f"复制 {result.get('copied_files', 0)} 个文件，"
                        f"跳过 {result.get('skipped_files', 0)} 个本地文件。"
                    )
                    messagebox.showinfo("更新完成", f"已更新到 v{version}。\n请关闭并重新打开“大尸兄一键翻唱”。")
                    continue
                if isinstance(message, tuple) and len(message) >= 2 and message[0] == "__UPDATE_ERROR__":
                    self.status.set("更新/检查失败")
                    self.write(f"更新/检查失败：{message[1]}")
                    messagebox.showerror("更新失败", str(message[1]))
                    continue
                if not isinstance(message, str):
                    continue
                if message == "__REFRESH_MODELS__":
                    self.refresh_models(write_log=False)
                    continue
                if message.startswith("__ORIGINAL_PREVIEW__:"):
                    self.last_original_preview.set(message.split(":", 1)[1])
                    self.write(f"可播放原唱预览：{self.last_original_preview.get()}")
                    continue
                if message.startswith("__COVER_PREVIEW__:"):
                    self.last_cover_preview.set(message.split(":", 1)[1])
                    self.write(f"可播放翻唱预览：{self.last_cover_preview.get()}")
                    continue
                if message.startswith("__MATRIX_DIR__:"):
                    self.last_matrix_dir.set(message.split(":", 1)[1])
                    self.write(f"可打开参数矩阵目录：{self.last_matrix_dir.get()}")
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
        auto_cleanup_after_train = bool(self.cleanup_after_train.get())
        if manual_mode and (not self.pth.get() or not self.index.get()):
            messagebox.showerror("模型不完整", "手动模型模式需要同时选择 .pth 和 .index。")
            return
        if train_mode:
            new_name = self.model_name.get().strip()
            if not new_name or new_name.lower() in {"auto", "自动", AUTO_MODEL_LABEL.lower(), TRAIN_MODEL_LABEL.lower()}:
                messagebox.showerror("缺少新模型显示名", "请给这次新声音填写一个显示名，例如“阿明男声”或 my_voice_2。")
                return
            new_internal = model_internal_name(new_name)
            duplicate_display = next(
                (
                    item
                    for item in discover_models()
                    if str(item.get("display_name") or item["name"]) == new_name
                ),
                None,
            )
            if duplicate_display:
                messagebox.showerror(
                    "模型显示名已存在",
                    f"显示名“{new_name}”已经存在，对应内部ID：{duplicate_display['name']}。\n\n"
                    "请换一个新的中文显示名，例如“阿明男声2”。\n\n"
                    "原因：同名旧模型会从旧 checkpoint 继续，如果旧模型已到默认训练轮数，"
                    "训练会很快结束并继续使用旧权重。"
                )
                return
            if (LOG_DIR / new_internal).exists():
                messagebox.showerror(
                    "模型内部ID已存在",
                    f"模型 logs/{new_internal} 已经存在。\n\n"
                    "请换一个全新的显示名，例如“阿明男声2”或 "
                    f"{new_model_default_name()}。\n\n"
                    "原因：同名旧模型会从旧 checkpoint 继续，如果旧模型已到默认训练轮数，"
                    "训练会很快结束并继续使用旧权重。"
                )
                return
            if not self.voice_dir.get():
                messagebox.showerror("缺少训练素材", "请先选择新声音素材文件夹。")
                return
            audio_files = [
                p
                for p in Path(self.voice_dir.get()).rglob("*")
                if p.is_file() and p.suffix.lower() in AUDIO_EXTS
            ]
            if not audio_files:
                messagebox.showerror("训练素材为空", "训练素材文件夹里没有支持的音频文件，请放入 wav/mp3/flac/m4a 等声音素材。")
                return

        self.running = True
        self.status.set("正在生成翻唱…")
        if train_mode:
            self.training_progress_text.set("训练进度：准备预处理和特征提取…")
            self.training_progress_value.set(0.0)
        else:
            self.training_progress_text.set("训练进度：本次使用已有模型，无需训练")
            self.training_progress_value.set(100.0)
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
                    progress_hook=self.training_progress_threadsafe if train_mode else None,
                )
                if train_mode:
                    self.training_progress_threadsafe(
                        {
                            "current_epoch": int(self.epochs.get()),
                            "total_epochs": int(self.epochs.get()),
                            "progress_percent": 100.0,
                            "current_step": 1,
                            "total_steps": 1,
                            "steps_per_minute": None,
                            "remaining_seconds": 0,
                            "eta": datetime.now(),
                        }
                    )
                self.log_threadsafe(f"生成完成：{result}")
                if train_mode and auto_cleanup_after_train:
                    try:
                        self.log_threadsafe("训练任务完成，开始自动清理训练缓存，只保留声音模型。")
                        cleaned = cleanup_model_training_cache(model_name, self.log_threadsafe)
                        self.status_threadsafe(f"生成完成，已清理 {human_size(int(cleaned['reclaimed']))}")
                    except Exception as cleanup_exc:
                        self.log_threadsafe(f"生成已完成，但自动清理失败：{cleanup_exc}")
                        self.status_threadsafe("生成完成，自动清理失败")
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
