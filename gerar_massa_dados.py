# -*- coding: utf-8 -*-
"""
gerar_massa_dados.py - MecatroniCar v2.0 (Issue #10)
Gerador robusto de massa de dados realista para a oficina MecatroniCar.

Cria ~200 planilhas .xlsx na pasta planilhas_exemplo/ com:
1. Variedade de clientes brasileiros realistas (Santos e Baixada Santista).
2. Variedade de visitas por veículo (1 até 24 visitas).
3. Clientes com múltiplos veículos associados.
4. Histórico compartilhado de veículos transferidos entre proprietários.
5. Peças e serviços reais com valores de mercado coerentes (Item 14.01 / NF-e 55).
6. Variedade de status de pátio (7 status oficiais) e controle fiscal (NFS-e Santos / NF-e 55).
7. Indexação completa no banco SQLite oficina_cache.db.
"""

import os
import sys
import json
import random
import datetime
import sqlite3
import argparse

import excel_writer
import parser
import cache
import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Arquivos legados originais que JAMAIS devem ser sobrescritos ou apagados
PRESERVED_LEGACY_FILES = [
    "DTZ 9080 - 35 - NATANAEL novo dono - Partner - Branco.xls",
    "EVI 2484 - 13 Cau  Raquel (cunhados ) NovoDono - (Nissan ) Sentra - Prata.xls",
    "FNB 1A77 -7 -  Danilo Pereira - VW Fox - Prata.xlsx",
    "FQE 5724 - 4 - Natanael - Sentra - Prata.xls"
]

PRESERVED_PLATES = {"DTZ9080", "EVI2484", "FNB1A77", "FQE5724", "TST9999", "XYZ9999"}

# ==============================================================================
# POOL DE CLIENTES BRASILEIROS REALISTAS (SANTOS / BAIXADA SANTISTA)
# ==============================================================================

