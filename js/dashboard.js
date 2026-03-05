/* ═══════════════════════════════════════════════════════════
   js/dashboard.js  —  Trading Dashboard Interactivity
   Project: Stock Trading Quant Bot with Dashboard

   HOW Chart.js is loaded (in dashboard.html, before this file):
   <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
   <script src="js/dashboard.js"></script>
   ═══════════════════════════════════════════════════════════ */

'use strict';

// ─────────────────────────────────────────────
// 1.  GLOBAL STATE
// ─────────────────────────────────────────────
let priceChart = null;   // holds the active Chart.js instance

// Strategy display names
const STRATEGY_NAMES = { ma: 'Moving Average', rsi: 'RSI', macd: 'MACD' };

// Number of price points per timeframe
const TIMEFRAME_POINTS = { '1m': 50, '3m': 90, '1y': 252 };


// ─────────────────────────────────────────────
// 2.  PRICE DATA GENERATOR
//     Produces a realistic random walk with
//     slight upward drift and occasional jumps
// ─────────────────────────────────────────────
function generatePriceData(timeframe) {
  const points   = TIMEFRAME_POINTS[timeframe] || 50;
  const labels   = [];
  const prices   = [];

  // Start at a realistic price between $150–$220
  let price      = 150 + Math.random() * 70;
  const today    = new Date('2024-02-15');

  for (let i = points - 1; i >= 0; i--) {
    // Build date label
    const d = new Date(today);
    d.setDate(today.getDate() - i);
    labels.push(d.toISOString().slice(0, 10));

    // Random walk: small daily move ±2%, slight positive drift, rare spike
    const drift    =  0.0003;                         // tiny upward bias
    const sigma    =  0.018;                          // daily volatility
    const shock    = (Math.random() < 0.04) ? (Math.random() - 0.5) * 0.06 : 0;
    const dailyRet = drift + sigma * (Math.random() * 2 - 1) + shock;
    price          = Math.max(price * (1 + dailyRet), 80);
    prices.push(parseFloat(price.toFixed(2)));
  }

  return { labels, prices };
}


// ─────────────────────────────────────────────
// 3.  INDICATOR CALCULATORS
// ─────────────────────────────────────────────

/** Simple Moving Average over `period` bars */
function calcSMA(prices, period) {
  return prices.map((_, i) => {
    if (i < period - 1) return null;
    const slice = prices.slice(i - period + 1, i + 1);
    return parseFloat((slice.reduce((a, b) => a + b, 0) / period).toFixed(2));
  });
}

/** Relative Strength Index */
function calcRSI(prices, period = 14) {
  const rsi = Array(prices.length).fill(null);
  if (prices.length < period + 1) return rsi;

  let gains = 0, losses = 0;
  for (let i = 1; i <= period; i++) {
    const diff = prices[i] - prices[i - 1];
    if (diff >= 0) gains += diff; else losses -= diff;
  }
  let avgGain = gains / period;
  let avgLoss = losses / period;
  rsi[period] = avgLoss === 0 ? 100 : parseFloat((100 - 100 / (1 + avgGain / avgLoss)).toFixed(2));

  for (let i = period + 1; i < prices.length; i++) {
    const diff = prices[i] - prices[i - 1];
    avgGain = (avgGain * (period - 1) + Math.max(diff, 0)) / period;
    avgLoss = (avgLoss * (period - 1) + Math.max(-diff, 0)) / period;
    rsi[i]  = avgLoss === 0 ? 100 : parseFloat((100 - 100 / (1 + avgGain / avgLoss)).toFixed(2));
  }
  return rsi;
}

/** MACD line and Signal line */
function calcMACD(prices) {
  function ema(data, period) {
    const k   = 2 / (period + 1);
    const out = Array(data.length).fill(null);
    let   sum = 0, count = 0;
    for (let i = 0; i < data.length; i++) {
      if (data[i] === null) continue;
      if (count < period) { sum += data[i]; count++; if (count === period) out[i] = sum / period; }
      else { out[i] = data[i] * k + out[i - 1] * (1 - k); }
    }
    return out;
  }
  const ema12   = ema(prices, 12);
  const ema26   = ema(prices, 26);
  const macdLine = ema12.map((v, i) => (v !== null && ema26[i] !== null) ? parseFloat((v - ema26[i]).toFixed(4)) : null);
  const signalLine = ema(macdLine, 9);
  return { macdLine, signalLine };
}


