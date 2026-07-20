#!/usr/bin/env sh
# install.sh - explicit-source installer for qwen-launcher 0.1 on Linux.
#
# IMPLEMENTATION_SPEC.md sections 5.10-5.12 require a small, idempotent installer that verifies
# prerequisites, pins uv 0.11.28 through its official versioned installer, and installs the tool
# with CPython 3.12.13. Exactly one source remains mandatory so an install never changes version or
# trust boundary because of an implicit default.
set -eu

UV_VERSION="0.11.28"
PYTHON_VERSION="3.12.13"
REPO_URL="https://github.com/tommasonovelli/qwen-launcher.git"
UV_INSTALLER_URL="https://astral.sh/uv/${UV_VERSION}/install.sh"

# Print an actionable error to stderr without a traceback and exit with a contractual code
# (spec section 5.11: 2 = invalid input/CLI, 1 = expected operational failure).
die() {
    printf 'install.sh: %s\n' "$1" >&2
    exit "$2"
}

usage() {
    cat >&2 <<EOF
Usage: install.sh (--wheel PATH --sha256 HEX | --git-commit HEX | --pypi-version VERSION)

Exactly one explicit source is required; no version is selected implicitly.

  --wheel PATH --sha256 HEX   install a local wheel after verifying its 64-hex SHA-256
  --git-commit HEX            install from a 40-hex commit of ${REPO_URL}
  --pypi-version VERSION      install an explicit version that exists on PyPI
EOF
}

wheel=""
sha256=""
git_commit=""
pypi_version=""

while [ "$#" -gt 0 ]; do
    key="$1"
    case "$key" in
        --wheel | --sha256 | --git-commit | --pypi-version)
            [ "$#" -ge 2 ] || die "missing value for $key" 2
            value="$2"
            shift 2
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        *)
            usage
            die "unknown argument: $key" 2
            ;;
    esac
    case "$key" in
        --wheel) wheel="$value" ;;
        --sha256) sha256="$value" ;;
        --git-commit) git_commit="$value" ;;
        --pypi-version) pypi_version="$value" ;;
    esac
done

# Require exactly one explicit source. A missing source is an input error, never a silent PyPI
# default, so rerunning the installer cannot unexpectedly select a newer release.
source_count=0
if [ -n "$wheel" ]; then source_count=$((source_count + 1)); fi
if [ -n "$git_commit" ]; then source_count=$((source_count + 1)); fi
if [ -n "$pypi_version" ]; then source_count=$((source_count + 1)); fi
if [ "$source_count" -ne 1 ]; then
    usage
    die "select exactly one explicit install source (got $source_count)" 2
fi

is_hex() {
    # Return success when $1 is exactly $2 lowercase/uppercase hexadecimal characters.
    printf '%s' "$1" | grep -Eq "^[0-9a-fA-F]{$2}\$"
}

if [ -n "$wheel" ]; then
    [ -n "$sha256" ] || die "--wheel requires --sha256 with the wheel's SHA-256" 2
    is_hex "$sha256" 64 || die "--sha256 must be 64 hexadecimal characters" 2
elif [ -n "$sha256" ]; then
    die "--sha256 is only valid together with --wheel" 2
fi

if [ -n "$git_commit" ]; then
    is_hex "$git_commit" 40 || die "--git-commit must be a full 40-character commit hash" 2
fi

# Verify the supported platform and architecture before any download or install (spec section
# 5.10: no elevation, actionable prerequisite errors).
os="$(uname -s)"
arch="$(uname -m)"
[ "$os" = "Linux" ] || die "unsupported OS '$os'; this installer targets Linux x86-64" 1
case "$arch" in
    x86_64 | amd64) ;;
    *) die "unsupported architecture '$arch'; x86-64 is required" 1 ;;
esac

if [ -n "$wheel" ]; then
    [ -f "$wheel" ] || die "wheel not found: $wheel" 1
    if command -v sha256sum >/dev/null 2>&1; then
        actual_sha="$(sha256sum "$wheel" | cut -d ' ' -f 1)"
    elif command -v shasum >/dev/null 2>&1; then
        actual_sha="$(shasum -a 256 "$wheel" | cut -d ' ' -f 1)"
    else
        die "no SHA-256 tool found; install sha256sum or shasum" 1
    fi
    expected_lower="$(printf '%s' "$sha256" | tr 'A-F' 'a-f')"
    actual_lower="$(printf '%s' "$actual_sha" | tr 'A-F' 'a-f')"
    [ "$expected_lower" = "$actual_lower" ] ||
        die "SHA-256 mismatch for $wheel (expected $expected_lower, got $actual_lower)" 1
fi

# Ensure exactly uv 0.11.28. Reuse an already-matching uv to keep reruns cheap and offline;
# otherwise download the official versioned installer to a temporary file and run it directly,
# with TLS enforced and never through eval or a pipe to a shell.
uv_dir="${UV_INSTALL_DIR:-$HOME/.local/bin}"
uv_matches() {
    command -v "$1" >/dev/null 2>&1 &&
        "$1" --version 2>/dev/null | grep -Eq '^uv 0\.11\.28([[:space:]]|$)'
}

if uv_matches uv; then
    uv_bin="uv"
else
    command -v curl >/dev/null 2>&1 || die "curl is required to download uv ${UV_VERSION}" 1
    command -v mktemp >/dev/null 2>&1 || die "mktemp is required to install uv" 1
    installer_tmp="$(mktemp)" || die "could not create a temporary installer file" 1
    trap 'rm -f "$installer_tmp"' EXIT
    curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error \
        "$UV_INSTALLER_URL" --output "$installer_tmp" ||
        die "could not download the official uv ${UV_VERSION} installer" 1
    UV_INSTALL_DIR="$uv_dir" sh "$installer_tmp" || die "the uv ${UV_VERSION} installer failed" 1
    rm -f "$installer_tmp"
    trap - EXIT
    if uv_matches uv; then
        uv_bin="uv"
    elif uv_matches "$uv_dir/uv"; then
        uv_bin="$uv_dir/uv"
    else
        die "uv ${UV_VERSION} is not available after running its installer" 1
    fi
fi

# Build the single explicit install target and install the tool with the pinned Python.
if [ -n "$wheel" ]; then
    target="$wheel"
elif [ -n "$git_commit" ]; then
    target="qwen-launcher @ git+${REPO_URL}@${git_commit}"
else
    target="qwen-launcher==${pypi_version}"
fi

"$uv_bin" tool install --force --python "$PYTHON_VERSION" "$target" ||
    die "uv could not install the tool from the requested source" 1

printf 'install.sh: installed qwen-launcher with uv %s and Python %s.\n' \
    "$UV_VERSION" "$PYTHON_VERSION"
printf 'install.sh: re-running this installer is safe.\n'
printf 'install.sh: to remove the tool later, run: uv tool uninstall qwen-launcher\n'
printf 'install.sh: to remove managed data, run: qwen-launcher uninstall\n'
