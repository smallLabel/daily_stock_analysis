from nicegui import ui

# =========================================================
# Theme & Styles
# =========================================================
# 设置全局颜色主题
ui.colors(
    primary='#2563eb',    # 科技蓝
    secondary='#64748b',  # 沉稳灰
    accent='#8b5cf6',     # 强调紫
    positive='#10b981',   # 成功绿
    negative='#ef4444',   # 警告红
    info='#3b82f6',
    warning='#f59e0b'
)

# 自定义 CSS 增强质感
ui.add_head_html('''
<style>
    body {
        background-color: #f8fafc;
        font-family: 'Inter', -apple-system, system-ui, sans-serif;
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.9);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.5);
    }
    .gradient-text {
        background: linear-gradient(135deg, #2563eb, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
''')

# =========================================================
# Layout Components
# =========================================================

def render_header():
    with ui.header().classes('bg-white/80 backdrop-blur-md text-gray-800 shadow-sm border-b border-gray-200 items-center h-16 px-6'):
        # Logo Area
        with ui.row().classes('items-center gap-2'):
            ui.icon('query_stats').classes('text-3xl text-blue-600')
            ui.label('StockMind').classes('text-2xl font-black tracking-tight text-gray-800')
            ui.label('AI Pro').classes('text-xs font-bold bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full')

        ui.space()

        # Navigation Mockup
        with ui.row().classes('gap-1 mr-8 hidden md:flex'):
            for label, icon in [('仪表盘', 'dashboard'), ('自选股', 'star'), ('持仓', 'account_balance_wallet')]:
                ui.button(label, icon=icon).props('flat').classes('text-gray-600 hover:text-blue-600 font-medium')

        # User / Settings
        with ui.row().classes('items-center gap-2'):
            ui.button(icon='notifications').props('flat round').classes('text-gray-500')
            ui.avatar('robot', color='blue-100', text_color='blue-600').classes('cursor-pointer')

def render_sidebar():
    # 这里可以放左侧导航，但在现代设计中，如果是即用型工具，单页更清爽
    pass

# =========================================================
# Main Content
# =========================================================

# =========================================================
# Main Content
# =========================================================

# 直接构建页面（Script Mode）
render_header()

