# app/core/phone.py
import re

E164_RE = re.compile(r'^\+[1-9]\d{1,14}$')

def normalize_phone(value: str) -> str:
    v = re.sub(r'[\s\-().]', '', value)      # remove spaces, dashes, brackets

    if v.startswith('+'):
        pass                                  # +27821234567, +260971234567
    elif v.startswith('00'):
        v = '+' + v[2:]                       # 0027821234567
    elif v.startswith('0'):
        v = '+27' + v[1:]                     # 0821234567 (South Africa)
    elif v.startswith('27') and len(v) == 11:
        v = '+' + v                           # 27821234567
    else:
        raise ValueError('phone must start with 0, 27 or +country code')

    if not E164_RE.match(v):
        raise ValueError('invalid phone number')
    return v