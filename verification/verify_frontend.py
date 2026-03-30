import threading
import uvicorn
import time
from playwright.sync_api import sync_playwright, expect
import main
import os

# Start backend server
def run_server():
    uvicorn.run(main.app, host="127.0.0.1", port=8001, log_level="warning")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(2)

def verify():
    with sync_playwright() as p:
        # We need a browser context to record video
        browser = p.chromium.launch()
        context = browser.new_context(record_video_dir="verification/videos/")
        page = context.new_page()

        page.goto("http://localhost:8001/")

        team_name_input = page.locator("#teamName")
        start_btn = page.locator("#startGameBtn")
        error_msg = page.locator("#teamNameError")

        # Check initial state
        assert team_name_input.get_attribute("aria-errormessage") == "teamNameError"
        assert team_name_input.get_attribute("aria-invalid") == "false"
        assert error_msg.get_attribute("role") == "alert"

        # Submit empty to trigger error
        start_btn.click()

        # Wait for error to appear
        expect(error_msg).to_be_visible()
        assert error_msg.text_content() == "Enter a team name (min 2 chars)"
        assert team_name_input.get_attribute("aria-invalid") == "true"

        # Verify the border color is set
        expect(team_name_input).to_have_css("border-color", "rgb(255, 0, 68)")

        # Wait more than 2 seconds to ensure it persists
        page.wait_for_timeout(2500)

        # Still visible and red?
        expect(error_msg).to_be_visible()
        expect(team_name_input).to_have_css("border-color", "rgb(255, 0, 68)")
        assert team_name_input.get_attribute("aria-invalid") == "true"

        # Type to clear error
        team_name_input.type("a")

        # Verify error is cleared
        expect(error_msg).not_to_be_visible()
        assert team_name_input.get_attribute("aria-invalid") == "false"

        page.screenshot(path="verification/screenshot.png")

        context.close()
        browser.close()

if __name__ == "__main__":
    verify()
