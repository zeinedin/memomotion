import asyncio
import time
import threading
from playwright.sync_api import sync_playwright, expect
import uvicorn

# Start the server in a background thread
def run_server():
    from main import app
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()

# Wait for server to start
time.sleep(3)

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(record_video_dir="verification")
        page = context.new_page()

        page.goto("http://localhost:8001/")

        # Click start without entering team name
        start_btn = page.locator("#startGameBtn")
        start_btn.click()

        # Verify error displays and has correct accessibility attributes
        team_name_error = page.locator("#teamNameError")
        expect(team_name_error).to_be_visible()
        expect(team_name_error).to_have_text("Enter a team name (min 2 chars)")
        expect(team_name_error).to_have_attribute("role", "alert")

        team_name_input = page.locator("#teamName")
        expect(team_name_input).to_have_attribute("aria-errormessage", "teamNameError")
        expect(team_name_input).to_have_attribute("aria-invalid", "true")

        # Verify persistence (wait 3 seconds, should still be there)
        page.wait_for_timeout(3000)
        expect(team_name_error).to_be_visible()
        expect(team_name_input).to_have_attribute("aria-invalid", "true")

        # Type into input
        team_name_input.fill("Te")

        # Verify error disappears and invalid attribute is removed
        expect(team_name_error).not_to_be_visible()
        assert team_name_input.get_attribute("aria-invalid") is None

        # Take screenshot of focus state on start button
        page.keyboard.press("Tab") # tab to mode selector
        page.keyboard.press("Tab") # tab to mode simon
        page.keyboard.press("Tab") # endless
        page.keyboard.press("Tab") # speedrun
        page.keyboard.press("Tab") # level medium
        page.keyboard.press("Tab") # level hard
        page.keyboard.press("Tab") # Start button

        page.screenshot(path="verification/screenshot.png")

        context.close()
        browser.close()

if __name__ == "__main__":
    verify()
