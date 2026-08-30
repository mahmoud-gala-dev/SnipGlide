Set oWS = WScript.CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
strPath = fso.GetParentFolderName(WScript.ScriptFullName)
sDesktop = oWS.SpecialFolders("Desktop")
sLinkFile = sDesktop & "\SnipGlide Pro.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)

If fso.FileExists(strPath & "\.venv\Scripts\pythonw.exe") Then
    oLink.TargetPath = strPath & "\.venv\Scripts\pythonw.exe"
    oLink.Arguments = """" & strPath & "\app.py"""
Else
    oLink.TargetPath = "pythonw.exe"
    oLink.Arguments = """" & strPath & "\app.py"""
End If

oLink.WorkingDirectory = strPath
oLink.Description = "SnipGlide Pro - Text Expander & Smart Chat Notes"
oLink.IconLocation = strPath & "\snipglide\assets\icon.ico, 0"
oLink.Save
