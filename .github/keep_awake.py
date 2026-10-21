"""Open the bot in a real browser so Streamlit Cloud does not put it to sleep.
If it is already asleep, click the button that wakes it up.

Run by GitHub Actions (.github/workflows/keep-awake.yml) every 6 hours.
"""
from playwright.sync_api import sync_playwright

URL = "https://phoenix-bot.streamlit.app/"
WAKE_BUTTON = "Yes, get this app back up!"

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto(URL, timeout=60_000)
    page.wait_for_timeout(10_000)          # give the page time to show the app or the sleep screen

    button = page.get_by_role("button", name=WAKE_BUTTON)
    if button.count():
        print("The app was asleep, waking it up")
        button.click()
        page.wait_for_timeout(90_000)      # let the app start before closing the browser
    else:
        print("The app is awake")
    browser.close()
