import glob
import os
import shutil
import time
from typing import Any, Dict, List, Optional
from loguru import logger
import requests
import streamlit as st

from app.config import config
from app.models.schema import VideoAspect, VideoParams
from app.services import brand_kit, image_generator, material, video
from app.utils import utils


def switch_studio(mode_name: str):
    """Safely switches studio mode using pending switch before next render."""
    st.session_state["pending_studio_switch"] = mode_name
    st.session_state["ia_studio_mode"] = mode_name
    st.rerun(scope="app")


def render_studio_navigation() -> str:
    """
    Renders the modern ImagineArt Studio Switcher pills navigation bar.
    """
    modes = [
        ("auto_video", "⚡ Full-Auto Video Studio"),
        ("home", "🏠 Dashboard"),
        ("video", "🎬 Video Tools & Models"),
        ("image", "🎨 Image Tools & Models"),
        ("sequence", "🔗 Sequence Memory & Storyboard"),
        ("assets", "📦 All Assets Hub"),
        ("brand_kits", "🏷️ Brand Kits Studio"),
    ]
    mode_keys = [m[0] for m in modes]

    if "ia_studio_mode" not in st.session_state:
        st.session_state["ia_studio_mode"] = "auto_video"

    if "pending_studio_switch" in st.session_state:
        target = st.session_state.pop("pending_studio_switch")
        st.session_state["ia_studio_mode"] = target
        st.session_state["ia_studio_nav_pills"] = target
    elif "ia_studio_nav_pills" not in st.session_state:
        st.session_state["ia_studio_nav_pills"] = st.session_state.get("ia_studio_mode", "auto_video")

    def _sync_nav_pills():
        new_val = st.session_state.get("ia_studio_nav_pills")
        if new_val and new_val in mode_keys:
            st.session_state["ia_studio_mode"] = new_val
        else:
            # Prevent deselecting: keep active mode
            st.session_state["ia_studio_nav_pills"] = st.session_state.get("ia_studio_mode", "auto_video")

    selected = st.pills(
        "Studio Navigation",
        options=mode_keys,
        format_func=lambda k: dict(modes).get(k, k),
        key="ia_studio_nav_pills",
        on_change=_sync_nav_pills,
        label_visibility="collapsed",
    )

    if selected and selected in mode_keys:
        st.session_state["ia_studio_mode"] = selected

    return st.session_state.get("ia_studio_mode", "auto_video")


def _render_api_key_helper(provider_name: str = "kie"):
    """Inline API key configuration so users never get stuck in settings."""
    if provider_name == "kie":
        current_key = config.app.get("kie_api_key", "").strip()
        if not current_key:
            with st.container(border=True):
                st.warning("⚠️ **Kie.ai API Key Not Configured**")
                st.caption("Enter your Kie.ai API key to unlock cloud generation (Seedance 2.5, Nano Banana Pro, Kling 3.0), or use the Free Local Engine below.")
                k_col1, k_col2 = st.columns([3, 1])
                new_key = k_col1.text_input("Kie.ai API Key", type="password", placeholder="Enter Bearer API Key...", key="ia_inline_kie_key")
                if k_col2.button("💾 Save Key", key="ia_inline_save_kie_key"):
                    if new_key.strip():
                        config.app["kie_api_key"] = new_key.strip()
                        config.save_config()
                        st.success("Kie.ai API Key saved!")
                        st.rerun(scope="app")


def render_imagineart_home_dashboard():
    """
    ImagineArt Home Creative Studio Dashboard (matching screenshot media_1790159579464.png).
    """
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(34, 197, 94, 0.12) 0%, rgba(14, 165, 233, 0.08) 100%); 
                    border: 1px solid rgba(34, 197, 94, 0.25); border-radius: 18px; padding: 28px; margin-bottom: 24px;">
            <h2 style="margin: 0 0 8px 0; font-size: 2.2rem; font-weight: 800; color: #ffffff;">
                Imagine Anything with <span style="color: #22c55e;">elSandoo2 el a5dar</span>
            </h2>
            <p style="color: #94a3b8; font-size: 1.05rem; margin: 0 0 20px 0;">
                Next-generation creative studio powered by <b>Seedance 2.5</b>, <b>Nano Banana Pro</b>, 
                <b>MiniMax Hailuo</b>, and <b>Higgsfield Sequence Memory</b>.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Hero Quick Creation Bar
    with st.container(border=True):
        st.markdown("##### 🚀 Fast Creative Launch")
        hcol1, hcol2, hcol3 = st.columns([4, 1.2, 1.2])
        quick_prompt = hcol1.text_input(
            "Quick Prompt",
            placeholder="Describe what you want to create (e.g. Luxurious perfume bottle on black marble surrounded by golden sparks, cinematic 8k)",
            label_visibility="collapsed",
            key="home_quick_prompt",
        )
        quick_aspect = hcol2.selectbox(
            "Aspect",
            options=["9:16 (Portrait)", "16:9 (Landscape)", "1:1 (Square)"],
            index=0,
            label_visibility="collapsed",
            key="home_quick_aspect",
        )
        if hcol3.button("✨ Create Magic", use_container_width=True, type="primary", key="home_btn_create"):
            if quick_prompt.strip():
                st.session_state["ia_video_prompt"] = quick_prompt.strip()
                st.session_state["ia_image_prompt"] = quick_prompt.strip()
                switch_studio("video")
            else:
                st.warning("Please enter a creative prompt first.")

    st.markdown("### 🌟 Creative Studios & Tools")
    card_cols = st.columns(3)

    with card_cols[0]:
        with st.container(border=True):
            st.markdown("#### 🎬 Create Videos")
            st.markdown(
                "<span class='ia-badge ia-badge-new'>NEW</span> <b>ByteDance Seedance 2.5</b><br/>"
                "<span class='ia-badge ia-badge-hot'>HOT</span> <b>MiniMax Hailuo H3 Max</b><br/>"
                "<span class='ia-badge ia-badge-best'>BEST</span> <b>Kling 3.0 Pro</b>",
                unsafe_allow_html=True,
            )
            st.caption("Generate cinematic AI video footage from text or reference start frames.")
            if st.button("Launch Video Studio ➔", key="home_nav_vid", use_container_width=True):
                switch_studio("video")

    with card_cols[1]:
        with st.container(border=True):
            st.markdown("#### 🎨 Create Images")
            st.markdown(
                "<span class='ia-badge ia-badge-hot'>HOT</span> <b>Google Nano Banana Pro</b><br/>"
                "<span class='ia-badge ia-badge-new'>NEW</span> <b>ByteDance Seedream V5 Pro</b><br/>"
                "<span class='ia-badge ia-badge-new'>NEW</span> <b>GPT Image 2.5 Sunburst</b>",
                unsafe_allow_html=True,
            )
            st.caption("Photorealistic 8K image generation with style conditioning and face/product locking.")
            if st.button("Launch Image Studio ➔", key="home_nav_img", use_container_width=True):
                switch_studio("image")

    with card_cols[2]:
        with st.container(border=True):
            st.markdown("#### 🔗 Sequence Memory")
            st.markdown(
                "<span class='ia-badge ia-badge-best'>BEST</span> <b>Higgsfield Chaining</b><br/>"
                "<span class='ia-badge ia-badge-hot'>HOT</span> <b>Hero Keyframe Anchor</b><br/>"
                "<span class='ia-badge ia-badge-new'>NEW</span> <b>Multi-Scene Storyboard</b>",
                unsafe_allow_html=True,
            )
            st.caption("Maintain seamless visual continuity across multiple scenes with end-to-start frame chaining.")
            if st.button("Open Storyboard ➔", key="home_nav_seq", use_container_width=True):
                switch_studio("sequence")

    card_cols2 = st.columns(3)
    with card_cols2[0]:
        with st.container(border=True):
            st.markdown("#### 🏷️ Brand Kits Studio")
            st.caption("Extract logos, color palettes, fonts, and brand tone directly from any website URL.")
            if st.button("Manage Brand Kits ➔", key="home_nav_brand", use_container_width=True):
                switch_studio("brand_kits")

    with card_cols2[1]:
        with st.container(border=True):
            st.markdown("#### 📦 All Assets Hub")
            st.caption("Central media locker for generated clips, scraped product photos, and audio files.")
            if st.button("Browse Assets ➔", key="home_nav_assets", use_container_width=True):
                switch_studio("assets")

    with card_cols2[2]:
        with st.container(border=True):
            st.markdown("#### ⚡ Full-Auto Video Pipeline")
            st.caption("Automated scriptwriting, voiceover, music, subtitles, and scene assembly.")
            if st.button("Open Full Pipeline ➔", key="home_nav_auto", use_container_width=True, type="primary"):
                switch_studio("auto_video")


