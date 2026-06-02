from playwright.sync_api import sync_playwright, expect

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the application
        page.goto("http://127.0.0.1:8001/")

        # Wait for the main menu to load
        expect(page.locator("#startGameBtn")).to_be_visible()

        # Fill team name and click start to go to game screen
        page.locator("#teamName").press_sequentially("Crew 1")
        page.locator("#startGameBtn").click()

        # Wait for the game screen and back button to be visible
        close_btn = page.locator("#backToStartBtn")
        expect(close_btn).to_be_visible()

        # Hover over the button to show the title tooltip
        close_btn.hover()

        # Take a screenshot
        page.screenshot(path="/app/verification/screenshot.png")

        browser.close()

if __name__ == "__main__":
    run()
