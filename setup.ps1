<#
.SYNOPSIS
  Create the GitHub repo from this folder, push, set GEMINI_API_KEY, and trigger the workflow once.
.EXAMPLE
  ./setup.ps1 -RepoName daily-dev-journal
#>
param(
    [string]$RepoName = "daily-dev-journal"
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "GitHub CLI (gh) not found. Install it and run 'gh auth login'." }
gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) { throw "Not logged in. Run 'gh auth login' first." }

$email = git config user.email
if ($email -ne "theeditornitish@gmail.com") {
    Write-Warning "Local git user.email is '$email'. Setting repo-local email to theeditornitish@gmail.com."
    git config user.email "theeditornitish@gmail.com"
    git config user.name "Nitish Singh"
}

Write-Host "Creating public repo '$RepoName' and pushing..."
gh repo create $RepoName --public --source . --remote origin --push
if ($LASTEXITCODE -ne 0) { throw "gh repo create failed." }

$answer = Read-Host "Set GEMINI_API_KEY secret now? (y/N)"
if ($answer -match '^[Yy]') {
    # gh prompts for the value without echoing it; the key never touches disk or history.
    gh secret set GEMINI_API_KEY --repo (gh repo view $RepoName --json nameWithOwner -q .nameWithOwner)
    if ($LASTEXITCODE -ne 0) { throw "Setting secret failed." }
} else {
    Write-Host "Skipped. The workflow will use the offline fallback until you add the secret."
}

Write-Host "Triggering the workflow once..."
Start-Sleep -Seconds 5   # give GitHub a moment to register the workflow file
gh workflow run daily-journal.yml --repo (gh repo view $RepoName --json nameWithOwner -q .nameWithOwner)
if ($LASTEXITCODE -ne 0) { Write-Warning "Trigger failed; run it from Actions -> Daily dev journal -> Run workflow." }

Write-Host "Done. Watch it with: gh run watch"
