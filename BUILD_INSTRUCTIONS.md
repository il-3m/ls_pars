# Unified Parser - Build Instructions

## Problem Solved: Playwright Browsers in EXE

The issue was that PyInstaller's one-file mode extracts everything to a temporary folder (`_MEIxxxxx`) at runtime, but Playwright browsers were being looked for in that temp folder instead of the permanent cache location.

## Solution

The updated code now:
1. **Uses permanent browser cache**: Sets `PLAYWRIGHT_BROWSERS_PATH` to `%USERPROFILE%\.cache\ms-playwright` instead of the temp folder
2. **Auto-installs on first run**: If browsers are not found, Playwright will automatically download them (~150MB) on the first run
3. **Better error messages**: Clear instructions if installation fails

## How to Build

### On Windows (with Python 3.8-3.12):

1. **Copy these files to one folder:**
   - `unified_parser.py`
   - `eis_parser.py`
   - `link_finder.py`
   - `requirements.txt`
   - `build_exe.bat`

2. **Run `build_exe.bat`** (double-click or from command line)

3. **Wait 5-15 minutes** for:
   - Dependencies installation
   - Playwright Chromium download (~150MB)
   - EXE compilation

4. **Find your EXE** in `export\Unified_Parser.exe`

## First Run on Target Computer

When you run the EXE on a computer without Python:

1. **First launch** (1-2 minutes):
   - Playwright detects missing browsers
   - Automatically downloads Chromium (~150MB)
   - Saves to `%USERPROFILE%\.cache\ms-playwright`
   - You'll see progress in the console

2. **Subsequent launches**: Fast! Browsers are cached permanently.

## Requirements on Target Computer

✅ **Required:**
- Windows 10/11
- Google Chrome installed (for Selenium part - link finding)
- Internet connection (for first run + actual parsing)

❌ **NOT required:**
- Python
- Manual Playwright installation
- Any special configuration

## Troubleshooting

### "Executable doesn't exist" error on first run:
- **Normal behavior!** Wait 1-2 minutes for auto-installation
- Ensure internet connection is active
- Check firewall/antivirus isn't blocking the download

### Build fails with pandas/numpy errors:
- You're likely using Python 3.13 which lacks pre-built wheels
- **Solution:** Install Python 3.11 or 3.12 from python.org
- Or try: `pip install pandas --only-binary :all:`

### EXE is too large (>300MB):
- This is normal - includes PyQt5, pandas, and Playwright dependencies
- The browsers are cached separately on first run, not bundled

### Antivirus blocks EXE:
- False positive common with PyInstaller apps
- Add exception or sign the EXE with a certificate

## File Sizes

- **Source files**: ~200KB
- **EXE file**: ~50-80MB (compressed)
- **First run download**: ~150MB (Playwright Chromium)
- **Total disk usage**: ~200-250MB

## Technical Details

### Why not bundle browsers inside EXE?

1. **Size**: Would make EXE 400MB+ (slow to distribute)
2. **Temp folder issues**: PyInstaller one-file mode extracts to temp, causing path problems
3. **Updates**: Separate cache allows Playwright to update browsers independently

### How it works:

```
First Run:
EXE starts → Checks %USERPROFILE%\.cache\ms-playwright → Not found → 
Downloads Chromium → Saves to cache → Runs parser

Second Run:
EXE starts → Checks %USERPROFILE%\.cache\ms-playwright → Found! → 
Runs parser immediately
```

## Support

If issues persist:
1. Check `unified_parser_log.txt` for detailed logs
2. Run EXE from command line to see console output
3. Ensure no corporate proxy/firewall blocking downloads
