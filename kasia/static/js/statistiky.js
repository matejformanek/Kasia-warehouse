// Statistiky (decision 0107): renders each panel's json_script payload with the
// vendored Chart.js and wires click-to-drill + the product picker.
(function () {
  "use strict";

  function cssVar(name) {
    return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  }

  // Series colours come from the sklad tokens; the second lap reuses them translucent.
  function palette() {
    const base = ["--accent", "--warn", "--fg-soft", "--error", "--accent-deep", "--fg-faint"]
      .map(cssVar)
      .filter(Boolean);
    const colors = base.concat(base.map(function (c) { return /^#[0-9a-f]{6}$/i.test(c) ? c + "99" : c; }));
    return { colors: colors, line: cssVar("--line"), text: cssVar("--fg-soft") };
  }

  function fmt(v) {
    return Number(v).toLocaleString("cs-CZ", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  }

  function drillUrl(drill, index) {
    const url = new URL(window.location.href);
    const p = url.searchParams;
    if (drill.param === "product") {
      p.delete("produkt");
      p.append("produkt", drill.values[index]);
    } else if (drill.param === "bucket") {
      const span = drill.values[index];
      p.set("rozsah", "vlastni");
      p.set("od", span[0]);
      p.set("do", span[1]);
      if (drill.finer === "rok") p.set("gran", "mesic");
      else if (drill.finer === "mesic") p.set("gran", "den");
    }
    return url.toString();
  }

  function render(box) {
    const data = JSON.parse(document.getElementById(box.dataset.chartFor).textContent);
    const pal = palette();
    const type = data.type;
    const horizontal = type === "hbar";
    const pie = type === "doughnut";
    const stacked = !!data.stacked;

    if (horizontal) box.style.height = Math.max(220, data.labels.length * 28 + 60) + "px";

    const datasets = data.datasets.map(function (ds, i) {
      const color = pal.colors[i % pal.colors.length];
      if (pie) {
        return { label: ds.label, data: ds.data, backgroundColor: data.labels.map(function (_, j) { return pal.colors[j % pal.colors.length]; }), borderWidth: 0 };
      }
      return {
        label: ds.label,
        data: ds.data,
        backgroundColor: color,
        borderColor: color,
        borderWidth: type === "line" ? 2 : 0,
        pointRadius: type === "line" ? 2 : 0,
        tension: 0,
      };
    });

    const scales = pie ? {} : {
      x: { stacked: stacked, grid: { color: pal.line }, ticks: { color: pal.text, font: { family: cssVar("--mono") } } },
      y: { stacked: stacked, beginAtZero: true, grid: { color: pal.line }, ticks: { color: pal.text, font: { family: cssVar("--mono") } } },
    };

    const chart = new Chart(box.querySelector("canvas"), {
      type: horizontal ? "bar" : type,
      data: { labels: data.labels, datasets: datasets },
      options: {
        indexAxis: horizontal ? "y" : "x",
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        borderRadius: 0,
        scales: scales,
        plugins: {
          legend: {
            display: pie || datasets.length > 1,
            labels: { color: pal.text, boxWidth: 12, font: { family: cssVar("--ui") } },
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                const v = pie ? ctx.parsed : (horizontal ? ctx.parsed.x : ctx.parsed.y);
                return (ctx.dataset.label || "") + ": " + fmt(v) + " kg";
              },
            },
          },
        },
        onClick: function (_evt, elements) {
          if (!data.drill || !elements.length) return;
          window.location.href = drillUrl(data.drill, elements[0].index);
        },
        onHover: function (evt, elements) {
          evt.native.target.style.cursor = data.drill && elements.length ? "pointer" : "default";
        },
      },
    });
    return chart;
  }

  // GA4-style "all products over time" explorer: metric switch, plotted rows,
  // sortable/searchable/paged table. Everything is computed from the payload.
  const MAX_PLOTTED = 10;
  const PCT_OPTS = { minimumFractionDigits: 1, maximumFractionDigits: 1 };

  function mk(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function pctText(value, total) {
    return (total ? value / total * 100 : 0).toLocaleString("cs-CZ", PCT_OPTS) + " %";
  }

  function changePct(cur, prev) {
    return prev ? (cur - prev) / prev * 100 : null;
  }

  function renderExplorer(root) {
    const payload = JSON.parse(document.getElementById(root.dataset.explorerFor).textContent);
    const data = payload.explorer;
    const pal = palette();
    const metrics = data.metrics;
    const labelOf = {};
    metrics.forEach(function (m) { labelOf[m.key] = m.label; });
    const products = data.products;
    const state = { metric: metrics[0].key, sort: null, dir: -1, query: "", size: 10, page: 0, checked: [], slots: {} };

    const metricBox = root.querySelector(".stat-ex-metrics");
    const search = root.querySelector(".stat-ex-search");
    const sizeSel = root.querySelector(".stat-ex-pagesize");
    const hint = root.querySelector(".stat-ex-hint");
    const table = root.querySelector(".stat-ex-table");
    const pager = root.querySelector(".stat-ex-pager");

    function slotColor(slot) {
      return pal.colors[slot % pal.colors.length];
    }

    function takeSlot(id) {
      const used = Object.keys(state.slots).map(function (k) { return state.slots[k]; });
      for (let s = 0; s < MAX_PLOTTED; s++) {
        if (used.indexOf(s) === -1) { state.slots[id] = s; return; }
      }
    }

    function resetChecked() {
      state.slots = {};
      state.checked = products
        .filter(function (p) { return p.kg[state.metric] > 0; })
        .sort(function (a, b) { return b.kg[state.metric] - a.kg[state.metric]; })
        .slice(0, 5)
        .map(function (p) { return p.id; });
      state.checked.forEach(takeSlot);
    }

    const chart = new Chart(root.querySelector("canvas"), {
      type: "line",
      data: { labels: payload.labels, datasets: [] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: { mode: "index", intersect: false },
        scales: {
          x: { grid: { color: pal.line }, ticks: { color: pal.text, font: { family: cssVar("--mono") } } },
          y: { beginAtZero: true, grid: { color: pal.line }, ticks: { color: pal.text, font: { family: cssVar("--mono") } } },
        },
        plugins: {
          legend: { labels: { color: pal.text, boxWidth: 12, font: { family: cssVar("--ui") } } },
          tooltip: { callbacks: { label: function (ctx) { return ctx.dataset.label + ": " + fmt(ctx.parsed.y) + " kg"; } } },
        },
      },
    });

    function plot() {
      const key = state.metric;
      const total = {
        label: "Celkem",
        data: data.totals[key],
        borderColor: pal.text,
        backgroundColor: pal.text + "22",
        borderDash: [2, 4],
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        tension: 0,
        order: 99,
      };
      const lines = state.checked.map(function (id) {
        const p = products.find(function (x) { return x.id === id; });
        const slot = state.slots[id];
        return {
          label: p.name,
          data: p.series[key],
          borderColor: slotColor(slot),
          backgroundColor: slotColor(slot),
          borderDash: slot >= pal.colors.length / 2 ? [6, 3] : [],
          borderWidth: 2,
          pointRadius: 2,
          tension: 0,
          order: slot,
        };
      });
      chart.data.datasets = [total].concat(lines);
      chart.update();
    }

    function sortValue(p, col) {
      if (col === "name") return p.name;
      if (col === "change") {
        const c = changePct(p.kg[state.metric], p.prev[state.metric]);
        return c === null ? -Infinity : c;
      }
      return p.kg[col];
    }

    function visibleRows() {
      const rf = window.kasiaRowFilter;
      const tokens = rf ? rf.tokenize(state.query) : state.query.toLowerCase().split(/\s+/).filter(Boolean);
      const rows = products.filter(function (p) {
        if (!tokens.length) return true;
        const text = rf ? rf.fold(p.name) : p.name.toLowerCase();
        return rf ? rf.matches(tokens, text, text.split(" ")) : tokens.every(function (t) { return text.indexOf(t) !== -1; });
      });
      const col = state.sort || state.metric;
      return rows.sort(function (a, b) {
        const x = sortValue(a, col), y = sortValue(b, col);
        const r = typeof x === "string" ? x.localeCompare(y, "cs") : (x === y ? 0 : x - y);
        return (r || a.name.localeCompare(b.name, "cs")) * state.dir;
      });
    }

    function headCell(label, col, num) {
      const cell = mk("th", num ? "num" : "");
      const active = (state.sort || state.metric) === col;
      const btn = mk("button", "stat-ex-sort", label + (active ? (state.dir < 0 ? " ▼" : " ▲") : ""));
      btn.type = "button";
      btn.addEventListener("click", function () {
        if (active) state.dir = -state.dir;
        else { state.sort = col; state.dir = col === "name" ? 1 : -1; }
        state.page = 0;
        renderTable();
      });
      cell.appendChild(btn);
      return cell;
    }

    function numCell(value, total, strong) {
      const td = mk("td", "num mono");
      td.appendChild(mk("span", strong ? "stat-ex-val strong" : "stat-ex-val", fmt(value)));
      td.appendChild(mk("small", "stat-ex-pct muted", pctText(value, total)));
      return td;
    }

    function changeCell(cur, prev) {
      const td = mk("td", "num mono");
      const c = changePct(cur, prev);
      if (c === null) {
        td.textContent = cur > 0 ? "nové" : "—";
      } else {
        const arrow = c > 0 ? "▲ " : c < 0 ? "▼ " : "● ";
        td.appendChild(mk("span", "stat-delta " + (c > 0 ? "up" : c < 0 ? "down" : "flat"), arrow + Math.abs(c).toLocaleString("cs-CZ", PCT_OPTS) + " %"));
      }
      return td;
    }

    function toggle(id, on) {
      if (on) {
        if (state.checked.length >= MAX_PLOTTED || state.checked.indexOf(id) !== -1) return;
        state.checked.push(id);
        takeSlot(id);
      } else {
        state.checked = state.checked.filter(function (x) { return x !== id; });
        delete state.slots[id];
      }
      plot();
      renderTable();
    }

    function renderTable() {
      const key = state.metric;
      const others = metrics.filter(function (m) { return m.key !== key; });
      const rows = visibleRows();
      const pages = Math.max(1, Math.ceil(rows.length / state.size));
      if (state.page >= pages) state.page = pages - 1;
      const start = state.page * state.size;
      const full = state.checked.length >= MAX_PLOTTED;
      hint.hidden = !full;

      table.textContent = "";
      const thead = mk("thead");
      const hr = mk("tr");
      hr.appendChild(mk("th", "stat-ex-check"));
      hr.appendChild(mk("th", "num", "#"));
      hr.appendChild(headCell("Produkt", "name", false));
      hr.appendChild(headCell(labelOf[key] + " (kg)", key, true));
      hr.appendChild(headCell("Změna", "change", true));
      others.forEach(function (m) { hr.appendChild(headCell(m.label + " (kg)", m.key, true)); });
      thead.appendChild(hr);
      table.appendChild(thead);

      const tbody = mk("tbody");
      const sum = mk("tr", "stat-ex-total");
      sum.appendChild(mk("td"));
      sum.appendChild(mk("td"));
      sum.appendChild(mk("td", "", "Celkem"));
      sum.appendChild(numCell(data.grand[key], data.grand[key], true));
      sum.appendChild(changeCell(data.grand[key], data.grand_prev[key]));
      others.forEach(function (m) { sum.appendChild(numCell(data.grand[m.key], data.grand[m.key], true)); });
      tbody.appendChild(sum);

      rows.slice(start, start + state.size).forEach(function (p, i) {
        const tr = mk("tr");
        const checked = state.checked.indexOf(p.id) !== -1;
        const c1 = mk("td", "stat-ex-check");
        const box = mk("input");
        box.type = "checkbox";
        box.checked = checked;
        box.disabled = !checked && full;
        box.setAttribute("aria-label", "Zobrazit v grafu: " + p.name);
        box.addEventListener("change", function () { toggle(p.id, box.checked); });
        const swatch = mk("span", "stat-ex-swatch");
        if (checked) swatch.style.background = slotColor(state.slots[p.id]);
        c1.appendChild(box);
        c1.appendChild(swatch);
        tr.appendChild(c1);
        tr.appendChild(mk("td", "num mono muted", String(start + i + 1)));
        tr.appendChild(mk("td", "", p.name));
        tr.appendChild(numCell(p.kg[key], data.grand[key], false));
        tr.appendChild(changeCell(p.kg[key], p.prev[key]));
        others.forEach(function (m) { tr.appendChild(numCell(p.kg[m.key], data.grand[m.key], false)); });
        tbody.appendChild(tr);
      });
      table.appendChild(tbody);

      pager.textContent = "";
      const to = Math.min(rows.length, start + state.size);
      const prev = mk("button", "secondary", "←");
      prev.type = "button";
      prev.disabled = state.page === 0;
      prev.setAttribute("aria-label", "Předchozí strana");
      prev.addEventListener("click", function () { state.page--; renderTable(); });
      const next = mk("button", "secondary", "→");
      next.type = "button";
      next.disabled = state.page >= pages - 1;
      next.setAttribute("aria-label", "Další strana");
      next.addEventListener("click", function () { state.page++; renderTable(); });
      pager.appendChild(mk("span", "stat-ex-range", (rows.length ? start + 1 : 0) + "–" + to + " z " + rows.length));
      pager.appendChild(prev);
      pager.appendChild(next);
    }

    function renderMetrics() {
      metricBox.textContent = "";
      metrics.forEach(function (m) {
        const btn = mk("button", "tab-chip" + (m.key === state.metric ? " active" : ""), m.label);
        btn.type = "button";
        btn.addEventListener("click", function () {
          state.metric = m.key;
          state.sort = null;
          state.dir = -1;
          state.page = 0;
          resetChecked();
          renderMetrics();
          plot();
          renderTable();
        });
        metricBox.appendChild(btn);
      });
    }

    search.addEventListener("input", function () { state.query = search.value; state.page = 0; renderTable(); });
    sizeSel.addEventListener("change", function () { state.size = parseInt(sizeSel.value, 10); state.page = 0; renderTable(); });

    resetChecked();
    renderMetrics();
    plot();
    renderTable();
  }

  function wireProductPicker() {
    const input = document.getElementById("stat-product-search");
    const list = document.getElementById("stat-product-list");
    if (!input || !list) return;
    input.addEventListener("input", function () {
      const rf = window.kasiaRowFilter;
      const tokens = rf ? rf.tokenize(input.value) : input.value.toLowerCase().split(/\s+/).filter(Boolean);
      list.querySelectorAll("label").forEach(function (label) {
        let show = true;
        if (tokens.length) {
          const text = rf ? rf.fold(label.dataset.filterText) : label.dataset.filterText.toLowerCase();
          show = rf ? rf.matches(tokens, text, text.split(" ")) : tokens.every(function (t) { return text.indexOf(t) !== -1; });
        }
        label.style.display = show ? "" : "none";
      });
    });
  }

  function wireRangeSelect() {
    const preset = document.getElementById("id_rozsah");
    ["id_od", "id_do"].forEach(function (id) {
      const el = document.getElementById(id);
      if (el && preset) el.addEventListener("change", function () { preset.value = "vlastni"; });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    wireProductPicker();
    wireRangeSelect();
    if (typeof Chart === "undefined") return;
    document.querySelectorAll(".stat-canvas[data-chart-for]").forEach(render);
    document.querySelectorAll(".stat-explorer[data-explorer-for]").forEach(renderExplorer);
  });
})();