CLIENTS_POOL = [
    {
        "name": "Carlos Eduardo Silveira",
        "cpf": "184.920.348-12",
        "rg": "28.491.023-4",
        "phone": "(13) 99712-3456",
        "tel_res": "(13) 3289-1122",
        "address": "Av. Ana Costa",
        "address_num": "450",
        "address_compl": "Apto 82",
        "neighborhood": "Gonzaga",
        "city": "Santos",
        "cep": "11060-002",
        "email": "carlos.silveira@gmail.com"
    },
    {
        "name": "Juliana Martins Ferreira",
        "cpf": "291.834.756-33",
        "rg": "34.120.985-7",
        "phone": "(13) 98144-8890",
        "tel_res": "(13) 3224-5566",
        "address": "Av. Conselheiro Nébias",
        "address_num": "620",
        "address_compl": "Conj 41",
        "neighborhood": "Boqueirão",
        "city": "Santos",
        "cep": "11045-001",
        "email": "juliana.martins.adv@uol.com.br"
    },
    {
        "name": "Rodrigo Albuquerque",
        "cpf": "382.741.905-44",
        "rg": "41.562.839-1",
        "phone": "(13) 99105-2244",
        "tel_res": "(13) 3232-4411",
        "address": "R. Dr. Carvalho de Mendonça",
        "address_num": "315",
        "address_compl": "",
        "neighborhood": "Campo Grande",
        "city": "Santos",
        "cep": "11070-101",
        "email": "rodrigo.albuquerque@hotmail.com"
    },
    {
        "name": "Ana Paula Guimarães",
        "cpf": "473.652.819-55",
        "rg": "37.894.102-8",
        "phone": "(13) 99655-7788",
        "tel_res": "(13) 3284-9900",
        "address": "Av. Bartolomeu de Gusmão",
        "address_num": "98",
        "address_compl": "Apto 12",
        "neighborhood": "Embaré",
        "city": "Santos",
        "cep": "11045-401",
        "email": "anapaula.guimaraes@gmail.com"
    },
    {
        "name": "Lucas de Souza Mendes",
        "cpf": "564.563.728-66",
        "rg": "45.231.670-3",
        "phone": "(13) 98822-3344",
        "tel_res": "(13) 3227-8899",
        "address": "Av. Washington Luís",
        "address_num": "210",
        "address_compl": "Bloco B Apto 54",
        "neighborhood": "Encruzilhada",
        "city": "Santos",
        "cep": "11050-200",
        "email": "lucas.mendes@outlook.com"
    },
    {
        "name": "Patrícia Lima Castro",
        "cpf": "655.474.637-77",
        "rg": "29.741.058-2",
        "phone": "(13) 99133-6677",
        "tel_res": "(13) 3286-3344",
        "address": "R. Tolentino Filgueiras",
        "address_num": "85",
        "address_compl": "Apto 101",
        "neighborhood": "Gonzaga",
        "city": "Santos",
        "cep": "11060-300",
        "email": "patricia.castro@gmail.com"
    },
    {
        "name": "Fernando Henrique Ribeiro",
        "cpf": "746.385.546-88",
        "rg": "32.658.914-9",
        "phone": "(13) 99788-9900",
        "tel_res": "(13) 3236-7788",
        "address": "Av. Afonso Pena",
        "address_num": "512",
        "address_compl": "",
        "neighborhood": "Ponta da Praia",
        "city": "Santos",
        "cep": "11030-001",
        "email": "fernando.ribeiro@terra.com.br"
    },
    {
        "name": "Camila Barbosa Santos",
        "cpf": "837.296.455-99",
        "rg": "48.192.304-5",
        "phone": "(13) 98111-5544",
        "tel_res": "(13) 3221-3322",
        "address": "R. Frei Galvão",
        "address_num": "42",
        "address_compl": "Apto 31",
        "neighborhood": "Embaré",
        "city": "Santos",
        "cep": "11040-080",
        "email": "camila.barbosa@gmail.com"
    },
    {
        "name": "Marcelo Nogueira",
        "cpf": "928.107.364-00",
        "rg": "23.456.789-0",
        "phone": "(13) 99177-8899",
        "tel_res": "(13) 3288-4455",
        "address": "R. Galeão Carvalhal",
        "address_num": "118",
        "address_compl": "Apto 44",
        "neighborhood": "Gonzaga",
        "city": "Santos",
        "cep": "11055-200",
        "email": "marcelo.nogueira@uol.com.br"
    },
    {
        "name": "Beatriz Rocha de Oliveira",
        "cpf": "139.018.273-11",
        "rg": "43.987.654-1",
        "phone": "(13) 99633-2211",
        "tel_res": "(13) 3231-6677",
        "address": "Av. Presidente Wilson",
        "address_num": "1800",
        "address_compl": "Apto 71",
        "neighborhood": "José Menino",
        "city": "Santos",
        "cep": "11065-201",
        "email": "beatriz.rocha@gmail.com"
    },
    {
        "name": "Thiago Cavalcante",
        "cpf": "240.129.384-22",
        "rg": "36.541.289-4",
        "phone": "(13) 98844-5566",
        "tel_res": "(13) 3223-9988",
        "address": "R. Oswaldo Cruz",
        "address_num": "285",
        "address_compl": "Conj 12",
        "neighborhood": "Boqueirão",
        "city": "Santos",
        "cep": "11045-101",
        "email": "thiago.cavalcante@yahoo.com.br"
    },
    {
        "name": "Mariana Costa e Silva",
        "cpf": "351.230.495-33",
        "rg": "40.123.456-7",
        "phone": "(13) 99766-4433",
        "tel_res": "(13) 3284-1100",
        "address": "R. Trabulsi",
        "address_num": "77",
        "address_compl": "Apto 93",
        "neighborhood": "Ponta da Praia",
        "city": "Santos",
        "cep": "11030-500",
        "email": "mariana.costa.silva@gmail.com"
    },
    {
        "name": "Gabriel Freitas",
        "cpf": "462.341.506-44",
        "rg": "47.890.123-2",
        "phone": "(13) 98155-9988",
        "tel_res": "(13) 3234-7766",
        "address": "Av. Almirante Cochrane",
        "address_num": "134",
        "address_compl": "",
        "neighborhood": "Aparecida",
        "city": "Santos",
        "cep": "11040-002",
        "email": "gabriel.freitas@gmail.com"
    },
    {
        "name": "Vanessa Moreira",
        "cpf": "573.452.617-55",
        "rg": "35.678.901-3",
        "phone": "(13) 99122-8877",
        "tel_res": "(13) 3289-5544",
        "address": "R. Floriano Peixoto",
        "address_num": "190",
        "address_compl": "Apto 52",
        "neighborhood": "Gonzaga",
        "city": "Santos",
        "cep": "11060-302",
        "email": "vanessa.moreira@hotmail.com"
    },
    {
        "name": "André Luiz Peixoto",
        "cpf": "684.563.728-66",
        "rg": "31.234.567-8",
        "phone": "(13) 99744-1122",
        "tel_res": "(13) 3225-4433",
        "address": "R. Saturnino de Brito",
        "address_num": "95",
        "address_compl": "",
        "neighborhood": "Marapé",
        "city": "Santos",
        "cep": "11070-001",
        "email": "andre.peixoto@gmail.com"
    },
    {
        "name": "Renata Fernandes",
        "cpf": "795.674.839-77",
        "rg": "42.345.678-9",
        "phone": "(13) 98133-7766",
        "tel_res": "(13) 3286-9988",
        "address": "Av. Vicente de Carvalho",
        "address_num": "45",
        "address_compl": "Apto 141",
        "neighborhood": "Boqueirão",
        "city": "Santos",
        "cep": "11045-500",
        "email": "renata.fernandes@uol.com.br"
    },
    {
        "name": "Bruno Correia",
        "cpf": "806.785.940-88",
        "rg": "38.901.234-5",
        "phone": "(13) 99188-3322",
        "tel_res": "(13) 3237-1199",
        "address": "R. Princesa Isabel",
        "address_num": "65",
        "address_compl": "",
        "neighborhood": "Vila Belmiro",
        "city": "Santos",
        "cep": "11075-501",
        "email": "bruno.correia@gmail.com"
    },
    {
        "name": "Letícia Dias Prado",
        "cpf": "917.896.051-99",
        "rg": "46.789.012-4",
        "phone": "(13) 99677-4455",
        "tel_res": "(13) 3288-6633",
        "address": "R. Marcílio Dias",
        "address_num": "84",
        "address_compl": "Apto 21",
        "neighborhood": "Gonzaga",
        "city": "Santos",
        "cep": "11060-280",
        "email": "leticia.prado@gmail.com"
    },
    {
        "name": "Rafael Duarte",
        "cpf": "128.907.162-00",
        "rg": "33.456.789-6",
        "phone": "(13) 98855-6677",
        "tel_res": "(13) 3222-8811",
        "address": "Av. Bernardino de Campos",
        "address_num": "340",
        "address_compl": "Apto 64",
        "neighborhood": "Campo Grande",
        "city": "Santos",
        "cep": "11070-002",
        "email": "rafael.duarte@gmail.com"
    },
    {
        "name": "Cláudia Regina Macedo",
        "cpf": "239.018.273-11",
        "rg": "27.890.123-5",
        "phone": "(13) 99722-9900",
        "tel_res": "(13) 3284-5522",
        "address": "R. Epitácio Pessoa",
        "address_num": "215",
        "address_compl": "Apto 81",
        "neighborhood": "Embaré",
        "city": "Santos",
        "cep": "11045-300",
        "email": "claudia.macedo@gmail.com"
    },
    {
        "name": "Diego Ramos Vieira",
        "cpf": "340.129.384-22",
        "rg": "39.012.345-8",
        "phone": "(13) 98166-4433",
        "tel_res": "(13) 3236-4477",
        "address": "Av. Presidente Wilson",
        "address_num": "480",
        "address_compl": "Apto 15",
        "neighborhood": "Gonzaguinha",
        "city": "São Vicente",
        "cep": "11310-000",
        "email": "diego.vieira@outlook.com"
    },
    {
        "name": "Aline Toledo Pires",
        "cpf": "451.230.495-33",
        "rg": "44.567.890-1",
        "phone": "(13) 99144-7788",
        "tel_res": "(13) 3289-2233",
        "address": "Av. Ayrton Senna",
        "address_num": "310",
        "address_compl": "Apto 102",
        "neighborhood": "Itararé",
        "city": "São Vicente",
        "cep": "11320-000",
        "email": "aline.pires@gmail.com"
    },
    {
        "name": "Gustavo Henrique Farias",
        "cpf": "562.341.506-44",
        "rg": "30.123.456-9",
        "phone": "(13) 99755-3344",
        "tel_res": "(13) 3224-9911",
        "address": "Av. Mal. Mallet",
        "address_num": "750",
        "address_compl": "Apto 42",
        "neighborhood": "Canto do Forte",
        "city": "Praia Grande",
        "cep": "11700-000",
        "email": "gustavo.farias@gmail.com"
    },
    {
        "name": "Larissa Monteiro Cruz",
        "cpf": "673.452.617-55",
        "rg": "41.234.567-0",
        "phone": "(13) 98877-2233",
        "tel_res": "(13) 3231-5588",
        "address": "Av. Costa e Silva",
        "address_num": "180",
        "address_compl": "Sala 3",
        "neighborhood": "Boqueirão",
        "city": "Praia Grande",
        "cep": "11700-100",
        "email": "larissa.cruz@gmail.com"
    },
    {
        "name": "Felipe Augusto Borges",
        "cpf": "784.563.728-66",
        "rg": "36.789.012-3",
        "phone": "(13) 99622-5566",
        "tel_res": "(13) 3286-4411",
        "address": "Av. Guilhermina",
        "address_num": "420",
        "address_compl": "Apto 33",
        "neighborhood": "Guilhermina",
        "city": "Praia Grande",
        "cep": "11701-000",
        "email": "felipe.borges@yahoo.com.br"
    },
    {
        "name": "Priscila Antunes Bueno",
        "cpf": "895.674.839-77",
        "rg": "49.012.345-6",
        "phone": "(13) 98188-1122",
        "tel_res": "(13) 3228-3355",
        "address": "R. Castro Alves",
        "address_num": "55",
        "address_compl": "",
        "neighborhood": "Embaré",
        "city": "Santos",
        "cep": "11040-120",
        "email": "priscila.bueno@gmail.com"
    },
    {
        "name": "Marcos Vinicius Tavares",
        "cpf": "906.785.940-88",
        "rg": "37.123.456-8",
        "phone": "(13) 99199-4455",
        "tel_res": "(13) 3234-8822",
        "address": "R. Moura Ribeiro",
        "address_num": "112",
        "address_compl": "Apto 11",
        "neighborhood": "Marapé",
        "city": "Santos",
        "cep": "11070-060",
        "email": "marcos.tavares@gmail.com"
    },
    {
        "name": "Tatiane Cristina Ramos",
        "cpf": "117.896.051-99",
        "rg": "45.678.901-2",
        "phone": "(13) 99733-8899",
        "tel_res": "(13) 3288-1144",
        "address": "R. Cunha Moreira",
        "address_num": "78",
        "address_compl": "",
        "neighborhood": "Encruzilhada",
        "city": "Santos",
        "cep": "11050-250",
        "email": "tatiane.ramos@gmail.com"
    },
    {
        "name": "Eduardo Paiva Lima",
        "cpf": "228.907.162-00",
        "rg": "28.901.234-7",
        "phone": "(13) 98833-4455",
        "tel_res": "(13) 3227-3366",
        "address": "Av. Saldanha da Gama",
        "address_num": "65",
        "address_compl": "Apto 84",
        "neighborhood": "Ponta da Praia",
        "city": "Santos",
        "cep": "11030-400",
        "email": "eduardo.paiva@gmail.com"
    },
    {
        "name": "Sabrina Mendes Fagundes",
        "cpf": "339.018.273-11",
        "rg": "43.210.987-5",
        "phone": "(13) 99644-7711",
        "tel_res": "(13) 3284-8877",
        "address": "R. Teodoro Sampaio",
        "address_num": "145",
        "address_compl": "Apto 23",
        "neighborhood": "Campo Grande",
        "city": "Santos",
        "cep": "11070-130",
        "email": "sabrina.fagundes@gmail.com"
    }
]

