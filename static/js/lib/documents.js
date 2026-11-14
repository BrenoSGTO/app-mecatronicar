/**
 * Ações de documento compartilhadas entre telas: abrir planilha no Excel e
 * gerar PDFs (orçamento/OS, checklist, histórico) em nova janela.
 */
import { api, openInNewTab, postToNewTab } from '../api.js';
import { toast } from '../ui/toast.js';

export async function openInExcel(filePath) {
    if (!filePath) {
        toast('Planilha não encontrada para esta visita.', 'error');
        return;
    }
    toast('Abrindo planilha no Excel…');
    try {
        await api.post('/api/open_file', { file_path: filePath }, { errorMessage: 'Erro ao abrir arquivo' });
        toast('Planilha aberta no Excel.', 'success');
    } catch (err) {
        toast(`Não foi possível abrir a planilha: ${err.message}`, 'error');
    }
}

export function openOrcamentoPdf(filePath) {
    if (!filePath) {
        toast('Nenhuma visita selecionada.', 'error');
        return;
    }
    openInNewTab('/api/orcamento_pdf', { file_path: filePath });
}

/** POST /api/checklist_pdf com config_json (abre nova janela). */
export function openChecklistPdf(config) {
    postToNewTab('/api/checklist_pdf', { config_json: JSON.stringify(config) });
}

/** POST /api/history_pdf com config_json (abre nova janela). */
export function openHistoryPdf(config) {
    postToNewTab('/api/history_pdf', { config_json: JSON.stringify(config) });
}
