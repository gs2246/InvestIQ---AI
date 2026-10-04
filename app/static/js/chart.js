/* Stock page chart: candlesticks + simple average on top, RSI(14) below, time axes linked.
   Everything drawn here was calculated on the server; this file only draws it. */
(function () {
  "use strict";

  var COLORS = {
    paper: "#f5f1e6",
    ink: "#1a1a1a",
    forest: "#1e5631",
    oxblood: "#4a0e0e",
    hairline: "rgba(26, 26, 26, 0.18)",
  };
  var MONO = '"IBM Plex Mono", Consolas, "Courier New", monospace';
  var TIMEFRAMES = ["daily", "weekly", "monthly"];
  var RIGHT_PADDING_BARS = 3;
  var PRICE_SCALE_MIN_WIDTH = 76; // same on both charts so their plot areas line up

  var section = document.querySelector(".chart-section");
  if (!section || typeof LightweightCharts === "undefined") {
    var early = document.getElementById("page-error");
    if (early) {
      early.textContent = "The chart could not start because its drawing library did not load. Try reloading the page.";
      early.hidden = false;
    }
    var spinner = document.getElementById("chart-loading");
    if (spinner) spinner.hidden = true;
    return;
  }

  var symbol = section.dataset.symbol;
  var pageError = document.getElementById("page-error");
  var loading = document.getElementById("chart-loading");
  var readout = document.getElementById("chart-readout");
  var legendSma = document.getElementById("legend-sma-label");
  var buttons = Array.prototype.slice.call(section.querySelectorAll("[data-timeframe]"));

  var markerToggle = document.getElementById("marker-toggle");
  var markerToggleWrap = document.getElementById("marker-toggle-wrap");
  var weeklyOnly = Array.prototype.slice.call(section.querySelectorAll("[data-weekly-only]"));

  var cache = {};          // timeframe -> server response
  var current = null;      // { data, candleByTime, smaByTime, rsiByTime }
  var currentTimeframe = null;
  var system1Signals = null; // BUY / SELL bars from system1.js, null until loaded

  /* ---- charts ---------------------------------------------------------- */
  function baseOptions(showTimeAxis) {
    return {
      autoSize: true,
      layout: {
        background: { type: "solid", color: COLORS.paper },
        textColor: COLORS.ink,
        fontFamily: MONO,
        fontSize: 12,
      },
      grid: {
        vertLines: { color: COLORS.hairline },
        horzLines: { color: COLORS.hairline },
      },
      rightPriceScale: { borderColor: COLORS.hairline, minimumWidth: PRICE_SCALE_MIN_WIDTH },
      timeScale: {
        borderColor: COLORS.hairline,
        rightOffset: RIGHT_PADDING_BARS,
        visible: showTimeAxis,
        timeVisible: false,
      },
      crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
    };
  }

  var priceOptions = baseOptions(false);
  priceOptions.localization = { priceFormatter: money }; // 19,000.00 not 19000.00
  var priceChart = LightweightCharts.createChart(document.getElementById("price-chart"), priceOptions);

  var rsiOptions = baseOptions(true);
  // Little padding, so the 0-100 range is not stretched to a misleading "120" at the top.
  rsiOptions.rightPriceScale.scaleMargins = { top: 0.04, bottom: 0.04 };
  var rsiChart = LightweightCharts.createChart(document.getElementById("rsi-chart"), rsiOptions);

  // Filled body = up. Hollow body with an oxblood outline = down. Colour is never the only cue.
  var candleSeries = priceChart.addCandlestickSeries({
    upColor: COLORS.forest,
    borderUpColor: COLORS.forest,
    wickUpColor: COLORS.forest,
    downColor: COLORS.paper,
    borderDownColor: COLORS.oxblood,
    wickDownColor: COLORS.oxblood,
    borderVisible: true,
    priceLineVisible: false,
  });

  var smaSeries = priceChart.addLineSeries({
    color: COLORS.ink,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: false,
    crosshairMarkerVisible: false,
  });

  var rsiSeries = rsiChart.addLineSeries({
    color: COLORS.ink,
    lineWidth: 2,
    priceLineVisible: false,
    lastValueVisible: true,
    // RSI always lives on a 0-100 scale, whatever the visible window holds.
    autoscaleInfoProvider: function () {
      return { priceRange: { minValue: 0, maxValue: 100 } };
    },
  });
  var zoneLines = [];

  /* ---- keep the two time axes in step ---------------------------------- */
  var syncing = false;
  function link(from, to) {
    from.timeScale().subscribeVisibleLogicalRangeChange(function (range) {
      if (syncing || !range) return;
      syncing = true;
      try { to.timeScale().setVisibleLogicalRange(range); } finally { syncing = false; }
    });
  }
  link(priceChart, rsiChart);
  link(rsiChart, priceChart);

  /* ---- hover readout --------------------------------------------------- */
  function money(n) {
    return Number(n).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  function timeKey(t) {
    if (!t) return null;
    if (typeof t === "string") return t;
    var m = String(t.month).padStart(2, "0");
    var d = String(t.day).padStart(2, "0");
    return t.year + "-" + m + "-" + d;
  }
  function describeBar(key, prefix) {
    if (!current || !current.candleByTime[key]) return null;
    var c = current.candleByTime[key];
    var parts = [
      prefix + key,
      "O " + money(c.open), "H " + money(c.high), "L " + money(c.low), "C " + money(c.close),
    ];
    if (current.smaByTime[key] !== undefined) parts.push("Avg " + money(current.smaByTime[key]));
    if (current.rsiByTime[key] !== undefined) parts.push("RSI " + current.rsiByTime[key].toFixed(2));
    return parts.join("   ");
  }
  function showLatestBar() {
    if (!current) return;
    var candles = current.data.candles;
    readout.textContent = describeBar(candles[candles.length - 1].time, "Latest bar ") || "";
  }
  function onCrosshair(param) {
    var key = timeKey(param && param.time);
    var text = key ? describeBar(key, "") : null;
    if (text) readout.textContent = text; else showLatestBar();
  }
  priceChart.subscribeCrosshairMove(onCrosshair);
  rsiChart.subscribeCrosshairMove(onCrosshair);

  /* ---- Trend Following markers ----------------------------------------- */
  // Arrows only, no text. Shape differs as well as colour: up arrow = BUY, down arrow = SELL.
  // Signals exist only on weekly candles, so on daily/monthly there are no markers and the
  // toggle and the arrow legend entries are hidden.
  function toMarker(signal) {
    var buy = signal.state === "BUY";
    return {
      time: signal.time,
      position: buy ? "belowBar" : "aboveBar",
      shape: buy ? "arrowUp" : "arrowDown",
      color: buy ? COLORS.forest : COLORS.oxblood,
      size: 1,
    };
  }
  function applyMarkers() {
    var weekly = currentTimeframe === "weekly";
    markerToggleWrap.hidden = !weekly;
    weeklyOnly.forEach(function (el) { el.hidden = !weekly; });
    candleSeries.setMarkers(weekly && markerToggle.checked && system1Signals ? system1Signals.map(toMarker) : []);
  }
  markerToggle.addEventListener("change", applyMarkers);
  window.addEventListener("system1:loaded", function (event) {
    system1Signals = event.detail.signals;
    applyMarkers();
  });

  /* ---- drawing a response --------------------------------------------- */
  function indexByTime(points, field) {
    var out = {};
    for (var i = 0; i < points.length; i++) out[points[i].time] = field ? points[i][field] : points[i];
    return out;
  }

  function render(data) {
    var candles = data.candles;
    var smaByTime = indexByTime(data.sma, "value");
    var rsiByTime = indexByTime(data.rsi, "value");

    candleSeries.setMarkers([]); // old markers belong to the previous timeframe's bars
    candleSeries.setData(candles);
    smaSeries.setData(data.sma);

    // The RSI chart needs one entry per candle (blank where RSI is not defined yet),
    // otherwise its bar positions would not match the price chart's and linking would drift.
    rsiSeries.setData(candles.map(function (c) {
      return rsiByTime[c.time] === undefined ? { time: c.time } : { time: c.time, value: rsiByTime[c.time] };
    }));

    zoneLines.forEach(function (line) { rsiSeries.removePriceLine(line); });
    zoneLines = data.rsi_zone_bounds.map(function (level) {
      return rsiSeries.createPriceLine({
        price: level,
        color: COLORS.ink,
        lineWidth: 1,
        lineStyle: LightweightCharts.LineStyle.Dotted,
        // no axis label: the legend explains the 40/60 lines, and their labels used to
        // overlap the current-RSI label when RSI sat near either boundary
        axisLabelVisible: false,
        title: "",
      });
    });

    legendSma.textContent = data.sma_label + ":";

    current = {
      data: data,
      candleByTime: indexByTime(candles),
      smaByTime: smaByTime,
      rsiByTime: rsiByTime,
    };

    // Open on a recent window; the full history is one zoom-out away.
    var n = candles.length;
    var visible = data.default_bars_visible;
    if (n > visible) {
      priceChart.timeScale().setVisibleLogicalRange({ from: n - visible, to: n - 1 + RIGHT_PADDING_BARS });
    } else {
      priceChart.timeScale().fitContent();
    }
    showLatestBar();
  }

  /* ---- loading --------------------------------------------------------- */
  function showError(message) {
    pageError.textContent = message;
    pageError.hidden = false;
  }
  function clearError() {
    pageError.hidden = true;
    pageError.textContent = "";
  }
  function setBusy(busy) {
    buttons.forEach(function (b) { b.disabled = busy; });
  }
  function markPressed(timeframe) {
    buttons.forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.timeframe === timeframe ? "true" : "false");
    });
  }

  async function fetchCandles(timeframe) {
    if (cache[timeframe]) return cache[timeframe];
    var res = await fetch("/api/stocks/" + encodeURIComponent(symbol) + "/candles?timeframe=" + timeframe);
    var body = null;
    try { body = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) throw new Error((body && body.detail) || "The server answered with an error (" + res.status + ").");
    if (!body || !body.candles) throw new Error("The server sent data in an unexpected shape.");
    cache[timeframe] = body;
    return body;
  }

  function showSkeleton() { loading.hidden = false; }
  function hideSkeleton() { loading.hidden = true; }

  async function show(timeframe) {
    showSkeleton();
    setBusy(true);
    try {
      var data = await fetchCandles(timeframe);
      render(data);
      currentTimeframe = timeframe;
      applyMarkers();
      markPressed(timeframe);
      clearError();
      try {
        var url = new URL(window.location.href);
        url.searchParams.set("timeframe", timeframe);
        window.history.replaceState(null, "", url);
      } catch (e) { /* the address bar is cosmetic */ }
    } catch (err) {
      markPressed(currentTimeframe);
      var reason = err instanceof TypeError
        ? "The app's server could not be reached. Check that the InvestIQ window opened by start.bat is still running, then reload this page."
        : (err && err.message ? err.message : "");
      showError("Could not load the " + timeframe + " chart. " + reason);
    } finally {
      hideSkeleton(); // always, so the chart area can never stay covered
      setBusy(false);
    }
  }

  buttons.forEach(function (b) {
    b.addEventListener("click", function () {
      if (b.dataset.timeframe !== currentTimeframe) show(b.dataset.timeframe);
    });
  });

  // The charts draw text on a canvas, so redraw once the web fonts are really loaded.
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () {
      var fontOptions = { layout: { fontFamily: MONO } };
      priceChart.applyOptions(fontOptions);
      rsiChart.applyOptions(fontOptions);
    });
  }

  var asked = new URLSearchParams(window.location.search).get("timeframe");
  show(TIMEFRAMES.indexOf(asked) >= 0 ? asked : "weekly");
})();