def render_imagineart_video_studio():
    """
    ImagineArt Video Generation Studio (matching screenshot media_1790159668176.png).
    Supports Kie.ai Cloud and Free Local Ken-Burns Video Engine.
    """
    st.markdown("### 🎬 Video Tools & Generation Studio")
    st.caption("Generate cinematic AI videos using ByteDance Seedance 2.5, MiniMax Hailuo H3 Max, Kling 3.0 Pro, or Local Ken-Burns Motion.")

    _render_api_key_helper("kie")

    vcol_left, vcol_right = st.columns([1.8, 1.2])

    with vcol_left:
        with st.container(border=True):
            st.markdown("##### ⚙️ Generation Configuration")

            engine_choice = st.radio(
                "Generation Engine",
                options=["Kie.ai Cloud Models (Seedance 2.5 / Kling 3.0)", "Local Ken-Burns Motion Engine (100% Free & Local)"],
                index=0 if config.app.get("kie_api_key") else 1,
                key="ia_vid_engine_choice",
            )

            video_model_options = [
                ("bytedance/seedance-2-5", "ByteDance Seedance 2.5 [NEW]"),
                ("minimax/hailuo-01", "MiniMax Hailuo H3 Max [HOT]"),
                ("flux-3", "Flux 3 Video [NEW]"),
                ("google/omni-flash", "Google Omni Flash [NEW]"),
                ("seedance-2-0", "ByteDance Seedance 2.0 [HOT]"),
                ("kling-3-0", "Kling 3.0 Pro Video [BEST]"),
                ("kling-v2-1", "Kling 2.1 Video"),
                ("kling-v1-5", "Kling 1.5 Video"),
                ("wan-3-0", "Wan 3.0 Video [NEW]"),
                ("wan-2-1", "Wan 2.1 Video"),
                ("custom", "Custom Model ID..."),
            ]
            saved_vid_model = config.app.get("kie_video_model", "bytedance/seedance-2-5")

            if "Kie.ai" in engine_choice:
                selected_model = st.selectbox(
                    "Video Model",
                    options=[m[0] for m in video_model_options],
                    index=[m[0] for m in video_model_options].index(saved_vid_model) if saved_vid_model in [m[0] for m in video_model_options] else 0,
                    format_func=lambda k: dict(video_model_options).get(k, k),
                    key="ia_vid_model_select",
                )
                if selected_model == "custom":
                    custom_model = st.text_input("Enter Model ID", placeholder="e.g. bytedance/seedance-2-5", key="ia_custom_vid_model")
                    active_model = custom_model.strip() or "bytedance/seedance-2-5"
                else:
                    active_model = selected_model
            else:
                st.info("✨ **Local Motion Engine Active**: Generates photorealistic scenes using Pollinations AI (free) and animates with 4K cinematic camera motion via MoviePy.")
                active_model = "local-ken-burns"

            prompt_val = st.text_area(
                "Video Prompt",
                value=st.session_state.get("ia_video_prompt", ""),
                placeholder="e.g. Cinematic drone tracking shot of a futuristic cyberpunk supercar speeding through rainy neon Tokyo at midnight, 8k resolution, photorealistic",
                height=110,
                key="ia_vid_prompt_input",
            )

            pcol1, pcol2 = st.columns([1, 1])
            aspect_choice = pcol1.selectbox("Aspect Ratio", options=["9:16 (Portrait)", "16:9 (Landscape)", "1:1 (Square)"], index=0, key="ia_vid_aspect")
            duration_choice = pcol2.slider("Duration (seconds)", min_value=3, max_value=10, value=5, step=1, key="ia_vid_duration")

            # Start Frame conditioning (Image-to-Video)
            st.markdown("##### 🖼️ Start Frame / Image Conditioning (Optional)")
            start_frame_source = st.radio(
                "Conditioning Source",
                options=["None (Text-to-Video)", "Upload Image", "Use Sequence Anchor", "Choose from Scraped Photos"],
                horizontal=True,
                key="ia_vid_start_frame_source",
            )

            start_frame_path = ""
            if start_frame_source == "Upload Image":
                uploaded_img = st.file_uploader("Upload Start Frame", type=["png", "jpg", "jpeg", "webp"], key="ia_vid_frame_uploader")
                if uploaded_img:
                    target_dir = utils.storage_dir("local_videos")
                    os.makedirs(target_dir, exist_ok=True)
                    start_frame_path = os.path.join(target_dir, f"start_{uploaded_img.name}")
                    with open(start_frame_path, "wb") as f:
                        f.write(uploaded_img.getvalue())
            elif start_frame_source == "Use Sequence Anchor":
                anchor = st.session_state.get("sequence_anchor_frame", "")
                if anchor and os.path.exists(anchor):
                    start_frame_path = anchor
                else:
                    st.info("No sequence anchor frame set yet. Set one below or in the Storyboard.")
            elif start_frame_source == "Choose from Scraped Photos":
                scraped = st.session_state.get("scraped_product_images", [])
                if scraped:
                    picked = st.selectbox("Scraped Product Photo", options=scraped, key="ia_vid_scraped_pick")
                    start_frame_path = picked
                else:
                    st.info("No scraped product photos in session. Pull a product link in Auto Video to populate.")

            if start_frame_path and os.path.exists(start_frame_path):
                st.image(start_frame_path, caption=f"Active Start Frame: {os.path.basename(start_frame_path)}", width=160)

            generate_btn = st.button("🚀 Generate AI Video Clip", type="primary", use_container_width=True, key="ia_btn_gen_video")

    with vcol_right:
        with st.container(border=True):
            st.markdown("##### 📺 Output Player & Preview")

            if generate_btn:
                if not prompt_val.strip():
                    st.error("Please enter a prompt to generate video.")
                elif "Kie.ai" in engine_choice and not config.app.get("kie_api_key"):
                    st.error("Kie.ai API key is required for cloud models. Switch to the Local Ken-Burns Engine or enter your key above.")
                else:
                    with st.spinner(f"Generating video with {active_model}..."):
                        try:
                            aspect_ratio = VideoAspect.portrait if "9:16" in aspect_choice else VideoAspect.landscape if "16:9" in aspect_choice else VideoAspect.square
                            out_dir = utils.storage_dir("local_videos")
                            os.makedirs(out_dir, exist_ok=True)

                            if "Local Ken-Burns" in engine_choice or active_model == "local-ken-burns":
                                # 100% Free & Local Engine
                                if start_frame_path and os.path.exists(start_frame_path):
                                    img_path = start_frame_path
                                else:
                                    img_path = image_generator.generate_image_pollinations(
                                        prompt=prompt_val.strip(),
                                        model="flux",
                                        aspect=aspect_ratio,
                                        output_dir=out_dir,
                                    )
                                clip_out = os.path.join(out_dir, f"video_local_{int(time.time())}.mp4")
                                gen_clip = image_generator.image_to_animated_clip(
                                    image_path=img_path,
                                    duration=float(duration_choice),
                                    output_path=clip_out,
                                    aspect=aspect_ratio,
                                )
                                clips = [gen_clip] if gen_clip and os.path.exists(gen_clip) else []
                            else:
                                # Kie.ai Cloud Generation
                                clips = material._download_videos_kie_video_on_demand(
                                    task_id=f"studio_vid_{int(time.time())}",
                                    search_terms=[prompt_val.strip()],
                                    video_aspect=aspect_ratio,
                                    audio_duration=float(duration_choice),
                                    max_clip_duration=duration_choice,
                                    material_directory=out_dir,
                                    sequence_memory_mode="storyboard" if start_frame_path else "none",
                                    sequence_anchor_frame=start_frame_path,
                                    scene_models={0: active_model},
                                )

                            if clips and os.path.exists(clips[0]):
                                st.session_state["ia_last_generated_video"] = clips[0]
                                st.success(f"Video generated and saved locally to: `{clips[0]}`")
                            else:
                                st.error("Video generation did not return clips.")
                        except Exception as e:
                            logger.error(f"Video generation error: {e}")
                            st.error(f"Generation error: {e}")

            last_vid = st.session_state.get("ia_last_generated_video")
            if last_vid and os.path.exists(last_vid):
                st.video(last_vid)
                st.caption(f"📁 **Saved Locally**: `{last_vid}`")
                bcol1, bcol2 = st.columns(2)
                with open(last_vid, "rb") as vf:
                    bcol1.download_button("💾 Download MP4", data=vf.read(), file_name=os.path.basename(last_vid), mime="video/mp4", use_container_width=True)
                if bcol2.button("🔗 Set End Frame as Anchor", key="ia_btn_extract_anchor", use_container_width=True):
                    extracted = video.extract_last_frame(last_vid)
                    if extracted and os.path.exists(extracted):
                        st.session_state["sequence_anchor_frame"] = extracted
                        st.success("Final frame extracted and saved as Sequence Anchor Frame!")
            else:
                st.info("No video generated yet. Configure the prompt on the left and click Generate.")


