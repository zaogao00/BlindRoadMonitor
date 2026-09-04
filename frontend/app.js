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
          const name = document.createElement("span");
          name.textContent = o.zh || o.class;
          const cf = document.createElement("span");
          cf.className = "cf";
          cf.textContent = (o.confidence != null ? o.confidence.toFixed(2) : "");
          li.appendChild(name);
          li.appendChild(cf);
          list.appendChild(li);
        });
      }
    }

    // Alert banner
    const banner = $("alert-banner");
    if (!banner) return;
    if (s.alert) {
      banner.classList.remove("hidden");
      $("alert-msg").textContent = s.alert_message || "检测到障碍物，请注意。";
      const al = $("alert-list");
      al.innerHTML = "";
      (s.obstacles || []).forEach((o) => {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = (o.zh || o.class) + (o.confidence != null ? " " + o.confidence.toFixed(2) : "");
        al.appendChild(chip);
      });
    } else {
      banner.classList.add("hidden");
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
