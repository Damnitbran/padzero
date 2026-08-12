# stats.ps1 - how many people are actually using Pad Zero.
#
# Everything here comes from GitHub's own data. The tool itself contains no
# telemetry and never will: a printer utility that phones home would deserve
# every antivirus warning it got, and trust is the only thing this project
# has going for it.
#
# Usage:  powershell -ExecutionPolicy Bypass -File stats.ps1

$repo = "Damnitbran/padzero"

function Line { param($k, $v) "{0,-34} {1}" -f $k, $v }

Write-Host ""
Write-Host "==============================================================="
Write-Host " PAD ZERO  ::  $repo"
Write-Host "==============================================================="

# ---------------------------------------------------------------- downloads
Write-Host ""
Write-Host "-- Downloads --------------------------------------------------"
$releases = gh api "repos/$repo/releases" 2>$null | ConvertFrom-Json
if (-not $releases) {
    Write-Host "  (no releases, or not authenticated - run: gh auth login)"
} else {
    $grand = 0
    foreach ($r in $releases) {
        $sum = 0
        foreach ($a in $r.assets) { $sum += $a.download_count }
        $grand += $sum
        Write-Host ""
        Write-Host ("  {0}  ({1})" -f $r.tag_name, ([datetime]$r.published_at).ToString("d MMM yyyy"))
        foreach ($a in $r.assets) {
            Write-Host (Line ("    " + $a.name) ("{0} downloads" -f $a.download_count))
        }
        if (-not $r.assets) { Write-Host "    (no files attached)" }
    }
    Write-Host ""
    Write-Host (Line "  TOTAL DOWNLOADS" $grand)
}

# ------------------------------------------------------------------ interest
Write-Host ""
Write-Host "-- Interest ---------------------------------------------------"
$repoInfo = gh api "repos/$repo" 2>$null | ConvertFrom-Json
if ($repoInfo) {
    Write-Host (Line "  Stars" $repoInfo.stargazers_count)
    Write-Host (Line "  Forks" $repoInfo.forks_count)
    Write-Host (Line "  Watchers" $repoInfo.subscribers_count)
    Write-Host (Line "  Open issues" $repoInfo.open_issues_count)
    Write-Host (Line "  Visibility" $(if ($repoInfo.private) { "PRIVATE - nobody can download" } else { "public" }))
}

# ------------------------------------------------------------------- traffic
# GitHub only keeps 14 days of traffic data, so check in occasionally or
# it is simply gone.
Write-Host ""
Write-Host "-- Traffic (last 14 days) -------------------------------------"
$views = gh api "repos/$repo/traffic/views" 2>$null | ConvertFrom-Json
if ($views) {
    Write-Host (Line "  Page views" $views.count)
    Write-Host (Line "  Unique visitors" $views.uniques)
} else {
    Write-Host "  (needs push access, or no data yet)"
}
$clones = gh api "repos/$repo/traffic/clones" 2>$null | ConvertFrom-Json
if ($clones) {
    Write-Host (Line "  Clones" $clones.count)
    Write-Host (Line "  Unique cloners" $clones.uniques)
}
$refs = gh api "repos/$repo/traffic/popular/referrers" 2>$null | ConvertFrom-Json
if ($refs -and $refs.Count) {
    Write-Host ""
    Write-Host "  Where people came from:"
    foreach ($r in $refs) {
        Write-Host ("    {0,-24} {1} views, {2} unique" -f $r.referrer, $r.count, $r.uniques)
    }
}

# -------------------------------------------------------------------- issues
Write-Host ""
Write-Host "-- Recent issues ----------------------------------------------"
$issues = gh issue list --repo $repo --limit 10 --state all --json number,title,state,createdAt 2>$null | ConvertFrom-Json
if ($issues -and $issues.Count) {
    foreach ($i in $issues) {
        Write-Host ("  #{0,-4} [{1,-6}] {2}" -f $i.number, $i.state, $i.title)
    }
} else {
    Write-Host "  (none yet)"
}

Write-Host ""
Write-Host "==============================================================="
Write-Host " Issues are the signal that matters most. Someone opening one"
Write-Host " with a model you have never seen is both real usage and the"
Write-Host " only way coverage grows."
Write-Host "==============================================================="
Write-Host ""
