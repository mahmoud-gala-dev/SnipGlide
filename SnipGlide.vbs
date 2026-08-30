Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)

If fso.FileExists(strPath & "\.venv\Scripts\pythonw.exe") Then
    pyExe = strPath & "\.venv\Scripts\pythonw.exe"
Else
    pyExe = "pythonw.exe"
End If

WshShell.CurrentDirectory = strPath
WshShell.Run """" & pyExe & """ """ & strPath & "\app.py""", 0, False
