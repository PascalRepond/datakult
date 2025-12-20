from collections.abc import Iterable

from django.db.models import Count

from .models import Agent


def delete_orphan_agents_by_ids(agent_ids: Iterable[int]) -> int:
    """Delete all Agents in the given IDs that are not linked to any Media.

    Returns the number of Agents deleted.
    """
    ids = list({int(i) for i in agent_ids if i is not None})
    if not ids:
        return 0
    qs = Agent.objects.filter(pk__in=ids).annotate(n=Count("media")).filter(n=0)
    count = qs.count()
    qs.delete()
    return count
