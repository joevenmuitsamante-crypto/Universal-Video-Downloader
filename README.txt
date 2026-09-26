UNIVERSAL MEDIA DOWNLOADER V4.3.2
Version 4.3.2 | Build 2026

DISTRIBUTION
- The normal release file is UniversalMediaDownloader_Setup_v4.3.2.exe.
- Distribute ONLY the generated installer to end users.
- Do not distribute this source folder, the QR source image, or build files.

INSTALLER DESIGN
- The main application is a PyInstaller one-file EXE installed under Program Files.
- The GCash QR, PayPal QR, and app logo are embedded inside the application; there are no separate QR images in the installed app.
- yt-dlp.exe and ffmpeg.exe are installed into the user's LocalAppData app-data folder and hidden, allowing automatic component updates without administrator rights.
- A Start Menu shortcut is created automatically. A desktop shortcut is optional during setup.

FEATURES
- Universal URL downloader interface
- YouTube, TikTok, Instagram, Facebook and other yt-dlp-supported URLs
- Best Available / 8K / 4K / 1080p / 720p / 480p / 360p (quality choices are enabled based on source metadata)
- Audio Only / MP3
- Download speed modes: Auto 4 / Fast 8 / Maximum 16 concurrent fragments
- Preview metadata and thumbnail
- Download folder selection
- Progress and download history
- Dark/light appearance
- Optional GCash support section
- Manual yt-dlp + FFmpeg update detection from Settings
- No command prompt window during normal use

BUILD OPTION A — LOCAL WINDOWS PC
1. Install Python 3.11+ and enable PATH.
2. Install Inno Setup 6.
3. Run BUILD_INSTALLER.bat.
4. The finished installer appears in installer_output.

BUILD OPTION B — GITHUB ACTIONS
- The project includes .github/workflows/build-installer.yml.
- Upload/push the project to a GitHub repository.
- Open Actions → Build Windows Installer → Run workflow.
- Download the generated installer artifact.

BUILD REQUIREMENTS
- Windows 10/11
- Internet connection during build to bundle the current yt-dlp Windows binary and latest stable FFmpeg Windows essentials build

SECURITY NOTE
The installer makes the app much harder to casually inspect or modify, but no Windows application can be made impossible to reverse-engineer or change by a determined user with sufficient access to the machine.

V4.3.2 RESPONSIVE WINDOW
- Minimum window size is reduced to fit 14-inch and high-DPI laptop screens.
- The main content is vertically scrollable, so the preview and controls remain whole instead of being clipped.
- The preview thumbnail has stable bounds and resizes without being cropped.

V4.3.2 QUALITY OPTIONS
- Best Available, 8K, 4K, 1080p, 720p, 480p, 360p, and Audio Only are available.
- Resolution choices are enabled only when the source metadata reports that resolution or higher.

V4.3.2 SECURITY BUILD
- Uses the standard official PyInstaller wheel.
- Uses onedir packaging instead of a self-extracting one-file EXE.
- UPX is disabled. No obfuscation, encryption, anti-analysis, or antivirus-evasion code is used.
- This is a conventional build intended to reduce unnecessary heuristic triggers, but no build can guarantee that every antivirus/ML engine will classify it as clean.
- VirusTotal aggregates third-party vendor verdicts. Remaining vendor detections should be submitted to the specific vendor for false-positive review.

V4.3.2 SUPPORT QR
- The GCash QR and PayPal QR are embedded directly in the application.
- The PayPal QR is the exact image supplied for this release.

V4.3.2 BUNDLED COMPONENTS
- yt-dlp and FFmpeg are fetched during the Windows build and placed into the installer.
- A fresh installation therefore has both components available on first launch without an initial component download.


V4.3.2 UI / DOWNLOAD UPGRADES
- Smaller fixed preview area with a compact thumbnail sized for clear identification without dominating the page.
- Preview title and metadata use transparent backgrounds.
- Added a dedicated Support menu with GCash and PayPal QR codes and prominent "100% FREE / SUPPORT IS OPTIONAL" messaging.
- Important page text is larger and bold.
- Download history now keeps URL, folder, file path, date, quality, resolution, and detected file size; double-click an entry for Open File / Open Folder / Download Again.
- Added sequential download queue with + Add URL.
- Video quality choices: Best, 4K, 2K, Full HD, HD, 480p, 360p.
- Audio quality choices: Best, 320 kbps, 256 kbps, 128 kbps.
- Unsupported quality choices are disabled after media detection.
- Added General, Downloads, Appearance, and Behavior settings.
- Added GitHub Releases app-version checking. GITHUB_REPO is configured for joevenmuitsamante-crypto/Universal-Video-Downloader.
- Added a tag-based GitHub Actions release workflow that builds the Windows installer and attaches it to a GitHub Release.


AUTOMATIC GITHUB RELEASES
- Repository: https://github.com/joevenmuitsamante-crypto/Universal-Video-Downloader
- The app checks the latest GitHub Release from this repository.
- To publish a new version, create and push a semantic version tag such as v4.4.0.
- GitHub Actions reads the tag version, builds the Windows installer, calculates its SHA-256 checksum, and publishes the installer to the GitHub Release automatically.
- The application embeds the build version from UMD_BUILD_VERSION, so the installed app and GitHub release stay on the same version number.
- Manual builds can still use the default 4.3.2 version or provide UMD_BUILD_VERSION before running BUILD_INSTALLER.bat.
- GitHub Actions must have permission to write repository contents. The included release workflow requests contents: write.
