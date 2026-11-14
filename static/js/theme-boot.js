/*
 * Boot síncrono (script clássico no <head>): aplica tema, zoom e estado da
 * sidebar ANTES da primeira pintura, a partir do último valor salvo no
 * navegador. O main.js depois sincroniza com o config do servidor.
 * Não use ES modules aqui (precisa rodar bloqueando o parse).
 */
(function () {
    var root = document.documentElement;
    function read(key) {
        try { return localStorage.getItem(key); } catch (e) { return null; }
    }

    // Tema: 'light' | 'dark' | 'auto' (auto segue o Windows)
    var pref = read('mc.theme') || 'light';
    var dark = pref === 'dark' || (pref === 'auto' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    root.setAttribute('data-theme', dark ? 'dark' : 'light');
    root.setAttribute('data-theme-pref', pref);

    // Zoom da interface (50–150%)
    var zoom = parseInt(read('mecatronicar_zoom') || '100', 10);
    if (isNaN(zoom) || zoom < 50 || zoom > 150) zoom = 100;
    root.style.setProperty('--ui-zoom', String(zoom / 100));

    // Sidebar: 'auto' recolhe em telas < 1440px
    var sb = read('mc.sidebar') || 'auto';
    var narrow = window.matchMedia && window.matchMedia('(max-width: 1439.98px)').matches;
    if (sb === 'collapsed' || (sb === 'auto' && narrow)) root.classList.add('sb-collapsed');
}());
