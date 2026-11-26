"""CR2 converter: run without arguments for the Chinese GUI, or use --help."""
from __future__ import annotations

import argparse
from pathlib import Path
import queue
import sys
import threading

FORMATS = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP", "tiff": "TIFF", "bmp": "BMP"}


def normalize_format(value: str) -> str:
    value = value.lower().lstrip(".")
    value = {"jpeg": "jpg", "tif": "tiff"}.get(value, value)
    if value not in FORMATS:
        raise ValueError("格式必须为 jpg、png、webp、tiff 或 bmp")
    return value


def collect_files(inputs, recursive=False):
    """Expand folders and deduplicate files, including mixed-case CR2 suffixes."""
    result, seen = [], set()
    for item in inputs:
        path = Path(item).expanduser().resolve()
        if not path.exists():
            raise ValueError(f"路径不存在：{path}")
        if path.is_dir():
            candidates = sorted(path.rglob("*") if recursive else path.iterdir())
        elif path.suffix.lower() == ".cr2":
            candidates = [path]
        else:
            raise ValueError(f"请选择 CR2 文件或文件夹：{path}")
        for candidate in candidates:
            if candidate.is_file() and candidate.suffix.lower() == ".cr2":
                resolved = candidate.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    result.append(resolved)
    return result


def check_dependencies():
    try:
        import rawpy  # noqa: F401
        from PIL import Image, ImageCms  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("依赖缺失或无法加载，请运行 tools 中的 start.bat 安装依赖。") from exc


def save_image(image, target: Path, fmt: str, quality: int):
    """Reserve a unique output atomically; remove incomplete files on failure."""
    from PIL import ImageCms
    options = {}
    if fmt != "bmp":
        options["icc_profile"] = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    if fmt == "jpg":
        options.update(quality=quality, subsampling=0, optimize=True)
    elif fmt == "webp":
        options.update(quality=quality, method=4)
    elif fmt == "tiff":
        options["compression"] = "tiff_deflate"
    target.parent.mkdir(parents=True, exist_ok=True)
    number = 0
    while True:
        destination = target if number == 0 else target.with_name(f"{target.stem}_{number}{target.suffix}")
        try:
            stream = destination.open("xb")
            break
        except FileExistsError:
            number += 1
    try:
        with stream:
            image.save(stream, format=FORMATS[fmt], **options)
    except BaseException:
        destination.unlink(missing_ok=True)
        raise
    return destination


def convert_one(source: Path, output_dir=None, fmt="jpg", quality=95, half_size=False, auto_wb=False):
    import rawpy
    from PIL import Image
    fmt = normalize_format(fmt)
    if not 1 <= quality <= 100:
        raise ValueError("质量必须在 1–100 之间")
    source = Path(source).resolve()
    # Process sensor data, rather than copying the embedded JPEG preview.
    with rawpy.imread(str(source)) as raw:
        rgb = raw.postprocess(
            use_camera_wb=not auto_wb,
            use_auto_wb=auto_wb,
            output_color=rawpy.ColorSpace.sRGB,
            output_bps=8,
            half_size=half_size,
        )
    folder = Path(output_dir).expanduser().resolve() if output_dir else source.parent / "converted"
    with Image.fromarray(rgb) as image:
        return save_image(image, folder / f"{source.stem}.{fmt}", fmt, quality)


