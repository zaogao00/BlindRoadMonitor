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
    args = ap.parse_args()

    # 写入全局配置, camera worker (lifespan) 启动后读取
    web.CONFIG["source"] = args.source
    web.CONFIG["model"] = args.model
    web.CONFIG["conf"] = args.conf
    web.CONFIG["imgsz"] = args.imgsz
    web.CONFIG["device"] = args.device
    web.CONFIG["iou"] = args.iou

    print(f"[web] 启动 http://{args.host}:{args.port}")
    print(f"[web] 源={args.source}  model={args.model}  conf={args.conf}  imgsz={args.imgsz}")

    import uvicorn
    uvicorn.run(web.app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
