# CR2 图片转换工具

这款 Windows 中文桌面工具可将佳能 CR2 原始照片批量转换为 JPG、PNG、WebP、TIFF 或 BMP。默认输出 JPG，质量为 95。

## 下载与安装

1. 安装 64 位 Windows 版 Python，建议使用 Python 3.11，保留安装器中的 Tcl/Tk 和 Python Launcher，并勾选 **Add python.exe to PATH**。[Python 官网](https://www.python.org/downloads/windows/)
2. 点击 **[下载 CR2 图片转换工具（ZIP）](https://github.com/vensailvensail/cr2-image-converter/archive/refs/heads/main.zip)**，也可以在仓库首页选择 **Code → Download ZIP**。
3. 右键 ZIP 并选择「全部解压」，打开包含 `start.bat` 的文件夹。双击 `start.bat`，保持窗口打开。首次启动会联网安装 rawpy 和 Pillow，之后可离线转换。

## 转换照片

点击「添加 CR2 文件」或「添加文件夹」，选择输出格式，点击「开始转换」。勾选「包含子文件夹」可处理整个目录树。大图可选择「半尺寸」以减少内存占用。点击停止后，工具会先完成当前照片。

输出目录留空时，每张照片保存在原文件旁的 `converted` 文件夹；指定目录后，所有结果集中保存。同名结果自动追加 `_1`、`_2` 等编号，原始 CR2 会保留。

## 命令行（PowerShell）

在本工具目录打开终端：

```powershell
# 单张图片转 JPG
.\start.bat "D:\Photos\IMG_0001.CR2"

# 整个目录及子目录转 PNG，指定输出目录
.\start.bat "D:\Photos" -r -f png -o "D:\Export"

# 多张图片转 WebP，自定义质量
.\start.bat "D:\Photos\A.CR2" "D:\Photos\B.CR2" -f webp -q 90

# 半尺寸 TIFF，使用自动白平衡
.\start.bat "D:\Photos" -f tiff --half-size --auto-wb

# 查看参数
.\start.bat --help
```

也可使用已安装依赖的 Python 运行 `python cr2_converter.py`。直接运行 Python 脚本时的退出码：0 全部成功，1 部分或全部文件转换失败，2 参数、路径或依赖错误。

## 图像处理说明

- 使用 rawpy/LibRaw 解码原始传感器数据，不是仅提取内嵌预览图。
- 默认使用相机白平衡、sRGB 和 rawpy 默认亮度/色调处理，按相机方向信息旋转；效果可能与相机直出 JPEG 或 Lightroom 不同。
- 所有格式输出 **8 位 RGB**，包括 TIFF；本版不提供 16 位存档输出。PNG/TIFF 使用无损压缩，JPG/WebP 使用有损压缩，BMP 不压缩。
- JPG、PNG、WebP、TIFF 写入 sRGB ICC 配置。不会复制原始 EXIF、GPS、拍摄时间或相机专用元数据；如需要这些信息，请保留原始 CR2。
- 损坏、加密或当前 LibRaw 不支持的 CR2 会在日志中报错，批量任务会继续处理其他文件。
- 大尺寸 RAW 转换会使用较多内存；程序逐张处理，可勾选「半尺寸」降低消耗。

依赖文档：[rawpy 参数](https://letmaik.github.io/rawpy/api/rawpy.Params.html)、[Pillow 文件格式](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html)。

项目源码采用 [MIT 许可证](LICENSE)。
