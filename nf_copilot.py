# -*- coding: utf-8 -*-
"""
MecatroniCar - Copiloto de Notas Fiscais (CP-07)
Módulo inteligente para separação de Mão de Obra (NFS-e Prefeitura de Santos - Item 14.01)
e Peças (NF-e Modelo 55 - Autopeças), com gerador de textos em 1 clique, sugestão fiscal
(NCM/CFOP) e fila de pendências.
"""

import re

COMPANY_INFO = {
    "razao_social": "Mecatroni Car - Serviços e Autopeças Ltda",
    "nome_fantasia": "MecatroniCar",
    "cnpj": "05.961.672/0001-87",
    "cnpj_raw": "05961672000187",
    "inscricao_municipal": "Santos/SP",
    "cidade": "Santos",
    "uf": "SP",
    "cnae_servicos": "4520-0/01",
    "cnae_servicos_desc": "Serviços de manutenção e reparação mecânica de veículos automotores",
    "item_lc116": "14.01",
    "item_lc116_desc": "Lubrificação, limpeza, revisão, conserto, restauração, manutenção e conservação de máquinas, veículos, motores e equipamentos",
    "cnae_pecas": "4530-7/03",
    "cnae_pecas_desc": "Comércio a varejo de peças e acessórios novos para veículos automotores",
    "cfop_pecas_padrao": "5.405",
    "cfop_pecas_desc": "Venda de mercadoria adquirida ou recebida de terceiros em operação c/ ICMS-ST recolhido anteriormente",
    "ncm_pecas_padrao": "8708.29.99",
}

# Tabela de sugestão inteligente de NCM conforme palavras-chave
NCM_KEYWORD_RULES = [
    (r"\b(oleo|óleo|lubrificante|fluido|aditivo)\b", "2710.19.32", "Óleos lubrificantes automotivos"),
    (r"\b(filtro de oleo|filtro de óleo|filtro oleo|filtro óleo|filtro combustivel|filtro combustível)\b", "8421.23.00", "Filtros de óleo ou combustível para motores de ignição"),
    (r"\b(filtro de ar|filtro ar|filtro de cabine|filtro ar condicionado)\b", "8421.31.00", "Filtros de entrada de ar para motores de combustão"),
    (r"\b(pastilha|disco|freio|lona|tambor|cilindro mestre|cilindro roda|servo freio|hidrovacuo)\b", "8708.30.90", "Freios e servo-freios, guarnições montadas"),
    (r"\b(amortecedor|suspensao|suspensão|mola|batente|coxim|bieleta|pivo|pivô|bandeja|bucha)\b", "8708.80.00", "Sistemas de suspensão e suas partes (amortecedores)"),
    (r"\b(vela|velas|ignicao|ignição|cabo de vela|bobina)\b", "8511.10.00", "Velas de ignição e aparelhos elétricos de ignição"),
    (r"\b(bateria|acumulador)\b", "8507.10.10", "Acumuladores elétricos de chumbo para arranque"),
    (r"\b(correia|tensor|estirador|polia)\b", "4010.39.00", "Correias de transmissão de borracha vulcanizada"),
    (r"\b(bomba dagua|bomba d'agua|bomba d'água|radiador|valvula termostatica|válvula termostática)\b", "8413.30.10", "Bombas para refrigerante do motor"),
    (r"\b(sensor|sonda|atuador|modulo|módulo)\b", "9031.80.99", "Instrumentos e sensores de controle e medida automotiva"),
    (r"\b(lampada|lâmpada|farol|lanterna)\b", "8512.20.11", "Aparelhos elétricos de iluminação e sinalização visual"),
    (r"\b(palheta|limpador)\b", "8512.90.00", "Partes de limpadores de para-brisas"),
    (r"\b(embreagem|disco embreagem|plato|platô|rolamento)\b", "8708.93.00", "Embreagens e suas partes"),
]

def suggest_fiscal_classification(description):
    """
    Retorna a sugestão inteligente de NCM, CFOP e CST/CSOSN para uma peça.
    """
    desc_lower = (description or "").lower()
    suggested_ncm = COMPANY_INFO["ncm_pecas_padrao"]
    ncm_desc = "Partes e acessórios para veículos automotores (Geral)"
    
    for pattern, ncm, ndesc in NCM_KEYWORD_RULES:
        if re.search(pattern, desc_lower, re.IGNORECASE):
            suggested_ncm = ncm
            ncm_desc = ndesc
            break

    return {
        "cfop": COMPANY_INFO["cfop_pecas_padrao"],
        "cfop_desc": COMPANY_INFO["cfop_pecas_desc"],
        "ncm": suggested_ncm,
        "ncm_desc": ncm_desc,
        "csosn": "500",
        "csosn_desc": "ICMS cobrado anteriormente por substituição tributária (Simples Nacional)"
    }

