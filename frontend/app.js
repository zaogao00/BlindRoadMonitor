// Phase 19 — 前端逻辑: 轮询 /api/status, 更新状态面板 + 视觉警告横幅。
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);

  function setText(id, txt, cls) {
    const el = $(id);
    if (!el) return;
    el.textContent = txt;
    if (cls !== undefined) {
      el.className = "v" + (cls ? " " + cls : "");
    }
  }

  function renderStatus(s) {
    // Camera / Model
    setText("st-camera", s.camera ? "Connected" : "Error", s.camera ? "ok" : "err");
    if (!s.camera && s.camera_error) {
      const el = $("st-camera");
      if (el) el.title = s.camera_error;
    }
    setText("st-model", s.model ? "Loaded" : (s.model_error ? "Error" : "…"),
            s.model ? "ok" : (s.model_error ? "err" : ""));

    setText("st-fps", s.fps_stream != null ? s.fps_stream.toFixed(1) : "…");
    setText("st-fpsm", s.fps_model != null ? s.fps_model.toFixed(1) : "…");

    // Blind road
    if (s.blind_road) {
      setText("st-blind", s.blind_road_count > 1 ? "Detected (" + s.blind_road_count + ")" : "Detected", "ok");
    } else {
      setText("st-blind", "Not Detected", "");
    }

    // Obstacles
    setText("st-obs", String(s.obstacle_count || 0));

    // ---- Phase 20: 空间关系 (盲道占用) + 告警等级 ----
    const occ = s.occupancy || {};
    const blocking = !!s.blocking || occ.status === "suspected";
    if (blocking) {
      setText("st-occ", "疑似", "blocking");
    } else if ((s.obstacle_count || 0) > 0) {
      setText("st-occ", "未发现", "ok");
    } else {
      setText("st-occ", "未发现", "");
    }
    const lvl = s.alert_level != null ? s.alert_level : (occ.level || 0);
    const lvlTxt = lvl === 2 ? "2 · 疑似占用盲道" : (lvl === 1 ? "1 · 普通障碍物" : "0 · 无");
    setText("st-level", lvlTxt, lvl === 2 ? "blocking" : (lvl === 1 ? "warn" : "ok"));

    // TTS
    if (s.tts_available) {
      setText("st-tts", "可用", "ok");
    } else {
      setText("st-tts", "不可用", "warn");
      const el = $("st-tts");
      if (el && s.tts_error) el.title = s.tts_error;
    }

    // Obstacle list
    const list = $("obs-list");
    if (list) {
      list.innerHTML = "";
      const obs = s.obstacles || [];
      if (obs.length === 0) {
        const li = document.createElement("li");
        li.className = "muted";
        li.textContent = "当前未检测到障碍物";
        list.appendChild(li);
      } else {
        obs.forEach((o) => {
          const li = document.createElement("li");
          if (o.blocking) li.className = "blocking";  // 疑似占用盲道
          const name = document.createElement("span");
          name.textContent = o.zh || o.class;
          const cf = document.createElement("span");
          cf.className = "cf";
          cf.textContent = (o.confidence != null ? o.confidence.toFixed(2) : "");
          li.appendChild(name);
          li.appendChild(cf);
          if (o.blocking) {
            const tag = document.createElement("span");
            tag.className = "tag";
            tag.textContent = "占用盲道?";
            li.appendChild(tag);
          }
          list.appendChild(li);
        });
      }
    }

    // ---- Alert banner (Phase 20: Level 1 琥珀 / Level 2 红色) ----
    const banner = $("alert-banner");
    if (!banner) return;
    if (s.alert) {
      banner.classList.remove("hidden");
      const lvl2 = (s.alert_level === 2) || blocking;
      banner.classList.toggle("blocking", !!lvl2);
      $("alert-title").textContent = lvl2
        ? "🔴 障碍物疑似占用盲道，请注意！"
        : "⚠️ 检测到障碍物，请注意！";
      $("alert-msg").textContent = s.alert_message || "检测到障碍物，请注意。";

      // Level 2: 显示"相关障碍物" (即疑似占用盲道的那些, 含几何指标)
      const rel = $("alert-related");
      if (rel) {
        const bo = occ.blocking_obstacles || [];
        if (lvl2 && bo.length > 0) {
          rel.classList.remove("hidden");
          $("alert-related-list").innerHTML = bo
            .map(function (o) {
              const nm = o.zh || o.class;
              const cfi = o.confidence != null ? o.confidence.toFixed(2) : "";
              const iou = o.iou != null ? o.iou.toFixed(2) : "-";
              const ovr = o.overlap_ratio != null ? o.overlap_ratio.toFixed(2) : "-";
              return nm + " <b>" + cfi + "</b>" + " (IoU " + iou + " / 交叠 " + ovr + ")";
            })
            .join("　");
        } else {
          rel.classList.add("hidden");
        }
      }

      // 全部当前障碍物 chip
      const al = $("alert-list");
      if (al) {
        al.innerHTML = "";
        (s.obstacles || []).forEach((o) => {
          const chip = document.createElement("span");
          chip.className = "chip";
          chip.textContent =
            (o.zh || o.class) +
            (o.confidence != null ? " " + o.confidence.toFixed(2) : "") +
            (o.blocking ? " · 占用盲道?" : "");
          al.appendChild(chip);
        });
      }
    } else {
      banner.classList.add("hidden");
      banner.classList.remove("blocking");
      const rel2 = $("alert-related");
      if (rel2) rel2.classList.add("hidden");
    }
  }

  async function poll() {
    try {
      const r = await fetch("/api/status", { cache: "no-store" });
      if (r.ok) {
        const s = await r.json();
        renderStatus(s);
      }
    } catch (e) {
      // 网络抖动忽略, 下次重试
    }
  }

  // 初始渲染 + 定时轮询 (规格: 状态面板约 500ms 刷新)
  poll();
  setInterval(poll, 500);
})();
