#!/bin/bash
# Script to create a new release

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if we're in the project root
if [ ! -f "custom_components/phantom/manifest.json" ]; then
    print_error "Must be run from project root"
    exit 1
fi

# Check if git is clean
if [ -n "$(git status --porcelain)" ]; then
    print_error "Working directory is not clean. Please commit or stash changes."
    exit 1
fi

# Check if we're on main branch
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" != "main" ]; then
    print_info "Warning: You're not on the main branch (current: $CURRENT_BRANCH)"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Update manifest.json
print_info "Updating manifest.json to version $VERSION..."
sed -i.bak "s/\"version\": \"[^\"]*\"/\"version\": \"$VERSION\"/" custom_components/phantom/manifest.json
rm custom_components/phantom/manifest.json.bak

# Show the change
print_info "Updated manifest.json:"
grep '"version"' custom_components/phantom/manifest.json

# Commit the change
print_info "Committing version bump..."
git add custom_components/phantom/manifest.json
git commit -m "Bump version to $VERSION"

# Create tag
print_info "Creating tag v$VERSION..."
git tag -a "v$VERSION" -m "Release version $VERSION"

# Push changes and tag
print_info "Pushing to remote..."
git push origin main
git push origin "v$VERSION"

print_success "✓ Version $VERSION has been released!"
print_info "GitHub Actions will now create the release with zip files."
print_info "Check the Actions tab in your repository to monitor progress."