# Requires: gh auth login
# Creates the public repo if needed, then pushes this public-lite package.
$ErrorActionPreference = "Stop"
gh auth status
gh repo create kyal102/chipgate --public --source . --remote origin --push --description "Public-safe JARVI3 Chip DesignGuard Lite demo package"
