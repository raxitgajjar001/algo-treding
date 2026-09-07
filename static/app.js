// Indian Market Ribbon & Live Tickers
let nativeChart = null;
let candleSeries = null;
let areaSeries = null;
let volumeSeries = null;
let ema9Series = null;
let ema21Series = null;

// Dedicated RSI Sub-chart
let rsiChart = null;
let rsiLineSeries = null;
let rsiUpperSeries = null;
let rsiMiddleSeries = null;
let rsiLowerSeries = null;

let currentChartSymbol = 'NIFTY';
let currentTimeframe = '5m';
let currentCandle = null;
let allCandles = [];
let allVolumes = [];

let indicatorsState = {
  ema9: true,
  ema21: true,
  rsi: false,
  vol: true,
  chartType: 'candles'
};

let currentPnlFilterDays = 1;
let isRunning = false;
let currentMode = 'PAPER';

// Technical Indicator Calculations
function calculateEMA(candles, period) {
  if (!candles || candles.length < period) return [];
  const k = 2 / (period + 1);
  const result = [];
  
  let sum = 0;
  for (let i = 0; i < period; i++) {
    sum += candles[i].close;
  }
  let prevEma = sum / period;
  result.push({ time: candles[period - 1].time, value: parseFloat(prevEma.toFixed(2)) });

  for (let i = period; i < candles.length; i++) {
    const c = candles[i].close;
    prevEma = (c * k) + (prevEma * (1 - k));
    result.push({ time: candles[i].time, value: parseFloat(prevEma.toFixed(2)) });
  }
  return result;
}

function calculateRSI(candles, period = 14) {
  if (!candles || candles.length <= period) return { data: [], current: 50.0 };
  let gains = 0;
  let losses = 0;

  for (let i = 1; i <= period; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    if (diff >= 0) gains += diff;
    else losses += Math.abs(diff);
  }

  let avgGain = gains / period;
  let avgLoss = losses / period;
  const result = [];

  let rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
  let rsi = avgLoss === 0 ? 100 : 100 - (100 / (1 + rs));
  result.push({ time: candles[period].time, value: parseFloat(rsi.toFixed(2)) });

  for (let i = period + 1; i < candles.length; i++) {
    const diff = candles[i].close - candles[i - 1].close;
    const gain = diff > 0 ? diff : 0;
    const loss = diff < 0 ? Math.abs(diff) : 0;

    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;

    rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi = avgLoss === 0 ? 100 : 100 - (100 / (1 + rs));
    result.push({ time: candles[i].time, value: parseFloat(rsi.toFixed(2)) });
  }

  return { data: result, current: parseFloat(rsi.toFixed(2)) };
}

function initRsiSubChart() {
  const rsiContainer = document.getElementById('rsi_chart_container');
  if (!rsiContainer || typeof LightweightCharts === 'undefined') return;

  if (rsiChart) {
    try { rsiChart.remove(); } catch (e) {}
    rsiChart = null;
  }

  rsiContainer.innerHTML = '';

  const chart = LightweightCharts.createChart(rsiContainer, {
    width: rsiContainer.clientWidth || 800,
    height: 85,
    layout: {
      background: { color: '#FAF5FF' },
      textColor: '#6B21A8',
      fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial'
    },
    grid: {
      vertLines: { color: '#F3E8FF' },
      horzLines: { color: '#E9D5FF' }
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal
    },
    rightPriceScale: {
      borderColor: '#D8B4FE',
      scaleMargins: { top: 0.1, bottom: 0.1 }
    },
    timeScale: {
      borderColor: '#D8B4FE',
      timeVisible: true,
      secondsVisible: false,
      visible: false // Hidden to avoid duplicate time axis
    }
  });

  rsiChart = chart;

  // Upper Overbought line (70)
  rsiUpperSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#DC2626',
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    lastValueVisible: false,
    priceLineVisible: false
  });

  // Centerline (50)
  rsiMiddleSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#94A3B8',
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dotted,
    lastValueVisible: false,
    priceLineVisible: false
  });

  // Lower Oversold line (30)
  rsiLowerSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#16A34A',
    lineWidth: 1,
    lineStyle: LightweightCharts.LineStyle.Dashed,
    lastValueVisible: false,
    priceLineVisible: false
  });

  // Purple RSI line
  rsiLineSeries = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#7E22CE',
    lineWidth: 2,
    priceLineVisible: true
  });
}

function renderChartData() {
  if (!nativeChart || !allCandles || allCandles.length === 0) return;

  // 1. Candlestick vs Line Series
  if (indicatorsState.chartType === 'candles') {
    if (areaSeries) areaSeries.setData([]);
    if (candleSeries) candleSeries.setData(allCandles);
  } else {
    if (candleSeries) candleSeries.setData([]);
    const lineData = allCandles.map(c => ({ time: c.time, value: c.close }));
    if (areaSeries) areaSeries.setData(lineData);
  }

  // 2. Volume Series
  if (volumeSeries) {
    if (indicatorsState.vol) {
      volumeSeries.setData(allVolumes);
    } else {
      volumeSeries.setData([]);
    }
  }

  // 3. EMA 9 (Fast)
  if (ema9Series) {
    if (indicatorsState.ema9) {
      const ema9Data = calculateEMA(allCandles, 9);
      ema9Series.setData(ema9Data);
    } else {
      ema9Series.setData([]);
    }
  }

  // 4. EMA 21 (Slow)
  if (ema21Series) {
    if (indicatorsState.ema21) {
      const ema21Data = calculateEMA(allCandles, 21);
      ema21Series.setData(ema21Data);
    } else {
      ema21Series.setData([]);
    }
  }

  // 5. Dedicated RSI Sub-Chart Pane
  const rsiWrapper = document.getElementById('rsi-subchart-wrapper');
  const rsiBadge = document.getElementById('rsi-indicator-badge');
  const rsiValBadge = document.getElementById('rsi-val-badge');

  if (indicatorsState.rsi) {
    if (rsiWrapper) rsiWrapper.style.display = 'block';
    if (!rsiChart) initRsiSubChart();

    const rsiRes = calculateRSI(allCandles, 14);
    if (rsiLineSeries && rsiRes.data.length > 0) {
      rsiLineSeries.setData(rsiRes.data);
      // Reference bands 70, 50, 30
      const upper70 = rsiRes.data.map(d => ({ time: d.time, value: 70 }));
      const mid50 = rsiRes.data.map(d => ({ time: d.time, value: 50 }));
      const lower30 = rsiRes.data.map(d => ({ time: d.time, value: 30 }));
      if (rsiUpperSeries) rsiUpperSeries.setData(upper70);
      if (rsiMiddleSeries) rsiMiddleSeries.setData(mid50);
      if (rsiLowerSeries) rsiLowerSeries.setData(lower30);
      if (rsiChart) rsiChart.timeScale().fitContent();
    }

    let rsiStatus = 'સામાન્ય (Neutral)';
    let rsiColor = '#7E22CE';
    let rsiBg = '#FAF5FF';
    if (rsiRes.current >= 70) {
      rsiStatus = 'ઓવરબોટ ⚠️ (Overbought)';
      rsiColor = '#B91C1C';
      rsiBg = '#FEF2F2';
    } else if (rsiRes.current <= 30) {
      rsiStatus = 'ઓવરસોલ્ડ 💎 (Oversold)';
      rsiColor = '#15803D';
      rsiBg = '#F0FDF4';
    } else if (rsiRes.current >= 55) {
      rsiStatus = 'મજબૂત તેજી 🟢 (Bullish)';
      rsiColor = '#166534';
      rsiBg = '#DCFCE7';
    } else if (rsiRes.current <= 45) {
      rsiStatus = 'નરમાશ / મંદી 🔴 (Bearish)';
      rsiColor = '#991B1B';
      rsiBg = '#FEE2E2';
    }

    if (rsiBadge) {
      rsiBadge.style.display = 'inline-block';
      rsiBadge.textContent = 'RSI (14): ' + rsiRes.current + ' (' + rsiStatus + ')';
      rsiBadge.style.color = rsiColor;
      rsiBadge.style.background = rsiBg;
    }
    if (rsiValBadge) {
      rsiValBadge.textContent = 'RSI: ' + rsiRes.current + ' (' + rsiStatus + ')';
    }
  } else {
    if (rsiWrapper) rsiWrapper.style.display = 'none';
    if (rsiBadge) rsiBadge.style.display = 'none';
  }

  nativeChart.timeScale().fitContent();
}

