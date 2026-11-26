/**
 * Cadastro de autopeças (fornecedores usados na cotação de peças da OS).
 * Cada autopeça tem nome, atendente e o desconto fixo que dá para a oficina.
 * Uso interno: nada daqui aparece na OS impressa, no orçamento ou na NF.
 *
 *   await loadAutopecas();                      // lista em cache (state 'autopecas')
 *   openAutopecasManager({ onSaved(autopeca) {}, startNew: true });
 */
import { api } from '../api.js';
import { state } from '../state.js';
import { html, render, on, $, busy } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal, confirmDialog } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { parseDecimal } from '../lib/format.js';

let modal = null;
let form = null;
let editingId = null;
let onSavedCb = null;

const PCT = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 2 });

/** "12%" / "12,5%" */
export function formatPct(value) {
    return `${PCT.format(Number(value) || 0)}%`;
}

export async function loadAutopecas({ force = false } = {}) {
    const cached = state.get('autopecas');
    if (cached && !force) return cached;
    try {
        const data = await api.get('/api/autopecas', { errorMessage: 'Não foi possível carregar as autopeças' });
        const list = data.autopecas || [];
        state.set('autopecas', list);
        return list;
    } catch (err) {
        toast(err.message, 'error');
        return cached || [];
    }
}

function rowsMarkup(list) {
    if (!list.length) {
        return html`<div class="empty-state">
            <span class="empty-state-icon">${icon('warehouse', 24)}</span>
            <div class="empty-state-title">Nenhuma autopeça cadastrada</div>
            <div class="empty-state-text">Cadastre as autopeças onde a oficina costuma cotar, com o desconto fixo de cada uma.</div>
        </div>`;
    }
    return html`<div class="table-wrap"><table class="table autopecas-table">
        <thead><tr><th>Autopeça</th><th>Atendente</th><th class="num">Desconto</th><th class="autopecas-col-tools"><span class="sr-only">Ações</span></th></tr></thead>
        <tbody>${list.map((a) => html`<tr data-id="${a.id}"${String(a.id) === String(editingId) ? html` class="is-editing"` : ''}>
            <td class="autopecas-name">${a.name}</td>
            <td class="text-muted">${a.attendant || '—'}</td>
            <td class="num"><span class="tag tag-success">${formatPct(a.discount_pct)}</span></td>
            <td class="autopecas-col-tools">
                <button type="button" class="btn btn-ghost btn-icon btn-sm" data-action="edit" aria-label="Editar ${a.name}" data-tooltip="Editar">${icon('pencil', 14)}</button>
                <button type="button" class="btn btn-danger-ghost btn-icon btn-sm" data-action="delete" aria-label="Excluir ${a.name}" data-tooltip="Excluir">${icon('trash-2', 14)}</button>
            </td>
        </tr>`)}</tbody>
    </table></div>`;
}

function renderList() {
    render($('[data-field="list"]', modal.body), rowsMarkup(state.get('autopecas') || []));
}

function resetForm() {
    editingId = null;
    form.reset();
    $('[data-field="form-title"]', form).textContent = 'Nova autopeça';
    $('[data-field="submit-label"]', form).textContent = 'Cadastrar';
    $('[data-action="cancel-edit"]', form).hidden = true;
    form.elements.name.classList.remove('is-invalid');
    form.elements.discount_pct.classList.remove('is-invalid');
}

function startEdit(id) {
    const a = (state.get('autopecas') || []).find((x) => String(x.id) === String(id));
    if (!a) return;
    editingId = a.id;
    form.elements.name.value = a.name;
    form.elements.attendant.value = a.attendant || '';
    form.elements.discount_pct.value = PCT.format(a.discount_pct || 0);
    $('[data-field="form-title"]', form).textContent = `Editando ${a.name}`;
    $('[data-field="submit-label"]', form).textContent = 'Salvar alterações';
    $('[data-action="cancel-edit"]', form).hidden = false;
    renderList();
    form.elements.name.focus();
}

