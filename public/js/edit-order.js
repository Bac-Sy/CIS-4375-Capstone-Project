// Edit order page (views/pages/edit-order.ejs): explains what saving will do to the stock.
(function () {
  var form = document.getElementById('orderForm');
  var preview = document.getElementById('stockPreview');
  if (!form || !preview) return;
  var item = document.getElementById('Variant_ID');
  var qty = document.getElementById('Quantity_Change');
  var type = document.getElementById('Transaction_Type_ID');
  var hint = document.getElementById('signHint');
  var oldVariant = form.dataset.oldVariant;
  var oldQty = Number(form.dataset.oldQty) || 0;

  function option(id) {
    for (var i = 0; i < item.options.length; i++) if (item.options[i].value === id) return item.options[i];
    return null;
  }
  function text(node, value) { node.textContent = value; }
  function line(name, before, after) {
    var b = document.createElement('strong'); b.textContent = name;
    var span = document.createElement('span');
    span.appendChild(b);
    span.appendChild(document.createTextNode(before === '' ? '' : ' (' + before + ' → ' + after + ')'));
    return span;
  }
  function update() {
    var newVariant = item.value;
    var newQty = Number(qty.value);
    var kind = type.options[type.selectedIndex] ? type.options[type.selectedIndex].dataset.type : '';
    text(hint, kind === 'Sale' ? 'A Sale is negative (stock goes down).'
      : kind === 'Restock' ? 'A Restock is positive (stock goes up).'
      : 'An Adjustment can be either: negative takes stock away, positive adds it.');
    preview.innerHTML = '';
    if (!Number.isInteger(newQty) || newQty === 0) { text(preview, 'Enter a whole number other than 0.'); return; }
    var oldOpt = option(oldVariant), newOpt = option(newVariant);
    var oldName = oldOpt ? oldOpt.dataset.name : 'the original item';
    var newName = newOpt ? newOpt.dataset.name : 'the new item';
    var oldStock = oldOpt && oldOpt.dataset.stock !== '' ? Number(oldOpt.dataset.stock) : '';
    var newStock = newOpt && newOpt.dataset.stock !== '' ? Number(newOpt.dataset.stock) : '';
    var parts = [];
    if (newVariant === oldVariant) {
      var diff = newQty - oldQty;
      if (diff === 0) { text(preview, 'The stock stays the same.'); return; }
      parts.push(document.createTextNode((diff > 0 ? 'Adds ' + diff + ' to ' : 'Takes ' + (-diff) + ' off ')));
      parts.push(line(newName, newStock, newStock === '' ? '' : newStock + diff));
      parts.push(document.createTextNode('.'));
      if (newStock !== '' && newStock + diff < 0) parts.push(document.createTextNode(' There isn’t enough stock, so it won’t save.'));
    } else {
      var back = -oldQty, after = newQty;
      parts.push(document.createTextNode(back > 0 ? 'Puts ' + back + ' back on ' : 'Takes ' + (-back) + ' off '));
      parts.push(line(oldName, oldStock, oldStock === '' ? '' : oldStock + back));
      parts.push(document.createTextNode(after > 0 ? ' and adds ' + after + ' to ' : ' and takes ' + (-after) + ' off '));
      parts.push(line(newName, newStock, newStock === '' ? '' : newStock + after));
      parts.push(document.createTextNode('.'));
      if ((newStock !== '' && newStock + after < 0) || (oldStock !== '' && oldStock + back < 0)) {
        parts.push(document.createTextNode(' There isn’t enough stock, so it won’t save.'));
      }
    }
    parts.forEach(function (p) { preview.appendChild(p); });
  }
  form.addEventListener('input', update);
  form.addEventListener('change', update);
  update();
})();
