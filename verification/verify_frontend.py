import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="critical")

def test_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001/")

        # Verify #teamNameError has role="alert"
        error_span = page.locator("#teamNameError")
        assert error_span.get_attribute("role") == "alert", "role='alert' is missing on error span"

        # Check aria-label on the back to start button
        back_btn = page.locator("#backToStartBtn")
        assert back_btn.get_attribute("aria-label") == "Quit game and return to start", "aria-label is missing on back to start button"

        # Click Start Mission with an empty input to trigger error
        page.locator("#startGameBtn").click()

        # The input should have an error (red border and aria-invalid=true)
        team_input = page.locator("#teamName")

        # We need to wait a small bit for JS to apply the error if it's asynchronous, but it's synchronous here.
        assert team_input.get_attribute("aria-invalid") == "true", "aria-invalid='true' not set on input after error"
        border_color = team_input.evaluate("el => el.style.borderColor")
        assert "var(--neon-red)" in border_color, f"border-color is wrong: {border_color}"

        # Verify the error message is visible
        assert error_span.is_visible()

        # Start typing into the input to clear the error
        # .type() emits keydown, keypress, input, and keyup events
        team_input.type("A", delay=50)

        # The error should be cleared: border-color removed, aria-invalid='false', and error message hidden
        assert team_input.get_attribute("aria-invalid") == "false", "aria-invalid not 'false' after input"

        border_color = team_input.evaluate("el => el.style.borderColor")
        assert border_color == "", "border-color not cleared after input"

        assert not error_span.is_visible(), "error message should be hidden after input"

        browser.close()
        print("Frontend verification passed successfully!")

if __name__ == "__main__":
    # Start server in a background thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give the server a moment to start up
    time.sleep(1)

    # Run Playwright verification
    test_frontend()
