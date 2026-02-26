import copy
import io
from pathlib import Path
import folder_paths
import zipfile

from .utils import *

TOOLTIP_LIMIT_OPUS_FREE = "Limit image size and steps for free generation by Opus."

import random
import time

class RandomDelayNAID:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "min_delay": ("INT", {"default": 10, "min": 0, "max": 600, "tooltip": "最小冷却时间（秒）"}),
                "max_delay": ("INT", {"default": 30, "min": 0, "max": 600, "tooltip": "最大冷却时间（秒）"}),
                "seed_in": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "tooltip": "用来串联工作流的种子"}),
            }
        }

    RETURN_TYPES = ("INT",)
    RETURN_NAMES = ("seed_out",)
    FUNCTION = "do_delay"
    CATEGORY = "NovelAI/utils"

    def do_delay(self, min_delay, max_delay, seed_in):
        # 防止你不小心把最小值填得比最大值还大
        if min_delay > max_delay:
            min_delay, max_delay = max_delay, min_delay
            
        # 计算随机休眠时间
        delay_time = random.randint(min_delay, max_delay)
        
        # 在控制台打印提示，让你知道它没有死机，只是在休息
        print(f"\n⏳ [防降权保护] 正在模拟人类操作，随机休眠 {delay_time} 秒...\n")
        
        # 让程序在这里睡大觉
        time.sleep(delay_time)
        
        # 睡醒后，把原封不动的种子传递给下一个节点
        return (seed_in,)

class RandomResolution:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "presets": ("STRING", {
                    "default": "832x1216, 5\n1216x832, 2\n1024x1024, 1", 
                    "multiline": True,
                    "tooltip": "每行写一个尺寸，格式为 '宽x高, 权重'"
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff, "tooltip": "用于触发每次随机"}),
            }
        }

    RETURN_TYPES = ("INT", "INT", "STRING")
    RETURN_NAMES = ("width", "height", "size_text")
    FUNCTION = "get_random_size"
    CATEGORY = "NovelAI/utils"

    def get_random_size(self, presets, seed):
        lines = presets.strip().split('\n')
        valid_sizes = []
        weights = []
        
        for line in lines:
            line = line.strip().lower()
            if not line:
                continue
            
            # 解析权重（支持使用逗号或冒号分隔）
            weight = 1.0
            if ',' in line:
                parts, w_str = line.split(',', 1)
                try:
                    weight = float(w_str.strip())
                except ValueError:
                    weight = 1.0
            elif ':' in line:
                parts, w_str = line.split(':', 1)
                try:
                    weight = float(w_str.strip())
                except ValueError:
                    weight = 1.0
            else:
                parts = line

            # 解析宽和高
            res_parts = parts.strip().split('x')
            if len(res_parts) == 2 and res_parts[0].isdigit() and res_parts[1].isdigit():
                valid_sizes.append((int(res_parts[0]), int(res_parts[1])))
                weights.append(weight)
        
        # 如果格式写错导致没提取到尺寸，给个保底防报错
        if not valid_sizes:
            valid_sizes = [(832, 1216)]
            weights = [1.0]
            
        # 根据种子和设定的权重进行随机抽取
        random.seed(seed)
        selected = random.choices(valid_sizes, weights=weights, k=1)[0]
        
        return (selected[0], selected[1], f"{selected[0]}x{selected[1]}")

class PromptToNAID:
    @classmethod
    def INPUT_TYPES(s):
        return { "required": {
            "text": ("STRING", { "forceInput":True, "multiline": True, "dynamicPrompts": False,}),
            "weight_per_brace": ("FLOAT", { "default": 0.05, "min": 0.05, "max": 0.10, "step": 0.05 }),
            "syntax_mode": (["brace", "numeric"], { "default": "brace" }),
        }}

    RETURN_TYPES = ("STRING",)
    FUNCTION = "convert"
    CATEGORY = "NovelAI/utils"
    def convert(self, text, weight_per_brace, syntax_mode):
        nai_prompt = prompt_to_nai(text, weight_per_brace, syntax_mode)
        return (nai_prompt,)

class ImageToNAIMask:
    @classmethod
    def INPUT_TYPES(s):
        return { "required": { "image": ("IMAGE",) } }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "convert"
    CATEGORY = "NovelAI/utils"
    def convert(self, image):
        s = resize_to_naimask(image)
        return (s,)

