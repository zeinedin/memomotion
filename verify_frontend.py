from playwright.sync_api import sync_playwright
import time
import subprocess
import os
import signal

def run_cuj(page):
    print("Navigating to app...")
    page.goto("http://localhost:8001")
    page.wait_for_timeout(1000)

    print("Triggering validation error...")
    page.get_by_role("button", name="LAUNCH MISSION").click()
    page.wait_for_timeout(1000)

    print("Verifying error state...")
    # Error should be visible
    page.get_by_role("alert").wait_for(state="visible")
    # Input should have aria-invalid
    assert page.locator("#teamName").get_attribute("aria-invalid") == "true"

    print("Typing to clear error...")
    page.locator("#teamName").fill("Crew")
    page.wait_for_timeout(1000)

    print("Verifying cleared state...")
    # Input should not have aria-invalid
    assert page.locator("#teamName").get_attribute("aria-invalid") is None

    print("Taking screenshot...")
    page.screenshot(path="/app/verification/screenshots/verification.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
    print("Starting local server...")
    server_process = subprocess.Popen(
        ["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8001"],
        cwd="/app",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2) # Wait for server to start

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                record_video_dir="/app/verification/videos"
            )
            page = context.new_page()
            try:
                run_cuj(page)
            finally:
                context.close()
                browser.close()
    finally:
        print("Stopping local server...")
        server_process.terminate()
        server_process.wait()
