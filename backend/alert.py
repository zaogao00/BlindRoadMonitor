# -*- coding: utf-8 -*-
"""Phase 19 — 障碍物提醒模块 (AlertManager)；Phase 20 在此之上叠加空间关系分级。

职责:
  - 从检测框中筛选"障碍物"类别 (OBSTACLE_CLASS_INDICES, 由 data.yaml 的 26 类派生)
  - 盲道状态 (blind_road) 检测
  - 提醒冷却 (ALERT_COOLDOWN 秒, 防止逐帧刷屏)
  - 多障碍物去重 (按类别集合合成一句话)
  - 异步 TTS (独立线程 + 队列, 不阻塞检测主循环)
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
import queue

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

ALERT_COOLDOWN = 2.5  # 秒 (规格 §11 建议 2~3 秒)
TTS_RATE = 160       # 语速 (Windows SAPI, 默认 200, 略降更清晰)

# Phase 20 — 空间关系判断 (纯几何, 不复制类别列表, 只接收已筛好的 bbox)
# 兼容两种被 import 的方式: 作为 backend 包成员 (backend.alert) 或 backend 在 sys.path 上 (alert)
try:  # noqa: E402
    from .spatial import classify as _spatial_classify
except ImportError:  # noqa: E402
    from spatial import classify as _spatial_classify


class AlertManager:
    """障碍物提醒状态机。线程安全。"""

    def __init__(self, cooldown=ALERT_COOLDOWN):
        self.cooldown = cooldown
        self._lock = threading.Lock()
        self.tts_available = False
        self.tts_error = ""
        self._tts_engine = None
        self._tts_queue = queue.Queue()
        self._tts_thread = None
        self._tts_started = False

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

        # 冷却去重 (Phase 19: 单一冷却; Phase 20: 区分 normal / blocking 两套冷却,
        # 使 Level 2 高级告警不被 Level 1 普通告警的冷却阻塞, 规格 §十六)
        self._last_tts_normal = 0.0
        self._last_tts_blocking = 0.0
        self.speech_log = []         # 最近播报文本 (用于验证/调试, 最多 20 条)

        self._init_tts()

    # ---- TTS 初始化 (优雅降级) ----
    def _init_tts(self):
        # 关键: 不在主线程创建 pyttsx3 引擎。Windows SAPI 是 COM 对象, 绑定在创建它的
        # 线程单元 (apartment) 中; 若在主线程 init() 而在 worker 线程 runAndWait(), 会跨
        # 线程单元不匹配而静默失败 (现象: tts_available=True 但完全无声)。
        # 因此引擎延迟到 _tts_loop worker 线程内部创建, 保证 say/runAndWait 与引擎同线程。
        try:
            self._tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
            self._tts_thread.start()
            self._tts_started = True
            self.tts_available = True  # 子系统已启动; 引擎就绪情况由 worker 线程回报
        except Exception as e:
            # 线程无法启动等极端情况 -> 保留视觉提醒, 不抛错
            self.tts_available = False
            self._tts_engine = None
            self._tts_started = False
            self.tts_error = f"{type(e).__name__}: {str(e)[:120]}"

    def _tts_loop(self):
        import pyttsx3
        engine = None
        try:
            # 在 worker 线程内初始化引擎, 避免跨线程 COM 单元不匹配导致无声
            engine = pyttsx3.init()
            try:
                engine.setProperty('rate', TTS_RATE)
            except Exception:
                pass
            with self._lock:
                self._tts_engine = engine
                self.tts_available = True
        except Exception as e:
            with self._lock:
                self.tts_available = False
                self.tts_error = f"{type(e).__name__}: {str(e)[:120]}"
        while True:
            text = self._tts_queue.get()
            if text is None:
                self._tts_queue.task_done()
                break
            eng = self._tts_engine
            try:
                if eng is not None:
                    eng.say(text)
                    eng.runAndWait()
            except Exception:
                pass  # TTS 失败不影响主系统
            self._tts_queue.task_done()

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
        # 视觉提醒: 始终反映"当前帧"状态 (不受冷却影响, 规格 §十六: 升级立即可见)
        if occupancy['blocking']:
            msg = "障碍物疑似占用盲道，请注意。"
            with self._lock:
                self.alert = True
                self.alert_message = msg
            # TTS (blocking 冷却): Level 2 不被 Level 1 冷却阻塞
            with self._lock:
                can_speak = (now - self._last_tts_blocking) >= self.cooldown
            if can_speak:
                with self._lock:
                    self._last_tts_blocking = now
                self._speak(msg)
        elif obs:
            msg = self._compose(obs)
            with self._lock:
                self.alert = True
                self.alert_message = msg
            # TTS (normal 冷却)
            with self._lock:
                can_speak = (now - self._last_tts_normal) >= self.cooldown
            if can_speak:
                with self._lock:
                    self._last_tts_normal = now
                self._speak(msg)
        else:
            with self._lock:
                self.alert = False
                self.alert_message = ""

        return self.get_status()

    @staticmethod
    def _compose(obs):
        uniq = []
        for o in obs:
            if o['zh'] not in uniq:
                uniq.append(o['zh'])
        if len(uniq) == 1:
            return f"检测到{uniq[0]}，请注意。"
        if len(uniq) <= 3:
            return f"检测到{'、'.join(uniq)}，请注意。"
        return "检测到多个障碍物，请注意。"

    def _speak(self, text):
        with self._lock:
            self.speech_log.append(text)
            if len(self.speech_log) > 20:
                self.speech_log.pop(0)
        if self._tts_started:
            try:
                self._tts_queue.put(text)
            except Exception:
                pass

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
                'speech_count': len(self.speech_log),
            }

    def get_speech_log(self):
        with self._lock:
            return list(self.speech_log)

    def shutdown(self):
        """停止异步 TTS 线程 (发送哨兵 None, 最多等 2 秒)。可重复调用。

        注意: TTS 始终是"独立线程 + 队列" (Phase 19 机制), 此处只做优雅收尾,
        不涉及同步语音, 主检测循环不会被 TTS 阻塞。
        """
        if self._tts_thread is None or not self._tts_thread.is_alive():
            return
        try:
            self._tts_queue.put(None)
        except Exception:
            return
        self._tts_thread.join(timeout=2.0)


# 便于外部直接引用
OBSTACLE_NAMES = [DATA_YAML_NAMES[i] for i in sorted(OBSTACLE_CLASS_INDICES)]
