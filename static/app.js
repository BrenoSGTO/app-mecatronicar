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
    const btnZoomOut = document.getElementById('btn-zoom-out');
    const btnZoomIn = document.getElementById('btn-zoom-in');
    const zoomValueText = document.getElementById('zoom-value-text');
    let currentZoom = parseInt(localStorage.getItem('mecatronicar_zoom') || '100', 10);
    if (isNaN(currentZoom) || currentZoom < 50 || currentZoom > 150) currentZoom = 100;
    
    const searchInput = document.getElementById('search-input');
    const btnClearSearch = document.getElementById('btn-clear-search');
    const vehicleItemSearchInput = document.getElementById('vehicle-item-search-input');
    const btnClearVehicleItemSearch = document.getElementById('btn-clear-vehicle-item-search');
    const vehicleItemMatchesBox = document.getElementById('vehicle-item-matches-box');
    const vehicleItemMatchesTitle = document.getElementById('vehicle-item-matches-title');
    const vehicleItemMatchesBadge = document.getElementById('vehicle-item-matches-badge');
    const vehicleItemMatchesList = document.getElementById('vehicle-item-matches-list');
    
    const welcomeSection = document.getElementById('welcome-section');
    const searchResultsSection = document.getElementById('search-results-section');
    const searchCardsGrid = document.getElementById('search-cards-grid');
    const searchResultsTitle = document.getElementById('search-results-title');
    const searchResultsCount = document.getElementById('search-results-count');
    
    const vehicleHistorySection = document.getElementById('vehicle-history-section');
    const visitsListContainer = document.getElementById('visits-list-container');
    const btnToggleAllServices = document.getElementById('btn-toggle-all-services');
    let showAllServicesGlobal = false;
    
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
    
    const btnVehicleOrcamento = document.getElementById('btn-vehicle-orcamento');
    const btnVehicleChecklist = document.getElementById('btn-vehicle-checklist');
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

    // Checklist Config Modal Elements (Issue #13)
    const modalChecklistConfig = document.getElementById('modal-checklist-config');
    const modalChecklistClose = document.getElementById('modal-checklist-close');
    const checklistModalSubtitle = document.getElementById('checklist-modal-subtitle');
    const chkChecklistScanner = document.getElementById('chk-checklist-scanner');
    const checklistScannerDesc = document.getElementById('checklist-scanner-desc');
    const checklistItemsCount = document.getElementById('checklist-items-count');
    const btnChecklistSelAll = document.getElementById('btn-checklist-sel-all');
    const btnChecklistDeselAll = document.getElementById('btn-checklist-desel-all');
    const checklistItemsList = document.getElementById('checklist-items-list');
    const checklistManualType = document.getElementById('checklist-manual-type');
    const checklistManualQty = document.getElementById('checklist-manual-qty');
    const checklistManualDesc = document.getElementById('checklist-manual-desc');
    const btnChecklistAddManual = document.getElementById('btn-checklist-add-manual');
    const checklistManualList = document.getElementById('checklist-manual-list');
    const btnChecklistCancel = document.getElementById('btn-checklist-cancel');
    const btnChecklistPreview = document.getElementById('btn-checklist-preview');
    const btnChecklistGenerate = document.getElementById('btn-checklist-generate');

    // Print Visits Selection Modal Elements (Issue #13)
    const modalPrintVisitsSelection = document.getElementById('modal-print-visits-selection');
    const modalPrintVisitsClose = document.getElementById('modal-print-visits-close');
    const printVisitsModalSubtitle = document.getElementById('print-visits-modal-subtitle');
    const btnPvAll = document.getElementById('btn-pv-all');
    const btnPvNone = document.getElementById('btn-pv-none');
    const btnPvLatest = document.getElementById('btn-pv-latest');
    const btnPvLast3 = document.getElementById('btn-pv-last-3');
    const btnPvLast5 = document.getElementById('btn-pv-last-5');
    const printVisitsCounterText = document.getElementById('print-visits-counter-text');
    const printVisitsScrollList = document.getElementById('print-visits-scroll-list');
    const chkPrintNoPrices = document.getElementById('chk-print-no-prices');
    const chkPrintExpandServices = document.getElementById('chk-print-expand-services');
    const btnPrintVisitsCancel = document.getElementById('btn-print-visits-cancel');
    const btnPrintVisitsPdfTab = document.getElementById('btn-print-visits-pdf-tab');
    const btnPrintVisitsConfirm = document.getElementById('btn-print-visits-confirm');

    function applyZoom(zoomPct, saveServer = false) {
        currentZoom = Math.max(50, Math.min(150, Math.round(zoomPct / 5) * 5));
        document.body.style.zoom = `${currentZoom}%`;
        if (zoomValueText) {
            zoomValueText.textContent = `${currentZoom}%`;
        }
        localStorage.setItem('mecatronicar_zoom', String(currentZoom));
        if (saveServer) {
            fetch('/api/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ui_zoom: currentZoom })
            }).catch(() => {});
        }
    }

    // Apply saved zoom immediately
    applyZoom(currentZoom, false);

    // Initialization
    loadInitialData();

    // Event Listeners
    btnChangeFolder.addEventListener('click', handleSelectFolder);
    btnReindex.addEventListener('click', handleReindex);
    btnCheckUpdates.addEventListener('click', handleCheckUpdatesManual);

    if (btnZoomOut) {
        btnZoomOut.addEventListener('click', () => {
            applyZoom(currentZoom - 10, true);
            showToast(`🔍 Zoom ajustado para ${currentZoom}%`);
        });
    }
    if (btnZoomIn) {
        btnZoomIn.addEventListener('click', () => {
            applyZoom(currentZoom + 10, true);
            showToast(`🔍 Zoom ajustado para ${currentZoom}%`);
        });
    }
    if (zoomValueText) {
        zoomValueText.addEventListener('click', () => {
            applyZoom(100, true);
            showToast('🔍 Zoom restaurado para 100%');
        });
    }
    
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

    if (vehicleItemSearchInput) {
        vehicleItemSearchInput.addEventListener('input', (e) => {
            const val = e.target.value.trim();
            if (btnClearVehicleItemSearch) {
                btnClearVehicleItemSearch.style.display = val ? 'flex' : 'none';
            }
            filterVehicleItems(val);
        });
    }

    if (btnClearVehicleItemSearch) {
        btnClearVehicleItemSearch.addEventListener('click', () => {
            vehicleItemSearchInput.value = '';
            btnClearVehicleItemSearch.style.display = 'none';
            filterVehicleItems('');
            vehicleItemSearchInput.focus();
        });
    }

    if (btnToggleAllServices) {
        btnToggleAllServices.addEventListener('click', () => {
            showAllServicesGlobal = !showAllServicesGlobal;
            updateGlobalServicesButtonUI();
            const allCards = document.querySelectorAll('.visit-card, .extra-sheet-panel');
            allCards.forEach(container => {
                if (typeof container._setServicesVisible === 'function') {
                    container._setServicesVisible(showAllServicesGlobal);
                }
            });
            showToast(
                showAllServicesGlobal
                    ? '🛠️ Exibindo serviços executados em todas as planilhas'
                    : '🔩 Exibindo apenas peças (clique em "Ver Serviços Executados" na planilha desejada)'
            );
        });
    }

    function updateGlobalServicesButtonUI() {
        if (!btnToggleAllServices) return;
        btnToggleAllServices.classList.toggle('active', showAllServicesGlobal);
        btnToggleAllServices.innerHTML = showAllServicesGlobal
            ? '🛠️ Ocultar Serviços Feitos em Todas as Planilhas'
            : '🛠️ Mostrar Serviços Feitos em Todas as Planilhas';
    }

    // Banner Vehicle Actions (CP-04 e CP-05)
    if (btnVehicleOrcamento) {
        btnVehicleOrcamento.addEventListener('click', () => {
            if (!currentCarHistory || !currentCarHistory.visits || currentCarHistory.visits.length === 0) {
                showToast('Nenhuma visita selecionada.');
                return;
            }
            const latestVisit = currentCarHistory._sortedVisits ? currentCarHistory._sortedVisits[0] : currentCarHistory.visits[0];
            const url = `/api/orcamento_pdf?file_path=${encodeURIComponent(latestVisit.file_path)}`;
            window.open(url, '_blank');
        });
    }

    if (btnVehicleChecklist) {
        btnVehicleChecklist.addEventListener('click', () => {
            if (!currentCarHistory || !currentCarHistory.visits || currentCarHistory.visits.length === 0) {
                showToast('Nenhuma visita selecionada.');
                return;
            }
            const latestVisit = currentCarHistory._sortedVisits ? currentCarHistory._sortedVisits[0] : currentCarHistory.visits[0];
            openChecklistConfigModal(latestVisit);
        });
    }

    // Print full (with prices)
    btnPrint.addEventListener('click', () => {
        openPrintVisitsSelectionModal(false);
    });

    // Print without prices
    if (btnPrintNoPrices) {
        btnPrintNoPrices.addEventListener('click', () => {
            openPrintVisitsSelectionModal(true);
        });
    }

    // Checklist modal listeners (Issue #13)
    if (modalChecklistClose) modalChecklistClose.addEventListener('click', closeChecklistConfigModal);
    if (btnChecklistCancel) btnChecklistCancel.addEventListener('click', closeChecklistConfigModal);
    if (modalChecklistConfig) {
        modalChecklistConfig.addEventListener('click', (e) => {
            if (e.target === modalChecklistConfig) closeChecklistConfigModal();
        });
    }
    if (btnChecklistSelAll) {
        btnChecklistSelAll.addEventListener('click', () => {
            if (checklistItemsList) {
                checklistItemsList.querySelectorAll('.chk-checklist-item').forEach(cb => cb.checked = true);
            }
        });
    }
    if (btnChecklistDeselAll) {
        btnChecklistDeselAll.addEventListener('click', () => {
            if (checklistItemsList) {
                checklistItemsList.querySelectorAll('.chk-checklist-item').forEach(cb => cb.checked = false);
            }
        });
    }
    if (btnChecklistAddManual) {
        btnChecklistAddManual.addEventListener('click', addChecklistManualItem);
    }
    if (checklistManualDesc) {
        checklistManualDesc.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                addChecklistManualItem();
            }
        });
    }
    if (btnChecklistPreview) {
        btnChecklistPreview.addEventListener('click', () => submitChecklistForm(false));
    }
    if (btnChecklistGenerate) {
        btnChecklistGenerate.addEventListener('click', () => submitChecklistForm(true));
    }

    // Print visits modal listeners (Issue #13)
    if (modalPrintVisitsClose) modalPrintVisitsClose.addEventListener('click', closePrintVisitsSelectionModal);
    if (btnPrintVisitsCancel) btnPrintVisitsCancel.addEventListener('click', closePrintVisitsSelectionModal);
    if (modalPrintVisitsSelection) {
        modalPrintVisitsSelection.addEventListener('click', (e) => {
            if (e.target === modalPrintVisitsSelection) closePrintVisitsSelectionModal();
        });
    }
    if (btnPvAll) {
        btnPvAll.addEventListener('click', () => setPrintVisitsSelection(() => true));
    }
    if (btnPvNone) {
        btnPvNone.addEventListener('click', () => setPrintVisitsSelection(() => false));
    }
    if (btnPvLatest) {
        btnPvLatest.addEventListener('click', () => setPrintVisitsSelection((idx) => idx === 0));
    }
    if (btnPvLast3) {
        btnPvLast3.addEventListener('click', () => setPrintVisitsSelection((idx) => idx < 3));
    }
    if (btnPvLast5) {
        btnPvLast5.addEventListener('click', () => setPrintVisitsSelection((idx) => idx < 5));
    }
    if (btnPrintVisitsConfirm) {
        btnPrintVisitsConfirm.addEventListener('click', executePrintSelectedVisits);
    }
    if (btnPrintVisitsPdfTab) {
        btnPrintVisitsPdfTab.addEventListener('click', openConsolidatedHistoryPdfTab);
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
            if (modalChecklistConfig && modalChecklistConfig.style.display !== 'none') closeChecklistConfigModal();
            if (modalPrintVisitsSelection && modalPrintVisitsSelection.style.display !== 'none') closePrintVisitsSelectionModal();
            const anModal = document.getElementById('analytics-modal');
            if (anModal && anModal.style.display !== 'none') anModal.style.display = 'none';
        }
        if (e.ctrlKey && (e.key === '-' || e.key === '_')) {
            e.preventDefault();
            applyZoom(currentZoom - 10, true);
            showToast(`🔍 Zoom ajustado para ${currentZoom}%`);
        } else if (e.ctrlKey && (e.key === '+' || e.key === '=')) {
            e.preventDefault();
            applyZoom(currentZoom + 10, true);
            showToast(`🔍 Zoom ajustado para ${currentZoom}%`);
        } else if (e.ctrlKey && e.key === '0') {
            e.preventDefault();
            applyZoom(100, true);
            showToast('🔍 Zoom restaurado para 100%');
        }
    });

    // Helper para verificar status da resposta e Content-Type antes de invocar res.json()
    async function safeParseJsonResponse(res, fallbackErrorMsg = 'Falha na comunicação com o servidor') {
        const contentType = res.headers.get('content-type') || '';
        let data = null;

        if (contentType.includes('application/json')) {
            try {
                data = await res.json();
            } catch (e) {
                throw new Error('Falha ao interpretar dados do servidor (formato JSON corrompido).');
            }
        } else {
            const raw = await res.text().catch(() => '');
            const clean = raw.replace(/<[^>]*>?/gm, '').trim();
            const snippet = clean ? (clean.length > 80 ? clean.substring(0, 80) + '...' : clean) : '';
            if (!res.ok) {
                throw new Error(`Servidor retornou erro HTTP ${res.status}${snippet ? `: ${snippet}` : '.'}`);
            }
            throw new Error(`Resposta do servidor não está em formato JSON válido${snippet ? `: ${snippet}` : '.'}`);
        }

        if (!res.ok) {
            const msg = (data && (data.error || data.message)) ? (data.error || data.message) : `${fallbackErrorMsg} (HTTP ${res.status})`;
            const err = new Error(msg);
            err.status = res.status;
            err.data = data;
            throw err;
        }

        return data;
    }

    // API Functions
    async function loadInitialData() {
        try {
            const res = await fetch('/api/config');
            const data = await safeParseJsonResponse(res, 'Erro ao ler configurações');
            currentConfig = data.config || {};
            if (data.version && appVersionBadge) {
                appVersionBadge.textContent = `v${data.version}`;
            }
            if (currentConfig.ui_zoom) {
                applyZoom(parseInt(currentConfig.ui_zoom, 10), false);
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
            const data = await safeParseJsonResponse(res, 'Erro ao carregar veículos');
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
            const data = await safeParseJsonResponse(res, 'Erro ao configurar pasta');
            if (data.success) {
                updateFolderUI(data.folder);
                showToast(`Pasta configurada com sucesso! ${data.stats.total_files} planilhas indexadas.`);
                await loadCarsList();
                resetToWelcome();
            }
        } catch (err) {
            console.error('Erro escolhendo pasta:', err);
            showToast('Erro ao selecionar pasta: ' + err.message);
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
            const data = await safeParseJsonResponse(res, 'Erro ao reindexar');
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
            showToast('Erro ao atualizar planilhas: ' + err.message);
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
            const data = await safeParseJsonResponse(res, 'Erro ao abrir arquivo');
            if (data.success) {
                showToast('✓ Planilha aberta no Excel com sucesso!');
            } else {
                showToast(`Erro ao abrir: ${data.error}`);
            }
        } catch (err) {
            showToast('Falha na comunicação ao abrir o arquivo: ' + err.message);
        }
    }

    async function selectVehicleByPlate(plate) {
        showToast(`Carregando histórico do veículo ${plate}...`);
        try {
            const res = await fetch(`/api/car_history/${encodeURIComponent(plate)}`);
            const data = await safeParseJsonResponse(res, 'Erro ao carregar histórico');
            if (data.visits && data.visits.length > 0) {
                currentCarHistory = data;
                renderVehicleHistory(data);
            } else {
                showToast(`Nenhuma visita encontrada para a placa ${plate}`);
            }
        } catch (err) {
            console.error('Erro carregando histórico:', err);
            showToast('Erro ao buscar visitas do carro: ' + err.message);
        }
    }

    async function performSearch(query) {
        if (!query || query.length < 3) {
            resetToWelcome();
            return;
        }

        try {
            const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
            const data = await safeParseJsonResponse(res, 'Erro na busca');
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

        if (vehicleItemSearchInput) {
            vehicleItemSearchInput.value = '';
        }
        if (btnClearVehicleItemSearch) {
            btnClearVehicleItemSearch.style.display = 'none';
        }
        if (vehicleItemMatchesBox) {
            vehicleItemMatchesBox.style.display = 'none';
        }

        renderVisits(visits);

        vehicleHistorySection.style.display = 'block';
        searchResultsSection.style.display = 'none';
        welcomeSection.style.display = 'none';
    }

    function normalizeSearchText(str) {
        if (!str) return '';
        return String(str)
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .toLowerCase()
            .trim();
    }

    function matchesSearchTokens(targetText, rawQuery) {
        const stopWords = new Set(['de', 'do', 'da', 'dos', 'das', 'e', 'o', 'a', 'os', 'as', 'no', 'na', 'nos', 'nas', 'para', 'por', 'com', 'em']);
        const actionWords = new Set(['troca', 'trocar', 'substituicao', 'substituir', 'subst', 'reparo', 'conserto', 'servico', 'peca']);
        const normTarget = normalizeSearchText(targetText);
        const tokens = normalizeSearchText(rawQuery)
            .split(/\s+/)
            .filter(t => t.length > 0 && !stopWords.has(t));
        if (tokens.length === 0) {
            return normTarget.includes(normalizeSearchText(rawQuery));
        }
        const specificTokens = tokens.filter(t => !actionWords.has(t));
        const activeTokens = specificTokens.length > 0 ? specificTokens : tokens;
        return activeTokens.every(tok => normTarget.includes(tok));
    }

    function filterVehicleItems(rawQuery) {
        if (!currentCarHistory || !currentCarHistory.visits) return;
        const q = (rawQuery || '').trim();
        const visitCards = visitsListContainer.querySelectorAll('.visit-card');

        if (!q) {
            if (vehicleItemMatchesBox) {
                vehicleItemMatchesBox.style.display = 'none';
            }
            visitCards.forEach(card => {
                card.style.display = '';
                card.querySelectorAll('tr.item-search-match').forEach(tr => {
                    tr.classList.remove('item-search-match');
                });
                if (typeof card._setServicesVisible === 'function') {
                    card._setServicesVisible(showAllServicesGlobal);
                }
            });
            return;
        }

        const matchedOccurrences = [];

        visitCards.forEach(card => {
            const visitIdx = parseInt(card.dataset.visitIndex || '0', 10);
            const visit = currentCarHistory._sortedVisits ? currentCarHistory._sortedVisits[visitIdx] : null;
            if (!visit) return;

            let cardHasMatch = false;
            let serviceHasMatch = false;
            const d = visit.details || {};
            const complaintStr = `${visit.complaint || ''} ${d.complaint_comment || ''}`;

            if (matchesSearchTokens(complaintStr, q)) {
                cardHasMatch = true;
                matchedOccurrences.push({
                    visit,
                    cardElement: card,
                    section: 'Queixa',
                    description: visit.complaint || 'Nota Técnica / Diagnóstico',
                    quantity: '',
                    total_price: ''
                });
            }

            const rows = card.querySelectorAll('.main-sheet-table tbody tr');
            rows.forEach(tr => {
                const desc = tr.dataset.itemDesc || '';
                const comment = tr.dataset.itemComment || '';
                const sec = tr.dataset.itemSection || 'Item';
                const qty = tr.dataset.itemQty || '';
                const price = tr.dataset.itemPrice || '';

                if (matchesSearchTokens(`${desc} ${comment}`, q)) {
                    tr.classList.add('item-search-match');
                    cardHasMatch = true;
                    if (sec === 'Serviço') {
                        serviceHasMatch = true;
                    }
                    matchedOccurrences.push({
                        visit,
                        cardElement: card,
                        rowElement: tr,
                        isServiceRow: sec === 'Serviço',
                        section: sec,
                        description: desc,
                        quantity: qty,
                        total_price: price
                    });
                } else {
                    tr.classList.remove('item-search-match');
                }
            });

            if (serviceHasMatch && typeof card._setServicesVisible === 'function') {
                card._setServicesVisible(true);
            }

            const extraSheets = d.extra_sheets_data || [];
            extraSheets.forEach(secSheet => {
                (secSheet.items || []).forEach(it => {
                    if (matchesSearchTokens(`${it.description || ''} ${it.comment || ''}`, q)) {
                        cardHasMatch = true;
                        matchedOccurrences.push({
                            visit,
                            cardElement: card,
                            section: `${secSheet.sheet_name} • ${it.section || 'Item'}`,
                            description: it.description || '',
                            quantity: it.quantity || '',
                            total_price: it.total_price || ''
                        });
                    }
                });
            });

            card.style.display = cardHasMatch ? '' : 'none';
        });

        if (vehicleItemMatchesBox) {
            vehicleItemMatchesBox.style.display = 'block';
            vehicleItemMatchesTitle.textContent = `Histórico de "${q}" neste veículo`;
            vehicleItemMatchesBadge.textContent = `${matchedOccurrences.length} ${matchedOccurrences.length === 1 ? 'registro encontrado' : 'registros encontrados'}`;
            vehicleItemMatchesList.innerHTML = '';

            if (matchedOccurrences.length === 0) {
                vehicleItemMatchesList.innerHTML = `
                    <div style="padding: 10px; color: var(--text-muted); font-size: 13px; text-align: center;">
                        Nenhuma peça ou serviço com <strong>"${escapeHtml(q)}"</strong> foi encontrado nas visitas deste veículo.
                    </div>
                `;
            } else {
                matchedOccurrences.forEach(occ => {
                    const row = document.createElement('div');
                    row.className = 'match-row-card';
                    const dateStr = occ.visit.entry_date || 'Sem data';
                    const kmStr = occ.visit.odometer ? formatKm(occ.visit.odometer) : 'KM não inf.';
                    const vNum = occ.visit.visit_num ? `Visita #${occ.visit.visit_num}` : '';
                    const qtyInfo = occ.quantity && occ.quantity !== '-' ? ` (Qtd: ${occ.quantity})` : '';

                    row.innerHTML = `
                        <div class="match-meta-pills">
                            <span class="match-pill-date">📅 ${escapeHtml(dateStr)}</span>
                            <span class="match-pill-km">⏱️ ${escapeHtml(kmStr)}</span>
                            ${vNum ? `<span class="match-pill-visit">${escapeHtml(vNum)}</span>` : ''}
                        </div>
                        <div class="match-item-desc">
                            <span class="match-item-section-tag">${escapeHtml(occ.section)}</span>
                            ${escapeHtml(occ.description)}${escapeHtml(qtyInfo)}
                        </div>
                        ${occ.total_price && occ.total_price !== '-' ? `<div class="match-item-price col-price">${escapeHtml(occ.total_price)}</div>` : ''}
                    `;

                    row.addEventListener('click', () => {
                        if (occ.isServiceRow && occ.cardElement && typeof occ.cardElement._setServicesVisible === 'function') {
                            occ.cardElement._setServicesVisible(true);
                        }
                        const target = occ.rowElement || occ.cardElement;
                        if (target) {
                            target.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        }
                    });

                    vehicleItemMatchesList.appendChild(row);
                });
            }
        }
    }

    function renderVisits(visits) {
        visitsListContainer.innerHTML = '';
        updateGlobalServicesButtonUI();

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

        if (currentCarHistory) {
            currentCarHistory._sortedVisits = sortedVisits;
        }

        sortedVisits.forEach((visit, idx) => {
            const card = createVisitCard(visit, idx);
            visitsListContainer.appendChild(card);
        });
    }

    function buildItemsTableElement(items, isMainSheet = false, tableMode = 'pecas') {
        const table = document.createElement('table');
        table.className = isMainSheet ? 'items-table main-sheet-table' : 'items-table';
        const descHeader = tableMode === 'servicos'
            ? 'Descrição do Serviço Executado / Mão de Obra'
            : 'Descrição da Peça / Anotação da Planilha';
        table.innerHTML = `
            <thead>
                <tr>
                    <th style="width: 90px;">Tipo</th>
                    <th>${descHeader}</th>
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
            tr.dataset.itemDesc = it.description || '';
            tr.dataset.itemComment = it.comment || '';
            tr.dataset.itemSection = it.section || 'Item';
            tr.dataset.itemQty = it.quantity || '';
            tr.dataset.itemPrice = it.total_price || '';
            
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

            const sectionBadgeClass = it.section === 'Serviço' ? 'td-section td-section-service' : 'td-section';

            tr.innerHTML = `
                <td class="${sectionBadgeClass}" style="${it.color ? 'color: inherit; opacity: 0.85;' : ''}">${it.section || 'Item'}</td>
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

        return table;
    }

    function buildServicesPanelAndToggle(servicosItems, totalServicos, isMainSheet, initiallyOpen) {
        const wrapper = document.createElement('div');
        wrapper.className = 'services-section-panel';
        wrapper.style.display = initiallyOpen ? 'block' : 'none';

        const srvHeader = document.createElement('div');
        srvHeader.className = 'services-panel-header';
        srvHeader.innerHTML = `
            <div class="services-panel-title">
                <span>🛠️ Serviços Executados / Mão de Obra nesta Planilha</span>
                <span class="services-count-pill">${servicosItems.length} ${servicosItems.length === 1 ? 'serviço' : 'serviços'}</span>
            </div>
            ${totalServicos && totalServicos !== 'R$ 0,00' ? `<div class="services-subtotal col-price">Total de Serviços: <strong>${escapeHtml(totalServicos)}</strong></div>` : ''}
        `;
        wrapper.appendChild(srvHeader);

        const srvBody = document.createElement('div');
        srvBody.className = 'items-table-container';
        if (servicosItems.length === 0) {
            srvBody.innerHTML = `
                <div class="empty-services-msg">
                    Nenhum serviço foi preenchido separadamente no campo "Serviço" desta planilha.
                </div>
            `;
        } else {
            srvBody.appendChild(buildItemsTableElement(servicosItems, isMainSheet, 'servicos'));
        }
        wrapper.appendChild(srvBody);

        return wrapper;
    }

    function createExtraSheetPanel(sheetData) {
        const panel = document.createElement('div');
        panel.className = 'extra-sheet-panel';

        const allItems = sheetData.items || [];
        const pecasItems = sheetData.pecas_items || allItems.filter(i => i.section !== 'Serviço');
        const servicosItems = sheetData.servicos_items || allItems.filter(i => i.section === 'Serviço');
        const totalPecas = sheetData.total_pecas || '';
        const totalServicos = sheetData.total_servicos || '';

        const header = document.createElement('div');
        header.className = 'extra-sheet-panel-header';
        header.innerHTML = `
            <div>
                <span class="extra-sheet-panel-title">📑 Aba: ${escapeHtml(sheetData.sheet_name)}</span>
                ${sheetData.title ? `<span style="margin-left: 10px; font-weight: 500; color: #e2e8f0;">— ${escapeHtml(sheetData.title)}</span>` : ''}
            </div>
            <div class="totals-group" style="margin-left: auto;">
                ${totalPecas ? `<span class="col-price" style="font-size: 12px; color: #cbd5e1;">Peças: <strong>${escapeHtml(totalPecas)}</strong></span>` : ''}
                ${totalServicos ? `<span class="col-price" style="font-size: 12px; color: #fde047;">Serviços: <strong>${escapeHtml(totalServicos)}</strong></span>` : ''}
                ${sheetData.subtotal ? `<span class="col-price" style="font-size: 12px; color: #cbd5e1;">SubTotal: <strong>${escapeHtml(sheetData.subtotal)}</strong></span>` : ''}
                ${sheetData.discount ? `<span class="col-price" style="font-size: 12px; color: #cbd5e1;">Desconto: <strong>${escapeHtml(sheetData.discount)}</strong></span>` : ''}
                ${sheetData.total ? `<span class="col-price" style="font-size: 13px; background: var(--primary); color: #111827; padding: 2px 8px; border-radius: 4px; font-weight: 800;">Total: ${escapeHtml(sheetData.total)}</span>` : ''}
            </div>
        `;
        panel.appendChild(header);

        if (allItems.length > 0) {
            const sectionBar = document.createElement('div');
            sectionBar.className = 'sheet-section-bar';
            sectionBar.innerHTML = `
                <div class="sheet-section-bar-left">
                    <span class="sheet-section-label">🔩 Peças da Aba (${pecasItems.length})</span>
                    ${totalPecas ? `<span class="sheet-section-subtotal col-price">Subtotal Peças: <strong>${escapeHtml(totalPecas)}</strong></span>` : ''}
                </div>
                <div class="sheet-section-bar-right">
                    <button type="button" class="btn-toggle-services">
                        🛠️ Ver Serviços Executados (${servicosItems.length})
                    </button>
                </div>
            `;
            panel.appendChild(sectionBar);

            const tblWrap = document.createElement('div');
            tblWrap.className = 'items-table-container';
            if (pecasItems.length > 0) {
                tblWrap.appendChild(buildItemsTableElement(pecasItems, false, 'pecas'));
            } else {
                tblWrap.innerHTML = `
                    <div style="padding: 14px; text-align: center; color: var(--text-muted); font-size: 13px;">
                        Nenhuma peça listada nesta aba.
                    </div>
                `;
            }
            panel.appendChild(tblWrap);

            const autoOpen = showAllServicesGlobal || (pecasItems.length === 0 && servicosItems.length > 0);
            const srvPanel = buildServicesPanelAndToggle(servicosItems, totalServicos, false, autoOpen);
            panel.appendChild(srvPanel);

            const toggleBtn = sectionBar.querySelector('.btn-toggle-services');
            const setServicesVisible = (vis) => {
                srvPanel.style.display = vis ? 'block' : 'none';
                toggleBtn.classList.toggle('active', vis);
                toggleBtn.innerHTML = vis
                    ? `🛠️ Ocultar Serviços Executados (${servicosItems.length})`
                    : `🛠️ Ver Serviços Executados (${servicosItems.length})`;
            };
            setServicesVisible(autoOpen);
            toggleBtn.addEventListener('click', () => {
                const currentlyHidden = srvPanel.style.display === 'none';
                setServicesVisible(currentlyHidden);
            });
            panel._setServicesVisible = setServicesVisible;
        } else if (sheetData.grid_rows && sheetData.grid_rows.length > 0) {
            const tblWrap = document.createElement('div');
            tblWrap.className = 'items-table-container';
            const gridTable = document.createElement('table');
            gridTable.className = 'items-table';
            const tbody = document.createElement('tbody');
            sheetData.grid_rows.forEach(rCells => {
                const tr = document.createElement('tr');
                rCells.forEach(cellVal => {
                    const td = document.createElement('td');
                    td.textContent = cellVal || '';
                    tr.appendChild(td);
                });
                tbody.appendChild(tr);
            });
            gridTable.appendChild(tbody);
            tblWrap.appendChild(gridTable);
            panel.appendChild(tblWrap);
        }

        return panel;
    }

    function createVisitCard(visit, index) {
        const d = visit.details || {};
        const items = d.items || [];
        const pecasItems = d.pecas_items || items.filter(i => i.section !== 'Serviço');
        const servicosItems = d.servicos_items || items.filter(i => i.section === 'Serviço');
        const totalPecas = d.total_pecas || '';
        const totalServicos = d.total_servicos || '';
        
        const card = document.createElement('div');
        card.className = 'visit-card';
        card.dataset.visitIndex = String(index);

        const header = document.createElement('div');
        header.className = 'visit-header';
        
        const dateDisplay = visit.entry_date || 'Data não informada';
        const kmDisplay = visit.odometer ? `${formatKm(visit.odometer)}` : 'KM não informado';
        const visitNumDisplay = visit.visit_num ? `Visita #${visit.visit_num}` : '';

        // Fiscal status badge for visit card
        const nfControl = visit.nf_control || {};
        const isServicoDone = (nfControl.status_servico === 'emitida') || (nfControl.nfse_status === 'emitida');
        const isPecasDone = (nfControl.status_pecas === 'emitida') || (nfControl.nfe_status === 'emitida');
        const hasServicoVal = (nfControl.valor_servico > 0) || (servicosItems.length > 0);
        const hasPecasVal = (nfControl.valor_pecas > 0) || (pecasItems.length > 0);

        let nfBadgeHtml = '';
        if (isServicoDone && isPecasDone) {
            const numServ = nfControl.nf_servico_num || nfControl.nfse_number || '';
            const numPecas = nfControl.nf_pecas_num || nfControl.nfe_number || '';
            const numsStr = [numServ ? `NFS-e #${numServ}` : 'NFS-e', numPecas ? `NF-e #${numPecas}` : 'NF-e'].join(' • ');
            nfBadgeHtml = `<span class="badge-visit-nf emitted" title="Notas Fiscais emitidas para esta visita">✅ ${numsStr}</span>`;
        } else if (isServicoDone || isPecasDone) {
            nfBadgeHtml = `<span class="badge-visit-nf partial" title="Uma nota fiscal emitida e outra pendente">🟡 NF Parcial</span>`;
        } else if (hasServicoVal || hasPecasVal) {
            nfBadgeHtml = `<span class="badge-visit-nf pending" title="Notas Fiscais pendentes de emissão. Clique para abrir no Copiloto.">⏳ NF Pendente</span>`;
        } else {
            nfBadgeHtml = `<span class="badge-visit-nf none" title="Nenhuma nota fiscal emitida ainda">🧾 NF</span>`;
        }

        header.innerHTML = `
            <div class="visit-meta-left">
                <span class="badge-date">📅 ${dateDisplay}</span>
                <span class="badge-km">⏱️ ${kmDisplay}</span>
                ${visitNumDisplay ? `<span class="badge-visit-num">${visitNumDisplay}</span>` : ''}
                ${nfBadgeHtml}
            </div>
            <div class="visit-meta-right">
                <span class="visit-filename" title="${escapeHtml(visit.file_name)}">📄 ${escapeHtml(visit.file_name)}</span>
                <button type="button" class="btn btn-primary btn-sm btn-doc-orcamento" title="Gerar Orçamento / OS Profissional com Logotipo MecatroniCar em PDF">
                    📄 Orçamento / OS
                </button>
                <button type="button" class="btn btn-checklist btn-sm btn-doc-checklist" title="Gerar Checklist para os mecânicos (sem valores financeiros)">
                    📋 Checklist
                </button>
                <button type="button" class="btn btn-sm btn-visit-fiscal" style="background: #fefce8; border: 1.5px solid #fde047; color: #854d0e; font-weight: 700;" title="Abrir Copiloto Fiscal para emissão de NFS-e (Santos) e NF-e 55 desta OS">
                    🧾 Copiloto NF
                </button>
                <button type="button" class="btn-toggle-services btn-sm" title="Mostrar ou ocultar os serviços executados nesta planilha">
                    🛠️ Serviços (${servicosItems.length})
                </button>
                <button type="button" class="btn btn-sm btn-edit-os" title="Editar dados, peças ou serviços desta OS no Excel">
                    ✏️ Editar OS
                </button>
                <button class="btn btn-excel btn-sm" title="Abrir planilha original no Microsoft Excel">
                    📂 Excel
                </button>
            </div>
        `;

        const nfBadgeEl = header.querySelector('.badge-visit-nf');
        if (nfBadgeEl) {
            nfBadgeEl.addEventListener('click', () => {
                openFiscalModal(visit.file_path, currentCarHistory?.vehicle?.plate || visit.plate, visit.visit_num);
            });
        }

        const btnVisitFiscal = header.querySelector('.btn-visit-fiscal');
        if (btnVisitFiscal) {
            btnVisitFiscal.addEventListener('click', () => {
                openFiscalModal(visit.file_path, currentCarHistory?.vehicle?.plate || visit.plate, visit.visit_num);
            });
        }

        header.querySelector('.btn-doc-orcamento').addEventListener('click', () => {
            const url = `/api/orcamento_pdf?file_path=${encodeURIComponent(visit.file_path)}`;
            window.open(url, '_blank');
        });

        header.querySelector('.btn-doc-checklist').addEventListener('click', () => {
            openChecklistConfigModal(visit);
        });

        header.querySelector('.btn-edit-os').addEventListener('click', () => {
            openOsModalForEdit(visit);
        });

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

        // Section bar above Peças with per-spreadsheet button to toggle Serviços Executados
        const sectionBar = document.createElement('div');
        sectionBar.className = 'sheet-section-bar';
        sectionBar.innerHTML = `
            <div class="sheet-section-bar-left">
                <span class="sheet-section-label">🔩 Peças da Planilha (${pecasItems.length})</span>
                ${totalPecas && totalPecas !== 'R$ 0,00' ? `<span class="sheet-section-subtotal col-price">Total de Peças: <strong>${escapeHtml(totalPecas)}</strong></span>` : ''}
            </div>
            <div class="sheet-section-bar-right">
                <button type="button" class="btn-toggle-services">
                    🛠️ Ver Serviços Executados (${servicosItems.length})${totalServicos && totalServicos !== 'R$ 0,00' ? ` • ${escapeHtml(totalServicos)}` : ''}
                </button>
            </div>
        `;
        card.appendChild(sectionBar);

        const tableContainer = document.createElement('div');
        tableContainer.className = 'items-table-container';

        if (pecasItems.length === 0) {
            tableContainer.innerHTML = `
                <div style="padding: 18px; text-align: center; color: var(--text-muted); font-size: 13px;">
                    Nenhuma peça discriminada na seção de Peças desta planilha.
                </div>
            `;
        } else {
            tableContainer.appendChild(buildItemsTableElement(pecasItems, true, 'pecas'));
        }

        card.appendChild(tableContainer);

        const autoOpenServices = showAllServicesGlobal || (pecasItems.length === 0 && servicosItems.length > 0);
        const servicesPanel = buildServicesPanelAndToggle(servicosItems, totalServicos, true, autoOpenServices);
        card.appendChild(servicesPanel);

        const headerToggleBtn = header.querySelector('.btn-toggle-services');
        const barToggleBtn = sectionBar.querySelector('.btn-toggle-services');
        const priceSuffix = totalServicos && totalServicos !== 'R$ 0,00' ? ` • ${escapeHtml(totalServicos)}` : '';

        const setServicesVisible = (vis) => {
            servicesPanel.style.display = vis ? 'block' : 'none';
            [headerToggleBtn, barToggleBtn].forEach(b => {
                if (!b) return;
                b.classList.toggle('active', vis);
            });
            if (headerToggleBtn) {
                headerToggleBtn.innerHTML = vis
                    ? `🛠️ Ocultar Serviços (${servicosItems.length})`
                    : `🛠️ Ver Serviços Executados (${servicosItems.length})`;
            }
            if (barToggleBtn) {
                barToggleBtn.innerHTML = vis
                    ? `🛠️ Ocultar Serviços Executados (${servicosItems.length})${priceSuffix}`
                    : `🛠️ Ver Serviços Executados (${servicosItems.length})${priceSuffix}`;
            }
        };

        setServicesVisible(autoOpenServices);

        [headerToggleBtn, barToggleBtn].forEach(b => {
            if (!b) return;
            b.addEventListener('click', () => {
                const currentlyHidden = servicesPanel.style.display === 'none';
                setServicesVisible(currentlyHidden);
            });
        });

        card._setServicesVisible = setServicesVisible;

        const footer = document.createElement('div');
        footer.className = 'visit-footer';

        const filledExtraSheets = d.extra_sheets_data || [];
        const extraSheetsContainer = document.createElement('div');
        extraSheetsContainer.className = 'extra-sheets-bar';

        const extraPanelsHolder = document.createElement('div');

        if (filledExtraSheets.length > 0) {
            const lbl = document.createElement('span');
            lbl.className = 'extra-sheets-label';
            lbl.textContent = '📑 Outras planilhas preenchidas nesta ficha:';
            extraSheetsContainer.appendChild(lbl);

            filledExtraSheets.forEach((secSheet) => {
                const btn = document.createElement('button');
                btn.className = 'btn-extra-sheet';
                const countBadge = secSheet.items && secSheet.items.length > 0
                    ? ` (${secSheet.items.length} itens)`
                    : '';
                btn.textContent = `👁️ Ver ${secSheet.sheet_name}${countBadge}`;
                btn.title = secSheet.title || `Clique para ver o conteúdo preenchido na aba ${secSheet.sheet_name}`;

                let panelEl = null;
                btn.addEventListener('click', () => {
                    if (panelEl) {
                        const isHidden = panelEl.style.display === 'none';
                        panelEl.style.display = isHidden ? 'block' : 'none';
                        btn.classList.toggle('active', isHidden);
                    } else {
                        panelEl = createExtraSheetPanel(secSheet);
                        extraPanelsHolder.appendChild(panelEl);
                        btn.classList.add('active');
                    }
                });

                extraSheetsContainer.appendChild(btn);
            });
        }

        const subtotal = d.subtotal || '';
        const discount = d.discount || '';
        const total = d.total || '';

        const totalsDiv = document.createElement('div');
        totalsDiv.className = 'totals-group';
        totalsDiv.innerHTML = `
            ${totalPecas && totalPecas !== 'R$ 0,00' ? `<span class="total-item">Peças: <strong>${totalPecas}</strong></span>` : ''}
            ${totalServicos && totalServicos !== 'R$ 0,00' ? `<span class="total-item">Serviços: <strong>${totalServicos}</strong></span>` : ''}
            ${subtotal && subtotal !== 'R$ 0,00' ? `<span class="total-item">SubTotal: <strong>${subtotal}</strong></span>` : ''}
            ${discount ? `<span class="total-item">Desconto: <strong>${discount}</strong></span>` : ''}
            ${total && total !== 'R$ 0,00' ? `<span class="total-item total-final">Total da Visita: ${total}</span>` : ''}
        `;

        footer.appendChild(extraSheetsContainer);
        footer.appendChild(totalsDiv);
        card.appendChild(footer);
        card.appendChild(extraPanelsHolder);

        return card;
    }

    function resetToWelcome() {
        vehicleHistorySection.style.display = 'none';
        searchResultsSection.style.display = 'none';
        welcomeSection.style.display = 'block';
        currentCarHistory = null;
        if (vehicleItemSearchInput) vehicleItemSearchInput.value = '';
        if (btnClearVehicleItemSearch) btnClearVehicleItemSearch.style.display = 'none';
        if (vehicleItemMatchesBox) vehicleItemMatchesBox.style.display = 'none';
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

    // =========================================================================
    // Issue #13: Customização Interativa de Checklist e Seleção de Visitas
    // =========================================================================
    let currentChecklistVisit = null;
    let currentManualItems = [];
    let currentPrintVisits = [];

    function openChecklistConfigModal(visit) {
        if (!visit) {
            showToast('Nenhuma visita disponível para checklist.');
            return;
        }
        currentChecklistVisit = visit;
        currentManualItems = [];

        const plate = visit.plate_display || visit.plate || (currentCarHistory && currentCarHistory.plate) || 'SEM PLACA';
        const car = visit.car_model || (currentCarHistory && currentCarHistory.visits && currentCarHistory.visits[0]?.car_model) || 'Veículo';
        const client = visit.client_name || (currentCarHistory && currentCarHistory.visits && currentCarHistory.visits[0]?.client_name) || '';
        const vNum = visit.visit_num || '1';

        if (checklistModalSubtitle) {
            checklistModalSubtitle.textContent = `Veículo: ${plate} • ${car} • Visita #${vNum}${client ? ' • Cliente: ' + client : ''}`;
        }

        const d = visit.details || {};
        const items = d.items || [];
        const pecas = d.pecas_items || items.filter(i => i.section !== 'Serviço');
        const servicos = d.servicos_items || items.filter(i => i.section === 'Serviço');

        // Configura toggle do Scanner OBD2
        const hasScannerNote = Boolean(d.complaint_comment && d.complaint_comment.trim());
        if (chkChecklistScanner) {
            chkChecklistScanner.checked = true;
        }
        if (checklistScannerDesc) {
            if (hasScannerNote) {
                const sampleText = d.complaint_comment.trim().split('\n')[0].slice(0, 45);
                checklistScannerDesc.innerHTML = `<span style="color: #15803d; font-weight: 700;">✓ Códigos/Diagnóstico detectados: "${escapeHtml(sampleText)}..."</span>`;
            } else {
                checklistScannerDesc.textContent = 'Exibir anotações técnicas e códigos gravados (nenhum gravado nesta visita)';
            }
        }

        if (checklistManualDesc) checklistManualDesc.value = '';
        if (checklistManualQty) checklistManualQty.value = '1';

        renderChecklistItems(pecas, servicos);
        renderChecklistManualItems();

        if (modalChecklistConfig) {
            modalChecklistConfig.style.display = 'flex';
        }
    }

    function renderChecklistItems(pecas, servicos) {
        if (!checklistItemsList) return;
        checklistItemsList.innerHTML = '';

        const allItems = [];
        (pecas || []).forEach(p => allItems.push({ ...p, itemType: 'peca' }));
        (servicos || []).forEach(s => allItems.push({ ...s, itemType: 'servico' }));

        if (checklistItemsCount) {
            checklistItemsCount.textContent = String(allItems.length);
        }

        if (allItems.length === 0) {
            checklistItemsList.innerHTML = `
                <div style="padding: 12px; text-align: center; color: #64748b; font-size: 13px; font-style: italic;">
                    Nenhuma peça ou serviço registrado originalmente nesta visita. Você pode adicionar itens manualmente abaixo.
                </div>
            `;
            return;
        }

        allItems.forEach((it) => {
            const row = document.createElement('div');
            row.className = 'checklist-item-row';
            const isServico = it.itemType === 'servico';
            const typeLabel = isServico ? '🛠️ Serviço' : '🔩 Peça';
            const typeClass = isServico ? 'servico' : 'peca';
            const qty = it.quantity || '1';
            const desc = it.description || 'Item sem descrição';
            const comment = it.comment || '';

            row.innerHTML = `
                <input type="checkbox" class="chk-checklist-item" checked 
                       data-type="${typeClass}" 
                       data-qty="${escapeHtml(qty)}" 
                       data-desc="${escapeHtml(desc)}" 
                       data-comment="${escapeHtml(comment)}">
                <span class="badge-item-type ${typeClass}">${typeLabel}</span>
                <span class="checklist-item-qty">${escapeHtml(qty)}x</span>
                <span class="checklist-item-desc">${escapeHtml(desc)}${comment ? ` <small style="color: #64748b;">(Obs: ${escapeHtml(comment)})</small>` : ''}</span>
            `;

            row.addEventListener('click', (e) => {
                if (e.target.tagName !== 'INPUT') {
                    const cb = row.querySelector('.chk-checklist-item');
                    if (cb) cb.checked = !cb.checked;
                }
            });

            checklistItemsList.appendChild(row);
        });
    }

    function addChecklistManualItem() {
        if (!checklistManualDesc) return;
        const desc = checklistManualDesc.value.trim();
        if (!desc) {
            showToast('Informe a descrição do item a adicionar.');
            checklistManualDesc.focus();
            return;
        }
        const qty = (checklistManualQty && checklistManualQty.value.trim()) ? checklistManualQty.value.trim() : '1';
        const type = checklistManualType ? checklistManualType.value : 'peca';

        currentManualItems.push({
            type: type,
            quantity: qty,
            description: desc
        });

        checklistManualDesc.value = '';
        if (checklistManualQty) checklistManualQty.value = '1';
        renderChecklistManualItems();
        showToast('✓ Item adicionado ao checklist!');
    }

    function renderChecklistManualItems() {
        if (!checklistManualList) return;
        checklistManualList.innerHTML = '';
        if (currentManualItems.length === 0) {
            checklistManualList.style.display = 'none';
            return;
        }

        checklistManualList.style.display = 'flex';
        currentManualItems.forEach((mItem, idx) => {
            const row = document.createElement('div');
            row.className = 'manual-item-row';
            const isServico = mItem.type === 'servico';
            row.innerHTML = `
                <div class="manual-item-left">
                    <span class="badge-item-type ${isServico ? 'servico' : 'peca'}">${isServico ? '🛠️ Serviço' : '🔩 Peça'}</span>
                    <strong>${escapeHtml(mItem.quantity)}x</strong>
                    <span>${escapeHtml(mItem.description)}</span>
                    <span style="font-size: 11px; color: #854d0e; font-weight: 600;">(Manual)</span>
                </div>
                <button type="button" class="btn-del-manual-item" title="Remover item">✕</button>
            `;
            row.querySelector('.btn-del-manual-item').addEventListener('click', (e) => {
                e.stopPropagation();
                currentManualItems.splice(idx, 1);
                renderChecklistManualItems();
            });
            checklistManualList.appendChild(row);
        });
    }

    function closeChecklistConfigModal() {
        if (modalChecklistConfig) {
            modalChecklistConfig.style.display = 'none';
        }
    }

    function submitChecklistForm(autoPrint = false) {
        if (!currentChecklistVisit) return;

        const selectedItems = [];
        if (checklistItemsList) {
            const checkboxes = checklistItemsList.querySelectorAll('.chk-checklist-item:checked');
            checkboxes.forEach(cb => {
                selectedItems.push({
                    type: cb.dataset.type,
                    quantity: cb.dataset.qty,
                    description: cb.dataset.desc,
                    comment: cb.dataset.comment || ''
                });
            });
        }

        // Adiciona itens manuais
        currentManualItems.forEach(mi => {
            selectedItems.push(mi);
        });

        const includeScanner = chkChecklistScanner ? chkChecklistScanner.checked : true;

        const payload = {
            file_path: currentChecklistVisit.file_path,
            plate: currentChecklistVisit.plate_clean || currentChecklistVisit.plate,
            include_scanner: includeScanner,
            auto_print: autoPrint,
            items: selectedItems
        };

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/checklist_pdf';
        form.target = '_blank';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'config_json';
        input.value = JSON.stringify(payload);
        form.appendChild(input);

        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);

        closeChecklistConfigModal();
    }

    function openPrintVisitsSelectionModal(withoutPrices = false) {
        if (!currentCarHistory || !currentCarHistory.visits || currentCarHistory.visits.length === 0) {
            showToast('Nenhum veículo com visitas carregado.');
            return;
        }

        currentPrintVisits = currentCarHistory._sortedVisits || currentCarHistory.visits;
        const plate = currentCarHistory.vehicle?.plate || currentPrintVisits[0]?.plate_display || currentPrintVisits[0]?.plate || 'SEM PLACA';
        const car = currentPrintVisits[0]?.car_model || 'Veículo';
        const client = currentPrintVisits[0]?.client_name || '';

        if (printVisitsModalSubtitle) {
            printVisitsModalSubtitle.textContent = `Veículo: ${plate} • ${car} (${client}) • Total: ${currentPrintVisits.length} visitas`;
        }

        if (chkPrintNoPrices) {
            chkPrintNoPrices.checked = Boolean(withoutPrices);
        }
        if (chkPrintExpandServices) {
            chkPrintExpandServices.checked = true;
        }

        renderPrintVisitsList();

        if (modalPrintVisitsSelection) {
            modalPrintVisitsSelection.style.display = 'flex';
        }
    }

    function renderPrintVisitsList() {
        if (!printVisitsScrollList) return;
        printVisitsScrollList.innerHTML = '';

        currentPrintVisits.forEach((v, idx) => {
            const row = document.createElement('div');
            row.className = 'print-visit-row selected';
            row.dataset.visitIdx = String(idx);

            const vNum = v.visit_num || String(currentPrintVisits.length - idx);
            const dateStr = v.entry_date || 'Sem data';
            const kmStr = v.odometer ? `${formatKm(v.odometer)}` : 'KM não inf.';
            const complaintStr = v.complaint || 'Revisão / Manutenção preventiva';
            
            const details = v.details || {};
            const totalGeral = details.total_geral || '';

            row.innerHTML = `
                <input type="checkbox" class="chk-pv-item" checked data-idx="${idx}">
                <div class="pvr-details">
                    <div class="pvr-top">
                        <span class="pvr-badge-num">Visita #${escapeHtml(vNum)}</span>
                        <span class="pvr-date">📅 ${escapeHtml(dateStr)}</span>
                        <span class="pvr-km">⏱️ ${escapeHtml(kmStr)}</span>
                        ${totalGeral ? `<span class="pvr-total">${escapeHtml(totalGeral)}</span>` : ''}
                    </div>
                    <div class="pvr-complaint">${escapeHtml(complaintStr)}</div>
                </div>
            `;

            row.addEventListener('click', (e) => {
                if (e.target.tagName !== 'INPUT') {
                    const cb = row.querySelector('.chk-pv-item');
                    if (cb) {
                        cb.checked = !cb.checked;
                        row.classList.toggle('selected', cb.checked);
                        updatePrintVisitsCounter();
                    }
                }
            });

            const cb = row.querySelector('.chk-pv-item');
            cb.addEventListener('change', () => {
                row.classList.toggle('selected', cb.checked);
                updatePrintVisitsCounter();
            });

            printVisitsScrollList.appendChild(row);
        });

        updatePrintVisitsCounter();
    }

    function updatePrintVisitsCounter() {
        if (!printVisitsScrollList || !printVisitsCounterText) return;
        const total = currentPrintVisits.length;
        const checked = printVisitsScrollList.querySelectorAll('.chk-pv-item:checked').length;
        printVisitsCounterText.textContent = `${checked} de ${total} visitas selecionadas para impressão`;
    }

    function setPrintVisitsSelection(filterFn) {
        if (!printVisitsScrollList) return;
        const rows = printVisitsScrollList.querySelectorAll('.print-visit-row');
        rows.forEach((row, idx) => {
            const cb = row.querySelector('.chk-pv-item');
            const shouldCheck = filterFn(idx, currentPrintVisits.length);
            if (cb) {
                cb.checked = shouldCheck;
                row.classList.toggle('selected', shouldCheck);
            }
        });
        updatePrintVisitsCounter();
    }

    function closePrintVisitsSelectionModal() {
        if (modalPrintVisitsSelection) {
            modalPrintVisitsSelection.style.display = 'none';
        }
    }

    function executePrintSelectedVisits() {
        if (!printVisitsScrollList) return;
        const checkedBoxes = printVisitsScrollList.querySelectorAll('.chk-pv-item:checked');
        if (checkedBoxes.length === 0) {
            showToast('Selecione ao menos 1 visita para imprimir.');
            return;
        }

        const selectedIndices = new Set();
        checkedBoxes.forEach(cb => {
            selectedIndices.add(parseInt(cb.dataset.idx, 10));
        });

        const withoutPrices = chkPrintNoPrices ? chkPrintNoPrices.checked : false;
        const expandServices = chkPrintExpandServices ? chkPrintExpandServices.checked : true;

        if (withoutPrices) {
            document.body.classList.add('print-no-prices');
        } else {
            document.body.classList.remove('print-no-prices');
        }

        // Exclui da impressão na tela todos os cards cujo índice NÃO foi selecionado
        const allCards = document.querySelectorAll('.visit-card');
        allCards.forEach(card => {
            const idx = parseInt(card.dataset.visitIndex, 10);
            if (selectedIndices.has(idx)) {
                card.classList.remove('print-excluded');
                if (expandServices && typeof card._setServicesVisible === 'function') {
                    card._setServicesVisible(true);
                }
            } else {
                card.classList.add('print-excluded');
            }
        });

        // Oculta abas extras na impressão de histórico selecionado
        document.querySelectorAll('.extra-sheet-panel').forEach(p => p.classList.add('print-excluded'));

        // Fecha modal
        closePrintVisitsSelectionModal();

        // Dispara diálogo de impressão nativo
        setTimeout(() => {
            window.print();

            // Limpa as classes de exclusão após o diálogo de impressão
            const cleanupPrint = () => {
                document.body.classList.remove('print-no-prices');
                allCards.forEach(card => card.classList.remove('print-excluded'));
                document.querySelectorAll('.extra-sheet-panel').forEach(p => p.classList.remove('print-excluded'));
                window.removeEventListener('afterprint', cleanupPrint);
            };

            window.addEventListener('afterprint', cleanupPrint);
            setTimeout(cleanupPrint, 2500);
        }, 150);
    }

    function openConsolidatedHistoryPdfTab() {
        if (!printVisitsScrollList || !currentPrintVisits || currentPrintVisits.length === 0) return;
        const checkedBoxes = printVisitsScrollList.querySelectorAll('.chk-pv-item:checked');
        if (checkedBoxes.length === 0) {
            showToast('Selecione ao menos 1 visita para gerar o relatório.');
            return;
        }

        const selectedIndices = [];
        checkedBoxes.forEach(cb => {
            selectedIndices.push(parseInt(cb.dataset.idx, 10));
        });

        const withoutPrices = chkPrintNoPrices ? chkPrintNoPrices.checked : false;
        const plate = currentCarHistory?.vehicle?.plate || currentPrintVisits[0]?.plate_clean || currentPrintVisits[0]?.plate || '';

        const payload = {
            plate: plate,
            selected_indices: selectedIndices,
            without_prices: withoutPrices,
            auto_print: false
        };

        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/history_pdf';
        form.target = '_blank';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'config_json';
        input.value = JSON.stringify(payload);
        form.appendChild(input);

        document.body.appendChild(form);
        form.submit();
        document.body.removeChild(form);

        closePrintVisitsSelectionModal();
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

    // ==========================================
    // Integração do Pátio da Oficina (CP-06)
    // ==========================================
    const btnOpenPatioModal = document.getElementById('btn-open-patio-modal');
    const btnVehiclePatio = document.getElementById('btn-vehicle-patio');
    const patioModal = document.getElementById('patio-modal');
    const patioModalCloseBtn = document.getElementById('patio-modal-close-btn');
    const patioCarsList = document.getElementById('patio-cars-list');
    const patioListCount = document.getElementById('patio-list-count');
    const patioCarForm = document.getElementById('patio-car-form');
    const desktopPatioCarId = document.getElementById('desktop-patio-car-id');
    const desktopPatioPlate = document.getElementById('desktop-patio-plate');
    const desktopPatioClient = document.getElementById('desktop-patio-client');
    const desktopPatioModel = document.getElementById('desktop-patio-model');
    const desktopPatioColor = document.getElementById('desktop-patio-color');
    const desktopPatioStatus = document.getElementById('desktop-patio-status');
    const desktopPatioBox = document.getElementById('desktop-patio-box');
    const desktopPatioNotes = document.getElementById('desktop-patio-notes');
    const desktopThirdPartyBox = document.getElementById('desktop-third-party-box');
    const desktopPatioAuthName = document.getElementById('desktop-patio-auth-name');
    const desktopPatioAuthDoc = document.getElementById('desktop-patio-auth-doc');
    const desktopPatioAuthPhone = document.getElementById('desktop-patio-auth-phone');
    const btnDesktopPatioDelete = document.getElementById('btn-desktop-patio-delete');
    const btnDesktopPatioClear = document.getElementById('btn-desktop-patio-clear');

    function toggleDesktopThirdParty() {
        if (!desktopPatioStatus || !desktopThirdPartyBox) return;
        if (desktopPatioStatus.value === 'Liberado p/ Retirada por Terceiro') {
            desktopThirdPartyBox.style.display = 'flex';
            if (desktopPatioAuthName) desktopPatioAuthName.setAttribute('required', 'true');
            if (desktopPatioAuthDoc) desktopPatioAuthDoc.setAttribute('required', 'true');
        } else {
            desktopThirdPartyBox.style.display = 'none';
            if (desktopPatioAuthName) desktopPatioAuthName.removeAttribute('required');
            if (desktopPatioAuthDoc) desktopPatioAuthDoc.removeAttribute('required');
        }
    }
    if (desktopPatioStatus) {
        desktopPatioStatus.addEventListener('change', toggleDesktopThirdParty);
    }

    async function refreshDesktopPatioList() {
        if (!patioCarsList) return;
        try {
            const resp = await fetch('/api/patio', { cache: 'no-store' });
            const data = await resp.json();
            if (!data.success) return;

            const cars = data.cars || [];
            if (patioListCount) patioListCount.textContent = cars.length;

            if (cars.length === 0) {
                patioCarsList.innerHTML = '<div style="font-size: 13px; color: #94a3b8; font-style: italic; padding: 10px 0;">Nenhum veículo no pátio no momento.</div>';
                return;
            }

            patioCarsList.innerHTML = '';
            cars.forEach(car => {
                const row = document.createElement('div');
                row.className = 'patio-item-row';
                
                let badgeClass = 'patio-status-default';
                if (car.status === 'Liberado p/ Retirada por Terceiro') badgeClass = 'patio-status-terceiro';
                else if (car.status === 'Em Execução') badgeClass = 'patio-status-execucao';
                else if (car.status === 'Esperando Cliente Buscar') badgeClass = 'patio-status-pronto';

                let authInfo = '';
                if (car.status === 'Liberado p/ Retirada por Terceiro' && car.authorized_name) {
                    authInfo = `<span style="color: #ef4444; font-weight: 700;"> • 🔑 Autorizado: ${escapeHtml(car.authorized_name)} (Doc: ${escapeHtml(car.authorized_doc || 's/ doc')})</span>`;
                }

                row.innerHTML = `
                    <div class="patio-item-info">
                        <span class="patio-item-plate">${escapeHtml(car.plate_display || car.plate)}</span>
                        <div class="patio-item-details">
                            <span class="patio-item-model">${escapeHtml(car.car_model || 'Veículo')} ${car.car_color ? `(${escapeHtml(car.car_color)})` : ''} - 👤 ${escapeHtml(car.client_name || 'Cliente')}</span>
                            <span class="patio-item-sub">${car.box_mecanico ? `🔧 ${escapeHtml(car.box_mecanico)} ` : ''}${car.notes ? `• ${escapeHtml(car.notes)}` : ''}${authInfo}</span>
                        </div>
                    </div>
                    <span class="patio-status-badge ${badgeClass}">${escapeHtml(car.status)}</span>
                `;

                row.style.cursor = 'pointer';
                row.title = 'Clique para editar os dados deste carro';
                row.addEventListener('click', () => {
                    populateDesktopPatioForm(car);
                });

                patioCarsList.appendChild(row);
            });
        } catch (e) {
            console.error('Erro ao carregar lista de pátio:', e);
        }
    }

    function populateDesktopPatioForm(car) {
        if (!desktopPatioCarId) return;
        desktopPatioCarId.value = car.id || '';
        desktopPatioPlate.value = car.plate || '';
        desktopPatioClient.value = car.client_name || '';
        desktopPatioModel.value = car.car_model || '';
        desktopPatioColor.value = car.car_color || '';
        desktopPatioStatus.value = car.status || 'Em Diagnóstico';
        desktopPatioBox.value = car.box_mecanico || '';
        desktopPatioNotes.value = car.notes || '';
        desktopPatioAuthName.value = car.authorized_name || '';
        desktopPatioAuthDoc.value = car.authorized_doc || '';
        desktopPatioAuthPhone.value = car.authorized_phone || '';

        if (btnDesktopPatioDelete) btnDesktopPatioDelete.style.display = car.id ? 'inline-block' : 'none';
        toggleDesktopThirdParty();
    }

    function clearDesktopPatioForm() {
        if (!desktopPatioCarId) return;
        desktopPatioCarId.value = '';
        desktopPatioPlate.value = '';
        desktopPatioClient.value = '';
        desktopPatioModel.value = '';
        desktopPatioColor.value = '';
        desktopPatioStatus.value = 'Em Diagnóstico';
        desktopPatioBox.value = '';
        desktopPatioNotes.value = '';
        desktopPatioAuthName.value = '';
        desktopPatioAuthDoc.value = '';
        desktopPatioAuthPhone.value = '';
        if (btnDesktopPatioDelete) btnDesktopPatioDelete.style.display = 'none';
        toggleDesktopThirdParty();
    }

    if (btnOpenPatioModal) {
        btnOpenPatioModal.addEventListener('click', () => {
            clearDesktopPatioForm();
            refreshDesktopPatioList();
            if (patioModal) patioModal.style.display = 'flex';
        });
    }

    if (btnVehiclePatio) {
        btnVehiclePatio.addEventListener('click', async () => {
            if (!currentCarHistory || currentCarHistory.length === 0) return;
            const latest = currentCarHistory[0];
            const plate = latest.plate_display || latest.plate || '';

            clearDesktopPatioForm();
            desktopPatioPlate.value = plate;
            desktopPatioClient.value = latest.client_name || '';
            desktopPatioModel.value = latest.car_model || '';
            desktopPatioColor.value = latest.car_color || '';

            // Verifica se o carro já está no pátio para preencher id e status
            try {
                const resp = await fetch('/api/patio', { cache: 'no-store' });
                const data = await resp.json();
                if (data.success && data.cars) {
                    const found = data.cars.find(c => c.plate_clean === latest.plate_clean);
                    if (found) {
                        populateDesktopPatioForm(found);
                    }
                }
            } catch (e) {}

            refreshDesktopPatioList();
            if (patioModal) patioModal.style.display = 'flex';
        });
    }

    if (patioModalCloseBtn) {
        patioModalCloseBtn.addEventListener('click', () => {
            if (patioModal) patioModal.style.display = 'none';
        });
    }

    if (btnDesktopPatioClear) {
        btnDesktopPatioClear.addEventListener('click', clearDesktopPatioForm);
    }

    if (patioModal) {
        patioModal.addEventListener('click', (e) => {
            if (e.target === patioModal) patioModal.style.display = 'none';
        });
    }

    if (patioCarForm) {
        patioCarForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                id: desktopPatioCarId.value ? parseInt(desktopPatioCarId.value, 10) : null,
                plate: desktopPatioPlate.value.trim(),
                client_name: desktopPatioClient.value.trim(),
                car_model: desktopPatioModel.value.trim(),
                car_color: desktopPatioColor.value.trim(),
                status: desktopPatioStatus.value,
                box_mecanico: desktopPatioBox.value.trim(),
                notes: desktopPatioNotes.value.trim(),
                authorized_name: desktopPatioAuthName.value.trim(),
                authorized_doc: desktopPatioAuthDoc.value.trim(),
                authorized_phone: desktopPatioAuthPhone.value.trim()
            };

            try {
                const resp = await fetch('/api/patio', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (data.success) {
                    showToast(`Veículo ${payload.plate} atualizado no pátio da TV!`);
                    clearDesktopPatioForm();
                    refreshDesktopPatioList();
                } else {
                    alert(`Erro: ${data.error || 'Falha ao salvar'}`);
                }
            } catch (err) {
                alert(`Erro de conexão: ${err.message}`);
            }
        });
    }

    if (btnDesktopPatioDelete) {
        btnDesktopPatioDelete.addEventListener('click', async () => {
            const carId = desktopPatioCarId.value;
            if (!carId) return;
            const plate = desktopPatioPlate.value.trim();
            if (!confirm(`Confirma remover o veículo ${plate} do pátio?`)) return;

            try {
                const resp = await fetch(`/api/patio/${carId}`, { method: 'DELETE' });
                const data = await resp.json();
                if (data.success) {
                    showToast(`Veículo ${plate} removido do pátio.`);
                    clearDesktopPatioForm();
                    refreshDesktopPatioList();
                } else {
                    alert(`Erro: ${data.error || 'Falha ao remover'}`);
                }
            } catch (err) {
                alert(`Erro ao remover: ${err.message}`);
            }
        });
    }

    // =========================================================================
    // MECATRONICAR v2.0 - CONTROLADORES DE NOVA OS E MOTOR EXCEL (CP-03)
    // =========================================================================
    const btnOpenNewOs = document.getElementById('btn-open-new-os');
    const btnVehicleNewVisit = document.getElementById('btn-vehicle-new-visit');
    const osModal = document.getElementById('os-modal');
    const osModalTitle = document.getElementById('os-modal-title');
    const osModalCloseBtn = document.getElementById('os-modal-close-btn');
    const osModalCancel = document.getElementById('os-modal-cancel');
    const osModalSave = document.getElementById('os-modal-save');
    const osSearchClient = document.getElementById('os-search-client');
    const osAutocompleteDropdown = document.getElementById('os-autocomplete-dropdown');
    const osExistingFilePath = document.getElementById('os-existing-file-path');
    const osPlateLookupBadge = document.getElementById('os-plate-lookup-badge');
    const osPlateSpinner = document.getElementById('os-plate-spinner');
    const osVisitSuggestedHint = document.getElementById('os-visit-suggested-hint');
    const osLastOdometerHint = document.getElementById('os-last-odometer-hint');

    // Campos do formulário
    const osCarPlate = document.getElementById('os-car-plate');
    const osCarModel = document.getElementById('os-car-model');
    const osCarBrand = document.getElementById('os-car-brand');
    const osCarYear = document.getElementById('os-car-year');
    const osCarColor = document.getElementById('os-car-color');
    const osCarFuel = document.getElementById('os-car-fuel');
    const osCarChassis = document.getElementById('os-car-chassis');
    const osVisitNum = document.getElementById('os-visit-num');
    const osOdometer = document.getElementById('os-odometer');
    const osEntryDate = document.getElementById('os-entry-date');
    const osEntryTime = document.getElementById('os-entry-time');
    const osPatioStatus = document.getElementById('os-patio-status');
    const osPaymentMethod = document.getElementById('os-payment-method');
    const osComplaint = document.getElementById('os-complaint');

    const osClientName = document.getElementById('os-client-name');
    const osClientPhone = document.getElementById('os-client-phone');
    const osClientCpf = document.getElementById('os-client-cpf');
    const osClientRg = document.getElementById('os-client-rg');
    const osClientAddress = document.getElementById('os-client-address');
    const osClientNum = document.getElementById('os-client-num');
    const osClientCompl = document.getElementById('os-client-compl');
    const osClientBairro = document.getElementById('os-client-bairro');
    const osClientCity = document.getElementById('os-client-city');
    const osClientCep = document.getElementById('os-client-cep');
    const osClientTelRes = document.getElementById('os-client-tel-res');
    const osClientTelCom = document.getElementById('os-client-tel-com');
    const osClientEmail = document.getElementById('os-client-email');

    // Tabelas e Totais
    const btnAddPecaRow = document.getElementById('btn-add-peca-row');
    const btnAddServicoRow = document.getElementById('btn-add-servico-row');
    const osPecasTbody = document.getElementById('os-pecas-tbody');
    const osServicosTbody = document.getElementById('os-servicos-tbody');
    const osPecasChips = document.getElementById('os-pecas-chips');
    const osServicosChips = document.getElementById('os-servicos-chips');
    const osDatalistPecas = document.getElementById('os-datalist-pecas');
    const osDatalistServicos = document.getElementById('os-datalist-servicos');
    const osDiscountInput = document.getElementById('os-discount');

    let quickSuggestionsCache = null;
    let plateLookupDebounce = null;

    function cleanPlateStr(plateStr) {
        if (!plateStr) return '';
        return String(plateStr).toUpperCase().replace(/[^A-Z0-9]/g, '').trim();
    }

    function formatDateBr(dateObj) {
        const d = dateObj || new Date();
        const dd = String(d.getDate()).padStart(2, '0');
        const mm = String(d.getMonth() + 1).padStart(2, '0');
        const yyyy = d.getFullYear();
        return `${dd}/${mm}/${yyyy}`;
    }

    function formatTimeBr(dateObj) {
        const d = dateObj || new Date();
        const hh = String(d.getHours()).padStart(2, '0');
        const mm = String(d.getMinutes()).padStart(2, '0');
        return `${hh}:${mm}`;
    }

    function parseVal(v) {
        if (!v) return 0;
        const s = String(v).replace('R$', '').replace(/\./g, '').replace(',', '.').trim();
        const f = parseFloat(s);
        return isNaN(f) ? 0 : f;
    }

    function formatMoeda(val) {
        const n = typeof val === 'number' ? val : parseVal(val);
        return 'R$ ' + n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    async function loadQuickSuggestions() {
        if (quickSuggestionsCache) {
            renderQuickSuggestions(quickSuggestionsCache);
            return;
        }
        try {
            const res = await fetch('/api/quick_suggestions');
            const data = await res.json();
            quickSuggestionsCache = data;
            renderQuickSuggestions(data);
        } catch (e) {
            console.error('Erro ao carregar sugestões rápidas:', e);
        }
    }

    function renderQuickSuggestions(data) {
        const pecas = (data && data.pecas) || [];
        const servicos = (data && data.servicos) || [];

        // Preenche datalists para autocompletar ao digitar
        if (osDatalistPecas) {
            osDatalistPecas.innerHTML = pecas.map(p => `<option value="${escapeHtml(p)}">`).join('');
        }
        if (osDatalistServicos) {
            osDatalistServicos.innerHTML = servicos.map(s => `<option value="${escapeHtml(s)}">`).join('');
        }

        // Renderiza Chips Rápidos de Peças
        if (osPecasChips) {
            osPecasChips.innerHTML = '';
            pecas.slice(0, 10).forEach(pText => {
                const chip = document.createElement('span');
                chip.className = 'os-chip os-chip-peca';
                chip.textContent = `+ ${pText}`;
                chip.title = `Clique para adicionar ${pText} à lista de peças`;
                chip.addEventListener('click', () => {
                    addOrFillPeca(pText);
                });
                osPecasChips.appendChild(chip);
            });
        }

        // Renderiza Chips Rápidos de Serviços
        if (osServicosChips) {
            osServicosChips.innerHTML = '';
            servicos.slice(0, 8).forEach(sText => {
                const chip = document.createElement('span');
                chip.className = 'os-chip os-chip-servico';
                chip.textContent = `+ ${sText}`;
                chip.title = `Clique para adicionar ${sText} à lista de serviços`;
                chip.addEventListener('click', () => {
                    addOrFillServico(sText);
                });
                osServicosChips.appendChild(chip);
            });
        }
    }

    function addOrFillPeca(desc) {
        const rows = osPecasTbody.querySelectorAll('tr');
        for (const tr of rows) {
            const descInp = tr.querySelector('.peca-desc');
            if (descInp && !descInp.value.trim()) {
                descInp.value = desc;
                const unitInp = tr.querySelector('.peca-unit');
                if (unitInp) unitInp.focus();
                recalcOsTotals();
                return;
            }
        }
        addPecaRow(desc, 1, '');
        const newRows = osPecasTbody.querySelectorAll('tr');
        const lastRow = newRows[newRows.length - 1];
        if (lastRow) {
            const unitInp = lastRow.querySelector('.peca-unit');
            if (unitInp) unitInp.focus();
        }
        recalcOsTotals();
    }

    function addOrFillServico(desc) {
        const rows = osServicosTbody.querySelectorAll('tr');
        for (const tr of rows) {
            const descInp = tr.querySelector('.servico-desc');
            if (descInp && !descInp.value.trim()) {
                descInp.value = desc;
                const unitInp = tr.querySelector('.servico-unit');
                if (unitInp) unitInp.focus();
                recalcOsTotals();
                return;
            }
        }
        addServicoRow(desc, 1, '');
        const newRows = osServicosTbody.querySelectorAll('tr');
        const lastRow = newRows[newRows.length - 1];
        if (lastRow) {
            const unitInp = lastRow.querySelector('.servico-unit');
            if (unitInp) unitInp.focus();
        }
        recalcOsTotals();
    }

    function addPecaRow(desc = '', qty = 1, unit = '') {
        const tr = document.createElement('tr');
        const totalInit = (parseFloat(qty) || 1) * parseVal(unit);
        tr.innerHTML = `
            <td>
                <input type="text" class="os-table-input peca-desc" list="os-datalist-pecas" placeholder="Ex: Óleo 5W30 Sintético, Filtro de Óleo" value="${escapeHtml(desc)}">
            </td>
            <td>
                <input type="number" step="any" min="0" class="os-table-input peca-qty" value="${qty}" style="text-align: center;">
            </td>
            <td>
                <input type="text" class="os-table-input peca-unit" placeholder="0,00" value="${unit ? (typeof unit === 'number' ? unit.toFixed(2).replace('.', ',') : unit) : ''}" style="text-align: right;">
            </td>
            <td>
                <input type="text" class="os-table-input peca-total" readonly value="${formatMoeda(totalInit)}" style="text-align: right;">
            </td>
            <td style="text-align: center;">
                <button type="button" class="btn-remove-row" title="Remover Peça">🗑️</button>
            </td>
        `;

        const qtyInp = tr.querySelector('.peca-qty');
        const unitInp = tr.querySelector('.peca-unit');
        const totalInp = tr.querySelector('.peca-total');

        function updateRowTotal() {
            const q = parseFloat(qtyInp.value) || 0;
            const u = parseVal(unitInp.value);
            totalInp.value = formatMoeda(q * u);
            recalcOsTotals();
        }

        qtyInp.addEventListener('input', updateRowTotal);
        unitInp.addEventListener('input', updateRowTotal);
        tr.querySelector('.peca-desc').addEventListener('input', recalcOsTotals);

        tr.querySelector('.btn-remove-row').addEventListener('click', () => {
            tr.remove();
            recalcOsTotals();
        });

        osPecasTbody.appendChild(tr);
    }

    function addServicoRow(desc = '', qty = 1, unit = '') {
        const tr = document.createElement('tr');
        const totalInit = (parseFloat(qty) || 1) * parseVal(unit);
        tr.innerHTML = `
            <td>
                <input type="text" class="os-table-input servico-desc" list="os-datalist-servicos" placeholder="Ex: Troca de óleo e filtros, Alinhamento 3D" value="${escapeHtml(desc)}">
            </td>
            <td>
                <input type="number" step="any" min="0" class="os-table-input servico-qty" value="${qty}" style="text-align: center;">
            </td>
            <td>
                <input type="text" class="os-table-input servico-unit" placeholder="0,00" value="${unit ? (typeof unit === 'number' ? unit.toFixed(2).replace('.', ',') : unit) : ''}" style="text-align: right;">
            </td>
            <td>
                <input type="text" class="os-table-input servico-total" readonly value="${formatMoeda(totalInit)}" style="text-align: right;">
            </td>
            <td style="text-align: center;">
                <button type="button" class="btn-remove-row" title="Remover Serviço">🗑️</button>
            </td>
        `;

        const qtyInp = tr.querySelector('.servico-qty');
        const unitInp = tr.querySelector('.servico-unit');
        const totalInp = tr.querySelector('.servico-total');

        function updateRowTotal() {
            const q = parseFloat(qtyInp.value) || 0;
            const u = parseVal(unitInp.value);
            totalInp.value = formatMoeda(q * u);
            recalcOsTotals();
        }

        qtyInp.addEventListener('input', updateRowTotal);
        unitInp.addEventListener('input', updateRowTotal);
        tr.querySelector('.servico-desc').addEventListener('input', recalcOsTotals);

        tr.querySelector('.btn-remove-row').addEventListener('click', () => {
            tr.remove();
            recalcOsTotals();
        });

        osServicosTbody.appendChild(tr);
    }

    function recalcOsTotals() {
        let sumPecas = 0;
        osPecasTbody.querySelectorAll('tr').forEach(tr => {
            const q = parseFloat(tr.querySelector('.peca-qty')?.value) || 0;
            const u = parseVal(tr.querySelector('.peca-unit')?.value);
            sumPecas += (q * u);
        });

        let sumServicos = 0;
        osServicosTbody.querySelectorAll('tr').forEach(tr => {
            const q = parseFloat(tr.querySelector('.servico-qty')?.value) || 0;
            const u = parseVal(tr.querySelector('.servico-unit')?.value);
            sumServicos += (q * u);
        });

        const disc = parseVal(osDiscountInput?.value);
        const subtotal = sumPecas + sumServicos;
        const total = Math.max(0, subtotal - disc);

        const elPecas = document.getElementById('os-sum-pecas');
        const elServ = document.getElementById('os-sum-servicos');
        const elTotal = document.getElementById('os-sum-total');

        if (elPecas) elPecas.textContent = formatMoeda(sumPecas);
        if (elServ) elServ.textContent = formatMoeda(sumServicos);
        if (elTotal) elTotal.textContent = formatMoeda(total);
    }

    async function handlePlateLookup(rawPlate) {
        const clean = cleanPlateStr(rawPlate);
        if (clean.length < 5) return;

        if (osPlateSpinner) osPlateSpinner.style.display = 'block';

        try {
            const res = await fetch(`/api/car_lookup/${encodeURIComponent(clean)}`);
            const data = await res.json();

            if (osPlateSpinner) osPlateSpinner.style.display = 'none';

            if (data && data.found) {
                // Autocompleta Dados do Cliente
                const c = data.client || {};
                if (c.client_name) osClientName.value = c.client_name;
                if (c.phone) osClientPhone.value = c.phone;
                if (c.phone_res) osClientTelRes.value = c.phone_res;
                if (c.phone_com) osClientTelCom.value = c.phone_com;
                if (c.cpf) osClientCpf.value = c.cpf;
                if (c.rg) osClientRg.value = c.rg;
                if (c.email) osClientEmail.value = c.email;
                if (c.address) osClientAddress.value = c.address;
                if (c.address_num) osClientNum.value = c.address_num;
                if (c.address_compl) osClientCompl.value = c.address_compl;
                if (c.neighborhood) osClientBairro.value = c.neighborhood;
                if (c.city) osClientCity.value = c.city || 'Santos';
                if (c.cep) osClientCep.value = c.cep;

                // Autocompleta Dados do Veículo
                const v = data.car || {};
                if (v.car_model) osCarModel.value = v.car_model;
                if (v.car_brand) osCarBrand.value = v.car_brand;
                if (v.car_year) osCarYear.value = v.car_year;
                if (v.car_color) osCarColor.value = v.car_color;
                if (v.car_fuel) osCarFuel.value = v.car_fuel;
                if (v.car_chassis) osCarChassis.value = v.car_chassis;

                // Sugere automaticamente Visita N + 1
                if (!osExistingFilePath.value) {
                    osVisitNum.value = data.suggested_visit_num || '1';
                }

                if (osVisitSuggestedHint) {
                    osVisitSuggestedHint.textContent = `✨ Sugerido: Visita ${data.suggested_visit_num} (última: ${data.max_visit_num})`;
                }

                if (osPlateLookupBadge) {
                    osPlateLookupBadge.style.display = 'inline-flex';
                    osPlateLookupBadge.className = 'os-plate-badge found';
                    osPlateLookupBadge.textContent = `🟢 Veículo Recorrente (${data.visits_count} visitas)`;
                }

                if (osLastOdometerHint) {
                    osLastOdometerHint.textContent = data.last_odometer ? `Último KM: ${data.last_odometer} km` : '';
                }
            } else {
                // Veículo novo
                if (!osExistingFilePath.value && (!osVisitNum.value || osVisitNum.value === '1')) {
                    osVisitNum.value = '1';
                }
                if (osVisitSuggestedHint) {
                    osVisitSuggestedHint.textContent = '1ª visita na oficina';
                }
                if (osPlateLookupBadge) {
                    osPlateLookupBadge.style.display = 'inline-flex';
                    osPlateLookupBadge.className = 'os-plate-badge new';
                    osPlateLookupBadge.textContent = '🆕 Novo Veículo na Oficina';
                }
                if (osLastOdometerHint) {
                    osLastOdometerHint.textContent = '';
                }
            }
        } catch (err) {
            if (osPlateSpinner) osPlateSpinner.style.display = 'none';
            console.error('Erro no car_lookup:', err);
        }
    }

    function openNewOsModal(prefillPlate = '') {
        document.getElementById('os-form').reset();
        osExistingFilePath.value = '';

        if (osModalTitle) osModalTitle.textContent = '🛠️ Nova Visita / Ordem de Serviço';
        if (osModalSave) osModalSave.textContent = '💾 Salvar Ficha no Excel (.xlsx) e Sistema';

        // Preenche data e hora de hoje
        const now = new Date();
        osEntryDate.value = formatDateBr(now);
        osEntryTime.value = formatTimeBr(now);
        osPatioStatus.value = 'Em Diagnóstico';
        osPaymentMethod.value = '';

        osPecasTbody.innerHTML = '';
        osServicosTbody.innerHTML = '';
        addPecaRow('', 1, '');
        addPecaRow('', 1, '');
        addServicoRow('', 1, '');

        if (osPlateLookupBadge) osPlateLookupBadge.style.display = 'none';
        if (osVisitSuggestedHint) osVisitSuggestedHint.textContent = '';
        if (osLastOdometerHint) osLastOdometerHint.textContent = '';
        if (osAutocompleteDropdown) osAutocompleteDropdown.style.display = 'none';

        loadQuickSuggestions();
        recalcOsTotals();

        osModal.style.display = 'flex';

        if (prefillPlate) {
            osCarPlate.value = prefillPlate;
            handlePlateLookup(prefillPlate);
            setTimeout(() => osOdometer.focus(), 150);
        } else {
            setTimeout(() => osCarPlate.focus(), 150);
        }
    }

    function openOsModalForEdit(visit) {
        if (!visit) return;
        document.getElementById('os-form').reset();

        const det = visit.details || {};
        osExistingFilePath.value = visit.file_path || '';

        if (osModalTitle) {
            osModalTitle.textContent = `✏️ Editar Ordem de Serviço • Visita #${visit.visit_num || '1'} (${visit.plate_display || visit.plate || ''})`;
        }
        if (osModalSave) {
            osModalSave.textContent = '💾 Salvar Alterações na Planilha (.xlsx)';
        }

        // Dados do Veículo & Entrada
        osCarPlate.value = visit.plate_display || visit.plate || '';
        osCarModel.value = det.car_model || visit.car_model || '';
        osCarBrand.value = det.car_brand || '';
        osCarYear.value = det.car_year || visit.car_year || '';
        osCarColor.value = det.car_color || visit.car_color || '';
        osCarFuel.value = det.car_fuel || '';
        osCarChassis.value = det.car_chassis || '';
        osVisitNum.value = visit.visit_num || det.visit_num || '1';
        osOdometer.value = visit.odometer || det.odometer || '';
        osEntryDate.value = visit.entry_date || det.entry_date || formatDateBr(new Date());
        osEntryTime.value = det.entry_time || formatTimeBr(new Date());
        osPatioStatus.value = 'Em Execução';
        osPaymentMethod.value = det.payment_method || '';
        osComplaint.value = visit.complaint || det.complaint || '';

        if (osVisitSuggestedHint) osVisitSuggestedHint.textContent = `Visita atual da planilha: #${visit.visit_num || '1'}`;
        if (osLastOdometerHint) osLastOdometerHint.textContent = visit.odometer ? `KM atual: ${visit.odometer}` : '';
        if (osPlateLookupBadge) {
            osPlateLookupBadge.style.display = 'inline-flex';
            osPlateLookupBadge.className = 'os-plate-badge found';
            osPlateLookupBadge.textContent = '✏️ Editando Planilha Existente';
        }

        // Dados do Cliente
        osClientName.value = det.client_name || visit.client_name || '';
        osClientPhone.value = det.phone || '';
        osClientTelRes.value = det.tel_res || '';
        osClientTelCom.value = det.tel_com || '';
        osClientCpf.value = det.cpf || '';
        osClientRg.value = det.rg || '';
        osClientEmail.value = det.email || '';
        osClientAddress.value = det.address || '';
        osClientNum.value = det.address_num || '';
        osClientCompl.value = det.address_compl || '';
        osClientBairro.value = det.neighborhood || '';
        osClientCity.value = det.city || 'Santos';
        osClientCep.value = det.cep || '';

        // Peças
        osPecasTbody.innerHTML = '';
        const pecas = det.pecas_items || (det.items ? det.items.filter(i => i.section !== 'Serviço') : []);
        if (pecas && pecas.length > 0) {
            pecas.forEach(p => {
                addPecaRow(p.description || '', p.quantity || 1, p.unit_price || '');
            });
        } else {
            addPecaRow('', 1, '');
        }

        // Serviços
        osServicosTbody.innerHTML = '';
        const servicos = det.servicos_items || (det.items ? det.items.filter(i => i.section === 'Serviço') : []);
        if (servicos && servicos.length > 0) {
            servicos.forEach(s => {
                addServicoRow(s.description || '', s.quantity || 1, s.unit_price || '');
            });
        } else {
            addServicoRow('', 1, '');
        }

        // Desconto
        if (osDiscountInput) {
            osDiscountInput.value = det.discount ? (typeof det.discount === 'number' ? det.discount.toFixed(2).replace('.', ',') : det.discount) : '';
        }

        loadQuickSuggestions();
        recalcOsTotals();

        osModal.style.display = 'flex';
    }

    function closeOsModal() {
        osModal.style.display = 'none';
        if (osAutocompleteDropdown) osAutocompleteDropdown.style.display = 'none';
    }

    // Botões de Abertura da Modal
    if (btnOpenNewOs) {
        btnOpenNewOs.addEventListener('click', () => openNewOsModal());
    }

    if (btnVehicleNewVisit) {
        btnVehicleNewVisit.addEventListener('click', () => {
            const plate = currentVehiclePlate || (currentCarHistory && currentCarHistory.plate) || (detailPlate ? detailPlate.textContent : '');
            openNewOsModal(plate);
        });
    }

    if (osModalCloseBtn) osModalCloseBtn.addEventListener('click', closeOsModal);
    if (osModalCancel) osModalCancel.addEventListener('click', closeOsModal);

    // Listener para o input de Placa: formatação maiúscula e Autocomplete ao digitar
    if (osCarPlate) {
        osCarPlate.addEventListener('input', (e) => {
            const raw = e.target.value;
            const cleaned = cleanPlateStr(raw);
            if (raw !== cleaned) {
                e.target.value = cleaned;
            }
            clearTimeout(plateLookupDebounce);
            if (cleaned.length >= 7) {
                plateLookupDebounce = setTimeout(() => {
                    handlePlateLookup(cleaned);
                }, 200);
            } else {
                if (osPlateLookupBadge) osPlateLookupBadge.style.display = 'none';
            }
        });

        osCarPlate.addEventListener('blur', (e) => {
            const cleaned = cleanPlateStr(e.target.value);
            if (cleaned.length >= 5) {
                handlePlateLookup(cleaned);
            }
        });
    }

    if (btnAddPecaRow) btnAddPecaRow.addEventListener('click', () => addPecaRow());
    if (btnAddServicoRow) btnAddServicoRow.addEventListener('click', () => addServicoRow());
    if (osDiscountInput) osDiscountInput.addEventListener('input', recalcOsTotals);

    // Autocomplete no campo "Buscar Cliente ou Carro Já Cadastrado"
    let autocompleteTimeout = null;
    if (osSearchClient) {
        osSearchClient.addEventListener('input', () => {
            clearTimeout(autocompleteTimeout);
            const q = osSearchClient.value.trim();
            if (q.length < 2) {
                if (osAutocompleteDropdown) osAutocompleteDropdown.style.display = 'none';
                return;
            }
            autocompleteTimeout = setTimeout(async () => {
                try {
                    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
                    const data = await res.json();
                    const results = data.results || [];
                    if (results.length > 0) {
                        osAutocompleteDropdown.innerHTML = '';
                        const seenPlates = new Set();
                        results.forEach(r => {
                            const pClean = r.plate_clean || r.plate;
                            if (seenPlates.has(pClean)) return;
                            seenPlates.add(pClean);

                            const item = document.createElement('div');
                            item.className = 'os-autocomplete-item';
                            item.innerHTML = `
                                <div><strong>${escapeHtml(r.plate_display || r.plate)}</strong> • ${escapeHtml(r.car_model || '')} (${escapeHtml(r.car_color || '')})</div>
                                <div style="color: #64748b; font-size: 11px;">👤 ${escapeHtml(r.client_name || 'Cliente')} • Visitas: ${r.visit_num || '1'}</div>
                            `;
                            item.addEventListener('click', () => {
                                osCarPlate.value = r.plate_display || r.plate;
                                handlePlateLookup(r.plate_clean || r.plate);
                                osAutocompleteDropdown.style.display = 'none';
                                osSearchClient.value = `${r.plate_display || r.plate} - ${r.client_name || ''}`;
                            });
                            osAutocompleteDropdown.appendChild(item);
                        });
                        osAutocompleteDropdown.style.display = 'block';
                    } else {
                        osAutocompleteDropdown.style.display = 'none';
                    }
                } catch (e) {
                    osAutocompleteDropdown.style.display = 'none';
                }
            }, 250);
        });

        document.addEventListener('click', (e) => {
            if (osAutocompleteDropdown && !osSearchClient.contains(e.target) && !osAutocompleteDropdown.contains(e.target)) {
                osAutocompleteDropdown.style.display = 'none';
            }
        });
    }

    // Salvar Ficha no Excel (.xlsx) e no Sistema SQLite
    if (osModalSave) {
        osModalSave.addEventListener('click', async () => {
            const plate = osCarPlate.value.trim().toUpperCase();
            const clientName = osClientName.value.trim();
            const carModel = osCarModel.value.trim();

            if (!plate) {
                alert('Por favor, informe a Placa do Veículo.');
                osCarPlate.focus();
                return;
            }
            if (!clientName) {
                alert('Por favor, informe o Nome do Cliente.');
                osClientName.focus();
                return;
            }
            if (!carModel) {
                alert('Por favor, informe o Modelo do Veículo.');
                osCarModel.focus();
                return;
            }

            const pecasList = [];
            osPecasTbody.querySelectorAll('tr').forEach(tr => {
                const desc = tr.querySelector('.peca-desc')?.value.trim();
                const qty = parseFloat(tr.querySelector('.peca-qty')?.value) || 1;
                const unit = parseVal(tr.querySelector('.peca-unit')?.value);
                if (desc) {
                    pecasList.push({
                        description: desc,
                        desc: desc,
                        quantity: qty,
                        qty: qty,
                        unit_price: unit,
                        price: unit
                    });
                }
            });

            const servicosList = [];
            osServicosTbody.querySelectorAll('tr').forEach(tr => {
                const desc = tr.querySelector('.servico-desc')?.value.trim();
                const qty = parseFloat(tr.querySelector('.servico-qty')?.value) || 1;
                const unit = parseVal(tr.querySelector('.servico-unit')?.value);
                if (desc) {
                    servicosList.push({
                        description: desc,
                        desc: desc,
                        quantity: qty,
                        qty: qty,
                        unit_price: unit,
                        price: unit
                    });
                }
            });

            const payload = {
                existing_file_path: osExistingFilePath.value || null,
                client: {
                    name: clientName,
                    phone: osClientPhone.value.trim(),
                    tel_res: osClientTelRes.value.trim(),
                    tel_com: osClientTelCom.value.trim(),
                    cpf: osClientCpf.value.trim(),
                    rg: osClientRg.value.trim(),
                    email: osClientEmail.value.trim(),
                    address: osClientAddress.value.trim(),
                    address_num: osClientNum.value.trim(),
                    address_compl: osClientCompl.value.trim(),
                    neighborhood: osClientBairro.value.trim(),
                    city: osClientCity.value.trim() || 'Santos',
                    cep: osClientCep.value.trim()
                },
                car: {
                    plate: plate,
                    model: carModel,
                    brand: osCarBrand.value.trim(),
                    year: osCarYear.value.trim(),
                    color: osCarColor.value.trim(),
                    fuel: osCarFuel.value.trim(),
                    chassis: osCarChassis.value.trim()
                },
                os: {
                    visit_num: osVisitNum.value.trim() || '1',
                    odometer: osOdometer.value.trim(),
                    entry_date: osEntryDate.value.trim() || formatDateBr(new Date()),
                    entry_time: osEntryTime.value.trim() || formatTimeBr(new Date()),
                    payment_method: osPaymentMethod.value.trim(),
                    complaint: osComplaint.value.trim(),
                    discount: parseVal(osDiscountInput?.value)
                },
                patio_status: osPatioStatus.value || 'Em Diagnóstico',
                pecas: pecasList,
                servicos: servicosList
            };

            try {
                osModalSave.disabled = true;
                osModalSave.textContent = '⏳ Salvando no Excel e Sistema...';

                const res = await fetch('/api/save_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                const contentType = res.headers.get('content-type') || '';
                let data = null;

                if (contentType.includes('application/json')) {
                    try {
                        data = await res.json();
                    } catch (parseErr) {
                        throw new Error('Não foi possível interpretar a resposta do servidor (JSON inválido).');
                    }
                } else {
                    const rawText = await res.text().catch(() => '');
                    const cleanText = rawText.replace(/<[^>]*>?/gm, '').trim();
                    const snippet = cleanText ? (cleanText.length > 80 ? cleanText.substring(0, 80) + '...' : cleanText) : '';
                    throw new Error(`O servidor retornou um formato inesperado (${res.status} ${res.statusText || ''})${snippet ? `: ${snippet}` : ''}`);
                }

                if (res.ok && data && data.success) {
                    showToast(`🎉 Ficha salva com sucesso! Planilha: ${data.file_name || data.filename}`);
                    closeOsModal();

                    // Atualiza a visualização da tela
                    const savedPlate = data.plate || plate;
                    selectVehicleByPlate(savedPlate);
                } else {
                    const errorMsg = (data && data.error) ? data.error : `Erro HTTP ${res.status}: Não foi possível salvar a planilha no Excel.`;
                    alert('Erro ao salvar no Excel: ' + errorMsg);
                }
            } catch (err) {
                alert('Erro ao salvar ficha: ' + err.message);
            } finally {
                osModalSave.disabled = false;
                osModalSave.textContent = '💾 Salvar Ficha no Excel (.xlsx) e Sistema';
            }
        });
    }

    // =========================================================================
    // MECATRONICAR v2.0 - COPILOTO FISCAL (CP-07)
    // =========================================================================
    const btnOpenFiscalHub = document.getElementById('btn-open-fiscal-hub');
    const headerNfBadge = document.getElementById('header-nf-badge');
    const modalPendingCounter = document.getElementById('modal-pending-counter');
    const footerNfSummary = document.getElementById('footer-nf-summary');
    const btnVehicleFiscal = document.getElementById('btn-vehicle-fiscal');

    const fiscalModal = document.getElementById('fiscal-modal');
    const fiscalModalCloseBtn = document.getElementById('fiscal-modal-close-btn');
    const fiscalModalDismiss = document.getElementById('fiscal-modal-dismiss');
    const fiscalModalTitle = document.getElementById('fiscal-modal-title');
    const fiscalModalSubtitle = document.getElementById('fiscal-modal-subtitle');

    // Tabs
    const tabBtnNfse = document.getElementById('tab-btn-nfse');
    const tabBtnNfe = document.getElementById('tab-btn-nfe');
    const tabBtnTomador = document.getElementById('tab-btn-tomador');
    const tabBtnPending = document.getElementById('tab-btn-pending');
    const panelNfse = document.getElementById('panel-nfse');
    const panelNfe = document.getElementById('panel-nfe');
    const panelTomador = document.getElementById('panel-tomador');
    const panelPending = document.getElementById('panel-pending');

    // Tab 1 Elements - NFS-e
    const btnCopyNfseDesc = document.getElementById('btn-copy-nfse-desc');
    const nfseDescText = document.getElementById('nfse-desc-text');
    const pillCopyTomadorNfse = document.getElementById('pill-copy-tomador-nfse');
    const pillCopyCpfNfse = document.getElementById('pill-copy-cpf-nfse');
    const pillCopyCepNfse = document.getElementById('pill-copy-cep-nfse');
    const pillCopyAddrNfse = document.getElementById('pill-copy-addr-nfse');
    const pillCopyServVal = document.getElementById('pill-copy-serv-val');
    const nfseServicesList = document.getElementById('nfse-services-list');
    const nfseTotalVal = document.getElementById('nfse-total-val');
    const nfseCurrentStatusTag = document.getElementById('nfse-current-status-tag');
    const nfseNumberInput = document.getElementById('nfse-number-input');
    const nfseDateInput = document.getElementById('nfse-date-input');
    const btnMarkNfseDone = document.getElementById('btn-mark-nfse-done');

    // Tab 2 Elements - NF-e 55
    const btnCopyNfeSummary = document.getElementById('btn-copy-nfe-summary');
    const btnCopyNfeTsv = document.getElementById('btn-copy-nfe-tsv');
    const pillCopyPartsVal = document.getElementById('pill-copy-parts-val');
    const pillCopyTomadorNfe = document.getElementById('pill-copy-tomador-nfe');
    const nfeItemsTbody = document.getElementById('nfe-items-tbody');
    const nfeTotalVal = document.getElementById('nfe-total-val');
    const nfeCurrentStatusTag = document.getElementById('nfe-current-status-tag');
    const nfeNumberInput = document.getElementById('nfe-number-input');
    const nfeDateInput = document.getElementById('nfe-date-input');
    const btnMarkNfeDone = document.getElementById('btn-mark-nfe-done');

    // Tab 3 Elements - Tomador
    const btnCopyFullTomador = document.getElementById('btn-copy-full-tomador');
    const tomadorName = document.getElementById('tomador-name');
    const tomadorCpf = document.getElementById('tomador-cpf');
    const btnCopyCpfRaw = document.getElementById('btn-copy-cpf-raw');
    const tomadorPhone = document.getElementById('tomador-phone');
    const tomadorEmail = document.getElementById('tomador-email');
    const tomadorSingleLine = document.getElementById('tomador-single-line');
    const tomadorStreet = document.getElementById('tomador-street');
    const tomadorNeighborhood = document.getElementById('tomador-neighborhood');
    const tomadorCity = document.getElementById('tomador-city');
    const tomadorCep = document.getElementById('tomador-cep');
    const btnCopyCepRaw = document.getElementById('btn-copy-cep-raw');

    // Tab 4 Elements - Queue
    const kpiPendingVisits = document.getElementById('kpi-pending-visits');
    const kpiPendingServices = document.getElementById('kpi-pending-services');
    const kpiPendingServicesSub = document.getElementById('kpi-pending-services-sub');
    const kpiPendingParts = document.getElementById('kpi-pending-parts');
    const kpiPendingPartsSub = document.getElementById('kpi-pending-parts-sub');
    const kpiEmittedCount = document.getElementById('kpi-emitted-count');
    const queueSearchInput = document.getElementById('queue-search-input');
    const btnClearQueueSearch = document.getElementById('btn-clear-queue-search');
    const btnExportQueueCsv = document.getElementById('btn-export-queue-csv');
    const btnExportQueueTxt = document.getElementById('btn-export-queue-txt');
    const btnRefreshQueue = document.getElementById('btn-refresh-queue');
    const fiscalPendingList = document.getElementById('fiscal-pending-list');

    // State variables
    let currentFiscalFilePath = '';
    let currentFiscalPlate = '';
    let currentFiscalVisitNum = null;
    let currentFiscalData = null;
    let activeQueueFilter = 'pending';
    let queueSearchDebounceTimer = null;

    function copyToClipboard(text, successToastMsg) {
        if (!text) {
            showToast('⚠️ Nada para copiar.');
            return;
        }
        navigator.clipboard.writeText(text).then(() => {
            showToast(successToastMsg || '📋 Copiado com sucesso!');
        }).catch(err => {
            console.error('Falha ao copiar:', err);
            // Fallback para input temporário
            const tempInput = document.createElement('textarea');
            tempInput.value = text;
            document.body.appendChild(tempInput);
            tempInput.select();
            document.execCommand('copy');
            document.body.removeChild(tempInput);
            showToast(successToastMsg || '📋 Copiado com sucesso!');
        });
    }

    function switchFiscalTab(tab) {
        [tabBtnNfse, tabBtnNfe, tabBtnTomador, tabBtnPending].forEach(b => b?.classList.remove('active'));
        [panelNfse, panelNfe, panelTomador, panelPending].forEach(p => { if (p) p.style.display = 'none'; });

        if (tab === 'nfse') {
            tabBtnNfse?.classList.add('active');
            if (panelNfse) panelNfse.style.display = 'block';
        } else if (tab === 'nfe') {
            tabBtnNfe?.classList.add('active');
            if (panelNfe) panelNfe.style.display = 'block';
        } else if (tab === 'tomador') {
            tabBtnTomador?.classList.add('active');
            if (panelTomador) panelTomador.style.display = 'block';
        } else if (tab === 'pending') {
            tabBtnPending?.classList.add('active');
            if (panelPending) panelPending.style.display = 'block';
            loadFiscalPendingList();
        }
    }

    if (tabBtnNfse) tabBtnNfse.addEventListener('click', () => switchFiscalTab('nfse'));
    if (tabBtnNfe) tabBtnNfe.addEventListener('click', () => switchFiscalTab('nfe'));
    if (tabBtnTomador) tabBtnTomador.addEventListener('click', () => switchFiscalTab('tomador'));
    if (tabBtnPending) tabBtnPending.addEventListener('click', () => switchFiscalTab('pending'));

    async function updateHeaderFiscalBadge() {
        try {
            const res = await fetch('/api/nf/pending');
            const data = await res.json();
            if (data.success && data.stats) {
                const s = data.stats;
                const pendingCount = s.pending_visits_count || 0;

                if (headerNfBadge) {
                    headerNfBadge.textContent = pendingCount;
                    headerNfBadge.style.display = pendingCount > 0 ? 'inline-block' : 'none';
                }
                if (modalPendingCounter) {
                    modalPendingCounter.textContent = pendingCount;
                }
                if (footerNfSummary) {
                    footerNfSummary.textContent = `${pendingCount} visita(s) com emissão pendente`;
                }

                if (kpiPendingVisits) kpiPendingVisits.textContent = pendingCount;
                if (kpiPendingServices) kpiPendingServices.textContent = formatMoeda(s.total_pending_services_val || 0);
                if (kpiPendingServicesSub) kpiPendingServicesSub.textContent = `${s.pending_servicos_count || 0} visitas`;
                if (kpiPendingParts) kpiPendingParts.textContent = formatMoeda(s.total_pending_pecas_val || 0);
                if (kpiPendingPartsSub) kpiPendingPartsSub.textContent = `${s.pending_pecas_count || 0} visitas`;
                if (kpiEmittedCount) kpiEmittedCount.textContent = s.emitted_count || 0;
            }
        } catch (e) {
            console.warn('Erro ao atualizar badge fiscal:', e);
        }
    }

    async function openFiscalModal(filePath = null, plate = null, visitNum = null, initialTab = 'nfse') {
        currentFiscalFilePath = filePath || '';
        currentFiscalPlate = plate || (currentCarHistory?.vehicle?.plate) || '';
        currentFiscalVisitNum = visitNum || null;

        // Se não temos nem arquivo nem placa especificada, abre direto na fila de pendentes
        if (!currentFiscalFilePath && !currentFiscalPlate) {
            switchFiscalTab('pending');
            fiscalModal.style.display = 'flex';
            return;
        }

        switchFiscalTab(initialTab || 'nfse');
        fiscalModal.style.display = 'flex';

        // Feedback inicial de carregamento
        if (fiscalModalTitle) fiscalModalTitle.textContent = `Carregando Copiloto Fiscal...`;
        if (fiscalModalSubtitle) fiscalModalSubtitle.textContent = `Buscando dados da OS e cliente...`;
        if (nfseDescText) nfseDescText.value = 'Carregando discriminação formatada dos serviços...';
        if (nfseServicesList) nfseServicesList.innerHTML = '<div style="padding: 10px; color: #64748b; font-size: 12px;">Carregando serviços...</div>';
        if (nfeItemsTbody) nfeItemsTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 16px;">Carregando autopeças...</td></tr>';

        try {
            const queryParams = new URLSearchParams();
            if (currentFiscalFilePath) queryParams.set('file_path', currentFiscalFilePath);
            if (currentFiscalPlate) queryParams.set('plate', currentFiscalPlate);
            if (currentFiscalVisitNum) queryParams.set('visit_num', currentFiscalVisitNum);

            const res = await fetch(`/api/nf/data?${queryParams.toString()}`);
            const data = await res.json();

            if (!data.success) {
                alert('Erro ao carregar dados fiscais: ' + (data.error || 'Erro desconhecido'));
                return;
            }

            currentFiscalData = data;
            currentFiscalPlate = data.plate || currentFiscalPlate;
            currentFiscalFilePath = data.file_path || currentFiscalFilePath;
            currentFiscalVisitNum = data.visit_num || currentFiscalVisitNum;

            // 1. Header do Modal
            const plateDisp = data.plate_display || data.plate || 'OFICINA';
            const modelDisp = data.car_model || 'Veículo';
            if (fiscalModalTitle) {
                fiscalModalTitle.textContent = `Copiloto Fiscal • ${plateDisp} (${modelDisp})`;
            }
            if (fiscalModalSubtitle) {
                const clientDisp = data.tomador?.nome || data.client_name || 'Cliente';
                const dateDisp = data.entry_date || '-';
                const vNum = data.visit_num ? `Visita #${data.visit_num}` : 'OS';
                fiscalModalSubtitle.textContent = `${vNum} • Data: ${dateDisp} • Tomador: ${clientDisp}`;
            }

            // 2. Aba 1 - NFS-e Santos (Serviços)
            const nfse = data.nfse || {};
            if (nfseDescText) {
                nfseDescText.value = nfse.discriminacao_completa || data.discriminacao_nfse || '';
            }
            if (nfseTotalVal) {
                nfseTotalVal.textContent = formatMoeda(nfse.valor_servicos || data.valor_servicos || 0);
            }

            const nfseStatus = nfse.status || (data.nf_control && data.nf_control.status_servico) || 'pendente';
            const nfseNum = nfse.numero_nfse || (data.nf_control && data.nf_control.nf_servico_num) || '';
            const nfseDate = nfse.data_emissao || (data.nf_control && data.nf_control.data_emissao_servico) || new Date().toISOString().split('T')[0];

            if (nfseNumberInput) nfseNumberInput.value = nfseNum;
            if (nfseDateInput) nfseDateInput.value = nfseDate;

            if (nfseCurrentStatusTag) {
                if (nfseStatus === 'emitida') {
                    nfseCurrentStatusTag.className = 'badge-status-pill emitted';
                    nfseCurrentStatusTag.textContent = `✅ Emitida (NFS-e #${nfseNum || 'S/N'})`;
                } else if (nfse.valor_servicos === 0 && (nfse.itens_servico || []).length === 0) {
                    nfseCurrentStatusTag.className = 'badge-status-pill na';
                    nfseCurrentStatusTag.textContent = 'Não Aplicável (Sem Serviços)';
                } else {
                    nfseCurrentStatusTag.className = 'badge-status-pill pending';
                    nfseCurrentStatusTag.textContent = '⏳ Pendente';
                }
            }

            // Lista de Serviços
            if (nfseServicesList) {
                const sItems = nfse.itens_servico || [];
                if (sItems.length === 0) {
                    nfseServicesList.innerHTML = '<div style="padding: 10px; color: #64748b; font-size: 12px; font-style: italic;">Nenhum item discriminado como Mão de Obra / Serviço nesta OS.</div>';
                } else {
                    nfseServicesList.innerHTML = '';
                    sItems.forEach(s => {
                        const row = document.createElement('div');
                        row.className = 'fiscal-item-row';
                        row.innerHTML = `
                            <span class="fiscal-item-desc">🔧 ${escapeHtml(s.desc)} ${s.qty > 1 ? `(${s.qty}x)` : ''}</span>
                            <span class="fiscal-item-val">${formatMoeda(s.total || s.unit_price || 0)}</span>
                        `;
                        nfseServicesList.appendChild(row);
                    });
                }
            }

            // 3. Aba 2 - NF-e Modelo 55 (Peças)
            const nfe = data.nfe || {};
            if (nfeTotalVal) {
                nfeTotalVal.textContent = formatMoeda(nfe.valor_pecas || data.valor_pecas || 0);
            }

            const nfeStatus = nfe.status || (data.nf_control && data.nf_control.status_pecas) || 'pendente';
            const nfeNum = nfe.numero_nfe || (data.nf_control && data.nf_control.nf_pecas_num) || '';
            const nfeDate = nfe.data_emissao || (data.nf_control && data.nf_control.data_emissao_pecas) || new Date().toISOString().split('T')[0];

            if (nfeNumberInput) nfeNumberInput.value = nfeNum;
            if (nfeDateInput) nfeDateInput.value = nfeDate;

            if (nfeCurrentStatusTag) {
                if (nfeStatus === 'emitida') {
                    nfeCurrentStatusTag.className = 'badge-status-pill emitted';
                    nfeCurrentStatusTag.textContent = `✅ Emitida (NF-e #${nfeNum || 'S/N'})`;
                } else if (nfe.valor_pecas === 0 && (nfe.itens_pecas || []).length === 0) {
                    nfeCurrentStatusTag.className = 'badge-status-pill na';
                    nfeCurrentStatusTag.textContent = 'Não Aplicável (Sem Peças)';
                } else {
                    nfeCurrentStatusTag.className = 'badge-status-pill pending';
                    nfeCurrentStatusTag.textContent = '⏳ Pendente';
                }
            }

            // Tabela de Peças
            if (nfeItemsTbody) {
                const pItems = nfe.itens_pecas || data.pecas_nfe || [];
                if (pItems.length === 0) {
                    nfeItemsTbody.innerHTML = '<tr><td colspan="7" style="text-align: center; color: #64748b; padding: 18px; font-style: italic;">Nenhuma peça faturável nesta OS.</td></tr>';
                } else {
                    nfeItemsTbody.innerHTML = '';
                    pItems.forEach((p, idx) => {
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td style="color: #94a3b8; font-weight: 700;">${idx + 1}</td>
                            <td><strong>${escapeHtml(p.desc)}</strong></td>
                            <td style="text-align: right;">${p.qty || 1}</td>
                            <td style="text-align: right;">${formatMoeda(p.unit_price || 0)}</td>
                            <td style="text-align: right;"><strong>${formatMoeda(p.total || 0)}</strong></td>
                            <td style="text-align: center;"><span class="badge" style="background: #fef3c7; color: #92400e; font-weight: 700;">${p.cfop || '5.405'}</span></td>
                            <td><span class="badge" style="background: #f1f5f9; color: #0f172a; font-family: monospace; font-size: 11px;">${p.ncm_sugerido || '8708.29.99'}</span></td>
                        `;
                        nfeItemsTbody.appendChild(tr);
                    });
                }
            }

            // 4. Aba 3 - Dados do Tomador
            const t = data.tomador || {};
            if (tomadorName) tomadorName.textContent = t.nome || '-';
            if (tomadorCpf) tomadorCpf.textContent = t.cpf_formatado || t.cpf_cnpj || '-';
            if (tomadorPhone) tomadorPhone.textContent = t.telefone || '-';
            if (tomadorEmail) tomadorEmail.textContent = t.email || '-';
            if (tomadorSingleLine) tomadorSingleLine.textContent = t.endereco_linha_unica || '-';
            if (tomadorStreet) tomadorStreet.textContent = t.logradouro_numero || '-';
            if (tomadorNeighborhood) tomadorNeighborhood.textContent = t.bairro || '-';
            if (tomadorCity) tomadorCity.textContent = `${t.municipio || 'Santos'} / ${t.uf || 'SP'}`;
            if (tomadorCep) tomadorCep.textContent = t.cep || '-';

            // Atualiza resumo no rodapé
            updateHeaderFiscalBadge();

        } catch (err) {
            console.error('Erro carregando Copiloto Fiscal:', err);
            alert('Falha ao conectar com o servidor para abrir o Copiloto Fiscal.');
        }
    }

    // Ações de cópia em 1 clique
    if (btnCopyNfseDesc) {
        btnCopyNfseDesc.addEventListener('click', () => {
            copyToClipboard(nfseDescText?.value, '📋 Discriminação NFS-e copiada com sucesso!');
        });
    }

    if (pillCopyTomadorNfse) {
        pillCopyTomadorNfse.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.tomador?.resumo, '👤 Dados do Tomador copiados!');
        });
    }

    if (pillCopyCpfNfse) {
        pillCopyCpfNfse.addEventListener('click', () => {
            const rawCpf = (currentFiscalData?.tomador?.cpf_cnpj || '').replace(/\D/g, '');
            copyToClipboard(rawCpf, `🔢 CPF sem pontuação copiado: ${rawCpf}`);
        });
    }

    if (pillCopyCepNfse) {
        pillCopyCepNfse.addEventListener('click', () => {
            const rawCep = (currentFiscalData?.tomador?.cep || '').replace(/\D/g, '');
            copyToClipboard(rawCep, `📍 CEP copiado: ${rawCep}`);
        });
    }

    if (pillCopyAddrNfse) {
        pillCopyAddrNfse.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.tomador?.endereco_linha_unica, '🗺️ Endereço em 1 linha copiado!');
        });
    }

    if (pillCopyServVal) {
        pillCopyServVal.addEventListener('click', () => {
            const v = (currentFiscalData?.nfse?.valor_servicos || 0).toFixed(2).replace('.', ',');
            copyToClipboard(v, `💰 Valor de Mão de Obra copiado: R$ ${v}`);
        });
    }

    // Aba 2 - Cópia NF-e 55
    if (btnCopyNfeSummary) {
        btnCopyNfeSummary.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.nfe?.resumo_texto, '📋 Lista de Peças e Valores copiada!');
        });
    }

    if (btnCopyNfeTsv) {
        btnCopyNfeTsv.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.nfe?.tabela_tsv, '📊 Tabela TSV copiada! Pronta para colar no Excel ou Emissor Fiscal.');
        });
    }

    if (pillCopyPartsVal) {
        pillCopyPartsVal.addEventListener('click', () => {
            const v = (currentFiscalData?.nfe?.valor_pecas || 0).toFixed(2).replace('.', ',');
            copyToClipboard(v, `💰 Valor de Peças copiado: R$ ${v}`);
        });
    }

    if (pillCopyTomadorNfe) {
        pillCopyTomadorNfe.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.tomador?.resumo, '👤 Dados do Destinatário copiados!');
        });
    }

    // Aba 3 - Cópia Tomador
    if (btnCopyFullTomador) {
        btnCopyFullTomador.addEventListener('click', () => {
            copyToClipboard(currentFiscalData?.tomador?.resumo, '👤 Ficha cadastral do tomador copiada!');
        });
    }

    if (btnCopyCpfRaw) {
        btnCopyCpfRaw.addEventListener('click', () => {
            const rawCpf = (currentFiscalData?.tomador?.cpf_cnpj || '').replace(/\D/g, '');
            copyToClipboard(rawCpf, `🔢 CPF sem pontuação copiado: ${rawCpf}`);
        });
    }

    if (btnCopyCepRaw) {
        btnCopyCepRaw.addEventListener('click', () => {
            const rawCep = (currentFiscalData?.tomador?.cep || '').replace(/\D/g, '');
            copyToClipboard(rawCep, `📍 CEP sem traço copiado: ${rawCep}`);
        });
    }

    // Botões inline para copiar campos do tomador
    document.querySelectorAll('.btn-copy-inline[data-target]').forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                const val = targetEl.textContent.trim();
                if (val && val !== '-') {
                    copyToClipboard(val, `📋 Copiado: ${val}`);
                }
            }
        });
    });

    // Gravação de Status: NFS-e de Mão de Obra
    if (btnMarkNfseDone) {
        btnMarkNfseDone.addEventListener('click', async () => {
            const num = (nfseNumberInput?.value || '').trim();
            const date = (nfseDateInput?.value || '').trim();
            if (!currentFiscalPlate && !currentFiscalFilePath) {
                alert('Nenhuma visita selecionada.');
                return;
            }

            try {
                btnMarkNfseDone.disabled = true;
                btnMarkNfseDone.textContent = 'Salvando...';

                const res = await fetch('/api/nf/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_path: currentFiscalFilePath,
                        plate: currentFiscalPlate,
                        visit_num: currentFiscalVisitNum,
                        status_servico: 'emitida',
                        nf_servico_num: num,
                        data_emissao_servico: date
                    })
                });

                const data = await res.json();
                if (data.success) {
                    showToast(`✅ NFS-e #${num || 'S/N'} marcada como EMITIDA!`);
                    if (nfseCurrentStatusTag) {
                        nfseCurrentStatusTag.className = 'badge-status-pill emitted';
                        nfseCurrentStatusTag.textContent = `✅ Emitida (NFS-e #${num || 'S/N'})`;
                    }
                    updateHeaderFiscalBadge();
                    if (currentCarHistory && currentCarHistory.vehicle && currentCarHistory.vehicle.plate === currentFiscalPlate) {
                        selectVehicleByPlate(currentFiscalPlate);
                    }
                } else {
                    alert('Erro ao salvar status: ' + (data.error || 'Erro desconhecido'));
                }
            } catch (e) {
                alert('Erro de conexão ao salvar status: ' + e.message);
            } finally {
                btnMarkNfseDone.disabled = false;
                btnMarkNfseDone.textContent = '✅ Marcar NFS-e Emitida';
            }
        });
    }

    // Gravação de Status: NF-e de Peças
    if (btnMarkNfeDone) {
        btnMarkNfeDone.addEventListener('click', async () => {
            const num = (nfeNumberInput?.value || '').trim();
            const date = (nfeDateInput?.value || '').trim();
            if (!currentFiscalPlate && !currentFiscalFilePath) {
                alert('Nenhuma visita selecionada.');
                return;
            }

            try {
                btnMarkNfeDone.disabled = true;
                btnMarkNfeDone.textContent = 'Salvando...';

                const res = await fetch('/api/nf/status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        file_path: currentFiscalFilePath,
                        plate: currentFiscalPlate,
                        visit_num: currentFiscalVisitNum,
                        status_pecas: 'emitida',
                        nf_pecas_num: num,
                        data_emissao_pecas: date
                    })
                });

                const data = await res.json();
                if (data.success) {
                    showToast(`✅ NF-e #${num || 'S/N'} marcada como EMITIDA!`);
                    if (nfeCurrentStatusTag) {
                        nfeCurrentStatusTag.className = 'badge-status-pill emitted';
                        nfeCurrentStatusTag.textContent = `✅ Emitida (NF-e #${num || 'S/N'})`;
                    }
                    updateHeaderFiscalBadge();
                    if (currentCarHistory && currentCarHistory.vehicle && currentCarHistory.vehicle.plate === currentFiscalPlate) {
                        selectVehicleByPlate(currentFiscalPlate);
                    }
                } else {
                    alert('Erro ao salvar status: ' + (data.error || 'Erro desconhecido'));
                }
            } catch (e) {
                alert('Erro de conexão ao salvar status: ' + e.message);
            } finally {
                btnMarkNfeDone.disabled = false;
                btnMarkNfeDone.textContent = '✅ Marcar NF-e Emitida';
            }
        });
    }

    // Aba 4: Fila de Notas Fiscais Pendentes
    async function loadFiscalPendingList() {
        if (!fiscalPendingList) return;
        fiscalPendingList.innerHTML = '<div style="padding: 24px; text-align: center; color: #64748b;">Carregando fila fiscal...</div>';

        const q = (queueSearchInput?.value || '').trim();
        try {
            const params = new URLSearchParams();
            params.set('filter', activeQueueFilter);
            if (q) params.set('q', q);

            const res = await fetch(`/api/nf/queue?${params.toString()}`);
            const data = await res.json();

            if (!data.success) {
                fiscalPendingList.innerHTML = `<div style="padding: 16px; color: #ef4444;">Erro ao carregar fila: ${escapeHtml(data.error || 'Falha')}</div>`;
                return;
            }

            const items = data.items || [];
            const stats = data.stats || {};

            // Atualiza KPI cards
            if (kpiPendingVisits) kpiPendingVisits.textContent = stats.pending_visits_count || 0;
            if (kpiPendingServices) kpiPendingServices.textContent = formatMoeda(stats.total_pending_services_val || 0);
            if (kpiPendingServicesSub) kpiPendingServicesSub.textContent = `${stats.pending_servicos_count || 0} visitas`;
            if (kpiPendingParts) kpiPendingParts.textContent = formatMoeda(stats.total_pending_pecas_val || 0);
            if (kpiPendingPartsSub) kpiPendingPartsSub.textContent = `${stats.pending_pecas_count || 0} visitas`;
            if (kpiEmittedCount) kpiEmittedCount.textContent = stats.emitted_count || 0;

            if (items.length === 0) {
                fiscalPendingList.innerHTML = `
                    <div style="padding: 32px; text-align: center; color: #166534; font-weight: 700; background: #f0fdf4; border: 1.5px solid #bbf7d0; border-radius: 8px;">
                        🎉 Parabéns! Nenhuma nota fiscal pendente encontrada neste filtro.
                    </div>
                `;
                return;
            }

            fiscalPendingList.innerHTML = '';
            items.forEach(item => {
                const card = document.createElement('div');
                card.className = 'fiscal-queue-card';

                const isServDone = item.status_servico === 'emitida';
                const isPecasDone = item.status_pecas === 'emitida';

                const servBadgeHtml = isServDone
                    ? `<span class="badge-status-pill emitted">✅ NFS-e #${escapeHtml(item.nf_servico_num || 'S/N')} (${formatMoeda(item.valor_servico)})</span>`
                    : `<span class="badge-status-pill pending">⏳ NFS-e Santos: ${formatMoeda(item.valor_servico)}</span>`;

                const pecasBadgeHtml = isPecasDone
                    ? `<span class="badge-status-pill emitted">✅ NF-e #${escapeHtml(item.nf_pecas_num || 'S/N')} (${formatMoeda(item.valor_pecas)})</span>`
                    : `<span class="badge-status-pill pending">⏳ NF-e 55: ${formatMoeda(item.valor_pecas)}</span>`;

                const plateDisp = item.plate_display || item.plate;
                const vNumStr = item.visit_num ? `Visita #${item.visit_num}` : '';

                card.innerHTML = `
                    <div class="fiscal-card-info">
                        <div class="fiscal-card-title-row">
                            <span class="fiscal-card-plate">${escapeHtml(plateDisp)}</span>
                            <span class="fiscal-card-model">${escapeHtml(item.car_model || 'Veículo')}</span>
                            <span class="fiscal-card-client">• 👤 ${escapeHtml(item.client_name || 'Cliente')}</span>
                            <span class="fiscal-card-date">📅 ${escapeHtml(item.entry_date || '-')}</span>
                            ${vNumStr ? `<span class="badge" style="background: #e2e8f0; color: #334155; font-size: 11px;">${vNumStr}</span>` : ''}
                        </div>
                        <div class="fiscal-card-status-row">
                            <div class="fiscal-status-item">
                                <small style="color: #64748b; font-weight: 700;">Mão de Obra:</small>
                                ${servBadgeHtml}
                            </div>
                            <div class="fiscal-status-item">
                                <small style="color: #64748b; font-weight: 700;">Peças:</small>
                                ${pecasBadgeHtml}
                            </div>
                        </div>
                    </div>
                    <div class="fiscal-card-actions">
                        <button type="button" class="btn-action-mini primary btn-queue-open" title="Abrir esta OS no Copiloto Fiscal para emissão">
                            ⚡ Abrir no Copiloto
                        </button>
                        <button type="button" class="btn-action-mini btn-queue-copy-nfse" title="Copiar discriminação formatada para a NFS-e Santos">
                            📋 Copiar NFS-e
                        </button>
                        <button type="button" class="btn-action-mini btn-queue-copy-nfe" title="Copiar resumo de peças para a NF-e 55">
                            🔩 Copiar Peças
                        </button>
                    </div>
                `;

                // Eventos dos botões do card
                card.querySelector('.btn-queue-open').addEventListener('click', () => {
                    openFiscalModal(item.file_path, item.plate, item.visit_num, isServDone && !isPecasDone ? 'nfe' : 'nfse');
                });

                card.querySelector('.btn-queue-copy-nfse').addEventListener('click', async () => {
                    try {
                        const r = await fetch(`/api/nf/copilot_text?type=nfse_discriminacao&file_path=${encodeURIComponent(item.file_path || '')}&plate=${encodeURIComponent(item.plate || '')}&visit_num=${encodeURIComponent(item.visit_num || '')}`);
                        const d = await r.json();
                        if (d.success && d.text) {
                            copyToClipboard(d.text, `📋 Discriminação NFS-e de ${plateDisp} copiada!`);
                        } else {
                            showToast('Erro ao gerar discriminação.');
                        }
                    } catch (e) {
                        showToast('Erro ao buscar texto da NFS-e.');
                    }
                });

                card.querySelector('.btn-queue-copy-nfe').addEventListener('click', async () => {
                    try {
                        const r = await fetch(`/api/nf/copilot_text?type=nfe_pecas_tsv&file_path=${encodeURIComponent(item.file_path || '')}&plate=${encodeURIComponent(item.plate || '')}&visit_num=${encodeURIComponent(item.visit_num || '')}`);
                        const d = await r.json();
                        if (d.success && d.text) {
                            copyToClipboard(d.text, `📊 Tabela TSV de Peças de ${plateDisp} copiada!`);
                        } else {
                            showToast('Erro ao gerar dados de peças.');
                        }
                    } catch (e) {
                        showToast('Erro ao buscar dados de peças.');
                    }
                });

                fiscalPendingList.appendChild(card);
            });

        } catch (err) {
            fiscalPendingList.innerHTML = `<div style="padding: 16px; color: #ef4444;">Erro ao carregar fila fiscal: ${err.message}</div>`;
        }
    }

    // Filtros da Fila
    document.querySelectorAll('.queue-filter-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.queue-filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            activeQueueFilter = btn.getAttribute('data-filter') || 'pending';
            loadFiscalPendingList();
        });
    });

    if (queueSearchInput) {
        queueSearchInput.addEventListener('input', () => {
            const val = queueSearchInput.value.trim();
            if (btnClearQueueSearch) {
                btnClearQueueSearch.style.display = val ? 'block' : 'none';
            }
            clearTimeout(queueSearchDebounceTimer);
            queueSearchDebounceTimer = setTimeout(() => {
                loadFiscalPendingList();
            }, 250);
        });
    }

    if (btnClearQueueSearch) {
        btnClearQueueSearch.addEventListener('click', () => {
            queueSearchInput.value = '';
            btnClearQueueSearch.style.display = 'none';
            loadFiscalPendingList();
        });
    }

    if (btnRefreshQueue) {
        btnRefreshQueue.addEventListener('click', () => {
            loadFiscalPendingList();
            updateHeaderFiscalBadge();
        });
    }

    if (btnExportQueueCsv) {
        btnExportQueueCsv.addEventListener('click', () => {
            const q = (queueSearchInput?.value || '').trim();
            window.open(`/api/nf/export_batch?format=csv&filter=${encodeURIComponent(activeQueueFilter)}&q=${encodeURIComponent(q)}`, '_blank');
        });
    }

    if (btnExportQueueTxt) {
        btnExportQueueTxt.addEventListener('click', () => {
            const q = (queueSearchInput?.value || '').trim();
            window.open(`/api/nf/export_batch?format=txt&filter=${encodeURIComponent(activeQueueFilter)}&q=${encodeURIComponent(q)}`, '_blank');
        });
    }

    // Handlers do Modal
    if (btnOpenFiscalHub) {
        btnOpenFiscalHub.addEventListener('click', () => {
            if (currentCarHistory && currentCarHistory.vehicle && currentCarHistory.vehicle.plate) {
                openFiscalModal(null, currentCarHistory.vehicle.plate, null, 'nfse');
            } else {
                openFiscalModal(null, null, null, 'pending');
            }
        });
    }

    if (btnVehicleFiscal) {
        btnVehicleFiscal.addEventListener('click', () => {
            if (currentCarHistory && currentCarHistory.vehicle && currentCarHistory.vehicle.plate) {
                openFiscalModal(null, currentCarHistory.vehicle.plate, null, 'nfse');
            } else {
                openFiscalModal(null, currentVehiclePlate || null, null, 'nfse');
            }
        });
    }

    if (fiscalModalCloseBtn) {
        fiscalModalCloseBtn.addEventListener('click', () => {
            fiscalModal.style.display = 'none';
        });
    }

    if (fiscalModalDismiss) {
        fiscalModalDismiss.addEventListener('click', () => {
            fiscalModal.style.display = 'none';
        });
    }

    // =========================================================================
    // MÓDULO DE ANALYTICS & MÉTRICAS DA OFICINA (Issue #16)
    // =========================================================================

    const btnOpenAnalyticsModal = document.getElementById('btn-open-analytics-modal');
    const welcomeBtnAnalytics = document.getElementById('welcome-btn-analytics');
    const welcomeBtnPatio = document.getElementById('welcome-btn-patio');
    const welcomeBtnFiscal = document.getElementById('welcome-btn-fiscal');
    const analyticsModal = document.getElementById('analytics-modal');
    const analyticsModalCloseBtn = document.getElementById('analytics-modal-close-btn');
    const analyticsModalDismiss = document.getElementById('analytics-modal-dismiss');
    const btnRefreshAnalytics = document.getElementById('btn-refresh-analytics');
    const btnPrintAnalytics = document.getElementById('btn-print-analytics');
    const analyticsPeriodCaption = document.getElementById('analytics-period-caption');

    const periodBtns = {
        '30': document.getElementById('btn-period-30'),
        '90': document.getElementById('btn-period-90'),
        'all': document.getElementById('btn-period-all')
    };

    let currentAnalyticsPeriod = '30';

    function formatCurrencyBR(value) {
        const num = parseFloat(value) || 0;
        return 'R$ ' + num.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatDecimalBR(value, decimals = 2) {
        const num = parseFloat(value) || 0;
        return num.toLocaleString('pt-BR', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
    }

    async function loadAnalyticsData(period = '30') {
        currentAnalyticsPeriod = period;

        // Atualiza estilo dos botões de período
        Object.keys(periodBtns).forEach(pKey => {
            if (periodBtns[pKey]) {
                if (pKey === period) {
                    periodBtns[pKey].classList.add('active');
                } else {
                    periodBtns[pKey].classList.remove('active');
                }
            }
        });

        // Atualiza legenda do período
        if (analyticsPeriodCaption) {
            analyticsPeriodCaption.textContent = period === '30' ? 'Últimos 30 Dias' : (period === '90' ? 'Últimos 90 Dias' : 'Geral (Histórico Completo)');
        }

        try {
            const resp = await fetch(`/api/analytics?period=${encodeURIComponent(period)}`);
            if (!resp.ok) {
                throw new Error(`Erro na API (${resp.status})`);
            }
            const resJson = await resp.json();
            if (!resJson.success || !resJson.data) {
                throw new Error(resJson.error || 'Falha ao obter dados analíticos');
            }

            renderAnalyticsDashboard(resJson.data);
        } catch (err) {
            console.error('Erro ao carregar analytics:', err);
            showToast('Erro ao carregar dados de analytics: ' + err.message, 'error');
        }
    }

    function renderAnalyticsDashboard(data) {
        const vol = data.volume || {};
        const stay = data.stay_time || {};
        const fin = data.financials || {};
        const trend = data.monthly_trend || [];
        const recent = data.recent_orders || [];

        // 1. Volume de Carros
        const valTotalCars = document.getElementById('val-total-cars');
        const valTotalOrders = document.getElementById('val-total-orders');
        const valAvgCarsDay = document.getElementById('val-avg-cars-day');
        const valAvgOrdersDay = document.getElementById('val-avg-orders-day');
        const valAvgCarsWeek = document.getElementById('val-avg-cars-week');
        const valAvgOrdersWeek = document.getElementById('val-avg-orders-week');
        const valAvgCarsMonth = document.getElementById('val-avg-cars-month');
        const valAvgOrdersMonth = document.getElementById('val-avg-orders-month');

        if (valTotalCars) valTotalCars.textContent = vol.total_cars || 0;
        if (valTotalOrders) valTotalOrders.textContent = `${vol.total_orders || 0} ${vol.total_orders === 1 ? 'ordem de serviço' : 'ordens de serviço'} (${vol.active_days_count || 0} dias ativos)`;
        if (valAvgCarsDay) valAvgCarsDay.textContent = formatDecimalBR(vol.avg_cars_per_day, 2);
        if (valAvgOrdersDay) valAvgOrdersDay.textContent = `${formatDecimalBR(vol.avg_orders_per_day, 2)} OSs / dia`;
        if (valAvgCarsWeek) valAvgCarsWeek.textContent = formatDecimalBR(vol.avg_cars_per_week, 2);
        if (valAvgOrdersWeek) valAvgOrdersWeek.textContent = `${formatDecimalBR(vol.avg_orders_per_week, 2)} OSs / sem`;
        if (valAvgCarsMonth) valAvgCarsMonth.textContent = formatDecimalBR(vol.avg_cars_per_month, 2);
        if (valAvgOrdersMonth) valAvgOrdersMonth.textContent = `${formatDecimalBR(vol.avg_orders_per_month, 2)} OSs / mês`;

        // 2. Tempo Médio de Permanência
        const valAvgStayDays = document.getElementById('val-avg-stay-days');
        const valStayRange = document.getElementById('val-stay-range');
        const valStayCount = document.getElementById('val-stay-count');

        if (valAvgStayDays) {
            valAvgStayDays.textContent = stay.avg_stay_text || `${formatDecimalBR(stay.avg_stay_days, 1)} dias`;
        }
        if (valStayRange) {
            if (stay.stays_measured_count > 0) {
                const minTxt = stay.min_stay_days === 0 ? '0d (mesmo dia)' : `${stay.min_stay_days}d`;
                const maxTxt = `${stay.max_stay_days}d`;
                valStayRange.textContent = `Mín: ${minTxt} • Máx: ${maxTxt}`;
            } else {
                valStayRange.textContent = 'Mín: - • Máx: -';
            }
        }
        if (valStayCount) {
            valStayCount.textContent = `Medido em ${stay.stays_measured_count || 0} ${stay.stays_measured_count === 1 ? 'veículo finalizado' : 'veículos finalizados'}`;
        }

        // Distribuição de Permanência
        const dist = stay.distribution || {};
        const totalMeasured = stay.stays_measured_count || 0;
        const calcPct = (cnt) => totalMeasured > 0 ? Math.round((cnt / totalMeasured) * 100) : 0;

        const sameDayCnt = dist.same_day || 0;
        const d13Cnt = dist.days_1_to_3 || 0;
        const d47Cnt = dist.days_4_to_7 || 0;
        const dOver7Cnt = dist.days_over_7 || 0;

        const elDistSame = document.getElementById('dist-count-same-day');
        const elBarSame = document.getElementById('dist-bar-same-day');
        if (elDistSame) elDistSame.textContent = `${sameDayCnt} carros (${calcPct(sameDayCnt)}%)`;
        if (elBarSame) elBarSame.style.width = `${calcPct(sameDayCnt)}%`;

        const elDist13 = document.getElementById('dist-count-1-3');
        const elBar13 = document.getElementById('dist-bar-1-3');
        if (elDist13) elDist13.textContent = `${d13Cnt} carros (${calcPct(d13Cnt)}%)`;
        if (elBar13) elBar13.style.width = `${calcPct(d13Cnt)}%`;

        const elDist47 = document.getElementById('dist-count-4-7');
        const elBar47 = document.getElementById('dist-bar-4-7');
        if (elDist47) elDist47.textContent = `${d47Cnt} carros (${calcPct(d47Cnt)}%)`;
        if (elBar47) elBar47.style.width = `${calcPct(d47Cnt)}%`;

        const elDistOver7 = document.getElementById('dist-count-over-7');
        const elBarOver7 = document.getElementById('dist-bar-over-7');
        if (elDistOver7) elDistOver7.textContent = `${dOver7Cnt} carros (${calcPct(dOver7Cnt)}%)`;
        if (elBarOver7) elBarOver7.style.width = `${calcPct(dOver7Cnt)}%`;

        // 3. Médias Financeiras
        const valAvgParts = document.getElementById('val-avg-parts');
        const valTotalParts = document.getElementById('val-total-parts');
        const valPartsBilledNote = document.getElementById('val-parts-billed-note');

        const valAvgLabor = document.getElementById('val-avg-labor');
        const valTotalLabor = document.getElementById('val-total-labor');
        const valLaborBilledNote = document.getElementById('val-labor-billed-note');

        const valAvgTicket = document.getElementById('val-avg-ticket');
        const valOrdersBilledCount = document.getElementById('val-orders-billed-count');
        const valTicketBilledNote = document.getElementById('val-ticket-billed-note');

        const valTotalRevenue = document.getElementById('val-total-revenue');
        const valRevenueRatio = document.getElementById('val-revenue-ratio');
        const valPeriodDaysCount = document.getElementById('val-period-days-count');

        if (valAvgParts) valAvgParts.textContent = formatCurrencyBR(fin.avg_parts_per_order);
        if (valTotalParts) valTotalParts.textContent = `Total em peças: ${formatCurrencyBR(fin.total_parts)}`;
        if (valPartsBilledNote) valPartsBilledNote.textContent = `Média p/ OS c/ peças: ${formatCurrencyBR(fin.avg_parts_per_billed_order)} (${fin.orders_with_parts_count || 0} OSs)`;

        if (valAvgLabor) valAvgLabor.textContent = formatCurrencyBR(fin.avg_labor_per_order);
        if (valTotalLabor) valTotalLabor.textContent = `Total em serviços: ${formatCurrencyBR(fin.total_labor)}`;
        if (valLaborBilledNote) valLaborBilledNote.textContent = `Média p/ OS c/ serviço: ${formatCurrencyBR(fin.avg_labor_per_billed_order)} (${fin.orders_with_labor_count || 0} OSs)`;

        if (valAvgTicket) valAvgTicket.textContent = formatCurrencyBR(fin.avg_ticket_order);
        if (valOrdersBilledCount) valOrdersBilledCount.textContent = `${fin.orders_billed_count || 0} de ${vol.total_orders || 0} OSs faturadas`;
        if (valTicketBilledNote) valTicketBilledNote.textContent = `Ticket médio faturado: ${formatCurrencyBR(fin.avg_ticket_billed_order)}`;

        if (valTotalRevenue) valTotalRevenue.textContent = formatCurrencyBR(fin.total_revenue);
        if (valRevenueRatio) valRevenueRatio.textContent = `Peças: ${formatDecimalBR(fin.parts_percentage, 1)}% • Mão de Obra: ${formatDecimalBR(fin.labor_percentage, 1)}%`;
        if (valPeriodDaysCount) valPeriodDaysCount.textContent = `Base: ${data.days_span || 30} dias de intervalo analisado`;

        // Barra de proporção empilhada
        const ratioPartsBar = document.getElementById('ratio-bar-parts');
        const ratioLaborBar = document.getElementById('ratio-bar-labor');
        const partsLaborLegend = document.getElementById('val-parts-labor-legend');
        const ratioTextParts = document.getElementById('ratio-text-parts');
        const ratioTextLabor = document.getElementById('ratio-text-labor');

        const partsPct = fin.parts_percentage || 0;
        const laborPct = fin.labor_percentage || 0;

        if (ratioPartsBar) ratioPartsBar.style.width = `${partsPct}%`;
        if (ratioLaborBar) ratioLaborBar.style.width = `${laborPct}%`;
        if (partsLaborLegend) partsLaborLegend.textContent = `${formatDecimalBR(partsPct, 1)}% Peças | ${formatDecimalBR(laborPct, 1)}% Serviços`;
        if (ratioTextParts) ratioTextParts.textContent = `${formatCurrencyBR(fin.total_parts)} (${formatDecimalBR(partsPct, 1)}%)`;
        if (ratioTextLabor) ratioTextLabor.textContent = `${formatCurrencyBR(fin.total_labor)} (${formatDecimalBR(laborPct, 1)}%)`;

        // 4. Gráfico Mensal
        renderMonthlyChart(trend);

        // 5. Tabela de Ordens Recentes
        renderRecentOrdersTable(recent);
    }

    function renderMonthlyChart(trend) {
        const chartContainer = document.getElementById('analytics-monthly-chart');
        if (!chartContainer) return;

        chartContainer.innerHTML = '';

        if (!trend || trend.length === 0) {
            chartContainer.innerHTML = `
                <div style="width: 100%; text-align: center; padding: 25px 10px; color: #94a3b8; font-size: 13px;">
                    Nenhum histórico mensal disponível para o período selecionado.
                </div>
            `;
            return;
        }

        const maxTotal = Math.max(...trend.map(t => t.total || 0), 100);

        trend.forEach(item => {
            const group = document.createElement('div');
            group.className = 'chart-bar-group';

            const heightPct = Math.max(10, Math.round(((item.total || 0) / maxTotal) * 100));
            const barHeightPx = Math.max(10, Math.round((heightPct / 100) * 80));

            group.innerHTML = `
                <div class="chart-bar-val">${item.total > 0 ? formatCurrencyBR(item.total) : `${item.cars} carros`}</div>
                <div class="chart-bar-pillar" style="height: ${barHeightPx}px;" title="${item.label}: ${item.cars} ${item.cars === 1 ? 'carro' : 'carros'}, ${item.orders} OSs, Peças: ${formatCurrencyBR(item.parts)}, Mão de Obra: ${formatCurrencyBR(item.labor)}, Total: ${formatCurrencyBR(item.total)}"></div>
                <div class="chart-bar-label">${item.label}</div>
                <div class="chart-bar-sub">${item.cars} ${item.cars === 1 ? 'carro' : 'carros'}</div>
            `;
            chartContainer.appendChild(group);
        });
    }

    function renderRecentOrdersTable(orders) {
        const tbody = document.getElementById('analytics-recent-tbody');
        const countBadge = document.getElementById('analytics-recent-count');
        if (countBadge) countBadge.textContent = orders ? orders.length : 0;
        if (!tbody) return;

        tbody.innerHTML = '';

        if (!orders || orders.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; padding: 20px; color: #94a3b8;">
                        Nenhuma ordem de serviço registrada no período selecionado.
                    </td>
                </tr>
            `;
            return;
        }

        orders.forEach(ord => {
            const tr = document.createElement('tr');

            let stayPillHtml = '<span class="stay-pill stay-open">-</span>';
            if (ord.stay_days !== null && ord.stay_days !== undefined) {
                if (ord.stay_days === 0) {
                    stayPillHtml = '<span class="stay-pill stay-fast">0d (mesmo dia)</span>';
                } else if (ord.stay_days <= 3) {
                    stayPillHtml = `<span class="stay-pill stay-norm">${ord.stay_days}d</span>`;
                } else {
                    stayPillHtml = `<span class="stay-pill stay-long">${ord.stay_days}d</span>`;
                }
            } else if (ord.exit_date) {
                stayPillHtml = '<span class="stay-pill stay-norm">Finalizado</span>';
            } else {
                stayPillHtml = '<span class="stay-pill stay-open">Em aberto</span>';
            }

            tr.innerHTML = `
                <td><span class="analytics-plate-badge">${escapeHtml(ord.plate_display || ord.plate || '-')}</span></td>
                <td><strong>${escapeHtml(ord.client_name || '-')}</strong></td>
                <td>${escapeHtml(ord.car_model || '-')}</td>
                <td>${escapeHtml(ord.entry_date || '-')}</td>
                <td>${escapeHtml(ord.exit_date || '-')}</td>
                <td>${stayPillHtml}</td>
                <td style="color: #d97706; font-weight: 600;">${ord.parts_val > 0 ? formatCurrencyBR(ord.parts_val) : '-'}</td>
                <td style="color: #0284c7; font-weight: 600;">${ord.labor_val > 0 ? formatCurrencyBR(ord.labor_val) : '-'}</td>
                <td style="font-weight: 700; color: #111827;">${ord.total_val > 0 ? formatCurrencyBR(ord.total_val) : '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    }

    function openAnalyticsModal(period = '30') {
        if (analyticsModal) {
            analyticsModal.style.display = 'flex';
            loadAnalyticsData(period);
        }
    }

    function closeAnalyticsModal() {
        if (analyticsModal) {
            analyticsModal.style.display = 'none';
        }
    }

    // Eventos de Abertura e Fechamento do Modal de Analytics
    if (btnOpenAnalyticsModal) {
        btnOpenAnalyticsModal.addEventListener('click', () => {
            openAnalyticsModal(currentAnalyticsPeriod);
        });
    }

    if (welcomeBtnAnalytics) {
        welcomeBtnAnalytics.addEventListener('click', () => {
            openAnalyticsModal(currentAnalyticsPeriod);
        });
    }

    if (welcomeBtnPatio) {
        welcomeBtnPatio.addEventListener('click', () => {
            const btnPatio = document.getElementById('btn-open-patio-modal');
            if (btnPatio) btnPatio.click();
        });
    }

    if (welcomeBtnFiscal) {
        welcomeBtnFiscal.addEventListener('click', () => {
            const btnFiscal = document.getElementById('btn-open-fiscal-hub');
            if (btnFiscal) btnFiscal.click();
        });
    }

    if (analyticsModalCloseBtn) {
        analyticsModalCloseBtn.addEventListener('click', closeAnalyticsModal);
    }

    if (analyticsModalDismiss) {
        analyticsModalDismiss.addEventListener('click', closeAnalyticsModal);
    }

    if (analyticsModal) {
        analyticsModal.addEventListener('click', (e) => {
            if (e.target === analyticsModal) {
                closeAnalyticsModal();
            }
        });
    }

    if (btnRefreshAnalytics) {
        btnRefreshAnalytics.addEventListener('click', () => {
            loadAnalyticsData(currentAnalyticsPeriod);
            showToast('Métricas de Analytics atualizadas com sucesso!', 'success');
        });
    }

    if (btnPrintAnalytics) {
        btnPrintAnalytics.addEventListener('click', () => {
            window.print();
        });
    }

    // Filtros por Período
    if (periodBtns['30']) {
        periodBtns['30'].addEventListener('click', () => loadAnalyticsData('30'));
    }
    if (periodBtns['90']) {
        periodBtns['90'].addEventListener('click', () => loadAnalyticsData('90'));
    }
    if (periodBtns['all']) {
        periodBtns['all'].addEventListener('click', () => loadAnalyticsData('all'));
    }

    // Inicialização da contagem no carregamento da tela
    updateHeaderFiscalBadge();
});


