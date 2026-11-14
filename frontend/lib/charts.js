const PALETTE = ['#0000aa', '#d40037', '#7f88ff', '#00006b', '#ff7a9c', '#4a54e1'];

// items: [{ name, revenue }]. Returns SVG ring segments, or null if there is nothing to show.
function buildDonut(items) {
  const rows = (items || []).filter((i) => Number(i.revenue) > 0);
  const total = rows.reduce((sum, i) => sum + Number(i.revenue), 0);
  if (!rows.length || total <= 0) return null;

  const gap = rows.length > 1 ? 1 : 0;
  let start = 0;
  const segments = rows.map((item, idx) => {
    const pct = (Number(item.revenue) / total) * 100;
    const len = Math.max(pct - gap, 0.5);
    const segment = {
      name: item.name,
      revenue: Number(item.revenue),
      color: PALETTE[idx % PALETTE.length],
      dash: `${len.toFixed(2)} ${(100 - len).toFixed(2)}`,
      offset: (25 - start).toFixed(2)
    };
    start += pct;
    return segment;
  });
  return { total, segments };
}

// Stock in vs. out (Dashboard): weeks = [{ start: 'YYYY-MM-DD', sold, restocked }] from Flask /dashboard.
// Returns bar geometry for an SVG with one y-axis, or null when there are no weeks.
// Colors were checked to stay distinguishable for color-blind viewers (blue vs. teal).
const FLOW_COLORS = { sold: '#2b2fd6', restocked: '#1a9e8f' };
function buildFlow(weeks) {
  if (!Array.isArray(weeks) || !weeks.length) return null;
  const W = 440, H = 190, LEFT = 34, BOTTOM = 26, TOP = 12;
  const plotH = H - BOTTOM - TOP;
  const rows = weeks.map((w) => ({
    start: String(w.start || ''),
    sold: Math.max(0, Number(w.sold) || 0),
    restocked: Math.max(0, Number(w.restocked) || 0)
  }));
  const biggest = Math.max(...rows.map((r) => Math.max(r.sold, r.restocked)), 0);
  // A round top value (4, 10, 20, 50, 100…) so the 3 gridlines get tidy labels.
  const nice = [4, 10, 20, 30, 50, 100, 200, 300, 500, 1000, 2000, 5000, 10000];
  const top = nice.find((n) => n >= biggest) || Math.ceil(biggest / 1000) * 1000;
  const y = (v) => TOP + plotH - (v / top) * plotH;
  const group = (W - LEFT) / rows.length;
  const barW = Math.min(26, group / 3);
  const label = (iso) => {
    const [yy, mm, dd] = iso.split('-').map(Number);
    return new Date(yy, (mm || 1) - 1, dd || 1).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };
  const bars = [];
  rows.forEach((r, i) => {
    const center = LEFT + group * i + group / 2;
    [['sold', center - barW - 1], ['restocked', center + 1]].forEach(([kind, x]) => {
      const value = r[kind];
      if (value <= 0) return;
      const yTop = y(value), base = TOP + plotH, rad = Math.min(4, base - yTop);
      bars.push({
        kind, value, week: label(r.start), color: FLOW_COLORS[kind],
        // rounded top corners, square at the baseline
        d: `M${x.toFixed(1)},${base} V${(yTop + rad).toFixed(1)} Q${x.toFixed(1)},${yTop.toFixed(1)} ${(x + rad).toFixed(1)},${yTop.toFixed(1)} ` +
           `H${(x + barW - rad).toFixed(1)} Q${(x + barW).toFixed(1)},${yTop.toFixed(1)} ${(x + barW).toFixed(1)},${(yTop + rad).toFixed(1)} V${base} Z`
      });
    });
  });
  const totals = rows.reduce((t, r) => ({ sold: t.sold + r.sold, restocked: t.restocked + r.restocked }), { sold: 0, restocked: 0 });
  return {
    width: W, height: H, left: LEFT, colors: FLOW_COLORS, bars, totals,
    gridlines: [0, top / 2, top].map((v) => ({ value: v, y: y(v).toFixed(1) })),
    labels: rows.map((r, i) => ({ text: label(r.start), x: (LEFT + group * i + group / 2).toFixed(1), y: H - 6 }))
  };
}

module.exports = { buildDonut, buildFlow };
