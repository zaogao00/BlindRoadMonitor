# -*- coding: utf-8 -*-
"""Phase 19 — 障碍物提醒模块 (AlertManager)；Phase 20 在此之上叠加空间关系分级。

职责:
  - 从检测框中筛选"障碍物"类别 (OBSTACLE_CLASS_INDICES, 由 data.yaml 的 26 类派生)
  - 盲道状态 (blind_road) 检测
  - 提醒冷却 (ALERT_COOLDOWN 秒, 防止逐帧刷屏)
  - 多障碍物去重 (按类别集合合成一句话)
  - 异步 TTS (独立 worker 线程 + latest-message-wins 单槽位, 不阻塞检测主循环)
  - TTS 不可用时优雅降级 (保留视觉提醒, 标记 tts_available=False, 不抛异常)

Phase 20 新增 (复用上述全部机制, 不重写):
  - 调用 backend.spatial.classify 计算障碍物与 blind_road bbox 的空间关系
  - 三级告警: Level 0 无障碍 / Level 1 普通障碍物 / Level 2 疑似占用盲道
  - normal / blocking **两套独立冷却**, 使 Level 1→Level 2 升级能立即触发高级告警
  - 障碍物类别定义仍只有一份 (OBSTACLE_CLASS_INDICES), spatial.py 不复制

安全边界: 不重新训练 / 不改 best.pt / 不修改数据集。
"""
import os
import sys
import time
import threading

# 进程级串行锁: 用于兼容多 AlertManager 实例的测试场景。SAPI COM 同步 Speak
# 在当前 worker 线程内执行, 单实例本无并发; 多实例共存时仍用此锁串行, 避免
# 多个 SAPI voice 同时抢音频设备导致后续播报静默。
_TTS_ENGINE_LOCK = threading.Lock()

# ---- 障碍物类别定义 (由 datasets/processed/data.yaml 的 26 类派生) ----
# 排除"非实体路面/信号"类: blind_road(0) 核心目标, crosswalk(7) 地面标线,
# green_light(9) / red_light(10) 信号灯。其余均为可能对盲道通行构成实体阻挡的
# 物体/设施, 视为障碍物。后续 Phase 20 可在其上叠加"是否占用盲道"的空间关系判断。
DATA_YAML_NAMES = [
    'blind_road', 'person', 'pole', 'car', 'tree', 'motorcycle', 'warning_column',
    'crosswalk', 'bicycle', 'green_light', 'red_light', 'roadblock', 'cone', 'truck',
    'sign', 'trash_bin', 'bus', 'tricycle', 'fire_hydrant', 'dog', 'stairs', 'manhole',
    'guard_rail', 'chair', 'bench', 'plant_pot',
]
NON_OBSTACLE_INDICES = {0, 7, 9, 10}  # blind_road / crosswalk / green_light / red_light
OBSTACLE_CLASS_INDICES = set(range(len(DATA_YAML_NAMES))) - NON_OBSTACLE_INDICES

# 中文显示名 (规格 §8 允许中文)
ZH_NAMES = {
    'blind_road': '盲道', 'person': '行人', 'pole': '电线杆', 'car': '汽车', 'tree': '树木',
    'motorcycle': '摩托车', 'warning_column': '警示柱', 'crosswalk': '斑马线', 'bicycle': '自行车',
    'green_light': '绿灯', 'red_light': '红灯', 'roadblock': '路障', 'cone': '锥桶', 'truck': '卡车',
    'sign': '标志牌', 'trash_bin': '垃圾桶', 'bus': '公交车', 'tricycle': '三轮车',
    'fire_hydrant': '消防栓', 'dog': '狗', 'stairs': '楼梯', 'manhole': '井盖', 'guard_rail': '护栏',
    'chair': '椅子', 'bench': '长椅', 'plant_pot': '花盆',
}

ALERT_COOLDOWN = 2.5  # 秒 (规格 §11 建议 2~3 秒); 同时作为 blocking 默认冷却与构造参数
NORMAL_COOLDOWN = 5.0   # 普通障碍物重复播报最小间隔 (规格 §二 rule 2: 同语义至少 ~5s)
BLOCKING_COOLDOWN = 2.5 # 盲道占用 (Level 2) 更紧急, 间隔更短
STABLE_WINDOW = 0.5     # 普通障碍物组合稳定确认窗口 (规格 §五: 抑制 YOLO 逐帧抖动)
TTS_RATE = 1         # SAPI Rate: -10..10, 1 比正常略快但清晰 (pyttsx3 200 wpm 约对应 2)

