import log
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from tab.core.models import Organization


def send_slack_message(channel: str, text: str):
    organization = Organization.objects.get(
        repository_index="https://github.com/KittyCAD"
    )
    client = WebClient(token=organization.slack_bot_token)
    channel_id = _get_channel_id_by_name(client, channel)
    try:
        client.chat_postMessage(
            channel=channel_id, text=text, icon_emoji=":test-analysis-bot:"
        )
        log.info(f"Slack message sent to {channel}: {text}")
    except SlackApiError as e:
        log.error(f"Slack error: {e.response['error']}")


def _get_channel_id_by_name(client: WebClient, name: str) -> str:
    result = client.conversations_list()
    for channel in result["channels"]:
        if channel["name"] == name.lstrip("#"):
            return channel["id"]
    return ""
