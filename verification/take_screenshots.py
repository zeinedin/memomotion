from playwright.sync_api import sync_playwright
import time
import multiprocessing
import uvicorn
import os

def run_server():
    import main
    uvicorn.run(main.app, host="127.0.0.1", port=8002, log_level="warning")

def verify_frontend():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            print("Navigating to local server...")
            page.goto("http://127.0.0.1:8002")

            page.wait_for_selector("#startGameBtn")

            print("Triggering form validation error...")
            page.click("#startGameBtn")

            page.wait_for_selector("#teamNameError:visible")

            # Take screenshot of error state
            page.screenshot(path="verification/error_state.png")
            print("Captured error_state.png")

            # Type to clear error
            print("Typing to clear error...")
            page.type("#teamName", "A")

            # Take screenshot of cleared state
            page.screenshot(path="verification/cleared_state.png")
            print("Captured cleared_state.png")

        finally:
            browser.close()

if __name__ == "__main__":
    os.environ["PYTHONPATH"] = "."
    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    try:
        time.sleep(2)  # Wait for server
        verify_frontend()
    finally:
        server_process.terminate()
        server_process.join()