# ==============================================================================
# PACOTES DE SERVIÇOS E PEÇAS REALISTAS (MECATRONICAR)
# ==============================================================================

PACKAGES = [
    {
        "category": "Revisão Preventiva Básica",
        "complaint": "Revisão periódica programada e troca preventiva de óleo e filtros",
        "scanner_comment": "Scanner KTS: Sem avarias memorizadas na ECU. Parâmetros de injeção e sonda dentro dos limites nominais.",
        "servicos": [
            {"desc": "Troca de óleo de motor e filtros (Item 14.01)", "qty": 1, "unit_price": 80.00},
            {"desc": "Checklist preventivo e inspeção de 30 itens de segurança", "qty": 1, "unit_price": 60.00}
        ],
        "pecas": [
            {"desc": "Óleo Sintético 5W30 API SP (Litro)", "qty": 4, "unit_price": 54.00, "color": None, "comment": "Castrol Magnatec"},
            {"desc": "Filtro de óleo lubrificante do motor (Mann Filter)", "qty": 1, "unit_price": 48.00, "color": None, "comment": ""},
            {"desc": "Filtro de ar do motor (Tecfil)", "qty": 1, "unit_price": 52.00, "color": None, "comment": ""},
            {"desc": "Filtro de combustível (Mahle)", "qty": 1, "unit_price": 42.00, "color": None, "comment": ""},
            {"desc": "Anel de vedação do bujão do cárter", "qty": 1, "unit_price": 8.00, "color": None, "comment": ""}
        ],
        "discount": 10.00
    },
    {
        "category": "Sistema de Freios",
        "complaint": "Pedal de freio vibrando em frenagens rodoviárias e ruído metálico nas rodas dianteiras",
        "scanner_comment": "Inspeção técnica: Discos com empenamento de 0.08mm e pastilhas com menos de 2mm de massa residual.",
        "servicos": [
            {"desc": "Substituição de pastilhas e discos de freio dianteiros", "qty": 1, "unit_price": 180.00},
            {"desc": "Sangria computadorizada e troca completa do fluido de freio", "qty": 1, "unit_price": 110.00}
        ],
        "pecas": [
            {"desc": "Jogo de pastilhas de freio dianteiras (Cobreq)", "qty": 1, "unit_price": 230.00, "color": "#FEF08A", "comment": "Cobreq Cerâmica"},
            {"desc": "Par de discos de freio dianteiros ventilados (Fremax)", "qty": 1, "unit_price": 440.00, "color": None, "comment": ""},
            {"desc": "Fluido de freio sintético DOT 4 (Varga 500ml)", "qty": 2, "unit_price": 38.00, "color": None, "comment": ""},
            {"desc": "Spray desengraxante e limpa freios", "qty": 1, "unit_price": 32.00, "color": None, "comment": ""}
        ],
        "discount": 30.00
    },
    {
        "category": "Suspensão Dianteira",
        "complaint": "Batidas secas na suspensão dianteira ao trafegar em paralelepípedos e lombadas",
        "scanner_comment": "Elevador automotivo: Buchas da bandeja dianteira estouradas e amortecedores com vazamento de óleo.",
        "servicos": [
            {"desc": "Substituição de amortecedores dianteiros e batentes", "qty": 1, "unit_price": 280.00},
            {"desc": "Substituição de bandejas dianteiras e bieletas", "qty": 1, "unit_price": 160.00},
            {"desc": "Alinhamento computadorizado 3D e balanceamento de 4 rodas", "qty": 1, "unit_price": 130.00}
        ],
        "pecas": [
            {"desc": "Par de amortecedores dianteiros pressurizados (Cofap Turbogás)", "qty": 1, "unit_price": 820.00, "color": "#FEF08A", "comment": "Garantia 2 anos Cofap"},
            {"desc": "Kit de batente, coifa e rolamento dianteiro (Sampel)", "qty": 2, "unit_price": 95.00, "color": None, "comment": ""},
            {"desc": "Par de bieletas da barra estabilizadora (Nakata)", "qty": 1, "unit_price": 140.00, "color": None, "comment": ""},
            {"desc": "Bandeja de suspensão dianteira completa c/ buchas (Par)", "qty": 1, "unit_price": 490.00, "color": None, "comment": ""}
        ],
        "discount": 50.00
    },
    {
        "category": "Arrefecimento do Motor",
        "complaint": "Ponteiro de temperatura oscilando e nível do reservatório de água baixando semanalmente",
        "scanner_comment": "Teste de estanqueidade sob pressão (1.5 bar): Identificado vazamento pela carcaça plástica da válvula termostática.",
        "servicos": [
            {"desc": "Limpeza química do radiador e sangria do sistema de arrefecimento", "qty": 1, "unit_price": 140.00},
            {"desc": "Substituição da válvula termostática e carcaça de alumínio", "qty": 1, "unit_price": 150.00}
        ],
        "pecas": [
            {"desc": "Aditivo concentrado orgânico para radiador (Paraflu 1L)", "qty": 2, "unit_price": 46.00, "color": None, "comment": ""},
            {"desc": "Água desmineralizada para arrefecimento (Galão 1L)", "qty": 3, "unit_price": 12.00, "color": None, "comment": ""},
            {"desc": "Válvula termostática com sensor e carcaça de alumínio (Wahler)", "qty": 1, "unit_price": 260.00, "color": "#FEF08A", "comment": "Upgrade carcaça alumínio"},
            {"desc": "Jogo de abraçadeiras de pressão para mangueiras", "qty": 4, "unit_price": 8.00, "color": None, "comment": ""}
        ],
        "discount": 20.00
    },
    {
        "category": "Correia Dentada e Sincronismo",
        "complaint": "Revisão preventiva de 60.000 km para substituição do sincronismo do motor",
        "scanner_comment": "Inspeção visual: Correia dentada original com início de ressecamento e microfissuras no dorso.",
        "servicos": [
            {"desc": "Substituição do kit de correia dentada, tensor e bomba d'água", "qty": 1, "unit_price": 390.00},
            {"desc": "Substituição da correia de acessórios Poli-V do alternador", "qty": 1, "unit_price": 90.00}
        ],
        "pecas": [
            {"desc": "Kit correia dentada e tensor automático (Gates PowerGrip)", "qty": 1, "unit_price": 420.00, "color": "#FEF08A", "comment": "Kit oficial Gates"},
            {"desc": "Bomba d'água do motor (Urba)", "qty": 1, "unit_price": 235.00, "color": None, "comment": ""},
            {"desc": "Correia de acessórios Poli-V (Gates)", "qty": 1, "unit_price": 82.00, "color": None, "comment": ""},
            {"desc": "Retentor dianteiro da árvore de manivelas (Sabó)", "qty": 1, "unit_price": 45.00, "color": None, "comment": ""}
        ],
        "discount": 40.00
    },
    {
        "category": "Injeção Eletrônica e Ignição",
        "complaint": "Luz de injeção acesa no painel, motor engasgando e falhando na retomada de velocidade",
        "scanner_comment": "Scanner Bosch: DTC P0300 e P0302 detectados (falha de combustão cil. 2). Velas com eletrodo desgastado e bico com vazão 18% abaixo.",
        "servicos": [
            {"desc": "Diagnóstico eletrônico avançado com scanner automotivo KTS", "qty": 1, "unit_price": 120.00},
            {"desc": "Limpeza, teste de estanqueidade e equalização de bicos injetores", "qty": 1, "unit_price": 180.00},
            {"desc": "Descarbonização química do corpo de borboleta (TBI) e ajuste básico", "qty": 1, "unit_price": 110.00}
        ],
        "pecas": [
            {"desc": "Jogo com 4 velas de ignição Iridium Laser (NGK)", "qty": 1, "unit_price": 280.00, "color": "#FEF08A", "comment": "NGK Iridium Japão"},
            {"desc": "Jogo de cabos de vela resistivos de silicone (Bosch)", "qty": 1, "unit_price": 155.00, "color": None, "comment": ""},
            {"desc": "Kit de filtros e anéis o-ring dos bicos injetores", "qty": 1, "unit_price": 50.00, "color": None, "comment": ""},
            {"desc": "Spray descarbonizante para coletores e TBI (Koube)", "qty": 1, "unit_price": 38.00, "color": None, "comment": ""}
        ],
        "discount": 25.00
    },
    {
        "category": "Ar-Condicionado e Climatização",
        "complaint": "Ar-condicionado com refrigeração deficiente nos dias quentes e cheiro de mofo ao ligar",
        "scanner_comment": "Manômetro de refrigeração: Pressão na linha de baixa em 18 PSI (carga baixa). Filtro de cabine saturado de fuligem.",
        "servicos": [
            {"desc": "Manutenção, evacuação com bomba de vácuo e recarga de gás R134a", "qty": 1, "unit_price": 190.00},
            {"desc": "Higienização antibacteriana do evaporador com gerador de ozônio", "qty": 1, "unit_price": 90.00}
        ],
        "pecas": [
            {"desc": "Filtro de cabine / ar-condicionado com carvão ativado (Tecfil)", "qty": 1, "unit_price": 72.00, "color": None, "comment": "Antialérgico com carvão"},
            {"desc": "Carga de gás refrigerante R134a automotivo (500g)", "qty": 1, "unit_price": 135.00, "color": None, "comment": ""},
            {"desc": "Contraste fluorescente UV e óleo lubrificante PAG 46", "qty": 1, "unit_price": 45.00, "color": None, "comment": ""}
        ],
        "discount": 15.00
    },
    {
        "category": "Embreagem e Transmissão",
        "complaint": "Pedal de embreagem excessivamente pesado e patinando em subidas íngremes",
        "scanner_comment": "Teste mecânico: Disco de embreagem nos rebites e platô com espelho superaquecido com manchas azuis.",
        "servicos": [
            {"desc": "Substituição do conjunto de embreagem e retífica do volante", "qty": 1, "unit_price": 540.00},
            {"desc": "Sangria e ajuste do atuador hidráulico da embreagem", "qty": 1, "unit_price": 80.00}
        ],
        "pecas": [
            {"desc": "Kit de embreagem completo platô, disco e rolamento (LUK RepSet)", "qty": 1, "unit_price": 720.00, "color": "#FEF08A", "comment": "LUK Original"},
            {"desc": "Atuador hidráulico auxiliar de embreagem (LUK)", "qty": 1, "unit_price": 220.00, "color": None, "comment": ""},
            {"desc": "Óleo sintético de transmissão manual 75W80 (Litro)", "qty": 2, "unit_price": 68.00, "color": None, "comment": ""}
        ],
        "discount": 60.00
    },
    {
        "category": "Vazamento de Óleo e Vedação",
        "complaint": "Gotejamento de óleo no piso da garagem e cheiro de queimado no compartimento do motor",
        "scanner_comment": "Inspeção técnica: Junta da tampa de válvulas ressecada vazando óleo sobre o coletor de escape.",
        "servicos": [
            {"desc": "Substituição da junta da tampa de válvulas e desengraxamento", "qty": 1, "unit_price": 170.00},
            {"desc": "Substituição de coxim limitador de torque do motor", "qty": 1, "unit_price": 140.00}
        ],
        "pecas": [
            {"desc": "Junta da tampa de válvulas de borracha nitrílica (Sabó)", "qty": 1, "unit_price": 105.00, "color": None, "comment": ""},
            {"desc": "Coxim hidráulico do motor lado direito (Sampel)", "qty": 1, "unit_price": 360.00, "color": "#FEF08A", "comment": ""},
            {"desc": "Sensor de oxigênio pré-catalisador Sonda Lambda (NTK)", "qty": 1, "unit_price": 310.00, "color": None, "comment": ""}
        ],
        "discount": 20.00
    }
]