// ─────────────────────────────────────────────
// 4.  SIGNAL GENERATORS  (per strategy)
//     Returns array of { index, date, signal, price }
// ─────────────────────────────────────────────
function generateSignals(strategy, labels, prices) {
  const signals = [];

  if (strategy === 'ma') {
    // Crossover: SMA10 crosses SMA30
    const sma10 = calcSMA(prices, 10);
    const sma30 = calcSMA(prices, 30);
    for (let i = 31; i < prices.length; i++) {
      if (sma10[i] === null || sma30[i] === null) continue;
      const crossUp   = sma10[i] > sma30[i] && sma10[i-1] <= sma30[i-1];
      const crossDown = sma10[i] < sma30[i] && sma10[i-1] >= sma30[i-1];
      if (crossUp)   signals.push({ index: i, date: labels[i], signal: 'BUY',  price: prices[i] });
      if (crossDown) signals.push({ index: i, date: labels[i], signal: 'SELL', price: prices[i] });
    }

  } else if (strategy === 'rsi') {
    // Oversold (<30) → BUY, Overbought (>70) → SELL
    const rsi = calcRSI(prices, 14);
    let lastSig = null;
    for (let i = 1; i < prices.length; i++) {
      if (rsi[i] === null) continue;
      if (rsi[i] < 30 && (lastSig !== 'BUY')) {
        signals.push({ index: i, date: labels[i], signal: 'BUY',  price: prices[i] });
        lastSig = 'BUY';
      } else if (rsi[i] > 70 && (lastSig !== 'SELL')) {
        signals.push({ index: i, date: labels[i], signal: 'SELL', price: prices[i] });
        lastSig = 'SELL';
      }
    }

  } else if (strategy === 'macd') {
    // MACD line crosses Signal line
    const { macdLine, signalLine } = calcMACD(prices);
    for (let i = 1; i < prices.length; i++) {
      if (macdLine[i] === null || signalLine[i] === null) continue;
      const crossUp   = macdLine[i] > signalLine[i] && macdLine[i-1] <= signalLine[i-1];
      const crossDown = macdLine[i] < signalLine[i] && macdLine[i-1] >= signalLine[i-1];
      if (crossUp)   signals.push({ index: i, date: labels[i], signal: 'BUY',  price: prices[i] });
      if (crossDown) signals.push({ index: i, date: labels[i], signal: 'SELL', price: prices[i] });
    }
  }

  // Always return at least a couple of fallback signals for display
  if (signals.length === 0) {
    const mid = Math.floor(prices.length / 2);
    signals.push({ index: 10,  date: labels[10],  signal: 'BUY',  price: prices[10]  });
    signals.push({ index: mid, date: labels[mid],  signal: 'SELL', price: prices[mid] });
  }

  return signals;
}


// ─────────────────────────────────────────────
// 5.  PERFORMANCE METRICS  (computed from signals)
// ─────────────────────────────────────────────
function calcMetrics(signals) {
  // Simulate simple long-only: buy on BUY, sell on next SELL
  let totalReturn = 0, wins = 0, numTrades = 0, maxDD = 0;
  let equity = 100, peak = 100;

  let buyPrice = null;
  signals.forEach(sig => {
    if (sig.signal === 'BUY' && buyPrice === null) {
      buyPrice = sig.price;
    } else if (sig.signal === 'SELL' && buyPrice !== null) {
      const ret    = (sig.price - buyPrice) / buyPrice * 100;
      totalReturn += ret;
      equity      *= (1 + ret / 100);
      if (equity > peak) peak = equity;
      const dd = ((peak - equity) / peak) * 100;
      if (dd > maxDD) maxDD = dd;
      if (ret > 0) wins++;
      numTrades++;
      buyPrice = null;
    }
  });

  return {
    totalReturn : parseFloat(totalReturn.toFixed(1)),
    winRate     : numTrades > 0 ? Math.round((wins / numTrades) * 100) : 0,
    numTrades,
    maxDD       : parseFloat(maxDD.toFixed(1)),
  };
}


