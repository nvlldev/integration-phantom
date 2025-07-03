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
1. Auto-detect your integration name
2. Update the version in the appropriate `manifest.json`
3. Commit the change
4. Create a git tag
5. Push everything to GitHub
6. Trigger GitHub Actions to create the release with zip files

## Manual Release Process

If you prefer to do it manually:

1. Detect your integration name: `ls custom_components/`
2. Update version in `custom_components/[INTEGRATION_NAME]/manifest.json`
3. Commit: `git commit -am "Bump version to X.Y.Z"`
4. Tag: `git tag -a vX.Y.Z -m "Release version X.Y.Z"`
5. Push: `git push origin main --tags`

## GitHub Actions

### Release Workflow

The `.github/workflows/release.yml` workflow will automatically:
- Validate the integration with HACS
- Auto-detect the integration name from your project structure
- Create two zip files:
  - `[INTEGRATION_NAME]-vX.Y.Z.zip` - For manual installation (includes outer directory)
  - `[INTEGRATION_NAME]-hacs-vX.Y.Z.zip` - For HACS (no outer directory)
- Generate a changelog from git commits since the last release
- Create a GitHub release with installation instructions
- Mark pre-releases appropriately based on version format

### Version Bump Workflow

You can also use the GitHub Actions workflow to bump versions:

1. Go to the "Actions" tab in your repository
2. Select "Version Bump" workflow
3. Click "Run workflow"
4. Enter the desired version number
5. The workflow will update the manifest and create a tag

## Version Format

Versions should follow semantic versioning:
- `MAJOR.MINOR.PATCH` for stable releases (e.g., `1.2.3`)
- `MAJOR.MINOR.PATCH-PRERELEASE` for pre-releases (e.g., `1.2.3-beta.1`, `1.2.3-alpha`, `1.2.3-rc.1`)

Pre-releases (any version containing a dash) will be marked as such in GitHub releases.

## Universal Compatibility

These scripts and workflows are designed to work with any Home Assistant custom component project structure:
- Automatically detects integration names (`phantom`, `utility_tariff`, etc.)
- Works with single or multiple integrations in one repository
- Generates appropriate display names (e.g., "Phantom Power Monitoring", "Utility Tariff")
- Creates correctly named zip files for each integration

## File Structure

Your project should follow this structure:
```
repository/
├── custom_components/
│   └── [integration_name]/
│       ├── manifest.json
│       ├── __init__.py
│       └── ...
├── scripts/
│   └── release.sh
├── .github/
│   └── workflows/
│       ├── release.yml
│       └── version-bump.yml
└── RELEASE.md
```

## Troubleshooting

### Common Issues

1. **Script not executable**: Run `chmod +x scripts/release.sh`
2. **Wrong directory**: Run from project root where `custom_components/` exists
3. **Dirty git state**: Commit or stash changes before running
4. **Missing integration**: Ensure `custom_components/[name]/manifest.json` exists

### Debug Information

The release script provides detailed output including:
- Detected integration name and display name
- Current git branch and status
- Changes being made to manifest.json
- Confirmation prompts before pushing

If something goes wrong, the script will show clear error messages and stop before making any permanent changes.