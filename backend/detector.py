# -*- coding: utf-8 -*-
"""Phase 17 — Detector: 加载 best.pt, 对单帧做 YOLO 推理并绘制检测框 (OpenCV)。

复用 Phase 13/15/16 已验证的沙箱兼容方案:
  - YOLO_CONFIG_DIR / MPLCONFIGDIR 重定向 (避免字体/matplotlib 缓存写入失败)
  - monkeypatch ultralytics ThreadPool 为纯线程池 (命名管道被沙箱拒)
  - 推理用 workers=0 ( Windows spawn + 沙箱限制 )

安全边界 (Phase 17): 不重新训练 / 不修改 best.pt / 不导出 / 不进下一阶段。
"""
import os
import sys
import time
import threading

ROOT = r"D:\BlindRoadMonitor"

# ---- 沙箱兼容 (同 Phase 13/14/15/16) ----
os.environ["YOLO_CONFIG_DIR"] = os.path.join(ROOT, ".yolo_config")
os.environ["MPLCONFIGDIR"] = os.path.join(ROOT, ".yolo_config", "mpl")
os.makedirs(os.environ["MPLCONFIGDIR"], exist_ok=True)

import ultralytics.data.dataset as _uds
from concurrent.futures import ThreadPoolExecutor


class _NoPipeThreadPool:
    """纯线程池替换 ultralytics 的 ThreadPool (命名管道被沙箱拒)。仅影响缓存扫描。"""

    def __init__(self, max_workers=None):
        self._ex = ThreadPoolExecutor(max_workers=max_workers or 1)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self._ex.shutdown(wait=True)
        return False

    def imap(self, func, iterable):
        futs = [self._ex.submit(func, item) for item in iterable]
        for f in futs:
            yield f.result()


_uds.ThreadPool = _NoPipeThreadPool

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from ultralytics import YOLO  # noqa: E402


class Detector:
    """封装 YOLOv8 推理与绘制。线程安全 (FPS 用锁保护)。"""

    def __init__(self, weights, device="0", imgsz=640, conf=0.25, iou=0.45):
        if not os.path.isfile(weights):
            raise FileNotFoundError(f"模型文件不存在: {weights}")
        self.weights = weights
        self.device = device
        self.imgsz = imgsz
        self.conf = conf
        self.iou = iou

        # 设备可用性检查
        if str(device) != "cpu" and not torch.cuda.is_available():
            raise RuntimeError(f"CUDA 不可用, 无法使用 GPU 推理 (device={device})")

        try:
            self.model = YOLO(weights)
        except Exception as e:
            raise RuntimeError(f"模型加载失败: {e}") from e

        self.names = self.model.names  # {idx: name}
        self.nc = len(self.names)

        # warmup: 用一张合成帧触发首次编译 + 缓存扫描 (ThreadPool monkeypatch 生效)
        try:
            self.model.predict(
                source=np.zeros((imgsz, imgsz, 3), dtype=np.uint8),
                imgsz=imgsz, conf=conf, iou=iou, device=device, verbose=False,
            )
        except Exception:
            pass

        self._fps = 0.0
        self._lock = threading.Lock()

    def infer(self, frame):
        """对 BGR 帧推理, 返回 (boxes, frame)。

        boxes: list of (x1, y1, x2, y2, cls, conf)
        内部更新 EMA 推理 FPS。
        """
        if frame is None:
            return [], frame
        t0 = time.time()
        try:
            res = self.model.predict(
                source=frame, imgsz=self.imgsz, conf=self.conf,
                iou=self.iou, device=self.device, verbose=False,
            )
        except Exception as e:
            raise RuntimeError(f"GPU 推理失败: {e}") from e

        boxes = []
        if res and res[0].boxes is not None and len(res[0].boxes) > 0:
            for b, c, cf in zip(
                res[0].boxes.xyxy.tolist(),
                res[0].boxes.cls.tolist(),
                res[0].boxes.conf.tolist(),
            ):
                boxes.append(
                    (float(b[0]), float(b[1]), float(b[2]), float(b[3]),
                     int(c), float(cf))
                )

        dt = time.time() - t0
        inst = (1.0 / dt) if dt > 0 else 0.0
        with self._lock:
            self._fps = 0.9 * self._fps + 0.1 * inst if self._fps else inst
        return boxes, frame

    def draw(self, frame, boxes, fps=None, occupancy=None):
        """在副本上绘制检测框 + 类别 + confidence (+可选 FPS)。

        Phase 20: occupancy 不为 None 时, 改由 backend.spatial.draw_occupancy 绘制,
        以便体现空间关系 (盲道橙框保留 / 疑似占用盲道的障碍物红框 + "占用盲道?")。
        occupancy=None 时行为与 Phase 17/18/19 完全一致 (向后兼容)。
        """
        out = frame.copy()
        if occupancy is not None:
            # 由空间关系层统一绘制 (原地), 避免与下方循环重复叠加标签
            from spatial import draw_occupancy
            draw_occupancy(out, occupancy)
            if fps is not None:
                cv2.putText(
                    out, f"FPS: {fps:.1f}", (10, 26),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2,
                )
            return out

        for (x1, y1, x2, y2, cls, conf) in boxes:
            name = self.names.get(cls, str(cls))
            # blind_road 主任务用醒目橙色, 其余绿色
            color = (0, 200, 255) if name == "blind_road" else (0, 255, 0)
            cv2.rectangle(out, (int(x1), int(y1)), (int(x2), int(y2)), color, 2)
            label = f"{name} {conf:.2f}"
            cv2.putText(
                out, label, (int(x1), max(12, int(y1) - 6)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
            )
        if fps is not None:
            cv2.putText(
                out, f"FPS: {fps:.1f}", (10, 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2,
            )
        return out

    @property
    def fps(self):
        with self._lock:
            return self._fps
