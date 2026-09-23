import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from app.services import brand_kit


class TestBrandKit(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_dir = brand_kit.BRAND_KITS_DIR
        brand_kit.BRAND_KITS_DIR = self.test_dir

    def tearDown(self):
        brand_kit.BRAND_KITS_DIR = self.orig_dir
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_load_brand_kit(self):
        data = {
            "brand_name": "TestCorp",
            "colors": {"primary": "#ff0000"},
            "tagline": "Innovative testing",
        }
        saved_path = brand_kit.save_brand_kit("test_brand", data)
        self.assertTrue(os.path.exists(saved_path))

        loaded = brand_kit.load_brand_kit("test_brand")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["brand_name"], "TestCorp")
        self.assertEqual(loaded["colors"]["primary"], "#ff0000")

        all_kits = brand_kit.list_brand_kits()
        self.assertEqual(len(all_kits), 1)

        deleted = brand_kit.delete_brand_kit("test_brand")
        self.assertTrue(deleted)
        self.assertIsNone(brand_kit.load_brand_kit("test_brand"))

    @patch("requests.get")
    def test_extract_brand_from_url_mocked(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <html>
            <head>
                <title>Acme Innovations - Build Faster</title>
                <meta name="description" content="Acme builds cutting edge AI solutions." />
                <meta property="og:image" content="https://acme.com/assets/logo.png" />
                <style>
                    :root { --main-color: #3b82f6; }
                    body { color: #10b981; }
                </style>
            </head>
            <body>
                <h1>Welcome to Acme</h1>
            </body>
        </html>
        """
        mock_get.return_value = mock_resp

        result = brand_kit.extract_brand_from_url("https://acme.com")
        self.assertIn("Acme", result["brand_name"])
        self.assertIn("cutting edge", result["tagline"])
        self.assertIn("logo.png", result["logo_url"])
        self.assertIn("#3b82f6", [result["colors"]["primary"], result["colors"].get("secondary")])


if __name__ == "__main__":
    unittest.main()
