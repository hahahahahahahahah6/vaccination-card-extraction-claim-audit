"""Contract tests use temporary repositories and fixed reference literals."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from vaccination_card_extraction_claim_audit.audit import audit, match_phrases, normalize, source_evidence
from vaccination_card_extraction_claim_audit.phrases import VACCINATIONCARDEXTRACTION, NOVACCINATIONCARDEXTRACTION, GENERIC_NAMES
from vaccination_card_extraction_claim_audit.__main__ import main

EXPECTED_POS = ('vaccination card extraction', 'extract vaccination cards', 'extracts vaccination cards', 'extracting vaccination cards', 'extract vaccination card', 'extracts vaccination card', 'extracting vaccination card', 'vaccination card parsing', 'vaccination card parser', 'parse vaccination cards', 'parses vaccination cards', 'parse vaccination card', 'parses vaccination card', 'vaccination card scanning', 'vaccination card scanner', 'scan vaccination cards', 'scans vaccination cards', 'scan vaccination card', 'scans vaccination card', 'vaccine card extraction', 'extract vaccine cards', 'extracts vaccine cards', 'extracting vaccine cards', 'extract vaccine card', 'extracts vaccine card', 'extracting vaccine card', 'vaccine card parsing', 'vaccine card parser', 'parse vaccine cards', 'parses vaccine cards', 'parse vaccine card', 'parses vaccine card', 'vaccine card scanning', 'vaccine card scanner', 'scan vaccine cards', 'scans vaccine cards', 'scan vaccine card', 'scans vaccine card', 'vaccination card data extraction', 'extract vaccination card data', 'extracts vaccination card data', 'extracting vaccination card data', 'vaccination card data parsing', 'vaccination card data parser', 'parse vaccination card data', 'parses vaccination card data', 'vaccination card data scanning', 'vaccination card data scanner', 'scan vaccination card data', 'scans vaccination card data')
EXPECTED_NEG = ('no vaccination card extraction', 'does not extract vaccination cards', 'does not extract vaccination card', 'does not support vaccination card extraction', 'without vaccination card extraction', 'no vaccination card parser', 'does not parse vaccination cards', 'does not parse vaccination card', 'no vaccine card extraction', 'does not extract vaccine cards', 'does not extract vaccine card', 'does not support vaccine card extraction', 'without vaccine card extraction', 'no vaccine card parser', 'does not parse vaccine cards', 'does not parse vaccine card', 'no vaccination card scanner', 'does not scan vaccination cards', 'does not scan vaccination card', 'no vaccination card data extraction', 'does not extract vaccination card data', 'without vaccination card data extraction', 'no vaccine card scanner', 'vaccination card extraction not supported')
EXPECTED_NAMES = ('extract_vaccination_card', 'extract_vaccination_cards', 'parse_vaccination_card', 'parse_vaccination_cards', 'extract_vaccination_card_data', 'parse_vaccination_card_data', 'vaccination_card_extraction', 'vaccination_card_extractor', 'vaccination_card_parser', 'extract_vaccine_card', 'parse_vaccine_card', 'vaccine_card_extraction', 'vaccine_card_extractor', 'vaccine_card_parser', 'extract_vaccination_card_info', 'parse_vaccination_card_info', 'vaccination_card_scan', 'vaccination_card_scanner', 'scan_vaccination_card', 'scan_vaccination_cards', 'extract_vaccine_card_info', 'parse_vaccine_card_info', 'extract_vaccine_card_data', 'parse_vaccine_card_data')

class AuditTests(unittest.TestCase):
    def repo(self, files):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for name, content in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
        return root

    def cli(self, root, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(['audit', str(root), '--json', *args])
        return code, json.loads(out.getvalue())

    def test_phrase_oracle(self):
        phrase_file = Path(__file__).resolve().parents[1] / 'vaccination_card_extraction_claim_audit' / 'phrases.py'
        parsed = {node.targets[0].id: ast.literal_eval(node.value)
                  for node in ast.parse(phrase_file.read_text()).body
                  if isinstance(node, ast.Assign)}
        self.assertEqual(parsed['VACCINATIONCARDEXTRACTION'], EXPECTED_POS)
        self.assertEqual(parsed['NOVACCINATIONCARDEXTRACTION'], EXPECTED_NEG)
        self.assertEqual(parsed['GENERIC_NAMES'], EXPECTED_NAMES)
        self.assertEqual(VACCINATIONCARDEXTRACTION, EXPECTED_POS)
        self.assertEqual(NOVACCINATIONCARDEXTRACTION, EXPECTED_NEG)
        self.assertEqual(GENERIC_NAMES, EXPECTED_NAMES)
        self.assertEqual((len(EXPECTED_POS), len(EXPECTED_NEG), len(set(EXPECTED_NAMES))), (50, 24, 24))

    def test_good(self):
        self.assertEqual(self.cli(self.repo({'README.md': 'vaccination card extraction', 'app.py': 'x.extract_vaccination_card()'}))[0], 0)

    def test_bad(self):
        code, result = self.cli(self.repo({'README.md': 'vaccination card extraction'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-vaccination-card-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')
        self.assertTrue(result['findings'][0]['message'])
        self.assertEqual(result['verdict'], 'FAIL')
        self.assertIn('test_evidence', result)
        self.assertIn('production_evidence', result)

    def test_denial(self):
        code, result = self.cli(self.repo({'README.md': 'no vaccination card extraction', 'app.py': 'x.extract_vaccination_card()'}))
        self.assertEqual(code, 2)
        self.assertEqual(result['findings'][0]['rule'], 'documented-no-vaccination-card-extraction-claim-false')
        self.assertEqual(result['findings'][0]['severity'], 'HIGH')

    def test_no_source_denial(self):
        self.assertEqual(audit(self.repo({'README.md': 'no vaccination card extraction'}))['verdict'], 'PASS')

    def test_no_claim(self):
        self.assertEqual(audit(self.repo({'README.md': 'neutral', 'app.py': 'x.extract_vaccination_card()'}))['verdict'], 'PASS')

    def test_test_only(self):
        for filename in ('tests/helper.py', 'test_feature.py', 'feature_test.py'):
            with self.subTest(filename=filename):
                root = self.repo({'README.md': 'vaccination card extraction', filename: 'x.extract_vaccination_card()'})
                code, result = self.cli(root)
                self.assertEqual(code, 0)
                self.assertEqual(result['verdict'], 'PASS')
                self.assertEqual(result['findings'][0]['severity'], 'MEDIUM')
                code, result = self.cli(root, '--fail-on', 'medium')
                self.assertEqual(code, 2)
                self.assertEqual(result['verdict'], 'FAIL')

    def test_ignore_component_prefix(self):
        root = self.repo({'README.md': 'vaccination card extraction', 'src/a.py': 'x.extract_vaccination_card()'})
        self.assertEqual(self.cli(root, '--ignore', 'sr')[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'src')[0], 2)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', str(root), '--ignore', '../outside']), 1)
            self.assertEqual(main(['audit', str(root), '--ignore', '/abs']), 1)

    def test_fences(self):
        for fence in ('```', '~~~', '   ````'):
            root = self.repo({'README.md': fence + '\nvaccination card extraction\n' + fence})
            self.assertEqual(audit(root)['verdict'], 'PASS')
        root = self.repo({'README.md': '`vaccination card extraction`'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_boundaries_longest_denial(self):
        yes, no = match_phrases('extract vaccination cards')
        self.assertEqual([p[0] for p in yes], ['extract vaccination cards'])
        self.assertFalse(match_phrases('preextract vaccination cardsuffix')[0])
        yes, no = match_phrases('does not extract vaccination cards')
        self.assertEqual(yes, [])
        self.assertEqual([p[0] for p in no], ['does not extract vaccination cards'])
        self.assertEqual(match_phrases("doesn't extract vaccination cards")[0], [])
        self.assertEqual(normalize('VACCINATION-CARD  extraction'), 'vaccination card extraction')

    def test_invalid_encoding_declaration(self):
        root = self.repo({'README.md': 'vaccination card extraction', 'app.py': '# coding: nonexistent-r205\nx.extract_vaccination_card()'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_attribute_assignment_preserves_import(self):
        self.assertTrue(source_evidence('from p import extract_vaccination_card as e\ne.setting = True\ne()'))

    def test_single_module(self):
        root = self.repo({'README.md': 'vaccination card extraction', 'one.py': 'from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\n', 'two.py': 'x.begin_analyze_document("prebuilt-vaccinationCard")'})
        self.assertEqual(self.cli(root)[0], 2)

    def test_paths_and_ignore(self):
        for folder in ('fixtures', 'docs', 'examples'):
            root = self.repo({'README.md': 'vaccination card extraction', folder+'/a.py': 'x.extract_vaccination_card()'})
            self.assertEqual(self.cli(root)[0], 2)
        root = self.repo({'nested/docs/a.md': 'vaccination card extraction', 'other.md': 'no vaccination card extraction', 'vendor/a.py': 'x.extract_vaccination_card()'})
        self.assertEqual(self.cli(root)[0], 0)
        self.assertEqual(self.cli(root, '--ignore', 'vendor', '--ignore', 'unused')[0], 2)
        self.assertEqual(self.cli(root, '--ignore', 'nested')[0], 0)

    def test_symlinks(self):
        root = self.repo({'README.md': 'vaccination card extraction'})
        outside = self.repo({'a.py': 'x.extract_vaccination_card()', 'a.md': 'vaccination card extraction'})
        (root/'link.py').symlink_to(outside/'a.py')
        (root/'linked').symlink_to(outside, target_is_directory=True)
        self.assertEqual(self.cli(root)[0], 2)
        (root/'README.md').unlink()
        (root/'README.md').symlink_to(outside/'a.md')
        self.assertEqual(audit(root)['verdict'], 'PASS')

    def test_usage_io(self):
        for argv in ([], ['audit', '--fail-on', 'HIGH'], ['audit', '--unknown']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                main(argv)
            self.assertEqual(caught.exception.code, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['audit', '/nonexistent/r205']), 1)
        root = self.repo({})
        root.chmod(0)
        try:
            with self.assertRaises(OSError): audit(root)
        finally:
            root.chmod(0o700)

    def test_entry_points(self):
        root = self.repo({})
        command = [sys.executable, '-m', 'vaccination_card_extraction_claim_audit']
        self.assertEqual(subprocess.check_output(command+['--version'], text=True).strip(), '0.1.0')
        result = subprocess.run(command+['audit', str(root), '--json'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['verdict'], 'PASS')


    def test_positive_000(self):
        self.assertTrue(source_evidence('x.extract_vaccination_card()'))

    def test_positive_001(self):
        self.assertTrue(source_evidence('from provider import extract_vaccination_card as run\nrun()'))

    def test_positive_002(self):
        self.assertTrue(source_evidence('import provider.extract_vaccination_card as run\nrun()'))

    def test_positive_003(self):
        self.assertTrue(source_evidence('x.extract_vaccination_cards()'))

    def test_positive_004(self):
        self.assertTrue(source_evidence('from provider import extract_vaccination_cards as run\nrun()'))

    def test_positive_005(self):
        self.assertTrue(source_evidence('import provider.extract_vaccination_cards as run\nrun()'))

    def test_positive_006(self):
        self.assertTrue(source_evidence('x.parse_vaccination_card()'))

    def test_positive_007(self):
        self.assertTrue(source_evidence('from provider import parse_vaccination_card as run\nrun()'))

    def test_positive_008(self):
        self.assertTrue(source_evidence('import provider.parse_vaccination_card as run\nrun()'))

    def test_positive_009(self):
        self.assertTrue(source_evidence('x.parse_vaccination_cards()'))

    def test_positive_010(self):
        self.assertTrue(source_evidence('from provider import parse_vaccination_cards as run\nrun()'))

    def test_positive_011(self):
        self.assertTrue(source_evidence('import provider.parse_vaccination_cards as run\nrun()'))

    def test_positive_012(self):
        self.assertTrue(source_evidence('x.extract_vaccination_card_data()'))

    def test_positive_013(self):
        self.assertTrue(source_evidence('from provider import extract_vaccination_card_data as run\nrun()'))

    def test_positive_014(self):
        self.assertTrue(source_evidence('import provider.extract_vaccination_card_data as run\nrun()'))

    def test_positive_015(self):
        self.assertTrue(source_evidence('x.parse_vaccination_card_data()'))

    def test_positive_016(self):
        self.assertTrue(source_evidence('from provider import parse_vaccination_card_data as run\nrun()'))

    def test_positive_017(self):
        self.assertTrue(source_evidence('import provider.parse_vaccination_card_data as run\nrun()'))

    def test_positive_018(self):
        self.assertTrue(source_evidence('x.vaccination_card_extraction()'))

    def test_positive_019(self):
        self.assertTrue(source_evidence('from provider import vaccination_card_extraction as run\nrun()'))

    def test_positive_020(self):
        self.assertTrue(source_evidence('import provider.vaccination_card_extraction as run\nrun()'))

    def test_positive_021(self):
        self.assertTrue(source_evidence('x.vaccination_card_extractor()'))

    def test_positive_022(self):
        self.assertTrue(source_evidence('from provider import vaccination_card_extractor as run\nrun()'))

    def test_positive_023(self):
        self.assertTrue(source_evidence('import provider.vaccination_card_extractor as run\nrun()'))

    def test_positive_024(self):
        self.assertTrue(source_evidence('x.vaccination_card_parser()'))

    def test_positive_025(self):
        self.assertTrue(source_evidence('from provider import vaccination_card_parser as run\nrun()'))

    def test_positive_026(self):
        self.assertTrue(source_evidence('import provider.vaccination_card_parser as run\nrun()'))

    def test_positive_027(self):
        self.assertTrue(source_evidence('x.extract_vaccine_card()'))

    def test_positive_028(self):
        self.assertTrue(source_evidence('from provider import extract_vaccine_card as run\nrun()'))

    def test_positive_029(self):
        self.assertTrue(source_evidence('import provider.extract_vaccine_card as run\nrun()'))

    def test_positive_030(self):
        self.assertTrue(source_evidence('x.parse_vaccine_card()'))

    def test_positive_031(self):
        self.assertTrue(source_evidence('from provider import parse_vaccine_card as run\nrun()'))

    def test_positive_032(self):
        self.assertTrue(source_evidence('import provider.parse_vaccine_card as run\nrun()'))

    def test_positive_033(self):
        self.assertTrue(source_evidence('x.vaccine_card_extraction()'))

    def test_positive_034(self):
        self.assertTrue(source_evidence('from provider import vaccine_card_extraction as run\nrun()'))

    def test_positive_035(self):
        self.assertTrue(source_evidence('import provider.vaccine_card_extraction as run\nrun()'))

    def test_positive_036(self):
        self.assertTrue(source_evidence('x.vaccine_card_extractor()'))

    def test_positive_037(self):
        self.assertTrue(source_evidence('from provider import vaccine_card_extractor as run\nrun()'))

    def test_positive_038(self):
        self.assertTrue(source_evidence('import provider.vaccine_card_extractor as run\nrun()'))

    def test_positive_039(self):
        self.assertTrue(source_evidence('x.vaccine_card_parser()'))

    def test_positive_040(self):
        self.assertTrue(source_evidence('from provider import vaccine_card_parser as run\nrun()'))

    def test_positive_041(self):
        self.assertTrue(source_evidence('import provider.vaccine_card_parser as run\nrun()'))

    def test_positive_042(self):
        self.assertTrue(source_evidence('x.extract_vaccination_card_info()'))

    def test_positive_043(self):
        self.assertTrue(source_evidence('from provider import extract_vaccination_card_info as run\nrun()'))

    def test_positive_044(self):
        self.assertTrue(source_evidence('import provider.extract_vaccination_card_info as run\nrun()'))

    def test_positive_045(self):
        self.assertTrue(source_evidence('x.parse_vaccination_card_info()'))

    def test_positive_046(self):
        self.assertTrue(source_evidence('from provider import parse_vaccination_card_info as run\nrun()'))

    def test_positive_047(self):
        self.assertTrue(source_evidence('import provider.parse_vaccination_card_info as run\nrun()'))

    def test_positive_048(self):
        self.assertTrue(source_evidence('x.vaccination_card_scan()'))

    def test_positive_049(self):
        self.assertTrue(source_evidence('from provider import vaccination_card_scan as run\nrun()'))

    def test_positive_050(self):
        self.assertTrue(source_evidence('import provider.vaccination_card_scan as run\nrun()'))

    def test_positive_051(self):
        self.assertTrue(source_evidence('x.vaccination_card_scanner()'))

    def test_positive_052(self):
        self.assertTrue(source_evidence('from provider import vaccination_card_scanner as run\nrun()'))

    def test_positive_053(self):
        self.assertTrue(source_evidence('import provider.vaccination_card_scanner as run\nrun()'))

    def test_positive_054(self):
        self.assertTrue(source_evidence('x.scan_vaccination_card()'))

    def test_positive_055(self):
        self.assertTrue(source_evidence('from provider import scan_vaccination_card as run\nrun()'))

    def test_positive_056(self):
        self.assertTrue(source_evidence('import provider.scan_vaccination_card as run\nrun()'))

    def test_positive_057(self):
        self.assertTrue(source_evidence('x.scan_vaccination_cards()'))

    def test_positive_058(self):
        self.assertTrue(source_evidence('from provider import scan_vaccination_cards as run\nrun()'))

    def test_positive_059(self):
        self.assertTrue(source_evidence('import provider.scan_vaccination_cards as run\nrun()'))

    def test_positive_060(self):
        self.assertTrue(source_evidence('x.extract_vaccine_card_info()'))

    def test_positive_061(self):
        self.assertTrue(source_evidence('from provider import extract_vaccine_card_info as run\nrun()'))

    def test_positive_062(self):
        self.assertTrue(source_evidence('import provider.extract_vaccine_card_info as run\nrun()'))

    def test_positive_063(self):
        self.assertTrue(source_evidence('x.parse_vaccine_card_info()'))

    def test_positive_064(self):
        self.assertTrue(source_evidence('from provider import parse_vaccine_card_info as run\nrun()'))

    def test_positive_065(self):
        self.assertTrue(source_evidence('import provider.parse_vaccine_card_info as run\nrun()'))

    def test_positive_066(self):
        self.assertTrue(source_evidence('x.extract_vaccine_card_data()'))

    def test_positive_067(self):
        self.assertTrue(source_evidence('from provider import extract_vaccine_card_data as run\nrun()'))

    def test_positive_068(self):
        self.assertTrue(source_evidence('import provider.extract_vaccine_card_data as run\nrun()'))

    def test_positive_069(self):
        self.assertTrue(source_evidence('x.parse_vaccine_card_data()'))

    def test_positive_070(self):
        self.assertTrue(source_evidence('from provider import parse_vaccine_card_data as run\nrun()'))

    def test_positive_071(self):
        self.assertTrue(source_evidence('import provider.parse_vaccine_card_data as run\nrun()'))

    def test_positive_072(self):
        self.assertTrue(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document("prebuilt-vaccinationCard")'))

    def test_positive_073(self):
        self.assertTrue(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document(model_id="prebuilt-vaccinationCard")'))

    def test_positive_074(self):
        self.assertTrue(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document_from_url("prebuilt-vaccinationCard")'))

    def test_positive_075(self):
        self.assertTrue(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document_from_url(model_id="prebuilt-vaccinationCard")'))

    def test_positive_076(self):
        self.assertTrue(source_evidence('import azure.ai.formrecognizer as az\naz.DocumentAnalysisClient()\nx.begin_analyze_document_from_url("prebuilt-vaccinationCard")'))

    def test_positive_077(self):
        self.assertTrue(source_evidence('import azure.ai.documentintelligence\nazure.ai.documentintelligence.DocumentIntelligenceClient()\nx.begin_analyze_document("prebuilt-vaccinationCard")'))

    def test_negative_000(self):
        self.assertEqual(source_evidence('import mindee'), [])

    def test_negative_001(self):
        self.assertEqual(source_evidence('import veryfi'), [])

    def test_negative_002(self):
        self.assertEqual(source_evidence('import azure.ai.documentintelligence'), [])

    def test_negative_003(self):
        self.assertEqual(source_evidence('import google.cloud.documentai'), [])

    def test_negative_004(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()'), [])

    def test_negative_005(self):
        self.assertEqual(source_evidence('extract_vaccination_card()'), [])

    def test_negative_006(self):
        self.assertEqual(source_evidence('x.extract_vaccination_card'), [])

    def test_negative_007(self):
        self.assertEqual(source_evidence('"x.extract_vaccination_card()"'), [])

    def test_negative_008(self):
        self.assertEqual(source_evidence('# x.extract_vaccination_card()'), [])

    def test_negative_009(self):
        self.assertEqual(source_evidence('this is invalid syntax !'), [])

    def test_negative_010(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.InvoiceV4)'), [])

    def test_negative_011(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.ReceiptV5)'), [])

    def test_negative_012(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PassportV1)'), [])

    def test_negative_013(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.FinancialDocumentV1)'), [])

    def test_negative_014(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BankCheckV1)'), [])

    def test_negative_015(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BankAccountDetailsV2)'), [])

    def test_negative_016(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PayslipV2)'), [])

    def test_negative_017(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.PayslipV3)'), [])

    def test_negative_018(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.HealthcareCardV1)'), [])

    def test_negative_019(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BusinessCardV1)'), [])

    def test_negative_020(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.CustomV1)'), [])

    def test_negative_021(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.GeneratedV1)'), [])

    def test_negative_022(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.BillOfLadingV1)'), [])

    def test_negative_023(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.ResumeV1)'), [])

    def test_negative_024(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.DeliveryNoteV1)'), [])

    def test_negative_025(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.DriverLicenseV1)'), [])

    def test_negative_026(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.IdCardV1)'), [])

    def test_negative_027(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.InternationalIdV2)'), [])

    def test_negative_028(self):
        self.assertEqual(source_evidence('import mindee\nc=mindee.Client()\nc.parse(product.CarteGriseV1)'), [])

    def test_negative_029(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-invoice')"), [])

    def test_negative_030(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-receipt')"), [])

    def test_negative_031(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-layout')"), [])

    def test_negative_032(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-read')"), [])

    def test_negative_033(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-idDocument')"), [])

    def test_negative_034(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-check.us')"), [])

    def test_negative_035(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-tax.us')"), [])

    def test_negative_036(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-bankStatement.us')"), [])

    def test_negative_037(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-payStub.us')"), [])

    def test_negative_038(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-healthInsuranceCard.us')"), [])

    def test_negative_039(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-businessCard')"), [])

    def test_negative_040(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-creditCard')"), [])

    def test_negative_041(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-contract')"), [])

    def test_negative_042(self):
        self.assertEqual(source_evidence("x.begin_analyze_document('prebuilt-mortgage.us.1003')"), [])

    def test_negative_043(self):
        self.assertEqual(source_evidence('veryfi.Client()'), [])

    def test_negative_044(self):
        self.assertEqual(source_evidence('azure.DocumentIntelligenceClient()'), [])

    def test_negative_045(self):
        self.assertEqual(source_evidence('x.process_any_document()'), [])

    def test_negative_046(self):
        self.assertEqual(source_evidence('x.process_any_document_url()'), [])

    def test_negative_047(self):
        self.assertEqual(source_evidence('x.process_document()'), [])

    def test_negative_048(self):
        self.assertEqual(source_evidence('x.process_document_url()'), [])

    def test_negative_049(self):
        self.assertEqual(source_evidence('x.process_w2_document()'), [])

    def test_negative_050(self):
        self.assertEqual(source_evidence('x.process_w9_document()'), [])

    def test_negative_051(self):
        self.assertEqual(source_evidence('x.process_w8_document()'), [])

    def test_negative_052(self):
        self.assertEqual(source_evidence('x.process_check()'), [])

    def test_negative_053(self):
        self.assertEqual(source_evidence('x.process_check_url()'), [])

    def test_negative_054(self):
        self.assertEqual(source_evidence('x.process_check_with_remittance()'), [])

    def test_negative_055(self):
        self.assertEqual(source_evidence('x.process_bank_statement_document()'), [])

    def test_negative_056(self):
        self.assertEqual(source_evidence('x.process_bussines_card_document()'), [])

    def test_negative_057(self):
        self.assertEqual(source_evidence('x.classify_document()'), [])

    def test_negative_058(self):
        self.assertEqual(source_evidence('x.get_business_cards()'), [])

    def test_negative_059(self):
        self.assertEqual(source_evidence('x.process_energy_bill_document()'), [])

    def test_negative_060(self):
        self.assertEqual(source_evidence('x.batch_process_documents()'), [])

    def test_negative_061(self):
        self.assertEqual(source_evidence('x.analyze_document()'), [])

    def test_negative_062(self):
        self.assertEqual(source_evidence('x.analyze_expense()'), [])

    def test_negative_063(self):
        self.assertEqual(source_evidence('x.analyze_id()'), [])

    def test_negative_064(self):
        self.assertEqual(source_evidence('x.start_document_analysis()'), [])

    def test_negative_065(self):
        self.assertEqual(source_evidence('x.get_expense_analysis()'), [])

    def test_negative_066(self):
        self.assertEqual(source_evidence('x.extract_text()'), [])

    def test_negative_067(self):
        self.assertEqual(source_evidence('x.image_to_string()'), [])

    def test_negative_068(self):
        self.assertEqual(source_evidence('x.read_csv()'), [])

    def test_negative_069(self):
        self.assertEqual(source_evidence('x.read_excel()'), [])

    def test_negative_070(self):
        self.assertEqual(source_evidence('x.read_pdf()'), [])

    def test_negative_071(self):
        self.assertEqual(source_evidence('x.convert_into()'), [])

    def test_negative_072(self):
        self.assertEqual(source_evidence('x.extract_table()'), [])

    def test_negative_073(self):
        self.assertEqual(source_evidence('x.extract_tables()'), [])

    def test_negative_074(self):
        self.assertEqual(source_evidence('x.find_tables()'), [])

    def test_negative_075(self):
        self.assertEqual(source_evidence('x.find_table()'), [])

    def test_negative_076(self):
        self.assertEqual(source_evidence('x.get_meter_reading()'), [])

    def test_negative_077(self):
        self.assertEqual(source_evidence('requests.post("https://api.veryfi.com/api/v8/partner/documents")'), [])

    def test_negative_078(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/invoice_parser/affinda"})'), [])

    def test_negative_079(self):
        self.assertEqual(source_evidence('x.post("universal-ai", json={"model":"ocr/resume_parser/affinda"})'), [])

    def test_negative_080(self):
        self.assertEqual(source_evidence('LlamaParse().parse("file")'), [])

    def test_negative_081(self):
        self.assertEqual(source_evidence('nanonets.ocr(model_id="opaque")'), [])

    def test_negative_082(self):
        self.assertEqual(source_evidence('docsumo.upload("file")'), [])

    def test_negative_083(self):
        self.assertEqual(source_evidence('mindee.ClientV2().enqueue_and_parse(model_id="opaque")'), [])

    def test_negative_084(self):
        self.assertEqual(source_evidence('re.search("total", text)'), [])

    def test_negative_085(self):
        self.assertEqual(source_evidence('str.parse("vaccination card")'), [])

    def test_negative_086(self):
        self.assertEqual(source_evidence('subprocess.run(["mindee", "parse"])'), [])

    def test_negative_087(self):
        self.assertEqual(source_evidence('subprocess.run(["veryfi", "process"])'), [])

    def test_negative_088(self):
        self.assertEqual(source_evidence('def extract_vaccination_card(): pass\nx.extract_vaccination_card()'), [])

    def test_negative_089(self):
        self.assertEqual(source_evidence('from p import extract_vaccination_card as e\ne = other\ne()'), [])

    def test_negative_090(self):
        self.assertEqual(source_evidence('from p import extract_vaccination_card as e\ne: object = other\ne()'), [])

    def test_negative_091(self):
        self.assertEqual(source_evidence('from p import extract_vaccination_card as e\nwith context() as e:\n e()'), [])

    def test_negative_092(self):
        self.assertEqual(source_evidence('from p import extract_vaccination_card as e\nasync def f():\n async with context() as e:\n  e()'), [])

    def test_negative_093(self):
        self.assertEqual(source_evidence('import mindee\nclass Client: pass\nmindee.Client()\nx.parse(EnergyBillV1)'), [])

    def test_negative_094(self):
        self.assertEqual(source_evidence('from p import extract_vaccination_card\nclass X:\n def extract_vaccination_card(self): pass\nx.extract_vaccination_card()'), [])

    def test_negative_095(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-invoice')"), [])

    def test_negative_096(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-receipt')"), [])

    def test_negative_097(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-layout')"), [])

    def test_negative_098(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-read')"), [])

    def test_negative_099(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-idDocument')"), [])

    def test_negative_100(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-check.us')"), [])

    def test_negative_101(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-tax.us')"), [])

    def test_negative_102(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-bankStatement.us')"), [])

    def test_negative_103(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-payStub.us')"), [])

    def test_negative_104(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-healthInsuranceCard.us')"), [])

    def test_negative_105(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-businessCard')"), [])

    def test_negative_106(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-creditCard')"), [])

    def test_negative_107(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-contract')"), [])

    def test_negative_108(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-mortgage.us.1003')"), [])

    def test_negative_109(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('other')"), [])

    def test_negative_110(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client().parse(product.EnergyBillV1)'), [])

    def test_negative_111(self):
        self.assertEqual(source_evidence('affinda.create_document(collection="opaque")'), [])

    def test_negative_112(self):
        self.assertEqual(source_evidence('pdf4me.ai_vaccination_card_parser()'), [])

    def test_negative_113(self):
        self.assertEqual(source_evidence('abbyy.run(skill="opaque")'), [])

    def test_negative_114(self):
        self.assertEqual(source_evidence('rossum.run(queue="opaque")'), [])

    def test_negative_115(self):
        self.assertEqual(source_evidence('klippa.run(template="opaque")'), [])

    def test_negative_116(self):
        self.assertEqual(source_evidence('parseur.run(template="opaque")'), [])

    def test_negative_117(self):
        self.assertEqual(source_evidence('extend.run(workflow="opaque")'), [])

    def test_negative_118(self):
        self.assertEqual(source_evidence('veryfi.process_vaccination_card_document()'), [])

    def test_negative_119(self):
        self.assertEqual(source_evidence('veryfi.process_vaccination_card_document_url()'), [])

    def test_negative_120(self):
        self.assertEqual(source_evidence('subprocess.run(["az", "analyze"])'), [])

    def test_negative_121(self):
        self.assertEqual(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\ndef DocumentIntelligenceClient(): pass\nx.begin_analyze_document("prebuilt-vaccinationCard")'), [])

    def test_every_phrase_individually(self):
        for phrase in EXPECTED_POS:
            with self.subTest(phrase=phrase):
                self.assertEqual([m[0] for m in match_phrases(phrase)[0]], [phrase])
        for phrase in EXPECTED_NEG:
            with self.subTest(phrase=phrase):
                yes, no = match_phrases(phrase)
                self.assertEqual(yes, [])
                self.assertEqual([m[0] for m in no], [phrase])

    def test_readme_only_self_audit(self):
        readme = Path(__file__).resolve().parents[1] / 'README.md'
        self.assertEqual(audit(self.repo({'README.md': readme.read_text()}))['verdict'], 'PASS')

    def test_missed_wording(self):
        for phrase in ('vaccination record extraction', 'extract vaccination records',
                       'immunization record extraction', 'immunization card extraction',
                       'vaccination certificate extraction', 'extract vaccination certificates',
                       'vaccination card verification', 'proof of vaccination extraction',
                       'extract text from vaccination card', 'vaccination card template',
                       'vaccination card form', 'vaccination card tracking'):
            with self.subTest(phrase=phrase):
                self.assertEqual(match_phrases(phrase), ([], []))

    def test_specific_rejection_0(self):
        self.assertEqual(source_evidence('import azure.ai.formrecognizer'), [])

    def test_specific_rejection_1(self):
        self.assertEqual(source_evidence('from azure.ai.documentintelligence import DocumentIntelligenceClient\nDocumentIntelligenceClient()'), [])

    def test_specific_rejection_2(self):
        self.assertEqual(source_evidence('import mindee\nmindee.Client().parse(product.CarteGriseV1)'), [])

    def test_specific_rejection_3(self):
        self.assertEqual(source_evidence('from google.cloud import documentai\ndocumentai.DocumentProcessorServiceClient().process_document(request={})'), [])

    def test_specific_rejection_4(self):
        self.assertEqual(source_evidence('import boto3\nboto3.client("textract").analyze_document(QueriesConfig={"Queries": [{"Text": "What is Vaccination Status?"}]})'), [])

    def test_specific_rejection_5(self):
        self.assertEqual(source_evidence('from pyzbar.pyzbar import decode\ndecode(card)'), [])

    def test_specific_rejection_6(self):
        self.assertEqual(source_evidence('import pdfplumber\npdfplumber.open("card.pdf").pages[0].extract_text()'), [])

    def test_specific_rejection_7(self):
        self.assertEqual(source_evidence('import pytesseract\npytesseract.image_to_string(card)'), [])

    def test_specific_rejection_8(self):
        self.assertEqual(source_evidence('import pandas\npandas.read_csv("card.csv")'), [])

    def test_specific_rejection_9(self):
        self.assertEqual(source_evidence('import camelot\ncamelot.read_pdf("card.pdf")'), [])

    def test_specific_rejection_10(self):
        self.assertEqual(source_evidence('import tabula\ntabula.read_pdf("card.pdf")'), [])

    def test_specific_rejection_11(self):
        self.assertEqual(source_evidence('import pdfplumber\npdfplumber.open("card.pdf").pages[0].extract_table()'), [])

    def test_specific_rejection_12(self):
        self.assertEqual(source_evidence('import re\ntext = page.extract_text()\nfields = {"name": re.search("Name: (.*)", text)}'), [])

    def test_specific_rejection_13(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-marriageCertificate.us')"), [])

    def test_specific_rejection_14(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-vaccinationCard.us')"), [])

    def test_specific_rejection_15(self):
        self.assertEqual(source_evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nC()\nx.begin_analyze_document('prebuilt-vaccinationcard')"), [])