with ui.column().classes('w-full max-w-7xl mx-auto p-6 gap-8'):
    
    # 1. Hero Section / Input Area
    with ui.row().classes('w-full justify-center mt-8'):
        with ui.card().classes('w-full max-w-3xl p-8 rounded-2xl shadow-xl bg-gradient-to-br from-white to-blue-50 border border-blue-100'):
            ui.label('开始智能分析').classes('text-3xl font-bold mb-2 gradient-text text-center w-full')
            ui.label('输入 A股 / 港股 / 美股 代码，获取 AI 深度投研报告').classes('text-gray-500 text-center w-full mb-8')
            
            with ui.row().classes('w-full gap-4 items-stretch'):
                # 输入框
                with ui.input(placeholder='例如: 600519, AAPL, 00700').props('outlined rounded item-aligned input-class="text-lg uppercase"').classes('flex-grow text-lg h-14') as input_field:
                    with input_field.add_slot('prepend'):
                        ui.icon('search').classes('text-gray-400')
                
                # 报告类型选择
                select = ui.select(['精简日报', '深度研报', '技术面分析'], value='精简日报').props('outlined rounded').classes('w-40 h-14')
                
                # 分析按钮
                analyze_btn = ui.button('立即分析', icon='auto_awesome') \
                    .classes('bg-blue-600 text-white text-lg font-bold px-8 rounded-xl shadow-lg shadow-blue-200 hover:scale-105 transition-transform h-14')

    # 2. Dashboard Grid
    with ui.row().classes('w-full gap-6 items-start'):
        
        # Left: Task Status & Updates
        with ui.column().classes('w-full md:w-2/3 gap-6'):
            
            # Active Task Card
            with ui.card().classes('w-full p-0 rounded-2xl border border-gray-100 shadow-sm overflow-hidden'):
                with ui.row().classes('p-5 bg-white border-b border-gray-100 items-center justify-between'):
                    with ui.row().classes('gap-2 items-center'):
                        ui.icon('list_alt').classes('text-blue-500')
                        ui.label('分析任务队列').classes('font-bold text-lg text-gray-800')
                    ui.chip('2 进行中', color='blue', text_color='white', icon='sync').props('dense')

                # Styled Table
                columns = [
                    {'name': 'code', 'label': '标的', 'field': 'code', 'align': 'left', 'classes': 'font-bold'},
                    {'name': 'type', 'label': '类型', 'field': 'type', 'align': 'left'},
                    {'name': 'status', 'label': '状态', 'field': 'status', 'align': 'left'},
                    {'name': 'progress', 'label': '进度', 'field': 'progress', 'align': 'center'},
                    {'name': 'action', 'label': '操作', 'field': 'action', 'align': 'right'},
                ]
                rows = [
                    {'code': 'AAPL.US', 'type': '深度研报', 'status': 'Running', 'progress': 0.7},
                    {'code': '600519.SH', 'type': '精简日报', 'status': 'Completed', 'progress': 1.0},
                    {'code': '00700.HK', 'type': '技术面分析', 'status': 'Waiting', 'progress': 0.0},
                ]
                
                with ui.table(columns=columns, rows=rows, row_key='code').classes('w-full no-shadow') as table:
                    # 自定义渲染让表格更漂亮
                    table.add_slot('body-cell-status', '''
                        <q-td :props="props">
                            <q-badge :color="props.value == 'Completed' ? 'green' : (props.value == 'Running' ? 'blue' : 'grey')">
                                {{ props.value }}
                            </q-badge>
                        </q-td>
                    ''')
                    table.add_slot('body-cell-progress', '''
                        <q-td :props="props">
                            <q-linear-progress :value="props.value" size="10px" class="rounded-full" :color="props.value == 1 ? 'green' : 'blue'" track-color="blue-1">
                            </q-linear-progress>
                        </q-td>
                    ''')

        # Right: Market / Watchlist
        with ui.column().classes('w-full md:w-1/3 gap-6'):
            
            with ui.card().classes('w-full p-5 rounded-2xl border border-gray-100 shadow-sm bg-white'):
                with ui.row().classes('items-center justify-between mb-4'):
                    ui.label('🎯 重点关注').classes('font-bold text-lg text-gray-800')
                    ui.button(icon='add').props('flat round size=sm')

                # Stock List Item
                for stock in [
                    {'code': 'NVDA', 'name': 'NVIDIA Corp', 'price': '822.79', 'change': '+3.12%', 'up': True},
                    {'code': 'TSLA', 'name': 'Tesla Inc', 'price': '175.34', 'change': '-1.20%', 'up': False},
                    {'code': 'MSFT', 'name': 'Microsoft', 'price': '415.50', 'change': '+0.55%', 'up': True},
                ]:
                    with ui.row().classes('w-full items-center justify-between py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 px-2 rounded-lg cursor-pointer transition-colors'):
                        with ui.row().classes('gap-3 items-center'):
                            ui.avatar(stock['code'][0], color='gray-100', text_color='gray-800').classes('font-bold')
                            with ui.column().classes('gap-0'):
                                ui.label(stock['code']).classes('font-bold text-gray-800')
                                ui.label(stock['name']).classes('text-xs text-gray-500')
                        
                        with ui.column().classes('items-end gap-0'):
                            ui.label(stock['price']).classes('font-medium')
                            color = 'text-green-500 bg-green-50' if stock['up'] else 'text-red-500 bg-red-50'
                            ui.label(stock['change']).classes(f'text-xs font-bold px-2 py-0.5 rounded {color}')

# Start the App
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(title='StockMind AI', port=8081, show=False)
