from datetime import date, datetime
from zoneinfo import ZoneInfo

from django import template

from campaigns import registry
from core import instance

register = template.Library()


@register.filter
def num(value):
    if value is None or value == "":
        return "Unknown"
    return f"{value:,}"


@register.filter
def signed(value):
    if value is None:
        return ""
    return f"+{value:,}" if value > 0 else f"{value:,}"


@register.filter
def day(value):
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%a %-d %b %Y")


@register.filter
def short_day(value):
    if not value:
        return ""
    if isinstance(value, str):
        value = date.fromisoformat(value[:10])
    return value.strftime("%-d %b")


@register.filter
def local(value, fmt="%a %-d %b %Y, %H:%M"):
    if not isinstance(value, datetime):
        return ""
    return value.astimezone(ZoneInfo(instance.load()["timezone"])).strftime(fmt)


@register.filter
def local_input(value):
    """Value for an <input type=datetime-local> in the installation timezone."""
    if not isinstance(value, datetime):
        return ""
    return value.astimezone(ZoneInfo(instance.load()["timezone"])).strftime("%Y-%m-%dT%H:%M")


@register.filter
def channel_label(value):
    return registry.CHANNEL_LABELS.get(value, value or "")


@register.filter
def type_label(value):
    return registry.type_label(value)


@register.filter
def get(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None


@register.filter
def humanise(value):
    text = str(value).replace("_", " ").strip()
    return text[:1].upper() + text[1:]


@register.filter
def percent(value):
    return "" if value is None else f"{round(value * 100)}%"
