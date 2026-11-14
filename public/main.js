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

// Show / hide password: an eye button inside every password box (login, settings, add employee, reset password).
(function () {
  var EYE = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>';
  var EYE_OFF = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M17.9 17.9A10.7 10.7 0 0 1 12 19c-6.5 0-10-7-10-7a18.4 18.4 0 0 1 5.1-5.9M9.9 5.2A9.8 9.8 0 0 1 12 5c6.5 0 10 7 10 7a18.5 18.5 0 0 1-2.2 3.2M14.1 14.1a3 3 0 1 1-4.2-4.2"/><path d="M2 2l20 20"/></svg>';
  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    if (input.hidden || input.closest('.pw-wrap')) return;
    var wrap = document.createElement('span');
    wrap.className = 'pw-wrap';
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'pw-toggle';
    btn.setAttribute('aria-label', 'Show password');
    btn.setAttribute('aria-pressed', 'false');
    btn.title = 'Show password';
    btn.innerHTML = EYE;
    btn.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      btn.innerHTML = show ? EYE_OFF : EYE;
      btn.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      btn.setAttribute('aria-pressed', String(show));
      btn.title = show ? 'Hide password' : 'Show password';
      input.focus();
    });
    // hide it again when the form is sent, so the browser doesn't remember it as plain text
    if (input.form) input.form.addEventListener('submit', function () { input.type = 'password'; });
    wrap.appendChild(btn);
  });
})();

// Theme: light / dark / match the computer. The sidebar moon/sun button flips light <-> dark;
// Settings -> Appearance also offers "Match my computer". Saved in this browser (localStorage).
(function () {
  var root = document.documentElement;
  function stored() { try { return localStorage.getItem('scc-theme') || 'light'; } catch (e) { return 'light'; } }
  function save(choice) { try { localStorage.setItem('scc-theme', choice); } catch (e) { /* storage blocked */ } }
  var systemDark = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function apply(choice) {
    var dark = choice === 'dark' || (choice === 'system' && systemDark && systemDark.matches);
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.setAttribute('data-bs-theme', dark ? 'dark' : 'light');
    document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
      b.setAttribute('aria-label', dark ? 'Switch to light mode' : 'Switch to dark mode');
      b.title = dark ? 'Light mode' : 'Dark mode';
    });
    document.querySelectorAll('input[name="theme-choice"]').forEach(function (r) { r.checked = r.value === choice; });
  }
  document.querySelectorAll('[data-theme-toggle]').forEach(function (b) {
    b.addEventListener('click', function () {
      var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      save(next); apply(next);
    });
  });
  document.querySelectorAll('input[name="theme-choice"]').forEach(function (r) {
    r.addEventListener('change', function () { save(r.value); apply(r.value); });
  });
  if (systemDark && systemDark.addEventListener) systemDark.addEventListener('change', function () { if (stored() === 'system') apply('system'); });
  apply(stored());
})();
