import cv2
import subprocess
import threading
import time
import fcntl
import os
import numpy as np
from collections import deque

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

# ===================== 配置参数（直接修改这里）=====================
WIDTH, HEIGHT = 1280, 720    # 摄像头分辨率
FPS = 30                     # 推流帧率
RTMP_URL = "rtmp://120.26.89.24:1935/live/cam01"  # 推流地址
AUDIO_DEVICE = "plughw:3,0"  # ALSA 音频源（plughw 走 plug 层，避免与 Pulse/Pipewire 冲突）

# 曝光：低光下自动曝光会把曝光时间拉到 1/15s，导致帧率从 30 掉到 15。
# 锁定较短的手动曝光可恢复 30fps，代价是画面变暗（需补光）。
VIDEO_DEVICE = "/dev/video0" # 摄像头设备，用于 v4l2-ctl 设置 OpenCV 访问不到的控制项
MANUAL_EXPOSURE = True       # True=锁定手动曝光保帧率，False=自动曝光
EXPOSURE_ABS = 300           # 手动曝光时间，单位 100μs（范围 78~1250；≤333 才能保 30fps，越大越亮）

# 摄像头旋转：物理安装方向（0=正立, 90=右侧卧, 180=倒置, 270=左侧卧）
CAMERA_ROTATION = 0           # 帧采集后先旋转到此角度再处理，确保人脸检测对着正立画面
# 旋转 90/270 时宽高互换
EFF_W, EFF_H = (HEIGHT, WIDTH) if CAMERA_ROTATION in (90, 270) else (WIDTH, HEIGHT)

# 运动检测 / 人脸
EFF_DETECT_W, EFF_DETECT_H = 320, 180  # 检测降采样分辨率
# 摄像头旋转时等比交换，避免人脸被非等比缩放压扁
if CAMERA_ROTATION in (90, 270):
    EFF_DETECT_W, EFF_DETECT_H = EFF_DETECT_H, EFF_DETECT_W
MOTION_THRESHOLD = 0.003     # 前景像素占比 > 该值认定为有运动
MOTION_HOLD_SEC = 3.0        # 运动消失后人脸框保留时间（秒）
MOTION_INTERVAL = 5          # 每 N 帧跑一次运动检测（>1 省 CPU）
FACE_INTERVAL = 15           # 每 N 帧跑一次人脸检测（Haar 开销大，不宜过频）
FACE_MIN_SIZE = 30           # 最小人脸尺寸（在降采样图像上的像素）
FACE_CASCADE_PATH = "/media/usb0/opencv/haarcascade_frontalface_default.xml"

# 自动重连
RECONNECT_INITIAL = 1.0      # 初始退避秒数
RECONNECT_MAX = 30.0         # 最大退避秒数
SESSION_HEALTHY_SEC = 10.0   # 会话存活 ≥ 该时长再失败时，退避归零
# ==================================================================


def set_v4l2_ctrl(device, ctrl, value):
    """通过 v4l2-ctl 设置 OpenCV 访问不到的 UVC 控制项（如 exposure_dynamic_framerate）"""
    try:
        subprocess.run(["v4l2-ctl", "-d", device, "-c", f"{ctrl}={value}"],
                       check=True, capture_output=True)
    except Exception as e:
        print(f"设置 {ctrl}={value} 失败：{e}", flush=True)


def build_ffmpeg_cmd():
    """ffmpeg 推流命令（视频走 RK VPU 硬编，音频走 ALSA + AAC）"""
    return [
        "ffmpeg",
        "-y",
        # ---- 输入 1：视频（来自 Python stdin）----
        "-thread_queue_size", "4096",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{EFF_W}x{EFF_H}",
        "-r", str(FPS),
        "-use_wallclock_as_timestamps", "1",
        "-i", "-",
        # ---- 输入 2：音频（USB 摄像头自带麦克风 HBV HD CAMERA）----
        "-thread_queue_size", "4096",
        "-f", "alsa",
        "-ac", "1",
        "-ar", "44100",            # 与输出一致，省一次重采样
        "-i", AUDIO_DEVICE,
        # ---- 视频编码（Rockchip VPU 硬件编码）----
        "-c:v", "h264_rkmpp",
        "-pix_fmt", "nv12",        # VPU 原生吃 NV12，让 ffmpeg 做 BGR24→NV12 转换
        "-rc_mode", "CBR",
        "-b:v", "4M",
        "-g", "60",
        "-bf", "0",                # 零 B 帧，进一步降低延迟
        "-profile:v", "high",
        # ---- 音频编码（AAC，FLV 标准）+ 同步补偿 ----
        "-c:a", "aac",
        "-b:a", "96k",
        "-ar", "44100",
        # 关键：音频自适应重采样补偿，让音频跟随视频时间戳，解决 Python 处理延迟造成的不同步
        "-af", "aresample=async=1000",
        # ---- 输出 ----
        "-f", "flv",
        "-loglevel", "error",
        RTMP_URL,
    ]


