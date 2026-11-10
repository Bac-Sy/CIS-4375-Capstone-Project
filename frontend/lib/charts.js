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

// points: [{ date, total_units }]. Needs at least two days of history to draw a line.
function buildTrend(points) {
  if (!points || points.length < 2) return null;

  const W = 320, H = 140, PAD = 14;
  const values = points.map((p) => Number(p.total_units));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const coords = values.map((v, i) => {
    const x = (i * W) / (values.length - 1);
    const y = H - PAD - ((v - min) / range) * (H - PAD * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const line = 'M' + coords.join(' L');
  return {
    line,
    area: `${line} L${W},${H} L0,${H} Z`,
    first: points[0],
    last: points[points.length - 1]
  };
}

module.exports = { buildDonut, buildTrend };
