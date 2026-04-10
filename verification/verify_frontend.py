import sys
import subprocess
import time
from playwright.sync_api import sync_playwright

def main():
    print("Starting FastAPI server...")
    server = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8008"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Wait for server to be ready
    time.sleep(3)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(record_video_dir="verification/videos")
            page = context.new_page()

            # Navigate to local server
            page.goto("http://127.0.0.1:8008/")

            print("Focusing button to capture focus-visible state...")
            page.evaluate("document.getElementById('backToStartBtn').focus()")
            time.sleep(0.5)
            page.screenshot(path="verification/focus_state.png")

            print("Triggering form error...")
            start_btn = page.locator("#startGameBtn")
            start_btn.click()
            time.sleep(0.5)

            # Capture error state
            page.screenshot(path="verification/error_state.png")

            # Close browser
            context.close()
            browser.close()

            print("\nCaptured verification screenshots!")

    except Exception as e:
        print(f"Failed: {e}")
        sys.exit(1)
    finally:
        print("Terminating server...")
        server.terminate()
        server.wait()

if __name__ == "__main__":
    main()
