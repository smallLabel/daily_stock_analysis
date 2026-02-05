"""
Settings UI 优化版本 - 实现 Vertical Tabs 布局与真实配置保存
"""

from nicegui import ui
from web.utils.theme import setup_theme
from web.services import get_all_env_config, get_config_service
import logging

logger = logging.getLogger(__name__)

# Design System
class DesignSystem:
    """Professional fintech design system"""
    
    # Colors
    PRIMARY = '#2563EB'        # Professional blue
    PRIMARY_HOVER = '#1D4ED8'
    PRIMARY_LIGHT = '#3B82F6'
    ACCENT = '#F97316'         # Orange for CTAs
    SUCCESS = '#10B981'
    WARNING = '#F59E0B'
    DANGER = '#EF4444'
    
    # Backgrounds
    BG_PRIMARY = '#09090B'     # Deep dark
    BG_SURFACE = '#18181B'     # Card surface
    BG_SIDEBAR = '#121214'     # Sidebar background (slightly lighter than deep dark)
    BG_HOVER = '#27272A'
    
    # Text
    TEXT_PRIMARY = '#FAFAFA'
    TEXT_SECONDARY = '#A1A1AA'
    TEXT_MUTED = '#71717A'
    
    # Borders
    BORDER_DEFAULT = '#27272A'
    BORDER_FOCUS = '#3B82F6'
    
    # Typography
    FONT_HEADING = 'Inter, system-ui, -apple-system, sans-serif'
    
    # Effects
    SHADOW_SM = '0 1px 2px 0 rgb(0 0 0 / 0.05)'
    SHADOW_MD = '0 4px 6px -1px rgb(0 0 0 / 0.1)'
    SHADOW_GLOW = f'0 0 20px 0 {PRIMARY}40'
    
    TRANSITION_DEFAULT = '200ms cubic-bezier(0.4, 0, 0.2, 1)'


class ConfigManager:
    """配置管理器"""
    
    def __init__(self):
        self.config = {}
        self.inputs = {}
        self.changes = set()
        self.changes_label = None
        self.config_service = get_config_service()
    
    def load_config(self):
        """加载配置"""
        self.config = get_all_env_config()
        return self.config
    
    def mark_changed(self, key):
        """标记配置已更改"""
        self.changes.add(key)
        self._update_changes_label()
    
    def has_changes(self):
        return len(self.changes) > 0
    
    def _update_changes_label(self):
        if self.changes_label:
            count = len(self.changes)
            if count > 0:
                self.changes_label.text = f'共 {count} 项未保存'
                self.changes_label.classes('text-sm px-3 py-1.5 rounded-full font-medium transition-all duration-200').style(
                    f'background: {DesignSystem.WARNING}20; color: {DesignSystem.WARNING}; border: 1px solid {DesignSystem.WARNING}50;'
                )
            else:
                self.changes_label.text = '所有配置已保存'
                self.changes_label.classes('text-sm font-medium transition-all duration-200').style(
                    f'color: {DesignSystem.TEXT_MUTED};'
                )
    
    async def save_all(self):
        """保存所有更改到 .env"""
        try:
            updates = {}
            # 仅处理已标记为变更的项
            for key in list(self.changes): # Create copy to iterate
                if key in self.inputs:
                    input_widget = self.inputs[key]
                    val = None
                    if hasattr(input_widget, 'value'):
                        if isinstance(input_widget, type(ui.switch)):
                            val = 'true' if input_widget.value else 'false'
                        else:
                            val = str(input_widget.value or '')
                        
                        # 转换 key (UI key -> ENV key)
                        # 这里简单处理，假设 key 就是 ENV key (大写)
                        # 但是 UI 中传递的 key 是小写的 (e.g. 'gemini_api_key')
                        # 需要映射回大写。
                        
                        env_key = key.upper()
                        updates[env_key] = val
            
            if not updates:
                ui.notify('没有需要保存的更改', type='info')
                return True

            success = self.config_service.update_multiple_configs(updates)
            
            if success:
                self.changes.clear()
                self._update_changes_label()
                ui.notify('✅ 配置已保存到 .env 文件', type='positive')
                return True
            else:
                ui.notify('❌ 保存失败', type='negative')
                return False
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}", exc_info=True)
            ui.notify(f'❌ 保存异常: {str(e)}', type='negative')
            return False