async function loadChartData(symbol, timeframe = currentTimeframe) {
  const sym = symbol.replace('NSE:', '').replace('BSE:', '').toUpperCase();
  currentChartSymbol = sym;
  currentTimeframe = timeframe;

  const symBadge = document.getElementById('current-chart-symbol');
  const ltpElem = document.getElementById('current-chart-ltp');
  if (symBadge) symBadge.textContent = '🇮🇳 ' + sym;

  try {
    const res = await fetch('/api/market/chart/' + sym + '?interval=' + timeframe);
    const data = await res.json();
    
    if (data.candles && data.candles.length > 0) {
      allCandles = data.candles;
      allVolumes = data.volumes || [];
      currentCandle = { ...data.candles[data.candles.length - 1] };
      
      if (ltpElem && currentCandle) {
        ltpElem.textContent = '₹' + Number(currentCandle.close).toLocaleString('en-IN', {minimumFractionDigits: 2});
      }
      
      renderChartData();
    }
  } catch (err) {
    console.error('Error fetching real market candles:', err);
  }
}

function initNativeChart(symbol = 'NIFTY') {
  currentChartSymbol = symbol.replace('NSE:', '').replace('BSE:', '').toUpperCase();
  const container = document.getElementById('lightweight_chart_container');
  if (!container || typeof LightweightCharts === 'undefined') return;

  container.innerHTML = '';

  const chart = LightweightCharts.createChart(container, {
    width: container.clientWidth || 800,
    height: 440,
    layout: {
      background: { color: '#FFFFFF' },
      textColor: '#334155',
      fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Arial'
    },
    grid: {
      vertLines: { color: '#F1F5F9' },
      horzLines: { color: '#F1F5F9' }
    },
    crosshair: {
      mode: LightweightCharts.CrosshairMode.Normal
    },
    rightPriceScale: {
      borderColor: '#CBD5E1',
      scaleMargins: {
        top: 0.08,
        bottom: 0.22
      }
    },
    timeScale: {
      borderColor: '#CBD5E1',
      timeVisible: true,
      secondsVisible: false
    }
  });

  nativeChart = chart;

  // Candlestick Series
  candleSeries = chart.addSeries(LightweightCharts.CandlestickSeries, {
    upColor: '#16A34A',
    downColor: '#DC2626',
    borderVisible: false,
    wickUpColor: '#16A34A',
    wickDownColor: '#DC2626'
  });

  // Area Series (Line chart view)
  areaSeries = chart.addSeries(LightweightCharts.AreaSeries, {
    topColor: 'rgba(37, 99, 235, 0.25)',
    bottomColor: 'rgba(37, 99, 235, 0.01)',
    lineColor: '#2563EB',
    lineWidth: 2
  });

  // Volume Series
  volumeSeries = chart.addSeries(LightweightCharts.HistogramSeries, {
    priceFormat: { type: 'volume' },
    priceScaleId: 'volume_scale'
  });

  chart.priceScale('volume_scale').applyOptions({
    scaleMargins: {
      top: 0.82,
      bottom: 0
    }
  });

  // EMA 9 Series (INDmoney Blue)
  ema9Series = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#2563EB',
    lineWidth: 2,
    title: 'EMA 9'
  });

  // EMA 21 Series (INDmoney Orange)
  ema21Series = chart.addSeries(LightweightCharts.LineSeries, {
    color: '#EA580C',
    lineWidth: 2,
    title: 'EMA 21'
  });

  loadChartData(currentChartSymbol, currentTimeframe);

  window.addEventListener('resize', () => {
    handleChartResize();
  });
}

function handleChartResize() {
  const panel = document.querySelector('.chart-panel');
  const isFullscreen = panel && panel.classList.contains('fullscreen-active');
  const container = document.getElementById('native-chart-wrapper');
  if (!container || !nativeChart) return;

  if (isFullscreen) {
    const w = window.innerWidth - 48;
    const h = window.innerHeight - (indicatorsState.rsi ? 290 : 180);
    container.style.height = h + 'px';
    nativeChart.applyOptions({ width: w, height: h });
    if (rsiChart && indicatorsState.rsi) {
      const rsiContainer = document.getElementById('rsi_chart_container');
      if (rsiContainer) rsiChart.applyOptions({ width: w });
    }
  } else {
    container.style.height = '440px';
    nativeChart.applyOptions({ width: container.clientWidth, height: 440 });
    if (rsiChart && indicatorsState.rsi) {
      rsiChart.applyOptions({ width: container.clientWidth });
    }
  }
}

function toggleFullscreenChart() {
  const panel = document.querySelector('.chart-panel');
  const btn = document.getElementById('btn-fullscreen');
  if (!panel || !btn) return;

  const isFull = panel.classList.toggle('fullscreen-active');

  if (isFull) {
    btn.innerHTML = '✖ નાની સ્ક્રીન (Exit Full Screen)';
    btn.className = 'btn btn-stop';
    btn.style.borderColor = '#FCA5A5';
  } else {
    btn.innerHTML = '⛶ મોટો ચાર્ટ (Full Screen)';
    btn.className = 'btn btn-secondary';
    btn.style.borderColor = '#CBD5E1';
  }

  setTimeout(handleChartResize, 60);
}

// Listen for Escape key to exit fullscreen
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') {
    const panel = document.querySelector('.chart-panel');
    if (panel && panel.classList.contains('fullscreen-active')) {
      toggleFullscreenChart();
    }
  }
});

function switchChart(rawSymbol) {
  const sym = rawSymbol.replace('NSE:', '').replace('BSE:', '').toUpperCase();
  currentChartSymbol = sym;

  // Highlight active quick symbol button
  const symButtons = ['NIFTY', 'BANKNIFTY', 'SENSEX', 'RELIANCE', 'HDFCBANK', 'SBIN', 'TATAMOTORS', 'ICICIBANK', 'TCS', 'INFY'];
  symButtons.forEach(s => {
    const btn = document.getElementById('sym-btn-' + s);
    if (btn) {
      btn.className = (s === sym) ? 'btn btn-primary' : 'btn btn-secondary';
    }
  });

  if (!nativeChart) {
    initNativeChart(sym);
  } else {
    loadChartData(sym, currentTimeframe);
  }
}

function switchTimeframe(tf) {
  currentTimeframe = tf;
  const timeframes = ['1m', '5m', '15m', '30m', '1h', '1d'];
  timeframes.forEach(t => {
    const btn = document.getElementById('tf-' + t);
    if (btn) {
      btn.className = (t === tf.toLowerCase()) ? 'btn btn-primary' : 'btn btn-secondary';
    }
  });

  loadChartData(currentChartSymbol, tf);
}

function toggleIndicator(ind) {
  if (ind === 'ema9') {
    indicatorsState.ema9 = !indicatorsState.ema9;
    const btn = document.getElementById('btn-ind-ema9');
    if (btn) btn.className = indicatorsState.ema9 ? 'btn btn-primary' : 'btn btn-secondary';
  } else if (ind === 'ema21') {
    indicatorsState.ema21 = !indicatorsState.ema21;
    const btn = document.getElementById('btn-ind-ema21');
    if (btn) btn.className = indicatorsState.ema21 ? 'btn btn-primary' : 'btn btn-secondary';
  } else if (ind === 'rsi') {
    indicatorsState.rsi = !indicatorsState.rsi;
    const btn = document.getElementById('btn-ind-rsi');
    if (btn) btn.className = indicatorsState.rsi ? 'btn btn-primary' : 'btn btn-secondary';
  } else if (ind === 'vol') {
    indicatorsState.vol = !indicatorsState.vol;
    const btn = document.getElementById('btn-ind-vol');
    if (btn) btn.className = indicatorsState.vol ? 'btn btn-primary' : 'btn btn-secondary';
  }
  renderChartData();
  setTimeout(handleChartResize, 40);
}

function toggleChartType() {
  const btn = document.getElementById('btn-chart-type');
  if (indicatorsState.chartType === 'candles') {
    indicatorsState.chartType = 'line';
    if (btn) {
      btn.textContent = 'Line 📈';
      btn.className = 'btn btn-primary';
    }
  } else {
    indicatorsState.chartType = 'candles';
    if (btn) {
      btn.textContent = 'Candles 🕯️';
      btn.className = 'btn btn-secondary';
    }
  }
  renderChartData();
}