def render_imagineart_image_studio():
    """
    ImagineArt Image Generation Studio (matching screenshot media_1790159652616.png).
    Supports Kie.ai Cloud, Free Pollinations (Flux / Midjourney), and OpenAI.
    """
    st.markdown("### 🎨 Image Tools & Generation Studio")
    st.caption("Generate ultra-detailed imagery with Google Nano Banana Pro, ByteDance Seedream V5 Pro, GPT Image 2.5 Sunburst, or Free Pollinations Flux.")

    _render_api_key_helper("kie")

    icol_left, icol_right = st.columns([1.8, 1.2])

    with icol_left:
        with st.container(border=True):
            st.markdown("##### ⚙️ Generation Configuration")

            prov_col, model_col = st.columns([1, 1.2])
            img_prov = prov_col.selectbox(
                "Image Provider",
                options=["pollinations", "kie", "openai"],
                format_func=lambda p: {"pollinations": "Pollinations (100% Free / Instant)", "kie": "Kie.ai (Credits - Banana Pro/Seedream)", "openai": "OpenAI (DALL-E)"}.get(p, p),
                key="ia_img_prov_select",
            )

            if img_prov == "kie":
                image_model_options = [
                    ("google/nano-banana-pro", "Nano Banana Pro (Google) [HOT]"),
                    ("google/nano-banana", "Nano Banana 2 (Google)"),
                    ("bytedance/seedream-5-0-pro", "Seedream V5 Pro (ByteDance) [NEW]"),
                    ("bytedance/seedream-4-0", "Seedream 4.0 (ByteDance)"),
                    ("gpt-image-2.5", "GPT Image 2.5 Sunburst [NEW]"),
                    ("imagineart-2-0", "ImagineArt 2.0 [BEST]"),
                    ("grok-imagine", "Grok Imagine 2.0 (xAI)"),
                    ("flux-kontext-pro", "Flux Kontext Pro (Ultra-Realistic)"),
                    ("custom", "Custom Model ID..."),
                ]
                saved_img_m = config.app.get("image_model_name", "google/nano-banana-pro")
                selected_img_model = model_col.selectbox(
                    "Image Model",
                    options=[m[0] for m in image_model_options],
                    index=[m[0] for m in image_model_options].index(saved_img_m) if saved_img_m in [m[0] for m in image_model_options] else 0,
                    format_func=lambda k: dict(image_model_options).get(k, k),
                    key="ia_img_model_select",
                )
                if selected_img_model == "custom":
                    custom_im = st.text_input("Enter Model ID", placeholder="e.g. google/nano-banana-pro", key="ia_custom_img_model")
                    active_img_model = custom_im.strip() or "google/nano-banana-pro"
                else:
                    active_img_model = selected_img_model
            elif img_prov == "pollinations":
                selected_img_model = model_col.selectbox(
                    "Free Image Model",
                    options=[m[1] for m in image_generator.POLLINATIONS_IMAGE_MODELS],
                    format_func=lambda k: dict((m[1], m[0]) for m in image_generator.POLLINATIONS_IMAGE_MODELS).get(k, k),
                    key="ia_pol_model_select",
                )
                active_img_model = selected_img_model
            else:
                active_img_model = model_col.selectbox("OpenAI Model", options=["dall-e-3", "dall-e-2"], key="ia_oai_model_select")

            img_prompt = st.text_area(
                "Image Prompt",
                value=st.session_state.get("ia_image_prompt", ""),
                placeholder="e.g. Macro close-up portrait of a cyberpunk android with glowing cyan optical sensors, detailed circuitry on ceramic skin, 35mm lens, 8k",
                height=110,
                key="ia_img_prompt_input",
            )

            scol1, scol2, scol3 = st.columns([1.2, 1, 1])
            style_presets = image_generator.STYLE_PRESETS
            selected_style = scol1.selectbox(
                "Visual Style",
                options=[s[1] for s in style_presets],
                format_func=lambda v: dict((s[1], s[0]) for s in style_presets).get(v, "Custom"),
                key="ia_img_style",
            )
            aspect_choice = scol2.selectbox("Aspect Ratio", options=["9:16", "16:9", "1:1"], key="ia_img_aspect")
            quality_choice = scol3.selectbox("Quality", options=["standard", "hd"], key="ia_img_quality")

            # Reference Image conditioning
            st.markdown("##### 🧬 Reference Image / Face & Product Lock (Optional)")
            uploaded_ref = st.file_uploader("Upload Reference Image", type=["png", "jpg", "jpeg", "webp"], key="ia_img_ref_uploader")
            ref_path = ""
            if uploaded_ref:
                target_dir = utils.storage_dir("local_videos")
                os.makedirs(target_dir, exist_ok=True)
                ref_path = os.path.join(target_dir, f"ref_{uploaded_ref.name}")
                with open(ref_path, "wb") as f:
                    f.write(uploaded_ref.getvalue())
                st.image(ref_path, caption="Active Reference Image", width=140)

            gen_img_btn = st.button("🎨 Generate Image", type="primary", use_container_width=True, key="ia_btn_gen_img")

    with icol_right:
        with st.container(border=True):
            st.markdown("##### 🖼️ Generated Result")
            if gen_img_btn:
                if not img_prompt.strip():
                    st.error("Please enter a prompt.")
                elif img_prov == "kie" and not config.app.get("kie_api_key"):
                    st.error("Kie.ai API key is required. Switch to Pollinations (Free) or enter your API key above.")
                else:
                    with st.spinner(f"Generating image with {active_img_model}..."):
                        try:
                            target_out_dir = utils.storage_dir("local_videos")
                            os.makedirs(target_out_dir, exist_ok=True)
                            saved_img = image_generator.generate_scene_image(
                                prompt=img_prompt.strip(),
                                provider=img_prov,
                                model=active_img_model,
                                aspect=aspect_choice,
                                style=selected_style,
                                quality=quality_choice,
                                output_dir=target_out_dir,
                                start_frame=ref_path if ref_path else None,
                            )
                            if saved_img and os.path.exists(saved_img):
                                st.session_state["ia_last_generated_image"] = saved_img
                                st.success(f"Image generated and saved locally to: `{saved_img}`")
                            else:
                                st.error("Image generation failed.")
                        except Exception as e:
                            logger.error(f"Image generation error: {e}")
                            st.error(f"Image error: {e}")

            last_img = st.session_state.get("ia_last_generated_image")
            if last_img and os.path.exists(last_img):
                st.image(last_img, use_container_width=True)
                st.caption(f"📁 **Saved Locally**: `{last_img}`")
                bcol1, bcol2, bcol3 = st.columns(3)
                with open(last_img, "rb") as fimg:
                    bcol1.download_button("💾 Download", data=fimg.read(), file_name=os.path.basename(last_img), mime="image/png", use_container_width=True)
                if bcol2.button("🎭 Set Anchor", key="ia_btn_set_anchor", use_container_width=True):
                    st.session_state["sequence_anchor_frame"] = last_img
                    st.success("Set as Sequence Hero Anchor!")
                if bcol3.button("🎬 Animate Clip", key="ia_btn_anim_clip", use_container_width=True):
                    with st.spinner("Animating image with Ken-Burns motion..."):
                        clip_path = image_generator.image_to_animated_clip(
                            image_path=last_img,
                            duration=5.0,
                            aspect="9:16" if "9:16" in aspect_choice else "16:9",
                        )
                        if clip_path and os.path.exists(clip_path):
                            st.session_state["ia_last_generated_video"] = clip_path
                            st.success(f"Animated video clip saved to `{clip_path}`!")
                            switch_studio("video")
            else:
                st.info("No image generated yet. Configure and click Generate.")


