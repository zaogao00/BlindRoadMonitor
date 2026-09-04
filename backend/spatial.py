# -*- coding: utf-8 -*-
"""Phase 20 — 障碍物是否占用盲道：空间关系判断 (SpatialChecker)。

职责:
  - 输入: blind_road 的 bbox 列表 + obstacle 的 bbox 列表 (已由 AlertManager 从 YOLO 原始框筛选)
  - 计算每个障碍物与盲道的二维几何关系:
      * IoU (交集面积 / 并集面积)
      * center_inside (障碍物中心是否落在盲道 bbox 内)
      * obstacle_overlap_ratio (交集面积 / 障碍物面积, 即障碍物有多少比例压在盲道上)
  - 综合可解释规则判定空间状态:
      NONE / NORMAL_OBSTACLE / BLOCKING_SUSPECTED
  - 纯几何 + 规则, 不加载模型, 不引第三方 AI, 不依赖 GPU。

设计边界 (Phase 20, 规格 §四/§二十一/§二十五/§二十七):
  - 仅基于 YOLO bounding box 的二维空间关系; 非 pixel 级 segmentation, 非 3D 距离测量。
  - 输出定义为"疑似占用盲道", 不是绝对阻挡确认。
  - 本文件**不**定义/复制障碍物类别列表 (复用 backend.alert 的 OBSTACLE_CLASS_INDICES);
    它只接收已经筛好的 bbox 与类别名, 保持几何层与业务层解耦。
"""
# ---- 默认阈值 (经 tests/test_spatial.py 的 3x3 阈值扫描选定, 见 docs/spatial_relation_report.md) ----
IOU_THRESHOLD = 0.10        # 条件 A: IoU >= 此值 → 疑似占用
OVERLAP_THRESHOLD = 0.20    # 条件 C: 障碍物 bbox 落入盲道比例 >= 此值 → 疑似占用
# 条件 B 的护栏: "中心在盲道 bbox 内" 仍需有**可观测的交叠**才计数,
# 避免退化情形 (极大障碍物 + 极小盲道框, 或坐标异常) 造成纯几何上的"中心命中"。
# 阈值取的很小 (5%), 只用于排除病态输入, 不改变 B 的语义。
CENTER_MIN_OVERLAP = 0.05


# ----------------------------------------------------------------------------
# 基础几何
# ----------------------------------------------------------------------------
def _area(box):
    """box 像素面积; 负宽高夹紧为 0。"""
    w = max(0.0, box[2] - box[0])
    h = max(0.0, box[3] - box[1])
    return w * h


def _intersection_area(box, region):
    ix1 = max(box[0], region[0])
    iy1 = max(box[1], region[1])
    ix2 = min(box[2], region[2])
    iy2 = min(box[3], region[3])
    w = max(0.0, ix2 - ix1)
    h = max(0.0, iy2 - iy1)
    return w * h


def compute_iou(box, region):
    """Intersection over Union (规格 §八)。box / region: (x1,y1,x2,y2)。"""
    inter = _intersection_area(box, region)
    union = _area(box) + _area(region) - inter
    if union <= 0:
        return 0.0
    return inter / union


def is_center_inside(box, region):
    """障碍物中心是否位于盲道 bbox 内 (规格 §九)。"""
    cx = (box[0] + box[2]) / 2.0
    cy = (box[1] + box[3]) / 2.0
    return (region[0] <= cx <= region[2]) and (region[1] <= cy <= region[3])


def obstacle_overlap_ratio(box, region):
    """障碍物 bbox 有多少比例落入盲道 bbox (交集面积 / 障碍物面积, 规格 §十)。"""
    inter = _intersection_area(box, region)
    a = _area(box)
    if a <= 0:
        return 0.0
    return inter / a


# ----------------------------------------------------------------------------
# 综合判定
# ----------------------------------------------------------------------------
def best_metrics(box, blind_rects):
    """对一个障碍物, 取它与所有盲道框中最强的一组几何指标 (取各指标最大值)。"""
    best = {"iou": 0.0, "overlap_ratio": 0.0, "center_inside": False}
    for br in blind_rects:
        iou = compute_iou(box, br)
        ovr = obstacle_overlap_ratio(box, br)
        ctr = is_center_inside(box, br)
        if iou > best["iou"]:
            best["iou"] = iou
        if ovr > best["overlap_ratio"]:
            best["overlap_ratio"] = ovr
        if ctr:
            best["center_inside"] = True
    return best