// Sub-second Live Market Ticker & Real-time Chart Streaming
async function fetchLiveTicks() {
  try {
    const res = await fetch('/api/market/live-ticks');
    const data = await res.json();
    const ticks = data.ticks;
    if (!ticks) return;

    // 1. Update Ribbon
    if (ticks['NIFTY']) {
      const el = document.getElementById('ticker-nifty');
      if (el) el.textContent = '₹' + ticks['NIFTY'].ltp.toLocaleString('en-IN') + ' (' + ticks['NIFTY'].change_pct + '%)';
    }
    if (ticks['BANKNIFTY']) {
      const el = document.getElementById('ticker-banknifty');
      if (el) el.textContent = '₹' + ticks['BANKNIFTY'].ltp.toLocaleString('en-IN') + ' (' + ticks['BANKNIFTY'].change_pct + '%)';
    }
    if (ticks['SENSEX']) {
      const el = document.getElementById('ticker-sensex');
      if (el) el.textContent = '₹' + ticks['SENSEX'].ltp.toLocaleString('en-IN') + ' (' + ticks['SENSEX'].change_pct + '%)';
    }
    if (ticks['FINNIFTY']) {
      const el = document.getElementById('ticker-finnifty');
      if (el) el.textContent = '₹' + ticks['FINNIFTY'].ltp.toLocaleString('en-IN') + ' (' + ticks['FINNIFTY'].change_pct + '%)';
    }
    if (ticks['INDIAVIX']) {
      const el = document.getElementById('ticker-vix');
      if (el) el.textContent = ticks['INDIAVIX'].ltp + ' (' + ticks['INDIAVIX'].change_pct + '%)';
    }

    // 2. Stream Active Candlestick on Chart in Real Time
    const currentTick = ticks[currentChartSymbol];
    if (currentTick && currentCandle && allCandles.length > 0) {
      const newClose = currentTick.ltp;
      const newHigh = Math.max(currentCandle.high, newClose);
      const newLow = Math.min(currentCandle.low, newClose);

      currentCandle.close = newClose;
      currentCandle.high = newHigh;
      currentCandle.low = newLow;

      if (indicatorsState.chartType === 'candles' && candleSeries) {
        candleSeries.update(currentCandle);
      } else if (indicatorsState.chartType === 'line' && areaSeries) {
        areaSeries.update({ time: currentCandle.time, value: newClose });
      }

      const ltpElem = document.getElementById('current-chart-ltp');
      if (ltpElem) {
        ltpElem.textContent = '₹' + Number(newClose).toLocaleString('en-IN', {minimumFractionDigits: 2});
      }
    }
  } catch (e) {}
}

// P&L Performance Filter & Reset Logic
async function applyPnlFilter(days) {
  currentPnlFilterDays = days;
  
  // 1. Update filter button styling
  const daysList = [1, 2, 7, 30, 90, 180, 365];
  daysList.forEach(d => {
    const btn = document.getElementById('filter-btn-' + d);
    if (btn) {
      btn.className = (d === days) ? 'btn btn-primary' : 'btn btn-secondary';
    }
  });

  // 2. Fetch performance data for timeframe
  try {
    const res = await fetch('/api/performance?days=' + days);
    const data = await res.json();
    
    // 3. Update KPI cards
    const netPnlElem = document.getElementById('net-pnl');
    const pnlCard = document.getElementById('pnl-card');
    const realizedPnlElem = document.getElementById('realized-pnl');
    const unrealizedPnlElem = document.getElementById('unrealized-pnl');
    const winRateElem = document.getElementById('win-rate');
    const winCountsElem = document.getElementById('win-counts');
    
    const pnl = data.net_pnl !== undefined ? data.net_pnl : 0.0;
    if (pnl === 0) {
      netPnlElem.textContent = '₹0.00';
      netPnlElem.className = 'metric-value profit';
      pnlCard.className = 'metric-card pnl-card';
    } else if (pnl > 0) {
      netPnlElem.textContent = '+₹' + pnl.toLocaleString('en-IN', {minimumFractionDigits: 2});
      netPnlElem.className = 'metric-value profit';
      pnlCard.className = 'metric-card pnl-card';
    } else {
      netPnlElem.textContent = '-₹' + Math.abs(pnl).toLocaleString('en-IN', {minimumFractionDigits: 2});
      netPnlElem.className = 'metric-value loss';
      pnlCard.className = 'metric-card pnl-card negative';
    }
    
    realizedPnlElem.textContent = 'Realized: ₹' + (data.realized_pnl !== undefined ? Number(data.realized_pnl).toFixed(2) : '0.00');
    unrealizedPnlElem.textContent = 'Open: ₹' + (data.unrealized_pnl !== undefined ? Number(data.unrealized_pnl).toFixed(2) : '0.00');
    winRateElem.textContent = (data.win_rate !== undefined ? data.win_rate : 0) + '%';
    winCountsElem.textContent = (data.total_trades || 0) + ' Trades (' + (data.winning_trades || 0) + ' Win / ' + (data.losing_trades || 0) + ' Loss)';
  } catch (err) {
    console.error('Error fetching filtered performance:', err);
  }
}

async function resetAllPnLToZero() {
  const confirmed = confirm('શું તમે ખરેખર તમામ નફો/નુકસાન અને પાછલા સોદા Reset કરીને ₹0.00 કરવા માંગો છો?');
  if (!confirmed) return;

  try {
    const res = await fetch('/api/trades/reset', { method: 'POST' });
    const data = await res.json();
    
    // Instantly zero out all UI metric displays
    const netPnlElem = document.getElementById('net-pnl');
    const pnlCard = document.getElementById('pnl-card');
    netPnlElem.textContent = '₹0.00';
    netPnlElem.className = 'metric-value profit';
    pnlCard.className = 'metric-card pnl-card';

    document.getElementById('realized-pnl').textContent = 'Realized: ₹0.00';
    document.getElementById('unrealized-pnl').textContent = 'Open: ₹0.00';
    document.getElementById('win-rate').textContent = '0%';
    document.getElementById('win-counts').textContent = '0 Trades Executed';
    document.getElementById('active-trades-count').textContent = '0';

    await applyPnlFilter(1);
    await fetchActiveTrades();
    await fetchTradeHistory();
    await fetchStatus();
  } catch (err) {
    console.error('Error resetting trades and P&L:', err);
  }
}

async function fetchStatus() {
  try {
    const res = await fetch('/api/status');
    const data = await res.json();

    // 1. Update Market Timing & Notice Banner
    const timing = data.market_timing;
    if (timing) {
      const marketBadge = document.getElementById('market-status-badge');
      const noticeText = document.getElementById('market-notice-text');
      const noticeBar = document.getElementById('market-notice-bar');
      const clockElem = document.getElementById('clock-ist');

      if (marketBadge) {
        marketBadge.textContent = timing.badge_text;
        marketBadge.className = timing.is_open ? 'badge badge-live' : 'badge badge-bearish';
      }
      if (noticeText) noticeText.textContent = timing.message;
      if (clockElem) clockElem.textContent = timing.time_str;
      if (noticeBar) {
        noticeBar.style.background = timing.is_open ? '#F0FDF4' : '#FEF2F2';
        noticeBar.style.borderColor = timing.is_open ? '#86EFAC' : '#FCA5A5';
        noticeBar.style.color = timing.is_open ? '#166534' : '#991B1B';
      }
    }
    
    // 2. Update Mode Badge
    currentMode = data.mode;
    const modeBadge = document.getElementById('mode-badge');
    modeBadge.textContent = data.mode === 'LIVE' ? 'LIVE TRADING (સાચું ટ્રેડિંગ)' : 'PAPER TRADING (ડેમો મોડ)';
    modeBadge.className = data.mode === 'LIVE' ? 'badge badge-live' : 'badge badge-paper';

    // 3. Update Engine Toggle Button based on Market Hours
    isRunning = data.is_running;
    const btnToggle = document.getElementById('btn-toggle-engine');
    const subText = document.getElementById('engine-subtext');
    const isMarketOpen = timing && timing.is_open;

    if (!isMarketOpen) {
      btnToggle.disabled = true;
      btnToggle.textContent = '🔒 બજાર બંધ છે (Market Closed - ટ્રેડિંગ બંધ)';
      btnToggle.className = 'btn btn-secondary';
      btnToggle.style.background = '#F1F5F9';
      btnToggle.style.color = '#64748B';
      btnToggle.style.borderColor = '#CBD5E1';
      btnToggle.style.cursor = 'not-allowed';
      if (subText) {
        subText.textContent = '⛔ બજાર બંધ હોવાથી ઓટો ટ્રેડિંગ સંપૂર્ણપણે બંધ (OFF) છે. સવારે 09:15 વાગ્યે આપોઆપ અનલોક થશે.';
        subText.style.color = '#DC2626';
        subText.style.fontWeight = '700';
      }
    } else {
      btnToggle.disabled = false;
      btnToggle.style.cursor = 'pointer';
      btnToggle.style.background = '';
      btnToggle.style.color = '';
      btnToggle.style.borderColor = '';
      if (isRunning) {
        btnToggle.textContent = '⏹️ Pause Engine (ઓટો ટ્રેડિંગ થોભાવો)';
        btnToggle.className = 'btn btn-stop';
        if (subText) {
          subText.textContent = '(ઓટો ટ્રેડિંગ ચાલુ છે: સિસ્ટમ આપોઆપ સારા સોદા શોધીને BUY અને SELL કરશે)';
          subText.style.color = '#15803D';
          subText.style.fontWeight = '600';
        }
      } else {
        btnToggle.textContent = '▶️ Start Auto-Trading (ઓટો ટ્રેડિંગ શરૂ કરો)';
        btnToggle.className = 'btn btn-primary';
        if (subText) {
          subText.textContent = '(સિસ્ટમ આપોઆપ સારા સોદા શોધીને BUY અને SELL કરશે)';
          subText.style.color = '#64748B';
          subText.style.fontWeight = '600';
        }
      }
    }

    // 4. Update Metrics (Respect active timeframe filter)
    if (currentPnlFilterDays === 1) {
      const netPnlElem = document.getElementById('net-pnl');
      const pnlCard = document.getElementById('pnl-card');
      const pnl = data.total_pnl || 0.0;
      if (pnl === 0) {
        netPnlElem.textContent = '₹0.00';
        netPnlElem.className = 'metric-value profit';
        pnlCard.className = 'metric-card pnl-card';
      } else if (pnl > 0) {
        netPnlElem.textContent = '+₹' + pnl.toLocaleString('en-IN', {minimumFractionDigits: 2});
        netPnlElem.className = 'metric-value profit';
        pnlCard.className = 'metric-card pnl-card';
      } else {
        netPnlElem.textContent = '-₹' + Math.abs(pnl).toLocaleString('en-IN', {minimumFractionDigits: 2});
        netPnlElem.className = 'metric-value loss';
        pnlCard.className = 'metric-card pnl-card negative';
      }

      document.getElementById('realized-pnl').textContent = 'Realized: ₹' + (data.daily_realized_pnl || 0.0);
      document.getElementById('unrealized-pnl').textContent = 'Open: ₹' + (data.active_unrealized_pnl || 0.0);
      document.getElementById('win-rate').textContent = (data.win_rate || 0) + '%';
      document.getElementById('win-counts').textContent = (data.closed_trades_count || 0) + ' Trades Executed';
    } else {
      applyPnlFilter(currentPnlFilterDays);
    }

    document.getElementById('managed-capital').textContent = '₹' + Number(data.total_managed_capital).toLocaleString('en-IN');
    document.getElementById('active-trades-count').textContent = data.active_trades_count || 0;

    // Capital %
    document.getElementById('capital-pct-slider').value = data.capital_allocation_pct;
    document.getElementById('capital-pct-val').textContent = data.capital_allocation_pct + '%';
    document.getElementById('metric-alloc-pct').textContent = data.capital_allocation_pct + '%';

    // Render Logs
    const logContainer = document.getElementById('log-stream');
    logContainer.innerHTML = (data.logs || []).map(l => `
      <div class="log-line log-${l.level}">
        <span class="log-time">[${l.timestamp}]</span> ${l.message}
      </div>
    `).join('');

  } catch (err) {
    console.error('Error fetching status:', err);
  }
}