def render_imagineart_sequence_storyboard():
    """
    ImagineArt & Higgsfield Sequence Memory Multi-Scene Storyboard with full rendering engine.
    """
    st.markdown("### 🔗 Sequence Memory & Multi-Scene Storyboard")
    st.caption(
        "Higgsfield & ImagineArt visual continuity engine. Chain ending frames into start frames, "
        "lock hero characters or products, and configure individual models per scene."
    )

    with st.container(border=True):
        st.markdown("##### ⚙️ Global Continuity Pipeline")
        mcol1, mcol2 = st.columns([1.5, 1])

        seq_modes = [
            ("chained", "🔗 Chained Sequence Memory (Scene N End Frame -> Scene N+1 Start Frame)"),
            ("anchor_keyframe", "🎭 Anchor Hero Keyframe (Lock Same Character / Product Across All Scenes)"),
            ("storyboard", "🎬 Storyboard Custom Start Frames (Individual Per Scene)"),
            ("none", "⚡ Independent Shots (No Continuity Conditioning)"),
        ]
        active_mode = st.session_state.get("sequence_memory_mode", "chained")
        chosen_mode = mcol1.selectbox(
            "Continuity Mode",
            options=[m[0] for m in seq_modes],
            index=[m[0] for m in seq_modes].index(active_mode) if active_mode in [m[0] for m in seq_modes] else 0,
            format_func=lambda k: dict(seq_modes).get(k, k),
            key="ia_sb_seq_mode_select",
        )
        st.session_state["sequence_memory_mode"] = chosen_mode

        anchor_frame = st.session_state.get("sequence_anchor_frame", "")
        with mcol2:
            st.markdown("**🎭 Active Hero Anchor Keyframe**")
            if anchor_frame and os.path.exists(anchor_frame):
                st.image(anchor_frame, caption=f"Locked Hero: {os.path.basename(anchor_frame)}", width=120)
                if st.button("🗑️ Clear Anchor", key="ia_sb_clear_anchor"):
                    st.session_state["sequence_anchor_frame"] = ""
                    st.rerun(scope="app")
            else:
                uploaded_sb_anchor = st.file_uploader("Upload Hero Anchor Frame", type=["png", "jpg", "jpeg", "webp"], key="ia_sb_anchor_uploader")
                if uploaded_sb_anchor:
                    anchor_dir = utils.storage_dir("local_videos")
                    os.makedirs(anchor_dir, exist_ok=True)
                    fpath = os.path.join(anchor_dir, f"anchor_{uploaded_sb_anchor.name}")
                    with open(fpath, "wb") as f:
                        f.write(uploaded_sb_anchor.getvalue())
                    st.session_state["sequence_anchor_frame"] = fpath
                    st.rerun(scope="app")

    # Storyboard Scenes List
    if "storyboard_scenes" not in st.session_state or not st.session_state["storyboard_scenes"]:
        st.session_state["storyboard_scenes"] = [
            {"prompt": "Hero character walking into a high-tech laboratory, wide cinematic shot", "model": "bytedance/seedance-2-5", "start_frame": "", "clip_path": ""},
            {"prompt": "Close-up of hero operating the holographic interface with glowing blue particles", "model": "bytedance/seedance-2-5", "start_frame": "", "clip_path": ""},
            {"prompt": "Dramatic explosion of golden light reveals the breakthrough formula", "model": "kling-3-0", "start_frame": "", "clip_path": ""},
        ]

    scenes = st.session_state["storyboard_scenes"]

    st.markdown(f"#### 🎬 Storyboard Timeline ({len(scenes)} Scenes)")

    btn_add, btn_render_all = st.columns([1, 2])
    if btn_add.button("➕ Add Scene Shot", key="ia_sb_add_scene"):
        scenes.append({"prompt": "New scene shot prompt...", "model": "bytedance/seedance-2-5", "start_frame": "", "clip_path": ""})
        st.rerun(scope="app")

    render_all_clicked = btn_render_all.button("🎬 Render Full Video Sequence (Chain All Shots)", type="primary", use_container_width=True, key="ia_sb_render_all")

    all_models = [m[1] for m in material.KIE_VIDEO_MODELS] + [m[1] for m in image_generator.KIE_IMAGE_MODELS]
    model_labels = dict(material.KIE_VIDEO_MODELS + image_generator.KIE_IMAGE_MODELS)

    # Master render loop
    if render_all_clicked:
        with st.spinner("Rendering full storyboard sequence with continuity chaining..."):
            rendered_clips = []
            prev_last_frame = ""
            out_dir = utils.storage_dir("local_videos")
            os.makedirs(out_dir, exist_ok=True)

            for idx, sc in enumerate(scenes):
                # Resolve start frame
                if chosen_mode == "chained":
                    sf = st.session_state.get("sequence_anchor_frame", "") if idx == 0 else prev_last_frame
                elif chosen_mode == "anchor_keyframe":
                    sf = st.session_state.get("sequence_anchor_frame", "")
                else:
                    sf = sc.get("start_frame") or st.session_state.get("sequence_anchor_frame", "")

                prompt_text = sc.get("prompt", "cinematic shot").strip()
                clip_file = os.path.join(out_dir, f"scene_{idx + 1}_{int(time.time())}.mp4")

                # If Kie API key available and selected cloud model, use Kie.ai; else use local Ken-Burns
                if config.app.get("kie_api_key") and sc.get("model") in [m[1] for m in material.KIE_VIDEO_MODELS]:
                    clips = material._download_videos_kie_video_on_demand(
                        task_id=f"sb_scene_{idx}_{int(time.time())}",
                        search_terms=[prompt_text],
                        video_aspect=VideoAspect.portrait,
                        audio_duration=4.0,
                        max_clip_duration=4,
                        material_directory=out_dir,
                        sequence_memory_mode="storyboard" if sf else "none",
                        sequence_anchor_frame=sf,
                        scene_models={0: sc.get("model", "bytedance/seedance-2-5")},
                    )
                    gen_path = clips[0] if clips and os.path.exists(clips[0]) else ""
                else:
                    # High quality local fallback with start frame conditioning
                    if sf and os.path.exists(sf):
                        base_img = sf
                    else:
                        base_img = image_generator.generate_image_pollinations(
                            prompt=prompt_text,
                            model="flux",
                            aspect="9:16",
                            output_dir=out_dir,
                        )
                    gen_path = image_generator.image_to_animated_clip(
                        image_path=base_img,
                        duration=4.0,
                        output_path=clip_file,
                        aspect="9:16",
                    )

                if gen_path and os.path.exists(gen_path):
                    sc["clip_path"] = gen_path
                    rendered_clips.append(gen_path)
                    if chosen_mode == "chained":
                        extracted = video.extract_last_frame(gen_path)
                        if extracted and os.path.exists(extracted):
                            prev_last_frame = extracted

            if rendered_clips:
                master_video_path = os.path.join(out_dir, f"master_sequence_{int(time.time())}.mp4")
                final_out = video.combine_scene_clips(rendered_clips, output_path=master_video_path)
                st.session_state["ia_sb_master_video"] = final_out
                st.success(f"Full Sequence Rendered and Combined! Saved locally to `{final_out}`")

    # Display Master Sequence Video if rendered
    master_v = st.session_state.get("ia_sb_master_video")
    if master_v and os.path.exists(master_v):
        with st.container(border=True):
            st.markdown("#### 🏆 Master Combined Video Sequence")
            st.video(master_v)
            st.caption(f"📁 **Saved Locally**: `{master_v}`")
            with open(master_v, "rb") as mf:
                st.download_button("💾 Download Full Master Sequence Video", data=mf.read(), file_name=os.path.basename(master_v), mime="video/mp4", type="primary")

    # Display individual scene cards
    for idx, sc in enumerate(scenes):
        with st.container(border=True):
            sc_header, sc_del = st.columns([5, 1])
            sc_header.markdown(f"##### 🎥 Scene #{idx + 1}")
            if sc_del.button(f"🗑️ Delete", key=f"ia_sb_del_{idx}"):
                scenes.pop(idx)
                st.rerun(scope="app")

            sc_c1, sc_c2, sc_c3 = st.columns([2.5, 1.5, 1.5])
            sc["prompt"] = sc_c1.text_area(f"Scene #{idx + 1} Prompt", value=sc.get("prompt", ""), height=80, key=f"ia_sb_prompt_{idx}")

            cur_m = sc.get("model", "bytedance/seedance-2-5")
            sc["model"] = sc_c2.selectbox(
                f"Scene #{idx + 1} Model",
                options=all_models,
                index=all_models.index(cur_m) if cur_m in all_models else 0,
                format_func=lambda k: model_labels.get(k, k),
                key=f"ia_sb_model_{idx}",
            )

            with sc_c3:
                st.markdown("**Start Frame**")
                if chosen_mode == "chained":
                    if idx == 0:
                        st.caption("Initial Anchor Frame")
                    else:
                        st.markdown("<span class='ia-chain-indicator'>🔗 Chained from Scene #" + str(idx) + "</span>", unsafe_allow_html=True)
                else:
                    st.caption("Conditioning Start Frame")

                if sc.get("start_frame") and os.path.exists(sc["start_frame"]):
                    st.image(sc["start_frame"], width=100)
                else:
                    up_sf = st.file_uploader("Upload Frame", type=["png", "jpg", "jpeg", "webp"], key=f"ia_sb_frame_{idx}")
                    if up_sf:
                        sf_dir = utils.storage_dir("local_videos")
                        sf_path = os.path.join(sf_dir, f"sb_frame_{idx}_{up_sf.name}")
                        with open(sf_path, "wb") as f:
                            f.write(up_sf.getvalue())
                        sc["start_frame"] = sf_path
                        st.rerun(scope="app")

            # Per-scene generate button & video preview
            act_col, preview_col = st.columns([1, 2])
            if act_col.button(f"⚡ Generate Clip #{idx + 1}", key=f"ia_sb_gen_scene_{idx}"):
                with st.spinner(f"Generating Scene #{idx + 1}..."):
                    out_dir = utils.storage_dir("local_videos")
                    os.makedirs(out_dir, exist_ok=True)
                    prompt_txt = sc.get("prompt", "").strip() or "cinematic scene"
                    sf_to_use = sc.get("start_frame") or st.session_state.get("sequence_anchor_frame", "")

                    if config.app.get("kie_api_key") and sc.get("model") in [m[1] for m in material.KIE_VIDEO_MODELS]:
                        clips = material._download_videos_kie_video_on_demand(
                            task_id=f"sb_single_{idx}_{int(time.time())}",
                            search_terms=[prompt_txt],
                            video_aspect=VideoAspect.portrait,
                            audio_duration=4.0,
                            max_clip_duration=4,
                            material_directory=out_dir,
                            sequence_memory_mode="storyboard" if sf_to_use else "none",
                            sequence_anchor_frame=sf_to_use,
                            scene_models={0: sc.get("model", "bytedance/seedance-2-5")},
                        )
                        cpath = clips[0] if clips and os.path.exists(clips[0]) else ""
                    else:
                        img_p = sf_to_use if sf_to_use and os.path.exists(sf_to_use) else image_generator.generate_image_pollinations(
                            prompt=prompt_txt,
                            model="flux",
                            aspect="9:16",
                            output_dir=out_dir,
                        )
                        cpath = image_generator.image_to_animated_clip(
                            image_path=img_p,
                            duration=4.0,
                            output_path=os.path.join(out_dir, f"scene_{idx+1}_{int(time.time())}.mp4"),
                            aspect="9:16",
                        )
                    if cpath and os.path.exists(cpath):
                        sc["clip_path"] = cpath
                        st.success(f"Scene #{idx + 1} generated and saved locally to `{cpath}`!")
                        st.rerun(scope="app")

            if sc.get("clip_path") and os.path.exists(sc["clip_path"]):
                with preview_col:
                    st.video(sc["clip_path"])
                    st.caption(f"📁 `{sc['clip_path']}`")


