/**
 * Verificação e instalação de atualizações (GET /api/check_update,
 * POST /api/apply_update). Mesmo fluxo da v2, com o modal do design system.
 */
import { html, setVar, setText } from '../ui/dom.js';
import { icon } from '../ui/icon.js';
import { createModal } from '../ui/modal.js';
import { toast } from '../ui/toast.js';
import { api } from '../api.js';

let modal = null;
let pending = null;

function build() {
    modal = createModal({
        id: 'updates',
        title: 'Atualizações do MecatroniCar',
        icon: 'download',
        size: 'sm',
        body: html`
            <div class="update-state" data-state="checking">
                <div class="empty-state empty-state-compact">
                    <span class="empty-state-icon">${icon('loader-circle', 20, 'icon-spin')}</span>
                    <div class="empty-state-title">Verificando novas versões…</div>
                    <div class="empty-state-text">Consultando o repositório oficial no GitHub.</div>
                </div>
            </div>
            <div class="update-state" data-state="uptodate" hidden>
                <div class="empty-state empty-state-compact empty-state-success">
                    <span class="empty-state-icon">${icon('circle-check', 20)}</span>
                    <div class="empty-state-title">O sistema está atualizado</div>
                    <div class="empty-state-text">Você está usando a versão mais recente (<strong data-field="current"></strong>).</div>
                </div>
            </div>
            <div class="update-state stack" data-state="available" hidden>
                <div class="callout callout-warning">
                    ${icon('sparkles', 16)}
                    <div>
                        <div class="callout-title">Nova versão disponível: <span data-field="latest"></span></div>
                        <div class="text-muted">Versão instalada: <span data-field="installed"></span></div>
                    </div>
                </div>
                <div class="stack stack-2">
                    <div class="eyebrow">O que há de novo</div>
                    <div class="preformatted update-notes" data-field="notes"></div>
                </div>
                <div class="stack stack-2" data-field="progress" hidden>
                    <div class="row row-between text-sm">
                        <span data-field="progress-status">Baixando atualização…</span>
                        <span class="num fw-semibold" data-field="progress-percent">0%</span>
                    </div>
                    <div class="progress"><div class="progress-bar" data-field="progress-bar"></div></div>
                </div>
            </div>`,
        footer: html`
            <button type="button" class="btn btn-secondary" data-modal-close data-field="cancel">Fechar</button>
            <button type="button" class="btn btn-primary" data-field="apply" hidden>${icon('download', 16)} Atualizar agora</button>`,
    });

    modal.footer.querySelector('[data-field="apply"]').addEventListener('click', applyUpdate);
}

function field(name) {
    return modal.el.querySelector(`[data-field="${name}"]`);
}

function showState(name) {
    for (const el of modal.el.querySelectorAll('.update-state')) {
        el.hidden = el.dataset.state !== name;
    }
}

function setProgress(pct, status) {
    field('progress').hidden = false;
    setVar(field('progress-bar'), '--value', `${pct}%`);
    setText(field('progress-percent'), `${pct}%`);
    if (status) setText(field('progress-status'), status);
}

export async function openUpdatesModal() {
    if (!modal) build();
    pending = null;
    showState('checking');
    field('apply').hidden = true;
    field('apply').disabled = false;
    field('cancel').disabled = false;
    setText(field('cancel'), 'Fechar');
    field('progress').hidden = true;
    modal.open();

    try {
        const data = await api.get('/api/check_update', { timeout: 30000 });
        pending = data;
        if (data.update_available) {
            setText(field('latest'), `v${data.latest_version}`);
            setText(field('installed'), `v${data.current_version}`);
            setText(field('notes'), data.release_notes || 'Melhorias de desempenho e correções gerais.');
            showState('available');
            field('apply').hidden = false;
            setText(field('cancel'), 'Depois');
        } else {
            setText(field('current'), `v${data.current_version || '?'}`);
            showState('uptodate');
        }
    } catch (err) {
        setText(field('current'), 'sem conexão com a internet');
        showState('uptodate');
        toast('Não foi possível verificar atualizações agora.', 'error');
    }
}

async function applyUpdate() {
    if (!pending || !pending.download_url) {
        toast('Endereço da atualização indisponível.', 'error');
        return;
    }
    const applyBtn = field('apply');
    const cancelBtn = field('cancel');
    applyBtn.disabled = true;
    cancelBtn.disabled = true;
    setProgress(30, 'Baixando a nova versão do GitHub…');

    try {
        const data = await api.post('/api/apply_update', { download_url: pending.download_url }, { timeout: 300000, allowFailure: true });
        if (data.success) {
            setProgress(80, 'Instalando a atualização…');
            setTimeout(() => {
                setProgress(100, 'Reiniciando o sistema…');
                toast('Atualização instalada. O MecatroniCar está reiniciando…', 'success');
                setTimeout(() => window.location.reload(), 4000);
            }, 1500);
        } else {
            toast(`Erro na atualização: ${data.error || 'falha desconhecida'}`, 'error');
            applyBtn.disabled = false;
            cancelBtn.disabled = false;
        }
    } catch {
        // O servidor reinicia durante a instalação e a conexão cai: comportamento esperado (v2).
        setProgress(100, 'Reiniciando o sistema…');
        setTimeout(() => window.location.reload(), 4000);
    }
}

export function isUpdatesModalOpen() {
    return Boolean(modal && modal.isOpen());
}

