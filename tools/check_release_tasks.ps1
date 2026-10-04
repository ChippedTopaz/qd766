$ErrorActionPreference = 'Stop'
# Read-only deployment preflight. No registration, stopping, starting or process kill.
foreach ($TaskName in @('QD766 Public Backend', 'QD766 Worker')) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    if ($Task.Actions.Count -ne 1) { throw "Unexpected action count for $TaskName. Inspect locally." }
    $Action = $Task.Actions[0]
    $Arguments = [string]$Action.Arguments
    if ($Arguments -match '(?i)(password|secret|token|credentials|https?://)') {
        throw "Task arguments may contain sensitive configuration. Inspect locally; do not paste them."
    }
    [pscustomobject]@{
        TaskName = $TaskName
        State = $Task.State
        Execute = $Action.Execute
        Arguments = $Arguments
        WorkingDirectory = $Action.WorkingDirectory
    } | Format-List
}