def start_ffmpeg():
    """启动 ffmpeg 子进程，并起后台线程持续排空 stderr，避免管道写满阻塞"""
    try:
        proc = subprocess.Popen(
            build_ffmpeg_cmd(),
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            bufsize=0,
        )
    except FileNotFoundError:
        print("错误：未找到 ffmpeg 可执行文件，请确认已安装并在 PATH 中", flush=True)
        raise
    # 增大管道缓冲区，减少 2.76MB 大帧写入时的阻塞等待
    try:
        F_SETPIPE_SZ = 1031  # Linux fcntl 常量
        fcntl.fcntl(proc.stdin.fileno(), F_SETPIPE_SZ, 1048576)
        print("管道缓冲区已增至 1MB", flush=True)
    except Exception as e:
        print(f"增大管道缓冲区失败（使用默认 64KB）: {e}", flush=True)
    stderr_lines = deque(maxlen=200)
    def _drain(pipe):
        try:
            for line in iter(pipe.readline, b''):
                stderr_lines.append(line.decode("utf-8", errors="ignore").rstrip())
        except Exception:
            pass
    threading.Thread(target=_drain, args=(proc.stderr,), daemon=True).start()
    return proc, stderr_lines


def stop_ffmpeg(proc):
    """优雅关闭 ffmpeg：先关 stdin 让其写完 FLV 尾，超时再强制"""
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
    except Exception as e:
        print(f"释放 ffmpeg 时出错：{e}", flush=True)


class FrameGrabber:
    """独立线程持续抓取摄像头，只保留最新帧，避免采集与处理串行造成掉帧/累积延迟"""

    def __init__(self, cap):
        self.cap = cap
        self.cond = threading.Condition()
        self.frame = None
        self.seq = 0
        self.ok = True
        self.running = True
        self.grab_times = deque(maxlen=60)  # 诊断：采集时间戳
        self.read_ms = deque(maxlen=60)     # 诊断：cap.read() 耗时
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        while self.running:
            t0 = time.monotonic()
            ret, frame = self.cap.read()
            dt = time.monotonic() - t0
            with self.cond:
                self.ok = ret
                if ret:
                    self.frame = frame
                    self.seq += 1
                    self.grab_times.append(time.monotonic())
                    self.read_ms.append(dt * 1000)
                self.cond.notify_all()
            if not ret:
                time.sleep(0.01)

    def grab_fps(self):
        with self.cond:
            n = len(self.grab_times)
            if n < 2:
                return 0.0
            return (n - 1) / (self.grab_times[-1] - self.grab_times[0])

    def read_avg_ms(self):
        with self.cond:
            return sum(self.read_ms) / len(self.read_ms) if self.read_ms else 0.0

    def read(self, last_seq, timeout=2.0):
        """阻塞等待比 last_seq 更新的帧；返回 (ok, frame, seq)。超时返回 (True, None, last_seq)"""
        with self.cond:
            got = self.cond.wait_for(
                lambda: self.seq != last_seq or not self.ok or not self.running,
                timeout)
            if not got:
                return True, None, last_seq
            if not self.ok:
                return False, None, self.seq
            return True, self.frame, self.seq

    def stop(self):
        with self.cond:
            self.running = False
            self.cond.notify_all()
        self.thread.join(timeout=1.0)


