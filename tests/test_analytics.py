# -*- coding: utf-8 -*-
"""
Testes unitários e de integração para a funcionalidade de Analytics e Métricas (Issue #16):
1. Volume de Carros: total atendido e médias por dia, semana e mês.
2. Tempo Médio de Permanência: cálculo em dias da entrada até a saída/entrega.
3. Métricas Financeiras Médias: valor médio de autopeças por OS e mão de obra por visita/serviço.
4. Rota e API REST /api/analytics: filtros por período (30 dias, 90 dias, geral).
5. Casos de borda: banco vazio, valores zerados e ordens sem datas de saída.
"""

import os
import tempfile
import shutil
import sqlite3
import json
import datetime
import unittest

import cache
import server


class TestAnalytics(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="mecatronicar_analytics_")
        cls.db_path = os.path.join(cls.test_dir, "analytics_test.db")
        cache.init_db(cls.db_path)

        server.app.config["TESTING"] = True
        cls.client = server.app.test_client()

    @classmethod
    def tearDownClass(cls):
        try:
            shutil.rmtree(cls.test_dir, ignore_errors=True)
        except Exception:
            pass

    def setUp(self):
        # Limpa as tabelas entre testes
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("DELETE FROM files")
        cur.execute("DELETE FROM nf_control")
        conn.commit()
        conn.close()

    def _insert_test_file(self, plate, client, model, entry_date_str, exit_date_str="",
                           parts_val=0.0, labor_val=0.0, visit_num="1", filename=None):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        ed = cache.parse_any_date(entry_date_str)
        sort_date = ed.strftime("%Y-%m-%d") if ed else "0000-00-00"

        fname = filename or f"{plate} - {visit_num} - {client} - {model}.xlsx"
        fpath = os.path.join(self.test_dir, fname)

        total_val = parts_val + labor_val
        pecas_str = f"R$ {parts_val:.2f}".replace(".", ",") if parts_val > 0 else ""
        serv_str = f"R$ {labor_val:.2f}".replace(".", ",") if labor_val > 0 else ""
        tot_str = f"R$ {total_val:.2f}".replace(".", ",") if total_val > 0 else ""

        pecas_items = [{"description": "Item Peça Teste", "quantity": 1, "unit_price": parts_val, "total_price": pecas_str}] if parts_val > 0 else []
        servicos_items = [{"description": "Item Serviço Teste", "quantity": 1, "unit_price": labor_val, "total_price": serv_str}] if labor_val > 0 else []

        data_json = {
            "plate": plate,
            "plate_clean": cache.clean_plate(plate),
            "client_name": client,
            "car_model": model,
            "visit_num": visit_num,
            "entry_date": entry_date_str,
            "exit_date": exit_date_str,
            "total_pecas": pecas_str,
            "total_servicos": serv_str,
            "total": tot_str,
            "pecas_items": pecas_items,
            "servicos_items": servicos_items
        }

        cur.execute("""
        INSERT INTO files (
            file_path, file_name, file_mtime, file_size,
            plate, plate_clean, plate_display, client_name, client_clean,
            car_model, visit_num, entry_date, entry_date_sort, data_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            fpath, fname, 123456.0, 1024,
            plate, cache.clean_plate(plate), plate, client, client.lower(),
            model, visit_num, entry_date_str, sort_date, json.dumps(data_json)
        ))
        conn.commit()
        conn.close()

    def test_01_empty_database_analytics(self):
        """Valida que banco vazio retorna métricas zeradas sem exceções."""
        data = cache.get_analytics(period="30", db_path=self.db_path)
        self.assertEqual(data["volume"]["total_cars"], 0)
        self.assertEqual(data["volume"]["total_orders"], 0)
        self.assertEqual(data["volume"]["avg_cars_per_day"], 0.0)
        self.assertEqual(data["volume"]["avg_cars_per_week"], 0.0)
        self.assertEqual(data["volume"]["avg_cars_per_month"], 0.0)

        self.assertEqual(data["stay_time"]["avg_stay_days"], 0.0)
        self.assertEqual(data["stay_time"]["stays_measured_count"], 0)

        self.assertEqual(data["financials"]["total_parts"], 0.0)
        self.assertEqual(data["financials"]["total_labor"], 0.0)
        self.assertEqual(data["financials"]["avg_parts_per_order"], 0.0)
        self.assertEqual(data["financials"]["avg_labor_per_order"], 0.0)

    def test_02_car_volume_and_averages(self):
        """Valida total de carros atendidos e cálculo de médias diária, semanal e mensal."""
        ref_date = datetime.date(2026, 11, 10)

        # 3 carros distintos atendidos nos últimos 30 dias
        self._insert_test_file("ABC1234", "Cliente A", "Gol", "05/11/2026", parts_val=200, labor_val=100)
        self._insert_test_file("XYZ9876", "Cliente B", "Fox", "06/11/2026", parts_val=300, labor_val=150)
        self._insert_test_file("BRA2E19", "Cliente C", "Onix", "08/11/2026", parts_val=500, labor_val=250)

        data = cache.get_analytics(period="30", db_path=self.db_path, ref_date=ref_date)
        vol = data["volume"]

        self.assertEqual(vol["total_cars"], 3)
        self.assertEqual(vol["total_orders"], 3)
        # Média diária: 3 / 30 = 0.1
        self.assertEqual(vol["avg_cars_per_day"], 0.1)
        # Média semanal: 3 / (30/7) = 3 / 4.2857 ~ 0.70
        self.assertAlmostEqual(vol["avg_cars_per_week"], 0.7, places=1)
        # Média mensal: 3 / 1 = 3.0
        self.assertEqual(vol["avg_cars_per_month"], 3.0)

    def test_03_average_stay_time(self):
        """Valida o cálculo do tempo médio de permanência da entrada à entrega."""
        ref_date = datetime.date(2026, 11, 10)

        # Carro 1: Entrada 01/11/2026, Saída 03/11/2026 -> 2 dias
        self._insert_test_file("ABC1234", "Cliente 1", "Civic", "01/11/2026", exit_date_str="03/11/2026")
        # Carro 2: Entrada 04/11/2026, Saída 08/11/2026 -> 4 dias
        self._insert_test_file("XYZ9876", "Cliente 2", "Corolla", "04/11/2026", exit_date_str="08/11/2026")
        # Carro 3: Entrada 05/11/2026, Saída 05/11/2026 -> 0 dias (mesmo dia)
        self._insert_test_file("BRA2E19", "Cliente 3", "HB20", "05/11/2026", exit_date_str="05/11/2026")
        # Carro 4: Entrada 06/11/2026, sem data de saída ainda (em aberto no pátio)
        self._insert_test_file("FFF0001", "Cliente 4", "Kwid", "06/11/2026", exit_date_str="")

        data = cache.get_analytics(period="30", db_path=self.db_path, ref_date=ref_date)
        stay = data["stay_time"]

        # Medidos: 3 veículos (2, 4, 0 dias) -> Média = (2 + 4 + 0) / 3 = 2.0 dias
        self.assertEqual(stay["stays_measured_count"], 3)
        self.assertEqual(stay["avg_stay_days"], 2.0)
        self.assertEqual(stay["min_stay_days"], 0)
        self.assertEqual(stay["max_stay_days"], 4)
        self.assertEqual(stay["distribution"]["same_day"], 1)
        self.assertEqual(stay["distribution"]["days_1_to_3"], 1)
        self.assertEqual(stay["distribution"]["days_4_to_7"], 1)
        self.assertEqual(stay["distribution"]["days_over_7"], 0)

    def test_04_financial_averages_parts_and_labor(self):
        """Valida valor médio de autopeças por OS e valor médio de mão de obra por serviço."""
        ref_date = datetime.date(2026, 11, 10)

        # OS 1: Peças R$ 600, Mão de Obra R$ 400 (Total R$ 1000)
        self._insert_test_file("CAR1111", "Cliente 1", "Polo", "01/11/2026", parts_val=600.0, labor_val=400.0)
        # OS 2: Peças R$ 400, Mão de Obra R$ 200 (Total R$ 600)
        self._insert_test_file("CAR2222", "Cliente 2", "Argo", "02/11/2026", parts_val=400.0, labor_val=200.0)
        # OS 3: Apenas diagnóstico de mão de obra R$ 300 (sem peças)
        self._insert_test_file("CAR3333", "Cliente 3", "Cruze", "03/11/2026", parts_val=0.0, labor_val=300.0)

        data = cache.get_analytics(period="30", db_path=self.db_path, ref_date=ref_date)
        fin = data["financials"]

        self.assertEqual(fin["total_parts"], 1000.0)
        self.assertEqual(fin["total_labor"], 900.0)
        self.assertEqual(fin["total_revenue"], 1900.0)

        # Média de peças por OS (total 3 OSs): 1000 / 3 = 333.33
        self.assertAlmostEqual(fin["avg_parts_per_order"], 333.33, places=2)
        # Média de peças quando há peças (2 OSs): 1000 / 2 = 500.0
        self.assertEqual(fin["avg_parts_per_billed_order"], 500.0)

        # Média de mão de obra por OS/serviço (total 3 OSs): 900 / 3 = 300.0
        self.assertEqual(fin["avg_labor_per_order"], 300.0)
        self.assertEqual(fin["avg_labor_per_billed_order"], 300.0)

        # Proporção
        self.assertAlmostEqual(fin["parts_percentage"], 52.6, places=1)
        self.assertAlmostEqual(fin["labor_percentage"], 47.4, places=1)

    def test_05_period_filters_30_90_and_all(self):
        """Valida que os filtros 30 dias, 90 dias e geral segregam corretamente os períodos."""
        ref_date = datetime.date(2026, 11, 10)

        # 10 dias atrás (dentro dos 30 dias)
        self._insert_test_file("AAA0001", "Cliente 1", "Ka", "01/11/2026", parts_val=100, labor_val=100)
        # 50 dias atrás (fora dos 30 dias, mas dentro dos 90 dias)
        self._insert_test_file("BBB0002", "Cliente 2", "Uno", "20/09/2026", parts_val=200, labor_val=200)
        # 200 dias atrás (fora dos 90 dias, apenas em 'all')
        self._insert_test_file("CCC0003", "Cliente 3", "Palio", "24/04/2026", parts_val=500, labor_val=500)

        d30 = cache.get_analytics(period="30", db_path=self.db_path, ref_date=ref_date)
        self.assertEqual(d30["volume"]["total_cars"], 1)
        self.assertEqual(d30["financials"]["total_revenue"], 200.0)

        d90 = cache.get_analytics(period="90", db_path=self.db_path, ref_date=ref_date)
        self.assertEqual(d90["volume"]["total_cars"], 2)
        self.assertEqual(d90["financials"]["total_revenue"], 600.0)

        d_all = cache.get_analytics(period="all", db_path=self.db_path, ref_date=ref_date)
        self.assertEqual(d_all["volume"]["total_cars"], 3)
        self.assertEqual(d_all["financials"]["total_revenue"], 1600.0)

    def test_06_api_analytics_endpoint(self):
        """Valida endpoint REST /api/analytics com respostas HTTP e serialização JSON."""
        ref_date = "2026-11-10"
        self._insert_test_file("ABC1234", "Carlos Silva", "Fox", "05/11/2026", "07/11/2026", parts_val=400, labor_val=300)

        # Teste GET /api/analytics padrão (30 dias)
        resp = self.client.get(f"/api/analytics?period=30&ref_date={ref_date}&db_path={self.db_path}")
        self.assertEqual(resp.status_code, 200)
        payload = resp.get_json()
        self.assertTrue(payload["success"])
        data = payload["data"]

        self.assertEqual(data["period"], "30")
        self.assertEqual(data["volume"]["total_cars"], 1)
        self.assertEqual(data["stay_time"]["avg_stay_days"], 2.0)
        self.assertEqual(data["financials"]["avg_parts_per_order"], 400.0)
        self.assertEqual(data["financials"]["avg_labor_per_order"], 300.0)
        self.assertTrue(len(data["recent_orders"]) >= 1)
        self.assertEqual(data["recent_orders"][0]["plate_clean"], "ABC1234")


if __name__ == "__main__":
    unittest.main()