class ModelOption:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "model": (["nai-diffusion-2", "nai-diffusion-furry-3", "nai-diffusion-3", "nai-diffusion-4-curated-preview", "nai-diffusion-4-full", "nai-diffusion-4-5-curated", "nai-diffusion-4-5-full"], { "default": "nai-diffusion-4-5-full" }),
            },
            "optional": { "option": ("NAID_OPTION",) },
        }

    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "set_option"
    CATEGORY = "NovelAI"
    def set_option(self, model, option=None):
        option = copy.deepcopy(option) if option else {}
        option["model"] = model
        return (option,)

class Img2ImgOption:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "strength": ("FLOAT", { "default": 0.70, "min": 0.01, "max": 0.99, "step": 0.01, "display": "number" }),
                "noise": ("FLOAT", { "default": 0.00, "min": 0.00, "max": 0.99, "step": 0.02, "display": "number" }),
            },
        }

    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "set_option"
    CATEGORY = "NovelAI"
    def set_option(self, image, strength, noise):
        option = {}
        option["img2img"] = (image, strength, noise)
        return (option,)

class InpaintingOption:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "mask": ("IMAGE",),
                "add_original_image": ("BOOLEAN", { "default": True }),
            },
        }

    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "set_option"
    CATEGORY = "NovelAI"
    def set_option(self, image, mask, add_original_image):
        option = {}
        option["infill"] = (image, mask, add_original_image)
        return (option,)

class VibeTransferOption:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "information_extracted": ("FLOAT", { "default": 1.0, "min": 0.01, "max": 1.0, "step": 0.01, "display": "number" }),
                "strength": ("FLOAT", { "default": 0.6, "min": 0.01, "max": 1.0, "step": 0.01, "display": "number" }),
            },
            "optional": { "option": ("NAID_OPTION",) },
        }
    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "set_option"
    CATEGORY = "NovelAI"
    def set_option(self, image, information_extracted, strength, option=None):
        option = copy.deepcopy(option) if option else {}
        if "vibe" not in option:
            option["vibe"] = []

        option["vibe"].append((image, information_extracted, strength))
        return (option,)

class NetworkOption:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "ignore_errors": ("BOOLEAN", { "default": True }),
                "timeout_sec": ("INT", { "default": 120, "min": 30, "max": 3000, "step": 1, "display": "number" }),
                "retry": ("INT", { "default": 3, "min": 1, "max": 100, "step": 1, "display": "number" }),
            },
            "optional": { "option": ("NAID_OPTION",) },
        }
    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "set_option"
    CATEGORY = "NovelAI"
    def set_option(self, ignore_errors, timeout_sec, retry, option=None):
        option = copy.deepcopy(option) if option else {}
        option["ignore_errors"] = ignore_errors
        option["timeout"] = timeout_sec
        option["retry"] = retry
        return (option,)


