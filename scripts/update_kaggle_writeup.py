#!/usr/bin/env python3
"""Update Kaggle Writeup on the competition web portal with audited academic text."""

import os
import sys
import dbus
import sqlite3
import hashlib
import time
import json
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from playwright.sync_api import sync_playwright

WRITEUP_MD_PATH = "/home/mikhail/gemma-4-developer-agent/paper/writeup.md"
TARGET_URL = "https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups/ast-guided-deterministic-gemma4-agent"
COOKIES_DB = "/tmp/chrome_cookies.db"

def get_cookies():
    bus = dbus.SessionBus()
    service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
    session = dbus.Interface(service, "org.freedesktop.Secret.Service").OpenSession("plain", "")[1]
    item = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets/collection/login/6")
    secret_bytes = bytes(dbus.Interface(item, "org.freedesktop.Secret.Item").GetSecret(session)[2])

    key = hashlib.pbkdf2_hmac("sha1", secret_bytes, b"saltysalt", 1, 16)
    cipher = Cipher(algorithms.AES(key), modes.CBC(b" " * 16))

    def decrypt_val(enc_val):
        if not enc_val:
            return ""
        dec = cipher.decryptor().update(enc_val[3:])
        pad = dec[-1]
        raw = dec[:-pad]
        return raw[32:].decode("utf-8", errors="ignore")

    conn = sqlite3.connect(COOKIES_DB)
    c = conn.cursor()
    c.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%kaggle%'")

    pw_cookies = []
    for h, n, val in c.fetchall():
        cookie_val = decrypt_val(val)
        if not cookie_val:
            continue
        pw_cookies.append({"name": n, "value": cookie_val, "url": "https://www.kaggle.com"})
    return pw_cookies

def main():
    with open(WRITEUP_MD_PATH) as f:
        writeup_text = f.read()

    words = len(writeup_text.split())
    chars = len(writeup_text)
    print(f"Loaded academic writeup: {chars} characters, {words} words.")

    pw_cookies = get_cookies()
    print(f"Extracted {len(pw_cookies)} authenticated Kaggle cookies.")

    network_logs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        context.add_cookies(pw_cookies)
        page = context.new_page()

        def on_response(response):
            if any(k in response.url.lower() for k in ["writeup", "hackathon", "save"]):
                network_logs.append(f"{response.request.method} {response.url} -> HTTP {response.status}")
        page.on("response", on_response)

        print(f"Navigating to {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(4000)

        print("Clicking Edit button...")
        clicked = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll("button"));
            const editBtn = btns.find(b => b.innerText.trim() === "Edit");
            if (editBtn) {
                editBtn.click();
                return true;
            }
            return false;
        }""")
        if not clicked:
            print("ERROR: Edit button not found or not clickable!")
            sys.exit(1)

        page.wait_for_timeout(4000)

        ta = page.locator("textarea.sc-fpQesT__input").first
        old_val = ta.input_value()
        print(f"Textarea located. Old text length: {len(old_val)} characters.")

        print("Filling textarea with updated academic text...")
        ta.fill(writeup_text)
        page.wait_for_timeout(1000)

        new_val = ta.input_value()
        print(f"Textarea updated. New text length: {len(new_val)} characters.")

        update_btn = page.locator("button:has-text('Update Submission')").first
        if not update_btn.is_visible():
            print("ERROR: Update Submission button not visible!")
            sys.exit(1)

        print("Clicking 'Update Submission' button...")
        update_btn.click()

        print("Waiting 12 seconds for server processing and re-render...")
        page.wait_for_timeout(12000)

        page.screenshot(path="/tmp/kaggle_published_updated.png")
        print("Screenshot saved to /tmp/kaggle_published_updated.png")

        content = page.content()
        with open("/tmp/kaggle_updated_page.html", "w") as f:
            f.write(content)

        print("\n=== VERIFICATION CHECKS ===")
        print("Old '18.2%' in page:", "18.2%" in content)
        print("Old '39.4%' in page:", "39.4%" in content)
        print("Old '66.5%' in page:", "66.5%" in content)
        print("New '44.6%' in page:", "44.6%" in content)
        print("New '30.6%' in page:", "30.6%" in content)
        print("New '38.2' in page:", "38.2" in content)
        print("New '3.893 ms' in page:", "3.893 ms" in content)
        print("New 'Component Ablation Study' in page:", "Component Ablation Study" in content)
        print("Title 'AST-Guided Verification Suite' in page:", "AST-Guided Verification Suite" in content)

        browser.close()

    print("\n=== NETWORK LOGS ===")
    for nl in network_logs:
        print(nl)

if __name__ == "__main__":
    main()
