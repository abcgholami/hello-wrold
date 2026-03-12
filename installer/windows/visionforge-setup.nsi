; =============================================================================
; VisionForge Platform — Windows Installer
; Requires NSIS 3.x  (https://nsis.sourceforge.io)
;
; Build:
;   makensis visionforge-setup.nsi
;   (or use installer/windows/build.ps1 on a Windows machine)
; =============================================================================

Unicode True

;------------------------------------------------------------------------------
; Includes
;------------------------------------------------------------------------------
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "WinVer.nsh"
!include "x64.nsh"
!include "FileFunc.nsh"

;------------------------------------------------------------------------------
; Metadata
;------------------------------------------------------------------------------
!define PRODUCT_NAME      "VisionForge"
!define PRODUCT_VERSION   "1.0.0"
!define PRODUCT_PUBLISHER "VisionForge Team"
!define PRODUCT_URL       "http://localhost"
!define PRODUCT_GUID      "{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}"

!define INSTALL_DIR       "$PROGRAMFILES64\${PRODUCT_NAME}"
!define STARTMENU_FOLDER  "${PRODUCT_NAME}"
!define UNINSTALLER_NAME  "Uninstall VisionForge.exe"

!define REG_UNINSTALL     "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define REG_INSTALL       "Software\${PRODUCT_NAME}"

; Docker Desktop minimum version
!define DOCKER_MIN_VER    "4.0.0"
!define DOCKER_URL        "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"

;------------------------------------------------------------------------------
; General Settings
;------------------------------------------------------------------------------
Name              "${PRODUCT_NAME} ${PRODUCT_VERSION}"
OutFile           "VisionForge-Setup-${PRODUCT_VERSION}.exe"
InstallDir        "${INSTALL_DIR}"
InstallDirRegKey  HKLM "${REG_INSTALL}" "InstallDir"
RequestExecutionLevel admin
SetCompressor     /SOLID lzma
SetCompress       auto

;------------------------------------------------------------------------------
; MUI2 Interface Settings
;------------------------------------------------------------------------------
!define MUI_ABORTWARNING
!define MUI_ICON          "assets\icon.ico"
!define MUI_UNICON        "assets\icon.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP   "assets\installer-side.bmp"
!define MUI_UNWELCOMEFINISHPAGE_BITMAP "assets\installer-side.bmp"

!define MUI_WELCOMEPAGE_TITLE   "Welcome to VisionForge ${PRODUCT_VERSION} Setup"
!define MUI_WELCOMEPAGE_TEXT    "This wizard will install VisionForge — a full-stack, no-code machine vision platform.$\r$\n$\r$\nDocker Desktop is required. The installer will offer to download it if it is not already present.$\r$\n$\r$\nClick Next to continue."

!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT      "Launch VisionForge now"
!define MUI_FINISHPAGE_RUN_FUNCTION  LaunchVisionForge
!define MUI_FINISHPAGE_LINK          "Open VisionForge in browser"
!define MUI_FINISHPAGE_LINK_LOCATION "http://localhost"
!define MUI_FINISHPAGE_SHOWREADME
!define MUI_FINISHPAGE_SHOWREADME_TEXT "Show release notes"
!define MUI_FINISHPAGE_SHOWREADME_FUNCTION ShowReleaseNotes

;------------------------------------------------------------------------------
; Pages — Installer
;------------------------------------------------------------------------------
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "..\..\LICENSE"
Page custom PageGPU PageGPULeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

;------------------------------------------------------------------------------
; Pages — Uninstaller
;------------------------------------------------------------------------------
!insertmacro MUI_UNPAGE_WELCOME
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_UNPAGE_FINISH

;------------------------------------------------------------------------------
; Languages
;------------------------------------------------------------------------------
!insertmacro MUI_LANGUAGE "English"

;------------------------------------------------------------------------------
; Variables
;------------------------------------------------------------------------------
Var GPUEnabled
Var DockerInstalled
Var StartMenuFolder

;------------------------------------------------------------------------------
; GPU option page
;------------------------------------------------------------------------------
!include "nsDialogs.nsh"

Var GPU_Dialog
Var GPU_Check
Var GPU_Label

Function PageGPU
  nsDialogs::Create 1018
  Pop $GPU_Dialog
  ${If} $GPU_Dialog == error
    Abort
  ${EndIf}

  ${NSD_CreateLabel} 0 0 100% 30u "GPU Support (optional)"
  Pop $0
  SendMessage $0 ${WM_SETFONT} $mui.Header.text.Font 0

  ${NSD_CreateLabel} 0 35u 100% 40u "Enable GPU support if you have an NVIDIA GPU and want to use hardware-accelerated training and inference. Requires an NVIDIA driver (>= 527.41) and WSL 2 backend."
  Pop $GPU_Label

  ${NSD_CreateCheckBox} 0 85u 100% 15u "Enable NVIDIA GPU support (requires NVIDIA GPU + driver)"
  Pop $GPU_Check
  ${NSD_SetState} $GPU_Check $BST_UNCHECKED

  nsDialogs::Show
FunctionEnd

Function PageGPULeave
  ${NSD_GetState} $GPU_Check $GPUEnabled
FunctionEnd

;------------------------------------------------------------------------------
; Helper — check Docker Desktop
;------------------------------------------------------------------------------
Function CheckDockerDesktop
  ; Try to locate Docker CLI
  nsExec::ExecToStack 'cmd /C "docker --version >nul 2>&1"'
  Pop $0
  ${If} $0 == 0
    StrCpy $DockerInstalled "yes"
  ${Else}
    StrCpy $DockerInstalled "no"
  ${EndIf}
FunctionEnd

;------------------------------------------------------------------------------
; Helper — install Docker Desktop silently
;------------------------------------------------------------------------------
Function InstallDockerDesktop
  DetailPrint "Downloading Docker Desktop installer..."
  NSISdl::download "${DOCKER_URL}" "$TEMP\DockerDesktopInstaller.exe"
  Pop $0
  ${If} $0 != "success"
    MessageBox MB_ICONEXCLAMATION|MB_OK \
      "Failed to download Docker Desktop.$\r$\nPlease install it manually from:$\r$\nhttps://www.docker.com/products/docker-desktop/"
    Abort
  ${EndIf}

  DetailPrint "Installing Docker Desktop (this may take several minutes)..."
  ExecWait '"$TEMP\DockerDesktopInstaller.exe" install --quiet --accept-license' $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION|MB_OK \
      "Docker Desktop installation did not complete successfully (exit code $0).$\r$\nPlease install Docker Desktop manually and re-run this installer."
    Abort
  ${EndIf}

  DetailPrint "Docker Desktop installed. A system restart may be required."
FunctionEnd

;------------------------------------------------------------------------------
; Helper — ensure WSL 2 is enabled
;------------------------------------------------------------------------------
Function EnsureWSL2
  ; Enable WSL feature silently (no-op if already enabled)
  DetailPrint "Ensuring WSL 2 is enabled..."
  nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -Command \
    "dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart | Out-Null; \
     dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart | Out-Null; \
     wsl --set-default-version 2 2>$null"'
FunctionEnd

;------------------------------------------------------------------------------
; Finish page callbacks
;------------------------------------------------------------------------------
Function LaunchVisionForge
  ; Start services in the background via the start script
  nsExec::Exec '"$INSTDIR\start-visionforge.bat"'
FunctionEnd

Function ShowReleaseNotes
  ExecShell "open" "$INSTDIR\RELEASE_NOTES.txt"
FunctionEnd

;------------------------------------------------------------------------------
; Main install section
;------------------------------------------------------------------------------
Section "VisionForge Platform" SecMain
  SectionIn RO   ; required, cannot be de-selected

  SetOutPath "$INSTDIR"

  ; ── Pre-requisite checks ─────────────────────────────────────────────────
  Call CheckDockerDesktop
  ${If} $DockerInstalled == "no"
    MessageBox MB_ICONINFORMATION|MB_YESNO \
      "Docker Desktop was not found on this PC.$\r$\n$\r$\nVisionForge requires Docker Desktop to run.$\r$\n$\r$\nDownload and install Docker Desktop now? (approx. 500 MB)" \
      IDYES DoInstallDocker IDNO SkipDocker
    DoInstallDocker:
      Call EnsureWSL2
      Call InstallDockerDesktop
    SkipDocker:
  ${Else}
    DetailPrint "Docker Desktop detected — skipping installation."
    ; Still make sure WSL 2 is the backend
    Call EnsureWSL2
  ${EndIf}

  ; ── Extract project files ─────────────────────────────────────────────────
  DetailPrint "Extracting VisionForge files..."

  ; Core project structure
  SetOutPath "$INSTDIR"
  File /r "..\..\infra"
  File /r "..\..\backend"
  File /r "..\..\frontend"
  File /r "..\..\sdks"
  File "..\..\Makefile"
  File ".env.template"         ; pre-built .env template shipped with installer

  ; Installer helper scripts
  SetOutPath "$INSTDIR"
  File "scripts\post-install.ps1"
  File "scripts\start-visionforge.ps1"
  File "scripts\stop-visionforge.ps1"

  ; Batch wrappers (double-clickable without needing to open PowerShell)
  File "scripts\start-visionforge.bat"
  File "scripts\stop-visionforge.bat"
  File "scripts\open-visionforge.bat"

  ; ── Generate .env if it doesn't exist ────────────────────────────────────
  ${If} ${FileExists} "$INSTDIR\.env"
    DetailPrint ".env already exists — keeping existing configuration."
  ${Else}
    DetailPrint "Generating .env from template with a random JWT secret..."
    nsExec::ExecToLog 'powershell -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\post-install.ps1" -InstallDir "$INSTDIR"'
  ${EndIf}

  ; ── Write GPU flag to .env ────────────────────────────────────────────────
  ${If} $GPUEnabled == ${BST_CHECKED}
    DetailPrint "GPU support enabled — appending COMPOSE_PROFILES=gpu to .env"
    FileOpen $0 "$INSTDIR\.env" a
    FileSeek $0 0 END
    FileWrite $0 "$\r$\nCOMPOSE_PROFILES=gpu$\r$\n"
    FileClose $0
  ${EndIf}

  ; ── Start menu shortcuts ──────────────────────────────────────────────────
  !insertmacro MUI_STARTMENU_WRITE_BEGIN Application
  CreateDirectory "$SMPROGRAMS\$StartMenuFolder"
  CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Start VisionForge.lnk" \
    "$INSTDIR\start-visionforge.bat" "" "$INSTDIR\assets\icon.ico"
  CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Stop VisionForge.lnk" \
    "$INSTDIR\stop-visionforge.bat" "" "$INSTDIR\assets\icon.ico"
  CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Open VisionForge.lnk" \
    "$INSTDIR\open-visionforge.bat" "" "$INSTDIR\assets\icon.ico"
  CreateShortcut "$SMPROGRAMS\$StartMenuFolder\Uninstall VisionForge.lnk" \
    "$INSTDIR\${UNINSTALLER_NAME}" "" "$INSTDIR\assets\icon.ico"
  !insertmacro MUI_STARTMENU_WRITE_END

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\VisionForge.lnk" \
    "$INSTDIR\start-visionforge.bat" "" "$INSTDIR\assets\icon.ico" 0 \
    SW_SHOWNORMAL "" "Start VisionForge"

  ; ── Write registry keys ───────────────────────────────────────────────────
  WriteRegStr HKLM "${REG_INSTALL}" "InstallDir" "$INSTDIR"
  WriteRegStr HKLM "${REG_INSTALL}" "Version"    "${PRODUCT_VERSION}"
  WriteRegStr HKLM "${REG_INSTALL}" "GPUEnabled" "$GPUEnabled"

  ; Add/Remove Programs entry
  WriteRegStr   HKLM "${REG_UNINSTALL}" "DisplayName"     "${PRODUCT_NAME} ${PRODUCT_VERSION}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "DisplayVersion"  "${PRODUCT_VERSION}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "Publisher"       "${PRODUCT_PUBLISHER}"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "InstallLocation" "$INSTDIR"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "UninstallString" '"$INSTDIR\${UNINSTALLER_NAME}"'
  WriteRegStr   HKLM "${REG_UNINSTALL}" "DisplayIcon"     "$INSTDIR\assets\icon.ico"
  WriteRegStr   HKLM "${REG_UNINSTALL}" "URLInfoAbout"    "${PRODUCT_URL}"
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoModify"        1
  WriteRegDWORD HKLM "${REG_UNINSTALL}" "NoRepair"        1

  ; ── Create uninstaller ────────────────────────────────────────────────────
  WriteUninstaller "$INSTDIR\${UNINSTALLER_NAME}"

SectionEnd

;------------------------------------------------------------------------------
; Uninstaller
;------------------------------------------------------------------------------
Section "Uninstall"

  ; Stop running services first
  DetailPrint "Stopping VisionForge services..."
  nsExec::ExecToLog '"$INSTDIR\stop-visionforge.bat"'

  ; Remove files
  RMDir /r "$INSTDIR\infra"
  RMDir /r "$INSTDIR\backend"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\sdks"
  RMDir /r "$INSTDIR\assets"
  Delete "$INSTDIR\.env"
  Delete "$INSTDIR\.env.template"
  Delete "$INSTDIR\Makefile"
  Delete "$INSTDIR\post-install.ps1"
  Delete "$INSTDIR\start-visionforge.ps1"
  Delete "$INSTDIR\stop-visionforge.ps1"
  Delete "$INSTDIR\start-visionforge.bat"
  Delete "$INSTDIR\stop-visionforge.bat"
  Delete "$INSTDIR\open-visionforge.bat"
  Delete "$INSTDIR\RELEASE_NOTES.txt"
  Delete "$INSTDIR\${UNINSTALLER_NAME}"
  RMDir  "$INSTDIR"

  ; Remove Start Menu folder
  !insertmacro MUI_STARTMENU_GETFOLDER Application $StartMenuFolder
  RMDir /r "$SMPROGRAMS\$StartMenuFolder"

  ; Remove Desktop shortcut
  Delete "$DESKTOP\VisionForge.lnk"

  ; Remove registry keys
  DeleteRegKey HKLM "${REG_UNINSTALL}"
  DeleteRegKey HKLM "${REG_INSTALL}"

  MessageBox MB_ICONINFORMATION|MB_OK \
    "VisionForge has been uninstalled.$\r$\n$\r$\nNote: Docker Desktop and Docker volumes (database, model cache) have been preserved.$\r$\nTo remove them, open Docker Desktop → Volumes."

SectionEnd