# Phase 20 — 空间关系判断 (纯几何, 不复制类别列表, 只接收已筛好的 bbox)
# 兼容两种被 import 的方式: 作为 backend 包成员 (backend.alert) 或 backend 在 sys.path 上 (alert)
try:  # noqa: E402
    from .spatial import classify as _spatial_classify
except ImportError:  # noqa: E402
    from spatial import classify as _spatial_classify


class AlertManager:
    """障碍物提醒状态机。线程安全。"""

    def __init__(self, cooldown=ALERT_COOLDOWN):
        # 冷却: blocking(Level 2, 紧急) 取构造参数; normal(Level 1) 至少 NORMAL_COOLDOWN
        self.cooldown_blocking = cooldown
        self.cooldown_normal = max(cooldown, NORMAL_COOLDOWN)
        self._lock = threading.Lock()
        self._log_lock = threading.Lock()   # speech_log 专用锁 (与 _lock 分开, 避免 _mark_speech 重入死锁)
        self.tts_available = False
        self.tts_error = ""
        self._tts_thread = None
        self._tts_started = False

        # latest-message-wins 单槽位 (任意时刻最多 1 条待播; 新消息覆盖旧消息; NONE 清空)
        self._pending_text = None
        self._pending_level = 0          # 0 无 / 1 普通 / 2 占用盲道
        self._pending_event = threading.Event()
        self._shutdown = threading.Event()
        self._tts_ready = threading.Event()

        # 当前状态 (每帧更新)
        self.blind_road = False
        self.blind_road_count = 0
        self.obstacles = []          # [{'class','confidence','zh'}, ...]
        self.obstacle_count = 0
        self.alert = False
        self.alert_message = ""
        self.alert_level = 0         # Phase 20: 0 无障碍 / 1 普通 / 2 疑似占用盲道
        self.blocking = False         # Phase 20: 是否出现疑似占用盲道
        self.occupancy = {           # Phase 20: 空间关系判定结果
            "status": "none", "level": 0, "blocking": False,
            "obstacles": [], "blocking_obstacles": [], "blind_rects": [],
        }

        # 冷却去重 (Phase 20: normal / blocking 两套独立冷却, 使 Level 1->Level 2 升级能立即播报)
        self._last_tts_normal = 0.0
        self._last_tts_blocking = 0.0
        # 普通障碍物组合稳定候选 (规格 §五: 抑制 YOLO 逐帧抖动, 避免频繁切换播报)
        self._cur_normal_sig = None
        self._cur_normal_sig_since = 0.0
        self._last_normal_announced_sig = None
        self.speech_log = []         # TTS 事件日志: {"ts","text","status","err"} status∈queued/started/finished/error, 最多 20 条
        self.speech_count = 0        # 已真正放入待播槽位的播报次数

        self._init_tts()

    # ---- TTS 初始化 (优雅降级) ----
    def _init_tts(self):
        # 关键: 不在主线程创建 SAPI voice。Windows SAPI 是 COM 对象, 绑定在创建它的
        # 线程单元 (apartment) 中; 若在主线程创建而在 worker 线程调用, 会跨线程单元
        # 不匹配而静默失败 (现象: tts_available=True 但完全无声)。
        # 因此 voice 延迟到 _tts_loop worker 线程内部创建, 保证播放与 voice 同线程。
        # 调度改为 "latest-message-wins" 单槽位: 任意时刻最多只有一条待播消息,
        # 新消息覆盖旧消息, 当前画面 NONE 时清空槽位 (杜绝旧消息堆积/续播)。
        try:
            self._tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
            self._tts_thread.start()
            self._tts_started = True
            # 等待 worker 完成启动期 init probe, 使 tts_available 同步反映真实情况
            # (不要在此处乐观置 True: 否则会覆盖 probe 的失败结果)
            self._tts_ready.wait(timeout=3.0)
            if not self._tts_thread.is_alive():
                self.tts_available = False
        except Exception as e:
            # 线程无法启动等极端情况 -> 保留视觉提醒, 不抛错
            self.tts_available = False
            self._tts_started = False
            self.tts_error = f"{type(e).__name__}: {str(e)[:120]}"

    def _tts_loop(self):
        """TTS worker: 直接使用 Windows SAPI COM 同步播放, 绕过 pyttsx3 事件循环 bug。

        根因 (对应用户实测): pyttsx3 即使"持久 engine + runAndWait 正常返回",
        在 Windows 11 + Python 3.13 环境下仍会出现"首句有声、后续无声"。
        改用原生 win32com.client.Dispatch("SAPI.SpVoice").Speak(text, 0) 同步调用后,
        每一句都真正阻塞到 SAPI 完成音频输出, 首句之后不再静默。

        线程模型 (对应规格 §二/§七):
          - 仅在此 worker 线程内创建/使用 SAPI voice, 绝不跨线程;
          - worker 线程内显式 pythoncom.CoInitialize() (SAPI 是 COM 对象, 非主线程需初始化);
          - 退出时 CoUninitialize() 释放。

        调度模型 (对应规格 §1~§6, 不被本次修改破坏):
          - latest-message-wins 单槽位: 任意时刻最多 1 条待播; 新消息覆盖旧消息;
          - 当前画面 NONE 时主线程清空槽位 -> 旧等待消息被丢弃;
          - Level 2 始终优先, 不被普通消息覆盖;
          - 异常被记录 (类型/信息/文本) 并恢复, 绝不静默吞掉;
          - 异常不会杀死本线程, 也不阻塞 YOLO 主循环 / Web 服务。
        """
        import pythoncom
        try:
            import win32com.client
            _has_win32com = True
        except Exception:
            _has_win32com = False

        _com_inited = False
        voice = None
        try:
            pythoncom.CoInitialize()  # 默认 STA, SAPI 事件/同步播放需要 STA
            _com_inited = True
        except Exception as e:
            with self._lock:
                self.tts_error = f"CoInitialize failed: {type(e).__name__}: {str(e)[:120]}"
            self._tts_ready.set()
            return

        tid = threading.get_ident()
        try:
            if not _has_win32com:
                raise RuntimeError("win32com.client not available")
            # ---- worker 生命周期内只创建一个 SAPI.SpVoice, 长期复用 ----
            voice = win32com.client.Dispatch("SAPI.SpVoice")
            # SAPI Rate 范围 -10..10, 0 正常; 1 略快, 仍清晰。
            try:
                voice.Rate = TTS_RATE
            except Exception:
                pass
            try:
                voice.Volume = 100
            except Exception:
                pass
            with self._lock:
                self.tts_available = True
                self.tts_error = ""
            self._tts_ready.set()
            print(f"[TTS] worker started | thread={tid}")
            print(f"[TTS] SAPI voice initialized | thread={tid} | reused=True")

            # ---- 主循环: 复用同一 SAPI voice 消费 latest-message-wins 槽位 ----
            while True:
                if self._shutdown.is_set():
                    break
                self._pending_event.wait(timeout=0.5)
                if self._shutdown.is_set():
                    break
                with self._lock:
                    text = self._pending_text
                    level = self._pending_level
                    self._pending_text = None
                    self._pending_level = 0
                self._pending_event.clear()
                if text is None:
                    continue
                print(f"[TTS] speaking start: {text!r} | thread={tid} | pending_level={level} | engine_reused=True")
                self._mark_speech(text, "started")
                try:
                    with _TTS_ENGINE_LOCK:
                        # 0 = SVSFDefault (同步播放), 阻塞到 SAPI 真正把音频送完
                        voice.Speak(text, 0)
                    print(f"[TTS] speaking end: {text!r} | thread={tid}")
                    with self._lock:
                        self.tts_available = True
                        self.tts_error = ""
                    self._mark_speech(text, "finished")
                except Exception as e:
                    err = f"{type(e).__name__}: {str(e)[:160]}"
                    print(f"[TTS] 异常: type={type(e).__name__} msg={err} text={text!r}")
                    with self._lock:
                        self.tts_available = False
                        self.tts_error = err
                    self._mark_speech(text, "error", err)
                    # 故障恢复: 仅在本句失败后重建 voice 一次, 不"每消息 init"
                    try:
                        if voice is not None:
                            try:
                                voice.Speak("", 2)  # 2 = SVSFPurgeBeforeSpeak, 清空队列
                            except Exception:
                                pass
                        voice = win32com.client.Dispatch("SAPI.SpVoice")
                        try:
                            voice.Rate = TTS_RATE
                            voice.Volume = 100
                        except Exception:
                            pass
                        with self._lock:
                            self.tts_available = True
                            self.tts_error = ""
                        print(f"[TTS] SAPI voice re-initialized after error | thread={tid}")
                    except Exception as e2:
                        voice = None
                        with self._lock:
                            self.tts_error = f"voice re-init failed: {type(e2).__name__}: {str(e2)[:120]}"
                        print(f"[TTS] SAPI voice re-init 失败, 暂停播报: {type(e2).__name__}: {str(e2)[:120]}")
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:160]}"
            print(f"[TTS] SAPI voice 初始化失败: {err}")
            with self._lock:
                self.tts_available = False
                self.tts_error = err
            self._tts_ready.set()
        finally:
            if voice is not None:
                try:
                    voice.Speak("", 2)  # 退出前清空队列
                except Exception:
                    pass
            if _com_inited:
                try:
                    pythoncom.CoUninitialize()
                except Exception:
                    pass
            self._tts_ready.set()

    # ---- 每帧更新 ----
    def update(self, boxes, names):
        """boxes: list[(x1,y1,x2,y2,cls,conf)]; names: {idx:name}。

        复用现有 OBSTACLE_CLASS_INDICES 筛选障碍物 (不复制类别列表),
        再调用 spatial.classify 计算"是否疑似占用盲道", 最后分级告警。
        返回当前状态 dict (也可调用 get_status)。
        """
        blind_conf = []
        blind_rects = []
        obs_items = []      # 传给 SpatialChecker 的带坐标障碍物
        obs = []            # 给前端/API 的简化障碍物列表 (无几何)
        for (x1, y1, x2, y2, c, cf) in boxes:
            name = names.get(c, str(c))
            if name == 'blind_road':
                blind_conf.append(cf)
                blind_rects.append((x1, y1, x2, y2))
            elif c in OBSTACLE_CLASS_INDICES:
                zh = ZH_NAMES.get(name, name)
                obs_items.append({
                    'box': (x1, y1, x2, y2),
                    'cls': c,
                    'class': name,
                    'confidence': cf,
                    'zh': zh,
                })
                obs.append({
                    'class': name,
                    'confidence': round(float(cf), 3),
                    'zh': zh,
                })

        # ---- Phase 20: 空间关系判定 (复用现有类别定义, 不重算筛选) ----
        occupancy = _spatial_classify(blind_rects, obs_items)
        # obs 与 occupancy['obstacles'] 由同一循环构造, 索引对齐 -> 给简化列表打 blocking 标记
        for i, o in enumerate(obs):
            if i < len(occupancy["obstacles"]):
                o["blocking"] = occupancy["obstacles"][i]["blocking"]

        with self._lock:
            self.blind_road = len(blind_conf) > 0
            self.blind_road_count = len(blind_conf)
            self.obstacles = obs
            self.obstacle_count = len(obs)
            self.occupancy = occupancy
            self.alert_level = occupancy['level']
            self.blocking = occupancy['blocking']

        now = time.time()
        # 视觉提醒: 始终反映"当前帧"状态 (不受冷却影响, 规格: 升级立即可见)
        if occupancy['blocking']:
            msg = "障碍物疑似占用盲道，请注意。"
            with self._lock:
                self.alert = True
                self.alert_message = msg
                can_speak = (now - self._last_tts_blocking) >= self.cooldown_blocking
            if can_speak:
                with self._lock:
                    self._last_tts_blocking = now
                self._speak(msg, level=2)
        elif obs:
            # 视觉提醒用当前帧组合 (即时)
            visual_msg = self._compose(obs)
            # TTS 用"稳定候选组合", 抑制 YOLO 逐帧抖动 (规格 §五)
            sig = tuple(sorted(o['zh'] for o in obs))
            with self._lock:
                if self._cur_normal_sig is None:
                    self._cur_normal_sig = sig
                    self._cur_normal_sig_since = now
                elif sig != self._cur_normal_sig:
                    if (now - self._cur_normal_sig_since) >= STABLE_WINDOW:
                        self._cur_normal_sig = sig
                        self._cur_normal_sig_since = now
                    # 否则忽略短暂抖动, 维持原候选
                candidate = self._cur_normal_sig
                stable_enough = (now - self._cur_normal_sig_since) >= STABLE_WINDOW
                can_speak = (now - self._last_tts_normal) >= self.cooldown_normal
                self.alert = True
                self.alert_message = visual_msg
            if can_speak and stable_enough:
                with self._lock:
                    self._last_tts_normal = now
                self._speak(self._compose_zh(candidate), level=1)
        else:
            with self._lock:
                self.alert = False
                self.alert_message = ""
                # 当前画面无障碍 -> 清空尚未播放的旧 TTS 等待消息 (latest-wins 槽位),
                # 避免遮住摄像头后仍续播几十秒前产生的旧消息 (规格 §六 rule 3)
                if self._pending_text is not None:
                    old = self._pending_text
                    self._pending_text = None
                    self._pending_level = 0
                    self._pending_event.clear()
                    print(f"[TTS] clear stale pending messages (dropped: {old!r})")
                # 重置稳定候选, 使恢复画面后重新稳定再播报 (测试 C)
                self._cur_normal_sig = None
                self._cur_normal_sig_since = 0.0

        return self.get_status()

    @staticmethod
    def _compose(obs):
        uniq = []
        for o in obs:
            if o['zh'] not in uniq:
                uniq.append(o['zh'])
        return AlertManager._compose_zh(uniq)

    @staticmethod
    def _compose_zh(zh_list):
        uniq = list(zh_list)
        if len(uniq) == 1:
            return f"检测到{uniq[0]}，请注意。"
        if len(uniq) <= 3:
            return f"检测到{'、'.join(uniq)}，请注意。"
        return "检测到多个障碍物，请注意。"

    def _mark_speech(self, text, status, err=""):
        # 注意: 调用方可能已持有 self._lock, 因此这里用独立的 _log_lock, 绝不重入 self._lock
        with self._log_lock:
            self.speech_log.append({
                "ts": round(time.time(), 3),
                "text": text,
                "status": status,
                "err": err,
            })
            if len(self.speech_log) > 20:
                self.speech_log.pop(0)

    def _speak(self, text, level):
        """放入 latest-message-wins 单槽位 (level: 1=普通 2=占用盲道)。

        优先级规则 (规格 §2/§4/§5):
          - Level 2 始终覆盖任何 pending (包括普通消息);
          - 已有 Level 2 在等待时, 新到的普通消息被丢弃 (不被覆盖);
          - 普通消息之间: 新消息替换旧 pending (latest wins)。
        仅当消息真正进入待播槽位时计数 + 记录; 被高优先级覆盖/丢弃的不计数。
        """
        if not self._tts_started:
            with self._lock:
                self._mark_speech(text, "queued")
                self.speech_count += 1
            print(f"[TTS] enqueue (worker 未启动): {text!r} | level={level} | count={self.speech_count}")
            return
        with self._lock:
            cur = self._pending_level
            if level == 2:
                if cur == 1:
                    print("[TTS] blocking message preempt normal message")
                elif cur == 2:
                    print(f"[TTS] replace pending blocking message: {self._pending_text!r} -> {text!r}")
                self._pending_level = 2
                self._pending_text = text
                placed = True
            else:
                if cur == 2:
                    # 已有占用盲道警告在等待, 普通消息不能覆盖
                    print(f"[TTS] blocking message preempt normal message (drop normal: {text!r})")
                    placed = False
                else:
                    if cur == 1 and self._pending_text != text:
                        print(f"[TTS] replace pending normal message: {self._pending_text!r} -> {text!r}")
                    self._pending_level = 1
                    self._pending_text = text
                    placed = True
            if placed:
                self._pending_event.set()
                self.speech_count += 1
                self._mark_speech(text, "queued")
                cnt = self.speech_count
                pend = self._pending_text
        if placed:
            print(f"[TTS] enqueue: {text!r} | level={level} | pending={pend!r} | count={cnt}")

    def get_status(self):
        with self._lock:
            return {
                'alert': self.alert,
                'alert_message': self.alert_message,
                'alert_level': self.alert_level,
                'blocking': self.blocking,
                'occupancy': dict(self.occupancy),
                'obstacles': list(self.obstacles),
                'obstacle_count': self.obstacle_count,
                'blind_road': self.blind_road,
                'blind_road_count': self.blind_road_count,
                'tts_available': self.tts_available,
                'tts_error': self.tts_error,
                'tts_thread_alive': (self._tts_thread.is_alive() if self._tts_thread else False),
                'pending_message': self._pending_text,
                'pending_level': self._pending_level,
                'speech_count': self.speech_count,
                'speech_log': list(self.speech_log),
            }

    def get_speech_log(self):
        with self._lock:
            return list(self.speech_log)

    def shutdown(self):
        """停止异步 TTS 线程 (置 shutdown 标志 + 唤醒 worker, 最多等 2 秒)。可重复调用。

        注意: TTS 始终是"独立线程 + latest-message-wins 单槽位" (Phase 19 机制演进),
        此处只做优雅收尾, 不涉及同步语音, 主检测循环不会被 TTS 阻塞。
        """
        if self._tts_thread is None or not self._tts_thread.is_alive():
            return
        self._shutdown.set()
        self._pending_event.set()  # 唤醒可能在 wait 的 worker, 使其检查 shutdown
        self._tts_thread.join(timeout=2.0)


# 便于外部直接引用
OBSTACLE_NAMES = [DATA_YAML_NAMES[i] for i in sorted(OBSTACLE_CLASS_INDICES)]
