# -*- coding: utf-8 -*-
"""
test_gerar_massa_dados.py
Testes unitários para o gerador de massa de dados realista gerar_massa_dados.py (Issue #10).
"""

import os
import shutil
import tempfile
import unittest
import openpyxl

import gerar_massa_dados
import parser
import cache

class TestGerarMassaDados(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="mecatroni_seed_test_")
        self.db_path = os.path.join(self.test_dir, "test_cache.db")
        cache.init_db(self.db_path)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_generate_mass_data_execution_and_integrity(self):
        """Valida geração de massa reduzida (10 planilhas), leitura via parser e integridade no cache."""
        res = gerar_massa_dados.generate_mass_data(
            target_folder=self.test_dir,
            db_file=self.db_path,
            target_total=10,
            seed=123,
            clean_first=False
        )

        self.assertTrue(res["success"])
        self.assertEqual(res["total_generated"], 10)

        # Verifica arquivos físicos gerados
        files = [f for f in os.listdir(self.test_dir) if f.endswith(".xlsx")]
        self.assertEqual(len(files), 10)

        # Testa leitura e integridade da primeira planilha via parser.py
        first_file = os.path.join(self.test_dir, files[0])
        parsed = parser.parse_file(first_file)

        self.assertIsNotNone(parsed)
        self.assertTrue(len(parsed.get("plate", "")) >= 7)
        self.assertTrue(len(parsed.get("client_name", "")) > 0)
        self.assertIn("pecas_items", parsed)
        self.assertIn("servicos_items", parsed)
        self.assertTrue(len(parsed["pecas_items"]) > 0)
        self.assertTrue(len(parsed["servicos_items"]) > 0)
        self.assertTrue(parsed.get("total", "").startswith("R$"))

        # Valida banco de dados SQLite preenchido
        stats = cache.get_stats(self.db_path)
        self.assertEqual(stats["total_files"], 10)
        self.assertGreater(stats["total_cars"], 0)
        self.assertGreater(stats["total_clients"], 0)

        # Valida se os status do pátio foram persistidos
        patio = cache.list_patio_status(db_path=self.db_path)
        self.assertIsInstance(patio, list)

        # Valida se registros fiscais foram inseridos
        nfs = cache.list_nf_control(db_path=self.db_path)
        self.assertIsInstance(nfs, list)
        self.assertGreater(len(nfs), 0)

    def test_preservation_of_legacy_files(self):
        """Garante que a flag --clean não apaga os arquivos legados oficiais."""
        # Cria um arquivo mock com o mesmo nome de um arquivo legado
        legacy_mock = os.path.join(self.test_dir, gerar_massa_dados.PRESERVED_LEGACY_FILES[0])
        with open(legacy_mock, "w", encoding="utf-8") as f:
            f.write("legado")

        # Roda a geração com clean_first=True
        gerar_massa_dados.generate_mass_data(
            target_folder=self.test_dir,
            db_file=self.db_path,
            target_total=5,
            seed=999,
            clean_first=True
        )

        # O arquivo legado deve continuar existindo intacto
        self.assertTrue(os.path.exists(legacy_mock))

if __name__ == "__main__":
    unittest.main()
