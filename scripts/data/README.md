# scripts/data/

## common_passwords.txt

**Source:** SecLists — `Passwords/Common-Credentials/10k-most-common.txt`  
**URL:** https://github.com/danielmiessler/SecLists  
**Downloaded:** 2026-05-12  
**Line count:** 10,000  
**Format:** One password per line, UTF-8, LF line endings.

Used by `durgam/services/password.py` → `PasswordService.validate_policy()` to deny
commonly-used passwords per RFP §6.1. Loaded at service import time into a frozenset
for O(1) membership tests.

**Do not commit runtime secrets or PII to this directory.**
