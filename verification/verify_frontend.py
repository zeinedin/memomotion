import threading
import time
import requests
import uvicorn
from playwright.sync_api import sync_playwright

from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")

def test_frontend():
    # Start server in daemon thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server to be ready
    for _ in range(30):
        try:
            response = requests.get("http://127.0.0.1:8001/")
            if response.status_code == 200:
                break
        except requests.ConnectionError:
            pass
        time.sleep(0.1)
    else:
        raise RuntimeError("Server failed to start")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001/")

        print("Testing form validation error persistence...")
        # Submit empty form to trigger error
        page.click("#startGameBtn")

        # Verify error is visible immediately
        page.wait_for_selector("#teamNameError", state="visible")
        error_display = page.evaluate("document.getElementById('teamNameError').style.display")
        assert error_display == "block", f"Expected error to be block, got {error_display}"

        aria_invalid = page.evaluate("document.getElementById('teamName').getAttribute('aria-invalid')")
        assert aria_invalid == "true", f"Expected aria-invalid to be true, got {aria_invalid}"

        border_color = page.evaluate("document.getElementById('teamName').style.borderColor")
        assert "var(--neon-red)" in border_color, f"Expected border color to be var(--neon-red), got {border_color}"

        print("Waiting 2.5 seconds to ensure error doesn't auto-hide...")
        time.sleep(2.5)

        # Verify error is still visible after the previous 2-second timeout would have hidden it
        error_display = page.evaluate("document.getElementById('teamNameError').style.display")
        assert error_display == "block", f"Expected error to still be block after 2.5s, got {error_display}"

        border_color = page.evaluate("document.getElementById('teamName').style.borderColor")
        assert "var(--neon-red)" in border_color, f"Expected border color to still be var(--neon-red) after 2.5s, got {border_color}"

        print("Testing clear errors on input...")
        # Type into the input to trigger 'input' event
        page.fill("#teamName", "A")

        # Give it a tiny bit of time to run the event listener
        time.sleep(0.1)

        # Verify error is hidden and styles/attributes are cleared
        error_display = page.evaluate("document.getElementById('teamNameError').style.display")
        assert error_display == "none", f"Expected error to be hidden after input, got {error_display}"

        aria_invalid = page.evaluate("document.getElementById('teamName').getAttribute('aria-invalid')")
        assert aria_invalid is None, f"Expected aria-invalid to be removed after input, got {aria_invalid}"

        border_color = page.evaluate("document.getElementById('teamName').style.borderColor")
        assert border_color == "", f"Expected border color to be cleared after input, got '{border_color}'"

        print("Testing icon-only button accessibility...")
        aria_label = page.evaluate("document.getElementById('backToStartBtn').getAttribute('aria-label')")
        assert aria_label == "Back to start", f"Expected backToStartBtn aria-label to be 'Back to start', got {aria_label}"

        page.screenshot(path="verification/screenshot.png")
        print("All tests passed successfully!")
        browser.close()

if __name__ == "__main__":
    test_frontend()