;SetCompressor /SOLID zlib 


!define NAME "W5PL Driver for DL2MAN (tr)uSDX"
!define EXE "W5PL truSDX Driver"   ; Nuitka output name (build.ps1)
!define VERSION "beta-2026-11-08-3"
!define REGPATH_UNINSTSUBKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${NAME}"
Name "${NAME}"
; Beta: one script, two builds. makensis trusdx.nsi = x64/x86 (VSPE COM8/COM9 pair, bundled VB-CABLE + CH340).
; makensis /DARM64 /DVBCABLE_SETUP=<file> trusdx.nsi = Windows ARM64: no VSPE (no free ARM64 virtual COM driver),
;   CAT over TCP 127.0.0.1:4542 instead, current VB-CABLE + CH340 v3.9+ (ARM64 drivers) from arm64-drivers\.
!ifdef ARM64
  OutFile "Setup_W5PL_truSDX_Driver_beta_arm64.exe"
  !define DRIVER_ARGS "--cat-tcp 4542"
  !ifndef VBCABLE_DIR
    !define VBCABLE_DIR "arm64-drivers\vbcable"
  !endif
  !ifndef VBCABLE_SETUP
    !define VBCABLE_SETUP "VBCABLE_Setup_x64.exe"   ; build.ps1 passes the actual file name from arm64-drivers\vbcable folder
  !endif
!else
  OutFile "Setup_W5PL_truSDX_Driver_beta_x64.exe"
  !define DRIVER_ARGS ""
!endif
ShowInstDetails show
Unicode True
RequestExecutionLevel Admin ; Request admin rights on WinVista+ (when UAC is turned on)
InstallDir "$ProgramFiles\$(^Name)"
InstallDirRegKey HKLM "${REGPATH_UNINSTSUBKEY}" "UninstallString"

!include LogicLib.nsh
!include Integration.nsh
!include WinVer.nsh
!include x64.nsh


!include MUI.nsh
!include nsDialogs.nsh
!include WinCore.nsh ; MAKELONG
!include FileFunc.nsh ; GetParent

;Page custom nsDialogsWelcome
Page Directory
;Page InstFiles
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_LANGUAGE English
Page custom nsDialogsWelcome
Page custom PostInstall

Uninstpage UninstConfirm
Uninstpage InstFiles

!macro EnsureAdminRights
  UserInfo::GetAccountType
  Pop $0
  ${If} $0 != "admin" ; Require admin rights on WinNT4+
    MessageBox MB_IconStop "Administrator rights required!"
    SetErrorLevel 740 ; ERROR_ELEVATION_REQUIRED
    Quit
  ${EndIf}
!macroend

Function .onInit
  SetShellVarContext All
  !insertmacro EnsureAdminRights
  ; the new exe must not be running, or its files cannot be replaced
  nsExec::Exec 'taskkill /F /IM "${EXE}.exe"'
  Pop $2
  ; an older "truSDX Driver" (factory driver or earlier beta) is a separate program. Remove it FIRST: its uninstaller
  ; deletes the VSPE COM8/COM9 service this driver also uses (reinstalled below by PostInstall on x64).
  ReadRegStr $0 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\truSDX Driver" "UninstallString"
  ${If} $0 != ""
    MessageBox MB_YESNOCANCEL|MB_ICONQUESTION "An older $\"truSDX Driver$\" is installed (the factory driver or an earlier beta). Only one driver can use the radio at a time.$\r$\n$\r$\nYes = remove it now (recommended)$\r$\nNo = keep it and install anyway$\r$\nCancel = stop setup$\r$\n$\r$\nVB-CABLE and the CH340 USB driver stay installed." IDYES old_remove IDNO old_done
    Quit
    old_remove:
    StrCpy $1 $0 1
    ${If} $1 == '"'
      StrCpy $0 $0 "" 1     ; UninstallString is "C:\...\Uninst.exe" (quoted): strip the quotes
      StrCpy $0 $0 -1
    ${EndIf}
    ${GetParent} $0 $1
    nsExec::Exec 'taskkill /F /IM "truSDX Driver.exe"'   ; files of a running driver cannot be deleted
    Pop $2
    ExecWait '"$0" /S _?=$1' $2   ; _?= runs the uninstaller in place, so ExecWait really waits for it
    Delete "$0"                    ; with _?= the uninstaller leaves itself and its folder behind
    ${GetFileName} $1 $4
    ${If} $4 == "truSDX Driver"      ; only ever delete the old driver's own folder
      RMDir /r "$1"
    ${Else}
      RMDir "$1"                     ; anything else: only if it is empty
    ${EndIf}
    ReadRegStr $3 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\truSDX Driver" "UninstallString"
    ${If} $3 != ""
      MessageBox MB_OK|MB_ICONEXCLAMATION "The old $\"truSDX Driver$\" could not be removed completely (code $2). Setup continues; remove it later in Settings > Apps, then run this setup again (on Intel/AMD the COM8/COM9 pair is reinstalled by it)."
    ${EndIf}
    old_done:
  ${EndIf}
