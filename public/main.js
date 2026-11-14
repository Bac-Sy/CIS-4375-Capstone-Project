(function () {
  var sidebar = document.getElementById('sidebar');
  var toggles = document.querySelectorAll('[data-menu-toggle]');
  if (!sidebar || !toggles.length) return;

  function setOpen(open) {
    sidebar.classList.toggle('open', open);
    document.body.classList.toggle('nav-open', open);
    toggles.forEach(function (btn) {
      btn.setAttribute('aria-expanded', String(open));
    });
  }

  toggles.forEach(function (btn) {
    btn.addEventListener('click', function () {
      setOpen(!sidebar.classList.contains('open'));
    });
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setOpen(false);
  });

  // Reset if the window is resized up to desktop width
  window.matchMedia('(min-width: 801px)').addEventListener('change', function (e) {
    if (e.matches) setOpen(false);
  });
})();

// ⋯ row menus (template/rowmenu.ejs). The list uses position: fixed so a table's scroll box can't cut it off.
(function () {
  var menus = document.querySelectorAll('details.row-menu');
  if (!menus.length) return;

  function place(menu) {
    var list = menu.querySelector('.row-menu-list');
    var btn = menu.querySelector('summary');
    if (!list || !btn) return;
    var r = btn.getBoundingClientRect();
    list.style.visibility = 'hidden';
    list.style.left = '0px';
    list.style.top = '0px';
    var w = list.offsetWidth, h = list.offsetHeight;
    var left = Math.max(8, Math.min(r.right - w, window.innerWidth - w - 8));
    var top = r.bottom + 6;
    if (top + h > window.innerHeight - 8 && r.top - h - 6 > 8) top = r.top - h - 6; // open upward near the bottom
    list.style.left = left + 'px';
    list.style.top = top + 'px';
    list.style.visibility = '';
  }
  function closeAll(except) {
    menus.forEach(function (m) { if (m !== except) m.removeAttribute('open'); });
  }

  menus.forEach(function (menu) {
    menu.addEventListener('toggle', function () {
      if (menu.open) { closeAll(menu); place(menu); }
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('details.row-menu')) closeAll(null);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = document.querySelector('details.row-menu[open]');
    if (open) { open.removeAttribute('open'); open.querySelector('summary').focus(); }
  });
  // Keep an open menu next to its button when the page scrolls; close it once the button is out of sight.
  function follow() {
    var open = document.querySelector('details.row-menu[open]');
    if (!open) return;
    var r = open.querySelector('summary').getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight) open.removeAttribute('open');
    else place(open);
  }
  window.addEventListener('scroll', follow, true);
  window.addEventListener('resize', follow);
})();

// Inventory: − / + buttons and the "Was 5 · saves +2" note while adjusting stock.
(function () {
  document.querySelectorAll('form.inv-adjust').forEach(function (form) {
    var input = form.querySelector('input[name="New_Quantity"]');
    var note = form.querySelector('.inv-adjust-note');
    var was = Number(form.dataset.was) || 0;
    function update() {
      var n = Number(input.value);
      if (!note) return;
      if (input.value === '' || !Number.isInteger(n) || n < 0) { note.textContent = 'Was ' + was + ' · enter a whole number'; return; }
      var diff = n - was;
      note.textContent = diff === 0 ? 'Was ' + was + ' · no change'
        : 'Was ' + was + ' · saves ' + (diff > 0 ? '+' : '') + diff + ' as an Adjustment';
    }
    form.querySelectorAll('[data-step]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var n = Number(input.value) || 0;
        input.value = Math.max(0, n + Number(btn.dataset.step));
        update();
      });
    });
    input.addEventListener('input', update);
    update();
    input.focus();
    input.select();
  });

  // ▾ / ▸ collapses a product's variant rows.
  document.querySelectorAll('[data-collapse]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') === 'true';
      btn.setAttribute('aria-expanded', String(!open));
      btn.textContent = open ? '▸' : '▾';
      document.querySelectorAll('[data-parent="' + btn.dataset.collapse + '"]').forEach(function (row) {
        row.hidden = open;
      });
    });
  });
})();
