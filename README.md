# WebRTC 视频播放器

Vue3 前端播放器，通过 SRS 拉取 WebRTC 流。

## 项目结构

```
webrtc-player/             # Vue3 前端项目（唯一需要部署的部分）
├── src/
│   ├── App.vue
│   └── components/
│       └── WebRTCPlayer.vue
├── .env                   # 本地环境变量（需自行创建）
├── .env.example           # 环境变量模板
├── package.json
└── vite.config.js
srs/                       # SRS 服务端参考配置（不作为部署内容）
├── docker-compose-rtc.yml
└── rtc.conf
```

## 部署需要修改的文件

### 1. `webrtc-player/.env`

复制 `.env.example` 创建 `.env`，填入实际服务器地址：

```
VITE_SRS_URL=webrtc://你的服务器IP:1985/应用名/流名称
```

例如：

```
VITE_SRS_URL=webrtc://120.26.89.24:1985/live/cam01
```

### 2. `webrtc-player/src/App.vue:3`

如果不想用 `.env` 文件，可以直接改这里的默认值：

```vue
<WebRTCPlayer src="webrtc://你的服务器IP:1985/live/cam01" />
```

### 3. 推流地址中的 IP

推流命令中的 `rtmp://你的服务器IP:1935/live/cam01` 也需要替换。

## 启动

```bash
cd webrtc-player
npm install
npm run dev
```

浏览器打开显示的地址，点击 **连接**。

## 硬件环境

| 设备 | 型号 |
|------|------|
| 主板 | 鲁班猫 3 (RK3588) |
| 系统 | Ubuntu |
| 摄像头 | UVC 摄像头 (USB Video Class) |
| 编码 | 硬件编码器 h264_rkmpp (RKMPP) |

摄像头通过 USB 连接，设备节点 `/dev/video0`。系统需安装 Rockchip MPP 编码驱动：

```bash
# RK3588 硬件编码支持
sudo apt install librkmpv* rockchip-mpp
```

## LubanCat 推流命令

### 720P 带水印

```bash
ffmpeg -thread_queue_size 4096 \
  -f v4l2 -r 30 -s 1280x720 -input_format mjpeg \
  -i /dev/video0 \
  -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='lubancat %{localtime}':fontcolor=white:fontsize=32:x=w-tw-20:y=30" \
  -c:v h264_rkmpp -profile:v high -bf 0 \
  -b:v 4000k -g 60 -an \
  -f flv rtmp://你的服务器IP:1935/live/cam01
```

### 4K 高码率

```bash
ffmpeg -f v4l2 -r 30 -s 3840x2160 -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 -rtbufsize 8M \
  -i /dev/video0 \
  -c:v h264_rkmpp -profile:v high -bf 0 \
  -b:v 15000k -maxrate 18000k -bufsize 18000k \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -flags +global_header -avoid_negative_ts make_zero \
  -flvflags no_duration_filesize \
  -f flv rtmp://你的服务器IP:1935/live/cam01
```

### 1080P 低码率

```bash
ffmpeg -f v4l2 -r 30 -s 1920x1080 -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 -rtbufsize 3M \
  -i /dev/video0 \
  -c:v h264_rkmpp -profile:v baseline -bf 0 \
  -b:v 2500k -maxrate 2600k -bufsize 2600k \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -flags +global_header -avoid_negative_ts make_zero \
  -flvflags no_duration_filesize \
  -f flv rtmp://你的服务器IP:1935/live/cam01
```

### 1080P 低码率

```bash
ffmpeg -f v4l2 -r 30 -s 1920x1080 -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 -rtbufsize 3M \
  -i /dev/video0 \
  -c:v h264_rkmpp -profile:v baseline -bf 0 \
  -b:v 2500k -maxrate 2600k -bufsize 2600k \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -flags +global_header -avoid_negative_ts make_zero \
  -flvflags no_duration_filesize \
  -f flv rtmp://120.26.89.24:1935/live/cam01
```

## 端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 1935 | TCP | RTMP 推流 |
| 8085 | TCP | SRS 管理页面 |
| 1985 | TCP | SRS API（WebRTC 信令） |
| 8009 | UDP | WebRTC 媒体流 |
