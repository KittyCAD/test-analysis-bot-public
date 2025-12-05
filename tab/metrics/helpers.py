import log
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from tab.core.models import Organization

from .types import Message


def send_slack_message(
    organization: Organization, channel: str, message: Message, unfurl: bool
) -> str | None:
    if not organization.slack_bot_token:
        log.warning(f"{organization} has no Slack bot token")
        return None

    client = WebClient(token=organization.slack_bot_token)
    channel_id = _get_channel_id(client, channel)
    if not channel_id:
        log.warning(f"{organization} Slack channel not found: {channel}")
        return None

    try:
        response = client.chat_postMessage(
            channel=channel_id, text=message.mrkdwn, unfurl_links=unfurl
        )
        log.info(f"{organization} Slack message sent to {channel}")
        response = client.chat_getPermalink(
            channel=channel_id, message_ts=response["ts"]
        )
        return response["permalink"]
    except SlackApiError as e:
        log.error(f"{organization} Slack message not sent: {e.response['error']}")
        return None


def _get_channel_id(client: WebClient, name: str) -> str | None:
    result = client.conversations_list()
    for channel in result["channels"]:
        if channel["name"] == name.lstrip("#"):
            return channel["id"]
    return None
