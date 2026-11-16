const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' });
const num = new Intl.NumberFormat('en-US');
const day = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' });

module.exports = {
  money: (n) => usd.format(Number(n) || 0),
  number: (n) => num.format(Number(n) || 0),
  signed: (n) => (Number(n) > 0 ? '+' : '') + num.format(Number(n) || 0),
  // Flask sends dates as YYYY-MM-DD. Parse as UTC so the day never shifts.
  date: (iso) => (iso ? day.format(new Date(`${String(iso).slice(0, 10)}T00:00:00Z`)) : ''),
  tagClass: (type) => (type === 'Sale' ? 'tag-blue' : type === 'Restock' ? 'tag-soft' : 'tag-outline')
};