class GenerateNAID:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "width": ("INT", { "default": 832, "min": 64, "max": 1600, "step": 64, "display": "number" }),
                "height": ("INT", { "default": 1216, "min": 64, "max": 1600, "step": 64, "display": "number" }),
                "positive": ("STRING", { "default": ", best quality, amazing quality, very aesthetic, absurdres", "multiline": True, "dynamicPrompts": False }),
                "negative": ("STRING", { "default": "lowres", "multiline": True, "dynamicPrompts": False }),
                "steps": ("INT", { "default": 28, "min": 0, "max": 50, "step": 1, "display": "number" }),
                "cfg": ("FLOAT", { "default": 5.0, "min": 0.0, "max": 10.0, "step": 0.1, "display": "number" }),
                "variety" : ("BOOLEAN", { "default": False }),
                "decrisper": ("BOOLEAN", { "default": False }),
                "smea": (["none", "SMEA", "SMEA+DYN"], { "default": "none" }),
                "sampler": (["k_euler", "k_euler_ancestral", "k_dpmpp_2s_ancestral", "k_dpmpp_2m_sde", "k_dpmpp_2m", "k_dpmpp_sde", "ddim"], { "default": "k_euler" }),
                "scheduler": (["native", "karras", "exponential", "polyexponential"], { "default": "native" }),
                "seed": ("INT", { "default": 0, "min": 0, "max": 9999999999, "step": 1, "display": "number" }),
                "uncond_scale": ("FLOAT", { "default": 1.0, "min": 0.0, "max": 1.5, "step": 0.05, "display": "number" }),
                "cfg_rescale": ("FLOAT", { "default": 0.0, "min": 0.0, "max": 1.0, "step": 0.02, "display": "number" }),
                "keep_alpha": ("BOOLEAN", { "default": True, "tooltip": "Disable to further process output images locally" }),
            },
            "optional": { "option": ("NAID_OPTION",) },
        }

    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "generate"
    CATEGORY = "NovelAI"

    def generate(self, limit_opus_free, width, height, positive, negative, steps, cfg, decrisper, variety, smea, sampler, scheduler, seed, uncond_scale, cfg_rescale, keep_alpha, option=None):
        width, height = calculate_resolution(width*height, (width, height))

        # ref. novelai_api.ImagePreset
        params = {
            "params_version": 1,
            "width": width,
            "height": height,
            "scale": cfg,
            "sampler": sampler,
            "steps": steps,
            "seed": seed,
            "n_samples": 1,
            "ucPreset": 3,
            "qualityToggle": False,
            "sm": (smea == "SMEA" or smea == "SMEA+DYN") and sampler != "ddim",
            "sm_dyn": smea == "SMEA+DYN" and sampler != "ddim",
            "dynamic_thresholding": decrisper,
            "skip_cfg_above_sigma": None,
            "controlnet_strength": 1.0,
            "legacy": False,
            "add_original_image": False,
            "cfg_rescale": cfg_rescale,
            "noise_schedule": scheduler,
            "legacy_v3_extend": False,
            "uncond_scale": uncond_scale,
            "negative_prompt": negative,
            "prompt": positive,
            "reference_image_multiple": [],
            "reference_information_extracted_multiple": [],
            "reference_strength_multiple": [],
            "extra_noise_seed": seed,
            "v4_prompt": {
                "use_coords": False,
                "use_order": False,
                "caption": {
                    "base_caption": positive,
                    "char_captions": []
                }
            },
            "v4_negative_prompt": {
                "use_coords": False,
                "use_order": False,
                "caption": {
                    "base_caption": negative,
                    "char_captions": []
                }
            },
            "characterPrompts": []
        }
        model = "nai-diffusion-4-5-full"
        action = "generate"

        if sampler == "k_euler_ancestral" and scheduler != "native":
            params["deliberate_euler_ancestral_bug"] = False
            params["prefer_brownian"] = True

        if option:
            if "img2img" in option:
                action = "img2img"
                image, strength, noise = option["img2img"]
                params["image"] = image_to_base64(resize_image(image, (width, height)))
                params["strength"] = strength
                params["noise"] = noise
            elif "infill" in option:
                action = "infill"
                image, mask, add_original_image = option["infill"]
                params["image"] = image_to_base64(resize_image(image, (width, height)))
                params["mask"] = naimask_to_base64(resize_to_naimask(mask, (width, height), "4" in model))
                params["add_original_image"] = add_original_image

            if "vibe" in option:
                for vibe in option["vibe"]:
                    image, information_extracted, strength = vibe
                    params["reference_image_multiple"].append(image_to_base64(resize_image(image, (width, height))))
                    params["reference_information_extracted_multiple"].append(information_extracted)
                    params["reference_strength_multiple"].append(strength)

            if "model" in option:
                model = option["model"]

            # Handle V4 options
            if "v4_prompt" in option:
                params["v4_prompt"].update(option["v4_prompt"])
            
            # --- 严谨版：AI's Choice / 手动指定 双模式解析逻辑 ---
            if "characters" in option:
                use_manual_coords = False # 默认全局为 AI's Choice
                
                for char in option["characters"]:
                    # 严谨判定：只要有任何一个角色显式要求了手动排版，全局坐标网格就必须开启
                    if char["position_mode"] == "Manual Coords":
                        use_manual_coords = True

                    # 核心拦截逻辑：如果处于 AI's Choice 模式，强行覆写前端传来的垃圾坐标，对齐官网的 0.5！
                    safe_x = char["center_x"] if char["position_mode"] == "Manual Coords" else 0.5
                    safe_y = char["center_y"] if char["position_mode"] == "Manual Coords" else 0.5

                    # 1. 塞入 characterPrompts 数组
                    params["characterPrompts"].append({
                        "prompt": char["prompt"],
                        "uc": char["uc"],
                        "center": {"x": safe_x, "y": safe_y},
                        "enabled": True
                    })
                    # 2. 同步塞入 v4_prompt
                    params["v4_prompt"]["caption"]["char_captions"].append({
                        "char_caption": char["prompt"],
                        "centers": [{"x": safe_x, "y": safe_y}]
                    })
                    # 3. 同步塞入 v4_negative_prompt
                    params["v4_negative_prompt"]["caption"]["char_captions"].append({
                        "char_caption": char["uc"],
                        "centers": [{"x": safe_x, "y": safe_y}]
                    })
                
                # 绝对严谨的底层开关锁死，完全听命于用户的 explicit 设置
                params["v4_prompt"]["use_coords"] = use_manual_coords
                params["v4_negative_prompt"]["use_coords"] = use_manual_coords
                params["v4_prompt"]["use_order"] = True # V4只要用多角色，顺序权重必须锁定为True

        timeout = option["timeout"] if option and "timeout" in option else None
        retry = option["retry"] if option and "retry" in option else None

        if limit_opus_free:
            pixel_limit = 1024*1024
            if width * height > pixel_limit:
                max_width, max_height = calculate_resolution(pixel_limit, (width, height))
                params["width"] = max_width
                params["height"] = max_height
            if steps > 28:
                params["steps"] = 28

        if variety:
            params["skip_cfg_above_sigma"] = calculate_skip_cfg_above_sigma(params["width"], params["height"])

        if sampler == "ddim" and model not in ("nai-diffusion-2"):
            params["sampler"] = "ddim_v3"

        if action == "infill" and model not in ("nai-diffusion-2"):
            model = f"{model}-inpainting"

        image = blank_image()
        try:
            zipped_bytes = generate_image(self.access_token, positive, model, action, params, timeout, retry)
            zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
            image_bytes = zipped.read(zipped.infolist()[0]) # only support one n_samples

            image = bytes_to_image(image_bytes, keep_alpha)
        except Exception as e:
            if "ignore_errors" in option and option["ignore_errors"]:
                print("ignore error:", e)
            else:
                raise e

        return (image,)


