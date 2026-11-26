/* MJSCalc browser demo.
 * Loads Pyodide, installs MJSCalc's engine (py/mjscalc/engine/*.py, copied from the
 * desktop app by packaging/build_web.py) plus bridge.py, and drives four pages with it.
 * All calculations happen in Python, the same code the desktop app runs. */
"use strict";

const ENGINE_FILES = ["__init__.py", "engine/__init__.py", "engine/expression.py",
                      "engine/finance.py", "engine/units.py", "engine/graph.py"];
const DOWNLOAD_URL = "https://mjsapps.net/mjscalc/";
const LOCKED = [   // each page's own description from the desktop app
  ["∑", "Math", "Calculus, matrices, vectors, equations, exact fractions and geometry. Entries can be fractions like 2/3 or expressions like sqrt(2)."],
  ["📈", "Finance", "Take-home pay, savings and investing, time-value-of-money, cash flows, and everyday money math."],
  ["🏖", "Retirement", "Enter your numbers to see how your savings could grow, how long they'll last, and your chances across 1,000 simulated markets."],
  ["💰", "Budget", "List your income and expenses — monthly or yearly — to see what you spend each month and year, what's left over, and where it goes."],
  ["⚛", "Physics", "Pick a formula, choose what to solve for, and fill in the rest — every value can use its own units."],
  ["🧪", "Chemistry", "Molar mass, equation balancing, solution and gas formulas, and the periodic table."],
  ["🔧", "Engineering", "Calculators and formulas for electrical, computer, civil, mechanical, chemical and robotics engineering, plus electronics and construction."],
  ["💻", "Programmer", "Integer math in hex, decimal, octal and binary with bitwise operators, and character codes."],
  ["🌐", "Networking", "Subnets for IPv4 and IPv6, subnet planning (VLSM), summarizing and IP ranges, a CIDR chart, bandwidth and latency math, MAC addresses and well-known ports."],
  ["❤", "Health", "BMI, calories, body fat, heart-rate zones and running pace. Estimates from standard formulas — not medical advice."],
  ["📅", "Date & Time", "Days between dates, date math, ages, business days, time zones and time cards."],
  ["📊", "Statistics", "Describe data, fit a line, work out probabilities, confidence intervals, sample sizes and t-tests."],
];

let py = null;          // the bridge module
let pyodide = null;

// ---------------------------------------------------------------- helpers
const $ = (id) => document.getElementById(id);
const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem("mjscalc-demo-" + key); return v === null ? fallback : JSON.parse(v); }
    catch (e) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem("mjscalc-demo-" + key, JSON.stringify(value)); } catch (e) { /* private mode */ }
  },
};

function call(name, ...args) {
  const pyArgs = args.map((a) => (a !== null && typeof a === "object") ? pyodide.toPy(a) : a);
  let r;
  try { r = py[name](...pyArgs); }
  finally { pyArgs.forEach((a) => a && a.destroy && a.destroy()); }
  if (r && typeof r.toJs === "function") {
    const out = r.toJs({ dict_converter: Object.fromEntries });
    r.destroy();
    return out;
  }
  return r;
}

function seg(id, onChange) {
  const el = $(id);
  el.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    setSeg(id, b.dataset.v);
    onChange(b.dataset.v);
  });
  return el;
}
function setSeg(id, value) {
  for (const b of $(id).querySelectorAll("button")) b.classList.toggle("on", b.dataset.v === value);
}
function segValue(id) { return $(id).querySelector("button.on").dataset.v; }

function table(el, headers, rows) {
  const esc = (s) => String(s).replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]));
  el.innerHTML = "<table><thead><tr>" + headers.map((h) => `<th>${esc(h)}</th>`).join("") +
    "</tr></thead><tbody>" + rows.map((r) => "<tr>" + r.map((c) => `<td>${esc(c)}</td>`).join("") + "</tr>").join("") +
    "</tbody></table>";
}

const coarse = window.matchMedia("(pointer: coarse)").matches;

// ---------------------------------------------------------------- popover
function popover(anchor, items) {
  const pop = $("popover");
  pop.innerHTML = "";
  for (const [text, small, action] of items) {
    const b = document.createElement("button");
    b.textContent = text;
    if (small) { const s = document.createElement("small"); s.textContent = small; b.appendChild(s); }
    b.addEventListener("click", () => { hidePopover(); action(); });
    pop.appendChild(b);
  }
  pop.hidden = false;
  const r = anchor.getBoundingClientRect();
  const w = pop.offsetWidth, h = pop.offsetHeight;
  pop.style.left = Math.max(8, Math.min(r.left, innerWidth - w - 8)) + "px";
  pop.style.top = (r.bottom + h + 8 < innerHeight ? r.bottom + 4 : Math.max(8, r.top - h - 4)) + "px";
}
function hidePopover() { $("popover").hidden = true; }
document.addEventListener("pointerdown", (e) => {
  if (!$("popover").hidden && !e.target.closest("#popover") && !e.target.closest("[data-pop]")) hidePopover();
});

