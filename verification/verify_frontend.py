import threading
import time
from playwright.sync_api import sync_playwright
import uvicorn
from main import app

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="critical")

def test_frontend():
    # Start server in background
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()

    # Give server time to start
    time.sleep(2)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto("http://127.0.0.1:8001")

        # 1. Check Fieldsets
        print("Checking fieldsets...")
        fieldsets = page.locator("fieldset.form-group")
        assert fieldsets.count() == 2, f"Expected 2 fieldsets, found {fieldsets.count()}"

        # 2. Check aria-pressed states on mode buttons
        print("Checking aria-pressed on mode buttons...")
        classic_btn = page.locator('button.mode-btn[data-mode="classic"]')
        simon_btn = page.locator('button.mode-btn[data-mode="simon"]')

        assert classic_btn.get_attribute("aria-pressed") == "true", "Classic should be pressed initially"
        assert simon_btn.get_attribute("aria-pressed") == "false", "Simon should not be pressed initially"

        # Click simon and check states
        simon_btn.click()
        time.sleep(0.5)
        assert classic_btn.get_attribute("aria-pressed") == "false", "Classic should not be pressed after clicking simon"
        assert simon_btn.get_attribute("aria-pressed") == "true", "Simon should be pressed after clicking simon"

        # 3. Check aria-pressed states on level buttons
        print("Checking aria-pressed on level buttons...")
        easy_btn = page.locator('button.level-btn[data-level="easy"]')
        medium_btn = page.locator('button.level-btn[data-level="medium"]')

        assert easy_btn.get_attribute("aria-pressed") == "true", "Easy should be pressed initially"
        assert medium_btn.get_attribute("aria-pressed") == "false", "Medium should not be pressed initially"

        # Click medium and check states
        medium_btn.click()
        time.sleep(0.5)
        assert easy_btn.get_attribute("aria-pressed") == "false", "Easy should not be pressed after clicking medium"
        assert medium_btn.get_attribute("aria-pressed") == "true", "Medium should be pressed after clicking medium"

        # 4. Check Form Validation and aria-invalid
        print("Checking form validation...")
        start_btn = page.locator("#startGameBtn")
        team_input = page.locator("#teamName")
        team_error = page.locator("#teamNameError")

        # Click start without entering name
        start_btn.click()
        time.sleep(0.5)

        # Should have error
        assert team_error.is_visible(), "Error message should be visible"
        assert team_error.get_attribute("role") == "alert", "Error message should have role=alert"
        assert team_input.get_attribute("aria-invalid") == "true", "Input should have aria-invalid=true"

        # Type to clear error
        team_input.fill("Team 1")
        time.sleep(0.5)

        assert not team_error.is_visible(), "Error message should be hidden after typing"
        assert team_input.get_attribute("aria-invalid") is None, "Input should not have aria-invalid after typing"

        print("All frontend tests passed!")
        browser.close()

if __name__ == "__main__":
    test_frontend()
