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
    <script src="/web/static/progress.js"></script>
    <script>
    let analysisPolling = null;
    let currentAnalysisData = null;
    let isAnalyzing = false;
    let currentStockCode = null;
    
    function validateStockCode(code) {
        if (!code || code.trim() === '') {
            Quasar.Notify.create({ message: '请输入股票代码', type: 'warning', position: 'top' });
            return false;
        }
        
        code = code.trim().toUpperCase();
        
        const aSharePattern = /^\d{6}$/;
        const hkSharePattern = /^(HK)?\d{5}$/;
        const usSharePattern = /^[A-Z]{1,5}$/;
        
        if (!aSharePattern.test(code) && !hkSharePattern.test(code) && !usSharePattern.test(code)) {
            Quasar.Notify.create({ message: '股票代码格式不正确 (A股6位数字/港股5位/美股字母)', type: 'warning', position: 'top' });
            return false;
        }
        
        return true;
    }
    
    function setAnalyzingState(analyzing) {
        isAnalyzing = analyzing;
        const button = document.querySelector('.analyze-btn');
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
            overlay.classList.remove('hidden'); // Remove Tailwind hidden class
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
            overlay.classList.add('hidden'); // Add Tailwind hidden class
            overlay.style.display = 'none';
            document.body.style.overflow = '';
        }
    }
    
    function showLoadingState(step = 'AI正在分析中...') {
        // 先显示模态框
        const overlay = document.getElementById('analysis-overlay');
        if (overlay) {
            overlay.classList.remove('hidden'); // Remove Tailwind hidden class
            overlay.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
        
        const loadingHtml = `
            <div class="w-full flex flex-col items-center justify-center py-20 h-full">
                <div class="animate-spin rounded-full h-10 w-10 border-b-2 border-[#1890ff] mb-6"></div>
                <p class="text-[#ffffffd9] text-[16px] font-medium">${step}</p>
                <p class="text-[#ffffff73] text-[14px] mt-2">正在获取行情数据、计算技术指标、搜索舆情资讯</p>
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
                    class="mt-6 px-4 py-1.5 bg-[#177ddc] hover:bg-[#1890ff] text-white rounded-[4px] text-sm transition-colors shadow-sm">
                重试分析
            </button>
        ` : '';
        
        const card = document.querySelector('[id*="analysis-content"]');
        if (card) {
            card.innerHTML = `
                <div class="w-full flex flex-col items-center justify-center py-20 h-full">
                    <span class="material-icons text-[#ff4d4f] mb-4" style="font-size: 48px;">error_outline</span>
                    <p class="text-[#ff4d4f] text-[16px] font-medium">分析失败</p>
                    <p class="text-[#ffffff73] text-[14px] mt-2 max-w-md text-center">${message || '请稍后重试'}</p>
                    ${retryButton}
                </div>
            `;
        }
    }
    
    function renderAnalysisCard(data) {
        console.log('Rendering Analysis Card', data);
        const safe = (text) => {
            if (text === null || text === undefined) return '';
            return String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        };
        
        const formatAmount = (val) => {
            if (val === undefined || val === null) return '0';
            const num = parseFloat(val);
            if (isNaN(num)) return '0';
            const absVal = Math.abs(num);
            if (absVal >= 100000000) return (num / 100000000).toFixed(2) + '亿';
            if (absVal >= 10000) return (num / 10000).toFixed(2) + '万';
            return num.toFixed(0);
        };

        try {
            currentAnalysisData = data;
            const card = document.querySelector('[id*="analysis-content"]');
            if (!card) {
                console.error('Card element [id*=analysis-content] not found');
                return;
            }
        
        const d = data.dashboard;
        
        const signalColors = {
            '🟡持有观望': { bg: 'bg-[#faad14]/10', border: 'border-[#faad14]/20', text: 'text-[#faad14]' },
            '🟢买入信号': { bg: 'bg-[#52c41a]/10', border: 'border-[#52c41a]/20', text: 'text-[#52c41a]' },
            '🔴卖出信号': { bg: 'bg-[#ff4d4f]/10', border: 'border-[#ff4d4f]/20', text: 'text-[#ff4d4f]' },
        };
        const signalStyle = signalColors[d.core_conclusion.signal_type] || signalColors['🟡持有观望'];
        
        const biasStatusColors = { '危险': 'text-[#ff4d4f]', '警戒': 'text-[#faad14]', '正常': 'text-[#52c41a]' };
        const biasColor = biasStatusColors[d.data_perspective.price_position.bias_status] || 'text-[#ffffff73]';
        
        const chipColors = { '健康': 'text-[#52c41a]', '警惕': 'text-[#faad14]', '风险': 'text-[#ff4d4f]' };
        const chipColor = chipColors[d.data_perspective.chip_structure.chip_health] || 'text-[#ffffff73]';

        const cap = data.capital_flow || {};
        const capStatus = cap.capital_status || '未知';
        const capColors = { '主力大幅流入': 'text-[#ff4d4f]', '主力小幅流入': 'text-[#ff4d4f]', '主力小幅流出': 'text-[#52c41a]', '主力大幅流出': 'text-[#52c41a]', '中性': 'text-[#ffffff73]' };
        const capColor = capColors[capStatus] || 'text-[#ffffff73]';
        
        const priceDiff = d.data_perspective.price_position.current_price - d.data_perspective.price_position.ma5;
        const diffColor = priceDiff > 0 ? 'text-[#ff4d4f]' : 'text-[#52c41a]';
        const diffSign = priceDiff > 0 ? '+' : '';
        
        const checklistHtml = d.battle_plan.action_checklist.map(check => 
            `<div class="text-[12px] text-[#ffffff73] mt-1">${safe(check)}</div>`
        ).join('');
        
        // 提取次优买入价格
        const secondaryBuyPrice = (() => {
            const sniper = d.battle_plan?.sniper_points?.secondary_buy || '';
            const match = sniper.match(/(\d+\.?\d*)/);
            return match ? parseFloat(match[1]).toFixed(2) : '-';
        })();
        
        card.innerHTML = `
            <div class="w-full flex items-center justify-between p-4 bg-[#262626] rounded-lg border border-[#303030]">
                <div class="flex items-center gap-4">
                    <div class="flex flex-col gap-0.5">
                        <span class="text-[20px] font-bold text-[#ffffffd9]">${safe(data.code)}</span>
                        <span class="text-[14px] text-[#ffffff73]">${safe(data.name)}</span>
                    </div>
                    <div class="relative w-16 h-16 flex items-center justify-center">
                        <div class="absolute inset-0 rounded-full bg-gradient-to-br from-[#faad14]/20 to-[#1890ff]/20 border border-[#faad14]/30"></div>
                        <span class="text-2xl font-bold text-[#faad14]">${data.sentiment_score || 0}</span>
                    </div>
                    <div class="flex gap-2">
                        <span class="px-3 py-1 rounded-[4px] ${signalStyle.bg} ${signalStyle.text} text-sm border ${signalStyle.border}">${safe(d.core_conclusion.signal_type)}</span>
                        <span class="px-3 py-1 rounded-[4px] bg-[#1890ff]/10 text-[#1890ff] text-sm border border-[#1890ff]/20">信心:${safe(data.confidence_level)}</span>
                    </div>
                </div>
                <div class="flex flex-col items-end gap-1">
                    <span class="text-[24px] font-bold text-[#ffffffd9] font-mono">¥${d.data_perspective.price_position.current_price.toLocaleString()}</span>
                    <span class="text-xs ${diffColor} font-mono">${diffSign}${priceDiff.toFixed(1)}元(MA5)${diffSign}${d.data_perspective.price_position.bias_ma5.toFixed(1)}%</span>
                </div>
            </div>
            
            <div class="w-full p-4 bg-[#262626] rounded-lg border border-[#303030] mt-3">
                <div class="flex items-start">
                    <span class="material-icons mr-2 shrink-0 text-[#faad14] mt-0.5" style="font-size: 20px;">tips_and_updates</span>
                    <div class="flex flex-col gap-1">
                        <span class="text-[12px] text-[#ffffff73] uppercase tracking-wider">核心结论</span>
                        <span class="text-[#ffffffd9] font-medium text-[15px]">${safe(d.core_conclusion.one_sentence)}</span>
                        <div class="flex gap-8 mt-3">
                            <div class="flex flex-col gap-0.5">
                                <span class="text-[12px] text-[#ffffff73]">空仓建议</span>
                                <span class="text-[14px] text-[#ffffffd9]">${safe(d.core_conclusion.position_advice.no_position)}</span>
                            </div>
                            <div class="flex flex-col gap-0.5">
                                <span class="text-[12px] text-[#ffffff73]">持仓建议</span>
                                <span class="text-[14px] text-[#ffffffd9]">${safe(d.core_conclusion.position_advice.has_position)}</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="grid grid-cols-5 gap-3 w-full mt-3">
                <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                    <span class="text-[12px] text-[#ffffff73]">理想买入</span>
                    <div class="text-[18px] font-bold text-[#52c41a] font-mono mt-1">¥${d.data_perspective.price_position.support_level.toFixed(2)}</div>
                    <span class="text-[12px] text-[#ffffff73]">MA5支撑</span>
                </div>
                <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                    <span class="text-[12px] text-[#ffffff73]">次优买入</span>
                    <div class="text-[18px] font-bold text-[#faad14] font-mono mt-1">¥${secondaryBuyPrice}</div>
                    <span class="text-[12px] text-[#ffffff73]">回调支撑</span>
                </div>
                <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                    <span class="text-[12px] text-[#ffffff73]">止损位</span>
                    <div class="text-[18px] font-bold text-[#ff4d4f] font-mono mt-1">¥${(d.data_perspective.price_position.ma20 * 0.97).toFixed(2)}</div>
                    <span class="text-[12px] text-[#ffffff73]">跌破MA20+3%</span>
                </div>
                <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                    <span class="text-[12px] text-[#ffffff73]">目标位</span>
                    <div class="text-[18px] font-bold text-[#1890ff] font-mono mt-1">¥${d.data_perspective.price_position.resistance_level.toFixed(2)}</div>
                    <span class="text-[12px] text-[#ffffff73]">整数关口</span>
                </div>
                <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                    <span class="text-[12px] text-[#ffffff73]">趋势判断</span>
                    <div class="text-[18px] font-bold text-[#ffffffd9] mt-1">${safe(data.trend_prediction)}</div>
                    <span class="text-[12px] text-[#ffffff73]">${safe(d.core_conclusion.time_sensitivity)}</span>
                </div>
            </div>
            
            <div class="flex flex-col gap-4 w-full mt-3">
                <div class="flex flex-col gap-2">
                    <span class="text-[14px] font-bold text-[#ffffffd9]">数据透视</span>
                    <div class="grid grid-cols-2 gap-3">
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[14px] font-medium text-[#ffffffd9]">📈 趋势状态</span>
                                <span class="text-[12px] text-[#ffffff73]">评分:${d.data_perspective.trend_status.trend_score}</span>
                            </div>
                            <span class="text-[12px] text-[#ffffff73]">${safe(d.data_perspective.trend_status.ma_alignment)}</span>
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[14px] font-medium text-[#ffffffd9]">💰 价位分析</span>
                                <span class="text-[12px] ${biasColor}">乖离:${d.data_perspective.price_position.bias_ma5.toFixed(1)}%</span>
                            </div>
                            <div class="grid grid-cols-2 gap-2">
                                <span class="text-[12px] text-[#ffffff73] font-mono">MA5:${d.data_perspective.price_position.ma5.toFixed(1)}</span>
                                <span class="text-[12px] text-[#ffffff73] font-mono">MA10:${d.data_perspective.price_position.ma10.toFixed(1)}</span>
                                <span class="text-[12px] text-[#ffffff73] font-mono">MA20:${d.data_perspective.price_position.ma20.toFixed(1)}</span>
                                <span class="text-[12px] text-[#ffffff73] font-mono">支撑:${d.data_perspective.price_position.support_level.toFixed(0)}</span>
                            </div>
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[14px] font-medium text-[#ffffffd9]">📊 量能分析</span>
                                <span class="text-[12px] text-[#ffffff73]">${safe(d.data_perspective.volume_analysis.volume_status)}</span>
                            </div>
                            <span class="text-[12px] text-[#ffffff73] leading-relaxed block">${safe(d.data_perspective.volume_analysis.volume_meaning)}</span>
                            <div class="mt-2 pt-2 border-t border-[#303030] flex justify-between">
                                <span class="text-[12px] text-[#ffffff73]">量比: <span class="text-[#ffffffd9]">${d.data_perspective.volume_analysis.volume_ratio.toFixed(2)}</span></span>
                                <span class="text-[12px] text-[#ffffff73]">换手率: <span class="text-[#ffffffd9]">${d.data_perspective.volume_analysis.turnover_rate.toFixed(2)}%</span></span>
                            </div>
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[14px] font-medium text-[#ffffffd9]">🎯 筹码结构</span>
                                <span class="text-[12px] ${chipColor}">${safe(d.data_perspective.chip_structure.chip_health)}</span>
                            </div>
                            <div class="space-y-1">
                                <span class="text-[12px] text-[#ffffff73] block">获利盘: <span class="text-[#ffffffd9]">${d.data_perspective.chip_structure.profit_ratio.toFixed(0)}%</span> | 集中度: <span class="text-[#ffffffd9]">${d.data_perspective.chip_structure.concentration.toFixed(1)}</span></span>
                                <span class="text-[12px] text-[#ffffff73] block">平均成本: <span class="text-[#ffffffd9] font-mono">¥${d.data_perspective.chip_structure.avg_cost.toFixed(1)}</span></span>
                            </div>
                        </div>

                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030] col-span-2 sm:col-span-1">
                            <div class="flex items-center justify-between mb-2">
                                <span class="text-[14px] font-medium text-[#ffffffd9]">💸 资金流向</span>
                                <span class="text-[12px] ${capColor}">${safe(capStatus)}</span>
                            </div>
                            <div class="space-y-1">
                                <span class="text-[12px] text-[#ffffff73] block">今日主力: <span class="text-[#ffffffd9] font-mono">${formatAmount(cap.main_net_inflow_today)}</span></span>
                                <span class="text-[12px] text-[#ffffff73] block">5日主力: <span class="text-[#ffffffd9] font-mono">${formatAmount(cap.main_net_inflow_5d)}</span> | 连红: <span class="text-[#ffffffd9]">${cap.consecutive_inflow_days || 0}天</span></span>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="flex flex-col gap-2">
                    <span class="text-[14px] font-bold text-[#ffffffd9]">情报分析</span>
                    <div class="grid grid-cols-2 gap-3">
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030] col-span-2">
                            <span class="text-[12px] font-medium text-[#ffffffd9] mb-1 block">📰 最新消息</span>
                            <span class="text-[12px] text-[#ffffff73] block leading-relaxed">${safe(d.intelligence.latest_news)}</span>
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <span class="text-[12px] font-medium text-[#ff4d4f] mb-1 block">⚠️ 风险提示</span>
                            ${d.intelligence.risk_alerts.map(r => `<span class="text-[12px] text-[#ffffffd9] block mt-1">• ${safe(r.replace('风险点', ''))}</span>`).join('')}
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <span class="text-[12px] font-medium text-[#52c41a] mb-1 block">💡 利好因素</span>
                            ${d.intelligence.positive_catalysts.map(c => `<span class="text-[12px] text-[#ffffffd9] block mt-1">• ${safe(c.replace('利好', ''))}</span>`).join('')}
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <span class="text-[12px] font-medium text-[#ffffffd9] mb-1 block">🎯 战斗计划</span>
                            <span class="text-[13px] text-[#faad14] block font-medium">${safe(d.battle_plan.position_strategy.suggested_position)}</span>
                            <span class="text-[12px] text-[#ffffff73] block mt-1 leading-relaxed">${safe(d.battle_plan.position_strategy.entry_plan)}</span>
                            <div class="mt-2 pt-2 border-t border-[#303030]">
                                <span class="text-[12px] text-[#ffffff73] block">${safe(d.battle_plan.position_strategy.risk_control)}</span>
                            </div>
                        </div>
                        
                        <div class="p-3 bg-[#262626] rounded-lg border border-[#303030]">
                            <span class="text-[12px] font-medium text-[#ffffffd9] mb-1 block">✅ 操作检查项</span>
                            ${checklistHtml}
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="w-full p-3 bg-[#faad14]/5 rounded-lg border border-[#faad14]/20 mt-3">
                <div class="flex items-start">
                    <span class="material-icons mr-2 shrink-0 self-start mt-0.5 text-[#faad14]" style="font-size: 18px;">summarize</span>
                    <div class="flex flex-col gap-1">
                        <span class="text-[12px] text-[#faad14] uppercase tracking-wider">分析摘要</span>
                        <span class="text-[13px] text-[#ffffffd9] leading-relaxed">${safe(data.analysis_summary)}</span>
                    </div>
                </div>
            </div>
        `;
        } catch (e) {
            console.error('Error rendering analysis card:', e);
            const card = document.querySelector('[id*="analysis-content"]');
            if (card) {
                card.innerHTML = `<div class="p-4 flex items-center justify-center flex-col text-[#ff4d4f]"><span class="material-icons text-4xl mb-2">error</span><span>渲染界面时发生错误</span><span class="text-xs text-[#ffffff73] mt-1">${e.message}</span></div>`;
            }
        }
    }
    
    let retryCode = null;
    
    async function submitStockAnalysis(code) {
        if (!validateStockCode(code)) {
            return;
        }
        
        if (isAnalyzing) {
            Quasar.Notify.create({ message: '分析进行中，请稍候...', type: 'info', position: 'top' });
            return;
        }
        
        try {
            code = code.trim();
            currentStockCode = code;
            retryCode = code;
            
            setAnalyzingState(true);
            
            // 使用新的进度追踪UI
            if (typeof showLoadingStateWithProgress === 'function') {
                showLoadingStateWithProgress(code);
            } else {
                showLoadingState('正在连接AI分析服务...');
            }
            
            const apiReportType = 'full';
            
            const response = await fetch('/api/analyze?code=' + encodeURIComponent(code) + '&report_type=' + encodeURIComponent(apiReportType));
            const data = await response.json();
            
            console.log('分析响应:', data); // 调试日志
            
            if (data.success && data.result) {
                // 确保模态框显示并渲染结果
                const overlay = document.getElementById('analysis-overlay');
                if (overlay) {
                    overlay.classList.remove('hidden'); // Remove Tailwind hidden class
                    overlay.style.display = 'flex';
                }
                renderAnalysisCard(data.result);
                window.dispatchEvent(new Event('historyUpdated'));
                Quasar.Notify.create({ message: '✅ 分析完成！', type: 'positive', position: 'top-right' });
            } else {
                showErrorState(data.error || '分析失败，请检查股票代码是否正确', code);
                Quasar.Notify.create({ message: '❌ ' + (data.error || '分析失败'), type: 'negative', position: 'top-right' });
            }
        } catch (error) {
            console.error('分析请求失败:', error);
            showErrorState('网络请求失败: ' + error.message, retryCode);
            Quasar.Notify.create({ message: '❌ 请求失败: ' + error.message, type: 'negative', position: 'top-right' });
        } finally {
            setAnalyzingState(false);
            // 停止进度轮询
            if (typeof stopProgressPolling === 'function') {
                stopProgressPolling();
            }
        }
    }
    
    function retryAnalysis(code) {
        if (code) {
            const input = document.querySelector('input[placeholder*="输入代码"]');
            if (input) {
                input.value = code;
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
            submitStockAnalysis(code || retryCode);
        }
    }
    
    function quickAnalyze(code) {
        const input = document.querySelector('input[placeholder*="输入代码"]');
        if (input) {
            input.value = code;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        submitStockAnalysis(code);
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
    with ui.column().classes('w-full h-[calc(100vh-100px)] px-4 pb-4 pt-2.5 gap-2 overflow-auto'):
        # 1. Stock Analysis Input Section
        # 1. Stock Analysis Input Section
        with ui.row().classes('w-full items-center justify-between mb-0 shrink-0 bg-[#18181B] p-4 rounded-xl border border-[#27272A] shadow-sm'):
            # Left: Title Area with Icon
            with ui.row().classes('items-center gap-3'):
                with ui.element('div').classes('flex items-center justify-center w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20'):
                    ui.icon('show_chart', size='20px').classes('text-blue-500')
                with ui.column().classes('gap-0'):
                    ui.label('市场扫描').classes('text-[16px] font-bold text-gray-100 tracking-tight leading-tight')
                    ui.label('AI 深度研报生成').classes('text-zinc-500 text-[12px] leading-tight')
            
            # Right: Input Control Group
            with ui.row().classes('items-center gap-3'):
                # Stock Code Input - Compact & Styled
                code_input = ui.input(placeholder='股票代码 (如 600519)').props(
                    'outlined dense dark color=blue-6 rounded input-class="text-center"'
                ).classes(
                    'w-64 transition-all focus-within:w-72 font-mono tracking-wider bg-transparent'
                )
                
                with code_input.add_slot('prepend'):
                    ui.icon('search', size='xs').classes('text-zinc-500')
                
                async def analyze_stock():
                    code = code_input.value
                    if not code:
                        ui.notify('请输入股票代码', type='warning')
                        return
                    await ui.run_javascript(f'submitStockAnalysis("{code}")')
                
                code_input.on('keydown.enter', analyze_stock)
                
                # Action Button
                ui.button('开始分析', icon='auto_awesome').classes(
                    'bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-5 py-1.5 rounded-lg shadow-sm border border-blue-500/20 transition-all active:scale-95'
                ).on_click(analyze_stock)
        
        # 2. Analysis Result Modal (Popup)
        # Use a fixed overlay that covers the screen
        # 3. Analysis Result Modal (Popup) - Ant Design Style
        # Use a fixed overlay that covers the screen
        with ui.element('div').props('id=analysis-overlay').classes(
            'fixed inset-0 z-[9999] hidden items-center justify-center bg-black/45 modal-fade-in'
        ) as analysis_overlay:
            # Click outside to close implementation could be added here with JS if needed

            # Modal Window
            with ui.element('div').classes(
                'modal-window w-[1000px] max-w-[95vw] max-h-[85vh] bg-[#1f1f1f] rounded-lg shadow-2xl overflow-hidden relative flex flex-col flex-nowrap'
            ):
                # Modal Header
                with ui.row().classes('w-full items-center justify-between px-6 py-4 border-b border-[#303030] bg-[#1f1f1f] shrink-0'):
                    with ui.row().classes('items-center gap-2'):
                        # ui.icon('analytics', color=Colors.PRIMARY).classes('text-[18px]')
                        ui.label('深度分析报告').classes('text-[16px] font-semibold text-[#ffffffd9]')
                    
                    # Close X Button
                    ui.button(icon='close').props('flat round dense size=sm').classes('text-[#ffffff73] hover:text-[#ffffffd9]').on_click(
                        lambda: ui.run_javascript('hideAnalysisResult()')
                    )

                # Modal Content (Scrollable)
                # Using #1f1f1f to match AntD modal body background
                with ui.element('div').classes('w-full p-6 overflow-y-auto custom-scrollbar text-[#ffffffd9] flex-1 flex flex-col flex-nowrap').props('id=analysis-content').style('font-size: 14px; line-height: 1.5715;'):
                    # Content will be injected by JavaScript
                    pass
                
                # Modal Footer
                with ui.row().classes('w-full items-center justify-end px-4 py-3 border-t border-[#303030] bg-[#1f1f1f] shrink-0 gap-2'):
                    ui.button('关闭').props('outline').classes('text-[#ffffffd9] border-[#434343] hover:text-[#40a9ff] hover:border-[#40a9ff] px-4 rounded-[4px]').on_click(
                        lambda: ui.run_javascript('hideAnalysisResult()')
                    )
                    ui.button('重新分析', icon='refresh').classes('bg-[#177ddc] text-white hover:bg-[#1890ff] px-4 rounded-[4px] shadow-none border-none').on_click(
                        lambda: ui.run_javascript('retryAnalysis(currentStockCode)')
                    )
        
        # 3. Recent Analysis List with Pagination
        ui.label('近期分析记录').classes(Styles.H2 + ' text-lg mb-1 shrink-0')
        
        from src.storage import get_db
        total_records = get_db().get_analysis_history_count()
        
        table_container = ui.element('div').classes('w-full flex-1 overflow-hidden border border-[#27272A] rounded-xl bg-[#18181B] shadow-sm')
        table_content = ui.element('div').classes('h-full overflow-auto')
        
        with table_container:
            with table_content:
                with ui.element('table').classes('w-full text-left text-sm border-collapse'):
                    with ui.element('thead').classes('bg-[#27272A] text-sm uppercase text-zinc-500 sticky top-0 z-10 font-medium tracking-wider'):
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
                                ui.label('次优买入')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-right'):
                                ui.label('止损位')
                            with ui.element('th').classes('px-4 py-3 font-semibold text-center'):
                                ui.label('评分')
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
                        with ui.element('td').props('colspan=10').classes('px-4 py-12 text-center text-zinc-500'):
                            ui.label('暂无分析记录，试试分析一只股票吧！').classes('text-sm')
                return
            
            with tbody:
                for stock in page_stocks:
                    with ui.element('tr').classes('hover:bg-[#27272A]/50 transition-colors'):
                        with ui.element('td').classes('px-4 py-3 font-mono font-medium text-white cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['code'])
                        with ui.element('td').classes('px-4 py-3 cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['name']).classes('font-medium text-white')
                            if stock['code'].isdigit():
                                ui.label('A股').classes('text-xs text-zinc-500')
                            elif stock['code'].startswith('0'):
                                ui.label('港股').classes('text-xs text-zinc-500')
                            else:
                                ui.label('美股').classes('text-xs text-zinc-500')
                        with ui.element('td').classes('px-4 py-3 text-right cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['price']).classes('font-mono text-white')
                        with ui.element('td').classes('px-4 py-3 text-right cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['buy_point']).classes('font-mono text-emerald-400')
                        with ui.element('td').classes('px-4 py-3 text-right cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock.get('secondary_buy', '-')).classes('font-mono text-amber-400')
                        with ui.element('td').classes('px-4 py-3 text-right cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['stop_loss']).classes('font-mono text-red-400')
                        with ui.element('td').classes('px-4 py-3 text-center cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            score = stock.get('score', 0)
                            score_color = 'text-emerald-400' if score >= 70 else ('text-amber-400' if score >= 50 else 'text-red-400')
                            ui.label(str(score)).classes(f'font-mono font-bold {score_color}')
                        with ui.element('td').classes('px-4 py-3 text-center cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            if stock['signal'] == 'buy':
                                ui.label('强力买入').classes(Styles.BADGE_SUCCESS)
                            elif stock['signal'] == 'sell':
                                ui.label('卖出').classes(Styles.BADGE_ERROR)
                            else:
                                ui.label('持有').classes(Styles.BADGE_WARNING)
                        with ui.element('td').classes('px-4 py-3 text-center text-zinc-400 cursor-pointer').on('click', lambda _, r=stock: show_history_record(r)):
                            ui.label(stock['query_time'])
                        with ui.element('td').classes('px-4 py-3 text-center'):
                            with ui.row().classes('gap-1 items-center justify-center'):
                                ui.button(icon='visibility', color='grey-8').props('flat round size=sm').classes('hover:text-blue-500').on('click', lambda _, r=stock: show_history_record(r))
                                ui.button(icon='refresh', color='grey-8').props('flat round size=sm').classes('hover:text-green-500').on('click', lambda e, code=stock['code']: (e.stopPropagation(), ui.run_javascript(f'quickAnalyze("{code}")')))
        
        pagination = create_pagination(
            total=total_records,
            page_size=10,
            current_page=1,
            on_page_change=update_table,
            page_count=7
        )
        
        update_table(1)
        
        # 创建一个隐藏的刷新按钮，用于通过JavaScript触发表格刷新
        refresh_trigger = ui.button('', on_click=lambda: update_table(1)).classes('hidden').props('id=refresh-trigger')
        
        # 添加事件监听器，当分析完成后自动刷新表格
        ui.add_head_html('''
        <script>
        window.addEventListener('DOMContentLoaded', function() {
            window.addEventListener('historyUpdated', function() {
                console.log('历史记录已更新，刷新表格...');
                // 等待一下确保数据已保存，然后触发表格刷新
                setTimeout(function() {
                    const refreshBtn = document.getElementById('refresh-trigger');
                    if (refreshBtn) {
                        refreshBtn.click();
                    }
                }, 300);
            });
        });
        </script>
        ''')
        







if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='股票每日分析', dark=True, port=8080)
