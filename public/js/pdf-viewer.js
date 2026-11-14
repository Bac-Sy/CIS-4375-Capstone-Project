// PDF preview window for reports (buttons with data-pdf-preview="/reports/...?format=pdf").
// Shows the real PDF the server makes, with page thumbnails, page count, zoom, rotate and search,
// plus Download PDF and Print. Uses pdf.js, served from node_modules at /vendor/pdfjs.
(function () {
  var ZOOMS = [0.5, 0.75, 1, 1.25, 1.5, 2];
  var ICONS = {
    file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    panel: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18"/>',
    rotateLeft: '<path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/>',
    rotateRight: '<path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/>',
    zoomOut: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/>',
    zoomIn: '<circle cx="12" cy="12" r="10"/><path d="M8 12h8M12 8v8"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    close: '<path d="M18 6 6 18M6 6l12 12"/>',
    up: '<path d="m18 15-6-6-6 6"/>',
    down: '<path d="m6 9 6 6 6-6"/>'
  };

  // Small element builder: h('div', { class: 'x', onclick: fn }, child, 'text')
  function h(tag, attrs) {
    var el = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) {
      var v = attrs[k];
      if (v === null || v === undefined || v === false) return;
      if (k.indexOf('on') === 0) el.addEventListener(k.slice(2), v);
      else if (k === 'hidden') el.hidden = true;
      else el.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c === null || c === undefined || c === false) continue;
      el.append(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function icon(name) {
    var span = h('span', { class: 'pdfv-icon', 'aria-hidden': 'true' });
    span.innerHTML = '<svg viewBox="0 0 24 24">' + ICONS[name] + '</svg>';
    return span;
  }
  function tool(name, label, onclick) {
    return h('button', { class: 'pdfv-tool', type: 'button', 'aria-label': label, title: label, onclick: onclick }, icon(name));
  }

  var pdfjs = null;
  function loadPdfjs() {
    if (pdfjs) return Promise.resolve(pdfjs);
    return import('/vendor/pdfjs/pdf.min.mjs').then(function (lib) {
      lib.GlobalWorkerOptions.workerSrc = '/vendor/pdfjs/pdf.worker.min.mjs';
      pdfjs = lib;
      return lib;
    });
  }

  function openPdfPreview(opts) {
    var old = document.querySelector('dialog.pdfv');
    if (old) old.remove();
    var view = { pdf: null, bytes: null, zoom: 1, rotation: 0, page: 1, query: '', matches: [], matchAt: -1 };

    var pageLabel = h('span', { class: 'pdfv-count' }, 'Loading…');
    var zoomSelect = h('select', { class: 'pdfv-zoom', 'aria-label': 'Zoom', onchange: function () { setZoom(Number(zoomSelect.value)); } });
    ZOOMS.forEach(function (z) { zoomSelect.append(h('option', { value: String(z) }, Math.round(z * 100) + '%')); });
    var zoomOutBtn = tool('zoomOut', 'Zoom out', function () { setZoom(stepZoom(-1)); });
    var zoomInBtn = tool('zoomIn', 'Zoom in', function () { setZoom(stepZoom(1)); });

    var searchInput = h('input', { type: 'search', class: 'form-control form-control-sm', placeholder: 'Search the report', 'aria-label': 'Search the report' });
    var matchLabel = h('span', { class: 'pdfv-matches' });
    var searchBar = h('div', { class: 'pdfv-search', hidden: true }, icon('search'), searchInput, matchLabel,
      tool('up', 'Previous match', function () { jumpMatch(-1); }), tool('down', 'Next match', function () { jumpMatch(1); }));

    var thumbs = h('nav', { class: 'pdfv-thumbs', 'aria-label': 'Pages' });
    var pages = h('div', { class: 'pdfv-pages', tabindex: '0' },
      h('div', { class: 'pdfv-status' }, h('span', { class: 'pdfv-spinner', 'aria-hidden': 'true' }),
        h('p', null, 'Making the PDF…'), h('p', { class: 'pdfv-muted' }, 'This takes a few seconds.')));
    var body = h('div', { class: 'pdfv-body' }, thumbs, pages);
    if (window.innerWidth < 760) body.classList.add('no-thumbs');

    var error = h('p', { class: 'pdfv-error', role: 'alert', hidden: true });
    var downloadBtn = h('a', { class: 'btn btn-outline-secondary disabled', href: opts.url + (opts.url.indexOf('?') >= 0 ? '&' : '?') + 'download=1', 'aria-disabled': 'true' }, 'Download PDF');
    var printBtn = h('button', { class: 'scc-btn', type: 'button', disabled: true, onclick: printPdf }, 'Print');
    var closeBtn = h('button', { class: 'btn btn-outline-secondary', type: 'button', onclick: function () { dlg.close(); } }, 'Close');

    var dlg = h('dialog', { class: 'pdfv', 'aria-label': 'Preview: ' + opts.title },
      h('header', { class: 'pdfv-head' },
        h('div', { class: 'pdfv-title' }, icon('file'),
          h('div', null, h('h2', null, opts.title), opts.subtitle ? h('p', null, opts.subtitle) : null)),
        tool('close', 'Close preview', function () { dlg.close(); })),
      h('div', { class: 'pdfv-toolbar' },
        h('div', { class: 'pdfv-group' }, tool('panel', 'Show or hide pages', function () { body.classList.toggle('no-thumbs'); }), pageLabel),
        h('div', { class: 'pdfv-group' },
          tool('rotateLeft', 'Rotate left', function () { setRotation(view.rotation - 90); }),
          tool('rotateRight', 'Rotate right', function () { setRotation(view.rotation + 90); }),
          h('span', { class: 'pdfv-sep' }), zoomOutBtn, zoomInBtn, zoomSelect,
          h('span', { class: 'pdfv-sep' }), tool('search', 'Search', toggleSearch))),
      searchBar,
      body,
      h('footer', { class: 'pdfv-foot' },
        h('div', { class: 'pdfv-note' }, h('p', null, 'This is exactly what prints or downloads.'), error),
        h('div', { class: 'pdfv-actions' }, closeBtn, downloadBtn, printBtn)));

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) setCurrentPage(Number(e.target.dataset.page)); });
    }, { root: pages, threshold: 0.5 });
    dlg.addEventListener('close', function () {
      observer.disconnect();
      if (view.pdf) view.pdf.destroy();
      dlg.remove();
    });
    document.body.append(dlg);
    dlg.showModal();
    load();

    function load() {
      fetch(opts.url, { cache: 'no-store', credentials: 'same-origin' }).then(function (res) {
        if (!res.ok) return res.text().then(function (t) { throw new Error(t || 'The PDF could not be made.'); });
        if ((res.headers.get('Content-Type') || '').indexOf('application/pdf') < 0) throw new Error('Your session may have ended. Refresh the page and log in again.');
        return res.arrayBuffer();
      }).then(function (bytes) {
        view.bytes = bytes.slice(0);
        return loadPdfjs().then(function (lib) { return lib.getDocument({ data: bytes }).promise; });
      }).then(function (pdf) {
        view.pdf = pdf;
        if (!dlg.isConnected) return pdf.destroy();
        return pdf.getPage(1).then(function (first) {
          var vp = first.getViewport({ scale: 96 / 72 });
          view.zoom = Math.min(1, Math.floor(((pages.clientWidth - 48) / vp.width) * 100) / 100);
          return renderAll();
        });
      }).then(function () {
        printBtn.disabled = false;
        downloadBtn.classList.remove('disabled');
        downloadBtn.removeAttribute('aria-disabled');
        printBtn.focus();
      }).catch(function (err) {
        pages.replaceChildren(h('div', { class: 'pdfv-status' }, h('p', null, err.message)));
        pageLabel.textContent = '';
      });
    }

    function renderAll() {
      var n = view.pdf.numPages;
      var ratio = window.devicePixelRatio || 1;
      observer.disconnect();
      var pageNodes = [], thumbNodes = [], jobs = [];
      for (var i = 1; i <= n; i++) jobs.push(view.pdf.getPage(i));
      return Promise.all(jobs).then(function (list) {
        list.forEach(function (page, idx) {
          var num = idx + 1;
          var vp = page.getViewport({ scale: view.zoom * (96 / 72), rotation: view.rotation });
          var canvas = h('canvas', { width: Math.floor(vp.width * ratio), height: Math.floor(vp.height * ratio) });
          canvas.style.width = vp.width + 'px';
          canvas.style.height = vp.height + 'px';
          var textLayer = h('div', { class: 'textLayer' });
          var sheet = h('div', { class: 'pdfv-page', 'data-page': String(num) }, canvas, textLayer);
          sheet.style.width = vp.width + 'px';
          sheet.style.height = vp.height + 'px';
          sheet.style.setProperty('--scale-factor', String(vp.scale));
          pageNodes.push(sheet);
          page.render({ canvasContext: canvas.getContext('2d'), viewport: vp, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null });
          new pdfjs.TextLayer({ textContentSource: page.streamTextContent(), container: textLayer, viewport: vp })
            .render().then(function () { highlight(textLayer); });
          var base = page.getViewport({ scale: 1, rotation: view.rotation });
          var small = page.getViewport({ scale: (140 / base.width) * ratio, rotation: view.rotation });
          var thumbCanvas = h('canvas', { width: Math.floor(small.width), height: Math.floor(small.height) });
          thumbCanvas.style.width = '140px';
          page.render({ canvasContext: thumbCanvas.getContext('2d'), viewport: small });
          thumbNodes.push(h('button', { class: 'pdfv-thumb', type: 'button', 'data-page': String(num), 'aria-label': 'Page ' + num,
            onclick: function () { sheet.scrollIntoView({ behavior: 'smooth', block: 'start' }); } }, thumbCanvas, h('span', null, String(num))));
        });
        var at = pages.scrollTop / (pages.scrollHeight || 1);
        pages.replaceChildren.apply(pages, pageNodes);
        thumbs.replaceChildren.apply(thumbs, thumbNodes);
        pages.scrollTop = at * pages.scrollHeight;
        pageNodes.forEach(function (p) { observer.observe(p); });
        setCurrentPage(Math.min(view.page, n));
        var fit = zoomSelect.querySelector('.fit');
        if (fit) fit.remove();
        if (ZOOMS.indexOf(view.zoom) < 0) zoomSelect.prepend(h('option', { class: 'fit', value: String(view.zoom) }, Math.round(view.zoom * 100) + '%'));
        zoomSelect.value = String(view.zoom);
        zoomOutBtn.disabled = view.zoom <= ZOOMS[0];
        zoomInBtn.disabled = view.zoom >= ZOOMS[ZOOMS.length - 1];
      });
    }

    function setCurrentPage(n) {
      view.page = n;
      pageLabel.textContent = 'Page ' + n + ' of ' + (view.pdf ? view.pdf.numPages : 1);
      thumbs.querySelectorAll('.pdfv-thumb').forEach(function (t) { t.classList.toggle('active', Number(t.dataset.page) === n); });
    }
    function stepZoom(dir) {
      var next = dir > 0 ? ZOOMS.find(function (z) { return z > view.zoom; }) : ZOOMS.slice().reverse().find(function (z) { return z < view.zoom; });
      return next === undefined ? view.zoom : next;
    }
    function setZoom(z) { if (view.pdf && z !== view.zoom) { view.zoom = z; renderAll(); } }
    function setRotation(r) { if (view.pdf) { view.rotation = ((r % 360) + 360) % 360; renderAll(); } }

    // Search: matches are marked in the invisible text layer over each page.
    function toggleSearch() {
      searchBar.hidden = !searchBar.hidden;
      if (!searchBar.hidden) searchInput.focus();
      else { searchInput.value = ''; runSearch(); }
    }
    var timer;
    searchInput.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(runSearch, 150); });
    searchInput.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); jumpMatch(e.shiftKey ? -1 : 1); } });
    function runSearch() {
      view.query = searchInput.value.trim().toLowerCase();
      pages.querySelectorAll('.textLayer').forEach(highlight);
      collect();
      if (view.matches.length) jumpMatch(1);
    }
    function highlight(layer) {
      layer.querySelectorAll('mark').forEach(function (m) { m.replaceWith(m.textContent); });
      layer.querySelectorAll('span').forEach(function (s) { s.normalize(); });
      if (!view.query) return;
      layer.querySelectorAll('span:not(.markedContent)').forEach(function (span) {
        var text = span.textContent, lower = text.toLowerCase();
        if (lower.indexOf(view.query) < 0) return;
        var parts = [], at = 0;
        for (var i = lower.indexOf(view.query); i !== -1; i = lower.indexOf(view.query, at)) {
          parts.push(text.slice(at, i), h('mark', { class: 'pdfv-hit' }, text.slice(i, i + view.query.length)));
          at = i + view.query.length;
        }
        parts.push(text.slice(at));
        span.replaceChildren.apply(span, parts);
      });
      if (layer.isConnected) collect();
    }
    function collect() {
      view.matches = Array.prototype.slice.call(pages.querySelectorAll('mark.pdfv-hit'));
      view.matchAt = Math.min(view.matchAt, view.matches.length - 1);
      matchLabel.textContent = !view.query ? '' : view.matches.length ? (Math.max(view.matchAt, 0) + 1) + ' of ' + view.matches.length : 'No matches';
    }
    function jumpMatch(dir) {
      if (!view.matches.length) return;
      if (view.matches[view.matchAt]) view.matches[view.matchAt].classList.remove('current');
      view.matchAt = (view.matchAt + dir + view.matches.length) % view.matches.length;
      var mark = view.matches[view.matchAt];
      mark.classList.add('current');
      mark.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'center' });
      matchLabel.textContent = (view.matchAt + 1) + ' of ' + view.matches.length;
    }

    // Print the PDF itself (not the web page): load it into a hidden frame and open the print dialog.
    function printPdf() {
      if (!view.bytes) return;
      var url = URL.createObjectURL(new Blob([view.bytes], { type: 'application/pdf' }));
      var frame = h('iframe', { class: 'pdfv-print-frame', title: 'Print', src: url });
      frame.addEventListener('load', function () {
        try { frame.contentWindow.focus(); frame.contentWindow.print(); }
        catch (e) { window.open(url, '_blank'); }
        setTimeout(function () { frame.remove(); URL.revokeObjectURL(url); }, 60000);
      });
      document.body.append(frame);
    }
  }

  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-pdf-preview]');
    if (!btn) return;
    e.preventDefault();
    openPdfPreview({ url: btn.getAttribute('data-pdf-preview'), title: btn.getAttribute('data-pdf-title') || 'Report', subtitle: btn.getAttribute('data-pdf-subtitle') || '' });
  });
  window.openPdfPreview = openPdfPreview;
})();