def clean_unmasked(value):
    if not value:
        return ""
    return re.sub(r'[^\w]', '', str(value))

def format_currency_raw(val_str):
    if not val_str:
        return "0,00"
    cleaned = str(val_str).replace("R$", "").strip()
    return cleaned

def format_tomador_data(details):
    """
    Gera dados do tomador formatados e em campos individuais prontos para cópia rápida.
    """
    name = (details.get("client_name") or "").strip()
    cpf = (details.get("cpf") or "").strip()
    cpf_raw = clean_unmasked(cpf)
    rg = (details.get("rg") or "").strip()
    phone = (details.get("phone") or details.get("tel_res") or details.get("tel_com") or "").strip()
    email = (details.get("email") or "").strip()
    
    address = (details.get("address") or "").strip()
    address_num = (details.get("address_num") or "").strip()
    address_compl = (details.get("address_compl") or "").strip()
    neighborhood = (details.get("neighborhood") or "").strip()
    city = (details.get("city") or "Santos").strip()
    uf = "SP"
    cep = (details.get("cep") or "").strip()
    cep_raw = clean_unmasked(cep)
    
    # Monta endereço completo legível em 1 linha
    addr_parts = []
    if address:
        if address_num:
            addr_parts.append(f"{address}, {address_num}")
        else:
            addr_parts.append(address)
    if address_compl:
        addr_parts.append(f"Compl: {address_compl}")
    if neighborhood:
        addr_parts.append(neighborhood)
    if city:
        addr_parts.append(f"{city}/{uf}")
    if cep:
        addr_parts.append(f"CEP {cep}")
    address_single_line = " - ".join(addr_parts)
    
    formatted_text = f"""DADOS DO TOMADOR / CLIENTE:
Nome / Razão Social: {name or 'Não informado'}
CPF / CNPJ: {cpf or 'Não informado'}
{f'RG: {rg}' if rg else ''}
{f'Telefone: {phone}' if phone else ''}
{f'E-mail: {email}' if email else ''}
Endereço: {address or ''}{f', {address_num}' if address_num else ''}{f' ({address_compl})' if address_compl else ''}
Bairro: {neighborhood or ''}
Município / UF: {city} / {uf}
CEP: {cep or ''}
""".strip()
    
    # Remove linhas vazias consecutivas
    formatted_text = "\n".join([line for line in formatted_text.splitlines() if line.strip()])

    return {
        "text": formatted_text,
        "name": name,
        "cpf": cpf,
        "cpf_raw": cpf_raw,
        "rg": rg,
        "phone": phone,
        "email": email,
        "address": address,
        "address_num": address_num,
        "address_compl": address_compl,
        "neighborhood": neighborhood,
        "city": city,
        "uf": uf,
        "cep": cep,
        "cep_raw": cep_raw,
        "address_single_line": address_single_line
    }