// ─────────────────────────────────────────────
// 6.  CHART RENDERER
// ─────────────────────────────────────────────
function renderChart(symbol, strategy, labels, prices, signals) {
  if (priceChart) { priceChart.destroy(); priceChart = null; }

  // Build secondary line per strategy
  let secondaryDataset = null;
  if (strategy === 'ma') {
    secondaryDataset = {
      label: 'SMA 10',
      data: calcSMA(prices, 10),
      borderColor: '#00b37d',
      borderWidth: 1.5,
      borderDash: [5, 4],
      pointRadius: 0,
      fill: false,
      tension: 0.4,
    };
  } else if (strategy === 'rsi') {
    // Show SMA30 as context when RSI is the strategy
    secondaryDataset = {
      label: 'SMA 30',
      data: calcSMA(prices, 30),
      borderColor: '#f0b429',
      borderWidth: 1.5,
      borderDash: [4, 3],
      pointRadius: 0,
      fill: false,
      tension: 0.4,
    };
  } else if (strategy === 'macd') {
    const { macdLine } = calcMACD(prices);
    secondaryDataset = {
      label: 'MACD',
      data: macdLine.map((v, i) => v !== null ? parseFloat((prices[i] + v * 10).toFixed(2)) : null),
      borderColor: '#a855f7',
      borderWidth: 1.5,
      borderDash: [3, 3],
      pointRadius: 0,
      fill: false,
      tension: 0.3,
    };
  }

  // BUY / SELL scatter points on the chart
  const buyPoints  = signals.filter(s => s.signal === 'BUY' ).map(s => ({ x: s.date, y: s.price }));
  const sellPoints = signals.filter(s => s.signal === 'SELL').map(s => ({ x: s.date, y: s.price }));

  const chartArea = document.getElementById('chart-area');
  chartArea.innerHTML = '<canvas id="price-canvas"></canvas>';
  const ctx = document.getElementById('price-canvas').getContext('2d');

  const gradient = ctx.createLinearGradient(0, 0, 0, 320);
  gradient.addColorStop(0, 'rgba(0, 87, 255, 0.15)');
  gradient.addColorStop(1, 'rgba(0, 87, 255, 0.0)');

  const datasets = [
    {
      label: `${symbol} Price`,
      data: prices,
      borderColor: '#0057ff',
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointHoverBackgroundColor: '#0057ff',
      fill: true,
      backgroundColor: gradient,
      tension: 0.35,
      order: 2,
    },
  ];

  if (secondaryDataset) datasets.push({ ...secondaryDataset, order: 3 });

  // BUY markers
  datasets.push({
    label: 'BUY',
    data: labels.map((l, i) => {
      const found = buyPoints.find(p => p.x === l);
      return found ? found.y : null;
    }),
    borderColor: '#00b37d',
    backgroundColor: '#00b37d',
    pointRadius: labels.map(l => buyPoints.find(p => p.x === l) ? 7 : 0),
    pointStyle: 'triangle',
    showLine: false,
    order: 1,
  });

  // SELL markers
  datasets.push({
    label: 'SELL',
    data: labels.map((l, i) => {
      const found = sellPoints.find(p => p.x === l);
      return found ? found.y : null;
    }),
    borderColor: '#e03b3b',
    backgroundColor: '#e03b3b',
    pointRadius: labels.map(l => sellPoints.find(p => p.x === l) ? 7 : 0),
    pointStyle: 'triangle',
    rotation: 180,
    showLine: false,
    order: 1,
  });

  priceChart = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 2.8,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          align: 'end',
          labels: {
            font: { family: "'Share Tech Mono', monospace", size: 10 },
            color: '#6b7a99',
            boxWidth: 12,
            padding: 14,
            filter: item => item.text !== 'BUY' && item.text !== 'SELL'
                            ? true
                            : item.text === 'BUY' || item.text === 'SELL',
          },
        },
        tooltip: {
          backgroundColor: '#0f1923',
          titleFont: { family: "'Share Tech Mono', monospace", size: 10 },
          bodyFont:  { family: "'Share Tech Mono', monospace", size: 11 },
          padding: 10,
          callbacks: {
            label: ctx => {
              if (ctx.parsed.y === null) return null;
              return ` ${ctx.dataset.label}: $${ctx.parsed.y.toFixed(2)}`;
            },
          },
        },
      },
      scales: {
        x: {
          ticks: {
            font: { family: "'Share Tech Mono', monospace", size: 9 },
            color: '#8899aa',
            maxTicksLimit: 8,
            maxRotation: 0,
          },
          grid: { color: '#f0f2f6' },
        },
        y: {
          ticks: {
            font: { family: "'Share Tech Mono', monospace", size: 9 },
            color: '#8899aa',
            callback: val => `$${val.toFixed(0)}`,
          },
          grid: { color: '#f0f2f6' },
        },
      },
    },
  });
}


