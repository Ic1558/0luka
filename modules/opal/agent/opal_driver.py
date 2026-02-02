import sys
import os
import yaml
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

def run_opal_task(task_file):
    with open(task_file, 'r') as f:
        job = yaml.safe_load(f)
    
    url = job.get('url')
    task = job.get('task')
    job_id = job.get('id', 'unknown')
    
    print(f"[opal_driver] Starting Task: {job_id}")
    print(f"[opal_driver] Target: {url}")
    print(f"[opal_driver] Goal: {task}")

    with sync_playwright() as p:
        # Launch persistent context to reuse login if possible, or standard launch
        # Assuming user might need to login once manually or we use a specific profile
        # For this v1, we launch headed so user can sign-in if needed, or headless if confident.
        # Hybrid Lane implies we might use a user profile directory.
        
        user_data_dir = os.path.expanduser("~/0luka/modules/opal/browser_profile")
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Headful for v1 to allow manual login/visual proof
            channel="chrome", # Try to use installed chrome if available, else chromium
            args=["--disable-blink-features=AutomationControlled"]
        )
        
        page = browser.pages[0]
        # Handle Creation or Navigation
        if url in ["NEW", "CREATE"]:
            print("[opal_driver] Mode: CREATE NEW PROJECT")
            page.goto("https://opal.google")
            
            # Click Create Button (Scouted Selector: #create-new-button-inline)
            try:
                # Check for Login Barrier
                try:
                    if page.locator('#sign-in-header').is_visible(timeout=3000):
                         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                         print("[opal_driver] LOGIN REQUIRED: Please sign in to Google in the browser window!")
                         print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                except:
                    pass

                # Handle Landing Page Redirection (Try Opal / Sign In)
                try:
                    # Look for "Try Opal" or common landing page signals
                    if page.get_by_text("Try Opal").is_visible():
                        print("[opal_driver] Found 'Try Opal' button. Clicking...")
                        page.get_by_text("Try Opal").click()
                    elif page.locator("a[href*='opal.google/']").first.is_visible():
                         # Fallback: Click first link that looks like entering the app
                         pass
                except:
                    pass

                # DEBUG: Take a screenshot of the home state
                page.screenshot(path=f"modules/opal/inbox/{job_id}_home_scout.png")

                # Wait for user to login and button to appear (increased timeout to 120s)
                try:
                    page.wait_for_selector('#create-new-button-inline', timeout=120000)
                    page.click('#create-new-button-inline')
                except:
                    print("[opal_driver] ID selector failed. Trying text-based click...")
                    page.get_by_text("Create New").click()
                
                print("[opal_driver] Clicked 'Create New'...")
                
                # Wait for URL to change (Project ID generation)
                page.wait_for_url(lambda u: "/edit/" in u, timeout=30000)
                url = page.url
                print(f"[opal_driver] New Project Created: {url}")
                
                # Save this new URL to the task file so Studio knows it
                job['url'] = url
                job['status'] = 'CREATED'
                with open(task_file, 'w') as f:
                    yaml.safe_dump(job, f)
                
            except Exception as e:
                print(f"[opal_driver] Creation Failed: {str(e)}")
                page.screenshot(path=f"modules/opal/inbox/{job_id}_error_create.png")
                return
        else:
            page.goto(url)
        
        # Wait for Editor or Login
        try:
            page.wait_for_selector('textarea[placeholder="Edit these steps"]', timeout=45000)
        except:
            print("[opal_driver] Editor not detected. Is login required?")
            # Screenshot for debug
            page.screenshot(path=f"modules/opal/inbox/{job_id}_error.png")
            return

        print("[opal_driver] Editor loaded.")
        
        # Execute Edit
        box = page.locator('textarea[placeholder="Edit these steps"]')
        box.click()
        box.fill(task)
        page.keyboard.press("Enter")
        
        print("[opal_driver] Task submitted. Waiting for processing...")
        
        # Wait for "Applying changes" or spinner to settle. 
        # Heuristic: Wait for stable network or specific UI state.
        time.sleep(10) # Minimal wait for v1
        
        # Verification Capture
        screenshot_path = f"modules/opal/inbox/{job_id}_result.png"
        page.screenshot(path=screenshot_path)
        print(f"[opal_driver] Evidence captured: {screenshot_path}")
        
        browser.close()
        
    print("[opal_driver] Success.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python opal_driver.py <task_yaml>")
        sys.exit(1)
    run_opal_task(sys.argv[1])
