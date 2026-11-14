"""
Testes automatizados para o Copiloto de Notas Fiscais (CP-07) do MecatroniCar.
Verifica:
1. nf_copilot.py: Separação Mão de Obra (Item 14.01 Santos) vs Peças (NF-e 55), sugestão inteligente de NCM/CFOP,
   formatação de discriminação de serviços, dados do tomador e exportação TSV.
2. cache.py: Persistência no SQLite (nf_control), fila de pendências (get_nf_queue) e cálculo de KPIs.
3. server.py: Endpoints HTTP /api/nf/data, /api/nf/queue, /api/nf/pending, /api/nf/status, /api/nf/copilot_text e /api/nf/export_batch.
"""

import os
import unittest
import tempfile
import sqlite3
import json
import shutil

import nf_copilot
import cache
import server


class TestNfCopilotLogic(unittest.TestCase):
    """Testa a lógica de negócios fiscal no nf_copilot.py"""

    def setUp(self):
        self.mock_details = {
            'file_path': 'C:/Oficina/Planilhas/ABC1234_2026-03-15.xlsx',
            'file_name': 'ABC1234_2026-03-15.xlsx',
            'plate': 'ABC1D34',
            'plate_display': 'ABC-1D34',
            'car_model': 'Honda Civic 2.0 LXR',
            'car_year': '2016',
            'entry_date': '15/03/2026',
            'odometer': '85.420 km',
            'visit_num': '3',
            'client_name': 'Carlos Eduardo Silva',
            'phone': '(13) 99876-5432',
            'cpf': '123.456.789-00',
            'address': 'Av. Ana Costa',
            'address_num': '450',
            'address_compl': 'Apto 42',
            'neighborhood': 'Gonzaga',
            'city': 'Santos',
            'cep': '11060-002',
            'total_servicos': 'R$ 200,00',
            'total_pecas': 'R$ 495,00',
            'total': 'R$ 695,00',
            'servicos_items': [
                {'section': 'Serviço', 'description': 'Substituição das Pastilhas de Freio Dianteiras', 'quantity': '1', 'unit_price': 'R$ 120,00', 'total_price': 'R$ 120,00'},
                {'section': 'Serviço', 'description': 'Troca de Óleo e Filtro', 'quantity': '1', 'unit_price': 'R$ 80,00', 'total_price': 'R$ 80,00'},
                {'section': 'Serviço', 'description': 'Checkup de 25 itens da suspensão (Cortesia)', 'quantity': '1', 'unit_price': 'R$ 0,00', 'total_price': 'R$ 0,00'}
            ],
            'pecas_items': [
                {'section': 'Peça', 'description': 'Pastilha de Freio Dianteira Cerâmica', 'quantity': '1', 'unit_price': 'R$ 280,00', 'total_price': 'R$ 280,00'},
                {'section': 'Peça', 'description': 'Óleo de Motor 5W30 Sintético', 'quantity': '4', 'unit_price': 'R$ 45,00', 'total_price': 'R$ 180,00'},
                {'section': 'Peça', 'description': 'Filtro de Óleo Blindado', 'quantity': '1', 'unit_price': 'R$ 35,00', 'total_price': 'R$ 35,00'}
            ]
        }

    def test_ncm_suggestions(self):
        """Testa o motor de classificação por palavras-chave de NCM e CFOP."""
        c_pastilha = nf_copilot.suggest_fiscal_classification('Pastilha de freio dianteira')
        self.assertEqual(c_pastilha['ncm'], '8708.30.90')
        self.assertEqual(c_pastilha['cfop'], '5.405')

        c_filtro_oleo = nf_copilot.suggest_fiscal_classification('Filtro de oleo motor blindado')
        self.assertEqual(c_filtro_oleo['ncm'], '8421.23.00')

        c_filtro_ar = nf_copilot.suggest_fiscal_classification('Filtro de ar do motor')
        self.assertEqual(c_filtro_ar['ncm'], '8421.31.00')

        c_oleo = nf_copilot.suggest_fiscal_classification('Oleo sintetico 5w30')
        self.assertEqual(c_oleo['ncm'], '2710.19.32')

        c_vela = nf_copilot.suggest_fiscal_classification('Vela de ignicao iridio')
        self.assertEqual(c_vela['ncm'], '8511.10.00')

        c_amort = nf_copilot.suggest_fiscal_classification('Amortecedor dianteiro pressurizado')
        self.assertEqual(c_amort['ncm'], '8708.80.00')

        c_gen = nf_copilot.suggest_fiscal_classification('Peca desconhecida generica')
        self.assertEqual(c_gen['ncm'], '8708.29.99')

    def test_format_tomador_data(self):
        """Testa a extração e formatação dos dados cadastrais do tomador."""
        tomador = nf_copilot.format_tomador_data(self.mock_details)
        self.assertEqual(tomador['name'], 'Carlos Eduardo Silva')
        self.assertEqual(tomador['cpf'], '123.456.789-00')
        self.assertEqual(tomador['cpf_raw'], '12345678900')
        self.assertEqual(tomador['city'], 'Santos')
        self.assertEqual(tomador['uf'], 'SP')
        self.assertEqual(tomador['cep'], '11060-002')
        self.assertEqual(tomador['cep_raw'], '11060002')
        self.assertIn('Av. Ana Costa, 450', tomador['address_single_line'])
        self.assertIn('Gonzaga', tomador['address_single_line'])

    def test_format_nfse_discriminacao(self):
        """Testa a formatação da discriminação de serviços da NFS-e Santos."""
        texto = nf_copilot.format_nfse_discriminacao(self.mock_details)

        self.assertIn("ITEM 14.01", texto)
        self.assertIn("4520-0/01", texto)
        self.assertIn("ABC-1D34", texto)
        self.assertIn("Honda Civic", texto)
        self.assertIn("85.420 km", texto)
        self.assertIn("Substituição das Pastilhas", texto)
        self.assertIn("Troca de Óleo e Filtro", texto)
        self.assertIn("Cortesia", texto)
        self.assertIn("R$ 200,00", texto)
        self.assertIn("Mecatroni Car", texto)
        self.assertIn("05.961.672/0001-87", texto)

    def test_format_nfe_pecas_text_and_tsv(self):
        """Testa a formatação de resumo e TSV das peças da NF-e 55."""
        texto = nf_copilot.format_nfe_pecas_text(self.mock_details)
        self.assertIn("NF-e MODELO 55", texto)
        self.assertIn("5.405", texto)
        self.assertIn("Pastilha de Freio Dianteira", texto)
        self.assertIn("R$ 495,00", texto)

        tsv = nf_copilot.format_nfe_pecas_tsv(self.mock_details)
        lines = tsv.strip().split('\n')
        self.assertGreaterEqual(len(lines), 4)
        header = lines[0].split('\t')
        self.assertIn('Descrição da Peça', header)
        self.assertIn('CFOP Sugerido', header)
        self.assertIn('NCM Sugerido', header)

    def test_build_copilot_payload(self):
        """Testa a montagem completa da carga do Copiloto."""
        payload = nf_copilot.build_copilot_payload(
            self.mock_details['file_path'],
            self.mock_details,
            nf_status={'nf_servico_num': '1042', 'status_servico': 'emitida'}
        )
        self.assertIn('copilot_texts', payload)
        self.assertIn('tomador', payload)
        self.assertIn('servicos_items', payload)
        self.assertIn('pecas_items', payload)
        self.assertEqual(payload['total_servicos'], 'R$ 200,00')
        self.assertEqual(payload['total_pecas'], 'R$ 495,00')
        self.assertEqual(payload['total_geral'], 'R$ 695,00')
        self.assertEqual(len(payload['pecas_items']), 3)
        self.assertEqual(len(payload['servicos_items']), 3)
        self.assertEqual(payload['nf_status']['nfse_status'], 'pendente')


