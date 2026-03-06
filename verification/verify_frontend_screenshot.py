import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="warning")

def verify_frontend():
    # Start the server in a daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for the server to spin up
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002")

        # Ensure we are on the start screen
        page.wait_for_selector("#startScreen.active")

        # Leave team name empty and click Start to trigger error
        page.click("#startGameBtn")

        # Verify error message is visible
        page.wait_for_selector("#teamNameError", state="visible")

        # Wait a moment to ensure UI updates
        time.sleep(0.5)

        # Take a screenshot showing the error state and red border
        page.screenshot(path="verification/error_state.png")

        # Now start typing
        page.locator("#teamName").type("a")

        # Wait a moment for UI to update (error hidden, border cleared)
        time.sleep(0.5)

        # Take another screenshot showing the error cleared
        page.screenshot(path="verification/cleared_state.png")

        browser.close()

if __name__ == "__main__":
    verify_frontend()