# HACS Integration

This integration is compatible with HACS (Home Assistant Community Store).

## Configuration

The `hacs.json` file is configured with:
- `"zip_release": true` - HACS will download releases from GitHub
- `"filename": "phantom.zip"` - The specific file HACS looks for

## Release Process

When a new release is created:

1. The GitHub Actions workflow creates multiple zip files:
   - `phantom-vX.Y.Z.zip` - For manual installation (includes outer directory)
   - `phantom-hacs-vX.Y.Z.zip` - HACS format (no outer directory)
   - `phantom.zip` - Copy of HACS format with the filename HACS expects

2. HACS will automatically:
   - Detect new releases via GitHub API
   - Download `phantom.zip` from the release assets
   - Extract it directly to `custom_components/phantom/`

## Adding to HACS

Users can add this integration to HACS as a custom repository:

1. Open HACS in Home Assistant
2. Click the menu (three dots) and select "Custom repositories"
3. Add the repository URL
4. Select "Integration" as the category
5. Click "Add"

Or use the My Home Assistant link:
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=integration-phantom&category=integration)

## Validation

The release workflow includes HACS validation to ensure:
- Manifest format is correct
- Required files are present
- Integration structure is valid

This validation runs before creating the release to prevent issues.