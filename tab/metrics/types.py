from dataclasses import dataclass


@dataclass
class Message:
    text: str
    label: str
    url: str
    test: bool = False

    def __str__(self):
        return f"{self.text}: {self.label}"

    @property
    def html(self) -> str:
        return f"{self._html_prefix}{self.text}: <a href='{self.url}' target='_blank'>{self.label}</a>"

    @property
    def markdown(self) -> str:
        """GitHub's Markdown format."""
        return f"{self._markdown_prefix}{self.text}: [{self.label}]({self.url})"

    @property
    def mrkdwn(self) -> str:
        """Slack's Markdown-like format."""
        return f"{self._markdown_prefix}{self.text}: <{self.url}|{self.label}>"

    @property
    def _html_prefix(self) -> str:
        return (
            "<span style='display: inline-block; background-color: #28a745; color: #fff; font-size: 0.75em; font-weight: 500; padding: 0.25em 0.5em; border-radius: 0.375rem; text-transform: uppercase; letter-spacing: 0.025em;'>SAMPLE ALERT</span> "
            if self.test
            else ""
        )

    @property
    def _markdown_prefix(self) -> str:
        return "`SAMPLE ALERT` " if self.test else ""
