import os
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from PIL import Image

from app.models.schema import VideoAspect
from app.services import image_generator, material, video


class TestSequenceMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_model_catalogs_contain_imagineart_suite(self):
        img_models = [m[1] for m in image_generator.KIE_IMAGE_MODELS]
        self.assertIn("google/nano-banana-pro", img_models)
        self.assertIn("google/nano-banana", img_models)
        self.assertIn("bytedance/seedream-5-0-pro", img_models)
        self.assertIn("gpt-image-2.5", img_models)
        self.assertIn("imagineart-2-0", img_models)

        vid_models = [m[1] for m in material.KIE_VIDEO_MODELS]
        self.assertIn("bytedance/seedance-2-5", vid_models)
        self.assertIn("minimax/hailuo-01", vid_models)
        self.assertIn("kling-3-0", vid_models)
        self.assertIn("google/omni-flash", vid_models)

    def test_encode_image_to_data_uri(self):
        # Create a sample test image
        img_path = os.path.join(self.test_dir, "sample.png")
        img = Image.new("RGB", (64, 64), color="red")
        img.save(img_path)

        data_uri = image_generator.encode_image_to_data_uri(img_path)
        self.assertTrue(data_uri.startswith("data:image/png;base64,"))
        self.assertTrue(len(data_uri) > 50)

        # Passthrough test for existing URIs
        self.assertEqual(
            image_generator.encode_image_to_data_uri("https://example.com/image.jpg"),
            "https://example.com/image.jpg",
        )

    def test_extract_last_frame(self):
        # Test nonexistent file returns empty string gracefully
        res = video.extract_last_frame(os.path.join(self.test_dir, "nonexistent.mp4"))
        self.assertEqual(res, "")

    @patch("requests.post")
    @patch("requests.get")
    def test_kie_video_on_demand_chained_sequence(self, mock_get, mock_post):
        # Mock createTask response
        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 200
        mock_post_resp.json.return_value = {"code": 200, "data": {"taskId": "task-test-123"}}
        mock_post.return_value = mock_post_resp

        # Mock recordInfo response
        mock_get_resp = MagicMock()
        mock_get_resp.status_code = 200
        mock_get_resp.json.return_value = {
            "code": 200,
            "data": {"state": "success", "result": {"video_url": "https://example.com/v.mp4"}},
        }
        mock_get.return_value = mock_get_resp

        # Mock save_video and extract_last_frame
        dummy_clip = os.path.join(self.test_dir, "clip.mp4")
        with open(dummy_clip, "wb") as f:
            f.write(b"dummy mp4 content")

        dummy_frame = os.path.join(self.test_dir, "frame.jpg")
        with open(dummy_frame, "wb") as f:
            f.write(b"dummy frame")

        with patch("app.services.material.save_video", return_value=dummy_clip), \
             patch("app.services.material.extract_last_frame", return_value=dummy_frame), \
             patch("app.config.config.app.get", side_effect=lambda k, d="": "mock_api_key" if k == "kie_api_key" else d):

            paths = material._download_videos_kie_video_on_demand(
                task_id="test_task",
                search_terms=["scene 1 prompt", "scene 2 prompt"],
                video_aspect=VideoAspect.portrait,
                audio_duration=10.0,
                max_clip_duration=5,
                material_directory=self.test_dir,
                sequence_memory_mode="chained",
                scene_models={0: "bytedance/seedance-2-5", 1: "kling-3-0"},
            )

            self.assertEqual(len(paths), 2)
            # Verify mock_post was called with distinct models
            self.assertEqual(mock_post.call_count, 2)
            first_call_body = mock_post.call_args_list[0][1]["json"]
            second_call_body = mock_post.call_args_list[1][1]["json"]

            self.assertEqual(first_call_body["model"], "bytedance/seedance-2-5")
            self.assertEqual(second_call_body["model"], "kling-3-0")
            # In chained mode, scene 2 receives the start frame from scene 1
            self.assertIn("image_url", second_call_body["input"])


if __name__ == "__main__":
    unittest.main()
