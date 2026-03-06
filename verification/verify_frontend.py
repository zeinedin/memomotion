import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="warning")

def verify_frontend():
    # Start the server in a daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for the server to spin up
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001")

        # Ensure we are on the start screen
        page.wait_for_selector("#startScreen.active")

        # Leave team name empty and click Start to trigger error
        page.click("#startGameBtn")

        # Verify error message is visible
        page.wait_for_selector("#teamNameError", state="visible")
        error_msg = page.locator("#teamNameError")
        print("Error message text:", error_msg.inner_text())

        # Verify aria-invalid is set to "true"
        team_name_input = page.locator("#teamName")
        aria_invalid = team_name_input.get_attribute("aria-invalid")
        print("aria-invalid before typing:", aria_invalid)
        assert aria_invalid == "true", f"Expected aria-invalid to be 'true', got {aria_invalid}"

        # Wait a bit over 2 seconds to ensure the old timeout (2000ms) would have expired
        print("Waiting 2.5 seconds to verify error persists...")
        time.sleep(2.5)

        # Verify error message is still visible
        assert error_msg.is_visible(), "Error message disappeared after timeout, but it should persist!"
        aria_invalid = team_name_input.get_attribute("aria-invalid")
        assert aria_invalid == "true", f"Expected aria-invalid to still be 'true', got {aria_invalid}"
        print("Error properly persisted.")

        # Now start typing
        print("Typing in the input field...")
        team_name_input.type("a")

        # Verify error message is now hidden
        assert not error_msg.is_visible(), "Error message should be hidden after input!"

        # Verify aria-invalid is removed
        aria_invalid_after = team_name_input.get_attribute("aria-invalid")
        print("aria-invalid after typing:", aria_invalid_after)
        assert aria_invalid_after is None, f"Expected aria-invalid to be None, got {aria_invalid_after}"
        print("Error properly cleared on input.")

        browser.close()

if __name__ == "__main__":
    verify_frontend()