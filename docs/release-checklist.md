# Release Checklist

## Before commit

- Restore `assets/GIT.zip` if it should remain in the repository
- Confirm no confidential files are present
- Confirm `sample_data/` contains only public sample files
- Confirm `defaults/` contains only safe demonstration data

## Do not commit

- `venv/`
- `__pycache__/`
- `build/`
- `dist/`
- executable payloads under `release/`
- local CSV exports from actual work

## Recommended checks

```powershell
git status
git diff -- README.md README_ja.md LICENSE .gitignore
git diff -- app.py io_utils.py ui_components.py run_exe.py build_exe.ps1
```

## Recommended staging approach

```powershell
git add README.md README_ja.md LICENSE .gitignore
git add app.py run_exe.py calculators.py io_utils.py models.py resource_paths.py ui_components.py
git add build_exe.ps1 chikuchiku_denden.spec BUILD_EXE.md RELEASE_README.txt
git add requirements.txt requirements-build.txt __init__.py
git add engine defaults docs sample_data tests assets
```

## Before push

- Confirm staged files do not include `__pycache__`
- Confirm staged files do not include `dist/`
- Confirm staged files do not include built release artifacts
- Confirm README screenshots render correctly
- Confirm LICENSE is present
- Confirm executable distribution is prepared separately for GitHub Releases

## GitHub release packaging

Recommended archive name:

- `chikuchiku-denden-win64-v1.0.0.zip`

Recommended command:

```powershell
Compress-Archive -Path .\release\chikuchiku_denden -DestinationPath .\release\chikuchiku-denden-win64-v1.0.0.zip -Force
```
