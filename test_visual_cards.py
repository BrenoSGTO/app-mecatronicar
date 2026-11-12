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
        """Verifica se as silhuetas dos 100 modelos populares + genéricos existem em static/models/."""
        self.assertTrue(os.path.isdir(self.models_dir), f"Diretório {self.models_dir} não encontrado")

        # 10 modelos das 10 principais montadoras
        expected_models = [
            # Fiat
            'fiat-argo.svg', 'fiat-cronos.svg', 'fiat-fastback.svg', 'fiat-fiorino.svg',
            'fiat-mobi.svg', 'fiat-palio.svg', 'fiat-pulse.svg', 'fiat-strada.svg',
            'fiat-toro.svg', 'fiat-uno.svg',
            # VW
            'vw-fox.svg', 'vw-gol.svg', 'vw-nivus.svg', 'vw-polo.svg',
            'vw-saveiro.svg', 'vw-taos.svg', 'vw-tcross.svg', 'vw-up.svg',
            'vw-virtus.svg', 'vw-voyage.svg',
            # Chevrolet
            'chevrolet-celta.svg', 'chevrolet-corsa.svg', 'chevrolet-cruze.svg', 'chevrolet-montana.svg',
            'chevrolet-onix-plus.svg', 'chevrolet-onix.svg', 'chevrolet-prisma.svg', 'chevrolet-s10.svg',
            'chevrolet-spin.svg', 'chevrolet-tracker.svg',
            # Toyota
            'toyota-bandeirante.svg', 'toyota-corolla-cross.svg', 'toyota-corolla.svg', 'toyota-etios.svg',
            'toyota-hilux.svg', 'toyota-prius.svg', 'toyota-rav4.svg', 'toyota-sw4.svg',
            'toyota-yaris-hatch.svg', 'toyota-yaris-sedan.svg',
            # Hyundai
            'hyundai-azera.svg', 'hyundai-creta.svg', 'hyundai-elantra.svg', 'hyundai-hb20.svg',
            'hyundai-hb20s.svg', 'hyundai-hr.svg', 'hyundai-i30.svg', 'hyundai-ix35.svg',
            'hyundai-santafe.svg', 'hyundai-tucson.svg',
            # Renault
            'renault-captur.svg', 'renault-clio.svg', 'renault-duster.svg', 'renault-kangoo.svg',
            'renault-kwid.svg', 'renault-logan.svg', 'renault-master.svg', 'renault-megane.svg',
            'renault-oroch.svg', 'renault-sandero.svg',
            # Jeep
            'jeep-cherokee.svg', 'jeep-commander-blackhawk.svg', 'jeep-commander.svg', 'jeep-compass-4xe.svg',
            'jeep-compass.svg', 'jeep-gladiator.svg', 'jeep-grandcherokee.svg', 'jeep-renegade-4xe.svg',
            'jeep-renegade.svg', 'jeep-wrangler.svg',
            # Nissan
            'nissan-frontier.svg', 'nissan-grandlivina.svg', 'nissan-kicks.svg', 'nissan-livina.svg',
            'nissan-march.svg', 'nissan-sentra.svg', 'nissan-tiida.svg', 'nissan-vdrive.svg',
            'nissan-versa.svg', 'nissan-xtrail.svg',
            # Honda
            'honda-accord.svg', 'honda-city-hatchback.svg', 'honda-city.svg', 'honda-civic.svg',
            'honda-crv.svg', 'honda-fit.svg', 'honda-hrv.svg', 'honda-prelude.svg',
            'honda-wrv.svg', 'honda-zrv.svg',
            # Ford
            'ford-bronco-sport.svg', 'ford-ecosport.svg', 'ford-fiesta.svg', 'ford-focus.svg',
            'ford-fusion.svg', 'ford-ka-sedan.svg', 'ford-ka.svg', 'ford-maverick.svg',
            'ford-ranger.svg', 'ford-territory.svg',
            # Silhuetas Genéricas
            'car-generic.svg', 'hatch-generic.svg', 'sedan-generic.svg',
            'suv-generic.svg', 'pickup-generic.svg', 'van-generic.svg'
        ]

        self.assertEqual(len(expected_models), 106, "Deveriam existir 106 silhuetas mapeadas")

        for model_file in expected_models:
            file_path = os.path.join(self.models_dir, model_file)
            self.assertTrue(os.path.isfile(file_path), f"Silhueta não encontrada: {model_file}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.assertGreater(len(content), 50, f"SVG muito pequeno: {model_file}")
            self.assertIn('<svg', content, f"{model_file} sem tag <svg")
            self.assertIn('</svg>', content, f"{model_file} sem tag </svg>")

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
