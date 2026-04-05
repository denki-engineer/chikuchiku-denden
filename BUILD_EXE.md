# Build EXE

The default datasets in `defaults/` are bundled into the executable build.

```powershell
pip install -r requirements-build.txt
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

The build script creates an `onedir` build so the app can run without one-file extraction issues on Windows. The app entry point is `dist/chikuchiku_denden/chikuchiku_denden.exe`.

If the existing output folder is locked, a timestamped fallback folder is created under `dist/`.

For distribution, use the folder created under `release/`.
Hand off the whole `release/chikuchiku_denden` folder, including `_internal`.