def base_augment(access_token, output_dir, limit_opus_free, ignore_errors, req_type, image, options=None):
    image = image.movedim(-1, 1)
    w, h = (image.shape[3], image.shape[2])
    image = image.movedim(1, -1)

    if limit_opus_free:
        pixel_limit = 1024 * 1024
        if w * h > pixel_limit:
            w, h = calculate_resolution(pixel_limit, (w, h))
    base64_image = image_to_base64(resize_image(image, (w, h)))
    result_image = blank_image()
    try:
        # Build request based on NAI v4 API spec
        request = {
            "image": base64_image,
            "req_type": req_type,
            "width": w,
            "height": h
        }

        # Add optional parameters if provided
        if options:
            if "defry" in options:
                request["defry"] = options["defry"]
            if "prompt" in options:
                request["prompt"] = options["prompt"]

        zipped_bytes = augment_image(access_token, req_type, w, h, base64_image, options=options)
        zipped = zipfile.ZipFile(io.BytesIO(zipped_bytes))
        image_bytes = zipped.read(zipped.infolist()[0]) # only support one n_samples

        result_image = bytes_to_image(image_bytes)
    except Exception as e:
        if ignore_errors:
            print("ignore error:", e)
        else:
            raise e

    return (result_image,)

class RemoveBGAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors):
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "bg-removal", image)

class LineArtAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors):
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "lineart", image)

class SketchAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors):
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "sketch", image)

class ColorizeAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
                "defry": ("INT", { "default": 0, "min": 0, "max": 5, "step": 1, "display": "number" }),
                "prompt": ("STRING", { "default": "", "multiline": True, "dynamicPrompts": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors, defry, prompt):
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "colorize", image, options={ "defry": defry, "prompt": prompt })

class EmotionAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()

    strength_list = ["normal", "slightly_weak", "weak", "even_weaker", "very_weak", "weakest"]
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
                "mood": (["neutral", "happy", "sad", "angry", "scared",
                     "surprised", "tired", "excited", "nervous", "thinking",
                     "confused", "shy", "disgusted", "smug", "bored",
                     "laughing", "irritated", "aroused", "embarrassed", "worried",
                     "love", "determined", "hurt", "playful"], { "default": "neutral" }),
                "strength": (s.strength_list, { "default": "normal" }),
                "prompt": ("STRING", { "default": "", "multiline": True, "dynamicPrompts": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors, mood, strength, prompt):
        prompt = f"{mood};;{prompt}"
        defry = EmotionAugment.strength_list.index(strength)
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "emotion", image, options={ "defry": defry, "prompt": prompt })

class DeclutterAugment:
    def __init__(self):
        self.access_token = get_access_token()
        self.output_dir = folder_paths.get_output_directory()
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "image": ("IMAGE",),
                "limit_opus_free": ("BOOLEAN", { "default": True, "tooltip": TOOLTIP_LIMIT_OPUS_FREE }),
                "ignore_errors": ("BOOLEAN", { "default": False }),
            },
        }
    RETURN_TYPES = ("IMAGE",)
    FUNCTION = "augment"
    CATEGORY = "NovelAI/director_tools"
    def augment(self, image, limit_opus_free, ignore_errors):
        return base_augment(self.access_token, self.output_dir, limit_opus_free, ignore_errors, "declutter", image)
        
