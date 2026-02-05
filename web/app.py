# -*- coding: utf-8 -*-
"""
===================================
NiceGUI 主入口 - 统一Web UI
===================================

职责：
1. 初始化NiceGUI应用
2. 注册API端点
3. 构建主界面
4. 集成分析、自选股、持仓管理功能

架构说明：
- 使用NiceGUI作为唯一UI框架
- API层通过web/api.py提供
- 业务逻辑复用web/services.py
"""

import sys
import os
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from nicegui import ui, app
from web.utils.theme import Colors, Styles, setup_theme
from web.services.api import register_api
from web.components.pagination import create_pagination
from web.services.history import load_history_page
import logging

logger = logging.getLogger(__name__)


# 初始化UI应用


# 导入系统设置页面 V2（自动注册 /settings_v2 路由）
import web.pages.settings
# 导入自选股选股页面（自动注册 /watchlist 路由）
import web.pages.watchlist

# 注册API端点
register_api()

# 添加自定义CSS



@ui.page('/')
def index_page():
    """首页 - 仪表盘"""
    # Initialize theme for this page
    setup_theme()
    
    # Add page-specific CSS
    ui.add_css('''
        .q-page-container {
            padding-top: 0px !important;
        }
        /* Modal Animations */
        .modal-fade-in {
            animation: fadeIn 0.2s ease-out;
        }
        .modal-content-in {
            animation: scaleIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes scaleIn { from { transform: scale(0.98); opacity: 0; } to { transform: scale(1); opacity: 1; } }
    ''')

    # Add JavaScript helper functions
    ui.add_head_html('''
    <script>
    let analysisPolling = null;
    let currentAnalysisData = null;
    let isAnalyzing = false;
    let currentStockCode = null;
    
    function validateStockCode(code) {
        if (!code || code.trim() === '') {
            ui.notify('请输入股票代码', {type: 'warning', position: 'top'});
            return false;
        }
        
        code = code.trim().toUpperCase();
        
        const aSharePattern = /^\d{6}$/;
        const hkSharePattern = /^(HK)?\d{5}$/;
        const usSharePattern = /^[A-Z]{1,5}$/;
        
        if (!aSharePattern.test(code) && !hkSharePattern.test(code) && !usSharePattern.test(code)) {
            ui.notify('股票代码格式不正确 (A股6位数字/港股5位/美股字母)', {type: 'warning', position: 'top'});
            return false;
        }
        
        return true;
    }
    
    function setAnalyzingState(analyzing) {
        isAnalyzing = analyzing;
        const button = document.querySelector('button[aria-label*="开始分析"], button:has(span:contains("开始分析"))');
        const inputs = document.querySelectorAll('input, select');
        
        if (analyzing) {
            if (button) {
                button.disabled = true;
                button.style.opacity = '0.6';
                button.style.cursor = 'not-allowed';
            }
            inputs.forEach(input => input.disabled = true);
        } else {
            if (button) {
                button.disabled = false;
                button.style.opacity = '1';
                button.style.cursor = 'pointer';
            }
            inputs.forEach(input => input.disabled = false);
        }
    }
    
    function showAnalysisResult() {
        const overlay = document.getElementById('analysis-overlay');
        if (overlay) {
            overlay.style.display = 'flex';
            document.body.style.overflow = 'hidden'; // Prevent background scrolling
            // Trigger animation
            const content = overlay.querySelector('.modal-window');
            if (content) {
                content.classList.remove('modal-content-in');
                void content.offsetWidth; // trigger reflow
                content.classList.add('modal-content-in');
            }
        }
    }
    
    function hideAnalysisResult() {
        const overlay = document.getElementById('analysis-overlay');
        if (overlay) {
            overlay.style.display = 'none';
            document.body.style.overflow = '';
        }
    }
    
    function showLoadingState(step = 'AI正在分析中...') {
        showAnalysisResult();
        
        const loadingHtml = `
            <div class="w-full flex flex-col items-center justify-center py-12" style="min-height: 400px;">
                <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mb-4"></div>
                <p class="text-zinc-400 text-sm">${step}</p>
                <p class="text-zinc-500 text-xs mt-2">正在获取行情数据、计算技术指标、搜索舆情资讯</p>
            </div>
        `;
        
        const card = document.querySelector('[id*="analysis-content"]');
        if (card) {
            card.innerHTML = loadingHtml;
        }
    }
    
    function showErrorState(message, code) {
        const retryButton = code ? `
            <button onclick="retryAnalysis('${code}')" 
                    class="mt-4 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm">
                重试分析
            </button>
        ` : '';
        
        const card = document.querySelector('[id*="analysis-content"]');
        if (card) {
            card.innerHTML = `
                <div class="w-full flex flex-col items-center justify-center py-12" style="min-height: 400px;">
                    <span class="material-icons text-red-500 mb-4" style="font-size: 48px;">error_outline</span>
                    <p class="text-red-400 text-sm">分析失败</p>
                    <p class="text-zinc-500 text-xs mt-2">${message || '请稍后重试'}</p>
                    ${retryButton}
                </div>
            `;
        }
    }
    
    function renderAnalysisCard(data) {
        currentAnalysisData = data;
        const card = document.querySelector('[id*="analysis-content"]');
        if (!card) return;
        
        const d = data.dashboard;
        
        const signalColors = {
            '🟡持有观望': { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
            '🟢买入信号': { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400' },
            '🔴卖出信号': { bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400' },
        };
        const signalStyle = signalColors[d.core_conclusion.signal_type] || signalColors['🟡持有观望'];
        
        const biasStatusColors = { '危险': 'text-red-400', '警戒': 'text-amber-400', '正常': 'text-emerald-400' };
        const biasColor = biasStatusColors[d.data_perspective.price_position.bias_status] || 'text-zinc-400';
        
        const chipColors = { '健康': 'text-emerald-400', '警惕': 'text-amber-400', '风险': 'text-red-400' };
        const chipColor = chipColors[d.data_perspective.chip_structure.chip_health] || 'text-zinc-400';
        
        const priceDiff = d.data_perspective.price_position.current_price - d.data_perspective.price_position.ma5;
        const diffColor = priceDiff > 0 ? 'text-emerald-400' : 'text-red-400';
        const diffSign = priceDiff > 0 ? '+' : '';
        
        const riskAlerts = d.intelligence.risk_alerts.map(r => `• ${r.replace('风险点', '')}`).join('');
        const positiveCatalysts = d.intelligence.positive_catalysts.map(c => `• ${c.replace('利好', '')}`).join('');
        const actionChecklist = d.battle_plan.action_checklist.map(check => `<div class="text-xs text-zinc-400 mt-0.5">${check}</div>`).join('');
        
        const checklistHtml = d.battle_plan.action_checklist.map(check => 
            `<div class="text-xs text-zinc-400 mt-0.5">${check}</div>`
        ).join('');
        
        card.innerHTML = `
            <div class="w-full flex items-center justify-between p-4 bg-[#18181B] rounded-xl border border-[#27272A]">
                <div class="flex items-center gap-4">
                    <div class="flex flex-col gap-0">
                        <span class="text-xl font-bold text-white">${data.code}</span>
                        <span class="text-sm text-zinc-400">${data.name}</span>
                    </div>
                    <div class="relative w-16 h-16 flex items-center justify-center">
                        <div class="absolute inset-0 rounded-full bg-gradient-to-br from-amber-500/20 to-blue-500/20 border border-amber-500/30"></div>
                        <span class="text-2xl font-bold text-amber-400">${data.sentiment_score}</span>
                    </div>
                    <div class="flex gap-2">
                        <span class="px-3 py-1 rounded-full ${signalStyle.bg} ${signalStyle.text} text-sm border ${signalStyle.border}">${d.core_conclusion.signal_type}</span>
                        <span class="px-3 py-1 rounded-full bg-blue-500/10 text-blue-400 text-sm border border-blue-500/20">信心:${data.confidence_level}</span>
                    </div>
                </div>
                <div class="flex flex-col items-end gap-1">
                    <span class="text-2xl font-bold text-white">¥${d.data_perspective.price_position.current_price.toLocaleString()}</span>
                    <span class="text-sm ${diffColor}">${diffSign}${priceDiff.toFixed(1)}元(MA5)${diffSign}${d.data_perspective.price_position.bias_ma5.toFixed(1)}%</span>
                </div>
            </div>
            
            <div class="w-full p-4 bg-[#27272A]/50 rounded-xl mt-2">
                <div class="flex items-start">
                    <span class="material-icons mr-2 shrink-0 text-amber-400" style="font-size: 20px;">tips_and_updates</span>
                    <div class="flex flex-col gap-1">
                        <span class="text-xs text-zinc-400 uppercase tracking-wider">核心结论</span>
                        <span class="text-white font-medium">${d.core_conclusion.one_sentence}</span>
                        <div class="flex gap-4 mt-2">
                            <div class="flex flex-col gap-0">
                                <span class="text-xs text-zinc-500">空仓建议</span>
                                <span class="text-sm text-zinc-300">${d.core_conclusion.position_advice.no_position}</span>
                            </div>
                            <div class="flex flex-col gap-0">
                                <span class="text-xs text-zinc-500">持仓建议</span>
                                <span class="text-sm text-zinc-300">${d.core_conclusion.position_advice.has_position}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="grid grid-cols-4 gap-3 w-full mt-2">
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">理想买入</span>
                    <div class="text-lg font-bold text-emerald-400">¥${d.data_perspective.price_position.support_level.toFixed(0)}</div>
                    <span class="text-xs text-zinc-600">MA5支撑</span>
                </div>
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">止损位</span>
                    <div class="text-lg font-bold text-red-400">¥${(d.data_perspective.price_position.ma20 * 0.97).toFixed(0)}</div>
                    <span class="text-xs text-zinc-600">跌破MA20+3%</span>
                </div>
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">目标位</span>
                    <div class="text-lg font-bold text-blue-400">¥${parseInt(d.data_perspective.price_position.resistance_level).toLocaleString()}</div>
                    <span class="text-xs text-zinc-600">整数关口</span>
                </div>
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">趋势判断</span>
                    <div class="text-lg font-bold text-white">${data.trend_prediction}</div>
                    <span class="text-xs text-zinc-600">${d.core_conclusion.time_sensitivity}</span>
                </div>
            </div>
            
            <div class="flex gap-3 w-full mt-2">
                <div class="flex-1 flex flex-col gap-2">
                    <span class="text-sm font-bold text-white">数据透视</span>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium text-white">📈 趋势状态</span>
                            <span class="text-xs text-zinc-500">评分:${d.data_perspective.trend_status.trend_score}</span>
                        </div>
                        <span class="text-xs text-zinc-400">${d.data_perspective.trend_status.ma_alignment}</span>
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium text-white">💰 价位分析</span>
                            <span class="text-xs ${biasColor}">乖离:${d.data_perspective.price_position.bias_ma5.toFixed(1)}%</span>
                        </div>
                        <div class="grid grid-cols-2 gap-2">
                            <span class="text-xs text-zinc-500">MA5:${d.data_perspective.price_position.ma5.toFixed(1)}</span>
                            <span class="text-xs text-zinc-500">MA10:${d.data_perspective.price_position.ma10.toFixed(1)}</span>
                            <span class="text-xs text-zinc-500">MA20:${d.data_perspective.price_position.ma20.toFixed(1)}</span>
                            <span class="text-xs text-zinc-500">支撑:${d.data_perspective.price_position.support_level.toFixed(0)}</span>
                        </div>
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium text-white">📊 量能分析</span>
                            <span class="text-xs text-zinc-500">${d.data_perspective.volume_analysis.volume_status}</span>
                        </div>
                        <span class="text-xs text-zinc-400">${d.data_perspective.volume_analysis.volume_meaning}</span>
                        <span class="text-xs text-zinc-500 mt-1">量比:${d.data_perspective.volume_analysis.volume_ratio.toFixed(2)} | 换手率:${d.data_perspective.volume_analysis.turnover_rate.toFixed(2)}%</span>
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-sm font-medium text-white">🎯 筹码结构</span>
                            <span class="text-xs ${chipColor}">${d.data_perspective.chip_structure.chip_health}</span>
                        </div>
                        <span class="text-xs text-zinc-500">获利盘:${d.data_perspective.chip_structure.profit_ratio.toFixed(0)}% | 集中度:${d.data_perspective.chip_structure.concentration.toFixed(1)}</span>
                        <span class="text-xs text-zinc-500">平均成本:¥${d.data_perspective.chip_structure.avg_cost.toFixed(1)}</span>
                    </div>
                </div>
                
                <div class="flex-1 flex flex-col gap-2">
                    <span class="text-sm font-bold text-white">情报分析</span>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <span class="text-xs font-medium text-white mb-1">📰 最新消息</span>
                        <span class="text-xs text-zinc-400 block mt-1">${d.intelligence.latest_news}</span>
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <span class="text-xs font-medium text-red-400 mb-1">⚠️ 风险提示</span>
                        ${d.intelligence.risk_alerts.map(r => `<span class="text-xs text-zinc-400 block">• ${r.replace('风险点', '')}</span>`).join('')}
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <span class="text-xs font-medium text-emerald-400 mb-1">💡 利好因素</span>
                        ${d.intelligence.positive_catalysts.map(c => `<span class="text-xs text-zinc-400 block">• ${c.replace('利好', '')}</span>`).join('')}
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <span class="text-xs font-medium text-white mb-1">🎯 战斗计划</span>
                        <span class="text-xs text-amber-400 block">${d.battle_plan.position_strategy.suggested_position}</span>
                        <span class="text-xs text-zinc-400 block mt-1">${d.battle_plan.position_strategy.entry_plan}</span>
                        <span class="text-xs text-zinc-400 block mt-1">${d.battle_plan.position_strategy.risk_control}</span>
                    </div>
                    
                    <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                        <span class="text-xs font-medium text-white mb-1">✅ 操作检查项</span>
                        ${checklistHtml}
                    </div>
                </div>
            </div>
            
            <div class="w-full p-3 bg-amber-500/5 rounded-lg border border-amber-500/10 mt-2">
                <div class="flex items-start">
                    <span class="material-icons mr-2 shrink-0 self-start mt-0.5 text-amber-400" style="font-size: 18px;">summarize</span>
                    <div class="flex flex-col gap-1">
                        <span class="text-xs text-amber-400 uppercase tracking-wider">分析摘要</span>
                        <span class="text-xs text-zinc-300">${data.analysis_summary}</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    let retryCode = null;
    
    async function submitStockAnalysis(code, reportType) {
        if (!validateStockCode(code)) {
            return;
        }
        
        if (isAnalyzing) {
            ui.notify('分析进行中，请稍候...', {type: 'info', position: 'top'});
            return;
        }
        
        try {
            code = code.trim();
            currentStockCode = code;
            retryCode = code;
            
            setAnalyzingState(true);
            showLoadingState('正在连接AI分析服务...');
            
            const reportTypeMap = {'精简报告': 'simple', '完整报告': 'full'};
            const apiReportType = reportTypeMap[reportType] || 'simple';
            
            const response = await fetch('/api/analyze?code=' + encodeURIComponent(code) + '&report_type=' + encodeURIComponent(apiReportType));
            const data = await response.json();
            
            if (data.success && data.result) {
                showAnalysisResult();
                renderAnalysisCard(data.result);
                window.dispatchEvent(new Event('historyUpdated'));
                ui.notify('✅ 分析完成！', {type: 'positive', position: 'top-right'});
            } else {
                showErrorState(data.error || '分析失败，请检查股票代码是否正确', code);
                ui.notify('❌ ' + (data.error || '分析失败'), {type: 'negative', position: 'top-right'});
            }
        } catch (error) {
            console.error('分析请求失败:', error);
            showErrorState('网络请求失败: ' + error.message, retryCode);
            ui.notify('❌ 请求失败: ' + error.message, {type: 'negative', position: 'top-right'});
        } finally {
            setAnalyzingState(false);
        }
    }
    
    function retryAnalysis(code) {
        if (code) {
            const input = document.querySelector('input[placeholder*="输入代码"]');
            if (input) {
                input.value = code;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            submitStockAnalysis(code || retryCode, 'simple');
        }
    }
    
    function quickAnalyze(code) {
        const input = document.querySelector('input[placeholder*="输入代码"]');
        if (input) {
            input.value = code;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        submitStockAnalysis(code, 'simple');
    }
    
    </script>
    ''')

    # Header
    with ui.header().classes('bg-transparent border-b border-[#27272A] py-2 px-4 backdrop-blur-md sticky top-0 z-50'):
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('show_chart', size='24px', color=Colors.PRIMARY)
                ui.label('股票每日分析').classes('text-lg font-bold tracking-tight')
            
            with ui.row().classes('items-center gap-4'):
                ui.button(icon='notifications', on_click=lambda: ui.notify('暂无新通知')).props('flat round color=grey')
                ui.avatar(icon='person', color=Colors.SURFACE_HOVER).classes('cursor-pointer')
    
    # Left Drawer
    with ui.left_drawer().props('show-if-above bordered width=256 break-point=0').classes('bg-[#09090B] border-r border-[#27272A] p-4'):
        nav_items = [
            ('dashboard', '仪表盘', '/'),
            ('star', '自选股选股', '/watchlist'),
            ('analytics', '深度分析', '/'),
            ('settings', '系统设置', '/settings_v2'),
            ('folder', '研报中心', '/'),
        ]
        
        with ui.column().classes('gap-2 w-full'):
            for icon, label, route in nav_items:
                is_active = label == '仪表盘'
                bg_class = f'bg-[{Colors.SURFACE}]' if is_active else 'hover:bg-zinc-900'
                text_class = f'text-[{Colors.PRIMARY}]' if is_active else f'text-[{Colors.TEXT_MUTED}]'
                
                with ui.row().classes(f'w-full items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors {bg_class}').on('click', lambda r=route: ui.navigate.to(r)):
                    ui.icon(icon).classes(text_class)
                    ui.label(label).classes(f'text-sm font-medium {text_class}')
    
    # Main Content
    with ui.column().classes('w-full h-[calc(100vh-60px)] px-4 pb-4 pt-2.5 gap-2 overflow-auto'):
        # 1. Stock Analysis Input Section
        with ui.row().classes('w-full items-center gap-4 mb-0 shrink-0 bg-[#18181B] p-4 rounded-xl border border-[#27272A]'):
            with ui.column().classes('gap-0.5'):
                ui.label('个股分析').classes('text-lg font-bold text-white')
                ui.label('深度AI研报生成').classes('text-zinc-500 text-xs')
            
            with ui.row().classes('flex-grow items-center gap-3 ml-4'):
                code_input = ui.input(placeholder='输入代码 (如: 600519)').classes('flex-grow').props('outlined dense dark color=blue-6').style('background-color: transparent;')
                code_input.on('keydown.enter', lambda: ui.run_javascript(f'submitStockAnalysis("{code_input.value}", "{report_type_select.value}")'))
                
                report_type_select = ui.select(['精简报告', '完整报告'], value='精简报告').classes('w-32').props('outlined dense dark color=blue-6')
                ui.button('开始分析', icon='auto_awesome').classes('bg-blue-600 hover:bg-blue-700 text-white px-6 rounded-md shadow-sm transition-colors').on_click(
                    lambda: ui.run_javascript(f'submitStockAnalysis("{code_input.value}", "{report_type_select.value}")')
                )
        
        # 2. Analysis Result Modal (Popup)
        # Use a fixed overlay that covers the screen
        with ui.element('div').props('id=analysis-overlay').classes(
            'fixed inset-0 z-[9999] hidden items-center justify-center bg-black/80 backdrop-blur-sm modal-fade-in'
        ).style('display: none;') as analysis_overlay:
            # Click outside to close (optional, but good UX)
            # We can't easily do click-outside in pure NiceGUI without JS for the parent vs child separation, 
            # so we'll rely on the close button or careful JS connection if needed.
            # For now, we utilize the structure.

            # Modal Window
            with ui.column().classes(
                'modal-window w-full max-w-5xl max-h-[90vh] bg-[#09090B] border border-[#27272A] rounded-2xl shadow-2xl overflow-hidden relative'
            ):
                # Modal Header
                with ui.row().classes('w-full items-center justify-between px-6 py-4 border-b border-[#27272A] bg-[#18181B] shrink-0'):
                    with ui.row().classes('items-center gap-2'):
                        ui.icon('analytics', color=Colors.PRIMARY)
                        ui.label('深度分析报告').classes('text-lg font-bold text-white')
                    
                    with ui.row().classes('gap-2'):
                        ui.button('重新分析', icon='refresh').props('flat dense').classes('text-zinc-400 hover:text-blue-400').on_click(
                            lambda: ui.run_javascript('retryAnalysis(currentStockCode)')
                        )
                        ui.button(icon='close').props('flat round dense').classes('text-zinc-400 hover:text-white hover:bg-zinc-800').on_click(
                            lambda: ui.run_javascript('hideAnalysisResult()')
                        )

                # Modal Content (Scrollable)
                with ui.column().classes('w-full p-6 overflow-y-auto custom-scrollbar').props('id=analysis-content'):
                    # Content will be injected by JavaScript
                    pass
        
        # 3. Recent Analysis List with Pagination
        ui.label('近期分析记录').classes(Styles.H2 + ' text-lg mb-1 shrink-0')
        
        from src.storage import get_db
        total_records = get_db().get_analysis_history_count()
        
        table_container = ui.element('div').classes('w-full flex-1 overflow-hidden border border-[#27272A] rounded-xl bg-[#18181B] shadow-sm')
        table_content = ui.element('div').classes('h-full overflow-auto')
        
        with table_container:
            with table_content:
                with ui.element('table').classes('w-full text-left text-sm border-collapse'):
                    with ui.element('thead').classes('bg-[#27272A] text-xs uppercase text-zinc-500 sticky top-0 z-10 font-medium tracking-wider'):
                        with ui.element('tr'):
                            with ui.element('th').classes('px-4 py-3 font-semibold'):
                                ui.label('代码')
                            with ui.element('th').classes('px-4 py-3 font-semibold'):
                                ui.label('名称')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-right'):
                                ui.label('现价')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-right'):
                                ui.label('理想买入')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-right'):
                                ui.label('止损位')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-center'):
                                ui.label('信号')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-center'):
                                ui.label('查询时间')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-center'):
                                ui.label('操作')
                    
                    tbody = ui.element('tbody').classes('divide-y divide-[#27272A] text-zinc-300')
        
        def update_table(page_num):

            from src.storage import get_db
            
            # 定义查看历史记录的处理函数
            def show_history_record(record):
                if not record.get('result_json'):
                    ui.notify('该历史记录不包含详细数据，正在重新分析...', type='warning', position='top')
                    ui.run_javascript(f'quickAnalyze("{record["code"]}")')
                    return
                
                try:
                    data = record['result_json']
                    # 确保是字典
                    if isinstance(data, str):
                        data = json.loads(data)
                        
                    json_str = json.dumps(data, ensure_ascii=False)
                    
                    # 更新当前代码并显示弹窗
                    ui.run_javascript(f'''
                        currentStockCode = "{record['code']}";
                        showAnalysisResult();
                        renderAnalysisCard({json_str});
                    ''')
                except Exception as e:
                    logger.error(f"加载历史记录失败: {e}")
                    ui.notify('加载历史记录详情失败', type='negative')

            page_stocks, new_total = load_history_page(page_num, page_size=10)
            tbody.clear()
            
            if not page_stocks:
                with tbody:
                    with ui.element('tr'):
                        with ui.element('td').props('colspan=8').classes('px-4 py-12 text-center text-zinc-500'):
                            ui.label('暂无分析记录，试试分析一只股票吧！').classes('text-sm')
                return
            
            with tbody:
                for stock in page_stocks:
                    with ui.element('tr').classes('hover:bg-[#27272A]/50 transition-colors cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                        with ui.element('td').classes('px-4 py-3 font-mono font-medium text-white'):
                            ui.label(stock['code'])
                        with ui.element('td').classes('px-4 py-3'):
                            ui.label(stock['name']).classes('font-medium text-white')
                            if stock['code'].isdigit():
                                ui.label('A股').classes('text-xs text-zinc-500')
                            elif stock['code'].startswith('0'):
                                ui.label('港股').classes('text-xs text-zinc-500')
                            else:
                                ui.label('美股').classes('text-xs text-zinc-500')
                        with ui.element('td').classes('px-4 py-3 text-right'):
                            ui.label(stock['price']).classes('font-mono text-white')
                        with ui.element('td').classes('px-4 py-3 text-right'):
                            ui.label(stock['buy_point']).classes('font-mono text-emerald-400')
                        with ui.element('td').classes('px-4 py-3 text-right'):
                            ui.label(stock['stop_loss']).classes('font-mono text-red-400')
                        with ui.element('td').classes('px-4 py-3 text-center'):
                            if stock['signal'] == 'buy':
                                ui.label('强力买入').classes(Styles.BADGE_SUCCESS)
                            elif stock['signal'] == 'sell':
                                ui.label('卖出').classes(Styles.BADGE_ERROR)
                            else:
                                ui.label('持有').classes(Styles.BADGE_WARNING)
                        with ui.element('td').classes('px-4 py-3 text-center text-zinc-400'):
                            ui.label(stock['query_time'])
                        with ui.element('td').classes('px-4 py-3 text-center'):
                            ui.button(icon='arrow_forward', color='grey-8').props('flat round size=sm').classes('hover:text-blue-500')
        
        pagination = create_pagination(
            total=total_records,
            page_size=10,
            current_page=1,
            on_page_change=update_table,
            page_count=7
        )
        
        update_table(1)
        







if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='股票每日分析', dark=True, port=8080)
