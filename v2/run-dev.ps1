<#!
.SYNOPSIS
    啟動重構後 v2 的開發入口，不需手動輸入 runtime/app 路徑。
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = Join-Path $root 'runtime\lib\python_embed\python.exe'
$entry = Join-Path $root 'app\main.pyw'

if (!(Test-Path -LiteralPath $python)) { throw "找不到內嵌 Python：$python" }
if (!(Test-Path -LiteralPath $entry)) { throw "找不到程式入口：$entry" }

& $python $entry @args
