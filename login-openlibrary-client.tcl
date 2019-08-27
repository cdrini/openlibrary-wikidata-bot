#!/usr/bin/expect

spawn ol --configure --email "$env(USERNAME)"
expect "password*\r"
send -- "$env(PASSWORD)\r"
expect "Successfully configured\r"