def format_nfse_discriminacao(details):
    """
    Gera o texto completo da 'Discriminação dos Serviços' para a NFS-e de Santos (Item 14.01).
    Formatado exatamente com placa, modelo, km, ano, itens de serviço e tomador.
    """
    plate_disp = details.get("plate_display") or details.get("plate") or "SEM PLACA"
    car_model = details.get("car_model") or "Veículo"
    car_year = details.get("car_year") or ""
    odometer = details.get("odometer") or ""
    visit_num = details.get("visit_num") or ""
    entry_date = details.get("entry_date") or ""
    total_servicos = details.get("total_servicos") or "R$ 0,00"
    client_name = details.get("client_name") or ""
    cpf = details.get("cpf") or ""
    
    servicos_items = details.get("servicos_items") or []
    if not servicos_items:
        # Se não houver itens explícitos de serviço, verifica complaint ou geral
        complaint = details.get("complaint") or ""
        if complaint:
            items_lines = [f"1. Serviços de manutenção preventiva e corretiva automotiva: {complaint}"]
        else:
            items_lines = ["1. Serviços de revisão e manutenção mecânica geral conforme Ordem de Serviço"]
    else:
        items_lines = []
        for idx, it in enumerate(servicos_items, start=1):
            desc = it.get("description", "").strip()
            tot = it.get("total_price", "").strip()
            unit = it.get("unit_price", "").strip()
            qty = it.get("quantity", "").strip()
            
            # Formatação do item
            price_tag = ""
            if tot and tot not in ("R$ 0,00", "0", "0,00"):
                price_tag = f" ({tot})"
            elif "cortesia" in desc.lower():
                price_tag = " (Cortesia)"
            elif tot in ("R$ 0,00", "0,00", "0"):
                price_tag = " (Cortesia / Incluso)"
                
            qty_prefix = f"[{qty}x] " if qty and qty not in ("1", "1,0", "-") else ""
            items_lines.append(f"{idx}. {qty_prefix}{desc}{price_tag}")
            
    services_block = "\n".join(items_lines)
    
    # Veículo header line
    veh_parts = [f"VEÍCULO: {car_model}"]
    if car_year:
        veh_parts.append(f"ANO: {car_year}")
    veh_parts.append(f"PLACA: {plate_disp}")
    if odometer:
        veh_parts.append(f"KM: {odometer}")
    if visit_num:
        veh_parts.append(f"OS: #{visit_num}")
    veh_line = " | ".join(veh_parts)
    
    text = f"""PRESTAÇÃO DE SERVIÇOS MECÂNICOS AUTOMOTIVOS - ITEM 14.01 (LC 116/03)
CNAE: {COMPANY_INFO['cnae_servicos']} - {COMPANY_INFO['cnae_servicos_desc'].upper()}
----------------------------------------------------------------------
{veh_line}
{f'DATA DE ENTRADA: {entry_date}' if entry_date else ''}
----------------------------------------------------------------------
SERVIÇOS EXECUTADOS / MÃO DE OBRA:
{services_block}

VALOR TOTAL DA MÃO DE OBRA: {total_servicos}
----------------------------------------------------------------------
TOMADOR: {client_name}{f' - CPF/CNPJ: {cpf}' if cpf else ''}
EMISSOR: {COMPANY_INFO['razao_social']} | CNPJ: {COMPANY_INFO['cnpj']} | SANTOS/SP
""".strip()

    # Limpa linhas vazias duplas
    cleaned_lines = [l for l in text.splitlines() if l.strip()]
    return "\n".join(cleaned_lines)

def format_nfe_pecas_text(details):
    """
    Gera o texto resumo das Peças para a NF-e Modelo 55 (Autopeças / Sefaz-SP).
    """
    plate_disp = details.get("plate_display") or details.get("plate") or "SEM PLACA"
    car_model = details.get("car_model") or "Veículo"
    visit_num = details.get("visit_num") or ""
    total_pecas = details.get("total_pecas") or "R$ 0,00"
    client_name = details.get("client_name") or ""
    cpf = details.get("cpf") or ""
    
    pecas_items = details.get("pecas_items") or []
    items_lines = []
    
    for idx, it in enumerate(pecas_items, start=1):
        desc = it.get("description", "").strip()
        qty = it.get("quantity", "1").strip() or "1"
        unit = it.get("unit_price", "").strip()
        tot = it.get("total_price", "").strip() or unit
        fisc = suggest_fiscal_classification(desc)
        
        items_lines.append(
            f"{idx}. {desc} | Qtd: {qty} | Unit: {unit or tot} | Total: {tot} (NCM: {fisc['ncm']} / CFOP: {fisc['cfop']})"
        )
        
    items_block = "\n".join(items_lines) if items_lines else "Nenhuma peça discriminada nesta visita."
    
    text = f"""PEÇAS E AUTOPEÇAS APLICADAS - NF-e MODELO 55 (ICMS / SEFAZ-SP)
CNAE: {COMPANY_INFO['cnae_pecas']} - {COMPANY_INFO['cnae_pecas_desc'].upper()}
CFOP PADRÃO: {COMPANY_INFO['cfop_pecas_padrao']} (AUTOPEÇAS C/ ICMS-ST)
----------------------------------------------------------------------
VEÍCULO: {car_model} | PLACA: {plate_disp}{f' | OS: #{visit_num}' if visit_num else ''}
----------------------------------------------------------------------
ITENS / AUTOPEÇAS:
{items_block}

VALOR TOTAL DAS PEÇAS: {total_pecas}
----------------------------------------------------------------------
DESTINATÁRIO: {client_name}{f' | CPF/CNPJ: {cpf}' if cpf else ''}
EMITENTE: {COMPANY_INFO['razao_social']} | CNPJ: {COMPANY_INFO['cnpj']} | SANTOS/SP
""".strip()

    return text