def create_input_field(
    config_manager: ConfigManager, 
    label: str, 
    key: str, 
    value: str, 
    input_type: str = 'text', 
    placeholder: str = '', 
    width: str = 'flex-grow',
    options: list = None
):
    """创建通用输入字段"""
    
    with ui.row().classes('w-full items-center gap-4 py-1'):
        # Label
        with ui.column().classes('w-48 shrink-0 gap-0'):
            ui.label(label).classes('text-sm font-medium').style(f'color: {DesignSystem.TEXT_PRIMARY};')
            if key:
                ui.label(key.upper()).classes('text-xs font-mono').style(f'color: {DesignSystem.TEXT_MUTED};')
        
        input_widget = None
        
        style_props = f'background-color: {DesignSystem.BG_HOVER}; border-color: {DesignSystem.BORDER_DEFAULT};'
        
        if input_type == 'password':
            input_widget = ui.input(
                value=value or '', 
                password=True, 
                password_toggle_button=True,
                placeholder=placeholder
            ).classes(width).props('outlined dense dark').style(style_props)
            
        elif input_type == 'switch':
            # NiceGUI switch props
            input_widget = ui.switch(value=(str(value).lower() == 'true')).props('dark').style(
                f'color: {DesignSystem.PRIMARY};'
            )
            
        elif input_type == 'select':
            input_widget = ui.select(
                options or [], 
                value=value
            ).classes(width).props('outlined dense dark').style(style_props)
            
        elif input_type == 'number':
            try:
                num_value = float(value) if value else 0
            except:
                num_value = 0
            input_widget = ui.number(
                value=num_value,
                placeholder=placeholder
            ).classes(width).props('outlined dense dark').style(style_props)
            
        else:  # text
            input_widget = ui.input(
                value=value or '',
                placeholder=placeholder
            ).classes(width).props('outlined dense dark').style(style_props)
        
        # 监听变化
        if input_widget:
            input_widget.on('update:model-value', lambda: config_manager.mark_changed(key))
            config_manager.inputs[key] = input_widget
        
        return input_widget


