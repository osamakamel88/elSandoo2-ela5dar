import unittest
from unittest.mock import patch, MagicMock

from app.services import product_importer


class TestProductImporter(unittest.TestCase):
    def test_synthesize_product_script_arabic(self):
        info = {
            "title": "ثنائي Fresh & Flawless للعناية بالإبطين",
            "description": "مزيل عرق تفتيح البشرة ومزيل رائحة العرق الطبيعي",
            "price": "450",
            "currency": "EGP",
            "platform": "safiraworld.com",
            "features": ["طبيعي 100%", "يدوم 48 ساعة"],
        }
        script = product_importer.synthesize_product_script(
            product_info=info,
            theme_context="Viral TikTok / Reels Promo (مصر)",
            language="",
        )
        self.assertTrue(len(script) > 50)
        self.assertIn("Fresh & Flawless", script)
        self.assertIn("450", script)
        self.assertFalse(script.startswith("Error:"))

    def test_synthesize_product_script_english(self):
        info = {
            "title": "Wireless Noise Cancelling Earbuds Pro",
            "description": "Crystal clear sound with active noise cancellation",
            "price": "59.99",
            "currency": "USD",
            "platform": "Amazon",
            "features": ["Active Noise Cancellation", "36h Battery Life"],
        }
        script = product_importer.synthesize_product_script(
            product_info=info,
            theme_context="Viral TikTok / Reels Promo",
            language="en",
        )
        self.assertTrue(len(script) > 50)
        self.assertIn("Earbuds Pro", script)
        self.assertIn("59.99", script)
        self.assertFalse(script.startswith("Error:"))

    def test_synthesize_search_terms(self):
        info = {
            "title": "ثنائي Fresh & Flawless مزيل عرق تفتيح",
            "features": ["طبيعي 100%"],
        }
        terms = product_importer.synthesize_search_terms(info)
        self.assertTrue(len(terms) >= 3)
        self.assertTrue(any("skincare" in t or "beauty" in t or "deodorant" in t or "product" in t for t in terms))

    def test_generate_product_script_fallback_when_llm_errors(self):
        info = {
            "title": "سيروم العناية بالبشرة",
            "price": "300",
            "currency": "EGP",
            "features": ["ترطيب عميق"],
        }
        # Simulate LLM returning an error
        with patch("app.services.llm._generate_response", return_value="Error: Connection failed"):
            script = product_importer.generate_product_script(
                product_info=info,
                theme_context="إعلان تيك توك",
                language="",
            )
            self.assertTrue(len(script) > 40)
            self.assertFalse(script.startswith("Error:"))
            self.assertIn("سيروم العناية بالبشرة", script)


if __name__ == "__main__":
    unittest.main()
