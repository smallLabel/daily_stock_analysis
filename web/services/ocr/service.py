# -*- coding: utf-8 -*-
"""
===================================
OCR 服务 - 股票代码/名称识别
===================================

职责：
1. 基于 PaddleOCR/CnOCR 从截图提取文本块
2. 匹配 6 位股票代码与相邻名称
3. 针对同花顺自选股截图做表格式布局的专项识别
4. 针对移动端竖屏截图：聚焦左侧、纵行排列，上行名称、下行代码
"""

import logging
import re
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import os
from web.services.stock_data_service import get_stock_data_service
# import sqlite3 # Removed
# import datetime # Removed
# from data_provider import DataFetcherManager # Removed

logger = logging.getLogger(__name__)

# 移动端截图：仅保留图片左侧该比例内的块（右侧多为涨跌幅等）
MOBILE_LEFT_RATIO = 0.55
# 纵行内名称与代码的 Y 方向最大间距（相对平均行高）
MOBILE_NAME_CODE_Y_RATIO = 2.5

# 同花顺自选股截图：表头/页脚常见词，不当作股票名称
THS_HEADER_FOOTER = frozenset({
    '代码', '名称', '现价', '涨跌幅', '涨幅', '跌幅', '涨跌', '今开', '最高', '最低',
    '昨收', '成交量', '成交额', '振幅', '换手', '市盈', '市净', '总市值', '流通市值',
    '自选', '同花顺', '自选股', '股票', '添加', '删除', '全选', '取消',
    '上证指数', '最新', '资金', '资讯', '资产', '分析', '持仓股', '热门', '农业', '军工', '光伏',
})
# 同花顺表头关键词，出现则认为是表格式布局
THS_TABLE_MARKERS = ('代码', '名称', '同花顺', '自选')

