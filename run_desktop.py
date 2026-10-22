"""
Desktop Launcher untuk Aplikasi Kasir & Inventaris Toko
Membuka aplikasi dalam mode Window Desktop (Edge / Chrome App Mode atau Default Browser)
"""
import os
import sys
import time
import shutil
import threading
import subprocess
import webbrowser
import urllib.request

HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"

def is_server_ready():
    try:
        with urllib.request.urlopen(URL, timeout=1) as response:
            return response.status in (200, 302)
    except Exception:
        return False

def run_flask():
    from app import app, init_db
    init_db()
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    app.run(host=HOST, port=PORT, debug=False, use_reloader=False)

def find_browser_app():
    candidates = [
        os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%LocalAppData%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        shutil.which("msedge"),
        shutil.which("chrome"),
    ]
    for p in candidates:
        if p and os.path.exists(p):
            return p
    return None

def main():
    print("=" * 60)
    print("   MEMULAI APLIKASI KASIR TOKO ")
    print("=" * 60)

    if not is_server_ready():
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        
        for _ in range(10):
            if is_server_ready():
                break
            time.sleep(0.5)

    print(f"   Server aktif di {URL}")

    browser_exe = find_browser_app()
    if browser_exe:
        print(f"   Membuka antarmuka desktop via: {os.path.basename(browser_exe)}")
        cmd = [
            browser_exe,
            f"--app={URL}",
            "--window-size=1280,820",
            "--window-position=100,50",
            "--disable-extensions",
        ]
        try:
            proc = subprocess.Popen(cmd)
            proc.wait()
            sys.exit(0)
        except Exception as e:
            print(f"   Gagal membuka app mode: {e}, membuka default browser...")
            webbrowser.open(URL)
    else:
        print("   Membuka di browser default...")
        webbrowser.open(URL)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n   Aplikasi ditutup.")

if __name__ == "__main__":
    main()
