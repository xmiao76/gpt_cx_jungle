$ErrorActionPreference='Stop'
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$locations=@('C:\Program Files (x86)\Microsoft\EdgeWebView\Application','C:\Program Files\Microsoft\EdgeWebView\Application')
if($env:LOCALAPPDATA){$locations+=Join-Path $env:LOCALAPPDATA 'Microsoft\EdgeWebView\Application'}
$versions=@()
foreach($location in $locations){
 if(Test-Path -LiteralPath $location){
  $versions+=Get-ChildItem -LiteralPath $location -Directory | Where-Object {$_.Name -match '^\d+\.\d+\.\d+\.\d+$'} | Select-Object -ExpandProperty Name
 }
}
if(-not $versions){throw 'Install the Microsoft WebView2 runtime before desktop GUI validation.'}
$version=$versions | Sort-Object {[version]$_} -Descending | Select-Object -First 1
$folder=[IO.Path]::GetFullPath((Join-Path $workspace ('artifacts\tools\edge-'+$version)))
if(-not $folder.StartsWith($workspace+'\artifacts\tools\',[StringComparison]::OrdinalIgnoreCase)){throw 'Invalid driver directory.'}
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$driver=Join-Path $folder 'msedgedriver.exe'
if(-not (Test-Path -LiteralPath $driver)){
 $archive=Join-Path $folder 'driver.zip'
 Invoke-WebRequest -Uri ('https://msedgedriver.microsoft.com/'+$version+'/edgedriver_win64.zip') -OutFile $archive -UseBasicParsing
 Expand-Archive -LiteralPath $archive -DestinationPath $folder -Force
}
& $driver --version
Write-Output $driver
