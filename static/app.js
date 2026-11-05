(function () {
  var d = document, root = d.body.dataset.root, lang = d.body.dataset.lang;
  function store(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  // Theme toggle
  var tb = d.querySelector('[data-theme-toggle]');
  if (tb) tb.addEventListener('click', function () {
    var cur = d.documentElement.dataset.theme;
    var dark = cur === 'dark' || (cur !== 'light' && matchMedia('(prefers-color-scheme: dark)').matches);
    var next = dark ? 'light' : 'dark';
    d.documentElement.dataset.theme = next; store('ovnw-theme', next);
  });

  // Remember language choice
  d.querySelectorAll('[data-setlang]').forEach(function (a) {
    a.addEventListener('click', function () { store('ovnw-lang', a.dataset.setlang); });
  });

  // Mobile drawer
  var drawer = d.getElementById('drawer'), mb = d.querySelector('[data-open-menu]');
  function closeDrawer() { drawer.hidden = true; if (mb) mb.setAttribute('aria-expanded', 'false'); }
  if (mb) mb.addEventListener('click', function () { drawer.hidden = false; mb.setAttribute('aria-expanded', 'true'); });
  if (drawer) drawer.addEventListener('click', function (e) { if (e.target === drawer || e.target.closest('[data-close-menu]')) closeDrawer(); });

  // Copy link
  d.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(function () {
        var o = b.getAttribute('aria-label'); b.setAttribute('aria-label', b.dataset.copied); b.style.color = 'var(--brand)';
        setTimeout(function () { b.setAttribute('aria-label', o); b.style.color = ''; }, 1600);
      });
    });
  });

  // Search
  var modal = d.getElementById('search'), q = d.getElementById('q'), res = d.getElementById('results'), idx = null, sel = -1;
  function openSearch() {
    modal.hidden = false; q.value = ''; render([]); setTimeout(function () { q.focus(); }, 10);
    if (!idx) fetch(root + lang + '/search.json').then(function (r) { return r.json(); }).then(function (j) { idx = j; }).catch(function () { idx = []; });
  }
  function closeSearch() { modal.hidden = true; }
  function esc(s) { return s.replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function render(items) {
    sel = -1;
    if (!q.value.trim()) { res.innerHTML = ''; return; }
    if (!items.length) { res.innerHTML = '<li class="r-empty">' + res.dataset.empty + '</li>'; return; }
    res.innerHTML = items.slice(0, 12).map(function (a) {
      return '<li><a href="' + root + lang + '/a/' + a.id + '.html"><span class="r-t">' + esc(a.t) + '</span><span class="r-m">' + esc(a.c) + ' · ' + esc(a.d) + '</span></a></li>';
    }).join('');
  }
  if (modal) {
    d.querySelectorAll('[data-open-search]').forEach(function (b) { b.addEventListener('click', openSearch); });
    modal.addEventListener('click', function (e) { if (e.target === modal || e.target.closest('[data-close-search]')) closeSearch(); });
    q.addEventListener('input', function () {
      var terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
      render((idx || []).filter(function (a) { var h = (a.t + ' ' + a.s + ' ' + a.c).toLowerCase(); return terms.every(function (t) { return h.indexOf(t) > -1; }); }));
    });
    q.addEventListener('keydown', function (e) {
      var links = res.querySelectorAll('a'); if (!links.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length;
        links.forEach(function (l, i) { l.classList.toggle('sel', i === sel); });
      } else if (e.key === 'Enter' && sel > -1) { location.href = links[sel].href; }
    });
  }
  d.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { if (modal && !modal.hidden) closeSearch(); if (drawer && !drawer.hidden) closeDrawer(); }
    if ((e.key === '/' || (e.key === 'k' && (e.metaKey || e.ctrlKey))) && modal && modal.hidden && !/input|textarea/i.test(d.activeElement.tagName)) { e.preventDefault(); openSearch(); }
  });
})();

// Radio player (TuneIn embed is only loaded when the reader presses play)
(function () {
  var d = document, bar = d.getElementById('radio-bar');
  function popout(url) {
    var w = window.open(url, 'ovnw-radio', 'width=420,height=220,menubar=no,toolbar=no,location=no,status=no');
    if (w) { w.focus(); return true; } return false;
  }
  function closeBar() { if (!bar) return; bar.hidden = true; d.getElementById('radio-frame').innerHTML = ''; d.body.classList.remove('radio-on'); }
  d.querySelectorAll('[data-radio-open]').forEach(function (b) {
    b.addEventListener('click', function () {
      if (!bar) return;
      var f = d.getElementById('radio-frame');
      if (!f.firstChild) {
        var i = d.createElement('iframe'); i.src = bar.dataset.src; i.allow = 'autoplay'; i.title = 'Radio'; i.setAttribute('scrolling', 'no');
        f.appendChild(i);
      }
      bar.hidden = false; d.body.classList.add('radio-on');
    });
  });
  d.querySelectorAll('[data-radio-popout]').forEach(function (b) {
    b.addEventListener('click', function () {
      var url = b.dataset.popup || (bar && bar.dataset.popup);
      if (url && popout(url)) closeBar();
    });
  });
  d.querySelectorAll('[data-radio-close]').forEach(function (b) { b.addEventListener('click', closeBar); });
})();
