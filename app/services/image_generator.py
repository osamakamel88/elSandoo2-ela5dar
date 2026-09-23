import base64
import mimetypes
import os
import time
import urllib.parse
import uuid
from typing import Optional, Dict, Any, List
from loguru import logger
import requests
from PIL import Image

from app.config import config
from app.models.schema import VideoAspect
from app.utils import utils

# Supported Image Models Catalog (ImagineArt & Kie.ai Suite)
KIE_IMAGE_MODELS = [
    ("Nano Banana Pro (Google) [HOT]", "google/nano-banana-pro"),
    ("Nano Banana 2 (Google)", "google/nano-banana"),
    ("ByteDance Seedream V5 Pro [NEW]", "bytedance/seedream-5-0-pro"),
    ("ByteDance Seedream 4.0", "bytedance/seedream-4-0"),
    ("GPT Image 2.5 Sunburst [NEW]", "gpt-image-2.5"),
    ("ImagineArt 2.0 [BEST]", "imagineart-2-0"),
    ("Grok Imagine 2.0 (xAI)", "grok-imagine"),
    ("Flux Kontext Pro (Ultra Realistic)", "flux-kontext-pro"),
    ("Flux 2 Pro", "flux-2/pro-text-to-image"),
    ("Flux 2 Flex", "flux-2/flex-text-to-image"),
]

POLLINATIONS_IMAGE_MODELS = [
    ("Flux (Default)", "flux"),
    ("Flux Realism (Photorealistic)", "flux-realism"),
    ("Midjourney Style", "midjourney"),
    ("Flux Anime", "flux-anime"),
    ("Flux 3D (Pixar/CGI)", "flux-3d"),
    ("Turbo (Super Fast)", "turbo"),
]

OPENAI_IMAGE_MODELS = [
    ("DALL-E 3 (High Definition)", "dall-e-3"),
    ("DALL-E 2", "dall-e-2"),
]

STYLE_PRESETS = [
    ("None (Raw Prompt)", ""),
    ("Cinematic Photorealistic", "cinematic photography, 8k, highly detailed, photorealistic, dramatic lighting, 35mm lens"),
    ("Digital Art / Concept Art", "detailed digital art, artstation trending, vibrant colors, cinematic composition"),
    ("Anime / Studio Ghibli", "anime aesthetic, studio ghibli style, vibrant colors, detailed scenery"),
    ("3D CGI / Pixar Style", "3d render, octane render, smooth lighting, pixar style, vibrant, high detail"),
    ("Cyberpunk / Neon", "cyberpunk aesthetic, neon lighting, futuristic city, dark atmosphere, highly detailed"),
    ("Vintage Film (35mm Kodak)", "vintage 35mm photograph, kodak portra 400, grainy, film aesthetic, nostalgic lighting"),
    ("Oil Painting / Fine Art", "classical oil painting, textured brush strokes, masterpiece, museum lighting"),
]


def resolve_aspect_ratio_string(aspect: VideoAspect | str) -> str:
    """Returns aspect ratio string like '9:16', '16:9', or '1:1'."""
    val = getattr(aspect, "value", aspect)
    if val in ("portrait", "9:16", "竖屏 9:16"):
        return "9:16"
    elif val in ("landscape", "16:9", "横屏 16:9"):
        return "16:9"
    elif val in ("square", "1:1", "方形 1:1"):
        return "1:1"
    return "9:16"


def resolve_pixel_dimensions(aspect: VideoAspect | str, quality: str = "standard") -> tuple[int, int]:
    """Returns width, height for standard or HD quality."""
    ar = resolve_aspect_ratio_string(aspect)
    if quality == "hd":
        if ar == "9:16":
            return (1080, 1920)
        elif ar == "16:9":
            return (1920, 1080)
        else:
            return (1080, 1080)
    else:
        if ar == "9:16":
            return (720, 1280)
        elif ar == "16:9":
            return (1280, 720)
        else:
            return (768, 768)


def _apply_prompt_style(prompt: str, style: str) -> str:
    prompt = prompt.strip()
    if not style:
        return prompt
    return f"{prompt}, {style.strip()}"


def encode_image_to_data_uri(image_path: str) -> str:
    """
    Encodes a local image file to a base64 Data URI (e.g. data:image/png;base64,...).
    If already a URL or data URI, returns it directly.
    """
    if not image_path:
        return ""
    if image_path.startswith("data:") or image_path.startswith("http://") or image_path.startswith("https://"):
        return image_path
    if not os.path.exists(image_path):
        return ""
    mime_type, _ = mimetypes.guess_type(image_path)
    if not mime_type:
        mime_type = "image/png"
    try:
        with open(image_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"
    except Exception as e:
        logger.warning(f"Failed to encode image {image_path} to data URI: {e}")
        return ""


def generate_image_pollinations(
    prompt: str,
    model: str = "flux",
    aspect: VideoAspect | str = "9:16",
    quality: str = "standard",
    output_dir: str = "",
    seed: Optional[int] = None,
) -> str:
    """
    Generate an image using Pollinations AI (free, zero API key required).
    """
    width, height = resolve_pixel_dimensions(aspect, quality)
    clean_prompt = urllib.parse.quote(prompt.strip())
    model_name = model or "flux"
    
    url = f"https://image.pollinations.ai/prompt/{clean_prompt}?model={model_name}&width={width}&height={height}&nologo=true"
    if seed is not None:
        url += f"&seed={seed}"

    logger.info(f"[Pollinations] Requesting image: model={model_name}, size={width}x{height}")
    response = requests.get(url, proxies=config.proxy, timeout=(15, 60))
    if response.status_code != 200:
        raise RuntimeError(f"Pollinations image generation failed with HTTP {response.status_code}")

    if not output_dir:
        output_dir = utils.storage_dir("local_videos")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"gen_pollinations_{uuid.uuid4().hex[:10]}.png"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "wb") as f:
        f.write(response.content)

    logger.success(f"[Pollinations] Saved image to {filepath}")
    return filepath


