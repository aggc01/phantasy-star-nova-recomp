# A live progress bar for a scripted game run: the newest "frame N" line in its log against the frame it runs to,
# finished when the run's output file appears (a capture, a last shot).
#   powershell -File dev\watch_progress.ps1 -Log <run log> -Target <frame> [-Done <file>] [-Label <text>]
param([Parameter(Mandatory)][string]$Log, [Parameter(Mandatory)][int]$Target, [string]$Done = "", [string]$Label = "Game run")
$start = Get-Date; $width = 40
while ($true) {
	$frame = 0
	if (Test-Path $Log) {
		$m = Select-String -Path $Log -Pattern 'frame (\d+):' -AllMatches | Select-Object -Last 1
		if ($m) { $frame = [int]$m.Matches[-1].Groups[1].Value }
	}
	$finished = $Done -and (Test-Path $Done)
	$pct = if ($finished) { 100 } else { [math]::Min(99, [int](100 * $frame / $Target)) }
	$fill = [int]($width * $pct / 100)
	$bar = ('#' * $fill) + ('-' * ($width - $fill))
	$secs = [int]((Get-Date) - $start).TotalSeconds
	$eta = if ($frame -gt 0 -and -not $finished) { " ~$([int]($secs * ($Target - $frame) / $frame))s left" } else { "" }
	Write-Host -NoNewline "`r$Label [$bar] $pct%  frame $frame / $Target  ${secs}s$eta      "
	if ($finished) { Write-Host ""; Write-Host "Done: $Done"; break }
	Start-Sleep -Milliseconds 500
}
