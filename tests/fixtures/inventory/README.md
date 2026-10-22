Synthetic fake homes and a fake project for `tests/test_inventory_contract.py`.
Every secret-shaped value contains the word `canary`; the tests assert that no
inventory output ever contains it. `@HOME@` and `@PROJECT@` are replaced with the
temporary copy's absolute paths before use. Nothing here is copied from a real
machine.
