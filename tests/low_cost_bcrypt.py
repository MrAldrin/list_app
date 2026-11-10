"""Make bcrypt cheap for tests. Import this before the app.

Password hashing at production cost takes about 0.2 s for each hash and each
check. Almost every API test signs in, so tests use the lowest bcrypt cost.
A check takes its cost from the stored hash, so this also makes sign-in fast.
test_password_hashes.py checks the production cost with the real function.
"""

import bcrypt

REAL_GENSALT = bcrypt.gensalt
TEST_COST = 4


def _low_cost_gensalt(rounds: int = TEST_COST, prefix: bytes = b"2b") -> bytes:
    return REAL_GENSALT(TEST_COST, prefix)


bcrypt.gensalt = _low_cost_gensalt
