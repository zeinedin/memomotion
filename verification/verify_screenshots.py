import time
from playwright.sync_api import sync_playwright
import threading
import uvicorn
from main import app
import sys

# Start FastAPI server in background
def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)  # Give server time to start

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002/")

        print("Testing form validation UX...")

        # Click start without entering team name
        start_btn = page.locator("#startGameBtn")
        start_btn.click()

        # Wait for error to appear
        page.wait_for_selector("#teamNameError", state="visible")

        # Take screenshot of error state
        page.screenshot(path="verification/error_state.png")
        print("✓ Screenshot taken for error state: verification/error_state.png")

        # Start typing to clear error
        input_field = page.locator("#teamName")
        input_field.fill("Te")

        # Take screenshot of cleared state
        page.screenshot(path="verification/cleared_state.png")
        print("✓ Screenshot taken for cleared state: verification/cleared_state.png")

        browser.close()

if __name__ == "__main__":
    try:
        verify()
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