def push_session(grabber, face_cascade, mog2, morph_kernel):
    proc, stderr_lines = start_ffmpeg()
    print("推流已启动 →", RTMP_URL, flush=True)

    sx, sy = EFF_W / EFF_DETECT_W, EFF_H / EFF_DETECT_H
    # 整数化的运动像素阈值，避免每帧除法
    motion_pixel_thresh = int(EFF_DETECT_W * EFF_DETECT_H * MOTION_THRESHOLD)
    detect_boxes = []
    last_motion_ts = 0.0
    has_motion = False
    frame_count = 0
    last_seq = -1
    fps_samples = deque(maxlen=30)
    diag_proc = diag_write = 0.0  # 诊断：处理 / 写管道累计耗时
    diag_n = 0

    # 右上角文字缓存：秒级更新即可
    osd_cache = {"sec": -1, "fps_bucket": -1, "text": "", "x": 0, "y": 0}

    # CPU 占用采样（/proc/stat 需前后两次差值计算）
    _cpu_prev = [0, 0]  # [total, idle]
    def _read_cpu():
        try:
            with open('/proc/stat', 'r') as f:
                vals = [int(x) for x in f.readline().split()[1:]]
            total, idle = sum(vals), vals[3]
            dt, di = total - _cpu_prev[0], idle - _cpu_prev[1]
            _cpu_prev[0], _cpu_prev[1] = total, idle
            return 100.0 * (1 - di / dt) if dt > 0 else 0.0
        except Exception:
            return 0.0

    def _read_mem():
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            total = int([l for l in lines if l.startswith('MemTotal')][0].split()[1])
            avail = int([l for l in lines if l.startswith('MemAvailable')][0].split()[1])
            return 100.0 * (total - avail) / total
        except Exception:
            return 0.0

    # 中文字体渲染（OpenCV HERSHEY 不支持中文，用 PIL）
    _cn_font_path = None
    _cn_font = None
    if _PIL_OK:
        _font_paths = [
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Medium.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ]
        for fp in _font_paths:
            if os.path.exists(fp):
                try:
                    _cn_font_path = fp
                    _cn_font = ImageFont.truetype(fp, 24)
                    break
                except Exception:
                    pass

    def _put_cn(img, text, pos, color, font_size=None):
        """在 OpenCV 图像上绘制中文，自动回退 ASCII"""
        if _cn_font_path is not None:
            f = ImageFont.truetype(_cn_font_path, font_size or 20) if font_size else _cn_font
            bbox = f.getbbox(text)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            if tw <= 0 or th <= 0:
                return
            pad = 12
            txt_img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
            d = ImageDraw.Draw(txt_img)
            d.text((pad - bbox[0], pad - bbox[1]), text, font=f, fill=(*color, 255))
            txt_np = np.array(txt_img)
            x, y = pos
            ih, iw = img.shape[:2]
            ph, pw = txt_np.shape[:2]
            if x < 0: x = 0
            if y < 0: y = 0
            if x + pw > iw: pw = iw - x
            if y + ph > ih: ph = ih - y
            if pw <= 0 or ph <= 0:
                return
            roi = img[y:y+ph, x:x+pw]
            alpha = txt_np[:ph, :pw, 3:] / 255.0
            img[y:y+ph, x:x+pw] = (txt_np[:ph, :pw, :3] * alpha + roi * (1 - alpha)).astype(np.uint8)
        else:
            cv2.putText(img, text.encode('ascii', 'replace').decode(), pos,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

    def ffmpeg_exited():
        if proc.poll() is None:
            return False
        err = "\n".join(stderr_lines)
        print("=" * 50, flush=True)
        print("FFMPEG 异常退出！错误信息：", flush=True)
        print(err or "(无 stderr 输出)", flush=True)
        print("=" * 50, flush=True)
        return True

    try:
        while True:
            ok, frame, last_seq = grabber.read(last_seq)
            if not ok:
                print("摄像头读取失败，结束当前会话以触发重连", flush=True)
                return
            if frame is None:
                # 超时无新帧：仅检查 ffmpeg 是否已退出，再继续等待
                if ffmpeg_exited():
                    return
                continue

            now = time.monotonic()

            # 摄像头物理旋转纠正：先把帧转正，后续检测/推流都是正立画面
            if CAMERA_ROTATION == 90:
                frame = cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
            elif CAMERA_ROTATION == 180:
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            elif CAMERA_ROTATION == 270:
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
            if CAMERA_ROTATION:
                frame = frame.copy()  # cv2.rotate 可能产生非连续内存，data 写入管道会错乱

            fps_samples.append(now)
            real_fps = ((len(fps_samples) - 1) / (fps_samples[-1] - fps_samples[0])
                        if len(fps_samples) >= 2 else 0.0)

            frame_count += 1

            if frame_count % MOTION_INTERVAL == 0:
                small = cv2.resize(frame, (EFF_DETECT_W, EFF_DETECT_H))
                small_gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                fg = mog2.apply(small_gray)
                _, fg = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)
                fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, morph_kernel)
                has_motion = cv2.countNonZero(fg) > motion_pixel_thresh
                if has_motion:
                    last_motion_ts = now

            # 人脸检测独立于运动检测运行
            if frame_count % FACE_INTERVAL == 0:
                # 复用最近一次的 small_gray（若本轮已算过），否则重新降采样
                if frame_count % MOTION_INTERVAL != 0:
                    small = cv2.resize(frame, (EFF_DETECT_W, EFF_DETECT_H))
                    small_gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    small_gray, scaleFactor=1.1, minNeighbors=3,
                    minSize=(FACE_MIN_SIZE, FACE_MIN_SIZE))
                if len(faces) > 0:
                    last_motion_ts = now  # 有人脸时延长保留时间
                detect_boxes = [
                    (int(x * sx), int(y * sy), int(w * sx), int(h * sy))
                    for (x, y, w, h) in faces
                ]

            # 人脸框超过保留时间后清除
            if now - last_motion_ts > MOTION_HOLD_SEC:
                detect_boxes = []

            # 有人脸框或运动标签时才绘制
            if detect_boxes or has_motion:
                for (x, y, w, h) in detect_boxes:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                    cv2.putText(frame, "FACE", (x, y - 8),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
                if has_motion:
                    _put_cn(frame, "检测中", (10, 22), (0, 255, 0))

            # 右上角时间戳 + 帧率 + CPU/内存：秒级更新
            cur_sec = int(now)
            fps_bucket = int(real_fps * 2)  # 0.5 fps 一档
            if cur_sec != osd_cache["sec"] or fps_bucket != osd_cache["fps_bucket"]:
                text = "lubancat {}  {:.1f}fps  CPU:{:.0f}%  MEM:{:.0f}%".format(
                    time.strftime("%Y-%m-%d %H:%M:%S"), real_fps,
                    _read_cpu(), _read_mem())
                (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
                osd_cache.update(sec=cur_sec, fps_bucket=fps_bucket, text=text,
                                 x=EFF_W - tw - 10, y=10 + th + 1)
            x1, y1 = osd_cache["x"], osd_cache["y"]
            text = osd_cache["text"]
            cv2.putText(frame, text, (x1 + 1, y1 + 1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
            cv2.putText(frame, text, (x1, y1),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            if ffmpeg_exited():
                return

            t_write = time.monotonic()
            diag_proc += t_write - now
            try:
                proc.stdin.write(frame.data)
            except BrokenPipeError:
                print("错误：管道破裂，ffmpeg 已退出", flush=True)
                return
            except Exception as e:
                print(f"写入帧失败：{e}", flush=True)
                return
            diag_write += time.monotonic() - t_write
            diag_n += 1
            if diag_n >= 60:
                print("诊断 处理fps={:.1f} 采集fps={:.1f} read={:.1f}ms 处理={:.1f}ms 写管道={:.1f}ms".format(
                    real_fps, grabber.grab_fps(), grabber.read_avg_ms(),
                    diag_proc / diag_n * 1000, diag_write / diag_n * 1000), flush=True)
                diag_proc = diag_write = 0.0
                diag_n = 0
    finally:
        stop_ffmpeg(proc)


def main():
    # 初始化摄像头
    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    if not cap.isOpened():
        print("错误：无法打开摄像头！", flush=True)
        cap.release()
        return

    # MJPG 格式必须设，USB2.0 下 YUYV 带宽不够跑 30fps
    cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, FPS)

    # 锁定曝光：避免低光下自动曝光拉长曝光时间，把帧率从 30 钳到 15
    if MANUAL_EXPOSURE:
        cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # 1=手动, 3=自动（V4L2 UVC 约定）
        cap.set(cv2.CAP_PROP_EXPOSURE, EXPOSURE_ABS)
        # 关键：关闭动态帧率，否则曝光再短相机仍会为曝光降帧（OpenCV 无法访问此控制）
        set_v4l2_ctrl(VIDEO_DEVICE, "exposure_dynamic_framerate", 0)

    # 诊断：打印摄像头实际生效的采集参数（格式不是 MJPG 时帧率上不去）
    fourcc = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join(chr((fourcc >> (8 * i)) & 0xFF) for i in range(4))
    print("摄像头实际参数：{}x{} @ {:.0f}fps  格式={}  auto_exp={}  exposure={}".format(
        int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        cap.get(cv2.CAP_PROP_FPS), fourcc_str,
        cap.get(cv2.CAP_PROP_AUTO_EXPOSURE), cap.get(cv2.CAP_PROP_EXPOSURE)), flush=True)

    # 模型
    face_cascade = cv2.CascadeClassifier(FACE_CASCADE_PATH)
    if face_cascade.empty():
        print(f"错误：无法加载人脸检测模型！路径：{FACE_CASCADE_PATH}", flush=True)
        cap.release()
        return
    mog2 = cv2.createBackgroundSubtractorMOG2(
        history=300, varThreshold=25, detectShadows=True
    )
    morph_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))

    # 独立线程采集，主线程专注处理 + 推流，避免串行掉帧
    grabber = FrameGrabber(cap)

    backoff = RECONNECT_INITIAL
    try:
        while True:
            try:
                t0 = time.monotonic()
                push_session(grabber, face_cascade, mog2, morph_kernel)
                # 会话存活够久才失败，认为之前是稳定的，下次退避归零
                if time.monotonic() - t0 >= SESSION_HEALTHY_SEC:
                    backoff = RECONNECT_INITIAL
                print(f"准备 {backoff:.1f}s 后重连...", flush=True)
                time.sleep(backoff)
                backoff = min(backoff * 2, RECONNECT_MAX)
            except RuntimeError as e:
                print(f"致命错误：{e}，停止程序", flush=True)
                break
    except KeyboardInterrupt:
        print("\n用户手动停止程序", flush=True)
    finally:
        grabber.stop()
        cap.release()
        print("摄像头已释放，程序退出", flush=True)


if __name__ == "__main__":
    main()
