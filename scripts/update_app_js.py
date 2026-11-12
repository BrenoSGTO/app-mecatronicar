# -*- coding: utf-8 -*-
"""
Atualiza static/app.js para:
1. Renderizar Placas Mercosul Oficiais em todos os cards e modais
2. Exibir logotipos oficiais das montadoras nos cards e banner de veículo
3. Exibir silhuetas de perfil dos modelos nos cards e banner de veículo
4. Eliminar 100% dos emojis da aplicação substituindo por ícones SVG da biblioteca CarCatalog
"""

with open("static/app.js", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Atualizar renderSearchResultsGrid
old_search_grid = """        results.forEach(item => {
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
        });"""

new_search_grid = """        results.forEach(item => {
            const card = document.createElement('div');
            card.className = 'search-card';

            const plateFmt = item.plate_display || item.plate || 'SEM PLACA';
            const plateHtml = window.CarCatalog
                ? window.CarCatalog.renderMercosulPlateHtml(plateFmt, 'md')
                : `<div class="mercosul-plate mercosul-plate-md"><div class="mercosul-body-area"><span class="mercosul-number">${escapeHtml(plateFmt)}</span></div></div>`;

            const carInfo = window.CarCatalog ? window.CarCatalog.identifyCar(item.car_model || '') : null;
            const brandLogoHtml = (carInfo && window.CarCatalog) ? window.CarCatalog.renderBrandLogoHtml(carInfo.brandKey, 36) : '';
            const silhouetteHtml = (carInfo && window.CarCatalog) ? window.CarCatalog.renderCarSilhouetteHtml(carInfo, 46) : '';

            const calIcon = window.CarCatalog ? window.CarCatalog.getIcon('calendar', 13) : '';
            const userIcon = window.CarCatalog ? window.CarCatalog.getIcon('user', 14) : '';
            const gaugeIcon = window.CarCatalog ? window.CarCatalog.getIcon('gauge', 13) : '';

            card.innerHTML = `
                <div class="search-card-top">
                    ${plateHtml}
                    <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 4px;">
                        ${brandLogoHtml}
                        <span class="search-card-date">${calIcon} ${item.entry_date || 'Sem data'}</span>
                    </div>
                </div>
                ${silhouetteHtml}
                <div class="search-card-owner">${userIcon} ${escapeHtml(item.client_name || 'Cliente não identificado')}</div>
                <div class="search-card-car"><strong>${escapeHtml(item.car_model || '')}</strong> ${item.car_year ? '(' + escapeHtml(item.car_year) + ')' : ''} ${item.car_color ? '• ' + escapeHtml(item.car_color) : ''}</div>
                ${item.odometer ? `<div style="font-size: 12px; color: #475569;">${gaugeIcon} Hodômetro: <strong>${formatKm(item.odometer)}</strong></div>` : ''}
                ${item.complaint ? `<div class="search-card-complaint" title="${escapeHtml(item.complaint)}">${escapeHtml(item.complaint)}</div>` : ''}
            `;
            card.addEventListener('click', () => {
                selectVehicleByPlate(item.plate_clean || item.plate);
            });
            searchCardsGrid.appendChild(card);
        });"""

if old_search_grid in code:
    code = code.replace(old_search_grid, new_search_grid)
else:
    print("WARNING: old_search_grid não encontrado exatamente")

# 2. Atualizar renderVehicleHistory para configurar Brand Logo e Silhueta
old_history_banner = """        detailCarModel.textContent = latest.car_model || 'Veículo';"""
new_history_banner = """        detailCarModel.textContent = latest.car_model || 'Veículo';

        const carInfo = window.CarCatalog ? window.CarCatalog.identifyCar(latest.car_model || '') : null;
        const brandLogoEl = document.getElementById('detail-brand-logo');
        const silhouetteEl = document.getElementById('detail-car-silhouette');
        if (brandLogoEl && carInfo) {
            brandLogoEl.src = carInfo.brandLogo;
            brandLogoEl.alt = carInfo.brandName;
            brandLogoEl.title = `Montadora: ${carInfo.brandName}`;
        }
        if (silhouetteEl && carInfo) {
            silhouetteEl.src = carInfo.silhouette;
            silhouetteEl.alt = carInfo.modelName;
            silhouetteEl.title = `Modelo: ${carInfo.modelName}`;
        }"""

if old_history_banner in code:
    code = code.replace(old_history_banner, new_history_banner)

# 3. Substituições de emojis em todo o código de app.js
replacements = [
    # Botões e cabeçalhos de visit-card
    ("📄 Orçamento / OS", "Orçamento / OS"),
    ("📋 Checklist", "Checklist"),
    ("🧾 Copiloto NF", "Copiloto NF"),
    ("🛠️ Serviços (", "Serviços ("),
    ("✏️ Editar OS", "Editar OS"),
    ("📂 Excel", "Excel"),
    ("📅 ${dateDisplay}", "${dateDisplay}"),
    ("⏱️ ${kmDisplay}", "${kmDisplay}"),
    ("📄 ${escapeHtml(visit.file_name)}", "${escapeHtml(visit.file_name)}"),
    ("✅ ${numsStr}", "${numsStr}"),
    ("🟡 NF Parcial", "NF Parcial"),
    ("⏳ NF Pendente", "NF Pendente"),
    ("🧾 NF", "NF"),
    ("📞 ${details.phone}", "${details.phone}"),
    ("📅 ${escapeHtml(dateStr)}", "${escapeHtml(dateStr)}"),
    ("⏱️ ${escapeHtml(kmStr)}", "${escapeHtml(kmStr)}"),
    ("💬 Ver nota", "Ver nota"),
    ("<span>🛠️ Serviços Executados / Mão de Obra nesta Planilha</span>", "<span>Serviços Executados / Mão de Obra nesta Planilha</span>"),
    ("<span class=\"extra-sheet-panel-title\">📑 Aba:", "<span class=\"extra-sheet-panel-title\">Aba:"),
    ("<span class=\"sheet-section-label\">🔩 Peças da Aba", "<span class=\"sheet-section-label\">Peças da Aba"),
    ("🛠️ Ver Serviços Executados (", "Ver Serviços Executados ("),
    ("🛠️ Ocultar Serviços Executados (", "Ocultar Serviços Executados ("),
    ("🛠️ Ocultar Serviços (", "Ocultar Serviços ("),
    ("📝 Relatório do Scanner / Nota Técnica", "Relatório do Scanner / Nota Técnica"),
    ("⚠️ Queixa / Motivo:", "Queixa / Motivo:"),
    ("<span class=\"sheet-section-label\">🔩 Peças da Planilha", "<span class=\"sheet-section-label\">Peças da Planilha"),
    ("📑 Outras planilhas preenchidas nesta ficha:", "Outras planilhas preenchidas nesta ficha:"),
    ("👁️ Ver ${secSheet.sheet_name}", "Ver ${secSheet.sheet_name}"),

    # Pátio Desktop
    ("• 🔑 Autorizado:", "• Autorizado:"),
    ("- 👤 ${escapeHtml(car.client_name || 'Cliente')}", "- ${escapeHtml(car.client_name || 'Cliente')}"),
    ("${car.box_mecanico ? `🔧 ${escapeHtml(car.box_mecanico)} ` : ''}", "${car.box_mecanico ? `${escapeHtml(car.box_mecanico)} ` : ''}"),
    ("<button type=\"button\" class=\"btn-remove-row\" title=\"Remover Peça\">🗑️</button>", "<button type=\"button\" class=\"btn-remove-row\" title=\"Remover Peça\">&times;</button>"),
    ("<button type=\"button\" class=\"btn-remove-row\" title=\"Remover Serviço\">🗑️</button>", "<button type=\"button\" class=\"btn-remove-row\" title=\"Remover Serviço\">&times;</button>"),
    ("✨ Sugerido: Visita", "Sugerido: Visita"),
    ("🟢 Veículo Recorrente", "Veículo Recorrente"),
    ("🆕 Novo Veículo na Oficina", "Novo Veículo na Oficina"),
    ("🛠️ Nova Visita / Ordem de Serviço", "Nova Visita / Ordem de Serviço"),
    ("💾 Salvar Ficha no Excel (.xlsx) e Sistema", "Salvar Ficha no Excel (.xlsx) e Sistema"),
    ("✏️ Editar Ordem de Serviço", "Editar Ordem de Serviço"),
    ("💾 Salvar Alterações na Planilha (.xlsx)", "Salvar Alterações na Planilha (.xlsx)"),
    ("✏️ Editando Planilha Existente", "Editando Planilha Existente"),
    ("👤 ${escapeHtml(r.client_name || 'Cliente')}", "${escapeHtml(r.client_name || 'Cliente')}"),
    ("⏳ Salvando no Excel e Sistema...", "Salvando no Excel e Sistema..."),
    ("🎉 Ficha salva com sucesso!", "Ficha salva com sucesso!"),
    ("⚠️ Nada para copiar.", "Nada para copiar."),
    ("📋 Copiado com sucesso!", "Copiado com sucesso!"),
    ("✅ Emitida (NFS-e", "Emitida (NFS-e"),
    ("⏳ Pendente", "Pendente"),
    ("<span class=\"fiscal-item-desc\">🔧 ${escapeHtml(s.desc)}", "<span class=\"fiscal-item-desc\">${escapeHtml(s.desc)}"),
    ("✅ Emitida (NF-e", "Emitida (NF-e"),
    ("📋 Discriminação NFS-e copiada com sucesso!", "Discriminação NFS-e copiada com sucesso!"),
    ("👤 Dados do Tomador copiados!", "Dados do Tomador copiados!"),
    ("🔢 CPF sem pontuação copiado:", "CPF sem pontuação copiado:"),
    ("📍 CEP copiado:", "CEP copiado:"),
    ("🗺️ Endereço em 1 linha copiado!", "Endereço em 1 linha copiado!"),
    ("💰 Valor de Mão de Obra copiado:", "Valor de Mão de Obra copiado:"),
    ("📋 Lista de Peças e Valores copiada!", "Lista de Peças e Valores copiada!"),
    ("📊 Tabela TSV copiada!", "Tabela TSV copiada!"),
    ("💰 Valor de Peças copiado:", "Valor de Peças copiado:"),
    ("👤 Dados do Destinatário copiados!", "Dados do Destinatário copiados!"),
    ("👤 Ficha cadastral do tomador copiada!", "Ficha cadastral do tomador copiada!"),
    ("📍 CEP sem traço copiado:", "CEP sem traço copiado:"),
    ("📋 Copiado:", "Copiado:"),
    ("✅ NFS-e #${num || 'S/N'} marcada como EMITIDA!", "NFS-e #${num || 'S/N'} marcada como EMITIDA!"),
    ("✅ Marcar NFS-e Emitida", "Marcar NFS-e Emitida"),
    ("✅ NF-e #${num || 'S/N'} marcada como EMITIDA!", "NF-e #${num || 'S/N'} marcada como EMITIDA!"),
    ("✅ Marcar NF-e Emitida", "Marcar NF-e Emitida"),
    ("🎉 Parabéns! Nenhuma nota fiscal pendente", "Nenhuma nota fiscal pendente"),
    ("badge-status-pill emitted\">✅ NFS-e", "badge-status-pill emitted\">NFS-e"),
    ("badge-status-pill pending\">⏳ NFS-e", "badge-status-pill pending\">NFS-e"),
    ("badge-status-pill emitted\">✅ NF-e", "badge-status-pill emitted\">NF-e"),
    ("badge-status-pill pending\">⏳ NF-e", "badge-status-pill pending\">NF-e"),
    ("• 👤 ${escapeHtml(item.client_name || 'Cliente')}", "• ${escapeHtml(item.client_name || 'Cliente')}"),
    ("<span class=\"fiscal-card-date\">📅 ${escapeHtml(item.entry_date || '-')}", "<span class=\"fiscal-card-date\">${escapeHtml(item.entry_date || '-')}"),
    ("⚡ Abrir no Copiloto", "Abrir no Copiloto"),
    ("📋 Copiar NFS-e", "Copiar NFS-e"),
    ("🔩 Copiar Peças", "Copiar Peças"),
    ("📋 Discriminação NFS-e de", "Discriminação NFS-e de"),
    ("📊 Tabela TSV de Peças de", "Tabela TSV de Peças de"),
    ("📋 Copiar Texto", "Copiar Texto"),
    ("🔍 Zoom ajustado", "Zoom ajustado"),
    ("🔍 Zoom restaurado", "Zoom restaurado"),
    ("⏳ Escolhendo...", "Escolhendo..."),
    ("📂 Alterar Pasta", "Alterar Pasta"),
    ("⏳ Atualizando...", "Atualizando..."),
    ("✓ Atualizado!", "Atualizado!"),
    ("🔄 Atualizar Lista", "Atualizar Lista"),
    ("✓ Planilha aberta no Excel", "Planilha aberta no Excel"),
    ("✓ Atualização instalada!", "Atualização instalada!")
]

for old, new in replacements:
    code = code.replace(old, new)

# 4. Melhora itens do pátio para usar Mercosul plate e Brand Logo
old_patio_row = """                row.innerHTML = `
                    <div class="patio-item-info">
                        <span class="patio-item-plate">${escapeHtml(car.plate_display || car.plate)}</span>
                        <div class="patio-item-details">
                            <span class="patio-item-model">${escapeHtml(car.car_model || 'Veículo')} ${car.car_color ? `(${escapeHtml(car.car_color)})` : ''} - 👤 ${escapeHtml(car.client_name || 'Cliente')}</span>
                            <span class="patio-item-sub">${car.box_mecanico ? `🔧 ${escapeHtml(car.box_mecanico)} ` : ''}${car.notes ? `• ${escapeHtml(car.notes)}` : ''}${authInfo}</span>
                        </div>
                    </div>
                    <span class="patio-status-badge ${badgeClass}">${escapeHtml(car.status)}</span>
                `;"""

new_patio_row = """                const carInfo = window.CarCatalog ? window.CarCatalog.identifyCar(car.car_model || '') : null;
                const brandLogoHtml = (carInfo && window.CarCatalog) ? window.CarCatalog.renderBrandLogoHtml(carInfo.brandKey, 26) : '';
                const plateHtml = window.CarCatalog 
                    ? window.CarCatalog.renderMercosulPlateHtml(car.plate_display || car.plate, 'sm') 
                    : `<span class="patio-item-plate">${escapeHtml(car.plate_display || car.plate)}</span>`;

                row.innerHTML = `
                    <div class="patio-item-info" style="display: flex; align-items: center; gap: 10px;">
                        ${plateHtml}
                        ${brandLogoHtml}
                        <div class="patio-item-details">
                            <span class="patio-item-model">${escapeHtml(car.car_model || 'Veículo')} ${car.car_color ? `(${escapeHtml(car.car_color)})` : ''} - ${escapeHtml(car.client_name || 'Cliente')}</span>
                            <span class="patio-item-sub">${car.box_mecanico ? `${escapeHtml(car.box_mecanico)} ` : ''}${car.notes ? `• ${escapeHtml(car.notes)}` : ''}${authInfo}</span>
                        </div>
                    </div>
                    <span class="patio-status-badge ${badgeClass}">${escapeHtml(car.status)}</span>
                `;"""

if old_patio_row in code:
    code = code.replace(old_patio_row, new_patio_row)

# 5. Melhora cards na fila fiscal para usar Mercosul plate e Brand Logo
old_fiscal_card = """            card.innerHTML = `
                <div class="fiscal-card-header">
                    <div>
                        <span class="fiscal-card-plate">${escapeHtml(plateDisp)}</span>
                        <span class="fiscal-card-client">• 👤 ${escapeHtml(item.client_name || 'Cliente')}</span>
                        <span class="fiscal-card-model">• ${escapeHtml(item.car_model || 'Veículo')}</span>
                    </div>
                    <span class="fiscal-card-date">📅 ${escapeHtml(item.entry_date || '-')}</span>
                </div>"""

new_fiscal_card = """            const carInfo = window.CarCatalog ? window.CarCatalog.identifyCar(item.car_model || '') : null;
            const brandLogoHtml = (carInfo && window.CarCatalog) ? window.CarCatalog.renderBrandLogoHtml(carInfo.brandKey, 24) : '';
            const plateHtml = window.CarCatalog 
                ? window.CarCatalog.renderMercosulPlateHtml(plateDisp, 'sm')
                : `<span class="fiscal-card-plate">${escapeHtml(plateDisp)}</span>`;

            card.innerHTML = `
                <div class="fiscal-card-header" style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        ${plateHtml}
                        ${brandLogoHtml}
                        <span class="fiscal-card-client">• ${escapeHtml(item.client_name || 'Cliente')}</span>
                        <span class="fiscal-card-model">• ${escapeHtml(item.car_model || 'Veículo')}</span>
                    </div>
                    <span class="fiscal-card-date">${escapeHtml(item.entry_date || '-')}</span>
                </div>"""

if old_fiscal_card in code:
    code = code.replace(old_fiscal_card, new_fiscal_card)

with open("static/app.js", "w", encoding="utf-8") as f:
    f.write(code)

print("static/app.js atualizado com sucesso!")
