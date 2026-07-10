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
  const numUnits = Object.keys(data.ellis_member_collaborations || {})
    .filter(name => !name.includes('Tübingen')).length;
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

// Approximate coordinates (lat, lon) for each ELLIS Site's host city.
const SITE_COORDS = {
  "Associate Unit Lviv": { lat: 49.84, lon: 24.03, city: "Lviv" },
  "Institute Finland": { lat: 60.17, lon: 24.94, city: "Finland" },
  "Institute Tübingen": { lat: 48.52, lon: 9.06, city: "Tübingen" },
  "Unit Amsterdam": { lat: 52.37, lon: 4.90, city: "Amsterdam" },
  "Unit Barcelona": { lat: 41.39, lon: 2.17, city: "Barcelona" },
  "Unit Berlin": { lat: 52.52, lon: 13.40, city: "Berlin" },
  "Unit Cambridge": { lat: 52.21, lon: 0.12, city: "Cambridge" },
  "Unit Copenhagen": { lat: 55.68, lon: 12.57, city: "Copenhagen" },
  "Unit Czechia": { lat: 49.20, lon: 16.61, city: "Czechia" },
  "Unit Darmstadt": { lat: 49.87, lon: 8.65, city: "Darmstadt" },
  "Unit Delft": { lat: 52.01, lon: 4.36, city: "Delft" },
  "Unit Denmark": { lat: 56.16, lon: 10.20, city: "Denmark" },
  "Unit Edinburgh": { lat: 55.95, lon: -3.19, city: "Edinburgh" },
  "Unit Franconia": { lat: 49.59, lon: 11.01, city: "Franconia" },
  "Unit Freiburg": { lat: 48.00, lon: 7.84, city: "Freiburg" },
  "Unit Genoa": { lat: 44.41, lon: 8.95, city: "Genoa" },
  "Unit Graz": { lat: 47.07, lon: 15.44, city: "Graz" },
  "Unit Grenoble": { lat: 45.19, lon: 5.72, city: "Grenoble" },
  "Unit Haifa": { lat: 32.79, lon: 34.99, city: "Haifa" },
  "Unit Heidelberg": { lat: 49.40, lon: 8.67, city: "Heidelberg" },
  "Unit Helsinki": { lat: 60.17, lon: 24.94, city: "Helsinki" },
  "Unit Jena": { lat: 50.93, lon: 11.59, city: "Jena" },
  "Unit Lausanne": { lat: 46.52, lon: 6.63, city: "Lausanne" },
  "Unit Leuven": { lat: 50.88, lon: 4.70, city: "Leuven" },
  "Unit Linz": { lat: 48.31, lon: 14.29, city: "Linz" },
  "Unit Lisbon": { lat: 38.72, lon: -9.14, city: "Lisbon" },
  "Unit London": { lat: 51.51, lon: -0.13, city: "London" },
  "Unit Madrid": { lat: 40.42, lon: -3.70, city: "Madrid" },
  "Unit Manchester": { lat: 53.48, lon: -2.24, city: "Manchester" },
  "Unit Milan": { lat: 45.46, lon: 9.19, city: "Milan" },
  "Unit Modena": { lat: 44.65, lon: 10.93, city: "Modena" },
  "Unit Munich": { lat: 48.14, lon: 11.58, city: "Munich" },
  "Unit NRW": { lat: 50.74, lon: 7.10, city: "NRW" },
  "Unit Nijmegen": { lat: 51.81, lon: 5.84, city: "Nijmegen" },
  "Unit Oxford": { lat: 51.75, lon: -1.26, city: "Oxford" },
  "Unit Paris": { lat: 48.86, lon: 2.35, city: "Paris" },
  "Unit Potsdam": { lat: 52.39, lon: 13.06, city: "Potsdam" },
  "Unit Prague": { lat: 50.08, lon: 14.44, city: "Prague" },
  "Unit Saarbrücken": { lat: 49.24, lon: 7.00, city: "Saarbrücken" },
  "Unit Slovenia": { lat: 46.06, lon: 14.51, city: "Slovenia" },
  "Unit Sofia": { lat: 42.70, lon: 23.32, city: "Sofia" },
  "Unit Stuttgart": { lat: 48.78, lon: 9.18, city: "Stuttgart" },
  "Unit Sweden": { lat: 59.33, lon: 18.07, city: "Sweden" },
  "Unit Tel Aviv": { lat: 32.09, lon: 34.78, city: "Tel Aviv" },
  "Unit Trento": { lat: 46.07, lon: 11.12, city: "Trento" },
  "Unit Turin": { lat: 45.07, lon: 7.69, city: "Turin" },
  "Unit Tübingen": { lat: 48.52, lon: 9.06, city: "Tübingen" },
  "Unit Vienna": { lat: 48.21, lon: 16.37, city: "Vienna" },
  "Unit Warsaw": { lat: 52.23, lon: 21.01, city: "Warsaw" },
  "Unit Zurich": { lat: 47.38, lon: 8.54, city: "Zurich" },
};