def render_imagineart_assets_hub():
    """
    ImagineArt All Assets Hub (matching screenshot media_1790159592913.png).
    Central media manager: upload, preview, delete, and download.
    """
    st.markdown("### 📦 All Assets Hub")
    st.caption("Central media management library. Upload assets, search, preview, download, or set as start frame.")

    # Direct Upload Area
    with st.expander("⬆️ Upload Media to Local Library (Images / Videos / Audio)", expanded=False):
        uploaded_media = st.file_uploader(
            "Select files to upload",
            type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "mkv", "mp3", "wav"],
            accept_multiple_files=True,
            key="ia_assets_multi_uploader",
        )
        if uploaded_media:
            target_storage = utils.storage_dir("local_videos")
            os.makedirs(target_storage, exist_ok=True)
            saved_count = 0
            for f in uploaded_media:
                out_path = os.path.join(target_storage, f.name)
                with open(out_path, "wb") as dest:
                    dest.write(f.getvalue())
                saved_count += 1
            st.success(f"Successfully saved {saved_count} files locally to `{target_storage}`!")
            st.rerun(scope="app")

    # Top Filter Bar matching screenshot 2
    fcol1, fcol2, fcol3 = st.columns([2, 2, 1.5])
    asset_filter = fcol1.segmented_control(
        "Asset Type Filter",
        options=["All", "Images", "Videos", "Audio"],
        default="All",
        key="ia_assets_type_filter",
        label_visibility="collapsed",
    )
    search_q = fcol2.text_input("Search Assets", placeholder="Search by filename or keyword...", label_visibility="collapsed", key="ia_assets_search")
    grid_zoom = fcol3.select_slider("Grid Zoom", options=["Small", "Medium", "Large"], value="Medium", key="ia_assets_zoom")

    # Collect files
    storage_dirs = [
        utils.storage_dir("local_videos"),
        utils.storage_dir("cache_videos"),
        utils.storage_dir("audio"),
    ]
    all_files = []
    seen_paths = set()
    for sdir in storage_dirs:
        if os.path.exists(sdir):
            for fname in os.listdir(sdir):
                fpath = os.path.join(sdir, fname)
                if os.path.isfile(fpath) and fpath not in seen_paths:
                    seen_paths.add(fpath)
                    ext = os.path.splitext(fname)[1].lower()
                    ftype = "Images" if ext in (".png", ".jpg", ".jpeg", ".webp") else "Videos" if ext in (".mp4", ".mov", ".mkv", ".webm") else "Audio" if ext in (".mp3", ".wav", ".m4a") else "Other"
                    all_files.append({"name": fname, "path": fpath, "type": ftype, "size": os.path.getsize(fpath), "mtime": os.path.getmtime(fpath)})

    # Sort descending by modification time
    all_files.sort(key=lambda x: x["mtime"], reverse=True)

    # Filter
    if asset_filter and asset_filter != "All":
        all_files = [f for f in all_files if f["type"] == asset_filter]
    if search_q.strip():
        all_files = [f for f in all_files if search_q.strip().lower() in f["name"].lower()]

    cols_count = 5 if grid_zoom == "Small" else 3 if grid_zoom == "Medium" else 2
    st.markdown(f"**Showing {len(all_files)} assets in `{utils.storage_dir('local_videos')}`**")

    if not all_files:
        st.info("No assets found matching the filter. Upload images or generate media to populate.")
        return

    grid_cols = st.columns(cols_count)
    for idx, item in enumerate(all_files):
        c = grid_cols[idx % cols_count]
        with c:
            with st.container(border=True):
                if item["type"] == "Images":
                    st.image(item["path"], use_container_width=True)
                elif item["type"] == "Videos":
                    st.video(item["path"])
                elif item["type"] == "Audio":
                    st.audio(item["path"])

                st.caption(f"**{item['name'][:22]}** ({item['size'] // 1024} KB)")

                act1, act2, act3 = st.columns([1, 1, 1])
                with open(item["path"], "rb") as af:
                    act1.download_button("💾", data=af.read(), file_name=item["name"], key=f"ia_dl_ast_{idx}", use_container_width=True)

                if item["type"] == "Images":
                    if act2.button("🎭", key=f"ia_set_anc_{idx}", help="Set as Sequence Anchor Frame", use_container_width=True):
                        st.session_state["sequence_anchor_frame"] = item["path"]
                        st.toast(f"Set as Sequence Anchor: {item['name']}")

                if act3.button("🗑️", key=f"ia_del_ast_{idx}", help="Delete File from Disk", use_container_width=True):
                    try:
                        os.remove(item["path"])
                        st.toast(f"Deleted {item['name']}")
                        st.rerun(scope="app")
                    except Exception as err:
                        st.error(f"Delete failed: {err}")


