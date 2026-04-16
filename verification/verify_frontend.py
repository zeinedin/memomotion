from playwright.sync_api import sync_playwright, expect
import threading
import uvicorn
import time
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Record video
        context = browser.new_context(record_video_dir="/app/verification/")
        page = context.new_page()

        try:
            print("Navigating to start screen...")
            page.goto("http://127.0.0.1:8001/")

            # 1. Assert initial state elements have explicit :focus-visible outlines
            # We can trigger focus via keyboard navigation (Tab)
            print("Testing focus on Mode Button...")
            mode_btn = page.locator(".mode-btn.active")
            mode_btn.focus()

            # Evaluate the style directly using Playwright
            # This is tricky because :focus-visible is pseudo-class. Playwright handles focus well but we might just need to capture screenshot of it
            page.screenshot(path="/app/verification/focus-mode-btn.png")

            print("Testing focus on Launch Button...")
            launch_btn = page.locator("#startGameBtn")
            launch_btn.focus()
            page.screenshot(path="/app/verification/focus-launch-btn.png")

            # Go to game screen to check icon button
            print("Starting game to check game screen...")
            page.fill("#teamName", "A11y Team")
            launch_btn.click()

            # Wait for game screen to be visible
            expect(page.locator("#gameScreen")).to_be_visible(timeout=5000)

            # 2. Check aria-label on icon button
            print("Testing aria-label on back button...")
            back_btn = page.locator("#backToStartBtn")
            expect(back_btn).to_have_attribute("aria-label", "Quit game")

            # Focus it
            back_btn.focus()
            page.screenshot(path="/app/verification/focus-back-btn.png")

            print("Verification successful!")

        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to start
    time.sleep(2)

    try:
        verify_frontend()
    except Exception as e:
        print(f"Verification failed: {e}")
        import sys
        sys.exit(1)
