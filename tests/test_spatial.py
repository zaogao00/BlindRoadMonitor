# -*- coding: utf-8 -*-
"""Phase 20 — SpatialChecker 单元测试。

约束 (规格 §三十二 / §三十三):
  - **不加载 YOLO, 不依赖 GPU** (只用人工构造的 bbox, 秒级完成)
  - 只测几何计算与规则判断, 不触碰模型/数据集/best.pt
  - 同时覆盖 AlertManager 的分级告警与双冷却 (AlertManager 本身不加载模型)

运行:
  D:\\BlindRoadMonitor.venv\\Scripts\\python.exe tests\\test_spatial.py
  (也兼容 pytest: 每个 test_* 函数可单独被收集)
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

from spatial import (  # noqa: E402
    compute_iou, is_center_inside, obstacle_overlap_ratio,
    classify, IOU_THRESHOLD, OVERLAP_THRESHOLD, CENTER_MIN_OVERLAP,
)

# ----------------------------------------------------------------------------
# 人工场景 (图像假定 1280x720)
# ----------------------------------------------------------------------------
BR = (200, 300, 1000, 520)          # 典型盲道 bbox (宽条形)
BR_THIN = (200, 300, 1000, 340)     # 细长盲道 bbox (远透视/窄视角)
BR_SMALL = (300, 400, 500, 500)     # 小盲道框 (远处/窄视角), 面积仅 20000


def _obs(box, cls=1, name="person", zh="行人", conf=0.90):
    return {"box": box, "cls": cls, "class": name, "confidence": conf, "zh": zh}


# expect: 'yes' 应判疑似占用 / 'no' 不应判 / 'edge' 阈值敏感边界 (只记录不判对错)
SCENARIOS = [
    {"name": "A 无盲道无障碍物", "blind": [], "obs": [], "expect": "no"},
    {"name": "B 只有盲道", "blind": [BR], "obs": [], "expect": "no"},
    {"name": "C 盲道+远离障碍物", "blind": [BR],
     "obs": [_obs((100, 50, 180, 200))], "expect": "no"},
    {"name": "D 盲道+明显覆盖", "blind": [BR],
     "obs": [_obs((400, 340, 600, 500))], "expect": "yes"},
    {"name": "E1 仅小角擦到(7%)", "blind": [BR],
     "obs": [_obs((980, 240, 1120, 360))], "expect": "no"},
    {"name": "E2 边缘交叠约10%", "blind": [BR],
     "obs": [_obs((988, 300, 1108, 420))], "expect": "edge"},
    {"name": "E3 边缘交叠约25%", "blind": [BR],
     "obs": [_obs((970, 300, 1090, 420))], "expect": "edge"},
    {"name": "E4 大物体骑细盲道(中心在内)", "blind": [BR_THIN],
     "obs": [_obs((400, 150, 700, 500), name="car", zh="汽车")], "expect": "yes"},
    {"name": "F1 多障碍-person(远)", "blind": [BR],
     "obs": [_obs((100, 50, 180, 200))], "expect": "no"},
    {"name": "F2 多障碍-bicycle(压盲道)", "blind": [BR],
     "obs": [_obs((420, 350, 620, 510), cls=8, name="bicycle", zh="自行车")],
     "expect": "yes"},
    {"name": "F3 多障碍-car(远)", "blind": [BR],
     "obs": [_obs((1050, 80, 1250, 260), cls=3, name="car", zh="汽车")],
     "expect": "no"},
    {"name": "G1 误报测试-盲道旁边", "blind": [BR],
     "obs": [_obs((1010, 290, 1150, 430))], "expect": "no"},
    {"name": "G2 误报测试-仅贴边(零交叠)", "blind": [BR],
     "obs": [_obs((1000, 300, 1140, 420))], "expect": "no"},
    {"name": "H 漏报测试-细长杆压盲道", "blind": [BR],
     "obs": [_obs((480, 310, 520, 510), cls=2, name="pole", zh="电线杆")],
     "expect": "yes"},
    # 关键: 盲道框很小 + 大物体压住其大部分 —— 此时 IoU 高 (0.143) 但
    # 障碍物自身交叠比例低 (0.167), 中心也在盲道框外 -> **只有条件 A 能命中**。
    # 该场景用于证明 IoU 条件不是"死代码", 并让阈值扫描真正区分 IoU=0.10 与 0.15。
    {"name": "I 小盲道框-大物体压住(IoU决定)", "blind": [BR_SMALL],
     "obs": [_obs((400, 400, 700, 600), cls=3, name="car", zh="汽车")],
     "expect": "yes"},
]


# ----------------------------------------------------------------------------
# 1. 基础几何
# ----------------------------------------------------------------------------
def test_geometry_iou():
    assert abs(compute_iou((0, 0, 100, 100), (0, 0, 100, 100)) - 1.0) < 1e-9
    assert compute_iou((0, 0, 100, 100), (200, 200, 300, 300)) == 0.0
    # 半重叠: inter 50x100=5000, union 5000+5000+5000... -> 10000+10000-5000=15000
    v = compute_iou((0, 0, 100, 100), (50, 0, 150, 100))
    assert abs(v - 5000.0 / 15000.0) < 1e-9, v
    # 完全包含: 小框在大框内 -> IoU = 小/大
    v = compute_iou((0, 0, 50, 50), (0, 0, 100, 100))
    assert abs(v - 0.25) < 1e-9, v
    print("  [OK] compute_iou: 相同=1.0 / 相离=0.0 / 半叠=0.333 / 包含=0.25")


def test_geometry_center_inside():
    assert is_center_inside((200, 150, 300, 250), (100, 100, 500, 300)) is True
    assert is_center_inside((600, 400, 700, 500), (100, 100, 500, 300)) is False
    # 边界: 中心正好落在盲道边框上 -> 视为在内 (>= 比较)
    assert is_center_inside((100, 200, 300, 400), (200, 100, 400, 300)) is True
    print("  [OK] is_center_inside: 内/外/边界 均正确")


def test_geometry_overlap_ratio():
    # 障碍物完全落在盲道内 -> 1.0
    assert abs(obstacle_overlap_ratio((200, 150, 300, 250), (100, 100, 500, 300)) - 1.0) < 1e-9
    # 相离 -> 0.0
    assert obstacle_overlap_ratio((600, 400, 700, 500), (100, 100, 500, 300)) == 0.0
    # 一半落入 -> 0.5 (obstacle 100x100, inter 50x100)
    v = obstacle_overlap_ratio((50, 0, 150, 100), (0, 0, 100, 100))
    assert abs(v - 0.5) < 1e-9, v
    print("  [OK] obstacle_overlap_ratio: 全落=1.0 / 相离=0.0 / 半落=0.5")


# ----------------------------------------------------------------------------
# 2. 场景分类 (默认阈值)
# ----------------------------------------------------------------------------
def test_scenarios_default_thresholds():
    fails = []
    rows = []
    for sc in SCENARIOS:
        occ = classify(sc["blind"], sc["obs"])
        got = "yes" if occ["blocking"] else "no"
        o = occ["obstacles"][0] if occ["obstacles"] else {}
        rows.append((sc["name"], sc["expect"], got, occ["level"],
                     o.get("iou", 0.0), o.get("overlap_ratio", 0.0),
                     o.get("center_inside", False)))
        if sc["expect"] in ("yes", "no") and got != sc["expect"]:
            fails.append(f"{sc['name']}: 期望 {sc['expect']} 实得 {got}")

    print("  --- 默认阈值 (IoU>=%.2f, overlap>=%.2f) 场景矩阵 ---"
          % (IOU_THRESHOLD, OVERLAP_THRESHOLD))
    print("  %-30s %-6s %-6s %-5s %-7s %-7s %s" %
          ("场景", "期望", "实得", "等级", "IoU", "交叠", "中心在内"))
    for n, e, g, lv, iou, ovr, ctr in rows:
        flag = "OK" if (e == "edge" or e == g) else "FAIL"
        print("  %-30s %-6s %-6s %-5d %-7.3f %-7.3f %-5s %s"
              % (n, e, g, lv, iou, ovr, ctr, flag))
    assert not fails, "场景判定不符: " + "; ".join(fails)
    print("  [OK] A/B/C/D/E1/E4/F/G/H 全部符合预期 (E2/E3 为边界场景, 仅记录)")


def test_no_blind_road_never_blocking():
    """未检出盲道时不得判定"疑似占用" (无参照物, 只能降级为普通障碍物)。"""
    occ = classify([], [_obs((400, 340, 600, 500))])
    assert occ["status"] == "normal" and occ["level"] == 1 and occ["blocking"] is False
    print("  [OK] 无盲道框 -> 最高只能 Level 1 (不臆造占用判断)")


def test_multi_obstacle_grading():
    """场景 F: person/car 普通, bicycle 疑似占用 -> 能逐个区分且整体 Level 2。"""
    obs = [
        _obs((100, 50, 180, 200)),                                 # person 远
        _obs((420, 350, 620, 510), cls=8, name="bicycle", zh="自行车"),
        _obs((1050, 80, 1250, 260), cls=3, name="car", zh="汽车"),
    ]
    occ = classify([BR], obs)
    assert occ["level"] == 2 and occ["blocking"] is True
    flags = [o["blocking"] for o in occ["obstacles"]]
    assert flags == [False, True, False], flags
    assert len(occ["blocking_obstacles"]) == 1
    assert occ["blocking_obstacles"][0]["class"] == "bicycle"
    print("  [OK] 多障碍物分级: person=普通 / bicycle=疑似占用 / car=普通, 整体 Level 2")


# ----------------------------------------------------------------------------
# 3. 阈值扫描 (规格 §三十: 必须比较 IoU 0.05/0.10/0.15 × overlap 0.10/0.20/0.30)
# ----------------------------------------------------------------------------
def threshold_scan():
    print("\n  --- 阈值扫描 (误报 FP = 期望no却判yes; 漏报 FN = 期望yes却判no) ---")
    print("  %-6s %-6s %-5s %-5s %s" % ("IoU", "交叠", "FP", "FN", "边界场景 (E2/E3)"))
    results = {}
    for iou_th in (0.05, 0.10, 0.15):
        for ov_th in (0.10, 0.20, 0.30):
            fp = fn = 0
            edge = {}
            for sc in SCENARIOS:
                occ = classify(sc["blind"], sc["obs"], iou_th=iou_th, overlap_th=ov_th)
                got = occ["blocking"]
                if sc["expect"] == "no" and got:
                    fp += 1
                elif sc["expect"] == "yes" and not got:
                    fn += 1
                elif sc["expect"] == "edge":
                    edge[sc["name"].split()[0]] = "yes" if got else "no"
            results[(iou_th, ov_th)] = (fp, fn)
            print("  %-6.2f %-6.2f %-5d %-5d %s" % (iou_th, ov_th, fp, fn, edge))
    return results


def test_threshold_choice():
    results = threshold_scan()
    fp, fn = results[(IOU_THRESHOLD, OVERLAP_THRESHOLD)]
    assert fp == 0, f"选定阈值存在误报: FP={fp}"
    assert fn == 0, f"选定阈值存在漏报: FN={fn}"
    # IoU 阈值在本场景集上不起决定作用 (盲道 bbox 面积远大于障碍物, IoU 天然偏小),
    # 这正印证规格 §八"不要只依赖 IoU"。此处只断言"存在无 FP/FN 的组合", 不硬编码。
    best = [k for k, v in results.items() if v == (0, 0)]
    assert best, "没有任何阈值组合能做到零误报零漏报"
    print("  [OK] 选定组合 IoU>=%.2f / 交叠>=%.2f: FP=%d FN=%d (零误报零漏报)"
          % (IOU_THRESHOLD, OVERLAP_THRESHOLD, fp, fn))
    print("  [INFO] 同样零 FP/FN 的组合: %s" % (best,))
    print("  [INFO] IoU=0.15 会在场景 I (小盲道框+大物体压住) 漏报 -> IoU 上限定为 0.10")
    print("  [INFO] 交叠 0.20 与 0.30 均可, 选 0.20: 安全类产品漏报代价 > 误报代价")


# ----------------------------------------------------------------------------
# 4. AlertManager 分级告警集成 (不加载 YOLO, 复用现有异步 TTS 线程/队列)
# ----------------------------------------------------------------------------
def _boxes_from(blind, obs_raw):
    """构造 AlertManager.update 所需的 (x1,y1,x2,y2,cls,conf) 列表。"""
    out = []
    for b in blind:
        out.append((float(b[0]), float(b[1]), float(b[2]), float(b[3]), 0, 0.95))
    for cls, box in obs_raw:
        out.append((float(box[0]), float(box[1]), float(box[2]),
                    float(box[3]), cls, 0.90))
    return out


NAMES = {
    0: 'blind_road', 1: 'person', 2: 'pole', 3: 'car', 8: 'bicycle',
}


def test_alert_manager_levels_and_escalation():
    from alert import AlertManager

    am = AlertManager(cooldown=0.5)  # 缩短冷却以便快速测试
    try:
        # Level 0
        st = am.update([], NAMES)
        assert st["alert_level"] == 0 and st["alert"] is False

        # Level 1: 盲道 + 远处行人
        st = am.update(_boxes_from([BR], [(1, (100, 50, 180, 200))]), NAMES)
        assert st["alert_level"] == 1 and st["blocking"] is False
        assert st["alert"] is True and "行人" in st["alert_message"], st["alert_message"]
        n1 = st["speech_count"]

        # Level 1 -> Level 2 升级: 必须**立即**触发高级告警 (不被 Level 1 冷却阻塞)
        st = am.update(_boxes_from([BR], [(1, (400, 340, 600, 500))]), NAMES)
        assert st["alert_level"] == 2 and st["blocking"] is True
        assert "疑似占用盲道" in st["alert_message"], st["alert_message"]
        assert st["occupancy"]["status"] == "suspected"
        assert st["speech_count"] == n1 + 1, "Level1->Level2 升级未立即播报"

        # Level 2 冷却内持续存在 -> 不再刷屏
        for _ in range(5):
            st = am.update(_boxes_from([BR], [(1, (400, 340, 600, 500))]), NAMES)
        assert st["speech_count"] == n1 + 1, "Level 2 冷却失效 (刷屏)"

        # 障碍物消失 -> 回到 Level 0, 视觉提醒关闭
        st = am.update(_boxes_from([BR], []), NAMES)
        assert st["alert_level"] == 0 and st["alert"] is False

        # API 结构完整性 (规格 §十九)
        for k in ("occupancy", "alert_level", "blocking", "alert_message",
                  "obstacles", "obstacle_count", "blind_road", "tts_available"):
            assert k in st, f"/api/status 缺字段 {k}"
        occ = st["occupancy"]
        for k in ("status", "level", "blocking", "obstacles",
                  "blocking_obstacles", "blind_rects"):
            assert k in occ, f"occupancy 缺字段 {k}"

        print("  [OK] AlertManager: L0/L1/L2 分级 + L1->L2 立即升级 + 冷却防刷屏 + API 字段完整")
        print("  [OK] TTS 线程: tts_available=%s (沙箱无音频时优雅降级, 仍为异步队列)"
              % st["tts_available"])
    finally:
        am.shutdown()


def test_alert_manager_blocking_obstacle_detail():
    from alert import AlertManager
    am = AlertManager(cooldown=0.5)
    try:
        st = am.update(_boxes_from([BR], [(8, (420, 350, 620, 510))]), NAMES)
        bo = st["occupancy"]["blocking_obstacles"]
        assert len(bo) == 1 and bo[0]["class"] == "bicycle"
        for k in ("iou", "overlap_ratio", "center_inside", "confidence", "zh"):
            assert k in bo[0], f"blocking_obstacles 缺字段 {k}"
        print("  [OK] blocking_obstacles 含 iou/overlap_ratio/center_inside (前端可解释)")
    finally:
        am.shutdown()


# ----------------------------------------------------------------------------
# 5. 性能: SpatialChecker 必须极轻量 (规格 §二十六)
# ----------------------------------------------------------------------------
def test_spatial_performance():
    blind = [BR, BR_THIN]
    obs = [_obs((400 + i, 340, 600 + i, 500)) for i in range(20)]
    t0 = time.perf_counter()
    n = 2000
    for _ in range(n):
        classify(blind, obs)
    dt = time.perf_counter() - t0
    per_call_ms = dt / n * 1000.0
    # 单帧预算以 30FPS = 33.3ms 计, 空间计算应 < 1ms
    assert per_call_ms < 1.0, f"SpatialChecker 过重: {per_call_ms:.3f} ms/帧"
    print("  [OK] SpatialChecker 开销 %.4f ms/帧 (2 盲道框 x 20 障碍物, 远低于 33ms 预算)"
          % per_call_ms)


def main():
    print("=" * 72)
    print("Phase 20 — SpatialChecker 单元测试 (纯几何, 不加载 YOLO / 不依赖 GPU)")
    print("默认阈值: IoU>=%.2f, 交叠>=%.2f, 中心判定最小交叠=%.2f"
          % (IOU_THRESHOLD, OVERLAP_THRESHOLD, CENTER_MIN_OVERLAP))
    print("=" * 72)
    tests = [
        test_geometry_iou,
        test_geometry_center_inside,
        test_geometry_overlap_ratio,
        test_scenarios_default_thresholds,
        test_no_blind_road_never_blocking,
        test_multi_obstacle_grading,
        test_threshold_choice,
        test_alert_manager_levels_and_escalation,
        test_alert_manager_blocking_obstacle_detail,
        test_spatial_performance,
    ]
    failed = []
    for t in tests:
        print("\n[%s]" % t.__name__)
        try:
            t()
        except AssertionError as e:
            failed.append((t.__name__, str(e)))
            print("  [FAIL] %s" % e)
        except Exception as e:
            failed.append((t.__name__, f"{type(e).__name__}: {e}"))
            print("  [ERROR] %s: %s" % (type(e).__name__, e))

    print("\n" + "=" * 72)
    if failed:
        print("结果: FAIL (%d/%d)" % (len(failed), len(tests)))
        for n, e in failed:
            print("  - %s: %s" % (n, e))
        return 1
    print("结果: PASS (%d/%d 全部通过)" % (len(tests), len(tests)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