// ---------------------------------------------------------------- navigation
const pages = {};
function showPage(name, lockedInfo) {
  document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
  if (lockedInfo) {
    const [icon, title, text] = lockedInfo;
    $("locked-icon").textContent = icon;
    $("locked-title").textContent = `${title} is in the full app`;
    $("locked-text").textContent = text;
    $("page-locked").classList.add("active");
    document.querySelector(`.nav-item[data-locked="${title}"]`).classList.add("active");
    return;
  }
  $("page-" + name).classList.add("active");
  document.querySelector(`.nav-item[data-page="${name}"]`).classList.add("active");
  store.set("page", name);
  if (pages[name] && pages[name].shown) pages[name].shown();
}
function setupNav() {
  const box = $("locked");
  for (const info of LOCKED) {
    const b = document.createElement("button");
    b.className = "nav-item lock";
    b.dataset.locked = info[1];
    b.innerHTML = `${info[0]} <span></span>`;
    b.querySelector("span").textContent = info[1];
    b.addEventListener("click", () => showPage(null, info));
    box.appendChild(b);
  }
  document.querySelectorAll(".nav-item[data-page]").forEach((b) =>
    b.addEventListener("click", () => showPage(b.dataset.page)));
}

// ================================================================ Calculator
const CONTINUE = ["+", "-", "−", "*", "×", "/", "÷", "^", "%", "!", "²", "³"];

function setupCalculator() {
  const edit = $("expr"), preview = $("preview"), prevExpr = $("prev-expr");
  let angle = store.get("angle", "deg"), mode = store.get("fmt", "auto");
  let history = store.get("history", []);
  let justEvaluated = false;
  const catalog = call("calc_catalog");
  const d = catalog.descriptions;
  call("calc_restore", history.slice(0, 1));
  if (coarse) edit.setAttribute("inputmode", "none");   // the keypad is the keyboard on iPad

  setSeg("angle", angle);
  setSeg("fmt", mode);
  seg("angle", (v) => { angle = v; store.set("angle", v); updatePreview(); });
  seg("fmt", (v) => { mode = v; store.set("fmt", v); updatePreview(); renderHistory(); });

  const sciOn = store.get("scientific", true);
  const setSci = (on) => {
    $("sci-toggle").classList.toggle("on", on);
    $("sci-pad").hidden = !on;
    store.set("scientific", on);
  };
  setSci(sciOn);
  $("sci-toggle").addEventListener("click", () => setSci($("sci-pad").hidden));
  $("hist-toggle").addEventListener("click", () => {
    const card = $("history-card");
    card.hidden = !card.hidden;
    $("hist-toggle").classList.toggle("on", !card.hidden);
  });

  function caret() {
    const s = edit.selectionStart ?? edit.value.length, e = edit.selectionEnd ?? s;
    return [s, e];
  }
  function beforeInsert(text) {
    if (justEvaluated) {
      if (!CONTINUE.some((c) => text.startsWith(c))) edit.value = "";
      else edit.setSelectionRange(edit.value.length, edit.value.length);
      justEvaluated = false;
    }
  }
  function insert(text) {
    beforeInsert(text);
    const [s, e] = caret();
    edit.value = edit.value.slice(0, s) + text + edit.value.slice(e);
    const pos = s + text.length;
    edit.setSelectionRange(pos, pos);
    if (!coarse) edit.focus();
    updatePreview();
  }
  function setText(t, cursor) {
    edit.value = t;
    const pos = cursor ?? t.length;
    edit.setSelectionRange(pos, pos);
    justEvaluated = false;
    if (!coarse) edit.focus();
    updatePreview();
  }
  function clear() { edit.value = ""; prevExpr.textContent = ""; justEvaluated = false; updatePreview(); if (!coarse) edit.focus(); }
  function backspace() {
    justEvaluated = false;
    const [s, e] = caret();
    if (s !== e) edit.value = edit.value.slice(0, s) + edit.value.slice(e);
    else if (s > 0) { edit.value = edit.value.slice(0, s - 1) + edit.value.slice(s); edit.setSelectionRange(s - 1, s - 1); }
    updatePreview();
  }
  const plainNumber = (s) => s.trim() !== "" && !isNaN(Number(s));
  function negate() {
    const t = edit.value.trim();
    if (!t) setText("-");
    else if (t.startsWith("-(") && t.endsWith(")")) setText(t.slice(2, -1));
    else if (t.startsWith("-") && plainNumber(t.slice(1))) setText(t.slice(1));
    else if (plainNumber(t)) setText("-" + t);
    else setText(`-(${t})`);
  }
  const reciprocal = () => setText(`1/(${edit.value.trim() || "ans"})`);
  const assignVar = () => setText("x = " + (edit.value.trim() || "ans"), 1);

  function showPreview(text, cls) {
    preview.textContent = text;
    preview.className = "preview" + (cls ? " " + cls : "");
  }
  function updatePreview() {
    const t = edit.value.trim();
    if (!t) return showPreview("0");
    const r = call("calc_eval", t, angle, mode, false);
    showPreview(r.ok ? "= " + r.shown : "");
  }
  function evaluate() {
    const t = edit.value.trim();
    if (!t) return;
    const r = call("calc_eval", t, angle, mode, true);
    if (!r.ok) return showPreview(r.error, "error");
    prevExpr.textContent = t + " =";
    history.unshift({ expr: t, value: r.value });
    history = history.slice(0, 200);
    store.set("history", history);
    renderHistory();
    edit.value = r.shown.replace(/,/g, "");
    showPreview(r.shown, "final");
    justEvaluated = true;
    if (!coarse) edit.focus();
  }

  function renderHistory() {
    const ul = $("history");
    ul.innerHTML = "";
    if (!history.length) {
      ul.innerHTML = '<li class="empty">Your calculations<br>will appear here</li>';
      return;
    }
    for (const entry of history) {
      const li = document.createElement("li");
      li.innerHTML = '<div class="h-expr"></div><div class="h-val"></div>';
      li.firstChild.textContent = entry.expr;
      li.lastChild.textContent = "= " + call("fmt", entry.value, mode, 12);
      let last = 0;
      li.addEventListener("click", () => {
        const now = Date.now();
        if (now - last < 350) setText(entry.expr);             // double-tap: edit it again
        else insert(call("fmt", entry.value, "auto", 15).replace(/,/g, ""));
        last = now;
      });
      ul.appendChild(li);
    }
  }
  $("hist-clear").addEventListener("click", () => { history = []; store.set("history", history); renderHistory(); });

  // keys
  const key = (text, kind, action, tip) => {
    const b = document.createElement("button");
    b.className = "key " + kind;
    b.textContent = text;
    if (tip) b.title = tip;
    b.addEventListener("pointerdown", (e) => e.preventDefault());   // keep the caret in the box
    b.addEventListener("click", () => (typeof action === "function" ? action(b) : insert(action)));
    return b;
  };
  const sci = [
    [["sin", "sin(", d.sin], ["cos", "cos(", d.cos], ["tan", "tan(", d.tan], ["π", "π", "pi — 3.14159…"], ["e", "e", "Euler's number 2.71828…"]],
    [["sin⁻¹", "asin(", d.asin], ["cos⁻¹", "acos(", d.acos], ["tan⁻¹", "atan(", d.atan], ["x!", "!", "factorial"], ["|x|", "abs(", d.abs]],
    [["sinh", "sinh(", d.sinh], ["cosh", "cosh(", d.cosh], ["tanh", "tanh(", d.tanh], ["nCr", "nCr(", d.nCr], ["nPr", "nPr(", d.nPr]],
    [["x²", "²", "square"], ["xʸ", "^", "power — 2^10"], ["√", "√(", d.sqrt], ["ʸ√x", "root(", d.root], ["10ˣ", "10^", "ten to the power x"]],
    [["ln", "ln(", d.ln], ["log", "log(", d.log], ["eˣ", "e^", "e to the x"], ["1/x", reciprocal, "reciprocal of the current entry"], ["mod", "mod(", d.mod]],
    [[",", ",", "separates function arguments — log(8, 2)"], ["EE", "e", "× 10 to the power — 6.02 EE 23 enters 6.02e23"],
     ["x=", assignVar, "Store the result in a variable (x = 5, then use x)"], ["const", "const", "Physical & math constants"], ["f(x)", "fx", "All functions"]],
  ];
  const sciPad = $("sci-pad");
  for (const row of sci) for (const [text, action, tip] of row) {
    if (action === "const" || action === "fx") {
      const b = key(text, "fn", (btn) => popover(btn, action === "const"
        ? catalog.constants.map(([n, desc, v]) => [n, `${desc} = ${v}`, () => insert(n)])
        : catalog.functions.map(([n, desc]) => [n + "(…)", desc, () => insert(n + "(")])), tip);
      b.dataset.pop = "1";
      sciPad.appendChild(b);
    } else sciPad.appendChild(key(text, "fn", action, tip));
  }
  const basic = [
    ["C", "clear", clear, "Clear (Esc)"], ["⌫", "clear", backspace, "Delete last character"], ["(", "op", "("], [")", "op", ")"],
    ["7", "", "7"], ["8", "", "8"], ["9", "", "9"], ["÷", "op", "÷"],
    ["4", "", "4"], ["5", "", "5"], ["6", "", "6"], ["×", "op", "×"],
    ["1", "", "1"], ["2", "", "2"], ["3", "", "3"], ["−", "op", "−"],
    ["0", "", "0"], [".", "", "."], ["%", "op", "%", "Percent — 200 + 10% = 220"], ["+", "op", "+"],
    ["±", "", negate, "Change sign"], ["ans", "fn", "ans", "Previous answer"], ["=", "eq", evaluate, "Calculate (Enter)"],
  ];
  for (const [text, kind, action, tip] of basic) $("basic-pad").appendChild(key(text, kind, action, tip));

  edit.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === "=") { e.preventDefault(); evaluate(); }
    else if (e.key === "Escape") { e.preventDefault(); clear(); }
    else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) beforeInsert(e.key);
    else justEvaluated = false;
  });
  edit.addEventListener("input", updatePreview);
  renderHistory();
  pages.calculator = { shown: () => { if (!coarse) edit.focus(); } };
}