PAYMENT_METHODS = [
    "Cartão de Crédito 3x",
    "Cartão de Crédito 1x",
    "Cartão de Crédito 2x",
    "Pix",
    "Transferência Bancária",
    "Cartão de Débito",
    "Dinheiro",
    "Boleto Bancário 30DD"
]

MECHANICS = [
    "Carlos Mecânico",
    "Marcos Chefe",
    "Roberto Eletricista",
    "André Suspensão",
    "Lucas Diagnóstico"
]

# ==============================================================================
# ESTRUTURAÇÃO DOS VEÍCULOS E VISITAS (~200 PLANILHAS)
# ==============================================================================

# Definição dos veículos da oficina (marca, modelo, cor, placa, combustível, ano, chassi, proprietário inicial)
VEHICLE_CONFIGS = [
    # Carros com muitas visitas (15 a 24 visitas) - Clientes mais fiéis
    {"plate": "BRA 2E19", "brand": "Honda", "model": "Civic 2.0 EXL", "color": "Cinza", "fuel": "Flex", "year": 2019, "chassis": "93HFC2670KZ123456", "owner_idx": 0, "visits_count": 24},
    {"plate": "ABC 3D45", "brand": "Chevrolet", "model": "Onix 1.0 Turbo Premier", "color": "Branco", "fuel": "Flex", "year": 2020, "chassis": "9BGKL48U0LG234567", "owner_idx": 2, "visits_count": 20, "transfer_at": 11, "new_owner_idx": 7},
    {"plate": "KMT 4J88", "brand": "Toyota", "model": "Corolla 2.0 Altis", "color": "Prata", "fuel": "Flex", "year": 2018, "chassis": "9BRBD3HE8J0345678", "owner_idx": 5, "visits_count": 15, "transfer_at": 9, "new_owner_idx": 14},
    {"plate": "RLX 9G12", "brand": "Volkswagen", "model": "T-Cross 1.4 TSI Highline", "color": "Bronze", "fuel": "Flex", "year": 2020, "chassis": "9BWGB4BZ7LP456789", "owner_idx": 9, "visits_count": 14, "transfer_at": 7, "new_owner_idx": 10},
    {"plate": "DFR 7812", "brand": "Fiat", "model": "Strada 1.3 Firefly Volcano", "color": "Vermelho", "fuel": "Flex", "year": 2021, "chassis": "9BD2814AFMY567890", "owner_idx": 13, "visits_count": 12, "transfer_at": 6, "new_owner_idx": 8},
    {"plate": "PAX 3982", "brand": "Jeep", "model": "Compass 1.3 Turbo Limited", "color": "Preto", "fuel": "Flex", "year": 2021, "chassis": "988683A3MNK678901", "owner_idx": 16, "visits_count": 10, "transfer_at": 6, "new_owner_idx": 17},

    # Carros com 6 a 10 visitas
    {"plate": "GHJ 5A67", "brand": "Volkswagen", "model": "Polo 1.0 TSI Comfortline", "color": "Cinza", "fuel": "Flex", "year": 2020, "chassis": "9BWDB4BZ4LP789012", "owner_idx": 1, "visits_count": 10},
    {"plate": "EJW 4410", "brand": "Hyundai", "model": "HB20 1.0 TGDI Evolution", "color": "Branco", "fuel": "Flex", "year": 2019, "chassis": "9BHBG51DAMG890123", "owner_idx": 4, "visits_count": 8},
    {"plate": "KBC 8F23", "brand": "Nissan", "model": "Kicks 1.6 SV CVT", "color": "Cinza", "fuel": "Flex", "year": 2020, "chassis": "3N1CP5CU8LL901234", "owner_idx": 6, "visits_count": 8},
    {"plate": "MNO 7B89", "brand": "Renault", "model": "Duster 1.6 Dynamique", "color": "Marrom", "fuel": "Flex", "year": 2018, "chassis": "93YHR4A07JJ012345", "owner_idx": 11, "visits_count": 7},
    {"plate": "OPQ 1C34", "brand": "Ford", "model": "EcoSport 1.5 Titanium", "color": "Azul", "fuel": "Flex", "year": 2019, "chassis": "9BFAB55A4KB123456", "owner_idx": 12, "visits_count": 7},
    {"plate": "RST 6D56", "brand": "Fiat", "model": "Argo 1.0 Firefly Drive", "color": "Prata", "fuel": "Flex", "year": 2021, "chassis": "9BD358A1FMY234567", "owner_idx": 15, "visits_count": 6},
    {"plate": "UVW 2E78", "brand": "Chevrolet", "model": "Tracker 1.2 Turbo Premier", "color": "Azul", "fuel": "Flex", "year": 2021, "chassis": "9BGKR48T7MC345678", "owner_idx": 18, "visits_count": 6},
    {"plate": "XYZ 9A12", "brand": "Honda", "model": "HR-V 1.5 Turbo Touring", "color": "Preto", "fuel": "Flex", "year": 2020, "chassis": "93HRV2870MZ456789", "owner_idx": 0, "visits_count": 6}, # 2º carro de Carlos Eduardo Silveira

    # Carros com 3 a 5 visitas
    {"plate": "BCB 4C56", "brand": "Jeep", "model": "Renegade 1.3 Turbo Longitude", "color": "Cinza", "fuel": "Flex", "year": 2022, "chassis": "988611A2MNK567890", "owner_idx": 1, "visits_count": 5}, # 2º carro de Juliana Martins Ferreira
    {"plate": "CDE 8D90", "brand": "Volkswagen", "model": "Nivus 1.0 TSI Highline", "color": "Vermelho", "fuel": "Flex", "year": 2021, "chassis": "9BWGB4BZ2MP678901", "owner_idx": 3, "visits_count": 5},
    {"plate": "EFG 2F34", "brand": "Fiat", "model": "Pulse 1.0 Turbo Impetus", "color": "Cinza", "fuel": "Flex", "year": 2022, "chassis": "9BD363A5NMY789012", "owner_idx": 19, "visits_count": 5},
    {"plate": "GHI 6G78", "brand": "Ford", "model": "Ranger 2.2 Diesel XLS 4x4", "color": "Branco", "fuel": "Diesel", "year": 2018, "chassis": "8AFAR35D8JJ890123", "owner_idx": 4, "visits_count": 4}, # 2º carro de Lucas de Souza Mendes
    {"plate": "IJK 0H12", "brand": "Chevrolet", "model": "Cruze 1.4 Turbo LTZ", "color": "Prata", "fuel": "Flex", "year": 2019, "chassis": "8AGBN69Y8KG901234", "owner_idx": 20, "visits_count": 4},
    {"plate": "KLM 4I56", "brand": "Toyota", "model": "Yaris Hatch 1.5 XLS", "color": "Cinza", "fuel": "Flex", "year": 2020, "chassis": "9BRB23FE5L0012345", "owner_idx": 21, "visits_count": 4},
    {"plate": "NOP 8J90", "brand": "Nissan", "model": "Versa 1.6 Exclusive CVT", "color": "Branco", "fuel": "Flex", "year": 2021, "chassis": "3N1CN8EV9ML123456", "owner_idx": 22, "visits_count": 4},
    {"plate": "PQR 2K34", "brand": "Volkswagen", "model": "Virtus 1.0 TSI Highline", "color": "Azul", "fuel": "Flex", "year": 2021, "chassis": "9BWDB4BZ8MP234567", "owner_idx": 6, "visits_count": 3}, # 2º carro de Fernando Henrique Ribeiro
    {"plate": "STU 6L78", "brand": "Hyundai", "model": "Creta 1.0 Turbo Prestige", "color": "Prata", "fuel": "Flex", "year": 2022, "chassis": "9BHBG81DANP345678", "owner_idx": 23, "visits_count": 3},
    {"plate": "VWX 0M12", "brand": "Renault", "model": "Kwid 1.0 SCe Zen", "color": "Laranja", "fuel": "Flex", "year": 2021, "chassis": "93YBB0A02MJ456789", "owner_idx": 24, "visits_count": 3},
    {"plate": "YZA 4N56", "brand": "Fiat", "model": "Toro 1.3 Turbo Volcano", "color": "Vinho", "fuel": "Flex", "year": 2022, "chassis": "9BD226A6MNK567890", "owner_idx": 25, "visits_count": 3},

    # Carros com 2 visitas
    {"plate": "BCD 8P90", "brand": "Volkswagen", "model": "Saveiro 1.6 Cross", "color": "Branco", "fuel": "Flex", "year": 2020, "chassis": "9BWKB4BZ7LP678901", "owner_idx": 26, "visits_count": 2},
    {"plate": "DEF 2Q34", "brand": "Chevrolet", "model": "Spin 1.8 LTZ 7L", "color": "Cinza", "fuel": "Flex", "year": 2019, "chassis": "9BGJB75H3KG789012", "owner_idx": 27, "visits_count": 2},
    {"plate": "FGH 6R78", "brand": "Honda", "model": "Fit 1.5 EXL Flex", "color": "Prata", "fuel": "Flex", "year": 2018, "chassis": "93HGK5870JZ890123", "owner_idx": 28, "visits_count": 2},
    {"plate": "HIJ 0S12", "brand": "Toyota", "model": "Hilux 2.8 TDI SRX 4x4", "color": "Branco", "fuel": "Diesel", "year": 2021, "chassis": "8AJBA3CD7M0901234", "owner_idx": 29, "visits_count": 2},
    {"plate": "JKL 4T56", "brand": "Fiat", "model": "Mobi 1.0 Like", "color": "Vermelho", "fuel": "Flex", "year": 2022, "chassis": "9BD341A1NMY012345", "owner_idx": 11, "visits_count": 2}, # 2º carro de Mariana Costa e Silva

    # Carros novos / 1ª visita (10 carros = 10 planilhas)
    {"plate": "LMN 8U90", "brand": "Volkswagen", "model": "Gol 1.6 MSI Flex", "color": "Prata", "fuel": "Flex", "year": 2022, "chassis": "9BWAB45U9NT123456", "owner_idx": 2, "visits_count": 1},
    {"plate": "NOP 2V34", "brand": "Chevrolet", "model": "Onix Plus 1.0 Turbo LTZ", "color": "Cinza", "fuel": "Flex", "year": 2023, "chassis": "9BGKM48U5PG234567", "owner_idx": 5, "visits_count": 1},
    {"plate": "PQR 6W78", "brand": "Fiat", "model": "Cronos 1.3 Firefly Precision", "color": "Preto", "fuel": "Flex", "year": 2022, "chassis": "9BD359A3NMY345678", "owner_idx": 7, "visits_count": 1},
    {"plate": "RST 0X12", "brand": "Toyota", "model": "Corolla Cross 2.0 XRX", "color": "Branco", "fuel": "Flex", "year": 2023, "chassis": "9BRBE3HEXPP456789", "owner_idx": 8, "visits_count": 1},
    {"plate": "UVW 4Y56", "brand": "Honda", "model": "City 1.5 EXL Sedan", "color": "Azul", "fuel": "Flex", "year": 2023, "chassis": "93HGN2670PZ567890", "owner_idx": 10, "visits_count": 1},
    {"plate": "XYZ 8Z90", "brand": "Hyundai", "model": "HB20S 1.0 TGDI Diamond", "color": "Prata", "fuel": "Flex", "year": 2023, "chassis": "9BHBG61DAPG678901", "owner_idx": 12, "visits_count": 1},
    {"plate": "ZAB 2A34", "brand": "Renault", "model": "Sandero 1.6 Stepway", "color": "Laranja", "fuel": "Flex", "year": 2021, "chassis": "93YBS4A05MJ789012", "owner_idx": 14, "visits_count": 1},
    {"plate": "BCD 6B78", "brand": "Peugeot", "model": "208 1.6 Griffe", "color": "Azul", "fuel": "Flex", "year": 2022, "chassis": "8ADUP5F46N0890123", "owner_idx": 16, "visits_count": 1},
    {"plate": "DEF 0C12", "brand": "Citroën", "model": "C4 Cactus 1.6 Feel", "color": "Branco", "fuel": "Flex", "year": 2022, "chassis": "935P45FK8NL901234", "owner_idx": 18, "visits_count": 1},
    {"plate": "FGH 4D56", "brand": "Ford", "model": "Ka 1.0 SE Flex", "color": "Vermelho", "fuel": "Flex", "year": 2020, "chassis": "9BFB654A2LB012345", "owner_idx": 20, "visits_count": 1}
]

