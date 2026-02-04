import os
import sys

# Ensure the project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from web.main_ui import init_ui
    from nicegui import ui
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Please ensure you have installed nicegui: pip install nicegui")
    sys.exit(1)

if __name__ in {"__main__", "__mp_main__"}:
    print("Starting Daily Stock Analysis UI...")
    print("Access the UI at http://localhost:8080")
    
    # Initialize the UI
    init_ui()
    
    # Run the application
    ui.run(
        title='Daily Stock Analysis', 
        dark=True, 
        port=8080,
        show=True, # Automatically open browser
        reload=True # Enable hot reloading for development
    )