// ================================================================ Loan
const PRESETS = {
  "30-year mortgage": [350000, 6.5, 30], "15-year mortgage": [350000, 5.75, 15],
  "Auto loan (5 yr)": [35000, 7.0, 5], "Student loan (10 yr)": [40000, 5.5, 10],
  "Personal loan (3 yr)": [10000, 11.0, 3],
};

function setupLoan() {
  const num = (id) => { const v = parseFloat($(id).value.replace(/[$,\s%]/g, "")); return isFinite(v) ? v : 0; };
  const moneyText = (v) => v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  let result = null;
  const start = new Date();
  start.setMonth(start.getMonth() + 1);
  $("l-start").value = start.toISOString().slice(0, 10);

  seg("l-mode", () => { modeChanged(); recalc(); });
  seg("l-view", renderTable);
  function modeChanged() {
    const borrow = segValue("l-mode") === "borrow";
    for (const id of ["l-amount", "l-amount-label"]) $(id).hidden = borrow;
    for (const id of ["l-budget", "l-budget-label"]) $(id).hidden = !borrow;
  }
  $("l-preset").addEventListener("change", () => {
    const p = PRESETS[$("l-preset").value];
    if (!p) return;
    $("l-amount").value = moneyText(p[0]);
    $("l-rate").value = p[1];
    $("l-term").value = p[2];
    $("l-term-unit").value = "years";
    recalc();
  });
  for (const id of ["l-amount", "l-rate", "l-term"]) $(id).addEventListener("input", () => { $("l-preset").value = "Custom"; });
  for (const id of ["l-amount", "l-budget", "l-rate", "l-term", "l-term-unit", "l-freq", "l-extra", "l-down", "l-start"]) {
    $(id).addEventListener("input", recalc);
    $(id).addEventListener("change", recalc);
  }
  for (const el of document.querySelectorAll("#page-loan .money")) {
    el.addEventListener("blur", () => { el.value = moneyText(num(el.id)); });
  }
  for (const el of document.querySelectorAll("#page-loan .num")) {
    el.addEventListener("focus", () => setTimeout(() => el.select(), 0));
  }

  function recalc() {
    const freq = $("l-freq");
    const r = call("loan", {
      mode: segValue("l-mode"), amount: num("l-amount"), budget: num("l-budget"), rate: num("l-rate"),
      term: Math.max(1, Math.round(num("l-term"))), term_unit: $("l-term-unit").value, ppy: Number(freq.value),
      extra: num("l-extra"), down: num("l-down"), start: $("l-start").value || start.toISOString().slice(0, 10),
    });
    $("l-error").textContent = "";
    if (!r.ok) {
      result = null;
      $("l-error").textContent = r.error;
      for (const id of ["s-payment", "s-interest", "s-total", "s-principal", "s-payoff", "s-count"]) $(id).textContent = "—";
      $("l-saved").textContent = "";
      $("l-table").innerHTML = "";
      return;
    }
    result = r;
    const fname = freq.options[freq.selectedIndex].text;
    $("s-payment-label").textContent = `${fname} payment` + (num("l-extra") ? " + extra" : "");
    $("s-payment").textContent = r.payment;
    $("s-interest").textContent = r.interest;
    $("s-total").textContent = r.total;
    $("s-principal").textContent = r.principal;
    $("s-principal-label").textContent = segValue("l-mode") === "borrow" ? "You can borrow" : "Loan amount";
    $("s-payoff").textContent = r.payoff;
    $("s-count").textContent = r.count;
    const total = r.principal_value + r.interest_value || 1;
    $("pbar-principal").style.width = (100 * r.principal_value / total) + "%";
    $("pbar-interest").style.width = (100 * r.interest_value / total) + "%";
    $("l-saved").textContent = r.saved;
    renderTable();
  }
  function headers() {
    return segValue("l-view") === "every"
      ? ["#", "Date", "Principal", "Interest", "Extra", "Balance"]
      : ["Year", "Payments", "Principal", "Interest", "Extra", "Balance"];
  }
  function renderTable() {
    if (!result) return;
    table($("l-table"), headers(), segValue("l-view") === "every" ? result.every : result.yearly);
  }
  $("l-csv").addEventListener("click", () => {
    if (!result) return;
    const rows = [headers(), ...(segValue("l-view") === "every" ? result.every : result.yearly)];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(",")).join("\r\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    a.download = "amortization.csv";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  modeChanged();
  recalc();
}

// ================================================================ Converter
const NUMBER_BASE = "Number base";

function setupConverter() {
  const cat = call("unit_catalog");
  const names = [...cat.categories, NUMBER_BASE];
  let current = store.get("unit-cat", names[0]);
  if (!names.includes(current)) current = names[0];
  const box = $("cats"), sel = $("cats-select");
  for (const n of names) {
    const b = document.createElement("button");
    b.textContent = n;
    b.addEventListener("click", () => choose(n));
    box.appendChild(b);
    sel.add(new Option(n, n));
  }
  sel.addEventListener("change", () => choose(sel.value));

  function choose(n) {
    current = n;
    store.set("unit-cat", n);
    for (const b of box.children) b.classList.toggle("on", b.textContent === n);
    sel.value = n;
    const bases = n === NUMBER_BASE;
    $("conv-units").hidden = bases;
    $("conv-bases").hidden = !bases;
    if (bases) return;
    for (const id of ["c-from-unit", "c-to-unit"]) {
      const s = $(id);
      s.innerHTML = "";
      for (const u of cat.units[n]) s.add(new Option(u, u));
    }
    $("c-to-unit").selectedIndex = cat.units[n].length > 1 ? 1 : 0;
    convert(true);
  }
  function convert(forward) {
    if (current === NUMBER_BASE) return;
    const [src, dst, su, du] = forward
      ? ["c-from", "c-to", "c-from-unit", "c-to-unit"] : ["c-to", "c-from", "c-to-unit", "c-from-unit"];
    const r = call("convert", $(src).value, current, $(su).value, $(du).value);
    if (!r.ok) { $(dst).value = ""; return; }
    $(dst).value = r.value;
    const f = forward ? r : call("convert", $("c-from").value, current, $("c-from-unit").value, $("c-to-unit").value);
    if (f.ok) {
      $("c-formula").textContent = f.formula;
      table($("c-all"), ["Unit", "Value"], f.rows);
    }
  }
  $("c-from").addEventListener("input", () => convert(true));
  $("c-to").addEventListener("input", () => convert(false));
  $("c-from-unit").addEventListener("change", () => convert(true));
  $("c-to-unit").addEventListener("change", () => convert(true));
  $("c-swap").addEventListener("click", () => {
    const a = $("c-from-unit").selectedIndex;
    $("c-from-unit").selectedIndex = $("c-to-unit").selectedIndex;
    $("c-to-unit").selectedIndex = a;
    convert(true);
  });

  // number bases
  const form = $("bases");
  const edits = {};
  for (const [name, base] of cat.bases) {
    const l = document.createElement("label");
    l.textContent = name;
    const e = document.createElement("input");
    e.spellcheck = false;
    e.autocapitalize = "off";
    if (base === 10) e.inputMode = "numeric";
    e.addEventListener("input", () => baseChanged(e.value, base));
    form.append(l, e);
    edits[base] = e;
  }
  function baseChanged(text, base) {
    const r = call("base_convert", text, base);
    $("base-info").textContent = r.info || "";
    if (!r.ok) return;
    for (const [b, e] of Object.entries(edits)) if (Number(b) !== base) e.value = r.values[b];
  }
  edits[10].value = "255";
  baseChanged("255", 10);
  choose(current);
}

// ================================================================ Graph
const SUB = "₁₂₃₄₅₆";
const MAX_FUNCTIONS = 6;

function setupGraph() {
  const canvas = $("canvas"), ctx = canvas.getContext("2d");
  const saved = store.get("graph", {});
  let curves = (saved.curves || [{ slot: 0, text: "sin(x)" }, { slot: 1, text: "x^2/4 - 2" }])
    .map((c) => ({ slot: c.slot, text: c.text, visible: c.visible !== false, ok: false, error: "" }));
  let params = saved.params || {};
  let angle = saved.angle || "rad";
  let view = { x0: -10, x1: 10, y0: -6, y1: 6 };
  let samples = [], keyPoints = [], hover = null, fitted = false;
  let W = 0, H = 0;
  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const series = (slot) => color("--s" + slot);
  const name = (slot) => "f" + SUB[slot];

  $("show-points").checked = saved.points !== false;
  $("show-tangent").checked = !!saved.tangent;
  setSeg("g-angle", angle);
  seg("g-angle", (v) => { angle = v; refresh(); });
  seg("g-mode", (v) => {
    const t = v === "table";
    canvas.hidden = t;
    $("g-table").hidden = !t;
    $("step-wrap").hidden = !t;
    if (t) fillTable(); else draw();
  });
  $("g-step").addEventListener("input", fillTable);
  $("show-points").addEventListener("change", () => { save(); draw(); });
  $("show-tangent").addEventListener("change", () => { save(); draw(); });
  $("g-out").addEventListener("click", () => zoom(1 / 0.7));
  $("g-in").addEventListener("click", () => zoom(0.7));
  $("g-reset").addEventListener("click", reset);
  $("g-fit").addEventListener("click", fitY);
  $("fn-add").addEventListener("click", () => addCurve(""));

  function save() {
    store.set("graph", { curves: curves.map((c) => ({ slot: c.slot, text: c.text, visible: c.visible })),
      params, angle, points: $("show-points").checked, tangent: $("show-tangent").checked });
  }
  const live = () => curves.filter((c) => c.visible && c.ok);

  // ---------- function rows
  function renderRows() {
    const box = $("fn-rows");
    box.innerHTML = "";
    for (const c of curves) {
      const row = document.createElement("div");
      row.className = "fn-row";
      const dot = document.createElement("button");
      dot.className = "dot";
      dot.style.borderColor = series(c.slot);
      dot.style.background = c.visible ? series(c.slot) : "transparent";
      dot.title = c.visible ? "Hide this graph" : "Show this graph";
      dot.addEventListener("click", () => { c.visible = !c.visible; renderRows(); refresh(); });
      const label = document.createElement("span");
      label.className = "name";
      label.textContent = name(c.slot);
      const input = document.createElement("input");
      input.value = c.text;
      input.placeholder = "e.g. a*x^2 + b";
      input.spellcheck = false;
      input.autocapitalize = "off";
      input.className = c.error ? "bad" : "";
      input.addEventListener("input", () => { c.text = input.value; refresh(); input.className = c.error ? "bad" : ""; err.textContent = c.error; });
      const x = document.createElement("button");
      x.className = "x";
      x.textContent = "×";
      x.title = "Remove";
      x.addEventListener("click", () => { curves = curves.filter((o) => o !== c); renderRows(); refresh(); });
      row.append(dot, label, input, x);
      const err = document.createElement("div");
      err.className = "fn-err";
      err.textContent = c.error;
      box.append(row, err);
    }
    $("fn-add").hidden = curves.length >= MAX_FUNCTIONS;
  }
  function addCurve(text) {
    const used = new Set(curves.map((c) => c.slot));
    const slot = [0, 1, 2, 3, 4, 5].find((s) => !used.has(s));
    if (slot === undefined) return;
    curves.push({ slot, text, visible: true, ok: false, error: "" });
    renderRows();
    const inputs = $("fn-rows").querySelectorAll("input");
    inputs[inputs.length - 1].focus();
    refresh();
  }

  // ---------- parameters
  function renderParams(names) {
    const box = $("param-rows");
    const have = [...box.children].map((r) => r.dataset.name);
    if (have.join() === names.join()) return;
    box.innerHTML = "";
    for (const n of names) {
      if (!(n in params)) params[n] = 1;
      const row = document.createElement("div");
      row.className = "param";
      row.dataset.name = n;
      row.innerHTML = `<b></b><input type="range" min="-10" max="10" step="0.1"><input class="num" inputmode="decimal">`;
      row.querySelector("b").textContent = n;
      const range = row.querySelector("input[type=range]"), numBox = row.querySelector(".num");
      range.value = params[n];
      numBox.value = params[n];
      range.addEventListener("input", () => { params[n] = Number(range.value); numBox.value = range.value; resample(); });
      numBox.addEventListener("input", () => {
        const v = parseFloat(numBox.value);
        if (!isFinite(v)) return;
        params[n] = v;
        if (v < Number(range.min)) range.min = Math.floor(v);
        if (v > Number(range.max)) range.max = Math.ceil(v);
        range.value = v;
        resample();
      });
      box.appendChild(row);
    }
    $("param-card").hidden = names.length === 0;
  }

  // ---------- view
  function px(x) { return (x - view.x0) / (view.x1 - view.x0) * W; }
  function pyy(y) { return (view.y1 - y) / (view.y1 - view.y0) * H; }
  function wx(p) { return view.x0 + p / Math.max(1, W) * (view.x1 - view.x0); }
  function wy(p) { return view.y1 - p / Math.max(1, H) * (view.y1 - view.y0); }
  function reset() {
    const half = 10 * H / Math.max(1, W);
    view = { x0: -10, x1: 10, y0: -half, y1: half };
    resample();
  }
  function zoom(f, cx, cy) {
    cx = cx ?? (view.x0 + view.x1) / 2;
    cy = cy ?? (view.y0 + view.y1) / 2;
    const nw = (view.x1 - view.x0) * f;
    if (!(nw > 1e-9 && nw < 1e9)) return;
    view = { x0: cx - (cx - view.x0) * f, x1: cx + (view.x1 - cx) * f,
             y0: cy - (cy - view.y0) * f, y1: cy + (view.y1 - cy) * f };
    resample();
  }
  function fitY() {
    const r = call("fit_y", live().map((c) => c.text), angle, params, view.x0, view.x1);
    if (r) { view.y0 = r[0]; view.y1 = r[1]; resample(); }
  }

  // ---------- data
  let pointsTimer = 0;
  function refresh() {
    const checks = call("graph_check", curves.map((c) => c.text), angle);
    const paramNames = [];
    curves.forEach((c, i) => {
      c.ok = checks[i].ok;
      c.error = checks[i].error;
      for (const p of checks[i].params) if (!paramNames.includes(p)) paramNames.push(p);
    });
    renderParams(paramNames);
    for (const [i, err] of [...$("fn-rows").querySelectorAll(".fn-err")].entries()) {
      err.textContent = curves[i] ? curves[i].error : "";
      const input = err.previousSibling.querySelector("input");
      if (input) input.className = curves[i] && curves[i].error ? "bad" : "";
    }
    save();
    resample();
  }
  function resample() {
    const lv = live();
    const n = Math.max(200, Math.round(W * 2)) * 2;     // odd samples are midpoints (asymptote test)
    const ys = call("graph_sample", lv.map((c) => c.text), angle, params, view.x0, view.x1, n);
    samples = lv.map((c, i) => ({ slot: c.slot, ys: ys[i], n }));
    draw();
    clearTimeout(pointsTimer);
    pointsTimer = setTimeout(findPoints, 150);
    if (!$("g-table").hidden) fillTable();
    save();
  }
  function findPoints() {
    const lv = live();
    keyPoints = call("graph_points", lv.map((c) => [c.slot, c.text]), angle, params, view.x0, view.x1, view.y0, view.y1);
    const ul = $("points");
    ul.innerHTML = "";
    if (!keyPoints.length) ul.innerHTML = '<li class="empty">None in view</li>';
    for (const kp of keyPoints) {
      const li = document.createElement("li");
      li.innerHTML = "<div></div><small></small>";
      li.firstChild.textContent = kp[4];
      li.lastChild.textContent = kp[5];
      li.addEventListener("click", () => {
        const hw = (view.x1 - view.x0) / 2, hh = (view.y1 - view.y0) / 2;
        view = { x0: kp[0] - hw, x1: kp[0] + hw, y0: kp[1] - hh, y1: kp[1] + hh };
        resample();
      });
      ul.appendChild(li);
    }
    draw();
  }
  function fillTable() {
    if ($("g-table").hidden) return;
    const lv = live();
    const rows = call("graph_table", lv.map((c) => c.text), angle, params, view.x0, view.x1, $("g-step").value);
    table($("g-table"), ["x", ...lv.map((c) => name(c.slot) + "(x)")], rows);
  }

  // ---------- drawing
  function niceStep(span, target) {
    const raw = span / target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    return [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw);
  }
  function tick(v, step) {
    if (Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && v !== 0)) return v.toExponential(2).replace("e+", "e");
    const dec = step < 1 ? Math.max(0, -Math.floor(Math.log10(step))) : 0;
    return v.toFixed(dec).replace("-", "−");
  }
  const fmt6 = (v) => call("fmt", Math.abs(v) < 1e-12 ? 0 : v, "auto", 6);
  function dot(x, y, fill, r = 5) {
    ctx.beginPath();
    ctx.arc(x, y, r, 0, 2 * Math.PI);
    ctx.fillStyle = fill;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = color("--panel");
    ctx.stroke();
  }
  function draw() {
    if (canvas.hidden || !W) return;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = color("--panel");
    ctx.fillRect(0, 0, W, H);
    ctx.font = "11px -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
    const sx = niceStep(view.x1 - view.x0, Math.max(4, Math.floor(W / 90)));
    const sy = niceStep(view.y1 - view.y0, Math.max(4, Math.floor(H / 70)));
    const xs = [], ys = [];
    for (let i = Math.ceil(view.x0 / sx); i <= Math.floor(view.x1 / sx); i++) xs.push(i * sx);
    for (let i = Math.ceil(view.y0 / sy); i <= Math.floor(view.y1 / sy); i++) ys.push(i * sy);
    ctx.strokeStyle = color("--border");
    ctx.lineWidth = 1;
    ctx.beginPath();
    for (const x of xs) { const p = Math.round(px(x)) + .5; ctx.moveTo(p, 0); ctx.lineTo(p, H); }
    for (const y of ys) { const p = Math.round(pyy(y)) + .5; ctx.moveTo(0, p); ctx.lineTo(W, p); }
    ctx.stroke();
    ctx.strokeStyle = color("--muted");
    ctx.globalAlpha = .67;
    ctx.beginPath();
    ctx.moveTo(0, pyy(0)); ctx.lineTo(W, pyy(0));
    ctx.moveTo(px(0), 0); ctx.lineTo(px(0), H);
    ctx.stroke();
    ctx.globalAlpha = 1;
    ctx.fillStyle = color("--muted");
    const axY = Math.min(Math.max(pyy(0), 0), H), axX = Math.min(Math.max(px(0), 0), W);
    ctx.textBaseline = "top";
    for (const x of xs) {
      if (Math.abs(x) < sx / 2) continue;
      const t = tick(x, sx), tw = ctx.measureText(t).width;
      ctx.fillText(t, Math.min(Math.max(px(x) - tw / 2, 2), W - tw - 4), Math.min(Math.max(axY + 4, 2), H - 14));
    }
    ctx.textBaseline = "middle";
    for (const y of ys) {
      if (Math.abs(y) < sy / 2) continue;
      const t = tick(y, sy), tw = ctx.measureText(t).width;
      ctx.fillText(t, Math.min(Math.max(axX - tw - 6, 2), W - tw - 4), pyy(y));
    }

    // curves
    const spanH = view.y1 - view.y0;
    for (const s of samples) {
      const ys2 = s.ys, n = s.n;
      if (!ys2 || !ys2.length) continue;
      ctx.strokeStyle = series(s.slot);
      ctx.lineWidth = 2;
      ctx.lineJoin = ctx.lineCap = "round";
      ctx.beginPath();
      let prev = null;
      for (let i = 0; i <= n; i += 2) {
        const y = ys2[i];
        if (y == null) { prev = null; continue; }
        const X = px(view.x0 + (view.x1 - view.x0) * i / n), Y = Math.max(-1e5, Math.min(1e5, pyy(y)));
        if (prev !== null && Math.abs(y - prev) > spanH * 2) {
          const ym = ys2[i - 1];
          if (ym == null || !(Math.min(y, prev) <= ym && ym <= Math.max(y, prev))) prev = null;
        }
        if (prev === null) ctx.moveTo(X, Y); else ctx.lineTo(X, Y);
        prev = y;
      }
      ctx.stroke();
    }

    if ($("show-points").checked) {
      for (const kp of keyPoints) dot(px(kp[0]), pyy(kp[1]), kp[2] === "intersection" ? color("--text") : series(kp[3][0]));
    }
    drawHover();
  }
  function drawHover() {
    const tip = $("tip");
    if (!hover || drag) { tip.hidden = true; return; }
    const [hx, hy] = hover;
    const rect = canvas.getBoundingClientRect();
    if ($("show-points").checked && keyPoints.length) {
      let best = null, bd = Infinity;
      for (const kp of keyPoints) {
        const dd = (px(kp[0]) - hx) ** 2 + (pyy(kp[1]) - hy) ** 2;
        if (dd < bd) { bd = dd; best = kp; }
      }
      if (best && bd < (coarse ? 400 : 100)) {
        dot(px(best[0]), pyy(best[1]), color("--text"), 6);
        showTip(rect, px(best[0]), pyy(best[1]), [[null, best[4], true], [null, "x = " + fmt6(best[0])], [null, "y = " + fmt6(best[1])]]);
        return;
      }
    }
    const x = wx(hx);
    ctx.strokeStyle = color("--muted");
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(hx, 0); ctx.lineTo(hx, H); ctx.stroke();
    const lv = live();
    const vals = call("graph_eval", lv.map((c) => c.text), angle, params, x);
    const lines = [[null, "x = " + fmt6(x), true]];
    let nearest = null;
    lv.forEach((c, i) => {
      const v = vals[i];
      if (v == null) { lines.push([series(c.slot), name(c.slot) + " undefined"]); return; }
      const [y, slope] = v;
      const Y = pyy(y);
      if (Y >= 0 && Y <= H) dot(hx, Y, series(c.slot), 4);
      if (!$("show-tangent").checked || slope == null) { lines.push([series(c.slot), `${name(c.slot)} = ${fmt6(y)}`]); return; }
      lines.push([series(c.slot), `${name(c.slot)} = ${fmt6(y)}   slope ${fmt6(slope)}`]);
      const dist = Math.abs(Y - hy);
      if (!nearest || dist < nearest[0]) nearest = [dist, c, y, slope];
    });
    if (nearest) {
      const [, c, y, slope] = nearest;
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = series(c.slot);
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(0, pyy(y + slope * (view.x0 - x)));
      ctx.lineTo(W, pyy(y + slope * (view.x1 - x)));
      ctx.stroke();
      ctx.restore();
    }
    if (lines.length > 1) showTip(rect, hx, hy, lines); else tip.hidden = true;
  }
  function showTip(rect, x, y, lines) {
    const tip = $("tip");
    tip.innerHTML = "";
    for (const [c, t, bold] of lines) {
      const div = document.createElement("div");
      if (c) { const k = document.createElement("span"); k.style.cssText = `display:inline-block;width:10px;height:3px;border-radius:2px;background:${c};margin-right:6px;vertical-align:middle`; div.appendChild(k); }
      div.appendChild(document.createTextNode(t));
      if (bold) div.style.fontWeight = "600";
      tip.appendChild(div);
    }
    tip.hidden = false;
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let left = rect.left + x + 14;
    if (left + tw > rect.right) left = rect.left + x - 14 - tw;
    const top = Math.min(Math.max(rect.top + 4, rect.top + y - th / 2), rect.bottom - th - 4);
    tip.style.left = left + "px";
    tip.style.top = top + "px";
  }

  // ---------- pointer: drag, wheel, pinch, trace
  let drag = null;
  const pointers = new Map();
  let pinch = null;
  const local = (e) => { const r = canvas.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top]; };
  canvas.addEventListener("pointerdown", (e) => {
    canvas.setPointerCapture(e.pointerId);
    pointers.set(e.pointerId, local(e));
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), view: { ...view } };
      drag = null;
    } else {
      drag = { start: local(e), view: { ...view }, moved: false, touch: e.pointerType === "touch" };
      if (e.pointerType === "touch") { hover = local(e); draw(); }
    }
  });
  canvas.addEventListener("pointermove", (e) => {
    const p = local(e);
    if (pointers.has(e.pointerId)) pointers.set(e.pointerId, p);
    if (pinch && pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
      const f = pinch.d / Math.max(10, d);
      const cxp = (a[0] + b[0]) / 2, cyp = (a[1] + b[1]) / 2;
      const v = pinch.view;
      const cx = v.x0 + cxp / W * (v.x1 - v.x0), cy = v.y1 - cyp / H * (v.y1 - v.y0);
      view = { x0: cx - (cx - v.x0) * f, x1: cx + (v.x1 - cx) * f, y0: cy - (cy - v.y0) * f, y1: cy + (v.y1 - cy) * f };
      hover = null;
      resample();
      return;
    }
    if (drag) {
      // A touch traces; a mouse drags. A touch that moves far starts panning instead.
      if (drag.touch && !drag.moved && Math.hypot(p[0] - drag.start[0], p[1] - drag.start[1]) < 12) {
        hover = p; draw(); return;
      }
      if (drag.touch && !drag.pan) {
        // Horizontal finger movement keeps tracing; a clear vertical move pans.
        if (Math.abs(p[1] - drag.start[1]) < 24 && !drag.moved) { hover = p; draw(); return; }
        drag.pan = true;
      }
      drag.moved = true;
      canvas.classList.add("dragging");
      const v = drag.view;
      const dx = (p[0] - drag.start[0]) / W * (v.x1 - v.x0), dy = (p[1] - drag.start[1]) / H * (v.y1 - v.y0);
      view = { x0: v.x0 - dx, x1: v.x1 - dx, y0: v.y0 + dy, y1: v.y1 + dy };
      hover = null;
      resample();
      return;
    }
    if (e.pointerType === "mouse") { hover = p; draw(); }
  });
  const end = (e) => {
    pointers.delete(e.pointerId);
    if (pointers.size < 2) pinch = null;
    if (pointers.size === 0) {
      drag = null;
      canvas.classList.remove("dragging");
      if (e.pointerType === "touch") { hover = null; draw(); }
    }
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
  canvas.addEventListener("pointerleave", (e) => { if (e.pointerType === "mouse") { hover = null; draw(); } });
  canvas.addEventListener("wheel", (e) => {
    e.preventDefault();
    const [x, y] = local(e);
    zoom(Math.pow(1.0015, e.deltaY), wx(x), wy(y));
  }, { passive: false });

  function resize() {
    const r = canvas.getBoundingClientRect();
    if (!r.width) return;
    const dpr = window.devicePixelRatio || 1;
    const oldW = W, oldH = H;
    W = r.width; H = r.height;
    canvas.width = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    if (!fitted) { fitted = true; reset(); return; }
    if (oldW && oldH) {     // keep the scale; grow or shrink the visible area
      const cx = (view.x0 + view.x1) / 2, cy = (view.y0 + view.y1) / 2;
      const hw = (view.x1 - view.x0) / 2 * W / oldW, hh = (view.y1 - view.y0) / 2 * H / oldH;
      view = { x0: cx - hw, x1: cx + hw, y0: cy - hh, y1: cy + hh };
    }
    resample();
  }
  new ResizeObserver(resize).observe(canvas);
  renderRows();
  refresh();
  pages.graph = { shown: resize };
}

