import threading
import uvicorn
import time
from playwright.sync_api import sync_playwright, expect
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

if __name__ == "__main__":
    # Start the server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give the server a moment to start
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(record_video_dir="verification/video")
        page = context.new_page()

        try:
            print("Navigating to http://127.0.0.1:8001/")
            page.goto("http://127.0.0.1:8001/")
            page.wait_for_timeout(500)

            # Locate the input and the submit button
            team_input = page.locator("#teamName")
            submit_btn = page.locator("#startGameBtn")
            error_span = page.locator("#teamNameError")

            print("Testing validation error state...")
            # Click submit with empty input
            submit_btn.click()
            page.wait_for_timeout(500)

            # Verify the error message is displayed and accessibility attributes are set
            expect(error_span).to_be_visible()
            expect(error_span).to_have_text("Enter a team name (min 2 chars)")
            expect(error_span).to_have_attribute("role", "alert")

            # Verify the input has aria-invalid set
            expect(team_input).to_have_attribute("aria-invalid", "true")

            # The inline style should be applied
            border_color = team_input.evaluate("el => el.style.borderColor")
            assert "var(--neon-red)" in border_color or border_color != ""

            # Take a screenshot of the error state
            page.screenshot(path="verification/error_state.png")
            page.wait_for_timeout(1000)

            print("Testing error clearing on input...")
            # Type into the input
            team_input.fill("Te")
            page.wait_for_timeout(500)

            # Verify the error is cleared
            expect(error_span).not_to_be_visible()

            # Verify the aria-invalid attribute is removed
            assert team_input.get_attribute("aria-invalid") is None

            # Verify the inline style is cleared
            border_color_after = team_input.evaluate("el => el.style.borderColor")
            assert border_color_after == ""

            # Take a screenshot of the cleared state
            page.screenshot(path="verification/cleared_state.png")
            page.wait_for_timeout(1000)

            print("Frontend verification completed successfully!")

        except Exception as e:
            print(f"Verification failed: {e}")
            raise
        finally:
            context.close()
            browser.close()