class TestNfCachePersistence(unittest.TestCase):
    """Testa o armazenamento no banco SQLite e consultas da fila de notas."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, cache.DB_FILE)
        cache.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_nf_queue(self):
        """Testa o salvamento de status fiscal e a consulta da fila com KPIs."""
        rec = cache.save_nf_control(
            file_path='C:/Planilhas/XYZ9999.xlsx',
            plate='XYZ-9999',
            visit_num=1,
            client_name='Maria Santos',
            car_model='Toyota Corolla',
            entry_date='10/03/2026',
            status_servico='pendente',
            valor_servico=350.0,
            status_pecas='pendente',
            valor_pecas=600.0,
            db_path=self.db_path
        )
        self.assertIsNotNone(rec)
        self.assertEqual(rec['plate_display'], 'XYZ-9999')
        self.assertEqual(rec['plate_clean'], 'XYZ9999')

        # Consulta fila 'pending'
        queue_data = cache.get_nf_queue(filter_type='pending', db_path=self.db_path)
        self.assertEqual(len(queue_data['items']), 1)
        self.assertEqual(queue_data['stats']['pending_visits_count'], 1)
        self.assertEqual(queue_data['stats']['total_pending_services_val'], 350.0)
        self.assertEqual(queue_data['stats']['total_pending_pecas_val'], 600.0)

        # Marca serviço como emitido
        cache.save_nf_control(
            file_path='C:/Planilhas/XYZ9999.xlsx',
            plate='XYZ-9999',
            status_servico='emitida',
            nf_servico_num='1042',
            data_emissao_servico='11/03/2026',
            db_path=self.db_path
        )

        # Consulta fila 'pending_pecas'
        queue_pecas = cache.get_nf_queue(filter_type='pending_pecas', db_path=self.db_path)
        self.assertEqual(len(queue_pecas['items']), 1)
        self.assertEqual(queue_pecas['items'][0]['status_servico'], 'emitida')
        self.assertEqual(queue_pecas['items'][0]['status_pecas'], 'pendente')

        # Marca peças como emitida
        cache.save_nf_control(
            file_path='C:/Planilhas/XYZ9999.xlsx',
            plate='XYZ-9999',
            status_pecas='emitida',
            nf_pecas_num='5501',
            db_path=self.db_path
        )

        # Fila pending agora deve estar vazia (0 pendências)
        queue_pending_now = cache.get_nf_queue(filter_type='pending', db_path=self.db_path)
        self.assertEqual(len(queue_pending_now['items']), 0)
        self.assertEqual(queue_pending_now['stats']['emitted_count'], 1)


class TestNfServerEndpoints(unittest.TestCase):
    """Testa as rotas da API Flask do servidor MecatroniCar."""

    def setUp(self):
        server.app.testing = True
        self.client = server.app.test_client()

    def test_api_nf_endpoints(self):
        """Testa o fluxo completo da API /api/nf/..."""
        # 1. Salva status inicial de uma visita
        resp_status = self.client.post('/api/nf/status', json={
            'file_path': 'C:/Oficina/BRA2E19_TEST.xlsx',
            'plate': 'BRA-2E19',
            'client_name': 'Roberto Almeida',
            'car_model': 'VW Golf 1.4 TSI',
            'entry_date': '01/04/2026',
            'visit_num': 2,
            'valor_servico': 400.0,
            'valor_pecas': 750.0,
            'status_servico': 'pendente',
            'status_pecas': 'pendente'
        })
        self.assertEqual(resp_status.status_code, 200)
        data = resp_status.get_json()
        self.assertTrue(data['success'])

        # 2. GET /api/nf/pending
        resp_pending = self.client.get('/api/nf/pending')
        self.assertEqual(resp_pending.status_code, 200)
        pdata = resp_pending.get_json()
        self.assertTrue(pdata['success'])
        self.assertIn('stats', pdata)

        # 3. GET /api/nf/data?plate=BRA-2E19
        resp_data = self.client.get('/api/nf/data?plate=BRA-2E19')
        self.assertEqual(resp_data.status_code, 200)
        ddata = resp_data.get_json()
        self.assertTrue(ddata['success'])
        self.assertIn('nfse', ddata)
        self.assertIn('nfe', ddata)
        self.assertIn('tomador', ddata)

        # 4. GET /api/nf/copilot_text?type=nfse_discriminacao&plate=BRA-2E19
        resp_text = self.client.get('/api/nf/copilot_text?type=nfse_discriminacao&plate=BRA-2E19')
        self.assertEqual(resp_text.status_code, 200)
        tdata = resp_text.get_json()
        self.assertTrue(tdata['success'])
        self.assertIn('14.01', tdata['text'])

        # 5. Emite NFS-e via POST /api/nf/status
        resp_emit = self.client.post('/api/nf/status', json={
            'file_path': 'C:/Oficina/BRA2E19_TEST.xlsx',
            'plate': 'BRA-2E19',
            'status_servico': 'emitida',
            'nf_servico_num': '9988'
        })
        self.assertEqual(resp_emit.status_code, 200)
        edata = resp_emit.get_json()
        rec = edata.get('nf') or edata.get('record')
        self.assertEqual(rec['nf_servico_num'], '9988')

        # 6. GET /api/nf/export_batch?format=csv
        resp_csv = self.client.get('/api/nf/export_batch?format=csv&filter=all')
        self.assertEqual(resp_csv.status_code, 200)
        self.assertIn('text/csv', resp_csv.content_type)
        self.assertIn('BRA-2E19', resp_csv.get_data(as_text=True))

        # 7. GET /api/nf/export_batch?format=txt
        resp_txt = self.client.get('/api/nf/export_batch?format=txt&filter=all')
        self.assertEqual(resp_txt.status_code, 200)
        self.assertIn('text/plain', resp_txt.content_type)
        self.assertIn('FILA DE NOTAS FISCAIS', resp_txt.get_data(as_text=True))


if __name__ == '__main__':
    unittest.main()
