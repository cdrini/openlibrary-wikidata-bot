#!/usr/bin/expect

spawn python3 /app/src/pywikibot/pwb.py login -dir:/pywikibot
expect "Password*\r"
send -- "$env(PASSWORD)\r"
expect eof
