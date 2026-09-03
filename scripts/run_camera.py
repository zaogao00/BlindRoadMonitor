# -*- coding: utf-8 -*-
"""Phase 17 — 实时摄像头检测主程序。

链路: 摄像头(OpenCV) -> YOLO(best.pt, GPU) -> 实时绘制 检测框 + 类别 + confidence + FPS。

复用 Phase 13/15/16 沙箱兼容 (由 backend.detector 在 import 时设置
YOLO_CONFIG_DIR / MPLCONFIGDIR / ThreadPool monkeypatch)。

安全边界 (Phase 17): 不重新训练 / 不改 best.pt / 不导出部署模型 / 不进下一阶段。

用法:
  # 摄像头实时 (有 GUI 的机器)
  python scripts/run_camera.py --source 0

  # headless 测试 (无显示器环境, 不弹窗, 跑到 max-frames 或按 Ctrl+C)
  python scripts/run_camera.py --source 0 --no-display --max-frames 120

  # 单张图片 / 目录测试 (不依赖摄像头)
  python scripts/run_camera.py --source datasets/processed/images/test/xxx.jpg --no-display --save-dir runs/.../camera_test

退出: 摄像头/视频循环内按 q / Q / ESC 退出; 异常均打印清晰信息后非 0 退出。
"""
import os
import sys
import time
import argparse

ROOT = r"D:\BlindRoadMonitor"
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from detector import Detector  # noqa: E402  (import 即应用沙箱兼容)
from camera import list_cameras, open_camera  # noqa: E402

import cv2  # noqa: E402

BEST_PT = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")

EXIT_KEYS = (ord("q"), ord("Q"), 27)  # q / Q / ESC
VIDEO_EXTS = (".mp4", ".avi", ".mov", ".mkv", ".wmv")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp")


def _process_image(det, path, save_dir):
    frame = cv2.imread(path)
    if frame is None:
        print(f"[warn] 无法读取图片: {path}")
        return None
    boxes, _ = det.infer(frame)
    out = det.draw(frame, boxes, fps=None)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
        outp = os.path.join(save_dir, "img_" + os.path.basename(path))
        cv2.imwrite(outp, out)
        print(f"[img] {os.path.basename(path)} -> {len(boxes)} 框, 存 {outp}")
    return boxes


