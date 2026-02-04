# -*- coding: utf-8 -*-
"""
===================================
分页组件 - 类似 ElementUI 的分页组件
===================================

职责：
1. 提供可复用的分页UI组件
2. 支持配置页大小、总记录数
3. 支持页码变化回调
"""

from nicegui import ui
from typing import Callable, Optional


class Pagination:
    """分页组件"""
    
    def __init__(
        self,
        total: int,
        page_size: int = 10,
        current_page: int = 1,
        on_page_change: Optional[Callable[[int], None]] = None,
        layout: str = 'prev, pager, next',
        page_count: Optional[int] = None
    ):
        """
        初始化分页组件
        
        Args:
            total: 总记录数
            page_size: 每页记录数（默认10）
            current_page: 当前页码（默认1）
            on_page_change: 页码变化回调函数
            layout: 分页布局 ('prev, pager, next' | 'total, prev, pager, next')
            page_count: 显示的页码按钮数量（默认7）
        """
        self.total = total
        self.page_size = page_size
        self.current_page = current_page
        self.on_page_change = on_page_change
        self.layout = layout
        self.page_count = page_count or 7
        
        self.total_pages = (total + page_size - 1) // page_size
        
        # UI组件
        self.info_label = None
        self.buttons_container = None
        
        # 构建UI
        self._build_ui()
    
    def _build_ui(self):
        """构建分页UI"""
        with ui.row().classes('w-full items-center justify-between shrink-0 mt-2 mb-2.5'):
            # 左侧：总记录数信息
            self.info_label = ui.label(f'共 {self.total} 条记录').classes('text-xs text-zinc-500')
            
            # 右侧：分页按钮
            self.buttons_container = ui.row().classes('items-center gap-1')
            
            with self.buttons_container:
                self._render_buttons()
    
    def _render_buttons(self):
        """渲染分页按钮"""
        self.buttons_container.clear()
        
        with self.buttons_container:
            # 上一页按钮
            if self.current_page > 1:
                ui.button(
                    icon='chevron_left',
                    on_click=lambda: self._go_to_page(self.current_page - 1)
                ).props('unelevated square').classes('bg-[#27272A] hover:bg-[#3F3F46] text-white').style('min-width: 36px; height: 36px;')
            else:
                ui.button(
                    icon='chevron_left',
                    on_click=None
                ).props('unelevated square disable').classes('bg-[#18181B] text-zinc-600').style('min-width: 36px; height: 36px;')
            
            # 页码按钮
            self._render_page_numbers()
            
            # 下一页按钮
            if self.current_page < self.total_pages:
                ui.button(
                    icon='chevron_right',
                    on_click=lambda: self._go_to_page(self.current_page + 1)
                ).props('unelevated square').classes('bg-[#27272A] hover:bg-[#3F3F46] text-white').style('min-width: 36px; height: 36px;')
            else:
                ui.button(
                    icon='chevron_right',
                    on_click=None
                ).props('unelevated square disable').classes('bg-[#18181B] text-zinc-600').style('min-width: 36px; height: 36px;')
    
    def _render_page_numbers(self):
        """渲染页码按钮"""
        pages = self._get_visible_pages()
        
        for page in pages:
            if page == '...':
                ui.button(
                    '...',
                    on_click=None
                ).props('unelevated square disable').classes('bg-[#18181B] text-zinc-600').style('min-width: 36px; height: 36px;')
            elif page == self.current_page:
                ui.button(
                    str(page),
                    on_click=None
                ).props('unelevated square').classes('bg-blue-600 hover:bg-blue-700 text-white font-medium').style('min-width: 36px; height: 36px;')
            else:
                ui.button(
                    str(page),
                    on_click=lambda p=page: self._go_to_page(p)
                ).props('unelevated square').classes('bg-[#27272A] hover:bg-[#3F3F46] text-white').style('min-width: 36px; height: 36px;')
    
    def _get_visible_pages(self):
        """获取可见的页码列表"""
        if self.total_pages <= self.page_count:
            return list(range(1, self.total_pages + 1))
        
        # 计算当前页附近的页码
        half = self.page_count // 2
        start = max(1, self.current_page - half)
        end = min(self.total_pages, start + self.page_count - 1)
        
        # 调整start以确保显示足够多的页码
        if end - start + 1 < self.page_count:
            start = max(1, end - self.page_count + 1)
        
        pages = list(range(start, end + 1))
        
        # 添加省略号
        if start > 1:
            pages.insert(0, '...')
        if end < self.total_pages:
            pages.append('...')
        
        return pages
    
    def _go_to_page(self, page_num: int):
        """跳转到指定页"""
        if page_num != self.current_page and 1 <= page_num <= self.total_pages:
            self.current_page = page_num
            self._render_buttons()
            if self.on_page_change:
                self.on_page_change(page_num)
    
    def set_total(self, total: int):
        """设置总记录数"""
        self.total = total
        self.total_pages = (total + self.page_size - 1) // self.page_size
        self.info_label.text = f'共 {total} 条记录'
        self._render_buttons()
    
    def set_page_size(self, page_size: int):
        """设置每页记录数"""
        self.page_size = page_size
        self.total_pages = (self.total + page_size - 1) // page_size
        self._render_buttons()
    
    def set_current_page(self, page_num: int):
        """设置当前页"""
        self._go_to_page(page_num)
    
    def get_current_page(self) -> int:
        """获取当前页码"""
        return self.current_page
    
    def get_total_pages(self) -> int:
        """获取总页数"""
        return self.total_pages
    
    def get_page_data(self, data: list) -> list:
        """获取当前页的数据"""
        start_idx = (self.current_page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, self.total)
        return data[start_idx:end_idx]


def create_pagination(
    total: int,
    page_size: int = 10,
    current_page: int = 1,
    on_page_change: Optional[Callable[[int], None]] = None,
    layout: str = 'prev, pager, next',
    page_count: Optional[int] = None
) -> Pagination:
    """
    创建分页组件的便捷函数
    
    Args:
        total: 总记录数
        page_size: 每页记录数（默认10）
        current_page: 当前页码（默认1）
        on_page_change: 页码变化回调函数
        layout: 分页布局
        page_count: 显示的页码按钮数量
    
    Returns:
        Pagination: 分页组件实例
    """
    return Pagination(
        total=total,
        page_size=page_size,
        current_page=current_page,
        on_page_change=on_page_change,
        layout=layout,
        page_count=page_count
    )
