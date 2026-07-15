const COLORS = {
  text: '#E8E6DE',
  muted: '#8FA0A6',
  sandstone: '#E38E48',
  network: '#4BC5BE',
  line: '#2A3338',
  surface: '#171E22',
};

async function loadData() {
  const res = await fetch('data/publications.json');
  return res.json();
}

function renderStats(data) {
  const totalCitations = data.publications.reduce((s, p) => s + (p.cited_by_count || 0), 0);
  const numUnits = Object.keys(data.ellis_member_collaborations || {})
    .filter(name => !name.includes('Tübingen')).length;
  const numScientists = Object.keys(data.per_scientist_counts || {}).length;

  const stats = [
    { num: data.total_publications, label: 'Tracked publications' },
    { num: totalCitations, label: 'Total citations' },
    { num: numScientists, label: 'PIs & project leaders tracked' },
    { num: numUnits, label: 'ELLIS Sites collaborated with' },
    { num: (data.open_access_percent || 0) + '%', label: 'Open access' },
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

function renderMemberCollaborations(data) {
  const container = document.getElementById('member-collab-list');
  const collabs = data.ellis_member_collaborations || {};
  const entries = Object.entries(collabs);

  if (!entries.length) {
    container.innerHTML = `<p style="color:var(--muted); font-size:13.5px;">No confirmed collaborations found yet against the current ELLIS member roster.</p>`;
    return;
  }

  const maxCount = Math.max(...entries.map(([, c]) => c));
  container.innerHTML = entries.map(([site, count]) => {
    const pct = Math.max(4, Math.round((count / maxCount) * 100));
    return `
      <div class="member-collab-row">
        <div class="site-name">${site.replace('Unit ', '').replace('Institute ', '')}</div>
        <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
        <div class="count">${count}</div>
      </div>
    `;
  }).join('');
}

function renderVenues(data) {
  const row = document.getElementById('venue-stat-row');
  const venues = data.venue_counts || {};
  const order = ['NeurIPS', 'ICML', 'ICLR'];
  const cards = order.map(name => `
    <div class="stat">
      <div class="num">${(venues[name] || 0).toLocaleString()}</div>
      <div class="label">${name}</div>
    </div>
  `).join('');

  const broaderTotal = data.top_tier_total_count || 0;
  const broaderCard = `
    <div class="stat">
      <div class="num">${broaderTotal.toLocaleString()}</div>
      <div class="label">All top-tier venues combined</div>
    </div>
  `;

  row.innerHTML = cards + broaderCard;

  const breakdown = data.broader_venue_counts || {};
  const breakdownEntries = Object.entries(breakdown);
  const breakdownEl = document.getElementById('venue-breakdown');
  if (breakdownEl) {
    breakdownEl.innerHTML = breakdownEntries.length
      ? 'Also includes: ' + breakdownEntries.map(([name, count]) => `${name} (${count})`).join(', ')
      : '';
  }
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
  const sideList = document.getElementById('networkSideList');
  const allUnits = Object.entries(data.ellis_member_collaborations || {})
    .filter(([name]) => !name.includes('Tübingen'))
    .sort((a, b) => b[1] - a[1]);

  const units = allUnits.filter(([, count]) => count > 4);
  const minorUnits = allUnits.filter(([, count]) => count <= 4);

  const width = 950, height = 620;
  const cx = width / 2, cy = height / 2;
  const radius = Math.min(width, height) / 2 - 110;
  const maxCount = Math.max(1, ...units.map(u => u[1]));

  let edges = '', nodes = '';
  units.forEach(([name, count], i) => {
    const angle = (i / units.length) * 2 * Math.PI - Math.PI / 2;
    const x = cx + radius * Math.cos(angle);
    const y = cy + radius * Math.sin(angle);

    const t = count / maxCount;
    const r = 12 + Math.pow(t, 0.7) * 28;
    const strokeWidth = 1 + Math.pow(t, 0.7) * 8;
    const labelSize = 11.5 + t * 3;

    edges += `<path class="edge" d="M ${cx} ${cy} L ${x} ${y}" stroke-width="${strokeWidth.toFixed(1)}" />`;
    nodes += `
      <g class="node-unit" transform="translate(${x},${y})" tabindex="0" role="button"
         aria-label="View shared papers with ${name}"
         onclick="openCollabModal('${name.replace(/'/g, "\\'")}')"
         onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCollabModal('${name.replace(/'/g, "\\'")}')}">
        <circle r="${r.toFixed(1)}" />
        <text text-anchor="middle" dy="${r + 15}" font-size="${labelSize.toFixed(1)}">${name.replace('ELLIS Unit ', '').replace('Unit ', '').replace('Institute ', '')}</text>
        <text text-anchor="middle" dy="4" font-size="${(labelSize - 1).toFixed(1)}" fill="${COLORS.network}">${count}</text>
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

  if (sideList) {
    const rows = minorUnits.map(([name, count]) => `
      <div class="side-row" tabindex="0" role="button" aria-label="View shared papers with ${name}"
           onclick="openCollabModal('${name.replace(/'/g, "\\'")}')"
           onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openCollabModal('${name.replace(/'/g, "\\'")}')}">
        <span class="site-name">${name.replace('ELLIS Unit ', '').replace('Unit ', '').replace('Institute ', '')}</span>
        <span class="site-count">${count}</span>
      </div>
    `).join('');
    sideList.innerHTML = `<div class="side-list-title">Also collaborated with</div>${rows}`;
  }
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
      return `
        <tr>
          <td>
            <div class="pub-title">${p.title}</div>
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

function renderBudgetChart(data) {
  const budgetByYear = data.budget_by_year || {};
  const partialYears = data.budget_partial_years || {};
  const pubsByYear = data.publications_per_year || {};
  const headcountByYear = data.pi_headcount_by_year || {};

  const years = Object.keys(budgetByYear).sort();
  const maxHeadcount = Math.max(1, ...years.map(y => headcountByYear[y] || 0));

  const points = years.map(y => {
    const headcount = headcountByYear[y] || 0;
    return {
      x: budgetByYear[y],
      y: pubsByYear[y] || 0,
      r: 8 + (headcount / maxHeadcount) * 22,
      year: y,
      headcount,
      partial: !!partialYears[y],
    };
  });

  // Year + headcount labels drawn directly next to each bubble via a small
  // custom plugin (no datalabels library vendored, so drawn manually).
  const bubbleLabelPlugin = {
    id: 'bubbleLabels',
    afterDatasetsDraw(chart) {
      const { ctx } = chart;
      const meta = chart.getDatasetMeta(0);
      meta.data.forEach((point, i) => {
        const p = points[i];
        ctx.save();
        ctx.font = '11px JetBrains Mono, monospace';
        ctx.fillStyle = COLORS.muted;
        ctx.textAlign = 'left';
        ctx.fillText(`${p.year}${p.partial ? '*' : ''} · ${p.headcount} PIs`, point.x + p.r + 6, point.y + 4);
        ctx.restore();
      });
    },
  };

  new Chart(document.getElementById('budgetChart'), {
    type: 'bubble',
    data: {
      datasets: [{
        label: 'Year',
        data: points,
        backgroundColor: points.map(p => p.partial ? COLORS.muted + '99' : COLORS.sandstone + '99'),
        borderColor: points.map(p => p.partial ? COLORS.muted : COLORS.sandstone),
        borderWidth: 1.5,
      }],
    },
    plugins: [bubbleLabelPlugin],
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => {
              const p = points[ctx.dataIndex];
              return `${p.year}${p.partial ? ' (partial year)' : ''}: €${p.x.toLocaleString()} · ${p.y} papers · ${p.headcount} PIs`;
            },
          },
        },
      },
      scales: {
        x: {
          title: { display: true, text: 'Budget used (€)', color: COLORS.muted, font: { family: 'JetBrains Mono', size: 11 } },
          ticks: { color: COLORS.muted, callback: v => '€' + (v / 1e6).toFixed(1) + 'M' },
          grid: { color: COLORS.line },
        },
        y: {
          title: { display: true, text: 'Publications', color: COLORS.muted, font: { family: 'JetBrains Mono', size: 11 } },
          beginAtZero: true,
          ticks: { color: COLORS.muted, precision: 0 },
          grid: { color: COLORS.line },
        },
      },
    },
  });
}