class OCRService:
    def __init__(self):
        self.ocr = None
        self.engine_type = None # 'paddle' or 'cnocr'
        
    def _get_ocr_instance(self):
        """Lazy load OCR model, prioritizing CnOCR"""
        if self.ocr is None:
            # 1. Try CnOCR (Priority)
            try:
                from cnocr import CnOcr
                self.ocr = CnOcr() 
                self.engine_type = 'cnocr'
                logger.info("CnOcr initialized successfully")
                return self.ocr
            except ImportError:
                logger.warning("CnOcr not installed or import failed.")
            except Exception as e:
                logger.warning(f"Failed to initialize CnOcr: {e}")

            # 2. Try PaddleOCR (Fallback)
            try:
                from paddleocr import PaddleOCR
                # Set environment variable to skip connection check
                import os
                os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
                self.ocr = PaddleOCR(lang="ch")
                self.engine_type = 'paddle'
                logger.info("PaddleOCR initialized successfully")
                return self.ocr
            except ImportError:
                logger.warning("PaddleOCR not installed or import failed.")
            except Exception as e:
                logger.error(f"Failed to initialize PaddleOCR: {e}")
            
            if self.ocr is None:
                raise RuntimeError("No suitable OCR library found. Please install 'paddleocr' or 'cnocr'.")

        return self.ocr

    def _get_image_size(self, image_path: str) -> Tuple[int, int]:
        """返回 (width, height)，失败时从 blocks 估算则返回 (0, 0)。"""
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
                return (w, h)
        except Exception as e:
            logger.warning(f"PIL image size detection failed: {e}")
            pass
        try:
            import cv2
            img = cv2.imread(image_path)
            if img is not None:
                h, w = img.shape[:2]
                return (w, h)
        except Exception as e:
            logger.warning(f"OpenCV image size detection failed: {e}")
            pass
        logger.warning(f"Could not detect image size for {image_path}")
        return (0, 0)

    def extract_stocks_from_image(self, image_path: str) -> List[Dict[str, str]]:
        """
        Extract stock codes from image using coordinate-aware matching.
        仅提取股票代码，名称由 _enhance_results 从数据库匹配
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file does not exist: {image_path}")
                return []
            ocr = self._get_ocr_instance()
            text_blocks = [] # List of {'text': str, 'center_y': float, 'center_x': float, 'height': float}

            # --- 1. Extract raw blocks based on engine ---
            if self.engine_type == 'paddle':
                result = ocr.ocr(image_path)
                if result and result[0]:
                    for line in result[0]:
                        box = line[0]
                        text = line[1][0]
                        
                        if isinstance(box, np.ndarray):
                            box = box.tolist()
                        
                        ys = [float(p[1]) for p in box]
                        height = max(ys) - min(ys)
                        center_y = sum(ys) / len(ys)
                        center_x = sum([float(p[0]) for p in box]) / len(box)
                        
                        text_blocks.append({
                            'text': text,
                            'center_y': center_y,
                            'center_x': center_x,
                            'height': height
                        })

            elif self.engine_type == 'cnocr':
                result = ocr.ocr(image_path)
                for line in result:
                    text = line['text']
                    box = line['position']
                    if isinstance(box, np.ndarray):
                        box = box.tolist()
                    
                    ys = [float(p[1]) for p in box]
                    height = max(ys) - min(ys)
                    center_y = sum(ys) / len(ys)
                    center_x = sum([float(p[0]) for p in box]) / len(box)
                    
                    text_blocks.append({
                        'text': text,
                        'center_y': center_y,
                        'center_x': center_x,
                        'height': height
                    })
            
            logger.info(f"Raw OCR blocks count: {len(text_blocks)}")
            if len(text_blocks) > 0:
                logger.debug(f"First 5 blocks: {text_blocks[:5]}")
            
            if not text_blocks:
                logger.warning("OCR found no text blocks")
                return []

            img_w, img_h = self._get_image_size(image_path)
            is_portrait = img_h > img_w
            logger.info(f"Image size: {img_w}x{img_h}, Portrait: {is_portrait}, Text blocks: {len(text_blocks)}")

            # 竖屏时优先用移动端纵行解析
            if is_portrait and self._is_mobile_portrait_style(text_blocks, img_w, img_h):
                logger.info("Detected mobile portrait layout, using left-side vertical parser.")
                result = self._extract_codes_mobile_vertical(text_blocks, img_w, img_h)
                logger.info(f"Mobile vertical parser found {len(result)} stock codes")
                return self._enhance_results(result)

            # 同花顺横屏/表格式：表头 代码|名称|现价...
            if self._is_tonghuashun_style(text_blocks):
                logger.info("Detected Tonghuashun-style watchlist layout, using table parser.")
                result = self._extract_codes_tonghuashun(text_blocks)
                logger.info(f"Tonghuashun parser found {len(result)} stock codes")
                return self._enhance_results(result)

            logger.info(f"OCR found {len(text_blocks)} text blocks. Using generic parser...")
            result = self._extract_codes_generic(text_blocks)
            logger.info(f"Generic parser found {len(result)} stock codes")
            return self._enhance_results(result)
            
        except Exception as e:
            logger.error(f"OCR extraction error: {e}", exc_info=True)
            return []

    def _is_tonghuashun_style(self, blocks: List[Dict]) -> bool:
        """若截图中出现同花顺/自选/代码/名称等表头特征，判定为同花顺表格式布局。"""
        for b in blocks:
            t = (b.get('text') or '').strip()
            for marker in THS_TABLE_MARKERS:
                if marker in t:
                    return True
            if re.search(r'(\d{6})', t):
                return True
        return False

    def _extract_codes_tonghuashun(self, blocks: List[Dict]) -> List[Dict[str, str]]:
        """
        针对同花顺自选股截图：提取 6 位股票代码。
        仅提取代码，名称由数据库匹配。
        """
        code_pattern = re.compile(r'(\d{6})')
        extracted = set()

        for b in blocks:
            text = (b.get('text') or '').strip()
            codes = code_pattern.findall(text)
            for code in codes:
                extracted.add(code)

        logger.info(f"Tonghuashun parser extracted {len(extracted)} stock codes")
        return [{'code': code, 'name': ''} for code in extracted]

    def _group_blocks_into_rows(self, blocks: List[Dict], row_threshold: float = 0.8) -> List[List[Dict]]:
        """按 center_y 将块分组成行，同一行内 Y 差 < row_threshold * 平均高度。"""
        if not blocks:
            return []
        sorted_by_y = sorted(blocks, key=lambda b: b['center_y'])
        rows: List[List[Dict]] = []
        current_row: List[Dict] = [sorted_by_y[0]]
        for b in sorted_by_y[1:]:
            avg_h = np.mean([x['height'] for x in current_row])
            if abs(b['center_y'] - current_row[-1]['center_y']) <= avg_h * row_threshold:
                current_row.append(b)
            else:
                rows.append(current_row)
                current_row = [b]
        if current_row:
            rows.append(current_row)
        return rows

    def _looks_like_header_row(self, row_blocks: List[Dict]) -> bool:
        """若该行文本主要由表头关键词组成，判定为表头行。"""
        texts = [(b.get('text') or '').strip() for b in row_blocks]
        if not texts:
            return False
        header_count = sum(1 for t in texts if t in THS_HEADER_FOOTER)
        return header_count >= min(2, len(texts))

    def _is_mobile_portrait_style(self, blocks: List[Dict], img_w: int, img_h: int) -> bool:
        """竖屏且内容偏左：height > width，或无法取尺寸时根据块分布判断。"""
        if img_w > 0 and img_h > 0:
            if img_h <= img_w:
                return False
            left_blocks = [b for b in blocks if b['center_x'] < img_w * MOBILE_LEFT_RATIO]
            return len(left_blocks) >= max(2, len(blocks) * 0.4)
        if len(blocks) < 2:
            return False
        ys = [b['center_y'] for b in blocks]
        y_span = max(ys) - min(ys)
        avg_h = np.mean([b['height'] for b in blocks]) or 1
        return y_span > avg_h * 4

    def _extract_codes_mobile_vertical(
        self, blocks: List[Dict], img_w: int, img_h: int
    ) -> List[Dict[str, str]]:
        """
        移动端竖屏：仅提取 6 位股票代码。
        仅提取代码，名称由数据库匹配。
        """
        code_pattern = re.compile(r'(\d{6})')
        
        if img_w > 0:
            left_blocks = [b for b in blocks if b['center_x'] < img_w * MOBILE_LEFT_RATIO]
        else:
            xs = [b['center_x'] for b in blocks]
            x_max = max(xs) if xs else 1
            left_blocks = [b for b in blocks if b['center_x'] < x_max * MOBILE_LEFT_RATIO]

        if not left_blocks:
            left_blocks = blocks

        extracted = set()
        for b in left_blocks:
            text = (b.get('text') or '').strip()
            codes = code_pattern.findall(text)
            for code in codes:
                extracted.add(code)

        logger.info(f"Mobile vertical parser extracted {len(extracted)} stock codes")
        return [{'code': code, 'name': ''} for code in extracted]

    def _extract_codes_generic(self, blocks: List[Dict]) -> List[Dict[str, str]]:
        """
        通用解析：仅提取 6 位股票代码。
        仅提取代码，名称由数据库匹配。
        """
        code_pattern = re.compile(r'(\d{6})')
        extracted = set()

        for block in blocks:
            text = block['text']
            codes = code_pattern.findall(text)
            for code in codes:
                extracted.add(code)

        logger.info(f"Generic parser extracted {len(extracted)} stock codes")
        return [{'code': code, 'name': ''} for code in extracted]

    def _is_valid_name(self, text: str) -> bool:
        """Check if text likely represents a stock name"""
        if not text: return False
        text = text.strip()
        
        # Filter numeric/price-like strings (strict)
        # Matches: 12.34, +12.34, -1.2%, 1,234, 12.34元
        if re.match(r'^[\d\.,\+%¥\-\s]+[元]?$', text): return False
        
        # Filter strings containing price patterns like "12.34" or "10%" mixed with minimal text
        if re.search(r'\d+\.\d{2}', text) or '%' in text:
             # If it has meaningful text, we might keep it (e.g. "ST 500"), but risky if it's "Vol 500"
             # For now, simplistic filter: if it has floating point or %, likely not a name
             return False

        # Filter very short strings (noise)
        if len(text) < 2: return False
        
        # Filter common keywords
        if text in THS_HEADER_FOOTER: return False

        return True

    def _clean_name(self, text: str) -> str:
        """Clean up stock name"""
        # Remove special chars often found in OCR noise
        text = re.sub(r'[^\w\u4e00-\u9fa5]+', '', text)
        return text

    def _enhance_results(self, results: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Enhance OCR results with data from database.
        1. Check if we have full market data (fetch if needed).
        2. Use code to lookup official name in DB.
        """
        if not results:
            return results
            
        try:
            service = get_stock_data_service()
            service.ensure_market_data()
            
            enhanced_count = 0
            for item in results:
                code = item.get('code')
                if code:
                    db_name = service.get_stock_name(code)
                    if db_name:
                        # Update/Fill name from DB
                        original_name = item.get('name', '')
                        if not original_name or original_name != db_name:
                            item['name'] = db_name
                            enhanced_count += 1
            
            if enhanced_count > 0:
                logger.info(f"Enhanced {enhanced_count} stocks with names from database")
                
        except Exception as e:
            logger.error(f"Failed to enhance OCR results with DB data: {e}", exc_info=True)
            
        return results

_ocr_service = None

def get_ocr_service():
    global _ocr_service
    if _ocr_service is None:
        _ocr_service = OCRService()
    return _ocr_service

