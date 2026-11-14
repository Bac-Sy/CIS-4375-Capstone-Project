// Record transaction page (views/pages/newtransaction.ejs):
// - Restock: shows which supplier the stock comes from (the product's supplier, set on Edit product).
// - Sale of a product set to Not available: says it can't be sold and disables Record
//   (the server and the API refuse it too; restocks are still allowed).
(function () {
  var item = document.getElementById('Variant_ID');
  var type = document.getElementById('Transaction_Type_ID');
  var note = document.getElementById('supplierNote');
  if (!item || !type || !note) return;
  var form = item.closest('form');
  var submit = form ? form.querySelector('button[type="submit"]') : null;
  function update() {
    var chosenType = type.options[type.selectedIndex];
    var chosenItem = item.options[item.selectedIndex];
    var kind = chosenType ? chosenType.dataset.type : '';
    var hasItem = chosenItem && chosenItem.value;
    var blocked = kind === 'Sale' && hasItem && chosenItem.dataset.available === '0';
    if (submit) submit.disabled = !!blocked;
    note.classList.toggle('blocked-note', !!blocked);
    note.textContent = '';
    if (blocked) {
      note.textContent = 'This product is set to Not available, so it can’t be sold. Set it back to Available on Edit product first.';
      note.hidden = false;
      return;
    }
    if (kind !== 'Restock' || !hasItem) { note.hidden = true; return; }
    var supplier = chosenItem.dataset.supplier;
    if (supplier) {
      note.appendChild(document.createTextNode('From: '));
      var name = document.createElement('strong');
      name.textContent = supplier;
      note.appendChild(name);
    } else {
      note.textContent = 'This product has no supplier yet. Set one on Edit product.';
    }
    note.hidden = false;
  }
  item.addEventListener('change', update);
  type.addEventListener('change', update);
  update();
})();
