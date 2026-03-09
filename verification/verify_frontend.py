from playwright.sync_api import sync_playwright
import threading
import uvicorn
import time
import requests

def run_server():
    uvicorn.run("main:app", host="127.0.0.1", port=8002, log_level="warning")

def verify():
    # Start server
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Wait for server
    for _ in range(30):
        try:
            if requests.get("http://127.0.0.1:8002/").status_code == 200:
                break
        except:
            time.sleep(0.5)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:8002/")
        page.wait_for_selector("#startGameBtn")

        # Take initial screenshot
        page.screenshot(path="verification/before_click.png")

        # Check Classic Mode Button ARIA state
        classic_btn = page.locator(".mode-btn[data-mode='classic']")
        simon_btn = page.locator(".mode-btn[data-mode='simon']")

        print("Classic aria-pressed initially:", classic_btn.get_attribute("aria-pressed"))
        print("Simon aria-pressed initially:", simon_btn.get_attribute("aria-pressed"))

        # Click Simon Says
        simon_btn.click()
        page.wait_for_timeout(100) # Wait for UI update

        print("Classic aria-pressed after click:", classic_btn.get_attribute("aria-pressed"))
        print("Simon aria-pressed after click:", simon_btn.get_attribute("aria-pressed"))

        # Verify fieldset / legend presence
        fieldset_count = page.locator("fieldset.form-group").count()
        legend_count = page.locator("fieldset.form-group legend").count()
        print(f"Fieldsets found: {fieldset_count}")
        print(f"Legends found: {legend_count}")

        # Verify aria-label on close btn
        close_btn = page.locator("#backToStartBtn")
        print("Close button aria-label:", close_btn.get_attribute("aria-label"))

        # Take screenshot after click
        page.screenshot(path="verification/after_click.png")

        browser.close()

if __name__ == "__main__":
    verify()