def run_batch(files, *, log=print, progress=None, cancel=None, **options):
    ok = failed = 0
    for index, source in enumerate(files, 1):
        if cancel is not None and cancel.is_set():
            break
        try:
            destination = convert_one(source, **options)
            ok += 1
            log(f"成功：{source.name} → {destination}")
        except Exception as exc:
            failed += 1
            log(f"失败：{source}：{exc}")
        if progress:
            progress(index, len(files))
    return ok, failed, len(files) - ok - failed


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from tkinter.scrolledtext import ScrolledText

    root = tk.Tk()
    root.title("CR2 图片转换工具")
    root.geometry("820x620")
    root.minsize(680, 520)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    frame = ttk.Frame(root, padding=16)
    frame.grid(sticky="nsew")
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(2, weight=1)
    frame.rowconfigure(8, weight=1)
    ttk.Label(frame, text="CR2 图片转换", font=("Microsoft YaHei UI", 18, "bold")).grid(sticky="w")
    ttk.Label(frame, text="批量转换为常用图片格式 · 保留原文件 · 同名自动编号").grid(row=1, sticky="w", pady=(4, 10))
    file_list = tk.Listbox(frame, height=6, selectmode=tk.EXTENDED)
    file_list.grid(row=2, sticky="nsew")
    inputs = []
    events = queue.Queue()
    cancel = threading.Event()
    busy = False

    def add_paths(paths):
        for path in paths:
            if path not in inputs:
                inputs.append(path)
                file_list.insert(tk.END, path)

    def clear():
        inputs.clear()
        file_list.delete(0, tk.END)

    toolbar = ttk.Frame(frame)
    toolbar.grid(row=3, sticky="w", pady=8)
    ttk.Button(toolbar, text="添加 CR2 文件", command=lambda: add_paths(filedialog.askopenfilenames(filetypes=[("CR2 文件", "*.cr2 *.CR2"), ("所有文件", "*.*")]))).pack(side="left")

    def add_folder():
        folder = filedialog.askdirectory()
        if folder:
            add_paths([folder])

    ttk.Button(toolbar, text="添加文件夹", command=add_folder).pack(side="left", padx=6)
    ttk.Button(toolbar, text="清空列表", command=clear).pack(side="left")
    recursive = tk.BooleanVar(value=True)
    ttk.Checkbutton(toolbar, text="包含子文件夹", variable=recursive).pack(side="left", padx=10)

    output = tk.StringVar()
    output_row = ttk.Frame(frame)
    output_row.grid(row=4, sticky="ew", pady=6)
    output_row.columnconfigure(1, weight=1)
    ttk.Label(output_row, text="输出目录：").grid(row=0, column=0)
    ttk.Entry(output_row, textvariable=output).grid(row=0, column=1, sticky="ew")

    def choose_output():
        folder = filedialog.askdirectory()
        if folder:
            output.set(folder)

    ttk.Button(output_row, text="选择…", command=choose_output).grid(row=0, column=2, padx=(6, 0))
    ttk.Label(frame, text="留空时，保存到各原文件旁的 converted 文件夹。所有格式均输出 8 位 RGB。", wraplength=730).grid(row=5, sticky="w")
    settings = ttk.Frame(frame)
    settings.grid(row=6, sticky="w", pady=10)
    fmt = tk.StringVar(value="jpg")
    quality = tk.StringVar(value="95")
    half_size = tk.BooleanVar()
    auto_wb = tk.BooleanVar()
    ttk.Label(settings, text="格式：").pack(side="left")
    ttk.Combobox(settings, textvariable=fmt, values=list(FORMATS), width=7, state="readonly").pack(side="left")
    ttk.Label(settings, text="  JPG/WebP 质量：").pack(side="left")
    ttk.Spinbox(settings, from_=1, to=100, textvariable=quality, width=5).pack(side="left")
    ttk.Checkbutton(settings, text="半尺寸", variable=half_size).pack(side="left", padx=8)
    ttk.Checkbutton(settings, text="自动白平衡", variable=auto_wb).pack(side="left")

    controls = ttk.Frame(frame)
    controls.grid(row=7, sticky="ew", pady=(0, 8))
    bar = ttk.Progressbar(controls, mode="determinate")
    bar.pack(side="left", fill="x", expand=True, padx=(0, 10))
    log_box = ScrolledText(frame, height=9, wrap="word", state="disabled")
    log_box.grid(row=8, sticky="nsew")
    status = tk.StringVar(value="就绪")
    ttk.Label(frame, textvariable=status).grid(row=9, sticky="w", pady=(8, 0))

    def log(message):
        log_box.configure(state="normal")
        log_box.insert(tk.END, message + "\n")
        log_box.see(tk.END)
        log_box.configure(state="disabled")

    def worker(selected, recurse, options):
        try:
            files = collect_files(selected, recurse)
            if not files:
                raise ValueError("未找到 CR2 文件")
            result = run_batch(files, log=lambda s: events.put(("log", s)),
                               progress=lambda n, total: events.put(("progress", (n, total))),
                               cancel=cancel, **options)
            events.put(("done", result))
        except Exception as exc:
            events.put(("error", str(exc)))

    def start():
        nonlocal busy
        try:
            if not inputs:
                raise ValueError("请先添加 CR2 文件或文件夹")
            check_dependencies()
            q = int(quality.get())
            if not 1 <= q <= 100:
                raise ValueError("质量必须在 1–100 之间")
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("无法开始", str(exc))
            return
        options = dict(output_dir=output.get().strip() or None, fmt=fmt.get(), quality=q,
                       half_size=half_size.get(), auto_wb=auto_wb.get())
        busy = True
        cancel.clear()
        start_button.configure(state="disabled")
        stop_button.configure(state="normal")
        bar["value"] = 0
        status.set("正在查找并转换 CR2 文件…")
        log("开始转换；本次使用点击开始时的文件列表和设置。")
        threading.Thread(target=worker, args=(list(inputs), recursive.get(), options), daemon=True).start()

    def stop():
        cancel.set()
        status.set("正在停止，当前文件处理完毕后结束…")
        stop_button.configure(state="disabled")

    start_button = ttk.Button(controls, text="开始转换", command=start)
    start_button.pack(side="left")
    stop_button = ttk.Button(controls, text="停止", command=stop, state="disabled")
    stop_button.pack(side="left", padx=(6, 0))

    def poll():
        nonlocal busy
        while True:
            try:
                kind, payload = events.get_nowait()
            except queue.Empty:
                break
            if kind == "log":
                log(payload)
            elif kind == "progress":
                n, total = payload
                bar.configure(maximum=total, value=n)
                if not cancel.is_set():
                    status.set(f"已处理 {n}/{total}")
            else:
                busy = False
                start_button.configure(state="normal")
                stop_button.configure(state="disabled")
                if kind == "done":
                    ok, failed, pending = payload
                    message = f"完成：成功 {ok}，失败 {failed}，未处理 {pending}"
                else:
                    message = "错误：" + payload
                status.set(message)
                log(message)
        root.after(100, poll)

    def close():
        if busy:
            stop()
            messagebox.showinfo("正在结束转换", "当前文件处理完毕后即可关闭窗口。")
        else:
            root.destroy()

    root.protocol("WM_DELETE_WINDOW", close)
    root.after(100, poll)
    root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description="将 CR2 原始照片转换为常用图片；不带参数时打开窗口。")
    parser.add_argument("inputs", nargs="*", help="CR2 文件或文件夹，可传多个")
    parser.add_argument("--gui", action="store_true", help="打开图形界面")
    parser.add_argument("-o", "--output", type=Path, help="输出目录；默认是原文件旁的 converted")
    parser.add_argument("-f", "--format", default="jpg", help="jpg / png / webp / tiff / bmp")
    parser.add_argument("-q", "--quality", type=int, default=95, help="JPG/WebP 质量，1–100，默认 95")
    parser.add_argument("-r", "--recursive", action="store_true", help="扫描子文件夹")
    parser.add_argument("--half-size", action="store_true", help="宽高缩小至约一半，加快处理")
    parser.add_argument("--auto-wb", action="store_true", help="自动白平衡；默认使用相机白平衡")
    args = parser.parse_args(argv)
    if args.gui or not args.inputs:
        launch_gui()
        return 0
    try:
        fmt = normalize_format(args.format)
        if not 1 <= args.quality <= 100:
            raise ValueError("质量必须在 1–100 之间")
        check_dependencies()
        files = collect_files(args.inputs, args.recursive)
        if not files:
            raise ValueError("未找到 CR2 文件")
        ok, failed, _ = run_batch(files, output_dir=args.output, fmt=fmt, quality=args.quality,
                                  half_size=args.half_size, auto_wb=args.auto_wb)
        print(f"完成：成功 {ok}，失败 {failed}")
        return 1 if failed else 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
