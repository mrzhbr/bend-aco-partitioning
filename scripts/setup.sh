#!/usr/bin/env bash
# Project-local installation of the official, pinned Bend 2 release.
set -euo pipefail
cd "$(dirname "$0")/.."
version=2.0.37
if [[ -x .tools/bend/bin/bend ]] && [[ "$(.tools/bend/bin/bend version)" == "bend $version" ]]; then
	echo "Bend $version already installed locally."
	exit 0
fi
case "$(uname -s)-$(uname -m)" in
Darwin-arm64)
	platform=darwin-arm64
	sha=846d25ccf0c12d5d1e5e648c0b3ba4c8397fdb852812ac00ef8135998f8e194b
	;;
Darwin-x86_64)
	platform=darwin-x64
	sha=93eea3f54b7b91f28ea15a1b9f2d825afa58c1fcd417c11024a62f8c3506b813
	;;
Linux-aarch64)
	platform=linux-arm64
	sha=b65d452e5c68a4c486e353220d4298ba5d76f535db47109a7d76ffdf72efafb1
	;;
Linux-x86_64)
	platform=linux-x64
	sha=84c32465a39bc9ac315eade23f470cb8db03153dc860f89564fcfec153c3e445
	;;
*)
	echo "Unsupported platform. See https://github.com/bendlang/bend/releases/tag/v$version" >&2
	exit 1
	;;
esac
mkdir -p .tools
archive=$(mktemp .tools/bend-download.XXXXXX)
trap 'rm -f "$archive"' EXIT
curl --fail --location --silent --show-error \
	"https://github.com/bendlang/bend/releases/download/v$version/bend-$version-$platform.tar.gz" \
	-o "$archive"
if command -v shasum >/dev/null; then
	printf '%s  %s\n' "$sha" "$archive" | shasum -a 256 -c -
else
	printf '%s  %s\n' "$sha" "$archive" | sha256sum -c -
fi
tar -xzf "$archive" -C .tools
.tools/bend/bin/bend version
