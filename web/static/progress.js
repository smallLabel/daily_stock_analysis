// 股票分析进度追踪 JavaScript
// 四个分析步骤：数据获取、技术分析、资讯查询、AI分析

function showLoadingStateWithProgress(stockCode) {
    // 先显示模态框
    const overlay = document.getElementById('analysis-overlay');
    if (overlay) {
        overlay.classList.remove('hidden');
        overlay.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }

    const loadingHtml = `
        <div class="w-full flex flex-col items-center justify-center py-12" style="min-height: 500px;">
            <div class="w-full max-w-2xl px-8">
                <div class="text-center mb-8">
                    <div class="animate-spin rounded-full h-16 w-16 border-b-2 border-blue-500 mx-auto mb-4"></div>
                    <h3 class="text-xl font-semibold text-zinc-200 mb-2">AI正在分析中...</h3>
                    <p id="current-step-message" class="text-zinc-400 text-sm">正在初始化分析流程</p>
                </div>
                
                <!-- 进度步骤 -->
                <div class="space-y-4 mt-8">
                    <div class="progress-step" data-step="数据获取">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-3">
                                <div class="step-icon w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                                    <span class="text-zinc-400 text-sm">1</span>
                                </div>
                                <div>
                                    <div class="text-zinc-300 font-medium">数据获取</div>
                                    <div class="step-message text-xs text-zinc-500">等待中...</div>
                                </div>
                            </div>
                            <div class="step-status text-zinc-500 text-sm">0%</div>
                        </div>
                        <div class="w-full bg-zinc-700 rounded-full h-1.5">
                            <div class="step-progress bg-blue-500 h-1.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>

                    <div class="progress-step" data-step="技术分析">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-3">
                                <div class="step-icon w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                                    <span class="text-zinc-400 text-sm">2</span>
                                </div>
                                <div>
                                    <div class="text-zinc-300 font-medium">技术分析</div>
                                    <div class="step-message text-xs text-zinc-500">等待中...</div>
                                </div>
                            </div>
                            <div class="step-status text-zinc-500 text-sm">0%</div>
                        </div>
                        <div class="w-full bg-zinc-700 rounded-full h-1.5">
                            <div class="step-progress bg-blue-500 h-1.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>

                    <div class="progress-step" data-step="资讯查询">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-3">
                                <div class="step-icon w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                                    <span class="text-zinc-400 text-sm">3</span>
                                </div>
                                <div>
                                    <div class="text-zinc-300 font-medium">资讯查询</div>
                                    <div class="step-message text-xs text-zinc-500">等待中...</div>
                                </div>
                            </div>
                            <div class="step-status text-zinc-500 text-sm">0%</div>
                        </div>
                        <div class="w-full bg-zinc-700 rounded-full h-1.5">
                            <div class="step-progress bg-blue-500 h-1.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>

                    <div class="progress-step" data-step="AI分析">
                        <div class="flex items-center justify-between mb-2">
                            <div class="flex items-center gap-3">
                                <div class="step-icon w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center">
                                    <span class="text-zinc-400 text-sm">4</span>
                                </div>
                                <div>
                                    <div class="text-zinc-300 font-medium">AI分析</div>
                                    <div class="step-message text-xs text-zinc-500">等待中...</div>
                                </div>
                            </div>
                            <div class="step-status text-zinc-500 text-sm">0%</div>
                        </div>
                        <div class="w-full bg-zinc-700 rounded-full h-1.5">
                            <div class="step-progress bg-blue-500 h-1.5 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    const card = document.querySelector('[id*="analysis-content"]');
    if (card) {
        card.innerHTML = loadingHtml;
    }

    // 开始轮询进度
    if (stockCode) {
        startProgressPolling(stockCode);
    }
}

function startProgressPolling(stockCode) {
    // 清除旧的轮询
    if (window.progressPollingInterval) {
        clearInterval(window.progressPollingInterval);
    }

    window.progressPollingInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/analyze/progress?code=${stockCode}`);
            const data = await response.json();

            if (data.success) {
                updateProgress(data.step, data.progress, data.message);
            }
        } catch (error) {
            console.error('获取进度失败:', error);
        }
    }, 500); // 每500ms查询一次
}

function stopProgressPolling() {
    if (window.progressPollingInterval) {
        clearInterval(window.progressPollingInterval);
        window.progressPollingInterval = null;
    }
}

function updateProgress(step, progress, message) {
    // 更新主消息
    const stepMessage = document.getElementById('current-step-message');
    if (stepMessage) {
        stepMessage.textContent = message || `正在${step}...`;
    }

    // 更新对应步骤的进度
    const stepElements = document.querySelectorAll('.progress-step');
    stepElements.forEach(el => {
        const stepName = el.getAttribute('data-step');
        const progressBar = el.querySelector('.step-progress');
        const statusText = el.querySelector('.step-status');
        const stepMsg = el.querySelector('.step-message');
        const icon = el.querySelector('.step-icon');

        if (stepName === step) {
            // 当前步骤
            if (progressBar) progressBar.style.width = `${progress}%`;
            if (statusText) statusText.textContent = `${progress}%`;
            if (stepMsg) stepMsg.textContent = message || '进行中...';
            if (icon) {
                icon.classList.remove('bg-zinc-700', 'bg-green-600');
                icon.classList.add('bg-blue-500');
            }
            if (progress >= 100) {
                if (icon) {
                    icon.classList.remove('bg-blue-500');
                    icon.classList.add('bg-green-600');
                    icon.innerHTML = '<span class="text-white text-sm">✓</span>';
                }
                if (stepMsg) stepMsg.textContent = '完成';
            }
        }
    });
}