async function fetchScanner() {
  try {
    const res = await fetch('/api/scanner');
    const opps = await res.json();
    const tbody = document.getElementById('scanner-table-body');
    
    tbody.innerHTML = opps.map(o => `
      <tr style="cursor: pointer;" onclick="switchChart('${o.symbol}')" title="ચાર્ટ જોવા માટે અહીં ક્લિક કરો">
        <td>
          <strong>${o.symbol}</strong><br>
          <small style="color: #64748B;">${o.name}</small>
        </td>
        <td>₹${Number(o.current_price).toLocaleString('en-IN')}</td>
        <td>
          <div class="score-bar"><div class="score-fill" style="width: ${o.score}%"></div></div>
          <strong>${o.score}</strong>
        </td>
        <td>
          <span class="${o.trade_type === 'SWING_DELIVERY' ? 'type-swing' : 'type-intraday'}">
            ${o.trade_type === 'SWING_DELIVERY' ? '📦 2-7d Swing' : '⚡ Intraday'}
          </span>
        </td>
        <td>₹${o.target_price} (+${o.target_pct}%)</td>
        <td>₹${o.stoploss_price} (-${o.stoploss_pct}%)</td>
        <td>
          <span class="badge ${o.status === 'SIGNAL_READY' ? 'badge-bullish' : 'badge-paper'}">
            ${o.status === 'SIGNAL_READY' ? '🟢 READY TO BUY' : '⏳ SCANNING'}
          </span>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error fetching scanner:', err);
  }
}

async function fetchActiveTrades() {
  try {
    const res = await fetch('/api/trades/active');
    const trades = await res.json();
    const tbody = document.getElementById('active-trades-body');
    const countBadge = document.getElementById('active-trades-badge');
    countBadge.textContent = trades.length;

    if (trades.length === 0) {
      tbody.innerHTML = `<tr><td colspan="8" style="text-align:center; color:#6B7280; padding:20px;">No open positions right now. Scanner is actively searching for high-probability setups.</td></tr>`;
      return;
    }

    tbody.innerHTML = trades.map(t => `
      <tr>
        <td><strong>${t.symbol}</strong><br><small style="color:#64748B;">${t.account_name}</small></td>
        <td><span class="${t.trade_type === 'SWING_DELIVERY' ? 'type-swing' : 'type-intraday'}">${t.trade_type}</span></td>
        <td>${t.qty}</td>
        <td>₹${t.entry_price}</td>
        <td>₹${t.current_price}</td>
        <td class="${t.unrealized_pnl >= 0 ? 'metric-value profit' : 'metric-value loss'}" style="font-size:0.85rem;">
          ${t.unrealized_pnl >= 0 ? '+' : ''}₹${t.unrealized_pnl} (${t.pnl_pct}%)
        </td>
        <td>
          <span style="color:#15803D; font-weight:700;">Tgt: ₹${t.target_price}</span><br>
          <span style="color:#DC2626; font-size:0.75rem;">SL: ₹${t.stoploss_price}</span>
          ${t.trailing_sl_price && t.trailing_sl_price > t.stoploss_price ? `<br><span style="background:#DCFCE7; color:#15803D; padding:1px 5px; border-radius:4px; font-weight:800; font-size:0.7rem; border:1px solid #86EFAC;">🛡️ Trail SL: ₹${t.trailing_sl_price}</span>` : ''}
        </td>
        <td>
          <button class="btn btn-secondary" style="padding:4px 8px; font-size:0.7rem;" onclick="manualCloseTrade('${t.id}')">Exit (વેચો)</button>
        </td>
      </tr>
    `).join('');
  } catch (err) {
    console.error('Error fetching active trades:', err);
  }
}

let currentHistoryFilter = 'today';

function setHistoryFilter(filter) {
  currentHistoryFilter = filter;
  const btnToday = document.getElementById('btn-hist-today');
  const btnAll = document.getElementById('btn-hist-all');
  if (btnToday && btnAll) {
    if (filter === 'today') {
      btnToday.style.background = '#FFFFFF';
      btnToday.style.color = '#0F172A';
      btnToday.style.fontWeight = '700';
      btnToday.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';
      btnAll.style.background = 'transparent';
      btnAll.style.color = '#64748B';
      btnAll.style.fontWeight = 'normal';
      btnAll.style.boxShadow = 'none';
    } else {
      btnAll.style.background = '#FFFFFF';
      btnAll.style.color = '#0F172A';
      btnAll.style.fontWeight = '700';
      btnAll.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)';
      btnToday.style.background = 'transparent';
      btnToday.style.color = '#64748B';
      btnToday.style.fontWeight = 'normal';
      btnToday.style.boxShadow = 'none';
    }
  }
  fetchTradeHistory();
}

async function exportTradesCSV() {
  window.open(`/api/trades/export-csv?filter=${currentHistoryFilter}`, '_blank');
}

async function fetchTradeHistory() {
  try {
    const res = await fetch(`/api/trades/history?filter=${currentHistoryFilter}`);
    const trades = await res.json();
    const tbody = document.getElementById('trade-history-body');
    const countBadge = document.getElementById('history-count-badge');
    const pnlBadge = document.getElementById('history-pnl-badge');

    if (!tbody) return;

    if (countBadge) {
      countBadge.textContent = `${trades.length} Trades`;
    }

    const totalPnL = trades.reduce((sum, t) => sum + (t.pnl || 0), 0);
    if (pnlBadge) {
      const isProfit = totalPnL >= 0;
      pnlBadge.textContent = `Realized: ${isProfit ? '+' : ''}₹${totalPnL.toFixed(2)}`;
      pnlBadge.style.color = isProfit ? '#15803D' : '#DC2626';
      pnlBadge.style.background = isProfit ? '#DCFCE7' : '#FEE2E2';
      pnlBadge.style.border = `1px solid ${isProfit ? '#86EFAC' : '#FCA5A5'}`;
    }

    if (!trades || trades.length === 0) {
      const emptyMsg = currentHistoryFilter === 'today'
        ? 'આજે હજુ કોઈ સોદો પૂર્ણ થયો નથી. માર્કેટ શરૂ થતાં ખરીદ-વેચાણની વિગત (કેટલામાં લીધા, કેટલામાં વેચ્યા, નફો) અહીં લાઈવ નોંધાશે.'
        : 'હજુ સુધી કોઈ સોદાનો ઇતિહાસ નોંધાયેલ નથી.';
      tbody.innerHTML = `<tr><td colspan="9" style="text-align:center; color:#64748B; padding:24px;">${emptyMsg}</td></tr>`;
      return;
    }

    tbody.innerHTML = trades.map((t) => {
      const pnl = Number(t.pnl || 0);
      const isProfit = pnl >= 0;
      const pnlColor = isProfit ? '#15803D' : '#DC2626';
      const pnlBg = isProfit ? '#DCFCE7' : '#FEE2E2';
      const pnlSign = isProfit ? '+' : '';
      
      const buyPrice = Number(t.entry_price || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      const sellPrice = Number(t.exit_price || 0).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      const pnlVal = Number(Math.abs(pnl)).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      
      const exitTimeStr = t.exit_date ? String(t.exit_date).slice(11, 19) : '--';
      const exitDateStr = t.exit_date ? String(t.exit_date).slice(0, 10) : '--';
      const entryTimeStr = t.entry_date ? String(t.entry_date).slice(11, 19) : '--';

      let reasonLabel = String(t.exit_reason || 'Exit');
      if (reasonLabel.includes('TARGET_HIT')) {
        reasonLabel = `<span style="background:#DCFCE7; color:#15803D; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #86EFAC;">🎯 Target Hit</span>`;
      } else if (reasonLabel.includes('TRAILING_SL')) {
        reasonLabel = `<span style="background:#DCFCE7; color:#166534; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #86EFAC;">🛡️ Trailing SL Locked</span>`;
      } else if (reasonLabel.includes('STOPLOSS_HIT')) {
        reasonLabel = `<span style="background:#FEE2E2; color:#DC2626; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #FCA5A5;">🛑 Stop Loss</span>`;
      } else if (reasonLabel.includes('INTRADAY_315') || reasonLabel.includes('MARKET_CLOSE')) {
        reasonLabel = `<span style="background:#FEF3C7; color:#B45309; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #FCD34D;">🕒 3:15 PM Square-off</span>`;
      } else if (reasonLabel.includes('MANUAL')) {
        reasonLabel = `<span style="background:#E2E8F0; color:#334155; font-weight:700; padding:2px 8px; border-radius:4px; border:1px solid #CBD5E1;">👤 Manual Exit</span>`;
      }

      const modeBadge = t.mode === 'LIVE' 
        ? `<span style="background:#DCFCE7; color:#15803D; font-size:0.68rem; padding:1px 5px; border-radius:4px; font-weight:700;">LIVE</span>`
        : `<span style="background:#F1F5F9; color:#64748B; font-size:0.68rem; padding:1px 5px; border-radius:4px; font-weight:700;">PAPER</span>`;

      return `
        <tr>
          <td>
            <strong>${exitTimeStr}</strong> <small style="color:#64748B;">(${exitDateStr})</small><br>
            <small style="color:#64748B;">લીધા: ${entryTimeStr}</small>
          </td>
          <td>
            <strong>${t.symbol}</strong> ${modeBadge}<br>
            <small style="color:#64748B;">${t.account_name || 'Account'}</small>
          </td>
          <td>
            <span class="${t.trade_type === 'SWING_DELIVERY' ? 'type-swing' : 'type-intraday'}">
              ${t.trade_type === 'SWING_DELIVERY' ? '📦 2-7d Swing' : '⚡ Intraday'}
            </span>
          </td>
          <td><strong>${t.qty}</strong> <small style="color:#64748B;">શેર</small></td>
          <td><span style="font-weight:700; color:#0F172A;">₹${buyPrice}</span></td>
          <td><span style="font-weight:700; color:#0F172A;">₹${sellPrice}</span></td>
          <td><span style="font-size:0.8rem; color:#475569;">${t.duration_str || '--'}</span></td>
          <td>
            <span style="font-weight:800; font-size:0.9rem; color:${pnlColor}; background:${pnlBg}; padding:2px 8px; border-radius:4px;">
              ${pnlSign}₹${pnlVal} (${pnlSign}${t.pnl_pct || 0}%)
            </span>
          </td>
          <td>${reasonLabel}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    console.error('Error fetching trade history:', err);
  }
}

async function fetchAccounts() {
  try {
    const res = await fetch('/api/accounts');
    const accounts = await res.json();
    const container = document.getElementById('accounts-container');

    if (!accounts || accounts.length === 0) {
      container.innerHTML = `
        <div style="background:#F8FAFC; border:1.5px dashed #CBD5E1; border-radius:8px; padding:22px; text-align:center; color:#64748B;">
          <p style="margin:0 0 10px 0; font-weight:700; color:#334155; font-size:0.9rem;">હાલમાં કોઈ ડિમેટ એકાઉન્ટ જોડાયેલું નથી.</p>
          <button class="btn btn-primary" style="padding:6px 14px; font-size:0.8rem;" onclick="openAddAccountModal()">
            + Add Account (તમારું INDstocks એકાઉન્ટ ઉમેરો)
          </button>
        </div>
      `;
      return;
    }

    container.innerHTML = accounts.map(a => `
      <div class="account-card" style="background:#FFFFFF; border:1px solid #CBD5E1; border-radius:8px; padding:12px; margin-bottom:12px; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
        <div class="account-info">
          <h4>${a.name} <span class="badge ${a.is_active ? 'badge-live' : 'badge-paper'}" style="font-size:0.65rem;">${a.is_active ? 'ACTIVE' : 'PAUSED'}</span></h4>
          <p>Broker: <strong>${a.broker}</strong> | Capital: <strong style="color:#0F172A; font-size:0.95rem;">₹${Number(a.total_capital).toLocaleString('en-IN')}</strong> | Allocation: <strong>${a.capital_allocation_pct}%</strong></p>
          <small style="color:#6B7280;">Token: ${a.access_token_masked || 'નથી નાખેલું (Paper Mode)'}</small>
        </div>
        <div style="display:flex; gap:6px; margin-top:8px; flex-wrap:wrap;">
          <button class="btn btn-primary" style="padding:4px 10px; font-size:0.72rem;" onclick="syncAccountFunds('${a.id}')" title="INDmoney માંથી સીધું લાઇવ બેલેન્સ ખેંચો">
            🔄 Auto-Sync INDmoney Balance
          </button>
          <button class="btn btn-secondary" style="padding:4px 10px; font-size:0.72rem;" onclick="editAccountCapital('${a.id}', ${a.total_capital})" title="તમારી પાસે INDmoney માં જે રકમ હોય તે અહીં લખો">
            ✏️ Edit Capital (મૂડી બદલો)
          </button>
          <button class="btn btn-secondary" style="padding:4px 10px; font-size:0.72rem;" onclick="editAccountToken('${a.id}')" title="તમારો INDstocks API Access Token સેટ કરો">
            🔑 Set API Token
          </button>
          <button class="btn btn-secondary" style="padding:4px 10px; font-size:0.72rem;" onclick="toggleAccount('${a.id}', ${!a.is_active})">
            ${a.is_active ? 'Pause' : 'Activate'}
          </button>
          <button class="btn btn-stop" style="padding:4px 8px; font-size:0.72rem;" onclick="deleteAccount('${a.id}')" title="આ એકાઉન્ટ રદ કરો">×</button>
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error fetching accounts:', err);
  }
}

async function editAccountToken(accId) {
  const token = prompt('તમારો INDstocks API Access Token અહીં પેસ્ટ કરો:\n(નોંધ: જો તમારી પાસે Token ન હોય તો ડેમો/પેપર મોડમાં ટોકન વગર પણ ટેસ્ટિંગ કરી શકાય છે)');
  if (token === null) return;
  try {
    const res = await fetch(`/api/accounts/${accId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ access_token: token.trim() })
    });
    if (res.ok) {
      alert(token.trim() ? 'INDstocks API Access Token સફળતાપૂર્વક અપડેટ થઈ ગયો છે!' : 'ટોકન હટાવી દેવામાં આવ્યો છે.');
      fetchAccounts();
      fetchStatus();
    } else {
      alert('ટોકન અપડેટ કરવામાં ભૂલ આવી.');
    }
  } catch (err) {
    alert('સર્વર સાથે કનેક્ટ ન થઈ શક્યું: ' + err);
  }
}

