# -*- coding: utf-8 -*-
"""Phase 19 — Web 启动入口。

启动 FastAPI (backend.web:app) 于 127.0.0.1:8000 (仅本机, 规格 §28)。
camera worker 在 app lifespan 启动时拉起 (单摄像头/源, 规格 §18)。

用法:
  # 默认: 物理/USB 摄像头 (idx 0)
  python scripts/run_web.py

  # 用测试图片循环回放 (无摄像头时验证检测+提醒逻辑)
  python scripts/run_web.py --source datasets/processed/images/test/rod_IMG_19187.jpg

  # 指定端口 / 置信度
  python scripts/run_web.py --port 8000 --conf 0.20

  # Phase 21: 指定摄像头请求分辨率 (软设置; 摄像头不支持则沿用其自身协商值)
  python scripts/run_web.py --source 0 --width 1280 --height 720

  # 也可直接用 uvicorn 模块:
  python -m uvicorn backend.web:app --host 127.0.0.1 --port 8000
"""
import os
import sys
import argparse

ROOT = r"D:\BlindRoadMonitor"
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import web  # noqa: E402  (import 即应用沙箱兼容 + 定义 CONFIG/app)


def main():
    ap = argparse.ArgumentParser(description="Phase 19 Web UI 启动")
    ap.add_argument("--source", default="0",
                    help="摄像头索引(int) / 图片路径(循环回放) / 视频文件")
    ap.add_argument("--host", default="127.0.0.1",
                    help="绑定地址 (默认 127.0.0.1, 仅本机)")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--model", default=web.PROD_MODEL,
                    help="模型权重路径 (默认 best.pt)")
    ap.add_argument("--conf", type=float, default=0.20,
                    help="置信度阈值 (默认 0.20: 兼顾 blind_road 召回与误报; 可调 0.15~0.25)")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--device", default="0")
    ap.add_argument("--iou", type=float, default=0.45)
    # Phase 21: 分辨率软设置 (默认 640x480 = 已验证配置; 不锁 FPS, 由摄像头自行协商)
    ap.add_argument("--width", type=int, default=640,
                    help="请求摄像头宽度 (软设置, 默认 640)")
    ap.add_argument("--height", type=int, default=480,
                    help="请求摄像头高度 (软设置, 默认 480)")
    args = ap.parse_args()

    # 写入全局配置, camera worker (lifespan) 启动后读取
    web.CONFIG["source"] = args.source
    web.CONFIG["model"] = args.model
    web.CONFIG["conf"] = args.conf
    web.CONFIG["imgsz"] = args.imgsz
    web.CONFIG["device"] = args.device
    web.CONFIG["iou"] = args.iou
    web.CONFIG["width"] = args.width
    web.CONFIG["height"] = args.height

    print(f"[web] 启动 http://{args.host}:{args.port}")
    print(f"[web] 源={args.source}  model={args.model}  conf={args.conf}  imgsz={args.imgsz}")
    print(f"[web] 请求分辨率={args.width}x{args.height} (软设置; 实际以 /api/status 的 resolution 为准)")
    print(f"[web] 打开浏览器访问 http://127.0.0.1:{args.port}  (退出: 在本窗口按 Ctrl+C)")

    import uvicorn
    uvicorn.run(web.app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
