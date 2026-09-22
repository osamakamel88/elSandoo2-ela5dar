import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from app.models.schema import VideoAspect
from app.services import image_generator


class TestImageGenerator(unittest.TestCase):
    def test_resolve_aspect_ratio_string(self):
        self.assertEqual(image_generator.resolve_aspect_ratio_string(VideoAspect.portrait), "9:16")
        self.assertEqual(image_generator.resolve_aspect_ratio_string(VideoAspect.landscape), "16:9")
        self.assertEqual(image_generator.resolve_aspect_ratio_string(VideoAspect.square), "1:1")
        self.assertEqual(image_generator.resolve_aspect_ratio_string("9:16"), "9:16")
        self.assertEqual(image_generator.resolve_aspect_ratio_string("16:9"), "16:9")

    def test_resolve_pixel_dimensions(self):
        w, h = image_generator.resolve_pixel_dimensions(VideoAspect.portrait, quality="standard")
        self.assertEqual((w, h), (720, 1280))
        w_hd, h_hd = image_generator.resolve_pixel_dimensions(VideoAspect.portrait, quality="hd")
        self.assertEqual((w_hd, h_hd), (1080, 1920))

        w_l, h_l = image_generator.resolve_pixel_dimensions(VideoAspect.landscape, quality="standard")
        self.assertEqual((w_l, h_l), (1280, 720))

    def test_apply_prompt_style(self):
        prompt = "a majestic mountain"
        style = "cinematic, 8k, photorealistic"
        styled = image_generator._apply_prompt_style(prompt, style)
        self.assertEqual(styled, "a majestic mountain, cinematic, 8k, photorealistic")

        raw = image_generator._apply_prompt_style(prompt, "")
        self.assertEqual(raw, "a majestic mountain")

    @patch("requests.get")
    def test_generate_image_pollinations(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = b"fake-pollinations-image-bytes"
        mock_get.return_value = mock_resp

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = image_generator.generate_image_pollinations(
                prompt="futuristic city",
                model="flux",
                aspect=VideoAspect.portrait,
                output_dir=tmp_dir,
            )
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "rb") as f:
                self.assertEqual(f.read(), b"fake-pollinations-image-bytes")

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_image_kie(self, mock_get, mock_post):
        # Mock task creation
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"data": {"taskId": "task-test-123"}}
        mock_post.return_value = mock_post_resp

        # Mock polling & image download
        mock_query_resp = MagicMock()
        mock_query_resp.status_code = 200
        mock_query_resp.json.return_value = {
            "data": {
                "state": "success",
                "result": {"url": "https://fake.kie.ai/image.png"},
            }
        }
        mock_dl_resp = MagicMock()
        mock_dl_resp.status_code = 200
        mock_dl_resp.content = b"fake-kie-image-bytes"

        mock_get.side_effect = [mock_query_resp, mock_dl_resp]

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = image_generator.generate_image_kie(
                prompt="cyberpunk samurai",
                model="flux-kontext-pro",
                aspect=VideoAspect.portrait,
                output_dir=tmp_dir,
                api_key="test-kie-key",
            )
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "rb") as f:
                self.assertEqual(f.read(), b"fake-kie-image-bytes")

    @patch("requests.post")
    @patch("requests.get")
    def test_generate_image_openai(self, mock_get, mock_post):
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {
            "data": [{"url": "https://fake.openai.com/image.png"}]
        }
        mock_post.return_value = mock_post_resp

        mock_dl_resp = MagicMock()
        mock_dl_resp.status_code = 200
        mock_dl_resp.content = b"fake-openai-image-bytes"
        mock_get.return_value = mock_dl_resp

        with tempfile.TemporaryDirectory() as tmp_dir:
            out_file = image_generator.generate_image_openai(
                prompt="golden retriever in park",
                model="dall-e-3",
                aspect=VideoAspect.portrait,
                output_dir=tmp_dir,
                api_key="test-openai-key",
            )
            self.assertTrue(os.path.exists(out_file))
            with open(out_file, "rb") as f:
                self.assertEqual(f.read(), b"fake-openai-image-bytes")


if __name__ == "__main__":
    unittest.main()
