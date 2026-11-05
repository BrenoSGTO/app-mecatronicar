// MecatroniCar - Frontend App Logic
document.addEventListener('DOMContentLoaded', () => {
    // State
    let currentConfig = {};
    let allCars = [];
    let currentCarHistory = null;
    let searchDebounceTimer = null;
    let pendingUpdateData = null;

    // DOM Elements
    const appVersionBadge = document.getElementById('app-version-badge');
    const currentFolderText = document.getElementById('current-folder-text');
    const btnChangeFolder = document.getElementById('btn-change-folder');
    const btnReindex = document.getElementById('btn-reindex');
    const btnCheckUpdates = document.getElementById('btn-check-updates');
    
    const searchInput = document.getElementById('search-input');
    const btnClearSearch = document.getElementById('btn-clear-search');
    
    const welcomeSection = document.getElementById('welcome-section');
    const searchResultsSection = document.getElementById('search-results-section');
    const searchCardsGrid = document.getElementById('search-cards-grid');
    const searchResultsTitle = document.getElementById('search-results-title');
    const searchResultsCount = document.getElementById('search-results-count');
    
    const vehicleHistorySection = document.getElementById('vehicle-history-section');
    const visitsListContainer = document.getElementById('visits-list-container');
    
    // Vehicle banner elements
    const detailPlate = document.getElementById('detail-plate');
    const detailOwnerName = document.getElementById('detail-owner-name');
    const detailPhone = document.getElementById('detail-phone');
    const detailCarModel = document.getElementById('detail-car-model');
    const detailCarYear = document.getElementById('detail-car-year');
    const detailCarColor = document.getElementById('detail-car-color');
    const detailCarFuel = document.getElementById('detail-car-fuel');
    const detailCarChassis = document.getElementById('detail-car-chassis');
    
    const metricTotalVisits = document.getElementById('metric-total-visits');
    const metricLastKm = document.getElementById('metric-last-km');
    const metricKmDiff = document.getElementById('metric-km-diff');
    
    const btnPrint = document.getElementById('btn-print');
    const btnPrintNoPrices = document.getElementById('btn-print-no-prices');
    
    // Comment Modal elements
    const commentModal = document.getElementById('comment-modal');
    const modalItemTitle = document.getElementById('modal-item-title');
    const modalItemSubtitle = document.getElementById('modal-item-subtitle');
    const modalCommentText = document.getElementById('modal-comment-text');
    const modalCloseBtn = document.getElementById('modal-close-btn');
    const modalDismissBtn = document.getElementById('modal-dismiss-btn');
    const modalCopyBtn = document.getElementById('modal-copy-btn');
    
    // Update Modal elements
    const updateModal = document.getElementById('update-modal');
    const updateModalCloseBtn = document.getElementById('update-modal-close-btn');
    const updateCancelBtn = document.getElementById('update-cancel-btn');
    const updateApplyBtn = document.getElementById('update-apply-btn');
    const updateCheckingState = document.getElementById('update-checking-state');
    const updateUptodateState = document.getElementById('update-uptodate-state');
    const updateAvailableState = document.getElementById('update-available-state');
    const uptodateVersion = document.getElementById('uptodate-version');
    const newVersionTag = document.getElementById('new-version-tag');
    const currentVersionTag = document.getElementById('current-version-tag');
    const updateNotesBox = document.getElementById('update-notes-box');
    const updateProgressContainer = document.getElementById('update-progress-container');
    const updateProgressBar = document.getElementById('update-progress-bar');
    const updateProgressStatus = document.getElementById('update-progress-status');
    const updateProgressPercent = document.getElementById('update-progress-percent');

    const toast = document.getElementById('toast');

    // Initialization
    loadInitialData();

    // Event Listeners
    btnChangeFolder.addEventListener('click', handleSelectFolder);
    btnReindex.addEventListener('click', handleReindex);
    btnCheckUpdates.addEventListener('click', handleCheckUpdatesManual);
    
    searchInput.addEventListener('input', (e) => {
        const val = e.target.value.trim();
        btnClearSearch.style.display = val ? 'flex' : 'none';
        
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            performSearch(val);
        }, 150);
    });
    
    btnClearSearch.addEventListener('click', () => {
        searchInput.value = '';
        btnClearSearch.style.display = 'none';
        searchInput.focus();
        resetToWelcome();
    });

    // Print full (with prices)
    btnPrint.addEventListener('click', () => {
        document.body.classList.remove('print-no-prices');
        window.print();
    });

    // Print without prices
    if (btnPrintNoPrices) {
        btnPrintNoPrices.addEventListener('click', () => {
            document.body.classList.add('print-no-prices');
            window.print();
            setTimeout(() => {
                document.body.classList.remove('print-no-prices');
            }, 1000);
        });
    }

    modalCloseBtn.addEventListener('click', closeModal);
    modalDismissBtn.addEventListener('click', closeModal);
    commentModal.addEventListener('click', (e) => {
        if (e.target === commentModal) closeModal();
    });

    modalCopyBtn.addEventListener('click', () => {
        const text = modalCommentText.textContent;
        navigator.clipboard.writeText(text).then(() => {
            showToast('✓ Texto copiado para a área de transferência!');
            modalCopyBtn.textContent = '✓ Copiado!';
            setTimeout(() => {
                modalCopyBtn.textContent = '📋 Copiar Texto';
            }, 2000);
        }).catch(() => {
            showToast('Erro ao copiar texto');
        });
    });

    // Update modal listeners
    updateModalCloseBtn.addEventListener('click', closeUpdateModal);
    updateCancelBtn.addEventListener('click', closeUpdateModal);
    updateModal.addEventListener('click', (e) => {
        if (e.target === updateModal) closeUpdateModal();
    });
    updateApplyBtn.addEventListener('click', handleApplyUpdate);

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (commentModal.style.display !== 'none') closeModal();
            if (updateModal.style.display !== 'none') closeUpdateModal();
        }
    });

    // API Functions
    async function loadInitialData() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            currentConfig = data.config || {};
            if (data.version && appVersionBadge) {
                appVersionBadge.textContent = `v${data.version}`;
            }
            updateFolderUI(currentConfig.spreadsheet_folder);
            
            await loadCarsList();
        } catch (err) {
            console.error('Erro carregando config inicial:', err);
            showToast('Erro ao conectar com o servidor local.');
        }
    }

    async function loadCarsList() {
        try {
            const res = await fetch('/api/cars');
            const data = await res.json();
            allCars = data.cars || [];
        } catch (err) {
            console.error('Erro carregando veículos:', err);
        }
    }

    async function handleSelectFolder() {
        btnChangeFolder.disabled = true;
        btnChangeFolder.textContent = '⏳ Escolhendo...';
        showToast('Selecione a pasta na janela do Windows...');
        
        try {
            const res = await fetch('/api/select_folder', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                updateFolderUI(data.folder);
                showToast(`Pasta configurada com sucesso! ${data.stats.total_files} planilhas indexadas.`);
                await loadCarsList();
                resetToWelcome();
            }
        } catch (err) {
            console.error('Erro escolhendo pasta:', err);
            showToast('Erro ao selecionar pasta.');
        } finally {
            btnChangeFolder.disabled = false;
            btnChangeFolder.textContent = '📂 Alterar Pasta';
        }
    }

    async function handleReindex() {
        btnReindex.disabled = true;
        btnReindex.textContent = '⏳ Atualizando...';
        showToast('Atualizando lista de planilhas...');
        
        try {
            const res = await fetch('/api/reindex', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                showToast(`✓ Atualizado! Total de ${data.stats.total_files} arquivos.`);
                await loadCarsList();
                if (searchInput.value.trim()) {
                    performSearch(searchInput.value.trim());
                }
            } else {
                showToast(data.error || 'Erro ao reindexar');
            }
        } catch (err) {
            console.error('Erro reindexando:', err);
            showToast('Erro ao atualizar planilhas.');
        } finally {
            btnReindex.disabled = false;
            btnReindex.textContent = '🔄 Atualizar Lista';
        }
    }

    async function openInExcel(filePath) {
        showToast('Abrindo arquivo no Excel...');
        try {
            const res = await fetch('/api/open_file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ file_path: filePath })
            });
            const data = await res.json();
            if (data.success) {
                showToast('✓ Planilha aberta no Excel com sucesso!');
            } else {
                showToast(`Erro ao abrir: ${data.error}`);
            }
        } catch (err) {
            showToast('Falha na comunicação ao abrir o arquivo');
        }
    }

    async function selectVehicleByPlate(plate) {
        showToast(`Carregando histórico do veículo ${plate}...`);
        try {
            const res = await fetch(`/api/car_history/${encodeURIComponent(plate)}`);
            const data = await res.json();
            if (data.visits && data.visits.length > 0) {
                currentCarHistory = data;
                renderVehicleHistory(data);
            } else {
                showToast(`Nenhuma visita encontrada para a placa ${plate}`);
            }
        } catch (err) {
            console.error('Erro carregando histórico:', err);
            showToast('Erro ao buscar visitas do carro');
        }
    }

    async function performSearch(query) {
        if (!query) {
            resetToWelcome();
            return;
        }

        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await res.json();
            const results = data.results || [];

            const uniquePlates = [...new Set(results.map(r => r.plate_clean).filter(Boolean))];

            if (results.length === 0) {
                searchResultsTitle.textContent = `Nenhum resultado para "${query}"`;
                searchResultsCount.textContent = '0 encontrados';
                searchCardsGrid.innerHTML = `
                    <div style="grid-column: 1 / -1; padding: 30px; text-align: center; color: var(--text-muted); background: white; border-radius: 10px; border: 1px dashed var(--border-color);">
                        Nenhum arquivo encontrado com a placa ou cliente informado.
                    </div>
                `;
                searchResultsSection.style.display = 'block';
                vehicleHistorySection.style.display = 'none';
                welcomeSection.style.display = 'none';
            } else if (uniquePlates.length === 1) {
                await selectVehicleByPlate(uniquePlates[0]);
            } else {
                renderSearchResultsGrid(results, query);
            }
        } catch (err) {
            console.error('Erro na busca:', err);
        }
    }

    // Auto-update functions
    async function handleCheckUpdatesManual() {
        updateModal.style.display = 'flex';
        updateCheckingState.style.display = 'block';
        updateUptodateState.style.display = 'none';
        updateAvailableState.style.display = 'none';
        updateApplyBtn.style.display = 'none';
        updateCancelBtn.textContent = 'Fechar';

        try {
            const res = await fetch('/api/check_update');
            const data = await res.json();
            pendingUpdateData = data;

            updateCheckingState.style.display = 'none';

            if (data.update_available) {
                newVersionTag.textContent = `v${data.latest_version}`;
                currentVersionTag.textContent = `v${data.current_version}`;
                updateNotesBox.textContent = data.release_notes || 'Melhorias de desempenho e correções gerais.';
                updateAvailableState.style.display = 'block';
                updateProgressContainer.style.display = 'none';
                updateApplyBtn.style.display = 'inline-flex';
                updateCancelBtn.textContent = 'Depois';
            } else {
                uptodateVersion.textContent = `v${data.current_version || '1.0.0'}`;
                updateUptodateState.style.display = 'block';
            }
        } catch (err) {
            updateCheckingState.style.display = 'none';
            uptodateVersion.textContent = 'v1.0.0 (sem conexão)';
            updateUptodateState.style.display = 'block';
            showToast('Não foi possível verificar atualizações no momento.');
        }
    }

    async function handleApplyUpdate() {
        if (!pendingUpdateData || !pendingUpdateData.download_url) {
            showToast('URL da atualização indisponível.');
            return;
        }

        updateApplyBtn.disabled = true;
        updateCancelBtn.disabled = true;
        updateProgressContainer.style.display = 'block';
        updateProgressBar.style.width = '30%';
        updateProgressPercent.textContent = '30%';
        updateProgressStatus.textContent = 'Baixando nova versão do GitHub...';

        try {
            const res = await fetch('/api/apply_update', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ download_url: pendingUpdateData.download_url })
            });
            const data = await res.json();
            if (data.success) {
                updateProgressBar.style.width = '80%';
                updateProgressPercent.textContent = '80%';
                updateProgressStatus.textContent = 'Instalando atualização...';

                setTimeout(() => {
                    updateProgressBar.style.width = '100%';
                    updateProgressPercent.textContent = '100%';
                    updateProgressStatus.textContent = 'Reiniciando o sistema...';
                    showToast('✓ Atualização instalada! O MecatroniCar está reiniciando...');
                    setTimeout(() => {
                        window.location.reload();
                    }, 4000);
                }, 1500);
            } else {
                showToast(`Erro na atualização: ${data.error}`);
                updateApplyBtn.disabled = false;
                updateCancelBtn.disabled = false;
            }
        } catch (err) {
            updateProgressBar.style.width = '100%';
            updateProgressStatus.textContent = 'Reiniciando o sistema...';
            setTimeout(() => {
                window.location.reload();
            }, 4000);
        }
    }

    function closeUpdateModal() {
        updateModal.style.display = 'none';
    }

    // UI Renderers
    function updateFolderUI(folderPath) {
        if (folderPath) {
            currentFolderText.textContent = folderPath;
            currentFolderText.title = folderPath;
        } else {
            currentFolderText.textContent = "Nenhuma pasta selecionada (Clique em 'Alterar Pasta')";
        }
    }

    function renderSearchResultsGrid(results, query) {
        searchResultsTitle.textContent = `Resultados para "${query}"`;
        searchResultsCount.textContent = `${results.length} visitas encontradas`;
        searchCardsGrid.innerHTML = '';

        results.forEach(item => {
            const card = document.createElement('div');
            card.className = 'search-card';
            card.innerHTML = `
                <div class="search-card-top">
                    <span class="search-card-plate">🚗 ${item.plate_display || item.plate}</span>
                    <span class="search-card-date">📅 ${item.entry_date || 'Sem data'}</span>
                </div>
                <div class="search-card-owner">👤 ${item.client_name || 'Cliente não identificado'}</div>
                <div class="search-card-car">${item.car_model || ''} ${item.car_year ? '(' + item.car_year + ')' : ''}</div>
                ${item.odometer ? `<div style="font-size: 12px; color: #475569;">⏱️ Hodômetro: <strong>${formatKm(item.odometer)}</strong></div>` : ''}
                ${item.complaint ? `<div class="search-card-complaint" title="${escapeHtml(item.complaint)}">${escapeHtml(item.complaint)}</div>` : ''}
            `;
            card.addEventListener('click', () => {
                selectVehicleByPlate(item.plate_clean || item.plate);
            });
            searchCardsGrid.appendChild(card);
        });

        searchResultsSection.style.display = 'block';
        vehicleHistorySection.style.display = 'none';
        welcomeSection.style.display = 'none';
    }

    function renderVehicleHistory(data) {
        const visits = data.visits || [];
        if (visits.length === 0) return;

        const latest = visits[0];
        const details = latest.details || {};

        detailPlate.textContent = latest.plate_display || latest.plate || 'SEM PLACA';
        detailOwnerName.textContent = latest.client_name || 'Cliente';
        detailPhone.textContent = details.phone ? `📞 ${details.phone}` : '';
        detailPhone.style.display = details.phone ? 'inline-block' : 'none';

        detailCarModel.textContent = latest.car_model || 'Veículo';
        detailCarYear.textContent = latest.car_year ? `Ano: ${latest.car_year}` : '';
        detailCarYear.style.display = latest.car_year ? 'inline-block' : 'none';

        detailCarColor.textContent = latest.car_color ? `Cor: ${latest.car_color}` : '';
        detailCarColor.style.display = latest.car_color ? 'inline-block' : 'none';

        detailCarFuel.textContent = details.car_fuel ? `Combustível: ${details.car_fuel}` : '';
        detailCarFuel.style.display = details.car_fuel ? 'inline-block' : 'none';

        detailCarChassis.textContent = details.car_chassis ? `Chassi: ${details.car_chassis}` : '';
        detailCarChassis.style.display = details.car_chassis ? 'inline-block' : 'none';

        metricTotalVisits.textContent = visits.length;
        
        const validKms = visits.map(v => v.odometer_int).filter(k => k > 0);
        if (validKms.length > 0) {
            const maxKm = Math.max(...validKms);
            const minKm = Math.min(...validKms);
            metricLastKm.textContent = `${maxKm.toLocaleString('pt-BR')} km`;
            
            if (validKms.length > 1 && maxKm > minKm) {
                const diff = maxKm - minKm;
                metricKmDiff.textContent = `+${diff.toLocaleString('pt-BR')} km`;
            } else {
                metricKmDiff.textContent = '1 registro';
            }
        } else {
            metricLastKm.textContent = latest.odometer ? `${latest.odometer} km` : '- km';
            metricKmDiff.textContent = '-';
        }

        renderVisits(visits);

        vehicleHistorySection.style.display = 'block';
        searchResultsSection.style.display = 'none';
        welcomeSection.style.display = 'none';
    }

    function renderVisits(visits) {
        visitsListContainer.innerHTML = '';

        // Chronological order: newest visits first
        const sortedVisits = [...visits].sort((a, b) => {
            const dateA = a.entry_date_sort || '0000-00-00';
            const dateB = b.entry_date_sort || '0000-00-00';
            if (dateA !== dateB) {
                return dateB.localeCompare(dateA);
            }
            const kmA = a.odometer_int || 0;
            const kmB = b.odometer_int || 0;
            return kmB - kmA;
        });

        sortedVisits.forEach((visit, idx) => {
            const card = createVisitCard(visit, idx);
            visitsListContainer.appendChild(card);
        });
    }

    function createVisitCard(visit, index) {
        const d = visit.details || {};
        const items = d.items || [];
        
        const card = document.createElement('div');
        card.className = 'visit-card';

        const header = document.createElement('div');
        header.className = 'visit-header';
        
        const dateDisplay = visit.entry_date || 'Data não informada';
        const kmDisplay = visit.odometer ? `${formatKm(visit.odometer)}` : 'KM não informado';
        const visitNumDisplay = visit.visit_num ? `Visita #${visit.visit_num}` : '';

        header.innerHTML = `
            <div class="visit-meta-left">
                <span class="badge-date">📅 ${dateDisplay}</span>
                <span class="badge-km">⏱️ ${kmDisplay}</span>
                ${visitNumDisplay ? `<span class="badge-visit-num">${visitNumDisplay}</span>` : ''}
            </div>
            <div class="visit-meta-right">
                <span class="visit-filename" title="${escapeHtml(visit.file_name)}">📄 ${escapeHtml(visit.file_name)}</span>
                <button class="btn btn-excel btn-sm" title="Abrir planilha original no Microsoft Excel">
                    📂 Abrir no Excel
                </button>
            </div>
        `;

        header.querySelector('.btn-excel').addEventListener('click', () => {
            openInExcel(visit.file_path);
        });

        card.appendChild(header);

        if (visit.complaint || d.complaint_comment) {
            const compBox = document.createElement('div');
            compBox.className = 'complaint-box';
            
            const compText = escapeHtml(visit.complaint || 'Visita para revisão / manutenção');
            let commentBtnHtml = '';
            if (d.complaint_comment) {
                commentBtnHtml = `
                    <button class="btn-scanner-note" title="Ver relatório do scanner ou nota técnica">
                        📝 Relatório do Scanner / Nota Técnica
                    </button>
                `;
            }

            compBox.innerHTML = `
                <div class="complaint-text">⚠️ Queixa / Motivo: ${compText}</div>
                ${commentBtnHtml}
            `;

            if (d.complaint_comment) {
                compBox.querySelector('.btn-scanner-note').addEventListener('click', () => {
                    openModal(
                        'Relatório do Scanner / Diagnóstico',
                        `Veículo: ${visit.car_model || visit.plate} • Data: ${visit.entry_date || ''}`,
                        d.complaint_comment
                    );
                });
            }

            card.appendChild(compBox);
        }

        const tableContainer = document.createElement('div');
        tableContainer.className = 'items-table-container';

        if (items.length === 0) {
            tableContainer.innerHTML = `
                <div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">
                    Nenhum item discriminado no corpo padrão desta planilha.
                </div>
            `;
        } else {
            const table = document.createElement('table');
            table.className = 'items-table';
            table.innerHTML = `
                <thead>
                    <tr>
                        <th style="width: 90px;">Tipo</th>
                        <th>Descrição do Item / Serviço / Anotação</th>
                        <th style="width: 70px; text-align: right;">Qtd</th>
                        <th class="col-price" style="width: 110px; text-align: right;">Valor Unit.</th>
                        <th class="col-price" style="width: 110px; text-align: right;">Valor Total</th>
                    </tr>
                </thead>
                <tbody></tbody>
            `;

            const tbody = table.querySelector('tbody');

            items.forEach(it => {
                const tr = document.createElement('tr');
                
                if (it.color) {
                    tr.className = 'has-color';
                    tr.style.backgroundColor = it.color;
                    tr.style.color = it.text_color || '#1e293b';
                }

                const hasNote = Boolean(it.comment);
                const noteAttr = hasNote ? 'class="td-desc has-excel-note" title="Clique para ver o comentário desta célula"' : 'class="td-desc"';

                let noteBadgeHtml = '';
                if (hasNote) {
                    noteBadgeHtml = `
                        <button class="note-btn-inline" title="Clique para abrir a anotação da célula">
                            💬 Ver nota
                        </button>
                    `;
                }

                tr.innerHTML = `
                    <td class="td-section" style="${it.color ? 'color: inherit; opacity: 0.85;' : ''}">${it.section || 'Item'}</td>
                    <td ${noteAttr}>
                        ${escapeHtml(it.description || '')}
                        ${noteBadgeHtml}
                    </td>
                    <td class="td-num">${it.quantity || '-'}</td>
                    <td class="td-num col-price">${it.unit_price || '-'}</td>
                    <td class="td-num col-price" style="font-weight: 600;">${it.total_price || '-'}</td>
                `;

                if (hasNote) {
                    const descTd = tr.querySelector('.td-desc');
                    descTd.addEventListener('click', (e) => {
                        e.stopPropagation();
                        openModal(
                            'Nota da Planilha (Excel)',
                            `Item: ${it.description || 'Célula'} (${it.section || 'Geral'})`,
                            it.comment
                        );
                    });
                }

                tbody.appendChild(tr);
            });

            tableContainer.appendChild(table);
        }

        card.appendChild(tableContainer);

        const footer = document.createElement('div');
        footer.className = 'visit-footer';

        const extraSheets = (d.sheets || []).filter(s => s !== d.active_sheet && s !== 'Plan1');
        let extraSheetsHtml = '';
        if (extraSheets.length > 0) {
            extraSheetsHtml = `<span class="extra-sheets-info">📑 Abas adicionais neste arquivo: <strong>${extraSheets.join(', ')}</strong></span>`;
        }

        const subtotal = d.subtotal || '';
        const discount = d.discount || '';
        const total = d.total || '';

        footer.innerHTML = `
            ${extraSheetsHtml}
            <div class="totals-group">
                ${subtotal && subtotal !== 'R$ 0,00' ? `<span class="total-item">SubTotal: <strong>${subtotal}</strong></span>` : ''}
                ${discount ? `<span class="total-item">Desconto: <strong>${discount}</strong></span>` : ''}
                ${total && total !== 'R$ 0,00' ? `<span class="total-item total-final">Total da Visita: ${total}</span>` : ''}
            </div>
        `;

        card.appendChild(footer);

        return card;
    }

    function resetToWelcome() {
        vehicleHistorySection.style.display = 'none';
        searchResultsSection.style.display = 'none';
        welcomeSection.style.display = 'block';
        currentCarHistory = null;
    }

    // Modal helpers
    function openModal(title, subtitle, text) {
        modalItemTitle.textContent = title;
        modalItemSubtitle.textContent = subtitle;
        modalCommentText.textContent = text;
        commentModal.style.display = 'flex';
    }

    function closeModal() {
        commentModal.style.display = 'none';
    }

    // Toast helper
    function showToast(message) {
        toast.textContent = message;
        toast.style.display = 'flex';
        clearTimeout(toast._timer);
        toast._timer = setTimeout(() => {
            toast.style.display = 'none';
        }, 3200);
    }

    // Helpers
    function formatKm(kmStr) {
        const n = parseInt(String(kmStr).replace(/\D/g, ''), 10);
        if (!isNaN(n) && n > 0) {
            return `${n.toLocaleString('pt-BR')} km`;
        }
        return `${kmStr} km`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
});
