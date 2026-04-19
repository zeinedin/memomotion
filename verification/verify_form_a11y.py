from playwright.sync_api import sync_playwright

def run_cuj(page):
    page.goto("http://localhost:8000")
    page.wait_for_timeout(1000)

    # Click start without entering a name to trigger the error
    page.get_by_role("button", name="🚀 LAUNCH MISSION").click()
    page.wait_for_timeout(500)

    # Verify error styling and accessibility attributes
    page.screenshot(path="/app/verification/screenshots/verification_error_state.png")
    page.wait_for_timeout(500)

    # Type something to clear the error
    page.locator("#teamName").fill("Test")
    page.wait_for_timeout(500)

    page.screenshot(path="/app/verification/screenshots/verification_cleared_state.png")
    page.wait_for_timeout(1000)

if __name__ == "__main__":
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
