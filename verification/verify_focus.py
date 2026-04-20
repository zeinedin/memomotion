from playwright.sync_api import sync_playwright
import time
import subprocess
import os

def run_cuj(page):
    page.goto("http://127.0.0.1:8001/")
    page.wait_for_timeout(1000)

    # Press Tab multiple times to navigate through the interactive elements
    for _ in range(5):
        page.keyboard.press("Tab")
        page.wait_for_timeout(500)

    # Take a screenshot to capture focus state
    page.screenshot(path="/app/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    # Start the backend server on a specific port
    print("Starting backend server...")
    server = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd="/app"
    )
    time.sleep(2)  # Wait for server to initialize

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir="/app/verification/videos"
            )
            page = context.new_page()
            try:
                run_cuj(page)
            finally:
                context.close()
                browser.close()
    finally:
        # Clean up the server process
        server.terminate()
        server.wait()
        print("Server terminated.")
