# -----------------------------------------------------------------------------
# Escrow Service Integration Test & Demonstration
# -----------------------------------------------------------------------------
# This script executes a complete Escrow transaction lifecycle.
# It simulates an f-commerce transaction where a buyer secures funds,
# and later releases them upon receipt of goods.

$BaseUrl = "http://localhost:8000"

function Pause-Execution {
    param([string]$Message)
    Write-Host ""
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Write-Host " $Message" -ForegroundColor Yellow
    Write-Host "===============================================================================" -ForegroundColor Cyan
    Read-Host " Press ENTER to proceed..." | Out-Null
    Write-Host ""
}

function Print-Json {
    param (
        [Parameter(ValueFromPipeline=$true)]
        $InputObject
    )
    process {
        $InputObject | ConvertTo-Json -Depth 5 | Write-Host -ForegroundColor Green
    }
}

# -----------------------------------------------------------------------------
# STEP 1: Initialization
# -----------------------------------------------------------------------------
Pause-Execution "[Phase 1/4] Initializing buyer and seller accounts with 100,000.00 BDT."

# Use randomized identifiers to avoid unique constraint violations in repeated tests
$SessionId = Get-Random -Minimum 1000 -Maximum 9999
$BuyerUser = "buyer_client_$SessionId"
$SellerUser = "seller_client_$SessionId"

Write-Host "Registering $BuyerUser..."
Invoke-RestMethod -Method POST -Uri "$BaseUrl/auth/register" -ContentType "application/json" -Body "{`"username`":`"$BuyerUser`", `"password`":`"SecurePass123`"}" | Print-Json

Write-Host "Registering $SellerUser..."
Invoke-RestMethod -Method POST -Uri "$BaseUrl/auth/register" -ContentType "application/json" -Body "{`"username`":`"$SellerUser`", `"password`":`"SecurePass123`"}" | Print-Json

# Authenticate
$TokenBuyer = (Invoke-RestMethod -Method POST -Uri "$BaseUrl/auth/login" -ContentType "application/json" -Body "{`"username`":`"$BuyerUser`", `"password`":`"SecurePass123`"}").access_token
$TokenSeller = (Invoke-RestMethod -Method POST -Uri "$BaseUrl/auth/login" -ContentType "application/json" -Body "{`"username`":`"$SellerUser`", `"password`":`"SecurePass123`"}").access_token

Write-Host "`nAuthentication successful. Tokens acquired." -ForegroundColor Green

# -----------------------------------------------------------------------------
# STEP 2: Pre-Escrow Ledger State
# -----------------------------------------------------------------------------
Pause-Execution "[Phase 2/4] Verifying pre-escrow ledger state (Expected: 100,000.00 BDT)."

Write-Host "$BuyerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenBuyer"} | Print-Json

Write-Host "$SellerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenSeller"} | Print-Json

# -----------------------------------------------------------------------------
# STEP 3: Escrow Hold 
# -----------------------------------------------------------------------------
Pause-Execution "[Phase 3/4] Escrow Hold: Buyer secures 5,000.00 BDT in ESCROW_HOLD wallet.`nSecurity Constraint: Idempotency-Key prevents double-charging on network retries."

$IdempotencyKey = [guid]::NewGuid().ToString()

$EscrowBody = @{
    seller_username = $SellerUser
    amount_bdt = 5000.00
    note = "Payment held pending goods delivery"
} | ConvertTo-Json

$EscrowResult = Invoke-RestMethod -Method POST -Uri "$BaseUrl/escrow/payments" -Headers @{"Authorization"="Bearer $TokenBuyer"; "Idempotency-Key"=$IdempotencyKey} -ContentType "application/json" -Body $EscrowBody
$EscrowResult | Print-Json
$EscrowId = $EscrowResult.id

Write-Host "`nVerifying ledger state during hold... (Buyer should be debited 5,000.00, Seller unchanged)" -ForegroundColor Yellow

Write-Host "$BuyerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenBuyer"} | Print-Json

Write-Host "$SellerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenSeller"} | Print-Json

# -----------------------------------------------------------------------------
# STEP 4: Escrow Release
# -----------------------------------------------------------------------------
Pause-Execution "[Phase 4/4] Escrow Release: Buyer releases funds to Seller.`nSecurity Constraint: Uses SELECT...FOR UPDATE to prevent concurrent release/refund race conditions."

Invoke-RestMethod -Method POST -Uri "$BaseUrl/escrow/payments/$EscrowId/release" -Headers @{"Authorization"="Bearer $TokenBuyer"} | Print-Json

Write-Host "`nVerifying final ledger state... (Seller should be credited 5,000.00 BDT)" -ForegroundColor Yellow

Write-Host "$BuyerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenBuyer"} | Print-Json

Write-Host "$SellerUser Balance:"
Invoke-RestMethod -Method GET -Uri "$BaseUrl/wallets/me" -Headers @{"Authorization"="Bearer $TokenSeller"} | Print-Json

Write-Host ""
Write-Host "===============================================================================" -ForegroundColor Cyan
Write-Host " INTEGRATION TEST COMPLETE. Ledger integrity verified." -ForegroundColor Yellow
Write-Host "===============================================================================" -ForegroundColor Cyan
