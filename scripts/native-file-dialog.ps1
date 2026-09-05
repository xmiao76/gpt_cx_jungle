param([Parameter(Mandatory=$true)][string]$ApplicationPath,[Parameter(Mandatory=$true)][string]$FilePath)
$ErrorActionPreference='Stop'
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public static class JungleDialogText {
  [DllImport("user32.dll")]
  public static extern bool IsWindowVisible(IntPtr window);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")]
  private static extern IntPtr SendText(IntPtr window, uint message, IntPtr wparam, string text);
  [DllImport("user32.dll", CharSet=CharSet.Unicode, EntryPoint="SendMessageW")]
  private static extern IntPtr ReadText(IntPtr window, uint message, IntPtr wparam, StringBuilder text);
  [DllImport("user32.dll", SetLastError=true)]
  private static extern bool PostMessageW(IntPtr window,uint message,IntPtr wparam,IntPtr lparam);
  public static void Press(IntPtr window) {
    if(window==IntPtr.Zero || !PostMessageW(window,0x00F5,IntPtr.Zero,IntPtr.Zero)) throw new Exception("Cannot click the native dialog button.");
  }
  public static void Accept(IntPtr dialog, IntPtr button) {
    if(dialog==IntPtr.Zero || !PostMessageW(dialog,0x0111,new IntPtr(1),button)) throw new Exception("Cannot accept the native file dialog.");
  }
  public static string SetAndRead(IntPtr window, string text) {
    if(window==IntPtr.Zero) throw new Exception("Missing native Edit window.");
    SendText(window,0x000C,IntPtr.Zero,text);
    var buffer=new StringBuilder(32768);
    ReadText(window,0x000D,new IntPtr(buffer.Capacity),buffer);
    return buffer.ToString();
  }
}
'@
$resolvedApp=[IO.Path]::GetFullPath($ApplicationPath)
$resolvedFile=[IO.Path]::GetFullPath($FilePath)
$artifactRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\artifacts')) + [IO.Path]::DirectorySeparatorChar
if(-not $resolvedFile.StartsWith($artifactRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Test dialog targets must stay inside artifacts.'}
$deadline=[DateTime]::UtcNow.AddSeconds(20)
$loggedDialog=$false
while([DateTime]::UtcNow -lt $deadline){
  $appProcesses=Get-CimInstance Win32_Process -Filter "Name='Jungle.exe'" | Where-Object {$_.ExecutablePath -eq $resolvedApp}
  foreach($appProcess in $appProcesses){
    $condition=New-Object System.Windows.Automation.AndCondition(
      (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty,[int]$appProcess.ProcessId)),
      (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'#32770')))
    $dialog=[System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
    if($dialog){
      $editCondition=New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ClassNameProperty,'Edit')
      $edits=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,$editCondition)
      $edit=$null
      foreach($candidate in $edits){
        $parent=[System.Windows.Automation.TreeWalker]::ControlViewWalker.GetParent($candidate)
        if(-not $loggedDialog){Write-Output ('Edit name='+$candidate.Current.Name+'; id='+$candidate.Current.AutomationId+'; parent='+$parent.Current.Name+'; parentId='+$parent.Current.AutomationId)}
        if($candidate.Current.Name -eq 'File name:' -or $parent.Current.AutomationId -in @('1148','FileNameControlHost')){$edit=$candidate;break}
      }
      if(-not $edit -and $edits.Count -eq 1){$edit=$edits[0]}
      $accept=$dialog.FindFirst([System.Windows.Automation.TreeScope]::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::AutomationIdProperty,'1')))
      if(-not $loggedDialog){Write-Output ('Dialog='+$dialog.Current.Name+'; handle='+$dialog.Current.NativeWindowHandle+'; edit='+[bool]$edit+'; accept='+[bool]$accept);$loggedDialog=$true}
      if($edit -and $accept){
        # This Windows shell exposes its filename Edit as a UIA Pane. Use the
        # native text message on that exact, application-owned control.
        $actual=[JungleDialogText]::SetAndRead([IntPtr]$edit.Current.NativeWindowHandle,$resolvedFile)
        if($actual -ne $resolvedFile){throw 'The native filename field did not accept the path.'}
        Start-Sleep -Milliseconds 150
        if(-not $accept.Current.IsEnabled){continue}
        [JungleDialogText]::Accept([IntPtr]$dialog.Current.NativeWindowHandle,[IntPtr]$accept.Current.NativeWindowHandle)
        $dialogHandle=$dialog.Current.NativeWindowHandle
        $closeDeadline=[DateTime]::UtcNow.AddSeconds(5)
        while([DateTime]::UtcNow -lt $closeDeadline){
          Start-Sleep -Milliseconds 150
          $open=[JungleDialogText]::IsWindowVisible([IntPtr]$dialogHandle)
          if(-not $open){Write-Output 'Native file dialog closed after accepting the path.';exit 0}
        }
        $controls=$dialog.FindAll([System.Windows.Automation.TreeScope]::Descendants,[System.Windows.Automation.Condition]::TrueCondition)
        foreach($control in $controls){
          if($control.Current.ControlType.ProgrammaticName -ne 'ControlType.ListItem'){
            Write-Output ('Control name='+$control.Current.Name+'; id='+$control.Current.AutomationId+'; class='+$control.Current.ClassName+'; handle='+$control.Current.NativeWindowHandle+'; type='+$control.Current.ControlType.ProgrammaticName)
          }
        }
        throw 'The native dialog did not close after accepting the filename.'
      }
    }
  }
  Start-Sleep -Milliseconds 150
}
throw 'The application file dialog was not found.'
