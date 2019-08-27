#!/usr/bin/expect

spawn python3 -m pwb login -dir:/pywikibot
expect "Password*\r"
send -- "$env(PASSWORD)\r"
expect eof
