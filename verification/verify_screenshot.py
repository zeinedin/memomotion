import threading
import time
from playwright.sync_api import sync_playwright, expect
import uvicorn
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="critical")

def test_frontend_screenshot():
    # Start server in background
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002")

        # Click start without entering name to trigger validation error
        start_btn = page.locator("#startGameBtn")
        start_btn.click()

        # Wait for the error to appear
        team_error = page.locator("#teamNameError")
        expect(team_error).to_be_visible()

        # Take a screenshot
        page.screenshot(path="/home/jules/verification/validation_error.png")

        print("Screenshot saved to /home/jules/verification/validation_error.png")
        browser.close()

if __name__ == "__main__":
    test_frontend_screenshot()
