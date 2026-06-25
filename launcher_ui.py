import os
import queue
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from urllib.request import Request, urlopen

APP_TITLE = "大尸兄一键翻唱启动器"
DEFAULT_APP_DIR = Path(r"D:\Applio")
MINICONDA_DIR = Path.home() / "Miniconda3"
CONDA_EXE = MINICONDA_DIR / "Scripts" / "conda.exe"
INSTALL_BAT = "run-install.bat"
INSTALL_PS1 = "install_env.ps1"
APP_BAT = "run-applio.bat"
TENSORBOARD_BAT = "run-tensorboard.bat"
COVER_BAT = "run-one-click-cover.bat"

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


class LauncherApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("860x620")
        self.root.minsize(820, 560)

        self.app_dir = tk.StringVar(value=str(DEFAULT_APP_DIR if DEFAULT_APP_DIR.exists() else Path.cwd()))
        self.status = tk.StringVar(value="就绪")
        self.progress = tk.DoubleVar(value=0.0)
        self.worker_queue: queue.Queue[str] = queue.Queue()
        self.current_proc: subprocess.Popen | None = None

        self._build_ui()
        self.root.after(200, self._poll_queue)

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        header = ttk.Frame(self.root)
        header.pack(fill="x", **pad)
        ttk.Label(header, text="大尸兄一键翻唱启动器", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(header, text="安装、补齐基础模型、启动 Web UI / TensorBoard / 打开目录。", foreground="#555").pack(anchor="w")

        path_frame = ttk.LabelFrame(self.root, text="项目路径")
        path_frame.pack(fill="x", **pad)
        ttk.Entry(path_frame, textvariable=self.app_dir).pack(side="left", fill="x", expand=True, padx=8, pady=8)
        ttk.Button(path_frame, text="选择…", command=self.choose_dir).pack(side="left", padx=8, pady=8)
        ttk.Button(path_frame, text="打开目录", command=self.open_dir).pack(side="left", padx=8, pady=8)

        model_frame = ttk.LabelFrame(self.root, text="模型与运行件")
        model_frame.pack(fill="x", **pad)
        ttk.Button(model_frame, text="检查缺失", command=self.check_missing).pack(side="left", padx=8, pady=8)
        ttk.Button(model_frame, text="下载缺失", command=self.download_missing).pack(side="left", padx=8, pady=8)
        ttk.Button(model_frame, text="安装环境", command=self.install_env).pack(side="left", padx=8, pady=8)

        run_frame = ttk.LabelFrame(self.root, text="启动")
        run_frame.pack(fill="x", **pad)
        ttk.Button(run_frame, text="启动 Applio", command=self.launch_app).pack(side="left", padx=8, pady=8)
        ttk.Button(run_frame, text="启动 TensorBoard", command=self.launch_tensorboard).pack(side="left", padx=8, pady=8)
        ttk.Button(run_frame, text="大尸兄一键翻唱", command=self.launch_cover).pack(side="left", padx=8, pady=8)
        ttk.Button(run_frame, text="停止当前进程", command=self.stop_current).pack(side="left", padx=8, pady=8)

        prog_frame = ttk.Frame(self.root)
        prog_frame.pack(fill="x", **pad)
        ttk.Progressbar(prog_frame, variable=self.progress, maximum=100).pack(fill="x", expand=True)
        ttk.Label(prog_frame, textvariable=self.status).pack(anchor="w", pady=(4, 0))

        log_frame = ttk.LabelFrame(self.root, text="日志")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log = tk.Text(log_frame, height=18, wrap="word")
        self.log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

        self._log(f"默认项目路径：{self.app_dir.get()}")
        self._log("提示：Applio 官方安装检查要求路径在系统盘、无空格、纯 ASCII。")

    def _log(self, message: str):
        self.log.insert("end", message + "\n")
        self.log.see("end")

    def choose_dir(self):
        selected = filedialog.askdirectory(initialdir=self.app_dir.get())
        if selected:
            self.app_dir.set(selected)
            self._log(f"切换路径：{selected}")

    def _app_path(self) -> Path:
        return Path(self.app_dir.get()).expanduser().resolve()

    def _bat(self, name: str) -> Path:
        return self._app_path() / name

    def _env_ready(self) -> bool:
        return (self._app_path() / "env" / "python.exe").exists()

    def _spawn(self, args, cwd: Path | None = None):
        if self.current_proc and self.current_proc.poll() is None:
            messagebox.showinfo("提示", "已有进程在运行，请先停止当前进程。")
            return None
        cwd = cwd or self._app_path()
        self._log(f"执行：{' '.join(map(str, args))}")
        self.status.set("运行中…")
        self.progress.set(0)
        self.current_proc = subprocess.Popen(args, cwd=str(cwd), shell=False)
        self.root.after(1000, self._watch_proc)
        return self.current_proc

    def _watch_proc(self):
        if self.current_proc is None:
            return
        code = self.current_proc.poll()
        if code is None:
            self.root.after(1000, self._watch_proc)
            return
        self._log(f"进程结束，返回码：{code}")
        self.status.set(f"已结束（{code}）")
        self.current_proc = None
        self.progress.set(100 if code == 0 else 0)

    def stop_current(self):
        if self.current_proc and self.current_proc.poll() is None:
            self._log("正在停止当前进程…")
            self.current_proc.terminate()
            self.current_proc = None
            self.status.set("已停止")
        else:
            self._log("当前没有运行中的进程。")

    def open_dir(self):
        path = self._app_path()
        if path.exists():
            os.startfile(str(path))
        else:
            messagebox.showerror("错误", f"路径不存在：{path}")

    def check_missing(self):
        app = self._app_path()
        missing = [rel for rel in ASSET_URLS if not (app / rel).exists()]
        self._log(f"缺失 {len(missing)} 项基础件：")
        for item in missing:
            self._log(f"  - {item}")
        if not missing:
            self._log("基础件已齐全。")
        self.status.set(f"缺失 {len(missing)} 项")

    def download_missing(self):
        app = self._app_path()
        app.mkdir(parents=True, exist_ok=True)
        missing = [(rel, url) for rel, url in ASSET_URLS.items() if not (app / rel).exists()]
        if not missing:
            self._log("没有需要下载的基础件。")
            self.status.set("无需下载")
            return

        def task():
            total = len(missing)
            for idx, (rel, url) in enumerate(missing, start=1):
                dst = app / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                self.worker_queue.put(f"开始下载：{rel}")
                try:
                    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urlopen(req) as resp, open(dst, "wb") as f:
                        shutil.copyfileobj(resp, f)
                    self.worker_queue.put(f"完成：{rel}")
                except Exception as e:
                    self.worker_queue.put(f"失败：{rel} -> {e}")
                    return
                self.worker_queue.put(f"PROGRESS:{int(idx / total * 100)}")
            self.worker_queue.put("DONE:下载完成")

        self.status.set("正在下载基础件…")
        threading.Thread(target=task, daemon=True).start()

    def install_env(self):
        app = self._app_path()
        ps1 = app / INSTALL_PS1
        bat = self._bat(INSTALL_BAT)
        if ps1.exists():
            self._spawn(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps1)], cwd=app)
            return
        if not bat.exists():
            messagebox.showerror("错误", f"找不到安装脚本：{bat}")
            return
        self._spawn(["cmd", "/c", str(bat)], cwd=app)

    def launch_app(self):
        app = self._app_path()
        bat = self._bat(APP_BAT)
        if not bat.exists():
            messagebox.showerror("错误", f"找不到启动脚本：{bat}")
            return
        if not self._env_ready():
            if messagebox.askyesno("未检测到环境", "未发现 env\\python.exe，是否先执行安装？"):
                self.install_env()
            return
        self._spawn(["cmd", "/c", str(bat)], cwd=app)

    def launch_tensorboard(self):
        app = self._app_path()
        bat = self._bat(TENSORBOARD_BAT)
        if not bat.exists():
            messagebox.showerror("错误", f"找不到脚本：{bat}")
            return
        if not self._env_ready():
            if messagebox.askyesno("未检测到环境", "未发现 env\\python.exe，是否先执行安装？"):
                self.install_env()
            return
        self._spawn(["cmd", "/c", str(bat)], cwd=app)

    def launch_cover(self):
        app = self._app_path()
        bat = self._bat(COVER_BAT)
        if not bat.exists():
            messagebox.showerror("错误", f"找不到脚本：{bat}")
            return
        if not self._env_ready():
            if messagebox.askyesno("未检测到环境", "未发现 env\\python.exe，是否先执行安装？"):
                self.install_env()
            return
        self._spawn(["cmd", "/c", str(bat)], cwd=app)

    def _poll_queue(self):
        try:
            while True:
                msg = self.worker_queue.get_nowait()
                if msg.startswith("PROGRESS:"):
                    self.progress.set(float(msg.split(":", 1)[1]))
                elif msg.startswith("DONE:"):
                    self.status.set(msg.split(":", 1)[1])
                    self.progress.set(100)
                else:
                    self._log(msg)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)


def main():
    root = tk.Tk()
    try:
        style = ttk.Style()
        if "vista" in style.theme_names():
            style.theme_use("vista")
    except Exception:
        pass
    LauncherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
