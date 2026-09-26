@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
if not defined UMD_BUILD_VERSION set "UMD_BUILD_VERSION=4.3.0"
title Universal Media Downloader V%UMD_BUILD_VERSION% Builder

echo ============================================================
echo   Universal Media Downloader V%UMD_BUILD_VERSION% Builder
echo ============================================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    set "PY=py -3"
    goto PY_FOUND
)
where python >nul 2>&1
if %errorlevel%==0 (
    set "PY=python"
    goto PY_FOUND
)
echo Python 3 was not found. Install Python 3.11+ and enable PATH.
pause
exit /b 1

:PY_FOUND
where iscc >nul 2>&1
if %errorlevel%==0 (
    set "ISCC=iscc"
    goto ISCC_FOUND
)
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
    goto ISCC_FOUND
)
if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" (
    set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
    goto ISCC_FOUND
)
echo Inno Setup 6 was not found.
echo Install Inno Setup 6, then run this builder again.
pause
exit /b 1

:ISCC_FOUND
echo.
echo [1/7] Installing Python build dependencies...
%PY% -m pip install --upgrade PySide6 PyInstaller
if errorlevel 1 goto FAIL

rem Use the official PyInstaller wheel for a conventional, reproducible build.
rem Do not compile or alter the PyInstaller bootloader locally.
rem UPX is explicitly disabled. No obfuscation or anti-analysis is used.
set "BOOTLOADER_MODE=Official PyInstaller wheel"


echo.
echo [2/7] Preparing clean build folders...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist installer_output rmdir /s /q installer_output
mkdir build\components
mkdir installer_output

if exist __pycache__ rmdir /s /q __pycache__
for /r %%F in (*.pyc) do del /q "%%F" >nul 2>&1


echo.
echo [3/7] Bundling current helper components...
if not exist build\components\yt-dlp.exe (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe' -OutFile 'build\components\yt-dlp.exe'"
    if errorlevel 1 goto FAIL
)
if not exist build\components\ffmpeg.exe (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile 'build\ffmpeg.zip'; Expand-Archive -Force 'build\ffmpeg.zip' 'build\ffmpeg_extract'; $f=Get-ChildItem 'build\ffmpeg_extract' -Recurse -Filter 'ffmpeg.exe' | Select-Object -First 1; if(-not $f){throw 'ffmpeg.exe not found'}; Copy-Item $f.FullName 'build\components\ffmpeg.exe'; Remove-Item 'build\ffmpeg.zip' -Force; Remove-Item 'build\ffmpeg_extract' -Recurse -Force"
    if errorlevel 1 goto FAIL
)

if exist build\components\yt-dlp.exe (build\components\yt-dlp.exe --version > build\components\yt-dlp-version.txt)
if exist build\components\ffmpeg.exe (build\components\ffmpeg.exe -version > build\components\ffmpeg-version.txt)
certutil -hashfile "build\components\yt-dlp.exe" SHA256 > "build\components\yt-dlp.exe.sha256.txt"
certutil -hashfile "build\components\ffmpeg.exe" SHA256 > "build\components\ffmpeg.exe.sha256.txt"


echo.
echo [4/7] Building the application EXE (standard onedir, UPX disabled)...
rem onedir avoids a self-extracting one-file executable, which is a more conventional
rem Windows distribution and can reduce heuristic/ML false positives.
%PY% -m PyInstaller --noconsole --onedir --clean --noupx --name UniversalMediaDownloader --icon=UniversalMediaDownloader.ico --version-file=version_info.txt main.py
if errorlevel 1 goto FAIL
if not exist dist\UniversalMediaDownloader\UniversalMediaDownloader.exe goto FAIL


echo.
echo [5/7] Generating SHA-256 checksum...
certutil -hashfile "dist\UniversalMediaDownloader\UniversalMediaDownloader.exe" SHA256 > "dist\UniversalMediaDownloader\UniversalMediaDownloader.exe.sha256.txt"
if errorlevel 1 goto FAIL


echo.
echo [6/7] Building the Windows installer...
"%ISCC%" /DMyAppVersion=%UMD_BUILD_VERSION% UniversalMediaDownloader.iss
if errorlevel 1 goto FAIL

if not exist installer_output\UniversalMediaDownloader_Setup_v%UMD_BUILD_VERSION%.exe goto FAIL
certutil -hashfile "installer_output\UniversalMediaDownloader_Setup_v%UMD_BUILD_VERSION%.exe" SHA256 > "installer_output\UniversalMediaDownloader_Setup_v%UMD_BUILD_VERSION%.exe.sha256.txt"


echo.
echo [7/7] Writing build information...
> "installer_output\BUILD_INFO.txt" echo Universal Media Downloader v%UMD_BUILD_VERSION%
>>"installer_output\BUILD_INFO.txt" echo PyInstaller bootloader: %BOOTLOADER_MODE%
>>"installer_output\BUILD_INFO.txt" echo Packaging: onedir
>>"installer_output\BUILD_INFO.txt" echo UPX: disabled
>>"installer_output\BUILD_INFO.txt" echo Obfuscation: none
>>"installer_output\BUILD_INFO.txt" echo SHA-256 checksums: generated
>>"installer_output\BUILD_INFO.txt" echo Note: Antivirus detections are vendor-specific and cannot be guaranteed to disappear without vendor review or code signing.


echo.
echo ============================================================
echo BUILD COMPLETE
echo ============================================================
echo.
echo Installer:
echo   %CD%\installer_output\UniversalMediaDownloader_Setup_v%UMD_BUILD_VERSION%.exe
echo.
echo Packaging:
echo   onedir (standard Windows application layout)
echo.
echo If a security vendor still flags the release, submit the exact
necho SHA-256 and sample to that vendor for false-positive review.
echo.
pause
endlocal
exit /b 0

:FAIL
echo.
echo ============================================================
echo BUILD FAILED
echo ============================================================
pause
endlocal
exit /b 1
