import os
from pathlib import Path
from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from modules import release_status
from threading import Thread

from flask import Flask, request, Response

app = Flask(__name__)

client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])


def process_request(channel_id, user_id, ts):
    releaseOutput = release_status.main(["tower"])
    prdata = ""
    message = ""
    for releases in releaseOutput.keys():
        message += f"*{releaseOutput[releases]['tag']}:*\n*Open PRs: {releaseOutput[releases]['opened_pr_count']}*\n\n"
        if releaseOutput[releases]["opened_prs"]:
            for item in releaseOutput[releases]["opened_prs"]:
                prdata += f"- {item['title']}\n  {item['author']}   {item['link']}\n"
        if prdata:
            message += f"```\n{prdata}```\n\n"
        print(message)
    try:
        client.chat_postMessage(channel=channel_id, thread_ts=ts, text=message)
    except SlackApiError as e:
        print(f"Error: {e}")


@app.route("/get-all", methods=["POST"])
def get_tower():
    data = request.form
    user_name = data.get("user_name")
    channel_id = data.get("channel_id")
    try:
        result = client.chat_postMessage(
            channel=channel_id, text=f":robot_face: <@{user_name}> Working on it"
        )
        thr = Thread(target=process_request, args=[channel_id, user_name, result["ts"]])
        thr.start()
    except SlackApiError as e:
        print(f"Error: {e}")
    return Response()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
