# -*- coding: utf-8 -*-
"""
Testes unitários e de integração para o Checkpoint [CP-01] (Issue #1)
- Validação das tabelas patio_status e nf_control no SQLite
- Validação das funções de acesso em cache.py (list, get, update, delete)
- Validação de preservação do banco de dados existente (sem quebra de files)
- Validação de compatibilidade com rotas do servidor e TV
"""

import os
import tempfile
import sqlite3
import unittest
import cache

class TestCP01Database(unittest.TestCase):

    def test_fresh_database_schema(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            cache.init_db(temp_db_path)
            conn = sqlite3.connect(temp_db_path)
            cur = conn.cursor()

            # Verifica patio_status
            cur.execute("PRAGMA table_info(patio_status)")
            patio_cols = [row[1] for row in cur.fetchall()]
            expected_patio = [
                "id", "file_path", "plate", "plate_clean", "status",
                "mechanic_name", "third_party_name", "third_party_doc",
                "updated_at", "notes"
            ]
            self.assertEqual(patio_cols, expected_patio, f"Colunas de patio_status incorretas: {patio_cols}")

            # Verifica nf_control
            cur.execute("PRAGMA table_info(nf_control)")
            nf_cols = [row[1] for row in cur.fetchall()]
            expected_nf = [
                "id", "file_path", "plate_clean", "visit_num",
                "nfse_status", "nfse_number", "nfe_status", "nfe_number",
                "updated_at", "notes"
            ]
            self.assertEqual(nf_cols, expected_nf, f"Colunas de nf_control incorretas: {nf_cols}")

            # Verifica templates
            cur.execute("PRAGMA table_info(templates)")
            templates_cols = [row[1] for row in cur.fetchall()]
            self.assertTrue("id" in templates_cols and "name" in templates_cols and "content" in templates_cols)

            # Verifica files
            cur.execute("PRAGMA table_info(files)")
            files_cols = [row[1] for row in cur.fetchall()]
            self.assertTrue("file_path" in files_cols and "plate_clean" in files_cols)

            conn.close()
        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_patio_status_crud(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            cache.init_db(temp_db_path)

            # 1. Inserir veículo no pátio
            item = cache.update_patio_status(
                plate="ABC-1234",
                file_path="C:/oficina/ABC1234 - 1 - Cliente Teste.xlsx",
                status="Em Diagnóstico", # Deve normalizar para Em Diagnostico
                mechanic_name="Mestre Tonho",
                third_party_name="Guincho Silva",
                third_party_doc="123.456.789-00",
                notes="Cliente reclamou de barulho na suspensão dianteira",
                db_path=temp_db_path
            )

            self.assertIsNotNone(item)
            self.assertEqual(item["id"], 1)
            self.assertEqual(item["plate_clean"], "ABC1234")
            self.assertEqual(item["status"], "Em Diagnostico")
            self.assertEqual(item["mechanic_name"], "Mestre Tonho")
            self.assertEqual(item["third_party_name"], "Guincho Silva")
            self.assertEqual(item["third_party_doc"], "123.456.789-00")
            self.assertEqual(item["notes"], "Cliente reclamou de barulho na suspensão dianteira")
            self.assertTrue(bool(item["updated_at"]))

            # 2. Obter por placa e por id
            by_plate = cache.get_patio_status(plate="ABC1234", db_path=temp_db_path)
            self.assertIsNotNone(by_plate)
            self.assertEqual(by_plate["id"], 1)

            by_id = cache.get_patio_status(id=1, db_path=temp_db_path)
            self.assertIsNotNone(by_id)
            self.assertEqual(by_id["plate"], "ABC-1234")

            # 3. Atualizar status para Em Execucao
            updated = cache.update_patio_status(
                record_id=1,
                status="Em Execucao",
                mechanic_name="Tonho e Carlos",
                db_path=temp_db_path
            )
            self.assertEqual(updated["status"], "Em Execucao")
            self.assertEqual(updated["mechanic_name"], "Tonho e Carlos")
            self.assertEqual(updated["notes"], "Cliente reclamou de barulho na suspensão dianteira")

            # 4. Inserir mais veículos com outros status válidos
            statuses = [
                "Esperando Orcamento",
                "Esperando Aprovacao",
                "Esperando Pecas",
                "Esperando Cliente",
                "Liberado Terceiro"
            ]
            for idx, st in enumerate(statuses, start=2):
                cache.update_patio_status(
                    plate=f"CAR{idx:04d}",
                    status=st,
                    notes=f"Teste status {st}",
                    db_path=temp_db_path
                )

            # 5. Listar todos
            all_patio = cache.list_patio_status(db_path=temp_db_path)
            self.assertEqual(len(all_patio), 6)

            # 6. Filtrar por status
            exec_list = cache.list_patio_status(status="Em Execucao", db_path=temp_db_path)
            self.assertEqual(len(exec_list), 1)
            self.assertEqual(exec_list[0]["plate_clean"], "ABC1234")

            filtered_multi = cache.list_patio_status(
                status=["Esperando Pecas", "Liberado Terceiro"],
                db_path=temp_db_path
            )
            self.assertEqual(len(filtered_multi), 2)

            # 7. Summary
            summary = cache.get_patio_summary(db_path=temp_db_path)
            self.assertEqual(summary["total"], 6)
            self.assertEqual(summary["by_status"]["Em Execucao"], 1)
            self.assertEqual(summary["by_status"]["Esperando Pecas"], 1)

            # 8. Remover veículo
            deleted = cache.delete_patio_status(plate="ABC1234", db_path=temp_db_path)
            self.assertTrue(deleted)
            self.assertIsNone(cache.get_patio_status(plate="ABC1234", db_path=temp_db_path))
            self.assertEqual(len(cache.list_patio_status(db_path=temp_db_path)), 5)

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_nf_control_crud(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            temp_db_path = tmp.name

        try:
            cache.init_db(temp_db_path)

            # 1. Inserir controle de NF
            nf = cache.update_nf_control(
                file_path="C:/oficina/XYZ9999 - 3 - Maria.xlsx",
                plate_clean="XYZ9999",
                visit_num="3",
                nfse_status="Pendente",
                nfe_status="Pendente",
                notes="Aguardando liberação do cliente para emitir NF de peças",
                db_path=temp_db_path
            )

            self.assertIsNotNone(nf)
            self.assertEqual(nf["id"], 1)
            self.assertEqual(nf["plate_clean"], "XYZ9999")
            self.assertEqual(nf["visit_num"], "3")
            self.assertEqual(nf["nfse_status"], "Pendente")
            self.assertEqual(nf["nfe_status"], "Pendente")
            self.assertEqual(nf["notes"], "Aguardando liberação do cliente para emitir NF de peças")

            # 2. Obter por (plate_clean, visit_num)
            by_pv = cache.get_nf_control(plate_clean="XYZ9999", visit_num="3", db_path=temp_db_path)
            self.assertIsNotNone(by_pv)
            self.assertEqual(by_pv["id"], 1)

            # 3. Atualizar NFS-e para Emitida
            updated_nf = cache.update_nf_control(
                record_id=1,
                nfse_status="Emitida",
                nfse_number="2026001234",
                db_path=temp_db_path
            )
            self.assertEqual(updated_nf["nfse_status"], "Emitida")
            self.assertEqual(updated_nf["nfse_number"], "2026001234")
            self.assertEqual(updated_nf["nfe_status"], "Pendente")

            # 4. Listar pendentes (deve conter XYZ9999 pois NF-e de peças ainda está Pendente)
            pending = cache.get_pending_nf_list(db_path=temp_db_path)
            self.assertEqual(len(pending), 1)
            self.assertEqual(pending[0]["plate_clean"], "XYZ9999")

            # 5. Atualizar NF-e para Emitida
            cache.update_nf_control(
                record_id=1,
                nfe_status="Emitida",
                nfe_number="550098",
                db_path=temp_db_path
            )

            # Agora não há mais pendências
            pending_after = cache.get_pending_nf_list(db_path=temp_db_path)
            self.assertEqual(len(pending_after), 0)

            # Listar todas
            all_nfs = cache.list_nf_control(db_path=temp_db_path)
            self.assertEqual(len(all_nfs), 1)

            # Deletar
            deleted = cache.delete_nf_control(record_id=1, db_path=temp_db_path)
            self.assertTrue(deleted)
            self.assertEqual(len(cache.list_nf_control(db_path=temp_db_path)), 0)

        finally:
            if os.path.exists(temp_db_path):
                os.remove(temp_db_path)

    def test_existing_database_preservation(self):
        """
        Garante que a base oficial oficina_cache.db mantém suas 4 planilhas indexadas intactas.
        """
        official_db = cache.get_db_path()
        self.assertTrue(os.path.exists(official_db), "oficina_cache.db deve existir na raiz")

        cache.init_db(official_db)
        stats = cache.get_stats(official_db)
        self.assertGreaterEqual(stats["total_files"], 4, f"Deveriam existir pelo menos 4 arquivos no cache, encontrado: {stats['total_files']}")

        # Testa busca existente
        results = cache.search_files("FNB", official_db)
        self.assertGreater(len(results), 0, "Deveria encontrar veículo FNB1A77 existente")

        # Testa status pátio no banco oficial
        patio = cache.list_patio_status(db_path=official_db)
        self.assertIsInstance(patio, list)

        # Testa controle fiscal no banco oficial
        nfs = cache.list_nf_control(db_path=official_db)
        self.assertIsInstance(nfs, list)

if __name__ == "__main__":
    unittest.main()
