let allStocks = [];
let filteredStocks = [];
let currentTimeframe = 'daily';
let currentViewMode = 'table';
let currentStrategyPill = 'diamond'; // Default to Top Sniper List!
let activeChart = null;
let currentModalSymbol = '';
let currentChartTab = 'cpr';

function initDeviceView() {
  const isMobile = window.innerWidth < 768;
  setViewMode(isMobile ? 'cards' : 'table');
}

async function loadScreenerData() {
  try {
    const res = await fetch('data/screener_output.json');
    const data = await res.json();
    
    document.getElementById('last-updated').textContent = data.updated_at || 'Just Now';
    allStocks = data.stocks || [];

    populateIndustryDropdown();
    updateKPIs();
    initDeviceView();
    setStrategyPill('diamond'); // Start in Diamond Sniper mode
  } catch (e) {
    console.error('Error loading data:', e);
  }
}

function setViewMode(mode) {
  currentViewMode = mode;
  const tableWrap = document.getElementById('desktop-table-container');
  const cardsWrap = document.getElementById('mobile-cards-container');
  const btnCards = document.getElementById('btn-view-cards');
  const btnTable = document.getElementById('btn-view-table');

  if (mode === 'cards') {
    tableWrap.classList.add('hidden');
    cardsWrap.classList.remove('hidden');
    btnCards.className = 'view-btn px-2.5 py-1.5 rounded-md bg-emerald-600 text-white font-medium';
    btnTable.className = 'view-btn px-2.5 py-1.5 rounded-md text-slate-400 hover:text-white';
  } else {
    cardsWrap.classList.add('hidden');
    tableWrap.classList.remove('hidden');
    btnTable.className = 'view-btn px-2.5 py-1.5 rounded-md bg-emerald-600 text-white font-medium';
    btnCards.className = 'view-btn px-2.5 py-1.5 rounded-md text-slate-400 hover:text-white';
  }
  renderCurrentView();
}

function populateIndustryDropdown() {
  const select = document.getElementById('filter-industry');
  const industryCounts = {};

  allStocks.forEach(s => {
    const ind = s.industry || 'General';
    industryCounts[ind] = (industryCounts[ind] || 0) + 1;
  });

  const sorted = Object.keys(industryCounts).sort();
  select.innerHTML = `<option value="all">🏢 All Sectors (${allStocks.length})</option>`;
  sorted.forEach(ind => {
    const opt = document.createElement('option');
    opt.value = ind;
    opt.textContent = `${ind} (${industryCounts[ind]})`;
    select.appendChild(opt);
  });
}

function updateKPIs() {
  document.getElementById('kpi-total').textContent = allStocks.length;
  document.getElementById('kpi-diamond').textContent = allStocks.filter(s => s.is_diamond).length;
  document.getElementById('kpi-narrow').textContent = allStocks.filter(s => s.compression && s.compression.includes('Extreme')).length;
  document.getElementById('kpi-bull').textContent = allStocks.filter(s => s.confluence && s.confluence.includes('Triple Bullish')).length;
}

function setTimeframe(tf) {
  currentTimeframe = tf;
  document.querySelectorAll('.tf-btn').forEach(b => {
    b.className = 'tf-btn px-3 sm:px-4 py-1.5 rounded-md text-slate-400 hover:text-white';
  });
  document.getElementById(`btn-${tf}`).className = 'tf-btn px-3 sm:px-4 py-1.5 rounded-md bg-emerald-600 text-white font-medium';
  applyFilters();
}

function setStrategyPill(strategy) {
  currentStrategyPill = strategy;

  document.querySelectorAll('.preset-pill').forEach(btn => {
    btn.className = 'preset-pill px-3 py-1.5 rounded-full bg-slate-900 border border-slate-800 text-slate-300 hover:border-slate-600 text-xs transition';
  });

  const activePill = document.getElementById(`pill-${strategy}`);
  if (activePill) {
    activePill.className = 'preset-pill px-3 py-1.5 rounded-full bg-emerald-600 border border-emerald-400 text-white font-bold text-xs transition shadow-lg shadow-emerald-500/20';
  }

  document.getElementById('filter-score').value = 'all';
  document.getElementById('filter-industry').value = 'all';
  document.getElementById('search-box').value = '';

  applyFilters();
}

function filterByIndustry(ind) {
  document.getElementById('filter-industry').value = ind;
  applyFilters();
}

