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
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from nicegui import ui, app
from web.theme import Colors, Styles, setup_theme
from web.api import register_api
from web.components.pagination import create_pagination
from web.history_loader import load_history_page
import logging

logger = logging.getLogger(__name__)


# 初始化UI应用
setup_theme()

# 注册API端点
register_api()

# 添加自定义CSS
ui.add_css('''
    .q-page-container {
        padding-top: 0px !important;
    }
    .analysis-result-card {
        display: none;
    }
    .analysis-result-card.show {
        display: flex;
    }
''')

# 添加JavaScript辅助函数
ui.add_head_html('''
    <script>
    let analysisPolling = null;
    let currentAnalysisData = null;
    let isAnalyzing = false;  // 分析状态标志
    let currentStockCode = null;  // 当前分析的股票代码
    
    // ============= 输入验证 =============
    function validateStockCode(code) {
        if (!code || code.trim() === '') {
            ui.notify('请输入股票代码', {type: 'warning', position: 'top'});
            return false;
        }
        
        code = code.trim().toUpperCase();
        
        // A股：6位数字
        const aSharePattern = /^\d{6}$/;
        // 港股：5位数字或HK开头
        const hkSharePattern = /^(HK)?\d{5}$/;
        // 美股：1-5个大写字母
        const usSharePattern = /^[A-Z]{1,5}$/;
        
        if (!aSharePattern.test(code) && !hkSharePattern.test(code) && !usSharePattern.test(code)) {
            ui.notify('股票代码格式不正确 (A股6位数字/港股5位/美股字母)', {type: 'warning', position: 'top'});
            return false;
        }
        
        return true;
    }
    
    // ============= UI状态管理 =============
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
        const contentCard = document.querySelector('[id*="analysis-content"]');
        if (contentCard && contentCard.parentElement) {
            contentCard.parentElement.style.display = 'flex';
        }
    }
    
    function hideAnalysisResult() {
        const contentCard = document.querySelector('[id*="analysis-content"]');
        if (contentCard && contentCard.parentElement) {
            contentCard.parentElement.style.display = 'none';
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
        
        // 信号类型颜色
        const signalColors = {
            '🟡持有观望': { bg: 'bg-amber-500/10', border: 'border-amber-500/20', text: 'text-amber-400' },
            '🟢买入信号': { bg: 'bg-emerald-500/10', border: 'border-emerald-500/20', text: 'text-emerald-400' },
            '🔴卖出信号': { bg: 'bg-red-500/10', border: 'border-red-500/20', text: 'text-red-400' },
        };
        const signalStyle = signalColors[d.core_conclusion.signal_type] || signalColors['🟡持有观望'];
        
        // 乖离率状态颜色
        const biasStatusColors = { '危险': 'text-red-400', '警戒': 'text-amber-400', '正常': 'text-emerald-400' };
        const biasColor = biasStatusColors[d.data_perspective.price_position.bias_status] || 'text-zinc-400';
        
        // 筹码健康度颜色
        const chipColors = { '健康': 'text-emerald-400', '警惕': 'text-amber-400', '风险': 'text-red-400' };
        const chipColor = chipColors[d.data_perspective.chip_structure.chip_health] || 'text-zinc-400';
        
        const priceDiff = d.data_perspective.price_position.current_price - d.data_perspective.price_position.ma5;
        const diffColor = priceDiff > 0 ? 'text-emerald-400' : 'text-red-400';
        const diffSign = priceDiff > 0 ? '+' : '';
        
        // 生成风险提示列表
        const riskAlerts = d.intelligence.risk_alerts.map(r => `• ${r.replace('风险点', '')}`).join('');
        const positiveCatalysts = d.intelligence.positive_catalysts.map(c => `• ${c.replace('利好', '')}`).join('');
        const actionChecklist = d.battle_plan.action_checklist.map(check => `<div class="text-xs text-zinc-400 mt-0.5">${check}</div>`).join('');
        
        // 生成检查清单
        const checklistHtml = d.battle_plan.action_checklist.map(check => 
            `<div class="text-xs text-zinc-400 mt-0.5">${check}</div>`
        ).join('');
        
        card.innerHTML = `
            <!-- 顶部股票信息栏 -->
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
            
            <!-- 核心结论 -->
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
            
            <!-- 关键指标网格 -->
            <div class="grid grid-cols-4 gap-3 w-full mt-2">
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">理想买入</span>
                    <div class="text-lg font-bold text-emerald-400">¥${d.data_perspective.price_position.support_level.toFixed(0)}</div>
                    <span class="text-xs text-zinc-600">MA5支撑</span>
                </div>
                <div class="p-3 bg-[#18181B] rounded-lg border border-[#27272A]">
                    <span class="text-xs text-zinc-500">止损位</span>
                    <div class="text-lg font-bold text-red-400">¥1,350</div>
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
            
            <!-- 数据透视与情报分析 -->
            <div class="flex gap-3 w-full mt-2">
                <!-- 左侧：数据透视 -->
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
                
                <!-- 右侧：情报分析与战斗计划 -->
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
            
            <!-- 分析摘要 -->
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
    
    // 同步分析 - 集成验证和状态管理
    async function submitStockAnalysis(code, reportType) {
        // 验证股票代码
        if (!validateStockCode(code)) {
            return;
        }
        
        // 防止重复提交
        if (isAnalyzing) {
            ui.notify('分析进行中，请稍候...', {type: 'info', position: 'top'});
            return;
        }
        
        try {
            code = code.trim();
            currentStockCode = code;
            retryCode = code;
            
            // 设置分析状态
            setAnalyzingState(true);
            showLoadingState('正在连接AI分析服务...');
            
            // 使用同步API - 直接等待结果
            const reportTypeMap = {'精简报告': 'simple', '完整报告': 'full'};
            const apiReportType = reportTypeMap[reportType] || 'simple';
            
            const response = await fetch('/api/analyze?code=' + encodeURIComponent(code) + '&report_type=' + encodeURIComponent(apiReportType));
            const data = await response.json();
            
            if (data.success && data.result) {
                showAnalysisResult();
                renderAnalysisCard(data.result);
                // 不再调用saveAnalysisHistory，后端已自动保存
                // 触发表格更新事件
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
            // 恢复UI状态
            setAnalyzingState(false);
        }
    }
    
    function retryAnalysis(code) {
        if (code) {
            // 填充到输入框
            const input = document.querySelector('input[placeholder*="输入代码"]');
            if (input) {
                input.value = code;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            submitStockAnalysis(code || retryCode, 'simple');
        }
    }
    
    // 快速分析（从表格点击）
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

# --- Header ---
with ui.header().classes('bg-transparent border-b border-[#27272A] py-2 px-4 backdrop-blur-md sticky top-0 z-50'):
    with ui.row().classes('w-full items-center justify-between no-wrap'):
        with ui.row().classes('items-center gap-2'):
            ui.icon('show_chart', size='24px', color=Colors.PRIMARY)
            ui.label('股票每日分析').classes('text-lg font-bold tracking-tight')
        
        with ui.row().classes('items-center gap-4'):
            ui.button(icon='notifications', on_click=lambda: ui.notify('暂无新通知')).props('flat round color=grey')
            ui.avatar(icon='person', color=Colors.SURFACE_HOVER).classes('cursor-pointer')

# --- Left Drawer ---
with ui.left_drawer().props('show-if-above bordered width=256 break-point=0').classes('bg-[#09090B] border-r border-[#27272A] p-4'):
    nav_items = [
        ('dashboard', '仪表盘'),
        ('analytics', '深度分析'),
        ('pie_chart', '投资组合'),
        ('settings', '系统设置'),
        ('folder', '研报中心'),
    ]
    
    with ui.column().classes('gap-2 w-full'):
        for icon, label in nav_items:
            is_active = label == '仪表盘'
            bg_class = f'bg-[{Colors.SURFACE}]' if is_active else 'hover:bg-zinc-900'
            text_class = f'text-[{Colors.PRIMARY}]' if is_active else f'text-[{Colors.TEXT_MUTED}]'
            
            with ui.row().classes(f'w-full items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors {bg_class}'):
                ui.icon(icon).classes(text_class)
                ui.label(label).classes(f'text-sm font-medium {text_class}')

# --- Main Content ---
with ui.column().classes('w-full h-[calc(100vh-60px)] px-4 pb-4 pt-2.5 gap-2 overflow-auto'):
    
    # 1. Stock Analysis Input Section
    with ui.row().classes('w-full items-center gap-4 mb-0 shrink-0 bg-[#18181B] p-4 rounded-xl border border-[#27272A]'):
        with ui.column().classes('gap-0.5'):
            ui.label('个股分析').classes('text-lg font-bold text-white')
            ui.label('深度AI研报生成').classes('text-zinc-500 text-xs')
        
        with ui.row().classes('flex-grow items-center gap-3 ml-4'):
            code_input = ui.input(placeholder='输入代码 (如: 600519)').classes('flex-grow').props('outlined dense dark color=blue-6').style('background-color: transparent;')
            # 添加回车提交
            code_input.on('keydown.enter', lambda: ui.run_javascript(f'submitStockAnalysis("{code_input.value}", "{report_type_select.value}")'))
            
            report_type_select = ui.select(['精简报告', '完整报告'], value='精简报告').classes('w-32').props('outlined dense dark color=blue-6')
            ui.button('开始分析', icon='auto_awesome').classes('bg-blue-600 hover:bg-blue-700 text-white px-6 rounded-md shadow-sm transition-colors').on_click(
                lambda: ui.run_javascript(f'submitStockAnalysis("{code_input.value}", "{report_type_select.value}")')
            )
    
    # 2. Analysis Result Card (Hidden by default - no space when hidden)
    with ui.column().classes('w-full shrink-0').style('display: none;') as analysis_result_container:
        
        # 分析内容容器 - 由JavaScript动态渲染
        analysis_content = ui.column().classes('w-full').props('id=analysis-content')
        
        # 按钮操作区（独立于动态内容）
        with ui.row().classes('w-full justify-end gap-2 mt-2'):
            ui.button('查看详情', icon='visibility').props('flat round dense').classes('text-zinc-400').on_click(
                lambda: ui.notify('📑 完整查看功能即将上线', type='info')
            )
            ui.button('重新分析', icon='refresh').props('flat round dense').classes('text-zinc-400 hover:text-blue-400').on_click(
                lambda: ui.run_javascript('retryAnalysis(currentStockCode)')
            )
            ui.button('×').props('flat round dense').classes('text-zinc-500 hover:text-red-400').on_click(
                lambda: ui.run_javascript('hideAnalysisResult()')
            )
    
    # 3. Recent Analysis List with Pagination
    ui.label('近期分析记录').classes(Styles.H2 + ' text-lg mb-1 shrink-0')
    
    # 从数据库获取初始总记录数
    from src.storage import get_db
    total_records = get_db().get_analysis_history_count()
    
    # 表格容器 - 移除固定高度，改为flex-1自动填充剩余空间
    table_container = ui.element('div').classes('w-full flex-1 overflow-hidden border border-[#27272A] rounded-xl bg-[#18181B] shadow-sm')
    
    # 表格内容容器
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
                
                # 表格体
                tbody = ui.element('tbody').classes('divide-y divide-[#27272A] text-zinc-300')
    
    def update_table(page_num):
        """更新表格内容 - 从数据库加载"""
        # 从数据库获取当前页的数据
        page_stocks, new_total = load_history_page(page_num, page_size=10)
        # Note: 总数变化需要重新创建分页组件（当前简化实现）
        
        # 清空并重新填充表格
        tbody.clear()
        
        if not page_stocks:
            # 空状态提示
            with tbody:
                with ui.element('tr'):
                    with ui.element('td').props('colspan=8').classes('px-4 py-12 text-center text-zinc-500'):
                        ui.label('暂无分析记录，试试分析一只股票吧！').classes('text-sm')
            return
        
        with tbody:
            for stock in page_stocks:
                with ui.element('tr').classes('hover:bg-[#27272A]/50 transition-colors cursor-pointer'):
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
    
    # 创建分页组件
    pagination = create_pagination(
        total=total_records,
        page_size=10,
        current_page=1,
        on_page_change=update_table,
        page_count=7
    )
    
    
    # 初始化第一页数据
    update_table(1)
    
    # 添加表格交互JavaScript
    ui.add_body_html('''
        <script>
        // 为表格行添加点击事件
        function attachRowClickHandlers() {
            const rows = document.querySelectorAll('tbody tr');
            rows.forEach(row => {
                row.style.cursor = 'pointer';
                row.style.transition = 'background-color 0.2s';
                
                row.addEventListener('mouseenter', () => {
                    row.style.backgroundColor = '#27272A';
                });
                row.addEventListener('mouseleave', () => {
                    row.style.backgroundColor = 'transparent';
                });
                row.addEventListener('click', (e) => {
                    // 如果点击的是按钮，不触发行点击
                    if (e.target.closest('button')) return;
                    
                    const codeCell = row.querySelector('td:first-child');
                    if (codeCell) {
                        const code = codeCell.textContent.trim();
                        quickAnalyze(code);
                    }
                });
            });
        }
        
        // 页面加载后立即添加事件监听
        document.addEventListener('DOMContentLoaded', () => {
            attachRowClickHandlers();
            
            // 监听表格更新事件（翻页时）
            const observer = new MutationObserver(() => {
                attachRowClickHandlers();
            });
            
            const tbody = document.querySelector('tbody');
            if (tbody) {
                observer.observe(tbody, { childList: true, subtree: true });
            }
        });
        
        // 等待DOM加载完成后附加事件
        setTimeout(attachRowClickHandlers, 500);
        </script>
    ''')


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='股票每日分析', dark=True, port=8080)