function renderGrowthChart(data) {
  const joinDates = (data.scientist_join_dates || []).slice().sort();
  if (!joinDates.length) return;

  const formatLabel = iso => {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
  };

  const labels = joinDates.map(formatLabel);
  const cumulative = joinDates.map((_, i) => i + 1);

  // Extend the line to "today" so it doesn't just stop at the last join date.
  const today = new Date().toISOString().slice(0, 10);
  if (today > joinDates[joinDates.length - 1]) {
    labels.push(formatLabel(today));
    cumulative.push(cumulative[cumulative.length - 1]);
  }

  new Chart(document.getElementById('growthChart'), {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'PIs & project leaders',
        data: cumulative,
        borderColor: COLORS.sandstone,
        backgroundColor: COLORS.sandstone,
        stepped: 'before',
        pointRadius: 3,
        pointBackgroundColor: COLORS.sandstone,
        fill: false,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { color: COLORS.muted, font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 45, minRotation: 45 },
          grid: { color: COLORS.line },
        },
        y: {
          beginAtZero: true,
          ticks: { color: COLORS.muted, precision: 0 },
          grid: { color: COLORS.line },
        },
      },
    },
  });
}

function renderHIndex(data) {
  const container = document.getElementById('hindexPlot');
  const values = data.h_index_distribution || [];
  if (!values.length) {
    container.innerHTML = `<p style="color:var(--muted); font-size:13.5px;">No h-index data available.</p>`;
    return;
  }

  const width = 900, height = 200;
  const marginLeft = 40, marginRight = 40, plotY = 100;
  const maxVal = Math.max(...values, 10);
  const scaleX = v => marginLeft + (v / maxVal) * (width - marginLeft - marginRight);

  // Simple deterministic jitter so identical values don't stack exactly on
  // top of each other (still anonymous — jitter carries no information).
  const jittered = values.map((v, i) => {
    const sameValueBefore = values.slice(0, i).filter(x => x === v).length;
    const jitter = (sameValueBefore % 2 === 0 ? 1 : -1) * Math.ceil(sameValueBefore / 2) * 14;
    return { v, y: plotY + jitter };
  });

  const median = values[Math.floor(values.length / 2)];
  const min = values[0], max = values[values.length - 1];

  let dots = jittered.map(({ v, y }) =>
    `<circle class="hindex-dot" cx="${scaleX(v).toFixed(1)}" cy="${y}" r="9" />`
  ).join('');

  let axisTicks = '';
  const tickStep = Math.max(1, Math.ceil(maxVal / 8));
  for (let t = 0; t <= maxVal; t += tickStep) {
    const x = scaleX(t);
    axisTicks += `
      <line class="hindex-axis-line" x1="${x}" y1="${plotY + 45}" x2="${x}" y2="${plotY + 50}" />
      <text class="hindex-axis-label" text-anchor="middle" x="${x}" y="${plotY + 65}">${t}</text>
    `;
  }

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg" class="hindex-svg-wrap">
      <line class="hindex-axis-line" x1="${marginLeft}" y1="${plotY + 45}" x2="${width - marginRight}" y2="${plotY + 45}" />
      ${axisTicks}
      ${dots}
      <text class="hindex-stat-label" x="${marginLeft}" y="20">min ${min}</text>
      <text class="hindex-stat-label" text-anchor="middle" x="${width / 2}" y="20">median ${median}</text>
      <text class="hindex-stat-label" text-anchor="end" x="${width - marginRight}" y="20">max ${max}</text>
    </svg>
  `;
  container.innerHTML = svg;
}

function switchTab(name) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.tab === name);
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    panel.classList.toggle('active', panel.id === `tab-${name}`);
  });
}

async function loadActivities() {
  try {
    const res = await fetch('data/activities.json');
    if (!res.ok) return;
    const data = await res.json();
    initActivities(data.entries || []);
  } catch (err) {
    console.warn('Could not load activities.json:', err.message);
  }
}

const ACTIVITY_TYPE_LABELS = {
  talk: 'Talk', press: 'Press', award: 'Award',
  panel: 'Panel', podcast: 'Podcast', organizing: 'Organizing',
};

function initActivities(entries) {
  const typeFilter = document.getElementById('activityTypeFilter');
  const scientistFilter = document.getElementById('activityScientistFilter');
  const listEl = document.getElementById('activityList');
  if (!listEl) return;

  const people = [...new Set(entries.map(e => e.scientist).filter(Boolean))].sort();
  scientistFilter.innerHTML = '<option value="">All people</option>' +
    people.map(p => `<option value="${p}">${p}</option>`).join('');

  function draw() {
    const type = typeFilter.value;
    const person = scientistFilter.value;
    const filtered = entries.filter(e =>
      (!type || e.type === type) && (!person || e.scientist === person)
    );

    if (!filtered.length) {
      listEl.innerHTML = `<p style="color:var(--muted); font-size:13.5px; padding:20px 0;">No activities match this filter yet.</p>`;
      return;
    }

    listEl.innerHTML = filtered.map(e => {
      const titleHtml = e.url
        ? `<a href="${e.url}" target="_blank" rel="noopener">${e.title}</a>`
        : e.title;
      const dateLabel = e.date
        ? new Date(e.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
        : '';
      return `
        <div class="activity-row">
          <div class="activity-type-badge ${e.type}">${ACTIVITY_TYPE_LABELS[e.type] || e.type}</div>
          <div class="activity-content">
            <div class="activity-title">${titleHtml}</div>
            <div class="activity-meta">${[dateLabel, e.scientist, e.venue].filter(Boolean).join(' · ')}</div>
            ${e.description ? `<div class="activity-description">${e.description}</div>` : ''}
          </div>
        </div>
      `;
    }).join('');
  }

  typeFilter.addEventListener('change', draw);
  scientistFilter.addEventListener('change', draw);
  draw();
}

let CURRENT_DATA = null;

loadData().then(data => {
  CURRENT_DATA = data;
  renderStats(data);
  renderVenues(data);
  renderTrendChart(data);
  renderBudgetChart(data);
  renderGrowthChart(data);
  renderHIndex(data);
  renderNetwork(data);
  renderTable(data);
}).catch(err => {
  document.querySelector('.wrap').innerHTML =
    `<p style="padding:60px 0;color:#E38E48;font-family:monospace;">Could not load data/publications.json — ${err.message}</p>`;
});

loadActivities();

function openCollabModal(unitName) {
  const details = (CURRENT_DATA && CURRENT_DATA.ellis_member_collaboration_details) || {};
  const papers = details[unitName] || [];
  const displayName = unitName.replace('ELLIS Unit ', '').replace('Unit ', '').replace('Institute ', '');

  document.getElementById('collabModalTitle').textContent = `${displayName} — ${papers.length} shared paper${papers.length === 1 ? '' : 's'}`;

  const body = document.getElementById('collabModalBody');
  body.innerHTML = papers.length
    ? papers.map(p => `
        <div class="modal-pub-row">
          <div class="pub-title">${p.title}</div>
          <div class="pub-meta">
            <span class="highlight">${p.year || '—'}</span> ·
            our scientist: ${p.scientist} ·
            ELLIS co-author: <span class="highlight">${p.co_author}</span>
          </div>
        </div>
      `).join('')
    : `<p style="color:var(--muted); font-size:13.5px;">No paper details available.</p>`;

  document.getElementById('collabModalOverlay').classList.add('open');
}

function closeCollabModal() {
  document.getElementById('collabModalOverlay').classList.remove('open');
}
