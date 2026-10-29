@echo off
setlocal
pushd "%~dp0"
set "MHFZ_BUILDER_PROJECT=%~dp0"
if exist "dist\desktop-ai-beta\mhfz-ai-quest-builder-desktop.exe" (
  start "" "dist\desktop-ai-beta\mhfz-ai-quest-builder-desktop.exe"
) else (
  echo The CQ Editor AI beta has not been built. See README.md.
  echo Developers can use Dev.cmd for the terminal diagnostic interface.
  pause
)
popd
endlocal
