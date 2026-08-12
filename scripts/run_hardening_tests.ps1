$ErrorActionPreference = "Stop"

function Test-Python312([string]$Executable, [string[]]$PrefixArgs) {
    try {
        $output = & $Executable @PrefixArgs -c "import sys; print(sys.version_info[:2] == (3, 12))" 2>$null
        return $LASTEXITCODE -eq 0 -and $output -eq "True"
    } catch {
        return $false
    }
}

$python = $null
$pythonPrefix = @()
if (Get-Command py -ErrorAction SilentlyContinue) {
    if (Test-Python312 "py" @("-3.12")) {
        $python = "py"
        $pythonPrefix = @("-3.12")
    }
}

if (-not $python) {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    )
    $candidates += @(Get-Command python -All -ErrorAction SilentlyContinue | ForEach-Object Source)
    foreach ($candidate in $candidates | Select-Object -Unique) {
        if ((Test-Path -LiteralPath $candidate) -and (Test-Python312 $candidate @())) {
            $python = $candidate
            break
        }
    }
}

if (-not $python) {
    $fallback = Get-Command python -ErrorAction SilentlyContinue
    if (-not $fallback) {
        throw "Python 3.12 is unavailable and no fallback Python interpreter was found."
    }
    $python = $fallback.Source
    Write-Warning "Python 3.12 is unavailable; validating with $python."
}

function Invoke-Checked([string]$Label, [string]$Executable, [string[]]$Arguments) {
    Write-Host "==> $Label"
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

$hardeningCandidates = @(
    "tests/test_mtf_no_lookahead.py",
    "tests/test_a03_canonical_action.py",
    "tests/test_a04_scheduler_pipeline_contract.py",
    "tests/test_a05_fail_closed_safeguards.py",
    "tests/test_a05_prediction_context.py",
    "tests/test_a06_a15_data_layer.py",
    "tests/test_a08_first_run_readiness.py",
    "tests/test_a09_risk_sizing.py",
    "tests/test_a13_a14_hardening.py",
    "tests/test_a18_test_isolation.py",
    "tests/test_infrastructure.py"
)
$hardeningTests = @($hardeningCandidates | Where-Object { Test-Path -LiteralPath $_ })

Invoke-Checked "Existing hardening regressions" $python @(
    $pythonPrefix + @("-m", "pytest", "-q") + $hardeningTests
)
Invoke-Checked "B1 closed-loop persistence" $python @(
    $pythonPrefix + @("-m", "pytest", "-q", "tests/test_b1_closed_loop_persistence.py")
)
Invoke-Checked "Python compileall" $python @($pythonPrefix + @("-m", "compileall", "-q", "."))
Invoke-Checked "git diff --check" "git" @("diff", "--check")
