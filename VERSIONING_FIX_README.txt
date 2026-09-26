Universal Media Downloader - V4.4.0 Version Fix
================================================

This package updates the V4.4.0 fallback/default version values so a local
build reports 4.4.0 instead of the old 4.3.2 value.

Files updated:
- BUILD_INSTALLER.bat
- UniversalMediaDownloader.iss
- main.py
- .github/workflows/build-installer.yml

NEXT:
1. Run BUILD_INSTALLER.bat locally.
2. Install the resulting installer.
3. Open the app and confirm it says:
   Version 4.4.0 • Build 2026
4. Only after that, commit these source changes to GitHub and create/replace
   the release asset using the corrected build.

Do not create a new release until the local version check passes.
