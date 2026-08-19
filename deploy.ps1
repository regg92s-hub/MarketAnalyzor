# v14/D1 + v19-sikring: Git-basert deploy — erstatter håndlim som har
# avkuttet filer to ganger OG sultet GitHub Actions' 60-dagers aktivitets-
# timer (kun commits teller).
#
# v19: HERDET etter en hendelse der -Source ved en feil pekte på en gammel/
# ufullstendig mappe. robocopy /MIR speiler kildemappen eksakt — mangler
# kilden filer som finnes i repoet, SLETTES de. Skriptet stopper nå FØR
# noe kopieres hvis kilden mangler kjente nøkkelfiler, eller har vesentlig
# færre Python-filer enn det som allerede ligger i repoet (typisk tegn på
# feil/utdatert kildemappe).
#
# Bruk:
#   1. Engangs: git clone https://github.com/regg92s-hub/MarketAnalyzor.git C:\repos\MarketAnalyzor
#   2. Pakk ut market-analysor.zip fra Claude et sted (f.eks. C:\temp\market-analysor)
#   3. .\deploy.ps1 -Source "C:\temp\market-analysor\market-analysor"
#
# Skriptet kopierer scripts/, tests/, workflows og README inn i klonen,
# committer og pusher. Git nekter delvise filer — avkuttingsproblemet dør her.
param(
    [Parameter(Mandatory=$true)][string]$Source,
    [string]$Repo = "C:\repos\MarketAnalyzor",
    [switch]$Force   # hopp over sikkerhetssjekkene (bruk kun hvis du BEVISST fjerner filer)
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path "$Repo\.git")) { throw "Fant ikke git-repo i $Repo - kjor git clone forst" }
if (-not (Test-Path "$Source\scripts\build.py")) { throw "Kilden $Source ser ikke ut som market-analysor (mangler scripts\build.py)" }

# ── Sikkerhetssjekk 1: kjente nøkkelfiler må finnes i kilden ──────────────
$requiredFiles = @(
    "scripts\build.py",
    "scripts\build_screener.py",
    "scripts\analysor\config.py",
    "scripts\analysor\render.py",
    "scripts\analysor\layout.py",
    "scripts\analysor\data.py",
    "scripts\analysor\indicators.py",
    "scripts\analysor\scoring.py",
    "scripts\analysor\analytics.py",
    "scripts\analysor\regime.py",
    "scripts\analysor\today.py",
    "scripts\analysor\roadmap.py",
    "scripts\analysor\portfolio.py",
    "scripts\analysor\backtest.py",
    "scripts\analysor\benchmarks.py",
    "scripts\analysor\paper.py",
    "scripts\analysor\validation.py",
    "scripts\analysor\glossary.py",
    "scripts\analysor\positioning.py",
    "scripts\analysor\screener.py",
    "scripts\analysor\stock_universe.py",
    "scripts\analysor\universe_fetch.py"
)
$missing = $requiredFiles | Where-Object { -not (Test-Path (Join-Path $Source $_)) }
if ($missing.Count -gt 0 -and -not $Force) {
    Write-Host "STOPPER: kilden $Source mangler $($missing.Count) forventede fil(er):" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Dette ser ut som en GAMMEL eller UFULLSTENDIG utpakking, ikke den" -ForegroundColor Yellow
    Write-Host "nyeste zip-en. Robocopy /MIR ville SLETTET disse filene fra repoet." -ForegroundColor Yellow
    Write-Host "Pakk ut den nyeste zip-en pa nytt til en ren mappe og prov igjen." -ForegroundColor Yellow
    Write-Host "(Bruk -Force hvis du BEVISST fjerner disse filene.)" -ForegroundColor Yellow
    throw "Avbrutt - se manglende filer over."
}

# ── Sikkerhetssjekk 2: kilden bør ikke ha vesentlig FÆRRE Python-filer ────
# enn det som allerede ligger i repoet -- klassisk tegn på feil/gammel kilde.
$srcPyCount = (Get-ChildItem "$Source\scripts" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue).Count
$repoPyCount = (Get-ChildItem "$Repo\scripts" -Recurse -Filter "*.py" -ErrorAction SilentlyContinue).Count
if ($repoPyCount -gt 0 -and $srcPyCount -lt ($repoPyCount * 0.7) -and -not $Force) {
    Write-Host "STOPPER: kilden har kun $srcPyCount Python-filer, repoet har $repoPyCount." -ForegroundColor Red
    Write-Host "Det er over 30% nedgang -- speiling ville sannsynligvis SLETTET filer" -ForegroundColor Yellow
    Write-Host "som er i bruk. Sjekk at -Source peker pa riktig, nyeste mappe." -ForegroundColor Yellow
    Write-Host "(Bruk -Force hvis dette er tilsiktet, f.eks. en bevisst opprydding.)" -ForegroundColor Yellow
    throw "Avbrutt - kildemappen virker ufullstendig sammenlignet med repoet."
}

Write-Host "Sikkerhetssjekk OK: $srcPyCount Python-filer i kilden (repo har $repoPyCount fra for)." -ForegroundColor Green

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
    if (-not $status) { Write-Host "Ingen endringer a deploye."; return }

    # ── Sikkerhetssjekk 3: vis en oppsummering av SLETTEDE filer FØR commit ──
    $deletions = $status -split "`n" | Where-Object { $_ -match "^\s*D\s" }
    if ($deletions.Count -gt 5 -and -not $Force) {
        Write-Host "ADVARSEL: denne endringen vil SLETTE $($deletions.Count) filer fra repoet:" -ForegroundColor Red
        $deletions | Select-Object -First 15 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        if ($deletions.Count -gt 15) { Write-Host "  ... og $($deletions.Count - 15) til" -ForegroundColor Red }
        Write-Host ""
        $confirm = Read-Host "Skriv JA for a bekrefte at dette er tilsiktet, eller noe annet for a avbryte"
        if ($confirm -ne "JA") { throw "Avbrutt av bruker - ingen commit gjort." }
    }

    git commit -m "deploy $ver"
    git push
    Write-Host "Deployet $ver. Sjekk Actions-fanen: CI-testen kjorer pa pushen."
    Write-Host "NB: Hvis schedule var deaktivert (60 dager uten commits), reaktiver den i Actions-fanen."
} finally { Pop-Location }
