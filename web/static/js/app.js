/* PricePulse dashboard — vanilla JS, no build step. */
(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const state = {
    products: [],
    summary: null,
    filter: "all",
    search: "",
    sort: "recent",
    editingId: null,
    deleteId: null,
    preview: null,
    chartProductId: null,
    chartDays: 30,
    chart: null,
    chartData: null,
    loading: false,
  };

  const SHOP_NAMES = {
    demo: "Demo Store",
    wildberries: "Wildberries",
    ozon: "Ozon",
  };
  const DEMO_SLUGS = [
    "aurora-headphones",
    "nova-watch",
    "pulse-keyboard",
    "drift-sneakers",
    "brew-coffee",
    "nomad-backpack",
    "halo-lamp",
    "echo-speaker",
  ];
  const KIND_LABELS = {
    target: "Цель достигнута",
    discount: "Скидка к медиане",
    price_drop: "Цена снизилась",
    error: "Ошибка парсера",
  };
  const KIND_ICONS = { target: "🎯", discount: "🔥", price_drop: "📉", error: "⚠️" };

  const nf0 = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 });
  const nf1 = new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 1 });
  const rtf = new Intl.RelativeTimeFormat("ru", { numeric: "auto" });
  const dateFmt = new Intl.DateTimeFormat("ru-RU", { day: "numeric", month: "short" });
  const timeFmt = new Intl.DateTimeFormat("ru-RU", { hour: "2-digit", minute: "2-digit" });
  const fullFmt = new Intl.DateTimeFormat("ru-RU", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  /* ------------------------------ utils ------------------------------ */

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function stripHtml(html) {
    const doc = new DOMParser().parseFromString(String(html || ""), "text/html");
    return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
  }

  function fmtMoney(value, currency = "RUB") {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const symbol = { RUB: "₽", USD: "$", EUR: "€" }[currency] || currency;
    return `${nf0.format(Number(value))} ${symbol}`;
  }

  function fmtPct(value, withSign = false) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
    const number = Number(value);
    const sign = withSign && number > 0 ? "+" : "";
    return `${sign}${nf1.format(number)}%`;
  }

  function relativeTime(iso) {
    if (!iso) return "—";
    const date = new Date(iso);
    const diff = (date.getTime() - Date.now()) / 1000;
    const abs = Math.abs(diff);
    if (abs < 45) return "только что";
    if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
    if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
    if (abs < 86400 * 7) return rtf.format(Math.round(diff / 86400), "day");
    return dateFmt.format(date);
  }

  function clockTime(iso) {
    if (!iso) return "—";
    return timeFmt.format(new Date(iso));
  }

  function debounce(fn, ms = 250) {
    let timer;
    return (...args) => {
      clearTimeout(timer);
      timer = setTimeout(() => fn(...args), ms);
    };
  }

  function icon(name, cls = "icon") {
    return `<svg class="${cls}"><use href="#i-${name}"/></svg>`;
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    if (response.status === 204) return null;
    let payload = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    if (!response.ok) {
      let detail = "Не удалось выполнить запрос";
      if (payload && typeof payload === "object") {
        if (typeof payload.detail === "string") detail = payload.detail;
        else if (Array.isArray(payload.detail)) {
          detail = payload.detail.map((item) => item.msg).join("; ");
        }
      }
      const error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return payload;
  }

  /* ------------------------------ toasts ------------------------------ */

  function toast(type, title, text = "") {
    const stack = $("#toastStack");
    const node = document.createElement("div");
    node.className = `toast toast-${type}`;
    const iconName = type === "error" ? "x" : type === "success" ? "check" : "spark";
    node.innerHTML = `
      <span class="toast-icon">${icon(iconName, "icon icon-xs")}</span>
      <span class="toast-body"><strong>${escapeHtml(title)}</strong>${text ? `<span>${escapeHtml(text)}</span>` : ""}</span>`;
    stack.appendChild(node);
    setTimeout(() => {
      node.classList.add("is-out");
      setTimeout(() => node.remove(), 320);
    }, 4200);
  }

  /* ------------------------------ modals ------------------------------ */

  const modalIds = ["chartModal", "formModal", "confirmModal", "notificationsDrawer"];

  function openModal(id) {
    const node = document.getElementById(id);
    if (!node) return;
    node.hidden = false;
    document.body.classList.add("no-scroll");
    if (id === "formModal") {
      setTimeout(() => $("#productUrl")?.focus(), 80);
    }
  }

  function closeModal(id) {
    const node = document.getElementById(id);
    if (!node) return;
    node.hidden = true;
    if (id === "chartModal") destroyChart();
    if (!modalIds.some((modalId) => !document.getElementById(modalId)?.hidden)) {
      document.body.classList.remove("no-scroll");
    }
  }

  function closeAllModals() {
    modalIds.forEach(closeModal);
  }

  /* ------------------------------ theme ------------------------------ */

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("pricepulse-theme", theme);
    const meta = $('meta[name="theme-color"]');
    if (meta) meta.content = theme === "light" ? "#f2f3f8" : "#06070b";
    if (state.chartData && !$("#chartModal").hidden) renderChart(state.chartData);
  }

  function initTheme() {
    const saved = localStorage.getItem("pricepulse-theme");
    const preferred = window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
    applyTheme(saved || preferred);
    $("#themeToggle").addEventListener("click", () => {
      applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
    });
  }

  /* ------------------------------ data ------------------------------ */

  async function loadAll({ quiet = false } = {}) {
    if (!quiet) {
      $("#skeletonGrid").classList.add("is-visible");
      $("#productGrid").innerHTML = "";
      $("#emptyState").hidden = true;
    }
    try {
      const [products, summary] = await Promise.all([api("/api/products"), api("/api/summary")]);
      state.products = products;
      state.summary = summary;
      renderSummary();
      renderProducts();
      renderHero();
      renderTelegramStatus();
    } catch (error) {
      toast("error", "API недоступен", error.message);
      $("#productGrid").innerHTML = "";
      $("#emptyState").hidden = false;
      $("#emptyTitle").textContent = "Не удалось загрузить данные";
      $("#emptyText").textContent = "Проверьте, что сервер запущен, и обновите страницу.";
    } finally {
      $("#skeletonGrid").classList.remove("is-visible");
    }
  }

  async function refreshSummary() {
    try {
      state.summary = await api("/api/summary");
      renderSummary();
      renderTelegramStatus();
    } catch {
      /* silent background refresh */
    }
  }

  /* ------------------------------ summary ------------------------------ */

  function animateValue(element, target, suffix = "", decimals = 0) {
    if (!element) return;
    const to = Number(target) || 0;
    const from = Number(element.dataset.value || 0);
    element.dataset.value = String(to);
    const duration = 650;
    const started = performance.now();
    const format = decimals ? nf1 : nf0;

    function frame(now) {
      const progress = Math.min(1, (now - started) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      const value = from + (to - from) * eased;
      element.textContent = `${format.format(value)}${suffix}`;
      if (progress < 1) requestAnimationFrame(frame);
      else element.textContent = `${format.format(to)}${suffix}`;
    }
    requestAnimationFrame(frame);
  }

  function renderSummary() {
    const summary = state.summary;
    if (!summary) return;

    animateValue($("#statTotal"), summary.total_products);
    animateValue($("#statBelow"), summary.below_target);
    animateValue($("#statDiscount"), summary.average_discount ?? 0, "%", 1);
    animateValue($("#statChecks"), summary.checks_today);

    $("#statActiveTag").textContent = `${summary.active_products} активных`;
    $("#statTargetTag").textContent = `${summary.with_target} с целью`;
    $("#statDiscountTag").textContent =
      summary.average_discount === null ? "нет данных" : "от пика";
    $("#statSchedulerTag").textContent = summary.scheduler_running ? "онлайн" : "выключен";
    $("#statNext").textContent = summary.next_check_at
      ? `следующая в ${clockTime(summary.next_check_at)}`
      : "по расписанию";

    $("#schedulerLabel").textContent = summary.scheduler_running
      ? "планировщик активен"
      : "планировщик выключен";
    $("#nextCheckLabel").textContent = `каждые ${nf1.format(summary.check_interval_hours)} ч`;

    $("#heroSavings").textContent = fmtMoney(summary.savings_from_peak);
    $("#heroBelow").textContent = String(summary.below_target);
    $("#heroChecks").textContent = String(summary.checks_today);
    $("#floatSaved").textContent = `−${fmtMoney(summary.savings_from_peak)}`;
    $("#bellDot").hidden = summary.notifications_sent === 0;
  }

  function renderTelegramStatus() {
    const summary = state.summary;
    if (!summary) return;
    const box = $("#tgStatus");
    const text = $("#tgStatusText");
    if (summary.telegram_configured) {
      box.classList.remove("is-off");
      text.textContent = "Подключён — алерты уходят в чат";
    } else {
      box.classList.add("is-off");
      text.textContent = "Демо-режим — события копятся в ленте";
    }
  }

  /* ------------------------------ hero ------------------------------ */

  function pickHeroProduct() {
    const withSpark = state.products.filter((product) => product.sparkline?.length > 1);
    return (
      withSpark.sort((a, b) => (b.savings_from_peak || 0) - (a.savings_from_peak || 0))[0] ||
      state.products[0] ||
      null
    );
  }

  function renderHero() {
    const product = pickHeroProduct();
    const title = $("#heroTitle");
    const shop = $("#heroShop");
    const price = $("#heroPrice");
    const old = $("#heroOld");
    const delta = $("#heroDelta");
    const target = $("#heroTarget");
    const thumb = $("#heroThumb");
    const monitor = $("#heroMonitor");

    if (!product) {
      title.textContent = "Добавьте первый товар";
      shop.textContent = "PricePulse";
      price.textContent = "—";
      old.textContent = "";
      delta.hidden = true;
      target.textContent = "цель не задана";
      thumb.innerHTML = "";
      monitor.onclick = null;
      monitor.style.cursor = "default";
      $("#heroLinePath").setAttribute("d", "M0 82 L70 74 L140 86 L210 62 L280 70 L350 48 L420 56");
      $("#heroFillPath").setAttribute("d", "M0 82 L70 74 L140 86 L210 62 L280 70 L350 48 L420 56 L420 120 L0 120 Z");
      return;
    }

    delta.hidden = false;
    title.textContent = product.title;
    shop.textContent = SHOP_NAMES[product.shop] || product.shop;
    price.textContent = fmtMoney(product.current_price, product.currency);
    if (product.max_price && product.current_price && product.max_price > product.current_price) {
      old.textContent = fmtMoney(product.max_price, product.currency);
      old.hidden = false;
    } else {
      old.hidden = true;
    }

    const change = product.delta_percent_24h;
    delta.textContent = change === null ? "без изменений" : fmtPct(change, true);
    delta.className = `chip ${change !== null && change > 0 ? "chip-danger" : "chip-lime"}`;
    target.textContent = product.target_price
      ? `цель ${fmtMoney(product.target_price, product.currency)}`
      : "цель не задана";

    thumb.innerHTML = product.image_url
      ? `<img src="${escapeHtml(product.image_url)}" alt="">`
      : `<span style="font-size:13px;font-weight:800">${escapeHtml((product.title || "?")[0])}</span>`;
    const img = thumb.querySelector("img");
    if (img) {
      img.addEventListener("error", () => {
        img.remove();
        thumb.textContent = (product.title || "?")[0];
      });
    }

    const values = product.sparkline?.length > 1 ? product.sparkline : [product.current_price, product.current_price];
    drawSpark($("#heroLinePath"), $("#heroFillPath"), values, 420, 120);
    monitor.onclick = () => openChart(product.id);
    monitor.style.cursor = "pointer";
    $("#floatSaved").textContent = `−${fmtMoney(product.savings_from_peak || 0, product.currency)}`;
  }

  /* ------------------------------ sparklines ------------------------------ */

  function buildPoints(values, width, height, padding = 4) {
    const min = Math.min(...values);
    const max = Math.max(...values);
    const span = max - min || 1;
    const step = values.length > 1 ? width / (values.length - 1) : width;
    return values.map((value, index) => {
      const x = index * step;
      const y = height - padding - ((value - min) / span) * (height - padding * 2);
      return [Number(x.toFixed(2)), Number(y.toFixed(2))];
    });
  }

  function pathFrom(points, closePath, width, height) {
    if (!points.length) return "";
    const line = points.map(([x, y], index) => `${index ? "L" : "M"}${x} ${y}`).join(" ");
    return closePath ? `${line} L${width} ${height} L0 ${height} Z` : line;
  }

  function drawSpark(lineEl, fillEl, values, width, height) {
    const points = buildPoints(values, width, height);
    if (lineEl) lineEl.setAttribute("d", pathFrom(points, false, width, height));
    if (fillEl) fillEl.setAttribute("d", pathFrom(points, true, width, height));
  }

  function sparklineSvg(product, index) {
    const values = product.sparkline?.length > 1 ? product.sparkline : [1, 1];
    const points = buildPoints(values, 220, 48, 3);
    const gradientId = `spark-grad-${product.id}-${index}`;
    const line = pathFrom(points, false, 220, 48);
    const area = pathFrom(points, true, 220, 48);
    return `
      <svg viewBox="0 0 220 48" preserveAspectRatio="none" aria-hidden="true">
        <defs>
          <linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="currentColor" stop-opacity=".28"/>
            <stop offset="100%" stop-color="currentColor" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <path d="${area}" fill="url(#${gradientId})"></path>
        <path d="${line}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
      </svg>`;
  }

  /* ------------------------------ products ------------------------------ */

  function filteredProducts() {
    const query = state.search.trim().toLowerCase();
    let items = state.products.filter((product) => {
      if (state.filter === "active" && product.status !== "active") return false;
      if (state.filter === "paused" && product.status !== "paused") return false;
      if (state.filter === "error" && product.status !== "error") return false;
      if (state.filter === "below" && !product.below_target) return false;
      if (query && !product.title.toLowerCase().includes(query)) return false;
      return true;
    });

    const sorters = {
      recent: (a, b) => new Date(b.last_checked_at || b.created_at) - new Date(a.last_checked_at || a.created_at),
      discount: (a, b) => (b.discount_percent ?? -999) - (a.discount_percent ?? -999),
      price_asc: (a, b) => (a.current_price ?? Infinity) - (b.current_price ?? Infinity),
      price_desc: (a, b) => (b.current_price ?? -Infinity) - (a.current_price ?? -Infinity),
      title: (a, b) => a.title.localeCompare(b.title, "ru"),
    };
    items = items.sort(sorters[state.sort] || sorters.recent);
    return items;
  }

  function statusPill(product) {
    if (product.status === "error") {
      return `<span class="status-pill is-error">Ошибка · ${product.error_count}</span>`;
    }
    if (product.status === "paused") return `<span class="status-pill">На паузе</span>`;
    if (product.below_target) return `<span class="status-pill is-below is-active">Ниже цели</span>`;
    return `<span class="status-pill is-active">Активен</span>`;
  }

  function productCard(product, index) {
    const currency = product.currency || "RUB";
    const delta = product.delta_percent_24h;
    const deltaClass = delta === null ? "flat" : delta < 0 ? "down" : delta > 0 ? "up" : "flat";
    const deltaIcon = delta !== null && delta > 0 ? "trend-up" : "trend-down";
    const deltaText = delta === null ? "—" : fmtPct(Math.abs(delta));
    const progress = product.target_progress;
    const targetHead = product.target_price
      ? `<span>Цель <b>${fmtMoney(product.target_price, currency)}</b></span><span>${Math.round(progress ?? 0)}%</span>`
      : `<span>Цель не задана</span><span>—</span>`;
    const progressWidth = product.target_price ? Math.min(100, Math.max(2, progress ?? 0)) : 0;
    const isPaused = product.status === "paused";
    const actionIcon = isPaused ? "play" : "pause";
    const actionTitle = isPaused ? "Возобновить" : "Поставить на паузу";
    const sparkClass = delta !== null && delta > 0 ? "pc-spark is-up" : "pc-spark";
    const belowBadge = product.below_target ? `<span class="below-badge">У цели</span>` : "";

    return `
      <article class="product-card ${isPaused ? "is-paused" : ""} ${product.status === "error" ? "is-error" : ""}"
               data-product-id="${product.id}" tabindex="0" style="animation-delay:${Math.min(index * 45, 360)}ms"
               aria-label="${escapeHtml(product.title)}">
        <div class="pc-media">
          <div class="pc-badges">
            <span class="shop-badge" data-shop="${escapeHtml(product.shop)}">${escapeHtml(SHOP_NAMES[product.shop] || product.shop)}</span>
            ${belowBadge}
          </div>
          <div class="pc-actions">
            <button class="mini-btn" data-action="chart" type="button" title="График цены" aria-label="График цены">${icon("chart", "icon")}</button>
            <button class="mini-btn" data-action="check" type="button" title="Проверить сейчас" aria-label="Проверить сейчас">${icon("refresh", "icon")}</button>
            <button class="mini-btn" data-action="toggle" type="button" title="${actionTitle}" aria-label="${actionTitle}">${icon(actionIcon, "icon")}</button>
            <button class="mini-btn" data-action="edit" type="button" title="Изменить порог" aria-label="Изменить порог">${icon("edit", "icon")}</button>
            <button class="mini-btn is-danger" data-action="delete" type="button" title="Удалить" aria-label="Удалить">${icon("trash", "icon")}</button>
          </div>
          ${product.image_url
            ? `<img data-image src="${escapeHtml(product.image_url)}" alt="${escapeHtml(product.title)}" loading="lazy">`
            : `<div class="pc-image-fallback">${escapeHtml((product.title || "?")[0])}</div>`}
        </div>
        <div class="pc-body">
          <div class="pc-meta">
            <span class="pc-category">${escapeHtml(product.shop === "demo" ? "Demo Store" : SHOP_NAMES[product.shop] || product.shop)}</span>
            <span>${relativeTime(product.last_checked_at)}</span>
          </div>
          <h3 class="pc-title">${escapeHtml(product.title)}</h3>
          <div class="pc-price-row">
            <span class="pc-price">${fmtMoney(product.current_price, currency)}</span>
            <span class="pc-delta ${deltaClass}">${icon(deltaIcon, "icon")}${deltaText}</span>
          </div>
          <div class="pc-target">
            <div class="pc-target-head">${targetHead}</div>
            <div class="progress ${progress >= 100 ? "is-full" : ""}"><i style="width:${progressWidth}%"></i></div>
          </div>
          <div class="${sparkClass}">${sparklineSvg(product, index)}</div>
          ${product.status === "error" && product.last_error
            ? `<div class="pc-error">${icon("x", "icon icon-xs")}<span>${escapeHtml(product.last_error)}</span></div>`
            : ""}
          <div class="pc-foot">
            ${statusPill(product)}
            <button class="link-btn" data-action="chart" type="button">История ${icon("chevron", "icon")}</button>
          </div>
        </div>
      </article>`;
  }

  function renderProducts() {
    const grid = $("#productGrid");
    const items = filteredProducts();
    const total = state.products.length;

    $("#productsCount").textContent = String(total);
    $$("[data-filter-count]").forEach((node) => {
      const key = node.dataset.filterCount;
      if (key === "all") node.textContent = String(total);
      if (key === "active") node.textContent = String(state.products.filter((p) => p.status === "active").length);
      if (key === "below") node.textContent = String(state.products.filter((p) => p.below_target).length);
      if (key === "paused") node.textContent = String(state.products.filter((p) => p.status === "paused").length);
      if (key === "error") node.textContent = String(state.products.filter((p) => p.status === "error").length);
    });

    const active = state.products.filter((p) => p.status === "active").length;
    $("#productsSub").textContent = total
      ? `${total} товаров · ${active} активны · ${items.length} в выборке`
      : "Добавьте первый товар, чтобы начать следить за ценой";

    grid.innerHTML = items.map(productCard).join("");
    grid.hidden = items.length === 0;

    $$("img[data-image]", grid).forEach((img) => {
      img.addEventListener("error", () => {
        const fallback = document.createElement("div");
        fallback.className = "pc-image-fallback";
        fallback.textContent = (img.alt || "?")[0];
        img.replaceWith(fallback);
      });
    });

    const empty = $("#emptyState");
    if (items.length === 0) {
      empty.hidden = false;
      if (total === 0) {
        $("#emptyTitle").textContent = "Пока пусто";
        $("#emptyText").textContent =
          "Добавьте ссылку на товар из Demo Store, Wildberries или Ozon — и мы начнём следить за ценой.";
      } else {
        $("#emptyTitle").textContent = "Ничего не найдено";
        $("#emptyText").textContent = "Попробуйте другой фильтр или очистите поиск.";
      }
    } else {
      empty.hidden = true;
    }
  }

  function findProduct(id) {
    return state.products.find((product) => product.id === Number(id));
  }

  async function handleCardAction(action, id) {
    const product = findProduct(id);
    if (!product) return;

    if (action === "chart") return openChart(id);
    if (action === "edit") return openEditModal(id);
    if (action === "delete") return openDeleteModal(id);
    if (action === "check") return checkOne(id);
    if (action === "toggle") {
      const nextStatus = product.status === "paused" ? "active" : "paused";
      try {
        await api(`/api/products/${id}`, {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
        });
        toast("success", nextStatus === "paused" ? "Отслеживание на паузе" : "Снова следим", product.title);
        await loadAll({ quiet: true });
      } catch (error) {
        toast("error", "Не удалось изменить статус", error.message);
      }
    }
  }

  async function checkOne(id) {
    const product = findProduct(id);
    if (!product) return;
    toast("info", "Проверяем цену…", product.title);
    try {
      const result = await api(`/api/products/${id}/check?force=true`, { method: "POST" });
      if (result.status === "error") {
        toast("error", "Парсер не смог прочитать страницу", result.error || "");
      } else if (result.changed) {
        toast("success", "Цена изменилась", `${fmtMoney(result.old_price)} → ${fmtMoney(result.price)}`);
      } else {
        toast("info", "Цена без изменений", `${fmtMoney(result.price)} · ${product.title}`);
      }
      await loadAll({ quiet: true });
      if (state.chartProductId === Number(id) && !$("#chartModal").hidden) {
        await loadChartData(state.chartDays);
      }
    } catch (error) {
      toast("error", "Ошибка проверки", error.message);
    }
  }

  async function checkAll() {
    if (state.loading) return;
    if (!state.products.length) {
      toast("info", "Сначала добавьте товар", "Проверять пока нечего.");
      return;
    }
    state.loading = true;
    const button = $("#checkAllBtn");
    button.classList.add("is-loading");
    button.disabled = true;
    const iconNode = button.querySelector("use");
    if (iconNode) iconNode.setAttribute("href", "#i-refresh");
    button.querySelector("svg")?.classList.add("spin");

    try {
      const summary = await api("/api/check", {
        method: "POST",
        body: JSON.stringify({ force: true }),
      });
      if (summary.checked === 0 && summary.skipped === 0 && summary.failed === 0) {
        toast("info", "Проверка уже идёт", "Попробуйте через несколько секунд.");
      } else if (summary.failed > 0) {
        toast(
          "error",
          `Проверено: ${summary.checked + summary.failed}`,
          `${summary.failed} ошибок · ${summary.changed} изменений`,
        );
      } else {
        toast(
          "success",
          "Проверка завершена",
          `${summary.checked} товаров · ${summary.changed} изменений · ${summary.notifications} алертов`,
        );
      }
      await loadAll({ quiet: true });
      if (state.chartProductId && !$("#chartModal").hidden) {
        await loadChartData(state.chartDays);
      }
    } catch (error) {
      toast("error", "Не удалось запустить проверку", error.message);
    } finally {
      state.loading = false;
      button.classList.remove("is-loading");
      button.disabled = false;
      button.querySelector("svg")?.classList.remove("spin");
    }
  }

  /* ------------------------------ add / edit ------------------------------ */

  function resetForm() {
    $("#productForm").reset();
    $("#formError").hidden = true;
    $("#previewCard").hidden = true;
    $("#urlField").hidden = false;
    $("#productUrl").disabled = false;
    state.preview = null;
    $("#submitProduct .btn-label").textContent = "Добавить товар";
    $("#formKicker").textContent = "Новый товар";
    $("#formTitle").textContent = "Добавить в трекер";
    $("#formLead").textContent = "Вставьте ссылку — название и цену достанем сами.";
    $("#formModal .modal-panel").classList.remove("is-editing");
  }

  function openAddModal() {
    state.editingId = null;
    resetForm();
    openModal("formModal");
  }

  function openEditModal(id) {
    const product = findProduct(id);
    if (!product) return;
    state.editingId = product.id;
    resetForm();
    state.editingId = product.id;
    $("#urlField").hidden = true;
    $("#formKicker").textContent = "Настройки товара";
    $("#formTitle").textContent = "Изменить порог";
    $("#formLead").textContent = "Цена, скидка и статус отслеживания — всё в одном месте.";
    $("#submitProduct .btn-label").textContent = "Сохранить";
    $("#targetPrice").value = product.target_price ?? "";
    $("#targetDiscount").value = product.target_discount_percent ?? "";
    showPreview({
      title: product.title,
      price: product.current_price,
      currency: product.currency,
      shop: product.shop,
      image_url: product.image_url,
      in_stock: true,
    });
    openModal("formModal");
  }

  function showPreview(data) {
    state.preview = data;
    $("#previewCard").hidden = false;
    $("#previewShop").textContent = SHOP_NAMES[data.shop] || data.shop;
    $("#previewTitle").textContent = data.title;
    $("#previewPrice").textContent = fmtMoney(data.price, data.currency);
    $("#previewStock").textContent = data.in_stock ? "в наличии" : "нет в наличии";
    const img = $("#previewImg");
    img.src = data.image_url || "";
    img.alt = data.title;
    img.style.display = data.image_url ? "" : "none";
  }

  async function previewUrl() {
    const url = $("#productUrl").value.trim();
    const errorBox = $("#formError");
    errorBox.hidden = true;
    if (!url) {
      errorBox.textContent = "Вставьте ссылку на товар.";
      errorBox.hidden = false;
      return;
    }
    if (!/^https?:\/\//i.test(url)) {
      errorBox.textContent = "Ссылка должна начинаться с http:// или https://";
      errorBox.hidden = false;
      return;
    }
    const button = $("#previewBtn");
    button.disabled = true;
    button.textContent = "Проверяем…";
    try {
      const data = await api("/api/preview", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      showPreview(data);
      if (!$("#targetPrice").value) {
        $("#targetPrice").value = String(Math.max(0, Math.round((data.price * 0.9) / 10) * 10));
      }
      $("#formError").hidden = true;
    } catch (error) {
      $("#previewCard").hidden = true;
      state.preview = null;
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      button.disabled = false;
      button.textContent = "Проверить";
    }
  }

  async function submitForm(event) {
    event.preventDefault();
    const button = $("#submitProduct");
    const errorBox = $("#formError");
    errorBox.hidden = true;

    const targetValue = $("#targetPrice").value.trim();
    const discountValue = $("#targetDiscount").value.trim();
    const payload = {
      target_price: targetValue === "" ? null : Number(targetValue),
      target_discount_percent: discountValue === "" ? null : Number(discountValue),
    };

    if (state.editingId) {
      button.classList.add("is-loading");
      button.disabled = true;
      try {
        await api(`/api/products/${state.editingId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        closeModal("formModal");
        toast("success", "Настройки сохранены", "Порог обновлён.");
        await loadAll({ quiet: true });
        if (state.chartProductId === state.editingId && !$("#chartModal").hidden) {
          await loadChartData(state.chartDays);
        }
      } catch (error) {
        errorBox.textContent = error.message;
        errorBox.hidden = false;
      } finally {
        button.classList.remove("is-loading");
        button.disabled = false;
      }
      return;
    }

    const url = $("#productUrl").value.trim();
    if (!url) {
      errorBox.textContent = "Вставьте ссылку на товар.";
      errorBox.hidden = false;
      return;
    }

    button.classList.add("is-loading");
    button.disabled = true;
    button.querySelector(".btn-spinner").hidden = false;
    try {
      const product = await api("/api/products", {
        method: "POST",
        body: JSON.stringify({ url, ...payload }),
      });
      closeModal("formModal");
      toast("success", "Товар добавлен", `${product.title} · ${fmtMoney(product.current_price, product.currency)}`);
      await loadAll({ quiet: true });
      setTimeout(() => openChart(product.id), 250);
    } catch (error) {
      errorBox.textContent = error.message;
      errorBox.hidden = false;
    } finally {
      button.classList.remove("is-loading");
      button.disabled = false;
      button.querySelector(".btn-spinner").hidden = true;
    }
  }

  /* ------------------------------ delete ------------------------------ */

  function openDeleteModal(id) {
    const product = findProduct(id);
    if (!product) return;
    state.deleteId = id;
    $("#confirmText").textContent = `«${product.title}» и вся история цен будут удалены. Это действие нельзя отменить.`;
    openModal("confirmModal");
  }

  async function confirmDelete() {
    if (!state.deleteId) return;
    const button = $("#confirmDeleteBtn");
    button.disabled = true;
    try {
      await api(`/api/products/${state.deleteId}`, { method: "DELETE" });
      closeModal("confirmModal");
      toast("success", "Товар удалён", "История цен очищена.");
      state.deleteId = null;
      await loadAll({ quiet: true });
    } catch (error) {
      toast("error", "Не удалось удалить товар", error.message);
    } finally {
      button.disabled = false;
    }
  }

  /* ------------------------------ chart ------------------------------ */

  function chartColors() {
    const styles = getComputedStyle(document.documentElement);
    const light = document.documentElement.dataset.theme === "light";
    return {
      lime: styles.getPropertyValue("--lime").trim() || "#c9ff4d",
      text: light ? "#5d6579" : "#939aae",
      grid: light ? "rgba(12,16,30,.07)" : "rgba(255,255,255,.06)",
      target: light ? "rgba(180,120,0,.8)" : "rgba(251,191,36,.75)",
      tooltipBg: light ? "#ffffff" : "#11141d",
      tooltipText: light ? "#0b0e17" : "#f3f4f8",
    };
  }

  function destroyChart() {
    if (state.chart) {
      state.chart.destroy();
      state.chart = null;
    }
  }

  async function openChart(id) {
    const product = findProduct(id);
    if (!product) return;
    state.chartProductId = Number(id);
    state.chartDays = 30;
    $$("#rangeTabs .range-tab").forEach((tab) => {
      tab.classList.toggle("is-active", Number(tab.dataset.days) === 30);
    });
    fillChartHeader(product);
    openModal("chartModal");
    await loadChartData(30);
  }

  function fillChartHeader(product) {
    $("#chartTitle").textContent = product.title;
    $("#chartShop").textContent = SHOP_NAMES[product.shop] || product.shop;
    $("#chartPrice").textContent = fmtMoney(product.current_price, product.currency);
    const delta = product.delta_percent_24h;
    const chip = $("#chartDelta");
    chip.textContent = delta === null ? "без изменений" : `${fmtPct(delta, true)} за 24 ч`;
    chip.className = `chip ${delta !== null && delta > 0 ? "chip-danger" : "chip-lime"}`;
    $("#chartTargetInput").value = product.target_price ?? "";
    $("#chartExport").href = `/api/products/${product.id}/history.csv`;
    $("#chartOpenLink").href = product.url;

    const thumb = $("#chartThumb");
    thumb.innerHTML = product.image_url
      ? `<img src="${escapeHtml(product.image_url)}" alt="">`
      : `<span style="font-weight:800">${escapeHtml((product.title || "?")[0])}</span>`;
    const img = thumb.querySelector("img");
    if (img) {
      img.addEventListener("error", () => {
        img.remove();
        thumb.textContent = (product.title || "?")[0];
      });
    }
  }

  async function loadChartData(days) {
    if (!state.chartProductId) return;
    const product = findProduct(state.chartProductId);
    if (product) fillChartHeader(product);
    try {
      const data = await api(
        `/api/products/${state.chartProductId}/history?days=${days}&limit=700`,
      );
      state.chartData = data;
      state.chartDays = days;
      renderChart(data);
      fillChartStats(data);
    } catch (error) {
      toast("error", "Не удалось загрузить историю", error.message);
    }
  }

  function fillChartStats(data) {
    const stats = data.stats || {};
    $("#chartMin").textContent = fmtMoney(stats.min_price, data.currency);
    $("#chartMax").textContent = fmtMoney(stats.max_price, data.currency);
    $("#chartAvg").textContent = fmtMoney(stats.avg_price, data.currency);
    $("#chartMedian").textContent = fmtMoney(stats.median_30d, data.currency);
    $("#chartChanges").textContent = String(stats.change_count ?? 0);
    $("#chartMeta").textContent = `${data.points.length} точек · ${state.chartDays} дней · медиана ${fmtMoney(stats.median_30d, data.currency)}`;
  }

  function renderChart(data) {
    if (!window.Chart || !data) return;
    destroyChart();
    const colors = chartColors();
    const labels = data.points.map((point) => {
      const date = new Date(point.checked_at);
      return state.chartDays <= 7
        ? `${dateFmt.format(date)}, ${timeFmt.format(date)}`
        : dateFmt.format(date);
    });
    const prices = data.points.map((point) => point.price);
    const product = findProduct(state.chartProductId);
    const target = product?.target_price ?? data.stats?.target_price ?? null;
    const canvas = $("#priceChart");
    const ctx = canvas.getContext("2d");
    const height = canvas.parentElement.clientHeight || 290;
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, "rgba(201,255,77,.28)");
    gradient.addColorStop(1, "rgba(201,255,77,0)");

    const datasets = [
      {
        label: "Цена",
        data: prices,
        borderColor: colors.lime,
        backgroundColor: gradient,
        borderWidth: 2.5,
        fill: true,
        tension: 0.35,
        pointRadius: 0,
        pointHoverRadius: 5,
        pointHoverBackgroundColor: colors.lime,
        pointHoverBorderColor: "#08090f",
        pointHoverBorderWidth: 2,
      },
    ];

    if (target) {
      datasets.push({
        label: "Цель",
        data: labels.map(() => target),
        borderColor: colors.target,
        borderWidth: 1.5,
        borderDash: [6, 6],
        pointRadius: 0,
        pointHoverRadius: 0,
        fill: false,
        tension: 0,
      });
    }

    state.chart = new Chart(ctx, {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        animation: { duration: 650, easing: "easeOutQuart" },
        layout: { padding: { top: 10, right: 6, left: 0, bottom: 0 } },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: colors.tooltipBg,
            titleColor: colors.tooltipText,
            bodyColor: colors.tooltipText,
            borderColor: colors.grid,
            borderWidth: 1,
            padding: 11,
            cornerRadius: 10,
            displayColors: false,
            titleFont: { family: "Manrope", size: 11, weight: "700" },
            bodyFont: { family: "Manrope", size: 12, weight: "700" },
            callbacks: {
              title: (items) => {
                const point = data.points[items[0].dataIndex];
                return point ? fullFmt.format(new Date(point.checked_at)) : "";
              },
              label: (item) => {
                if (item.dataset.label === "Цель") return `Цель: ${fmtMoney(item.parsed.y, data.currency)}`;
                return `Цена: ${fmtMoney(item.parsed.y, data.currency)}`;
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: {
              color: colors.text,
              font: { family: "Manrope", size: 10, weight: "600" },
              maxTicksLimit: 7,
              maxRotation: 0,
              autoSkip: true,
            },
          },
          y: {
            position: "right",
            grid: { color: colors.grid, drawTicks: false },
            border: { display: false },
            ticks: {
              color: colors.text,
              padding: 8,
              font: { family: "Manrope", size: 10, weight: "600" },
              callback: (value) => nf0.format(value),
            },
          },
        },
      },
    });
  }

  async function saveChartTarget() {
    if (!state.chartProductId) return;
    const raw = $("#chartTargetInput").value.trim();
    try {
      await api(`/api/products/${state.chartProductId}`, {
        method: "PATCH",
        body: JSON.stringify({ target_price: raw === "" ? null : Number(raw) }),
      });
      toast("success", "Цель обновлена", raw === "" ? "Порог снят." : `Новый порог: ${fmtMoney(Number(raw))}`);
      await loadAll({ quiet: true });
      await loadChartData(state.chartDays);
    } catch (error) {
      toast("error", "Не удалось сохранить цель", error.message);
    }
  }

  /* ------------------------------ notifications ------------------------------ */

  async function openNotifications() {
    openModal("notificationsDrawer");
    renderTelegramStatus();
    const feed = $("#feedList");
    feed.innerHTML = `<div class="feed-empty">Загружаем события…</div>`;
    try {
      const items = await api("/api/notifications?limit=40");
      if (!items.length) {
        feed.innerHTML = `<div class="feed-empty">Событий пока нет. Как только цена дойдёт до цели, здесь появится запись.</div>`;
        return;
      }
      feed.innerHTML = items
        .map((item) => {
          const kind = item.kind || "target";
          const status = item.status || "skipped";
          const statusLabel = status === "sent" ? "отправлено" : status === "failed" ? "ошибка" : "демо";
          const text = stripHtml(item.message).slice(0, 160);
          return `
            <button class="feed-item" data-notification-product="${item.product_id}" type="button">
              <span class="feed-icon feed-icon-${escapeHtml(kind)}">${KIND_ICONS[kind] || "🔔"}</span>
              <span class="feed-body">
                <span class="feed-top">
                  <strong>${escapeHtml(KIND_LABELS[kind] || "Событие")}</strong>
                  <span class="feed-time">${relativeTime(item.sent_at)}</span>
                </span>
                <p>${escapeHtml(text)}</p>
                <span class="feed-meta">
                  <span class="feed-price">${fmtMoney(item.price)}</span>
                  <span class="feed-status is-${escapeHtml(status)}">${statusLabel}</span>
                </span>
              </span>
            </button>`;
        })
        .join("");
    } catch (error) {
      feed.innerHTML = `<div class="feed-empty">Не удалось загрузить ленту: ${escapeHtml(error.message)}</div>`;
    }
  }

  /* ------------------------------ events ------------------------------ */

  function bindEvents() {
    $("#addBtn").addEventListener("click", openAddModal);
    $("#heroAddBtn").addEventListener("click", openAddModal);
    $("#emptyAddBtn").addEventListener("click", openAddModal);
    $("#insightAddBtn").addEventListener("click", openAddModal);
    $("#checkAllBtn").addEventListener("click", checkAll);
    $("#notificationsBtn").addEventListener("click", openNotifications);
    $("#insightFeedBtn").addEventListener("click", openNotifications);
    $("#openDemoShop").addEventListener("click", () => window.open("/demo/shop", "_blank", "noopener"));

    $("#previewBtn").addEventListener("click", previewUrl);
    $("#fillDemoBtn").addEventListener("click", () => {
      const slug = DEMO_SLUGS[Math.floor(Math.random() * DEMO_SLUGS.length)];
      $("#productUrl").value = `${window.location.origin}/demo/shop/${slug}`;
      $("#previewCard").hidden = true;
      state.preview = null;
      previewUrl();
    });
    $("#productUrl").addEventListener("input", () => {
      if (state.preview) {
        $("#previewCard").hidden = true;
        state.preview = null;
      }
    });
    $("#productUrl").addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        previewUrl();
      }
    });

    $$("#quickPrices button").forEach((button) => {
      button.addEventListener("click", () => {
        const base = state.preview?.price || (state.editingId ? findProduct(state.editingId)?.current_price : null);
        if (!base) {
          toast("info", "Сначала проверьте ссылку", "Цена понадобится для расчёта скидки.");
          return;
        }
        const discount = Number(button.dataset.discount);
        $("#targetPrice").value = String(Math.max(0, Math.round((base * (1 - discount / 100)) / 10) * 10));
      });
    });

    $("#productForm").addEventListener("submit", submitForm);
    $("#confirmDeleteBtn").addEventListener("click", confirmDelete);
    $("#chartTargetSave").addEventListener("click", saveChartTarget);
    $("#chartCheckBtn").addEventListener("click", () => {
      if (state.chartProductId) checkOne(state.chartProductId);
    });

    $("#searchInput").addEventListener(
      "input",
      debounce((event) => {
        state.search = event.target.value;
        renderProducts();
      }, 160),
    );

    $("#sortSelect").addEventListener("change", (event) => {
      state.sort = event.target.value;
      renderProducts();
    });

    $("#filterRow").addEventListener("click", (event) => {
      const chip = event.target.closest("[data-filter]");
      if (!chip) return;
      state.filter = chip.dataset.filter;
      $$("#filterRow .filter-chip[data-filter]").forEach((node) => {
        node.classList.toggle("is-active", node === chip);
      });
      renderProducts();
    });

    $("#productGrid").addEventListener("click", (event) => {
      const card = event.target.closest(".product-card");
      if (!card) return;
      const actionButton = event.target.closest("[data-action]");
      if (actionButton) {
        event.stopPropagation();
        handleCardAction(actionButton.dataset.action, card.dataset.productId);
        return;
      }
      openChart(card.dataset.productId);
    });

    $("#productGrid").addEventListener("keydown", (event) => {
      if (event.key !== "Enter" && event.key !== " ") return;
      const card = event.target.closest(".product-card");
      if (!card || event.target.closest("button")) return;
      event.preventDefault();
      openChart(card.dataset.productId);
    });

    $("#feedList").addEventListener("click", (event) => {
      const item = event.target.closest("[data-notification-product]");
      if (!item) return;
      const id = Number(item.dataset.notificationProduct);
      closeModal("notificationsDrawer");
      if (findProduct(id)) openChart(id);
    });

    $("#rangeTabs").addEventListener("click", (event) => {
      const tab = event.target.closest(".range-tab");
      if (!tab) return;
      $$("#rangeTabs .range-tab").forEach((node) => node.classList.toggle("is-active", node === tab));
      loadChartData(Number(tab.dataset.days));
    });

    $$("[data-close]").forEach((node) => {
      node.addEventListener("click", () => closeModal(node.dataset.close));
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        const open = modalIds.filter((id) => !document.getElementById(id)?.hidden);
        if (open.length) closeModal(open[open.length - 1]);
      }
      if (
        event.key === "/" &&
        !event.target.closest("input, textarea, select") &&
        $("#formModal").hidden
      ) {
        event.preventDefault();
        $("#searchInput").focus();
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refreshSummary();
    });
  }

  /* ------------------------------ boot ------------------------------ */

  function init() {
    initTheme();
    bindEvents();
    loadAll();
    setInterval(refreshSummary, 120000);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
