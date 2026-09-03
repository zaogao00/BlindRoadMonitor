# -*- coding: utf-8 -*-
"""Phase 17 — Camera helpers: 枚举可用摄像头, 安全打开 VideoCapture。

设计:
  - list_cameras(): 探测 0..max_idx-1 中可打开的设备, 返回 {index, width, height, fps}。
  - open_camera(): 优先默认 backend; 失败回退 CAP_DSHOW / CAP_MSMF (Windows)。
    仍失败抛出清晰 RuntimeError, 不吞异常。
"""
import cv2


def list_cameras(max_idx=6):
    """返回可打开的摄像头列表。每个元素 dict(index, width, height, fps)。"""
    found = []
    for i in range(max_idx):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fps = cap.get(cv2.CAP_PROP_FPS)
            found.append(dict(index=i, width=w, height=h, fps=fps))
            cap.release()
    return found


def open_camera(index=0, backend=None, width=None, height=None):
    """打开指定摄像头索引。失败回退多 backend; 全部失败抛 RuntimeError。

    backend: 可选 cv2.CAP_DSHOW / cv2.CAP_MSMF 等; 默认 None (自动)。
    """
    if backend is not None:
        cap = cv2.VideoCapture(index, backend)
    else:
        cap = cv2.VideoCapture(index)

    if not cap.isOpened():
        # 回退尝试常用 backend (Windows 下 MSMF 默认可能异常, DSHOW 更稳)
        for b in (cv2.CAP_DSHOW, cv2.CAP_MSMF):
            try:
                cap = cv2.VideoCapture(index, b)
            except Exception:
                continue
            if cap.isOpened():
                break
        else:
            cap.release()
            raise RuntimeError(
                f"无法打开摄像头 idx={index} (设备不存在 / 被其他程序占用 / backend 不支持)"
            )

    if width:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    if height:
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap
