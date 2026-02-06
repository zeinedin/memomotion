from playwright.sync_api import sync_playwright, expect

def verify_accessibility():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://localhost:8000/")

        # Wait for the page to load
        page.wait_for_selector(".hero")

        print("Verifying Mode Selector...")
        # Verify Mode Selector container
        mode_selector = page.locator(".mode-selector")
        expect(mode_selector).to_have_attribute("role", "radiogroup")
        expect(mode_selector).to_have_attribute("aria-label", "Mission Type")

        # Verify Classic Mode button (default selected)
        classic_btn = page.locator('.mode-btn[data-mode="classic"]')
        expect(classic_btn).to_have_attribute("role", "radio")
        expect(classic_btn).to_have_attribute("aria-checked", "true")

        # Verify Simon Says button (not selected)
        simon_btn = page.locator('.mode-btn[data-mode="simon"]')
        expect(simon_btn).to_have_attribute("role", "radio")
        expect(simon_btn).to_have_attribute("aria-checked", "false")

        # Click Simon Says and verify update
        print("Clicking Simon Says...")
        simon_btn.click()
        expect(simon_btn).to_have_attribute("aria-checked", "true")
        expect(classic_btn).to_have_attribute("aria-checked", "false")

        print("Verifying Level Selector...")
        # Verify Level Selector container
        level_selector = page.locator(".level-selector")
        expect(level_selector).to_have_attribute("role", "radiogroup")
        expect(level_selector).to_have_attribute("aria-label", "Difficulty")

        # Verify Easy Level button (default selected)
        easy_btn = page.locator('.level-btn[data-level="easy"]')
        expect(easy_btn).to_have_attribute("role", "radio")
        expect(easy_btn).to_have_attribute("aria-checked", "true")

        # Click Medium and verify update
        print("Clicking Medium...")
        medium_btn = page.locator('.level-btn[data-level="medium"]')
        medium_btn.click()
        expect(medium_btn).to_have_attribute("aria-checked", "true")
        expect(easy_btn).to_have_attribute("aria-checked", "false")

        print("Verifying Back to Start Button...")
        # Go to game screen to see the back button (simulated or just check DOM if hidden)
        # It's in the DOM but hidden? No, it's on game screen.
        # But wait, the button exists in the DOM anyway.
        back_btn = page.locator("#backToStartBtn")
        expect(back_btn).to_have_attribute("aria-label", "Close")

        print("Verifying Message Text...")
        message_text = page.locator("#messageText")
        expect(message_text).to_have_attribute("aria-live", "polite")

        # Take screenshot
        page.screenshot(path="verification.png")
        print("Verification complete! Screenshot saved to verification.png")

        browser.close()

if __name__ == "__main__":
    verify_accessibility()
