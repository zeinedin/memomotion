import time
import threading
import uvicorn
from playwright.sync_api import sync_playwright

from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

def verify():
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)  # Wait for server to start

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Record video as instructed in memory
        context = browser.new_context(record_video_dir="verification/")
        page = context.new_page()

        page.goto("http://127.0.0.1:8001/")

        # Click Start without filling name
        page.locator("#startGameBtn").click()
        time.sleep(0.5)

        # Screenshot of error state
        page.screenshot(path="verification/error_state.png")

        # Now input a name
        page.locator("#teamName").fill("Apollo")
        time.sleep(0.5)

        # Screenshot of cleared state
        page.screenshot(path="verification/cleared_state.png")

        context.close()
        browser.close()
        print("Verification completed successfully.")

if __name__ == "__main__":
    verify()
