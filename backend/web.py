# -*- coding: utf-8 -*-
"""Phase 19 — Web 后端 (FastAPI): 摄像头 -> YOLO -> MJPEG 实时画面 + 障碍物提醒。

设计:
  - 单一 camera worker 线程: 整个进程只打开一次摄像头/源, 持续读帧 -> YOLO(Detector)
    -> 绘制 -> AlertManager.update -> 维护"最新已绘制帧" + 状态。
  - /video_feed: MJPEG 流, 从最新帧生成 JPEG (多个浏览器连接共享同一帧, 绘制只做一次)。
  - /api/status: JSON 状态 (camera/model/fps/blind_road/obstacles/alert/alert_message/tts_available)。
  - /static: 前端静态文件 (index.html / style.css / app.js)。
  - 绑定 127.0.0.1 (规格 §28, 仅本机)。
  - 复用 backend.detector 的沙箱兼容 (import 即生效) + backend.camera 的多 backend 回退。

安全边界 (Phase 19): 不重新训练 / 不改 best.pt / 不导出 / 不进下一阶段。
"""
import os
import sys
import time
import threading
from contextlib import asynccontextmanager

ROOT = r"D:\BlindRoadMonitor"
FRONTEND_DIR = os.path.join(ROOT, "frontend")
DEFAULT_MODEL = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
# 正式模型 (若上面默认路径不存在则用此)
PROD_MODEL = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")

# 全局配置 (由 scripts/run_web.py 在启动前设置)
CONFIG = {
    "source": "0",
    "model": PROD_MODEL,
    "conf": 0.20,  # Phase 16/17/18 建议的 blind_road 运行阈值 (原 0.25 漏检偏多)
    "imgsz": 640,
    "device": "0",
    "iou": 0.45,
    # Phase 21: 请求分辨率 (软设置 — 摄像头不支持则沿用其自身协商值, 不强制、不失败)。
    # 故意**不设置 FPS**: 允许摄像头自行协商帧率, 避免锁死 60FPS 导致打开失败或卡顿。
    "width": 640,
    "height": 480,
}

# 全局运行状态
state = {
    "camera": False,
    "model": False,
    "model_error": "",
    "camera_error": "",
    "fps_stream": 0.0,
    "fps_model": 0.0,
    "started_at": 0.0,
    # Phase 21: 摄像头实际协商出的分辨率 (软设置后回读, 用于排障与状态显示)
    "resolution": "",
    "camera_fps": 0.0,
}
latest_annotated = None
_latest_lock = threading.Lock()
running = threading.Event()

# 延迟初始化的组件
alert_mgr = None
_detector = None

# ---- 触发沙箱兼容 (import detector 时设置 YOLO_CONFIG_DIR / MPLCONFIGDIR / ThreadPool monkeypatch) ----
sys.path.insert(0, os.path.join(ROOT, "backend"))
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from detector import Detector  # noqa: E402  (沙箱兼容在此生效)
from camera import open_camera, list_cameras  # noqa: E402
from alert import AlertManager, OBSTACLE_NAMES  # noqa: E402

app = FastAPI(title="BlindRoadMonitor Web UI")


# ----------------------------------------------------------------------------
# camera worker
# ----------------------------------------------------------------------------
def _resolve_source(src):
    """返回 (kind, cap_or_image)。kind in {'image','video','camera'}。"""
    if isinstance(src, str):
        low = src.lower()
        if low.endswith((".jpg", ".jpeg", ".png", ".bmp", ".webp")):
            img = cv2.imread(src)
            if img is None:
                raise RuntimeError(f"无法读取图片源: {src}")
            return "image", img
        if low.endswith((".mp4", ".avi", ".mov", ".mkv", ".wmv")):
            cap = cv2.VideoCapture(src)
            if not cap.isOpened():
                raise RuntimeError(f"无法打开视频源: {src}")
            return "video", cap
    # 整数摄像头索引
    idx = int(src)
    cams = list_cameras()
    if cams and idx not in [c["index"] for c in cams]:
        print(f"[web][warn] idx {idx} 不在枚举摄像头列表 {cams} 中, 仍尝试打开")
    # Phase 21: 软请求分辨率 (摄像头不支持时保留自身默认值, 不会因此失败)
    cap = open_camera(idx, width=CONFIG.get("width"), height=CONFIG.get("height"))
    return "camera", cap


