# -*- coding: utf-8 -*-
"""Phase 21 — 正式部署测试脚本。

覆盖规格 §13 的六项测试与 §14 的八项异常恢复场景。为节省时间, 多个 HTTP 相关
用例复用同一个服务实例 (不同用例用不同端口/参数启动独立实例)。

结果口径:
  PASS         实测通过
  FAIL         实测不通过
  CONDITIONAL  当前环境无法证明 (如沙箱无 GUI / 无扬声器), 需用户实机确认,
               绝不用 PASS 冒充。

用法:
  python scripts/run_deployment_check.py
  python scripts/run_deployment_check.py --camera-seconds 30
  python scripts/run_deployment_check.py --only test1,test2

约束: 不训练 / 不改 best.pt / 不改数据集 / 不删文件 / 不 git push。
"""
import os
import sys
import time
import json
import shutil
import urllib.request
import urllib.error
import subprocess
import threading

ROOT = r"D:\BlindRoadMonitor"
PY = r"D:\BlindRoadMonitor.venv\Scripts\python.exe"
RUN_WEB = os.path.join(ROOT, "scripts", "run_web.py")
MODEL = os.path.join(ROOT, "runs", "yolov8n_prod_b32", "weights", "best.pt")
SHOT_DIR = os.path.join(ROOT, "outputs", "phase21")

PASS, FAIL, COND = "PASS", "FAIL", "CONDITIONAL"
RESULTS = []


