' 감성힙합 자동화 스튜디오 - 자동 실행 스크립트
Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

' 현재 폴더 경로 가져오기
strCurrentPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

' Python 경로 확인
strPythonPath = ""
strCmd = "where python"

Set objExec = objShell.Exec(strCmd)
strPythonPath = objExec.StdOut.ReadAll()

If strPythonPath = "" Then
    MsgBox "Python이 설치되어 있지 않습니다. Python을 먼저 설치해주세요.", vbCritical, "오류"
    WScript.Quit
End If

' 패키지 설치 + 앱 실행
strCommand = "cd /d " & strCurrentPath & " && pip install -r requirements.txt -q && streamlit run app.py"

' cmd 창을 보이지 않게 실행
objShell.Run "cmd /c " & strCommand, 0, False

' 3초 후 브라우저 자동 실행
WScript.Sleep 3000
objShell.Run "start http://localhost:8501"