function applyFilters() {
  const industryFilter = document.getElementById('filter-industry').value;
  const scoreFilter = document.getElementById('filter-score').value;
  const query = document.getElementById('search-box').value.toLowerCase();

  filteredStocks = allStocks.filter(s => {
    // 1. Preset Matching
    if (currentStrategyPill === 'diamond' && !s.is_diamond) {
      return false;
    }
    if (currentStrategyPill === 'extreme' && !s.compression.includes('Extreme')) {
      return false;
    }
    if (currentStrategyPill === 'triple_bull' && !s.confluence.includes('Triple Bullish')) {
      return false;
    }
    if (currentStrategyPill === 'rs_leaders' && (s.rs_score || 0) < 8.0) {
      return false;
    }
    if (currentStrategyPill === 'weekly_swing') {
      const wNarrow = s.weekly && s.weekly.width_pct <= 0.85;
      const wBull = s.price >= s.weekly.pivot;
      if (!wNarrow || !wBull) return false;
    }

    // 2. Dropdown Filters
    if (industryFilter !== 'all' && (s.industry || 'General') !== industryFilter) return false;
    if (scoreFilter !== 'all' && s.quant_score < parseInt(scoreFilter)) return false;
    if (query && !s.symbol.toLowerCase().includes(query) && !s.industry.toLowerCase().includes(query) && !s.name.toLowerCase().includes(query)) return false;

    return true;
  });

  renderCurrentView();
}

function renderCurrentView() {
  if (currentViewMode === 'cards') {
    renderMobileCards(filteredStocks);
  } else {
    renderDesktopTable(filteredStocks);
  }
}

// -------------------------------------------------------------
// MOBILE CARDS RENDERER (TOUCH-OPTIMIZED)
// -------------------------------------------------------------
function renderMobileCards(stocks) {
  const container = document.getElementById('mobile-cards-container');
  container.innerHTML = '';

  if (stocks.length === 0) {
    container.innerHTML = `<div class="col-span-full text-center py-12 text-slate-500 text-xs">No setups match this strict quant filter today.</div>`;
    return;
  }

  stocks.forEach(s => {
    const tfData = s[currentTimeframe] || s.daily;
    const isDiamond = s.is_diamond;
    
    const card = document.createElement('div');
    card.className = `bg-slate-900/90 border ${isDiamond ? 'border-emerald-500/50 shadow-lg shadow-emerald-500/10' : 'border-slate-800'} rounded-xl p-3.5 hover:border-slate-700 transition cursor-pointer active:scale-[0.99]`;
    card.onclick = () => openChartModal(s.symbol);

    card.innerHTML = `
      <div class="flex items-start justify-between gap-2 mb-2">
        <div>
          <div class="flex items-center gap-1.5">
            <span class="font-bold text-white text-sm">${s.symbol}</span>
            ${isDiamond ? '<span class="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] px-1.5 py-0.2 rounded font-black">💎 SNIPER</span>' : ''}
          </div>
          <div class="text-[11px] text-slate-400 truncate max-w-[180px]">${s.name}</div>
        </div>
        <div class="text-right">
          <div class="font-bold text-slate-100 text-sm">₹${s.price}</div>
          <div class="text-[10px] font-bold ${s.quant_score >= 80 ? 'text-emerald-400' : 'text-amber-400'}">Score: ${s.quant_score}/100</div>
        </div>
      </div>

      <div class="bg-slate-950/80 rounded-lg p-2 flex items-center justify-between text-[11px] border border-slate-800/80 mb-2">
        <div>
          <span class="text-slate-500 text-[10px]">Width:</span>
          <span class="font-bold text-cyan-400">${tfData.width_pct}%</span>
        </div>
        <div class="text-center">
          <span class="text-slate-500 text-[10px]">Pivot:</span>
          <span class="font-semibold text-white">₹${tfData.pivot}</span>
        </div>
        <div class="text-right">
          <span class="text-slate-500 text-[10px]">RS vs Nifty:</span>
          <span class="font-semibold ${s.rs_score >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${s.rs_score >= 0 ? '+' : ''}${s.rs_score}%</span>
        </div>
      </div>

      <div class="flex items-center justify-between text-[10px]">
        <span class="px-2 py-0.5 rounded ${s.compression.includes('Extreme') ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium' : 'bg-slate-800 text-slate-400'}">
          ${s.compression}
        </span>
        <span class="${s.confluence.includes('Bull') ? 'text-emerald-400 font-medium' : 'text-slate-400'}">
          ${s.confluence}
        </span>
      </div>
    `;
    container.appendChild(card);
  });
}

