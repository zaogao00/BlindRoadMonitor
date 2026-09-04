# -*- coding: utf-8 -*-
"""Phase 19 — 障碍物提醒模块 (AlertManager)。

职责:
  - 从检测框中筛选"障碍物"类别 (OBSTACLE_CLASS_INDICES, 由 data.yaml 的 26 类派生)
  - 盲道状态 (blind_road) 检测
  - 提醒冷却 (ALERT_COOLDOWN 秒, 防止逐帧刷屏)
  - 多障碍物去重 (按类别集合合成一句话)
  - 异步 TTS (独立线程 + 队列, 不阻塞检测主循环)
  - TTS 不可用时优雅降级 (保留视觉提醒, 标记 tts_available=False, 不抛异常)

安全边界 (Phase 19): 不重新训练 / 不改 best.pt / 不修改数据集。
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

        # 当前状态 (每帧更新)
        self.blind_road = False
        self.blind_road_count = 0
        self.obstacles = []          # [{'class','confidence','zh'}, ...]
        self.obstacle_count = 0
        self.alert = False
        self.alert_message = ""

        # 冷却去重
        self._last_alert_time = 0.0
        self._last_alert_key = ""
        self.speech_log = []         # 最近播报文本 (用于验证/调试, 最多 20 条)

        self._init_tts()

    # ---- TTS 初始化 (优雅降级) ----
    def _init_tts(self):
        try:
            import pyttsx3
            self._tts_engine = pyttsx3.init()
            try:
                self._tts_engine.setProperty('rate', TTS_RATE)
            except Exception:
                pass
            self.tts_available = True
            self._tts_thread = threading.Thread(target=self._tts_loop, daemon=True)
            self._tts_thread.start()
        except Exception as e:
            # 无音频设备 / 驱动异常 / 沙箱环境 -> 保留视觉提醒, 不抛错
            self.tts_available = False
            self._tts_engine = None
            self.tts_error = f"{type(e).__name__}: {str(e)[:120]}"

    def _tts_loop(self):
        while True:
            text = self._tts_queue.get()
            if text is None:
                self._tts_queue.task_done()
                break
            try:
                if self._tts_engine is not None:
                    self._tts_engine.say(text)
                    self._tts_engine.runAndWait()
            except Exception:
                pass  # TTS 失败不影响主系统
            self._tts_queue.task_done()

    # ---- 每帧更新 ----
    def update(self, boxes, names):
        """boxes: list[(x1,y1,x2,y2,cls,conf)]; names: {idx:name}。

        返回当前状态 dict (也可调用 get_status)。
        """
        blind = []
        obs = []
        for (x1, y1, x2, y2, c, cf) in boxes:
            name = names.get(c, str(c))
            if name == 'blind_road':
                blind.append(cf)
            elif c in OBSTACLE_CLASS_INDICES:
                obs.append({
                    'class': name,
                    'confidence': round(float(cf), 3),
                    'zh': ZH_NAMES.get(name, name),
                })

        with self._lock:
            self.blind_road = len(blind) > 0
            self.blind_road_count = len(blind)
            self.obstacles = obs
            self.obstacle_count = len(obs)

        now = time.time()
        if obs:
            # 视觉提醒: 始终反映"当前帧"是否有障碍物 (不受冷却影响)
            msg = self._compose(obs)
            with self._lock:
                self.alert = True
                self.alert_message = msg
            # TTS 语音: 仅在冷却窗口外触发, 防止逐帧刷屏
            with self._lock:
                can_speak = (now - self._last_alert_time) >= self.cooldown
            if can_speak:
                with self._lock:
                    self._last_alert_time = now
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
        if self.tts_available and self._tts_engine is not None:
            try:
                self._tts_queue.put(text)
            except Exception:
                pass

    def get_status(self):
        with self._lock:
            return {
                'alert': self.alert,
                'alert_message': self.alert_message,
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


# 便于外部直接引用
OBSTACLE_NAMES = [DATA_YAML_NAMES[i] for i in sorted(OBSTACLE_CLASS_INDICES)]
