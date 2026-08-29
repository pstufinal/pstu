$ErrorActionPreference = 'Stop'
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8000/scaling/metrics" -Method Get
    Write-Host "`n=== SCALING METRICS DEMO ==="
    Write-Host "CONNECTIONS:"
    Write-Host "  Active: $($response.connections.current_active) / $($response.connections.max_allowed) ($($response.connections.utilization_percent)%)"
    Write-Host "`nTABLE SIZES:"
    foreach ($table in $response.table_sizes.PSObject.Properties) {
        Write-Host "  $($table.Name): $($table.Value)"
    }
    Write-Host "`n>>> NEXT SCALING STEP <<<"
    Write-Host $response.next_scaling_step
    Write-Host "============================`n"
} catch {
    Write-Host "ERROR: Could not reach the server at http://localhost:8000"
    Write-Host $_.Exception.Message
    exit 1
}
