(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const canvas = $("view");
  const ctx = canvas.getContext("2d");
  const scrollEl = $("canvas-scroll");
  const statusEl = $("status-text");
  const coordList = $("coord-list");
  const imageList = $("image-list");
  const fileInput = $("file-input");
  const btnDraw = $("btn-draw");
  const btnErase = $("btn-erase");
  const btnUndo = $("btn-undo");
  const btnRedo = $("btn-redo");
  const btnClear = $("btn-clear");
  const btnSave = $("btn-save");
  const btnFit = $("btn-fit");
  const toast = $("toast");

  const ZOOM_MIN = 0.04;
  const ZOOM_MAX = 10;

  const state = {
    imageId: null,
    img: null,
    drawMode: false,
    eraseMode: false,
    zoom: 1,
    autoFit: true,
    current: [],
    saved: [],
    undoStack: [],
    redoStack: [],
    dragIdx: null,
    isDragging: false,
  };

  const COLORS = [
    "#22d3ee",
    "#facc15",
    "#e879f9",
    "#4ade80",
    "#fb923c",
    "#f87171",
  ];

  function setStatus(msg) {
    statusEl.textContent = msg;
  }

  function showToast(msg, isError) {
    toast.textContent = msg;
    toast.classList.remove("hidden", "error");
    if (isError) toast.classList.add("error");
    else toast.classList.remove("error");
    clearTimeout(showToast._t);
    showToast._t = setTimeout(() => toast.classList.add("hidden"), 5000);
  }

  function clampZoom(z) {
    return Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  }

  /** Snap to 0.1 px for finer control (matches PyQt refinement). */
  function refineXY(x, y) {
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
  }

  function applyFitZoom() {
    if (!state.img || !scrollEl) return;
    const pad = 12;
    const cw = Math.max(80, scrollEl.clientWidth - pad);
    const ch = Math.max(80, scrollEl.clientHeight - pad);
    const iw = state.img.naturalWidth || state.img.width;
    const ih = state.img.naturalHeight || state.img.height;
    if (!iw || !ih) return;
    let z = Math.min(cw / iw, ch / ih) * 0.98;
    state.zoom = clampZoom(z);
  }

  async function fetchJSON(url, options) {
    const res = await fetch(url, {
      credentials: "same-origin",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.error || res.statusText || "Request failed");
    return data;
  }

  async function loadSavedPolygons(imageId) {
    try {
      const data = await fetchJSON("/api/image/" + imageId + "/annotations");
      const polys = data.polygons || [];
      state.saved = polys.map((p) => p.map((pt) => [Number(pt[0]), Number(pt[1])]));
    } catch {
      state.saved = [];
    }
  }

  function hitRadiusImage() {
    return 14 / state.zoom;
  }

  function findVertexIndex(poly, ix, iy) {
    const thr = hitRadiusImage();
    let best = -1;
    let bestD = thr;
    for (let i = 0; i < poly.length; i++) {
      const [px, py] = poly[i];
      const d = Math.hypot(ix - px, iy - py);
      if (d <= bestD) {
        bestD = d;
        best = i;
      }
    }
    return best;
  }

  function redraw() {
    if (!state.img) return;
    const z = state.zoom;
    const w = Math.round(state.img.width * z);
    const h = Math.round(state.img.height * z);
    canvas.width = w;
    canvas.height = h;
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(state.img, 0, 0, w, h);

    const sx = z;
    const sy = z;

    function drawPoly(points, stroke, fillPt) {
      if (!points.length) return;
      ctx.strokeStyle = stroke;
      ctx.lineWidth = Math.max(1, 2 / Math.sqrt(state.zoom));
      ctx.beginPath();
      points.forEach(([x, y], i) => {
        const px = x * sx;
        const py = y * sy;
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      });
      if (points.length >= 3) ctx.closePath();
      ctx.stroke();
      ctx.fillStyle = fillPt;
      const pr = Math.max(3, 5 * Math.sqrt(state.zoom));
      points.forEach(([x, y]) => {
        ctx.beginPath();
        ctx.arc(x * sx, y * sy, pr, 0, Math.PI * 2);
        ctx.fill();
      });
    }

    state.saved.forEach((poly, idx) => {
      drawPoly(poly, COLORS[idx % COLORS.length], "#f87171");
    });
    drawPoly(state.current, "#22d3ee", "#f87171");

    updateCoordList();
  }

  function fmtCoord(x, y) {
    return "(" + x.toFixed(1) + ", " + y.toFixed(1) + ")";
  }

  function updateCoordList() {
    coordList.innerHTML = "";
    state.saved.forEach((poly) => {
      const li = document.createElement("li");
      li.className = "hl";
      li.textContent = "Saved outline";
      coordList.appendChild(li);
      poly.forEach(([x, y]) => {
        const li2 = document.createElement("li");
        li2.textContent = "  " + fmtCoord(x, y);
        coordList.appendChild(li2);
      });
    });
    if (state.current.length) {
      const li = document.createElement("li");
      li.className = "hl";
      li.textContent = "Editing";
      coordList.appendChild(li);
      state.current.forEach(([x, y]) => {
        const li2 = document.createElement("li");
        li2.textContent = "  " + fmtCoord(x, y);
        coordList.appendChild(li2);
      });
    }
  }

  function canvasToImageCoords(clientX, clientY) {
    const r = canvas.getBoundingClientRect();
    const mx = clientX - r.left;
    const my = clientY - r.top;
    const ix = mx / state.zoom;
    const iy = my / state.zoom;
    if (ix < 0 || iy < 0 || ix >= state.img.width || iy >= state.img.height) return null;
    return refineXY(ix, iy);
  }

  function syncModeButtons() {
    btnDraw.classList.toggle("on", state.drawMode);
    btnDraw.textContent = state.drawMode ? "Draw: ON" : "Draw: OFF";
    btnErase.classList.toggle("on", state.eraseMode);
    btnErase.textContent = state.eraseMode ? "Erase: ON" : "Erase: OFF";
    if (state.eraseMode) canvas.style.cursor = "cell";
    else if (state.drawMode) canvas.style.cursor = "crosshair";
    else canvas.style.cursor = "default";
  }

  canvas.addEventListener("mousedown", (e) => {
    if (!state.img) return;
    if (!state.drawMode && !state.eraseMode) return;
    if (e.button !== 0) return;
    const c = canvasToImageCoords(e.clientX, e.clientY);
    if (!c) return;
    const [ix, iy] = c;

    if (state.eraseMode) {
      const hi = findVertexIndex(state.current, ix, iy);
      if (hi >= 0) {
        state.undoStack.push(JSON.stringify(state.current));
        state.redoStack.length = 0;
        state.current.splice(hi, 1);
        redraw();
        setStatus("Vertex removed near " + fmtCoord(ix, iy));
        return;
      }
      setStatus("No vertex here — zoom in or switch to Draw");
      return;
    }

    if (state.drawMode) {
      const hi = findVertexIndex(state.current, ix, iy);
      if (hi >= 0) {
        state.isDragging = true;
        state.dragIdx = hi;
        return;
      }
      state.undoStack.push(JSON.stringify(state.current));
      state.redoStack.length = 0;
      state.current.push([ix, iy]);
      redraw();
      setStatus("Added " + fmtCoord(ix, iy));
    }
  });

  canvas.addEventListener("mousemove", (e) => {
    if (!state.isDragging || state.dragIdx === null || !state.img) return;
    const c = canvasToImageCoords(e.clientX, e.clientY);
    if (!c) return;
    state.current[state.dragIdx] = c;
    redraw();
  });

  window.addEventListener("mouseup", () => {
    state.isDragging = false;
    state.dragIdx = null;
  });

  canvas.addEventListener("contextmenu", (e) => e.preventDefault());

  canvas.addEventListener(
    "wheel",
    (e) => {
      if (!state.img) return;
      e.preventDefault();
      state.autoFit = false;
      const delta = e.deltaY > 0 ? 0.9 : 1.1;
      state.zoom = clampZoom(state.zoom * delta);
      redraw();
      setStatus("Zoom " + state.zoom.toFixed(2) + "× (max " + ZOOM_MAX + "×)");
    },
    { passive: false }
  );

  btnDraw.addEventListener("click", () => {
    state.drawMode = !state.drawMode;
    if (state.drawMode) state.eraseMode = false;
    syncModeButtons();
    setStatus(state.drawMode ? "Draw on — click to add, drag vertices" : "Draw off");
  });

  btnErase.addEventListener("click", () => {
    state.eraseMode = !state.eraseMode;
    if (state.eraseMode) state.drawMode = false;
    syncModeButtons();
    setStatus(state.eraseMode ? "Erase on — click a vertex to remove it" : "Erase off");
  });

  btnUndo.addEventListener("click", () => {
    if (!state.undoStack.length) return;
    state.redoStack.push(JSON.stringify(state.current));
    state.current = JSON.parse(state.undoStack.pop());
    redraw();
  });

  btnRedo.addEventListener("click", () => {
    if (!state.redoStack.length) return;
    state.undoStack.push(JSON.stringify(state.current));
    state.current = JSON.parse(state.redoStack.pop());
    redraw();
  });

  btnClear.addEventListener("click", () => {
    state.current = [];
    state.undoStack.length = 0;
    state.redoStack.length = 0;
    redraw();
    setStatus("Cleared current outline");
  });

  btnSave.addEventListener("click", async () => {
    if (!state.imageId) {
      showToast("Select an image from the list", true);
      return;
    }
    if (state.current.length < 3) {
      showToast("Need at least three points for a closed region", true);
      return;
    }
    try {
      const body = { image_id: state.imageId, points: state.current };
      const r = await fetchJSON("/api/annotation", { method: "POST", body: JSON.stringify(body) });
      await loadSavedPolygons(state.imageId);
      state.current = [];
      state.undoStack.length = 0;
      state.redoStack.length = 0;
      redraw();
      showToast("Saved region — " + (r.mask || "data/masks/…") + " and label.csv");
    } catch (err) {
      showToast(err.message || "Save failed", true);
    }
  });

  btnFit.addEventListener("click", () => {
    if (!state.img) {
      showToast("Open an image first", true);
      return;
    }
    state.autoFit = true;
    applyFitZoom();
    redraw();
    setStatus("Fit to view — " + state.zoom.toFixed(2) + "×");
  });

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.img && state.autoFit) {
        applyFitZoom();
        redraw();
      }
    }, 150);
  });

  async function selectImage(id, url, name) {
    state.imageId = id;
    state.current = [];
    state.undoStack.length = 0;
    state.redoStack.length = 0;
    state.autoFit = true;
    state.zoom = 1;
    await loadSavedPolygons(id);
    const im = new Image();
    im.crossOrigin = "anonymous";
    im.onload = () => {
      state.img = im;
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (state.autoFit) applyFitZoom();
          redraw();
          setStatus(
            "Loaded " +
              name +
              " — " +
              state.saved.length +
              " saved outline(s). Zoom " +
              state.zoom.toFixed(2) +
              "×"
          );
        });
      });
    };
    im.onerror = () => showToast("Could not load image", true);
    im.src = url;
    Array.from(imageList.querySelectorAll("button")).forEach((b) => {
      b.classList.toggle("active", Number(b.dataset.id) === id);
    });
  }

  async function refreshImages() {
    const data = await fetchJSON("/api/images");
    imageList.innerHTML = "";
    data.images.forEach((row) => {
      const li = document.createElement("li");
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.id = row.id;
      btn.textContent = row.original_name;
      btn.addEventListener("click", () => selectImage(row.id, row.url, row.original_name));
      li.appendChild(btn);
      imageList.appendChild(li);
    });
  }

  $("btn-import").addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", async () => {
    const f = fileInput.files && fileInput.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    try {
      const res = await fetch("/api/upload", { method: "POST", body: fd, credentials: "same-origin" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Import failed");
      await refreshImages();
      await selectImage(data.id, data.url, data.original_name);
      showToast("Image imported");
    } catch (e) {
      showToast(e.message || "Import failed", true);
    }
    fileInput.value = "";
  });

  refreshImages().catch((e) => showToast(e.message, true));
})();
