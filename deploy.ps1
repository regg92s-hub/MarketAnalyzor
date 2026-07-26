# v14/D1: Git-basert deploy — erstatter håndlim som har avkuttet filer to ganger
# OG sultet GitHub Actions' 60-dagers aktivitetstimer (kun commits teller).
#
# Bruk:
#   1. Engangs: git clone https://github.com/regg92s-hub/MarketAnalyzor.git C:\repos\MarketAnalyzor
#   2. Pakk ut market-analysor.zip fra Claude et sted (f.eks. C:\temp\market-analysor)
#   3. .\deploy.ps1 -Source C:\temp\market-analysor
#
# Skriptet kopierer scripts/, tests/, workflows og README inn i klonen,
# committer og pusher. Git nekter delvise filer — avkuttingsproblemet dør her.
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [string]$Repo = "C:\repos\MarketAnalyzor"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$Repo\.git")) { throw "Fant ikke git-repo i $Repo - kjør git clone først" }
if (-not (Test-Path "$Source\scripts\build.py")) { throw "Kilden $Source ser ikke ut som market-analysor" }

# Kopier (speil scripts/ og tests/, enkeltfiler ellers)
robocopy "$Source\scripts" "$Repo\scripts" /MIR /NFL /NDL /NJH /NJS | Out-Null
if (Test-Path "$Source\tests") { robocopy "$Source\tests" "$Repo\tests" /MIR /NFL /NDL /NJH /NJS | Out-Null }
robocopy "$Source\.github\workflows" "$Repo\.github\workflows" /MIR /NFL /NDL /NJH /NJS | Out-Null
Copy-Item "$Source\README.md" "$Repo\README.md" -Force
Copy-Item "$Source\deploy.ps1" "$Repo\deploy.ps1" -Force -ErrorAction SilentlyContinue

# Versjon fra config -> commit-melding
$ver = (Select-String -Path "$Repo\scripts\analysor\config.py" -Pattern 'VERSION = "([^"]+)"').Matches[0].Groups[1].Value
Push-Location $Repo
try {
    git add -A
    $status = git status --porcelain
    if (-not $status) { Write-Host "Ingen endringer å deploye."; return }
    git commit -m "deploy $ver"
    git push
    Write-Host "Deployet $ver. Sjekk Actions-fanen: CI-testen kjører på pushen."
    Write-Host "NB: Hvis schedule var deaktivert (60 dager uten commits), reaktiver den i Actions-fanen."
} finally { Pop-Location }
