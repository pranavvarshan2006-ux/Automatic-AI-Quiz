import os
import sys
import webbrowser
import threading
import time

def get_base_dir():
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))

# Point Flask templates and static folders to bundled files
base_dir = get_base_dir()
template_folder = os.path.join(base_dir, 'templates')

from dotenv import load_dotenv

# Try loading .env from directory where exe is placed, or bundled directory
exe_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(exe_dir, '.env')
if os.path.exists(env_path):
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv(dotenv_path=os.path.join(base_dir, '.env'))

# Import app from app.py and configure template directory
import app as flask_module
flask_module.app.template_folder = template_folder

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")

if __name__ == '__main__':
    print("=" * 50)
    print("Starting Flask Web Application...")
    print("Opening browser automatically at http://127.0.0.1:5000")
    print("Keep this window open while using the application.")
    print("Press Ctrl+C to stop.")
    print("=" * 50)
    
    threading.Thread(target=open_browser, daemon=True).start()
    flask_module.app.run(host="127.0.0.1", port=5000, debug=False)
