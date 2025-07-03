# Release Scripts

## Creating a New Release

To create a new release, use the `release.sh` script:

```bash
./scripts/release.sh 1.2.3
```

For pre-releases:
```bash
./scripts/release.sh 1.2.3-beta.1
```

This script will:
1. Update the version in `manifest.json`
2. Commit the change
3. Create a git tag
4. Push everything to GitHub
5. Trigger GitHub Actions to create the release with zip files

## Manual Release Process

If you prefer to do it manually:

1. Update version in `manifest.json`
2. Commit: `git commit -am "Bump version to X.Y.Z"`
3. Tag: `git tag -a vX.Y.Z -m "Release version X.Y.Z"`
4. Push: `git push origin main --tags`

## GitHub Actions

The `.github/workflows/release.yml` workflow will automatically:
- Validate the integration with HACS
- Create two zip files:
  - `phantom-vX.Y.Z.zip` - For manual installation (includes outer directory)
  - `phantom-hacs-vX.Y.Z.zip` - For HACS (no outer directory)
- Generate a changelog from git commits
- Create a GitHub release with installation instructions

## Version Format

Versions should follow semantic versioning:
- `MAJOR.MINOR.PATCH` for stable releases (e.g., `1.2.3`)
- `MAJOR.MINOR.PATCH-PRERELEASE` for pre-releases (e.g., `1.2.3-beta.1`)

Pre-releases will be marked as such in GitHub releases.