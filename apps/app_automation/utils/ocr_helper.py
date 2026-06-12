# -*- coding: utf-8 -*-
"""
OCR 工具类 - 基于 EasyOCR
"""
import os
import time
import logging
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache

import cv2
import numpy as np
from PIL import Image, ImageEnhance

try:
    import easyocr
    from easyocr.config import (
        all_lang_list,
        arabic_lang_list,
        bengali_lang_list,
        cyrillic_lang_list,
        detection_models,
        devanagari_lang_list,
        recognition_models,
    )
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    all_lang_list = []
    arabic_lang_list = []
    bengali_lang_list = []
    cyrillic_lang_list = []
    detection_models = {}
    devanagari_lang_list = []
    recognition_models = {}

from airtest.core.api import G, sleep as airtest_sleep

logger = logging.getLogger(__name__)


class OCRRuntimeError(RuntimeError):
    """OCR 运行时不可用或初始化失败。"""


class OCRHelper:
    """OCR 辅助类 - 提供图像文字识别功能"""

    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    DEFAULT_MODEL_STORAGE_DIRECTORY = str(PROJECT_ROOT / 'third_party' / 'easyocr' / 'model')

    # OCR结果缓存：key为(坐标区域hash, 图片hash)，value为(识别结果, 时间戳)
    _ocr_cache = {}
    _cache_ttl = 2.0  # 缓存有效期2秒
    _cache_max_size = 50  # 最大缓存条目数

    # EasyOCR reader实例（延迟初始化）
    _easyocr_reader = None
    _easyocr_reader_config = None

    def __init__(
        self,
        languages=None,
        use_gpu=False,
        model_storage_directory: Optional[str] = None,
        download_enabled: bool = False,
        detect_network: str = 'craft',
    ):
        """
        初始化 OCR 助手

        Args:
            languages: OCR 识别语言列表，默认为 ['en']（英文）
                      可选：['ch_sim', 'en'] (简体中文和英文)
            use_gpu: 是否使用 GPU 加速，默认 False
            model_storage_directory: EasyOCR 模型目录，默认使用项目内 third_party/easyocr/model
            download_enabled: 是否允许 EasyOCR 在线下载模型，默认 False
            detect_network: EasyOCR 检测模型，默认 craft
        """
        if not EASYOCR_AVAILABLE:
            logger.warning("EasyOCR 未安装，OCR 功能将不可用。请运行: pip install easyocr")

        self.languages = list(languages or ['en'])
        self.use_gpu = use_gpu
        self.model_storage_directory = self._resolve_model_storage_directory(model_storage_directory)
        self.download_enabled = download_enabled
        self.detect_network = detect_network
        os.makedirs(self.model_storage_directory, exist_ok=True)

    @classmethod
    def _resolve_model_storage_directory(cls, model_storage_directory: Optional[str] = None) -> str:
        target_dir = model_storage_directory or cls.DEFAULT_MODEL_STORAGE_DIRECTORY
        return os.path.abspath(os.path.expanduser(str(target_dir)))

    @classmethod
    def _get_model_directory_hint(cls, model_storage_directory: str) -> str:
        if os.path.isdir(model_storage_directory):
            current_files = sorted(
                entry.name for entry in os.scandir(model_storage_directory) if entry.is_file()
            )
            if current_files:
                return f"；当前模型目录: {model_storage_directory}；现有文件: {', '.join(current_files)}"
            return f"；当前模型目录为空: {model_storage_directory}"
        return f"；当前模型目录不存在: {model_storage_directory}"

    @classmethod
    def _get_recognition_model_config(cls, languages=None) -> Dict[str, Any]:
        languages = list(languages or ['en'])
        if not recognition_models:
            raise OCRRuntimeError("EasyOCR 配置不可用，无法解析识别模型")

        if languages == ['en']:
            return recognition_models['gen2']['english_g2']

        unknown_lang = set(languages) - set(all_lang_list)
        if unknown_lang:
            raise OCRRuntimeError(f"EasyOCR 不支持的语言: {sorted(unknown_lang)}")

        if 'th' in languages:
            return recognition_models['gen1']['thai_g1']
        if 'ch_tra' in languages:
            return recognition_models['gen1']['zh_tra_g1']
        if 'ch_sim' in languages:
            return recognition_models['gen2']['zh_sim_g2']
        if 'ja' in languages:
            return recognition_models['gen2']['japanese_g2']
        if 'ko' in languages:
            return recognition_models['gen2']['korean_g2']
        if 'ta' in languages:
            return recognition_models['gen1']['tamil_g1']
        if 'te' in languages:
            return recognition_models['gen2']['telugu_g2']
        if 'kn' in languages:
            return recognition_models['gen2']['kannada_g2']
        if set(languages) & set(bengali_lang_list):
            return recognition_models['gen1']['bengali_g1']
        if set(languages) & set(arabic_lang_list):
            return recognition_models['gen1']['arabic_g1']
        if set(languages) & set(devanagari_lang_list):
            return recognition_models['gen1']['devanagari_g1']
        if set(languages) & set(cyrillic_lang_list):
            return recognition_models['gen2']['cyrillic_g2']
        return recognition_models['gen2']['latin_g2']

    @classmethod
    def _get_required_model_filenames(cls, languages=None, detect_network: str = 'craft') -> List[str]:
        if detect_network not in detection_models:
            raise OCRRuntimeError(f"不支持的 EasyOCR 检测模型: {detect_network}")

        detector_filename = detection_models[detect_network]['filename']
        recognizer_filename = cls._get_recognition_model_config(languages)['filename']
        return [detector_filename, recognizer_filename]

    def ensure_local_models_ready(
        self,
        languages=None,
        model_storage_directory: Optional[str] = None,
        detect_network: Optional[str] = None,
    ) -> None:
        languages = list(languages or self.languages)
        model_storage_directory = self._resolve_model_storage_directory(
            model_storage_directory or self.model_storage_directory
        )
        detect_network = detect_network or self.detect_network
        os.makedirs(model_storage_directory, exist_ok=True)

        required_files = self._get_required_model_filenames(languages, detect_network)
        missing_files = [
            filename
            for filename in required_files
            if not os.path.isfile(os.path.join(model_storage_directory, filename))
        ]
        if missing_files:
            raise OCRRuntimeError(
                "本地 EasyOCR 模型缺失，已禁用在线下载。"
                f"请将以下文件预置到目录 {model_storage_directory}: {', '.join(missing_files)}"
            )

    def get_easyocr_reader(
        self,
        languages=None,
        use_gpu=None,
        model_storage_directory: Optional[str] = None,
        download_enabled: Optional[bool] = None,
        detect_network: Optional[str] = None,
    ):
        """
        获取或创建 EasyOCR reader 实例（延迟初始化，单例模式）。
        """
        if not EASYOCR_AVAILABLE:
            raise ImportError("EasyOCR 未安装，请运行: pip install easyocr")

        languages = list(languages or self.languages or ['en'])
        use_gpu = self.use_gpu if use_gpu is None else use_gpu
        model_storage_directory = self._resolve_model_storage_directory(
            model_storage_directory or self.model_storage_directory
        )
        download_enabled = self.download_enabled if download_enabled is None else download_enabled
        detect_network = detect_network or self.detect_network

        self.ensure_local_models_ready(languages, model_storage_directory, detect_network)

        reader_config = (
            tuple(languages),
            bool(use_gpu),
            model_storage_directory,
            bool(download_enabled),
            detect_network,
        )
        if (
            type(self)._easyocr_reader is None
            or type(self)._easyocr_reader_config != reader_config
        ):
            try:
                logger.info(
                    f"初始化 EasyOCR reader (语言: {languages}, GPU: {use_gpu}, 模型目录: {model_storage_directory})..."
                )
                type(self)._easyocr_reader = easyocr.Reader(
                    languages,
                    gpu=use_gpu,
                    model_storage_directory=model_storage_directory,
                    download_enabled=download_enabled,
                    detect_network=detect_network,
                )
                type(self)._easyocr_reader_config = reader_config
                logger.info("EasyOCR reader 初始化完成")
            except Exception as e:
                logger.error(f"EasyOCR 初始化失败: {e}")
                model_hint = self._get_model_directory_hint(model_storage_directory)
                raise OCRRuntimeError(f"EasyOCR 初始化失败: {e}{model_hint}") from e
        return type(self)._easyocr_reader
    
    @staticmethod
    def _get_image_hash(img) -> str:
        """
        计算图片的hash值用于缓存
        
        Args:
            img: PIL Image 或 numpy array
            
        Returns:
            图片的 MD5 hash 值
        """
        if isinstance(img, Image.Image):
            img_array = np.array(img)
        else:
            img_array = img
        return hashlib.md5(img_array.tobytes()).hexdigest()
    
    @classmethod
    def _get_cache_key(cls, region: Tuple, img_hash: str) -> Tuple:
        """生成缓存key"""
        return (tuple(region), img_hash)
    
    @classmethod
    def _clean_cache(cls):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, timestamp) in cls._ocr_cache.items()
            if current_time - timestamp > cls._cache_ttl
        ]
        for key in expired_keys:
            cls._ocr_cache.pop(key, None)
        
        # 如果缓存仍然太大，删除最旧的条目
        if len(cls._ocr_cache) > cls._cache_max_size:
            sorted_items = sorted(
                cls._ocr_cache.items(),
                key=lambda x: x[1][1]  # 按时间戳排序
            )
            # 删除最旧的一半
            for key, _ in sorted_items[:len(sorted_items)//2]:
                cls._ocr_cache.pop(key, None)
    
    def recognize_text(self, img, min_confidence=0.3, use_cache=True) -> str:
        """
        识别图片中的文本
        
        Args:
            img: PIL Image 对象
            min_confidence: 最小置信度阈值
            use_cache: 是否使用缓存
            
        Returns:
            识别出的文本字符串
        """
        if not EASYOCR_AVAILABLE:
            logger.error("EasyOCR 未安装，无法进行文字识别")
            return ""
        
        # 检查缓存
        img_hash = None
        cache_key = None
        if use_cache:
            img_hash = self._get_image_hash(img)
            cache_key = (img_hash,)  # 简化的缓存键
            if cache_key in self._ocr_cache:
                result, timestamp = self._ocr_cache[cache_key]
                if time.time() - timestamp < self._cache_ttl:
                    logger.debug(f"使用缓存 OCR 结果: {result}")
                    return result
        
        try:
            reader = self.get_easyocr_reader(self.languages, self.use_gpu)
            
            # 图像预处理
            if isinstance(img, Image.Image):
                # 转换为 RGB
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # 图片较小时放大以提高识别率
                width, height = img.size
                if width < 1000 or height < 200:
                    scale_factor = 2
                    img = img.resize(
                        (width * scale_factor, height * scale_factor),
                        Image.LANCZOS
                    )
                    logger.debug(f"图片放大 {scale_factor} 倍以提高识别率")
                
                img_array = np.array(img)
            else:
                img_array = img
                if len(img_array.shape) == 2:
                    # 灰度图转 RGB
                    img_array = np.stack([img_array] * 3, axis=-1)
            
            # EasyOCR 识别
            results = reader.readtext(img_array)
            
            # 提取文本，按从左到右排序
            text_items = []
            for (bbox, text, confidence) in results:
                if float(confidence) >= min_confidence:
                    x_coord = bbox[0][0]  # 左上角的 x 坐标
                    text_items.append((x_coord, text, float(confidence)))
                    logger.debug(f"OCR: '{text}', 置信度: {confidence:.2f}, x: {x_coord:.1f}")
            
            # 按 x 坐标排序
            text_items.sort(key=lambda x: x[0])
            texts = [item[1] for item in text_items]
            combined_text = ' '.join(texts)
            
            # 缓存结果
            if use_cache and cache_key:
                self._ocr_cache[cache_key] = (combined_text, time.time())
                self._clean_cache()
            
            logger.info(f"OCR 识别结果: '{combined_text}'")
            return combined_text.strip()
            
        except OCRRuntimeError:
            raise
        except Exception as e:
            logger.error(f"OCR 识别失败: {e}")
            raise OCRRuntimeError(f"OCR 识别失败: {e}") from e
    
    def recognize_number(self, img, allow_comma=True, use_cache=True) -> int:
        """
        识别图片中的数字
        
        Args:
            img: PIL Image 对象
            allow_comma: 是否允许逗号分隔符
            use_cache: 是否使用缓存
            
        Returns:
            识别出的数字（整数）
        """
        text = self.recognize_text(img, use_cache=use_cache)
        
        # 常见字符替换
        text = text.replace('o', '0').replace('O', '0')  # o/O -> 0
        text = text.replace('l', '1').replace('I', '1')  # l/I -> 1
        text = text.replace('?', '1')  # ? -> 1
        
        # 提取数字和逗号
        if allow_comma:
            digits = ''.join(filter(lambda x: x.isdigit() or x == ',', text))
            digits = digits.replace(',', '')
        else:
            digits = ''.join(filter(str.isdigit, text))
        
        try:
            number = int(digits) if digits else 0
            logger.info(f"提取数字: {number}")
            return number
        except ValueError:
            logger.error(f"无法将文本转换为数字: {text}")
            return 0
    
    def _prepare_image_array(self, img) -> np.ndarray:
        """将输入图片统一转换为 EasyOCR 可识别的 RGB ndarray。"""
        if isinstance(img, Image.Image):
            if img.mode != 'RGB':
                img = img.convert('RGB')
            width, height = img.size
            if width < 1000 or height < 200:
                scale_factor = 2
                img = img.resize((width * scale_factor, height * scale_factor), Image.LANCZOS)
            return np.array(img)

        img_array = img
        if len(img_array.shape) == 2:
            img_array = np.stack([img_array] * 3, axis=-1)
        return img_array

    def recognize_with_boxes(self, img, min_confidence=0.3) -> List[Dict[str, Any]]:
        """识别图片中的文本并返回带 bbox/center 的结果。"""
        if not EASYOCR_AVAILABLE:
            logger.error("EasyOCR 未安装，无法进行文字定位")
            return []

        try:
            reader = self.get_easyocr_reader(self.languages, self.use_gpu)
            img_array = self._prepare_image_array(img)
            results = reader.readtext(img_array)
            text_items: List[Dict[str, Any]] = []
            for bbox, text, confidence in results:
                confidence_value = float(confidence)
                if confidence_value < min_confidence:
                    continue
                center_x = int(sum(point[0] for point in bbox) / len(bbox))
                center_y = int(sum(point[1] for point in bbox) / len(bbox))
                text_items.append({
                    'text': str(text).strip(),
                    'confidence': confidence_value,
                    'bbox': [(int(point[0]), int(point[1])) for point in bbox],
                    'center': (center_x, center_y),
                })
            text_items.sort(key=lambda item: (item['bbox'][0][1], item['bbox'][0][0]))
            return text_items
        except OCRRuntimeError:
            raise
        except Exception as e:
            logger.error(f"OCR 文字定位失败: {e}")
            raise OCRRuntimeError(f"OCR 文字定位失败: {e}") from e

    def find_text(
        self,
        target_text: str,
        match_mode: str = 'contains',
        region: Optional[Tuple[int, int, int, int]] = None,
        index: int = 0,
        min_confidence: float = 0.3,
        screenshot_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """在整屏或指定区域中查找目标文字并返回位置。"""
        if not target_text:
            return None

        offset_x = 0
        offset_y = 0
        if region:
            img = self.crop_region(region, screenshot_path)
            offset_x, offset_y = int(region[0]), int(region[1])
        elif screenshot_path and os.path.exists(screenshot_path):
            img_cv = cv2.imread(screenshot_path)
            if img_cv is None:
                return None
            img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))
        else:
            airtest_sleep(0.3)
            img_cv = G.DEVICE.snapshot()
            if img_cv is None:
                return None
            img = Image.fromarray(cv2.cvtColor(img_cv, cv2.COLOR_BGR2RGB))

        target_normalized = re.sub(r'\s+', '', str(target_text)).lower()
        candidates = []
        for item in self.recognize_with_boxes(img, min_confidence=min_confidence):
            item_text_normalized = re.sub(r'\s+', '', str(item.get('text', ''))).lower()
            if not item_text_normalized:
                continue
            matched = (
                item_text_normalized == target_normalized
                if match_mode == 'exact'
                else target_normalized in item_text_normalized
            )
            if not matched:
                continue
            bbox = [(x + offset_x, y + offset_y) for x, y in item['bbox']]
            center = (item['center'][0] + offset_x, item['center'][1] + offset_y)
            candidates.append({
                **item,
                'bbox': bbox,
                'center': center,
            })

        if not candidates:
            return None
        if -len(candidates) <= index < len(candidates):
            return candidates[index]
        return None

    @staticmethod
    def crop_region(region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> Image.Image:
        """
        裁剪屏幕指定区域
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选，如果不提供则实时截图）
            
        Returns:
            裁剪后的 PIL Image
        """
        if screenshot_path and os.path.exists(screenshot_path):
            # 从文件加载
            img_cv = cv2.imread(screenshot_path)
        else:
            # 实时截图
            airtest_sleep(0.3)
            img_cv = G.DEVICE.snapshot()
            if img_cv is None:
                raise RuntimeError("截图失败，snapshot 返回 None")
        
        # 裁剪
        x1, y1, x2, y2 = region
        cropped = img_cv[y1:y2, x1:x2]
        
        # 转换为 PIL Image
        pil_img = Image.fromarray(cv2.cvtColor(cropped, cv2.COLOR_BGR2RGB))
        
        # 增强对比度
        pil_img = ImageEnhance.Contrast(pil_img).enhance(2.0)
        
        return pil_img
    
    def recognize_region_text(self, region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> str:
        """
        识别屏幕指定区域的文本
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选）
            
        Returns:
            识别出的文本
        """
        img = self.crop_region(region, screenshot_path)
        return self.recognize_text(img)
    
    def recognize_region_number(self, region: Tuple[int, int, int, int], screenshot_path: Optional[str] = None) -> int:
        """
        识别屏幕指定区域的数字
        
        Args:
            region: 坐标元组 (x1, y1, x2, y2)
            screenshot_path: 截图文件路径（可选）
            
        Returns:
            识别出的数字
        """
        img = self.crop_region(region, screenshot_path)
        return self.recognize_number(img)


# 全局单例实例
_ocr_helper_instance = None


def get_ocr_helper(
    languages=None,
    use_gpu=False,
    model_storage_directory: Optional[str] = None,
    download_enabled: bool = False,
    detect_network: str = 'craft',
) -> OCRHelper:
    """
    获取全局 OCR Helper 单例实例

    Args:
        languages: OCR 识别语言列表
        use_gpu: 是否使用 GPU
        model_storage_directory: EasyOCR 模型目录
        download_enabled: 是否允许在线下载模型
        detect_network: EasyOCR 检测模型

    Returns:
        OCRHelper 实例
    """
    global _ocr_helper_instance
    languages = list(languages or ['en'])
    resolved_model_storage_directory = OCRHelper._resolve_model_storage_directory(model_storage_directory)

    if (
        _ocr_helper_instance is None
        or _ocr_helper_instance.languages != languages
        or _ocr_helper_instance.use_gpu != use_gpu
        or _ocr_helper_instance.model_storage_directory != resolved_model_storage_directory
        or _ocr_helper_instance.download_enabled != download_enabled
        or _ocr_helper_instance.detect_network != detect_network
    ):
        _ocr_helper_instance = OCRHelper(
            languages=languages,
            use_gpu=use_gpu,
            model_storage_directory=resolved_model_storage_directory,
            download_enabled=download_enabled,
            detect_network=detect_network,
        )
    return _ocr_helper_instance
