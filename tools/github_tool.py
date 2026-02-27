from github import Github

MAX_REPO_CHARS = 20000  # Prevent token overflow

def fetch_repo_content(repo_url, github_token):

    g = Github(github_token)
    repo_name = repo_url.split("github.com/")[1]
    repo = g.get_repo(repo_name)

    contents = repo.get_contents("")
    full_content = ""

    while contents:
        file_content = contents.pop(0)

        if file_content.type == "dir":
            contents.extend(repo.get_contents(file_content.path))

        elif file_content.type == "file":

            # Only read safe files
            if file_content.name.endswith((".py", ".md", ".txt")):

                try:
                    if file_content.encoding == "base64":
                        decoded = file_content.decoded_content.decode(
                            "utf-8", errors="ignore"
                        )

                        full_content += f"\n\nFile: {file_content.path}\n"
                        full_content += decoded

                        # Stop if repo too large
                        if len(full_content) > MAX_REPO_CHARS:
                            break

                except:
                    pass

    return full_content[:MAX_REPO_CHARS]
