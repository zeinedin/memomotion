import time
import threading
import uvicorn
from playwright.sync_api import sync_playwright, expect
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

def verify_frontend():
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give the server a moment to start
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            record_video_dir="verification/videos"
        )
        page = context.new_page()

        try:
            # Navigate to the app
            page.goto("http://127.0.0.1:8001/")
            page.wait_for_timeout(1000)

            # --- Verify the initial ARIA attributes on index.html ---
            team_name_input = page.locator("#teamName")
            expect(team_name_input).to_have_attribute("aria-errormessage", "teamNameError")

            error_span = page.locator("#teamNameError")
            expect(error_span).to_have_attribute("role", "alert")

            back_btn = page.locator("#backToStartBtn")
            expect(back_btn).to_have_attribute("aria-label", "Back to Start")

            # --- Trigger the validation error ---
            start_btn = page.locator("#startGameBtn")
            start_btn.click()
            page.wait_for_timeout(500)

            # Verify error state is applied
            expect(team_name_input).to_have_attribute("aria-invalid", "true")
            # Playwright evaluates inline styles; check for the computed value or exact inline string if possible.
            # We'll assert the attribute is there and the error span is visible.
            expect(error_span).to_be_visible()
            expect(error_span).to_have_text("Enter a team name (min 2 chars)")

            # Wait 2.5 seconds to ensure the error does NOT disappear automatically
            page.wait_for_timeout(2500)

            # Verify error state STILL persists after the time that used to clear it
            expect(team_name_input).to_have_attribute("aria-invalid", "true")
            expect(error_span).to_be_visible()

            # Capture the state with the error showing
            page.screenshot(path="verification/screenshots/error_persists.png")
            page.wait_for_timeout(500)

            # --- Clear the error by typing ---
            team_name_input.fill("A") # Triggers 'input' event
            page.wait_for_timeout(500)

            # Verify error state is cleared
            # In Playwright, to assert an attribute is absent, we use expect(...).not_to_have_attribute(name, value)
            # Or assert it returns None from get_attribute
            assert team_name_input.get_attribute("aria-invalid") is None, "aria-invalid should be removed"
            expect(error_span).not_to_be_visible()

            # Capture the state after clearing the error
            page.screenshot(path="verification/screenshots/error_cleared.png")
            page.wait_for_timeout(1000)

            print("Verification successful!")

        finally:
            context.close()
            browser.close()

if __name__ == "__main__":
    verify_frontend()
