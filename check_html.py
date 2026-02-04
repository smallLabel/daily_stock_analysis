#!/usr/bin/env python3
from web.handlers import get_page_handler
h = get_page_handler()
page = h.handle_index()
content = page.body.decode('utf-8')

# 查找所有script标签
import re
scripts = re.findall(r'<script>(.*?)</script>', content, re.DOTALL)
print('找到', len(scripts), '个script标签')

for i, script in enumerate(scripts):
    print(f'\n--- Script {i+1} (长度: {len(script)}) ---')
    # 检查是否有分析相关代码
    if 'submitAnalysis' in script:
        print('包含submitAnalysis函数')
        # 保存到文件
        with open(f'temp_js_{i}.js', 'w', encoding='utf-8') as f:
            f.write(script)
        print(f'已保存到 temp_js_{i}.js')
