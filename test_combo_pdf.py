import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import helpers


EMBEDDED_PDF_PAGE = '''
<a class="button" href="#">Download PDF</a>
<script>
  AdobeDC.View({content: {location: {
    url: 'https://cdn.example.test/brewhouse_allergen_matrix.pdf'
  }}});
  const proxy = 'https://download.example.test/?file=https://cdn.example.test/brewhouse_allergen_matrix.pdf';
</script>
'''


class _Response:
    status_code = 200
    text = EMBEDDED_PDF_PAGE


class ComboPdfTests(unittest.TestCase):
    def test_downloads_pdf_url_embedded_in_a_script_when_button_has_no_url(self):
        # Catches PDF viewer pages whose visible button is href="#".
        with tempfile.TemporaryDirectory() as output_dir, \
             patch.object(helpers, 'create_folder', return_value=output_dir), \
             patch.object(helpers, 'UserAgent') as user_agent, \
             patch.object(helpers.requests, 'get', return_value=_Response()), \
             patch.object(helpers, 'PDFDownloader') as download:
            user_agent.return_value.random = 'test-agent'
            helpers.combo_PDFDownload('Brewhouse', 'https://example.test/allergens')

        download.assert_called_once_with(
            url='https://cdn.example.test/brewhouse_allergen_matrix.pdf',
            filePath=str(Path(output_dir) / 'brewhouse_allergen_matrix.pdf'),
        )

    def _run(self, responses):
        with tempfile.TemporaryDirectory() as output_dir, \
             patch.object(helpers, 'create_folder', return_value=output_dir), \
             patch.object(helpers, 'UserAgent') as user_agent, \
             patch.object(helpers, 'sleep') as sleep, \
             patch.object(helpers.requests, 'get', side_effect=responses) as get, \
             patch.object(helpers, 'PDFDownloader') as download:
            user_agent.return_value.random = 'test-agent'
            helpers.combo_PDFDownload('Brewhouse', 'https://example.test/allergens')
        return get, sleep, download

    def test_retries_a_429_then_downloads(self):
        # Catches the Cornish Bakery run where one 429 silently dropped the PDF.
        throttled = _Response()
        throttled.status_code, throttled.headers = 429, {'Retry-After': '7'}
        get, sleep, download = self._run([throttled, _Response()])

        self.assertEqual(get.call_count, 2)
        sleep.assert_called_once_with(7)
        download.assert_called_once()

    def test_gives_up_after_three_throttled_attempts(self):
        throttled = _Response()
        throttled.status_code, throttled.headers = 429, {}
        get, _, download = self._run([throttled] * 3)

        self.assertEqual(get.call_count, 3)
        download.assert_not_called()


if __name__ == '__main__':
    unittest.main()
