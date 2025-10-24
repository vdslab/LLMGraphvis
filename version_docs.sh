#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# Check if a version date is provided as an argument
if [ -z "$1" ]; then
  echo "Usage: $0 <YYYY-MM-DD>"
  exit 1
fi

NEW_VERSION_DATE=$1
PLUGIN_ID="specification"
VERSIONS_FILE="versions.json"

echo "Creating new version: $NEW_VERSION_DATE for plugin: $PLUGIN_ID"

# Create the new Docusaurus version
npm run docusaurus docs:version "$NEW_VERSION_DATE" --plugin-id "$PLUGIN_ID"

echo "Version $NEW_VERSION_DATE created successfully."

# Use jq to add the new version and sort the array
if command -v jq &> /dev/null
then
    echo "Updating and sorting versions.json using jq..."
    # Add the new version if it's not already there, then sort and reverse
    jq --arg date "$NEW_VERSION_DATE" '. | if index($date) | not then . + [$date] else . end | sort | reverse' "$VERSIONS_FILE" > "${VERSIONS_FILE}.tmp"
    mv "${VERSIONS_FILE}.tmp" "$VERSIONS_FILE"
    echo "$VERSIONS_FILE updated and sorted."
else
    echo "jq is not installed. Please install jq for automatic updating and sorting of versions.json."
    echo "Versions in versions.json might not be chronologically sorted."
    # Fallback for adding without sorting if jq is not available
    CURRENT_VERSIONS=$(cat "$VERSIONS_FILE")
    if ! echo "$CURRENT_VERSIONS" | grep -q "\"$NEW_VERSION_DATE\""; then
        UPDATED_VERSIONS=$(echo "$CURRENT_VERSIONS" | sed -E "s/\\\]$/  \"$NEW_VERSION_DATE\"\\n\\\]/")
        echo "$UPDATED_VERSIONS" > "$VERSIONS_FILE"
        echo "$VERSIONS_FILE updated with $NEW_VERSION_DATE (unsorted)."
    else
        echo "Version $NEW_VERSION_DATE already exists in $VERSIONS_FILE."
    fi
fi

echo "Script finished."