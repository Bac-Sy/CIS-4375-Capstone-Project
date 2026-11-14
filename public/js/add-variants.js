// Add variants page (views/pages/newvariant.ejs).
// Shows a row for each picked size x color, keeps the "Add N variants" button count current,
// and switches each row between its own location/price/cost and the "same for all" values.
(function () {
  var form = document.getElementById('variantForm');
  if (!form) return;
  var rows = Array.prototype.slice.call(form.querySelectorAll('.combo-row'));
  var noCombos = document.getElementById('noCombos');
  var countText = document.getElementById('variantCount');
  var addButton = document.getElementById('addButton');
  var sameLocation = document.getElementById('sameLocation');
  var samePrice = document.getElementById('samePrice');
  var location = document.getElementById('Location_ID');
  var price = document.getElementById('Price');
  var cost = document.getElementById('Cost');

  function picked(kind) {
    var ids = {};
    form.querySelectorAll('[data-pick="' + kind + '"]:checked').forEach(function (box) { ids[box.value] = true; });
    return ids;
  }
  function money(value) {
    var n = Number(String(value || '').replace(/^\$/, ''));
    return value && Number.isFinite(n) ? '$' + n.toFixed(2) : '—';
  }

  // Unchecked rows are greyed out and their boxes are switched off, so they aren't sent.
  function paintRow(row) {
    if (row.dataset.exists) return;
    var box = row.querySelector('.combo-check');
    var on = box.checked;
    row.classList.toggle('off', !on);
    row.querySelectorAll('.fields').forEach(function (cell) { cell.hidden = !on; });
    row.querySelector('.off-note').hidden = on;
    row.querySelectorAll('[data-own]').forEach(function (input) {
      var useSame = (input.dataset.own === 'location' && sameLocation.checked) ||
                    (input.dataset.own !== 'location' && samePrice.checked);
      input.hidden = useSame;
      input.disabled = !on || useSame;
    });
    row.querySelector('input.stock').disabled = !on;
    row.querySelectorAll('[data-same]').forEach(function (span) {
      var kind = span.dataset.same;
      var useSame = kind === 'location' ? sameLocation.checked : samePrice.checked;
      span.hidden = !useSame;
      if (kind === 'location') span.textContent = location.options[location.selectedIndex] ? location.options[location.selectedIndex].text : '—';
      if (kind === 'price') span.textContent = money(price.value);
      if (kind === 'cost') span.textContent = money(cost.value);
    });
  }

  function refresh() {
    var sizes = picked('size'), colors = picked('color');
    var shown = 0, checked = 0, exist = 0, unchecked = 0;
    rows.forEach(function (row) {
      var visible = sizes[row.dataset.size] && colors[row.dataset.color];
      var box = row.querySelector('.combo-check');
      if (!visible && box && box.checked) box.checked = false;
      if (visible && box && !row.dataset.seen) { box.checked = true; row.dataset.seen = '1'; }
      if (!visible && row.dataset.seen) delete row.dataset.seen;
      row.hidden = !visible;
      if (!visible) return;
      shown++;
      if (row.dataset.exists) exist++;
      else if (box.checked) checked++;
      else unchecked++;
      paintRow(row);
    });
    noCombos.hidden = shown > 0;
    if (!shown) countText.textContent = 'Pick at least one size and one color.';
    else countText.innerHTML = '<strong>' + checked + ' checked</strong>' +
      (exist ? ' · ' + exist + ' already exist' : '') + (unchecked ? ' · ' + unchecked + ' left unchecked' : '');
    addButton.textContent = checked === 1 ? 'Add 1 variant' : 'Add ' + checked + ' variants';
    addButton.disabled = checked === 0;
    location.disabled = false;
    price.required = cost.required = samePrice.checked && checked > 0;
  }

  form.addEventListener('change', function (e) {
    if (e.target.matches('.combo-check')) { paintRow(e.target.closest('.combo-row')); refreshCountOnly(); return; }
    refresh();
  });
  form.addEventListener('input', function (e) {
    if (e.target === price || e.target === cost) rows.forEach(function (row) { if (!row.hidden) paintRow(row); });
  });
  function refreshCountOnly() { refresh(); }

  // Rows the server sent were all visible (so the page works without this script); start from the picks.
  refresh();

  form.addEventListener('submit', function (e) {
    var checked = form.querySelectorAll('.combo-check:checked').length;
    if (!checked) { e.preventDefault(); countText.textContent = 'Check at least one combination to add.'; return; }
    if (samePrice.checked && (!price.value || !cost.value)) {
      e.preventDefault();
      (price.value ? cost : price).focus();
      countText.textContent = 'Enter the price and cost to use for all variants, or untick "Same price and cost".';
    }
  });
})();