async function submit(event) {
    event?.preventDefault();
    const name = form.elements.name.value.trim();
    const discountRaw = form.elements.discount_pct.value.replace('%', '').trim();
    const discount = discountRaw === '' ? 0 : parseDecimal(discountRaw);
    form.elements.name.classList.toggle('is-invalid', !name);
    const badPct = Number.isNaN(discount) || discount < 0 || discount > 100;
    form.elements.discount_pct.classList.toggle('is-invalid', badPct);
    if (!name) {
        toast('Informe o nome da autopeça.', 'error');
        form.elements.name.focus();
        return;
    }
    if (badPct) {
        toast('O desconto precisa ficar entre 0% e 100%.', 'error');
        form.elements.discount_pct.focus();
        return;
    }
    // busy() troca o conteúdo do botão (some o span do rótulo): devolve o botão ao normal
    // ANTES de mexer no formulário, senão resetForm() não acha o rótulo e quebra.
    const busyRestore = busy($('[data-action="submit"]', form), 'Salvando…');
    let restored = false;
    const restore = () => { if (!restored) { restored = true; busyRestore(); } };
    try {
        const body = { name, attendant: form.elements.attendant.value.trim(), discount_pct: discount };
        if (editingId) body.id = editingId;
        const data = await api.post('/api/autopecas', body, { errorMessage: 'Não foi possível salvar a autopeça' });
        const wasEditing = Boolean(editingId);
        restore();
        await loadAutopecas({ force: true });
        resetForm();
        renderList();
        toast(wasEditing ? `${data.autopeca.name} atualizada.` : `${data.autopeca.name} cadastrada.`, 'success');
        const cb = onSavedCb;
        if (!wasEditing && cb) {
            onSavedCb = null;
            modal.close();
            cb(data.autopeca);
        }
    } catch (err) {
        toast(err.message, 'error');
    } finally {
        restore();
    }
}

async function remove(id) {
    const a = (state.get('autopecas') || []).find((x) => String(x.id) === String(id));
    if (!a) return;
    const ok = await confirmDialog({
        title: `Excluir ${a.name}?`,
        message: 'Ela sai da lista de autopeças. Cotações já feitas continuam mostrando o nome e o desconto que tinham.',
        confirmLabel: 'Excluir',
        danger: true,
    });
    if (!ok) return;
    try {
        await api.del(`/api/autopecas/${encodeURIComponent(a.id)}`, { errorMessage: 'Não foi possível excluir a autopeça' });
        if (String(editingId) === String(a.id)) resetForm();
        await loadAutopecas({ force: true });
        renderList();
        toast(`${a.name} excluída.`, 'info');
    } catch (err) {
        toast(err.message, 'error');
    }
}

function build() {
    modal = createModal({
        id: 'autopecas',
        title: 'Autopeças cadastradas',
        subtitle: 'Usadas nas cotações de peças da OS · uso interno',
        icon: 'warehouse',
        size: 'md',
        body: html`
            <form class="autopecas-form card" novalidate autocomplete="off">
                <div class="card-header"><span class="card-title" data-field="form-title">Nova autopeça</span></div>
                <div class="card-body">
                    <div class="form-grid">
                        <label class="field col-5">
                            <span class="field-label">Nome da autopeça <span class="req">*</span></span>
                            <input class="input" name="name" maxlength="120" placeholder="Ex.: Autopeças Central">
                        </label>
                        <label class="field col-4">
                            <span class="field-label">Atendente</span>
                            <input class="input" name="attendant" maxlength="120" placeholder="Ex.: Marcos">
                        </label>
                        <label class="field col-3">
                            <span class="field-label">Desconto fixo (%)</span>
                            <input class="input input-num" name="discount_pct" inputmode="decimal" maxlength="6" placeholder="Ex.: 12">
                        </label>
                    </div>
                    <div class="autopecas-form-actions">
                        <button type="button" class="btn btn-ghost btn-sm" data-action="cancel-edit" hidden>Cancelar edição</button>
                        <button type="submit" class="btn btn-secondary btn-sm" data-action="submit">${icon('save', 14)} <span data-field="submit-label">Cadastrar</span></button>
                    </div>
                </div>
            </form>
            <div class="autopecas-list" data-field="list"></div>`,
        footer: html`<button type="button" class="btn btn-secondary" data-modal-close>Fechar</button>`,
        onClose: () => { onSavedCb = null; },
    });
    form = $('form', modal.body);
    form.addEventListener('submit', submit);
    on(modal.body, 'click', '[data-action]', (e, btn) => {
        const id = btn.closest('[data-id]')?.dataset.id;
        switch (btn.dataset.action) {
            case 'edit': startEdit(id); break;
            case 'delete': remove(id); break;
            case 'cancel-edit': resetForm(); renderList(); break;
            default: break;
        }
    });
}

export async function openAutopecasManager({ onSaved = null } = {}) {
    if (!modal) build();
    onSavedCb = onSaved;
    resetForm();
    render($('[data-field="list"]', modal.body), html`<div class="skeleton skeleton-block"></div>`);
    modal.open({ focus: false });
    setTimeout(() => form.elements.name.focus(), 40);
    await loadAutopecas({ force: true });
    renderList();
}
