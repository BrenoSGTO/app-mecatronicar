"""
Testes unitários e de integração para a Issue #12:
Padronização visual dos cards de veículos, catálogo de marcas e modelos,
placa Mercosul oficial e eliminação completa de emojis no app MecatroniCar.
"""

import os
import re
import unittest
from pdf_generator import render_orcamento_html, render_checklist_html, format_plate_display


class TestVisualCardsAndAssets(unittest.TestCase):
    """Testes de validação dos assets visuais, placa Mercosul e ausência de emojis."""

    def setUp(self):
        self.root_dir = os.path.dirname(os.path.abspath(__file__))
        self.brands_dir = os.path.join(self.root_dir, 'static', 'brands')
        self.models_dir = os.path.join(self.root_dir, 'static', 'models')
        self.emoji_pattern = re.compile(r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50]')

    def test_01_brand_logos_exist_and_valid_svg(self):
        """Verifica se os logos vetoriais das montadoras existem e são SVGs válidos."""
        expected_brands = [
            'fiat.svg', 'volkswagen.svg', 'chevrolet.svg', 'toyota.svg',
            'hyundai.svg', 'renault.svg', 'jeep.svg', 'nissan.svg',
            'honda.svg', 'ford.svg', 'peugeot.svg', 'citroen.svg',
            'mitsubishi.svg', 'chery.svg', 'bmw.svg', 'mercedes.svg',
            'audi.svg', 'kia.svg', 'byd.svg', 'generic.svg'
        ]
        self.assertTrue(os.path.isdir(self.brands_dir), f"Diretório {self.brands_dir} não encontrado")

        for brand_file in expected_brands:
            file_path = os.path.join(self.brands_dir, brand_file)
            self.assertTrue(os.path.isfile(file_path), f"Logo não encontrado: {brand_file}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertGreater(len(content), 50, f"SVG muito pequeno: {brand_file}")
            self.assertIn('<svg', content, f"Arquivo {brand_file} não contém tag <svg")
            self.assertIn('</svg>', content, f"Arquivo {brand_file} não contém fechamento </svg>")

    def test_02_popular_model_silhouettes_exist(self):
        """Verifica se toda silhueta referenciada pelo catálogo (arquétipos + genéricos) existe.

        Repaginação v3 (T6): as ~100 silhuetas individuais foram substituídas por
        arquétipos de carroceria em escala real; cada modelo de POPULAR_MODELS
        aponta para um arquétipo pelo campo ``shape`` em static/car_catalog.js.
        """
        self.assertTrue(os.path.isdir(self.models_dir), f"Diretório {self.models_dir} não encontrado")

        catalog_path = os.path.join(self.root_dir, 'static', 'car_catalog.js')
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog = f.read()
        model_keys = re.findall(r"key:\s*'([^']+)',\s*name:", catalog)
        shapes = re.findall(r"key:\s*'[^']+',\s*name:\s*'[^']+',\s*body:\s*'[^']+',\s*shape:\s*'([^']+)'", catalog)
        self.assertGreaterEqual(len(model_keys), 100, "Catálogo deveria mapear ao menos 100 modelos")
        self.assertEqual(len(shapes), len(model_keys), "Todo modelo do catálogo precisa de um campo shape")

        generics = ['car-generic', 'hatch-generic', 'sedan-generic',
                    'suv-generic', 'pickup-generic', 'van-generic']
        for name in sorted(set(shapes) | set(generics)):
            file_path = os.path.join(self.models_dir, f'{name}.svg')
            self.assertTrue(os.path.isfile(file_path), f"Silhueta não encontrada: {name}.svg")
            self._assert_clean_svg(file_path)

    def test_02b_assets_are_optimized_and_themeable(self):
        """Todos os SVGs de marcas e modelos: < 3 KB, viewBox, sem width/height fixos, currentColor."""
        for folder in (self.brands_dir, self.models_dir):
            for name in os.listdir(folder):
                if name.endswith('.svg'):
                    self._assert_clean_svg(os.path.join(folder, name))

    def _assert_clean_svg(self, file_path):
        name = os.path.basename(file_path)
        self.assertLess(os.path.getsize(file_path), 3 * 1024, f"{name} maior que 3 KB")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        root = re.search(r'<svg\b[^>]*>', content)
        self.assertIsNotNone(root, f"{name} sem tag <svg")
        self.assertIn('</svg>', content, f"{name} sem tag </svg>")
        self.assertIn('viewBox="', root.group(0), f"{name} sem viewBox")
        self.assertNotRegex(root.group(0), r'\s(width|height)=', f"{name} com width/height fixos")
        self.assertIn('currentColor', content, f"{name} não usa currentColor")
        for junk in ('<metadata', '<!--', 'sodipodi', 'inkscape', 'data:image'):
            self.assertNotIn(junk, content, f"{name} contém {junk}")

    def test_03_car_catalog_js_contains_required_functions(self):
        """Verifica se static/car_catalog.js expõe todas as funções necessárias."""
        catalog_path = os.path.join(self.root_dir, 'static', 'car_catalog.js')
        self.assertTrue(os.path.isfile(catalog_path), "static/car_catalog.js não encontrado")

        with open(catalog_path, 'r', encoding='utf-8') as f:
            content = f.read()

        expected_symbols = [
            'BRANDS',
            'POPULAR_MODELS',
            'identifyCar',
            'renderMercosulPlateHtml',
            'renderBrandLogoHtml',
            'renderCarSilhouetteHtml',
            'getIcon'
        ]
        for sym in expected_symbols:
            self.assertIn(sym, content, f"Símbolo {sym} não encontrado em car_catalog.js")

    def test_04_css_classes_defined(self):
        """Verifica se classes essenciais para Placa Mercosul e Cards existem no CSS."""
        style_path = os.path.join(self.root_dir, 'static', 'style.css')
        tv_css_path = os.path.join(self.root_dir, 'static', 'tv.css')

        with open(style_path, 'r', encoding='utf-8') as f:
            style_content = f.read()
        with open(tv_css_path, 'r', encoding='utf-8') as f:
            tv_content = f.read()

        for cls in ['.mercosul-plate', '.mercosul-top-bar', '.mercosul-body-area', '.brand-logo-container', '.car-silhouette-container']:
            self.assertIn(cls, style_content, f"Classe {cls} não encontrada em static/style.css")

        for cls in ['.mercosul-plate', '.brand-logo-container', '.car-silhouette-container']:
            self.assertIn(cls, tv_content, f"Classe {cls} não encontrada em static/tv.css")

    def test_05_strict_zero_emojis_in_core_files(self):
        """Validação estrita de 0 emojis nos arquivos de código e templates."""
        files_to_check = [
            os.path.join('static', 'app.js'),
            os.path.join('static', 'index.html'),
            os.path.join('static', 'tv.js'),
            os.path.join('static', 'tv.html'),
            'pdf_generator.py',
            'gui_desktop.py',
            'apresentacao_pitch.html'
        ]

        for rel_path in files_to_check:
            full_path = os.path.join(self.root_dir, rel_path)
            self.assertTrue(os.path.isfile(full_path), f"Arquivo não encontrado: {rel_path}")
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            matches = self.emoji_pattern.findall(content)
            self.assertEqual(
                len(matches), 0,
                f"Arquivo {rel_path} contém {len(matches)} emojis: {matches[:5]}"
            )

    def test_06_pdf_mercosul_plate_generation(self):
        """Verifica se o gerador de PDF gera orçamentos e checklists com placa Mercosul sem erros."""
        mock_data = {
            'client_name': 'Oficina Teste',
            'car_model': 'Chevrolet Onix 1.0 Flex',
            'plate': 'BRA-2E19',
            'plate_display': 'BRA2E19',
            'phone': '(13) 99999-9999',
            'date': '12/11/2026',
            'km': '45000',
            'pecas': [
                {'description': 'Troca de Óleo 5W30 Sintético', 'quantity': '4', 'unit_price': 'R$ 45,00', 'total_price': 'R$ 180,00'},
                {'description': 'Filtro de Óleo Motor', 'quantity': '1', 'unit_price': 'R$ 35,00', 'total_price': 'R$ 35,00'}
            ],
            'servicos': [
                {'description': 'Mão de Obra Troca de Óleo e Filtros', 'quantity': '1', 'unit_price': 'R$ 150,00', 'total_price': 'R$ 150,00'}
            ],
            'total_pecas': 'R$ 215,00',
            'total_servicos': 'R$ 150,00',
            'total_geral': 'R$ 365,00',
            'complaint_comment': 'Veículo revisado conforme especificações do fabricante.'
        }

        orcamento_html = render_orcamento_html(mock_data)
        self.assertIsNotNone(orcamento_html)
        self.assertTrue('plate-mercosul' in orcamento_html or 'mercosul-plate' in orcamento_html)
        self.assertIn('BRA2E19', orcamento_html)
        self.assertIn('BRASIL', orcamento_html)

        checklist_html = render_checklist_html(mock_data)
        self.assertIsNotNone(checklist_html)
        self.assertTrue('plate-mercosul' in checklist_html or 'mercosul-plate' in checklist_html)
        self.assertIn('BRA2E19', checklist_html)

        # Garantir ausência de emojis no HTML gerado
        self.assertEqual(len(self.emoji_pattern.findall(orcamento_html)), 0)
        self.assertEqual(len(self.emoji_pattern.findall(checklist_html)), 0)


if __name__ == '__main__':
    unittest.main()
