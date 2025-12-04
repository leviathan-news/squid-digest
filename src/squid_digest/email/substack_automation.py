"""Substack RSS import automation using Playwright browser automation."""

import json
import os
import time
from typing import Optional, List, Dict, Any
from playwright.sync_api import sync_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError


class SubstackAutomation:
    """Automate RSS feed import to Substack using browser automation.
    
    Supports dual authentication:
    1. Session cookies (primary, most persistent)
    2. Email/password login (fallback)
    """
    
    def __init__(
        self,
        substack_url: str = "https://leviathannews.substack.com",
        headless: bool = True,
        timeout: int = 60000
    ):
        """Initialize Substack automation.
        
        Args:
            substack_url: Base URL for Substack publication
            headless: Run browser in headless mode
            timeout: Page timeout in milliseconds
        """
        self.substack_url = substack_url.rstrip('/')
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
    
    def authenticate_with_cookies(self, cookies_json: str) -> bool:
        """Authenticate using session cookies.
        
        Args:
            cookies_json: JSON string containing cookies array
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            cookies = json.loads(cookies_json)
            if not isinstance(cookies, list):
                print("❌ Cookies must be a JSON array")
                return False
            
            # Validate cookie format
            for cookie in cookies:
                if not isinstance(cookie, dict):
                    print("❌ Each cookie must be a JSON object")
                    return False
                required_fields = ['name', 'value', 'domain']
                if not all(field in cookie for field in required_fields):
                    print(f"❌ Cookie missing required fields: {required_fields}")
                    return False
            
            # Navigate to Substack first to set domain context
            if not self.page:
                raise RuntimeError("Browser page not initialized. Call start() first.")
            
            self.page.goto(self.substack_url, wait_until="domcontentloaded", timeout=self.timeout)
            time.sleep(2)  # Allow page to load
            
            # Add cookies
            self.page.context.add_cookies(cookies)
            
            # Verify authentication by checking if we're logged in
            self.page.goto(f"{self.substack_url}/publish", wait_until="domcontentloaded", timeout=self.timeout)
            time.sleep(2)
            
            # Check if we're redirected to login or if we see publish page
            current_url = self.page.url
            if "login" in current_url.lower() or "sign-in" in current_url.lower():
                print("⚠️  Cookie authentication failed - redirected to login")
                return False
            
            print("✓ Cookie authentication successful")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in cookies: {e}")
            return False
        except Exception as e:
            print(f"❌ Cookie authentication error: {e}")
            return False
    
    def authenticate_with_login(
        self,
        email: str,
        password: str
    ) -> bool:
        """Authenticate using email and password.
        
        Args:
            email: Substack account email
            password: Substack account password
            
        Returns:
            True if authentication successful, False otherwise
        """
        try:
            if not self.page:
                raise RuntimeError("Browser page not initialized. Call start() first.")
            
            # Navigate to login page
            login_url = f"{self.substack_url}/api/v1/login"
            self.page.goto(login_url, wait_until="domcontentloaded", timeout=self.timeout)
            time.sleep(2)
            
            # Try to find and fill email field
            # Substack login page structure may vary, try multiple selectors
            email_selectors = [
                'input[type="email"]',
                'input[name="email"]',
                'input[id="email"]',
                'input[placeholder*="email" i]',
            ]
            
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = self.page.wait_for_selector(selector, timeout=5000)
                    if email_field:
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not email_field:
                # Try navigating to the sign-in page instead
                signin_url = f"{self.substack_url}/account/login"
                self.page.goto(signin_url, wait_until="domcontentloaded", timeout=self.timeout)
                time.sleep(2)
                
                for selector in email_selectors:
                    try:
                        email_field = self.page.wait_for_selector(selector, timeout=5000)
                        if email_field:
                            break
                    except PlaywrightTimeoutError:
                        continue
            
            if not email_field:
                print("❌ Could not find email input field")
                return False
            
            email_field.fill(email)
            time.sleep(1)
            
            # Find and fill password field
            password_selectors = [
                'input[type="password"]',
                'input[name="password"]',
                'input[id="password"]',
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = self.page.wait_for_selector(selector, timeout=5000)
                    if password_field:
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not password_field:
                print("❌ Could not find password input field")
                return False
            
            password_field.fill(password)
            time.sleep(1)
            
            # Find and click submit button
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Sign in")',
                'button:has-text("Log in")',
                'button:has-text("Continue")',
                'input[type="submit"]',
            ]
            
            submit_button = None
            for selector in submit_selectors:
                try:
                    submit_button = self.page.wait_for_selector(selector, timeout=5000)
                    if submit_button:
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not submit_button:
                print("❌ Could not find submit button")
                return False
            
            submit_button.click()
            
            # Wait for navigation or error
            time.sleep(5)
            
            # Check if login was successful
            current_url = self.page.url
            if "login" in current_url.lower() or "sign-in" in current_url.lower():
                # Check for error messages
                error_selectors = [
                    '.error',
                    '[role="alert"]',
                    '.alert',
                    'text=/error/i',
                    'text=/invalid/i',
                ]
                for selector in error_selectors:
                    try:
                        error_element = self.page.query_selector(selector)
                        if error_element:
                            error_text = error_element.inner_text()
                            print(f"❌ Login failed: {error_text}")
                            return False
                    except:
                        continue
                
                print("❌ Login failed - still on login page")
                return False
            
            print("✓ Email/password authentication successful")
            return True
            
        except Exception as e:
            print(f"❌ Login authentication error: {e}")
            return False
    
    def import_rss_feed(self, rss_url: str) -> bool:
        """Import RSS feed to Substack.
        
        Args:
            rss_url: URL of the RSS feed to import
            
        Returns:
            True if import successful, False otherwise
        """
        try:
            if not self.page:
                raise RuntimeError("Browser page not initialized. Call start() first.")
            
            # Navigate to import page
            import_url = f"{self.substack_url}/publish/import"
            print(f"Navigating to import page: {import_url}")
            self.page.goto(import_url, wait_until="domcontentloaded", timeout=self.timeout)
            time.sleep(3)  # Allow page to fully load
            
            # Find RSS feed input field
            # Try multiple selectors for the RSS URL input
            rss_input_selectors = [
                'input[type="url"]',
                'input[name*="rss" i]',
                'input[name*="feed" i]',
                'input[placeholder*="rss" i]',
                'input[placeholder*="feed" i]',
                'input[placeholder*="url" i]',
            ]
            
            rss_input = None
            for selector in rss_input_selectors:
                try:
                    rss_input = self.page.wait_for_selector(selector, timeout=5000)
                    if rss_input:
                        print(f"✓ Found RSS input field with selector: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not rss_input:
                # Try to find any text input that might be for RSS
                all_inputs = self.page.query_selector_all('input[type="text"], input[type="url"]')
                if all_inputs:
                    print(f"⚠️  Found {len(all_inputs)} text/url inputs, trying first one")
                    rss_input = all_inputs[0]
                else:
                    print("❌ Could not find RSS feed input field")
                    print("Page content preview:")
                    print(self.page.content()[:500])
                    return False
            
            # Clear and fill RSS URL
            rss_input.clear()
            rss_input.fill(rss_url)
            time.sleep(1)
            
            # Find and click import/submit button
            import_button_selectors = [
                'button:has-text("Import")',
                'button:has-text("Submit")',
                'button[type="submit"]',
                'button:has-text("Continue")',
                'button:has-text("Next")',
            ]
            
            import_button = None
            for selector in import_button_selectors:
                try:
                    import_button = self.page.wait_for_selector(selector, timeout=5000)
                    if import_button:
                        print(f"✓ Found import button with selector: {selector}")
                        break
                except PlaywrightTimeoutError:
                    continue
            
            if not import_button:
                # Try to find any button that might be for import
                all_buttons = self.page.query_selector_all('button')
                if all_buttons:
                    print(f"⚠️  Found {len(all_buttons)} buttons, trying to find import button")
                    for button in all_buttons:
                        button_text = button.inner_text().lower()
                        if "import" in button_text or "submit" in button_text or "continue" in button_text:
                            import_button = button
                            break
                
                if not import_button:
                    print("❌ Could not find import button")
                    print("Available buttons on page:")
                    for button in self.page.query_selector_all('button'):
                        print(f"  - {button.inner_text()}")
                    return False
            
            print(f"Clicking import button...")
            import_button.click()
            
            # Wait for import to process
            print("Waiting for import to complete...")
            time.sleep(5)
            
            # Check for success indicators
            # Substack may show a success message or redirect
            current_url = self.page.url
            success_indicators = [
                'text=/success/i',
                'text=/imported/i',
                'text=/complete/i',
            ]
            
            # Check if we're still on import page (might indicate failure)
            if "import" not in current_url.lower():
                print(f"✓ Redirected to: {current_url}")
                print("✓ Import appears to have completed (redirected away from import page)")
                return True
            
            # Check for success messages
            for selector in success_indicators:
                try:
                    success_element = self.page.query_selector(selector)
                    if success_element:
                        success_text = success_element.inner_text()
                        print(f"✓ Import success: {success_text}")
                        return True
                except:
                    continue
            
            # Check for error messages
            error_selectors = [
                '.error',
                '[role="alert"]',
                '.alert',
                'text=/error/i',
                'text=/failed/i',
                'text=/invalid/i',
            ]
            
            for selector in error_selectors:
                try:
                    error_element = self.page.query_selector(selector)
                    if error_element:
                        error_text = error_element.inner_text()
                        print(f"❌ Import error: {error_text}")
                        return False
                except:
                    continue
            
            # If we're still here and no errors, assume success
            print("✓ Import completed (no errors detected)")
            return True
            
        except PlaywrightTimeoutError as e:
            print(f"❌ Timeout during RSS import: {e}")
            return False
        except Exception as e:
            print(f"❌ RSS import error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def start(self):
        """Start the browser and create a page."""
        playwright = sync_playwright().start()
        self.browser = playwright.chromium.launch(headless=self.headless)
        context = self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        self.page = context.new_page()
        self.page.set_default_timeout(self.timeout)
    
    def stop(self):
        """Stop the browser and cleanup."""
        if self.browser:
            self.browser.close()
            self.browser = None
        self.page = None
    
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
    
    def get_cookies(self) -> List[Dict[str, Any]]:
        """Get current browser cookies.
        
        Returns:
            List of cookie dictionaries
        """
        if not self.page:
            return []
        
        return self.page.context.cookies()

