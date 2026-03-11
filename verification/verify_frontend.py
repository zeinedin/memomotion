import time
from playwright.sync_api import sync_playwright
import threading
import uvicorn
from main import app
import sys

# Start FastAPI server in background
def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()
time.sleep(2)  # Give server time to start

def verify():
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002/")

        print("Testing form validation UX...")

        # Click start without entering team name
        start_btn = page.locator("#startGameBtn")
        start_btn.click()

        # Verify error state
        input_field = page.locator("#teamName")
        assert input_field.get_attribute("aria-invalid") == "true", "Expected aria-invalid='true' after error"
        print("✓ Error state correctly sets aria-invalid='true'")

        # Verify error clears on input
        input_field.fill("Te")
        assert input_field.get_attribute("aria-invalid") is None, "Expected aria-invalid to be removed after input"
        print("✓ Error state cleared on input")

        print("Testing ARIA label on backToStartBtn...")
        # Start game properly
        input_field.fill("Team Bob")
        start_btn.click()
        time.sleep(1) # wait for animation

        # check backToStartBtn
        back_btn = page.locator("#backToStartBtn")
        assert back_btn.get_attribute("aria-label") == "Close game and return to start", "Expected backToStartBtn to have correct aria-label"
        print("✓ backToStartBtn has correct aria-label")

        # Admin page delete button
        print("Testing ARIA label on delete button in admin page...")
        page.goto("http://127.0.0.1:8002/admin.html")
        time.sleep(1) # wait for load
        delete_btn = page.locator(".delete-btn").first
        if delete_btn.count() > 0:
            aria_label = delete_btn.get_attribute("aria-label")
            assert aria_label and aria_label.startswith("Delete score for "), "Expected delete button to have correct aria-label"
            print("✓ deleteBtn has correct aria-label")
        else:
            print("⚠ No entries found to test delete button aria-label")

        browser.close()

if __name__ == "__main__":
    try:
        verify()
        print("All frontend verification tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
