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
        Extract stock codes and names using coordinate-aware matching.
        """
        try:
            if not os.path.exists(image_path):
                logger.error(f"Image file does not exist: {image_path}")
                return []
            ocr = self._get_ocr_instance()
            text_blocks = [] # List of {'text': str, 'center_y': float, 'center_x': float, 'height': float}

            # --- 1. Extract raw blocks based on engine ---
            if self.engine_type == 'paddle':
                # Paddle returns: [[[[x1,y1]...], ('text', score)], ...]
                result = ocr.ocr(image_path)
                if result and result[0]:
                    for line in result[0]:
                        box = line[0] # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
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
                # CnOCR returns: [{'text': '...', 'position': [[x,y]...], 'score': ...}]
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
            
            # Debug: Log raw OCR blocks
            logger.info(f"Raw OCR blocks count: {len(text_blocks)}")
            if len(text_blocks) > 0:
                logger.debug(f"First 5 blocks: {text_blocks[:5]}")
            
            if not text_blocks:
                logger.warning("OCR found no text blocks")
                return []

            img_w, img_h = self._get_image_size(image_path)
            is_portrait = img_h > img_w
            logger.info(f"Image size: {img_w}x{img_h}, Portrait: {is_portrait}, Text blocks: {len(text_blocks)}")

            # 竖屏时优先用移动端纵行解析（同花顺 App 竖屏也是左侧名称+代码纵行，不是横表）
            if is_portrait and self._is_mobile_portrait_style(text_blocks, img_w, img_h):
                logger.info("Detected mobile portrait layout, using left-side vertical parser.")
                result = self._match_codes_and_names_mobile_vertical(text_blocks, img_w, img_h)
                logger.info(f"Mobile vertical parser found {len(result)} stocks")
                return self._enhance_results(result)

            # 同花顺横屏/表格式：表头 代码|名称|现价...
            if self._is_tonghuashun_style(text_blocks):
                logger.info("Detected Tonghuashun-style watchlist layout, using table parser.")
                result = self._match_codes_and_names_tonghuashun(text_blocks)
                logger.info(f"Tonghuashun parser found {len(result)} stocks")
                return self._enhance_results(result)

            logger.info(f"OCR found {len(text_blocks)} text blocks. Using generic parser...")
            result = self._match_codes_and_names(text_blocks)
            msg = f"Generic parser found {len(result)} stocks"
            logger.info(msg)
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
            # 6 位连续数字出现多次，也判定为股票列表
            if re.search(r'(\d{6})', t):
                return True
        return False

    def _match_codes_and_names_tonghuashun(self, blocks: List[Dict]) -> List[Dict[str, str]]:
        """
        针对同花顺自选股截图：按行分组，同行内按 X 排序，取第一个 6 位数字为代码、紧随其后的有效中文为名称。
        过滤表头/页脚关键词，避免误识别。
        """
        code_pattern = re.compile(r'(\d{6})')
        # 按 Y 分组为行（同一行 Y 差在约 0.8 倍平均高度内）
        rows = self._group_blocks_into_rows(blocks)
        extracted = []
        for row_blocks in rows:
            # 按 center_x 排序，模拟从左到右的列
            row_blocks = sorted(row_blocks, key=lambda b: b['center_x'])
            if self._looks_like_header_row(row_blocks):
                continue
            code = None
            name = ''
            for b in row_blocks:
                text = (b.get('text') or '').strip()
                if not text:
                    continue
                if text in THS_HEADER_FOOTER:
                    continue
                m = code_pattern.search(text)
                if m and code is None:
                    code = m.group(1)
                    # 同块内代码后的内容可能是名称，如 "600519 贵州茅台"
                    remains = text[: m.start()] + text[m.end() :]
                    remains = re.sub(r'[\s\d\.\-]+', '', remains).strip()
                    if self._is_valid_name(remains) and remains not in THS_HEADER_FOOTER:
                        name = self._clean_name(remains)
                    continue
                if code is not None and not name and self._is_valid_name(text) and text not in THS_HEADER_FOOTER:
                    # 过滤纯数字/价格
                    if not re.match(r'^[\d\.,\+%¥\-]+$', text):
                        name = self._clean_name(text)
                        break
            if code:
                extracted.append({'code': code, 'name': name or ''})
        # 去重（同代码保留带名称的）
        final_map = {}
        for item in extracted:
            c = item['code']
            if c not in final_map or (not final_map[c]['name'] and item['name']):
                final_map[c] = item

        # 后备方案：遍历所有文本块，提取 6 位数字代码
        code_pattern = re.compile(r'(\d{6})')
        for b in blocks:
            text = (b.get('text') or '').strip()
            codes = code_pattern.findall(text)
            for code in codes:
                if code not in final_map:
                    final_map[code] = {'code': code, 'name': ''}

        return list(final_map.values())

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
            # 竖屏时，若多数块在左侧则视为移动端列表
            left_blocks = [b for b in blocks if b['center_x'] < img_w * MOBILE_LEFT_RATIO]
            return len(left_blocks) >= max(2, len(blocks) * 0.4)
        # 无尺寸时根据 Y 方向跨度大、块数较多推测为竖屏列表
        if len(blocks) < 2:
            return False
        ys = [b['center_y'] for b in blocks]
        y_span = max(ys) - min(ys)
        avg_h = np.mean([b['height'] for b in blocks]) or 1
        return y_span > avg_h * 4

    def _match_codes_and_names_mobile_vertical(
        self, blocks: List[Dict], img_w: int, img_h: int
    ) -> List[Dict[str, str]]:
        """
        移动端竖屏：仅用左侧区域，按 Y 排序后纵行配对。
        每行上方是股票名称、下方是 6 位股票代码（同花顺等会带「融」等后缀，只取前 6 位数字）。
        """
        code_6 = re.compile(r'(\d{6})')
        # 块内"以 6 位数字为主"即视为代码块（允许前有空格、后有「融」等）
        def block_looks_like_code(t: str) -> Optional[str]:
            t = (t or '').strip()
            m = code_6.search(t)
            if not m:
                return None
            code = m.group(0)
            # 移除严格的 before/after 检查，只提取 6 位代码
            return code

        # 聚焦左侧
        if img_w > 0:
            left_blocks = [b for b in blocks if b['center_x'] < img_w * MOBILE_LEFT_RATIO]
        else:
            xs = [b['center_x'] for b in blocks]
            x_max = max(xs) if xs else 1
            left_blocks = [b for b in blocks if b['center_x'] < x_max * MOBILE_LEFT_RATIO]

        if not left_blocks:
            left_blocks = blocks

        # 按 center_y 从上到下排序（纵行）
        sorted_blocks = sorted(left_blocks, key=lambda b: b['center_y'])
        avg_height = np.mean([b['height'] for b in sorted_blocks]) or 20
        max_gap = avg_height * MOBILE_NAME_CODE_Y_RATIO

        extracted = []
        i = 0
        while i < len(sorted_blocks):
            block = sorted_blocks[i]
            text = (block.get('text') or '').strip()
            # 块内主要为 6 位代码（含「600963融」等形式）
            # Case 3: Code is in Current Block, Name might be in NEXT Block (Reverse Order: Code above Name)
            code = block_looks_like_code(text)
            if code:
                # 3.1 Try Previous Block (Name above Code - Standard)
                if i > 0:
                    prev = sorted_blocks[i - 1]
                    prev_text = (prev.get('text') or '').strip()
                    if (
                        abs(block['center_y'] - prev['center_y']) <= max_gap
                        and self._is_valid_name(prev_text)
                        and prev_text not in THS_HEADER_FOOTER
                        and block_looks_like_code(prev_text) is None
                    ):
                        name = self._clean_name(prev_text)
                        logger.debug(f"Row {i} - Matched [Name Code] Vertical: {name} -> {code}")
                        extracted.append({'code': code, 'name': name})
                        i += 1
                        continue

                # 3.2 Try Next Block (Code above Name - Rare/Eastmoney app sometimes)
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    next_text = (next_block.get('text') or '').strip()
                    if (
                        abs(next_block['center_y'] - block['center_y']) <= max_gap
                        and self._is_valid_name(next_text)
                        and next_text not in THS_HEADER_FOOTER
                        and block_looks_like_code(next_text) is None
                    ):
                        name = self._clean_name(next_text)
                        logger.debug(f"Row {i} - Matched [Code Name] Vertical: {code} -> {name}")
                        extracted.append({'code': code, 'name': name})
                        i += 2 # Skip next block as it is used
                        continue
                
                # If no name found, just add code
                extracted.append({'code': code, 'name': ''})
                i += 1
                continue
            # 当前块像名称：看下一块是否含 6 位代码
            if self._is_valid_name(text) and text not in THS_HEADER_FOOTER:
                if i + 1 < len(sorted_blocks):
                    next_block = sorted_blocks[i + 1]
                    next_text = (next_block.get('text') or '').strip()
                    next_clean = re.sub(r'\s+', '', next_text)
                    m = re.search(r'\d{6}', next_clean)
                    if m:
                        code = m.group(0)
                        extracted.append({'code': code, 'name': self._clean_name(text)})
                        i += 2
                        continue
            # 同一块内同时有名称和代码
            m = code_6.search(text)
            if m:
                code = m.group(0)
                name_before = re.sub(r'[\d\s\.\-]+', '', text[: m.start()]).strip()
                name_after = re.sub(r'[\d\s\.\-融]+', '', text[m.end() :]).strip()
                
                # Check for "Code Name" (e.g. "600519 茅台")
                if name_after and self._is_valid_name(name_after) and name_after not in THS_HEADER_FOOTER:
                     name = self._clean_name(name_after)
                     logger.debug(f"Row {i} - Matched [Code Name] in block: {code} -> {name}")
                     extracted.append({'code': code, 'name': name})
                     i += 1
                     continue
                
                # Check for "Name Code" (e.g. "茅台 600519")
                if name_before and self._is_valid_name(name_before) and name_before not in THS_HEADER_FOOTER:
                     name = self._clean_name(name_before)
                     logger.debug(f"Row {i} - Matched [Name Code] in block: {code} -> {name}")
                     extracted.append({'code': code, 'name': name})
                     i += 1
                     continue
            i += 1
        
        logger.info(f"Mobile vertical parser matched {len(extracted)} items before dedup")

        # 去重
        final_map = {}
        for item in extracted:
            c = item['code']
            if c not in final_map or (not final_map[c]['name'] and item['name']):
                final_map[c] = item

        # 如果没有识别到任何股票，尝试简单提取所有 6 位代码作为后备
        if not final_map:
            logger.warning("Mobile vertical parser found no stocks with names, trying fallback extraction")
            for b in sorted_blocks:
                text = (b.get('text') or '').strip()
                m = re.search(r'(\d{6})', text)
                if m:
                    code = m.group(0)
                    if code not in final_map:
                        final_map[code] = {'code': code, 'name': ''}

        return list(final_map.values())

    def _match_codes_and_names(self, blocks: List[Dict]) -> List[Dict[str, str]]:
        """
        Match 6-digit stock codes to adjacent names using geometric proximity.
        """
        extracted = []
        code_pattern = re.compile(r'(\d{6})')
        
        # Sort blocks by Y then X for easier debugging (optional)
        # blocks.sort(key=lambda b: (b['center_y'], b['center_x']))

        for i, block in enumerate(blocks):
            text = block['text']
            
            # Use findall to catch multiple codes in one line (rare but possible)
            codes = code_pattern.findall(text)
            
            for code in codes:
                item = {'code': code, 'name': ''}
                
                # Strategy 1: Check if name is INSIDE the same block
                # e.g. "600519 贵州茅台"
                remains = text.replace(code, '').strip()
                if self._is_valid_name(remains):
                    item['name'] = self._clean_name(remains)
                
                # Strategy 2: Look for neighbors in the same Row
                if not item['name']:
                    # Define "Same Row": Center Y difference is small relative to text height
                    # We accept roughly 80% of height deviation
                    
                    candidates = []
                    for j, other in enumerate(blocks):
                        if i == j: continue # Skip self
                        
                        y_diff = abs(block['center_y'] - other['center_y'])
                        avg_h = (block['height'] + other['height']) / 2
                        
                        if y_diff < avg_h * 0.8: # Same visual row
                            # Calculate horizontal distance
                            dist = abs(block['center_x'] - other['center_x'])
                            candidates.append((dist, other['text']))
                    
                    # Sort candidates by distance (closest first)
                    candidates.sort(key=lambda x: x[0])
                    
                    # Pick the first valid name
                    for dist, candidate_text in candidates:
                        if self._is_valid_name(candidate_text):
                            item['name'] = self._clean_name(candidate_text)
                            logger.debug(f"Row Match: {code} <-> {candidate_text} (dist={dist:.1f})")
                            break
                            
                extracted.append(item)
        
        logger.info(f"Generic parser extracted {len(extracted)} potential items")
        
        # Deduplicate results (prefer entries with names)
        # If we have [{'code': '000001', 'name': ''}, {'code': '000001', 'name': '平安银行'}]
        # we want to keep the one with the name.
        final_map = {}
        for item in extracted:
            c = item['code']
            if c not in final_map:
                final_map[c] = item
            else:
                # If existing has no name but new one does, update
                if not final_map[c]['name'] and item['name']:
                    final_map[c] = item
        
        return list(final_map.values())

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