def camera_worker():
    global alert_mgr, _detector, latest_annotated
    print("[web][worker] 启动 camera worker ...")
    # 1) 加载模型
    try:
        _detector = Detector(
            weights=CONFIG["model"], device=CONFIG["device"],
            imgsz=CONFIG["imgsz"], conf=CONFIG["conf"], iou=CONFIG["iou"],
        )
        state["model"] = True
        print(f"[web][worker] 模型加载成功: {CONFIG['model']} (类数={_detector.nc})")
    except Exception as e:
        state["model"] = False
        state["model_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        print(f"[web][FATAL] 模型加载失败: {state['model_error']}")
        return  # 模型失败, 不启动摄像头

    alert_mgr = AlertManager()

    # 2) 打开源
    try:
        kind, src = _resolve_source(CONFIG["source"])
        state["camera"] = True
        # Phase 21: 回读摄像头实际协商结果 (分辨率/FPS 只记录, 不强制)
        if kind == "camera" and src is not None:
            try:
                w = int(src.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(src.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = float(src.get(cv2.CAP_PROP_FPS) or 0.0)
                state["resolution"] = f"{w}x{h}"
                state["camera_fps"] = round(fps, 1)
            except Exception:
                pass
        print(f"[web][worker] 源已打开: kind={kind} "
              f"resolution={state['resolution'] or '-'} fps={state['camera_fps'] or '-'}")
    except Exception as e:
        state["camera"] = False
        state["camera_error"] = f"{type(e).__name__}: {str(e)[:200]}"
        print(f"[web][FATAL] 摄像头/源打开失败: {state['camera_error']}")
        # 仍保持服务运行 (status 报错, video_feed 显示占位)
        return

    state["started_at"] = time.time()
    frame_count = 0
    fps_t0 = time.time()
    fps_frames = 0
    try:
        while running.is_set():
            if kind == "image":
                frame = src.copy()
                ok = True
            else:
                ok, frame = src.read()
            if not ok:
                if kind == "video":
                    # 视频循环回放, 便于无摄像头时验证
                    src.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                print("[web][worker] 帧读取失败 (源断开), 退出 worker")
                state["camera"] = False
                state["camera_error"] = "帧读取失败 (源断开)"
                break

            boxes, _ = _detector.infer(frame)
            # Phase 20: 先做空间关系判定 (AlertManager -> SpatialChecker), 再据结果绘制,
            # 使画面能体现"哪个是盲道 / 哪个障碍物疑似占用盲道"。
            status = alert_mgr.update(boxes, _detector.names)
            annotated = _detector.draw(
                frame, boxes, fps=state["fps_stream"],
                occupancy=status.get("occupancy"),
            )

            with _latest_lock:
                latest_annotated = annotated

            # stream fps (主循环帧率)
            fps_frames += 1
            if fps_frames >= 10:
                el = time.time() - fps_t0
                if el > 0:
                    state["fps_stream"] = fps_frames / el
                fps_frames = 0
                fps_t0 = time.time()
            state["fps_model"] = _detector.fps

            frame_count += 1
    except Exception as e:
        print(f"[web][worker] 运行异常: {type(e).__name__}: {e}")
        state["camera_error"] = f"{type(e).__name__}: {str(e)[:200]}"
    finally:
        if kind in ("video", "camera") and src is not None:
            try:
                src.release()
            except Exception:
                pass
        print("[web][worker] 退出")


# ----------------------------------------------------------------------------
# lifespan: 启动/停止 worker
# ----------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app):
    running.set()
    t = threading.Thread(target=camera_worker, daemon=True)
    t.start()
    yield
    running.clear()


app = FastAPI(title="BlindRoadMonitor Web UI", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


# ----------------------------------------------------------------------------
# 路由
# ----------------------------------------------------------------------------
def _placeholder_frame(text):
    """摄像头未就绪时返回占位 JPEG。"""
    img = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(img, text, (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                (0, 200, 255), 2)
    ok, jpg = cv2.imencode(".jpg", img)
    return jpg.tobytes() if ok else b""


@app.get("/")
def index():
    p = os.path.join(FRONTEND_DIR, "index.html")
    try:
        with open(p, "r", encoding="utf-8") as f:
            return HTMLResponse(f.read())
    except Exception as e:
        return HTMLResponse(f"<h1>index.html 缺失</h1><p>{e}</p>", status_code=500)


@app.get("/api/health")
def api_health():
    """Phase 21 — 存活探针: 只要 HTTP 服务本身活着就返回 200。

    与 /api/status 的区别: health **不因摄像头/模型故障而变红**, 用于
    "服务是否起来了"的判断; 子系统状态请看 /api/status。
    """
    return JSONResponse({
        "status": "ok",
        "service": "BlindRoadMonitor",
        "version": "Phase 21",
        "uptime": round(time.time() - state["started_at"], 1) if state["started_at"] else 0.0,
        "camera": state["camera"],
        "model": state["model"],
        "worker_running": running.is_set(),
    })


@app.get("/api/status")
def api_status():
    s = {
        "camera": state["camera"],
        "model": state["model"],
        "model_error": state["model_error"],
        "camera_error": state["camera_error"],
        "fps_stream": round(state["fps_stream"], 1),
        "fps_model": round(state["fps_model"], 1),
        # Phase 21: 摄像头实际协商结果 (软设置, 可能不是请求的 640x480)
        "resolution": state["resolution"],
        "camera_fps": state["camera_fps"],
        "started_at": state["started_at"],
        "uptime": round(time.time() - state["started_at"], 1) if state["started_at"] else 0.0,
        "config": {
            "source": CONFIG["source"],
            "model": CONFIG["model"],
            "imgsz": CONFIG["imgsz"],
            "conf": CONFIG["conf"],
            "device": CONFIG["device"],
            "width": CONFIG.get("width"),
            "height": CONFIG.get("height"),
        },
    }
    if alert_mgr is not None:
        s.update(alert_mgr.get_status())
    else:
        s.update({
            "alert": False, "alert_message": "", "obstacles": [],
            "obstacle_count": 0, "blind_road": False, "blind_road_count": 0,
            "tts_available": False, "tts_error": "",
            # Phase 20: 模型未就绪时前端也要能读到一致的数据结构
            "alert_level": 0, "blocking": False,
            "occupancy": {
                "status": "none", "level": 0, "blocking": False,
                "obstacles": [], "blocking_obstacles": [], "blind_rects": [],
            },
        })
    return JSONResponse(s)


@app.get("/api/obstacle_classes")
def api_obstacle_classes():
    return JSONResponse({"obstacle_classes": OBSTACLE_NAMES})


@app.get("/video_feed")
def video_feed():
    def gen():
        while True:
            with _latest_lock:
                f = latest_annotated
            if f is None:
                data = _placeholder_frame("等待摄像头/模型初始化 ...")
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + data + b"\r\n")
                time.sleep(0.2)
                continue
            ok, jpg = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                time.sleep(0.05)
                continue
            yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
            time.sleep(0.03)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    import uvicorn
    print(f"[web] 启动 http://127.0.0.1:8000  source={CONFIG['source']}")
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")
