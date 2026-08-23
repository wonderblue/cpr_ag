let allStocks = [];
let currentTimeframe = 'daily';
let activeChart = null;

async function loadScreenerData() {
  try {
    const res = await fetch('data/screener_output.json');
    const data = await res.json();
    
    document.getElementById('last-updated').textContent = data.updated_at || 'Just Now';
    allStocks = data.stocks || [];

    updateKPIs();
    applyFilters();
  } catch (e) {
    console.error('Error loading data:', e);
  }
}

function updateKPIs() {
  document.getElementById('kpi-total').textContent = allStocks.length;
  document.getElementById('kpi-5star').textContent = allStocks.filter(s => s.rating === 5).length;
  document.getElementById('kpi-narrow').textContent = allStocks.filter(s => s.compression.includes('Narrow')).length;
  document.getElementById('kpi-bull').textContent = allStocks.filter(s => s.confluence.includes('Bullish')).length;
}

function setTimeframe(tf) {
  currentTimeframe = tf;
  document.querySelectorAll('.tf-btn').forEach(b => {
    b.className = 'tf-btn px-4 py-1.5 rounded-md text-slate-400 hover:text-white';
  });
  document.getElementById(`btn-${tf}`).className = 'tf-btn px-4 py-1.5 rounded-md bg-emerald-600 text-white font-medium';
  applyFilters();
}

function applyFilters() {
  const ratingFilter = document.getElementById('filter-rating').value;
  const compFilter = document.getElementById('filter-compression').value;
  const biasFilter = document.getElementById('filter-bias').value;
  const query = document.getElementById('search-box').value.toLowerCase();

  const filtered = allStocks.filter(s => {
    if (ratingFilter === '5' && s.rating !== 5) return false;
    if (ratingFilter === '4' && s.rating < 4) return false;
    if (compFilter === 'narrow' && !s.compression.includes('Narrow')) return false;
    if (compFilter === 'extreme' && !s.compression.includes('Extreme')) return false;
    if (biasFilter === 'bullish' && !s.bias.includes('Bullish')) return false;
    if (biasFilter === 'bearish' && !s.bias.includes('Bearish')) return false;
    if (query && !s.symbol.toLowerCase().includes(query) && !s.industry.toLowerCase().includes(query)) return false;
    return true;
  });

  renderTable(filtered);
}

function renderTable(stocks) {
  const tbody = document.getElementById('screener-table-body');
  tbody.innerHTML = '';

  if (stocks.length === 0) {
    tbody.innerHTML = `<tr><td colspan="12" class="text-center py-8 text-slate-500">No stocks match the selected filter criteria.</td></tr>`;
    return;
  }

  stocks.forEach(s => {
    const tfData = s[currentTimeframe] || s.daily;
    const isNarrow = tfData.width_pct <= 0.40;
    
    const row = document.createElement('tr');
    row.className = 'hover:bg-slate-800/40 transition cursor-pointer border-b border-slate-800/50';
    
    row.innerHTML = `
      <td class="px-4 py-3 font-semibold text-white">
        ${s.symbol}
        <div class="text-[10px] text-slate-500 font-normal">${s.industry}</div>
      </td>
      <td class="px-4 py-3 font-bold text-slate-200">₹${s.price}</td>
      <td class="px-4 py-3 text-amber-400 font-medium">${s.stars}</td>
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

function openChartModal(symbol) {
  const stock = allStocks.find(s => s.symbol === symbol);
  if (!stock || !stock.candles) return;

  document.getElementById('modal-title').textContent = `${stock.symbol} (${stock.name}) - ₹${stock.price}`;
  document.getElementById('modal-subtitle').textContent = `Sector: ${stock.industry} | Rating: ${stock.stars} | 14D Compression: ${stock.comp_ratio}`;
  
  const modal = document.getElementById('chart-modal');
  modal.classList.remove('hidden');

  const container = document.getElementById('chart-container');
  container.innerHTML = '';

  activeChart = LightweightCharts.createChart(container, {
    width: container.clientWidth,
    height: 380,
    layout: { background: { color: '#090d16' }, textColor: '#94a3b8' },
    grid: { vertLines: { color: '#1e293b' }, horzLines: { color: '#1e293b' } },
    timeScale: { borderColor: '#334155' }
  });

  const candleSeries = activeChart.addCandlestickSeries({
    upColor: '#10b981', downColor: '#ef4444', borderVisible: false,
    wickUpColor: '#10b981', wickDownColor: '#ef4444'
  });

  candleSeries.setData(stock.candles);

  // Overlay Daily CPR Lines
  const tf = stock[currentTimeframe] || stock.daily;
  const pLine = activeChart.addLineSeries({ color: '#38bdf8', lineWidth: 2, title: 'Pivot' });
  const tcLine = activeChart.addLineSeries({ color: '#a855f7', lineWidth: 1, title: 'TC' });
  const bcLine = activeChart.addLineSeries({ color: '#ec4899', lineWidth: 1, title: 'BC' });

  pLine.setData(stock.candles.map(c => ({ time: c.time, value: tf.pivot })));
  tcLine.setData(stock.candles.map(c => ({ time: c.time, value: tf.tc })));
  bcLine.setData(stock.candles.map(c => ({ time: c.time, value: tf.bc })));

  document.getElementById('modal-levels').innerHTML = `
    <span class="text-purple-400 font-semibold">TC: ₹${tf.tc}</span>
    <span class="text-cyan-400 font-semibold">Pivot: ₹${tf.pivot}</span>
    <span class="text-pink-400 font-semibold">BC: ₹${tf.bc}</span>
    <span class="text-slate-400">|</span>
    <span class="text-emerald-400">R1: ₹${tf.r1}</span>
    <span class="text-rose-400">S1: ₹${tf.s1}</span>
    <span class="text-emerald-300">R2: ₹${tf.r2}</span>
    <span class="text-rose-300">S2: ₹${tf.s2}</span>
  `;
}

function closeChartModal() {
  document.getElementById('chart-modal').classList.add('hidden');
  if (activeChart) {
    activeChart.remove();
    activeChart = null;
  }
}

// Initial Load
loadScreenerData();