def format_nfe_pecas_tsv(details):
    """
    Gera tabela TSV (Tab-Separated Values) das peças para colar direto no Excel ou em emissores fiscais.
    """
    pecas_items = details.get("pecas_items") or []
    lines = ["Item\tQuantidade\tDescrição da Peça\tValor Unitário\tValor Total\tNCM Sugerido\tCFOP Sugerido"]
    
    for idx, it in enumerate(pecas_items, start=1):
        desc = it.get("description", "").strip()
        qty = it.get("quantity", "1").strip() or "1"
        unit = format_currency_raw(it.get("unit_price", ""))
        tot = format_currency_raw(it.get("total_price", "") or unit)
        fisc = suggest_fiscal_classification(desc)
        lines.append(f"{idx}\t{qty}\t{desc}\t{unit}\t{tot}\t{fisc['ncm']}\t{fisc['cfop']}")
        
    return "\n".join(lines)

def build_copilot_payload(file_path, details, nf_status=None):
    """
    Prepara a carga completa com separação de Peças vs Serviços, textos prontos
    para cópia em 1 clique, sugestões fiscais e status de persistência.
    """
    details = details or {}
    nf_status = nf_status or {}
    
    pecas = details.get("pecas_items") or []
    servicos = details.get("servicos_items") or []
    
    # Enriquecimento com sugestão fiscal
    enriched_pecas = []
    for it in pecas:
        it_copy = dict(it)
        fisc = suggest_fiscal_classification(it_copy.get("description", ""))
        it_copy["suggested_ncm"] = fisc["ncm"]
        it_copy["suggested_ncm_desc"] = fisc["ncm_desc"]
        it_copy["suggested_cfop"] = fisc["cfop"]
        it_copy["suggested_csosn"] = fisc["csosn"]
        enriched_pecas.append(it_copy)
        
    enriched_servicos = []
    for it in servicos:
        it_copy = dict(it)
        it_copy["suggested_item_lc116"] = COMPANY_INFO["item_lc116"]
        it_copy["suggested_item_desc"] = COMPANY_INFO["item_lc116_desc"]
        enriched_servicos.append(it_copy)
        
    tomador = format_tomador_data(details)
    nfse_text = format_nfse_discriminacao(details)
    nfe_text = format_nfe_pecas_text(details)
    nfe_tsv = format_nfe_pecas_tsv(details)
    
    total_serv = details.get("total_servicos") or "R$ 0,00"
    total_pec = details.get("total_pecas") or "R$ 0,00"
    total_geral = details.get("total") or details.get("subtotal") or "R$ 0,00"

    # Determina se há peças/serviços para faturar
    has_services = len(servicos) > 0 or (total_serv not in ("", "R$ 0,00", "0", "0,00"))
    has_parts = len(pecas) > 0 or (total_pec not in ("", "R$ 0,00", "0", "0,00"))

    # Preenche status padrão se não persistido
    nfse_status_val = nf_status.get("nfse_status")
    if not nfse_status_val:
        nfse_status_val = "pendente" if has_services else "nao_se_aplica"

    nfe_status_val = nf_status.get("nfe_status")
    if not nfe_status_val:
        nfe_status_val = "pendente" if has_parts else "nao_se_aplica"

    return {
        "file_path": file_path,
        "company": COMPANY_INFO,
        "plate": details.get("plate", ""),
        "plate_display": details.get("plate_display", ""),
        "client_name": details.get("client_name", ""),
        "car_model": details.get("car_model", ""),
        "car_year": details.get("car_year", ""),
        "visit_num": details.get("visit_num", ""),
        "entry_date": details.get("entry_date", ""),
        "odometer": details.get("odometer", ""),
        "payment_method": details.get("payment_method", ""),
        "has_services": has_services,
        "has_parts": has_parts,
        "servicos_items": enriched_servicos,
        "pecas_items": enriched_pecas,
        "total_servicos": total_serv,
        "total_pecas": total_pec,
        "total_geral": total_geral,
        "tomador": tomador,
        "copilot_texts": {
            "nfse_discriminacao": nfse_text,
            "tomador_resumo": tomador["text"],
            "nfe_pecas_resumo": nfe_text,
            "nfe_pecas_tsv": nfe_tsv
        },
        "nf_status": {
            "file_path": file_path,
            "nfse_status": nfse_status_val,
            "nfse_number": nf_status.get("nfse_number", ""),
            "nfse_date": nf_status.get("nfse_date", "") or details.get("entry_date", ""),
            "nfse_value": nf_status.get("nfse_value", "") or total_serv,
            "nfe_status": nfe_status_val,
            "nfe_number": nf_status.get("nfe_number", ""),
            "nfe_date": nf_status.get("nfe_date", "") or details.get("entry_date", ""),
            "nfe_value": nf_status.get("nfe_value", "") or total_pec,
            "notes": nf_status.get("notes", ""),
            "persisted": bool(nf_status.get("updated_at") or nf_status.get("created_at"))
        }
    }