const MAP_BOUNDS = { lonMin: -11, lonMax: 36, latMin: 31, latMax: 62 };

function projectLatLon(lat, lon, width, height) {
  const x = ((lon - MAP_BOUNDS.lonMin) / (MAP_BOUNDS.lonMax - MAP_BOUNDS.lonMin)) * width;
  const y = ((MAP_BOUNDS.latMax - lat) / (MAP_BOUNDS.latMax - MAP_BOUNDS.latMin)) * height;
  return { x, y };
}

function declutterNodes(nodes, home, minDist) {
  // Iteratively pushes nodes apart from each other AND away from the home
  // point if they're closer than minDist, preserving general map direction
  // while keeping labels legible. Home itself never moves.
  for (let iter = 0; iter < 300; iter++) {
    let moved = false;

    for (let i = 0; i < nodes.length; i++) {
      const dx0 = nodes[i].x - home.x, dy0 = nodes[i].y - home.y;
      const d0 = Math.sqrt(dx0 * dx0 + dy0 * dy0) || 0.001;
      if (d0 < minDist) {
        moved = true;
        const ux = dx0 / d0, uy = dy0 / d0;
        nodes[i].x = home.x + ux * minDist;
        nodes[i].y = home.y + uy * minDist;
      }
    }

    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = nodes[j].x - nodes[i].x, dy = nodes[j].y - nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 0.001;
        if (dist < minDist) {
          moved = true;
          const overlap = (minDist - dist) / 2;
          const ux = dx / dist, uy = dy / dist;
          nodes[i].x -= ux * overlap; nodes[i].y -= uy * overlap;
          nodes[j].x += ux * overlap; nodes[j].y += uy * overlap;
        }
      }
    }
    if (!moved) break;
  }
}

function renderNetwork(data) {
  const container = document.getElementById('networkSvgContainer');
  const units = Object.entries(data.ellis_member_collaborations || {})
    .filter(([name]) => !name.includes('Tübingen'))
    .filter(([name]) => SITE_COORDS[name]);

  const width = 1100, height = 620;
  const home = projectLatLon(SITE_COORDS["Institute Tübingen"].lat, SITE_COORDS["Institute Tübingen"].lon, width, height);
  const maxCount = Math.max(1, ...units.map(u => u[1]));

  const nodes = units.map(([name, count]) => {
    const coord = SITE_COORDS[name];
    const { x, y } = projectLatLon(coord.lat, coord.lon, width, height);
    return { name, count, city: coord.city, x, y, origX: x, origY: y };
  });

  declutterNodes(nodes, home, 55);

  let edges = '', nodeEls = '';
  nodes.forEach(n => {
    const strokeWidth = 1 + (n.count / maxCount) * 6;
    const r = 12 + (n.count / maxCount) * 12;

    // Line drawn to the node's true (pre-declutter) geographic position,
    // so direction stays accurate even though the label itself was nudged.
    edges += `<path class="edge" d="M ${home.x} ${home.y} L ${n.origX} ${n.origY}" stroke-width="${strokeWidth.toFixed(1)}" />`;
    nodeEls += `
      <g class="node-unit" transform="translate(${n.x},${n.y})">
        <circle r="${r.toFixed(1)}" />
        <text text-anchor="middle" dy="${r + 14}" font-size="12">${n.city}</text>
        <text text-anchor="middle" dy="4" font-size="11" fill="${COLORS.network}">${n.count}</text>
      </g>`;
  });

  const svg = `
    <svg viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
      ${edges}
      <g class="node-institute" transform="translate(${home.x},${home.y})">
        <circle r="20" />
        <text text-anchor="middle" dy="34" font-size="12" font-weight="600">ELLIS Tübingen</text>
      </g>
      ${nodeEls}
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
  renderVenues(data);
  renderTrendChart(data);
  renderNetwork(data);
  renderTable(data);
}).catch(err => {
  document.querySelector('.wrap').innerHTML =
    `<p style="padding:60px 0;color:#C87F4A;font-family:monospace;">Could not load data/publications.json — ${err.message}</p>`;
});
