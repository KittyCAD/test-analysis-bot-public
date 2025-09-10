from dataclasses import dataclass


@dataclass
class Message:
    text: str
    label: str
    url: str

    def __str__(self):
        return f"{self.text}: {self.label}"

    @property
    def html(self) -> str:
        return f"{self.text}: <a href='{self.url}' target='_blank'>{self.label}</a>"

    @property
    def markdown(self) -> str:
        """GitHub's Markdown format."""
        return f"{self.text}: [{self.label}]({self.url})"

    @property
    def mrkdwn(self) -> str:
        """Slack's Markdown-like format."""
        return f"{self.text}: <{self.url}|{self.label}>"
