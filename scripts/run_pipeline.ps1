param(
  [Parameter(Mandatory=$true)][string]$Input,
  [string]$Date,
  [string]$StartTime,
  [switch]$UseMtime
)

$cmd = @("daylog", "run", "--input", $Input)
if ($Date) { $cmd += @("--date", $Date) }
if ($StartTime) { $cmd += @("--start-time", $StartTime) }
if ($UseMtime) { $cmd += @("--use-mtime") }
& $cmd
