import os
import sys
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Skip UI tests if tkinter is not available (e.g., headless CI environments)
pytest_plugins = []

try:
    import tkinter as tk
    TKINTER_AVAILABLE = True
except ImportError:
    TKINTER_AVAILABLE = False

def test_tkinter_available():
    """Test that tkinter is available in the environment."""
    try:
        import tkinter as tk
        # Test basic tkinter functionality
        root = tk.Tk()
        root.withdraw()  # Hide the window
        root.destroy()
        assert True
    except ImportError:
        pytest.skip("tkinter not available in this environment")

@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="tkinter not available")
def test_ui_imports():
    """Test that UI module can be imported without errors."""
    try:
        import ui
        assert hasattr(ui, 'App')
        assert hasattr(ui, 'SeedManager')
    except ImportError as e:
        pytest.fail(f"Failed to import ui module: {e}")

@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="tkinter not available")
def test_app_class_creation():
    """Test that App class can be instantiated without errors."""
    import ui
    
    # Create app but don't call mainloop (which would block)
    try:
        app = ui.App()
        assert app is not None
        assert hasattr(app, 'seed_mgr')
        assert hasattr(app, 'run')
        
        # Clean up
        app.destroy()
    except Exception as e:
        pytest.fail(f"Failed to create App instance: {e}")

@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="tkinter not available")
def test_seed_manager_creation():
    """Test that SeedManager can be created."""
    import ui
    import tkinter as tk
    
    try:
        root = tk.Tk()
        root.withdraw()  # Hide window
        
        def mock_shape_getter():
            return (10, 10, 10)
        
        def mock_status_callback(msg):
            pass
        
        seed_mgr = ui.SeedManager(root, mock_shape_getter, mock_status_callback)
        assert seed_mgr is not None
        assert hasattr(seed_mgr, 'seeds')
        assert hasattr(seed_mgr, 'add_seed')
        assert hasattr(seed_mgr, 'clear_all')
        assert isinstance(seed_mgr.seeds, list)
        
        root.destroy()
    except Exception as e:
        pytest.fail(f"Failed to create SeedManager: {e}")

@pytest.mark.skipif(not TKINTER_AVAILABLE, reason="tkinter not available")
def test_ui_variables_initialization():
    """Test that App initializes all required variables."""
    import ui
    
    try:
        app = ui.App()
        
        # Check that key variables are initialized
        assert hasattr(app, 'Z') and app.Z.get() > 0
        assert hasattr(app, 'Y') and app.Y.get() > 0
        assert hasattr(app, 'X') and app.X.get() > 0
        assert hasattr(app, 'steps') and app.steps.get() > 0
        assert hasattr(app, 'birth')
        assert hasattr(app, 'survive')
        assert hasattr(app, 'mut_enable')
        assert hasattr(app, 'outdir')
        
        app.destroy()
    except Exception as e:
        pytest.fail(f"Failed to initialize App variables: {e}")

def test_ui_module_structure():
    """Test UI module structure without requiring tkinter."""
    # This test can run even without tkinter
    import importlib.util
    import os
    
    ui_path = os.path.join(os.path.dirname(__file__), '..', 'ui.py')
    spec = importlib.util.spec_from_file_location("ui", ui_path)
    
    # Just test that the file can be read and has expected structure
    with open(ui_path, 'r') as f:
        content = f.read()
        
    assert 'class App(' in content
    assert 'class SeedManager(' in content
    assert 'import tkinter' in content
    assert 'from life3d import Life3DRGB' in content
    assert 'from visualize import render_voxels' in content