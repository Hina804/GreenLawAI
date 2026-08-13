# Detached pipeline runner - survives IDE close. Resumes via is_already_processed().
$ErrorActionPreference = "Continue"
$Root = "E:\GL_AI"
$LogOut = "$Root\data_processed\new_documents\pipeline_stdout.log"
$LogErr = "$Root\data_processed\new_documents\pipeline_stderr.log"
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
Write-Output "=== Pipeline detached start $(Get-Date -Format o) ===" | Out-File $LogOut -Append -Encoding utf8
& python "$Root\run_new_documents_pipeline.py" *>> $LogOut 2>> $LogErr
Write-Output "=== Pipeline exit $(Get-Date -Format o) exitcode=$LASTEXITCODE ===" | Out-File $LogOut -Append -Encoding utf8
