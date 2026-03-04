import re
import warnings
from github import Github, GithubException

MAX_REPO_CHARS = 20000  # Prevent token overflow
GITHUB_TIMEOUT = 15     # Seconds before request times out


def parse_github_repo_name(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL robustly.

    Handles trailing slashes, .git suffix, branch/tree paths,
    and validates that the URL is actually a GitHub URL.
    """
    url = repo_url.strip().rstrip("/")

    if not re.search(r"github\.com", url, re.IGNORECASE):
        raise ValueError(f"Not a valid GitHub URL: {repo_url!r}")

    # Remove .git suffix
    url = re.sub(r"\.git$", "", url)

    # Extract path after github.com
    match = re.search(r"github\.com[/:]([^/]+/[^/]+)", url)
    if not match:
        raise ValueError(
            f"Could not extract owner/repo from GitHub URL: {repo_url!r}. "
            "Expected format: https://github.com/owner/repo"
        )

    # Strip any trailing branch/tree path (e.g. /tree/main or /blob/main/...)
    repo_path = match.group(1)
    repo_path = re.split(r"/(tree|blob)/", repo_path)[0]

    return repo_path


def fetch_repo_content(repo_url: str, github_token: str) -> str:
    """Fetch readable file contents from a GitHub repository.

    Returns up to MAX_REPO_CHARS characters of combined file text,
    each file wrapped in triple-backtick delimiters to reduce prompt
    injection risk.

    Raises:
        ValueError: If the URL is not a valid GitHub repo URL.
        GithubException: On 401/403/404 API errors (propagated so caller
            can surface a user-friendly message).
    """
    repo_name = parse_github_repo_name(repo_url)

    g = Github(github_token, timeout=GITHUB_TIMEOUT)

    try:
        repo = g.get_repo(repo_name)
    except GithubException as exc:
        if exc.status == 404:
            raise GithubException(
                exc.status,
                {"message": f"Repository '{repo_name}' not found. Check the URL and your token permissions."},
            ) from exc
        if exc.status in (401, 403):
            raise GithubException(
                exc.status,
                {"message": "GitHub API access denied. Check your token or rate-limit status."},
            ) from exc
        raise

    contents = list(repo.get_contents(""))
    full_content = ""
    skipped = 0

    while contents:
        file_content = contents.pop(0)

        if file_content.type == "dir":
            try:
                contents.extend(repo.get_contents(file_content.path))
            except GithubException as exc:
                warnings.warn(f"Could not read directory '{file_content.path}': {exc}")
            continue

        if file_content.type != "file":
            continue

        if not file_content.name.endswith((".py", ".md", ".txt")):
            continue

        try:
            if file_content.encoding != "base64":
                skipped += 1
                warnings.warn(
                    f"Skipped '{file_content.path}': unsupported encoding "
                    f"'{file_content.encoding}'"
                )
                continue

            decoded = file_content.decoded_content.decode("utf-8", errors="ignore")
            full_content += (
                f"\n\n```\n# File: {file_content.path}\n{decoded}\n```"
            )

            if len(full_content) > MAX_REPO_CHARS:
                break

        except GithubException as exc:
            if exc.status in (401, 403):
                raise GithubException(
                    exc.status,
                    {"message": "GitHub rate limit or access error while reading files."},
                ) from exc
            skipped += 1
            warnings.warn(f"Skipped '{file_content.path}': GitHub error {exc.status}")
        except Exception as exc:
            skipped += 1
            warnings.warn(f"Skipped '{file_content.path}': {exc}")

    if skipped:
        warnings.warn(f"Total files skipped due to errors: {skipped}")

    return full_content[:MAX_REPO_CHARS]
