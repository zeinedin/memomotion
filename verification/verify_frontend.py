import time
import threading
import uvicorn
from playwright.sync_api import sync_playwright, expect
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

def verify():
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give the server a moment to start
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(record_video_dir="verification/videos/")
        page = context.new_page()

        page.goto("http://127.0.0.1:8002/")

        # Test 1: Empty submission shows error and adds aria-invalid
        page.click("button#startGameBtn")

        # Verify error message
        expect(page.locator("#teamNameError")).to_have_text("Enter a team name (min 2 chars)")
        expect(page.locator("#teamNameError")).to_be_visible()

        # Verify aria-errormessage and role="alert" are set correctly in DOM
        expect(page.locator("#teamNameError")).to_have_attribute("role", "alert")
        expect(page.locator("#teamName")).to_have_attribute("aria-errormessage", "teamNameError")

        # Verify aria-invalid is set
        expect(page.locator("#teamName")).to_have_attribute("aria-invalid", "true")

        # Test 2: Typing clears the error and aria-invalid
        page.fill("#teamName", "A")

        # The error text is cleared and display is none
        expect(page.locator("#teamNameError")).to_be_hidden()
        assert page.locator("#teamNameError").text_content() == ""

        # The aria-invalid attribute is removed
        assert page.locator("#teamName").get_attribute("aria-invalid") is None

        page.screenshot(path="verification/screenshot.png")

        context.close()
        browser.close()

if __name__ == "__main__":
    verify()