// -------------------------------------------------------------
// DESKTOP TABLE RENDERER
// -------------------------------------------------------------
function renderDesktopTable(stocks) {
  const tbody = document.getElementById('screener-table-body');
  tbody.innerHTML = '';

  if (stocks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="13" class="text-center py-8 text-slate-500">No stocks match this strict quant filter today.</td></tr>`;
    return;
  }

  stocks.forEach(s => {
    const tfData = s[currentTimeframe] || s.daily;
    const isNarrow = tfData.width_pct <= 0.40;
    const isDiamond = s.is_diamond;
    
    const row = document.createElement('tr');
    row.className = `hover:bg-slate-800/40 transition cursor-pointer border-b border-slate-800/50 ${isDiamond ? 'bg-emerald-950/20' : ''}`;
    
    row.innerHTML = `
      <td class="px-4 py-3 font-semibold text-white sticky left-0 bg-slate-950 z-10">
        <div class="flex items-center gap-1.5">
          <span>${s.symbol}</span>
          ${isDiamond ? '<span class="text-[9px] bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 px-1 rounded font-bold">💎</span>' : ''}
        </div>
      </td>
      <td class="px-4 py-3 text-slate-300 sticky left-[90px] bg-slate-950 z-10 border-r border-slate-800 max-w-[150px]">
        <div class="truncate font-medium text-slate-200" title="${s.name}">${s.name}</div>
        <button onclick="filterByIndustry('${s.industry}')" class="text-[10px] text-indigo-400 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 px-1.5 py-0.5 rounded transition mt-0.5">
          ${s.industry}
        </button>
      </td>
      <td class="px-4 py-3 font-bold text-slate-200">₹${s.price}</td>
      <td class="px-4 py-3">
        <div class="flex items-center gap-1.5">
          <span class="font-black ${s.quant_score >= 80 ? 'text-emerald-400' : 'text-amber-400'}">${s.quant_score}</span>
          <span class="text-[10px] text-slate-500">/100</span>
        </div>
      </td>
      <td class="px-4 py-3 font-medium ${isNarrow ? 'text-emerald-400' : 'text-slate-400'}">${tfData.width_pct}%</td>
      <td class="px-4 py-3">
        <span class="px-2 py-0.5 rounded text-[11px] font-medium ${s.compression.includes('Extreme') ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30' : (s.compression.includes('Narrow') ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30' : 'bg-slate-800 text-slate-400')}">
          ${s.compression}
        </span>
      </td>
      <td class="px-4 py-3 text-slate-300">${s.rvol}x</td>
      <td class="px-4 py-3 font-medium ${s.rs_score >= 0 ? 'text-emerald-400' : 'text-rose-400'}">${s.rs_score >= 0 ? '+' : ''}${s.rs_score}%</td>
      <td class="px-4 py-3 text-slate-400">₹${tfData.tc}</td>
      <td class="px-4 py-3 font-semibold text-white">₹${tfData.pivot}</td>
      <td class="px-4 py-3 text-slate-400">₹${tfData.bc}</td>
      <td class="px-4 py-3">
        <span class="text-[11px] ${s.confluence.includes('Bull') ? 'text-emerald-400' : (s.confluence.includes('Bear') ? 'text-rose-400' : 'text-slate-400')}">
          ${s.confluence}
        </span>
      </td>
      <td class="px-4 py-3 text-center">
        <button onclick="openChartModal('${s.symbol}')" class="bg-slate-800 hover:bg-emerald-600 text-slate-200 hover:text-white px-2.5 py-1 rounded text-xs transition border border-slate-700">
          📈 View
        </button>
      </td>
    `;
    tbody.appendChild(row);
  });
}

// -------------------------------------------------------------
// DUAL CHART ENGINE
// -------------------------------------------------------------
function openChartModal(symbol) {
  const stock = allStocks.find(s => s.symbol === symbol);
  if (!stock) return;

  currentModalSymbol = symbol;
  document.getElementById('modal-title').textContent = `${stock.symbol} (${stock.name}) - ₹${stock.price}`;
  document.getElementById('modal-subtitle').textContent = `Quant Score: ${stock.quant_score}/100 | ${stock.industry} | 14D: ${stock.comp_ratio} | RS: ${stock.rs_score}%`;

  const modal = document.getElementById('chart-modal');
  modal.classList.remove('hidden');

  switchChartTab('cpr');
}

function switchChartTab(tab) {
  currentChartTab = tab;
  const cprView = document.getElementById('cpr-chart-view');
  const tvView = document.getElementById('tv-chart-view');
  const btnCpr = document.getElementById('btn-tab-cpr');
  const btnTv = document.getElementById('btn-tab-tv');

  if (tab === 'cpr') {
    cprView.classList.remove('hidden');
    tvView.classList.add('hidden');
    btnCpr.className = 'px-2.5 sm:px-3 py-1 rounded bg-emerald-600 text-white font-medium';
    btnTv.className = 'px-2.5 sm:px-3 py-1 rounded text-slate-400 hover:text-white';
    setTimeout(renderLightweightCPRChart, 50);
  } else {
    cprView.classList.add('hidden');
    tvView.classList.remove('hidden');
    btnTv.className = 'px-2.5 sm:px-3 py-1 rounded bg-emerald-600 text-white font-medium';
    btnCpr.className = 'px-2.5 sm:px-3 py-1 rounded text-slate-400 hover:text-white';
    renderTradingViewIFrame();
  }
}

function renderLightweightCPRChart() {
  const stock = allStocks.find(s => s.symbol === currentModalSymbol);
  if (!stock || !stock.candles || stock.candles.length === 0) return;

  const container = document.getElementById('chart-container');
  container.innerHTML = '';

  const chartWidth = container.clientWidth || (window.innerWidth < 768 ? window.innerWidth - 32 : 860);
  const chartHeight = window.innerWidth < 768 ? 320 : 380;

  if (activeChart) {
    try { activeChart.remove(); } catch(e) {}
    activeChart = null;
  }

  try {
    activeChart = LightweightCharts.createChart(container, {
      width: chartWidth,
      height: chartHeight,
      layout: {
        backgroundColor: '#090d16',
        textColor: '#94a3b8'
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.3)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.3)' }
      },
      timeScale: {
        borderColor: '#334155',
        timeVisible: true
      },
      rightPriceScale: {
        borderColor: '#334155'
      }
    });

    const candleSeries = activeChart.addCandlestickSeries({
      upColor: '#10b981',
      downColor: '#ef4444',
      borderVisible: false,
      wickUpColor: '#10b981',
      wickDownColor: '#ef4444'
    });

    const sortedCandles = [...stock.candles].sort((a, b) => new Date(a.time) - new Date(b.time));
    candleSeries.setData(sortedCandles);

    const tf = stock[currentTimeframe] || stock.daily;

    const pLine = activeChart.addLineSeries({ color: '#38bdf8', lineWidth: 2, title: 'P' });
    pLine.setData(sortedCandles.map(c => ({ time: c.time, value: tf.pivot })));

    const tcLine = activeChart.addLineSeries({ color: '#a855f7', lineWidth: 1, title: 'TC' });
    tcLine.setData(sortedCandles.map(c => ({ time: c.time, value: tf.tc })));

    const bcLine = activeChart.addLineSeries({ color: '#ec4899', lineWidth: 1, title: 'BC' });
    bcLine.setData(sortedCandles.map(c => ({ time: c.time, value: tf.bc })));

    activeChart.timeScale().fitContent();

    document.getElementById('modal-levels').innerHTML = `
      <span class="text-purple-400 font-semibold">TC: ₹${tf.tc}</span>
      <span class="text-cyan-400 font-semibold">P: ₹${tf.pivot}</span>
      <span class="text-pink-400 font-semibold">BC: ₹${tf.bc}</span>
      <span class="text-slate-500">|</span>
      <span class="text-emerald-400 font-medium">R1: ₹${tf.r1}</span>
      <span class="text-rose-400 font-medium">S1: ₹${tf.s1}</span>
      <span class="text-slate-500">|</span>
      <span class="text-amber-400 font-medium">Reasons: ${stock.reasons}</span>
    `;
  } catch (err) {
    console.error("Chart render error:", err);
  }
}

function renderTradingViewIFrame() {
  const container = document.getElementById('tv-widget-container');
  const sym = currentModalSymbol;

  container.innerHTML = `
    <iframe 
      src="https://s.tradingview.com/widgetembed/?symbol=NSE%3A${sym}&interval=D&hidesidetoolbar=0&symboledit=1&saveimage=1&toolbarbg=090d16&theme=dark&style=1&timezone=Asia%2FKolkata&withdateranges=1&locale=en" 
      style="width: 100%; height: 100%; min-height: 380px; border: none; border-radius: 10px;"
      allowtransparency="true" 
      frameborder="0">
    </iframe>
  `;
}

function closeChartModal() {
  document.getElementById('chart-modal').classList.add('hidden');
  if (activeChart) {
    try { activeChart.remove(); } catch(e) {}
    activeChart = null;
  }
  document.getElementById('chart-container').innerHTML = '';
  document.getElementById('tv-widget-container').innerHTML = '';
}

function handleBackdropClick(event) {
  if (event.target.id === 'chart-modal') {
    closeChartModal();
  }
}

document.addEventListener('keydown', function(event) {
  if (event.key === 'Escape' || event.keyCode === 27) {
    closeChartModal();
  }
});

window.addEventListener('resize', () => {
  if (activeChart) {
    const container = document.getElementById('chart-container');
    activeChart.applyOptions({ width: container.clientWidth });
  }
});

function exportToTradingView() {
  const listToExport = filteredStocks.length > 0 ? filteredStocks : allStocks;
  const tvString = listToExport.map(s => `NSE:${s.symbol}`).join(',');

  navigator.clipboard.writeText(tvString).then(() => {
    alert(`✅ Copied ${listToExport.length} symbols to clipboard!\n\nOpen TradingView -> Paste -> Done!`);
  }).catch(err => {
    prompt("Copy TradingView Watchlist:", tvString);
  });
}

// Initialize on page load
loadScreenerData();
