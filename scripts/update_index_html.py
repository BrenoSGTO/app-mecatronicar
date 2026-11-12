# -*- coding: utf-8 -*-
import re

with open("static/index.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Scripts: include car_catalog.js
if "car_catalog.js" not in content:
    content = content.replace(
        '<script src="app.js',
        '<script src="car_catalog.js?v=2.0.0"></script>\n    <script src="app.js'
    )

# 2. Vehicle Banner Mercosul plate, brand logo and silhouette
old_banner_plate = """                <div class="plate-card-wrapper">
                    <div class="brasil-plate">
                        <div class="plate-top">
                            <span class="plate-country">BRASIL</span>
                            <span class="plate-flag">🇧🇷</span>
                        </div>
                        <div class="plate-number" id="detail-plate">AAA-0000</div>
                    </div>
                </div>"""

new_banner_plate = """                <div class="plate-card-wrapper">
                    <div class="mercosul-plate mercosul-plate-lg" id="detail-plate-card">
                        <div class="mercosul-top-bar">
                            <span class="mercosul-country">BRASIL</span>
                            <span class="mercosul-br-box">
                                <span class="mercosul-br-text">BR</span>
                                <svg class="mercosul-mini-flag" viewBox="0 0 20 14" width="14" height="10">
                                    <rect width="20" height="14" fill="#009b3a" rx="1"/>
                                    <polygon points="10,1.5 18.5,7 10,12.5 1.5,7" fill="#fedf00"/>
                                    <circle cx="10" cy="7" r="3.2" fill="#002776"/>
                                </svg>
                            </span>
                        </div>
                        <div class="mercosul-body-area">
                            <span class="mercosul-number" id="detail-plate">AAA-0000</span>
                        </div>
                    </div>
                </div>

                <div id="detail-brand-box" class="brand-logo-container" style="width: 58px; height: 58px;" title="Montadora">
                    <img id="detail-brand-logo" src="/static/brands/generic.svg" alt="Montadora" class="brand-logo-img">
                </div>"""

if old_banner_plate in content:
    content = content.replace(old_banner_plate, new_banner_plate)

# Add silhouette container in vehicle banner after vehicle-info-block if not present
old_info_block_end = """                        <span class="tag tag-chassis" id="detail-car-chassis">Chassi</span>
                    </div>
                </div>"""

new_info_block_end = """                        <span class="tag tag-chassis" id="detail-car-chassis">Chassi</span>
                    </div>
                </div>

                <div id="detail-silhouette-box" class="car-silhouette-container" style="max-width: 175px; height: 64px;" title="Silhueta do Modelo">
                    <img id="detail-car-silhouette" src="/static/models/car-generic.svg" alt="Silhueta" class="car-silhouette-img">
                </div>"""

if old_info_block_end in content and "detail-silhouette-box" not in content:
    content = content.replace(old_info_block_end, new_info_block_end)

# 3. Direct emoji string replacements in index.html
replacements = [
    ('<span class="zoom-label">🔍 Zoom:</span>', '<span class="zoom-label">Zoom:</span>'),
    ('📺 Painel TV', 'Painel TV'),
    ('🚗 Pátio', 'Pátio'),
    ('➕ Nova Visita / OS', 'Nova Visita / OS'),
    ('🧾 Copiloto Fiscal', 'Copiloto Fiscal'),
    ('✨ Atualizações', 'Atualizações'),
    ('<span class="folder-label">📁 Pasta:</span>', '<span class="folder-label">Pasta:</span>'),
    ('📂 Alterar Pasta', 'Alterar Pasta'),
    ('🔄 Atualizar Lista', 'Atualizar Lista'),
    ('<div class="search-icon">🔍</div>', '<div class="search-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></div>'),
    ('>✕</button>', '>&times;</button>'),
    ('➕ Nova Visita', 'Nova Visita'),
    ('📄 Orçamento (PDF)', 'Orçamento (PDF)'),
    ('📋 Checklist', 'Checklist'),
    ('📑 Copiloto Fiscal', 'Copiloto Fiscal'),
    ('📍 Status no Pátio', 'Status no Pátio'),
    ('🖨️ Imprimir', 'Imprimir'),
    ('📄 Sem Preços', 'Sem Preços'),
    ('<span class="vehicle-item-search-icon">🔧</span>', '<span class="vehicle-item-search-icon"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg></span>'),
    ('🛠️ Mostrar Serviços Feitos em Todas as Planilhas', 'Mostrar Serviços Feitos em Todas as Planilhas'),
    ('<span class="modal-icon">📝</span>', '<span class="modal-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg></span>'),
    ('📋 Copiar Texto', 'Copiar Texto'),
    ('<div style="font-size: 32px; margin-bottom: 12px; animation: spin 1s infinite linear;">🔄</div>', '<div style="font-size: 32px; margin-bottom: 12px;"><svg viewBox="0 0 24 24" width="32" height="32" fill="none" stroke="#0284c7" stroke-width="2" class="app-icon" style="animation: spin 1s infinite linear;"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg></div>'),
    ('<div style="font-size: 38px; margin-bottom: 12px;">✅</div>', '<div style="font-size: 38px; margin-bottom: 12px;"><svg viewBox="0 0 24 24" width="38" height="38" fill="none" stroke="#10b981" stroke-width="2" class="app-icon"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg></div>'),
    ('🎉 Nova versão encontrada:', 'Nova versão encontrada:'),
    ('🚀 Atualizar Agora Automaticamente', 'Atualizar Agora Automaticamente'),
    ('<h3 id="patio-modal-title" class="modal-title">🚗 Gerenciar Pátio da Oficina</h3>', '<h3 id="patio-modal-title" class="modal-title">Gerenciar Pátio da Oficina</h3>'),
    ('📺 Abrir Painel TV', 'Abrir Painel TV'),
    ('🔍 Em Diagnóstico', 'Em Diagnóstico'),
    ('📝 Esperando Orçamento', 'Esperando Orçamento'),
    ('⏳ Esperando Aprovação', 'Esperando Aprovação'),
    ('📦 Esperando Peças', 'Esperando Peças'),
    ('🔧 Em Execução', 'Em Execução'),
    ('✅ Esperando Cliente Buscar', 'Esperando Cliente Buscar'),
    ('🔑 Liberado p/ Retirada por Terceiro', 'Liberado p/ Retirada por Terceiro'),
    ('🔑 Liberado p/ Terceiro', 'Liberado p/ Terceiro'),
    ('🔑 Dados de Quem Está Autorizado a Buscar o Carro:', 'Dados de Quem Está Autorizado a Buscar o Carro:'),
    ('🗑️ Remover do Pátio', 'Remover do Pátio'),
    ('💾 Salvar no Pátio', 'Salvar no Pátio'),
    ('<span class="modal-icon">🛠️</span>', '<span class="modal-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg></span>'),
    ('🔍 Buscar Cliente ou Carro Já Cadastrado (Preenchimento Automático):', 'Buscar Cliente ou Carro Já Cadastrado (Preenchimento Automático):'),
    ('🚗 Dados do Veículo &amp; Entrada na Oficina', 'Dados do Veículo &amp; Entrada na Oficina'),
    ('<span id="os-plate-spinner" class="os-spinner-icon" style="display: none;">🔄</span>', '<span id="os-plate-spinner" class="os-spinner-icon" style="display: none;"><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg></span>'),
    ('✅ Pronto / Esperando Cliente', 'Pronto / Esperando Cliente'),
    ('👤 Dados Cadastrais do Cliente (Ficha Legacy)', 'Dados Cadastrais do Cliente (Ficha Legacy)'),
    ('📦 Peças Utilizadas', 'Peças Utilizadas'),
    ('➕ Adicionar Peça', 'Adicionar Peça'),
    ('⚡ Sugestões Rápidas:', 'Sugestões Rápidas:'),
    ('🔧 Serviços / Mão de Obra', 'Serviços / Mão de Obra'),
    ('➕ Adicionar Serviço', 'Adicionar Serviço'),
    ('💾 Salvar Ficha no Excel (.xlsx) e Sistema', 'Salvar Ficha no Excel (.xlsx) e Sistema'),
    ('<span class="modal-icon">🧾</span>', '<span class="modal-icon"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" class="app-icon"><path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1Z"/><path d="M16 8h-8"/><path d="M16 12h-8"/><path d="M12 16h-4"/></svg></span>'),
    ('🟦 1. NFS-e Santos (Mão de Obra)', '1. NFS-e Santos (Mão de Obra)'),
    ('🟨 2. NF-e 55 (Peças / Autopeças)', '2. NF-e 55 (Peças / Autopeças)'),
    ('👤 3. Dados do Tomador', '3. Dados do Tomador'),
    ('📋 4. Fila de Notas Pendentes', '4. Fila de Notas Pendentes'),
    ('🏛️ Prefeitura Municipal de Santos • LC 116/03 Subitem 14.01', 'Prefeitura Municipal de Santos • LC 116/03 Subitem 14.01'),
    ('📋 Copiar Discriminação Formatada (1 Clique)', 'Copiar Discriminação Formatada'),
    ('⚡ Cópia Rápida:', 'Cópia Rápida:'),
    ('👤 Tomador', 'Tomador'),
    ('🆔 CPF', 'CPF'),
    ('📍 CEP', 'CEP'),
    ('🗺️ Endereço', 'Endereço'),
    ('💰 Valor Mão de Obra', 'Valor Mão de Obra'),
    ('🛠️ Itens de Serviço Detectados nesta Ordem de Serviço:', 'Itens de Serviço Detectados nesta Ordem de Serviço:'),
    ('✅ Marcar NFS-e Emitida', 'Marcar NFS-e Emitida'),
    ('🚗 Sefaz-SP • NF-e Modelo 55 • Comércio Varejista de Autopeças', 'Sefaz-SP • NF-e Modelo 55 • Comércio Varejista de Autopeças'),
    ('📋 Copiar Lista de Peças e Valores (1 Clique)', 'Copiar Lista de Peças e Valores'),
    ('📊 Copiar Tabela TSV (Excel/Emissor)', 'Copiar Tabela TSV (Excel/Emissor)'),
    ('💰 Copiar Total Peças', 'Copiar Total Peças'),
    ('👤 Copiar Destinatário', 'Copiar Destinatário'),
    ('✅ Marcar NF-e Emitida', 'Marcar NF-e Emitida'),
    ('👤 Dados Cadastrais do Tomador do Serviço / Destinatário', 'Dados Cadastrais do Tomador do Serviço / Destinatário'),
    ('📋 Copiar Todos os Dados', 'Copiar Todos os Dados'),
    ('>📋 Formatado<', '>Formatado<'),
    ('>🔢 Sem pontuação<', '>Sem pontuação<'),
    ('>🔢 Sem traço<', '>Sem traço<'),
    ('title="Copiar nome">📋</button>', 'title="Copiar nome">Copiar</button>'),
    ('title="Copiar telefone">📋</button>', 'title="Copiar telefone">Copiar</button>'),
    ('title="Copiar e-mail">📋</button>', 'title="Copiar e-mail">Copiar</button>'),
    ('title="Copiar endereço completo em linha única">📋 Linha Única</button>', 'title="Copiar endereço completo em linha única">Linha Única</button>'),
    ('title="Copiar rua e número">📋</button>', 'title="Copiar rua e número">Copiar</button>'),
    ('title="Copiar bairro">📋</button>', 'title="Copiar bairro">Copiar</button>'),
    ('title="Copiar cidade">📋</button>', 'title="Copiar cidade">Copiar</button>'),
    ('title="Copiar CEP">📋</button>', 'title="Copiar CEP">Copiar</button>'),
    ('⏳ Visitas c/ NFs Pendentes', 'Visitas c/ NFs Pendentes'),
    ('🛠️ NFS-e Serviços a Emitir', 'NFS-e Serviços a Emitir'),
    ('🔩 NF-e Peças a Emitir', 'NF-e Peças a Emitir'),
    ('✅ NFs Já Emitidas', 'NFs Já Emitidas'),
    ('🛠️ Só Mão de Obra', 'Só Mão de Obra'),
    ('🔩 Só Peças', 'Só Peças'),
    ('✅ Já Emitidas', 'Já Emitidas'),
    ('placeholder="🔍 Filtrar por placa, cliente, carro..."', 'placeholder="Filtrar por placa, cliente, carro..."'),
    ('📥 CSV', 'CSV'),
    ('📄 TXT', 'TXT'),
    ('<button id="btn-refresh-queue" class="btn-refresh-queue" title="Recarregar fila de notas fiscais">🔄</button>', '<button id="btn-refresh-queue" class="btn-refresh-queue" title="Recarregar fila de notas fiscais">Atualizar</button>')
]

for old, new in replacements:
    content = content.replace(old, new)

with open("static/index.html", "w", encoding="utf-8") as f:
    f.write(content)

print("static/index.html atualizado com sucesso!")