// ================================================================ start
async function main() {
  const fill = $("loading-fill"), text = $("loading-text");
  const step = (pct, msg) => { fill.style.width = pct + "%"; if (msg) text.textContent = msg; };
  try {
    step(10, "Loading Python…");
    pyodide = await loadPyodide();
    step(70, "Loading MJSCalc’s calculation engine…");
    pyodide.FS.mkdirTree("/home/pyodide/mjscalc/engine");
    const files = await Promise.all([...ENGINE_FILES.map((f) => "py/mjscalc/" + f), "bridge.py"].map(async (path) => {
      const r = await fetch(path, { cache: "no-cache" });
      if (!r.ok) throw new Error(`${path}: ${r.status}`);
      return [path, await r.text()];
    }));
    for (const [path, src] of files) {
      const dest = path === "bridge.py" ? "/home/pyodide/bridge.py" : "/home/pyodide/" + path.slice(3);
      pyodide.FS.writeFile(dest, src);
    }
    step(90, "Starting…");
    py = pyodide.pyimport("bridge");
    setupNav();
    setupCalculator();
    setupLoan();
    setupConverter();
    setupGraph();
    step(100);
    $("loading").hidden = true;
    const page = store.get("page", "calculator");
    showPage(["calculator", "graph", "loan", "converter"].includes(page) ? page : "calculator");
  } catch (err) {
    console.error(err);
    $("loading").classList.add("failed");
    text.textContent = "Sorry — MJSCalc couldn’t start in this browser. Try reloading, or download the app.";
  }
}
main();
