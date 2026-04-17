import subprocess
import time
from playwright.sync_api import sync_playwright

def verify():
    # Start the backend server on port 8001 to avoid conflicts
    server_process = subprocess.Popen(["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"])
    time.sleep(2)  # Give server time to start

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(record_video_dir="/app/verification/videos")
            page = context.new_page()

            page.goto("http://127.0.0.1:8001/")

            # Click the start button with an empty team name to trigger the error
            page.click("#startGameBtn")

            # Verify the error message is displayed
            error_element = page.locator("#teamNameError")
            assert error_element.is_visible(), "Error message is not visible"
            assert error_element.text_content() == "Enter a team name (min 2 chars)", f"Unexpected error message: {error_element.text_content()}"

            # Verify role="alert" is present
            assert error_element.get_attribute("role") == "alert", "role='alert' is missing"

            # Verify aria-errormessage is present on the input
            input_element = page.locator("#teamName")
            assert input_element.get_attribute("aria-errormessage") == "teamNameError", "aria-errormessage is missing on input"

            # Verify aria-invalid is true
            assert input_element.get_attribute("aria-invalid") == "true", "aria-invalid is missing or false"

            # Wait for 2.5 seconds to ensure the error doesn't disappear (testing the removal of setTimeout)
            page.wait_for_timeout(2500)

            # Re-verify the error message is still visible and aria-invalid is still true
            assert error_element.is_visible(), "Error message disappeared after timeout"
            assert input_element.get_attribute("aria-invalid") == "true", "aria-invalid disappeared after timeout"

            # Take a screenshot of the error state
            page.screenshot(path="/app/verification/error_state.png")

            # Type something into the input field to trigger the 'input' event
            input_element.type("Test Crew")

            # Verify the error message is cleared
            assert not error_element.is_visible(), "Error message did not clear after typing"
            assert input_element.get_attribute("aria-invalid") is None, "aria-invalid is still present after typing"

            # Take a screenshot of the cleared state
            page.screenshot(path="/app/verification/cleared_state.png")

            print("Verification successful!")

            context.close()
            browser.close()
    finally:
        server_process.terminate()
        server_process.wait()

if __name__ == "__main__":
    verify()
