; Zenith-OS NSIS Installer Script
; Creates a professional Windows installer

!include "MUI2.nsh"
!include "FileFunc.nsh"

; ===== Configuration =====
Name "Zenith-OS"
OutFile "Zenith-OS-Setup.exe"
InstallDir "$PROGRAMFILES\Zenith-OS"
InstallDirRegKey HKLM "Software\Zenith-OS" "InstallDir"
RequestExecutionLevel admin

; Version info
VIProductVersion "1.0.0.0"
VIAddVersionKey "ProductName" "Zenith-OS"
VIAddVersionKey "CompanyName" "ApeironAI"
VIAddVersionKey "FileDescription" "Zenith-OS Personal AI Agent Operating System"
VIAddVersionKey "FileVersion" "1.0.0"
VIAddVersionKey "ProductVersion" "1.0.0"

; ===== Modern UI =====
!define MUI_ABORTWARNING
!define MUI_ICON "icon.ico"
!define MUI_UNICON "icon.ico"

; Pages
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

; Languages
!insertmacro MUI_LANGUAGE "English"

; ===== Installation Sections =====
Section "Zenith-OS (Required)" SecMain
    SectionIn RO

    ; Set output path
    SetOutPath "$INSTDIR"

    ; Install main application
    File /r "dist\Zenith-OS\*.*"

    ; Create uninstaller
    WriteUninstaller "$INSTDIR\Uninstall.exe"

    ; Create start menu shortcuts
    CreateDirectory "$SMPROGRAMS\Zenith-OS"
    CreateShortCut "$SMPROGRAMS\Zenith-OS\Zenith-OS.lnk" "$INSTDIR\Zenith-OS.exe"
    CreateShortCut "$SMPROGRAMS\Zenith-OS\Uninstall.lnk" "$INSTDIR\Uninstall.exe"

    ; Create desktop shortcut
    CreateShortCut "$DESKTOP\Zenith-OS.lnk" "$INSTDIR\Zenith-OS.exe"

    ; Write registry keys
    WriteRegStr HKLM "Software\Zenith-OS" "InstallDir" "$INSTDIR"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "DisplayName" "Zenith-OS"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "UninstallString" "$\"$INSTDIR\Uninstall.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "DisplayIcon" "$\"$INSTDIR\Zenith-OS.exe$\""
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "Publisher" "ApeironAI"
    WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "DisplayVersion" "1.0.0"

    ; Get installed size
    ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
    IntFmt $0 "0x%08X" $0
    WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS" \
        "EstimatedSize" "$0"
SectionEnd

Section "Start Menu Shortcuts" SecStartMenu
    CreateDirectory "$SMPROGRAMS\Zenith-OS"
    CreateShortCut "$SMPROGRAMS\Zenith-OS\Zenith-OS.lnk" "$INSTDIR\Zenith-OS.exe"
    CreateShortCut "$SMPROGRAMS\Zenith-OS\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Desktop Shortcut" SecDesktop
    CreateShortCut "$DESKTOP\Zenith-OS.lnk" "$INSTDIR\Zenith-OS.exe"
SectionEnd

; ===== Descriptions =====
!insertmacro MUI_FUNCTION_DESCRIPTION_BEGIN
    !insertmacro MUI_DESCRIPTION_TEXT ${SecMain} "The core Zenith-OS application."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecStartMenu} "Add shortcuts to Start Menu."
    !insertmacro MUI_DESCRIPTION_TEXT ${SecDesktop} "Add shortcut to Desktop."
!insertmacro MUI_FUNCTION_DESCRIPTION_END

; ===== Uninstaller Section =====
Section "Uninstall"
    ; Remove files
    RMDir /r "$INSTDIR"

    ; Remove shortcuts
    RMDir /r "$SMPROGRAMS\Zenith-OS"
    Delete "$DESKTOP\Zenith-OS.lnk"

    ; Remove registry keys
    DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\Zenith-OS"
    DeleteRegKey HKLM "Software\Zenith-OS"
SectionEnd
