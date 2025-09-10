import log
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from tab.core.models import Organization

from .types import Message


def send_slack_message(
    organization: Organization, channel: str, message: Message
) -> bool:
    if not organization.slack_bot_token:
        log.warning(f"{organization} has no Slack bot token")
        return False

    client = WebClient(token=organization.slack_bot_token)
    channel_id = _get_channel_id(client, channel)
    if not channel_id:
        log.warning(f"{organization} Slack channel not found: {channel}")
        return False

    try:
        client.chat_postMessage(channel=channel_id, text=message.mrkdwn)
    except SlackApiError as e:
        log.error(f"{organization} Slack message not sent: {e.response['error']}")
        return False

    log.debug(f"{organization} Slack message sent to {channel}: {message}")
    return True


def _get_channel_id(client: WebClient, name: str) -> str:
    result = client.conversations_list()
    for channel in result["channels"]:
        if channel["name"] == name.lstrip("#"):
            return channel["id"]
    return ""
