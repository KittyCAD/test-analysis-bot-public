from dataclasses import dataclass


@dataclass
class Message:
    text: str
    label: str
    url: str
    extra: str = ""
    debug: bool = False

    def __str__(self):
        return f"{self.text}: {self.label}"

    @property
    def html(self) -> str:
        value = f"{self._html_prefix}"
        value += f"{self.text}: <a href='{self.url}' target='_blank'>{self.label}</a>"
        if self.extra:
            value += f"<pre>{self.extra}</pre>"
        return value

    @property
    def markdown(self) -> str:
        """GitHub's Markdown format."""
        value = f"{self._markdown_prefix}"
        value += f"{self.text}: [{self.label}]({self.url})"
        value += self._markdown_extra
        return value

    @property
    def mrkdwn(self) -> str:
        """Slack's Markdown-like format."""
        value = f"{self._markdown_prefix}"
        label = self.label.replace("::", ":\u200b:")  # prevent interpolation
        value += f"{self.text}: <{self.url}|{label}>"
        value += self._markdown_extra
        return value

    @property
    def _html_prefix(self) -> str:
        return (
            "<span style='display: inline-block; background-color: #28a745; color: #fff; font-size: 0.75em; font-weight: 500; padding: 0.25em 0.5em; border-radius: 0.375rem; text-transform: uppercase; letter-spacing: 0.025em;'>SAMPLE ALERT</span> "
            if self.debug
            else ""
        )

    @property
    def _markdown_prefix(self) -> str:
        return "`SAMPLE ALERT` " if self.debug else ""

    @property
    def _markdown_extra(self) -> str:
        lines = [line for line in self.extra.split("\n") if line.strip()]

        if not lines:
            return ""

        values = "\n\n```\n"

        for count, line in enumerate(lines, start=1):
            if (count == 5 and len(line) <= 10) or count > 5:
                remaining = len(lines) - count + 1
                s = "" if remaining == 1 else "s"
                values += f"({remaining} more line{s} omitted)\n"
                break

            if len(line) > 100:
                line = line[:99] + "…"

            values += line + "\n"

        return values + "```"
