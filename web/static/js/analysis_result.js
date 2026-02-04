// Analysis Result Card Controller
// 用于控制分析结果卡片的显示和交互

function showAnalysisResult(data) {
    // 显示分析结果卡片
    const card = document.querySelector('[class*="analysis_result_container"]');
    if (card) {
        card.style.display = 'flex';
    }
    
    // 更新股票信息
    updateStockInfo(data);
}

function updateStockInfo(data) {
    // 更新股票代码和名称
    const codeEl = document.querySelector('text-white font-bold');
    if (codeEl && data.code) {
        codeEl.textContent = data.code;
    }
    
    // 更新评分
    const scoreEl = document.querySelector('text-2xl font-bold text-emerald-400');
    if (scoreEl && data.sentiment_score) {
        scoreEl.textContent = data.sentiment_score;
    }
    
    // 更新价格和涨跌幅
    const priceEl = document.querySelector('text-2xl font-bold text-white');
    if (priceEl && data.current_price) {
        priceEl.textContent = '¥' + data.current_price.toFixed(2);
    }
    
    // 更新核心结论
    const conclusionEl = document.querySelector('font-medium text-white');
    if (conclusionEl && data.dashboard?.core_conclusion?.one_sentence) {
        conclusionEl.textContent = data.dashboard.core_conclusion.one_sentence;
    }
}

// 模拟显示分析结果（用于测试）
function simulateShowResult() {
    const mockData = {
        code: '600519',
        name: '贵州茅台',
        sentiment_score: 85,
        current_price: 1850.00,
        change: '+2.5%',
        dashboard: {
            core_conclusion: {
                one_sentence: '股价站稳5日均线，MACD金叉放量，建议在1800-1850区间建仓，止损位1750'
            }
        }
    };
    showAnalysisResult(mockData);
}

// 初始化事件监听
document.addEventListener('DOMContentLoaded', function() {
    // 为分析按钮添加点击事件
    const analyzeBtn = document.querySelector('button');
    if (analyzeBtn && analyzeBtn.textContent.includes('分析')) {
        analyzeBtn.addEventListener('click', function() {
            setTimeout(simulateShowResult, 500);
        });
    }
});
