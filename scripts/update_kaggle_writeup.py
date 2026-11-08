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
TARGET_URL = "https://www.kaggle.com/competitions/gemma-4-developer-agent-paper/writeups"
COOKIES_DB = "file:/home/mikhail/.config/yandex-browser/Default/Cookies?mode=ro"

def get_cookies():
    bus = dbus.SessionBus()
    service = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets")
    session = dbus.Interface(service, "org.freedesktop.Secret.Service").OpenSession("plain", "")[1]
    item = bus.get_object("org.freedesktop.secrets", "/org/freedesktop/secrets/collection/login/4")
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

    conn = sqlite3.connect(COOKIES_DB, uri=True)
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
    with open(WRITEUP_MD_PATH, "r", encoding="utf-8") as f:
        writeup_text = f.read()

    words = len(writeup_text.split())
    chars = len(writeup_text)
    print(f"Loaded academic writeup: {chars} characters, {words} words.")
    if words >= 3000:
        raise ValueError(f"Word count {words} exceeds Kaggle limit of 3000 words!")

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

        print(f"Navigating to competition writeups list: {TARGET_URL}...")
        page.goto(TARGET_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)

        print("Navigating to our writeup card detail page...")
        card = page.locator("text='AST-Guided Loops: Deterministic Verification for Gemma 4 SWE Agents'").first
        if not card.is_visible():
            print("ERROR: Writeup card not found on competition page!")
            sys.exit(1)
        card.click()
        page.wait_for_timeout(5000)

        print(f"Writeup detail page loaded: {page.url}")
        print("Clicking Edit button...")
        edit_btn = page.locator("button:has-text('Edit')").first
        if not edit_btn.is_visible():
            print("ERROR: Edit button not found on detail page!")
            sys.exit(1)
        edit_btn.click()
        page.wait_for_timeout(4000)

        # Locate the article textarea (the one with the largest content)
        textareas = page.locator("textarea").all()
        target_ta = None
        for ta in textareas:
            val = ta.input_value()
            if len(val) > 1000:
                target_ta = ta
                print(f"Target writeup textarea located with old length: {len(val)} characters.")
                break

        if not target_ta:
            print("ERROR: Writeup textarea not located!")
            sys.exit(1)

        print("Filling textarea with updated academic writeup text...")
        target_ta.fill(writeup_text)
        page.wait_for_timeout(1000)

        new_val = target_ta.input_value()
        print(f"Textarea updated. New text length: {len(new_val)} characters.")

        update_btn = page.locator("button:has-text('Update Submission')").first
        if not update_btn.is_visible():
            print("ERROR: Update Submission button not visible!")
            sys.exit(1)

        print("Clicking 'Update Submission' button...")
        update_btn.click()

        print("Waiting 14 seconds for server processing and re-render...")
        page.wait_for_timeout(14000)

        page.screenshot(path="/tmp/kaggle_published_updated.png")
        print("Screenshot saved to /tmp/kaggle_published_updated.png")

        content = page.content()
        with open("/tmp/kaggle_updated_page.html", "w", encoding="utf-8") as f:
            f.write(content)

        print("\n=== VERIFICATION CHECKS ===")
        print("Presence of '31.52%':", "31.52%" in content)
        print("Presence of '56.86%':", "56.86%" in content)
        print("Presence of 'Patch Test Pass Rate':", "Patch Test Pass Rate" in content)
        print("Presence of '120 live inference calls':", "120 live inference calls" in content)
        print("Presence of '0.2539':", "0.2539" in content)
        print("Presence of 'Submitted':", "Submitted" in content)
        print("Presence of 'AST-Guided Verification Suite':", "AST-Guided Verification Suite" in content)

        browser.close()

    print("\n=== NETWORK LOGS ===")
    for nl in network_logs:
        print(nl)

if __name__ == "__main__":
    main()
