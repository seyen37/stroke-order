@echo off
REM ============================================================
REM stroke-order session-close check (double-click to run)
REM 1) fetch-first SOP  2) full pytest  3) commit only if green
REM NOTE: ASCII-only on purpose -- cmd.exe parses this file in
REM       the OEM codepage; Chinese text lives in the UTF-8
REM       commit-message file read via "git commit -F".
REM ============================================================
chcp 65001 >nul
cd /d "%~dp0"
call .venv\Scripts\activate.bat

echo.
echo === [1/3] SOP-0 fetch-first ===
git fetch origin
git log HEAD..origin/main --oneline
echo (If commits are listed above: cross-machine changes exist.
echo  Run "git pull" first, then re-run this script.)
echo.

echo === [2/3] full pytest ===
python -m pytest tests/ -q
if errorlevel 1 (
    echo.
    echo ******** TESTS FAILED -- NOT committing. ********
    echo ******** Paste the failures above to Claude. ********
    pause
    exit /b 1
)

echo.
echo === [3/3] tests green -- committing ===
git add -A
git status -s
git commit -F "docs\_commit_msg\2026-07-11_01.txt"

echo.
echo === done. last 3 commits: ===
git log --oneline -3
echo.
echo Reminder: update README badges (tests count from pytest above,
echo           version badge to 0.14.134).
pause
