const COLORS = {
  text: '#E8E6DE',
  muted: '#8FA0A6',
  sandstone: '#C87F4A',
  network: '#5FA8D3',
  line: '#2A3338',
  surface: '#171E22',
};

async function loadData() {
  const res = await fetch('data/publications.json');
  return res.json();
}

function renderStats(data) {
  const totalCitations = data.publications.reduce((s, p) => s + (p.cited_by_count || 0), 0);
  const numUnits = Object.keys(data.ellis_site_collaborations || {}).length;
  const numScientists = Object.keys(data.per_scientist_counts || {}).length;

  const stats = [
    { num: data.total_publications, label: 'Tracked publications' },
    { num: data.confirmed_affiliation_count || 0, label: 'With confirmed ELLIS affiliation tag' },
    { num: totalCitations, label: 'Total citations' },
    { num: numScientists, label: 'Scientists tracked' },
    { num: numUnits, label: 'ELLIS Sites collaborated with' },
  ];

  const row = document.getElementById('stat-row');
  row.innerHTML = stats.map(s => `
    <div class="stat">
      <div class="num">${s.num.toLocaleString()}</div>
      <div class="label">${s.label}</div>
    </div>
  `).join('');

  const updated = new Date(data.generated_at);
  document.getElementById('updated-note').textContent =
    `Last updated ${updated.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}`;
}

function renderTrendChart(data) {
  const years = Object.keys(data.publications_per_year).sort();
  const counts = years.map(y => data.publications_per_year[y]);

  new Chart(document.getElementById('trendChart'), {
    type: 'bar',
    data: {
      labels: years,
      datasets: [{
        label: 'Publications',
        data: counts,
        backgroundColor: COLORS.sandstone,
        borderRadius: 2,
        maxBarThickness: 46,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: COLORS.muted, font: { family: 'JetBrains Mono', size: 11 } }, grid: { color: COLORS.line } },
        y: { beginAtZero: true, ticks: { color: COLORS.muted, precision: 0 }, grid: { color: COLORS.line } },
      },
    },
  });
}

function renderNetwork(data) {
  const container = document.getElementById('networkSvgContainer');
  const units = Object.entries(data.ellis_site_collaborations || {});
  const width = 1100, height = 460;
  const cx = width / 2, cy = height / 2;
  const radius = Math.min(width, height) / 2 - 90;

  const maxCount = Math.max(1, ...units.map(u => u[1]));

  let edges = '', nodes = '';
  units.forEach(([name, count], i) => {
    const angle = (i / units.length) * 2 * Math.PI - Math.PI / 2;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);
    const strokeWidth = 1 + (count / maxCount) * 6;

    edges += `<path class="edge" d="M ${cx} ${cy} L ${x} ${y}" stroke-width="${strokeWidth.toFixed(1)}" />`;
    nodes += `
      <g class="node-unit" transform="translate(${x},${y})">
        <circle r="${14 + (count / maxCount) * 10}" />
        <text text-anchor="middle" dy="34" font-size="12">${name.replace('ELLIS Unit ', '')}</text>
        <text text-anchor="middle" dy="4" font-size="11" fill="${COLORS.network}">${count}</text>
      </g>`;
  });

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
      ${edges}
      <g class="node-institute" transform="translate(${cx},${cy})">
        <circle r="34" />
        <text text-anchor="middle" dy="5" font-size="12" font-weight="600">ELLIS</text>
      </g>
      ${nodes}
    </svg>
  `;
  container.innerHTML = svg;
}

function renderTable(data) {
  const tbody = document.getElementById('pubTableBody');
  const scientistFilter = document.getElementById('scientistFilter');
  const yearFilter = document.getElementById('yearFilter');
  const searchBox = document.getElementById('searchBox');

  const scientists = Object.keys(data.per_scientist_counts).sort();
  scientists.forEach(s => {
    const opt = document.createElement('option');
    opt.value = s; opt.textContent = s;
    scientistFilter.appendChild(opt);
  });

  const years = [...new Set(data.publications.map(p => p.year))].filter(Boolean).sort((a, b) => b - a);
  years.forEach(y => {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    yearFilter.appendChild(opt);
  });

  function draw() {
    const q = searchBox.value.toLowerCase();
    const sFilter = scientistFilter.value;
    const yFilter = yearFilter.value;

    const rows = data.publications.filter(p => {
      const scientistList = Array.isArray(p.scientist) ? p.scientist : [p.scientist];
      const matchesSearch = !q || (
        p.title.toLowerCase().includes(q) ||
        (p.venue || '').toLowerCase().includes(q) ||
        p.authors.join(' ').toLowerCase().includes(q)
      );
      const matchesScientist = !sFilter || scientistList.includes(sFilter);
      const matchesYear = !yFilter || String(p.year) === yFilter;
      return matchesSearch && matchesScientist && matchesYear;
    });

    tbody.innerHTML = rows.map(p => {
      const scientistList = Array.isArray(p.scientist) ? p.scientist.join(', ') : p.scientist;
      const badge = p.confirmed_ellis_affiliation
        ? '<span style="color:var(--network); font-size:11px; font-family:var(--font-mono); margin-left:8px;">· ELLIS-tagged</span>'
        : '';
      return `
        <tr>
          <td>
            <div class="pub-title">${p.title}${badge}</div>
            <div class="pub-meta">${p.venue || '—'} · ${p.authors.join(', ')}</div>
          </td>
          <td>${scientistList}</td>
          <td class="year-tag">${p.year || '—'}</td>
          <td class="cite-tag">${p.cited_by_count ?? 0}</td>
        </tr>
      `;
    }).join('') || `<tr><td colspan="4" style="color:var(--muted); padding:20px 12px;">No publications match those filters.</td></tr>`;
  }

  searchBox.addEventListener('input', draw);
  scientistFilter.addEventListener('change', draw);
  yearFilter.addEventListener('change', draw);
  draw();
}

loadData().then(data => {
  renderStats(data);
  renderTrendChart(data);
  renderNetwork(data);
  renderTable(data);
}).catch(err => {
  document.querySelector('.wrap').innerHTML =
    `<p style="padding:60px 0;color:#C87F4A;font-family:monospace;">Could not load data/publications.json — ${err.message}</p>`;
});