FunctionEnd

Function un.onInit
  SetShellVarContext All
  !insertmacro EnsureAdminRights
FunctionEnd


Section "Program files (Required)"
  SectionIn Ro

  SetOutPath $InstDir
  WriteUninstaller "$InstDir\Uninst.exe"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "DisplayName" "${NAME}"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "DisplayIcon" "$InstDir\${EXE}.exe,0"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "Publisher" "W5PL"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "UninstallString" '"$InstDir\Uninst.exe"'
  WriteRegStr HKLM "${REGPATH_UNINSTSUBKEY}" "QuietUninstallString" '"$InstDir\Uninst.exe" /S'
  WriteRegDWORD HKLM "${REGPATH_UNINSTSUBKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${REGPATH_UNINSTSUBKEY}" "NoRepair" 1

  File "trusdx.bmp"
  File /r "${EXE}.dist\*.*"
!ifdef ARM64
  File "arm64-drivers\CH341SER.EXE"
  SetOutPath "$InstDir\Setup_vbcable"
  File /r "${VBCABLE_DIR}\*.*"
  SetOutPath $InstDir
!else
  File "CH341SER.EXE"
  File /R "SetupVSPE_32"
  File /R "Setup_vbcable"
!endif
SectionEnd

Section "Start Menu shortcut"
  CreateShortcut /NoWorkingDir "$SMPrograms\${NAME}.lnk" "$InstDir\${EXE}.exe" "${DRIVER_ARGS}"
SectionEnd

!macro DeleteFileOrAskAbort path
  ClearErrors
  Delete "${path}"
  IfErrors 0 +3
    MessageBox MB_ABORTRETRYIGNORE|MB_ICONSTOP 'Unable to delete "${path}"!' IDRETRY -3 IDIGNORE +2
    Abort "Aborted"
!macroend

Section -Uninstall
  Delete "$InstDir\Uninst.exe"
  !insertmacro DeleteFileOrAskAbort "$InstDir\*"
  RMDir "$InstDir"
  DeleteRegKey HKLM "${REGPATH_UNINSTSUBKEY}"

!ifndef ARM64
  ExecWait '"sc.exe" stop EterlogicVspeService'
  ExecWait '"sc.exe" delete EterlogicVspeService'
  ExecWait '"$InstDir\SetupVSPE_32\WixInteractor.exe" on_uninstall'
!endif

  Delete "$InstDir\SetupVSPE_32\*.*"
  Delete "$InstDir\SetupVSPE_32"

  Delete "$InstDir\Setup_vbcable\*.*"
  RMDir "$InstDir\Setup_vbcable"

  ${UnpinShortcut} "$SMPrograms\${NAME}.lnk"
  Delete "$SMPrograms\${NAME}.lnk"
  RMDir /r "$InstDir"   ; beta: also remove Nuitka sub-folders
SectionEnd

Function PostInstall
	Delete "$InstDir\trusdx.bmp"

