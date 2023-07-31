# gh_awx_notify
A notifier for the current state of releases and PRs

create an .env with and `source .env`  or export prior to running the python code
```
export SLACK_BOT_TOKEN="xoxb-xxxxxxx"
export GH_TOKEN="ghp_xxxxxx"
```

Run the bot with:
```
$ python gh_awx_notify.py
```

For testing, I am using the ngrok to expose the port with slack
```
$ ngrok http 8080
```

Note: the original code has been changed to allow importing the module in gh_awx_notify but it does not fully work with awx due to the semantic_version comparison(WIP). 