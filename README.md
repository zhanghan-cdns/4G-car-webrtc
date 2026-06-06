# WebRTC 视频播放器

Vue3 + SRS 实现 WebRTC 流播放

## 项目结构

```
├── webrtc-player/          # Vue3 前端项目
│   ├── src/
│   │   ├── App.vue
│   │   └── components/
│   │       └── WebRTCPlayer.vue   # 播放器组件
│   ├── package.json
│   └── vite.config.js
├── srs/                    # SRS 服务端配置
│   ├── docker-compose.yml
│   └── rtc.conf
└── README.md
```

## 快速开始

### 1. 启动 SRS 服务器

```bash
# 创建配置目录
mkdir -p /home/docker/rtc

# 将 srs/ 下两个文件放到 /home/docker/rtc/
# 然后启动
cd /home/docker/rtc
docker compose up -d
```

### 2. 推流（LubanCat / 任何 RTMP 推流端）

```bash
ffmpeg -f v4l2 -r 30 -s 3840x2160 -fflags nobuffer -flags low_delay \
  -probesize 32 -analyzeduration 0 -rtbufsize 8M \
  -i /dev/video0 \
  -c:v h264_rkmpp -profile:v high -bf 0 \
  -b:v 15000k -maxrate 18000k -bufsize 18000k \
  -g 60 -keyint_min 60 -sc_threshold 0 \
  -flags +global_header -avoid_negative_ts make_zero \
  -flvflags no_duration_filesize \
  -f flv rtmp://120.26.89.24:1935/live/cam01
```

### 3. 启动前端播放器

```bash
cd webrtc-player
npm install
npm run dev
```

浏览器打开 `http://localhost:3001`，点击 **连接**。

## 端口说明

| 端口 | 协议 | 用途 |
|------|------|------|
| 1935 | TCP | RTMP 推流 |
| 8085 | TCP | SRS 管理页面 |
| 1985 | TCP | SRS API（WebRTC 信令） |
| 8009 | UDP | WebRTC 媒体流 |

## SRS 配置说明

`rtc.conf` 关键配置项：

- `listen 8009` — WebRTC UDP 端口（与 docker 映射一致）
- `candidate 120.26.89.24` — 服务器公网 IP，必须正确填写
- `rtmp_to_rtc on` — 允许将 RTMP 推流转为 WebRTC 播放
