import os
import subprocess
import time
from playwright.sync_api import sync_playwright, expect

def main():
    # Start the backend server
    print("Starting backend server...")
    server_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd="/app"
    )

    # Give the server time to start
    time.sleep(3)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(record_video_dir="/app/verification/videos/")
            page = context.new_page()

            print("Navigating to app...")
            page.goto("http://127.0.0.1:8002/")

            # Find elements
            team_input = page.locator("#teamName")
            error_msg = page.locator("#teamNameError")
            start_btn = page.locator("#startGameBtn")

            print("Testing initial state...")
            expect(team_input).to_have_attribute("aria-invalid", "false")
            expect(team_input).to_have_attribute("aria-errormessage", "teamNameError")
            expect(error_msg).to_have_attribute("role", "alert")
            expect(error_msg).not_to_be_visible()

            print("Triggering error state...")
            start_btn.click()

            print("Testing error state...")
            expect(error_msg).to_be_visible()
            expect(team_input).to_have_attribute("aria-invalid", "true")
            # In playwright, evaluating a style returns rgb
            # However, since we just need to ensure the style exists and clears, we can check truthiness or wait for attribute
            # We'll take a screenshot of the error state first
            page.screenshot(path="/app/verification/error_state.png")

            print("Testing error clearing on input...")
            # Type something to trigger the 'input' event
            team_input.type("A")

            # The input event listener should clear the error state immediately
            expect(error_msg).not_to_be_visible()
            expect(team_input).to_have_attribute("aria-invalid", "false")

            # Ensure the border is reset (style string is empty)
            border_style = team_input.evaluate("el => el.style.borderColor")
            assert border_style == "", f"Expected empty borderColor, got '{border_style}'"

            # Take a final screenshot
            page.screenshot(path="/app/verification/final_state.png")
            print("Verification successful!")

            context.close()
            browser.close()
    finally:
        # Clean up the server process
        server_process.terminate()
        server_process.wait()
        print("Backend server stopped.")

if __name__ == "__main__":
    main()
