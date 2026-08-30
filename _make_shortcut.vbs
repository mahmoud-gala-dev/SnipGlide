Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "C:\Users\mrbea\Desktop\SnipGlide Pro.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "C:\Users\mrbea\Downloads\New folder (31)\snipglide_python\SnipGlide.vbs"
oLink.WorkingDirectory = "C:\Users\mrbea\Downloads\New folder (31)\snipglide_python"
oLink.Description = "SnipGlide Pro - Text Expander & Smart Chat Notes"
oLink.IconLocation = "C:\Users\mrbea\Downloads\New folder (31)\snipglide_python\snipglide\assets\icon.ico, 0"
oLink.Save