def render_imagineart_brand_kits():
    """
    ImagineArt Brand Kits Studio (matching screenshot media_1790159603036.png).
    """
    st.markdown("### 🏷️ Brand Kits Studio")
    st.caption("Manage brand identities, extract logos and palettes from website links, and apply consistency across videos.")

    kits = brand_kit.list_brand_kits()
    kit_names = [k.get("brand_name", k.get("brand_id", "Brand")) for k in kits]

    top_c1, top_c2 = st.columns([2, 1])
    selected_kit_name = top_c1.selectbox(
        "Active Brand Kit",
        options=["New Brand..."] + kit_names,
        index=1 if kit_names else 0,
        key="ia_bk_active_select",
    )

    if "active_brand_kit" not in st.session_state or selected_kit_name != st.session_state.get("last_selected_kit"):
        st.session_state["last_selected_kit"] = selected_kit_name
        if selected_kit_name != "New Brand...":
            for k in kits:
                if k.get("brand_name") == selected_kit_name or k.get("brand_id") == selected_kit_name:
                    st.session_state["active_brand_kit"] = k
                    break
        else:
            st.session_state["active_brand_kit"] = {
                "brand_name": "My Brand",
                "website_url": "",
                "logo_url": "",
                "colors": {"primary": "#22c55e", "secondary": "#0ea5e9", "accent": "#f59e0b", "background": "#0e1117"},
                "fonts": {"heading": "Montserrat", "body": "Inter"},
                "voice_and_tone": "Authoritative, modern, customer-centric.",
                "tagline": "",
            }

    active_kit = st.session_state["active_brand_kit"]

    # Extract from Website URL tool (matching screenshot 3)
    with st.container(border=True):
        st.markdown("##### 🌐 Extract Brand from Website Link")
        st.caption("Enter any website URL (e.g. apple.com, nike.com, or your store link) to automatically scrape logos, colors, fonts, and description.")
        url_col, btn_ext_col = st.columns([4, 1.2])
        target_url = url_col.text_input("Website URL", value=active_kit.get("website_url", ""), placeholder="e.g. https://apple.com or https://yourstore.com", key="ia_bk_url_input")
        if btn_ext_col.button("⚡ Extract Brand", type="primary", use_container_width=True, key="ia_bk_btn_extract"):
            if target_url.strip():
                with st.spinner("Extracting brand identity from website..."):
                    extracted = brand_kit.extract_brand_from_url(target_url.strip())
                    active_kit.update(extracted)
                    brand_kit.save_brand_kit(active_kit.get("brand_name", "Brand"), active_kit)
                    st.session_state["active_brand_kit"] = active_kit
                    st.success(f"Successfully extracted brand assets for {active_kit.get('brand_name')}! Saved locally.")
                    st.rerun(scope="app")
            else:
                st.warning("Please enter a valid website URL.")

    # Brand Assets Editor
    st.markdown("##### 🎨 Brand Assets Locker")
    ecol1, ecol2 = st.columns([1.5, 1])

    with ecol1:
        active_kit["brand_name"] = st.text_input("Brand Name", value=active_kit.get("brand_name", ""), key="ia_bk_name")
        active_kit["tagline"] = st.text_input("Tagline / Headline", value=active_kit.get("tagline", ""), key="ia_bk_tagline")
        active_kit["voice_and_tone"] = st.text_area("Brand Voice & Tone Guidelines", value=active_kit.get("voice_and_tone", ""), height=80, key="ia_bk_voice")

        st.markdown("**Color Palette Swatches**")
        colors = active_kit.get("colors", {})
        cc1, cc2, cc3, cc4 = st.columns(4)
        c_primary = cc1.color_picker("Primary", value=colors.get("primary", "#22c55e"), key="ia_cp_prim")
        c_secondary = cc2.color_picker("Secondary", value=colors.get("secondary", "#0ea5e9"), key="ia_cp_sec")
        c_accent = cc3.color_picker("Accent", value=colors.get("accent", "#f59e0b"), key="ia_cp_acc")
        c_bg = cc4.color_picker("Background", value=colors.get("background", "#0e1117"), key="ia_cp_bg")
        active_kit["colors"] = {"primary": c_primary, "secondary": c_secondary, "accent": c_accent, "background": c_bg}

    with ecol2:
        st.markdown("**Logo & Visuals**")
        if active_kit.get("logo_url"):
            st.image(active_kit["logo_url"], caption="Brand Logo", width=140)

        uploaded_logo = st.file_uploader("Upload New Brand Logo", type=["png", "jpg", "svg", "webp"], key="ia_bk_logo_up")
        if uploaded_logo:
            target_dir = utils.storage_dir("local_videos")
            os.makedirs(target_dir, exist_ok=True)
            lpath = os.path.join(target_dir, f"logo_{uploaded_logo.name}")
            with open(lpath, "wb") as f:
                f.write(uploaded_logo.getvalue())
            active_kit["logo_url"] = lpath
            st.rerun(scope="app")

        # Color Swatches Preview
        st.markdown(
            f"""
            <div style="margin-top: 12px; display: flex; gap: 10px;">
                <div class="ia-swatch-box"><div class="ia-swatch" style="background-color: {c_primary};"></div><div class="ia-swatch-label">Primary</div></div>
                <div class="ia-swatch-box"><div class="ia-swatch" style="background-color: {c_secondary};"></div><div class="ia-swatch-label">Secondary</div></div>
                <div class="ia-swatch-box"><div class="ia-swatch" style="background-color: {c_accent};"></div><div class="ia-swatch-label">Accent</div></div>
                <div class="ia-swatch-box"><div class="ia-swatch" style="background-color: {c_bg};"></div><div class="ia-swatch-label">Base</div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    act_col1, act_col2 = st.columns([1, 1])
    if act_col1.button("💾 Save Brand Kit Locally", type="primary", use_container_width=True, key="ia_bk_save_btn"):
        fpath = brand_kit.save_brand_kit(active_kit.get("brand_name", "Brand"), active_kit)
        st.session_state["active_brand_kit"] = active_kit
        st.success(f"Brand kit saved locally to `{fpath}`!")

    if act_col2.button("✨ Apply Brand Guidelines to Video Script", use_container_width=True, key="ia_bk_apply_btn"):
        brand_instructions = f"Brand: {active_kit.get('brand_name')}. Tagline: {active_kit.get('tagline')}. Voice: {active_kit.get('voice_and_tone')}."
        st.session_state["brand_guideline_prompt"] = brand_instructions
        st.toast("Brand guidelines applied across video production!")
