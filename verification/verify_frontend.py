import asyncio
import os
import sys
from playwright.async_api import async_playwright
import uvicorn
import multiprocessing
import time

def run_server():
    import main
    uvicorn.run(main.app, host="127.0.0.1", port=8001, log_level="warning")

async def test_frontend():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            print("Connecting to local server...")
            await page.goto("http://127.0.0.1:8001")

            # Wait for the start screen
            await page.wait_for_selector("#startGameBtn")

            # Try to start without team name to trigger error
            print("Triggering form validation error...")
            await page.click("#startGameBtn")

            # Verify error state
            await page.wait_for_selector("#teamNameError:visible")

            # Check aria-invalid
            is_invalid = await page.get_attribute("#teamName", "aria-invalid")
            assert is_invalid == "true", f"Expected aria-invalid='true', got '{is_invalid}'"
            print("✓ aria-invalid is true on error")

            # Ensure the border color is red
            # In playwright, evaluate to get inline style
            border_color = await page.evaluate('document.getElementById("teamName").style.borderColor')
            assert border_color == "var(--neon-red)", f"Expected border-color 'var(--neon-red)', got '{border_color}'"
            print("✓ border color is red on error")

            # Wait a few seconds to ensure the error doesn't disappear (old timeout behavior)
            print("Waiting to ensure error persists...")
            await asyncio.sleep(2.5)

            # Check again
            is_invalid = await page.get_attribute("#teamName", "aria-invalid")
            assert is_invalid == "true", "aria-invalid should still be true after 2.5s"
            border_color = await page.evaluate('document.getElementById("teamName").style.borderColor')
            assert border_color == "var(--neon-red)", "border-color should still be red after 2.5s"
            print("✓ error state persists")

            # Now type in the input box to clear the error
            print("Typing to clear error...")
            await page.type("#teamName", "A")

            # Verify error state is cleared
            is_invalid = await page.get_attribute("#teamName", "aria-invalid")
            assert is_invalid == "false", f"Expected aria-invalid='false', got '{is_invalid}'"
            print("✓ aria-invalid is false after typing")

            border_color = await page.evaluate('document.getElementById("teamName").style.borderColor')
            assert border_color == "", f"Expected empty border-color, got '{border_color}'"
            print("✓ border color is cleared after typing")

            error_display = await page.evaluate('document.getElementById("teamNameError").style.display')
            assert error_display == "none", f"Expected display 'none', got '{error_display}'"
            print("✓ error message hidden after typing")

            print("All frontend verification checks passed!")

        finally:
            await browser.close()

if __name__ == "__main__":
    # Start the background server
    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    try:
        # Give server a moment to start
        time.sleep(2)
        asyncio.run(test_frontend())
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
    finally:
        server_process.terminate()
        server_process.join()
