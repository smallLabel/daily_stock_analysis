# -*- coding: utf-8 -*-
"""
===================================
自选股选股页面 - NiceGUI Refactored
===================================
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional

from nicegui import ui, app
from web.utils.theme import Colors, Styles, setup_theme
from src.storage import get_db
from web.services.core import get_analysis_service
from src.enums import ReportType

logger = logging.getLogger(__name__)

# Constants for Styling
GLASS_BG = "bg-zinc-900/50"
GLASS_BORDER = "border-white/10"
GLASS_EFFECT = "backdrop-blur-md"
CARD_STYLE = f"{GLASS_BG} {GLASS_BORDER} {GLASS_EFFECT} rounded-xl border p-6 transition-all duration-300 hover:border-blue-500/30"

class WatchlistState:
    def __init__(self):
        self.watchlist: List[Dict[str, Any]] = []
        self.selected_stocks: List[str] = []
        self.is_loading: bool = False
        self.analysis_results: Optional[Dict[str, Any]] = None

state = WatchlistState()

@ui.page('/watchlist')
async def watchlist_page():
    """自选股选股页面"""
    setup_theme()
    
    # Refresh logic
    async def load_watchlist():
        try:
            db = get_db()
            stocks = db.get_watchlist_stocks()
            state.watchlist = [s.to_dict() for s in stocks]
            watchlist_grid.refresh()
            update_summary_counts()
        except Exception as e:
            ui.notify(f'加载自选股失败: {e}', type='negative')

    async def add_stock(code: str, name: str = ""):
        code = code.strip().upper()
        if not code:
            ui.notify('请输入股票代码', type='warning')
            return
        
        # Simple validation
        if not code.isdigit() or len(code) != 6:
             ui.notify('无效的股票代码格式（需6位数字）', type='warning')
             return

        try:
            db = get_db()
            # Check existence
            existing = db.get_watchlist_stocks()
            if any(s.stock_code == code for s in existing):
                ui.notify(f'{code} 已在自选股中', type='info')
                return

            if db.save_watchlist_stock(code, name):
                ui.notify(f'已添加 {code}', type='positive')
                await load_watchlist()
                code_input.value = "" # Clear input
                name_input.value = ""
            else:
                 ui.notify('保存失败', type='negative')
        except Exception as e:
            ui.notify(f'添加失败: {e}', type='negative')

    async def remove_stock(code: str):
        try:
            db = get_db()
            if db.delete_watchlist_stock(code):
                 ui.notify(f'已移除 {code}', type='positive')
                 await load_watchlist()
            else:
                 ui.notify('移除失败', type='negative')
        except Exception as e:
            ui.notify(f'操作失败: {e}', type='negative')

    async def clear_watchlist():
        try:
            db = get_db()
            if db.clear_watchlist():
                ui.notify('已清空所有自选股', type='positive')
                await load_watchlist()
        except Exception as e:
            ui.notify(f'清空失败: {e}', type='negative')

    async def import_from_config():
        try:
            # Import logic mirroring ApiHandler
            from web.services.core import get_config_service
            config_service = get_config_service()
            stock_list_str = config_service.get_stock_list()
            
            if not stock_list_str:
                ui.notify('配置中无股票', type='warning')
                return

            codes = [c.strip() for c in stock_list_str.split(',') if c.strip()]
            valid_codes = [c for c in codes if c.isdigit() and len(c)==6]
            
            if not valid_codes:
                 ui.notify('无有效股票代码', type='warning')
                 return

            db = get_db()
            existing = {s.stock_code for s in db.get_watchlist_stocks()}
            new_codes = [c for c in valid_codes if c not in existing]
            
            if new_codes:
                if db.save_watchlist_stocks(new_codes):
                    ui.notify(f'成功导入 {len(new_codes)} 只股票', type='positive')
                    await load_watchlist()
                else:
                    ui.notify('部分导入失败', type='negative')
            else:
                ui.notify('所有股票已存在', type='info')

        except Exception as e:
            ui.notify(f'导入失败: {e}', type='negative')

    async def start_analysis():
        if not state.watchlist:
            ui.notify('自选股为空，请先添加', type='warning')
            return
        
        state.is_loading = True
        loading_overlay.classes(remove='hidden')
        results_container.classes(add='hidden')
        
        try:
            service = get_analysis_service()
            # Analyze all local watchlist stocks
            # Note: In a real app, you might want to analyze only selected or use a queue
            # Here we follow existing logic: analyze all
            codes = [s['stock_code'] for s in state.watchlist]
            
            # Since analysis service is async but we might need to wait for results 
            # or trigger a background task. 
            # If the service returns a task_id immediately:
            # result = service.submit_analysis(code...
            
            # However, the original UI fetched /api/analysis?codes=... which seemed to wait 
            # or return task info. The original handlers.py handle_analysis does ONE code.
            # But the javascript was looping or the API handled comma separated? 
            # Original JS: fetch('/api/analysis?codes=' + stockCodes)
            # Check ApiHandler.handle_analysis... it gets `code_list[0]`. It handles ONE code.
            # Wait, existing `watchlist.py` JS calls `/api/analysis?codes=...` 
            # But `ApiHandler.handle_analysis` takes `code_list[0]`. 
            # This suggests the original code actually might have been broken for multiple codes 
            # OR I misread the handler.
            # Let's re-read the handler quickly. 
            # `code_list = query.get("code", [])` -> `code = code_list[0].strip()`
            # It seems it ONLY handled the first code! 
            # Ideally we want to batch analyze.
            
            # For this redesign, let's implement a proper batch analysis loops 
            # or check if there is a batch API.
            # Assuming no batch API, we loop.
            
            results = []
            analyzed_count = 0
            
            # Use asyncio.gather for parallelism if backend supports it safely
            # or sequential to be safe.
            for s in state.watchlist:
                code = s['stock_code']
                # Submitting task...
                # The service method `submit_analysis` returns a dict with task_id.
                # We actually want the RESULT. 
                # If `submit_analysis` is async and waits, good. 
                # If it just queues, we need to poll.
                # Looking at `analysis_service.submit_analysis` would be good. 
                # But for now, let's assume we can loop and notify.
                
                # To make this responsive, we can't block the main thread.
                # We'll run in executor or use the service if it's async.
                try:
                     # Simulate specific logic from original:
                     # The original JS seemed to expect a JSON response with data.
                     # If the backend only returns task_id, the original JS `displayResults(data.data)` 
                     # would fail unless `handle_analysis` returns the result.
                     # The handler returns `JsonResponse(result)`. 
                     # `result` comes from `analysis_service.submit_analysis`.
                     
                     res = service.submit_analysis(code, report_type=ReportType.SIMPLE)
                     # If it returns a task object, we might need to wait for it?
                     # Existing code implies it returns result immediately or the user was mistaken about functionality.
                     # "analysis_service" usually implies background tasks in modern apps.
                     # But let's assume it works for now.
                     
                     # Actually, to improve this, let's just trigger it and tell user 
                     # "Check Dashboard/Tasks" or if we want real-time, we need a better mechanism.
                     # BUT, the original requirement asks for functional parity + improvement.
                     # Let's show a "Tasks Submited" and maybe a results table if we can get them.
                     
                     analyzed_count += 1
                except Exception as e:
                    logger.error(f"Error analyzing {code}: {e}")
            
            ui.notify(f'已提交 {analyzed_count} 个分析任务', type='positive')
            
            # For the purpose of this UI, since we can't easily get sync results from an async task system
            # without polling, we will just show the updated dashboard or tasks link.
            # OR we can try to fetch the result if it's cached.
            
        except Exception as e:
            ui.notify(f'分析请求失败: {e}', type='negative')
        finally:
            state.is_loading = False
            loading_overlay.classes(add='hidden')

    

    # --- Analysis Logic ---

    async def poll_analysis_results(task_ids: List[str]):
        """Polls for analysis results until all are completed or failed"""
        service = get_analysis_service()
        completed_count = 0
        
        while task_ids and state.is_loading:
            pending = []
            results_updated = False
            
            for tid in task_ids:
                status = service.get_task_status(tid)
                if not status:
                    pending.append(tid)
                    continue
                
                task_state = status.get('status')
                if task_state in ['completed', 'failed']:
                    # Task done
                    if task_state == 'completed' and status.get('result'):
                        # Update result in state
                        code = status['code']
                        if not state.analysis_results:
                            state.analysis_results = {}
                        state.analysis_results[code] = status['result']
                        results_updated = True
                        completed_count += 1
                    elif task_state == 'failed':
                         ui.notify(f"分析 {status['code']} 失败: {status.get('error')}", type='negative')
                else:
                    pending.append(tid)
            
            task_ids = pending
            
            if results_updated:
                 watchlist_grid.refresh()
                 # Show results container if hidden
                 results_container.classes(remove='hidden')
                 render_analysis_results.refresh()

            if not task_ids:
                break
                
            await asyncio.sleep(1.0) # Poll every second
            
        state.is_loading = False
        loading_overlay.classes(add='hidden')
        if completed_count > 0:
             ui.notify(f'分析完成: {completed_count} 只股票', type='positive')

    async def start_analysis():
        if not state.watchlist:
            ui.notify('自选股为空，请先添加', type='warning')
            return
        
        state.is_loading = True
        loading_overlay.classes(remove='hidden')
        results_container.classes(remove='hidden')
        state.analysis_results = {} # Clear previous
        render_analysis_results.refresh() # Clear view
        
        try:
            service = get_analysis_service()
            task_ids = []
            
            for s in state.watchlist:
                code = s['stock_code']
                # Submit task
                res = service.submit_analysis(code, report_type=ReportType.SIMPLE)
                if res.get('success') and 'task_id' in res:
                    task_ids.append(res['task_id'])
            
            if task_ids:
                ui.notify(f'已提交 {len(task_ids)} 个分析任务', type='info')
                # Start polling in background
                asyncio.create_task(poll_analysis_results(task_ids))
            else:
                 state.is_loading = False
                 loading_overlay.classes(add='hidden')
                 ui.notify('任务提交失败', type='warning')

        except Exception as e:
            state.is_loading = False
            loading_overlay.classes(add='hidden')
            ui.notify(f'分析请求失败: {e}', type='negative')

    
    # --- History Performance Logic ---
    
    async def show_history_performance():
        try:
            import os
            import json
            from data_provider import DataFetcherManager
            
            history_dir = os.path.join(os.getcwd(), 'data', 'history')
            if not os.path.exists(history_dir):
                ui.notify('暂无历史记录', type='info')
                return

            files = [f for f in os.listdir(history_dir) if f.startswith('recommendation_')]
            if not files:
                 ui.notify('暂无历史推荐记录', type='info')
                 return
            
            files.sort(reverse=True)
            target_file = files[0] # Simplification: Just take latest
            
            with open(os.path.join(history_dir, target_file), 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            recs = data.get('all_recommendations', [])
            if not recs:
                 ui.notify('最近记录无推荐', type='info')
                 return
            
            # Fetch realtime
            codes = [r['code'] for r in recs]
            dm = DataFetcherManager()
            quotes = dm.get_realtime_quotes(codes)
            
            perf_data = []
            total_ret = 0
            win_count = 0
            
            for r in recs:
                code = r['code']
                start = r['current_price']
                curr = quotes.get(code, {}).get('current', start)
                
                ret = 0.0
                if start > 0:
                    ret = ((curr - start) / start) * 100
                
                if ret > 0: win_count += 1
                total_ret += ret
                
                perf_data.append({
                    'code': code,
                    'name': r['name'],
                    'start': start,
                    'curr': curr,
                    'ret': ret,
                    'strategy': r.get('strategy_name', '-')
                })
            
            count = len(recs)
            win_rate = (win_count / count) * 100 if count else 0
            avg_ret = total_ret / count if count else 0
            date_str = target_file.split('_')[1].split('.')[0]
            
            # Update Dialog
            history_dialog.open()
            render_history_content.refresh(date_str, count, win_rate, avg_ret, perf_data)
            
        except Exception as e:
            ui.notify(f'获取战绩失败: {e}', type='negative')
            logger.error(f"History Error: {e}")

    # --- UI Layout ---

    # Header
    with ui.header().classes('bg-transparent border-b border-[#27272A] py-2 px-4 backdrop-blur-md sticky top-0 z-50'):
        with ui.row().classes('w-full items-center justify-between no-wrap'):
            with ui.row().classes('items-center gap-2'):
                ui.icon('show_chart', size='24px', color=Colors.PRIMARY)
                ui.label('股票每日分析').classes('text-lg font-bold tracking-tight')
            
            with ui.row().classes('items-center gap-4'):
                ui.button(icon='notifications', on_click=lambda: ui.notify('暂无新通知')).props('flat round color=grey')
                ui.avatar(icon='person', color=Colors.SURFACE_HOVER).classes('cursor-pointer')

    # Drawer
    with ui.left_drawer().props('show-if-above bordered width=256 break-point=0').classes('bg-[#09090B] border-r border-[#27272A] p-4'):
        nav_items = [
            ('dashboard', '仪表盘', '/'),
            ('star', '自选股选股', '/watchlist'),
            ('analytics', '深度分析', '/'),
            ('settings', '系统设置', '/settings_v2'),
        ]
        
        with ui.column().classes('gap-2 w-full'):
            for icon, label, route in nav_items:
                is_active = label == '自选股选股'
                bg_class = f'bg-[{Colors.SURFACE}]' if is_active else 'hover:bg-zinc-900'
                text_class = f'text-[{Colors.PRIMARY}]' if is_active else f'text-[{Colors.TEXT_MUTED}]'
                
                with ui.row().classes(f'w-full items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors {bg_class}').on('click', lambda r=route: ui.navigate.to(r) if r != '/watchlist' else None):
                    ui.icon(icon).classes(text_class)
                    ui.label(label).classes(f'text-sm font-medium {text_class}')

    # Main Content
    with ui.column().classes('w-full h-screen px-6 pb-6 gap-6 overflow-auto bg-[#000000] no-scrollbar'):
        
        # Title & Stats
        with ui.row().classes('w-full justify-between items-center'):
            with ui.column().classes('gap-1'):
                ui.label('自选股管理').classes('text-2xl font-bold text-white tracking-tight')
                ui.label('管理您的投资组合并跟踪表现').classes('text-sm text-zinc-400')
            
            with ui.row().classes('gap-2'):
                 ui.button('战绩回顾', icon='history', on_click=show_history_performance).props('flat color=green')
                 ui.button('刷新列表', icon='refresh', on_click=load_watchlist).props('flat color=grey')

            # Verification Button
            ui.button('验证昨日推荐', icon='rule', on_click=lambda: show_verification_results()).props('flat color=amber')

        # Control Bar (Add & Actions)
        with ui.row().classes(f'w-full items-center gap-4 {CARD_STYLE}'):
            # Add Stock Input
            with ui.row().classes('items-center gap-2 flex-grow'):
                code_input = ui.input(placeholder='股票代码 (600519)').props('outlined dense dark').classes('w-48')
                name_input = ui.input(placeholder='名称 (可选)').props('outlined dense dark').classes('w-40')
                ui.button('添加', icon='add', on_click=lambda: add_stock(code_input.value, name_input.value)).classes('bg-blue-600 hover:bg-blue-700 text-white')

            # Actions
            with ui.row().classes('items-center gap-2'):
                ui.button('导入配置', icon='file_download', on_click=import_from_config).props('outline color=white')
                ui.button('清空全部', icon='delete', on_click=clear_watchlist).props('outline color=red')

        # Content Area: Grid & Analysis
        with ui.grid().classes('w-full grid-cols-1 lg:grid-cols-3 gap-6'):
            
            # Left: Watchlist Table (Approx 2/3 width)
            with ui.column().classes('lg:col-span-2 w-full gap-4'):
                
                # Watchlist Grid/Table
                @ui.refreshable
                def render_grid():
                    if not state.watchlist:
                         with ui.column().classes(f'w-full h-64 items-center justify-center {CARD_STYLE} border-dashed'):
                             ui.icon('sentiment_dissatisfied', size='48px', color='grey')
                             ui.label('暂无自选股').classes('text-zinc-500 mt-2')
                         return
                    
                    columns = [
                        {'name': 'code', 'label': '代码', 'field': 'stock_code', 'align': 'left', 'sortable': True},
                        {'name': 'name', 'label': '名称', 'field': 'stock_name', 'align': 'left', 'sortable': True},
                        {'name': 'time', 'label': '加入时间', 'field': 'created_at', 'align': 'left', 'sortable': True, 'style': 'font-family: monospace'},
                        {'name': 'result', 'label': '分析评分', 'field': 'result', 'align': 'center'}, # Placeholder for inline result
                        {'name': 'actions', 'label': '操作', 'align': 'center'}
                    ]
                    
                    rows = []
                    for s in state.watchlist:
                        r = s.copy()
                        # Enrich with analysis result if available
                        if state.analysis_results and s['stock_code'] in state.analysis_results:
                            res = state.analysis_results[s['stock_code']]
                            r['score'] = res.get('sentiment_score', 0)
                        else:
                            r['score'] = None
                        rows.append(r)

                    with ui.table(columns=columns, rows=rows, pagination=10).classes('w-full bg-zinc-900 text-white border-zinc-700') as table:
                        table.add_slot('body-cell-result', r'''
                            <q-td :props="props">
                                <q-badge v-if="props.row.score != null" 
                                    :color="props.row.score >= 8 ? 'green' : (props.row.score < 4 ? 'red' : 'orange')"
                                    outline>
                                    {{ props.row.score.toFixed(1) }}
                                </q-badge>
                                <span v-else class="text-gray-500">-</span>
                            </q-td>
                        ''')
                        table.add_slot('body-cell-actions', r'''
                            <q-td :props="props">
                                <q-btn icon="delete" flat round color="red" size="sm" 
                                    @click="$parent.$emit('delete', props.row)" />
                            </q-td>
                        ''')
                        table.on('delete', lambda e: remove_stock(e.args['stock_code']))

                watchlist_grid = render_grid
                watchlist_grid()

            # Right: Analysis & Stats (Approx 1/3 width)
            with ui.column().classes('w-full gap-4'):
                
                # Action Card
                with ui.column().classes(f'w-full gap-4 {CARD_STYLE}'):
                    ui.label('智能分析').classes('text-xl font-bold text-white')
                    ui.label('基于最新市场数据进行AI多维度分析').classes('text-sm text-zinc-400')
                    
                    ui.button('🚀 开始一键分析', on_click=start_analysis) \
                        .classes('w-full bg-gradient-to-r from-blue-600 to-purple-600 h-12 text-lg font-bold shadow-lg hover:shadow-blue-500/20')
                    
                    ui.separator().classes('bg-zinc-700')
                    
                    with ui.row().classes('w-full justify-between'):
                        ui.label('总数').classes('text-zinc-400')
                        limit_label = ui.label('0').classes('text-white font-mono')

                # Results Summary (Right side detailed view)
                @ui.refreshable
                def render_analysis_results():
                    if not state.analysis_results:
                        return
                    
                    with ui.column().classes(f'w-full gap-3 {CARD_STYLE} max-h-[60vh] overflow-auto'):
                        ui.label('分析结果').classes('font-bold text-white mb-2')
                        
                        sorted_res = sorted(state.analysis_results.values(), key=lambda x: x.get('sentiment_score', 0), reverse=True)
                        
                        for res in sorted_res:
                            score = res.get('sentiment_score', 0)
                            color_cls = 'text-green-400' if score >= 8 else ('text-red-400' if score < 4 else 'text-amber-400')
                            
                            with ui.row().classes('w-full justify-between items-start border-b border-white/5 pb-2'):
                                with ui.column().classes('gap-0'):
                                    ui.label(f"{res.get('name')}").classes('font-bold text-white')
                                    ui.label(f"{res.get('code')}").classes('text-xs text-zinc-500')
                                
                                ui.label(f"{score:.1f}").classes(f'font-mono font-bold {color_cls}')
                            
                            ui.label(res.get('operation_advice', '-')).classes('text-xs text-zinc-300 mb-2')

                render_analysis_results()


    # Loading Overlay
    with ui.element('div').classes('fixed inset-0 bg-black/80 backdrop-blur-sm z-[100] flex flex-col items-center justify-center hidden') as loading_overlay:
        ui.spinner(size='4rem', color='blue')
        ui.label('正在进行多维度分析...').classes('text-white text-xl mt-4 max-w-md text-center animate-pulse')
    
    # --- Analysis Verification Dialog ---
    
    verify_dialog = ui.dialog()
    with verify_dialog, ui.card().classes('w-full max-w-4xl bg-[#18181B] border border-[#27272A]'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
             ui.label('🔍 昨日推荐验证').classes('text-2xl font-bold text-amber-500')
             ui.button(icon='close', on_click=verify_dialog.close).props('flat round color=white')
        
        @ui.refreshable
        def render_verification_content(results=[]):
            if not results:
                ui.label('暂无昨日分析记录或数据不足').classes('text-zinc-400')
                return

            columns = [
                {'name': 'name', 'label': '股票', 'field': 'name', 'align': 'left'},
                {'name': 'date', 'label': '分析日期', 'field': 'analysis_date', 'align': 'left'},
                {'name': 'rec', 'label': '分析时价格', 'field': 'rec_price'},
                {'name': 'curr', 'label': '现价', 'field': 'curr_price'},
                {'name': 'ret', 'label': '收益', 'field': 'return_pct'},
                {'name': 'status', 'label': '状态', 'field': 'status'}
            ]
            
            with ui.table(columns=columns, rows=results, pagination=10).classes('w-full bg-zinc-900 text-white') as table:
                 table.add_slot('body-cell-ret', r'''
                    <q-td :props="props">
                        <span :class="props.row.return_pct >= 0 ? 'text-green-400' : 'text-red-400'">
                            {{ props.row.return_pct.toFixed(2) }}%
                        </span>
                    </q-td>
                 ''')
                 table.add_slot('body-cell-status', r'''
                    <q-td :props="props">
                        <q-badge :color="props.row.badge_color">
                            {{ props.row.status }}
                        </q-badge>
                    </q-td>
                 ''')

        render_verification_content([])

    async def show_verification_results():
        try:
            from web.services.verification import get_verification_service
            
            if not state.watchlist:
                ui.notify('自选股列表为空', type='warning')
                return
                
            codes = [s['stock_code'] for s in state.watchlist]
            service = get_verification_service()
            
            verify_dialog.open()
            ui.notify('正在验证数据...', type='info')
            
            # Run in executor to avoid blocking
            results = await asyncio.get_event_loop().run_in_executor(None, service.verify_predictions, codes)
            
            render_verification_content.refresh(results)
            
            if not results:
                ui.notify('未找到昨日分析记录', type='warning')
                
        except Exception as e:
            ui.notify(f'验证失败: {e}', type='negative')
            logger.error(f"Verification Error: {e}")

    # History Dialog
    history_dialog = ui.dialog()

    with history_dialog, ui.card().classes('w-full max-w-4xl bg-[#18181B] border border-[#27272A]'):
        with ui.row().classes('w-full justify-between items-center mb-4'):
             ui.label('📜 历史战绩回顾').classes('text-2xl font-bold text-blue-500')
             ui.button(icon='close', on_click=history_dialog.close).props('flat round color=white')
             
        @ui.refreshable
        def render_history_content(date_str="", count=0, win_rate=0, avg_ret=0, rows=[]):
             with ui.row().classes('w-full grid grid-cols-4 gap-4 mb-6 p-4 bg-[#27272A]/50 rounded-xl'):
                  def stat_item(label, value, color='text-blue-500'):
                      with ui.column().classes('text-center'):
                           ui.label(label).classes('text-zinc-400 text-sm mb-1')
                           ui.label(str(value)).classes(f'text-xl font-bold {color}')
                  
                  stat_item('分析日期', date_str)
                  stat_item('推荐数量', count)
                  stat_item('胜率', f"{win_rate:.1f}%", 'text-green-500' if win_rate>=50 else 'text-red-500')
                  stat_item('平均收益', f"{avg_ret:.2f}%", 'text-green-500' if avg_ret>=0 else 'text-red-500')

             columns = [
                 {'name': 'name', 'label': '股票', 'field': 'name', 'align': 'left'},
                 {'name': 'start', 'label': '推荐价', 'field': 'start'},
                 {'name': 'curr', 'label': '现价', 'field': 'curr'},
                 {'name': 'ret', 'label': '收益率', 'field': 'ret', 'sortable': True},
                 {'name': 'strategy', 'label': '策略', 'field': 'strategy'}
             ]
             
             with ui.table(columns=columns, rows=rows, pagination=10).classes('w-full bg-zinc-900 text-white') as table:
                 table.add_slot('body-cell-name', r'''
                    <q-td :props="props">
                        <div>{{ props.row.name }}</div>
                        <div class="text-xs text-gray-500">{{ props.row.code }}</div>
                    </q-td>
                 ''')
                 table.add_slot('body-cell-ret', r'''
                    <q-td :props="props">
                        <span :class="props.row.ret >= 0 ? 'text-green-400' : 'text-red-400'">
                            {{ props.row.ret.toFixed(2) }}%
                        </span>
                    </q-td>
                 ''')

        render_history_content()

    def update_summary_counts():
        limit_label.set_text(str(len(state.watchlist)))

    # Init
    await load_watchlist()

    # Add styles for table custom slots if needed
    ui.add_head_html('''
    <style>
    body { overflow: hidden !important; }
    .q-page-container { padding-top: 0 !important; }
    .q-table__container { background-color: transparent !important; }
    .q-table__top, .q-table__bottom, thead tr:first-child th { background-color: rgba(24, 24, 27, 0.5) !important; color: white !important; }
    tbody tr:hover { background-color: rgba(63, 63, 70, 0.3) !important; }
    </style>
    ''')