def classify(blind_rects, obstacle_items, iou_th=IOU_THRESHOLD, overlap_th=OVERLAP_THRESHOLD):
    """综合规则判定空间占用 (规格 §十一~§十三)。

    参数:
      blind_rects:   list[(x1,y1,x2,y2)]  (盲道框)
      obstacle_items: list[dict], 每项含:
          box:        (x1,y1,x2,y2)
          cls:        int 类别索引
          class:      str 类别名 (用于 API/绘制)
          confidence: float
          zh:         str 中文显示名
      阈值 iou_th / overlap_th 可调 (阈值扫描见 tests/test_spatial.py)。

    返回 occupancy dict:
      status:             'none' | 'normal' | 'suspected'
      level:              0 | 1 | 2
      blocking:           bool  (是否出现疑似占用)
      obstacles:          [ {class, confidence, iou, overlap_ratio, center_inside, blocking, box, zh} ]
                           (所有障碍物, 含几何指标与 blocking 标记, 供前端区分/绘制)
      blocking_obstacles: [ 同上但仅 blocking=True ]
      blind_rects:        [[x1,y1,x2,y2], ...]  (回传, 供视频绘制)
    """
    obstacles_out = []
    blocking_out = []
    for it in obstacle_items:
        box = it["box"]
        m = best_metrics(box, blind_rects)
        # 综合规则 (规格 §十一): 满足任一条件即"疑似占用"
        #   条件 A: IoU >= iou_th
        #   条件 B: 障碍物中心在盲道 bbox 内 (且交叠 >= CENTER_MIN_OVERLAP, 排除病态输入)
        #   条件 C: 障碍物 bbox 落入盲道比例 >= overlap_th
        blocking = (
            (m["iou"] >= iou_th)
            or (m["center_inside"] and m["overlap_ratio"] >= CENTER_MIN_OVERLAP)
            or (m["overlap_ratio"] >= overlap_th)
        )
        rec = {
            "class": it.get("class"),
            "cls": it.get("cls"),
            "zh": it.get("zh", it.get("class")),
            "confidence": round(float(it.get("confidence", 0.0)), 3),
            "iou": round(m["iou"], 3),
            "overlap_ratio": round(m["overlap_ratio"], 3),
            "center_inside": bool(m["center_inside"]),
            "blocking": bool(blocking),
            "box": [float(v) for v in box],
        }
        obstacles_out.append(rec)
        if blocking:
            blocking_out.append(rec)

    if blocking_out:
        status = "suspected"
        level = 2
        blocking = True
    elif obstacles_out:
        status = "normal"
        level = 1
        blocking = False
    else:
        status = "none"
        level = 0
        blocking = False

    return {
        "status": status,
        "level": level,
        "blocking": blocking,
        "obstacles": obstacles_out,
        "blocking_obstacles": blocking_out,
        "blind_rects": [[float(v) for v in b] for b in blind_rects],
    }


# ----------------------------------------------------------------------------
# 视频绘制 (lazy import cv2, 避免纯几何测试被迫加载 OpenCV)
# ----------------------------------------------------------------------------
def draw_occupancy(frame, occupancy, names=None):
    """在空间关系判定结果下绘制全部检测框 (规格 §二十):

      - 盲道框:     橙色 + "盲道 blind_road" 标签 (必须保留, 用户据此看出哪块是盲道)
      - 普通障碍物: 绿色 + "类别 置信度"
      - 疑似占用:   红色 + "类别 置信度 占用盲道?"

    注意: **原地修改** frame (由调用方负责 copy, 见 Detector.draw)。
    """
    import cv2  # lazy: 仅绘制时依赖, 几何/单元测试不触发

    out = frame
    occ = occupancy or {}
    for br in occ.get("blind_rects", []):
        x1, y1, x2, y2 = (int(br[0]), int(br[1]), int(br[2]), int(br[3]))
        cv2.rectangle(out, (x1, y1), (x2, y2), (0, 200, 255), 2)
        cv2.putText(
            out, "blind_road", (x1, max(12, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 200, 255), 2,
        )
    for o in occ.get("obstacles", []):
        x1, y1, x2, y2 = (int(o["box"][0]), int(o["box"][1]), int(o["box"][2]), int(o["box"][3]))
        zh = o.get("zh") or o.get("class") or ""
        conf = o.get("confidence", 0.0)
        if o.get("blocking"):
            color = (0, 0, 255)  # 红: 疑似占用
            label = f"{zh} {conf:.2f} 占用盲道?"
        else:
            color = (0, 255, 0)  # 绿: 普通障碍物
            label = f"{zh} {conf:.2f}"
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            out, label, (x1, max(12, y1 - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2,
        )
    return out