# ==============================================================================
# FUNÇÃO PRINCIPAL DE GERAÇÃO
# ==============================================================================

def generate_mass_data(target_folder=None, db_file=None, target_total=200, seed=42, clean_first=False):
    """
    Gera a massa de dados de planilhas e indexa no banco SQLite.
    """
    random.seed(seed)
    
    out_dir = target_folder or os.path.join(BASE_DIR, "planilhas_exemplo")
    db_path = db_file or cache.get_db_path(BASE_DIR)
    
    os.makedirs(out_dir, exist_ok=True)
    cache.init_db(db_path)
    
    print(f"=== GERADOR DE MASSA DE DADOS MECATRONICAR ===")
    print(f"Diretório de saída: {out_dir}")
    print(f"Banco de cache: {db_path}")
    print(f"Total planejado: {target_total} planilhas")
    print(f"Seed aleatório: {seed}")
    
    # 1. Limpeza se solicitada (preservando os 4 arquivos originais)
    if clean_first:
        print("\nLimpando arquivos gerados anteriormente...")
        removed = 0
        for fname in os.listdir(out_dir):
            if fname in PRESERVED_LEGACY_FILES:
                continue
            if fname.lower().endswith(".xlsx"):
                fpath = os.path.join(out_dir, fname)
                try:
                    os.remove(fpath)
                    removed += 1
                except Exception as e:
                    print(f"Aviso ao remover {fname}: {e}")
        print(f"Removidos {removed} arquivos antigos gerados.")

    # 2. Constrói a lista ordenada de visitas para os veículos
    all_os_tasks = []
    
    base_end_date = datetime.date(2026, 11, 12)
    
    for v_conf in VEHICLE_CONFIGS:
        total_v = v_conf["visits_count"]
        transfer_at = v_conf.get("transfer_at")
        
        # Define datas de visita retroativas
        # A última visita ocorre perto de nov/2026
        # Visitas anteriores espaçadas de 45 a 120 dias
        intervals = [random.randint(45, 110) for _ in range(total_v - 1)]
        total_days_span = sum(intervals)
        
        start_date = base_end_date - datetime.timedelta(days=total_days_span + random.randint(1, 15))
        
        cur_date = start_date
        cur_odo = random.randint(12000, 35000)
        
        for v_num in range(1, total_v + 1):
            if v_num > 1:
                cur_date += datetime.timedelta(days=intervals[v_num - 2])
                cur_odo += random.randint(3500, 11500)
                
            # Determina proprietário (com suporte a transferência/novo dono)
            if transfer_at and v_num >= transfer_at:
                client = CLIENTS_POOL[v_conf["new_owner_idx"]]
                is_transferred = True
                prev_owner_name = CLIENTS_POOL[v_conf["owner_idx"]]["name"]
            else:
                client = CLIENTS_POOL[v_conf["owner_idx"]]
                is_transferred = False
                prev_owner_name = None
                
            all_os_tasks.append({
                "vehicle": v_conf,
                "visit_num": v_num,
                "total_visits": total_v,
                "client": client,
                "is_transferred": is_transferred,
                "prev_owner": prev_owner_name,
                "date": cur_date,
                "odometer": cur_odo
            })

    # Ajusta para bater exatamente target_total se necessário
    if len(all_os_tasks) > target_total:
        all_os_tasks = all_os_tasks[:target_total]
    elif len(all_os_tasks) < target_total:
        diff = target_total - len(all_os_tasks)
        print(f"Ajustando tarefas para atingir exatamente {target_total} (adicionando {diff})...")
        # Duplica com novos veículos fictícios se necessário
        
    print(f"\nGerando {len(all_os_tasks)} ordens de serviço no padrão oficial OpenXML...")
    
    saved_records = []
    start_time = datetime.datetime.now()
    
    for idx, task in enumerate(all_os_tasks, start=1):
        v = task["vehicle"]
        client = task["client"]
        v_num = task["visit_num"]
        entry_dt = task["date"]
        
        # Hora de entrada e saída
        in_hour = random.randint(8, 11)
        in_min = random.choice([0, 15, 30, 45])
        out_hour = random.randint(16, 18)
        out_min = random.choice([0, 15, 30, 45])
        
        days_in_shop = random.choice([0, 0, 1, 1, 2])
        exit_dt = entry_dt + datetime.timedelta(days=days_in_shop)
        
        # Seleciona pacote de serviço compatível
        if v_num == 1:
            pkg = PACKAGES[0] # Revisão Básica
        elif v_num % 5 == 0:
            pkg = PACKAGES[4] # Correia dentada
        elif v_num % 4 == 0:
            pkg = PACKAGES[2] # Suspensão
        elif v_num % 3 == 0:
            pkg = PACKAGES[1] # Freios
        elif v_num % 2 == 0:
            pkg = random.choice([PACKAGES[3], PACKAGES[5], PACKAGES[6]])
        else:
            pkg = random.choice(PACKAGES)
            
        # Comentário de placa se transferência
        plate_comment = ""
        if task["is_transferred"] and v_num == v["transfer_at"]:
            plate_comment = f"Transferência de propriedade: Antigo dono {task['prev_owner']}"
            
        os_payload = {
            "client_name": client["name"],
            "address": client["address"],
            "address_num": client["address_num"],
            "address_compl": client["address_compl"],
            "neighborhood": client["neighborhood"],
            "city": client["city"],
            "cep": client["cep"],
            "phone": client["phone"],
            "tel_res": client["tel_res"],
            "tel_com": "",
            "cpf": client["cpf"],
            "rg": client["rg"],
            "email": client["email"],

            "car_brand": v["brand"],
            "car_model": v["model"],
            "model_comment": f"Motor {v['fuel']} - Ano mod {v['year']}",
            "car_year": v["year"],
            "car_plate": v["plate"],
            "plate_comment": plate_comment,
            "car_color": v["color"],
            "car_fuel": v["fuel"],
            "car_chassis": v["chassis"],

            "visit_num": str(v_num),
            "entry_date": entry_dt.strftime("%d/%m/%Y"),
            "entry_time": f"{in_hour:02d}:{in_min:02d}",
            "exit_date": exit_dt.strftime("%d/%m/%Y"),
            "exit_time": f"{out_hour:02d}:{out_min:02d}",
            "odometer": task["odometer"],
            "complaint": pkg["complaint"],
            "complaint_comment": pkg["scanner_comment"],
            "payment_method": random.choice(PAYMENT_METHODS),
            "pecas_items": [
                {
                    "description": p.get("description") or p.get("desc", ""),
                    "quantity": p.get("quantity") or p.get("qty", 1),
                    "unit_price": p.get("unit_price", 0.0),
                    "color": p.get("color"),
                    "comment": p.get("comment", "")
                }
                for p in pkg["pecas"]
            ],
            "servicos_items": [
                {
                    "description": s.get("description") or s.get("desc", ""),
                    "quantity": s.get("quantity") or s.get("qty", 1),
                    "unit_price": s.get("unit_price", 0.0),
                    "color": s.get("color"),
                    "comment": s.get("comment", "")
                }
                for s in pkg["servicos"]
            ],
            "discount": pkg["discount"]
        }
        
        # Salva via excel_writer oficial
        res = excel_writer.save_os_spreadsheet(
            os_payload,
            folder_path=out_dir,
            auto_index=False,
            db_path=db_path
        )
        
        if res.get("success"):
            saved_records.append({
                "file_path": res["file_path"],
                "file_name": res["file_name"],
                "plate": v["plate"],
                "visit_num": v_num,
                "total_visits": task["total_visits"],
                "is_latest": (v_num == task["total_visits"]),
                "entry_date": entry_dt,
                "client_name": client["name"],
                "car_model": v["model"],
                "car_color": v["color"],
                "car_year": v["year"],
                "odometer": task["odometer"],
                "data": os_payload
            })
            
        if idx % 25 == 0 or idx == len(all_os_tasks):
            elapsed = (datetime.datetime.now() - start_time).total_seconds()
            rate = idx / elapsed if elapsed > 0 else 0
            print(f"  Progresso: {idx}/{len(all_os_tasks)} planilhas criadas ({idx*100//len(all_os_tasks)}%) - {rate:.1f} planilhas/s")

    # 3. Indexa e atualiza o banco de dados oficial oficina_cache.db
    print("\nIndexando todos os arquivos da pasta planilhas_exemplo no SQLite oficina_cache.db...")
    idx_res = cache.scan_and_index_folder(out_dir, db_path)
    print(f"Resultado do scan: {idx_res['indexed']} arquivos indexados de um total de {idx_res['total']}.")
    
    # 4. Enriquece o cache com dados completos (data_json) e popula status de pátio e notas fiscais
    print("\nEnriquecendo dados analíticos, status de pátio (7 status) e Copiloto Fiscal...")
    
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Atualiza as linhas recém-geradas com o JSON completo
    for rec in saved_records:
        fp = rec["file_path"]
        d = rec["data"]
        p_clean = parser.clean_plate(rec["plate"])
        p_disp = parser.format_plate_display(rec["plate"])
        c_clean = parser.remove_accents(rec["client_name"]).lower()
        d_sort = rec["entry_date"].strftime("%Y-%m-%d")
        
        # Constrói o parsed compatível com o parser
        v_s = sum(float(s.get("qty", 1)) * float(s.get("unit_price", 0.0)) for s in d["servicos_items"])
        v_p = sum(float(p.get("qty", 1)) * float(p.get("unit_price", 0.0)) for p in d["pecas_items"])
        disc = float(d.get("discount", 0.0))
        tot = (v_s + v_p) - disc

        norm_pecas = []
        for r_idx, p in enumerate(d["pecas_items"], start=30):
            p_desc = p.get("desc") or p.get("description", "")
            p_qty = p.get("qty") or p.get("quantity", 1)
            p_unit = float(p.get("unit_price", 0.0))
            p_tot = float(p_qty) * p_unit
            norm_pecas.append({
                "section": "Peça",
                "row_index": r_idx,
                "description": p_desc,
                "quantity": str(p_qty) if p_qty else "",
                "unit_price": f"R$ {p_unit:.2f}".replace(".", ","),
                "total_price": f"R$ {p_tot:.2f}".replace(".", ","),
                "color": p.get("color"),
                "text_color": "#1e293b",
                "comment": p.get("comment", "")
            })

        norm_servicos = []
        for r_idx, s in enumerate(d["servicos_items"], start=47):
            s_desc = s.get("desc") or s.get("description", "")
            s_qty = s.get("qty") or s.get("quantity", 1)
            s_unit = float(s.get("unit_price", 0.0))
            s_tot = float(s_qty) * s_unit
            norm_servicos.append({
                "section": "Serviço",
                "row_index": r_idx,
                "description": s_desc,
                "quantity": str(s_qty) if s_qty else "",
                "unit_price": f"R$ {s_unit:.2f}".replace(".", ","),
                "total_price": f"R$ {s_tot:.2f}".replace(".", ","),
                "color": s.get("color"),
                "text_color": "#1e293b",
                "comment": s.get("comment", "")
            })
        
        parsed_dict = {
            "file_path": fp,
            "file_name": rec["file_name"],
            "plate": rec["plate"],
            "plate_clean": p_clean,
            "plate_display": p_disp,
            "client_name": rec["client_name"],
            "client_clean": c_clean,
            "phone": d["phone"],
            "tel_res": d["tel_res"],
            "cpf": d["cpf"],
            "rg": d["rg"],
            "email": d["email"],
            "address": d["address"],
            "address_num": d["address_num"],
            "address_compl": d["address_compl"],
            "neighborhood": d["neighborhood"],
            "city": d["city"],
            "cep": d["cep"],
            "car_brand": d["car_brand"],
            "car_model": d["car_model"],
            "car_year": str(d["car_year"]),
            "car_plate": d["car_plate"],
            "car_color": d["car_color"],
            "car_fuel": d["car_fuel"],
            "car_chassis": d["car_chassis"],
            "visit_num": str(rec["visit_num"]),
            "entry_date": d["entry_date"],
            "entry_time": d["entry_time"],
            "exit_date": d["exit_date"],
            "exit_time": d["exit_time"],
            "odometer": str(rec["odometer"]),
            "complaint": d["complaint"],
            "payment_method": d["payment_method"],
            "pecas_items": norm_pecas,
            "servicos_items": norm_servicos,
            "total_pecas": f"R$ {v_p:.2f}".replace(".", ","),
            "total_servicos": f"R$ {v_s:.2f}".replace(".", ","),
            "subtotal": f"R$ {(v_s + v_p):.2f}".replace(".", ","),
            "discount": f"R$ {disc:.2f}".replace(".", ","),
            "total": f"R$ {tot:.2f}".replace(".", ","),
            "parser_version": parser.PARSER_VERSION
        }
        
        data_json = json.dumps(parsed_dict, ensure_ascii=False)
        cur.execute("""
        UPDATE files SET
            plate = ?, plate_clean = ?, plate_display = ?,
            client_name = ?, client_clean = ?,
            car_model = ?, car_year = ?, car_color = ?, visit_num = ?,
            entry_date = ?, entry_date_sort = ?, odometer = ?, odometer_int = ?,
            complaint = ?, data_json = ?
        WHERE file_path = ?
        """, (
            rec["plate"], p_clean, p_disp,
            rec["client_name"], c_clean,
            rec["car_model"], str(rec["car_year"]), rec["car_color"], str(rec["visit_num"]),
            d["entry_date"], d_sort, str(rec["odometer"]), rec["odometer"],
            d["complaint"], data_json, fp
        ))
        
    conn.commit()
    conn.close()

    # 5. Configuração dos 7 status do Pátio para os veículos mais recentes
    # Identifica os veículos mais recentes (is_latest=True com data recente)
    latest_records = [r for r in saved_records if r["is_latest"]]
    latest_records.sort(key=lambda x: x["entry_date"], reverse=True)
    
    # Distribuição entre os 7 status de pátio
    statuses_to_assign = [
        ("Em Diagnostico", "Carlos Mecânico", None, None, "Aguardando teste de rodagem e leitura de sensores"),
        ("Em Diagnostico", "Lucas Diagnóstico", None, None, "Passando scanner automotivo KTS 590"),
        ("Esperando Orcamento", "Marcos Chefe", None, None, "Cotação de peças enviada para autopeças"),
        ("Esperando Orcamento", "Carlos Mecânico", None, None, "Desmontando para conferir espessura de discos"),
        ("Esperando Aprovacao", "Marcos Chefe", None, None, "Orçamento enviado no WhatsApp do cliente"),
        ("Esperando Aprovacao", "André Suspensão", None, None, "Aguardando retorno sobre amortecedores"),
        ("Esperando Pecas", "André Suspensão", None, None, "Bandejas e bieletas Nakata com previsão de entrega hoje"),
        ("Esperando Pecas", "Roberto Eletricista", None, None, "Aguardando chegada do jogo de velas Iridium"),
        ("Em Execucao", "Carlos Mecânico", None, None, "Troca de correia dentada e bomba d'água em andamento"),
        ("Em Execucao", "Roberto Eletricista", None, None, "Limpeza de bicos e descarbonização de TBI"),
        ("Esperando Cliente", "Marcos Chefe", None, None, "Serviço concluído com sucesso. Carro lavado e pronto."),
        ("Esperando Cliente", "Carlos Mecânico", None, None, "Aguardando cliente vir retirar no final da tarde"),
        ("Liberado Terceiro", "Marcos Chefe", "João da Silva Guinchos", "28.910.456-7", "Autorizado pelo proprietário a retirar pelo guincho"),
        ("Liberado Terceiro", "Carlos Mecânico", "Auto Socorro Litoral", "33.456.789-0", "Guincho acionado pela seguradora Porto Seguro")
    ]
    
    for i, st_info in enumerate(statuses_to_assign):
        if i < len(latest_records):
            r = latest_records[i]
            st_name, mech, tp_name, tp_doc, notes = st_info
            cache.update_patio_status(
                file_path=r["file_path"],
                plate=r["plate"],
                status=st_name,
                mechanic_name=mech,
                third_party_name=tp_name,
                third_party_doc=tp_doc,
                notes=notes,
                db_path=db_path
            )

    # 6. Configuração dos registros fiscais (Copiloto Fiscal)
    print("Populando base fiscal de NFS-e (Santos) e NF-e 55 (Peças)...")
    nf_counter = 1000
    for idx, r in enumerate(saved_records):
        nf_counter += 1
        d = r["data"]
        p_clean = parser.clean_plate(r["plate"])
        v_s = sum(float(s.get("qty", 1)) * float(s.get("unit_price", 0.0)) for s in d["servicos_items"])
        v_p = sum(float(p.get("qty", 1)) * float(p.get("unit_price", 0.0)) for p in d["pecas_items"])
        
        # Visitas mais antigas já foram emitidas
        if r["entry_date"] < datetime.date(2026, 10, 1):
            st_s = "Emitida"
            num_s = f"2026{nf_counter:06d}"
            dt_s = r["entry_date"].strftime("%d/%m/%Y")
            st_p = "Emitida" if v_p > 0 else "Nao Aplicavel"
            num_p = f"000{nf_counter:05d}" if v_p > 0 else None
            dt_p = r["entry_date"].strftime("%d/%m/%Y") if v_p > 0 else None
        else:
            # Visitas recentes: distribuição entre pendentes e emitidas
            if idx % 3 == 0:
                st_s = "Pendente"
                num_s = None
                dt_s = None
                st_p = "Pendente"
                num_p = None
                dt_p = None
            elif idx % 3 == 1:
                st_s = "Emitida"
                num_s = f"2026{nf_counter:06d}"
                dt_s = r["entry_date"].strftime("%d/%m/%Y")
                st_p = "Pendente"
                num_p = None
                dt_p = None
            else:
                st_s = "Emitida"
                num_s = f"2026{nf_counter:06d}"
                dt_s = r["entry_date"].strftime("%d/%m/%Y")
                st_p = "Emitida"
                num_p = f"000{nf_counter:05d}"
                dt_p = r["entry_date"].strftime("%d/%m/%Y")
                
        cache.update_nf_control(
            file_path=r["file_path"],
            plate_clean=p_clean,
            visit_num=str(r["visit_num"]),
            nfse_status=st_s,
            nfse_number=num_s,
            nfse_date=dt_s,
            nfse_value=v_s,
            nfe_status=st_p,
            nfe_number=num_p,
            nfe_date=dt_p,
            nfe_value=v_p,
            notes=f"OS #{r['visit_num']} - {r['car_model']}",
            db_path=db_path
        )

    # 7. Relatório Final de Estatísticas
    final_stats = cache.get_stats(db_path)
    total_time = (datetime.datetime.now() - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print("GERAÇÃO E INDEXAÇÃO CONCLUÍDAS COM SUCESSO!")
    print(f"Tempo total gasto: {total_time:.2f} segundos")
    print(f"Total de arquivos no cache: {final_stats['total_files']}")
    print(f"Total de veículos distintos: {final_stats['total_cars']}")
    print(f"Total de clientes cadastrados: {final_stats['total_clients']}")
    print(f"Veículos ativos no pátio: {len(cache.list_patio_status(db_path=db_path))}")
    print(f"Registros no controle fiscal: {len(cache.list_nf_control(db_path=db_path))}")
    print("=" * 60)
    
    return {
        "success": True,
        "total_generated": len(saved_records),
        "stats": final_stats
    }

if __name__ == "__main__":
    parser_arg = argparse.ArgumentParser(description="Gerador de Massa de Dados MecatroniCar (Issue #10)")
    parser_arg.add_argument("--output-dir", default=None, help="Pasta para salvar planilhas (default: planilhas_exemplo)")
    parser_arg.add_argument("--db-path", default=None, help="Caminho do banco SQLite (default: oficina_cache.db)")
    parser_arg.add_argument("--total", type=int, default=200, help="Quantidade de planilhas a gerar (default: 200)")
    parser_arg.add_argument("--seed", type=int, default=42, help="Seed para reproducibilidade (default: 42)")
    parser_arg.add_argument("--clean", action="store_true", help="Limpar planilhas geradas anteriormente")
    
    args = parser_arg.parse_args()
    
    generate_mass_data(
        target_folder=args.output_dir,
        db_file=args.db_path,
        target_total=args.total,
        seed=args.seed,
        clean_first=args.clean
    )
