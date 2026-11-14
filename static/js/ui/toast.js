/**
 * Notificações curtas (canto inferior direito).
 *   toast('Ficha salva.', 'success');   // tipos: 'info' (padrão) | 'success' | 'error'
 *   toast('Ficha salva.', 'success', { actions: [{ label: 'Abrir ficha', onClick: () => {} }] });
 */
import { h } from './dom.js';
import { iconEl } from './icon.js';

const ICONS = { info: 'info', success: 'circle-check', error: 'circle-alert' };
const MAX_VISIBLE = 3;

function region() {
    let el = document.getElementById('toast-region');
    if (!el) {
        el = h('div', { id: 'toast-region', class: 'toast-region', 'aria-live': 'polite', role: 'status' });
        document.body.append(el);
    }
    return el;
}

function dismiss(el) {
    if (!el || el.dataset.closing) return;
    el.dataset.closing = '1';
    el.classList.remove('is-visible');
    setTimeout(() => el.remove(), 200);
}

export function toast(message, type = 'info', { duration, actions } = {}) {
    const kind = ICONS[type] ? type : 'info';
    const root = region();
    const text = h('span', { class: 'toast-message', text: String(message ?? '') });
    const buttons = (actions || []).map((action) => h('button', {
        type: 'button',
        class: 'toast-action',
        text: action.label,
        onclick: (event) => {
            event.stopPropagation();
            dismiss(el);
            action.onClick?.();
        },
    }));
    const el = h('div', { class: `toast toast-${kind}`, role: kind === 'error' ? 'alert' : 'status' },
        iconEl(ICONS[kind], 16),
        buttons.length
            ? h('div', { class: 'toast-content' }, text, h('div', { class: 'toast-actions' }, ...buttons))
            : text);
    el.addEventListener('click', () => dismiss(el));
    root.append(el);

    const items = root.querySelectorAll('.toast:not([data-closing])');
    if (items.length > MAX_VISIBLE) dismiss(items[0]);

    requestAnimationFrame(() => el.classList.add('is-visible'));
    const ms = duration ?? (kind === 'error' ? 6000 : buttons.length ? 9000 : 3200);
    setTimeout(() => dismiss(el), ms);
    return el;
}