@ui.page('/settings_v2')
def settings_page_v2():
    """系统设置页面 - Vertical Tabs Layout"""
    setup_theme()
    
    config_manager = ConfigManager()
    config = config_manager.load_config()
    
    # 注入 CSS
    ui.add_css(f'''
        .settings-splitter .q-splitter__separator {{
            background-color: {DesignSystem.BORDER_DEFAULT};
            width: 1px;
        }}
        .settings-tab {{
            justify-content: center !important;
            padding: 12px 16px;
            margin-bottom: 4px;
            border-radius: 8px;
            color: {DesignSystem.TEXT_SECONDARY};
            transition: all 0.2s;
            text-transform: none !important;
            font-weight: 500;
            display: flex !important;
        }}
        .settings-tab .q-tab__content {{
            width: 100%;
            justify-content: center !important;
            flex: 1 1 auto;
        }}
        .settings-tab .q-tab__icon {{
            margin-right: 8px; /* 图标和文字的间距 */
        }}
        .settings-tab .q-tab__label {{
            text-align: left; /* 文字本身左对齐，但在 flex 容器中居中 */
        }}
        .settings-tab .q-focus-helper {{
            visibility: hidden;
        }}
        .settings-tab.q-tab--active {{
            background-color: {DesignSystem.PRIMARY}15;
            color: {DesignSystem.PRIMARY};
        }}
        .settings-panel {{
            background: transparent;
            padding: 0 0 24px 0;
        }}
    ''')

    # Main Container
    with ui.row().classes('w-full h-screen no-wrap').style(f'background: {DesignSystem.BG_PRIMARY};'):
        
        # 1. Sidebar (Navigation ONLY)
        with ui.column().classes('w-64 h-full p-4 border-r border-[#27272A] flex flex-col shrink-0').style(f'background: {DesignSystem.BG_SIDEBAR};'):
            # Title
            with ui.row().classes('items-center gap-2 px-2 mb-6'):
                ui.icon('settings', size='24px').style(f'color: {DesignSystem.PRIMARY};')
                ui.label('系统设置').classes('text-xl font-bold tracking-tight').style(f'color: {DesignSystem.TEXT_PRIMARY};')

            # Scrollable drawer for tabs
            with ui.column().classes('flex-grow overflow-y-auto pr-2').style('max-height: calc(100vh - 180px);'):
                # Vertical Tabs Control (With inline-label for alignment)
                with ui.tabs().props('vertical inline-label indicator-color="transparent"').classes('w-full settings-tabs gap-2') as tabs:
                    t_ai = ui.tab('AI', label='AI 模型', icon='psychology').classes('settings-tab')
                    t_data = ui.tab('Data', label='数据源 & 搜索', icon='storage').classes('settings-tab')
                    t_notify = ui.tab('Notification', label='通知渠道', icon='notifications').classes('settings-tab')
            
            # Bottom Action: Return - More prominent styling (always visible)
            with ui.row().classes('w-full px-2 py-3 mt-4 rounded-lg transition-all').style(f'background: {DesignSystem.BG_HOVER}; border: 1px solid {DesignSystem.BORDER_DEFAULT};'):
                ui.button('返回首页', icon='home', on_click=lambda: ui.navigate.to('/')).props('flat').classes('w-full font-medium').style(f'color: {DesignSystem.TEXT_PRIMARY};')

        # 2. Content Area (Splitter Right)
        with ui.column().classes('flex-grow h-full overflow-hidden'):
            # Header Area (Title + Global Actions)
            with ui.row().classes('w-full h-20 items-center justify-between px-8 border-b border-[#27272A]').style(f'background: {DesignSystem.BG_PRIMARY};'):
                 with ui.column().classes('gap-0'):
                    ui.label('详细配置').classes('text-lg font-bold text-white')
                    ui.label('修改配置后请点击保存').classes('text-xs text-zinc-500')
                 
                 # Right Side: Changes Status + Save Button
                 with ui.row().classes('items-center gap-4'):
                     config_manager.changes_label = ui.label('所有配置已保存').classes('text-xs font-medium').style(f'color: {DesignSystem.TEXT_MUTED};')
                     
                     ui.button('保存更改', icon='save', on_click=config_manager.save_all).props('unelevated').classes('px-6 py-2 rounded-lg font-bold transition-all hover:scale-105').style(
                        f'background: {DesignSystem.PRIMARY}; color: white; box-shadow: {DesignSystem.SHADOW_GLOW};'
                     )

            # Scrollable Panel Area
            with ui.scroll_area().classes('w-full h-[calc(100%-64px)] p-8'):
                with ui.tab_panels(tabs, value='AI').classes('w-full max-w-4xl bg-transparent animated fadeIn'):

                    # --- AI 模型 ---
                    with ui.tab_panel(t_ai).classes('settings-panel gap-6'):
                        ui.label('AI 模型配置').classes('text-2xl font-bold mb-4 text-white')
                        
                        # Gemini
                        with ui.card().classes('w-full p-6 rounded-xl border border-[#27272A] bg-[#18181B]'):
                            with ui.row().classes('items-center justify-between w-full mb-4'):
                                ui.label('Google Gemini').classes('text-lg font-medium text-blue-400')
                                ui.button('测试连接', icon='link', on_click=lambda: ui.notify('连接成功 (模拟)', type='positive')).props('flat dense size=sm color=blue')
                            
                            create_input_field(config_manager, 'API Key', 'gemini_api_key', config['ai_config'].get('gemini_api_key'), 'password')
                            create_input_field(config_manager, '模型名称', 'gemini_model', config['ai_config'].get('gemini_model'))
                        
                        # OpenAI
                        with ui.card().classes('w-full p-6 rounded-xl border border-[#27272A] bg-[#18181B] mt-6'):
                            with ui.row().classes('items-center justify-between w-full mb-4'):
                                ui.label('OpenAI / 兼容接口').classes('text-lg font-medium text-green-400')
                                ui.button('测试连接', icon='link').props('flat dense size=sm color=green')
                            
                            create_input_field(config_manager, 'API Key', 'openai_api_key', config['ai_config'].get('openai_api_key'), 'password')
                            create_input_field(config_manager, '接口地址', 'openai_base_url', config['ai_config'].get('openai_base_url'), placeholder='https://api.openai.com/v1')
                            create_input_field(config_manager, '模型名称', 'openai_model', config['ai_config'].get('openai_model'))
                            create_input_field(config_manager, '温度参数', 'openai_temperature', config['ai_config'].get('openai_temperature'), 'number')

                    # --- 数据源 ---
                    with ui.tab_panel(t_data).classes('settings-panel gap-6'):
                        ui.label('数据源与搜索').classes('text-2xl font-bold mb-4 text-white')
                        
                        with ui.card().classes('w-full p-6 rounded-xl border border-[#27272A] bg-[#18181B]'):
                            ui.label('搜索API配置').classes('text-lg font-medium mb-4 text-amber-400')
                            create_input_field(config_manager, 'Tavily Key', 'tavily_api_keys', config['search_config'].get('tavily_api_keys'), 'password')
                            create_input_field(config_manager, 'SerpAPI Key', 'serpapi_api_keys', config['search_config'].get('serpapi_api_keys'), 'password')

                    # --- 通知 ---
                    with ui.tab_panel(t_notify).classes('settings-panel gap-6'):
                        ui.label('通知渠道').classes('text-2xl font-bold mb-4 text-white')
                        
                        with ui.card().classes('w-full p-6 rounded-xl border border-[#27272A] bg-[#18181B]'):
                            ui.label('即时通讯 Webhook').classes('text-lg font-medium mb-4 text-purple-400')
                            create_input_field(config_manager, '企业微信', 'wechat_webhook_url', config['notification_config'].get('wechat_webhook_url'), 'password')
                            create_input_field(config_manager, '飞书', 'feishu_webhook_url', config['notification_config'].get('feishu_webhook_url'), 'password')
                            create_input_field(config_manager, 'Discord', 'discord_webhook_url', config['notification_config'].get('discord_webhook_url'), 'password')
                        
                        with ui.card().classes('w-full p-6 rounded-xl border border-[#27272A] bg-[#18181B] mt-6'):
                            ui.label('Telegram').classes('text-lg font-medium mb-4 text-blue-400')
                            create_input_field(config_manager, 'Bot Token', 'telegram_bot_token', config['notification_config'].get('telegram_bot_token'), 'password')
                            create_input_field(config_manager, 'Chat ID', 'telegram_chat_id', config['notification_config'].get('telegram_chat_id'))