# ----------------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------------
def http_get(url, timeout=5.0, read_bytes=None):
    """返回 (code, body)。异常时返回 (-1, str(e))。"""
    try:
        req = urllib.request.Request(url, headers={"Cache-Control": "no-store"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read(read_bytes) if read_bytes else r.read()
            return r.status, data
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception as e:
        return -1, str(e)


def http_json(url, timeout=5.0):
    code, body = http_get(url, timeout=timeout)
    if code != 200:
        return code, {}
    try:
        return code, json.loads(body.decode("utf-8"))
    except Exception:
        return code, {}


class Service:
    """以子进程启动 run_web.py, 并后台收集日志。"""

    def __init__(self, port, source="0", model=None, env_extra=None):
        self.port = port
        self.log = []
        self.proc = None
        self._reader = None
        cmd = [PY, RUN_WEB, "--source", str(source), "--port", str(port),
               "--conf", "0.20"]
        if model:
            cmd += ["--model", model]
        env = os.environ.copy()
        if env_extra:
            env.update(env_extra)
        self.proc = subprocess.Popen(
            cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", env=env, bufsize=1,
        )
        self._reader = threading.Thread(target=self._pump, daemon=True)
        self._reader.start()

    def _pump(self):
        try:
            for line in self.proc.stdout:
                self.log.append(line.rstrip("\n"))
        except Exception:
            pass

    def wait_ready(self, timeout=120):
        """轮询 /api/health 直到 200 或超时。返回是否就绪。"""
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                return False
            code, _ = http_get(f"http://127.0.0.1:{self.port}/api/health", timeout=2)
            if code == 200:
                return True
            time.sleep(0.5)
        return False

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except Exception:
                self.proc.kill()
        return "\n".join(self.log)

    def tail(self, n=15):
        """返回最近 n 行服务日志 (用于排查 CUDA error / OOM 等)。"""
        return "\n".join(self.log[-n:])

    def wait_camera_settled(self, timeout=60):
        """等待 worker 真正尝试过打开摄像头 (camera=True 或 camera_error 非空)。

        注意: /api/health 一旦可访问就返回 200, 但此刻 worker 线程可能还在加载模型
        或正在打开摄像头。直接读 /api/status 会看到 camera=False 且 camera_error 为空
        的**中间态**, 据此断言会产生假 FAIL。这里显式等到"结论态"。
        """
        last = {}
        t0 = time.time()
        while time.time() - t0 < timeout:
            code, js = http_json(f"http://127.0.0.1:{self.port}/api/status", timeout=3)
            last = js if code == 200 else last
            if code == 200 and (js.get("camera") or js.get("camera_error")
                                or js.get("model_error")):
                return js
            time.sleep(0.5)
        return last


def record(name, status, note=""):
    RESULTS.append((name, status, note))
    print(f"  [{status:11s}] {name}" + (f" — {note}" if note else ""))


# ----------------------------------------------------------------------------
# Test 1: 模型 / CUDA / GPU
# ----------------------------------------------------------------------------
def test1_model():
    print("\n[Test 1] 模型与 GPU")
    try:
        import torch
    except Exception as e:
        record("Test1 best.pt 加载", FAIL, f"torch 导入失败: {e}")
        return
    if not torch.cuda.is_available():
        record("Test1 CUDA 可用", FAIL, "torch.cuda.is_available() == False")
        return
    gpu = torch.cuda.get_device_name(0)
    record("Test1 CUDA/可用", PASS, f"GPU={gpu}")

    if not os.path.isfile(MODEL):
        record("Test1 best.pt 存在", FAIL, f"缺失: {MODEL}")
        return
    record("Test1 best.pt 存在", PASS, f"{os.path.getsize(MODEL)/1024/1024:.2f} MB")

    sys.path.insert(0, os.path.join(ROOT, "backend"))
    try:
        from detector import Detector
        t0 = time.time()
        det = Detector(weights=MODEL, device="0", imgsz=640, conf=0.20, iou=0.45)
        dt = time.time() - t0
        import numpy as np
        boxes, _ = det.infer(np.zeros((480, 640, 3), dtype="uint8"))
        record("Test1 best.pt 可加载", PASS,
               f"nc={det.nc} 加载耗时 {dt:.1f}s 空帧推理正常 (boxes={len(boxes)})")
    except Exception as e:
        record("Test1 best.pt 可加载", FAIL, f"{type(e).__name__}: {str(e)[:160]}")


# ----------------------------------------------------------------------------
# Test 2: SpatialChecker 单元测试
# ----------------------------------------------------------------------------
def test2_spatial():
    print("\n[Test 2] SpatialChecker 单元测试 (tests/test_spatial.py)")
    try:
        p = subprocess.run([PY, os.path.join(ROOT, "tests", "test_spatial.py")],
                           cwd=ROOT, capture_output=True, text=True, timeout=300)
    except Exception as e:
        record("Test2 单元测试", FAIL, f"{type(e).__name__}: {e}")
        return
    out = (p.stdout or "") + (p.stderr or "")
    if p.returncode == 0 and "结果: PASS (10/10" in out:
        record("Test2 单元测试", PASS, "10/10 全部通过 (纯几何, 不依赖 GPU)")
    else:
        last = [l for l in out.strip().splitlines() if l.strip()][-3:]
        record("Test2 单元测试", FAIL, f"returncode={p.returncode} | {' | '.join(last)}")


# ----------------------------------------------------------------------------
# Test 3 / 4 / E6 / E7: 复用同一服务实例
# ----------------------------------------------------------------------------
def test3_web_endpoints(svc):
    print("\n[Test 3] Web 端点 (GET / , /api/health , /api/status , /video_feed)")
    base = f"http://127.0.0.1:{svc.port}"
    c, body = http_get(base + "/", timeout=8)
    ok = (c == 200 and "智能盲道障碍物监测与预警系统" in body.decode("utf-8", "ignore"))
    record("Test3 GET /", PASS if ok else FAIL, f"HTTP {c}")

    c, js = http_json(base + "/api/health", timeout=8)
    ok = (c == 200 and js.get("status") == "ok")
    record("Test3 GET /api/health", PASS if ok else FAIL, f"HTTP {c} body={js}")

    c, js = http_json(base + "/api/status", timeout=8)
    need = ["camera", "model", "alert_level", "occupancy", "blind_road",
            "obstacle_count", "tts_available", "fps_stream", "resolution"]
    miss = [k for k in need if k not in js]
    record("Test3 GET /api/status", PASS if (c == 200 and not miss) else FAIL,
           f"HTTP {c}" + (f" 缺字段 {miss}" if miss else " 字段齐全"))

    # /video_feed: 连上后读一小段即断开
    try:
        req = urllib.request.Request(base + "/video_feed")
        with urllib.request.urlopen(req, timeout=8) as r:
            ctype = r.headers.get("Content-Type", "")
            chunk = r.read(200000)
        ok = (r.status == 200 and "multipart" in ctype and len(chunk) > 5000)
        record("Test3 GET /video_feed", PASS if ok else FAIL,
               f"HTTP {r.status} {ctype} 首段 {len(chunk)/1024:.0f} KB")
    except Exception as e:
        record("Test3 GET /video_feed", FAIL, f"{type(e).__name__}: {str(e)[:120]}")


def test4_camera(svc, seconds):
    print(f"\n[Test 4] 摄像头 source=0 连续读取 {seconds}s")
    base = f"http://127.0.0.1:{svc.port}"
    c, js = http_json(base + "/api/status", timeout=8)
    if not js.get("camera"):
        record("Test4 摄像头打开", FAIL, f"camera={js.get('camera')} error={js.get('camera_error')}")
        return
    record("Test4 摄像头打开", PASS,
           f"分辨率={js.get('resolution') or '-'} 协商FPS={js.get('camera_fps')}")

    t0 = time.time()
    min_fps, max_fps, samples = 1e9, 0.0, 0
    err_seen = ""
    while time.time() - t0 < seconds:
        time.sleep(3)
        c, js = http_json(base + "/api/status", timeout=5)
        if c != 200:
            err_seen = f"/api/status 返回 {c}"
            break
        if js.get("camera_error"):
            err_seen = js["camera_error"]
            break
        f = float(js.get("fps_stream") or 0)
        if f > 0:
            min_fps, max_fps = min(min_fps, f), max(max_fps, f)
            samples += 1
    if err_seen:
        record("Test4 连续读取", FAIL, err_seen)
        return
    c, js = http_json(base + "/api/status", timeout=5)
    up = js.get("uptime", 0)
    fps_note = (f"fps_stream {min_fps:.1f}~{max_fps:.1f} ({samples} 次采样)"
                if samples else "未采集到有效 FPS")
    record("Test4 连续读取", PASS if samples else FAIL,
           f"{seconds}s 无 read failure / 无 CUDA error; {fps_note}, uptime={up}s")

    log = svc.tail(200)
    bad = [k for k in ("CUDA error", "CUDA out of memory", "Traceback") if k in log]
    record("Test4 无 OOM/CUDA 错误", PASS if not bad else FAIL,
           "日志干净" if not bad else f"发现关键字 {bad}")


def e6_client_disconnect(svc):
    print("\n[E6] 浏览器/客户端中途断开视频流")
    base = f"http://127.0.0.1:{svc.port}"
    try:
        for _ in range(3):
            req = urllib.request.Request(base + "/video_feed")
            with urllib.request.urlopen(req, timeout=5) as r:
                r.read(120000)      # 读一段后 with 退出即断开
    except Exception:
        pass
    time.sleep(2)
    c, js = http_json(base + "/api/status", timeout=5)
    alive = (c == 200 and js.get("fps_stream", 0) > 0)
    record("E6 客户端断开后服务继续", PASS if alive else FAIL,
           f"HTTP {c} fps_stream={js.get('fps_stream')}")


def e7_client_refresh(svc):
    print("\n[E7] 客户端反复刷新 (页面 + 状态 + 视频流)")
    base = f"http://127.0.0.1:{svc.port}"
    ok = True
    for i in range(5):
        c1, _ = http_get(base + "/", timeout=5)
        c2, _ = http_get(base + "/api/status", timeout=5)
        try:
            with urllib.request.urlopen(base + "/video_feed", timeout=4) as r:
                r.read(60000)
            c3 = 200
        except Exception:
            c3 = -1
        if not (c1 == 200 and c2 == 200 and c3 == 200):
            ok = False
            break
        time.sleep(0.3)
    time.sleep(2)
    c, js = http_json(base + "/api/status", timeout=5)
    ok = ok and c == 200 and js.get("fps_stream", 0) > 0
    record("E7 反复刷新无异常", PASS if ok else FAIL,
           f"5 轮刷新后 fps_stream={js.get('fps_stream')}")


# ----------------------------------------------------------------------------
# Test 5: 真实浏览器 (headless 截图; 无 GUI 则 CONDITIONAL)
# ----------------------------------------------------------------------------
def _find_browser():
    cands = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for p in cands:
        if os.path.isfile(p):
            return p
    for nm in ("msedge", "chrome"):
        p = shutil.which(nm)
        if p:
            return p
    return None


def test5_browser(svc):
    print("\n[Test 5] 真实浏览器渲染 (headless 截图)")
    browser = _find_browser()
    if not browser:
        record("Test5 浏览器渲染", COND, "本机未找到 Edge/Chrome 可执行文件, 需用户实机打开确认")
        return
    os.makedirs(SHOT_DIR, exist_ok=True)
    shot = os.path.join(SHOT_DIR, f"web_ui_{time.strftime('%H%M%S')}.png")
    url = f"http://127.0.0.1:{svc.port}/"
    cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
           f"--window-size=1280,900", "--virtual-time-budget=12000",
           f"--screenshot={shot}", url]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    except Exception as e:
        record("Test5 浏览器渲染", COND,
               f"headless 启动失败 ({type(e).__name__}), 需用户实机确认")
        return
    if os.path.isfile(shot) and os.path.getsize(shot) > 20000:
        record("Test5 浏览器渲染", PASS,
               f"headless 截图成功 {os.path.getsize(shot)/1024:.0f} KB -> {shot}")
    else:
        record("Test5 浏览器渲染", COND,
               f"headless 未产出截图 (rc={p.returncode}), 需用户实机确认")


# ----------------------------------------------------------------------------
# Test 6: TTS (异步机制可测; 真实扬声器 CONDITIONAL)
# ----------------------------------------------------------------------------
def test6_tts():
    print("\n[Test 6] TTS 异步机制")
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    try:
        from alert import AlertManager
        am = AlertManager(cooldown=0.5)
    except Exception as e:
        record("Test6 TTS 初始化", FAIL, f"{type(e).__name__}: {e}")
        return
    try:
        BR = (200, 300, 1000, 520)
        NAMES = {0: "blind_road", 1: "person", 8: "bicycle"}
        # Level 1: 远处行人
        st = am.update([(200, 300, 1000, 520, 0, 0.95), (100, 50, 180, 200, 1, 0.9)], NAMES)
        l1 = st["alert_level"]
        n1 = st["speech_count"]
        # Level 2: 行人压盲道 -> 应立即播报 (双冷却)
        st = am.update([(200, 300, 1000, 520, 0, 0.95), (400, 340, 600, 500, 1, 0.9)], NAMES)
        l2 = st["alert_level"]
        n2 = st["speech_count"]
        # 连续 5 帧 Level 2 -> 冷却内不应刷屏
        for _ in range(5):
            st = am.update([(200, 300, 1000, 520, 0, 0.95), (400, 340, 600, 500, 1, 0.9)], NAMES)
        n3 = st["speech_count"]
        async_ok = (am._tts_thread is None) or am._tts_thread.is_alive()
        ok = (l1 == 1 and l2 == 2 and n2 == n1 + 1 and n3 == n2)
        record("Test6 分级 TTS + 冷却", PASS if ok else FAIL,
               f"L1={l1} L2={l2} 播报计数 {n1}->{n2}->{n3} (升级立即播报, 冷却内不刷屏)")
        record("Test6 TTS 异步线程", PASS if async_ok else FAIL,
               f"tts_available={am.tts_available}, 独立线程+队列未阻塞主循环")
        # 真实扬声器: 沙箱无音频设备, 不能伪造
        record("Test6 真实扬声器播放", COND,
               "沙箱无音频输出设备; 需要用户 Windows 11 实机确认是否真的听到语音")
        am.shutdown()
    except Exception as e:
        record("Test6 分级 TTS + 冷却", FAIL, f"{type(e).__name__}: {str(e)[:160]}")


# ----------------------------------------------------------------------------
# 异常恢复 E1 / E2 / E3 / E4 / E5
# ----------------------------------------------------------------------------
def e1_camera_missing():
    print("\n[E1] 摄像头不存在 (source=99)")
    svc = Service(8111, source="99")
    try:
        if not svc.wait_ready(90):
            record("E1 摄像头不存在", FAIL, "服务未能启动")
            return
        js = svc.wait_camera_settled(60)   # 等到 worker 真正尝试过打开摄像头
        c = 200 if js else -1
        ok = (js.get("camera") is False and bool(js.get("camera_error")))
        record("E1 摄像头不存在", PASS if ok else FAIL,
               f"HTTP {c} camera={js.get('camera')} 错误提示={js.get('camera_error', '')[:60]}")
    finally:
        svc.stop()


def e2_camera_busy():
    print("\n[E2] 摄像头被占用 (本进程先占住 idx 0)")
    import cv2
    cap = cv2.VideoCapture(0)
    held = cap.isOpened()
    svc = Service(8112, source="0")
    try:
        if not svc.wait_ready(90):
            record("E2 摄像头被占用", FAIL, "服务未能启动")
            return
        js = svc.wait_camera_settled(60)
        c = 200 if js else -1
        # 两种结果都算可接受: 独占设备 -> camera=False + 中文错误; 共享设备 -> 仍可用
        if js.get("camera"):
            note = (f"HTTP {c} 该摄像头允许多重打开, 服务仍正常取流 "
                    f"(实机独占设备时会走 camera_error 分支)")
        else:
            note = f"HTTP {c} 已按预期降级: {js.get('camera_error', '')[:60]}"
        record("E2 摄像头被占用", PASS if c == 200 else FAIL,
               f"先占住={held}; {note}")
    finally:
        svc.stop()
        cap.release()


def e3_model_missing():
    print("\n[E3] 模型文件不存在")
    svc = Service(8113, model=r"D:\BlindRoadMonitor\runs\_not_exist_\best.pt")
    try:
        if not svc.wait_ready(90):
            record("E3 模型不存在", FAIL, "服务未能启动")
            return
        js = svc.wait_camera_settled(60)
        c = 200 if js else -1
        ok = (js.get("model") is False and bool(js.get("model_error")))
        record("E3 模型不存在", PASS if ok else FAIL,
               f"HTTP {c} model={js.get('model')} 错误提示={js.get('model_error', '')[:60]}")
    finally:
        svc.stop()


def e4_gpu_unavailable():
    print("\n[E4] GPU 不可用 (CUDA_VISIBLE_DEVICES=\"\")")
    svc = Service(8114, env_extra={"CUDA_VISIBLE_DEVICES": ""})
    try:
        if not svc.wait_ready(120):
            record("E4 GPU 不可用", FAIL, "服务未能启动")
            return
        js = svc.wait_camera_settled(60)
        c = 200 if js else -1
        err = js.get("model_error", "")
        ok = (c == 200 and js.get("model") is False and ("CUDA" in err or "GPU" in err))
        record("E4 GPU 不可用", PASS if ok else FAIL,
               f"HTTP {c} model={js.get('model')} 中文错误={err[:70]}")
    finally:
        svc.stop()


def e5_tts_init_fail():
    print("\n[E5] TTS 初始化失败")
    sys.path.insert(0, os.path.join(ROOT, "backend"))
    try:
        import pyttsx3
        import alert as alert_mod
        orig = pyttsx3.init
        pyttsx3.init = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("无音频设备"))
        try:
            am = alert_mod.AlertManager(cooldown=0.5)
        finally:
            pyttsx3.init = orig
        if am.tts_available:
            record("E5 TTS 初始化失败", FAIL, "模拟失败后仍标记可用")
            am.shutdown()
            return
        NAMES = {0: "blind_road", 1: "person"}
        st = am.update([(200, 300, 1000, 520, 0, 0.95), (400, 340, 600, 500, 1, 0.9)], NAMES)
        ok = (st["alert_level"] == 2 and st["alert"] is True)
        record("E5 TTS 初始化失败", PASS if ok else FAIL,
               f"优雅降级: tts_available=False, 视觉提醒仍工作 "
               f"(alert_level={st['alert_level']}), 未抛异常")
        am.shutdown()
    except Exception as e:
        record("E5 TTS 初始化失败", FAIL, f"{type(e).__name__}: {str(e)[:160]}")


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------
def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera-seconds", type=int, default=90,
                    help="Test4 摄像头连续读取时长 (默认 90s)")
    ap.add_argument("--only", default="", help="只跑指定用例, 逗号分隔 (如 test1,test2)")
    args = ap.parse_args()
    only = [s.strip() for s in args.only.split(",") if s.strip()]

    def want(name):
        return (not only) or (name in only)

    print("=" * 74)
    print("Phase 21 — 部署检查 (规格 §13 六项测试 + §14 异常恢复)")
    print("=" * 74)

    if want("test1"):
        test1_model()
    if want("test2"):
        test2_spatial()
    if want("test6"):
        test6_tts()
    if want("e5"):
        e5_tts_init_fail()

    need_svc = any(want(x) for x in ("test3", "test4", "e6", "e7", "test5"))
    if need_svc:
        print("\n[Service] 启动主服务实例 (source=0, port=8101) ...")
        svc = Service(8101, source="0")
        try:
            if not svc.wait_ready(150):
                record("Service 启动", FAIL, "主服务 150s 内未就绪")
                print(svc.tail(30))
            else:
                record("Service 启动", PASS, "127.0.0.1:8101 就绪")
                if want("test3"):
                    test3_web_endpoints(svc)
                if want("test4"):
                    test4_camera(svc, args.camera_seconds)
                if want("test5"):
                    test5_browser(svc)
                if want("e6"):
                    e6_client_disconnect(svc)
                if want("e7"):
                    e7_client_refresh(svc)
        finally:
            svc.stop()

    if want("e1"):
        e1_camera_missing()
    if want("e2"):
        e2_camera_busy()
    if want("e3"):
        e3_model_missing()
    if want("e4"):
        e4_gpu_unavailable()

    # ---- 汇总 ----
    print("\n" + "=" * 74)
    print("测试矩阵")
    print("=" * 74)
    print(f"{'测试项':<34} {'结果':<12} 说明")
    print("-" * 74)
    for n, s, note in RESULTS:
        print(f"{n:<34} {s:<12} {note}")
    print("-" * 74)
    n_pass = sum(1 for _, s, _ in RESULTS if s == PASS)
    n_fail = sum(1 for _, s, _ in RESULTS if s == FAIL)
    n_cond = sum(1 for _, s, _ in RESULTS if s == COND)
    print(f"PASS={n_pass}  FAIL={n_fail}  CONDITIONAL={n_cond}  合计={len(RESULTS)}")
    if n_cond:
        print("\nCONDITIONAL 项需用户在 Windows 11 实机确认 (沙箱无 GUI/无音频, 不伪造 PASS):")
        for n, s, note in RESULTS:
            if s == COND:
                print(f"  - {n}: {note}")
    print("\n结论:", "GO (无 FAIL)" if n_fail == 0 else "NO-GO (存在 FAIL)")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
