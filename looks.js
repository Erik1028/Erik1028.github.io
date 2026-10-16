// The hub's looks: Modern (the page's own), Windows 95, Cyber and Terminal - the styles OrbitOverlay's watch can
// wear. The choice is remembered in this browser; a link ending in #look-95, #look-cyber or #look-terminal opens the
// page in that look (the head's inline script applies it before the first paint).
(function () {
  var root = document.documentElement, KEY = 'hub-look';
  var buttons = Array.prototype.slice.call(document.querySelectorAll('.looks button'));
  var tint = document.querySelector('meta[name="theme-color"]');
  var TINT = { modern: '#101116', '95': '#008080', cyber: '#0c0a0b', terminal: '#030805' };
  var clock = document.querySelector('.taskbar .clock'), timer = 0;
  function tick() { if (clock) clock.textContent = new Date().toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' }); }
  function set(look, save) {
    if (!/^(95|cyber|terminal)$/.test(look)) look = 'modern';
    if (look === 'modern') root.removeAttribute('data-look'); else root.setAttribute('data-look', look);
    buttons.forEach(function (b) { b.setAttribute('aria-pressed', String(b.getAttribute('data-look') === look)); });
    if (tint) tint.setAttribute('content', TINT[look]);
    clearInterval(timer);
    if (look === '95') { tick(); timer = setInterval(tick, 10000); }
    if (save) {
      try { localStorage.setItem(KEY, look); } catch (e) {}
      if (/^#look-/.test(location.hash)) history.replaceState(null, '', location.pathname + location.search);
    }
  }
  buttons.forEach(function (b) { b.addEventListener('click', function () { set(b.getAttribute('data-look'), true); }); });
  set(root.getAttribute('data-look') || 'modern', false);
})();