// ─────────────────────────────────────────────
// 7.  SIGNAL TABLE RENDERER
// ─────────────────────────────────────────────
function renderSignalTable(signals, strategyName) {
  const tbody = document.querySelector('.signals-table tbody');
  const badge = document.querySelector('.table-badge');
  tbody.innerHTML = '';

  // Show max 8 most recent signals
  const display = signals.slice(-8).reverse();

  display.forEach(row => {
    const tr          = document.createElement('tr');
    const signalClass = row.signal === 'BUY' ? 'buy' : 'sell';
    tr.style.animation = 'rowFadeIn 0.3s ease both';
    tr.innerHTML = `
      <td class="mono">${row.date}</td>
      <td><span class="signal-badge ${signalClass}">${row.signal}</span></td>
      <td class="mono">$${row.price.toFixed(2)}</td>
      <td>${strategyName}</td>
    `;
    tbody.appendChild(tr);
  });

  if (badge) badge.textContent = `${signals.length} signal${signals.length !== 1 ? 's' : ''}`;
}


// ─────────────────────────────────────────────
// 8.  METRICS RENDERER
// ─────────────────────────────────────────────
function renderMetrics(metrics) {
  const values = document.querySelectorAll('.metric-value');
  if (values.length < 4) return;

  const { totalReturn, winRate, numTrades, maxDD } = metrics;
  const isPositive = totalReturn >= 0;

  values[0].textContent = (isPositive ? '+' : '') + totalReturn + '%';
  values[0].className   = 'metric-value ' + (isPositive ? 'positive' : 'negative');

  values[1].textContent = winRate + '%';
  values[1].className   = 'metric-value ' + (winRate >= 50 ? 'positive' : 'negative');

  values[2].textContent = numTrades;
  values[2].className   = 'metric-value neutral';

  values[3].textContent = '-' + maxDD + '%';
  values[3].className   = 'metric-value negative';
}

function flashCards() {
  document.querySelectorAll('.metric-card').forEach((card, i) => {
    setTimeout(() => {
      card.style.transform = 'translateY(-4px)';
      card.style.boxShadow = '0 8px 24px rgba(0,87,255,0.14)';
      setTimeout(() => { card.style.transform = ''; card.style.boxShadow = ''; }, 350);
    }, i * 80);
  });
}


// ─────────────────────────────────────────────
// 9.  MAIN — wire up DOM events
// ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {

  const runBtn      = document.getElementById('run-strategy-btn');
  const symbolInput = document.getElementById('stock-symbol');
  const strategyEl  = document.getElementById('strategy-select');
  const timeframeEl = document.getElementById('timeframe-select');
  const tickerLabel = document.getElementById('chart-ticker-label');
  const stratLabel  = document.getElementById('chart-strategy-label');

  // ── Live toolbar label sync ──
  symbolInput.addEventListener('input', () => {
    tickerLabel.textContent = symbolInput.value.toUpperCase() || 'AAPL';
  });
  strategyEl.addEventListener('change', () => {
    stratLabel.textContent = STRATEGY_NAMES[strategyEl.value];
  });

  // ── Run Strategy button ──
  runBtn.addEventListener('click', () => {
    const symbol       = symbolInput.value.trim().toUpperCase() || 'AAPL';
    const strategy     = strategyEl.value;
    const timeframe    = timeframeEl.value;
    const strategyName = STRATEGY_NAMES[strategy];

    // Update toolbar
    tickerLabel.textContent = symbol;
    stratLabel.textContent  = strategyName;

    // Loading state
    runBtn.disabled  = true;
    runBtn.innerHTML = '⏳ Running...';

    /*
     * setTimeout simulates async API latency.
     * When Flask backend is ready, replace this block with:
     *
     *   fetch(`/api/run?symbol=${symbol}&strategy=${strategy}&timeframe=${timeframe}`)
     *     .then(r => r.json())
     *     .then(data => { renderChart(...); renderSignalTable(...); renderMetrics(...); })
     */
    setTimeout(() => {

      // 1. Generate price data
      const { labels, prices } = generatePriceData(timeframe);

      // 2. Compute signals from real indicator logic
      const signals = generateSignals(strategy, labels, prices);

      // 3. Compute metrics from signals
      const metrics = calcMetrics(signals);

      // 4. Render everything
      renderChart(symbol, strategy, labels, prices, signals);
      renderSignalTable(signals, strategyName);
      renderMetrics(metrics);
      flashCards();

      // 5. Reset button
      runBtn.disabled  = false;
      runBtn.innerHTML = '<span class="run-icon">▶</span> Run Strategy';

      // 6. Smooth scroll to chart
      document.getElementById('chart-section')
        .scrollIntoView({ behavior: 'smooth', block: 'start' });

    }, 850);
  });

});