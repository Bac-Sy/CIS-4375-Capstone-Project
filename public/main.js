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
