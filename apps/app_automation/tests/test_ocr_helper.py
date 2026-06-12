from tempfile import TemporaryDirectory
from unittest import mock

from django.test import SimpleTestCase
import numpy as np

from apps.app_automation.utils.ocr_helper import OCRHelper, OCRRuntimeError


class OCRHelperLocalModelTests(SimpleTestCase):
    def setUp(self):
        OCRHelper._easyocr_reader = None
        OCRHelper._easyocr_reader_config = None

    def tearDown(self):
        OCRHelper._easyocr_reader = None
        OCRHelper._easyocr_reader_config = None

    def test_get_easyocr_reader_uses_project_local_model_dir_and_disables_download(self):
        helper = OCRHelper(languages=['ch_sim', 'en'], use_gpu=False)

        with mock.patch.object(helper, 'ensure_local_models_ready') as mock_ensure:
            with mock.patch('apps.app_automation.utils.ocr_helper.easyocr.Reader') as mock_reader:
                fake_reader = mock.Mock()
                mock_reader.return_value = fake_reader

                reader = helper.get_easyocr_reader(
                    helper.languages,
                    helper.use_gpu,
                    model_storage_directory=helper.model_storage_directory,
                    download_enabled=helper.download_enabled,
                    detect_network=helper.detect_network,
                )

        self.assertIs(reader, fake_reader)
        mock_ensure.assert_called_once_with(
            helper.languages,
            helper.model_storage_directory,
            helper.detect_network,
        )
        mock_reader.assert_called_once_with(
            ['ch_sim', 'en'],
            gpu=False,
            model_storage_directory=helper.model_storage_directory,
            download_enabled=False,
            detect_network='craft',
        )

    def test_ensure_local_models_ready_raises_clear_error_when_models_missing(self):
        with TemporaryDirectory() as temp_dir:
            helper = OCRHelper(
                languages=['ch_sim', 'en'],
                use_gpu=False,
                model_storage_directory=temp_dir,
            )

            with self.assertRaisesRegex(OCRRuntimeError, r'craft_mlt_25k\.pth'):
                helper.ensure_local_models_ready(
                    helper.languages,
                    helper.model_storage_directory,
                    helper.detect_network,
                )

    @mock.patch('apps.app_automation.utils.ocr_helper.G')
    def test_find_text_supports_negative_index_for_last_candidate(self, mock_global_device):
        helper = OCRHelper(languages=['ch_sim', 'en'], use_gpu=False)
        mock_global_device.DEVICE.snapshot.return_value = np.zeros((40, 40, 3), dtype=np.uint8)

        with mock.patch.object(helper, 'recognize_with_boxes', return_value=[
            {
                'text': '交易登录',
                'confidence': 0.99,
                'bbox': [(100, 300), (300, 300), (300, 360), (100, 360)],
                'center': (200, 330),
            },
            {
                'text': '交易登录',
                'confidence': 0.98,
                'bbox': [(140, 1760), (940, 1760), (940, 1880), (140, 1880)],
                'center': (540, 1820),
            },
        ]):
            match = helper.find_text('交易登录', match_mode='contains', index=-1)

        self.assertIsNotNone(match)
        self.assertEqual(match['center'], (540, 1820))
