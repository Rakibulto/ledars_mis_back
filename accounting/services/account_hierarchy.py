"""Account hierarchy helpers: descendants and parent balance rollups."""

from collections import defaultdict
from decimal import Decimal


def build_parent_and_children_maps(accounts):
    """
    accounts: iterable of Account (or objects with .id and .parent_id)
    Returns (parent_of, children_of) where children_of[id] = [child_ids]
    """
    parent_of = {}
    children_of = defaultdict(list)
    for acc in accounts:
        aid = acc.id if hasattr(acc, "id") else acc["id"]
        pid = (
            acc.parent_id
            if hasattr(acc, "parent_id")
            else acc.get("parent_id") or acc.get("parent")
        )
        parent_of[aid] = pid
        if pid:
            children_of[pid].append(aid)
    return parent_of, children_of


def get_descendant_ids(account_id, children_of=None, include_self=True, accounts=None):
    """
    Return account_id plus all descendant ids (BFS).
    Pass children_of from build_parent_and_children_maps, or accounts to build it.
    """
    if children_of is None:
        if accounts is None:
            from accounting.models import Account

            accounts = Account.objects.only("id", "parent_id")
        _, children_of = build_parent_and_children_maps(accounts)

    result = []
    if include_self:
        result.append(int(account_id))

    stack = list(children_of.get(int(account_id), []))
    seen = set(result)
    while stack:
        cid = stack.pop()
        if cid in seen:
            continue
        seen.add(cid)
        result.append(cid)
        stack.extend(children_of.get(cid, []))
    return result


def get_leaf_ids(account_ids, children_of):
    """Ids among account_ids that have no children in the map."""
    return [aid for aid in account_ids if not children_of.get(aid)]


def rollup_amount_map(own_map, children_of, account_ids=None):
    """
    own_map: {account_id: Decimal|float|int} — own (leaf) amounts
    Returns {account_id: own + sum(descendants)} for every key in own_map
    and every parent that appears in children_of / account_ids.
    """
    ids = set(account_ids or [])
    ids.update(own_map.keys())
    ids.update(children_of.keys())
    for kids in children_of.values():
        ids.update(kids)

    memo = {}

    def total(aid):
        if aid in memo:
            return memo[aid]
        own = Decimal(str(own_map.get(aid, 0) or 0))
        child_sum = sum((total(cid) for cid in children_of.get(aid, [])), Decimal("0"))
        memo[aid] = own + child_sum
        return memo[aid]

    return {aid: total(aid) for aid in ids}


def rollup_dict_map(own_map, children_of, fields, account_ids=None):
    """
    own_map: {account_id: {field: number, ...}}
    Roll up numeric `fields` so parents include descendant totals.
    Non-listed keys are taken from the account's own row when present.
    """
    ids = set(account_ids or [])
    ids.update(own_map.keys())
    ids.update(children_of.keys())
    for kids in children_of.values():
        ids.update(kids)

    field_maps = {f: {aid: Decimal(str((own_map.get(aid) or {}).get(f, 0) or 0)) for aid in ids} for f in fields}
    rolled_fields = {f: rollup_amount_map(field_maps[f], children_of, account_ids=ids) for f in fields}

    result = {}
    for aid in ids:
        base = dict(own_map.get(aid) or {})
        for f in fields:
            base[f] = rolled_fields[f].get(aid, Decimal("0"))
        result[aid] = base
    return result