class V4BasePrompt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "base_caption": ("STRING", { "multiline": True }),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "convert"
    CATEGORY = "NovelAI/v4"
    def convert(self, base_caption):
        return (base_caption,)

class V4NegativePrompt:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "negative_caption": ("STRING", { "multiline": True }),
            }
        }

    RETURN_TYPES = ("STRING",)
    FUNCTION = "convert"
    CATEGORY = "NovelAI/v4"
    def convert(self, negative_caption):
        return (negative_caption,)
        
class CharacterPromptNAID:
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "prompt": ("STRING", { "multiline": True, "tooltip": "该角色的专属正面提示词" }),
                "uc": ("STRING", { "multiline": True, "default": "", "tooltip": "该角色的专属负面提示词" }),
                "position_mode": (["AI's Choice", "Manual Coords"], { "default": "AI's Choice", "tooltip": "选择AI自由排版，或手动强制使用下方坐标" }),
                "center_x": ("FLOAT", { "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "X坐标 (仅在Manual模式下生效)" }),
                "center_y": ("FLOAT", { "default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01, "tooltip": "Y坐标 (仅在Manual模式下生效)" }),
            },
            "optional": { "option": ("NAID_OPTION",) },
        }

    RETURN_TYPES = ("NAID_OPTION",)
    FUNCTION = "add_character"
    CATEGORY = "NovelAI/v4"

    def add_character(self, prompt, uc, position_mode, center_x, center_y, option=None):
        option = copy.deepcopy(option) if option else {}
        if "characters" not in option:
            option["characters"] = []

        # 将所有的显式配置打包传给主节点
        option["characters"].append({
            "prompt": prompt,
            "uc": uc,
            "position_mode": position_mode,
            "center_x": center_x,
            "center_y": center_y
        })
        return (option,)

NODE_CLASS_MAPPINGS = {
    "CharacterPromptNAID": CharacterPromptNAID,
    "RandomDelayNAID": RandomDelayNAID,
    "RandomResolutionNAID": RandomResolution,
    "GenerateNAID": GenerateNAID,
    "ModelOptionNAID": ModelOption,
    "Img2ImgOptionNAID": Img2ImgOption,
    "InpaintingOptionNAID": InpaintingOption,
    "VibeTransferOptionNAID": VibeTransferOption,
    "NetworkOptionNAID": NetworkOption,
    "MaskImageToNAID": ImageToNAIMask,
    "PromptToNAID": PromptToNAID,
    "RemoveBGNAID": RemoveBGAugment,
    "LineArtNAID": LineArtAugment,
    "SketchNAID": SketchAugment,
    "ColorizeNAID": ColorizeAugment,
    "EmotionNAID": EmotionAugment,
    "DeclutterNAID": DeclutterAugment,
    "V4BasePrompt": V4BasePrompt,
    "V4NegativePrompt": V4NegativePrompt,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CharacterPromptNAID": "Character Prompt ✒️🅝🅐🅘",
    "RandomDelayNAID": "Random Delay ✒️🅝🅐🅘",
    "RandomResolutionNAID": "Random Resolution ✒️🅝🅐🅘",
    "GenerateNAID": "Generate ✒️🅝🅐🅘",
    "ModelOptionNAID": "ModelOption ✒️🅝🅐🅘",
    "Img2ImgOptionNAID": "Img2ImgOption ✒️🅝🅐🅘",
    "InpaintingOptionNAID": "InpaintingOption ✒️🅝🅐🅘",
    "VibeTransferOptionNAID": "VibeTransferOption ✒️🅝🅐🅘",
    "NetworkOptionNAID": "NetworkOption ✒️🅝🅐🅘",
    "MaskImageToNAID": "Convert Mask Image ✒️🅝🅐🅘",
    "PromptToNAID": "Convert Prompt ✒️🅝🅐🅘",
    "RemoveBGNAID": "Remove BG ✒️🅝🅐🅘",
    "LineArtNAID": "LineArt ✒️🅝🅐🅘",
    "SketchNAID": "Sketch ✒️🅝🅐🅘",
    "ColorizeNAID": "Colorize ✒️🅝🅐🅘",
    "EmotionNAID": "Emotion ✒️🅝🅐🅘",
    "DeclutterNAID": "Declutter ✒️🅝🅐🅘",
    "V4BasePrompt": "V4 Base Prompt ✒️🅝🅐🅘",
    "V4NegativePrompt": "V4 Negative Prompt ✒️🅝🅐🅘",
}