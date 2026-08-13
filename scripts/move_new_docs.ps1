$keep_docs = @(
    "DOC_20260214_092951_7bd9ef5f",
    "DOC_20260214_094034_ffba3818",
    "DOC_20260214_095138_b48d7a73",
    "DOC_20260214_095552_7124e462",
    "DOC_20260214_095911_e1eae640",
    "DOC_20260214_100126_bdc5720d",
    "DOC_20260214_100316_74b4b28c",
    "DOC_20260214_100925_6d622853",
    "DOC_20260214_101828_69291d72",
    "DOC_20260214_102540_c9251636",
    "DOC_20260214_103408_0e6b0664",
    "DOC_20260214_103609_f8ef1724",
    "DOC_20260214_104008_65935823",
    "DOC_20260214_104513_7477507b",
    "DOC_20260214_105007_23b3640c",
    "DOC_20260214_105249_2fc4409c",
    "DOC_20260214_130309_185aaa71",
    "DOC_20260214_143927_913b92d8",
    "DOC_20260214_144443_e738685c"
)

$source = "E:\GL_AI\data_processed\documents"
$dest = "E:\GL_AI\data_processed\new_documents"

if (!(Test-Path -Path $dest)) {
    New-Item -ItemType Directory -Path $dest | Out-Null
}

$dirs = Get-ChildItem -Path $source -Directory

foreach ($dir in $dirs) {
    if ($keep_docs -notcontains $dir.Name) {
        $dest_path = Join-Path -Path $dest -ChildPath $dir.Name
        if (Test-Path -Path $dest_path) {
            Remove-Item -Path $dest_path -Recurse -Force
        }
        Move-Item -Path $dir.FullName -Destination $dest -Force
        Write-Output "Moved $($dir.Name)"
    } else {
        Write-Output "Kept $($dir.Name)"
    }
}
