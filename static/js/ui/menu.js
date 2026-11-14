/**
 * Menu suspenso ancorado em um botão (dropdown / popover).
 *
 *   const menu = createMenu(botao, {
 *       render: () => html`<button class="menu-item" data-action="x">...</button>`,
 *       onAction: (action, item, event) => {},   // clique em [data-action]
 *       align: 'end',                              // 'start' | 'end'
 *   });
 *
 * Fecha com Esc, clique fora, rolagem/redimensionamento ou ao clicar em um
 * [data-action] (a menos que o item tenha data-keep-open).
 * Setas ↑/↓ navegam entre .menu-item.
 */
import { render, toElement, html } from './dom.js';

let openMenu = null;

function currentZoom() {
    const z = parseFloat(getComputedStyle(document.documentElement).zoom);
    return Number.isFinite(z) && z > 0 ? z : 1;
}

window.addEventListener('keydown', (event) => {
    if (!openMenu) return;
    if (event.key === 'Escape') {
        event.preventDefault();
        event.stopPropagation();
        openMenu.close(true);
    } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        const items = [...openMenu.el.querySelectorAll('.menu-item:not([disabled])')];
        if (!items.length) return;
        event.preventDefault();
        const idx = items.indexOf(document.activeElement);
        const next = event.key === 'ArrowDown' ? (idx + 1) % items.length : (idx - 1 + items.length) % items.length;
        items[next].focus();
    }
}, true);

document.addEventListener('pointerdown', (event) => {
    if (!openMenu) return;
    if (openMenu.el.contains(event.target) || openMenu.trigger.contains(event.target)) return;
    openMenu.close();
}, true);

window.addEventListener('resize', () => openMenu?.close());

export function createMenu(trigger, { render: renderContent, onAction, align = 'end', className = '', onOpen } = {}) {
    const el = toElement(html`<div class="menu ${className}" role="menu" hidden></div>`);
    document.body.append(el);
    trigger.setAttribute('aria-haspopup', 'menu');
    trigger.setAttribute('aria-expanded', 'false');

    function position() {
        const zoom = currentZoom();
        const rect = trigger.getBoundingClientRect();
        const top = (rect.bottom + 6) / zoom;
        el.style.top = `${top}px`;
        if (align === 'end') {
            el.style.left = '';
            el.style.right = `${Math.max(8, (window.innerWidth - rect.right) / zoom)}px`;
        } else {
            el.style.right = '';
            el.style.left = `${Math.max(8, rect.left / zoom)}px`;
        }
    }

    const menu = {
        el,
        trigger,
        isOpen: () => openMenu === menu,
        refresh() {
            if (renderContent) render(el, renderContent());
        },
        open() {
            if (openMenu && openMenu !== menu) openMenu.close();
            menu.refresh();
            el.hidden = false;
            position();
            openMenu = menu;
            trigger.setAttribute('aria-expanded', 'true');
            requestAnimationFrame(() => el.classList.add('is-open'));
            onOpen?.(menu);
            const first = el.querySelector('.menu-item:not([disabled])');
            if (first) setTimeout(() => first.focus({ preventScroll: true }), 20);
        },
        close(restoreFocus = false) {
            if (openMenu !== menu) return;
            openMenu = null;
            el.classList.remove('is-open');
            el.hidden = true;
            trigger.setAttribute('aria-expanded', 'false');
            if (restoreFocus) trigger.focus();
        },
        toggle() {
            if (menu.isOpen()) menu.close();
            else menu.open();
        },
    };

    trigger.addEventListener('click', (event) => {
        event.preventDefault();
        menu.toggle();
    });

    el.addEventListener('click', (event) => {
        const item = event.target.closest('[data-action]');
        if (!item || !el.contains(item)) return;
        const keepOpen = item.hasAttribute('data-keep-open');
        onAction?.(item.dataset.action, item, event);
        if (!keepOpen) menu.close(true);
    });

    return menu;
}
