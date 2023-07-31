def getTags(repo):
    print("Getting tags")
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
    print(query_dict)
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
    print(query)
    print(query == query_dict)


getTags("awx")
