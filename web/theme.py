from nicegui import ui

# Color Palette (Dark Mode - Zinc based)
class Colors:
    PRIMARY = '#2563EB'      # Blue 600
    PRIMARY_HOVER = '#1D4ED8' # Blue 700
    
    BG = '#09090B'           # Zinc 950
    SURFACE = '#18181B'      # Zinc 900
    SURFACE_HOVER = '#27272A' # Zinc 800
    
    TEXT = '#FAFAFA'         # Zinc 50
    TEXT_MUTED = '#A1A1AA'   # Zinc 400
    
    BORDER = '#27272A'       # Zinc 800
    
    SUCCESS = '#10B981'
    ERROR = '#EF4444'
    WARNING = '#F59E0B'
    INFO = '#3B82F6'

# Application Theme Setup
def setup_theme():
    """Initialize the application theme"""
    # Load fonts (Inter for UI, JetBrains Mono for code/numbers)
    ui.add_head_html('''
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&family=Noto+Sans+SC:wght@400;500;700&display=swap" rel="stylesheet">
        <style>
            body { font-family: 'Inter', 'Noto Sans SC', sans-serif; background-color: #09090B; color: #FAFAFA; margin: 0; padding: 0; overflow: hidden; }
            .font-mono { font-family: 'JetBrains Mono', monospace; }
            /* Hide scrollbar for Chrome, Safari and Opera */
            ::-webkit-scrollbar {
                display: none;
            }
            /* Hide scrollbar for IE, Edge and Firefox */
            body {
                -ms-overflow-style: none;  /* IE and Edge */
                scrollbar-width: none;  /* Firefox */
            }
        </style>
    ''')
    
    # Set default native styling to dark
    ui.dark_mode().enable()

    # Define custom classes via Tailwind
    # We can use ui.add_css if needed, but Tailwind is preferred inline or via config.
    # NiceGUI allows Tailwind classes directly.

# Component Styles
class Styles:
    # Containers
    CONTAINER = 'max-w-7xl mx-auto p-6 transition-all duration-300'
    CARD = f'bg-[{Colors.SURFACE}] border border-[{Colors.BORDER}] rounded-xl p-6 shadow-sm hover:shadow-md transition-all duration-200'
    
    # Typography
    H1 = 'text-3xl font-bold tracking-tight mb-2'
    H2 = 'text-2xl font-semibold tracking-tight mb-4'
    SUBTITLE = f'text-[{Colors.TEXT_MUTED}] text-sm mb-6'
    LABEL = f'text-[{Colors.TEXT_MUTED}] text-xs font-medium uppercase tracking-wider mb-1'
    
    # Components
    BUTTON_PRIMARY = f'bg-[{Colors.PRIMARY}] text-white px-4 py-2 rounded-lg font-medium hover:bg-[{Colors.PRIMARY_HOVER}] transition-colors duration-200 shadow-sm'
    BUTTON_SECONDARY = f'bg-transparent border border-[{Colors.BORDER}] text-[{Colors.TEXT}] px-4 py-2 rounded-lg font-medium hover:bg-[{Colors.SURFACE_HOVER}] transition-colors duration-200'
    INPUT = f'bg-[{Colors.BG}] border border-[{Colors.BORDER}] text-[{Colors.TEXT}] rounded-lg px-3 py-2 w-full focus:outline-none focus:border-[{Colors.PRIMARY}] focus:ring-1 focus:ring-[{Colors.PRIMARY}] transition-all duration-200'
    
    # Status badges
    BADGE_SUCCESS = 'bg-emerald-500/10 text-emerald-500 px-2 py-0.5 rounded text-xs font-medium border border-emerald-500/20'
    BADGE_ERROR = 'bg-red-500/10 text-red-500 px-2 py-0.5 rounded text-xs font-medium border border-red-500/20'
    BADGE_WARNING = 'bg-amber-500/10 text-amber-500 px-2 py-0.5 rounded text-xs font-medium border border-amber-500/20'
    
    # Grid
    GRID_DASHBOARD = 'grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6'
