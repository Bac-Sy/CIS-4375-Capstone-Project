// Record transaction page (views/pages/newtransaction.ejs): when Restock is chosen,
// show which supplier the stock comes from (the product's supplier, set on Edit product).
(function () {
  var item = document.getElementById('Variant_ID');
  var type = document.getElementById('Transaction_Type_ID');
  var note = document.getElementById('supplierNote');
  if (!item || !type || !note) return;
  function update() {
    var chosenType = type.options[type.selectedIndex];
    var chosenItem = item.options[item.selectedIndex];
    var isRestock = chosenType && chosenType.dataset.type === 'Restock';
    if (!isRestock || !chosenItem || !chosenItem.value) { note.hidden = true; return; }
    var supplier = chosenItem.dataset.supplier;
    note.textContent = '';
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
