import asyncio
import time
from playwright.sync_api import sync_playwright
import uvicorn
import threading
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="critical")

def test_frontend_validation(page):
    page.goto("http://127.0.0.1:8001")

    # Trigger form validation error (empty name)
    page.fill("#teamName", "")
    page.click("#startGameBtn")

    # Wait for the error to appear
    page.wait_for_selector("#teamNameError", state="visible")

    # Take a screenshot showing the error state
    page.screenshot(path="verification/error_state.png")

def main():
    # Start server in background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)  # Wait for server to start

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            test_frontend_validation(page)
        finally:
            browser.close()

if __name__ == "__main__":
    main()