!ifndef ARM64
	ExecWait '"$InstDir\SetupVSPE_32\WixInteractor.exe" on_install'
    ExecWait '"$InstDir\SetupVSPE_32\EterlogicVspeService.exe" install "$InstDir\SetupVSPE_32\VSPEmulator.exe" "$InstDir\SetupVSPE_32\pair.vspe" "$LocalAppdata"'
    ExecWait '"sc.exe" start EterlogicVspeService'
!endif
	
    MessageBox MB_OK "Now, CH340 USB driver will be installed. Please connect (tr)usdx to USB and select INSTALL to continue."

	ExecWait '"$InstDir\CH341SER.EXE"'

    MessageBox MB_OK "Now, VAC will be installed. Please select INSTALL to continue, you may ignore the browser page."

!ifdef ARM64
	ExecWait '"$InstDir\Setup_vbcable\${VBCABLE_SETUP}"'
!else
	${If} ${RunningX64}
		ExecWait '"$InstDir\Setup_vbcable\VBCABLE_Setup_x64.exe"'
	${Else}
		ExecWait '"$InstDir\Setup_vbcable\VBCABLE_Setup.exe"'
	${EndIf}
!endif
	;Delete "$InstDir\Setup_vbcable\*.*"
	;RMDir "$InstDir\Setup_vbcable"

!ifdef ARM64
	MessageBox MB_OK "ARM64 edition: CAT runs over the network, no virtual COM port is used.$\r$\n$\r$\nIn WSJT-X set Radio > Serial Port to:  127.0.0.1:4542$\r$\nPTT Method: CAT.  Audio: CABLE Output (input) / CABLE Input (output)."
!else
	${IfNot} ${AtLeastWin8}
       MessageBox MB_OK "Unfortunatly this windows version is not supported by VSPE, download and install Virtual Serial Ports Emulator 0.937.4.747 for legacy OS systems, and create a COM8 COM9 pair."
	${EndIf}
!endif

	DetailPrint "Installation Finished"
FunctionEnd

Var DIALOG
Var HEADLINE
Var TEXT
Var IMAGECTL
Var IMAGE
Var HEADLINE_FONT

Function nsDialogsWelcome
	nsDialogs::Create 1044
	Pop $DIALOG
	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS}|${SS_BITMAP} 0 0 0 109u 193u ""
	Pop $IMAGECTL

    StrCpy $0 $InstDir\trusdx.bmp
	System::Call 'user32::LoadImage(p 0, t r0, i ${IMAGE_BITMAP}, i 0, i 0, i ${LR_LOADFROMFILE})p.s'
	Pop $IMAGE
	
	SendMessage $IMAGECTL ${STM_SETIMAGE} ${IMAGE_BITMAP} $IMAGE
	CreateFont $HEADLINE_FONT "$(^Font)" "18" "700"
	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 10u -130u 20u "W5PL Driver for DL2MAN (tr)uSDX"
	Pop $HEADLINE
	SendMessage $HEADLINE ${WM_SETFONT} $HEADLINE_FONT 0

	nsDialogs::CreateControl STATIC ${WS_VISIBLE}|${WS_CHILD}|${WS_CLIPSIBLINGS} 0 120u 32u -130u -32u "Audio and CAT over the single USB cable of the DL2MAN (tr)uSDX: no audio cables needed. A virtual audio cable (and on Intel/AMD a virtual COM port) is installed to connect WSJT-X or another digimode app. Start the driver from the Start menu: ${NAME}.$\r$\n$\r$\nBeta ${VERSION}, based on trusdx-audio by SQ3SWF / PE1NNZ."
	Pop $TEXT
	SetCtlColors $DIALOG 0 0xffffff
	SetCtlColors $HEADLINE 0 0xffffff
	SetCtlColors $TEXT 0 0xffffff
	nsDialogs::Show
	System::Call gdi32::DeleteObject(p$IMAGE)
FunctionEnd

Section
SectionEnd
