/**
 * Campo de texto com lista suspensa filtrável. Sempre aceita texto livre: a lista só
 * sugere (ex.: marca/ano/modelo da tabela FIPE, mas um carro "maluco" pode ser digitado).
 *
 *   const combo = attachCombobox(input, {
 *       host: modal.el,                       // onde a lista flutua (position: fixed)
 *       getOptions: (query) => [{ value, label, hint, logo, group }],
 *       onPick: (option) => { ... },
 *       emptyText: (query) => 'Nada encontrado',
 *   });
 *   combo.open();  combo.close();  combo.refresh();
 *
 * Teclas: ↓/↑ escolhem, Enter confirma, Esc fecha. Abre ao focar/clicar no campo.
 */
import { html, render, setVar, toElement } from './dom.js';

const MAX_ITEMS = 120;
let uid = 0;

export function attachCombobox(input, { host, getOptions, onPick, emptyText = null, openOnFocus = true }) {
    const id = `combo-${++uid}`;
    const list = toElement(html`<div class="dropdown-list combo-list" role="listbox" id="${id}" hidden></div>`);
    host.append(list);
    input.setAttribute('role', 'combobox');
    input.setAttribute('aria-autocomplete', 'list');
    input.setAttribute('aria-controls', id);
    input.setAttribute('aria-expanded', 'false');

    let options = [];
    let active = -1;
    let filterQuery = '';

    function position() {
        if (list.hidden) return;
        const rect = input.getBoundingClientRect();
        const width = Math.max(rect.width, 280);
        setVar(list, '--combo-x', `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`);
        setVar(list, '--combo-w', `${width}px`);
        const below = window.innerHeight - rect.bottom;
        const height = list.offsetHeight;
        const up = below < height + 12 && rect.top > height + 12;
        setVar(list, '--combo-y', `${up ? rect.top - height - 4 : rect.bottom + 4}px`);
    }

    function draw() {
        const shown = options.slice(0, MAX_ITEMS);
        let lastGroup = null;
        const rows = [];
        shown.forEach((opt, i) => {
            if (opt.group && opt.group !== lastGroup) {
                rows.push(html`<div class="combo-group" role="presentation">${opt.group}</div>`);
            }
            lastGroup = opt.group || lastGroup;
            rows.push(html`<button type="button" class="dropdown-option combo-option${i === active ? ' is-active' : ''}" role="option" tabindex="-1" data-index="${i}" aria-selected="${i === active ? 'true' : 'false'}">
                ${opt.logo ? html`<span class="combo-logo"><img src="${opt.logo}" alt="" loading="lazy"></span>` : ''}
                <span class="combo-text"><span class="combo-label">${opt.label}</span>${opt.hint ? html`<span class="combo-hint">${opt.hint}</span>` : ''}</span>
            </button>`);
        });
        if (!shown.length) {
            const text = typeof emptyText === 'function' ? emptyText(filterQuery) : emptyText;
            if (!text) return close();
            rows.push(html`<div class="combo-empty">${text}</div>`);
        } else if (options.length > MAX_ITEMS) {
            rows.push(html`<div class="combo-empty">Mais ${options.length - MAX_ITEMS} opções: continue digitando para filtrar.</div>`);
        }
        render(list, html`${rows}`);
        list.hidden = false;
        input.setAttribute('aria-expanded', 'true');
        position();
    }

    function open({ all = false } = {}) {
        // all: lista completa (ao focar/clicar), com o valor atual marcado.
        filterQuery = all ? '' : input.value.trim();
        options = getOptions(filterQuery) || [];
        active = options.findIndex((o) => String(o.value).toLowerCase() === input.value.trim().toLowerCase());
        draw();
        if (active >= 0) list.querySelector(`[data-index="${active}"]`)?.scrollIntoView({ block: 'nearest' });
    }

    function close() {
        list.hidden = true;
        active = -1;
        input.setAttribute('aria-expanded', 'false');
    }

    function highlight(index) {
        const count = Math.min(options.length, MAX_ITEMS);
        if (!count) return;
        active = (index + count) % count;
        list.querySelectorAll('.combo-option').forEach((el) => {
            const on = Number(el.dataset.index) === active;
            el.classList.toggle('is-active', on);
            el.setAttribute('aria-selected', on ? 'true' : 'false');
            if (on) el.scrollIntoView({ block: 'nearest' });
        });
    }

    function pick(index) {
        const opt = options[index];
        close();
        if (!opt) return;
        input.value = opt.value;
        input.dataset.src = 'user';
        onPick?.(opt);
    }

    list.addEventListener('mousedown', (e) => {
        e.preventDefault(); // não tira o foco do campo
        const btn = e.target.closest('[data-index]');
        if (btn) pick(Number(btn.dataset.index));
    });
    input.addEventListener('focus', () => { if (openOnFocus) open({ all: true }); });
    input.addEventListener('click', () => { if (list.hidden) open({ all: true }); });
    input.addEventListener('input', (e) => { if (e.isTrusted) open(); });
    input.addEventListener('blur', () => setTimeout(() => { if (document.activeElement !== input) close(); }, 120));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowDown' && !e.altKey) {
            e.preventDefault();
            if (list.hidden) open({ all: true });
            else highlight(active + 1);
        } else if (e.key === 'ArrowUp' && !e.altKey && !list.hidden) {
            e.preventDefault();
            highlight(active - 1);
        } else if (e.key === 'Enter' && !list.hidden && active >= 0) {
            e.preventDefault();
            e.stopPropagation();
            pick(active);
        } else if (e.key === 'Escape' && !list.hidden) {
            e.preventDefault();
            e.stopPropagation();
            close();
        } else if (e.key === 'Tab') {
            close();
        }
    });
    const reposition = () => position();
    window.addEventListener('resize', reposition);
    host.addEventListener('scroll', reposition, { capture: true, passive: true });

    return {
        open,
        close,
        refresh: () => { if (!list.hidden) open(); },
        get isOpen() { return !list.hidden; },
    };
}
