#!/bin/bash
# Universal script to create a new release for any Home Assistant custom component

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_error() {
    echo -e "${RED}Error: $1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_info() {
    echo -e "${YELLOW}$1${NC}"
}

print_debug() {
    echo -e "${BLUE}$1${NC}"
}

# Function to detect integration name
detect_integration() {
    if [ ! -d "custom_components" ]; then
        print_error "custom_components directory not found"
        return 1
    fi

    local integrations=(custom_components/*)
    if [ ${#integrations[@]} -eq 0 ]; then
        print_error "No integrations found in custom_components/"
        return 1
    fi

    if [ ${#integrations[@]} -gt 1 ]; then
        print_info "Multiple integrations found:"
        for integration in "${integrations[@]}"; do
            local name=$(basename "$integration")
            echo "  - $name"
        done

        read -p "Enter integration name to release: " -r INTEGRATION_NAME
        if [ ! -d "custom_components/$INTEGRATION_NAME" ]; then
            print_error "Integration '$INTEGRATION_NAME' not found"
            return 1
        fi
    else
        INTEGRATION_NAME=$(basename "${integrations[0]}")
    fi

    print_debug "Detected integration: $INTEGRATION_NAME"
    return 0
}

# Function to get display name for integration
get_display_name() {
    local name="$1"
    # Convert underscores to spaces and title case
    echo "$name" | sed 's/_/ /g' | sed 's/\b\w/\U&/g'
}

# Check if version argument is provided
if [ -z "$1" ]; then
    print_error "Version number required"
    echo "Usage: $0 <version>"
    echo "Example: $0 1.2.3"
    echo "Example: $0 1.2.3-beta.1"
    exit 1
fi

VERSION=$1

# Validate version format
if ! [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$ ]]; then
    print_error "Invalid version format"
    echo "Version must be in format X.Y.Z or X.Y.Z-suffix"
    exit 1
fi

# Detect integration
if ! detect_integration; then
    exit 1
fi

DISPLAY_NAME=$(get_display_name "$INTEGRATION_NAME")
MANIFEST_PATH="custom_components/$INTEGRATION_NAME/manifest.json"

print_info "Project: $DISPLAY_NAME"
print_info "Integration: $INTEGRATION_NAME"
print_info "Version: $VERSION"
echo

# Check if manifest exists
if [ ! -f "$MANIFEST_PATH" ]; then
    print_error "Manifest not found at $MANIFEST_PATH"
    exit 1
fi

# Check if git is available
if ! command -v git &> /dev/null; then
    print_error "Git is not installed or not in PATH"
    exit 1
fi

# Check if we're in a git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    print_error "Not in a git repository"
    exit 1
fi

# Check if git is clean
if [ -n "$(git status --porcelain)" ]; then
    print_error "Working directory is not clean. Please commit or stash changes."
    git status --short
    exit 1
fi

# Check current branch
CURRENT_BRANCH=$(git branch --show-current)
print_debug "Current branch: $CURRENT_BRANCH"

if [ "$CURRENT_BRANCH" != "main" ] && [ "$CURRENT_BRANCH" != "master" ]; then
    print_info "Warning: You're not on the main/master branch (current: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if tag already exists
if git tag -l | grep -q "^v$VERSION$"; then
    print_error "Tag v$VERSION already exists"
    exit 1
fi

# Update manifest.json
print_info "Updating $MANIFEST_PATH to version $VERSION..."

# Create backup
cp "$MANIFEST_PATH" "$MANIFEST_PATH.bak"

# Update version using sed (works on both macOS and Linux)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$MANIFEST_PATH"
else
    # Linux
    sed -i "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" "$MANIFEST_PATH"
fi

# Verify the update worked
if ! grep -q "\"version\": \"$VERSION\"" "$MANIFEST_PATH"; then
    print_error "Failed to update version in manifest.json"
    mv "$MANIFEST_PATH.bak" "$MANIFEST_PATH"
    exit 1
fi

# Remove backup
rm "$MANIFEST_PATH.bak"

# Show the change
print_info "Updated manifest.json:"
grep '"version"' "$MANIFEST_PATH"

# Commit the change
print_info "Committing version bump..."
git add "$MANIFEST_PATH"
git commit -m "Bump version to $VERSION"

# Create tag
print_info "Creating tag v$VERSION..."
git tag -a "v$VERSION" -m "Release $DISPLAY_NAME version $VERSION"

# Show what will be pushed
echo
print_info "Ready to push:"
print_debug "  Commit: $(git log -1 --oneline)"
print_debug "  Tag: v$VERSION"
print_debug "  Branch: $CURRENT_BRANCH"

# Confirm push
read -p "Push changes and tag to remote? (Y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Nn]$ ]]; then
    print_info "Changes committed locally but not pushed."
    print_info "To push later, run:"
    echo "  git push origin $CURRENT_BRANCH"
    echo "  git push origin v$VERSION"
    exit 0
fi

# Push changes and tag
print_info "Pushing to remote..."
if git push origin "$CURRENT_BRANCH"; then
    print_success "✓ Pushed commits to $CURRENT_BRANCH"
else
    print_error "Failed to push commits"
    exit 1
fi

if git push origin "v$VERSION"; then
    print_success "✓ Pushed tag v$VERSION"
else
    print_error "Failed to push tag"
    exit 1
fi

echo
print_success "🚀 Version $VERSION has been released!"
print_info "Integration: $DISPLAY_NAME"
print_info "Tag: v$VERSION"
echo
print_info "GitHub Actions will now create the release with zip files."
print_info "Check the Actions tab in your repository to monitor progress:"
print_debug "  https://github.com/$(git config --get remote.origin.url | sed 's/.*github.com[:/]\([^/]*\/[^/]*\).*/\1/' | sed 's/\.git$//')/actions"