# -*- coding: utf-8 -*-
"""
test_excel_writer.py
Testes unitários e de integração para o módulo excel_writer.py (CP-02 / Issue #2).
Valida:
1. Geração canônica de nome de arquivo (PLACA - Nº_VISITA - Nome Cliente - Modelo - Cor.xlsx)
2. Cálculo automático do número da próxima visita (Visita N + 1)
3. Auto-recuperação de dados cadastrais de clientes recorrentes
4. Criação de planilha .xlsx respeitando o layout legado A1:I54, 45 mesclagens e fórmulas
5. Validação de leitura perfeita via parser.py (valores, textos, datas, comentários, totais)
6. Atualização de planilha existente preservando abas secundárias
7. Integração com o índice de cache SQLite
"""

import os
import shutil
import tempfile
import unittest
import openpyxl

import excel_writer
import parser
import cache

class TestExcelWriter(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mecatroni_test_")
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        cache.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_filename_generation_and_sanitization(self):
        """Testa geração de nome de arquivo padronizado e limpeza de caracteres proibidos."""
        # Placa Mercosul contígua
        fn1 = excel_writer.generate_filename("FNB1A77", 8, "Danilo Pereira", "VW Fox", "Prata")
        self.assertEqual(fn1, "FNB 1A77 - 8 - Danilo Pereira - VW Fox - Prata.xlsx")
        
        # Placa com caracteres especiais no nome do cliente e modelo
        fn2 = excel_writer.generate_filename("abc1234", "3", "João da Silva / Filhos <Ltda>", "Gol 1.0 : Flex *", "Preto?")
        self.assertEqual(fn2, "ABC 1234 - 3 - João da Silva Filhos Ltda - Gol 1.0 Flex - Preto.xlsx")
        
        # Placa já espaçada
        fn3 = excel_writer.generate_filename("DTZ 9080", 36, "Natanael", "Partner", "Branco")
        self.assertEqual(fn3, "DTZ 9080 - 36 - Natanael - Partner - Branco.xlsx")

    def test_02_next_visit_number_calculation(self):
        """Testa o cálculo automático da próxima visita (Visita N + 1)."""
        # Para carro desconhecido, deve retornar 1
        v_new = excel_writer.get_next_visit_number("XYZ9999", folder_path=self.test_dir, db_path=self.db_path)
        self.assertEqual(v_new, 1)

        # Usando a pasta de exemplos existente onde FNB 1A77 tem visita 7
        samples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "planilhas_exemplo")
        v_next = excel_writer.get_next_visit_number("FNB1A77", folder_path=samples_dir)
        self.assertEqual(v_next, 8)

    def test_03_create_new_os_spreadsheet_and_validate_with_parser(self):
        """
        Cria uma planilha completa do zero com todos os campos legados,
        fórmulas =G*H, =SUM, comentários e valida que parser.py lê tudo com perfeição.
        """
        os_data = {
            "client_name": "Mariana Souza Oliveira",
            "address": "Av. Ana Costa",
            "address_num": 450,
            "address_compl": "Apto 82",
            "neighborhood": "Gonzaga",
            "city": "Santos",
            "cep": "11060-002",
            "phone": "13 99123-4567",
            "tel_res": "13 3222-1111",
            "tel_com": "",
            "cpf": "123.456.789-00",
            "rg": "12.345.678-9",
            "email": "mariana.souza@exemplo.com",

            "car_brand": "Honda",
            "car_model": "Civic 2.0 EXL",
            "model_comment": "Câmbio CVT / G10",
            "car_year": 2019,
            "car_plate": "BRA 2E19",
            "plate_comment": "Placa Mercosul nova",
            "car_color": "Cinza",
            "car_fuel": "Flex",
            "car_chassis": "93HFC2670KZ123456",

            "visit_num": "1",
            "entry_date": "12/11/2026",
            "entry_time": "08:30",
            "exit_date": "12/11/2026",
            "exit_time": "17:45",
            "odometer": 65400,
            "complaint": "Barulho na suspensão dianteira ao passar em lombadas",
            "complaint_comment": "Scanner CodeScan: Sem códigos de falha na injeção. Buchas da bandeja dianteira rompidas.",
            "payment_method": "Cartão de Crédito 3x",

            "pecas_items": [
                {
                    "description": "Bandeja dianteira direita c/ buchas (Nakata)",
                    "quantity": 1,
                    "unit_price": 420.00,
                    "color": "#FEF08A",
                    "comment": "Comprada na Autopeças Santos"
                },
                {
                    "description": "Bandeja dianteira esquerda c/ buchas (Nakata)",
                    "quantity": 1,
                    "unit_price": 420.00
                },
                {
                    "description": "Bieleta da barra estabilizadora dianteira",
                    "quantity": 2,
                    "unit_price": 75.00
                }
            ],

            "servicos_items": [
                {
                    "description": "Substituição das bandejas e bieletas dianteiras",
                    "quantity": 1,
                    "unit_price": 280.00
                },
                {
                    "description": "Alinhamento computadorizado 3D e balanceamento",
                    "quantity": 1,
                    "unit_price": 120.00
                }
            ],

            "discount": 40.00
        }

        # Salva a planilha na pasta de testes
        res = excel_writer.save_os_spreadsheet(
            os_data,
            folder_path=self.test_dir,
            auto_index=True,
            db_path=self.db_path
        )

        self.assertTrue(res["success"])
        saved_file = res["file_path"]
        self.assertTrue(os.path.exists(saved_file))
        self.assertEqual(os.path.basename(saved_file), "BRA 2E19 - 1 - Mariana Souza Oliveira - Civic 2.0 EXL - Cinza.xlsx")

        # 1. Validação da estrutura OpenXML bruta (fórmulas e mesclagens)
        wb_raw = openpyxl.load_workbook(saved_file, data_only=False)
        self.assertIn("Plan1", wb_raw.sheetnames)
        ws_raw = wb_raw["Plan1"]

        # Fórmulas de peças e serviços
        self.assertEqual(ws_raw["I30"].value, "=G30*H30")
        self.assertEqual(ws_raw["I31"].value, "=G31*H31")
        self.assertEqual(ws_raw["I32"].value, "=G32*H32")
        self.assertEqual(ws_raw["I44"].value, "=SUM(I30:I43)")
        self.assertEqual(ws_raw["I47"].value, "=G47*H47")
        self.assertEqual(ws_raw["I48"].value, "=G48*H48")
        self.assertEqual(ws_raw["I51"].value, "=SUM(I47:I50)")
        self.assertEqual(ws_raw["G51"].value, "=I44+I51")
        self.assertEqual(ws_raw["G53"].value, "=I44+I51-G52")

        # Verifica 45 mesclagens
        raw_merges = {str(m) for m in ws_raw.merged_cells.ranges}
        for expected_m in excel_writer.MERGED_RANGES:
            self.assertIn(expected_m, raw_merges, f"Mesclagem ausente: {expected_m}")

        # 2. Validação completa via parser.py (como o sistema e a interface web leem)
        parsed = parser.parse_file(saved_file)

        # Metadados do veículo
        self.assertEqual(parsed["plate"], "BRA 2E19")
        self.assertEqual(parsed["visit_num"], "1")
        self.assertEqual(parsed["client_name"], "Mariana Souza Oliveira")
        self.assertEqual(parsed["car_brand"], "Honda")
        self.assertEqual(parsed["car_model"], "Civic 2.0 EXL")
        self.assertEqual(parsed["car_year"], "2019")
        self.assertEqual(parsed["car_color"], "Cinza")
        self.assertEqual(parsed["car_fuel"], "Flex")
        self.assertEqual(parsed["car_chassis"], "93HFC2670KZ123456")

        # Dados do cliente
        self.assertEqual(parsed["address"], "Av. Ana Costa")
        self.assertEqual(parsed["address_num"], "450")
        self.assertEqual(parsed["address_compl"], "Apto 82")
        self.assertEqual(parsed["neighborhood"], "Gonzaga")
        self.assertEqual(parsed["city"], "Santos")
        self.assertEqual(parsed["cep"], "11060-002")
        self.assertEqual(parsed["phone"], "13 99123-4567")
        self.assertEqual(parsed["cpf"], "123.456.789-00")
        self.assertEqual(parsed["rg"], "12.345.678-9")
        self.assertEqual(parsed["email"], "mariana.souza@exemplo.com")

        # Entrada, Saída e Hodômetro
        self.assertEqual(parsed["entry_date"], "12/11/2026")
        self.assertEqual(parsed["entry_time"], "08:30")
        self.assertEqual(parsed["exit_date"], "12/11/2026")
        self.assertEqual(parsed["exit_time"], "17:45")
        self.assertEqual(parsed["odometer"], "65400")
        self.assertEqual(parsed["complaint"], "Barulho na suspensão dianteira ao passar em lombadas")
        self.assertIn("Scanner CodeScan", parsed["complaint_comment"])
        self.assertEqual(parsed["model_comment"], "Câmbio CVT / G10")
        self.assertEqual(parsed["plate_comment"], "Placa Mercosul nova")
        self.assertEqual(parsed["payment_method"], "Cartão de Crédito 3x")

        # Itens de Peças
        self.assertEqual(len(parsed["pecas_items"]), 3)
        self.assertEqual(parsed["pecas_items"][0]["description"], "Bandeja dianteira direita c/ buchas (Nakata)")
        self.assertEqual(parsed["pecas_items"][0]["quantity"], "1")
        self.assertEqual(parsed["pecas_items"][0]["unit_price"], "R$ 420,00")
        self.assertEqual(parsed["pecas_items"][0]["total_price"], "R$ 420,00")
        self.assertEqual(parsed["pecas_items"][0]["color"], "#fef08a")
        self.assertEqual(parsed["pecas_items"][0]["comment"], "Comprada na Autopeças Santos")

        self.assertEqual(parsed["pecas_items"][2]["description"], "Bieleta da barra estabilizadora dianteira")
        self.assertEqual(parsed["pecas_items"][2]["quantity"], "2")
        self.assertEqual(parsed["pecas_items"][2]["unit_price"], "R$ 75,00")
        self.assertEqual(parsed["pecas_items"][2]["total_price"], "R$ 150,00")

        # Itens de Serviços
        self.assertEqual(len(parsed["servicos_items"]), 2)
        self.assertEqual(parsed["servicos_items"][0]["description"], "Substituição das bandejas e bieletas dianteiras")
        self.assertEqual(parsed["servicos_items"][0]["total_price"], "R$ 280,00")
        self.assertEqual(parsed["servicos_items"][1]["description"], "Alinhamento computadorizado 3D e balanceamento")
        self.assertEqual(parsed["servicos_items"][1]["total_price"], "R$ 120,00")

        # Totais Calculados pelas Fórmulas
        # Peças: 420 + 420 + 150 = 990
        self.assertEqual(parsed["total_pecas"], "R$ 990,00")
        # Serviços: 280 + 120 = 400
        self.assertEqual(parsed["total_servicos"], "R$ 400,00")
        # Subtotal: 990 + 400 = 1390
        self.assertEqual(parsed["subtotal"], "R$ 1.390,00")
        # Desconto: 40
        self.assertEqual(parsed["discount"], "R$ 40,00")
        # Total: 1390 - 40 = 1350
        self.assertEqual(parsed["total"], "R$ 1.350,00")

    def test_04_update_existing_spreadsheet(self):
        """Testa atualização de planilha existente preservando abas secundárias e atualizando valores."""
        # 1. Cria planilha inicial
        initial_data = {
            "client_name": "Carlos Eduardo",
            "car_plate": "ABC 1234",
            "car_model": "Corsa",
            "car_color": "Preto",
            "visit_num": "2",
            "odometer": 80000,
            "complaint": "Troca de correia",
            "pecas_items": [
                {"description": "Correia Dentada", "quantity": 1, "unit_price": 60.0}
            ],
            "servicos_items": [
                {"description": "Mão de obra troca correia", "quantity": 1, "unit_price": 150.0}
            ]
        }

        res1 = excel_writer.save_os_spreadsheet(initial_data, folder_path=self.test_dir, auto_index=False)
        target_file = res1["file_path"]

        # 2. Adiciona manualmente uma aba secundária para simular planilhas antigas
        wb = openpyxl.load_workbook(target_file)
        ws_sec = wb.create_sheet("Anotações da Oficina")
        ws_sec["A1"] = "Orçamento aprovado por WhatsApp"
        wb.save(target_file)

        # 3. Atualiza a planilha adicionando nova peça e novo hodômetro
        updated_data = dict(initial_data)
        updated_data["odometer"] = 80150
        updated_data["complaint"] = "Troca de correia e tensor + revisão"
        updated_data["pecas_items"].append({
            "description": "Tensor da correia dentada",
            "quantity": 1,
            "unit_price": 90.0
        })

        res2 = excel_writer.save_os_spreadsheet(updated_data, filepath=target_file, auto_index=False)
        self.assertTrue(res2["success"])

        # 4. Valida que a aba secundária foi preservada e os dados foram atualizados
        wb_check = openpyxl.load_workbook(target_file)
        self.assertIn("Anotações da Oficina", wb_check.sheetnames)
        self.assertEqual(wb_check["Anotações da Oficina"]["A1"].value, "Orçamento aprovado por WhatsApp")

        parsed_updated = parser.parse_file(target_file)
        self.assertEqual(parsed_updated["odometer"], "80150")
        self.assertEqual(len(parsed_updated["pecas_items"]), 2)
        # 60 + 90 = 150 peças
        self.assertEqual(parsed_updated["total_pecas"], "R$ 150,00")
        # 150 serviços
        self.assertEqual(parsed_updated["total_servicos"], "R$ 150,00")
        # Total = 300
        self.assertEqual(parsed_updated["total"], "R$ 300,00")

    def test_05_cache_indexing_and_search_integration(self):
        """Testa se a planilha salva é indexada e encontrada na busca do sistema."""
        os_data = {
            "client_name": "Renata Bastos",
            "car_plate": "RNK 9A99",
            "car_model": "Renegade Longitude",
            "car_color": "Vermelho",
            "visit_num": "1",
            "odometer": 42000,
            "complaint": "Revisão dos 40.000 km",
            "pecas_items": [
                {"description": "Kit filtros Renegade", "quantity": 1, "unit_price": 250.0}
            ]
        }

        res = excel_writer.save_os_spreadsheet(
            os_data,
            folder_path=self.test_dir,
            auto_index=True,
            db_path=self.db_path
        )
        self.assertTrue(res["cached_index_updated"])

        # Busca pelo nome da cliente no banco
        results = cache.search_files("Renata Bastos", self.db_path)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["plate_clean"], "RNK9A99")
        self.assertEqual(results[0]["client_name"], "Renata Bastos")

        # Busca pelo histórico da placa
        history = cache.get_car_history("RNK 9A99", self.db_path)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["visit_num"], "1")

if __name__ == "__main__":
    unittest.main()
