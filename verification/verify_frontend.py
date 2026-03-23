import threading
import uvicorn
import time
from playwright.sync_api import sync_playwright, expect
import main
import os

def run_server():
    uvicorn.run(main.app, host="127.0.0.1", port=8001, log_level="error")

def verify():
    # Start server in background
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(2)  # Wait for server to start

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(record_video_dir="verification/videos/")
        page = context.new_page()

        print("Navigating to start page...")
        page.goto("http://localhost:8001/")

        team_name_input = page.locator("#teamName")
        team_name_error = page.locator("#teamNameError")
        start_btn = page.locator("#startGameBtn")
        back_btn = page.locator("#backToStartBtn")

        # Verify initial state
        print("Checking initial ARIA properties...")
        expect(team_name_input).to_have_attribute("aria-errormessage", "teamNameError")
        expect(team_name_input).to_have_attribute("aria-invalid", "false")
        expect(team_name_error).to_have_attribute("role", "alert")
        expect(back_btn).to_have_attribute("aria-label", "Close")

        # Trigger error
        print("Triggering form error...")
        start_btn.click()

        # Verify error state
        print("Verifying error state...")
        expect(team_name_input).to_have_attribute("aria-invalid", "true")
        assert team_name_input.evaluate("el => el.style.borderColor") == "var(--neon-red)"
        expect(team_name_error).to_be_visible()
        expect(team_name_error).to_contain_text("Enter a team name")

        # Wait past previous 2s timeout
        print("Waiting 3s to ensure error persists...")
        time.sleep(3)
        expect(team_name_input).to_have_attribute("aria-invalid", "true")
        assert team_name_input.evaluate("el => el.style.borderColor") == "var(--neon-red)"
        expect(team_name_error).to_be_visible()

        # Type to clear error
        print("Typing to clear error...")
        # Use JS to trigger input event
        team_name_input.evaluate("el => { el.value = 'a'; el.dispatchEvent(new Event('input')); }")

        # Verify error cleared
        print("Verifying error cleared...")
        expect(team_name_input).to_have_attribute("aria-invalid", "false")
        assert team_name_input.evaluate("el => el.style.borderColor") == ""
        expect(team_name_error).not_to_be_visible()

        page.screenshot(path="verification/success.png")
        print("Verification completed successfully!")

        context.close()
        browser.close()

if __name__ == "__main__":
    verify()
