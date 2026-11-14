/**
 * Modais acessíveis: pilha (Esc fecha o de cima), foco preso no diálogo,
 * foco devolvido ao fechar, clique no fundo fecha (opcional).
 *
 *   const modal = createModal({
 *       id: 'patio', title: 'Gerenciar pátio', icon: 'warehouse', size: 'md',
 *       body: html`...`, footer: html`<button class="btn btn-secondary" data-modal-close>Cancelar</button> ...`,
 *       onClose: () => {},
 *   });
 *   modal.open();  modal.close();  modal.setTitle('...');  modal.body / modal.footer (elementos)
 *
 * Tamanhos: 'sm' (420) | 'md' (640) | 'lg' (820) | 'xl' (1160).
 * Qualquer elemento com [data-modal-close] dentro do modal fecha o modal.
 */
import { html, render, toElement } from './dom.js';
import { icon } from './icon.js';

const stack = [];
let uid = 0;

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function modalRoot() {
    let root = document.getElementById('modal-root');
    if (!root) {
        root = document.createElement('div');
        root.id = 'modal-root';
        document.body.append(root);
    }
    return root;
}

function syncBody() {
    document.body.classList.toggle('has-modal', stack.length > 0);
}

document.addEventListener('keydown', (event) => {
    const top = stack[stack.length - 1];
    if (!top) return;
    if (event.key === 'Escape') {
        if (event.defaultPrevented) return;
        event.preventDefault();
        top.close();
        return;
    }
    if (event.key === 'Tab') {
        const focusables = [...top.dialog.querySelectorAll(FOCUSABLE)].filter((el) => el.offsetParent !== null || el === document.activeElement);
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        } else if (!top.dialog.contains(document.activeElement)) {
            event.preventDefault();
            first.focus();
        }
    }
});

export function createModal({
    id,
    title = '',
    subtitle = '',
    icon: iconName = '',
    size = 'md',
    body = '',
    footer = null,
    closeOnBackdrop = true,
    bodyClass = '',
    onClose = null,
    onOpen = null,
} = {}) {
    const modalId = `modal-${id || ++uid}`;
    const titleId = `${modalId}-title`;

    const el = toElement(html`<div class="modal modal-${size}" id="${modalId}" hidden>
        <div class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="${titleId}">
            <header class="modal-header">
                ${iconName ? html`<span class="modal-header-icon">${icon(iconName, 18)}</span>` : ''}
                <div class="modal-heading">
                    <h2 class="modal-title" id="${titleId}"></h2>
                    <p class="modal-subtitle" hidden></p>
                </div>
                <button type="button" class="btn btn-ghost btn-icon btn-sm modal-close" data-modal-close aria-label="Fechar (Esc)" data-tooltip="Fechar (Esc)" data-tooltip-pos="bottom">${icon('x', 18)}</button>
            </header>
            <div class="modal-body ${bodyClass}"></div>
            <footer class="modal-footer" hidden></footer>
        </div>
    </div>`);

    const dialog = el.querySelector('.modal-dialog');
    const titleEl = el.querySelector('.modal-title');
    const subtitleEl = el.querySelector('.modal-subtitle');
    const bodyEl = el.querySelector('.modal-body');
    const footerEl = el.querySelector('.modal-footer');
    let lastFocus = null;
    let closeTimer = null;

    const api = {
        el,
        dialog,
        body: bodyEl,
        footer: footerEl,
        isOpen: () => stack.includes(api),
        setTitle(text) {
            titleEl.textContent = text || '';
        },
        setSubtitle(text) {
            subtitleEl.textContent = text || '';
            subtitleEl.hidden = !text;
        },
        setBody(content) {
            render(bodyEl, content);
        },
        setFooter(content) {
            render(footerEl, content);
            footerEl.hidden = !content;
        },
        open({ focus = true } = {}) {
            if (api.isOpen()) return api;
            clearTimeout(closeTimer);
            lastFocus = document.activeElement;
            el.hidden = false;
            stack.push(api);
            syncBody();
            void el.offsetWidth; // força reflow para a transição
            el.classList.add('is-open');
            if (focus) {
                const target = dialog.querySelector('[autofocus]') || bodyEl.querySelector(FOCUSABLE) || dialog.querySelector(FOCUSABLE);
                if (target) setTimeout(() => target.focus({ preventScroll: true }), 30);
            }
            onOpen?.(api);
            return api;
        },
        close() {
            const idx = stack.indexOf(api);
            if (idx === -1) return api;
            stack.splice(idx, 1);
            syncBody();
            el.classList.remove('is-open');
            closeTimer = setTimeout(() => {
                el.hidden = true;
            }, 160);
            if (lastFocus && typeof lastFocus.focus === 'function' && document.contains(lastFocus)) {
                lastFocus.focus({ preventScroll: true });
            }
            onClose?.(api);
            return api;
        },
    };

    api.setTitle(title);
    api.setSubtitle(subtitle);
    api.setBody(body);
    if (footer) api.setFooter(footer);

    el.addEventListener('click', (event) => {
        if (event.target.closest('[data-modal-close]')) {
            api.close();
        } else if (closeOnBackdrop && event.target === el) {
            api.close();
        }
    });

    modalRoot().append(el);
    return api;
}

/**
 * Confirmação (substitui window.confirm).
 *   if (await confirmDialog({ title: 'Remover do pátio?', message: '...', confirmLabel: 'Remover', danger: true })) ...
 */
export function confirmDialog({ title = 'Confirmar', message = '', confirmLabel = 'Confirmar', cancelLabel = 'Cancelar', danger = false } = {}) {
    return new Promise((resolve) => {
        let result = false;
        const modal = createModal({
            title,
            size: 'sm',
            icon: danger ? 'triangle-alert' : 'circle-help',
            body: html`<p class="text-muted pre-wrap">${message}</p>`,
            footer: html`
                <button type="button" class="btn btn-secondary" data-modal-close>${cancelLabel}</button>
                <button type="button" class="btn ${danger ? 'btn-danger' : 'btn-primary'}" data-confirm autofocus>${confirmLabel}</button>`,
            onClose: () => {
                resolve(result);
                setTimeout(() => modal.el.remove(), 250);
            },
        });
        modal.footer.querySelector('[data-confirm]').addEventListener('click', () => {
            result = true;
            modal.close();
        });
        modal.open();
    });
}

/** Fecha todos os modais abertos (ex.: ao trocar de tela). */
export function closeAllModals() {
    [...stack].reverse().forEach((m) => m.close());
}
