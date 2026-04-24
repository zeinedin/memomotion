from playwright.sync_api import sync_playwright, expect
import subprocess
import time
import os

def run_test():
    # Start the server
    process = subprocess.Popen(["python", "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8002"])
    time.sleep(2)  # Wait for server to start

    try:
        with sync_playwright() as p:
            # We record a video as instructed in memory
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(record_video_dir="/app/verification/videos")
            page = context.new_page()

            page.goto("http://127.0.0.1:8002/")

            # Get the team name input and start button
            team_input = page.locator("#teamName")
            start_btn = page.locator("#startGameBtn")

            # 1. Verify aria-errormessage is set
            expect(team_input).to_have_attribute("aria-errormessage", "teamNameError")

            # 2. Trigger error by submitting an empty/short name
            team_input.fill("")
            start_btn.click()

            # Error should be visible and input should be marked invalid
            error_span = page.locator("#teamNameError")
            expect(error_span).to_be_visible()
            expect(error_span).to_have_attribute("role", "alert")
            expect(team_input).to_have_attribute("aria-invalid", "true")
            # style should have red border
            assert "border-color: var(--neon-red);" in team_input.get_attribute("style")

            # Wait 2.5 seconds to prove it doesn't clear on a timeout
            time.sleep(2.5)
            expect(error_span).to_be_visible()
            expect(team_input).to_have_attribute("aria-invalid", "true")

            # 3. Type into the input to trigger the 'input' event listener
            team_input.fill("A")

            # The error should now be cleared
            expect(error_span).to_be_hidden()
            assert team_input.get_attribute("aria-invalid") is None
            # Check style cleared
            style = team_input.get_attribute("style")
            assert style is None or "border-color: var(--neon-red);" not in style

            # Take a screenshot to show the final state
            page.screenshot(path="/app/verification/verification.png")

            context.close()
            browser.close()
            print("Verification successful!")

    except Exception as e:
        print(f"Test failed: {e}")
        raise e
    finally:
        process.terminate()
        process.wait()

if __name__ == "__main__":
    run_test()