def main():
    ap = argparse.ArgumentParser(description="Phase 17 实时摄像头检测")
    ap.add_argument("--source", default="0",
                    help="摄像头索引(整数串) / 图片 / 目录 / 视频文件")
    ap.add_argument("--model", default=BEST_PT)
    ap.add_argument("--conf", type=float, default=0.25,
                    help="置信度阈值 (blind_road 漏检偏多, 可调低如 0.15~0.20)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="0")
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--no-display", action="store_true",
                    help="无 GUI 环境用 (headless, 不弹窗)")
    ap.add_argument("--max-frames", type=int, default=0,
                    help="最大处理帧数 (0=无限, 仅摄像头/视频)")
    ap.add_argument("--save-dir", default="",
                    help="单图/截图保存目录 (摄像头用 --save-every)")
    ap.add_argument("--save-every", type=int, default=0,
                    help="摄像头模式每 N 帧存一张截图 (0=不存)")
    ap.add_argument("--width", type=int, default=0)
    ap.add_argument("--height", type=int, default=0)
    args = ap.parse_args()

    # ---- 1) 加载模型 ----
    print(f"[init] 加载模型 {args.model} device={args.device} ...")
    try:
        det = Detector(weights=args.model, device=args.device,
                       imgsz=args.imgsz, conf=args.conf, iou=args.iou)
    except FileNotFoundError as e:
        print(f"[FATAL] 模型文件不存在: {e}")
        sys.exit(2)
    except RuntimeError as e:
        print(f"[FATAL] 模型加载/设备错误: {e}")
        sys.exit(2)
    print(f"[init] 模型加载成功, 类别数={det.nc}, 设备={args.device}")

    src = args.source
    src_lower = src.lower() if isinstance(src, str) else ""

    # ---- 2) 单张图片 ----
    if src_lower.endswith(IMAGE_EXTS):
        _process_image(det, src, args.save_dir)
        cv2.destroyAllWindows()
        return

    # ---- 3) 目录 (批量图片) ----
    if isinstance(src, str) and os.path.isdir(src):
        for f in sorted(os.listdir(src)):
            if f.lower().endswith(IMAGE_EXTS):
                _process_image(det, os.path.join(src, f), args.save_dir)
        cv2.destroyAllWindows()
        return

    # ---- 4) 摄像头 / 视频文件 ----
    try:
        if src_lower.endswith(VIDEO_EXTS):
            cap = cv2.VideoCapture(src)
            src_label = f"video:{src}"
        else:
            idx = int(src)
            cams = list_cameras()
            print(f"[cam] 检测到的摄像头: {cams}")
            if cams and idx not in [c["index"] for c in cams]:
                print(f"[warn] idx {idx} 不在枚举列表中, 仍尝试打开")
            cap = open_camera(idx, width=args.width or None,
                              height=args.height or None)
            src_label = f"camera:{idx}"
    except RuntimeError as e:
        print(f"[FATAL] 摄像头打开失败: {e}")
        print("       排查: 设备是否存在 / 是否被其他程序占用 / 换 backend / 是否需 USB 摄像头")
        sys.exit(3)
    except ValueError:
        print(f"[FATAL] --source 无法解析为摄像头索引: {src}")
        sys.exit(3)

    if not cap.isOpened():
        print("[FATAL] 摄像头/视频 打开失败 (isOpened=False)")
        sys.exit(3)

    fps_cam = cap.get(cv2.CAP_PROP_FPS)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[run] {src_label} 分辨率={w}x{h} 摄像头标称fps={fps_cam:.1f} (实时) ...")
    print("      按 q / Q / ESC 退出" + (" (headless 模式: Ctrl+C 停止)" if args.no_display else ""))

    if str(args.device) != "cpu":
        torch_imported = __import__("torch")
        torch_imported.cuda.reset_peak_memory_stats()

    frame_count = 0
    start = time.time()
    saved = 0
    blind_road_hits = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[warn] 帧读取失败 (摄像头断开 / 视频 EOF)")
                break

            boxes, _ = det.infer(frame)
            if any(det.names.get(c) == "blind_road" for (_, _, _, _, c, _) in boxes):
                blind_road_hits += 1
            out = det.draw(frame, boxes, fps=det.fps)

            if args.save_dir and args.save_every and (frame_count % args.save_every == 0):
                os.makedirs(args.save_dir, exist_ok=True)
                p = os.path.join(args.save_dir, f"frame_{frame_count:06d}.jpg")
                cv2.imwrite(p, out)
                saved += 1

            if not args.no_display:
                cv2.imshow("BlindRoadMonitor", out)
                key = cv2.waitKey(1) & 0xFF
                if key in EXIT_KEYS:
                    print("[user] 退出")
                    break

            frame_count += 1
            if args.max_frames and frame_count >= args.max_frames:
                print(f"[done] 达到 --max-frames={args.max_frames}")
                break
    except KeyboardInterrupt:
        print("[user] 中断 (Ctrl+C)")
    except Exception as e:
        print(f"[FATAL] 运行异常: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cap.release()
        if not args.no_display:
            cv2.destroyAllWindows()
        el = time.time() - start
        print("=" * 60)
        if el > 0:
            print(f"[summary] 处理帧数={frame_count} 耗时={el:.1f}s 平均={frame_count / el:.1f} FPS")
        else:
            print(f"[summary] 处理帧数={frame_count}")
        print(f"[summary] 模型推理 FPS(EMA)~={det.fps:.1f}  blind_road命中帧={blind_road_hits}  存图={saved}")
        if str(args.device) != "cpu":
            peak = torch_imported.cuda.max_memory_allocated() / 1024 ** 2
            print(f"[summary] GPU 峰值显存={peak:.1f} MB ({peak / 1024:.2f} GB)")


if __name__ == "__main__":
    main()
