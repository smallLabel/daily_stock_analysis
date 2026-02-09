# -*- coding: utf-8 -*-
"""
===================================
自选股选股页面 - NiceGUI Refactored
===================================
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
import os

from nicegui import ui, app
from web.utils.theme import Colors, Styles, setup_theme
from src.storage import get_db
from web.services.core import get_analysis_service
from src.enums import ReportType
from data_provider import DataFetcherManager
from data_provider.repository.stock_repo import StockDailyRepository

logger = logging.getLogger(__name__)

def format_datetime(value: Any) -> str:
    """格式化时间显示"""
    if not value:
        return '-'
    try:
        if isinstance(value, str):
            dt = datetime.fromisoformat(value.replace('Z', '+08:00'))
        elif isinstance(value, datetime):
            dt = value
        else:
            return str(value)
        return dt.strftime('%m-%d %H:%M')
    except Exception:
        return str(value)[:16] if str(value) else '-'

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
        self.quotes: Dict[str, Any] = {}
        self.analysis_results: Optional[Dict[str, Any]] = None

state = WatchlistState()

@ui.page('/watchlist')
async def watchlist_page():
    """自选股选股页面"""
    # Reset loading state
    state.is_loading = False
    
    setup_theme()
    
    # Refresh logic
    # Refresh logic
    async def load_watchlist(force_refresh: bool = False):
        try:
            state.is_loading = True
            watchlist_grid.refresh() # Show loading state if grid supports it or update UI elsewhere
            
            db = get_db()
            stocks = db.get_watchlist_stocks()
            state.watchlist = stocks
            
            # 1. Check data freshness
            repo = StockDailyRepository()
            last_update = await asyncio.get_event_loop().run_in_executor(None, repo.get_snapshot_status)
            
            should_fetch = True
            if not force_refresh and last_update:
                # Cache duration: 10 minutes
                if (datetime.now() - last_update).total_seconds() < 600:
                    should_fetch = False
                    ui.notify(f'使用缓存行情数据 ({last_update.strftime("%H:%M:%S")})', type='positive', position='bottom-right')
            
            if should_fetch:
                # 2. Fetch full market snapshot
                dm = DataFetcherManager()
                ui.notify('正在获取全市场实时行情...', type='info', position='bottom-right')
                
                try:
                    # Run in executor with timeout (30s)
                    snapshot_df = await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(None, dm.get_all_stocks_snapshot),
                        timeout=30.0
                    )
                    
                    if snapshot_df is not None and not snapshot_df.empty:
                        # Save to DB with timeout (60s)
                        ui.notify(f'获取成功，正在更新 {len(snapshot_df)} 条数据...', type='info', position='bottom-right')
                        saved_count = await asyncio.wait_for(
                            asyncio.get_event_loop().run_in_executor(None, repo.save_snapshot, snapshot_df),
                            timeout=60.0
                        )
                        ui.notify(f'数据库更新完成，新增/更新 {saved_count} 条记录', type='positive', position='bottom-right')
                    else:
                        ui.notify('获取全市场行情失败/为空，将显示历史数据', type='warning', position='bottom-right')
                except asyncio.TimeoutError:
                    ui.notify('获取/保存实时行情超时，将显示历史数据', type='warning', position='bottom-right')
                    logger.warning("Fetch/Save snapshot timed out")
                except Exception as e:
                    ui.notify(f'获取实时行情出错: {e}', type='warning', position='bottom-right')
                    logger.error(f"Error fetching snapshot: {e}")

            # 3. Read latest data from DB for watchlist
            codes = [s['stock_code'] for s in stocks]
            if codes:
                repo = StockDailyRepository()
                # Run in executor as DB read might block
                latest_data_map = await asyncio.get_event_loop().run_in_executor(None, repo.get_latest_batch, codes)
                
                # Convert to quotes format for UI
                state.quotes = {}
                for code, daily in latest_data_map.items():
                    if daily:
                        state.quotes[code] = {
                            'price': daily.close,
                            'change_pct': daily.pct_chg,
                            'volume': daily.volume,
                            'amount': daily.amount,
                            # Add other fields if needed by UI
                        }
            
            update_summary_counts()
            
        except Exception as e:
            ui.notify(f'加载自选股失败: {e}', type='negative')
            logger.error(f"Error loading watchlist: {e}", exc_info=True)
        finally:
            state.is_loading = False
            watchlist_grid.refresh()

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
            if any(s['stock_code'] == code for s in existing):
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
                 # ui.notify(f'已移除 {code}', type='positive')
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
            existing = {s['stock_code'] for s in db.get_watchlist_stocks()}
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

    
    
    # --- OCR Upload Logic ---
    
    # OCR State
    # 0: Upload, 1: Processing, 2: Review, 3: Error, 4: Success; importing = 导入中防重复提交
    ocr_state = {'step': 0, 'data': [], 'file_path': None, 'success_count': 0, 'error_msg': '', 'importing': False} 
    
    ocr_dialog = ui.dialog()
    
    with ocr_dialog, ui.card().classes('w-full max-w-3xl bg-[#141416] border border-zinc-700/80 p-0 overflow-hidden rounded-2xl shadow-xl ocr-dialog-reduce-motion'):
        # 标题栏
        with ui.row().classes('w-full justify-between items-center px-6 py-5 border-b border-zinc-700/80'):
             with ui.row().classes('items-center gap-3'):
                 with ui.element('div').classes('w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center'):
                     ui.icon('document_scanner', size='22px').classes('text-amber-400')
                 with ui.column().classes('gap-0.5'):
                     ui.label('智能截图识别').classes('text-xl font-semibold text-white tracking-tight')
                     ui.label('上传自选股截图，自动识别股票代码').classes('text-xs text-zinc-500')
             ui.button(icon='close', on_click=ocr_dialog.close).props('flat round color=white size=md aria-label="关闭"').classes('hover:bg-zinc-700/50 transition-colors duration-200 cursor-pointer min-w-[44px] min-h-[44px]')

        # 步骤条
        @ui.refreshable
        def render_progress_steps():
            step_config = [
                {'icon': 'cloud_upload', 'label': '上传', 'step': 0},
                {'icon': 'psychology', 'label': '识别', 'step': 1},
                {'icon': 'checklist', 'label': '确认', 'step': 2},
                {'icon': 'check_circle', 'label': '完成', 'step': 4}
            ]
            current_step = ocr_state['step']
            display_step = current_step if current_step != 3 else 1
            with ui.row().classes('w-full px-8 py-5 bg-zinc-900/40 rounded-b-xl justify-between items-start'):
                for idx, config in enumerate(step_config):
                    step_num = config['step']
                    is_active = display_step == step_num
                    is_completed = display_step > step_num or (current_step == 4)
                    if is_completed:
                        circle_class = 'bg-emerald-500/90 border-emerald-400 shadow-lg shadow-emerald-500/20'
                        text_class = 'text-emerald-400'
                        icon_class = 'text-white'
                    elif is_active:
                        circle_class = 'bg-amber-500 border-amber-400 shadow-lg shadow-amber-500/25 animate-pulse'
                        text_class = 'text-amber-400'
                        icon_class = 'text-white'
                    else:
                        circle_class = 'bg-zinc-700/80 border-zinc-600'
                        text_class = 'text-zinc-500'
                        icon_class = 'text-zinc-500'
                    with ui.column().classes('items-center gap-2 flex-1 min-w-0'):
                        with ui.element('div').classes(f'w-11 h-11 rounded-xl border {circle_class} flex items-center justify-center transition-all duration-300 shrink-0'):
                            ui.icon(config['icon'], size='22px').classes(icon_class)
                        ui.label(config['label']).classes(f'text-xs font-medium {text_class} transition-colors truncate w-full text-center')
                    if idx < len(step_config) - 1:
                        line_done = 'bg-emerald-500/60' if is_completed else 'bg-zinc-700'
                        ui.element('div').classes(f'flex-1 min-w-[20px] h-0.5 self-center mt-[-1.5rem] {line_done} transition-colors duration-300 mx-1')

        render_progress_steps()

        # 内容区
        ocr_content_area = ui.column().classes('w-full px-8 pb-8 pt-2 min-h-[380px] justify-center transition-all duration-300')
        
        async def extract_file_content_safe(e):
            """Robust file content extraction from NiceGUI upload event"""
            content = None
            import inspect
            
            # 1. Try standard 'content'
            if hasattr(e, 'content'):
                val = e.content
                try:
                    if hasattr(val, 'read'):
                        content = val.read()
                        if inspect.isawaitable(content): content = await content
                    elif isinstance(val, (bytes, bytearray)):
                        content = val
                except: pass
            
            # 2. Try 'files' list
            if not content and hasattr(e, 'files'):
                try:
                    if isinstance(e.files, list) and e.files:
                        f = e.files[0]
                        if hasattr(f, 'content'):
                            # recursive try? just get read
                            val = f.content
                            if hasattr(val, 'read'): 
                                content = val.read()
                                if inspect.isawaitable(content): content = await content
                            else: content = val
                except: pass
                
            # 3. Last resort: scan attributes for readable
            if not content:
                for attr_name in [a for a in dir(e) if not a.startswith('_')]:
                    val = getattr(e, attr_name)
                    if hasattr(val, 'read') and callable(val.read):
                        try:
                            content = val.read()
                            if inspect.isawaitable(content): content = await content
                            break
                        except: pass
            
            return content

        async def run_ocr_process(e):
            ocr_state['step'] = 1
            render_progress_steps.refresh()
            render_ocr_content.refresh()
            
            try:
                # 1. Read File
                content = await extract_file_content_safe(e)
                if not content:
                     ocr_state['error_msg'] = '无法读取文件内容，请确保文件格式正确'
                     ocr_state['step'] = 3 # Error State
                     render_progress_steps.refresh()
                     render_ocr_content.refresh()
                     return

                # 2. Save Temp
                import tempfile
                with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                ocr_state['file_path'] = tmp_path
                
                # 3. Process
                from web.services.ocr import get_ocr_service
                service = get_ocr_service()
                
                # Update UI to ensure spinner is seen
                await asyncio.sleep(0.5) 
                
                extracted = await asyncio.get_event_loop().run_in_executor(None, service.extract_stocks_from_image, tmp_path)
                logger.info(f"OCR extraction result: {len(extracted) if extracted else 0} stocks found")
                
                # Cleanup
                try:
                    os.remove(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to remove temp file: {e}")
                
                if not extracted:
                    ocr_state['error_msg'] = '未识别到股票代码，请上传清晰的自选股截图'
                    ocr_state['step'] = 3 # No results
                else:
                    # Filter logic
                    current_codes = {s['stock_code'] for s in state.watchlist}
                    ocr_state['data'] = []
                    new_set = set() # Avoid dupes in result
                    
                    for item in extracted:
                        code = item['code']
                        if code not in new_set:
                            item['is_new'] = code not in current_codes
                            item['selected'] = True # Default select all
                            ocr_state['data'].append(item)
                            new_set.add(code)
                    
                    ocr_state['step'] = 2

            except Exception as err:
                logger.error(f"OCR Failed: {err}")
                ocr_state['error_msg'] = f"处理失败: {str(err)}"
                ocr_state['step'] = 3
            
            render_progress_steps.refresh()
            render_ocr_content.refresh()

        async def confirm_import_ocr():
            selected = [x for x in ocr_state['data'] if x.get('selected')]
            if not selected:
                ui.notify('请至少选择一项', type='warning')
                return
            # UX: 防止重复提交（Loading Buttons）
            ocr_state['importing'] = True
            render_ocr_content.refresh()
            try:
                db = get_db()
                count = 0
                for stock in selected:
                    if db.save_watchlist_stock(stock['code'], stock['name']):
                        count += 1
                ocr_state['success_count'] = count
                ocr_state['step'] = 4  # Success State
                await load_watchlist()
                render_progress_steps.refresh()
                render_ocr_content.refresh()
                # Auto close after 2 seconds
                await asyncio.sleep(2)
                ocr_dialog.close()
            except Exception as e:
                ocr_state['error_msg'] = f"导入失败: {e}"
                ocr_state['step'] = 3  # Error State
                render_progress_steps.refresh()
                render_ocr_content.refresh()
            finally:
                ocr_state['importing'] = False
                render_ocr_content.refresh()

        def reset_ocr_state():
            ocr_state['step'] = 0
            ocr_state['data'] = []
            ocr_state['error_msg'] = ''
            ocr_state['success_count'] = 0
            ocr_state['importing'] = False
            render_progress_steps.refresh()
            render_ocr_content.refresh()

        @ui.refreshable
        def render_ocr_content():
            ocr_content_area.clear()
            step = ocr_state['step']
            
            with ocr_content_area:
                # --- STEP 0: 上传（点击打开文件选择；拖拽由底层 upload 接收）---
                if step == 0:
                     with ui.column().classes('w-full items-center gap-5'):
                        with ui.element('div').classes('relative w-full group min-h-[220px]'):
                             # 底层：upload 全屏透明，用于接收拖拽
                             ocr_upload = ui.upload(
                                 on_upload=run_ocr_process,
                                 auto_upload=True,
                                 max_file_size=10_000_000,
                                 multiple=False,
                             ).props('accept=".jpg,.jpeg,.png" flat square').classes(
                                 'absolute inset-0 w-full h-full opacity-0 z-[1] cursor-pointer'
                             )
                             # 顶层：可见上传区，点击时调用 pickFiles 打开系统文件选择
                             clickable_zone = ui.column().classes(
                                 'absolute inset-0 w-full min-h-[220px] py-12 border-2 border-dashed border-zinc-600 rounded-xl items-center justify-center '
                                 'bg-zinc-800/30 group-hover:border-amber-500/40 group-hover:bg-zinc-800/50 transition-all duration-300 cursor-pointer z-[2]'
                             )
                             with clickable_zone:
                                  with ui.element('div').classes('relative mb-3'):
                                      ui.element('div').classes('absolute inset-0 bg-amber-500/15 rounded-2xl blur-xl group-hover:bg-amber-500/25 transition-all')
                                      ui.icon('cloud_upload', size='3.5rem').classes('relative text-zinc-400 group-hover:text-amber-400 transition-all duration-300 group-hover:scale-105')
                                  with ui.column().classes('items-center gap-1.5'):
                                      ui.label('拖拽截图到此处，或点击上传').classes('text-base font-medium text-zinc-300 group-hover:text-zinc-200 transition-colors')
                                      ui.label('JPG / PNG，最大 10MB').classes('text-xs text-zinc-500')
                                      with ui.row().classes('gap-2 mt-1'):
                                          ui.badge('JPG', color='amber').props('outline dense')
                                          ui.badge('PNG', color='amber').props('outline dense')
                             clickable_zone.on('click', lambda: ocr_upload.run_method('pickFiles'))
                        with ui.card().classes('w-full bg-zinc-800/30 border border-zinc-600/50 rounded-xl p-4'):
                            with ui.row().classes('items-start gap-3'):
                                with ui.element('div').classes('w-8 h-8 rounded-lg bg-amber-500/20 flex items-center justify-center shrink-0'):
                                    ui.icon('lightbulb', size='18px').classes('text-amber-400')
                                with ui.column().classes('gap-1.5 flex-1'):
                                    ui.label('识别技巧').classes('text-sm font-semibold text-zinc-200')
                                    ui.label('• 截图清晰、股票代码可见，识别更准').classes('text-xs text-zinc-500 leading-relaxed')
                                    ui.label('• 同花顺自选股截图支持表格式专项识别').classes('text-xs text-zinc-500 leading-relaxed')
                                    ui.label('• 移动端竖屏截图：自动识别左侧纵行，上行名称、下行代码').classes('text-xs text-zinc-500 leading-relaxed')
                                    ui.label('• 已存在的股票将自动标记，无需重复添加').classes('text-xs text-zinc-500 leading-relaxed')

                # --- STEP 1: 识别中 ---
                elif step == 1:
                     with ui.column().classes('w-full items-center gap-8 py-14'):
                         with ui.element('div').classes('relative flex items-center justify-center'):
                             ui.element('div').classes('absolute w-28 h-28 bg-amber-500/20 rounded-2xl blur-2xl animate-pulse')
                             ui.spinner(size='5rem', thickness=2).props('color=amber').classes('relative')
                             ui.icon('document_scanner', size='2rem').classes('absolute text-amber-400/90')
                         with ui.column().classes('items-center gap-2'):
                             ui.label('正在识别中').classes('text-xl font-semibold text-white')
                             ui.label('正在提取截图中的股票代码与名称').classes('text-sm text-zinc-500')
                             with ui.row().classes('gap-1.5 mt-3'):
                                 for i in range(3):
                                     ui.element('div').classes('w-1.5 h-1.5 bg-amber-400 rounded-full animate-bounce').style(f'animation-delay: {i*0.15}s')

                # --- STEP 2: 确认导入 ---
                elif step == 2:
                     data = ocr_state['data']
                     new_items = [x for x in data if x['is_new']]
                     exist_items = [x for x in data if not x['is_new']]
                     with ui.column().classes('w-full gap-4 max-h-[480px] overflow-hidden flex flex-col'):
                         with ui.row().classes('items-center gap-3 pb-3 border-b border-zinc-700/80'):
                             with ui.element('div').classes('w-10 h-10 rounded-xl bg-emerald-500/20 flex items-center justify-center'):
                                 ui.icon('check_circle', size='24px').classes('text-emerald-400')
                             with ui.column().classes('gap-0.5'):
                                 ui.label('识别完成').classes('text-lg font-semibold text-white')
                                 ui.label(f'共 {len(data)} 个代码，{len(new_items)} 个可添加').classes('text-xs text-zinc-500')

                         with ui.scroll_area().classes('flex-grow rounded-xl border border-zinc-700/80 bg-zinc-800/30 p-3 min-h-0'):
                             if new_items:
                                 with ui.row().classes('items-center justify-between mb-2 px-1'):
                                     ui.label('可添加').classes('text-xs font-semibold text-emerald-400 uppercase tracking-wide')
                                     ui.badge(f'{len(new_items)}', color='positive').props('rounded')
                                 for idx, item in enumerate(new_items):
                                     with ui.card().classes('w-full bg-zinc-800/60 border border-zinc-600/80 hover:border-emerald-500/40 transition-colors duration-200 p-3 mb-2 cursor-pointer min-h-[44px] rounded-lg'):
                                         with ui.row().classes('w-full items-center justify-between'):
                                             with ui.row().classes('items-center gap-3 flex-1'):
                                                 # Checkbox: 勾选变化时刷新以更新「导入 N 个」按钮数字（UX: 即时反馈）
                                                 cb = ui.checkbox(value=item['selected']).props('dense color=green size=lg aria-label="选择股票"')
                                                 def toggle(val, i=item):
                                                     i['selected'] = val
                                                     render_ocr_content.refresh()
                                                 cb.on_value_change(lambda e, i=item: toggle(e.value))
                                                 # Stock Info
                                                 with ui.column().classes('gap-1 flex-1'):
                                                     with ui.row().classes('items-center gap-2'):
                                                         ui.label(item['code']).classes('font-mono font-bold text-white text-lg')
                                                         # Always display name
                                                         name_display = item['name'] if item['name'] else '未识别名称'
                                                         name_style = 'text-base text-zinc-300' if item['name'] else 'text-xs text-zinc-500 italic'
                                                         ui.label(name_display).classes(name_style)
                                                     ui.label(f'# {idx+1}').classes('text-xs text-zinc-600')
                                             ui.badge('新', color='positive').props('outline rounded').classes('text-xs')

                             if exist_items:
                                 ui.separator().classes('my-3 bg-zinc-700/80')
                                 with ui.row().classes('items-center justify-between mb-2 px-1'):
                                     ui.label('已在列表中').classes('text-xs font-medium text-zinc-500 uppercase tracking-wide')
                                     ui.badge(f'{len(exist_items)}', color='grey').props('rounded')
                                 for item in exist_items:
                                     with ui.card().classes('w-full bg-zinc-800/20 border border-zinc-700/80 p-3 mb-2 rounded-lg opacity-70'):
                                         with ui.row().classes('w-full items-center justify-between'):
                                             with ui.row().classes('items-center gap-3'):
                                                 ui.icon('check_circle', color='grey', size='md')
                                                 with ui.column().classes('gap-0'):
                                                     ui.label(item['code']).classes('font-mono text-zinc-500 line-through')
                                                     name_display = item['name'] if item['name'] else '未识别名称'
                                                     ui.label(name_display).classes('text-sm text-zinc-600')
                                             ui.label('已在列表').classes('text-xs text-zinc-600')

                         with ui.row().classes('w-full justify-between items-center pt-4 mt-1 border-t border-zinc-700/80 gap-3'):
                             ui.button('重新上传', icon='refresh', on_click=lambda: reset_ocr_state()).props('flat color=grey-8 aria-label="重新上传截图"').classes('hover:bg-zinc-700/50 rounded-lg min-h-[44px]')
                             with ui.row().classes('gap-2'):
                                 ui.button('取消', on_click=ocr_dialog.close).props('outline color=grey-7 aria-label="取消"').classes('rounded-lg min-h-[44px]')
                                 selected_count = len([x for x in new_items if x.get('selected')])
                                 is_importing = ocr_state.get('importing', False)
                                 btn_props = 'unelevated aria-label="确认导入所选股票"'
                                 if is_importing:
                                     btn_props += ' disable loading'
                                 ui.button(
                                     '导入中...' if is_importing else f'导入 {selected_count} 个',
                                     icon='download',
                                     on_click=confirm_import_ocr,
                                 ).props(btn_props).classes(
                                     'bg-amber-600 hover:bg-amber-700 text-white rounded-lg px-5 font-semibold min-h-[44px]'
                                 )

                # --- STEP 3: 识别失败 ---
                elif step == 3:
                     msg = ocr_state.get('error_msg', '未识别到有效信息')
                     with ui.column().classes('w-full items-center gap-6 py-10').props('role="alert" aria-live="assertive"'):
                         with ui.element('div').classes('relative ocr-error-icon'):
                             ui.element('div').classes('absolute inset-0 bg-red-500/15 rounded-2xl blur-xl motion-reduce:opacity-0')
                             with ui.element('div').classes('relative w-20 h-20 rounded-2xl bg-red-500/10 border border-red-500/40 flex items-center justify-center'):
                                ui.icon('error_outline', size='2.5rem').classes('text-red-400')
                         with ui.column().classes('items-center gap-2 max-w-sm'):
                             ui.label('识别失败').classes('text-lg font-semibold text-white')
                             ui.label(msg).classes('text-sm text-zinc-400 text-center leading-relaxed')
                         ui.button('重新上传', icon='refresh', on_click=lambda: reset_ocr_state()).props('outline flat aria-label="重新尝试识别"').classes('text-white border-zinc-600 hover:bg-zinc-700/50 rounded-lg px-6 min-h-[44px]')

                # --- STEP 4: 导入成功 ---
                elif step == 4:
                     count = ocr_state.get('success_count', 0)
                     with ui.column().classes('w-full items-center gap-6 py-10'):
                         with ui.element('div').classes('relative'):
                             ui.element('div').classes('absolute inset-0 bg-emerald-500/20 rounded-2xl blur-2xl')
                             with ui.element('div').classes('relative w-20 h-20 rounded-2xl bg-emerald-500/20 border border-emerald-400/50 flex items-center justify-center'):
                                ui.icon('check_circle', size='2.5rem').classes('text-emerald-400')
                         with ui.column().classes('items-center gap-1'):
                             ui.label('导入成功').classes('text-lg font-semibold text-white')
                             ui.label(f'已添加 {count} 只自选股，列表已刷新').classes('text-sm text-zinc-400')
                         with ui.row().classes('gap-1.5 mt-2'):
                             for i in range(3):
                                 ui.element('div').classes('w-2 h-2 bg-emerald-400 rounded-full animate-ping').style(f'animation-delay: {i*0.12}s')

        render_ocr_content()

    def open_ocr_dialog():
        reset_ocr_state()
        ocr_dialog.open()

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
                 ui.button('刷新列表', icon='refresh', on_click=lambda: load_watchlist(force_refresh=True)).props('flat color=grey')

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
                ui.button('OCR 截图导入', icon='document_scanner', on_click=open_ocr_dialog).props('outline color=amber')
                ui.button('清空全部', icon='delete', on_click=clear_watchlist).props('outline color=red')

        # Content Area: Grid & Analysis
        with ui.grid().classes('w-full grid-cols-1 lg:grid-cols-3 gap-6'):
            
            # Left: Watchlist Table (Approx 2/3 width)
            with ui.column().classes('lg:col-span-2 w-full gap-4'):
                
                # Watchlist Grid/Table
                @ui.refreshable
                def render_grid():
                    if state.is_loading:
                         with ui.column().classes(f'w-full h-64 items-center justify-center p-8 bg-zinc-900/50 rounded-xl border border-dashed border-zinc-700'):
                             ui.spinner('dots', size='3em', color='blue')
                             ui.label('正在同步全市场行情...').classes('text-zinc-500 mt-4 animate-pulse')
                             ui.label('（首次加载可能需要几秒钟）').classes('text-xs text-zinc-600')
                         return

                    if not state.watchlist:
                         with ui.column().classes(f'w-full h-64 items-center justify-center {CARD_STYLE} border-dashed'):
                             ui.icon('sentiment_dissatisfied', size='48px', color='grey')
                             ui.label('暂无自选股').classes('text-zinc-500 mt-2')
                         return
                    
                    columns = [
                        {'name': 'code', 'label': '代码', 'field': 'stock_code', 'align': 'left', 'sortable': True},
                        {'name': 'name', 'label': '名称', 'field': 'stock_name', 'align': 'left', 'sortable': True},
                        {'name': 'price', 'label': '当前价', 'field': 'price', 'align': 'right', 'sortable': True},
                        {'name': 'change', 'label': '涨跌幅', 'field': 'change_pct', 'align': 'right', 'sortable': True},
                        {'name': 'volume', 'label': '成交量', 'field': 'volume', 'align': 'right', 'sortable': True},
                        {'name': 'amount', 'label': '成交额', 'field': 'amount', 'align': 'right', 'sortable': True},
                        {'name': 'result', 'label': 'AI评分', 'field': 'score', 'align': 'center', 'sortable': True},
                        {'name': 'actions', 'label': '操作', 'align': 'center'}
                    ]
                    
                    rows = []
                    for s in state.watchlist:
                        code = s['stock_code']
                        r = s.copy()
                        r['created_at'] = format_datetime(r.get('created_at'))
                        
                        # Enrich with Realtime Quote
                        if state.quotes and code in state.quotes:
                            q = state.quotes[code]
                            r['price'] = q.get('price', '-')
                            r['change_pct'] = q.get('change_pct', 0)
                            r['volume'] = q.get('volume', 0)
                            r['amount'] = q.get('amount', 0)
                        else:
                            r['price'] = '-'
                            r['change_pct'] = 0
                            r['volume'] = '-'
                            r['amount'] = '-'

                        # Enrich with Analysis Result
                        if state.analysis_results and code in state.analysis_results:
                            res = state.analysis_results[code]
                            r['score'] = res.get('sentiment_score', 0)
                        else:
                            r['score'] = None
                            
                        rows.append(r)

                    with ui.table(columns=columns, rows=rows, pagination=10).classes('w-full bg-zinc-900 text-white border-zinc-700') as table:
                        # Price Column: Red for Up, Green for Down (A-share style)
                        table.add_slot('body-cell-price', r'''
                            <q-td :props="props">
                                <span :class="props.row.change_pct > 0 ? 'text-red-500' : (props.row.change_pct < 0 ? 'text-green-500' : 'text-gray-400')">
                                    {{ props.value }}
                                </span>
                            </q-td>
                        ''')
                        
                        # Change Column: With Arrow and Color
                        table.add_slot('body-cell-change', r'''
                            <q-td :props="props">
                                <div :class="props.row.change_pct > 0 ? 'text-red-500' : (props.row.change_pct < 0 ? 'text-green-500' : 'text-gray-400')">
                                    <q-icon v-if="props.row.change_pct > 0" name="arrow_drop_up" />
                                    <q-icon v-if="props.row.change_pct < 0" name="arrow_drop_down" />
                                    {{ props.value > 0 ? '+' : '' }}{{ props.value }}%
                                </div>
                            </q-td>
                        ''')
                        
                        # Volume Column: Format number
                        table.add_slot('body-cell-volume', r'''
                            <q-td :props="props">
                                <div class="text-zinc-400 text-xs">
                                    {{ (props.value / 10000).toFixed(1) }}万
                                </div>
                            </q-td>
                        ''')
                        
                        # Amount Column: Format Currency
                        table.add_slot('body-cell-amount', r'''
                            <q-td :props="props">
                                <div class="text-zinc-400 text-xs">
                                    {{ (props.value / 100000000).toFixed(2) }}亿
                                </div>
                            </q-td>
                        ''')

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
                        
                        async def confirm_delete(e):
                            stock = e.args
                            code = stock['stock_code']
                            with ui.dialog() as dialog, ui.card().classes('bg-zinc-800 border-zinc-700'):
                                ui.label(f'确认移除 {code} 吗？').classes('text-lg font-bold text-white')
                                with ui.row().classes('w-full justify-end gap-2 mt-4'):
                                    ui.button('取消', on_click=dialog.close).props('flat color=grey')
                                    async def do_delete():
                                        await remove_stock(code)
                                        dialog.close()
                                    ui.button('确认移除', on_click=do_delete).props('unelevated color=red')
                            dialog.open()

                        table.on('delete', confirm_delete)
                        


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
    # Init
    # Defer loading to allow UI to render first
    ui.timer(0.1, lambda: asyncio.create_task(load_watchlist()), once=True)

    # Add styles for table custom slots if needed
    ui.add_head_html('''
    <style>
    body { overflow: hidden !important; }
    .q-page-container { padding-top: 0 !important; }
    .q-table__container { background-color: transparent !important; }
    .q-table__top, .q-table__bottom, thead tr:first-child th { background-color: rgba(24, 24, 27, 0.5) !important; color: white !important; }
    tbody tr:hover { background-color: rgba(63, 63, 70, 0.3) !important; }
    @media (prefers-reduced-motion: reduce) {
      .ocr-dialog-reduce-motion .animate-pulse,
      .ocr-dialog-reduce-motion .animate-bounce,
      .ocr-dialog-reduce-motion .animate-ping { animation: none !important; }
    }
    </style>
    ''')