def generate_image_kie(
    prompt: str,
    model: str = "flux-kontext-pro",
    aspect: VideoAspect | str = "9:16",
    quality: str = "standard",
    output_dir: str = "",
    api_key: str = "",
    start_frame: Optional[str] = None,
) -> str:
    """
    Generate an image using Kie.ai task API (/api/v1/jobs/createTask & recordInfo).
    Uses the user's Kie.ai credits. Supports start_frame image conditioning.
    """
    effective_api_key = (api_key or config.app.get("kie_api_key", "")).strip()
    if not effective_api_key:
        raise ValueError("Kie.ai API key is required. Please set it in Basic Settings -> Kie.ai.")

    aspect_ratio_str = resolve_aspect_ratio_string(aspect)
    resolution = "2K" if quality == "hd" else "1K"
    model_id = model or "flux-kontext-pro"

    headers = {
        "Authorization": f"Bearer {effective_api_key}",
        "Content-Type": "application/json",
    }
    input_data: Dict[str, Any] = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio_str,
        "resolution": resolution,
    }
    if start_frame:
        ref_uri = encode_image_to_data_uri(start_frame)
        if ref_uri:
            input_data["image_url"] = ref_uri
            input_data["input_image"] = ref_uri
            input_data["image"] = ref_uri
            input_data["first_frame"] = ref_uri
            logger.info(f"[Kie.ai] Added start_frame conditioning: {start_frame[:60]}")

    payload = {
        "model": model_id,
        "input": input_data,
    }

    logger.info(f"[Kie.ai] Submitting image task: model={model_id}, aspect={aspect_ratio_str}")
    submit_res = requests.post(
        "https://api.kie.ai/api/v1/jobs/createTask",
        json=payload,
        headers=headers,
        proxies=config.proxy,
        timeout=(15, 45),
    )
    if submit_res.status_code != 200:
        raise RuntimeError(f"Kie.ai image task creation failed with HTTP {submit_res.status_code}: {submit_res.text}")

    submit_json = submit_res.json()
    task_data = submit_json.get("data") if isinstance(submit_json, dict) else {}
    task_id = task_data.get("taskId") if isinstance(task_data, dict) else None
    if not task_id:
        task_id = submit_json.get("taskId")

    if not task_id:
        raise RuntimeError(f"Kie.ai task submission did not return a taskId: {submit_json}")

    logger.info(f"[Kie.ai] Task created: id={task_id}. Polling for result...")

    # Poll for completion (up to 3 minutes)
    deadline = time.monotonic() + 180.0
    image_url = ""
    while time.monotonic() < deadline:
        time.sleep(3.0)
        query_res = requests.get(
            f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}",
            headers=headers,
            proxies=config.proxy,
            timeout=(10, 30),
        )
        if query_res.status_code != 200:
            logger.warning(f"[Kie.ai] Polling returned HTTP {query_res.status_code}, retrying...")
            continue

        query_json = query_res.json()
        record_data = query_json.get("data") if isinstance(query_json, dict) else {}
        if not isinstance(record_data, dict):
            record_data = query_json

        state = str(record_data.get("state") or record_data.get("status") or "").lower()
        if state == "success":
            result = record_data.get("result") or record_data.get("output") or record_data.get("response")
            if isinstance(result, dict):
                image_url = result.get("url") or result.get("image_url") or result.get("images", [""])[0]
            elif isinstance(result, list) and result:
                image_url = result[0] if isinstance(result[0], str) else result[0].get("url", "")
            elif isinstance(result, str):
                image_url = result
            break
        elif state == "fail" or state == "failed":
            error_msg = record_data.get("failReason") or record_data.get("error") or "Generation failed"
            raise RuntimeError(f"Kie.ai image task {task_id} failed: {error_msg}")

    if not image_url:
        raise TimeoutError(f"Kie.ai image generation timed out for task {task_id}")

    logger.info(f"[Kie.ai] Downloading generated image from: {image_url}")
    img_resp = requests.get(image_url, proxies=config.proxy, timeout=(15, 60))
    if img_resp.status_code != 200:
        raise RuntimeError(f"Failed to download generated Kie.ai image from {image_url}")

    if not output_dir:
        output_dir = utils.storage_dir("local_videos")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"gen_kie_{uuid.uuid4().hex[:10]}.png"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_resp.content)

    logger.success(f"[Kie.ai] Saved image to {filepath}")
    return filepath


