import random
import string

def generate_trx_code() -> str:
    """
    Generate a bKash-style TrxID.
    Format: PST26-XXXXXX
    Characters: A-Z, 2-9 (Excluding 0, 1, O, I to avoid visual confusion).
    """
    # Alphabet without O and I
    allowed_letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    # Digits without 0 and 1
    allowed_digits = "23456789"
    allowed_chars = allowed_letters + allowed_digits
    
    random_part = "".join(random.choices(allowed_chars, k=6))
    return f"PST26-{random_part}"
