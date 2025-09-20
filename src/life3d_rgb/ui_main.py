"""Safe UI entry point that gracefully handles missing Tkinter."""

def main():
    """Main UI entry point with guarded Tkinter imports."""
    try:
        # Check if Tkinter is available
        import tkinter as tk
        from tkinter import ttk, messagebox, colorchooser, simpledialog
        
        # Make them available globally for the UI module
        import sys
        current_module = sys.modules[__name__]
        current_module.tk = tk
        current_module.ttk = ttk
        current_module.messagebox = messagebox
        current_module.colorchooser = colorchooser
        current_module.simpledialog = simpledialog
        
    except ImportError:
        raise SystemExit(
            "Tkinter is not available in this environment. "
            "Install a Python build with Tcl/Tk (e.g. from python.org or homebrew with tcl-tk) and try again."
        )
    
    # Try to import and run the UI
    try:
        from .ui import main as ui_main
        ui_main()
    except NameError as e:
        if 'ttk' in str(e) or 'tk' in str(e):
            raise SystemExit(
                "UI module requires Tkinter components that are not available. "
                "This installation may not support GUI applications."
            )
        else:
            raise
    except Exception as e:
        print(f"Error starting UI: {e}")
        raise SystemExit(1)

if __name__ == "__main__":
    main()