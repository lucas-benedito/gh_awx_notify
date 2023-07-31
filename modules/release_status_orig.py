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

try:
    import semantic_version
except:
    missing_modules.append("semantic_version")

if len(missing_modules) > 0:
    print("This requires python libraries to work; try:")
    for a_module in missing_modules:
        print("    pip install {}".format(a_module))
    sys.exit(1)


def findReleaseItems(repo, release_branch, tag_dict):
    #
    # This loads the commits since the last release and gets their associated PRs and scans those for release_type: [xyz]
    # Any X or Y changes also get captured for bullhorn release notes
    #
    print()
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
            f"https://api.github.com/repos/ansible/tower/commits/{sha}/pulls"
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
                f"https://api.github.com/repos/ansible/tower/pulls/{a_pr['number']}/reviews"
            )
            for approver in response.json():
                tag_dict["associated_prs"][a_pr["html_url"]]["approvals"].append(
                    {"user": approver["user"]["login"], "state": approver["state"]}
                )


def getReleaseBranches():
    print("Getting current versions")
    latest_release = 1.0
    release_branches = []
    page = 1
    while page == 1 or len(response.json()) == 100:
        response = session.get(
            f"https://api.github.com/repos/ansible/tower/branches?per_page=100&page={page}"
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
            if re.fullmatch("release_\d.\d", branch.get("name", "")):
                release = branch.get("name", "").replace("release_", "")[0:3]
                release_branches.append(
                    (branch.get("name"), release, branch.get("sha"))
                )
        page = page + 1

    return release_branches


def getAWXTag():
    print("Getting latest AWX tag")
    query = {
        "query": """{ repository(owner: "ansible", name: "awx") {
          refs(refPrefix: "refs/tags/", last: 100, orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
            edges {
              node {
                name
                target {
                  oid
                  ... on Tag {
                    tagger {
                      name
                      date
                    }
                  }
                }
              }
            }
          }
        }
      }"""
    }

    # If we end up with > 100 tags we will have to paganate the query
    response = session.post(f"https://api.github.com/graphql", json=query)
    json_data = response.json()
    for tag in json_data["data"]["repository"]["refs"]["edges"]:
        tag = tag["node"]
        return {
            "tag": tag["name"],
            "author": tag.get("target", {}).get("tagger", {}).get("name", "Unknown"),
            "date": tag.get("target", {}).get("tagger", {}).get("date", "Unknown"),
            "opened_prs": [],
        }


def getTags():
    print("Getting tags")
    query = {
        "query": """{ repository(owner: "ansible", name: "tower") {
          refs(refPrefix: "refs/tags/", last: 100, orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
            edges {
              node {
                name
                target {
                  oid
                  ... on Tag {
                    tagger {
                      name
                      date
                    }
                  }
                }
              }
            }
          }
        }
      }"""
    }

    tags = {}
    # If we end up with > 100 tags we will have to paganate the query
    response = session.post(f"https://api.github.com/graphql", json=query)
    json_data = response.json()
    for tag in json_data["data"]["repository"]["refs"]["edges"]:
        tag = tag["node"]
        tags[tag["name"]] = {
            "author": tag.get("target", {}).get("tagger", {}).get("name", "Unknown"),
            "date": tag.get("target", {}).get("tagger", {}).get("date", "Unknown"),
        }

    return tags


def getOpenPRs(latest_tags):
    print("Finding opened PRs")
    page = 1
    while page == 1 or len(response.json()) == 100:
        response = session.get(
            f"https://api.github.com/repos/ansible/tower/pulls?per_page=100&state=open"
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


#
# Load the users session information
#
session = requests.Session()
try:
    print("Loading credentials")
    with open(".github_creds", "r") as f:
        password = f.read().strip()
    session.headers.update(
        {
            "Authorization": "bearer {}".format(password),
            "Accept": "application/vnd.github.v3+json",
        }
    )
except Exception:
    print("Failed to load credentials from ./.github_creds")
    sys.exit(255)

release_branches = getReleaseBranches()

tags = getTags()

# [X] For each X.Y series
# [X]   Print the last tag in this series and the tag date
# [X]   Show merged commits not in last tag, for each give -> tower PRs -> Jira issue
# [X]   [optional] John also mentioned print reviewers, to assure QE approved it
# [X]   Show unmerged tower PRs -> Jira issue
# [X] Give same info for AWX devel branch
# [X]   Print last tag and tag date
# [X]   show merged commits since last tag (no further links needed)

latest_tags = {}
for release_branch, major_minor_version, branch_sha in release_branches:
    for tag_version in tags.keys():
        if tag_version.startswith(major_minor_version):
            latest_version = latest_tags.get(release_branch, {}).get("tag", "1.0.0")
            if semantic_version.compare(latest_version, tag_version) < 0:
                latest_tags[release_branch] = {
                    "tag": tag_version,
                    "date": tags[tag_version]["date"],
                    "author": tags[tag_version]["author"],
                    "opened_prs": [],
                }

getOpenPRs(latest_tags)

for release_branch in latest_tags.keys():
    print(f"Finding release items for {release_branch}")
    findReleaseItems("tower", release_branch, latest_tags[release_branch])
    latest_tags[release_branch]["opened_pr_count"] = len(
        latest_tags[release_branch]["opened_prs"]
    )


latest_tags["awx_devel"] = getAWXTag()
findReleaseItems("awx", "devel", latest_tags["awx_devel"])

print(json.dumps(latest_tags, indent=4))
