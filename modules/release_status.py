#!/usr/bin/env python

missing_modules = []
try:
    import requests
except:
    missing_modules.append("requests")
import json
import os
import re
import sys
from dotenv import load_dotenv

try:
    import semantic_version
except:
    missing_modules.append("semantic_version")

if len(missing_modules) > 0:
    print("This requires python libraries to work; try:")
    for a_module in missing_modules:
        print("    pip install {}".format(a_module))
    sys.exit(1)


def findReleaseItems(repo, release_branch, tag_dict, session):
    #
    # This loads the commits since the last release and gets their associated PRs and scans those for release_type: [xyz]
    # Any X or Y changes also get captured for bullhorn release notes
    #
    response = session.get(
        f'https://api.github.com/repos/ansible/{repo}/compare/{tag_dict["tag"]}...{release_branch}'
    )
    commit_data = response.json()
    commit_shas = []
    tag_dict["branch ahead by commits"] = commit_data["ahead_by"]
    tag_dict["commits"] = []
    for commit in commit_data["commits"]:
        tag_dict["commits"].append(
            {
                "sha": commit["sha"][0:9],
                "author": commit["author"]["login"],
                "msg": commit["commit"]["message"],
            }
        )
        commit_shas.append(commit["sha"])

    tag_dict["associated_prs"] = {}
    for sha in commit_shas:
        response = session.get(
            f"https://api.github.com/repos/ansible/{repo}/commits/{sha}/pulls"
        )
        prs = response.json()
        for a_pr in prs:
            if not a_pr["merged_at"]:
                continue

            # If we've already seen this PR we don't need to check again
            try:
                if a_pr["html_url"] in tag_dict["associated_prs"]:
                    continue
            except:
                print("Unable to check on PR")
                print(json.dumps(a_pr, indent=4))
                sys.exit(255)
            tag_dict["associated_prs"][a_pr["html_url"]] = {
                "body": a_pr.get("body", ""),
                "commit": sha,
                "approvals": [],
            }
            response = session.get(
                f"https://api.github.com/repos/ansible/{repo}/pulls/{a_pr['number']}/reviews"
            )
            for approver in response.json():
                tag_dict["associated_prs"][a_pr["html_url"]]["approvals"].append(
                    {"user": approver["user"]["login"], "state": approver["state"]}
                )


def getReleaseBranches(repo, session):
    print("Getting current versions")
    latest_release = 1.0
    release_branches = []
    page = 1
    while page == 1 or len(response.json()) == 100:
        response = session.get(
            f"https://api.github.com/repos/ansible/{repo}/branches?per_page=100&page={page}"
        )
        if (
            "X-RateLimit-Limit" in response.headers
            and int(response.headers["X-RateLimit-Limit"]) <= 60
        ):
            print(
                "Your key in .github_creds did not work right and you are using unauthenticated requests"
            )
            print("This script would likely overrun your available requests, exiting")
            sys.exit(3)
        for branch in response.json():
            if repo == "awx":
                if re.fullmatch("devel", branch.get("name", "")):
                    release = "devel"
                    release_branches.append(
                        (branch.get("name"), release, branch["commit"].get("sha"))
                    )
            else:
                if re.fullmatch("release_\d.\d", branch.get("name", "")):
                    release = branch.get("name", "").replace("release_", "")[0:3]
                    release_branches.append(
                        (branch.get("name"), release, branch["commit"].get("sha"))
                    )
        page = page + 1

    return release_branches


def getTags(repo, session):
    print(f"Getting {repo} tags")
    query = f"""{{ repository(owner: "ansible", name: "{repo}") {{
            refs(refPrefix: "refs/tags/", last: 100, orderBy: {{field: TAG_COMMIT_DATE, direction: DESC}}) {{
                edges {{
                    node {{
                        name
                        target {{
                            oid
                            ... on Tag {{
                                tagger {{
                                    name
                                    date
                                }}
                            }}
                        }}
                    }}
                }}
            }}
        }}
    }}"""
    query_dict = {"query": query}

    tags = {}
    # If we end up with > 100 tags we will have to paganate the query
    response = session.post(f"https://api.github.com/graphql", json=query_dict)
    json_data = response.json()
    for tag in json_data["data"]["repository"]["refs"]["edges"]:
        tag = tag["node"]
        tags[tag["name"]] = {
            "author": tag.get("target", {}).get("tagger", {}).get("name", "Unknown"),
            "date": tag.get("target", {}).get("tagger", {}).get("date", "Unknown"),
            "opened_prs": [],
        }

    return tags


def getOpenPRs(repo, latest_tags, session):
    print("Finding opened PRs")
    page = 1
    while page == 1 or len(response.json()) == 100:
        response = session.get(
            f"https://api.github.com/repos/ansible/{repo}/pulls?page={page}&per_page=100&state=open"
        )
        for pr in response.json():
            if pr["base"]["ref"] in latest_tags:
                latest_tags[pr["base"]["ref"]]["opened_prs"].append(
                    {
                        "title": pr["title"],
                        "link": pr["html_url"],
                        "author": pr["user"]["login"],
                        "opened": pr["created_at"],
                    }
                )
        page = page + 1


def main(repoSelection):
    session = requests.Session()
    try:
        token = os.environ["GH_TOKEN"]
        session.headers.update(
            {
                "Authorization": "bearer {}".format(token),
                "Accept": "application/vnd.github.v3+json",
            }
        )
    except Exception:
        print("Missing environment token setting: GH_TOKEN")
        sys.exit(255)
    
    latest_tags = {}

    for gh_repo in repoSelection:
        release_branches = getReleaseBranches(gh_repo, session)
        tags = getTags(gh_repo, session)

        # [X] For each X.Y series
        # [X]   Print the last tag in this series and the tag date
        # [X]   Show merged commits not in last tag, for each give -> tower PRs -> Jira issue
        # [X]   [optional] John also mentioned print reviewers, to assure QE approved it
        # [X]   Show unmerged tower PRs -> Jira issue
        # [X] Give same info for AWX devel branch
        # [X]   Print last tag and tag date
        # [X]   show merged commits since last tag (no further links needed)

        for release_branch, major_minor_version, branch_sha in release_branches:
            for tag_version in tags.keys():
                if tag_version.startswith(major_minor_version):
                    latest_version = latest_tags.get(release_branch, {}).get(
                        "tag", "1.0.0"
                    )
                    if semantic_version.compare(latest_version, tag_version) < 0:
                        latest_tags[release_branch] = {
                            "tag": tag_version,
                            "date": tags[tag_version]["date"],
                            "author": tags[tag_version]["author"],
                            "opened_prs": [],
                        }

        getOpenPRs(gh_repo, latest_tags, session)

        for release_branch in latest_tags.keys():
            print(f"Finding release items for {release_branch}")
            findReleaseItems(
                gh_repo, release_branch, latest_tags[release_branch], session
            )
            latest_tags[release_branch]["opened_pr_count"] = len(
                latest_tags[release_branch]["opened_prs"]
            )
    return latest_tags


if __name__ == "__main__":
    if sys.argv[1:]:
        args = sys.argv[1:]
    else:
        args = ["tower", "awx"]
    data = main(args)
    print(json.dumps(data, indent=4))
