# Manual Test Commands

## Full System Demo
```powershell
python demo_all.py
```

## TrxID Verification (Public Proof-of-Payment)

```powershell
# 1. Verify a standard transfer (Replace PST26-XXXXXX with a real ID)
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/verify/PST26-ABCDEF"
# Expected Output:
# {
#   "trx_code": "PST26-ABCDEF",
#   "type": "TRANSFER",
#   "amount": "2000.00",
#   "status": "completed",
#   "created_at": "2026-08-29T12:00:00Z",
#   "sender_masked": "ali***",
#   "receiver_masked": "bob***"
# }

# 2. Verify an Escrow Release
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/verify/PST26-GHIJKL"
# Expected Output:
# {
#   "trx_code": "PST26-GHIJKL",
#   "type": "ESCROW_RELEASE",
#   "amount": "5000.00",
#   "status": "completed",
#   "created_at": "2026-08-29T12:05:00Z",
#   "sender_masked": "ESC***",
#   "receiver_masked": "bob***"
# }

# 3. Test a Fake/Invalid TrxID (404 Not Found)
Invoke-RestMethod -Method GET -Uri "http://localhost:8000/verify/PST26-FAKEXX"
# Expected Output (HTTP 404):
# {
#   "detail": "Transaction not found."
# }
```