async function syncAccountFunds(accId) {
  try {
    const res = await fetch(`/api/accounts/${accId}/sync-funds`, { method: 'POST' });
    const data = await res.json();
    alert(data.message);
    fetchAccounts();
    fetchStatus();
  } catch (err) {
    alert('સર્વર સાથે કનેક્ટ ન થઈ શક્યું: ' + err);
  }
}

async function editAccountCapital(accId, currentVal) {
  const input = prompt('તમારા INDmoney એકાઉન્ટમાં અત્યારે જેટલા રૂપિયા ઉપલબ્ધ હોય તે રકમ અહીં લખો (₹):', currentVal);
  if (!input) return;
  const newCapital = parseFloat(input);
  if (isNaN(newCapital) || newCapital <= 0) {
    alert('કૃપા કરીને સાચી રકમ લખો.');
    return;
  }
  try {
    await fetch(`/api/accounts/${accId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ total_capital: newCapital })
    });
    fetchAccounts();
    fetchStatus();
  } catch (err) {
    alert('અપડેટ કરવામાં ભૂલ: ' + err);
  }
}

let lastRenderedNewsTitle = '';

// 100% Gujarati News Fetcher & Renderer (Stable, Zero auto-slide)
async function fetchNews(force = false) {
  try {
    const res = await fetch('/api/news');
    const news = await res.json();
    const container = document.getElementById('news-container');
    if (!container || !news || news.length === 0) return;

    // Prevent auto-sliding / jumping while reading
    if (!force && news[0].title === lastRenderedNewsTitle) {
      return; // Stable! Do NOT touch DOM, prevent jumping or sliding!
    }
    lastRenderedNewsTitle = news[0].title;

    container.style.maxHeight = '480px';
    container.style.overflowY = 'auto';
    container.style.paddingRight = '6px';

    container.innerHTML = news.map(n => `
      <div class="news-item" style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:12px; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.03);">
        <div class="news-header" style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
          <div style="display:flex; align-items:center; gap:8px;">
            <span style="font-size:0.75rem; font-weight:700; color:#1E293B; background:#F1F5F9; padding:2px 8px; border-radius:4px;">${n.source || 'માર્કેટ ડેસ્ક'}</span>
            <span style="font-size:0.72rem; color:#64748B;">🕒 ${n.published_at || 'હમણાં જ'}</span>
          </div>
          <span class="badge" style="font-size:0.72rem; font-weight:800; background:#DCFCE7; color:#166534; border:1px solid #86EFAC;">
            ${n.sentiment || '📈 તેજી'}
          </span>
        </div>
        <div class="news-title" style="font-size:0.88rem; font-weight:800; color:#0F172A; line-height:1.4; margin-bottom:5px;">
          ${n.title}
        </div>
        <div class="news-summary" style="font-size:0.80rem; color:#475569; line-height:1.45;">
          ${n.summary}
        </div>
      </div>
    `).join('');
  } catch (err) {
    console.error('Error fetching news:', err);
  }
}

async function refreshNewsNow() {
  try {
    lastRenderedNewsTitle = '';
    await fetch('/api/news/refresh', { method: 'POST' });
    await fetchNews(true);
  } catch (e) {
    await fetchNews(true);
  }
}

// User Actions
async function toggleEngine() {
  const btnToggle = document.getElementById('btn-toggle-engine');
  if (btnToggle && btnToggle.disabled) {
    alert('ભારતીય શેરબજાર (NSE/BSE) અત્યારે બંધ છે (03:30 PM પછી).\n\nબજાર બંધ હોવાથી ઓટો ટ્રેડિંગ સંપૂર્ણપણે બંધ છે. કોઈ પણ સોદો પડશે નહીં.\n\nઆવતીકાલે સવારે 09:15 વાગ્યે માર્કેટ ખુલતાં જ ઓટો ટ્રેડિંગ શરૂ કરી શકાશે.');
    return;
  }
  try {
    const res = await fetch('/api/engine/toggle', { method: 'POST' });
    const data = await res.json();
    if (data.status === 'blocked' || !data.market_open) {
      alert('સૂચના: ' + (data.message || 'ભારતીય શેરબજાર અત્યારે બંધ છે. ઓટો ટ્રેડિંગ શરૂ થઈ શકશે નહીં.'));
    }
    fetchStatus();
  } catch (e) {
    fetchStatus();
  }
}

async function toggleMode() {
  const nextMode = currentMode === 'PAPER' ? 'LIVE' : 'PAPER';
  if (nextMode === 'LIVE') {
    const confirmed = confirm('ચેતવણી: તમે સાચા પૈસાથી Live Trading મોડ શરૂ કરવા જઈ રહ્યા છો. શું તમે આગળ વધવા માંગો છો?');
    if (!confirmed) return;
  }
  await fetch('/api/engine/mode', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: nextMode })
  });
  fetchStatus();
}

async function updateCapitalPct(value) {
  document.getElementById('capital-pct-val').textContent = value + '%';
  await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ capital_allocation_pct: parseFloat(value) })
  });
  fetchStatus();
}

async function emergencyKill() {
  const confirmed = confirm('EMERGENCY KILL SWITCH: આ બટન દબાવવાથી તમામ એકાઉન્ટ્સના બધા જ ઓપન ટ્રેડ્સ તુરંત સ્ક્વેર-ઓફ થઈ જશે અને ઓટો ટ્રેડિંગ બંધ થઈ જશે. શું તમે ખરેખર આગળ વધવા માંગો છો?');
  if (!confirmed) return;
  await fetch('/api/emergency/kill', { method: 'POST' });
  fetchStatus();
  fetchActiveTrades();
  fetchTradeHistory();
}

async function manualCloseTrade(tradeId) {
  await fetch('/api/trades/close/' + tradeId, { method: 'POST' });
  fetchActiveTrades();
  fetchTradeHistory();
  fetchStatus();
}

async function toggleAccount(accId, isActive) {
  await fetch('/api/accounts/' + accId, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: isActive })
  });
  fetchAccounts();
  fetchStatus();
}

async function deleteAccount(accId) {
  if (!confirm('શું તમે ખરેખર આ એકાઉન્ટ રદ કરવા માંગો છો?')) return;
  try {
    const res = await fetch('/api/accounts/' + accId, { method: 'DELETE' });
    if (res.ok) {
      alert('એકાઉન્ટ સફળતાપૂર્વક ડિલીટ થઈ ગયું છે.');
    } else {
      const data = await res.json();
      alert('એકાઉન્ટ ડિલીટ કરવામાં સમસ્યા આવી: ' + (data.detail || 'ભૂલ'));
    }
  } catch (e) {
    alert('સર્વર સાથે કનેક્ટ ન થઈ શક્યું: ' + e);
  }
  fetchAccounts();
  fetchStatus();
}

function openAddAccountModal() {
  document.getElementById('add-account-modal').style.display = 'flex';
}

function closeAddAccountModal() {
  document.getElementById('add-account-modal').style.display = 'none';
}

async function submitAddAccount(e) {
  e.preventDefault();
  const payload = {
    name: document.getElementById('acc-name').value,
    broker: document.getElementById('acc-broker').value,
    access_token: document.getElementById('acc-token').value,
    total_capital: parseFloat(document.getElementById('acc-capital').value),
    capital_allocation_pct: parseFloat(document.getElementById('acc-alloc').value),
    is_active: true,
    is_paper: true
  };
  await fetch('/api/accounts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  closeAddAccountModal();
  fetchAccounts();
  fetchStatus();
}

function onBrokerChange(broker) {
  const lbl = document.getElementById('lbl-acc-token');
  const input = document.getElementById('acc-token');
  if (!lbl || !input) return;

  const brokerTokens = {
    'INDstocks': 'INDmoney Access Token',
    'Zerodha': 'Kite API Key & Access Token',
    'AngelOne': 'SmartAPI Key & JWT Token',
    'Groww': 'Groww Auth / API Token',
    'Upstox': 'Upstox API Access Token',
    'Dhan': 'Dhan Client ID & Access Token',
    'Fyers': 'Fyers App ID & Access Token',
    'KotakNeo': 'Kotak Neo Consumer Key & Secret',
    'ICICIDirect': 'Breeze API Key & Session Token',
    'HDFCSky': 'HDFC Sky API Access Token',
    'MotilalOswal': 'MOSL API Key & Token',
    '5paisa': '5paisa User Key & Encryption Key',
    'AliceBlue': 'ANT API Key & User ID',
    'Shoonya': 'Shoonya User ID & Token',
    'PaytmMoney': 'Paytm Money Access Token'
  };

  const name = brokerTokens[broker] || 'API Key / Access Token';
  lbl.textContent = `${name} (વૈકલ્પિક for Paper):`;
  input.placeholder = name;
}

// ============================================================
// Night Lamp Interactive Authentication System
// ============================================================
let dashboardLoopsStarted = false;

function playLampClickSound() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sine';
    osc.frequency.setValueAtTime(580, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(140, ctx.currentTime + 0.05);

    gain.gain.setValueAtTime(0.35, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.05);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.05);
  } catch (e) {}
}

function playRejectionSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = 'sawtooth';
    osc.frequency.setValueAtTime(130, ctx.currentTime);
    osc.frequency.setValueAtTime(85, ctx.currentTime + 0.12);

    gain.gain.setValueAtTime(0.45, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3);

    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (e) {}
}

function pullLampCord() {
  const cord = document.getElementById('lamp-cord');
  const screen = document.getElementById('lamp-login-screen');
  if (!cord || !screen) return;

  // Animate cord pull
  cord.classList.add('pulling');
  playLampClickSound();

  setTimeout(() => {
    cord.classList.remove('pulling');
  }, 220);

  // Toggle Lamp State
  const isNowOn = screen.classList.toggle('lamp-on');

  if (isNowOn) {
    setTimeout(() => {
      const pwdInput = document.getElementById('lamp-password');
      if (pwdInput) pwdInput.focus();
    }, 350);
  }
}

function showDashboardScreen() {
  const screen = document.getElementById('lamp-login-screen');
  const dashboard = document.getElementById('app-dashboard');
  if (screen) {
    screen.classList.add('hidden-screen');
    screen.classList.remove('visible-flex');
    screen.style.setProperty('display', 'none', 'important');
    screen.style.setProperty('visibility', 'hidden', 'important');
  }
  if (dashboard) {
    dashboard.classList.remove('hidden-screen');
    dashboard.classList.add('visible-screen');
    dashboard.style.setProperty('display', 'block', 'important');
    dashboard.style.setProperty('visibility', 'visible', 'important');
  }
}

function showLoginScreen() {
  const screen = document.getElementById('lamp-login-screen');
  const dashboard = document.getElementById('app-dashboard');
  if (dashboard) {
    dashboard.classList.add('hidden-screen');
    dashboard.classList.remove('visible-screen');
    dashboard.style.setProperty('display', 'none', 'important');
    dashboard.style.setProperty('visibility', 'hidden', 'important');
  }
  if (screen) {
    screen.classList.remove('hidden-screen');
    screen.classList.add('visible-flex');
    screen.classList.add('lamp-on');
    screen.style.setProperty('display', 'flex', 'important');
    screen.style.setProperty('visibility', 'visible', 'important');
  }
}

async function checkAuthentication() {
  // Clear any old persistent local storage tokens so opening platform ALWAYS starts at the lamp screen
  localStorage.removeItem('algo_auth_token');
  
  const token = sessionStorage.getItem('algo_auth_token');
  
  if (!token) {
    showLoginScreen();
    return false;
  }
  try {
    const res = await fetch(`/api/auth/check?token=${encodeURIComponent(token)}`);
    const data = await res.json();
    if (data.authenticated) {
      showDashboardScreen();
      const savedUser = sessionStorage.getItem('algo_auth_user') || 'Raxit@5001';
      const userBadge = document.getElementById('user-badge');
      if (userBadge) userBadge.textContent = `👤 ${savedUser}`;
      return true;
    } else {
      sessionStorage.removeItem('algo_auth_token');
      showLoginScreen();
      return false;
    }
  } catch (e) {
    showDashboardScreen();
    return true; // Fallback in case of brief network disconnect
  }
}

async function submitLampLogin(e) {
  if (e) {
    e.preventDefault();
  }
  const userEl = document.getElementById('lamp-username');
  const passEl = document.getElementById('lamp-password');
  const username = userEl ? userEl.value.trim() : '';
  const password = passEl ? passEl.value.trim() : '';
  const errDiv = document.getElementById('lamp-login-error');
  const card = document.querySelector('.lamp-login-card');
  const submitBtn = document.querySelector('.btn-lamp-login');

  if (!username || !password) {
    if (errDiv) {
      errDiv.innerHTML = '<strong>⚠️ અધૂરું ફોર્મ:</strong> કૃપા કરીને User ID અને Password બંને દાખલ કરો.';
      errDiv.style.display = 'block';
    }
    if (!username && userEl) userEl.focus();
    else if (!password && passEl) passEl.focus();
    return;
  }

  if (errDiv) errDiv.style.display = 'none';
  if (card) card.classList.remove('shake-error');
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = '⏳ પ્રવેશ થઈ રહ્યો છે...';
  }

  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.token) {
      sessionStorage.setItem('algo_auth_token', data.token);
      sessionStorage.setItem('algo_auth_user', data.username);
      
      showDashboardScreen();
      
      const userBadge = document.getElementById('user-badge');
      if (userBadge) userBadge.textContent = `👤 ${data.username}`;
      startDashboardLoops();
    } else {
      playRejectionSound();
      if (card) {
        void card.offsetWidth; // Trigger reflow to restart animation
        card.classList.add('shake-error');
      }
      if (errDiv) {
        errDiv.innerHTML = `<strong>⛔ પ્રવેશ નામંજૂર:</strong><br/>${data.detail || 'અમાન્ય User ID અથવા Password. સાચો પાસવર્ડ દાખલ કરો!'}`;
        errDiv.style.display = 'block';
      }
      if (passEl) {
        passEl.value = '';
        passEl.focus();
      }
    }
  } catch (err) {
    if (errDiv) {
      errDiv.textContent = 'સર્વર સાથે કનેક્ટ ન થઈ શક્યું: ' + err;
      errDiv.style.display = 'block';
    }
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = 'Login';
    }
  }
}

function showForgotPasswordView(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const loginView = document.getElementById('lamp-view-login');
  const forgotView = document.getElementById('lamp-view-forgot');
  const card = document.querySelector('.lamp-login-card');
  if (card) card.classList.remove('shake-error');

  if (loginView && forgotView) {
    loginView.style.display = 'none';
    forgotView.style.display = 'block';

    const errDiv = document.getElementById('card-forgot-error');
    const succDiv = document.getElementById('card-forgot-success');
    if (errDiv) errDiv.style.display = 'none';
    if (succDiv) succDiv.style.display = 'none';

    const userInp = document.getElementById('card-forgot-user');
    if (userInp) {
      userInp.value = '';
      setTimeout(() => userInp.focus(), 80);
    }
    const pinInp = document.getElementById('card-forgot-pin');
    if (pinInp) pinInp.value = '';
    const passInp = document.getElementById('card-forgot-newpass');
    if (passInp) passInp.value = '';
    const confInp = document.getElementById('card-forgot-confpass');
    if (confInp) confInp.value = '';
  }
}

function showLoginView(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const loginView = document.getElementById('lamp-view-login');
  const forgotView = document.getElementById('lamp-view-forgot');
  if (loginView && forgotView) {
    forgotView.style.display = 'none';
    loginView.style.display = 'block';
  }
}

let verifiedRecoveryUser = '';
let verifiedRecoveryPin = '';

function openForgotPasswordModal(e) {
  if (e) {
    e.preventDefault();
    e.stopPropagation();
  }
  const modal = document.getElementById('forgot-password-modal');
  if (!modal) return;
  modal.style.display = 'flex';
  
  const step1 = document.getElementById('forgot-step-1');
  const step2 = document.getElementById('forgot-step-2');
  const title = document.getElementById('forgot-modal-title');
  if (step1) step1.style.display = 'block';
  if (step2) step2.style.display = 'none';
  if (title) title.innerHTML = '<span>🔐</span> Reset Password';

  const errDiv = document.getElementById('forgot-modal-error');
  const succDiv = document.getElementById('forgot-modal-success');
  if (errDiv) errDiv.style.display = 'none';
  if (succDiv) succDiv.style.display = 'none';
  
  const userInp = document.getElementById('forgot-user');
  if (userInp) {
    userInp.value = '';
    setTimeout(() => userInp.focus(), 100);
  }
  
  const pinInp = document.getElementById('forgot-pin');
  if (pinInp) pinInp.value = '';
  
  const passInp = document.getElementById('forgot-new-pass');
  if (passInp) passInp.value = '';
  
  const confInp = document.getElementById('forgot-confirm-pass');
  if (confInp) confInp.value = '';

  verifiedRecoveryUser = '';
  verifiedRecoveryPin = '';
}

function closeForgotPasswordModal() {
  const modal = document.getElementById('forgot-password-modal');
  if (modal) modal.style.display = 'none';
}

function backToStep1() {
  const step1 = document.getElementById('forgot-step-1');
  const step2 = document.getElementById('forgot-step-2');
  const title = document.getElementById('forgot-modal-title');
  if (step1) step1.style.display = 'block';
  if (step2) step2.style.display = 'none';
  if (title) title.innerHTML = '<span>🔐</span> Reset Password';
  
  const errDiv = document.getElementById('forgot-modal-error');
  if (errDiv) errDiv.style.display = 'none';
}

async function verifyPinStep(e) {
  e.preventDefault();
  const username = document.getElementById('forgot-user').value.trim();
  const pin = document.getElementById('forgot-pin').value.trim();

  const errDiv = document.getElementById('forgot-modal-error');
  const succDiv = document.getElementById('forgot-modal-success');
  if (errDiv) errDiv.style.display = 'none';
  if (succDiv) succDiv.style.display = 'none';

  if (!username) {
    if (errDiv) {
      errDiv.textContent = 'Please enter your User ID.';
      errDiv.style.display = 'block';
    }
    return;
  }

  if (!pin) {
    if (errDiv) {
      errDiv.textContent = 'Please enter your Recovery PIN.';
      errDiv.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch('/api/auth/verify-pin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, pin })
    });
    const data = await res.json();
    if (res.ok) {
      verifiedRecoveryUser = username;
      verifiedRecoveryPin = pin;
      
      // Smoothly transition to Step 2: Set New Password
      const step1 = document.getElementById('forgot-step-1');
      const step2 = document.getElementById('forgot-step-2');
      const title = document.getElementById('forgot-modal-title');
      if (step1) step1.style.display = 'none';
      if (step2) step2.style.display = 'block';
      if (title) title.innerHTML = '<span>🔐</span> Set New Password';

      const passInp = document.getElementById('forgot-new-pass');
      if (passInp) {
        passInp.value = '';
        setTimeout(() => passInp.focus(), 100);
      }
      const confInp = document.getElementById('forgot-confirm-pass');
      if (confInp) confInp.value = '';
    } else {
      if (errDiv) {
        errDiv.textContent = '⛔ ' + (data.detail || 'Incorrect Recovery PIN or User ID.');
        errDiv.style.display = 'block';
      }
      playRejectionSound();
    }
  } catch (err) {
    if (errDiv) {
      errDiv.textContent = 'Failed to connect to server: ' + err;
      errDiv.style.display = 'block';
    }
  }
}

async function submitNewPasswordStep(e) {
  e.preventDefault();
  const username = verifiedRecoveryUser || document.getElementById('forgot-user').value.trim();
  const pin = verifiedRecoveryPin || document.getElementById('forgot-pin').value.trim();
  const new_password = document.getElementById('forgot-new-pass').value.trim();
  const confirm_password = document.getElementById('forgot-confirm-pass').value.trim();

  const errDiv = document.getElementById('forgot-modal-error');
  const succDiv = document.getElementById('forgot-modal-success');
  if (errDiv) errDiv.style.display = 'none';
  if (succDiv) succDiv.style.display = 'none';

  if (new_password !== confirm_password) {
    if (errDiv) {
      errDiv.textContent = 'Passwords do not match!';
      errDiv.style.display = 'block';
    }
    return;
  }

  if (new_password.length < 4) {
    if (errDiv) {
      errDiv.textContent = 'New password must be at least 4 characters.';
      errDiv.style.display = 'block';
    }
    return;
  }

  try {
    const res = await fetch('/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, pin, new_password })
    });
    const data = await res.json();
    if (res.ok) {
      if (succDiv) {
        succDiv.textContent = '✅ Password reset successfully!';
        succDiv.style.display = 'block';
      }
      setTimeout(() => {
        closeForgotPasswordModal();
        const pwdInput = document.getElementById('lamp-password');
        if (pwdInput) {
          pwdInput.value = '';
          pwdInput.focus();
        }
        const lampErr = document.getElementById('lamp-login-error');
        if (lampErr) {
          lampErr.innerHTML = `<span style="color:#86efac;">✅ Password reset successfully! Please login with your new password.</span>`;
          lampErr.style.display = 'block';
        }
      }, 1000);
    } else {
      if (errDiv) {
        errDiv.textContent = '⛔ ' + (data.detail || 'Failed to reset password.');
        errDiv.style.display = 'block';
      }
      playRejectionSound();
    }
  } catch (err) {
    if (errDiv) {
      errDiv.textContent = 'Failed to connect to server: ' + err;
      errDiv.style.display = 'block';
    }
  }
}

async function submitForgotPassword(e) {
  return submitNewPasswordStep(e);
}

async function logoutUser() {
  if (!confirm('શું તમે ખરેખર લૉગઆઉટ કરવા માંગો છો?')) return;
  const token = sessionStorage.getItem('algo_auth_token');
  if (token) {
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token })
      });
    } catch (e) {}
  }
  sessionStorage.removeItem('algo_auth_token');
  sessionStorage.removeItem('algo_auth_user');
  localStorage.removeItem('algo_auth_token');
  localStorage.removeItem('algo_auth_user');
  
  showLoginScreen();

  const pwdInput = document.getElementById('lamp-password');
  if (pwdInput) pwdInput.value = '';
}

function openChangePasswordModal() {
  document.getElementById('change-password-modal').style.display = 'flex';
  const savedUser = sessionStorage.getItem('algo_auth_user') || 'Raxit@5001';
  document.getElementById('chg-new-user').value = savedUser;
  document.getElementById('chg-old-pass').value = '';
  document.getElementById('chg-new-pass').value = '';
}

function closeChangePasswordModal() {
  document.getElementById('change-password-modal').style.display = 'none';
}

async function submitChangePassword(e) {
  e.preventDefault();
  const old_password = document.getElementById('chg-old-pass').value.trim();
  const new_username = document.getElementById('chg-new-user').value.trim();
  const new_password = document.getElementById('chg-new-pass').value.trim();

  try {
    const res = await fetch('/api/auth/change-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ old_password, new_username, new_password })
    });
    const data = await res.json();
    if (res.ok) {
      alert(data.message || 'ID અને પાસવર્ડ સફળતાપૂર્વક અપડેટ થઈ ગયા છે!');
      closeChangePasswordModal();
      sessionStorage.setItem('algo_auth_user', new_username);
      const userBadge = document.getElementById('user-badge');
      if (userBadge) userBadge.textContent = `👤 ${new_username}`;
    } else {
      alert('ભૂલ: ' + (data.detail || 'પાસવર્ડ બદલી શકાયો નહીં'));
    }
  } catch (err) {
    alert('સર્વર સાથે કનેક્ટ ન થઈ શક્યું: ' + err);
  }
}

function startDashboardLoops() {
  if (dashboardLoopsStarted) return;
  dashboardLoopsStarted = true;

  try { fetchStatus(); } catch (e) { console.error('fetchStatus err:', e); }
  try { fetchScanner(); } catch (e) { console.error('fetchScanner err:', e); }
  try { fetchActiveTrades(); } catch (e) { console.error('fetchActiveTrades err:', e); }
  try { fetchTradeHistory(); } catch (e) { console.error('fetchTradeHistory err:', e); }
  try { fetchAccounts(); } catch (e) { console.error('fetchAccounts err:', e); }
  try { fetchNews(); } catch (e) { console.error('fetchNews err:', e); }
  try { initNativeChart('NIFTY'); } catch (e) { console.error('initNativeChart err:', e); }

  setInterval(() => { try { fetchLiveTicks(); } catch(e){} }, 500);
  setInterval(() => { try { fetchActiveTrades(); } catch(e){} }, 2000);
  setInterval(() => { try { fetchTradeHistory(); } catch(e){} }, 3000);
  setInterval(() => { try { fetchStatus(); } catch(e){} }, 3000);
  setInterval(() => { try { fetchScanner(); } catch(e){} }, 5000);
  setInterval(() => { try { fetchNews(false); } catch(e){} }, 20000);
}

let activeMobileUrl = '';

async function openMobileConnectModal() {
  const modal = document.getElementById('mobile-connect-modal');
  const linkInput = document.getElementById('mobile-link-input');
  const qrImg = document.getElementById('mobile-qr-img');
  
  if (modal) modal.style.display = 'flex';
  
  try {
    const res = await fetch('/api/tunnel-url');
    const data = await res.json();
    activeMobileUrl = data.tunnel_url || data.local_ip_url || window.location.origin;
    
    if (linkInput) {
      linkInput.value = activeMobileUrl;
    }
    if (qrImg && activeMobileUrl) {
      qrImg.src = 'https://api.qrserver.com/v1/create-qr-code/?size=220x220&data=' + encodeURIComponent(activeMobileUrl);
    }
  } catch (err) {
    console.error('Error fetching mobile URL:', err);
    if (linkInput) linkInput.value = window.location.origin;
  }
}

function closeMobileConnectModal() {
  const modal = document.getElementById('mobile-connect-modal');
  if (modal) modal.style.display = 'none';
}

function copyMobileLink() {
  const linkInput = document.getElementById('mobile-link-input');
  const copyBtn = document.getElementById('btn-copy-mobile-link');
  if (linkInput) {
    linkInput.select();
    navigator.clipboard.writeText(linkInput.value).then(() => {
      if (copyBtn) {
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '✅ કોપી થઈ ગયું!';
        setTimeout(() => { copyBtn.innerHTML = originalText; }, 2000);
      }
    }).catch(() => {
      document.execCommand('copy');
      if (copyBtn) {
        copyBtn.innerHTML = '✅ કોપી થઈ ગયું!';
        setTimeout(() => { copyBtn.innerHTML = '📋 કોપી'; }, 2000);
      }
    });
  }
}

// Initial loader guarded by Authentication
window.onload = async () => {
  const isAuth = await checkAuthentication();
  if (isAuth) {
    startDashboardLoops();
  }
};