def generate_image_openai(
    prompt: str,
    model: str = "dall-e-3",
    aspect: VideoAspect | str = "9:16",
    quality: str = "standard",
    output_dir: str = "",
    api_key: str = "",
    base_url: str = "",
) -> str:
    """
    Generate an image using OpenAI DALL-E or custom OpenAI-compatible endpoint.
    """
    effective_api_key = (api_key or config.app.get("openai_api_key", "")).strip()
    if not effective_api_key:
        raise ValueError("OpenAI API key is required. Please set it in Basic Settings.")

    effective_base_url = (base_url or config.app.get("openai_base_url", "")).strip().rstrip("/")
    if not effective_base_url:
        effective_base_url = "https://api.openai.com/v1"

    ar = resolve_aspect_ratio_string(aspect)
    if model == "dall-e-3":
        size = "1024x1792" if ar == "9:16" else ("1792x1024" if ar == "16:9" else "1024x1024")
    else:
        size = "1024x1024"

    headers = {
        "Authorization": f"Bearer {effective_api_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": model or "dall-e-3",
        "prompt": prompt,
        "n": 1,
        "size": size,
    }
    if model == "dall-e-3" and quality == "hd":
        payload["quality"] = "hd"

    logger.info(f"[OpenAI] Requesting image: model={model}, size={size}")
    res = requests.post(
        f"{effective_base_url}/images/generations",
        json=payload,
        headers=headers,
        proxies=config.proxy,
        timeout=(20, 90),
    )
    if res.status_code != 200:
        raise RuntimeError(f"OpenAI image generation failed with HTTP {res.status_code}: {res.text}")

    res_json = res.json()
    data = res_json.get("data", [])
    if not data or not isinstance(data[0], dict):
        raise RuntimeError(f"OpenAI returned empty data: {res_json}")

    image_url = data[0].get("url")
    if not image_url:
        b64_json = data[0].get("b64_json")
        if b64_json:
            import base64
            img_bytes = base64.b64decode(b64_json)
        else:
            raise RuntimeError("No image URL or b64 data returned from OpenAI")
    else:
        dl_res = requests.get(image_url, proxies=config.proxy, timeout=(15, 60))
        img_bytes = dl_res.content

    if not output_dir:
        output_dir = utils.storage_dir("local_videos")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"gen_openai_{uuid.uuid4().hex[:10]}.png"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(img_bytes)

    logger.success(f"[OpenAI] Saved image to {filepath}")
    return filepath


def generate_scene_image(
    prompt: str,
    provider: str = "kie",
    model: str = "",
    aspect: VideoAspect | str = "9:16",
    style: str = "",
    quality: str = "standard",
    output_dir: str = "",
    api_key: str = "",
    base_url: str = "",
    start_frame: Optional[str] = None,
) -> str:
    """
    Unified entry point to generate a scene image with full customizability.
    Supports start_frame conditioning for visual continuity.
    """
    final_prompt = _apply_prompt_style(prompt, style)
    prov = (provider or "kie").lower()

    if prov == "pollinations":
        return generate_image_pollinations(
            prompt=final_prompt,
            model=model or "flux",
            aspect=aspect,
            quality=quality,
            output_dir=output_dir,
        )
    elif prov == "openai":
        return generate_image_openai(
            prompt=final_prompt,
            model=model or "dall-e-3",
            aspect=aspect,
            quality=quality,
            output_dir=output_dir,
            api_key=api_key,
            base_url=base_url,
        )
    else:  # default to Kie.ai
        return generate_image_kie(
            prompt=final_prompt,
            model=model or "flux-kontext-pro",
            aspect=aspect,
            quality=quality,
            output_dir=output_dir,
            api_key=api_key,
            start_frame=start_frame,
        )


def image_to_animated_clip(
    image_path: str,
    duration: float = 4.0,
    output_path: str = "",
    aspect: VideoAspect | str = "9:16",
) -> str:
    """
    Converts a static image into a smooth Ken-Burns dynamic zoom video clip (MP4).
    Uses MoviePy with CompositeVideoClip and safe resource cleanup.
    """
    from moviepy import ImageClip, CompositeVideoClip

    if not output_path:
        base, _ = os.path.splitext(image_path)
        output_path = f"{base}_clip.mp4"

    logger.info(f"Converting image {image_path} to animated {duration}s clip: {output_path}")

    clip = None
    final_clip = None
    try:
        clip = ImageClip(image_path).with_duration(duration).with_position("center")
        # Gentle dynamic zoom up to 115% for cinematic motion
        zoom_clip = clip.resized(lambda t: 1.0 + (0.15 * (t / max(duration, 0.1))))
        final_clip = CompositeVideoClip([zoom_clip])
        final_clip.write_videofile(
            output_path,
            fps=30,
            codec="libx264",
            audio=False,
            logger=None,
        )
        return output_path
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass
        if final_clip is not None:
            try:
                final_clip.close()
            except Exception:
                pass
